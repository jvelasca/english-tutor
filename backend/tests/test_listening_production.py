"""Tests de tareas de producción de listening (dictado y shadowing).

Cubre el scoring determinista (`production_score`/`production_reference`), la
persistencia con `task_type`/`score` y la exposición de `mean_score` en el
diagnóstico. No rompe el flujo MCQ.
"""

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import (
    dictation_score,
    get_question,
    listening_diagnostic,
    production_reference,
    production_score,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Unidades puras --------------------------------------------------------


def test_production_score_perfect_match():
    result = production_score("hello world", "hello world")
    assert result["score"] == 100
    assert result["word_accuracy"] == 100
    assert result["phonetic_score"] == 100
    assert result["breakdown"]["total"] == 2


def test_production_score_low_for_unrelated_text():
    result = production_score("the quick brown fox jumps", "zzz")
    assert result["score"] < 80
    assert 0 <= result["score"] <= 100


# --- dictation_score: exacto por token (V3.28.1, P1-02) ----------------------

def test_dictation_score_exact_ignores_case_and_punctuation():
    """El dictado normaliza mayúsculas/puntuación pero exige tokens exactos."""
    result = dictation_score("Hello world.", "hello world")
    assert result["score"] == 100
    assert result["word_accuracy"] == 100
    assert result["breakdown"]["total"] == 2


def test_dictation_score_rejects_phonetic_spelling_variant():
    """`new sistem` por `new system` es incorrecto en dictado escrito: no hay
    tolerancia fonética (Soundex/fonemas/prosodia a 0)."""
    result = dictation_score("new system", "new sistem")
    assert result["score"] == 50
    assert result["score"] < 80  # por debajo de PRODUCTION_PASS_SCORE
    assert result["phonetic_score"] == 0
    assert result["phoneme_accuracy_proxy"] == 0
    assert result["breakdown"]["substituted"] == [
        {"expected": "system", "heard": "sistem"}
    ]


def test_shadowing_keeps_phonetic_composite_while_dictation_is_exact():
    """El shadowing (oral) conserva el composite con señales fonéticas; el
    dictado escrito no (misma entrada, puntuaciones distintas)."""
    oral = production_score("new system", "new sistem")
    escrito = dictation_score("new system", "new sistem")
    assert oral["phonetic_score"] > 0
    assert oral["phoneme_accuracy_proxy"] > 0
    assert escrito["phonetic_score"] == 0
    assert oral["score"] > escrito["score"]


def test_production_reference_priority():
    assert (
        production_reference(
            {"transcript": "A", "clean_transcript": "B", "script": "C"}
        )
        == "A"
    )
    assert production_reference({"clean_transcript": "B", "script": "C"}) == "B"
    assert production_reference({"script": "C"}) == "C"
    assert production_reference({}) == ""


# --- submit_production vía API ----------------------------------------------


def test_dictation_correct_persists_task_type_and_score(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = get_question("l18")
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={"question_id": "l18", "transcript": q["transcript"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["task_type"] == "dictation"
    assert body["score"] == 100
    assert body["reference"] == q["transcript"]
    attempts = listening_repo.list_attempts(uid)
    assert len(attempts) == 1
    row = attempts[0]
    assert row["task_type"] == "dictation"
    assert row["answer_index"] == -1
    assert row["score"] == 1.0


def test_dictation_wrong_is_not_correct(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={
                "question_id": "l18",
                "transcript": "completely unrelated words here",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is False
    assert body["score"] < 80


def test_shadowing_correct_persists_task_type_and_score(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = get_question("l19")
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/shadowing",
            params={"user_id": uid},
            json={"question_id": "l19", "transcript": q["transcript"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["task_type"] == "shadowing"
    attempts = listening_repo.list_attempts(uid)
    assert attempts[0]["task_type"] == "shadowing"


def test_dictation_skill_mismatch_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={"question_id": "l19", "transcript": "x"},  # l19 es shadowing
        )
    assert r.status_code == 404


def test_shadowing_skill_mismatch_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/shadowing",
            params={"user_id": uid},
            json={"question_id": "l18", "transcript": "x"},  # l18 es dictation
        )
    assert r.status_code == 404


def test_dictation_unknown_question_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={"question_id": "nope", "transcript": "x"},
        )
    assert r.status_code == 404


# --- mean_score en el diagnóstico -------------------------------------------


def test_diagnostic_mean_score_over_production_rows():
    rows = [
        {"skill": "dictation", "correct": True, "score": 0.9},
        {"skill": "dictation", "correct": False, "score": 0.5},
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["dictation"]["mean_score"] == 70.0
    assert by_skill["shadowing"]["mean_score"] is None


def test_diagnostic_mean_score_none_without_production():
    rows = [
        {"skill": "detail", "correct": True, "response_time_ms": 1000},
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    assert by_skill["detail"]["mean_score"] is None


def test_diagnostic_endpoint_exposes_mean_score(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = get_question("l18")
    with TestClient(app) as client:
        client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={"question_id": "l18", "transcript": q["transcript"]},
        )
        r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    by_skill = {s["skill"]: s for s in r.json()["subskills"]}
    assert by_skill["dictation"]["mean_score"] == 100.0
