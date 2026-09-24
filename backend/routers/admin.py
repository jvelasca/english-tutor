"""Consola de gestión de cuentas (V3.77, ampliada en V3.81).

Estas rutas son las que **mandan**: crean cuentas, asignan credenciales, verifican
emails a mano, fuerzan bajas, editan datos, purgan evidencia y leen el historial.
Por eso van detrás del candado más estrecho de la app
(`dependencies.require_admin_local`): PIN de administración **y** que la petición
venga del propio equipo. Las dos cosas son necesarias y ninguna basta sola — el PIN
viaja en una cabecera y en una red compartida eso es material expuesto; estar en el
equipo sin el PIN no debería bastar para borrarle el historial a nadie.

**Toda acción que cambia el estado de una cuenta deja una fila en `user_events`**
(quién, qué, cuándo y por qué). No es un adorno de auditoría: es lo que convierte
«control y prioridad» en algo que se puede sostener cuando alguien pregunta por qué
su cuenta está dada de baja.

Lo que **no** hace este router es decidir por su cuenta: resolver una petición,
desactivar o purgar es un acto explícito del webmaster.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

import config
from dependencies import require_admin_local
from domain import profile_requests as requests_service
from domain import users as user_service
from repositories import profile_requests as requests_repo
from schemas.profiles import (
    AdminActivationOut,
    AdminApprovalOut,
    AdminCredentials,
    AdminForceUnenroll,
    AdminHistoryOut,
    AdminPurge,
    AdminSessionOut,
    AdminSmtpOut,
    AdminSmtpTest,
    AdminUserCreate,
    AdminUserEdit,
    AdminUsersOut,
    AdminUserStatus,
    ProfileRequestDecision,
    ProfileRequestOut,
    ProfileRequestsOut,
)
from schemas.users import User
from services import credentials, mailer

router = APIRouter()

# `None` = todas las solicitudes. `pending` es el defecto porque es lo que el
# webmaster tiene que atender; el histórico se pide a propósito.
_STATUS_FILTERS = (None, *requests_repo.STATUSES)


@router.get("/api/admin/profile-requests", response_model=ProfileRequestsOut)
async def list_profile_requests(
    status: str | None = Query(default=requests_repo.STATUS_PENDING),
    _: None = Depends(require_admin_local),
) -> dict:
    if status not in _STATUS_FILTERS:
        raise HTTPException(status_code=422, detail="Estado de solicitud no válido")
    return await requests_service.list_requests(status)


@router.post(
    "/api/admin/profile-requests/{request_id}/approve",
    response_model=AdminApprovalOut,
)
async def approve_profile_request(
    request_id: int,
    body: ProfileRequestDecision,
    request: Request,
    _: None = Depends(require_admin_local),
) -> dict:
    """Aprueba: un alta **crea** la cuenta e **invita**; una baja **desactiva**.

    Purgar no ocurre aquí, ni siquiera cuando la petición era de borrado: es un
    acto aparte, con confirmación por nombre y copia previa. Aprobar una baja es
    «esta cuenta deja de usarse», que es lo que el alumno puede pedir; destruir su
    evidencia es lo que decide el webmaster.

    V3.82: al aprobar un alta, la cuenta nace con el email y el avatar de la
    solicitud y sale la **invitación** (el correo que le pide poner su
    contraseña). `activation_link` vuelve siempre que haya invitación, para que el
    webmaster pueda entregarla a mano cuando no haya SMTP configurado.
    """
    resolved = await requests_service.approve(request_id, note=body.note)
    if resolved is None:
        raise HTTPException(
            status_code=409,
            detail="La solicitud no existe o ya estaba resuelta",
        )
    user = resolved.get("user") or {}
    activation_url, sent = _invite(
        str(request.base_url), resolved.get("activation_token") or "", user
    )
    return {
        "request": resolved["request"],
        "user": user or None,
        "email_sent": sent,
        "activation_link": activation_url,
    }


def _invite(base_url: str, token: str, user: dict) -> tuple[str, bool]:
    """Construye el enlace de invitación y manda el correo si hay a quién.

    Devuelve `(enlace, enviado)`. El enlace se devuelve aunque el correo salga:
    el webmaster puede reenviarlo por su cuenta, y si el envío falla, el enlace
    es la única forma de que la persona active su cuenta (modo híbrido).
    """
    if not token:
        return "", False
    link = mailer.activation_link(base_url.rstrip("/"), token)
    to = str((user or {}).get("email") or "")
    sent = bool(to) and mailer.send(kind=mailer.KIND_ACTIVATION, to=to, link=link)
    return link, sent


@router.post(
    "/api/admin/users/{user_id}/resend-activation",
    response_model=AdminActivationOut,
)
async def resend_user_activation(
    user_id: str,
    request: Request,
    _: None = Depends(require_admin_local),
) -> dict:
    """Reemite la invitación de activación de una cuenta (V3.82).

    Existe porque un correo se pierde, caduca o cae en una bandeja que nadie mira,
    y la alternativa —asignarle una contraseña a mano— es justo lo que esta
    release retira. Emite un token **nuevo** (el anterior deja de valer) y lo
    manda con el mismo texto que la invitación original.
    """
    user = await user_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if not user.get("email"):
        raise HTTPException(
            status_code=409, detail="La cuenta no tiene email al que invitar"
        )
    token = await requests_service.issue_activation(user_id)
    if not token:
        raise HTTPException(status_code=409, detail="No se pudo emitir la invitación")
    link, sent = _invite(str(request.base_url), token, user)
    return {"user": user, "email_sent": sent, "activation_link": link}


@router.post(
    "/api/admin/profile-requests/{request_id}/reject",
    response_model=ProfileRequestOut,
)
async def reject_profile_request(
    request_id: int,
    body: ProfileRequestDecision,
    _: None = Depends(require_admin_local),
) -> dict:
    resolved = await requests_service.reject(request_id, note=body.note)
    if resolved is None:
        raise HTTPException(
            status_code=409,
            detail="La solicitud no existe o ya estaba resuelta",
        )
    return resolved


@router.get("/api/admin/users", response_model=AdminUsersOut)
async def list_admin_users(
    include_disabled: bool = Query(default=True),
    include_test: bool = Query(default=False),
    _: None = Depends(require_admin_local),
) -> dict:
    """Todas las cuentas, fuera de servicio incluidas, con los contadores.

    El lanzador lo pinta junto a las solicitudes, así que devolver los contadores
    aquí ahorra viajes y, sobre todo, evita que los números se pinten de momentos
    distintos y se contradigan.

    `without_password` es la **lista de tareas**: mientras no sea cero, esas
    cuentas heredadas siguen entrando nombrando, que es justo el agujero que esta
    release viene a cerrar. Un contador que se ve es un contador que baja.
    """
    users = await user_service.list_users(
        include_test=include_test, include_disabled=include_disabled
    )
    return {
        "users": users,
        "pending": await requests_service.count_pending(),
        "without_password": sum(1 for u in users if not u.get("has_password")),
        "unverified_email": sum(
            1 for u in users if u.get("email") and not u.get("email_verified")
        ),
    }


@router.post("/api/admin/users", response_model=AdminSessionOut)
async def create_admin_user(
    body: AdminUserCreate,
    _: None = Depends(require_admin_local),
) -> dict:
    """Alta directa del webmaster, ya con credenciales (sin pasar por la cola).

    Si no se da contraseña se **genera una temporal legible** y se marca
    `must_change_password`: el webmaster puede entregarla sin inventarse nada y
    sin llegar a saber nunca cuál será la contraseña definitiva del alumno. La
    temporal viaja en la respuesta y en ningún otro sitio.
    """
    email = credentials.normalize_email(body.email)
    if body.email and not email:
        raise HTTPException(status_code=400, detail="EMAIL_FORMAT")
    if email and await user_service.email_in_use(email):
        raise HTTPException(status_code=409, detail="EMAIL_TAKEN")
    if await user_service.name_in_use(body.name):
        raise HTTPException(status_code=409, detail="USER_NAME_TAKEN")

    temporary = ""
    password = body.password
    if not password:
        temporary = credentials.new_temporary_password()
        password = temporary
    if not credentials.is_valid_password(password):
        raise HTTPException(status_code=400, detail="PASSWORD_FORMAT")

    created = await requests_service.create_profile(
        body.name,
        email=email,
        password_hash=credentials.hash_password(password),
        must_change=True,
    )
    if created is None:
        raise HTTPException(status_code=409, detail="No se pudo crear la cuenta")
    return {"user": created, "temporary_password": temporary if temporary else ""}


@router.patch("/api/admin/users/{user_id}", response_model=User)
async def edit_admin_user(
    user_id: str,
    body: AdminUserEdit,
    _: None = Depends(require_admin_local),
) -> dict:
    """El webmaster edita los datos de una cuenta con la misma autoridad que su dueño.

    Y con una más: puede corregir el **email**, cosa que el alumno solo puede hacer
    con su contraseña delante. Cambiarlo reinicia la verificación (ver
    `requests_service.edit_user`): el sello pertenecía al correo anterior.
    """
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Nada que cambiar")
    updated = await requests_service.edit_user(user_id, fields)
    if updated is None:
        raise HTTPException(
            status_code=409,
            detail="Nombre repetido, email no válido o ya en uso",
        )
    return updated


@router.post("/api/admin/users/{user_id}/status", response_model=User)
async def set_admin_user_status(
    user_id: str,
    body: AdminUserStatus,
    _: None = Depends(require_admin_local),
) -> dict:
    """Activa o desactiva. Reactivar también sirve para una cuenta dada de baja.

    Se separa en dos caminos porque el historial tiene que distinguirlos: una
    cuenta que vuelve desde una baja autoservicio no es lo mismo que una que
    vuelve desde una desactivación, y el alumno que pregunta merece la respuesta
    correcta.
    """
    current = await user_service.get_user(user_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if body.status == "active":
        updated = await requests_service.reenroll(user_id, note="reactivada")
    else:
        updated = await requests_service.set_status(user_id, "disabled")
    if updated is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return updated


@router.post("/api/admin/users/{user_id}/credentials", response_model=AdminSessionOut)
async def set_admin_user_credentials(
    user_id: str,
    body: AdminCredentials,
    _: None = Depends(require_admin_local),
) -> dict:
    """Asigna o **restablece** la credencial: es la recuperación de contraseña.

    El producto no promete un correo de recuperación (puede no haber SMTP), y no
    prometerlo es más honesto que prometerlo y no cumplirlo: quien olvide su
    contraseña se la pide al webmaster, que se la restablece aquí con una temporal
    y `must_change_password`. Reinicia además la verificación del email, porque la
    credencial vuelve a estar en manos de otro.
    """
    temporary = ""
    password = body.password
    if not password:
        temporary = credentials.new_temporary_password()
        password = temporary

    updated = await requests_service.set_credentials(
        user_id, email=body.email, password=password, must_change=True
    )
    if updated is None:
        raise HTTPException(
            status_code=409,
            detail="Email no válido, contraseña con mala forma o email ya en uso",
        )
    return {"user": updated, "temporary_password": temporary}


@router.post("/api/admin/users/{user_id}/verify-email", response_model=User)
async def verify_admin_user_email(
    user_id: str,
    _: None = Depends(require_admin_local),
) -> dict:
    """Sella el email **a mano**: es la mitad del modo híbrido.

    Sin SMTP configurado el enlace de verificación no sale de ningún sitio, así
    que el webmaster confirma —normalmente porque tiene delante a la persona— y la
    cuenta deja de arrastrar el chip de «sin verificar». Sin esto, la verificación
    sería un muro en una app que se promete local.
    """
    updated = await requests_service.verify_email_by_hand(user_id)
    if updated is None:
        raise HTTPException(
            status_code=409, detail="La cuenta no existe o no tiene email"
        )
    return updated


@router.post("/api/admin/users/{user_id}/unenroll", response_model=User)
async def force_admin_user_unenroll(
    user_id: str,
    body: AdminForceUnenroll,
    _: None = Depends(require_admin_local),
) -> dict:
    """**Fuerza** la baja de una cuenta. El motivo es obligatorio.

    No borra nada: la cuenta deja de operar y cierra sus sesiones al instante
    (sube la época de autenticación). El motivo queda en el historial para poder
    explicárselo a quien pregunte — y eso es la diferencia entre una decisión y un
    botón.
    """
    updated = await requests_service.force_unenroll(user_id, body.reason)
    if updated is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return updated


@router.get("/api/admin/users/{user_id}/events", response_model=AdminHistoryOut)
async def admin_user_history(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    _: None = Depends(require_admin_local),
) -> dict:
    """Historial de la cuenta, del más reciente al más antiguo.

    Sobrevive a la purga a propósito (ver `repositories/users.py`): cuando ya no
    queda ninguna fila de `users`, este es el único sitio que responde «¿quién
    borró esto y por qué?».
    """
    return {"events": await requests_service.history(user_id, limit)}


@router.post("/api/admin/users/{user_id}/purge")
async def purge_admin_user(
    user_id: str,
    body: AdminPurge,
    _: None = Depends(require_admin_local),
) -> dict:
    """Purga irreversible, con copia previa. `confirm_name` debe coincidir.

    Un fallo aquí no dice cuál de las condiciones falló (nombre que no cuadra,
    cuenta inexistente, cuenta todavía activa, o que la copia no se pudo escribir)
    a propósito: el lanzador ya sabe qué pidió y ya comprueba el estado antes de
    llamar, así que distinguirlas hacia fuera solo daría un oráculo sobre qué
    cuentas existen.
    """
    result = await requests_service.purge_profile(user_id, body.confirm_name)
    if result is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No se purgó: la cuenta no existe, sigue activa (desactívala o "
                "dale de baja antes), el nombre de confirmación no coincide o la "
                "copia de seguridad no se pudo crear"
            ),
        )
    return result


@router.get("/api/admin/smtp", response_model=AdminSmtpOut)
async def get_smtp_config(_: None = Depends(require_admin_local)) -> dict:
    """Config del correo saliente tal como la ve el backend. **Sin la contraseña.**

    La consola necesita saber si hay SMTP y si hay contraseña guardada, pero el
    valor no sale de aquí por el mismo motivo por el que no sale el del PIN: una
    pantalla que enseña un secreto es una pantalla desde la que se copia.
    """
    settings = config.smtp_settings()
    return {**settings, "has_password": bool(mailer.smtp_password())}


@router.post("/api/admin/smtp/test")
async def test_smtp(
    body: AdminSmtpTest, _: None = Depends(require_admin_local)
) -> dict:
    """Manda un correo de prueba. Devuelve `sent` en vez de lanzar.

    Probar el correo es la única forma de saber que funciona: la alternativa
    —confiar en que el host y el puerto están bien— se descubre fallando cuando
    alguien espera una verificación que nunca llega.
    """
    sent = mailer.send(kind=mailer.KIND_TEST, to=body.to)
    return {
        "sent": sent,
        "error": "" if sent else "SMTP_NOT_CONFIGURED_OR_SEND_FAILED",
    }
