import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { E2E_USERS } from "../playwright.config";

export type Portal = "admin" | "company";
export const ORIGIN = "http://localhost:3100";
const json = { "Content-Type": "application/json", Origin: ORIGIN };

/** Unique per test run, so tests can be rerun against the same database. */
export const unique = (label: string) => `${label}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`.toUpperCase();

/** Sign in through the same proxy endpoint the login form uses; the cookie lands in this page's context. */
export async function signIn(page: Page, portal: Portal) {
  const response = await page.request.post("/api/backend/auth/login", { headers: json, data: { ...E2E_USERS[portal], portal } });
  expect(response.status(), await response.text()).toBe(200);
}

export async function api<T = unknown>(request: APIRequestContext, method: "GET" | "POST", path: string, data?: unknown): Promise<T> {
  const response = await request.fetch(`/api/backend/${path}`, { method, headers: json, data });
  expect(response.ok(), `${method} ${path} -> ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

/** Create an invoice through the API (as the company user) for tests that are not about data entry. */
export async function createExceptionInvoice(page: Page, { amount = "1150.00", poAmount = "1000.00" } = {}) {
  const number = unique("E2E");
  const supplier = `E2E Supplier ${number}`;
  const invoice = await api<{ id: string }>(page.request, "POST", "invoices", {
    supplier_name: supplier, po_amount: poAmount, amount, currency: "USD", invoice_number: number, invoice_date: "2026-11-01",
  });
  return { id: invoice.id, number, supplier };
}

/** Open the invoice in the queue and run the named workflow through the UI. */
export async function runWorkflow(page: Page, base: string, invoice: { id: string; supplier: string }, workflow = "AI Invoice Exception Resolution") {
  await page.goto(`${base}/invoices?invoice=${invoice.id}`);
  await expect(page.getByRole("heading", { name: invoice.supplier })).toBeVisible();
  await page.locator("#workflow").selectOption({ label: workflow });
  await page.getByRole("button", { name: "Run review workflow" }).click();
  await expect(page.getByRole("region", { name: "Execution details" })).toBeVisible();
  return page.getByRole("region", { name: "Execution details" });
}
