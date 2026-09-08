# Briefing — Auditoría TOTAL externa (read-only) de v3.22.0

> Fecha: 2026-09-08 · Rol: **auditor externo read-only** (subagente autocontenido).
> Objetivo: reproducir y verificar las afirmaciones de la posición **v3.22.0** —
> *ASR Calibration + Student Model (léxico)* — y que el cierre no rompe
> CONSTITUCIÓN, premisas ni mecanismos previos (V3.19/V3.20/V3.21). Sigue la
> metodología de las auditorías externas v3.16–v3.21 y la plantilla
> `docs/audit/TEMPLATE.md`.

## 0. Cómo arrancar (auditor, contexto nuevo)

1. Lee en orden: `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`,
   `docs/RELEVO.md` (solo encabezado + secciones 0 y 9), `PLAN.md`
   (estado actual), `README.md`, `CHANGELOG.md`, `release-notes-v3.22.0.md`
   y los dossieres `docs/audit/*.md`.
2. Confirma el punto de partida del repo con:
   ```powershell
   git log --oneline -3
   git status --short          # debe estar limpio (o solo cambios del auditor)
   ```
   La posición es **v3.22.0**, commit de release `f4b60ce`
   (`backend/config.py::VERSION = "3.22.0"`, `frontend/package.json` /
   `package-lock.json` idénticos). `git status` limpio.
3. Entorno Windows/PowerShell. Backend: Python en `backend\.venv`. Frontend:
   Node en `frontend`. No instalar dependencias; no modificar código fuera de
   `docs/audit/` si el gerente autoriza el dossier.

## 1. Alcance (TOTAL con foco V3.22)

- **Núcleo v3.22 (plan V3.22 del dossier de la auditoría externa V3.21.0)**:
  - **ASR-01 — Calibración ASR por segmentos (P1-01/02/03).** En
    faster-whisper 1.2.1 las métricas de confianza viven en cada `Segment`
    (`avg_logprob`, `no_speech_prob`, `compression_ratio`), no en
    `TranscriptionInfo`. V3.21 las leía con `getattr(info, ...)`: `no_speech`
    era inalcanzable (todo audio vacío → `unintelligible`) y `low_confidence`
    inalcanzable (todo texto → `ok`). V3.22 agrega por segmentos
    (`aggregate_asr_segments`, puro y determinista) y clasifica con la nueva
    firma `classify_asr_status(*, text, metrics)` y política explícita.
  - **P1-04 — Retention ≠ Transfer en la matriz léxica.** Columnas nuevas
    `exposure_days`/`first_exposed_at` (migración idempotente + backfill),
    `record_exposures` cuenta días distintos, `transfer` = producción en ≥ 2
    canales (`transfer_contexts`) y `retention` = espaciado receptivo o
    productivo (`_spaced_exposure`/`_spaced_production`).
  - **P1-05 — Gaps independientes.** `production_gap` (reconocida-nunca-
    producida; antes `gap`) y `transfer_gap` (producida-sin-transferir);
    `summary` con 6 contadores; UI del diccionario a 6 chips + copia i18n.
- **Estado global declarado** (`docs/RELEVO.md` encabezado, `CHANGELOG.md`,
  `release-notes-v3.22.0.md`): números de tests, gates, consistencia de versión,
  i18n.
- **NO se audita** (frontera honesta): ejecución física en dispositivos
  (`docs/audit/G-DEVICES.md`), variabilidad LLM con Ollama real
  (`docs/audit/C-SPEAKING-CALIBRATION.md`), calibración con alumnos reales
  (dossieres D/E), telemetría ASR persistente en el Student Model (fuera de
  alcance: se emiten las señales en el dict de `transcribe_with_timing`, sin
  tabla), `LANGUAGE_MISMATCH` como estado ASR (frontera documentada), renombre
  `appearances → production_count` y preparación Recall → Sentence → Context →
  Free Transfer (deuda documentada), el paso Sentence duplicando
  `speaking_prod` (semántica V3.21).

## 2. Tarea — batería automática (reproducir, no creer)

Ejecuta cada gate y anota el resultado real. La **cita de comando** queda en el
dossier. Nota: `test_stt_asr_integration.py` es **opt-in**: con los modelos
Whisper y piper locales (como en la máquina de release) corre; en una máquina
limpia sin modelos se omite con `skip` (no falla).

