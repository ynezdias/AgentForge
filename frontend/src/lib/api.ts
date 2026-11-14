export type InvoiceValidation = { valid: boolean; discrepancy_percentage: string | number | null; issues: string[] };
export type Invoice = {
  id: string; vendor_id: string; purchase_order_id: string; amount: string;
  currency: string; status: string; vendor_name?: string;
  invoice_number?: string | null; invoice_date?: string | null; due_date?: string | null;
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
export class DuplicateInvoiceError extends Error {
  constructor(message: string, public invoiceId: string) { super(message); this.name = "DuplicateInvoiceError"; }
}
async function apiRequest(path: string, options?: RequestInit): Promise<unknown> {
  let response: Response;
  try { response = await fetch(`/api/backend/${path}`, { ...options, cache: "no-store" }); }
  catch { throw new Error("Cannot connect to AgentForge. Check that the application is running and try again."); }
  if (!response.ok) {
    let message = "The request could not be completed.";
    let duplicateId = "";
    try {
      const body: unknown = await response.json();
      if (object(body) && typeof body.detail === "string") message = body.detail;
      else if (object(body) && object(body.detail) && body.detail.code === "DUPLICATE_INVOICE" && typeof body.detail.invoice_id === "string" && typeof body.detail.message === "string") {
        duplicateId = body.detail.invoice_id; message = body.detail.message;
      } else if (object(body) && Array.isArray(body.detail)) message = body.detail.map((item: unknown) => object(item) && typeof item.msg === "string" ? `${Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "Field"}: ${item.msg}` : "Check the invoice details").join("; ");
    } catch { /* Preserve a readable error for non-JSON upstream failures. */ }
    if (response.status === 409 && duplicateId) throw new DuplicateInvoiceError(message, duplicateId);
    throw new Error(response.status === 503 ? "The backend is unavailable. Start the application and refresh this page." : message);
  }
  return response.json();
}
const managerHeaders = { "Content-Type": "application/json", "x-demo-manager-token": "local-manager-demo" };
export const api = {
  getPurchaseOrders: async () => await apiRequest("invoices/purchase-orders") as Array<{ id: string; vendor_name: string; amount: string; currency: string }>,
  createInvoice: async (payload: { purchase_order_id?: string; supplier_name?: string; po_amount?: string; amount: string; currency: string; invoice_number: string; invoice_date: string; due_date?: string }) => await apiRequest("invoices", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }) as Invoice,
  extractPDF: async (content: string) => await apiRequest("invoices/extract-pdf", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) }) as { amount: string | null; supplier_name: string | null; currency: string | null; invoice_number: string | null; invoice_date: string | null; due_date: string | null; text_preview: string; notice: string },
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
