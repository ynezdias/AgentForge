import { expect, test } from "@playwright/test";
import { createExceptionInvoice, runWorkflow, signIn } from "./helpers";

test.describe("escalation, admin override, audit, and recovery", () => {
  test("company escalates; admin decides, overrides with a reason, and it appears in the audit log", async ({ browser }) => {
    const company = await (await browser.newContext()).newPage();
    const admin = await (await browser.newContext()).newPage();
    await signIn(company, "company");
    await signIn(admin, "admin");

    const invoice = await createExceptionInvoice(company);
    const run = await runWorkflow(company, "/company", invoice);
    await run.getByRole("button", { name: "Escalate to admin" }).click();
    const confirm = run.getByRole("button", { name: "Escalate", exact: true });
    await run.getByLabel("Reason (recorded in the audit log)").fill("too short");
    await expect(confirm).toBeDisabled();
    await run.getByLabel("Reason (recorded in the audit log)").fill("Supplier changed the price without a contract amendment.");
    await confirm.click();
    await expect(run.getByText("Escalated to an admin.")).toBeVisible();
    await expect(run.getByRole("button", { name: "Approve review" })).toHaveCount(0);

    // The admin finds it under Escalated and approves it.
    await admin.goto("/admin/approvals");
    await admin.getByRole("tab", { name: /Escalated/ }).click();
    await admin.locator(".approval-item", { hasText: invoice.supplier }).click();
    const detail = admin.getByRole("region", { name: "Execution details" });
    await expect(detail.getByText(/Escalated to admin ·/)).toBeVisible();
    await detail.getByRole("button", { name: "Approve review" }).click();
    await expect(detail.getByText(/Approved by e2e-admin@example\.test/)).toBeVisible();

    // Override: the original approval stays in the record next to the override.
    const reason = `No signed amendment on file for ${invoice.number}.`;
    await detail.getByRole("button", { name: "Override decision" }).click();
    await detail.getByLabel("Reason (recorded in the audit log)").fill(reason);
    await detail.getByRole("button", { name: "Record override: reject" }).click();
    await expect(detail.getByText("Override recorded. The original decision is preserved.")).toBeVisible();
    await expect(detail.getByText(/Approved by e2e-admin@example\.test/)).toBeVisible();
    await expect(detail.getByText(/Overridden to rejected by e2e-admin@example\.test/)).toBeVisible();
    await expect(detail.getByText(reason)).toBeVisible();
    await expect(detail.getByText(/Effective decision: Rejected/)).toBeVisible();

    // The company sees the override too: oversight is transparent.
    await company.reload();
    await expect(company.getByRole("region", { name: "Execution details" }).getByText(reason)).toBeVisible();

    await admin.goto("/admin/activity");
    await admin.getByLabel("Search activity").fill(invoice.number);
    const row = admin.getByRole("row", { name: new RegExp(reason.replace(/\./g, "\\.")) });
    await expect(row).toContainText("Decision overridden");
    await expect(row).toContainText("e2e-admin@example.test");
  });

  test("AI outage: the run fails clearly, then Retry resumes it", async ({ page }) => {
    await signIn(page, "company");
    // Totals ending in .13 make the fake AI provider return 503s for three calls.
    const invoice = await createExceptionInvoice(page, { amount: "1150.13" });
    const run = await runWorkflow(page, "/company", invoice);
    await expect(run.getByText("The AI service is temporarily unavailable.")).toBeVisible();
    await expect(run.getByText("Stopped at: Investigate exception")).toBeVisible();
    await run.getByRole("button", { name: "Retry from this step" }).click();
    await expect(run.getByText("Retry succeeded. The run continued from the step that failed.")).toBeVisible();
    await expect(run.getByRole("button", { name: "Approve review" })).toBeVisible();
    await expect(run.getByText("GEMINI INVESTIGATION")).toBeVisible();
  });

  test("admin oversight dashboard shows companies and run outcomes", async ({ page }) => {
    await signIn(page, "admin");
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Every company, every decision." })).toBeVisible();
    await expect(page.getByRole("cell", { name: /E2E Company/ }).first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Run outcomes" }).getByText("Completed")).toBeVisible();
  });
});
