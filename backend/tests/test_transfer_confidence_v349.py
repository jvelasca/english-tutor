"""V3.49 — Transfer Evidence 3.0 (confianza del eje de transferencia).

La auditoría de V3.43.0 (punto 8) avisó de que los NOMBRES de los estados
(`transfer_demonstrated`, `transfer_stable`) pueden sugerir más evidencia de la
disponible. V3.49 no cambia la escalera: añade una CONFIANZA explícita y
explicable derivada de la evidencia fina ya existente, para poder decir no solo
«en qué estado está» sino «con cuánta evidencia se afirma».

- `services.evidence.transfer_confidence` (PURA) sintetiza los `drivers`
  (`contexts`/`successes`/`diversity`/`independence`/`variety`/`spacing`) en un
  `{score, level, sample, drivers, recency_days}`.
- Los `drivers` son componentes 0..1 de evidencia YA registrada; no hay reloj en
  el `score` (`recency_days` es informativo).
- Se deriva en la MISMA frontera que `transfer_state` (`with_transfer_state`),
  así que el resumen puro y el SQL comparten valor por construcción.
- Resumen legacy/parcial: conservador (`none`), nunca inflado y sin lanzar.
"""

from __future__ import annotations

from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import evidence
from services.evidence import (
    context_signals,
    summarize_evidence,
    transfer_confidence,
    transfer_state,
    with_transfer_state,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "A1") -> None:
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


def _row(
    context_id: str,
    *,
    condition: str = "",
    error_type: str = "correct",
    day: str = "2026-01-01",
    success: int = 1,
) -> dict:
    return {
        "context_id": context_id,
        "success": success,
        "error_type": error_type,
        "occurred_at": f"{day}T10:00:00+00:00",
        "transfer_condition": condition,
    }


def _summary(rows: list[dict]) -> dict:
    summary = {
        "attempts": len(rows),
        "successes": sum(1 for row in rows if row.get("success")),
    }
    summary.update(context_signals(rows))
    return with_transfer_state(summary)


def _seed_transfer_evidence(
    uid: str, word: str, context_id: str, *, condition: str, day: str = "2026-01-01"
) -> None:
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id=word,
        surface_form=word,
        lexical_unit=word,
        skill="spontaneous_use",
        task="transfer",
        activity="drill",
        activity_id="drill:transfer",
        context_id=context_id,
        success=True,
        support_level="spontaneous",
        error_type="correct",
        transfer_condition=condition,
        occurred_at=f"{day}T10:00:00+00:00",
    )


# ------------------------------------------------------------ contrato básico


def test_confidence_shape_and_neutral_default():
    confidence = transfer_confidence({})
    assert confidence["score"] == 0.0
    assert confidence["level"] == "none"
    assert confidence["sample"] == 0
    assert confidence["recency_days"] is None
    assert set(confidence["drivers"]) == set(
        evidence.TRANSFER_CONFIDENCE_WEIGHTS
    )
    assert all(0.0 <= value <= 1.0 for value in confidence["drivers"].values())


def test_confidence_weights_are_declared_and_normalized():
    weights = evidence.TRANSFER_CONFIDENCE_WEIGHTS
    assert set(weights) == {
        "contexts",
        "successes",
        "diversity",
        "independence",
        "variety",
        "spacing",
    }
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert all(weight > 0 for weight in weights.values())
    assert evidence.TRANSFER_CONFIDENCE_LEVELS == ("none", "low", "medium", "high")


def test_with_transfer_state_and_empty_summary_attach_confidence():
    summary = _summary([_row("transfer:story", condition="open_context")])
    assert summary["transfer_confidence"]["level"] in {"low", "medium", "high"}
    empty = evidence.empty_summary()
    assert empty["transfer_confidence"]["level"] == "none"
    assert empty["transfer_confidence"]["score"] == 0.0


# --------------------------------------------------------- calibración/estado


