from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.get("/status")
def agent_status():
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, started_at, finished_at, status,
                       fetched, new_items, saved, error
                FROM agent_runs
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).mappings().first()

        discovery_count = conn.execute(
            text("SELECT COUNT(*) FROM discoveries")
        ).scalar()

    last_run = dict(row) if row else None
    if last_run:
        last_run["run_id"] = last_run.get("id")

    return {
        "agent_status": "running",
        "discovery_count": discovery_count or 0,
        "last_run": last_run,
    }
