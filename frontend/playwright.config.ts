import { defineConfig, devices } from "@playwright/test";

/**
 * Browser end-to-end tests against a real, isolated stack:
 *   PostgreSQL (E2E_DATABASE_URL) -> FastAPI on :8100 with the fake AI provider
 *   -> the production Next.js build on :3100.
 * Never points at the developer's Docker stack, and never calls Gemini.
 */
const CI = !!process.env.CI;
const BACKEND_PORT = 8100;
const FRONTEND_PORT = 3100;
const python = process.env.E2E_PYTHON ?? "python";
const databaseUrl = process.env.E2E_DATABASE_URL;
if (!databaseUrl) throw new Error("Set E2E_DATABASE_URL to a disposable PostgreSQL database for end-to-end tests.");

export const E2E_USERS = {
  admin: { email: "e2e-admin@example.test", password: "e2e-admin-password" },
  company: { email: "e2e-company@example.test", password: "e2e-company-password" },
};

const backendEnv = {
  DATABASE_URL: databaseUrl,
  APP_ENV: "test",
  AUTH_SECRET_KEY: "e2e-only-signing-key-not-used-anywhere-else-0001",
  AI_PROVIDER: "fake",
  GOOGLE_API_KEY: "",
  ENABLE_DEMO_SETUP: "true",
  DEMO_COMPANY_NAME: "E2E Company",
  DEMO_ADMIN_EMAIL: E2E_USERS.admin.email,
  DEMO_ADMIN_PASSWORD: E2E_USERS.admin.password,
  DEMO_COMPANY_EMAIL: E2E_USERS.company.email,
  DEMO_COMPANY_PASSWORD: E2E_USERS.company.password,
  PYTHONUNBUFFERED: "1",
};

export default defineConfig({
  testDir: "./e2e",
  // Tests share one database and one company, so run them in order.
  workers: 1,
  fullyParallel: false,
  retries: CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Locally, PW_CHANNEL=msedge (or chrome) reuses an installed browser.
    ...(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {}),
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m alembic upgrade head && ${python} -m app.db.seed_users --reset && ${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${BACKEND_PORT}/health`,
      env: backendEnv,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npm run start -- --port ${FRONTEND_PORT}`,
      url: `http://localhost:${FRONTEND_PORT}`,
      env: { BACKEND_URL: `http://127.0.0.1:${BACKEND_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
