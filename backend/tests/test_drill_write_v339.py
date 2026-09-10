"""V3.39 (Fase 3B) — actividad de escritura del drill (`written_production`).

El motor de tarea óptima detectaba el hueco `spoken ✓ / written ✗` pero no era
accionable. Esta actividad lo cierra: el alumno escribe una frase PROPIA con la
palabra objetivo, el servidor la puntúa de forma determinista (unidad alineada +
longitud mínima, sin LLM) y la evidencia declara `skill="written_production"` con
`activity_id="drill:write"` y apoyo `independent`. El fallo también se registra
clasificado (taxonomía `WRITE_ERROR_TYPES`): lo que no se produjo es señal.

Se mantiene "señal ≠ evidencia": el paso no declara dominio ni toca la
recuperación demorada (D5/E3).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import lexicon
from services.evidence import WRITE_ERROR_TYPES


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, cefr: str = "A1") -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


def _post_write(client: TestClient, uid: str, word: str, text: str) -> dict:
    res = client.post(
        "/api/vocabulary/drill/write-attempt",
        params={"user_id": uid},
        json={"word": word, "text": text, "response_time_ms": 4200},
    )
    assert res.status_code == 200, res.text
    return res.json()


# ------------------------------------------------------------ scoring puro


def test_score_write_attempt_passes_with_aligned_word_and_minimum_length():
    got = lexicon.score_write_attempt(
        "travel", "I usually travel by train in summer."
    )
    assert got == {
        "used_word": True,
        "word_count": 7,
        "passed": True,
        "error_type": "correct",
    }


def test_score_write_attempt_rejects_the_bare_word():
    """La palabra suelta (o con relleno insuficiente) no es producción propia."""
    got = lexicon.score_write_attempt("travel", "travel")
    assert got["used_word"] is True
    assert got["word_count"] == 1
    assert got["passed"] is False
    assert got["error_type"] == "too_short"


def test_score_write_attempt_classifies_missing_target_and_empty():
    missing = lexicon.score_write_attempt(
        "travel", "I usually go by train in summer."
    )
    assert missing["used_word"] is False
    assert missing["passed"] is False
    assert missing["error_type"] == "missing_target"
    empty = lexicon.score_write_attempt("travel", "   ")
    assert empty["word_count"] == 0
    assert empty["error_type"] == "empty"
    for error_type in (missing["error_type"], empty["error_type"]):
        assert error_type in WRITE_ERROR_TYPES


def test_score_write_attempt_keeps_multiword_units_atomic():
    """Una unidad de varias palabras exige la secuencia contigua (V20-01)."""
    ok = lexicon.score_write_attempt(
        "living room", "My living room is really bright today."
    )
    assert ok["used_word"] is True and ok["passed"] is True
    broken = lexicon.score_write_attempt(
        "living room", "My living is a very big room today."
    )
    assert broken["used_word"] is False
    assert broken["error_type"] == "missing_target"


# ------------------------------------------------------------- endpoints


def test_write_attempt_passed_accredits_written_production(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        body = _post_write(
            client, uid, "travel", "I usually travel by train in summer."
        )

    assert body["passed"] is True
    assert body["used_word"] is True
    assert body["word_count"] == 7
    assert body["error_type"] == "correct"
    assert body["text"] == "I usually travel by train in summer."

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    row = vocab["travel"]
    assert row["writing_prod"] == 1
    assert row["production_count"] == 1
    # Invariante de trazabilidad por fila (suma de canales == producción).
    assert (
        row["chat_prod"]
        + row["speaking_prod"]
        + row["writing_prod"]
        + row["conversation_prod"]
    ) == row["production_count"]

    events = learning_repo.list_events(uid, "exercise")
    assert any(e["detail"] == "drill:travel:write:ok" for e in events)

    # Una sola fila de evidencia por intento, con la modalidad escrita.
    rows = evidence_repo.list_evidence(uid, "travel")
    assert len(rows) == 1
    event = rows[0]
    assert event["skill"] == "written_production"
    assert event["activity_id"] == "drill:write"
    assert event["context_id"] == "lexicon:writing"
    assert event["support_level"] == "independent"
    assert event["success"] == 1
    assert event["response_time_ms"] == 4200
    assert event["error_type"] == "correct"


def test_write_attempt_failure_is_recorded_and_never_accredits(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        body = _post_write(client, uid, "travel", "travel")

    assert body["passed"] is False
    assert body["error_type"] == "too_short"
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["travel"]["writing_prod"] == 0
    assert vocab["travel"]["production_count"] == 0

    events = learning_repo.list_events(uid, "exercise")
    assert any(e["detail"] == "drill:travel:write:ko" for e in events)

    rows = evidence_repo.list_evidence(uid, "travel")
    assert len(rows) == 1
    assert rows[0]["skill"] == "written_production"
    assert rows[0]["success"] == 0
    assert rows[0]["error_type"] == "too_short"


def test_write_attempt_closes_the_optimal_task_gap(monkeypatch, tmp_path):
    """Antes de escribir, el planner pide `write`; después, el hueco se cierra."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    # Recall + producción oral ya cubiertos: solo falta la escrita.
    vocabulary_repo.record_recalls(uid, ["travel"])
    vocabulary_repo.record_production(uid, ["travel"], channel="speaking")
    for skill in ("recall", "spoken_production"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill=skill,
            success=True,
            support_level="independent",
        )

    summary = evidence_repo.summarize_by_target(uid).get("travel", {})
    matrix = lexicon.item_competence_matrix(
        {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}["travel"]
    )
    before = lexicon.recommend_review_activity(
        {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}["travel"],
        matrix,
        evidence=summary,
    )
    assert before["activity"] == "write"
    assert before["reason"] == "skill_gap"

    with TestClient(app) as client:
        body = _post_write(
            client, uid, "travel", "I usually travel by train in summer."
        )
    assert body["passed"] is True

    summary = evidence_repo.summarize_by_target(uid).get("travel", {})
    row = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}["travel"]
    after = lexicon.recommend_review_activity(
        row, lexicon.item_competence_matrix(row), evidence=summary
    )
    assert after["activity"] != "write"
    assert after["reason"] != "skill_gap"
    # Y el ledger ya segmenta el éxito por modalidad escrita.
    assert summary["skill_successes"]["written_production"] == 1


def test_write_attempt_rejects_empty_payload(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        missing = client.post(
            "/api/vocabulary/drill/write-attempt",
            params={"user_id": uid},
            json={"word": "", "text": "I travel a lot."},
        )
        assert missing.status_code == 422
