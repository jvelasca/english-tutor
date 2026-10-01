# J — Auditoría TOTAL externa (read-only) de v3.23.0

> Fecha: 2026-09-08 · Rol: **auditor externo read-only** (runbook
> `agentes/auditoria-total-externa-v323.md`). Posición auditada: **v3.23.0** —
> *Student Model Calibration (parte 2): Retention real y Transfer por contexto*
> — commit de release `f3739a9` (HEAD del auditor: `fc83e1f`, único cambio
> posterior = briefing de esta auditoría, docs). Método y formato: serie de
> auditorías TOTALES externas v3.16–v3.22 + plantilla `docs/audit/TEMPLATE.md`.
> Veredicto: **APROBADO CON OBSERVACIONES**.

## Alcance

- **Núcleo v3.23 (plan V3.23 del dossier de la auditoría externa V3.22.0)**:
  - **P1-02** — retention = recuperación correcta DEMORADA (éxito de
    micro-drill ≥ `RETENTION_MIN_INTERVAL_DAYS` después del ancla
    `min(first_exposed_at, first_seen)`); columnas `retrieval_successes`/
    `retrieval_days`/`last_retrieval_at` (migración idempotente **sin
    backfill**); `_spaced_exposure`/`_spaced_production` pasan a señales
    independientes que informan pero no certifican.
  - **P1-04** — transfer por CONTEXTO de actividad (`channel:activity` en
    `context_tags`), `production_contexts(row)` con fallback `channel:other`
    para legacy; `transfer_contexts = len(...)`, `transfer = >= 2`.
  - **Quick fixes base (auditoría externa V3.22)**: P1-01 `item_recall` por
    actividad MÁS RECIENTE (`_last_activity_at`); P1-03 `item_mastery` con
    pesos `RECOGNITION_VOLUME_WEIGHT` 0.4 / `RECOGNITION_DAYS_WEIGHT` 0.6
    sobre `exposure_days` y `classify_asr_status` con `no_speech` (alucinación
    de silencio) ANTES de `low_confidence`.
  - **Contratos + UI**: `LexicalCompetence`/`LexiconSummary` (schemas +
    `frontend/src/types/api.ts`), tooltip del diccionario
    (`frontend/src/utils/i18n.ts`), mock de `PersonalDictionary.test.tsx`.
  - **Estado global declarado**: `docs/RELEVO.md` (2026-09-08 11:15),
    `CHANGELOG.md`, `release-notes-v3.23.0.md`, `PLAN.md`.
- **Qué NO se audita** (fronteras honestas del cierre, se comprueban solo como
  ausencia): ejecución física en dispositivos (`docs/audit/G-DEVICES.md`),
  variabilidad LLM con Ollama real (`docs/audit/C-SPEAKING-CALIBRATION.md`),
  calibración con alumnos reales, telemetría ASR persistente en el Student
  Model, `support_level` por evento (V3.24), backfill de retrieval histórico
  (anclas pre-V3.22 no fiables), superficie de "recuerdo de significado",
  renombre `appearances → production_count`.

## Método

1. **Lectura previa (orden del briefing §0)**: `docs/PREMISAS.md`,
   `docs/CONSTITUCION-PEDAGOGICA.md`, `docs/RELEVO.md` (encabezado + §0 + §9),
   `PLAN.md`, `README.md`, `CHANGELOG.md`, `release-notes-v3.23.0.md`,
   dossieres `docs/audit/*.md` y plantilla `docs/audit/TEMPLATE.md`.
2. **Punto de partida**: `git log --oneline -3` → HEAD `fc83e1f` (briefing
   docs) sobre release `f3739a9` (v3.23.0); `git status --short` → **limpio**
   (también verificado limpio al terminar los gates).
3. **Batería automática**: se ejecutaron los 9 gates de la sección 2 del
   briefing tal cual (cita de comando en la tabla de evidencia); no se creyó
   ningún claim.
4. **Verificación por claim (sección 3 del briefing)**: localización
   `archivo:línea`, confirmación del test que fija cada comportamiento y
   comprobación de que pasa dentro de la suite reproducida.
5. **Puntos de atención (sección 4)** verificados explícitamente: ausencia de
   backfill, semántica nueva de retention/transfer, retrocompatibilidad,
   invariante por fila, fronteras y no-rotura de premisas/CONSTITUCIÓN.
