"""Esquemas Pydantic de pronunciación."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Level = Literal["good", "fair", "needs_practice"]


class WordSubstitution(BaseModel):
    expected: str
    heard: str


class PhonemeSubstitution(BaseModel):
    expected: str
    heard: str


class PronunciationBreakdown(BaseModel):
    correct: list[str]
    missing: list[str]
    extra: list[str]
    substituted: list[WordSubstitution]
    total: int


class PhonemeBreakdown(BaseModel):
    correct: list[str]
    missing: list[str]
    extra: list[str]
    substituted: list[PhonemeSubstitution]
    total: int


class FluencyStats(BaseModel):
    word_count: int
    duration_seconds: float | None = None
    wpm: float | None = None
    level: str


class PronunciationResponse(BaseModel):
    expected: str
    heard: str
    score: int
    level: Level
    ok: bool
    word_accuracy: int
    phonetic_score: int
    phoneme_accuracy_proxy: int
    prosody_proxy: int
    pronunciation_source: str
    breakdown: PronunciationBreakdown
    phoneme_breakdown: PhonemeBreakdown
    fluency: FluencyStats
    # V3.21 (V20-14/V20-15): metadatos ASR del intento. Cuando `asr_status !=
    # "ok"` el intento no se registra como fallo lingüístico.
    asr_status: str = "ok"  # ok | no_speech | unintelligible | low_confidence
    asr_confidence: float | None = None
