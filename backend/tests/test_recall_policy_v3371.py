"""Tests de aceptación de V3.37.1 — política de consolidación y regresión.

La auditoría de V3.37.0 señaló dos P1 pedagógicos:

- **P1-01**: `next_recall_rung` ascendía con UN solo éxito;
- **P1-02**: no existía regresión: fallos repetidos no bajaban el apoyo.

V3.37.1 formaliza las dos políticas en la capa pura (`services.recall`):

    progresión:  un peldaño está SUPERADO solo con >= 2 éxitos en >= 2 DÍAS
                 NATURALES distintos (EVIDENCIA → CONSOLIDACIÓN → MÁS EXIGENCIA);
    regresión:   >= 2 fallos SIN ningún éxito en el peldaño ideal bajan la
                 recomendación a más apoyo (nunca por debajo de `translation`).

La evidencia legacy sin peldaño (`drill:recall`) no alimenta ninguna de las dos
políticas: no es evidencia negativa ni acredita un peldaño que no declaraba.

Se cubre la capa pura, la paridad pura↔SQL de los histogramas nuevos y el flujo
hasta la cola de repaso.
"""
from __future__ import annotations

from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from services import evidence as evidence_svc
from services import lexicon, recall


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Progresión: consolidación, no un acierto suelto -------------------------


def test_consolidation_requires_two_successes_on_distinct_days():
    assert recall.next_recall_rung({}, {}) == "translation"
    # Un solo éxito no supera el peldaño.
    one_success = {
        "recall_rungs": {"translation": 1},
        "recall_rung_days": {"translation": 1},
    }
    assert recall.next_recall_rung({}, one_success) == "translation"
    # Volumen el MISMO día tampoco: la evidencia debe estar espaciada.
    same_day = {
        "recall_rungs": {"translation": 4},
        "recall_rung_days": {"translation": 1},
    }
    assert recall.next_recall_rung({}, same_day) == "translation"
    # Dos éxitos en dos días distintos: peldaño superado.
    spaced = {
        "recall_rungs": {"translation": 2},
        "recall_rung_days": {"translation": 2},
    }
    assert recall.next_recall_rung({}, spaced) == "definition"


def test_ceiling_of_the_ladder_is_situation():
    # V3.38: con los tres peldaños previos consolidados, el ideal es `situation`.
    without_situation = {
        "recall_rungs": {"translation": 2, "definition": 2, "cloze": 2},
        "recall_rung_days": {"translation": 2, "definition": 2, "cloze": 2},
    }
    assert recall.next_recall_rung({}, without_situation) == "situation"
    # Y una vez consolidado `situation`, el techo se mantiene ahí.
    all_passed = {
        "recall_rungs": {
            "translation": 2,
            "definition": 2,
            "cloze": 2,
            "situation": 2,
        },
        "recall_rung_days": {
            "translation": 2,
            "definition": 2,
            "cloze": 2,
            "situation": 2,
        },
    }
    assert recall.next_recall_rung({}, all_passed) == "situation"


# --- Regresión: patrón de fallos, no un tropiezo -----------------------------


def test_single_failure_repeats_the_rung_without_regressing():
    evidence = {
        "recall_rungs": {"translation": 2},
        "recall_rung_days": {"translation": 2},
        "recall_rung_failures": {"definition": 1},
    }
    assert recall.next_recall_rung({}, evidence) == "definition"


def test_repeated_failures_regress_toward_more_support():
    # `cloze` se atraganta (2 fallos, 0 éxitos) → baja a `definition`.
    stuck_cloze = {
        "recall_rungs": {"translation": 2, "definition": 2},
        "recall_rung_days": {"translation": 2, "definition": 2},
        "recall_rung_failures": {"cloze": 2},
    }
    assert recall.next_recall_rung({}, stuck_cloze) == "definition"
    # `definition` también se atraganta → baja a `translation`.
    stuck_definition = {
        "recall_rungs": {"translation": 2},
        "recall_rung_days": {"translation": 2},
        "recall_rung_failures": {"definition": 3},
    }
    assert recall.next_recall_rung({}, stuck_definition) == "translation"


def test_regression_never_goes_below_translation():
    evidence = {
        "recall_rung_failures": {"translation": 5},
    }
    assert recall.next_recall_rung({}, evidence) == "translation"


def test_failures_do_not_regress_when_the_rung_has_any_success():
    # El patrón de remediación es "fallos SIN ningún éxito": un tropiezo con
    # algún acierto en el peldaño no baja la exigencia.
    evidence = {
        "recall_rungs": {"translation": 2, "definition": 1},
        "recall_rung_days": {"translation": 2, "definition": 1},
        "recall_rung_failures": {"definition": 2},
    }
    assert recall.next_recall_rung({}, evidence) == "definition"


