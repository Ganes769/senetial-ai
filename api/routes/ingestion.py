import httpx
from fastapi import APIRouter, HTTPException, Query

from agent.ingestion.arxiv.arxiv import fetch_recent_papers
from agent.ingestion.openai.openai import fetch_openai_news

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


@router.get("/arxiv")
async def get_arxiv_papers(
    max_results: int = Query(10, ge=1, le=50),
):
    try:
        return await fetch_recent_papers(max_results=max_results)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"arXiv request failed: {error}",
        ) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/openai")
async def get_openai_news(
    max_results: int = Query(10, ge=1, le=50),
):
    try:
        return await fetch_openai_news(max_results=max_results)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI news request failed: {error}",
        ) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
