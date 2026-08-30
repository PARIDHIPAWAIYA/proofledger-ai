from __future__ import annotations

from functools import cached_property

from proofledger.domain.controls import FinanceControlEngine
from proofledger.domain.graph import FinancialLifecycleGraph
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
from proofledger.services.ingestion import IngestionService
from proofledger.services.synthetic import DatasetBundle, SyntheticFinanceGenerator


class DemoWorkspace:
    """Read-mostly in-memory application state for the reproducible Buildathon demo."""

    def __init__(
        self,
        seed: int = 2026,
        order_count: int = 600,
        settlement_size: int = 50,
    ) -> None:
        self.dataset: DatasetBundle = SyntheticFinanceGenerator(seed=seed).generate(
            order_count=order_count,
            settlement_size=settlement_size,
        )
        self.source_records_by_id = {
            record.record_id: record for record in self.dataset.records
        }
        self.certificates: dict[str, SettlementCertificate] = {}
        self.review_resolutions: dict[str, ReviewResolution] = {}
        self.ingestion = IngestionService()

    @property
    def effective_records(self) -> list[EvidenceRecord]:
        """Return a derived evidence view while preserving every original source row."""

        resolutions_by_candidate = {
            resolution.candidate_record_id: resolution
            for resolution in self.review_resolutions.values()
            if resolution.candidate_record_id
        }
        records: list[EvidenceRecord] = []
        for record in self.dataset.records:
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
            for record in self.dataset.records
            if record.object_type == ObjectType.PAYMENT
        ]
        failed = [
            result for result in self.controls if result.status == ControlStatus.FAIL
        ]
        settlement_decisions = [
            decision
            for decision in self.decisions
            if decision.left_record_ids[0].startswith("razorpay_settlement_")
        ]
        automated = sum(
            decision.status == DecisionStatus.AUTO_APPROVED
            for decision in settlement_decisions
        )
        graph_summary = self.graph.summary()
        return {
            "dataset_id": self.dataset.dataset_id,
            "evidence_records": len(self.dataset.records),
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
