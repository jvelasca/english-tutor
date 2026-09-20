"""Persistencia de los ajustes del launcher (JSON, sin dependencias externas).

V3.75.3: el launcher recuerda **la última configuración usada**, no solo la
geometría de la ventana (`state_store.py`). Hoy guarda una sola preferencia —el
modo LAN (`ENGLISH_TUTOR_LAN`)— que antes vivía únicamente en el entorno del
proceso y se perdía al cerrar: activar «red local» y reabrir el launcher
devolvía el modo desactivado.

Este fichero es **configuración**, no estado visual, y por eso vive aparte de
`state.json`: se lee al arrancar antes de pintar la interfaz (el panel de acceso
tiene que mostrar el modo vigente) y se escribe **en cada cambio**, no al cerrar
(una preferencia de red no debería depender de que la ventana se cierre bien).

Si el archivo no existe o está corrupto, se usan valores por defecto; si no se
puede escribir, se ignora silenciosamente (el launcher funciona igual sin
persistencia). El valor por defecto es **cerrado** (`lan: False`): la ausencia de
preferencia nunca expone la API en la red local.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULTS: dict = {
    # Fail-closed: sin preferencia guardada, modo LAN desactivado. Es el mismo
    # criterio que `core.lan_mode`, que trata ausencia y valores raros como False.
    "lan": False,
}


def load_config(path: Path | None = None) -> dict:
    """Carga los ajustes guardados; si faltan o son inválidos, los defaults."""
    path = path or CONFIG_PATH
    config: dict = dict(DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config
    if not isinstance(data, dict):
        return config

    # `bool` antes que `int` a propósito: en Python `True` es un `int`, así que
    # sin este `isinstance` un `1` numérico del JSON colaría como booleano.
    lan = data.get("lan")
    if isinstance(lan, bool):
        config["lan"] = lan

    return config


def save_config(config: dict, path: Path | None = None) -> None:
    """Guarda los ajustes en disco (JSON indentado); ignora errores de escritura.

    La escritura es **atómica** (fichero temporal + `os.replace`): un corte a mitad
    deja intacto el fichero anterior en vez de un JSON truncado, que en la
    siguiente arrancada se leería como «sin preferencia» y **cerraría** el modo que
    el usuario había dejado activo. `os.replace` sobrescribe el destino si existe,
    así que tampoco hay una ventana sin fichero.
    """
    path = path or CONFIG_PATH
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)
    except OSError:
        # No poder guardar no puede tumbar el launcher ni dejar basura: la sesión
        # sigue con el modo vigente en memoria y el temporal se retira.
        try:
            tmp.unlink()
        except OSError:
            pass
