"""V3.39 (Fase 3) — motor de tarea óptima por skill.

`services.planner` deja de responder solo "¿qué palabra repaso?" (prioridad) y
pasa a decidir también "¿qué skill limita, qué actividad la cierra y con cuánto
apoyo?" (`select_task`), separando SELECCIÓN DE ACTIVIDAD de PUNTUACIÓN DE
PRIORIDAD (P1-02 de la auditoría de V3.38.1). La novedad funcional es que el
hueco de escritura (`spoken ✓ / written ✗`) pasa a ser accionable: la modalidad
`written_production` se cierra con la actividad `write`.

Se cubre: tablas de mapeo skill→actividad, `skill_priority`, `limiting_skill`,
`select_task` (orden declarado de razones, robustez ante basura) y la exposición
aditiva de `limiting_skill`/`task` en la cola HTTP.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, planner


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    """Carta FSRS `lexicon` ya revisada y VENCIDA (due ayer)."""
    now = datetime.now(timezone.utc)
    last = (now - timedelta(days=days_ago)).isoformat()
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": last,
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


def _review_queue(client: TestClient, uid: str) -> dict:
    res = client.get("/api/learning/review", params={"user_id": uid})
    assert res.status_code == 200, res.text
    return res.json()


# --- Tablas declaradas skill → actividad y actividad → apoyo -----------------


def test_activity_tables_cover_every_skill_and_activity():
    """Toda modalidad canónica tiene actividad, y toda actividad apoyo declarado."""
    from services.evidence import LEXICAL_SKILLS

    for skill in LEXICAL_SKILLS:
        assert skill in planner.ACTIVITY_FOR_SKILL, skill
        assert planner.ACTIVITY_FOR_SKILL[skill] in lexicon.REVIEW_ACTIVITIES
    for activity in lexicon.REVIEW_ACTIVITIES:
        assert activity in planner.ACTIVITY_SUPPORT_LEVEL, activity
    # La actividad de escritura (V3.39) es propia de `written_production`.
    assert planner.ACTIVITY_FOR_SKILL["written_production"] == "write"
    assert planner.ACTIVITY_SUPPORT_LEVEL["write"] == "independent"


# --- skill_priority / limiting_skill ----------------------------------------


def _segmented_signals() -> dict:
    """Señales con TRES modalidades medidas: recall acierta con apoyo, la
    escritura acierta sin apoyo y la producción oral falla siempre. La que
    limita es la producción oral."""
    evidence = {
        "attempts": 6,
        "successes": 4,
        "skill_attempts": {
            "recall": 2,
            "written_production": 2,
            "spoken_production": 2,
        },
        "skill_successes": {
            "recall": 2,
            "written_production": 2,
            "spoken_production": 0,
        },
        "skill_independent_successes": {
            "recall": 0,
            "written_production": 2,
        },
        "skill_mean_response_time_ms": {"recall": 9000},
    }
    matrix = {"recall": True, "cued_recall": True, "production_gap": True}
    return planner.planned_signals(evidence, matrix, retrievability=0.5)


def test_skill_priority_applies_declared_weights_per_modality():
    signals = _segmented_signals()
    priorities = planner.skill_priority(signals)
    assert set(priorities) == {
        "recall",
        "written_production",
        "spoken_production",
        "spontaneous_use",
    }
    # La modalidad que falla siempre (spoken) pesa más que la que acierta con
    # apoyo (recall) y que la que acierta sin apoyo (written).
    assert priorities["spoken_production"] > priorities["recall"]
    assert priorities["spoken_production"] > priorities["written_production"]
    assert all(0.0 <= value <= 1.0 for value in priorities.values())


def test_limiting_skill_is_argmax_in_canonical_order():
    signals = _segmented_signals()
    # La modalidad fallida manda sobre la que acierta con apoyo y sobre la que
    # nunca se ha intentado (sin intentos, `weakness` es máxima: es un hueco).
    assert planner.limiting_skill(signals) == "spoken_production"
    # Empate: gana la primera modalidad canónica (`recall`), no el orden del dict.
    tied = {
        "forgetting": 0.5,
        "gap": 0.5,
        "skills": {
            "written_production": {"weakness": 0.0, "support": 0.0, "latency": 0.0},
            "recall": {"weakness": 0.0, "support": 0.0, "latency": 0.0},
        },
    }
    assert planner.limiting_skill(tied) == "recall"
    # Ítem sin señales de modalidad: el peldaño por defecto del repaso.
    assert planner.limiting_skill(planner.planned_signals({}, {})) == "recall"


def test_limiting_skill_is_empty_without_segmentation():
    assert planner.limiting_skill({}) == ""
    assert planner.limiting_skill({"skills": "nope"}) == ""
    assert planner.skill_priority({}) == {}


# --- select_task: orden declarado de razones --------------------------------


def test_select_task_prioritizes_error_prone_over_gap_and_slow_recall():
    evidence = {
        "error_types": {"wrong_word": 2},
        "skill_successes": {"recall": 1},
        "skill_mean_response_time_ms": {"recall": 12000},
    }
    task = planner.select_task({"production": True}, evidence)
    assert task == {
        "skill": "recall",
        "activity": "recall",
        "reason": "error_prone",
        "support_level": "cued",
    }


def test_select_task_routes_the_written_gap_to_write():
    evidence = {"skill_successes": {"recall": 2, "spoken_production": 2}}
    task = planner.select_task({"production": True}, evidence)
    assert task["skill"] == "written_production"
    assert task["activity"] == "write"
    assert task["reason"] == "skill_gap"
    # El hueco ORAL (simétrico) conserva el comportamiento de V3.38.1.
    oral_gap = planner.select_task(
        {"production": True}, {"skill_successes": {"recall": 2}}
    )
    assert oral_gap["skill"] == "spoken_production"
    assert oral_gap["activity"] == "sentence"


def test_select_task_slow_recall_only_when_both_productions_are_covered():
    evidence = {
        "skill_successes": {
            "recall": 1,
            "spoken_production": 1,
            "written_production": 1,
        },
        "skill_mean_response_time_ms": {"recall": 12000},
    }
    task = planner.select_task({"production": True}, evidence)
    assert task["skill"] == "recall"
    assert task["activity"] == "recall"
    assert task["reason"] == "slow_recall"


def test_select_task_without_directive_is_empty_and_never_raises():
    empty = {"skill": "", "activity": "", "reason": "", "support_level": ""}
    assert planner.select_task(None, None) == empty
    assert planner.select_task({}, {}) == empty
    assert planner.select_task({"production": True}, {}) == empty
    # Basura: el planner nunca rompe la cola.
    garbage = {"skill_successes": ["recall"], "error_types": 3,
               "skill_mean_response_time_ms": "slow"}
    assert planner.select_task(None, garbage) == empty
    assert planner.select_task("nope", garbage) == empty
    assert planner.evidence_reason({"production": True}, garbage) == ""


def test_evidence_reason_is_a_facade_of_select_task():
    evidence = {"error_types": {"wrong_word": 3}}
    matrix = {"production": True}
    assert planner.evidence_reason(matrix, evidence) == (
        planner.select_task(matrix, evidence)["reason"]
    )


# --- Cola HTTP: exposición aditiva de la tarea ------------------------------


def test_review_queue_exposes_limiting_skill_and_task(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = _review_queue(client, uid)

    item = body["items"][0]
    assert item["limiting_skill"] in {"", *planner.ACTIVITY_FOR_SKILL}
    task = item["task"]
    assert set(task) == {"skill", "activity", "reason", "support_level"}
    assert task["activity"] == item["activity"]
    assert task["reason"] == item["reason"]
    assert task["support_level"] == planner.ACTIVITY_SUPPORT_LEVEL[task["activity"]]


def test_review_queue_task_closes_the_written_gap(monkeypatch, tmp_path):
    """`spoken ✓ / written ✗` → la cola recomienda la actividad de escritura."""
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    vocabulary_repo.record_recalls(uid, ["river"])
    vocabulary_repo.record_production(uid, ["river"], channel="speaking")
    for skill in ("recall", "spoken_production"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill=skill,
            success=True,
            support_level="independent",
        )
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = _review_queue(client, uid)

    task = body["items"][0]["task"]
    assert body["items"][0]["activity"] == "write"
    assert task["skill"] == "written_production"
    assert task["activity"] == "write"
    assert task["reason"] == "skill_gap"
    assert task["support_level"] == "independent"


def test_review_queue_task_reports_error_prone_from_the_ledger(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    vocabulary_repo.record_recalls(uid, ["river"])
    for _ in range(2):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            success=False,
            error_type="wrong_word",
        )
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = _review_queue(client, uid)

    task = body["items"][0]["task"]
    assert task["reason"] == "error_prone"
    assert task["skill"] == "recall"
    assert task["activity"] == "recall"
