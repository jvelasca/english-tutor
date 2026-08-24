# Subagente A.1 — Launcher de escritorio: núcleo puro + tests

## Rol
Programador Python (stdlib). Sin acceso a Git (no hagas commit), sin GUI aún (eso es A.2),
y sin tocar `backend/` ni `frontend/`.

## Objetivo
Crear el **núcleo puro y testable** de un launcher de escritorio para la app English Tutor.
Solo lógica determinista (rutas, comandos, normalización de estado), sin red, sin procesos,
sin GUI. Se testea con pytest.

## Contexto (autocontenido)
- El repo tiene esta forma (raíz = carpeta del proyecto):
  - `backend/` — FastAPI (venv en `backend/.venv`, con `python.exe` y `pythonw.exe`).
  - `frontend/` — Vite + React (se arranca con `npm run dev`).
  - El launcher vivirá en **`launcher/`** (nueva carpeta, hermana de las otras dos).
- Estilo: `from __future__ import annotations`, docstrings en español, línea ≤ 88.
  Ruff se aplica con las mismas reglas del backend (`select E,F,W,I,B`, `ignore B008`,
  `line-length 88`).
- Python disponible: `..\backend\.venv\Scripts\python.exe` (Python 3.13.7, con pytest).

## Tarea

### 1. `launcher/core.py` (nuevo) — contenido exacto

```python
"""Núcleo puro del launcher de escritorio (sin GUI, sin red, sin procesos).

Funciones deterministas para resolver rutas, construir comandos de arranque y
normalizar el estado de la app, las dependencias y la base de datos. Testeable
sin lanzar nada.
"""
from __future__ import annotations

import os
from pathlib import Path

# El launcher vive en <repo>/launcher/, así que el repo raíz es el padre del padre.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
DB_PATH = BACKEND_DIR / "data" / "tutor.db"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173


def backend_command() -> list[str]:
    """Comando para arrancar el backend con el venv del proyecto (uvicorn)."""
    exe = "python.exe" if os.name == "nt" else "python"
    python = BACKEND_DIR / ".venv" / "Scripts" / exe
    return [
        str(python),
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(BACKEND_PORT),
    ]


def frontend_command() -> list[str]:
    """Comando para arrancar el frontend (Vite dev)."""
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return [npm, "run", "dev"]


def backend_url() -> str:
    return f"http://127.0.0.1:{BACKEND_PORT}"


def frontend_url() -> str:
    return f"http://localhost:{FRONTEND_PORT}"


def app_summary(backend_up: bool, frontend_up: bool) -> dict[str, str]:
    """Estado on/off de cada servicio."""
    return {
        "backend": "on" if backend_up else "off",
        "frontend": "on" if frontend_up else "off",
    }


def health_status(deps: dict | None) -> dict[str, str]:
    """Normaliza el dict de /api/health/dependencies a estados por dependencia."""
    unknown = {
        "database": "unknown",
        "ollama": "unknown",
        "stt": "unknown",
        "tts": "unknown",
    }
    if deps is None:
        return {"api": "off", **unknown}

    def _norm(value: str | None) -> str:
        if value in ("ok", "ready"):
            return "ok"
        if value == "error":
            return "error"
        return "unavailable"

    return {
        "api": "ok",
        "database": _norm(deps.get("database")),
        "ollama": _norm(deps.get("ollama")),
        "stt": _norm(deps.get("stt")),
        "tts": _norm(deps.get("tts")),
    }


def db_summary(counts: dict) -> dict[str, int]:
    """Normaliza los contadores de la BD (entero, 0 si falta)."""
    return {
        "users": int(counts.get("users", 0)),
        "conversations": int(counts.get("conversations", 0)),
        "messages": int(counts.get("messages", 0)),
    }


def user_overview(rows: list[tuple]) -> list[dict]:
    """Convierte filas (id, name, conversations, messages) a dicts legibles."""
    return [
        {
            "id": row[0],
            "name": row[1],
            "conversations": int(row[2]),
            "messages": int(row[3]),
        }
        for row in rows
    ]
```