6. Sin instalación de dependencias, sin ejecución de Ollama/Whisper/Piper
   fuera de lo que pytest opt-in ya usa, sin modificaciones de código o BD de
   producción. Única escritura: este dossier en `docs/audit/`.

## Evidencia — Gates (resultados reales reproducidos)

| # | Gate (comando) | Resultado real | Claim del briefing | Veredicto |
|---|---|---|---|---|
| G1 | `cd backend; .venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider` | `1455 passed, 1 warning in 100.25s (0:01:40)` — exit 0, **0 skipped** (los 2 tests opt-in de `test_stt_asr_integration.py` corrieron: modelos Whisper/piper locales presentes) | 1455 passed (o 1453+2 skip si faltan modelos locales) | ✔ reproducido |
| G2 | `.venv\Scripts\python.exe -m ruff check .` | `All checks passed!` — exit 0 | ruff limpio | ✔ reproducido |
| G3 | `.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict --quality` | `Sin huecos \`empty\` en niveles con curso.` — exit 0 (overall 96.2; unit loop 100 %; listening 100 %) | exit 0 | ✔ reproducido |
| G4 | `.venv\Scripts\python.exe -m scripts.content_validation` | `OK=True quality=True` (513 ítems listening; 14/14 `[PASS]`) — exit 0 | exit 0 (OK=True quality=True) | ✔ reproducido |
| G5 | `backend\.venv\Scripts\python.exe scripts\check_release_consistency.py` | `OK: Release consistency (3.23.0) en todos los orígenes` — exit 0 (`config.py::VERSION`, `package.json`, `package-lock.json`) | 3.23.0 exit 0 | ✔ reproducido |
| G6 | `backend\.venv\Scripts\python.exe scripts\check_beta_v3.py` | `OK: Beta V3.0 gate (feature freeze pedagógico V2.7–V2.12)` — exit 0 | exit 0 | ✔ reproducido |
| G7 | `backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py` | STRINGS definidas **1232**; usadas-no-definidas **0**; duplicadas **0**; en/es vacío **0**; sin uso 190 (candidatas a limpieza, no fallan) — exit 0 | exit 0 | ✔ reproducido |
| G8 | `cd frontend; npm test` | `Test Files 57 passed (57)` · `Tests 450 passed (450)` — exit 0 | vitest 450 (57 archivos) | ✔ reproducido |
| G9 | `npm run build` | `tsc && vite build` OK — `✓ built in 2.94s` — exit 0 | tsc + vite build OK | ✔ reproducido |

## Claims verificados contra el código (sección 3 del briefing)

