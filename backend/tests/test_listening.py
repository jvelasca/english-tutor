"""Tests de listening: banco, puntuación, dominio, repositorio y endpoints."""
import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import (
    LEVEL_ORDER,
    LISTENING_SUBSKILLS,
    QUESTION_BANK,
    accuracy_by_difficulty,
    accuracy_by_topic,
    current_level,
    difficulty_from_vector,
    get_question,
    level_items,
    level_status,
    listening_diagnostic,
    pick_next_question,
    questions_for_level,
    recent_trend,
    recurrence_stats,
    review_next_question,
    route_competence,
    score_answer,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_score_answer_correct():
    assert score_answer(1, 1) is True


def test_score_answer_incorrect():
    assert score_answer(0, 1) is False


def test_get_question_found():
    q = get_question(QUESTION_BANK[0]["id"])
    assert q is not None
    assert q["script"]


def test_get_question_missing():
    assert get_question("nope") is None


def test_pick_next_starts_at_a1():
    assert pick_next_question(set())["id"] == QUESTION_BANK[0]["id"]


def test_pick_next_serves_unseen_before_retrying():
    # l1 visto pero no dominado: se sirve la siguiente no vista (l2) antes de
    # reintentar l1, de modo que el usuario recorre el nivel sin atascarse.
    assert pick_next_question({"l1"}, set())["id"] == "l2"


def test_pick_next_retries_wrong_after_unseen_exhausted():
    # Con todo el nivel visto y solo l3 sin dominar, se reintenta la fallada tras
    # agotar las no vistas.
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    assert pick_next_question(a1_ids, a1_ids - {"l3"})["id"] == "l3"


def test_pick_next_advances_when_level_mastered():
    # A1 completo → siguiente pregunta es de A2 (l4).
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    assert pick_next_question(set(), a1_ids)["id"] == "l4"


def test_pick_next_completes_all_levels_and_rotates():
    # Todo dominado: rota sobre el banco en lugar de quedarse atascado.
    all_ids = {q["id"] for q in QUESTION_BANK}
    assert pick_next_question(set(), all_ids)["id"] == QUESTION_BANK[0]["id"]


def test_review_next_serves_never_attempted_first():
    # En repaso, una frase nunca intentada en el nivel se sirve antes que las
    # ya practicadas (es la menos practicada).
    a1 = questions_for_level("A1")
    reviewed = a1[0]["id"]
    attempts = [{"question_id": reviewed}]
    got = review_next_question("A1", attempts)
    assert got["id"] != reviewed
    assert got["id"] in {q["id"] for q in a1}


def test_review_next_rotates_by_oldest_attempt():
    a1 = questions_for_level("A1")
    ids = [q["id"] for q in a1]
    # Una vuelta completa: cada frase intentada una vez, en orden.
    attempts = [{"question_id": qid} for qid in ids]
    assert review_next_question("A1", attempts)["id"] == ids[0]
    # Tras "responderla", su intento pasa a ser el más reciente: la siguiente
    # es la que ahora tiene el intento más antiguo.
    attempts.append({"question_id": ids[0]})
    assert review_next_question("A1", attempts)["id"] == ids[1]


def test_review_question_endpoint_filters_by_level(monkeypatch, tmp_path):
    """`GET /api/listening/question?level=...` sirve solo frases de ese nivel."""
    uid = _setup(monkeypatch, tmp_path)
    a1 = questions_for_level("A1")
    a2 = questions_for_level("A2")
    with TestClient(app) as client:
        for q in a1:
            r = client.post(
                "/api/listening/answer",
                params={"user_id": uid},
                json={"question_id": q["id"], "answer_index": q["answer_index"]},
            )
            assert r.status_code == 200
        r = client.get(
            "/api/listening/question", params={"user_id": uid, "level": "A1"}
        )
        body = r.json()
        # A1 ya está dominado: el repaso rota dentro de A1 (no salta a A2).
        assert body["level"] == "A1"
        assert body["id"] in {q["id"] for q in a1}

        bad = client.get(
            "/api/listening/question", params={"user_id": uid, "level": "XX"}
        )
        assert bad.status_code == 400

        # Sin `level`, la progresión normal avanza a A2.
        nxt = client.get("/api/listening/question", params={"user_id": uid}).json()
        assert nxt["level"] == "A2"
        assert nxt["id"] in {q["id"] for q in a2}


def test_current_level_advances_with_mastery():
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    a2_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A2"}
    b1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "B1"}
    b2_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "B2"}
    c1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "C1"}
    assert current_level(set()) == "A1"
    assert current_level(a1_ids) == "A2"
    assert current_level(a1_ids | a2_ids) == "B1"
    assert current_level(a1_ids | a2_ids | b1_ids) == "B2"
    assert current_level(a1_ids | a2_ids | b1_ids | b2_ids) == "C1"
    assert current_level(a1_ids | a2_ids | b1_ids | b2_ids | c1_ids) == "C2"
    # Completados todos → se mantiene en el último nivel para seguir practicando.
    assert current_level({q["id"] for q in QUESTION_BANK}) == "C2"


