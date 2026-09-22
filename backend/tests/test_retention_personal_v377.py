"""Tests de retención Personal: ingestión + sesión FSRS (D3/D5).

- Añadir palabra/lista/pack crea fila vocabulary + carta lexicon, sin
  production/exposure ni mastery.
- Grade retention reprograma due_at y escribe evento informativo.
- Aislamiento entre usuarios.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import collections as collections_repo
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.evidence import classify_event_role


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _count(table: str, where: str = "1=1", params=()) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
    finally:
        conn.close()


def test_add_item_seeds_vocab_and_fsrs_without_skill_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        before_events = _count("learning_events", "user_id = ?", (a,))
        before_vocab_events = _count("vocabulary_events", "user_id = ?", (a,))

        res = client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "Passport", "translation": "pasaporte"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["added"] == ["passport"]
        assert body["item"]["word"] == "passport"

        rows = vocabulary_repo.get_vocabulary(a)
        assert len(rows) == 1
        row = rows[0]
        assert row["word"] == "passport"
        assert int(row["production_count"] or 0) == 0
        assert int(row["exposure_count"] or 0) == 0
        assert row["source"] == "user"

        card = academy_repo.get_fsrs_card(a, "lexicon", "passport")
        assert card is not None
        assert card["target_type"] == "lexicon"
        assert int(card["reps"] or 0) == 0

        assert _count("learning_events", "user_id = ?", (a,)) == before_events
        assert (
            _count("vocabulary_events", "user_id = ?", (a,)) == before_vocab_events
        )


def test_bulk_and_enroll_theme_pack(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        packs = client.get(
            "/api/vocabulary/collections", params={"user_id": a}
        )
        assert packs.status_code == 200
        collections = packs.json()["collections"]
        assert any(c["slug"] == "travel" and c["is_global"] for c in collections)
        travel = next(c for c in collections if c["slug"] == "travel")

        enroll = client.post(
            f"/api/vocabulary/collections/{travel['id']}/enroll",
            params={"user_id": a},
        )
        assert enroll.status_code == 200, enroll.text
        data = enroll.json()
        assert data["count"] > 0
        assert "airport" in data["added"]

        rows = vocabulary_repo.get_vocabulary(a)
        assert len(rows) == data["count"]
        assert all(int(r["production_count"] or 0) == 0 for r in rows)

        bulk = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": a},
            json={"text": "hello\nworld\nhello\ngood morning", "title": "Basics"},
        )
        assert bulk.status_code == 200, bulk.text
        assert bulk.json()["count"] == 3
        assert set(bulk.json()["added"]) == {"hello", "world", "good morning"}


def test_retention_review_reschedules_and_informative_event(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "ticket"},
        )
        due = client.get(
            "/api/vocabulary/retention/due", params={"user_id": a}
        )
        assert due.status_code == 200
        items = due.json()["items"]
        assert any(i["word"] == "ticket" for i in items)

        review = client.post(
            "/api/vocabulary/retention/review",
            params={"user_id": a},
            json={"word": "ticket", "grade": 4},
        )
        assert review.status_code == 200, review.text
        out = review.json()
        assert out["grade"] == 4
        assert out["reps"] >= 1
        assert out["next_in_days"] > 0

        events = learning_repo.list_events(a, event_type="exercise")
        retention = [e for e in events if "retention:ticket:" in e["detail"]]
        assert retention
        assert retention[0]["event_role"] == "informative"
        assert classify_event_role("exercise", "retention:ticket:4") == "informative"

        row = vocabulary_repo.get_vocabulary(a)[0]
        assert int(row["production_count"] or 0) == 0


def test_add_isolated_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "luggage"},
        )
        assert len(vocabulary_repo.get_vocabulary(a)) == 1
        assert vocabulary_repo.get_vocabulary(b) == []

        due_b = client.get(
            "/api/vocabulary/retention/due", params={"user_id": b}
        )
        assert due_b.json()["due_count"] == 0


# --- Control de acceso al catálogo de colecciones (V3.77.2, P0) -----------
#
# `collection_id` es entrada pública del cliente (body de `/items` y
# `/items/bulk`) y escribe en el CATÁLOGO de la colección. Antes de V3.77.2
# solo `enroll_collection` comprobaba el propietario: la ingestión aceptaba
# cualquier id, de modo que un perfil podía inyectar palabras y traducciones en
# un pack global (visible para todos) o en la lista privada de otro usuario
# (ids enumerables). Estas pruebas fijan la puerta extendida.


def _create_list(client: TestClient, user_id: str, title: str) -> int:
    res = client.post(
        "/api/vocabulary/collections",
        params={"user_id": user_id},
        json={"title": title},
    )
    assert res.status_code == 200, res.text
    return int(res.json()["id"])


def test_add_item_rejects_collection_of_another_user(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        private = _create_list(client, a, "Solo de A")

        res = client.post(
            "/api/vocabulary/items",
            params={"user_id": b},
            json={
                "word": "intruder",
                "translation": "intruso",
                "collection_id": private,
            },
        )
        assert res.status_code == 400, res.text
        # Ni léxico ni catálogo ajenos se tocan.
        assert vocabulary_repo.get_vocabulary(b) == []
        assert collections_repo.list_collection_items(private) == []


def test_bulk_rejects_collection_of_another_user(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        private = _create_list(client, a, "Solo de A")

        res = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": b},
            json={"text": "sneaky\nwords", "collection_id": private},
        )
        assert res.status_code == 400, res.text
        assert vocabulary_repo.get_vocabulary(b) == []
        assert collections_repo.list_collection_items(private) == []


def test_bulk_rejects_missing_collection(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": a},
            json={"text": "ghost", "collection_id": 999_999},
        )
        assert res.status_code == 400, res.text
        assert collections_repo.list_collection_items(999_999) == []


def test_ingestion_accepts_own_list_and_global_pack(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        own = _create_list(client, a, "Mía")

        into_own = client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "mine", "translation": "mío", "collection_id": own},
        )
        assert into_own.status_code == 200, into_own.text
        assert [i["word"] for i in collections_repo.list_collection_items(own)] == [
            "mine"
        ]

        # Un pack global es de todos: mismo comportamiento que `enroll`.
        travel = next(
            c
            for c in client.get(
                "/api/vocabulary/collections", params={"user_id": a}
            ).json()["collections"]
            if c["slug"] == "travel"
        )
        into_global = client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "jetlag", "collection_id": travel["id"]},
        )
        assert into_global.status_code == 200, into_global.text


# --- P3: la importación en lote no abre una conexión por palabra -------------
#
# `add_membership` y `_ensure_fsrs_lexicon` abrían conexión (y `get_user`) por
# palabra: importar un pack de N palabras hacía O(N) idas y vueltas a la BD,
# cada una dentro de su propio `to_thread`. V3.77.2 las agrupa en una
# transacción. Este test fija el COSTE, no solo el resultado: contar filas no
# habría detectado la regresión.


def test_bulk_membership_and_fsrs_seed_open_constant_connections(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    from domain import retention as retention_domain

    created = collections_repo.create_user_list(a, title="Lote")
    assert created is not None
    coll_id = int(created["id"])
    words = [f"pack{i}" for i in range(40)]

    calls = {"membership": 0, "fsrs": 0}
    real_collections_conn = collections_repo._conn
    real_academy_conn = academy_repo._conn

    def collections_conn(*args, **kwargs):
        calls["membership"] += 1
        return real_collections_conn(*args, **kwargs)

    def academy_conn(*args, **kwargs):
        calls["fsrs"] += 1
        return real_academy_conn(*args, **kwargs)

    monkeypatch.setattr(collections_repo, "_conn", collections_conn)
    monkeypatch.setattr(academy_repo, "_conn", academy_conn)

    collections_repo.add_memberships(a, coll_id, words)
    # Una transacción para las 40 membresías (más, como mucho, una lectura).
    assert calls["membership"] <= 2, calls
    assert collections_repo.words_in_collection(a, coll_id) == set(words)

    # Idempotente: repetir no duplica ni dispara conexiones extra.
    collections_repo.add_memberships(a, coll_id, words)
    assert len(collections_repo.words_in_collection(a, coll_id)) == 40

    retention_domain._ensure_fsrs_lexicon(a, words, why="retention-import")
    # Un `IN (...)` + un `executemany`: constante, no proporcional a 40.
    assert calls["fsrs"] <= 3, calls
    seeded = academy_repo.fsrs_cards_by_ids(a, "lexicon", words)
    assert set(seeded) == set(words)
    assert all(int(card["reps"] or 0) == 0 for card in seeded.values())
