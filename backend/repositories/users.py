"""Repositorio de usuarios (SQLite).

V3.81 (Fase 3 del P0 de identidad): el «perfil» es una **cuenta**. La fila de
`users` guarda ahora también el email, el hash de la contraseña, el estado de
verificación del correo y la época de autenticación, y el historial de lo que
decide la administración vive en `user_events`.

Dos invariantes que este módulo sostiene y que conviene leer antes de tocarlo:

1. **Los secretos no salen del diccionario del perfil.** `password_hash`,
   `auth_epoch` y `email_verify_token_hash` se leen para derivar
   `has_password`, pero se retiran antes de devolver la fila: exponerlos en
   `GET /api/users` no aporta nada y le da material al atacante. Es la misma
   doctrina con la que V3.76 trataba `pin_hash`.
2. **`pin_hash` sigue en la tabla y ya no se lee.** Retirar la columna exigiría
   reconstruir la tabla en SQLite, y una copia antigua restaurada sobre esta
   versión tiene que seguir abriendo.
"""
from __future__ import annotations

import uuid
from contextlib import closing

from repositories.db import _conn, _now, redact_emails

# Columnas que forman el perfil que la API sirve. `email_verified_at` viaja
# porque es informativo (cuándo se verificó), no porque sea un secreto.
_COLUMNS = (
    "id, name, avatar_color, avatar_emoji, avatar_image, is_test, created_at, "
    "status, email, email_verified_at, must_change_password"
)

# Columnas de secreto: se LEEN para derivar los booleanos del perfil
# (`has_password`) y para validar la época de las sesiones, pero **nunca** salen
# en el diccionario.
_SECRET_COLUMNS = "password_hash, auth_epoch, email_verify_token_hash"

_SELECT = f"{_COLUMNS}, {_SECRET_COLUMNS}"

# V3.77 + V3.81: estado de servicio de la cuenta. `unenrolled` es la baja
# **autoservicio** (el propio usuario se retira) y `disabled` es la decisión del
# webmaster; las dos sacan la cuenta del selector y le cierran la sesión, y las
# dos son reversibles. `active` es la única que puede tener sesión.
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
STATUS_UNENROLLED = "unenrolled"
# Estados que el webmaster puede poner con `set_status` (la baja autoservicio
# tiene su propia función: no es una decisión suya).
STATUSES = (STATUS_ACTIVE, STATUS_DISABLED, STATUS_UNENROLLED)

# Acciones que se registran en `user_events`. Son códigos y no texto libre para
# que el lanzador pueda contarlas y traducirlas sin inventarse cadenas.
EVENT_CREDENTIALS = "credentials"  # el webmaster asigna email + contraseña
EVENT_EMAIL_VERIFIED = "email_verified"
EVENT_PASSWORD_CHANGED = "password_changed"
EVENT_INVITED = "invited"  # V3.82: se emitió la invitación de activación
EVENT_ACTIVATED = "activated"  # V3.82: la persona puso su contraseña
EVENT_PASSWORD_RESET = "password_reset"  # V3.82: «olvidé mi contraseña»
EVENT_UNENROLLED = "unenrolled"  # el propio usuario pide la baja
EVENT_ENROLLED = "reenrolled"
EVENT_DISABLED = "disabled"
EVENT_FORCE_UNENROLLED = "force_unenrolled"  # el webmaster da de baja
EVENT_PURGED = "purged"
EVENT_EDITED = "edited"
EVENT_CREATED = "created"


def _row_to_user(row: object) -> dict:
    """Fila de `users` → perfil de la API, con los secretos retirados."""
    data = dict(row)  # type: ignore[arg-type]
    data["has_password"] = bool(data.pop("password_hash", "") or "")
    # La época solo la usan las sesiones (`get_auth_epoch`): fuera del perfil.
    data.pop("auth_epoch", None)
    data.pop("email_verify_token_hash", None)
    data["email_verified"] = bool(data.get("email_verified_at"))
    data["must_change_password"] = bool(data.get("must_change_password"))
    return data


