"""Tests del registro cross-skill por estructura (V3.13, P1.2).

Verifica el prototipo B1: el registro es derivado del currículo (normativo), el
binding de producción controlada resuelve a objetivos reales con checks MC de
grammar, y la matriz distingue instrumento ofrecido (`offered`) de evidencia
real del usuario (`evidence`). También cubre el endpoint de solo lectura.
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import cross_skill
from services.curriculum import load_all_levels, load_level

# Las 8 estructuras de B1 con checks MC de grammar (anclas del registro).
B1_GRAMMAR_STRUCTURES = {
    "b1-m01-u01-l01-o01",  # present perfect vs past simple
    "b1-m01-u01-l01-o02",  # yet / already
    "b1-m02-u01-l01-o05",  # will / going to / present continuous
    "b1-m02-u01-l01-o06",  # first conditional
    "b1-m02-u01-l02-o07",  # have to / must
    "b1-m03-u01-l01-o15",  # reported speech
    "b1-m04-u01-l01-o10",  # conversación final B1
    "b1-m04-u01-l01-o18",  # conversación integrada B1
}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Registro: normativo y derivado del currículo -----------------------------


def test_b1_registry_covers_every_grammar_structure():
    rows = cross_skill.structure_registry("b1")
    assert {r["structure_id"] for r in rows} == B1_GRAMMAR_STRUCTURES
    # Todo el registro ofrece reconocimiento (checks MC de grammar).
    assert all(r["channels"]["recognition"]["offered"] for r in rows)
    # La estructura final B1 expone la estructura a listening (hay listening_items).
    finales = {r["structure_id"]: r for r in rows if r["structure_id"].startswith("b1-m04")}
    for r in finales.values():
        assert r["channels"]["listening"]["offered"] is True


def test_registry_of_level_outside_proto_is_empty():
    rows = cross_skill.structure_registry("a1")
    assert rows == []


def test_binding_resolves_to_real_curriculum_objects():
    level = load_level("b1")
    level_cp_ids = {c.id for c in level.production_checks}
    rows = {r["structure_id"] for r in cross_skill.structure_registry("b1")}
    # Cada binding apunta a un objetivo con checks MC de grammar.
    for cp_id, obj_id in cross_skill.B1_PRODUCTION_BINDINGS.items():
        assert cp_id in level_cp_ids, f"{cp_id} no existe en el currículo B1"
        assert obj_id in rows, f"{obj_id} (de {cp_id}) no es estructura gramatical B1"
        obj = next(o for o in level.objectives() if o.id == obj_id)
        assert any(c.skill == "grammar" for c in obj.checks)
    # Los 6 cp del nivel quedan atribuidos (sin huérfanos).
    assert set(cross_skill.B1_PRODUCTION_BINDINGS) == level_cp_ids
    # Toda estructura con cp binding ofrece producción en el registro.
    bound_objects = set(cross_skill.B1_PRODUCTION_BINDINGS.values())
    for obj_id in bound_objects:
        row = next(r for r in cross_skill.structure_registry("b1") if r["structure_id"] == obj_id)
        assert row["channels"]["production"]["offered"] is True


# --- Matriz: instrumento vs evidencia ----------------------------------------


def test_matrix_counts_recognition_by_objective():
    rows = cross_skill.structure_registry("b1")
    target = next(r for r in rows if r["structure_id"] == "b1-m01-u01-l01-o01")
    evidence = [
        {"objective_id": "b1-m01-u01-l01-o01", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "familiar", "result": 1.0},
        {"objective_id": "b1-m01-u01-l01-o01", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "transfer", "result": 1.0},
        {"objective_id": "b1-m01-u01-l01-o01", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "familiar", "result": 0.0},  # fallo no cuenta
        {"objective_id": "b1-m01-u01-l02-o04", "skill": "grammar", "item_type": "mcq",
         "evidence_kind": "familiar", "result": 1.0},  # otra estructura
    ]
    matrix = cross_skill.cross_skill_matrix("b1", evidence_rows=evidence)
    out = {s["structure_id"]: s for s in matrix["structures"]}
    assert out["b1-m01-u01-l01-o01"]["channels"]["recognition"]["evidence"] == 2
    assert out["b1-m01-u01-l01-o01"]["channels"]["transfer"]["evidence"] == 1


def test_matrix_production_uses_passed_bound_cp_ids():
    matrix = cross_skill.cross_skill_matrix(
        "b1",
        evidence_rows=[],
        production_passed_ids={"b1-cp-01", "b1-cp-04", "no-existe"},
    )
    out = {s["structure_id"]: s for s in matrix["structures"]}
    assert out["b1-m01-u01-l01-o01"]["channels"]["production"]["evidence"] == 1
    assert out["b1-m01-u01-l01-o01"]["channels"]["production"]["offered"] is True
    assert out["b1-m02-u01-l01-o06"]["channels"]["production"]["evidence"] == 1
    # Estructura con checks MC de grammar pero sin ítem CP: producción no ofrecida.
    assert out["b1-m04-u01-l01-o10"]["channels"]["production"]["offered"] is False


def test_matrix_empty_user_shows_instruments_offered_but_no_evidence():
    matrix = cross_skill.cross_skill_matrix("b1", evidence_rows=[], production_passed_ids=set())
    assert matrix["proto"] is True
    for structure in matrix["structures"]:
        for name, cell in structure["channels"].items():
            assert cell["evidence"] == 0
    o01 = next(s for s in matrix["structures"] if s["structure_id"] == "b1-m01-u01-l01-o01")
    assert o01["channels"]["recognition"]["offered"] is True
    assert o01["channels"]["speaking"]["offered"] is True  # scenario "doctor"


# --- Endpoint (solo lectura) --------------------------------------------------


def test_endpoint_returns_b1_matrix_read_only(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/cross-skill", params={"user_id": uid, "level": "b1"})
        assert r.status_code == 200
        body = r.json()
        assert body["proto"] is True
        assert body["level"] == "B1"
        assert {s["structure_id"] for s in body["structures"]} == B1_GRAMMAR_STRUCTURES
        for structure in body["structures"]:
            assert set(structure["channels"]) == set(cross_skill.CHANNELS)
        # Ninguna petición GET escribe: sin intentos nuevos de grammar.
        attempts = __import__("repositories.grammar_routes", fromlist=["list_attempts"]).list_attempts(uid)
        assert attempts == []


def test_endpoint_rejects_level_outside_proto(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/cross-skill", params={"user_id": uid, "level": "c2"})
        assert r.status_code == 400
        assert "not_in_proto" in r.json()["detail"]


def test_bindings_stable_across_all_loaded_levels():
    # Regresión: el prototipo es B1; otros niveles no deben introducir bindings
    # sueltos que el registro no consume (escalado posterior explícito).
    for level in load_all_levels():
        bindings = cross_skill._production_bindings_for(level.level_id)
        if level.level_id == "b1":
            assert bindings == cross_skill.B1_PRODUCTION_BINDINGS
        else:
            assert bindings == {}
