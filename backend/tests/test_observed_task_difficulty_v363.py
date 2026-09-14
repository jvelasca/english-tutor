"""V3.63 — Observed Task Difficulty 2.0 y honestidad del Student Skill State.

Cierra la deuda de honestidad que dejó V3.62 declarada por escrito, sin recablear
la decisión de tareas:

- **A** identidad de evidencia y OCASIONES (un dedup que solo puede acreditar
  menos);
- **B** canal OBSERVADO de la evidencia léxica (`spontaneous_use` escrito vs oral)
  con degradación exacta a V3.62 cuando la fila no declara canal;
- **C** capa EMPÍRICA de dificultad (`observed_difficulty`), medida con tablas
  declaradas sobre las filas canónicas y la MISMA puerta espaciada;
- **D** confianza de EVALUACIÓN separada de la confianza estadística;
- **E** pronunciación con el criterio DECLARADO que la ruta ya puntúa;
- **F** capas de listening reutilizando `SKILL_LAYER` sin vocabulario nuevo;
- **G** seam de política del gate (solo la política por defecto);
- **H** frescura del estado cacheado (una caché vieja nunca se sirve como fresca).

La invariante central sigue siendo la de V3.62: el camino de decisión es
byte-idéntico y `test_skill_state_v362.py` sigue verde **sin tocarse**.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from domain import profile as profile_domain
from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from services import competence, learner_skill, observed_difficulty, skill_axis
from services import skill_state as skill_state_service
from services.listening import LISTENING_LAYERS, SKILL_LAYER
from services.pronunciation import PRONUNCIATION_CRITERIA

_BACKEND = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _columns(table: str) -> set[str]:
    with closing(db._conn()) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


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
    response_time_ms: object = None,
    error_type: str = "",
) -> dict:
    """Fila del ledger léxico como la entrega `list_observed_rows`."""
    return {
        "id": row_id,
        "occurred_at": f"{day}T10:00:00+00:00",
        "skill": skill,
        "assessed_skill": assessed or skill,
        "success": 1,
        "served_difficulty": served,
        "observed_task_difficulty": earned,
        "observed_difficulty": served,
        "support_level": support_level,
        "response_time_ms": response_time_ms,
        "error_type": error_type,
        "activity_id": activity_id,
    }


def _academy_ledger(
    *,
    day: str,
    skill: str = "listening",
    item_id: str = "item",
    level_id: str = "a2",
    objective_id: str = "obj-1",
    result: float = 0.9,
    row_id: str = "1",
) -> dict:
    """Fila de `academy_evidence` como la entrega `list_evidence`."""
    return {
        "id": row_id,
        "user_id": "u",
        "level_id": level_id,
        "objective_id": objective_id,
        "skill": skill,
        "item_id": item_id,
        "item_type": "mcq",
        "difficulty": 1,
        "source": "objective_assessment",
        "result": result,
        "curriculum_version": "",
        "assessment_version": "",
        "evidence_kind": "familiar",
        "context_id": "",
        "activity_id": "",
        "task_type": "",
        "support_level": "",
        "created_at": f"{day}T12:00:00+00:00",
    }


def _listening_ledger(
    *,
    day: str,
    skill: str = "gist",
    correct: bool = True,
    row_id: str = "1",
    speed_used: str = "normal",
    transcript_used: object = 0,
    replay_count: object = 0,
    response_time_ms: object = None,
    score: float | None = None,
) -> dict:
    return {
        "id": row_id,
        "question_id": "q1",
        "correct": 1 if correct else 0,
        "skill": skill,
        "difficulty": 1,
        "response_time_ms": response_time_ms,
        "replay_count": replay_count,
        "topic": "",
        "realized_difficulty": 0,
        "task_type": "mcq",
        "score": score,
        "layer": SKILL_LAYER.get(skill, ""),
        "speed_used": speed_used,
        "stage": "",
        "transcript_used": transcript_used,
        "segments_replayed": 0,
        "shadowing_duration_ms": None,
        "shadowing_speech_rate": None,
        "word_breakdown_json": "",
        "created_at": f"{day}T09:00:00+00:00",
    }


def _pronunciation_ledger(*, day: str, score: int = 90, row_id: str = "1") -> dict:
    return {
        "id": row_id,
        "expected": "hello",
        "heard": "hello",
        "score": score,
        "level": "a1",
        "created_at": f"{day}T08:00:00+00:00",
    }


_OBJECTIVES = {("a2", "obj-1"): (("gist", "detail"), {"listening": 0.5})}


def _seed_lexicon_evidence(uid: str, skill: str, days: list[str], load: str) -> None:
    for day in days:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill=skill,
            assessed_skill=skill,
            success=True,
            served_difficulty=load,
            observed_task_difficulty=load,
            occurred_at=f"{day}T07:00:00+00:00",
        )


# ---------------------------------------------------------------------------
# A · Identidad de evidencia y ocasiones (P2-13)
# ---------------------------------------------------------------------------


def test_identity_is_empty_when_the_source_does_not_declare_it():
    rows = skill_state_service.skill_state_sources(
        lexicon=[_lexicon_ledger(day="2026-01-01", row_id="", activity_id="")]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["evidence_id"] == ""
    assert row["activity_id"] == ""
    assert row["assessment_id"] == ""
    assert skill_state_service.occasion_key(row) == ""


def test_lexicon_identity_is_carried_from_the_ledger():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01", row_id="7", activity_id="drill:transfer"
            )
        ]
    )
    row = rows[0]
    assert row["evidence_id"] == "7"
    assert row["activity_id"] == "drill:transfer"
    # La identidad es ESTABLE y no vacía: la ocasión se puede deduplicar.
    assert skill_state_service.occasion_key(row) != ""
    assert skill_state_service.occasion_key(row) == (
        skill_state_service.occasion_key(dict(row))
    )


def test_one_assessment_expanding_to_n_competences_is_one_occasion():
    rows = skill_state_service.skill_state_sources(
        academy=[_academy_ledger(day="2026-01-01")], objectives=_OBJECTIVES
    )
    # Una evaluación → una fila por competencia declarada del objetivo (N > 1)...
    assert len(rows) == 2
    assert {row["competence"] for row in rows} == {"detail", "gist"}
    # ...y las N comparten UNA sola ocasión.
    assert len({skill_state_service.occasion_key(row) for row in rows}) == 1


def test_occasion_dedup_never_accredits_more_than_v362():
    # (a) SIN identidad declarada la degradación es EXACTA: ocasiones == muestras.
    plain = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            lexicon=[
                _lexicon_ledger(
                    day=d, row_id="", served="lexical:3", earned="lexical:3"
                )
                for d in ("2026-01-01", "2026-01-02")
            ]
        )
    )
    entry = plain["writing"][""]
    assert entry["occasions"] == entry["samples"] == 2
    assert entry["observations"] == 2

    # (b) Con la MISMA identidad repetida, el dedup SOLO puede acreditar menos.
    deduped = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            lexicon=[
                _lexicon_ledger(
                    day=d, row_id="1", served="lexical:3", earned="lexical:3"
                )
                for d in ("2026-01-01", "2026-01-02")
            ]
        )
    )
    entry = deduped["writing"][""]
    assert entry["occasions"] == 1
    assert entry["samples"] == 2
    assert entry["occasions"] <= entry["samples"]


# ---------------------------------------------------------------------------
# B · Canal observado (P1-02)
# ---------------------------------------------------------------------------


def test_spontaneous_use_written_stays_interaction():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01",
                skill="spontaneous_use",
                assessed="",
                activity_id="drill:transfer",
            )
        ]
    )
    assert rows[0]["modality"] == "interaction"


def test_spontaneous_use_spoken_lands_in_speaking():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01",
                skill="spontaneous_use",
                assessed="",
                activity_id="drill:sentence",
            )
        ]
    )
    assert rows[0]["modality"] == "speaking"


def test_declared_channel_overrides_the_skill_fallback():
    # El mapa declara el CANAL, no solo la skill: `spoken` NO cae en el eje
    # escrito de V3.62 (`interaction`), cae en el canal oral (`speaking`).
    assert skill_axis.MODALITIES_BY_ASSESSED_CHANNEL[
        ("spontaneous_use", "spoken")
    ] == ("speaking",)
    assert skill_axis.MODALITIES_BY_ASSESSED_CHANNEL[
        ("spontaneous_use", "written")
    ] == ("interaction",)
    assert skill_axis.LEXICAL_MODALITY["spontaneous_use"] == "interaction"
    assert (
        skill_axis.MODALITIES_BY_ASSESSED_CHANNEL[("spontaneous_use", "spoken")]
        != (skill_axis.LEXICAL_MODALITY["spontaneous_use"],)
    )


def test_unknown_channel_degrades_exactly_to_v362():
    # Sin canal declarado la modalidad es EXACTAMENTE la de V3.62 para cada skill.
    for skill, modality in skill_axis.LEXICAL_MODALITY.items():
        rows = skill_state_service.skill_state_sources(
            lexicon=[
                _lexicon_ledger(
                    day="2026-01-01", skill=skill, assessed=skill, activity_id=""
                )
            ]
        )
        assert rows[0]["modality"] == modality
    # Un elemento de `ASSESSMENT_MODES` sin emisor no inventa modalidad.
    assert skill_axis.modality_for("receptive") == ""
    assert "receptive" in skill_axis.UNMAPPED_REASONS


# ---------------------------------------------------------------------------
# C · Observed Task Difficulty 2.0 empírica (P2-20)
# ---------------------------------------------------------------------------


def test_served_ceiling_minus_credited_ceiling_measures_scaffolding():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01",
                served="lexical:5",
                earned="lexical:3",
                support_level="guided",
            )
        ]
    )
    assert observed_difficulty.served_ceiling(rows) == {"lexical": 5}
    assert observed_difficulty.credited_ceiling(rows) == {"lexical": 3}
    assert observed_difficulty.scaffolding_gap(rows) == {"lexical": 2}


def test_experienced_load_is_declared_monotone_and_ignores_unknown_facts():
    base = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01", served="lexical:3", earned="lexical:3"
            )
        ]
    )[0]
    # Sin coste observado, la carga experimentada es la servida (no se inventa).
    assert observed_difficulty.experienced_load(base) == {"lexical": 3}

    slow = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01",
                served="lexical:3",
                earned="lexical:3",
                response_time_ms=9000,
            )
        ]
    )[0]
    slower = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(
                day="2026-01-01",
                served="lexical:3",
                earned="lexical:3",
                response_time_ms=25000,
            )
        ]
    )[0]
    # Monótona: más coste declarado nunca baja la carga experimentada.
    assert observed_difficulty.experienced_load(slow)["lexical"] >= 3
    assert (
        observed_difficulty.experienced_load(slower)["lexical"]
        >= observed_difficulty.experienced_load(slow)["lexical"]
    )
    # Y acotada al rango declarado de carga.
    assert observed_difficulty.experienced_load(slower)["lexical"] <= 5


def test_observed_task_difficulty_2_needs_spaced_sample():
    same_day = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(day="2026-01-01", served="lexical:4", earned="lexical:4"),
            _lexicon_ledger(day="2026-01-01", served="lexical:5", earned="lexical:5"),
        ]
    )
    undecided = observed_difficulty.observed_task_difficulty_2(same_day)
    assert undecided["served_ceiling"] == {}
    assert undecided["credited_ceiling"] == {}

    spaced = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(day="2026-01-01", served="lexical:4", earned="lexical:4"),
            _lexicon_ledger(day="2026-01-02", served="lexical:5", earned="lexical:5"),
        ]
    )
    decided = observed_difficulty.observed_task_difficulty_2(spaced)
    assert decided["served_ceiling"] == {"lexical": 5}
    assert decided["credited_ceiling"] == {"lexical": 5}
    assert decided["samples"] == 2
    assert decided["days"] == 2


def test_empirical_layer_is_deterministic_and_reads_no_clock():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lexicon_ledger(day="2026-01-01", served="lexical:4", earned="lexical:3"),
            _lexicon_ledger(day="2026-01-02", served="lexical:5", earned="lexical:5"),
        ]
    )
    first = observed_difficulty.observed_task_difficulty_2(rows)
    second = observed_difficulty.observed_task_difficulty_2(rows)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # El módulo puro no lee reloj ni aleatoriedad.
    source = (_BACKEND / "services" / "observed_difficulty.py").read_text("utf-8")
    for forbidden in ("import time", "import datetime", "import random", "hash("):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# D · Confianza de evaluación (P2-19)
# ---------------------------------------------------------------------------


def test_assessment_confidence_is_separate_from_statistical_confidence():
    rows = skill_state_service.skill_state_sources(
        listening=[
            _listening_ledger(day="2026-01-01", row_id="1"),
            _listening_ledger(day="2026-01-02", row_id="2"),
        ]
    )
    entry = skill_state_service.skill_state(rows)["listening"]["gist"]
    # La confianza ESTADÍSTICA no cambia de fórmula (éxitos / intentos).
    assert entry["confidence"] == 1.0
    # ...y la de EVALUACIÓN es otra cosa: banda declarada + motivos.
    assert entry["assessment_confidence"]["band"] in ("low", "medium", "high")
    assert isinstance(entry["assessment_confidence"]["reasons"], list)


def test_slow_tts_and_transcript_lower_assessment_confidence():
    clean = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            listening=[
                _listening_ledger(day="2026-01-01", row_id="1"),
                _listening_ledger(day="2026-01-02", row_id="2"),
            ]
        )
    )["listening"]["gist"]
    aided = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            listening=[
                _listening_ledger(
                    day="2026-01-01", row_id="1", speed_used="slow", transcript_used=1
                ),
                _listening_ledger(
                    day="2026-01-02", row_id="2", speed_used="slow", transcript_used=1
                ),
            ]
        )
    )["listening"]["gist"]
    order = ("low", "medium", "high")
    assert order.index(aided["assessment_confidence"]["band"]) <= order.index(
        clean["assessment_confidence"]["band"]
    )
    assert aided["assessment_confidence"]["reasons"]


def test_unknown_facts_give_the_lowest_band():
    entry = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            lexicon=[
                _lexicon_ledger(
                    day="2026-01-01",
                    skill="spontaneous_use",
                    assessed="",
                    served="lexical:3",
                    earned="lexical:3",
                    activity_id="",
                ),
                _lexicon_ledger(
                    day="2026-01-02",
                    skill="spontaneous_use",
                    assessed="",
                    served="lexical:3",
                    earned="lexical:3",
                    activity_id="",
                ),
            ]
        )
    )["interaction"][""]
    assert entry["assessment_confidence"]["band"] == "low"
    assert "channel_unknown" in entry["assessment_confidence"]["reasons"]


# ---------------------------------------------------------------------------
# E · Pronunciación con criterio declarado (P2-11)
# ---------------------------------------------------------------------------


def test_declared_rubric_criterion_becomes_the_competence():
    criterion = PRONUNCIATION_CRITERIA[0]
    rows = skill_state_service.skill_state_sources(
        academy=[
            _academy_ledger(
                day="2026-01-01", skill="pronunciation", item_id=criterion
            )
        ],
        objectives=_OBJECTIVES,
    )
    assert len(rows) == 1
    assert rows[0]["modality"] == "pronunciation"
    assert rows[0]["competence"] == criterion


def test_practice_route_keeps_empty_competence_with_reason():
    rows = skill_state_service.skill_state_sources(
        pronunciation=[_pronunciation_ledger(day="2026-01-01")]
    )
    assert rows[0]["modality"] == "pronunciation"
    assert rows[0]["competence"] == ""
    assert skill_state_service.PRONUNCIATION_PRACTICE_REASON.strip()


# ---------------------------------------------------------------------------
# F · Capas declaradas de listening (P2-12)
# ---------------------------------------------------------------------------


def test_layer_axis_reuses_skill_layer_without_new_vocabulary():
    declared = skill_axis.COMPETENCE_LAYERS_BY_MODALITY
    assert set(declared) == {"listening"}
    listening = declared["listening"]
    # Sin vocabulario nuevo: las capas son las de `SKILL_LAYER`.
    assert set(listening.values()) <= set(LISTENING_LAYERS)
    assert listening == {
        competence: layer
        for competence, layer in SKILL_LAYER.items()
        if competence in skill_axis.COMPETENCES_BY_MODALITY["listening"]
    }
    assert skill_axis.layer_for("listening", "gist") == "comprehension"
    assert skill_axis.layer_for("writing", "gist") == ""


def test_production_subskills_are_outside_the_layer_axis():
    declared = skill_axis.COMPETENCE_LAYERS_BY_MODALITY["listening"]
    for production in ("dictation", "shadowing"):
        assert production not in declared
        assert production in skill_axis.COMPETENCES_BY_MODALITY["listening"]
        # Fuera de capa CON motivo escrito (no es un olvido).
        assert skill_axis.UNLAYERED_COMPETENCE_REASONS[production].strip()


def test_summary_exposes_the_declared_layers():
    state = skill_state_service.empty_skill_state()
    state["listening"]["gist"] = {"state": "functional"}
    state["listening"]["inference"] = {"state": "developing"}
    summary = skill_state_service.skill_state_summary(state)
    layers = summary["listening"]["layers"]
    assert set(layers) == set(LISTENING_LAYERS)
    assert layers["comprehension"]["state"] == "functional"
    assert layers["inference"]["state"] == "developing"
    assert layers["recognition"]["state"] == "not_started"


# ---------------------------------------------------------------------------
# G · Seam de política del gate (P2-14)
# ---------------------------------------------------------------------------


def test_only_the_default_gate_policy_is_declared():
    # Añadir una política alternativa OBLIGA a declararla aquí y a actualizar el
    # docstring de `gate_for`: el test falla en cuanto exista una sola.
    assert competence.COMPETENCE_GATE_POLICIES == {}
    for args in (
        ("listening", "gist", "listening"),
        ("writing", "", "lexicon"),
        ("interaction", "", "lexicon"),
    ):
        assert competence.gate_for(*args) is competence.DEFAULT_COMPETENCE_GATE


def test_gate_is_byte_identical_to_v362():
    gate = competence.DEFAULT_COMPETENCE_GATE
    assert gate.min_samples == learner_skill.OBSERVED_MIN_SAMPLES
    assert gate.min_days == learner_skill.OBSERVED_MIN_DAYS
    rows = skill_state_service.skill_state_sources(
        listening=[
            _listening_ledger(day="2026-01-01", row_id="1"),
            _listening_ledger(day="2026-01-02", row_id="2"),
        ]
    )
    # Dos éxitos en dos días cruzan el gate; uno solo no.
    assert skill_state_service.skill_state(rows)["listening"]["gist"]["samples"] == 2
    assert (
        skill_state_service.skill_state(rows[:1])["listening"].get("gist") is None
    )


# ---------------------------------------------------------------------------
# H · Frescura del estado (P2-18)
# ---------------------------------------------------------------------------


def test_fingerprint_changes_when_any_of_the_four_sources_grows(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    base = evidence_repo.evidence_fingerprint(uid)

    _seed_lexicon_evidence(uid, "recall", ["2026-01-01"], "lexical:3")
    after_lexicon = evidence_repo.evidence_fingerprint(uid)
    assert after_lexicon != base

    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_evidence "
            "(user_id, level_id, objective_id, skill, item_id, item_type, "
            "difficulty, source, result, curriculum_version, assessment_version, "
            "evidence_kind, created_at) VALUES "
            "(?, 'a2', 'obj-1', 'listening', 'item', 'mcq', 1, 'x', 1, '', '', "
            "'familiar', '2026-01-01T00:00:00+00:00')",
            (uid,),
        )
    after_academy = evidence_repo.evidence_fingerprint(uid)
    assert after_academy != after_lexicon

    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, created_at) "
            "VALUES (?, 'q1', 0, 1, '2026-01-01T00:00:00+00:00')",
            (uid,),
        )
    after_listening = evidence_repo.evidence_fingerprint(uid)
    assert after_listening != after_academy

    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO pronunciation_attempts "
            "(user_id, expected, heard, score, level, created_at) "
            "VALUES (?, 'hello', 'hello', 90, 'a1', '2026-01-01T00:00:00+00:00')",
            (uid,),
        )
    after_pronunciation = evidence_repo.evidence_fingerprint(uid)
    assert after_pronunciation != after_listening


def test_stale_cache_is_never_reported_fresh(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Sin caché no hay frescura.
    assert profile_repo.skill_state_is_fresh(uid) is False

    # Con caché SELLADA con el fingerprint del momento, sí es fresca.
    stamped = evidence_repo.evidence_fingerprint(uid)
    profile_repo.set_skill_state(uid, "{}", source=stamped)
    assert profile_repo.skill_state_is_fresh(uid) is True

    # En cuanto entra evidencia nueva, la misma caché deja de ser fresca.
    _seed_lexicon_evidence(uid, "recall", ["2026-01-01"], "lexical:3")
    assert profile_repo.skill_state_is_fresh(uid) is False

    # Una caché SIN sello (legacy) nunca se reporta como fresca.
    profile_repo.set_skill_state(uid, "{}", source="")
    assert profile_repo.skill_state_is_fresh(uid) is False


def test_migration_is_idempotent_and_legacy_rows_default_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.init_db()
    assert "skill_state_source" in _columns("learning_profile")
    uid = users_repo.create_user("A")["id"]
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile (user_id, skill_state, updated_at) "
            "VALUES (?, '{}', '2026-01-01T00:00:00+00:00')",
            (uid,),
        )
    row = profile_repo.get_profile(uid)
    assert row["skill_state_source"] == ""


# ---------------------------------------------------------------------------
# Contrato aditivo (HTTP e2e)
# ---------------------------------------------------------------------------


def test_profile_endpoint_is_additive_with_the_new_keys(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_lexicon_evidence(
        uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4"
    )
    with closing(db._conn()) as conn, conn:
        for day, row_id in (("2026-01-01", 1), ("2026-01-02", 2)):
            conn.execute(
                "INSERT INTO listening_attempts "
                "(user_id, question_id, answer_index, correct, skill, created_at) "
                "VALUES (?, ?, 0, 1, 'gist', ?)",
                (uid, f"q{row_id}", f"{day}T09:00:00+00:00"),
            )
    asyncio.run(profile_domain.get_profile_summary(uid))

    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": uid}).json()
    entry = body["skill_state"]["listening"]["gist"]
    # Todas las claves de V3.62 siguen ahí...
    assert {
        "state",
        "samples",
        "days",
        "score",
        "confidence",
        "dimensions",
        "sources",
    } <= set(entry)
    # ...y las nuevas son ADITIVAS.
    assert {"observations", "occasions"} <= set(entry)
    assert "band" in entry["assessment_confidence"]
    assert entry["observed_task_difficulty_2"]["samples"] == 2
    # El resumen derivado gana las capas declaradas.
    assert set(body["skill_state_summary"]["listening"]["layers"]) == set(
        LISTENING_LAYERS
    )
