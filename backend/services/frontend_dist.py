"""Servido de la UI compilada (`frontend/dist`) desde el propio backend (V3.72).

Cierra **RC-01**: hasta V3.71 el artefacto de producción se construía en CI y
**no lo servía nadie**, así que el runtime de producto era el **dev server de
Vite** y Node + npm eran requisito de *ejecución*. Ahora el backend sirve
`frontend/dist` (assets + `index.html`) y el launcher arranca **un solo origen
HTTPS**, con Node como requisito solo de **compilación**.

Reglas del montaje:

- **Fail-open**: si el artefacto no existe, no se monta nada y el arranque no se
  rompe (un clon limpio sin `npm run build` sigue teniendo API).
- **Prioridad de la API**: los routers se registran antes, así que `/api/*` gana;
  el *fallback* SPA además responde **404** a cualquier `api/...` sin ruta, para
  no enmascarar un endpoint inexistente con un `index.html`.
- **Sin salir del directorio**: una ruta con `..` no puede leer ficheros de fuera
  del artefacto.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# `<repo>/frontend/dist` (este módulo vive en `<repo>/backend/services/`).
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def dist_dir() -> Path:
    """Directorio del artefacto de la UI."""
    return FRONTEND_DIST


def dist_available(path: Path | None = None) -> bool:
    """True si el artefacto existe y tiene `index.html` (es servible)."""
    root = path if path is not None else dist_dir()
    return (root / "index.html").is_file()


def resolve_static_file(relative: str, path: Path | None = None) -> Path | None:
    """Fichero del artefacto para una ruta relativa, o None si no es servible.

    Devuelve None si la ruta escapa del directorio del artefacto (`..`) o si el
    fichero no existe: el llamante decide entonces el *fallback*.
    """
    root = (path if path is not None else dist_dir()).resolve()
    clean = (relative or "").strip().lstrip("/\\")
    if not clean:
        return None
    candidate = (root / clean).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def mount_frontend(app: FastAPI, path: Path | None = None) -> bool:
    """Monta los assets y el *fallback* SPA del artefacto. True si lo sirvió.

    Debe llamarse **después** de registrar los routers, para que ninguna ruta
    catch-all eclipse a la API.
    """
    root = path if path is not None else dist_dir()
    index = root / "index.html"
    if not index.is_file():
        logger.info(
            "frontend/dist no encontrado en %s: la API arranca sin servir la UI "
            "(ejecuta `npm run build` para generarlo)",
            root,
        )
        return False

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        # Un `/api/...` sin ruta registrada es un 404 real, no una página.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = resolve_static_file(full_path, root)
        if candidate is not None:
            return FileResponse(candidate)
        return FileResponse(index)

    logger.info("Sirviendo la UI compilada desde %s", root)
    return True
