"""V3.43 (Transfer 2.0) — target oculto, semanticidad, diversidad y estado.

La auditoría de V3.42.0 detectó que la evidencia de transferencia estaba
SOBREESTIMADA. Esta release cierra los cuatro P1:

- P1-01: la consigna de transferencia muestra un ESCENARIO, nunca la unidad
  objetivo (antes daba la palabra y solo había que insertarla);
- P1-02: el TRANSFER LÉXICO (`lexical_transfer`) se separa de la ADECUACIÓN
  SEMÁNTICA (`semantic_fit`/`adequacy`), con un proxy determinista y advisory;
- P1-03: la diversidad contextual se mide de verdad (`context_diversity`), no
  con `context_id A != context_id B`;
- P1-04: `transfer_state` formaliza el eje (de `not_ready` a `automatic`) en
  lugar de un booleano.

Se mantiene la premisa 21: el LLM no decide evidencia; el proxy semántico es
observacional y nunca bloquea la evidencia léxica, solo la separa de los ÉXITOS
LIMPIOS que hacen avanzar el estado de transferencia.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import lexicon, planner, transfer
from services.evidence import (
    SEMANTIC_MISMATCH_ERROR,
    TRANSFER_ERROR_TYPES,
    TRANSFER_STATES,
    context_signals,
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


def _evidence(rows: list[dict]) -> dict:
    """Resumen de transferencia mínimo desde filas sintéticas (puro)."""
    summary = {
        "attempts": len(rows),
        "successes": sum(1 for row in rows if row.get("success")),
    }
    summary.update(context_signals(rows))
    return with_transfer_state(summary)


def _clean_row(context_id: str, day: str = "2026-01-01") -> dict:
    return {
        "context_id": context_id,
        "success": 1,
        "error_type": "correct",
        "occurred_at": f"{day}T10:00:00+00:00",
    }


# ------------------------------------------- banco de contextos (P1-01/P1-03)


def test_context_bank_declares_attributes_and_never_shows_the_target():
    for context in transfer.TRANSFER_CONTEXTS:
        attributes = transfer.context_attributes(context["id"])
        assert attributes["topic"]
        assert attributes["communicative_goal"]
        assert attributes["discourse_type"]
        assert "{word}" not in attributes["prompt"]
    # El prefijo de ledger se acepta igual que el id desnudo.
    assert transfer.context_attributes("transfer:story") == transfer.context_attributes(
        "story"
    )
    assert transfer.context_attributes("no-existe") == {}


def test_context_dimensions_and_distance_are_deterministic():
    dimensions = transfer.context_dimensions(["transfer:story", "transfer:future"])
    # Dos contextos con dimensiones distintas: no basta con el id.
    assert len([values for values in dimensions.values() if len(values) >= 2]) >= 2
    assert transfer.context_distance("transfer:story", "transfer:story") == 0
    assert transfer.context_distance("transfer:story", "transfer:work") >= 2
    assert transfer.context_distance("transfer:story", "no-existe") == 0


def test_context_diversity_requires_real_dimension_change():
    empty = transfer.context_diversity([])
    assert empty == {
        "distinct_contexts": 0,
        "dimensions": {},
        "diverse_dimensions": 0,
        "score": 0.0,
    }
    # Un `context_id` no reconocido no aporta dimensiones ni diversidad.
    only_unknown = transfer.context_diversity(["lexicon:writing", "drill:recall"])
    assert only_unknown["distinct_contexts"] == 0
    assert only_unknown["diverse_dimensions"] == 0
    # Dos contextos del banco con dimensiones distintas: diversidad real.
    diverse = transfer.context_diversity(["transfer:story", "transfer:future"])
    assert diverse["distinct_contexts"] == 2
    assert diverse["diverse_dimensions"] >= transfer.CONTEXT_DIVERSITY_MIN
    assert transfer.CONTEXT_DIVERSITY_MIN == 2


def test_context_for_prefers_the_most_distant_context_from_successes():
    got = transfer.context_for(
        "travel",
        used_context_ids=["transfer:story"],
        success_context_ids=["transfer:story"],
    )
    assert got["context_id"] != "transfer:story"
    # El contexto servido es NOVEDOSO respecto al ya logrado.
    assert transfer.context_distance(got["context_id"], "transfer:story") >= 2


# -------------------------------------------------- proxy semántico (P1-02)


def test_score_transfer_attempt_separates_lexical_from_semantic():
    suspect = lexicon.score_transfer_attempt(
        "bank", "I bank money every day.", pos="noun"
    )
    assert suspect["passed"] is True
    assert suspect["lexical_transfer"] is True
    assert suspect["semantic_fit"] is False
    assert suspect["adequacy"] == "suspect"
    assert suspect["error_type"] == SEMANTIC_MISMATCH_ERROR

    fit = lexicon.score_transfer_attempt(
        "bank", "The bank closes early today.", pos="noun"
    )
    assert fit["passed"] is True
    assert fit["semantic_fit"] is True
    assert fit["adequacy"] == "fit"
    assert fit["error_type"] == "correct"


def test_score_transfer_attempt_flags_verb_after_determiner():
    got = lexicon.score_transfer_attempt(
        "take", "The take was long today.", pos="verb"
    )
    assert got["passed"] is True
    assert got["adequacy"] == "suspect"
    assert got["error_type"] == SEMANTIC_MISMATCH_ERROR


def test_score_transfer_attempt_is_unknown_without_pos():
    got = lexicon.score_transfer_attempt("travel", "I travel by train.")
    assert got["adequacy"] == "unknown"
    assert got["semantic_fit"] is None
    assert got["error_type"] == "correct"


def test_write_scoring_is_unchanged_and_transfer_taxonomy_is_a_superset():
    got = lexicon.score_write_attempt("travel", "I usually travel by train.")
    # Contrato EXACTO de escritura (P2-04: acredita producción léxica).
    assert got == {
        "used_word": True,
        "word_count": 5,
        "passed": True,
        "error_type": "correct",
    }
    assert SEMANTIC_MISMATCH_ERROR in TRANSFER_ERROR_TYPES


# ------------------------------------ señales limpias y estado (P1-03/P1-04)


def test_semantic_mismatch_is_lexical_success_but_not_clean():
    rows = [
        {
            "context_id": "transfer:story",
            "success": 1,
            "error_type": SEMANTIC_MISMATCH_ERROR,
            "occurred_at": "2026-01-01T10:00:00+00:00",
        }
    ]
    signals = context_signals(rows)
    assert signals["success_contexts"] == ["transfer:story"]
    assert signals["clean_success_contexts"] == []
    assert signals["clean_successes"] == 0
    assert signals["transfer"] is False
    assert transfer_state(signals) == "not_ready"


def test_transfer_state_transitions():
    assert set(TRANSFER_STATES) == {
        "not_ready",
        "emerging",
        "contextualized",
        "transfer_demonstrated",
        "transfer_stable",
        "automatic",
    }
    not_ready = _evidence([_clean_row("transfer:story")])
    assert not_ready["transfer_state"] == "not_ready"
    assert transfer_state(not_ready) in TRANSFER_STATES

    emerging = _evidence([_clean_row("transfer:story"), _clean_row("transfer:story")])
    assert emerging["transfer_state"] == "emerging"

    # Dos contextos, pero uno fuera del banco: sin diversidad real → no demostrada.
    contextualized = _evidence(
        [_clean_row("lexicon:writing"), _clean_row("transfer:story")]
    )
    assert contextualized["transfer_state"] == "contextualized"

    demonstrated = _evidence(
        [_clean_row("transfer:story"), _clean_row("transfer:future")]
    )
    assert demonstrated["transfer_state"] == "transfer_demonstrated"

    stable = _evidence(
        [
            _clean_row("transfer:story", "2026-01-01"),
            _clean_row("transfer:future", "2026-01-01"),
            _clean_row("transfer:work", "2026-01-02"),
        ]
    )
    assert stable["transfer_state"] == "transfer_stable"

    automatic = dict(stable)
    automatic["automatic_skills"] = ["spontaneous_use"]
    assert transfer_state(automatic) == "automatic"


def test_transfer_state_honours_the_legacy_boolean_on_partial_summaries():
    """P2-02 de la auditoría pre-release de V3.43: un resumen parcial/legacy SIN
    los campos de V3.43 no se degrada. Si traía `transfer = true`, el estado sigue
    siendo de transferencia DEMOSTRADA (sin `clean_success_days` no se puede
    afirmar estabilidad, así que no se asciende más)."""
    legacy = {
        "success_contexts": ["transfer:story", "transfer:future"],
        "transfer": True,
    }
    assert transfer_state(legacy) == "transfer_demonstrated"
    assert planner.has_contextual_transfer(legacy) is True

    # Sin el booleano no se inventa transferencia: se queda contextualizada.
    assert (
        transfer_state({"success_contexts": ["transfer:story", "transfer:future"]})
        == "contextualized"
    )

    # Tres contextos pero sin días: demostrada, nunca estable.
    three_contexts = {
        "success_contexts": ["transfer:story", "transfer:future", "transfer:work"],
        "transfer": True,
    }
    assert transfer_state(three_contexts) == "transfer_demonstrated"


def test_planner_reads_the_transfer_state():
    emerging = _evidence([_clean_row("transfer:story"), _clean_row("transfer:story")])
    assert planner.transfer_gap(emerging) is True
    assert planner.has_contextual_transfer(emerging) is False

    contextualized = _evidence(
        [_clean_row("lexicon:writing"), _clean_row("transfer:story")]
    )
    assert planner.transfer_gap(contextualized) is True

    demonstrated = _evidence(
        [_clean_row("transfer:story"), _clean_row("transfer:future")]
    )
    assert planner.transfer_gap(demonstrated) is False
    assert planner.has_contextual_transfer(demonstrated) is True

    assert planner.transfer_gap(_evidence([_clean_row("transfer:story")])) is False

    signals = planner.planned_signals(demonstrated, {})
    assert signals["transfer_state"] == "transfer_demonstrated"
    assert signals["context_diversity"]["diverse_dimensions"] >= 2


# ------------------------------------------------- paridad pura ↔ SQL (P1-03)


def test_new_transfer_fields_agree_between_pure_and_sql_summaries(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    for word in ("travel", "story", "future"):
        _seed_word(uid, word)
    base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    for day, context in enumerate(
        ["transfer:story", "transfer:future", "transfer:story"]
    ):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill="spontaneous_use",
            success=True,
            support_level="spontaneous",
            context_id=context,
            error_type="correct",
            occurred_at=(base + timedelta(days=day)).isoformat(),
        )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="travel",
        skill="spontaneous_use",
        success=True,
        support_level="spontaneous",
        context_id="transfer:work",
        error_type=SEMANTIC_MISMATCH_ERROR,
        occurred_at=(base + timedelta(days=3)).isoformat(),
    )
    sql_summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")[
        "travel"
    ]
    rows = [
        {**row, "success": bool(row["success"])}
        for row in evidence_repo.list_evidence(uid, "travel")
    ]
    pure_signals = context_signals(rows)
    for key in (
        "contexts",
        "context_attempts",
        "success_contexts",
        "home_context",
        "clean_contexts",
        "clean_successes",
        "clean_success_contexts",
        "clean_success_days",
        "context_diversity",
        "transfer",
    ):
        assert sql_summary[key] == pure_signals[key], key
    assert sql_summary["transfer_state"] == transfer_state(sql_summary)


# ------------------------------------------------------ endpoint con POS (P1-02)


def test_transfer_endpoint_persists_semantic_mismatch(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "bank")
    dictionary_repo.save_entry("bank", pos="noun", definition="a financial place")

    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "bank",
                "text": "I bank money every day.",
                "context_id": "transfer:story",
                "response_time_ms": 4100,
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"] is True
    assert body["lexical_transfer"] is True
    assert body["adequacy"] == "suspect"
    assert body["error_type"] == SEMANTIC_MISMATCH_ERROR

    rows = evidence_repo.list_evidence(uid, "bank")
    assert len(rows) == 1
    assert rows[0]["success"] == 1
    assert rows[0]["error_type"] == SEMANTIC_MISMATCH_ERROR

    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["bank"]
    assert summary["success_contexts"] == ["transfer:story"]
    assert summary["clean_success_contexts"] == []
    assert summary["transfer_state"] == "not_ready"
    assert summary["transfer"] is False
