"""Información de acceso en red (para mostrar la URL a otros equipos de la LAN)."""
from __future__ import annotations

from fastapi import APIRouter

from config import lan_mode
from services import network

router = APIRouter()

# V3.72 (RC-01): el backend sirve la API **y** la UI compilada, así que el
# producto vive en un único origen HTTPS. Antes la UI la servía el dev server de
# Vite en :5173 y este endpoint anunciaba ese puerto (que en el runtime de
# producto ya no escucha).
FRONTEND_PORT = 8000
BACKEND_PORT = 8000


@router.get("/api/network")
async def network_info() -> dict[str, str | bool]:
    """Datos de acceso, **con el modo declarado**.

    V3.73.x: la URL de LAN solo responde en modo LAN (`ENGLISH_TUTOR_LAN`); con el
    bind en loopback es un enlace muerto. El endpoint lo dice explícitamente
    (`lan_mode`) para que ninguna superficie del producto anuncie una dirección
    inalcanzable como si funcionara, y `url` se devuelve solo cuando de verdad
    sirve. El puerto de la URL **no** depende del modo: en LAN es el mismo origen
    HTTPS.
    """
    ip = network.get_lan_ip()
    hostname = network.get_lan_hostname()
    expuesta = lan_mode()
    return {
        "ip": ip,
        "hostname": hostname,
        "frontend_port": str(FRONTEND_PORT),
        "backend_port": str(BACKEND_PORT),
        "lan_mode": expuesta,
        "bind": "0.0.0.0" if expuesta else "127.0.0.1",
        "url": f"https://{ip}:{FRONTEND_PORT}" if expuesta else "",
        "local_url": f"https://{hostname}.local:{FRONTEND_PORT}",
        "local_url_available": expuesta and network.local_url_resolves(),
    }
