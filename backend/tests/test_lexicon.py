"""Tests del servicio de léxico (V2.3 → P1): estado, recall, kinds y cobertura."""
from __future__ import annotations

import pytest

from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import lexicon
from services.curriculum import Level, Objective


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _level() -> Level:
    return Level(
        course_id="english-tutor-academy",
        level_id="a1",
        level="A1",
        title="A1 · Beginner",
        modules=[],
    )


def _objective(**kwargs) -> Objective:
    base = dict(
        id="a1-m01-u01-l01-o01",
        can_do="I can introduce myself.",
        title="Presentarme",
        skills=["speaking"],
        vocabulary=["Name", "Country"],
        concepts=["I am", "My name is"],
    )
    base.update(kwargs)
    return Objective(**base)


# --- items_from_objective ---------------------------------------------------


def test_items_from_objective_combines_vocabulary_and_concepts():
    obj = _objective()
    items = lexicon.items_from_objective(_level(), obj)
    by_word = {i["word"]: i for i in items}
    assert set(by_word) == {"name", "country", "i am", "my name is"}
    assert by_word["name"]["kind"] == "word"
    assert by_word["name"]["cefr"] == "A1"
    assert by_word["name"]["level_id"] == "a1"
    assert by_word["name"]["objective_id"] == obj.id
    # P1 (§3.2): oraciones con sujeto explícito se siembran como functional chunk.
    assert by_word["i am"]["kind"] == "functional_chunk"
    assert by_word["my name is"]["kind"] == "functional_chunk"


def test_items_from_objective_normalizes_and_dedupes():
    obj = _objective(vocabulary=["Name", "name"], concepts=["I am", "i am"])
    items = lexicon.items_from_objective(_level(), obj)
    assert len(items) == 2


def test_classify_kind_lexical_unit_taxonomy():
    """P1 (§3.2): la taxonomía de Lexical Unit va más allá de word/structure."""
    assert set(lexicon.LEXICAL_KINDS) == {
        "word",
        "collocation",
        "phrasal_verb",
        "expression",
        "sentence_frame",
        "functional_chunk",
        "structure",
    }
    # Palabra
    assert lexicon.classify_kind("train") == "word"
    # Verbo + partícula (dos tokens, partícula inequívoca)
    assert lexicon.classify_kind("get up", source="vocabulary") == "phrasal_verb"
    assert lexicon.classify_kind("wake up") == "phrasal_verb"
    # Frase fija declarada como vocabulary → collocation
    assert lexicon.classify_kind("living room", source="vocabulary") == "collocation"
    assert (
        lexicon.classify_kind("strong coffee", source="vocabulary") == "collocation"
    )
    # Huecos explícitos → sentence frame
    assert lexicon.classify_kind("How much is ...?") == "sentence_frame"
    assert lexicon.classify_kind("Where is …?") == "sentence_frame"
    # Interrogativa cerrada → functional chunk
    assert lexicon.classify_kind("How are you?") == "functional_chunk"
    assert lexicon.classify_kind("What is your name?") == "functional_chunk"
    # Petición funcional / oración con sujeto
    assert lexicon.classify_kind("Can I have") == "functional_chunk"
    assert lexicon.classify_kind("I would like") == "functional_chunk"
    # Etiquetas gramaticales/temáticas → structure (no se inventa tipo)
    assert lexicon.classify_kind("Present Simple") == "structure"
    assert lexicon.classify_kind("countable / uncountable") == "structure"
    assert lexicon.classify_kind("to be") == "structure"
    assert lexicon.classify_kind("family words") == "structure"


# --- seed_curriculum_items (repositorio) ------------------------------------


