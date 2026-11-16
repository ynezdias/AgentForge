"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Building2, Clock3, FileText, History, Scale, TriangleAlert } from "lucide-react";
import { api, type ActivityEvent, type AdminOverview as Overview, type CompanySummary } from "@/lib/api";
import { useWorkspace } from "@/components/Workspace";
import { EmptyWorkspace, Loading, PageHeading } from "@/components/UI";
import { dateLabel, statusLabel } from "@/lib/format";

const EVENT_LABELS: Record<string, string> = {
  INVOICE_SUBMITTED: "Invoice submitted", APPROVAL_DECIDED: "Approval decided", DECISION_OVERRIDDEN: "Decision overridden",
  EXCEPTION_ESCALATED: "Exception escalated", EXCEPTION_REOPENED: "Exception reopened", STEP_COMPLETED: "Step completed",
  STEP_REJECTED: "Step rejected", STEP_WAITING_APPROVAL: "Waiting for approval",
};
export function eventLabel(event: ActivityEvent) {
  if (event.event_type === "EXECUTION_STATE_CHANGED") return `Status → ${statusLabel(String(event.payload.to))}`;
  return EVENT_LABELS[event.event_type] ?? event.event_type.toLowerCase().replaceAll("_", " ");
}

export default function AdminOverview() {
  const { invoices, loading: workspaceLoading, error: workspaceError, updated } = useWorkspace();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api.adminOverview(), api.adminCompanies(), api.activity(15)])
      .then(([o, c, a]) => { if (active) { setOverview(o); setCompanies(c); setActivity(a); setError(""); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not load oversight data."); });
    return () => { active = false; };
  }, [updated]);
  const metrics = [
    { label: "Companies", value: overview?.companies, icon: Building2, note: "Active tenants", color: "" },
    { label: "Awaiting decision", value: overview?.pending_approvals, icon: Clock3, note: "Across all companies", color: "amber" },
    { label: "Escalated to admin", value: overview?.escalated_pending, icon: TriangleAlert, note: "Need an admin decision", color: "amber" },
    { label: "Overrides recorded", value: overview?.overrides, icon: Scale, note: "Original decisions preserved", color: "teal" },
  ];
  return <>
    <PageHeading eyebrow="ADMIN OVERSIGHT" title="Every company, every decision." description="Monitor company activity, step in on escalations, and review the full audit history." action={<Link href="/admin/approvals" className="button primary">Review decisions <ArrowRight size={15} /></Link>} />
    {error && <p role="alert" className="error-text" style={{ marginBottom: 16 }}>{error}</p>}
    <div className="metric-grid">{metrics.map(({ label, value, icon: Icon, note, color }) => <div className="metric" key={label}><div className="metric-top"><span>{label}</span><Icon size={17} /></div><div className={`metric-value ${color}`}>{value ?? "—"}</div><div className="metric-note">{note}</div></div>)}</div>
    {workspaceLoading ? <Loading /> : invoices.length === 0 && !workspaceError ? <div className="card"><EmptyWorkspace /></div> :
      <div className="content-grid">
        <section className="card"><div className="card-header"><div><h2>Companies</h2><p className="card-subtitle">Invoice volume and open decisions per tenant</p></div><Building2 size={17} color="#9daab8" /></div>
          <div className="table-wrap"><table><thead><tr><th>Company</th><th>Users</th><th>Invoices</th><th>Awaiting decision</th></tr></thead><tbody>{companies.map((c) => <tr key={c.id}><td><strong>{c.name}</strong><small className="subtle" style={{ display: "block" }}>Since {dateLabel(c.created_at)}</small></td><td>{c.users}</td><td>{c.invoices}</td><td>{c.pending_approvals > 0 ? <span className="badge exception">{c.pending_approvals} waiting</span> : <span className="subtle">None</span>}</td></tr>)}</tbody></table></div>
          <div className="table-footer"><span>{companies.length} companies</span><Link className="text-link" href="/admin/invoices">All invoices <FileText size={12} /></Link></div>
        </section>
        <section className="card"><div className="card-header"><div><h2>Recent activity</h2><p className="card-subtitle">Who did what, across all companies</p></div><History size={17} color="#9daab8" /></div>
          {activity.length === 0 ? <div className="empty-small"><p>No activity recorded yet.</p></div> : activity.map((event) => <div key={event.id} className="activity-item"><span className="activity-icon"><History size={14} /></span><div><strong>{eventLabel(event)}</strong><p>{event.actor_email ?? "Workflow engine"}{event.company_name ? ` · ${event.company_name}` : ""}</p><time>{dateLabel(event.created_at)}</time></div></div>)}
        </section>
      </div>}
  </>;
}
