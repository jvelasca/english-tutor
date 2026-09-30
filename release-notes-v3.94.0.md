# Release notes — English Tutor v3.94.0

**Fecha:** 2026-09-30 · **Tipo:** release de **PRODUCTO** (minor) · **Versión de app:**
`3.93.2 → 3.94.0`

**Con backend y SIN frontend**, **SIN migración de BD** (el ledger de V3.93 ya tenía
`sense_key` / `sense_match` / `sense_reason`), **SIN endpoints nuevos** y **SIN cambio de
contrato incompatible**: `new_sense_exposure` es un campo **aditivo** de
`POST /api/listening/answer`, y `difficulty_evidence` conserva su forma `{words, count}`.
`GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue
`1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json` **sigue
sin existir**.

**En una frase.** El puente Listening → evidencia deja de ser *lemma-based* y **decide con
la acepción**: un `mismatch` **probado** —la frase usa otra acepción de una palabra que el
alumno ya tiene— ya **no** sube la dificultad de la acepción aprendida; se registra como
`new_sense_exposure`. Todo lo demás conserva exactamente la evidencia de V3.92.

---

## 1. Qué fase es esta

SENSE-CONTEXT-01 llegó en **dos tiempos** deliberados:

| Fase | Versión | Qué hace |
|---|---|---|
| *Dark launch* | V3.93.0 | El resolver se **consulta** y su veredicto se **guarda** en el ledger; la evidencia no cambia |
| **ENFORCE** | **V3.94.0** | El resolver **decide**: el veredicto condiciona la evidencia |

V3.93.1 y V3.93.2 fueron los dos patches de robustez que cerraron la atomicidad y la
idempotencia de la escritura. Con el terreno firme, ENFORCE ya se puede aplicar.

## 2. El agujero que quedaba (por eso «aplicar la política» no bastaba)

En V3.93 el resolver se consultaba así:

```python
sense_context.classify_sense_evidence(word, text, senses.get(word), senses=())
```

`senses=()` significa **sin alternativas conocidas**. Y `mismatch` **exige** una
alternativa contra la que comparar: sin ella, el resolver solo puede devolver `matched` o
`ambiguous`. **`mismatch` era inalcanzable**, así que activar la política habría sido un
**no-op silencioso**: el código parecería hacer algo y no haría nada.

**El arreglo (`services/listening_bridge.py::alternatives_index`).** Un helper **puro**
que convierte la salida de `dictionary_repo.find_by_words` en
`{palabra canónica: [acepciones conocidas]}`. El puente lo consulta **una vez** por
intento (`domain/listening.py`) y reparte las alternativas de cada palabra al resolver:

```python
verdict = sense_context.classify_sense_evidence(
    word, text, senses.get(word), senses=alternatives.get(word, ())
)
```

Sin alternativas conocidas el veredicto sigue siendo `ambiguous`: **nunca se inventa** una
acepción distinta para declarar un `mismatch`.

## 3. La política (mínima, y declarada como decisión)

`services/sense_context.py::allows_difficulty_evidence` es una función **pura y total**:

```python
def allows_difficulty_evidence(verdict: object) -> bool:
    return not is_new_sense_exposure(verdict)
