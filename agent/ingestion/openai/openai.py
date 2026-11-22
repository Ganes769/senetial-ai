import asyncio
import calendar
import hashlib
import json
from datetime import datetime, timezone

import feedparser
import httpx
import trafilatura
from sqlalchemy import text

from app.database import engine

OPENAI_NEWS_URL = "https://openai.com/news/rss.xml"


async def read_article(client, url):
    """Download one article page and return its main text."""
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        return ""

    text_content = trafilatura.extract(response.text) or ""
    return " ".join(text_content.split())


def save_articles_to_db(articles):
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
        ON CONFLICT (external_id) DO UPDATE SET
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            url = EXCLUDED.url,
            published_at = EXCLUDED.published_at,
            updated_at = EXCLUDED.updated_at,
            content_hash = EXCLUDED.content_hash
        RETURNING (xmax = 0) AS inserted
    """)

    saved_count = 0
    updated_count = 0

    with engine.begin() as connection:
        for article in articles:
            summary = article["summary"]
            content_hash = hashlib.sha256(
                (summary or article["url"]).encode("utf-8")
            ).hexdigest()

            result = connection.execute(
                insert_query,
                {
                    "external_id": article["external_id"],
                    "source_name": article["source"],
                    "title": article["title"],
                    "content": summary,
                    "authors": json.dumps([]),
                    "published_at": article["published_at"],
                    "updated_at": article["published_at"],
                    "url": article["url"],
                    "categories": json.dumps(["openai_news"]),
                    "content_hash": content_hash,
                },
            )

            if result.scalar():
                saved_count += 1
            else:
                updated_count += 1

    return saved_count, updated_count


async def fetch_openai_news(max_results: int = 10):

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "sentinel-ai/1.0"},
    ) as client:
        response = await client.get(OPENAI_NEWS_URL)
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        articles = []

        for entry in feed.entries[:max_results]:

            link = entry.get("link")
            title = entry.get("title")

            if not link or not title:
                continue

            published = entry.get("published_parsed")

            published_at = (
                datetime.fromtimestamp(
                    calendar.timegm(published),
                    tz=timezone.utc
                )
                if published else None
            )

            body = await read_article(client, link)

            articles.append({
                "source": "openai_news",
                "external_id": entry.get("id") or link,
                "title": title,
                "url": link,
                "summary": body or entry.get("summary", ""),
                "published_at": published_at
            })

    saved_count, updated_count = await asyncio.to_thread(
        save_articles_to_db,
        articles
    )

    return {
        "fetched": len(articles),
        "saved": saved_count,
        "updated": updated_count,
        "articles": articles,
    }