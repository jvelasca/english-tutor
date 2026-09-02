"""Tests de FSRS-lite (V2.11)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs

NOW = "2026-09-02T10:00:00+00:00"


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Motor puro -------------------------------------------------------------


def test_fsrs_grades_and_version():
    assert fsrs.GRADES == (1, 2, 3, 4)
    assert fsrs.FSRS_VERSION.startswith("2.11")


def test_grade_from_score_buckets():
    assert fsrs.grade_from_score(0.2) == fsrs.GRADE_AGAIN
    assert fsrs.grade_from_score(0.6) == fsrs.GRADE_HARD
    assert fsrs.grade_from_score(0.8) == fsrs.GRADE_GOOD
    assert fsrs.grade_from_score(0.95) == fsrs.GRADE_EASY


def test_retrievability_decays_with_time():
    near = fsrs.retrievability(10.0, 1.0)
    far = fsrs.retrievability(10.0, 30.0)
    assert near > far
    assert 0.0 < far < 1.0


def test_interval_grows_with_stability():
    short = fsrs.interval_for_stability(2.0)
    long = fsrs.interval_for_stability(20.0)
    assert long > short


def test_schedule_again_vs_good():
    card = fsrs.empty_card(
        target_type="skill",
        target_id="grammar",
        label="grammar",
        now=NOW,
    )
    again = fsrs.schedule(card, fsrs.GRADE_AGAIN, now=NOW)
    good = fsrs.schedule(card, fsrs.GRADE_GOOD, now=NOW)
    assert again["state"] == "relearning"
    assert again["lapses"] == 0  # fallo en learning, aún no es lapse de review
    assert good["stability"] > again["stability"]
    assert good["due_at"] > again["due_at"]

    later = (
        datetime.fromisoformat(NOW) + timedelta(days=2)
    ).isoformat()
    failed = fsrs.schedule(good, fsrs.GRADE_AGAIN, now=later)
    assert failed["lapses"] == 1
    assert failed["state"] == "relearning"


def test_schedule_second_review_increases_stability():
    card = fsrs.empty_card(
        target_type="lexicon", target_id="hello", now=NOW
    )
    first = fsrs.schedule(card, fsrs.GRADE_GOOD, now=NOW)
    later = (
        datetime.fromisoformat(NOW) + timedelta(days=3)
    ).isoformat()
    second = fsrs.schedule(first, fsrs.GRADE_GOOD, now=later)
    assert second["reps"] == 2
    assert second["stability"] >= first["stability"]


def test_explain_has_audit_fields():
    card = fsrs.seed_card_from_evidence(
        target_type="skill",
        target_id="listening",
        label="listening",
        score=0.85,
        last_evidence_at=NOW,
        why="forgetting-curve",
        now=NOW,
    )
    explained = fsrs.explain(card, now=NOW)
    assert explained["what"]["target_id"] == "listening"
    assert explained["why"] == "forgetting-curve"
    assert "due_at" in explained["when"]
    assert "stability" in explained["how_strong"]
    assert "at" in explained["last_evidence"]
    assert "due_at" in explained["next_evidence"]


def test_due_queue_orders_by_urgency():
    now = datetime.fromisoformat(NOW)
    weak = fsrs.seed_card_from_evidence(
        target_type="skill",
        target_id="grammar",
        label="grammar",
        score=0.4,
        why="weak-skill",
        now=NOW,
    )
    weak["due_at"] = NOW
    weak["stability"] = 0.5
    weak["reps"] = 2
    weak["last_review_at"] = (now - timedelta(days=20)).isoformat()

    strong = fsrs.seed_card_from_evidence(
        target_type="skill",
        target_id="vocabulary",
        label="vocabulary",
        score=0.95,
        why="maintenance",
        now=NOW,
    )
    strong["due_at"] = NOW
    strong["stability"] = 30.0
    strong["reps"] = 5
    strong["last_review_at"] = (now - timedelta(days=1)).isoformat()

    queue = fsrs.due_queue([strong, weak], now=NOW, limit=10)
    assert queue[0]["target_id"] == "grammar"


# --- HTTP -------------------------------------------------------------------


def test_fsrs_due_and_review_http(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    # Evidencia de destreza débil para que sync cree cartas.
    academy_repo.apply_skill_evidence(
        uid,
        "a1",
        "grammar",
        {
            "score": 0.4,
            "recent_score": 0.4,
            "confidence": 0.3,
            "streak": 0,
            "attempts": 3,
            "last_seen_at": (
                datetime.now(timezone.utc) - timedelta(days=40)
            ).isoformat(),
        },
    )
    academy_repo.record_evidence(
        uid,
        "a1",
        "",
        "grammar",
        "item-1",
        source="assessment_v2",
        result=0.4,
        curriculum_version="test",
        assessment_version="2.0.0",
        evidence_kind="familiar",
    )

    client = TestClient(app)
    due = client.get(f"/api/academy/fsrs/due?user_id={uid}")
    assert due.status_code == 200, due.text
    body = due.json()
    assert body["fsrs_version"] == fsrs.FSRS_VERSION
    assert body["due_count"] >= 1
    card = body["cards"][0]
    assert card["explain"]["what"]["target_type"] in fsrs.TARGET_TYPES
    assert "why" in card["explain"]

    review = client.post(
        f"/api/academy/fsrs/review?user_id={uid}",
        json={
            "target_type": card["target_type"],
            "target_id": card["target_id"],
            "grade": 3,
        },
    )
    assert review.status_code == 200, review.text
    out = review.json()
    assert out["card"]["reps"] >= 1
    assert out["explain"]["how_strong"]["stability"] > 0

    summary = client.get(f"/api/academy/fsrs/summary?user_id={uid}")
    assert summary.status_code == 200
    assert summary.json()["total"] >= 1


def test_fsrs_sync_from_lexicon(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(uid, ["apple", "banana"])
    # Una sola aparición → learning/weak candidate.
    client = TestClient(app)
    sync = client.post(f"/api/academy/fsrs/sync?user_id={uid}")
    assert sync.status_code == 200, sync.text
    data = sync.json()
    assert data["total"] >= 1
    assert data["by_type"].get("lexicon", 0) >= 1