def test_level_status_marks_completed():
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    # Todo el banco A1 acertado a la primera y sin replays: cobertura, precisión,
    # variedad y checkpoint cumplidos → la ruta queda certificada.
    rows = [{"question_id": qid, "correct": True, "replay_count": 0} for qid in a1_ids]
    status = level_status(rows)
    by_level = {s["level"]: s for s in status}
    assert [s["level"] for s in status] == LEVEL_ORDER
    assert by_level["A1"]["completed"] is True
    assert by_level["A1"]["mastered"] == by_level["A1"]["total"]
    assert by_level["A1"]["gate"]["passed"] is True
    assert by_level["A1"]["gate"]["blockers"] == []
    assert by_level["A2"]["completed"] is False
    assert by_level["A2"]["gate"]["passed"] is False


def test_level_status_full_coverage_low_accuracy_not_certified():
    """Dominar todos los ítems tras fallarlos una vez deja precisión < 70 %:
    la cobertura está completa pero la ruta no se certifica."""
    a1 = questions_for_level("A1")
    rows = []
    for q in a1:
        rows.append({"question_id": q["id"], "correct": False, "replay_count": 0})
        rows.append({"question_id": q["id"], "correct": True, "replay_count": 1})
    status = level_status(rows)
    by_level = {s["level"]: s for s in status}
    entry = by_level["A1"]
    assert entry["mastered"] == entry["total"]  # cobertura completa
    assert entry["completed"] is False  # pero la puerta no se abre
    assert entry["gate"]["accuracy"] is not None
    assert entry["gate"]["accuracy"] < entry["gate"]["accuracy_required"]
    assert "accuracy" in entry["gate"]["blockers"]


def test_level_status_checkpoint_needs_clean_first_try():
    """El checkpoint exige aciertos a la primera sin replays: dominar el banco con
    un replay en cada primera exposición no aporta ni un ítem al checkpoint."""
    a1 = questions_for_level("A1")
    rows = [{"question_id": q["id"], "correct": True, "replay_count": 1} for q in a1]
    gate = next(
        s["gate"] for s in level_status(rows) if s["level"] == "A1"
    )
    assert gate["checkpoint"] == 0
    assert gate["checkpoint_required"] > 0
    assert gate["passed"] is False
    assert gate["blockers"] == ["checkpoint"]


def test_level_status_checkpoint_met_with_clean_majority():
    """Con cobertura y precisión altas basta un puñado de aciertos a la primera
    (≥ checkpoint_required) para que la ruta se certifique aunque el resto se
    dominase con replays."""
    a1 = questions_for_level("A1")
    rows = []
    for i, q in enumerate(a1):
        clean = i % 2 == 0
        rows.append(
            {
                "question_id": q["id"],
                "correct": True,
                "replay_count": 0 if clean else 1,
            }
        )
    entry = next(s for s in level_status(rows) if s["level"] == "A1")
    assert entry["mastered"] == entry["total"]
    assert entry["completed"] is True
    assert entry["gate"]["passed"] is True
    assert entry["gate"]["checkpoint"] >= entry["gate"]["checkpoint_required"]


