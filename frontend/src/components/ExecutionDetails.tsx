"use client";
import { useEffect, useState } from "react";
import { Check, CheckCircle2, Clock3, RefreshCw, ShieldCheck, Sparkles, TriangleAlert, X } from "lucide-react";
import { api, type AuditEvent, type Execution } from "@/lib/api";
import { dateLabel, issueLabel, reference, statusLabel } from "@/lib/format";
import { useWorkspace } from "./Workspace";
import { Loading, StatusBadge } from "./UI";

const stepName = (id: string) => id.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
export default function ExecutionDetails({ id }: { id: string }) {
  const [execution, setExecution] = useState<Execution | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [action, setAction] = useState<string | null>(null);
  const { refresh } = useWorkspace();
  useEffect(() => {
    let active = true;
    Promise.all([api.getExecution(id), api.getAudit(id)])
      .then(([result, events]) => { if (active) { setExecution(result); setAudit(events); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not retrieve this execution."); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => {
    if (execution?.status !== "PENDING" && execution?.status !== "RUNNING") return;
    let active = true;
    const timer = setInterval(() => {
      Promise.all([api.getExecution(id), api.getAudit(id)])
        .then(([result, events]) => { if (active) { setExecution(result); setAudit(events); if (!["PENDING", "RUNNING"].includes(result.status)) void refresh(); } })
        .catch(() => { if (active) setError("Status could not update. Use Refresh to try again."); });
    }, 4000);
    return () => { active = false; clearInterval(timer); };
  }, [id, execution?.status, refresh]);
  async function reload() {
    setAction("refresh"); setError("");
    try { const [result, events] = await Promise.all([api.getExecution(id), api.getAudit(id)]); setExecution(result); setAudit(events); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Refresh failed."); }
    finally { setAction(null); }
  }
  async function decide(decision: "approve" | "reject") {
    if (action || execution?.status !== "WAITING_APPROVAL") return;
    setAction(decision); setError("");
    let saved = false;
    try {
      const result = await api.approveExecution(id, decision);
      saved = true; setExecution(result);
      await refresh(); setAudit(await api.getAudit(id));
    } catch (err) {
      setError(`${saved ? "Your decision was saved, but its history could not refresh. " : ""}${err instanceof Error ? err.message : "Could not record the decision."}`);
      try { setExecution(await api.getExecution(id)); } catch { /* Keep the last verified state and the error visible. */ }
    } finally { setAction(null); }
  }
  if (!execution) return <section className="card"><div className="card-header"><h2>Execution details</h2></div>{error ? <div className="card-body"><p role="alert" className="error-text">{error}</p><button className="button secondary small" onClick={() => void reload()} disabled={!!action}>Try again</button></div> : <Loading text="Retrieving execution history…" />}</section>;
  const recommendation = execution.context.ai_recommendation;
  return <section className="card" aria-label="Execution details">
    <div className="card-header"><div><h2>{execution.workflow_name ?? "Workflow execution"}</h2><p className="card-subtitle">Run {reference(execution.execution_id)} · {dateLabel(execution.created_at)}</p></div><button className="icon-button" aria-label="Refresh execution" disabled={!!action} onClick={() => void reload()}><RefreshCw size={15} className={action === "refresh" ? "spin" : ""} /></button></div>
    <div className="card-body">
      <div className="run-summary"><StatusBadge status={execution.status} /><span className="subtle">{execution.steps.length} recorded steps</span></div>
      {error && <p role="alert" className="error-text" style={{ marginTop: 14 }}>{error}</p>}
      {execution.status === "FAILED" && <div className="notice danger" style={{ marginTop: 18 }}><TriangleAlert size={18} /><div><strong>{execution.context.error?.includes("AI") ? "The AI investigation couldn’t complete." : "This workflow needs attention."}</strong><p>{execution.context.error?.includes("AI") ? "No recommendation was produced. You can select Invoice Exception Review for a rules-based review, or retry the AI workflow after its connection is fixed." : execution.context.error ?? "Check the recorded steps and try again."}</p></div></div>}
      {execution.status === "COMPLETED" && <div className="notice" style={{ marginTop: 18 }}><CheckCircle2 size={18} /><div><strong>{execution.context.valid === true ? "Invoice passed validation." : "Review decision recorded."}</strong><p>{execution.context.valid === true ? "No exception was found, so this workflow finished without approval." : "The invoice review status has been updated. Its amount is unchanged."}</p></div></div>}
      {execution.status === "REJECTED" && <div className="notice danger" style={{ marginTop: 18 }}><X size={18} /><div><strong>The exception was rejected.</strong><p>This execution did not apply the review-status action.</p></div></div>}
      {execution.context.discrepancy_percentage !== undefined && <div className="result-grid"><div><small>Amount discrepancy</small><strong>{Number(execution.context.discrepancy_percentage).toFixed(2)}%</strong></div><div><small>Policy threshold</small><strong>5.00%</strong></div></div>}
      {recommendation && <div className="recommendation"><div className="workflow-number"><Sparkles size={14} />GEMINI INVESTIGATION <span className={`badge ${recommendation.risk_level === "HIGH" ? "exception" : "valid"}`}>{recommendation.risk_level.toLowerCase()} risk</span></div><h3>{recommendation.summary}</h3><p>{recommendation.reasoning}</p><div className="action-label">Suggested action</div><p style={{ color: "#426f62", fontWeight: 600 }}>{recommendation.recommended_action.replaceAll("_", " ").toLowerCase()}</p></div>}
      {execution.status === "WAITING_APPROVAL" && <div className="decision-card"><h3><ShieldCheck size={17} />Your decision is needed</h3><p>Approve to mark the invoice as review approved, or reject this exception. This decision does not change amounts or send a payment.</p><div className="decision-actions"><button className="button primary" disabled={!!action} onClick={() => void decide("approve")}><Check size={15} />{action === "approve" ? "Recording…" : "Approve review"}</button><button className="button danger" disabled={!!action} onClick={() => void decide("reject")}><X size={15} />{action === "reject" ? "Recording…" : "Reject"}</button></div></div>}
      <h3 className="card-title" style={{ marginTop: 27 }}>Execution timeline</h3>
      {execution.steps.length === 0 ? <p className="help">No step result has been recorded yet.</p> : <ol className="timeline">{execution.steps.map((step) => <li key={step.step_id}><span className={`timeline-dot ${step.status === "WAITING_APPROVAL" ? "waiting" : ""}`}>{step.status === "WAITING_APPROVAL" ? <Clock3 size={12} /> : <Check size={12} />}</span><div><strong>{stepName(step.step_id)}</strong><p>{statusLabel(step.status)}{Array.isArray(step.result.issues) && step.result.issues.length > 0 ? ` · ${(step.result.issues as string[]).map(issueLabel).join(", ")}` : ""}</p><details><summary>Step details</summary><pre>{JSON.stringify(step.result, null, 2)}</pre></details></div></li>)}</ol>}
      <details><summary>Audit history · {audit.length} recorded events</summary><div style={{ marginTop: 12 }}>{audit.map((event) => <div key={event.id} style={{ padding: "8px 0", borderTop: "1px solid #edf1f5" }}><strong>{event.event_type === "EXECUTION_STATE_CHANGED" ? `Status changed to ${statusLabel(String(event.payload.to))}` : event.event_type === "APPROVAL_DECIDED" ? `Manager ${event.payload.decision === "approve" ? "approved" : "rejected"} the review` : event.event_type === "STEP_COMPLETED" ? `${stepName(String(event.payload.step_id))} completed` : stepName(event.event_type.toLowerCase())}</strong><p>{dateLabel(event.created_at)}</p></div>)}</div></details>
      <p className="help" style={{ marginTop: 18 }}>Full execution reference: <span className="reference">{execution.execution_id}</span></p>
    </div>
  </section>;
}
