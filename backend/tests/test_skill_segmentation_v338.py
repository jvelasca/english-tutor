"""Tests de V3.38 — automaticidad segmentada por modalidad (P1-03).

V3.37 introdujo `is_automatic`: un ítem es automático con >= 2 éxitos
independientes en >= 2 días naturales distintos. Pero esa automaticidad era
GLOBAL por ítem: dos éxitos independientes podían venir de modalidades
distintas (uno escrito y otro oral) y el ítem se declaraba automático sin que
NINGUNA modalidad concreta lo fuera.

V3.38 (P1-03 de la auditoría de V3.37.0) segmenta el ledger por MODALIDAD
(`LEXICAL_SKILLS`) y añade `automatic_skills`, que aplica el mismo umbral POR
modalidad. Se cubren:

- el vocabulario declarado y el mapeo de los canales de producción;
- los histogramas puros (`skill_successes`/`skill_success_days`/
  `skill_independent_*`), ignorando `skill` legacy fuera del vocabulario;
- `automatic_skills`: mezclar modalidades NO hace automática ninguna;
- la paridad pura↔SQL de los histogramas por modalidad;
- la captura end-to-end: recall → `recall`, producción → su modalidad.
"""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from domain import vocabulary as domain_vocabulary
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import evidence as evidence_svc


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _row(skill: str, *, success: bool, support: str, day: str) -> dict:
    return {
        "occurred_at": f"{day}T10:00:00+00:00",
        "skill": skill,
        "success": success,
        "support_level": support,
    }


# --- Vocabulario declarado --------------------------------------------------


def test_lexical_skills_are_the_declared_modality_axis():
    assert evidence_svc.LEXICAL_SKILLS == (
        "recall",
        "written_production",
        "spoken_production",
        "spontaneous_use",
    )
    # Cada canal de producción declara una modalidad canónica (el canal concreto
    # sigue en `context_id`/`activity_id`, no se pierde información).
    for channel, skill in evidence_svc.PRODUCTION_CHANNEL_SKILL.items():
        assert skill in evidence_svc.LEXICAL_SKILLS, channel
    # Un canal desconocido no declara modalidad: nunca inventa una.
    assert evidence_svc.production_skill("telepathy") == ""


def test_channel_to_modality_mapping_is_the_pedagogical_axis():
    assert evidence_svc.production_skill("chat") == "spontaneous_use"
    assert evidence_svc.production_skill("conversation") == "spoken_production"
    assert evidence_svc.production_skill("speaking") == "spoken_production"
    assert evidence_svc.production_skill("writing") == "written_production"


# --- Histogramas puros ------------------------------------------------------


def test_summarize_segments_successes_by_modality():
    summary = evidence_svc.summarize_evidence(
        [
            _row("recall", success=True, support="cued", day="2026-09-01"),
            _row("recall", success=False, support="cued", day="2026-09-02"),
            _row(
                "spoken_production",
                success=True,
                support="guided",
                day="2026-09-01",
            ),
            _row("writing", success=True, support="independent", day="2026-09-03"),
        ]
    )
    # Solo ÉXITOS entran en los histogramas (una modalidad con únicamente fallos
    # no aparece): paridad con el `success = 1` del agregado SQL.
    assert summary["skill_successes"] == {
        "recall": 1,
        "spoken_production": 1,
    }
    assert summary["skill_success_days"] == {
        "recall": 1,
        "spoken_production": 1,
    }
    # `writing` es un valor LEGACY (canal crudo de V3.36-V3.37), no una modalidad
    # declarada: no entra en la segmentación (ni a favor ni en contra).
    assert summary["skill_independent_successes"] == {}
    assert summary["skill_independent_days"] == {}


def test_summarize_ignores_skills_outside_the_vocabulary():
    summary = evidence_svc.summarize_evidence(
        [
            _row("chat", success=True, support="spontaneous", day="2026-09-01"),
            _row("", success=True, support="independent", day="2026-09-02"),
        ]
    )
    assert summary["skill_successes"] == {}
    assert summary["skill_success_days"] == {}
    assert evidence_svc.automatic_skills(summary) == []


def test_skill_independent_histograms_require_unassisted_success():
    summary = evidence_svc.summarize_evidence(
        [
            _row("recall", success=True, support="cued", day="2026-09-01"),
            _row("recall", success=True, support="guided", day="2026-09-02"),
            _row("recall", success=True, support="independent", day="2026-09-03"),
        ]
    )
    assert summary["skill_successes"] == {"recall": 3}
    assert summary["skill_success_days"] == {"recall": 3}
    # `cued`/`guided` cuentan como éxito pero no como independiente.
    assert summary["skill_independent_successes"] == {"recall": 1}
    assert summary["skill_independent_days"] == {"recall": 1}


# --- automatic_skills (el núcleo de P1-03) ----------------------------------


