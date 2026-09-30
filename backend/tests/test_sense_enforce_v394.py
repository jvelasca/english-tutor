"""SENSE-CONTEXT-01 (V3.94, ENFORCE): la evidencia de Listening DECIDE con la acepción.

V3.94 cierra el dark launch de V3.93: el Sense Resolver no solo registra su veredicto,
**decide**. La política es MÍNIMA y declarada (ver `allows_difficulty_evidence`): la
evidencia se suprime SOLO ante un `mismatch` PROBADO —el contexto usa una acepción
DISTINTA a la aprendida— y el suceso se registra como `new_sense_exposure`; todo lo
demás conserva la evidencia de V3.92.

Qué se fija aquí:

1. `listening_bridge.alternatives_index` reúne las acepciones de la caché (pura);
2. con alternativas, un `mismatch` es ALCANZABLE y, en producción, NO sube la carta:
   el intento queda registrado como exposición y la respuesta lo publica;
3. un `matched` conserva la evidencia y NO expone;
4. repetir el MISMO intento no vuelve a exponer (idempotencia por `attempt_id`);
5. `daily_plan.day_metrics` NO cuenta una exposición como dificultad.
"""
import json
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import listening as listening_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import daily_plan, fsrs
from services import listening as listening_svc
from services import listening_bridge as bridge
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _receptive_question() -> dict:
    for q in QUESTION_BANK:
        if q["skill"] not in ("dictation", "shadowing") and listening_svc.audio_text(q):
            return q
    raise AssertionError("banco sin ítems receptivos con texto")


def _wrong_index(q: dict) -> int:
    return (q["answer_index"] + 1) % len(q["options"])


def _phrase_word(q: dict) -> str:
    units = [
        u for u in bridge.phrase_units(listening_svc.audio_text(q)) if len(u) >= 4
    ]
    assert units, "frase demasiado corta para la sonda"
    return units[0]


def _fail(client, uid: str, q: dict, attempt: int = 1, attempt_id: str = ""):
    payload = {
        "question_id": q["id"],
        "answer_index": _wrong_index(q),
        "attempt_number": attempt,
    }
    if attempt_id:
        payload["attempt_id"] = attempt_id
    return client.post("/api/listening/answer", params={"user_id": uid}, json=payload)


def _seed_word(user_id: str, word: str, sense: dict) -> None:
    """Da de alta la palabra con su ACEPCIÓN declarada y una carta FSRS nueva."""
    vocabulary_repo.seed_study_items(
        user_id, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "UPDATE vocabulary SET sense_json = ? WHERE user_id = ? AND word = ?",
            (json.dumps(sense), user_id, word),
        )
    academy_repo.upsert_fsrs_card(
        user_id, fsrs.empty_card(target_type="lexicon", target_id=word, label=word)
    )


def _seed_alternatives(word: str, senses: list[dict]) -> None:
    """Puebla la caché del diccionario con las acepciones conocidas de `word`."""
    dictionary_repo.save_entry(
        word, pos="noun", senses=senses, generator_version="1.7.0"
    )


def _difficulty(uid: str, word: str) -> float:
    return float(academy_repo.get_fsrs_card(uid, "lexicon", word)["difficulty"])


# --- El índice de alternativas del diccionario -------------------------------


def test_alternatives_index_gathers_known_senses():
    entries = [
        {"word": "Bank", "senses": [
            {"pos": "noun", "gloss": "money"},
            {"pos": "noun", "gloss": "river side"},
        ]},
        {"word": "anchor", "senses": []},
        {"word": "river", "senses": [{"pos": "noun", "gloss": "water"}]},
    ]
    index = bridge.alternatives_index(entries)
    assert set(index) == {"bank", "river"}
    assert len(index["bank"]) == 2


def test_alternatives_index_is_total_with_junk():
    assert bridge.alternatives_index(None) == {}
    assert bridge.alternatives_index(["bank", 7]) == {}
    assert bridge.alternatives_index([{"word": "", "senses": [{"pos": "noun"}]}]) == {}
    assert bridge.alternatives_index([{"word": "x", "senses": "nope"}]) == {}


# --- ENFORCE: el `mismatch` suprime la evidencia y expone --------------------


def test_mismatch_suppresses_the_card_and_exposes_a_new_sense(monkeypatch, tmp_path):
    """La frase usa OTRA acepción: la carta NO se toca y la respuesta expone.

    Antes de V3.94 esto subía la dificultad de la acepción aprendida (el defecto que
    SENSE-CONTEXT-01 midió). Ahora se registra como exposición y la carta queda
    intacta.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    # La acepción declarada NO aparece en la frase (glosa ajena)...
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": "zzz unrelated"})
    # ...y la caché conoce una alternativa que SÍ (su glosa es la propia frase).
    _seed_alternatives(word, [{"pos": "noun", "gloss": text}])
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == 0
    assert body["new_sense_exposure"]["words"] == [word]
    assert body["new_sense_exposure"]["count"] == 1
    assert _difficulty(uid, word) == pytest.approx(5.0, abs=0.001)  # NO se tocó
    rows = listening_repo.list_difficulty_evidence(uid)
    assert len(rows) == 1
    assert rows[0]["sense_match"] == "mismatch"
    # La fila NO aplicó dificultad: es el registro de la exposición, no un castigo.
    assert rows[0]["difficulty_before"] == rows[0]["difficulty_after"]


def test_matched_sense_keeps_evidence_and_does_not_expose(monkeypatch, tmp_path):
    """La frase usa la acepción aprendida: evidencia normal, sin exposición."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": text})
    _seed_alternatives(word, [{"pos": "noun", "gloss": "zzz unrelated"}])
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == 1
    assert body["new_sense_exposure"]["count"] == 0
    assert _difficulty(uid, word) == pytest.approx(5.6, abs=0.001)


def test_repeating_the_same_attempt_does_not_double_expose(monkeypatch, tmp_path):
    """El mismo `attempt_id` no vuelve a exponer (idempotencia del ledger)."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": "zzz unrelated"})
    _seed_alternatives(word, [{"pos": "noun", "gloss": text}])
    with TestClient(app) as client:
        first = _fail(client, uid, q, attempt_id="A1").json()
        second = _fail(client, uid, q, attempt_id="A1").json()
    assert first["new_sense_exposure"]["words"] == [word]
    assert second["new_sense_exposure"]["count"] == 0
    assert len(listening_repo.list_difficulty_evidence(uid)) == 1


# --- La métrica del día no cuenta una exposición como dificultad -------------


def test_day_metrics_separates_exposures_from_difficulty():
    day = "2026-09-29"
    bridge_rows = [
        {"word": "bank", "sense_match": "matched", "created_at": f"{day}T09:00:00"},
        {"word": "river", "sense_match": "", "created_at": f"{day}T09:05:00"},
        {"word": "bank", "sense_match": "mismatch", "created_at": f"{day}T09:10:00"},
    ]
    metrics = daily_plan.day_metrics([], [], [], day, bridge_rows)
    assert metrics["difficulty_evidence"] == 2
    assert metrics["words_flagged"] == 2
    assert metrics["sense_exposures"] == 1
