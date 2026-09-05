"""Tests de las rutas de grammar (V3.12).

Cubre el motor compartido quiz parametrizado con la skill grammar (pool desde
checks del currículo, estados por check, puerta de ruta honesta con checkpoint
adaptado a bancos cortos, modos all/failed/mastered), el repositorio, el dominio
determinista y los endpoints.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from domain import grammar_routes as grammar_domain
from domain.grammar_routes import SKILL, is_valid_level
from main import app
from repositories import db
from repositories import grammar_routes as grammar_repo
from repositories import users as users_repo
from services import quiz_routes as engine
from services.curriculum import load_all_levels


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _curriculum_check_ids(level: str) -> set[str]:
    """Ids de los ítems de grammar del currículo oficial para un nivel.

    Incluye los checks MC de los objetivos y los ítems de producción controlada
    de nivel (`production_checks`, V3.13 P1): ambos forman el banco de la ruta.
    """
    ids: set[str] = set()
    for lv in load_all_levels():
        if lv.level != level:
            continue
        for obj in lv.objectives():
            for check in obj.checks:
                if check.skill == SKILL:
                    ids.add(check.id)
        for check in lv.production_checks:
            ids.add(check.id)
    return ids


# --- Motor: pool desde el currículo -------------------------------------------


def test_pool_matches_curriculum_checks():
    for level in engine.LEVEL_ORDER:
        pool = engine.checks_for_level(SKILL, level)
        assert pool, f"nivel {level} sin ítems de grammar"
        assert {c["check_id"] for c in pool} == _curriculum_check_ids(level)
        for item in pool:
            assert item["level"] == level
            assert item["topic"], f"topic vacío en {item['check_id']}"
            assert item["prompt"], f"prompt vacío en {item['check_id']}"
            if item["type"] == "mcq":
                assert len(item["options"]) >= 2
                assert 0 <= item["correct_index"] < len(item["options"])
                assert not item["accepted_answers"]
            elif item["type"] == "controlled_production":
                # Producción controlada (V3.13 P1): sin opciones MC y con, al
                # menos, una respuesta aceptada para la corrección por texto.
                assert not item["options"]
                assert "correct_index" not in item
                assert item["accepted_answers"]
            else:
                raise AssertionError(f"tipo inesperado: {item['type']}")


def test_pool_is_segregated_by_skill():
    vocab_ids = {c["check_id"] for c in engine.quiz_checks("vocabulary")}
    grammar_ids = {c["check_id"] for c in engine.quiz_checks("grammar")}
    assert vocab_ids and grammar_ids
    assert vocab_ids.isdisjoint(grammar_ids)


# --- Motor: estados y modos ---------------------------------------------------


def test_level_items_states():
    first = engine.checks_for_level(SKILL, "A1")[0]
    rows = [
        {"check_id": first["check_id"], "passed": True},
        {"check_id": first["check_id"], "passed": False},
    ]
    items = engine.level_items(SKILL, "A1", rows)
    by_id = {i["check_id"]: i for i in items}
    assert by_id[first["check_id"]]["state"] == "mastered"
    assert by_id[first["check_id"]]["prompt"] == first["prompt"]
    assert by_id[first["check_id"]]["attempts"] == 2
    total = len(engine.checks_for_level(SKILL, "A1"))
    assert sum(i["state"] == "unseen" for i in items) == total - 1


def test_review_next_modes_all_failed_mastered():
    a1 = engine.checks_for_level(SKILL, "A1")
    first, second = a1[0], a1[1]
    rows = [
        {"check_id": first["check_id"], "passed": False},
        {"check_id": second["check_id"], "passed": True},
    ]
    got = engine.review_next_question(SKILL, "A1", rows)
    assert got["check_id"] != first["check_id"]
    assert got["check_id"] != second["check_id"]
    got = engine.review_next_question(SKILL, "A1", rows, only_failed=True)
    assert got["check_id"] == first["check_id"]
    got = engine.review_next_question(SKILL, "A1", rows, only_mastered=True)
    assert got["check_id"] == second["check_id"]


def test_review_next_only_failed_raises_when_empty():
    a1 = engine.checks_for_level(SKILL, "A1")
    rows = [{"check_id": c["check_id"], "passed": True} for c in a1]
    with pytest.raises(ValueError):
        engine.review_next_question(SKILL, "A1", rows, only_failed=True)


def test_current_level_advances_by_coverage():
    a1 = engine.checks_for_level(SKILL, "A1")
    rows_a1 = [{"check_id": c["check_id"], "passed": True} for c in a1]
    # Nivel del material: primer nivel cuyo banco no está dominado (V3.13).
    assert engine.current_level(SKILL, rows_a1) == "A2"
    assert engine.current_level(SKILL, []) == "A1"


def test_current_level_all_mastered_picks_due_review_level():
    """Con todos los bancos dominados, la sugerencia de material elige el nivel
    con el repaso más pendiente (intento más antiguo), no el último fijo."""
    all_rows: list[dict] = []
    for level in engine.LEVEL_ORDER:
        for c in engine.checks_for_level(SKILL, level):
            all_rows.append({"check_id": c["check_id"], "passed": True})
    # Último intento: C2 (más reciente) ⇒ el repaso más pendiente es A1.
    assert engine.current_level(SKILL, all_rows) == "A1"
    # Si el último intento global es A1 ⇒ el repaso más pendiente es A2.
    a1_ids = [c["check_id"] for c in engine.checks_for_level(SKILL, "A1")]
    rows = [r for r in all_rows if r["check_id"] not in set(a1_ids)]
    rows += [
        {"check_id": cid, "passed": True}
        for cid in a1_ids
    ]
    assert engine.current_level(SKILL, rows) == "A2"


# --- Puerta de ruta -----------------------------------------------------------


def test_route_gate_passes_when_bank_mastered_clean():
    a1 = engine.checks_for_level(SKILL, "A1")
    rows = [
        {"check_id": c["check_id"], "passed": True}
        for c in a1
    ]
    gate = engine.route_gate(SKILL, "A1", rows)
    assert gate["passed"] is True
    assert gate["blockers"] == []


def test_route_gate_needs_accuracy_and_checkpoint():
    a1 = engine.checks_for_level(SKILL, "A1")
    rows = []
    for i, c in enumerate(a1):
        rows.append({"check_id": c["check_id"], "passed": True})
        if i % 2 == 0:
            rows.append({"check_id": c["check_id"], "passed": False})
    gate = engine.route_gate(SKILL, "A1", rows)
    assert gate["passed"] is False
    assert "accuracy" in gate["blockers"]


def test_route_gate_flags_short_banks():
    """Los bancos cortos de grammar (C2 = 4) marcan short_bank y adaptan el
    checkpoint para no pedir '3 a la primera' sobre un banco diminuto. El gate
    interno sigue midiendo práctica (pasa al dominar el banco), pero el claim
    pedagógico queda en evidence depth LOW (R7)."""
    for level in ("C2",):
        bank = engine.checks_for_level(SKILL, level)
        assert bank and len(bank) < engine.QUIZ_SHORT_BANK
        gate = engine.route_gate(SKILL, level, [])
        assert gate["short_bank"] is True
        # Con todo dominado limpio, el gate pasa aunque el banco sea corto.
        rows = [{"check_id": c["check_id"], "passed": True} for c in bank]
        gate = engine.route_gate(SKILL, level, rows)
        assert gate["passed"] is True
        assert 1 <= gate["checkpoint_required"] <= len(bank)
        assert gate["practice_depth"] == "low"
    # Un banco normal (A1 = 38) no se marca como corto.
    assert engine.route_gate(SKILL, "A1", [])["short_bank"] is False
    # B2 dejó de ser banco corto con la producción controlada de V3.13 P1:
    # sus 8 checks MC + 6 ítems CP superan QUIZ_SHORT_BANK (12), así que la
    # puerta se normaliza y deja de marcar short_bank.
    b2 = engine.checks_for_level(SKILL, "B2")
    assert len(b2) >= engine.QUIZ_SHORT_BANK
    assert engine.route_gate(SKILL, "B2", [])["short_bank"] is False
    rows = [{"check_id": c["check_id"], "passed": True} for c in b2]
    gate = engine.route_gate(SKILL, "B2", rows)
    assert gate["passed"] is True
    assert gate["practice_depth"] == "medium"


def test_short_bank_practice_depth_low_but_never_proof_of_level():
    """R7: dominar 4 checks C2 es práctica con evidencia LOW, nunca competencia
    demostrada. La ruta declara functional (techo de práctica) sin certificar."""
    c2 = engine.checks_for_level(SKILL, "C2")
    rows = [{"check_id": c["check_id"], "passed": True} for c in c2]
    gate = engine.route_gate(SKILL, "C2", rows)
    assert gate["passed"] is True
    assert gate["practice_depth"] == "low"
    comp = {
        c["level"]: c["state"]
        for c in engine.route_competence(SKILL, rows)
    }
    assert comp["C2"] == "functional"
    assert "demonstrated" not in set(comp.values())


def test_route_competence_never_demonstrated(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    a1 = engine.checks_for_level(SKILL, "A1")
    for c in a1:
        grammar_repo.record_attempt(uid, c["check_id"], "A1", 100.0, True, c["topic"])
    rows = grammar_repo.list_attempts(uid)
    comp = engine.route_competence(SKILL, rows)
    states = {c["level"]: c["state"] for c in comp}
    assert states["A1"] == "functional"  # techo de práctica, nunca certifica
    assert "demonstrated" not in set(states.values())


# --- Repositorio --------------------------------------------------------------


def test_record_attempt_and_passed_ids(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    c = engine.checks_for_level(SKILL, "A1")[0]
    assert grammar_repo.record_attempt(uid, c["check_id"], "A1", 100.0, True)
    assert grammar_repo.record_attempt(uid, c["check_id"], "A1", 0.0, False)
    assert grammar_repo.passed_check_ids(uid) == {c["check_id"]}
    rows = grammar_repo.list_attempts(uid)
    assert len(rows) == 2
    assert rows[0]["check_id"] == c["check_id"]
    assert rows[0]["score"] == 100.0


# --- Dominio: intento determinista --------------------------------------------


def test_submit_attempt_correct_and_wrong(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    c = engine.checks_for_level(SKILL, "A1")[0]
    ok = asyncio.run(
        grammar_domain.submit_attempt(uid, c["check_id"], c["correct_index"])
    )
    assert ok is not None
    assert ok["passed"] is True
    assert ok["score"] == 100.0
    wrong = asyncio.run(
        grammar_domain.submit_attempt(
            uid, c["check_id"], (c["correct_index"] + 1) % len(c["options"])
        )
    )
    assert wrong is not None
    assert wrong["passed"] is False
    assert wrong["score"] == 0.0
    assert wrong["correct_index"] == c["correct_index"]
    rows = grammar_repo.list_attempts(uid)
    assert len(rows) == 2


def test_submit_attempt_bad_option_raises(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    c = engine.checks_for_level(SKILL, "A1")[0]
    with pytest.raises(ValueError) as err:
        asyncio.run(grammar_domain.submit_attempt(uid, c["check_id"], 999))
    assert str(err.value) == "grammar.bad_option"


def test_submit_attempt_unknown_check_returns_none(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert asyncio.run(grammar_domain.submit_attempt(uid, "no-existe", 0)) is None


def test_domain_remaps_no_failed_to_grammar_namespace(monkeypatch, tmp_path):
    """El motor compartido lanza `vocabulary.no_failed`; el dominio de grammar lo
    remapea a su propio namespace para el router."""
    uid = _setup(monkeypatch, tmp_path)
    a1 = engine.checks_for_level(SKILL, "A1")
    for c in a1:
        grammar_repo.record_attempt(uid, c["check_id"], "A1", 100.0, True, c["topic"])
    with pytest.raises(ValueError) as err:
        asyncio.run(grammar_domain.next_question(uid, level="A1", mode="failed"))
    assert str(err.value) == "grammar.no_failed"


# --- Endpoints ----------------------------------------------------------------


def test_question_endpoint_never_leaks_correct_index(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/grammar/routes/question", params={"user_id": uid}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["check_id"].startswith("a1-")
        assert body["prompt"]
        assert len(body["options"]) >= 2
        assert "correct_index" not in body  # la respuesta se oculta hasta POST
        failed = client.get(
            "/api/grammar/routes/question",
            params={"user_id": uid, "mode": "failed"},
        )
        assert failed.status_code == 404
        assert failed.json()["detail"] == "grammar.no_failed"


def test_question_endpoint_respects_level_and_validation(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/grammar/routes/question",
            params={"user_id": uid, "level": "B2", "mode": "mastered"},
        )
        assert r.status_code == 404  # nada dominado aún
        bad = client.get(
            "/api/grammar/routes/question",
            params={"user_id": uid, "level": "Z9"},
        )
        assert bad.status_code == 400


def test_stats_endpoint_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/grammar/routes/stats", params={"user_id": uid}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["attempts"] == 0
        assert body["level"] == "A1"
        assert len(body["levels"]) == len(engine.LEVEL_ORDER)
        assert body["levels"][0]["level"] == "A1"
        assert body["levels"][0]["total"] == len(
            engine.checks_for_level(SKILL, "A1")
        )
        assert body["levels"][0]["bank_size"] == body["levels"][0]["total"]
        assert body["levels"][0]["evidence_depth"] == "low"


def test_level_items_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/grammar/routes/items",
            params={"user_id": uid, "level": "A2"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["level"] == "A2"
        assert body["total"] == len(engine.checks_for_level(SKILL, "A2"))
        assert body["failed"] == 0 and body["mastered"] == 0
        assert body["completed"] is False
        assert body["gate"]["short_bank"] is False


def test_level_items_endpoint_flags_short_bank(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/grammar/routes/items",
            params={"user_id": uid, "level": "C2"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["gate"]["short_bank"] is True


def test_attempt_endpoint_scores_and_reveals_answer(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    c = engine.checks_for_level(SKILL, "A1")[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/grammar/routes/attempt",
            params={"user_id": uid},
            json={"check_id": c["check_id"], "selected_index": c["correct_index"]},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["check_id"] == c["check_id"]
        assert body["level"] == "A1"
        assert body["passed"] is True
        assert body["correct_index"] == c["correct_index"]
        assert body["options"] == c["options"]
        assert body["prompt"] == c["prompt"]
        assert grammar_repo.list_attempts(uid)  # el intento se persistió


def test_attempt_endpoint_bad_option_is_400(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    c = engine.checks_for_level(SKILL, "A1")[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/grammar/routes/attempt",
            params={"user_id": uid},
            json={"check_id": c["check_id"], "selected_index": 999},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "grammar.bad_option"


def test_attempt_endpoint_unknown_check_is_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/grammar/routes/attempt",
            params={"user_id": uid},
            json={"check_id": "no-existe", "selected_index": 0},
        )
        assert r.status_code == 404


def test_production_pool_items_present_in_a2_to_c1():
    """Producción controlada (V3.13 P1): cada nivel A2–C1 aporta ítems CP al
    banco de grammar; C2 no (sigue siendo 4 MC, banco corto honesto)."""
    for level in ("A2", "B1", "B2", "C1"):
        pool = engine.checks_for_level(SKILL, level)
        cps = [c for c in pool if c.get("type") == "controlled_production"]
        assert 6 <= len(cps) <= 10, f"{level}: {len(cps)} CP"
        for c in cps:
            assert c["accepted_answers"], c["check_id"]
            assert not c["options"]
    assert all(
        c.get("type") == "mcq"
        for c in engine.checks_for_level(SKILL, "C2")
    )


def test_submit_controlled_production_correct_and_wrong(monkeypatch, tmp_path):
    """Un ítem CP se puntúa por normalización determinista (sin LLM): variantes
    de mayúsculas/espacios aciertan; el feedback revela las respuestas esperadas
    y el intento se persiste igual que un MC."""
    uid = _setup(monkeypatch, tmp_path)
    cp = next(
        c for c in engine.checks_for_level(SKILL, "B2")
        if c.get("type") == "controlled_production"
    )
    ok = asyncio.run(
        grammar_domain.submit_attempt(uid, cp["check_id"], typed_answer=" although ")
    )
    assert ok is not None
    assert ok["type"] == "controlled_production"
    assert ok["passed"] is True
    assert ok["score"] == 100.0
    assert ok["selected_index"] == -1
    assert ok["correct_index"] == -1
    assert ok["expected_answers"] == cp["accepted_answers"]
    wrong = asyncio.run(
        grammar_domain.submit_attempt(uid, cp["check_id"], typed_answer="because")
    )
    assert wrong is not None
    assert wrong["passed"] is False
    assert wrong["score"] == 0.0
    rows = grammar_repo.list_attempts(uid)
    assert len(rows) == 2
    assert rows[0]["check_id"] == cp["check_id"]


def test_submit_controlled_production_requires_typed_answer(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    cp = next(
        c for c in engine.checks_for_level(SKILL, "B2")
        if c.get("type") == "controlled_production"
    )
    with pytest.raises(ValueError) as err:
        asyncio.run(
            grammar_domain.submit_attempt(uid, cp["check_id"], typed_answer="   ")
        )
    assert str(err.value) == "grammar.typed_answer_required"


def test_question_endpoint_serves_controlled_production_without_answers(
    monkeypatch, tmp_path,
):
    """La pregunta de un ítem CP expone `type` y un prompt con hueco, pero NUNCA
    filtra `accepted_answers` ni `correct_index` (sería hacer trampa)."""
    uid = _setup(monkeypatch, tmp_path)
    cp = next(
        c for c in engine.checks_for_level(SKILL, "B2")
        if c.get("type") == "controlled_production"
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/grammar/routes/question",
            params={"user_id": uid, "level": "B2"},
        )
        # La ruta sirve el pool completo (MC + CP): localizamos un CP con una
        # rotación que recorre el banco de B2 (LRU), así que forzamos recorrer
        # preguntando hasta encontrarlo.
        found = None
        seen = 0
        while seen < len(engine.checks_for_level(SKILL, "B2")):
            q = client.get(
                "/api/grammar/routes/question",
                params={"user_id": uid, "level": "B2"},
            ).json()
            if q["type"] == "controlled_production":
                found = q
                break
            # La LRU devuelve siempre el mismo no intentado: marcamos visto
            # persistiendo un intento fallido MC para avanzar el anillo.
            client.post(
                "/api/grammar/routes/attempt",
                params={"user_id": uid},
                json={"check_id": q["check_id"], "selected_index": 0},
            )
            seen += 1
        assert found is not None, "no se sirvió ningún ítem CP en B2"
        assert found["options"] == []
        assert "accepted_answers" not in found
        assert "correct_index" not in found
