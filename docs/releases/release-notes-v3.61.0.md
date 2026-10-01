# v3.61.0 — Instance-aware Evidence + Anti-spoiler Guard

> Release **SIN migración explícita de BD** (columna aditiva idempotente), **SIN
> bump de `GENERATOR_VERSION` y SIN cambios de UI** que cierra los **dos defectos
> funcionales** de la auditoría `T` de V3.60 y la parte determinista de los P1 de
> la auditoría `S`:
>
> - **T-01 (fuga del target):** la superficie servida podía **NOMBRAR la unidad
>   objetivo**. La familia `shopping` generaba «You are in a **supermarket** …» y
>   `context_for` la servía tal cual: el alumno leía la respuesta y la evidencia
>   acreditaba producción **guiada** en lugar de recuperación **espontánea**.
> - **T-02 (identidad de instancia):** la evidencia podía guardar la dificultad de
>   **OTRA instancia**. `TransferAttemptIn` no identificaba la superficie emitida y
>   el POST recalculaba la rotación con el contador actual, así que dos respuestas
>   simultáneas (o un reintento de red) persistían la carga de la **siguiente**
>   superficie.
>
> V3.61 añade un **GUARD anti-spoiler** léxico y determinista sobre la superficie
> que se sirve (sin LLM ni WSD: premisa 21), una **IDENTIDAD INMUTABLE** de
> instancia de GET a POST y `context_instance` **aditivo** en el ledger. Además
> cierra tres P1 deterministas de la auditoría `S`: **cap estratificado**, **rotación
> no secuencial** y un **validador de contenido** del espacio de instancias.
> La identidad pedagógica **sigue siendo la FAMILIA**: `context_id` es
> `transfer:<id>` y `context_instance` es solo la SUPERFICIE.

## Contexto

La auditoría externa `S` aprobó la arquitectura de V3.60 (9,6/10) pero dio por
bueno el anti-spoiler validando el `template` y las CLAVES del `instance_space`,
**no cada valor de slot contra la unidad objetivo**. La auditoría `T` reprodujo
justo ese agujero (índice 7 de `shopping`) y encontró el segundo defecto en el
contrato del POST. V3.61 reconcilia ambos veredictos:

| Punto | Veredicto consolidado |
| --- | --- |
| Arquitectura familia → especificación → instancia | **Correcta** (auditoría `S`) |
| Anti-spoiler «validado» | **Incompleto**: `S` miraba la plantilla, no los valores de slot |
| Dificultad de la instancia respondida | **Defectuosa**: el POST recalculaba la rotación |
| Corrección | En **V3.61** (ni `S` ni `T` piden un `V3.60.1`) |
| CI 6/6 de V3.60 | **Documentado, no verificado de forma independiente** |

## Cambio

### A. Guard anti-spoiler de la superficie SERVIDA — `services/transfer.py`

- `reveals_target(text, target)` normaliza (`casefold` + espacios) y compara por
  **TOKEN** (frontera de palabra) con un juego acotado de variantes inflexivas
  deterministas (`-s`/`-es`/`-d`/`-ed`/`-ing`/`-er`/`-ers` y su recorte). Con
  expresiones de varias palabras la coincidencia es de subcadena normalizada. Una
  unidad de menos de `_TARGET_GUARD_MIN_LEN = 3` caracteres **no aplica guard**
  (evita suprimir medio banco por una palabra funcional). Es **conservador**: la
  variante que genera de más solo puede **retirar** superficies, nunca dejar pasar
  la unidad.
- `available_instance_details(context, target)` es `context_instance_details`
  **sin** las superficies que nombran la unidad en su consigna o en sus metadatos
  (`prompt`/`scenario`/`goal`/`register`). La rotación, la dificultad efectiva y
  lo que el ledger persiste se resuelven sobre **esa** lista, así que el índice
  servido y la carga servida hablan siempre de la **misma** superficie.
