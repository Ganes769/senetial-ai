
import os
import json
import asyncio

from datetime import datetime, timezone

from sqlalchemy import text
from dotenv import load_dotenv

from app.database import engine
from agent.ingestion.github.client import GitHubClient

load_dotenv()

MAX_REPOS = int(os.getenv("GITHUB_MAX_REPOSITORIES", "10"))

CONFIGURED_REPOS = [
    repo.strip()
    for repo in os.getenv("GITHUB_REPOS", "").split(",")
    if repo.strip()
]


DEFAULT_CATEGORIES = {
    "repositories": True,
    "releases": True,
    "commits": True,
    "issues": True,
    "pull_requests": True,
    "ci_failures": True,
    "security_advisories": True,
}


def get_settings():

    with engine.connect() as connection:

        result = connection.execute(
            text("""
                SELECT enabled, categories, frequency_minutes
                FROM github_monitoring_settings
                WHERE id = 1
            """)
        ).mappings().first()

    if not result:
        return {
            "enabled": True,
            "categories": DEFAULT_CATEGORIES,
            "frequency_minutes": 60
        }

    categories = result["categories"] or DEFAULT_CATEGORIES

    return {
        "enabled": result["enabled"],
        "categories": categories,
        "frequency_minutes": result["frequency_minutes"]
    }


async def get_repositories(client):

    if CONFIGURED_REPOS:

        repositories = []

        for repo_name in CONFIGURED_REPOS:

            repo = await client.get(
                f"/repos/{repo_name}"
            )

            repositories.append(repo)

        return repositories

    return await client.get(
        "/user/repos",
        params={
            "sort": "updated",
            "per_page": 100,
            "type": "owner"
        }
    )


def normalize_event(
    event_type,
    repo_name,
    external_id,
    title,
    body=None,
    url=None,
    status=None,
    created_at=None,
    payload=None
):

    return {
        "event_type": event_type,
        "repo_full_name": repo_name,
        "external_id": str(external_id),
        "title": title,
        "body": body,
        "url": url,
        "status": status,
        "created_at_github": created_at,
        "payload": payload or {}
    }


async def fetch_repository_events(client, repo, categories):

    repo_name = repo["full_name"]

    events = []
    warnings = []

    async def collect(category, endpoint, event_type, mapper):

        if not categories.get(category, False):
            return

        try:
            results = await client.get(
                endpoint,
                params={"per_page": 20}
            )

            for item in results:
                event = mapper(item)

                if event:
                    events.append(event)

        except Exception as error:

            warnings.append({
                "repository": repo_name,
                "category": category,
                "error": str(error)
            })

    # Releases

    def map_release(item):

        return normalize_event(
            "release",
            repo_name,
            item["id"],
            item.get("name") or item.get("tag_name"),
            item.get("body"),
            item.get("html_url"),
            item.get("draft") and "draft" or "published",
            item.get("published_at"),
            item
        )

    await collect(
        "releases",
        f"/repos/{repo_name}/releases",
        "release",
        map_release
    )

    # Commits

    def map_commit(item):

        commit = item.get("commit", {})

        return normalize_event(
            "commit",
            repo_name,
            item["sha"],
            commit.get("message", "").split("\n")[0],
            commit.get("message"),
            item.get("html_url"),
            "committed",
            (commit.get("author") or {}).get("date"),
            item
        )

    await collect(
        "commits",
        f"/repos/{repo_name}/commits",
        "commit",
        map_commit
    )

    # Issues - exclude pull requests

    def map_issue(item):

        if "pull_request" in item:
            return None

        return normalize_event(
            "issue",
            repo_name,
            item["id"],
            item["title"],
            item.get("body"),
            item.get("html_url"),
            item.get("state"),
            item.get("created_at"),
            item
        )

    await collect(
        "issues",
        f"/repos/{repo_name}/issues",
        "issue",
        map_issue
    )

    # Pull requests

    def map_pr(item):

        return normalize_event(
            "pull_request",
            repo_name,
            item["id"],
            item["title"],
            item.get("body"),
            item.get("html_url"),
            item.get("state"),
            item.get("created_at"),
            item
        )

    await collect(
        "pull_requests",
        f"/repos/{repo_name}/pulls",
        "pull_request",
        map_pr
    )

    # CI/CD failures

    async def collect_workflows():

        if not categories.get("ci_failures", False):
            return

        try:

            result = await client.get(
                f"/repos/{repo_name}/actions/runs",
                params={"per_page": 20}
            )

            for run in result.get("workflow_runs", []):

                if run.get("conclusion") != "failure":
                    continue

                events.append(
                    normalize_event(
                        "ci_failure",
                        repo_name,
                        run["id"],
                        run.get("name", "Workflow failed"),
                        run.get("display_title"),
                        run.get("html_url"),
                        run.get("conclusion"),
                        run.get("created_at"),
                        run
                    )
                )

        except Exception as error:

            warnings.append({
                "repository": repo_name,
                "category": "ci_failures",
                "error": str(error)
            })

    await collect_workflows()

    # Dependabot security alerts

    def map_security(item):

        vulnerability = item.get("security_vulnerability", {})
        advisory = item.get("security_advisory", {})

        return normalize_event(
            "security_advisory",
            repo_name,
            item["number"],
            vulnerability.get("package", {}).get("name")
                or "Security advisory",
            advisory.get("description"),
            item.get("html_url"),
            item.get("state"),
            item.get("created_at"),
            item
        )

    await collect(
        "security_advisories",
        f"/repos/{repo_name}/dependabot/alerts",
        "security_advisory",
        map_security
    )

    return events, warnings


