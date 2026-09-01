"""Tests del Content Quality Gate (V2.1): umbrales de volumen y diversidad
pedagógica del banco de listening, complementarios al integrity check."""
from services.content_validation import (
    QUALITY_THRESHOLDS,
    _quality_metrics,
    run_content_validation,
    run_quality_check,
)

_ACCENTS = ["British RP", "General American", "Australian", "Irish"]
_CONTEXTS = ["conversation", "announcement", "message", "instructions", "news"]


def _item(idx, level, speaker_id, accent, context, skill="detail", vector=None):
    vec = {
        "speed": 1,
        "vocabulary": 1,
        "accent": 1,
        "syntactic": 1,
        "length": 1,
        "speaker_count": 1,
        "noise": 1,
        "connected_speech": 1,
    }
    if vector:
        vec.update(vector)
    return {
        "id": f"q{idx}",
        "level": level,
        "skill": skill,
        "speaker_id": speaker_id,
        "accent": accent,
        "context": context,
        "difficulty_vector": vec,
    }


def _passing_bank():
    bank = []
    idx = 0
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for _ in range(20):
            bank.append(
                _item(
                    idx,
                    level,
                    f"sp{idx % 10}",
                    _ACCENTS[idx % 4],
                    _CONTEXTS[idx % 5],
                )
            )
            idx += 1
    for i in range(8):
        bank[i]["difficulty_vector"]["connected_speech"] = 4
    for i in range(8, 14):
        bank[i]["difficulty_vector"]["noise"] = 3
    for i in range(14, 18):
        bank[i]["difficulty_vector"]["speaker_count"] = 2
    for i in range(18, 24):
        bank[i]["difficulty_vector"]["speed"] = 5
    return bank


def test_quality_check_fails_below_thresholds():
    bank = [
        _item(0, "A1", "sp1", "British RP", "conversation"),
        _item(1, "A1", "sp1", "British RP", "conversation"),
    ]
    result = run_quality_check(bank)
    assert result["pass"] is False
    names = {c["name"] for c in result["checks"] if not c["pass"]}
    assert "total_items" in names


def test_quality_check_passes_at_thresholds():
    result = run_quality_check(_passing_bank())
    assert result["pass"] is True
    assert result["passed"] == result["total"]
    assert len(result["checks"]) == 14  # 1 total + 6 niveles + 7 dimensiones


def test_quality_metrics_counts_dimensions():
    bank = _passing_bank()
    metrics = _quality_metrics(bank)
    assert metrics["total_items"] == 120
    assert metrics["per_level"] == {
        "A1": 20,
        "A2": 20,
        "B1": 20,
        "B2": 20,
        "C1": 20,
        "C2": 20,
    }
    assert metrics["speakers"] == 10
    assert metrics["accents"] == 4
    assert metrics["contexts"] == 5
    assert metrics["connected_speech"] == 8
    assert metrics["noise"] == 6
    assert metrics["multiple_speakers"] == 4
    assert metrics["fast_speech"] == 6


def test_quality_metrics_ignores_blank_metadata():
    bank = [
        _item(0, "A1", "", "", "", skill="detail"),
    ]
    metrics = _quality_metrics(bank)
    assert metrics["speakers"] == 0
    assert metrics["accents"] == 0
    assert metrics["contexts"] == 0


def test_content_validation_exposes_quality_report():
    report = run_content_validation()
    assert "quality" in report
    quality = report["quality"]
    assert set(quality) == {"pass", "passed", "total", "checks"}
    assert quality["total"] == len(quality["checks"])
    assert quality["checks"][0]["name"] == "total_items"


def test_real_bank_passes_quality_gate():
    report = run_content_validation()
    assert report["quality"]["pass"] is True


def test_quality_thresholds_are_defined():
    assert QUALITY_THRESHOLDS["min_total_items"] == 100
    assert set(QUALITY_THRESHOLDS["min_items_per_level"]) == {
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    }
