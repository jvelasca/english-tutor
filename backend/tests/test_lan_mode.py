"""Modo LAN opt-in (V3.73.x): la red local no entra sin declaración explícita.

Hasta V3.73.6 el producto se enlazaba **siempre** a `0.0.0.0` y aceptaba
cualquier origen de red privada. Con la identidad viajando en la URL (P0 abierto,
ver `PARKED.md`), eso significaba que cualquier equipo de la red podía leer,
renombrar y borrar los datos del alumno sin más que abrir el navegador.

Este fichero fija la frontera nueva:

1. el modo es **fail-closed** (ausente ⇒ sin LAN, y ningún valor ambiguo lo activa),
2. las dos mitades de la política —el `403` de `security.py` y el patrón de
   `CORSMiddleware`— dicen **lo mismo** sobre los mismos orígenes,
3. y la documentación declara la frontera (si no, el usuario no puede saber por
   qué su móvil ya no entra).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import config
import security

ROOT = Path(__file__).resolve().parents[2]

# Orígenes de muestra sobre los que las dos mitades tienen que coincidir.
ORIGENES = (
    "http://localhost:5173",
    "https://localhost:8000",
    "http://localhost:9999",
    "http://127.0.0.1:5173",
    "https://192.168.1.20:8000",
    "http://192.168.1.20:5173",
    "https://192.168.1.20",
    "http://10.0.0.5:3000",
    "http://172.16.0.9",
    "http://172.15.0.9",
    "http://11.0.0.5",
    "https://evil.example.com",
    "https://192.168.1.20.evil.com",
    "https://localhost.evil.com",
)


@pytest.mark.parametrize("valor", ["0", "", "  ", "no", "false", "off", "quizá"])
def test_el_modo_lan_es_fail_closed(monkeypatch, valor):
    """Solo un valor afirmativo abre la LAN; cualquier otra cosa la deja cerrada."""
    monkeypatch.setenv(config.LAN_MODE_ENV, valor)
    assert config.lan_mode() is False


@pytest.mark.parametrize("valor", ["1", "true", "TRUE", " yes ", "on", "si", "sí"])
def test_un_valor_afirmativo_activa_el_modo(monkeypatch, valor):
    monkeypatch.setenv(config.LAN_MODE_ENV, valor)
    assert config.lan_mode() is True


def test_sin_la_variable_el_modo_esta_apagado(monkeypatch):
    monkeypatch.delenv(config.LAN_MODE_ENV, raising=False)
    assert config.lan_mode() is False


def test_las_dos_mitades_de_la_politica_de_origen_coinciden(monkeypatch):
    """Candado de deriva: el patrón de CORS y el `403` no pueden discrepar.

    Son dos caminos distintos (el middleware de CORS compila el patrón una vez;
    `security.origin_allowed` decide en cada petición con 403). Si uno se
    relajara o se endureciera solo, la política de origen tendría dos verdades y
    este test lo detecta sobre los mismos orígenes.
    """
    for modo in (False, True):
        if modo:
            monkeypatch.setenv(config.LAN_MODE_ENV, "1")
        else:
            monkeypatch.delenv(config.LAN_MODE_ENV, raising=False)
        patron = re.compile(config.cors_origin_regex())
        for origen in ORIGENES:
            por_regex = bool(patron.fullmatch(origen))
            por_security = security.origin_allowed(origen)
            assert por_regex == por_security, (
                f"con modo LAN={modo} las dos políticas discrepan sobre {origen}: "
                f"regex={por_regex}, origin_allowed={por_security}"
            )


def test_la_regex_de_cors_deja_fuera_las_ips_privadas_sin_modo(monkeypatch):
    """El cambio de frontera, medido directamente sobre el patrón."""
    monkeypatch.delenv(config.LAN_MODE_ENV, raising=False)
    sin_lan = re.compile(config.cors_origin_regex())
    monkeypatch.setenv(config.LAN_MODE_ENV, "1")
    con_lan = re.compile(config.cors_origin_regex())

    privada = "https://192.168.1.20:8000"
    assert sin_lan.fullmatch(privada) is None
    assert con_lan.fullmatch(privada) is not None
    # El propio equipo entra en los dos modos: la frontera es la LAN, no el local.
    for patron in (sin_lan, con_lan):
        assert patron.fullmatch("http://localhost:5173")
        assert patron.fullmatch("http://127.0.0.1:5173")


def test_la_variable_del_modo_se_llama_igual_en_launcher_y_backend():
    """Contrato compartido entre los dos proyectos (no se pueden importar).

    El launcher declara el modo en el entorno y el backend lo lee: si el nombre
    cambia en un lado, el backend se quedaría **siempre** en loopback mientras el
    launcher enlaza a `0.0.0.0`, o al revés. Se comprueba leyendo el texto, como
    ya se hace con `ENGLISH_TUTOR_REQUIRE_UI`.
    """
    core = (ROOT / "launcher" / "core.py").read_text(encoding="utf-8")

    assert f'LAN_ENV = "{config.LAN_MODE_ENV}"' in core, (
        "la variable del modo LAN dejó de coincidir entre launcher/core.py y "
        "backend/config.py"
    )
    assert "def lan_mode(" in core, "el launcher perdió la lectura del modo"


def test_el_launcher_declara_el_modo_al_backend():
    """El backend no puede deducir el modo de una variable que puede faltar."""
    core = (ROOT / "launcher" / "core.py").read_text(encoding="utf-8")

    assert "env[LAN_ENV]" in core, (
        "el launcher dejó de declarar el modo en el entorno del backend"
    )


def test_los_docs_declaran_la_frontera_de_loopback():
    """Sin esto, el usuario no tiene forma de saber por qué su móvil no entra."""
    for doc in (
        ROOT / "README.md",
        ROOT / "docs" / "PREMISAS.md",
        ROOT / "docs" / "ARQUITECTURA.md",
    ):
        texto = " ".join(doc.read_text(encoding="utf-8").split())
        assert config.LAN_MODE_ENV in texto, (
            f"{doc.name} no declara la variable del modo LAN"
        )
        assert "loopback" in texto.lower(), (
            f"{doc.name} no declara que el modo por defecto es loopback"
        )
