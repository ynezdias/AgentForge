# AgentForge

**AI-assisted invoice exception management with human approval and admin oversight.**

AgentForge checks supplier invoices against their purchase orders, uses an LLM to investigate the ones that don't match, and routes every exception to a person for the decision. A separate admin portal oversees all companies: admins can take over escalated cases, override decisions with a written reason, and review a complete audit history.

The design principle is a strict split of authority:

| Part | Role | Can | Cannot |
|---|---|---|---|
| **Business rules** | Deterministic | Decide whether an invoice is an exception (5% amount tolerance, vendor and currency match) | Guess or interpret |
| **AI investigation** (Gemini) | Advisory | Summarise the discrepancy, rate risk, recommend an action | Approve, reject, or change an invoice or payment |
| **People** | Authoritative | Approve, reject, escalate; admins override or reopen with a reason | Erase an earlier decision |

> **Status:** Feature-complete for local use and fully tested locally. Not yet deployed. See [Roadmap](#roadmap) and [Known limitations](#known-limitations).

---

## How it is used

**Company user** (a finance team member)
1. Signs in to the **Company portal** and adds an invoice by typing it in or extracting it from a text PDF.
2. Runs a review workflow. Business rules compare the invoice with its purchase order.
3. If it matches, the run completes automatically. If not, Gemini writes a short investigation with a risk level and suggested action, and the run **pauses for a human decision**.
4. Approves, rejects, or **escalates** the exception to an admin with a reason.

**Admin**
1. Signs in to the **Admin portal** and sees every company, run outcomes, and escalations.
2. Decides escalated exceptions (the company can no longer act on them).
3. **Overrides** a company's decision or **reopens** a closed case, always with a written reason. The original decision is never edited; the override is appended beside it.
4. Reviews the **audit log**: who did what, when, across all companies.

---

## Architecture

```mermaid
flowchart LR
    Browser -->|"HttpOnly session cookie"| Next["Next.js 16<br/>pages + API proxy"]
    Next -->|"Bearer token (server-side only)"| API["FastAPI"]
    API --> Rules["Deterministic validation"]
    API --> Engine["Workflow engine<br/>(steps, cursor, advisory locks)"]
    Engine --> Rules
    Engine --> AI["LangGraph → Gemini<br/>(schema-validated output)"]
    Engine --> Approval["Approval gate<br/>(company user / admin)"]
    API --> DB[("PostgreSQL<br/>tenants, runs, approvals,<br/>overrides, audit events")]
    Engine --> DB
```

- **Frontend (Next.js 16, React 19, TypeScript).** Public homepage, two login pages, and two portals (`/company/*`, `/admin/*`). A server-side route handler proxies `/api/backend/*` to FastAPI. It holds the access token in an `HttpOnly; SameSite=Lax` cookie, injects it as a bearer token, ignores any `Authorization` header sent by the browser, and blocks cross-site state-changing requests. `proxy.ts` guards portal routes.
- **Backend (FastAPI, SQLAlchemy 2, Alembic, Pydantic).** REST API with role-based dependencies and tenant scoping on every query. Requests for another company's records return `404`, not `403`, so their existence is not revealed.
- **Workflow engine.** Executes a validated JSON workflow definition step by step (`invoice.validate` → condition → `invoice.investigate` → approval → `invoice.resolve`). Progress (step cursor, context, step results) is committed per step under a PostgreSQL advisory lock, so concurrent requests cannot advance the same run twice. Resolution refuses to run unless the *effective* decision is an approval.
- **AI investigation.** A LangGraph node calls Gemini with structured output and validates it against a strict Pydantic schema. Only typed invoice facts and the deterministic validation result are sent, never database access. Provider errors are replaced with a generic message so credentials and request data never reach logs or the UI.
- **Audit trail.** Every state change, decision, escalation, override, reopen, and invoice submission is an append-only `audit_events` row with the acting user (or the engine) and the company.

### Data model (key tables)

| Table | Purpose |
|---|---|
| `companies`, `users` | Tenants and accounts. Role is `admin` (no company) or `company` (exactly one company), enforced by a check constraint. |
| `vendors`, `purchase_orders`, `invoices` | Business data. Invoices and purchase orders carry `company_id`. Duplicate invoice identity is unique **per company**. |
| `workflows`, `workflow_executions`, `step_executions` | Workflow definitions and runs (status, cursor, context, idempotency key, escalation). |
| `approval_requests` | The original human decision: who, when, approve/reject. Never modified after it is recorded. |
| `decision_overrides` | Append-only admin overrides: admin, time, original decision, new decision, mandatory reason. |
| `invoice_investigations` | Saved AI recommendations with the facts they were based on. |
| `audit_events` | Append-only history with actor and company. |

---

## Security model

- **Passwords:** salted `scrypt` (standard library), constant-time comparison. Unknown emails take the same time as wrong passwords.
- **Sessions:** HS256 JWT, 8-hour expiry, signed with `AUTH_SECRET_KEY` (32+ characters; the server fails closed without it). The user is re-loaded on every request, so deactivating a user or bumping `token_version` revokes their tokens immediately.
- **Token handling:** the token lives only in an `HttpOnly` cookie (`Secure` over HTTPS) and never reaches browser JavaScript.
- **Authorization:** company users only ever see their company's rows. Only company users submit invoices; only admins create workflow templates, use `/admin/*`, override, or reopen. Escalated exceptions can only be decided by an admin.
- **Demo accounts** are created by an explicit seed script from environment variables, flagged `is_demo`, and **refused at login when `APP_ENV=production`**. The seed script and the demo-data endpoint also refuse to run in production.
- **CSRF:** `SameSite=Lax` cookie plus an `Origin` check on state-changing requests in the proxy.
- **Idempotency:** workflow runs require an `Idempotency-Key`. Repeating a key with the same input returns the original run; reusing it with different input returns `409`. Duplicate decisions and overrides return `409`. Reopen is idempotent per source run.

---

## Run locally (Docker Compose)

**Prerequisites:** Docker Desktop, and a Gemini API key from Google AI Studio.

1. Copy the example environment file and fill it in:
   ```powershell
   Copy-Item .env.example .env
   ```
   | Variable | Notes |
   |---|---|
   | `POSTGRES_PASSWORD` | Strong, URL-safe (letters, digits, `-`, `_`). |
   | `GOOGLE_API_KEY`, `GEMINI_MODEL` | Default model `gemini-3.5-flash`. |
   | `AUTH_SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
   | `APP_ENV` | `development` locally. `production` disables demo accounts and demo data. |
   | `DEMO_ADMIN_EMAIL` / `DEMO_ADMIN_PASSWORD`, `DEMO_COMPANY_EMAIL` / `DEMO_COMPANY_PASSWORD`, `DEMO_COMPANY_NAME` | Local demo accounts. Choose your own; never reuse them in production. |
   | `BACKEND_PORT` | Optional host port for the API (default `8000`; use e.g. `18000` if Windows reserves 8000). |

2. Start the stack, apply migrations, and create the demo accounts:
   ```powershell
   docker compose up --build -d
   docker compose exec backend alembic upgrade head
   docker compose exec backend python -m app.db.seed_users
   ```

3. Open **http://localhost:3000**, sign in to the **Admin portal**, and choose **Load sample workspace** to create sample suppliers, purchase orders, invoices, and workflows for the demo company. Then sign in to the **Company portal** to review them.

API docs (Swagger) are at `http://localhost:8000/docs` (or your `BACKEND_PORT`). PostgreSQL is only reachable inside the Compose network.

```powershell
docker compose logs --tail=50 backend frontend   # inspect logs
docker compose down                              # stop; data is kept
```

Do not pass `-v` to `down` unless you intend to delete the database volume.

---

## API overview

All endpoints except login and `/health` require a bearer token. Through the web app this is handled by the proxy and the session cookie.

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Anyone | Sign in to the `admin` or `company` portal |
| GET | `/api/v1/auth/me` | Signed in | Current user and company |
| GET / POST | `/api/v1/invoices` | Company (POST), both (GET, scoped) | List or submit invoices (`409` on duplicate) |
| GET | `/api/v1/invoices/purchase-orders` | Both (scoped) | Purchase orders |
| POST | `/api/v1/invoices/extract-pdf` | Company | Suggest fields from a text PDF (not saved, not sent to AI) |
| GET | `/api/v1/invoices/{id}/validate` | Both (scoped) | Deterministic validation result |
| GET / POST | `/api/v1/workflows` | Both (GET), admin (POST) | List or create workflow definitions |
| POST | `/api/v1/workflows/{id}/execute` | Both (scoped) | Start a run; requires `Idempotency-Key` |
| GET | `/api/v1/workflows/executions[/{id}[/audit]]` | Both (scoped) | Runs, run detail with decision record, run audit trail |
| POST | `/api/v1/approvals/{execution_id}` | Company (own, not escalated), admin | Approve or reject |
| POST | `/api/v1/approvals/{execution_id}/escalate` | Both (scoped) | Hand a pending decision to an admin (reason required) |
| POST | `/api/v1/admin/executions/{id}/override` | Admin | Replace the effective decision (reason required) |
| POST | `/api/v1/admin/executions/{id}/reopen` | Admin | Start a new linked run for the same invoice (reason required) |
| GET | `/api/v1/admin/overview`, `/admin/companies`, `/admin/overrides` | Admin | Cross-company oversight |
| GET | `/api/v1/activity` | Both (scoped) | Recent audit events with actors |
| POST | `/api/v1/investigations/{invoice_id}` | Both (scoped) | Stand-alone AI investigation |
| POST | `/api/v1/demo/setup` | Admin, non-production only | Load sample data |
| GET | `/health` | Anyone | Liveness |

Full request and response schemas are in Swagger at `/docs`.

---

## Testing

```powershell
# Unit tests (no database needed)
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# Full suite against a disposable PostgreSQL
docker run -d --name agentforge-testdb -e POSTGRES_USER=agentforge -e POSTGRES_PASSWORD=testonly -e POSTGRES_DB=agentforge -p 127.0.0.1:55432:5432 postgres:16
$env:DATABASE_URL = "postgresql+psycopg://agentforge:testonly@127.0.0.1:55432/agentforge"
$env:RUN_DB_TESTS = "1"; $env:GOOGLE_API_KEY = "test-key"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q
docker rm -f agentforge-testdb

# Frontend
cd ..\frontend
npm run lint; npm run build
```

The backend suite (96 tests) covers validation rules, the workflow engine, idempotency races, advisory locking, approvals, AI success and failure paths (Gemini mocked), password hashing and token tampering, login and portal rules, tenant isolation, escalation, overrides, and reopen. Database tests run inside a transaction that is rolled back.

GitHub Actions runs migrations, `alembic check` (model and migration drift), and the full backend suite against an ephemeral PostgreSQL with mocked Gemini, then frontend lint and build. CI never uses a real Gemini key.

---

## Known limitations

- **Synchronous AI calls.** A Gemini investigation runs inside the HTTP request (seconds, occasionally ~40 s). A background worker is not implemented.
- **No recovery action for failed runs yet.** A run that fails (for example when Gemini is unavailable) can be reopened by an admin, but there is no in-place retry yet.
- **Logout clears the cookie only.** A copied token stays valid until it expires (at most 8 hours) unless the user's `token_version` is bumped.
- **No login rate limiting yet.**
- **Text PDFs only.** Scanned PDFs need manual entry; there is no OCR.
- **Lists show up to 100 records** and have no pagination.
- **No payment tracking.** "Review approved" records a review status only; amounts and payments are never changed.

The first four are scheduled for the next step.

---

## Roadmap

- [x] Invoice intake, PDF extraction, per-company duplicate protection
- [x] Deterministic validation and workflow engine with approval gate
- [x] Gemini investigation with schema validation and safe failure handling
- [x] Role-based authentication, multi-tenancy, escalation, auditable admin overrides and reopen
- [x] Public homepage, Company portal, Admin portal, audit log
- [ ] Hardening: login rate limiting, token revocation on logout, retryable AI failures, failed-run recovery
- [ ] Deployment (frontend, backend, managed PostgreSQL) and production configuration
- [ ] Architecture diagrams, screenshots, and demo walkthrough

---

## Further documentation

- [Invoice intake and review](docs/INVOICE_INTAKE.md)

## License

See [LICENSE](LICENSE).
