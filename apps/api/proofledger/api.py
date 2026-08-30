from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Annotated

import networkx as nx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from proofledger.config import Settings, get_settings
from proofledger.domain.ingestion import AmountUnit, IngestionSource
from proofledger.domain.models import ControlStatus, SourceSystem
from proofledger.services.ai import BoundedExceptionExplainer, BoundedSchemaMapper
from proofledger.services.closing import (
    CloseBlockedError,
    SettlementCertificateService,
    settlement_evidence,
)
from proofledger.services.ingestion import MAX_UPLOAD_BYTES, IngestionError
from proofledger.services.workspace import DemoWorkspace

router = APIRouter(prefix="/api/v1")


class TamperSimulationRequest(BaseModel):
    simulate_tamper: bool = False


class ReviewResolutionRequest(BaseModel):
    candidate_id: str | None = None
    bank_reference: str = Field(min_length=4, max_length=80)
    amount_paise: int | None = Field(default=None, ge=0)
    occurred_at: datetime | None = None
    external_id: str | None = Field(default=None, min_length=3, max_length=120)
    evidence_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    actor: str = Field(min_length=3, max_length=120)
    rationale: str = Field(min_length=8, max_length=500)


class IngestionCommitRequest(BaseModel):
    upload_id: str = Field(min_length=4, max_length=80)
    field_mapping: dict[str, str]
    amount_unit: AmountUnit = AmountUnit.RUPEES


def ingestion_http_error(error: IngestionError, status_code: int = 422) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"message": str(error), "errors": error.errors},
    )


@lru_cache
def get_workspace() -> DemoWorkspace:
    return DemoWorkspace()


