# Q — Auditoría externa de V3.52.1 (Student Skill State + Difficulty Engine 2.0 + hotfix de producto)

> Fecha: 2026-09-11 · Rol: **auditoría externa del árbol `bdaaff9` (V3.52.1)**,
> contrastada contra el tag de la release base `v3.52.0` (`23cbad7`) y contra las
> afirmaciones de `release-notes-v3.52.1.md` / `release-notes-v3.52.0.md`.
> Método: lectura del código del árbol auditado, **ejecución real** de backend,
> frontend, Playwright y gates, `git diff` del hotfix, y análisis numérico del
> banco de contextos para verificar la calibración declarada.
> Briefing (histórico del método): `agentes/auditoria-externa-v352.md`.

## Veredicto

🟢 **Publicable como estable.** **Sin P0 y sin P1.** Los dos P1 de V3.51 y el
P1-01 de V3.52 están **realmente cerrados** y verificados por código y por
ejecución; el hotfix de producto está corregido de raíz (no son solo síntomas).
Quedan **2 P2** (calibración de `CEFR_CAPACITY` frente al banco real y una
diferenciación de tolerancia hoy inerte con una justificación invertida) y **3
P3** (etiqueta semántica de filas legacy, robustez latente de `_context_vector`,
`is_test` marcable por el cliente) más una **nota de proceso** (la release no
está etiquetada). Ninguno exige rehacer la release; sí conviene atender P2-01 y
P2-02 en V3.53.

> **Resolución (2026-09-11, V3.52.2).** Los dos P2 de este informe quedaron
> **cerrados** en la release **v3.52.2** (`release-notes-v3.52.2.md`): (P2-01)
> `CEFR_CAPACITY` es ahora el **envelope monótono** del banco, con
> `test_capacity_is_the_monotone_envelope_of_the_bank` y
> `test_every_bank_context_fits_its_own_level_under_strict_tolerance` (el impacto
> medido son 15 de 48 combinaciones con reto reconocible —7 niveles de ítem × 7
> de alumno menos el caso sin ningún nivel— que cambian de contexto servido: el
> alumno A2 demostrado pasa a `directions`/`shopping` en vez de
> `story`/`future`, el C1 de `academic` (C2) a `mediation` (C1), y los empates
> «diluidos» por la tabla inflada se estrechan); (P2-02) la
> justificación de la tolerancia está corregida y el bloque queda documentado
> como red de seguridad, con `test_tolerance_bites_only_when_a_context_declares_above_the_envelope`
> que fija la inercia (0 de 48) y comprueba que SÍ discrimina con un contexto
> sintético. El P3-04 (proceso) se resolvió creando y empujando la etiqueta
> `v3.52.1` sobre `89eff0b`. El impacto medido del P2-01 son **15 de 48
> combinaciones** con reto reconocible (7 niveles de ítem × 7 de alumno, menos el
> caso sin ningún nivel) que cambian de contexto servido —el alumno A2 demostrado
> pasa a `directions`/`shopping` en vez de `story`/`future`; el C1, de `academic`
> (C2) a `mediation` (C1)—, reproducido con la tabla antigua y la nueva. P3-01,
> P3-02 y P3-03 siguen **aceptados** (sin impacto de comportamiento) para V3.53+.

| Métrica | V3.52.0 | V3.52.1 | Juicio |
| --- | --- | --- | --- |
| P1 abiertos de la auditoría anterior (V3.51) | 2 | 0 | 🟢 CERRADOS |
| P1-01 de la auditoría de V3.52 (`fit` dimensional) | abierto | cerrado | 🟢 CERRADO |
| P0 / P1 nuevos | — | 0 / 0 | 🟢 |
| P2 nuevos | — | 2 | 🟡 |
| P3 nuevos | — | 3 | 🔵 |
| CI | 6/6 (`23cbad7`) | 6/6 (`89eff0b`, `bdaaff9`) | 🟢 |

