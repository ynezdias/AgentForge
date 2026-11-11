export type Invoice = {
  id: string;
  vendor_id: string;
  purchase_order_id: string;
  amount: string;
  currency: string;
  status: string;
};

export type Workflow = { id: string; name: string; version: number };
export type Recommendation = {
  summary: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  recommended_action: string;
  reasoning: string;
  requires_human_approval: boolean;
};
export type WorkflowRun = {
  execution_id: string;
  status: string;
  context: {
    valid?: boolean;
    issues?: string[];
    discrepancy_percentage?: string | number;
    ai_recommendation?: Recommendation;
    error?: string;
    [key: string]: unknown;
  };
};
export type Execution = WorkflowRun & {
  current_step: number;
  steps: Array<{ step_id: string; status: string; result: Record<string, unknown> }>;
};
export type ApprovalResult = {
  execution_id?: string;
  status: string;
  context?: Record<string, unknown>;
};
export type InvoiceValidation = {
  valid: boolean;
  discrepancy_percentage: string | number;
  issues: string[];
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
  getInvoiceValidation: (invoiceId: string) =>
    apiRequest<InvoiceValidation>(`invoices/${encodeURIComponent(invoiceId)}/validate`),
  approveExecution: (executionId: string, decision: "approve" | "reject") =>
    apiRequest<ApprovalResult>(`approvals/${encodeURIComponent(executionId)}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Development demo only; production requires server-side authorization.
        "x-demo-manager-token": "local-manager-demo",
      },
      body: JSON.stringify({ decision }),
    }),
  executeWorkflow: (workflowId: string, invoiceId: string, idempotencyKey = crypto.randomUUID()) =>
    apiRequest<Execution>(`workflows/${encodeURIComponent(workflowId)}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "idempotency-key": idempotencyKey },
      body: JSON.stringify({ invoice_id: invoiceId }),
    }),
};
