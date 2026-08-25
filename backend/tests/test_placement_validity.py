"""Tests de validez del placement adaptativo (V1.5.2).

Cubre la selección por máxima información, el error estándar y el criterio de
parada, el desglose multi-destreza y la versión del motor.
"""

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import load_assessments


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Error estándar -------------------------------------------------------


def test_placement_standard_error_none_without_responses():
    assert academy_svc.placement_standard_error(3.0, []) is None


def test_placement_standard_error_decreases_with_information():
    two = academy_svc.placement_standard_error(3.0, [(3, True), (3, False)])
    four = academy_svc.placement_standard_error(
        3.0, [(3, True), (3, False), (3, True), (3, False)]
    )
    assert two is not None and four is not None
    assert four < two


# --- Criterio de parada ---------------------------------------------------


def test_placement_should_stop_max_items():
    assert academy_svc.placement_should_stop(8, 20, 0.6) is True


def test_placement_should_stop_exhausted_items():
    assert academy_svc.placement_should_stop(20, 20, None) is True


def test_placement_should_stop_se_below_threshold_after_min_items():
    assert academy_svc.placement_should_stop(5, 20, 0.3) is True


def test_placement_should_stop_se_above_threshold():
    assert academy_svc.placement_should_stop(5, 20, 0.6) is False


def test_placement_should_stop_below_min_items_even_with_low_se():
    assert academy_svc.placement_should_stop(3, 20, 0.3) is False


# --- Selección por máxima información -------------------------------------


def test_select_next_item_maximizes_information():
    items = load_assessments().placement.items
    assert academy_svc.select_next_item(items, set(), 3.0).difficulty == 3
    assert academy_svc.select_next_item(items, set(), 6.0).difficulty == 6
    all_ids = {it.id for it in items}
    assert academy_svc.select_next_item(items, all_ids, 3.0) is None


# --- Resultado multi-destreza y versión -----------------------------------


def test_placement_result_adaptive_has_skills_and_version():
    items = load_assessments().placement.items
    answers = {it.id: it.correct_index for it in items}
    result = academy_svc.placement_result_adaptive(items, answers)
    assert result["skills"], "sin desglose por destreza"
    for breakdown in result["skills"].values():
        assert set(breakdown) == {"correct", "total", "score"}
        assert 0 <= breakdown["score"] <= 1
    assert result["placement_version"]


# --- Endpoint expone el error estándar ------------------------------------


def test_placement_next_exposes_standard_error(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    correct_by_id = {
        it.id: it.correct_index for it in load_assessments().placement.items
    }
    with TestClient(app) as client:
        r0 = client.post(
            "/api/academy/placement/next",
            params={"user_id": a},
            json={"answers": {}},
        )
        assert r0.status_code == 200
        body0 = r0.json()
        assert body0["standard_error"] is None  # sin respuestas aún

        nxt = body0["next_item"]
        answers = {nxt["id"]: correct_by_id[nxt["id"]]}
        r1 = client.post(
            "/api/academy/placement/next",
            params={"user_id": a},
            json={"answers": answers},
        )
        assert r1.status_code == 200
        assert isinstance(r1.json()["standard_error"], float)
