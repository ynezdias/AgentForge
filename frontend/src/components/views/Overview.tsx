"use client";
import Link from "next/link";
import { Activity, ArrowRight, CheckCircle2, Clock3, FileText, GitBranch, ShieldCheck, TriangleAlert } from "lucide-react";
import { useWorkspace } from "@/components/Workspace";
import { EmptyWorkspace, Loading, PageHeading, StatusBadge } from "@/components/UI";
import { dateLabel, money, reference } from "@/lib/format";

export default function Overview() {
  const { invoices, workflows, runs, loading, error, base } = useWorkspace();
  const exceptions = invoices.filter((invoice) => invoice.validation?.valid === false && invoice.status !== "review_approved");
  const waiting = runs.filter((run) => run.status === "WAITING_APPROVAL");
  const metrics = [
    { label: "Invoices in workspace", value: invoices.length, icon: FileText, note: "Ready for validation", color: "" },
    { label: "Open exceptions", value: exceptions.length, icon: TriangleAlert, note: "Outside your invoice policy", color: "amber" },
    { label: "Awaiting approval", value: waiting.length, icon: Clock3, note: "Waiting on a human decision", color: "amber" },
    { label: "Review approved", value: invoices.filter((invoice) => invoice.status === "review_approved").length, icon: CheckCircle2, note: "Reviewed by your team", color: "teal" },
  ];
  return <>
    <PageHeading eyebrow="YOUR DAILY OVERVIEW" title="A clear view of every exception." description="Keep invoices moving, with the right checks and a human in the loop." action={<Link href={`${base}/invoices`} className="button primary">Open invoice queue <ArrowRight size={15} /></Link>} />
    <div className="metric-grid">{metrics.map(({ label, value, icon: Icon, note, color }) => <div className="metric" key={label}><div className="metric-top"><span>{label}</span><Icon size={17} /></div><div className={`metric-value ${color}`}>{loading || error ? "—" : value}</div><div className="metric-note">{note}</div></div>)}</div>
    {loading ? <Loading /> : invoices.length === 0 && !error ? <div className="card"><EmptyWorkspace /></div> : <>
      <section className="hero"><div><h2>Automation handles the checks.<br />Your team makes the call.</h2><p>Compare invoices with purchase orders, investigate discrepancies, and record a decision in one place.</p><div className="hero-note"><ShieldCheck size={14} />5% amount tolerance · Manager approval for exceptions</div></div><Link className="button secondary" href={`${base}/workflows`}>See how it works <ArrowRight size={14} /></Link></section>
      <div className="content-grid"><section className="card"><div className="card-header"><div><h2>Needs your attention</h2><p className="card-subtitle">Invoice exceptions still awaiting review</p></div><Link className="text-link" href={`${base}/invoices`}>View queue <ArrowRight size={13} /></Link></div>
        {exceptions.length === 0 ? <div className="empty-small"><CheckCircle2 size={25} style={{ margin: "0 auto 10px", color: "#58a48a" }} /><p>You’re all caught up. No open invoice exceptions.</p></div> : <div className="table-wrap"><table><thead><tr><th>Supplier / reference</th><th>Invoice</th><th>Exception</th><th /></tr></thead><tbody>{exceptions.slice(0, 5).map((invoice) => <tr key={invoice.id}><td><div className="supplier"><span className="supplier-avatar">{invoice.vendor_name?.split(" ").map((word) => word[0]).slice(0, 2).join("") ?? "SU"}</span><div><strong>{invoice.vendor_name ?? "Supplier"}</strong><small>{reference(invoice.id)}</small></div></div></td><td className="number">{money(invoice.amount, invoice.currency)}</td><td><span className="badge exception">{invoice.validation?.issues.includes("AMOUNT_DISCREPANCY") ? `${Number(invoice.validation.discrepancy_percentage).toFixed(0)}% discrepancy` : "Vendor / currency"}</span></td><td><Link aria-label={`Review invoice ${reference(invoice.id)}`} href={`${base}/invoices?invoice=${invoice.id}`} className="text-link">Review <ArrowRight size={12} /></Link></td></tr>)}</tbody></table></div>}<div className="table-footer"><span>{exceptions.length} open exceptions in loaded invoices</span><span>Human review required</span></div>
      </section><section className="card"><div className="card-header"><div><h2>Recent activity</h2><p className="card-subtitle">Your latest workflow executions</p></div><Activity size={17} color="#9daab8" /></div>{runs.length === 0 ? <div className="empty-small"><p>No workflows have run yet.</p><Link className="text-link" href={`${base}/invoices`}>Review your first invoice <ArrowRight size={12} /></Link></div> : runs.slice(0, 5).map((run) => <Link key={run.execution_id} href={`${base}/invoices?execution=${run.execution_id}`} className="activity-item"><span className="activity-icon"><GitBranch size={14} /></span><div><strong>{run.workflow_name ?? "Invoice review"}</strong><p>Invoice {run.invoice_id ? reference(run.invoice_id) : "—"}</p><StatusBadge status={run.status} /><time>{dateLabel(run.created_at)}</time></div></Link>)}</section></div>
      <section className="card" style={{ marginTop: 24 }}><div className="process-steps">{[{ n: "01", title: "Validate", body: "Compare vendor, currency, and amount." }, { n: "02", title: "Investigate", body: "Use Gemini when you select an AI workflow." }, { n: "03", title: "Review", body: "A manager approves or rejects exceptions." }, { n: "04", title: "Record", body: "Save the result and its audit history." }].map((item) => <div className="process-step" key={item.n}><strong><span style={{ color: "#9eb1bf", marginRight: 8 }}>{item.n}</span>{item.title}</strong>{item.body}</div>)}</div></section>
      <p className="help">{invoices.length} invoices · {workflows.length} workflows · {runs.length} recent executions loaded. Lists show up to 100 records.</p>
    </>}
  </>;
}
