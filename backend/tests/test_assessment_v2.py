"""Tests de Assessment 2.0 (V2.10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import assessment_v2 as av2
from services.curriculum import load_assessments, load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Motor puro -------------------------------------------------------------


def test_assessment_kinds_are_five():
    assert av2.ASSESSMENT_KINDS == (
        "formative",
        "unit",
        "progress",
        "level",
        "retention",
    )


def test_build_formative_from_objective_checks():
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    instrument = av2.build_formative(obj)
    assert instrument["kind"] == "formative"
    assert instrument["objective_id"] == obj.id
    assert len(instrument["items"]) == len(obj.checks)
    assert "correct_index" not in instrument["items"][0]


def test_build_unit_and_progress_cap_items():
    lv = load_level("a1")
    units = av2.ordered_units(lv)
    assert units
    unit = av2.build_unit(lv, units[0].id)
    assert unit is not None
    assert unit["kind"] == "unit"
    assert len(unit["items"]) <= av2.ITEM_CAPS["unit"]

    anchor = units[min(len(units) - 1, av2.PROGRESS_UNIT_SPAN - 1)].id
    progress = av2.build_progress(lv, anchor)
    assert progress is not None
    assert progress["kind"] == "progress"
    assert len(progress["unit_ids"]) <= av2.PROGRESS_UNIT_SPAN
    assert len(progress["items"]) <= av2.ITEM_CAPS["progress"]


def test_evaluate_pass_and_fail():
    scored = {
        "overall": 0.8,
        "correct": 8,
        "total": 10,
        "skills": {"grammar": {"correct": 8, "total": 10, "score": 0.8}},
    }
    ok = av2.evaluate("unit", scored)
    assert ok["passed"] is True
    assert ok["threshold"] == av2.PASS_THRESHOLDS["unit"]

    scored["overall"] = 0.5
    scored["skills"]["grammar"]["score"] = 0.5
    bad = av2.evaluate("unit", scored)
    assert bad["passed"] is False


def test_retention_delta_and_stable():
    first = {
        "overall": 0.9,
        "skills": {"grammar": {"score": 0.9}, "vocabulary": {"score": 0.8}},
    }
    delayed = {
        "overall": 0.85,
        "skills": {"grammar": {"score": 0.8}, "vocabulary": {"score": 0.85}},
    }
    delta = av2.retention_delta(first, delayed)
    assert delta["retention_rate"] == pytest.approx(0.85 / 0.9, rel=1e-3)
    assert delta["stable"] is True
    assert len(delta["by_skill"]) == 2


def _exam_row(skill, created_at, result=1.0, *, context_id="exam:a1:1"):
    """Fila de evidencia de EXAMEN formal (baseline) tal como la escribe la
    escalera Assessment 2.0 (`kind=level`, task_type="exam") y submit_exam."""
    return {
        "skill": skill,
        "evidence_kind": "transfer",
        "task_type": "exam",
        "item_type": "mcq",
        "result": result,
        "source": "assessment_v2",
        "created_at": created_at,
        "context_id": context_id,
        "curriculum_version": "v1",
        "assessment_version": "assessment-v2",
    }


def _delayed_row(skill, created_at, result=0.9, *, context_id="retention:1"):
    """Fila de un retention reassessment (`evidence_kind="delayed"`). Por
    defecto es un evento propio con `context_id`; pasar `context_id` compartido
    agrupa varias filas en el mismo evento (sesión real, una fila por ítem)."""
    return {
        "skill": skill,
        "evidence_kind": "delayed",
        "task_type": "retention",
        "item_type": "mcq",
        "result": result,
        "source": "assessment_v2",
        "created_at": created_at,
        "context_id": context_id,
        "curriculum_version": "v1",
        "assessment_version": "assessment-v2",
    }


def test_certification_gate_requires_two_stable_reassessments_per_skill():
    """F-A3 (V3.26): completar (aprobar examen) no certifica. Por cada destreza
    del examen el gate exige ≥ CERTIFICATION_REQUIRED_DELAYED (2) retention
    reassessments ESTABLES: eventos `delayed` distintos, cada uno ≥
    RETENTION_MIN_DAYS después de su examen formal origen con ratio ≥
    RETENTION_STABLE_RATIO. Un perfil con un único delayed puntual deja de
    certificar."""
    skills = ["listening", "reading"]
    formal = "2026-08-01T00:00:00+00:00"
    p1 = "2026-08-08T00:00:00+00:00"  # reassessment 1: D+7 exacto
    p2 = "2026-08-22T00:00:00+00:00"  # reassessment 2: D+21 (separado)
    exam_rows = [
        _exam_row("listening", formal),
        _exam_row("reading", formal),
    ]
    gate = av2.certification_gate(skills, exam_rows)
    assert gate["certified"] is False
    assert gate["required"] is True
    assert gate["window_min_days"] == av2.RETENTION_MIN_DAYS
    assert gate["min_delayed"] == 2
    assert gate["pending_skills"] == ["listening", "reading"]

    # Un único reassessment estable por destreza ya NO certifica (F-A3).
    one_point = exam_rows + [
        _delayed_row("listening", p1, result=0.9, context_id="retention:1"),
        _delayed_row("reading", p1, result=0.95, context_id="retention:1"),
    ]
    gate = av2.certification_gate(skills, one_point)
    assert gate["certified"] is False
    assert gate["retention_report"]["listening"]["stable_points"] == 1
    assert gate["pending_skills"] == ["listening", "reading"]

    # Solo listening acumula su segundo punto; reading sigue pendiente.
    two_listening = one_point + [
        _delayed_row("listening", p2, result=0.9, context_id="retention:2"),
    ]
    gate = av2.certification_gate(skills, two_listening)
    assert gate["certified"] is False
    assert gate["pending_skills"] == ["reading"]

    # Ambos puntos estables en las dos destrezas → certifica.
    both = two_listening + [
        _delayed_row("reading", p2, result=0.95, context_id="retention:2"),
    ]
    gate = av2.certification_gate(skills, both)
    assert gate["certified"] is True
    assert gate["pending_skills"] == []
    assert gate["checks"] == {"listening": True, "reading": True}
    assert gate["retention_report"]["listening"]["stable_points"] == 2


def test_certification_gate_rejects_below_min_window():
    """P1-01 + F-A3: aunque existan DOS reassessments con ratio estable, si
    ninguno alcanza la ventana (eventos a D+3 y D+6) el gate NO certifica."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        _delayed_row(  # D+3: ventana no alcanzada, ratio 1.0
            "listening", "2026-08-04T00:00:00+00:00", 1.0,
            context_id="retention:1",
        ),
        _delayed_row(  # D+6: ventana no alcanzada, ratio 1.0
            "listening", "2026-08-07T00:00:00+00:00", 1.0,
            context_id="retention:2",
        ),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is False
    report = gate["retention_report"]["listening"]
    assert report["interval_days"] == [3, 6]
    # El informe es informativo: los ratios son estables (1.0), pero ninguna
    # ventana llega a RETENTION_MIN_DAYS → 0 puntos estables.
    assert report["stable_points"] == 0
    assert report["best_rate"] == 1.0
    assert gate["pending_skills"] == ["listening"]


