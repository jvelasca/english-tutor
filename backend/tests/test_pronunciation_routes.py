"""Tests de las rutas de pronunciation read-aloud (V3.9).

Cubre el motor puro (estados por frase, puerta de ruta honesta, modos
all/failed/mastered), el repositorio, la validación del corpus curado y los
endpoints de rutas con la transcripción Whisper mockeada (la evaluación es
determinista: `score_pronunciation`, sin LLM).
"""
import pytest
from fastapi.testclient import TestClient

from domain import pronunciation_routes as pron_domain
from main import app
from repositories import db
from repositories import pronunciation_routes as pron_repo
from repositories import users as users_repo
from services.pronunciation_routes import (
    LEVEL_ORDER,
    current_level,
    level_items,
    phrases_for_level,
    review_next_phrase,
    route_gate,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Corpus curado ------------------------------------------------------------


def test_pronunciation_corpus_covers_all_levels_with_phrases():
    """Cada frase del banco oficial tiene script/topic/difficulty coherentes y
    longitud producible para su nivel; todos los niveles tienen banco."""
    for level in LEVEL_ORDER:
        pool = phrases_for_level(level)
        assert len(pool) >= 15, f"banco de {level} demasiado pequeño"
        for item in pool:
            script = item.get("script", "").strip()
            assert script, f"script vacío en {item['id']}"
            assert item["level"] == level
            assert item.get("topic"), f"topic vacío en {item['id']}"
            assert 2 <= len(script.split()) <= 22, (
                f"longitud no producible en {item['id']}"
            )
            vector = item.get("difficulty_vector", {})
            assert {"lexical", "grammar", "length", "prosody"} <= set(vector)


# --- Motor: pool y estados ----------------------------------------------------


def test_level_items_states():
    first = phrases_for_level("A1")[0]
    rows = [
        {"phrase_id": first["id"], "passed": True},
        {"phrase_id": first["id"], "passed": False},
    ]
    items = level_items("A1", rows)
    by_id = {i["phrase_id"]: i for i in items}
    assert by_id[first["id"]]["state"] == "mastered"
    assert by_id[first["id"]]["script"] == first["script"]
    assert by_id[first["id"]]["attempts"] == 2
    # El resto del banco oficial queda sin intentar.
    assert sum(i["state"] == "unseen" for i in items) == len(
        phrases_for_level("A1")
    ) - 1


def test_review_next_modes_all_failed_mastered():
    a1 = phrases_for_level("A1")
    first, second = a1[0], a1[1]
    rows = [
        {"phrase_id": first["id"], "passed": False},
        {"phrase_id": second["id"], "passed": True},
    ]
    # Modo libre: la frase nunca intentada es la que se sirve (LRU).
    got = review_next_phrase("A1", rows)
    assert got["id"] != first["id"] and got["id"] != second["id"]
    # Modo failed: solo la frase nunca superada.
    got = review_next_phrase("A1", rows, only_failed=True)
    assert got["id"] == first["id"]
    # Modo mastered: solo la frase dominada.
    got = review_next_phrase("A1", rows, only_mastered=True)
    assert got["id"] == second["id"]


def test_review_next_only_failed_raises_when_empty():
    a1 = phrases_for_level("A1")
    rows = [{"phrase_id": q["id"], "passed": True} for q in a1]
    with pytest.raises(ValueError):
        review_next_phrase("A1", rows, only_failed=True)


def test_review_next_rotates_lru():
    a1 = phrases_for_level("A1")
    ids = [q["id"] for q in a1]
    rows = [{"phrase_id": qid, "passed": True} for qid in ids]
    got = review_next_phrase("A1", rows, only_mastered=True)
    assert got["id"] == ids[0]


def test_current_level_advances_by_coverage():
    a1 = phrases_for_level("A1")
    passed_all_a1 = {q["id"] for q in a1}
    assert current_level(passed_all_a1) in ("A2", "C2")
    assert current_level(set()) == "A1"


# --- Puerta de ruta -----------------------------------------------------------


def test_route_gate_passes_when_bank_mastered_clean():
    a1 = phrases_for_level("A1")
    rows = [
        {"phrase_id": q["id"], "passed": True, "created_at": i}
        for i, q in enumerate(a1)
    ]
    gate = route_gate("A1", rows)
    assert gate["passed"] is True
    assert gate["blockers"] == []


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


def test_route_gate_checkpoint_needs_first_pass():
    """Dominar el banco a base de reintentos NO satisface el checkpoint: las
    frases falladas la primera vez no cuentan aunque se dominen después."""
    a1 = phrases_for_level("A1")
    rows = []
    for q in a1:
        rows.append({"phrase_id": q["id"], "passed": False})
        rows.append({"phrase_id": q["id"], "passed": True})
    gate = route_gate("A1", rows)
    assert gate["passed"] is False
    assert "checkpoint" in gate["blockers"]


def test_route_competence_never_demonstrated(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = phrases_for_level("A1")
    for i, q in enumerate(a1):
        pron_repo.record_attempt(uid, q["id"], "A1", 95, True)
    rows = pron_repo.list_attempts(uid)
    comp = pron_domain.route_competence(rows)
    states = {c["level"]: c["state"] for c in comp}
    assert states["A1"] == "functional"  # techo de práctica, nunca certifica
    assert "demonstrated" not in set(states.values())


# --- Repositorio --------------------------------------------------------------


def test_record_attempt_and_passed_ids(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = phrases_for_level("A1")[0]
    assert pron_repo.record_attempt(uid, q["id"], "A1", 95, True)
    assert pron_repo.record_attempt(uid, q["id"], "A1", 40, False)
    assert pron_repo.passed_phrase_ids(uid) == {q["id"]}
    rows = pron_repo.list_attempts(uid)
    assert len(rows) == 2
    assert all(r["phrase_id"] == q["id"] for r in rows)
    assert rows[0]["score"] == 95


# --- Endpoints ----------------------------------------------------------------


def test_question_endpoint_serves_phrase_and_modes(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/pronunciation/routes/question",
            params={"user_id": uid},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"].startswith("pr-A1-")
        assert body["script"]
        # Modo failed sin frases falladas → 404 (no hay bucket).
        failed = client.get(
            "/api/pronunciation/routes/question",
            params={"user_id": uid, "mode": "failed"},
        )
        assert failed.status_code == 404


def test_stats_endpoint_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/pronunciation/routes/stats", params={"user_id": uid}
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
            "/api/pronunciation/routes/items",
            params={"user_id": uid, "level": "A2"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["level"] == "A2"
        assert body["total"] == len(phrases_for_level("A2"))
        assert body["failed"] == 0 and body["mastered"] == 0
        assert body["completed"] is False


def _fake_transcribe(text):
    def fake(_audio, _lang):
        return {"text": text, "duration": 2.0}

    return fake


def test_attempt_endpoint_scores_deterministic(monkeypatch, tmp_path):
    """El intento transcribe (mock Whisper) y puntúa con el scorer determinista:
    leyendo la frase exacta pasa (score >= 80) y persiste; una grabación vacía
    falla sin LLM."""
    uid = _setup(monkeypatch, tmp_path)
    phrase = phrases_for_level("A1")[0]

    from routers import pronunciation_routes as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe(phrase["script"])
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation/routes/attempt",
            params={"user_id": uid},
            data={"phrase_id": phrase["id"]},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["phrase_id"] == phrase["id"]
        assert body["level"] == "A1"
        assert body["script"] == phrase["script"]
        assert body["score"] >= 80
        assert body["passed"] is True
        assert body["grade"] == "good"
        assert body["topic"] == phrase["topic"]

    rows = pron_repo.list_attempts(uid)
    assert len(rows) == 1
    assert bool(rows[0]["passed"]) is True

    # Segundo intento con audio vacío → falla sin LLM, determinista.
    monkeypatch.setattr(router_mod, "transcribe_with_timing", _fake_transcribe(""))
    with TestClient(app) as client:
        ko = client.post(
            "/api/pronunciation/routes/attempt",
            params={"user_id": uid},
            data={"phrase_id": phrase["id"]},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ko.status_code == 200
        assert ko.json()["passed"] is False
        assert ko.json()["grade"] == "needs_practice"
    assert len(pron_repo.list_attempts(uid)) == 2


def test_attempt_endpoint_unknown_phrase_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)

    from routers import pronunciation_routes as router_mod

    monkeypatch.setattr(router_mod, "transcribe_with_timing", _fake_transcribe("hi"))
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation/routes/attempt",
            params={"user_id": uid},
            data={"phrase_id": "pr-XX-0000"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert r.status_code == 404
