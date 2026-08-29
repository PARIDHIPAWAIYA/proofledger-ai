from __future__ import annotations

from functools import lru_cache
from typing import Annotated

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from proofledger.config import Settings, get_settings
from proofledger.domain.models import ControlStatus, SourceSystem
from proofledger.services.ai import BoundedExceptionExplainer
from proofledger.services.closing import (
    CloseBlockedError,
    SettlementCertificateService,
    settlement_evidence,
)
from proofledger.services.workspace import DemoWorkspace

router = APIRouter(prefix="/api/v1")


class TamperSimulationRequest(BaseModel):
    simulate_tamper: bool = False


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
        "evidence": settlement_evidence(settlement, workspace.dataset.records),
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
    return [
        {
            "question": question,
            "decision": decisions[question.decision_id],
        }
        for question in workspace.questions
    ]


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
    records = workspace.dataset.records
    if source:
        records = [record for record in records if record.source == source]
    return {
        "total": len(records),
        "offset": offset,
        "limit": limit,
        "items": records[offset : offset + limit],
    }


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
            workspace.dataset.records,
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
    records = workspace.dataset.records
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
