from pathlib import Path

from proofledger.domain.ingestion import AmountUnit, IngestionSource
from proofledger.services.persistence import SQLAlchemyIngestionRepository
from proofledger.services.workspace import DemoWorkspace


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _mapping(preview) -> dict[str, str]:
    return {
        suggestion.canonical_field: suggestion.source_column
        for suggestion in preview.suggestions
        if suggestion.source_column
    }


def test_signed_import_and_activation_survive_workspace_restart(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "proofledger-test.db")
    first_repository = SQLAlchemyIngestionRepository(database_url)
    first = DemoWorkspace(
        seed=11,
        order_count=120,
        settlement_size=20,
        repository=first_repository,
    )
    demo = first.demo_bank_statement()
    preview = first.ingestion.preview(
        demo["filename"],
        demo["content"].encode(),
        IngestionSource.BANK_STATEMENT,
    )
    manifest, imported = first.ingestion.commit(
        preview.upload_id,
        _mapping(preview),
        AmountUnit.RUPEES,
    )
    first.activate_manifest(
        manifest.manifest_id,
        actor="controller@demo",
        rationale="Persist the approved bank source across process restarts.",
    )
    assert first_repository.health()

    second = DemoWorkspace(
        seed=11,
        order_count=120,
        settlement_size=20,
        repository=SQLAlchemyIngestionRepository(database_url),
    )

    assert list(second.ingestion.manifests) == [manifest.manifest_id]
    assert second.ingestion.verify(manifest.manifest_id).valid is True
    assert second.active_manifest_ids == {manifest.manifest_id}
    assert imported[0].record_id in second.records_by_id
    settlement = second.settlement(demo["settlement_id"])
    assert settlement is not None
    assert second.settlement_summary(settlement)["status"] == "ready"
    assert second.ingestion_activations[0].verify_integrity()

    second.deactivate_manifest(
        manifest.manifest_id,
        actor="controller@demo",
        rationale="Persist a governed source removal across another restart.",
    )
    third = DemoWorkspace(
        seed=11,
        order_count=120,
        settlement_size=20,
        repository=SQLAlchemyIngestionRepository(database_url),
    )

    assert third.active_manifest_ids == set()
    assert len(third.ingestion_activations) == 2
    assert all(event.verify_integrity() for event in third.ingestion_activations)
    settlement = third.settlement(demo["settlement_id"])
    assert settlement is not None
    assert third.settlement_summary(settlement)["status"] == "blocked"
    assert imported[0].record_id not in third.records_by_id


def test_import_commit_is_visible_to_a_new_repository_instance(tmp_path: Path) -> None:
    database_url = _database_url(tmp_path / "atomic-import.db")
    first = DemoWorkspace(
        seed=19,
        order_count=60,
        settlement_size=20,
        repository=SQLAlchemyIngestionRepository(database_url),
    )
    demo = first.demo_bank_statement()
    preview = first.ingestion.preview(
        demo["filename"],
        demo["content"].encode(),
        IngestionSource.BANK_STATEMENT,
    )
    manifest, records = first.ingestion.commit(
        preview.upload_id,
        _mapping(preview),
        AmountUnit.RUPEES,
    )

    imports = SQLAlchemyIngestionRepository(database_url).load_imports()

    assert len(imports) == 1
    loaded_manifest, loaded_records = imports[0]
    assert loaded_manifest == manifest
    assert loaded_records == records
    assert loaded_manifest.verify_signature()
    assert all(record.verify_integrity() for record in loaded_records)
