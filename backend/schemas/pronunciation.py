"""Esquemas Pydantic de pronunciación."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Level = Literal["good", "fair", "needs_practice"]


class PronunciationResponse(BaseModel):
    expected: str
    heard: str
    score: int
    level: Level
    ok: bool
