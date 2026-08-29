from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from proofledger.domain.models import (
    EvidenceRecord,
    ObjectType,
    SourceSystem,
)


class DatasetBundle(BaseModel):
    """Synthetic evidence plus labels kept separate from the reconciliation inputs."""

    dataset_id: str
    seed: int
    records: list[EvidenceRecord]
    true_links: dict[str, list[str]]
    anomaly_labels: dict[str, str] = Field(default_factory=dict)

    def by_source(self) -> dict[SourceSystem, list[EvidenceRecord]]:
        grouped: dict[SourceSystem, list[EvidenceRecord]] = defaultdict(list)
        for record in self.records:
            grouped[record.source].append(record)
        return dict(grouped)


class SyntheticFinanceGenerator:
    """Create deterministic Razorpay-shaped records without using real customer data."""

    def __init__(self, seed: int = 2026) -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self.start = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)

    def generate(self, order_count: int = 600, settlement_size: int = 50) -> DatasetBundle:
        if order_count < 20:
            raise ValueError("order_count must be at least 20")
        if settlement_size < 10:
            raise ValueError("settlement_size must be at least 10")

        records: list[EvidenceRecord] = []
        true_links: dict[str, list[str]] = {}
        anomaly_labels: dict[str, str] = {}
        payment_groups: dict[int, list[EvidenceRecord]] = defaultdict(list)
        refund_groups: dict[int, list[EvidenceRecord]] = defaultdict(list)

        for index in range(order_count):
            settlement_index = index // settlement_size
            occurred_at = self.start + timedelta(minutes=index * 11)
            amount_paise = self.random.randrange(250, 12_000) * 100
            order_id = f"order_demo_{index:05d}"
            payment_id = f"pay_demo_{index:05d}"

            order = EvidenceRecord(
                record_id=f"merchant_order_{index:05d}",
                source=SourceSystem.MERCHANT,
                object_type=ObjectType.ORDER,
                occurred_at=occurred_at,
                amount_paise=amount_paise,
                external_id=order_id,
                order_id=order_id,
                status="paid",
                attributes={"merchant_customer_key": f"customer_{index % 97:03d}"},
            )
            payment = EvidenceRecord(
                record_id=f"razorpay_payment_{index:05d}",
                source=SourceSystem.RAZORPAY,
                object_type=ObjectType.PAYMENT,
                occurred_at=occurred_at + timedelta(seconds=42),
                amount_paise=amount_paise,
                external_id=payment_id,
                order_id=order_id,
                payment_id=payment_id,
                status="captured",
                attributes={"method": ("upi", "card", "netbanking")[index % 3]},
            )
            records.extend([order, payment])
            payment_groups[settlement_index].append(payment)
            true_links[order.record_id] = [payment.record_id]

            if index % 17 == 0:
                refund_amount = min(amount_paise, (20 + index % 40) * 100)
                refund_id = f"rfnd_demo_{index:05d}"
                refund = EvidenceRecord(
                    record_id=f"refund_register_{index:05d}",
                    source=SourceSystem.REFUNDS,
                    object_type=ObjectType.REFUND,
                    occurred_at=occurred_at + timedelta(hours=3),
                    amount_paise=refund_amount,
                    external_id=refund_id,
                    order_id=order_id,
                    payment_id=payment_id,
                    refund_id=refund_id,
                    status="processed",
                )
                records.append(refund)
                refund_groups[settlement_index].append(refund)
                true_links[payment.record_id] = [refund.record_id]

        settlement_count = max(payment_groups) + 1
        for settlement_index in range(settlement_count):
            settlement_id = f"setl_demo_{settlement_index:04d}"
            settled_at = self.start + timedelta(days=2 + settlement_index)
            payments = payment_groups[settlement_index]
            refunds = refund_groups[settlement_index]
            gross_paise = sum(record.amount_paise for record in payments)
            refunds_paise = sum(record.amount_paise for record in refunds)
            fees_paise = round(gross_paise * 0.02)
            tax_paise = round(fees_paise * 0.18)
            net_paise = gross_paise - refunds_paise - fees_paise - tax_paise

            settlement = EvidenceRecord(
                record_id=f"razorpay_settlement_{settlement_index:04d}",
                source=SourceSystem.RAZORPAY,
                object_type=ObjectType.SETTLEMENT,
                occurred_at=settled_at,
                amount_paise=net_paise,
                external_id=settlement_id,
                settlement_id=settlement_id,
                bank_reference=f"UTRDEMO{settlement_index:010d}",
                status="processed",
                attributes={
                    "gross_paise": gross_paise,
                    "fees_paise": fees_paise,
                    "tax_paise": tax_paise,
                    "refunds_paise": refunds_paise,
                    "payment_record_ids": [record.record_id for record in payments],
                    "refund_record_ids": [record.record_id for record in refunds],
                },
            )
            records.append(settlement)
            for record in payments:
                true_links.setdefault(record.record_id, []).append(settlement.record_id)

            is_missing_bank = settlement_index == 1
            is_amount_mismatch = settlement_index == 2
            is_ambiguous = settlement_index in {3, 4}
            bank_amount = net_paise + (100 if is_amount_mismatch else 0)

            if is_missing_bank:
                anomaly_labels[settlement.record_id] = "missing_bank_credit"
            else:
                bank = EvidenceRecord(
                    record_id=f"bank_credit_{settlement_index:04d}",
                    source=SourceSystem.BANK,
                    object_type=ObjectType.BANK_CREDIT,
                    occurred_at=settled_at + timedelta(days=1, minutes=settlement_index * 3),
                    amount_paise=bank_amount,
                    external_id=f"bank_line_{settlement_index:04d}",
                    settlement_id=None if is_ambiguous else settlement_id,
                    bank_reference=None if is_ambiguous else settlement.bank_reference,
                    narration=(
                        "RAZORPAY SETTLEMENT CREDIT"
                        if is_ambiguous
                        else f"RAZORPAY {settlement_id} {settlement.bank_reference}"
                    ),
                    status="credited",
                )
                records.append(bank)
                true_links[settlement.record_id] = [bank.record_id]
                if is_amount_mismatch:
                    anomaly_labels[bank.record_id] = "bank_amount_plus_one_rupee"
                if is_ambiguous:
                    anomaly_labels[bank.record_id] = "missing_reference_requires_review"

            ledger = EvidenceRecord(
                record_id=f"ledger_bank_{settlement_index:04d}",
                source=SourceSystem.LEDGER,
                object_type=ObjectType.JOURNAL,
                occurred_at=settled_at + timedelta(days=1, hours=2),
                amount_paise=net_paise,
                external_id=f"journal_demo_{settlement_index:04d}",
                settlement_id=settlement_id,
                status="posted",
                attributes={"account_code": "1100", "side": "debit"},
            )
            records.append(ledger)
            true_links.setdefault(settlement.record_id, []).append(ledger.record_id)

            if settlement_index == 5:
                duplicate_payload: dict[str, Any] = ledger.model_dump(
                    exclude={"record_id", "external_id", "source_hash"}
                )
                duplicate = EvidenceRecord(
                    **duplicate_payload,
                    record_id="ledger_bank_0005_duplicate",
                    external_id="journal_demo_0005_duplicate",
                )
                records.append(duplicate)
                anomaly_labels[duplicate.record_id] = "duplicate_ledger_posting"

        return DatasetBundle(
            dataset_id=f"synthetic_{self.seed}_{order_count}",
            seed=self.seed,
            records=sorted(records, key=lambda record: (record.occurred_at, record.record_id)),
            true_links=true_links,
            anomaly_labels=anomaly_labels,
        )
