"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, CheckCircle2, Clock3, FileText, History, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { api, type ActivityEvent } from "@/lib/api";
import { useWorkspace } from "@/components/Workspace";
import { EmptyWorkspace, Loading, PageHeading } from "@/components/UI";
import StatusBar from "@/components/StatusBar";
import { dateLabel, eventLabel, money } from "@/lib/format";

export default function Overview() {
  const { invoices, runs, loading, error, base, user, updated } = useWorkspace();
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  useEffect(() => {
    let active = true;
    api.activity(7).then((rows) => { if (active) setActivity(rows); }).catch(() => { /* The feed is supplementary; the dashboard still works without it. */ });
    return () => { active = false; };
  }, [updated]);
  const openExceptions = invoices.filter((i) => i.validation?.valid === false && i.status === "pending");
  const waiting = runs.filter((r) => r.status === "WAITING_APPROVAL" && !r.escalated_at);
  const withAdmin = runs.filter((r) => r.status === "WAITING_APPROVAL" && r.escalated_at);
  const counts = useMemo(() => runs.reduce<Record<string, number>>((acc, r) => ({ ...acc, [r.status]: (acc[r.status] ?? 0) + 1 }), {}), [runs]);
  const metrics = [
    { label: "Invoices", value: invoices.length, icon: FileText, note: "Submitted by your company", tone: "" },
    { label: "Open exceptions", value: openExceptions.length, icon: TriangleAlert, note: "Outside the 5% tolerance", tone: "amber" },
    { label: "Awaiting your decision", value: waiting.length, icon: Clock3, note: "Paused for a person", tone: "amber" },
    { label: "With admin", value: withAdmin.length, icon: ArrowUpRight, note: "Escalated for a final call", tone: "accent" },
  ];
  return <div className="dashboard">
    <PageHeading eyebrow={user?.company_name ? user.company_name.toUpperCase() : "COMPANY PORTAL"} title="Your exceptions at a glance." description="Business rules check every invoice. AI explains the exceptions. Your team records the decision." action={<Link href={`${base}/invoices`} className="button primary">Open invoice queue <ArrowRight size={15} /></Link>} />
    <div className="metric-grid">{metrics.map(({ label, value, icon: Icon, note, tone }) => <div className="metric" key={label}><div className="metric-top"><span>{label}</span><Icon size={16} /></div><div className={`metric-value ${tone}`}>{loading || error ? "—" : value}</div><div className="metric-note">{note}</div></div>)}</div>
    {loading ? <Loading /> : invoices.length === 0 && !error ? <div className="card"><EmptyWorkspace /></div> : <>
      <div className="dash-row">
        <section className="card"><div className="card-header"><div><h2>Needs your attention</h2><p className="card-subtitle">Exceptions not yet decided</p></div><Link className="text-link" href={`${base}/invoices`}>View queue <ArrowRight size={13} /></Link></div>
          {openExceptions.length === 0 ? <div className="empty-small"><CheckCircle2 size={24} style={{ margin: "0 auto 10px", color: "#0ca30c" }} /><p>You’re all caught up. No open exceptions.</p></div> :
            <div className="table-wrap"><table><thead><tr><th>Supplier / invoice</th><th>Amount</th><th>Exception</th><th /></tr></thead><tbody>{openExceptions.slice(0, 5).map((invoice) => <tr key={invoice.id}><td><div className="supplier"><span className="supplier-avatar">{invoice.vendor_name?.split(" ").map((w) => w[0]).slice(0, 2).join("") ?? "SU"}</span><div><strong>{invoice.vendor_name ?? "Supplier"}</strong><small>{invoice.invoice_number ?? "No number"}</small></div></div></td><td className="number">{money(invoice.amount, invoice.currency)}</td><td><span className="badge exception">{invoice.validation?.issues.includes("AMOUNT_DISCREPANCY") ? `${Number(invoice.validation.discrepancy_percentage).toFixed(0)}% over PO` : "Vendor / currency"}</span></td><td><Link href={`${base}/invoices?invoice=${invoice.id}`} className="text-link">Review <ArrowRight size={12} /></Link></td></tr>)}</tbody></table></div>}
        </section>
        <StatusBar title="Review outcomes" caption="Every workflow run for your company" counts={counts} />
      </div>
      <div className="dash-row">
        <section className="card"><div className="card-header"><div><h2>Recent activity</h2><p className="card-subtitle">Who did what in your company</p></div><Link className="text-link" href={`${base}/activity`}>Activity log <ArrowRight size={12} /></Link></div>
          {activity.length === 0 ? <div className="empty-small"><p>No activity yet.</p></div> : activity.map((event) => <div key={event.id} className="activity-item"><span className="activity-icon"><History size={13} /></span><div><strong>{eventLabel(event)}</strong><p>{event.actor_email ?? "Workflow engine"}</p><time>{dateLabel(event.created_at)}</time></div></div>)}
        </section>
        <section className="card"><div className="card-header"><div><h2>How a decision is made</h2><p className="card-subtitle">The same path for every invoice</p></div><ShieldCheck size={16} color="#9daab8" /></div>
          <ol className="mini-steps">
            <li><span>1</span><div><strong>Rules check the facts</strong><p>Amount, vendor, and currency are compared with the purchase order. No AI involved.</p></div></li>
            <li><span>2</span><div><strong>AI explains exceptions</strong><p><Sparkles size={11} /> Gemini suggests an action. It cannot approve anything.</p></div></li>
            <li><span>3</span><div><strong>You decide</strong><p>Approve, reject, or escalate to an admin with a reason.</p></div></li>
            <li><span>4</span><div><strong>Everything is recorded</strong><p>Admins can override, but your original decision is never erased.</p></div></li>
          </ol>
        </section>
      </div>
    </>}
  </div>;
}
