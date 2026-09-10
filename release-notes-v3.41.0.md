# v3.41.0 — Motor de tarea óptima por skill + actividad de escritura + señales robustas

**Fase 3 del plan maestro V3.39+ (diccionario reversible → Traductor → motor de
tarea óptima → transferencia real). Release ADITIVA que convierte el planner en
un motor de decisión pedagógica: pasa de "¿qué palabra repaso?" a "¿qué
modalidad limita, qué actividad la cierra y con qué apoyo?". Cierra además el
hueco `spoken ✓ / written ✗`, que desde V3.38 se diagnosticaba pero no era
accionable, con una nueva actividad de ESCRITURA, y robustece las señales del
resumen (recencia de errores, distribución de latencia, automaticidad y orden
cronológico del ledger). Sin migración de BD y con contratos HTTP estrictamente
aditivos.**

Versión de app `3.40.0 → 3.41.0`. Backend (`services/planner.py`,
`services/lexicon.py`, `services/evidence.py`, `services/example_sentences.py`,
`repositories/evidence.py`, `domain/vocabulary.py`, `domain/review.py`,
`routers/vocabulary.py`, `schemas/vocabulary.py`, `schemas/learning.py`) +
frontend (`features/vocabulary/wordDrill.tsx`,
`features/vocabulary/ReviewQueueSection.tsx`, `api/vocabulary.ts`,
`types/api.ts`, i18n) + tests y docs.

## Contexto

V3.38 introdujo el planner (`planned_signals` + `priority_score` +
`evidence_reason`) y V3.38.1 cerró sus P1: la latencia de recall se lee por
modalidad, el hueco parcial `written ✓ / spoken ✗` es accionable y la
automaticidad se segmenta. La auditoría de V3.38.1 dejó dos deudas de fondo:

1. **La decisión estaba mezclada con la puntuación.** `recommend_review_activity`
   mapeaba razón→actividad, pero "¿qué ítem primero?" (prioridad) y "¿qué skill
   limita?" (decisión) no tenían una respuesta única y explícita.
2. **El hueco simétrico era un diagnóstico muerto.** `spoken ✓ / written ✗` se
   exponía en `skill_gaps` pero no existía ninguna actividad que produjera
   `written_production`: el planner no podía cerrarlo.
3. **Las señales medían todo el histórico.** Un `wrong_word` de hace cuarenta
   repasos bloqueaba la automaticidad igual que uno de ayer, la latencia era una
   media que ocultaba la cola lenta y la automaticidad tenía dos definiciones
   (global y por modalidad) que podían divergir.

```text
Evidencia por skill
   → planner.skill_signals      (weakness/support/latency por modalidad)
   → planner.skill_priority     (PRIORITY_WEIGHTS aplicados a esa segmentación)
   → planner.limiting_skill     (argmax con desempate canónico)
   → planner.select_task        (matrix + evidence + signals)
   → {skill, activity, reason, support_level}
   → ReviewQueueItem.task
```

## Qué cambia

### 1. Tarea óptima por skill (`services/planner.py`)

- `skill_priority(signals)` aplica los MISMOS `PRIORITY_WEIGHTS` declarados a las
  señales de cada modalidad (`signals["skills"]`): debilidad, dependencia de
  apoyo y latencia son por modalidad; el olvido y el hueco son del ítem.
- `limiting_skill(signals)` devuelve el argmax con **desempate determinista** por
  el orden canónico `LEXICAL_SKILLS` (recall antes que producción). Sin bloque
  `skills` devuelve `""`; sin evidencia segmentada la decisión cae en `recall`,
  el peldaño por defecto del repaso.
- `select_task(matrix, evidence, signals)` decide con el orden declarado
  `error_prone` → `skill_gap` → `slow_recall` y devuelve `{skill, activity,
  reason, support_level}`. `ACTIVITY_FOR_SKILL` (`recall`→`recall`,
  `spoken_production`→`sentence`, `written_production`→`write`,
  `spontaneous_use`→`sentence` hasta su actividad propia en Fase 4) y
  `ACTIVITY_SUPPORT_LEVEL` declaran el mapeo.