def test_bank_shape_valid():
    assert len(QUESTION_BANK) >= 3
    for q in QUESTION_BANK:
        assert q["id"]
        assert q["script"]
        assert q["question"]
        assert len(q["options"]) >= 2
        assert 0 <= q["answer_index"] < len(q["options"])
        assert q["skill"] in LISTENING_SUBSKILLS
        assert 1 <= difficulty_from_vector(q["difficulty_vector"]) <= 6
    from collections import Counter

    skill_counts = Counter(q["skill"] for q in QUESTION_BANK)
    assert skill_counts["gist"] >= 2
    assert skill_counts["vocabulary"] >= 2


def test_next_question_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/question", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["script"]
    assert body["question"]
    assert isinstance(body["options"], list) and len(body["options"]) >= 2
    assert "answer_index" not in body


def test_answer_correct(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["correct_index"] == q["answer_index"]


def test_answer_wrong(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    wrong = (q["answer_index"] + 1) % len(q["options"])
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": wrong},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is False


def test_answer_unknown_question_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": "nope", "answer_index": 0},
        )
    assert r.status_code == 404


def test_answer_unknown_user_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": "no-existe"},
            json={"question_id": q["id"], "answer_index": 0},
        )
    assert r.status_code == 404


def test_stats_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/stats", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 1
    assert body["correct"] == 1
    assert body["accuracy"] == 100.0
    assert body["level"] == "A1"
    assert body["completed"] is False
    assert [lv["level"] for lv in body["levels"]] == LEVEL_ORDER


def test_progression_advances_levels_via_api(monkeypatch, tmp_path):
    """Responder correctamente todas las preguntas de un nivel avanza al siguiente.

    Regresión del bug donde la práctica de listening se quedaba atascada (bucle)
    sin pasar de nivel."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for q in QUESTION_BANK:
            if q["level"] != "A1":
                continue
            r = client.post(
                "/api/listening/answer",
                params={"user_id": uid},
                json={"question_id": q["id"], "answer_index": q["answer_index"]},
            )
            assert r.status_code == 200

        nxt = client.get("/api/listening/question", params={"user_id": uid}).json()
        stats = client.get("/api/listening/stats", params={"user_id": uid}).json()

    assert nxt["level"] == "A2"  # A1 completado → avanza a A2
    assert stats["level"] == "A2"
    assert stats["levels"][0]["completed"] is True
    assert stats["levels"][1]["completed"] is False


def test_all_levels_completed_marks_completed(monkeypatch, tmp_path):
    """Responder correctamente todo el banco marca la práctica como completada."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for q in QUESTION_BANK:
            client.post(
                "/api/listening/answer",
                params={"user_id": uid},
                json={"question_id": q["id"], "answer_index": q["answer_index"]},
            )
        stats = client.get("/api/listening/stats", params={"user_id": uid}).json()
    assert stats["completed"] is True
    assert stats["level"] == "C2"
    assert all(lv["completed"] for lv in stats["levels"])


def test_listening_diagnostic_empty():
    diag = listening_diagnostic([])
    assert [s["skill"] for s in diag["subskills"]] == list(LISTENING_SUBSKILLS)
    assert all(s["attempts"] == 0 for s in diag["subskills"])
    assert all(s["accuracy"] is None for s in diag["subskills"])
    assert diag["weak"] == list(LISTENING_SUBSKILLS)
    assert diag["recommendation"].startswith("Focus on:")


