from fastapi.testclient import TestClient
from proofledger.api import get_workspace
from proofledger.main import app
from proofledger.services.workspace import DemoWorkspace

_TEST_WORKSPACE = DemoWorkspace(seed=11, order_count=120, settlement_size=20)


def _small_workspace() -> DemoWorkspace:
    return _TEST_WORKSPACE


app.dependency_overrides[get_workspace] = _small_workspace
client = TestClient(app)


def test_health_and_overview() -> None:
    assert client.get("/health").json()["status"] == "ok"

    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_records"] > 240
    assert payload["failed_controls"] > 0
    assert payload["graph"]["objects"] > 0


def test_settlement_drilldown_contains_proof_layers() -> None:
    response = client.get("/api/v1/settlements/setl_demo_0000")

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"]
    assert payload["controls"]
    assert payload["decision"]["tier"] == "exact"
    journal = payload["journal_proposal"]
    assert journal["debit_paise"] == journal["credit_paise"]


def test_graph_and_benchmark_endpoints() -> None:
    graph = client.get("/api/v1/graph/setl_demo_0000").json()
    benchmark = client.get("/api/v1/benchmark").json()

    assert graph["nodes"] and graph["edges"]
    assert benchmark["proofledger"]["incorrect_auto_approvals"] == 0
    assert benchmark["fuzzy"]["incorrect_auto_approvals"] > 0


def test_calibration_endpoint_splits_labels_and_sizes_candidate_sets() -> None:
    response = client.get("/api/v1/calibration")

    assert response.status_code == 200
    payload = response.json()
    profile = payload["profile"]
    assert profile["alpha"] == 0.10
    assert profile["sample_size"] == payload["calibration_size"]
    assert payload["holdout_size"] > 0
    assert 0 <= payload["holdout_coverage"] <= 1
    assert 0 <= profile["minimum_confidence"] <= 1
    assert payload["caveats"]
    for entry in payload["candidate_sets"]:
        assert entry["candidates_generated"] >= len(entry["candidate_set"])


def test_calibration_rejects_an_invalid_error_level() -> None:
    assert client.get("/api/v1/calibration?alpha=0").status_code == 422
    assert client.get("/api/v1/calibration?alpha=1").status_code == 422


def test_certificate_issue_block_and_tamper_simulation() -> None:
    issued = client.post("/api/v1/settlements/setl_demo_0000/certificate")
    blocked = client.post("/api/v1/settlements/setl_demo_0002/certificate")

    assert issued.status_code == 200
    assert blocked.status_code == 409

    certificate_id = issued.json()["certificate_id"]
    valid = client.post(
        f"/api/v1/certificates/{certificate_id}/verify",
        json={"simulate_tamper": False},
    )
    tampered = client.post(
        f"/api/v1/certificates/{certificate_id}/verify",
        json={"simulate_tamper": True},
    )

    assert valid.json()["valid"] is True
    assert tampered.json()["valid"] is False
    assert "evidence_hashes_match" in tampered.json()["failures"]


def test_review_resolution_endpoint_records_audit_and_updates_detail() -> None:
    workspace = DemoWorkspace(seed=11, order_count=120, settlement_size=20)
    settlement = workspace.settlement("setl_demo_0001")
    assert settlement is not None
    app.dependency_overrides[get_workspace] = lambda: workspace
    isolated_client = TestClient(app)
    try:
        reviews = isolated_client.get("/api/v1/reviews").json()
        review = next(
            item
            for item in reviews
            if item["settlement"]["settlement_id"] == "setl_demo_0001"
        )
        response = isolated_client.post(
            f"/api/v1/reviews/{review['question']['question_id']}/resolve",
            json={
                "candidate_id": None,
                "bank_reference": settlement.bank_reference,
                "amount_paise": settlement.amount_paise,
                "occurred_at": settlement.occurred_at.isoformat(),
                "external_id": "api_uploaded_bank_line_0001",
                "evidence_sha256": "c" * 64,
                "actor": "controller@demo",
                "rationale": "Verified against the API test bank statement.",
            },
        )

        assert response.status_code == 200
        assert response.json()["audit_verified"] is True
        assert response.json()["settlement"]["status"] == "ready"
        history = isolated_client.get("/api/v1/reviews/history").json()
        assert len(history) == 1
        assert history[0]["evidence_sha256"] == "c" * 64
        detail = isolated_client.get(
            "/api/v1/settlements/setl_demo_0001"
        ).json()
        assert detail["summary"]["status"] == "ready"
    finally:
        app.dependency_overrides[get_workspace] = _small_workspace