### Backend (`cd backend`)
```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
#   claim: 1440 passed (con Whisper/piper locales presentes, incluida la
#   integración ASR; sin modelos, 1438 passed + 2 skipped)
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
#   claim: OK: Release consistency (3.22.0) en todos los orígenes, exit 0
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

## 3. Verificación de las afirmaciones v3.22 contra el código

Reproduce cada ítem del encabezado de `docs/RELEVO.md` (2026-09-08) en el
código y en tests. Guía de localización:

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| **ASR-01.1** métricas leídas de `Segment`, no de `info` (materialización obligatoria) | `backend/services/stt.py::transcribe_with_timing` (`list(segments_gen)`) + `aggregate_asr_segments` (media ponderada por duración de segmento, `min_logprob`, `max_no_speech_prob`, `no_speech_ratio`, `speech_ratio`, `compression_ratio`, `segment_count`) | `backend/tests/test_stt_asr.py` (sintéticos `aggregate_*`) |
| **ASR-01.2** política de clasificación explícita | `classify_asr_status(*, text, metrics)` con `NO_SPEECH_PROB_THRESHOLD`, `LOW_LOGPROB_THRESHOLD`, `MIN_SPEECH_ATTEMPT_SECONDS`, `NO_SPEECH_RATIO_HALLUCINATION_THRESHOLD` | `test_stt_asr.py` (8 casos puros: silencio largo → `no_speech`, ruido 0 segmentos, intento < 0.5 s → `unintelligible`, voz limpia → `ok`, voz parcial, `low_confidence`, frase correcta/incorrecta → `ok` (el KO lo decide el scorer), alucinación de silencio con texto → `no_speech`) |
| **ASR-01.3** integración opt-in con Whisper real | `test_stt_asr_integration.py` (`skipif not is_ready()`): silencio digital nunca `ok`; voz sintetizada piper → `ok` | `backend/tests/test_stt_asr_integration.py` |
| **ASR-01.4** contrato de salida intacto + telemetría emitida (sin clasificar) | dict de `transcribe_with_timing`: `text/duration/asr_status/confidence` + aliases `avg_logprob`/`no_speech_prob` + telemetría `segment_count/mean_logprob/min_logprob/max_no_speech_prob/no_speech_ratio/speech_ratio/compression_ratio/language_probability` | consumers de routers (solo `text/duration/asr_status/confidence`); tests de gating HTTP conservados en `test_stt_asr.py` |
| **P1-04.1** migración idempotente + backfill | `backend/repositories/db.py` (ALTER `exposure_days`/`first_exposed_at`, `UPDATE` backfill), `repositories/vocabulary.py::record_exposures` (bucle por fila, suma solo día distinto a `last_exposed_at`, fija `first_exposed_at` en el alta) y `get_vocabulary` (`SELECT` ampliado) | `test_vocabulary.py` (`test_exposure_days_counts_distinct_days`, `test_exposure_days_columns_migration_and_backfill`) |
| **P1-04.2** matriz con dimensiones independientes | `services/lexicon.py::item_competence_matrix`: `transfer = transfer_contexts >= 2` (sin "or spaced"), `retention = _spaced_exposure or _spaced_production` | `test_lexicon.py` (casos de independencia: exposición espaciada sin producción → retention sin transfer; 2 canales mismo día → transfer sin retention; espaciado requiere hueco ≥ 1 día) |
| **P1-05** `production_gap`/`transfer_gap` + summary | `services/lexicon.py::summary` (6 contadores) + `schemas/vocabulary.py::LexicalCompetence`/`LexiconSummary` | `test_lexicon.py::test_summary_counts_matrix_competence`, `test_vocabulary.py::test_lexicon_endpoint_exposes_competence_matrix` |
| **UI 6 chips** + tipos + i18n | `frontend/src/features/vocabulary/PersonalDictionary.tsx`, `frontend/src/types/api.ts` (`LexicalCompetence`, `LexiconSummary`), `frontend/src/utils/i18n.ts` (`dictionary.competenceProductionGap`, hint) | vitest `PersonalDictionary.test.tsx` + paridad i18n |

**Reglas del juego (premisas):** el gating ASR (`asr_status != "ok"`) NO cambia
en ningún router — el cambio de `stt.py` es transparente para drill/read-aloud/
speaking/pronunciación; la lista de candidatas del micro-drill NO depende de la
matriz (`exposures`/`speaking_prod`/`ok_days`), por lo que su lista no cambia;
`test_fsrs_transfer_gap.py` y `services/fsrs.py` (razón `transfer-gap` a nivel de
objetivo) NO se tocan (semántica distinta de la matriz por ítem); micro-drill y
micro-review no declaran dominio (D5/E3); señal ≠ evidencia; toda clasificación
nueva (ASR, matriz) es determinista y con tests puros; invariante de trazabilidad
por fila `sum(channel_prod) == appearances` intacto.

## 4. Puntos de atención (comprobar explícitamente)

- **Fronteras del cierre**: fuera de alcance explícito en el plan (telemetría
  ASR persistente, `LANGUAGE_MISMATCH`, renombre `appearances → production_count`
  y preparación F6.3 Recall → Sentence → Context → Free Transfer, Sentence
  duplicando `speaking_prod`). Deuda de modelo V20-17 resuelta solo en la parte
  de `exposure_days`; el renombre de columnas sigue documentado sin migración
  destructiva.
- **Árbol git**: limpio en `f4b60ce`; `release-notes-v3.22.0.md` versionada;
  `docs/audit/generated/*` al día (i18n regenerado: `defined 1232`).
- **Gating ASR honesto**: con `asr_status != ok` la UI nunca debe mostrar
  "no lo dijiste" en rojo; el evento de actividad debe ser `unclear`, nunca
  `ko`. Verificar además que el silencio/alucinación de silencio no produce KO.
- **Semántica nueva**: `transfer` ya NO incluye producción espaciada en un solo
  canal (ese caso es `retention=True, transfer=False`); `production_gap` es el
  gap que cierra el micro-drill (antes `gap`); `transfer_gap` es
  producida-sin-transferir.
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
  claims (ASR-01 y léxico) con su test de respaldo, y lista de hallazgos.

## 7. Restricciones

- **Solo lectura** en código/BD de producción. No escribir fuera de `docs/audit/`
  si el gerente autoriza el dossier.
- No ejecutar nada que dependa de Ollama/Whisper/Piper salvo que el gerente lo
  pida (los flujos auditados no los requieren; el LLM real es frontera honesta;
  la integración ASR opt-in sí usa Whisper/piper locales si están presentes).
- No instalar dependencias ni lanzar migraciones destructivas. BD de tests =
  temporales (pytest con `tmp_path`).
