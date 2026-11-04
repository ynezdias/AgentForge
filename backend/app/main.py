from fastapi import FastAPI


app = FastAPI(title="AgentForge")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agentforge"}
