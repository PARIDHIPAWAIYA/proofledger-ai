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

function EvidenceGraphPage() {
  const [settlements, setSettlements] = useState<SettlementSummary[]>([]);
  const [selected, setSelected] = useState("setl_demo_0000");
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<SettlementSummary[]>("/settlements").then(setSettlements).catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    setGraph(null);
    api<GraphData>("/graph/" + selected).then(setGraph).catch((reason: Error) => setError(reason.message));
  }, [selected]);

  const flow = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] };
    const objectNodes = graph.nodes.filter((item) => item.kind === "object");
    const eventNodes = graph.nodes.filter((item) => item.kind === "event");
    const nodes: Node[] = [
      ...objectNodes.map((item, index) => ({
        id: item.id,
        position: { x: (index % 8) * 170, y: Math.floor(index / 8) * 130 },
        data: { label: item.id.split(":").slice(1).join(":") },
        className: "flow-object " + item.label,
      })),
      ...eventNodes.map((item, index) => ({
        id: item.id,
        position: { x: (index % 8) * 170 + 60, y: Math.floor(index / 8) * 130 + 65 },
        data: { label: item.label.replaceAll("_", " ") },
        className: "flow-event",
      })),
    ];
    const edges: Edge[] = graph.edges.map((item) => ({
      id: item.id,
      source: item.source,
      target: item.target,
      label: item.relationship,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: "#8e968f", strokeWidth: 1.2 },
      labelStyle: { fontSize: 9, fill: "#5c625f" },
    }));
    return { nodes, edges };
  }, [graph]);

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
        Objects are solid; source events are outlined. Pan, zoom, and select any node.
      </div>
      <div className="graph-canvas">
        {!graph ? (
          <LoadingState />
        ) : (
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            fitView
            minZoom={0.15}
            maxZoom={1.6}
          >
            <Background color="#d6d5cf" gap={22} />
            <MiniMap nodeColor={(node) => node.className?.toString().includes("flow-event") ? "#d5d3ca" : "#1e6a55"} />
            <Controls />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}

export default EvidenceGraphPage;
