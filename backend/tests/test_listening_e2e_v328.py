"""V3.28 (Listening Engine 4.0, Fase 2, Bloque F): E2E adaptativo y negativos.

Recorre con `TestClient` el ciclo pedagógico completo (diagnóstico → perfil →
pregunta → flujo → evidencia → diagnóstico) y fija los contratos:

- E2E-01 A1 con recognition débil → perfil Caso A (`bottom_up_path`) y la
  siguiente pregunta adaptativa es de capa recognition con flow de 5 etapas.
- E2E-02 B2 con connected speech débil → Caso D (`connected_speech_path`); en la
  ruta por nivel el shadowing deja de ser opcional (override del perfil).
- E2E-03 fuerte en comprehension y débil en inference → Caso C (`top_down_path`)
  y la siguiente pregunta adaptativa es de capa inference.
- E2E-04 sesión mastered → modo compacto sin flow (contrato del Bloque A).
- Negativos: B2 no permite reveal manual antes de Post; B2 no permite saltar el
  shadowing cuando el perfil lo obliga; un ítem derivado nunca aparece en la
  certificación; `transcript_used` refleja lo realmente visto (persistencia
  fiable).

Las siembras de perfil eligen ítems por *realización auditiva real*
(`resilience_dimensions`, nunca por la skill declarada): un intento solo aporta
evidencia a una dimensión si el audio del ítem la ejercita."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.auditory_profile import PROFILE_MIN_ATTEMPTS
from services.listening import (
    DERIVED_RECOGNITION_POOL,
    QUESTION_BANK,
    resilience_dimensions,
    route_questions,
    skill_layer,
)
from services.listening_flow import FLOW_STAGES

MIN = PROFILE_MIN_ATTEMPTS


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _realizes(q: dict, dim: str) -> bool:
    return dim in resilience_dimensions(q)


def _bank_items(level: str, layer: str | None = None) -> list[dict]:
    """Ítems del banco de un nivel, opcionalmente de una capa receptiva."""
    out = []
    for q in QUESTION_BANK:
        if q["level"] != level:
            continue
        if q["skill"] in ("dictation", "shadowing"):
            continue
        if layer is not None and skill_layer(q["skill"]) != layer:
            continue
        out.append(q)
    assert len(out) >= MIN, f"banco {level}/{layer} insuficiente: {len(out)}"
    return out


def _attempt(uid: str, q: dict, correct: bool) -> None:
    """Persiste un intento directo (siembra de perfil); no pasa por la API."""
    listening_repo.record_attempt(
        uid,
        q["id"],
        0 if correct else 1,
        correct,
        skill=q["skill"],
        difficulty=3,
    )


def _diagnostic(client: TestClient, uid: str) -> dict:
    r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    return r.json()


def _assert_5_stage_flow(body: dict) -> None:
    assert [step["stage"] for step in body["flow"]] == list(FLOW_STAGES)


# --- E2E-01: Caso A (recognition débil, A1) ----------------------------------

def test_e2e01_case_a_bottom_up_serves_recognition_with_flow(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Comprehension sólida (100%) y recognition débil (25%, con muestra mínima).
    # Poca muestra en clear_speech: evita que el perfil salte al Caso D.
    comp = _bank_items("A1", layer="comprehension")[:MIN + 2]
    rec = _bank_items("A1", layer="recognition")[:MIN + 1]
    for q in comp:
        _attempt(uid, q, True)
    for q in rec[:1]:
        _attempt(uid, q, True)
    for q in rec[1:]:
        _attempt(uid, q, False)

    with TestClient(app) as client:
        diag = _diagnostic(client, uid)
        assert diag["profile"]["layer"] == "recognition"
        assert diag["profile"]["intervention"] == "bottom_up_path"
        assert diag["profile"]["needs_min_attempts"] is False

        # Siguiente pregunta adaptativa: capa recognition con micro-flujo.
        r = client.get("/api/listening/question", params={"user_id": uid})
        assert r.status_code == 200
        body = r.json()
        assert skill_layer(body["skill"]) == "recognition"
        assert body["layer"] == "recognition"
        _assert_5_stage_flow(body)
        # El perfil Caso A hace el shadowing obligatorio en ese ítem.
        assert body["transcript_policy"]["shadowing_optional"] is False
        assert body["flow"][-1]["stage"] == "shadowing"
        assert body["flow"][-1]["allow_skip"] is False


# --- E2E-02: Caso D (connected speech débil, B2) ------------------------------

def test_e2e02_case_d_connected_speech_makes_shadowing_mandatory(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    # Condición clara sólida: ≥3 ítems cuya *realización* es habla clara.
    clear = [
        q for q in _bank_items("A1") if _realizes(q, "clear_speech")
    ][:MIN + 1]
    assert len(clear) >= MIN, "no hay ítems con realización clear_speech"
    for q in clear:
        _attempt(uid, q, True)
    # Condición connected débil: ≥3 ítems B2 cuya realización es connected.
    connected = [
        q
        for q in QUESTION_BANK
        if q["level"] == "B2" and q["skill"] not in ("dictation", "shadowing")
        and _realizes(q, "connected_speech")
    ][:MIN + 1]
    assert len(connected) >= MIN, "no hay ítems B2 con realización connected_speech"
    for q in connected:
        _attempt(uid, q, False)

    with TestClient(app) as client:
        diag = _diagnostic(client, uid)
        assert diag["profile"]["layer"] is None
        assert diag["profile"]["intervention"] == "connected_speech_path"

        # Objetivo: un ítem B2 de capa inferencia NO marcado (único no intentado
        # de la ruta B2) para fijar el contrato de política B2 + override D.
        target = next(
            q
            for q in _bank_items("B2", layer="inference")
            if q["id"] not in {c["id"] for c in connected}
        )
        for q in route_questions("B2"):
            if q["id"] != target["id"]:
                _attempt(uid, q, False)  # intentado (falla): no vuelve a salir
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "B2"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == target["id"]
        _assert_5_stage_flow(body)
        # B2 no permite reveal manual antes de Post…
        assert body["transcript_policy"]["revelation"] == "never_before_post"
        assert body["transcript_policy"]["allow_manual_reveal"] is False
        # …y el perfil Caso D obliga al shadowing (no se puede saltar).
        assert body["transcript_policy"]["shadowing_optional"] is False
        assert body["flow"][-1]["stage"] == "shadowing"
        assert body["flow"][-1]["allow_skip"] is False


# --- E2E-03: Caso C (inference débil) -----------------------------------------

def test_e2e03_case_c_top_down_serves_inference_with_flow(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Comprehension sólida; inference débil (25%, con muestra mínima). La poca
    # muestra en clear_speech evita el Caso D (que manda antes que el C).
    comp = _bank_items("A1", layer="comprehension")[:MIN + 2]
    inf = _bank_items("A1", layer="inference")[:MIN + 1]
    for q in comp:
        _attempt(uid, q, True)
    for q in inf[:1]:
        _attempt(uid, q, True)
    for q in inf[1:]:
        _attempt(uid, q, False)

    with TestClient(app) as client:
        diag = _diagnostic(client, uid)
        assert diag["profile"]["layer"] == "inference"
        assert diag["profile"]["intervention"] == "top_down_path"
        assert diag["profile"]["needs_min_attempts"] is False

        r = client.get("/api/listening/question", params={"user_id": uid})
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "inference"
        assert skill_layer(body["skill"]) == "inference"
        _assert_5_stage_flow(body)


# --- E2E-04: sesión mastered → modo compacto ---------------------------------

def test_e2e04_mastered_session_is_compact_without_flow(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _bank_items("A1", layer="comprehension")[0]
    _attempt(uid, q, True)
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "mastered"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == q["id"]
    # Modo compacto: sin micro-flujo ni sync (contrato del Bloque A/D).
    assert body["flow"] == []
    assert body["transcript_policy"] == {}
    assert body["sentence_timings"] == []


# --- Negativos del contrato pedagógico ----------------------------------------

def test_negative_derived_item_never_in_certification(monkeypatch, tmp_path):
    """Un ítem derivado bottom-up no forma parte del pool de ruta (gate/items)."""
    uid = _setup(monkeypatch, tmp_path)
    derived = next(q for q in DERIVED_RECOGNITION_POOL if q.get("level") == "A1")
    pool_ids = {q["id"] for q in route_questions("A1")}
    assert derived["id"] not in pool_ids
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/items", params={"user_id": uid, "level": "A1"}
        )
    assert r.status_code == 200
    item_ids = {item["question_id"] for item in r.json()["items"]}
    assert derived["id"] not in item_ids


def test_negative_transcript_used_reflects_what_was_seen(monkeypatch, tmp_path):
    """`transcript_used` se persiste de forma fiable por intento (evidencia)."""
    uid = _setup(monkeypatch, tmp_path)
    q = _bank_items("A1", layer="comprehension")[0]
    correct_index = q["answer_index"]
    wrong_index = (correct_index + 1) % len(q["options"])
    payload = {
        "question_id": q["id"],
        "answer_index": wrong_index,
        "response_time_ms": 3200,
        "replay_count": 0,
        "speed_used": "normal",
        "stage": "while2",
        "transcript_used": "hidden",
    }
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer", params={"user_id": uid}, json=payload
        )
        assert r.status_code == 200
        assert r.json()["correct"] is False
        payload.update(answer_index=correct_index, replay_count=1)
        payload["transcript_used"] = "full"
        r = client.post(
            "/api/listening/answer", params={"user_id": uid}, json=payload
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True
    rows = listening_repo.list_attempts(uid)
    assert [row["transcript_used"] for row in rows] == ["hidden", "full"]
    assert [row["correct"] for row in rows] == [False, True]


def test_negative_answering_derived_item_does_not_advance_gate(monkeypatch, tmp_path):
    """Aunque se responda (y acierte) un ítem derivado, la puerta del nivel no
    se mueve: la certificación se calcula solo sobre el banco curado."""
    uid = _setup(monkeypatch, tmp_path)
    derived = next(
        q
        for q in DERIVED_RECOGNITION_POOL
        if q.get("level") == "A1" and q.get("task_type") == "cloze"
    )
    level = derived["level"]
    base_total = len(route_questions(level))
    with TestClient(app) as client:
        before = client.get(
            "/api/listening/stats", params={"user_id": uid}
        ).json()
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": derived["id"],
                "answer_index": 0,
                "response_time_ms": 1000,
                "replay_count": 0,
                "speed_used": "normal",
                "stage": "while2",
                "transcript_used": "hidden",
            },
        )
        assert r.status_code in (200, 404), r.text
        after = client.get(
            "/api/listening/stats", params={"user_id": uid}
        ).json()
    level_before = next(
        lv for lv in before["levels"] if lv["level"] == level
    )
    level_after = next(lv for lv in after["levels"] if lv["level"] == level)
    assert level_after["total"] == level_before["total"] == base_total
    assert level_after["mastered"] == level_before["mastered"]
