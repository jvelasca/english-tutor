"""Información de acceso en red (para mostrar la URL a otros equipos de la LAN)."""
from __future__ import annotations

from fastapi import APIRouter

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
    ip = network.get_lan_ip()
    hostname = network.get_lan_hostname()
    return {
        "ip": ip,
        "hostname": hostname,
        "frontend_port": str(FRONTEND_PORT),
        "backend_port": str(BACKEND_PORT),
        "url": f"https://{ip}:{FRONTEND_PORT}",
        "local_url": f"https://{hostname}.local:{FRONTEND_PORT}",
        "local_url_available": network.local_url_resolves(),
    }
