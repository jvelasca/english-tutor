# v3.94.7 — Estudiar guarda la nota y completa la tarjeta

Release de **PRODUCTO (patch)** sobre `v3.94.6`. **CON frontend**, **SIN
migración de BD** y **SIN cambio de contrato**.

`POST /api/vocabulary/study/complete` no cambia. Sigue el `item_id` de la cola,
una nota y una sola carta FSRS.

El producto servía `frontend/dist` de antes de ese contrato. Al pulsar Bien el
cuerpo llevaba la palabra y la carta, no el `item_id`. El servidor rechazaba la
petición y la pantalla decía que no se había podido guardar.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción de Listening sigue a 0 filas.

## Qué cierra

1. **La nota.** La lección compilada envía el `item_id`. Escribir, revelar una
   sílaba o pedir otra frase no llaman al cierre.
2. **Escribir.** Oculta la palabra. Si coincide, se revela el significado. Si
   no, la carta sigue abierta.
3. **Sílaba.** Avanza un grupo vocálico. Es de la traducción mientras el
   significado está oculto, y de la palabra inglesa mientras se escribe.
4. **Frases.** La del diccionario queda la primera. «Otra frase» añade otra,
   hasta cuatro, y no borra las que ya estaban. Cada una se oye y se puede
   pasar al español. Si el modelo no responde, la lista anterior se conserva.

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

- `vitest` de `wordLesson.test.tsx`.

El pytest completo, el vitest completo y el contraste los corre la CI.
El tag anotado `v3.94.7` espera a que esa CI esté verde.
