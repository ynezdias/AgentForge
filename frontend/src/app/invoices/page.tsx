"use client";
import { Suspense, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, CheckCircle2, FileText, LoaderCircle, Play, Search, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { useWorkspace } from "@/components/Workspace";
import { EmptyWorkspace, Loading, PageHeading, StatusBadge } from "@/components/UI";
import ExecutionDetails from "@/components/ExecutionDetails";
import { api } from "@/lib/api";
import { issueLabel, money, reference } from "@/lib/format";

function InvoiceQueue() {
  const { invoices, workflows, runs, loading, refresh, error: workspaceError } = useWorkspace();
  const params = useSearchParams();
  const router = useRouter();
  const [selectedId, setSelectedId] = useState(params.get("invoice") ?? "");
  const [workflowId, setWorkflowId] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All invoices");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<{ signature: string; key: string } | null>(null);
  const locked = useRef(false);
  const executionId = params.get("execution");
  const runInvoice = runs.find((run) => run.execution_id === executionId)?.invoice_id;
  const selected = invoices.find((invoice) => invoice.id === (params.get("invoice") ?? selectedId ?? runInvoice)) ?? invoices.find((invoice) => invoice.id === runInvoice);
  const chosenWorkflow = workflows.find((workflow) => workflow.id === workflowId) ?? workflows.find((workflow) => !workflow.definition?.steps.some((step) => step.tool === "invoice.investigate")) ?? workflows[0];
  const ai = chosenWorkflow?.definition?.steps.some((step) => step.tool === "invoice.investigate");
  const filtered = invoices.filter((invoice) => {
    const match = `${invoice.vendor_name} ${invoice.id} ${invoice.amount}`.toLowerCase().includes(search.toLowerCase());
    return match && (filter === "All invoices" || (filter === "Exceptions" && invoice.validation?.valid === false && invoice.status !== "review_approved") || (filter === "Reviewed" && invoice.status === "review_approved"));
  });
  function select(id: string) { if (running) return; setSelectedId(id); setError(""); request.current = null; router.replace(`/invoices?invoice=${id}`, { scroll: false }); }
  async function execute() {
    if (!selected || !chosenWorkflow || locked.current) return;
    locked.current = true; setRunning(true); setError("");
    const signature = `${selected.id}:${chosenWorkflow.id}`;
    if (request.current?.signature !== signature) request.current = { signature, key: crypto.randomUUID() };
    try {
      const result = await api.executeWorkflow(chosenWorkflow.id, selected.id, request.current!.key);
      request.current = null;
      router.replace(`/invoices?invoice=${selected.id}&execution=${result.execution_id}`, { scroll: false });
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not start the workflow. Try again."); }
    finally { locked.current = false; setRunning(false); }
  }
  return <>
    <PageHeading eyebrow="ACCOUNTS PAYABLE" title="Invoice queue" description="Find an exception, compare the details, and start a review." action={<span className="badge">{invoices.length} invoices</span>} />
    {loading ? <Loading /> : invoices.length === 0 && !workspaceError ? <div className="card"><EmptyWorkspace /></div> : <div className="invoice-grid">
      <div className="stack"><section className="card"><div className="toolbar"><div className="tabs" aria-label="Filter invoices">{["All invoices", "Exceptions", "Reviewed"].map((value) => <button className={`tab ${filter === value ? "active" : ""}`} key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value}</button>)}</div><label className="search"><Search size={15} /><input placeholder="Search suppliers or reference" aria-label="Search invoices" value={search} onChange={(event) => setSearch(event.target.value)} /></label></div>
        <div className="table-wrap"><table><thead><tr><th>Supplier / reference</th><th>Invoice amount</th><th>Validation</th><th /></tr></thead><tbody>{filtered.map((invoice) => <tr key={invoice.id} className={`select-row ${selected?.id === invoice.id ? "selected" : ""}`}><td><div className="supplier"><span className="supplier-avatar">{invoice.vendor_name?.split(" ").map((word) => word[0]).slice(0, 2).join("") ?? "SU"}</span><div><strong>{invoice.vendor_name ?? "Supplier"}</strong><small>{reference(invoice.id)}</small></div></div></td><td><div className="number">{money(invoice.amount, invoice.currency)}</div><small className="subtle">PO {money(invoice.purchase_order_amount, invoice.purchase_order_currency)}</small></td><td>{invoice.status === "review_approved" ? <StatusBadge status={invoice.status} /> : <span className={`badge ${invoice.validation?.valid === false ? "exception" : "valid"}`}><i />{invoice.validation?.valid === false ? "Exception" : "Matches PO"}</span>}</td><td><button disabled={running} onClick={() => select(invoice.id)} className="row-button" aria-label={`Review ${invoice.vendor_name ?? "supplier"} invoice ${reference(invoice.id)}`}>{selected?.id === invoice.id ? "Selected" : "Review"} <ArrowRight size={11} style={{ display: "inline" }} /></button></td></tr>)}</tbody></table></div>
        {filtered.length === 0 && <div className="empty-small">No invoices match this search.</div>}<div className="table-footer"><span>{filtered.length} of {invoices.length} invoices</span><span>Select an invoice to see its details</span></div></section>
        {executionId && <ExecutionDetails key={executionId} id={executionId} />}
      </div>
      <aside className="stack">{selected ? <section className="card"><div className="card-header"><h2>Invoice details</h2><FileText size={17} color="#8b9cad" /></div><div className="card-body"><div className="detail-heading"><span className="badge">USD supplier invoice</span><StatusBadge status={selected.status} /></div><h2 className="detail-title">{selected.vendor_name ?? "Supplier invoice"}</h2><p className="reference">Reference {reference(selected.id)}</p><div className="amount-pair"><div><span>Invoice total</span><strong>{money(selected.amount, selected.currency)}</strong></div><div><span>Purchase order</span><strong>{money(selected.purchase_order_amount, selected.purchase_order_currency)}</strong></div></div>
        <div className={`issues ${selected.validation?.valid ? "valid" : ""}`}><p>{selected.validation?.valid ? <CheckCircle2 size={14} /> : <TriangleAlert size={14} />}<strong>{selected.validation?.valid ? "Invoice matches the purchase order" : "This invoice needs review"}</strong></p>{selected.validation?.valid === false && <ul>{selected.validation.issues.map((issue) => <li key={issue}>{issueLabel(issue)}{issue === "AMOUNT_DISCREPANCY" ? ` · ${Number(selected.validation?.discrepancy_percentage).toFixed(2)}%` : ""}</li>)}</ul>}</div>
        <label htmlFor="workflow" className="field-label">Review workflow</label><select id="workflow" className="field" value={chosenWorkflow?.id ?? ""} disabled={running || workflows.length === 0} onChange={(event) => { setWorkflowId(event.target.value); request.current = null; }}><option value="" disabled>Choose a workflow</option>{workflows.map((workflow) => <option key={workflow.id} value={workflow.id}>{workflow.name}</option>)}</select>
        <p className="help" style={{ display: "flex", gap: 7 }}>{ai ? <Sparkles size={14} /> : <ShieldCheck size={14} />}{ai ? "Includes a live Gemini investigation. AI service access is required." : "Validates with business rules and routes exceptions to a manager. No AI call is made."}</p>
        <button className="button primary full" onClick={() => void execute()} disabled={running || !chosenWorkflow}>{running ? <LoaderCircle size={16} className="spin" /> : <Play size={15} />}{running ? ai ? "Investigating invoice…" : "Starting review…" : "Run review workflow"}</button>
        {error && <p role="alert" className="error-text" style={{ marginTop: 12 }}>{error} Try again with these selections to reuse the request key.</p>}
        <p className="help">Exceptions pause for a human decision. Passing invoices finish automatically.</p>
      </div></section> : <section className="card"><div className="empty-state"><span className="empty-icon"><FileText size={27} /></span><h2>Select an invoice</h2><p>Choose Review in the queue to compare it with its purchase order and start a workflow.</p></div></section>}
      <section className="card"><div className="card-body"><div className="workflow-number"><ShieldCheck size={16} />REVIEW WITH CONFIDENCE</div><p className="help" style={{ marginTop: 12 }}>Manager approval records the invoice as review approved. Invoice amounts and payment instructions stay unchanged.</p></div></section></aside>
    </div>}
  </>;
}
export default function InvoicesPage() { return <Suspense fallback={<Loading />}><InvoiceQueue /></Suspense>; }
