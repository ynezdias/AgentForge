export function money(amount: string | number | undefined, currency = "USD") {
  if (amount === undefined) return "—";
  const value = Number(amount);
  return Number.isFinite(value) ? new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value) : "—";
}
export const reference = (id: string) => id.slice(0, 8).toUpperCase();
export function invoiceDateLabel(value?: string | null) {
  return value ? new Date(`${value}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "Not provided";
}
export function dueDatePassed(value?: string | null) {
  if (!value) return false;
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return value < today;
}
export const statusLabel = (status: string) => ({ PENDING: "Queued", RUNNING: "Running", WAITING_APPROVAL: "Needs approval", COMPLETED: "Completed", FAILED: "Needs attention", REJECTED: "Rejected", pending: "Pending review", review_approved: "Review approved", review_rejected: "Review rejected" }[status] ?? status.replaceAll("_", " "));
export function dateLabel(value?: string) { return value ? new Date(value).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—"; }
export const issueLabel = (issue: string) => ({ AMOUNT_DISCREPANCY: "Amount exceeds tolerance", VENDOR_MISMATCH: "Vendor does not match", CURRENCY_MISMATCH: "Currency does not match", INVALID_PURCHASE_ORDER_AMOUNT: "Purchase order needs checking" }[issue] ?? issue.replaceAll("_", " ").toLowerCase());
const EVENT_LABELS: Record<string, string> = {
  INVOICE_SUBMITTED: "Invoice submitted", APPROVAL_DECIDED: "Decision recorded", DECISION_OVERRIDDEN: "Decision overridden",
  EXCEPTION_ESCALATED: "Escalated to admin", EXCEPTION_REOPENED: "Exception reopened", EXECUTION_RETRIED: "Run retried", STEP_COMPLETED: "Step completed",
  STEP_REJECTED: "Step rejected", STEP_WAITING_APPROVAL: "Waiting for approval",
};
export function eventLabel(event: { event_type: string; payload: Record<string, unknown> }) {
  if (event.event_type === "EXECUTION_STATE_CHANGED") return `Status → ${statusLabel(String(event.payload.to))}`;
  if (event.event_type === "APPROVAL_DECIDED") return event.payload.decision === "approve" ? "Approved" : "Rejected";
  return EVENT_LABELS[event.event_type] ?? event.event_type.toLowerCase().replaceAll("_", " ");
}
