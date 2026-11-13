"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ArrowUpRight, Boxes, FileText, GitBranch, LayoutDashboard, RefreshCw, ShieldCheck } from "lucide-react";
import { WorkspaceProvider, useWorkspace } from "./Workspace";

const links = [{ href: "/", label: "Overview", icon: LayoutDashboard }, { href: "/invoices", label: "Invoice queue", icon: FileText }, { href: "/approvals", label: "Approvals", icon: ShieldCheck }, { href: "/workflows", label: "Workflows", icon: GitBranch }];
function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const workspace = useWorkspace();
  const pending = workspace.runs.filter((run) => run.status === "WAITING_APPROVAL").length;
  const current = links.find((link) => link.href === pathname)?.label ?? "Workspace";
  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand"><span className="brand-icon"><Boxes size={23} /></span><span>AgentForge<span className="brand-sub">FINANCE OPERATIONS</span></span></Link>
      <div className="workspace-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{links.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={`nav-link ${pathname === href ? "active" : ""}`} aria-current={pathname === href ? "page" : undefined}><Icon size={18} /><span>{label}</span>{href === "/approvals" && pending > 0 && <span className="nav-count">{pending}</span>}</Link>)}</nav>
      <div className="sidebar-note"><ShieldCheck size={20} /><strong>People make the decisions.</strong><p>AI investigates. Your team stays in control of every exception.</p><Link href="/workflows">Explore the process <ArrowUpRight size={14} /></Link></div>
      <div className="sidebar-user"><span className="avatar">FM</span><div><strong>Finance manager</strong><small>Local demo workspace</small></div><span className="presence" /></div>
    </aside>
    <div className="app-main">
      <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span><strong>{current}</strong></div><div className="topbar-actions"><span className={`connection ${workspace.error ? "offline" : ""}`}><span />{workspace.loading ? "Connecting" : workspace.error ? "Connection issue" : "Connected"}</span><span className="environment">Demo</span><button className="icon-button" aria-label="Refresh workspace" disabled={workspace.loading || workspace.refreshing} onClick={() => void workspace.refresh()}><RefreshCw size={17} className={workspace.refreshing ? "spin" : ""} /></button></div></header>
      <main className="page-content">{workspace.error && <div className="notice danger" role="alert"><Activity size={19} /><div><strong>We couldn’t update your workspace.</strong><p>{workspace.error}</p></div><button className="button small secondary" disabled={workspace.refreshing} onClick={() => void workspace.refresh()}>Try again</button></div>}{children}<footer className="page-footer"><span>AgentForge · Human-led financial operations</span><span>{workspace.updated ? `Updated ${workspace.updated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Waiting for workspace data"}</span></footer></main>
    </div>
  </div>;
}
export default function AppShell({ children }: { children: React.ReactNode }) { return <WorkspaceProvider><Shell>{children}</Shell></WorkspaceProvider>; }
