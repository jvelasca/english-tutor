# v3.70.0 — Auditoría pedagógica + CEFR

> **Release de MEDICIÓN, no de capacidad.** **SIN migración**, **SIN bump de
> `GENERATOR_VERSION`**, **SIN tocar el banco**, **SIN tocar el currículum**,
> **SIN capacidad pedagógica nueva**, **SIN tocar el argmax del Planner** y **con
> cero líneas de LÓGICA de producto** (el único diff en rutas de producto son los
> **bumps de versión**: `backend/config.py`, `frontend/package.json` +
> `package-lock.json`). Lo que entra son **cinco subcomandos NUEVOS y de SOLO
> LECTURA** en `backend/scripts/audit_dossier.py`, **6 dossiers**, **48 tests**
> nuevos y **documentación**. Igual que V3.69 validó la **arquitectura** del
> Adaptive Engine, V3.70 mide la **pedagogía real** de lo que ese motor sirve.
>
> **Regla dura declarada (briefing maestro `agentes/v370-auditoria-pedagogica.md`):**
> *V3.70 es una auditoría, no una release de capacidad.* **No se corrige nada**
> aunque se encuentre: cada hallazgo se **declara** y se **asigna a una fase**
> (contenido → V4.0.x · motor y acreditación → Planner 4.0 · instrumentos →
> V4.0.x/V3.72). El alcance **excluye explícitamente** los **6 P2 de la auditoría
> de V3.69**, que siguen abiertos. **V3.70 no cierra ningún P**: convierte «creemos
> que el contenido y la pedagogía son correctos» en «**está medido, acotado y
> declarado**».

## Contexto

La auditoría `X` de V3.67 fijó como **PRÓXIMO GRAN FOCO** la pedagogía y `PLAN.md`
`### M13` lo escribió como `→ V3.70`. V3.68 congeló la arquitectura del motor
adaptativo (auditoría `Y`: 9,3/10, **0 P1**) y V3.69 demostró **por HTTP** que la
cadena `Evidence → Student State → Decision Projection → Task selection →
Decision → Serving → Attempt → Outcome → Evidence` funciona **como una sola
pieza**, con **diff de producto cero en lógica**. Con el núcleo **cerrado y
validado**, el foco dejó de ser *cómo decide* el motor y pasó a ser **qué sirve**:
¿el contenido A1..C2 **es** de su nivel?, ¿están cubiertas todas las destrezas?,
¿se corrige de verdad?, ¿«demostrado» significa lo que dice?, ¿los instrumentos de
nivelación funcionan?

El estado de partida tenido en cuenta:

1. **Había cinco herramientas de medición** (`audit_dossier.py`: `corpus-stats`,
   `curriculum-stats`, `speaking-stats`, `sample`, `mc-bias`) pero **ninguna medía
   adecuación CEFR, cobertura de destrezas, feedback, validez de la maestría ni
   instrumentos de nivelación**.
2. **`docs/audit/generated/` estaba desincronizado con el disco**: las cifras
   publicadas de `curriculum-stats` (C1 = 14, C2 = 14 objetivos) **no**
   coincidían con los objetivos reales (20 y 20), y **auditorías previas se
   apoyaron en esas cifras**.
3. Los dossiers pedagógicos anteriores describían **intención declarada**
   (política, tracks P1–P6) pero **nunca la confrontaban contra el contenido y el
   código** de forma reproducible.

V3.70 se ataca con **medición determinista y regenerable** (nunca lectura a ojo),
con **tests que fijan cada hallazgo** y con una decisión de método explícita: **el
instrumento de medición no es una ruta de producto** — se declara como tal.

## A · Instrumentos de medición (nuevos, solo lectura)

Cinco subcomandos **nuevos** en `backend/scripts/audit_dossier.py`, con el mismo
patrón que los cinco existentes (`_write_generated`, salida en
`docs/audit/generated/`) y **sin escribir nunca en `data/` ni en `curriculum/`**:

