# P2 — Error Mastery: cometido / corregido / superado / dominado

## Rol
Subagente full-stack que convierte los errores gramaticales en un modelo de dominio: cada regla
distingue error **cometido**, uso **corregido** (evidencia positiva), **superado** (dominado) y
**recurrente** (reabierto). Añade evidencia positiva sobre la clasificación temporal existente.

## Contexto
Ya existe `services/mastery.py::classify_errors` que separa activos/resueltos **por tiempo**
(`RESOLVED_AFTER_DAYS=14`), usado por `domain/progress.py` y mostrado en `ProgressDashboard`.
Falta la **evidencia positiva**: saber que el alumno usó la forma correcta tras el error.

## Cambios (backend)
1. `repositories/db.py`: añadir a `grammar_errors` `first_seen`, `correct_after`, `streak`,
   `mastered` (CREATE TABLE + migración idempotente; backfill `first_seen = last_seen`).
2. `repositories/grammar.py`:
   - `record_errors`: `first_seen` solo en INSERT; al reincidir `streak=0, mastered=0`
     (conservando `correct_after`).
   - `record_correct_usage(user_id, rule, mastery_streak)`: incrementa `correct_after` y `streak`,
     marca `mastered` al alcanzar el umbral.
   - `get_recurring_errors`: devuelve los campos nuevos (`mastered` como bool).
3. `services/grammar.py`: `MASTERY_STREAK = 3`, `POSITIVE_PATTERNS` (`he_she_it_s`, `to_too`) y
   `find_correct_usage(text, rule)`. Solo estas reglas tienen detección determinista de uso correcto.
4. `domain/grammar.py::analyze_text`: tras registrar errores, para las reglas ya registradas (con
   patrón positivo) que no aparecen como error en el mensaje, si hay uso correcto → `record_correct_usage`.
5. `services/mastery.py::classify_errors`: un error `mastered` se considera **resuelto** (además
   del criterio temporal).
6. `domain/profile.py`: separa `recurring_errors` (activos = confirmados no dominados) de
   `mastered_errors` (confirmados dominados) + `mastered_count`. El prompt prioriza los activos.
7. `schemas/grammar.py` (`GrammarRecurringError`) y `schemas/profile.py` (`LearningProfile`):
   exponer los campos nuevos y `mastered_errors`/`mastered_count`.

## Cambios (frontend)
- `types/api.ts`: `GrammarRecurringError` con `first_seen`/`confidence`/`source`/`confirmed`/
  `correct_after`/`streak`/`mastered`; `LearningProfile` con `mastered_errors`/`mastered_count`.
- `LearningProfile.tsx`: indicador "Errores superados: N".

## Criterios de aceptación
- Backend `pytest` verde (nuevos tests de evidencia positiva, reapertura, clasificación y perfil)
  + `ruff` limpio; frontend `tsc` + `vitest` verdes.

## Restricciones
- Sin LLM, sin red. No cambia la API de endpoints existentes (solo añade campos a respuestas).
- Determinista; tests rápidos.

## Salida
- Diff backend + frontend + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde.
