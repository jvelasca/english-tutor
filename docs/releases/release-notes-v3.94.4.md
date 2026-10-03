# v3.94.4 — Estudiar lee el ámbito, y Flashcards deja de resembrar el léxico

Release de **PRODUCTO (patch)** sobre `v3.94.3`. **CON backend y CON frontend**,
**CON migración aditiva** y **CON endpoints nuevos**.

Columnas nuevas, con defecto vacío: `vocabulary.cefr`, `vocabulary.lesson_facets`
y `dictionary_entries.cefr`. No borran filas. Endpoints nuevos:
`GET /api/vocabulary/study/summary`, `GET /api/vocabulary/study/queue` y
`POST /api/vocabulary/study/complete`. La cola antigua de un mazo
(`GET /api/vocabulary/decks/{id}/queue`) sigue existiendo.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción de Listening sigue a 0 filas.

## Qué cierra

1. **El mazo es el mazo.** Elegir Herramientas ya no abre el repaso de las 50
   vencidas del léxico. Pendientes son las ya estudiadas y vencidas de ese
   ámbito. Falladas son las cuya última nota fue Otra vez. Todas de nuevo
   recorre el ámbito, con las vencidas primero, cortado por «palabras hoy».
   Calificar actualiza la carta y no reinicia el progreso.
2. **Una lección.** Palabra nueva: significado, pronunciación, contexto y, si
   el diccionario los trae, acepciones y una forma relacionada. Cada paso se
   puede saltar. Palabra ya estudiada: evocación corta y la nota. Al cerrar,
   la palabra entra en el léxico. Estudiar lleva con iconos a Mi léxico,
   Mazos, Tarjetas y Estadísticas.
3. **Abrir Flashcards no reescribe el léxico por cada mazo.** La siembra FSRS
   ocurre una vez por listado. Una carta cuyo motivo y etiqueta no cambian no
   se vuelve a guardar. La cola y los contadores salen de una sola lectura, y
   las traducciones de la sesión se piden juntas.

## Qué no cierra

- El ledger de producción de Listening sigue sin volumen.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable ni FSRS por acepción.
- Los **ocho gates humanos siguen `pending`**.

## Verificación local

- `pytest` de `backend/tests/test_study_bank.py`: **8/8**.
- `vitest` de `FlashcardsScreen.test.tsx` y `wordLesson.test.tsx`: **30/30**.
- `npm run build` (`tsc` y Vite) correcto.

El pytest completo, el vitest completo y el contraste los corre la CI.
El tag anotado `v3.94.4` espera a que esa CI esté verde y a la auditoría
externa. Hasta entonces la *Latest* sigue siendo `v3.94.2`.