| Subcomando | Qué mide |
| --- | --- |
| `cefr-adequacy` | Adecuación declarada frente a `docs/audit/CEFR-REFERENCE.md`: dificultad escalar, `speech_rate`, monotonía, `connected_speech` declarado **vs realizado**, resolución de los ítems `inference` y forma de los MC. |
| `skill-coverage` | Matriz modalidad × {competencias, matriz CEFR, canal de evidencia, contenido, scorer, UI} **con la existencia de los artefactos comprobada en disco**. |
| `feedback-coverage` | Canal de corrección por destreza + cobertura de la política de corrección. |
| `mastery-claims` | Los 4 estados, gates, mínimos de la matriz de 48 celdas y línea base sin evidencia. |
| `assessment-instruments` | Placement, exámenes, remediación, gate de unidad y equivalencia de los umbrales de banda. |

Se declaran honestamente como **herramienta de medición, no ruta de producto**.

## B · AA — Adecuación CEFR del contenido

Dossier: `docs/audit/AA-PED-CONTENIDO-CEFR.md` · Test: `backend/tests/test_ped_content_cefr_v370.py` (8)

- **P0 — el 89,4 % de los 368 checks del currículum tiene la respuesta correcta en
  la posición 0** (329/368): un alumno que marque **siempre la primera opción**
  acierta casi **9 de cada 10**. El corpus de listening, en cambio, **sí** está
  equilibrado (~25 % por posición).
- **P1** — **A1 entero por encima de su banda de velocidad** (86/200 por encima del
  techo de 115 wpm) y **C1/C2 casi enteros por debajo** (18/20 y 19/20). ·
  `connected_speech: true` **sin ninguna reducción real** en la transcripción en
  **C1 14/14 y C2 20/20**.
- **P2** — escalera de velocidad **no monótona** (el máximo de B2, 185 wpm, supera
  al de C1, 170) · 4 de los 5 ítems `inference` de A2 se resuelven con una **palabra
  literal** · sesgo de longitud.
- **P3 — deriva documental corregida**: `docs/audit/generated/` estaba
  desincronizado con el disco (`curriculum-stats` declaraba **C1 = 14** y
  **C2 = 14** objetivos frente a los **20 y 20** reales) y **auditorías previas se
  apoyaron en esas cifras**.
- **Limpio (verificado)**: **0 de 490 ítems fuera de su banda de DIFICULTAD**, 116
  objetivos · 368 checks · 512 actividades, 0 objetivos sin actividades o sin
  checks y 0 checks fuera de las `skills` de su objetivo.

## C · AB — Cobertura de destrezas

Dossier: `docs/audit/AB-PED-COBERTURA.md` · Test: `backend/tests/test_ped_coverage_v370.py` (10)

- **P1** — corpus de listening **B1–C2 al 13,9–20,0 %** de su objetivo declarado
  (`LISTENING_CORPUS_TARGETS`) · `reading` declara **15 objetivos y 18 checks pero
  no existe `backend/services/reading.py`** · **el manifest de la biblioteca de
  audio humano está versionado y vacío** (`entries: []`: **todo** el listening es
  TTS) · `mediation` **no tiene competencias, ni corpus, ni canal, ni scorer, ni
  UI**.
- **P2** — `interaction` **sin competencias y sin canal** pese a tener módulo,
  corpus de 66 ítems y UI · escenarios de speaking con **1** en A1 y **1** en C1.
- **P3** — `pre-a1` **sin curso** (0/7 celdas) · `pronunciation` fuera de la matriz
  **a propósito**.

## D · AC — Feedback y corrección

Dossier: `docs/audit/AC-PED-FEEDBACK.md` · Test: `backend/tests/test_ped_feedback_v370.py` (10)

- **P1** — **4 de las 7 reglas de grammar nunca pueden confirmarse** (su
  `confidence` está por debajo de `CONFIRMED_THRESHOLD = 0.8`) · **5 de las 7 no
  tienen patrón de uso correcto**, así que **solo 2 pueden alcanzar
  `MASTERY_STREAK = 3`** · `reading` y `mediation` **sin ningún canal de
  corrección**.
