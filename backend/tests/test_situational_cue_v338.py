"""Tests de aceptación de V3.38 — el 4.º peldaño situacional (`situation`).

V3.37 dejó la escalera de recall en `translation < definition < cloze` y anotó
que el peldaño que FALTABA —un enunciado situacional autorado— exigía extender
el CONTRATO DE CONTENIDO de la caché (`generator_version`, V3.30) porque no se
puede derivar de lo que ya existe. V3.38 lo cierra:

- el contrato de contenido gana `situation` (bump 1.1.0 -> 1.2.0), validado de
  forma determinista (un solo hueco `_____`, sin spoiler, acotado);
- `dictionary_entries` persiste la columna de forma aditiva e idempotente;
- `recall.RECALL_CUES` gana `situation` como TECHO de la escalera, con apoyo
  `guided`, y `next_recall_rung` solo llega a él con `cloze` consolidado;
- el GET/POST del drill lo sirven y lo declaran en el ledger
  (`drill:recall:situation`), y la cola de repaso lo recomienda cuando el
  contenido está cacheado, degradando hacia más apoyo cuando no lo está.

Se cubre la capa pura, la persistencia/migración, la escalera y el e2e HTTP.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from domain import review as review_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_content, fsrs, lexicon, recall


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _word(
    word: str,
    translation: str,
    *,
    definition: str = "",
    situation: str = "",
) -> None:
    """Entrada de caché FRESCA (versión actual) para no pagar el modelo."""
    dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=definition or f"the meaning of {word}",
        translation=translation,
        situation=situation,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )


def _payload(situation: object = None) -> str:
    body: dict = {
        "pos": "noun",
        "definition": "A small domesticated carnivorous mammal.",
        "translation": "gato",
    }
    if situation is not None:
        body["situation"] = situation
    return json.dumps(body)


def _evidence(uid: str, word: str) -> list[dict]:
    return evidence_repo.list_evidence(uid, word, target_type="lexicon")


def _post_recall(client: TestClient, uid: str, word: str, answer: str, cue: str):
    return client.post(
        "/api/vocabulary/drill/recall-attempt",
        params={"user_id": uid},
        json={"word": word, "answer": answer, "cue": cue},
    )


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    now = datetime.now(timezone.utc)
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": (now - timedelta(days=days_ago)).isoformat(),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


# --- Contrato de contenido (puro) -------------------------------------------


def test_generator_version_and_prompt_declare_the_situation_field():
    # V3.39: el contrato de contenido gana la dirección ES→EN y la versión sube
    # para regenerar una sola vez la caché previa bajo la política nueva.
    # V3.44: sube a 1.4.0 al ganar `senses` (modelo de sentidos del scoring).
    assert dictionary_content.GENERATOR_VERSION == "1.4.0"
    assert "situation" in dictionary_content._SYSTEM_PROMPT
    assert "situation" in dictionary_content._REVERSE_SYSTEM_PROMPT
    # V3.44 (P1-01): el contrato de contenido también declara `senses`.
    assert "senses" in dictionary_content._SYSTEM_PROMPT
    assert "senses" in dictionary_content._REVERSE_SYSTEM_PROMPT
    assert dictionary_content.SITUATION_BLANK == "_____"


def test_parse_content_extracts_a_valid_situation():
    out = dictionary_content.parse_content(
        _payload("At the vet, the _____ was purring loudly."),
        word="cat",
    )
    assert out["situation"] == "At the vet, the _____ was purring loudly."


def test_parse_normalizes_the_blank_run():
    out = dictionary_content.parse_content(_payload("The ____ ran away fast."))
    assert out["situation"] == "The _____ ran away fast."


def test_parse_leaves_situation_empty_when_absent():
    out = dictionary_content.parse_content(_payload())
    assert out["situation"] == ""


def test_parse_drops_situation_without_a_blank():
    out = dictionary_content.parse_content(_payload("The animal is on the mat."))
    assert out["situation"] == ""


def test_parse_drops_situation_with_more_than_one_blank():
    out = dictionary_content.parse_content(_payload("A _____ and a _____."))
    assert out["situation"] == ""


def test_parse_drops_oversized_situation():
    raw = _payload("word " * 60 + "_____")
    assert len(raw) > dictionary_content.MAX_SITUATION_CHARS
    out = dictionary_content.parse_content(raw)
    assert out["situation"] == ""


def test_parse_drops_situation_that_leaks_the_word():
    out = dictionary_content.parse_content(
        _payload("The cat sleeps on the _____ all day."),
        word="cat",
    )
    assert out["situation"] == ""


def test_generate_content_validates_the_situation_against_the_word():
    async def _fake(_word: str, _model: str | None) -> str:
        return _payload("The _____ purred on the sofa.")

    out = asyncio.run(
        dictionary_content.generate_content("cat", fetcher=_fake)
    )
    assert out["situation"] == "The _____ purred on the sofa."


# --- Endurecimiento del validador (V3.38.1, P2-01) --------------------------


def test_situation_validator_rejects_a_second_sentence():
    out = dictionary_content.parse_content(
        _payload("The _____ purred softly. Then it slept.")
    )
    assert out["situation"] == ""


def test_situation_validator_accepts_a_single_closing_mark():
    out = dictionary_content.parse_content(_payload("The _____ purred loudly!"))
    assert out["situation"] == "The _____ purred loudly!"


def test_situation_validator_rejects_regular_morphological_leaks():
    # Cada caso contiene una diana en forma derivada REGULAR (plural, 3.ª
    # persona, pasado, gerundio con e-drop/duplicación, adverbio o posesivo).
    leaks = (
        ("dog", "The dogs barked at the _____."),
        ("study", "He _____ hard and studied all night."),
        ("stop", "They _____ here and stopped the car."),
        ("make", "She is _____ a cake while making coffee."),
        ("quick", "He _____ left and quickly returned."),
        ("friend", "My friend's car was near the _____."),
    )
    for word, situation in leaks:
        out = dictionary_content.parse_content(_payload(situation), word=word)
        assert out["situation"] == "", (word, situation)


def test_situation_validator_keeps_a_legit_situation():
    out = dictionary_content.parse_content(
        _payload("At the vet, the _____ was purring loudly."), word="cat"
    )
    assert out["situation"] == "At the vet, the _____ was purring loudly."


# --- Persistencia y migración -----------------------------------------------


def test_repository_round_trips_the_situation(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert dictionary_repo.save_entry(
        "cat",
        pos="noun",
        definition="def",
        translation="gato",
        situation="The _____ purred.",
        generator_version="1.2.0",
    )
    stored = dictionary_repo.get_entry("cat")
    assert stored["situation"] == "The _____ purred."


def test_migration_adds_the_column_idempotently(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # segunda ejecución: no debe fallar ni duplicar la columna
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(dictionary_entries)")
        }
    finally:
        conn.close()
    assert "situation" in cols


def test_migration_backfills_situation_on_a_legacy_database(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "CREATE TABLE dictionary_entries ("
        "word TEXT PRIMARY KEY, pos TEXT NOT NULL DEFAULT '', "
        "definition TEXT NOT NULL DEFAULT '', "
        "translation TEXT NOT NULL DEFAULT '', "
        "generator_version TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT '')"
    )
    conn.execute(
        "INSERT INTO dictionary_entries VALUES "
        "('cat','noun','def','gato','1.1.0',"
        "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    db.init_db()

    stored = dictionary_repo.get_entry("cat")
    assert stored["situation"] == ""
    assert stored["translation"] == "gato"


# --- Escalera de recall (puro) ----------------------------------------------


def test_situation_is_the_ceiling_of_the_ladder():
    assert recall.RECALL_CUES[-1] == "situation"
    assert recall.RECALL_CUE_SUPPORT["situation"] == "guided"
    assert set(recall.RECALL_CUE_SUPPORT) == set(recall.RECALL_CUES)


def test_recall_prompt_serves_the_cached_situation():
    entries = [
        {
            "word": "cat",
            "translation": "gato",
            "definition": "a small mammal",
            "situation": "At the vet, the _____ was purring.",
        }
    ]
    assert recall.recall_prompt_for("cat", entries, cue="situation") == {
        "word": "cat",
        "cue": "At the vet, the _____ was purring.",
        "cue_kind": "situation",
    }


def test_recall_prompt_without_a_situation_is_none():
    entries = [
        {"word": "cat", "translation": "gato", "definition": "a small mammal"}
    ]
    assert recall.recall_prompt_for("cat", entries, cue="situation") is None


def test_recall_prompt_rejects_a_situation_that_leaks_the_word():
    entries = [
        {
            "word": "cat",
            "translation": "gato",
            "situation": "The cat likes the _____ by the window.",
        }
    ]
    assert recall.recall_prompt_for("cat", entries, cue="situation") is None


def test_recall_prompt_revalidates_a_stale_situation():
    """V3.38.1: una situación cacheada por reglas laxas no se sirve."""
    entries = [
        {
            "word": "cat",
            "translation": "gato",
            "situation": "The _____ purred softly. Then it slept.",
        }
    ]
    assert recall.recall_prompt_for("cat", entries, cue="situation") is None


def test_recall_prompt_rejects_a_morphological_leak():
    entries = [
        {
            "word": "dog",
            "translation": "perro",
            "situation": "The dogs barked near the _____.",
        }
    ]
    assert recall.recall_prompt_for("dog", entries, cue="situation") is None


def test_next_recall_rung_reaches_situation_after_cloze():
    evidence = {
        "recall_rungs": {"translation": 2, "definition": 2, "cloze": 2},
        "recall_rung_days": {"translation": 2, "definition": 2, "cloze": 2},
    }
    assert recall.next_recall_rung({}, evidence) == "situation"


def test_resolve_recall_cue_degrades_from_situation_toward_support():
    assert recall.resolve_recall_cue("situation", {"cloze"}) == "cloze"
    assert recall.resolve_recall_cue("situation", {"translation"}) == "translation"
    assert recall.resolve_recall_cue("situation", set()) is None


# --- Cola de repaso ---------------------------------------------------------


def test_review_queue_item_can_recommend_the_situation_rung():
    row = {
        "word": "river",
        "exposure_count": 2,
        "exposure_days": 2,
        "production_count": 1,
        "production_days": 1,
        "speaking_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    card = {"target_id": "river", "due_at": "2026-09-09T10:00:00+00:00"}
    evidence = {
        "recall_rungs": {"translation": 2, "definition": 2, "cloze": 2},
        "recall_rung_days": {"translation": 2, "definition": 2, "cloze": 2},
    }
    item = lexicon.review_queue_item(
        row,
        card,
        now="2026-09-09T10:00:00+00:00",
        evidence=evidence,
        available_cues={"translation", "definition", "cloze", "situation"},
    )
    assert item["activity"] == "recall"
    assert item["recommended_cue"] == "situation"
    # La cola nunca sirve el cue ni la forma esperada (premisa 21).
    assert "cue" not in item
    assert "expected" not in item


def test_review_queue_item_degrades_when_the_situation_is_not_cached():
    row = {
        "word": "river",
        "exposure_count": 2,
        "exposure_days": 2,
        "production_count": 1,
        "production_days": 1,
        "speaking_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    card = {"target_id": "river", "due_at": "2026-09-09T10:00:00+00:00"}
    evidence = {
        "recall_rungs": {"translation": 2, "definition": 2, "cloze": 2},
        "recall_rung_days": {"translation": 2, "definition": 2, "cloze": 2},
    }
    item = lexicon.review_queue_item(
        row,
        card,
        now="2026-09-09T10:00:00+00:00",
        evidence=evidence,
        available_cues={"translation", "cloze"},
    )
    assert item["recommended_cue"] == "cloze"


def test_available_recall_cues_read_the_cached_situation(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _word("cat", "gato", situation="The _____ purred on the sofa.")
    cues = asyncio.run(review_domain._available_recall_cues(["cat"]))
    assert "situation" in cues["cat"]


def test_available_recall_cues_omit_the_situation_without_content(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    _word("cat", "gato")
    cues = asyncio.run(review_domain._available_recall_cues(["cat"]))
    assert "situation" not in cues["cat"]


# --- Contrato HTTP ----------------------------------------------------------


def test_get_prompt_serves_the_situation_rung(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _word("cat", "gato", situation="At the vet, the _____ was purring.")
    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "cat", "cue": "situation"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
    assert body["available"] is True
    assert body["cue_kind"] == "situation"
    assert body["support_level"] == "guided"
    assert body["cue"] == "At the vet, the _____ was purring."
    assert "expected" not in body


def test_get_prompt_without_a_situation_degrades_without_error(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _word("cat", "gato")
    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "cat", "cue": "situation"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] is False
    assert body["cue"] == ""
    assert body["support_level"] == "guided"


def test_recall_attempt_with_situation_records_guided_evidence(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _word("cat", "gato", situation="At the vet, the _____ was purring.")
    with TestClient(app) as client:
        res = _post_recall(client, uid, "cat", "cat", cue="situation")
    assert res.status_code == 200, res.text
    assert res.json()["correct"] is True
    row = _evidence(uid, "cat")[0]
    assert row["skill"] == "recall"
    assert row["support_level"] == "guided"
    assert row["activity_id"] == "drill:recall:situation"


def test_recall_attempt_without_a_situation_is_422_without_event(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _word("cat", "gato")
    with TestClient(app) as client:
        res = _post_recall(client, uid, "cat", "cat", cue="situation")
    assert res.status_code == 422
    assert _evidence(uid, "cat") == []


def test_dictionary_lookup_exposes_the_situation(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _word("cat", "gato", situation="At the vet, the _____ was purring.")
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": "cat"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
    assert data["situation"] == "At the vet, the _____ was purring."


def test_review_queue_route_recommends_the_situation_when_cached(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _word("student", "estudiante", situation="At school, the _____ raised a hand.")
    vocabulary_repo.record_exposures(uid, ["student"])
    vocabulary_repo.record_recalls(uid, ["student"])
    vocabulary_repo.record_production(uid, ["student"], channel="speaking")
    for day in (
        "2026-09-01T10:00:00+00:00",
        "2026-09-02T10:00:00+00:00",
        # V3.38.1 (P1-04): 3 éxitos independientes en 3 días.
        "2026-09-03T10:00:00+00:00",
    ):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="student",
            task="production",
            activity_id="speaking_task",
            success=True,
            support_level="independent",
            occurred_at=day,
        )
    _due_lexicon_card(uid, "student", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        res = client.get("/api/learning/review", params={"user_id": uid})
        assert res.status_code == 200, res.text
        item = res.json()["items"][0]

    assert item["activity"] == "recall"
    assert item["reason"] == "automatic_maintenance"
    assert item["recommended_cue"] == "situation"
    assert "cue" not in item
    assert "expected" not in item
