"""Tests del placement adaptativo (IRT-lite V1.5)."""

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


# --- Motor IRT-lite puro --------------------------------------------------


def test_theta_to_level_boundaries():
    assert academy_svc.theta_to_level(1.4) == "A1"
    assert academy_svc.theta_to_level(1.5) == "A2"
    assert academy_svc.theta_to_level(2.5) == "B1"
    assert academy_svc.theta_to_level(3.5) == "B2"
    assert academy_svc.theta_to_level(4.5) == "C1"
    assert academy_svc.theta_to_level(5.5) == "C2"


def test_ability_theta_moves_with_correctness():
    easy_correct = academy_svc.ability_theta([(1, True), (2, True), (1, True)])
    hard_wrong = academy_svc.ability_theta([(5, False), (6, False), (5, False)])
    assert easy_correct > hard_wrong
    assert academy_svc.ability_theta([]) == 3.0


def test_ability_theta_all_correct_bounded():
    theta = academy_svc.ability_theta([(6, True)] * 5)
    assert theta > 5.0
    assert academy_svc.PLACEMENT_THETA_MIN <= theta <= academy_svc.PLACEMENT_THETA_MAX


def test_select_next_item_closest_to_theta():
    items = load_assessments().placement.items
    assert academy_svc.select_next_item(items, set(), 3.0).difficulty == 3
    assert academy_svc.select_next_item(items, set(), 6.0).difficulty == 6
    all_ids = {it.id for it in items}
    assert academy_svc.select_next_item(items, all_ids, 3.0) is None


def test_placement_result_adaptive_levels():
    items = load_assessments().placement.items
    # Acierta solo la dificultad 1 y falla el resto → nivel A1.
    low = {
        it.id: it.correct_index
        if it.difficulty == 1
        else (it.correct_index + 1) % len(it.options)
        for it in items
    }
    assert academy_svc.placement_result_adaptive(items, low)["level"] == "A1"

    # Acierta todo → θ alta.
    high = {it.id: it.correct_index for it in items}
    level = academy_svc.placement_result_adaptive(items, high)["level"]
    assert level in ("B2", "C1", "C2")


# --- Endpoint -------------------------------------------------------------


def test_placement_next_endpoint(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    correct_by_id = {it.id: it.correct_index for it in data.placement.items}
    answers = {}
    with TestClient(app) as client:
        for i in range(8):
            r = client.post(
                "/api/academy/placement/next",
                params={"user_id": a},
                json={"answers": answers},
            )
            assert r.status_code == 200
            body = r.json()
            if i == 0:
                assert body["done"] is False
                assert body["next_item"] is not None
                assert body["theta"] == 3.0
            if body["next_item"] is not None:
                item_id = body["next_item"]["id"]
                answers[item_id] = correct_by_id[item_id]

        # Con 8 respuestas acumuladas el siguiente POST devuelve done=True.
        r = client.post(
            "/api/academy/placement/next",
            params={"user_id": a},
            json={"answers": answers},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["done"] is True
        assert body["next_item"] is None
        assert body["result"] is not None
        assert isinstance(body["result"]["level"], str)
        assert isinstance(body["theta"], float)

        # Backward compat: GET placement y POST submit siguen funcionando.
        g = client.get("/api/academy/placement")
        assert g.status_code == 200
        submit = client.post(
            "/api/academy/placement/submit",
            params={"user_id": a},
            json={"answers": correct_by_id},
        )
        assert submit.status_code == 200
