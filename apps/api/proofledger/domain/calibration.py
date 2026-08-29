from __future__ import annotations

import math

from pydantic import BaseModel, Field

from proofledger.domain.models import CandidateMatch, ReconciliationDecision


class CalibrationProfile(BaseModel):
    alpha: float = Field(gt=0, lt=1)
    sample_size: int = Field(gt=0)
    minimum_confidence: float = Field(ge=0, le=1)
    empirical_coverage: float = Field(ge=0, le=1)
    assumptions: list[str]


class SplitConformalCalibrator:
    """Calibrate candidate-set inclusion from held-out true-match confidence scores."""

    def fit(
        self,
        true_match_confidences: list[float],
        alpha: float = 0.10,
    ) -> CalibrationProfile:
        if not true_match_confidences:
            raise ValueError("at least one held-out true-match confidence is required")
        if not 0 < alpha < 1:
            raise ValueError("alpha must be between zero and one")
        if any(not 0 <= score <= 1 for score in true_match_confidences):
            raise ValueError("confidence scores must be between zero and one")

        nonconformity = sorted(1.0 - score for score in true_match_confidences)
        quantile_rank = math.ceil((len(nonconformity) + 1) * (1 - alpha))
        quantile_index = min(quantile_rank, len(nonconformity)) - 1
        threshold = round(1.0 - nonconformity[quantile_index], 4)
        empirical_coverage = sum(
            score >= threshold for score in true_match_confidences
        ) / len(true_match_confidences)
        return CalibrationProfile(
            alpha=alpha,
            sample_size=len(true_match_confidences),
            minimum_confidence=threshold,
            empirical_coverage=round(empirical_coverage, 4),
            assumptions=[
                "Calibration and future examples are exchangeable.",
                "The candidate generator can surface the true match.",
                "Coverage is a dataset-level claim, not certainty for one transaction.",
            ],
        )

    @staticmethod
    def candidate_set(
        decision: ReconciliationDecision,
        profile: CalibrationProfile,
    ) -> list[CandidateMatch]:
        return [
            candidate
            for candidate in decision.candidates
            if candidate.confidence >= profile.minimum_confidence
        ]
