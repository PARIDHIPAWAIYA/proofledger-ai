from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

import networkx as nx

from proofledger.domain.models import (
    EventType,
    EvidenceRecord,
    FinancialEvent,
    FinancialObject,
    ObjectType,
)

EVENT_TYPE_BY_OBJECT: dict[ObjectType, EventType] = {
    ObjectType.ORDER: EventType.ORDER_CREATED,
    ObjectType.PAYMENT: EventType.PAYMENT_CAPTURED,
    ObjectType.REFUND: EventType.REFUND_PROCESSED,
    ObjectType.SETTLEMENT: EventType.SETTLEMENT_PROCESSED,
    ObjectType.BANK_CREDIT: EventType.BANK_CREDITED,
    ObjectType.JOURNAL: EventType.JOURNAL_POSTED,
}


@dataclass(frozen=True)
class GraphSummary:
    object_count: int
    event_count: int
    edge_count: int
    weak_component_count: int
    orphan_object_ids: list[str]


class FinancialLifecycleGraph:
    """OCEL-inspired bipartite graph linking immutable events to business objects."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()
        self.objects: dict[str, FinancialObject] = {}
        self.events: dict[str, FinancialEvent] = {}

    @classmethod
    def from_records(cls, records: Iterable[EvidenceRecord]) -> FinancialLifecycleGraph:
        lifecycle = cls()
        records_by_id = {record.record_id: record for record in records}
        evidence_by_object: dict[str, list[str]] = defaultdict(list)

        for record in records_by_id.values():
            object_ids = lifecycle._canonical_object_ids(record)
            event_id = f"event:{record.record_id}"
            event = FinancialEvent(
                event_id=event_id,
                event_type=EVENT_TYPE_BY_OBJECT[record.object_type],
                occurred_at=record.occurred_at,
                object_ids=object_ids,
                evidence_ids=[record.record_id],
                amount_paise=record.amount_paise,
                attributes={"source": record.source.value, "status": record.status},
            )
            lifecycle.events[event_id] = event
            lifecycle.graph.add_node(event_id, node_kind="event", payload=event)

            for object_id in object_ids:
                evidence_by_object[object_id].append(record.record_id)
                object_type = lifecycle._object_type_from_id(object_id)
                if object_id not in lifecycle.objects:
                    financial_object = FinancialObject(
                        object_id=object_id,
                        object_type=object_type,
                    )
                    lifecycle.objects[object_id] = financial_object
                    lifecycle.graph.add_node(
                        object_id,
                        node_kind="object",
                        payload=financial_object,
                    )
                lifecycle.graph.add_edge(event_id, object_id, relationship="touches")

        for object_id, evidence_ids in evidence_by_object.items():
            obj = lifecycle.objects[object_id]
            updated = obj.model_copy(update={"evidence_ids": sorted(evidence_ids)})
            lifecycle.objects[object_id] = updated
            lifecycle.graph.nodes[object_id]["payload"] = updated

        lifecycle._add_lifecycle_edges(records_by_id.values())
        return lifecycle

    @staticmethod
    def _canonical_object_ids(record: EvidenceRecord) -> list[str]:
        identifiers = [
            ("order", record.order_id),
            ("payment", record.payment_id),
            ("refund", record.refund_id),
            ("settlement", record.settlement_id),
        ]
        object_ids = [f"{prefix}:{value}" for prefix, value in identifiers if value]
        if record.object_type == ObjectType.BANK_CREDIT:
            object_ids.append(f"bank_credit:{record.external_id}")
        if record.object_type == ObjectType.JOURNAL:
            object_ids.append(f"journal:{record.external_id}")
        if not object_ids:
            object_ids.append(f"{record.object_type.value}:{record.external_id}")
        return sorted(set(object_ids))

    @staticmethod
    def _object_type_from_id(object_id: str) -> ObjectType:
        prefix = object_id.split(":", maxsplit=1)[0]
        return ObjectType(prefix)

    def _add_lifecycle_edges(self, records: Iterable[EvidenceRecord]) -> None:
        for record in records:
            links = [
                (record.order_id, record.payment_id, "order", "payment", "paid_by"),
                (record.payment_id, record.refund_id, "payment", "refund", "refunded_by"),
                (
                    record.settlement_id,
                    record.external_id if record.object_type == ObjectType.BANK_CREDIT else None,
                    "settlement",
                    "bank_credit",
                    "credited_as",
                ),
                (
                    record.settlement_id,
                    record.external_id if record.object_type == ObjectType.JOURNAL else None,
                    "settlement",
                    "journal",
                    "posted_as",
                ),
            ]
            for left_id, right_id, left_prefix, right_prefix, relationship in links:
                if not left_id or not right_id:
                    continue
                left = f"{left_prefix}:{left_id}"
                right = f"{right_prefix}:{right_id}"
                if left in self.graph and right in self.graph:
                    self.graph.add_edge(left, right, relationship=relationship)

            if record.object_type == ObjectType.SETTLEMENT:
                for payment_record_id in record.attributes.get("payment_record_ids", []):
                    payment_event = f"event:{payment_record_id}"
                    if payment_event not in self.graph:
                        continue
                    payment_objects = [
                        target
                        for _, target, data in self.graph.out_edges(payment_event, data=True)
                        if data.get("relationship") == "touches"
                        and str(target).startswith("payment:")
                    ]
                    settlement_object = f"settlement:{record.settlement_id}"
                    for payment_object in payment_objects:
                        self.graph.add_edge(
                            payment_object,
                            settlement_object,
                            relationship="settled_in",
                        )

    def evidence_path(self, source_object_id: str, target_object_id: str) -> list[str]:
        if source_object_id not in self.graph or target_object_id not in self.graph:
            return []
        try:
            undirected = self.graph.to_undirected()
            return nx.shortest_path(undirected, source_object_id, target_object_id)
        except nx.NetworkXNoPath:
            return []

    def summary(self) -> GraphSummary:
        object_ids = set(self.objects)
        connected_object_ids = {
            node_id
            for edge in self.graph.edges
            for node_id in edge[:2]
            if node_id in object_ids
        }
        return GraphSummary(
            object_count=len(self.objects),
            event_count=len(self.events),
            edge_count=self.graph.number_of_edges(),
            weak_component_count=nx.number_weakly_connected_components(self.graph),
            orphan_object_ids=sorted(object_ids - connected_object_ids),
        )
