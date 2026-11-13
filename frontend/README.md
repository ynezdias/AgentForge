# AgentForge frontend

Next.js App Router, TypeScript, Tailwind CSS, Lucide, and React Flow.

## Run locally

Start the backend first. Point the ignored `.env.local` at its host URL:
`BACKEND_URL=http://127.0.0.1:18000` for the current Compose setup, or port 8000
for a standalone backend using the default port. Inside Compose the proxy uses
the backend service's internal port 8000 automatically.

From this directory:

```powershell
.\dev.ps1
```

This uses the portable Node runtime in the repository's ignored `.tools` folder
when available. With Node installed on PATH, `npm run dev` also works.
Open http://localhost:3000.

## Checks

```powershell
npm run build
```

The dashboard loads invoices and workflows through `/api/backend/invoices` and
`/api/backend/workflows`. The server proxy uses `BACKEND_URL`; restart Next.js
after changing it. Counts describe loaded records (each backend list is capped
at 100), not global database totals. Invoice status is the persisted business
status; it is not the deterministic validation result.

Every page shares navigation. `/invoices` contains a searchable supplier queue,
purchase-order comparisons, deterministic validation, and workflow execution.
Execution URLs survive page reloads. `/approvals` lists waiting requests and
past decisions with recorded steps and audit history. `/workflows` renders
the saved workflow definitions, including condition branches, in React Flow.

An empty workspace offers an explicit Load sample workspace action. This is
enabled only when the backend's `ENABLE_DEMO_SETUP=true` flag is set (as in the
local Compose file) and requires the demo manager header. Setup is idempotent;
it preserves existing records and adds sample invoices and two workflows:
Invoice Exception Review (rules and human review) and AI Invoice Exception
Resolution (Gemini, rules, and human review). AI failures stay visible; the
application never substitutes a fabricated recommendation.

Approval authorizes the workflow's review-status action; it does not change
invoice amounts, send payments, or carry out the AI recommendation. The local
demo token is visible in the frontend. Live AI investigations require a Gemini
key in the backend environment. Requests that fail before returning an execution
reuse their idempotency key when retried with the same selections.

This proxy and demo manager token are for local development. It forwards only
content type, idempotency key, and the explicit demo manager token; production
requires authentication, authorization, and server-managed credentials.
