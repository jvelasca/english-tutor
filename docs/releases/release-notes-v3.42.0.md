# v3.42.0 — Transferencia contextual real + actividad `spontaneous_use` + gobierno por unidad léxica

**Fase 4 y CIERRE del plan maestro V3.39+ (diccionario reversible → Traductor →
motor de tarea óptima → transferencia real). Release ADITIVA que deja de confundir
dos cosas que el sistema mezclaba: `situation` es recuperación CONTEXTUALIZADA y
transferir es usar la unidad en un contexto DISTINTO del de aprendizaje. Cierra
la modalidad `spontaneous_use` (que se medía pero no tenía tarea), añade la
actividad `transfer` con evidencia por `context_id` y agrega el estado pedagógico
por `lexical_unit` (go/went/gone/going) sin tocar la evidencia por forma. Sin
migración de BD y con contratos HTTP estrictamente aditivos.**

Versión de app `3.41.0 → 3.42.0`. Backend (`services/transfer.py` nuevo,
`services/planner.py`, `services/evidence.py`, `services/lexicon.py`,
`domain/vocabulary.py`, `domain/review.py`, `routers/vocabulary.py`,
`schemas/vocabulary.py`, `schemas/learning.py`) + frontend
(`features/vocabulary/wordDrillSteps.tsx` nuevo,
`features/vocabulary/wordDrill.tsx`, `features/vocabulary/ReviewQueueSection.tsx`,
`api/vocabulary.ts`, `types/api.ts`, i18n) + tests y docs.

## Contexto

La auditoría de V3.38.1 (P1-03) señaló que **completar un hueco no es
transferir**: `situation` es recuperación contextualizada con guía fuerte, y la
transferencia real es usar la unidad por decisión propia en un contexto distinto
del de aprendizaje. Además quedaban dos deudas:

1. **`spontaneous_use` se medía pero no tenía tarea.** El planner podía leer en
   qué modalidad fallaba el ítem, pero no existía ninguna actividad que produjera
   `spontaneous_use`: el hueco no era accionable.
2. **El estado pedagógico se leía por forma superficial.** `go`, `went`, `gone` y
   `going` podían aparecer como cuatro estados independientes aunque fueran la
   misma unidad léxica (irregulares, phrasal verbs, collocations, chunks).
3. **`wordDrill.tsx` acumulaba deuda de tamaño** (ya documentada), lo que hacía
   caro añadir un peldaño nuevo.

```text
Evidencia por contexto (context_id)
→ evidence.context_signals        (contexts / success_contexts / home_context)
→ planner.transfer_gap            (≥ 2 éxitos y < 2 contextos → toca transferir)
→ services.transfer.context_for   (contexto NUEVO determinista, no usado)
→ actividad `transfer`            (evidencia spontaneous_use + context_id)
→ lexical_unit.unit_evidence      (roll-up del estado por unidad)
```

## Qué cambia

### 1. Banco de contextos de transferencia (`services/transfer.py`, nuevo)

- `TRANSFER_CONTEXTS` es un banco curado de consignas genéricas (story, question,
  work, future, opinion, problem) que sirven para CUALQUIER unidad: dan un
  escenario nuevo, nunca la forma esperada (eso sería `sentence`).
- `context_for(word, used_context_ids=())` (pura y determinista) filtra los
  `context_id` que el ítem ya registró y elige por **hash estable** (`zlib.crc32`,
  no el `hash()` de Python, que va sembrado por proceso); si el banco se agota,
  ROTA sobre el completo con `exhausted=True` (nunca deja al alumno sin tarea).
  Acepta tanto un iterable de `context_id` como el mapa `contexts` del resumen.
- `context_id_for(context)` genera el `context_id` del ledger con el prefijo
  `transfer:`.

### 2. Señales de contexto (`services/evidence.py`)

