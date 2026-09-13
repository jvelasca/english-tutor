"""V3.55 — Task Difficulty 3.0: `declared` / `served` / `observed_task`.

Hasta V3.54 el ledger guardaba UNA dificultad por evento (`observed_difficulty`,
V3.53) que en realidad era la de la tarea SERVIDA — el vector del contexto que el
alumno tenía delante, no la carga que había SUPERADO — y solo la escribía el
drill de Transfer (P2-01). Además `observed_signals` acreditaba igual un éxito
`guided` (repetir tras un modelo) que uno `spontaneous` (P2-02).

Aquí se cubre: el núcleo puro de las tres dificultades y la tabla de descuento
por andamiaje, la marca que distingue una fila V3.55 de una legacy, la capacidad
ACREDITADA (con y sin apoyo), el cableado de las vías del drill (escritura y
transferencia de punta a punta, y el helper compartido del drill léxico), la
migración aditiva e idempotente de las tres columnas y la paridad pura↔SQL.

Las guardias de no-regresión del motor viven en `test_difficulty_engine_v352.py`,
`test_learner_skill_v353.py` y `test_learner_skill_v354.py`.
"""

from __future__ import annotations

import asyncio
from contextlib import closing

from fastapi.testclient import TestClient

from domain import profile as profile_domain
from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, learner_skill, transfer
from services import evidence as evidence_svc

SERVED = {"lexical": 5, "syntax": 4, "discourse": 3, "interaction": 2}


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


def test_declared_difficulty_is_the_lexical_axis_only():
    # El ítem declara su CEFR (1..6) en la ÚNICA dimensión que puede declarar.
    assert difficulty.declared_difficulty(4) == {"lexical": 4}
    assert difficulty.declared_difficulty(4.0) == {"lexical": 4}
    # Recorta al rango canónico 1..5 y NO inventa para lo no declarado.
    assert difficulty.declared_difficulty(9) == {"lexical": 5}
    assert difficulty.declared_difficulty(0) == {}
    assert difficulty.declared_difficulty(0.0) == {}
    assert difficulty.declared_difficulty(None) == {}
    assert difficulty.declared_difficulty("B2") == {}
    assert difficulty.declared_difficulty(True) == {}


def test_support_discount_is_monotone_with_the_ladder():
    credited = {
        support: difficulty.observed_task_difficulty(SERVED, support)
        for support in ("guided", "cued", "independent", "spontaneous")
    }
    # `independent`/`spontaneous` acreditan la carga COMPLETA (sin descuento).
    assert credited["independent"] == SERVED
    assert credited["spontaneous"] == SERVED
    # Cada paso de andamiaje descuenta una unidad de carga por dimensión.
    assert credited["cued"] == {
        "lexical": 4,
        "syntax": 3,
        "discourse": 2,
        "interaction": 1,
    }
    assert credited["guided"] == {"lexical": 3, "syntax": 2, "discourse": 1}
    # `copied` (repetir tras un modelo) y un apoyo desconocido NO acreditan.
    assert difficulty.observed_task_difficulty(SERVED, "copied") == {}
    assert difficulty.observed_task_difficulty(SERVED, "") == {}
    assert difficulty.observed_task_difficulty(SERVED, "situational") == {}
    # Nunca se acredita MÁS de lo servido, y el descuento es monótono.
    for support, vector in credited.items():
        for dimension, load in vector.items():
            assert load <= SERVED[dimension], support


def test_observed_task_difficulty_drops_dimensions_below_the_floor():
    # Una dimensión que cae por debajo de la carga mínima no acredita nada.
    assert (
        difficulty.observed_task_difficulty({"lexical": 2, "syntax": 1}, "guided")
        == {}
    )
    assert difficulty.observed_task_difficulty({"lexical": 3}, "guided") == {
        "lexical": 1
    }
    # Un vector servido vacío o basura no acredita.
    assert difficulty.observed_task_difficulty({}, "independent") == {}
    assert difficulty.observed_task_difficulty(None, "independent") == {}


