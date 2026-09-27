"""Configuración de estudio: persistencia de la preferencia del alumno (V3.87.0).

Vive en la tabla `settings` (clave/valor por usuario) como **un** JSON bajo
`study_config`, y no en columnas nuevas: el mazo por defecto (`AUTO_DECK_ID = 0`)
es virtual y no admite columnas tipadas, y la preferencia es del ALUMNO, no de un
mazo —quién eres y cómo estudias no cambia al elegir mazo—. Ventaja de no migrar:
una BD de V3.86.1 se abre y funciona sin tocar el esquema.

`get_study_config` devuelve también `configured`, que es la pieza honesta: el
defecto no debe cambiar nada hasta que el alumno GUARDE su configuración. Sin
ese flag, el `mode` por defecto (`recognition`) restrigiría el Planner 3.0 de
todo el mundo al actualizar, y eso sería una regresión silenciosa.
"""
from __future__ import annotations

import json

from starlette.concurrency import run_in_threadpool

from repositories import settings as settings_repo
from services import study_config as study_config_service

#: Clave de la tabla `settings` donde vive el JSON de la configuración.
SETTINGS_KEY = "study_config"


def _load(raw: str | None) -> tuple[dict[str, str], bool]:
    """`(config normalizada, si el alumno la guardó alguna vez)`."""
    if not raw:
        return study_config_service.normalize_study_config(None), False
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        # Una fila corrupta no debe romper la sesión: se degrada al defecto y se
        # trata como «no configurado» para no aplicar un filtro que no se entiende.
        return study_config_service.normalize_study_config(None), False
    return study_config_service.normalize_study_config(parsed), True


async def get_study_config(user_id: str) -> dict:
    """`{"config": {...}, "configured": bool}` del alumno."""
    settings = await run_in_threadpool(settings_repo.get_settings, user_id)
    config, configured = _load(settings.get(SETTINGS_KEY))
    return {"config": config, "configured": configured}


async def set_study_config(user_id: str, patch: dict) -> dict:
    """Aplica un PATCH parcial (merge) y persiste el contrato completo.

    `None` en un campo significa «no lo toques», igual que el PATCH de fichas; la
    normalización garantiza que lo guardado es siempre válido. Devuelve el mismo
    sobre `get_study_config` para que la API no tenga que releer.
    """
    settings = await run_in_threadpool(settings_repo.get_settings, user_id)
    current, _ = _load(settings.get(SETTINGS_KEY))
    merged = dict(current)
    for key in study_config_service.DEFAULTS:
        value = patch.get(key)
        if value is not None:
            merged[key] = value
    normalized = study_config_service.normalize_study_config(merged)
    await run_in_threadpool(
        settings_repo.set_settings, user_id, {SETTINGS_KEY: json.dumps(normalized)}
    )
    return {"config": normalized, "configured": True}
