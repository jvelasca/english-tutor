"""V3.52 — Student level state (P1-01 de la auditoría de V3.51).

La auditoría de V3.51 confirmó que `learner_level` NO era el nivel demostrado:
`domain.vocabulary._learner_level` leía `learning_profile.cefr_level`, que
`domain.profile` escribe con `estimated_level` (una banda de PRÁCTICA continua).
El nivel DEMOSTRADO (`_demonstrated_level` + `certification_gate`) existía en el
Student Model, pero el drill nunca lo usaba y el docstring lo llamaba
"demostrado".

V3.52 separa explícitamente tres niveles y deriva de ellos el SUELO de
dificultad con una política conservadora:

    demostrado > estimado > declarado (práctica) > ninguno

Solo `demonstrated_cefr` exige certificación con retención; `estimated_cefr` es
un proxy de práctica y `practice_level` el nivel declarado/legacy. Este módulo es
PURO y nunca lanza; la caché (`learning_profile`) guarda las tres columnas y el
drill las lee en O(1).

Las guardias de regresión viven en las suites de V3.36/V3.43/V3.47/V3.50/V3.51;
aquí se cubre lo NUEVO.
"""

from __future__ import annotations

import asyncio
from contextlib import closing

from fastapi.testclient import TestClient

from domain import profile as profile_domain
from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import profile as profile_repo
from repositories import users as users_repo
from services import student_state


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# ------------------------------------------------------------- módulo puro


def test_level_sources_are_the_canonical_priority_order():
    assert student_state.LEVEL_SOURCES == (
        "demonstrated",
        "estimated",
        "practice",
        "none",
    )
    assert student_state.CERTIFIED_SOURCES == frozenset({"demonstrated"})


def test_floor_level_prefers_demonstrated_then_estimated_then_practice():
    # Demostrado gana SIEMPRE, incluso si su banda es inferior a la estimada:
    # una certificación demuestra retención; el estimado solo la intuye.
    assert student_state.floor_level("C1", "C1", "A2") == ("A2", "demonstrated")
    assert student_state.floor_level("C1", "B2", "") == ("B2", "estimated")
    assert student_state.floor_level("A2", "", "") == ("A2", "practice")
    assert student_state.floor_level("", "", "") == ("", "none")


def test_floor_level_is_robust_to_unknown_and_empty_values():
    # Valores no CEFR (o None) no participan: no se inventa un suelo.
    assert student_state.floor_level(None, None, None) == ("", "none")
    assert student_state.floor_level("Pre-A1", "no-existe", "  ") == ("", "none")
    # Normaliza a mayúsculas y recorta espacios.
    assert student_state.floor_level("  b1  ", "", "") == ("B1", "practice")
    # Un valor no reconocido en la fuente superior deja pasar a la siguiente.
    assert student_state.floor_level("b2", "no-existe", "") == ("B2", "practice")


def test_level_state_shape_and_normalization():
    state = student_state.level_state(
        practice_level="a2",
        estimated_cefr="B1",
        demonstrated_cefr="",
    )
    assert state == {
        "practice_level": "A2",
        "estimated_cefr": "B1",
        "demonstrated_cefr": "",
        "floor_level": "B1",
        "floor_source": "estimated",
    }
    assert student_state.is_certified(state["floor_source"]) is False


def test_is_certified_only_for_demonstrated_and_empty_state_is_fresh():
    assert student_state.is_certified("demonstrated") is True
    assert student_state.is_certified("DEMONSTRATED") is True
    assert student_state.is_certified("estimated") is False
    assert student_state.is_certified(None) is False
    first = student_state.empty_state()
    first["floor_level"] = "C2"
    assert student_state.empty_state()["floor_level"] == ""
    assert student_state.empty_state()["floor_source"] == "none"


# --------------------------------------------------------------- migración


