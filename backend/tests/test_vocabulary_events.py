"""Tests del ledger léxico por forma de superficie (V3.26, Eje B/F-B2).

La historia (`vocabulary_events`) es un ledger append-only complementario a los
contadores agregados de `vocabulary`: un evento por palabra producida/expuesta/
recuperada, escrito en la MISMA transacción del contador. Invariantes:
- la semántica de conteo es idéntica (presencia en un mensaje/intento, nunca
  frecuencia de tokens);
- el seed curricular NO crea eventos;
- la historia empieza en V3.26 (sin backfill); los contadores conservan la
  verdad agregada.
"""
import sqlite3
from datetime import date, timedelta

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import lexicon


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _history(user_id: str, word: str | None = None) -> list[dict]:
    return vocabulary_repo.list_vocabulary_events(user_id, word=word)


def _backdate_first_seen(user_id: str, word: str, days_ago: int) -> None:
    """Retrasa `first_seen`/`last_seen` para simular una palabra con ancla vieja
    (permite acreditar recuperación DEMORADA sin esperar el intervalo)."""
    when = (date.today() - timedelta(days=days_ago)).isoformat() + "T00:00:00+00:00"
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            "UPDATE vocabulary SET first_seen = ?, last_seen = ? "
            "WHERE user_id = ? AND word = ?",
            (when, when, user_id, word),
        )
        conn.commit()
    finally:
        conn.close()


def test_vocabulary_events_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(
            "PRAGMA foreign_key_list(vocabulary_events)"
        ).fetchall()
    finally:
        conn.close()
    assert ("users", "user_id") in {(row[2], row[3]) for row in rows}


def test_production_writes_one_event_per_word_per_message(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(
        user_id, ["cat", "dog"], channel="speaking", activity="speaking_mission"
    )
    assert vocabulary_repo.record_production(
        user_id, ["cat"], channel="chat", activity="free_chat"
    )
    produced = [e for e in _history(user_id) if e["event_type"] == "produced"]
    assert len(produced) == 3  # cat en 2 mensajes + dog en 1
    # Un evento por superficie, con su canal y actividad.
    cat_events = [e for e in produced if e["word"] == "cat"]
    assert len(cat_events) == 2
    assert {e["channel"] for e in cat_events} == {"speaking", "chat"}
    assert {e["activity"] for e in cat_events} == {"speaking_mission", "free_chat"}
    # La unidad canónica acompaña a la superficie (aquí coincide con la forma).
    assert all(e["lexical_unit"] == e["word"] for e in produced)


def test_exposures_write_exposed_events(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_exposures(user_id, ["cat", "dog"])
    exposed = [e for e in _history(user_id) if e["event_type"] == "exposed"]
    assert len(exposed) == 2
    assert {e["word"] for e in exposed} == {"cat", "dog"}
    # Sin producción no hay evento `produced`.
    assert not [e for e in _history(user_id) if e["event_type"] == "produced"]


def test_retrieval_event_only_when_delayed_ok(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(user_id, ["cat"], channel="chat")
    # Antes del intervalo demorado no hay recuperación ni evento.
    assert vocabulary_repo.record_retrievals(user_id, ["cat"]) is True
    assert not [
        e for e in _history(user_id) if e["event_type"] == "retrieval"
    ]
    # Con ancla demorada (>= RETENTION_MIN_INTERVAL_DAYS) sí acredita.
    assert lexicon.RETENTION_MIN_INTERVAL_DAYS >= 1
    _backdate_first_seen(user_id, "cat", days_ago=2)
    assert vocabulary_repo.record_retrievals(user_id, ["cat"]) is True
    retrieval_events = [
        e for e in _history(user_id) if e["event_type"] == "retrieval"
    ]
    assert len(retrieval_events) == 1
    assert retrieval_events[0]["word"] == "cat"
    row = next(
        r for r in vocabulary_repo.get_vocabulary(user_id) if r["word"] == "cat"
    )
    assert row["retrieval_successes"] == 1


def test_event_parity_with_production_counters(monkeypatch, tmp_path):
    """Invariante F-B2: nº de eventos `produced` por superficie == contador."""
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(
        user_id, ["cat", "dog"], channel="speaking", activity="speaking_task"
    )
    assert vocabulary_repo.record_production(
        user_id, ["cat"], channel="chat", activity="free_chat"
    )
    assert vocabulary_repo.record_production(
        user_id, ["cat"], channel="writing", activity="writing_task"
    )
    events = [e for e in _history(user_id) if e["event_type"] == "produced"]
    from collections import Counter

    counts = Counter(e["word"] for e in events)
    assert counts["cat"] == 3
    assert counts["dog"] == 1


def test_seed_curriculum_creates_no_events(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.seed_curriculum_items(
        user_id,
        [
            {"word": "cat", "lemma": "cat", "cefr": "A1", "level_id": "a1",
             "objective_id": "o1", "kind": "word"},
        ],
    )
    assert _history(user_id) == []


def test_history_filters_by_word_and_paginates(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(
        user_id, ["cat", "dog", "bird", "fish", "eagle"], channel="chat"
    )
    assert len(_history(user_id, word="cat")) == 1
    assert [e["word"] for e in _history(user_id, word="cat")] == ["cat"]
    page = vocabulary_repo.list_vocabulary_events(user_id, limit=2, offset=0)
    assert len(page) == 2
    assert len(vocabulary_repo.list_vocabulary_events(user_id, limit=2, offset=4)) == 1


def test_events_unknown_user_and_empty(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert _history("no-existe") == []
    assert vocabulary_repo.record_production("no-existe", ["cat"]) is False


def test_history_endpoint_returns_events(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(
        user_id, ["cat", "dog"], channel="speaking", activity="speaking_mission"
    )
    client = TestClient(app)
    got = client.get("/api/vocabulary/history", params={"user_id": user_id})
    assert got.status_code == 200
    body = got.json()
    assert isinstance(body, list) and len(body) == 2
    event = body[0]
    assert event["word"] == "dog" or event["word"] == "cat"
    assert event["event_type"] == "produced"
    assert event["channel"] == "speaking"
    assert event["activity"] == "speaking_mission"
    assert event["lexical_unit"] == event["word"]
    assert event["created_at"]
    # Filtro por superficie exacta.
    filtered = client.get(
        "/api/vocabulary/history", params={"user_id": user_id, "word": "cat"}
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["word"] == "cat"


def test_history_endpoint_unknown_user_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    got = client.get(
        "/api/vocabulary/history", params={"user_id": "no-existe"}
    )
    assert got.status_code == 404
