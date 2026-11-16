import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
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


app = FastAPI(title="AgentForge API", version="0.1.0", lifespan=lifespan)

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
