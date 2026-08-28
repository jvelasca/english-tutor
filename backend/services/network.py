"""Utilidades de red local (determinar la IP de la LAN para el acceso remoto)."""
from __future__ import annotations

import socket


def get_lan_ip() -> str:
    """IP IPv4 de la LAN desde la que se sirve la app.

    Usa un socket UDP "connect" hacia una IP pública: es perezoso (no envía
    paquetes) y solo fuerza al SO a elegir la ruta/interfaz de salida, por lo
    que funciona incluso sin Internet real. Devuelve ``127.0.0.1`` como último
    recurso si no se puede resolver.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def get_lan_hostname() -> str:
    """Nombre del host en la red local (sin dominio), para acceso mDNS.

    P. ej. ``ENGLISH-TUTOR-PC``. Sirve para construir una URL estable
    (``https://<hostname>.local``) independiente de la IP dinámica del router.
    """
    return socket.gethostname().split(".")[0]
