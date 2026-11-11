"use client";

import { ReactFlow, Background, Controls, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const nodes: Node[] = [
  { id: "1", position: { x: 100, y: 0 }, data: { label: "Invoice Received" }, type: "input" },
  { id: "2", position: { x: 100, y: 100 }, data: { label: "Validate Invoice" } },
  { id: "3", position: { x: 100, y: 200 }, data: { label: "Gemini Investigation" } },
  { id: "4", position: { x: 100, y: 300 }, data: { label: "Manager Approval" } },
  { id: "5", position: { x: 100, y: 400 }, data: { label: "Record Resolution" }, type: "output" },
];
const edges: Edge[] = [
  { id: "e1-2", source: "1", target: "2" },
  { id: "e2-3", source: "2", target: "3" },
  { id: "e3-4", source: "3", target: "4" },
  { id: "e4-5", source: "4", target: "5" },
];

export default function WorkflowVisualizer() {
  return (
    <div className="h-[550px] w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-100 text-slate-900" aria-label="Static invoice exception workflow diagram">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} colorMode="light" ariaLabelConfig={{ "controls.ariaLabel": "Diagram controls" }}>
        <Background /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
