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
    """¿La petición llegó por HTTPS? Decide el atributo `Secure` de la cookie.

    `Secure` impide que la cookie viaje por HTTP en claro, pero si se pusiera
    siempre el navegador la **descartaría** en el modo de desarrollo (Vite sirve
    por HTTP), y la sesión no se abriría nunca. Por eso se decide por petición,
    igual que hacía la cookie de perfil que la Fase 2 retiró.
    """
    forwarded = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded.split(",")[0].strip() == "https"


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        sessions.SESSION_COOKIE,
        token,
        max_age=sessions.SESSION_TTL_SECONDS,
        path="/",
        httponly=True,  # fuera del alcance de JS: lo que `et_user_id` no tenía
        samesite="lax",  # el producto no necesita cookies en flujos de terceros
        secure=_is_https(request),
    )


@router.post("/api/session", response_model=User)
async def open_session(
    body: SessionCreate, request: Request, response: Response
) -> dict:
    """Abre sesión para una cuenta existente (404 si no existe).

    V3.81: si la cuenta tiene contraseña, es obligatoria. Los desenlaces son
    distinguibles a propósito, para que la UI sepa qué pintar:

    - `401 PASSWORD_REQUIRED` — la cuenta tiene contraseña y no se envió ninguna.
    - `401 PASSWORD_INVALID`  — llegó una y no cuadra (nunca se dice si «casi»).
    - `429 PASSWORD_THROTTLED` — el freno de `services/credentials.py` está
      activo; incluye `Retry-After` para que la UI pueda contar los segundos.
    - `403 PROFILE_DISABLED` / `403 ACCOUNT_UNENROLLED` — la cuenta está fuera de
      servicio; se comprueba **antes** de gastar KDF y de contar intentos.
    """
    user = await user_service.get_user(body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_service.is_disabled(user):
        raise HTTPException(status_code=403, detail="PROFILE_DISABLED")
    if user_service.is_unenrolled(user):
        raise HTTPException(status_code=403, detail="ACCOUNT_UNENROLLED")

    await _require_password_if_set(body.user_id, body.password)

    epoch = await user_service.get_auth_epoch(body.user_id) or 0
    _set_session_cookie(response, request, sessions.issue(user["id"], epoch=epoch))
    return user


async def _require_password_if_set(uid: str, password: str | None) -> None:
    """Puerta de la contraseña. Sin credencial guardada no hace nada.

    Es deliberado que una cuenta heredada (`password_hash` vacío) siga entrando
    sin pedir nada: la alternativa —cerrar la puerta a todo el mundo al
    actualizar— convertiría una mejora de seguridad en un bloqueo. El precio está
    declarado: hasta que el webmaster asigne credenciales, esas cuentas siguen
    abriéndose nombrando. La consola de gestión las lista precisamente para que
    ese número llegue a cero.
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
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_EDITED,
        note=f"email → {email}",
    )
    return actualizado
