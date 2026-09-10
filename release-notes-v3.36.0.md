# v3.36.0 — Learning Evidence 2.0: el ledger aprende el CÓMO de cada evento

**El ledger longitudinal `learning_evidence` deja de saber solo QUÉ se recuperó y
CUÁNDO: cada evento declara ahora con cuánto APOYO se produjo (`support_level`),
con qué dificultad de ítem (`difficulty`), en qué contexto y actividad
(`context_id`/`activity_id`), con qué latencia (`response_time_ms`) y —si falló—
con qué tipo de fallo (`error_type`). Migración aditiva e idempotente, contrato
HTTP aditivo, sin cues graduados ni planner (eso es V3.37).**
Versión de app `3.35.1 → 3.36.0`. Backend + frontend + docs; esquema aditivo
(seis columnas nuevas + un índice), contrato HTTP aditivo.

## Contexto

V3.35 convirtió el Evidence Graph en una **historia longitudinal** (cadena
`evento_n → intervalo → evento_{n+1}`) y V3.35.1 blindó esa historia (semántica
del intervalo, cronología, no spoiler, lotes degenerados). Al cerrar la
auditoría quedó claro el hueco siguiente: el ledger registraba el resultado,
pero no el **cómo**. Sin el cómo no se puede distinguir un acierto de pie de un
acierto con traducción delante, ni un fallo por no recordar de un fallo por una
errata — y sin esa distinción el planner del futuro no puede decidir la
siguiente tarea.

## Decisión de alcance: `error_type` es OBSERVACIONAL

La taxonomía de error **no toca el scoring**. `correct` sigue siendo igualdad
estricta de superficie, la evidencia no cambia y FSRS no cambia: una errata
(`beautifull` por `beautiful`) sigue siendo `correct=false` y no acredita
recall. Lo que sí cambia es lo que el sistema **sabe** del intento: el tutor ya
puede distinguir "no lo sabe" de "lo sabe y lo escribió mal" para no volver a
enseñar lo que el alumno domina, sin regalar por error un acierto que no lo es.
Por eso el clasificador es deliberadamente **conservador** en palabras cortas:
en `cat`/`cut` una diferencia de un carácter es otra palabra, no una errata.

## Qué cambia

### 1. Migración aditiva del ledger (`repositories/db.py`)

`learning_evidence` gana seis columnas (idempotente, columna a columna, sin
backfill) y un índice:

| Columna | Tipo | Default | Significado |
|---|---|---|---|
| `support_level` | TEXT | `''` | Eje `copied → guided → cued → independent → spontaneous` (`''` = no declarado) |
| `difficulty` | REAL | `0` | Dificultad del ÍTEM en la escala CEFR 1-6 compartida con listening (`0.0` = no declarada) |
| `response_time_ms` | INTEGER | `NULL` | Latencia del intento (`NULL` = no medida) |
| `error_type` | TEXT | `''` | Clasificación del intento (`''` = no clasificado) |
| `context_id` | TEXT | `''` | Contexto (`lexicon:drill`, `lexicon:chat`, …) |
| `activity_id` | TEXT | `''` | Actividad concreta (`drill:recall`, `drill:word`, `drill:sentence`, `free_chat`, …) |

Índice nuevo: `(user_id, target_type, context_id, activity_id)` para los conteos
de contexto distinto del léxico (mismo eje que usa `academy_evidence`).
El default **no inventa semántica**: `''`/`0`/`NULL` significan "no declarado" y
no entran en los histogramas.

### 2. Capa pura: apoyo y taxonomía de error (`services/evidence.py`)

- `EVIDENCE_SUPPORT_LEVELS`: espejo de `services.academy.SUPPORT_LEVELS` para
  que la capa pura no dependa del servicio de academia (que toca BD). Un **test
  de paridad** garantiza que ambos ejes no divergen.
- `INDEPENDENT_SUPPORT_LEVELS` = `{independent, spontaneous}`: aciertos sin
  apoyo, lo único que podrá pesar en automaticidad.
- `RECALL_ERROR_TYPES` = `correct` / `empty` / `wrong_word` /
  `orthographic_error` / `partial` / `multiple_word_error`.
- `classify_recall_error(expected, given)` (pura y determinista):
  - **errata** (`orthographic_error`) = misma inicial + longitud ≥ 4 +
    distancia de Levenshtein acotada (1-2 según longitud), o la diana entera
    presente con caracteres de más;
  - **parcial** (`partial`) = prefijo de la palabra, comienzo de la unidad
    multi-palabra o recuperación mixta de tokens;
  - **`empty`** = nada escrito; **`wrong_word`** = otra palabra;
  - **`multiple_word_error`** = unidad multi-palabra con tokens equivocados.
