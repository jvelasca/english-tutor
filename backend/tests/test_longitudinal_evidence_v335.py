"""Tests de V3.35 — Longitudinal Learning Evidence 1.0 (P1-1).

El motor de recall de V3.34 medía la retención anclada a la PRIMERA exposición:
`D0 → D+3` acreditaba, pero también `D+3 → D+4` y cualquier repetición futura
(el ancla nunca se movía). V3.35 encadena el ancla:

    evento_1 → intervalo_1 → evento_2 → intervalo_2 → evento_3 → ...

Aquí se cubren:

- la decisión pura `delayed_retrieval_decision` (ancla, intervalo exigido por
  FSRS, suelo determinista, primera recuperación);
- el ancla encadenada en `record_retrievals` + gate FSRS `due_at`;
- el ledger `learning_evidence` (attempts vs successes vs días vs intervalos),
  su aislamiento por usuario y su derivación del intervalo anterior;
- `event_role` (evidence/telemetry/informative) en `learning_events`;
- la exposición aditiva de la evidencia en el léxico.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import evidence as evidence_svc
from services import lexicon


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _row(uid: str, word: str) -> dict:
    return next(
        (r for r in vocabulary_repo.get_vocabulary(uid) if r["word"] == word),
        {},
    )


# --- Decisión pura del ancla (P1-1) -----------------------------------------


def test_delayed_decision_first_retrieval_anchors_on_first_signal():
    row = {"first_seen": "2026-09-01T10:00:00+00:00", "first_exposed_at": ""}
    decision = lexicon.delayed_retrieval_decision(
        row, now="2026-09-02T10:00:00+00:00"
    )
    assert decision["anchor_at"] == "2026-09-01T10:00:00+00:00"
    assert decision["interval_days"] == 1.0
    assert decision["required_days"] == 1.0
    assert decision["credited"] is True


def test_delayed_decision_chains_from_last_valid_retrieval():
    """El ancla es la ÚLTIMA recuperación: D+3 acredita, pero D+3→D+4 ya no
    acredita automáticamente (el intervalo se mide desde D+3)."""
    row = {
        "first_seen": "2026-09-01T10:00:00+00:00",
        "last_retrieval_at": "2026-09-04T10:00:00+00:00",
    }
    same_day = lexicon.delayed_retrieval_decision(
        row, now="2026-09-04T20:00:00+00:00"
    )
    assert same_day["anchor_at"] == "2026-09-04T10:00:00+00:00"
    assert same_day["credited"] is False

    next_day = lexicon.delayed_retrieval_decision(
        row, now="2026-09-05T10:00:00+00:00"
    )
    assert next_day["anchor_at"] == "2026-09-04T10:00:00+00:00"
    assert next_day["interval_days"] == 1.0
    assert next_day["credited"] is True


def test_delayed_decision_anchor_is_latest_recall_or_retrieval():
    """Recall (texto) y retrieval (micro-drill) comparten la cadena longitudinal:
    el ancla es el más reciente de los dos."""
    row = {
        "first_seen": "2026-09-01T10:00:00+00:00",
        "last_retrieval_at": "2026-09-03T10:00:00+00:00",
        "last_recall_at": "2026-09-07T10:00:00+00:00",
    }
    decision = lexicon.delayed_retrieval_decision(
        row, now="2026-09-08T10:00:00+00:00"
    )
    assert decision["anchor_at"] == "2026-09-07T10:00:00+00:00"
    assert decision["credited"] is True


def test_delayed_decision_fsrs_gate_requires_due_at():
    """Con carta FSRS, el intervalo exigido es el vencimiento del scheduler."""
    row = {"first_seen": "2026-09-05T10:00:00+00:00"}
    due = "2026-09-09T10:00:00+00:00"  # intervalo FSRS de 4 días
    early = lexicon.delayed_retrieval_decision(
        row, now="2026-09-07T10:00:00+00:00", due_at=due
    )
    assert early["required_days"] == 4.0
    assert early["credited"] is False

    on_time = lexicon.delayed_retrieval_decision(row, now=due, due_at=due)
    assert on_time["credited"] is True


def test_delayed_decision_never_below_floor():
    """Un intervalo FSRS diminuto (lapse) no es una recuperación demorada."""
    row = {"first_seen": "2026-09-05T10:00:00+00:00"}
    decision = lexicon.delayed_retrieval_decision(
        row,
        now="2026-09-05T12:00:00+00:00",
        due_at="2026-09-05T11:00:00+00:00",
    )
    assert decision["required_days"] == float(lexicon.RETENTION_MIN_INTERVAL_DAYS)
    assert decision["credited"] is False


def test_delayed_decision_without_anchor_never_credits():
    decision = lexicon.delayed_retrieval_decision(
        {}, now="2026-09-05T10:00:00+00:00"
    )
    assert decision == {
        "anchor_at": "",
        "interval_days": None,
        "required_days": float(lexicon.RETENTION_MIN_INTERVAL_DAYS),
        "credited": False,
    }


# --- Ancla encadenada en el repositorio + gate FSRS -------------------------


def test_record_retrievals_chain_anchor_end_to_end(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-09-01T10:00:00+00:00",  # exposición (primera señal)
            "2026-09-04T10:00:00+00:00",  # retrieval +3d: acredita
            "2026-09-05T10:00:00+00:00",  # retrieval +1d desde el anterior
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    vocabulary_repo.record_exposures(a, ["sun"])
    assert vocabulary_repo.record_retrievals(a, ["sun"]) is True
    assert _row(a, "sun")["retrieval_successes"] == 1
    assert vocabulary_repo.record_retrievals(a, ["sun"]) is True
    assert _row(a, "sun")["retrieval_successes"] == 2
    assert _row(a, "sun")["retrieval_days"] == 2


def test_record_retrievals_fsrs_gate_blocks_early(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-09-05T10:00:00+00:00",  # exposición
            "2026-09-07T10:00:00+00:00",  # retrieval a +2d
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    vocabulary_repo.record_exposures(a, ["sun"])
    # La carta FSRS vence a 4 días: a 2 días el intento aún no acredita, aunque
    # supere el suelo determinista de 1 día.
    vocabulary_repo.record_retrievals(
        a, ["sun"], due_at="2026-09-09T10:00:00+00:00"
    )
    assert _row(a, "sun")["retrieval_successes"] == 0


# --- Ledger de evidencia ----------------------------------------------------


def test_classify_event_role_separates_signals():
    assert (
        evidence_svc.classify_event_role("exercise", "drill:cat:recognition:ok")
        == "informative"
    )
    assert (
        evidence_svc.classify_event_role("exercise", "drill:cat:recognition:ko")
        == "informative"
    )
    assert (
        evidence_svc.classify_event_role("exercise", "drill:cat:recall:ok")
        == "evidence"
    )
    assert evidence_svc.classify_event_role("exercise", "drill:cat:ok") == "evidence"
    assert (
        evidence_svc.classify_event_role("exercise", "drill:big cat:sentence:ok")
        == "evidence"
    )
    assert (
        evidence_svc.classify_event_role("exercise", "drill:cat:unclear")
        == "telemetry"
    )
    assert evidence_svc.classify_event_role("exercise", "otro") == "telemetry"
    assert evidence_svc.classify_event_role("message", "hola") == "telemetry"


def test_summarize_evidence_counts_attempts_successes_days_intervals():
    rows = [
        {
            "success": 1,
            "occurred_at": "2026-09-01T10:00:00+00:00",
            "interval_since_last_evidence": None,
        },
        {
            "success": 1,
            "occurred_at": "2026-09-01T20:00:00+00:00",
            "interval_since_last_evidence": 0.4,
        },
        {
            "success": 0,
            "occurred_at": "2026-09-02T10:00:00+00:00",
            "interval_since_last_evidence": None,
        },
        {
            "success": 1,
            "occurred_at": "2026-09-04T10:00:00+00:00",
            "interval_since_last_evidence": 3.0,
        },
    ]
    out = evidence_svc.summarize_evidence(rows)
    assert out["attempts"] == 4
    assert out["successes"] == 3
    assert out["distinct_success_days"] == 2  # 09-01 y 09-04
    assert out["intervals"] == [0.4, 3.0]


def test_record_evidence_derives_interval_from_previous(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    first = evidence_repo.record_evidence(
        a, target_type="lexicon", target_id="cat", task="retrieval", success=True
    )
    assert first is not None
    assert first["interval_since_last_evidence"] is None  # primera observación
    second = evidence_repo.record_evidence(
        a, target_type="lexicon", target_id="cat", task="retrieval", success=True
    )
    assert second is not None
    assert second["interval_since_last_evidence"] is not None  # desde el anterior
    other = evidence_repo.record_evidence(
        a, target_type="lexicon", target_id="dog", task="retrieval", success=True
    )
    assert other is not None
    assert other["interval_since_last_evidence"] is None


def test_evidence_isolated_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    evidence_repo.record_evidence(
        a, target_type="lexicon", target_id="cat", task="retrieval", success=True
    )
    assert evidence_repo.list_evidence(b) == []
    mine = evidence_repo.list_evidence(a)
    assert [e["target_id"] for e in mine] == ["cat"]


def test_learning_events_persist_event_role(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    learning_repo.record_event(a, "exercise", "drill:cat:recognition:ok")
    learning_repo.record_event(a, "exercise", "drill:cat:recall:ok")
    roles = {
        e["detail"]: e["event_role"]
        for e in learning_repo.list_events(a, "exercise")
    }
    assert roles["drill:cat:recognition:ok"] == "informative"
    assert roles["drill:cat:recall:ok"] == "evidence"


def test_recall_miss_records_attempt_and_negative_evidence(monkeypatch, tmp_path):
    """V3.35: un fallo de recall es evidencia negativa (intento ≠ éxito)."""
    a, _b = _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "quokka",
        pos="noun",
        definition="a small Australian marsupial",
        translation="marsupial australiano",
        generator_version="test",
    )
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": a},
            json={"word": "quokka", "answer": "nope"},
        )
        assert res.status_code == 200, res.text

    row = _row(a, "quokka")
    assert row["recall_attempts"] == 1
    assert row["recall_successes"] == 0
    events = evidence_repo.list_evidence(a, "quokka", target_type="lexicon")
    assert len(events) == 1
    assert events[0]["success"] == 0
    assert events[0]["task"] == "recall"
    assert events[0]["event_role"] == "evidence"


def test_lexicon_exposes_longitudinal_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "quokka",
        pos="noun",
        definition="a small Australian marsupial",
        translation="marsupial australiano",
        generator_version="test",
    )
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": a},
            json={"word": "quokka", "answer": "quokka"},
        )
        res = client.get("/api/vocabulary/lexicon", params={"user_id": a})
        assert res.status_code == 200, res.text
        body = res.json()

    item = next(i for i in body["items"] if i["word"] == "quokka")
    assert item["competence"]["recall_attempts"] == 1
    assert item["competence"]["recall_successes"] == 1
    assert item["evidence"]["attempts"] == 1
    assert item["evidence"]["successes"] == 1
    assert item["evidence"]["distinct_success_days"] == 1
