# v3.43.0 — Transfer 2.0 (target oculto, semanticidad, diversidad, `transfer_state`)

**Cierre quirúrgico de los 4 P1 de la auditoría de V3.42.0 sobre la evidencia de
transferencia. Release ADITIVA y SIN migración que corrige una
SOBREESTIMACIÓN: la consigna de transferencia mostraba la palabra objetivo
(solo había que insertarla), el éxito léxico se confundía con la adecuación
semántica, la diversidad contextual se medía con `context_id A != context_id B`
y el eje se resumía en un booleano `transfer = true`. Se mantiene la premisa 21
(el LLM no decide evidencia): el proxy de adecuación es DETERMINISTA y advisory,
y nunca bloquea la evidencia léxica, solo la separa de los ÉXITOS LIMPIOS que
hacen avanzar el estado.**

Versión de app `3.42.0 → 3.43.0`. Backend (`services/transfer.py`,
`services/evidence.py`, `services/lexicon.py`, `services/planner.py`,
`repositories/evidence.py`, `domain/vocabulary.py`, `schemas/vocabulary.py`,
`schemas/learning.py`) + frontend (`features/vocabulary/wordDrill.tsx`,
`features/vocabulary/ReviewQueueSection.tsx`, `types/api.ts`, i18n) + tests y
docs.

## Contexto

La auditoría de V3.42.0 (sección 22) detectó que la transferencia estaba
**sobreestimada** en cuatro puntos, todos P1:

1. **P1-01 — el target era visible.** La consigna («Tell a story using
   `"travel"`» / `linea con {word}`) daba la forma esperada: el alumno solo tenía
   que insertarla, y eso demuestra producción contextualizada, no recuperación
   léxica espontánea. El `support_level="spontaneous"` quedaba injustificado.
2. **P1-02 — `lexical_transfer` y semántica mezclados.** `passed` acreditaba
   «la unidad quedó alineada + longitud mínima», pero un uso incompatible con la
   categoría del ítem (`I bank yesterday`) contaba igual que un uso correcto.
3. **P1-03 — diversidad falsa.** Bastaba con dos `context_id` distintos: seis
   contextos con `topic`/`goal`/`discurso` distintos pueden producir la MISMA
   estructura lingüística (work/future/problem con `take`).
4. **P1-04 — `transfer` booleano.** «2 contextos con éxito» no distingue primera
   demostración de estabilidad ni de automaticidad.

Fuera de alcance (diferido a V3.44): modelo léxico *sense-aware*
(`lexical_unit → sense`), Context Bank enriquecido a escala y
`expected_learning_value` / Optimal Next Task completo.

## Qué cambia

- **Banco de contextos con target oculto y atributos (`services/transfer.py`,
  P1-01 + base de P1-03).** Cada contexto declara `id`, `topic`,
  `communicative_goal`, `discourse_type`, `social_relation`, `time_reference`,
  `register`, `interaction_type` y una consigna `prompt` que **nunca contiene
  `{word}`** (escenario + objetivo comunicativo). `context_for(word,
  used_context_ids, *, success_context_ids)` deja de sustituir el target y, con
  los contextos ya logrados, elige entre los no usados el de mayor DISTANCIA
  mínima a ellos (`_novelty_score`); los empates los resuelve el hash estable
  `zlib.crc32` (`_stable_index`). Nuevas funciones puras `context_attributes`,
  `context_dimensions`, `context_distance` y `context_diversity`
  (`distinct_contexts`, `dimensions`, `diverse_dimensions`, `score`) y constante
  `CONTEXT_DIVERSITY_MIN = 2`. `register` se declara como atributo pero queda
  fuera del denominador de diversidad (todo el banco es `neutral`).
- **Semanticidad determinista (`services/lexicon.py`, `services/evidence.py`,
  P1-02).** Sin columna nueva: se reutiliza el idioma observacional de
  `error_type`. `score_transfer_attempt(word, text, *, pos="")` separa
  `lexical_transfer` (alias de `passed`) de la adecuación
  (`semantic_fit` / `adequacy` = `fit`/`suspect`/`unknown`) con un proxy
  conservador (`_semantic_fit`): POS de familia `noun` usada como verbo
  (pronombre sujeto delante o flexión `-ed`/`-ing`) y POS de familia `verb`
  precedida de determinante → `suspect`. Un uso léxicamente correcto pero
  `suspect` conserva `passed=True` y guarda `error_type="semantic_mismatch"`
  (nueva tupla `TRANSFER_ERROR_TYPES`). `score_write_attempt` no cambia su
  contrato EXACTO (4 claves) y se documenta explícitamente (P2-04) que `passed`
  acredita PRODUCCIÓN LÉXICA, no corrección gramatical ni ortográfica.
  `domain/vocabulary.py::submit_transfer_attempt` lee la `pos` de la caché
  (`repositories.dictionary.get_entry`) y la pasa al scorer; `_record_transfer_evidence`
  mantiene `success = transfer léxico` y persiste el `error_type` clasificado.
