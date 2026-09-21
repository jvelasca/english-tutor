"""Cliente de administración del launcher (V3.77): habla con `/api/admin/*`.

Es el único sitio del launcher que **escribe** en el producto. Hasta V3.77 el
launcher solo miraba (contadores por SQLite en solo-lectura y GET al backend), y
la administración de perfiles obliga a la otra mitad: crear, desactivar y purgar.
Se hace por HTTP y **no** escribiendo la BD, aunque el launcher tenga el fichero a
mano, por una razón concreta: el borrado de un perfil tiene que pasar por el mismo
sitio que todo lo demás (la validación, el snapshot previo, la tabla de
solicitudes), o habría dos definiciones de «purgar» y la del launcher sería la que
nadie prueba.

El PIN viaja en la cabecera `X-Admin-Pin`. El backend exige **además** que la
petición venga del propio equipo, y eso se cumple por construcción: el launcher
habla con `backend_url()`, que es loopback.

Todas las funciones devuelven un `AdminResult` en vez de lanzar: la GUI tiene que
poder enseñar «no se pudo» sin que se le caiga el hilo, y un `try` en cada botón
sería el mismo código repetido siete veces.
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
        if self.status == 401:
            return "El backend no acepta el PIN de administración."
        if self.status == 403:
            return "La administración de perfiles solo se ejerce desde este equipo."
        if self.status == 409:
            return str(self.data.get("detail", "La solicitud ya estaba resuelta."))
        if self.status == 422:
            return str(self.data.get("detail", "Datos no válidos."))
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


def pending_requests(pin: str) -> AdminResult:
    """Cola de solicitudes pendientes + contador (una sola llamada)."""
    return _call("GET", "/api/admin/profile-requests?status=pending", pin=pin)


def approve_request(
    pin: str, request_id: int, *, note: str = "", profile_pin: str = ""
) -> AdminResult:
    """Aprueba: un alta crea el perfil; una baja lo desactiva."""
    return _call(
        "POST",
        f"/api/admin/profile-requests/{request_id}/approve",
        pin=pin,
        payload={"note": note, "pin": profile_pin},
    )


def reject_request(pin: str, request_id: int, *, note: str = "") -> AdminResult:
    return _call(
        "POST",
        f"/api/admin/profile-requests/{request_id}/reject",
        pin=pin,
        payload={"note": note, "pin": ""},
    )


def list_profiles(pin: str) -> AdminResult:
    """Perfiles con los desactivados incluidos, más el contador de pendientes."""
    result = _call("GET", "/api/admin/users?include_disabled=true", pin=pin)
    return result


def create_profile(pin: str, name: str, *, profile_pin: str = "") -> AdminResult:
    return _call(
        "POST",
        "/api/admin/users",
        pin=pin,
        payload={"name": name, "pin": profile_pin},
    )


def set_profile_status(pin: str, user_id: str, status: str) -> AdminResult:
    return _call(
        "POST",
        f"/api/admin/users/{user_id}/status",
        pin=pin,
        payload={"status": status},
    )


def purge_profile(pin: str, user_id: str, confirm_name: str) -> AdminResult:
    """Borrado irreversible. El backend toma el snapshot antes de borrar."""
    return _call(
        "POST",
        f"/api/admin/users/{user_id}/purge",
        pin=pin,
        payload={"confirm_name": confirm_name},
        # La copia de seguridad va antes del borrado y en un perfil grande puede
        # tardar: este es el único sitio donde se justifica esperar más.
        timeout=60.0,
    )
