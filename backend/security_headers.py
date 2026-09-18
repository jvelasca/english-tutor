"""Cabeceras HTTP defensivas (V3.73.x).

Hasta ahora las respuestas solo llevaban CORS y la protección de origen/rate
limiting de `security.py`: faltaban las cabeceras con las que el navegador evita
hacer cosas peligrosas con la respuesta (inferir tipos, enmarcar la app en otra
página, filtrar la URL de origen o abrir cámara/micrófono sin permiso).

Se implementa como middleware ASGI puro (no `BaseHTTPMiddleware`) para no romper
el streaming SSE del chat: solo añade cabeceras al `http.response.start`.

**No se envía HSTS** (`Strict-Transport-Security`) a propósito: el producto usa
un certificado **autofirmado** (`backend/data/certs/`) y un HSTS sobre un
certificado no confiable dejaría el origen inutilizable hasta limpiar el estado
del navegador.
"""
from __future__ import annotations

# CSP acotada a lo que **no** puede romper la carga de recursos: prohibir el
# enmarcado (clickjacking), los plugins, el `<base>` inyectado y el envío de
# formularios a terceros. Deliberadamente NO se fija `script-src`: el artefacto
# (`frontend/dist/index.html`) trae un script inline de tema, así que cerrarlo
# exige un hash y su propio candado (trabajo aparte, no de este cambio).
_CSP = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"

# El micrófono se permite (`self`) porque la práctica de speaking lo usa; cámara y
# geolocalización no tienen ningún consumidor en el producto.
_PERMISSIONS = "microphone=(self), camera=(), geolocation=()"

_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"content-security-policy", _CSP.encode("ascii")),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", _PERMISSIONS.encode("ascii")),
)


class SecurityHeadersMiddleware:
    """Añade las cabeceras defensivas a todas las respuestas HTTP.

    Respeta las cabeceras que ya venga poniendo la respuesta (no duplica ni
    pisa un valor más específico de una ruta concreta).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                presentes = {name.lower() for name, _ in headers}
                headers.extend(h for h in _HEADERS if h[0] not in presentes)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
