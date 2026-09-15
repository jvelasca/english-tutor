"""Pinnea la adecuación CEFR del contenido medida en V3.70 · Eje 1 (`AA`).

Tests de **medición**: afirman los hechos ya auditados en
`docs/audit/AA-PED-CONTENIDO-CEFR.md`. Si alguien reequilibra el currículum,
sube la velocidad de A1 o reduce la de C1/C2, estos tests **fallan** y obligan a
re-auditar el hallazgo. No afirman que el contenido sea bueno: afirman lo que el
contenido **es** hoy (regla dura de V3.70: solo medición).

Criterio: `docs/audit/CEFR-REFERENCE.md`, referencia **INTERNA** del proyecto,
no un documento CEFR normativo. Las bandas y los marcadores se replican aquí a
propósito: son copia del instrumento `scripts/audit_dossier.py` y **no** deben
importarse desde `services`.
"""
import json
import re
from collections import Counter
from pathlib import Path

from services.content_validation import content_stats
from services.curriculum import load_all_levels
from services.listening import QUESTION_BANK, difficulty_from_vector

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# Copia de `REFERENCE_BANDS` de `scripts/audit_dossier.py`, que calca la columna
# «Velocidad operativa (wpm)» de `docs/audit/CEFR-REFERENCE.md`.
REFERENCE_WPM_BANDS: dict[str, tuple[int, int]] = {
    "A1": (80, 115),
    "A2": (110, 135),
    "B1": (130, 160),
    "B2": (150, 185),
    "C1": (165, 195),
    "C2": (175, 200),
}

# Copia de `CONNECTED_SPEECH_MARKERS` del instrumento: reducciones REALES, no
# contracciones suaves (`we're`, `it's`, `I'll` no cuentan).
CONNECTED_SPEECH_MARKERS: tuple[str, ...] = (
    "gonna",
    "wanna",
    "gotta",
    "dunno",
    "whaddaya",
    "whatcha",
    "kinda",
    "sorta",
    "lemme",
    "gimme",
    "ain't",
    "oughta",
    "shoulda",
    "woulda",
    "coulda",
    "y'know",
)

# Copia de `STOPWORDS` del instrumento, para medir si la opción correcta de un
# ítem `inference` se reconstruye con palabras literales del audio.
STOPWORDS = frozenset(
    (
        "a an the of to in on at for and or but is are was were am be been "
        "being i you he she it we they me him her us them my your his its our "
        "their this that these those do does did done have has had with from "
        "by as not no yes so if then than there here what which who whom "
        "whose when where why how can could should would will shall may might "
        "must"
    ).split()
)

REPO_DIR = Path(__file__).resolve().parents[2]
GENERATED_DIR = REPO_DIR / "docs" / "audit" / "generated"


def _corpus() -> list[dict]:
    """Ítems del corpus de listening (`cNNN`), sin el banco heredado TTS."""
    return [q for q in QUESTION_BANK if str(q["id"]).startswith("c")]


