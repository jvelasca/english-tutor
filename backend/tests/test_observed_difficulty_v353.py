"""V3.53 — Parte A: `observed_difficulty` persistido por evento.

La dificultad de la TAREA servida (el `difficulty_vector` del contexto del banco)
se persiste en el ledger como vector serializado, no como media escalar, para no
volver a colapsar las dimensiones (el P1 que cerraron V3.52/V3.52.2). Aquí se
cubren: serialización canónica e inversa, contexto → vector, escritura REAL del
evento de transferencia, `''` en el resto de drills, migración aditiva e
idempotente y paridad entre el resumen puro y el agregado SQL.

Las guardias de no-regresión del motor viven en `test_difficulty_engine_v352.py`.
"""

from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, transfer
from services import evidence as evidence_svc


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "B2") -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


def _columns(table: str) -> set[str]:
    with closing(db._conn()) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# ------------------------------------------------------------- módulo puro


def test_format_vector_is_canonical_order_and_drops_unknowns():
    assert difficulty.format_vector(
        {"discourse": 4, "lexical": 2, "syntax": 3, "interaction": 2}
    ) == "lexical:2,syntax:3,discourse:4,interaction:2"
    # Recorta a 1..5, ignora claves desconocidas y no numéricas.
    assert difficulty.format_vector(
        {"lexical": 9, "syntax": 0, "bogus": 3, "interaction": "x"}
    ) == "lexical:5,syntax:1"
    assert difficulty.format_vector({}) == ""
    assert difficulty.format_vector(None) == ""


def test_parse_vector_is_the_inverse_and_tolerates_garbage():
    canonical = {"lexical": 2, "syntax": 3, "discourse": 4, "interaction": 1}
    assert difficulty.parse_vector(difficulty.format_vector(canonical)) == canonical
    # Tolerante: pares mal formados, claves desconocidas y cargas fuera de rango.
    assert difficulty.parse_vector("lexical:2,bogus:3,7,syntax:,discourse:9") == {
        "lexical": 2,
        "discourse": 5,
    }
    assert difficulty.parse_vector("") == {}
    assert difficulty.parse_vector(None) == {}
    assert difficulty.parse_vector("totally broken") == {}
    # La forma canónica se conserva con round-trip completo.
    for vector in ({}, {"syntax": 5}, canonical):
        assert difficulty.format_vector(
            difficulty.parse_vector(difficulty.format_vector(vector))
        ) == difficulty.format_vector(vector)


def test_context_difficulty_accepts_dict_id_and_context_id():
    context = transfer.TRANSFER_CONTEXTS[0]
    expected = difficulty.normalize_vector(context["difficulty_vector"])
    assert expected
    assert transfer.context_difficulty(context) == expected
    assert transfer.context_difficulty(context["id"]) == expected
    assert transfer.context_difficulty(transfer.context_id_for(context)) == expected
    # Un contexto no reconocido o sin carga no inventa vector.
    assert transfer.context_difficulty("no-existe") == {}
    assert transfer.context_difficulty({}) == {}


# ------------------------------------------------------------- persistencia


def test_transfer_event_persists_the_served_context_vector(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    profile_repo.set_level_state(uid, estimated_level="B2", demonstrated_level="")
    with TestClient(app) as client:
        served = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        ).json()
        attempt = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I travel to work by train every single day.",
                "context_id": served["context_id"],
            },
        )
    assert attempt.status_code == 200, attempt.text
    rows = evidence_repo.list_evidence(uid, "travel", target_type="lexicon")
    transfer_rows = [r for r in rows if r.get("activity_id") == "drill:transfer"]
    assert transfer_rows
    row = transfer_rows[0]
    # El vector persistido es el del contexto SERVIDO, no la media del ítem.
    assert row["observed_difficulty"] == difficulty.format_vector(
        transfer.context_difficulty(served["context_id"])
    )
    assert difficulty.parse_vector(row["observed_difficulty"])


def test_other_drills_leave_observed_difficulty_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    row = evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="recall",
        task="recall",
        success=True,
        support_level="cued",
    )
    assert row is not None
    assert row["observed_difficulty"] == ""
    stored = evidence_repo.list_evidence(uid, "river", target_type="lexicon")[0]
    assert stored["observed_difficulty"] == ""


def test_observed_difficulty_column_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "observed_difficulty" in _columns("learning_evidence")
    # Re-ejecutar la migración no rompe ni duplica la columna.
    db.init_db()
    assert "observed_difficulty" in _columns("learning_evidence")


# ------------------------------------------------------------- paridad pura/SQL


def test_summarize_by_target_matches_the_pure_observed_signals(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vector = "lexical:2,syntax:3,discourse:4,interaction:2"
    for day in ("2026-09-01", "2026-09-03"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="spontaneous_use",
            assessed_skill="written_production",
            task="transfer",
            activity_id="drill:transfer",
            context_id="transfer:story",
            success=True,
            support_level="spontaneous",
            observed_difficulty=vector,
            occurred_at=f"{day}T10:00:00+00:00",
        )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")
    rows = evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    pure = evidence_svc.summarize_evidence(rows)
    # Paridad EXACTA: el agregado SQL delega en la misma función pura.
    assert aggregated["river"] == pure
    expected_capacity = {
        "written_production": {
            "lexical": 2,
            "syntax": 3,
            "discourse": 4,
            "interaction": 2,
        }
    }
    assert aggregated["river"]["observed_capacity"] == expected_capacity
    assert aggregated["river"]["observed_samples"] == {
        "written_production": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 2,
            "interaction": 2,
        }
    }
    assert aggregated["river"]["observed_days"] == {
        "written_production": {
            "lexical": 2,
            "syntax": 2,
            "discourse": 2,
            "interaction": 2,
        }
    }


def test_list_observed_rows_keeps_only_successes_with_a_vector(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vector = "lexical:3,syntax:3,discourse:3,interaction:3"
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="written_production",
        success=True,
        observed_difficulty=vector,
    )
    # Un fallo con vector declarado no acredita capacidad.
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="written_production",
        success=False,
        observed_difficulty=vector,
    )
    # Un éxito sin vector (drill sin banco de contextos) tampoco.
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="written_production",
        success=True,
    )
    rows = evidence_repo.list_observed_rows(uid, target_type="lexicon")
    assert len(rows) == 1
    assert rows[0]["observed_difficulty"] == vector
