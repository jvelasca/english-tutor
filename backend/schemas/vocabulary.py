"""Esquemas Pydantic de vocabulario."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import MAX_CONTENT_CHARS

VocabularyStatus = Literal["exposed", "learning", "mastered"]

# Estado determinista por ítem léxico (V2.3). Más granular que `VocabularyStatus`
# porque distingue reconocimiento (`known`) de producción incipiente (`learning`)
# y añade `weak` (producido pero con recuerdo bajo).
LexicalStatus = Literal["mastered", "known", "learning", "weak"]


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


class LexicalItemOut(BaseModel):
    word: str
    lemma: str
    cefr: str
    kind: str  # "word" | "structure"
    source: str  # "curriculum" | "user" | "imported"
    status: LexicalStatus
    recall: float
    next_review_days: int
    exposures: int
    appearances: int


class CefrBucket(BaseModel):
    cefr: str
    count: int


class LexiconSummary(BaseModel):
    total: int
    known: int
    learning: int
    weak: int
    mastered: int
    by_cefr: list[CefrBucket]


class LexiconOut(BaseModel):
    summary: LexiconSummary
    items: list[LexicalItemOut]
