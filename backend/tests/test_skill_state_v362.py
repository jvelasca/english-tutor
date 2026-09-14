"""V3.62 — Student Skill State 4.0 (modalidad × competencia).

Hasta V3.61 convivían DOS modelos del mismo alumno que nunca se tocaban: el
adaptativo léxico (`LEXICAL_SKILLS` × `DIFFICULTY_DIMENSIONS`) y el curricular
(`MASTERY_SKILLS` × 4 estados pedagógicos). V3.62 construye UN estado
`{modalidad: {competencia: entry}}` alimentado por las CUATRO fuentes de
evidencia con la MISMA puerta espaciada, **sin tocar** el camino que decide
tareas (P1-03 de la auditoría `S`).

Aquí se cubre lo NUEVO: totalidad de la taxonomía, puerta espaciada única,
no-invención de competencias, aislamiento entre modalidades, paridad con el gate
de `services.competence` y con el estado léxico de V3.54, determinismo,
degradación neutra, migración idempotente, contrato aditivo y —la invariante
central— el **no-op probado del camino de decisión**.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from domain import learner_state as learner_state_domain
from domain import profile as profile_domain
from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from services import competence, difficulty, learner_skill, skill_axis
from services import skill_state as skill_state_service
from services.evidence import observed_signals

_BACKEND = Path(__file__).resolve().parent.parent

# Vocabularios que el estado debe poder leer. El test los importa REALES, así que
# añadir una cadena a cualquiera de ellos rompe la suite en lugar de colarse.
def _real_vocabularies() -> dict[str, tuple[str, ...]]:
    from services.curriculum import CANONICAL_SKILLS, SUBSKILLS
    from services.evidence import LEXICAL_SKILLS, PRODUCTION_CHANNEL_SKILL
    from services.listening import LISTENING_SUBSKILLS, SKILL_LAYER
    from services.mastery import MASTERY_SKILLS
    from services.pronunciation import PRONUNCIATION_CRITERIA
    from services.speaking import SPEAKING_CRITERIA
    from services.task_semantics import ASSESSMENT_MODES
    from services.writing import WRITING_CRITERIA

    return {
        "evidence.LEXICAL_SKILLS": tuple(LEXICAL_SKILLS),
        "evidence.PRODUCTION_CHANNEL_SKILL": tuple(PRODUCTION_CHANNEL_SKILL),
        "curriculum.CANONICAL_SKILLS": tuple(CANONICAL_SKILLS),
        "mastery.MASTERY_SKILLS": tuple(MASTERY_SKILLS),
        "curriculum.SUBSKILLS": tuple(
            raw for subskills in SUBSKILLS.values() for raw in subskills
        ),
        "listening.LISTENING_SUBSKILLS": tuple(LISTENING_SUBSKILLS),
        "listening.SKILL_LAYER": tuple(SKILL_LAYER),
        "speaking.SPEAKING_CRITERIA": tuple(SPEAKING_CRITERIA),
        "writing.WRITING_CRITERIA": tuple(WRITING_CRITERIA),
        "pronunciation.PRONUNCIATION_CRITERIA": tuple(PRONUNCIATION_CRITERIA),
        "task_semantics.ASSESSMENT_MODES": tuple(ASSESSMENT_MODES),
    }


_REAL_VOCABULARIES = _real_vocabularies()


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _columns(table: str) -> set[str]:
    with closing(db._conn()) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _lex_row(
    skill: str,
    *,
    day: str,
    dimensions: str,
    success: bool = True,
    assessed: str = "",
) -> dict:
    """Fila del ledger léxico como la entrega `list_observed_rows`."""
    return {
        "occurred_at": f"{day}T10:00:00+00:00",
        "skill": skill,
        "assessed_skill": assessed or skill,
        "success": success,
        "observed_difficulty": dimensions,
        "served_difficulty": dimensions,
        "observed_task_difficulty": dimensions,
    }


def _seed_academy(
    uid: str,
    *,
    level_id: str,
    objective_id: str,
    skill: str,
    result: float,
    day: str,
    item_type: str = "mcq",
    kind: str = "familiar",
) -> None:
    """Inserta una fila de `academy_evidence` con `created_at` CONTROLADO."""
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_evidence "
            "(user_id, level_id, objective_id, skill, item_id, item_type, "
            "difficulty, source, result, curriculum_version, assessment_version, "
            "evidence_kind, context_id, activity_id, task_type, support_level, "
            "created_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, '', '', '', '', ?)",
            (
                uid,
                level_id,
                objective_id,
                skill,
                "item",
                item_type,
                1,
                "objective_assessment",
                result,
                kind,
                f"{day}T12:00:00+00:00",
            ),
        )


def _seed_listening(
    uid: str, *, skill: str, correct: bool, day: str, score: float | None = None
) -> None:
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, skill, difficulty, "
            "response_time_ms, replay_count, topic, realized_difficulty, "
            "task_type, score, layer, speed_used, stage, transcript_used, "
            "segments_replayed, created_at) VALUES "
            "(?, 'q1', 0, ?, ?, 1, NULL, 0, '', 0, 'mcq', ?, '', 'normal', "
            "'', '', 0, ?)",
            (uid, 1 if correct else 0, skill, score, f"{day}T09:00:00+00:00"),
        )


def _seed_pronunciation(uid: str, *, score: int, day: str) -> None:
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO pronunciation_attempts "
            "(user_id, expected, heard, score, level, created_at) "
            "VALUES (?, 'hello', 'hello', ?, 'a1', ?)",
            (uid, score, f"{day}T08:00:00+00:00"),
        )


def _seed_lexicon(uid: str, skill: str, days: list[str], dimensions: str) -> None:
    for day in days:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill=skill,
            assessed_skill=skill,
            success=True,
            served_difficulty=dimensions,
            observed_task_difficulty=dimensions,
            occurred_at=f"{day}T07:00:00+00:00",
        )


# ---------------------------------------------------------------------------
# A · Taxonomía declarada
# ---------------------------------------------------------------------------


def test_taxonomy_is_total_for_every_declared_vocabulary():
    for name, strings in _REAL_VOCABULARIES.items():
        declared = skill_axis.MODALITY_BY_VOCABULARY.get(name)
        assert declared is not None, f"vocabulario sin declarar en la taxonomía: {name}"
        for raw in strings:
            # Totalidad = mapeada o declarada SIN modalidad con motivo escrito.
            assert raw in declared or raw in skill_axis.UNMAPPED_REASONS, (
                f"{name}:{raw} no está en la taxonomía"
            )
            assert skill_axis.modality_for(raw) in ("", *skill_axis.SKILL_MODALITIES)
        # Todo valor declarado pertenece al vocabulario real (no se inventa).
        for raw in declared:
            assert raw in strings, f"{name}:{raw} declarado y no existe en el árbol"


def test_unmapped_only_declares_real_strings_with_reason():
    for raw in skill_axis.UNMAPPED:
        assert not skill_axis.modality_for(raw), f"{raw} está mapeado y en UNMAPPED"
        assert skill_axis.UNMAPPED_REASONS[raw].strip()
    # `receptive` es el caso declarado: canal sin emisor (V3.13).
    assert "receptive" in skill_axis.UNMAPPED


def test_every_modality_declares_its_competences():
    assert set(skill_axis.COMPETENCES_BY_MODALITY) == set(skill_axis.SKILL_MODALITIES)
    # Toda subdestreza del currículum pertenece a la modalidad que la declara.
    from services.curriculum import SUBSKILLS

    for skill, subskills in SUBSKILLS.items():
        declared = skill_axis.COMPETENCES_BY_MODALITY[skill]
        for raw in subskills:
            assert raw in declared


def test_listening_competences_are_the_declared_union():
    """La discrepancia LISTENING_SUBSKILLS / SUBSKILLS["listening"] es explícita."""
    from services.curriculum import SUBSKILLS
    from services.listening import LISTENING_SUBSKILLS

    declared = set(skill_axis.COMPETENCES_BY_MODALITY["listening"])
    assert set(SUBSKILLS["listening"]) <= declared
    assert set(LISTENING_SUBSKILLS) <= declared
    # Las subdestrezas que solo declara el motor servido (y que graba de verdad).
    assert {"numbers", "note_taking", "prediction", "sequencing"} <= declared
    # Y las que solo declara el currículum (can-do del nivel).
    assert {"accents", "real_world"} <= declared


def test_canonical_competence_normalizes_without_fuzzy_matching():
    assert skill_axis.canonical_competence("listening", "  Gist ") == "gist"
    assert skill_axis.canonical_competence("listening", "gis") == ""
    assert skill_axis.canonical_competence("listening", "spelling") == ""
    assert skill_axis.canonical_competence("unknown", "gist") == ""
    assert skill_axis.canonical_competence("speaking", "spelling") == ""
    # La MISMA cadena se resuelve por MODALIDAD (el eje menor es por modalidad):
    # `register` es subdestreza declarada de listening, speaking y writing, pero
    # no de pronunciation.
    for modality in ("listening", "speaking", "writing"):
        assert skill_axis.canonical_competence(modality, "register") == "register"
    assert skill_axis.canonical_competence("pronunciation", "register") == ""


def test_modality_of_lexical_ledger_declares_the_channel():
    assert skill_axis.MODALITY_OF["written_production"] == "writing"
    assert skill_axis.MODALITY_OF["spoken_production"] == "speaking"
    assert skill_axis.MODALITY_OF["recall"] == "vocabulary"
    # `chat` es TEXTO en esta app: la condición sin guion no es producción oral.
    assert skill_axis.MODALITY_OF["spontaneous_use"] == "interaction"
    assert skill_axis.MODALITY_OF["chat"] == "interaction"


# ---------------------------------------------------------------------------
# B · Puerta espaciada única
# ---------------------------------------------------------------------------


def test_spaced_gate_requires_two_successes_on_two_days():
    rows = skill_state_service.skill_state_sources(
        listening=[
            {"skill": "gist", "correct": 1, "created_at": "2026-01-01T10:00:00"},
            {"skill": "gist", "correct": 1, "created_at": "2026-01-02T10:00:00"},
        ]
    )
    state = skill_state_service.skill_state(rows)
    assert state["listening"]["gist"]["samples"] == 2
    assert state["listening"]["gist"]["days"] == 2

    # Una sola muestra (o dos el mismo día) no declara nada...
    one = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            listening=[{"skill": "gist", "correct": 1, "created_at": "2026-01-01"}]
        )
    )
    assert one["listening"] == {}
    same_day = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            listening=[
                {"skill": "gist", "correct": 1, "created_at": "2026-01-01T09:00"},
                {"skill": "gist", "correct": 1, "created_at": "2026-01-01T21:00"},
            ]
        )
    )
    assert same_day["listening"] == {}
    # ...y un fallo no acredita muestra (fallo + acierto = 1 éxito en 1 día).
    mixed = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            listening=[
                {"skill": "gist", "correct": 1, "created_at": "2026-01-01"},
                {"skill": "gist", "correct": 0, "created_at": "2026-01-02"},
            ]
        )
    )
    assert mixed["listening"] == {}


def test_spaced_gate_does_not_block_other_keys():
    rows = skill_state_service.skill_state_sources(
        listening=[
            {"skill": "gist", "correct": 1, "created_at": "2026-01-01"},
            {"skill": "gist", "correct": 1, "created_at": "2026-01-02"},
            {"skill": "detail", "correct": 1, "created_at": "2026-01-01"},
        ]
    )
    state = skill_state_service.skill_state(rows)
    assert set(state["listening"]) == {"gist"}
    # Las demás modalidades siguen presentes y vacías.
    assert state["speaking"] == {}


def test_state_always_has_every_canonical_modality():
    state = skill_state_service.skill_state([])
    assert tuple(state) == skill_axis.SKILL_MODALITIES
    assert all(entry == {} for entry in state.values())
    assert state == skill_state_service.empty_skill_state()


# ---------------------------------------------------------------------------
# C · No invención de competencias y paridad con el gate
# ---------------------------------------------------------------------------


def test_lexical_only_student_declares_no_competence():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lex_row("written_production", day="2026-01-01", dimensions="lexical:3"),
            _lex_row("written_production", day="2026-01-02", dimensions="lexical:3"),
        ]
    )
    state = skill_state_service.skill_state(rows)
    assert set(state["writing"]) == {""}
    entry = state["writing"][""]
    assert entry["dimensions"] == {"lexical": 3}
    # Ninguna competencia de gramática/ortografía/fonética aparece por la carga.
    assert all(not competence for competence in state["writing"])
    for modality in ("grammar", "listening", "speaking", "pronunciation"):
        assert state[modality] == {}


def test_writing_evidence_does_not_touch_other_modalities():
    rows = skill_state_service.skill_state_sources(
        academy=[],
        lexicon=[
            _lex_row("written_production", day="2026-01-01", dimensions="lexical:4"),
            _lex_row("written_production", day="2026-01-02", dimensions="lexical:4"),
        ],
    )
    state = skill_state_service.skill_state(rows, level="B1")
    assert state["writing"][""]["state"] in competence.STATE_ORDER
    for modality in ("speaking", "listening", "pronunciation", "interaction"):
        assert state[modality] == {}


def test_state_uses_the_declared_gate_not_a_new_threshold():
    """El estado coincide con `competence.competence_state` sobre su propia entrada."""
    good = [
        {
            "modality": "listening",
            "competence": "gist",
            "occurred_on": day,
            "occurred_at": f"{day}T10:00:00",
            "success": True,
            "score": 0.9,
            "dimensions": {},
            "source": "listening",
            "kind": "",
            "production": False,
        }
        for day in ("2026-01-01", "2026-01-02", "2026-01-03")
    ]
    state = skill_state_service.skill_state(good, level="A2")
    entry = state["listening"]["gist"]
    expected = competence.competence_state(
        {
            "evidence_count": 3,
            "score": 0.9,
            "confidence": 1.0,
            "evidence_by_kind": {
                "familiar": 0,
                "transfer": 0,
                "novel": 0,
                "delayed": 0,
            },
            "production_count": 0,
            "review_due": False,
        },
        "listening",
        "A2",
    )
    assert entry["state"] == expected["state"]


def test_lexical_dimensions_match_the_v354_state_exactly():
    """Paridad EXACTA con `observed_skill_capacity` (V3.54), sin re-derivar."""
    rows = [
        _lex_row("written_production", day="2026-01-01", dimensions="lexical:5"),
        _lex_row("written_production", day="2026-01-02", dimensions="lexical:5"),
        # Misma dimensión, pero un solo día: no acredita carga en la puerta
        # por dimensión (V3.54) ni en el estado nuevo.
        _lex_row("written_production", day="2026-01-02", dimensions="syntax:4"),
    ]
    signals = observed_signals(rows)
    expected = learner_skill.observed_skill_capacity(signals)
    state = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(lexicon=rows)
    )
    for skill, modality in skill_axis.LEXICAL_MODALITY.items():
        entry = state[modality].get("")
        capacity = expected.get(skill, {})
        assert (entry["dimensions"] if entry else {}) == capacity


def test_production_evidence_is_declared_for_the_gate():
    speaking = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(
            academy=[
                {
                    "level_id": "a1",
                    "objective_id": "",
                    "skill": "speaking",
                    "item_type": "speaking",
                    "result": 0.9,
                    "created_at": "2026-01-01T10:00:00",
                }
            ]
        )
    )
    # Fila sin objetivo resoluble: intento sin éxito declarado (frontera F-K3).
    assert speaking["speaking"] == {}


def test_academy_competence_comes_from_the_objective_subskills():
    index = {
        ("a1", "o1"): (
            ("fluency", "register", "spelling"),
            {"speaking": 0.8},
        )
    }
    rows = skill_state_service.skill_state_sources(
        academy=[
            {
                "level_id": "a1",
                "objective_id": "o1",
                "skill": "speaking",
                "item_type": "speaking",
                "result": 0.9,
                "created_at": f"2026-01-0{day}T10:00:00",
            }
            for day in (1, 2)
        ],
        objectives=index,
    )
    # `spelling` es subdestreza de writing/vocabulary, no de speaking: se descarta.
    assert {row["competence"] for row in rows} == {"fluency", "register"}
    state = skill_state_service.skill_state(rows)
    assert set(state["speaking"]) == {"fluency", "register"}
    assert state["speaking"]["fluency"]["state"] in competence.STATE_ORDER


def test_academy_objective_without_subskills_falls_back_to_modality():
    index = {("a1", "o1"): ((), {"grammar": 0.7})}
    rows = skill_state_service.skill_state_sources(
        academy=[
            {
                "level_id": "a1",
                "objective_id": "o1",
                "skill": "grammar",
                "result": 0.75,
                "created_at": f"2026-01-0{day}T10:00:00",
            }
            for day in (1, 2)
        ],
        objectives=index,
    )
    assert {row["competence"] for row in rows} == {""}
    # 0.75 >= 0.7 (umbral declarado del objetivo): acredita éxito.
    assert all(row["success"] for row in rows)


def test_pronunciation_score_is_normalized_from_the_table_schema():
    rows = skill_state_service.skill_state_sources(
        pronunciation=[
            {"score": 90, "created_at": "2026-01-01"},
            {"score": 85, "created_at": "2026-01-02"},
        ]
    )
    assert {row["modality"] for row in rows} == {"pronunciation"}
    assert all(row["score"] == 0.9 or row["score"] == 0.85 for row in rows)
    assert all(row["success"] for row in rows)
    state = skill_state_service.skill_state(rows)
    assert set(state["pronunciation"]) == {""}
    # 90/100 y 85/100 son 0.875 de media, por encima del suelo 0.6 de la destreza.
    assert state["pronunciation"][""]["score"] == 0.875


def test_listening_undeclared_subskill_is_not_invented():
    rows = skill_state_service.skill_state_sources(
        listening=[
            {"skill": "not_a_subskill", "correct": 1, "created_at": "2026-01-01"},
            {"skill": "not_a_subskill", "correct": 1, "created_at": "2026-01-02"},
        ]
    )
    assert {row["competence"] for row in rows} == {""}


# ---------------------------------------------------------------------------
# D · Determinismo, resumen y normalización
# ---------------------------------------------------------------------------


def test_state_is_deterministic_and_serializes_with_sorted_keys():
    rows = skill_state_service.skill_state_sources(
        lexicon=[
            _lex_row("spoken_production", day="2026-01-01", dimensions="lexical:3"),
            _lex_row("spoken_production", day="2026-01-02", dimensions="lexical:3"),
        ],
        listening=[
            {"skill": "gist", "correct": 1, "created_at": "2026-01-01"},
            {"skill": "gist", "correct": 1, "created_at": "2026-01-02"},
        ],
    )
    first = json.dumps(
        skill_state_service.skill_state(rows, level="A2", now="2026-02-01T00:00:00"),
        sort_keys=True,
    )
    second = json.dumps(
        skill_state_service.skill_state(rows, level="A2", now="2026-02-01T00:00:00"),
        sort_keys=True,
    )
    assert first == second
    # Sin `now` la función no lee el reloj: `review_due` es False.
    state = skill_state_service.skill_state(rows, level="A2")
    assert state["listening"]["gist"]["dimensions"] == {}


def test_summary_is_derived_and_reads_the_highest_state():
    state = skill_state_service.empty_skill_state()
    state["listening"]["gist"] = {"state": "functional"}
    state["listening"][""] = {"state": "developing"}
    summary = skill_state_service.skill_state_summary(state)
    assert summary["listening"]["state"] == "functional"
    assert summary["listening"]["competences_with_sample"] == ["", "gist"]
    assert summary["listening"]["coverage"]["covered"] == 1
    assert summary["listening"]["coverage"]["total"] == len(
        skill_axis.COMPETENCES_BY_MODALITY["listening"]
    )
    # `interaction` no declara competencias: la cobertura no divide por cero.
    assert summary["interaction"]["coverage"] == {"covered": 0, "total": 0}


def test_normalize_skill_state_keeps_shape_and_drops_garbage():
    assert skill_state_service.normalize_skill_state("") == (
        skill_state_service.empty_skill_state()
    )
    assert skill_state_service.normalize_skill_state("no-json") == (
        skill_state_service.empty_skill_state()
    )
    normalized = skill_state_service.normalize_skill_state(
        '{"listening": {"gist": {"state": "functional"}, "bad": 3}}'
    )
    assert normalized["listening"] == {"gist": {"state": "functional"}}
    assert tuple(normalized) == skill_axis.SKILL_MODALITIES


# ---------------------------------------------------------------------------
# E · Persistencia aditiva e idempotente
# ---------------------------------------------------------------------------


def test_migration_is_idempotent_and_defaults_to_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert "skill_state" in _columns("learning_profile")
    db.init_db()  # repetible: no duplica ni rompe
    assert "skill_state" in _columns("learning_profile")
    assert profile_repo.get_profile(uid) is None
    profile_repo.set_level_state(uid, estimated_level="A2", demonstrated_level="")
    row = profile_repo.get_profile(uid)
    assert row["skill_state"] == ""
    assert profile_repo.set_skill_state(uid, "{}")["skill_state"] == "{}"
    # El escritor dedicado no toca el resto de la caché.
    assert profile_repo.get_profile(uid)["estimated_level"] == "A2"


def test_set_cefr_preserves_the_unified_state(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    profile_repo.set_level_state(uid, estimated_level="A2", demonstrated_level="")
    profile_repo.set_skill_state(uid, '{"listening": {}}')
    profile_repo.set_cefr(uid, "B1")
    row = profile_repo.get_profile(uid)
    assert row["cefr_level"] == "B1"
    assert row["skill_state"] == '{"listening": {}}'


# ---------------------------------------------------------------------------
# F · Extremo a extremo: contrato aditivo y degradación neutra
# ---------------------------------------------------------------------------

_V361_KEYS = {
    "user_id",
    "current_level",
    "estimated_level",
    "demonstrated_level",
    "observed_level",
    "observed_capacity",
    "observed_skill_capacity",
    "observed_skill_level",
    "skill_coverage",
    "estimated_bands",
    "estimated_descriptor",
    "estimated_confidence",
    "overall_ability",
    "target_level",
    "skills",
    "competence_states",
    "evidence_depth",
    "readiness",
    "cefr_history",
    "vocabulary_size",
    "vocabulary_exposed",
    "vocabulary_mastered",
    "top_words",
    "recurring_errors",
    "mastered_errors",
    "mastered_count",
    "pronunciation_average",
    "recommendations",
}


def test_profile_endpoint_is_additive(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": uid}).json()
    assert _V361_KEYS <= set(body)
    assert set(body["skill_state"]) == set(skill_axis.SKILL_MODALITIES)
    assert set(body["skill_state_summary"]) == set(skill_axis.SKILL_MODALITIES)


def test_profile_endpoint_degrades_neutrally_without_evidence(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": uid}).json()
    assert body["skill_state"] == skill_state_service.empty_skill_state()
    assert body["skill_state_summary"] == skill_state_service.skill_state_summary(
        skill_state_service.empty_skill_state()
    )
    # La caché queda escrita con el JSON determinista del estado neutro.
    row = profile_repo.get_profile(uid)
    assert json.loads(row["skill_state"]) == skill_state_service.empty_skill_state()


def test_profile_endpoint_feeds_every_available_source(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_lexicon(uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    _seed_listening(uid, skill="gist", correct=True, day="2026-01-01")
    _seed_listening(uid, skill="gist", correct=True, day="2026-01-02")
    _seed_pronunciation(uid, score=90, day="2026-01-01")
    _seed_pronunciation(uid, score=88, day="2026-01-02")
    _seed_academy(
        uid,
        level_id="a1",
        objective_id="",
        skill="grammar",
        result=0.9,
        day="2026-01-01",
    )
    _seed_academy(
        uid,
        level_id="a1",
        objective_id="",
        skill="grammar",
        result=0.9,
        day="2026-01-02",
    )
    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": uid}).json()
    state = body["skill_state"]
    sources = {
        row
        for entries in state.values()
        for entry in entries.values()
        for row in entry["sources"]
    }
    assert {"lexicon", "listening", "pronunciation"} <= sources
    assert state["writing"][""]["dimensions"] == {"lexical": 4}
    assert state["listening"]["gist"]["days"] == 2
    assert state["pronunciation"][""]["samples"] == 2


# ---------------------------------------------------------------------------
# G · La invariante central: el camino de decisión NO cambia
# ---------------------------------------------------------------------------


_RICH_STATE = {
    "speaking": {"fluency": {"state": "demonstrated", "samples": 9, "days": 9}},
    "writing": {"": {"state": "functional", "dimensions": {"lexical": 5}}},
    "listening": {"gist": {"state": "demonstrated", "samples": 7, "days": 7}},
    "interaction": {"": {"state": "functional"}},
}


_NOW = "2026-09-13T10:00:00+00:00"
_PRODUCTION_EVIDENCE = {
    "error_types": {"wrong_word": 2},
    "skill_successes": {"recall": 2, "spoken_production": 2},
}


def _lexicon_rows_of(uid: str) -> list[dict]:
    return evidence_repo.list_observed_rows(uid)


def _drill_item(learner_state: dict) -> str:
    """Payload REAL del drill léxico: la celda que consume el camino de decisión."""
    row = {
        "word": "river",
        "cefr": "B1",
        "exposure_count": 3,
        "writing_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    card = {
        "target_id": "river",
        "due_at": "2026-09-12T10:00:00+00:00",
        "state": "review",
        "stability": 5.0,
        "last_review_at": "2026-09-09T10:00:00+00:00",
    }
    from services import lexicon

    item = lexicon.review_queue_item(
        row,
        card,
        now=_NOW,
        evidence=_PRODUCTION_EVIDENCE,
        learner_state=learner_state,
    )
    # Byte a byte: la misma evidencia y un estado distinto no pueden cambiar ni la
    # tarea servida, ni la actividad del ítem, ni el valor esperado de aprendizaje.
    return json.dumps(item, sort_keys=True, default=str)


def test_decision_path_is_blind_to_the_persisted_state(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_lexicon(uid, "spoken_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    _seed_lexicon(uid, "written_production", ["2026-01-03", "2026-01-04"], "lexical:5")
    asyncio.run(profile_domain.get_profile_summary(uid))

    before = asyncio.run(learner_state_domain.learner_level_state(uid))
    # Se pisa la columna con un estado RICO (y ajeno a la evidencia real).
    profile_repo.set_skill_state(uid, json.dumps(_RICH_STATE, sort_keys=True))
    after = asyncio.run(learner_state_domain.learner_level_state(uid))

    assert before == after
    # El estado nuevo reproduce EXACTO lo que el drill ya lee de V3.54.
    served = skill_state_service.skill_state(
        skill_state_service.skill_state_sources(lexicon=_lexicon_rows_of(uid))
    )
    for skill, modality in skill_axis.LEXICAL_MODALITY.items():
        entry = served[modality].get("")
        assert (entry["dimensions"] if entry else {}) == (
            before["observed_skill_capacity"].get(skill, {})
        )
    assert _drill_item(before) == _drill_item(after)


def test_transfer_context_is_unchanged_by_the_new_column(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_lexicon(uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    asyncio.run(profile_domain.get_profile_summary(uid))
    before = asyncio.run(learner_state_domain.learner_level_state(uid))
    profile_repo.set_skill_state(uid, json.dumps(_RICH_STATE, sort_keys=True))
    after = asyncio.run(learner_state_domain.learner_level_state(uid))
    assert _transfer_payload(before) == _transfer_payload(after)
    # El banco NO se toca: el contexto servido es el de siempre.
    assert _transfer_payload(before)["available"] is True


def _transfer_payload(state: dict) -> dict:
    from services import transfer

    return transfer.context_for(
        "travel",
        used_context_ids=["transfer:story"],
        success_context_ids=[],
        level=state["practice_level"],
        skill="spontaneous_use",
        learner_level=state["floor_level"],
        learner_level_source=state["floor_source"],
        learner_capacity=state["learner_capacity"],
        learner_skill_capacity=state["observed_skill_capacity"],
        capacity_skill="written_production",
    )


def test_elv_and_argmax_are_unchanged_by_the_new_column(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_lexicon(uid, "recall", ["2026-01-01", "2026-01-02"], "lexical:3")
    _seed_lexicon(uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    asyncio.run(profile_domain.get_profile_summary(uid))
    before = asyncio.run(learner_state_domain.learner_level_state(uid))
    profile_repo.set_skill_state(uid, json.dumps(_RICH_STATE, sort_keys=True))
    after = asyncio.run(learner_state_domain.learner_level_state(uid))
    assert _elv_payload(before) == _elv_payload(after)
    # El argmax SÍ discrimina con estado (margen comparable, no None).
    payload = _elv_payload(before)
    assert payload["margin"] is not None
    assert payload["task"]["skill"] in ("recall", "written_production")


def _elv_payload(state: dict) -> dict:
    from services import lexicon, planner

    matrix = {"production": True}
    evidence = dict(_PRODUCTION_EVIDENCE)
    signals = planner.planned_signals(evidence, matrix)
    capacity = lexicon._capacity_by_skill(state)
    chosen = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill=capacity,
        task_difficulty={"lexical": 4},
    )
    payload = planner.expected_learning_value(
        signals,
        skill=chosen["skill"],
        task_difficulty={"lexical": 4},
        learner_capacity=capacity.get(planner.capacity_skill(chosen["skill"])),
        value=0.5,
        capacity_skill=planner.capacity_skill(chosen["skill"]),
    )
    return {"task": chosen, "elv": payload, "margin": payload["margin"]}


def test_decision_modules_do_not_mention_the_new_state():
    """Cero recableado, fijado en el código: nadie del camino de decisión lo lee."""
    guarded = (
        "services/planner.py",
        "services/difficulty.py",
        "services/transfer.py",
        "services/lexicon.py",
        "services/expected_learning_value.py",
        "domain/learner_state.py",
        "domain/vocabulary.py",
    )
    for relative in guarded:
        path = _BACKEND / relative
        if not path.exists():
            continue
        assert "skill_state" not in path.read_text(encoding="utf-8"), relative


def test_learner_capacity_is_unchanged_by_the_new_column(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_lexicon(uid, "written_production", ["2026-01-01", "2026-01-02"], "lexical:4")
    asyncio.run(profile_domain.get_profile_summary(uid))
    before = asyncio.run(learner_state_domain.learner_level_state(uid))
    profile_repo.set_skill_state(uid, json.dumps(_RICH_STATE, sort_keys=True))
    assert asyncio.run(learner_state_domain.learner_level_state(uid)) == before
    # El vector de dificultad del alumno se sigue derivando de SU columna, no del
    # estado nuevo: la proyección legacy queda intacta.
    assert difficulty.parse_vector(
        profile_repo.get_profile(uid)["observed_capacity"]
    ) == before["observed_capacity"]
    assert before["learner_capacity"] == learner_skill.learner_capacity(
        before["floor_level"], before["observed_capacity"]
    )
