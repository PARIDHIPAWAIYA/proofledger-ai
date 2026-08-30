from datetime import timedelta

import pytest
from proofledger.services.closing import SettlementCertificateService
from proofledger.services.workspace import DemoWorkspace


def _workspace() -> DemoWorkspace:
    return DemoWorkspace(seed=11, order_count=120, settlement_size=20)


def _question_for(workspace: DemoWorkspace, settlement_record_id: str):
    decisions = {
        decision.decision_id: decision for decision in workspace.decisions
    }
    return next(
        question
        for question in workspace.questions
        if decisions[question.decision_id].left_record_ids == [settlement_record_id]
    )


def test_review_and_decision_ids_are_stable_across_recomputation() -> None:
    workspace = _workspace()

    first_decisions = [decision.decision_id for decision in workspace.decisions]
    second_decisions = [decision.decision_id for decision in workspace.decisions]
    first_questions = [question.question_id for question in workspace.questions]
    second_questions = [question.question_id for question in workspace.questions]

    assert first_decisions == second_decisions
    assert first_questions == second_questions


def test_new_bank_statement_evidence_recomputes_and_unblocks_close() -> None:
    workspace = _workspace()
    settlement = workspace.settlement("setl_demo_0001")
    assert settlement is not None
    question = _question_for(workspace, settlement.record_id)
    original_records = workspace.dataset.model_dump(mode="json")["records"]

    outcome = workspace.resolve_review(
        question.question_id,
        candidate_id=None,
        bank_reference=settlement.bank_reference or "",
        amount_paise=settlement.amount_paise,
        occurred_at=settlement.occurred_at + timedelta(days=1),
        external_id="uploaded_bank_line_0001",
        evidence_sha256="a" * 64,
        actor="controller@demo",
        rationale="Verified against the attached July bank statement.",
    )

    assert outcome["audit_verified"] is True
    assert outcome["queue_after"] == outcome["queue_before"] - 1
    assert outcome["settlement"]["status"] == "ready"
    assert outcome["remaining_blockers"] == []
    assert outcome["affected_settlements"] == [
        {
            "settlement_id": "setl_demo_0001",
            "before_status": "blocked",
            "after_status": "ready",
            "before_decision": "abstained",
            "after_decision": "auto_approved",
        }
    ]
    assert workspace.dataset.model_dump(mode="json")["records"] == original_records

    resolution = outcome["resolution"]
    evidence = workspace.records_by_id[f"review_bank_{resolution.resolution_id}"]
    assert evidence.verify_integrity()
    assert evidence.attributes["attachment_sha256"] == "a" * 64
    assert SettlementCertificateService().issue(
        settlement,
        workspace.effective_records,
        workspace.controls,
    ).verify()


def test_review_cannot_mask_existing_amount_mismatch_with_duplicate_row() -> None:
    workspace = _workspace()
    settlement = workspace.settlement("setl_demo_0002")
    assert settlement is not None
    question = _question_for(workspace, settlement.record_id)

    with pytest.raises(ValueError, match="exact bank row already exists"):
        workspace.resolve_review(
            question.question_id,
            candidate_id=None,
            bank_reference=settlement.bank_reference or "",
            amount_paise=settlement.amount_paise,
            occurred_at=settlement.occurred_at + timedelta(days=1),
            external_id="duplicate_fix_attempt",
            evidence_sha256="b" * 64,
            actor="controller@demo",
            rationale="Attempt to hide the one rupee difference.",
        )

    assert workspace.settlement_summary(settlement)["status"] == "blocked"
    assert not workspace.review_resolutions
