# Briefing — Auditoría TOTAL externa (read-only) de v3.23.0

> Fecha: 2026-09-08 · Rol: **auditor externo read-only** (subagente autocontenido).
> Objetivo: reproducir y verificar las afirmaciones de la posición **v3.23.0** —
> *Student Model Calibration (parte 2): Retention real y Transfer por contexto* —
> y que el cierre no rompe CONSTITUCIÓN, premisas ni mecanismos previos
> (V3.19/V3.20/V3.21/V3.22). Sigue la metodología de las auditorías externas
> v3.16–v3.22 y la plantilla `docs/audit/TEMPLATE.md`.

## 0. Cómo arrancar (auditor, contexto nuevo)

1. Lee en orden: `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`,
   `docs/RELEVO.md` (solo encabezado + secciones 0 y 9), `PLAN.md`
   (estado actual), `README.md`, `CHANGELOG.md`, `release-notes-v3.23.0.md`
   y los dossieres `docs/audit/*.md`.
2. Confirma el punto de partida del repo con:
   ```powershell
   git log --oneline -3
   git status --short          # debe estar limpio (o solo cambios del auditor)
   ```
   La posición es **v3.23.0**, commit de release `f3739a9`
   (`backend/config.py::VERSION = "3.23.0"`, `frontend/package.json` /
   `package-lock.json` idénticos). `git status` limpio.
3. Entorno Windows/PowerShell. Backend: Python en `backend\.venv`. Frontend:
   Node en `frontend`. No instalar dependencias; no modificar código fuera de
   `docs/audit/` si el gerente autoriza el dossier.

## 1. Alcance (TOTAL con foco V3.23)

- **Núcleo v3.23 (plan V3.23 del dossier de la auditoría externa V3.22.0)**:
  - **P1-02 — Retention = recuperación correcta DEMORADA.** Hoy `retention =
    _spaced_exposure(row) or _spaced_production(row)` en
    `item_competence_matrix`: exposición/producción repetida en días distintos
    NO demuestra que se recuerda. V3.23 exige éxito de micro-drill
    (`drill:<word>:ok` / `:sentence:ok`) que ocurre `>= RETENTION_MIN_INTERVAL_DAYS`
    después del ancla. Columnas nuevas en `vocabulary` (migración idempotente,
    sin backfill documentado): `retrieval_successes`, `retrieval_days`,
    `last_retrieval_at`. `_spaced_exposure`/`_spaced_production` pasan a señales
    independientes (`spaced_exposure`/`spaced_production`) que informan pero no
    certifican retención.
  - **P1-04 — Transfer por CONTEXTO de actividad, no solo canal.** Hoy
    `transfer_contexts = nº de canales` (columnas `<channel>_prod`). V3.23
    etiqueta cada producción con `channel:activity` en `context_tags` (columna
    nueva) y deriva `production_contexts(row)`: tags explícitos + fallback
    `channel:other` para filas legacy; `transfer_contexts = len(...)`,
    `transfer = >= 2`. Dos actividades del mismo canal cuentan como contextos
    distintos; `chat` + `conversation` dejan de colapsar.
  - **Quick fixes base (auditoría externa V3.22, incluidos en V3.23):**
    - **P1-01** — `item_recall` usa la actividad MÁS RECIENTE
      (`_last_activity_at` = max de `last_seen`/`last_exposed_at`), no solo
      `last_seen`.
    - **P1-03** — `item_mastery` pondera la señal receptiva con
      `RECOGNITION_VOLUME_WEIGHT` 0.4 / `RECOGNITION_DAYS_WEIGHT` 0.6 sobre
      `exposure_days` (el volumen por sí solo no satura el reconocimiento);
      y `classify_asr_status` comprueba la alucinación de silencio (`no_speech`)
      ANTES que `low_confidence`.
- **Estado global declarado** (`docs/RELEVO.md` encabezado, `CHANGELOG.md`,
  `release-notes-v3.23.0.md`): números de tests, gates, consistencia de versión,
  i18n.
- **NO se audita** (frontera honesta): ejecución física en dispositivos
  (`docs/audit/G-DEVICES.md`), variabilidad LLM con Ollama real
  (`docs/audit/C-SPEAKING-CALIBRATION.md`), calibración con alumnos reales
  (dossieres D/E), telemetría ASR persistente en el Student Model, `support_level`
  por evento (V3.24), backfill de contadores de retrieval histórico (anclas no
  fiables), superficie de "recuerdo de significado" (MC ligado a unidad léxica),
  renombre `appearances → production_count` (deuda documentada V3.22).

## 2. Tarea — batería automática (reproducir, no creer)

Ejecuta cada gate y anota el resultado real. La **cita de comando** queda en el
dossier.