def test_listening_diagnostic_groups_and_weak():
    def _row(skill, correct, rms, replay):
        return {
            "skill": skill,
            "correct": correct,
            "response_time_ms": rms,
            "replay_count": replay,
        }

    rows = [
        _row("detail", True, 1000, 0),
        _row("detail", True, 1200, 0),
        _row("detail", True, 800, 1),
        _row("numbers", False, 2000, 2),
        _row("numbers", False, 2100, 3),
        _row("numbers", False, 1900, 1),
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}

    assert by_skill["detail"]["attempts"] == 3
    assert by_skill["detail"]["correct"] == 3
    assert by_skill["detail"]["accuracy"] == 100.0
    assert by_skill["detail"]["avg_response_ms"] == 1000.0
    assert by_skill["detail"]["review_due"] is False

    assert by_skill["numbers"]["attempts"] == 3
    assert by_skill["numbers"]["correct"] == 0
    assert by_skill["numbers"]["accuracy"] == 0.0
    assert by_skill["numbers"]["avg_replay_count"] == 2.0
    assert by_skill["numbers"]["review_due"] is True

    # gist no tiene muestras → review_due True para animar a explorar.
    assert by_skill["gist"]["attempts"] == 0
    assert by_skill["gist"]["review_due"] is True

    assert "numbers" in diag["weak"]
    assert "gist" in diag["weak"]
    assert "detail" not in diag["weak"]


def test_diagnostic_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert len(body["subskills"]) >= len(LISTENING_SUBSKILLS)
    by_skill = {s["skill"]: s for s in body["subskills"]}
    assert by_skill[q["skill"]]["attempts"] == 1


def test_new_subskills_generate_independent_evidence():
    """Cada sub-destreza canónica produce su propia fila de evidencia en el
    diagnóstico, con independencia del resto (V1.13)."""
    new_subskills = [
        "fast_speech",
        "connected_speech",
        "multiple_speakers",
        "dictation",
        "shadowing",
        "speaker_intention",
    ]
    rows = [
        {
            "skill": skill,
            "correct": True,
            "response_time_ms": 1500,
            "replay_count": 0,
        }
        for skill in new_subskills
    ]
    diag = listening_diagnostic(rows)
    by_skill = {s["skill"]: s for s in diag["subskills"]}
    for skill in new_subskills:
        assert by_skill[skill]["attempts"] == 1, skill
        assert by_skill[skill]["accuracy"] == 100.0, skill
    # Las que no tienen intentos siguen listadas con 0 intentos (evidencia vacía).
    assert by_skill["gist"]["attempts"] == 0


def test_answer_records_metrics(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": q["id"],
                "answer_index": q["answer_index"],
                "response_time_ms": 1234,
                "replay_count": 2,
            },
        )
    assert r.status_code == 200
    attempts = listening_repo.list_attempts(uid)
    assert len(attempts) == 1
    row = attempts[0]
    assert row["response_time_ms"] == 1234
    assert row["replay_count"] == 2
    assert row["skill"] == q["skill"]
    assert row["topic"] == q["topic"]
    assert row["difficulty"] == difficulty_from_vector(q["difficulty_vector"])


# --- P4: competencia (tema, dificultad, tendencia, reincidencia) -------------


def _attempt(qid, correct, difficulty=2, topic="travel", rms=None, replay=0):
    return {
        "question_id": qid,
        "correct": correct,
        "difficulty": difficulty,
        "topic": topic,
        "response_time_ms": rms,
        "replay_count": replay,
    }


def test_accuracy_by_difficulty_groups_and_orders():
    rows = [
        _attempt("a", True, difficulty=3),
        _attempt("b", False, difficulty=1),
        _attempt("c", True, difficulty=3),
        _attempt("d", True, difficulty=1),
    ]
    result = accuracy_by_difficulty(rows)
    assert [r["difficulty"] for r in result] == [1, 3]
    by_d = {r["difficulty"]: r for r in result}
    assert by_d[1]["attempts"] == 2
    assert by_d[1]["correct"] == 1
    assert by_d[1]["accuracy"] == 50.0
    assert by_d[3]["accuracy"] == 100.0


def test_accuracy_by_difficulty_skips_missing():
    assert accuracy_by_difficulty([{"question_id": "a", "correct": True}]) == []


