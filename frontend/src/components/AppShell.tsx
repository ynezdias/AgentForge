"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, ArrowUpRight, Boxes, FileText, GitBranch, History, LayoutDashboard, LogOut, RefreshCw, ShieldCheck } from "lucide-react";
import { api, type Portal } from "@/lib/api";
import { WorkspaceProvider, useWorkspace } from "./Workspace";

const NAV = {
  company: [{ path: "", label: "Overview", icon: LayoutDashboard }, { path: "/invoices", label: "Invoice queue", icon: FileText }, { path: "/approvals", label: "Approvals", icon: ShieldCheck }, { path: "/workflows", label: "Workflows", icon: GitBranch }, { path: "/activity", label: "Activity log", icon: History }],
  admin: [{ path: "", label: "Oversight", icon: LayoutDashboard }, { path: "/invoices", label: "All invoices", icon: FileText }, { path: "/approvals", label: "Decisions", icon: ShieldCheck }, { path: "/activity", label: "Audit log", icon: History }, { path: "/workflows", label: "Workflows", icon: GitBranch }],
};
const initials = (email?: string) => (email ?? "").split("@")[0].split(/[._-]/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "AF";

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const workspace = useWorkspace();
  const { portal, base, user } = workspace;
  const [signingOut, setSigningOut] = useState(false);
  const links = NAV[portal].map((link) => ({ ...link, href: `${base}${link.path}` }));
  const pending = workspace.runs.filter((run) => run.status === "WAITING_APPROVAL").length;
  const current = links.find((link) => link.href === pathname)?.label ?? "Workspace";
  async function signOut() {
    setSigningOut(true);
    try { await api.logout(); } finally { router.replace(`/login/${portal}`); }
  }
  return <div className="app-shell" data-portal={portal}>
    <aside className="sidebar">
      <Link href={base} className="brand"><span className="brand-icon"><Boxes size={23} /></span><span>AgentForge<span className="brand-sub">{portal === "admin" ? "ADMIN OVERSIGHT" : "COMPANY PORTAL"}</span></span></Link>
      <div className="workspace-label">{portal === "admin" ? "ALL COMPANIES" : (user?.company_name ?? "WORKSPACE").toUpperCase()}</div>
      <nav aria-label="Main navigation">{links.map(({ href, label, icon: Icon, path }) => <Link key={href} href={href} className={`nav-link ${pathname === href ? "active" : ""}`} aria-current={pathname === href ? "page" : undefined}><Icon size={18} /><span>{label}</span>{path === "/approvals" && pending > 0 && <span className="nav-count">{pending}</span>}</Link>)}</nav>
      <div className="sidebar-note"><ShieldCheck size={20} /><strong>{portal === "admin" ? "Every override is recorded." : "People make the decisions."}</strong><p>{portal === "admin" ? "Admin changes keep the original decision and require a reason." : "AI investigates. Your team stays in control of every exception."}</p><Link href={`${base}/workflows`}>Explore the process <ArrowUpRight size={14} /></Link></div>
      <div className="sidebar-user"><span className="avatar">{initials(user?.email)}</span><div style={{ minWidth: 0 }}><strong className="truncate">{user?.email ?? "Loading…"}</strong><small>{portal === "admin" ? "Administrator" : `Company user${user?.company_name ? ` · ${user.company_name}` : ""}`}</small></div><button className="signout" aria-label="Sign out" title="Sign out" disabled={signingOut} onClick={() => void signOut()}><LogOut size={15} /></button></div>
    </aside>
    <div className="app-main">
      <header className="topbar"><div className="breadcrumbs">{portal === "admin" ? "Admin" : "Company"} <span>/</span><strong>{current}</strong></div><div className="topbar-actions"><span className={`connection ${workspace.error ? "offline" : ""}`}><span />{workspace.loading ? "Connecting" : workspace.error ? "Connection issue" : "Connected"}</span>{user?.is_demo && <span className="environment">Demo account</span>}<button className="icon-button" aria-label="Refresh workspace" disabled={workspace.loading || workspace.refreshing} onClick={() => void workspace.refresh()}><RefreshCw size={17} className={workspace.refreshing ? "spin" : ""} /></button></div></header>
      <main className="page-content">{workspace.error && <div className="notice danger" role="alert"><Activity size={19} /><div><strong>We couldn’t update your workspace.</strong><p>{workspace.error}</p></div><button className="button small secondary" disabled={workspace.refreshing} onClick={() => void workspace.refresh()}>Try again</button></div>}{children}<footer className="page-footer"><span>AgentForge · Human-led financial operations</span><span>{workspace.updated ? `Updated ${workspace.updated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Waiting for workspace data"}</span></footer></main>
    </div>
  </div>;
}
export default function AppShell({ portal, children }: { portal: Portal; children: React.ReactNode }) { return <WorkspaceProvider portal={portal}><Shell>{children}</Shell></WorkspaceProvider>; }
