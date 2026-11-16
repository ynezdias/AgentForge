import { request } from "@playwright/test";
import { E2E_USERS } from "../playwright.config";

/** Load the sample workspace (workflow templates and sample invoices) once, as the admin. */
export default async function globalSetup() {
  const ctx = await request.newContext({ baseURL: "http://localhost:3100", extraHTTPHeaders: { Origin: "http://localhost:3100" } });
  const login = await ctx.post("/api/backend/auth/login", { data: { ...E2E_USERS.admin, portal: "admin" } });
  if (!login.ok()) throw new Error(`E2E admin sign-in failed: ${login.status()} ${await login.text()}`);
  const setup = await ctx.post("/api/backend/demo/setup", { data: {} });
  if (!setup.ok()) throw new Error(`Sample workspace setup failed: ${setup.status()} ${await setup.text()}`);
  await ctx.dispose();
}
