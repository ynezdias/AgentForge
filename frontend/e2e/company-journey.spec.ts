import { expect, test } from "@playwright/test";
import { createExceptionInvoice, runWorkflow, signIn, unique } from "./helpers";

test.describe("company portal", () => {
  test.beforeEach(async ({ page }) => { await signIn(page, "company"); });

  test("add an invoice, block a duplicate, and open the original", async ({ page }) => {
    const number = unique("UI");
    const supplier = `UI Supplier ${number}`;
    await page.goto("/company/invoices");
    const fill = async () => {
      await page.getByRole("button", { name: "Add invoice / PDF" }).click();
      await page.getByLabel("Invoice number").fill(number);
      await page.getByLabel("Invoice date").fill("2026-11-01");
      await page.getByLabel("Supplier name").fill(supplier);
      await page.getByLabel("Purchase order total").fill("1000");
      await page.getByLabel("Invoice total").fill("1150");
      await page.getByRole("button", { name: "Save invoice" }).click();
    };
    await fill();
    // The saved invoice opens with its deterministic validation result.
    await expect(page.getByRole("heading", { name: supplier })).toBeVisible();
    await expect(page.getByText("This invoice needs review")).toBeVisible();
    await expect(page.getByText(/Amount exceeds tolerance · 15\.00%/)).toBeVisible();

    await fill();
    await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText("already exists");
    await page.getByRole("link", { name: "Open existing invoice" }).click();
    await expect(page).toHaveURL(/\/company\/invoices\?invoice=/);
    await expect(page.getByRole("heading", { name: supplier })).toBeVisible();
  });

  test("AI investigation pauses for a person, who approves", async ({ page }) => {
    const invoice = await createExceptionInvoice(page);
    const run = await runWorkflow(page, "/company", invoice);
    await expect(run.getByText("Needs approval").first()).toBeVisible();
    await expect(run.getByText("GEMINI INVESTIGATION")).toBeVisible();
    await expect(run.getByText("request correction")).toBeVisible();
    await run.getByRole("button", { name: "Approve review" }).click();
    await expect(run.getByText("Review decision recorded.")).toBeVisible();
    await expect(run.getByText(/Approved by e2e-company@example\.test/)).toBeVisible();
    // The decision cannot be made twice.
    await expect(run.getByRole("button", { name: "Approve review" })).toHaveCount(0);
  });

  test("rejecting records the decision and the invoice status", async ({ page }) => {
    const invoice = await createExceptionInvoice(page);
    const run = await runWorkflow(page, "/company", invoice, "Invoice Exception Review");
    await run.getByRole("button", { name: "Reject" }).click();
    await expect(run.getByText("The exception was rejected.")).toBeVisible();
    await expect(page.locator(".detail-heading").getByText("Review rejected")).toBeVisible();
  });

  test("a matching invoice completes without asking anyone", async ({ page }) => {
    const invoice = await createExceptionInvoice(page, { amount: "1000.00" });
    const run = await runWorkflow(page, "/company", invoice);
    await expect(run.getByText("Invoice passed validation.")).toBeVisible();
    await expect(run.getByText("GEMINI INVESTIGATION")).toHaveCount(0);
  });
});