### 2. `launcher/tests/conftest.py` (nuevo)

```python
"""Asegura que los imports del launcher resuelvan al ejecutar pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

### 3. `launcher/tests/test_core.py` (nuevo, 13 tests) — contenido exacto

```python
"""Tests del núcleo puro del launcher (launcher/core.py)."""
from core import (
    BACKEND_DIR,
    BACKEND_PORT,
    FRONTEND_DIR,
    FRONTEND_PORT,
    REPO_ROOT,
    app_summary,
    backend_command,
    backend_url,
    db_summary,
    frontend_command,
    frontend_url,
    health_status,
    user_overview,
)


def test_repo_root_contains_backend_and_frontend():
    assert BACKEND_DIR.name == "backend"
    assert FRONTEND_DIR.name == "frontend"
    assert REPO_ROOT == BACKEND_DIR.parent


def test_backend_command_uses_venv_python():
    cmd = backend_command()
    assert cmd[0].endswith("python.exe") or cmd[0].endswith("python")
    assert "-m" in cmd
    assert "uvicorn" in cmd
    assert "main:app" in cmd
    assert str(BACKEND_PORT) in cmd


def test_frontend_command_runs_dev():
    cmd = frontend_command()
    assert "run" in cmd
    assert cmd[-1] == "dev"


def test_urls():
    assert backend_url() == f"http://127.0.0.1:{BACKEND_PORT}"
    assert frontend_url() == f"http://localhost:{FRONTEND_PORT}"


def test_app_summary_on():
    assert app_summary(True, True) == {"backend": "on", "frontend": "on"}


def test_app_summary_off():
    assert app_summary(False, False) == {"backend": "off", "frontend": "off"}


def test_app_summary_mixed():
    assert app_summary(True, False) == {"backend": "on", "frontend": "off"}


def test_health_status_none():
    status = health_status(None)
    assert status["api"] == "off"
    assert status["database"] == "unknown"


def test_health_status_ok():
    deps = {
        "api": "ok",
        "database": "ok",
        "ollama": "ok",
        "stt": "ready",
        "tts": "unavailable",
    }
    status = health_status(deps)
    assert status["database"] == "ok"
    assert status["stt"] == "ok"
    assert status["tts"] == "unavailable"


def test_health_status_error():
    status = health_status(
        {"database": "error", "ollama": "ok", "stt": "ready", "tts": "ready"}
    )
    assert status["database"] == "error"


def test_db_summary_defaults():
    assert db_summary({}) == {"users": 0, "conversations": 0, "messages": 0}


def test_db_summary_counts():
    assert db_summary({"users": 3, "conversations": 10, "messages": 42}) == {
        "users": 3,
        "conversations": 10,
        "messages": 42,
    }


def test_user_overview():
    rows = [("a", "Ana", 2, 5), ("b", "Bob", 0, 0)]
    overview = user_overview(rows)
    assert overview[0] == {
        "id": "a",
        "name": "Ana",
        "conversations": 2,
        "messages": 5,
    }
    assert overview[1]["messages"] == 0
```

### 4. `launcher/pyproject.toml` (nuevo) — para que ruff use las mismas reglas del backend

```toml
[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B"]
ignore = ["B008"]
```

## Verificación (desde `launcher/`)

```powershell
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q
..\backend\.venv\Scripts\python.exe -m ruff check .
```

Objetivo: **13 passed** y ruff "All checks passed!".

## Criterios de aceptación
- `..\backend\.venv\Scripts\python.exe -m pytest tests/ -q` → **13 passed**.
- `..\backend\.venv\Scripts\python.exe -m ruff check .` → **All checks passed!**.
- Sin tocar `backend/` ni `frontend/`.

## Restricciones
- NO tocar `backend/` ni `frontend/`.
- NO crear GUI ni gestionar procesos (eso es A.2).
- Solo añadir los 4 archivos indicados.
- NO hagas commit ni toques documentación.

## Salida
Lista de archivos creados, salida de `pytest` y de `ruff check .`, y cualquier desviación.
