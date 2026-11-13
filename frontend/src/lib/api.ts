export type InvoiceValidation = { valid: boolean; discrepancy_percentage: string | number | null; issues: string[] };
export type Invoice = {
  id: string; vendor_id: string; purchase_order_id: string; amount: string;
  currency: string; status: string; vendor_name?: string;
  purchase_order_amount?: string; purchase_order_currency?: string;
  validation?: InvoiceValidation;
};
export type WorkflowStep = { id: string; type: string; tool?: string | null; on_true?: string | null; on_false?: string | null; role?: string | null };
export type Workflow = { id: string; name: string; version: number; definition?: { name: string; steps: WorkflowStep[] } };
export type Recommendation = { summary: string; risk_level: "LOW" | "MEDIUM" | "HIGH"; recommended_action: string; reasoning: string; requires_human_approval: boolean };
export type WorkflowRun = {
  execution_id: string; status: string; workflow_id?: string; workflow_name?: string;
  invoice_id?: string; created_at?: string; current_step?: number;
  context: { valid?: boolean; issues?: string[]; discrepancy_percentage?: string | number;
    ai_recommendation?: Recommendation; error?: string; [key: string]: unknown };
};
export type Execution = WorkflowRun & { current_step: number; total_steps?: number; steps: Array<{ step_id: string; status: string; result: Record<string, unknown> }> };
export type ApprovalResult = { execution_id?: string; status: string; context?: Record<string, unknown> };
export type AuditEvent = { id: string; event_type: string; payload: Record<string, unknown>; created_at: string };

function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === "object" && !Array.isArray(value); }
function array<T>(value: unknown, check: (item: unknown) => boolean): T[] {
  if (!Array.isArray(value) || !value.every(check)) throw new Error("The server returned unexpected data. Refresh the workspace or check the backend version.");
  return value as T[];
}
function run(value: unknown): value is WorkflowRun { return object(value) && typeof value.execution_id === "string" && typeof value.status === "string" && object(value.context); }
function execution(value: unknown): Execution {
  if (!object(value)) throw new Error("Execution details could not be read. Refresh to try again.");
  const steps = value.steps;
  const currentStep = value.current_step;
  if (!run(value) || typeof currentStep !== "number" || !Array.isArray(steps) || !steps.every((step: unknown) => object(step) && typeof step.step_id === "string" && typeof step.status === "string" && object(step.result))) throw new Error("Execution details could not be read. Refresh to try again.");
  return value as Execution;
}
async function apiRequest(path: string, options?: RequestInit): Promise<unknown> {
  let response: Response;
  try { response = await fetch(`/api/backend/${path}`, { ...options, cache: "no-store" }); }
  catch { throw new Error("Cannot connect to AgentForge. Check that the application is running and try again."); }
  if (!response.ok) {
    let message = "The request could not be completed.";
    try { const body: unknown = await response.json(); if (object(body) && typeof body.detail === "string") message = body.detail; } catch { /* Preserve a readable error for non-JSON upstream failures. */ }
    throw new Error(response.status === 503 ? "The backend is unavailable. Start the application and refresh this page." : message);
  }
  return response.json();
}
const managerHeaders = { "Content-Type": "application/json", "x-demo-manager-token": "local-manager-demo" };
export const api = {
  getInvoices: async () => array<Invoice>(await apiRequest("invoices"), (item) => object(item) && typeof item.id === "string" && typeof item.amount === "string" && typeof item.currency === "string" && typeof item.status === "string"),
  getWorkflows: async () => array<Workflow>(await apiRequest("workflows"), (item) => object(item) && typeof item.id === "string" && typeof item.name === "string"),
  getExecutions: async () => array<WorkflowRun>(await apiRequest("workflows/executions"), run),
  getExecution: async (id: string) => execution(await apiRequest(`workflows/executions/${encodeURIComponent(id)}`)),
  getAudit: async (id: string) => array<AuditEvent>(await apiRequest(`workflows/executions/${encodeURIComponent(id)}/audit`), (item) => object(item) && typeof item.id === "string" && typeof item.event_type === "string" && object(item.payload)),
  getInvoiceValidation: async (id: string) => await apiRequest(`invoices/${encodeURIComponent(id)}/validate`) as InvoiceValidation,
  executeWorkflow: async (workflowId: string, invoiceId: string, key = crypto.randomUUID()) => execution(await apiRequest(`workflows/${encodeURIComponent(workflowId)}/execute`, {
    method: "POST", headers: { "Content-Type": "application/json", "idempotency-key": key }, body: JSON.stringify({ invoice_id: invoiceId }),
  })),
  approveExecution: async (id: string, decision: "approve" | "reject") => execution(await apiRequest(`approvals/${encodeURIComponent(id)}`, { method: "POST", headers: managerHeaders, body: JSON.stringify({ decision }) })),
  setupDemo: () => apiRequest("demo/setup", { method: "POST", headers: managerHeaders }),
};
