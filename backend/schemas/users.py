"""Esquemas Pydantic de usuarios (perfiles locales)."""
from __future__ import annotations

from pydantic import BaseModel, Field

# Límite para la imagen de avatar (data URL). Suficiente para una miniatura
# redimensionada en el cliente (~128 px) y evita abusos de tamaño en la BD.
MAX_AVATAR_IMAGE_CHARS = 500_000


class User(BaseModel):
    id: str
    name: str
    avatar_color: str = ""
    avatar_emoji: str = ""
    avatar_image: str = ""
    # V3.52.1: perfil de PRUEBA (tests visuales). Nunca aparece en el selector
    # de la app; se expone para que los tests puedan localizar y limpiar el suyo.
    is_test: bool = False
    # V3.76 (Fase 3 del P0): ¿este perfil tiene PIN? La puerta necesita saber si
    # preguntarlo. Se expone el **booleano**, jamás el hash.
    has_pin: bool = False
    # V3.77: `active` | `disabled`. La app y el selector solo ven perfiles
    # activos (el repositorio los filtra), así que este campo lo lee el lanzador
    # para poder mostrar y reactivar los desactivados.
    status: str = "active"
    created_at: str


class UserCreate(BaseModel):
    # `max_length` alineado con `UserUpdate`: `POST /api/users` no exige
    # credencial, así que sin tope se pueden crear nombres de tamaño arbitrario.
    name: str = Field(min_length=1, max_length=80)
    # Solo los tests lo marcan; la app siempre crea perfiles reales.
    is_test: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_color: str | None = Field(default=None, max_length=32)
    avatar_emoji: str | None = Field(default=None, max_length=16)
    avatar_image: str | None = Field(default=None, max_length=MAX_AVATAR_IMAGE_CHARS)


class SessionCreate(BaseModel):
    """Cuerpo de `POST /api/session`: el perfil que la petición **reclama**.

    No es una credencial por sí mismo —desde V3.76 puede acompañarse de una
    (`pin`) si el perfil la tiene— y conviene no confundirlo: es la declaración
    de con quién quieres abrir sesión, y el servidor la firma. Lo que cambia
    respecto a V3.73.x es que, a partir de ahí, la identidad viaja en una cookie
    que el cliente **no puede forjar**, en vez de en la URL
    (`docs/audit/PLAN-P0-IDENTIDAD.md` §4).

    V3.76: si el perfil tiene PIN y no se envía (o no cuadra), la respuesta es
    401 con `PIN_REQUIRED` / `PIN_INVALID` para que la UI pueda pedirlo. Un
    perfil sin PIN sigue abriendo con el cuerpo de siempre.
    """

    user_id: str = Field(min_length=1, max_length=64)
    # 4-6 dígitos. El tope de longitud lo valida `services/pins.is_valid_pin`,
    # que es también quien da formato al freno de intentos.
    pin: str | None = Field(default=None, max_length=16)


class PinSet(BaseModel):
    """Poner, cambiar o retirar el PIN del perfil **de la sesión**.

    `current_pin` solo es obligatorio al cambiar o retirar un PIN que ya existía:
    pedirlo es lo que impide que quien se siente delante de un equipo con sesión
    abierta ponga su propio PIN y se quede el perfil. `new_pin` vacío retira el
    PIN (el perfil vuelve a entrar sin credencial, con su consecuencia
    declarada).
    """

    current_pin: str | None = Field(default=None, max_length=16)
    new_pin: str = Field(default="", max_length=16)

