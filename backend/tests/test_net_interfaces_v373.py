"""Descubrimiento de la IP de LAN sin referencias externas (V3.73, cierre del P3).

La auditoría de V3.72 señaló que la IP local se obtenía con un socket UDP a
``8.8.8.8:80``: no era una dependencia de Internet (el ``connect`` UDP es
perezoso y no envía paquetes), pero sí una **referencia externa** en la lógica de
descubrimiento de una app que se declara 100 % local.

V3.73 lo sustituye por la enumeración de las direcciones del propio equipo. El
algoritmo de selección es puro, así que se prueba sin red.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.net_interfaces import (
    LAN_IP_ENV,
    candidate_addresses,
    is_usable_lan_address,
    lan_ipv4,
    select_lan_ipv4,
)

ROOT = Path(__file__).resolve().parents[2]


# --- El algoritmo de selección es puro -------------------------------------


@pytest.mark.parametrize(
    "value",
    ["192.168.1.42", "10.0.0.7", "172.16.5.9", "100.64.0.1", "8.8.8.8"],
)
def test_las_direcciones_con_identidad_de_interfaz_son_utilizables(value):
    """Una dirección pública sigue siendo una interfaz válida para anunciar."""
    assert is_usable_lan_address(value) is True


@pytest.mark.parametrize(
    "value",
    ["127.0.0.1", "169.254.10.20", "0.0.0.0", "224.0.0.1", "::1", "no-es-ip", ""],
)
def test_se_descartan_loopback_link_local_y_multicast(value):
    assert is_usable_lan_address(value) is False


def test_prefiere_la_primera_direccion_privada():
    assert select_lan_ipv4(["8.8.8.8", "192.168.0.10", "10.1.2.3"]) == "192.168.0.10"


def test_el_orden_de_entrada_no_se_reordena_si_ya_hay_privada():
    """Determinismo: dos ejecuciones con la misma entrada dan el mismo resultado."""
    assert select_lan_ipv4(["10.1.2.3", "192.168.0.10"]) == "10.1.2.3"


def test_si_ninguna_es_privada_se_acepta_la_primera_utilizable():
    assert select_lan_ipv4(["8.8.8.8", "1.1.1.1"]) == "8.8.8.8"


def test_sin_ninguna_direccion_utilizable_cae_a_loopback():
    assert select_lan_ipv4([]) == "127.0.0.1"
    assert select_lan_ipv4(["127.0.0.1", "169.254.1.1"]) == "127.0.0.1"


# --- La enumeración del sistema no revienta ---------------------------------


def test_la_enumeracion_nunca_lanza_y_no_devuelve_basura(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("sin resolución")

    monkeypatch.setattr("services.net_interfaces.socket.getaddrinfo", boom)
    monkeypatch.setattr("services.net_interfaces.socket.gethostbyname_ex", boom)

    assert candidate_addresses("equipo-inexistente") == []


def test_la_enumeracion_deduplica_las_direcciones(monkeypatch):
    monkeypatch.setattr(
        "services.net_interfaces.socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("192.168.1.5", 0))],
    )
    monkeypatch.setattr(
        "services.net_interfaces.socket.gethostbyname_ex",
        lambda *a, **k: ("pc", [], ["192.168.1.5", "10.0.0.4"]),
    )

    assert candidate_addresses("pc") == ["192.168.1.5", "10.0.0.4"]


# --- El override declarado --------------------------------------------------


def test_el_override_declarado_manda_sobre_la_deteccion():
    assert lan_ipv4({LAN_IP_ENV: "10.9.8.7"}) == "10.9.8.7"


def test_un_override_basura_se_ignora_sin_romper_nada():
    """Un valor inválido no puede romper el anuncio de la URL de LAN."""
    result = lan_ipv4({LAN_IP_ENV: "no-es-ip"})

    assert isinstance(result, str) and result
    assert result != "no-es-ip"


def test_sin_override_usa_la_deteccion_del_sistema(monkeypatch):
    monkeypatch.setattr(
        "services.net_interfaces.candidate_addresses",
        lambda *a, **k: ["169.254.1.1", "192.168.50.20"],
    )

    assert lan_ipv4({}) == "192.168.50.20"


# --- El candado de la frontera: sin referencias externas --------------------


def _code_string_literals(path: Path) -> list[str]:
    """Literales de cadena que son **código**, no docstrings.

    La prosa puede (y debe) explicar de dónde venía el ``8.8.8.8``; lo que no
    puede es aparecer en una cadena ejecutable. Se excluyen los docstrings por
    identidad de nodo y los comentarios no llegan al AST.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_el_descubrimiento_de_ip_no_contiene_direcciones_publicas():
    """La app se declara 100 % local: ninguna IP pública en el descubrimiento.

    Es el hallazgo P3 de la auditoría de V3.72 y este candado impide que vuelva
    por la puerta de atrás (en el backend o en el launcher).
    """
    files = [
        ROOT / "backend" / "services" / "net_interfaces.py",
        ROOT / "backend" / "services" / "network.py",
        ROOT / "backend" / "services" / "tls_cert.py",
        ROOT / "launcher" / "core.py",
    ]
    publics = ("8.8.8.8", "8.8.4.4", "1.1.1.1")
    for path in files:
        for literal in _code_string_literals(path):
            for public in publics:
                assert public not in literal, (
                    f"{path.name} volvió a referenciar la dirección pública "
                    f"{public} en código: el descubrimiento de la LAN debe ser "
                    "estrictamente local"
                )


def test_la_red_del_backend_no_usa_sockets_de_ruta():
    """El truco del socket UDP 'connect' queda retirado del backend."""
    text = (ROOT / "backend" / "services" / "network.py").read_text(encoding="utf-8")

    assert "net_interfaces" in text, "network.py dejó de delegar el descubrimiento"
    assert "SOCK_DGRAM" not in text
