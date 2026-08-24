"""Esquemas Pydantic de errores gramaticales."""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import MAX_CONTENT_CHARS


class GrammarAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class GrammarFinding(BaseModel):
    rule: str
    message: str
    example: str


class GrammarAnalyzeResponse(BaseModel):
    errors: list[GrammarFinding]


class GrammarRecurringError(BaseModel):
    rule: str
    message: str
    count: int
    last_example: str
    last_seen: str