def test_task_difficulty_vectors_serialize_the_three_and_gate_the_failure():
    won = difficulty.task_difficulty_vectors(
        declared={"lexical": 4},
        served=SERVED,
        support_level="spontaneous",
        success=True,
    )
    assert won["declared_difficulty"] == "lexical:4"
    assert won["served_difficulty"] == difficulty.format_vector(SERVED)
    assert won["observed_task_difficulty"] == difficulty.format_vector(SERVED)
    # Proyección legacy: idéntica a lo servido (paridad V3.53).
    assert won["observed_difficulty"] == won["served_difficulty"]
    # En el FALLO se declaran las dos dificultades de la tarea (hechos) y la
    # acreditada queda vacía: un intento no superado no acredita carga. La
    # proyección legacy sigue declarando lo servido.
    lost = difficulty.task_difficulty_vectors(
        declared={"lexical": 4},
        served=SERVED,
        support_level="spontaneous",
        success=False,
    )
    assert lost["declared_difficulty"] == "lexical:4"
    assert lost["served_difficulty"] == difficulty.format_vector(SERVED)
    assert lost["observed_task_difficulty"] == ""
    assert lost["observed_difficulty"] == lost["served_difficulty"]


def test_earned_difficulty_uses_the_v355_marker_and_falls_back_to_legacy():
    # Fila V3.55: `served_difficulty` marca el evento y lo acreditado es
    # EXACTAMENTE `observed_task_difficulty`, aunque sea '' (un éxito `copied`).
    assert difficulty.earned_difficulty(
        {
            "served_difficulty": "discourse:5",
            "observed_task_difficulty": "discourse:5",
            "observed_difficulty": "discourse:5",
        }
    ) == {"discourse": 5}
    assert difficulty.earned_difficulty(
        {
            "served_difficulty": "discourse:5",
            "observed_task_difficulty": "",
            "observed_difficulty": "discourse:5",
        }
    ) == {}
    # Fila legacy (V3.53/V3.54): sin `served_difficulty` se acredita la servida.
    assert difficulty.earned_difficulty(
        {"observed_difficulty": "lexical:2,discourse:4"}
    ) == {"lexical": 2, "discourse": 4}
    assert difficulty.earned_difficulty({}) == {}


# ------------------------------------------------------------- capacidad


def test_observed_signals_discounts_the_supported_successes():
    rows = [
        {
            "success": True,
            "skill": "written_production",
            "served_difficulty": "lexical:5",
            "observed_task_difficulty": "lexical:5",
            "occurred_at": "2026-09-01T10:00:00+00:00",
        },
        {
            "success": True,
            "skill": "written_production",
            "served_difficulty": "lexical:5",
            "observed_task_difficulty": "lexical:4",
            "occurred_at": "2026-09-02T10:00:00+00:00",
        },
        {
            "success": True,
            "skill": "written_production",
            "served_difficulty": "lexical:5",
            "observed_task_difficulty": "lexical:3",
            "occurred_at": "2026-09-03T10:00:00+00:00",
        },
        # Repetir tras un modelo no acredita: entra en el ledger pero no suma.
        {
            "success": True,
            "skill": "written_production",
            "served_difficulty": "lexical:5",
            "observed_task_difficulty": "",
            "occurred_at": "2026-09-04T10:00:00+00:00",
        },
    ]
    signals = evidence_svc.observed_signals(rows)
    assert signals["observed_capacity"] == {"written_production": {"lexical": 5}}
    assert signals["observed_samples"] == {"written_production": {"lexical": 3}}
    assert signals["observed_days"] == {"written_production": {"lexical": 3}}


def test_observed_signals_keeps_legacy_rows_unchanged():
    # Sin `served_difficulty` (filas V3.53/V3.54) la carga servida se acredita
    # completa: la capacidad histórica NO cambia con este incremento.
    rows = [
        {
            "success": True,
            "skill": "spontaneous_use",
            "assessed_skill": "written_production",
            "observed_difficulty": "lexical:2,discourse:4",
            "occurred_at": "2026-09-01T10:00:00+00:00",
        }
    ]
    signals = evidence_svc.observed_signals(rows)
    assert signals["observed_capacity"] == {
        "written_production": {"lexical": 2, "discourse": 4}
    }


