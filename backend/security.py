"""Seguridad LAN (V1.41): protección de origen + rate limiting en memoria.

Sin OAuth/cloud (la app es 100% local), el cierre de seguridad LAN se limita a:
- **Protección de origen (CSRF)**: rechazar peticiones de método no seguro
  (POST/PUT/PATCH/DELETE) cuyo encabezado `Origin` no coincide con los orígenes
  permitidos (localhost o IPs privadas de la LAN). Mitiga que una web maliciosa
  que el usuario visite en el mismo navegador dispare peticiones contra la app.
- **Rate limiting**: límite de peticiones por IP y ventana de tiempo, más estricto
  en los endpoints sensibles (subida de audio, restauración, chat, transcripción).
Todo en memoria (por proceso) y stdlib: suficiente para un servidor local de un
solo usuario; sin estado compartido ni dependencias externas.

Se implementa como middleware ASGI puro (no `BaseHTTPMiddleware`) para no romper
las respuestas en streaming (SSE del chat).
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque

import config

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_ORIGIN_RE = re.compile(config.ALLOWED_ORIGIN_REGEX)

# Ventana y límites de rate limiting (peticiones por IP). `_PATH_LIMITS` aplica
# límites más estrictos a los endpoints sensibles (por prefijo).
_RATE_WINDOW_SECONDS = 60.0
_DEFAULT_LIMIT = 600
_PATH_LIMITS: dict[str, int] = {
    "/api/audio-library/upload": 30,
    "/api/system/restore": 10,
    "/api/system/backup": 30,
    "/api/chat": 120,
    "/api/voz/transcribe": 60,
}

_clients: dict[str, deque[float]] = defaultdict(deque)


def origin_allowed(origin: str | None) -> bool:
    """¿Un `Origin` es admisible? Ausente (mismo origen / no navegador) → sí."""
    if not origin:
        return True
    if origin in config.ALLOWED_ORIGINS:
        return True
    return bool(_ORIGIN_RE.match(origin))


def _rate_limit_ok(host: str, path: str) -> bool:
    now = time.monotonic()
    limit = _DEFAULT_LIMIT
    for prefix, path_limit in _PATH_LIMITS.items():
        if path.startswith(prefix):
            limit = path_limit
            break
    queue = _clients[host]
    while queue and now - queue[0] > _RATE_WINDOW_SECONDS:
        queue.popleft()
    if len(queue) >= limit:
        return False
    queue.append(now)
    return True


def _header(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    for key, value in headers:
        if key.lower() == name:
            return value
    return None


async def _json(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityMiddleware:
    """Aplica protección de origen (CSRF) y rate limiting a todas las rutas HTTP."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        headers = scope.get("headers") or []
        origin_raw = _header(headers, b"origin")

        if method not in _SAFE_METHODS and origin_raw:
            if not origin_allowed(origin_raw.decode("latin-1")):
                await _json(send, 403, {"detail": "Origen no permitido"})
                return

        client = scope.get("client")
        host = client[0] if client else "unknown"
        path = scope.get("path", "")
        if not _rate_limit_ok(host, path):
            await _json(
                send,
                429,
                {"detail": "Demasiadas peticiones, inténtalo más tarde"},
            )
            return

        await self.app(scope, receive, send)
