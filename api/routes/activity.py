from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.database import engine

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@router.get("/")
def list_activity(limit: int = Query(30, ge=1, le=100)):
    """
    Live Activity feed for the UI.

    Built from agent_runs + discoveries so the frontend can poll
    without a WebSocket yet.
    """
    events: list[dict] = []

    with engine.connect() as conn:
        runs = conn.execute(
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

        discoveries = conn.execute(
            text(
                """
                SELECT id, title, source_name, importance, relevance_score,
                       url, discovered_at
                FROM discoveries
                ORDER BY discovered_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()

    for run in runs:
        run_id = run["id"]
        started = run.get("started_at")
        finished = run.get("finished_at")
        status = run.get("status") or "unknown"

        events.append(
            {
                "id": f"run-{run_id}-started",
                "type": "run.started",
                "status": "running",
                "message": f"News monitor run #{run_id} started",
                "timestamp": _iso(started),
                "run_id": run_id,
                "meta": {},
            }
        )

        if finished is not None:
            if status == "failed":
                message = (
                    f"News monitor run #{run_id} failed"
                    + (f": {run['error']}" if run.get("error") else "")
                )
                event_type = "run.failed"
            else:
                message = (
                    f"News monitor run #{run_id} finished: "
                    f"fetched {run.get('fetched') or 0}, "
                    f"new {run.get('new_items') or 0}, "
                    f"saved {run.get('saved') or 0}"
                )
                event_type = "run.completed"

            events.append(
                {
                    "id": f"run-{run_id}-finished",
                    "type": event_type,
                    "status": status,
                    "message": message,
                    "timestamp": _iso(finished),
                    "run_id": run_id,
                    "meta": {
                        "fetched": run.get("fetched"),
                        "new_items": run.get("new_items"),
                        "saved": run.get("saved"),
                        "error": run.get("error"),
                    },
                }
            )

    for discovery in discoveries:
        title = discovery.get("title") or "Untitled"
        source = discovery.get("source_name") or "unknown"
        events.append(
            {
                "id": f"discovery-{discovery['id']}",
                "type": "discovery.created",
                "status": "ok",
                "message": f"Discovered ({source}): {title}",
                "timestamp": _iso(discovery.get("discovered_at")),
                "run_id": None,
                "meta": {
                    "discovery_id": discovery["id"],
                    "importance": discovery.get("importance"),
                    "relevance_score": discovery.get("relevance_score"),
                    "url": discovery.get("url"),
                    "source_name": source,
                },
            }
        )

    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    events = events[:limit]

    return {"count": len(events), "events": events}
