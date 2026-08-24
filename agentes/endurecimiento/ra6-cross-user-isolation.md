# RA6 — Tests de aislamiento cross-user + tests del prompt/contexto

## Objetivo
Verificar explícitamente que un usuario nunca ve ni modifica los datos de otro en cada repositorio
y endpoint, y que el prompt personalizado solo incluye los datos del propio usuario.

## Tests a crear (`backend/tests/test_cross_user_isolation.py`)
- `test_cross_user_conversation_isolation`
- `test_cross_user_vocabulary_isolation`
- `test_cross_user_grammar_isolation`
- `test_cross_user_pronunciation_isolation`
- `test_cross_user_listening_isolation`
- `test_cross_user_learning_event_isolation`
- `test_cross_user_profile_isolation`

Cada test: crear usuario A y B, poblar datos de A y B, y comprobar que las consultas de A devuelven
solo lo de A (y viceversa), y que las mutaciones de A no afectan a B.

## Tests del prompt/contexto
- User A con error recurrente `he_she_it_s`; User B con `articles`.
- `prompt(A) != prompt(B)`, y `prompt(A)` **no** contiene los errores de B.
- `backend/tests/test_context.py` (o en el fichero de aislamiento).

## Verificación
- Backend `pytest` (todas las baterías verdes) + `ruff`.