- `context_for` descarta del pool las familias **sin ninguna** superficie servible
  —solo si queda alguna alternativa segura— y sirve sobre la lista filtrada. Con
  **todas** las familias delatando la unidad (banco patológico) **degrada a V3.60**
  y lo declara (`instance_guarded=False`): nunca se deja al alumno sin tarea.
- Claves **aditivas** de explicabilidad: `instance_suppressed` (n.º de superficies
  retiradas) e `instance_guarded`.
- `context_instance_index`, `context_instance_metadata`,
  `context_instance_difficulty` y `served_difficulty` ganan `target` **opcional**:
  por defecto **no filtran** (100 % compatible con V3.60 y sus tests).

En el banco real, con la unidad `supermarket`, el guard retira **12** superficies
de `shopping` y conserva **39** servibles.

### B. Identidad INMUTABLE de instancia de GET a POST — `services/transfer.py`

- `TransferAttemptIn` gana `context_instance` (el **slug** servido, estable porque
  `_slug` se deriva del CONTENIDO y nunca del orden).
- `serve_instance(context_id, slug, attempts_by_context, target=, unit=)` devuelve
  `{instance, index, count, matched, difficulty, suppressed}`:
  - `matched=True` si el slug existe en la familia (tras el guard) y `difficulty`
    es la carga de **ESA** superficie;
  - `matched=False` si falta o ya no existe (cliente legacy, familia cambiada,
    superficie retirada por el guard): cae a la **rotación actual** —degradación
    exacta a V3.60— y lo declara para que el ledger no mienta.
- `served_difficulty_for_instance` es la fachada que usa el ledger; el POST
  persiste la dificultad de la tarea **realmente respondida** aunque el contador
  haya avanzado.
- `TransferAttemptOut` gana `context_instance`, `instance_index`,
  `instance_count`, `instance_matched` e `instance_suppressed`.

### C. Evidencia instance-aware (ledger aditivo, sin migración)

- `repositories/db.py`: `context_instance TEXT NOT NULL DEFAULT ''` en la lista
  idempotente de `ALTER TABLE` (mismo patrón que V3.46/V3.51/V3.55) y en el
  `CREATE TABLE`.
- `repositories/evidence.py`: `context_instance` **kw-only** en `record_evidence` y
  `record_evidence_bulk` (INSERT + fila devuelta) y en el `SELECT` de
  `list_evidence`. Los agregados (`summarize_by_target`, `list_observed_rows`) y
  `transfer_state` **no cambian**.
- `domain/vocabulary.py`: `_record_transfer_evidence` la persiste y
  `submit_transfer_attempt` resuelve la superficie respondida con `serve_instance`.
- **Invariante explícita:** `context_id` sigue siendo la **FAMILIA**
  (`transfer:<id>`); `context_instance` es la **SUPERFICIE**. Nunca
  `context_id = transfer:<id>:<slug>`.

### D. P1-01 — Espacio paramétrico no memorizable

- **Cap ESTRATIFICADO.** `_expand_spec` ya no recorta el producto cartesiano por
  **prefijo** (`[:96]`, que sesgaba siempre a las últimas variables):
  `_stratified_indices` toma `CONTEXT_INSTANCE_SPACE_MAX` posiciones
  equiespaciadas sobre el producto **completo** y `_partial_at` las decodifica en
  base mixta. Determinista, sin materializar el producto e **idéntico** por debajo
  del techo (el banco real).
- **Rotación NO SECUENCIAL.** Los intentos **0/1/2** conservan las superficies
  0/1/2 (contrato V3.59/V3.60 intacto); a partir del **tercero** la posición se
  permuta con un desplazamiento derivado de `(familia, unidad)`
  (`zlib.crc32`; sin `random()` ni `hash()` sembrado por proceso). El
  desplazamiento es una **biyección** del tramo: el ciclo deja de ser el orden
  declarado, **difiere entre ítems** y sigue visitando **todo** el espacio. Sin
  `target` ni `unit` la degradación es exacta a V3.60.