- **P2** — `listening`, `pronunciation`, `vocabulary` e `interaction` tienen
  corrección **solo de puntuación, sin mensaje** · el error detectado **dentro de
  las rúbricas** solo **resta nota** (`1.0 − 0.25·len(errors)`) y **no genera la
  explicación**, que siempre la redacta el LLM desde el prompt.
- **Correcto y fijado por test** — 5 categorías formales de corrección, guía para
  los **7 niveles** (incluida Pre-A1) y **la nota la decide el scorer determinista,
  nunca el LLM** (verificado ejecutando `score_writing`/`score_speaking` **sin
  modelo**).

## E · AD — Validez de la afirmación de maestría

Dossier: `docs/audit/AD-PED-MAESTRIA.md` · Test: `backend/tests/test_ped_mastery_v370.py` (10)

- **P1** — **tres registros con tres tamaños para el mismo concepto** de destreza
  evaluable (**9 modalidades · 8 en matriz · 7 canales**) · **`interaction` y
  `mediation` no pueden acreditar evidencia por ninguna vía** aunque la matriz les
  exija requisitos en los 6 niveles.
- **P2** — **`novel_required = 0` en las 48 celdas** pese a que el emisor real de
  `novel` **existe desde V3.26**: **el briefing asumía que no existía y la
  verificación lo corrigió** — la **señal existe, la exigencia no** · **las filas
  sin `objective_id` resoluble no acreditan éxito**, medido **conductualmente**
  (`result 1,0` → `success False`), lo que deja **fuera del gate espaciado** a
  speaking assessment y misión (F-K3).
- **Correcto y fijado** — **sin evidencia no se afirma nada** (9/9 modalidades en
  `not_started`, banda `—`) y `transfer_required` **crece 0 → 4**.

## F · AE — Instrumentos de nivelación

Dossier: `docs/audit/AE-PED-INSTRUMENTOS.md` · Test: `backend/tests/test_ped_instruments_v370.py` (10)

- **P1** — **el criterio de parada por precisión del placement es inalcanzable**:
  pide `SE < 0,5` y la mejor cota con los 8 ítems declarados es **`0,7071`** (**cota
  analítica** del modelo 1PL declarado, **no** simulación) · **el examen de B1
  tiene los 12 ítems en dificultad 1**, igual que el de A1, así que **no se
  escala** · **cuatro de seis niveles sin examen final** (A2, B2, C1, C2).
- **P2** — el placement **mide reconocimiento o meta-lenguaje** para
  listening/speaking/writing/pronunciation (lo declara su **propio docstring**) ·
  **sesgo de forma**: la correcta es la **más larga única en el 50 %** y **más
  larga o empatada en el 75 %**; **70,8 %** en la **posición 1** y la **posición 3
  nunca** es correcta · umbrales de banda **triplicados** y sub-bandas `+` que
  **ningún estimador emite**.
- **Correcto y fijado** — los **tres estimadores coinciden en toda la rejilla** (0
  desacuerdos) y el banco de placement **no tiene huecos de dificultad** (4 ítems
  por cada nivel 1..6).

## G · AF — Síntesis

Dossier: `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`

Matriz consolidada: **1 P0 · 15 P1 · 12 P2 · 5 P3** (**33 hallazgos abiertos**) y
**4 propiedades positivas** verificadas. **Cinco cruces** que solo se ven mirando
los cinco ejes juntos:

1. **`reading` roto en tres planos** (contenido, corrección y remediación) y
   **`mediation` en cinco** (competencias, corpus, canal, scorer y UI).
2. **La forma de los ítems es el patrón más extendido**: checks del currículum,
   corpus de listening y placement **comparten el mismo defecto de autoría**.
3. **Lo declarado supera a lo realizado en cinco instancias**: `connected_speech`,
   `novel_required`, sub-bandas `+`, biblioteca de audio y `mediation`.
4. **El producto está más completo donde el alumno empieza que donde debería
   llegar**: A1/A2 al **100 %** de su objetivo de corpus y **únicos niveles con
   examen**, frente a **B1–C2 al 14–20 %**.
5. **La maestría se puede afirmar sin las dos modalidades que más la
   necesitarían** (`interaction` y `mediation`), porque ningún canal las alimenta.

## H · Tests

