"""Tests del Course Engine (V1.38): secuencia Course→Unit→Lesson, gating por
objetivo y posición actual ("¿dónde estoy?")."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import course as course_svc
from services.curriculum import load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Gating por objetivo ---------------------------------------------------


def test_gate_objective_ids_are_those_with_checks():
    lv = load_level("a1")
    gates = course_svc.gate_objective_ids(lv)
    assert gates
    for obj in lv.objectives():
        if obj.assessable_skills():
            assert obj.id in gates
        else:
            assert obj.id not in gates


def test_initial_status_first_available_rest_locked():
    lv = load_level("a1")
    statuses = course_svc.objective_gated_status(lv, set())
    objs = lv.objectives()
    assert statuses[objs[0].id] == "available"
    assert all(statuses[o.id] == "locked" for o in objs[1:])


def test_mastering_first_unlocks_second():
    lv = load_level("a1")
    objs = lv.objectives()
    mastered = {objs[0].id}
    statuses = course_svc.objective_gated_status(lv, mastered)
    assert statuses[objs[0].id] == "mastered"
    assert statuses[objs[1].id] == "available"
    assert all(statuses[o.id] == "locked" for o in objs[2:])


def test_attempted_but_not_mastered_is_review():
    lv = load_level("a1")
    objs = lv.objectives()
    attempts = {objs[0].id: {"correct": 1, "incorrect": 1}}
    statuses = course_svc.objective_gated_status(lv, set(), attempts)
    assert statuses[objs[0].id] == "review"
    # El siguiente sigue bloqueado hasta dominar el primero.
    assert statuses[objs[1].id] == "locked"


# --- Secuencia de unidades/lecciones ---------------------------------------


def test_unit_sequence_has_done_current_locked():
    lv = load_level("a1")
    # Dominamos todo el primer módulo: su primera unidad queda done, el resto
    # current/locked según la secuencia lineal.
    first_unit = next(
        u for m in lv.modules for u in m.units
    )
    first_unit_obj_ids = [
        o.id for les in first_unit.lessons for o in les.objectives
    ]
    mastered = set(first_unit_obj_ids)
    units = course_svc.unit_sequence(lv, mastered)
    assert units
    assert units[0]["status"] == "done"
    assert units[0]["progress"] == 1.0
    assert any(u["status"] == "current" for u in units[1:])


def test_unit_sequence_shape():
    lv = load_level("a1")
    units = course_svc.unit_sequence(lv, set())
    for unit in units:
        assert {"unit_id", "unit_title", "status", "lessons"} <= set(unit)
        assert unit["progress"] == 0.0
        for lesson in unit["lessons"]:
            assert {"lesson_id", "lesson_title", "objectives"} <= set(lesson)
            for obj in lesson["objectives"]:
                assert "status" in obj


# --- Posición actual -------------------------------------------------------


def test_current_position_starts_at_first_objective():
    lv = load_level("a1")
    objs = lv.objectives()
    pos = course_svc.current_position(lv, set())
    assert pos["objective_id"] == objs[0].id
    assert pos["unit_index"] == 0
    assert pos["complete"] is False
    assert pos["objective_order"] == 1
    assert pos["module_id"] and pos["unit_id"] and pos["lesson_id"]


def test_current_position_when_level_complete():
    lv = load_level("a1")
    objs = lv.objectives()
    pos = course_svc.current_position(lv, {o.id for o in objs})
    assert pos["complete"] is True
    assert pos["objective_id"] is None
    assert pos["progress"] == 1.0


# --- Mapa del curso + endpoint ---------------------------------------------


def test_course_map_shape():
    lv = load_level("a1")
    m = course_svc.course_map(lv, set())
    assert m["level_id"] == "a1"
    assert m["units"]
    assert m["position"]["objective_id"] == lv.objectives()[0].id
    expected_progress = {
        "mastered": 0,
        "total": len(lv.objectives()),
        "progress": 0.0,
    }
    assert m["progress"] == expected_progress


def test_endpoint_course_map(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/course/a1", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["level_id"] == "a1"
    assert body["units"]
    assert body["position"]["objective_id"]
    assert body["progress"]["total"] > 20


def test_endpoint_course_map_blocked_level(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/academy/course/b1", params={"user_id": a})
    assert r.status_code == 403