def test_seed_does_not_increment_appearances(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    items = lexicon.items_from_objective(_level(), _objective())
    assert vocabulary_repo.seed_curriculum_items(uid, items) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["name"]["appearances"] == 0
    assert vocab["name"]["exposures"] == 0
    assert vocab["name"]["production_days"] == 0
    assert vocab["name"]["cefr"] == "A1"
    assert vocab["name"]["source"] == "curriculum"
    assert vocab["name"]["kind"] == "word"
    assert vocab["i am"]["kind"] == "functional_chunk"


def test_seed_preserves_production_and_fills_context(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(uid, ["name"])
    items = lexicon.items_from_objective(_level(), _objective())
    vocabulary_repo.seed_curriculum_items(uid, items)
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["name"]["appearances"] == 1  # no se reinicia la producción
    assert vocab["name"]["cefr"] == "A1"  # pero sí se rellena el contexto
    assert vocab["name"]["source"] == "curriculum"


def test_seed_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        vocabulary_repo.seed_curriculum_items("no-existe", [{"word": "x"}]) is False
    )


# --- item_mastery / item_status ---------------------------------------------


def test_item_mastery_bounded():
    assert lexicon.item_mastery({"appearances": 0, "exposures": 0}) == 0.0
    assert lexicon.item_mastery({"appearances": 100, "production_days": 100,
                                 "exposures": 100}) == 1.0


def test_item_status_deterministic():
    assert lexicon.item_status({"appearances": 0, "exposures": 0}) == "learning"
    assert lexicon.item_status({"appearances": 0, "exposures": 2}) == "known"
    assert (
        lexicon.item_status(
            {"appearances": 1, "production_days": 1, "exposures": 0}
        )
        == "weak"
    )
    # producido repetido pero no espaciado (mismo día) → aún en consolidación
    assert (
        lexicon.item_status(
            {"appearances": 3, "production_days": 1, "exposures": 3}
        )
        == "learning"
    )
    assert (
        lexicon.item_status({"appearances": 3, "production_days": 2}) == "mastered"
    )


# --- recall / next review ---------------------------------------------------


def test_item_recall_decays_over_time():
    row = {
        "appearances": 3,
        "production_days": 2,
        "exposures": 0,
        "last_seen": "2026-01-01T00:00:00+00:00",
        "last_exposed_at": "",
    }
    r0 = lexicon.item_recall(row, "2026-01-01T00:00:00+00:00")
    r1 = lexicon.item_recall(row, "2026-01-10T00:00:00+00:00")
    assert 0 <= r1 < r0 <= 1.0


def test_next_review_days_bounded_and_monotonic():
    weak_row = {"appearances": 1, "production_days": 1, "exposures": 0}
    strong_row = {"appearances": 3, "production_days": 2, "exposures": 0}
    d_weak = lexicon.next_review_days(weak_row)
    d_strong = lexicon.next_review_days(strong_row)
    assert 1 <= d_weak <= d_strong <= 30


# --- distribución CEFR / resumen / señal micro-drill ------------------------


def test_cefr_distribution_orders_and_counts():
    rows = [
        {"cefr": "B1"},
        {"cefr": "A1"},
        {"cefr": "A1"},
        {"cefr": ""},
    ]
    assert lexicon.cefr_distribution(rows) == [
        {"cefr": "A1", "count": 2},
        {"cefr": "B1", "count": 1},
    ]


def test_summary_counts_statuses_and_cefr():
    rows = [
        {"appearances": 0, "exposures": 0, "cefr": "A1"},
        {"appearances": 0, "exposures": 1, "cefr": "A1"},
        {"appearances": 3, "production_days": 2, "exposures": 0, "cefr": "A2"},
    ]
    s = lexicon.summary(rows)
    assert s["total"] == 3
    assert s["learning"] == 1
    assert s["known"] == 1
    assert s["mastered"] == 1
    assert s["weak"] == 0
    assert s["by_cefr"] == [
        {"cefr": "A1", "count": 2},
        {"cefr": "A2", "count": 1},
    ]


def test_recognized_not_produced():
    rows = [
        {"word": "travel", "appearances": 0, "exposures": 3},
        {"word": "cat", "appearances": 1, "exposures": 0},
        {"word": "culture", "appearances": 0, "exposures": 0},
    ]
    assert lexicon.recognized_not_produced(rows) == ["travel"]


def test_coverage_indicator_receptive_productive_by_level():
    """P1 (§3.1): el Vocabulary Coverage Indicator distingue receptivo
    (encontrado: input o producción) de productivo (producido ≥1 vez), por
    nivel y frente a las bandas objetivo. Es indicador, no puerta."""
    rows = [
        {"cefr": "Pre-A1", "appearances": 0, "exposures": 0},
        {"cefr": "Pre-A1", "appearances": 0, "exposures": 2},
        {"cefr": "A1", "appearances": 3, "production_days": 2, "exposures": 0},
        {"cefr": "A1", "appearances": 0, "exposures": 1},
        {"cefr": "A2", "appearances": 0, "exposures": 0},
        {"cefr": "C2", "appearances": 0, "exposures": 1},
        {"cefr": "nivel-raro", "appearances": 5, "exposures": 0},  # sin banda
    ]
    cov = lexicon.coverage_indicator(rows)
    # Totales: receptivo suma los niveles con banda declarada (no "nivel-raro").
    assert cov["receptive"] == 4  # Pre-A1(1) + A1(2) + C2(1)
    assert cov["productive"] == 1  # solo la fila mastered A1
    assert cov["mastered"] == 1

    by_level = {lvl["cefr"]: lvl for lvl in cov["by_level"]}
    assert [lvl["cefr"] for lvl in cov["by_level"]] == [
        "Pre-A1",
        "A1",
        "A2",
        "C2",
    ]
    a1 = by_level["A1"]
    assert a1["total"] == 2
    assert a1["receptive"] == 2
    assert a1["productive"] == 1
    assert a1["mastered"] == 1
    assert a1["known"] == 1
    assert a1["learning"] == 0
    # Ratio frente al extremo superior de la banda objetivo (A1 receptivo
    # 700–1000; productivo 400–600).
    assert a1["receptive_pct"] == pytest.approx(round(2 / 1000, 3), rel=1e-6)
    assert a1["productive_pct"] == pytest.approx(round(1 / 600, 3), rel=1e-6)

    assert by_level["Pre-A1"]["receptive"] == 1
    # C2 no declara banda numérica: el ratio es None.
    assert by_level["C2"]["receptive"] == 1
    assert by_level["C2"]["receptive_pct"] is None
    assert by_level["C2"]["productive_pct"] is None
    assert "nivel-raro" not in by_level
