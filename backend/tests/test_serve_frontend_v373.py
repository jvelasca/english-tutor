"""Fail-closed del runtime de producto (V3.73, cierre del P2 de la auditoría).

V3.72 cerró RC-01 con un montaje **fail-open**: sin `frontend/dist` el backend
arrancaba y no servía UI. Para desarrollo es correcto (un clon limpio conserva
API), pero para **producto** es peligroso: la app parece lista y se ve vacía.

V3.73 añade el modo de producto, activado por el launcher con
`ENGLISH_TUTOR_REQUIRE_UI=1`, en el que la falta del artefacto es un error
explícito. Estos tests fijan las dos caras del contrato.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from services.frontend_dist import (
    REQUIRE_UI_ENV,
    build_missing_message,
    mount_frontend,
    require_ui_from_env,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("si", True),
        (" 1 ", True),
        ("", False),
        ("0", False),
        ("no", False),
        ("off", False),
    ],
)
def test_la_lectura_del_flag_de_producto_es_explicita(value, expected):
    """El flag solo se activa con valores afirmativos; nada implícito."""
    assert require_ui_from_env({REQUIRE_UI_ENV: value}) is expected


def test_sin_la_variable_el_modo_es_desarrollo():
    """`uvicorn main:app` manual (sin la variable) sigue siendo fail-open."""
    assert require_ui_from_env({}) is False


def test_en_desarrollo_la_falta_de_artefacto_sigue_siendo_fail_open(tmp_path):
    app = FastAPI()

    assert mount_frontend(app, tmp_path / "no-existe", require_ui=False) is False


def test_en_producto_la_falta_de_artefacto_es_un_error_explicito(tmp_path):
    """Fail-closed: el producto no puede arrancar pareciendo listo y sin UI."""
    app = FastAPI()

    with pytest.raises(RuntimeError) as excinfo:
        mount_frontend(app, tmp_path / "no-existe", require_ui=True)

    message = str(excinfo.value)
    assert "npm run build" in message, (
        "el mensaje no dice cómo arreglarlo: no es accionable"
    )


def test_la_variable_de_entorno_activa_el_modo_producto(tmp_path, monkeypatch):
    """El modo lo decide el entorno cuando el llamante no lo fuerza."""
    monkeypatch.setenv(REQUIRE_UI_ENV, "1")
    app = FastAPI()

    with pytest.raises(RuntimeError):
        mount_frontend(app, tmp_path / "no-existe")


def test_el_mensaje_nombra_la_ruta_del_artefacto_que_falta(tmp_path):
    message = build_missing_message(tmp_path)

    assert str(tmp_path / "index.html") in message
    assert "frontend/" in message or "frontend`" in message


def test_en_producto_con_artefacto_se_monta_normalmente(tmp_path):
    """El modo producto no cambia el camino feliz: solo el fallo."""
    (tmp_path / "index.html").write_text("<html>UI</html>", encoding="utf-8")
    app = FastAPI()

    assert mount_frontend(app, tmp_path, require_ui=True) is True


def test_el_launcher_y_el_backend_comparten_la_variable_de_entorno():
    """Contrato compartido entre las dos mitades del fail-closed.

    El launcher no puede importar este módulo (proyectos separados), así que
    `launcher/core.py` repite el nombre de la variable. Este candado detecta el
    día que alguien la renombre en un solo lado.
    """
    root = Path(__file__).resolve().parents[2]
    launcher_core = (root / "launcher" / "core.py").read_text(encoding="utf-8")

    assert f'REQUIRE_UI_ENV = "{REQUIRE_UI_ENV}"' in launcher_core, (
        "launcher/core.py dejó de declarar la misma variable de fail-closed"
    )


def test_el_launcher_no_arranca_el_backend_sin_ui():
    """La otra mitad: el launcher eleva antes de lanzar uvicorn."""
    root = Path(__file__).resolve().parents[2]
    manager = (root / "launcher" / "process_manager.py").read_text(encoding="utf-8")

    assert "frontend_dist_available()" in manager
    assert "PreparationError" in manager
    assert "backend_env()" in manager, (
        "el proceso de producto dejó de recibir la exigencia de UI"
    )
