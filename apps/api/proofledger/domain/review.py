from __future__ import annotations

import math

from proofledger.domain.models import (
    DecisionStatus,
    ReconciliationDecision,
    ReviewQuestion,
    stable_hash,
)


class MinimumEvidenceReviewPlanner:
    """Ask for the smallest piece of evidence that separates plausible candidates."""

    def questions(
        self, decisions: list[ReconciliationDecision]
    ) -> list[ReviewQuestion]:
        reviewable = [
            decision
            for decision in decisions
            if decision.status in {DecisionStatus.ABSTAINED, DecisionStatus.NEEDS_REVIEW}
        ]
        questions = [self._question(decision) for decision in reviewable]
        return sorted(
            questions,
            key=lambda question: question.expected_information_gain,
            reverse=True,
        )

    def _question(self, decision: ReconciliationDecision) -> ReviewQuestion:
        confidences = [candidate.confidence for candidate in decision.candidates]
        entropy = self._normalized_entropy(confidences)
        candidate_ids = [candidate.candidate_id for candidate in decision.candidates]
        settlement_record = decision.left_record_ids[0]
        if len(candidate_ids) > 1:
            prompt = (
                f"Provide the bank UTR for {settlement_record}. "
                f"It will distinguish {len(candidate_ids)} plausible credits."
            )
            evidence_requested = "bank UTR/reference"
        elif candidate_ids:
            prompt = (
                f"Confirm the bank UTR or attach the statement row for {settlement_record}."
            )
            evidence_requested = "bank statement row"
        else:
            prompt = (
                f"Upload the bank statement covering the payout date for {settlement_record}."
            )
            evidence_requested = "bank statement date range"

        question_fingerprint = stable_hash(
            {
                "decision_id": decision.decision_id,
                "evidence_requested": evidence_requested,
            }
        )
        return ReviewQuestion(
            question_id=f"q_{question_fingerprint[:12]}",
            decision_id=decision.decision_id,
            prompt=prompt,
            evidence_requested=evidence_requested,
            expected_information_gain=round(max(0.1, entropy), 4),
            candidate_ids=candidate_ids,
        )

    @staticmethod
    def _normalized_entropy(confidences: list[float]) -> float:
        if len(confidences) <= 1:
            return 0.25 if confidences else 0.1
        total = sum(confidences)
        probabilities = (
            [confidence / total for confidence in confidences]
            if total
            else [1 / len(confidences)] * len(confidences)
        )
        entropy = -sum(
            probability * math.log2(probability)
            for probability in probabilities
            if probability > 0
        )
        return entropy / math.log2(len(probabilities))
