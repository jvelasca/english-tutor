"""Tests de las rutas de conversation guiada multi-turno (V3.10).

Cubre el motor puro (estados por diálogo, puerta de ruta honesta, modos
all/failed/mastered), la validación del corpus curado, el repositorio y los
endpoints de rutas con el extractor de evidencia mockeado (la evaluación se hace
sobre el transcripto persistido de una conversación real con `conversation_id`).
"""
import pytest
from fastapi.testclient import TestClient

from domain import conversation_routes as conv_domain
from main import app
from repositories import conversation_routes as conv_repo
from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo
from services.conversation_routes import (
    LEVEL_ORDER,
    current_level,
    dialogues_for_level,
    level_items,
    review_next_dialogue,
    route_gate,
)

STUDENT_LINES = [
    "Hello! My name is Ana. I am from Spain and I am happy to meet you.",
    "Yes, I have one brother and one sister. They are older than me.",
    "I live in a small flat in the city centre with my family.",
]


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


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
        "interaction": 0.85 if passed else 0.2,
    }
    return base


def _seed_conversation(uid: str, lines: list[str] | None = None) -> str:
    """Crea una conversación persistida con turnos del alumno (estilo mini-chat)."""
    cid = conversations_repo.create_conversation(uid)["id"]
    texts = lines or STUDENT_LINES
    messages = []
    for i, content in enumerate(texts):
        messages.append(
            {
                "id": f"u-{i}",
                "role": "user",
                "content": content,
                "mode": "conversation",
                "duration_ms": 4000,
                "latency_ms": 600,
            }
        )
        messages.append(
            {
                "id": f"a-{i}",
                "role": "assistant",
                "content": "That sounds great. Tell me more, please.",
                "mode": "conversation",
            }
        )
    conversations_repo.save_conversation(cid, uid, "Guided chat", messages)
    return cid


# --- Corpus curado ------------------------------------------------------------


def test_conversation_corpus_covers_all_levels_with_dialogues():
    """Cada diálogo del banco oficial tiene todos los campos pedagógicos y todos
    los niveles tienen banco suficiente para rutas."""
    for level in LEVEL_ORDER:
        pool = dialogues_for_level(level)
        assert len(pool) >= 10, f"banco de {level} demasiado pequeño"
        ids = set()
        for item in pool:
            assert item["level"] == level
            assert item["id"].startswith("cv-")
            assert item["id"] not in ids
            ids.add(item["id"])
            assert item.get("topic"), f"topic vacío en {item['id']}"
            assert item.get("context"), f"context vacío en {item['id']}"
            assert item.get("student_role"), f"student_role vacío en {item['id']}"
            assert item.get("tutor_role"), f"tutor_role vacío en {item['id']}"
            opening = item.get("opening_line", "").strip()
            assert 4 <= len(opening.split()) <= 30, (
                f"opening no conversable en {item['id']}"
            )
            goals = item.get("communicative_goals", [])
            assert 3 <= len(goals) <= 5, f"metas fuera de rango en {item['id']}"
            assert all(g.strip() for g in goals)


# --- Motor: pool y estados ----------------------------------------------------


def test_level_items_states():
    first = dialogues_for_level("A1")[0]
    rows = [
        {"dialogue_id": first["id"], "passed": True},
        {"dialogue_id": first["id"], "passed": False},
    ]
    items = level_items("A1", rows)
    by_id = {i["dialogue_id"]: i for i in items}
    assert by_id[first["id"]]["state"] == "mastered"
    assert by_id[first["id"]]["opening_line"] == first["opening_line"]
    assert by_id[first["id"]]["attempts"] == 2
    assert sum(i["state"] == "unseen" for i in items) == len(
        dialogues_for_level("A1")
    ) - 1


def test_review_next_modes_all_failed_mastered():
    a1 = dialogues_for_level("A1")
    first, second = a1[0], a1[1]
    rows = [
        {"dialogue_id": first["id"], "passed": False},
        {"dialogue_id": second["id"], "passed": True},
    ]
    got = review_next_dialogue("A1", rows)
    assert got["id"] != first["id"] and got["id"] != second["id"]
    got = review_next_dialogue("A1", rows, only_failed=True)
    assert got["id"] == first["id"]
    got = review_next_dialogue("A1", rows, only_mastered=True)
    assert got["id"] == second["id"]


