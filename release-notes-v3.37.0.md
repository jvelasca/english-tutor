# v3.37.0 — Learning Evidence 3.0: cues graduados y automaticidad

**El peldaño `2 · Recall` deja de tener UN solo cue (traducción y, si no,
definición — un *fallback*) y pasa a tener una PROGRESIÓN declarada:
`translation (cued) < definition (cued) < cloze (guided)`. El ledger registra
por peldaño (`drill:recall:<peldaño>` → histograma `recall_rungs`),
`next_recall_rung` decide el siguiente por ÉXITOS ya registrados y
`resolve_recall_cue` degrada SIEMPRE hacia más apoyo cuando el peldaño ideal no
tiene contenido — nunca al revés. La **automaticidad** (`is_automatic`) exige ≥2
éxitos sin apoyo en DÍAS NATURALES distintos: un acierto suelto no consolida
(D5/E3). Sin migración de BD, contrato HTTP aditivo, sin LLM en los cues y sin
tocar scoring, FSRS ni la semántica del intervalo de evidencia (V3.35.1
P1-01).**
Versión de app `3.36.0 → 3.37.0`. Backend + frontend + docs; sin cambios de
esquema (`support_level`/`activity_id` ya existían desde V3.36.0) y contrato
HTTP aditivo.

## Contexto

V3.36 hizo que el ledger aprendiera el **CÓMO** de cada evento (`support_level`,
`difficulty`, `context_id`/`activity_id`, `response_time_ms`, `error_type`).
Pero el dato no se usaba: el peldaño `2 · Recall` elegía «el primer cue
disponible» (traducción y, si no, definición), así que una palabra con
traducción **jamás** se enfrentaba a un cue más difícil, el evento declaraba
siempre `support_level="cued"` y `independent_successes` se quedaba sin uso — la
escalera léxica nunca producía evidencia `independent`.

V3.37 cierra el arco: convierte la escalera en progresión, hace que cada peldaño
declare su propio apoyo y lee la historia resultante para decidir el siguiente
peldaño.

## Decisión de alcance: la escalera real, no la auditada

La auditoría pidió `translation → definition → cloze → situación → free recall`.
Contrastado con el código real:

| Peldaño auditado | Estado real | Decisión V3.37 |
|---|---|---|
| `translation` | ✅ existe (V3.34) | Peldaño 1 (`cued`) |
| `definition` | ⚠️ existe solo como *fallback* | **Peldaño 2 de pleno derecho** (`cued`) |
| `cloze` | ❌ no existe | **Peldaño 3 nuevo** (`guided`), determinista desde el corpus |
| `situación` | ❌ no existe | **Fuera de alcance**: exige contenido autorado por palabra (V3.38) |
| `free recall` | ✅ ya existe, pero no es un cue | Es el paso `3 · Sentence` + la producción espontánea (chat/writing) |

- **`free recall` no era el peldaño que faltaba.** Producir la palabra sin apoyo
  ya existe (paso `3 · Sentence` y producción espontánea: `chat` →
  `spontaneous`, `conversation` → `guided`, `speaking`/`writing` →
  `independent`). Lo que faltaba era el **tramo medio** de la escalera y la
  **lectura** de su evidencia.
- **`situación` no se implementa sin contenido.** Un enunciado situacional no se
  deriva de forma determinista de la caché del diccionario ni del banco de
  pronunciación; inventarlo rompería la regla de «no inventar contenido» y el
  principio de cues puros. Requiere extender el contrato de contenido
  (`generator_version`, V3.30) y se planifica como V3.38.

## Qué cambia

### 1. La escalera como progresión (`services/recall.py`)

- `RECALL_CUES = ("translation", "definition", "cloze")`, ordenados de MAYOR a
  MENOR apoyo. El orden ES la hipótesis pedagógica declarada
  (`translation < definition < cloze`) y V3.37 deja los datos
  (`recall_rungs` por `activity_id`) para corregirla si el corpus demuestra lo
  contrario.
- `RECALL_CUE_SUPPORT`: `translation`/`definition` → `cued`, `cloze` →
  `guided`. El mapeo vive junto a la escalera, en la capa pura, para que
  dominio, repositorio y tests no puedan divergir.