Cinco ficheros nuevos, **48 tests**:

| Fichero | Tests |
| --- | --- |
| `backend/tests/test_ped_content_cefr_v370.py` | 8 |
| `backend/tests/test_ped_coverage_v370.py` | 10 |
| `backend/tests/test_ped_feedback_v370.py` | 10 |
| `backend/tests/test_ped_mastery_v370.py` | 10 |
| `backend/tests/test_ped_instruments_v370.py` | 10 |

Cada test fija un hallazgo **medido**: si alguien cierra un hueco, **el test falla**
y obliga a **re-auditar el eje**. Backend **2600 passed** (2552 → **+48**).

## Honestidad — lo que V3.70 NO demuestra

1. **No demuestra eficacia pedagógica.** Ha medido **adecuación declarada frente a
   un criterio interno** (`docs/audit/CEFR-REFERENCE.md`, que **no** es un documento
   CEFR normativo), **no aprendizaje** de ningún alumno.
2. **No valida el nivel real de un alumno.** El placement se auditó **como
   instrumento**, no contra una evaluación externa.
3. **No audita la calidad acústica de un solo ítem.** No hay audio humano grabado:
   todo el análisis de listening es sobre **metadatos declarados**.
4. **No audita el texto que produce el LLM en ejecución.** Se auditó la **política
   declarada**.
5. **No audita el frontend.**
6. **No cierra los 6 P2 de la auditoría de V3.69**, que siguen abiertos por decisión
   de alcance.
7. **La cota del placement es analítica**, no empírica.
8. **No corrige nada.** Las 33 insuficiencias quedan declaradas y **asignadas a
   fase**: **contenido → V4.0.x · motor y acreditación → Planner 4.0 · instrumentos
   → V4.0.x/V3.72**.

El valor de V3.70 es que **dejan de ser opinión**.

## Asignación a fase (deuda declarada, no cerrada)

| Fase | Qué recoge |
| --- | --- |
| **V4.0.x (contenido)** | Posición 0 en los 368 checks · velocidad A1/C1/C2 · `connected_speech` no realizado · escalera de velocidad no monótona · ítems `inference` resolubles por palabra literal · forma de los MC (longitud y posición) · corpus de listening B1–C2 · audio humano real. |
| **Planner 4.0 (motor y acreditación)** | `novel_required = 0` en las 48 celdas · canales de evidencia de `interaction` y `mediation` · filas sin `objective_id` fuera del gate (F-K3) · `SCAFFOLDING_PENALTY` (hallazgo E17 de V3.69). |
| **V4.0.x / V3.72 (instrumentos y UX)** | Criterio de parada del placement · examen de B1 en dificultad 1 · exámenes de A2/B2/C1/C2 · sub-bandas `+` sin emisor · escenarios de speaking A1/C1 · `pre-a1` como producto. |

## Tabla de hallazgos (consolidada, con severidad)

