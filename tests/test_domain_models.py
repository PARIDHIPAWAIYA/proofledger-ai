from datetime import datetime, timezone

import pytest
from proofledger.domain.models import (
    DecisionStatus,
    EvidenceRecord,
    JournalLine,
    JournalProposal,
    JournalSide,
    MatchTier,
    ObjectType,
    ReconciliationDecision,
    SourceSystem,
    rupees_to_paise,
)


def test_rupees_are_converted_without_float_drift() -> None:
    assert rupees_to_paise("10.235") == 1024
    assert rupees_to_paise(0.1) == 10


def test_evidence_hash_is_populated_and_verifiable() -> None:
    record = EvidenceRecord(
        record_id="record_1",
        source=SourceSystem.BANK,
        object_type=ObjectType.BANK_CREDIT,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        amount_paise=10_000,
        external_id="line_1",
        status="credited",
    )

    assert len(record.source_hash) == 64
    assert record.verify_integrity()


def test_semantic_decision_cannot_auto_approve() -> None:
    with pytest.raises(ValueError, match="semantic matches"):
        ReconciliationDecision(
            left_record_ids=["left"],
            right_record_ids=["right"],
            tier=MatchTier.SEMANTIC,
            status=DecisionStatus.AUTO_APPROVED,
            confidence=0.99,
        )


def test_journal_must_balance() -> None:
    with pytest.raises(ValueError, match="unbalanced"):
        JournalProposal(
            settlement_id="setl_1",
            lines=[
                JournalLine(
                    account_code="1100",
                    account_name="Bank",
                    side=JournalSide.DEBIT,
                    amount_paise=10_000,
                    evidence_ids=["bank_1"],
                    memo="Settlement receipt",
                ),
                JournalLine(
                    account_code="1200",
                    account_name="Razorpay clearing",
                    side=JournalSide.CREDIT,
                    amount_paise=9_900,
                    evidence_ids=["setl_1"],
                    memo="Clear receivable",
                ),
            ],
        )
