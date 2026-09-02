"""Golden tests de calibración del corpus de listening (auditoría B).

Protegen las bandas auditadas en `docs/audit/B-LISTENING-CEFR.md` y los fixtures
`tests/golden/listening/*.json`: si una edición futura del corpus hace que un
nivel o un ítem muestreado se salga de lo auditado, estos tests fallan hasta que
se re-audite (y se actualice el golden a propósito).
"""
from __future__ import annotations

from golden import loader

from services.listening import difficulty_from_vector


def _stats_for_level(level: str) -> dict:
    items = loader.corpus_items_by_level(level)
    speech = [q.get("speech_rate") or 0 for q in items]
    diff = [difficulty_from_vector(q.get("difficulty_vector") or {}) for q in items]
    words = [
        len((q.get("clean_transcript") or q.get("script") or "").split())
        for q in items
    ]
    return {
        "n": len(items),
        "speech_min": min(speech),
        "speech_max": max(speech),
        "diff_min": min(diff),
        "diff_max": max(diff),
        "words_max": max(words),
        "connected": sum(1 for q in items if q.get("connected_speech")),
        "accents": len({q.get("accent") for q in items}),
    }


def test_level_bands_are_stable():
    bands = loader.load_json("listening/level_bands")["levels"]
    for level, band in bands.items():
        s = _stats_for_level(level)
        assert s["n"] == band["n"], (
            f"{level}: nº de ítems cambió ({s['n']} vs {band['n']})"
        )
        lo, hi = band["speech_rate"]
        assert lo <= s["speech_min"] and s["speech_max"] <= hi, (
            f"{level}: velocidad fuera de banda {lo}-{hi}: "
            f"{s['speech_min']}-{s['speech_max']}"
        )
        lo, hi = band["difficulty"]
        assert lo <= s["diff_min"] and s["diff_max"] <= hi, (
            f"{level}: dificultad fuera de banda {lo}-{hi}: "
            f"{s['diff_min']}-{s['diff_max']}"
        )
        assert s["words_max"] <= band["words_per_script_max"], (
            f"{level}: script más largo que lo auditado"
        )
        cs = band.get("connected_speech", {})
        if "min" in cs:
            assert s["connected"] >= cs["min"], (
                f"{level}: menos ítems connected_speech que lo auditado"
            )
        if "max" in cs:
            assert s["connected"] <= cs["max"], (
                f"{level}: más ítems connected_speech que lo auditado"
            )
        assert s["accents"] >= band["accent_variety_min"], (
            f"{level}: variedad de acentos por debajo de lo auditado"
        )


def test_reviewed_samples_still_exist_and_match_level():
    fixture = loader.load_json("listening/samples")
    for level, samples in fixture["levels"].items():
        for sample in samples:
            item = loader.corpus_item(sample["id"])
            assert item is not None, f"{sample['id']} fue eliminado del corpus"
            assert item["level"] == level, (
                f"{sample['id']} cambió de nivel ({item['level']} vs {level})"
            )
            assert item.get("skill"), f"{sample['id']} sin skill declarada"


def test_c2_pragmatics_samples_exist():
    """Las muestras de pragmática C1/C2 citadas en el dossier deben persistir."""
    fixture = loader.load_json("listening/samples")
    c2_ids = {s["id"] for s in fixture["levels"]["C2"]}
    assert "c123" in c2_ids  # ironía
    assert "c131" in c2_ids  # advertencia velada


def test_difficulty_derived_from_vector_is_authoritative():
    """`difficulty` de un ítem del corpus siempre se deriva de su vector."""
    for item in (
        loader.corpus_items_by_level("A1")[:5]
        + loader.corpus_items_by_level("C2")[:5]
    ):
        assert "difficulty" not in item, (
            f"{item['id']}: clave difficulty redundante presente en el corpus"
        )