def test_migration_adds_level_state_columns(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cols = {row[1] for row in db._conn().execute("PRAGMA table_info(learning_profile)")}
    assert {"cefr_level", "estimated_level", "demonstrated_level"} <= cols


def test_migration_alters_a_legacy_profile_table(monkeypatch, tmp_path):
    # Simula un `learning_profile` V3.51 (sin las columnas nuevas) y comprueba que
    # la migración aditiva las añade; las filas legacy quedan en ''.
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "CREATE TABLE learning_profile ("
            "user_id TEXT PRIMARY KEY, "
            "cefr_level TEXT NOT NULL DEFAULT 'A1', "
            "updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO learning_profile (user_id, cefr_level, updated_at) "
            "VALUES ('legacy', 'B1', '2026-01-01T00:00:00+00:00')"
        )
    db.init_db()
    cols = {row[1] for row in db._conn().execute("PRAGMA table_info(learning_profile)")}
    assert {"estimated_level", "demonstrated_level"} <= cols
    row = profile_repo.get_profile("legacy")
    assert row["cefr_level"] == "B1"
    assert row["estimated_level"] == ""
    assert row["demonstrated_level"] == ""


# ------------------------------------------------------------- repositorio


def test_set_level_state_roundtrip(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    saved = profile_repo.set_level_state(
        uid, estimated_level="B1", demonstrated_level="A2"
    )
    assert saved["estimated_level"] == "B1"
    assert saved["demonstrated_level"] == "A2"
    # `cefr_level` conserva el valor del estimado por compatibilidad.
    assert saved["cefr_level"] == "B1"
    row = profile_repo.get_profile(uid)
    assert row["estimated_level"] == "B1"
    assert row["demonstrated_level"] == "A2"
    assert row["cefr_level"] == "B1"


def test_set_level_state_unknown_user_is_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        profile_repo.set_level_state(
            "no-existe", estimated_level="B1", demonstrated_level=""
        )
        is None
    )


def test_set_cefr_is_a_wrapper_that_preserves_demonstrated(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    profile_repo.set_level_state(
        uid, estimated_level="B1", demonstrated_level="A2"
    )
    # El wrapper histórico actualiza el estimado sin pisar la certificación.
    profile_repo.set_cefr(uid, "C1")
    row = profile_repo.get_profile(uid)
    assert row["cefr_level"] == "C1"
    assert row["estimated_level"] == "C1"
    assert row["demonstrated_level"] == "A2"


# --------------------------------------------------- lectura en el drill


def test_learner_level_state_reads_the_cache_with_priority(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    profile_repo.set_level_state(
        uid, estimated_level="B1", demonstrated_level=""
    )
    state = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert state["floor_level"] == "B1"
    assert state["floor_source"] == "estimated"
    # La certificación (aunque sea de banda inferior) pasa a ser el suelo.
    profile_repo.set_level_state(
        uid, estimated_level="B1", demonstrated_level="A2"
    )
    state = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert state["floor_level"] == "A2"
    assert state["floor_source"] == "demonstrated"


def test_learner_level_state_uses_legacy_cefr_as_declared_level(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Fila migrada: `cefr_level` con valor (lo que V3.51 cachaba) y las columnas
    # nuevas vacías. El nivel declarado sigue alimentando el suelo, con fuente
    # "practice" (menos confianza → tolerancia amplia).
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile "
            "(user_id, cefr_level, estimated_level, demonstrated_level, updated_at) "
            "VALUES (?, 'C1', '', '', '2026-01-01T00:00:00+00:00')",
            (uid,),
        )
    state = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert state["floor_level"] == "C1"
    assert state["floor_source"] == "practice"


def test_learner_level_state_without_profile_is_neutral(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    state = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert state == student_state.empty_state()


# ------------------------------------------------------------- contrato HTTP


def test_api_profile_exposes_demonstrated_level(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.get("/api/profile", params={"user_id": uid})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "demonstrated_level" in body
    # Sin certificación el campo es None (nunca el estimado).
    assert body["demonstrated_level"] is None


def test_get_profile_summary_caches_both_levels(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    asyncio.run(profile_domain.get_profile_summary(uid))
    row = profile_repo.get_profile(uid)
    assert row is not None
    # El estimado queda cacheado y `cefr_level` lo refleja; el demostrado sigue
    # vacío mientras no haya certificación.
    assert row["estimated_level"]
    assert row["cefr_level"] == row["estimated_level"]
    assert row["demonstrated_level"] == ""
