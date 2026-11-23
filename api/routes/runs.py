from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.database import engine

router = APIRouter(prefix="/api/v1/runs", tags=["Runs"])


def _serialize_run(row) -> dict:
    data = dict(row)
    # Keep frontend-friendly aliases
    data["run_id"] = data.get("id")
    return data


@router.get("/")
def list_runs(limit: int = Query(20, ge=1, le=100)):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, started_at, finished_at, status,
                       fetched, new_items, saved, error
                FROM agent_runs
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()

    runs = [_serialize_run(row) for row in rows]
    return {"count": len(runs), "runs": runs}


@router.get("/{run_id}")
def get_run(run_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, started_at, finished_at, status,
                       fetched, new_items, saved, error
                FROM agent_runs
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return _serialize_run(row)
