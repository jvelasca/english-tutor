"""Esquemas Pydantic de usuarios (V3.81: la cuenta)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from services.credentials import PASSWORD_MAX_CHARS

# Límite para la imagen de avatar (data URL). Suficiente para una miniatura
# redimensionada en el cliente (~128 px) y evita abusos de tamaño en la BD.
MAX_AVATAR_IMAGE_CHARS = 500_000

# Topes de forma para email y contraseña. La **política** de la contraseña la
# decide `services.credentials.is_valid_password` (longitud mínima y lista de
# obvias); aquí solo se acota lo que Pydantic deja pasar antes de tocar el KDF.
MAX_EMAIL_CHARS = 254
MAX_PASSWORD_CHARS = PASSWORD_MAX_CHARS


class User(BaseModel):
    id: str
    name: str
    avatar_color: str = ""
    avatar_emoji: str = ""
    avatar_image: str = ""
    # V3.52.1: perfil de PRUEBA (tests visuales). Nunca aparece en el selector
    # de la app; se expone para que los tests puedan localizar y limpiar el suyo.
    is_test: bool = False
    # V3.81 (Fase 3 del P0): la cuenta. `has_password` es el booleano que la UI
    # necesita para saber si tiene que pedir credencial al elegirla; el hash no
    # sale nunca de la BD (misma doctrina que el PIN en V3.76).
    email: str = ""
    email_verified: bool = False
    has_password: bool = False
    # Contraseña temporal puesta por el webmaster: la app obliga a cambiarla
    # antes de dejar usar nada.
    must_change_password: bool = False
    # V3.77/V3.81: `active` | `disabled` | `unenrolled`. La app y el selector solo
    # ven cuentas activas (el repositorio las filtra), así que este campo lo lee
    # la consola de gestión para poder mostrar y reactivar las demás.
    status: str = "active"
    created_at: str


class UserCreate(BaseModel):
    """Alta de la **primera** cuenta en el propio equipo (`POST /api/users`).

    V3.81: es el registro autoservicio. Nace con email y contraseña, así que la
    puerta de entrada ya no ofrece «un nombre y a correr»: eso es exactamente el
    «sin cuentas» que la Fase 3 viene a cerrar.
    """

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=MAX_EMAIL_CHARS)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)
    # Solo los tests lo marcan; la app siempre crea cuentas reales.
    is_test: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_color: str | None = Field(default=None, max_length=32)
    avatar_emoji: str | None = Field(default=None, max_length=16)
    avatar_image: str | None = Field(default=None, max_length=MAX_AVATAR_IMAGE_CHARS)


class SessionCreate(BaseModel):
    """Cuerpo de `POST /api/session`: la cuenta que la petición **reclama**.

    V3.81: si la cuenta tiene contraseña, es obligatoria. Lo que cambia respecto a
    V3.73.x es que ya no basta con **nombrar** a alguien: hay que demostrar que se
    es quien dice ser. Las cuentas heredadas sin contraseña (`has_password` falso)
    siguen abriendo con el cuerpo de siempre mientras el webmaster no les asigne
    credenciales, que es la compatibilidad declarada de esta release.
    """

    user_id: str = Field(min_length=1, max_length=64)
    password: str | None = Field(default=None, max_length=MAX_PASSWORD_CHARS)


class PasswordChange(BaseModel):
    """Cambiar la contraseña de la cuenta **de la sesión** (V3.81).

    `current_password` solo es obligatorio si la cuenta ya tenía contraseña:
    pedirla es lo que impide que quien se sienta delante de un equipo con la
    sesión abierta ponga su propia contraseña y se quede la cuenta.
    """

    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_CHARS)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)


class EmailChange(BaseModel):
    """Cambiar el email de la cuenta **de la sesión**. Exige re-autenticarse.

    Sin la contraseña, un equipo con la sesión abierta bastaría para apuntar la
    verificación a un correo ajeno.
    """

    password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)
    email: str = Field(min_length=3, max_length=MAX_EMAIL_CHARS)


class UnenrollRequest(BaseModel):
    """Baja autoservicio. Exige la contraseña por el mismo motivo que el cambio de
    email: darse de baja es una decisión, no un descuido de quien pasa por delante."""

    password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)


class EmailVerify(BaseModel):
    """Token de verificación tal como llega del enlace del correo."""

    token: str = Field(min_length=8, max_length=256)
