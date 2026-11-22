
import asyncio
import hashlib
import json
from datetime import datetime, timezone

import httpx
import feedparser
from sqlalchemy import text

from app.database import engine


ARXIV_API_URL = "https://export.arxiv.org/api/query"


# Convert arXiv publication dates into Python datetime objects
def parse_date(date_value):
    if not date_value:
        return None

    return datetime(
        *date_value[:6],
        tzinfo=timezone.utc
    )


# Save papers into PostgreSQL
def save_papers_to_db(papers):

    insert_query = text("""
        INSERT INTO documents (
            external_id,
            source_name,
            title,
            content,
            authors,
            published_at,
            updated_at,
            url,
            categories,
            content_hash
        )
        VALUES (
            :external_id,
            :source_name,
            :title,
            :content,
            CAST(:authors AS JSONB),
            :published_at,
            :updated_at,
            :url,
            CAST(:categories AS JSONB),
            :content_hash
        )
        ON CONFLICT (external_id) DO NOTHING
    """)

    saved_count = 0

    # Opens a database transaction.
    # Automatically commits if successful or rolls back on error.
    with engine.begin() as connection:

        for paper in papers:

            abstract = paper["abstract"]

            content_hash = hashlib.sha256(
                abstract.encode("utf-8")
            ).hexdigest()

            result = connection.execute(
                insert_query,
                {
                    "external_id": paper["external_id"],
                    "source_name": paper["source_name"],
                    "title": paper["title"],
                    "content": abstract,
                    "authors": json.dumps(paper["authors"]),
                    "published_at": paper["published_at"],
                    "updated_at": paper["updated_at"],
                    "url": paper["url"],
                    "categories": json.dumps(paper["categories"]),
                    "content_hash": content_hash
                }
            )

            # PostgreSQL returns rowcount 0 when it skips a duplicate.
            if result.rowcount == 1:
                saved_count += 1

    return saved_count


# Fetch papers from arXiv
async def fetch_recent_papers(max_results: int = 10):

    params = {
        "search_query": "cat:cs.LG OR cat:cs.IR",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:

        response = await client.get(
            ARXIV_API_URL,
            params=params
        )

        response.raise_for_status()

    # Parse XML response
    feed = feedparser.parse(response.text)

    if feed.bozo and not feed.entries:
        raise RuntimeError("Could not parse arXiv response")

    papers = []

    for entry in feed.entries:

        abstract = " ".join(
            entry.get("summary", "").split()
        )

        paper = {
            "external_id": entry.get("id"),
            "title": " ".join(
                entry.get("title", "").split()
            ),
            "abstract": abstract,

            "authors": [
                author.get("name")
                for author in entry.get("authors", [])
                if author.get("name")
            ],

            "published_at": parse_date(
                entry.get("published_parsed")
            ),

            "updated_at": parse_date(
                entry.get("updated_parsed")
            ),

            "url": entry.get("link"),

            "categories": [
                category.get("term")
                for category in entry.get("tags", [])
                if category.get("term")
            ],

            "source_name": "arXiv"
        }

        if paper["external_id"]:
            papers.append(paper)

    # Save papers using the existing synchronous SQLAlchemy engine.
    # Run it in a worker thread so it does not block async requests.
    saved_count = await asyncio.to_thread(
        save_papers_to_db,
        papers
    )

    return {
        "fetched": len(papers),
        "saved": saved_count,
        "duplicates_skipped": len(papers) - saved_count,
        "papers": papers
    }
