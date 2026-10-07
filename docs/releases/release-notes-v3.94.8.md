# v3.94.8 — Iconos, frase, lápiz y fallo en Estudiar

Release de **PRODUCTO (patch)** sobre `v3.94.7`. **CON frontend**, **SIN
migración de BD** y **SIN cambio de contrato**.

`POST /api/vocabulary/study/complete` no cambia. Sigue el `item_id` de la cola,
una nota y una sola carta FSRS.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción de Listening sigue a 0 filas.

## Qué cierra

1. **Iconos.** Cada acción de la tarjeta lleva un icono y su nombre. Las cuatro
   notas también.
2. **Frase.** El ejemplo del diccionario se abre en el anverso. Se oye y se
   puede pasar al español. No revela el significado y no agenda.
3. **Lápiz.** En una ficha manual abre Tarjetas con el editor de esa ficha. En
   una palabra del léxico guarda la traducción. No agenda.
4. **«¿Cuál es?».** La primera opción incorrecta queda en rojo, muestra el
   significado y guarda Otra vez una sola vez. Siguiente avanza sin otra nota.
   Escribir mal la palabra sigue sin cerrar.

## Qué no cierra

- El ledger de producción de Listening sigue sin volumen.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable ni FSRS por acepción.
- Los **ocho gates humanos siguen `pending`**.
- Colección y nivel se pueden pedir juntos al backend. Con una colección
  activa, la UI sigue forzando el ámbito «todo el léxico».
- Siguen aparcados los tres P2 de V3.94.6: que la traducción generada
  corresponda a la frase, distinguir ejemplo cargado de ejemplo visto, y un
  cupo propio para «Otra frase».

## Verificación local

- `vitest` de `wordLesson.test.tsx`, 14/14.

El pytest completo, el vitest completo y el contraste los corre la CI.
El tag anotado `v3.94.8` espera a que esa CI esté verde.
