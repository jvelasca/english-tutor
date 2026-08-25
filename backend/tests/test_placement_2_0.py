"""Tests de V1.7 — Placement 2.0: perfil multiskill y calibración observacional."""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import load_assessments


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Perfil multiskill (puro) ---------------------------------------------


def test_placement_profile_is_multiskill():
    items = load_assessments().placement.items
    answers = {it.id: it.correct_index for it in items}
    profile = academy_svc.placement_profile(items, answers)
    assert profile["placement_version"] == "2.0.0"
    assert profile["overall_level"]
    assert isinstance(profile["overall_theta"], float)
    assert profile["profile"], "perfil multiskill vacío"
    by_skill = {p["skill"]: p for p in profile["profile"]}
    # Todas las destrezas del instrumento están representadas.
    assert set(by_skill) == {it.skill for it in items}
    for entry in profile["profile"]:
        assert entry["answered"] > 0, f"{entry['skill']} sin respuestas"
        assert entry["theta"] is not None
        assert entry["level"] is not None
        assert entry["confidence"] is not None


def test_placement_profile_skills_without_answers_are_none():
    items = load_assessments().placement.items
    target_skill = items[0].skill
    answers = {it.id: it.correct_index for it in items if it.skill == target_skill}
    profile = academy_svc.placement_profile(items, answers)
    by_skill = {p["skill"]: p for p in profile["profile"]}
    assert by_skill[target_skill]["answered"] > 0
    assert by_skill[target_skill]["theta"] is not None
    for p in profile["profile"]:
        if p["skill"] != target_skill:
            assert p["answered"] == 0
            assert p["theta"] is None
            assert p["level"] is None
            assert p["confidence"] is None


def test_placement_result_adaptive_exposes_profile():
    items = load_assessments().placement.items
    answers = {it.id: it.correct_index for it in items}
    result = academy_svc.placement_result_adaptive(items, answers)
    assert result["profile"], "el resultado adaptativo no expone perfil multiskill"
    skills = {p["skill"] for p in result["profile"]}
    assert skills == {it.skill for it in items}


# --- Calibración observacional (repositorio) ------------------------------


def test_placement_calibration_records_responses(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    items = load_assessments().placement.items
    correct_by_id = {it.id: it.correct_index for it in items}
    with TestClient(app) as client:
        start = client.post(
            "/api/academy/placement/start", params={"user_id": a}
        ).json()
        session_id = start["session_id"]
        answers: dict[str, int] = {}
        next_item = start["next_item"]
        done = False
        guard = 0
        while not done and guard < 20:
            guard += 1
            answers[next_item["id"]] = correct_by_id[next_item["id"]]
            body = client.post(
                "/api/academy/placement/next",
                params={"user_id": a},
                json={"answers": answers, "session_id": session_id},
            ).json()
            done = body["done"]
            next_item = body["next_item"]
    assert done

    calib = academy_repo.list_placement_calibration()
    assert calib, "la calibración no persistió respuestas"
    by_item = {c["item_id"]: c for c in calib}
    # Cada ítem respondido aparece con su contador incrementado una sola vez
    # (sin duplicar por las llamadas acumuladas de `/placement/next`).
    for item_id, answer_index in answers.items():
        correct = answer_index == correct_by_id[item_id]
        assert item_id in by_item
        assert by_item[item_id]["responses"] == 1
        assert by_item[item_id]["correct"] == (1 if correct else 0)
        assert by_item[item_id]["sample_size"] == 1
        assert by_item[item_id]["correct_rate"] == (1.0 if correct else 0.0)
        assert by_item[item_id]["estimated_difficulty"] is None


# --- Endpoint del perfil --------------------------------------------------


def test_placement_profile_endpoint(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    items = load_assessments().placement.items
    answers = {it.id: it.correct_index for it in items}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/placement/profile",
            params={"user_id": a},
            json={"answers": answers},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]
    assert body["overall_level"]
    assert body["overall_theta"] == body["overall_theta"]  # numérico
    assert body["placement_version"] == "2.0.0"
