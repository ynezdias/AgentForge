"use client";
import { useState } from "react";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import { useWorkspace } from "@/components/Workspace";
import { Loading, PageHeading, StatusBadge } from "@/components/UI";
import ExecutionDetails from "@/components/ExecutionDetails";
import { dateLabel, money, reference } from "@/lib/format";

export default function ApprovalsPage() {
  const { runs, invoices, loading } = useWorkspace();
  const [selectedId, setSelectedId] = useState("");
  const [history, setHistory] = useState(false);
  const waiting = runs.filter((run) => run.status === "WAITING_APPROVAL");
  const items = history ? runs.filter((run) => run.context.approved !== undefined) : waiting;
  const chosenId = selectedId || items[0]?.execution_id;
  return <><PageHeading eyebrow="HUMAN IN THE LOOP" title="The final call is yours." description="Review the evidence and record a decision for each invoice exception." action={<span className="badge exception">{waiting.length} waiting for review</span>} />
    {loading ? <Loading /> : <div className="approval-grid"><section className="card"><div className="toolbar"><div className="tabs"><button className={`tab ${!history ? "active" : ""}`} aria-pressed={!history} onClick={() => { setHistory(false); setSelectedId(""); }}>Awaiting review ({waiting.length})</button><button className={`tab ${history ? "active" : ""}`} aria-pressed={history} onClick={() => { setHistory(true); setSelectedId(""); }}>Past decisions</button></div></div>{items.length === 0 ? <div className="empty-small"><CheckCircle2 size={28} style={{ color: "#56a58a", margin: "0 auto 12px" }} /><p>{history ? "No review decisions have been recorded yet." : "Your review queue is clear."}</p><p className="help">Invoice exceptions appear here when a workflow requests approval.</p></div> : items.map((run) => { const invoice = invoices.find((item) => item.id === run.invoice_id); return <button key={run.execution_id} className={`approval-item ${chosenId === run.execution_id ? "selected" : ""}`} onClick={() => setSelectedId(run.execution_id)}><StatusBadge status={run.status} /><h3>{invoice?.vendor_name ?? "Supplier invoice"} {invoice && <span style={{ float: "right" }}>{money(invoice.amount, invoice.currency)}</span>}</h3><p>{run.workflow_name}</p><p style={{ marginTop: 6 }}>{run.invoice_id ? reference(run.invoice_id) : "—"} · {dateLabel(run.created_at)}</p></button>; })}</section>{chosenId ? <ExecutionDetails key={chosenId} id={chosenId} /> : <section className="card"><div className="empty-state"><span className="empty-icon"><ShieldCheck size={29} /></span><h2>Decisions backed by evidence.</h2><p>Select a review request to see its validation findings, available AI recommendation, and recorded workflow history.</p></div></section>}</div>}
  </>;
}
