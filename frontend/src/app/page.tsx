import Link from "next/link";
import { ArrowRight, ArrowUpRight, Boxes, Building2, Check, FileSearch, Gavel, History, Lock, Scale, ShieldCheck, Sparkles, X } from "lucide-react";

const STEPS = [
  { icon: FileSearch, title: "Validate", body: "Every invoice is compared with its purchase order: amount, vendor, and currency. Fixed business rules decide whether it is an exception, never a model." },
  { icon: Sparkles, title: "Investigate", body: "Exceptions get a Gemini investigation that summarises the risk and suggests an action. The output is checked against a strict schema." },
  { icon: Gavel, title: "Decide", body: "The workflow pauses. A person at the company approves, rejects, or escalates the exception to an admin." },
  { icon: Scale, title: "Oversee", body: "Admins see every company. They can take over escalations, override decisions with a reason, or reopen a case." },
];

const AUTHORITY = [
  { title: "Business rules", tag: "Deterministic", can: ["Decide if an invoice is an exception", "Apply the 5% tolerance", "Check vendor and currency"], cannot: ["Guess or interpret"] },
  { title: "AI investigation", tag: "Advisory", can: ["Summarise the discrepancy", "Rate the risk", "Recommend an action"], cannot: ["Approve or reject", "Change an invoice or payment"] },
  { title: "People", tag: "Authoritative", can: ["Approve or reject", "Escalate to an admin", "Override with a written reason"], cannot: ["Erase an earlier decision"] },
];

function ProductPreview() {
  return <div className="preview" aria-hidden="true">
    <div className="preview-bar"><span /><span /><span /><em>Company portal · Approvals</em></div>
    <div className="preview-body">
      <div className="preview-head"><div><small>Acme Supplies · ACME-1002</small><strong>$1,150.00</strong></div><span className="pv-badge warn">Needs approval</span></div>
      <div className="preview-compare"><div><small>Purchase order</small><b>$1,000.00</b></div><div><small>Discrepancy</small><b className="warn-ink">15.00%</b></div><div><small>Tolerance</small><b>5.00%</b></div></div>
      <div className="preview-ai"><span><Sparkles size={12} />Gemini investigation · <em>high risk</em></span><p>Invoice exceeds the purchase order by 15%, beyond the 5% policy. Recommend requesting a corrected invoice.</p><small>Suggested action: request correction</small></div>
      <div className="preview-actions"><span className="pv-btn primary"><Check size={12} />Approve</span><span className="pv-btn"><X size={12} />Reject</span><span className="pv-btn ghost"><ArrowUpRight size={12} />Escalate</span></div>
    </div>
    <div className="preview-audit">
      <div><i className="dot good" /><span><b>Approved</b> by finance@devforge</span><time>09:41</time></div>
      <div><i className="dot over" /><span><b>Overridden to reject</b> by admin · “No signed price change”</span><time>10:02</time></div>
    </div>
  </div>;
}

