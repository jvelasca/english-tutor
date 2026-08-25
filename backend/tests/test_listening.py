"""Tests de listening: banco, puntuación, dominio, repositorio y endpoints."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import (
    LEVEL_ORDER,
    LISTENING_SUBSKILLS,
    QUESTION_BANK,
    current_level,
    get_question,
    level_status,
    listening_diagnostic,
    pick_next_question,
    score_answer,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_score_answer_correct():
    assert score_answer(1, 1) is True


def test_score_answer_incorrect():
    assert score_answer(0, 1) is False


def test_get_question_found():
    q = get_question(QUESTION_BANK[0]["id"])
    assert q is not None
    assert q["script"]


def test_get_question_missing():
    assert get_question("nope") is None


def test_pick_next_starts_at_a1():
    assert pick_next_question(set())["id"] == QUESTION_BANK[0]["id"]


def test_pick_next_serves_unseen_before_retrying():
    # l1 visto pero no dominado: se sirve la siguiente no vista (l2) antes de
    # reintentar l1, de modo que el usuario recorre el nivel sin atascarse.
    assert pick_next_question({"l1"}, set())["id"] == "l2"


def test_pick_next_retries_wrong_after_unseen_exhausted():
    # Con todo el nivel visto y solo l3 sin dominar, se reintenta la fallada tras
    # agotar las no vistas.
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    assert pick_next_question(a1_ids, a1_ids - {"l3"})["id"] == "l3"


def test_pick_next_advances_when_level_mastered():
    # A1 completo → siguiente pregunta es de A2 (l4).
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    assert pick_next_question(set(), a1_ids)["id"] == "l4"


def test_pick_next_completes_all_levels_and_rotates():
    # Todo dominado: rota sobre el banco en lugar de quedarse atascado.
    all_ids = {q["id"] for q in QUESTION_BANK}
    assert pick_next_question(set(), all_ids)["id"] == QUESTION_BANK[0]["id"]


def test_current_level_advances_with_mastery():
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    a2_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A2"}
    assert current_level(set()) == "A1"
    assert current_level(a1_ids) == "A2"
    assert current_level(a1_ids | a2_ids) == "B1"
    # Completados todos → se mantiene en el último nivel para seguir practicando.
    assert current_level({q["id"] for q in QUESTION_BANK}) == "B1"


def test_level_status_marks_completed():
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    status = level_status(a1_ids)
    by_level = {s["level"]: s for s in status}
    assert [s["level"] for s in status] == LEVEL_ORDER
    assert by_level["A1"]["completed"] is True
    assert by_level["A1"]["mastered"] == by_level["A1"]["total"]
    assert by_level["A2"]["completed"] is False


def test_bank_shape_valid():
    assert len(QUESTION_BANK) >= 3
    for q in QUESTION_BANK:
        assert q["id"]
        assert q["script"]
        assert q["question"]
        assert len(q["options"]) >= 2
        assert 0 <= q["answer_index"] < len(q["options"])
        assert q["skill"] in LISTENING_SUBSKILLS
        assert 1 <= q["difficulty"] <= 6
    from collections import Counter

    skill_counts = Counter(q["skill"] for q in QUESTION_BANK)
    assert skill_counts["gist"] >= 2
    assert skill_counts["vocabulary"] >= 2


def test_next_question_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/question", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["script"]
    assert body["question"]
    assert isinstance(body["options"], list) and len(body["options"]) >= 2
    assert "answer_index" not in body


def test_answer_correct(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["correct_index"] == q["answer_index"]


def test_answer_wrong(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    wrong = (q["answer_index"] + 1) % len(q["options"])
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": wrong},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is False


def test_answer_unknown_question_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": "nope", "answer_index": 0},
        )
    assert r.status_code == 404


def test_answer_unknown_user_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": "no-existe"},
            json={"question_id": q["id"], "answer_index": 0},
        )
    assert r.status_code == 404


def test_stats_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/stats", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 1
    assert body["correct"] == 1
    assert body["accuracy"] == 100.0
    assert body["level"] == "A1"
    assert body["completed"] is False
    assert [lv["level"] for lv in body["levels"]] == LEVEL_ORDER


def test_progression_advances_levels_via_api(monkeypatch, tmp_path):
    """Responder correctamente todas las preguntas de un nivel avanza al siguiente.

    Regresión del bug donde la práctica de listening se quedaba atascada (bucle)
    sin pasar de nivel."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for q in QUESTION_BANK:
            if q["level"] != "A1":
                continue
            r = client.post(
                "/api/listening/answer",
                params={"user_id": uid},
                json={"question_id": q["id"], "answer_index": q["answer_index"]},
            )
            assert r.status_code == 200

        nxt = client.get("/api/listening/question", params={"user_id": uid}).json()
        stats = client.get("/api/listening/stats", params={"user_id": uid}).json()

    assert nxt["level"] == "A2"  # A1 completado → avanza a A2
    assert stats["level"] == "A2"
    assert stats["levels"][0]["completed"] is True
    assert stats["levels"][1]["completed"] is False


