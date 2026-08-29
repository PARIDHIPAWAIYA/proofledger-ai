from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from rapidfuzz.fuzz import token_set_ratio

from proofledger.domain.models import (
    CandidateMatch,
    DecisionStatus,
    EvidenceRecord,
    MatchTier,
    ObjectType,
    ReconciliationDecision,
    SourceSystem,
)


class ReconciliationEngine:
    """Three-tier reconciliation with an explicit safe-abstention boundary."""

    def reconcile(self, evidence: Iterable[EvidenceRecord]) -> list[ReconciliationDecision]:
        records = list(evidence)
        return [
            *self._orders_to_payments(records),
            *self._settlements_to_bank(records),
        ]

    @staticmethod
    def _orders_to_payments(records: list[EvidenceRecord]) -> list[ReconciliationDecision]:
        orders = [
            record
            for record in records
            if record.source == SourceSystem.MERCHANT
            and record.object_type == ObjectType.ORDER
        ]
        payments_by_order = {
            record.order_id: record
            for record in records
            if record.object_type == ObjectType.PAYMENT and record.order_id
        }
        decisions: list[ReconciliationDecision] = []
        for order in orders:
            payment = payments_by_order.get(order.order_id)
            if payment and payment.amount_paise == order.amount_paise:
                decisions.append(
                    ReconciliationDecision(
                        left_record_ids=[order.record_id],
                        right_record_ids=[payment.record_id],
                        tier=MatchTier.EXACT,
                        status=DecisionStatus.AUTO_APPROVED,
                        confidence=1.0,
                        reasons=["order_id exact", "amount exact", "currency exact"],
                    )
                )
            else:
                decisions.append(
                    ReconciliationDecision(
                        left_record_ids=[order.record_id],
                        right_record_ids=[],
                        tier=MatchTier.UNMATCHED,
                        status=DecisionStatus.ABSTAINED,
                        confidence=0.0,
                        reasons=["no captured payment with equal order_id and amount"],
                    )
                )
        return decisions

    def _settlements_to_bank(
        self, records: list[EvidenceRecord]
    ) -> list[ReconciliationDecision]:
        settlements = [
            record for record in records if record.object_type == ObjectType.SETTLEMENT
        ]
        banks = [record for record in records if record.object_type == ObjectType.BANK_CREDIT]
        used_bank_ids: set[str] = set()
        decisions: list[ReconciliationDecision] = []

        for settlement in settlements:
            exact = next(
                (
                    bank
                    for bank in banks
                    if bank.record_id not in used_bank_ids
                    and (
                        (
                            settlement.bank_reference
                            and bank.bank_reference == settlement.bank_reference
                        )
                        or (
                            settlement.settlement_id
                            and bank.settlement_id == settlement.settlement_id
                        )
                    )
                ),
                None,
            )
            if exact:
                used_bank_ids.add(exact.record_id)
                amount_equal = settlement.amount_paise == exact.amount_paise
                decisions.append(
                    ReconciliationDecision(
                        left_record_ids=[settlement.record_id],
                        right_record_ids=[exact.record_id],
                        tier=MatchTier.EXACT,
                        status=(
                            DecisionStatus.AUTO_APPROVED
                            if amount_equal
                            else DecisionStatus.NEEDS_REVIEW
                        ),
                        confidence=1.0 if amount_equal else 0.98,
                        reasons=[
                            "bank reference or settlement_id exact",
                            (
                                "amount exact"
                                if amount_equal
                                else (
                                    "amount differs by "
                                    f"{exact.amount_paise - settlement.amount_paise} paise"
                                )
                            ),
                        ],
                    )
                )
                continue

            candidates = [
                self._candidate(settlement, bank)
                for bank in banks
                if bank.record_id not in used_bank_ids
                and self._within_candidate_window(settlement, bank)
            ]
            candidates.sort(key=lambda item: item.confidence, reverse=True)

            if not candidates:
                decisions.append(
                    ReconciliationDecision(
                        left_record_ids=[settlement.record_id],
                        tier=MatchTier.UNMATCHED,
                        status=DecisionStatus.ABSTAINED,
                        confidence=0.0,
                        reasons=["no unused bank credit inside amount/date candidate window"],
                    )
                )
                continue

            best = candidates[0]
            runner_up = candidates[1] if len(candidates) > 1 else None
            ambiguous = runner_up is not None and best.confidence - runner_up.confidence < 0.08
            exact_amount = best.amount_delta_paise == 0
            composite_safe = exact_amount and best.date_delta_days <= 3 and not ambiguous

            below_safe_threshold = best.confidence < 0.80

            if ambiguous or below_safe_threshold:
                status = DecisionStatus.ABSTAINED
                tier = MatchTier.SEMANTIC
                right_ids: list[str] = []
                reasons = [
                    (
                        "top candidates are too close"
                        if ambiguous
                        else "best candidate is below the safe confidence threshold"
                    ),
                    "financial truth requires additional bank evidence",
                ]
            elif composite_safe:
                status = DecisionStatus.AUTO_APPROVED
                tier = MatchTier.COMPOSITE
                right_ids = [best.candidate_id]
                used_bank_ids.add(best.candidate_id)
                reasons = ["amount exact", "date inside T+3", "candidate is unique"]
            else:
                status = DecisionStatus.NEEDS_REVIEW
                tier = MatchTier.SEMANTIC
                right_ids = [best.candidate_id]
                reasons = [
                    "best candidate requires narration or amount interpretation",
                    "semantic evidence cannot auto-approve",
                ]

            decisions.append(
                ReconciliationDecision(
                    left_record_ids=[settlement.record_id],
                    right_record_ids=right_ids,
                    tier=tier,
                    status=status,
                    confidence=best.confidence,
                    reasons=reasons,
                    candidates=candidates[:5],
                )
            )
        return decisions

    @staticmethod
    def _days_between(left: datetime, right: datetime) -> int:
        return abs((right.date() - left.date()).days)

    def _within_candidate_window(
        self, settlement: EvidenceRecord, bank: EvidenceRecord
    ) -> bool:
        days = self._days_between(settlement.occurred_at, bank.occurred_at)
        amount_delta = abs(bank.amount_paise - settlement.amount_paise)
        tolerance = max(100, round(settlement.amount_paise * 0.005))
        return days <= 5 and amount_delta <= tolerance

    def _candidate(
        self, settlement: EvidenceRecord, bank: EvidenceRecord
    ) -> CandidateMatch:
        amount_delta = bank.amount_paise - settlement.amount_paise
        relative_delta = abs(amount_delta) / max(settlement.amount_paise, 1)
        amount_score = max(0.0, 1.0 - relative_delta * 20)
        date_delta = self._days_between(settlement.occurred_at, bank.occurred_at)
        date_score = max(0.0, 1.0 - date_delta / 7)
        expected_tokens = " ".join(
            token
            for token in [settlement.settlement_id, settlement.bank_reference]
            if token
        )
        narration_score = (
            token_set_ratio(expected_tokens, bank.narration or "") / 100
            if expected_tokens
            else 0.0
        )
        confidence = round(
            0.62 * amount_score + 0.25 * date_score + 0.13 * narration_score,
            4,
        )
        reasons = [
            f"amount delta {amount_delta} paise",
            f"date delta {date_delta} days",
            f"narration similarity {narration_score:.2f}",
        ]
        return CandidateMatch(
            candidate_id=bank.record_id,
            confidence=confidence,
            reasons=reasons,
            amount_delta_paise=amount_delta,
            date_delta_days=date_delta,
        )
