# Subagente E2.4 — CI + dependencias reproducibles + CORS restringido

## Rol
Programador backend Python (FastAPI) con nociones de DevOps/GitHub Actions. Sin acceso a Git
(sin commits) ni al código del frontend (solo leer su `package.json` si hace falta).

## Objetivo
Cerrar la Fase 2 (P1) con tres mejoras de infraestructura:
1. **CORS restringido**: pasar de `allow_origins=["*"]` a solo los orígenes de desarrollo local.
2. **Dependencias reproducibles**: `requirements.in` (intención, rangos) + `requirements.txt`
   (versiones exactas conocidas que funcionan) + `requirements-dev.txt` (pinned, + `ruff`).
3. **CI con GitHub Actions**: backend (ruff + pytest) y frontend (tsc + vitest + build).

## Contexto (autocontenido)
- El repo vive en `e:\SINCRONIZADO\Informatica\Proyectos Cursor\Ingles con IA`.
- `backend/requirements.txt` hoy usa `>=` (abierto); `requirements-dev.txt` añade `pytest>=8.0.0`
  y `httpx>=0.27.0`. NO hay `requirements.in`, NO hay `pyproject.toml`, NO hay `.github/`.
- `backend/main.py` monta CORS con `allow_origins=["*"]`.
- Versiones YA instaladas y verificadas en este entorno (Python 3.13.7, Node 22):
  `fastapi==0.128.0`, `uvicorn==0.40.0`, `ollama==0.6.2`, `python-multipart==0.0.32`,
  `faster-whisper==1.2.1`, `piper-tts==1.7.0`, `pytest==8.4.2`, `httpx==0.28.1`, `ruff==0.16.3`.
- `frontend/package-lock.json` existe (así que CI puede usar `npm ci`).
- Verificación local (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```
  (ruff se invoca como `python -m ruff`, no como `ruff` en PATH).

## Tarea detallada

### 1. CORS restringido
**`backend/config.py`** — añadir tras `DEFAULT_MODEL`:
```python
# Orígenes permitidos para CORS (solo el frontend de desarrollo local).
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
```

**`backend/main.py`** — usar la constante y ordenar imports (isort). El bloque de imports queda:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import ALLOWED_ORIGINS
from routers.chat import router as chat_router
from routers.conversations import router as conversations_router
from routers.health import router as health_router
from routers.models import router as models_router
from routers.progress import router as progress_router
from routers.pronunciation import router as pronunciation_router
from routers.users import router as users_router
from routers.voz import router as voz_router
from services.store import init_db
```
Y en el middleware:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Dependencias reproducibles
**`backend/requirements.in`** (nuevo) — intención de dependencias (rangos):
```text
# Dependencias directas (intención). Genera/pina las versiones en requirements.txt.
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
ollama>=0.4.0
python-multipart>=0.0.12
faster-whisper>=1.2.0
piper-tts>=1.7.0
```

**`backend/requirements.txt`** (sobrescribir) — versiones exactas conocidas que funcionan:
```text
fastapi==0.128.0
uvicorn[standard]==0.40.0
ollama==0.6.2
python-multipart==0.0.32
faster-whisper==1.2.1
piper-tts==1.7.0
```

**`backend/requirements-dev.txt`** (sobrescribir) — pinned + ruff:
```text
-r requirements.txt
pytest==8.4.2
httpx==0.28.1
ruff==0.16.3
```

### 3. Config determinista de ruff (NO depender del config del usuario)
**`backend/pyproject.toml`** (nuevo):
```toml
[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B"]
ignore = ["B008"]  # Query/Form/File/Depends de FastAPI son llamadas en default args
```

Después de crear este config, corrige los issues existentes:
```powershell
python -m ruff check . --fix
python -m ruff check .
```
`--fix` arreglará los `F401` (imports no usados, p.ej. `from pathlib import Path` en
`download_models.py`) y los `I001` (orden de imports). Si queda algún error restante, LEE el
archivo y arréglalo a mano. Resultado esperado: **0 errores** de `ruff check .`.
> NO borres los comentarios `# noqa: BLE001` (son inofensivos sin la regla RUF/BLE; no los
> necesitas tocar). No selecciones RUF/BLE/UP.

### 4. CI con GitHub Actions
**`.github/workflows/ci.yml`** (nuevo, en la raíz del repo):
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    name: Backend (ruff + pytest)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: backend/requirements-dev.txt
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements-dev.txt
      - name: Lint (ruff)
        run: python -m ruff check .
      - name: Test (pytest)
        run: python -m pytest tests/ -q

  frontend:
    name: Frontend (tsc + vitest + build)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Type check
        run: npx tsc --noEmit
      - name: Test (vitest)
        run: npm test
      - name: Build
        run: npm run build
```

### 5. Test nuevo `backend/tests/test_cors.py`
```python
from fastapi.testclient import TestClient

from main import app


def test_cors_allows_localhost_5173():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_allows_127_0_0_1_5173():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
        assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_rejects_unknown_origin():
    with TestClient(app) as client:
        r = client.get("/api/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in r.headers
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde** (59 previos + 3 nuevos = 62 tests).
- `python -m ruff check .` desde `backend/` termina **sin errores**.
- `ci.yml` es YAML válido (valida con `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`
  desde la raíz; si `yaml` no está, léelo una vez y revisa indentación).

## Restricciones
- NO tocar el código del frontend ni `frontend/package.json`/`package-lock.json`.
- NO tocar `services/`, `schemas/`, `routers/` (salvo `main.py` y `config.py` indicados).
- NO añadir reglas de ruff más allá de las indicadas; NO seleccionar RUF/BLE/UP.
- NO cambiar versiones de `requirements.txt` por otras distintas de las dadas.
- NO hacer commit en git.

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, la salida de `python -m ruff check .`, y cualquier desviación.
