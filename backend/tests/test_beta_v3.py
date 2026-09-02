"""Tests del gate Beta V3.0."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_beta_v3.py"


def test_beta_v3_gate_passes():
    # Ejecuta el script como __main__ y comprueba exit code 0.
    # runpy no propaga sys.exit; capturamos SystemExit.
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
        code = 0
    except SystemExit as exc:
        code = int(exc.code or 0)
    assert code == 0


def test_beta_v3_required_docs_exist():
    sys.path.insert(0, str(ROOT / "scripts"))
    # Importar funciones del script sin ejecutarlo.
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_beta_v3", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    failures: list[str] = []
    mod.check_docs(failures)
    assert failures == []
