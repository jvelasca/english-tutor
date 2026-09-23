"""Cuenta de la sesión: verificación de email y baja autoservicio (V3.81).

Este router es la mitad **del propio alumno** de la Fase 3: lo que puede hacer con
su cuenta sin pedirle permiso a nadie. La otra mitad es la consola de gestión del
lanzador, que tiene la última palabra.

Dos fronteras que conviene tener claras al leerlo:

- **La baja autoservicio no borra nada.** Marca la cuenta como retirada, cierra su
  sesión y sube su época de autenticación; la evidencia se queda intacta y el
  webmaster decide después si la purga. Es la distinción que separa «darme de
  baja» (un derecho) de «borrar mis datos» (una decisión administrativa, con copia
  previa y confirmación por nombre). Las apps que mezclan las dos cosas borran el
  historial de un alumno porque alguien pulsó el botón equivocado.
- **Nada de esto exige SMTP.** La verificación de email es una señal; sin correo
  configurado, el enlace no sale por ningún lado y el webmaster sella la
  verificación a mano desde la consola (`POST /api/admin/users/{id}/verify-email`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dependencies import current_user
from domain import users as user_service
from schemas.users import EmailVerify, UnenrollRequest, User
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
    if _is_expired(sent_at):
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


def _is_expired(sent_at: str) -> bool:
    """¿El token pasó su hora? Un `sent_at` ilegible cuenta como caducado.

    Fail-closed: una fecha que no se puede leer (fila manipulada, reloj raro) no
    habilita la verificación. Lo peor que pasa es pedir un reenvío.
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
    return now - emitted > timedelta(seconds=credentials.EMAIL_TOKEN_TTL_SECONDS)


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