def test_a_guided_success_reaches_a_lower_floor_than_an_independent_one():
    def _rows(observed_task: str) -> list[dict]:
        return [
            {
                "success": True,
                "skill": "recall",
                "served_difficulty": "lexical:5",
                "observed_task_difficulty": observed_task,
                "occurred_at": "2026-09-01T10:00:00+00:00",
            },
            {
                "success": True,
                "skill": "recall",
                "served_difficulty": "lexical:5",
                "observed_task_difficulty": observed_task,
                "occurred_at": "2026-09-03T10:00:00+00:00",
            },
        ]

    independent = learner_skill.observed_skill_capacity(
        evidence_svc.observed_signals(_rows("lexical:5"))
    )
    guided = learner_skill.observed_skill_capacity(
        evidence_svc.observed_signals(_rows("lexical:3"))
    )
    assert independent == {"recall": {"lexical": 5}}
    assert guided == {"recall": {"lexical": 3}}


# ------------------------------------------------------------- cableado


def test_item_task_difficulty_helper_matches_the_drill_rungs():
    row = {"cefr": "B2"}  # `lexicon.cefr_difficulty` → 4
    # Word/Sentence (oral tras un modelo): `guided` → −2 pasos.
    guided = vocabulary_domain._item_task_difficulty(row, "guided", True)
    assert guided["declared_difficulty"] == "lexical:4"
    assert guided["served_difficulty"] == "lexical:4"
    assert guided["observed_task_difficulty"] == "lexical:2"
    # Recall con cue de definición (`cued`) → −1 paso.
    cued = vocabulary_domain._item_task_difficulty(row, "cued", True)
    assert cued["observed_task_difficulty"] == "lexical:3"
    # Write (frase propia, sin modelo): acredita la carga completa.
    independent = vocabulary_domain._item_task_difficulty(row, "independent", True)
    assert independent["observed_task_difficulty"] == "lexical:4"
    # En el fallo la acreditada siempre queda vacía.
    failed = vocabulary_domain._item_task_difficulty(row, "independent", False)
    assert failed["observed_task_difficulty"] == ""
    # Un ítem sin CEFR no declara carga (no se inventa un 1).
    assert vocabulary_domain._item_task_difficulty({}, "independent", True) == {
        "declared_difficulty": "",
        "served_difficulty": "",
        "observed_task_difficulty": "",
        "observed_difficulty": "",
    }


def test_write_event_persists_the_three_difficulties(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    with TestClient(app) as client:
        body = client.post(
            "/api/vocabulary/drill/write-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I usually travel by train in summer.",
                "response_time_ms": 4200,
            },
        ).json()
    assert body["passed"] is True
    row = evidence_repo.list_evidence(uid, "travel")[0]
    assert row["declared_difficulty"] == "lexical:4"
    assert row["served_difficulty"] == "lexical:4"
    # `independent`: la frase es del alumno, sin modelo que repetir.
    assert row["observed_task_difficulty"] == "lexical:4"
    # Proyección legacy: sigue siendo la dificultad servida (paridad V3.53).
    assert row["observed_difficulty"] == row["served_difficulty"]


