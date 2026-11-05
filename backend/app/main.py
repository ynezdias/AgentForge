from fastapi import FastAPI
from app.api.invoices import router as invoice_router
from app.api.workflows import router as workflow_router

app = FastAPI(title="AgentForge API", version="0.1.0")

app.include_router(invoice_router)
app.include_router(workflow_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "agentforge"}
