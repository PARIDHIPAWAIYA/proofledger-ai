from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class SourceSystem(str, Enum):
    MERCHANT = "merchant_orders"
    RAZORPAY = "razorpay_reconciliation"
    BANK = "bank_statement"
    LEDGER = "general_ledger"
    REFUNDS = "refund_register"


class ObjectType(str, Enum):
    ORDER = "order"
    PAYMENT = "payment"
    REFUND = "refund"
    SETTLEMENT = "settlement"
    BANK_CREDIT = "bank_credit"
    JOURNAL = "journal"


class EventType(str, Enum):
    ORDER_CREATED = "order_created"
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_FAILED = "payment_failed"
    REFUND_CREATED = "refund_created"
    REFUND_PROCESSED = "refund_processed"
    SETTLEMENT_INITIATED = "settlement_initiated"
    SETTLEMENT_PROCESSED = "settlement_processed"
    BANK_CREDITED = "bank_credited"
    JOURNAL_POSTED = "journal_posted"


class MatchTier(str, Enum):
    EXACT = "exact"
    COMPOSITE = "composite"
    SEMANTIC = "semantic"
    UNMATCHED = "unmatched"


class DecisionStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    ABSTAINED = "abstained"
    REJECTED = "rejected"


class ControlSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ControlStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class JournalSide(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


def rupees_to_paise(value: str | int | float | Decimal) -> int:
    """Convert a rupee value to integer paise without binary-float arithmetic."""

    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EvidenceRecord(BaseModel):
    """Immutable normalized source record used as evidence by the control engine."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    source: SourceSystem
    object_type: ObjectType
    occurred_at: datetime
    amount_paise: int = Field(ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    external_id: str
    order_id: str | None = None
    payment_id: str | None = None
    refund_id: str | None = None
    settlement_id: str | None = None
    bank_reference: str | None = None
    narration: str | None = None
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_hash: str = ""

    @model_validator(mode="after")
    def populate_and_validate_hash(self) -> EvidenceRecord:
        payload = self.model_dump(exclude={"source_hash"}, mode="json")
        expected = stable_hash(payload)
        if self.source_hash and self.source_hash != expected:
            raise ValueError("source_hash does not match the canonical source payload")
        if not self.source_hash:
            object.__setattr__(self, "source_hash", expected)
        return self

    def verify_integrity(self) -> bool:
        payload = self.model_dump(exclude={"source_hash"}, mode="json")
        return self.source_hash == stable_hash(payload)


class FinancialObject(BaseModel):
    object_id: str
    object_type: ObjectType
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class FinancialEvent(BaseModel):
    event_id: str
    event_type: EventType
    occurred_at: datetime
    object_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    amount_paise: int | None = Field(default=None, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)


class CandidateMatch(BaseModel):
    candidate_id: str
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    amount_delta_paise: int
    date_delta_days: int


class ReconciliationDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"dec_{uuid4().hex[:12]}")
    left_record_ids: list[str] = Field(min_length=1)
    right_record_ids: list[str] = Field(default_factory=list)
    tier: MatchTier
    status: DecisionStatus
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    candidates: list[CandidateMatch] = Field(default_factory=list)
    requires_human: bool = False

    @model_validator(mode="after")
    def enforce_approval_boundary(self) -> ReconciliationDecision:
        if self.tier == MatchTier.SEMANTIC and self.status == DecisionStatus.AUTO_APPROVED:
            raise ValueError("semantic matches can never be auto-approved")
        if self.status in {DecisionStatus.NEEDS_REVIEW, DecisionStatus.ABSTAINED}:
            self.requires_human = True
        return self


class ControlResult(BaseModel):
    control_id: str
    name: str
    status: ControlStatus
    severity: ControlSeverity
    object_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    expected_paise: int | None = None
    observed_paise: int | None = None
    difference_paise: int | None = None
    explanation: str
    remediation: str | None = None


class ReviewQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: f"q_{uuid4().hex[:12]}")
    decision_id: str
    prompt: str
    evidence_requested: str
    expected_information_gain: float = Field(ge=0)
    candidate_ids: list[str] = Field(default_factory=list)


class JournalLine(BaseModel):
    account_code: str
    account_name: str
    side: JournalSide
    amount_paise: int = Field(gt=0)
    evidence_ids: list[str] = Field(min_length=1)
    memo: str


class JournalProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: f"jrn_{uuid4().hex[:12]}")
    settlement_id: str
    lines: list[JournalLine] = Field(min_length=2)
    status: DecisionStatus = DecisionStatus.NEEDS_REVIEW
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def debit_paise(self) -> int:
        return sum(line.amount_paise for line in self.lines if line.side == JournalSide.DEBIT)

    @computed_field
    @property
    def credit_paise(self) -> int:
        return sum(line.amount_paise for line in self.lines if line.side == JournalSide.CREDIT)

    @model_validator(mode="after")
    def require_balanced_entry(self) -> JournalProposal:
        debits = sum(line.amount_paise for line in self.lines if line.side == JournalSide.DEBIT)
        credits = sum(line.amount_paise for line in self.lines if line.side == JournalSide.CREDIT)
        if debits != credits:
            raise ValueError(f"journal is unbalanced: debit={debits}, credit={credits}")
        return self


class SettlementCertificate(BaseModel):
    certificate_id: str
    settlement_id: str
    issued_at: datetime
    gross_paise: int
    fees_paise: int
    tax_paise: int
    refunds_paise: int
    net_paise: int
    evidence_hashes: dict[str, str]
    passed_control_ids: list[str]
    unresolved_control_ids: list[str] = Field(default_factory=list)
    certificate_hash: str

    def verify(self) -> bool:
        payload = self.model_dump(exclude={"certificate_hash"}, mode="json")
        return stable_hash(payload) == self.certificate_hash
