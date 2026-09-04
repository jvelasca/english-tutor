"""Tests de las rutas de speaking por micro-conversaciones guiadas (V3.8).

Cubre el motor puro (estados por tarjeta de intercambio, puerta no afectada por
extras, modos all/failed/mastered), repositorio (intentos, catálogo generado,
activación), validación del corpus curado, endpoints de rutas/extras con mocks,
el intento de respuesta abierta (transcripción mock + extractor de evidencia LLM
mock + `scores_from_evidence`) y el audio modelo TTS con caché por tipo
(`opening`/`model`).
"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from domain import speaking_routes as speaking_domain
from main import app
from repositories import db
from repositories import speaking_routes as speaking_repo
from repositories import users as users_repo
from schemas.chat import ChatResponse
from services import speaking_generate as gen
from services.speaking_routes import (
    GENERATED_ID_PREFIX,
    LEVEL_ORDER,
    SPEAKING_TOPICS,
    level_items,
    phrases_for_level,
    review_next_phrase,
    route_gate,
    route_questions,
    topics_for_level,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _run_job(job_id):
    asyncio.run(speaking_domain.run_extras_job(job_id))


def _job_done(client, uid, job_id):
    _run_job(job_id)
    return client.get(
        "/api/speaking/routes/A1/extras/jobs/{0}".format(job_id),
        params={"user_id": uid},
    ).json()


def _card(
    level="A1",
    pid=None,
    topic=None,
    app_line=None,
    model_response=None,
):
    """Tarjeta de micro-conversación válida (dentro de las bandas de A1)."""
    return {
        "id": pid or f"{GENERATED_ID_PREFIX}{level}-00000001",
        "level": level,
        "topic": topic or topics_for_level(level)[0],
        "setup": "You are at a small cafe with a friend.",
        "you": "Answer your friend and order something to drink.",
        "app_line": app_line or "Hi! What would you like to drink?",
        "model_response": model_response
        or "Hello! I would like a coffee, please.",
        "difficulty_vector": {"lexical": 1, "grammar": 1, "length": 1, "discourse": 1},
    }


def _evidence(passed=True) -> dict:
    """Evidencia normalizada del extractor (alto rendimiento si `passed`)."""
    base = {
        "task_achieved": passed,
        "task_completion": 0.95 if passed else 0.2,
        "task_relevance": 0.95 if passed else 0.2,
        "task_coverage": 0.9 if passed else 0.1,
        "task_appropriateness": 0.95 if passed else 0.2,
        "grammar_errors": 0 if passed else 4,
        "lexical_tokens": ["I", "would", "like", "a", "coffee", "please"],
        "lexical_sophistication": 0.6,
        "lexical_precision": 0.8,
        "collocations": 0.5,
        "coherence": 0.95 if passed else 0.3,
        "smoothness": 0.9,
        "rhythm": 0.9,
        "self_corrections": 0,
        "hesitations": 0,
        "repetitions": 0,
        "appropriate_responses": 0.9 if passed else 0.2,
        "turn_completion": 0.9 if passed else 0.2,
        "follow_up_questions": 0.5 if passed else 0.0,
        "topic_maintenance": 0.9 if passed else 0.2,
        "clarification_requests": 0.0,
    }
    return base


# --- Corpus curado ------------------------------------------------------------


def test_speaking_corpus_are_conversation_cards():
    """Cada tarjeta del banco oficial tiene los campos del intercambio guiado,
    nivel y topic coherentes y longitud producible para el nivel."""
    for level in LEVEL_ORDER:
        pool = phrases_for_level(level)
        assert len(pool) >= 10, f"banco de {level} demasiado pequeño"
        for item in pool:
            for field in ("setup", "you", "app_line", "model_response"):
                assert item.get(field, "").strip(), f"{field} vacío en {item['id']}"
            assert item["level"] == level
            assert item.get("topic") in SPEAKING_TOPICS
            assert len(item.get("app_line", "").split()) >= 2
            assert len(item.get("model_response", "").split()) >= 2


# --- Motor: pool y estados ----------------------------------------------------


def test_route_questions_merges_base_and_extras():
    base = route_questions("A1")
    extra = _card()
    pool = route_questions("A1", [extra])
    assert len(pool) == len(base) + 1
    assert pool[-1]["id"] == extra["id"]


def test_route_questions_ignores_extras_of_other_level():
    base = route_questions("A1")
    pool = route_questions("A1", [_card(level="A2")])
    assert [q["id"] for q in pool] == [q["id"] for q in base]


def test_level_items_states_and_source():
    extra = _card(pid="sp-A1-00000001")
    first = phrases_for_level("A1")[0]
    rows = [
        {"phrase_id": first["id"], "passed": True},
        {"phrase_id": extra["id"], "passed": True},
    ]
    items = level_items("A1", rows, extra_phrases=[extra])
    by_id = {i["phrase_id"]: i for i in items}
    assert by_id[first["id"]]["state"] == "mastered"
    assert by_id[first["id"]]["source"] == "base"
    assert by_id[extra["id"]]["state"] == "mastered"
    assert by_id[extra["id"]]["source"] == "generated"
    assert by_id[extra["id"]]["app_line"] == extra["app_line"]
    # El resto del banco oficial (el primero está dominado) queda sin intentar.
    assert sum(i["state"] == "unseen" for i in items) == len(
        phrases_for_level("A1")
    ) - 1


def test_review_next_only_mastered_serves_mastered():
    extra = _card(pid="sp-A1-00000002")
    a1_first = phrases_for_level("A1")[0]
    rows = [{"phrase_id": a1_first["id"], "passed": True}]
    got = review_next_phrase(
        "A1", rows, only_mastered=True, extra_phrases=[extra]
    )
    assert got["id"] == a1_first["id"]


def test_review_next_only_failed_raises_when_empty():
    a1 = phrases_for_level("A1")
    rows = [{"phrase_id": q["id"], "passed": True} for q in a1]
    with pytest.raises(ValueError):
        review_next_phrase("A1", rows, only_failed=True)


def test_review_next_rotates_lru():
    a1 = phrases_for_level("A1")
    ids = [q["id"] for q in a1]
    rows = [{"phrase_id": qid, "passed": True} for qid in ids]
    # Todas dominadas con un intento: la siguiente a repasar es la más antigua.
    got = review_next_phrase("A1", rows, only_mastered=True)
    assert got["id"] == ids[0]


# --- Puerta de ruta -----------------------------------------------------------


def test_route_gate_unaffected_by_extras():
    """Los intentos sobre tarjetas extra NO mueven la puerta. Dominar el banco
    oficial de A1 pasa la puerta; añadir extras fallados/dominados la deja igual."""
    a1 = phrases_for_level("A1")
    base_rows = [
        {"phrase_id": q["id"], "passed": True, "created_at": i}
        for i, q in enumerate(a1)
    ]
    extra_rows = [
        {"phrase_id": "sp-A1-00000011", "passed": False},
        {"phrase_id": "sp-A1-00000012", "passed": True},
    ]
    gate_base = route_gate("A1", base_rows)
    gate_with_extra = route_gate("A1", base_rows + extra_rows)
    assert gate_with_extra == gate_base
    assert gate_base["passed"] is True


def test_route_gate_needs_accuracy_and_checkpoint():
    a1 = phrases_for_level("A1")
    # 100% de cobertura pero con intentos fallados después de la primera pasada:
    # la precisión <70 bloquea aunque el banco esté cubierto.
    rows = []
    for i, q in enumerate(a1):
        rows.append({"phrase_id": q["id"], "passed": True})
        if i % 2 == 0:
            rows.append({"phrase_id": q["id"], "passed": False})
    gate = route_gate("A1", rows)
    assert gate["passed"] is False
    assert "accuracy" in gate["blockers"]


def test_route_competence_never_demonstrated(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = phrases_for_level("A1")
    for i, q in enumerate(a1):
        speaking_repo.record_attempt(uid, q["id"], "A1", 0.9, True)
    rows = speaking_repo.list_attempts(uid)
    comp = speaking_domain.route_competence(rows)
    states = {c["level"]: c["state"] for c in comp}
    assert states["A1"] == "functional"  # techo de práctica, nunca certifica
    assert "demonstrated" not in set(states.values())


# --- Repositorio --------------------------------------------------------------


def test_record_attempt_and_passed_ids(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = phrases_for_level("A1")[0]
    assert speaking_repo.record_attempt(uid, q["id"], "A1", 0.71, True)
    assert speaking_repo.record_attempt(uid, q["id"], "A1", 0.4, False)
    assert speaking_repo.passed_phrase_ids(uid) == {q["id"]}
    rows = speaking_repo.list_attempts(uid)
    assert len(rows) == 2
    assert all(r["phrase_id"] == q["id"] for r in rows)


def test_insert_generated_dedupes_by_content(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    payload = _card()
    assert speaking_repo.insert_generated(payload, gen.GENERATOR_VERSION) is True
    second = dict(payload, id="sp-A1-00000003")
    assert speaking_repo.insert_generated(second, gen.GENERATOR_VERSION) is False
    assert len(speaking_repo.list_generated("A1")) == 1


def test_route_extras_add_list_remove(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert speaking_repo.insert_generated(
        _card(pid="sp-A1-00000021"), gen.GENERATOR_VERSION
    )
    assert speaking_repo.insert_generated(
        _card(
            pid="sp-A1-00000022",
            app_line="Are you coming to the party tonight?",
            model_response="Yes, I think I can come after work.",
        ),
        gen.GENERATOR_VERSION,
    )
    assert speaking_repo.add_route_extras(uid, "A1", ["sp-A1-00000021"]) == 1
    assert speaking_repo.add_route_extras(uid, "A1", ["sp-A1-00000021"]) == 0
    rows = speaking_repo.list_route_extras(uid, "A1")
    assert {r["phrase_id"] for r in rows} == {"sp-A1-00000021"}
    assert speaking_repo.remove_route_extra(uid, "A1", "sp-A1-00000021") is True
    assert speaking_repo.remove_route_extra(uid, "A1", "sp-A1-00000021") is False


# --- Generador determinista ---------------------------------------------------


def _fake_chat_once(items_json, calls=None):
    async def fake(messages, model, temperature=0.7, mode="default",
                   system_prompt=None):
        if calls is not None:
            calls.append((model, messages[-1].content))
        return ChatResponse(
            model=model, content=items_json, total_duration_ms=1,
            prompt_eval_count=1, eval_count=1,
        )
    return fake


def test_compose_item_valid_generated_card():
    payload = gen.compose_item(
        "A1",
        {
            "setup": "You are at a cafe with a friend.",
            "you": "Greet your friend and order a coffee.",
            "app_line": "Hi! What would you like to drink?",
            "model_response": "Hello! I would like a coffee, please.",
            "topic": topics_for_level("A1")[0],
        },
        item_id="sp-A1-99999999",
    )
    assert payload is not None
    assert payload["id"] == "sp-A1-99999999"
    assert payload["level"] == "A1"
    assert payload["app_line"]
    assert payload["model_response"]
    assert gen.validate_payload_shape(payload)
    assert len(payload["difficulty_vector"]) == 4


def test_compose_item_rejects_wrong_topic_or_word_count():
    assert (
        gen.compose_item(
            "A1",
            {
                "setup": "You are at a cafe with a friend.",
                "you": "Greet your friend and order a coffee.",
                "app_line": "Hi! What would you like to drink?",
                "model_response": "Hello! I would like a coffee, please.",
                "topic": "aliens",
            },
            item_id="sp-A1-00000031",
        )
        is None
    )
    # Respuesta modelo demasiado corta (<4 palabras) se descarta.
    assert (
        gen.compose_item(
            "A1",
            {
                "setup": "You are at a cafe with a friend.",
                "you": "Greet your friend and order a coffee.",
                "app_line": "Hi! What would you like to drink?",
                "model_response": "Coffee.",
                "topic": topics_for_level("A1")[0],
            },
            item_id="sp-A1-00000032",
        )
        is None
    )


# --- Endpoints ----------------------------------------------------------------


def test_stats_items_question_modes(monkeypatch, tmp_path):
    """Un extra dominado se sirve en el repaso de aprendidas y en los items del
    nivel figura con `source=generated`; el pool y la puerta no se ensucian."""
    uid = _setup(monkeypatch, tmp_path)
    extra = _card(pid="sp-A1-00000041")
    assert speaking_repo.insert_generated(extra, gen.GENERATOR_VERSION)
    assert speaking_repo.add_route_extras(uid, "A1", [extra["id"]]) == 1

    # Dominar el extra directamente (fila en speaking_attempts).
    assert speaking_repo.record_attempt(uid, extra["id"], "A1", 0.95, True)

    with TestClient(app) as client:
        stats = client.get("/api/speaking/stats", params={"user_id": uid}).json()
        a1 = next(lv for lv in stats["levels"] if lv["level"] == "A1")
        assert a1["extras"] == 1
        assert a1["extras_mastered"] == 1
        assert a1["total"] == len(phrases_for_level("A1")) + 1
        assert a1["base_total"] == len(phrases_for_level("A1"))
        assert a1["gate"]["total"] == len(phrases_for_level("A1"))
        assert a1["completed"] is False

        items = client.get(
            "/api/speaking/items",
            params={"user_id": uid, "level": "A1"},
        ).json()
        extra_item = next(i for i in items["items"] if i["phrase_id"] == extra["id"])
        assert extra_item["source"] == "generated"
        assert extra_item["state"] == "mastered"
        assert extra_item["app_line"] == extra["app_line"]

        # El repaso de aprendidas puede servir el extra dominado.
        q = client.get(
            "/api/speaking/question",
            params={"user_id": uid, "level": "A1", "mode": "mastered"},
        )
        assert q.status_code == 200
        body = q.json()
        assert body["id"] == extra["id"]
        # La respuesta modelo NO se filtra en la pregunta (se revela al evaluar).
        assert "model_response" not in body
        assert body["app_line"] == extra["app_line"]

        # Sin tarjetas falladas, pedir mode=failed da 404 (mensaje honesto).
        failed = client.get(
            "/api/speaking/question",
            params={"user_id": uid, "level": "A1", "mode": "failed"},
        )
        assert failed.status_code == 404

        # Modo inválido / nivel inválido → 400.
        assert (
            client.get(
                "/api/speaking/question",
                params={"user_id": uid, "level": "A1", "mode": "bogus"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/speaking/routes/XX/extras",
                params={"user_id": uid},
                json={"count": 1},
            ).status_code
            == 400
        )


def test_extras_endpoint_flow(monkeypatch, tmp_path):
    """POST extras con modelo simulado activa tarjetas generadas y el anillo
    (stats) crece sin tocar el banco curado de la puerta."""
    uid = _setup(monkeypatch, tmp_path)
    t0 = topics_for_level("A1")[0]
    t1 = topics_for_level("A1")[1 % len(topics_for_level("A1"))]
    items = [
        {
            "setup": "You meet a classmate at the bus stop.",
            "you": "Say hello and ask where they are going.",
            "app_line": "Good morning! How are you today?",
            "model_response": "Good morning! I am fine, thanks. How about you?",
            "topic": t0,
        },
        {
            "setup": "A friend offers you a drink at home.",
            "you": "Accept politely and choose something.",
            "app_line": "Would you like something to drink?",
            "model_response": "Yes please, I would like a glass of water.",
            "topic": t1,
        },
    ]
    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr("domain.speaking_routes.pick_model", fake_pick)
    calls = []
    monkeypatch.setattr(
        "domain.speaking_routes.chat_once",
        _fake_chat_once(json.dumps({"items": items}), calls),
    )
    base_total = len(phrases_for_level("A1"))
    with TestClient(app) as client:
        r = client.post(
            "/api/speaking/routes/A1/extras",
            params={"user_id": uid},
            json={"count": 2},
        )
        assert r.status_code == 202
        job = r.json()
        assert job["status"] == "running"
        done = _job_done(client, uid, job["job_id"])
        assert done["status"] == "done"
        assert len(done["added"]) == 2
        assert all(qid.startswith(GENERATED_ID_PREFIX) for qid in done["added"])

        extras = client.get(
            "/api/speaking/routes/A1/extras",
            params={"user_id": uid},
        ).json()
        assert extras["total"] == 2

        stats = client.get("/api/speaking/stats", params={"user_id": uid}).json()
        a1 = next(lv for lv in stats["levels"] if lv["level"] == "A1")
        assert a1["total"] == base_total + 2
        assert a1["base_total"] == base_total
        assert a1["extras"] == 2
        assert a1["gate"]["passed"] is False

        # DELETE desactiva un extra y el anillo vuelve.
        qid = done["added"][0]
        d = client.delete(
            "/api/speaking/routes/A1/extras/{0}".format(qid),
            params={"user_id": uid},
        )
        assert d.status_code == 200
        assert d.json()["total"] == 1


def test_generation_job_error_surfaces(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)

    async def broken_chat(*args, **kwargs):
        raise RuntimeError("ollama caído")

    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr("domain.speaking_routes.pick_model", fake_pick)
    monkeypatch.setattr("domain.speaking_routes.chat_once", broken_chat)
    with TestClient(app) as client:
        r = client.post(
            "/api/speaking/routes/A1/extras",
            params={"user_id": uid},
            json={"count": 2},
        )
        assert r.status_code == 202
        status = _job_done(client, uid, r.json()["job_id"])
        assert status["status"] == "error"
        assert status["error"]
        assert status["added"] == []


# --- Intento de respuesta abierta ---------------------------------------------

HEARD_GOOD = (
    "I would like a coffee please and maybe a cake with it thank you very much"
)


def test_attempt_endpoint_scores_open_answer(monkeypatch, tmp_path):
    """El intento transcribe (mock), extrae evidencia con el LLM local (mock) y
    persiste con criterios y overall del scorer de respuesta abierta; además
    revela la respuesta modelo de la tarjeta."""
    uid = _setup(monkeypatch, tmp_path)
    phrase = phrases_for_level("A1")[0]

    from routers import speaking_routes as router_mod

    def fake_transcribe(_audio, _lang):
        return {"text": HEARD_GOOD, "duration": 12.0}

    async def fake_extract(task, heard, model):
        assert phrase["setup"] in task or phrase["app_line"] in task
        assert heard == HEARD_GOOD
        return _evidence(passed=True)

    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr(router_mod, "transcribe_with_timing", fake_transcribe)
    monkeypatch.setattr(
        "domain.speaking_routes.pick_model", fake_pick
    )
    monkeypatch.setattr(
        "services.speaking_llm.extract_speaking_evidence", fake_extract
    )

    with TestClient(app) as client:
        r = client.post(
            "/api/speaking/attempt",
            params={"user_id": uid},
            data={"phrase_id": phrase["id"]},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["phrase_id"] == phrase["id"]
        assert body["app_line"] == phrase["app_line"]
        assert body["model_response"] == phrase["model_response"]
        assert body["heard"] == HEARD_GOOD
        assert body["passed"] is True
        assert body["overall"] >= 0.6
        assert isinstance(body["criteria"], dict)

    rows = speaking_repo.list_attempts(uid)
    assert len(rows) == 1
    assert rows[0]["phrase_id"] == phrase["id"]
    assert bool(rows[0]["passed"]) == body["passed"]


def test_attempt_endpoint_extractor_failure_is_503(monkeypatch, tmp_path):
    """Si el extractor no produce evidencia válida el intento NO se puntúa: 503
    transitorio para reintentar (nunca un falso fallido)."""
    uid = _setup(monkeypatch, tmp_path)
    phrase = phrases_for_level("A1")[0]

    from routers import speaking_routes as router_mod

    def fake_transcribe(_audio, _lang):
        return {"text": HEARD_GOOD, "duration": 12.0}

    async def fake_extract(task, heard, model):
        return None  # extractor sin salida válida (Ollama ocupado / no JSON)

    async def fake_pick(_model=None):
        return "fake-model"

    monkeypatch.setattr(router_mod, "transcribe_with_timing", fake_transcribe)
    monkeypatch.setattr("domain.speaking_routes.pick_model", fake_pick)
    monkeypatch.setattr(
        "services.speaking_llm.extract_speaking_evidence", fake_extract
    )

    with TestClient(app) as client:
        r = client.post(
            "/api/speaking/attempt",
            params={"user_id": uid},
            data={"phrase_id": phrase["id"]},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert r.status_code == 503
        assert r.json()["detail"] == "speaking.evidence_failed"

    # Nada se persiste: el fallo del extractor no cuenta como intento.
    assert speaking_repo.list_attempts(uid) == []


# --- Audio modelo TTS por tipo -------------------------------------------------


def test_audio_endpoint_kind_with_mocked_tts(monkeypatch, tmp_path):
    """GET /api/speaking/audio/{id}?kind=opening|model sintetiza con el TTS
    mockeado el texto correcto de la tarjeta la primera vez y sirve el WAV
    cacheado en las siguientes (caché separada por kind)."""
    uid = _setup(monkeypatch, tmp_path)
    phrase = phrases_for_level("A1")[0]
    synth_calls = []

    def fake_synthesize(text, rate, voice):
        synth_calls.append((text, voice))
        return b"RIFFfakewavdata"

    monkeypatch.setattr("services.tts.is_ready", lambda voice=None: True)
    monkeypatch.setattr("services.tts.resolve_voice", lambda prefs=None: "en_GB-alan-medium")
    monkeypatch.setattr("services.tts.synthesize", fake_synthesize)

    with TestClient(app) as client:
        opening = client.get(
            "/api/speaking/audio/{0}".format(phrase["id"]),
            params={"user_id": uid, "kind": "opening"},
        )
        assert opening.status_code == 200
        assert opening.content == b"RIFFfakewavdata"
        assert synth_calls[0][0] == phrase["app_line"]

        # La misma kind sale del caché (sin re-sintetizar).
        again = client.get(
            "/api/speaking/audio/{0}".format(phrase["id"]),
            params={"user_id": uid, "kind": "opening"},
        )
        assert again.status_code == 200
        assert len(synth_calls) == 1

        # kind=model sintetiza la respuesta modelo (nuevo fichero de caché).
        model = client.get(
            "/api/speaking/audio/{0}".format(phrase["id"]),
            params={"user_id": uid, "kind": "model"},
        )
        assert model.status_code == 200
        assert len(synth_calls) == 2
        assert synth_calls[1][0] == phrase["model_response"]

        # Un kind desconocido da 404 sin tocar el TTS.
        bogus = client.get(
            "/api/speaking/audio/{0}".format(phrase["id"]),
            params={"user_id": uid, "kind": "bogus"},
        )
        assert bogus.status_code == 404
        assert len(synth_calls) == 2

    # Una tarjeta inexistente da 404.
    with TestClient(app) as client:
        missing = client.get(
            "/api/speaking/audio/mc-00000000",
            params={"user_id": uid},
        )
    assert missing.status_code == 404
