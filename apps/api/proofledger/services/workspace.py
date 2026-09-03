from __future__ import annotations

from datetime import timedelta
from functools import cached_property

from proofledger.domain.calibration import SplitConformalCalibrator
from proofledger.domain.controls import FinanceControlEngine
from proofledger.domain.graph import FinancialLifecycleGraph
from proofledger.domain.ingestion import ActivationAction, IngestionActivation
from proofledger.domain.models import (
    ControlStatus,
    DecisionStatus,
    EvidenceRecord,
    ObjectType,
    ReviewResolution,
    SettlementCertificate,
    SourceSystem,
    stable_hash,
)
from proofledger.domain.reconciliation import ReconciliationEngine
from proofledger.domain.review import MinimumEvidenceReviewPlanner
from proofledger.services.benchmark import ReconciliationBenchmark
from proofledger.services.closing import JournalProposalService
from proofledger.services.ingestion import IngestionError, IngestionService
from proofledger.services.persistence import SQLAlchemyIngestionRepository
from proofledger.services.synthetic import DatasetBundle, SyntheticFinanceGenerator


class DemoWorkspace:
    """Read-mostly in-memory application state for the reproducible Buildathon demo."""

    def __init__(
        self,
        seed: int = 2026,
        order_count: int = 600,
        settlement_size: int = 50,
        repository: SQLAlchemyIngestionRepository | None = None,
    ) -> None:
        self.dataset: DatasetBundle = SyntheticFinanceGenerator(seed=seed).generate(
            order_count=order_count,
            settlement_size=settlement_size,
        )
        self.certificates: dict[str, SettlementCertificate] = {}
        self.review_resolutions: dict[str, ReviewResolution] = {}
        self.repository = repository
        self.ingestion = IngestionService(repository)
        self.active_manifest_ids: set[str] = set()
        self.ingestion_activations = (
            repository.load_activations() if repository else []
        )
        for event in self.ingestion_activations:
            if not event.verify_integrity():
                raise RuntimeError(
                    f"persisted activation {event.activation_id} failed verification"
                )
            if event.manifest_id not in self.ingestion.manifests:
                raise RuntimeError(
                    f"activation {event.activation_id} references a missing manifest"
                )
            if event.action == ActivationAction.ACTIVATE:
                self.active_manifest_ids.add(event.manifest_id)
            else:
                self.active_manifest_ids.discard(event.manifest_id)

    @property
    def active_import_records(self) -> list[EvidenceRecord]:
        return [
            record
            for manifest_id in sorted(self.active_manifest_ids)
            for record in self.ingestion.records_by_manifest.get(manifest_id, [])
        ]

    @property
    def source_records(self) -> list[EvidenceRecord]:
        return [*self.dataset.records, *self.active_import_records]

    @property
    def source_records_by_id(self) -> dict[str, EvidenceRecord]:
        return {record.record_id: record for record in self.source_records}

    @property
    def effective_records(self) -> list[EvidenceRecord]:
        """Return a derived evidence view while preserving every original source row."""

        resolutions_by_candidate = {
            resolution.candidate_record_id: resolution
            for resolution in self.review_resolutions.values()
            if resolution.candidate_record_id
        }
        records: list[EvidenceRecord] = []
        for record in self.source_records:
            resolution = resolutions_by_candidate.get(record.record_id)
            if not resolution:
                records.append(record)
                continue
            settlement = self.source_records_by_id[resolution.settlement_record_id]
            attributes = {
                **record.attributes,
                "evidence_overlay": "controller_bank_reference_attestation",
                "original_source_hash": record.source_hash,
                "review_resolution_id": resolution.resolution_id,
                "attachment_sha256": resolution.evidence_sha256.lower(),
            }
            payload = record.model_dump(exclude={"source_hash"})
            payload.update(
                settlement_id=settlement.settlement_id,
                bank_reference=resolution.provided_bank_reference,
                attributes=attributes,
            )
            records.append(EvidenceRecord.model_validate(payload))
        for resolution in self.review_resolutions.values():
            if resolution.candidate_record_id:
                continue
            settlement = self.source_records_by_id[resolution.settlement_record_id]
            records.append(
                EvidenceRecord(
                    record_id=f"review_bank_{resolution.resolution_id}",
                    source=SourceSystem.BANK,
                    object_type=ObjectType.BANK_CREDIT,
                    occurred_at=resolution.provided_occurred_at,
                    amount_paise=resolution.provided_amount_paise,
                    external_id=resolution.provided_external_id,
                    settlement_id=settlement.settlement_id,
                    bank_reference=resolution.provided_bank_reference,
                    narration="CONTROLLER-VERIFIED BANK STATEMENT EVIDENCE",
                    status="credited",
                    attributes={
                        "evidence_overlay": "controller_bank_statement_attachment",
                        "review_resolution_id": resolution.resolution_id,
                        "attachment_sha256": resolution.evidence_sha256.lower(),
                    },
                )
            )
        return records

    @property
    def records_by_id(self) -> dict[str, EvidenceRecord]:
        return {record.record_id: record for record in self.effective_records}

    @property
    def graph(self) -> FinancialLifecycleGraph:
        return FinancialLifecycleGraph.from_records(self.effective_records)

    @property
    def controls(self):
        return FinanceControlEngine().evaluate(self.effective_records)

    @property
    def decisions(self):
        return ReconciliationEngine().reconcile(self.effective_records)

    @property
    def questions(self):
        return MinimumEvidenceReviewPlanner().questions(self.decisions)

    @cached_property
    def benchmark(self):
        return ReconciliationBenchmark().evaluate(
            self.dataset.records,
            self.dataset.true_links,
            ReconciliationEngine().reconcile(self.dataset.records),
        )

    def calibration(self, alpha: float = 0.10) -> dict:
        """Split-conformal calibration over labelled settlement→bank confidences.

        The labelled settlements are split in half. The first half is the calibration
        set that produces a minimum-confidence threshold for the requested error level;
        the second half is never seen by the fit and reports empirical coverage. The
        threshold is then applied to the live review queue to size candidate sets.
        """

        records = self.dataset.records
        bank_ids = {
            record.record_id
            for record in records
            if record.object_type == ObjectType.BANK_CREDIT
        }
        settlement_ids = {
            record.record_id
            for record in records
            if record.object_type == ObjectType.SETTLEMENT
        }
        scored: list[tuple[str, float]] = []
        for decision in ReconciliationEngine().reconcile(records):
            left = decision.left_record_ids[0]
            if left not in settlement_ids:
                continue
            linked = [
                record_id
                for record_id in self.dataset.true_links.get(left, [])
                if record_id in bank_ids
            ]
            if not linked:
                continue
            true_id = linked[0]
            if true_id in decision.right_record_ids:
                score = decision.confidence
            else:
                candidate = next(
                    (
                        item
                        for item in decision.candidates
                        if item.candidate_id == true_id
                    ),
                    None,
                )
                score = candidate.confidence if candidate else 0.0
            scored.append((left, score))

        scored.sort()
        if len(scored) < 4:
            raise ValueError(
                "at least four labelled settlements are required to split-calibrate"
            )
        midpoint = len(scored) // 2
        calibration_scores = [score for _, score in scored[:midpoint]]
        holdout_scores = [score for _, score in scored[midpoint:]]
        profile = SplitConformalCalibrator().fit(calibration_scores, alpha=alpha)
        holdout_coverage = sum(
            score >= profile.minimum_confidence for score in holdout_scores
        ) / len(holdout_scores)

        records_by_id = self.records_by_id
        candidate_sets = [
            {
                "decision_id": decision.decision_id,
                "settlement_record_id": decision.left_record_ids[0],
                "decision_status": decision.status,
                "candidates_generated": len(decision.candidates),
                "candidate_set": [
                    item.candidate_id
                    for item in SplitConformalCalibrator.candidate_set(decision, profile)
                ],
            }
            for decision in self.decisions
            if decision.requires_human
            and records_by_id[decision.left_record_ids[0]].object_type
            == ObjectType.SETTLEMENT
        ]
        singleton = sum(len(item["candidate_set"]) == 1 for item in candidate_sets)
        empty = sum(not item["candidate_set"] for item in candidate_sets)
        return {
            "profile": profile,
            "calibration_size": len(calibration_scores),
            "holdout_size": len(holdout_scores),
            "holdout_coverage": round(holdout_coverage, 4),
            "candidate_sets": candidate_sets,
            "singleton_sets": singleton,
            "empty_sets": empty,
            "caveats": [
                "The threshold is fitted on a labelled half and measured on the unseen half.",
                "Coverage is a dataset-level property, never a guarantee for one payout.",
                "A calibrated candidate set never auto-approves; it only sizes the question.",
            ],
        }

    @property
    def settlements(self) -> list[EvidenceRecord]:
        return [
            record
            for record in self.effective_records
            if record.object_type == ObjectType.SETTLEMENT
        ]

    def settlement(self, settlement_id: str) -> EvidenceRecord | None:
        return next(
            (
                record
                for record in self.settlements
                if record.settlement_id == settlement_id
            ),
            None,
        )

    def settlement_controls(self, settlement: EvidenceRecord):
        object_id = f"settlement:{settlement.settlement_id}"
        return [
            result
            for result in self.controls
            if object_id in result.object_ids
            or settlement.record_id in result.evidence_ids
        ]

    def settlement_decision(self, settlement: EvidenceRecord):
        return next(
            (
                decision
                for decision in self.decisions
                if settlement.record_id in decision.left_record_ids
            ),
            None,
        )

    def settlement_summary(self, settlement: EvidenceRecord) -> dict:
        controls = self.settlement_controls(settlement)
        failed = [
            result for result in controls if result.status == ControlStatus.FAIL
        ]
        decision = self.settlement_decision(settlement)
        return {
            "settlement_id": settlement.settlement_id,
            "occurred_at": settlement.occurred_at,
            "gross_paise": settlement.attributes.get("gross_paise", 0),
            "fees_paise": settlement.attributes.get("fees_paise", 0),
            "tax_paise": settlement.attributes.get("tax_paise", 0),
            "refunds_paise": settlement.attributes.get("refunds_paise", 0),
            "net_paise": settlement.amount_paise,
            "bank_reference": settlement.bank_reference,
            "status": "blocked" if failed else "ready",
            "failed_controls": len(failed),
            "match_tier": decision.tier if decision else None,
            "decision_status": decision.status if decision else None,
            "confidence": decision.confidence if decision else None,
        }

    def overview(self) -> dict:
        payments = [
            record
            for record in self.effective_records
            if record.object_type == ObjectType.PAYMENT
        ]
        failed = [
            result for result in self.controls if result.status == ControlStatus.FAIL
        ]
        records_by_id = self.records_by_id
        settlement_decisions = [
            decision
            for decision in self.decisions
            if records_by_id[decision.left_record_ids[0]].object_type
            == ObjectType.SETTLEMENT
        ]
        automated = sum(
            decision.status == DecisionStatus.AUTO_APPROVED
            for decision in settlement_decisions
        )
        graph_summary = self.graph.summary()
        return {
            "dataset_id": self.dataset.dataset_id,
            "evidence_records": len(self.effective_records),
            "active_imports": len(self.active_manifest_ids),
            "imported_records": len(self.active_import_records),
            "captured_paise": sum(record.amount_paise for record in payments),
            "settled_paise": sum(record.amount_paise for record in self.settlements),
            "settlement_count": len(self.settlements),
            "failed_controls": len(failed),
            "critical_exceptions": sum(
                result.status == ControlStatus.FAIL
                and result.severity.value == "critical"
                for result in self.controls
            ),
            "review_queue": len(self.questions),
            "automation_rate": (
                round(automated / len(settlement_decisions), 4)
                if settlement_decisions
                else 0
            ),
            "graph": {
                "objects": graph_summary.object_count,
                "events": graph_summary.event_count,
                "edges": graph_summary.edge_count,
                "components": graph_summary.weak_component_count,
            },
        }

    def journal_for(self, settlement: EvidenceRecord):
        return JournalProposalService().propose(
            settlement,
            self.effective_records,
        )

    def demo_bank_statement(self) -> dict[str, str]:
        decision = next(
            (
                item
                for item in self.decisions
                if not item.right_record_ids
                and self.records_by_id[item.left_record_ids[0]].object_type
                == ObjectType.SETTLEMENT
            ),
            None,
        )
        if not decision:
            raise IngestionError("no missing bank-evidence scenario remains in this workspace")
        settlement = self.records_by_id[decision.left_record_ids[0]]
        amount = f"{settlement.amount_paise // 100}.{settlement.amount_paise % 100:02d}"
        value_date = (settlement.occurred_at + timedelta(days=1)).date().isoformat()
        external_id = f"judge_bank_{settlement.settlement_id}"
        content = (
            "Transaction ID,Value Date,Credit Amount,UTR,Settlement ID,Description\r\n"
            f"{external_id},{value_date},{amount},{settlement.bank_reference},"
            f"{settlement.settlement_id},Controller-verified settlement credit\r\n"
        )
        return {
            "filename": "judge-ready-missing-bank-evidence.csv",
            "content": content,
            "settlement_id": settlement.settlement_id or "",
            "expected_transition": "blocked_to_ready",
        }

    def activate_manifest(
        self,
        manifest_id: str,
        *,
        actor: str,
        rationale: str,
    ) -> dict:
        manifest = self.ingestion.manifests.get(manifest_id)
        if not manifest:
            raise IngestionError("ingestion manifest not found")
        if manifest_id in self.active_manifest_ids:
            raise IngestionError("ingestion manifest is already active")
        verification = self.ingestion.verify(manifest_id)
        if not verification.valid:
            raise IngestionError(
                "ingestion manifest failed verification and cannot be activated",
                verification.failures,
            )
        imported = self.ingestion.records_by_manifest[manifest_id]
        current = self.effective_records
        current_ids = {record.record_id for record in current}
        collisions = sorted(
            record.record_id
            for record in imported
            if record.record_id in current_ids
        )
        if collisions:
            raise IngestionError("record ID collision", collisions[:10])
        current_identities = {
            (record.source, record.object_type, record.external_id) for record in current
        }
        identity_collisions = sorted(
            record.external_id
            for record in imported
            if (record.source, record.object_type, record.external_id) in current_identities
        )
        if identity_collisions:
            raise IngestionError(
                "source records already exist for these external IDs",
                identity_collisions[:10],
            )
        self._reject_duplicate_bank_masking(imported, current)

        before = self._activation_snapshot()
        self.active_manifest_ids.add(manifest_id)
        after = self._activation_snapshot()
        event = self._activation_event(
            manifest_id,
            ActivationAction.ACTIVATE,
            actor,
            rationale,
        )
        if self.repository:
            try:
                self.repository.save_activation(event)
            except Exception:
                self.active_manifest_ids.remove(manifest_id)
                raise
        self.ingestion_activations.append(event)
        return self._activation_outcome(event, before, after)

    def deactivate_manifest(
        self,
        manifest_id: str,
        *,
        actor: str,
        rationale: str,
    ) -> dict:
        if manifest_id not in self.active_manifest_ids:
            raise IngestionError("ingestion manifest is not active")
        imported_ids = {
            record.record_id
            for record in self.ingestion.records_by_manifest[manifest_id]
        }
        referenced = [
            resolution.resolution_id
            for resolution in self.review_resolutions.values()
            if resolution.settlement_record_id in imported_ids
            or resolution.candidate_record_id in imported_ids
        ]
        if referenced:
            raise IngestionError(
                "cannot deactivate evidence referenced by controller resolutions",
                referenced,
            )

        before = self._activation_snapshot()
        self.active_manifest_ids.remove(manifest_id)
        after = self._activation_snapshot()
        event = self._activation_event(
            manifest_id,
            ActivationAction.DEACTIVATE,
            actor,
            rationale,
        )
        if self.repository:
            try:
                self.repository.save_activation(event)
            except Exception:
                self.active_manifest_ids.add(manifest_id)
                raise
        self.ingestion_activations.append(event)
        return self._activation_outcome(event, before, after)

    @staticmethod
    def _reject_duplicate_bank_masking(
        imported: list[EvidenceRecord],
        current: list[EvidenceRecord],
    ) -> None:
        banks = [
            record for record in current if record.object_type == ObjectType.BANK_CREDIT
        ]
        conflicts = []
        for record in imported:
            if record.object_type != ObjectType.BANK_CREDIT:
                continue
            if any(
                (
                    record.settlement_id
                    and bank.settlement_id == record.settlement_id
                )
                or (
                    record.bank_reference
                    and bank.bank_reference
                    and bank.bank_reference.upper() == record.bank_reference.upper()
                )
                for bank in banks
            ):
                conflicts.append(record.external_id)
        if conflicts:
            raise IngestionError(
                "bank evidence already exists for the linked settlement; correct the source "
                "instead of masking it with a second row",
                sorted(conflicts)[:10],
            )

    def _activation_snapshot(self) -> dict:
        summaries = {
            settlement.settlement_id: self.settlement_summary(settlement)
            for settlement in self.settlements
        }
        overview = self.overview()
        return {
            "evidence_records": overview["evidence_records"],
            "active_imports": overview["active_imports"],
            "imported_records": overview["imported_records"],
            "failed_controls": overview["failed_controls"],
            "review_queue": overview["review_queue"],
            "ready_settlements": sum(
                summary["status"] == "ready" for summary in summaries.values()
            ),
            "settlements": summaries,
        }

    def _activation_event(
        self,
        manifest_id: str,
        action: ActivationAction,
        actor: str,
        rationale: str,
    ) -> IngestionActivation:
        manifest = self.ingestion.manifests[manifest_id]
        records = self.ingestion.records_by_manifest[manifest_id]
        return IngestionActivation(
            manifest_id=manifest_id,
            manifest_hash=manifest.manifest_hash,
            action=action,
            actor=actor.strip(),
            rationale=rationale.strip(),
            record_count=len(records),
            affected_settlement_ids=sorted(
                {record.settlement_id for record in records if record.settlement_id}
            ),
        )

    @staticmethod
    def _activation_outcome(
        event: IngestionActivation,
        before: dict,
        after: dict,
    ) -> dict:
        before_settlements = before.pop("settlements")
        after_settlements = after.pop("settlements")
        settlement_ids = sorted(set(before_settlements) | set(after_settlements))
        affected = [
            {
                "settlement_id": settlement_id,
                "before": before_settlements.get(settlement_id),
                "after": after_settlements.get(settlement_id),
            }
            for settlement_id in settlement_ids
            if before_settlements.get(settlement_id)
            != after_settlements.get(settlement_id)
        ]
        return {
            "activation": event,
            "audit_verified": event.verify_integrity(),
            "before": before,
            "after": after,
            "affected_settlements": affected,
        }

    def resolve_review(
        self,
        question_id: str,
        *,
        candidate_id: str | None,
        bank_reference: str,
        amount_paise: int | None,
        occurred_at,
        external_id: str | None,
        evidence_sha256: str,
        actor: str,
        rationale: str,
    ) -> dict:
        """Attach controller evidence, then recompute every authoritative output."""

        if question_id in self.review_resolutions:
            raise ValueError("review question is already resolved")
        question = next(
            (item for item in self.questions if item.question_id == question_id),
            None,
        )
        if not question:
            raise ValueError("review question is stale or not found")
        decision = next(
            (item for item in self.decisions if item.decision_id == question.decision_id),
            None,
        )
        if not decision:
            raise ValueError("reconciliation decision is no longer available")
        settlement = self.source_records_by_id[decision.left_record_ids[0]]
        if settlement.object_type != ObjectType.SETTLEMENT:
            raise ValueError("review question does not belong to a settlement")
        candidate = None
        if candidate_id:
            allowed_candidates = {item.candidate_id for item in decision.candidates}
            if candidate_id not in allowed_candidates:
                raise ValueError("candidate is not part of this review question")
            candidate = self.source_records_by_id.get(candidate_id)
            if not candidate or candidate.object_type != ObjectType.BANK_CREDIT:
                raise ValueError("candidate bank evidence was not found")
            if any(
                item.candidate_record_id == candidate_id
                for item in self.review_resolutions.values()
            ):
                raise ValueError("candidate bank evidence is already linked")
            amount_paise = candidate.amount_paise
            occurred_at = candidate.occurred_at
            external_id = candidate.external_id
        else:
            if decision.right_record_ids:
                raise ValueError(
                    "an exact bank row already exists; correct its source amount "
                    "instead of attaching a duplicate"
                )
            if amount_paise is None or occurred_at is None or not external_id:
                raise ValueError(
                    "a new statement row requires amount, timestamp, and external ID"
                )
            if external_id in {
                record.external_id for record in self.effective_records
            }:
                raise ValueError("bank statement external ID already exists")
        normalized_reference = bank_reference.strip().upper()
        if normalized_reference != (settlement.bank_reference or "").upper():
            raise ValueError("provided UTR does not match the settlement payout reference")

        before_questions = len(self.questions)
        before_summaries = {
            item.settlement_id: self.settlement_summary(item)
            for item in self.settlements
        }
        resolution = ReviewResolution(
            resolution_id=(
                "res_"
                + stable_hash(
                    {
                        "question_id": question_id,
                        "candidate_id": candidate_id,
                        "amount_paise": amount_paise,
                        "occurred_at": str(occurred_at),
                        "external_id": external_id,
                        "evidence_sha256": evidence_sha256.lower(),
                    }
                )[:12]
            ),
            question_id=question_id,
            decision_id=decision.decision_id,
            settlement_record_id=settlement.record_id,
            candidate_record_id=candidate.record_id if candidate else None,
            provided_bank_reference=normalized_reference,
            provided_amount_paise=amount_paise,
            provided_occurred_at=occurred_at,
            provided_external_id=external_id,
            evidence_sha256=evidence_sha256.lower(),
            original_candidate_hash=candidate.source_hash if candidate else None,
            actor=actor.strip(),
            rationale=rationale.strip(),
        )
        self.review_resolutions[question_id] = resolution

        after_summaries = {
            item.settlement_id: self.settlement_summary(item)
            for item in self.settlements
        }
        affected = [
            {
                "settlement_id": settlement_id,
                "before_status": before_summaries[settlement_id]["status"],
                "after_status": summary["status"],
                "before_decision": before_summaries[settlement_id][
                    "decision_status"
                ],
                "after_decision": summary["decision_status"],
            }
            for settlement_id, summary in after_summaries.items()
            if summary != before_summaries[settlement_id]
        ]
        current_settlement = self.settlement(settlement.settlement_id or "")
        if not current_settlement:
            raise RuntimeError("resolved settlement disappeared from the workspace")
        remaining_blockers = [
            control.control_id
            for control in self.settlement_controls(current_settlement)
            if control.status == ControlStatus.FAIL
        ]
        return {
            "resolution": resolution,
            "audit_verified": resolution.verify_integrity(),
            "queue_before": before_questions,
            "queue_after": len(self.questions),
            "affected_settlements": affected,
            "settlement": self.settlement_summary(current_settlement),
            "remaining_blockers": remaining_blockers,
        }
