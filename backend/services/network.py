"""Utilidades de red local (determinar la IP de la LAN para el acceso remoto)."""
from __future__ import annotations

import socket

from services.net_interfaces import lan_ipv4


def get_lan_ip() -> str:
    """IP IPv4 de la LAN desde la que se sirve la app.

    V3.73: delega en ``services.net_interfaces``, que enumera las direcciones del
    propio equipo **sin consultar ninguna dirección externa** (hasta V3.72 se
    usaba un socket UDP a ``8.8.8.8``, perezoso pero con una referencia pública
    dentro de una app que se declara 100 % local). Devuelve ``127.0.0.1`` como
    último recurso si no se puede resolver.
    """
    return lan_ipv4()


def get_lan_hostname() -> str:
    """Nombre del host en la red local (sin dominio), para acceso mDNS.

    P. ej. ``ENGLISH-TUTOR-PC``. Sirve para construir una URL estable
    (``https://<hostname>.local``) independiente de la IP dinámica del router.
    """
    return socket.gethostname().split(".")[0]


def local_url_resolves() -> bool:
    """Comprueba si ``<hostname>.local`` resuelve realmente vía mDNS.

    Generar la URL ``.local`` no instala un servicio mDNS: sin un respondedor
    (Bonjour/Avahi/mDNS en Windows) el nombre no resolverá. Se intenta una
    resolución real y se devuelve ``False`` ante cualquier fallo (sin mDNS,
    sin red, sin DNS).
    """
    try:
        socket.getaddrinfo(f"{get_lan_hostname()}.local", None)
        return True
    except OSError:
        return False
