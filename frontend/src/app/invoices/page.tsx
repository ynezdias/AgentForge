"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertCircle, Check, GitBranch, Play, RefreshCw, ShieldCheck, X } from "lucide-react";
import { api, type Execution, type Invoice, type Workflow } from "@/lib/api";

const panel = "rounded-xl border border-slate-800 bg-slate-900 p-6";
const control = "w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm focus-visible:outline-2 focus-visible:outline-blue-400 disabled:opacity-50";
const errorMessage = (error: unknown) => error instanceof Error ? error.message : "Request failed";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState("");
  const [selectedWorkflow, setSelectedWorkflow] = useState("");
  const [execution, setExecution] = useState<Execution | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [action, setAction] = useState<"run" | "approve" | "reject" | "refresh" | null>(null);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const pendingKey = useRef<string | null>(null);

  async function loadData() {
    setLoadingData(true);
    setError("");
    try {
      const [invoiceData, workflowData] = await Promise.all([api.getInvoices(), api.getWorkflows()]);
      setInvoices(invoiceData);
      setWorkflows(workflowData);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingData(false);
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([api.getInvoices(), api.getWorkflows()])
      .then(([invoiceData, workflowData]) => {
        if (!active) return;
        setInvoices(invoiceData);
        setWorkflows(workflowData);
      })
      .catch((err: unknown) => { if (active) setError(errorMessage(err)); })
      .finally(() => { if (active) setLoadingData(false); });
    return () => { active = false; };
  }, []);

  async function runWorkflow() {
    if (busy.current || !selectedInvoice || !selectedWorkflow) return;
    busy.current = true;
    setAction("run");
    setError("");
    setExecution(null);
    // A transport failure may follow a successful server insertion. Reuse the
    // key on the next try for these selections to avoid starting a second run.
    pendingKey.current ??= crypto.randomUUID();
    try {
      const result = await api.executeWorkflow(selectedWorkflow, selectedInvoice, pendingKey.current);
      setExecution(result);
      pendingKey.current = null;
    } catch (err) {
      setError(`${errorMessage(err)}. Trying again with the same selections reuses the request key.`);
    } finally {
      busy.current = false;
      setAction(null);
    }
  }

  async function refreshExecution() {
    if (!execution || busy.current) return;
    busy.current = true;
    setAction("refresh");
    setError("");
    try {
      setExecution(await api.getExecution(execution.execution_id));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      busy.current = false;
      setAction(null);
    }
  }

  async function handleDecision(decision: "approve" | "reject") {
    if (!execution || execution.status !== "WAITING_APPROVAL" || busy.current) return;
    busy.current = true;
    setAction(decision);
    setError("");
    let decisionRecorded = false;
    try {
      const result = await api.approveExecution(execution.execution_id, decision);
      decisionRecorded = true;
      // Hide decision controls immediately even if the following refresh fails.
      setExecution((previous) => previous ? { ...previous, status: result.status } : previous);
      setExecution(await api.getExecution(execution.execution_id));
      setInvoices(await api.getInvoices());
    } catch (err) {
      setError(`${decisionRecorded ? "Decision recorded, but the latest data could not be loaded. Refresh the execution. " : ""}${errorMessage(err)}`);
    } finally {
      busy.current = false;
      setAction(null);
    }
  }

  function clearRun() {
    setExecution(null);
    setError("");
    pendingKey.current = null;
  }

  const recommendation = execution?.context.ai_recommendation;
  const loading = action !== null;

  return (
    <main className="min-h-screen bg-slate-950 p-6 text-slate-100 md:p-10">
      <div className="mx-auto max-w-5xl">
        <nav aria-label="Page navigation" className="mb-8 flex gap-5 text-sm text-blue-400"><Link href="/">Dashboard</Link><Link href="/workflows">Workflow Visualization</Link></nav>
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-blue-400">Operations console</p>
        <h1 className="text-3xl font-bold tracking-tight">Invoice Operations</h1>
        <p className="mt-2 text-slate-400">Run AI-powered invoice exception workflows.</p>

        <section aria-labelledby="run-title" aria-busy={loadingData || action === "run"} className={`${panel} mt-8`}>
          <h2 id="run-title" className="mb-5 flex items-center gap-2 font-semibold"><GitBranch size={20} className="text-blue-400" />Start a workflow</h2>
          <div className="grid gap-5 md:grid-cols-2">
            <div><label htmlFor="invoice" className="mb-2 block text-sm text-slate-300">Select Invoice</label>
              <select id="invoice" value={selectedInvoice} disabled={loadingData || loading} onChange={(event) => { setSelectedInvoice(event.target.value); clearRun(); }} className={control}>
                <option value="">{loadingData ? "Loading invoices…" : "Choose an invoice"}</option>
                {invoices.map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.id.slice(0, 8)} — {invoice.currency} {Number(invoice.amount).toFixed(2)} · {invoice.status.replaceAll("_", " ")}</option>)}
              </select>
            </div>
            <div><label htmlFor="workflow" className="mb-2 block text-sm text-slate-300">Select Workflow</label>
              <select id="workflow" value={selectedWorkflow} disabled={loadingData || loading} onChange={(event) => { setSelectedWorkflow(event.target.value); clearRun(); }} className={control}>
                <option value="">{loadingData ? "Loading workflows…" : "Choose a workflow"}</option>
                {workflows.map((workflow) => <option key={workflow.id} value={workflow.id}>{workflow.name} · v{workflow.version}</option>)}
              </select>
            </div>
          </div>
          {!loadingData && (invoices.length === 0 || workflows.length === 0) && <p className="mt-4 text-sm text-slate-400">{invoices.length === 0 ? "No invoices are available. Add sample invoice data in the backend. " : ""}{workflows.length === 0 ? "No workflows are available. Create an AI invoice workflow in the backend to get started." : ""}</p>}
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <button onClick={() => void runWorkflow()} disabled={loading || loadingData || !selectedInvoice || !selectedWorkflow} className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"><Play size={16} />{action === "run" ? "Running workflow…" : "Run Workflow"}</button>
            <button onClick={() => void loadData()} disabled={loading || loadingData} className="text-sm text-slate-400 hover:text-white disabled:opacity-50">Reload lists</button>
            {action === "run" && <p role="status" className="text-sm text-slate-400">Validation and AI investigation may take a moment.</p>}
          </div>
        </section>

        {error && <div role="alert" className="mt-6 flex items-start gap-3 rounded-lg border border-red-800 bg-red-950 p-4 text-sm text-red-200"><AlertCircle size={18} className="mt-0.5 shrink-0" /><span className="break-all">{error}</span></div>}

        {execution && <section aria-label="Workflow execution" className="mt-8 space-y-6">
          <div className={panel}>
            <div className="flex items-center justify-between gap-4"><h2 className="text-xl font-semibold">Execution Result</h2><button aria-label="Refresh execution" onClick={() => void refreshExecution()} disabled={loading} className="rounded-lg border border-slate-700 p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-50"><RefreshCw size={16} className={action === "refresh" ? "animate-spin" : ""} /></button></div>
            <p className="mt-4 break-all font-mono text-xs text-slate-400">Execution: {execution.execution_id}</p>
            <p role="status" className="mt-3 text-sm">Status: <span className={`font-semibold ${execution.status === "FAILED" || execution.status === "REJECTED" ? "text-red-300" : execution.status === "COMPLETED" ? "text-emerald-300" : "text-blue-400"}`}>{execution.status}</span></p>
            {execution.context.discrepancy_percentage !== undefined && <p className="mt-3 text-sm text-slate-300">Discrepancy: {Number(execution.context.discrepancy_percentage).toFixed(2)}%</p>}
            {execution.context.issues && execution.context.issues.length > 0 && <p className="mt-3 text-sm text-amber-300">Issues: {execution.context.issues.join(", ")}</p>}
            {execution.context.valid === true && <p className="mt-3 text-sm text-emerald-300">Invoice validation passed.</p>}
            {execution.context.error && <p role="alert" className="mt-3 text-sm text-red-300">{execution.context.error}</p>}
            {(execution.status === "PENDING" || execution.status === "RUNNING") && <p className="mt-3 text-sm text-slate-400">Execution is in progress. Refresh to retrieve its latest status.</p>}
          </div>

          {recommendation && <div className={panel}>
            <h2 className="text-xl font-semibold">Gemini Investigation</h2>
            <p className="mt-4 leading-7">{recommendation.summary}</p>
            <div className="mt-5 flex flex-wrap gap-3 text-xs"><span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-amber-200">Risk: {recommendation.risk_level}</span><span className="rounded-full border border-slate-700 px-3 py-1.5 text-slate-300">Human review required</span></div>
            <p className="mt-5 text-sm"><span className="text-slate-400">Recommended action: </span>{recommendation.recommended_action.replaceAll("_", " ")}</p>
            <p className="mt-3 text-sm leading-7 text-slate-400">{recommendation.reasoning}</p>
          </div>}

          {execution.status === "WAITING_APPROVAL" && <div className={panel}>
            <h2 className="flex items-center gap-2 text-lg font-semibold"><ShieldCheck size={20} className="text-blue-400" />Manager review</h2>
            <p className="mt-3 text-sm leading-6 text-slate-400">Approval allows the workflow to record the invoice as review approved. It does not change the amount, send payment, or carry out the AI recommendation.</p>
            <div className="mt-5 flex flex-wrap gap-3"><button onClick={() => void handleDecision("approve")} disabled={loading} className="flex items-center gap-2 rounded-lg bg-emerald-700 px-5 py-3 text-sm font-medium hover:bg-emerald-600 disabled:opacity-50"><Check size={16} />{action === "approve" ? "Approving…" : "Approve"}</button><button onClick={() => void handleDecision("reject")} disabled={loading} className="flex items-center gap-2 rounded-lg bg-red-800 px-5 py-3 text-sm font-medium hover:bg-red-700 disabled:opacity-50"><X size={16} />{action === "reject" ? "Rejecting…" : "Reject"}</button></div>
            <p className="mt-4 text-xs text-slate-500">Local prototype · decisions use the development manager identity.</p>
          </div>}

          <div className={panel}>
            <h2 className="text-xl font-semibold">Execution History</h2><p className="mt-2 text-sm text-slate-400">Recorded steps for this execution, in workflow order.</p>
            {execution.steps.length === 0 ? <p className="mt-5 text-sm text-slate-500">No step results have been recorded.</p> : <ol className="mt-5 space-y-3">{execution.steps.map((step, index) => <li key={step.step_id} className="rounded-lg border border-slate-800 bg-slate-950/60 p-4"><div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span className="break-all font-medium"><span className="mr-3 text-slate-500">{index + 1}.</span>{step.step_id}</span><span className="text-xs text-blue-300">{step.status}</span></div><details className="mt-3 text-xs text-slate-400"><summary className="cursor-pointer hover:text-white">View step result</summary><pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all rounded bg-slate-950 p-3 leading-6">{JSON.stringify(step.result, null, 2)}</pre></details></li>)}</ol>}
          </div>
        </section>}
      </div>
    </main>
  );
}
