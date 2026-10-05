# v3.94.10 — Dos sentidos, temas como mazos y rejilla

Release de **PRODUCTO (patch)** sobre `v3.94.9`. **CON backend y CON
frontend**, **CON migración aditiva** (`flashcard_decks.source_collection_id`)
y **SIN cambio de contrato** en el cierre de Estudiar.

`POST /api/vocabulary/study/complete` no cambia. Sigue el `item_id` de la cola,
una nota y una sola carta FSRS.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción de Listening sigue a 0 filas.
Los tres P2 de V3.94.6 siguen aparcados.

Este envío a GitHub lleva también `v3.94.7`, `v3.94.8` y `v3.94.9`, que
estaban en el árbol local y aún no tenían commit.

## Qué cierra

1. **Dos sentidos.** Español → Inglés estudia el lema inglés. Escribir lo
   compara con ese lema. La sílaba, mientras se escribe, parte el inglés. El
   español se oye solo en la voz de España. El sentido está en la cabecera.
2. **Donuts.** A repasar, No aprendidas, Difíciles, Bien y Todas eligen la
   cola. La cuarta nota sigue llamándose Fácil. Aprendida sigue siendo el
   estado derivado.
3. **Temas.** Dieciocho temas de cien palabras. Cada tema tomado es un mazo
   ligado a su colección (`source_collection_id`) y no se borra. Un mazo del
   alumno sí. Pegar una lista crea un mazo propio. El listado devuelve el
   `slug` del tema para el icono.
4. **Rejilla.** Mazos muestra icono, nombre y número de palabras. El panel de
   abajo lleva los datos y las acciones. Crear y pegar están en Añadir.
   Tarjetas usa la misma rejilla. Estadísticas sigue el diccionario entero.
5. **Crecimiento del catálogo.** Una palabra nueva del JSON entra con
   `INSERT OR IGNORE`. No reescribe la traducción ni la nota de una palabra
   que ya estaba.

## Qué no cierra

- El ledger de producción de Listening sigue sin volumen.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable ni FSRS por acepción.
- Los **ocho gates humanos siguen `pending`**.
- `CURRICULUM_VERSION` no sube. El catálogo crece al listar los mazos, no por
  un cambio de versión del currículo.
- Siguen aparcados los tres P2 de V3.94.6: que la traducción generada
  corresponda a la frase, distinguir ejemplo cargado de ejemplo visto, y un
  cupo propio para «Otra frase».
- El tag anotado `v3.94.10` espera a que la CI de esta PR esté verde. La
  *Latest* publicada sigue siendo `v3.94.2`.

## Verificación local

- `vitest` de `FlashcardsScreen.test.tsx`, 34/34.
- `pytest` de `test_bulk_and_enroll_theme_pack`, 1/1 (el mazo del tema trae
  el `slug`).

El pytest completo, el vitest completo y el contraste los corre la CI.
