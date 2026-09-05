"""Tests del registro cross-skill por estructura (V3.13 P1.2 → v3.14 A1–C2).

Verifica que el registro es derivado del currículo (normativo) en los seis
niveles A1–C2: las estructuras son los objetivos con checks MC de grammar, el
binding de producción controlada resuelve a objetivos reales con checks MC de
grammar sin dejar CP huérfanos, y la matriz distingue instrumento ofrecido
(`offered`) de evidencia real del usuario (`evidence`). También cubre el
endpoint de solo lectura.
"""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import cross_skill
from services.curriculum import load_level

ALL_LEVELS = list(cross_skill.CROSS_SKILL_LEVELS)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _grammar_structure_ids(level_id: str) -> set[str]:
    """Objetivos del nivel con ≥1 check MC de grammar (anclas del registro)."""
    level = load_level(level_id)
    return {
        o.id
        for o in level.objectives()
        if any(c.skill == "grammar" for c in o.checks)
    }


# --- Registro: normativo y derivado del currículo en los seis niveles ---------


def test_registry_covers_every_grammar_structure_per_level():
    for level_id in ALL_LEVELS:
        rows = cross_skill.structure_registry(level_id)
        assert {r["structure_id"] for r in rows} == _grammar_structure_ids(level_id)
        assert rows == sorted(rows, key=lambda r: r["structure_id"])
        # Todo el registro ofrece reconocimiento (checks MC de grammar).
        assert all(r["channels"]["recognition"]["offered"] for r in rows)


def test_registry_exposes_instruments_where_the_curriculum_has_them():
    """`listening`/`speaking` se ofrecen exactamente donde hay wiring (V2.5-C4)."""
    for level_id in ALL_LEVELS:
        level = load_level(level_id)
        by_id = {o.id: o for o in level.objectives()}
        for row in cross_skill.structure_registry(level_id):
            obj = by_id[row["structure_id"]]
            assert row["channels"]["listening"]["offered"] is bool(obj.listening_items)
            assert row["channels"]["speaking"]["offered"] is bool(obj.scenario_ids)


def test_registry_of_unknown_level_is_empty():
    assert cross_skill.structure_registry("zz") == []


def test_production_bindings_are_normative_per_level():
    """Cada CP del currículo queda atribuido a una estructura grammar real."""
    for level_id in ALL_LEVELS:
        level = load_level(level_id)
        level_cp_ids = {c.id for c in level.production_checks}
        rows = {r["structure_id"] for r in cross_skill.structure_registry(level_id)}
        bindings = cross_skill._production_bindings_for(level_id)
        # Sin CP huérfanos: todo ítem del banco está enlazado a una estructura.
        assert set(bindings) == level_cp_ids, f"{level_id}: CP huérfano en el binding"
        # Cada binding apunta a un objetivo con checks MC de grammar.
        for cp_id, obj_id in bindings.items():
            assert cp_id in level_cp_ids, f"{level_id}: {cp_id} no existe"
            assert obj_id in rows, f"{level_id}: {obj_id} (de {cp_id}) no es estructura"
            obj = next(o for o in level.objectives() if o.id == obj_id)
            assert any(c.skill == "grammar" for c in obj.checks)
        # Toda estructura con CP binding ofrece producción en el registro.
        bound_objects = set(bindings.values())
        registry = {
            r["structure_id"]: r for r in cross_skill.structure_registry(level_id)
        }
        for obj_id in bound_objects:
            assert registry[obj_id]["channels"]["production"]["offered"] is True


def test_a1_and_c2_have_production_bound_to_structures():
    """A1/C2 ya tienen producción controlada enlazada (no quedan sin canal)."""
    for level_id in ("a1", "c2"):
        bindings = cross_skill._production_bindings_for(level_id)
        assert len(bindings) >= 3, f"{level_id}: producción controlada insuficiente"
        rows = {r["structure_id"]: r for r in cross_skill.structure_registry(level_id)}
        for obj_id in set(bindings.values()):
            assert rows[obj_id]["channels"]["production"]["offered"] is True


# --- Matriz: instrumento vs evidencia ----------------------------------------


def test_matrix_counts_recognition_by_objective():
    rows = cross_skill.structure_registry("a2")
    assert any(r["structure_id"] == "a2-m01-u01-l01-o01" for r in rows)
    evidence = [
        {"objective_id": "a2-m01-u01-l01-o01", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "familiar", "result": 1.0},
        {"objective_id": "a2-m01-u01-l01-o01", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "transfer", "result": 1.0},
        {"objective_id": "a2-m01-u01-l01-o01", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "familiar", "result": 0.0},  # fallo no cuenta
        {"objective_id": "a2-m01-u01-l01-o02", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "familiar", "result": 1.0},  # otra estructura
    ]
    matrix = cross_skill.cross_skill_matrix("a2", evidence_rows=evidence)
    out = {s["structure_id"]: s for s in matrix["structures"]}
    assert out["a2-m01-u01-l01-o01"]["channels"]["recognition"]["evidence"] == 2
    assert out["a2-m01-u01-l01-o01"]["channels"]["transfer"]["evidence"] == 1


