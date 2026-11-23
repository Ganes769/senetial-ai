from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])

@router.get("/status")
def agent_status():
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM agent_runs ORDER BY id DESC LIMIT 1")
        ).mappings().first()
    return {"agent_status": "running", "last_run": dict(row) if row else None}