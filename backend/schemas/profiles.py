"""Esquemas de solicitudes de perfil y de su administración (V3.77, V3.81).

Los dos lados hablan idiomas distintos a propósito: el alumno **pide** (nombre o
nota, nada más) y el webmaster **decide** (nota, credenciales, estado, motivo).
Separarlos evita que el cuerpo de la petición pública acabe teniendo campos que
solo tienen sentido al resolver, como una contraseña temporal o el nombre de
confirmación de una purga.

V3.81: el webmaster pasa de «decidir sobre perfiles» a **administrar cuentas**.
Lo que gana son las operaciones reales de una consola de gestión —asignar
credenciales, verificar el email a mano, forzar la baja, editar los datos— y lo
que se mantiene es el candado: PIN de administración **y** loopback, sin
excepción.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from schemas.users import MAX_EMAIL_CHARS, MAX_PASSWORD_CHARS, User

MAX_NOTE_CHARS = 200
# Motivo obligatorio al forzar una baja: una decisión que se le impone a un alumno
# tiene que poder explicarse después («¿por qué me sacasteis?»). Es corto porque es
# una consola, no un formulario.
MAX_REASON_CHARS = 300


class ProfileRequestCreate(BaseModel):
    """Petición de alta. Se responde **sin sesión**, así que todo va acotado."""

    display_name: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=MAX_NOTE_CHARS)


class ProfileRequestDelete(BaseModel):
    """Petición de baja de la propia cuenta (requiere sesión)."""

    note: str = Field(default="", max_length=MAX_NOTE_CHARS)


class ProfileRequestOut(BaseModel):
    id: int
    kind: str
    display_name: str = ""
    user_id: str = ""
    note: str = ""
    requested_at: str
    status: str
    decided_at: str = ""
    decided_note: str = ""
    resolved_user_id: str = ""


class ProfileRequestsOut(BaseModel):
    requests: list[ProfileRequestOut]
    # Cuántas siguen pendientes en total, para que el lanzador pueda enseñar el
    # contador sin recorrer una lista que puede venir filtrada.
    pending: int


class ProfileRequestDecision(BaseModel):
    """Resolver una petición: solo la nota del webmaster.

    V3.81: ya no lleva `pin`. Aprobar un alta crea la cuenta **sin credencial** y
    la consola ofrece a continuación asignarle email y contraseña temporal: son
    dos decisiones distintas y mezclarlas obligaba a teclear el PIN antes de saber
    si la cuenta se iba a crear siquiera.
    """

    note: str = Field(default="", max_length=MAX_NOTE_CHARS)


class AdminUserCreate(BaseModel):
    """Alta directa del webmaster, ya con credenciales (V3.81).

    `password` vacío significa «genérala tú»: el backend devuelve una temporal
    legible y marca la cuenta con `must_change_password`, así que el webmaster
    puede entregarla sin inventarse nada y sin conocer la contraseña definitiva
    del alumno.
    """

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(default="", max_length=MAX_EMAIL_CHARS)
    password: str = Field(default="", max_length=MAX_PASSWORD_CHARS)


class AdminCredentials(BaseModel):
    """Asignar o restablecer la credencial de una cuenta existente."""

    email: str = Field(min_length=3, max_length=MAX_EMAIL_CHARS)
    password: str = Field(default="", max_length=MAX_PASSWORD_CHARS)


class AdminUserEdit(BaseModel):
    """El webmaster edita los datos de una cuenta con la misma autoridad que el
    propio alumno (y puede además corregir su email). Cambiar el email reinicia su
    verificación: apuntarlo a otro correo no puede heredar el sello del anterior."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=MAX_EMAIL_CHARS)
    avatar_color: str | None = Field(default=None, max_length=32)
    avatar_emoji: str | None = Field(default=None, max_length=16)
    avatar_image: str | None = Field(default=None, max_length=500_000)


class AdminUserStatus(BaseModel):
    """Estado de servicio que el webmaster puede poner con un clic.

    `unenrolled` **no** está aquí a propósito: forzar la baja exige un motivo
    (`AdminForceUnenroll`), y dejar dos formas de hacer lo mismo —una con motivo y
    otra sin él— garantiza que la mitad de las bajas forzadas no se expliquen.
    """

    status: Literal["active", "disabled"]


class AdminForceUnenroll(BaseModel):
    """Forzar la baja de una cuenta: el motivo es obligatorio y queda registrado."""

    reason: str = Field(min_length=1, max_length=MAX_REASON_CHARS)


class AdminPurge(BaseModel):
    """Confirmación de borrado: hay que teclear el nombre exacto de la cuenta."""

    confirm_name: str = Field(min_length=1, max_length=80)


class AdminUserEventOut(BaseModel):
    """Una línea del historial: qué se hizo, quién y con qué motivo."""

    id: int
    subject_id: str = ""
    subject_name: str = ""
    action: str
    actor: str = ""
    note: str = ""
    created_at: str


class AdminHistoryOut(BaseModel):
    events: list[AdminUserEventOut]


class AdminUsersOut(BaseModel):
    users: list[User]
    pending: int
    # Cuántas cuentas siguen **sin credencial** (contraseña vacía). Es la lista de
    # tareas del webmaster: mientras ese número no sea cero, esas cuentas entran
    # nombrando, que es el agujero que esta release viene a cerrar.
    without_password: int = 0
    # Cuántas tienen email y no está verificado (modo híbrido: las sella él).
    unverified_email: int = 0


class AdminSessionOut(BaseModel):
    """Credencial temporal recién generada, para que el webmaster la entregue.

    Va en la respuesta y **solo** en la respuesta: no se guarda en claro en ningún
    sitio ni se escribe en el log.
    """

    user: User
    temporary_password: str = ""


class AdminSmtpOut(BaseModel):
    """Config del correo saliente tal como la ve el backend (sin la contraseña)."""

    host: str = ""
    port: int = 0
    user: str = ""
    sender: str = ""
    configured: bool = False
    # Si hay contraseña guardada en `data/mail.secret`. Nunca se devuelve su valor:
    # la consola solo necesita saber si existe para poder decir «guardada».
    has_password: bool = False


class AdminSmtpTest(BaseModel):
    """Prueba de envío: a qué dirección se manda el correo de prueba."""

    to: str = Field(min_length=3, max_length=MAX_EMAIL_CHARS)
