"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, Check, CheckCircle2, Clock3, CloudOff, LoaderCircle, RefreshCw, RotateCcw, Scale, ShieldCheck, Sparkles, TriangleAlert, Unplug, X } from "lucide-react";
import { api, type AuditEvent, type Execution } from "@/lib/api";
import { dateLabel, issueLabel, reference, statusLabel } from "@/lib/format";
import { useWorkspace } from "./Workspace";
import { Loading, StatusBadge } from "./UI";
import ReasonAction from "./ReasonAction";

const stepName = (id: string) => id.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
const FAILURES: Record<string, { title: string; body: string; icon: typeof TriangleAlert }> = {
  AI_UNAVAILABLE: { title: "The AI service is temporarily unavailable.", body: "Gemini was busy or unreachable after three automatic attempts. Nothing was lost: completed steps are kept, and Retry continues from the investigation.", icon: CloudOff },
  AI_FAILED: { title: "The AI investigation didn’t produce a valid result.", body: "The response failed validation, so it was discarded. Retry asks again, or use Invoice Exception Review for a rules-only review.", icon: Sparkles },
  INTERRUPTED: { title: "This run was interrupted.", body: "The service stopped before this step finished, for example during a restart. Retry continues from the step that was interrupted.", icon: Unplug },
  UNEXPECTED: { title: "An unexpected error stopped this run.", body: "Completed steps are kept. Retry continues from the step that failed.", icon: TriangleAlert },
};
function FailurePanel({ execution, busy, onRetry }: { execution: Execution; busy: boolean; onRetry: () => void }) {
  const code = typeof execution.context.error_code === "string" ? execution.context.error_code : "UNEXPECTED";
  const info = FAILURES[code] ?? { title: "This step can’t complete with the current workflow or data.", body: execution.context.error ?? "Retrying won’t change the outcome. An admin can reopen it as a new run.", icon: TriangleAlert };
  const Icon = info.icon;
  const retry = execution.retry;
  return <div className={`notice ${code === "AI_UNAVAILABLE" || code === "INTERRUPTED" ? "warning" : "danger"}`} style={{ marginTop: 18 }}><Icon size={18} /><div>
    <strong>{info.title}</strong><p>{info.body}</p>
    {typeof execution.context.failed_step === "string" && <p className="subtle">Stopped at: {stepName(execution.context.failed_step)}{retry && retry.attempt_count > 0 ? ` · Retried ${retry.attempt_count} of ${retry.max_retries} times` : ""}</p>}
    {retry?.can_retry ? <button className="button small secondary" style={{ marginTop: 10 }} disabled={busy} onClick={onRetry}>{busy ? <LoaderCircle size={14} className="spin" /> : <RotateCcw size={14} />}{busy ? "Retrying…" : "Retry from this step"}</button>
      : retry && retry.attempt_count >= retry.max_retries ? <p className="subtle">Retry limit reached. An admin can reopen this as a new run.</p> : null}
  </div></div>;
}
const decisionWord = (decision?: string | null) => decision === "APPROVED" ? "Approved" : decision === "REJECTED" ? "Rejected" : "Pending";
export default function ExecutionDetails({ id, onOpen }: { id: string; onOpen?: (executionId: string) => void }) {
  const [execution, setExecution] = useState<Execution | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [action, setAction] = useState<string | null>(null);
  const { refresh, portal } = useWorkspace();
  const [panel, setPanel] = useState<"escalate" | "override" | "reopen" | null>(null);
  const [notice, setNotice] = useState("");
  async function governed(run: () => Promise<Execution>, message: string) {
    const result = await run();
    setPanel(null); setNotice(message);
    if (result.execution_id === id) { setExecution(result); setAudit(await api.getAudit(id)); }
    await refresh();
    return result;
  }
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
  async function retryRun() {
    if (action) return;
    setAction("retry"); setError(""); setNotice("");
    try {
      const result = await api.retryExecution(id);
      setExecution(result); setAudit(await api.getAudit(id)); await refresh();
      if (result.status !== "FAILED") setNotice("Retry succeeded. The run continued from the step that failed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed.");
      try { setExecution(await api.getExecution(id)); } catch { /* Keep the last verified state. */ }
    } finally { setAction(null); }
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
      {execution.status === "FAILED" && <FailurePanel execution={execution} busy={action === "retry"} onRetry={() => void retryRun()} />}
      {execution.status === "COMPLETED" && <div className="notice" style={{ marginTop: 18 }}><CheckCircle2 size={18} /><div><strong>{execution.context.valid === true ? "Invoice passed validation." : "Review decision recorded."}</strong><p>{execution.context.valid === true ? "No exception was found, so this workflow finished without approval." : "The invoice review status has been updated. Its amount is unchanged."}</p></div></div>}
      {execution.status === "REJECTED" && <div className="notice danger" style={{ marginTop: 18 }}><X size={18} /><div><strong>The exception was rejected.</strong><p>This execution did not apply the review-status action.</p></div></div>}
      {execution.context.discrepancy_percentage !== undefined && <div className="result-grid"><div><small>Amount discrepancy</small><strong>{Number(execution.context.discrepancy_percentage).toFixed(2)}%</strong></div><div><small>Policy threshold</small><strong>5.00%</strong></div></div>}
      {recommendation && <div className="recommendation"><div className="workflow-number"><Sparkles size={14} />GEMINI INVESTIGATION <span className={`badge ${recommendation.risk_level === "HIGH" ? "exception" : "valid"}`}>{recommendation.risk_level.toLowerCase()} risk</span></div><h3>{recommendation.summary}</h3><p>{recommendation.reasoning}</p><div className="action-label">Suggested action</div><p style={{ color: "#426f62", fontWeight: 600 }}>{recommendation.recommended_action.replaceAll("_", " ").toLowerCase()}</p></div>}
      {execution.status === "WAITING_APPROVAL" && execution.escalated_at && portal === "company" && <div className="notice" style={{ marginTop: 18 }}><ShieldCheck size={18} /><div><strong>Escalated to an admin.</strong><p>An administrator will record the decision for this exception.</p></div></div>}
      {execution.status === "WAITING_APPROVAL" && !(execution.escalated_at && portal === "company") && <div className="decision-card"><h3><ShieldCheck size={17} />{portal === "admin" ? "Admin decision" : "Your decision is needed"}</h3><p>Approve to mark the invoice as review approved, or reject this exception. This decision does not change amounts or send a payment.</p><div className="decision-actions"><button className="button primary" disabled={!!action} onClick={() => void decide("approve")}><Check size={15} />{action === "approve" ? "Recording…" : "Approve review"}</button><button className="button danger" disabled={!!action} onClick={() => void decide("reject")}><X size={15} />{action === "reject" ? "Recording…" : "Reject"}</button></div></div>}
      {execution.escalated_at && <div className="escalation-flag"><ArrowUpRight size={14} />Escalated to admin · {dateLabel(execution.escalated_at)}</div>}
      {execution.reopened_from && <p className="help">Reopened from run <button className="link-button" onClick={() => onOpen?.(execution.reopened_from!)}>{reference(execution.reopened_from)}</button>. The original run and its decision are unchanged.</p>}
      {notice && <div className="notice" role="status" style={{ marginTop: 18 }}><CheckCircle2 size={18} /><div><strong>{notice}</strong></div></div>}
      {execution.approval && execution.approval.status !== "PENDING" && <div className="decision-record">
        <h3 className="card-title"><Scale size={15} />Decision record</h3>
        <ol>
          <li><span className={`record-dot ${execution.approval.status === "APPROVED" ? "good" : "bad"}`} /><div><strong>{decisionWord(execution.approval.status)} by {execution.approval.decided_by ?? "unknown"}</strong><p>Original decision · {dateLabel(execution.approval.decided_at ?? undefined)}</p></div></li>
          {execution.overrides?.map((item) => <li key={item.id}><span className={`record-dot override ${item.new_decision === "APPROVED" ? "good" : "bad"}`} /><div><strong>Overridden to {decisionWord(item.new_decision).toLowerCase()} by {item.admin_email}</strong><p>Was {decisionWord(item.original_decision).toLowerCase()} · {dateLabel(item.created_at)}</p><blockquote>{item.reason}</blockquote></div></li>)}
        </ol>
        <p className="help">Effective decision: <strong>{decisionWord(execution.approval.effective_decision)}</strong>. Overrides are added to this record; earlier decisions are never edited.</p>
      </div>}
      {panel === null && <div className="governance-actions">
        {portal === "company" && execution.status === "WAITING_APPROVAL" && !execution.escalated_at && <button className="button secondary small" onClick={() => setPanel("escalate")}><ArrowUpRight size={14} />Escalate to admin</button>}
        {portal === "admin" && execution.approval && execution.approval.status !== "PENDING" && ["COMPLETED", "REJECTED"].includes(execution.status) && <button className="button secondary small" onClick={() => setPanel("override")}><Scale size={14} />Override decision</button>}
        {portal === "admin" && ["COMPLETED", "REJECTED", "FAILED"].includes(execution.status) && <button className="button secondary small" onClick={() => setPanel("reopen")}><RotateCcw size={14} />Reopen exception</button>}
      </div>}
      {panel === "escalate" && <ReasonAction title="Escalate to an admin" description="An administrator will make the final decision. You will no longer be able to approve or reject this exception." placeholder="Why does this need an admin decision?" confirmLabel="Escalate" onCancel={() => setPanel(null)} onConfirm={async (reason) => { await governed(() => api.escalate(id, reason), "Escalated. An admin will record the decision."); }} />}
      {panel === "override" && execution.approval && (() => { const toApprove = execution.approval.effective_decision === "REJECTED"; return <ReasonAction title={toApprove ? "Override to approve" : "Override to reject"} description={`The current decision (${decisionWord(execution.approval.effective_decision).toLowerCase()}) stays in the record. Your override, name, time, and reason are added beside it.`} placeholder="What evidence justifies changing this decision?" confirmLabel={toApprove ? "Record override: approve" : "Record override: reject"} tone={toApprove ? "primary" : "danger"} onCancel={() => setPanel(null)} onConfirm={async (reason) => { await governed(() => api.overrideDecision(id, toApprove ? "approve" : "reject", reason), "Override recorded. The original decision is preserved."); }} />; })()}
      {panel === "reopen" && <ReasonAction title="Reopen this exception" description="Starts a new run for the same invoice and returns it to the review queue. This run and its decision stay exactly as they are." placeholder="Why should this invoice be reviewed again?" confirmLabel="Reopen" onCancel={() => setPanel(null)} onConfirm={async (reason) => { const created = await governed(() => api.reopenExecution(id, reason), "Reopened. A new run was started for this invoice."); onOpen?.(created.execution_id); }} />}
      <h3 className="card-title" style={{ marginTop: 27 }}>Execution timeline</h3>
      {execution.steps.length === 0 ? <p className="help">No step result has been recorded yet.</p> : <ol className="timeline">{execution.steps.map((step) => <li key={step.step_id}><span className={`timeline-dot ${step.status === "WAITING_APPROVAL" ? "waiting" : step.status === "REJECTED" ? "rejected" : ""}`}>{step.status === "WAITING_APPROVAL" ? <Clock3 size={12} /> : step.status === "REJECTED" ? <X size={12} /> : <Check size={12} />}</span><div><strong>{stepName(step.step_id)}</strong><p>{statusLabel(step.status)}{Array.isArray(step.result.issues) && step.result.issues.length > 0 ? ` · ${(step.result.issues as string[]).map(issueLabel).join(", ")}` : ""}</p><details><summary>Step details</summary><pre>{JSON.stringify(step.result, null, 2)}</pre></details></div></li>)}</ol>}
      <details><summary>Audit history · {audit.length} recorded events</summary><div style={{ marginTop: 12 }}>{audit.map((event) => <div key={event.id} style={{ padding: "8px 0", borderTop: "1px solid #edf1f5" }}><strong>{event.event_type === "EXECUTION_STATE_CHANGED" ? `Status changed to ${statusLabel(String(event.payload.to))}` : event.event_type === "APPROVAL_DECIDED" ? `Review ${event.payload.decision === "approve" ? "approved" : "rejected"}` : event.event_type === "DECISION_OVERRIDDEN" ? `Decision overridden to ${String(event.payload.new_decision).toLowerCase()}` : event.event_type === "EXCEPTION_ESCALATED" ? "Escalated to admin" : event.event_type === "EXCEPTION_REOPENED" ? "Exception reopened" : event.event_type === "EXECUTION_RETRIED" ? `Retry ${String(event.payload.attempt)} started` : event.event_type === "STEP_COMPLETED" ? `${stepName(String(event.payload.step_id))} completed` : stepName(event.event_type.toLowerCase())}</strong><p>{typeof event.payload.actor_email === "string" ? `${event.payload.actor_email} · ` : ""}{dateLabel(event.created_at)}</p></div>)}</div></details>
      <p className="help" style={{ marginTop: 18 }}>Full execution reference: <span className="reference">{execution.execution_id}</span></p>
    </div>
  </section>;
}
