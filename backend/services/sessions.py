"""Sesiones firmadas por el servidor (Fase 2 del P0 de identidad, V3.75).

**Por qué existe.** Hasta V3.73.x la identidad del alumno la elegía el
**cliente** (`?user_id=…`): cualquiera que alcanzara la API podía pedir los datos
de otro perfil con solo cambiar un parámetro. Esta pieza mueve la identidad al
servidor: el cliente recibe una cookie **firmada**, el servidor es la única
autoridad sobre quién eres, y la identidad deja de viajar en URLs (ni en enlaces,
ni en el historial, ni en los logs).

**Qué NO es.** **No es autenticación**, y conviene decirlo antes que nada: los
perfiles siguen **sin credencial** (`POST /api/session` acepta un `user_id` y
devuelve la cookie). Quien pueda alcanzar la API sigue pudiendo pedir sesión para
otro perfil. Lo que esta fase cierra es el **alcance** —la identidad no se forja
desde fuera del servidor— no el acceso. Autenticar de verdad es la Fase 3 y es una
decisión de producto (`docs/audit/PLAN-P0-IDENTIDAD.md` §4).

**Formato del token** (`base64url(payload).base64url(hmac_sha256(secreto, payload))`
con `payload = {"iat": <epoch>, "uid": "<perfil>"}` en JSON canónico). Es
deliberadamente **stdlib**: `itsdangerous` haría lo mismo con más superficie y el
proyecto no mete una dependencia para treinta líneas. Lo que **no** se hace a mano
es la comparación: `hmac.compare_digest` es en tiempo constante, porque comparar
firmas con `==` filtra por temporización cuántos bytes acertó el atacante.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# Nombre de la cookie de sesión. `HttpOnly` la pone el router (`Set-Cookie`), no
# el cliente: es justo la mitad que `et_user_id` no podía tener.
SESSION_COOKIE = "et_session"

# Fichero del secreto de firma, en `DATA_DIR` (no versionado, fuera del backup:
# ver `services/backup.py::_NON_PORTABLE_TOP_NAMES`). Un ZIP sin cifrar con esta
# clave dentro permite **forjar sesiones**, así que no puede viajar.
SESSION_SECRET_NAME = "session.secret"

# Caducidad: un año, la misma semántica de «recuerda mi perfil» que tenía la
# cookie `et_user_id`, pero decidida por el servidor en vez de por el cliente.
SESSION_TTL_SECONDS = 365 * 24 * 3600

_SEPARATOR = "."
_SECRET_BYTES = 32

# Margen para relojes desajustados entre el equipo y el navegador. Un token «del
# futuro» por unos segundos es un reloj movido, no un ataque; más allá del margen
# se rechaza, porque alargar la vida de un token no es un derecho del cliente.
_CLOCK_SKEW_SECONDS = 60


def secret_path() -> Path:
    """Ruta del secreto de firma del equipo."""
    return config.DATA_DIR / SESSION_SECRET_NAME


def _restrict(path: Path) -> None:
    """Permisos de usuario para el secreto (best-effort: en Windows es un no-op)."""
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - sistema de ficheros sin permisos POSIX
        logger.warning("No se pudieron restringir los permisos de %s", path)


def _secret() -> bytes:
    """Lee el secreto del equipo; lo crea la primera vez.

    Se lee en **cada** llamada en vez de cachearlo al importar: el valor no
    existe hasta el primer arranque (cachearlo ataría la sesión al orden de
    importación de los módulos) y así los tests pueden aislar `DATA_DIR` sin
    invalidar ninguna caché. Es leer 44 bytes por petición.

    Un fichero **vacío** se trata como ausente y se regenera: solo puede venir de
    una escritura interrumpida, y firmar con una clave vacía sería el fallo grave
    (cualquiera podría forjar sesiones). Como esa clave nunca llegó a firmar nada,
    regenerarla no invalida ninguna sesión real.
    """
    path = secret_path()
    for _ in range(2):
        data = path.read_bytes() if path.exists() else b""
        if data:
            return data
        if path.exists():
            # Fichero **vacío**: solo puede venir de una escritura interrumpida, y
            # como nunca llegó a firmar nada, retirarlo no invalida ninguna sesión
            # real. Firmar con una clave vacía sí sería el fallo grave: cualquiera
            # podría forjar sesiones.
            path.unlink(missing_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        value = secrets.token_urlsafe(_SECRET_BYTES).encode("ascii")
        try:
            # Creación **exclusiva**: el producto arranca un solo proceso y esta
            # función no tiene `await`, así que en la práctica no hay carrera;
            # `xb` es la red por si algún día hay dos arranques a la vez, para que
            # el segundo no pise el secreto del primero (y no invalide sus sesiones).
            with open(path, "xb") as handle:
                handle.write(value)
        except FileExistsError:
            continue  # lo creó otro: se vuelve a leer
        _restrict(path)
        logger.info("Secreto de sesión creado en %s", path)
        return value
    raise RuntimeError(f"No se pudo crear el secreto de sesión en {path}")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    mac = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(mac)


def issue(user_id: str, *, epoch: int = 0, now: int | None = None) -> str:
    """Emite un token firmado para `user_id` en la época de autenticación `epoch`.

    `epoch` (V3.81) es lo que permite **cerrar sesiones de verdad**: viaja dentro
    del token firmado y el servidor lo compara con el de la fila en cada
    petición, así que cambiar la contraseña o forzar una baja invalida al
    instante todas las sesiones abiertas de esa cuenta. Sin él, una baja forzada
    no surtía efecto hasta que caducara la cookie (un año).

    `now` existe para los tests de caducidad: permite emitir un token «del
    pasado» sin tocar el reloj del sistema.
    """
    issued_at = int(time.time()) if now is None else int(now)
    payload = json.dumps(
        {"iat": issued_at, "uid": user_id, "ep": int(epoch)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    body = _b64encode(payload)
    return f"{body}{_SEPARATOR}{_sign(body)}"


def verify_session(
    token: str | None, *, now: int | None = None
) -> tuple[str, int] | None:
    """`(user_id, época)` de un token válido, o `None` si no lo es.

    `None` cubre **todos** los motivos (ausente, mal formado, firma que no cuadra,
    caducado, del futuro): quien llama no puede distinguirlos, y eso es
    deliberado — el cliente no recibe pistas sobre por qué su token falla.
    """
    if not token:
        return None
    body, separator, signature = token.partition(_SEPARATOR)
    if not body or not separator or not signature:
        return None
    if not hmac.compare_digest(_sign(body), signature):
        return None
    try:
        payload = json.loads(_b64decode(body))
        user_id = payload["uid"]
        issued_at = int(payload["iat"])
        # Un token de una versión anterior no trae época: se lee como 0, que es
        # la de las cuentas que aún no han cambiado nada. Así, actualizar la app
        # no cierra la sesión de nadie sin motivo.
        epoch = int(payload.get("ep", 0))
    except (ValueError, TypeError, KeyError, binascii.Error):
        return None
    if not isinstance(user_id, str) or not user_id:
        return None
    current = int(time.time()) if now is None else int(now)
    if issued_at > current + _CLOCK_SKEW_SECONDS:
        return None  # token del futuro: reloj movido o manipulado
    if current - issued_at > SESSION_TTL_SECONDS:
        return None
    return user_id, epoch


def verify(token: str | None, *, now: int | None = None) -> str | None:
    """Devuelve el `user_id` de un token válido, o `None` si no lo es.

    Se conserva porque es la firma que usan los sitios que no necesitan la época
    (tests, diagnóstico); la comprobación de época vive en `dependencies`.
    """
    resolved = verify_session(token, now=now)
    return resolved[0] if resolved is not None else None


def is_https(request) -> bool:  # noqa: ANN001 - se evita importar fastapi aquí
    """¿La petición llegó por HTTPS? Decide el atributo `Secure` de la cookie.

    `Secure` impide que la cookie viaje por HTTP en claro, pero si se pusiera
    siempre el navegador la **descartaría** en el modo de desarrollo (Vite sirve
    por HTTP), y la sesión no se abriría nunca. Por eso se decide por petición,
    igual que hacía la cookie de perfil que la Fase 2 del P0 retiró.

    Vive aquí y no en cada router porque abrir sesión ocurre ya en tres sitios
    (`/api/session`, `/api/account/activate`, `/api/account/reset-password`): tres
    copias de la misma política de cookie es exactamente cómo una de ellas se
    queda atrás en la siguiente release.
    """
    forwarded = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded.split(",")[0].strip() == "https"


def set_cookie(response, token: str, *, secure: bool) -> None:  # noqa: ANN001
    """Emite la cookie de sesión con la política del producto, en un solo sitio.

    `HttpOnly` (fuera del alcance de JavaScript) y `SameSite=Lax` (el producto no
    necesita flujos de terceros) no son negociables; `Secure` lo decide quien
    llama con `is_https`.
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )
