"""Credenciales de la cuenta (V3.81 · Fase 3 del P0 de identidad).

Este módulo **sustituye al PIN** de V3.76 (`services/pins.py`, retirado). Lo que
no cambia es la doctrina: **stdlib y cero dependencias nuevas**, PBKDF2-HMAC-
SHA256 con sal aleatoria por usuario e iteraciones declaradas en el propio valor
—para poder subirlas más adelante sin invalidar lo ya guardado—, y el **freno de
intentos**, que sigue siendo la pieza que de verdad carga el peso: una contraseña
corta es fuerza bruta trivial sin freno, por larga que sea la política.

Qué es y qué no es esto:

- Es una **credencial real por usuario**: `POST /api/session` deja de aceptar un
  id a secas cuando la cuenta tiene contraseña. Eso es exactamente lo que la
  Fase 3 del P0 dejó abierto, y contradice «sin cuentas, sin contraseñas» de
  `docs/PREMISAS.md` —una premisa que se reescribe con esta decisión, no que se
  incumpla a escondidas (ver `release-notes-v3.81.0.md`)—.
- **Sigue sin haber recuperación por email garantizada**: el producto es local y
  puede no tener SMTP. Quien olvide su contraseña la restablece el webmaster
  desde la consola de gestión. Es lo honesto: no se promete un correo que puede
  no salir.
- La comparación es en tiempo constante (`hmac.compare_digest`); comparar hashes
  con `==` filtra por temporización cuántos bytes acertó el atacante.
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

# Política de contraseña. El mínimo de 8 no es una opinión: por debajo de ahí,
# sin freno, una GPU prueba el espacio entero; con el freno de abajo, 8 ya
# obliga a miles de años. El máximo existe para que un cuerpo de 10 MB no
# convierta el KDF en una vía de agotamiento de CPU.
PASSWORD_MIN_CHARS = 8
PASSWORD_MAX_CHARS = 128

# Las que encabezan cualquier diccionario de ataque. No pretende ser una lista
# seria —eso es un diccionario, no una constante— sino cerrar las que la gente
# escribe de verdad cuando se le pide «una contraseña de 8». Se comparan en
# minúsculas.
_COMMON_PASSWORDS = frozenset(
    {
        "12345678",
        "123456789",
        "1234567890",
        "password",
        "contrasena",
        "contraseña",
        "qwertyui",
        "qwerty123",
        "iloveyou",
        "11111111",
        "00000000",
        "abcd1234",
        "password1",
        "english123",
    }
)

# Caducidad del token de verificación de email. Una hora es lo normal en
# cualquier alta: suficiente para ir al correo y volver, corto para que un enlace
# filtrado no sirva dentro de un mes.
EMAIL_TOKEN_TTL_SECONDS = 3600
_EMAIL_TOKEN_BYTES = 32

# --- Freno de intentos por cuenta -------------------------------------------
# Holgura antes de empezar a frenar. Quien se equivoca dos o tres veces no debe
# notar nada; a partir de ahí el retardo crece en potencias de 2.
_FREE_ATTEMPTS = 5
_MAX_DELAY_SECONDS = 300.0

_lock = threading.Lock()
_failures: dict[str, int] = {}
# Momento (monotónico) hasta el que la cuenta no puede volver a intentarlo.
_blocked_until: dict[str, float] = {}


def is_valid_password(password: object) -> bool:
    """¿Tiene forma de contraseña? Longitud sensata y no ser de las obvias."""
    if not isinstance(password, str):
        return False
    if password != password.strip():
        # Espacios en los extremos: casi siempre es un pegote de copiar y pegar,
        # y aceptarlo convierte «hola» y «hola » en dos contraseñas distintas que
        # nadie recuerda cuál era.
        return False
    if not (PASSWORD_MIN_CHARS <= len(password) <= PASSWORD_MAX_CHARS):
        return False
    if password.casefold() in _COMMON_PASSWORDS:
        return False
    # Todas las letras iguales («aaaaaaaa») tampoco es una contraseña.
    return len(set(password)) > 1


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str) -> str:
    """`password` en claro → `pbkdf2-sha256$<iter>$<sal>$<hash>`.

    La sal es nueva en cada llamada, así que dos cuentas con la misma contraseña
    no comparten hash (y romper una no rompe la otra).
    """
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"{_ALGORITHM}${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(stored: str, password: str) -> bool:
    """Compara en tiempo constante. Un valor corrupto o vacío no autentica.

    Un `stored` vacío es «cuenta sin credencial» y **no** debe llegar aquí: quien
    llama distingue ese caso para poder abrir la sesión sin pedir nada (es el
    estado heredado de los usuarios anteriores a V3.81). Aun así, la función es
    cerrada por defecto y devuelve `False`.
    """
    if not stored or not isinstance(password, str):
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
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def seconds_to_wait(uid: str) -> float:
    """Segundos que faltan para que la cuenta pueda reintentar (0.0 = libre)."""
    with _lock:
        until = _blocked_until.get(uid, 0.0)
        restante = until - time.monotonic()
    return restante if restante > 0 else 0.0


def note_failure(uid: str) -> float:
    """Registra una contraseña incorrecta y devuelve el retardo que pasa a aplicar.

    Los primeros `_FREE_ATTEMPTS` fallos no frenan (dedos torpes no son un
    ataque). A partir de ahí el retardo dobla: 1s, 2s, 4s… con techo de 5
    minutos, así que probar a mano el diccionario entero deja de ser barato.
    """
    with _lock:
        fallos = _failures.get(uid, 0) + 1
        _failures[uid] = fallos
        if fallos <= _FREE_ATTEMPTS:
            return 0.0
        delay = min(2.0 ** (fallos - _FREE_ATTEMPTS - 1), _MAX_DELAY_SECONDS)
        _blocked_until[uid] = time.monotonic() + delay
        return delay


def note_success(uid: str) -> None:
    """Una contraseña correcta limpia el contador: no penaliza a quien acierta."""
    with _lock:
        _failures.pop(uid, None)
        _blocked_until.pop(uid, None)


def reset_state() -> None:
    """Vacía el estado del freno. Solo para tests."""
    with _lock:
        _failures.clear()
        _blocked_until.clear()


def new_temporary_password() -> str:
    """Contraseña temporal que el webmaster entrega a mano (consola de gestión).

    Legible al dictarla en voz alta o copiarla de un pantallazo: tres bloques de
    cuatro caracteres de un alfabeto sin `0/O/1/l/I`, que son las que se confunden
    y obligan a repetir el alta.
    """
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    groups = [
        "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)
    ]
    return "-".join(groups)


# --- Verificación de email ---------------------------------------------------


def new_email_token() -> str:
    """Token de verificación en claro (el que viaja en el enlace del correo)."""
    return secrets.token_urlsafe(_EMAIL_TOKEN_BYTES)


def hash_email_token(token: str) -> str:
    """Hash del token para guardarlo.

    SHA-256 sin sal es suficiente aquí y es una decisión, no un descuido: el token
    lo genera el propio servidor con 256 bits de entropía (no es una contraseña
    elegida por una persona, así que no hay diccionario que lo ataque), es de un
    solo uso y caduca en una hora. Lo que sí evita el hash es que leer la fila de
    la BD baste para confirmar un email ajeno.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_valid_email(raw: object) -> bool:
    """¿Tiene forma de email? Deliberadamente laxa.

    La validación real de un correo es **recibirlo**. Una expresión regular
    estricta rechaza direcciones válidas (el caso clásico: `+` y subdominios) y no
    aporta nada a cambio, así que aquí solo se comprueba lo que sí distingue una
    dirección de un dedazo: una `@`, algo antes, un dominio con punto y nada de
    espacios.
    """
    if not isinstance(raw, str) or raw != raw.strip():
        return False
    if raw.count("@") != 1 or " " in raw or len(raw) > 254:
        return False
    local, _, domain = raw.partition("@")
    if not local or len(local) > 64:
        return False
    return "." in domain and not domain.startswith(".") and not domain.endswith(".")


def normalize_email(raw: str | None) -> str:
    """Email normalizado (sin espacios y en minúsculas), o `""` si no sirve.

    Se guarda siempre así: el índice único de la BD es `NOCASE`, pero normalizar
    además evita que dos filas que el índice considera iguales se muestren
    distinto («Ana@X.com» y «ana@x.com»).
    """
    text = (raw or "").strip().lower()
    return text if is_valid_email(text) else ""