def test_certification_gate_rejects_ratio_below_stable():
    """P1-01 + F-A3: con ventanas cumplidas pero ratios 0.89 (< 0.90) en AMBOS
    puntos, el gate NO certifica."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 0.89,  # D+7, 0.89
                     context_id="retention:1"),
        _delayed_row("listening", "2026-08-15T00:00:00+00:00", 0.89,  # D+14, 0.89
                     context_id="retention:2"),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is False
    report = gate["retention_report"]["listening"]
    assert report["best_rate"] == 0.89
    assert report["stable_points"] == 0
    assert gate["pending_skills"] == ["listening"]


def test_certification_gate_ratio_boundary_certifies():
    """P1-01 + F-A3: dos puntos con ventana cumplida y ratio 0.90 exacto
    (boundary por punto) SÍ certifican."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 0.90,  # D+7, 0.90
                     context_id="retention:1"),
        _delayed_row("listening", "2026-08-22T00:00:00+00:00", 0.90,  # D+21, 0.90
                     context_id="retention:2"),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is True
    assert gate["retention_report"]["listening"]["stable_points"] == 2
    assert gate["pending_skills"] == []


def test_certification_gate_rejects_long_window_low_ratio():
    """P1-01 + F-A3: intervalos largos (D+7/D+21) con ratio 0.50 no son
    retención estable: el gate NO certifica."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 0.50,  # D+7
                     context_id="retention:1"),
        _delayed_row("listening", "2026-08-22T00:00:00+00:00", 0.50,  # D+21
                     context_id="retention:2"),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is False
    report = gate["retention_report"]["listening"]
    assert report["interval_days"] == [7, 21]
    assert report["longest_interval_days"] == 21
    assert report["intervals_reached"] == [1, 3, 7, 21]
    assert report["best_rate"] == 0.5
    assert report["stable_points"] == 0
    assert gate["pending_skills"] == ["listening"]


def test_certification_gate_rejects_delayed_without_created_at():
    """F-L4 (robustez): filas `delayed` sin `created_at` parseable no pueden
    certificar: el gate no confía solo en la mera presencia de la etiqueta."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        {"skill": "listening", "evidence_kind": "delayed",
         "task_type": "retention", "result": 1.0, "created_at": "nunca",
         "context_id": "retention:1"},
        {"skill": "listening", "evidence_kind": "delayed",
         "task_type": "retention", "result": 1.0, "created_at": "nunca",
         "context_id": "retention:2"},
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is False
    assert gate["retention_report"]["listening"]["verified"] is False
    assert gate["retention_report"]["listening"]["stable_points"] == 0
    assert gate["pending_skills"] == ["listening"]


