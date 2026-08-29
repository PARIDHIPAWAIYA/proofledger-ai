import pytest
from proofledger.domain.calibration import SplitConformalCalibrator
from proofledger.domain.controls import FinanceControlEngine
from proofledger.domain.models import (
    DecisionStatus,
    ObjectType,
)
from proofledger.domain.reconciliation import ReconciliationEngine
from proofledger.domain.review import MinimumEvidenceReviewPlanner
from proofledger.services.benchmark import ReconciliationBenchmark
from proofledger.services.closing import (
    CloseBlockedError,
    JournalProposalService,
    SettlementCertificateService,
)
from proofledger.services.synthetic import SyntheticFinanceGenerator


def _dataset():
    return SyntheticFinanceGenerator(seed=11).generate(
        order_count=120,
        settlement_size=20,
    )


def test_split_conformal_profile_and_candidate_filter() -> None:
    calibrator = SplitConformalCalibrator()
    profile = calibrator.fit([0.99, 0.96, 0.94, 0.91, 0.88], alpha=0.2)

    assert 0 <= profile.minimum_confidence <= 1
    assert profile.empirical_coverage >= 0.8
    assert profile.assumptions


def test_review_planner_prioritizes_minimum_evidence_questions() -> None:
    dataset = _dataset()
    decisions = ReconciliationEngine().reconcile(dataset.records)
    questions = MinimumEvidenceReviewPlanner().questions(decisions)

    assert questions
    assert all(question.evidence_requested for question in questions)
    assert questions == sorted(
        questions,
        key=lambda question: question.expected_information_gain,
        reverse=True,
    )


def test_journal_proposal_is_balanced_and_requires_review() -> None:
    dataset = _dataset()
    settlement = next(
        record
        for record in dataset.records
        if record.object_type == ObjectType.SETTLEMENT
        and record.settlement_id == "setl_demo_0000"
    )
    proposal = JournalProposalService().propose(settlement, dataset.records)

    assert proposal.debit_paise == proposal.credit_paise
    assert proposal.status == DecisionStatus.NEEDS_REVIEW
    assert all(line.evidence_ids for line in proposal.lines)


def test_certificate_verifies_and_detects_one_rupee_source_change() -> None:
    dataset = _dataset()
    controls = FinanceControlEngine().evaluate(dataset.records)
    settlement = next(
        record
        for record in dataset.records
        if record.object_type == ObjectType.SETTLEMENT
        and record.settlement_id == "setl_demo_0000"
    )
    service = SettlementCertificateService()
    certificate = service.issue(settlement, dataset.records, controls)

    assert service.verify(certificate, dataset.records).valid

    changed_records = [
        (
            record.model_copy(update={"amount_paise": record.amount_paise + 100})
            if record.record_id == settlement.record_id
            else record
        )
        for record in dataset.records
    ]
    verification = service.verify(certificate, changed_records)

    assert not verification.valid
    assert "evidence_hashes_match" in verification.failures


def test_critical_bank_difference_blocks_certificate() -> None:
    dataset = _dataset()
    controls = FinanceControlEngine().evaluate(dataset.records)
    settlement = next(
        record
        for record in dataset.records
        if record.object_type == ObjectType.SETTLEMENT
        and record.settlement_id == "setl_demo_0002"
    )

    with pytest.raises(CloseBlockedError, match="CTRL-05"):
        SettlementCertificateService().issue(
            settlement,
            dataset.records,
            controls,
        )


def test_benchmark_reports_safety_and_accuracy_separately() -> None:
    dataset = _dataset()
    decisions = ReconciliationEngine().reconcile(dataset.records)
    report = ReconciliationBenchmark().evaluate(
        dataset.records,
        dataset.true_links,
        decisions,
    )

    assert report.proofledger.incorrect_auto_approvals == 0
    assert report.proofledger.review_rate > 0
    assert report.fuzzy.incorrect_auto_approvals > 0
    assert report.caveats
