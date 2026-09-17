"""Descubrimiento de la IP de LAN sin referencias externas (V3.73).

Hasta V3.72 la IP local se obtenía con un socket UDP ``connect`` a ``8.8.8.8:80``.
Es una técnica correcta —el ``connect`` UDP es perezoso, elige la ruta de salida
y **no envía paquetes**— pero introduce una dirección pública en la lógica de
descubrimiento de una aplicación que se declara **100 % local**. La auditoría de
V3.72 lo dejó como P3: no hay dependencia de Internet, pero sí una referencia
externa innecesaria.

V3.73 resuelve el problema enumerando las direcciones que el propio sistema
asocia al nombre del equipo, sin consultar ninguna dirección de fuera.

El **algoritmo de selección es puro** (``select_lan_ipv4``) y por tanto se prueba
sin red; ``lan_ipv4()`` solo aporta la enumeración del sistema operativo.
"""
from __future__ import annotations

import ipaddress
import os
import socket

LOOPBACK = "127.0.0.1"

# Override declarado para equipos con varias NIC o VPN, donde la elección
# automática puede no ser la interfaz por la que se llega a la app.
LAN_IP_ENV = "ENGLISH_TUTOR_LAN_IP"


def is_usable_lan_address(value: str) -> bool:
    """True si la dirección sirve para anunciar la app en la LAN.

    Se descartan loopback (no es LAN), link-local ``169.254/16`` (auto-IP sin
    red), ``0.0.0.0`` y multicast: ninguna de ellas identifica una interfaz
    alcanzable desde otro equipo.
    """
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.version != 4:
        return False
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
    )


def select_lan_ipv4(addresses) -> str:
    """Primera dirección IPv4 utilizable, prefiriendo rangos privados.

    Es **determinista respecto al orden de entrada**: si la primera utilizable ya
    es privada, se devuelve esa (no se reordena). Solo si ninguna es privada se
    acepta la primera utilizable. Nunca devuelve vacío: el último recurso es
    ``127.0.0.1``.
    """
    usable = [value for value in addresses if is_usable_lan_address(value)]
    for value in usable:
        if ipaddress.ip_address(value).is_private:
            return value
    if usable:
        return usable[0]
    return LOOPBACK


def candidate_addresses(hostname: str | None = None) -> list[str]:
    """Direcciones IPv4 que el sistema asocia a este equipo (sin salir a la red).

    Combina dos resoluciones **locales** del propio nombre (``getaddrinfo`` y
    ``gethostbyname_ex``) porque en algunos Windows el nombre solo aparece en una
    de las dos. Un fallo de resolución devuelve lista vacía, nunca una excepción:
    el llamante decide el último recurso.
    """
    name = hostname if hostname is not None else socket.gethostname()
    seen: list[str] = []

    def _add(value: object) -> None:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)

    try:
        for info in socket.getaddrinfo(name, None, socket.AF_INET):
            _add(info[4][0])
    except OSError:
        pass
    try:
        _, _, addresses = socket.gethostbyname_ex(name)
        for value in addresses:
            _add(value)
    except OSError:
        pass
    return seen


def lan_ipv4(env: dict[str, str] | None = None) -> str:
    """IP IPv4 con la que anunciar la app en la LAN. Nunca vacía.

    Orden de decisión: override declarado (``ENGLISH_TUTOR_LAN_IP``) → interfaz
    del sistema → ``127.0.0.1``. No consulta ninguna dirección externa.
    """
    source = os.environ if env is None else env
    override = str(source.get(LAN_IP_ENV, "")).strip()
    if override and is_usable_lan_address(override):
        return override
    return select_lan_ipv4(candidate_addresses())