### Backend (`cd backend`)
```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
#   claim: 1455 passed (sin modelos ASR locales: 1453 passed + 2 skipped
#   [integración opt-in test_stt_asr_integration.py])
.venv\Scripts\python.exe -m ruff check .
#   claim: All checks passed!
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict --quality
#   claim: exit 0 (sin huecos empty en niveles con curso)
.venv\Scripts\python.exe -m scripts.content_validation
#   claim: exit 0 (OK=True quality=True)
```

### Raíz
```powershell
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py
#   claim: OK: Release consistency (3.23.0) en todos los orígenes, exit 0
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py
#   claim: OK: Beta V3.0 gate, exit 0
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py
#   claim: exit 0; 0 claves usadas-no-definidas / duplicadas / con en|es vacío
#   (las "sin uso" son candidatas a limpieza, no errores)
```

### Frontend (`cd frontend`)
```powershell
npm test        # claim: vitest 450 passed (57 archivos)
npm run build   # claim: tsc + vite build OK
```

## 3. Verificación de las afirmaciones v3.23 contra el código

Reproduce cada ítem del encabezado de `docs/RELEVO.md` (2026-09-08, 11:15) en el
código y en tests. Guía de localización:

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| **P1-02.1** migración idempotente sin backfill | `backend/repositories/db.py` (ALTER `retrieval_successes`/`retrieval_days`/`last_retrieval_at`/`context_tags`, sin `UPDATE` de contadores) | `test_vocabulary.py` (`test_vocabulary_v323_columns_migration`: columnas presentes, contadores 0, `context_tags` '') |
| **P1-02.2** `record_retrievals` con intervalo y ancla | `repositories/vocabulary.py::record_retrievals` (ancla = `min(first_exposed_at, first_seen)`, `>= RETENTION_MIN_INTERVAL_DAYS`; `retrieval_days` solo si día distinto a `last_retrieval_at`) | `test_vocabulary.py` (`test_record_retrievals_requires_interval_since_anchor`, `test_record_retrievals_dedupe_by_day_and_counts`, `test_record_retrievals_without_anchor_ignored`, `test_record_retrievals_unknown_user_false`) |
| **P1-02.3** hook de retrieval SOLO en micro-drill | `domain/vocabulary.py`: `submit_drill_attempt` (si `produced`) y `submit_sentence_attempt` (si `passed`) invocan `_record_retrieval` tras el volcado `speaking`; sin tocar `learning_events` del router | tests de dominio de drill/sentence en `test_vocabulary.py` |
| **P1-02.4** matriz: retention por recuperación, espaciado independiente | `services/lexicon.py::item_competence_matrix`: `retention = _retrieval_days(row) >= RETENTION_MIN_RETRIEVAL_DAYS`; `spaced_exposure`/`spaced_production` como claves propias; constantes `RETENTION_MIN_INTERVAL_DAYS`/`RETENTION_MIN_RETRIEVAL_DAYS` | `test_lexicon.py` (`test_matrix_spaced_production_is_not_retention`, `test_matrix_spaced_receptive_exposure_is_not_retention`, `test_matrix_retention_requires_delayed_retrieval_days`, `test_matrix_retention_zero_retrieval_days`) |
| **P1-04.1** `context_tags` merge canónico y SELECT | `repositories/vocabulary.py::record_production(..., activity)` (`_merge_context_tag`: único, ordenado `chat→speaking→writing→conversation`), `get_vocabulary` con las 4 columnas nuevas | `test_vocabulary.py` (`test_record_production_context_tags_merge`, `test_record_production_without_activity_keeps_tags`) |
| **P1-04.2** `production_contexts` (tags + fallback legacy) | `services/lexicon.py::production_contexts`: tags explícitos `channel:activity` + fallback `channel:other` solo para canales legacy sin tag (un canal con tag explícito NO recibe `other`); orden `ACTIVITY_CHANNEL_ORDER` | `test_lexicon.py` (`test_production_contexts_explicit_tags_and_fallback`, `test_matrix_transfer_by_two_activities_same_channel`) |
| **P1-04.3** propagación de `activity` por superficies | `domain/academy.py` (7 sitios: `speaking_assessment`/`speaking_mission`/`speaking_controlled`/`writing_controlled`/`speaking_task`/`writing_task`/`read_aloud`), `domain/vocabulary.py` (`free_chat`), `speaking_routes.py` (`speaking_route`), `pronunciation_routes.py` (`read_aloud`), `routers/pronunciation.py` (`drill`), `conversation_routes.py` (`guided_conversation`) | llamadas reales + regresión de endpoints |
| **P1-04.4** `summary` con `spaced_exposure` + `transfer` por contextos | `services/lexicon.py::summary` (contador `spaced_exposure` informativo; `retention` nueva semántica) | `test_lexicon.py::test_summary_counts_matrix_competence` |
| **Quick P1-01** `item_recall` por actividad más reciente | `services/lexicon.py::item_recall` + `_last_activity_at` (max `last_seen`/`last_exposed_at`) | `test_lexicon.py::test_item_recall_uses_most_recent_activity` |
| **Quick P1-03** pesos de reconocimiento y orden ASR | `services/lexicon.py::item_mastery` (`RECOGNITION_VOLUME_WEIGHT` 0.4 / `RECOGNITION_DAYS_WEIGHT` 0.6 sobre `exposure_days`); `services/stt.py::classify_asr_status` (no_speech ANTES de low_confidence) | `test_lexicon.py::test_item_mastery_recognition_requires_spaced_exposure_days`, `test_stt_asr.py` (alucinación de silencio → `no_speech`, no `low_confidence`) |
| **Contratos + UI** | `backend/schemas/vocabulary.py` (`LexicalCompetence` con `spaced_exposure`/`spaced_production`/`retrieval_successes`/`retrieval_days`; `LexiconSummary` con `spaced_exposure`), `frontend/src/types/api.ts`, `frontend/src/utils/i18n.ts` (tooltip) | vitest `PersonalDictionary.test.tsx` + paridad i18n |

