# Plan de proyecto — English Tutor (100% local)

> Mantenido por el gerente del proyecto (yo). Los subagentes se ejecutan desde
> agentes locales: cada tarea se describe en `agentes/<nombre>.md`.
>
> **Premisas y reglas:** `docs/PREMISAS.md` · **Arquitectura:** `docs/ARQUITECTURA.md` ·
> **Guía de desarrollo:** `docs/DESARROLLO.md`.

## Estado actual

- ✅ **V3.52.0 — Student Skill State + Difficulty Engine 2.0 (2026-09-11)** (**Versión estable `3.52.0`**, app `3.51.0 → 3.52.0`). **Release ADITIVA (dos columnas de BD) que cierra los dos P1 de la auditoría externa de V3.51 SIN tocar `transfer_state`, sus umbrales, `context_signals`, el scoring ni FSRS. Determinista, sin LLM.** **Parte A — Student level state (P1-01):** nuevo módulo puro `services/student_state.py` (`LEVEL_SOURCES`, `level_state`, `floor_level`, `is_certified`, `empty_state`) que separa `practice_level`/`estimated_cefr`/`demonstrated_cefr` y deriva el SUELO con la política `demostrado > estimado > declarado > ninguno`; solo el demostrado (certificación con retención) usa tolerancia estricta. Migración aditiva: `learning_profile.estimated_level`/`demonstrated_level` (CREATE TABLE + `ALTER TABLE` idempotente) conservando `cefr_level`; `repositories.profile.get_profile` devuelve las dos columnas y nueva `set_level_state` (`set_cefr` queda de wrapper que no pisa el demostrado). `domain.profile.get_profile_summary` escribe AMBOS niveles y expone `demonstrated_level` (aditivo en `schemas/profile.py`); `domain.vocabulary._learner_level_state` lee la caché en O(1) y pasa `learner_level` + `learner_level_source` a `context_for` (paridad GET↔POST). **Parte B — Difficulty Engine 2.0 (P1-02):** nuevo módulo puro `services/difficulty.py` (`DIFFICULTY_DIMENSIONS`, `CEFR_CAPACITY` monótona con `interaction` retrasada en A1–B1, `capacity_for`, `challenge_vector` = máximo por dimensión, `fit` con distancia/`max_overshoot`/`within`, `select_by_difficulty` = conserva los `within` y, entre ellos, los de menor distancia, degradando al más cercano si ninguno encaja; tolerancias `DIFFICULTY_TOLERANCE = 1` demostrado / `DIFFICULTY_TOLERANCE_ESTIMATED = 2`). `services/transfer.py` sustituye `_difficulty_floor`/`_within_band` escalares por el motor (el TECHO lingüístico del ítem sigue en `_within_level`; `TRANSFER_DIFFICULTY_BAND` queda deprecada, `TRANSFER_DIFFICULTY_KEYS` pasa a alias) y su retorno gana `difficulty_fit` + `learner_level_source`. **Contratos aditivos:** `TransferContextOut` y `DrillTransferContext` (`learner_level_source`, `difficulty_fit`/`DrillDifficultyFit`). **Deuda confirmada y diferida (V3.55):** `assessed_skill` → decisión del planner y `skill_priorities` → `select_task` (evitar el doble conteo de `written_production` con el drill `write`). Tests: pytest **2158 passed** (+39: `test_student_state_v352.py` 15, `test_difficulty_engine_v352.py` 24; ajuste de `test_learner_level_raises_the_difficulty_floor` a `difficulty_fit`), `ruff` limpio. Fuera de alcance: Sense Engine 2.0, `observed_difficulty` persistido, entrega oral real del transfer, `expected_learning_value`/Adaptive Planner 2.0, Context Bank Family/Instance, offline TTS y code splitting del frontend.