- `evidence_reason` se conserva como **fachada estable** (delega en
  `select_task`): nada se elimina y `priority`/`signals`/`why` conservan su
  semántica.

### 2. Actividad de ESCRITURA que acredita `written_production`

- `services/lexicon.score_write_attempt(word, text)` (puro, sin LLM): el alumno
  escribe una frase PROPIA con la palabra objetivo. Se acredita si la unidad
  queda alineada (`unit_produced`, el mismo tokenizador normalizado que la
  producción oral) y si hay al menos `WRITE_MIN_WORDS = 4` palabras. Taxonomía
  observacional propia (`WRITE_ERROR_TYPES`): `correct`, `empty`,
  `missing_target`, `too_short`.
- **No juzga corrección gramatical**: no hay modelo de lengua local fiable para
  eso y un falso negativo contaminaría el modelo de alumno. Acredita PRODUCCIÓN
  con la palabra, que es lo que cierra la modalidad.
- `domain/vocabulary.submit_write_attempt` puntúa, registra la producción y
  escribe la evidencia (`skill="written_production"`, `activity_id="drill:write"`,
  `support_level="independent"`, latencia medida, `error_type` del intento),
  también en el fallo (`_record_write_evidence`).
- Endpoint nuevo `POST /api/vocabulary/drill/write-attempt`
  (`WriteAttemptIn`/`WriteAttemptOut`) que además registra el evento
  `drill:<word>:write:<ok|ko>`.

### 3. Robustez de señales (`services/evidence.py`, `repositories/evidence.py`)

- `recency_signals(rows, window=RECENT_WINDOW_EVENTS)` (pura): ventana de los 10
  eventos más recientes en orden `(occurred_at, id)` sin mutar la lista del
  llamador, y devuelve `recent_attempts`, `recent_error_rate`,
  `recent_wrong_word`, `median`/`p75`/`p90_response_time_ms` (percentil por
  **rango más cercano**, replicable en SQL sin interpolación),
  `recent_response_time_ms` y `latency_trend` (`recent − histórico`: positivo =
  se está volviendo más lento). La reutiliza tal cual
  `repositories/evidence.summarize_by_target`: **paridad pura↔SQL por
  construcción**, sin un segundo dialecto.
- `_has_grave_error` juzga sobre `recent_wrong_word` (una confusión ya corregida
  no bloquea la automaticidad para siempre) y cae al histórico cuando el resumen
  es parcial; `planner.error_prone` mira la misma ventana.
- `is_automatic` **unifica** las dos definiciones: si el resumen trae segmentación
  por modalidad, el ítem es automático exactamente cuando ALGUNA modalidad lo es
  (`automatic_skills`) — tres éxitos sueltos en tres modalidades ya no declaran
  automático el ítem, cerrando P1-03 también a nivel de ítem. Sin segmentación
  (resúmenes parciales o ledger legacy) mantiene el criterio global de V3.38.1,
  que es el único que esos resúmenes pueden sostener.
- Ledger: `last_evidence_at(..., before=...)` y `record_evidence` anclan
  `interval_since_last_evidence` al evento **cronológicamente anterior**, no al
  último insertado. Con un `occurred_at` externo fuera de orden (importaciones,
  sincronización de otro dispositivo) el intervalo podía salir negativo o
  absurdo. Sin `before` se conserva el comportamiento histórico.
- `example_for_many(words)` (`services/example_sentences.py`) resuelve el ejemplo
  real de VARIAS palabras en una sola pasada al banco de pronunciación,
  preservando la semántica exacta de `example_for` (primera frase del banco en su
  orden; `None` si no hay frase real) y cortando en cuanto todas quedan
  resueltas. `domain/review._available_recall_cues` lo usa para el peldaño
  `cloze` en lugar de pagar un recorrido del banco por palabra.

### 4. Cola y frontend