def _fold_name(name: str) -> str:
    """Nombre comparable: espacios colapsados y sin distinguir mayúsculas.

    Es la misma normalización que aplica el dominio al normalizar un nombre
    (`normalize_name`), **duplicada** aquí a propósito: el repositorio no puede
    importar el dominio (sería un ciclo) y una regla de unicidad que solo
    funcionara en la capa de arriba no serviría.
    """
    return " ".join((name or "").split()).casefold()


def name_in_use(name: str, *, exclude_uid: str | None = None) -> bool:
    """¿Otro usuario **activo** ya se llama así? (V3.80.2)

    El selector pinta los usuarios por nombre y con dos «J.A» no hay forma de
    saber cuál es cuál, así que el nombre se trata como identificador visible.
    Los perfiles de **prueba** quedan fuera a propósito (`is_test`): los crea y
    los borra el teardown de los tests visuales, y hacerlos chocar con esta
    regla convertiría un residuo de test en un alta rota.
    """
    folded = _fold_name(name)
    if not folded:
        return False
    return any(
        user["id"] != exclude_uid and _fold_name(user["name"]) == folded
        for user in list_users(include_test=False, include_disabled=False)
    )


def email_in_use(email: str, *, exclude_uid: str | None = None) -> bool:
    """¿Otra cuenta ya usa ese email? (V3.81)

    La BD tiene un índice único `NOCASE` que es la garantía de verdad; esto es la
    comprobación previa que permite dar un 409 legible en vez de un error de
    integridad. Se normaliza en minúsculas, igual que se guarda.
    """
    text = (email or "").strip().lower()
    if not text:
        return False
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email <> '' AND email = ? COLLATE NOCASE "
            "AND id <> ? LIMIT 1",
            (text, exclude_uid or ""),
        ).fetchone()
    return row is not None


def find_by_email(email: str) -> dict | None:
    """Cuenta por email (normalizado), o `None`. Lo usa el login opcional."""
    text = (email or "").strip().lower()
    if not text:
        return None
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_SELECT} FROM users WHERE email = ? COLLATE NOCASE LIMIT 1",
            (text,),
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def find_by_email_token(token_hash: str) -> dict | None:
    """Cuenta cuya verificación pendiente es ese token (hasheado), o `None`.

    Se busca por el hash, nunca por el token en claro: en la BD no hay nada que
    permita confirmar un email ajeno aunque alguien lea la fila.
    """
    if not token_hash:
        return None
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_SELECT} FROM users WHERE email_verify_token_hash = ? LIMIT 1",
            (token_hash,),
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def create_user(
    name: str,
    is_test: bool = False,
    *,
    email: str = "",
    password_hash: str = "",
    must_change_password: bool = False,
    avatar_color: str = "",
    avatar_emoji: str = "",
    avatar_image: str = "",
) -> dict:
    """Alta. Con `email`/`password_hash` nace una cuenta con credencial.

    V3.82: admite el avatar elegido en la solicitud, para que aprobarla no obligue
    a elegir de nuevo lo que la persona ya eligió al pedir la cuenta.
    """
    uid = uuid.uuid4().hex
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO users "
            "(id, name, created_at, is_test, email, password_hash, "
            "must_change_password, avatar_color, avatar_emoji, avatar_image) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uid,
                name,
                now,
                1 if is_test else 0,
                email,
                password_hash,
                1 if must_change_password else 0,
                avatar_color,
                avatar_emoji,
                avatar_image,
            ),
        )
    return {
        "id": uid,
        "name": name,
        "avatar_color": avatar_color,
        "avatar_emoji": avatar_emoji,
        "avatar_image": avatar_image,
        "is_test": is_test,
        "has_password": bool(password_hash),
        "email": email,
        "email_verified": False,
        "email_verified_at": None,
        "must_change_password": bool(must_change_password),
        "created_at": now,
        "status": STATUS_ACTIVE,
    }


