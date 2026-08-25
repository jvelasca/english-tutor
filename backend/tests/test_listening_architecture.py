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
    automaticity_from_metrics,
    difficulty_from_vector,
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
        assert difficulty_from_vector(q["difficulty_vector"]) in range(1, 7), q["id"]


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


def test_validate_listening_bank_detects_vector_out_of_range():
    # Con la dificultad derivada ya no hay "mean != difficulty"; el invariante
    # equivalente es que cada dimensión del vector esté en 1..6.
    bad = dict(QUESTION_BANK[0])
    bad["difficulty_vector"] = dict(bad["difficulty_vector"], speed=0)
    errors = validate_listening_bank([bad])
    assert any("out of range" in e for e in errors)


def test_validate_listening_bank_detects_missing_factor():
    bad = dict(QUESTION_BANK[0])
    bad["difficulty_vector"] = {
        f: v for f, v in QUESTION_BANK[0]["difficulty_vector"].items() if f != "accent"
    }
    errors = validate_listening_bank([bad])
    assert any("factors mismatch" in e for e in errors)


def test_validate_listening_bank_detects_extra_factor():
    bad = dict(QUESTION_BANK[0])
    bad["difficulty_vector"] = dict(QUESTION_BANK[0]["difficulty_vector"], syntax=1)
    errors = validate_listening_bank([bad])
    assert any("factors mismatch" in e for e in errors)


def test_validate_listening_bank_detects_bad_answer_index():
    bad = dict(QUESTION_BANK[0])
    bad["answer_index"] = 99
    errors = validate_listening_bank([bad])
    assert any("answer_index" in e for e in errors)


# --- Vector de 8 dimensiones y dificultad derivada -----------------------------


def test_difficulty_factors_are_exactly_8_in_order():
    assert DIFFICULTY_FACTORS == (
        "speed",
        "vocabulary",
        "accent",
        "syntactic",
        "length",
        "speaker_count",
        "noise",
        "connected_speech",
    )


def test_bank_vectors_have_all_8_factors():
    for q in QUESTION_BANK:
        assert set(q["difficulty_vector"]) == set(DIFFICULTY_FACTORS), q["id"]


def test_difficulty_from_vector_rounds_mean():
    # Media 1.0 → 1; media 2.625 → 3 (redondeo al par de Python).
    assert difficulty_from_vector({"speed": 1, "vocabulary": 1}) == 1
    assert difficulty_from_vector({f: 3 for f in DIFFICULTY_FACTORS}) == 3


def test_difficulty_from_vector_clamps_to_1_6():
    assert difficulty_from_vector({}) == 1
    assert difficulty_from_vector({"speed": 0, "vocabulary": 0}) == 1
    assert difficulty_from_vector({"speed": 100, "vocabulary": 100}) == 6


def test_automaticity_is_none_without_attempts():
    assert automaticity_from_metrics(0.0, None, attempts=0) is None


def test_automaticity_penalizes_replays_and_latency():
    # Sin replays y respuesta rápida → alta automaticidad.
    fast = automaticity_from_metrics(0.0, 1000.0, attempts=3)
    # Con replays y respuesta lenta → menor automaticidad.
    slow = automaticity_from_metrics(2.0, 5000.0, attempts=3)
    assert fast is not None and slow is not None
    assert 0 <= fast <= 1
    assert 0 <= slow <= 1
    assert slow < fast


def test_diagnostic_exposes_automaticity():
    rows = [
        {"question_id": "l1", "skill": "detail", "correct": True,
         "response_time_ms": 1000, "replay_count": 0},
        {"question_id": "l2", "skill": "detail", "correct": True,
         "response_time_ms": 1200, "replay_count": 0},
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["detail"]["automaticity"] is not None
    assert 0 <= by_skill["detail"]["automaticity"] <= 1
    assert diag["automaticity"] is not None
    assert 0 <= diag["automaticity"] <= 1


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