- `recall_prompt_for(word, entries, *, cue=None, example=None)`:
  - `cue=None` conserva **exactamente** el comportamiento V3.34 (traducción y,
    si no, definición) para no romper clientes antiguos;
  - un `cue` explícito sirve ESE peldaño o devuelve `None` si no tiene contenido
    (degradación controlada, **sin evento**); un `cue` no soportado, `None`.
- `blank_out(phrase, word)` — función pura del cloze. Reutiliza la MISMA
  alineación que acredita la producción del drill
  (`services.phonetics.unit_produced`, V20-01) y aplica reglas de honestidad:
  - si tras blanquear queda **cualquier otra aparición** de la palabra, el cue
    se descarta (`None`): sería un spoiler;
  - se aplica la misma comprobación anti-spoiler que la definición;
  - si no hay frase real en el corpus, `None` (**nunca se inventa una frase**).

### 2. Progresión por evidencia y disponibilidad (`services/recall.py`)

- `next_recall_rung(row, evidence)` — peldaño **recomendado**, puro:
  - sin éxito en `translation` → `translation`;
  - `translation` superado, sin `definition` → `definition`;
  - `definition` superado, sin `cloze` → `cloze`;
  - los tres superados → `cloze` (mantenimiento espaciado: es el techo hasta
    que exista `situación`).
  El «éxito en el peldaño X» se lee del ledger por `activity_id`
  (`drill:recall:<peldaño>`, agregado en `recall_rungs`), **no** de contadores
  nuevos.
- `resolve_recall_cue(ideal, available)` — separa la decisión pedagógica de la
  disponibilidad real de contenido (el `cloze` exige que la palabra aparezca en
  el banco de pronunciación y no todas lo hacen):
  - recorre la escalera desde el ideal hacia **ABAJO** (hacia más apoyo) y
    devuelve el primer peldaño disponible;
  - `None` si no hay ninguno (el peldaño degrada con `available=false`, sin
    evento, como en V3.34);
  - **nunca degrada hacia arriba**: subir la exigencia sin evidencia que lo
    justifique es lo contrario de lo que V3.37 quiere.

### 3. Automaticidad (`services/evidence.py`)

- `AUTOMATIC_MIN_INDEPENDENT = 2` — umbral declarado y calibrable.
- `is_automatic(evidence)` — pura: exige `independent_successes >= 2` **y**
  `independent_success_days >= 2` (días naturales distintos, mismo rigor que
  `distinct_success_days`). Un acierto suelto no es automaticidad (D5/E3) y
  `cued`/`guided` no cuentan como independiente (eso es recuperación CON ayuda).
- `summarize_evidence`/`empty_summary` añaden `independent_success_days` y
  `recall_rungs`.
- `RECALL_RUNG_EVIDENCE` + `recall_rung_activity`/`recall_rung_from_activity`:
  el vocabulario `drill:recall:<peldaño>` que el dominio ESCRIBE y el servicio
  puro LEE, para que no puedan divergir. Un `activity_id` legacy
  (`drill:recall`, sin peldaño) no declara peldaño.

### 4. Repositorio: paridad pura↔SQL (`repositories/evidence.py`)

`summarize_by_target` agrega `independent_success_days`
(`COUNT(DISTINCT substr(occurred_at,1,10))` de los éxitos sin apoyo) y
`recall_rungs` (histograma de `activity_id LIKE 'drill:recall:%'`), con la
**paridad exacta** frente a la versión pura fijada por test. Sin migración:
`support_level` y `activity_id` ya existen desde V3.36.0.

### 5. Cola de repaso (`services/lexicon.py`, `domain/review.py`)

- `recommend_review_activity` incorpora el ítem `automatic`
  (`is_automatic`) sin hueco de producción → `recall` de **mantenimiento**
  (`reason="automatic_maintenance"`), que la cola sirve en el peldaño `cloze`.
- `review_queue_item` gana `recommended_cue` y `automatic` (aditivos): el ideal
  de `next_recall_rung` se resuelve contra la disponibilidad real de contenido
  (`resolve_recall_cue`) con una sola lectura de la caché para todas las
  palabras vencidas. La cola sigue **sin** exponer el cue ni la forma esperada:
  el cue lo sirve el GET del peldaño (premisa 21 + P1-03 de V3.35.1).

