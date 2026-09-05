from datetime import timedelta

import pytest
from proofledger.services.closing import SettlementCertificateService
from proofledger.services.workspace import DemoWorkspace


def test_derived_views_are_cached_until_the_evidence_changes() -> None:
    workspace = DemoWorkspace(seed=11, order_count=120, settlement_size=20)

    # Repeated reads of an unchanged workspace reuse one computation.
    assert workspace.controls is workspace.controls
    assert workspace.decisions is workspace.decisions
    assert workspace.graph is workspace.graph
    assert workspace.effective_records is workspace.effective_records

    controls_before = workspace.controls
    blocked = workspace.settlement("setl_demo_0001")
    assert blocked is not None
    assert workspace.settlement_summary(blocked)["status"] == "blocked"

    decision = next(
        item
        for item in workspace.decisions
        if blocked.record_id in item.left_record_ids
    )
    question = next(
        item for item in workspace.questions if item.decision_id == decision.decision_id
    )
    workspace.resolve_review(
        question.question_id,
        candidate_id=None,
        bank_reference=blocked.bank_reference,
        amount_paise=blocked.amount_paise,
        occurred_at=blocked.occurred_at,
        external_id="cache_invalidation_bank_row",
        evidence_sha256="d" * 64,
        actor="controller@demo",
        rationale="Attaching the missing statement row to test recomputation.",
    )

    # A controller action must invalidate every derived view, not serve a stale one.
    assert workspace.controls is not controls_before
    resolved = workspace.settlement("setl_demo_0001")
    assert resolved is not None
    assert workspace.settlement_summary(resolved)["status"] == "ready"


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
