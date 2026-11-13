"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, type Invoice, type Workflow, type WorkflowRun } from "@/lib/api";

type Data = { invoices: Invoice[]; workflows: Workflow[]; runs: WorkflowRun[] };
type Workspace = Data & { loading: boolean; refreshing: boolean; error: string; updated: Date | null; refresh: () => Promise<void>; setup: () => Promise<void> };
const Context = createContext<Workspace | null>(null);
async function fetchData(): Promise<Data> { const [invoices, workflows, runs] = await Promise.all([api.getInvoices(), api.getWorkflows(), api.getExecutions()]); return { invoices, workflows, runs }; }
export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<Data>({ invoices: [], workflows: [], runs: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState<Date | null>(null);
  useEffect(() => {
    let active = true;
    fetchData().then((value) => { if (active) { setData(value); setUpdated(new Date()); } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not load the workspace."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const refresh = useCallback(async () => {
    setRefreshing(true); setError("");
    try { setData(await fetchData()); setUpdated(new Date()); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not refresh the workspace."); }
    finally { setRefreshing(false); }
  }, []);
  const setup = useCallback(async () => {
    setRefreshing(true); setError("");
    try { await api.setupDemo(); setData(await fetchData()); setUpdated(new Date()); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not prepare sample data."); }
    finally { setRefreshing(false); }
  }, []);
  return <Context.Provider value={{ ...data, loading, refreshing, error, updated, refresh, setup }}>{children}</Context.Provider>;
}
export function useWorkspace() { const value = useContext(Context); if (!value) throw new Error("Workspace provider is missing"); return value; }