def test_certification_gate_two_events_none_with_valid_ratio():
    """P1-01: dos eventos `delayed` (D+3 y D+8) donde ninguno combina ventana y
    ratio válidos → no certifica."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        _delayed_row(  # D+3: ventana no alcanzada
            "listening", "2026-08-04T00:00:00+00:00", 1.0,
            context_id="retention:1",
        ),
        _delayed_row(  # D+8: ventana ok, ratio 0.40 inválido
            "listening", "2026-08-09T00:00:00+00:00", 0.4,
            context_id="retention:2",
        ),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is False
    report = gate["retention_report"]["listening"]
    assert report["interval_days"] == [3, 8]
    assert report["longest_interval_days"] == 8
    assert report["intervals_reached"] == [1, 3, 7]
    assert gate["pending_skills"] == ["listening"]


def test_certification_gate_requires_formal_baseline():
    """P1-01 + F-A3: sin filas de examen (`task_type="exam"`) no hay baseline y
    el gate no puede certificar, aunque existan DOS eventos `delayed` con
    ventana y ratio."""
    rows = [
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 1.0,
                     context_id="retention:1"),
        _delayed_row("listening", "2026-08-22T00:00:00+00:00", 1.0,
                     context_id="retention:2"),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is False
    report = gate["retention_report"]["listening"]
    assert report["baseline_date"] is None
    assert report["initial_score"] is None
    assert gate["pending_skills"] == ["listening"]


def test_certification_gate_groups_delayed_rows_by_context():
    """Una sesión de retention real emite una fila por ítem compartiendo
    `context_id`: el gate agrupa el evento y usa la media de resultado por
    destreza (2 ítems → 1.0 y 0.8 → delayed_score 0.90). F-A3: hacen falta DOS
    sesiones (contextos distintos) para certificar."""
    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        # Sesión 1: dos ítems de listening (media 0.90).
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 1.0,
                     context_id="retention:1"),
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 0.8,
                     context_id="retention:1"),
        # Sesión 2: punto separado (media 0.95).
        _delayed_row("listening", "2026-08-22T00:00:00+00:00", 1.0,
                     context_id="retention:2"),
        _delayed_row("listening", "2026-08-22T00:00:00+00:00", 0.9,
                     context_id="retention:2"),
    ]
    gate = av2.certification_gate(["listening"], rows)
    assert gate["certified"] is True
    report = gate["retention_report"]["listening"]
    assert report["count"] == 4
    assert report["events"] == 2
    assert report["stable_points"] == 2
    assert report["best_rate"] == 0.95


def test_certification_gate_empty_exam_never_certifies():
    assert av2.certification_gate([], [])["certified"] is False


def test_retention_report_adds_event_age_and_retention_interval():
    """F-A2 (auditoría V3.25, P2-02): `event_age_days` (edad del evento delayed
    respecto al momento de la consulta) y `retention_interval_days` (intervalo
    formal→delayed, el intervalo pedagógico relevante) son conceptos distintos y
    el reporte los expone a la vez de forma aditiva (`interval_days` se conserva
    como alias retrocompatible)."""
    formal = "2026-08-01T00:00:00+00:00"
    now = "2026-08-30T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        # Dos reassessment points (F-A3): D+7 y D+14 desde el formal.
        _delayed_row("listening", "2026-08-08T00:00:00+00:00", 0.9,
                     context_id="retention:1"),
        _delayed_row("listening", "2026-08-15T00:00:00+00:00", 0.95,
                     context_id="retention:2"),
    ]
    gate = av2.certification_gate(["listening"], rows, now=now)
    report = gate["retention_report"]["listening"]
    assert report["retention_interval_days"] == [7, 14]  # formal → delayed
    assert report["interval_days"] == [7, 14]  # alias conservado
    assert report["event_age_days"] == [15, 22]  # ahora - delayed
    assert report["longest_interval_days"] == 14
    assert report["longest_event_age_days"] == 22
    assert report["stable_points"] == 2
    assert gate["certified"] is True


def test_certification_gate_anchors_delayed_to_origin_session():
    """F-A2: cada evento `delayed` se ancla a la sesión formal que reevalúa
    (`delayed_origins`, resuelta desde `source_session_id`), no al examen más
    reciente del nivel. Un examen formal posterior (re-intento) no debe acortar
    el intervalo real de los eventos previos."""
    formal = "2026-08-01T00:00:00+00:00"
    reattempt = "2026-08-10T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal, context_id="exam:a1:1"),
        # Re-intento formal posterior: el ancla global "más reciente" sería
        # 2026-08-10 y rompería el intervalo real de los eventos previos.
        _exam_row("listening", reattempt, context_id="exam:a1:2"),
        _delayed_row(  # reassessment 1: D+7 desde su origen real
            "listening", "2026-08-08T00:00:00+00:00", 0.9,
            context_id="assessment_v2:retention:7",
        ),
        _delayed_row(  # reassessment 2: D+14 desde su origen real
            "listening", "2026-08-15T00:00:00+00:00", 0.9,
            context_id="assessment_v2:retention:8",
        ),
    ]
    origins = {
        "assessment_v2:retention:7": formal,
        "assessment_v2:retention:8": formal,
    }
    # Sin anclaje por origen no certifica: ancla global = 2026-08-10 → los
    # eventos quedan a 0 y 5 días (ninguno ≥ RETENTION_MIN_DAYS).
    old = av2.certification_gate(["listening"], rows)
    assert old["certified"] is False
    assert old["retention_report"]["listening"]["interval_days"] == [0, 5]
    assert old["retention_report"]["listening"]["anchored_events"] == 0
    # Con `delayed_origins` cada evento se ancla a su sesión origen (2026-08-01):
    # D+7 y D+14 reales → dos puntos estables → sí certifica.
    gate = av2.certification_gate(["listening"], rows, delayed_origins=origins)
    assert gate["certified"] is True
    report = gate["retention_report"]["listening"]
    assert report["interval_days"] == [7, 14]
    assert report["anchored_events"] == 2
    assert report["stable_points"] == 2


def test_delayed_origin_anchors_maps_retention_contexts_to_origin_created_at():
    """F-A2: `delayed_origin_anchors` resuelve el `created_at` de la sesión
    formal origen (`source_session_id`) para cada sesión de retención cerrada;
    las sesiones abiertas o sin origen formal no producen ancla."""
    sessions = [
        {"id": 1, "kind": "level", "status": "done",
         "source_session_id": None, "created_at": "2026-08-01T00:00:00+00:00"},
        {"id": 2, "kind": "retention", "status": "done",
         "source_session_id": 1, "created_at": "2026-08-08T00:00:00+00:00"},
        {"id": 3, "kind": "retention", "status": "open",
         "source_session_id": 1, "created_at": "2026-08-15T00:00:00+00:00"},
        {"id": 4, "kind": "retention", "status": "done",
         "source_session_id": None, "created_at": "2026-08-20T00:00:00+00:00"},
    ]
    anchors = av2.delayed_origin_anchors(sessions)
    assert anchors == {
        "assessment_v2:retention:2": "2026-08-01T00:00:00+00:00"
    }


def test_retention_spacing_due_requires_gap_since_last_reassessment_of_origin():
    """F-A3: un reassessment nuevo del mismo origen debe separarse ≥
    RETENTION_MIN_DAYS del ÚLTIMO reassessment cerrado de ese origen; sin
    reassessment previo del origen, o con orígenes distintos, no hay restricción."""
    now = "2026-08-30T00:00:00+00:00"
    recent = "2026-08-26T00:00:00+00:00"  # hace 4 días
    old = "2026-08-20T00:00:00+00:00"  # hace 10 días
    sessions = [
        {"id": 1, "kind": "level", "status": "done",
         "source_session_id": None, "created_at": "2026-08-01T00:00:00+00:00"},
        {"id": 2, "kind": "retention", "status": "done",
         "source_session_id": 1, "created_at": old},
        {"id": 3, "kind": "retention", "status": "done",
         "source_session_id": 1, "created_at": recent},
        {"id": 4, "kind": "retention", "status": "open",  # abierta: no cuenta
         "source_session_id": 1, "created_at": now},
        {"id": 5, "kind": "retention", "status": "done",
         "source_session_id": 99, "created_at": now},  # otro origen: no aplica
    ]
    # El último cerrado del origen 1 es `recent` (4 días) → espaciado NO cumplido.
    assert av2.retention_spacing_due(sessions, origin_session_id=1, now=now) is False
    # Sin ningún reassessment cerrado del origen → transparente (True).
    assert av2.retention_spacing_due(sessions, origin_session_id=1, now=old) is False
    assert av2.retention_spacing_due(
        sessions, origin_session_id=99, now=now
    ) is False
    assert av2.retention_spacing_due(
        sessions, origin_session_id=1000, now=now
    ) is True


def test_retention_spacing_due_transparent_without_prior_point():
    """F-A3: el primer reassessment de un origen no tiene punto previo que
    respetar: el espaciado es transparente (la ventana formal la cubre
    retention_due)."""
    sessions = [
        {"id": 1, "kind": "level", "status": "done",
         "source_session_id": None, "created_at": "2026-08-01T00:00:00+00:00"},
    ]
    assert av2.retention_spacing_due(
        sessions, origin_session_id=1, now="2026-08-08T00:00:00+00:00"
    ) is True



def test_ladder_level_certified_requires_retention_step():
    """H5/P1: el nivel se *certifica* solo con peldaño `level` + `retention`;
    completar la escalera sin retention deja `ladder_complete` True (avance
    desbloqueado) pero `level_certified` False."""
    base = dict(
        units_done=4,
        has_exam=True,
        retention_ready=True,
    )
    no_retention = av2.ladder_status(
        completed_kinds={"formative", "unit", "progress", "level"}, **base
    )
    assert no_retention["readiness"]["ladder_complete"] is True
    assert no_retention["readiness"]["level_certified"] is False

    certified = av2.ladder_status(
        completed_kinds={"formative", "unit", "progress", "level", "retention"},
        **base,
    )
    assert certified["readiness"]["ladder_complete"] is True
    assert certified["readiness"]["level_certified"] is True


def test_mastery_evidence_gate_requires_full_ladder():
    """F-K1 (V3.24): MASTERED exige kinds emitibles — familiar×2 + transfer×2 +
    delayed. `novel` (sin emisor real) queda reservado y nunca aparece en
    `missing`, aunque se conserve en `counts` como señal."""
    incomplete = av2.mastery_evidence_gate({"familiar": 2, "transfer": 1})
    assert incomplete["met"] is False
    assert "transfer" in incomplete["missing"]
    assert "delayed" in incomplete["missing"]
    assert "novel" not in incomplete["missing"]

    # Kinds emitibles al completo (sin novel inyectado a mano) → met.
    complete = av2.mastery_evidence_gate(
        {"familiar": 2, "transfer": 2, "delayed": 1}
    )
    assert complete["met"] is True
    assert complete["missing"] == []
    assert complete["counts"]["novel"] == 0


def test_retention_due_window():
    now = datetime(2026, 9, 2, tzinfo=timezone.utc)
    recent = (now - timedelta(days=3)).isoformat()
    old = (now - timedelta(days=10)).isoformat()
    assert av2.retention_due(recent, now=now.isoformat()) is False
    assert av2.retention_due(old, now=now.isoformat()) is True


# --- F-A1 (V3.26): initial vs practice con re-encuentro espaciado -----------


def _familiar_row(created_at, *, context_id, skill="grammar", result=1.0):
    """Fila de evidencia `familiar` (formative/objetivo) con contexto."""
    return {
        "skill": skill,
        "evidence_kind": "familiar",
        "task_type": "formative",
        "item_type": "mcq",
        "result": result,
        "source": "objective_assessment",
        "created_at": created_at,
        "context_id": context_id,
        "curriculum_version": "v1",
        "assessment_version": "assessment-v2",
    }


def _day(d, skill="grammar", *, context_id="objective:o1", result=1.0):
    """created_at en el día d (2026-09-01 + d días, 12:00 UTC)."""
    base = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    return (base + timedelta(days=d)).isoformat()


def test_familiar_spaced_counts_separates_initial_and_practice():
    """F-A1: `initial` cuenta el primer encuentro de cada contexto; `practice`
    cuenta los re-encuentros del MISMO contexto separados >=1 día. Dos contextos
    distintos en un mismo día NO son practice (el agujero que audita P2-01)."""
    rows = [
        _familiar_row(_day(0), context_id="objective:a"),
        # El MISMO contexto objetivo:a vuelve D+1 y D+3 → 2 re-encuentros.
        _familiar_row(_day(1), context_id="objective:a"),
        _familiar_row(_day(3), context_id="objective:a"),
        # El contexto b se encuentra una sola vez (initial, sin practice).
        _familiar_row(_day(0), context_id="objective:b"),
    ]
    counts = av2.familiar_spaced_counts(rows)
    assert counts["initial_xp"] == 2  # a y b (primer encuentro de cada uno)
    assert counts["practice_xp"] == 2  # a en D+1 y D+3


def test_familiar_spaced_counts_ignores_rows_without_date_or_context():
    """F-A1: filas legacy (sin context_id) o con created_at corrupto no aportan
    re-encuentro (no se puede demostrar espaciado); el llamador usa el fallback
    legacy cuando no hay ningún contexto."""
    rows = [
        _familiar_row("", context_id="objective:a"),
        _familiar_row(_day(0), context_id=""),
    ]
    counts = av2.familiar_spaced_counts(rows)
    assert counts["initial_xp"] == 0
    assert counts["practice_xp"] == 0
    # Sin filas útiles → sin contexto, señala legacy para el fallback.
    assert av2.familiar_spaced_counts([]) == {"initial_xp": 0, "practice_xp": 0}


def test_mastery_gate_practice_requires_spaced_reencounter_of_same_context():
    """F-A1: con `familiar_spaced` presente, el gate exige que `practice` sea un
    re-encuentro espaciado del MISMO contexto. Dos contextos distintos el mismo
    día (2 primeras experiencias) NO satisfacen practice: es el agujero de
    P2-01 (familiar satisfaciendo initial y practice a la vez sin espaciado)."""
    counts = {"familiar": 3, "transfer": 2, "delayed": 1}
    # Dos contextos distintos en el mismo día → initial 2, practice 0.
    same_day = {"familiar": 3, "transfer": 2, "delayed": 1}
    gate = av2.mastery_evidence_gate(
        same_day,
        context_counts={"familiar": 2, "transfer": 2, "delayed": 1},
        familiar_spaced={"initial_xp": 2, "practice_xp": 0},
    )
    assert gate["met"] is False
    assert "practice" in gate["missing"]
    assert "initial" not in gate["missing"]
    assert gate["counts"]["familiar_initial_xp"] == 2
    assert gate["counts"]["familiar_practice_xp"] == 0

    # El mismo contexto objetivo:a vuelve D+1 y D+3 → practice 2 → met.
    gate2 = av2.mastery_evidence_gate(
        counts,
        context_counts={"familiar": 1, "transfer": 2, "delayed": 1},
        familiar_spaced={"initial_xp": 1, "practice_xp": 2},
    )
    assert gate2["met"] is True
    assert gate2["missing"] == []


def test_mastery_gate_legacy_fallback_keeps_old_row_semantics():
    """F-A1: sin `familiar_spaced` (modo legacy / llamadas puras por conteos) el
    gate conserva el comportamiento previo (filas/contextos), que F-C4 marcará
    como 'experiencias no verificadas' en el perfil. No rompe callers antiguos."""
    gate = av2.mastery_evidence_gate(
        {"familiar": 2, "transfer": 2, "delayed": 1},
        context_counts={"familiar": 2, "transfer": 2, "delayed": 1},
    )
    assert gate["met"] is True


def test_ladder_status_next_kind():
    status = av2.ladder_status(
        completed_kinds={"formative"},
        units_done=1,
        has_exam=True,
        retention_ready=False,
    )
    assert status["readiness"]["next_kind"] == "unit"
    kinds = {s["kind"]: s for s in status["steps"]}
    assert kinds["progress"]["available"] is False
    assert kinds["retention"]["available"] is False


def test_evidence_kind_for_mapping():
    assert av2.evidence_kind_for("formative") == "familiar"
    assert av2.evidence_kind_for("unit") == "transfer"
    assert av2.evidence_kind_for("retention") == "delayed"


# --- Flujo HTTP -------------------------------------------------------------


def test_assessment_v2_formative_http_loop(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    # Matricular para no bloquear por enrollment.
    academy_repo.enroll(uid, "a1", "A1")

    client = TestClient(app)
    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "formative",
            "level_id": "a1",
            "objective_id": obj.id,
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["kind"] == "formative"
    assert body["status"] == "open"
    assert len(body["instrument"]["items"]) >= 1

    answers = {c.id: c.correct_index for c in obj.checks}
    done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": body["session_id"], "answers": answers},
    )
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["status"] == "done"
    assert result["result"]["passed"] is True
    assert result["result"]["overall"] == 1.0

    ladder = client.get(f"/api/academy/assessment/v2/ladder?user_id={uid}&level_id=a1")
    assert ladder.status_code == 200
    data = ladder.json()
    assert data["assessment_version"] == av2.ASSESSMENT_VERSION
    steps = {s["kind"]: s for s in data["steps"]}
    assert steps["formative"]["completed"] is True


def test_assessment_v2_unit_and_level(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    lv = load_level("a1")
    unit = av2.ordered_units(lv)[0]
    client = TestClient(app)

    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "unit", "level_id": "a1", "unit_id": unit.id},
    )
    assert start.status_code == 200, start.text
    session = start.json()
    index = {c.id: c for o in lv.objectives() for c in o.checks}
    answers = {
        it["id"]: index[it["id"]].correct_index
        for it in session["instrument"]["items"]
        if it["id"] in index
    }
    done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": session["session_id"], "answers": answers},
    )
    assert done.status_code == 200
    assert done.json()["result"]["passed"] is True

    exam = load_assessments().exams["a1"]
    level_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "level", "level_id": "a1"},
    )
    assert level_start.status_code == 200
    level_session = level_start.json()
    level_answers = {it.id: it.correct_index for it in exam.items}
    level_done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={
            "session_id": level_session["session_id"],
            "answers": level_answers,
        },
    )
    assert level_done.status_code == 200
    assert level_done.json()["result"]["passed"] is True


def _backdate_session(session_id: int, days: int) -> None:
    """Retrasa created_at/updated_at de una sesión Assessment 2.0 a `days`.

    Simula que la sesión formal origen ocurrió hace `days` (R6-01: la ventana
    de retención se mide desde ese `created_at`)."""
    iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = db._conn()
    try:
        with conn:
            conn.execute(
                "UPDATE assessment_v2_sessions "
                "SET created_at = ?, updated_at = ? WHERE id = ?",
                (iso, iso, session_id),
            )
    finally:
        conn.close()


def _submit_unit_and_answers(uid: str, client, lv) -> tuple[dict, dict]:
    """Completa un unit assessment correcto; devuelve (sesión, índice answers)."""
    unit = av2.ordered_units(lv)[0]
    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "unit", "level_id": lv.level_id, "unit_id": unit.id},
    )
    session = start.json()
    index = {c.id: c for o in lv.objectives() for c in o.checks}
    answers = {
        it["id"]: index[it["id"]].correct_index
        for it in session["instrument"]["items"]
        if it["id"] in index
    }
    done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": session["session_id"], "answers": answers},
    )
    assert done.status_code == 200, done.text
    assert done.json()["result"]["passed"] is True
    return session, answers


def test_assessment_v2_retention_rejects_before_window(monkeypatch, tmp_path):
    """R6-01: abrir un retention reassessment el mismo día (ventana no cumplida)
    responde 409 en vez de 200 (antes: fail-open)."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    lv = load_level("a1")
    client = TestClient(app)

    session, _ = _submit_unit_and_answers(uid, client, lv)

    ret_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "retention",
            "level_id": "a1",
            "source_session_id": session["session_id"],
        },
    )
    assert ret_start.status_code == 409, ret_start.text
    assert ret_start.json()["code"] == "RETENTION_NOT_DUE"