def list_users(
    include_test: bool = False, include_disabled: bool = False
) -> list[dict]:
    """Cuentas locales. Por defecto EXCLUYE las de prueba y las no activas.

    V3.52.1: los perfiles de test (p. ej. «Visual Tester» de los tests visuales
    de Playwright) no deben aparecer en el selector de la app. Con
    `include_test=True` se listan también (lo usan los propios tests para
    localizar/limpiar su perfil).

    V3.77/V3.81: una cuenta **desactivada** o **dada de baja** tampoco aparece en
    el selector —eso es justo lo que significa— y `include_disabled=True` la
    recupera para la consola de gestión, que es quien puede reactivarla o
    purgarla.
    """
    clauses: list[str] = []
    if not include_test:
        clauses.append("is_test = 0")
    if not include_disabled:
        clauses.append(f"status = '{STATUS_ACTIVE}'")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_SELECT} FROM users{where} ORDER BY created_at ASC"
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def get_user(uid: str) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_SELECT} FROM users WHERE id = ?", (uid,)
        ).fetchone()
    return _row_to_user(row) if row is not None else None


# --- Secreto de la cuenta ----------------------------------------------------


def get_password_hash(uid: str) -> str | None:
    """Hash de la contraseña (`""` si no tiene credencial), o `None` si no existe.

    Consulta aparte a propósito: separa «quién es esta cuenta» (lo que la API
    sirve) de «con qué secreto entra» (lo que solo mira la apertura de sesión).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (uid,)
        ).fetchone()
    if row is None:
        return None
    return row["password_hash"] or ""


def get_auth_epoch(uid: str) -> int | None:
    """Época de autenticación, o `None` si la cuenta no existe.

    Va dentro del token de sesión: cuando cambia la contraseña o se fuerza una
    baja, sube, y **todas** las sesiones abiertas dejan de valer en la siguiente
    petición. Sin esto, forzar una baja no surtiría efecto hasta que caducara la
    cookie (un año).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT auth_epoch FROM users WHERE id = ?", (uid,)
        ).fetchone()
    if row is None:
        return None
    return int(row["auth_epoch"] or 0)


def set_password_hash(
    uid: str, password_hash: str, *, must_change: bool = False
) -> bool:
    """Escribe la contraseña (o la retira, con `""`) y sube la época.

    Subir la época en **cualquier** cambio es la decisión, no un efecto colateral:
    si alguien cambia la contraseña es porque sospecha que otro la sabe, así que
    dejar viva la sesión del intruso sería cerrar la puerta con él dentro.
    """
    if get_user(uid) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = ?, "
            "auth_epoch = auth_epoch + 1 WHERE id = ?",
            (password_hash, 1 if must_change else 0, uid),
        )
    return True


def set_credentials(
    uid: str, *, email: str, password_hash: str, must_change: bool = True
) -> dict | None:
    """Email + contraseña de golpe (el webmaster, desde la consola). Atómico.

    Se hace en una sola escritura a propósito: un email sin contraseña (o al
    revés) dejaría la cuenta en un estado que el webmaster no pidió y que nadie
    sabría deshacer desde la UI.
    """
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET email = ?, password_hash = ?, "
            "email_verified_at = NULL, email_verify_token_hash = '', "
            "must_change_password = ?, auth_epoch = auth_epoch + 1 WHERE id = ?",
            (email, password_hash, 1 if must_change else 0, uid),
        )
    return get_user(uid)


def set_email(uid: str, email: str, *, verified: bool = False) -> dict | None:
    """Cambia el email y reinicia su verificación. `None` si no existe."""
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET email = ?, email_verified_at = ?, "
            "email_verify_token_hash = '' WHERE id = ?",
            (email, _now() if verified and email else None, uid),
        )
    return get_user(uid)


