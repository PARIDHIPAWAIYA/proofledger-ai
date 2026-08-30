from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from enum import Enum

from cryptography.exceptions import InvalidSignature
from pydantic import BaseModel, Field

from proofledger.domain.models import stable_hash


class IngestionSource(str, Enum):
    RAZORPAY_SETTLEMENTS = "razorpay_settlements"
    BANK_STATEMENT = "bank_statement"
    GENERAL_LEDGER = "general_ledger"


class AmountUnit(str, Enum):
    RUPEES = "rupees"
    PAISE = "paise"


class MappingSuggestion(BaseModel):
    canonical_field: str
    source_column: str | None = None
    confidence: float = Field(ge=0, le=1)
    method: str
    required: bool


class IngestionPreview(BaseModel):
    upload_id: str
    source_type: IngestionSource
    filename: str
    file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(gt=0)
    row_count: int = Field(gt=0)
    headers: list[str] = Field(min_length=1)
    sample_rows: list[dict[str, str]]
    suggestions: list[MappingSuggestion]
    required_fields: list[str]
    warnings: list[str]
    expires_at: datetime


class IngestionManifest(BaseModel):
    manifest_id: str
    upload_id: str
    source_type: IngestionSource
    filename: str
    file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(gt=0)
    row_count: int = Field(gt=0)
    record_count: int = Field(gt=0)
    field_mapping: dict[str, str]
    amount_unit: AmountUnit
    record_hashes: dict[str, str]
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature_algorithm: str = "Ed25519"
    signing_public_key: str
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    signature: str

    def unsigned_payload(self) -> dict:
        return self.model_dump(
            exclude={"manifest_hash", "signature"},
            mode="json",
        )

    def verify_manifest_hash(self) -> bool:
        return self.manifest_hash == stable_hash(self.unsigned_payload())

    def verify_signature(self) -> bool:
        if not self.verify_manifest_hash() or self.signature_algorithm != "Ed25519":
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(self.signing_public_key, validate=True)
            )
            public_key.verify(
                base64.b64decode(self.signature, validate=True),
                self.manifest_hash.encode("ascii"),
            )
            return True
        except (binascii.Error, InvalidSignature, TypeError, ValueError):
            return False


class IngestionVerification(BaseModel):
    valid: bool
    checks: dict[str, bool]
    failures: list[str]
