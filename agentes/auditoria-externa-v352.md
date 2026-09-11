# Briefing de auditoría EXTERNA — V3.52.0 (Student Skill State + Difficulty Engine 2.0)

> **Para quién:** un agente/auditor EXTERNO que solo tiene acceso al repositorio
> público de GitHub (no al chat del gerente ni al historial de la sesión).
> **Qué entregar:** un informe siguiendo `docs/audit/TEMPLATE.md`, propuesto como
> `docs/audit/Q-AUDITORIA-TOTAL-V352.md` (la letra `Q` quedó reservada para el
> dossier de V3.50, nunca entregado como archivo; si ese se materializa, usa `R`).

## Punto de entrada (todo desde GitHub)

- **Repositorio:** https://github.com/jvelasca/english-tutor (público).
- **Release auditada:** tag **`v3.52.0`** → commit
  `23cbad738524465201d4025843478f4220252846` («release(v3.52.0): Student Skill
  State + Difficulty Engine 2.0»). Tag anotado: objeto `7f1d3ee`.
- **HEAD de `main` (incluye el commit de evidencia de CI):** `6744579`
  («docs(v3.52.0): registrar la evidencia de CI del release (run 34604654412
  sobre 23cbad7, 6/6 jobs en success)»).
- **CI del release:** run
  [34604654412](https://github.com/jvelasca/english-tutor/actions/runs/34604654412)
  sobre `23cbad7`, **6/6 jobs en success** (Release consistency, Backend
  ruff+pytest, Frontend tsc+vitest+build, Playwright E2E (visual), Beta V3.0
  gate, Content validation). El commit de evidencia `6744579` tiene su propio run
  en verde.
- **Documento de resultado (fuente de verdad de lo que se afirma):**
  `release-notes-v3.52.0.md`. Briefing previo (planificación/traspaso):
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
git checkout v3.52.0

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
python scripts/check_release_consistency.py   # debe imprimir 3.52.0
python scripts/check_beta_v3.py
python backend/scripts/content_validation.py
```

Cifras declaradas que debes poder reproducir: pytest **2158 passed** (+39: 15 de
`test_student_state_v352.py` y 24 de `test_difficulty_engine_v352.py`), vitest
**75 ficheros/641 tests**, `ruff`/`tsc`/`build` limpios, `check_release_consistency`
**3.52.0** exit 0.

> **Nota sobre el recuento de pytest (para que no lo cuentes como hallazgo
> nuevo):** en local (Windows, con el modelo Whisper descargado) son **2158
> passed**; en el runner de CI son **2156 passed + 2 skipped**, porque
> `backend/tests/test_stt_asr_integration.py` está marcado con
> `pytest.mark.skipif(not is_ready(), ...)` (integración ASR opt-in) y el runner
> no tiene el modelo. Es una discrepancia de entorno ya documentada en
> `release-notes-v3.52.0.md`, `CHANGELOG.md`, `PLAN.md` y `docs/RELEVO.md`.

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
9. **Cero regresión de la escalera.** Verifica por `git diff 788ecc0..23cbad7` y
   por grep que **nada** de `transfer_state`, sus umbrales,
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