```

| Veredicto | ¿Aplica dificultad? | Por qué |
|---|---|---|
| `matched` | **Sí** | Hay evidencia léxica de que el contexto **es** la acepción aprendida |
| `mismatch` | **No** | Hay prueba de una acepción **distinta**: subir la carta aprendida señalaría la carta equivocada |
| `ambiguous` (`declared:none`, `alternatives:none`, `tie`, `occurrence:none`) | **Sí** | **No hay prueba** de una acepción distinta: la duda no **resta** evidencia igual que no la **fabrica** |
| sin veredicto (`None`) | **Sí** | Se comporta como antes de V3.94 |

**Por qué `declared:none` conserva la evidencia, y por qué eso es una DECISIÓN.** El caso
dominante del ledger es `declared:none` —palabras que el alumno nunca dio de alta con qué
acepción—. El diseño de SENSE-CONTEXT-01 proponía «solo `matched` genera evidencia», y él
mismo advirtió de que tratar `declared:none` como `ambiguous` **«apagaría la mayor parte
del puente»**. Con el ledger a **0 filas** no hay datos para medir la pérdida, así que
V3.94 elige la política **mínima** —quitar solo lo que puede **probar**— y deja el
instrumento para revisarla. Es **reversible**: volver al diseño estricto es
`match == matched`.

## 4. La exposición se registra, no se castiga

Un `mismatch` **sí** deja rastro: es información valiosa («el alumno se topó con otro
sentido de una palabra que ya tiene»). La fila entra en
`listening_difficulty_evidence` con `sense_match='mismatch'`, su `sense_key`/`sense_reason`
y **`difficulty_before == difficulty_after`** —la carta no se tocó—, y es **idempotente**
por la clave del intento: repetir el mismo intento **no** reexpone.

Dos consecuencias de contrato:

- `POST /api/listening/answer` publica `new_sense_exposure: {words, count}` (**aditivo**);
- `services/daily_plan.py::day_metrics` **no** cuenta esas filas como dificultad: separa
  `applied` (subieron carta) de `sense_exposures` (`mismatch`) y publica las dos cifras
  aparte. Contarlas juntas mentiría: no subió ninguna carta.

## 5. Superficie del cambio

| Capa | Fichero | Cambio |
|---|---|---|
| Servicio | `services/sense_context.py` | `is_new_sense_exposure` + `allows_difficulty_evidence` (política ENFORCE) |
| Servicio | `services/listening_bridge.py` | `alternatives_index(entries)` (helper puro con las acepciones de la caché) |
| Dominio | `domain/listening.py` | `find_by_words` + `alternatives_index`; rama de `mismatch` que expone sin tocar la carta; `new_sense_exposure` en la respuesta |
| Esquema | `schemas/listening.py` | `ListeningSenseExposure` + `new_sense_exposure` en `ListeningAnswerResponse` |
| Servicio | `services/daily_plan.py` | `sense_exposures` separado de `difficulty_evidence`/`words_flagged` |
| Instrumento | `scripts/sense_shadow_report.py` | Proyecta con la **misma** `allows_difficulty_evidence` que decide en producción |

**No hay cambios de frontend**: el campo es aditivo y ningún consumidor decide con él
todavía.

## 6. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff` (backend) | limpio |
| `pytest` backend | **3471/3471** (3465 + 6 nuevos) |
| `vitest` frontend | **1108/1108** (112 ficheros) |
| `tsc --noEmit` + `vite build` | limpios |
| `check_release_consistency` | OK en los **6 orígenes** (`3.94.0`) |
| `sense_shadow_report.py` | usa la MISMA política; proyección vacía (ledger **0 filas**) |
| `frontend/dist/index.html` | 2012 B, 0 bytes a cero (sano) |

Tests nuevos (`backend/tests/test_sense_enforce_v394.py`, 6):

- `test_alternatives_index_gathers_known_senses`
- `test_alternatives_index_is_total_with_junk`
- `test_mismatch_suppresses_the_card_and_exposes_a_new_sense`
- `test_matched_sense_keeps_evidence_and_does_not_expose`
- `test_repeating_the_same_attempt_does_not_double_expose`
- `test_day_metrics_separates_exposures_from_difficulty`

Tests de caracterización **reapuntados** (mismo comportamiento, expectativa correcta):
`test_contract_v392.py` (forma de `new_sense_exposure`), `test_sense_context_v392.py` y
`test_sense_shadow_v393.py` (`declared:none` conserva evidencia **por decisión**, ya no
«porque aún no se aplica la política»).

## 7. Honestidad y límites

1. **El ledger está vacío (0 filas).** Toda la política es **decisión declarada, no
   medición**. `sense_shadow_report.py` mide el reparto real, pero hoy no tiene nada que
   medir: la revisión de la política exige **volumen**.
2. `mismatch` exige **alternativas conocidas**. Si la caché del diccionario no tiene la
   palabra, el veredicto será `ambiguous` y la evidencia se conservará. La política es
   conservadora **por construcción**, no por prudencia.
3. El **frontend no pinta** `new_sense_exposure`: es un campo aditivo sin consumidor. La
   UI del sentido nuevo llegará cuando haya datos que la justifiquen.
4. FSRS sigue **sin cartas por acepción**: una palabra sigue teniendo **una** carta. V3.94
   evita señalar la carta equivocada, pero no crea la carta correcta.
5. El ledger **sigue sin poda** y crecerá con las exposiciones.
6. Los **ocho gates humanos siguen `pending`**.

## 8. Qué queda para V3.95+

- **Cartas FSRS por acepción** (`sense_id` estable): la mitad que falta del problema.
- `MAX_MATCHES` por **relevancia** en vez de por orden de aparición.
- **Poda del ledger** (retención) con la evidencia ya consolidada.
- Revisar la política de `declared:none` **con datos** cuando el instrumento tenga volumen.
- Consumir `new_sense_exposure` en la UI (si los datos lo justifican).
