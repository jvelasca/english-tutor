"""V3.47 — Transfer Evidence 2.0 (P1-02 de la auditoría de V3.46.0).

La auditoría de V3.46.0 señaló que la escalera de transferencia aún acreditaba
demasiado pronto: bastaba UN éxito limpio no andamiado para declarar
`transfer_demonstrated`, y `transfer_stable` se alcanzaba con dos días. Eso
confunde «la ha usado sin ayuda una vez» con «puede transferirla de forma
estable».

V3.47 endurece los requisitos de forma ADITIVA y sin migración:

- `transfer_demonstrated` exige >= 2 éxitos limpios en condiciones NO andamiadas
  (`TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED`), además de 2 contextos limpios con
  diversidad real;
- `transfer_stable` exige >= 3 contextos, >= 3 días distintos con éxito limpio y
  >= 2 objetivos comunicativos distintos
  (`TRANSFER_STABLE_MIN_DAYS`/`TRANSFER_STABLE_MIN_GOALS`);
- el resumen expone la evidencia fina para poder medirlo y explicarlo
  (`unscaffolded_clean_success_contexts`, `unscaffolded_clean_success_days`,
  `clean_success_goals`, `last_clean_success_at`,
  `last_unscaffolded_clean_success_at`).

Fallback legacy intacto: sin datos de condición (filas previas a V3.46) se
conserva la regla anterior; sin datos de diversidad, la de V3.43.
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


# ------------------------------------------------ señales finas (V3.47)


def test_context_signals_expose_unscaffolded_evidence_and_goals():
    rows = [
        _row("transfer:story", condition="cued_context", day="2026-01-01"),
        _row("transfer:future", condition="cued_context", day="2026-01-01"),
        _row("transfer:work", condition="open_context", day="2026-01-02"),
        _row("transfer:opinion", condition="open_context", day="2026-01-03"),
    ]
    signals = context_signals(rows)
    assert signals["unscaffolded_clean_successes"] == 2
    assert signals["unscaffolded_clean_success_contexts"] == [
        "transfer:opinion",
        "transfer:work",
    ]
    assert signals["unscaffolded_clean_success_days"] == 2
    # Objetivos comunicativos distintos de los contextos con éxito limpio.
    assert set(signals["clean_success_goals"]) == {
        "narrate",
        "plan",
        "describe",
        "give_opinion",
    }
    assert signals["last_clean_success_at"] == "2026-01-03T10:00:00+00:00"
    assert (
        signals["last_unscaffolded_clean_success_at"] == "2026-01-03T10:00:00+00:00"
    )


def test_context_signals_ignore_mismatched_and_legacy_rows_for_the_new_fields():
    rows = [
        _row("transfer:story", error_type="semantic_mismatch"),  # no limpio
        _row("transfer:future"),  # limpio pero SIN condición (legacy)
    ]
    signals = context_signals(rows)
    assert signals["unscaffolded_clean_successes"] == 0
    assert signals["unscaffolded_clean_success_contexts"] == []
    assert signals["unscaffolded_clean_success_days"] == 0
    assert signals["last_unscaffolded_clean_success_at"] == ""
    # El limpio legacy sí alimenta `last_clean_success_at` (es un éxito limpio).
    assert signals["last_clean_success_at"] == "2026-01-01T10:00:00+00:00"


# -------------------------------------------- escalera endurecida (V3.47)


def test_transfer_demonstrated_requires_two_unscaffolded_successes():
    # Dos contextos limpios con diversidad real, pero solo UNO no andamiado: ya
    # no acredita transferencia (antes de V3.47 sí lo hacía).
    one_unscaffolded = _summary(
        [
            _row("transfer:story", condition="cued_context"),
            _row("transfer:future", condition="cued_context"),
            _row("transfer:work", condition="open_context"),
        ]
    )
    assert one_unscaffolded["context_diversity"]["diverse_dimensions"] >= 2
    assert one_unscaffolded["unscaffolded_clean_successes"] == 1
    assert transfer_state(one_unscaffolded) == "contextualized"

    # Con DOS éxitos no andamiados en contextos distintos sí se demuestra.
    two_unscaffolded = _summary(
        [
            _row("transfer:story", condition="cued_context"),
            _row("transfer:future", condition="cued_context"),
            _row("transfer:work", condition="open_context"),
            _row("transfer:opinion", condition="open_context"),
        ]
    )
    assert two_unscaffolded["unscaffolded_clean_successes"] == 2
    assert transfer_state(two_unscaffolded) == "transfer_demonstrated"


def test_transfer_stable_requires_three_days_and_goals():
    # 3 contextos, 2 éxitos no andamiados, pero solo 2 días: demostrada, no estable.
    two_days = _summary(
        [
            _row("transfer:story", condition="open_context", day="2026-01-01"),
            _row("transfer:future", condition="open_context", day="2026-01-01"),
            _row("transfer:work", condition="open_context", day="2026-01-02"),
        ]
    )
    assert two_days["clean_success_days"] == 2
    assert transfer_state(two_days) == "transfer_demonstrated"

    # Tres días distintos: ahora sí es estable.
    three_days = _summary(
        [
            _row("transfer:story", condition="open_context", day="2026-01-01"),
            _row("transfer:future", condition="open_context", day="2026-01-02"),
            _row("transfer:work", condition="open_context", day="2026-01-03"),
        ]
    )
    assert three_days["clean_success_days"] == 3
    assert transfer_state(three_days) == "transfer_stable"

    # La puerta de OBJETIVOS se evalúa con un resumen explícito: 3 contextos y 3
    # días, pero un único objetivo comunicativo → demostrada, nunca estable.
    single_goal = {
        "clean_success_contexts": [
            "transfer:story",
            "transfer:future",
            "transfer:work",
        ],
        "clean_successes": 3,
        "clean_success_days": 3,
        "clean_success_goals": ["narrate"],
        "context_diversity": {"diverse_dimensions": 3},
        "transfer_conditions": {"open_context": {"attempts": 3, "clean_successes": 3}},
        "unscaffolded_clean_successes": 3,
    }
    assert transfer_state(single_goal) == "transfer_demonstrated"


def test_transfer_stable_falls_back_to_bank_goals_without_the_declared_field():
    # Un resumen de V3.47 en adelante trae `clean_success_goals`, pero uno parcial
    # (por ejemplo de una versión intermedia) se deriva del propio banco.
    summary = {
        "clean_success_contexts": [
            "transfer:story",
            "transfer:future",
            "transfer:work",
        ],
        "clean_successes": 3,
        "clean_success_days": 3,
        "context_diversity": {"diverse_dimensions": 3},
        "transfer_conditions": {"open_context": {"attempts": 3, "clean_successes": 3}},
        "unscaffolded_clean_successes": 3,
    }
    assert transfer_state(summary) == "transfer_stable"


def test_transfer_state_keeps_the_legacy_rule_without_condition_data():
    # Filas de V3.43 (sin condición): no se puede afirmar que falte el requisito,
    # así que la regla anterior se conserva (cero regresión).
    legacy = _summary(
        [
            _row("transfer:story"),
            _row("transfer:future"),
        ]
    )
    assert legacy["transfer_conditions"] == {}
    assert transfer_state(legacy) == "transfer_demonstrated"


def test_constants_declare_the_hardened_ladder():
    assert evidence.TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED == 2
    assert evidence.TRANSFER_STABLE_MIN_CONTEXTS == 3
    assert evidence.TRANSFER_STABLE_MIN_DAYS == 3
    assert evidence.TRANSFER_STABLE_MIN_GOALS == 2
    assert evidence.TRANSFER_MIN_SUCCESSES == 2


# ------------------------------------------------- paridad pura ↔ SQL


def test_new_transfer_evidence_fields_agree_between_pure_and_sql(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    _seed_transfer_evidence(
        uid, "travel", "transfer:story", condition="cued_context", day="2026-01-01"
    )
    _seed_transfer_evidence(
        uid, "travel", "transfer:future", condition="cued_context", day="2026-01-01"
    )
    _seed_transfer_evidence(
        uid, "travel", "transfer:work", condition="open_context", day="2026-01-02"
    )
    _seed_transfer_evidence(
        uid, "travel", "transfer:opinion", condition="open_context", day="2026-01-03"
    )

    sql = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    pure = summarize_evidence(evidence_repo.list_evidence(uid, "travel"))
    for key in (
        "unscaffolded_clean_success_contexts",
        "unscaffolded_clean_success_days",
        "clean_success_goals",
        "last_clean_success_at",
        "last_unscaffolded_clean_success_at",
        "transfer_state",
    ):
        assert sql[key] == pure[key], key
    assert sql["unscaffolded_clean_successes"] == 2
    assert sql["transfer_state"] == "transfer_stable"
