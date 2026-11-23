from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/api/v1/discoveries", tags=["Discoveries"])

@router.get("/")
def list_discoveries(limit: int = Query(20, ge=1, le=100)):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT * FROM discoveries ORDER BY discovered_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).mappings().all()
    return {"count": len(rows), "discoveries": [dict(r) for r in rows]}