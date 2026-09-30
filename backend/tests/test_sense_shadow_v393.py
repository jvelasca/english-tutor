"""SENSE-CONTEXT-01 (V3.93): el dark launch sense-aware del puente.

V3.93 consulta el Sense Resolver al registrar evidencia de dificultad y GUARDA su
veredicto en el ledger (`sense_key`/`sense_match`/`sense_reason`), pero NO cambia
qué evidencia se genera: eso sigue siendo exactamente lo de V3.92. Estos tests fijan
las dos caras de esa frontera:

- el veredicto se registra (`matched` / `ambiguous`, con su razón);
- la evidencia NO se filtra: una acepción NO declarada sigue generando evidencia,
  que es justo lo que hay que medir antes de aplicar la política (enforce).
"""
import json
from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs
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


def _seed_word(user_id: str, word: str, sense: dict | None = None) -> None:
    vocabulary_repo.seed_study_items(
        user_id, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    if sense is not None:
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "UPDATE vocabulary SET sense_json = ? "
                "WHERE user_id = ? AND word = ?",
                (json.dumps(sense), user_id, word),
            )
    academy_repo.upsert_fsrs_card(
        user_id,
        fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
    )


def _fail(client, uid: str, q: dict):
    return client.post(
        "/api/listening/answer",
        params={"user_id": uid},
        json={
            "question_id": q["id"],
            "answer_index": _wrong_index(q),
            "attempt_number": 1,
        },
    )


def _rows(uid: str) -> list[dict]:
    return listening_repo.list_difficulty_evidence(uid)


# --- El índice de acepciones del léxico -------------------------------------


def test_sense_index_gathers_only_declared_senses():
    known = [
        {"word": "bank", "sense": {"pos": "noun", "gloss": "money"}},
        {"word": "anchor", "sense": {}},
        {"word": "river", "sense": {"pos": "noun", "gloss": "water"}},
    ]
    assert set(bridge.sense_index(known)) == {"bank", "river"}


def test_sense_index_is_total_with_junk():
    assert bridge.sense_index(None) == {}
    assert bridge.sense_index(["bank", 7]) == {}


# --- Dark launch: el veredicto se registra, la evidencia NO se filtra --------


def test_undeclared_sense_is_recorded_as_ambiguous_without_gating(
    monkeypatch, tmp_path
):
    """Sin acepción declarada la evidencia se SIGUE generando (comportamiento V3.92).

    Es el hallazgo clave del dark launch: si se aplicara la política, esta evidencia
    se suprimiría. Aquí se comprueba que todavía NO se suprime y que el ledger deja
    el veredicto medible.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word(uid, word)  # sin `sense_json`: acepción no declarada
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == 1  # NO se filtra
    rows = _rows(uid)
    assert len(rows) == 1
    assert rows[0]["sense_match"] == "ambiguous"
    assert rows[0]["sense_reason"] == "declared:none"
    assert rows[0]["sense_key"] == ""


def test_declared_sense_overlapping_the_phrase_is_matched(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, sense={"lemma": word, "pos": "noun", "gloss": text})
    with TestClient(app) as client:
        _fail(client, uid, q)
    rows = _rows(uid)
    assert len(rows) == 1
    assert rows[0]["sense_match"] == "matched"
    assert rows[0]["sense_reason"] == "gloss:declared"
    assert rows[0]["sense_key"].startswith(word + "|")


def test_declared_sense_without_alternatives_is_ambiguous(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word(
        uid, word, sense={"lemma": word, "pos": "noun", "gloss": "zzz unrelated"}
    )
    with TestClient(app) as client:
        _fail(client, uid, q)
    rows = _rows(uid)
    assert rows[0]["sense_match"] == "ambiguous"
    assert rows[0]["sense_reason"] == "alternatives:none"


def test_shadow_columns_are_additive_and_default_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q)
    row = _rows(uid)[0]
    assert row["evidence_key"] == listening_repo.evidence_key(uid, q["id"], word, 1)
    assert {"sense_key", "sense_match", "sense_reason"} <= set(row)
