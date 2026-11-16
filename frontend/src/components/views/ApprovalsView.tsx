"use client";
import { useState } from "react";
import { ArrowUpRight, CheckCircle2, ShieldCheck } from "lucide-react";
import { useWorkspace } from "@/components/Workspace";
import { Loading, PageHeading, StatusBadge } from "@/components/UI";
import ExecutionDetails from "@/components/ExecutionDetails";
import type { WorkflowRun } from "@/lib/api";
import { dateLabel, invoiceDateLabel, money, reference } from "@/lib/format";

type Tab = { key: string; label: string; filter: (run: WorkflowRun) => boolean; empty: string };
const waiting = (run: WorkflowRun) => run.status === "WAITING_APPROVAL";
const decided = (run: WorkflowRun) => run.context.approved !== undefined && ["COMPLETED", "REJECTED"].includes(run.status);
const TABS: Record<"admin" | "company", Tab[]> = {
  admin: [
    { key: "escalated", label: "Escalated", filter: (r) => waiting(r) && !!r.escalated_at, empty: "No exceptions are escalated to an admin." },
    { key: "waiting", label: "Awaiting decision", filter: waiting, empty: "No exceptions are waiting for a decision." },
    { key: "decided", label: "Decided", filter: decided, empty: "No decisions have been recorded yet." },
    { key: "failed", label: "Needs attention", filter: (r) => r.status === "FAILED", empty: "No failed runs. Nothing needs recovery." },
  ],
  company: [
    { key: "waiting", label: "Awaiting review", filter: (r) => waiting(r) && !r.escalated_at, empty: "Your review queue is clear." },
    { key: "escalated", label: "With admin", filter: (r) => waiting(r) && !!r.escalated_at, empty: "Nothing is escalated to an admin." },
    { key: "decided", label: "Past decisions", filter: decided, empty: "No review decisions have been recorded yet." },
  ],
};

export default function ApprovalsView() {
  const { runs, invoices, loading, portal } = useWorkspace();
  const tabs = TABS[portal];
  const [tabKey, setTabKey] = useState(tabs[0].key);
  const [selectedId, setSelectedId] = useState("");
  const tab = tabs.find((t) => t.key === tabKey) ?? tabs[0];
  const items = runs.filter(tab.filter);
  const chosenId = selectedId || items[0]?.execution_id;
  const pending = runs.filter(waiting).length;
  return <><PageHeading
    eyebrow={portal === "admin" ? "ADMIN DECISIONS" : "HUMAN IN THE LOOP"}
    title={portal === "admin" ? "Decide, override, or reopen." : "The final call is yours."}
    description={portal === "admin" ? "Escalations come first. Every override keeps the original decision and records your reason." : "Review the evidence and record a decision for each invoice exception, or escalate it to an admin."}
    action={<span className="badge exception">{pending} waiting for a decision</span>} />
    {loading ? <Loading /> : <div className="approval-grid"><section className="card"><div className="toolbar"><div className="tabs" role="tablist">{tabs.map((t) => { const count = runs.filter(t.filter).length; return <button key={t.key} role="tab" className={`tab ${t.key === tab.key ? "active" : ""}`} aria-selected={t.key === tab.key} onClick={() => { setTabKey(t.key); setSelectedId(""); }}>{t.label} <span className="tab-count">{count}</span></button>; })}</div></div>
      {items.length === 0 ? <div className="empty-small"><CheckCircle2 size={28} style={{ color: "#56a58a", margin: "0 auto 12px" }} /><p>{tab.empty}</p><p className="help">Exceptions appear here when a workflow requests approval.</p></div> : items.map((run) => { const invoice = invoices.find((item) => item.id === run.invoice_id); return <button key={run.execution_id} className={`approval-item ${chosenId === run.execution_id ? "selected" : ""}`} onClick={() => setSelectedId(run.execution_id)}>
        <div className="approval-item-top"><StatusBadge status={run.status} />{run.escalated_at && <span className="badge escalated"><ArrowUpRight size={10} />Escalated</span>}</div>
        <h3>{invoice?.vendor_name ?? "Supplier invoice"} {invoice && <span className="number" style={{ float: "right" }}>{money(invoice.amount, invoice.currency)}</span>}</h3>
        <p>{invoice?.invoice_number ?? (run.invoice_id ? reference(run.invoice_id) : "—")} · {run.workflow_name}</p>
        <p>Due {invoiceDateLabel(invoice?.due_date)} · Run {dateLabel(run.created_at)}</p>
      </button>; })}</section>
      {chosenId ? <ExecutionDetails key={chosenId} id={chosenId} onOpen={setSelectedId} /> : <section className="card"><div className="empty-state"><span className="empty-icon"><ShieldCheck size={29} /></span><h2>Decisions backed by evidence.</h2><p>Select an item to see its validation findings, the AI recommendation, and the full decision record.</p></div></section>}</div>}
  </>;
}
