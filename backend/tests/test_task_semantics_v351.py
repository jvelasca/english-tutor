"""V3.51 — Task/Skill semantics + Learner-level difficulty matching.

V3.50 hizo que la modalidad limitante del ítem orientara la elección del
contexto de transferencia, pero dejaba tres ambigüedades que esta suite blinda:

- **P1-01 — qué se EVALÚA.** El drill Transfer se entrega por TEXTO: su eje es
  `spontaneous_use`, pero la modalidad que puede medir es `written_production`.
  `services.task_semantics` separa target/assessed/mode/evidence y el ledger
  persiste `assessed_skill` sin tocar la escalera.
- **P1-02 — de quién es la dificultad.** El CEFR del ítem es el TECHO
  lingüístico y el nivel DEMOSTRADO del alumno el SUELO de reto.
- **P1-03 — el argmax pierde información.** `planner.skill_priorities` conserva
  el vector completo y `limiting_skill` pasa a ser su argmax.

Las guardias de regresión viven en las suites de V3.36/V3.38/V3.43/V3.46/V3.47/
V3.49/V3.50; aquí se cubre lo NUEVO.
"""

from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import evidence as evidence_svc
from services import planner, task_semantics, transfer


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "B1") -> None:
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


def _seed_evidence(a: str, word: str, *, skill: str, assessed: str, success: bool):
    evidence_repo.record_evidence(
        a,
        target_type="lexicon",
        target_id=word,
        surface_form=word,
        lexical_unit=word,
        skill=skill,
        assessed_skill=assessed,
        task="test",
        activity="drill",
        activity_id="drill:test",
        context_id="",
        success=success,
        support_level="independent",
        error_type="correct" if success else "missing_target",
    )


# ------------------------------------------------------------- vocabulario


def test_task_semantics_uses_only_canonical_skills():
    for activity, declared in task_semantics.TASK_SEMANTICS.items():
        for key in ("target_skill", "assessed_skill", "evidence_skill"):
            assert declared[key] in evidence_svc.LEXICAL_SKILLS, (activity, key)
        assert declared["assessment_mode"] in task_semantics.ASSESSMENT_MODES
    # El orden canónico local no puede divergir del contrato del ledger.
    assert task_semantics.SKILL_ORDER == evidence_svc.LEXICAL_SKILLS


def test_transfer_measures_written_production_not_spoken():
    assert task_semantics.target_skill_for("transfer") == "spontaneous_use"
    assert task_semantics.assessed_skill_for("transfer") == "written_production"
    assert task_semantics.assessment_mode_for("transfer") == "written"
    # El contrato HISTÓRICO del ledger (gate de transferencia) no cambia.
    assert task_semantics.evidence_skill_for("transfer") == "spontaneous_use"


def test_transfer_cannot_assess_spoken_production():
    assessable = task_semantics.assessable_skills("transfer")
    assert "spoken_production" not in assessable
    assert set(assessable) == {"written_production", "spontaneous_use"}
    # El peldaño oral sigue siendo una actividad que SÍ la evalúa.
    assert task_semantics.assessed_skill_for("sentence") == "spoken_production"
    assert task_semantics.assessment_mode_for("sentence") == "spoken"


def test_evidence_skill_reproduces_the_persisted_contract():
    # Paridad con los `skill=` que los caminos del drill escriben hoy.
    assert task_semantics.evidence_skill_for("recall") == evidence_svc.RECALL_SKILL
    assert task_semantics.evidence_skill_for("word") == evidence_svc.DRILL_SKILL
    assert task_semantics.evidence_skill_for("sentence") == evidence_svc.DRILL_SKILL
    assert task_semantics.evidence_skill_for("write") == "written_production"
    assert task_semantics.evidence_skill_for("transfer") == "spontaneous_use"


def test_unknown_activity_is_empty_and_never_raises():
    for activity in (None, "", "no-existe", 42):
        assert task_semantics.semantics_for(activity)["assessed_skill"] == ""
        assert task_semantics.assessable_skills(activity) == ()
        assert task_semantics.activity_for_target(activity) == ""
    # La copia devuelta no permite mutar la tabla declarativa.
    copy = task_semantics.semantics_for("transfer")
    copy["assessed_skill"] = "nope"
    assert task_semantics.assessed_skill_for("transfer") == "written_production"
    # Actividad desconocida: `is_assessable` responde False, no lanza.
    assert task_semantics.is_assessable("transfer", "spoken_production") is False
    assert task_semantics.is_assessable("transfer", "written_production") is True