def test_confidence_tracks_the_transfer_ladder():
    not_ready = transfer_confidence(
        {
            "clean_success_contexts": [],
            "clean_successes": 0,
            "context_diversity": {"diverse_dimensions": 0},
        }
    )
    assert not_ready["level"] == "none"

    emerging = transfer_confidence(
        {
            "clean_success_contexts": ["transfer:story"],
            "clean_successes": 1,
            "context_diversity": {"diverse_dimensions": 0},
            "transfer_conditions": {
                "cued_context": {"attempts": 1, "clean_successes": 1}
            },
            "unscaffolded_clean_successes": 0,
            "clean_success_days": 1,
        }
    )
    assert emerging["level"] == "low"

    demonstrated = _summary(
        [
            _row("transfer:story", condition="open_context", day="2026-01-01"),
            _row("transfer:future", condition="open_context", day="2026-01-01"),
        ]
    )
    assert transfer_state(demonstrated) == "transfer_demonstrated"
    assert demonstrated["transfer_confidence"]["level"] in {"medium", "high"}

    stable = _summary(
        [
            _row("transfer:story", condition="open_context", day="2026-01-01"),
            _row("transfer:future", condition="open_context", day="2026-01-02"),
            _row("transfer:work", condition="open_context", day="2026-01-03"),
        ]
    )
    assert transfer_state(stable) == "transfer_stable"
    assert stable["transfer_confidence"]["level"] == "high"
    # La confianza acompaña a la escalera: más evidencia, más confianza.
    assert (
        stable["transfer_confidence"]["score"]
        > demonstrated["transfer_confidence"]["score"]
    )


def test_confidence_is_monotonic_with_unscaffolded_evidence():
    rows: list[dict] = []
    scores: list[float] = [transfer_confidence(_summary(rows))["score"]]
    for context_id, day in (
        ("transfer:story", "2026-01-01"),
        ("transfer:future", "2026-01-01"),
        ("transfer:work", "2026-01-02"),
        ("transfer:opinion", "2026-01-03"),
        ("transfer:health", "2026-01-04"),
    ):
        rows.append(_row(context_id, condition="open_context", day=day))
        scores.append(transfer_confidence(_summary(rows))["score"])
    assert scores == sorted(scores), scores
    assert scores[-1] > scores[0]


def test_confidence_is_conservative_on_legacy_and_partial_summaries():
    # Resumen legacy (sin campos de V3.43 en adelante): no se puede cuantificar
    # confianza fina; se declara `none` en lugar de inflar.
    legacy = transfer_confidence({"transfer": True, "successes": 4})
    assert legacy["level"] == "none"
    assert legacy["score"] == 0.0
    # Resumen parcial con contextos pero sin contadores limpios: tampoco infla.
    partial = transfer_confidence(
        {"success_contexts": ["transfer:story", "transfer:future"]}
    )
    assert partial["level"] == "none"


def test_confidence_ignores_semantic_mismatch_and_legacy_condition_rows():
    # Un éxito léxico con uso semánticamente INCORRECTO no es éxito limpio: no
    # eleva la confianza.
    mismatched = _summary(
        [
            _row(
                "transfer:story",
                condition="open_context",
                error_type="semantic_mismatch",
            )
        ]
    )
    assert mismatched["clean_successes"] == 0
    assert mismatched["unscaffolded_clean_successes"] == 0
    assert mismatched["transfer_confidence"]["level"] == "none"

    # Un éxito limpio SIN condición declarada (legacy) cuenta como limpio, pero
    # no como no andamiado: la independencia sigue siendo 0.
    legacy = _summary([_row("transfer:future")])
    assert legacy["clean_successes"] == 1
    assert legacy["unscaffolded_clean_successes"] == 0
    assert legacy["transfer_confidence"]["drivers"]["independence"] == 0.0


def test_confidence_recency_days_is_informational_and_not_in_the_score():
    summary = _summary(
        [_row("transfer:story", condition="open_context", day="2026-01-01")]
    )
    without_now = transfer_confidence(summary)
    with_now = transfer_confidence(summary, now="2026-01-11T10:00:00+00:00")
    assert without_now["recency_days"] is None
    assert with_now["recency_days"] == 10
    assert with_now["score"] == without_now["score"]


# ---------------------------------------------------------- paridad pura ↔ SQL


def test_confidence_agrees_between_pure_and_sql(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    _seed_transfer_evidence(
        uid, "travel", "transfer:story", condition="open_context", day="2026-01-01"
    )
    _seed_transfer_evidence(
        uid, "travel", "transfer:future", condition="open_context", day="2026-01-02"
    )
    _seed_transfer_evidence(
        uid, "travel", "transfer:work", condition="open_context", day="2026-01-03"
    )

    sql = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    pure = summarize_evidence(evidence_repo.list_evidence(uid, "travel"))
    assert sql["transfer_confidence"] == pure["transfer_confidence"]
    assert sql["transfer_confidence"]["level"] == "high"
    assert sql["transfer_state"] == pure["transfer_state"] == "transfer_stable"
