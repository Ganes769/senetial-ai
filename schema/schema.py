from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ItemAnalysis(BaseModel):
    summary: str
    what_happened: str
    why_it_matters: str
    importance: Literal["low", "medium", "high"]
    relevance_score: float = Field(ge=0, le=1)
    theme_ids: List[int] = []
    category: Optional[str] = None