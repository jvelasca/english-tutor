# Cómo lanzar los subagentes (sin gastar tokens)

El gerente del proyecto (el asistente) **no ejecuta** estos subagentes. Tú los
lanzas desde tus propios agentes locales. Cada subagente es un archivo Markdown
**autocontenido**: incluye todo lo que el agente necesita para trabajar sin
pedir más contexto.

> **Estado actual (2026-09-14): `v3.62.0` Student Skill State 4.0 (modalidad ×
> competencia) IMPLEMENTADA y verificada en local** — unifica los dos modelos del
> alumno en **UN** estado `{modalidad: {competencia: entry}}` alimentado por las
> **cuatro** fuentes de evidencia con la **misma** puerta espaciada y el gate
> **reutilizado** de `services/competence.py`, sin umbrales nuevos, y es
> **aditiva**: la decisión de tareas sigue leyendo **exactamente** el estado de
> V3.61 (probado **byte a byte**). Verificación local: `pytest` **2404 passed**,
> `ruff` limpio, launcher **75**, `tsc` OK, `vitest` **651**, `build` OK,
> `check_release_consistency` **3.62.0**, `check_beta_v3`/`content_validation` OK y
> `transfer_validation` **20 familias / 1020 superficies / 0 errores**;
> **pendiente commit, CI 6/6 y tag** `v3.62.0`. Briefing y detalle en
> `agentes/v362-student-skill-state-4.md` y `release-notes-v3.62.0.md`.
> **Siguiente incremento esperado: V3.63 — Observed Task Difficulty 2.0**
> (el **recableado** de la decisión de tareas al eje de competencia es
> V3.63/V3.64). **V3.61.0 `Instance-aware Evidence + Anti-spoiler Guard` está
> CERRADA en `main`** (commit `1b4af42`,
> **CI 6/6** en el run
> [34831625926](https://github.com/jvelasca/english-tutor/actions/runs/34831625926),
> etiqueta anotada `v3.61.0` creada y empujada). **V3.62 — Student Skill State 4.0
> (modalidad × competencia)** cierra el
> **P1-03** de la auditoría `S` de V3.60 (el estado del alumno **no tiene eje de
> competencia** y toda la evidencia no léxica —grammar, listening por
> subdestreza, pronunciation, reading, writing, speaking— es **inerte**) **sin
> recablear** todavía la decisión de tareas (eso es V3.63/V3.64), con briefing
> autocontenido en `agentes/v362-student-skill-state-4.md`. Ver `docs/RELEVO.md`
> (nota superior y sección 0 "START HERE"). **V3.61 — Instance-aware Evidence +
> Anti-spoiler Guard** cerró los **2 defectos funcionales** de la auditoría `T` de
> V3.60 (**fuga del target** en una superficie generada de `shopping` e **identidad
> de instancia no inmutable** en el POST) y la parte determinista de los **P1** de
> la auditoría `S` (cap **estratificado**, rotación no secuencial y **validador de
> contenido** del `instance_space`): guard anti-spoiler por unidad objetivo,
> identidad inmutable de instancia GET→POST, **`context_instance` aditivo en el
> ledger** (columna idempotente, sin migración explícita y manteniendo
> `context_id = FAMILIA`) y banco **358 → 1020 superficies**. Verificación local:
> `pytest` **2373 passed**, `ruff` limpio, launcher **75**, `tsc` OK, `vitest`
> **651**, `build` OK, `check_release_consistency` **3.61.0**,
> `check_beta_v3`/`content_validation` OK y `transfer_validation` **20 familias /
> 1020 superficies / 0 errores**. Detalle en `release-notes-v3.61.0.md`. V3.60
> (**Context Engine 4.0: Instance Specification →
> Parameterized Instance**) es una release **SIN migración de BD, SIN bump de
> `GENERATOR_VERSION` y SIN cambios de UI** que cierra los cuatro hallazgos de la
> auditoría externa **R** de V3.59 (**P1-1** «3 superficies deterministas siguen
> siendo memorizables», **P1-2** «la instancia puede cambiar la dificultad real sin
> poder declararlo», **P2-6** «Context Engine todavía manual/finito», **P2-7** «la
> instancia no genera dificultad»): sustituye las **60 consignas escritas a mano**
> por un **ESPACIO de instancias PARAMETRIZADO** por familia (**FAMILIA →
> ESPECIFICACIÓN → INSTANCIA**). La **familia** sigue siendo la identidad
> pedagógica y la **unidad de EVIDENCIA** (`context_id` del ledger), así que **el
> ledger no se fragmenta** y no cambian los umbrales, la escalera `transfer_state`,
> `context_distance`, `context_diversity`, la novedad, `CEFR_CAPACITY` ni el
> Difficulty Engine; la **instancia** pasa a declarar metadatos **NO
> identitarios** (`scenario`/`goal`/`register`/`difficulty_delta`/`skill_delta`) y
> `CONTEXT_INSTANCE_KEYS` crece de 2 a 7 claves (la intersección con la identidad
> de familia sigue siendo `{"prompt"}`). El contenido sigue siendo **DECLARADO**
> (no hay LLM en el camino de la evidencia: se genera la COMBINACIÓN de valores
> declarados, no el texto) y la expansión es **determinista** (producto cartesiano
> en orden declarado, cap `CONTEXT_INSTANCE_SPACE_MAX = 96`, dedup, `_slug` sin
> `hash()`). `CONTEXT_INSTANCE_SPACE_MIN = 12` superficies TOTALES por familia es
> el invariante anti-memorización: **el banco pasa de 60 a 358 superficies** con
> las dos `instances` de V3.59 conservadas byte a byte en los índices 1–2 y la
> superficie 0 **histórica**. La **carga de la superficie servida** pasa a ser
> explícita (`difficulty.normalize_delta`/`apply_delta`, delta ±2 y clamp 1..5) y
> **persistida** de forma aditiva: `domain/vocabulary.py` escribe
> `transfer.served_difficulty(context_id, summary["contexts"])` —el MISMO mapa que
> el GET/POST— en las columnas de V3.55, así que la dificultad guardada
> corresponde a la tarea **realmente servida**. Contrato **+8 claves**
> (`instance_scenario`/`instance_goal`/`instance_register`/
> `instance_difficulty_delta`/`instance_difficulty_vector`/`instance_difficulty`/
> `instance_skills`/`instance_generated`), **36 en total**, con espejo TS opcional;
> las **28 de V3.59** quedan intactas y fijadas por test. Tests: nuevo
> `test_context_engine_v360.py` (23, con **equivalencia pedagógica** de las
> superficies de una familia y end-to-end HTTP de la superficie generada con el
> vector efectivo persistido), `pytest` **2335 passed** en local, launcher
> **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651**, `npm run build` OK y
> `check_release_consistency` **3.60.0**. **CI 6/6 en verde** (run
> [34814504063](https://github.com/jvelasca/english-tutor/actions/runs/34814504063)
> sobre `2c79040`), con la etiqueta anotada `v3.60.0` creada y empujada. La V3.59
> (**Context Engine 3.0: Context Bank Family/Instance**) sigue inmediatamente
> detrás; y antes, la V3.58
> (**Sense Engine 2.0**), la V3.57 (**Planner 2.0: argmax `(skill, actividad)`
> sobre ELV**), la V3.56 (**Planner 2.0 / `expected_learning_value`**, la mitad
> que ordena), la V3.55 (**Task Difficulty 3.0**, tres columnas de BD, el último
> cambio de ledger), la V3.54 como **Student Skill State 3.0** (P2-03), la V3.53.1
> como **Observed CEFR Safety Gate** (P1-01 de V3.53.0), la V3.53.0 como
> **Learner Skill State 2.0 + `observed_difficulty`** (P1-02), la V3.52.2 como
> **cierre de los dos P2 de la auditoría externa Q** y la V3.52.1 como el
> **hotfix de producto**. Los P3-02/P3-03 quedan abiertos y aceptados. El
> incremento cerrado fue **V3.61 — Instance-aware Evidence + Anti-spoiler
> Guard** (**cerrada**, ver arriba, con **CI 6/6**), que cerraba los **2 defectos funcionales**
> de la auditoría `T` de V3.60
> (**fuga del target** en una superficie generada de `shopping`,
> `backend/services/transfer.py:1074`/`:2978`, e **identidad de instancia no
> inmutable** en el POST, `backend/schemas/vocabulary.py:826` +
> `backend/domain/vocabulary.py:850`) y la parte determinista de los **P1** de la
> auditoría `S` (cap **estratificado**, rotación no secuencial y **validador de
> contenido** del `instance_space`): guard anti-spoiler por unidad objetivo,
> identidad inmutable de instancia GET→POST y **`context_instance` aditivo en el
> ledger** sin migración y manteniendo `context_id = FAMILIA`. Las dos auditorías
> están archivadas en `docs/audit/S-AUDITORIA-TOTAL-V360.md` y
> `docs/audit/T-AUDITORIA-TOTAL-V360.md`, y el veredicto consolidado en la nota
> superior de `docs/RELEVO.md`. El **relevo a V3.62** está escrito en
> `agentes/v362-student-skill-state-4.md` (modelo unificado **modalidad ×
> competencia** con las **cuatro** fuentes de evidencia y el **mismo** rigor de
> muestra espaciada; aditivo, con la decisión de tareas **intacta**) y el de V3.61
> en `agentes/v361-instance-aware-evidence.md`. El briefing de V3.60 vive en
> `agentes/v360-context-engine-4.md` (V3.59 en `agentes/v359-context-engine-3.md`,
> V3.58 en `agentes/v358-sense-engine-2.md` y V3.57 en
> `agentes/v357-argmax-elv.md`); el punto de entrada de la auditoría externa de
> V3.60 sigue en `agentes/auditoria-externa-v360.md` y la de V3.59 sigue pendiente
> de informe en `agentes/auditoria-externa-v359.md`. Antes de lanzar cualquier
> subagente, lee esa sección para no partir de un estado obsoleto (premisa 8 y 12:
> relevo al saturar y ancla contra la alucinación).

> **Nota histórica (2026-09-13): `v3.59.0`.** V3.59 (**Context Engine 3.0: Context
> Bank Family/Instance**) fue una release **SIN migración de BD, SIN bump de
> `GENERATOR_VERSION`, SIN cambios de UI y SIN tocar el ledger** que cerró el
> candidato diferido desde V3.48 y el hallazgo **P2-04** de la auditoría de V3.43:
> un banco finito de consignas **FIJAS** se **MEMORIZA** —agotado el banco, el
> alumno repite la misma redacción y puede reciclar una respuesta aprendida en
> lugar de transferir—. V3.59 separa **FAMILIA** de **INSTANCIA**: la **familia**
> (los 20 contextos, su `id` incluido) sigue siendo la identidad pedagógica y la
> **unidad de EVIDENCIA** —el `id` es el `context_id` del ledger—, así que el
> banco **no se fragmenta** y no cambian los umbrales, la escalera
> `transfer_state`, `context_distance`, `context_diversity`, la novedad ni el
> Difficulty Engine; la **instancia** es una superficie **DECLARADA** de la misma
> familia (otra redacción del mismo escenario) y la superficie **0** es SIEMPRE la
> consigna **histórica**, byte a byte. La rotación es `N % nº_superficies` sobre
> los **intentos** del ítem en esa familia: sin evidencia la degradación es
> **EXACTA** a V3.58 y con intentos cada estancia cambia la redacción.
> `CONTEXT_INSTANCE_KEYS` es **lista blanca** (una instancia no puede tocar la
> identidad) y `CONTEXT_INSTANCES_MIN = 2`: el banco pasa de **20 consignas a 60
> superficies** sin fragmentar el ledger. El contrato gana **3 claves aditivas**
> (`context_instance`/`instance_index`/`instance_count`) y las **25 de V3.58**
> quedan intactas y fijadas por test. NO toca `transfer_state`, sus umbrales,
> `context_signals`, `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el Sense
> Engine. Tests: nuevo `test_context_engine_v359.py` (16, con end-to-end HTTP de
> la rotación con el pool agotado), `pytest` **2312 passed** en local, launcher
> **75 passed**, `ruff` limpio, `tsc` OK, `vitest` **651** y
> `check_release_consistency` **3.59.0**. La V3.58 (**Sense Engine 2.0:
> `surface → lemma → sense → semantic_fit`**) sigue inmediatamente detrás; la
> V3.57 (**Planner 2.0: argmax `(skill, actividad)` sobre ELV**) la precede, con
> la V3.56 (**Planner 2.0 / `expected_learning_value`**, la mitad que ordena)
> antes; la V3.55 (**Task Difficulty 3.0**, tres columnas de BD) es el último
> cambio de ledger; la V3.54 como **Student Skill State 3.0** (P2-03), la V3.53.1
> como **Observed CEFR Safety Gate** (P1-01 de V3.53.0), la V3.53.0 como **Learner
> Skill State 2.0 + `observed_difficulty`** (P1-02), la V3.52.2 como **cierre de
> los dos P2 de la auditoría externa Q** y la V3.52.1 como el **hotfix de
> producto**. Los P3-02/P3-03 quedan abiertos y aceptados. El incremento que siguió
> fue **V3.60** (Context Engine 4.0; ver la nota superior). El briefing de V3.59
> vive en `agentes/v359-context-engine-3.md` (V3.58 en
> `agentes/v358-sense-engine-2.md` y V3.57 en `agentes/v357-argmax-elv.md`), y su
> auditoría externa se prepara en `agentes/auditoria-externa-v359.md`.

## Cómo usar un subagente

1. Abre el archivo `agentes/<nombre>.md`.
2. Copia su contenido completo y pégalo como prompt en tu agente local
   (o ábrelo como archivo de contexto/tarea en tu agente).
3. El agente local trabaja y devuelve el resultado.
4. Pega el resultado de vuelta aquí; el gerente revisa e integra o genera el siguiente paso.

## Estado de la biblioteca de briefings

- `agentes/auditoria-externa-v360.md` — **auditoría EXTERNA de V3.60.0 (lista para
  lanzar, 2026-09-14)**: prompt autocontenido para un auditor que **solo ve
  GitHub**. Punto de entrada: repo público, tag anotado **`v3.60.0`** → commit
  `2c79040`, diff `e721fce..2c79040` (18 ficheros, +2854 / −78) y run de CI
  [34814504063](https://github.com/jvelasca/english-tutor/actions/runs/34814504063)
  (debe estar **6/6**). Declara las **11 afirmaciones a falsar** (frontera de
  identidad de 7 claves, `space[:3]` byte a byte de V3.59, determinismo sin
  `hash()`/LLM, `CONTEXT_INSTANCE_SPACE_MIN = 12` y banco de **358 superficies**,
  especificación inservible, delta ±2 con clamp 1..5, degradación exacta sin
  intentos, elección de familia intacta, **+8 claves aditivas**, ledger con
  `served_difficulty` sin migración y números de verificación) y **10 preguntas de
  alto valor** (equivalencia pedagógica real, si el delta puede escalar al Student
  Model, si el GET y el POST pueden divergir, anti-spoiler de la unidad objetivo,
  dedup/colisiones, sesgo del cap, coste en el camino caliente, aditividad del
  contrato, determinismo y si los tests prueban la invariante o la
  implementación). Informe esperado: `docs/audit/S-AUDITORIA-TOTAL-V360.md` (la
  `R` sigue reservada para el informe pendiente de V3.59). Ojo: declara también la
  **re-priorización** de V3.60 (las notas de V3.59 anunciaban generación de
  sentidos) para que no se reporte como hallazgo nuevo.
- `agentes/auditoria-externa-v359.md` — **auditoría EXTERNA de V3.59.0 (ENTREGADA
  la entrada, informe PENDIENTE)**: prompt autocontenido sobre el tag `v3.59.0`
  (`e721fce`, run 34782482120), con 9 afirmaciones a falsar y 8 preguntas de alto
  valor; su informe se esperaba en `docs/audit/R-AUDITORIA-TOTAL-V359.md` (letra
  `R`) y **no está publicado** todavía. Se conserva como histórico del método.
- `agentes/v362-student-skill-state-4.md` — **V3.62 (EJECUTADA, 2026-09-14,
  v3.62.0)**: **Student Skill State 4.0 — modalidad × competencia**. Cierra el
  **P1-03** de la auditoría `S` de V3.60: hoy conviven **DOS** modelos del alumno
  que nunca se tocan — el **adaptativo léxico** (`LEXICAL_SKILLS` ×
  `DIFFICULTY_DIMENSIONS`, única fuente `learning_evidence`, alimenta
  ELV/planner/`transfer.context_for`) y el **curricular** (`MASTERY_SKILLS` × 4
  estados pedagógicos, Student Model, solo `/api/profile`) — y las cuatro
  «dimensiones» del primero son **CARGA de contenido, no competencia**
  (`syntax` ≠ `grammar`, y no hay eje fonológico, ortográfico ni pragmático). El
  incremento unifica los dos en un estado **{modalidad: {competencia: …}}**
  alimentado por **las cuatro** fuentes (`learning_evidence`, `academy_evidence`,
  `listening_attempts`, `pronunciation_attempts`) con el **mismo** rigor de
  muestra espaciada (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`), **reutiliza** el
  gate de `services/competence.py` (sin umbrales nuevos), **no traduce** carga a
  competencia (mapear `syntax→grammar` inventaría evidencia) y es **aditivo**
  (columna idempotente + `LearningProfile.skill_state` + espejo TS). **Alcance
  cerrado con el gerente:** la decisión de tareas (ELV/planner/`difficulty`/
  `transfer.context_for`) queda **intacta** y se prueba **byte a byte**; el
  recableado es V3.63/V3.64. Nota de nomenclatura: la auditoría lo llama «3.0»,
  pero ese nombre ya es V3.54. **Verificación local:** `pytest` **2404 passed**,
  `ruff` limpio, launcher **75**, `tsc` OK, `vitest` **651**, `build` OK,
  `check_release_consistency` **3.62.0**, `check_beta_v3`/`content_validation` OK y
  `transfer_validation` **20 familias / 1020 superficies / 0 errores**;
  **pendiente commit, CI 6/6 y tag**. Ver `release-notes-v3.62.0.md`.
- `agentes/v361-instance-aware-evidence.md` — **V3.61 (EJECUTADA, 2026-09-14,
  v3.61.0)**: **Instance-aware Evidence + Anti-spoiler Guard**. Cierra los **2
  defectos funcionales** de la auditoría `T` de V3.60 (**fuga del target**: la
  superficie servida podía NOMBRAR la unidad objetivo —`shopping` servía «You are
  in a supermarket…» con `supermarket` como unidad—; **identidad de instancia no
  inmutable**: el POST recalculaba la rotación y podía persistir la carga de OTRA
  superficie) y la parte **determinista** de los P1 de `S` (cap **estratificado**,
  rotación **no secuencial** para intentos ≥ 3 y **validador de contenido** del
  `instance_space`, con CLI dentro del job Backend). Guard léxico determinista (sin
  LLM ni WSD: frontera de palabra + variantes inflexivas acotadas), identidad
  inmutable GET→POST (`serve_instance`/`served_difficulty_for_instance`),
  `context_instance` **aditivo** en el ledger (manteniendo `context_id = FAMILIA`,
  sin fragmentar la evidencia) y banco **358 → 1020** superficies. **CI 6/6** (run
  [34831625926](https://github.com/jvelasca/english-tutor/actions/runs/34831625926)).
  Ver `release-notes-v3.61.0.md`.
- `agentes/v360-context-engine-4.md` — **V3.60 (EJECUTADO, 2026-09-14, v3.60.0)**:
  **Context Engine 4.0 — Instance Specification → Parameterized Instance**.
  Sustituye las **60 consignas escritas a mano** por un **ESPACIO de instancias
  PARAMETRIZADO** por familia (**FAMILIA → ESPECIFICACIÓN → INSTANCIA**) sin tocar
  la identidad de evidencia (`context_id` sigue siendo la familia) y **sin
  migración de BD**. Cierra los cuatro hallazgos de la auditoría externa **R** de
  V3.59: **P1-1** (3 superficies deterministas siguen siendo memorizables),
  **P1-2** (la instancia puede cambiar la dificultad real sin poder declararlo),
  **P2-6** (Context Engine todavía manual/finito) y **P2-7** (la instancia no
  genera dificultad). La lista blanca de instancia crece de 2 a 7 claves con
  metadatos **NO identitarios** (`scenario`/`goal`/`register`/`difficulty_delta`/
  `skill_delta`; la intersección con la identidad de familia sigue siendo
  `{"prompt"}`), `CONTEXT_INSTANCE_SPACE_MIN = 12` es el invariante
  anti-memorización (**el banco pasa de 60 a 358 superficies**, con las `instances`
  de V3.59 byte a byte en los índices 1–2 y la superficie 0 histórica) y el
  **contenido sigue siendo DECLARADO** (sin LLM: se genera la COMBINACIÓN de
  valores declarados, no el texto). La **carga de la superficie servida** pasa a
  ser explícita (`difficulty.normalize_delta`/`apply_delta`, delta ±2, clamp 1..5)
  y **persistida de forma aditiva** con `transfer.served_difficulty(context_id,
  summary["contexts"])` en las columnas de V3.55: la dificultad guardada
  corresponde a la tarea **realmente servida**. Contrato **+8 claves** (36 en
  total) con espejo TS opcional y las 28 de V3.59 intactas y fijadas por test.
  **SIN bump de `GENERATOR_VERSION` y SIN cambios de UI.** NO toca
  `transfer_state`, sus umbrales, `context_signals`, `context_diversity`,
  `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el Sense Engine. **Ejecutado**;
  ver `release-notes-v3.60.0.md`.
- `agentes/v359-context-engine-3.md` — **V3.59 (EJECUTADO, 2026-09-13, v3.59.0)**:
  **Context Engine 3.0 — Context Bank Family/Instance**. Separa **FAMILIA** de
  **INSTANCIA**: la familia sigue siendo la identidad pedagógica y la **unidad de
  EVIDENCIA** (`context_id` del ledger) y cada familia declara superficies
  ADICIONALES de la MISMA identidad, servidas por **rotación de intentos**
  (`N % nº_superficies`), con la superficie **0** SIEMPRE la consigna histórica
  (byte a byte). `CONTEXT_INSTANCE_KEYS = ("instance", "prompt")` es lista blanca
  y `CONTEXT_INSTANCES_MIN = 2` el mínimo por familia: el banco pasa de 20
  consignas a **60 superficies** sin fragmentar el ledger. Contrato **+3 claves**
  (28 en total) con espejo TS opcional. **SIN migración, SIN bump de
  `GENERATOR_VERSION` y SIN cambios de UI.** NO toca `transfer_state`, sus
  umbrales, `context_signals`, `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el
  Sense Engine. **Histórico, hecho**; ver `release-notes-v3.59.0.md`.
- `agentes/v358-sense-engine-2.md` — **V3.58 (EJECUTADO, 2026-09-13, v3.58.0)**:
  **Sense Engine 2.0 — `surface → lemma → sense → semantic_fit`**. Cierra la
  mitad que V3.44 dejó abierta: los sentidos `[{pos, gloss}]` se declaraban y se
  cacheaban, pero el juicio comparaba **FAMILIAS POS** y la `gloss` no la leía
  nadie (**dato INERTE**); con dos sentidos de la MISMA familia
  (`bank` = «financial place» / «river side») el motor no podía separarlos.
  Añade `lemma_of`/`lemma_variants` (**surface → lemma**, morfología regular
  declarada, sin diccionario ni lematizador), `gloss_tokens`/`context_window`/
  `sense_overlap` y `select_sense` (**lemma → sense**: familia del rol sintáctico
  → solapamiento con la glosa → orden declarado). **FRONTERA DECLARADA Y
  PROBADA:** la glosa decide el **SENTIDO**, **nunca el VEREDICTO** —
  `semantic_adequacy` conserva la adecuación de V3.44 **EXACTA** (`_adequacy` es
  la regla literal extraída) y **no se amplía `incorrect`**, porque la AUSENCIA
  de solapamiento no demuestra incompatibilidad. El sentido resuelto entra
  **ADITIVO** en `score_transfer_attempt` y en `TransferAttemptOut` (espejo TS
  opcional), así que **deja de ser dato inerte**. **SIN migración de BD, SIN bump
  de `GENERATOR_VERSION`** (la glosa ya estaba cacheada con 1.4.0: se
  RE-INTERPRETA, mismo patrón que V3.57 con `skill_priorities`) **y SIN cambios de
  UI**. NO toca `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `CEFR_CAPACITY`, el scoring, FSRS, el planner ni el
  Difficulty Engine. **Ejecutado**; ver `release-notes-v3.58.0.md`.
- `agentes/v357-argmax-elv.md` — **V3.57 (EJECUTADO, 2026-09-13, v3.57.0)**:
  **Planner 2.0 — argmax `(skill, actividad)` sobre ELV**. Cierra la segunda
  mitad del Planner 2.0: el planner **elige** la tarea por argmax de valor
  esperado entre las candidatas admisibles (`task_candidates`), con el `value`
  **por modalidad** (`skill_priorities`) y el margen medido sobre el **CANAL**
  que la actividad mide (`capacity_skill`: `transfer` declara eje
  `spontaneous_use` pero se evalúa como producción ESCRITA). Alcance CERRADO con
  el gerente: **CONSERVADOR** — el argmax solo actúa **con estado del alumno**;
  **sin él la decisión es EXACTAMENTE la de V3.56.0** (`select_task`). Resuelve
  las deudas `skill_priorities`→`select_task` y el doble conteo de
  `written_production`. **SIN migración de BD** y sin cambios de UI. NO toca
  `transfer_state`, sus umbrales, `context_signals`, `context_diversity`,
  `CEFR_CAPACITY`, el scoring ni FSRS. **Histórico, hecho**; ver
  `release-notes-v3.57.0.md`.
- `agentes/v356-planner-2.md` — **V3.56 (EJECUTADO, 2026-09-13, v3.56.0)**:
  **Planner 2.0 / `expected_learning_value`**
  (P1-03 de la auditoría de V3.52, el último candidato grande abierto). Convierte
  la prioridad del planner de una **suma de urgencia** en un **valor esperado de
  aprendizaje**: `ELV = dificultad_deseable(p) × value`, con `p = P(éxito)`
  derivada de una **tabla declarada por tramos** (`SUCCESS_BY_MARGIN`) sobre el
  MARGEN entre la capacidad del alumno en la modalidad que la tarea evalúa
  (`learner_skill.skill_capacity`) y la dificultad declarada del ítem
  (`difficulty.declared_difficulty`), y `value = priority_score` (mismos pesos
  declarados). Alcance CERRADO con el gerente: **núcleo ELV + orden de la cola
  por ELV**, con `select_task` (la cascada de razones) **intacto** y el argmax
  `(skill, actividad)` diferido a **V3.57**; **SIN migración de BD** y con
  **degradación neutra exacta** (`p = 0.5` → `desirabilidad = 1.0` →
  `ELV = priority` →
  orden IDÉNTICO al de V3.55.0 cuando no hay estado del alumno). NO toca
  `transfer_state`, sus umbrales, `context_signals`, `context_diversity`,
  `CEFR_CAPACITY`, el scoring ni FSRS. **Histórico, hecho**; ver
  `release-notes-v3.56.0.md`.
- `agentes/v355-task-difficulty-3.md` — **V3.55 (EJECUTADO, 2026-09-13,
  v3.55.0)**: **Task Difficulty 3.0**. Release ADITIVA (tres columnas de BD,
  `learning_evidence.declared_difficulty`/`served_difficulty`/
  `observed_task_difficulty`) que da nombres honestos a la dificultad de la
  tarea, hace que la capacidad observada acredite lo SUPERADO y no lo SERVIDO
  (descuento por andamiaje) y cablea la dificultad en las cuatro vías del drill
  léxico. Cierra los P2-01 y P2-02 de la auditoría de V3.53.1. NO toca
  `level_from_capacity`, `observed_skill_capacity`, `learner_capacity`,
  `CEFR_CAPACITY`, la escalera, el scoring, el planner ni FSRS. **Histórico,
  hecho**; ver `release-notes-v3.55.0.md`.
- `agentes/v354-student-skill-state-3.md` — **V3.54 (EJECUTADO, 2026-09-13,
  v3.54.0)**: **Student Skill State 3.0**. Release ADITIVA (una columna de BD,
  `learning_profile.observed_skill_capacity`) que conserva la MODALIDAD en la
  capacidad observada (`skill × dimensión`): `observed_skill_capacity` (fuente de
  verdad) + `observed_capacity` (proyección legacy), `level_from_skill_capacity`
  (cobertura dimensional COMPLETA por skill, regla de V3.53.1 intacta para el
  resumen global), `skill_coverage`/`skill_capacity`, `floor_level_for_skill`
  (demostrado > observado del SKILL > estimado > declarado, sin herencia entre
  modalidades) y gate de cobertura en `difficulty.challenge_for`/
  `select_by_difficulty` y `transfer.context_for` (una capacidad PARCIAL no eleva
  tareas multidimensionales). Contratos aditivos
  `LearningProfile.observed_skill_capacity`/`observed_skill_level`/`skill_coverage`
  y `TransferContextOut.capacity_skill`, con espejo TS. NO toca
  `level_from_capacity`, `CEFR_CAPACITY`, la escalera, el scoring, el planner ni
  FSRS. **Histórico, hecho**; ver `release-notes-v3.54.0.md`.
- `agentes/v3531-observed-cefr-gate.md` — **no existe**: V3.53.1 (**ejecutado
  directamente por el gerente**, 2026-09-13) se resolvió sin briefing separado,
  como V3.52.2/V3.38.1. Cierra el **P1-01** de la auditoría de V3.53.0: `level_from_capacity`
  exige cobertura dimensional COMPLETA (una sola dimensión ya no produce un CEFR
  global), sin migración de BD ni cambios de contrato. **Histórico, hecho**; ver
  `release-notes-v3.53.1.md`.
- `agentes/v353-learner-skill-state.md` — **V3.53 (EJECUTADO, 2026-09-11,
  v3.53.0)**: cierra el candidato **P1-02** (Learner Skill State 2.0 +
  `observed_difficulty` persistido por evento). Parte A: persiste el
  `difficulty_vector` del contexto SERVIDO en el evento de transferencia
  (columna aditiva `learning_evidence.observed_difficulty`, vector canónico con
  `format_vector`/`parse_vector` puros). Parte B: capacidad observada por
  modalidad y dimensión (`observed_signals` con muestra/días espaciados) →
  `services/learner_skill.py` (nivel equivalente + capacidad del alumno) →
  fuente `observed` en `LEVEL_SOURCES` (entre `demonstrated` y `estimated`) y
  caché O(1) en `learning_profile`, con **no-regresión exhaustiva** cuando no hay
  datos. NO toca `CEFR_CAPACITY`, la escalera, el scoring ni FSRS; el planner no
  la consume (eso es P1-03). **Histórico, hecho**; ver
  `release-notes-v3.53.0.md`.
- `agentes/v3522-cierre-p2-auditoria-q.md` — **no existe**: V3.52.2 (**ejecutado
  directamente por el gerente**, 2026-09-11) se resolvió sin briefing separado,
  como V3.38.1 y las FASES 1–5. Cierra los **dos P2** de la auditoría Q
  (`CEFR_CAPACITY` = envelope monótono del banco + invariante de encaje por
  nivel; tolerancia documentada como red de seguridad con test de inercia y de
  discriminación sintética) y crea la etiqueta `v3.52.1`. **Histórico, hecho**;
  ver `release-notes-v3.52.2.md` y `docs/audit/Q-AUDITORIA-TOTAL-V352.md`.
- `agentes/v3521-hotfix.md` — **V3.52.1 (ejecutado, 2026-09-11, v3.52.1)**: hotfix
  de producto (usuarios fantasma «Visual Tester» con guarda `users.is_test`,
  «RUTA ACTUAL» de Listening y bucle A/B) + cierre del P1-01 de la auditoría
  externa de V3.52 (cobertura dimensional en `difficulty.fit`). **Histórico,
  hecho**; ver `release-notes-v3.52.1.md`.
- `agentes/auditoria-externa-v352.md` — **auditoría EXTERNA de V3.52.1
  (EJECUTADA, 2026-09-11)**: prompt autocontenido para un auditor que solo ve
  GitHub (árbol `bdaaff9`, base tag `v3.52.0`/commit `23cbad7`, runs de CI 6/6),
  con punto de entrada, contexto de los dos P1 de V3.51 + el delta del hotfix
  V3.52.1, alcance dentro/fuera, método reproducible, 17 preguntas concretas
  (política del suelo, calibración de `CEFR_CAPACITY` **contra el banco real**,
  semántica de `challenge_vector`/`fit`, tolerancias, determinismo, O(1) del
  camino caliente, paridad GET↔POST, contrato aditivo, cobertura de tests y el
  delta del hotfix) y formato de informe. **Informe entregado**:
  `docs/audit/Q-AUDITORIA-TOTAL-V352.md` → **sin P0/P1**; 2 P2 (calibración de
  `CEFR_CAPACITY` frente al banco y tolerancia por fuente hoy inerte con la
  justificación invertida) y 3 P3, recomendados para V3.53.
- `agentes/auditoria-externa-v350.md` — auditoría EXTERNA de V3.50.0
  **ya entregada y resuelta** (sus tres P1 se cerraron en V3.51.0; V3.50 la dejó
  como briefing «listo para lanzar»). Se conserva como histórico del método.
- `agentes/v352-student-state-difficulty.md` — **V3.52 (ejecutado, 2026-09-11,
  v3.52.0)**: Student level state (separación `practice`/`estimated`/`demonstrated`
  con el demostrado como suelo, migración aditiva de `learning_profile` y lectura
  O(1) en el drill) + Difficulty Engine 2.0 por dimensión (`CEFR_CAPACITY`,
  `challenge_vector`, `fit`, `select_by_difficulty` con degradación por mínima
  distancia). Cierra los dos P1 de la auditoría externa de V3.51. **Histórico,
  hecho**; ver `release-notes-v3.52.0.md`.
- `agentes/v351-task-skill-semantics.md` — **V3.51 (ejecutado, 2026-09-11,
  v3.51.0)**: Task/Skill semantics (separación `target_skill`/`assessed_skill`/
  `assessment_mode`/`evidence_skill` con el transfer midiendo producción ESCRITA,
  columna aditiva `learning_evidence.assessed_skill`) + vector completo
  `planner.skill_priorities` + dificultad anclada al nivel DEMOSTRADO del alumno
  (suelo) sin perder el CEFR del ítem (techo). Cierra los tres P1 de la auditoría
  externa de V3.50. **Histórico, hecho**; ver `release-notes-v3.51.0.md`.
- `agentes/v350-context-skill-mapping.md` — **V3.50 (ejecutado, 2026-09-11,
  v3.50.0)**: Context→Skill mapping (cada contexto declara qué competencias
  ejercita y `context_for` prioriza la modalidad limitante) + difficulty matching
  por banda derivada del CEFR del ítem, sin migración, sin tocar la escalera
  `transfer_state` ni el gate. Cierra el candidato diferido por V3.49.0.
  **Histórico, hecho**; ver `release-notes-v3.50.0.md`.
- `agentes/v348-context-bank.md` — **V3.48 (ejecutado, 2026-09-11, v3.48.0)**:
  Context Bank 2.0 (banco de 6 → 20 contextos con cobertura A1–C2, 6 originales
  congelados) + diversidad 2.0 informativa (`register`/`lexical_environment`/
  `syntactic_focus` en `context_diversity.variety`, sin entrar en el gate de
  evidencia). Cierra los P2-04/P2-05 de la auditoría de V3.43.0. **Histórico,
  hecho**; ver `release-notes-v3.48.0.md`.
- `agentes/v347-transfer-evidence-cefr.md` — **V3.47 (ejecutado, 2026-09-11,
  v3.47.0)**: Transfer Evidence 2.0 (escalera endurecida: ≥2 éxitos no andamiados
  para `transfer_demonstrated`, 3 días + 2 objetivos para `transfer_stable`) +
  CEFR/`difficulty_vector` del contexto (banco etiquetado y `context_for(level)`).
  Cierra los dos P1 de la auditoría de V3.46.0. **Histórico, hecho**; ver
  `release-notes-v3.47.0.md`.
- `agentes/v346-transfer-condition.md` — **V3.46 (ejecutado, 2026-09-11,
  v3.46.0)**: condición de recuperación en la transferencia
  (`prompted`/`cued_context`/`open_context`/`free_choice`/`naturally_emergent`),
  escalera pura por evidencia, persistencia aditiva y endurecimiento de
  `transfer_demonstrated` (exige ≥1 éxito limpio NO andamiado). Cierra el P1
  `transfer_condition` de la auditoría de V3.43.0. **Histórico, hecho**; ver
  `release-notes-v3.46.0.md`.
- `agentes/v345-translator.md` — **V3.45 (ejecutado, 2026-09-11, v3.45.0)**:
  Traductor de viaje práctico (modo Conversación con dos botones grandes, VAD,
  auto-traducción y auto-reproducción, «cara a cara») + voz española real
  (`es_ES-davefx-medium`, default por idioma y auto-descarga en `/api/tts`).
  **Histórico, hecho**; ver `release-notes-v3.45.0.md`.
- `agentes/v344-sense-aware.md` — **V3.44 (ejecutado, 2026-09-11, v3.44.0)**:
  Lexicón sense-aware (`lexical_unit → sense`) + scoring semántico 2.0
  (`fit`/`suspect`/`incorrect`/`unknown`, solo `incorrect` bloquea el clean
  success). Cierra los dos P1 conceptuales de la auditoría de V3.43.0.
  **Histórico, hecho**; ver `release-notes-v3.44.0.md`.
- `agentes/v343-transfer-2.md` — **V3.43 (ejecutado, 2026-09-11, v3.43.0)**:
  Transfer 2.0 (target oculto, semanticidad determinista, diversidad contextual
  real y `transfer_state`). Cierra los 4 P1 de la auditoría de V3.42.0.
  **Histórico, hecho**; ver `release-notes-v3.43.0.md`.
- `agentes/v338-situacion-planner.md` — **V3.38 (ejecutado, 2026-09-10,
  v3.38.0)**: `situación` como techo de la escalera + planner (Optimal Next Task)
  + automaticidad por skill. **Histórico, hecho**; ver
  `release-notes-v3.38.0.md`. Su cierre quirúrgico (**V3.38.1**, ejecutado por el
  gerente sin briefing separado) cierra los 4 P1 de su auditoría y añade la UI de
  diccionario/estado; ver `release-notes-v3.38.1.md`.
- `agentes/v3371-politica-recall.md` — **V3.37.1 (ejecutado, 2026-09-10,
  v3.37.1)**: política de consolidación (≥2 éxitos en ≥2 días) y regresión
  (≥2 fallos sin éxito) de la escalera de recall. **Histórico, hecho**; ver
  `release-notes-v3.37.1.md`.
- `agentes/v337-cues-graduados.md` — **V3.37 (ejecutado, 2026-09-10, v3.37.0)**:
  cues graduados + automaticidad. **Histórico, hecho**; ver
  `release-notes-v3.37.0.md`. El siguiente briefing vivo (V3.39: decisión por
  skill + routing de escritura de `written_production`) está por escribir.
- `agentes/v330-*.md`, `v332-*`, `v333-*`, `v3331-*`, `v334-*` — puente
  Dictionary → Learning (V3.30–V3.34): **históricos, hechos**.
- `agentes/m*-*.md` — milestones M0–M10 y `v17`/`v18`: **históricos, todos hechos**.
- `agentes/endurecimiento/` — Release Audit 1.1 (RA1–RA7), launcher (A1/A2) y
  endurecimiento (E1–E4, F4–F9): **históricos, todos hechos**.
- `agentes/pedagogia/` — Etapa pedagógica (P1–P23): **históricos, todos hechos**.
- `agentes/ui2/` — Rediseño UI 2.0 (u1–u3): **históricos, todos hechos**.
- `agentes/curriculum/` — V2.5 Curriculum Completion (c1–c4): **hechos** (37.22–37.25). Ver
  `docs/RELEVO.md` sección 37.21 y `docs/CURRICULUM_COVERAGE.md` (huecos que cierran).

Las **FASE 1–5 de la auditoría externa (V1.30–V1.34)** — LAN/móvil, Adaptive 2.0,
Curriculum 2.0, Listening 2.0 y Speaking 2.0 — fueron ejecutadas **directamente por el
gerente** (sin briefings separados). Para esos incrementos, la fuente de verdad es
`CHANGELOG.md` + `docs/RELEVO.md` (sección 37), no un archivo `agentes/*.md`.

### ¿Qué queda?

Ver `docs/RELEVO.md` sección 37: **37.3** (contenido WAV real, pendiente del usuario),
**37.4** (Vercel, diferido) y el **commit `feat:` de cierre de V1.30–V1.34**. Si la
auditoría define **FASE 6 (Beta)**, se crea un nuevo briefing en esta carpeta antes de ejecutarla.

## Plantilla estándar de un subagente

Cada archivo contendrá las siguientes secciones:

- **Rol:** qué papel juega (backend, frontend, voz, testing…).
- **Objetivo:** qué debe conseguir exactamente.
- **Contexto:** stack, rutas de archivos, dependencias, cómo arrancar.
- **Tarea detallada:** pasos concretos.
- **Criterios de aceptación:** cómo saber que está bien hecho.
- **Restricciones:** qué NO debe hacer (no salir del scope, no tocar otros archivos, mantener tipado fuerte, 100% local…).
- **Salida esperada:** qué debe devolver (diff, archivos, explicación).

## Reglas anti-saturación / anti-alucinación

- Un subagente = una tarea acotada y autocontenida; **no** encadenar trabajo histórico.
- Si el contexto del agente se satura, **reiniciar** desde `docs/RELEVO.md` (sección 0) en lugar
  de seguir acumulando.
- Verificar rutas de archivos y nombres de funciones contra el código real (`docs/ARQUITECTURA.md`
  y `docs/PREMISAS.md`) antes de asumir que siguen existiendo.