def test_review_next_only_failed_raises_when_empty():
    a1 = dialogues_for_level("A1")
    rows = [{"dialogue_id": d["id"], "passed": True} for d in a1]
    with pytest.raises(ValueError):
        review_next_dialogue("A1", rows, only_failed=True)


def test_current_level_advances_by_coverage():
    a1 = dialogues_for_level("A1")
    passed_all_a1 = {d["id"] for d in a1}
    assert current_level(passed_all_a1) == "A2"
    assert current_level(set()) == "A1"


# --- Puerta de ruta -----------------------------------------------------------


def test_route_gate_passes_when_bank_mastered_clean():
    a1 = dialogues_for_level("A1")
    rows = [
        {"dialogue_id": d["id"], "passed": True, "created_at": i}
        for i, d in enumerate(a1)
    ]
    gate = route_gate("A1", rows)
    assert gate["passed"] is True
    assert gate["blockers"] == []


def test_route_gate_needs_accuracy_and_checkpoint():
    a1 = dialogues_for_level("A1")
    rows = []
    for i, d in enumerate(a1):
        rows.append({"dialogue_id": d["id"], "passed": True})
        if i % 2 == 0:
            rows.append({"dialogue_id": d["id"], "passed": False})
    gate = route_gate("A1", rows)
    assert gate["passed"] is False
    assert "accuracy" in gate["blockers"]