def test_accuracy_by_topic_groups_and_orders():
    rows = [
        _attempt("a", True, topic="travel"),
        _attempt("b", False, topic="food"),
        _attempt("c", True, topic="travel"),
    ]
    result = accuracy_by_topic(rows)
    assert [r["topic"] for r in result] == ["food", "travel"]
    by_t = {r["topic"]: r for r in result}
    assert by_t["food"]["accuracy"] == 0.0
    assert by_t["travel"]["accuracy"] == 100.0


def test_accuracy_by_topic_skips_empty():
    assert accuracy_by_topic([{"question_id": "a", "correct": True, "topic": ""}]) == []


def test_recent_trend_compares_windows():
    # 20 intentos: los primeros 10 mal, los últimos 10 bien. Con ventana 10, la
    # precisión reciente es 100% y la previa 0%.
    rows = [_attempt(f"q{i}", False) for i in range(10)]
    rows += [_attempt(f"r{i}", True) for i in range(10)]
    trend = recent_trend(rows, window=10)
    assert trend["recent_accuracy"] == 100.0
    assert trend["prior_accuracy"] == 0.0
    assert trend["delta"] == 100.0
    assert trend["direction"] == "up"


def test_recent_trend_no_prior_window():
    trend = recent_trend([_attempt(f"q{i}", True) for i in range(5)], window=10)
    assert trend["recent_accuracy"] == 100.0
    assert trend["prior_accuracy"] is None
    assert trend["direction"] == "n/a"


def test_recent_trend_empty():
    trend = recent_trend([])
    assert trend["direction"] == "n/a"
    assert trend["recent_accuracy"] is None


def test_recurrence_stats_measures_retries_and_recovery():
    rows = [
        _attempt("a", False),
        _attempt("a", True),
        _attempt("b", True),
        _attempt("c", False),
        _attempt("c", False),
    ]
    stats = recurrence_stats(rows)
    assert stats["questions_seen"] == 3
    assert stats["retried"] == 2
    assert stats["recovered"] == 1
    assert stats["retry_rate"] == round(2 / 3, 3)
    assert stats["recovery_rate"] == 0.5


def test_recurrence_stats_empty():
    stats = recurrence_stats([])
    assert stats["questions_seen"] == 0
    assert stats["retried"] == 0
    assert stats["recovered"] == 0
    assert stats["retry_rate"] is None
    assert stats["recovery_rate"] is None


def test_diagnostic_includes_competence_metrics():
    rows = [
        _attempt("a", True, difficulty=1, topic="travel"),
        _attempt("b", False, difficulty=3, topic="food"),
    ]
    diag = listening_diagnostic(rows)
    assert diag["by_difficulty"][0]["difficulty"] == 1
    assert diag["by_topic"][0]["topic"] == "food"
    assert diag["trend"]["direction"] == "n/a"
    assert diag["recurrence"]["questions_seen"] == 2