## Posición auditada y evidencia ejecutada

| Qué | Valor verificado |
| --- | --- |
| Árbol auditado | `main` @ `bdaaff9` (contiene `89eff0b`, release V3.52.1) |
| Base | tag `v3.52.0` = `23cbad7`; `v3.51.0` = `c056546` |
| Delta del hotfix | `git diff v3.52.0..bdaaff9` → 36 ficheros, **+1557/−175**, **sin** tocar `evidence`/`planner`/`fsrs` |
| CI | run [34622637688](https://github.com/jvelasca/english-tutor/actions/runs/34622637688) (`89eff0b`) y [34623244239](https://github.com/jvelasca/english-tutor/actions/runs/34623244239) (`bdaaff9`), **6/6** cada uno; log de Backend: `2162 passed, 2 skipped` |
| `ruff check .` (backend) | `All checks passed!` |
| `pytest` dirigido (5 ficheros) | `78 passed` |
| `tsc --noEmit` / `vitest` (listening) | exit 0 / `31 passed` (2 ficheros) |
| Playwright (local, backend+frontend vivos) | `23 passed, 22 skipped` (los `skip` son por proyecto/viewport) |
| BD local tras correr Playwright | `is_test=1` → **0**; usuarios totales **2** |

Prueba funcional del hotfix contra la app real (perfil `is_test` efímero creado y
borrado por API):

- `RUTA_ANTES: Current route: A1` → clic en `Level A2 history` →
  `RUTA_DESPUES: Current route: A2` ✔ (y la lista de nivel se recarga).
- `HINT_BUCLE: Looping 0:01 → 0:02` (usa el **B marcado**, no la posición viva) y
  tras «Clear mark» el hint desaparece y «Remove loop» queda deshabilitado
  (`BUCLE_TRAS_QUITAR_MARCA: desarmado`) ✔.
- Centrado medido con `boundingBox`: `CENTRO_BOTON: 640` = `CENTRO_CONTROLES: 640` ✔.

## 1. Cierre real de los P1

### 1.1 P1-01 de V3.51 — el suelo ya es el nivel DEMOSTRADO

Verificado en el árbol auditado:

- `repositories/profile.py::set_level_state` persiste `estimated_level` y
  `demonstrated_level` **separados**; `cefr_level` se conserva.
- `domain/profile.py::_compute_profile` expone `demonstrated_level` desde el
  Student Model (línea 172) y `get_profile_summary` escribe **ambos** en la caché
  (líneas 237-239) — único escritor de la caché (`grep set_level_state`).
- `domain/vocabulary.py::_learner_level_state` lee la fila única y aplica
  `student_state.level_state` pasando `cefr_level` como *declarado*, `estimated_level`
  como *estimado* y `demonstrated_level` como *demostrado*; el suelo lo fija
  `floor_level` con la política `demostrado > estimado > declarado > ninguno`.
- **No queda ningún camino del drill que use `cefr_level` como si fuera
  demostrado**: el único consumidor es `practice_level` (etiqueta «declarado»,
  tolerancia amplia). El docstring ya no miente.
- El test `test_student_state_v352.py` cubre la migración sobre una tabla legacy
  real y `test_difficulty_engine_v352.py::test_legacy_profile_column_still_feeds_the_drill`
  cubre la fila migrada.

### 1.2 P1-02 de V3.51 — el suelo ya es vectorial

`services/difficulty.py` compara vector contra vector (`CEFR_CAPACITY`,
`challenge_vector`, `fit`, `select_by_difficulty`) y `_difficulty_floor` /
`_within_band` **han desaparecido** (`grep` → 0 coincidencias). Las cuatro
dimensiones no se colapsan nunca.

### 1.3 P1-01 de V3.52 — cobertura dimensional (cerrado por V3.52.1)

Comprobado con datos reales:

- `fit` devuelve `dimensions_expected`/`dimensions_compared`/`coverage` y
  `within = (compared == expected) and (max_overshoot <= tolerance)`.
- Un contexto **sin** `difficulty_vector` da `coverage=0.0`, `within=False` y
  **no gana** la selección: `select_by_difficulty([sin_vector, declarado], reto)`
  → `['declarado']`.
- Con reto vacío el encaje sigue siendo vacuo (`within=True`, `coverage=1.0`), que
  es lo correcto.
- `select_by_difficulty` degrada por **mayor cobertura** y luego por menor
  distancia (verificado: un vector completo con distancia 16 gana a uno parcial
  con distancia 4).
- Los **20 contextos del banco declaran las 4 dimensiones** (n = 3/4/4/3/3/3), así
  que el endurecimiento **no cambia ninguna selección de producción**: cero
  regresión real, como afirma la release.

## 2. Cero regresión, determinismo y coste

- **Escalera intacta.** El diff del hotfix toca `transfer.py` **solo** en
  `_difficulty_fit_for` (añade 3 claves al payload; 19 líneas). No hay cambios en
  `transfer_state`, umbrales, `context_signals`, `context_diversity`,
  `score_transfer_attempt` ni FSRS.
- **`TRANSFER_DIFFICULTY_BAND`** queda declarada como deprecada y **ningún** camino
  de selección la consume (solo aparece su declaración y una mención en un
  docstring de `test_context_skill_v350.py`). Código muerto declarado e inerte,
  aceptable por trazabilidad.
- **Determinismo.** La misma entrada produce la misma selección (2 llamadas
  idénticas) y `context_for` devuelve el mismo `context_id` en 3 llamadas
  consecutivas; no hay reloj ni aleatoriedad en `difficulty`/`student_state`.
  `_stable_index` resuelve la rotación dentro del pool seleccionado.
- **Camino caliente O(1).** `_learner_level_state` hace **una** lectura de fila
  (`profile_repo.get_profile`) y `domain/vocabulary.py` **no** llama a
  `academy.build_student_model` (grep: solo `get_fsrs_card`/`upsert_fsrs_card`). La
  caché se escribe únicamente desde `domain/profile.py`.
- **Paridad GET↔POST.** Ambos caminos derivan `condition`, `skill`, `level`,
  `learner_level` y `learner_level_source` con las mismas funciones y el mismo
  resumen de evidencia; `test_get_and_post_share_the_level_source` lo fija.
- **Contrato aditivo.** `difficulty_fit` y `learner_level_source` viajan en **todos**
  los retornos de `context_for` (incluidos el de banco vacío y el de pool
  agotado), y `difficulty`/`difficulty_vector` se conservan. El espejo del
  frontend (`DrillDifficultyFit`) es opcional: las claves nuevas no rompen tipos.

## 3. Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
| --- | --- | --- | --- | --- | --- |
| P2-01 | media | `CEFR_CAPACITY` no cuadra con el banco que dice calibrar: la `interaction` declarada en A1/A2 queda **por debajo** del banco (1 vs máximo real 2/3) y el léxico/sintaxis de B2/C1 **por encima** (4/4 y 5/5 vs máximo real 3/4). Con la tolerancia ESTRICTA, un alumno A2 **demostrado** excluye 2 de los 4 contextos A2 del banco. | Ver §3.1 | Derivar/validar la tabla contra el banco y añadir test de consistencia | **cerrado en V3.52.2** |
| P2-02 | media | La distinción `DIFFICULTY_TOLERANCE`/`_ESTIMATED` es **inerte** en el banco real (0 de 48 combinaciones) y su justificación declarada está invertida: un margen mayor admite **más** exceso, no menos exigencia. | Ver §3.2 | Corregir el docstring y decidir: ejercitar la tolerancia (calibrar) o documentarla como perilla prospectiva con test que fije la inercia | **cerrado en V3.52.2** |
| P3-01 | menor | Una fila legacy de V3.51 (`cefr_level` con el **estimado** cacheado, columnas nuevas en `''`) se reporta con `floor_source = "practice"` («declarado») en vez de «estimated». El comportamiento es idéntico (`tolerance_for` da 2 en ambos), solo difiere la etiqueta. | `_learner_level_state` pasa `cefr_level` como `practice_level`; `test_legacy_profile_column_still_feeds_the_drill` | Mapear legacy → `estimated` o comentar la equivalencia | aceptado |
| P3-02 | menor | `_context_vector` trata un contexto **sin** `difficulty_vector` como si el propio dict fuera el vector: unas metadatos que usaran un nombre de dimensión canónico se leerían como carga. Latente (el banco no colisiona). | `services/difficulty.py` `_context_vector` | Devolver `{}` para dicts «de contexto» sin la clave | aceptado |
| P3-03 | menor | `is_test` es **marcable por el cliente** en `POST /api/users` (app local sin auth): un perfil creado con `is_test: true` queda invisible en app y lanzador. No es frontera de seguridad, pero la guarda es declarativa. | `routers/users.py` + `schemas/users.py` | Aceptar y documentar, o asignar el flag solo en servidor | aceptado |
| P3-04 | proceso | La release **no está etiquetada**: `git tag --list` llega a `v3.52.0`; el árbol auditado solo se referencia por commit. | `git tag --list`; briefings usan `git checkout v3.52.0` | Crear y empujar `v3.52.1` sobre `89eff0b` | **cerrado en V3.52.2** |

> Nota de honestidad: P3-01 y P3-03 se registran como **aceptados** (no generan
> comportamiento incorrecto hoy). P3-04 es de proceso, no de código.

### 3.1 P2-01 — la tabla de capacidad no sale del banco

Distribución real de los 20 contextos de `TRANSFER_CONTEXTS` (media y **máximo**
por dimensión) frente a `CEFR_CAPACITY`:

| Nivel | n | media (lex/syn/dis/int) | máx real (lex/syn/dis/int) | `CEFR_CAPACITY` | desvío del máx |
| --- | --- | --- | --- | --- | --- |
| A1 | 3 | 1.0 / 1.0 / 1.33 / **1.67** | 1 / 1 / 2 / **2** | 1 / 1 / 1 / **1** | interaction **+1** |
| A2 | 4 | 2.0 / 2.0 / 2.0 / 2.0 | 2 / 2 / 2 / **3** | 2 / 2 / 2 / **1** | interaction **+2** |
| B1 | 4 | 2.25 / 2.75 / 3.0 / 1.5 | 3 / 3 / 3 / 2 | 3 / 3 / 3 / 2 | 0 |
| B2 | 3 | **3.0** / **3.0** / 3.67 / 2.67 | 3 / 3 / 4 / 3 | **4** / **4** / 4 / 3 | lex/syn **−1** |
| C1 | 3 | **4.0** / 4.33 / 5.0 / 3.67 | 4 / 5 / 5 / 5 | **5** / **5** / 5 / 4 | lex **−1** |
| C2 | 3 | 5.0 / 5.0 / 5.0 / 3.33 | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 |

Consecuencia medida (caso A2, el único que falla hoy con la tolerancia estricta):
con **ítem A2 y alumno A2 demostrado** (`tolerance = 1`), el reto es
`{lexical: 2, syntax: 2, discourse: 2, interaction: 1}` y

- `story` / `future` → `within=True`, `distance=0`;
- `directions` / `shopping` (interaction **3**) → `within=False`, `overshoot=2`.

Es decir: el alumno con **más** confianza (certificado) queda excluido de 2 de los
4 contextos que el banco etiqueta con **su mismo** nivel, mientras que el alumno
estimado (tolerancia 2) al menos los tiene en el conjunto `within`. Impacto
acotado: en el primer intento el selector sirve `story`/`future` (distancia 0) en
ambos casos, y los dos contextos interactivos reaparecen al agotarse los otros dos,
así que no hay pérdida de contenido — pero **la afirmación del docstring («calibrada
con la distribución real del banco») no se sostiene para la `interaction` de A1/A2
ni para el léxico/sintaxis de B2/C1**, y la dirección es la contraria a la deseada:
la mayor confianza recibe el conjunto **más plano**.

Test que fallaría hoy:

```python
# backend/tests/test_difficulty_engine_v352.py (propuesto)
def test_bank_contexts_fit_their_own_level_capacity():
    for context in transfer.TRANSFER_CONTEXTS:
        level = context["cefr"]
        challenge = difficulty.challenge_vector(level, level)
        fit = difficulty.fit(
            context["difficulty_vector"], challenge,
            tolerance=difficulty.DIFFICULTY_TOLERANCE,
        )
        assert fit["within"], (context["id"], fit)     # falla en directions/shopping (A2)
```

Recomendación: o se **deriva** la tabla del banco (p. ej. `interaction` de A1/A2 a
2/3, léxico/sintaxis de B2/C1 a 3/4) o se documenta explícitamente como
«capacidad objetivo, no máxima del banco» y se acota el test a la tolerancia
amplia. En ambos casos, un test de consistencia evita que la tabla y el banco
vuelvan a divergir en silencio.

### 3.2 P2-02 — la tolerancia por fuente no cambia nada (y su motivo está invertido)

Enumerando las **48** combinaciones con reto reconocible (7 niveles de ítem × 7 de
alumno, menos el caso sin ningún nivel) sobre el banco real:

```
La tolerancia 1 vs 2 CAMBIA la selección en 0 casos.
Contextos servidos con overshoot > 0: 5 (A1/A1, A1/-, -/A1, -/B1, A2/B1).
```

Por tanto la política «estricta para demostrado / amplia para estimado» no tiene
**ningún** efecto observable hoy: solo cambia el número que viaja en el payload, y
el único test que la cubre
(`test_learner_level_source_selects_the_tolerance_in_the_payload`) **afirma ese
número**, no un cambio de elección. Además, el docstring dice que el margen amplio
es «deliberadamente conservador: ante la duda, más margen en lugar de más
exigencia», cuando en `fit`/`select_by_difficulty` un margen mayor admite
`overshoot` mayor, es decir **más** exigencia (un contexto que excede la capacidad
del alumno puede entrar en el conjunto `within` y ganar por menor distancia).

Recomendación: (a) corregir la justificación escrita; (b) elegir explícitamente
entre ejercitar la tolerancia (ligado a P2-01: con la tabla derivada del banco, la
tolerancia pasaría a discriminar) o declararla perilla prospectiva con un test que
**fije la inercia actual** (documentar que hoy es inerte es información útil, no un
fallo).

### 3.3 Observaciones que NO son hallazgos (verificadas y correctas)

- **Se sirve el contexto más exigente del nivel del ítem cuando el alumno está por
  debajo** (17 de 48 combinaciones sirven un contexto por encima del nivel del
  alumno). Es el diseño declarado desde V3.47: el **techo** es el CEFR del ítem y
  `_within_level` capa el pool por ese techo, no por el suelo del alumno. **No es
  regresión de V3.52** y está cubierto por
  `test_a1_item_with_c2_learner_never_exceeds_the_item_ceiling`.
- **El suelo es inerte a nivel A1**: con reto C2 y pool A1, los 3 contextos A1
  empatan en distancia (15) y el selector devuelve los 3; el servido lo decide
  `_stable_index(word)`. No es un defecto (los 3 son igual de duros en suma), pero
  conviene saber que «el suelo» no discrimina en A1.
- **`fit` con carga fuera de rango o tipo raro** se recorta/descarta sin lanzar
  (`normalize_vector({"lexical": 3.7, "syntax": "4", "discourse": 99, ...})` →
  `{lexical: 3, discourse: 5, interaction: 1}`); un descarte baja la cobertura y
  por tanto **excluye** el contexto (dirección conservadora).
- **Un contexto con vector parcial** contra un reto completo da `coverage<1` y
  `within=False`, pero **no** se descarta del todo: si nadie encaja, la degradación
  por cobertura puede servirlo (es el comportamiento deseado: degradar, no dejar
  sin tarea).

## 4. Delta del hotfix de producto (V3.52.1) verificado

| Bug reportado | Raíz | Verificación en el árbol auditado |
| --- | --- | --- |
| Usuarios fantasma «Visual Tester» | find-or-create **no atómico** de `gateHelper.ts` contra la BD real, en paralelo (9 specs × 3 proyectos) | `globalSetup.ts` crea/reutiliza **un** perfil marcado y `globalTeardown.ts` lo borra vía `DELETE /api/users/{id}`; `gateHelper.ts` solo mockea `GET /api/users`. Corrida real: `23 passed, 22 skipped` y BD final con `is_test=1 → 0` |
| Guarda definitiva | — | `users.is_test` (`CREATE TABLE` + `ALTER TABLE` idempotente en `db.py`), `list_users` filtra por defecto, `include_test=true` para tests, `PATCH` **no** puede cambiar `is_test`, `DELETE` devuelve 404 con un id real y limpia filas dependientes enumeradas dinámicamente (`settings`, `conversations`, `messages`); el lanzador filtra con degradación si falta la columna |
| «RUTA ACTUAL» no seguía al nivel | el anillo se ataba a `stats.level`; elegir nivel no recargaba | Prueba funcional: A1 → A2 actualiza `aria-label` a `Current route: A2` y recarga la pregunta |
| Bucle A/B desincronizado y descentrado | estado React y `segment` del controller por separado; `play(url)` recargaba siempre; `>` en el borde | Módulo puro `abLoop.ts`; `play(url)` idempotente por URL; `>=` + `onCurrentTime` al rebobinar; prueba funcional: hint `Looping 0:01 → 0:02`, «Clear mark» desarma el bucle, centros 640 = 640 |

Tests del hotfix: `test_users.py` (filtro por defecto, `DELETE` no borra perfiles
reales, borra filas dependientes), `test_user_profile.py` (contrato HTTP),
`launcher/tests/test_status.py` (filtro `is_test`), `abLoop.test.ts` y la
ampliación de `audioController.test.ts` (play idempotente, rebobinado en el
borde). Todos en verde.

## 5. Respuestas a las preguntas del briefing

1. **Cierre real de P1-01 (V3.51).** Sí: el suelo que consume el drill sale del
   nivel DEMOSTRADO; ningún camino usa `cefr_level` como demostrado (queda como
   «declarado»). El docstring ya no miente. Ver §1.1.
2. **Política de prioridad del suelo.** Demostrado > estimado es defendible
   (certificación = retención) y es la **dirección segura** (puede servir más
   fácil, no más difícil). Caso de infravaloración comprobado: demostrado A2 <
   estimado C1 con ítem A2 → sirve `story` (interacción 1) en vez de `directions`
   (interacción 3). Se acepta como coste deliberado del conservadurismo.
3. **Migración y filas legacy.** Idempotente y no destructiva; `cefr_level` se
   conserva y `set_cefr` no pisa un `demonstrated_level` certificado. Las filas
   legacy quedan con `''` en las columnas nuevas y alimentan el suelo como
   **declarado** (tolerancia amplia): no se pierde señal y no se crea suelo
   fantasma. Un `demonstrated_level` no CEFR simplemente no participa. Ver P3-01
   (etiqueta).
4. **Robustez de `student_state`.** Nunca lanza con `None`, `""`, `"a1"`, `" C1 "`,
   `"Z9"` ni no-strings; normaliza y devuelve `""`; `empty_state()` devuelve un dict
   nuevo (verificado `is not`). Verificado por ejecución.
5. **`CEFR_CAPACITY` como tabla declarada.** Monótona por dimensión ✔, pero
   **no** respaldada por el banco: ver **P2-01**. Los 20 contextos son 4/4 en
   cobertura, así que no hay impacto de producción, pero la afirmación «calibrada
   con la distribución real» es falsa en 3 de las 6 filas.
6. **`challenge_vector` = máximo por dimensión.** Correcto y sin mezclar escalas.
   Con ítem A1 y alumno C2 el reto es C2 pero `_within_level` capa el pool a A1: el
   motor **reordena dentro de A1** (y en A1 los 3 empatan, así que decide
   `_stable_index`). Está cubierto por test (`…never_exceeds_the_item_ceiling`) y
   no es ruido inerte, pero su efecto es nulo en A1.
7. **Política de `fit`/`select`.** `distance` incluye el defecto (quedarse corto) y
   `max_overshoot` solo el exceso; `within` primero y mínima distancia después es
   una política lexicográfica razonable. **Sí** puede servirse un contexto que
   exceda la capacidad del alumno, hasta `tolerance`. No deja el pool vacío
   (identidad sin reto/pool) y no sirve «el más difícil» por defecto (la
   degradación prefiere cobertura y luego cercanía).
8. **Tolerancias.** La intención está declarada, pero hoy **inerte** y con la
   justificación invertida: ver **P2-02**. Un `learner_level_source` desconocido o
   en mayúsculas cae al margen amplio (verificado `Demonstrated` → 1 por
   `lower()`; `DEMOSTRADO` → 2).
9. **Cero regresión de la escalera.** Verificado por diff del hotfix (solo claves
   de `difficulty_fit` en `transfer.py`) y grep: `_difficulty_floor`/`_within_band`
   no existen; `TRANSFER_DIFFICULTY_BAND` no la consume ningún camino de selección.
   Único «código muerto»: la constante deprecada (documentada).
10. **Determinismo.** Sí (ver §2), sin reloj ni aleatoriedad; los empates preservan
    el orden de entrada y `_stable_index` resuelve la rotación.
11. **Camino caliente O(1).** Sí: una fila, sin `build_student_model` en el drill y
    con la caché escribiéndose solo desde `get_profile_summary`.
12. **Paridad GET↔POST.** Sí para el mismo estado de evidencia (mismas funciones y
    mismo resumen); fijado por test. No se encontró una entrada real divergente.
13. **Contrato HTTP aditivo.** Sí: las claves nuevas viajan en todos los retornos
    (incluidos banco vacío y `exhausted`), `difficulty`/`difficulty_vector` intactos
    y el espejo del frontend opcional.
14. **Cobertura de tests.** Cobertura sólida de los bordes pedidos (no CEFR/`None`,
    niveles fuera de la tabla, contextos sin vector, claves desconocidas y cargas
    fuera de rango, empates exactos, pool vacío, migración sobre tabla legacy real,
    paridad pura↔SQL). **Faltan** dos tests que este informe echaría de menos:
    consistencia `CEFR_CAPACITY` ↔ banco (P2-01) y **comportamiento** de la
    tolerancia (P2-02; hoy solo se prueba el número del payload).
15. **¿Cuadra la capacidad con el banco?** No del todo: ver **P2-01** (tabla ±).
16. **¿La tolerancia cambia la selección?** No: 0 de 48. Ver **P2-02**.
17. **Delta del hotfix.** Verificado y correcto, salvo el matiz P3-03 (`is_test`
    marcable por el cliente). Ver §4.

## 6. Recomendación para el siguiente incremento

El informe **desbloquea V3.53**: no hay P0/P1 que exija un hotfix inmediato.

- **Cerrado en V3.52.2:** **P2-01** (`CEFR_CAPACITY` = envelope monótono del
  banco + invariante de encaje por nivel), **P2-02** (justificación de la
  tolerancia corregida y documentada como red de seguridad, con test de inercia y
  de discriminación sintética) y **P3-04** (etiqueta `v3.52.1` creada y empujada).
  Deja el motor listo para reutilizarse en speaking (2 dims) / listening (0 dims).
- **P3 restantes:** P3-02 puede esperar a tocar `_context_vector` por otro motivo;
  P3-01 (etiqueta semántica de filas legacy) y P3-03 (`is_test` marcable por el
  cliente) se aceptan tal cual, sin impacto de comportamiento.
- **Candidatos ya documentados para V3.53+** (sin cambios por este informe):
  P1-02 (Learner Skill State 2.0 + `observed_difficulty`), P1-03 (Planner 2.0 /
  Expected Learning Value), Sense Engine 2.0, deuda de planner (`assessed_skill` →
  planner, `skill_priorities` → `select_task`, con el doble conteo de
  `written_production`), entrega oral real del transfer y code splitting.

## Regenerar / Verificar

```powershell
# Delta del hotfix (nada de escalera/scoring/FSRS)
git diff v3.52.0..bdaaff9 --stat
git diff v3.52.0..bdaaff9 -- backend/services/transfer.py

# Backend
cd backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest tests/test_difficulty_engine_v352.py `
    tests/test_student_state_v352.py tests/test_users.py `
    tests/test_user_profile.py tests/test_task_semantics_v351.py -q

# Frontend
cd ../frontend
npx tsc --noEmit
npx vitest run src/features/listening/abLoop.test.ts src/features/listening/audioController.test.ts
npx playwright test        # crea y borra el perfil is_test; 23 passed / 22 skipped en local

# Consistencia capacidad ↔ banco y (in)utilidad de la tolerancia
cd ../backend
@'
from services import difficulty, transfer
for lv in ("A1","A2","B1","B2","C1","C2"):
    bank = [c for c in transfer.TRANSFER_CONTEXTS if c["cefr"] == lv]
    mx = {d: max(c["difficulty_vector"][d] for c in bank) for d in difficulty.DIFFICULTY_DIMENSIONS}
    print(lv, "max banco", mx, "capacidad", difficulty.CEFR_CAPACITY[lv])
# tolerancia 1 vs 2 (0 casos de diferencia hoy)
levels = ("", "A1","A2","B1","B2","C1","C2")
diff = 0
for i in levels:
    for l in levels:
        ch = difficulty.challenge_vector(i, l)
        if not ch: continue
        pool = transfer._within_level(list(transfer.TRANSFER_CONTEXTS), i)
        a = {c["id"] for c in difficulty.select_by_difficulty(pool, ch, tolerance=1)}
        b = {c["id"] for c in difficulty.select_by_difficulty(pool, ch, tolerance=2)}
        diff += a != b
print("casos donde la tolerancia cambia la selección:", diff)
'@ | .\.venv\Scripts\python.exe -
```

## Tests que respaldan

- `backend/tests/test_student_state_v352.py` — política de `floor_level`, robustez,
  migración legacy de `learning_profile`, `set_level_state`, contrato HTTP.
- `backend/tests/test_difficulty_engine_v352.py` — capacidad, reto por dimensión,
  `fit` (distancia/overshoot/cobertura/`within`), selector (incl. contexto sin
  vector y degradación por cobertura), techo del ítem A1 con alumno C2, tolerancia,
  forma del payload y **paridad GET↔POST**.
- `backend/tests/test_users.py` / `test_user_profile.py` — filtro `is_test`,
  `DELETE` acotado, borrado de filas dependientes.
- `launcher/tests/test_status.py` — `read_users` excluye perfiles de prueba.
- `frontend/src/features/listening/abLoop.test.ts` y `audioController.test.ts` —
  máquina de estados A/B y `play` idempotente/rebobinado.
