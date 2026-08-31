"""Tests de vocabulario: extracción, persistencia, aislamiento y endpoints."""
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.vocabulary import classify, extract_words


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def test_vocabulary_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("vocabulary")


def test_extract_words_filters_and_sorts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    words = extract_words("Hello, World! The cat sat on the mat.")
    assert words == ["cat", "hello", "mat", "sat", "world"]


def test_extract_words_deduplicates(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert extract_words("Cat cat CAT") == ["cat"]


def test_extract_words_removes_short_tokens(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    # "I", "a", "am" no cuentan como vocabulario.
    assert extract_words("I am a cat") == ["cat"]


def test_record_words_increments_appearances(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat", "dog"]) is True
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    vocab = {v["word"]: v["appearances"] for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["cat"] == 2
    assert vocab["dog"] == 1


def test_record_words_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words("no-existe", ["cat"]) is False


def test_vocabulary_occurrences_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    # Simula una BD legacy con la columna antigua `occurrences`.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("ALTER TABLE vocabulary RENAME COLUMN appearances TO occurrences")
    conn.commit()
    conn.close()

    # init_db debe volver a renombrar a `appearances` de forma idempotente.
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
    finally:
        conn.close()
    assert "appearances" in cols
    assert "occurrences" not in cols


def test_vocabulary_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat"])
    assert vocabulary_repo.get_vocabulary(b) == []


def test_get_vocabulary_ordered_by_appearances(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["zebra"])
    vocabulary_repo.record_words(a, ["apple", "apple"])
    vocab = vocabulary_repo.get_vocabulary(a)
    assert [v["word"] for v in vocab] == ["apple", "zebra"]


def test_vocabulary_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/vocabulary/analyze",
            params={"user_id": a},
            json={"text": "The cat sat on the mat."},
        )
        assert r.status_code == 200
        assert r.json()["words"] == ["cat", "mat", "sat"]

        got = client.get("/api/vocabulary", params={"user_id": a})
        assert got.status_code == 200
        assert {v["word"] for v in got.json()} == {"cat", "mat", "sat"}


def test_vocabulary_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get("/api/vocabulary", params={"user_id": "no-existe"}).status_code
            == 404
        )
        assert (
            client.post(
                "/api/vocabulary/analyze",
                params={"user_id": "no-existe"},
                json={"text": "hello"},
            ).status_code
            == 404
        )


def test_classify_statuses(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert classify(0, 0) == "exposed"
    assert classify(1, 1) == "learning"
    assert classify(2, 3) == "learning"  # menos de 3 producciones
    assert classify(3, 1) == "learning"  # 3 producciones pero un solo día
    assert classify(3, 2) == "mastered"


def test_record_exposures_creates_exposed_rows(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_exposures(a, ["travel", "culture"]) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["exposures"] == 1
    assert vocab["travel"]["appearances"] == 0
    assert vocab["travel"]["production_days"] == 0
    assert vocab["travel"]["last_exposed_at"]


def test_record_exposures_accumulates(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])
    vocabulary_repo.record_exposures(a, ["travel"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["exposures"] == 2
    assert vocab["travel"]["appearances"] == 0


def test_record_exposures_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_exposures("no-existe", ["travel"]) is False


def test_production_days_counts_distinct_days(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",
            "2026-08-20T11:00:00+00:00",  # mismo día → no suma
            "2026-08-21T10:00:00+00:00",  # día distinto → suma
            "2026-08-22T10:00:00+00:00",  # día distinto → suma
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    for _ in range(4):
        vocabulary_repo.record_words(a, ["cat"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["cat"]["appearances"] == 4
    assert vocab["cat"]["production_days"] == 3


def test_vocabulary_endpoint_reports_status(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])  # exposed
    vocabulary_repo.record_words(a, ["cat"])  # learning (1 producción, 1 día)
    with TestClient(app) as client:
        got = client.get("/api/vocabulary", params={"user_id": a})
    assert got.status_code == 200
    by_word = {v["word"]: v for v in got.json()}
    assert by_word["travel"]["status"] == "exposed"
    assert by_word["travel"]["appearances"] == 0
    assert by_word["cat"]["status"] == "learning"


def test_vocabulary_p3_columns_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    vocabulary_repo.record_words(uid, ["cat"])

    # Simula una BD previa a P3: elimina las columnas nuevas.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("ALTER TABLE vocabulary DROP COLUMN exposures")
    conn.execute("ALTER TABLE vocabulary DROP COLUMN last_exposed_at")
    conn.execute("ALTER TABLE vocabulary DROP COLUMN production_days")
    conn.commit()
    conn.close()

    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        row = conn.execute(
            "SELECT appearances, production_days FROM vocabulary WHERE word = 'cat'"
        ).fetchone()
    finally:
        conn.close()
    assert {"exposures", "last_exposed_at", "production_days"} <= cols
    assert row[0] == 1  # appearances
    assert row[1] == 1  # production_days (backfill de producciones previas)


def test_lexicon_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {"word": "name", "lemma": "name", "cefr": "A1", "level_id": "a1",
             "objective_id": "o1", "kind": "word"},
            {"word": "i am", "lemma": "i am", "cefr": "A1", "level_id": "a1",
             "objective_id": "o1", "kind": "structure"},
        ],
    )
    vocabulary_repo.record_exposures(a, ["name"])
    vocabulary_repo.record_words(a, ["name"])
    with TestClient(app) as client:
        got = client.get("/api/vocabulary/lexicon", params={"user_id": a})
    assert got.status_code == 200
    body = got.json()
    assert body["summary"]["total"] == 2
    items = {i["word"]: i for i in body["items"]}
    assert set(items) == {"name", "i am"}
    assert items["name"]["cefr"] == "A1"
    assert items["name"]["source"] == "curriculum"
    assert items["name"]["kind"] == "word"
    assert items["i am"]["kind"] == "structure"
    assert items["name"]["status"] in {"mastered", "known", "learning", "weak"}
    assert 0 <= items["name"]["recall"] <= 1
    assert isinstance(items["name"]["next_review_days"], int)


def test_lexicon_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        resp = client.get(
            "/api/vocabulary/lexicon", params={"user_id": "no-existe"}
        )
        assert resp.status_code == 404
