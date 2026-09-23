"""Cliente de administración del launcher (V3.77, ampliado en V3.81).

Es el único sitio del launcher que **escribe** en el producto. Hasta V3.77 el
launcher solo miraba (contadores por SQLite en solo-lectura y GET al backend), y
la administración de cuentas obliga a la otra mitad: crear, asignar credenciales,
verificar, forzar la baja, editar, purgar y leer el historial. Se hace por HTTP y
**no** escribiendo la BD, aunque el launcher tenga el fichero a mano, por una razón
concreta: el borrado de una cuenta tiene que pasar por el mismo sitio que todo lo
demás (la validación, el snapshot previo, la tabla de solicitudes y el registro de
auditoría), o habría dos definiciones de «purgar» y la del launcher sería la que
nadie prueba.

El PIN viaja en la cabecera `X-Admin-Pin`. El backend exige **además** que la
petición venga del propio equipo, y eso se cumple por construcción: el launcher
habla con `backend_url()`, que es loopback.

Todas las funciones devuelven un `AdminResult` en vez de lanzar: la GUI tiene que
poder enseñar «no se pudo» sin que se le caiga el hilo, y un `try` en cada botón
sería el mismo código repetido doce veces.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from core import backend_url
from status import _ssl_context

ADMIN_PIN_HEADER = "X-Admin-Pin"
_TIMEOUT_SECONDS = 8.0

# V3.81: los códigos con los que el backend explica un rechazo concreto
# (`detail` en mayúsculas, como `PASSWORD_FORMAT`). Se traducen aquí y no en la
# GUI porque es el mismo vocabulario para las cuatro pantallas que los provocan, y
# porque un `detail` en crudo en la barra de estado («EMAIL_TAKEN») no es una frase.
_DETAIL_MESSAGES = {
    "EMAIL_TAKEN": "Ese email ya está en uso por otra cuenta.",
    "EMAIL_FORMAT": "Ese email no tiene forma de email.",
    "USER_NAME_TAKEN": "Ya hay una cuenta activa con ese nombre.",
    "PASSWORD_FORMAT": "Esa contraseña no cumple la política (mínimo 8 caracteres).",
}


@dataclass(frozen=True)
class AdminResult:
    """Lo que el launcher necesita saber de una llamada admin, sin excepciones."""

    ok: bool
    status: int = 0
    data: dict = field(default_factory=dict)
    error: str = ""

    def message(self) -> str:
        """Frase corta para la barra de estado del launcher."""
        if self.ok:
            return "Hecho."
        detail = str(self.data.get("detail") or "")
        if detail in _DETAIL_MESSAGES:
            return _DETAIL_MESSAGES[detail]
        if self.status == 401:
            return "El backend no acepta el PIN de administración."
        if self.status == 403:
            return "La administración de cuentas solo se ejerce desde este equipo."
        if self.status == 404:
            return "Esa cuenta ya no existe."
        if self.status == 409:
            return detail or "La operación no se pudo completar (conflicto)."
        if self.status == 422:
            return detail or "Datos no válidos."
        if self.error:
            return f"No se pudo hablar con el servidor ({self.error})."
        return f"El servidor respondió {self.status}."


def _call(
    method: str,
    path: str,
    *,
    pin: str,
    payload: dict | None = None,
    timeout: float = _TIMEOUT_SECONDS,
) -> AdminResult:
    if not pin:
        # No es un error de red: sin PIN declarado la administración está
        # deshabilitada, y se dice así en vez de mandar una petición que el
        # backend va a rechazar.
        return AdminResult(ok=False, status=401)
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        backend_url() + path,
        data=body,
        method=method,
        headers={
            ADMIN_PIN_HEADER: pin,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=_ssl_context()
        ) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return AdminResult(ok=True, status=resp.status, data=data)
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            raw = ""
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return AdminResult(ok=False, status=exc.code, data=data)
    except Exception as exc:  # noqa: BLE001
        return AdminResult(ok=False, error=str(exc))


# --- Cola de solicitudes ------------------------------------------------------

def pending_requests(pin: str) -> AdminResult:
    """Cola de solicitudes pendientes + contador (una sola llamada)."""
    return _call("GET", "/api/admin/profile-requests?status=pending", pin=pin)


def approve_request(pin: str, request_id: int, *, note: str = "") -> AdminResult:
    """Aprueba: un alta crea la cuenta; una baja la desactiva.

    V3.81: ya no se manda `pin` de perfil. Aprobar un alta crea la cuenta **sin
    credencial** y la consola ofrece a continuación asignarle email y contraseña
    temporal: son dos decisiones distintas.
    """
    return _call(
        "POST",
        f"/api/admin/profile-requests/{request_id}/approve",
        pin=pin,
        payload={"note": note},
    )


def reject_request(pin: str, request_id: int, *, note: str = "") -> AdminResult:
    return _call(
        "POST",
        f"/api/admin/profile-requests/{request_id}/reject",
        pin=pin,
        payload={"note": note},
    )


# --- Cuentas ------------------------------------------------------------------

def list_users(pin: str) -> AdminResult:
    """Cuentas con las fuera de servicio incluidas, más los contadores.

    El backend devuelve en la misma respuesta las pendientes, las que siguen
    **sin contraseña** y las que tienen el email sin verificar: son la lista de
    tareas del webmaster, y pintarlas desde llamadas distintas las haría
    contradecirse entre sí.
    """
    return _call("GET", "/api/admin/users?include_disabled=true", pin=pin)


def create_user(
    pin: str, name: str, *, email: str = "", password: str = ""
) -> AdminResult:
    """Alta directa del webmaster, ya con credenciales (no pasa por la cola).

    Contraseña vacía = «genérala tú»: el backend devuelve una temporal legible y
    marca `must_change_password`, así que el webmaster puede entregarla sin
    inventarse nada y sin llegar a saber la definitiva del alumno.
    """
    return _call(
        "POST",
        "/api/admin/users",
        pin=pin,
        payload={"name": name, "email": email, "password": password},
    )


def edit_user(pin: str, user_id: str, **fields) -> AdminResult:
    """Edita los datos de una cuenta (nombre, email, avatar).

    Se mandan **solo** los campos presentes: el backend usa
    `exclude_unset`, así que un campo ausente no se toca. Mandar el dict entero
    con `None` sería otra cosa (un intento de vaciarlo).
    """
    return _call(
        "PATCH",
        f"/api/admin/users/{user_id}",
        pin=pin,
        payload={key: value for key, value in fields.items() if value is not None},
    )


def set_user_status(pin: str, user_id: str, status: str) -> AdminResult:
    """`active` o `disabled`. `active` sirve también para reactivar una baja.

    Forzar la baja **no** se hace por aquí: exige motivo y tiene su propia llamada
    (`force_unenroll`). Dejar dos caminos para lo mismo garantizaría que la mitad
    de las bajas forzadas no se expliquen.
    """
    return _call(
        "POST",
        f"/api/admin/users/{user_id}/status",
        pin=pin,
        payload={"status": status},
    )


def set_credentials(
    pin: str, user_id: str, *, email: str, password: str = ""
) -> AdminResult:
    """Asigna o **restablece** la credencial: es la recuperación de contraseña.

    Sin contraseña se genera una temporal (y `must_change_password`). Reinicia
    además la verificación del email, porque la credencial vuelve a estar en manos
    de otro.
    """
    return _call(
        "POST",
        f"/api/admin/users/{user_id}/credentials",
        pin=pin,
        payload={"email": email, "password": password},
    )


def verify_email(pin: str, user_id: str) -> AdminResult:
    """Sella el email a mano: la otra mitad del modo híbrido, para cuando no hay
    SMTP configurado y el enlace de verificación no sale de ningún sitio."""
    return _call("POST", f"/api/admin/users/{user_id}/verify-email", pin=pin)


def force_unenroll(pin: str, user_id: str, reason: str) -> AdminResult:
    """**Fuerza** la baja. No borra nada: cierra las sesiones al instante y deja
    el motivo en el historial, que es la diferencia entre una decisión y un botón."""
    return _call(
        "POST",
        f"/api/admin/users/{user_id}/unenroll",
        pin=pin,
        payload={"reason": reason},
    )


def user_history(pin: str, user_id: str) -> AdminResult:
    """Historial de auditoría de la cuenta, del más reciente al más antiguo.

    Sobrevive a la purga: cuando ya no queda fila en `users`, es el único sitio
    que responde «¿quién borró esto y por qué?».
    """
    return _call("GET", f"/api/admin/users/{user_id}/events", pin=pin)


def purge_user(pin: str, user_id: str, confirm_name: str) -> AdminResult:
    """Borrado irreversible. El backend toma el snapshot antes de borrar.

    Exige que la cuenta esté **fuera de servicio** (`disabled` o `unenrolled`):
    purgar borra todo rastro de una persona, y eso no se hace sin un paso previo
    que alguien pueda revisar.
    """
    return _call(
        "POST",
        f"/api/admin/users/{user_id}/purge",
        pin=pin,
        payload={"confirm_name": confirm_name},
        # La copia de seguridad va antes del borrado y en una cuenta con mucha
        # evidencia puede tardar: este es el único sitio donde se justifica
        # esperar más.
        timeout=60.0,
    )


# --- Correo saliente ----------------------------------------------------------

def smtp_config(pin: str) -> AdminResult:
    """Config del SMTP tal como la ve el backend, **sin la contraseña**.

    La consola solo necesita saber si hay contraseña guardada (`has_password`); el
    valor no sale de aquí por el mismo motivo por el que no sale el del PIN: una
    pantalla que enseña un secreto es una pantalla desde la que se copia.
    """
    return _call("GET", "/api/admin/smtp", pin=pin)


def test_smtp(pin: str, to: str) -> AdminResult:
    """Manda un correo de prueba. Es la única forma de saber que el correo
    funciona; la alternativa se descubre fallando cuando alguien espera una
    verificación que nunca llega."""
    return _call(
        "POST",
        "/api/admin/smtp/test",
        pin=pin,
        payload={"to": to},
        timeout=30.0,
    )