- **Banco ampliado.** Cada familia declara un **tercer eje** (`constraint`) que el
  `template` interpola: **358 → 1020 superficies** (51 por familia) sin escribir
  ninguna consigna a mano, sin tocar ninguna `id` y conservando
  `CONTEXT_INSTANCE_SPACE_MIN = 12` y las tres primeras superficies **byte a
  byte**.
- **Honestidad documental:** esto **reduce** la memorizabilidad, no la elimina. El
  cierre real es `Instance Generator 2.0` (V3.65+).

### E. P1-02 — Validador de contenido del espacio

Nuevo `services/transfer_audit.py` con `validate_instance_space(context,
target="")` y `validate_bank(contexts=None, target="")`, más el CLI
`python -m scripts.transfer_validation` (gate de CI **dentro del job Backend**, no
un job nuevo). Comprueba:

- ninguna consigna con `{...}` sin resolver, slugs **únicos** dentro de la familia
  y espacio dentro de `MIN..MAX`;
- **todo `difficulty_delta` no nulo exige `scenario`/`goal`** que lo justifiquen
  (declarar carga sin explicarla era el hueco de V3.60), es **entero**, cabe en
  **±2** y usa dimensiones que la familia declara;
- `register` de instancia, si se declara, **igual** al de la familia (formaliza que
  `family.register` es la identidad y `instance.register` su realización local);
- `skill_delta` ⊆ `CONTEXT_SKILLS` y todos los slots declarados **consumidos** por
  la plantilla;
- con unidad objetivo, la familia conserva **al menos una** superficie servible
  (evita el callejón sin salida del guard);
- **advisory** (nunca gate): perfil de **demanda** heurístico por features del
  texto (interrogación, imperativos, marcadores de opinión/argumentación, nº de
  cláusulas) que avisa si dos superficies con la **misma carga efectiva** piden
  cosas muy distintas. Se etiqueta como heurístico: **sin WSD real** la
  equivalencia pedagógica solo se cierra parcialmente.

El banco real pasa con **0 errores** y **7 avisos** (todos `demand_spread`).

### F. Contrato aditivo y frontend

- `TransferContextOut` gana `instance_suppressed`/`instance_guarded` (**38**
  claves); `TransferAttemptOut` gana cinco claves. Las **36** de V3.60 quedan
  intactas y fijadas por test.
- `frontend/src/types/api.ts` espeja las claves nuevas,
  `submitDrillTransferAttempt` envía `context_instance` y `wordDrill.tsx` lo pasa
  desde el contexto servido. **Sin cambio visual ni de i18n.**

### G. Auditorías archivadas

- `docs/audit/S-AUDITORIA-TOTAL-V360.md` (externa, 9,6/10 aprobada con matices) y
  `docs/audit/T-AUDITORIA-TOTAL-V360.md` (que reproduce los dos defectos), con el
  **conflicto de veredictos explícito** y el CI 6/6 de V3.60 declarado
  **documentado, no verificado de forma independiente**.
- Veredicto consolidado y plan en `docs/RELEVO.md` y `agentes/README.md`.

## NO cambia

- `context_id` sigue siendo la **FAMILIA** (`transfer:<id>`): unidad de evidencia,
  `transfer_state`, umbrales, `context_distance`, `context_diversity` y
  `_novelty_score` intactos.
- `context_difficulty()` (la carga de la FAMILIA) y `CONTEXT_DIMENSIONS` no
  cambian; la superficie no entra en el pool, la novedad, la distancia ni el
  Difficulty Engine.
- El scoring, el Sense Engine, FSRS y el planner no se tocan.
- **Sin `GENERATOR_VERSION`**: la columna es aditiva y idempotente, y las filas
  legacy quedan `''`.
- Sin cambio de UI ni de i18n.

## Contrato aditivo

| Modelo | Claves nuevas |
| --- | --- |
| `TransferContextOut` | `instance_suppressed`, `instance_guarded` |
| `TransferAttemptIn` | `context_instance` (opcional, `max_length=200`) |
| `TransferAttemptOut` | `context_instance`, `instance_index`, `instance_count`, `instance_matched`, `instance_suppressed` |

## Tests