| ID | Sev. | Eje | Hallazgo | Fase |
| --- | --- | --- | --- | --- |
| AA-01 | **P0** | AA | 329/368 checks (89,4 %) con la correcta en la **posición 0** | V4.0.x |
| AA-02 | P1 | AA | A1 entero por encima de su banda de velocidad (86/200) | V4.0.x |
| AA-03 | P1 | AA | C1/C2 casi enteros por debajo de su banda (18/20, 19/20) | V4.0.x |
| AA-04 | P1 | AA | `connected_speech: true` sin reducción real (C1 14/14, C2 20/20) | V4.0.x |
| AA-05 | P2 | AA | Escalera de velocidad no monótona (B2 185 wpm > C1 170) | V4.0.x |
| AA-06 | P2 | AA | 4 de 5 ítems `inference` de A2 resolubles por palabra literal | V4.0.x |
| AA-07 | P2 | AA | Sesgo de longitud de los MC | V4.0.x |
| AA-08 | P3 | AA | Deriva documental de `docs/audit/generated/` (C1/C2 = 14 vs 20) | **corregida en V3.70** |
| AB-01 | P1 | AB | Corpus de listening B1–C2 al 13,9–20,0 % de su objetivo | V4.0.x |
| AB-02 | P1 | AB | `reading` sin `services/reading.py` (15 objetivos, 18 checks) | V4.0.x + Planner 4.0 |
| AB-03 | P1 | AB | Manifest de audio humano versionado y **vacío** (`entries: []`) | V4.0.x |
| AB-04 | P1 | AB | `mediation` sin competencias, corpus, canal, scorer ni UI | Planner 4.0 |
| AB-05 | P2 | AB | `interaction` sin competencias y sin canal (tiene módulo y UI) | Planner 4.0 |
| AB-06 | P2 | AB | Escenarios de speaking: **1** en A1 y **1** en C1 | V4.0.x |
| AB-07 | P3 | AB | `pre-a1` sin curso (0/7 celdas) | V4.0.x |
| AB-08 | P3 | AB | `pronunciation` fuera de la matriz (a propósito) | — |
| AC-01 | P1 | AC | 4 de 7 reglas de grammar nunca confirmables (`confidence < 0.8`) | Planner 4.0 |
| AC-02 | P1 | AC | Solo 2 de 7 reglas pueden alcanzar `MASTERY_STREAK = 3` | Planner 4.0 |
| AC-03 | P1 | AC | `reading` y `mediation` sin canal de corrección | Planner 4.0 |
| AC-04 | P2 | AC | 4 modalidades con corrección solo de puntuación, sin mensaje | Planner 4.0 |
| AC-05 | P2 | AC | El error en rúbricas resta nota y no genera la explicación | Planner 4.0 |
| AD-01 | P1 | AD | Tres registros con tres tamaños (9 · 8 · 7) para la misma destreza | Planner 4.0 |
| AD-02 | P1 | AD | `interaction` y `mediation` no acreditan evidencia por ninguna vía | Planner 4.0 |
| AD-03 | P2 | AD | `novel_required = 0` en las 48 celdas (emisor existe desde V3.26) | Planner 4.0 |
| AD-04 | P2 | AD | Filas sin `objective_id` no acreditan éxito (F-K3) | Planner 4.0 |
| AD-05 | P3 | AD | `pronunciation` fuera de la matriz pero dentro de `MASTERY_SKILLS` (mismo hallazgo visto desde AB) | Constancia documental |
| AE-01 | P1 | AE | Criterio de parada del placement inalcanzable (`SE ≥ 0,7071 > 0,5`) | V4.0.x / V3.72 |
| AE-02 | P1 | AE | Examen de B1 con los 12 ítems en dificultad 1 (no escala) | V4.0.x |
| AE-03 | P1 | AE | Cuatro de seis niveles sin examen final (A2, B2, C1, C2) | V4.0.x |
| AE-04 | P2 | AE | Placement por reconocimiento/meta-lenguaje en 4 destrezas | V3.72 |
| AE-05 | P2 | AE | Sesgo de forma del placement (50 % / 75 %; posición 3 nunca) | V4.0.x |
| AE-06 | P2 | AE | Umbrales de banda triplicados y sub-bandas `+` sin emisor | V3.72 |
| AE-07 | P3 | AE | Banco de remediación de `reading` con solo **3** ítems (justo la destreza sin scorer) | V4.0.x |

**Por eje (idéntico a la matriz de `AF`):** AA = 1 P0 · 3 P1 · 3 P2 · 1 P3 · AB = 0 · 4 ·
2 · 2 · AC = 0 · 3 · 2 · 0 · AD = 0 · 2 · 2 · 1 · AE = 0 · 3 · 3 · 1.

**Totales: 1 P0 · 15 P1 · 12 P2 · 5 P3 = 33 hallazgos abiertos** y **4 propiedades
positivas** (una por eje AA/AC/AD/AE). Nota de conteo: `pronunciation` fuera de la
matriz aparece **en AB y en AD** (dos ejes, un mismo hecho). La **deriva documental
de `docs/audit/generated/`** (AA-08) se cuenta como el P3 del eje AA y queda
**regenerada en V3.70**. Matriz completa, con evidencia `archivo:línea` y comando de
reproducción, en `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`.

## Fuera de alcance (deliberadamente **no** tocado en V3.70)

