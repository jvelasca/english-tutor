# v3.94.6 — Estudiar muestra la palabra y el significado se revela

Release de **PRODUCTO (patch)** sobre `v3.94.5`. **CON backend y CON frontend**,
**SIN migración de BD** y **CON un endpoint nuevo**.

`POST /api/vocabulary/study/complete` no cambia. Sigue el `item_id` de la cola,
una nota y una sola carta FSRS. La cola gana `mnemonic`, un campo aditivo: el
recordatorio de la ficha manual o del léxico. El complete no lo lee.

`POST /api/vocabulary/study/example` pide al modelo local otra frase en inglés
que contenga la palabra y su traducción al español. No escribe léxico, FSRS,
repasos ni `study_lesson_items`.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción de Listening sigue a 0 filas.

## Qué cierra

1. **Una tarjeta.** Se ve la palabra en inglés. El significado permanece
   oculto hasta revelarlo, acertar entre las opciones o seguir las pistas.
   Oír la palabra no enseña el significado. Cada pista descubre la siguiente
   palabra de la traducción, o tres letras si es una sola. El recordatorio
   solo aparece si existe. Seis opciones salen cuando la sesión tiene seis
   traducciones distintas: fallar no cierra la carta; acertar revela.
2. **La nota no cambia de sitio.** Otra vez, Difícil, Bien y Fácil siguen
   siendo lo único que agenda FSRS. El significado queda hecho al revelar.
   La pronunciación queda hecha solo si se oyó. El contexto queda hecho solo
   si se vio un ejemplo. El resto no se marca hecho por pasar de largo.
3. **Otra frase.** Si el diccionario ya tiene ejemplo, se muestra al momento,
   con altavoz. «Otra frase» pide una nueva. Si el modelo no responde, se
   conserva la anterior y se avisa.

## Qué no cierra

- El ledger de producción de Listening sigue sin volumen.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable ni FSRS por acepción.
- Los **ocho gates humanos siguen `pending`**.
- Colección y nivel se pueden pedir juntos al backend. Con una colección
  activa, la UI sigue forzando el ámbito «todo el léxico».

## Verificación local

- `pytest` de `backend/tests/test_study_bank.py`,
  `backend/tests/test_study_complete_v3945.py` y
  `backend/tests/test_study_example_v3946.py`.
- `vitest` de `wordLesson.test.tsx` y `FlashcardsScreen.test.tsx`.

El pytest completo, el vitest completo y el contraste los corre la CI.
El tag anotado `v3.94.6` espera a que esa CI esté verde. Hasta entonces la
*Latest* sigue siendo `v3.94.2`.
