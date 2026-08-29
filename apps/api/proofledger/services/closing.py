from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from proofledger.domain.models import (
    ControlResult,
    ControlSeverity,
    ControlStatus,
    EvidenceRecord,
    JournalLine,
    JournalProposal,
    JournalSide,
    ObjectType,
    SettlementCertificate,
    stable_hash,
)


class CloseBlockedError(ValueError):
    """Raised when critical unresolved evidence prevents a financial close."""


class CertificateVerification(BaseModel):
    valid: bool
    checks: dict[str, bool]
    failures: list[str]


def settlement_evidence(
    settlement: EvidenceRecord,
    records: list[EvidenceRecord],
) -> list[EvidenceRecord]:
    member_ids = {
        settlement.record_id,
        *settlement.attributes.get("payment_record_ids", []),
        *settlement.attributes.get("refund_record_ids", []),
    }
    linked = [
        record
        for record in records
        if record.record_id in member_ids
        or (
            settlement.settlement_id
            and record.settlement_id == settlement.settlement_id
        )
        or (
            settlement.bank_reference
            and record.bank_reference == settlement.bank_reference
        )
    ]
    return sorted(
        {record.record_id: record for record in linked}.values(),
        key=lambda record: record.record_id,
    )


class JournalProposalService:
    """Propose a balanced settlement entry; posting remains a human action."""

    def propose(
        self,
        settlement: EvidenceRecord,
        records: list[EvidenceRecord],
    ) -> JournalProposal:
        if settlement.object_type != ObjectType.SETTLEMENT:
            raise ValueError("journal proposals require a settlement record")
        data = settlement.attributes
        gross = int(data.get("gross_paise", 0))
        fees = int(data.get("fees_paise", 0))
        tax = int(data.get("tax_paise", 0))
        refunds = int(data.get("refunds_paise", 0))
        if settlement.amount_paise + fees + tax + refunds != gross:
            raise CloseBlockedError("settlement components do not balance")

        evidence_ids = [
            record.record_id for record in settlement_evidence(settlement, records)
        ]
        lines = [
            JournalLine(
                account_code="1100",
                account_name="Bank",
                side=JournalSide.DEBIT,
                amount_paise=settlement.amount_paise,
                evidence_ids=evidence_ids,
                memo=f"Net receipt for {settlement.settlement_id}",
            ),
            JournalLine(
                account_code="1200",
                account_name="Razorpay clearing",
                side=JournalSide.CREDIT,
                amount_paise=gross,
                evidence_ids=evidence_ids,
                memo=f"Clear captured payments in {settlement.settlement_id}",
            ),
        ]
        optional_debits = [
            (
                "6100",
                "Payment gateway fees",
                fees,
                [settlement.record_id],
                f"Gateway fee for {settlement.settlement_id}",
            ),
            (
                "1410",
                "Input GST",
                tax,
                [settlement.record_id],
                f"Tax on gateway fee for {settlement.settlement_id}",
            ),
            (
                "2200",
                "Customer refunds",
                refunds,
                evidence_ids,
                f"Refunds deducted in {settlement.settlement_id}",
            ),
        ]
        for account_code, account_name, amount, line_evidence, memo in optional_debits:
            if amount > 0:
                lines.insert(
                    -1,
                    JournalLine(
                        account_code=account_code,
                        account_name=account_name,
                        side=JournalSide.DEBIT,
                        amount_paise=amount,
                        evidence_ids=line_evidence,
                        memo=memo,
                    ),
                )
        return JournalProposal(
            settlement_id=settlement.settlement_id or settlement.external_id,
            lines=lines,
        )


class SettlementCertificateService:
    """Issue and independently verify proof-carrying settlement close certificates."""

    def issue(
        self,
        settlement: EvidenceRecord,
        records: list[EvidenceRecord],
        control_results: list[ControlResult],
    ) -> SettlementCertificate:
        evidence = settlement_evidence(settlement, records)
        evidence_ids = {record.record_id for record in evidence}
        settlement_object_id = f"settlement:{settlement.settlement_id}"
        relevant = [
            result
            for result in control_results
            if settlement_object_id in result.object_ids
            or bool(evidence_ids.intersection(result.evidence_ids))
            or (not result.object_ids and not result.evidence_ids)
        ]
        blockers = [
            result
            for result in relevant
            if result.status == ControlStatus.FAIL
            and result.severity == ControlSeverity.CRITICAL
        ]
        if blockers:
            blocker_ids = ", ".join(
                sorted({result.control_id for result in blockers})
            )
            raise CloseBlockedError(
                f"critical controls block settlement close: {blocker_ids}"
            )

        data = settlement.attributes
        certificate_payload = {
            "certificate_id": f"cert_{settlement.settlement_id}",
            "settlement_id": settlement.settlement_id or settlement.external_id,
            "issued_at": datetime.now(timezone.utc),
            "gross_paise": int(data.get("gross_paise", 0)),
            "fees_paise": int(data.get("fees_paise", 0)),
            "tax_paise": int(data.get("tax_paise", 0)),
            "refunds_paise": int(data.get("refunds_paise", 0)),
            "net_paise": settlement.amount_paise,
            "evidence_hashes": {
                record.record_id: record.source_hash for record in evidence
            },
            "passed_control_ids": sorted(
                {
                    result.control_id
                    for result in relevant
                    if result.status == ControlStatus.PASS
                }
            ),
            "unresolved_control_ids": [],
        }
        return SettlementCertificate(
            **certificate_payload,
            certificate_hash=stable_hash(
                SettlementCertificate(
                    **certificate_payload,
                    certificate_hash="pending",
                ).model_dump(exclude={"certificate_hash"}, mode="json")
            ),
        )

    @staticmethod
    def verify(
        certificate: SettlementCertificate,
        records: list[EvidenceRecord],
    ) -> CertificateVerification:
        records_by_id = {record.record_id: record for record in records}
        checks = {
            "certificate_hash": certificate.verify(),
            "settlement_equation": (
                certificate.gross_paise
                - certificate.fees_paise
                - certificate.tax_paise
                - certificate.refunds_paise
                == certificate.net_paise
            ),
            "no_unresolved_controls": not certificate.unresolved_control_ids,
            "all_evidence_present": all(
                record_id in records_by_id
                for record_id in certificate.evidence_hashes
            ),
            "evidence_hashes_match": all(
                record_id in records_by_id
                and records_by_id[record_id].source_hash == expected_hash
                and records_by_id[record_id].verify_integrity()
                for record_id, expected_hash in certificate.evidence_hashes.items()
            ),
        }
        failures = [name for name, passed in checks.items() if not passed]
        return CertificateVerification(
            valid=not failures,
            checks=checks,
            failures=failures,
        )
