import Link from "next/link";
import WorkflowVisualizer from "@/components/WorkflowVisualizer";

export default function WorkflowsPage() {
  return (
    <main className="min-h-screen bg-slate-950 p-6 text-white md:p-10">
      <div className="mx-auto max-w-5xl">
        <nav aria-label="Page navigation" className="mb-8 flex gap-5 text-sm text-blue-400"><Link href="/">Dashboard</Link><Link href="/invoices">Invoice Operations</Link></nav>
        <h1 className="mb-2 text-3xl font-bold">Workflow Visualization</h1>
        <p className="mb-8 text-slate-400">Invoice exception automation pipeline.</p>
        <WorkflowVisualizer />
        <p className="mt-4 text-sm leading-6 text-slate-500">Static process overview, not a live execution diagram. Valid invoices can finish after validation; the exception path continues through investigation and manager review.</p>
      </div>
    </main>
  );
}
