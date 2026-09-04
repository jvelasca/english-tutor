"""Tests de la práctica extra generada de listening (V3.6).

Cubre: catálogo/repo (`listening_generated`, `listening_route_extras`),
no-regresión de la puerta de ruta al añadir extras, repaso solo-dominadas,
validación determinista del generador y los endpoints de extras.
"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from domain import listening_extras as listening_extras_domain
from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from schemas.chat import ChatResponse
from services import listening_generate as gen
from services.listening import (
    GENERATED_ID_PREFIX,
    LISTENING_SUBSKILLS,
    level_status,
    level_items,
    questions_for_level,
    review_next_question,
    route_gate,
    route_questions,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _run_job(job_id):
    """Ejecuta el trabajo de generación de forma síncrona para el test.

    Idempotente: si el background ya lo completó (status != running), no hace
    nada. Así el test no depende del timing del BackgroundTasks del TestClient.
    """
    asyncio.run(listening_extras_domain.run_extras_job(job_id))


def _job_done(client, uid, job_id):
    _run_job(job_id)
    return client.get(
        "/api/listening/routes/A1/extras/jobs/{0}".format(job_id),
        params={"user_id": uid},
    ).json()


def _minimal_extra(level="A1", qid="g-A1-00000000", script=None):
    return {
        "id": qid,
        "level": level,
        "script": script or "The bus leaves at half past six in the morning.",
        "topic": "travel",
        "skill": "numbers",
        "difficulty_vector": {f: 1 for f in (
            "speed", "vocabulary", "accent", "syntactic", "length",
            "speaker_count", "noise", "connected_speech",
        )},
    }


# --- Motor: pool de ruta con extras ------------------------------------------
# La puerta de ruta, el estado y el routing adaptativo se calculan SOLO sobre el
# banco curado; los extras solo amplían el pool de práctica y los contadores.


def test_route_questions_merges_base_and_extras():
    base = route_questions("A1")
    extra = _minimal_extra()
    pool = route_questions("A1", [extra])
    assert len(pool) == len(base) + 1
    assert pool[-1]["id"] == extra["id"]


def test_route_questions_ignores_extras_of_other_level():
    base = route_questions("A1")
    extra_a2 = _minimal_extra(level="A2", qid="g-A2-00000000")
    pool = route_questions("A1", [extra_a2])
    assert [q["id"] for q in pool] == [q["id"] for q in base]


def test_route_questions_dedupes_by_id():
    base = route_questions("A1")
    duplicate = {"id": base[0]["id"], "level": "A1"}
    pool = route_questions("A1", [duplicate])
    assert len(pool) == len(base)


def test_level_items_includes_extras_with_source():
    extra = _minimal_extra()
    items = level_items("A1", [], extra_questions=[extra])
    generated = [i for i in items if i["question_id"] == extra["id"]]
    assert len(generated) == 1
    assert generated[0]["source"] == "generated"
    assert all(
        i["source"] == "base"
        for i in items
        if i["question_id"].startswith(("l", "c"))
    )
    assert sum(i["state"] == "unseen" for i in items) == len(
        questions_for_level("A1")
    ) + 1


def test_level_items_counts_extra_mastered_with_attempt():
    extra = _minimal_extra()
    rows = [{"question_id": extra["id"], "correct": True}]
    items = level_items("A1", rows, extra_questions=[extra])
    by_id = {i["question_id"]: i for i in items}
    assert by_id[extra["id"]]["state"] == "mastered"
    assert by_id[extra["id"]]["attempts"] == 1


def test_review_next_only_mastered_serves_mastered():
    extra = _minimal_extra()
    # Un ítem del banco A1 dominado + el extra sin intentar: el repaso de lo
    # aprendido empieza por el dominado (es el único candidato mastered).
    a1_first = questions_for_level("A1")[0]
    rows = [{"question_id": a1_first["id"], "correct": True}]
    got = review_next_question(
        "A1", rows, only_mastered=True, extra_questions=[extra]
    )
    assert got["id"] == a1_first["id"]


def test_review_next_only_mastered_rotates_after_answer():
    a1 = questions_for_level("A1")
    ids = [q["id"] for q in a1]
    extra = _minimal_extra()
    rows = [{"question_id": qid, "correct": True} for qid in ids]
    # Tras una vuelta de dominadas (todas con un intento), la siguiente dominada
    # es la del intento más antiguo (ids[0]).
    got = review_next_question(
        "A1", rows, only_mastered=True, extra_questions=[extra]
    )
    assert got["id"] == ids[0]


def test_review_next_only_mastered_empty_pool_raises():
    a1 = questions_for_level("A1")
    rows = [{"question_id": q["id"], "correct": False} for q in a1]
    with pytest.raises(ValueError):
        review_next_question("A1", rows, only_mastered=True)


def test_route_gate_unaffected_by_extras():
    """Las respuestas a ítems extra NO mueven la puerta: ni la inflan ni la
    rompen. La puerta de A1 con (banco completo acertado + extra fallado) es
    exactamente la misma que con (banco completo acertado solo)."""
    a1 = questions_for_level("A1")
    base_rows = [
        {"question_id": q["id"], "correct": True, "replay_count": 0} for q in a1
    ]
    extra_rows = [
        {"question_id": "g-A1-00000001", "correct": False, "replay_count": 2},
        {"question_id": "g-A1-00000002", "correct": True, "replay_count": 0},
    ]
    gate_base = route_gate("A1", base_rows)
    gate_with_extra = route_gate("A1", base_rows + extra_rows)
    assert gate_with_extra == gate_base
    assert gate_base["passed"] is True


def test_level_status_extra_attempts_do_not_pollute_gate_rows():
    """Un extra fallado no añade evidencia negativa a la ruta (skill/topic del
    extra no existen en el banco): `level_status` lo ignora por diseño."""
    a1 = questions_for_level("A1")
    base_rows = [
        {"question_id": q["id"], "correct": True, "replay_count": 0} for q in a1
    ]
    extra_rows = [
        {"question_id": "g-A1-00000001", "correct": False, "replay_count": 0}
    ]
    base_status = next(s for s in level_status(base_rows) if s["level"] == "A1")
    with_status = next(
        s for s in level_status(base_rows + extra_rows) if s["level"] == "A1"
    )
    assert with_status["mastered"] == base_status["mastered"]
    assert with_status["completed"] == base_status["completed"] is True
    assert with_status["gate"] == base_status["gate"]


# --- Repositorio --------------------------------------------------------------


def test_insert_generated_dedupes_by_content(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    item = gen.compose_item(
        "A1",
        {
            "script": "The train leaves at half past six.",
            "question": "What time does the train leave?",
            "options": [
                "Half past six", "Half past five", "Half past seven",
                "Half past eight",
            ],
            "answer_index": 0,
            "skill": "numbers",
            "topic": "travel",
        },
        item_id="g-A1-11111111",
    )
    assert item is not None
    first = listening_repo.insert_generated(item, gen.GENERATOR_VERSION)
    assert first is True
    # Mismo contenido, otro id → se ignora (no se duplica el texto).
    second = listening_repo.insert_generated(
        dict(item, id="g-A1-22222222"), gen.GENERATOR_VERSION
    )
    assert second is False
    rows = listening_repo.list_generated("A1")
    assert len(rows) == 1
    assert rows[0]["id"] == "g-A1-11111111"


def test_route_extras_add_list_remove(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # `listening_route_extras` tiene FK a `listening_generated`: la activación
    # siempre apunta a un ítem del catálogo (generado antes).
    for qid, script in (
        (
            "g-A1-00000001",
            "The bus leaves at half past six in the morning.",
        ),
        (
            "g-A1-00000002",
            "The post office closes at five o'clock today.",
        ),
    ):
        item = _minimal_extra(qid=qid, script=script)
        assert listening_repo.insert_generated(item, gen.GENERATOR_VERSION)
    assert listening_repo.add_route_extras(uid, "A1", ["g-A1-00000001"]) == 1
    # Re-activar no cuenta como nuevo.
    assert listening_repo.add_route_extras(uid, "A1", ["g-A1-00000001"]) == 0
    assert listening_repo.add_route_extras(uid, "A1", ["g-A1-00000002"]) == 1
    rows = listening_repo.list_route_extras(uid, "A1")
    assert {r["question_id"] for r in rows} == {
        "g-A1-00000001", "g-A1-00000002",
    }
    assert listening_repo.remove_route_extra(uid, "A1", "g-A1-00000001") is True
    assert listening_repo.remove_route_extra(uid, "A1", "g-A1-00000001") is False
    assert len(listening_repo.list_route_extras(uid, "A1")) == 1


# --- Generador: parseo y validación determinista -----------------------------


def _fake_chat_once(items_json: str, calls=None):
    async def fake(messages, model, temperature=0.7, mode="default",
                   system_prompt=None):
        if calls is not None:
            calls.append((model, messages[-1].content))
        return ChatResponse(
            model=model, content=items_json, total_duration_ms=1,
            prompt_eval_count=1, eval_count=1,
        )

    return fake


def test_parse_content_fences_and_items():
    raw = 'Aquí va el JSON:\n```json\n{"items":[{"script":"Hi"}]}\n```\nFin'
    items = gen.parse_content(raw)
    assert items == [{"script": "Hi"}]


def test_parse_content_single_object():
    items = gen.parse_content('{"script":"Hola","question":"¿?"}')
    assert len(items) == 1


def test_parse_content_garbage_raises():
    with pytest.raises(ValueError):
        gen.parse_content("esto no es JSON")


def test_compose_item_valid_derives_answer_index():
    payload = gen.compose_item(
        "A1",
        {
            "script": "Tom gets up at seven o'clock every morning.",
            "question": "What time does Tom get up?",
            # answer_index del modelo mal (1): se ignora, la correcta es la
            # única que aparece en el script (índice 0).
            "options": [
                "At seven", "At nine", "At eight", "At six",
            ],
            "answer_index": 1,
            "skill": "detail",
            "topic": "daily_routine",
        },
        item_id="g-A1-33333333",
    )
    assert payload is not None
    assert payload["id"] == "g-A1-33333333"
    assert payload["level"] == "A1"
    assert payload["answer_index"] == 0
    assert payload["options"][0] == "At seven"
    assert gen.validate_payload_shape(payload)
    assert payload["skill"] == "detail"
    assert payload["topic"] == "daily_routine"
    assert payload["transcript"] == payload["script"]
    assert len(payload["difficulty_vector"]) == 8
    # Factores de audio no realizables con Piper fijados a 1 (honestidad).
    assert payload["difficulty_vector"]["accent"] == 1
    assert payload["difficulty_vector"]["speaker_count"] == 1


def test_compose_item_rejects_ambiguous_options():
    # Dos opciones presentes en el script → no verificable, se descarta.
    payload = gen.compose_item(
        "A1",
        {
            "script": "Tom drinks coffee and reads the news.",
            "question": "What does Tom do?",
            "options": [
                "Drinks coffee", "Reads the news", "Eats breakfast",
                "Watches TV",
            ],
            "skill": "detail",
            "topic": "daily_routine",
        },
        item_id="g-A1-44444444",
    )
    assert payload is None


def test_compose_item_rejects_wrong_shape():
    assert (
        gen.compose_item(
            "A1",
            {"script": "A short sentence here.", "question": "What?",
             "options": ["a", "b"], "skill": "detail", "topic": "travel"},
            item_id="g-A1-55555555",
        )
        is None
    )
    assert (
        gen.compose_item(
            "A1",
            {"script": "A short sentence here.", "question": "What?",
             "options": ["a", "b", "c", "d"], "skill": "gist",
             "topic": "travel"},
            item_id="g-A1-55555556",
        )
        is None
    )
    # Topic no canónico.
    assert (
        gen.compose_item(
            "A1",
            {"script": "A short sentence here.", "question": "What?",
             "options": ["a", "b", "c", "d"], "skill": "detail",
             "topic": "aliens"},
            item_id="g-A1-55555557",
        )
        is None
    )


def test_generated_skills_are_comprehension_only():
    assert set(gen.GENERATED_SUBSKILLS) <= set(LISTENING_SUBSKILLS)
    assert "dictation" not in gen.GENERATED_SUBSKILLS
    assert "shadowing" not in gen.GENERATED_SUBSKILLS
    assert "gist" not in gen.GENERATED_SUBSKILLS  # paráfrasis no verificable


def test_bank_shape_accepts_generated_payload():
    """Un payload generado pasa las invariantes del banco (validate_listening_bank
    usa las mismas claves/estructura)."""
    payload = gen.compose_item(
        "A1",
        {
            "script": "The post office closes at five o'clock today.",
            "question": "When does the post office close?",
            "options": [
                "At five", "At four", "At six", "At seven",
            ],
            "answer_index": 0,
            "skill": "numbers",
            "topic": "functional",
        },
        item_id="g-A1-66666666",
    )
    assert payload is not None
    assert payload["id"].startswith(GENERATED_ID_PREFIX)
    for key in ("script", "question", "options", "answer_index", "skill",
                "topic", "difficulty_vector", "speech_rate", "duration"):
        assert key in payload, key
    assert gen.validate_payload_shape(payload)


# --- Endpoints ----------------------------------------------------------------


def test_extras_endpoint_flow(monkeypatch, tmp_path):
    """POST extras (con modelo simulado) activa los ítems generados en la ruta y
    el anillo (stats) crece sin tocar el banco curado de la puerta."""
    uid = _setup(monkeypatch, tmp_path)

    items = [
        {
            "script": "The bus leaves at half past six in the morning.",
            "question": "What time does the bus leave?",
            "options": [
                "Half past six", "Half past five", "Half past seven",
                "Half past eight",
            ],
            "skill": "numbers",
            "topic": "travel",
        },
        {
            "script": "Sara bought a cheap umbrella because it was raining.",
            "question": "Which word describes the umbrella?",
            "options": ["Cheap", "Expensive", "Broken", "Heavy"],
            "skill": "vocabulary",
            "topic": "shopping",
        },
        {
            "script": "First we washed the dishes and then we dried them.",
            "question": "What did they do first?",
            "options": [
                "Washed the dishes", "Dried the towels", "Cooked the dinner",
                "Cleaned the windows",
            ],
            "skill": "sequencing",
            "topic": "daily_routine",
        },
    ]
    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr("domain.listening_extras.pick_model", fake_pick)
    calls = []
    monkeypatch.setattr(
        "domain.listening_extras.chat_once",
        _fake_chat_once(json.dumps({"items": items}), calls),
    )

    base_total = len(questions_for_level("A1"))
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/routes/A1/extras",
            params={"user_id": uid},
            json={"count": 3},
        )
        assert r.status_code == 202
        job = r.json()
        assert job["status"] == "running"
        job_id = job["job_id"]

        # El trabajo corre en background; al terminar devuelve los ids activados.
        done_body = _job_done(client, uid, job_id)
        assert done_body["status"] == "done"
        assert len(done_body["added"]) == 3
        assert all(qid.startswith("g-A1-") for qid in done_body["added"])

        # GET de extras activados.
        extras = client.get(
            "/api/listening/routes/A1/extras",
            params={"user_id": uid},
        ).json()
        assert extras["level"] == "A1"
        assert extras["total"] == 3

        # Stats: anillo crece con extras pero el banco curado queda intacto.
        stats = client.get(
            "/api/listening/stats", params={"user_id": uid}
        ).json()
        a1 = next(lv for lv in stats["levels"] if lv["level"] == "A1")
        assert a1["total"] == base_total + 3
        assert a1["base_total"] == base_total
        assert a1["base_mastered"] == 0
        assert a1["extras"] == 3
        assert a1["extras_mastered"] == 0
        assert a1["mastered"] == 0
        assert a1["completed"] is False
        assert a1["gate"]["passed"] is False
        assert a1["gate"]["total"] == base_total

        # La ruta actual y el estado no cambian al añadir extras.
        assert stats["level"] == "A1"

        # Responder correctamente un extra lo marca dominado (sin mover la puerta).
        qid = extras["question_ids"][0]
        answered = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": qid, "answer_index": 0},
        )
        assert answered.status_code == 200
        assert answered.json()["correct"] is True

        stats2 = client.get(
            "/api/listening/stats", params={"user_id": uid}
        ).json()
        a1b = next(lv for lv in stats2["levels"] if lv["level"] == "A1")
        assert a1b["extras_mastered"] == 1
        assert a1b["mastered"] == 1
        assert a1b["completed"] is False
        # La puerta sigue pidiendo el banco completo.
        assert a1b["gate"]["passed"] is False

        # DELETE desactiva un extra y el anillo vuelve a base.
        d = client.delete(
            "/api/listening/routes/A1/extras/{0}".format(qid),
            params={"user_id": uid},
        )
        assert d.status_code == 200
        assert d.json()["total"] == 2
        stats3 = client.get(
            "/api/listening/stats", params={"user_id": uid}
        ).json()
        a1c = next(lv for lv in stats3["levels"] if lv["level"] == "A1")
        assert a1c["total"] == base_total + 2
        assert a1c["extras"] == 2
        assert a1c["extras_mastered"] == 0  # el extra desactivado no cuenta


def test_extras_endpoint_question_modes(monkeypatch, tmp_path):
    """Con un extra dominado, `mode=mastered` lo sirve; los ítems generados se
    pueden responder y su audio/repaso funcionan igual que el banco."""
    uid = _setup(monkeypatch, tmp_path)
    item = {
        "script": "The meeting starts at nine thirty on Monday.",
        "question": "When does the meeting start?",
        "options": [
            "At nine thirty", "At nine fifteen", "At ten thirty", "At eight",
        ],
        "skill": "numbers",
        "topic": "work",
    }
    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr("domain.listening_extras.pick_model", fake_pick)
    monkeypatch.setattr(
        "domain.listening_extras.chat_once",
        _fake_chat_once(json.dumps({"items": [item]})),
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/routes/A1/extras",
            params={"user_id": uid},
            json={"count": 1},
        )
        assert r.status_code == 202
        _run_job(r.json()["job_id"])
        extras = client.get(
            "/api/listening/routes/A1/extras",
            params={"user_id": uid},
        ).json()
        qid = extras["question_ids"][0]

        # La pregunta del repaso de ruta (level) puede servir el extra.
        q = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1"},
        ).json()
        assert q["level"] == "A1"

        # Dominar el extra y pedir el repaso de lo aprendido.
        ok = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": qid, "answer_index": 0},
        )
        assert ok.status_code == 200 and ok.json()["correct"] is True

        mastered = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "mastered"},
        )
        assert mastered.status_code == 200
        assert mastered.json()["id"] in {q["id"] for q in questions_for_level("A1")} | {qid}

        # Los items del nivel marcan el origen del extra.
        items = client.get(
            "/api/listening/items", params={"user_id": uid, "level": "A1"}
        ).json()
        extra_item = next(
            i for i in items["items"] if i["question_id"] == qid
        )
        assert extra_item["source"] == "generated"
        assert extra_item["state"] == "mastered"
        assert items["total"] == len(questions_for_level("A1")) + 1

        # Modo no válido sigue rechazado.
        bad = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "bogus"},
        )
        assert bad.status_code == 400

        # Nivel no válido rechazado.
        assert (
            client.post(
                "/api/listening/routes/XX/extras",
                params={"user_id": uid},
                json={"count": 1},
            ).status_code
            == 400
        )


def test_generation_job_error_surfaces(monkeypatch, tmp_path):
    """Si el modelo local no responde, el trabajo termina en `error` con mensaje
    (el endpoint no se cuelga y el frontend puede mostrarlo)."""
    uid = _setup(monkeypatch, tmp_path)

    async def broken_chat(*args, **kwargs):
        raise RuntimeError("ollama caído")

    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr("domain.listening_extras.pick_model", fake_pick)
    monkeypatch.setattr("domain.listening_extras.chat_once", broken_chat)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/routes/A1/extras",
            params={"user_id": uid},
            json={"count": 2},
        )
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        status = _job_done(client, uid, job_id)
        assert status["status"] == "error"
        assert status["error"]
        assert status["added"] == []

        # Un trabajo de otro usuario no se puede consultar.
        other = users_repo.create_user("B")["id"]
        forbidden = client.get(
            "/api/listening/routes/A1/extras/jobs/{0}".format(job_id),
            params={"user_id": other},
        )
        assert forbidden.status_code == 404
