"""Tests de invariantes de evidencia (coherencia user_id/objective_id/skill/version).

Garantizan que ningún registro de evidencia que llegue al Student Model esté
incoherente: el `objective_id` debe pertenecer al nivel (o ser vacío para
evidencia de nivel, p. ej. examen), la `skill` canónica, `item_type`/`source`
conocidos, las versiones no vacías y el `result` en [0,1].
"""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services import pronunciation as pronunciation_svc
from services import speaking as speaking_svc
from services import writing as writing_svc
from services.curriculum import ASSESSMENT_VERSION, RUBRIC_VERSION, load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _assessable_objective():
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    return lv, obj


def _valid_record():
    lv, obj = _assessable_objective()
    check = obj.checks[0]
    return (
        lv,
        academy_svc.evidence_from_items(
            obj.checks,
            {check.id: check.correct_index},
            level_id="a1",
            objective_id=obj.id,
            source="objective_assessment",
            curriculum_version=lv.version,
            assessment_version=ASSESSMENT_VERSION,
        )[0],
    )


# --- Registros válidos ----------------------------------------------------


def test_valid_objective_record_passes():
    lv, record = _valid_record()
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv) == []


def test_valid_level_record_with_empty_objective_passes():
    lv, record = _valid_record()
    record["objective_id"] = ""  # evidencia de nivel (p. ej. examen)
    record["source"] = "exam"
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv) == []


# --- Violaciones individuales ---------------------------------------------


def test_invalid_user_id():
    lv, record = _valid_record()
    assert academy_svc.evidence_record_errors(record, user_id="", level=lv)


def test_invalid_objective_id():
    lv, record = _valid_record()
    record["objective_id"] = "no-existe"
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_invalid_skill():
    lv, record = _valid_record()
    record["skill"] = "dancing"
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_invalid_item_type():
    lv, record = _valid_record()
    record["item_type"] = "essay"
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_invalid_source():
    lv, record = _valid_record()
    record["source"] = "magic"
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_empty_curriculum_version():
    lv, record = _valid_record()
    record["curriculum_version"] = ""
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_empty_assessment_version():
    lv, record = _valid_record()
    record["assessment_version"] = ""
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_result_out_of_range():
    lv, record = _valid_record()
    record["result"] = 1.5
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


def test_result_non_numeric():
    lv, record = _valid_record()
    record["result"] = "high"
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv)


# --- Los builders de producción generan evidencia válida -------------------


def test_production_evidence_builders_are_valid():
    lv = load_level("a1")
    oid = lv.objectives()[0].id

    speaking_result = speaking_svc.score_speaking("I am happy", "I am happy", 2.0)
    writing_result = writing_svc.score_writing("I am happy", "I am happy")
    pron_result = pronunciation_svc.score_pronunciation_cefr("hello", "hello")

    builders = [
        speaking_svc.evidence_from_speaking(
            speaking_result,
            level_id="a1",
            objective_id=oid,
            curriculum_version=lv.version,
        ),
        writing_svc.evidence_from_writing(
            writing_result,
            level_id="a1",
            objective_id=oid,
            curriculum_version=lv.version,
        ),
        pronunciation_svc.evidence_from_pronunciation(
            pron_result,
            level_id="a1",
            objective_id=oid,
            curriculum_version=lv.version,
        ),
    ]
    for records in builders:
        assert records, "el builder no generó registros"
        for record in records:
            assert (
                academy_svc.evidence_record_errors(
                    record, user_id="u1", level=lv
                )
                == []
            )
            assert record["assessment_version"] == RUBRIC_VERSION


# --- End-to-end: el endpoint solo persiste evidencia válida ----------------


def test_objective_assessment_records_only_valid_evidence(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    lv, obj = _assessable_objective()
    checks = {c.id: c.correct_index for c in obj.checks}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id, "answers": checks},
        )
    assert r.status_code == 200
    rows = academy_repo.list_evidence(a)
    assert rows, "no se registró evidencia"
    for row in rows:
        assert academy_svc.evidence_record_errors(row, user_id=a, level=lv) == []