def test_activity_from_activity_id_normalizes_the_drill_prefix():
    assert task_semantics.activity_from_activity_id("drill:word") == "word"
    assert task_semantics.activity_from_activity_id("drill:recall:cued") == "recall"
    assert task_semantics.activity_from_activity_id("drill:transfer") == "transfer"
    assert task_semantics.activity_from_activity_id("") == ""
    # Un canal de producción no es una actividad del drill: no se inventa.
    assert task_semantics.assessed_skill_for(
        task_semantics.activity_from_activity_id("lexicon:writing")
    ) == ""


# ---------------------------------------------------------------- ledger


def test_migration_adds_assessed_skill_column(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    info = db._conn().execute("PRAGMA table_info(learning_evidence)")
    cols = {row[1] for row in info}
    assert "assessed_skill" in cols


def test_migration_alters_a_legacy_ledger(monkeypatch, tmp_path):
    # Simula un ledger V3.50 (tabla sin `assessed_skill`) y comprueba que el
    # bucle idempotente `ALTER TABLE ... ADD COLUMN` la añade con default ''.
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "CREATE TABLE learning_evidence ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, "
            "occurred_at TEXT NOT NULL, skill TEXT NOT NULL DEFAULT '', "
            "target_type TEXT NOT NULL DEFAULT '', "
            "target_id TEXT NOT NULL DEFAULT '')"
        )
    db.init_db()
    info = db._conn().execute("PRAGMA table_info(learning_evidence)")
    cols = {row[1] for row in info}
    assert "assessed_skill" in cols


