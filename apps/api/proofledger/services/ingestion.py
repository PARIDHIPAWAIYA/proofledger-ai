from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rapidfuzz.fuzz import WRatio

from proofledger.domain.ingestion import (
    AmountUnit,
    IngestionManifest,
    IngestionPreview,
    IngestionSource,
    IngestionVerification,
    MappingSuggestion,
)
from proofledger.domain.models import (
    EvidenceRecord,
    ObjectType,
    SourceSystem,
    rupees_to_paise,
    stable_hash,
)
from proofledger.services.persistence import SQLAlchemyIngestionRepository

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 60
MAX_CELL_CHARACTERS = 5_000


@dataclass(frozen=True)
class FieldSpec:
    name: str
    aliases: tuple[str, ...]
    required: bool = False


SCHEMAS: dict[IngestionSource, tuple[FieldSpec, ...]] = {
    IngestionSource.MERCHANT_ORDERS: (
        FieldSpec("order_id", ("order id", "orderid", "order reference", "id"), True),
        FieldSpec("amount", ("amount", "order amount", "order value", "total"), True),
        FieldSpec("occurred_at", ("created at", "order date", "date", "timestamp"), True),
        FieldSpec("currency", ("currency", "currency code")),
        FieldSpec("status", ("status", "order status")),
        FieldSpec("customer_key", ("customer", "customer id", "customer key", "buyer")),
    ),
    IngestionSource.RAZORPAY_SETTLEMENTS: (
        FieldSpec("settlement_id", ("settlement id", "settlementid", "id"), True),
        FieldSpec("amount", ("amount", "net amount", "settled amount", "credit"), True),
        FieldSpec("occurred_at", ("created at", "settled at", "date", "timestamp"), True),
        FieldSpec("bank_reference", ("utr", "bank utr", "bank reference", "bank ref")),
        FieldSpec("currency", ("currency", "currency code")),
        FieldSpec("status", ("status", "settlement status")),
        FieldSpec("gross", ("gross", "gross amount")),
        FieldSpec("fees", ("fee", "fees", "service fee")),
        FieldSpec("tax", ("tax", "gst", "fee tax")),
        FieldSpec("refunds", ("refund", "refunds", "refund amount")),
    ),
    IngestionSource.REFUND_REGISTER: (
        FieldSpec("refund_id", ("refund id", "refundid", "credit note", "id"), True),
        FieldSpec("amount", ("amount", "refund amount", "credit", "value"), True),
        FieldSpec("occurred_at", ("created at", "refund date", "date", "timestamp"), True),
        FieldSpec("order_id", ("order id", "orderid", "order reference"), True),
        FieldSpec("payment_id", ("payment id", "paymentid", "payment reference"), True),
        FieldSpec("currency", ("currency", "currency code")),
        FieldSpec("status", ("status", "refund status")),
    ),
    IngestionSource.BANK_STATEMENT: (
        FieldSpec("external_id", ("transaction id", "bank line id", "reference", "id"), True),
        FieldSpec("amount", ("amount", "credit", "deposit", "credit amount"), True),
        FieldSpec("occurred_at", ("date", "value date", "transaction date", "timestamp"), True),
        FieldSpec("bank_reference", ("utr", "bank utr", "bank reference", "reference no")),
        FieldSpec("settlement_id", ("settlement id", "payout id", "settlement")),
        FieldSpec("currency", ("currency", "currency code")),
        FieldSpec("narration", ("narration", "description", "remarks", "memo")),
        FieldSpec("status", ("status", "transaction status")),
    ),
    IngestionSource.GENERAL_LEDGER: (
        FieldSpec("external_id", ("journal id", "entry id", "document no", "id"), True),
        FieldSpec("amount", ("amount", "debit", "credit", "local amount"), True),
        FieldSpec("occurred_at", ("posting date", "date", "created at", "timestamp"), True),
        FieldSpec("account_code", ("account", "account code", "gl code", "ledger account"), True),
        FieldSpec("side", ("side", "debit credit", "dr cr", "entry type"), True),
        FieldSpec("settlement_id", ("settlement id", "payout id", "reference")),
        FieldSpec("currency", ("currency", "currency code")),
        FieldSpec("status", ("status", "posting status")),
    ),
}


class IngestionError(ValueError):
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


