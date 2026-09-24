"""Cuenta de la sesión: activación, recuperación, verificación y baja (V3.81–V3.82).

Este router reúne lo que la persona hace con su cuenta **sin pedirle permiso a
nadie**. La otra mitad —autorizar altas, reemitir invitaciones, verificar a mano,
forzar bajas y purgar— es la consola de gestión del lanzador, y tiene la última
palabra.

V3.82 añade aquí las dos piezas que hacen que el alta sea **profesional**: la
**activación** (`/api/account/activate`, el segundo acto del alta —el webmaster
autorizó y aquí la persona elige *su* contraseña, así que nadie más la conoce
nunca, ni siquiera de forma provisional) y la **recuperación**
(`/api/account/forgot-password` + `/api/account/reset-password`, para olvidarse de
la contraseña sin llamar al webmaster). Las tres rutas de token —activación,
restablecimiento y verificación— son **sin sesión** a propósito: el enlace puede
abrirse en otro navegador.

Dos fronteras que conviene tener claras al leerlo:

- **La baja autoservicio no borra nada.** Marca la cuenta como retirada, cierra su
  sesión y sube su época de autenticación; la evidencia se queda intacta y el
  webmaster decide después si la purga. Es la distinción que separa «darme de
  baja» (un derecho) de «borrar mis datos» (una decisión administrativa, con copia
  previa y confirmación por nombre). Las apps que mezclan las dos cosas borran el
  historial de un alumno porque alguien pulsó el botón equivocado.
- **Nada de esto exige SMTP.** El correo es un aviso: sin correo configurado no se
  abre ninguna conexión, el token se emite igual y el enlace se entrega a mano
  (modo híbrido), y el webmaster sella la verificación desde la consola
  (`POST /api/admin/users/{id}/verify-email`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dependencies import current_user
from domain import users as user_service
from schemas.users import (
    AccountActivate,
    EmailVerify,
    ForgotPasswordRequest,
    PasswordReset,
    UnenrollRequest,
    User,
)
from services import credentials, mailer, sessions

router = APIRouter()


def _base_url(request: Request) -> str:
    """Origen con el que construir el enlace del correo.

    Se toma el de **la petición** en vez de una constante: en desarrollo el alta
    llega por el proxy de Vite y en producto por el propio backend, y el enlace
    tiene que apuntar a donde está la app, no a donde el desarrollador cree.
    """
    return str(request.base_url).rstrip("/")


@router.post("/api/account/verify", response_model=User)
async def verify_email(body: EmailVerify) -> dict:
    """Confirma el email con el token del enlace. **Sin sesión**, a propósito.

    El enlace puede abrirse en otro navegador, en otro perfil del equipo o incluso
    en el móvil: exigir la sesión ahí haría que el enlace del correo no sirviera
    justo cuando más falta hace (alguien que quiere confirmar desde donde leyó el
    correo). Lo que autoriza no es la sesión, es el **token**: 256 bits de
    entropía, de un solo uso, guardado hasheado y con caducidad de una hora.
    """
    user = await user_service.find_by_email_token(
        credentials.hash_email_token(body.token)
    )
    if user is None:
        raise HTTPException(status_code=400, detail="VERIFY_TOKEN_INVALID")

    verification = await user_service.get_email_verification(user["id"])
    if verification is None:
        raise HTTPException(status_code=400, detail="VERIFY_TOKEN_INVALID")
    _, sent_at = verification
    if _is_expired(sent_at, credentials.EMAIL_TOKEN_TTL_SECONDS):
        raise HTTPException(status_code=400, detail="VERIFY_TOKEN_EXPIRED")

    actualizado = await user_service.mark_email_verified(user["id"])
    if actualizado is None:
        raise HTTPException(status_code=400, detail="VERIFY_TOKEN_INVALID")
    # La nota no repite el correo: `user_events` sobrevive a la purga y el
    # email es justo el dato que la purga tiene que dejar de conservar.
    await user_service.record_event(
        subject_id=user["id"],
        subject_name=user["name"],
        action=user_service.EVENT_EMAIL_VERIFIED,
        note="email verificado",
    )
    return actualizado


def _is_expired(sent_at: str, ttl_seconds: int) -> bool:
    """¿El token pasó su tiempo? Un `sent_at` ilegible cuenta como caducado.

    Fail-closed: una fecha que no se puede leer (fila manipulada, reloj raro) no
    habilita el canje. Lo peor que pasa es pedir un reenvío.

    V3.82: el TTL se recibe en vez de leer una constante. Verificación y
    restablecimiento caducan en una hora; la invitación de activación dura una
    semana, porque quien la recibe tiene que elegir contraseña y puede tardar.
    """
    if not sent_at:
        return True
    try:
        emitted = datetime.fromisoformat(sent_at)
    except ValueError:
        return True
    if emitted.tzinfo is None:
        emitted = emitted.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return now - emitted > timedelta(seconds=ttl_seconds)


@router.post("/api/account/activate", response_model=User)
async def activate_account(
    body: AccountActivate, request: Request, response: Response
) -> dict:
    """Pone la contraseña desde el enlace de **invitación** (V3.82). Sin sesión.

    Es el segundo acto del alta: el webmaster autorizó (Fase B) y aquí la propia
    persona **elige su contraseña**. Ni el webmaster ni la BD han visto nunca una
    contraseña provisional, y ese es el punto: no hay nada que interceptar.

    Qué comprueba, en orden: que el token exista (hasheado), que no haya caducado
    (7 días) y que la contraseña cumpla la política. Al canjearlo consume el token
    (de un solo uso), **marca el email como verificado** —pulsar el enlace prueba
    la posesión del correo, así que pedir además un segundo enlace sería pedir dos
    veces lo mismo— y fija la contraseña con `set_password_hash`, que es lo que
    sube `auth_epoch` y deja fuera cualquier sesión abierta.

    Deja la sesión abierta: quien acaba de poner su contraseña no tiene que
    volver a escribirla para entrar (y ya la tiene delante, no se está
    adivinando).
    """
    user = await user_service.find_by_activation_token(
        credentials.hash_token(body.token)
    )
    if user is None:
        raise HTTPException(status_code=400, detail="ACTIVATION_TOKEN_INVALID")

    activation = await user_service.get_activation(user["id"])
    if activation is None or not activation[0]:
        raise HTTPException(status_code=400, detail="ACTIVATION_TOKEN_INVALID")
    if _is_expired(activation[1], credentials.ACTIVATION_TOKEN_TTL_SECONDS):
        raise HTTPException(status_code=400, detail="ACTIVATION_TOKEN_EXPIRED")

    if not credentials.is_valid_password(body.password):
        raise HTTPException(status_code=400, detail="PASSWORD_FORMAT")

    uid = user["id"]
    await user_service.mark_activated(uid)
    await user_service.set_password_hash(
        uid, credentials.hash_password(body.password), must_change=False
    )
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_ACTIVATED,
        actor="alumno",
    )
    epoch = await user_service.get_auth_epoch(uid) or 0
    sessions.set_cookie(
        response,
        sessions.issue(uid, epoch=epoch),
        secure=sessions.is_https(request),
    )
    actualizado = await user_service.get_user(uid)
    if actualizado is None:  # carrera con un borrado
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return actualizado


@router.post("/api/account/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest, request: Request
) -> dict:
    """«Olvidé mi contraseña» (V3.82). **Sin sesión**. Responde 200 siempre.

    La respuesta es idéntica exista o no la cuenta, esté activa o no: si dijera
    «ese correo no está registrado», el formulario sería un oráculo para cosechar
    qué correos tienen cuenta. Por eso no hay ni un `if` que cambie el cuerpo;
    lo que cambia es lo que ocurre por dentro.

    Si la cuenta existe, está activa y tiene email, se emite un token de
    restablecimiento (de un solo uso, una hora) y se manda el correo. Si no, no se
    hace nada — y el tiempo de respuesta es el mismo porque el envío es
    fail-closed y no abre conexión cuando no hay SMTP.
    """
    email = credentials.normalize_email(body.email)
    user = await user_service.find_by_email(email) if email else None
    if user is not None and user.get("status") == user_service.STATUS_ACTIVE:
        token = credentials.new_password_reset_token()
        if await user_service.set_password_reset(
            user["id"], credentials.hash_token(token)
        ):
            mailer.send(
                kind=mailer.KIND_RESET,
                to=str(user.get("email") or ""),
                link=mailer.password_reset_link(_base_url(request), token),
            )
            await user_service.record_event(
                subject_id=user["id"],
                subject_name=user["name"],
                action=user_service.EVENT_PASSWORD_RESET,
                actor="alumno",
                note="solicitado el restablecimiento",
            )
    return {"sent": True}


@router.post("/api/account/reset-password", response_model=User)
async def reset_password(
    body: PasswordReset, request: Request, response: Response
) -> dict:
    """Elige contraseña nueva con el token del correo (V3.82). **Sin sesión.**

    Token de un solo uso con caducidad de una hora. Al aplicarlo: se consume el
    token, se sube `auth_epoch` (con `set_password_hash`), y con ello **dejan de
    valer todas las sesiones abiertas** de esa cuenta. Eso último es la mitad del
    valor de la función: si alguien pidió el restablecimiento porque sospechaba que
    otro tenía su contraseña, el otro se queda fuera en el mismo acto.
    """
    user = await user_service.find_by_password_reset_token(
        credentials.hash_token(body.token)
    )
    if user is None:
        raise HTTPException(status_code=400, detail="RESET_TOKEN_INVALID")

    reset = await user_service.get_password_reset(user["id"])
    if reset is None or not reset[0]:
        raise HTTPException(status_code=400, detail="RESET_TOKEN_INVALID")
    if _is_expired(reset[1], credentials.PASSWORD_RESET_TTL_SECONDS):
        raise HTTPException(status_code=400, detail="RESET_TOKEN_EXPIRED")

    if not credentials.is_valid_password(body.password):
        raise HTTPException(status_code=400, detail="PASSWORD_FORMAT")

    uid = user["id"]
    await user_service.clear_password_reset(uid)
    await user_service.set_password_hash(
        uid, credentials.hash_password(body.password), must_change=False
    )
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_PASSWORD_CHANGED,
        actor="alumno",
        note="restablecida por el alumno",
    )
    epoch = await user_service.get_auth_epoch(uid) or 0
    sessions.set_cookie(
        response,
        sessions.issue(uid, epoch=epoch),
        secure=sessions.is_https(request),
    )
    actualizado = await user_service.get_user(uid)
    if actualizado is None:  # carrera con un borrado
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return actualizado


@router.post("/api/account/resend-verification")
async def resend_verification(
    request: Request, user: dict = Depends(current_user)
) -> dict:
    """Emite un token nuevo y manda el enlace **si hay SMTP configurado**.

    Devuelve `sent: false` cuando no hay correo, y eso **no es un error**: es el
    modo híbrido. La UI lo dice tal cual («el webmaster tiene que confirmarlo») en
    vez de fingir un envío que no ha ocurrido.
    """
    uid = user["id"]
    email = str(user.get("email") or "")
    if not email:
        raise HTTPException(status_code=400, detail="EMAIL_MISSING")
    if user.get("email_verified"):
        return {"sent": False, "reason": "ALREADY_VERIFIED"}

    token = credentials.new_email_token()
    if not await user_service.set_email_verification(
        uid, credentials.hash_email_token(token)
    ):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    sent = mailer.send(
        kind=mailer.KIND_VERIFICATION,
        to=email,
        link=mailer.verification_link(_base_url(request), token),
    )
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_EMAIL_VERIFIED,
        note="reenvío de verificación" if sent else "reenvío sin SMTP",
    )
    return {"sent": sent, "reason": "" if sent else "SMTP_NOT_CONFIGURED"}


@router.post("/api/account/unenroll")
async def unenroll(
    body: UnenrollRequest,
    request: Request,
    response: Response,
    user: dict = Depends(current_user),
) -> dict:
    """Baja **autoservicio**: la cuenta deja de operar y no se borra nada.

    Exige la contraseña aunque ya haya sesión. Sin ella, bastaría con pasar por
    delante de un equipo con la sesión abierta para dar de baja a quien esté
    dentro — y una baja que se puede provocar desde fuera no es un derecho del
    alumno, es una vulnerabilidad con buenos modales.

    Lo que **no** hace: no borra evidencia, no borra la cuenta, no libera el
    nombre (la cuenta sigue existiendo, dada de baja). El webmaster puede
    reactivarla; si lo que se quiere es el borrado definitivo, eso es la purga, con
    copia previa y confirmación por nombre.
    """
    uid = user["id"]
    stored = await user_service.get_password_hash(uid) or ""
    if stored:
        espera = credentials.seconds_to_wait(uid)
        if espera > 0:
            raise HTTPException(
                status_code=429,
                detail="PASSWORD_THROTTLED",
                headers={"Retry-After": str(int(espera) + 1)},
            )
        if not credentials.verify_password(stored, body.password):
            credentials.note_failure(uid)
            raise HTTPException(status_code=401, detail="PASSWORD_INVALID")
        credentials.note_success(uid)

    actualizado = await user_service.set_unenrolled(uid, enrolled=False)
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await user_service.record_event(
        subject_id=uid,
        subject_name=user["name"],
        action=user_service.EVENT_UNENROLLED,
        note="baja autoservicio",
    )
    # La baja sube la época, así que la sesión ya no vale; se retira la cookie
    # aquí para que el navegador no la siga mandando (y el 403 no aparezca en
    # cada petición de una app que el alumno cree cerrada).
    response.delete_cookie(
        sessions.SESSION_COOKIE, path="/", httponly=True, samesite="lax"
    )
    return {"unenrolled": True, "user": actualizado}
