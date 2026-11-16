"use client";
import Link from "next/link";
import { ArrowRight, Database, LoaderCircle } from "lucide-react";
import { useWorkspace } from "./Workspace";
import { statusLabel } from "@/lib/format";
export function StatusBadge({ status }: { status: string }) { return <span className={`badge status-${status.toLowerCase()}`}><i />{statusLabel(status)}</span>; }
export function Loading({ text = "Loading your workspace…" }: { text?: string }) { return <div className="loading-state" role="status"><LoaderCircle size={22} className="spin" /><span>{text}</span></div>; }
export function EmptyWorkspace() {
  const { setup, refreshing, error, portal, base } = useWorkspace();
  if (portal === "company") return <div className="empty-state"><span className="empty-icon"><Database size={30} /></span><h2>No invoices yet.</h2><p>Add an invoice or upload a PDF to compare it with its purchase order and start a review.</p><Link className="button primary" href={`${base}/invoices`}>Add your first invoice<ArrowRight size={16} /></Link></div>;
  return <div className="empty-state"><span className="empty-icon"><Database size={30} /></span><h2>No company data yet.</h2><p>Load the sample supplier, purchase orders, and invoices into the demo company to explore the review process. This is available only outside production.</p><button className="button primary" disabled={refreshing} onClick={() => void setup()}>{refreshing ? <LoaderCircle size={17} className="spin" /> : <Database size={17} />}{refreshing ? "Preparing sample workspace…" : "Load sample workspace"}<ArrowRight size={16} /></button>{error && <p className="error-text" role="alert">{error}</p>}</div>;
}
export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) { return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</div>; }