| Claim | Evidencia de código | Test que lo fija (pasa en G1) | Resultado |
|---|---|---|---|
| **P1-02.1** migración idempotente sin backfill | `backend/repositories/db.py:658-695` — ALTER `retrieval_successes`/`retrieval_days`/`last_retrieval_at`/`context_tags` con comentario de no-backfill; ningún `UPDATE` de contadores retrieval/context_tags | `backend/tests/test_vocabulary.py::test_vocabulary_v323_columns_migration` (línea 526: columnas presentes, contadores 0, `context_tags` '' tras migrar BD previa) | ✔ reproducido |
| **P1-02.2** `record_retrievals` con intervalo y ancla | `backend/repositories/vocabulary.py::record_retrievals` (líneas 133-183): ancla `_earliest_day(first_seen, first_exposed_at)` = `min`; requiere `(hoy-ancla).days >= RETENTION_MIN_INTERVAL_DAYS`; `retrieval_successes += 1`; `retrieval_days += 1` solo si día distinto de `last_retrieval_at`; sin ancla/intervalo → ignora en silencio; usuario desconocido → False | `test_vocabulary.py::test_record_retrievals_requires_interval_since_anchor` (461), `::test_record_retrievals_dedupe_by_day_and_counts` (485), `::test_record_retrievals_without_anchor_ignored` (507), `::test_record_retrievals_unknown_user_false` (521) | ✔ reproducido |
| **P1-02.3** hook de retrieval solo en micro-drill | `backend/domain/vocabulary.py::_record_retrieval` (170-186, nunca lanza) invocado en `submit_drill_attempt` si `produced` (218-226) y `submit_sentence_attempt` si `passed` (299-308), tras el volcado `speaking` (`activity="drill"`); sin tocar `learning_events` del router | tests de dominio drill/sentence en `test_vocabulary.py` (flujo de endpoints `test_drill_attempt_endpoint_produces_word` 669 / KO 707) + `test_stt_asr.py::test_drill_attempt_asr_not_ok_never_produces` | ✔ reproducido |
| **P1-02.4** matriz: retention por recuperación, espaciado independiente | `backend/services/lexicon.py::item_competence_matrix` (442-495): `retention = _retrieval_days(row) >= RETENTION_MIN_RETRIEVAL_DAYS`; claves propias `spaced_exposure`/`spaced_production`; constantes en 52-63 (`RECOGNITION_*`, `RETENTION_MIN_INTERVAL_DAYS=1`, `RETENTION_MIN_RETRIEVAL_DAYS=1`) | `test_lexicon.py::test_matrix_spaced_production_is_not_retention` (523), `::test_matrix_spaced_receptive_exposure_is_not_retention` (546), `::test_matrix_retention_requires_delayed_retrieval_days` (567), `::test_matrix_retention_zero_retrieval_days` (589) | ✔ reproducido |
| **P1-04.1** `context_tags` merge canónico y SELECT | `backend/repositories/vocabulary.py::_merge_context_tag` (30-45: único, ordenado por `PRODUCTION_CHANNELS` y actividad) y `record_production(..., activity=None)` (65-123): si `activity` fusiona `f"{channel}:{activity}"`; **sin `activity` conserva `existing_tags`**; `get_vocabulary` SELECT ampliado (252-253) | `test_vocabulary.py::test_record_production_context_tags_merge` (415), `::test_record_production_without_activity_keeps_tags` (450) | ✔ reproducido |
| **P1-04.2** `production_contexts` (tags + fallback legacy) | `backend/services/lexicon.py::production_contexts` (408-439): tags explícitos `channel:activity` + fallback `channel:other` solo para canales con `<channel>_prod>0` sin tag (un canal con tag NO recibe `other`); orden `ACTIVITY_CHANNEL_ORDER` (336-341) + alfabético | `test_lexicon.py::test_production_contexts_explicit_tags_and_fallback` (599), `::test_matrix_transfer_by_two_activities_same_channel` (616) | ✔ reproducido |
| **P1-04.3** propagación de `activity` por superficies | `backend/domain/academy.py` 7 sitios: 964 `speaking_assessment`, 1162 `speaking_mission`, 3056 `speaking_controlled`, 3200 `writing_controlled`, 3144 `speaking_task`, 3254 `read_aloud`, 3315 `writing_task` (helper 456-457); `domain/vocabulary.py:30` `free_chat` y 222/305 `drill`; `domain/speaking_routes.py:332` `speaking_route`; `domain/pronunciation_routes.py:145` `read_aloud`; `routers/pronunciation.py:72` `drill`; `domain/conversation_routes.py:239` `guided_conversation` | llamadas reales (arriba) + regresión de endpoints en la suite (G1) | ✔ reproducido |
| **P1-04.4** `summary` con `spaced_exposure` + `transfer` por contextos | `backend/services/lexicon.py::summary` (515-555): añade `spaced_exposure` (informativo); `retention` con semántica nueva; transfer por contextos | `test_lexicon.py::test_summary_counts_matrix_competence` (650) | ✔ reproducido |
| **Quick P1-01** `item_recall` por actividad más reciente | `backend/services/lexicon.py::item_recall` (287-295) + `_last_activity_at` (260-285): max de `last_seen`/`last_exposed_at` comparando timestamps | `test_lexicon.py::test_item_recall_uses_most_recent_activity` (208) | ✔ reproducido |
| **Quick P1-03** pesos de reconocimiento y orden ASR | `backend/services/lexicon.py::item_mastery` (222-251): `RECOGNITION_VOLUME_WEIGHT` 0.4 / `RECOGNITION_DAYS_WEIGHT` 0.6 sobre `exposure_days`; `backend/services/stt.py::classify_asr_status` (187-241): alucinación de silencio (no-speech dominante) ANTES que `mean_logprob` (`no_speech`, nunca `low_confidence`) | `test_lexicon.py::test_item_mastery_recognition_requires_spaced_exposure_days` (148); `test_stt_asr.py::test_classify_no_speech_beats_low_confidence_on_hallucination` (165) y `::test_classify_low_confidence_without_no_speech_dominance` (191) | ✔ reproducido |
| **Contratos + UI** | `backend/schemas/vocabulary.py::LexicalCompetence` (43-69: `spaced_exposure`/`spaced_production` bool + `retrieval_successes`/`retrieval_days` int, conserva `production_channels`); `LexiconSummary` (101-118: `spaced_exposure`); espejo en `frontend/src/types/api.ts:255-265,348-362`; tooltip en `frontend/src/utils/i18n.ts:300-303` (`dictionary.competenceHint`, en/es) | vitest `PersonalDictionary.test.tsx` (mock con `spaced_exposure`, paridad de tipos) + G7/G8 | ✔ reproducido |

