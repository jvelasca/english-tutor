"""Tests de V3.39 (Fase 3C) — robustez de las señales pedagógicas.

La auditoría de V3.38.1 (P2) señaló que el resumen de evidencia medía todo el
histórico: un `wrong_word` de hace cuarenta repasos bloqueaba la automaticidad
igual que uno de ayer, y la latencia era una media única que ocultaba la cola
lenta. Además, la automaticidad tenía DOS definiciones (global y por modalidad)
que podían divergir, y el intervalo del ledger se encadenaba al último evento
INSERTADO en lugar del cronológicamente anterior.

Se cubre aquí, con funciones puras y con la paridad pura↔SQL:

- `recency_signals`: ventana de recencia, tasa de error reciente, `wrong_word`
  reciente, percentiles de latencia (`median`/`p75`/`p90`), media reciente y
  tendencia;
- `_has_grave_error` sobre la VENTANA (una confusión corregida ya no bloquea);
- `is_automatic` unificado con `automatic_skills` cuando hay segmentación, con
  el criterio global de V3.38.1 como fallback de resúmenes parciales;
- encadenado CRONOLÓGICO del ledger (`occurred_at` fuera de orden);
- batching de los ejemplos del peldaño `cloze` (`example_for_many`).
"""
from __future__ import annotations

from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from services import evidence as evidence_svc
from services import example_sentences


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _row(
    occurred_at: str,
    *,
    success: bool,
    error_type: str = "",
    response_time_ms: int | None = None,
    ident: int = 0,
) -> dict:
    return {
        "id": ident,
        "occurred_at": occurred_at,
        "success": success,
        "error_type": error_type,
        "response_time_ms": response_time_ms,
    }


# --- Ventana de recencia ----------------------------------------------------


def test_recent_window_only_counts_the_latest_events():
    rows = [
        _row(
            f"2026-09-{day:02d}T10:00:00+00:00",
            success=False,
            error_type="wrong_word",
        )
        for day in range(1, 13)
    ]
    # Solo los 3 últimos son aciertos: la ventana (10) recorta el histórico.
    for row in rows[-3:]:
        row["success"] = True
        row["error_type"] = ""
    signals = evidence_svc.recency_signals(rows)
    assert signals["recent_attempts"] == evidence_svc.RECENT_WINDOW_EVENTS
    assert signals["recent_wrong_word"] == 7  # los 7 fallos dentro de la ventana
    assert signals["recent_error_rate"] == 0.7


def test_recent_window_is_chronological_not_insertion_order():
    rows = [
        _row("2026-09-03T10:00:00+00:00", success=False, error_type="wrong_word"),
        _row("2026-09-01T10:00:00+00:00", success=True),
        _row("2026-09-02T10:00:00+00:00", success=True),
    ]
    signals = evidence_svc.recency_signals(rows, window=2)
    # La ventana son 09-02 y 09-03 (los dos más recientes), no los dos primeros.
    assert signals["recent_attempts"] == 2
    assert signals["recent_wrong_word"] == 1
    assert signals["recent_error_rate"] == 0.5


def test_recent_events_does_not_mutate_the_caller_list():
    rows = [
        _row("2026-09-02T10:00:00+00:00", success=True),
        _row("2026-09-01T10:00:00+00:00", success=True),
    ]
    evidence_svc.recent_events(rows, limit=1)
    assert [row["occurred_at"] for row in rows] == [
        "2026-09-02T10:00:00+00:00",
        "2026-09-01T10:00:00+00:00",
    ]


# --- Distribución de latencia ----------------------------------------------


def test_latency_percentiles_use_nearest_rank():
    rows = [
        _row(
            f"2026-09-{day:02d}T10:00:00+00:00",
            success=True,
            response_time_ms=ms,
        )
        for day, ms in enumerate((1000, 2000, 3000, 10000), start=1)
    ]
    signals = evidence_svc.recency_signals(rows)
    assert signals["median_response_time_ms"] == 2000
    assert signals["p75_response_time_ms"] == 3000
    assert signals["p90_response_time_ms"] == 10000
    assert signals["recent_response_time_ms"] == 4000.0


def test_latency_trend_compares_the_window_with_the_older_history():
    rows = [
        _row(
            f"2026-09-{day:02d}T10:00:00+00:00",
            success=True,
            response_time_ms=1000,
        )
        for day in range(1, 5)
    ] + [
        _row(
            f"2026-09-{day:02d}T10:00:00+00:00",
            success=True,
            response_time_ms=5000,
        )
        for day in range(5, 15)
    ]
    signals = evidence_svc.recency_signals(rows)
    # 10 recientes a 5000 ms contra 4 antiguos a 1000 ms: se está volviendo lento.
    assert signals["latency_trend"] == 4000.0


def test_latency_signals_ignore_unmeasured_rows():
    rows = [
        _row("2026-09-01T10:00:00+00:00", success=True),
        _row("2026-09-02T10:00:00+00:00", success=True, response_time_ms=None),
    ]
    signals = evidence_svc.recency_signals(rows)
    assert signals["median_response_time_ms"] is None
    assert signals["recent_response_time_ms"] is None
    assert signals["latency_trend"] is None


# --- Fallo grave: solo la ventana -------------------------------------------


def test_grave_error_only_looks_at_the_current_window():
    historically_confused = {
        "error_types": {"wrong_word": 5},
        "recent_wrong_word": 0,
        "skill_independent_successes": {"recall": 3},
        "skill_independent_days": {"recall": 3},
        "skill_successes": {"recall": 3},
        "skill_attempts": {"recall": 3},
    }
    assert evidence_svc.automatic_skills(historically_confused) == ["recall"]
    still_confused = {**historically_confused, "recent_wrong_word": 2}
    assert evidence_svc.automatic_skills(still_confused) == []


