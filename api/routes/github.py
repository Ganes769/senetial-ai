
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from agent.ingestion.github.service import sync_github
from app.database import engine

router = APIRouter(
    prefix="/api/v1/github",
    tags=["GitHub"],
)


class GitHubSettings(BaseModel):
    enabled: bool = True
    frequency_minutes: int = Field(default=60, ge=15)
    categories: dict[str, bool]


def _load_stats(connection) -> dict:
    repositories = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM github_repositories
            WHERE is_monitored = TRUE
            """
        )
    ).scalar()

    releases = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM github_events
            WHERE event_type = 'release'
              AND created_at_github >= NOW() - INTERVAL '7 days'
            """
        )
    ).scalar()

    issues = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM github_events
            WHERE event_type = 'issue'
              AND status = 'open'
            """
        )
    ).scalar()

    failed_workflows = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM github_events
            WHERE event_type = 'ci_failure'
            """
        )
    ).scalar()

    return {
        "repositories_monitored": repositories or 0,
        "new_releases": releases or 0,
        "open_issues": issues or 0,
        "failed_ci_workflows": failed_workflows or 0,
    }


def _load_settings(connection) -> dict | None:
    row = connection.execute(
        text(
            """
            SELECT *
            FROM github_monitoring_settings
            WHERE id = 1
            """
        )
    ).mappings().first()
    return dict(row) if row else None


def _load_repositories(connection) -> list[dict]:
    rows = connection.execute(
        text(
            """
            SELECT *
            FROM github_repositories
            ORDER BY github_updated_at DESC
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def _load_events(
    connection,
    *,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query = """
        SELECT id, event_type, repo_full_name,
               external_id, title, body, url,
               status, created_at_github, created_at
        FROM github_events
    """
    params: dict = {"limit": limit}

    if category:
        query += " WHERE event_type = :category"
        params["category"] = category

    query += " ORDER BY created_at_github DESC NULLS LAST LIMIT :limit"

    rows = connection.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


@router.get("")
@router.get("/")
def github_overview(
    events_limit: int = Query(default=50, ge=1, le=200),
    category: str | None = None,
):
    """Single GitHub dashboard payload: stats + settings + repos + events."""
    with engine.connect() as connection:
        settings = _load_settings(connection)
        stats = _load_stats(connection)
        repositories = _load_repositories(connection)
        events = _load_events(
            connection,
            category=category,
            limit=events_limit,
        )

    return {
        "stats": stats,
        "settings": settings,
        "repositories": repositories,
        "repositories_count": len(repositories),
        "events": events,
        "events_count": len(events),
    }


@router.post("/sync")
async def github_sync():
    try:
        return await sync_github()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@router.get("/stats")
def github_stats():
    with engine.connect() as connection:
        return _load_stats(connection)


@router.get("/repositories")
def github_repositories():
    with engine.connect() as connection:
        return _load_repositories(connection)


@router.get("/events")
def github_events(
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    with engine.connect() as connection:
        return _load_events(connection, category=category, limit=limit)


@router.get("/settings")
def get_github_settings():
    with engine.connect() as connection:
        row = _load_settings(connection)

    if not row:
        raise HTTPException(404, "Settings not found")

    return row


@router.put("/settings")
def update_github_settings(settings: GitHubSettings):
    allowed_categories = {
        "repositories",
        "releases",
        "commits",
        "issues",
        "pull_requests",
        "ci_failures",
        "security_advisories",
    }

    if set(settings.categories) != allowed_categories:
        raise HTTPException(
            status_code=400,
            detail="Please provide all seven monitoring categories",
        )

    if settings.frequency_minutes not in [15, 60, 360, 1440]:
        raise HTTPException(
            status_code=400,
            detail="Frequency must be 15, 60, 360 or 1440 minutes",
        )

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE github_monitoring_settings
                SET enabled = :enabled,
                    frequency_minutes = :frequency,
                    categories = CAST(:categories AS jsonb),
                    updated_at = NOW()
                WHERE id = 1
                """
            ),
            {
                "enabled": settings.enabled,
                "frequency": settings.frequency_minutes,
                "categories": json.dumps(settings.categories),
            },
        )

    return {
        "message": "GitHub monitoring settings updated",
        "settings": settings.model_dump(),
    }
