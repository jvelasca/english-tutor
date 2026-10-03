# v3.94.5 — Estudiar cierra el ítem servido una sola vez

Release de **PRODUCTO (patch)** sobre `v3.94.4`. **CON backend y CON frontend**,
**CON migración aditiva** y **CON cambio de contrato** en el cierre de la lección.

Tabla nueva: `study_lesson_items`. No borra filas. `POST /api/vocabulary/study/complete`
deja de aceptar la identidad de la carta. Exige el `item_id` que devolvió
`GET /api/vocabulary/study/queue`, más la nota, la traducción y los pasos que
el alumno afirma. Palabra, tipo, id de carta y mazo salen de la fila servida.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción de Listening sigue a 0 filas.
**`v3.94.4` no se etiqueta como cierre** de Estudiar.

## Qué cierra

1. **Una acción, una carta.** La cola guarda cada ítem. Cerrarlo agenda la
   carta que se estudió y escribe una fila en el libro de repasos. Repetir el
   mismo `item_id` responde con el resultado ya guardado: no hay un segundo
   `schedule` ni una segunda fila. Una ficha manual califica `flashcard:<id>`
   y crea la carta `lexicon` sin nota (`reps=0`), así que entra en el léxico
   como no estudiada. El ámbito léxico califica solo `lexicon:<palabra>`.
2. **El cierre es una transacción.** Alta en el léxico, pasos, FSRS, libro de
   repasos, evento y la marca de ítem completado se confirman juntos. Si algo
   falla, el ítem sigue abierto y no queda léxico ni FSRS a medias. Si la ficha
   ya no pertenece al mazo, no se agenda nada.
3. **«Aprendida» queda definida.** Se calcula sobre la carta que recibió la
   nota y los `required_facets` vigentes. No es un hecho histórico: vaciar esa
   lista puede contar la palabra sin un repaso nuevo. `state == review` no es
   mastery. Los pasos los afirma el cliente al cerrar; saltar uno lo deja
   `pending`.

## Qué no cierra

- El ledger de producción de Listening sigue sin volumen.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable ni FSRS por acepción.
- Los **ocho gates humanos siguen `pending`**.
- Colección y nivel se pueden pedir juntos al backend. Con una colección
  activa, la UI sigue forzando el ámbito «todo el léxico».

## Verificación local

- `pytest` de `backend/tests/test_study_bank.py` y
  `backend/tests/test_study_complete_v3945.py`: **15/15**.
- `vitest` de `FlashcardsScreen.test.tsx` y `wordLesson.test.tsx`: **30/30**.

El pytest completo, el vitest completo y el contraste los corre la CI.
El tag anotado `v3.94.5` espera a que esa CI esté verde. Hasta entonces la
*Latest* sigue siendo `v3.94.2`.