- `context_signals(rows)` (pura, reutilizada tal cual por el resumen SQL: paridad
  por construcción) agrupa el ledger por `context_id` (las filas sin contexto se
  ignoran: no son contexto) y devuelve `contexts`
  (`{context_id: {attempts, successes}}`), `context_attempts`, `success_contexts`
  (contextos con ≥ 1 éxito, orden estable), `home_context` (el de más intentos,
  desempate alfabético) y `transfer` (éxito en ≥ `CONTEXT_TRANSFER_MIN = 2`
  contextos distintos).
- `empty_summary` y `summarize_by_target` incluyen los campos nuevos (aditivos).

### 3. Tarea para `spontaneous_use` (`services/planner.py`, endpoints)

- `transfer_gap(evidence)` decide cuándo pedirla sin adelantarse: exige contexto
  registrado (`context_attempts > 0`), ≥ `TRANSFER_MIN_SUCCESSES = 2` éxitos (un
  solo uso aún se está aprendiendo) y éxito en ≥ 1 contexto pero <
  `TRANSFER_MIN_SUCCESS_CONTEXTS = 2` (aún no hay transferencia demostrada). Sin
  ventana por contexto (resumen parcial) devuelve `False`: no se inventa.
- `has_contextual_transfer(evidence)` (éxito en ≥ 2 contextos) y `transfer_gap`
  entran en `EVIDENCE_REASON_ORDER` como último motivo (tras `error_prone`,
  `skill_gap` y `slow_recall`) y en `planned_signals` (`transfer`,
  `transfer_gap`, `success_contexts`, `home_context`, `context_attempts`).
- `ACTIVITY_FOR_SKILL["spontaneous_use"] = "transfer"` con apoyo `spontaneous`
  (`ACTIVITY_SUPPORT_LEVEL`), de modo que `select_task` ya puede cerrarla.
- `services/lexicon.score_transfer_attempt(word, text)` (puro, sin LLM): mismo
  criterio que `write` (unidad alineada + `WRITE_MIN_WORDS`) mediante el helper
  compartido `_score_production_text`.
- `domain/vocabulary.get_transfer_context` (solo lectura) y
  `submit_transfer_attempt` (acredita la producción y registra la evidencia
  `skill="spontaneous_use"`, `activity_id="drill:transfer"`,
  `support_level="spontaneous"`, `context_id` del contexto NUEVO). Sin
  `context_id` del cliente el servidor lo deriva del banco: el evento nunca queda
  sin contexto.
- Endpoints nuevos `GET /api/vocabulary/drill/transfer-context` y
  `POST /api/vocabulary/drill/transfer-attempt`
  (`TransferContextOut`/`TransferAttemptIn`/`TransferAttemptOut`), con el evento
  `drill:<word>:transfer:<ok|ko>`.

### 4. Gobierno por unidad léxica (`services/lexicon.py`, `domain/review.py`)

- `unit_evidence(rows, evidence_by_word)` (pura y determinista) agrega el estado
  por `lexical_unit`: suma contadores y mapas (`error_types`, `skill_*`), **recalcula**
  `success_rate` del total (nunca media de medias), une `automatic`,
  `automatic_skills` y `success_contexts`, y deriva `transfer`. Cada intento sigue
  registrando su `surface_form`: el roll-up es informativo, no un segundo ledger.
- `GET /api/learning/review` expone `units` (aditivo) y cada `ReviewQueueItem`
  añade `unit_surfaces`, `transfer` y `success_contexts`.
- `ReviewActivity` gana `"transfer"`.

### 5. Descomposición de `wordDrill.tsx` + paso Transfer (frontend)

- Los peldaños presentacionales se extraen a
  `features/vocabulary/wordDrillSteps.tsx` (`RecognitionStep`, `RecallStep`,
  `ProductionTextarea`, `TransferStep`) **sin cambiar el contrato**: `WordDrill`
  sigue siendo el dueño del estado, las llamadas al servidor y la puntuación.
- `DrillStep` gana `transfer`; la escalera pasa a 5 peldaños con etiquetas en un
  mapa declarado (`STEP_LABEL_KEY`). El paso Transfer carga la consigna
  (`getDrillTransferContext`), la muestra con un textarea
  (`submitDrillTransferAttempt` con el `context_id` servido y latencia) y da
  feedback propio: el acierto dispara `onProduced` y el fallo distingue "no usaste
  la palabra" de "demasiado corto".
