"""Dependencias HTTP compartidas (contexto de usuario local)."""
from __future__ import annotations

from fastapi import Header, HTTPException, Request, UploadFile

import config
from domain import users as user_service
from services import sessions


async def require_admin(
    x_admin_pin: str | None = Header(default=None),
) -> None:
    """Candado local de administración (V1.37; fail-closed desde ADMIN-01 V3.19).

    Secure-by-default: si el PIN de administración está vacío, los endpoints admin
    quedan DESHABILITADOS (401) porque no hay secreto configurado con el que
    autenticarse. Con PIN definido, exige la cabecera `X-Admin-Pin` coincidente.
    Sin OAuth/cloud: separa el rol `student` (aprender) del rol `admin`
    (gestionar audio, copias y, desde V3.77, perfiles). Nunca abre la gestión por
    defecto (fail-open).

    V3.77: el PIN ya no sale solo de una constante sin fuente —
    `config.admin_pin()` resuelve entorno primero—, así que el lanzador puede
    declararlo al arrancar el backend que él mismo lanza.
    """
    admin_pin = config.admin_pin()
    if not admin_pin:
        raise HTTPException(
            status_code=401,
            detail="Administración deshabilitada (configurar ADMIN_PIN)",
        )
    if x_admin_pin != admin_pin:
        raise HTTPException(status_code=401, detail="PIN de administración requerido")


async def require_admin_local(
    request: Request,
    x_admin_pin: str | None = Header(default=None),
) -> None:
    """`require_admin` **más** la frontera de equipo (V3.77).

    La usan las acciones que gestionan perfiles (crear, desactivar, purgar), que
    son las más destructivas de la app: purgar se lleva la evidencia entera de un
    alumno. Dos candados en serie, porque cubren cosas distintas — el PIN es
    «quién eres» y el loopback es «desde dónde» — y ninguno de los dos basta
    solo: un PIN que viaja por la LAN está expuesto, y estar en el equipo sin el
    PIN no debería bastar para borrarle el historial a nadie.

    Fail-closed en las dos direcciones: sin PIN configurado no pasa (lo decide
    `require_admin`), y con el PIN correcto pero desde fuera del equipo tampoco.
    """
    await require_admin(x_admin_pin=x_admin_pin)
    client_host = request.client.host if request.client else None
    if not config.is_admin_loopback_host(client_host):
        raise HTTPException(
            status_code=403,
            detail="La administración de perfiles solo se ejerce desde el equipo",
        )


async def current_user(request: Request) -> dict:
    """Resuelve el perfil activo desde la **sesión firmada** (V3.75, Fase 2 del P0).

    Es el **único** sitio donde la API decide quién eres: los 138 usos de esta
    dependencia en los 20 routers no cambian. 401 `SESSION_REQUIRED` si no hay
    cookie o la firma no cuadra; 404 si el perfil de una sesión válida ya no
    existe (mismo contrato que antes).

    V3.81: además de la firma se comprueba la **época de autenticación**. Es lo
    que hace que cambiar la contraseña o forzar una baja cierren las sesiones
    abiertas de esa cuenta **en la siguiente petición**, no cuando caduque la
    cookie (un año). Se responde 401 `SESSION_STALE` y no 403 para que la UI sepa
    que lo que toca es volver a entrar, no pedir permiso.

    El `?user_id=` que aceptaba hasta V3.74 **ya no se lee**: era la
    vulnerabilidad —cualquiera que alcanzara la API podía pedir los datos de otro
    perfil con solo cambiar un parámetro—, y dejarlo como respaldo habría sido
    cambiar la forma del arreglo sin arreglarlo (`PLAN-P0-IDENTIDAD.md` §4).
    """
    resolved = sessions.verify_session(request.cookies.get(sessions.SESSION_COOKIE))
    if resolved is None:
        raise HTTPException(status_code=401, detail="SESSION_REQUIRED")
    user_id, epoch = resolved
    user = await user_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    current_epoch = await user_service.get_auth_epoch(user_id)
    if current_epoch is None or current_epoch != epoch:
        # Sesión de una credencial que ya no es la vigente: la contraseña cambió
        # o la cuenta se dio de baja. Es un 401 porque lo que toca es volver a
        # entrar, no pedir permiso.
        raise HTTPException(status_code=401, detail="SESSION_STALE")
    if user_service.is_disabled(user):
        # V3.77: una cuenta desactivada deja de poder usar su sesión, aunque la
        # cookie siga siendo válida — desactivar tiene que surtir efecto **ya**,
        # no cuando caduque la sesión. Se distingue de `SESSION_REQUIRED` para
        # que la UI pueda decir por qué y no parezca que se ha caído la conexión.
        raise HTTPException(status_code=403, detail="PROFILE_DISABLED")
    if user_service.is_unenrolled(user):
        # V3.81: la baja autoservicio. Mismo efecto que desactivar, distinto
        # motivo: aquí el que decidió fue el propio alumno.
        raise HTTPException(status_code=403, detail="ACCOUNT_UNENROLLED")
    if (
        user_service.is_password_change_due(user)
        and request.url.path not in _PASSWORD_CHANGE_ALLOWED_PATHS
    ):
        # V3.81: la contraseña temporal del webmaster obliga a cambiarla **antes**
        # de usar nada. La exención es literal y corta (la propia sesión y el
        # cambio de contraseña) porque todo lo demás es «usar la app», y una
        # contraseña que sobrevive al primer acceso deja de ser temporal.
        raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
    return user


# Lo único que se puede hacer con una contraseña temporal puesta: consultar quién
# eres (para que la UI sepa qué pedirte) y cambiarla. Se declara aquí arriba, junto
# a la comprobación que lo usa, y no disperso por los routers.
_PASSWORD_CHANGE_ALLOWED_PATHS = frozenset({"/api/session", "/api/session/password"})


async def current_user_optional(request: Request) -> dict | None:
    """Igual que `current_user`, pero **sin** sesión resuelve `None` en vez de 401:
    para los endpoints que saben funcionar sin perfil (su semántica no cambia).

    V3.81: también resuelve `None` —y no un error— cuando la sesión existe pero su
    época quedó atrás o la cuenta está fuera de servicio. Para estos endpoints el
    resultado es el mismo que no tener sesión: no hay datos que atribuir a nadie, y
    devolver 403 haría que un chat o una lectura sin perfil fallaran por un estado
    de cuenta que no les afecta.

    **El 404 sí se propaga**: una sesión válida cuyo usuario ya no existe (se purgó
    desde la consola) es un fallo distinto —la identidad que el cliente cree tener
    ha dejado de existir— y su contrato está fijado por tests. Convertirlo en
    `None` sería contar dos cosas distintas con la misma moneda.
    """
    try:
        return await current_user(request)
    except HTTPException as exc:
        if exc.status_code in (401, 403):
            return None
        raise


_ALLOWED_AUDIO_TYPES = {
    "application/octet-stream",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-wav",
}


def _content_type_ok(content_type: str | None) -> bool:
    if not content_type:
        return True
    base = content_type.split(";")[0].strip().lower()
    return base.startswith("audio/") or base in _ALLOWED_AUDIO_TYPES


async def read_audio_limited(file: UploadFile) -> bytes:
    """Lee un audio con límite de tamaño y tipo. 415 si el tipo no es audio, 413 si
    excede."""
    if not _content_type_ok(file.content_type):
        raise HTTPException(status_code=415, detail="Formato de audio no soportado")
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > config.MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio demasiado grande")
    return bytes(data)
