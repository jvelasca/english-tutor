"""V3.28 (Listening Engine 4.0, Fase 2, Bloque A): unificación del micro-flujo.

Resuelve el P1-01 de la auditoría V3.27: las rutas por nivel (`level`) y drill
(`failed`) debían servir el mismo contrato `flow`/`transcript_policy` que la ruta
adaptativa; solo `mastered` (repaso de lo superado) conserva el modo compacto sin
flow. Los tests verifican el contrato del endpoint en cada modo."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import LEVEL_ORDER, QUESTION_BANK, skill_layer
from services.listening_flow import FLOW_STAGES, REVELATION_MODES


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _receptive_at(level: str) -> dict:
    """Primer ítem receptivo (no dictation/shadowing) del banco en `level`."""
    for q in QUESTION_BANK:
        if q["level"] == level and q["skill"] not in ("dictation", "shadowing"):
            return q
    raise AssertionError(f"banco sin ítems receptivos en {level}")


def _assert_flow_contract(body: dict) -> None:
    """El payload trae flow no vacío y una política con revelación válida."""
    assert isinstance(body["flow"], list) and body["flow"]
    for step in body["flow"]:
        assert step["stage"] in FLOW_STAGES
        assert step["task"]
        assert step["transcript_state_inicial"] in ("hidden", "partial", "full")
    assert isinstance(body["transcript_policy"], dict)
    assert body["transcript_policy"]["revelation"] in REVELATION_MODES


def test_level_route_exposes_flow(monkeypatch, tmp_path):
    """GET /question?level=A1 (modo all) sirve flow + política por ítem."""
    uid = _setup(monkeypatch, tmp_path)
    level = LEVEL_ORDER[0]
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": level},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == level
    _assert_flow_contract(body)


def test_level_route_flow_policy_matches_level(monkeypatch, tmp_path):
    """La política servida en una ruta por nivel corresponde a su nivel CEFR."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "B2"},
        )
    assert r.status_code == 200
    body = r.json()
    _assert_flow_contract(body)
    # B2 no permite revelado manual antes de Post (política estricta por nivel).
    assert body["transcript_policy"]["allow_manual_reveal"] is False
    assert body["transcript_policy"]["revelation"] == "never_before_post"


def test_drill_failed_route_exposes_flow(monkeypatch, tmp_path):
    """GET /question?level=A1&mode=failed sirve flow para el drill de falladas."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_at("A1")
    # Registra un fallo para que exista grupo "failed" en el nivel.
    listening_repo.record_attempt(
        uid, q["id"], 0, False, skill=q["skill"], difficulty=3
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "failed"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == q["id"]
    _assert_flow_contract(body)
    # A1 permite revelado manual (política permisiva de la Fase 1).
    assert body["transcript_policy"]["allow_manual_reveal"] is True


def test_mastered_route_is_compact_without_flow(monkeypatch, tmp_path):
    """GET /question?level=A1&mode=mastered conserva el modo compacto (sin flow).

    Decisión V3.28 (auditoría V3.27): el repaso de lo ya superado no repite el
    micro-flujo completo; solo las rutas level/failed/adaptativa lo sirven."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_at("A1")
    listening_repo.record_attempt(
        uid, q["id"], 1, True, skill=q["skill"], difficulty=3
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "mastered"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == q["id"]
    # El modo compacto no declara pasos: schema default = listado vacío.
    assert body["flow"] == []
    assert body["transcript_policy"] == {}


def test_level_route_keeps_layer_metadata(monkeypatch, tmp_path):
    """La rama unificada sigue exponiendo la capa derivada del skill en el ítem."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A2"},
        )
    assert r.status_code == 200
    body = r.json()
    q = next(q for q in QUESTION_BANK if q["id"] == body["id"])
    assert body["layer"] == skill_layer(q["skill"])
