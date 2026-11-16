"use client";
import { useState } from "react";
import { LoaderCircle } from "lucide-react";

/** A consequential action that always requires a written reason (min 10 characters). */
export default function ReasonAction({ title, description, placeholder, confirmLabel, tone = "primary", onConfirm, onCancel }: {
  title: string; description: string; placeholder: string; confirmLabel: string;
  tone?: "primary" | "danger"; onConfirm: (reason: string) => Promise<void>; onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ready = reason.trim().length >= 10;
  async function submit() {
    if (!ready || busy) return;
    setBusy(true); setError("");
    try { await onConfirm(reason.trim()); }
    catch (err) { setError(err instanceof Error ? err.message : "The action could not be recorded."); setBusy(false); }
  }
  return <div className="reason-action">
    <h4>{title}</h4>
    <p>{description}</p>
    <label className="field-label" htmlFor="reason">Reason (recorded in the audit log)</label>
    <textarea id="reason" className="field textarea" rows={3} maxLength={1000} placeholder={placeholder} value={reason} disabled={busy} onChange={(event) => setReason(event.target.value)} />
    <div className="reason-meta"><span className={ready ? "" : "subtle"}>{ready ? "Ready to record" : `At least 10 characters (${reason.trim().length}/10)`}</span></div>
    {error && <p role="alert" className="error-text">{error}</p>}
    <div className="decision-actions"><button className={`button ${tone}`} disabled={!ready || busy} onClick={() => void submit()}>{busy && <LoaderCircle size={15} className="spin" />}{busy ? "Recording…" : confirmLabel}</button><button className="button secondary" disabled={busy} onClick={onCancel}>Cancel</button></div>
  </div>;
}
