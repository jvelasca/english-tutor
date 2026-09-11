# Briefing de auditoría EXTERNA — V3.52.1 (Student Skill State + Difficulty Engine 2.0 + hotfix de producto)

> **ESTADO: EJECUTADA** (2026-09-11). Informe entregado en
> [`docs/audit/Q-AUDITORIA-TOTAL-V352.md`](../docs/audit/Q-AUDITORIA-TOTAL-V352.md).
> Se conserva este briefing como histórico del método.
>
> **Para quién:** un agente/auditor EXTERNO que solo tiene acceso al repositorio
> público de GitHub (no al chat del gerente ni al historial de la sesión).
> **Qué entregar:** un informe siguiendo `docs/audit/TEMPLATE.md`, propuesto como
> `docs/audit/Q-AUDITORIA-TOTAL-V352.md` (la letra `Q` quedó reservada para el
> dossier de V3.50, nunca entregado como archivo; si ese se materializa, usa `R`).

## Punto de entrada (todo desde GitHub)

- **Repositorio:** https://github.com/jvelasca/english-tutor (público).
- **Estado auditado:** `main` → commit
  `bdaaff9` («docs(v3.52.1): registrar el run 6/6 de CI del hotfix»), que
  contiene la release **v3.52.1** (`89eff0b`, «release(v3.52.1): hotfix de
  producto + cierre del P1-01 de la auditoria»). El objeto de la auditoría es ese
  árbol: V3.52.0 + el hotfix V3.52.1. **Nota: `v3.52.1` NO tiene tag** (el
  último es `v3.52.0`); ver el hallazgo P3-05 del informe.
- **Release de referencia (base):** tag **`v3.52.0`** → commit
  `23cbad738524465201d4025843478f4220252846` («release(v3.52.0): Student Skill
  State + Difficulty Engine 2.0»). Tag anotado: objeto `7f1d3ee`.