def test_record_evidence_persists_assessed_skill(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(
        uid, "travel", skill="spontaneous_use", assessed="written_production",
        success=True,
    )
    rows = evidence_repo.list_evidence(uid, "travel")
    assert rows[0]["assessed_skill"] == "written_production"
    assert rows[0]["skill"] == "spontaneous_use"


def test_assessed_skill_maps_have_pure_sql_parity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Una modalidad con SOLO fallos (la clave debe faltar en successes) y una con
    # éxito (debe aparecer en ambos histogramas), en el mismo ítem.
    _seed_evidence(
        uid, "river", skill="spontaneous_use", assessed="written_production",
        success=False,
    )
    _seed_evidence(
        uid, "river", skill="spontaneous_use", assessed="written_production",
        success=True,
    )
    _seed_evidence(
        uid, "river", skill="recall", assessed="recall", success=True,
    )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")["river"]
    rows = evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    pure = evidence_svc.summarize_evidence(rows)
    assert aggregated == pure
    assert aggregated["assessed_skill_attempts"] == {
        "written_production": 2,
        "recall": 1,
    }
    assert aggregated["assessed_skill_successes"] == {
        "written_production": 1,
        "recall": 1,
    }
    # Las filas legacy sin la columna no entran (no se inventa semántica).
    assert evidence_svc.empty_summary()["assessed_skill_attempts"] == {}


# --------------------------------------------------------------- planner


def test_skill_priorities_is_the_full_vector_and_limiting_is_its_argmax():
    signals = {
        "skills": {
            "recall": {"weakness": 0.1, "support": 0.0, "latency": 0.0},
            "written_production": {"weakness": 0.62, "support": 0.0, "latency": 0.0},
            "spoken_production": {"weakness": 0.60, "support": 0.0, "latency": 0.0},
            "spontaneous_use": {"weakness": 0.31, "support": 0.0, "latency": 0.0},
        }
    }
    priorities = planner.skill_priorities(signals)
    # El vector conserva TODAS las modalidades (P1-03): nada se descarta.
    assert list(priorities) == list(evidence_svc.LEXICAL_SKILLS)
    assert priorities["written_production"] > priorities["spoken_production"]
    assert priorities["spoken_production"] > priorities["spontaneous_use"]
    assert planner.limiting_skill(signals) == "written_production"


def test_skills_priorities_is_empty_without_segmentation():
    assert planner.skill_priorities({}) == {}
    assert planner.skill_priorities({"skills": {}}) == {}
    assert planner.limiting_skill({}) == ""


def test_transfer_target_skill_never_orients_to_spoken(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    summary = {
        "skill_attempts": {
            "recall": 1,
            "written_production": 1,
            "spoken_production": 5,  # la más débil de todas
            "spontaneous_use": 1,
        },
        "skill_successes": {"recall": 1},
    }
    target = vocabulary_domain._transfer_target_skill({"cefr": "B1"}, summary)
    assert target != "spoken_production"
    assert target in task_semantics.assessable_skills("transfer")


# --------------------------------------------------- learner difficulty


def test_without_learner_level_the_choice_is_unchanged():
    base = transfer.context_for("travel", level="B1")
    assert transfer.context_for("travel", level="B1", learner_level="") == base
    assert transfer.context_for("travel", level="B1", learner_level=None) == base


def test_unknown_learner_level_degrades_gracefully():
    base = transfer.context_for("travel", level="B1")
    assert transfer.context_for("travel", level="B1", learner_level="Pre-A1") == base
    assert transfer.context_for("travel", level="B1", learner_level="no-existe") == base


def test_learner_level_raises_the_difficulty_floor():
    # Ítem B1 (techo bajo) con alumno C1 (suelo alto): el RETO objetivo sube por
    # dimensión, de modo que el contexto servido no puede quedarse tan plano como
    # en el caso de solo-ítem de V3.50. La comparación es VECTOR a VECTOR (V3.52),
    # no escalar: es el P1-02 de la auditoría de V3.51.
    item_only = transfer.context_for("travel", level="B1")
    with_learner = transfer.context_for("travel", level="B1", learner_level="C1")
    item_challenge = item_only["difficulty_fit"]["challenge"]
    learner_challenge = with_learner["difficulty_fit"]["challenge"]
    assert set(learner_challenge) == set(transfer.TRANSFER_DIFFICULTY_KEYS)
    assert all(
        learner_challenge[dimension] >= item_challenge[dimension]
        for dimension in transfer.TRANSFER_DIFFICULTY_KEYS
    )
    assert learner_challenge != item_challenge
    # El contexto servido no es más plano y el TECHO del ítem se respeta.
    assert with_learner["difficulty"] >= item_only["difficulty"]
    assert with_learner["item_level"] == "B1"
    assert with_learner["learner_level"] == "C1"
    assert transfer.cefr_index(with_learner["cefr"]) <= transfer.cefr_index("B1")


def test_context_exposes_the_semantic_dimensions():
    got = transfer.context_for(
        "travel",
        level="B2",
        learner_level="C1",
        skill="written_production",
        skill_priorities={"written_production": 0.62, "spoken_production": 0.60},
    )
    assert got["target_skill"] == "written_production"
    assert got["assessed_skill"] == "written_production"
    assert got["assessment_mode"] == "written"
    assert got["item_level"] == "B2"
    assert got["learner_level"] == "C1"
    assert got["skill_priorities"] == {
        "written_production": 0.62,
        "spoken_production": 0.60,
    }
    # El contexto declara su INTENCIÓN en `skills` (puede incluir orales).
    assert set(got["skills"]) <= set(transfer.CONTEXT_SKILLS)


# ------------------------------------------------------------ contrato HTTP


def test_api_exposes_the_semantic_dimensions(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["target_skill"] == "spontaneous_use"
    assert body["assessed_skill"] == "written_production"
    assert body["assessment_mode"] == "written"
    assert body["item_level"] == "B1"
    assert body["skill_priorities"] == {}


def test_transfer_attempt_records_assessed_skill_and_parity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    # El alumno demuestra nivel C1 y falla la producción escrita: la modalidad
    # limitante evaluable es escrita, y el nivel demostrado eleva el suelo.
    profile_repo.set_cefr(uid, "C1")
    _seed_evidence(
        uid, "travel", skill="written_production", assessed="written_production",
        success=False,
    )
    _seed_evidence(uid, "travel", skill="recall", assessed="recall", success=True)

    with TestClient(app) as client:
        served = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        ).json()
        attempts = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I travel to work by train every single day.",
            },
        ).json()

    # Paridad GET↔POST con nivel de alumno: mismo contexto derivado.
    assert attempts["context_id"] == served["context_id"]
    assert attempts["assessed_skill"] == "written_production"
    assert attempts["assessment_mode"] == "written"
    assert attempts["target_skill"] == "spontaneous_use"
    # El ledger declara AMBAS dimensiones: el eje histórico y lo evaluado.
    rows = evidence_repo.list_evidence(uid, "travel")
    assert rows[0]["skill"] == "spontaneous_use"
    assert rows[0]["assessed_skill"] == "written_production"
    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    assert summary["skill_attempts"]["spontaneous_use"] == 1
    # La fila sembrada (fallo de escritura) + el intento de transferencia.
    assert summary["assessed_skill_attempts"]["written_production"] == 2
    assert summary["assessed_skill_successes"]["written_production"] == 1


def test_review_queue_exposes_the_priority_vector(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    _seed_evidence(
        uid, "travel", skill="written_production", assessed="written_production",
        success=False,
    )
    with TestClient(app) as client:
        res = client.get("/api/learning/review", params={"user_id": uid})
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    if not items:
        return  # sin carta vencida no hay ítem que exponer
    item = items[0]
    assert "skill_priorities" in item
    if item["skill_priorities"]:
        assert item["limiting_skill"] == max(
            item["skill_priorities"], key=lambda skill: item["skill_priorities"][skill]
        )
