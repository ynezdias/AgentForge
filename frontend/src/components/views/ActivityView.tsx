"use client";
import { useEffect, useMemo, useState } from "react";
import { History, Search } from "lucide-react";
import { api, type ActivityEvent } from "@/lib/api";
import { useWorkspace } from "@/components/Workspace";
import { Loading, PageHeading } from "@/components/UI";

import { dateLabel, eventLabel, reference } from "@/lib/format";

const GROUPS: Record<string, (e: ActivityEvent) => boolean> = {
  "All events": () => true,
  "Decisions": (e) => ["APPROVAL_DECIDED", "DECISION_OVERRIDDEN"].includes(e.event_type),
  "Escalations & reopens": (e) => ["EXCEPTION_ESCALATED", "EXCEPTION_REOPENED"].includes(e.event_type),
  "Submissions": (e) => e.event_type === "INVOICE_SUBMITTED",
  "People only": (e) => !!e.actor_email,
};

function detail(event: ActivityEvent) {
  const p = event.payload;
  if (typeof p.reason === "string") return `“${p.reason}”`;
  if (event.event_type === "INVOICE_SUBMITTED") return `${p.supplier ?? "Supplier"} · ${p.invoice_number ?? "no number"} · ${p.amount} ${p.currency}`;
  if (event.event_type === "STEP_COMPLETED" && typeof p.step_id === "string") return p.step_id.replaceAll("_", " ");
  return "";
}

export default function ActivityView() {
  const { portal, updated } = useWorkspace();
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [error, setError] = useState("");
  const [group, setGroup] = useState("All events");
  const [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    api.activity(200).then((rows) => { if (active) { setEvents(rows); setError(""); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not load activity."); });
    return () => { active = false; };
  }, [updated]);
  const rows = useMemo(() => (events ?? []).filter(GROUPS[group]).filter((e) =>
    `${e.actor_email ?? "workflow engine"} ${e.company_name ?? ""} ${eventLabel(e)} ${detail(e)}`.toLowerCase().includes(search.toLowerCase())), [events, group, search]);
  return <>
    <PageHeading eyebrow={portal === "admin" ? "AUDIT LOG" : "ACTIVITY LOG"} title={portal === "admin" ? "Complete audit history." : "Everything that happened."}
      description={portal === "admin" ? "Every submission, decision, escalation, and override across all companies, with who did it and when. Records are append-only." : "Your company’s submissions, decisions, and workflow events, with who did each one."} />
    {error && <p role="alert" className="error-text" style={{ marginBottom: 14 }}>{error}</p>}
    {events === null && !error ? <Loading text="Loading activity…" /> : <section className="card">
      <div className="toolbar"><div className="tabs">{Object.keys(GROUPS).map((g) => <button key={g} className={`tab ${group === g ? "active" : ""}`} aria-pressed={group === g} onClick={() => setGroup(g)}>{g}</button>)}</div>
        <label className="search"><Search size={15} /><input placeholder="Search people, companies, reasons" aria-label="Search activity" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div>
      <div className="table-wrap"><table className="audit-table"><thead><tr><th>When</th><th>Event</th><th>Who</th>{portal === "admin" && <th>Company</th>}<th>Details</th><th>Run</th></tr></thead>
        <tbody>{rows.map((e) => <tr key={e.id}><td className="subtle">{dateLabel(e.created_at)}</td><td><span className={`event-pill ${e.event_type.toLowerCase()} ${e.payload.decision === "reject" || e.payload.new_decision === "REJECTED" || e.payload.to === "REJECTED" ? "negative" : ""}`}>{eventLabel(e)}</span></td><td>{e.actor_email ?? <span className="subtle">Workflow engine</span>}</td>{portal === "admin" && <td>{e.company_name ?? <span className="subtle">—</span>}</td>}<td className="audit-detail">{detail(e)}</td><td className="reference">{e.execution_id ? reference(e.execution_id) : "—"}</td></tr>)}</tbody></table></div>
      {rows.length === 0 && <div className="empty-small"><History size={24} style={{ margin: "0 auto 10px" }} /><p>No events match these filters.</p></div>}
      <div className="table-footer"><span>{rows.length} of {events?.length ?? 0} most recent events</span><span>Showing up to 200 events</span></div>
    </section>}
  </>;
}