- `summarize_evidence` añade `success_rate`, `independent_successes`,
  `support_levels`, `error_types` y `mean_response_time_ms` (ignora los eventos
  sin medida; `None` si ninguno la trae).

### 3. Persistencia y paridad del contrato (`repositories/evidence.py`)

`record_evidence` y `record_evidence_bulk` aceptan y persisten las seis
dimensiones y las devuelven; `list_evidence` las expone; `summarize_by_target`
las agrega en SQL con **paridad exacta** con la versión pura (fijada por test).
El dedupe de V3.35.1 sigue midiéndose por el EVENTO
(`target_type`+`target_id`+`task`+`activity`+`occurred_at`), no por las
dimensiones: repetir la misma entrada no duplica el ledger.

### 4. Captura end-to-end (`domain/vocabulary.py`, `services/lexicon.py`)

| Superficie | `support_level` | `activity_id` | `context_id` |
|---|---|---|---|
| Recall (cue: traducción/definición) | `cued` | `drill:recall` | `lexicon:drill` |
| Drill palabra (repite tras modelo) | `guided` | `drill:word` | `lexicon:drill` |
| Drill frase (repite tras modelo) | `guided` | `drill:sentence` | `lexicon:drill` |
| Producción chat libre | `spontaneous` | actividad declarada | `lexicon:chat` |
| Producción conversación guiada | `guided` | actividad declarada | `lexicon:conversation` |
| Producción speaking/writing | `independent` | actividad declarada | `lexicon:<canal>` |

- `submit_recall_attempt(..., response_time_ms=None)` clasifica el intento y
  declara la dificultad del ítem (`lexicon.cefr_difficulty`: posición CEFR en la
  escala 1-6, `0.0` si no está declarada).
- `_record_retrieval` recibe `activity_id` (palabra vs frase) y convierte la
  duración del cliente a ms con `_duration_ms` (el cliente manda segundos, el
  ledger guarda milisegundos: la unidad de `listening.response_time_ms`, para
  que las latencias sean comparables entre superficies).

### 5. Contrato HTTP (`schemas/vocabulary.py`, `routers/vocabulary.py`)

- `RecallAttemptIn` gana `response_time_ms` (opcional, `ge=0`, `le=600000`);
  un valor negativo se rechaza con **422** en vez de envenenar las medias.
- `RecallAttemptOut` expone `error_type` para el feedback del tutor.
- `LexicalEvidence` amplía `success_rate`, `independent_successes`,
  `support_levels`, `error_types` y `mean_response_time_ms`.

### 6. Frontend (`wordDrill.tsx`, `api/vocabulary.ts`, `types/api.ts`)

El peldaño Recall mide la latencia **cue → envío** con un `ref` que arranca
cuando el cue queda visible (un cue no disponible no produce intento, así que no
produce medida) y la envía como `response_time_ms`; sin medición el campo va a
`null` y el evento se registra igual. Tipos y cliente actualizados (aditivos).

## Verificación

- Backend: `ruff check .` limpio y `pytest` → **1791 passed** (+22 sobre
  v3.35.1), con el nuevo `tests/test_learning_evidence_v336.py`.
- Frontend: `tsc --noEmit` limpio y `vitest` → **65 ficheros/559 tests** (+1).
- `python scripts/check_release_consistency.py` → **3.36.0** exit 0.

## CI

- Commit `d91a637a74678e080478656ed02d7c1e6cd4ba07` con el run
  [34473218199](https://github.com/jvelasca/english-tutor/actions/runs/34473218199)
  en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build,
  release consistency, Beta V3.0 gate, content validation, Playwright E2E).

## Documentación

- `CHANGELOG.md`: entrada `[3.36.0]`.
- `PLAN.md`: hito V3.36 al frente de «Estado actual» y candidato V3.37 (cues
  graduados y planner) en «Siguiente incremento».
- `docs/RELEVO.md`: nota de cierre al frente.

## Fuera de alcance (V3.37)

Escalera de cues graduados (translation → definition → cloze → situación → free
recall), gradiente de apoyo como señal de automaticidad en el scheduler, grafo
de evidencia → estado de conocimiento → retención → hueco de transferencia →
Optimal Next Task, y los diferidos de V3.30 (`word_breakdown_json` en agregados /
práctica dirigida de falladas y palabras tocables en transcripts/chat) junto con
la transferencia por contexto de actividad V3.23 — que ahora sí tiene la pieza
que le faltaba (`context_id`/`activity_id` ya persistidos en el ledger léxico).
