"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, AlertCircle, ArrowUpRight, Box, FileText, GitBranch, LayoutDashboard, RefreshCw, ShieldCheck } from "lucide-react";
import { api, type Invoice, type Workflow } from "@/lib/api";

export default function Dashboard() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const [invoiceData, workflowData] = await Promise.all([api.getInvoices(), api.getWorkflows()]);
      setInvoices(invoiceData);
      setWorkflows(workflowData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
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
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load dashboard");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const stats = [
    { label: "Invoices", value: invoices.length, icon: FileText, note: "Invoice records loaded" },
    { label: "Workflows", value: workflows.length, icon: GitBranch, note: "Workflow definitions loaded" },
    { label: "Pending invoices", value: invoices.filter((invoice) => invoice.status === "pending").length, icon: Activity, note: "Awaiting review or processing" },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60 p-6 md:flex">
          <div className="mb-12 flex items-center gap-3 text-xl font-bold tracking-tight">
            <span className="rounded-xl bg-blue-500 p-2"><Box size={23} aria-hidden="true" /></span>AgentForge
          </div>
          <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Workspace</p>
          <nav aria-label="Main navigation" className="space-y-2 text-sm">
            <Link href="/" aria-current="page" className="flex items-center gap-3 rounded-lg border border-blue-500/20 bg-blue-500/10 px-3 py-3 font-medium text-blue-400"><LayoutDashboard size={18} />Dashboard</Link>
            {[{ label: "Invoices", href: "/invoices", icon: FileText }, { label: "Workflows", href: "/workflows", icon: GitBranch }].map(({ label, href, icon: Icon }) => (
              <Link key={label} href={href} className="flex items-center gap-3 rounded-lg px-3 py-3 text-slate-400 hover:bg-slate-800 hover:text-white"><Icon size={18} />{label}</Link>
            ))}
          </nav>
          <p className="mt-4 px-3 text-xs leading-5 text-slate-500">Run workflows and review approvals in Invoice Operations.</p>
          <div className="mt-auto border-t border-slate-800 pt-6 text-xs text-slate-500"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-blue-400" />Local development</div>
        </aside>

        <main className="min-w-0 flex-1">
          <div className="flex h-16 items-center justify-between border-b border-slate-800 px-6 text-xs text-slate-500 md:px-10">
            <span><span className="text-slate-300">Operations console</span><span className="mx-3">/</span>Overview</span>
            <span className="rounded-md border border-slate-800 px-2 py-1 uppercase tracking-widest">Development</span>
          </div>
          <div className="mx-auto max-w-7xl p-6 md:p-10 lg:p-12">
            <nav aria-label="Mobile navigation" className="mb-6 flex gap-5 text-sm text-blue-400 md:hidden"><Link href="/" aria-current="page">Dashboard</Link><Link href="/invoices">Invoices</Link><Link href="/workflows">Workflows</Link></nav>
            <header className="mb-10 flex items-start justify-between gap-4">
              <div><p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-blue-400">Workspace overview</p>
                <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Operations Dashboard</h1>
                <p className="mt-3 text-sm leading-6 text-slate-400">Monitor invoices and automation workflows.</p>
              </div>
              <button onClick={() => void loadData()} disabled={loading} className="mt-1 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-400 disabled:opacity-50" aria-label="Refresh dashboard">
                <RefreshCw size={16} className={loading ? "animate-spin" : ""} /><span className="hidden sm:inline">Refresh</span>
              </button>
            </header>

            {error && <div role="alert" className="mb-6 flex items-start gap-3 rounded-lg border border-red-800 bg-red-950/60 p-4 text-sm text-red-200"><AlertCircle size={18} className="mt-0.5 shrink-0" /><div><p className="font-medium">Couldn’t load dashboard data</p><p className="mt-1 break-all text-red-300">{error}</p><p className="mt-2">Check the backend connection, then select Refresh.</p></div></div>}

            <div aria-busy={loading} className="mb-10 grid gap-5 sm:grid-cols-3">
              {stats.map((stat) => <div key={stat.label} className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                <div className="mb-6 flex items-center justify-between"><span className="rounded-lg border border-blue-400/15 bg-blue-400/10 p-2 text-blue-400"><stat.icon size={20} /></span><ArrowUpRight size={16} className="text-slate-600" aria-hidden="true" /></div>
                <p className="text-sm text-slate-400">{stat.label}</p><p className="mt-2 text-4xl font-semibold tracking-tight">{loading || error ? "—" : stat.value}</p><p className="mt-3 text-xs text-slate-500">{stat.note}</p>
              </div>)}
            </div>

            <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60" aria-labelledby="invoices-title" aria-busy={loading}>
              <div className="flex items-center justify-between gap-3 border-b border-slate-800 p-6"><div className="flex items-center gap-3"><ShieldCheck size={21} className="text-blue-400" /><h2 id="invoices-title" className="text-lg font-semibold">Recent Invoices</h2></div><span className="text-xs text-slate-500">Live backend data</span></div>
              {loading ? <p role="status" className="p-8 text-sm text-slate-400">Loading invoices…</p>
                : error ? <p className="p-8 text-sm text-slate-400">Invoice data is unavailable.</p>
                : invoices.length === 0 ? <div className="flex flex-col items-center px-6 py-16 text-center"><FileText size={30} className="mb-4 text-slate-600" /><h3 className="text-sm font-medium text-slate-200">No invoices found</h3><p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">Invoices will appear here when records are added to AgentForge.</p></div>
                : <div className="overflow-x-auto px-6"><table className="w-full text-left text-sm"><thead className="text-xs uppercase tracking-wider text-slate-500"><tr><th scope="col" className="py-4 font-medium">Invoice ID</th><th scope="col" className="py-4 font-medium">Amount</th><th scope="col" className="py-4 font-medium">Status</th></tr></thead><tbody>
                  {invoices.map((invoice) => <tr key={invoice.id} className="border-t border-slate-800"><td className="py-5 pr-4 font-mono text-xs text-slate-300" title={invoice.id}>{invoice.id.slice(0, 8)}…</td><td className="whitespace-nowrap py-5 pr-4 tabular-nums">{invoice.currency} {Number(invoice.amount).toFixed(2)}</td><td className="py-5"><span className={`inline-flex rounded-full border px-2.5 py-1 text-xs ${invoice.status === "pending" ? "border-amber-400/20 bg-amber-400/10 text-amber-300" : invoice.status === "review_approved" ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-slate-700 bg-slate-800 text-slate-300"}`}>{invoice.status.replaceAll("_", " ")}</span></td></tr>)}
                </tbody></table></div>}
            </section>
            <p className="mt-5 text-xs text-slate-500">Counts reflect the records loaded from the backend (up to 100 per list).</p>
          </div>
        </main>
      </div>
    </div>
  );
}
