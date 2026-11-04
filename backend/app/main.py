from fastapi import FastAPI
from app.api.invoices import router as invoice_router

app = FastAPI(title="AgentForge API", version="0.1.0")

app.include_router(invoice_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "agentforge"}