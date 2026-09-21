"""PIN opcional por perfil (V3.76 · Fase 3 del P0 de identidad).

Doctrina, la misma que `services/sessions.py`: **stdlib y cero dependencias
nuevas**. Aquí el hash es PBKDF2-HMAC-SHA256 con sal aleatoria por perfil e
iteraciones declaradas en el propio valor, para poder subirlas más adelante sin
invalidar los PIN ya guardados.

Qué es y qué no es esto (importa más que el código):

- Es una **mitigación que el alumno activa**, no autenticación de persona. Un
  perfil sin PIN (`pin_hash == ""`) sigue entrando sin credencial, exactamente
  como hasta V3.75.8. El P0 queda cerrado para los perfiles que la usan, no
  para el producto.
- Un PIN de 4-6 dígitos es fuerza bruta trivial **sin** el freno de intentos: la
  pieza que carga el peso es `seconds_to_wait()`, no la longitud. Por eso el
  freno vive en el mismo módulo que el hash y no como adorno.
- No hay recuperación ni identidad: quien olvide el PIN no puede demostrar que
  es él. Lo único honesto es declararlo (ver `docs/audit/PARKED.md`).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time

# Iteraciones del KDF. Se declaran en el valor guardado, así que subirlas es
# compatible: los hashes viejos se verifican con las suyas.
PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16
_ALGORITHM = "pbkdf2-sha256"

# Formato del PIN que acepta la UI y la API: 4-6 dígitos, nada más. Sin letras ni
# símbolos para que se pueda teclear en el móvil de un alumno sin fricción.
PIN_MIN_DIGITS = 4
PIN_MAX_DIGITS = 6

# --- Freno de intentos por perfil -------------------------------------------
# Holgura antes de empezar a frenar. Un alumno que se equivoca dos o tres veces
# no debe notar nada; a partir de ahí el retardo crece en potencias de 2.
_FREE_ATTEMPTS = 5
_MAX_DELAY_SECONDS = 300.0

_lock = threading.Lock()
_failures: dict[str, int] = {}
# Momento (monotónico) hasta el que el perfil no puede volver a intentarlo.
_blocked_until: dict[str, float] = {}


def is_valid_pin(pin: object) -> bool:
    """¿Tiene forma de PIN? 4-6 dígitos, sin espacios ni signos."""
    if not isinstance(pin, str):
        return False
    if not pin.isdigit():
        return False
    return PIN_MIN_DIGITS <= len(pin) <= PIN_MAX_DIGITS


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_pin(pin: str) -> str:
    """`pin` en claro → `pbkdf2-sha256$<iter>$<sal>$<hash>`.

    La sal es nueva en cada llamada (poner o cambiar el PIN), así que dos
    perfiles con el mismo PIN no comparten hash.
    """
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"{_ALGORITHM}${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_pin(stored: str, pin: str) -> bool:
    """Compara en tiempo constante. Un valor corrupto o vacío no autentica.

    Un `stored` vacío es «perfil sin PIN» y **no** debe llegar aquí: quien llama
    distingue ambos casos para poder responder `PIN_REQUIRED` en vez de un 401
    genérico. Aun así, la función es cerrada por defecto y devuelve `False`.
    """
    if not stored or not isinstance(pin, str):
        return False
    partes = stored.split("$")
    if len(partes) != 4 or partes[0] != _ALGORITHM:
        return False
    try:
        iterations = int(partes[1])
        salt = _unb64(partes[2])
        expected = _unb64(partes[3])
    except (ValueError, TypeError):
        return False
    if iterations <= 0 or not salt or not expected:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def seconds_to_wait(uid: str) -> float:
    """Segundos que faltan para que el perfil pueda reintentar (0.0 = libre)."""
    with _lock:
        until = _blocked_until.get(uid, 0.0)
        restante = until - time.monotonic()
    return restante if restante > 0 else 0.0


def note_failure(uid: str) -> float:
    """Registra un PIN incorrecto y devuelve el retardo que pasa a aplicar.

    Los primeros `_FREE_ATTEMPTS` fallos no frenan (dedos torpes no son un
    ataque). A partir de ahí el retardo dobla: 1s, 2s, 4s… con techo de 5
    minutos, así que 10.000 intentos de un PIN de 4 dígitos dejan de ser
    baratos.
    """
    with _lock:
        fallos = _failures.get(uid, 0) + 1
        _failures[uid] = fallos
        if fallos <= _FREE_ATTEMPTS:
            return 0.0
        delay = min(2.0 ** (fallos - _FREE_ATTEMPTS), _MAX_DELAY_SECONDS)
        _blocked_until[uid] = time.monotonic() + delay
        return delay


def note_success(uid: str) -> None:
    """Un PIN correcto limpia el contador: el freno no penaliza al que acierta."""
    with _lock:
        _failures.pop(uid, None)
        _blocked_until.pop(uid, None)


def reset_state() -> None:
    """Vacía el estado del freno. Solo para tests."""
    with _lock:
        _failures.clear()
        _blocked_until.clear()


def new_pin_token() -> str:
    """PIN aleatorio (lo usa el sembrado de perfiles de test, no la app)."""
    largo = secrets.choice(range(PIN_MIN_DIGITS, PIN_MAX_DIGITS + 1))
    return "".join(secrets.choice("0123456789") for _ in range(largo))