1. **Los 6 P2 de la auditoría de V3.69** (cold start sin provenance,
   `abandoned_count` asimétrico, reopening de caducadas, semántica de
   `SCAFFOLDING_PENALTY`, `invalid_transition` por `StrictMode`, verificabilidad
   del CI). **Siguen abiertos.**
2. **Remediación de contenido**: volumen de corpus B1–C2, escenarios A1/C1,
   exámenes B2/C1/C2, curso Pre-A1 y audio humano grabado. Se **miden**, no se
   **corrigen**.
3. **Motor**: rediseño del Planner 4.0, Expected Learning Gain real y calibración
   con tráfico real.
4. **Validez empírica con alumnos reales** (fase de observación).
5. **Frontend**: no se audita ni se toca.
6. **`DECISION_POLICY_VERSION` y `GENERATOR_VERSION`**: **no** se tocan.

## Verificación

- `python -m ruff check .` en **`backend/`** (el gate real del CI:
  `working-directory: backend`) limpio.
- `pytest` backend **2600 passed** (2552 → **+48**).
- `vitest` **659** (sin cambios), `tsc`/`build` OK, launcher **75 passed**.
- `check_release_consistency` **3.70.0** en los 6 sitios.
- `check_beta_v3`, `content_validation` y `transfer_validation` OK.
- `docs/audit/generated/` **regenerado** con los cinco subcomandos nuevos
  (`cefr-adequacy`, `skill-coverage`, `feedback-coverage`, `mastery-claims`,
  `assessment-instruments`) + los cinco existentes; `curriculum-stats` queda
  **corregido** (C1 = 20, C2 = 20 objetivos).

**Honestidad sobre la verificación:** invocar `ruff` desde la **raíz** del repo
**no** es el gate del CI y reporta **1 `DTZ005` preexistente** en
`scripts/purge_virtual_testers.py:198` (`datetime.now()` sin `tz`), un fichero
**no tocado** por V3.70 (último cambio: `release(v3.52.1)`); se **registra** en
lugar de declararlo limpio.

**Deriva de formato, medida (no estimada):** `ruff format --check .` sobre
`backend/` reporta **317 de 377 ficheros (84,1 %) que se reformatearían** y solo
**60 ya formateados**. `ruff format --check` **no es un gate del CI** (`ci.yml`
corre únicamente `ruff check .`), la deriva es **preexistente** y **V3.70 no la
introduce ni la agrava**: sus 5 ficheros de test y sus 5 subcomandos nacen de
`ruff check` limpio, y **no se reformatea el árbol** porque haría el diff de la
release inauditable. Queda **cuantificada** para decidir su fase de limpieza.

**Intermitencias del entorno local, declaradas (no ocultadas):**

1. **Primera ejecución de la suite completa tras el reinicio de la máquina:**
   *access violation* del intérprete (`0xC0000005`, con volcado de hilos en
   `main.py::_auto_backup_daemon`) tras 32 tests, en un árbol cuyo diff **no toca
   hilos ni base de datos**. **No reproducible**: la ejecución inmediatamente
   posterior dio **2560 passed** (los 48 nuevos incluidos) y la final **2600
   passed**, ambas sin fallos. Se acota al **entorno local**.
2. **`resize.spec.ts`**: V3.69 lo registró como intermitente en local y verde en
   el CI. **Re-medido en V3.70: 3/3 verde** en ejecuciones aisladas (7,7 s, 7,8 s
   y 12,2 s) con el backend apagado (`ECONNREFUSED 127.0.0.1:8000` en el proxy,
   esperado: la spec corre sin backend). Es decir, **no se reproduce de forma
   determinista en aislamiento**: si aparece, viene de la ejecución **conjunta**
   de la suite (paralelismo/recursos), no de la spec. Queda **acotado y con
   medición**, no como afirmación heredada.

## Roadmap

**V3.71** runtime/offline/instalación (**siguiente**; los tracks P1–P6 de M13
quedan **medidos y acotados, no cerrados**) → **V3.72** UX/product completion →
**V3.73** auditoría final técnica → **V4.0** («English Tutor, primera versión
completa y estable»).