def test_automatic_skills_requires_spacing_within_one_modality():
    two_days = evidence_svc.summarize_evidence(
        [
            _row(
                "written_production",
                success=True,
                support="independent",
                day="2026-09-01",
            ),
            _row(
                "written_production",
                success=True,
                support="independent",
                day="2026-09-05",
            ),
        ]
    )
    assert evidence_svc.automatic_skills(two_days) == ["written_production"]


def test_same_day_volume_is_not_automatic_in_a_modality():
    one_day = evidence_svc.summarize_evidence(
        [
            _row("recall", success=True, support="independent", day="2026-09-01"),
            _row("recall", success=True, support="independent", day="2026-09-01"),
        ]
    )
    assert evidence_svc.automatic_skills(one_day) == []


def test_mixing_modalities_does_not_make_any_modality_automatic():
    """El bug que cierra P1-03: dos modalidades distintas no suman automaticidad.

    Un éxito escrito (D1) más un éxito oral (D5) hacían `is_automatic` global
    verdadero, aunque ninguna modalidad tuviera dos éxitos espaciados.
    """
    mixed = evidence_svc.summarize_evidence(
        [
            _row(
                "written_production",
                success=True,
                support="independent",
                day="2026-09-01",
            ),
            _row(
                "spoken_production",
                success=True,
                support="independent",
                day="2026-09-05",
            ),
        ]
    )
    assert evidence_svc.is_automatic(mixed) is True  # el ítem, globalmente...
    assert evidence_svc.automatic_skills(mixed) == []  # ...pero ninguna modalidad


def test_automatic_skills_can_coexist_in_several_modalities():
    both = evidence_svc.summarize_evidence(
        [
            _row("recall", success=True, support="independent", day="2026-09-01"),
            _row("recall", success=True, support="independent", day="2026-09-03"),
            _row(
                "spoken_production",
                success=True,
                support="spontaneous",
                day="2026-09-02",
            ),
            _row(
                "spoken_production",
                success=True,
                support="spontaneous",
                day="2026-09-04",
            ),
        ]
    )
    assert evidence_svc.automatic_skills(both) == [
        "recall",
        "spoken_production",
    ]


def test_automatic_skills_never_raises_on_partial_evidence():
    assert evidence_svc.automatic_skills({}) == []
    assert (
        evidence_svc.automatic_skills({"skill_independent_successes": "nope"}) == []
    )
    assert (
        evidence_svc.automatic_skills(
            {
                "skill_independent_successes": {"recall": "x"},
                "skill_independent_days": {"recall": 5},
            }
        )
        == []
    )


# --- Paridad pura ↔ SQL -----------------------------------------------------


def test_skill_histograms_match_between_pure_and_sql(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    events = [
        ("recall", True, "cued", "2026-09-01"),
        ("recall", True, "independent", "2026-09-02"),
        ("recall", False, "cued", "2026-09-03"),
        ("spoken_production", True, "independent", "2026-09-01"),
        ("chat", True, "spontaneous", "2026-09-02"),  # legacy: se ignora
    ]
    for skill, success, support, day in events:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill=skill,
            task="recall",
            success=success,
            support_level=support,
            occurred_at=f"{day}T10:00:00+00:00",
        )
    rows = evidence_repo.list_evidence(uid, target_type="lexicon")
    pure = evidence_svc.summarize_evidence(list(reversed(rows)))
    sql = evidence_repo.summarize_by_target(uid, target_type="lexicon")["river"]
    for field in (
        "skill_successes",
        "skill_success_days",
        "skill_independent_successes",
        "skill_independent_days",
    ):
        assert sql[field] == pure[field], field
    assert sql["skill_successes"] == {"recall": 2, "spoken_production": 1}
    assert evidence_svc.automatic_skills(sql) == []


# --- Captura end-to-end -----------------------------------------------------


def test_recall_event_declares_the_recall_modality(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "student",
        definition="a person who studies",
        translation="estudiante",
        generator_version="test",
    )
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "student", "answer": "student", "cue": "translation"},
        )
    assert res.status_code == 200, res.text
    row = evidence_repo.list_evidence(uid, target_type="lexicon")[0]
    assert row["skill"] == "recall"
    assert row["activity_id"] == "drill:recall:translation"


def test_production_event_declares_the_modality_not_the_channel(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    asyncio.run(
        domain_vocabulary.record_production_text(
            uid, "river", "writing", activity="writing_task"
        )
    )
    row = evidence_repo.list_evidence(uid, target_type="lexicon")[0]
    assert row["skill"] == "written_production"
    # El canal concreto NO se pierde: sigue en el contexto/actividad.
    assert row["context_id"] == "lexicon:writing"


def test_drill_retrieval_declares_spoken_production(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    asyncio.run(
        domain_vocabulary._record_retrieval(
            uid, "river", activity_id="drill:sentence"
        )
    )
    row = evidence_repo.list_evidence(uid, target_type="lexicon")[0]
    assert row["skill"] == "spoken_production"
    assert row["activity_id"] == "drill:sentence"
