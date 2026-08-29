from __future__ import annotations

from pydantic import BaseModel, Field
from rapidfuzz.fuzz import token_set_ratio

from proofledger.domain.models import (
    DecisionStatus,
    EvidenceRecord,
    ObjectType,
    ReconciliationDecision,
)


class BenchmarkMetrics(BaseModel):
    method: str
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    review_rate: float = Field(ge=0, le=1)
    incorrect_auto_approvals: int = Field(ge=0)
    predicted_links: int = Field(ge=0)


class BenchmarkReport(BaseModel):
    labeled_settlements: int
    exact: BenchmarkMetrics
    fuzzy: BenchmarkMetrics
    proofledger: BenchmarkMetrics
    caveats: list[str]


class ReconciliationBenchmark:
    """Compare simple baselines against ProofLedger on held-out synthetic labels."""

    def evaluate(
        self,
        records: list[EvidenceRecord],
        true_links: dict[str, list[str]],
        decisions: list[ReconciliationDecision],
    ) -> BenchmarkReport:
        settlements = [
            record for record in records if record.object_type == ObjectType.SETTLEMENT
        ]
        banks = {
            record.record_id: record
            for record in records
            if record.object_type == ObjectType.BANK_CREDIT
        }
        truth = {
            (settlement.record_id, linked_id)
            for settlement in settlements
            for linked_id in true_links.get(settlement.record_id, [])
            if linked_id in banks
        }
        exact_pairs = self._exact_pairs(settlements, list(banks.values()))
        fuzzy_pairs = self._fuzzy_pairs(settlements, list(banks.values()))
        proof_pairs = {
            (decision.left_record_ids[0], right_id)
            for decision in decisions
            if decision.left_record_ids[0].startswith("razorpay_settlement_")
            and decision.status != DecisionStatus.ABSTAINED
            for right_id in decision.right_record_ids
        }
        proof_auto_pairs = {
            (decision.left_record_ids[0], right_id)
            for decision in decisions
            if decision.left_record_ids[0].startswith("razorpay_settlement_")
            and decision.status == DecisionStatus.AUTO_APPROVED
            for right_id in decision.right_record_ids
        }
        total = len(settlements)
        reviewed = sum(
            decision.left_record_ids[0].startswith("razorpay_settlement_")
            and decision.status
            in {DecisionStatus.ABSTAINED, DecisionStatus.NEEDS_REVIEW}
            for decision in decisions
        )
        return BenchmarkReport(
            labeled_settlements=total,
            exact=self._metrics("Exact ID baseline", exact_pairs, truth, total, 0),
            fuzzy=self._metrics("Fuzzy narration baseline", fuzzy_pairs, truth, total, 0),
            proofledger=self._metrics(
                "ProofLedger",
                proof_pairs,
                truth,
                total,
                reviewed,
                auto_pairs=proof_auto_pairs,
            ),
            caveats=[
                "Results use deterministic synthetic data, not production merchant traffic.",
                "Ground-truth labels are hidden from all matching methods during prediction.",
                "Review rate is a safety/productivity trade-off, not an error rate.",
            ],
        )

    @staticmethod
    def _exact_pairs(
        settlements: list[EvidenceRecord],
        banks: list[EvidenceRecord],
    ) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for settlement in settlements:
            matched = next(
                (
                    bank
                    for bank in banks
                    if bank.bank_reference
                    and bank.bank_reference == settlement.bank_reference
                    and bank.amount_paise == settlement.amount_paise
                ),
                None,
            )
            if matched:
                pairs.add((settlement.record_id, matched.record_id))
        return pairs

    @staticmethod
    def _fuzzy_pairs(
        settlements: list[EvidenceRecord],
        banks: list[EvidenceRecord],
    ) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for settlement in settlements:
            expected = " ".join(
                token
                for token in [settlement.settlement_id, settlement.bank_reference]
                if token
            )
            if not banks:
                continue
            matched = max(
                banks,
                key=lambda bank: (
                    token_set_ratio(expected, bank.narration or ""),
                    -abs(bank.amount_paise - settlement.amount_paise),
                ),
            )
            pairs.add((settlement.record_id, matched.record_id))
        return pairs

    @staticmethod
    def _metrics(
        method: str,
        predictions: set[tuple[str, str]],
        truth: set[tuple[str, str]],
        total: int,
        reviewed: int,
        auto_pairs: set[tuple[str, str]] | None = None,
    ) -> BenchmarkMetrics:
        true_positives = len(predictions & truth)
        precision = true_positives / len(predictions) if predictions else 1.0
        recall = true_positives / len(truth) if truth else 1.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        assumed_auto = predictions if auto_pairs is None else auto_pairs
        return BenchmarkMetrics(
            method=method,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            review_rate=round(reviewed / total, 4) if total else 0.0,
            incorrect_auto_approvals=len(assumed_auto - truth),
            predicted_links=len(predictions),
        )
