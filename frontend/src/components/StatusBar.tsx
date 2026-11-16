"use client";
import { useState } from "react";
import { CheckCircle2, CircleDashed, Clock3, OctagonAlert, XCircle } from "lucide-react";

/*
 * Segmented bar for workflow run states (one whole split into parts).
 * Status colors are the fixed reference status palette and always ship with an
 * icon + label in the legend, so state is never conveyed by color alone.
 */
const STATES = [
  { key: "COMPLETED", label: "Completed", color: "#0ca30c", icon: CheckCircle2 },
  { key: "WAITING_APPROVAL", label: "Awaiting decision", color: "#fab219", icon: Clock3 },
  { key: "REJECTED", label: "Rejected", color: "#ec835a", icon: XCircle },
  { key: "FAILED", label: "Needs attention", color: "#d03b3b", icon: OctagonAlert },
  { key: "OTHER", label: "In progress", color: "#a3adb9", icon: CircleDashed },
] as const;

export default function StatusBar({ counts, title, caption }: { counts: Record<string, number>; title: string; caption?: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const known = new Set<string>(STATES.map((state) => state.key));
  const other = Object.entries(counts).filter(([key]) => !known.has(key)).reduce((sum, [, value]) => sum + value, 0);
  const parts = STATES.map((state) => ({ ...state, value: state.key === "OTHER" ? other : counts[state.key] ?? 0 }));
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  const share = (value: number) => (total ? `${Math.round((value / total) * 100)}%` : "0%");
  return <section className="card chart-card" aria-label={title}>
    <div className="card-header"><div><h2>{title}</h2>{caption && <p className="card-subtitle">{caption}</p>}</div><span className="chart-total">{total} {total === 1 ? "run" : "runs"}</span></div>
    <div className="card-body">
      {total === 0 ? <p className="help">No workflow runs yet.</p> : <div className="segbar" role="img" aria-label={parts.filter((p) => p.value).map((p) => `${p.label} ${p.value}`).join(", ")}>
        {parts.filter((part) => part.value > 0).map((part) => <div key={part.key} className={`segbar-hit ${hover && hover !== part.key ? "dim" : ""}`} style={{ flexGrow: part.value }}
          onMouseEnter={() => setHover(part.key)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(part.key)} onBlur={() => setHover(null)} tabIndex={0} aria-label={`${part.label}: ${part.value} (${share(part.value)})`}>
          <span className="segbar-fill" style={{ background: part.color }} />
          {hover === part.key && <span className="chart-tooltip" role="tooltip"><i style={{ background: part.color }} />{part.label}<strong>{part.value}</strong><em>{share(part.value)}</em></span>}
        </div>)}
      </div>}
      <ul className="chart-legend">{parts.map(({ key, label, color, icon: Icon, value }) => <li key={key} className={hover && hover !== key ? "dim" : ""}><span className="legend-key" style={{ background: color }} /><Icon size={13} className="legend-icon" />{label}<strong>{value}</strong><span className="subtle">{share(value)}</span></li>)}</ul>
    </div>
  </section>;
}
