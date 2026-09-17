"""Candados del arnés de validación (V3.73).

El arnés existe para que los gates de validación física **no se puedan cerrar en
falso**. Estos tests fijan lo que lo hace cumplir:

- el conjunto de gates es **cerrado** (una errata de id no abre un gate fantasma),
- registrar un gate exige notas (una evidencia vacía no vale),
- `status --strict` **falla** mientras haya gates sin `pass`,
- `auto` no escribe nada fuera de `docs/`,
- el informe es determinista y `auto` cubre todas las comprobaciones.

Se carga el script por ruta a propósito: vive en `scripts/` (no es un paquete) y
es stdlib pura, así que importarlo no arrastra dependencias del backend.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validation_gate.py"

EXPECTED_GATES = {
    "offline-fisico",
    "maquina-limpia",
    "launcher-windows",
    "dispositivos",
    "audio-stt-tts",
    "journeys",
    "pedagogia",
}


@pytest.fixture(scope="module")
def harness():
    import sys

    spec = importlib.util.spec_from_file_location("validation_gate_v373", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # `dataclasses` resuelve el módulo por `sys.modules`: sin registrarlo falla.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def evidence_path(harness, tmp_path, monkeypatch):
    """Aísla la evidencia en un fichero temporal (no toca el del repo)."""
    path = tmp_path / "validation-evidence.json"
    monkeypatch.setattr(harness, "EVIDENCE", path)
    return path


# --- El conjunto de gates es cerrado ----------------------------------------


def test_los_siete_gates_estan_definidos(harness):
    assert {gate.id for gate in harness.GATES} == EXPECTED_GATES


def test_los_gates_son_de_accion_humana(harness):
    """Ninguno es automatizable: si lo fuera, no sería un gate de validación."""
    assert all(gate.human for gate in harness.GATES)


def test_cada_gate_declara_protocolo_y_evidencia(harness):
    for gate in harness.GATES:
        assert gate.protocol.strip(), f"{gate.id} sin protocolo"
        assert gate.evidence.strip(), f"{gate.id} sin qué registrar"


def test_el_runbook_declara_todos_los_gates(harness):
    """La definición y la documentación no pueden separarse."""
    text = harness.RUNBOOK.read_text(encoding="utf-8")

    for gate in harness.GATES:
        assert gate.id in text, f"el runbook no declara el gate {gate.id}"
    assert harness.RUNBOOK.name in (
        "VALIDATION-RELEASE-V373.md",
    ), "el runbook de la release de validación cambió de nombre sin actualizar esto"


# --- Registrar un gate exige evidencia --------------------------------------


def test_un_gate_desconocido_se_rechaza(harness, evidence_path, capsys):
    assert harness.record("gate-que-no-existe", "pass", "notas") == 1
    assert "desconocido" in capsys.readouterr().out
    assert not evidence_path.exists(), "se escribió evidencia de un gate inválido"


def test_un_estado_desconocido_se_rechaza(harness, evidence_path):
    assert harness.record("journeys", "quizá", "notas") == 1
    assert not evidence_path.exists()


@pytest.mark.parametrize("status", ["pass", "fail", "skip"])
def test_registrar_exige_notas(harness, evidence_path, status):
    """`pass` sin notas es exactamente lo que el instrumento existe para impedir."""
    assert harness.record("journeys", status, "   ") == 1
    assert not evidence_path.exists()


def test_registrar_guarda_estado_notas_fecha_y_version(harness, evidence_path):
    assert harness.record("offline-fisico", "pass", "12/12 flujos OK") == 0

    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    entry = data["gates"]["offline-fisico"]
    assert entry["status"] == "pass"
    assert entry["notes"] == "12/12 flujos OK"
    assert entry["recorded_at"]
    assert entry["tree_version"] == harness.source_version()


def test_la_evidencia_se_guarda_en_orden_de_gate(harness, evidence_path):
    harness.record("pedagogia", "pending", "sin empezar")
    harness.record("offline-fisico", "pending", "sin empezar")

    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert list(data["gates"]) == ["offline-fisico", "pedagogia"]


# --- `status --strict` es la puerta de V4.0 ---------------------------------


def test_strict_falla_mientras_haya_gates_sin_pass(harness, evidence_path, capsys):
    harness.record("offline-fisico", "pass", "hecho")

    assert harness.status_report(strict=True) == 1
    assert "PENDIENTE" in capsys.readouterr().out


def test_strict_aprueba_con_los_siete_gates_en_pass(
    harness, evidence_path, capsys
):
    for gate in harness.GATES:
        harness.record(gate.id, "pass", "verificado en hardware real")

    assert harness.status_report(strict=True) == 0
    assert "V4.0 puede declararse" in capsys.readouterr().out


def test_strict_no_aprueba_con_un_gate_en_fail(harness, evidence_path):
    for gate in harness.GATES:
        harness.record(gate.id, "pass", "ok")
    harness.record("dispositivos", "fail", "iPhone Safari no dio micrófono")

    assert harness.status_report(strict=True) == 1


def test_sin_strict_el_estado_pendiente_no_hace_fallar(harness, evidence_path):
    """`status` informa; solo `--strict` es la puerta."""
    assert harness.status_report(strict=False) == 0


# --- La evidencia escrita a mano no cuela -----------------------------------


def test_un_gate_inventado_en_la_evidencia_se_detecta(
    harness, evidence_path, monkeypatch
):
    evidence_path.write_text(
        json.dumps({"gates": {"gate-inventado": {"status": "pass", "notes": "x"}}}),
        encoding="utf-8",
    )

    check = harness.check_evidence_not_invented()

    assert check.ok is False
    assert "desconocido" in check.detail


def test_una_evidencia_sin_notas_se_detecta(harness, evidence_path):
    evidence_path.write_text(
        json.dumps({"gates": {"journeys": {"status": "pass", "notes": "  "}}}),
        encoding="utf-8",
    )

    check = harness.check_evidence_not_invented()

    assert check.ok is False
    assert "sin notas" in check.detail


def test_un_estado_inventado_se_detecta(harness, evidence_path):
    evidence_path.write_text(
        json.dumps({"gates": {"journeys": {"status": "casi", "notes": "x"}}}),
        encoding="utf-8",
    )

    assert harness.check_evidence_not_invented().ok is False


# --- `auto`: cobertura, determinismo y alcance ------------------------------


def test_auto_cubre_todas_las_comprobaciones(harness):
    checks = harness.run_checks(require_dist=False)

    assert len(checks) >= 10
    ids = [check.id for check in checks]
    assert len(ids) == len(set(ids)), f"ids de comprobación duplicados: {ids}"


def test_el_informe_es_determinista(harness):
    checks = harness.run_checks(require_dist=False)

    first = harness.report_markdown(checks, "3.73.0")
    second = harness.report_markdown(checks, "3.73.0")

    assert first == second
    # El informe se commitea: no puede filtrar la ruta absoluta del equipo que lo
    # generó (sería determinista solo en esa máquina). Cubre `_run_script`.
    assert str(ROOT) not in first
    assert str(ROOT) not in json.dumps(harness.report_json(checks, "3.73.0"))
    assert harness.report_json(checks, "3.73.0") == harness.report_json(
        checks, "3.73.0"
    )


def test_el_artefacto_de_ui_es_skip_sin_require_dist(harness, monkeypatch, tmp_path):
    monkeypatch.setattr(harness, "ROOT", tmp_path)

    check = harness.check_dist_artifact(require_dist=False)

    assert check.ok is None


def test_el_artefacto_de_ui_falla_si_se_exige_y_no_esta(harness, monkeypatch, tmp_path):
    monkeypatch.setattr(harness, "ROOT", tmp_path)

    check = harness.check_dist_artifact(require_dist=True)

    assert check.ok is False
    assert "npm run build" in check.detail


def test_auto_solo_escribe_dentro_de_docs(harness):
    """El arnés no puede tocar código, currículum ni datos al medir."""
    for path in (harness.REPORT_MD, harness.REPORT_JSON, harness.EVIDENCE):
        assert harness.DOCS in path.parents, f"{path} queda fuera de docs/"


def test_las_comprobaciones_de_auto_no_fallan_en_este_arbol(harness):
    """El propio repo tiene que pasar las comprobaciones estáticas que declara."""
    failing = [
        check.title for check in harness.run_checks(require_dist=False)
        if check.ok is False
    ]

    assert failing == [], f"comprobaciones automáticas en rojo: {failing}"
