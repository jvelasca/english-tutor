"""Tests de retención retardada (delayed retention) del diagnóstico de listening.

Cubre `delayed_retention` con `created_at` controlados y la exposición del campo
`retention` en el endpoint de diagnóstico.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import QUESTION_BANK, delayed_retention, listening_diagnostic

NOW = "2026-08-26T00:00:00+00:00"


def _iso(days_offset: float) -> str:
    """Timestamp ISO UTC a `days_offset` días del 1-ene-2026."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(days=days_offset)).isoformat()


def _attempt(qid: str, correct: bool, created_at: str | None = None) -> dict:
    row = {"question_id": qid, "correct": correct}
    if created_at is not None:
        row["created_at"] = created_at
    return row


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_delayed_retention_empty():
    result = delayed_retention([])
    assert result["total_questions"] == 0
    assert result["immediate_accuracy"] is None
    assert result["delayed_accuracy"] is None
    assert result["retention_rate"] is None
    assert result["by_bucket"] == []


def test_delayed_retention_single_exposure_per_question():
    rows = [
        _attempt("q1", True, _iso(0)),
        _attempt("q2", False, _iso(0)),
    ]
    result = delayed_retention(rows, now=NOW)
    assert result["total_questions"] == 2
    assert result["immediate_accuracy"] == 50.0
    assert result["delayed_accuracy"] is None
    assert result["retention_rate"] is None
    assert result["by_bucket"] == []


def test_delayed_retention_one_day_re_exposure_is_not_delayed():
    rows = [
        _attempt("q1", True, _iso(0)),
        _attempt("q1", False, _iso(1)),
    ]
    result = delayed_retention(rows, now=NOW)
    assert result["immediate_accuracy"] == 100.0
    # 1 día < 2 → no cuenta como delayed, pero sí cae en el bucket "0-2".
    assert result["delayed_accuracy"] is None
    assert result["retention_rate"] is None
    assert result["by_bucket"] == [
        {"bucket": "0-2", "attempts": 1, "correct": 0, "accuracy": 0.0}
    ]


def test_delayed_retention_buckets_2_7_30():
    rows = [
        _attempt("q1", True, _iso(0)),
        _attempt("q1", True, _iso(3)),
        _attempt("q2", True, _iso(0)),
        _attempt("q2", False, _iso(10)),
        _attempt("q3", True, _iso(0)),
        _attempt("q3", True, _iso(40)),
    ]
    result = delayed_retention(rows, now=NOW)
    assert result["total_questions"] == 3
    assert result["immediate_accuracy"] == 100.0
    # 2 aciertos de 3 re-exposiciones (q1 3d, q2 10d, q3 40d).
    assert result["delayed_accuracy"] == round(2 / 3 * 100, 1)
    assert result["retention_rate"] == round(
        result["delayed_accuracy"] / result["immediate_accuracy"], 3
    )
    buckets = {b["bucket"]: b for b in result["by_bucket"]}
    assert set(buckets) == {"2-7", "7-30", "30+"}
    assert buckets["2-7"] == {
        "bucket": "2-7",
        "attempts": 1,
        "correct": 1,
        "accuracy": 100.0,
    }
    assert buckets["7-30"] == {
        "bucket": "7-30",
        "attempts": 1,
        "correct": 0,
        "accuracy": 0.0,
    }
    assert buckets["30+"] == {
        "bucket": "30+",
        "attempts": 1,
        "correct": 1,
        "accuracy": 100.0,
    }


def test_delayed_retention_first_exposure_not_in_bucket():
    rows = [
        _attempt("q1", False, _iso(0)),
        _attempt("q1", True, _iso(0)),  # misma jornada: bucket 0-2, no delayed
    ]
    result = delayed_retention(rows, now=NOW)
    total_bucket_attempts = sum(b["attempts"] for b in result["by_bucket"])
    assert total_bucket_attempts == 1
    assert result["by_bucket"][0]["bucket"] == "0-2"


def test_delayed_retention_retention_rate_none_when_immediate_zero():
    rows = [
        _attempt("q1", False, _iso(0)),
        _attempt("q1", True, _iso(5)),
    ]
    result = delayed_retention(rows, now=NOW)
    assert result["immediate_accuracy"] == 0.0
    assert result["delayed_accuracy"] == 100.0
    assert result["retention_rate"] is None


def test_delayed_retention_retention_rate_computed():
    rows = [
        _attempt("q1", True, _iso(0)),
        _attempt("q1", False, _iso(5)),
    ]
    result = delayed_retention(rows, now=NOW)
    assert result["immediate_accuracy"] == 100.0
    assert result["delayed_accuracy"] == 0.0
    assert result["retention_rate"] == 0.0


def test_delayed_retention_ignores_future_re_exposures():
    # `now` anterior a una re-exposición → esa re-exposición se descarta.
    rows = [
        _attempt("q1", True, _iso(0)),
        _attempt("q1", True, _iso(5)),
    ]
    result = delayed_retention(rows, now=_iso(3))
    assert result["delayed_accuracy"] is None
    assert result["by_bucket"] == []


def test_listening_diagnostic_includes_retention():
    rows = [
        _attempt("q1", True, _iso(0)),
        _attempt("q1", True, _iso(3)),
    ]
    diag = listening_diagnostic(rows, now=NOW)
    assert diag["retention"]["immediate_accuracy"] == 100.0
    assert diag["retention"]["delayed_accuracy"] == 100.0
    assert diag["retention"]["retention_rate"] == 1.0


def test_diagnostic_endpoint_includes_retention(monkeypatch, tmp_path):
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
    retention = r.json()["retention"]
    assert retention["total_questions"] == 1
    assert retention["immediate_accuracy"] == 100.0
    assert retention["delayed_accuracy"] is None
    assert retention["retention_rate"] is None
    assert retention["by_bucket"] == []