**Reglas del juego (premisas):** la lista de candidatas del micro-drill NO
cambia (depende de `exposures`/`speaking_prod`/`ok_days`, no de la matriz);
`test_fsrs_transfer_gap.py` y `services/fsrs.py` (razón `transfer-gap` a nivel de
objetivo) NO se tocan (semántica distinta de la matriz por ítem); micro-drill y
micro-review no declaran dominio (D5/E3); señal ≠ evidencia; `record_retrievals`
es señal pedagógica, nunca evidencia de mastery; invariante de trazabilidad por
fila `sum(channel_prod) == appearances` intacto; `record_production` sin
`activity` conserva los tags existentes (retrocompatibilidad).

## 4. Puntos de atención (comprobar explícitamente)

- **Fronteras del cierre**: `support_level` por evento (V3.24), backfill de
  retrieval histórico, superficie de recuerdo de significado, renombre
  `appearances → production_count`.
- **Árbol git**: limpio en `f3739a9`; `release-notes-v3.23.0.md` versionada;
  `docs/audit/generated/*` al día (i18n regenerado: `defined 1232`).
- **Sin backfill de retrieval**: la migración no inventa evidencia retrospectiva
  (una fila expuesta/producida antes de V3.23 tiene `retrieval_* = 0`).
- **Semántica nueva**: `retention` ya NO es espaciado (receptivo/productivo);
  `spaced_exposure`/`spaced_production` son señales independientes que la UI no
  muestra como chips; `transfer` se mide por contextos `channel:activity`, no por
  canales; una fila legacy sin `context_tags` cae al fallback `channel:other`
  (nunca doble `other` + tag explícito en el mismo canal).
- **Retrocompatibilidad**: `record_words` y callers de `record_production` sin
  `activity` (vía chat) no cambian su semántica y no borran tags existentes.
- **i18n**: parity es/en (checker exit 0; los "sin uso" son candidatas a
  limpieza, no errores).
- Busca **roturas de premisas**: si un hallazgo contradice `PREMISAS.md` o la
  CONSTITUCIÓN, es severidad alta aunque el gate pase.

## 5. Criterios de aceptación del auditor

1. Cada claim de la sección 2 y 3 queda **reproducido** o marcado *no
   reproducible* con su causa (comando + resultado real).
2. Ningún hallazgo de severidad alta sin acción; los medios/bajos quedan
   registrados con recomendación y estado.
3. Veredicto final en formato del proyecto: **APROBADO / APROBADO CON
   OBSERVACIONES / NO APROBADO** + resumen de 2–3 líneas.

## 6. Salida

- Dossier en `docs/audit/` siguiendo `docs/audit/TEMPLATE.md` (alcance, método,
  evidencia, hallazgos, veredicto, "Regenerar / Verificar") — el nombre y la
  consolidación los decide el gerente.
- Informe final con: veredicto, tabla de gates con resultados reales, tabla de
  claims (P1-02/P1-04/quick fixes) con su test de respaldo, y lista de hallazgos.

## 7. Restricciones

- **Solo lectura** en código/BD de producción. No escribir fuera de `docs/audit/`
  si el gerente autoriza el dossier.
- No ejecutar nada que dependa de Ollama/Whisper/Piper salvo que el gerente lo
  pida (los flujos auditados no los requieren; el LLM real es frontera honesta;
  la integración ASR opt-in sí usa Whisper/piper locales si están presentes).
- No instalar dependencias ni lanzar migraciones destructivas. BD de tests =
  temporales (pytest con `tmp_path`).
