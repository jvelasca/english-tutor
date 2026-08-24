"""Información de acceso en red (para mostrar la URL a otros equipos de la LAN)."""
from __future__ import annotations

from fastapi import APIRouter

from services import network

router = APIRouter()

FRONTEND_PORT = 5173
BACKEND_PORT = 8000


@router.get("/api/network")
async def network_info() -> dict[str, str]:
    ip = network.get_lan_ip()
    return {
        "ip": ip,
        "frontend_port": str(FRONTEND_PORT),
        "backend_port": str(BACKEND_PORT),
        "url": f"http://{ip}:{FRONTEND_PORT}",
    }
