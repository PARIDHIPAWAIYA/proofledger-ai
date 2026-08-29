from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

from proofledger.domain.models import (
    ControlResult,
    ControlSeverity,
    ControlStatus,
    EvidenceRecord,
    ObjectType,
    SourceSystem,
)


class FinanceControlEngine:
    """Deterministic accounting and process controls; no LLM participates here."""

    def evaluate(self, evidence: Iterable[EvidenceRecord]) -> list[ControlResult]:
        records = list(evidence)
        results: list[ControlResult] = []
        results.extend(self._source_integrity(records))
        results.extend(self._order_payment_amount(records))
        results.extend(self._settlement_equation(records))
        results.extend(self._bank_presence(records))
        results.extend(self._bank_amount(records))
        results.extend(self._duplicate_ledger(records))
        results.extend(self._ledger_amount(records))
        results.extend(self._lifecycle_sequence(records))
        results.extend(self._currency_consistency(records))
        results.extend(self._orphan_references(records))
        return results

    @staticmethod
    def _source_integrity(records: list[EvidenceRecord]) -> list[ControlResult]:
        invalid = [record.record_id for record in records if not record.verify_integrity()]
        return [
            ControlResult(
                control_id="CTRL-01",
                name="Source evidence integrity",
                status=ControlStatus.FAIL if invalid else ControlStatus.PASS,
                severity=ControlSeverity.CRITICAL,
                evidence_ids=invalid,
                explanation=(
                    f"{len(invalid)} source hashes do not match their canonical payloads."
                    if invalid
                    else f"All {len(records)} source records retain valid SHA-256 evidence hashes."
                ),
                remediation="Reload the affected source and investigate post-ingestion mutation."
                if invalid
                else None,
            )
        ]

    @staticmethod
    def _order_payment_amount(records: list[EvidenceRecord]) -> list[ControlResult]:
        orders = {
            record.order_id: record
            for record in records
            if record.source == SourceSystem.MERCHANT and record.order_id
        }
        payments = {
            record.order_id: record
            for record in records
            if record.object_type == ObjectType.PAYMENT and record.order_id
        }
        results: list[ControlResult] = []
        for order_id, order in orders.items():
            payment = payments.get(order_id)
            passed = payment is not None and payment.amount_paise == order.amount_paise
            observed = payment.amount_paise if payment else None
            results.append(
                ControlResult(
                    control_id="CTRL-02",
                    name="Order-to-payment amount equality",
                    status=ControlStatus.PASS if passed else ControlStatus.FAIL,
                    severity=ControlSeverity.CRITICAL,
                    object_ids=[f"order:{order_id}"],
                    evidence_ids=[order.record_id] + ([payment.record_id] if payment else []),
                    expected_paise=order.amount_paise,
                    observed_paise=observed,
                    difference_paise=(
                        observed - order.amount_paise if observed is not None else None
                    ),
                    explanation=(
                        "Captured payment equals the merchant order."
                        if passed
                        else "The order has no equal captured payment."
                    ),
                    remediation="Locate the missing payment or investigate the amount mismatch."
                    if not passed
                    else None,
                )
            )
        return results

    @staticmethod
    def _settlements(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
        return [record for record in records if record.object_type == ObjectType.SETTLEMENT]

    def _settlement_equation(self, records: list[EvidenceRecord]) -> list[ControlResult]:
        results: list[ControlResult] = []
        for settlement in self._settlements(records):
            data = settlement.attributes
            expected = (
                int(data.get("gross_paise", 0))
                - int(data.get("refunds_paise", 0))
                - int(data.get("fees_paise", 0))
                - int(data.get("tax_paise", 0))
            )
            passed = expected == settlement.amount_paise
            results.append(
                ControlResult(
                    control_id="CTRL-03",
                    name="Settlement accounting equation",
                    status=ControlStatus.PASS if passed else ControlStatus.FAIL,
                    severity=ControlSeverity.CRITICAL,
                    object_ids=[f"settlement:{settlement.settlement_id}"],
                    evidence_ids=[settlement.record_id],
                    expected_paise=expected,
                    observed_paise=settlement.amount_paise,
                    difference_paise=settlement.amount_paise - expected,
                    explanation=(
                        "Gross minus refunds, fees, and tax equals settlement net."
                        if passed
                        else "Settlement components do not reproduce the declared net amount."
                    ),
                    remediation="Recompute the settlement from payment-level evidence."
                    if not passed
                    else None,
                )
            )
        return results

    def _bank_presence(self, records: list[EvidenceRecord]) -> list[ControlResult]:
        banks = [record for record in records if record.object_type == ObjectType.BANK_CREDIT]
        results: list[ControlResult] = []
        for settlement in self._settlements(records):
            matched = [
                bank
                for bank in banks
                if bank.settlement_id == settlement.settlement_id
                or (
                    settlement.bank_reference
                    and bank.bank_reference == settlement.bank_reference
                )
            ]
            results.append(
                ControlResult(
                    control_id="CTRL-04",
                    name="Settlement has bank evidence",
                    status=ControlStatus.PASS if matched else ControlStatus.FAIL,
                    severity=ControlSeverity.CRITICAL,
                    object_ids=[f"settlement:{settlement.settlement_id}"],
                    evidence_ids=[settlement.record_id]
                    + [record.record_id for record in matched],
                    explanation=(
                        "A bank credit is linked by settlement ID or bank reference."
                        if matched
                        else "No exact bank evidence is linked to this processed settlement."
                    ),
                    remediation="Review candidate credits or obtain a bank reference."
                    if not matched
                    else None,
                )
            )
        return results

    def _bank_amount(self, records: list[EvidenceRecord]) -> list[ControlResult]:
        banks = [record for record in records if record.object_type == ObjectType.BANK_CREDIT]
        results: list[ControlResult] = []
        for settlement in self._settlements(records):
            matched = next(
                (
                    bank
                    for bank in banks
                    if bank.settlement_id == settlement.settlement_id
                    or (
                        settlement.bank_reference
                        and bank.bank_reference == settlement.bank_reference
                    )
                ),
                None,
            )
            if not matched:
                continue
            passed = settlement.amount_paise == matched.amount_paise
            results.append(
                ControlResult(
                    control_id="CTRL-05",
                    name="Settlement-to-bank amount equality",
                    status=ControlStatus.PASS if passed else ControlStatus.FAIL,
                    severity=ControlSeverity.CRITICAL,
                    object_ids=[
                        f"settlement:{settlement.settlement_id}",
                        f"bank_credit:{matched.external_id}",
                    ],
                    evidence_ids=[settlement.record_id, matched.record_id],
                    expected_paise=settlement.amount_paise,
                    observed_paise=matched.amount_paise,
                    difference_paise=matched.amount_paise - settlement.amount_paise,
                    explanation=(
                        "Bank credit equals the settlement net."
                        if passed
                        else "Bank credit differs from the settlement net."
                    ),
                    remediation="Do not close; inspect bank adjustments and settlement evidence."
                    if not passed
                    else None,
                )
            )
        return results

    @staticmethod
    def _duplicate_ledger(records: list[EvidenceRecord]) -> list[ControlResult]:
        ledger = [record for record in records if record.object_type == ObjectType.JOURNAL]
        keys = [
            (
                record.settlement_id,
                record.amount_paise,
                record.attributes.get("account_code"),
                record.attributes.get("side"),
            )
            for record in ledger
        ]
        duplicate_keys = {key for key, count in Counter(keys).items() if count > 1}
        duplicates = [
            record.record_id
            for record, key in zip(ledger, keys, strict=True)
            if key in duplicate_keys
        ]
        return [
            ControlResult(
                control_id="CTRL-06",
                name="Duplicate ledger posting",
                status=ControlStatus.FAIL if duplicates else ControlStatus.PASS,
                severity=ControlSeverity.CRITICAL,
                evidence_ids=duplicates,
                explanation=(
                    f"{len(duplicates)} ledger lines share a duplicate posting signature."
                    if duplicates
                    else "No duplicate settlement postings were detected."
                ),
                remediation="Reverse or remove the duplicate after controller approval."
                if duplicates
                else None,
            )
        ]

    def _ledger_amount(self, records: list[EvidenceRecord]) -> list[ControlResult]:
        ledger_by_settlement: dict[str, list[EvidenceRecord]] = defaultdict(list)
        for record in records:
            if record.object_type == ObjectType.JOURNAL and record.settlement_id:
                ledger_by_settlement[record.settlement_id].append(record)
        results: list[ControlResult] = []
        for settlement in self._settlements(records):
            lines = ledger_by_settlement.get(settlement.settlement_id or "", [])
            observed = sum(record.amount_paise for record in lines)
            passed = len(lines) == 1 and observed == settlement.amount_paise
            results.append(
                ControlResult(
                    control_id="CTRL-07",
                    name="Settlement ledger posting",
                    status=ControlStatus.PASS if passed else ControlStatus.FAIL,
                    severity=ControlSeverity.CRITICAL,
                    object_ids=[f"settlement:{settlement.settlement_id}"],
                    evidence_ids=[settlement.record_id] + [line.record_id for line in lines],
                    expected_paise=settlement.amount_paise,
                    observed_paise=observed,
                    difference_paise=observed - settlement.amount_paise,
                    explanation=(
                        "Exactly one ledger posting equals the settlement net."
                        if passed
                        else "Ledger evidence is missing, duplicated, or unequal to settlement net."
                    ),
                    remediation="Prepare a reviewed correcting journal."
                    if not passed
                    else None,
                )
            )
        return results

    def _lifecycle_sequence(self, records: list[EvidenceRecord]) -> list[ControlResult]:
        by_id = {record.record_id: record for record in records}
        results: list[ControlResult] = []
        for settlement in self._settlements(records):
            member_ids = settlement.attributes.get("payment_record_ids", [])
            members = [by_id[record_id] for record_id in member_ids if record_id in by_id]
            passed = (
                bool(members)
                and max(record.occurred_at for record in members)
                <= settlement.occurred_at
            )
            results.append(
                ControlResult(
                    control_id="CTRL-08",
                    name="Allowed financial lifecycle sequence",
                    status=ControlStatus.PASS if passed else ControlStatus.FAIL,
                    severity=ControlSeverity.CRITICAL,
                    object_ids=[f"settlement:{settlement.settlement_id}"],
                    evidence_ids=[settlement.record_id] + [item.record_id for item in members],
                    explanation=(
                        "All member payments were captured before settlement."
                        if passed
                        else "Settlement has no member payments or predates a captured payment."
                    ),
                    remediation="Validate settlement membership and event timestamps."
                    if not passed
                    else None,
                )
            )
        return results

    @staticmethod
    def _currency_consistency(records: list[EvidenceRecord]) -> list[ControlResult]:
        currencies = sorted({record.currency for record in records})
        passed = currencies == ["INR"]
        return [
            ControlResult(
                control_id="CTRL-09",
                name="Currency consistency",
                status=ControlStatus.PASS if passed else ControlStatus.FAIL,
                severity=ControlSeverity.CRITICAL,
                evidence_ids=[] if passed else [record.record_id for record in records],
                explanation=(
                    "All records use INR."
                    if passed
                    else f"Unexpected currencies detected: {', '.join(currencies)}."
                ),
                remediation="Partition and translate currencies before reconciliation."
                if not passed
                else None,
            )
        ]

    @staticmethod
    def _orphan_references(records: list[EvidenceRecord]) -> list[ControlResult]:
        order_ids = {record.order_id for record in records if record.order_id}
        payment_ids = {record.payment_id for record in records if record.payment_id}
        invalid: list[str] = []
        for record in records:
            if record.object_type == ObjectType.REFUND:
                if record.order_id not in order_ids or record.payment_id not in payment_ids:
                    invalid.append(record.record_id)
        return [
            ControlResult(
                control_id="CTRL-10",
                name="No orphan refund references",
                status=ControlStatus.FAIL if invalid else ControlStatus.PASS,
                severity=ControlSeverity.WARNING,
                evidence_ids=invalid,
                explanation=(
                    f"{len(invalid)} refunds point to unknown orders or payments."
                    if invalid
                    else "Every refund resolves to a known order and payment."
                ),
                remediation="Request the missing order/payment evidence." if invalid else None,
            )
        ]
