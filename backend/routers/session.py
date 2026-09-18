"""Sesión del perfil activo (Fase 2 del P0 de identidad, V3.75).

Tres verbos y una idea: la identidad la **firma el servidor**. `POST` la abre
(cookie `et_session`, `HttpOnly`), `GET` la consulta y `DELETE` la cierra.

**Lo que este router NO es:** autenticación. `POST` acepta un `user_id` sin más
credencial (el producto no tiene ninguna: es «sin cuentas, sin contraseñas» por
diseño) y comprueba que el perfil exista. Quien pueda alcanzar la API puede pedir
sesión para otro perfil; lo que ya no puede es **elegir** la identidad en cada
petición ni forjar una sesión sin el secreto del equipo. La Frontera de red
(loopback por defecto, V3.74) es la otra mitad de esta historia.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from domain import users as user_service
from schemas.users import SessionCreate, User
from services import sessions

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
    """Abre sesión para un perfil existente (404 si no existe)."""
    user = await user_service.get_user(body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _set_session_cookie(response, request, sessions.issue(user["id"]))
    return user


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
