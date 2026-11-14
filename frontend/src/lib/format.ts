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
export const statusLabel = (status: string) => ({ PENDING: "Queued", RUNNING: "Running", WAITING_APPROVAL: "Needs approval", COMPLETED: "Completed", FAILED: "Needs attention", REJECTED: "Rejected", pending: "Pending review", review_approved: "Review approved" }[status] ?? status.replaceAll("_", " "));
export function dateLabel(value?: string) { return value ? new Date(value).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—"; }
export const issueLabel = (issue: string) => ({ AMOUNT_DISCREPANCY: "Amount exceeds tolerance", VENDOR_MISMATCH: "Vendor does not match", CURRENCY_MISMATCH: "Currency does not match", INVALID_PURCHASE_ORDER_AMOUNT: "Purchase order needs checking" }[issue] ?? issue.replaceAll("_", " ").toLowerCase());
