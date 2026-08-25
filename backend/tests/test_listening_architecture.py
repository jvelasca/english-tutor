"""Tests de la arquitectura de listening: banco versionado, vector de dificultad,
first-pass accuracy, y revisión integrada con replay/latencia."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import (
    DIFFICULTY_FACTORS,
    LISTENING_BANK_VERSION,
    LISTENING_SUBSKILLS,
    QUESTION_BANK,
    listening_diagnostic,
    validate_listening_bank,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Banco: vector de dificultad y validación -----------------------------------


def test_bank_is_valid():
    assert validate_listening_bank() == []


def test_bank_vector_mean_matches_difficulty():
    for q in QUESTION_BANK:
        mean = sum(q["difficulty_vector"].values()) / len(DIFFICULTY_FACTORS)
        assert round(mean) == q["difficulty"], q["id"]


def test_bank_covers_every_subskill():
    skills = {q["skill"] for q in QUESTION_BANK}
    assert skills == set(LISTENING_SUBSKILLS)


def test_validate_listening_bank_detects_duplicate_id():
    bank = [dict(QUESTION_BANK[0]), dict(QUESTION_BANK[0])]
    errors = validate_listening_bank(bank)
    assert any("duplicate id" in e for e in errors)


def test_validate_listening_bank_detects_invalid_skill():
    bad = dict(QUESTION_BANK[0])
    bad["skill"] = "nope"
    errors = validate_listening_bank([bad])
    assert any("invalid skill" in e for e in errors)


def test_validate_listening_bank_detects_vector_mean_mismatch():
    bad = dict(QUESTION_BANK[0])
    bad["difficulty_vector"] = {f: 6 for f in DIFFICULTY_FACTORS}
    errors = validate_listening_bank([bad])
    assert any("mean != difficulty" in e for e in errors)


def test_validate_listening_bank_detects_missing_factor():
    bad = dict(QUESTION_BANK[0])
    bad["difficulty_vector"] = {
        f: v for f, v in QUESTION_BANK[0]["difficulty_vector"].items() if f != "accent"
    }
    errors = validate_listening_bank([bad])
    assert any("factors mismatch" in e for e in errors)


def test_validate_listening_bank_detects_extra_factor():
    bad = dict(QUESTION_BANK[0])
    bad["difficulty_vector"] = dict(QUESTION_BANK[0]["difficulty_vector"], noise=1)
    errors = validate_listening_bank([bad])
    assert any("factors mismatch" in e for e in errors)


def test_validate_listening_bank_detects_bad_answer_index():
    bad = dict(QUESTION_BANK[0])
    bad["answer_index"] = 99
    errors = validate_listening_bank([bad])
    assert any("answer_index" in e for e in errors)


# --- First-pass accuracy ---------------------------------------------------------


def test_first_pass_accuracy_ignores_learned_repetition():
    # l1 se falla a la primera y se acierta después (con replay): sólo cuenta el
    # primer intento. l2 se acierta a la primera.
    rows = [
        {
            "question_id": "l1",
            "skill": "detail",
            "correct": False,
            "response_time_ms": 1000,
            "replay_count": 0,
        },
        {
            "question_id": "l1",
            "skill": "detail",
            "correct": True,
            "response_time_ms": 800,
            "replay_count": 2,
        },
        {
            "question_id": "l2",
            "skill": "detail",
            "correct": True,
            "response_time_ms": 900,
            "replay_count": 0,
        },
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["detail"]["first_pass_accuracy"] == 50.0
    assert diag["first_pass_accuracy"] == 50.0


def test_first_pass_accuracy_none_without_question_ids():
    # Filas sin question_id (vista agregada) → no se puede derivar first-pass.
    rows = [
        {
            "skill": "detail",
            "correct": True,
            "response_time_ms": 1000,
            "replay_count": 0,
        }
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["detail"]["first_pass_accuracy"] is None
    assert diag["first_pass_accuracy"] is None


# --- Revisión integrada con replay/latencia -------------------------------------


def test_review_due_flags_replay_dependency():
    rows = [
        {"question_id": "l1", "skill": "detail", "correct": True,
         "response_time_ms": 1000, "replay_count": 2},
        {"question_id": "l2", "skill": "detail", "correct": True,
         "response_time_ms": 1000, "replay_count": 2},
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["detail"]["avg_replay_count"] == 2.0
    assert by_skill["detail"]["review_due"] is True


def test_review_due_flags_slow_responses():
    rows = [
        {"question_id": "l1", "skill": "detail", "correct": True,
         "response_time_ms": 5000, "replay_count": 0}
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["detail"]["review_due"] is True


# --- Endpoints: vector de dificultad y versión del banco ------------------------


def test_question_endpoint_exposes_difficulty_vector(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/question", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert set(body["difficulty_vector"]) == set(DIFFICULTY_FACTORS)
    assert all(1 <= v <= 6 for v in body["difficulty_vector"].values())


def test_diagnostic_endpoint_exposes_version_and_first_pass(monkeypatch, tmp_path):
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
    assert body["bank_version"] == LISTENING_BANK_VERSION
    assert body["first_pass_accuracy"] == 100.0
    by_skill = {s["skill"]: s for s in body["subskills"]}
    assert by_skill[q["skill"]]["first_pass_accuracy"] == 100.0
