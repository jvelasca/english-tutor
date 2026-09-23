"""Solicitudes de perfil (V3.77) — el estado que el webmaster resuelve.

Una solicitud es **inerte**: existe aquí y no toca `users` ni una sola fila de
evidencia. Aprobar es lo que crea o borra, y eso solo ocurre desde el lanzador
(`agentes/v377-perfiles-webmaster.md`).

Las solicitudes viven en la BD de la app y no en un fichero suelto por tres
razones concretas: sobreviven a un reinicio, viajan en el backup y el lanzador
—que ya abre esta BD en solo-lectura para sus contadores— puede contar las
pendientes sin depender de que el backend conteste
(`launcher/status.py::read_pending_requests`, V3.80.1: hasta entonces esa frase
era una capacidad declarada y no implementada, y una baja podía quedarse
invisible en el lanzador cuando no había PIN de administración).
"""
from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now

KIND_CREATE = "create"
KIND_DELETE = "delete"
KINDS = (KIND_CREATE, KIND_DELETE)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED)

_COLUMNS = (
    "id, kind, display_name, user_id, note, requested_at, status, "
    "decided_at, decided_note, resolved_user_id"
)


def _row_to_request(row: object) -> dict:
    return dict(row)  # type: ignore[arg-type]


def create_request(
    kind: str,
    *,
    display_name: str = "",
    user_id: str = "",
    note: str = "",
) -> dict:
    """Registra una solicitud pendiente. No crea ni borra ningún perfil."""
    now = _now()
    with closing(_conn()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO profile_requests "
            "(kind, display_name, user_id, note, requested_at, status, "
            "decided_at, decided_note, resolved_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, '', '', '')",
            (kind, display_name, user_id, note, now, STATUS_PENDING),
        )
        request_id = int(cursor.lastrowid or 0)
    created = get_request(request_id)
    assert created is not None  # recién insertada
    return created


def get_request(request_id: int) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM profile_requests WHERE id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row) if row is not None else None


def list_requests(status: str | None = None) -> list[dict]:
    """Solicitudes, de la más antigua a la más reciente.

    El orden es por fecha **ascendente** a propósito: lo que lleva más tiempo
    esperando es lo primero que debe ver quien decide.
    """
    where = ""
    params: tuple = ()
    if status is not None:
        where = " WHERE status = ?"
        params = (status,)
    with closing(_conn()) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM profile_requests{where} "
            "ORDER BY requested_at ASC, id ASC",
            params,
        ).fetchall()
    return [_row_to_request(r) for r in rows]


def count_pending() -> int:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM profile_requests WHERE status = ?",
            (STATUS_PENDING,),
        ).fetchone()
    return int(row[0]) if row is not None else 0


def has_pending_create_for_name(name: str) -> bool:
    """¿Hay ya una petición de alta pendiente con ese nombre?

    La comparación es sin distinguir mayúsculas porque el criterio de la regla
    es «no me pidas dos veces lo mismo», y `Ana` y `ana` son la misma persona
    pidiendo el mismo perfil.
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT 1 FROM profile_requests WHERE status = ? AND kind = ? "
            "AND LOWER(display_name) = LOWER(?) LIMIT 1",
            (STATUS_PENDING, KIND_CREATE, name),
        ).fetchone()
    return row is not None


def pending_delete_for_user(user_id: str) -> dict | None:
    """Petición de baja pendiente de ese perfil, si la hay."""
    with closing(_conn()) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM profile_requests WHERE status = ? "
            "AND kind = ? AND user_id = ? LIMIT 1",
            (STATUS_PENDING, KIND_DELETE, user_id),
        ).fetchone()
    return _row_to_request(row) if row is not None else None


def resolve(
    request_id: int,
    status: str,
    *,
    decided_note: str = "",
    resolved_user_id: str = "",
) -> dict | None:
    """Marca una solicitud como resuelta. `None` si no existe o ya no está pendiente.

    La condición `status = 'pending'` en el `UPDATE` es lo que impide resolver
    dos veces la misma solicitud (dos clics en el lanzador, o dos lanzadores):
    el segundo no encuentra fila que actualizar y devuelve `None`, así que
    aprobar dos veces no puede crear dos perfiles.
    """
    if status not in (STATUS_APPROVED, STATUS_REJECTED):
        return None
    with closing(_conn()) as conn, conn:
        cursor = conn.execute(
            "UPDATE profile_requests SET status = ?, decided_at = ?, "
            "decided_note = ?, resolved_user_id = ? "
            "WHERE id = ? AND status = ?",
            (
                status,
                _now(),
                decided_note,
                resolved_user_id,
                request_id,
                STATUS_PENDING,
            ),
        )
        if cursor.rowcount != 1:
            return None
    return get_request(request_id)
