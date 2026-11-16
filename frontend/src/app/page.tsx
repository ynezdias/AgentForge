import Link from "next/link";
import { ArrowRight, Boxes, Building2, ShieldCheck } from "lucide-react";

// Interim public entry point; the full homepage is built in step 2c.
export default function Home() {
  return <main className="login-page">
    <Link href="/" className="brand login-brand"><span className="brand-icon"><Boxes size={22} /></span><span>AgentForge</span></Link>
    <div className="login-card" style={{ maxWidth: 520 }}>
      <p className="eyebrow">INVOICE EXCEPTION AUTOMATION</p>
      <h1>Business rules check. AI investigates. People decide.</h1>
      <p className="page-description">Choose the portal for your role.</p>
      <div className="portal-choices">
        <Link href="/login/company" className="portal-choice"><Building2 size={18} /><span><strong>Company portal</strong><small>Submit invoices and decide on exceptions</small></span><ArrowRight size={15} /></Link>
        <Link href="/login/admin" className="portal-choice"><ShieldCheck size={18} /><span><strong>Admin portal</strong><small>Oversee companies, decisions, and overrides</small></span><ArrowRight size={15} /></Link>
      </div>
    </div>
  </main>;
}