- **Señales limpias y estado formalizado (`services/evidence.py`, P1-03/P1-04).**
  `context_signals` (pura, reutilizada por el resumen SQL → paridad por
  construcción) añade `clean_contexts`, `clean_successes`,
  `clean_success_contexts`, `clean_success_days` y `context_diversity`; el
  ÉXITO LIMPIO excluye los intentos con `error_type="semantic_mismatch"`. `transfer`
  pasa a exigir `>= CONTEXT_TRANSFER_MIN` contextos limpios **y**
  `diverse_dimensions >= CONTEXT_DIVERSITY_MIN`. Nueva función pura
  `transfer_state(evidence)` + `TRANSFER_STATES` (`not_ready` → `emerging` →
  `contextualized` → `transfer_demonstrated` → `transfer_stable` →
  `automatic`) y `with_transfer_state` (lo añade a los resúmenes puro y SQL).
  `transfer_state` respeta el booleano `transfer` de un resumen legacy/parcial
  (sin los campos de V3.43): lo lee como transferencia DEMOSTRADA, nunca
  estable, en lugar de degradarlo por falta de contadores nuevos.
  `empty_summary` y `repositories/evidence.summarize_by_target` exponen los
  campos nuevos (aditivos).
- **Planner por estado (`services/planner.py`, P1-04).**
  `has_contextual_transfer` lee `transfer_state ∈ {transfer_demonstrated,
  transfer_stable, automatic}` (con fallback al booleano `transfer` para
  resúmenes parciales) y `transfer_gap` dispara en `emerging`/`contextualized`
  (antes: 1 contexto con éxito), manteniendo los mínimos. `planned_signals`
  añade `transfer_state` y `context_diversity`.
- **Geometría y elección diversa (`domain/vocabulary.py`).**
  `get_transfer_context` pasa los `success_contexts` del resumen a `context_for`
  para pedir el contexto más novedoso; `submit_transfer_attempt` deriva el
  `context_id` con la MISMA función que el GET cuando el cliente no lo manda.
- **Contrato HTTP y cola (aditivos).** `TransferContextOut` añade `exhausted`,
  `communicative_goal` y `discourse_type`; `TransferAttemptOut` añade
  `lexical_transfer`, `semantic_fit` y `adequacy` (conserva `passed`).
  `ReviewQueueItem` añade `transfer_state` y `context_diversity` (los expone
  `lexicon.review_queue_item`, que ya alimenta `domain/review`). Sin endpoints
  nuevos ni migración.
- **Frontend.** `wordDrill.tsx` extiende `hideTarget` a `transfer` mientras no
  hay outcome: la cabecera muestra `dictionary.drill.transferHiddenTarget` (no
  la palabra) y la revela tras el intento; si `passed && adequacy === "suspect"`
  el feedback avisa en tono warning
  (`dictionary.drill.transferSemanticWarning`) y sigue llamando a `onProduced`
  (hubo producción léxica). `ReviewQueueSection.tsx` quita `transfer` de
  `showsWord`: la cola muestra la etiqueta oculta
  (`dictionary.review.hidden.transfer`, reescrita). `types/api.ts` añade
  `ContextDiversity` y los campos nuevos; i18n (`es`/`en`) con paridad.

## Tests

- Backend pytest **1989 passed** (+14): nuevo `test_transfer_v343.py`
  (atributos y diversidad de contextos, elección novedosa en `context_for`,
  proxy semántico `noun`-como-verbo / `verb`-tras-determinante, `unknown` sin
  POS, `semantic_mismatch` que no cuenta como éxito limpio, transiciones de
  `transfer_state` incluido el fallback legacy, `transfer_gap`/`has_contextual_transfer` por estado y
  paridad pura↔SQL de los campos nuevos). Se ajustan `test_transfer_v340.py`
  (consigna sin target y diversidad real) y `test_learning_evidence_v336.py`
  (contrato de `empty_summary`).
- Frontend vitest **70 ficheros/607 tests** (+1): `wordDrill.test.tsx` (el paso
  `transfer` oculta la palabra en la cabecera, la consigna no la incluye y el
  aviso semántico aparece) y `ReviewQueueSection.test.tsx` (la actividad
  `transfer` ya no revela la palabra). Verificación: pytest 0 fallos,
  `ruff check backend/` limpio, `npm run test`, `npx tsc --noEmit` y
  `npm run build`; y `check_release_consistency` **3.43.0** exit 0.

## Fuera de alcance (V3.44)

- Modelo léxico *sense-aware* (`lexical_unit → sense`) que sustituya el proxy
  POS por adecuación real.
- Context Bank enriquecido a escala (más contextos y dimensiones calibradas).
- `expected_learning_value` / Optimal Next Task completo.

## Decisiones de diseño

- **P1-02 sin migración:** se reutiliza `error_type` observacional
  (`semantic_mismatch`) en lugar de una columna nueva, para no romper el alcance
  quirúrgico acordado.
- **El proxy semántico nunca bloquea la evidencia léxica:** la separa. `success`
  sigue siendo el resultado léxico; `transfer_state` solo avanza con éxitos
  limpios.
- **`spontaneous` pasa a ser semánticamente correcto** al ocultarse el target:
  coincide con la tabla del punto 16 de la auditoría. No se renombra el valor
  canónico.
