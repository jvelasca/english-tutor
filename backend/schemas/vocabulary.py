"""Esquemas Pydantic de vocabulario."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import MAX_CONTENT_CHARS

VocabularyStatus = Literal["exposed", "learning", "mastered"]


class VocabularyAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class VocabularyAnalyzeResponse(BaseModel):
    words: list[str]


class VocabularyItem(BaseModel):
    word: str
    appearances: int
    first_seen: str
    last_seen: str
    exposures: int
    last_exposed_at: str
    production_days: int
    status: VocabularyStatus