export default function Home() {
  return <div className="home">
    <header className="home-nav">
      <Link href="/" className="home-brand"><span className="brand-icon"><Boxes size={18} /></span>AgentForge</Link>
      <nav aria-label="Homepage"><a href="#how">How it works</a><a href="#control">Control</a><a href="#portals">Portals</a></nav>
      <div className="home-nav-actions"><Link href="/login/company" className="button secondary small">Company sign in</Link><Link href="/login/admin" className="button dark small">Admin sign in</Link></div>
    </header>

    <main>
      <section className="home-hero">
        <div className="home-hero-copy">
          <p className="home-eyebrow rise">Invoice exception management</p>
          <h1 className="rise d1">Exceptions resolved with evidence, <em>and a person’s signature.</em></h1>
          <p className="home-lede rise d2">AgentForge checks every supplier invoice against its purchase order, uses AI to investigate the ones that don’t match, and routes each exception to a human for the decision, with an admin overseeing every company.</p>
          <div className="home-cta rise d3"><Link href="/login/company" className="button primary">Company portal <ArrowRight size={15} /></Link><Link href="/login/admin" className="button secondary">Admin portal</Link></div>
          <ul className="home-assurances rise d4"><li><Lock size={13} />AI never authorises a payment</li><li><History size={13} />Append-only audit history</li><li><ShieldCheck size={13} />Role-based access per company</li></ul>
        </div>
        <div className="rise d2"><ProductPreview /></div>
      </section>

      <section id="how" className="home-section">
        <div className="section-head"><p className="home-eyebrow">How it works</p><h2>Four steps, one accountable path.</h2><p>The same route for every invoice, from submission to a recorded outcome.</p></div>
        <ol className="home-steps">{STEPS.map(({ icon: Icon, title, body }, i) => <li key={title}><span className="step-index">0{i + 1}</span><Icon size={20} className="step-icon" /><h3>{title}</h3><p>{body}</p></li>)}</ol>
      </section>

      <section id="control" className="home-section">
        <div className="section-head"><p className="home-eyebrow">Who decides what</p><h2>Rules find facts. AI explains. <em>People decide.</em></h2><p>Each part of the system has a clear boundary. Nothing consequential happens without a person.</p></div>
        <div className="authority">{AUTHORITY.map((col) => <div key={col.title} className="authority-col"><span className="authority-tag">{col.tag}</span><h3>{col.title}</h3><ul>{col.can.map((c) => <li key={c}><Check size={13} />{c}</li>)}{col.cannot.map((c) => <li key={c} className="cannot"><X size={13} />{c}</li>)}</ul></div>)}</div>
      </section>

      <section className="home-section oversight">
        <div><p className="home-eyebrow">Admin oversight</p><h2>Overrides add to the record. <em>They never rewrite it.</em></h2>
          <p>When an admin changes a company’s decision, the original stays exactly as it was. The override records who made it, when, what changed, and why, and the reason is mandatory.</p>
          <ul className="oversight-points"><li><ArrowUpRight size={14} /><span><b>Escalate</b> hands a decision to an admin; the company can no longer act on it.</span></li><li><Scale size={14} /><span><b>Override</b> replaces the effective decision and keeps the original.</span></li><li><History size={14} /><span><b>Reopen</b> starts a fresh review while the closed one stays intact.</span></li></ul>
        </div>
        <div className="record-card" aria-hidden="true">
          <div className="record-title"><Scale size={14} />Decision record · ACME-1002</div>
          <div className="record-line"><i className="dot good" /><div><b>Approved</b> by finance@devforge<small>Original decision · Nov 16, 09:41</small></div></div>
          <div className="record-line"><i className="dot over" /><div><b>Overridden to rejected</b> by admin<small>Was approved · Nov 16, 10:02</small><blockquote>Supplier has not provided the signed price-change approval.</blockquote></div></div>
          <div className="record-foot">Effective decision: <b>Rejected</b></div>
        </div>
      </section>

      <section id="portals" className="home-section">
        <div className="section-head"><p className="home-eyebrow">Two portals</p><h2>Built for the people who do the work, and the people who answer for it.</h2></div>
        <div className="portal-cards">
          <div className="portal-card"><span className="portal-icon"><Building2 size={18} /></span><h3>Company portal</h3><p>For finance teams processing their own supplier invoices.</p><ul><li>Submit invoices or extract them from a PDF</li><li>See validation results and AI recommendations</li><li>Approve, reject, or escalate exceptions</li><li>Track every run and its history</li></ul><Link href="/login/company" className="button primary">Sign in as a company <ArrowRight size={14} /></Link></div>
          <div className="portal-card admin"><span className="portal-icon"><ShieldCheck size={18} /></span><h3>Admin portal</h3><p>For the people accountable across every company.</p><ul><li>Monitor all companies and their activity</li><li>Decide escalated exceptions</li><li>Override or reopen with a recorded reason</li><li>Review the complete audit log</li></ul><Link href="/login/admin" className="button dark">Sign in as an admin <ArrowRight size={14} /></Link></div>
        </div>
      </section>
    </main>

    <footer className="home-footer"><span className="home-brand small"><span className="brand-icon"><Boxes size={14} /></span>AgentForge</span><span>FastAPI · PostgreSQL · Gemini · Next.js</span><span>Human-led invoice exception management</span></footer>
  </div>;
}
