# RA5 — Gramática: `confidence` / `source` / `confirmed`

## Objetivo
El detector heurístico no debe tratar cada hallazgo como un error confirmado. Introducir
`confidence`, `source` y `confirmed`, y filtrar el prompt del tutor a errores confirmados para
evitar que falsos positivos contaminen el Learning Profile.

## Cambios
- `backend/services/grammar.py`: añadir `confidence` a cada regla de `RULES`, una
  `CONFIRMED_THRESHOLD`, y que `find_errors` devuelva `confidence`, `source`, `confirmed`
  (`confirmed = confidence >= CONFIRMED_THRESHOLD`).
- `backend/schemas/grammar.py`: `GrammarFinding` y `GrammarRecurringError` con `confidence`,
  `source`, `confirmed`.
- `backend/repositories/grammar.py`: `record_errors` guarda los campos nuevos; `get_recurring_errors`
  los recupera.
- `backend/repositories/db.py`: migración idempotente para `confidence`, `source`, `confirmed`.
- `backend/services/context.py`: `build_system_prompt` filtra `recurring_errors` por
  `confirmed=True`.

## Tests
- `backend/tests/test_grammar.py`: tests de `confidence` y `confirmed` en `find_errors` y
  `record_errors`.
- `backend/tests/test_context.py`: test de que solo errores confirmados entran en el prompt
  (`test_profile_excludes_unconfirmed_errors`).

## Verificación
- Backend `pytest` + `ruff`.
