# P1 — Política pedagógica formal (CORRECT / NATURAL / OPTIONAL / STYLE / PRONUNCIATION)

## Rol
Subagente backend (puro, determinista) que codifica una política pedagógica de corrección
estricta y la integra en el system prompt del tutor.

## Contexto
El prompt actual dice "correct mistakes gently" y "explain briefly", sin distinguir un error real
de una frase correcta pero poco natural, de una variante opcional o de una cuestión de estilo.
Necesitamos una taxonomía formal para que el tutor no señale como error lo que no lo es
(auditoría externa, punto 31).

Arquitectura congelada (`routers → domain → repositories → SQLite`; `services` puros). Este
cambio es **solo de prompt**, no toca BD ni API.

## Archivos
- `backend/services/policy.py` (puro): hoy tiene `CORRECTNESS_GUIDANCE` + `correctness_guidance()`.
- `backend/services/context.py`: `build_system_prompt(mode, profile)`.
- Tests: `backend/tests/test_policy.py`, `backend/tests/test_context.py`,
  `backend/tests/test_chat_profile.py`, `backend/tests/test_chat_integration.py`.

## Tarea
1. En `services/policy.py` añadir:
   - `FEEDBACK_CATEGORIES: dict[str, str]` con las 5 categorías (claves en mayúscula):
     `CORRECT`, `NATURAL`, `OPTIONAL`, `STYLE`, `PRONUNCIATION` (descripciones cortas en inglés).
   - `feedback_policy() -> str` que devuelve un bloque de instrucciones: "clasifica cada
     corrección con exactamente una categoría" + lista de categorías + "solo corrige errores
     reales; nunca marques como error lo natural, opcional o de estilo".
2. En `services/context.py`, integrar `feedback_policy()` en `build_system_prompt` de forma
   **siempre activa** (con y sin perfil): `parts = [base, feedback_policy()]` y, si hay perfil,
   añadir después la guía por nivel, errores recurrentes y recomendaciones.
3. Actualizar los tests que asumían `build_system_prompt(mode, None/None-profile) == MODE_PROMPTS`:
   ahora el prompt es `base + "\n" + feedback_policy()`. Usar `startswith(MODE_PROMPTS[...])` y
   comprobar que las categorías (`CORRECT`, `NATURAL`, `OPTIONAL`, `STYLE`, `PRONUNCIATION`)
   aparecen. Archivos afectados:
   - `test_context.py` (`test_no_profile_returns_base_mode_prompt`,
     `test_unknown_mode_falls_back_to_conversation`, `test_empty_profile_returns_base_mode_prompt`).
   - `test_chat_profile.py::test_chat_without_user_id_uses_base_prompt` (assert `sent == ...`).
   - `test_chat_integration.py::test_chat_ok_injects_system_prompt_and_mode` y
     `test_chat_unknown_mode_falls_back_to_conversation` (assert de `sent[0]["content"] == ...`).
4. Añadir tests en `test_policy.py`:
   - `feedback_policy()` no vacía y contiene las 5 categorías.
   - `FEEDBACK_CATEGORIES` tiene exactamente las 5 claves.
   - determinismo: dos llamadas devuelven lo mismo.
5. Añadir un test en `test_context.py`: el prompt con perfil incluye la política de feedback
   además de la guía por nivel.

## Criterios de aceptación
- `feedback_policy()` es puro y determinista; contiene las 5 categorías.
- `build_system_prompt` siempre incluye la política; con perfil incluye además nivel + errores + recs.
- Backend `pytest` verde y `ruff check .` limpio.

## Restricciones
- Sin LLM, sin red, sin cambios de BD ni de API.
- No tocar `services/llm.py::system_prompt_for` ni `config.py::MODE_PROMPTS`.
- Mantener los tests rápidos y deterministas.

## Salida
- Diff de los 5 archivos + resultado de `pytest` y `ruff` en verde.
