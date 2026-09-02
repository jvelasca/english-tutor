"""Tests de Assessment 2.0 (V2.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import assessment_v2 as av2
from services.curriculum import load_assessments, load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Motor puro -------------------------------------------------------------


def test_assessment_kinds_are_five():
    assert av2.ASSESSMENT_KINDS == (
        "formative",
        "unit",
        "progress",
        "level",
        "retention",
    )


def test_build_formative_from_objective_checks():
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    instrument = av2.build_formative(obj)
    assert instrument["kind"] == "formative"
    assert instrument["objective_id"] == obj.id
    assert len(instrument["items"]) == len(obj.checks)
    assert "correct_index" not in instrument["items"][0]


def test_build_unit_and_progress_cap_items():
    lv = load_level("a1")
    units = av2.ordered_units(lv)
    assert units
    unit = av2.build_unit(lv, units[0].id)
    assert unit is not None
    assert unit["kind"] == "unit"
    assert len(unit["items"]) <= av2.ITEM_CAPS["unit"]

    anchor = units[min(len(units) - 1, av2.PROGRESS_UNIT_SPAN - 1)].id
    progress = av2.build_progress(lv, anchor)
    assert progress is not None
    assert progress["kind"] == "progress"
    assert len(progress["unit_ids"]) <= av2.PROGRESS_UNIT_SPAN
    assert len(progress["items"]) <= av2.ITEM_CAPS["progress"]


def test_evaluate_pass_and_fail():
    scored = {
        "overall": 0.8,
        "correct": 8,
        "total": 10,
        "skills": {"grammar": {"correct": 8, "total": 10, "score": 0.8}},
    }
    ok = av2.evaluate("unit", scored)
    assert ok["passed"] is True
    assert ok["threshold"] == av2.PASS_THRESHOLDS["unit"]

    scored["overall"] = 0.5
    scored["skills"]["grammar"]["score"] = 0.5
    bad = av2.evaluate("unit", scored)
    assert bad["passed"] is False


def test_retention_delta_and_stable():
    first = {
        "overall": 0.9,
        "skills": {"grammar": {"score": 0.9}, "vocabulary": {"score": 0.8}},
    }
    delayed = {
        "overall": 0.85,
        "skills": {"grammar": {"score": 0.8}, "vocabulary": {"score": 0.85}},
    }
    delta = av2.retention_delta(first, delayed)
    assert delta["retention_rate"] == pytest.approx(0.85 / 0.9, rel=1e-3)
    assert delta["stable"] is True
    assert len(delta["by_skill"]) == 2


def test_mastery_evidence_gate_requires_full_ladder():
    incomplete = av2.mastery_evidence_gate({"familiar": 2, "transfer": 1})
    assert incomplete["met"] is False
    assert "novel" in incomplete["missing"]
    assert "delayed" in incomplete["missing"]

    complete = av2.mastery_evidence_gate(
        {"familiar": 2, "transfer": 1, "novel": 1, "delayed": 1}
    )
    assert complete["met"] is True
    assert complete["missing"] == []


def test_retention_due_window():
    now = datetime(2026, 9, 2, tzinfo=timezone.utc)
    recent = (now - timedelta(days=3)).isoformat()
    old = (now - timedelta(days=10)).isoformat()
    assert av2.retention_due(recent, now=now.isoformat()) is False
    assert av2.retention_due(old, now=now.isoformat()) is True


def test_ladder_status_next_kind():
    status = av2.ladder_status(
        completed_kinds={"formative"},
        units_done=1,
        has_exam=True,
        retention_ready=False,
    )
    assert status["readiness"]["next_kind"] == "unit"
    kinds = {s["kind"]: s for s in status["steps"]}
    assert kinds["progress"]["available"] is False
    assert kinds["retention"]["available"] is False


def test_evidence_kind_for_mapping():
    assert av2.evidence_kind_for("formative") == "familiar"
    assert av2.evidence_kind_for("unit") == "transfer"
    assert av2.evidence_kind_for("retention") == "delayed"


# --- Flujo HTTP -------------------------------------------------------------


def test_assessment_v2_formative_http_loop(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    # Matricular para no bloquear por enrollment.
    academy_repo.enroll(uid, "a1", "A1")

    client = TestClient(app)
    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "formative",
            "level_id": "a1",
            "objective_id": obj.id,
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["kind"] == "formative"
    assert body["status"] == "open"
    assert len(body["instrument"]["items"]) >= 1

    answers = {c.id: c.correct_index for c in obj.checks}
    done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": body["session_id"], "answers": answers},
    )
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["status"] == "done"
    assert result["result"]["passed"] is True
    assert result["result"]["overall"] == 1.0

    ladder = client.get(f"/api/academy/assessment/v2/ladder?user_id={uid}&level_id=a1")
    assert ladder.status_code == 200
    data = ladder.json()
    assert data["assessment_version"] == av2.ASSESSMENT_VERSION
    steps = {s["kind"]: s for s in data["steps"]}
    assert steps["formative"]["completed"] is True


def test_assessment_v2_unit_and_level(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    lv = load_level("a1")
    unit = av2.ordered_units(lv)[0]
    client = TestClient(app)

    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "unit", "level_id": "a1", "unit_id": unit.id},
    )
    assert start.status_code == 200, start.text
    session = start.json()
    index = {c.id: c for o in lv.objectives() for c in o.checks}
    answers = {
        it["id"]: index[it["id"]].correct_index
        for it in session["instrument"]["items"]
        if it["id"] in index
    }
    done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": session["session_id"], "answers": answers},
    )
    assert done.status_code == 200
    assert done.json()["result"]["passed"] is True

    exam = load_assessments().exams["a1"]
    level_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "level", "level_id": "a1"},
    )
    assert level_start.status_code == 200
    level_session = level_start.json()
    level_answers = {it.id: it.correct_index for it in exam.items}
    level_done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={
            "session_id": level_session["session_id"],
            "answers": level_answers,
        },
    )
    assert level_done.status_code == 200
    assert level_done.json()["result"]["passed"] is True


def test_assessment_v2_retention_delta_http(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    lv = load_level("a1")
    unit = av2.ordered_units(lv)[0]
    client = TestClient(app)

    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "unit", "level_id": "a1", "unit_id": unit.id},
    )
    session = start.json()
    index = {c.id: c for o in lv.objectives() for c in o.checks}
    answers = {
        it["id"]: index[it["id"]].correct_index
        for it in session["instrument"]["items"]
        if it["id"] in index
    }
    first = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": session["session_id"], "answers": answers},
    ).json()

    ret_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "retention",
            "level_id": "a1",
            "source_session_id": first["session_id"],
        },
    )
    assert ret_start.status_code == 200
    ret_session = ret_start.json()
    # Fallo parcial: primer ítem incorrecto.
    ret_answers = dict(answers)
    first_id = ret_session["instrument"]["items"][0]["id"]
    correct = index[first_id].correct_index
    ret_answers[first_id] = (correct + 1) % len(index[first_id].options)

    ret_done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": ret_session["session_id"], "answers": ret_answers},
    )
    assert ret_done.status_code == 200
    body = ret_done.json()
    assert body["retention"] is not None
    assert body["retention"]["delayed_overall"] < body["retention"]["initial_overall"]
    assert body["result"]["kind"] == "retention"
