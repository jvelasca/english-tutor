"""V3.64 — Decision Projection + Planner 3.0 (cierre del P1-01 de V3.62).

Hasta V3.63 el Student Skill State era **descriptivo**: se construía, se sellaba y
se exponía, pero la decisión de tareas seguía leyendo la columna de V3.54
(`observed_skill_capacity`). V3.64 cierra el P1-01 con la capa declarada:

    Student Skill State  →  DECISION PROJECTION  →  Planner 3.0

**Nunca** `skill_state → planner`: el planner recibe `capacity_by_skill`,
`skill_values` y `drivers`, que son proyecciones puras calculadas por
`services.decision_projection`. La proyección se deriva de las **filas canónicas**
(caché sellada validada por frescura; si está vieja se recomputa UNA vez).

Este fichero fija, en orden: pureza del módulo, forma de la proyección (carga vs
esfuerzo, error de tarea vs incertidumbre de medida), el reemplazo de capacidad,
el valor pedagógico, los drivers, la degradación EXACTA a V3.63 cuando la
proyección no declara capacidad comparable, la contraprueba de que **el estado
ahora SÍ gobierna**, la frescura/recompute-once y el contrato aditivo HTTP.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from domain import decision as decision_domain
from domain import profile as profile_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import decision_projection as projection
from services import fsrs, lexicon, planner, skill_axis
from services import skill_state as skill_state_service
from services.evidence import LEXICAL_SKILLS

_BACKEND = Path(__file__).resolve().parent.parent
SKILLS = ("recall", "written_production", "spoken_production", "spontaneous_use")
NOW = "2026-09-13T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _lexicon_ledger(
    *,
    day: str,
    skill: str = "written_production",
    assessed: str = "",
    served: str = "lexical:4",
    earned: str = "lexical:4",
    row_id: str = "1",
    activity_id: str = "",
    support_level: str = "independent",
    error_type: str = "",
    context_instance: str = "",
    occurred_at: str = "",
) -> dict:
    """Fila del ledger léxico como la entrega `list_observed_rows`."""
    return {
        "id": row_id,
        "occurred_at": occurred_at or f"{day}T10:00:00+00:00",
        "skill": skill,
        "assessed_skill": assessed or skill,
        "success": 1,
        "served_difficulty": served,
        "observed_task_difficulty": earned,
        "observed_difficulty": served,
        "support_level": support_level,
        "response_time_ms": None,
        "error_type": error_type,
        "context_instance": context_instance,
        "activity_id": activity_id,
    }


def _state(rows: list[dict], *, level: str = "", now: str = "") -> dict:
    return skill_state_service.skill_state(
        skill_state_service.skill_state_sources(lexicon=rows),
        level=level,
        now=now,
    )


def _spaced(
    *,
    skill: str = "written_production",
    load: str = "lexical:4",
    days: tuple[str, str] = ("2026-01-01", "2026-01-02"),
    tag: str = "",
    **overrides,
) -> list[dict]:
    """Dos éxitos en dos días distintos: la puerta espaciada (2/2)."""
    return [
        _lexicon_ledger(
            day=day,
            skill=skill,
            served=load,
            earned=load,
            row_id=f"{tag}{index + 1}",
            **overrides,
        )
        for index, day in enumerate(days)
    ]


def _payload(state: dict) -> dict:
    """Payload de decisión desde un estado YA calculado (puro, sin I/O)."""
    return decision_domain.project_state(state, source="test")


def _row(**overrides) -> dict:
    row = {
        "word": "river",
        "cefr": "B1",
        "exposure_count": 3,
        "writing_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    row.update(overrides)
    return row


def _card(**overrides) -> dict:
    card = {
        "target_id": "river",
        "due_at": "2026-09-12T10:00:00+00:00",
        "state": "review",
        "stability": 5.0,
        "last_review_at": "2026-09-09T10:00:00+00:00",
    }
    card.update(overrides)
    return card


def _learner_state(*, floor: str = "B1", observed: dict | None = None) -> dict:
    """Estado del alumno con la MISMA forma que `learner_level_state`."""
    return {
        "floor_level": floor,
        "floor_source": "estimated" if floor else "none",
        "floor_level_by_skill": {skill: floor for skill in SKILLS},
        "floor_source_by_skill": {
            skill: ("estimated" if floor else "none") for skill in SKILLS
        },
        "observed_skill_capacity": observed or {},
    }


def _seed_word(uid: str, word: str, *, cefr: str = "B1") -> None:
    vocabulary_repo.seed_curriculum_items(
        uid,
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
    vocabulary_repo.record_exposures(uid, [word])


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    now = datetime.now(timezone.utc)
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": (now - timedelta(days=days_ago)).isoformat(),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


def _seed_evidence(uid: str, skill: str, days: list[str], load: str) -> None:
    for day in days:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill=skill,
            assessed_skill=skill,
            success=True,
            served_difficulty=load,
            observed_task_difficulty=load,
            occurred_at=f"{day}T07:00:00+00:00",
        )


def _recompute_counter(monkeypatch) -> list[str]:
    """Cuenta los recálculos REALES desde las filas canónicas (V3.64)."""
    calls: list[str] = []
    original = decision_domain._recompute

    async def counted(user_id, *, level, now):
        calls.append(user_id)
        return await original(user_id, level=level, now=now)

    monkeypatch.setattr(decision_domain, "_recompute", counted)
    return calls


# ---------------------------------------------------------------------------
# A · Pureza del módulo (mismo contrato que `observed_difficulty.py`)
# ---------------------------------------------------------------------------


def test_module_is_pure_deterministic_and_reads_no_clock_nor_io():
    state = _state(_spaced())
    first = projection.project(state)
    second = projection.project(state)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # Y todo lo derivado es función determinista de la proyección.
    for fn in (
        projection.capacity_by_skill,
        projection.skill_values,
    ):
        assert json.dumps(fn(first), sort_keys=True) == json.dumps(
            fn(second), sort_keys=True
        )
    assert projection.drivers(first, "recall") == projection.drivers(
        second, "recall"
    )
    source = (_BACKEND / "services" / "decision_projection.py").read_text("utf-8")
    for forbidden in (
        "import time",
        "import datetime",
        "import random",
        "hash(",
        "open(",
        "sqlite",
        "requests",
    ):
        assert forbidden not in source, forbidden


# ---------------------------------------------------------------------------
# B · Forma de la proyección: carga ≠ esfuerzo, error ≠ incertidumbre
# ---------------------------------------------------------------------------


def test_projection_is_total_over_the_canonical_modalities():
    empty = projection.project(skill_state_service.empty_skill_state())
    assert set(empty) == set(skill_axis.SKILL_MODALITIES)
    assert all(cells == {} for cells in empty.values())


def test_cell_splits_the_load_from_the_effort_and_names_the_demonstrated_load():
    rows = _spaced(skill="recall", support_level="guided", activity_id="lexicon:recall")
    cell = projection.project(_state(rows))["vocabulary"][""]
    load = set(cell["load"])
    effort = set(cell["effort"])
    # Grupos SEPARADOS (P2-02): ninguna clave vive en los dos.
    assert not load & effort
    assert "highest_demonstrated_load" in load
    # El nombre es el hecho: carga máxima DEMOSTRADA (P2-04), no dificultad.
    assert cell["load"]["highest_demonstrated_load"] == {"lexical": 4}
    assert cell["capacity"] == {"lexical": 4}
    assert "empirical_difficulty" not in json.dumps(cell)
    # El esfuerzo declara su nivel (tabla declarada) sin tocar la carga.
    assert set(effort) == {"level", "reasons", "extra_load"}


def test_scaffolding_gap_is_the_served_ceiling_minus_the_credited_one():
    rows = [
        _lexicon_ledger(day="2026-01-01", served="lexical:5", earned="lexical:3"),
        _lexicon_ledger(day="2026-01-02", served="lexical:5", earned="lexical:4"),
        _lexicon_ledger(
            day="2026-01-03",
            served="lexical:5",
            earned="lexical:5",
            support_level="guided",
        ),
    ]
    cell = projection.project(_state(rows))["writing"][""]
    assert cell["load"]["served_ceiling"] == {"lexical": 5}
    assert cell["load"]["credited_ceiling"] == {"lexical": 5}
    assert cell["load"]["scaffolding_gap"] == {}


def test_statistical_and_assessment_confidence_are_never_merged():
    cell = projection.project(_state(_spaced()))["writing"][""]
    assert isinstance(cell["confidence"], float)
    assert set(cell["assessment_confidence"]) == {"band", "reasons"}
    assert isinstance(cell["assessment_confidence"]["reasons"], list)
    # No hay ninguna clave que fusione las dos.
    assert "confidence_band" not in cell
    assert cell["assessment_confidence"]["band"] in ("low", "medium", "high")


def test_measurement_uncertainty_is_not_a_task_error_and_never_raises_load():
    uncertainty = projection.project(
        _state(_spaced(error_type="low_confidence"))
    )["writing"][""]
    task_error = projection.project(_state(_spaced(error_type="wrong_word")))[
        "writing"
    ][""]
    # La CARGA es la misma: el tipo de error no toca la dificultad servida.
    assert uncertainty["load"] == task_error["load"]
    assert uncertainty["capacity"] == task_error["capacity"]
    # El reparto declarado los separa (P2-03)...
    assert uncertainty["error_families"]["task"] == []
    assert uncertainty["error_families"]["measurement"] == ["low_confidence"]
    assert task_error["error_families"]["task"] == ["wrong_word"]
    assert task_error["error_families"]["measurement"] == []
    # ...y solo el error de TAREA enciende `recent_failure` en los drivers.
    proj_u = projection.project(_state(_spaced(error_type="low_confidence")))
    proj_t = projection.project(_state(_spaced(error_type="wrong_word")))
    assert projection.drivers(proj_u, "written_production")["recent_failure"] is False
    assert projection.drivers(proj_t, "written_production")["recent_failure"] is True


# ---------------------------------------------------------------------------
# C · `capacity_by_skill`: reemplazo directo de `lexicon._capacity_by_skill`
# ---------------------------------------------------------------------------


def test_capacity_keys_and_channel_mapping_match_the_lexical_vocabulary():
    assert set(projection.LEXICAL_MODALITY) == set(LEXICAL_SKILLS)
    # El canal EVALUADO de cada eje es el de V3.57 (política declarada, no nueva).
    assert planner.capacity_skill("recall") == "recall"
    assert planner.capacity_skill("written_production") == "written_production"
    assert planner.capacity_skill("spoken_production") == "spoken_production"
    # `transfer` se entrega y se MIDE por texto (escritura): no es un canal nuevo.
    assert planner.capacity_skill("spontaneous_use") == "written_production"
    rows = (
        _spaced(skill="recall", load="lexical:3", tag="1")
        + _spaced(skill="written_production", load="lexical:4", tag="2")
        + _spaced(skill="spoken_production", load="lexical:5", tag="3")
        + _spaced(
            skill="spontaneous_use",
            load="lexical:2",
            tag="4",
            activity_id="drill:transfer",
        )
    )
    capacity = projection.capacity_by_skill(projection.project(_state(rows)))
    assert set(capacity) == set(LEXICAL_SKILLS)
    assert capacity["recall"] == {"lexical": 3}
    assert capacity["written_production"] == {"lexical": 4}
    assert capacity["spoken_production"] == {"lexical": 5}
    assert capacity["spontaneous_use"] == {"lexical": 2}
    # `interaction` es la modalidad del eje de transferencia (no un canal aparte).
    assert projection.LEXICAL_MODALITY["spontaneous_use"] == "interaction"


def test_provisional_assessment_is_not_comparable_capacity():
    # Canal DESCONOCIDO declarado por la evidencia → banda mínima (V3.63).
    rows = _spaced(
        skill="spontaneous_use",
        load="lexical:3",
        assessed="",
        activity_id="",
    )
    proj = projection.project(_state(rows))
    cell = proj["interaction"][""]
    assert cell["assessment_confidence"]["band"] == "low"
    assert cell["provisional"] is True
    capacity = projection.capacity_by_skill(proj)
    assert capacity["spontaneous_use"] == {}
    assert projection.has_comparable_capacity(capacity) is False


def test_has_comparable_capacity_is_false_without_any_dimension():
    assert projection.has_comparable_capacity({}) is False
    assert projection.has_comparable_capacity({"recall": {}}) is False
    assert projection.has_comparable_capacity(None) is False
    assert projection.has_comparable_capacity({"recall": {"lexical": 3}}) is True


# ---------------------------------------------------------------------------
# D · `skill_values`: valor pedagógico proyectado
# ---------------------------------------------------------------------------


def test_declared_weights_sum_to_one_and_exclude_assessment_confidence():
    assert round(sum(projection.PROJECTION_WEIGHTS.values()), 4) == 1.0
    assert "assessment_confidence" not in projection.PROJECTION_WEIGHTS
    assert set(projection.PROJECTION_WEIGHTS) == {
        "gap",
        "retention",
        "transfer",
        "effort",
    }


def test_value_is_bounded_and_defined_for_every_axis():
    values = projection.skill_values(projection.project(_state(_spaced())))
    assert set(values) == set(LEXICAL_SKILLS)
    for skill, value in values.items():
        assert isinstance(value, float), skill
        assert 0.0 <= value <= 1.0, skill


def test_retention_is_a_first_class_signal_of_the_value():
    rows = _spaced(skill="recall", load="lexical:3")
    # El vencimiento lo declara el llamador (el módulo NO lee el reloj).
    due = projection.project(_state(rows, now="2030-01-01T00:00:00+00:00"))
    fresh = projection.project(_state(rows))
    assert projection.skill_values(due)["recall"] > projection.skill_values(fresh)[
        "recall"
    ]
    assert projection.skill_components(due, "recall")["retention"] == 1.0
    assert projection.skill_components(fresh, "recall")["retention"] == 0.0


def test_an_axis_without_sample_declares_the_maximum_gap():
    components = projection.skill_components(
        projection.project(skill_state_service.empty_skill_state()), "recall"
    )
    assert components["gap"] == 1.0
    assert components["transfer"] == 1.0


# ---------------------------------------------------------------------------
# E · `drivers`: explicabilidad declarada
# ---------------------------------------------------------------------------


def test_drivers_declare_the_keys_and_the_measurement_flag():
    unmeasured = projection.drivers(
        projection.project(skill_state_service.empty_skill_state()), "recall"
    )
    assert unmeasured["measured"] is False
    assert unmeasured["skill"] == "recall"
    measured = projection.drivers(projection.project(_state(_spaced())), "recall")
    assert measured["measured"] is False  # `recall` no tiene muestra en ese estado
    measured = projection.drivers(
        projection.project(_state(_spaced(skill="recall"))), "recall"
    )
    assert measured["measured"] is True
    assert set(measured) >= {
        "skill",
        "modality",
        "value",
        "components",
        "weights",
        "gap",
        "retention_due",
        "transfer_gap",
        "effort",
        "assessment_confidence",
        "recent_failure",
        "novelty",
        "contexts",
    }


def test_declared_contexts_are_counted_without_inventing_any():
    rows = _spaced(skill="spontaneous_use", context_instance="transfer:story")
    assert projection.drivers(
        projection.project(_state(rows)), "spontaneous_use"
    )["contexts"] == 1
    assert projection.drivers(
        projection.project(_state(_spaced(skill="spontaneous_use"))),
        "spontaneous_use",
    )["contexts"] == 0


def test_explain_drivers_never_invents_text():
    assert planner.explain_drivers(None) == []
    assert planner.explain_drivers({}) == []
    assert planner.explain_drivers({"measured": False}) == ["no spaced evidence yet"]
    phrases = planner.explain_drivers(
        {"measured": True, "gap": "high", "retention_due": True}
    )
    assert "large competence gap in the limiting modality" in phrases
    assert "review is due" in phrases


# ---------------------------------------------------------------------------
# F · Planner 3.0: aditivo y con degradación EXACTA a V3.63
# ---------------------------------------------------------------------------


def _planner_inputs() -> tuple[dict, dict, dict]:
    matrix = {"production": True}
    evidence = {
        "error_types": {"wrong_word": 2},
        "skill_successes": {"recall": 2},
    }
    return matrix, evidence, planner.planned_signals(evidence, matrix)


def test_select_task_by_elv_without_the_projection_keeps_the_v363_contract():
    matrix, evidence, signals = _planner_inputs()
    # Sin capacidad: EXACTO la cascada, byte a byte (sin clave `decision`).
    assert planner.select_task_by_elv(matrix, evidence, signals) == (
        planner.select_task(matrix, evidence, signals)
    )
    # Con capacidad: la MISMA tarea, sin ninguna clave nueva.
    chosen = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={"recall": {"lexical": 3}},
        task_difficulty={"lexical": 4},
    )
    assert set(chosen) == {"skill", "activity", "reason", "support_level"}
    assert "decision" not in chosen


def test_the_projected_value_replaces_the_priority_in_the_elv():
    matrix, evidence, signals = _planner_inputs()
    capacity = {"recall": {"lexical": 3}}
    projected = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill=capacity,
        task_difficulty={"lexical": 4},
        skill_values={"recall": 0.1234, "written_production": 0.9},
        drivers={"recall": {"measured": True, "gap": "low"}},
    )["decision"]
    assert projected["projected"] is True
    assert projected["value"] == 0.1234
    assert projected["drivers"] == {"measured": True, "gap": "low"}
    assert projected["source"] == "argmax"
    # `difficulty_fit` es el encaje declarado (punto 26) y solo vive aquí.
    assert projected["difficulty_fit"] == "above"
    # Las alternativas puntuadas viajan con la decisión (auditable).
    assert {item["skill"] for item in projected["alternatives"]} >= {"recall"}


def test_the_cascade_keeps_the_task_when_the_projection_has_no_capacity():
    matrix, evidence, signals = _planner_inputs()
    planned = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={},
        skill_values={"recall": 0.5},
        drivers={},
    )
    assert {key: value for key, value in planned.items() if key != "decision"} == (
        planner.select_task(matrix, evidence, signals)
    )
    assert planned["decision"]["source"] == "cascade"
    assert planned["decision"]["difficulty_fit"] == "unknown"


def test_difficulty_fit_reuses_the_declared_bands_and_never_raises():
    assert planner.difficulty_fit(0.9, -1) == "below"
    assert planner.difficulty_fit(0.55, 0) == "in_zone"
    assert planner.difficulty_fit(0.35, -1) == "above"
    assert planner.difficulty_fit(None, None) == "unknown"
    assert planner.difficulty_fit("nope", 0) == "unknown"
    assert planner.difficulty_fit(0.9, None) == "unknown"


def test_explain_priority_is_extended_additively_with_the_drivers():
    signals = {"forgetting": 0.6}
    base = planner.explain_priority(signals, "error_prone", None)
    assert base
    extended = planner.explain_priority(
        signals,
        "error_prone",
        None,
        {"measured": True, "gap": "high"},
    )
    assert extended.startswith(base)
    assert "large competence gap in the limiting modality" in extended


# ---------------------------------------------------------------------------
# G · Contraprueba: el estado AHORA SÍ gobierna (P1-01 cerrado)
# ---------------------------------------------------------------------------


def test_the_projection_governs_the_served_task_and_not_the_legacy_column():
    """Mismo `learner_state`, dos proyecciones: manda la proyección."""
    legacy = _learner_state(observed={"recall": {"lexical": 5}})
    argued = {"error_types": {"wrong_word": 2}, "skill_successes": {"recall": 2}}
    # Camino V3.63: recall MUY por encima del ítem → el argmax NO se va al recall.
    without = lexicon.review_queue_item(
        _row(), _card(), now=NOW, evidence=argued, learner_state=legacy
    )
    assert without["task"]["activity"] != "recall"
    assert "decision" not in without
    # Con la proyección que declara capacidad REAL del estado (recall en zona):
    # la tarea servida CAMBIA y la decisión se explica.
    rows = _spaced(skill="recall", load="lexical:3")
    with_projection = lexicon.review_queue_item(
        _row(),
        _card(),
        now=NOW,
        evidence=argued,
        learner_state=legacy,
        projection=_payload(_state(rows)),
    )
    assert with_projection["task"]["activity"] == "recall"
    assert with_projection["task"]["activity"] != without["task"]["activity"]
    assert with_projection["decision"]["projected"] is True
    assert with_projection["decision"]["margin"] == 0
    assert with_projection["decision"]["drivers"]["measured"] is True
    # `why` se EXTIENDE de forma aditiva (mismas claves de V3.63, más motivos).
    assert set(with_projection) >= set(without)


def test_a_silent_projection_degrades_exactly_to_the_v363_decision():
    legacy = _learner_state(observed={"recall": {"lexical": 5}})
    argued = {"error_types": {"wrong_word": 2}, "skill_successes": {"recall": 2}}
    without = lexicon.review_queue_item(
        _row(), _card(), now=NOW, evidence=argued, learner_state=legacy
    )
    silent = lexicon.review_queue_item(
        _row(),
        _card(),
        now=NOW,
        evidence=argued,
        learner_state=legacy,
        projection=_payload(skill_state_service.empty_skill_state()),
    )
    # Sin capacidad comparable: byte-idéntico (ni clave `decision` ni cambio de
    # tarea). El estado manda cuando tiene algo que decir y NUNCA se pierde señal.
    assert silent == without


# ---------------------------------------------------------------------------
# H · Frescura: caché fresca no recomputa; vieja recomputa UNA vez y re-sella
# ---------------------------------------------------------------------------


def test_a_fresh_cache_is_used_without_recomputing(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    asyncio.run(profile_domain.get_profile_summary(uid))
    calls = _recompute_counter(monkeypatch)
    payload = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert payload["source"] == "cached"
    assert payload["sealed"] is False
    assert calls == []
    assert payload["capacity_by_skill"]["written_production"] == {"lexical": 4}


def test_a_legacy_cache_without_seal_is_recomputed_once(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    # Caché legacy de V3.62: estado sin sello de frescura.
    profile_repo.set_skill_state(uid, json.dumps(_state([]), sort_keys=True))
    calls = _recompute_counter(monkeypatch)
    first = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert first["source"] == "recomputed"
    assert first["sealed"] is True
    assert len(calls) == 1
    assert first["capacity_by_skill"]["written_production"] == {"lexical": 4}
    # Y la caché queda fresca: la segunda llamada NO recomputa.
    second = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert second["source"] == "cached"
    assert len(calls) == 1
    assert second["capacity_by_skill"] == first["capacity_by_skill"]


def test_new_evidence_makes_the_cache_stale_and_it_is_resealed(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(uid, "recall", ["2026-01-01", "2026-01-02"], "lexical:3")
    asyncio.run(profile_domain.get_profile_summary(uid))
    before = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert before["source"] == "cached"
    # Entra evidencia nueva: la huella de las cuatro fuentes cambia.
    _seed_evidence(uid, "written_production", ["2026-01-03", "2026-01-04"], "lexical:5")
    calls = _recompute_counter(monkeypatch)
    after = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert after["source"] == "recomputed"
    assert after["sealed"] is True
    assert len(calls) == 1
    assert after["capacity_by_skill"]["written_production"] == {"lexical": 5}
    assert (
        asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))[
            "source"
        ]
        == "cached"
    )
    assert len(calls) == 1


def test_projection_never_raises_without_a_profile(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    payload = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert payload["source"] == "recomputed"
    assert payload["sealed"] is False  # sin fila de perfil no se inventa caché
    assert set(payload["capacity_by_skill"]) == set(LEXICAL_SKILLS)


# ---------------------------------------------------------------------------
# I · Contrato aditivo (HTTP e2e)
# ---------------------------------------------------------------------------


def test_review_queue_and_profile_are_additive_with_the_decision(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "river", cefr="B1")
    vocabulary_repo.record_production(uid, ["river"], channel="writing")
    vocabulary_repo.record_recalls(uid, ["river"])
    for _ in range(2):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            success=False,
            error_type="wrong_word",
        )
    # Evidencia ESPACIADA real que hace hablar al estado unificado (2/2).
    _seed_evidence(uid, "recall", ["2026-01-01", "2026-01-02"], "lexical:3")
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        queue = client.get("/api/learning/review", params={"user_id": uid}).json()
        profile = client.get("/api/profile", params={"user_id": uid}).json()

    item = queue["items"][0]
    assert item["task"]["activity"] == "recall"
    decision = item["decision"]
    assert decision["projected"] is True
    assert decision["source"] == "argmax"
    assert decision["drivers"]["measured"] is True
    assert isinstance(item["why"], str) and item["why"]
    # Todas las claves de V3.63 siguen presentes con el mismo significado.
    assert {
        "word",
        "activity",
        "reason",
        "priority",
        "expected_learning_value",
        "learning_value",
        "signals",
        "why",
        "limiting_skill",
        "skill_priorities",
        "task",
        "competence",
        "transfer_state",
    } <= set(item)
    # El perfil expone la proyección completa (aditiva).
    exposed = profile["decision_projection"]
    assert exposed["source"] == "profile"
    assert set(exposed["capacity_by_skill"]) == set(LEXICAL_SKILLS)
    assert set(exposed["skill_values"]) == set(LEXICAL_SKILLS)
    assert set(exposed["drivers"]) == set(LEXICAL_SKILLS)
    assert exposed["state"] == profile["skill_state"]


# ---------------------------------------------------------------------------
# J · V3.64.1 — sellado estable y snapshot fingerprint (P1-01/P1-02)
# ---------------------------------------------------------------------------


def test_recompute_reseals_only_a_stable_snapshot(monkeypatch, tmp_path):
    """La carrera del sellado (P1-01): si la huella cambia durante la lectura,
    se reintenta hasta devolver un sello ESTABLE; nunca un sello más nuevo que el
    estado (el par `before == after` es el que autoriza sellar)."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(
        uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4"
    )
    stable = evidence_repo.evidence_fingerprint(uid)

    calls: list[str] = []
    flip = {"on": True}

    def flapping(user_id):
        # Primera lectura devuelve una huella ANTERIOR: el par (before, after)
        # difiere y el sellado debe reintentar en vez de sellar estado viejo
        # con huella nueva.
        if flip["on"]:
            flip["on"] = False
            calls.append("stale")
            return "stale-before"
        calls.append("stable")
        return stable

    monkeypatch.setattr(evidence_repo, "evidence_fingerprint", flapping)

    _, seal = asyncio.run(decision_domain._recompute(uid, level="", now=NOW))
    assert seal == stable
    # before(stale) + after(stable) del intento fallido, y before/after del
    # intento estable: exactamente un reintento.
    assert calls == ["stale", "stable", "stable", "stable"]


def test_decision_payload_declares_the_observed_snapshot_fingerprint(
    monkeypatch, tmp_path
):
    """P1-02: la decisión declara la huella observada al INICIO (snapshot
    trazable); el camino del perfil (proyección aditiva, no decisión) la deja
    vacía."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_evidence(
        uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4"
    )
    asyncio.run(profile_domain.get_profile_summary(uid))

    expected = evidence_repo.evidence_fingerprint(uid)
    payload = asyncio.run(decision_domain.decision_projection(uid, level="", now=NOW))
    assert payload["snapshot_fingerprint"] == expected

    profile = asyncio.run(profile_domain.get_profile_summary(uid))
    assert profile["decision_projection"]["snapshot_fingerprint"] == ""
