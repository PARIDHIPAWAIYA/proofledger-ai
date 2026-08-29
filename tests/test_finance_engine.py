from collections import Counter

from proofledger.domain.controls import FinanceControlEngine
from proofledger.domain.graph import FinancialLifecycleGraph
from proofledger.domain.models import ControlStatus, DecisionStatus, MatchTier
from proofledger.domain.reconciliation import ReconciliationEngine
from proofledger.services.synthetic import SyntheticFinanceGenerator


def test_generator_is_deterministic_and_large_enough() -> None:
    first = SyntheticFinanceGenerator(seed=7).generate()
    second = SyntheticFinanceGenerator(seed=7).generate()

    assert len(first.records) > 1_200
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert all(record.verify_integrity() for record in first.records)


def test_object_centric_graph_connects_order_to_settlement() -> None:
    dataset = SyntheticFinanceGenerator(seed=7).generate(order_count=40, settlement_size=20)
    graph = FinancialLifecycleGraph.from_records(dataset.records)

    path = graph.evidence_path(
        "order:order_demo_00000",
        "settlement:setl_demo_0000",
    )

    assert path
    assert graph.summary().object_count > 40
    assert graph.summary().event_count == len(dataset.records)


def test_controls_expose_seeded_anomalies() -> None:
    dataset = SyntheticFinanceGenerator(seed=7).generate(order_count=120, settlement_size=20)
    results = FinanceControlEngine().evaluate(dataset.records)
    failures = [result for result in results if result.status == ControlStatus.FAIL]
    failed_control_ids = Counter(result.control_id for result in failures)

    assert failed_control_ids["CTRL-04"] >= 1
    assert failed_control_ids["CTRL-05"] >= 1
    assert failed_control_ids["CTRL-06"] == 1
    assert failed_control_ids["CTRL-07"] >= 1


def test_reconciliation_never_auto_approves_semantic_match() -> None:
    dataset = SyntheticFinanceGenerator(seed=7).generate(order_count=120, settlement_size=20)
    decisions = ReconciliationEngine().reconcile(dataset.records)

    assert any(decision.status == DecisionStatus.ABSTAINED for decision in decisions)
    assert any(decision.tier == MatchTier.COMPOSITE for decision in decisions)
    assert all(
        not (
            decision.tier == MatchTier.SEMANTIC
            and decision.status == DecisionStatus.AUTO_APPROVED
        )
        for decision in decisions
    )
