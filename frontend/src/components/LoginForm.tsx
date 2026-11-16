"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Boxes, Building2, LoaderCircle, LockKeyhole, ShieldCheck } from "lucide-react";
import { api, type Portal } from "@/lib/api";
import { safeNext } from "@/lib/session";

const COPY = {
  admin: { title: "Admin sign in", subtitle: "Oversee every company, review decisions, and record overrides.", icon: ShieldCheck, other: "company" as Portal, otherLabel: "Company sign in" },
  company: { title: "Company sign in", subtitle: "Submit invoices, track validation, and decide on exceptions.", icon: Building2, other: "admin" as Portal, otherLabel: "Admin sign in" },
};

function Form({ portal }: { portal: Portal }) {
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const copy = COPY[portal];
  const Icon = copy.icon;
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api.login(email.trim(), password, portal);
      // Full navigation so the new HttpOnly cookie is sent with the first portal request.
      window.location.assign(safeNext(params.get("next"), portal));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed. Try again.");
      setBusy(false);
    }
  }
  return <form className="login-card" onSubmit={(event) => void submit(event)}>
    <span className={`login-badge ${portal}`}><Icon size={18} /></span>
    <h1>{copy.title}</h1>
    <p className="page-description">{copy.subtitle}</p>
    <label className="field-label" htmlFor="email">Work email</label>
    <input id="email" className="field" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} disabled={busy} />
    <label className="field-label" htmlFor="password">Password</label>
    <input id="password" className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
    {error && <p role="alert" className="error-text">{error}</p>}
    <button className="button primary full" type="submit" disabled={busy || !email || !password}>{busy ? <LoaderCircle size={16} className="spin" /> : <LockKeyhole size={15} />}{busy ? "Signing in…" : "Sign in"}</button>
    <div className="login-links"><Link href="/"><ArrowLeft size={13} />Back to home</Link><Link href={`/login/${copy.other}`}>{copy.otherLabel}</Link></div>
  </form>;
}

export default function LoginForm({ portal }: { portal: Portal }) {
  return <main className="login-page">
    <Link href="/" className="brand login-brand"><span className="brand-icon"><Boxes size={22} /></span><span>AgentForge</span></Link>
    <Suspense fallback={<div className="login-card" />}><Form portal={portal} /></Suspense>
    <p className="login-foot">Sessions are kept in a secure, HttpOnly cookie and expire after 8 hours.</p>
  </main>;
}