def test_all_levels_completed_marks_completed(monkeypatch, tmp_path):
    """Responder correctamente todo el banco marca la práctica como completada."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for q in QUESTION_BANK:
            client.post(
                "/api/listening/answer",
                params={"user_id": uid},
                json={"question_id": q["id"], "answer_index": q["answer_index"]},
            )
        stats = client.get("/api/listening/stats", params={"user_id": uid}).json()
    assert stats["completed"] is True
    assert stats["level"] == "B1"
    assert all(lv["completed"] for lv in stats["levels"])


def test_listening_diagnostic_empty():
    diag = listening_diagnostic([])
    assert [s["skill"] for s in diag["subskills"]] == list(LISTENING_SUBSKILLS)
    assert all(s["attempts"] == 0 for s in diag["subskills"])
    assert all(s["accuracy"] is None for s in diag["subskills"])
    assert diag["weak"] == list(LISTENING_SUBSKILLS)
    assert diag["recommendation"].startswith("Focus on:")


def test_listening_diagnostic_groups_and_weak():
    def _row(skill, correct, rms, replay):
        return {
            "skill": skill,
            "correct": correct,
            "response_time_ms": rms,
            "replay_count": replay,
        }

    rows = [
        _row("detail", True, 1000, 0),
        _row("detail", True, 1200, 0),
        _row("detail", True, 800, 1),
        _row("numbers", False, 2000, 2),
        _row("numbers", False, 2100, 3),
        _row("numbers", False, 1900, 1),
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}

    assert by_skill["detail"]["attempts"] == 3
    assert by_skill["detail"]["correct"] == 3
    assert by_skill["detail"]["accuracy"] == 100.0
    assert by_skill["detail"]["avg_response_ms"] == 1000.0
    assert by_skill["detail"]["review_due"] is False

    assert by_skill["numbers"]["attempts"] == 3
    assert by_skill["numbers"]["correct"] == 0
    assert by_skill["numbers"]["accuracy"] == 0.0
    assert by_skill["numbers"]["avg_replay_count"] == 2.0
    assert by_skill["numbers"]["review_due"] is True

    # gist no tiene muestras → review_due True para animar a explorar.
    assert by_skill["gist"]["attempts"] == 0
    assert by_skill["gist"]["review_due"] is True

    assert "numbers" in diag["weak"]
    assert "gist" in diag["weak"]
    assert "detail" not in diag["weak"]


def test_diagnostic_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert len(body["subskills"]) >= len(LISTENING_SUBSKILLS)
    by_skill = {s["skill"]: s for s in body["subskills"]}
    assert by_skill[q["skill"]]["attempts"] == 1


def test_answer_records_metrics(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "answer_index": q["answer_index"],
                "response_time_ms": 1234,
                "replay_count": 2,
            },
        )
    assert r.status_code == 200
    attempts = listening_repo.list_attempts(uid)
    assert len(attempts) == 1
    row = attempts[0]
    assert row["response_time_ms"] == 1234
    assert row["replay_count"] == 2
    assert row["skill"] == q["skill"]
    assert row["difficulty"] == q["difficulty"]
