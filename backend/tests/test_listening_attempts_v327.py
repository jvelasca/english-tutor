"""V3.27 (Listening Engine 4.0, Fase 1): migración y persistencia de la
evidencia ampliada por intento (columnas `layer`, `speed_used`, `stage`,
`transcript_used`, `segments_replayed` en `listening_attempts`), exposición del
micro-flujo en la pregunta servida y persistencia de metadatos vía endpoints."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import QUESTION_BANK, skill_layer


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


NEW_COLUMNS = (
    "layer",
    "speed_used",
    "stage",
    "transcript_used",
    "segments_replayed",
)


def _columns() -> set[str]:
    return {
        row[1]
        for row in db._conn().execute("PRAGMA table_info(listening_attempts)")
    }


def test_migration_adds_five_columns(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cols = _columns()
    for column in NEW_COLUMNS:
        assert column in cols


def test_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    # Segunda inicialización (simula re-arranque) no debe fallar ni duplicar.
    db.init_db()
    cols = _columns()
    for column in NEW_COLUMNS:
        assert column in cols


def test_record_attempt_persists_new_fields(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    ok = listening_repo.record_attempt(
        uid,
        "c001",
        1,
        True,
        skill="gist",
        layer="comprehension",
        speed_used="fast",
        stage="while2",
        transcript_used="hidden",
        segments_replayed=2,
    )
    assert ok is True
    rows = listening_repo.list_attempts(uid)
    assert len(rows) == 1
    row = rows[0]
    assert row["layer"] == "comprehension"
    assert row["speed_used"] == "fast"
    assert row["stage"] == "while2"
    assert row["transcript_used"] == "hidden"
    assert row["segments_replayed"] == 2


def test_record_attempt_backwards_compatible_defaults(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Sin los kwargs nuevos (llamador legacy): la fila conserva los defaults.
    ok = listening_repo.record_attempt(uid, "c001", 0, False, skill="gist")
    assert ok is True
    row = listening_repo.list_attempts(uid)[0]
    assert row["layer"] == ""
    assert row["speed_used"] == "normal"
    assert row["stage"] == ""
    assert row["transcript_used"] == ""
    assert row["segments_replayed"] == 0


def test_record_attempt_unknown_user_returns_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        listening_repo.record_attempt(
            "no-existe", "c001", 0, True, layer="recognition"
        )
        is False
    )


def test_existing_diagnostic_reads_rows_with_extra_columns(monkeypatch, tmp_path):
    """`list_attempts` devuelve las columnas nuevas sin romper a los consumidores
    actuales del diagnóstico (usan `row.get(...)`)."""
    uid = _setup(monkeypatch, tmp_path)
    listening_repo.record_attempt(uid, "c001", 0, True, skill="gist")
    listening_repo.record_attempt(uid, "c002", 1, False, skill="detail")
    rows = listening_repo.list_attempts(uid)
    assert len(rows) == 2
    # Consumidor real: services.listening.listening_diagnostic agrega sin fallar
    # y sigue leyendo bien los campos que ya existían.
    from services.listening import listening_diagnostic

    diagnostic = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diagnostic["subskills"]}
    assert by_skill["gist"]["attempts"] == 1
    assert by_skill["gist"]["accuracy"] == 100.0
    assert by_skill["detail"]["attempts"] == 1
    assert by_skill["detail"]["accuracy"] == 0.0


# --- Endpoints: persistencia de metadatos y exposición del micro-flujo ---------


def _receptive_question() -> dict:
    for q in QUESTION_BANK:
        if q["skill"] not in ("dictation", "shadowing"):
            return q
    raise AssertionError("banco sin ítems receptivos")


def _production_question(kind: str) -> dict:
    for q in QUESTION_BANK:
        if q["skill"] == kind:
            return q
    raise AssertionError(f"banco sin ítems {kind}")


def test_answer_endpoint_persists_layer_and_support(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "answer_index": q["answer_index"],
                "response_time_ms": 900,
                "replay_count": 1,
                "speed_used": "fast",
                "stage": "while2",
                "transcript_used": "hidden",
                "segments_replayed": 1,
            },
        )
    assert r.status_code == 200
    row = listening_repo.list_attempts(uid)[0]
    assert row["layer"] == (skill_layer(q["skill"]) or "")
    assert row["speed_used"] == "fast"
    assert row["stage"] == "while2"
    assert row["transcript_used"] == "hidden"
    assert row["segments_replayed"] == 1


def test_dictation_endpoint_persists_stage_and_transcript(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _production_question("dictation")
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "transcript": q["script"],
                "stage": "post",
                "transcript_used": "full",
                "speed_used": "slow",
            },
        )
    assert r.status_code == 200
    row = listening_repo.list_attempts(uid)[0]
    assert row["task_type"] == "dictation"
    assert row["layer"] == ""
    assert row["stage"] == "post"
    assert row["transcript_used"] == "full"
    assert row["speed_used"] == "slow"


def test_question_endpoint_exposes_flow_and_transcript_policy(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/question", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    # El micro-flujo se expone en el modo adaptativo.
    assert isinstance(body["flow"], list) and body["flow"]
    assert isinstance(body["transcript_policy"], dict)
    assert body["transcript_policy"]["revelation"] in (
        "on_first_fail",
        "on_second_fail",
        "on_finish",
        "never_before_post",
    )
    from services.listening_flow import FLOW_STAGES

    for step in body["flow"]:
        assert step["stage"] in FLOW_STAGES


def test_diagnostic_endpoint_exposes_profile(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Sin datos: el perfil debe venir con needs_min_attempts y sin intervención.
    with TestClient(app) as client:
        r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    profile = r.json()["profile"]
    assert set(profile) == {
        "layer",
        "intervention",
        "reason",
        "needs_min_attempts",
    }
    assert profile["intervention"] is None
    assert profile["needs_min_attempts"] is True