def test_partial_summary_without_window_falls_back_to_history():
    legacy = {
        "error_types": {"wrong_word": 2},
        "independent_successes": 3,
        "independent_success_days": 3,
        "success_rate": 1.0,
    }
    assert evidence_svc.is_automatic(legacy) is False


# --- Automaticidad: una sola definición -------------------------------------


def test_is_automatic_is_the_union_of_automatic_skills_when_segmented():
    mixed = evidence_svc.summarize_evidence(
        [
            _row("2026-09-01T10:00:00+00:00", success=True),
            _row("2026-09-03T10:00:00+00:00", success=True),
            _row("2026-09-05T10:00:00+00:00", success=True),
        ]
    )
    mixed.update(
        {
            "skill_successes": {
                "recall": 1,
                "written_production": 1,
                "spoken_production": 1,
            },
            "skill_attempts": {
                "recall": 1,
                "written_production": 1,
                "spoken_production": 1,
            },
            "skill_independent_successes": {
                "recall": 1,
                "written_production": 1,
                "spoken_production": 1,
            },
            "skill_independent_days": {
                "recall": 1,
                "written_production": 1,
                "spoken_production": 1,
            },
            "independent_successes": 3,
            "independent_success_days": 3,
            "success_rate": 1.0,
        }
    )
    assert evidence_svc.automatic_skills(mixed) == []
    assert evidence_svc.is_automatic(mixed) is False

    consolidated = {
        **mixed,
        "skill_independent_successes": {"recall": 3},
        "skill_independent_days": {"recall": 3},
        "skill_successes": {"recall": 3},
        "skill_attempts": {"recall": 3},
    }
    assert evidence_svc.automatic_skills(consolidated) == ["recall"]
    assert evidence_svc.is_automatic(consolidated) is True


def test_is_automatic_keeps_the_global_criterion_without_segmentation():
    assert (
        evidence_svc.is_automatic(
            {
                "independent_successes": 3,
                "independent_success_days": 3,
                "successes": 3,
                "attempts": 3,
                "success_rate": 1.0,
            }
        )
        is True
    )


def test_empty_summary_is_not_automatic():
    assert evidence_svc.is_automatic(evidence_svc.empty_summary()) is False
    assert evidence_svc.automatic_skills(evidence_svc.empty_summary()) == []


# --- Ledger: encadenado cronológico -----------------------------------------


def test_interval_chains_to_the_chronologically_previous_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        success=True,
        occurred_at="2026-09-01T10:00:00+00:00",
    )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        success=True,
        occurred_at="2026-09-03T10:00:00+00:00",
    )
    # Un evento IMPORTADO con fecha intermedia: su ancla es 09-01 (1 día), no el
    # último insertado 09-03 (que daría un intervalo negativo→0).
    late = evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        success=True,
        occurred_at="2026-09-02T10:00:00+00:00",
    )
    assert late is not None
    assert late["interval_since_last_evidence"] == 1.0


def test_last_evidence_at_can_look_before_a_mark(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    for day in ("2026-09-01T10:00:00+00:00", "2026-09-03T10:00:00+00:00"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            task="recall",
            success=True,
            occurred_at=day,
        )
    assert (
        evidence_repo.last_evidence_at(uid, "lexicon", "river")
        == "2026-09-03T10:00:00+00:00"
    )
    assert (
        evidence_repo.last_evidence_at(
            uid, "lexicon", "river", before="2026-09-02T00:00:00+00:00"
        )
        == "2026-09-01T10:00:00+00:00"
    )
    assert (
        evidence_repo.last_evidence_at(
            uid, "lexicon", "river", before="2026-08-01T00:00:00+00:00"
        )
        == ""
    )


# --- Paridad pura ↔ SQL de las señales nuevas -------------------------------


def test_recency_signals_pure_sql_parity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    for day in range(1, 13):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            task="recall",
            success=day % 2 == 0,
            error_type="" if day % 2 == 0 else "wrong_word",
            support_level="independent",
            response_time_ms=1000 * day,
            occurred_at=f"2026-09-{day:02d}T10:00:00+00:00",
        )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")["river"]
    pure = evidence_svc.summarize_evidence(
        evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    )
    assert aggregated == pure
    assert aggregated["recent_attempts"] == evidence_svc.RECENT_WINDOW_EVENTS
    assert aggregated["recent_wrong_word"] == pure["recent_wrong_word"]
    assert aggregated["median_response_time_ms"] == pure["median_response_time_ms"]
    assert aggregated["latency_trend"] is not None


# --- Batching de los ejemplos del peldaño `cloze` ---------------------------


def test_example_for_many_matches_the_single_lookup():
    batched = example_sentences.example_for_many(
        ["coffee", "flabbergasted", "Coffee"]
    )
    assert batched["coffee"] == example_sentences.example_for("coffee")
    assert batched["coffee"] is not None
    assert batched["coffee"]["source"] == "pronunciation_corpus"
    assert batched["flabbergasted"] is None


def test_example_for_many_handles_empty_and_normalizes():
    assert example_sentences.example_for_many([]) == {}
    assert example_sentences.example_for_many(["", "   "]) == {}
    assert set(example_sentences.example_for_many(["coffee", " coffee "])) == {
        "coffee"
    }