def set_email_verification(uid: str, token_hash: str) -> bool:
    """Guarda el token de verificación (hasheado) y cuándo se emitió."""
    if get_user(uid) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET email_verify_token_hash = ?, "
            "email_verify_sent_at = ? WHERE id = ?",
            (token_hash, _now(), uid),
        )
    return True


def get_email_verification(uid: str) -> tuple[str, str] | None:
    """`(token_hash, sent_at)` de la verificación pendiente, o `None`."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT email_verify_token_hash, email_verify_sent_at FROM users "
            "WHERE id = ?",
            (uid,),
        ).fetchone()
    if row is None:
        return None
    return (row["email_verify_token_hash"] or "", row["email_verify_sent_at"] or "")


def mark_email_verified(uid: str) -> dict | None:
    """Sella el email como verificado y consume el token (de un solo uso)."""
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET email_verified_at = ?, email_verify_token_hash = '' "
            "WHERE id = ?",
            (_now(), uid),
        )
    return get_user(uid)


# --- Activación de la cuenta (invitación, V3.82) ------------------------------
#
# El ciclo es: el webmaster aprueba → se emite un token de activación y sale el
# correo → la persona abre el enlace y **elige su contraseña**. Son tres columnas
# y dos operaciones, y el token se guarda hasheado igual que los demás: quien lea
# la BD no puede activar una cuenta ajena con lo que hay en la fila.


def set_activation(uid: str, token_hash: str) -> bool:
    """Guarda el token de activación (hasheado) y cuándo se emitió."""
    if get_user(uid) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET activation_token_hash = ?, activation_sent_at = ? "
            "WHERE id = ?",
            (token_hash, _now(), uid),
        )
    return True


def get_activation(uid: str) -> tuple[str, str] | None:
    """`(token_hash, sent_at)` de la invitación pendiente, o `None`."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT activation_token_hash, activation_sent_at FROM users "
            "WHERE id = ?",
            (uid,),
        ).fetchone()
    if row is None:
        return None
    return (row["activation_token_hash"] or "", row["activation_sent_at"] or "")


def find_by_activation_token(token_hash: str) -> dict | None:
    """Cuenta cuya invitación pendiente es ese token (hasheado), o `None`."""
    if not token_hash:
        return None
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_SELECT} FROM users WHERE activation_token_hash = ? LIMIT 1",
            (token_hash,),
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def mark_activated(uid: str, *, email_verified: bool = True) -> dict | None:
    """Pone la contraseña de activación, consume el token y da el email por bueno.

    Marcar el email como verificado no es un atajo: para canjear el token hay que
    haber recibido el correo y abierto el enlace, que es exactamente lo que la
    verificación comprueba. Pedir además un segundo enlace sería pedir dos veces
    lo mismo.

    La contraseña **no** se escribe aquí: la escribe `set_password_hash`, que es
    el único sitio que sube la época de autenticación (`auth_epoch`). Mezclar las
    dos cosas aquí dejaría dos formas de cambiar una contraseña, y solo una
    sería la que revoca las sesiones.
    """
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET activation_token_hash = '', activation_sent_at = NULL, "
            "email_verified_at = ?, email_verify_token_hash = '' "
            "WHERE id = ?",
            (_now() if email_verified else None, uid),
        )
    return get_user(uid)


# --- Restablecimiento de contraseña (V3.82) ----------------------------------


def set_password_reset(uid: str, token_hash: str) -> bool:
    """Guarda el token de restablecimiento (hasheado) y cuándo se emitió."""
    if get_user(uid) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET password_reset_token_hash = ?, "
            "password_reset_sent_at = ? WHERE id = ?",
            (token_hash, _now(), uid),
        )
    return True