def test_regressed_rung_still_degrades_down_toward_more_support():
    stuck_cloze = {
        "recall_rungs": {"translation": 2, "definition": 2},
        "recall_rung_days": {"translation": 2, "definition": 2},
        "recall_rung_failures": {"cloze": 2},
    }
    ideal = recall.next_recall_rung({}, stuck_cloze)
    assert ideal == "definition"
    # Si el peldaño regresado no tiene contenido, sigue bajando hacia más
    # apoyo; NUNCA sube a `cloze` (eso exigiría evidencia que no existe).
    assert recall.resolve_recall_cue(ideal, {"translation"}) == "translation"
    assert recall.resolve_recall_cue(ideal, {"cloze"}) is None


# --- Evidencia legacy sin peldaño --------------------------------------------


def test_legacy_evidence_never_feeds_the_ladder():
    legacy = evidence_svc.summarize_evidence(
        [
            {
                "occurred_at": "2026-09-01T10:00:00+00:00",
                "success": 1,
                "activity_id": "drill:recall",
            },
            {
                "occurred_at": "2026-09-02T10:00:00+00:00",
                "success": 0,
                "activity_id": "drill:recall",
            },
        ]
    )
    assert legacy["recall_rungs"] == {}
    assert legacy["recall_rung_days"] == {}
    assert legacy["recall_rung_failures"] == {}
    # Un alumno con historial legacy empieza en `translation`: su evidencia no
    # declara peldaño, así que no acredita progresión ni penaliza.
    assert recall.next_recall_rung({}, legacy) == "translation"


# --- Histogramas de la capa pura ---------------------------------------------


def test_summarize_evidence_histograms_rung_days_and_failures():
    rows = [
        {
            "occurred_at": "2026-09-01T10:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall:translation",
        },
        {
            # Mismo día natural: suma éxito pero no día.
            "occurred_at": "2026-09-01T18:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall:translation",
        },
        {
            "occurred_at": "2026-09-02T10:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall:translation",
        },
        {
            "occurred_at": "2026-09-03T10:00:00+00:00",
            "success": 0,
            "activity_id": "drill:recall:definition",
        },
        {
            "occurred_at": "2026-09-04T10:00:00+00:00",
            "success": 0,
            "activity_id": "drill:recall:definition",
        },
        {
            # Legacy sin peldaño: no entra en ningún histograma.
            "occurred_at": "2026-09-05T10:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall",
        },
    ]
    out = evidence_svc.summarize_evidence(rows)
    assert out["recall_rungs"] == {"translation": 3}
    assert out["recall_rung_days"] == {"translation": 2}  # 09-01 y 09-02
    assert out["recall_rung_failures"] == {"definition": 2}


# --- Paridad pura↔SQL del agregado -------------------------------------------


def test_rung_days_and_failures_pure_sql_parity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    events = [
        ("2026-09-01T10:00:00+00:00", "drill:recall:translation", True),
        ("2026-09-02T10:00:00+00:00", "drill:recall:translation", True),
        ("2026-09-03T10:00:00+00:00", "drill:recall:definition", False),
        ("2026-09-04T10:00:00+00:00", "drill:recall:definition", False),
    ]
    for at, activity_id, success in events:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            task="recall",
            activity_id=activity_id,
            success=success,
            support_level="cued",
            occurred_at=at,
        )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")[
        "river"
    ]
    pure = evidence_svc.summarize_evidence(
        evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    )
    assert aggregated == pure
    assert aggregated["recall_rung_days"] == {"translation": 2}
    assert aggregated["recall_rung_failures"] == {"definition": 2}
    # `translation` consolidado y `definition` atragantado → la política leída
    # del agregado real regresa a `translation`.
    assert recall.next_recall_rung({}, aggregated) == "translation"


# --- La cola de repaso sirve el peldaño regresado ----------------------------


def test_review_queue_serves_the_regressed_rung():
    row = {
        "word": "river",
        "exposure_count": 2,
        "exposure_days": 2,
        "production_count": 1,
        "production_days": 1,
        "speaking_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    card = {"target_id": "river", "due_at": "2026-09-09T10:00:00+00:00"}
    evidence = {
        "recall_rungs": {"translation": 2},
        "recall_rung_days": {"translation": 2},
        "recall_rung_failures": {"definition": 2},
    }
    item = lexicon.review_queue_item(
        row,
        card,
        now="2026-09-09T10:00:00+00:00",
        evidence=evidence,
        available_cues={"translation", "definition", "cloze"},
    )
    assert item["activity"] == "recall"
    # No avanza a `definition` (se le atraganta): vuelve a `translation`.
    assert item["recommended_cue"] == "translation"
    # La cola sigue sin exponer el cue ni la forma esperada.
    assert "cue" not in item
    assert "expected" not in item
