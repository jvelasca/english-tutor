# Release notes — English Tutor v3.94.1

**Fecha:** 2026-10-01 · **Tipo:** release de **PRODUCTO** (patch) · **Versión de app:**
`3.94.0 → 3.94.1`

**Con backend y SIN frontend**, **SIN migración de BD**, **SIN endpoints nuevos** y
**SIN cambio de contrato incompatible**: `sense_match` conserva sus tres valores
(`matched`/`mismatch`/`ambiguous`) y `new_sense_exposure: {words, count}` mantiene su
forma. El veredicto del resolver añade `mismatch_strength` (interno) y una razón nueva
(`gloss:other:weak`). `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION`
(`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se
añade ni se retira gate** —siguen los **ocho**, todos en `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** El Sense Resolver deja de estar subordinado al filtro de cartas
débiles (una acepción nueva en una palabra fuerte deja de ser invisible) y un
`mismatch` solo se declara con **prueba**, no con un único token.

---

## 1. Qué fase es esta

Esta patch cierra dos hallazgos de la auditoría de V3.94.0 sobre SENSE-CONTEXT-01:

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 2 | El sentido se resuelve DESPUÉS de filtrar por debilidad (`select_targets`), así que una palabra fuerte con acepción nueva es invisible | P1 alto | **corregido** |
| 3/6 | `mismatch` y `matched` eran reglas simétricas: un solo token ya suprimía evidencia | medio | **corregido** |

De paso se arregla la línea `baseUrl` del `tsconfig.json` del frontend (redundante).

## 2. El P1: el sentido se resuelve AHORA antes de filtrar

En V3.94 el bucle de `domain/listening.py::_apply_difficulty_evidence` iteraba
`listening_bridge.select_targets(matches, cards)`, que descarta las cartas **fuertes**
con `is_weak_card()` **antes** de llamar al resolver:

```python
for target in listening_bridge.select_targets(matches, cards):   # filtra primero
    ...
    verdict = sense_context.classify_sense_evidence(...)          # resuelve después
```

Consecuencia medida: `FSRS = 4.0 / ledger = 0 / new_sense_exposure = 0` ante una
acepción nueva en una carta fuerte.

**El arreglo.** El sentido se resuelve para **todas** las palabras emparejadas y la
decisión de escribir la carta se separa de la resolución:

```python
for match in matches:
    word = match["word"]
    card = cards.get(word)
    verdict = sense_context.classify_sense_evidence(...)
    if sense_context.is_new_sense_exposure(verdict):
        ...  # registra la exposición; la carta NO se toca
        continue
    if not listening_bridge.is_weak_card(card):
        continue  # carta fuerte en su propia acepción: conserva su dominio
    ...
```

Regla resultante: **resolver siempre, escribir solo cuando toca**. Una carta fuerte:
(a) ante un `mismatch` **probado** registra `new_sense_exposure` sin tocar FSRS;
(b) en su propia acepción conserva su dominio (sin evidencia de dificultad, como en
V3.92). `select_targets` se conserva como helper puro —sus tests de caracterización
siguen verdes— pero ya no gobierna la resolución.

## 3. `mismatch` exige PRUEBA: posible ≠ probado

La regla de V3.94 era simétrica:

```
declarada > otra  → matched
otra > declarada  → mismatch      # con UN token bastaba
```

Pedagógicamente no debe serlo: un `matched` solo significa «la evidencia es compatible
con lo aprendido» (tolera duda), mientras que un `mismatch` **suprime** la evidencia y
clasifica el uso como acepción nueva (exige prueba). V3.94.1 la hace **asimétrica**:

| Señal | Resultado | ¿Suprime? |
|---|---|---|
| declarada > otra | `matched` (`gloss:declared`) | No |
| otra ≥ 2 **y** otra > declarada | `mismatch` (`gloss:other`, **proven**) | **Sí** |
| sin alternativas | `ambiguous` (`alternatives:none`) | No |
| solo la familia declarada encaja **y no hay señal léxica débil** | `matched` (`role:declared`) | No |
| solo la familia alternativa encaja y la pista es Fuerte | `mismatch` (`role:other`, **proven**) | **Sí** |
| otra > declarada con **un** token | `ambiguous` (`gloss:other:weak`, **possible**) | No |
| resto | `ambiguous` (`tie`) | No |

El desempate gramatical a favor de la familia declarada (`role:declared`) exige además
que **no** haya señal léxica débil a favor de otra acepción
(`best_other_overlap <= declared_overlap`); si la hay, el caso baja a `possible`. Sin
esta condición, un solo token hacia otro sentido se etiquetaba `matched` y la señal se
perdía en el contador `possible_mismatch` (hallazgo de la revisión externa, corregido en
esta release).

`allows_difficulty_evidence` **no cambia**: sigue siendo `match != mismatch`, y ahora
`mismatch` y «probado» coinciden porque el resolver nunca emite `mismatch` débil. La
distinción viaja en `mismatch_strength` (`proven`/`possible`/`""`) y en la razón
persistida en el ledger.

## 4. El `tsconfig.json` del frontend

Se retira `"baseUrl": "."`: con `paths` declarado es **redundante desde TypeScript 4.1**
(los `paths` se resuelven relativos al tsconfig) y su resolución de respaldo puede
enmascarar un import mal escrito. `npx tsc --noEmit` y `npm run build` siguen limpios.

## 5. Superficie del cambio

| Capa | Fichero | Cambio |
|---|---|---|
| Servicio | `services/sense_context.py` | `PROVEN_OTHER_OVERLAP`, `MISMATCH_PROVEN/POSSIBLE`, `REASON_GLOSS_OTHER_WEAK`; `mismatch_strength` en el veredicto; decisión asimétrica |
| Dominio | `domain/listening.py` | resuelve el sentido para TODAS las palabras; separa resolución de escritura de carta |
| Instrumento | `scripts/sense_shadow_report.py` | contador `possible_mismatch` (`gloss:other:weak`) |
| Config | `frontend/tsconfig.json` | se retira `baseUrl` |
| Tests | `tests/test_sense_threshold_v3941.py` (nuevo), `tests/test_sense_enforce_v394.py`, `tests/test_sense_context_v392.py` | umbral, corpus real, carta fuerte y ciclo pedagógico |

**No hay cambios de frontend** salvo el `tsconfig`: el contrato no cambia.

## 6. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff` (backend) | limpio |
| `pytest` backend | **3486/3486** |
| `vitest` frontend | **1108/1108** (112 ficheros) |
| `tsc --noEmit` + `vite build` | limpios |
| `check_release_consistency` | OK en los **6 orígenes** (`3.94.1`) |
| `sense_shadow_report.py` | usa la MISMA política; publica `possible_mismatch` |
| `frontend/dist/index.html` | 0 bytes a cero (sano) |

Tests nuevos/ajustados:

- `test_sense_threshold_v3941.py` (nuevo): umbral (1 token → possible, 2 → proven),
  desempate por rol, que el desempate gramatical **no oculte** una señal léxica débil
  (`role:declared` baja a `possible` si hay un token de la alternativa), la asimetría no
  invierte `matched`, y un **corpus real** de `bank` con **glosas de diccionario** (no el
  texto de la frase).
- `test_sense_enforce_v394.py`: carta fuerte (`review`, dificultad 4.0) que expone sin
  tocar FSRS; carta fuerte en su propia acepción que no se toca; **ciclo pedagógico
  completo** (aprende → fallo sube FSRS → aparece otra acepción → `mismatch` no sube y
  expone → idempotencia → declara la segunda acepción → vuelve a ser dificultad).
- `test_sense_context_v392.py`: el caso de **un solo token** pasa de `mismatch` a
  `ambiguous`; el de **dos tokens** queda como `mismatch` probado.

## 7. Revisión externa (diff sin commitear)

| Revisor | Alcance | Resultado |
|---|---|---|
| **Bugbot** | diff sin commitear | **1 hallazgo bajo**, corregido en esta release |
| **Security Review** | diff sin commitear | **sin hallazgos** |

- **Bugbot** (`services/sense_context.py`): el desempate gramatical `role:declared` se
  evaluaba antes que la señal léxica débil, así que un **único** token a favor de otra
  acepción podía etiquetarse `matched` en vez de `possible` (y no lo veía el contador
  `possible_mismatch`). **Corregido**: `role:declared` exige ahora
  `best_other_overlap <= declared_overlap`. Fijado con
  `test_role_support_does_not_hide_a_weak_signal_toward_another_sense`.
- **Security Review**: cambio puro de lógica pedagógica + bumps de versión/config; sin
  superficie nueva (mismos `user_id`/inputs), sin inyección, sin cambios de auth, rutas,
  red ni sistema de ficheros.

## 8. Honestidad y límites

1. **Endurecer cambia el caso de un token.** El caso canónico de la auditoría
   (`«We sat on the bank of the river»`) pasa de `mismatch` a `ambiguous`: **conserva**
   la evidencia de dificultad. Es el precio de exigir prueba; queda **medible** como
   `possible_mismatch` en `sense_shadow_report.py` para decidir con volumen.
2. `mismatch` sigue exigiendo **alternativas conocidas** (caché del diccionario).
   Sin ellas el veredicto es `ambiguous`.
3. El **ledger sigue vacío (0 filas)**: la política es decisión declarada, no medición.
4. El **frontend sigue sin pintar** `new_sense_exposure`.
5. FSRS sigue **sin cartas por acepción** y el ledger **sin poda**.
6. Los **ocho gates humanos siguen `pending`**.

## 9. Qué queda para V3.95+

- **UI educativa** de `new_sense_exposure` (convertir la señal en aprendizaje visible).
- `sense_id` **estable** emitido por el generador (resuelve H13).
- **Cartas FSRS por acepción** y `MAX_MATCHES` por **relevancia**.
- Política de **calidad de las alternativas** del diccionario (acepción usable vs marginal).
