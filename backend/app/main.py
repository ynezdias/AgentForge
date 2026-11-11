from fastapi import FastAPI
from app.api.invoices import router as invoice_router
from app.api.workflows import router as workflow_router
from app.api.approvals import router as approval_router
from app.api.investigations import router as investigation_router
from app.core.logging_config import configure_logging

configure_logging()
app = FastAPI(title="AgentForge API", version="0.1.0")

app.include_router(invoice_router)
app.include_router(workflow_router)
app.include_router(approval_router)
app.include_router(investigation_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "agentforge"}
