"""Sesión de la cuenta activa (Fase 2 del P0, V3.75; credencial real en V3.81).

Cuatro verbos y una idea: la identidad la **firma el servidor**. `POST` la abre
(cookie `et_session`, `HttpOnly`), `GET` la consulta, `PUT /password` cambia la
credencial y `DELETE` la cierra.

**Lo que este router ya no es (V3.81).** Hasta V3.80 `POST` aceptaba un `user_id`
y, si la cuenta tenía PIN, además ese PIN. Eso era una llave de puerta, no una
credencial: cualquiera con acceso a la API abría sesión como cualquier cuenta sin
PIN. Ahora, si la cuenta tiene contraseña, la petición **tiene que traerla** y se
verifica contra un hash PBKDF2 con sal por cuenta y freno de intentos. La
compatibilidad se mantiene para las cuentas heredadas (`has_password` falso), que
es el estado en el que quedan los usuarios anteriores a esta release hasta que el
webmaster les asigne credenciales desde la consola de gestión — así nadie queda
fuera de la app por actualizar.

El cierre de sesión sigue siendo `DELETE /api/session` (existe desde V3.75 y es
lo que llama `closeSession()` en el frontend): no se añade un `POST
/api/session/logout` porque serían dos rutas para el mismo efecto.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dependencies import current_user
from domain import users as user_service
from schemas.users import EmailChange, PasswordChange, SessionCreate, User
from services import credentials, sessions

router = APIRouter()


def _is_https(request: Request) -> bool:
    """Compatibilidad: la política vive en `services.sessions.is_https`."""
    return sessions.is_https(request)


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    sessions.set_cookie(response, token, secure=sessions.is_https(request))


@router.post("/api/session", response_model=User)
async def open_session(
    body: SessionCreate, request: Request, response: Response
) -> dict:
    """Abre sesión con **email + contraseña** (V3.82).

    Lo que cambió respecto a V3.81 y por qué: antes se entraba nombrando una
    cuenta (`user_id`) y la contraseña era opcional si la cuenta no tenía. Eso
    hacía posible suplantar a cualquiera con solo saber su nombre. Ahora la
    identidad se demuestra con el email y una contraseña que **siempre** existe:
    una cuenta sin contraseña no es una cuenta, es una invitación pendiente.

    Desenlaces, y qué puede aprender quien llama de cada uno:

    - `401 INVALID_CREDENTIALS` — email inexistente o contraseña que no cuadra;
      **el mismo** para los dos, para que el login no sirva para averiguar qué
      correos tienen cuenta.
    - `403 ACCOUNT_NOT_ACTIVATED` — la cuenta existe y está autorizada pero
      todavía no tiene contraseña: se le dice a quien **ya ha demostrado conocer
      el email**, para que sepa que su invitación está en el correo. Es un mensaje
      de ayuda, no un oráculo: no revela nada que el email no revelara ya.
    - `429 PASSWORD_THROTTLED` — freno de intentos, con `Retry-After`.
    - `403 PROFILE_DISABLED` / `403 ACCOUNT_UNENROLLED` — la cuenta está fuera de
      servicio; se comprueba **antes** de gastar KDF y de contar intentos.
    """
    email = credentials.normalize_email(body.email)
    user = await user_service.find_by_email(email) if email else None
    if user is None:
        # Mismo cuerpo que una contraseña incorrecta: enumerar cuentas no puede
        # ser tan barato como probar correos.
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    if user_service.is_disabled(user):
        raise HTTPException(status_code=403, detail="PROFILE_DISABLED")
    if user_service.is_unenrolled(user):
        raise HTTPException(status_code=403, detail="ACCOUNT_UNENROLLED")

    stored = await user_service.get_password_hash(user["id"]) or ""
    if not stored:
        # Invitación pendiente: sin contraseña no hay entrada. Esto es el cierre
        # **por construcción** del agujero que el gate de G0 vigilaba.
        raise HTTPException(status_code=403, detail="ACCOUNT_NOT_ACTIVATED")

    uid = user["id"]
    espera = credentials.seconds_to_wait(uid)
    if espera > 0:
        raise HTTPException(
            status_code=429,
            detail="PASSWORD_THROTTLED",
            headers={"Retry-After": str(int(espera) + 1)},
        )
    if not credentials.verify_password(stored, body.password):
        credentials.note_failure(uid)
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    credentials.note_success(uid)

    epoch = await user_service.get_auth_epoch(uid) or 0
    sessions.set_cookie(
        response,
        sessions.issue(uid, epoch=epoch),
        secure=sessions.is_https(request),
    )
    return user


async def _require_password_if_set(uid: str, password: str | None) -> None:
    """Puerta de la contraseña para acciones sobre la cuenta **de la sesión**.

    V3.82: la entrada ya no la usa —`open_session` demuestra la credencial por
    email—, pero sigue siendo la comprobación de las acciones destructivas
    (cambiar la contraseña, darse de baja): que la sesión esté abierta no basta
    para darse de baja, hay que volver a demostrar la contraseña. Sin eso, pasar
    por delante de un equipo con la sesión abierta bastaría para dar de baja a
    quien esté dentro.

    Si la cuenta no tiene contraseña (una invitación a medias) no hay nada que
    comprobar: las acciones que la usan ya exigen sesión, y sin contraseña no hay
    sesión posible.
    """
    stored = await user_service.get_password_hash(uid)
    if not stored:
        return

    espera = credentials.seconds_to_wait(uid)
    if espera > 0:
        raise HTTPException(
            status_code=429,
            detail="PASSWORD_THROTTLED",
            headers={"Retry-After": str(int(espera) + 1)},
        )
    if password is None:
        raise HTTPException(status_code=401, detail="PASSWORD_REQUIRED")
    if not credentials.verify_password(stored, password):
        credentials.note_failure(uid)
        raise HTTPException(status_code=401, detail="PASSWORD_INVALID")
    credentials.note_success(uid)


@router.get("/api/session", response_model=User)
async def read_session(user: dict = Depends(current_user)) -> dict:
    """La cuenta de la sesión.

    Delegar en `current_user` no es un atajo: es la garantía de que este endpoint
    y el resto de la API **contestan lo mismo** sobre quién eres (401 sin sesión,
    401 `SESSION_STALE` si la credencial cambió, 404 si la cuenta ya no existe,
    403 si está desactivada o dada de baja). Antes tenía su propia copia de esas
    reglas, y esa duplicación es justo lo que se desincroniza.
    """
    return user


@router.delete("/api/session")
async def close_session(request: Request, response: Response) -> dict:
    """Cierra sesión: caduca la cookie en el navegador.

    No hace falta consultar el servidor para esto: el token es autocontenido y
    caduca solo. Borrar la cookie es suficiente y es lo que la UI necesita en el
    caso normal («Salir»).
    """
    response.delete_cookie(
        sessions.SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
    )
    return {"closed": True}


@router.put("/api/session/password", response_model=User)
async def change_password(
    body: PasswordChange,
    request: Request,
    response: Response,
    user: dict = Depends(current_user),
) -> dict:
    """Cambia la contraseña de la cuenta **de la sesión**.

    Solo la tuya: no hay `{id}` en la ruta, así que no existe la forma de tocar
    la credencial de otra cuenta ni por descuido. Si ya había contraseña hay que
    demostrar la actual, con la misma puerta y el mismo freno que abrir sesión:
    sin eso, quien se siente delante de un equipo con la sesión abierta podría
    poner su propia contraseña y quedarse la cuenta.

    Al cambiarla sube la época de autenticación, así que **todas** las sesiones
    abiertas de esa cuenta dejan de valer… incluida esta. Por eso se reemite la
    cookie aquí mismo: quien acaba de cambiar su contraseña no debe verse fuera
    de su propia app (y si el cambio lo hizo porque sospechaba de otro, el otro
    sí se queda fuera, que es el objetivo).
    """
    uid = user["id"]
    stored = await user_service.get_password_hash(uid) or ""
    if stored:
        await _require_password_if_set(uid, body.current_password)

    if not credentials.is_valid_password(body.new_password):
        raise HTTPException(status_code=400, detail="PASSWORD_FORMAT")

    await user_service.set_password_hash(
        uid, credentials.hash_password(body.new_password), must_change=False
    )
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_PASSWORD_CHANGED,
    )

    epoch = await user_service.get_auth_epoch(uid) or 0
    _set_session_cookie(response, request, sessions.issue(uid, epoch=epoch))
    actualizado = await user_service.get_user(uid)
    if actualizado is None:  # carrera con un borrado: mismo contrato que el resto
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return actualizado


@router.put("/api/session/email", response_model=User)
async def change_email(
    body: EmailChange, user: dict = Depends(current_user)
) -> dict:
    """Cambia el email de la cuenta **de la sesión**.

    Exige la contraseña aunque ya haya sesión: apuntar la verificación a un correo
    distinto es la forma de quedarse una cuenta (se pide el restablecimiento al
    email nuevo). Un email nuevo siempre nace **sin verificar**.
    """
    uid = user["id"]
    stored = await user_service.get_password_hash(uid) or ""
    if stored:
        await _require_password_if_set(uid, body.password)

    email = credentials.normalize_email(body.email)
    if not email:
        raise HTTPException(status_code=400, detail="EMAIL_FORMAT")
    if await user_service.email_in_use(email, exclude_uid=uid):
        raise HTTPException(status_code=409, detail="EMAIL_TAKEN")

    actualizado = await user_service.set_email(uid, email)
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    # El historial sobrevive a la purga, así que no se anota el correo nuevo
    # (PII): se anota que **hubo** un cambio de correo. El valor vive en la fila
    # de `users`, que la purga borra.
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_EDITED,
        note="email actualizado",
    )
    return actualizado
