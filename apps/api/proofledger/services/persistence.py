from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Engine

from proofledger.domain.ingestion import IngestionActivation, IngestionManifest
from proofledger.domain.models import EvidenceRecord

metadata = MetaData()

ingestion_manifests = Table(
    "ingestion_manifests",
    metadata,
    Column("manifest_id", String(80), primary_key=True),
    Column("imported_at", DateTime(timezone=True), nullable=False, index=True),
    Column("payload", Text, nullable=False),
)

ingestion_records = Table(
    "ingestion_records",
    metadata,
    Column(
        "manifest_id",
        String(80),
        ForeignKey("ingestion_manifests.manifest_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("record_id", String(240), primary_key=True),
    Column("payload", Text, nullable=False),
)

ingestion_activations = Table(
    "ingestion_activations",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("activation_id", String(80), nullable=False, unique=True),
    Column(
        "manifest_id",
        String(80),
        ForeignKey("ingestion_manifests.manifest_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)


class SQLAlchemyIngestionRepository:
    """Durable append-only storage for signed imports and activation authority."""

    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        metadata.create_all(self.engine)

    def save_import(
        self,
        manifest: IngestionManifest,
        records: Iterable[EvidenceRecord],
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(ingestion_manifests).values(
                    manifest_id=manifest.manifest_id,
                    imported_at=manifest.imported_at,
                    payload=manifest.model_dump_json(),
                )
            )
            connection.execute(
                insert(ingestion_records),
                [
                    {
                        "manifest_id": manifest.manifest_id,
                        "record_id": record.record_id,
                        "payload": record.model_dump_json(),
                    }
                    for record in records
                ],
            )

    def load_imports(self) -> list[tuple[IngestionManifest, list[EvidenceRecord]]]:
        with self.engine.connect() as connection:
            manifest_payloads = connection.execute(
                select(ingestion_manifests.c.payload).order_by(
                    ingestion_manifests.c.imported_at,
                    ingestion_manifests.c.manifest_id,
                )
            ).scalars()
            manifests = [
                IngestionManifest.model_validate_json(payload)
                for payload in manifest_payloads
            ]
            records = connection.execute(
                select(
                    ingestion_records.c.manifest_id,
                    ingestion_records.c.payload,
                ).order_by(
                    ingestion_records.c.manifest_id,
                    ingestion_records.c.record_id,
                )
            )
        records_by_manifest: dict[str, list[EvidenceRecord]] = {
            manifest.manifest_id: [] for manifest in manifests
        }
        for manifest_id, payload in records:
            records_by_manifest[manifest_id].append(
                EvidenceRecord.model_validate_json(payload)
            )
        return [
            (manifest, records_by_manifest[manifest.manifest_id])
            for manifest in manifests
        ]

    def save_activation(self, activation: IngestionActivation) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(ingestion_activations).values(
                    activation_id=activation.activation_id,
                    manifest_id=activation.manifest_id,
                    created_at=activation.created_at,
                    payload=activation.model_dump_json(),
                )
            )

    def load_activations(self) -> list[IngestionActivation]:
        with self.engine.connect() as connection:
            payloads = connection.execute(
                select(ingestion_activations.c.payload).order_by(
                    ingestion_activations.c.sequence
                )
            ).scalars()
            return [
                IngestionActivation.model_validate_json(payload)
                for payload in payloads
            ]

    def health(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1