def save_github_data(repositories, events):

    saved_events = 0

    with engine.begin() as connection:

        for repo in repositories:

            connection.execute(
                text("""
                    INSERT INTO github_repositories (
                        github_id,
                        full_name,
                        name,
                        description,
                        html_url,
                        language,
                        stars,
                        forks,
                        is_private,
                        github_updated_at
                    )
                    VALUES (
                        :github_id,
                        :full_name,
                        :name,
                        :description,
                        :html_url,
                        :language,
                        :stars,
                        :forks,
                        :is_private,
                        CAST(:updated_at AS timestamptz)
                    )
                    ON CONFLICT (github_id)
                    DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        html_url = EXCLUDED.html_url,
                        language = EXCLUDED.language,
                        stars = EXCLUDED.stars,
                        forks = EXCLUDED.forks,
                        is_private = EXCLUDED.is_private,
                        github_updated_at = EXCLUDED.github_updated_at
                """),
                {
                    "github_id": repo["id"],
                    "full_name": repo["full_name"],
                    "name": repo["name"],
                    "description": repo.get("description"),
                    "html_url": repo.get("html_url"),
                    "language": repo.get("language"),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "is_private": repo.get("private", False),
                    "updated_at": repo.get("updated_at")
                }
            )

        for event in events:

            result = connection.execute(
                text("""
                    INSERT INTO github_events (
                        event_type,
                        repo_full_name,
                        external_id,
                        title,
                        body,
                        url,
                        status,
                        created_at_github,
                        payload
                    )
                    VALUES (
                        :event_type,
                        :repo_full_name,
                        :external_id,
                        :title,
                        :body,
                        :url,
                        :status,
                        CAST(:created_at_github AS timestamptz),
                        CAST(:payload AS jsonb)
                    )
                    ON CONFLICT (
                        event_type,
                        repo_full_name,
                        external_id
                    )
                    DO NOTHING
                """),
                {
                    **event,
                    "payload": json.dumps(event["payload"])
                }
            )

            saved_events += result.rowcount

        connection.execute(
            text("""
                UPDATE github_monitoring_settings
                SET last_sync_at = NOW(),
                    updated_at = NOW()
                WHERE id = 1
            """)
        )

    return saved_events


async def sync_github():

    settings = get_settings()

    if not settings["enabled"]:
        return {
            "status": "paused",
            "message": "GitHub monitoring is disabled"
        }

    client = GitHubClient()

    repositories = await get_repositories(client)

    repositories = repositories[:MAX_REPOS]

    all_events = []
    all_warnings = []

    categories = settings["categories"]

    for repo in repositories:

        events, warnings = await fetch_repository_events(
            client,
            repo,
            categories
        )

        all_events.extend(events)
        all_warnings.extend(warnings)

    saved_events = await asyncio.to_thread(
        save_github_data,
        repositories,
        all_events
    )

    return {
        "status": "success",
        "repositories_checked": len(repositories),
        "events_fetched": len(all_events),
        "new_events_saved": saved_events,
        "warnings": all_warnings
    }
