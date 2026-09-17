"""Pinnea la cobertura de destrezas medida en V3.70 · Eje 2 (`AB`).

Tests de **medición**: afirman los hechos ya auditados en
`docs/audit/AB-PED-COBERTURA.md` y en la evidencia cruda
`docs/audit/generated/skill-coverage.{md,json}`, generada por
`python -m scripts.audit_dossier skill-coverage` (solo lectura).

Si alguien cierra un hueco (escribe `services/reading.py`, dota de canal a
`interaction`, amplía el corpus B1–C2, graba audio humano, crea el curso
Pre-A1), estos tests **fallan** y obligan a re-auditar el eje. No afirman que la
cobertura sea buena: afirman la cobertura que **hay** hoy (regla dura de V3.70:
solo medición).

Miden **cobertura declarada y volumen realizado**, no eficacia pedagógica: que
una destreza tenga contenido, scorer y UI no demuestra que el alumno aprenda.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from services import (
    audio_library,
    cefr_descriptors,
    cefr_matrix,
    content_validation,
    curriculum,
    mastery,
    skill_axis,
    skill_state,
    speaking_scenarios,
)

REPO_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_DIR / "backend"
SERVICES_DIR = BACKEND_DIR / "services"
FRONTEND_FEATURES_DIR = REPO_DIR / "frontend" / "src" / "features"
FRONTEND_ROUTER_DIR = REPO_DIR / "frontend" / "src" / "router"
GENERATED_DIR = REPO_DIR / "docs" / "audit" / "generated"

# Las 9 modalidades declaradas (mastery.MASTERY_SKILLS), en su orden canónico.
EXPECTED_MODALITIES = (
    "vocabulary",
    "grammar",
    "pronunciation",
    "listening",
    "speaking",
    "reading",
    "writing",
    "interaction",
    "mediation",
)

# Los cinco atributos que el dossier exige a cada modalidad (columnas de la
# matriz): competencias, presencia en la matriz CEFR, canal de evidencia,
# scorer de ejecución y feature de UI. Los conteos de contenido van aparte.
FIVE_ATTRIBUTES = (
    "competences",
    "declared_in_matrix",
    "evidence_channel",
    "scorer_module",
    "ui_feature",
)


def _json_entries(name: str) -> list:
    """Copia de `_json_entries` del instrumento: ítems de un corpus del disco."""
    data = json.loads(
        (curriculum.CURRICULUM_DIR / name).read_text(encoding="utf-8")
    )
    if isinstance(data, list):
        return data
    for key in ("items", "entries", "corpus", "scenarios", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _live_content_counts() -> dict[str, dict[str, int]]:
    """Conteos de contenido por modalidad, recalculados del disco."""
    counts = {
        m: {"objectives": 0, "checks": 0, "corpus": 0} for m in EXPECTED_MODALITIES
    }
    for level in curriculum.load_all_levels():
        for obj in level.objectives():
            for skill in set(obj.skills):
                if skill in counts:
                    counts[skill]["objectives"] += 1
            for check in obj.checks:
                if check.skill in counts:
                    counts[check.skill]["checks"] += 1
    from services.listening import QUESTION_BANK

    corpus = {
        "listening": sum(
            1 for q in QUESTION_BANK if str(q["id"]).startswith("c")
        ),
        "speaking": len(_json_entries("speaking_corpus.json"))
        + len(speaking_scenarios.list_scenarios()),
        "pronunciation": len(_json_entries("pronunciation_corpus.json")),
        "interaction": len(_json_entries("conversation_corpus.json")),
    }
    for modality, total in corpus.items():
        counts[modality]["corpus"] = total
    return counts


def _reading_counts() -> tuple[int, int]:
    """(objetivos que declaran reading, checks de reading) en todo el curso."""
    objectives = 0
    checks = 0
    for level in curriculum.load_all_levels():
        for obj in level.objectives():
            if "reading" in obj.skills:
                objectives += 1
            checks += sum(1 for c in obj.checks if c.skill == "reading")
    return objectives, checks


def _corpus_by_level() -> Counter:
    from services.listening import QUESTION_BANK

    return Counter(
        q["level"] for q in QUESTION_BANK if str(q["id"]).startswith("c")
    )


def _generated() -> dict:
    return json.loads(
        (GENERATED_DIR / "skill-coverage.json").read_text(encoding="utf-8")
    )


# --- Matriz modalidad × artefacto (hallazgos 1, 4, 5 y 8) ------------------


def test_every_mastery_modality_is_accounted_for() -> None:
    """Las 9 modalidades aparecen en la matriz del dossier con sus 5 atributos."""
    assert tuple(mastery.MASTERY_SKILLS) == EXPECTED_MODALITIES
    assert tuple(skill_axis.SKILL_MODALITIES) == EXPECTED_MODALITIES
    generated = _generated()
    assert set(generated["modalities"]) == set(EXPECTED_MODALITIES)
    live = _live_content_counts()
    for modality in EXPECTED_MODALITIES:
        entry = generated["modalities"][modality]
        assert set(FIVE_ATTRIBUTES) <= set(entry), modality
        assert modality in skill_axis.COMPETENCES_BY_MODALITY
        assert entry["competences"] == len(
            skill_axis.COMPETENCES_BY_MODALITY[modality]
        )
        for key in ("objectives", "checks", "corpus"):
            assert entry[key] == live[modality][key], (modality, key)
    # La matriz también está renderizada en el `.md` (una fila por modalidad).
    md = (GENERATED_DIR / "skill-coverage.md").read_text(encoding="utf-8")
    for modality in EXPECTED_MODALITIES:
        assert f"| {modality} |" in md


def test_reading_has_no_dedicated_scorer() -> None:
    """`reading` declara objetivos, checks y UI, pero no tiene scorer propio."""
    assert not (SERVICES_DIR / "reading.py").exists()
    assert _reading_counts() == (15, 18)
    # La asimetría es explícita: contenido y UI sí, corpus y scorer no.
    # V3.73.1 (Opción A): la UI de reading ya no es el directorio
    # `frontend/src/features/reading` (retirado junto con `ReadingPractice`),
    # sino el **chat con destreza** `/chat/lectura`. Se comprueba el cableado
    # real —el router tiene que declarar el slug— y que el dossier generado
    # siga viendo esa UI: si el router pierde `reading`, esto falla.
    chat_router = (FRONTEND_ROUTER_DIR / "chat.ts").read_text(encoding="utf-8")
    assert re.search(r'reading:\s*"lectura"', chat_router)
    entry = _generated()["modalities"]["reading"]
    assert entry["ui_exists"] is True
    assert entry["scorer_exists"] is False
    assert entry["corpus"] == 0


def test_mediation_is_declared_but_inert() -> None:
    """`mediation` se declara evaluable y no puede recibir ninguna evidencia."""
    assert "mediation" in mastery.MASTERY_SKILLS
    assert "mediation" not in skill_state.MODALITY_CHANNEL
    assert skill_axis.COMPETENCES_BY_MODALITY["mediation"] == ()
    assert not (SERVICES_DIR / "mediation.py").exists()
    assert not (FRONTEND_FEATURES_DIR / "mediation").exists()
    assert _live_content_counts()["mediation"] == {
        "objectives": 0,
        "checks": 0,
        "corpus": 0,
    }


def test_mediation_requirements_cannot_be_met() -> None:
    """La matriz CEFR exige 24 evidencias de `mediation` que nadie emite."""
    matrix = cefr_matrix.load_matrix()
    required = {
        level_id: row.skills["mediation"].minimum_evidence
        for level_id, row in matrix.levels.items()
    }
    assert required == {"A1": 3, "A2": 3, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    assert sum(required.values()) == 24
    # Y el requisito es inalcanzable por construcción: sin competencias, sin
    # canal, sin corpus, sin scorer y sin UI (nada produce la evidencia).
    assert "mediation" not in skill_state.MODALITY_CHANNEL
    assert skill_axis.COMPETENCES_BY_MODALITY["mediation"] == ()


def test_interaction_has_no_evidence_channel() -> None:
    """`interaction` tiene módulo y corpus, pero ni competencias ni canal."""
    assert "interaction" in mastery.MASTERY_SKILLS
    assert "interaction" not in skill_state.MODALITY_CHANNEL
    assert skill_axis.COMPETENCES_BY_MODALITY["interaction"] == ()
    # Hay material y artefactos: el hueco es de emisor, no de contenido.
    assert (SERVICES_DIR / "interaction.py").exists()
    entry = _live_content_counts()["interaction"]
    assert entry == {"objectives": 0, "checks": 0, "corpus": 66}
    # La interacción se entrena por subdestrezas de otros objetivos: 6 de los 7
    # niveles tienen contenido en la sección `interaction`.
    coverage = content_validation.content_stats()["total_curriculum_coverage"]
    assert coverage["by_section"]["interaction"] == {"populated": 6, "total": 7}


def test_pronunciation_is_operative_but_outside_the_cefr_matrix() -> None:
    """`pronunciation` funciona (canal, scorer, corpus, UI) y no está en matriz."""
    matrix = cefr_matrix.load_matrix()
    matrix_skills = {s for row in matrix.levels.values() for s in row.skills}
    assert "pronunciation" not in matrix_skills
    assert skill_state.MODALITY_CHANNEL["pronunciation"] == "spoken"
    assert len(skill_axis.COMPETENCES_BY_MODALITY["pronunciation"]) == 10
    assert len(_json_entries("pronunciation_corpus.json")) == 120
    assert (SERVICES_DIR / "pronunciation.py").exists()
    assert (FRONTEND_FEATURES_DIR / "pronunciation").is_dir()


# --- Volumen frente a objetivo declarado (hallazgos 2 y 6) -----------------


def test_listening_corpus_meets_a1_a2_and_not_b1_c2() -> None:
    """A1/A2 cumplen su objetivo declarado; B1–C2 no llegan ni al 25 %."""
    by_level = _corpus_by_level()
    targets = curriculum.LISTENING_CORPUS_TARGETS
    for level in ("A1", "A2"):
        assert by_level[level] == targets[level] == 200
    assert {level: by_level[level] for level in ("B1", "B2", "C1", "C2")} == {
        "B1": 25,
        "B2": 25,
        "C1": 20,
        "C2": 20,
    }
    for level in ("B1", "B2", "C1", "C2"):
        assert by_level[level] / targets[level] < 0.25


def test_speaking_scenarios_extremes_are_thin() -> None:
    """A1 y C1 tienen un solo escenario cada uno; el resto, entre 5 y 7."""
    by_level = Counter(
        s["cefr_target"] for s in speaking_scenarios.list_scenarios()
    )
    assert sum(by_level.values()) == 26
    assert by_level["A1"] == 1
    assert by_level["C1"] == 1
    for level in ("A2", "B1", "B2", "C2"):
        assert by_level[level] >= 5


# --- Audio, Pre-A1 y métrica canónica (hallazgos 3 y 7) --------------------


def test_no_recorded_human_audio() -> None:
    """La biblioteca de audio humano está versionada y vacía: 100 % TTS."""
    manifest = audio_library.load_manifest()
    assert manifest.version == "1.2.0"
    assert manifest.entries == []
    listening = content_validation.content_stats()["listening"]
    assert listening == {
        "total": 513,
        "corpus": 490,
        "legacy_tts": 23,
        "with_audio_id": 499,
    }


def test_pre_a1_has_no_course() -> None:
    """La banda `pre-a1` existe en la escalera, pero no tiene curso."""
    assert "pre-a1" in cefr_descriptors.CEFR_LADDER
    assert not (curriculum.CURRICULUM_DIR / "pre-a1.json").exists()
    coverage = content_validation.content_stats()["total_curriculum_coverage"]
    assert coverage["by_level"]["pre-a1"] == {"populated": 0, "total": 7}
    assert coverage["populated_cells"] == 42
    assert coverage["total_cells"] == 49
    assert coverage["coverage_pct"] == 85.7