### 6. Captura en dominio (`domain/vocabulary.py`)

`submit_recall_attempt(…, cue=None)` re-deriva el peldaño con la misma función
pura (premisa 21: la UI declara QUÉ peldaño le sirvieron; el servidor puntúa) y:

- rechaza con **422 sin evento** un `cue` no soportado o un peldaño sin
  contenido para esa palabra;
- declara `support_level = RECALL_CUE_SUPPORT[cue]` y
  `activity_id = "drill:recall:<cue>"` (antes: `"drill:recall"`, `cued` fijo);
- **no cambia el scoring**: `correct` sigue siendo igualdad estricta de
  superficie y `classify_recall_error` (V3.36) sigue siendo observacional. Un
  acierto con cloze vale lo mismo que con traducción para el contador de recall;
  lo que cambia es lo que el ledger sabe del apoyo.

### 7. Contrato HTTP (`schemas/vocabulary.py`, `routers/vocabulary.py`)

- `GET /api/vocabulary/drill/recall?user_id&word[&cue=cloze]` →
  `RecallPromptOut {word, available, cue, cue_kind, support_level}`. `cue_kind`
  es el identificador ÚNICO del peldaño servido y admite `cloze` además de
  `translation`/`definition` (aditivo). En un cloze, `cue` es la frase con el
  hueco.
- `POST /api/vocabulary/drill/recall-attempt`
  (body `{word, answer, cue?, response_time_ms?}`) → `RecallAttemptOut` (sin
  cambios de forma; `cue` es aditivo y opcional). Sin `cue`, el servidor se
  comporta como V3.36.
- `LexicalEvidence` amplía `independent_success_days`/`recall_rungs` y
  `ReviewQueueItem` amplía `recommended_cue`/`automatic`.

### 8. Frontend (`wordDrill.tsx`, `api/vocabulary.ts`, `types/api.ts`, `i18n.ts`)

- El peldaño `2 · Recall` pinta el cue del peldaño servido sin saber de más: un
  cloze se ve tal cual (la frase con `_____`), con estilo monoespaciado para el
  hueco, y se rotula con `dictionary.drill.recallCue.<peldaño>` (es/en).
- `submitDrillRecallAttempt` envía el `cue_kind` servido en el intento; la
  latencia de V3.36 se sigue midiendo igual (cue visible → envío).
- El peldaño sigue ocultando la palabra diana (`hideTarget`, V3.34) y **no hay
  UI nueva que spoilee**.

## Verificación

- Backend: `ruff check .` limpio y `pytest` → **1813 passed** (+22 sobre
  v3.36.0), con el nuevo `tests/test_graduated_cues_v337.py`.
- Frontend: `tsc --noEmit` limpio, `vitest` → **65 ficheros/560 tests** (+1) y
  `npm run build` OK.
- `python scripts/check_release_consistency.py` → **3.37.0** exit 0.

## CI

- Commit `bdc77cd5e467cea4b027178e6235da8e57b36f9e` con el run
  [34476875230](https://github.com/jvelasca/english-tutor/actions/runs/34476875230)
  en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build,
  release consistency, Beta V3.0 gate, content validation, Playwright E2E).

## Documentación

- `CHANGELOG.md`: entrada `[3.37.0]`.
- `PLAN.md`: hito V3.37 al frente de «Estado actual» y candidato **V3.38**
  (`situación` + planner) en «Siguiente incremento».
- `docs/RELEVO.md`: nota de cierre al frente y `START HERE` actualizado a
  `v3.37.0`.
- `README.md`: versión estable `v3.37.0`.

## Fuera de alcance (V3.38/V3.39)

- **`situación`** (enunciado situacional por palabra) y el **planner** (grafo
  evidencia → estado de conocimiento → retención → hueco de transferencia →
  Optimal Next Task) — V3.38.
- Los diferidos de V3.30 (consumo de `word_breakdown_json` en agregados /
  práctica dirigida de las palabras falladas y palabras tocables en
  transcripts/chat) y el cierre de la transferencia por contexto de actividad
  V3.23 — V3.39.
