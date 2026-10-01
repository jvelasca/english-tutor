"""V3.89 (Listening robusto): la cola de repaso de frases falladas.

Fija el contrato que convierte el fallo en **evidencia** y no en una barrera de
navegación:

- la migración añade `listening_attempts.outcome` y la tabla
  `listening_review_queue` de forma aditiva e idempotente;
- `services/listening_review.py` clasifica el desenlace y programa la reapertura
  (puro y determinista);
- un fallo **encola** la frase y declara `immediate_retry_available`, un acierto
  la **resuelve**, y «repasar después» la **pospone** en vez de ignorarla.
"""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services import listening_review as review
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _receptive_question() -> dict:
    for q in QUESTION_BANK:
        if q["skill"] not in ("dictation", "shadowing"):
            return q
    raise AssertionError("banco sin ítems receptivos")


def _wrong_index(q: dict) -> int:
    return (q["answer_index"] + 1) % len(q["options"])


# --- Migración ---------------------------------------------------------------


def test_migration_adds_outcome_column(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cols = {
        row[1] for row in db._conn().execute("PRAGMA table_info(listening_attempts)")
    }
    assert "outcome" in cols


def test_migration_creates_review_queue_table(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    tables = {
        row[0]
        for row in db._conn().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "listening_review_queue" in tables


def test_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # re-arranque: no debe fallar ni duplicar
    cols = {
        row[1] for row in db._conn().execute("PRAGMA table_info(listening_attempts)")
    }
    assert "outcome" in cols


# --- Política pura -----------------------------------------------------------


def test_outcome_first_try_is_strong_success():
    assert review.outcome_for(True, 1) == review.OUTCOME_CORRECT_FIRST


def test_outcome_after_retry_is_assisted_success():
    assert review.outcome_for(True, 2) == review.OUTCOME_CORRECT_RETRY


def test_outcome_wrong_is_plain_failure():
    assert review.outcome_for(False, 1) == review.OUTCOME_WRONG


def test_outcome_wrong_with_solution_is_assisted_failure():
    assert (
        review.outcome_for(False, 1, solution_shown=True)
        == review.OUTCOME_SOLUTION_SHOWN
    )
    assert review.outcome_for(False, 1, hint_used=True) == review.OUTCOME_HINT_USED


def test_outcome_always_in_catalog():
    for correct in (True, False):
        for attempt in (0, 1, 2, 5):
            for hint in (False, True):
                for shown in (False, True):
                    value = review.outcome_for(
                        correct, attempt, hint_used=hint, solution_shown=shown
                    )
                    assert value in review.OUTCOMES


def test_review_interval_escalates_and_is_capped():
    assert review.review_interval_hours(1) == 24
    assert review.review_interval_hours(2) == 72
    assert review.review_interval_hours(3) == 168
    assert review.review_interval_hours(4) == 336
    # Acotado: cuatro fallos o más no crecen sin límite.
    assert review.review_interval_hours(99) == 336


def test_priority_rewards_fail_count():
    now = review._parse_iso("2026-09-29T10:00:00+00:00")
    once = review.priority(1, "2026-09-29T09:00:00+00:00", "gist", now)
    four = review.priority(4, "2026-09-29T09:00:00+00:00", "gist", now)
    assert four > once


def test_priority_rewards_recent_failure():
    now = review._parse_iso("2026-09-29T10:00:00+00:00")
    recent = review.priority(1, "2026-09-29T09:00:00+00:00", "gist", now)
    old = review.priority(1, "2026-08-01T09:00:00+00:00", "gist", now)
    assert recent > old


def test_priority_rewards_pedagogical_skill_weight():
    now = review._parse_iso("2026-09-29T10:00:00+00:00")
    hard = review.priority(1, "2026-09-29T09:00:00+00:00", "inference", now)
    easy = review.priority(1, "2026-09-29T09:00:00+00:00", "recognition", now)
    assert hard > easy


def test_priority_is_deterministic():
    now = review._parse_iso("2026-09-29T10:00:00+00:00")
    a = review.priority(2, "2026-09-29T09:00:00+00:00", "detail", now)
    b = review.priority(2, "2026-09-29T09:00:00+00:00", "detail", now)
    assert a == b


def test_priority_survives_corrupt_date():
    now = review._parse_iso("2026-09-29T10:00:00+00:00")
    # Una fecha ilegible no puede tumbar la prioridad de la cola entera.
    assert review.priority(1, "no-es-fecha", "gist", now) > 0


def test_immediate_retry_is_capped_at_one():
    assert review.can_retry_immediately(1) is True
    assert review.can_retry_immediately(2) is False
    assert review.can_retry_immediately(3) is False


# --- Repositorio -------------------------------------------------------------


def test_enqueue_failure_increments_fail_count(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid,
        "c001",
        level="A1",
        skill="gist",
        next_review_at="2099-01-01T00:00:00+00:00",
        priority=5.0,
    )
    listening_repo.enqueue_failure(
        uid,
        "c001",
        level="A1",
        skill="gist",
        next_review_at="2099-01-01T00:00:00+00:00",
        priority=8.0,
        fail_count=2,
    )
    entry = listening_repo.get_queue_entry(uid, "c001")
    assert entry is not None
    assert entry["fail_count"] == 2
    assert entry["priority"] == 8.0


def test_queue_is_ordered_by_priority(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid, "low", next_review_at="2099-01-01T00:00:00+00:00", priority=1.0
    )
    listening_repo.enqueue_failure(
        uid, "high", next_review_at="2099-01-01T00:00:00+00:00", priority=9.0
    )
    rows = listening_repo.list_queue(uid)
    assert [r["question_id"] for r in rows] == ["high", "low"]


def test_mark_reviewed_removes_entry(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid, "c001", next_review_at="2099-01-01T00:00:00+00:00", priority=1.0
    )
    assert listening_repo.mark_queue_reviewed(uid, "c001") is True
    assert listening_repo.get_queue_entry(uid, "c001") is None


def test_defer_marks_state_and_keeps_entry(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid, "c001", next_review_at="2000-01-01T00:00:00+00:00", priority=1.0
    )
    assert (
        listening_repo.defer_queue_entry(
            uid, "c001", "2099-01-01T00:00:00+00:00"
        )
        is True
    )
    entry = listening_repo.get_queue_entry(uid, "c001")
    assert entry["state"] == "deferred"
    # Posponer NO borra: sigue viva para el futuro.
    assert entry is not None
    assert listening_repo.due_queue(uid, db._now()) == []


def test_enqueue_unknown_user_is_rejected(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        listening_repo.enqueue_failure(
            "no-existe", "c001", next_review_at="2099-01-01T00:00:00+00:00",
            priority=1.0,
        )
        is False
    )


# --- Endpoint: el fallo no bloquea y encola --------------------------------


def test_wrong_answer_is_queued_and_not_blocking(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": _wrong_index(q)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is False
    assert body["outcome"] == review.OUTCOME_WRONG
    assert body["queued_for_review"] is True
    # Primer fallo: queda UNA repetición inmediata (nunca un bucle).
    assert body["immediate_retry_available"] is True
    entry = listening_repo.get_queue_entry(uid, q["id"])
    assert entry is not None
    assert entry["fail_count"] == 1
    assert entry["state"] == "pending"


def test_second_wrong_attempt_has_no_immediate_retry(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "answer_index": _wrong_index(q),
                "attempt_number": 2,
            },
        )
    body = r.json()
    assert body["outcome"] == review.OUTCOME_WRONG
    assert body["immediate_retry_available"] is False
    # Y aun así la frase se registra: se puede continuar.
    assert body["queued_for_review"] is True


def test_outcome_is_persisted_on_attempt(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "answer_index": q["answer_index"],
                "attempt_number": 2,
            },
        )
    row = listening_repo.list_attempts(uid)[0]
    assert row["outcome"] == review.OUTCOME_CORRECT_RETRY


def test_correct_answer_resolves_queue_entry(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": _wrong_index(q)},
        )
        assert listening_repo.get_queue_entry(uid, q["id"]) is not None
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.json()["queued_for_review"] is False
    assert listening_repo.get_queue_entry(uid, q["id"]) is None


# --- Endpoint: consultar, posponer y resolver la cola ----------------------


def test_review_queue_endpoint_lists_pending(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": _wrong_index(q)},
        )
        r = client.get("/api/listening/review-queue", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["pending"] == 1
    assert body["entries"][0]["question_id"] == q["id"]
    assert body["entries"][0]["fail_count"] == 1
    # Como se acaba de fallar, aún no vence.
    assert body["due"] == 0


def test_defer_endpoint_postpones_entry(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid, "c001", level="A1", skill="gist",
        next_review_at="2000-01-01T00:00:00+00:00", priority=3.0,
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/review-queue/c001/defer",
            params={"user_id": uid},
            json={"hours": 48},
        )
    assert r.status_code == 200
    assert r.json()["state"] == "deferred"


def test_due_deferred_returns_to_the_pending_queue(monkeypatch, tmp_path):
    """«Repasar después» reaparece cuando llega la fecha; antes se quedaba fuera."""
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid, "c001", level="A1", skill="gist",
        next_review_at="2099-01-01T00:00:00+00:00", priority=3.0,
    )
    listening_repo.defer_queue_entry(uid, "c001", "2000-01-01T00:00:00+00:00")
    with TestClient(app) as client:
        r = client.get("/api/listening/review-queue", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["pending"] == 1
    assert body["due"] == 1
    assert body["entries"][0]["question_id"] == "c001"
    assert body["entries"][0]["state"] == "pending"


def test_defer_unknown_entry_is_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/review-queue/no-existe/defer",
            params={"user_id": uid},
            json={"hours": 24},
        )
    assert r.status_code == 404


def test_resolve_endpoint_removes_entry(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.enqueue_failure(
        uid, "c001", next_review_at="2000-01-01T00:00:00+00:00", priority=3.0
    )
    with TestClient(app) as client:
        r = client.delete(
            "/api/listening/review-queue/c001", params={"user_id": uid}
        )
    assert r.status_code == 204
    assert listening_repo.get_queue_entry(uid, "c001") is None