- `ReviewQueueItem` expone de forma **aditiva** `limiting_skill` y `task`
  (`{skill, activity, reason, support_level}`), de modo que la cola es explicable
  extremo a extremo sin re-derivar nada en el cliente. `ReviewActivity` gana
  `"write"`.
- `wordDrill.tsx` añade el paso `write` (cuarta opción de la escalera): textarea
  para la frase propia, mínimo declarado en la UI, envío por
  `submitDrillWriteAttempt` y feedback que distingue "no usaste la palabra" de
  "frase demasiado corta". Al acreditarse dispara `onProduced` como la
  producción oral.
- `ReviewQueueSection` muestra la actividad `write` (con la palabra como recurso,
  igual que `recognition`) y abre el drill en ese paso con `initialStep`.
- Claves i18n nuevas con paridad es/en.

## Compatibilidad

| Elemento | Antes | Ahora |
| --- | --- | --- |
| `ReviewQueueItem` | `activity` ∈ {recognition, recall, sentence} | + `write`; y campos aditivos `limiting_skill`, `task` |
| Resumen de evidencia | sin ventana de recencia | + `recent_attempts`, `recent_error_rate`, `recent_wrong_word`, `median`/`p75`/`p90_response_time_ms`, `recent_response_time_ms`, `latency_trend` |
| `is_automatic` | contadores globales | unión de `automatic_skills` con segmentación; criterio global como fallback |
| `interval_since_last_evidence` | ancla en el último insertado | ancla en el evento cronológicamente anterior |
| `example_for(word)` | un recorrido del banco por palabra | `example_for_many(words)` (una pasada); `example_for` delega |
| Endpoints | — | + `POST /api/vocabulary/drill/write-attempt` |

Ningún campo existente cambia de semántica y ninguna llamada existente necesita
tocar su payload.

## Tests

- **Backend pytest 1960 passed** (+36).
  - `test_optimal_task_v339.py`: pesos por skill, `limiting_skill` con desempate
  canónico (y `recall` por defecto sin segmentación), orden de razones de
  `select_task`, hueco escrito accionable (actividad `write`,
  `support_level="independent"`) y robustez ante datos parciales; campos
  aditivos de la cola por HTTP.
  - `test_drill_write_v339.py`: scoring (acierto, palabra suelta, sin objetivo,
  unidades multi-palabra), acreditación de `written_production` con la evidencia
  completa (skill, actividad, contexto, apoyo, latencia, `error_type`), el fallo
  también registrado y el cierre del hueco en el planner.
  - `test_evidence_signals_v339.py`: ventana de recencia (incluido el orden
  cronológico frente al de inserción y la no mutación de la lista), percentiles
  por rango más cercano, tendencia de latencia, filas sin medir, fallo grave por
  ventana con fallback histórico, automaticidad unificada, encadenado cronológico
  del ledger con `occurred_at` desordenado, paridad pura↔SQL y batching de
  ejemplos.
  - Ajustes: `test_planner_v338.py` (hueco escrito accionable),
  `test_skill_segmentation_v338.py` (una sola definición de automaticidad) y
  `test_learning_evidence_v336.py` (contrato de `empty_summary`).
- **Frontend vitest 70 ficheros/602 tests** (+5): paso `write` en
  `wordDrill.test.tsx` (abre el paso sin pedir contenido al servidor, acredita y
  no acredita) y actividad `write` en `ReviewQueueSection.test.tsx`.
- `ruff check backend/` limpio, `tsc --noEmit` limpio y
  `python scripts/check_release_consistency.py` → **3.41.0** exit 0.

## Fuera de alcance (Fase 4 del plan maestro)

- Transferencia contextual **real**: contextos A/B/nuevos con evidencia propia
  por `context_id`, con `situation` como *contextualized retrieval* y `transfer`
  como dimensión separada.
- Actividad propia para `spontaneous_use` (hoy se mide y se sirve como
  `sentence`).
- Agregación del estado pedagógico por `lexical_unit` (go/went/gone/going), no
  solo por `surface_form`.
- Descomposición de `frontend/src/features/vocabulary/wordDrill.tsx` sin cambiar
  su contrato.