Nuevo `backend/tests/test_context_engine_v361.py` (**38**):

- **Guard:** frontera de palabra y conservadurismo, unidades demasiado cortas,
  degradación **exacta** sin unidad objetivo, reproducción del defecto **T-01**
  (`shopping`/`supermarket`: ningún intento sirve ya una consigna que nombre la
  unidad; `instance_suppressed == 12`), la familia solo se retira del pool **si hay
  alternativa** y el banco patológico degrada **declarándolo**.
- **Acuerdo GET/POST:** para TODOS los intentos de una familia guardada, la
  consigna servida es la de la superficie que declara el guard y su carga coincide
  con `served_difficulty` y `context_instance_difficulty(target=…)`.
- **Identidad inmutable:** los **1020** slugs del banco se resuelven a su propia
  superficie; con el contador **avanzado** el slug conserva la carga de la
  superficie **respondida** (regresión **T-02**), también **end-to-end HTTP** con
  la fila persistida; sin slug o con slug desconocido se cae a la rotación con
  `matched=False`; una superficie retirada por el guard **no** es respondible.
- **Ledger:** columna aditiva presente, filas sin superficie en `''` y la
  superficie **nunca** fragmenta la familia (`context_id` = FAMILIA).
- **P1-01:** `_stratified_indices` es determinista, monótono y da cobertura a
  TODOS los ejes (ningún eje hambriento); los intentos 0/1/2 son las superficies
  0/1/2; el ciclo es una **biyección** y el orden a partir del 3.º es permutado y
  **dependiente del ítem**.
- **Validador:** el banco real pasa y **cada** invariante se comprueba con una
  violación sintética (espacio, placeholders, slugs, deltas —sin justificar, fuera
  de rango, no enteros, dimensión desconocida—, `register`, `skill_delta`, slots
  sin consumir, familia sin tarea para la unidad, delta base sin explicar) más el
  aviso de demanda y el gate del banco.
- **Contrato:** 38 claves, banco vacío con los mismos defaults y `context_instance`
  opcional en el input.

## Verificación

```text
ruff check .                                  All checks passed
pytest tests/ -q                              2373 passed
pytest launcher/tests -q                      75 passed
npx tsc --noEmit                              OK
npm test                                      76 ficheros / 651 tests
npm run build                                 OK
python scripts/check_release_consistency.py   3.61.0
python scripts/check_beta_v3.py               OK
python backend/scripts/content_validation.py  OK
python -m scripts.transfer_validation         20 familias / 1020 superficies / 0 errores
```

## CI

**Pendiente de la ejecución del workflow tras el push** (6 checks: Release
consistency **3.61.0**, Backend con `ruff` + `pytest` + el nuevo paso
`python -m scripts.transfer_validation`, Frontend con `tsc` + `vitest` +
`build`, Playwright E2E, Beta V3.0 gate y Content validation). La etiqueta
anotada `v3.61.0` se crea tras el verde.

> Nota de método: en V3.60 el «CI 6/6» quedó como afirmación del repositorio sin
> verificación independiente. Esta release **no** adelanta ese dato.

## Fuera de alcance (V3.62+)

- **Student Skill State 3.0** (modalidad × competencia × dimensión; V3.62).
- **Observed Task Difficulty 2.0** (`declared` → `served` → `observed` empírico;
  V3.63).
- **Planner 3.0** y rotación **adaptativa** (la siguiente instancia no depende aún
  del fallo ni del acierto; V3.64).
- **Instance Generator 2.0** (cierre real de la memorizabilidad; V3.65).
- WSD real, la división de `transfer.py` en paquete y el arrastre de V3.59 (el
  contrato/prompt de generación de sentidos con su bump de `GENERATOR_VERSION` y la
  ponderación de la adecuación en `transfer_confidence`).

## Siguiente paso

V3.62 — **Student Skill State 3.0**: pasar del `skill × 4 dimensiones` actual a
`modalidad × competencia × dimensión`, para que la evidencia **escrita** no eleve
nunca la selección de una tarea **oral**.
