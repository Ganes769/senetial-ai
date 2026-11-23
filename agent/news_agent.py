import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from sqlalchemy import text

from agent.ingestion.arxiv.arxiv import fetch_recent_papers
from agent.ingestion.openai.openai import fetch_openai_news
from schema.schema import ItemAnalysis
from app.database import engine

load_dotenv()


class NewsState(TypedDict, total=False):
    arxiv_result: dict
    openai_result: dict
    new_items: list
    themes: list
    analyses: list
    saved_count: int
    errors: list


def _normalize_arxiv(papers: list) -> list:
    items = []
    for p in papers:
        items.append({
            "external_id": p["external_id"],
            "source_name": "arXiv",
            "title": p["title"],
            "content": p.get("abstract") or "",
            "url": p.get("url"),
            "published_at": p.get("published_at"),
        })
    return items


def _normalize_openai(articles: list) -> list:
    items = []
    for a in articles:
        items.append({
            "external_id": a["external_id"],
            "source_name": "openai_news",
            "title": a["title"],
            "content": a.get("summary") or "",
            "url": a.get("url"),
            "published_at": a.get("published_at"),
        })
    return items


def fetch_sources(state: NewsState) -> dict:
    errors: list[str] = []

    async def _run():
        max_results = int(os.getenv("NEWS_FETCH_MAX_RESULTS", "5"))
        arxiv_task = fetch_recent_papers(max_results=max_results)
        openai_task = fetch_openai_news(max_results=max_results)
        return await asyncio.gather(arxiv_task, openai_task, return_exceptions=True)

    arxiv_raw, openai_raw = asyncio.run(_run())

    if isinstance(arxiv_raw, Exception):
        errors.append(f"arxiv: {type(arxiv_raw).__name__}: {arxiv_raw!r}")
        arxiv = {"fetched": 0, "saved": 0, "papers": []}
    else:
        arxiv = arxiv_raw

    if isinstance(openai_raw, Exception):
        errors.append(f"openai: {type(openai_raw).__name__}: {openai_raw!r}")
        openai = {"fetched": 0, "saved": 0, "updated": 0, "articles": []}
    else:
        openai = openai_raw

    return {"arxiv_result": arxiv, "openai_result": openai, "errors": errors}


def filter_new_items(state: NewsState) -> dict:
    candidates = (
        _normalize_arxiv(state.get("arxiv_result", {}).get("papers", []))
        + _normalize_openai(state.get("openai_result", {}).get("articles", []))
    )
    if not candidates:
        return {"new_items": []}

    ids = [c["external_id"] for c in candidates]
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT document_external_id FROM discoveries "
                "WHERE document_external_id = ANY(CAST(:ids AS text[]))"
            ),
            {"ids": ids},
        ).fetchall()
    already = {r[0] for r in rows}
    new_items = [c for c in candidates if c["external_id"] not in already]
    return {"new_items": new_items}


def load_themes(state: NewsState) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, description FROM themes "
                "WHERE is_active = TRUE ORDER BY id"
            )
        ).mappings().all()
    return {"themes": [dict(r) for r in rows]}


def analyze_items(state: NewsState) -> dict:
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    ).with_structured_output(ItemAnalysis)

    themes = state.get("themes", [])
    theme_blob = json.dumps(themes, ensure_ascii=False)
    analyses = []
    errors = list(state.get("errors") or [])

    for item in state.get("new_items", []):
        prompt = f"""You are Sentinel AI. Analyze this news/paper against active themes.

Themes JSON:
{theme_blob}

Item:
title: {item['title']}
source: {item['source_name']}
url: {item.get('url')}
content: {item['content'][:4000]}

Return: summary, what_happened, why_it_matters, importance,
relevance_score (0-1), theme_ids (only matching theme ids), category.
If irrelevant to all themes, relevance_score < 0.3 and theme_ids=[].
"""
        try:
            result: ItemAnalysis = llm.invoke(prompt)
            analyses.append({"item": item, "analysis": result.model_dump()})
        except Exception as e:
            errors.append(f"{item['external_id']}: {e}")

    return {"analyses": analyses, "errors": errors}


def save_discoveries(state: NewsState) -> dict:
    insert_q = text(
        """
        INSERT INTO discoveries (
          document_external_id, source_name, title, summary,
          what_happened, why_it_matters, importance, relevance_score,
          theme_ids, category, url, published_at, discovered_at
        ) VALUES (
          :document_external_id, :source_name, :title, :summary,
          :what_happened, :why_it_matters, :importance, :relevance_score,
          CAST(:theme_ids AS JSONB), :category, :url, :published_at, :discovered_at
        )
        ON CONFLICT (document_external_id) DO NOTHING
        """
    )
    saved = 0
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        for row in state.get("analyses", []):
            item = row["item"]
            a = row["analysis"]
            if a.get("relevance_score", 0) < 0.3:
                continue
            result = conn.execute(
                insert_q,
                {
                    "document_external_id": item["external_id"],
                    "source_name": item["source_name"],
                    "title": item["title"],
                    "summary": a.get("summary"),
                    "what_happened": a.get("what_happened"),
                    "why_it_matters": a.get("why_it_matters"),
                    "importance": a.get("importance"),
                    "relevance_score": a.get("relevance_score"),
                    "theme_ids": json.dumps(a.get("theme_ids") or []),
                    "category": a.get("category"),
                    "url": item.get("url"),
                    "published_at": item.get("published_at"),
                    "discovered_at": now,
                },
            )
            if result.rowcount == 1:
                saved += 1
    return {"saved_count": saved}


def _has_new_items(state: NewsState) -> str:
    return "load_themes" if state.get("new_items") else "end"


builder = StateGraph(NewsState)
builder.add_node("fetch_sources", fetch_sources)
builder.add_node("filter_new_items", filter_new_items)
builder.add_node("load_themes", load_themes)
builder.add_node("analyze_items", analyze_items)
builder.add_node("save_discoveries", save_discoveries)

builder.set_entry_point("fetch_sources")
builder.add_edge("fetch_sources", "filter_new_items")
builder.add_conditional_edges(
    "filter_new_items",
    _has_new_items,
    {"load_themes": "load_themes", "end": END},
)
builder.add_edge("load_themes", "analyze_items")
builder.add_edge("analyze_items", "save_discoveries")
builder.add_edge("save_discoveries", END)

news_graph = builder.compile()