def test_assessment_v2_retention_delta_http(monkeypatch, tmp_path):
    """R6-01: con la ventana ≥ RETENTION_MIN_DAYS cumplida, el retention
    reassessment se abre y cierra con evidencia `delayed` y ratio estable."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    lv = load_level("a1")
    index = {c.id: c for o in lv.objectives() for c in o.checks}
    client = TestClient(app)

    session, answers = _submit_unit_and_answers(uid, client, lv)
    _backdate_session(session["session_id"], av2.RETENTION_MIN_DAYS + 1)

    ret_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "retention",
            "level_id": "a1",
            "source_session_id": session["session_id"],
        },
    )
    assert ret_start.status_code == 200, ret_start.text
    ret_session = ret_start.json()
    # Fallo parcial: primer ítem incorrecto.
    ret_answers = dict(answers)
    first_id = ret_session["instrument"]["items"][0]["id"]
    correct = index[first_id].correct_index
    ret_answers[first_id] = (correct + 1) % len(index[first_id].options)

    ret_done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": ret_session["session_id"], "answers": ret_answers},
    )
    assert ret_done.status_code == 200, ret_done.text
    body = ret_done.json()
    assert body["retention"] is not None
    assert body["retention"]["delayed_overall"] < body["retention"]["initial_overall"]
    assert body["retention"]["stable"] is True
    assert body["result"]["kind"] == "retention"


def test_assessment_v2_retention_rejects_unstable_ratio(monkeypatch, tmp_path):
    """R6-01: con ventana cumplida pero ratio delayed/initial < 0.9, el submit
    rechaza la evidencia `delayed` con 409 (antes: fail-open)."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    lv = load_level("a1")
    index = {c.id: c for o in lv.objectives() for c in o.checks}
    client = TestClient(app)

    session, answers = _submit_unit_and_answers(uid, client, lv)
    _backdate_session(session["session_id"], av2.RETENTION_MIN_DAYS + 1)

    ret_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "retention",
            "level_id": "a1",
            "source_session_id": session["session_id"],
        },
    )
    assert ret_start.status_code == 200, ret_start.text
    ret_session = ret_start.json()
    # Fallo masivo: todas las respuestas incorrectas → ratio muy por debajo.
    wrong = {
        it["id"]: (index[it["id"]].correct_index + 1) % len(index[it["id"]].options)
        for it in ret_session["instrument"]["items"]
        if it["id"] in index
    }
    ret_done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": ret_session["session_id"], "answers": wrong},
    )
    assert ret_done.status_code == 409, ret_done.text
    assert ret_done.json()["code"] == "RETENTION_NOT_DUE"