def get_password_reset(uid: str) -> tuple[str, str] | None:
    """`(token_hash, sent_at)` del restablecimiento pendiente, o `None`."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT password_reset_token_hash, password_reset_sent_at FROM users "
            "WHERE id = ?",
            (uid,),
        ).fetchone()
    if row is None:
        return None
    return (
        row["password_reset_token_hash"] or "",
        row["password_reset_sent_at"] or "",
    )


def find_by_password_reset_token(token_hash: str) -> dict | None:
    """Cuenta cuyo restablecimiento pendiente es ese token (hasheado), o `None`."""
    if not token_hash:
        return None
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_SELECT} FROM users "
            "WHERE password_reset_token_hash = ? LIMIT 1",
            (token_hash,),
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def clear_password_reset(uid: str) -> bool:
    """Consume el token de restablecimiento (de un solo uso)."""
    if get_user(uid) is None:
        return False
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET password_reset_token_hash = '', "
            "password_reset_sent_at = NULL WHERE id = ?",
            (uid,),
        )
    return True


def update_user(
    uid: str,
    *,
    name: str | None = None,
    avatar_color: str | None = None,
    avatar_emoji: str | None = None,
    avatar_image: str | None = None,
) -> dict | None:
    """Actualiza solo los campos indicados. Devuelve el usuario actualizado o
    None si no existe."""
    existing = get_user(uid)
    if existing is None:
        return None
    new_name = name if name is not None else existing["name"]
    new_color = avatar_color if avatar_color is not None else existing["avatar_color"]
    new_emoji = avatar_emoji if avatar_emoji is not None else existing["avatar_emoji"]
    new_image = avatar_image if avatar_image is not None else existing["avatar_image"]
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET name = ?, avatar_color = ?, avatar_emoji = ?, "
            "avatar_image = ? WHERE id = ?",
            (new_name, new_color, new_emoji, new_image, uid),
        )
    return get_user(uid)


def set_status(uid: str, status: str) -> dict | None:
    """Desactiva o reactiva una cuenta. `None` si no existe o el estado no vale.

    Desactivar es la mitad **reversible** de un borrado: la cuenta sale del
    selector y no puede abrir sesión, pero no se toca ni una fila de su
    evidencia. Es el camino por defecto del webmaster.
    """
    if status not in STATUSES:
        return None
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, uid))
    return get_user(uid)


def set_unenrolled(uid: str, *, enrolled: bool) -> dict | None:
    """Baja autoservicio (y su vuelta). Sube la época: la sesión se cierra ya.

    No borra nada: marca `unenrolled_at` y el estado. Los datos del alumno se
    quedan donde están y solo el webmaster decide después si se purgan.
    """
    if get_user(uid) is None:
        return None
    with closing(_conn()) as conn, conn:
        if enrolled:
            conn.execute(
                "UPDATE users SET status = ?, unenrolled_at = NULL, "
                "auth_epoch = auth_epoch + 1 WHERE id = ?",
                (STATUS_ACTIVE, uid),
            )
        else:
            conn.execute(
                "UPDATE users SET status = ?, unenrolled_at = ?, "
                "auth_epoch = auth_epoch + 1 WHERE id = ?",
                (STATUS_UNENROLLED, _now(), uid),
            )
    return get_user(uid)


# --- Historial de la administración ------------------------------------------


def record_event(
    *,
    subject_id: str,
    subject_name: str,
    action: str,
    note: str = "",
    actor: str = "webmaster",
) -> None:
    """Anota una decisión de la administración (o un hito de la cuenta).

    Nunca lanza hacia fuera por un fallo al anotar: perder una línea de historial
    es malo, pero tumbar la acción que ya se ejecutó es peor (el webmaster
    creería que no se hizo y la repetiría).
    """
    try:
        with closing(_conn()) as conn, conn:
            conn.execute(
                "INSERT INTO user_events "
                "(subject_id, subject_name, action, actor, note, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (subject_id, subject_name, action, actor, note, _now()),
            )
    except Exception:  # noqa: BLE001 - ver docstring
        pass


def list_events(subject_id: str, limit: int = 50) -> list[dict]:
    """Historial de una cuenta, del más reciente al más antiguo."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, subject_id, subject_name, action, actor, note, created_at "
            "FROM user_events WHERE subject_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (subject_id, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def _purge_user_rows(conn, uid: str) -> None:
    """Borra las filas de TODAS las tablas con `user_id` para una cuenta.

    Se enumeran dinámicamente (igual que `scripts/purge_virtual_testers.py`)
    porque el esquema **no** tiene `ON DELETE CASCADE` salvo en `messages`, y se
    abre la conexión con las FKs desactivadas para que el orden de borrado no
    importe. No borra la fila de `users`: eso lo decide quien llama.

    `user_events` **no** entra aquí aunque hable de la misma cuenta: su columna es
    `subject_id` a propósito, para que el registro de un purgado sobreviva al
    purgado (es el registro que responde «¿quién borró esto y por qué?»).
    """
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    ]
    tables = []
    for name in names:
        columns = {c[1] for c in conn.execute(f'PRAGMA table_info("{name}")')}
        if "user_id" in columns:
            tables.append(name)
    conversation_ids = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM conversations WHERE user_id = ?", (uid,)
        )
    ]
    if conversation_ids:
        marks = ", ".join("?" for _ in conversation_ids)
        conn.execute(
            f"DELETE FROM messages WHERE conversation_id IN ({marks})",
            conversation_ids,
        )
    for name in tables:
        safe = '"' + name.replace('"', '""') + '"'
        conn.execute(f"DELETE FROM {safe} WHERE user_id = ?", (uid,))


