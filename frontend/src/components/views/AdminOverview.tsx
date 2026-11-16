"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Building2, Clock3, History, Scale, TriangleAlert } from "lucide-react";
import { api, type ActivityEvent, type AdminOverview as Overview, type CompanySummary } from "@/lib/api";
import { useWorkspace } from "@/components/Workspace";
import { EmptyWorkspace, Loading, PageHeading } from "@/components/UI";
import StatusBar from "@/components/StatusBar";
import { dateLabel, eventLabel, money, reference } from "@/lib/format";

export default function AdminOverview() {
  const { invoices, runs, loading: workspaceLoading, error: workspaceError, updated } = useWorkspace();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api.adminOverview(), api.adminCompanies(), api.activity(8)])
      .then(([o, c, a]) => { if (active) { setOverview(o); setCompanies(c); setActivity(a); setError(""); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not load oversight data."); });
    return () => { active = false; };
  }, [updated]);
  const escalated = runs.filter((run) => run.status === "WAITING_APPROVAL" && run.escalated_at);
  const companyName = (id?: string | null) => companies.find((c) => c.id === id)?.name ?? "Unassigned";
  const metrics = [
    { label: "Companies", value: overview?.companies, icon: Building2, note: "Organisations using AgentForge", tone: "" },
    { label: "Awaiting decision", value: overview?.pending_approvals, icon: Clock3, note: "Across every company", tone: "amber" },
    { label: "Escalated to you", value: overview?.escalated_pending, icon: TriangleAlert, note: "Only an admin can decide these", tone: "amber" },
    { label: "Overrides recorded", value: overview?.overrides, icon: Scale, note: "Original decisions kept", tone: "accent" },
  ];
  return <div className="dashboard">
    <PageHeading eyebrow="ADMIN OVERSIGHT" title="Every company, every decision." description="Watch company activity, take over escalations, and correct decisions with a recorded reason." action={<Link href="/admin/approvals" className="button primary">Open decisions <ArrowRight size={15} /></Link>} />
    {error && <p role="alert" className="error-text" style={{ marginBottom: 16 }}>{error}</p>}
    <div className="metric-grid">{metrics.map(({ label, value, icon: Icon, note, tone }) => <div className="metric" key={label}><div className="metric-top"><span>{label}</span><Icon size={16} /></div><div className={`metric-value ${tone}`}>{value ?? "—"}</div><div className="metric-note">{note}</div></div>)}</div>
    {workspaceLoading ? <Loading /> : invoices.length === 0 && !workspaceError ? <div className="card"><EmptyWorkspace /></div> : <>
      <div className="dash-row">
        <section className="card"><div className="card-header"><div><h2>Escalated to admin</h2><p className="card-subtitle">Company users handed these to you. They cannot decide them.</p></div><Link className="text-link" href="/admin/approvals">Decide <ArrowRight size={12} /></Link></div>
          {escalated.length === 0 ? <div className="empty-small"><p>No escalations. Companies are handling their own exceptions.</p></div> :
            <div className="table-wrap"><table><thead><tr><th>Invoice</th><th>Company</th><th>Amount</th><th>Escalated</th></tr></thead><tbody>{escalated.slice(0, 6).map((run) => { const invoice = invoices.find((i) => i.id === run.invoice_id); return <tr key={run.execution_id}><td><strong>{invoice?.vendor_name ?? "Supplier"}</strong><small className="reference" style={{ display: "block" }}>{invoice?.invoice_number ?? reference(run.execution_id)}</small></td><td>{companyName(run.company_id)}</td><td className="number">{invoice ? money(invoice.amount, invoice.currency) : "—"}</td><td><span className="badge escalated"><ArrowUpRight size={10} />{dateLabel(run.escalated_at ?? undefined)}</span></td></tr>; })}</tbody></table></div>}
        </section>
        <StatusBar title="Run outcomes" caption="All companies, all workflow runs" counts={overview?.executions_by_status ?? {}} />
      </div>
      <div className="dash-row">
        <section className="card"><div className="card-header"><div><h2>Companies</h2><p className="card-subtitle">Volume and open decisions per company</p></div><Building2 size={16} color="#9daab8" /></div>
          <div className="table-wrap"><table><thead><tr><th>Company</th><th>Users</th><th>Invoices</th><th>Awaiting decision</th></tr></thead><tbody>{companies.map((c) => <tr key={c.id}><td><strong>{c.name}</strong><small className="subtle" style={{ display: "block" }}>Since {dateLabel(c.created_at)}</small></td><td>{c.users}</td><td>{c.invoices}</td><td>{c.pending_approvals > 0 ? <span className="badge exception">{c.pending_approvals} waiting</span> : <span className="subtle">None</span>}</td></tr>)}</tbody></table></div>
        </section>
        <section className="card"><div className="card-header"><div><h2>Latest activity</h2><p className="card-subtitle">Who did what, across companies</p></div><Link className="text-link" href="/admin/activity">Audit log <ArrowRight size={12} /></Link></div>
          {activity.length === 0 ? <div className="empty-small"><p>No activity recorded yet.</p></div> : activity.map((event) => <div key={event.id} className="activity-item"><span className="activity-icon"><History size={13} /></span><div><strong>{eventLabel(event)}</strong><p>{event.actor_email ?? "Workflow engine"}{event.company_name ? ` · ${event.company_name}` : ""}</p><time>{dateLabel(event.created_at)}</time></div></div>)}
        </section>
      </div>
    </>}
  </div>;
}
