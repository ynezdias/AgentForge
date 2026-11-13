"use client";
import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import type { Workflow } from "@/lib/api";
import "@xyflow/react/dist/style.css";

const labels: Record<string, string> = { "invoice.validate": "Validate invoice", "invoice.investigate": "Gemini investigation", "invoice.resolve": "Record review status" };
export default function WorkflowVisualizer({ workflow }: { workflow: Workflow }) {
  const { nodes, edges } = useMemo(() => {
    const steps = workflow.definition?.steps ?? [];
    const nodes: Node[] = steps.map((step, index) => ({
      id: step.id, position: { x: index * 235, y: 55 },
      data: { label: step.type === "approval" ? "Manager approval" : step.type === "condition" ? "Exception detected?" : labels[step.tool ?? ""] ?? step.id.replaceAll("_", " ") },
      type: index === 0 ? "input" : "default",
      style: { width: 170, borderColor: step.type === "approval" ? "#62a78f" : step.type === "condition" ? "#d3b77e" : "#cfdce3", background: step.type === "approval" ? "#edf7f1" : "#fff" },
    }));
    nodes.push({ id: "__end__", position: { x: Math.max(steps.length - 1, 0) * 235, y: 220 }, data: { label: "Completed" }, type: "output", style: { width: 170, borderColor: "#7caf9c", background: "#edf7f1" } });
    const edges: Edge[] = [];
    steps.forEach((step, index) => {
      const add = (target: string, label?: string) => edges.push({ id: `${step.id}-${target}-${label ?? "next"}`, source: step.id, target, label, type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed, color: "#91a9ab" }, style: { stroke: "#91a9ab" }, labelStyle: { fontSize: 9, fill: "#778c94" }, labelBgStyle: { fill: "#fafcfc" } });
      if (step.type === "condition") { if (step.on_true) add(step.on_true, "Exception"); if (step.on_false) add(step.on_false, "No exception"); }
      else add(steps[index + 1]?.id ?? "__end__");
    });
    return { nodes, edges };
  }, [workflow.definition]);
  return <div className="workflow-diagram" aria-label={`Process diagram for ${workflow.name}`}><ReactFlow key={workflow.id} nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: .2 }} minZoom={.2} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} colorMode="light" proOptions={{ hideAttribution: false }}><Background color="#d8e5e5" gap={20} /><Controls showInteractive={false} /></ReactFlow></div>;
}
