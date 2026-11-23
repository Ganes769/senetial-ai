from datetime import datetime, timezone

from sqlalchemy import text

from app.celery_app import celery_app
from app.database import engine


@celery_app.task(name="agent.ingestion.tasks.run_news_monitor")
def run_news_monitor():
    started = datetime.now(timezone.utc)
    run_id = None
    try:
        with engine.begin() as conn:
            run_id = conn.execute(
                text(
                    "INSERT INTO agent_runs (started_at, status) "
                    "VALUES (:started_at, 'running') RETURNING id"
                ),
                {"started_at": started},
            ).scalar()

        from agent.news_agent import news_graph

        result = news_graph.invoke({})
        fetched = (
            result.get("arxiv_result", {}).get("fetched", 0)
            + result.get("openai_result", {}).get("fetched", 0)
        )
        new_items = len(result.get("new_items") or [])
        saved = result.get("saved_count") or 0
        errors = result.get("errors") or []

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE agent_runs
                    SET finished_at = :finished_at,
                        status = :status,
                        fetched = :fetched,
                        new_items = :new_items,
                        saved = :saved,
                        error = :error
                    WHERE id = :id
                    """
                ),
                {
                    "id": run_id,
                    "finished_at": datetime.now(timezone.utc),
                    "status": "failed" if errors else "ok",
                    "fetched": fetched,
                    "new_items": new_items,
                    "saved": saved,
                    "error": "; ".join(errors) if errors else None,
                },
            )
        return {
            "run_id": run_id,
            "fetched": fetched,
            "new_items": new_items,
            "saved": saved,
            "errors": errors,
        }
    except Exception as e:
        if run_id:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE agent_runs SET finished_at=:t, status='failed', error=:e WHERE id=:id"
                    ),
                    {"t": datetime.now(timezone.utc), "e": str(e), "id": run_id},
                )
        raise