def test_route_competence_never_demonstrated(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = dialogues_for_level("A1")
    for i, d in enumerate(a1):
        conv_repo.record_attempt(uid, d["id"], "A1", 0.8, True)
    rows = conv_repo.list_attempts(uid)
    comp = conv_domain.route_competence(rows)
    states = {c["level"]: c["state"] for c in comp}
    assert states["A1"] == "functional"  # techo de práctica, nunca certifica
    assert "demonstrated" not in set(states.values())


# --- Repositorio --------------------------------------------------------------


def test_record_attempt_and_passed_ids(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    d = dialogues_for_level("A1")[0]
    assert conv_repo.record_attempt(uid, d["id"], "A1", 0.8, True, {"a": 1})
    assert conv_repo.record_attempt(uid, d["id"], "A1", 0.4, False)
    assert conv_repo.passed_dialogue_ids(uid) == {d["id"]}
    rows = conv_repo.list_attempts(uid)
    assert len(rows) == 2
    assert rows[0]["dialogue_id"] == d["id"]
    assert rows[0]["overall"] == 0.8


# --- Dominio: intento sobre transcripto persistido ----------------------------


async def _fake_extract(task, heard, model):
    assert "Scenario:" in task
    assert "Communicative goals" in task
    assert len(heard.split()) >= 20
    return _evidence(passed=True)


async def _fake_pick(_model=None):
    return "fake-model"


def test_submit_attempt_scores_transcript_and_persists(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dialogue = dialogues_for_level("A1")[0]
    cid = _seed_conversation(uid)

    import services.speaking_llm as llm_mod

    monkeypatch.setattr(conv_domain, "pick_model", _fake_pick)
    monkeypatch.setattr(
        llm_mod, "extract_speaking_evidence", _fake_extract
    )

    import asyncio

    result = asyncio.run(
        conv_domain.submit_attempt(uid, dialogue["id"], cid)
    )
    assert result is not None
    assert result["passed"] is True
    assert result["dialogue_id"] == dialogue["id"]
    assert result["level"] == "A1"
    assert "Hello! My name is Ana" in result["heard"]
    assert isinstance(result["criteria"], dict)
    assert result["topic"] == dialogue["topic"]

    rows = conv_repo.list_attempts(uid)
    assert len(rows) == 1
    assert rows[0]["dialogue_id"] == dialogue["id"]
    assert bool(rows[0]["passed"]) is True


def test_submit_attempt_too_short(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dialogue = dialogues_for_level("A1")[0]
    cid = _seed_conversation(uid, lines=["Hello!", "Ok."])

    import asyncio

    with pytest.raises(ValueError) as err:
        asyncio.run(conv_domain.submit_attempt(uid, dialogue["id"], cid))
    assert str(err.value) == "conversation.too_short"


def test_submit_attempt_unknown_returns_none(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    import asyncio

    # Diálogo inexistente.
    assert (
        asyncio.run(conv_domain.submit_attempt(uid, "no-existe", "cualquiera"))
        is None
    )
    # Conversación que no es del usuario.
    other = users_repo.create_user("B")["id"]
    cid = _seed_conversation(other)
    dialogue = dialogues_for_level("A1")[0]
    assert (
        asyncio.run(conv_domain.submit_attempt(uid, dialogue["id"], cid)) is None
    )


# --- Endpoints ----------------------------------------------------------------


def test_question_endpoint_serves_dialogue_and_modes(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/conversation/routes/question",
            params={"user_id": uid},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"].startswith("cv-A1-")
        assert body["opening_line"]
        assert len(body["communicative_goals"]) >= 3
        failed = client.get(
            "/api/conversation/routes/question",
            params={"user_id": uid, "mode": "failed"},
        )
        assert failed.status_code == 404


def test_stats_endpoint_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/conversation/routes/stats", params={"user_id": uid}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["attempts"] == 0
        assert body["level"] == "A1"
        assert len(body["levels"]) == len(LEVEL_ORDER)
        assert body["levels"][0]["level"] == "A1"


def test_level_items_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/conversation/routes/items",
            params={"user_id": uid, "level": "A2"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["level"] == "A2"
        assert body["total"] == len(dialogues_for_level("A2"))
        assert body["failed"] == 0 and body["mastered"] == 0
        assert body["completed"] is False


def test_attempt_endpoint_scores_conversation(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dialogue = dialogues_for_level("A1")[0]
    cid = _seed_conversation(uid)

    import services.speaking_llm as llm_mod

    monkeypatch.setattr(conv_domain, "pick_model", _fake_pick)
    monkeypatch.setattr(
        llm_mod, "extract_speaking_evidence", _fake_extract
    )

    with TestClient(app) as client:
        r = client.post(
            "/api/conversation/routes/attempt",
            params={"user_id": uid},
            json={"dialogue_id": dialogue["id"], "conversation_id": cid},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["dialogue_id"] == dialogue["id"]
        assert body["level"] == "A1"
        assert body["passed"] is True
        assert body["overall"] >= 0.6
        assert isinstance(body["criteria"], dict)
        assert isinstance(body["communicative_goals"], list)


def test_attempt_endpoint_too_short_is_400(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dialogue = dialogues_for_level("A1")[0]
    cid = _seed_conversation(uid, lines=["Hi!", "Ok."])

    with TestClient(app) as client:
        r = client.post(
            "/api/conversation/routes/attempt",
            params={"user_id": uid},
            json={"dialogue_id": dialogue["id"], "conversation_id": cid},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "conversation.too_short"


def test_attempt_endpoint_extractor_failure_is_503(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dialogue = dialogues_for_level("A1")[0]
    cid = _seed_conversation(uid)

    import services.speaking_llm as llm_mod

    async def fake_extract_none(task, heard, model):
        return None  # extractor sin salida válida (Ollama ocupado / no JSON)

    monkeypatch.setattr(conv_domain, "pick_model", _fake_pick)
    monkeypatch.setattr(
        llm_mod, "extract_speaking_evidence", fake_extract_none
    )

    with TestClient(app) as client:
        r = client.post(
            "/api/conversation/routes/attempt",
            params={"user_id": uid},
            json={"dialogue_id": dialogue["id"], "conversation_id": cid},
        )
        assert r.status_code == 503
        assert r.json()["detail"] == "speaking.evidence_failed"

    # Nada se persiste: el fallo del extractor no cuenta como intento.
    assert conv_repo.list_attempts(uid) == []
