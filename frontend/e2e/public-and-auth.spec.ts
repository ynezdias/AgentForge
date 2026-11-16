import { expect, test } from "@playwright/test";
import { E2E_USERS } from "../playwright.config";

test.describe("public site and authentication", () => {
  test("homepage explains the product and links to both portals", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.headers()["x-frame-options"]).toBe("DENY");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Exceptions resolved with evidence");
    await expect(page.getByRole("heading", { name: /Rules find facts\. AI explains\./ })).toBeVisible();
    await page.getByRole("link", { name: "Company portal", exact: true }).click();
    await expect(page).toHaveURL(/\/login\/company$/);
  });

  test("portal pages redirect anonymous visitors to the right sign-in page", async ({ page }) => {
    await page.goto("/company/approvals");
    await expect(page).toHaveURL(/\/login\/company\?next=%2Fcompany%2Fapprovals/);
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login\/admin\?next=%2Fadmin/);
  });

  test("wrong password shows an error and sets no session", async ({ page, context }) => {
    await page.goto("/login/company");
    await page.getByLabel("Work email").fill(E2E_USERS.company.email);
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toHaveText("Email or password is incorrect");
    expect((await context.cookies()).some((c) => c.name === "af_session")).toBe(false);
  });

  test("admin account cannot use the company portal", async ({ page }) => {
    await page.goto("/login/company");
    await page.getByLabel("Work email").fill(E2E_USERS.admin.email);
    await page.getByLabel("Password").fill(E2E_USERS.admin.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText("signs in through the Admin portal");
  });

  test("company sign-in returns to the requested page; the cookie is HttpOnly; sign-out ends the session", async ({ page, context }) => {
    await page.goto("/company/approvals");
    await page.getByLabel("Work email").fill(E2E_USERS.company.email);
    await page.getByLabel("Password").fill(E2E_USERS.company.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/company\/approvals$/);
    await expect(page.getByText(E2E_USERS.company.email)).toBeVisible();
    const session = (await context.cookies()).find((c) => c.name === "af_session");
    expect(session?.httpOnly).toBe(true);
    expect(session?.sameSite).toBe("Lax");
    expect(await page.evaluate(() => document.cookie)).not.toContain("af_session");

    // A company user is kept out of the admin portal.
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login\/admin/);

    await page.goto("/company");
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login\/company$/);
    await page.goto("/company");
    await expect(page).toHaveURL(/\/login\/company/);
  });
});
