"""V3.53 — Parte B: Learner Skill State 2.0 (capacidad OBSERVADA).

La capacidad observada por dimensión se deriva de la dificultad de la TAREA
servida (`observed_difficulty`), exige muestra ESPACIADA, se cachea en
`learning_profile` y se usa como SUELO del Difficulty Engine sin bajar nunca el
suelo declarado. Con `observed_capacity` vacío todo es idéntico a V3.52.2: aquí
se blinda esa no-regresión de forma exhaustiva.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from domain import profile as profile_domain
from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, learner_skill, student_state, transfer
from services.cefr import CEFR_LEVELS
from services.evidence import observed_signals


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


def _signals(
    skill: str,
    dimension: str,
    load: int,
    *,
    samples: int,
    days: int,
) -> dict:
    """Señales de `observed_signals` para una modalidad/dimensión."""
    return {
        "observed_samples": {skill: {dimension: samples}},
        "observed_days": {skill: {dimension: days}},
        "observed_capacity": {skill: {dimension: load}},
    }


# ------------------------------------------------------------- módulo puro


def test_observed_capacity_requires_spaced_samples():
    # Un solo éxito no asciende.
    assert learner_skill.observed_capacity(
        _signals("written_production", "discourse", 4, samples=1, days=1)
    ) == {}
    # Dos éxitos el MISMO día tampoco: volumen sin espaciado no es retención.
    assert learner_skill.observed_capacity(
        _signals("written_production", "discourse", 4, samples=2, days=1)
    ) == {}
    # Dos éxitos en dos días naturales distintos sí.
    assert learner_skill.observed_capacity(
        _signals("written_production", "discourse", 4, samples=2, days=2)
    ) == {"discourse": 4}
    # Sin señales válidas no se inventa capacidad.
    assert learner_skill.observed_capacity(None) == {}
    assert learner_skill.observed_capacity({}) == {}


def test_observed_capacity_takes_the_max_across_qualifying_modalities():
    signals = {
        "observed_samples": {
            "written_production": {"lexical": 2, "syntax": 2},
            "spoken_production": {"lexical": 2},
        },
        "observed_days": {
            "written_production": {"lexical": 2, "syntax": 2},
            "spoken_production": {"lexical": 1},
        },
        "observed_capacity": {
            "written_production": {"lexical": 3, "syntax": 2},
            "spoken_production": {"lexical": 5},
        },
    }
    # `spoken` no alcanza el espaciado, así que su lexical 5 NO asciende; el
    # máximo entre las modalidades que sí cualifican es lexical 3.
    assert learner_skill.observed_capacity(signals) == {"lexical": 3, "syntax": 2}


def test_level_from_capacity_requires_full_dimensional_coverage():
    # Sin muestra no hay nivel.
    assert learner_skill.level_from_capacity({}) == ""
    assert learner_skill.level_from_capacity(None) == ""
    # V3.53.1 (P1-01): una sola dimensión NO produce un CEFR global. Una
    # capacidad léxica compatible con C2 no es un nivel C2: el resto de
    # dimensiones del nivel no tiene muestra y bloquean la etiqueta global.
    assert learner_skill.level_from_capacity({"lexical": 1}) == ""
    assert learner_skill.level_from_capacity({"lexical": 5}) == ""
    assert learner_skill.level_from_capacity({"discourse": 2}) == ""
    assert learner_skill.level_from_capacity({"discourse": 3}) == ""
    # Cobertura PARCIAL (3 de 4 dimensiones) tampoco declara nivel global.
    assert learner_skill.level_from_capacity(
        {"lexical": 5, "syntax": 5, "discourse": 5}
    ) == ""
    # Con cobertura COMPLETA el nivel se decide por la dimensión LIMITANTE.
    a2 = difficulty.capacity_for("A2")
    assert learner_skill.level_from_capacity(a2) == "A2"


def test_level_from_capacity_cases_are_multidimensional():
    # Caso 1: solo léxico C2 -> sin nivel global (la capacidad se conserva).
    assert learner_skill.level_from_capacity({"lexical": 5}) == ""
    # Caso 2: léxico C2 con el resto en B2 (interaction 3 < C1 5) -> B2.
    assert learner_skill.level_from_capacity(
        {"lexical": 5, "syntax": 3, "discourse": 4, "interaction": 3}
    ) == "B2"
    # Caso 3: la envolvente completa de C1 (lexical 4, resto 5) -> C1; C2
    # queda bloqueado por el léxico (4 < 5).
    assert learner_skill.level_from_capacity(difficulty.capacity_for("C1")) == "C1"
    assert learner_skill.level_from_capacity(difficulty.capacity_for("C2")) == "C2"


def test_partial_coverage_keeps_capacity_and_raises_only_observed_dimensions():
    # La corrección NO destruye `observed_capacity` (fuente de verdad) ni la
    # subida por dimensión: sin nivel global, `learner_capacity` sigue subiendo
    # el reto SOLO donde hay evidencia y conserva el suelo declarado.
    partial = {"lexical": 5}
    assert learner_skill.level_from_capacity(partial) == ""
    raised = learner_skill.learner_capacity("B1", partial)
    floor = difficulty.capacity_for("B1")
    assert raised["lexical"] == 5
    assert raised["syntax"] == floor["syntax"]
    assert raised["discourse"] == floor["discourse"]
    assert raised["interaction"] == floor["interaction"]



def test_learner_capacity_never_lowers_the_declared_floor():
    floor = difficulty.capacity_for("B1")
    # Observado por debajo del suelo declarado: el suelo manda.
    assert learner_skill.learner_capacity("B1", {"lexical": 1})["lexical"] == (
        floor["lexical"]
    )
    # Observado por encima: sube SOLO esa dimensión.
    raised = learner_skill.learner_capacity("B1", {"lexical": 5})
    assert raised["lexical"] == 5
    assert raised["syntax"] == floor["syntax"]
    # Sin ninguna fuente no hay reto.
    assert learner_skill.learner_capacity("", {}) == {}
    # Sin nivel pero con observado, el observado es el suelo.
    assert learner_skill.learner_capacity("", {"discourse": 4}) == {"discourse": 4}


def test_floor_level_places_observed_between_demonstrated_and_estimated():
    assert student_state.floor_level(
        practice_level="A1",
        estimated_cefr="C1",
        demonstrated_cefr="",
        observed_cefr="B1",
    ) == ("B1", "observed")
    # Una certificación sigue ganando a una capacidad observada superior.
    assert student_state.floor_level(
        practice_level="A1",
        estimated_cefr="C1",
        demonstrated_cefr="A2",
        observed_cefr="C2",
    ) == ("A2", "demonstrated")
    # Sin observado cae al estimado.
    assert student_state.floor_level("", "B2", "", "") == ("B2", "estimated")
    # El estado normaliza y expone el nivel observado.
    state = student_state.level_state(observed_cefr="b1")
    assert state["observed_cefr"] == "B1"
    assert state["floor_source"] == "observed"


# ------------------------------------------------------------- integración


def test_learner_level_state_reads_the_cached_observed_capacity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    profile_repo.set_level_state(
        uid,
        estimated_level="",
        demonstrated_level="",
        observed_level="B1",
        observed_capacity="lexical:4,syntax:3,discourse:3,interaction:3",
    )
    state = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert state["floor_level"] == "B1"
    assert state["floor_source"] == "observed"
    assert state["observed_capacity"] == {
        "lexical": 4,
        "syntax": 3,
        "discourse": 3,
        "interaction": 3,
    }
    assert state["learner_capacity"]["lexical"] == 4


def test_profile_derives_and_caches_the_observed_state(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vector = "lexical:3,syntax:3,discourse:4,interaction:2"
    for day in ("2026-09-01", "2026-09-03"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
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
    asyncio.run(profile_domain.get_profile_summary(uid))
    row = profile_repo.get_profile(uid)
    assert row is not None
    assert difficulty.parse_vector(row["observed_capacity"]) == {
        "lexical": 3,
        "syntax": 3,
        "discourse": 4,
        "interaction": 2,
    }
    assert row["observed_level"] == learner_skill.level_from_capacity(
        {"lexical": 3, "syntax": 3, "discourse": 4, "interaction": 2}
    )


def test_context_for_raises_the_challenge_with_the_observed_override():
    base = transfer.context_for("travel", level="A2", learner_level="A2")
    raised = transfer.context_for(
        "travel",
        level="A2",
        learner_level="A2",
        learner_capacity={"lexical": 5, "interaction": 5},
    )
    assert base["difficulty_fit"]["challenge"]["lexical"] == 2
    assert raised["difficulty_fit"]["challenge"]["lexical"] == 5
    assert raised["difficulty_fit"]["challenge"]["interaction"] == 5
    # La dimensión no observada conserva la capacidad del ítem (techo).
    assert raised["difficulty_fit"]["challenge"]["syntax"] == 2
    assert raised["learner_capacity"] == {"lexical": 5, "interaction": 5}


def test_empty_observed_capacity_is_exactly_v352():
    # No-regresión exhaustiva: con la capacidad observada vacía el reto, la
    # elección y la tolerancia son IDÉNTICOS a no aportar nada.
    for item in (*CEFR_LEVELS, ""):
        for learner in (*CEFR_LEVELS, ""):
            for source in ("", "demonstrated", "estimated", "observed"):
                base = transfer.context_for(
                    "travel",
                    level=item,
                    learner_level=learner,
                    learner_level_source=source,
                )
                empty = transfer.context_for(
                    "travel",
                    level=item,
                    learner_level=learner,
                    learner_level_source=source,
                    learner_capacity={},
                )
                assert base["context_id"] == empty["context_id"]
                assert base["difficulty_fit"] == empty["difficulty_fit"]
                assert base["learner_capacity"] == {}


def test_get_and_post_share_the_observed_floor(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    profile_repo.set_level_state(
        uid,
        estimated_level="",
        demonstrated_level="",
        observed_level="C1",
        observed_capacity="lexical:4,syntax:4,discourse:4,interaction:4",
    )
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
            },
        ).json()
    assert served["learner_level_source"] == "observed"
    assert served["learner_level"] == "C1"
    assert served["learner_capacity"]
    # Paridad GET↔POST: ambos caminos derivan el MISMO contexto.
    assert attempt["context_id"] == served["context_id"]


def test_observed_signals_ignores_failures_and_unattributed_skills():
    rows = [
        {
            "success": True,
            "skill": "spontaneous_use",
            "assessed_skill": "written_production",
            "observed_difficulty": "discourse:4",
            "occurred_at": "2026-09-01T10:00:00+00:00",
        },
        {
            "success": False,
            "skill": "spontaneous_use",
            "assessed_skill": "written_production",
            "observed_difficulty": "discourse:5",
            "occurred_at": "2026-09-02T10:00:00+00:00",
        },
        {
            "success": True,
            "skill": "chat",  # no canónica y sin assessed_skill: se ignora
            "assessed_skill": "",
            "observed_difficulty": "discourse:5",
            "occurred_at": "2026-09-03T10:00:00+00:00",
        },
    ]
    signals = observed_signals(rows)
    assert signals["observed_capacity"] == {"written_production": {"discourse": 4}}
    assert signals["observed_samples"] == {"written_production": {"discourse": 1}}
    assert signals["observed_days"] == {"written_production": {"discourse": 1}}
    assert learner_skill.observed_capacity(signals) == {}
