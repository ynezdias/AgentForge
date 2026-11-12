# AgentForge frontend

Next.js App Router, TypeScript, Tailwind CSS, Lucide, and React Flow.

## Run locally

Start PostgreSQL and FastAPI from `backend` first. The frontend's ignored
`.env.local` contains `BACKEND_URL=http://127.0.0.1:8000`.

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

The dashboard links to `/invoices` for invoice/workflow selection, execution
results, AI recommendations, manager decisions, and recorded step history.
`/workflows` displays a static React Flow process diagram; it does not read live
workflow definitions or execution status. Page links are available on mobile.

Approval authorizes the workflow's review-status action; it does not change
invoice amounts, send payments, or carry out the AI recommendation. The local
demo token is visible in the frontend. Live AI investigations require a Gemini
key in the backend environment. Requests that fail before returning an execution
reuse their idempotency key when retried with the same selections.

This proxy and demo manager token are for local development. It forwards only
content type, idempotency key, and the explicit demo manager token; production
requires authentication, authorization, and server-managed credentials.