def test_write_failure_declares_but_does_not_accredit(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    with TestClient(app) as client:
        body = client.post(
            "/api/vocabulary/drill/write-attempt",
            params={"user_id": uid},
            json={"word": "travel", "text": "travel"},
        ).json()
    assert body["passed"] is False
    row = evidence_repo.list_evidence(uid, "travel")[0]
    assert row["declared_difficulty"] == "lexical:4"
    assert row["served_difficulty"] == "lexical:4"
    assert row["observed_task_difficulty"] == ""


def test_transfer_event_persists_declared_served_and_credited(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
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
    row = [
        r
        for r in evidence_repo.list_evidence(uid, "travel")
        if r.get("activity_id") == "drill:transfer"
    ][0]
    # Declarado = carga léxica del ÍTEM; servido = vector del contexto elegido.
    assert row["declared_difficulty"] == "lexical:4"
    assert row["served_difficulty"] == difficulty.format_vector(
        transfer.context_difficulty(served["context_id"])
    )
    # Apoyo `spontaneous`: acredita la carga servida completa.
    assert row["observed_task_difficulty"] == row["served_difficulty"]
    assert row["observed_difficulty"] == row["served_difficulty"]


def test_write_successes_cache_the_lexical_capacity_of_the_skill(
    monkeypatch, tmp_path
):
    """El drill de escritura (independiente) ya acredita capacidad por skill.

    Hasta V3.54 `written_production` no acumulaba capacidad NUNCA: solo el drill
    de Transfer escribía la dificultad de la tarea. Con V3.55 dos escrituras
    independientes en días distintos son muestra espaciada de la carga léxica.
    """
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    for day in ("2026-09-01", "2026-09-03"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill="written_production",
            assessed_skill="written_production",
            task="write",
            activity_id="drill:write",
            context_id="lexicon:writing",
            success=True,
            support_level="independent",
            **difficulty.task_difficulty_vectors(
                declared={"lexical": 4},
                served={"lexical": 4},
                support_level="independent",
                success=True,
            ),
            occurred_at=f"{day}T10:00:00+00:00",
        )
    summary = asyncio.run(profile_domain.get_profile_summary(uid))
    row = profile_repo.get_profile(uid)
    nested = learner_skill.normalize_skill_capacity(row["observed_skill_capacity"])
    assert nested == {"written_production": {"lexical": 4}}
    # Cobertura PARCIAL (solo léxico): no hay nivel CEFR por skill que declarar
    # (la regla de cobertura completa de V3.53.1/V3.54 devuelve "").
    assert summary["observed_skill_level"] == {"written_production": ""}


# ------------------------------------------------------------- persistencia


def test_task_difficulty_columns_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    for column in (
        "declared_difficulty",
        "served_difficulty",
        "observed_task_difficulty",
    ):
        assert column in _columns("learning_evidence")
    # Re-ejecutar la migración no rompe ni duplica ninguna columna.
    db.init_db()
    for column in (
        "declared_difficulty",
        "served_difficulty",
        "observed_task_difficulty",
    ):
        assert column in _columns("learning_evidence")


def test_legacy_rows_keep_observed_difficulty_empty(monkeypatch, tmp_path):
    # Un evento escrito sin las tres dificultades (como los hacía V3.53/V3.54)
    # conserva el contrato: las tres columnas quedan en ''.
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
    assert row["declared_difficulty"] == ""
    assert row["served_difficulty"] == ""
    assert row["observed_task_difficulty"] == ""


def test_summarize_by_target_matches_the_pure_signals(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    for day, observed_task in (
        ("2026-09-01", "lexical:3,syntax:3,discourse:3,interaction:2"),
        ("2026-09-03", "lexical:3,syntax:3,discourse:3,interaction:2"),
    ):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="written_production",
            assessed_skill="written_production",
            task="write",
            activity_id="drill:write",
            success=True,
            support_level="independent",
            declared_difficulty="lexical:3",
            served_difficulty="lexical:3",
            observed_task_difficulty=observed_task,
            observed_difficulty="lexical:3",
            occurred_at=f"{day}T10:00:00+00:00",
        )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")
    rows = evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    pure = evidence_svc.summarize_evidence(rows)
    # Paridad EXACTA: el agregado SQL delega en la misma función pura.
    assert aggregated["river"] == pure
    assert aggregated["river"]["observed_capacity"] == {
        "written_production": {
            "lexical": 3,
            "syntax": 3,
            "discourse": 3,
            "interaction": 2,
        }
    }


def test_list_observed_rows_reads_the_credited_column(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="written_production",
        success=True,
        served_difficulty="lexical:5",
        observed_task_difficulty="lexical:4",
        observed_difficulty="lexical:5",
    )
    rows = evidence_repo.list_observed_rows(uid, target_type="lexicon")
    assert len(rows) == 1
    assert rows[0]["observed_task_difficulty"] == "lexical:4"
    assert difficulty.earned_difficulty(rows[0]) == {"lexical": 4}