**Reglas del juego (premisas) verificadas**: la lista de candidatas del
micro-drill no cambia — `services/lexicon.py::drill_candidates`/
`_is_pending_drill_candidate` (616-671) depende de `exposures`/
`speaking_prod`/`production_days`/`ok_days`, nunca de la matriz · `fsrs.py`
(razón `transfer-gap`/`recognition-only` por objetivo, líneas 387-399) y
`test_fsrs_transfer_gap.py` NO se tocan en el release (ausentes del diff
`3e2fad2..f3739a9`) · invariante por fila `sum(channel_prod) == appearances`
intacto (test `test_vocabulary.py:347-377`) · `record_production` sin
`activity` conserva tags (`vocabulary.py:103-104,119`) · señal ≠ evidencia
(release-notes y RELEVO: D5/E3; los nuevos contadores no alimentan FSRS ni
mastery — grep de consumo confirma que `retrieval_*`/`context_tags` solo se
usan en repositorio/servicio léxico/schemas y tipos UI).

## Puntos de atención (sección 4 del briefing) — verificación explícita

- **Fronteras del cierre**: `support_level` por evento (V3.24) → **sin
  apariciones** en el código; backfill de retrieval histórico → **sin backfill**
  (`db.py:670-675` documenta la decisión); superficie de recuerdo de significado
  → no añadida; renombre `appearances → production_count` → se mantiene como
  deuda comentada (`lexicon.py:468-472`) sin migración destructiva.
- **Árbol git**: limpio en `f3739a9` y tras reproducir todos los gates (solo
  cambio del auditor = este dossier); `release-notes-v3.23.0.md` versionada;
  `docs/audit/generated/i18n-report.md` al día (**defined 1232**, regeneración
  del checker no produce diff).
- **Sin backfill de retrieval**: comprobado en migración y en el test de
  migración (fila expuesta/producida pre-V3.23 queda `retrieval_* = 0`,
  `context_tags = ''`).
- **Semántica nueva**: `retention` ya no es espaciado (tests 523/546);
  `spaced_exposure`/`spaced_production` son señales independientes que la UI no
  muestra como chips; transfer por contextos (chat+conversation dejan de
  colapsar — fallback/etiquetas); fila legacy sin `context_tags` cae a
  `channel:other` sin doble `other` + tag en el mismo canal.
- **Retrocompatibilidad**: `record_words` y callers sin `activity` no cambian
  semántica ni borran tags (test 450).
- **i18n**: parity en/es verificada por G7 (0 usadas-no-definidas, 0
  duplicadas, 0 vacías).
- **Premisas/CONSTITUCIÓN**: sin roturas. `PREMISAS.md` y
  `CONSTITUCION-PEDAGOGICA.md` no cambian en el release (diff); la retención
  nueva es señal por ítem del Student Model léxico (fuera de la certificación
  R6/§6.3, que sigue intacta vía `assessment_v2`/listening), coherente con
  premisa 21 y D5/E3.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| H1 | baja | Docstrings etiquetan la ponderación de reconocimiento de `item_mastery` como "V3.23 (P1-04)" cuando en `RELEVO`/release notes/PLAN esa quick fix es **P1-03** (P1-04 = transfer por contexto). Solo comentarios: sin impacto funcional ni en tests. | `backend/services/lexicon.py:229-231`; `backend/tests/test_lexicon.py:148-149` | Re-etiquetar ambos docstrings a P1-03 para mantener el trazado claim→código estable entre releases y evitar confusión en futuras auditorías. | abierto |