WorkspaceDependency = Annotated[DemoWorkspace, Depends(get_workspace)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/overview")
def overview(workspace: WorkspaceDependency):
    return workspace.overview()


@router.get("/settlements")
def settlements(workspace: WorkspaceDependency):
    return [workspace.settlement_summary(item) for item in workspace.settlements]


@router.get("/settlements/{settlement_id}")
def settlement_detail(
    settlement_id: str,
    workspace: WorkspaceDependency,
):
    settlement = workspace.settlement(settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="settlement not found")
    decision = workspace.settlement_decision(settlement)
    return {
        "summary": workspace.settlement_summary(settlement),
        "settlement": settlement,
        "evidence": settlement_evidence(settlement, workspace.effective_records),
        "controls": workspace.settlement_controls(settlement),
        "decision": decision,
        "journal_proposal": workspace.journal_for(settlement),
        "certificate_id": (
            f"cert_{settlement_id}"
            if f"cert_{settlement_id}" in workspace.certificates
            else None
        ),
    }


@router.get("/controls")
def controls(
    workspace: WorkspaceDependency,
    status: ControlStatus | None = None,
):
    results = workspace.controls
    if status:
        results = [result for result in results if result.status == status]
    return results


@router.get("/reviews")
def reviews(workspace: WorkspaceDependency):
    decisions = {
        decision.decision_id: decision for decision in workspace.decisions
    }
    payload = []
    for question in workspace.questions:
        decision = decisions[question.decision_id]
        settlement = workspace.records_by_id.get(decision.left_record_ids[0])
        payload.append(
            {
                "question": question,
                "decision": decision,
                "settlement": (
                    workspace.settlement_summary(settlement)
                    if settlement and settlement.settlement_id
                    else None
                ),
                "expected_bank_reference": (
                    settlement.bank_reference if settlement else None
                ),
            }
        )
    return payload


@router.get("/reviews/history")
def review_history(workspace: WorkspaceDependency):
    return list(reversed(list(workspace.review_resolutions.values())))


@router.post("/reviews/{question_id}/resolve")
def resolve_review(
    question_id: str,
    request: ReviewResolutionRequest,
    workspace: WorkspaceDependency,
):
    try:
        return workspace.resolve_review(
            question_id,
            candidate_id=request.candidate_id,
            bank_reference=request.bank_reference,
            amount_paise=request.amount_paise,
            occurred_at=request.occurred_at,
            external_id=request.external_id,
            evidence_sha256=request.evidence_sha256,
            actor=request.actor,
            rationale=request.rationale,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/benchmark")
def benchmark(workspace: WorkspaceDependency):
    return workspace.benchmark


@router.get("/evidence")
def evidence(
    workspace: WorkspaceDependency,
    source: SourceSystem | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    records = workspace.effective_records
    if source:
        records = [record for record in records if record.source == source]
    return {
        "total": len(records),
        "offset": offset,
        "limit": limit,
        "items": records[offset : offset + limit],
    }


@router.post("/ingestion/preview")
async def preview_ingestion(
    workspace: WorkspaceDependency,
    source_type: Annotated[IngestionSource, Query()],
    file: Annotated[UploadFile, File()],
):
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        return workspace.ingestion.preview(
            file.filename or "upload.csv",
            content,
            source_type,
        )
    except IngestionError as error:
        raise ingestion_http_error(error) from error


@router.post("/ingestion/{upload_id}/ai-map")
def suggest_ingestion_mapping(
    upload_id: str,
    settings: SettingsDependency,
    workspace: WorkspaceDependency,
):
    try:
        preview, fields = workspace.ingestion.mapping_context(upload_id)
    except IngestionError as error:
        raise ingestion_http_error(error, 404) from error
    deterministic = {
        item.canonical_field: item.source_column for item in preview.suggestions
    }
    return BoundedSchemaMapper(settings).suggest(
        source_type=preview.source_type.value,
        headers=preview.headers,
        target_fields=[field.name for field in fields],
        deterministic_mapping=deterministic,
    )


@router.post("/ingestion/commit")
def commit_ingestion(
    request: IngestionCommitRequest,
    workspace: WorkspaceDependency,
):
    try:
        manifest, records = workspace.ingestion.commit(
            request.upload_id,
            request.field_mapping,
            request.amount_unit,
        )
    except IngestionError as error:
        raise ingestion_http_error(error) from error
    return {"manifest": manifest, "records_preview": records[:5]}


@router.get("/ingestion/manifests")
def ingestion_manifests(workspace: WorkspaceDependency):
    return list(reversed(list(workspace.ingestion.manifests.values())))


@router.post("/ingestion/manifests/{manifest_id}/verify")
def verify_ingestion_manifest(
    manifest_id: str,
    request: TamperSimulationRequest,
    workspace: WorkspaceDependency,
):
    try:
        return workspace.ingestion.verify(
            manifest_id,
            simulate_tamper=request.simulate_tamper,
        )
    except IngestionError as error:
        raise ingestion_http_error(error, 404) from error


@router.get("/graph/{settlement_id}")
def graph(
    settlement_id: str,
    workspace: WorkspaceDependency,
):
    settlement = workspace.settlement(settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="settlement not found")
    object_id = f"settlement:{settlement_id}"
    lifecycle = workspace.graph.graph
    component = nx.node_connected_component(lifecycle.to_undirected(), object_id)
    subgraph = lifecycle.subgraph(component)
    nodes = []
    for node_id, data in subgraph.nodes(data=True):
        payload = data["payload"]
        nodes.append(
            {
                "id": node_id,
                "kind": data["node_kind"],
                "label": (
                    payload.event_type.value
                    if data["node_kind"] == "event"
                    else payload.object_type.value
                ),
            }
        )
    edges = [
        {
            "id": f"{source}|{target}|{key}",
            "source": source,
            "target": target,
            "relationship": data.get("relationship", "related"),
        }
        for source, target, key, data in subgraph.edges(keys=True, data=True)
    ]
    return {"nodes": nodes, "edges": edges}


@router.post("/settlements/{settlement_id}/certificate")
def issue_certificate(
    settlement_id: str,
    workspace: WorkspaceDependency,
):
    settlement = workspace.settlement(settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="settlement not found")
    try:
        certificate = SettlementCertificateService().issue(
            settlement,
            workspace.effective_records,
            workspace.controls,
        )
    except CloseBlockedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    workspace.certificates[certificate.certificate_id] = certificate
    return certificate


@router.post("/certificates/{certificate_id}/verify")
def verify_certificate(
    certificate_id: str,
    request: TamperSimulationRequest,
    workspace: WorkspaceDependency,
):
    certificate = workspace.certificates.get(certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="certificate not found")
    records = workspace.effective_records
    if request.simulate_tamper:
        target_id = next(iter(certificate.evidence_hashes))
        records = [
            (
                record.model_copy(update={"amount_paise": record.amount_paise + 100})
                if record.record_id == target_id
                else record
            )
            for record in records
        ]
    return SettlementCertificateService.verify(certificate, records)


@router.post("/controls/{control_id}/explain")
def explain_control(
    control_id: str,
    settings: SettingsDependency,
    workspace: WorkspaceDependency,
):
    result = next(
        (
            control
            for control in workspace.controls
            if control.control_id == control_id
            and control.status == ControlStatus.FAIL
        ),
        None,
    )
    if not result:
        raise HTTPException(status_code=404, detail="failed control not found")
    return BoundedExceptionExplainer(settings).explain(result)
