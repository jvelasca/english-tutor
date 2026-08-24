# Subagente F5.2 — Context Builder + perfil al prompt

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Hacer que el **perfil del alumno entre al system prompt del tutor**. Añadir un Context Builder
(`services/context.py`) que compone `prompt del modo + política de corrección (F5.1) + errores
recurrentes + áreas de enfoque`, y cablearlo en `/api/chat` y `/api/chat/stream`. El `user_id`
será **opcional** en `ChatRequest` para no romper el frontend (que aún no lo envía; F5.3 lo
propagará). Si no hay `user_id` o el usuario no existe, se usa el prompt base (sin personalizar).

## Contexto (autocontenido)
- `backend/services/policy.py` (F5.1): `correctness_guidance(cefr_level)`.
- `backend/config.py`: `MODE_PROMPTS` (dict modo→prompt), `DEFAULT_MODE`.
- `backend/schemas/chat.py`: `ChatRequest` (messages, model, temperature, mode).
- `backend/services/llm.py` (LEERLO): `system_prompt_for(mode)`, `_messages(messages, mode)`,
  `chat_once(messages, model, temperature, mode)`, `chat_stream(...)`. `get_client()` inyectable.
- `backend/routers/chat.py` (LEERLO): `/api/chat` y `/api/chat/stream` llaman a
  `chat_once`/`chat_stream` sin system prompt propio.
- `backend/domain/profile.py` (LEERLO): `get_profile_summary(user_id)` compone el perfil y
  persiste el CEFR (llama a `profile_repo.set_cefr`). Devuelve `None` si el usuario no existe.
- `backend/tests/test_chat_integration.py`: patrón `FakeOllamaClient` + `monkeypatch.setattr(llm,
  "get_client", ...)`.
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/context.py` (nuevo)
```python
"""Construcción del system prompt del tutor a partir del modo y el perfil."""
from __future__ import annotations

from config import DEFAULT_MODE, MODE_PROMPTS
from services.policy import correctness_guidance

MAX_ERRORS_IN_PROMPT = 3
MAX_RECS_IN_PROMPT = 3


def build_system_prompt(mode: str, profile: dict | None = None) -> str:
    """Compone el system prompt: prompt base del modo + política de corrección por
    CEFR + errores recurrentes + áreas de enfoque. Sin perfil, solo el base."""
    base = MODE_PROMPTS.get(mode, MODE_PROMPTS[DEFAULT_MODE])
    if not profile:
        return base

    parts = [base]

    level = profile.get("cefr_level")
    if level:
        parts.append(correctness_guidance(level))

    errors = profile.get("recurring_errors") or []
    if errors:
        top = "; ".join(e["message"] for e in errors[:MAX_ERRORS_IN_PROMPT])
        parts.append(
            f"The learner's most frequent mistakes: {top} "
            "Prioritize correcting these patterns."
        )

    recs = profile.get("recommendations") or []
    if recs:
        parts.append("Learner focus areas: " + "; ".join(recs[:MAX_RECS_IN_PROMPT]))

    return "\n".join(parts)
```

### 2. `backend/domain/profile.py` — extraer `_compute_profile` y añadir `get_profile_context`
Refactor sin cambio de comportamiento: mueve el cuerpo de `get_profile_summary` a
`_compute_profile(user_id)` (sin la escritura de CEFR). Luego:
```python
async def get_profile_summary(user_id: str) -> dict | None:
    """Compone el perfil del alumno y persiste el CEFR estimado como caché."""
    profile = await _compute_profile(user_id)
    if profile is None:
        return None
    await run_in_threadpool(profile_repo.set_cefr, user_id, profile["cefr_level"])
    return profile


async def get_profile_context(user_id: str) -> dict | None:
    """Devuelve el perfil para construir el prompt del tutor (sin persistir)."""
    return await _compute_profile(user_id)
```
> Los tests de F4 (`test_profile.py`) deben seguir verdes: `get_profile_summary` mantiene forma
> y sigue persistiendo el CEFR.

### 3. `backend/schemas/chat.py` — `user_id` opcional
En `ChatRequest`, añade `user_id: str | None = None`.

### 4. `backend/services/llm.py` — aceptar `system_prompt`
- `_messages(messages, mode=DEFAULT_MODE, system_prompt=None)`: usa `system_prompt` si viene
  dado, si no `system_prompt_for(mode)`.
- `chat_once(...)` y `chat_stream(...)`: añade parámetro `system_prompt: str | None = None` y
  pásalo a `_messages`. Comportamiento por defecto intacto.

### 5. `backend/routers/chat.py` — resolver perfil y construir prompt
Añade helper y úsalo en ambos endpoints:
```python
from domain import profile as profile_service
from services.context import build_system_prompt


async def _system_prompt(req: ChatRequest) -> str:
    profile = None
    if req.user_id:
        profile = await profile_service.get_profile_context(req.user_id)
    return build_system_prompt(req.mode, profile)
```
`chat` pasa `await _system_prompt(req)` como `system_prompt` a `chat_once`; `chat_stream_endpoint`
calcula `system_prompt = await _system_prompt(req)` antes de `generate()` y se lo pasa a
`chat_stream`.

### 6. Tests
`backend/tests/test_context.py` (puro):
- `test_no_profile_returns_base_mode_prompt`
- `test_unknown_mode_falls_back_to_conversation`
- `test_profile_includes_cefr_guidance`
- `test_profile_includes_recurring_errors`
- `test_profile_includes_recommendations`

`backend/tests/test_chat_profile.py` (integración con `FakeOllamaClient` propio y
`monkeypatch.setattr(llm, "get_client", ...)`):
- `test_chat_with_user_id_personalizes_prompt` (siembra un error gramatical, verifica que el
  system prompt enviado contenga "CEFR" y el mensaje del error).
- `test_chat_without_user_id_uses_base_prompt` (system prompt == `MODE_PROMPTS["conversation"]`).
- `test_chat_unknown_user_id_uses_base_prompt`.
- `test_chat_stream_with_user_id_personalizes` (mismo aserto sobre `chat_stream`).

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 127 tests** (118 previos + 9 nuevos).
- `python -m ruff check .` **sin errores**.

## Restricciones
- NO tocar el frontend.
- NO cambiar el comportamiento por defecto de `/api/chat` sin `user_id` (sigue igual).
- NO tocar `services/policy.py`, `repositories/`, `schemas/` salvo `schemas/chat.py`.
- Mantener estilo (docstrings en español, `from __future__ import annotations`, ruff limpio).

## Salida
Lista de archivos creados/modificados, salida de `python -m pytest tests/ -q`, de
`python -m ruff check .`, y cualquier desviación.
