# RA4 — Vocabulario: `occurrences` → `appearances`

## Objetivo
El extractor usa un `set`, así que cada palabra cuenta una vez por mensaje. El campo `occurrences`
es engañoso. Renombrar a `appearances` para reflejar "número de mensajes en los que apareció la
palabra".

## Cambios
- `backend/repositories/db.py`: `CREATE TABLE IF NOT EXISTS vocabulary` usa `appearances`;
  añadir migración idempotente que renombra `occurrences` → `appearances` si existe la columna
  antigua.
- `backend/repositories/vocabulary.py`: reemplazar `occurrences` → `appearances` en SQL y docstrings.
- `backend/schemas/vocabulary.py`: `VocabularyItem.occurrences` → `appearances`.
- `backend/domain/vocabulary.py`: actualizar cualquier referencia.

## Tests
- `backend/tests/test_vocabulary.py`: renombrar y añadir test de la migración
  `occurrences` → `appearances`.

## Nota pedagógica (no implementar ahora)
Queda pendiente separar *exposure* / *production* / *mastery* en una fase pedagógica futura.

## Verificación
- Backend `pytest` + `ruff`.
