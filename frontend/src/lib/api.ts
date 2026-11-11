export type Invoice = {
  id: string;
  vendor_id: string;
  purchase_order_id: string;
  amount: string;
  currency: string;
  status: string;
};

export type Workflow = { id: string; name: string; version: number };
export type Execution = {
  execution_id: string;
  status: string;
  current_step: number;
  context: Record<string, unknown>;
  steps: Array<{ step_id: string; status: string; result: Record<string, unknown> }>;
};

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, { ...options, cache: "no-store" });
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body);
      message = typeof parsed.detail === "string" ? parsed.detail : body;
    } catch { /* Keep a plain-text backend error. */ }
    throw new Error(`API error ${response.status}: ${message}`);
  }
  return response.json();
}

export const api = {
  getInvoices: () => apiRequest<Invoice[]>("invoices"),
  getWorkflows: () => apiRequest<Workflow[]>("workflows"),
  getExecution: (id: string) => apiRequest<Execution>(`workflows/executions/${encodeURIComponent(id)}`),
  executeWorkflow: (workflowId: string, invoiceId: string) =>
    apiRequest<Execution>(`workflows/${encodeURIComponent(workflowId)}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "idempotency-key": crypto.randomUUID() },
      body: JSON.stringify({ invoice_id: invoiceId }),
    }),
};