# --- F-A3: retención sobre el examen de nivel + espaciado multi-punto --------


def _submit_level_exam(uid, client, *, level_id="a1") -> tuple[dict, dict]:
    """Pasa el examen de nivel (escalera Assessment 2.0, kind=level) con todas
    las respuestas correctas; devuelve (sesión, respuestas correctas)."""
    exam = load_assessments().exams[level_id]
    start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={"kind": "level", "level_id": level_id},
    )
    assert start.status_code == 200, start.text
    session = start.json()
    answers = {it.id: it.correct_index for it in exam.items}
    done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": session["session_id"], "answers": answers},
    )
    assert done.status_code == 200, done.text
    assert done.json()["result"]["passed"] is True
    return session, answers


def test_assessment_v2_retention_over_level_exam_writes_delayed(
    monkeypatch, tmp_path
):
    """F-A3 (fix escritor): la retención sobre el EXAMEN de nivel (kind=level)
    antes no se podía puntuar — los ítems del examen no viven en el índice de
    checks del currículo y `submit` devolvía None sin escribir evidencia
    `delayed`. Ahora `correct_index` se resuelve desde el examen (origen
    `kind=level`) y la evidencia delayed se escribe de verdad."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    client = TestClient(app)

    exam_session, answers = _submit_level_exam(uid, client)
    _backdate_session(exam_session["session_id"], av2.RETENTION_MIN_DAYS + 1)

    ret_start = client.post(
        f"/api/academy/assessment/v2/start?user_id={uid}",
        json={
            "kind": "retention",
            "level_id": "a1",
            "source_session_id": exam_session["session_id"],
        },
    )
    assert ret_start.status_code == 200, ret_start.text
    ret_session = ret_start.json()
    assert ret_session["instrument"]["source_kind"] == "level"
    # Las respuestas del retention se puntúan contra la clave del examen.
    ret_done = client.post(
        f"/api/academy/assessment/v2/submit?user_id={uid}",
        json={"session_id": ret_session["session_id"], "answers": answers},
    )
    assert ret_done.status_code == 200, ret_done.text
    body = ret_done.json()
    assert body["retention"] is not None
    assert body["retention"]["stable"] is True
    assert body["result"]["kind"] == "retention"

    delayed = [
        r
        for r in academy_repo.list_evidence(uid, "a1")
        if (r.get("evidence_kind") or "") == "delayed"
    ]
    assert delayed, "la retención sobre kind=level debe escribir evidencia delayed"
    assert {r["skill"] for r in delayed}


def test_assessment_v2_second_retention_of_same_origin_needs_spacing(
    monkeypatch, tmp_path
):
    """F-A3 (espaciado): para que >1 punto sea REAL y separado, un reassessment
    nuevo del mismo origen exige ≥ RETENTION_MIN_DAYS desde el último cerrado
    de ese origen (409 si no). Tras espaciar el primer punto, el segundo abre y
    cierra con normalidad."""
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    client = TestClient(app)

    exam_session, answers = _submit_level_exam(uid, client)
    _backdate_session(exam_session["session_id"], av2.RETENTION_MIN_DAYS + 1)

    def _open_retention(source_sid):
        return client.post(
            f"/api/academy/assessment/v2/start?user_id={uid}",
            json={
                "kind": "retention",
                "level_id": "a1",
                "source_session_id": source_sid,
            },
        )

    def _submit_retention(session_id, correct_answers):
        return client.post(
            f"/api/academy/assessment/v2/submit?user_id={uid}",
            json={"session_id": session_id, "answers": correct_answers},
        )

    # Punto 1: abre y cierra estable.
    r1_start = _open_retention(exam_session["session_id"])
    assert r1_start.status_code == 200, r1_start.text
    r1 = r1_start.json()
    r1_done = _submit_retention(r1["session_id"], answers)
    assert r1_done.status_code == 200, r1_done.text
    assert r1_done.json()["retention"]["stable"] is True

    # Punto 2 inmediato (mismo origen, 0 días) → 409.
    r2_start = _open_retention(exam_session["session_id"])
    assert r2_start.status_code == 409, r2_start.text
    assert r2_start.json()["code"] == "RETENTION_NOT_DUE"

    # Espaciar: el primer reassessment ocurrió hace ≥ RETENTION_MIN_DAYS.
    _backdate_session(r1["session_id"], av2.RETENTION_MIN_DAYS + 1)
    r2_start = _open_retention(exam_session["session_id"])
    assert r2_start.status_code == 200, r2_start.text
    r2 = r2_start.json()
    r2_done = _submit_retention(r2["session_id"], answers)
    assert r2_done.status_code == 200, r2_done.text
    assert r2_done.json()["retention"]["stable"] is True
