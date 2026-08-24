# Subagente E2.2 — Backend: health real (live / ready / dependencies)

## Rol
Programador backend Python (FastAPI + Pydantic). Sin acceso a Git ni al frontend.

## Objetivo
El endpoint `/api/health` actual es estático (`{"status": "ok"}`): dice que FastAPI vive, pero no
si SQLite, Ollama, Whisper o Piper están disponibles. Añadir liveness/readiness/estado de
dependencias, como pide la auditoría (P1).

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` y `docs/ARQUITECTURA.md`.
- `routers/models.py` hoy contiene `/`, `/api/health` (estático) y `/api/models`. El `/api/health`
  se va a **mover** a un router dedicado.
- `services/store.py` (SQLite síncrono), `services/llm.py` (Ollama, `ollama.AsyncClient()`),
  `services/stt.py` (faster-whisper, lazy `_model`, `WHISPER_DIR`/`WHISPER_SIZE`),
  `services/tts.py` (piper, lazy `_voice`, `PIPER_DIR`/`PIPER_VOICE`).
- `main.py` registra los routers y tiene `init_db()` en lifespan.
- El frontend **NO** consume `/api/health` (verificado). Puedes añadir endpoints sin romper la UI.
- `starlette.concurrency.run_in_threadpool` ya se usa en el repo para no bloquear el event loop.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  ```

## Tarea detallada

### 1. `services/store.py` — añadir `ping()`
Al final del archivo (NO tocar nada existente):
```python
def ping() -> bool:
    """Comprueba que SQLite responde (SELECT 1)."""
    try:
        with closing(_conn()) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False
```

### 2. `services/llm.py` — añadir `ping()`
```python
async def ping() -> bool:
    """Comprueba que Ollama responde."""
    try:
        await ollama.AsyncClient().list()
        return True
    except Exception:  # noqa: BLE001
        return False
```

### 3. `services/stt.py` — añadir `is_ready()`
```python
def is_ready() -> bool:
    """True si el modelo Whisper está descargado (directorio no vacío)."""
    try:
        return WHISPER_DIR.exists() and any(WHISPER_DIR.iterdir())
    except OSError:
        return False
```

### 4. `services/tts.py` — añadir `is_ready()`
```python
def is_ready() -> bool:
    """True si el modelo Piper (onnx + config) está presente."""
    return (PIPER_DIR / f"{PIPER_VOICE}.onnx").exists() and (
        PIPER_DIR / f"{PIPER_VOICE}.onnx.json"
    ).exists()
```

### 5. Crear `backend/routers/health.py`
Código completo:

```python
"""Endpoints de salud: liveness, readiness y estado de dependencias."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from services import llm, store, stt, tts

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "english-tutor"}


@router.get("/api/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


async def _dependencies() -> dict[str, str]:
    db_ok = await run_in_threadpool(store.ping)
    ollama_ok = await llm.ping()
    stt_ready = await run_in_threadpool(stt.is_ready)
    tts_ready = await run_in_threadpool(tts.is_ready)
    return {
        "api": "ok",
        "database": "ok" if db_ok else "error",
        "ollama": "ok" if ollama_ok else "error",
        "stt": "ready" if stt_ready else "unavailable",
        "tts": "ready" if tts_ready else "unavailable",
    }


@router.get("/api/health/dependencies")
async def dependencies() -> dict[str, str]:
    return await _dependencies()


@router.get("/api/health/ready")
async def ready() -> JSONResponse:
    deps = await _dependencies()
    ok = (
        deps["database"] == "ok"
        and deps["ollama"] == "ok"
        and deps["stt"] == "ready"
        and deps["tts"] == "ready"
    )
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "unavailable", "dependencies": deps},
    )
```

> Referenciar `store.ping`/`stt.is_ready`/`tts.is_ready`/`llm.ping` como atributos de módulo
> (no `from services.store import ping`) para que los tests puedan monkeypatchearlos.

### 6. `backend/routers/models.py` — quitar el `/api/health` estático
Eliminar el endpoint `health` (el bloque `@router.get("/api/health") ...`). Dejar `/` y `/api/models`.
No tocar nada más.

### 7. `backend/main.py` — registrar el router de health
- Añadir `from routers.health import router as health_router`.
- Añadir `app.include_router(health_router)` (junto al resto).

### 8. Tests — ampliar `backend/tests/test_health.py`
Conservar `test_root` y `test_health`. Añadir (monkeypatching los checks; NO llamar a Ollama real):

```python
from fastapi.testclient import TestClient

from main import app
from services import llm, stt, store, tts


def _all_ok(monkeypatch):
    monkeypatch.setattr(store, "ping", lambda: True)
    monkeypatch.setattr(llm, "ping", _async_true)
    monkeypatch.setattr(stt, "is_ready", lambda: True)
    monkeypatch.setattr(tts, "is_ready", lambda: True)


async def _async_true():
    return True


async def _async_false():
    return False


def test_health_live(monkeypatch):
    with TestClient(app) as client:
        r = client.get("/api/health/live")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_dependencies_all_ok(monkeypatch):
    _all_ok(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/health/dependencies")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "api": "ok",
            "database": "ok",
            "ollama": "ok",
            "stt": "ready",
            "tts": "ready",
        }


def test_ready_200_when_all_ok(monkeypatch):
    _all_ok(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_ready_503_when_ollama_down(monkeypatch):
    monkeypatch.setattr(store, "ping", lambda: True)
    monkeypatch.setattr(llm, "ping", _async_false)
    monkeypatch.setattr(stt, "is_ready", lambda: True)
    monkeypatch.setattr(tts, "is_ready", lambda: True)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "unavailable"
        assert body["dependencies"]["ollama"] == "error"
```

> `monkeypatch.setattr(llm, "ping", _async_true)` parchea el atributo del módulo; como `health.py`
> hace `from services import llm` y llama `llm.ping()`, la referencia se resuelve en runtime.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (48 previos + 4 nuevos = 52 tests).
- `/api/health` sigue devolviendo `{"status": "ok", ...}` (compatibilidad).
- `dependencies` y `ready` reflejan el estado real de las dependencias; `ready` devuelve 503
  cuando alguna dependencia crítica falla.

## Restricciones
- NO tocar `services/llm.py` salvo añadir `ping()`; NO tocar `stt.py`/`tts.py` salvo `is_ready()`;
  NO tocar `store.py` salvo `ping()`. No alterar el resto de su lógica.
- NO tocar `schemas/`, otros routers, ni el frontend.
- NO cambiar el contrato de `/api/health` existente.
- NO añadir dependencias.

## Salida
Lista de archivos creados/modificados (resumen por archivo) y la salida de
`python -m pytest tests/ -q`.
