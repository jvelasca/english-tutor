"""V3.29 (Fase 3): evidencia de palabra fallada en `listening_attempts`.

Cubre la migración idempotente de la columna `word_breakdown_json`, la
persistencia vía `record_attempt` (repo) y los dos caminos de dominio:
- `submit_production` (dictado/shadowing) persiste el breakdown de
  `word_alignment` del intento;
- `submit_answer` persiste `{"target": ...}` solo cuando un cloze/segmentation
  derivado se falla; MCQ correcto y dictado sin fallo guardan `NULL`/None.
"""
import json

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import DERIVED_BY_ID, QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _columns() -> set[str]:
    return {
        row[1]
        for row in db._conn().execute("PRAGMA table_info(listening_attempts)")
    }


def _production_question(kind: str) -> dict:
    for q in QUESTION_BANK:
        if q["skill"] == kind:
            return q
    raise AssertionError(f"banco sin ítems {kind}")


def _cloze_question() -> dict:
    for q in DERIVED_BY_ID.values():
        if q.get("task_type") == "cloze":
            return q
    raise AssertionError("catálogo sin cloze derivado")


def _receptive_question() -> dict:
    for q in QUESTION_BANK:
        if q["skill"] not in ("dictation", "shadowing"):
            return q
    raise AssertionError("banco sin ítems receptivos")


# --- Migración idempotente ---------------------------------------------------

def test_migration_adds_word_breakdown_json(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "word_breakdown_json" in _columns()
    # Segunda inicialización (re-arranque): no falla ni duplica columnas.
    db.init_db()
    assert "word_breakdown_json" in _columns()


# --- Repositorio -------------------------------------------------------------

def test_record_attempt_persists_word_breakdown_serialized(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    breakdown = {"missing": ["hello"], "substituted": [], "correct": ["there"]}
    ok = listening_repo.record_attempt(
        uid, "c001", -1, False, skill="dictation", difficulty=3,
        task_type="dictation", score=0.5, word_breakdown=breakdown,
    )
    assert ok is True
    row = listening_repo.list_attempts(uid)[0]
    assert row["word_breakdown_json"] == json.dumps(breakdown)


def test_record_attempt_without_breakdown_stores_null(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.record_attempt(uid, "c001", 0, True, skill="gist")
    row = listening_repo.list_attempts(uid)[0]
    assert row["word_breakdown_json"] is None


# --- Caminos de dominio (endpoints) ------------------------------------------

def test_dictation_fallido_persiste_breakdown(monkeypatch, tmp_path):
    """Un dictado incorrecto persiste su breakdown de `word_alignment`."""
    uid = _setup(monkeypatch, tmp_path)
    q = _production_question("dictation")
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={"question_id": q["id"], "transcript": ""},  # oye mal: vacío
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is False
    assert body["task_type"] == "dictation"
    row = listening_repo.list_attempts(uid)[0]
    breakdown = json.loads(row["word_breakdown_json"])
    assert isinstance(breakdown, dict)
    # Con transcripción vacía, todo el texto de referencia queda en `missing`.
    assert breakdown["missing"]
    assert breakdown["total"] > 0


def test_mcq_correcto_persiste_null(monkeypatch, tmp_path):
    """Un MCQ acertado (respuesta receptiva) no genera evidencia de palabra
    fallada: `word_breakdown_json` queda NULL."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is True
    row = listening_repo.list_attempts(uid)[0]
    assert row["word_breakdown_json"] is None


def test_cloze_fallado_persiste_target(monkeypatch, tmp_path):
    """Un cloze derivado fallado persiste la palabra diana del hueco como
    evidencia de palabra fallada."""
    uid = _setup(monkeypatch, tmp_path)
    q = _cloze_question()
    target = q["options"][q["answer_index"]]
    wrong_index = next(
        i for i in range(len(q["options"])) if i != q["answer_index"]
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": wrong_index},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is False
    row = listening_repo.list_attempts(uid)[0]
    assert json.loads(row["word_breakdown_json"]) == {"target": target}


def test_cloze_acertado_persiste_null(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _cloze_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is True
    row = listening_repo.list_attempts(uid)[0]
    assert row["word_breakdown_json"] is None
