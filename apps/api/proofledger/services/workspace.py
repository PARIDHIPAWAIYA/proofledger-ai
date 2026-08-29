from __future__ import annotations

from functools import cached_property

from proofledger.domain.controls import FinanceControlEngine
from proofledger.domain.graph import FinancialLifecycleGraph
from proofledger.domain.models import (
    ControlStatus,
    DecisionStatus,
    EvidenceRecord,
    ObjectType,
    SettlementCertificate,
)
from proofledger.domain.reconciliation import ReconciliationEngine
from proofledger.domain.review import MinimumEvidenceReviewPlanner
from proofledger.services.benchmark import ReconciliationBenchmark
from proofledger.services.closing import JournalProposalService
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
        self.records_by_id = {
            record.record_id: record for record in self.dataset.records
        }
        self.certificates: dict[str, SettlementCertificate] = {}

    @cached_property
    def graph(self) -> FinancialLifecycleGraph:
        return FinancialLifecycleGraph.from_records(self.dataset.records)

    @cached_property
    def controls(self):
        return FinanceControlEngine().evaluate(self.dataset.records)

    @cached_property
    def decisions(self):
        return ReconciliationEngine().reconcile(self.dataset.records)

    @cached_property
    def questions(self):
        return MinimumEvidenceReviewPlanner().questions(self.decisions)

    @cached_property
    def benchmark(self):
        return ReconciliationBenchmark().evaluate(
            self.dataset.records,
            self.dataset.true_links,
            self.decisions,
        )

    @property
    def settlements(self) -> list[EvidenceRecord]:
        return [
            record
            for record in self.dataset.records
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
            self.dataset.records,
        )
