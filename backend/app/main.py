import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.invoices import router as invoice_router
from app.api.workflows import router as workflow_router
from app.api.approvals import router as approval_router
from app.api.investigations import router as investigation_router
from app.api.demo import router as demo_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router, activity_router
from app.core.logging_config import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(_app):
    # Opt-in so unit tests and tools importing the app never touch a database.
    if os.environ.get("RECOVER_INTERRUPTED_ON_STARTUP", "false").lower() == "true":
        from app.db.session import SessionLocal
        from app.services.recovery import recover_interrupted_runs
        try:
            with SessionLocal() as db:
                recover_interrupted_runs(db)
        except Exception as exc:  # Never block startup on recovery.
            logging.getLogger(__name__).error("startup_recovery_failed", extra={"error_type": type(exc).__name__})
    yield


# Interactive docs are useful locally; a deployment can turn them off.
_docs = os.environ.get("ENABLE_API_DOCS", "true").lower() == "true"
app = FastAPI(title="AgentForge API", version="0.1.0", lifespan=lifespan,
              docs_url="/docs" if _docs else None, redoc_url="/redoc" if _docs else None,
              openapi_url="/openapi.json" if _docs else None)


@app.middleware("http")
async def require_internal_token(request: Request, call_next):
    """When INTERNAL_API_TOKEN is set, only the frontend proxy (which holds the
    token) may call the API. This keeps the public backend URL from being used
    directly, and is what makes a forwarded client IP trustworthy."""
    expected = os.environ.get("INTERNAL_API_TOKEN", "")
    if expected and request.url.path != "/health":
        supplied = request.headers.get("x-internal-token", "")
        if not secrets.compare_digest(supplied.encode(), expected.encode()):
            return JSONResponse({"detail": "Not found"}, status_code=404)
    return await call_next(request)

app.include_router(auth_router)
app.include_router(invoice_router)
app.include_router(workflow_router)
app.include_router(approval_router)
app.include_router(investigation_router)
app.include_router(demo_router)
app.include_router(admin_router)
app.include_router(activity_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "agentforge"}
