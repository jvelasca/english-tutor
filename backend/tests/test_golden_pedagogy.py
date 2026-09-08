"""Tests golden de la calibración de evidencia pedagógica (V3.13, P0.1/P0.3).

Consumen `tests/golden/pedagogy/evidence_depth_cases.json` (audit C-2026-09-05):
bandas de profundidad de la evidencia por destreza/nivel (Constitución §6.4) y
suelos de "demostrado" (§7, reglas R5/R7). Un cambio de motor o de matriz que
altere un veredicto es una regresión de calibración: se re-audita (dossier en
`docs/audit/`) antes de tocar el fixture (regla del README de goldens).
"""
from __future__ import annotations

from golden import loader

from services.competence import competence_state
from services.evidence_depth import evidence_depth_report


def _evidence_case_expects() -> list[dict]:
    fixture = loader.load_json("pedagogy", "evidence_depth_cases")
    return fixture["evidence_depth_cases"]


def _floor_case_expects() -> list[dict]:
    fixture = loader.load_json("pedagogy", "evidence_depth_cases")
    return fixture["demonstrated_floor_cases"]


def test_fixture_has_audit_id():
    fixture = loader.load_json("pedagogy", "evidence_depth_cases")
    assert fixture["area"] == "pedagogy"
    # Audit C-2026-09-05; re-auditado en C-2026-09-08 (recalibración F-C2 V3.26).
    assert fixture["audit"].startswith("C-2026-09-08")
    # 6 casos A1–C2 de profundidad + 3 suelos de demostrado (dossier fijado).
    assert len(fixture["evidence_depth_cases"]) == 6
    assert len(fixture["demonstrated_floor_cases"]) == 3


def test_evidence_depth_golden_cases():
    for case in _evidence_case_expects():
        got = evidence_depth_report(
            case["skill"],
            case["level"],
            case["samples"],
            case["evidence_by_kind"],
            production_count=case["production_count"],
        )
        expect = case["expect"]
        # Verificación selectiva: profundidad, cumplimiento de matriz y campos
        # que fijan la calibración auditada (mínimo, retención, producción).
        assert got["depth"] == expect["depth"], case["id"]
        assert got["meets_matrix"] is expect["meets_matrix"], case["id"]
        assert got["minimum_evidence"] == expect["minimum_evidence"], case["id"]
        assert got["delayed"] == expect["delayed"], case["id"]
        assert got["production_count"] == expect["production_count"], case["id"]


def test_demonstrated_floors_golden_cases():
    for case in _floor_case_expects():
        got = competence_state(
            dict(case["entry"]),
            case["skill"],
            case["level"],
        )
        expect = case["expect"]
        assert got["state"] == expect["state"], case["id"]
        assert got["demonstrated"] is expect["demonstrated"], case["id"]
        assert got["evidence_depth"] == expect["evidence_depth"], case["id"]
        for flag, value in expect["gate"].items():
            assert got["gate"][flag] is value, f"{case['id']}: {flag}"
