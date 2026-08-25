"""Tests de trazabilidad de la sesión de placement (V1.5.3).

Verifica que `POST /placement/start` crea una sesión y que el bucle de
`POST /placement/next` con `session_id` persiste los ítems, las respuestas, la
traza de θ y el resultado final, reconstruibles vía repositorio.
"""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services.curriculum import load_assessments


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_placement_session_traceability(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    correct_by_id = {
        it.id: it.correct_index for it in load_assessments().placement.items
    }
    with TestClient(app) as client:
        r = client.post("/api/academy/placement/start", params={"user_id": a})
        assert r.status_code == 200
        start = r.json()
        session_id = start["session_id"]
        assert start["placement_version"]
        assert start["next_item"] is not None

        answers: dict[str, int] = {}
        next_item = start["next_item"]
        done = False
        guard = 0
        while not done and guard < 20:
            guard += 1
            assert next_item is not None, "siguiente ítem inesperadamente vacío"
            answers[next_item["id"]] = correct_by_id[next_item["id"]]
            r = client.post(
                "/api/academy/placement/next",
                params={"user_id": a},
                json={"answers": answers, "session_id": session_id},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["session_id"] == session_id
            done = body["done"]
            next_item = body["next_item"]
        assert done

    session = academy_repo.get_placement_session(session_id)
    assert session is not None
    assert session["user_id"] == a
    assert session["placement_version"]
    assert session["items"], "no se persistieron los ítems del instrumento"
    assert session["answers"] == answers
    assert session["theta_trace"], "no se persistió la traza de θ"
    assert all("theta" in t and "answered" in t for t in session["theta_trace"])
    assert session["final_result"] is not None
    assert session["completed_at"] is not None

    sessions = academy_repo.list_placement_sessions(a)
    assert any(s["id"] == session_id for s in sessions)


def test_placement_next_without_session_still_works(monkeypatch, tmp_path):
    # Retrocompatibilidad: sin session_id el endpoint sigue siendo stateless.
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/placement/next",
            params={"user_id": a},
            json={"answers": {}},
        )
    assert r.status_code == 200
    assert r.json()["session_id"] is None