- **CI del hotfix:** run
  [34622637688](https://github.com/jvelasca/english-tutor/actions/runs/34622637688)
  sobre `89eff0b` y run
  [34623244239](https://github.com/jvelasca/english-tutor/actions/runs/34623244239)
  sobre `bdaaff9`, **ambos 6/6 en success** (Release consistency, Backend
  ruff+pytest, Frontend tsc+vitest+build, Playwright E2E (visual), Beta V3.0
  gate, Content validation). CI del release base (V3.52.0): run
  [34604654412](https://github.com/jvelasca/english-tutor/actions/runs/34604654412)
  sobre `23cbad7`, también 6/6.
- **Documentos de resultado (afirmaciones a verificar):**
  `release-notes-v3.52.1.md` (el hotfix) y `release-notes-v3.52.0.md` (la base).
  Briefings previos: `agentes/v3521-hotfix.md` y
  `agentes/v352-student-state-difficulty.md`.
- **Releases previas de referencia:** `v3.51.0` → `c056546`,
  `v3.50.0` → `1c8d6e0`.

## Contexto: qué es V3.52 y qué reemplaza

V3.52 cierra los **dos P1** de la auditoría externa de V3.51. Es una release
**aditiva** (dos columnas de BD + claves nuevas en el contrato HTTP), determinista
y sin LLM en la decisión, y **no toca** la escalera `transfer_state`, sus
umbrales, `context_signals`, `context_diversity`, el scoring
(`score_transfer_attempt`), FSRS ni el Evidence Ledger.

**P1-01 — `learner_level` no era el nivel DEMOSTRADO.** El auditor de V3.51
confirmó en código que `domain.vocabulary._learner_level` leía
`learning_profile.cefr_level`, y que esa columna la escribe
`domain.profile.get_profile_summary` con `estimated_level` (una banda de PRÁCTICA
continua: suelo por niveles completados + progreso ponderado), **no** con
`demonstrated_level` (que exige matrícula completada **y** `certification_gate`
certificado). El `demonstrated_level` ya existía en
`domain.academy._demonstrated_level` / `build_student_model` y en `StudentModelOut`,
pero el drill nunca lo usaba y el docstring de `_learner_level` lo llamaba
«demostrado». Consecuencia: se podía **sobreestimar** el nivel del alumno y
elevar el suelo de dificultad sin evidencia que lo respaldara.

V3.52 introduce el módulo puro `backend/services/student_state.py` que separa tres
nociones y deriva el SUELO con una política conservadora
(`demostrado > estimado > declarado > ninguno`; en detalle, ver
`LEVEL_SOURCES` y `floor_level`, líneas 38 y 64) y persiste `estimated_level` y
`demonstrated_level` en `learning_profile` sin tocar `cefr_level`.

**P1-02 — el difficulty floor mezclaba escalas.** `_difficulty_floor` comparaba el
ordinal CEFR (0..5) contra `difficulty_from_vector` (media 1..6 del vector) y
**colapsaba** las cuatro dimensiones antes de comparar: un contexto `(5,1,5,1)` y
otro `(3,3,3,3)` tenían la misma media y resultaban indistinguibles, de modo que
el suelo no podía razonar sobre **qué** dimensión exigía el contexto.

V3.52 introduce `backend/services/difficulty.py`, que compara **vector contra
vector** por dimensión (`CEFR_CAPACITY`, `challenge_vector`, `fit`,
`select_by_difficulty`, `tolerance_for`) y sustituye el escalar en `transfer.py`.

## Delta de V3.52.1 (lo que añade el hotfix y también se juzga)

Sobre esa base, V3.52.1 (`89eff0b`, diff completo contra el tag `v3.52.0`)
introduce cuatro bloques, **todos aditivos**:

1. **Cierre real del P1-01 de V3.52** (`services/difficulty.py`): `fit` añade
   `dimensions_expected`/`dimensions_compared`/`coverage` y `within` exige
   **cobertura dimensional completa** (`compared == expected`) además de no
   pasarse de la tolerancia; solo un reto VACÍO deja el encaje vacuo.
   `select_by_difficulty`, cuando nadie encaja, degrada por **mayor cobertura** y
   luego por menor distancia (antes solo por distancia). `services/transfer.py`
   expone las claves nuevas en `difficulty_fit` (añadido puro: verificado por
   diff, 19 líneas).
2. **Usuarios fantasma «Visual Tester»** (raíz + guarda + purga): columna aditiva
   `users.is_test` (`CREATE TABLE` + `ALTER TABLE` idempotente), filtro por
   defecto en `GET /api/users` (`include_test=true` lo usan los tests),
   `DELETE /api/users/{id}` acotado a `is_test=1`, filtro en
   `launcher/status.py::read_users` con degradación tolerante, `globalSetup`/
   `globalTeardown` de Playwright (un único perfil de prueba, sin carrera) y
   `scripts/purge_virtual_testers.py --is-test`.
3. **Listening «RUTA ACTUAL»** (`ListeningPractice.tsx`): el anillo pasa de
   `stats.level` a `resolveRouteLevel(sesión > ruta seleccionada > recomendada)` y
   el efecto de carga depende de `[userId, selectedLevel]`.
4. **Bucle A/B de Listening**: módulo puro `features/listening/abLoop.ts` como
   única fuente de verdad UI↔controller, `AudioController.play(url)` idempotente
   por URL, `loop`/`rewindIfPastSegmentEnd` con `>=` y notificación
   `onCurrentTime`, marca tomada de `audioController.currentTime`, hint con el B
   marcado y controles centrados.

**Cifras declaradas de este hotfix (a verificar):** pytest **2162 passed + 2
skipped en CI** (2164 passed en local con el modelo Whisper), vitest **76
ficheros/651 tests**, lanzador 76, `check_release_consistency` **3.52.1**.
Playwright en local: 23 passed / 22 skipped (el resto son `test.skip` por
proyecto/viewport).

## Alcance de la auditoría (qué juzgar)

**Dentro:**

- `backend/services/student_state.py` (nuevo, 122 líneas): `LEVEL_SOURCES`,
  `CERTIFIED_SOURCES`, `_normalize_level`, `floor_level`, `level_state`,
  `is_certified`, `empty_state`.
- `backend/services/difficulty.py` (nuevo, 246 líneas): `DIFFICULTY_DIMENSIONS`,
  `CEFR_CAPACITY`, `DIFFICULTY_TOLERANCE`/`DIFFICULTY_TOLERANCE_ESTIMATED`,
  `normalize_vector`, `normalize_level`, `capacity_for`, `challenge_vector`,
  `fit`, `select_by_difficulty`, `tolerance_for`.
- `backend/repositories/db.py` (líneas 267–293): columnas aditivas
  `estimated_level`/`demonstrated_level` en `learning_profile` (`CREATE TABLE` +
  bucle idempotente `ALTER TABLE ... ADD COLUMN`).
- `backend/repositories/profile.py`: `get_profile` (11), `set_level_state` (26),
  `set_cefr` (65, ahora wrapper).
- `backend/domain/profile.py`: `_compute_profile` (131, expone
  `demonstrated_level` en 172), `get_profile_summary` (224, escribe ambos niveles
  en 235–238).
- `backend/domain/vocabulary.py`: `_learner_level_state` (853), `_learner_level`
  (880), y los dos puntos que pasan `learner_level_source` (940 y 1012).
- `backend/services/transfer.py`: `TRANSFER_DIFFICULTY_KEYS` (128, alias),
  `TRANSFER_DIFFICULTY_BAND` (149, deprecada), `_within_level` (186),
  `_filter_skill` (215), `_challenge_and_tolerance` (230), `_difficulty_fit_for`
  (244), `_normalize_source` (278), `context_for` (1220).
- `backend/schemas/vocabulary.py` (`TransferContextOut.learner_level_source` /
  `difficulty_fit`), `backend/schemas/profile.py`
  (`LearningProfile.demonstrated_level`) y `frontend/src/types/api.ts`
  (`DrillTransferContext.learner_level_source?` / `difficulty_fit?`,
  `DrillDifficultyFit`).
- Tests: `backend/tests/test_student_state_v352.py` (15),
  `backend/tests/test_difficulty_engine_v352.py` (24) y el ajuste de
  `backend/tests/test_task_semantics_v351.py::test_learner_level_raises_the_difficulty_floor`
  (pasa de comparar escalares a comparar `difficulty_fit`).
- **Delta V3.52.1:** `backend/services/difficulty.py` (`_empty_fit`, `fit`,
  `select_by_difficulty`), `backend/services/transfer.py::_difficulty_fit_for`,
  `backend/repositories/{db,users}.py`, `backend/domain/users.py`,
  `backend/routers/users.py`, `backend/schemas/users.py`,
  `backend/tests/{test_difficulty_engine_v352,test_users,test_user_profile}.py`,
  `launcher/status.py` + `launcher/tests/test_status.py`,
  `scripts/purge_virtual_testers.py`,
  `frontend/src/features/listening/{ListeningPractice.tsx,audioController.ts,abLoop.ts,abLoop.test.ts,audioController.test.ts}`,
  `frontend/src/types/api.ts`, `frontend/tests/visual/{gateHelper,globalSetup,globalTeardown}.ts`
  y `frontend/playwright.config.ts`.

**Fuera (documentado y diferido; si un hallazgo cae aquí, márcalo como
«fuera de alcance/diferido», no como P0):** `assessed_skill` → decisión del
planner y `skill_priorities` → `planner.select_task` (V3.55: cablearlo sin más
haría que el transfer contase como `written_production` junto al drill `write`,
doble conteo), Sense Engine 2.0 (`surface→lemma→sense→semantic_fit`),
`observed_difficulty` persistido por evento, entrega oral real del transfer
(audio+STT), `expected_learning_value` / Adaptive Planner 2.0, Context Bank
Family/Instance, offline TTS y code splitting del frontend. Tampoco se juzga la
CONSTITUCIÓN (R8/R9 sigue como propuesta abierta).

## Método reproducible (clona en el tag)

```powershell
git clone https://github.com/jvelasca/english-tutor.git
cd english-tutor
git checkout bdaaff9          # v3.52.1 (el tag v3.52.1 NO existe: ver P3-05)
git diff v3.52.0..bdaaff9     # delta del hotfix

# Backend
cd backend
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest tests/ -q

# Frontend
cd ../frontend
npm ci
npx tsc --noEmit
npm test
npm run build

# Gates del repo
cd ..
python scripts/check_release_consistency.py   # debe imprimir 3.52.1
python scripts/check_beta_v3.py
python backend/scripts/content_validation.py

# Verificación del hotfix (local, con backend+frontend arriba)
cd frontend
npx playwright test                            # visual (crea y borra el perfil de prueba)
```

Cifras declaradas que debes poder reproducir en `bdaaff9` (V3.52.1): pytest
**2164 passed en local** (+6 del hotfix) / **2162 passed + 2 skipped en CI**,
vitest **76 ficheros/651 tests**, `ruff`/`tsc`/`build` limpios,
`check_release_consistency` **3.52.1** exit 0. Para la base V3.52.0: pytest
**2158 passed** (2156 + 2 skipped en CI), vitest **75/641**,
`check_release_consistency` **3.52.0**.

> **Nota sobre el recuento de pytest (para que no lo cuentes como hallazgo
> nuevo):** en local (Windows, con el modelo Whisper descargado) son **2158
> passed** (V3.52.0) / **2164** (V3.52.1); en el runner de CI son **2156** /
> **2162** **+ 2 skipped**, porque `backend/tests/test_stt_asr_integration.py`
> está marcado con `pytest.mark.skipif(not is_ready(), ...)` (integración ASR
> opt-in) y el runner no tiene el modelo. Es una discrepancia de entorno ya
> documentada en `release-notes-v3.52.{0,1}.md`, `CHANGELOG.md`, `PLAN.md` y
> `docs/RELEVO.md`.

## Preguntas concretas que debe responder el informe

1. **Cierre real de P1-01.** ¿El suelo que consume el drill proviene de verdad del
   nivel DEMOSTRADO y no del estimado? Recorre `learning_profile` (escritura en
   `domain/profile.py`), `student_state.floor_level` y
   `domain/vocabulary._learner_level_state`. ¿Queda algún camino (GET, POST,
   cola de repaso, otro router) que siga usando `cefr_level` como si fuera
   demostrado? ¿El docstring ya no miente?
2. **Política de prioridad del suelo.** `floor_level` prefiere el DEMOSTRADO
   **aunque su banda sea inferior** al estimado. ¿Es pedagógicamente defendible
   (una certificación acredita retención; el estimado solo la intuye) o produce
   infravaloración del alumno? ¿Y es la dirección segura del error? Busca un
   caso donde la política elegida sirva un contexto claramente demasiado fácil.
3. **Migración aditiva y filas legacy.** ¿La migración es idempotente y no
   destructiva? ¿`cefr_level` se conserva? Las filas legacy quedan con las
   columnas nuevas en `''` y alimentan el suelo como nivel **declarado**
   (`practice`): ¿se pierde señal o se gana un suelo fantasma? ¿`set_cefr` es de
   verdad un wrapper que **no** pisa un `demonstrated_level` certificado (y qué
   pasa si llega un `demonstrated_level` no CEFR)?
4. **Robustez de `student_state`.** ¿Nunca lanza con `None`, `""`, `"a1"`,
   `"C1 "`, `"Z9"` o valores no-string? ¿`level_state` normaliza los tres niveles
   y devuelve un estado vacío válido? ¿`empty_state()` devuelve un dict nuevo en
   cada llamada (sin mutación compartida)?
5. **`CEFR_CAPACITY` como tabla declarada.** ¿Es monótona no decreciente por
   dimensión? ¿La `interaction` retrasada en A1–B1 está **respaldada por la
   distribución real del banco** de transferencia, o es una afirmación sin
   evidencia? Contrasta la tabla con los `difficulty_vector` reales de los
   contextos del banco y di si la calibración es defendible. Es el punto más
   «a ojo» de la release: ¿se puede derivar del banco y cuánto se desvía?
6. **`challenge_vector` = máximo por dimensión.** ¿Es correcto que el reto
   objetivo generalice `max(item_index, learner_index)` sin mezclar escalas? Un
   ítem A1 con alumno C2 produce un reto C2 **mientras `_within_level` limita el
   pool a A1**: ¿qué hace entonces el motor, reordenar dentro de A1? ¿El
   `difficulty_fit` resultante es útil o ruido inerte? ¿La release garantiza de
   verdad que «una unidad A1 con alumno C2 no recibe contextos por encima de A1»
   (test concreto)?
7. **Política de `fit` y `select_by_difficulty`.** `distance` es la suma de
   distancias absolutas (**incluye el defecto**, es decir, quedarse corto) y
   `max_overshoot` solo cuenta el exceso. ¿Es correcta la política lexicográfica
   `within` primero y `distance` mínimo después? ¿Puede llegar a servir un
   contexto que **exceda** la capacidad del alumno (hasta `tolerance`)? ¿Deja el
   pool vacío alguna vez? ¿Sirve «el más difícil por defecto» en algún caso?
8. **Tolerancias.** `DIFFICULTY_TOLERANCE = 1` (suelo demostrado) vs
   `DIFFICULTY_TOLERANCE_ESTIMATED = 2` (estimado/declarado/ausente). ¿Están
   justificadas y en la dirección conservadora? ¿Un `learner_level_source`
   desconocido o con mayúsculas cae al margen amplio?
9. **Cero regresión de la escalera.** Verifica por `git diff 788ecc0..bdaaff9`
   (V3.51 → V3.52.1) y, en particular, por `git diff v3.52.0..bdaaff9` (el
   hotfix) y por grep que **nada** de `transfer_state`, sus umbrales,
   `context_signals`, `context_diversity`, `score_transfer_attempt` ni FSRS
   cambia. `TRANSFER_DIFFICULTY_BAND` queda declarada como deprecada: comprueba
   que **ningún** camino de selección la consume (`_difficulty_floor` y
   `_within_band` deben haber desaparecido). ¿Queda código muerto?
10. **Determinismo.** ¿La elección es función determinista de (palabra, evidencia,
    `level`, `skill`, `learner_level`, `learner_level_source`), sin reloj, sin
    `hash()` aleatorizado y sin aleatoriedad? ¿`select_by_difficulty` preserva el
    orden de entrada en los empates y `_stable_index` sigue resolviendo la
    rotación?
11. **Camino caliente O(1).** ¿`_learner_level_state` lee una fila única y **no**
    recalcula el Student Model en el drill? ¿Hay algún camino nuevo que invoque
    `academy.build_student_model` o `_demonstrated_level` dentro del drill (lo
    que rompería la garantía de coste)? ¿La caché sigue escribiéndose solo desde
    `get_profile_summary`?
12. **Paridad GET↔POST.** ¿`get_transfer_context` y el fallback de
    `submit_transfer_attempt` derivan el MISMO `context_id` y el MISMO
    `learner_level_source` con la misma evidencia? ¿Hay alguna entrada real por
    la que diverjan?
13. **Contrato HTTP aditivo.** ¿`difficulty_fit` y `learner_level_source` viajan
    en **todos** los retornos de `context_for`, incluidos los tempranos (banco
    vacío, pool agotado/`exhausted`, nivel no reconocido)? ¿`difficulty` y
    `difficulty_vector` se conservan intactos por compatibilidad y siguen siendo
    coherentes con el contexto servido? ¿El espejo del frontend es opcional y no
    rompe tipos existentes?
14. **Cobertura de tests.** ¿Los criterios de aceptación del briefing
    (`agentes/v352-student-state-difficulty.md`) están cubiertos por test?
    ¿Faltan bordes: valores no CEFR/`None`, niveles fuera de `CEFR_CAPACITY`,
    contextos sin `difficulty_vector`, `difficulty_vector` con claves
    desconocidas o cargas fuera de 1..5, empates exactos de distancia, banco
    vacío, migración sobre una BD legacy **real** (no solo un `CREATE TABLE`
    limpio) y paridad pura↔SQL?
15. **¿La `CEFR_CAPACITY` declarada cuadra con el banco que dice calibrar?**
    El docstring de `services/difficulty.py` afirma que la tabla está «calibrada
    con la distribución real del banco de transferencia (en A1–B1 la
    `interaction` va por detrás del resto)». Calcula la media **y el máximo** por
    dimensión de los 20 contextos de `TRANSFER_CONTEXTS` agrupados por `cefr` y
    contrástalos con la tabla. ¿Qué contextos del banco quedan `within=False`
    contra el reto de **su propio nivel** con la tolerancia ESTRICTA (demostrado)?
    ¿Es defendible que el alumno con más confianza no pueda recibir contextos que
    el banco etiqueta con su mismo nivel? ¿Se puede derivar la tabla del banco?
    ¿Y los tramos B2/C1: la capacidad declarada de léxico/sintaxis (4 y 5)
    EXCEDE todo el banco de ese nivel (máximo real 3 y 4)?
16. **¿La distinción de tolerancia cambia alguna vez la selección?** Enumera
    todas las combinaciones (nivel de ítem × nivel de alumno) con reto reconocible
    sobre el banco real y comprueba si `select_by_difficulty` devuelve un conjunto
    distinto con `tolerance=1` y con `tolerance=2`. Si no cambia en ningún caso,
    la diferenciación «estricta para demostrado / amplia para estimado» es hoy
    **inerte**: ¿basta con que el número viaje en el payload
    (`test_learner_level_source_selects_the_tolerance_in_the_payload`) o falta un
    test de COMPORTAMIENTO? Además, el docstring afirma que el margen amplio es
    «conservador: ante la duda, más margen en lugar de más exigencia»: razona si
    un margen mayor no admite de hecho **más** exceso (más exigencia).
17. **Delta del hotfix (producto).** ¿El cierre del P1-01 es real y completo (un
    contexto sin `difficulty_vector` ya no puede ganar con `distance=0`, ni antes
    ni ahora)? ¿La migración `users.is_test` es idempotente y no destructiva?
    ¿`DELETE /api/users/{id}` no puede borrar un perfil real y limpia todas las
    filas dependientes (`settings`, `conversations`, `messages`…)? ¿`is_test` es
    inmutable por `PATCH`? ¿El perfil de prueba de Playwright se crea UNA vez
    (`globalSetup`) y se borra al terminar (`globalTeardown`), sin carrera?
    ¿La app y el lanzador lo ocultan? ¿El lanzador degrada si la columna no
    existe? ¿«RUTA ACTUAL» de Listening sigue al nivel seleccionado y recarga la
    pregunta? ¿El bucle A/B mantiene el estado UI↔controller (quitar marca
    desarma el bucle, el hint muestra el B marcado, los controles están
    centrados)? ¿El `is_test` es marcable por el cliente (y qué implica)?

## Formato del informe

Sigue `docs/audit/TEMPLATE.md`. Para cada hallazgo:

- **ID y severidad** (P0 bloqueante / P1 alto / P2 medio / P3 menor).
- **Evidencia** verificable desde el repositorio (archivo:línea del tag, comando
  exacto y salida, o test concreto).
- **Recomendación** y, si aplica, el test que fallaría hoy.
- **Veredicto final** de 2-3 líneas: ¿la release es publicable como estable tal
  cual?

No aceptes como evidencia el contenido de `release-notes-v3.52.0.md` por sí
mismo: úsalo como afirmación a verificar contra el código y los tests del tag.
