import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { GitBranch, Info } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { GraphData, SettlementSummary } from "../types";
import { ErrorState, LoadingState, PageHeader } from "./Shared";

/** Left-to-right lifecycle order. Anything unknown lands after the known stages. */
const STAGES = [
  "order",
  "payment",
  "refund",
  "settlement",
  "bank_credit",
  "journal",
] as const;

/** Object types collapsed into one node in spine mode; a payout holds ~50 payments. */
const BULK_TYPES = new Set(["order", "payment", "refund"]);

const STAGE_LABELS: Record<string, string> = {
  order: "Merchant orders",
  payment: "Captured payments",
  refund: "Refunds",
  settlement: "Settlement",
  bank_credit: "Bank credit",
  journal: "Ledger posting",
};

const COLUMN_WIDTH = 210;
const ROW_HEIGHT = 62;
const COLUMN_ROWS = 12;

function stageOf(objectId: string): number {
  const prefix = objectId.split(":", 1)[0];
  const index = STAGES.indexOf(prefix as (typeof STAGES)[number]);
  return index === -1 ? STAGES.length : index;
}

function typeOf(objectId: string): string {
  return objectId.split(":", 1)[0];
}

function shortLabel(objectId: string): string {
  const value = objectId.split(":").slice(1).join(":");
  return value.length > 22 ? `${value.slice(0, 20)}…` : value;
}

function EvidenceGraphPage() {
  const [settlements, setSettlements] = useState<SettlementSummary[]>([]);
  const [selected, setSelected] = useState("setl_demo_0000");
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [spineOnly, setSpineOnly] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<SettlementSummary[]>("/settlements")
      .then(setSettlements)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    setGraph(null);
    api<GraphData>("/graph/" + selected)
      .then(setGraph)
      .catch((reason: Error) => setError(reason.message));
  }, [selected]);

  const flow = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[], hidden: 0 };

    const objectNodes = graph.nodes.filter((item) => item.kind === "object");
    const eventNodes = graph.nodes.filter((item) => item.kind === "event");

    /**
     * Spine mode rewrites every bulk object onto a single aggregate node and drops
     * per-record events, so the payout lifecycle stays legible. Full mode keeps
     * every node and only fixes the layout.
     */
    const alias = new Map<string, string>();
    const aggregateCounts = new Map<string, number>();
    if (spineOnly) {
      objectNodes.forEach((item) => {
        const type = typeOf(item.id);
        if (!BULK_TYPES.has(type)) return;
        alias.set(item.id, `group:${type}`);
        aggregateCounts.set(type, (aggregateCounts.get(type) ?? 0) + 1);
      });
    }

    const visibleObjects = objectNodes.filter((item) => !alias.has(item.id));
    const visibleEvents = spineOnly ? [] : eventNodes;

    type Placed = { id: string; label: string; className: string; stage: number };
    const placed: Placed[] = [
      ...[...aggregateCounts.entries()].map(([type, count]) => ({
        id: `group:${type}`,
        label: `${count} ${STAGE_LABELS[type] ?? type}`.toLowerCase(),
        className: `flow-object flow-aggregate ${type}`,
        stage: stageOf(`${type}:`),
      })),
      ...visibleObjects.map((item) => ({
        id: item.id,
        label: shortLabel(item.id),
        className: `flow-object ${item.label}`,
        stage: stageOf(item.id),
      })),
      ...visibleEvents.map((item) => ({
        id: item.id,
        label: item.label.replaceAll("_", " "),
        className: "flow-event",
        stage: STAGES.length,
      })),
    ];

    const rowCursor = new Map<number, number>();
    const nodes: Node[] = placed.map((item) => {
      const row = rowCursor.get(item.stage) ?? 0;
      rowCursor.set(item.stage, row + 1);
      const subColumn = Math.floor(row / COLUMN_ROWS);
      return {
        id: item.id,
        position: {
          x: item.stage * COLUMN_WIDTH + subColumn * 96,
          y: (row % COLUMN_ROWS) * ROW_HEIGHT,
        },
        data: { label: item.label },
        className: item.className,
      };
    });

    const visibleIds = new Set(nodes.map((item) => item.id));
    const seen = new Set<string>();
    const edges: Edge[] = [];
    graph.edges.forEach((item) => {
      const source = alias.get(item.source) ?? item.source;
      const target = alias.get(item.target) ?? item.target;
      if (source === target) return;
      if (!visibleIds.has(source) || !visibleIds.has(target)) return;
      const key = `${source}|${target}|${item.relationship}`;
      if (seen.has(key)) return;
      seen.add(key);
      edges.push({
        id: key,
        source,
        target,
        label: item.relationship,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "#8e968f", strokeWidth: 1.2 },
        labelStyle: { fontSize: 9, fill: "#5c625f" },
      });
    });

    const hidden = graph.nodes.length - nodes.length;
    return { nodes, edges, hidden };
  }, [graph, spineOnly]);

  if (error) return <ErrorState message={error} />;
  if (!settlements.length) return <LoadingState />;

  return (
    <div className="page graph-page">
      <PageHeader
        eyebrow="OCEL-inspired lifecycle"
        title="See the money move."
        description="Events and business objects form one evidence graph, so a controller can traverse from an order through settlement, bank credit, and journal posting."
        action={
          <label className="select-box">
            <GitBranch size={16} />
            <select value={selected} onChange={(event) => setSelected(event.target.value)}>
              {settlements.map((item) => (
                <option key={item.settlement_id} value={item.settlement_id}>
                  {item.settlement_id}
                </option>
              ))}
            </select>
          </label>
        }
      />

      <div className="graph-note">
        <Info size={16} />
        <span>
          Stages run left to right: orders → payments → refunds → settlement → bank credit →
          ledger. {spineOnly
            ? `${flow.hidden} member records are folded into stage totals.`
            : "Every member record and source event is shown."}
        </span>
        <div className="segmented graph-mode">
          <button className={spineOnly ? "active" : ""} onClick={() => setSpineOnly(true)}>
            Lifecycle spine
          </button>
          <button className={spineOnly ? "" : "active"} onClick={() => setSpineOnly(false)}>
            Every record
          </button>
        </div>
      </div>
      <div className="graph-canvas">
        {!graph ? (
          <LoadingState />
        ) : (
          <ReactFlow
            key={`${selected}-${spineOnly}`}
            nodes={flow.nodes}
            edges={flow.edges}
            fitView
            minZoom={0.15}
            maxZoom={1.6}
          >
            <Background color="#d6d5cf" gap={22} />
            <MiniMap
              nodeColor={(node) =>
                node.className?.toString().includes("flow-event") ? "#d5d3ca" : "#1e6a55"
              }
            />
            <Controls />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}

export default EvidenceGraphPage;
