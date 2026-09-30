"""SENSE-CONTEXT-01: robustez del ledger de evidencia (V3.93: arreglado).

V3.92 escribía la evidencia con un read-compute-write sobre un upsert de REEMPLAZO
ciego (`academy_repo.upsert_fsrs_card`) y sin deduplicar. V3.93 cierra los dos
frentes que SENSE-CONTEXT-01 dejó medidos:

- H8 (dedup): la evidencia lleva `evidence_key` (usuario+frase+palabra+intento) con
  índice único parcial; repetir el MISMO intento no vuelve a sumar, dos intentos
  distintos sí;
- H7 (lost update): `academy_repo.upsert_fsrs_card_cas` escribe solo si la
  dificultad guardada es la que se leyó, así que dos evidencias simultáneas suman
  las DOS en vez de pisarse;
- la migración desde un árbol anterior es ADITIVA e idempotente.
"""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest
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


def _seed_word_with_empty_card(user_id: str, word: str) -> None:
    vocabulary_repo.seed_study_items(
        user_id, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    academy_repo.upsert_fsrs_card(
        user_id,
        fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
    )


def _fail(client, uid: str, q: dict, attempt: int = 1):
    return client.post(
        "/api/listening/answer",
        params={"user_id": uid},
        json={
            "question_id": q["id"],
            "answer_index": _wrong_index(q),
            "attempt_number": attempt,
        },
    )


# --- H8: dedup por intento; dos intentos distintos sí apilan -----------------


def test_distinct_attempts_stack_difficulty_and_evidence_rows(monkeypatch, tmp_path):
    """Dos INTENTOS distintos = DOS evidencias y DOS subidas (y es lo correcto).

    La dedup es por intento (`evidence_key`), no por palabra: fallar la frase en
    el intento 1 y volver a fallarla en el intento 2 son dos sucesos, y contarlos
    es la lectura honesta. Repetir el MISMO intento no suma (test siguiente).
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q)
        _fail(client, uid, q, attempt=2)
    rows = listening_repo.list_difficulty_evidence(uid)
    assert [r["word"] for r in rows] == [word, word]
    assert rows[1]["difficulty_after"] > rows[0]["difficulty_after"]
    card = academy_repo.get_fsrs_card(uid, "lexicon", word)
    assert card["difficulty"] == pytest.approx(6.2, abs=0.001)
    assert card["reps"] == 0  # la evidencia nunca finge una recuperación


def test_repeating_the_same_attempt_does_not_double_count(monkeypatch, tmp_path):
    """V3.93: la evidencia es idempotente por intento (`evidence_key`).

    Un reintento de red o un doble toque repiten el MISMO `attempt_number`: el
    ledger no inserta una segunda fila y la carta no vuelve a subir.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q)  # intento 1
        _fail(client, uid, q)  # el MISMO intento 1, otra vez
    rows = listening_repo.list_difficulty_evidence(uid)
    assert len(rows) == 1
    card = academy_repo.get_fsrs_card(uid, "lexicon", word)
    assert card["difficulty"] == pytest.approx(5.6, abs=0.001)


# --- H7: el CAS impide el lost update concurrente ---------------------------


def test_cas_prevents_lost_update(monkeypatch, tmp_path):
    """V3.93: dos evidencias sobre la MISMA base suman las DOS, no se pisan.

    Con el upsert ciego de V3.92, ambas calculaban `5.6` y la segunda pisaba a la
    primera (lost update). Con el CAS, la segunda parte de una base obsoleta, NO
    escribe, y el reintento con la carta fresca suma hasta `6.2`.
    """
    uid = _setup(monkeypatch, tmp_path)
    base = fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank")
    now = datetime.now(timezone.utc).isoformat()
    academy_repo.upsert_fsrs_card(uid, base)
    first = fsrs.apply_difficulty_evidence(base, source="listening-evidence", now=now)
    second = fsrs.apply_difficulty_evidence(base, source="listening-evidence", now=now)
    assert academy_repo.upsert_fsrs_card_cas(
        uid, first, expected_difficulty=5.0
    ) is True
    # La segunda parte de la MISMA base ya obsoleta: el CAS la rechaza.
    assert academy_repo.upsert_fsrs_card_cas(
        uid, second, expected_difficulty=5.0
    ) is False
    card = academy_repo.get_fsrs_card(uid, "lexicon", "bank")
    assert card["difficulty"] == pytest.approx(5.6, abs=0.001)
    # Reintento con la carta fresca: la segunda evidencia SÍ se cobra.
    retry = fsrs.apply_difficulty_evidence(card, source="listening-evidence", now=now)
    assert academy_repo.upsert_fsrs_card_cas(
        uid, retry, expected_difficulty=5.6
    ) is True
    card = academy_repo.get_fsrs_card(uid, "lexicon", "bank")
    assert card["difficulty"] == pytest.approx(6.2, abs=0.001)


# --- Migración aditiva e idempotente desde un árbol anterior ----------------


@pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 35, 0),
    reason="DROP COLUMN necesita SQLite >= 3.35 para simular el árbol anterior",
)
def test_migration_adds_the_v392_pieces_from_a_previous_tree(monkeypatch, tmp_path):
    """Una BD sin `sense_json` ni el ledger se migra sola al arrancar."""
    _setup(monkeypatch, tmp_path)
    with closing(db._conn()) as conn, conn:
        conn.execute("DROP TABLE listening_difficulty_evidence")
        conn.execute("ALTER TABLE vocabulary DROP COLUMN sense_json")
    # Re-arranque: la migración vuelve a añadir ambas piezas sin duplicar nada.
    db.init_db()
    with closing(db._conn()) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        vocab_cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        evidence_cols = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(listening_difficulty_evidence)"
            )
        }
    assert "listening_difficulty_evidence" in tables
    assert "sense_json" in vocab_cols
    for column in ("evidence_key", "sense_key", "sense_match", "sense_reason"):
        assert column in evidence_cols
    db.init_db()  # idempotente
    with closing(db._conn()) as conn:
        vocab_cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
    assert "sense_json" in vocab_cols
