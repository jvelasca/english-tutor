# v3.94.2 — Dos sentidos en la misma frase no se colapsan, y la polisemia queda fijada en CI

Release de **PRODUCTO (patch)** sobre `v3.94.1`. **CON backend y CON frontend**
(la Ayuda parte los textos largos; el barrido responsive incluye Formación),
**SIN migración de BD**, **SIN endpoints nuevos** y **SIN cambio de contrato
incompatible**: `sense_match` sigue siendo `matched` / `mismatch` /
`ambiguous`. La razón nueva es `occurrence:split`. `new_sense_exposure:
{words, count}` conserva su forma.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

## Qué cierra

1. **Conflicto de ocurrencias.** Si una aparición de la palabra es `mismatch`
   probado y otra no, la palabra no hereda la de mayor margen. El agregado es
   `ambiguous` / `occurrence:split` / `mismatch_strength="possible"`. No es
   `new_sense_exposure`.
2. **Carta débil y carta fuerte.** La débil **sí** sube de dificultad: la duda
   no resta. La fuerte deja una fila con `difficulty_before ==
   difficulty_after` y no toca FSRS. `day_metrics` no cuenta esa fila ni como
   dificultad ni como exposición. `occurrences` vive en memoria; no hay
   columna nueva. La clave de evidencia sigue siendo
   `user:question:word:attempt`.
3. **Corpus de regresión.**
   `backend/tests/fixtures/sense_regression_corpus.json`: 95 frases y 15
   familias (`bank`, `charge`, `right`, `match`, `point`, `light`, `mean`,
   `issue`, `case`, `change`, `break`, `run`, `set`, `turn`, `play`). CI
   falla si el resolver se aparta de `resolver_expected`. El `gold` humano
   puede diferir. Hoy discrepan `bank-07` (hipoteca), `bank-08` (la frase
   mixta de la auditoría), `bank-10` (`official organization`) y `run-07`
   (`business operation`).
4. **Telemetría.** `scripts/sense_shadow_report.py` cuenta `occurrence_split`
   junto a `possible_mismatch`. Un conflicto no suprime evidencia
   (`allows_difficulty_evidence` sigue en verdadero salvo `mismatch` probado).
5. **Ayuda y responsive.** Los textos y el correo de la Ayuda parten línea.
   El barrido de desborde horizontal incluye `/#/formacion`.

## Qué no es

- El umbral de 2 tokens **no** se convierte en confianza semántica. Sigue
  siendo solape de glosa.
- La frase de la auditoría («The bank by the river was closed, but the bank
  approved my loan.») **no** parte el veredicto con las glosas actuales: la
  primera aparición solo solapa un token. El caso que sí parte es «On the
  river side, the bank was covered in mud, but I put my money in the bank.»
  Queda fijado en el corpus (`bank-09` coincide con el `gold`; `bank-08`
  discrepa a propósito).
- El corpus mide el software. El ledger de producción sigue sin volumen: la
  política está **declarada, no medida** con alumnos.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable, ni sentido nuevo pedagógico, ni FSRS por
  acepción. Eso queda para V3.95 y V3.96.
- No hay puntuación compuesta ni modelo. ENFORCE se mantiene conservador.

## Verificación local

- `ruff` limpio en los ficheros de backend tocados.
- `pytest` del backend: **3496/3496**.
- `vitest` de la Ayuda: **3/3**.
- Playwright `responsiveOverflow`: **4 passed · 2 skipped** (320 px solo en
  el proyecto mobile), a 320, 390, 768 y 1280 px, sin backend (estados
  vacíos).
- `scripts/check_release_consistency.py`: los seis orígenes en `3.94.2`.

El resto (vitest completo, `tsc`, build, contraste) lo corre la CI. El tag
anotado `v3.94.2` espera a que esa CI esté verde.
