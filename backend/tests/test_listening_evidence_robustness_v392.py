"""SENSE-CONTEXT-01: robustez del ledger de evidencia (diseño + caracterización).

V3.92 escribe la evidencia de dificultad con un read-compute-write:
`domain/listening.py::_apply_difficulty_evidence` lee la carta, calcula la subida y
la persiste con `academy_repo.upsert_fsrs_card`, que es un upsert de REEMPLAZO
ciego. Estos tests fijan lo que eso significa hoy, para que la fase de robustez de
V3.93+ tenga una línea base:

- H8: la evidencia NO se deduplica; el mismo fallo repetido suma `+0.6` cada vez;
- H7: dos lecturas concurrentes del mismo estado pierden una subida (lost update);
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


# --- H8: sin deduplicación, cada fallo apila --------------------------------


def test_repeated_failures_stack_difficulty_and_evidence_rows(monkeypatch, tmp_path):
    """Dos fallos = DOS evidencias y DOS subidas. Es el comportamiento actual.

    No es un defecto de contrato (la tabla es append-only y `count` cuenta cartas,
    no eventos), pero sí un límite a decidir antes de cablear el resolver: un
    reintento inmediato no debería valer lo mismo que un fallo distinto.
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


# --- H7: el read-compute-write pierde una subida concurrente ----------------


def test_two_updates_from_the_same_base_lose_one_increment(monkeypatch, tmp_path):
    """Caracteriza el lost update: el upsert reemplaza, no acumula.

    Dos peticiones que leen la MISMA carta base calculan `5.6` las dos; la segunda
    escritura pisa a la primera y la dificultad queda en `5.6` en vez de `6.2`.
    El test fija el riesgo (no lo arregla: el arreglo es de V3.93+).
    """
    uid = _setup(monkeypatch, tmp_path)
    base = fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank")
    now = datetime.now(timezone.utc).isoformat()
    first = fsrs.apply_difficulty_evidence(base, source="listening-evidence", now=now)
    second = fsrs.apply_difficulty_evidence(base, source="listening-evidence", now=now)
    academy_repo.upsert_fsrs_card(uid, first)
    academy_repo.upsert_fsrs_card(uid, second)  # pisa el resultado del primero
    card = academy_repo.get_fsrs_card(uid, "lexicon", "bank")
    assert card["difficulty"] == pytest.approx(5.6, abs=0.001)
    assert card["difficulty"] != pytest.approx(6.2, abs=0.001)


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
    assert "listening_difficulty_evidence" in tables
    assert "sense_json" in vocab_cols
    db.init_db()  # idempotente
    with closing(db._conn()) as conn:
        vocab_cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
    assert "sense_json" in vocab_cols
