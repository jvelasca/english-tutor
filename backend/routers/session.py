"""Sesión del perfil activo (Fase 2 del P0 de identidad, V3.75; PIN en V3.76).

Cuatro verbos y una idea: la identidad la **firma el servidor**. `POST` la abre
(cookie `et_session`, `HttpOnly`), `GET` la consulta, `PUT`/`DELETE` sobre
`/api/session/pin` ponen y retiran el PIN del perfil de la sesión.

**Lo que este router NO es:** autenticación de persona. `POST` acepta un
`user_id` y, **si el perfil tiene PIN**, exige además ese PIN (401
`PIN_REQUIRED`/`PIN_INVALID`); si no lo tiene, la puerta sigue abierta como
siempre —es «sin cuentas, sin contraseñas» por diseño, y el PIN es una
mitigación **opcional que el alumno activa**, no un cambio de ese contrato—.
Quien pueda alcanzar la API puede pedir sesión para un perfil sin PIN; lo que ya
no puede es **elegir** la identidad en cada petición ni forjar una sesión sin el
secreto del equipo. La Frontera de red (loopback por defecto, V3.74) es la otra
mitad de esta historia.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dependencies import current_user
from domain import users as user_service
from schemas.users import PinSet, SessionCreate, User
from services import pins, sessions

router = APIRouter()


def _is_https(request: Request) -> bool:
    """¿La petición llegó por HTTPS? Decide el atributo `Secure` de la cookie.

    `Secure` impide que la cookie viaje por HTTP en claro, pero si se pusiera
    siempre el navegador la **descartaría** en el modo de desarrollo (Vite sirve
    por HTTP), y la sesión no se abriría nunca. Por eso se decide por petición,
    igual que hacía la cookie de perfil que esta fase retira.
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
    """Abre sesión para un perfil existente (404 si no existe).

    V3.76: si el perfil tiene PIN, la petición debe traerlo. Los tres desenlaces
    son distinguibles a propósito, para que la UI sepa qué pintar:

    - `401 PIN_REQUIRED` — el perfil tiene PIN y la petición no lo traía.
    - `401 PIN_INVALID`  — llegó un PIN y no cuadra (nunca se dice si «casi»).
    - `429 PIN_THROTTLED` — el freno de `services/pins.py` está activo; incluye
      `Retry-After` para que la UI pueda contar los segundos.
    """
    user = await user_service.get_user(body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # V3.77: un perfil desactivado no abre sesión. Se comprueba **antes** del PIN
    # a propósito: no tiene sentido gastar KDF en un perfil fuera de servicio, y
    # el freno por perfil no debe contar intentos de algo que no puede entrar.
    if user_service.is_disabled(user):
        raise HTTPException(status_code=403, detail="PROFILE_DISABLED")

    await _require_pin_if_set(body.user_id, body.pin)

    _set_session_cookie(response, request, sessions.issue(user["id"]))
    return user


async def _require_pin_if_set(uid: str, pin: str | None) -> None:
    """Puerta del PIN. Sin PIN guardado no hace nada (compatibilidad total)."""
    stored = await user_service.get_pin_hash(uid)
    if not stored:
        # Perfil sin PIN: `has_pin` es False y esta rama es la de siempre. Un
        # `pin` enviado de más se ignora en vez de fallar: no hay nada que
        # comprobar y responder 401 aquí sería castigar un campo inocuo.
        return

    espera = pins.seconds_to_wait(uid)
    if espera > 0:
        raise HTTPException(
            status_code=429,
            detail="PIN_THROTTLED",
            headers={"Retry-After": str(int(espera) + 1)},
        )
    if pin is None:
        raise HTTPException(status_code=401, detail="PIN_REQUIRED")
    if not pins.verify_pin(stored, pin):
        pins.note_failure(uid)
        raise HTTPException(status_code=401, detail="PIN_INVALID")
    pins.note_success(uid)


@router.get("/api/session", response_model=User)
async def read_session(request: Request) -> dict:
    """El perfil de la sesión (401 `SESSION_REQUIRED` si no hay sesión válida)."""
    user_id = sessions.verify(request.cookies.get(sessions.SESSION_COOKIE))
    if user_id is None:
        raise HTTPException(status_code=401, detail="SESSION_REQUIRED")
    user = await user_service.get_user(user_id)
    if user is None:
        # El perfil se borró con la sesión abierta: se responde igual que en el
        # resto de la API (404), no se finge una sesión válida.
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user_service.is_disabled(user):
        # V3.77: desactivado es «no hay sesión que valga»; la UI desmonta la
        # sesión y vuelve a la puerta de perfil, que ya no lo lista.
        raise HTTPException(status_code=403, detail="PROFILE_DISABLED")
    return user


@router.delete("/api/session")
async def close_session(request: Request, response: Response) -> dict:
    """Cierra sesión: caduca la cookie en el navegador."""
    response.delete_cookie(
        sessions.SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
    )
    return {"closed": True}


@router.put("/api/session/pin", response_model=User)
async def set_pin(body: PinSet, user: dict = Depends(current_user)) -> dict:
    """Pone, cambia o retira el PIN del perfil **de la sesión** (V3.76).

    Solo el tuyo: no hay `{id}` en la ruta, así que no existe la forma de tocar
    el PIN de otro perfil ni por descuido. Cambiar o retirar un PIN existente
    exige el anterior, con la misma puerta y el mismo freno que abrir sesión: sin
    eso, quien se siente delante de un equipo con sesión abierta podría poner su
    propio PIN y quedarse el perfil.

    `new_pin` vacío retira el PIN (el perfil vuelve a entrar sin credencial).
    """
    await _require_pin_if_set(user["id"], body.current_pin)

    if body.new_pin == "":
        await user_service.set_pin_hash(user["id"], "")
    else:
        if not pins.is_valid_pin(body.new_pin):
            raise HTTPException(status_code=400, detail="PIN_FORMAT")
        await user_service.set_pin_hash(user["id"], pins.hash_pin(body.new_pin))

    actualizado = await user_service.get_user(user["id"])
    if actualizado is None:  # carrera con un borrado: mismo contrato que el resto
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return actualizado
