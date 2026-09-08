"""F-C1 (V3.26, P2-04): taxonomía de capas de la comprensión auditiva.

La taxonomía clasifica cada sub-destreza receptiva de listening en la capa
cognitiva del proceso que su evidencia ejercita:

- `recognition`   → decodificación abajo-arriba (sonido/palabra/frase/números).
- `comprehension` → construcción del significado literal (gist/detalle/…).
- `inference`     → ir más allá de lo dicho (intención, actitud, matices).

`dictation`/`shadowing` son tareas de producción: se reportan aparte (capa
None) y no entran en la agregación receptiva por capa.
"""
import pytest

from services.listening import (
    LISTENING_LAYERS,
    LISTENING_SUBSKILLS,
    accuracy_by_layer,
    listening_diagnostic,
    skill_layer,
)

# Mapa aprobado (decisión F-C1): sub-destreza → capa. La taxonomía es
# determinista: no requiere migración de datos ni etiquetado por ítem.
EXPECTED_LAYER_SKILLS: dict[str, list[str]] = {
    "recognition": ["word_recognition", "sound_recognition", "phrase_recognition", "numbers"],
    "comprehension": ["gist", "detail", "vocabulary", "sequencing", "note_taking", "prediction"],
    "inference": [
        "inference",
        "attitude",
        "speaker_intention",
        "fast_speech",
        "connected_speech",
        "multiple_speakers",
    ],
}

# Tareas de producción: fuera de la taxonomía receptiva (capa None).
PRODUCTION_SUBSKILLS = ("dictation", "shadowing")


def _row(skill: str, correct: bool) -> dict:
    return {"question_id": "x", "skill": skill, "correct": correct}


# --- Mapa determinista skill → capa ----------------------------------------

def test_skill_layer_covers_every_subskill():
    """Toda sub-destreza canónica tiene capa asignada o es una tarea de producción."""
    mapped = {s: skill_layer(s) for s in LISTENING_SUBSKILLS}
    for skill, layer in mapped.items():
        assert layer in LISTENING_LAYERS or skill in PRODUCTION_SUBSKILLS, (
            f"{skill!r} sin capa y sin clasificar como producción"
        )


def test_skill_layer_maps_agreed_taxonomy():
    for layer, skills in EXPECTED_LAYER_SKILLS.items():
        for skill in skills:
            assert skill_layer(skill) == layer, f"{skill} debería ser {layer}"


def test_skill_layer_maps_only_one_layer():
    for layer, skills in EXPECTED_LAYER_SKILLS.items():
        for skill in skills:
            for other in LISTENING_LAYERS:
                if other != layer:
                    assert skill_layer(skill) != other


def test_skill_layer_production_and_unknown_are_none():
    for skill in PRODUCTION_SUBSKILLS:
        assert skill_layer(skill) is None
    assert skill_layer("") is None
    assert skill_layer("does_not_exist") is None


# --- Agregación por capa ----------------------------------------------------

def test_accuracy_by_layer_groups_and_orders():
    rows = [
        _row("word_recognition", True),
        _row("phrase_recognition", False),
        _row("detail", True),
        _row("gist", True),
        _row("gist", False),
        _row("inference", True),
        _row("attitude", False),
    ]
    by_layer = accuracy_by_layer(rows)
    assert [e["layer"] for e in by_layer] == list(LISTENING_LAYERS)
    by = {e["layer"]: e for e in by_layer}

    assert by["recognition"]["attempts"] == 2
    assert by["recognition"]["correct"] == 1
    assert by["recognition"]["accuracy"] == 50.0

    assert by["comprehension"]["attempts"] == 3
    assert by["comprehension"]["correct"] == 2
    assert by["comprehension"]["accuracy"] == round(2 / 3 * 100, 1)

    assert by["inference"]["attempts"] == 2
    assert by["inference"]["correct"] == 1
    assert by["inference"]["accuracy"] == 50.0


def test_accuracy_by_layer_always_reports_all_layers():
    """El reporte por capa incluye las tres capas aunque una no tenga evidencia
    (la UI puede explicar que falta practicar esa capa)."""
    by_layer = accuracy_by_layer([_row("gist", True)])
    assert [e["layer"] for e in by_layer] == list(LISTENING_LAYERS)
    empty = {e["layer"] for e in by_layer if e["attempts"] == 0}
    assert empty == {"recognition", "inference"}


def test_accuracy_by_layer_excludes_production_and_unknown():
    rows = [
        _row("dictation", True),
        _row("shadowing", False),
        _row("gist", True),
        _row("", True),
        _row(None, True),
    ]
    by_layer = accuracy_by_layer(rows)
    total = sum(e["attempts"] for e in by_layer)
    assert total == 1
    assert by_layer[1]["layer"] == "comprehension"
    assert by_layer[1]["attempts"] == 1


# --- Diagnóstico ------------------------------------------------------------

def test_diagnostic_includes_layer_per_subskill():
    rows = [
        _row("word_recognition", True),
        _row("gist", False),
        _row("dictation", True),
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["word_recognition"]["layer"] == "recognition"
    assert by_skill["gist"]["layer"] == "comprehension"
    # La tarea de producción se reporta en subskills con capa None.
    assert by_skill["dictation"]["layer"] is None


def test_diagnostic_includes_by_layer():
    rows = [
        _row("word_recognition", True),
        _row("gist", False),
        _row("attitude", True),
    ]
    diag = listening_diagnostic(rows)
    assert [e["layer"] for e in diag["by_layer"]] == list(LISTENING_LAYERS)
    by = {e["layer"]: e for e in diag["by_layer"]}
    assert by["recognition"]["attempts"] == 1
    assert by["comprehension"]["attempts"] == 1
    assert by["inference"]["attempts"] == 1
    assert by["inference"]["correct"] == 1


def test_diagnostic_empty_reports_three_empty_layers():
    diag = listening_diagnostic([])
    assert [e["layer"] for e in diag["by_layer"]] == list(LISTENING_LAYERS)
    assert all(e["attempts"] == 0 and e["accuracy"] is None for e in diag["by_layer"])


# --- Exposición en ítems servidos ------------------------------------------

def test_public_item_exposes_layer():
    """`_public` añade `layer` derivado del skill del ítem a la pregunta servida."""
    from domain import listening as listening_domain

    from services.listening import QUESTION_BANK, skill_layer as _sl

    public = listening_domain._public(QUESTION_BANK[0])
    assert public["layer"] == _sl(QUESTION_BANK[0]["skill"])


def test_level_items_include_layer():
    from services.listening import level_items

    rows = [{"question_id": "l1", "skill": "numbers", "correct": True}]
    items = level_items("A1", rows)
    for item in items:
        assert "layer" in item
    by_id = {i["question_id"]: i for i in items}
    assert by_id["l1"]["layer"] == "recognition"
