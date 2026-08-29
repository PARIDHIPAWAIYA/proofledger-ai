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