def delete_test_user(uid: str) -> bool:
    """Borra un perfil de PRUEBA y sus filas dependientes (V3.52.1).

    Lo usa el teardown de los tests visuales para no dejar residuos en la BD
    local. Muy acotado: si el id no está marcado como `is_test = 1` devuelve
    False sin tocar nada (nunca puede borrar un perfil real).
    """
    with closing(_conn(foreign_keys=False)) as conn, conn:
        row = conn.execute("SELECT is_test FROM users WHERE id = ?", (uid,)).fetchone()
        if row is None or not row["is_test"]:
            return False
        _purge_user_rows(conn, uid)
        conn.execute("DELETE FROM users WHERE id = ? AND is_test = 1", (uid,))
        return True


def redact_subject_notes(conn, subject_id: str) -> None:
    """Redacta los correos que hubieran quedado en las notas del historial.

    `user_events` no entra en `_purge_user_rows` a propósito: es el registro que
    responde «¿quién borró esta cuenta y por qué?». Pero su `note` es texto libre
    y en V3.81 pudo guardar el email, así que purgar la cuenta y dejar el correo
    atrás sería lo contrario de lo que la purga promete. Redactar aquí —antes de
    borrar la fila de `users`— es la garantía de que no sobrevive PII, y
    complementa la limpieza de arranque de `repositories/db.py`.
    """
    rows = conn.execute(
        "SELECT id, note FROM user_events WHERE subject_id = ? AND note LIKE '%@%'",
        (subject_id,),
    ).fetchall()
    for row in rows:
        redacted = redact_emails(row["note"])
        if redacted != row["note"]:
            conn.execute(
                "UPDATE user_events SET note = ? WHERE id = ?", (redacted, row["id"])
            )


def purge_user(uid: str) -> bool:
    """Borra una cuenta REAL y toda su evidencia (V3.77). Irreversible.

    Es la mitad **no reversible** del borrado y por eso no la llama nadie por su
    cuenta: el webmaster la ejecuta desde la consola de gestión, tras una
    confirmación por nombre y **después** de que `services.backup` haya tomado una
    copia. Admite cualquier cuenta, también una desactivada o dada de baja (es el
    caso normal).
    """
    if get_user(uid) is None:
        return False
    with closing(_conn(foreign_keys=False)) as conn, conn:
        _purge_user_rows(conn, uid)
        # El historial sobrevive a la purga, pero sin la PII que pudiera esconder
        # en sus notas: se limpia antes de que la fila de `users` desaparezca.
        redact_subject_notes(conn, uid)
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    return True