- ✅ **V3.51.0 — Task/Skill semantics + learner-level difficulty matching (2026-09-11)** (**Versión estable `3.51.0`**, app `3.50.0 → 3.51.0`). **Release ADITIVA (una columna de BD) que cierra los tres P1 de la auditoría externa de V3.50 SIN tocar la escalera `transfer_state`, sus umbrales, FSRS ni el scoring.** **Parte A — Semántica explícita de tarea (P1-01):** nuevo módulo puro `services/task_semantics.py` con `TASK_SEMANTICS` (`target_skill`/`assessed_skill`/`assessment_mode`/`evidence_skill` por actividad), `ASSESSMENT_MODES` y helpers que nunca lanzan; el drill **Transfer**, que se entrega por TEXTO, declara `target_skill="spontaneous_use"`, `assessed_skill="written_production"`, `assessment_mode="written"` y conserva `evidence_skill="spontaneous_use"`. **Parte B — Ledger honesto (migración aditiva):** `learning_evidence.assessed_skill` (CREATE TABLE + `ALTER TABLE` idempotente), persistido en `record_evidence`/`record_evidence_bulk`/`list_evidence` y agregado en `summarize_evidence`/`summarize_by_target`/`empty_summary` (`assessed_skill_attempts`/`assessed_skill_successes`, paridad pura↔SQL); las cinco vías del drill registran las dos dimensiones (`skill` no cambia, `assessed_skill` dice qué se evaluó). **Parte C — Vector de prioridades (P1-03):** `planner.skill_priorities(signals)` expone el vector completo en orden canónico y `limiting_skill` pasa a ser su argmax; `_transfer_target_skill` elige solo entre `task_semantics.assessable_skills("transfer")` (nunca `spoken_production`); `context_for` y la cola de repaso exponen `skill_priorities` (aditivo). **Parte D — Dificultad por nivel del alumno (P1-02):** `context_for(..., learner_level="")`; el CEFR del ítem es el TECHO (`_within_level`) y el nivel DEMOSTRADO del alumno (`domain.vocabulary._learner_level`, caché del Student Model en `learning_profile.cefr_level`) el SUELO de reto de `_difficulty_floor`; sin nivel conocido el resultado es idéntico a V3.50. **Contratos aditivos:** `TransferContextOut`/`TransferAttemptOut` (target/assessed/mode/item_level/learner_level/skill_priorities) y `ReviewQueueItem.skill_priorities`, con espejo opcional en `types/api.ts`. Tests: pytest **2119 passed** (+20: `test_task_semantics_v351.py`; ajuste del contrato exacto de `empty_summary` en `test_learning_evidence_v336.py`), vitest **75 ficheros/641 tests**, `ruff`/`tsc` limpios, `npm run build`, `check_beta_v3`, `content_validation` y `check_release_consistency` **3.51.0** exit 0. **CI 6/6 en verde** (run [34599637351](https://github.com/jvelasca/english-tutor/actions/runs/34599637351) sobre `c056546`). **P3-01:** corregida la cifra documental de V3.50 (2099 → 2097 passed, la de CI). Fuera de alcance (V3.52+): Sense Engine 2.0, entrega oral real del transfer, `observed_difficulty` por evento, `expected_learning_value`/Adaptive Planner 2.0, Context Bank Family/Instance y offline TTS.

- ✅ **V3.50.0 — Context→Skill mapping + difficulty matching (2026-09-11)** (**Versión estable `3.50.0`**, app `3.49.0 → 3.50.0`). **Release ADITIVA y SIN migración de BD que NO cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS**: cierra el candidato diferido por V3.49.0 (los datos de dificultad del banco de contextos V3.47/V3.48 y la modalidad limitante del planner dejan de ser inertes al elegir la tarea). **Parte A — Context→Skill mapping:** nuevo vocabulario declarado `CONTEXT_SKILLS` (espejo verificado de `services.evidence.LEXICAL_SKILLS`, declarado en `transfer.py` para no crear el ciclo `evidence → transfer → evidence`), `skills` curado en los 20 contextos del banco (subconjunto no vacío con al menos una modalidad de producción; los 6 originales conservan `id` y valores core congelados y solo ganan `skills`) y helper puro `context_skills` (acepta dict/`id`/`context_id`, normaliza y nunca lanza). **Parte B — Difficulty matching:** `TRANSFER_DIFFICULTY_BAND = 1`, `_difficulty_floor` (objetivo = mayor del techo real alcanzable y la posición del nivel en la escala 1..6; sin él un ítem B1 seguía recibiendo contextos A1) y `_within_band` (degrada con gracia a lo más difícil disponible). `context_for` gana la firma aditiva `skill=""` y un pipeline determinista: usados → `_within_level` → mínimo sobre todo el alcance → preferencia por modalidad limitante → banda → novedad (V3.43) → `_stable_index`; el retorno añade `skills`. Consumo en `domain/vocabulary.py` con `_transfer_target_skill` (`planner.limiting_skill(planned_signals(...))`, `""` sin segmentación por modalidad) en GET y en el fallback del POST, con paridad de `context_id`. Contratos aditivos `TransferContextOut.skills`/`DrillTransferContext.skills?`; sin cambio de UI. Tests: pytest **2097** (+15: `test_context_skill_v350.py`; ajuste en `test_transfer_cefr_v347.py`), vitest **75 ficheros/641 tests** (sin cambios), `ruff`/`tsc` limpios, `npm run build`, `check_beta_v3`, `content_validation` y `check_release_consistency` **3.50.0** exit 0. **CI 6/6 en verde** (run [34594042697](https://github.com/jvelasca/english-tutor/actions/runs/34594042697) sobre `1c8d6e0`). Fuera de alcance (V3.51+): Sense Engine 2.0, semantic appropriateness, `expected_learning_value`/Adaptive Planner 2.0 y la persistencia de la dificultad por evento.

- ✅ **V3.49.0 — Transfer Evidence 3.0: confianza explicable del eje de transferencia (2026-09-11)** (**Versión estable `3.49.0`**, app `3.48.1 → 3.49.0`). **Release ADITIVA y SIN migración de BD que NO cambia la escalera `transfer_state`, sus umbrales, el scoring ni FSRS**: cierra el punto 8 de la auditoría `docs/audit/P-AUDITORIA-TOTAL-V343.md` («los nombres de los estados pueden sugerir más evidencia de la disponible»). Nueva función pura `services.evidence.transfer_confidence` (`{score, level, sample, drivers, recency_days}`): `score` = suma ponderada de seis `drivers` 0..1 declarados (`contexts`/`successes`/`diversity`/`independence`/`variety`/`spacing`, `TRANSFER_CONFIDENCE_WEIGHTS` suman 1.0), `level` ∈ `none`/`low`/`medium`/`high` calibrado para que `transfer_stable` caiga en `high`, y `recency_days` informativo FUERA del `score` (sin reloj). Monótona no decreciente al añadir evidencia no andamiada y conservadora (`none`, nunca inflada) en resúmenes legacy/parciales; se deriva en la MISMA frontera pura↔SQL (`with_transfer_state`), expuesta en `planner.planned_signals` y `lexicon.review_item`, con contrato aditivo `ReviewQueueItem.transfer_confidence` (`schemas/learning.py`, `types/api.ts`) y etiqueta honesta en `ReviewQueueSection` (aclara que es «transferencia contextual demostrada bajo el protocolo interno», no generalizada). Claves i18n `dictionary.review.transfer.level.*`/`scope` con paridad es/en. Tests: pytest **2084** (+9: `test_transfer_confidence_v349.py`), vitest **75 ficheros/641 tests** (+2), `ruff`/`tsc` limpios y `check_release_consistency` **3.49.0** exit 0. **CI 6/6 en verde** (run [34591158824](https://github.com/jvelasca/english-tutor/actions/runs/34591158824) sobre `034da5c`). Fuera de alcance (V3.50+): Context→Skill mapping y difficulty matching por `difficulty_vector`, Sense Engine 2.0, semantic appropriateness y `expected_learning_value`/Adaptive Planner 2.0.

- ✅ **V3.48.1 — APRENDER más limpio + ruta CEFR seleccionada (2026-09-11)** (**Versión estable `3.48.1`**, app `3.48.0 → 3.48.1`). **Patch SOLO-FRONTEND (más un script de mantenimiento), sin cambios de contrato ni migración de BD.** **(A) Listening sin «Antes de escuchar»:** `microFlow` salta los pasos `stage === "pre"` (`firstRenderableIndex`), el flujo arranca en `while1`; la tarjeta y las claves `listening.flow.preTitle`/`preHint`/`begin` se eliminan y el contexto del ítem pasa a caption compacta bajo el botón de audio (el backend sigue sirviendo `pre` por contrato, sin alterar `transcript_policy`). **(B) Notas CEFR plegables:** nuevo `components/InfoDisclosure.tsx` (`button` + `aria-expanded` + `MoreHorizontal`, montado solo al abrir; variantes `inline`/`corner`) que pliega `routeNote`/`routeCertNote`/`routeRingHelp`/`routesMapHint` en Listening y en el mapa de rutas de las cinco destrezas, y la prosa explicativa (`demonstrateNote`/`demonstrateFormal`/`extraHonestNote`) en los seis paneles de nivel, dejando visibles los estados accionables (gate/`demoNotYet`). **(C) Ruta CEFR seleccionada persistente:** `utils/selectedRoute.ts` (validación `A1..C2`, parseo tolerante, `resolveRouteLevel`) y `hooks/useSelectedRoute.ts` (persistencia doble `localStorage` + `selected_route_level` vía `GET/PUT /api/settings`, sin cambios de backend); prioridad **sesión > ruta seleccionada > nivel recomendado**, pulsar un anillo selecciona y abre su panel (anillo resaltado + «Ruta seleccionada»), chip «Auto» para volver al motor y `exitSession` que conserva la selección. **(D) Limpieza:** `scripts/purge_virtual_testers.py` (dry-run por defecto; `--apply` con copia `tutor.db.bak-<ts>` y borrado transaccional enumerando tablas con `user_id`) y eliminación de los 6 perfiles `Visual Tester` (quedan los 2 reales). Tests: vitest **75 ficheros/639 tests** (+3/+16), `check_i18n_coverage` 0 indefinidas/0 duplicadas, `tsc`/`build`/`check_release_consistency` **3.48.1** en verde. **CI 6/6 en verde** (run [34588975928](https://github.com/jvelasca/english-tutor/actions/runs/34588975928) sobre `6a0a757`). Fuera de alcance (V3.49): Sense Engine 2.0, Context→Skill mapping, difficulty matching y Transfer evidence 3.0; no se tocan FSRS, Evidence Ledger ni el gate.

- ✅ **V3.48.0 — Context Bank 2.0 + diversidad 2.0 (2026-09-11)** (**Versión estable `3.48.0`**, app `3.47.0 → 3.48.0`). **Release ADITIVA y SIN migración de BD que cierra los dos P2 abiertos por la auditoría externa de V3.43.0 sobre la transferencia**, sin tocar la escalera `transfer_state`, el scoring ni FSRS. **Parte A — Context Bank 2.0:** `TRANSFER_CONTEXTS` pasa de 6 a 20 contextos (14 nuevos: `introductions`, `routine`, `directions`, `shopping`, `health`, `travel_plan`, `work_problem`, `community`, `debate`, `review`, `mediation`, `academic`, `negotiation`, `keynote`) con cobertura A1:3 / A2:4 / B1:4 / B2:3 / C1:3 / C2:3; cada uno declara los 6 atributos core, `cefr`, `difficulty_vector` y los ejes de variedad, y ningún `prompt` contiene `{word}`. Los **6 contextos originales se congelan** (mismos `id` y valores core; guardia por test) para no reinterpretar la evidencia histórica. **Parte B — Diversidad 2.0 informativa:** nuevos `CONTEXT_VARIETY_DIMENSIONS` (`register`/`lexical_environment`/`syntactic_focus`), función pura `context_variety` (`{dimensions, varied_dimensions, score}`) y `context_dimensions(..., dimensions=...)` generalizada vía `_normalize_dimensions`; `context_diversity` conserva sus cuatro claves históricas y añade `variety`. **El gate NO cambia** (`CONTEXT_DIMENSIONS`, `context_distance`, `_novelty_score`, `diverse_dimensions` y `CONTEXT_DIVERSITY_MIN = 2`; distancia mínima entre pares `>= 2`); `empty_summary()["context_diversity"]` gana el default `variety` por paridad pura↔SQL. Contrato aditivo `ContextDiversity.variety` (`types/api.ts`), **sin cambio de UI**. Tests: pytest **2075** (+12: `test_context_bank_v348.py`; ajustes en `test_transfer_v343.py` y `test_learning_evidence_v336.py`), vitest **72 ficheros/623 tests** (sin cambios), `ruff`/`tsc` limpios y `check_release_consistency` **3.48.0** exit 0. Fuera de alcance (V3.49): TTS/offline (auto-descarga implícita de voces), Sense Engine 2.0, `transfer_state` enriquecido y `expected_learning_value`/Adaptive Planner 2.0.

- ✅ **V3.47.0 — Transfer Evidence 2.0 + CEFR/`difficulty_vector` del contexto (2026-09-11)** (**Versión estable `3.47.0`**, app `3.46.0 → 3.47.0`). **Release doble y ADITIVA, SIN migración de BD, que cierra los dos P1 abiertos por la auditoría de V3.46.0 sobre la transferencia**, sin tocar el scoring (`score_transfer_attempt`) ni FSRS. **Parte A — Transfer Evidence 2.0 (P1-02):** `services/evidence.py` endurece la escalera: `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED = 2` (2 éxitos limpios NO andamiados para `transfer_demonstrated`, antes 1), `TRANSFER_STABLE_MIN_DAYS` `2 → 3` y nuevo `TRANSFER_STABLE_MIN_GOALS = 2` (objetivos comunicativos distintos); `TRANSFER_STABLE_MIN_CONTEXTS = 3` se mantiene. `context_signals` expone la evidencia fina (`unscaffolded_clean_success_contexts`/`_days`, `clean_success_goals` derivados de la dimensión `communicative_goal`, `last_clean_success_at`/`last_unscaffolded_clean_success_at`; la decisión NO usa reloj) y `empty_summary` los defaults neutros. Fallback legacy intacto: sin datos de condición se conserva la regla anterior y la paridad pura↔SQL sigue siendo por construcción (`repositories/evidence.py` reutiliza la MISMA `context_signals`). **Parte B — CEFR/`difficulty_vector` del contexto:** los 6 contextos de `services/transfer.py` declaran `cefr` (`services.cefr.CEFR_LEVELS`) y `difficulty_vector` (`lexical`/`syntax`/`discourse`/`interaction`, 1..5, convención de listening/speaking); nuevos helpers puros `difficulty_from_vector` (media redondeada, clamp 1..6) y `cefr_index`; `context_for(..., level="")` (retrocompatible) prefiere contextos de nivel ≤ al del alumno y, si ninguno es alcanzable, cae al nivel más cercano por arriba; `context_for` devuelve además `cefr`/`difficulty_vector`/`difficulty`, expuestos por `TransferContextOut` y `DrillTransferContext` (`types/api.ts`). `domain/vocabulary.py` pasa `level=row.get("cefr")` en el GET y en el registro. **Sin cambio de UI.** Tests: pytest **2063** (+16: `test_transfer_evidence_v347.py` y `test_transfer_cefr_v347.py`), vitest **72 ficheros/623 tests** (sin cambios), `ruff`/`tsc` limpios y `check_release_consistency` **3.47.0** exit 0. Fuera de alcance (V3.47.1/V3.48): TTS/offline (auto-descarga implícita de voces), Sense Engine 2.0, Context Bank 2.0, `transfer_state` enriquecido y `expected_learning_value`/Adaptive Planner 2.0.

- ✅ **V3.46.0 — Condición de recuperación en la transferencia (`transfer_condition`) (2026-09-11)** (**Versión estable `3.46.0`**, app `3.45.0 → 3.46.0`). **Cierre quirúrgico del P1 `transfer_condition` de la auditoría de V3.43.0**, release ADITIVA y SIN migración destructiva. Hasta ahora TODO intento de transferencia era `spontaneous_use` con `support_level="spontaneous"`, sin distinguir si la unidad se usó porque se pidió (`prompted`), porque el escenario la insinuaba (`cued_context`), por decisión propia en un escenario abierto (`open_context`), por elección libre (`free_choice`) o porque surgió sola (`naturally_emergent`); sin esa dimensión `transfer_demonstrated` podía declararse con tareas andamiadas. `services/transfer.py` define `TRANSFER_CONDITIONS` (orden de andamiaje decreciente), `SERVABLE_CONDITIONS`, `UNSCAFFOLDED_CONDITIONS`, `REQUIRED_TARGET_CONDITIONS`, `CONDITION_INSTRUCTIONS`, `normalize_condition` y la escalera pura `condition_for_state` (`not_ready` con intentos → `prompted`; `not_ready` sin intentos y `emerging` → `cued_context`, comportamiento de V3.43; `contextualized`+ → `open_context`, unidad NO obligatoria). Persistencia aditiva `transfer_condition TEXT NOT NULL DEFAULT ''` en `learning_evidence` (ALTER idempotente) con plumbing en `record_evidence`/lote/`list_evidence`/SELECT de detalle. `services/evidence.py` agrega `transfer_conditions`, `success_conditions` y `unscaffolded_clean_successes`, y **endurece `transfer_demonstrated`**: además de 2 contextos limpios con diversidad real, exige ≥1 éxito limpio NO andamiado (fallback legacy sin datos de condición). `domain/vocabulary.py` deriva la condición del resumen (el cliente NO la declara), la sirve, la persiste, y un intento de `open_context` que NO usa la unidad no se registra (`required_target=false`). Contratos aditivos (`condition`/`required_target`/`unscaffolded`) y UI del drill con la condición visible y aviso neutro `transferNotRequired`. Tests: pytest **2047**, vitest **72 ficheros/623 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.46.0** exit 0. Fuera de alcance (V3.47+): CEFR/`difficulty_vector` del contexto (P1 restante), Context Bank 2.0, diversidad 2.0, semantic appropriateness, transfer_state enriquecido y `expected_learning_value` / Adaptive Planner 2.0.

- ✅ **V3.45.0 — Traductor de viaje práctico + voz española real (2026-09-11)** (**Versión estable `3.45.0`**, app `3.44.0 → 3.45.0`). Cierra la experiencia del Traductor de viaje. **(A) Voz española real:** la salida en español sonaba a «un inglés hablando español» porque `language="es"` degradaba a la voz inglesa (no había voces `es_*` instaladas, `download_models.py` solo bajaba la inglesa y `resolve_voice` caía al fallback global). Ahora `SPANISH_VOICE = "es_ES-davefx-medium"` y `DEFAULT_VOICES = {"en": ..., "es": ...}`, `default_voice_for(language)` (pura) y `resolve_voice` priorizan el default del idioma; `ensure_voice_for_language(language)` auto-descarga la voz del idioma en `/api/tts` (no-op si ya está, `False` sin red con caché negativa de 300 s, nunca lanza) y `download_models.py` instala también la española reutilizando el catálogo curado. `VoicesResponse.defaults` expone el mapa idioma → voz (aditivo). **(B) Modo Conversación:** `TranslatorScreen` gana dos pestañas (Conversación por defecto, Escribir intacto). Nuevos `useVoiceTurn.ts` (MediaRecorder + AnalyserNode + VAD + transcripción; helper PURO `nextTurnVadState` que cierra por silencio y descarta picos; auto-stop 120 s), `BigMicButton.tsx` (botón `size-24` con anillo según nivel), `ConversationPanel.tsx` (por idioma, repetir audio, avisos, rotación) y `ConversationTranslator.tsx` (dos paneles, traduce y auto-reproduce cada turno, historial en `english-tutor.translator-conversation`, toggles auto-play/«cara a cara», tamaño de texto y aviso/descarga de la voz española). i18n `translator.mode.*`/`translator.conversation.*` con paridad es/en. El Traductor sigue siendo AUXILIAR: no registra evidencia. Tests: pytest **2030**, vitest **72 ficheros/621 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.45.0** exit 0. Fuera de alcance (V3.46+): `transfer_condition` + CEFR/`difficulty_vector` del contexto (P1), Context Bank 2.0, diversidad 2.0, semantic appropriateness, transfer_state enriquecido y `expected_learning_value` / Adaptive Planner 2.0.

- ✅ **V3.44.0 — Lexicón sense-aware + scoring semántico 2.0 (2026-09-11)** (release `3.44.0`, app `3.43.0 → 3.44.0`). **Cierre quirúrgico de los dos P1 conceptuales de la auditoría de V3.43.0** (9,6/10), sin migración de datos y con contratos aditivos. **P1-01 (sense-aware):** el contrato de contenido gana `senses` (`GENERATOR_VERSION` `1.3.0 → 1.4.0`) con el helper puro `normalize_senses`; migración aditiva `senses_json` en `dictionary_entries`/`dictionary_reverse_entries` (idempotente, también en la tabla inversa ya creada); nuevo módulo PURO `services/semantics.py` con `pos_family`, `families_from_senses`, `occurrence_role` y `semantic_adequacy` (función de la ocurrencia vs familias POS de los sentidos). **P1-02 (scoring robusto):** `score_transfer_attempt(word, text, *, pos="", senses=())` devuelve `adequacy` ∈ `fit`/`suspect`/`incorrect`/`unknown`; `incorrect` → `semantic_mismatch` es el ÚNICO que bloquea el clean success y `suspect` → `semantic_doubt` (nueva en `TRANSFER_ERROR_TYPES`) es advisory; sin sentidos → `unknown`. `passed`/`lexical_transfer`/`semantic_fit` conservan su semántica y `score_write_attempt` no cambia. Contratos aditivos (`DictionaryEntryOut.senses`, `adequacy` admite `incorrect`) y feedback de `wordDrill` para `incorrect`. Tests: pytest **2020**, vitest **70 ficheros/608 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.44.0** exit 0. Fuera de alcance (V3.45+): `transfer_condition`, CEFR/`difficulty_vector` del contexto, Context Bank 2.0 y `expected_learning_value` / Adaptive Planner 2.0.

- ✅ **V3.43.0 — Transfer 2.0: target oculto, semanticidad, diversidad y `transfer_state` (2026-09-11)** (**Versión estable `3.43.0`**, app `3.42.0 → 3.43.0`). **Cierre quirúrgico de los 4 P1 de la auditoría de V3.42.0** sobre la evidencia de transferencia, sin migración y con contratos HTTP aditivos. **P1-01:** `services/transfer.py` reescribe el banco de contextos con atributos (`topic`/`communicative_goal`/`discourse_type`/…) y consignas que NUNCA contienen el target; el drill oculta la palabra también en `transfer` y la cola deja de mostrarla. **P1-02:** `score_transfer_attempt(word, text, *, pos)` separa el transfer léxico (`lexical_transfer`) de la adecuación semántica (`semantic_fit`/`adequacy` = `fit`/`suspect`/`unknown`) con un proxy DETERMINISTA (POS `noun` usada como verbo o `verb` tras determinante → `suspect`); el uso sospechoso mantiene `passed=True` y guarda `error_type="semantic_mismatch"` (nueva `TRANSFER_ERROR_TYPES`), sin bloquear la evidencia léxica. **P1-03:** `context_signals` mide diversidad contextual REAL (`context_diversity` con `diverse_dimensions`, `CONTEXT_DIVERSITY_MIN = 2`) sobre ÉXITOS LIMPIOS (sin `semantic_mismatch`), y `context_for` prioriza el contexto más distante de los ya logrados. **P1-04:** `transfer_state` (`not_ready` → `emerging` → `contextualized` → `transfer_demonstrated` → `transfer_stable` → `automatic`) sustituye al booleano `transfer`; `has_contextual_transfer` y `transfer_gap` leen el estado y `planned_signals` expone `transfer_state`/`context_diversity`. Contratos aditivos (`TransferContextOut`/`TransferAttemptOut`/`ReviewQueueItem`) y `spontaneous` justificado al ocultarse el target. Tests: pytest **1989**, vitest **70 ficheros/607 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.43.0** exit 0. Fuera de alcance (V3.44): modelo *sense-aware*, Context Bank a escala y `expected_learning_value`.

- ✅ **V3.42.0 — Transferencia contextual real + actividad `spontaneous_use` + gobierno por unidad léxica (2026-09-10)** (**Versión estable `3.42.0`**, app `3.41.0 → 3.42.0`). **Fase 4 y CIERRE del plan maestro V3.39+** (diccionario reversible → Traductor → motor de tarea óptima → transferencia real). La auditoría de V3.38.1 había separado dos cosas que el sistema confundía: `situation` es recuperación **contextualizada** y transferir es usar la unidad en un contexto **DISTINTO** del de aprendizaje. `services/transfer.py` (puro) aporta un banco curado de contextos y la elección determinista del que toca (`context_for`, filtrado por los `context_id` ya usados + hash estable `zlib.crc32`, rotación con `exhausted=True` al agotarse), `services/evidence.py::context_signals` agrupa el ledger por `context_id` (`contexts`, `context_attempts`, `success_contexts`, `home_context`, `transfer` con `CONTEXT_TRANSFER_MIN = 2`) y `planner.transfer_gap` decide cuándo pedir la tarea (≥ 2 éxitos en ≥ 1 contexto y < 2 contextos), añadiendo `transfer_gap` al orden de `EVIDENCE_REASON_ORDER`. La modalidad `spontaneous_use` deja de medirse sin tarea: **nueva actividad `transfer`** con `score_transfer_attempt`, `GET /api/vocabulary/drill/transfer-context` (solo lectura) y `POST /api/vocabulary/drill/transfer-attempt` (evidencia `spontaneous_use` + `activity_id="drill:transfer"` + `context_id` del contexto NUEVO). **Gobierno por unidad léxica:** `lexicon.unit_evidence` agrega el estado por `lexical_unit` (suma de contadores/mapas, `success_rate` recalculada del total, `automatic`/`automatic_skills`/`success_contexts` unidos, `transfer` derivado) para que `go/went/gone/going` no sean cuatro estados independientes; la cola expone `units` y cada ítem `unit_surfaces`/`transfer`/`success_contexts` (aditivos, la evidencia por forma no cambia). **Descomposición de `wordDrill.tsx`:** peldaños presentacionales extraídos a `wordDrillSteps.tsx` (`RecognitionStep`/`RecallStep`/`ProductionTextarea`/`TransferStep`) sin cambiar el contrato, escalera de 5 peldaños. Frontend: actividad `transfer` en la cola (palabra como recurso) y paso Transfer en el drill. Tests: pytest **1975**, vitest **70 ficheros/606 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.42.0** exit 0. **Plan maestro V3.39+ completo: sin fases pendientes.**

- ✅ **V3.41.0 — Motor de tarea óptima por skill + actividad de escritura + robustez de señales (2026-09-10)** (**Versión estable `3.41.0`**, app `3.40.0 → 3.41.0`). Fase 3 del plan maestro V3.39+ (diccionario reversible → Traductor → motor de tarea óptima → transferencia real). El planner pasa de "¿qué palabra repaso?" a **"¿qué modalidad limita, qué actividad la cierra y con qué apoyo?"**: `skill_priority`/`limiting_skill` (argmax con desempate canónico) y `select_task` (`{skill, activity, reason, support_level}`, orden `error_prone` → `skill_gap` → `slow_recall`) separan la **selección de actividad** de la **puntuación de prioridad**. El hueco simétrico `spoken ✓ / written ✗` deja de ser un diagnóstico muerto: nueva actividad **`write`** con scoring determinista y sin LLM (`score_write_attempt`, `unit_produced` + `WRITE_MIN_WORDS = 4`, taxonomía `WRITE_ERROR_TYPES`) y endpoint `POST /api/vocabulary/drill/write-attempt` que acredita `written_production`. **Señales robustas:** `recency_signals` (ventana de los 10 eventos más recientes + `median`/`p75`/`p90`/`latency_trend`, reutilizada por el resumen SQL), fallo grave y `error_prone` sobre la ventana, `is_automatic` **unificado** con `automatic_skills` cuando hay segmentación (con el criterio global como fallback de resúmenes parciales) y ledger encadenado al evento **cronológicamente anterior**. `example_for_many` batchea los ejemplos del `cloze` en una sola pasada al banco. Frontend: paso `write` en el drill y actividad `write` en la cola. Contratos HTTP **aditivos** (`limiting_skill`/`task` en `ReviewQueueItem`). Tests: pytest **1960**, vitest **70 ficheros/602 tests**, `ruff`/`tsc` limpios y `check_release_consistency` **3.41.0** exit 0. Siguiente: Fase 4 (transferencia contextual real y gobierno por `lexical_unit`).

- ✅ **V3.40.0 — Traductor de viaje bidireccional ES↔EN (2026-09-10)** (**Versión estable `3.40.0`**, app `3.39.0 → 3.40.0`). Fase 2 del plan maestro V3.39+
  (diccionario reversible → Traductor → motor de tarea óptima → transferencia
  real). **Nuevo destino AUXILIAR `translator`** (`/traductor`, 5.º en la
  navegación tras el separador, icono `Languages`, `grid-cols-5` en la
  bottom-nav) con `TranslatorScreen`: conmutador ES→EN / EN→ES (defecto ES→EN,
  el caso del viajero), botón ⇄ que intercambia sentido y textos, entrada por
  voz (`MicButton` con idioma) o texto, panel de resultado con altavoz por
  idioma (`ListenButton` con `language`) e historial reciente en
  `localStorage`. Es una ayuda de apoyo: **no registra evidencia** y funciona sin
  perfil. **Backend:** `services/translate.py` pasa a bidireccional con prompt
  por dirección y caché por `(direction, text)`, `/api/translate` gana
  `direction` (defecto `"en-es"`), `/api/tts` gana `language` y
  `resolve_voice(prefs, language)` elige la voz del idioma (preferida del idioma
  → default del idioma → primera instalada del idioma → fallback). El catálogo
  Piper añade tres voces `es_*` medium descargables. Contratos HTTP aditivos y
  retrocompatibles. Tests: pytest **1924**, vitest **70 ficheros/597 tests**,
  `ruff`/`tsc` limpios y `check_release_consistency` **3.40.0** exit 0.
  Siguiente: Fase 3 (motor de tarea óptima por skill).

- ✅ **V3.39.0 — Diccionario reversible EN↔ES + persistencia de la pestaña
  (2026-09-10)** (**Versión estable `3.39.0`**, app `3.38.1 → 3.39.0`). Fase 1 del
  plan maestro V3.39+ (diccionario reversible → Traductor → motor de tarea óptima
  → transferencia real). **Diccionario ES→EN:** inversa instantánea sobre las
  traducciones cacheadas (`services/dictionary_reverse.py`, puro: glosa múltiple,
  acentos plegados con la eñe conservada, ranking exacto > parcial) y generación
  con el modelo local solo si no hay coincidencia, cacheada en la tabla propia
  `dictionary_reverse_entries` (aislada de `dictionary_entries` para no
  contaminar el banco de distractores del MCQ). `GENERATOR_VERSION` 1.2.1 →
  **1.3.0** (política de frescura única para ambas direcciones) y fontanería de
  generación (single-flight, negative cache, rate limit) indexada por
  `(direction, word)`. Contrato HTTP aditivo: `direction` (defecto `"en-es"`) en
  la petición y `direction`/`alternatives` en la respuesta. La consulta sigue
  siendo SOLO LECTURA (D3). **Frontend:** conmutador EN↔ES, tarjeta reetiquetada
  y puente de práctica que practica el término INGLÉS. **Persistencia de la
  pestaña Personal/Consultar:** `useDictionaryView` con patrón doble
  (`localStorage` `english-tutor.dictionary-view` + settings `dictionary_view`),
  integrado en `DictionaryScreen` y en `QuizRoutePage`. Tests: pytest **1910**,
  vitest **68 ficheros/578**, `ruff`/`tsc` limpios y
  `check_release_consistency` **3.39.0** exit 0. Siguiente: Fase 2 (Traductor).

- ✅ **V3.38.1 — Cierre quirúrgico de los P1 del Planner + UI de diccionario y
  estado (2026-09-10)** (**Versión estable `3.38.1`**, app `3.38.0 → 3.38.1`).
  Release ADITIVA que cierra los 4 P1 de la auditoría de V3.38.0 y endurece
  `situation`, sin funcionalidad nueva, sin migración de BD y sin tocar scoring,
  FSRS ni la semántica del intervalo de evidencia. **(P1-01) Planner globalmente
  óptimo:** `domain/review.py` separa la cota de CANDIDATOS
  (`REVIEW_QUEUE_CANDIDATE_LIMIT = 500`) del límite de PRESENTACIÓN
  (`REVIEW_QUEUE_*_LIMIT`) y el recorte se aplica DESPUÉS del ranking global por
  `priority`; las cues se resuelven solo para los ítems servidos (arregla de paso
  el coste de `example_for` por todas las vencidas). **(P1-02) Señales por
  modalidad:** `summarize_evidence`/`summarize_by_target` (paridad exacta pura↔SQL)
  añaden `skill_attempts` y `skill_mean_response_time_ms`, `planned_signals` gana
  el bloque `skills` (attempts/successes/success_rate/weakness/support/latency por
  modalidad) y `is_slow_recall` deja de leer la media GLOBAL: mide la latencia de
  `recall` y exige un éxito de recall. **(P1-03) `skill_gap` parcial accionable:**
  basta con que falte `spoken_production` (caso `written ✓ / spoken ✗`) para
  dirigir la siguiente tarea a `sentence`. **(P1-04) Automaticidad robusta:**
  `AUTOMATIC_MIN_INDEPENDENT` 2 → **3**, nueva ratio mínima
  `AUTOMATIC_MIN_SUCCESS_RATIO = 0.80` y ausencia de fallo grave
  (`wrong_word` > `AUTOMATIC_MAX_WRONG_WORD_ERRORS`), aplicado a `is_automatic` y
  a `automatic_skills`. **(P2-01) `situation` endurecida:** nuevo módulo puro
  `services/situation.py` (única fuente de verdad) exige UN hueco, UNA sola frase
  y sin fuga morfológica regular de la diana; lo usan la generación
  (`GENERATOR_VERSION` 1.2.0 → **1.2.1**, regeneración lazy de la caché) y la
  lectura de la escalera. **UI:** ruta dedicada `/diccionario`
  (`DICTIONARY_PATH`, `routeMap`, cuarto destino tras separador, `DictionaryScreen`
  con vistas Personal/Consultar) y el indicador de conexión se integra en la
  cabecera (`ConnectionIndicator` con popover `SystemStatus`), eliminando la barra
  de estado inferior. Tests: pytest **1890**, vitest (**67 ficheros/568**),
  `ruff`/`tsc` limpios y `check_release_consistency` **3.38.1** exit 0. Diferido a
  V3.39: prioridad completa por skill, routing de escritura para
  `written_production`, `sense`/CEFR/contexto y refactor de `wordDrill.tsx`.

- ✅ **V3.38 — La siguiente tarea óptima: `situación`, planner y automaticidad por
  skill (2026-09-10)** (**Versión estable `3.38.0`**, app `3.37.1 → 3.38.0`). Cierra
  el incremento que V3.37 dejó abierto en tres frentes. **(1) P1-03 — automaticidad
  por modalidad.** El `skill` del ledger léxico deja de ser `""`: cada evento
  declara su MODALIDAD con el vocabulario canónico `LEXICAL_SKILLS` (`recall`,
  `written_production`, `spoken_production`, `spontaneous_use`); `summarize_evidence`
  (puro) y `summarize_by_target` (SQL, con paridad exacta fijada por test) añaden
  `skill_successes`/`skill_success_days`/`skill_independent_successes`/
  `skill_independent_days`, y `automatic_skills` segmenta `is_automatic` por
  modalidad: un ítem ya no es "automático" porque mezcle aciertos de reconocimiento
  con producción. **(2) Planner (Optimal Next Task).** Nuevo servicio puro
  `services/planner.py`: `planned_signals` combina olvido (1 − `retrievability`),
  hueco (`gap`), debilidad (`weakness`), dependencia de apoyo (`support`) y latencia
  (`latency`) con pesos declarados y calibrables (`PRIORITY_WEIGHTS`);
  `priority_score` los agrega y `evidence_reason` añade razones dirigidas por la
  evidencia fina (`error_prone`, `skill_gap`, `slow_recall`). La cola de repaso
  (`GET /api/learning/review`) pasa a ordenarse por esa prioridad —desempate por
  `retrievability` y palabra— y cada ítem expone `priority`/`signals`/`why`/
  `automatic_skills` (aditivos, sin spoiler). **(3) `situación`.** El contrato de
  contenido de la caché sube `GENERATOR_VERSION` 1.1.0 → **1.2.0** y gana
  `dictionary_entries.situation` (migración aditiva e idempotente): un enunciado
  situacional con un único hueco `_____`, validado de forma determinista (un solo
  hueco, sin spoiler, ≤ `MAX_SITUATION_CHARS`) y descartado —sin invalidar
  definición/traducción— si no cumple. `recall.RECALL_CUES` gana `situation` como
  TECHO de la escalera con apoyo `guided`; `next_recall_rung` solo llega a él con
  `cloze` consolidado y `resolve_recall_cue` sigue degradando solo hacia más apoyo.
  El GET/POST del drill lo sirven y lo declaran (`drill:recall:situation`), y la
  cola lo recomienda cuando hay contenido. Contrato HTTP aditivo; sin tocar scoring
  ni FSRS. Tests: pytest **1880** (+56: nuevos `test_skill_segmentation_v338.py`,
  `test_planner_v338.py` y `test_situational_cue_v338.py`), vitest (65
  ficheros/**560**), `ruff`/`tsc` limpios y `check_release_consistency` **3.38.0**
  exit 0. Diferidos a V3.39: deudas de V3.30 + transferencia por contexto V3.23 +
  `cloze_coverage` de corpus + `example_for_many` + refactor de `wordDrill.tsx`.

- ✅ **V3.37.1 — Política de consolidación y regresión de la escalera de recall
  (2026-09-10)** (**Versión estable `3.37.1`**, app `3.37.0 → 3.37.1`). Patch
  quirúrgico que cierra los dos P1 pedagógicos de la auditoría de V3.37.0, sin
  migración de BD (el peldaño ya se declaraba en `activity_id` desde V3.37.0) y
  sin tocar scoring ni FSRS. **P1-01 (consolidación):** un peldaño
  (`translation`/`definition`/`cloze`) solo se da por SUPERADO con
  `RECALL_RUNG_PASS_MIN_SUCCESSES = 2` éxitos en
  `RECALL_RUNG_PASS_MIN_DAYS = 2` días naturales distintos; la progresión pasa a
  ser EVIDENCIA → CONSOLIDACIÓN → MÁS EXIGENCIA (el umbral se mide sobre los
  éxitos del propio peldaño, no sobre `independent_successes`, porque
  `cued`/`guided` nunca son `independent` y exigir automaticidad bloquearía la
  escalera). **P1-02 (regresión):** si el peldaño ideal acumula
  `RECALL_REGRESSION_FAILURES = 2` fallos SIN ningún éxito, la recomendación
  baja al peldaño inmediatamente inferior (más apoyo); nunca por debajo de
  `translation`, y fallar jamás hace subir (el peldaño inferior ya está
  consolidado, así que no hay oscilación). `resolve_recall_cue` sigue
  degradando SOLO hacia más apoyo. El resumen de evidencia añade
  `recall_rung_days`/`recall_rung_failures` (puros y con paridad pura↔SQL en
  `summarize_by_target`), consumiendo el `activity_id` `drill:recall:<peldaño>`
  que V3.37 ya escribía; la evidencia legacy `drill:recall` no alimenta ninguna
  política. Contrato aditivo: `LexicalEvidence` amplía esos dos histogramas.
  Tests: pytest **1824** (+11, nuevo `test_recall_policy_v3371.py` con la matriz
  éxito/fallo/regresión/legacy/paridad), vitest (65 ficheros/**560**), `ruff`/
  `tsc` limpios y `check_release_consistency` **3.37.1** exit 0. Diferidos a
  V3.38/V3.39: P1-03 (automaticidad por skill), `cloze_coverage` y el refactor de
  `wordDrill.tsx`.

- ✅ **V3.37 — Learning Evidence 3.0: cues graduados y automaticidad (2026-09-10)**
  (**Versión estable `3.37.0`**, app `3.36.0 → 3.37.0`). La escalera del peldaño
  `2 · Recall` deja de ser un *fallback* (traducción y, si no, definición) y pasa
  a ser una PROGRESIÓN declarada `translation (cued) < definition (cued) <
  cloze (guided)`: `services/recall.py` sirve el peldaño PEDIDO (o el de V3.34
  cuando no se pide ninguno), `next_recall_rung` decide el siguiente por los
  ÉXITOS ya registrados por peldaño (`drill:recall:<peldaño>` → histograma
  `recall_rungs`) y `resolve_recall_cue` separa la decisión pedagógica de la
  disponibilidad real degradando SIEMPRE hacia más apoyo (nunca al revés). Cada
  peldaño declara su `support_level` en el ledger, así que `independent_successes`
  (V3.36) por fin tiene de dónde salir, y la **automaticidad** (`is_automatic`)
  exige ≥2 éxitos sin apoyo en DÍAS NATURALES distintos: un acierto suelto no
  consolida (D5/E3). El cloze es determinista desde el banco de pronunciación
  (`blank_out`, con reglas de honestidad: si queda alguna aparición de la
  palabra, el cue se descarta) y **ningún peldaño llama a un LLM**. La cola de
  repaso expone `recommended_cue`/`automatic` sin spoilear la palabra (P1-03 de
  V3.35.1 intacto). Sin migración de BD (`support_level`/`activity_id` ya
  existían) y sin tocar scoring, FSRS ni la semántica del intervalo de evidencia.
  Contrato HTTP aditivo: `cue` opcional en GET/POST, `support_level` en
  `RecallPromptOut`, `independent_success_days`/`recall_rungs` en
  `LexicalEvidence`. Fuera de alcance: `situación` (exige contenido autorado) y
  el planner (V3.38). Tests: pytest **1813** (+22), vitest (65
  ficheros/**560**, +1), `ruff`/`tsc` limpios, build OK y
  `check_release_consistency` **3.37.0** exit 0.

- ✅ **V3.36 — Learning Evidence 2.0 (2026-09-10)** (**Versión estable `3.36.0`**,
  app `3.35.1 → 3.36.0`). El ledger longitudinal aprende el **CÓMO** de cada
  evento, con migración aditiva e idempotente y contrato HTTP aditivo:
  `support_level` (eje `copied → guided → cued → independent → spontaneous`, el
  MISMO de `academy_evidence`; hay test de paridad entre ambos), `difficulty`
  (CEFR 1-6, escala compartida con listening; `0.0` = no declarada),
  `context_id`/`activity_id` (contexto y actividad concreta), `response_time_ms`
  (latencia medida en cliente) y `error_type` (taxonomía determinista del
  intento). Captura end-to-end: recall → `cued`/`drill:recall` con clasificación
  del intento; retrieval → `guided`/`drill:word`|`drill:sentence` con la duración
  convertida a ms; producción por canal → apoyo real del canal (`chat` →
  `spontaneous`, `conversación guiada` → `guided`, `speaking`/`writing` →
  `independent`) y contexto `lexicon:<canal>`. `summarize_evidence` y
  `summarize_by_target` añaden `success_rate`, `independent_successes`,
  `support_levels`, `error_types` y `mean_response_time_ms` con paridad pura↔SQL
  fijada por test. **Decisión de alcance (`error_type` observacional):**
  clasificar NO toca scoring, ni evidencia, ni FSRS — una errata sigue siendo
  `correct=false`, pero el tutor ya distingue "no lo sabe" de "lo sabe y lo
  escribió mal" (el clasificador es conservador a propósito: `cat`/`cut` es otra
  palabra, no una errata). Fuera de alcance: cues graduados y planner (V3.37).
  Tests: pytest **1791** (+22), vitest (65 ficheros/**559**, +1), `ruff`/`tsc`
  limpios y `check_release_consistency` **3.36.0** exit 0.

- ✅ **V3.35.1 — Cierre de la auditoría V3.35.0 (2026-09-10)**
  (**Versión estable `3.35.1`**, app `3.35.0 → 3.35.1`). Patch quirúrgico de
  integridad del modelo longitudinal, sin cambios de esquema ni de arquitectura:
  **P1-01** `interval_since_last_evidence` deja de recibir el `interval_days` de
  la decisión de retención (ancla FSRS) y lo deriva SIEMPRE `record_evidence` de
  la evidencia anterior del ledger (`learning_evidence → learning_evidence`):
  dos conceptos distintos que ya no se mezclan; **P1-02** los `intervals` del
  resumen conservan el orden CRONOLÓGICO (se retira el `sort()` de
  `summarize_evidence` y el `summarize_by_target` ordena por
  `occurred_at, id`, no por valor del intervalo): la secuencia real del
  scheduler no se pierde; **P1-03** la cola «Repaso de hoy» solo muestra la
  palabra en `recognition` — en `recall`/`sentence` la oculta (el drill ya la
  ocultaba) para no spoilear la recuperación; **P2-02**
  `record_evidence_bulk` deduplica eventos idénticos y encadena el intervalo de
  eventos distintos del mismo target dentro del lote. Tests: pytest **1769**
  (+5), vitest (65 ficheros/**558**, +1), `ruff`/`tsc` limpios y
  `check_release_consistency` **3.35.1** exit 0.

- ✅ **V3.35 — Longitudinal Learning Evidence 1.0 (2026-09-10)**
  (**Versión estable `3.35.0`**, app `3.34.0 → 3.35.0`). Cierra los **dos P1**
  de la auditoría de V3.34.0 y sienta el modelo de evidencia longitudinal, sin
  rehacer arquitectura y sin migración destructiva.
  **P1-1 (ancla):** la recuperación demorada deja de estar anclada a la primera
  exposición. `services/lexicon.py::delayed_retrieval_decision` (pura) encadena
  `evento_n → intervalo → evento_{n+1}`: el ancla es la última recuperación
  válida (`max(last_retrieval_at, last_recall_at)`) y el intervalo exigido lo
  calcula FSRS (`due_at` de la carta `lexicon`); sin carta, suelo
  `RETENTION_MIN_INTERVAL_DAYS`. `D0 → D+3` acredita; `D+3 → D+4` ya no si FSRS
  no ha vencido. **P1-2 (cola):** el repaso espaciado sale del speaking
  micro-drill — nuevo `GET /api/learning/review` con cartas FSRS `lexicon`
  vencidas ordenadas por urgencia y actividad óptima por hueco de competencia
  (`recommend_review_activity`: recognition/recall/sentence); se retira
  `due_words` de `drill_candidates`. **Evidencia:** tabla append-only
  `learning_evidence` (+ `event_role` en `learning_events`), repositorio
  `evidence.py` y servicio puro `services/evidence.py` (roles +
  `summarize_evidence`), contador aditivo `recall_attempts` y bloque `evidence`
  (`attempts`/`successes`/`days`/`intervals`) expuesto en el léxico y en la cola
  de repaso. UI: sección «Repaso de hoy» (`ReviewQueueSection`) + `initialStep`
  del `WordDrill`. Tests: pytest **1764** (+21), vitest (65 ficheros/**557**,
  +2 ficheros/+8 tests), `ruff`/`tsc` limpios y `check_release_consistency`
  **3.35.0** exit 0.

- ✅ **V3.34 — Dictionary → Learning Bridge, eslabón 3: Recall 2.0 (texto)
  (2026-09-10)** (**Versión estable `3.34.0`**, app `3.33.1 → 3.34.0`). El
  peldaño intermedio del drill deja de ser una repetición oral de la palabra y
  pasa a ser recuperación REAL por texto: el alumno ve el SIGNIFICADO (cue =
  traducción o definición sin spoiler) y teclea la palabra. A diferencia de
  Recognition (informativo), el acierto deja señal léxica PROPIA
  (`recall_successes`/`recall_days` + ledger `recalled`) sin acreditar
  producción, acredita la recuperación demorada existente si supera el
  intervalo (`retrieval_*`) y reprograma la carta FSRS `lexicon` con intervalos
  reales (Good/Easy/Again). La escalera queda en tres peldaños
  (`1 · Recognize` · `2 · Recall` · `3 · Sentence`) con el micrófono reservado a
  Sentence; si Recall no tiene cue, degrada a Sentence sin romperla. Endpoints
  `GET /api/vocabulary/drill/recall` y `POST …/recall-attempt`; migración
  idempotente y sin backfill de la capa de recall. Tests: pytest **1743** (+20),
  vitest (63 ficheros/**549**, +2), `ruff`/`tsc` limpios y
  `check_release_consistency` **3.34.0** exit 0.

- ✅ **V3.33.1 — Hardening de Recognition (auditoría V3.33.0) (2026-09-10)**
  (**Versión estable `3.33.1`**, app `3.33.0 → 3.33.1`). Dos correcciones P1 de
  la auditoría externa, sin tocar la evidencia (sigue SOLO informativa) ni la
  seguridad del scoring (el GET nunca expone la correcta):
  **P1-01** la permutación deja de depender solo de la palabra —
  `recognition_options_for(word, entries, seed="")` mezcla `palabra + seed` y el
  `GET drill/recognition` entrega un nonce por intento (`question_id`) que el
  `POST` reenvía para reconstruir la misma permutación (premisa 21: sin estado
  servidor), de modo que reintentar `cat` rebaraja las opciones y no se puede
  memorizar la posición; **P2** `_stable_int` pasa a `SHA-256` (mejor dispersión;
  `listening_bottom_up` conserva el suyo por compatibilidad de ítems publicados);
  **P1-02** `WordDrill` arranca en `1 · Recognize` y degrada a Recall si
  `available=false` (`Practicar → Recognize → Recall → Sentence`). Contrato
  aditivo (`question_id` opcional en GET/POST). Tests: pytest **1723** (+1),
  vitest (63 ficheros/**547**, +1), `ruff`/`tsc` limpios y
  `check_release_consistency` **3.33.1** exit 0.

- ✅ **V3.33 — Dictionary → Learning Bridge, eslabón 2: Recognition (MCQ
  definición ↔ palabra) (2026-09-09)** (**Versión estable `3.33.0`**, app
  `3.32.0 → 3.33.0`). La escalera compartida de drill (`wordDrill.tsx`, lookup
  Y hub) pasa a **`1 · Recognize` · `2 · Word` · `3 · Sentence`**: el primer
  peldaño pide el significado de la palabra entre opciones que sirve el
  backend. La pregunta es **pura y determinista por palabra** (premisa 21, sin
  estado servidor): `services/dictionary_mcq.py` la deriva de la caché global
  `dictionary_entries` (`list_entries()` nuevo en `repositories/dictionary.py`)
  — correcta = significado real de la diana en un modo consistente
  (`translation` si hay distractores, si no `definition`), distractores de
  otras entradas preferir mismo `pos`, deduplicados, barajado estable ocultando
  la correcta; sin distractores → `available=false` (degradación con aviso) — y
  el servidor la RECOMPUTA al puntuar (`GET drill/recognition` nunca expone la
  correcta; `POST drill/recognition-attempt` devuelve
  `{correct, correct_index, selected_index}`). **Evidencia SOLO informativa**
  (V3.13: el MC de reconocimiento no demuestra destrezas productivas): un
  evento `learning_events` `drill:<word>:recognition:ok|ko`; cero cambios en
  `vocabulary`/`vocabulary_events`, FSRS, mastery, usage ni candidatas (el
  acierto no dispara `onProduced`/`refreshEntry`). Sin etiquetas de origen ni
  estados servidor; sin cambios de esquema de BD. Tests: pytest **1722** (+11
  del nuevo `test_dictionary_recognition_v333.py`: determinismo y GET sin la
  correcta · acierto/fallo solo informativos con cero efectos · modo definition
  y dedupe · eventos recognition que no alteran `drill_ok_days`/candidates ·
  aislamiento A/B · sin entrada/sin distractores → 409/`available=false` ·
  normalización), ruff limpio, vitest (63 ficheros/546) y `tsc --noEmit`
  limpios y `check_release_consistency` **3.33.0** exit 0. Pendiente hacia
  **V3.34**: recall demorado con FSRS, transferencia por contexto de actividad
  V3.23 y los diferidos de V3.30 (consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat).

- ✅ **V3.32 — Dictionary → Learning Bridge, primer eslabón (2026-09-09)**
  (**Versión estable `3.32.0`**, app `3.31.1 → 3.32.0`). Convierte la
  consulta del diccionario (V3.30, D3: solo lectura) en puerta a la práctica
  real: la tarjeta del lookup gana **«Practicar esta palabra»**, que monta
  in-line la escalera de drill existente (Recall → Sentence) para la palabra
  consultada — también si `usage.tracked=false` (sin fila previa en
  `vocabulary`): el éxito crea producción pura igual que fuera del
  diccionario. Refactor de extracción neutro: `WordDrill`,
  `SpeakingDrillSection`, `DrillStep` e `isSentenceAttempt` pasan de
  `PersonalDictionary.tsx` al módulo compartido `wordDrill.tsx` (misma UI,
  mismo comportamiento). Sin backend nuevo (los endpoints de drill ya aceptan
  palabras arbitrarias) ni etiquetas de origen en la evidencia: un éxito llama
  `record_production_text(speaking, as_unit=True, activity="drill")` +
  `learning_events` `drill:<word>:ok`, con fila idéntica a practicar fuera del
  diccionario (verificado por aceptación A/B). D3 intacto: el lookup sigue sin
  escribir; solo la acción explícita «Practicar» y su resultado escriben en el
  Student Model. Tests: pytest **1711** (+3 del nuevo
  `test_dictionary_bridge_v332.py`: lookup read-only + práctica con evidencia
  idéntica entre usuarios A/B, paso frase equivalente con cierre D3 y
  aislamiento entre usuarios), ruff limpio, vitest y `tsc --noEmit` limpios y
  `check_release_consistency` **3.32.0** exit 0. Pendiente hacia **V3.33**:
  los diferidos de V3.30 — consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat — y los siguientes eslabones del puente (escaleras por
  destreza, recall demorado FSRS).

- ✅ **V3.31.1 — Hardening del diccionario tras la auditoría V3.31.0
  (2026-09-09)** (**Versión estable `3.31.1`**, app `3.31.0 → 3.31.1`; solo
  backend + docs, sin cambios de UI ni de esquema de BD). Cierra el **P1-01
  residual** y los **P2** de robustez del diccionario: **`pick_model` exige un
  modelo explícito INSTALADO** (`services/translate.py`: antes bastaba con que
  no estuviera en `UNUSABLE_MODELS` para llegar a Ollama; ahora consulta
  `installed_models()` y solo devuelve el explícito si está instalado y es
  utilizable, si no cae al fallback automático) · **negative cache del
  generador** (`domain/vocabulary.py`: un fallo marca la palabra en memoria
  durante `DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS` 30 s — las consultas
  siguientes degradan a `definition_source="none"` sin reintentar en bucle — y
  la marca expira o se limpia al conseguir una generación) · **rate limit de
  generación nueva** por usuario (10/min) y global (40/min) con degradación
  normal (nunca 5xx); solo el dueño de un vuelo genera y lo cacheado no
  consume cupo · **tope servidor del dueño del vuelo**
  (`DICTIONARY_GENERATION_TIMEOUT_SECONDS` 90 s con `asyncio.wait_for`: un
  Ollama colgado degrada, libera el vuelo y marca negative cache) ·
  **semántica documentada del contenido canónico** (la caché es global y sin
  `model_id`; `model` solo influye en la generación de contenido nuevo).
  Tests: pytest **1708** (+11: +3 en `test_translate.py` de explícito no
  instalado y +8 en el nuevo `test_dictionary_hardening_v3311.py`),
  ruff limpio, vitest y `tsc --noEmit` limpios y `check_release_consistency`
  **3.31.1** exit 0. Pendiente hacia **V3.32**: Dictionary → Learning Bridge
  (`agentes/v332-dictionary-learning-bridge.md`), consumo de
  `word_breakdown_json` en agregados/práctica dirigida de las falladas y
  palabras tocables en transcripts/chat.

- ✅ **V3.31 — Cierre de la auditoría V3.30.1: robustez y contrato del
  diccionario (2026-09-09)** (**Versión estable `3.31.0`**, app
  `3.30.1 → 3.31.0`). Cierra los hallazgos residuales de la auditoría profunda
  de V3.30.1: **single-flight robusto a cancelación** (`domain/vocabulary.py`:
  el `CancelledError` del dueño del vuelo resuelve el Future con None antes de
  propagar — los waiters ya no cuelgan — y tope defensivo de 60 s en los
  waiters) · **invalidación del contenido de caché previo a V3.31**
  (`GENERATOR_VERSION` `1.0.0 → 1.1.0` en `services/dictionary_content.py`;
  `DICTIONARY_LEGACY_VERSION = "1.0.0"` en `repositories/db.py`, marca
  deliberadamente distinta de la actual que la migración aplica a las filas sin
  versión: el contenido del parser greedy de V3.30 regenera una vez) · **tests**
  de la migración de upgrade desde una BD V3.30.0 (aditiva + backfill +
  conservación + idempotencia), del path real del diccionario con modelo
  explícito no utilizable (`qwen3.5:9b` nunca llega a Ollama) y de la
  cancelación del líder · **contrato frontend**: tipo `DictionaryLookupRequest`,
  body tipado y test del `POST /api/vocabulary/dictionary?user_id=` (método,
  query, header y body) + timeout de cliente de 120 s. Tests: pytest **1697**
  (+4), ruff limpio, vitest y `tsc --noEmit` limpios y
  `check_release_consistency` **3.31.0** exit 0. Pendiente hacia **V3.32**:
  Dictionary → Learning Bridge (`agentes/v332-dictionary-learning-bridge.md`),
  consumo de `word_breakdown_json` en agregados/práctica dirigida de las
  falladas y palabras tocables en transcripts/chat.

- ✅ **V3.30.1 — Endurecimiento del diccionario de consulta (2026-09-09)**:
  patch de la auditoría V3.30.0 sobre v3.30.0 (**Versión estable `3.30.1`**,
  app `3.30.0 → 3.30.1`; solo backend + docs, sin cambios de UI). Cierra los
  tres P1: **P1-01** una sola generación LLM por palabra en concurrencia
  (`domain/vocabulary.py`: single-flight por palabra con Future — N consultas
  simultáneas → 1 llamada al modelo y 1 fila; el `INSERT OR IGNORE` protegía la
  fila pero no la generación; los waiters reciben el mismo resultado y un fallo
  no reintenta en cascada) · **P1-02** la política `UNUSABLE_MODELS` ya no se
  salta con un modelo explícito (`services/translate.py` `pick_model`: el
  explícito no utilizable cae al fallback automático, único punto de política
  para diccionario y traducción) · **P1-03** caché versionada
  (`dictionary_entries.generator_version` aditiva + migración idempotente con
  backfill `'1.0.0'` del contenido V3.30; `save_entry` upsert `ON CONFLICT DO
  UPDATE` con `updated_at` real; el dominio solo sirve caché con la
  `generator_version` actual y regenera/sobrescribe la obsoleta). P2: parser
  JSON con `raw_decode` que toma el PRIMER objeto válido (la regex greedy
  `{.*}` se tragaba `{…} texto {…}`). Tests: pytest **1693** (+9: concurrencia
  misma palabra y dos usuarios, fallo concurrente sin reintentos, regeneración
  por versión obsoleta, reuso de versión fresca, parser multi-objeto y llaves
  en prosa, `pick_model` con explícito no utilizable), ruff limpio y
  `check_release_consistency` **3.30.1** exit 0. Pendiente entonces: candidatos
  hacia V3.32 (Dictionary → Learning Bridge, palabras tocables en
  transcripts/chat).

- ✅ **V3.30 — Diccionario de consulta con marcas de uso y aprendizaje
  (2026-09-09)**: cerrado e implementado sobre v3.29.0 (**Versión estable `3.30.0`**, app `3.29.0 → 3.30.0`) con el dossier
  `docs/DISENO-V330-DICCIONARIO-CONSULTA.md` (decisiones **D1** LLM local a
  demanda con caché persistente en `dictionary_entries` · **D2** entrada = hub
  Vocabulario, vista «Consultar» · **D3** la consulta es solo lectura, sin
  evidencia ni impacto en mastery): **endpoint `POST /api/vocabulary/dictionary`**
  — marca de uso/aprendizaje por forma y por `lexical_unit` (estado, recall,
  contadores, matriz de competencia, agregado de unidad), frase de ejemplo
  determinista del banco (`services/example_sentences.py`) y definición/
  traducción generadas por el modelo local (`services/dictionary_content.py`:
  prompt JSON, parseo tolerante, `INSERT OR IGNORE` idempotente, degradación a
  `definition_source="none"` y fallback en memoria si la BD falla) ·
  **UI «Consultar»** (`DictionaryLookup.tsx`, conmutador con el diccionario
  personal en la vista alterna de `QuizRoutePage`; solo Vocabulario la declara),
  cliente `lookupDictionaryWord` + tipo `DictionaryEntry`, claves
  `dictionary.lookup.*` es/en. Tests: pytest **1684** (39 tests del diccionario
  en `test_dictionary_lookup.py` + `test_dictionary_content_v330.py`), ruff
  limpio, vitest **538** (63 archivos; `DictionaryLookup.test.tsx`), `tsc
  --noEmit` limpio y `check_release_consistency` **3.30.0** exit 0. Pendiente:
  candidatos V3.31 (palabras tocables en transcripts/chat, consumo de
  `word_breakdown_json` en agregados / práctica dirigida de las falladas).

- ✅ **V3.29 — Listening Engine 4.0, Fase 3 (núcleo, 2026-09-09)**: cerrado e
  implementado sobre v3.28.1 (**Versión estable `3.29.0`**, app `3.28.1 →
  3.29.0`) con el plan `v3.29_nucleo_fase_3…plan.md` (P1–P6): **motor de
  alineación por palabra offline** (`services/word_alignment_proxy.py` +
  `transcribe_words` con `word_timestamps=True`; sidecar `{wav}.words.json`
  etiquetado `asr_word_proxy` con cobertura mínima ~80 %, nunca verdad
  acústica; hooks en `generate_listening_audio.py`/`get_audio`/
  `import_audio.py` + script de backfill) · **`word_timings` servidos en el
  payload** (`word_timings_for`; asignación palabra→frase por tiempo contra
  `coarse_sentence_timings`; funciona con `repetition_policy="twice"` y ítems
  derivados `d-`; slow/fast se escalan en cliente por `speech_rate`) · **karaoke
  palabra a palabra** (`KaraokeTranscript`: revelado por frase, palabra activa,
  toque→seek; degrada a `CoarseTranscript` sin sidecar/cobertura baja) ·
  **controles de audio precisos** (duración vía `loadedmetadata`, bucle con
  scheduler `requestAnimationFrame` inyectable, seek slider + bucle A/B en la
  tarjeta) · **salto a la palabra fallada** (`failedWordTiming`, botones
  «repetir palabra fallada» normal/slow en dictado y cloze incorrecto) ·
  **evidencia `word_breakdown_json`** (columna aditiva nullable, migración
  idempotente; se persiste el breakdown del dictado fallido y el target del
  cloze/segmentation incorrecto; sin consumo en agregados — V3.30). El
  diccionario de consulta se reprioriza a V3.30 (siguiente candidato).

- ✅ **V3.28.1 — patch de la auditoría V3.28.0 (2026-09-09)**: cerrado e
  implementado sobre v3.28.0 (**Versión estable `3.28.1`**, app `3.28.0 →
  3.28.1`) con el plan `v3.28.1_patch_auditado_e76303f2.plan.md`: **P1-01**
  dictado parcial derivado servible — `derived_catalog` expone
  `DERIVED_PRODUCTION_POOL` y `pick_next_question` lo sirve en sesiones
  bottom-up (Caso A) con señal de `dictation` débil, tras agotar
  cloze/segmentación del nivel, nunca en puerta/certificación · **P1-02**
  scoring exacto por token del dictado escrito (`dictation_score` sin
  Soundex/phoneme/prosodia; `submit_production` lo aplica a todo
  `task_type=dictation`; fila fonética oculta en la UI) · **P1-03**
  Gonnago/reducciones por token y frontera (`contains_word_token` compartido
  en `_reductions_in`/`_is_eligible_token`/`_connected_speech_realized`;
  contenido de `l16` corregido, audio digest regenerado) · **P1-04/P2-01**
  AudioController integrado verificado (play/pausa/variantes operativas;
  seek/setRate fino/loop/replay/markSegment sin UI → V3.29 Fase 3) y `seek()`
  notifica `onCurrentTime` en pausa. Tests: pytest **1693** (backend 1619 +
  launcher 74), ruff limpio, vitest **506** (61 archivos), `tsc --noEmit`
  limpio y `check_release_consistency` **3.28.1** exit 0. Pendiente: dossier de
  auditoría del candidato v3.28.0 (letra P) y Fase 3 del engine en V3.29.
- ✅ **V3.28 — Listening Engine 4.0 Fase 2 (2026-09-09)**: cerrado e
  implementado sobre v3.27.0 (**Versión estable `3.28.0`**, app `3.27.0 →
  3.28.0`) con el plan
  `v3.28_listening_engine_fase_2_…plan.md` y los Bloques A-F de la Fase 2 de
  `docs/LISTENING_ENGINE_4.0.md` (§14, **Fase 2 cerrada**; el diccionario de
  consulta se reprioriza a V3.29, candidato). **Bloque A — micro-flujo
  unificado (P1-01)**: `next_question` sirve `flow`/`transcript_policy` también
  en rutas por nivel (`level=X`) y drill (`mode=failed`) vía el helper
  `_public_with_flow`; solo `mastered` conserva el modo compacto sin flow
  (contrato E2E-04) · **Bloque B — AudioController 4.0**:
  `features/listening/audioController.ts` (clase pura sobre
  `HTMLAudioElement`: `play/pause/seek/setRate` con `preservesPitch` y selección
  de la variante de URL más cercana, `loopSegment`, `replayCurrent`,
  `markSegment`, suscripción de `currentTime`/`ended`/`ratechange`) + hook
  `useAudioController` consumido por `ListeningPractice.tsx` (while1/while2/
  replay ya no crean `new Audio()` sueltos) · **Bloque C — Bottom-up derivado
  (P1-02/P1-03 parcial)**: `services/listening_bottom_up.py` deriva ítems
  deterministas del corpus existente (`cloze` auditivo MCQ con banco de
  distractores por nivel, `partial_dictation` de producción con scoring por
  tokens, `segmentation` de pares contraídos solo donde el corpus los realiza;
  regla «si no hay candidato fiable no se emite»); los derivados (`derived=True`)
  se sirven en práctica adaptativa/por nivel con perfil Caso A pero se filtran
  siempre del pool de ruta y la certificación · **Bloque D — transcript
  dinámico con sync grueso**: timings de frase heurísticos y proporcionales a
  `clean_transcript`/`duration` (etiquetados `coarse_heuristic`, nunca
  alineación acústica) en el payload; frontend con `CoarseTranscript`
  (hidden/partial/full + resaltado de la frase activa por `currentTime` del
  AudioController) · **Bloque E — Shadowing 2.0**: playback real de la grabación
  del alumno en el paso shadowing (`RecordingPlayButton` reutilizado) y señales
  auxiliares no bloqueantes (`shadowing_duration_ms`, `shadowing_speech_rate`)
  calculadas en cliente y persistidas con migración aditiva idempotente —sin
  peso de mastery ni gate— · **Bloque F — E2E adaptativos y negativos**:
  `test_listening_e2e_v328.py` recorre el ciclo completo con `TestClient`
  (E2E-01 Caso A recognition→bottom_up con flow de 5 etapas · E2E-02 Caso D
  connected speech que obliga al shadowing en B2 · E2E-03 Caso C top-down ·
  E2E-04 `mastered` compacto) + negativos del contrato pedagógico (derivado
  nunca certifica, `transcript_used` fiable, B2 sin reveal manual pre-Post).
  Tests: pytest **1683** (backend + launcher), ruff limpio, vitest **505** (61
  archivos), `tsc --noEmit` limpio y `check_release_consistency` **3.28.0**
  exit 0. Pendiente: dossier de auditoría del candidato v3.28.0 (letra P) y
  Fase 3 del engine (karaoke palabra a palabra) en V3.29.
- ✅ **V3.27 — Listening Engine 4.0 Fase 1 (2026-09-09)**: cerrado e
  implementado sobre v3.26.0 (**Versión estable `3.27.0`**, app `3.26.0 →
  3.27.0`) con el plan
  `docs/PLAN-V327-LISTENING-ENGINE-4.md` y la especificación
  `docs/LISTENING_ENGINE_4.0.md`. **Backend = fuente única de la política
  pedagógica** (`services/listening_flow.py`: `flow` pre/while1/while2/post/
  shadowing + `transcript_policy` servidos por pregunta; el frontend ejecuta
  una máquina de presentación en `features/listening/microFlow.ts`, sin reglas
  propias) · **Perfil auditivo visible en UI**: `services/auditory_profile.py`
  (casos A-D) + `AuditoryProfileCard` persistente y no bloqueante (sin datos →
  needsMore → intervención), y `next_question` prioriza la capa recomendada
  (`pick_next_question(layer=...)`) · **Evidencia ampliada**: 5 columnas nuevas
  en `listening_attempts` (`layer`/`speed_used`/`stage`/`transcript_used`/
  `segments_replayed`) con migración idempotente y persistencia en
  `submit_answer`/`submit_production`, contrato opcional y backward compatible
  en schemas/routers/tipos/API. Tests: pytest **1647**, vitest **472** (59
  archivos), ruff/`tsc` limpios, `check_release_consistency` **3.27.0** exit 0.
  Pendiente: auditoría externa del candidato v3.27.0 y Fase 2 del engine
  (reproductor rico/karaoke; calibración de umbrales del perfil).

- ✅ **V3.19 — Léxico por destreza + Speaking micro-drill (2026-09-07)**: cerrado
  e implementado sobre v3.18.0 (backend `3.18.0 → 3.19.0`) con las decisiones
  del gerente y el dossier de la auditoría profunda V3.18. **P0 — volcado por
  destreza**: `record_words` → `record_production(user, words, channel)`; la
  tabla `vocabulary` gana `chat_prod`/`speaking_prod`/`writing_prod`/
  `conversation_prod` (backfill idempotente `chat_prod = appearances`;
  invariante `sum(columnas) == appearances`) y las 7 superficies de producción
  vuelcan por un único helper compartido (CAP-01/REFAC-01) · **P1 — Speaking
  micro-drill**: señal en servidor `exposures > 0 AND speaking_prod == 0`
  (`GET /api/vocabulary/drill/candidates`) + `POST /api/vocabulary/drill/attempt`
  reutilizando el scorer de pronunciación (sin evidence/FSRS, D5/E3); chips de
  `PersonalDictionary` con acción real · **Fixes P1 del dossier**: R6-01
  retención impuesta en servidor (409), GATE-01 objetivo `locked` no evaluable
  (409), CLAIM-01 copy "nivel oral actual (examen)", SIGNAL-01 semántica oral +
  copy, ERR-01 404→503, LIST-01/02/03 tokens de foco servibles + corpus
  re-etiquetado + unicidad de script, CONV-01 reconstrucción por `mode` (el
  tecleo no es tiempo oral) · **Deuda externa**: ADMIN-01 fail-closed
  (`ADMIN_PIN=""` → 401) y BOOL-01 (`type(selected) is int`). Tests: pytest
  **1371**, vitest **417**, ruff/`tsc`/`vite build` limpios,
  `check_release_consistency` **3.19.0** exit 0 y curriculum `--strict --quality`
  exit 0; CONSTITUCIÓN sin cambios (R8/R9 propuesta abierta).
- ✅ **Auditoría profunda V3.18 pre-V3.19 (2026-09-07, read-only)**: auditado
  código por código en 6 áreas (A1 academy/dominio · A2 evidence graph/FSRS/
  léxico · A3 speaking/pronunciación · A4 writing/conversación/cross-skill ·
  A5 assessment/contenido CEFR · A6 frontend claims) con dossier consolidado
  `docs/audit/I-AUDITORIA-PROFUNDA-V318.md` y lista P0/P1/P2 mapeada a
  decisiones V3.19. Sin P0 confirmado; P1 clave: **R6-01** retención R6 sin
  enforcement en servidor, **GATE-01** gating de objetivo no validado en
  endpoints, **CLAIM-01** UI "demostrado" oral sin gate, **SIGNAL-01**
  `recognized_not_produced` con semántica de teclado, **PROD-01/WR-UI-01**
  producción oral/escrita nunca llega al léxico (confirma el P0 del candidato
  V3.19). Deuda de la auditoría externa diferida a V3.19: **ADMIN-01**
  (`ADMIN_PIN=""` → fail-closed) y **BOOL-01** (bool-as-int en
  `unit_review.py`). Árbol sin cambios de código; `backend/config.py` sigue
  `3.18.0`; CONSTITUCIÓN sin cambios (R8/R9 siguen como propuesta abierta).
- ✅ **Preparado para auditoría TOTAL externa (2026-09-07, read-only):** árbol de
  trabajo limpio (v3.18.0 en HEAD, release-notes v3.10–v3.18 versionadas),
  todos los gates automáticos en verde (pytest 1345, ruff, vitest 414,
  `tsc`/`vite build`, consistencia 3.18.0, i18n exit 0, Beta V3.0, curriculum
  `--strict --quality`, content validation) y briefing autocontenido en
  `agentes/auditoria-total-externa.md` con el runbook y el mapa claim→código.
- ✅ Backend FastAPI + Pydantic (chat + voz + progreso + listening + CEFR + evaluación del tutor).
- ✅ Frontend Vite + React + TypeScript (chat, voz continua, dashboard de progreso, listening, calidad del tutor).
- ✅ Lanzador de escritorio (`launcher/`, GUI tkinter) con acceso directo e icono.
- ✅ Versión estable `3.26.0` — **Hoja de ruta completa: Ejes A + B + C** (los
  P2 de las auditorías externas V3.24/V3.25; dossier `docs/audit/O-AUDITORIA-TOTAL-V326.md`):
  **Eje A — retención longitudinal y gate MASTERED** (F-A1 initial/practice
  espaciado, F-A2 ancla `delayed` a su origen formal con `event_age` vs
  `retention_interval`, F-A3 ≥2 reassessment points estables por destreza con
  fix del escritor `kind=level`) · **Eje B — emisor real de `novel`** (F-B1:
  primera misión B2+ jamás practicada; requisito `novel_required=0` intacto) +
  **historia léxica por superficie** (F-B2: ledger `vocabulary_events`
  append-only, sin backfill) · **Eje C — Listening real y calibración** (F-C1
  taxonomía recognition/comprehension/inference con reporte `by_layer`,
  F-C2 escalera CEFR monótona unificada de extremos matriz 2.1.0, F-C3
  `blocked_by` con motivo traducido en la UI, F-C4 marcas de legacy sin
  `context_id` por destreza/global/ladder). Verificación íntegra: pytest
  backend **1538 passed** + ruff, vitest **450 passed** (57 archivos) + tsc;
  `check_release_consistency` 3.26.0 exit 0.
- ✅ Versión estable `3.25.1` — **Cierre de P1 de la auditoría externa V3.25**
  (patch correctivo sobre v3.25.0; dossier `docs/audit/N-AUDITORIA-TOTAL-V3251.md`,
  evidencia de cierre: los 6 tests negativos del gate): **certification_gate
  real** — baseline formal (`task_type="exam"`) + eventos `delayed` por
  `context_id`, con ventana ≥ `RETENTION_MIN_DAYS` y ratio ≥
  `RETENTION_STABLE_RATIO` verificados desde las propias filas (sin examen no
  se certifica; `retention_report` informa `interval_days`/`initial_score`/
  `rate`/`baseline_date`) · **agregación real por `lexical_unit`** —
  `units_from_rows`/`summary_units` en `services/lexicon.py` (cada superficie
  conserva su estado; aditivo en schemas/domain/frontend `types`) ·
  **`support_level` pondera la evidencia de dominio** —
  `SUPPORT_LEVEL_WEIGHTS` (copied .5 / guided .7 / cued .9 / independent 1.0 /
  spontaneous 1.0) en `generalized_mastery_score`, con legacy neutral 1.0.
  Tests: `release-notes-v3.25.1.md` y CHANGELOG `[3.25.1]`.
- ✅ Versión estable `3.25.0` — **Calibración del Student Model: contexto en la
  evidencia, transfer por experiencias y semántica demostrado/estimado** (cierra
  el plan V3.25 del dossier L — auditoría TOTAL verificada de V3.24.0 — que
  absorbe los pendientes F-K3…F-K7): **F1 — modelo de eventos con contexto** —
  `academy_evidence` gana `context_id`/`activity_id`/`task_type`/`support_level`
  (migración idempotente + índice `idx_evidence_context`) y
  `evidence_from_items`/`record_evidence` enriquecen cada evento sin romper
  agregados · **F2 — `support_level` canónico** — enumerados
  `copied/guided/cued/independent/spontaneous` y persistidos por emisor
  (formative → guided/cued; objective assessment → cued; speaking
  assessment/misión y chat libre → independent; read-aloud → guided); el perfil
  expone `support_levels`/`independent_count` por destreza · **F3 — transfer por
  contextos/tareas distintos** — `mastery_evidence_gate`, `adaptive.readiness`,
  el unit gate de `course` y evidence_graph consumen contextos efectivos
  (`effective_evidence_context_count`, con fallback legacy a nº de filas); se
  desambigua `transfer`/`retention` académica vs léxica (F-K5) · **F4 —
  retention longitudinal** — `certification_gate` verifica `created_at` de las
  filas `delayed` (robustez) y emite `retention_report` con intervalos
  D+1/D+3/D+7/D+21 · **F5 — semántica UI demostrado vs estimado** — el Student
  Model separa `demonstrated_level`/`estimated_level`/`level_progress` y el
  header de Progreso los muestra sin ambigüedad (F-K4 parcial: `estimated_band`
  ya existe por destreza) · **F6 — renombrado canónico + unidad léxica** —
  migración idempotente `occurrences→appearances→production_count` y
  `exposures→exposure_count` en toda la pila (DB/schemas/servicios/frontend) y
  columna `lexical_unit` (lema/superficie normalizada) para no tratar
  `go/going/went` como conocimientos independientes (F-K7/P2-01/P2-02); decisión
  `novel` confirmada: reservado hasta emisor real · **F7 — doble vía speaking
  (F-K3)** — `cefr_target` persistido en columna de
  `speaking_mission_sessions` (migración + backfill desde `mission_json`); la
  vía assessment y la misión declaran evidencia `independent`. Tests:
  `release-notes-v3.25.0.md`.
- ✅ Versión estable `3.24.0` — **Calibración de salida del Student Model**
  (cierra el plan V3.24 del dossier K — auditoría profunda Eje 1 sobre v3.23.0 —
  con los dos P1 por decisión del gerente y sus tests e2e previos: **F-K1 —
  MASTERED relajado a lo emisible** — el kind `novel` no tiene emisor real y
  `mastery_evidence_gate` lo exigía (bloqueo permanente de la escalera
  Assessment 2.0): `MASTERY_EVIDENCE_REQUIREMENTS` pasa a `initial 1 +
  practice 2 + transfer 2 + delayed 1` y `novel_required = 0` en las 12 celdas
  macro de `cefr_matrix.json`; `novel` queda **reservado** hasta que exista un
  emisor real; frontera documentada en `ASSESSMENT_2.md` y CONSTITUCIÓN §2.1/§6 ·
  **F-K2 — nivel estimado anclado sin rebase** — `estimated_level` recibe
  `current_level` + `completed_levels` y ancla `numeric` (0.5–6.0) al nivel
  completado más alto + progreso del tramo actual (fin del escenario G4:
  dominar A1 ya no estima B2, aprobar el examen A1 ya no devuelve a Pre-A1);
  `build_student_model` deriva ambos de las matrículas `completed` · **F-K8 —
  tests e2e del salto A1→A2** en `test_academy.py` (dominio A1 → estimado A1,
  nunca ≥ B2; examen A1 → matrícula A2, estimado A1 con numeric 1.0) ·
  **tests**: backend pytest **1457** + ruff limpio; Eje 1 G1 **311** + G2
  **329** (640); frontend sin cambios; `check_release_consistency` 3.24.0
  exit 0). Base: `3.23.0`
- ✅ Versión estable `3.23.0` — **Student Model Calibration (parte 2): Retention
  real y Transfer por contexto** (implementa el plan V3.23 del dossier de la
  auditoría externa V3.22.0: **P1-02 — retention por recuperación DEMORADA** —
  migración idempotente en `vocabulary`: `retrieval_successes`/
  `retrieval_days`/`last_retrieval_at` (sin backfill: ancla retrospectiva
  injusta), `record_retrievals` cuenta éxitos ≥ `RETENTION_MIN_INTERVAL_DAYS`
  tras el ancla `min(first_exposed_at, first_seen)`, hook solo en micro-drill
  (`submit_drill_attempt` si `produced`, `submit_sentence_attempt` si
  `passed`), y la matriz exige `retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS`
  con `spaced_exposure`/`spaced_production` como señales independientes ·
  **P1-04 — transfer por contexto de actividad** — migración `context_tags`
  (CSV `channel:activity` único y ordenado), `record_production(..., activity)`
  con merge canónico, `activity` propagada por todas las superficies
  (`free_chat`/`speaking_assessment`/`speaking_mission`/`speaking_controlled`/
  `writing_controlled`/`speaking_task`/`writing_task`/`read_aloud`/`drill`/
  `speaking_route`/`guided_conversation`), y `production_contexts(row)` con
  fallback `channel:other` para legacy; `transfer`/`transfer_contexts` por
  contextos · **quick fixes base (auditoría externa V3.22)**: P1-01 `item_recall`
  con `_last_activity_at` (max de `last_seen`/`last_exposed_at`); P1-03
  `item_mastery` con pesos de reconocimiento (0.4 volumen / 0.6
  `exposure_days`) y `no_speech` antes que `low_confidence` en el ASR ·
  **tests**: backend pytest **1455** + ruff limpio; frontend vitest **450** (57
  archivos) + `tsc`/`vite build` OK; curriculum `--strict --quality` y content
  validation OK; `check_release_consistency` 3.23.0 exit 0; CONSTITUCIÓN sin
  cambios). Base: `3.22.0`
- ✅ Versión estable `3.22.0` — **ASR Calibration + Student Model (léxico)**
  (implementa el plan V3.22 del dossier de la auditoría externa V3.21.0:
  **ASR-01 — calibración ASR por segmentos** — `aggregate_asr_segments`
  materializa los `Segment` de faster-whisper y agrega `mean_logprob`/
  `min_logprob`/`max_no_speech_prob`/`no_speech_ratio`/`speech_ratio`/
  `compression_ratio`/`segment_count` (V3.21 los leía de `TranscriptionInfo`,
  que no los expone: `no_speech` y `low_confidence` eran inalcanzables);
  `classify_asr_status(*, text, metrics)` con política explícita
  (`MIN_SPEECH_ATTEMPT_SECONDS` 0.5 s; texto vacío con 0 segmentos y audio
  corto → `unintelligible`, con audio ≥ 0.5 s → `no_speech`; texto alucinado
  sobre no-habla — `no_speech_ratio` alto — → `no_speech`; `mean_logprob` bajo
  → `low_confidence`) y telemetría emitida sin clasificar (frontera
  `LANGUAGE_MISMATCH` documentada) · **Student Model léxico (P1-04/05)** —
  migración idempotente `exposure_days`/`first_exposed_at` en `vocabulary`
  (backfill 1 día + `first_exposed_at = last_exposed_at`), `record_exposures`
  cuenta días distintos de exposición y fija el alta, y la matriz
  `item_competence_matrix` **separa Retention de Transfer**: `transfer` =
  producción en ≥ 2 canales (`transfer_contexts`), `retention` = espaciado
  receptivo (`_spaced_exposure`) o productivo (`_spaced_production`);
  `production_gap` (reconocida-nunca-producida, antes `gap`) y `transfer_gap`
  (producida-sin-transferir) independientes en la matriz y el summary; la UI
  del diccionario pasa a 6 contadores · **tests**: backend pytest **1440** +
  integración ASR opt-in (`test_stt_asr_integration.py`, Whisper real) + ruff
  limpio; frontend vitest **450** (57 archivos) + `tsc`/`vite build` OK;
  `check_release_consistency` 3.22.0 exit 0; CONSTITUCIÓN sin cambios). Base:
  `3.21.0`
- ✅ Versión estable `3.21.0` — **Speaking & Evidence Calibration**
  (cierra el plan V3.21 del dossier de la auditoría externa V3.20.0, calibrando
  la verdad del micro-drill y el feedback ASR honesto: **F1 P0 — verdad del
  drill** — la producción se decide por **alineación secuencial**
  (`unit_produced` en `services/phonetics.py`, misma normalización
  `tokenize`, nunca `.split()`): palabra alineada `equal`, frase multi-palabra
  contigua — "get it up" NO es "get up", "my living room is nice" sí produce
  "living room" · las unidades multi-palabra se acreditan a SÍ MISMAS
  (`record_production_text(as_unit=True)`, invariante
  `sum(channel_prod)==appearances` por fila) · **F2 P1 — feedback honesto +
  ASR** — `transcribe_with_timing` captura `no_speech_prob`/`avg_logprob`/
  `language_probability` y clasifica `asr_status ∈ {ok, no_speech,
  unintelligible, low_confidence}`; gating de NO-penalización en drill/
  read-aloud/speaking/pronunciación (`asr_status != ok` → ni KO ni fallo,
  evento `unclear`); chips re-etiquetados ("Reconocida correctamente" no "Bien
  dicha"), mensajes por `asr_status` en las escenas y estado `unclear` en
  manos-libres · **F3 quick wins** — `DEFAULT_MODEL` fuente única
  (`GET /api/models` → `default_model` + `utils/models.ts`
  `resolveDefaultChatModel`, sustituye las 3 constantes), comentario
  `ADMIN_PIN` fail-closed, hook `useRecordingSession` (cronómetro + auto-stop
  120 s) y red de seguridad backend de duración (400), aviso de audio no
  reconocido · **F4 — semántica de superficie Speaking** — títulos por modo
  (Micro-práctica/Acento/Diálogo) y pies de stats con la competencia real
  (Pronunciación/Conversación/Producción oral) · **F5 — matriz de competencia
  léxica** — `item_competence_matrix` pura
  (Recognition/Production/Transfer/Retention/gap por ítem, sin migrar
  columnas), expuesta en el léxico y el diccionario, y **Transfer Gap para
  FSRS** (razón `transfer-gap` en el "why" de cartas lexicon de objetivos con
  producción, `recognition-only` si no) · **F6 — drill escalera MVP** — paso
  **Sentence determinista sin LLM** (`sentence_context_for`: frase del banco de
  read-aloud del nivel que contiene la unidad o plantilla neutra; endpoints
  `GET/POST /api/vocabulary/drill/sentence(-context|-attempt)`, `passed =
  produced AND phrase_ok`) con la UI Recall → Sentence en la misma tarjeta de
  `WordDrill`, y **graduación espaciada** (V20-06: una producción del día no
  elimina de la lista "pendiente"; se sale con 2 días de éxito de drill —
  eventos `drill:<word>[:sentence]:ok` — u otra señal de speaking espaciada;
  sin declarar dominio D5/E3) · F6.3 (Contexto/Transfer libre) queda APLAZADO
  a la auditoría pedagógica de Speaking/Listening · **tests**: backend pytest
  **1424** + ruff limpio; frontend vitest **450** (57 archivos) + `tsc` limpio;
  `check_release_consistency` 3.21.0 exit 0; CONSTITUCIÓN sin cambios). Base:
  `3.20.0`
- ✅ Versión estable `3.20.0` — **Speaking único + feedback oral**
  (cierra el candidato V3.20, definido 2026-09-07 frontend-only, F1 de
  `docs/DISENO-SPEAKING-UNICO.md` + feedback oral: **F1** — consolidación de la
  práctica oral en una sola superficie **Speaking** — hub de APRENDER a 4
  tarjetas, Pronunciation/Conversation reutilizadas como modos internos
  Micro-conversación / Acento / Diálogo guiado (`SpeakingRoutesPractice` +
  `modeTabs` en `QuizRoutePage`, configs exportadas), `/aprender/pronunciacion`
  y `/aprender/conversar` degradan al hub, NextBest/Recorridos navegan a
  Speaking · texto «Cada nivel es una ruta…» plegado tras el botón (i) «Cómo
  funcionan las rutas» · **se reproduce la grabación real del alumno**
  (`RecordingPlayButton`, blob en memoria: el backend solo transcribe) en
  Micro-conversación y Acento · **F3 frontend** — Diálogo guiado con turnos
  hablados reales (`ConversationVoiceButton` + `mode="voice"` + telemetría con
  duración real) · **chips palabra a palabra en Acento**
  (`utils/pronunciationAlignment.ts`, puerto TS del `SequenceMatcher` con
  paridad con el backend) · **F4** — modos por URL + redirección de URLs
  heredadas · **fix** botón traducir del interlocutor y de la respuesta modelo
  en Micro-conversación (pintaba el inglés crudo en vez de `display`) ·
  **tests**: vitest 434 + `tsc`/`vite build` OK; backend sin cambios (impl
  V3.19 sin release previo incluida en este commit) · `check_release_consistency`
  3.20.0 exit 0; CONSTITUCIÓN sin cambios). Base: `3.19.0`
- ✅ Versión estable `3.19.0` — **Léxico por destreza + Speaking micro-drill**
  (cierra el candidato V3.19, definido 2026-09-07: **P0** — la producción del
  alumno se vuelca al léxico etiquetada por destreza — `record_production(user,
  words, channel)` + 4 columnas contadoras en `vocabulary` con backfill
  `chat_prod = appearances` y punto único de captura en `domain/academy.py`
  (CAP-01/REFAC-01); speaking/pronunciación/writing/conversación guiada ya no
  descartan `heard`/`text` · **P1** — speaking micro-drill de 1 nivel honesto:
  candidatos reales `exposures > 0 AND speaking_prod == 0` servidos por
  endpoint determinista y practicados sobre el scorer de pronunciación; sin
  evidence/FSRS (D5/E3); chips del diccionario con acción · **Fixes P1 del
  dossier**: R6-01 retención (409), GATE-01 objetivo locked (409), CLAIM-01
  copy oral "examen estimado", SIGNAL-01, ERR-01 404→503, LIST-01/02/03,
  CONV-01 reconstrucción por `mode` · **Deuda externa**: ADMIN-01 fail-closed y
  BOOL-01 · **tests**: pytest 1371 + ruff limpio, vitest 417 + `tsc`/`vite
  build` OK, `check_release_consistency` 3.19.0 exit 0, curriculum
  `--strict --quality` exit 0; CONSTITUCIÓN sin cambios). Base: `3.18.0`
- ✅ Versión estable `3.18.0` — **Knowledge Graph remainder + deuda del grafo (P3)**
  (cierra el candidato P3, auditado ABIERTO en 2026-09-06. **P3-I2**: ancla de
  unidad congelada al completar — tabla `unit_review_anchors` de escritura única
  (`INSERT OR IGNORE`, backfill lazy) + `build_unit_review_plan(anchor=)`; los
  refuerzos/decay posteriores ya no desplazan las ventanas 7/30/90 · **P3-O1**:
  cascade de ventanas — una ventana sin intento propio se cierra con un intento
  superado de la unidad posterior a su `due_at`; el intento propio manda siempre
  · **P3-M4**: cartas FSRS `objective` fuera del panel autograduable (single
  writer con el micro-review: siembra solo en ventana `due_now`/`failed` o con
  `reps > 0`; `get_fsrs_due` y el `due_count` de resumen las excluyen y
  `/fsrs/review` las rechaza con 400) · **P3-O3**: plan de repaso agregado por
  niveles — `/unit-plan` devuelve `{levels, due_count}` (nivel actual +
  anteriores matriculados), el micro-review acepta `level_id` y valida la unidad
  en el nivel donde vive, `UnitReviewPanel` agrupa por nivel · **P3-H5**: etiquetas
  humanas de las dimensiones del grafo — `GRAPH_DIMENSION_LABELS` + `dimensionLabel`
  en chip de factor limitante/`NextBestCard`/`ObjectiveNodeCard`/`EvidenceGraphPanel`
  (Transfer/Discourse/Interaction, nunca el id en crudo) · **P3-H6**: coste lazy
  de `/session` y `/next-best` — nodos solo para los grupos de remediación que
  pueden convertirse en paso (≤ `SESSION_CAPS.weakness`) y `list_evidence` una
  sola vez y solo si hay nodos que construir (payloads idénticos, sin cambio de
  API) · **P3-auditoría v3.17**: `ObjectiveNodeCard` distingue error real (copia +
  reintento) de 404/sin-datos, `float()` defensivo en `rank_weakness_objectives`,
  spec Playwright `homeGraphChip` nueva con mock determinista (chip "Transfer")
  · **tests**: pytest 1345 + ruff limpio, vitest 414 + build OK, Playwright de la
  región Home/grafo en desktop OK). Base: `3.17.0`
- ✅ Versión estable `3.17.0` — **Knowledge Graph + Daily Adaptive Plan**
  (cierra el candidato P2: el plan diario ahora deriva del Evidence Graph.
  **P0-grafo→plan (D1b)**: `rank_weakness_objectives` + `enrich_item` en
  `services/evidence_graph.py` (puros); `_session_steps` reordena los candidatos
  de cada destreza débil por su nodo y enriquece los pasos con
  `can_do`/`limiting_factor`/`graph_mastery`/`because[]` (una única lectura de
  evidencia; `/session` y `/next-best` nunca divergen) · **P0-vista (D2)**:
  `ObjectiveNodeCard` consume `getEvidenceGraphNode` en el curso (hitos
  expansibles) y en el perfil (Habilidades); sin endpoint nuevo · **P0-muerte
  de `/today` (D3)**: endpoint, `get_today_plan`, schemas, `adaptive.today_plan`
  + `TODAY_MIX`, cliente y tipos frontend eliminados; la Home consume solo
  `/session`; tests migrados con rationale · **P0-deuda v3.16 (D4b)**: M2/M3/O2
  ✅ con test y M1 ✅ en el cierre (devDeps DOM `jsdom` + `@testing-library/react`,
  vitest a `*.test.tsx` y 6 vitest de componente de `UnitReviewPanel`/`TodayPlan`)
  · **P0-UI (D6)**: micro-líneas del can-do/factor limitante en las filas de la
  sesión · **P0-fallback (D7)**: sin nodo la práctica nunca se bloquea
  · **tests**: `test_graph_plan.py` + `test_session_graph.py` nuevos y suites
  migradas; backend pytest 1333 + ruff, frontend vitest 398 + build OK).
  Base: `3.16.0`
- ✅ Versión estable `3.16.0` — **Review/SRS por unidad: micro-review + ventanas de retención fijas 7/30/90 días sobre la base FSRS**
  (cierra el candidato P1 "Review/SRS por unidad" auditado como abierto 2026-09-05:
  el motor FSRS ya soportaba `target_type="objective"` pero no se sembraba; no
  había plan de repaso por unidad ni ventanas fijas. **P0-motor**: nuevo
  `backend/services/unit_review.py` puro y determinista — ventanas `(7, 30, 90)`
  desde el ancla de la unidad (completada = todos sus objetivos `mastered`),
  estados `upcoming/due_now/passed/failed`, micro-review con muestreo
  balanceado de los checks MC **oficiales** del currículo (cero contenido
  artificial; reintento prioriza fallidos) y puntuación en servidor (premisa 21)
  · **P1-siembra**: `sync_fsrs_cards` siembra/refresca cartas `objective` solo
  para objetivos de unidades completadas del nivel actual, sin pisar `reps > 0`
  y sin tocar `TARGET_TYPES`; `why_for_objective` en `fsrs.py` · **P1-datos**:
  tabla idempotente `unit_review_attempts` (`per_objective` + `failed_items`) y
  repos; el micro-review NO crea evidencia de mastery ni declara dominio (D5,
  mecanismos separados E3) · **P2-API**: `GET /api/academy/review/unit-plan` y
  `GET/POST /api/academy/review/unit/{unit_id}/micro-review` con gating de
  ventanas (400/404) · **P2-UI**: `UnitReviewPanel` en INICIO con chips de
  ventana 7/30/90, micro-review por tarjetas y nota honesta "no cuenta como
  demostración de dominio"; lógica pura en `unitReviewLogic.ts` e i18n es/en con
  parity · **tests**: `test_unit_review.py` + `test_unit_review_endpoints.py`
  (siembra, idempotencia, sin `correct_index`, aislamiento entre usuarios),
  vitest de lógica y API; backend pytest 1318 + ruff, frontend vitest 392 +
  build OK). Base: `3.15.0`
- ✅ Versión estable `3.15.0` — **Profundidad avanzada C1/C2: densidad, taxonomía avanzada y banco grammar C2 normalizado**
  (cierra el candidato P0 "C1/C2 depth" auditado como abierto 2026-09-05:
  **P0-contenido**: C1 y C2 pasan de 14 a 20 objetivos con evidencia completa
  (checks MC + activities con fases; +30 activities y +18/+19 checks por nivel),
  en `c1-m02-u01`/`c1-m03-u01` y `c2-m02-u01` (+2 en `l01` "Register shifts" y
  lección nueva `l03` con elipsis/gramática formal), dejando intactos los
  módulos Final · **P0-taxonomía**: `SUBSKILLS` gana la capa avanzada
  (`register`/`pragmatics`/`discourse`/`nuance`/`argumentation`) en speaking/
  listening/writing/grammar/reading/vocabulary y los objetivos C1/C2 se
  re-etiquetan solo donde el contenido lo justifica (C1 3→16 y C2 7→20 con
  subskill avanzada) · **P0-banco**: grammar C2 normalizado a 15 ítems (11 MC +
  4 CP en 3 temas) — deja de ser el único banco corto real y su práctica deja
  de leer `low`; la regla R7 se verifica con banco corto sintético en los tests
  · **tests**: snapshot depth V2.6 reformulado (`depth(C1) 93.1`, `depth(C2)
  92.5` ≥ 90), R7 re-apuntada, conteos C2 actualizados, textos "C2 = 4"
  retirados; `validate_level` vacío en 6 niveles y CLI `--strict --quality`
  exit 0 con unit coverage y loop 100 %). Base: `3.14.0`
- ✅ Versión estable `3.14.0` — **Registro cross-skill de B1 a los 6 niveles (A1–C2): producción controlada en todos los niveles y panel sin marca de prototipo**
  (escala el registro cross-skill por estructura de V3.13 P1.2 del prototipo B1 a
  `a1..c2`: **P0-contenido**: ítems `controlled_production` nuevos en A1 (6:
  `to be`, present simple 3.ª persona, adverbios de frecuencia, `have/has got`,
  preposiciones de lugar, past simple) y C2 (4: inversión enfática, cleft,
  mixed conditional, pasiva formal); el banco Grammar crece (A1 38→44, C2 4→8)
  y C2 conserva su etiqueta honesta de banco corto (≤12) · **P0-motor**:
  `cross_skill.py` generalizado (`CROSS_SKILL_LEVELS = a1..c2`), bindings
  normativos CP → estructura en los seis niveles (`PRODUCTION_BINDINGS_BY_LEVEL`,
  verificado por test: sin CP huérfanos), producción por objetivo agrupando CP ·
  **P1-API**: sin `proto` en esquema/tipos, `/api/cross-skill` valida `a1..c2`
  (400 `cross_skill.level_unknown`) · **P2-UI**: `CrossSkillMatrix` en el panel
  Grammar de cualquier nivel, copia generalizada sin "prototipo B1" y clave
  `crossSkill.protoNote` eliminada de i18n · tests backend por nivel +
  invariantes de contenido A1/C2 + Playwright `grammarRoutesReview` con mock
  determinista). Base: `3.13.0`
- ✅ Versión estable `3.13.0` — **Calibración de evidencia pedagógica: del "¿está implementada la actividad?" al "¿la evidencia demuestra competencia?"**
  (iteración que recalibra el modelo pedagógico en un único documento normativo
  (`docs/CONSTITUCION-PEDAGOGICA.md`) con reglas inmutables R1–R7 y §6.4
  evidence depth. **P0**: `services/evidence_depth.py` clasifica la evidencia en
  LOW/MEDIUM/HIGH contra `cefr_matrix.json` y se expone en `/api/profile`;
  claims honestos —bancos cortos ≤12 checks (Grammar B2/C2) muestran "practice
  coverage · evidence depth LOW" con techo `functional`—; suelo de "demostrado"
  con mínimo de muestras + retención ≥7d + producción en destrezas productivas
  (vocabulary techado en `functional`); `current_level` como sugerencia de
  material con fallback por `review_due`; suite de invariantes pedagógicas.
  **P1**: Grammar en 3 niveles con ítems `controlled_production` (typed answers
  deterministas, A2–C1); cross-skill evidence B1 (matriz por estructura +
  endpoint + panel); golden pedagogical dataset. **P2**: LearnRoutePage
  compartido (QuizRoutePage + routeSession: Grammar/Vocabulary/Pronunciation/
  Conversation/Speaking migradas, ~1.600 líneas menos) y parity i18n
  automática). Base: `3.12.0`
- ✅ Versión estable `3.12.0` — **Grammar por rutas CEFR: página única de checks MC del currículo**
  (APRENDER → Grammar deja el chat del tutor (que sigue en `/chat`) y pasa a una
  página única como el resto: arriba el escenario de práctica —un check MC de
  grammar del currículo del nivel recomendado, con feedback inmediato y la
  respuesta correcta revelada al fallar— y debajo el mapa de rutas A1–C2 con
  anillos y el panel del nivel (Practicar el nivel / Repetir fallidas / Repasar
  aprendidas + «Demostrar el nivel» → exámenes y escalera de evaluaciones del
  curso). El banco son los checks MC de la destreza grammar del currículo
  oficial (97 checks; sin contenido nuevo) sobre el motor compartido
  `backend/services/quiz_routes.py`; los bancos cortos (B2 = 8 y C2 = 4)
  adaptan la puerta automáticamente. Intento determinista persistido en
  `grammar_route_attempts`; endpoints `/api/grammar/routes/*`. La ruta es un
  hito de práctica —`functional` como techo, nunca certifica—; demostrar el
  nivel exige los instrumentos formales del curso. Con Grammar, las 6
  actividades de APRENDER comparten la misma página única de rutas CEFR).
  Base: `3.11.0`
- ✅ Versión estable `3.11.0` — **Vocabulary por rutas CEFR: página única de checks MC del currículo + diccionario a mano**
  (APRENDER → Vocabulary deja de ser solo el diccionario personal y pasa a una
  página única como el resto: arriba el escenario de práctica —un check MC de
  vocabulary del currículo del nivel recomendado, con feedback inmediato y la
  respuesta correcta revelada al fallar— y debajo el mapa de rutas A1–C2 con
  anillos y el panel del nivel (Practicar el nivel / Repetir fallidas / Repasar
  aprendidas + «Demostrar el nivel» → exámenes y escalera de evaluaciones del
  curso). El banco son los checks MC de la destreza vocabulary del currículo
  oficial (sin contenido nuevo) sobre el motor compartido de rutas quiz
  `backend/services/quiz_routes.py` (lo reutilizará Grammar, v3.12); el intento
  es determinista y se persiste en `vocabulary_route_attempts`. La ruta es un
  hito de práctica —`functional` como techo, nunca certifica—; demostrar el
  nivel exige los instrumentos formales del curso. El diccionario personal se
  integra en la página). Base: `3.10.0`
- ✅ Versión estable `3.10.0` — **Conversation por rutas CEFR: página única de mini-diálogos guiados multi-turno**
  (APRENDER → Conversation deja el chat libre (ahora en su propia raíz `/chat`,
  accesible desde la propia página) y pasa a una página única como Speaking:
  el escenario de práctica —un mini-diálogo guiado multi-turno con el tutor:
  situación, roles y metas comunicativas, y se conversa por texto o micrófono
  hasta cumplirlas— vive arriba y, debajo, el mapa de rutas A1–C2 con anillos y
  sus modos (Practicar el nivel / Repetir fallidos / Repasar aprendidos). Banco
  oficial nuevo y auditable `curriculum/conversation_corpus.json` (v1.0.0: 11
  mini-diálogos por nivel) y el intento se evalúa sobre el transcripto completo
  con el pipeline LLM de evidencia (task_type conversation) fusionado con la
  señal objetiva de interacción. La ruta es un hito de práctica —`functional`
  como techo, nunca certifica—; demostrar el nivel sigue siendo del Speaking
  Assessment + evidencia + retención). Base: `3.9.0`
- ✅ Versión estable `3.9.0` — **Pronunciation por rutas CEFR: página única read-aloud con operativa tipo Listening/Speaking**
  (APRENDER → Pronunciation deja la práctica libre de 3 frases hardcodeadas y
  pasa a una página única como Speaking/Listening: la frase modelo a leer en voz
  alta vive arriba —la escuchas con TTS local y te grabas leyéndola— y debajo el
  mapa de rutas A1–C2 con anillos y el panel del nivel (Repetir fallidas /
  Repasar aprendidas / Practicar o repasar el nivel). Banco oficial nuevo y
  auditable `curriculum/pronunciation_corpus.json` (v1.0.0: 20 frases por nivel)
  y la evaluación es determinista y barata: Whisper + `score_pronunciation`
  (score ≥80 = superada), sin LLM por intento. La ruta es un hito de práctica —
  `functional` como techo, nunca certifica—; demostrar el nivel sigue siendo del
  Speaking Assessment + evidencia + retención). Base: `3.8.0`
- ✅ Versión estable `3.8.0` — **Speaking por micro-conversaciones guiadas, con operativa tipo Listening**
  (APRENDER → Speaking es ahora una página única con scroll como Listening: el
  escenario de práctica —tarjeta de micro-conversación guiada con situación, rol
  y línea del interlocutor con voz, a la que respondes hablando— vive arriba y,
  bajo él, el mapa de rutas A1–C2 con anillos y sus modos (practicar el nivel,
  repetir fallidas, repasar aprendidas, añadir práctica extra) más el acceso al
  Speaking Assessment. El banco oficial `speaking_corpus.json` se regenera como
  tarjetas `{setup, you, app_line, model_response}` (v2.0.0: A1 36 / A2 32 / B1
  28 / B2 22 / C1 16 / C2 14) y el intento deja de ser read-aloud: cada respuesta
  se evalúa como respuesta abierta con el pipeline LLM+evidencia existente
  (`extract_speaking_evidence` + `scores_from_evidence`), con error transitorio
  503 si el extractor falla (nunca se puntúa en falso). El audio TTS se sirve por
  tipo con caché (`?kind=opening|model`). La ruta sigue siendo un hito de
  práctica —`functional` como techo, nunca certifica—; demostrar el nivel sigue
  siendo del Speaking Assessment + escenarios/misiones + retención). Base: `3.7.0`
- ✅ Versión estable `3.7.0` — **Speaking por rutas CEFR + fuente compacta en logs del lanzador**
  (APRENDER → Speaking es ahora un mapa de rutas A1–C2 con frases modelo
  read-aloud y banco curado oficial nuevo (`speaking_corpus.json`): practicar el
  nivel, repetir fallidas, repasar aprendidas y añadir práctica extra generada,
  todo puntuado en local sin LLM por intento. La ruta es un hito de práctica —
  `functional` como techo, puerta con cobertura/precisión/checkpoint sobre el
  banco oficial—; demostrar el nivel sigue siendo del Speaking Assessment +
  escenarios/misiones + retención, nunca de la ruta. El lanzador muestra los
  logs con fuente compacta monospace). Base: `3.6.2`
- ✅ Versión estable `3.6.2` — **Estado del servidor en el lanzador + corrección del 429 espurio**
  (el «Demasiadas peticiones» lo devolvía el rate limiter propio
  (`SecurityMiddleware`), no Ollama, cuando el servidor local se saturaba:
  las sondas `/api/health` quedan exentas de cupo y de 429, los topes suben
  para el uso local razonable, cada rechazo queda registrado y visible en el
  nuevo `GET /api/system/status` —generación de práctica extra en curso por
  nivel + rechazos del último minuto—, el mensaje de error 429 se localiza en
  la lengua de la UI (`errors.rateLimited`) y el launcher gana la sección
  «Actividad del servidor» con la píldora de cabecera en ámbar
  («En marcha · generando…» / «saturado») cuando el backend trabaja o
  rechaza). Base: `3.6.1`
- ✅ Versión estable `3.6.1` — **Atajos de APRENDER + coherencia de idioma**
  (la franja superior de cada práctica de APRENDER conserva la flecha al hub y
  añade un atajo directo entre las 6 actividades —Listening/Speaking/
  Pronunciation/Conversation/Vocabulary/Grammar—; los nombres de actividad se
  unifican en inglés en ambos idiomas y se localiza el chrome que se pintaba en
  inglés con la UI en español: tipos de audio y buckets de retención en
  listening, fluidez y avisos de pronunciación, píldoras y estabilidad del plan
  del día, foco/acción de Writing, título/pts de Speaking, PASS/DUE del curso y
  skip-link). Base: `3.6.0`
  — **Listening: práctica ilimitada + repaso por ruta**
  (cada ruta A1..C2 se puede ampliar con práctica generada por IA local —nunca
  contenido oficial: la puerta, el estado functional/demonstrated y el routing
  adaptativo siguen anclados al banco curado, así que añadir extras no revoca ni
  encarece certificar—; el anillo crece con el desglose "oficiales + extra" y
  cada ruta permite "Repasar lo aprendido", no solo las falladas). Base: `3.5.8`
  — **Auditoría de UI: contraste claro/oscuro + QR**
  (QR visible en modo oscuro sobre tarjeta blanca fija, contraste WCAG corregido
  en insignias CEFR, avisos ámbar, fechas/texto tenue y avatar "?" sin perfil; la
  ProfileGate de V3.5.7 se estabiliza en tests visuales con perfil de test
  mockeado). Base: `3.5.0` — **P2 de la Constitución pedagógica en UI**
  (pantallas honestas: la práctica de listening se lee por estado de ruta
  —`functional` es hito de práctica y solo `demonstrated` (puerta + retención
  retardada estable ≥7 días) muestra «A1 Listening — demonstrated»—, todo badge
  de nivel estimado lleva el calificador «estimado · no certificado» y se eliminó
  el código muerto `modeCefrLevel`/`modeCefrBand`; ver `CHANGELOG.md` y
  Constitución §9). Base: `3.4.0` — **P1 de la Constitución pedagógica en código**
  (matriz CEFR a C1/C2 × las 8 destrezas con evidencia por kind, certificación de
  nivel con retención —*completado ≠ certificado*— y Lexical Units con Vocabulary
  Coverage Indicator receptivo/productivo). Base: `3.3.0` — **P0 de la
  Constitución pedagógica en código** (sin
  interpretación palabras→nivel, registro por competencia Estimado/Demostrado con
  `competence_states`, listening como evidencia del Student Model con retención).
  Base: `3.2.1` — **Auditoría pedagógica del modelo de nivelación** (solo
  documentación; ver `docs/audit/H-NIVELACION-PEDAGOGICA.md` y
  `docs/CONSTITUCION-PEDAGOGICA.md`). Base: `3.2.0` — **Calibración pedagógica de
  niveles** (nivel estimado global honesto con `Pre-A1`, Listening como rutas con
  puerta de evidencia y corpus A1/A2 → 200 ítems c/u). Sobre la base de **V3.1 UI**
  (release de interfaz y navegación; ver `docs/UI_V3.1.md`). El stack
  pedagógico previo sigue en `3.0.0` — **V3.0
  Beta freeze** tras el stack pedagógico
  V2.7–V2.12 (Depth → Listening → Speaking Mission → Assessment 2.0 → FSRS →
  Evidence Graph). Gates en `docs/BETA_V3.md` + `docs/BETA_GATES.md`. Base previa:
  **FASE 1–5** de la auditoría externa a V1.29 (LAN/HTTPS/audio móvil):
  **V1.30** LAN + Mobile 100% (mDNS real, test de micrófono con medidor, QR de conexión,
  `/help/connect`), **V1.31** Adaptive Engine 2.0 (Priority Engine + "Why this activity?"),
  **V1.32** Curriculum 2.0 (escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones),
  **V1.33** Listening 2.0 (Listening Resilience + `context` del corpus), **V1.34** Speaking 2.0
  (pronunciation proxy + Interaction Quality + Conversation Endurance), **V1.35** gestión en-app
  de la biblioteca de audio humano (Ajustes → Audio), **V1.36** Audio Corpus 1.0 (corpus de audio
  humano versionado + pipeline de grabación + importación masiva), **V1.37** Audio QA + Content
  Audit (QA acústica + content integrity check + Content Audit Dashboard + candado admin/PIN),
  **V1.38** Course Engine (secuenciación Course→Unit→Lesson→Practice→Review→Assessment con gating
  por objetivo + progreso visible "¿dónde estoy?") y **V1.39** Mastery 2.0 (`MasteryRecord`
  transversal para las 9 destrezas + CEFR readiness con banda cualitativa "B1 developing" en lugar
  de media simple + curva de olvido/review_due conectada a todo el currículo), y **V1.40** Speaking 3.0
  (catálogo de 8 escenarios comunicativos con objetivo comunicativo y métricas declaradas
  task_completion/interaction/fluency/repair/turn_taking + honestidad del proxy de pronunciación en la
  UI: "Confidence: medium · automated proxy"), y **V1.41** Beta Hardening (sin features nuevas: backup
  local completo SQLite+perfil+progreso+evidencia+manifest+WAV+settings con restore/export y
  auto-backup diario "keep 7", endpoints admin con PIN local, middleware de seguridad LAN
  origin-check + rate limiting, panel de backup en Ajustes → Sistema, matriz de dispositivos
  actualizada PC/Android/iPhone/iPad con HTTPS/mDNS/mic/audio/listening/speaking/recovery, a11y
  skip-link + `lang` sincronizado y code-splitting de vendors React/motion/iconos), y **Beta 1.0**
  (5 gates de salida 10/10: Infra/Curriculum/Listening+Speaking/Adaptive+Mastery/UX — ver
  `docs/BETA_GATES.md`). Sobre la base **V1.21**
  (cierre de la auditoría pedagógica A1→B2: corpus de audio humano 1.0 + validación determinista
  audio↔metadata + separación del proxy de pronunciación del audio real + evidencia
  familiar/transfer/novel + Interaction 3.0 + matriz de assessment CEFR; y nueva UI de 3 paneles
  con barra de estado y navegación por destrezas, más el **Learning Home** como pantalla central)
  y **V1.20** (pronunciación fonémica P6, turn-taking real e infraestructura de biblioteca de
  audio humano).
- **V3.2.x (2026-09-03) — Auditoría pedagógica del modelo de nivelación (solo documentación)**:
  dossier desk `docs/audit/H-NIVELACION-PEDAGOGICA.md` (hallazgos H1–H7: palabras→nivel aún en el
  modelo legacy, sin par Estimado/Demostrado, listening sin evidencia en el Student Model, matriz
  CEFR solo hasta B2, retención fuera de la certificación, mastery duplicado, estimado crudo en la
  UI) y especificación normativa **`docs/CONSTITUCION-PEDAGOGICA.md`**: separa Practice Level /
  Mastery / Estimated CEFR / Demonstrated CEFR con 4 estados por competencia
  (NOT STARTED → DEVELOPING → FUNCTIONAL → DEMONSTRATED), define cobertura léxica como indicador
  (no puerta), Lexical Units, progresión de listening y el Mastery Gate general (coverage +
  accuracy + subskills + retención ≥ 7 días + checkpoint). Los incrementos de código derivados
  (P0/P1/P2) quedan priorizados en la sección 9 de la constitución; no se ejecutan en esta iteración.
- ✅ **V2.0 Beta 1.0** (5 gates de salida 10/10), **V2.1 Content** (Content Quality Gate + corpus de
  listening 40→100 + escenarios de speaking 8→20 + niveles C1/C2), **V2.2 Academy/Course Engine**
  (métrica única "TOTAL VALIDATED LEARNING ITEMS" = 143, plantilla fija de 7 secciones por unidad,
  Mastery Gates por unidad, tríada Progress/Mastery/Readiness y pantalla Learning Journey) y
  **V2.3 Personal Dictionary + evidencia por ítem léxico** (siembra de vocabulario/estructuras desde
  el currículo, estado `known`/`learning`/`weak`/`mastered` + `recall` por ítem reutilizando la
  curva de olvido, endpoint `/api/vocabulary/lexicon` y pantalla Personal Dictionary) y
  **V2.4 Curriculum Coverage** (auditoría de cobertura curricular: recorre Pre-A1→C2 × 7 secciones,
  cruza el contenido del curso con los bancos de listening/speaking y genera
  `curriculum_coverage_report.json` con la métrica "TOTAL CURRICULUM COVERAGE", distinta de
  "TOTAL VALIDATED LEARNING ITEMS").
- ✅ **V2.5 Curriculum Completion** (completado; cierra los huecos de la auditoría V2.4). Hecho:
  **C1 listening C1/C2** (corpus 100→140, `c101`–`c140`), **C2 speaking C2** (escenarios 20→26),
  **C3 interaction A1/A2/B2/C1/C2** (subskills `interaction`+`turn_taking` en 39 objetivos,
  TOTAL VALIDATED 143→189, cobertura 37/49→42/49) y **C4 wiring curso↔bancos**
  (`listening_items` + `scenario_ids` por objetivo, 18 objetivos de listening y 50 de speaking
  cableados a los bancos; conteo y validación reflejan las referencias).
- ✅ **V2.6-C1 Capa de medición** (en curso): "cobertura" ≠ "profundidad". Nuevas métricas en
  `services/curriculum_coverage.py`: **UNIT COVERAGE** por unidad, **CEFR DEPTH SCORE** (0..100,
  4 componentes auditables), **UNIT LEARNING LOOP** (9 fases por unidad), drill-down
  LEVEL→UNIT→LESSON→OBJECTIVE y **Curriculum Quality Dashboard** (7 dimensiones + before/after).
  Overall **56,8**; puntos débiles medidos: review/assessment 23,5, listening 47,8 y las fases de
  cierre del loop (retrieve/transfer 0%, assess/review 19,4%). Loop etiquetado por unidad (V2.6-C5:
  50,6% → 84,7%); queda ampliar C1/C2 depth y subir unit coverage.
- ✅ **V2.7 Curriculum Depth (piloto B1)** (hecho). "Cobertura ≠ profundidad" convertido en acción
  con dos hilos: **(1) alineación de medición** — `unit_sections()` cuenta review/assessment por
  marcadores `phase` (consistente con `unit_learning_loop()`), no solo en el módulo Final — y
  **(2) contenido B1 real** — de 10 a 18 objetivos (interaction, listening, speaking y discourse
  markers por unidad, loop cerrado en todas las unidades). Dashboard: Overall **56,8 → 84,0**,
  Depth media 55,7 → 68,0, review/assessment 23,5 → 100, loop 84,7 → 88,4%; **B1 depth 55,7 → 90,4**
  (meta ≥82 cumplida). Plantilla maestra en `docs/UNIT_ARCHITECTURE.md` y briefings de escalado
  `agentes/curriculum/v27-depth-{a2,b2,c1,c2}.md`. Delta en `docs/CURRICULUM_COVERAGE.md`.
- ✅ **V2.7 Curriculum Depth (escalado A2–C2)** (hecho). La plantilla de "Unit Architecture"
  se aplicó al resto de niveles: **A2 11→17 objetivos (depth 60,9→82,6), B2 9→13 (68,4→82,7),
  C1 7→14 (55,5→82,6), C2 5→14 (49,2→82,2)**, cerrando el loop de aprendizaje y añadiendo
  listening/grammar/speaking/interaction por unidad. Dashboard: Overall **84,0 → 94,5**,
  Depth media 68,0 → 84,0, Listening 56,2 → 91,7, Speaking/Interaction 88,9 → 100, loop
  88,4 → 98,7%. Todos los niveles con curso superan depth 80. Queda como hueco real
  **Listening en A1** (5 unidades) → objetivo de V2.8.
- ✅ **V2.8 Listening Curriculum** (hecho). Cierre del listening en **A1** (+5 objetivos,
  loop Final) → **listening por unidad 100%** y **fase `listen` 100%** en todos los
  niveles. Progresión CEFR por subskill (`LISTENING_FOCUS_BY_LEVEL` en
  `services/curriculum.py`): A1 word recognition → A2 information → B1 natural speech
  → B2 inference → C1/C2 nuance/pragmatics. Métrica `listening_curriculum()` (alineación
  foco/subskill **100%** en 38 objetivos). Dashboard: Overall **95,7**, Listening **100%**,
  loop **100%**. Referencia en `docs/LISTENING_CURRICULUM.md`.
- ✅ **V2.9 Speaking Mission Performance** (hecho). Loop
  **Mission → Attempt → Evaluation → Targeted drill → Retry → Improvement**:
  motor puro (`speaking_mission.py`), sesión trazable, API Academy y panel UI.
  Mejora visible (delta overall + por criterio). Referencia en
  `docs/SPEAKING_MISSION.md`.
- ✅ **V2.10 Assessment 2.0** (hecho). Escalera
  **formative → unit → progress → level → retention** + readiness derivado
  y mastery gate (initial/practice/transfer/novel/delayed). Motor
  `assessment_v2.py`, sesiones, API y UI en pestaña Assessment.
  Referencia en `docs/ASSESSMENT_2.md`.
- ✅ **V2.11 SRS / FSRS** (hecho). Scheduler FSRS-lite sobre el Evidence Model:
  cartas skill/lexicon, cola due auditable (What/Why/When/How strong/Last/Next),
  grades Again/Hard/Good/Easy. Referencia en `docs/FSRS.md`.
- ✅ **V2.12 Knowledge / Evidence Graph** (hecho). Can-do → dimensiones →
  limiting factor → mastery; Adaptive Engine con `because[]` estructurado.
  Referencia en `docs/EVIDENCE_GRAPH.md`.
- ✅ **V3.0 Beta freeze** (hecho). Funcionalidad congelada tras V2.7–V2.12;
  fase abierta: contenido + calibración + UX + pruebas reales.
  Gate `scripts/check_beta_v3.py` + `docs/BETA_V3.md`.
- ✅ Diálogo real probado con `qwen3.5:9b`.
- ✅ Documentación (`docs/`, premisas, arquitectura, guía de desarrollo, relevo, changelog).

## Hitos (roadmap)

### M0 — Esqueleto modular  [HECHO ✔]
- Refactor sin cambios de comportamiento: separar backend (`routers/`, `services/`, `schemas/`)
  y frontend (`api/`, `components/`, `hooks/`, `types/`) según `docs/ARQUITECTURA.md`.
- Verificado: backend arranca y responde, frontend compila (`tsc`), chat funciona de punta a punta.
- Subagente (ejecutado por el gerente): `agentes/m0-esqueleto-modular.md`.

### M1 — Streaming de respuestas  [HECHO ✔]
- El texto aparece mientras se genera (SSE/streaming), en vez de esperar la respuesta completa.
- Backend: `POST /api/chat/stream` (SSE). Frontend: `streamChat` consume e incrementa la burbuja.
- Verificado: múltiples `data: {"content":...}` + `data: {"done":true}`; `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m1-backend-streaming.md`, `agentes/m1-frontend-streaming.md`.

### M2 — Voz 100% local  [HECHO ✔]
- **Oído (STT):** voz → texto con **Whisper** (`faster-whisper`, `small`, CPU). ✔
- **Boca (TTS):** texto → voz con **Piper** (`en_US-lessac-medium`, CPU). ✔
- Backend: `POST /api/transcribe` y `POST /api/tts` (modelos en `backend/models/`).
- Frontend: botón micrófono (grabar → transcribir) y altavoz (escuchar respuesta).
- Verificado: TTS genera WAV válido; Whisper transcribe el audio generado correctamente.
- Subagentes (ejecutados por el gerente): `agentes/m2-backend-voz.md`, `agentes/m2-frontend-voz.md`.

### M3 — Memoria e historial  [HECHO ✔]
- Guardar conversaciones, poder retomarlas, contexto persistente.
- Backend: `services/store.py` (SQLite) + CRUD `/api/conversations`.
- Frontend: sidebar con lista de conversaciones, nuevo chat, cargar y eliminar.
- Verificado: crear → guardar → leer → listar → borrar funciona.
- Subagente (ejecutado por el gerente): sin briefing previo; implementación directa del gerente.

### M4 — Modo profesor de inglés  [HECHO ✔]
- **Modos de tutor**: `conversation`, `grammar`, `exercises`, `pronunciation` (system prompts por modo).
- **Corrección de pronunciación**: `POST /api/pronunciation` (audio + texto esperado → score).
- Frontend: selector de modo + tarjeta de práctica de pronunciación (grabar → evaluar).
- Verificado: backend 13 tests, frontend 10 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m4-backend-modo.md`, `agentes/m4-frontend-modo.md`.

### M5 — Modelo conversacional  [HECHO ✔]
- Evaluar cambiar a un modelo no-coder (ej. `llama3.1:8b` o `mistral`) para mejor calidad de tutor.
- Criterio: calidad como profesor (correcciones, explicaciones, tono) + tamaño/VRAM (RTX 4060 Ti 4 GB).
- Entregable: script de evaluación repetible + decisión documentada del modelo por defecto.
- Subagente (ejecutado por el gerente): `agentes/m5-modelo-conversacional.md`.
- **Decisión:** se mantiene **`qwen3.5:9b`** como `DEFAULT_MODEL`. Tras evaluar ambos con
  `scripts/eval_model.py` (4 prompts de tutor), `qwen3.5:9b` gana en calidad como tutor:
  correcciones más estructuradas, ejercicios con contexto y una guía de pronunciación IPA
  mucho más detallada y **correcta**. `llama3.1:8b` es ~6x más rápido (21s vs 125s) pero
  comete un error de pronunciación (confunde la fricativa sorda /θ/ de *through* con la
  sonora /ð/ de *this/that*), así que **no es claramente mejor**. `llama3.1:8b` queda
  instalado como alternativa selectable en el frontend.
- **Descarga desbloqueada:** con VPN iba lenta (~400-900 KB/s) y se atascaba cada ~30 min.
  Al **quitar la VPN** la descarga terminó en ~1 min a 52 MB/s y sin error de certificado
  (el MITM del ISP ya no afectaba a esa conexión). `ollama pull llama3.1:8b` completado.
- **Fix:** `scripts/eval_model.py` ahora fuerza UTF-8 en stdout/stderr (Windows usaba cp1252
  y fallaba al imprimir emojis/símbolos fonéticos).

### M6 — Release a GitHub  [HECHO ✔]
- Repositorio **público**: https://github.com/jvelasca/english-tutor
- V1.0 (tag `v1.0.0`) subida con release e issues de seguimiento.

### M7 — Multi-usuario  [HECHO ✔]
- Perfiles locales con **seguimiento independiente** (conversaciones, progreso, puntuaciones, ajustes).
- Selección simple de perfil al abrir; aislamiento total de datos entre usuarios (premisa 13).
- Backend: tabla `users`, columna `user_id` en `conversations` (migración idempotente no
  destructiva con usuario por defecto `Usuario`), `GET/POST /api/users` y CRUD de
  conversaciones filtrado por `user_id` (query param).
- Frontend: selector de perfil (`UserSelect`) en la cabecera, creación de usuarios, y
  aislamiento al cambiar de perfil (resetea conversación y recarga la lista del nuevo usuario).
- Verificado: backend 20 tests, frontend 14 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m7-backend-multiusuario.md`, `agentes/m7-frontend-multiusuario.md`.

### M8 — Diseño y UX nivel top  [HECHO ✔]
- Rediseño al nivel de apps líderes (ChatGPT/Duolingo): sistema de tokens, tema claro/oscuro,
  responsive, micro-interacciones y estados vacíos/carga/error (premisa 14).
- Sistema de **tokens** en `index.css` (`--color-*`, `--font-*`, `--text-*`, `--space-*`,
  `--radius-*`, `--shadow-*`, motion). Tema **claro/oscuro** (`data-theme`, hook `useTheme`,
  toggle accesible, persistencia en `localStorage`, anti-FOUC en `index.html`).
- **Responsive** (≤768px): sidebar drawer + hamburguesa. **a11y**: `:focus-visible`,
  `aria-*`, `prefers-reduced-motion`.
- Verificado: frontend 19 tests (5 nuevos de tema), `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m8-diseno-ux.md`.

### M9 — Seguimiento de progreso del alumno  [HECHO ✔]
- Registrar el progreso por usuario: nº de ejercicios, correcciones y puntuaciones de
  pronunciación; mostrar un resumen en el frontend (issue #2, pendiente diferido de M4).
- Backend: tabla `pronunciation_attempts` + columna `mode` en `messages` (migración
  idempotente), `GET /api/progress?user_id=<id>` y `POST /api/pronunciation` con `user_id`
  opcional. Frontend: panel `ProgressSummary` + api `progress.ts`.
- Verificado: backend 27 tests, frontend 26 tests, `tsc` sin errores, `npm run build` OK.
- Subagentes (ejecutados por el gerente): `agentes/m9-backend-progreso.md`, `agentes/m9-frontend-progreso.md`.

### M10 — Conversación por voz continua (manos libres)  [HECHO ✔]
- Modo continuo: VAD (detección de silencio vía Web Audio API), transcripción automática y
  respuesta hablada sin pulsar botones (issue #3). Sin cambios de backend
  (transcribe/tts/stream ya existían).
- Frontend: refactor `useChat.sendText(text): Promise<string>`, `utils/vad.ts` (RMS +
  `shouldEndUtterance`), `hooks/useHandsFree.ts` (bucle de estados + VAD por energía),
  `components/HandsFreeToggle.tsx` (toggle + indicador de estado accesible).
- Verificado: frontend 37 tests, `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m10-voz-continua.md`.

### M11 — Lanzador de escritorio + release estable  [HECHO ✔]
- Lanzador de escritorio (`launcher/`, GUI `tkinter` sin dependencias nuevas) que arranca/detiene
  la app (backend + frontend) y muestra el estado de servicios, base de datos y usuarios.
- Acceso directo del escritorio con icono (`launcher/install_shortcut.ps1` + `make_icon.ps1`).
- Versión unificada `1.1.0` (backend `config.py::VERSION` expuesta en `/api/health` y `/`, y
  frontend `package.json`).
- Verificado: launcher 22 tests + ruff limpio; backend 217 tests, frontend 88 tests, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/a1-launcher-core.md`,
  `agentes/endurecimiento/a2-launcher-gui.md`.

### M12 — Release Audit 1.1 + versión 1.1.1  [HECHO ✔]
- Cierre de los 6 puntos señalados por la auditoría externa antes de congelar la arquitectura.
  1. Unificar `current_user` en todos los endpoints sensibles.
  2. Fluidez ya expuesta como `FluencyStats` en `PronunciationResponse` (verificado, sin cambios).
  3. Renombrar "CEFR estimate" → `estimated_level/bands/descriptor`.
  4. Corregir semántica de vocabulario: `occurrences` → `appearances` (+ migración idempotente).
  5. Añadir `confidence`/`source`/`confirmed` a gramática y filtrar el prompt a errores confirmados.
  6. Tests de aislamiento cross-user + tests del Learning Context/Prompt.
- Selector de perfil: no auto-seleccionar el primer usuario si hay varios.
- Versión unificada `1.1.1`.
- Verificado: backend 231 tests, frontend 92 tests, launcher 22 tests, ruff limpio, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/ra-*.md` (RA1–RA7).

### M13 — Etapa 2: Pedagogía (Learning Engine v2)  [EN CURSO]
- Arquitectura congelada; solo se añade rigor pedagógico a lo ya medido (ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`).
- Tracks (un subagente a la vez): P1 política pedagógica formal, P2 error mastery,
  P3 vocabulario exposure/production/mastery, P4 listening como competencia, P5 CEFR basado
  en evidencia, P6 pronunciación fonémica.
- Subagentes (ejecutados por el gerente): `agentes/pedagogia/p-*.md` (P1–P6).

### M14 — Evidence & Performance + Listening + Placement  [HECHO ✔]
- **Evidence & Performance Engine (V1.3)**: ciclo `Evidence → Mastery → Skill Profile →
  Remediación` para speaking, writing y pronunciation (scorer determinista + extracción de
  evidencia con LLM + puente a mastery). CEFR Skill Profile (`/api/academy/profile`) y
  remediación adaptativa (`/api/academy/remediation`); el tutor lee el perfil CEFR.
- **Modelo de olvido (V1.4)**: `services/forgetting.py` (retrieval_probability + `review_due`
  real en función del tiempo).
- **Listening Engine**: sub-destrezas + dificultad + diagnóstico adaptativo
  (`/api/listening/diagnostic`).
- **Placement Engine (V1.5)**: IRT-lite adaptativo (`POST /api/academy/placement/next`).
- Verificado: backend 406 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M15 — Listening 2.0 + Placement 2.0  [HECHO ✔]
- **Listening 2.0 (V1.6)**: audio como entidad de primer nivel (`ListeningAsset` con metadatos
  de audio), vector de dificultad de 8 dimensiones con dificultad derivada por construcción,
  15 sub-destrezas (9 nuevas) y métrica de automaticidad (fluidez procesal).
- **Placement 2.0 (V1.7)**: calibración observacional de ítems (tabla
  `placement_item_calibration` con contadores poblacionales) y perfil **multiskill**
  (θ/nivel/confianza por destreza) sobre el motor IRT-lite/1PL. Endpoint
  `POST /api/academy/placement/profile` y banco de placement ampliado a las 7 destrezas.
- Verificado: backend 480 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M16 — FASE 1–5 de la auditoría externa (LAN/móvil → Speaking 2.0)  [HECHO ✔]
> Ejecutadas **directamente por el gerente** (sin briefings separados); ver `CHANGELOG.md` y
> `docs/RELEVO.md` (sección 37.6–37.11).
- **V1.30 LAN + Mobile 100%**: mDNS real (`local_url_available`), recuperación de permisos de
  micrófono, test de micrófono con medidor, QR de conexión y `/help/connect`.
- **V1.31 Adaptive Engine 2.0**: Priority Engine (`priority_signals`/`priority_score`/
  `explain_priority`) + "Why this activity?" en la tarjeta de siguiente mejor actividad.
- **V1.32 Curriculum 2.0**: escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones
  (`/api/academy/cefr-ladder`).
- **V1.33 Listening 2.0**: Listening Resilience por condición de escucha + `context` del corpus.
- **V1.34 Speaking 2.0**: pronunciation proxy + Interaction Quality por sub-dimensión +
  Conversation Endurance (`/api/academy/speaking/endurance`).
- Verificado: backend 843 tests + ruff limpio; frontend 234 tests + `tsc`/`build` OK; launcher 64
  tests; Playwright 14 passed + 10 skipped.

## Decisiones tomadas

- Hitos M1 y M2 en paralelo (tras M0).
- STT → Whisper (`faster-whisper`). TTS → Piper.
- Ritmo: poco a poco, hito a hito.
- Requisitos nuevos (premisas 13 y 14): **multi-usuario** y **diseño nivel top**. Quedan como M7 y M8.

## Tablero de subagentes

| Subagente | Archivo | Estado |
|---|---|---|
| M0 Esqueleto modular | `agentes/m0-esqueleto-modular.md` | ✔ hecho |
| M1 Backend streaming | `agentes/m1-backend-streaming.md` | ✔ hecho |
| M1 Frontend streaming | `agentes/m1-frontend-streaming.md` | ✔ hecho |
| M2 Backend voz | `agentes/m2-backend-voz.md` | ✔ hecho |
| M2 Frontend voz | `agentes/m2-frontend-voz.md` | ✔ hecho |
| M4 Backend modo profesor | `agentes/m4-backend-modo.md` | ✔ hecho |
| M4 Frontend modo profesor | `agentes/m4-frontend-modo.md` | ✔ hecho |
| M5 Modelo conversacional | `agentes/m5-modelo-conversacional.md` | ✔ hecho |
| M7 Backend multi-usuario | `agentes/m7-backend-multiusuario.md` | ✔ hecho |
| M7 Frontend multi-usuario | `agentes/m7-frontend-multiusuario.md` | ✔ hecho |
| M8 Diseño y UX | `agentes/m8-diseno-ux.md` | ✔ hecho |
| M9 Backend progreso | `agentes/m9-backend-progreso.md` | ✔ hecho |
| M9 Frontend progreso | `agentes/m9-frontend-progreso.md` | ✔ hecho |
| M10 Voz continua | `agentes/m10-voz-continua.md` | ✔ hecho |
| A.1 Launcher núcleo puro | `agentes/endurecimiento/a1-launcher-core.md` | ✔ hecho |
| A.2 Launcher GUI + procesos + atajo | `agentes/endurecimiento/a2-launcher-gui.md` | ✔ hecho |
| RA1–RA7 Release Audit 1.1 | `agentes/endurecimiento/ra-*.md` | ✔ hecho |
| P1 Política pedagógica formal | `agentes/pedagogia/p1-politica-pedagogica.md` | ✔ hecho |
| P2 Error Mastery | `agentes/pedagogia/p2-error-mastery.md` | ✔ hecho |
| P3–P6 Etapa pedagógica | `agentes/pedagogia/p-*.md` | ✔ hecho |
| V1.15 Speaking 3.0 | `agentes/pedagogia/p9-speaking-3.0.md` | ✔ hecho |
| V1.18 P1 listening (retention + dictado/shadowing + variantes) | `agentes/pedagogia/p13-p15.md` | ✔ hecho |
| V1.19 Refresco UI profesional (frontend) | plan Cursor `refresco_ui_profesional` | ✔ hecho |
| V1.21 UI Learning Home (HOME como centro) | plan Cursor `v1.21_ui_learning_home` | ✔ hecho |
| V1.30–V1.34 FASE 1–5 auditoría (LAN/móvil → Speaking 2.0) | directo del gerente (sin briefings) | ✔ hecho |
| V2.7 Depth B1 (piloto) | directo del gerente (plan Cursor `v2.7_curriculum_depth`) | ✔ hecho |
| V2.7 Depth A2 | `agentes/curriculum/v27-depth-a2.md` | ✔ hecho |
| V2.7 Depth B2 | `agentes/curriculum/v27-depth-b2.md` | ✔ hecho |
| V2.7 Depth C1 | `agentes/curriculum/v27-depth-c1.md` | ✔ hecho |
| V2.7 Depth C2 | `agentes/curriculum/v27-depth-c2.md` | ✔ hecho |
| V2.8 Listening Curriculum | directo del gerente | ✔ hecho |
| V2.9 Speaking Mission Performance | directo del gerente | ✔ hecho |
| V2.10 Assessment 2.0 | directo del gerente | ✔ hecho |
| V2.11 SRS / FSRS | directo del gerente | ✔ hecho |
| V2.12 Evidence Graph | directo del gerente | ✔ hecho |
| V3.0 Beta freeze | directo del gerente | ✔ hecho |
| V3.18 Deuda del grafo (P3) | directo del gerente | ✔ hecho |
| V3.19 Léxico por destreza + Speaking micro-drill | directo del gerente (plan Cursor `v3.19_lexico_microdrill`) | ✔ hecho |
| Auditoría profunda V3.18 pre-V3.19 (6 áreas) | `agentes/auditoria-profunda-v318.md` | ✔ hecho (dossier `docs/audit/I-AUDITORIA-PROFUNDA-V318.md`) |
| Auditoría TOTAL externa (v3.18.0) | `agentes/auditoria-total-externa.md` | ⏳ pendiente de ejecutar |

**Regla de proceso (premisa 5 y 12):** todo trabajo se descompone en subagentes
autocontenidos (`agentes/*.md`), vigilando la saturación de contexto de todos los agentes.
Antes de alucinar, se reinicia el contexto apoyándose en `docs/`.

## Siguiente incremento (planificado)

- **⏳ V3.38 — `situación` + planner (Optimal Next Task) (siguiente milestone)**:
  cerradas V3.37 (los peldaños graduados y la automaticidad ya están en el
  ledger) y V3.37.1 (la progresión ya exige consolidación y ya existe regresión
  hacia más apoyo), el siguiente paso es USARLOS para planificar: extender el
  contrato de
  contenido de la caché (`generator_version`, V3.30) para un enunciado
  situacional por palabra — el último peldaño del tramo medio, que exige
  contenido autorado y por eso quedó fuera de V3.37 — y generalizar
  `recommend_review_activity` con retención FSRS + hueco de producción + hueco
  de TRANSFERENCIA por contexto (`context_id`/`activity_id`, ya persistidos
  desde V3.36) + gradiente de apoyo (`support_level`) →
  Optimal Next Task alimentado también por `difficulty`/`response_time_ms`/
  `error_type`. Siguen abiertos, además, los diferidos de V3.30 (consumo de
  `word_breakdown_json` en agregados / práctica dirigida de las falladas y
  palabras tocables en transcripts/chat) y la transferencia por contexto de
  actividad V3.23.

- ~~**⏳ V3.37 — Cues graduados y planner sobre la evidencia**~~ ✅ **cerrado
  (2026-09-10, v3.37.0)**: implementado y publicado (ver «Estado actual» arriba y
  `release-notes-v3.37.0.md`). La escalera graduada
  (`translation < definition < cloze`), la automaticidad espaciada y la cola de
  repaso con `recommended_cue`/`automatic` ya están en producción; `situación` y
  el planner se rebasan a V3.38.

- ~~**⏳ V3.36 — Learning Evidence 2.0**~~ ✅ **cerrado (2026-09-10, v3.36.0)**:
  implementado y publicado (ver «Estado actual» arriba y
  `release-notes-v3.36.0.md`). `support_level`, `difficulty`, `response_time_ms`,
  `error_type`, `context_id`/`activity_id` ya se capturan y agregan. Los cues
  graduados y el planner se rebasan a V3.37.

- ✅ **V3.29 — Listening Engine 4.0 Fase 3 (núcleo) cerrado (2026-09-09,
  v3.29.0)**: implementado (ver "Estado actual" arriba,
  `release-notes-v3.29.0.md`). Núcleo de la Fase 3 de
  `docs/LISTENING_ENGINE_4.0.md` cerrado (alineación por palabra offline
  `word_alignment_proxy`, karaoke, controles precisos, salto a la palabra
  fallada y evidencia `word_breakdown_json`). El diccionario de consulta se
  reprioriza a V3.30 (siguiente candidato).

- ~~**⏳ V3.30 — Diccionario de consulta con marcas de uso y aprendizaje**~~ ✅
  **cerrado (2026-09-09, v3.30.0)**: implementado y publicado (ver «Estado
  actual» arriba, `release-notes-v3.30.0.md` y `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`).
  Quedan abiertos hacia **V3.31** los candidatos que V3.30 había diferido:
  consumo de `word_breakdown_json` en agregados / práctica dirigida de las
  palabras falladas y palabras tocables en transcripts/chat.

- ~~**⏳ V3.30.1 — Endurecimiento del diccionario (auditoría V3.30.0)**~~ ✅
  **cerrado (2026-09-09, v3.30.1)**: implementado y publicado (ver «Estado
  actual» arriba y `release-notes-v3.30.1.md`). Cierra los tres P1 de la
  auditoría (single-flight de generación, política `UNUSABLE_MODELS` frente al
  modelo explícito, caché versionada con `generator_version`) y el P2 del
  parser JSON. **Próximo candidato (rebasado a V3.32 por el cierre de V3.31)**:
  Dictionary → Learning Bridge (borrador en `agentes/v332-dictionary-learning-bridge.md`)
  — convertir la consulta en puerta al aprendizaje con «Practicar» explícito
  sin contaminar evidencia (D3 intacta), más los diferidos de V3.30.

- ~~**⏳ V3.31 — Cierre de la auditoría V3.30.1 (robustez y contrato del
  diccionario)**~~ ✅ **cerrado (2026-09-09, v3.31.0)**: implementado y
  publicado (ver «Estado actual» arriba y `release-notes-v3.31.0.md`). Cierra
  los hallazgos residuales de la auditoría de V3.30.1: cancelación del dueño
  del vuelo sin colgar a los waiters + tope de espera defensivo, invalidación
  del contenido de caché previo a V3.31 (`GENERATOR_VERSION` `1.1.0` + marca
  `DICTIONARY_LEGACY_VERSION` en la migración), tests de la migración de
  upgrade y del path real con modelo no utilizable, y contrato frontend del
  diccionario (tipo `DictionaryLookupRequest`, test del endpoint y timeout de
  cliente). **Próximo candidato V3.32**: Dictionary → Learning Bridge
  (borrador en `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.31.1 — Hardening del diccionario (cierre de la auditoría V3.31.0)**~~ ✅
  **cerrado (2026-09-09, v3.31.1)**: implementado y publicado (ver «Estado
  actual» arriba y `release-notes-v3.31.1.md`). Cierra el P1-01 residual y los
  P2 de robustez del diccionario: `pick_model` con explícito instalado +
  utilizable, negative cache con TTL de generación, rate limit de generación
  nueva por usuario/global y tope servidor del dueño del vuelo (90 s), más la
  semántica documentada del contenido canónico. **Próximo candidato V3.32**:
  Dictionary → Learning Bridge (borrador en
  `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.32 — Dictionary → Learning Bridge (primer eslabón)**~~ ✅ **cerrado
  (2026-09-09, v3.32.0)**: implementado y publicado (ver «Estado actual» arriba
  y `release-notes-v3.32.0.md`). Primer eslabón del puente: «Practicar esta
  palabra» en la tarjeta del lookup reutiliza la escalera de drill existente
  (Recall → Sentence) con evidencia idéntica a practicar fuera del diccionario
  (D3 intacta). Siguiente incremento hacia **V3.33**: los diferidos de V3.30
  (consumo de `word_breakdown_json` en agregados/práctica dirigida de las
  falladas y palabras tocables en transcripts/chat) y los siguientes eslabones
  del puente (escaleras por destreza — reconocimiento MCQ, recall demorado con
  FSRS — y transferencia por contexto, según `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.33 — Recognition (MCQ definición ↔ palabra), eslabón 2 del
  puente**~~ ✅ **cerrado (2026-09-09, v3.33.0)**: implementado y publicado
  (ver «Estado actual» arriba y `release-notes-v3.33.0.md`). Segundo eslabón
  del Dictionary → Learning Bridge: peldaño `1 · Recognize` en la escalera
  compartida con pregunta determinista servida y puntuada por el backend y
  evidencia SOLO informativa. Siguiente incremento hacia **V3.34**: los
  diferidos de V3.30 (consumo de `word_breakdown_json` en agregados/práctica
  dirigida de las falladas y palabras tocables en transcripts/chat) y los
  eslabones restantes del puente — recall demorado con FSRS y transferencia
  por contexto de actividad V3.23 (según `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.34 — Recall 2.0 (recuperación por texto + FSRS), eslabón 3 del
  puente**~~ ✅ **cerrado (2026-09-10, v3.34.0)**: implementado y publicado
  (ver «Estado actual» arriba, `release-notes-v3.34.0.md` y
  `agentes/v334-recall-2.0.md`). El peldaño intermedio del drill pasa a ser
  recuperación real por texto (cue = significado, nunca la palabra): señal de
  recall propia (`recall_successes`/`recall_days` + ledger `recalled`),
  recuperación demorada si supera el intervalo y reprogramación FSRS `lexicon`
  con intervalos reales; la escalera queda `1 · Recognize` · `2 · Recall` ·
  `3 · Sentence`, con el micrófono solo en Sentence. Siguiente incremento hacia
  **V3.35**: los diferidos de V3.30 (consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat), la transferencia por contexto de actividad V3.23 y el
  Lexical Evidence Engine / Evidence Graph como fuente longitudinal.

- ~~**⏳ V3.19 — Léxico por destreza + Speaking micro-drill**~~ ✅ **cerrado
  (2026-09-07, v3.19.0)**: implementado con las decisiones cerradas de diseño
  (ver "Estado actual" arriba, `release-notes-v3.19.0.md` y la entrada 37.37 de
  `docs/RELEVO.md`). Tests: pytest 1371 + ruff limpio, vitest 417 + `tsc`/
  `vite build` OK, `check_release_consistency` 3.19.0 exit 0, curriculum
  `--strict --quality` exit 0; CONSTITUCIÓN sin cambios (R8/R9 propuesta
  abierta). Fuera de alcance de V3.19 (decisión (b)/futura): micro-drill 3
  niveles + integración con el grafo (GRAPH-01), flag de modalidad oral/tecleo,
  WR-UI-01, siembra FSRS sin señal (LEX-03).
- **V3.24 — Calibración de salida del Student Model (diseño cerrado
  2026-09-08)**: alcance decidido por el gerente = los 2 hallazgos **P1** del
  dossier `docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md` + **F-K8** (prerequisito
  de test de F-K2). Decisiones cerradas:
  - **F-K1 (decisión b) — relajar a lo emisible**: `MASTERY_EVIDENCE_REQUIREMENTS`
    queda `familiar×2 + transfer×2 + delayed` (sin `novel`); `novel_required=0`
    en las 12 celdas macro (B2/C1/C2 × listening/speaking/reading/writing) de
    `cefr_matrix.json`; el kind `novel` queda **reservado** y la frontera se
    documenta (sin emisor real, ningún gate debe exigirlo).
  - **F-K2 (decisión a) — anclaje por niveles completados + progreso en el
    tramo actual**: `adaptive.estimated_level` deja de proyectar `1 + 5·overall`
    y pasa a anclar: con niveles completados, el suelo es `CEFR_NUMERIC[mayor
    completado]`; sin completados, el suelo es el centro Pre-A1 (0.5, tramo
    A1) y la etiqueta nunca supera el nivel actual sin certificación previa.
    `build_student_model` pasa `current_level` + `completed_levels`.
  - **F-K8**: tests e2e del salto A1→A2 (premisa 12 del dossier K), escritos
    primero (fallan hoy) y que fijan: (a) dominar A1 no estima ≥ B2; (b) aprobar
    el examen A1 no baja el estimado por debajo de A1.
  El briefing autocontenido (rol/tarea/aceptación) vive en
  `agentes/v324-calibracion-salida.md`. **Todo lo pendiente hacia V3.24 queda
  consolidado en `docs/RELEVO.md` → sección 38** (backlog completo, fronteras y
  primeros pasos). El dossier K supera en contexto al briefing antiguo de
  auditoría TOTAL v3.18 (`agentes/auditoria-total-externa.md`).