def test_diagnostic_endpoint_exposes_competence(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/diagnostic", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["trend"]["direction"] == "n/a"
    assert body["recurrence"]["questions_seen"] == 1
    assert any(
        d["difficulty"] == difficulty_from_vector(q["difficulty_vector"])
        for d in body["by_difficulty"]
    )
    assert any(t["topic"] == q["topic"] for t in body["by_topic"])


# --- Control del alumno por nivel: items por frase + drill de falladas --------


def test_level_items_states():
    a1 = questions_for_level("A1")
    assert len(a1) >= 3, "el banco A1 debe tener al menos 3 frases para este test"
    q0, q1, q2 = a1[0], a1[1], a1[2]
    rows = [
        {"question_id": q0["id"], "correct": False},
        {"question_id": q1["id"], "correct": True},
    ]
    items = level_items("A1", rows)
    by_id = {i["question_id"]: i for i in items}
    assert len(items) == len(a1)
    assert by_id[q0["id"]]["state"] == "failed"
    assert by_id[q0["id"]]["attempts"] == 1
    assert by_id[q1["id"]]["state"] == "mastered"
    assert by_id[q2["id"]]["state"] == "unseen"
    assert by_id[q2["id"]]["attempts"] == 0
    # Frase fallada y luego acertada pasa a mastered (no failed).
    rows.append({"question_id": q0["id"], "correct": True})
    items2 = level_items("A1", rows)
    by_id2 = {i["question_id"]: i for i in items2}
    assert by_id2[q0["id"]]["state"] == "mastered"
    assert by_id2[q0["id"]]["attempts"] == 2


def test_level_items_exposes_script_and_metadata():
    a1 = questions_for_level("A1")
    first = level_items("A1", [])[0]
    assert first["question_id"] == a1[0]["id"]
    assert first["script"]
    assert first["level"] == "A1"
    assert first["difficulty"] == difficulty_from_vector(
        a1[0]["difficulty_vector"]
    )


def test_review_next_only_failed_filters():
    a1 = questions_for_level("A1")
    ids = [q["id"] for q in a1]
    rows = [
        {"question_id": ids[0], "correct": False},
        {"question_id": ids[1], "correct": True},
    ]
    got = review_next_question("A1", rows, only_failed=True)
    assert got["id"] == ids[0]


def test_review_next_only_failed_empty_pool_raises():
    a1 = questions_for_level("A1")
    rows = [{"question_id": q["id"], "correct": True} for q in a1]
    with pytest.raises(ValueError):
        review_next_question("A1", rows, only_failed=True)


def test_level_items_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = questions_for_level("A1")
    q0 = a1[0]
    with TestClient(app) as client:
        wrong = (q0["answer_index"] + 1) % len(q0["options"])
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q0["id"], "answer_index": wrong},
        )
        r = client.get(
            "/api/listening/items", params={"user_id": uid, "level": "A1"}
        )
        bad_level = client.get(
            "/api/listening/items", params={"user_id": uid, "level": "XX"}
        )
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == "A1"
    assert body["total"] == len(a1)
    assert body["mastered"] == 0
    assert body["failed"] == 1
    assert body["unseen"] == len(a1) - 1
    assert body["completed"] is False
    item = next(i for i in body["items"] if i["question_id"] == q0["id"])
    assert item["state"] == "failed"
    assert item["attempts"] == 1
    assert item["script"]
    assert bad_level.status_code == 400


def test_drill_question_mode_failed(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = questions_for_level("A1")
    q0, q1 = a1[0], a1[1]
    with TestClient(app) as client:
        wrong0 = (q0["answer_index"] + 1) % len(q0["options"])
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q0["id"], "answer_index": wrong0},
        )
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q1["id"], "answer_index": q1["answer_index"]},
        )
        got = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "failed"},
        )
    assert got.status_code == 200
    assert got.json()["id"] == q0["id"]


def test_drill_question_mode_failed_no_failed_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = questions_for_level("A1")
    with TestClient(app) as client:
        for q in a1:
            client.post(
                "/api/listening/answer",
                params={"user_id": uid},
                json={"question_id": q["id"], "answer_index": q["answer_index"]},
            )
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "failed"},
        )
        bad = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "bogus"},
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "listening.no_failed"
    assert bad.status_code == 400


def test_route_competence_empty_all_not_started():
    """Sin intentos, toda ruta está en NOT_STARTED y sin retención estable."""
    rows = route_competence([])
    assert [r["level"] for r in rows] == LEVEL_ORDER
    assert all(r["state"] == "not_started" for r in rows)
    assert all(r["gate"]["passed"] is False for r in rows)
    assert all(r["retention"]["stable"] is False for r in rows)


def test_route_competence_full_bank_functional_but_not_demonstrated():
    """Todo el banco A1 acertado a la primera (gate superado) sin re-exposiciones
    retardadas: la ruta queda FUNCTIONAL, nunca DEMONSTRATED (falta retención)."""
    a1_ids = {q["id"] for q in QUESTION_BANK if q["level"] == "A1"}
    rows = [{"question_id": qid, "correct": True, "replay_count": 0} for qid in a1_ids]
    by_level = {r["level"]: r for r in route_competence(rows)}
    assert by_level["A1"]["state"] == "functional"
    assert by_level["A1"]["retention"]["stable"] is False
    assert by_level["A1"]["retention"]["retention_rate"] is None