@dataclass
class StagedUpload:
    preview: IngestionPreview
    rows: list[dict[str, str]]


class ManifestSigner:
    def __init__(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        public_bytes = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_key = base64.b64encode(public_bytes).decode("ascii")

    def sign(self, manifest_hash: str) -> str:
        signature = self.private_key.sign(manifest_hash.encode("ascii"))
        return base64.b64encode(signature).decode("ascii")


class IngestionService:
    """Stage untrusted CSVs, normalize confirmed mappings, and sign the evidence manifest."""

    def __init__(
        self,
        repository: SQLAlchemyIngestionRepository | None = None,
    ) -> None:
        self.staged: dict[str, StagedUpload] = {}
        self.manifests: dict[str, IngestionManifest] = {}
        self.records_by_manifest: dict[str, list[EvidenceRecord]] = {}
        self.signer = ManifestSigner()
        self.repository = repository
        if repository:
            for manifest, records in repository.load_imports():
                actual_hashes = {
                    record.record_id: record.source_hash for record in records
                }
                if (
                    not manifest.verify_signature()
                    or actual_hashes != manifest.record_hashes
                    or not all(record.verify_integrity() for record in records)
                ):
                    raise RuntimeError(
                        f"persisted ingestion manifest {manifest.manifest_id} failed verification"
                    )
                self.manifests[manifest.manifest_id] = manifest
                self.records_by_manifest[manifest.manifest_id] = records

    def preview(
        self,
        filename: str,
        content: bytes,
        source_type: IngestionSource,
    ) -> IngestionPreview:
        safe_name = Path(filename or "upload.csv").name
        if Path(safe_name).suffix.lower() not in {".csv", ".tsv", ".txt"}:
            raise IngestionError("only CSV, TSV, or delimited text files are accepted")
        if not content:
            raise IngestionError("uploaded file is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise IngestionError("uploaded file exceeds the 5 MB demo limit")
        if b"\x00" in content:
            raise IngestionError("binary or NUL-containing files are not accepted")
        try:
            text = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as error:
            raise IngestionError("file must be UTF-8 encoded") from error

        headers, rows = self._parse_delimited(text)
        suggestions = self._suggest_mapping(source_type, headers)
        required_fields = [spec.name for spec in SCHEMAS[source_type] if spec.required]
        missing = [
            item.canonical_field
            for item in suggestions
            if item.required and not item.source_column
        ]
        warnings = []
        if missing:
            warnings.append("Required mappings need confirmation: " + ", ".join(missing))
        low_confidence = [
            item.canonical_field
            for item in suggestions
            if item.source_column and item.confidence < 0.8
        ]
        if low_confidence:
            warnings.append("Review low-confidence mappings: " + ", ".join(low_confidence))
        warnings.append("Only column names may be sent to Gemini; row values stay server-side.")

        upload_id = f"upl_{uuid4().hex[:12]}"
        preview = IngestionPreview(
            upload_id=upload_id,
            source_type=source_type,
            filename=safe_name,
            file_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            row_count=len(rows),
            headers=headers,
            sample_rows=[
                {key: value[:120] for key, value in row.items()}
                for row in rows[:5]
            ],
            suggestions=suggestions,
            required_fields=required_fields,
            warnings=warnings,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        self.staged[upload_id] = StagedUpload(preview=preview, rows=rows)
        return preview

    def mapping_context(self, upload_id: str) -> tuple[IngestionPreview, list[FieldSpec]]:
        stage = self._stage(upload_id)
        return stage.preview, list(SCHEMAS[stage.preview.source_type])

    def commit(
        self,
        upload_id: str,
        field_mapping: dict[str, str],
        amount_unit: AmountUnit,
    ) -> tuple[IngestionManifest, list[EvidenceRecord]]:
        stage = self._stage(upload_id)
        if any(
            manifest.file_sha256 == stage.preview.file_sha256
            and manifest.source_type == stage.preview.source_type
            for manifest in self.manifests.values()
        ):
            raise IngestionError("this source file has already been committed")
        mapping = self._validate_mapping(stage.preview, field_mapping)
        records: list[EvidenceRecord] = []
        errors: list[str] = []
        for index, row in enumerate(stage.rows, start=2):
            try:
                records.append(
                    self._normalize_row(
                        stage.preview,
                        row,
                        mapping,
                        amount_unit,
                        index,
                    )
                )
            except (ValueError, InvalidOperation) as error:
                errors.append(f"row {index}: {error}")
                if len(errors) >= 25:
                    break
        if errors:
            raise IngestionError(
                f"{len(errors)} row validation error(s); no records were committed",
                errors,
            )

        imported_at = datetime.now(timezone.utc)
        manifest_id = f"manifest_{uuid4().hex[:12]}"
        draft = IngestionManifest(
            manifest_id=manifest_id,
            upload_id=upload_id,
            source_type=stage.preview.source_type,
            filename=stage.preview.filename,
            file_sha256=stage.preview.file_sha256,
            size_bytes=stage.preview.size_bytes,
            row_count=stage.preview.row_count,
            record_count=len(records),
            field_mapping=mapping,
            amount_unit=amount_unit,
            record_hashes={record.record_id: record.source_hash for record in records},
            imported_at=imported_at,
            signing_public_key=self.signer.public_key,
            manifest_hash="0" * 64,
            signature="",
        )
        manifest_hash = stable_hash(draft.unsigned_payload())
        manifest = draft.model_copy(
            update={
                "manifest_hash": manifest_hash,
                "signature": self.signer.sign(manifest_hash),
            }
        )
        if not manifest.verify_signature():
            raise RuntimeError("generated ingestion manifest failed signature verification")
        if self.repository:
            self.repository.save_import(manifest, records)
        self.manifests[manifest_id] = manifest
        self.records_by_manifest[manifest_id] = records
        return manifest, records

    def verify(
        self,
        manifest_id: str,
        *,
        simulate_tamper: bool = False,
    ) -> IngestionVerification:
        manifest = self.manifests.get(manifest_id)
        if not manifest:
            raise IngestionError("ingestion manifest not found")
        records = self.records_by_manifest[manifest_id]
        if simulate_tamper:
            target = records[0]
            records = [
                (
                    record.model_copy(update={"amount_paise": record.amount_paise + 100})
                    if record.record_id == target.record_id
                    else record
                )
                for record in records
            ]
        actual_hashes = {record.record_id: record.source_hash for record in records}
        integrity = all(record.verify_integrity() for record in records)
        stage = self.staged.get(manifest.upload_id)
        source_file_hash_bound = manifest.verify_manifest_hash()
        if stage:
            source_file_hash_bound = (
                source_file_hash_bound
                and stage.preview.file_sha256 == manifest.file_sha256
            )
        checks = {
            "manifest_hash_matches": manifest.verify_manifest_hash(),
            "ed25519_signature_valid": manifest.verify_signature(),
            "record_hashes_match": actual_hashes == manifest.record_hashes and integrity,
            "source_file_hash_bound": source_file_hash_bound,
        }
        failures = [name for name, passed in checks.items() if not passed]
        return IngestionVerification(valid=not failures, checks=checks, failures=failures)

    def _stage(self, upload_id: str) -> StagedUpload:
        stage = self.staged.get(upload_id)
        if not stage:
            raise IngestionError("staged upload not found")
        if stage.preview.expires_at < datetime.now(timezone.utc):
            self.staged.pop(upload_id, None)
            raise IngestionError("staged upload expired; preview the file again")
        return stage

    @staticmethod
    def _parse_delimited(text: str) -> tuple[list[str], list[dict[str, str]]]:
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text, newline=""), dialect)
        try:
            raw_headers = next(reader)
        except StopIteration as error:
            raise IngestionError("file does not contain a header row") from error
        headers = [header.strip() for header in raw_headers]
        if not headers or any(not header for header in headers):
            raise IngestionError("every column must have a non-empty header")
        if len(headers) > MAX_COLUMNS:
            raise IngestionError(f"file exceeds the {MAX_COLUMNS}-column demo limit")
        if len(set(headers)) != len(headers):
            raise IngestionError("duplicate column headers are not accepted")

        rows: list[dict[str, str]] = []
        for raw_row in reader:
            if not raw_row or not any(value.strip() for value in raw_row):
                continue
            if len(raw_row) != len(headers):
                raise IngestionError(
                    f"row {len(rows) + 2} has {len(raw_row)} cells; expected {len(headers)}"
                )
            if any(len(value) > MAX_CELL_CHARACTERS for value in raw_row):
                raise IngestionError(f"row {len(rows) + 2} contains an oversized cell")
            rows.append(dict(zip(headers, (value.strip() for value in raw_row), strict=True)))
            if len(rows) > MAX_ROWS:
                raise IngestionError(f"file exceeds the {MAX_ROWS:,}-row demo limit")
        if not rows:
            raise IngestionError("file contains no data rows")
        return headers, rows

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _suggest_mapping(
        self,
        source_type: IngestionSource,
        headers: list[str],
    ) -> list[MappingSuggestion]:
        normalized_headers = {header: self._normalize_header(header) for header in headers}
        used: set[str] = set()
        suggestions: list[MappingSuggestion] = []
        specs = sorted(SCHEMAS[source_type], key=lambda item: not item.required)
        for spec in specs:
            canonical = self._normalize_header(spec.name)
            aliases = {self._normalize_header(alias) for alias in spec.aliases}
            ranked: list[tuple[float, str, str]] = []
            for header, normalized in normalized_headers.items():
                if header in used:
                    continue
                if normalized == canonical:
                    ranked.append((1.0, header, "canonical"))
                elif normalized in aliases:
                    ranked.append((0.97, header, "exact_alias"))
                else:
                    candidates = [
                        WRatio(normalized, canonical),
                        *[WRatio(normalized, alias) for alias in aliases],
                    ]
                    score = max(candidates)
                    if score >= 72:
                        ranked.append((round(score / 100 * 0.9, 4), header, "fuzzy_header"))
            ranked.sort(reverse=True)
            if ranked:
                confidence, source_column, method = ranked[0]
                used.add(source_column)
            else:
                confidence, source_column, method = 0.0, None, "unmapped"
            suggestions.append(
                MappingSuggestion(
                    canonical_field=spec.name,
                    source_column=source_column,
                    confidence=confidence,
                    method=method,
                    required=spec.required,
                )
            )
        return suggestions

    @staticmethod
    def _validate_mapping(
        preview: IngestionPreview,
        mapping: dict[str, str],
    ) -> dict[str, str]:
        specs = {spec.name: spec for spec in SCHEMAS[preview.source_type]}
        unknown = sorted(set(mapping) - set(specs))
        if unknown:
            raise IngestionError("unknown canonical fields: " + ", ".join(unknown))
        cleaned = {key: value for key, value in mapping.items() if value}
        invalid_columns = sorted(set(cleaned.values()) - set(preview.headers))
        if invalid_columns:
            raise IngestionError("unknown source columns: " + ", ".join(invalid_columns))
        if len(set(cleaned.values())) != len(cleaned):
            raise IngestionError("one source column cannot map to multiple canonical fields")
        missing = [
            spec.name
            for spec in specs.values()
            if spec.required and not cleaned.get(spec.name)
        ]
        if missing:
            raise IngestionError("required fields are unmapped: " + ", ".join(missing))
        return dict(sorted(cleaned.items()))

    def _normalize_row(
        self,
        preview: IngestionPreview,
        row: dict[str, str],
        mapping: dict[str, str],
        amount_unit: AmountUnit,
        row_number: int,
    ) -> EvidenceRecord:
        def value(field: str, default: str = "") -> str:
            column = mapping.get(field)
            return row.get(column, "").strip() if column else default

        amount = self._amount(value("amount"), amount_unit)
        occurred_at = self._datetime(value("occurred_at"))
        currency = (value("currency", "INR") or "INR").upper()
        record_id = (
            f"import_{preview.source_type.value}_{preview.file_sha256[:10]}_"
            f"{row_number - 1:06d}"
        )
        if preview.source_type == IngestionSource.MERCHANT_ORDERS:
            order_id = self._identifier(value("order_id"), "order_id")
            customer_key = value("customer_key")
            return EvidenceRecord(
                record_id=record_id,
                source=SourceSystem.MERCHANT,
                object_type=ObjectType.ORDER,
                occurred_at=occurred_at,
                amount_paise=amount,
                currency=currency,
                external_id=order_id,
                order_id=order_id,
                status=value("status", "paid") or "paid",
                attributes=(
                    {"merchant_customer_key": customer_key} if customer_key else {}
                ),
            )
        if preview.source_type == IngestionSource.REFUND_REGISTER:
            refund_id = self._identifier(value("refund_id"), "refund_id")
            return EvidenceRecord(
                record_id=record_id,
                source=SourceSystem.REFUNDS,
                object_type=ObjectType.REFUND,
                occurred_at=occurred_at,
                amount_paise=amount,
                currency=currency,
                external_id=refund_id,
                refund_id=refund_id,
                order_id=self._identifier(value("order_id"), "order_id"),
                payment_id=self._identifier(value("payment_id"), "payment_id"),
                status=value("status", "processed") or "processed",
            )
        if preview.source_type == IngestionSource.RAZORPAY_SETTLEMENTS:
            settlement_id = self._identifier(value("settlement_id"), "settlement_id")
            attributes = {}
            for field in ("gross", "fees", "tax", "refunds"):
                raw = value(field)
                if raw:
                    attributes[f"{field}_paise"] = self._amount(raw, amount_unit)
            return EvidenceRecord(
                record_id=record_id,
                source=SourceSystem.RAZORPAY,
                object_type=ObjectType.SETTLEMENT,
                occurred_at=occurred_at,
                amount_paise=amount,
                currency=currency,
                external_id=settlement_id,
                settlement_id=settlement_id,
                bank_reference=value("bank_reference") or None,
                status=value("status", "processed") or "processed",
                attributes=attributes,
            )
        if preview.source_type == IngestionSource.BANK_STATEMENT:
            external_id = self._identifier(value("external_id"), "external_id")
            return EvidenceRecord(
                record_id=record_id,
                source=SourceSystem.BANK,
                object_type=ObjectType.BANK_CREDIT,
                occurred_at=occurred_at,
                amount_paise=amount,
                currency=currency,
                external_id=external_id,
                settlement_id=value("settlement_id") or None,
                bank_reference=value("bank_reference") or None,
                narration=value("narration") or None,
                status=value("status", "credited") or "credited",
            )
        external_id = self._identifier(value("external_id"), "external_id")
        account_code = self._identifier(value("account_code"), "account_code")
        raw_side = re.sub(r"[^a-z]", "", value("side").lower())
        side = {
            "d": "debit",
            "dr": "debit",
            "debit": "debit",
            "c": "credit",
            "cr": "credit",
            "credit": "credit",
        }.get(raw_side)
        if not side:
            raise ValueError("side must be debit/credit or dr/cr")
        return EvidenceRecord(
            record_id=record_id,
            source=SourceSystem.LEDGER,
            object_type=ObjectType.JOURNAL,
            occurred_at=occurred_at,
            amount_paise=amount,
            currency=currency,
            external_id=external_id,
            settlement_id=value("settlement_id") or None,
            status=value("status", "posted") or "posted",
            attributes={"account_code": account_code, "side": side},
        )

    @staticmethod
    def _identifier(value: str, field: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field} is empty")
        if len(cleaned) > 200:
            raise ValueError(f"{field} exceeds 200 characters")
        return cleaned

    @staticmethod
    def _amount(value: str, unit: AmountUnit) -> int:
        cleaned = (
            value.replace("₹", "")
            .replace("INR", "")
            .replace(",", "")
            .strip()
        )
        negative = cleaned.startswith("(") and cleaned.endswith(")")
        if negative:
            cleaned = cleaned[1:-1]
        amount = Decimal(cleaned)
        if negative or amount < 0:
            raise ValueError("negative amounts are not valid for this evidence type")
        if unit == AmountUnit.RUPEES:
            return rupees_to_paise(amount)
        if amount != amount.to_integral_value():
            raise ValueError("paise input must be a whole number")
        return int(amount)

    @staticmethod
    def _datetime(value: str) -> datetime:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("occurred_at is empty")
        if cleaned.isdigit() and len(cleaned) in {10, 13}:
            timestamp = int(cleaned) / (1000 if len(cleaned) == 13 else 1)
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
            for pattern in (
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%d/%m/%Y %H:%M:%S",
                "%d-%m-%Y %H:%M:%S",
            ):
                try:
                    parsed = datetime.strptime(cleaned, pattern)
                    break
                except ValueError:
                    continue
            if parsed is None:
                raise ValueError(
                    f"unsupported occurred_at value: {cleaned}"
                ) from None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