def test_matrix_counts_listening_and_speaking_by_objective():
    """La evidencia de listening/speaking del objetivo alimenta su canal."""
    rows = cross_skill.structure_registry("b1")
    # Estructura de la conversación final B1 con listening y speaking ofrecidos.
    target = next(r for r in rows if r["structure_id"] == "b1-m04-u01-l01-o10")
    assert target["channels"]["listening"]["offered"] is True
    evidence = [
        {"objective_id": "b1-m04-u01-l01-o10", "skill": "listening",
         "item_type": "check", "evidence_kind": "familiar", "result": 1.0},
        {"objective_id": "b1-m04-u01-l01-o10", "skill": "speaking",
         "item_type": "open", "evidence_kind": "familiar", "result": 1.0},
    ]
    matrix = cross_skill.cross_skill_matrix("b1", evidence_rows=evidence)
    out = {s["structure_id"]: s for s in matrix["structures"]}
    assert out["b1-m04-u01-l01-o10"]["channels"]["listening"]["evidence"] == 1
    assert out["b1-m04-u01-l01-o10"]["channels"]["speaking"]["evidence"] == 1


def test_matrix_production_uses_passed_bound_cp_ids():
    matrix = cross_skill.cross_skill_matrix(
        "a2",
        evidence_rows=[],
        production_passed_ids={"a2-cp-01", "a2-cp-03", "no-existe"},
    )
    out = {s["structure_id"]: s for s in matrix["structures"]}
    assert out["a2-m01-u01-l01-o01"]["channels"]["production"]["evidence"] == 1
    assert out["a2-m01-u01-l01-o01"]["channels"]["production"]["offered"] is True
    assert out["a2-m02-u01-l01-o01"]["channels"]["production"]["evidence"] == 1
    # Estructura con checks MC de grammar pero sin ítem CP: producción no ofrecida.
    assert out["a2-m05-u01-l01-o01"]["channels"]["production"]["offered"] is False


def test_matrix_production_counts_items_not_rows_for_multi_cp_structures():
    """Una estructura con dos CP (p. ej. C1 o04) cuenta CP superados, no filas."""
    matrix = cross_skill.cross_skill_matrix(
        "c1",
        evidence_rows=[],
        production_passed_ids={"c1-cp-01", "c1-cp-03", "c1-cp-05"},
    )
    out = {s["structure_id"]: s for s in matrix["structures"]}
    # c1-m01-u01-l01-o01 (cp-01) y c1-m01-u01-l01-o04 (cp-03) tienen 1 cada uno.
    assert out["c1-m01-u01-l01-o01"]["channels"]["production"]["evidence"] == 1
    assert out["c1-m01-u01-l01-o04"]["channels"]["production"]["evidence"] == 1
    # c1-m03-u01-l01-o04 agrupa cp-05 y cp-06: 1 superado de 2 posibles.
    assert out["c1-m03-u01-l01-o04"]["channels"]["production"]["offered"] is True
    assert out["c1-m03-u01-l01-o04"]["channels"]["production"]["evidence"] == 1


def test_matrix_empty_user_shows_instruments_offered_but_no_evidence():
    for level_id in ("a1", "b1", "c2"):
        matrix = cross_skill.cross_skill_matrix(
            level_id, evidence_rows=[], production_passed_ids=set()
        )
        assert matrix["level_id"] == level_id
        assert "proto" not in matrix
        for structure in matrix["structures"]:
            for cell in structure["channels"].values():
                assert cell["evidence"] == 0


# --- Endpoint (solo lectura) --------------------------------------------------


def test_endpoint_returns_matrix_for_every_level_read_only(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    from repositories import grammar_routes as grammar_repo

    with TestClient(app) as client:
        for level_id in ALL_LEVELS:
            r = client.get(
                "/api/cross-skill", params={"user_id": uid, "level": level_id}
            )
            assert r.status_code == 200, level_id
            body = r.json()
            assert body["level_id"] == level_id
            assert body["level"] == level_id.upper()
            assert {s["structure_id"] for s in body["structures"]} == (
                _grammar_structure_ids(level_id)
            )
            for structure in body["structures"]:
                assert set(structure["channels"]) == set(cross_skill.CHANNELS)
        # Ninguna petición GET escribe: sin intentos nuevos de grammar.
        attempts = grammar_repo.list_attempts(uid)
        assert attempts == []


def test_endpoint_rejects_unknown_level(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/cross-skill", params={"user_id": uid, "level": "zz"})
        assert r.status_code == 400
        assert "level_unknown" in r.json()["detail"]
