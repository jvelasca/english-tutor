"""Descubrimiento de la IP de LAN en el launcher (V3.73).

El launcher no puede importar el backend (son proyectos separados, y el job de CI
del launcher solo instala pytest/ruff), así que replica el algoritmo puro. El
candado de contrato está en el suite del backend
(`backend/tests/test_net_interfaces_v373.py`) y aquí se fija el comportamiento
del launcher: sin referencias externas y sin romperse cuando no hay red.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core import (
    candidate_addresses,
    is_usable_lan_address,
    lan_ip,
    select_lan_ipv4,
)

CORE_PATH = Path(__file__).resolve().parent.parent / "core.py"


@pytest.mark.parametrize("value", ["192.168.1.42", "10.0.0.7", "172.16.5.9"])
def test_las_direcciones_privadas_son_utilizables(value):
    assert is_usable_lan_address(value) is True


@pytest.mark.parametrize("value", ["127.0.0.1", "169.254.1.1", "0.0.0.0", "x"])
def test_se_descartan_loopback_link_local_y_basura(value):
    assert is_usable_lan_address(value) is False


def test_prefiere_la_privada_y_no_reordena():
    assert select_lan_ipv4(["8.8.8.8", "192.168.0.10"]) == "192.168.0.10"
    assert select_lan_ipv4(["192.168.0.10", "8.8.8.8"]) == "192.168.0.10"


def test_sin_direcciones_cae_a_loopback():
    assert select_lan_ipv4([]) == "127.0.0.1"


def test_la_enumeracion_nunca_lanza(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr("core.socket.getaddrinfo", boom)
    monkeypatch.setattr("core.socket.gethostbyname_ex", boom)

    assert candidate_addresses("equipo-inexistente") == []


def test_el_override_declarado_manda(monkeypatch):
    monkeypatch.setenv("ENGLISH_TUTOR_LAN_IP", "10.9.8.7")

    assert lan_ip() == "10.9.8.7"


def test_sin_override_usa_la_deteccion(monkeypatch):
    monkeypatch.delenv("ENGLISH_TUTOR_LAN_IP", raising=False)
    monkeypatch.setattr(
        "core.candidate_addresses", lambda *a, **k: ["169.254.1.1", "192.168.7.7"]
    )

    assert lan_ip() == "192.168.7.7"


def test_el_launcher_no_referencia_direcciones_publicas():
    """El launcher anunciaba la LAN con un socket a 8.8.8.8 hasta V3.72."""
    tree = ast.parse(CORE_PATH.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if isinstance(node, holders):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    docstrings.add(id(value))
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]

    for literal in literals:
        for public in ("8.8.8.8", "8.8.4.4", "1.1.1.1"):
            assert public not in literal, (
                f"launcher/core.py volvió a referenciar {public} en código: el "
                "descubrimiento de la LAN debe ser estrictamente local"
            )
