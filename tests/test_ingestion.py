import base64

import pytest
from fastapi.testclient import TestClient
from proofledger.api import get_workspace
from proofledger.config import Settings
from proofledger.domain.ingestion import AmountUnit, IngestionSource
from proofledger.main import app
from proofledger.services.ai import BoundedSchemaMapper
from proofledger.services.ingestion import IngestionError, IngestionService
from proofledger.services.workspace import DemoWorkspace

BANK_CSV = b"""Transaction ID,Value Date,Credit Amount,UTR,Description
bank_001,18/07/2026,1250.50,UTR-1001,Razorpay settlement
bank_002,19/07/2026,999.00,UTR-1002,Razorpay settlement
"""


def _suggested_mapping(preview) -> dict[str, str]:
    return {
        suggestion.canonical_field: suggestion.source_column
        for suggestion in preview.suggestions
        if suggestion.source_column
    }


def test_preview_maps_headers_without_committing_records() -> None:
    service = IngestionService()

    preview = service.preview(
        "../../bank.csv",
        BANK_CSV,
        IngestionSource.BANK_STATEMENT,
    )

    assert preview.filename == "bank.csv"
    assert preview.row_count == 2
    assert preview.file_sha256
    assert preview.sample_rows[0]["Credit Amount"] == "1250.50"
    assert _suggested_mapping(preview)["external_id"] == "Transaction ID"
    assert _suggested_mapping(preview)["amount"] == "Credit Amount"
    assert service.manifests == {}


def test_commit_normalizes_records_and_signs_manifest() -> None:
    service = IngestionService()
    preview = service.preview(
        "bank.csv",
        BANK_CSV,
        IngestionSource.BANK_STATEMENT,
    )

    manifest, records = service.commit(
        preview.upload_id,
        _suggested_mapping(preview),
        AmountUnit.RUPEES,
    )

    assert [record.amount_paise for record in records] == [125050, 99900]
    assert all(record.verify_integrity() for record in records)
    assert manifest.verify_manifest_hash()
    assert manifest.verify_signature()
    assert manifest.record_hashes == {
        record.record_id: record.source_hash for record in records
    }
    assert service.verify(manifest.manifest_id).valid is True
    tampered = service.verify(manifest.manifest_id, simulate_tamper=True)
    assert tampered.valid is False
    assert "record_hashes_match" in tampered.failures


def test_signature_rejects_modified_manifest() -> None:
    service = IngestionService()
    preview = service.preview(
        "bank.csv",
        BANK_CSV,
        IngestionSource.BANK_STATEMENT,
    )
    manifest, _ = service.commit(
        preview.upload_id,
        _suggested_mapping(preview),
        AmountUnit.RUPEES,
    )

    changed = manifest.model_copy(update={"row_count": 99})
    invalid_signature = manifest.model_copy(
        update={"signature": base64.b64encode(b"not-a-signature").decode()}
    )

    assert changed.verify_manifest_hash() is False
    assert changed.verify_signature() is False
    assert invalid_signature.verify_signature() is False


def test_invalid_rows_are_rejected_atomically() -> None:
    service = IngestionService()
    content = BANK_CSV.replace(b"999.00", b"not-money")
    preview = service.preview(
        "bank.csv",
        content,
        IngestionSource.BANK_STATEMENT,
    )

    with pytest.raises(IngestionError, match="no records were committed") as raised:
        service.commit(
            preview.upload_id,
            _suggested_mapping(preview),
            AmountUnit.RUPEES,
        )

    assert "row 3" in raised.value.errors[0]
    assert service.manifests == {}
    assert service.records_by_manifest == {}


def test_upload_boundaries_and_ledger_side_normalization() -> None:
    service = IngestionService()
    with pytest.raises(IngestionError, match="NUL"):
        service.preview(
            "attack.csv",
            b"id,amount\x00\n1,2",
            IngestionSource.BANK_STATEMENT,
        )
    with pytest.raises(IngestionError, match="duplicate"):
        service.preview(
            "duplicate.csv",
            b"id,id,date,amount\n1,2,2026-01-01,3",
            IngestionSource.BANK_STATEMENT,
        )

    ledger = b"entry id,amount,date,account code,side\nj_1,20,2026-07-01,bank,credit\n"
    preview = service.preview(
        "ledger.csv",
        ledger,
        IngestionSource.GENERAL_LEDGER,
    )
    _, records = service.commit(
        preview.upload_id,
        _suggested_mapping(preview),
        AmountUnit.RUPEES,
    )
    assert records[0].attributes["side"] == "credit"


def test_bounded_ai_mapper_has_safe_deterministic_fallback() -> None:
    response = BoundedSchemaMapper(Settings(gemini_api_key=None)).suggest(
        source_type="bank_statement",
        headers=["Txn Id", "Credit"],
        target_fields=["external_id", "amount"],
        deterministic_mapping={"external_id": "Txn Id", "amount": "Credit"},
    )

    assert response.generated_by == "deterministic-fallback"
    assert response.mapping == {"external_id": "Txn Id", "amount": "Credit"}
    assert "controller" in response.warning.lower()


def test_ingestion_api_preview_commit_and_verify() -> None:
    workspace = DemoWorkspace(seed=13, order_count=60, settlement_size=20)
    app.dependency_overrides[get_workspace] = lambda: workspace
    client = TestClient(app)
    try:
        preview_response = client.post(
            "/api/v1/ingestion/preview?source_type=bank_statement",
            files={"file": ("bank.csv", BANK_CSV, "text/csv")},
        )
        assert preview_response.status_code == 200
        preview = preview_response.json()
        mapping = {
            item["canonical_field"]: item["source_column"]
            for item in preview["suggestions"]
            if item["source_column"]
        }

        ai_mapping = client.post(
            f"/api/v1/ingestion/{preview['upload_id']}/ai-map"
        )
        assert ai_mapping.status_code == 200
        assert ai_mapping.json()["generated_by"] == "deterministic-fallback"

        committed = client.post(
            "/api/v1/ingestion/commit",
            json={
                "upload_id": preview["upload_id"],
                "field_mapping": mapping,
                "amount_unit": "rupees",
            },
        )
        assert committed.status_code == 200
        manifest = committed.json()["manifest"]
        assert manifest["record_count"] == 2
        assert len(client.get("/api/v1/ingestion/manifests").json()) == 1

        verified = client.post(
            f"/api/v1/ingestion/manifests/{manifest['manifest_id']}/verify",
            json={"simulate_tamper": False},
        )
        tampered = client.post(
            f"/api/v1/ingestion/manifests/{manifest['manifest_id']}/verify",
            json={"simulate_tamper": True},
        )
        assert verified.json()["valid"] is True
        assert tampered.json()["valid"] is False
    finally:
        app.dependency_overrides.pop(get_workspace, None)