def _content_words(text: object) -> list[str]:
    words = re.findall(r"[a-z']+", str(text or "").lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def _resolves_by_literal_word(item: dict) -> bool:
    """True si la opción correcta se reconstruye con palabras del audio."""
    transcript = (
        item.get("clean_transcript")
        or item.get("transcript")
        or item.get("script")
        or ""
    )
    options = item.get("options") or []
    index = item.get("answer_index")
    if not transcript or not isinstance(index, int):
        return False
    if not 0 <= index < len(options):
        return False
    correct = _content_words(options[index])
    if not correct:
        return False
    heard = set(_content_words(transcript))
    matched = sum(1 for word in correct if word in heard)
    return matched / len(correct) >= 0.6


def _wpm_by_level() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {level: [] for level in LEVELS}
    for item in _corpus():
        out[item["level"]].append(float(item["speech_rate"]))
    return out


# --- Hallazgo 1 · sesgo posicional de los checks ---------------------------


def test_mc_position_bias_of_curriculum_checks_is_declared():
    """La posición 0 concentra el 89,4 % de las respuestas correctas."""
    positions = Counter(
        check.correct_index
        for level in load_all_levels()
        for objective in level.objectives()
        for check in objective.checks
        if len(check.options) >= 2
    )
    total = sum(positions.values())
    assert total == 368
    assert positions[0] == 329
    assert positions[0] / total >= 0.80
    # El corpus de listening, en cambio, está equilibrado: una respuesta de
    # 4 opciones no debe superar el 35 % en ninguna posición.
    corpus_positions = Counter(q["answer_index"] for q in _corpus())
    assert sum(corpus_positions.values()) == 490
    for index in range(4):
        assert corpus_positions[index] / 490 <= 0.35


# --- Hallazgo 2 · A1 sistemáticamente rápido -------------------------------


def test_a1_corpus_is_faster_than_its_reference_band():
    """86 de los 200 ítems A1 superan el techo de 115 wpm."""
    floor, ceiling = REFERENCE_WPM_BANDS["A1"]
    rates = _wpm_by_level()["A1"]
    assert len(rates) == 200
    above = [rate for rate in rates if rate > ceiling]
    assert len(above) == 86
    # Todo el corpus A1 vive en [115, 125]: el mínimo ya toca el techo.
    assert min(rates) == 115.0
    assert max(rates) == 125.0
    assert sum(rates) / len(rates) > ceiling
    assert floor < min(rates)


# --- Hallazgo 3 · C1/C2 sistemáticamente lentos ----------------------------


def test_c1_c2_corpus_is_slower_than_its_reference_band():
    """18 de 20 ítems C1 y 19 de 20 C2 quedan por debajo del suelo."""
    rates = _wpm_by_level()
    for level, under_floor in (("C1", 18), ("C2", 19)):
        floor, ceiling = REFERENCE_WPM_BANDS[level]
        assert len(rates[level]) == 20
        below = [rate for rate in rates[level] if rate < floor]
        assert len(below) == under_floor
        assert max(rates[level]) < ceiling
        assert sum(rates[level]) / len(rates[level]) < floor


# --- Hallazgo 4 · la escalera de velocidad no es monótona ------------------


def test_speed_ladder_is_not_monotonic_is_declared():
    """El ítem más rápido de B2 (185 wpm) supera al de C1 (170 wpm)."""
    rates = _wpm_by_level()
    maxima = {level: max(values) for level, values in rates.items()}
    assert maxima["B2"] == 185.0
    assert maxima["C1"] == 170.0
    assert maxima["B2"] > maxima["C1"]
    # La escalera de máximos no es no-decreciente entre niveles consecutivos.
    assert maxima["C2"] < maxima["B2"]
    # Y la dificultad media también invierte el orden B2/C1 (4,04 > 4,0).
    def _mean_difficulty(level: str) -> float:
        values = [
            difficulty_from_vector(q["difficulty_vector"])
            for q in _corpus()
            if q["level"] == level
        ]
        return sum(values) / len(values)

    assert _mean_difficulty("B2") > _mean_difficulty("C1")


# --- Hallazgo 5 · connected_speech declarado sin respaldo textual ----------


def test_connected_speech_declared_without_textual_support():
    """C1 (14/14) y C2 (20/20) declaran connected speech que no está escrito."""
    declared: Counter = Counter()
    realized: Counter = Counter()
    for item in _corpus():
        if not item.get("connected_speech"):
            continue
        declared[item["level"]] += 1
        text = " ".join(
            str(item.get(key) or "")
            for key in ("transcript", "clean_transcript", "script")
        ).lower()
        if any(marker in text for marker in CONNECTED_SPEECH_MARKERS):
            realized[item["level"]] += 1
    assert declared["C1"] == 14
    assert realized["C1"] == 0
    assert declared["C2"] == 20
    assert realized["C2"] == 0
    assert declared["B2"] == 11
    assert realized["B2"] == 3


# --- Hallazgo 6 · `inference` de A2 resoluble con una palabra --------------


def test_inference_items_of_a2_are_resolvable_by_literal_word():
    """4 de los 5 `inference` de A2 se resuelven con una palabra del audio."""
    items = [
        q for q in _corpus() if q["level"] == "A2" and q.get("skill") == "inference"
    ]
    assert len(items) == 5
    resolvable = sorted(q["id"] for q in items if _resolves_by_literal_word(q))
    assert len(resolvable) == 4
    # `c011` es el único que sí exige integrar dos claves no adyacentes.
    assert "c011" not in resolvable


# --- Integridad estructural del currículum ---------------------------------


def test_curriculum_structural_integrity_is_clean():
    """116 objetivos · 368 checks · 512 actividades, sin huecos estructurales."""
    levels = load_all_levels()
    objectives = [obj for level in levels for obj in level.objectives()]
    checks = [check for obj in objectives for check in obj.checks]
    activities = [act for obj in objectives for act in obj.activities]
    assert len(levels) == 6
    assert len(objectives) == 116
    assert len(checks) == 368
    assert len(activities) == 512
    assert sum(len(level.production_checks) for level in levels) == 34
    assert sum(len(mod.units) for level in levels for mod in level.modules) == 31
    assert all(obj.activities for obj in objectives)
    assert all(obj.checks for obj in objectives)
    assert all(
        check.skill in set(obj.skills)
        for obj in objectives
        for check in obj.checks
    )


# --- Anti-drift de las métricas generadas ----------------------------------


def test_generated_metrics_match_disk():
    """Las cifras canónicas y `curriculum-stats.json` coinciden con el disco."""
    stats = content_stats()
    assert stats["listening"]["corpus"] == 490
    assert stats["listening"]["total"] == 513
    live = {
        level.level: {
            "objectives": len(level.objectives()),
            "units": sum(len(mod.units) for mod in level.modules),
        }
        for level in load_all_levels()
    }
    assert sum(row["objectives"] for row in live.values()) == 116
    assert sum(row["units"] for row in live.values()) == 31
    generated = json.loads(
        (GENERATED_DIR / "curriculum-stats.json").read_text(encoding="utf-8")
    )
    declared = {
        row["level"]: {"objectives": row["objectives"], "units": row["units"]}
        for row in generated["levels"]
    }
    assert declared == live