| H2 | baja | Umbrales `RETENTION_MIN_INTERVAL_DAYS = 1` y `RETENTION_MIN_RETRIEVAL_DAYS = 1` (`services/lexicon.py:62-63`): un éxito de drill al día siguiente del ancla ya acredita `retention` por ítem y la UI muestra el chip "Retention" — semántica mucho más débil que la retención R6/§6.3 de la CONSTITUCIÓN (ventana ≥7 días y ratio estable), que pertenece a la certificación. No es rotura (señal por ítem, no alimenta evidencia/mastery), y el propio código la declara "heurística a calibrar". | `backend/services/lexicon.py:44-63`; `frontend/src/utils/i18n.ts:300-303` (tooltip) | Documentar en la CONSTITUCIÓN o en la UI que el chip léxico "Retention" es una señal por ítem con intervalo de 1 día, distinta de la retención certificable de §6.3 (≥7 días); calibrar los umbrales cuando haya datos. | abierto |
| H3 | informativa | G7 reporta 190 claves i18n "sin uso" (candidatas a limpieza, no errores por diseño del checker); paridad en/es OK (0 usadas-no-definidas/duplicadas/vacías). | salida de `scripts/check_i18n_coverage.py` + `docs/audit/generated/i18n-report.md` | Mantener la limpieza como deuda de higiene opcional, sin prisa. | aceptado |
| H4 | informativa | pytest emite 1 warning de deprecación upstream (`StarletteDeprecationWarning: httpx con starlette.testclient`; sugiere `httpx2`). No afecta a resultados ni al cierre. | salida de G1 (warnings summary) | Revisar en la siguiente actualización de dependencias (premisa 12: no tocar durante una auditoría read-only). | aceptado |

## Veredicto

**APROBADO CON OBSERVACIONES.** Los 9 gates de la sección 2 se reproducen con
resultados reales idénticos a los claims (pytest backend **1455 passed** —con la
integración ASR opt-in activa, sin skips—, ruff limpio, curriculum
`--strict --quality` y content validation OK, consistencia **3.23.0**, Beta V3.0
OK, i18n parity exit 0 con 1232 definidas, vitest **450 passed / 57 archivos** y
`tsc`+`vite build` OK) y los 11 claims de la sección 3 quedan localizados
`archivo:línea` y fijados por tests que pasan dentro de la suite. No se detecta
ningún hallazgo alto ni medio; las 4 observaciones son de severidad baja o
informativa (docstrings P1-03/P1-04, umbrales de 1 día de la señal léxica a
documentar/calibrar, limpieza i18n, warning de deprecación), sin rotura de
premisas ni de la CONSTITUCIÓN y respetando todas las fronteras del cierre.

## Regenerar / Verificar

```powershell
git log --oneline -3            # HEAD fc83e1f · release v3.23.0 = f3739a9 · limpio
git status --short              # limpio (antes y después de los gates)

# Backend (cd backend)
.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider     # 1455 passed (+2 ASR opt-in activos)
.venv\Scripts\python.exe -m ruff check .                              # All checks passed!
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict --quality   # exit 0
.venv\Scripts\python.exe -m scripts.content_validation                # OK=True quality=True

# Raíz
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py # OK: Release consistency (3.23.0)
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py             # OK: Beta V3.0 gate
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py       # exit 0 (1232 definidas)

# Frontend (cd frontend)
npm test                    # vitest 450 passed (57 archivos)
npm run build               # tsc + vite build OK
```

## Tests que respaldan

- `backend/tests/test_vocabulary.py` — migración V3.23 sin backfill (526),
  `record_retrievals` intervalo/ancla/dedupe/sin ancla/usuario (461-524),
  merge canónico y retrocompatibilidad de `context_tags` (415, 450),
  invariante por fila (347-377), regresión de endpoints de drill (669, 707).
- `backend/tests/test_lexicon.py` — matriz: espaciado ≠ retención (523, 546),
  retención por recuperación (567, 589), contextos y transfer del mismo canal
  (599, 616), `summary` (650), P1-01 recall (208), P1-03 mastery (148).
- `backend/tests/test_stt_asr.py` — orden `no_speech` antes de
  `low_confidence` (149, 165, 191) y gating de no-penalización (230, 323).
- `backend/tests/test_stt_asr_integration.py` — integración opt-in ASR real
  (ejecutada: 0 skips en G1).
- Frontend: `PersonalDictionary.test.tsx` (mock de `LexiconSummary` con los
  campos nuevos); paridad i18n cubierta por G7.
