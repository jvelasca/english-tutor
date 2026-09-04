"""Seguridad LAN (V1.41): protección de origen + rate limiting en memoria.

Sin OAuth/cloud (la app es 100% local), el cierre de seguridad LAN se limita a:
- **Protección de origen (CSRF)**: rechazar peticiones de método no seguro
  (POST/PUT/PATCH/DELETE) cuyo encabezado `Origin` no coincide con los orígenes
  permitidos (localhost o IPs privadas de la LAN). Mitiga que una web maliciosa
  que el usuario visite en el mismo navegador dispare peticiones contra la app.
- **Rate limiting**: límite de peticiones por IP y ventana de tiempo, más estricto
  en los endpoints sensibles (subida de audio, restauración, chat, transcripción).
  Todo en memoria (por proceso) y stdlib: suficiente para un servidor local de un
  solo usuario; sin estado compartido ni dependencias externas. Las sondas de
  salud (`/api/health`) están exentas: nunca consumen cupo ni pueden recibir 429,
  y los topes están holgados para el uso local normal (V3.6.2): cuando un modelo
  local satura el servidor, lo correcto es que las peticiones esperen (cola), no
  que se rechacen en ráfaga. Los rechazos quedan contados para exponerlos en
  `/api/system/status`.

Se implementa como middleware ASGI puro (no `BaseHTTPMiddleware`) para no romper
las respuestas en streaming (SSE del chat).
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque

import config

logger = logging.getLogger(__name__)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_ORIGIN_RE = re.compile(config.ALLOWED_ORIGIN_REGEX)

# Ventana y límites de rate limiting (peticiones por IP). `_PATH_LIMITS` aplica
# límites más estrictos a los endpoints sensibles (por prefijo). Los topes son
# holgados a propósito (V3.6.2): la app es local y los falsos 429 por ráfagas de
# pollers + reintentos eran más dañinos que el abuso que previenen.
_RATE_WINDOW_SECONDS = 60.0
_DEFAULT_LIMIT = 1200
_PATH_LIMITS: dict[str, int] = {
    "/api/audio-library/upload": 60,
    "/api/system/restore": 20,
    "/api/system/backup": 60,
    "/api/chat": 240,
    "/api/voz/transcribe": 180,
}

_clients: dict[str, deque[float]] = defaultdict(deque)

# Marca de tiempo (monotónica) de cada rechazo 429, para exponer la saturación
# en `/api/system/status` (rate_limit_snapshot). Solo lectura desde los routers.
_rejections: deque[float] = deque(maxlen=10_000)

# Prefijos de rutas exentas de rate limiting: las sondas de salud no consumen
# cupo ni pueden ser rechazadas, para que el launcher/health-check sigan
# funcionando aunque el servidor esté saturado.
_EXEMPT_PREFIXES = ("/api/health",)


def origin_allowed(origin: str | None) -> bool:
    """¿Un `Origin` es admisible? Ausente (mismo origen / no navegador) → sí."""
    if not origin:
        return True
    if origin in config.ALLOWED_ORIGINS:
        return True
    return bool(_ORIGIN_RE.match(origin))


def is_exempt(path: str) -> bool:
    """¿La ruta está exenta de rate limiting? (health checks)."""
    return path.startswith(_EXEMPT_PREFIXES)


def rate_limit_snapshot(window_seconds: float = _RATE_WINDOW_SECONDS) -> int:
    """Nº de rechazos 429 en la ventana (podando las marcas antiguas)."""
    now = time.monotonic()
    while _rejections and now - _rejections[0] > window_seconds:
        _rejections.popleft()
    return len(_rejections)


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


async def _json(
    send, status: int, payload: dict, extra_headers: list[tuple[bytes, bytes]] | None = None
) -> None:
    body = json.dumps(payload).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if extra_headers:
        headers.extend(extra_headers)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": headers,
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
        path = scope.get("path", "")

        if method not in _SAFE_METHODS and origin_raw:
            if not origin_allowed(origin_raw.decode("latin-1")):
                await _json(send, 403, {"detail": "Origen no permitido"})
                return

        # Health checks exentos: no consumen cupo y no se rechazan nunca.
        if method in _SAFE_METHODS and is_exempt(path):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        host = client[0] if client else "unknown"
        if not _rate_limit_ok(host, path):
            _rejections.append(time.monotonic())
            logger.warning(
                "Rate limit 429 en %s (host=%s): %d rechazo(s) en 60s",
                path,
                host,
                rate_limit_snapshot(),
            )
            await _json(
                send,
                429,
                {
                    "detail": (
                        "El servidor local está saturado: espera unos segundos e "
                        "inténtalo de nuevo"
                    ),
                    "code": "RATE_LIMITED",
                },
                extra_headers=[(b"retry-after", b"5")],
            )
            return

        await self.app(scope, receive, send)
