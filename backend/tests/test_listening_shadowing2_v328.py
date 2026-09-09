"""V3.28 (Listening Engine 4.0, Fase 2, Bloque E): Shadowing 2.0.

Las señales auxiliares del shadowing (`shadowing_duration_ms`,
`shadowing_speech_rate`) son informativas: el cliente las calcula desde el audio
grabado y se persisten con el patrón aditivo de migración (columnas nullables)
en el intento de shadowing. NO tienen peso de mastery: el scoring determinista
sigue siendo la comparación del texto oído y la puerta/gate no se altera por
incluirlas (la prueba honesta: dos usuarios idénticos salvo las señales producen
el mismo diagnóstico y la misma puerta)."""

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import get_question


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _shadowing_question() -> dict:
    q = get_question("l19")
    assert q and q["skill"] == "shadowing"
    return q


def _shadowing_mean(diag: dict) -> dict:
    """mean_score de la sub-destreza shadowing en un diagnóstico."""
    return {
        s["skill"]: s["mean_score"]
        for s in diag["subskills"]
        if s["skill"] == "shadowing"
    }


# --- Persistencia aditiva de las señales -------------------------------------

def test_shadowing_aux_signals_persist_on_attempt(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _shadowing_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/shadowing",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "transcript": q["transcript"],
                "shadowing_duration_ms": 2340,
                "shadowing_speech_rate": 152.0,
            },
        )
    assert r.status_code == 200
    assert r.json()["correct"] is True
    row = listening_repo.list_attempts(uid)[0]
    assert row["task_type"] == "shadowing"
    # Señales informativas persistidas (migración aditiva nullable).
    assert row["shadowing_duration_ms"] == 2340
    assert row["shadowing_speech_rate"] == 152.0
    # El scoring determinista no cambia: score continuo 1.0 por texto exacto.
    assert row["score"] == 1.0


def test_aux_signals_are_optional_and_default_to_null(monkeypatch, tmp_path):
    """Sin señales en el request el intento guarda NULL (retrocompatible)."""
    uid = _setup(monkeypatch, tmp_path)
    q = _shadowing_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/shadowing",
            params={"user_id": uid},
            json={"question_id": q["id"], "transcript": q["transcript"]},
        )
    assert r.status_code == 200
    row = listening_repo.list_attempts(uid)[0]
    assert row["shadowing_duration_ms"] is None
    assert row["shadowing_speech_rate"] is None


def test_aux_signals_only_persist_for_shadowing(monkeypatch, tmp_path):
    """Un dictado que envía señales no las persiste: solo el intento shadowing
    las declara (la puerta de las señales vive en submit_production)."""
    uid = _setup(monkeypatch, tmp_path)
    q = get_question("l18")
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/dictation",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "transcript": q["transcript"],
                "shadowing_duration_ms": 999,
                "shadowing_speech_rate": 42.0,
            },
        )
    assert r.status_code == 200
    row = listening_repo.list_attempts(uid)[0]
    assert row["task_type"] == "dictation"
    assert row["shadowing_duration_ms"] is None
    assert row["shadowing_speech_rate"] is None


def test_migration_is_idempotent(monkeypatch, tmp_path):
    """El patrón aditivo de migración tolera reinicializar la base (V3.27)."""
    uid = _setup(monkeypatch, tmp_path)
    db.init_db()  # segunda pasada: columnas ya existen, sin error
    q = _shadowing_question()
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/shadowing",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "transcript": q["transcript"],
                "shadowing_duration_ms": 1200,
                "shadowing_speech_rate": 90.5,
            },
        )
    assert r.status_code == 200
    row = listening_repo.list_attempts(uid)[0]
    assert row["shadowing_duration_ms"] == 1200


# --- Las señales NO alteran mastery/gate -------------------------------------

def test_aux_signals_do_not_change_stats_or_gate(monkeypatch, tmp_path):
    """Dos usuarios idénticos salvo las señales auxiliares producen el mismo
    diagnóstico y la misma puerta de ruta: las señales son informativas."""
    uid_a = _setup(monkeypatch, tmp_path)
    uid_b = users_repo.create_user("B")["id"]
    q = _shadowing_question()
    with TestClient(app) as client:
        for uid, aux in (
            (uid_a, {"shadowing_duration_ms": 2340, "shadowing_speech_rate": 152.0}),
            (uid_b, {}),
        ):
            r = client.post(
                "/api/listening/shadowing",
                params={"user_id": uid},
                json={"question_id": q["id"], "transcript": q["transcript"], **aux},
            )
            assert r.status_code == 200

        sa = client.get("/api/listening/stats", params={"user_id": uid_a}).json()
        sb = client.get("/api/listening/stats", params={"user_id": uid_b}).json()
        da = client.get(
            "/api/listening/diagnostic", params={"user_id": uid_a}
        ).json()
        dbd = client.get(
            "/api/listening/diagnostic", params={"user_id": uid_b}
        ).json()
    # Mismo número de intentos/aciertos y niveles de ruta idénticos (incluye gate
    # y estado pedagógico): la señal extra no mueve mastery.
    assert sa["attempts"] == sb["attempts"] == 1
    assert sa["correct"] == sb["correct"] == 1
    assert sa["levels"] == sb["levels"]
    assert all(not level["completed"] for level in sa["levels"])
    # Mismo diagnóstico de producción.
    assert _shadowing_mean(da) == _shadowing_mean(dbd)
