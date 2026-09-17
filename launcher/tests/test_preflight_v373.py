"""Candados del preflight fail-closed del launcher (V3.73).

V3.72 dejó el runtime de producto **fail-open** en el backend: sin
`frontend/dist` la app arrancaba, no servía UI y **parecía lista**. V3.73 declara
el runtime de producto como fail-closed en **los dos lados**:

- el launcher inyecta `ENGLISH_TUTOR_REQUIRE_UI=1` en el entorno de uvicorn, y
- el launcher **no arranca** el backend si falta el artefacto.

Estos tests fijan las dos mitades y el contrato compartido entre `core.py` y
`backend/services/frontend_dist.py` (la variable se llama igual en ambos).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import REQUIRE_UI_ENV, backend_env
from process_manager import PreparationError, ProcessManager

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def test_el_entorno_de_producto_exige_la_ui_compilada():
    env = backend_env()

    assert env[REQUIRE_UI_ENV] == "1"


def test_el_entorno_de_producto_conserva_lo_que_ya_habia():
    env = backend_env({"PATH": "/usr/bin", "OTRA": "valor"})

    assert env["PATH"] == "/usr/bin"
    assert env["OTRA"] == "valor"
    assert env[REQUIRE_UI_ENV] == "1"


def test_el_entorno_de_producto_no_muta_el_diccionario_de_entrada():
    base = {"PATH": "/usr/bin"}

    backend_env(base)

    assert base == {"PATH": "/usr/bin"}


def test_no_se_arranca_el_producto_sin_la_ui_compilada(monkeypatch):
    """Fail-closed: sin artefacto no hay proceso, y el mensaje dice qué hacer."""
    monkeypatch.setattr("process_manager.frontend_dist_available", lambda: False)

    def boom(*args, **kwargs):  # pragma: no cover — no debe llegar a Popen
        raise AssertionError("no debe arrancar el backend sin la UI compilada")

    monkeypatch.setattr("process_manager.subprocess.Popen", boom)

    with pytest.raises(PreparationError, match="npm run build"):
        ProcessManager().start_backend()


def test_el_backend_recibe_la_exigencia_de_ui_en_su_entorno(monkeypatch, tmp_path):
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("process_manager.frontend_dist_available", lambda: True)
    capturado: dict = {}

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            capturado.update(kwargs)

        def poll(self):
            return None

    monkeypatch.setattr("process_manager.subprocess.Popen", _FakePopen)

    ProcessManager().start_backend()

    assert capturado["env"][REQUIRE_UI_ENV] == "1"


def test_la_variable_se_llama_igual_en_el_launcher_y_en_el_backend():
    """Contrato compartido: si una mitad cambia el nombre, esto falla.

    El launcher no puede importar el backend (son proyectos separados), así que
    el contrato se fija leyendo el módulo del backend como texto.
    """
    module = (BACKEND / "services" / "frontend_dist.py").read_text(encoding="utf-8")

    assert f'REQUIRE_UI_ENV = "{REQUIRE_UI_ENV}"' in module, (
        "la variable de entorno del fail-closed de producto dejó de coincidir "
        "entre launcher/core.py y backend/services/frontend_dist.py"
    )
    assert "ENGLISH_TUTOR_REQUIRE_UI" in module


def test_el_backend_declara_el_modo_de_producto_en_el_montaje():
    """`main.py` pasa el modo explícitamente: el fail-closed no puede ser latente."""
    main = (BACKEND / "main.py").read_text(encoding="utf-8")

    assert "require_ui_from_env()" in main, (
        "main.py dejó de declarar el modo de montaje de la UI"
    )
    assert "require_ui=" in main
