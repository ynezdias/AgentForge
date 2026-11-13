"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowRight, GitBranch, ShieldCheck, Sparkles } from "lucide-react";
import { useWorkspace } from "@/components/Workspace";
import { EmptyWorkspace, Loading, PageHeading } from "@/components/UI";
import WorkflowVisualizer from "@/components/WorkflowVisualizer";

export default function WorkflowsPage() {
  const { workflows, loading, error } = useWorkspace();
  const [selectedId, setSelectedId] = useState("");
  const selected = workflows.find((workflow) => workflow.id === selectedId) ?? workflows[0];
  return <><PageHeading eyebrow="YOUR AUTOMATIONS" title="Built for a careful review." description="See the checks, decisions, and handoffs in each configured workflow." action={<Link href="/invoices" className="button primary">Review an invoice <ArrowRight size={15} /></Link>} />
    {loading ? <Loading /> : workflows.length === 0 && !error ? <div className="card"><EmptyWorkspace /></div> : selected ? <div className="workflow-grid"><div className="workflow-options">{workflows.map((workflow) => { const ai = workflow.definition?.steps.some((step) => step.tool === "invoice.investigate"); return <button key={workflow.id} className={`workflow-option ${selected.id === workflow.id ? "selected" : ""}`} aria-pressed={selected.id === workflow.id} onClick={() => setSelectedId(workflow.id)}><span className="workflow-number">{ai ? <Sparkles size={17} /> : <ShieldCheck size={17} />}{ai ? "AI + BUSINESS RULES" : "RULES + HUMAN REVIEW"}</span><h2>{workflow.name}</h2><p>{ai ? "Investigate invoice exceptions with Gemini before a manager records a decision." : "Check invoice facts and route discrepancies directly to a manager for review."}</p><span className="badge">{workflow.definition?.steps.length ?? 0} steps · Version {workflow.version}</span></button>; })}</div><section className="card"><div className="card-header"><div><h2>{selected.name}</h2><p className="card-subtitle">Configured process · drag the canvas or use the zoom controls</p></div><GitBranch size={18} color="#7d9b9b" /></div><WorkflowVisualizer workflow={selected} /><div className="card-body" style={{ borderTop: "1px solid #edf1f5" }}><div className="workflow-number"><ShieldCheck size={17} />A HUMAN DECISION AT EVERY EXCEPTION</div><p className="help">This diagram reads the saved workflow definition. A matching invoice takes the completion path. Exceptions pause for manager approval before recording a review status.</p><p className="help">Execution progress is shown in Invoice Operations and Approvals.</p></div></section></div> : null}
  </>;
}