- `ReviewQueueSection` muestra la actividad `transfer` con la palabra como
  RECURSO (`showsWord(activity)` unifica recognition/write/transfer) y abre el
  drill en ese peldaño con `initialStep`.
- Claves i18n nuevas con paridad es/en (`dictionary.review.activity.transfer`,
  `dictionary.review.reason.transfer_gap`, `dictionary.review.hidden.write|transfer`
  y `dictionary.drill.stepTransfer`/`transfer*`).

## Compatibilidad

| Elemento | Antes | Ahora |
| --- | --- | --- |
| `ReviewActivity` | {recognition, recall, sentence, write} | + `transfer` |
| Resumen de evidencia | sin contextos | + `contexts`, `context_attempts`, `success_contexts`, `home_context`, `transfer` |
| `ReviewQueueOut` | `due_count`/`items`/`fsrs_version` | + `units` (roll-up por unidad) |
| `ReviewQueueItem` | + `limiting_skill`/`task`/`competence` | + `unit_surfaces`, `transfer`, `success_contexts` |
| Orden de decisión | error_prone → skill_gap → slow_recall | + transfer_gap (último) |
| `ACTIVITY_FOR_SKILL["spontaneous_use"]` | `sentence` | `transfer` |
| `wordDrill.tsx` | 4 peldaños en un solo fichero | 5 peldaños, presentacionales en `wordDrillSteps.tsx` |

Todo es **aditivo**: ningún campo existente cambia de semántica, no hay migración
de BD y la evidencia por forma superficial se conserva intacta.

## Tests

- Backend pytest **1975 passed** (+15): nuevo `test_transfer_v340.py` (banco
  determinista y rotación con banco agotado, tolerancia a entradas no iterables,
  `context_signals` con transferencia a los 2 contextos, `transfer_gap`/
  `has_contextual_transfer` incluyendo el caso "2 éxitos en 1 solo contexto",
  routing de `select_task` a `transfer`, roll-up de `unit_evidence`, endpoints
  GET/POST con evidencia `spontaneous_use` + `context_id`, transferencia real al
  segundo contexto y `units`/`unit_surfaces`/`transfer`/`success_contexts` en la
  cola HTTP). Se ajusta `test_learning_evidence_v336.py` al contrato de
  `empty_summary` con los campos de contexto.
- Frontend vitest **70 ficheros/606 tests** (+4): paso `transfer` en
  `wordDrill.test.tsx` (abre con consigna sin pedir contenido, envía el
  `context_id` y avisa al padre, y no deja enviar sin consigna) y actividad
  `transfer` en `ReviewQueueSection.test.tsx` (revela la palabra y abre el paso).
- `ruff check backend/` limpio, `tsc --noEmit` limpio y
  `check_release_consistency` **3.42.0** exit 0.

## Fuera de alcance

Nada pendiente del plan maestro V3.39+: las cuatro fases (diccionario reversible +
pestaña persistida, Traductor de viaje, motor de tarea óptima y transferencia
contextual real) quedan cerradas.

## CI

- Commit `3522bac4592beffe92df9fae5fbd3cae817fdc28` (tag `v3.42.0`) con el run
  [34540962417](https://github.com/jvelasca/english-tutor/actions/runs/34540962417)
  en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build,
  release consistency, Beta V3.0 gate, content validation, Playwright E2E).
  Este es el commit verde y auditable de la release.
- Ese commit **agrupa las fases 1–4** (v3.39.0 → v3.42.0): el trabajo se
  desarrolló sobre el árbol de trabajo y las tres releases anteriores no
  llegaron a commitearse, así que **no existen estados intermedios auditables**.
  Las notas de cada versión sí están versionadas (`release-notes-v3.39.0.md` …
  `release-notes-v3.42.0.md`), y son la fuente para la auditoría fase a fase.
