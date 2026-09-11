"""V3.44 — Lexicón sense-aware + scoring semántico 2.0.

Cierra los dos P1 conceptuales de la auditoría de V3.43.0:

- **P1-01**: la adecuación semántica deja de usar la `pos` GLOBAL como
  sustituto de sentido. La unidad declara sus SENTIDOS y el uso se juzga contra
  las familias POS de esos sentidos; `I plan my trip` deja de ser un falso
  positivo cuando `plan` declara sentido verbal.
- **P1-02**: la taxonomía gana `incorrect`. Solo `incorrect` bloquea el clean
  success (`semantic_mismatch`); `suspect` es advisory (`semantic_doubt`) y
  NUNCA destruye la evidencia léxica.

Se mantiene la premisa 21: el scoring es determinista y sin LLM.
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
from services import dictionary_content, lexicon, semantics
from services.evidence import (
    SEMANTIC_DOUBT_ERROR,
    SEMANTIC_MISMATCH_ERROR,
    TRANSFER_ERROR_TYPES,
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
    summary = {
        "attempts": len(rows),
        "successes": sum(1 for row in rows if row.get("success")),
    }
    summary.update(context_signals(rows))
    return with_transfer_state(summary)


def _row(context_id: str, error_type: str, day: str = "2026-01-01") -> dict:
    return {
        "context_id": context_id,
        "success": 1,
        "error_type": error_type,
        "occurred_at": f"{day}T10:00:00+00:00",
    }


# ---------------------------------------------------- semántica pura (P1-01)


def test_pos_family_prefers_verb_and_ignores_other_categories():
    assert semantics.pos_family("phrasal verb") == "verb"
    assert semantics.pos_family("Noun") == "noun"
    assert semantics.pos_family("adjective") == ""
    assert semantics.pos_family("") == ""


def test_families_from_senses_falls_back_to_the_global_pos():
    senses = [{"pos": "noun"}, {"pos": "verb"}, {"pos": "adjective"}]
    assert semantics.families_from_senses(senses) == {"noun", "verb"}
    # Sin sentidos reconocibles se conserva la compatibilidad con la POS global.
    assert semantics.families_from_senses([], pos="noun") == {"noun"}
    assert semantics.families_from_senses(None, pos="adverbio") == set()


def test_semantic_adequacy_needs_data_to_judge():
    assert semantics.semantic_adequacy("travel", "I travel by train.") == (
        semantics.SENSE_UNKNOWN
    )
    # Sin la unidad en el texto tampoco se inventa.
    assert semantics.semantic_adequacy(
        "travel", "I go by train.", senses=[{"pos": "verb"}]
    ) == semantics.SENSE_UNKNOWN


def test_multi_word_units_abstain_instead_of_risking_a_false_incorrect():
    got = lexicon.score_transfer_attempt(
        "look after",
        "I look after my sister every day.",
        senses=[{"pos": "verb", "gloss": "to care for"}],
    )
    assert got["passed"] is True
    assert got["adequacy"] == semantics.SENSE_UNKNOWN
    assert got["error_type"] == "correct"


# ------------------------------------------------ regresión P1-01 (el falso +)


def test_polysemous_noun_verb_word_is_no_longer_a_false_positive():
    """El caso que motivó V3.44: `plan` declara sentido verbal y la frase es
    correcta. Con la `pos` global `noun` (V3.43) marcaba falso positivo."""
    got = lexicon.score_transfer_attempt(
        "plan",
        "I plan my trip next week.",
        senses=[
            {"pos": "noun", "gloss": "an arrangement"},
            {"pos": "verb", "gloss": "to decide to do something"},
        ],
    )
    assert got["passed"] is True
    assert got["lexical_transfer"] is True
    assert got["adequacy"] == semantics.SENSE_FIT
    assert got["semantic_fit"] is True
    assert got["error_type"] == "correct"


def test_a_legit_occurrence_prevents_a_false_incorrect():
    got = lexicon.score_transfer_attempt(
        "bank",
        "I bank there. The bank is closed.",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
    )
    # Hay al menos un uso válido (el segundo): no se declara contradicción.
    assert got["adequacy"] == semantics.SENSE_FIT


def test_strong_contradiction_is_incorrect_and_blocks_the_clean_success():
    got = lexicon.score_transfer_attempt(
        "bank",
        "I bank money every day.",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
    )
    assert got["passed"] is True  # la evidencia LÉXICA se conserva
    assert got["lexical_transfer"] is True
    assert got["adequacy"] == semantics.SENSE_INCORRECT
    assert got["semantic_fit"] is False
    assert got["error_type"] == SEMANTIC_MISMATCH_ERROR


def test_weak_contradiction_is_suspect_advisory():
    got = lexicon.score_transfer_attempt(
        "take",
        "The take was long today.",
        senses=[{"pos": "verb", "gloss": "to grab"}],
    )
    assert got["passed"] is True
    assert got["adequacy"] == semantics.SENSE_SUSPECT
    assert got["error_type"] == SEMANTIC_DOUBT_ERROR


def test_inflected_verb_form_is_a_strong_verb_cue():
    # La pista se prueba en la capa PURA (el scoring léxico exige que la unidad
    # aparezca tal cual; aquí interesa solo el rol detectado).
    tokens = ["she", "banked", "the", "money", "yesterday"]
    assert semantics.occurrence_role(tokens, 1, "bank") == ("verb", "strong")


def test_auxiliary_before_the_unit_is_a_strong_verb_cue():
    got = lexicon.score_transfer_attempt(
        "bank",
        "They will bank the money tomorrow.",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
    )
    assert got["passed"] is True
    assert got["adequacy"] == semantics.SENSE_INCORRECT
    assert got["error_type"] == SEMANTIC_MISMATCH_ERROR


def test_transfer_taxonomy_is_a_superset_of_the_lexical_one():
    assert SEMANTIC_MISMATCH_ERROR in TRANSFER_ERROR_TYPES
    assert SEMANTIC_DOUBT_ERROR in TRANSFER_ERROR_TYPES
    assert lexicon.score_write_attempt("travel", "I usually travel by train.") == {
        "used_word": True,
        "word_count": 5,
        "passed": True,
        "error_type": "correct",
    }


# --------------------------------------- clean success y estado (P1-02)


def test_only_incorrect_blocks_a_clean_success():
    doubt = context_signals([_row("transfer:story", SEMANTIC_DOUBT_ERROR)])
    assert doubt["success_contexts"] == ["transfer:story"]
    assert doubt["clean_success_contexts"] == ["transfer:story"]
    assert doubt["clean_successes"] == 1

    mismatch = context_signals([_row("transfer:story", SEMANTIC_MISMATCH_ERROR)])
    assert mismatch["success_contexts"] == ["transfer:story"]
    assert mismatch["clean_success_contexts"] == []
    assert mismatch["clean_successes"] == 0
    assert mismatch["transfer"] is False


def test_transfer_state_advances_with_doubt_but_not_with_mismatch():
    # Dos usos dudosos SÍ cuentan como limpios: la duda es advisory.
    doubt = _evidence(
        [
            _row("transfer:story", SEMANTIC_DOUBT_ERROR),
            _row("transfer:story", SEMANTIC_DOUBT_ERROR),
        ]
    )
    assert doubt["transfer_state"] == "emerging"

    # El mismatch NO cuenta como limpio: sin el segundo éxito limpio no avanza.
    blocked = _evidence(
        [
            _row("transfer:story", SEMANTIC_DOUBT_ERROR),
            _row("transfer:story", SEMANTIC_MISMATCH_ERROR),
        ]
    )
    assert blocked["transfer_state"] == "not_ready"


def test_pure_and_sql_summaries_agree_with_the_new_taxonomy(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    rows = [
        ("transfer:story", SEMANTIC_DOUBT_ERROR),
        ("transfer:future", SEMANTIC_DOUBT_ERROR),
        ("transfer:work", SEMANTIC_MISMATCH_ERROR),
    ]
    for day, (context, error_type) in enumerate(rows):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill="spontaneous_use",
            success=True,
            support_level="spontaneous",
            context_id=context,
            error_type=error_type,
            occurred_at=(base + timedelta(days=day)).isoformat(),
        )
    sql_summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")[
        "travel"
    ]
    pure_rows = [
        {**row, "success": bool(row["success"])}
        for row in evidence_repo.list_evidence(uid, "travel")
    ]
    pure_signals = context_signals(pure_rows)
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
    # El mismatch NO es clean; los doubt SÍ.
    assert sql_summary["clean_success_contexts"] == [
        "transfer:future",
        "transfer:story",
    ]


# ------------------------------------------------------ endpoint con sentidos


def test_transfer_endpoint_uses_the_senses_of_the_unit(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "plan")
    dictionary_repo.save_entry(
        "plan",
        pos="noun",
        definition="an arrangement",
        senses=[
            {"pos": "noun", "gloss": "an arrangement"},
            {"pos": "verb", "gloss": "to decide to do something"},
        ],
    )

    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "plan",
                "text": "I plan my trip next week.",
                "context_id": "transfer:story",
                "response_time_ms": 4100,
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"] is True
    assert body["adequacy"] == "fit"
    assert body["error_type"] == "correct"

    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["plan"]
    assert summary["clean_success_contexts"] == ["transfer:story"]


def test_transfer_endpoint_persists_a_strong_mismatch(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "bank")
    dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="a financial place",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
    )

    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "bank",
                "text": "I bank money every day.",
                "context_id": "transfer:story",
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"] is True
    assert body["adequacy"] == "incorrect"
    assert body["error_type"] == SEMANTIC_MISMATCH_ERROR

    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["bank"]
    assert summary["clean_success_contexts"] == []
    assert summary["transfer"] is False


def test_dictionary_lookup_exposes_the_senses(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="a financial place",
        senses=[{"pos": "noun", "gloss": "a financial place"}],
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}", json={"word": "bank"}
        )
    assert res.status_code == 200, res.text
    assert res.json()["senses"] == [{"pos": "noun", "gloss": "a financial place"}]
