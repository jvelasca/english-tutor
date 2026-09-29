# Release notes — English Tutor v3.92.0

**Fecha:** 2026-09-29 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.91.0 → 3.92.0`

**Con backend y frontend, CON migración de BD aditiva e idempotente** (tabla append-only
`listening_difficulty_evidence` + índice por `(user_id, created_at)`; columna aditiva
`vocabulary.sense_json`), **SIN endpoints nuevos** y **SIN cambio de contrato incompatible**: los
cuatro endpoints que cambian —`POST /api/listening/answer`, `POST /api/vocabulary/items`,
`GET /api/vocabulary/lexicon` y `GET /api/academy/daily-plan`— crecen con campos **aditivos**.
`GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate** —siguen los **ocho**,
todos en `pending`— y `docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** El fallo de Listening deja de ser un callejón sin salida y pasa a ser **evidencia
de dificultad sobre las palabras que el alumno ya tiene** (sube su dificultad FSRS y las vuelve a
poner debidas hoy, **sin gastarles un repaso ni tocar `reps`/`stability`**), la **acepción** elegida
en el diccionario viaja con la palabra y gobierna el alta, la práctica y el repaso, y el plan diario
publica una **métrica del día unificada y honesta** que no confunde evidencia con progreso.

---

## 1. Lo que se verificó antes de tocar nada

| Comprobación | Estado en `main` antes de V3.92 |
|---|---|
| Fallo de Listening | Se registraba (V3.89: cola + tres acciones) pero **no dejaba rastro** sobre las palabras del alumno |
| FSRS | Solo lo movían `schedule()` (recuperación real) y el alta; **ninguna señal receptiva** entraba |
| Acepción del diccionario | Se elegía en pantalla (`chosenMeaning`) y **se perdía**: no viajaba al alta ni al léxico |
| Métrica del día | Contaba minutos/unidades/nuevas/repasos, **no** la evidencia de dificultad |
| Contrato de la tarjeta de fallo | El backend servía `transcript_policy`/`sentence_timings`/`word_timings` en **snake_case**; el cliente los leía en **camelCase** |

De ahí el recorte: **no** un subsistema nuevo, sino (1) cerrar el puente Listening→FSRS como
**evidencia** —nunca como flashcard—, (2) hacer que la **acepción elegida** sea un dato que viaja, y
(3) publicar **una sola verdad** para el día.

## 2. El puente Listening → FSRS: evidencia, no flashcard

**La frontera que V3.89 dejó escrita se respeta.** El objeto que se falla es una **frase**, y meterla
en FSRS habría mezclado dos cosas distintas: el objeto de FSRS es una **palabra**. Pero el fallo
**sí** dice algo sobre las palabras que aparecían en esa frase, y esa señal se perdía.

**Nuevo módulo puro `services/listening_bridge.py`** — sin BD, sin reloj, sin FastAPI:

| Función | Qué hace |
|---|---|
| `phrase_units(text)` | Trocea a minúsculas, descarta no-alfabético y **palabras vacías** (`GLOSS_STOPWORDS`), deduplica en orden. Total: entrada rara → `[]` |
| `unit_index(known)` | Índice `forma → palabra canónica` del léxico del alumno (superficie + lema + **variantes** del lematizador declarado) |
| `match_units(text, known)` | Empareja por **lema y morfología** (`banks`/`banking` → `bank`) con el **mismo** lematizador que el Sense Engine |
| `is_weak_card(card)` | Una carta es **débil** si está en `new`/`learning`/`relearning` **o** su `difficulty` ya es `≥ 6.0` |
| `select_targets(matches, cards)` | Se queda con las unidades que **ya tienen carta** y son **débiles**, acotadas a `MAX_MATCHES = 8` |

**Sin diccionario, sin LLM y sin dependencias nuevas** (PREMISAS §2 y §21): el emparejamiento es
**morfológico y por lemma**, no semántico. Que una frase fallada **no** señale ninguna palabra es un
resultado **válido**: no se inventa evidencia.

**La carta FSRS sube de dificultad sin fingir una recuperación.** `fsrs.apply_difficulty_evidence()`
(`DIFFICULTY_EVIDENCE_DELTA = 0.6`, tope `10.0`):

- **sube** `difficulty` y **adelanta el vencimiento a ahora** —una palabra que no se entiende al oírla
  es una palabra que reclama repaso—;
- **no toca** `reps`, `stability`, `state` ni `last_evidence_at`: un fallo receptivo **no es** una
  recuperación, así que **no consume un repaso ni corrompe el intervalo real**;
- **salta las cartas fuertes** (`state == "review"` con `difficulty < 6.0`): el dominio demostrado no
  se rompe por un fallo de escucha puntual de **otra** destreza.

**Invariante que no se cruza (D3):** este puente **NUNCA crea vocabulario**. Solo mira palabras que el
alumno **ya tiene** en `vocabulary`. Y como `apply_difficulty_evidence` **no reordena por dificultad**,
la cola de vencimiento conserva su **prioridad de urgencia**.

**Todo queda registrado.** Tabla **append-only** `listening_difficulty_evidence` (palabra, intento,
`difficulty_before`/`after`, `due_at`, `created_at`), con `record_difficulty_evidence()` y
`list_difficulty_evidence(user_id, day)`. Vive **aparte** de `fsrs_cards` por dos razones explícitas:
(1) permite **contar la evidencia por día** sin deducirla de un `why` de texto, y (2) deja la carta
FSRS con su **contrato intacto**.

`POST /api/listening/answer` devuelve `difficulty_evidence: {words, count}` para que la UI lo
**explique** en vez de esconderlo (i18n `listening.bridge.wordsHarder`).

## 3. La acepción elegida deja de ser una etiqueta de pantalla

`bank` no es una palabra: es un conjunto de acepciones y el alumno aprende **una**. Esa elección ahora
**viaja**:

- se envía en el alta (`sense`) y se persiste en la columna aditiva `vocabulary.sense_json` con el
  contrato `{term, pos, gloss, lemma, source, domain}`;
- se expone **en solo lectura** en el léxico (`LexicalItemOut.sense` / `LexiconOut`) y el inventario la
  pinta como «Meaning: noun · A place for money.»;
- **si el alta NO declara acepción** —lista pegada, currículo, importación— el campo **no se manda**
  (ni como `null`) y el inventario **no pinta** ningún significado. «No consta» es información;
  **inventar** un significado no lo es.

Se recorta por campo (**300** caracteres) y se **ignoran** las claves desconocidas, así que la fila se
sirve **tal cual** y **no** se rellena a ojo. El feedback del alta (`dictionary.lookup.addSense`)
confirma qué acepción se guardó. `sense_json` **no cambia el scoring** ni la cara B: la traducción del
alumno sigue mandando.

## 4. Una sola verdad para el día (y la evidencia no se disfraza de progreso)

`services/daily_plan.py::day_metrics` publica dos cifras **separadas**:

- `difficulty_evidence` — cuántas **veces** el día ha subido la dificultad de una palabra;
- `words_flagged` — cuántas palabras **distintas** han subido.

Se cuentan **por separado** porque miden cosas distintas y **sumarlas mentiría**: una palabra puede
fallar tres veces en la misma mañana y son **3** eventos sobre **1** palabra. En Home se pinta una
línea propia —«Words that got harder: 2 · (3 listening misses; it's evidence, not a review)»— que
**solo aparece si la hay** (nunca un cero decorativo) y que **no** toca ni el porcentaje del objetivo
ni los repasos pendientes: la evidencia **no es trabajo hecho**.

## 5. Un fallo de contrato real, encontrado al cerrar el circuito (V3.27–V3.91)

El backend sirve `transcript_policy`, `sentence_timings` y `word_timings` en **snake_case** (contrato
Pydantic), pero el cliente los leía en **camelCase**: las tres claves llegaban `undefined` y con ellas
se caía, **sin ruido**:

- la **tarjeta de fallo de V3.89** —las tres acciones «Continuar / Repasar ahora / Repasar después»—
  **nunca se pintaban**;
- el **resaltado de frase** y el **karaoke por palabra de V3.29** servían siempre lista vacía.

Se arregla en el **borde** (`frontend/src/api/listening.ts::toListeningQuestion`): una sola vez, sin
que ninguna pantalla tenga que conocer las dos formas. Se fija con vitest contra la forma **exacta**
del backend y con una **E2E que mockea snake_case** —mockear camelCase habría escondido justo el
defecto que la prueba debe vigilar—.

## 6. Verificación

| Puerta | Resultado |
|---|---|
| `ruff check .` (backend y lanzador) | limpio |
| `pytest` backend | **3408 passed** (incluye `test_listening_bridge_v392.py` y `test_sense_adoption_v392.py`, nuevos, y la ampliación de `test_daily_plan_v390.py`) |
| `vitest run` | **1103 passed** (111 ficheros) |
| `tsc --noEmit` | limpio |
| `npm run build` | correcto |
| `check_i18n_coverage.py --strict` | **1871** cadenas · 0 huérfanas · 0 sin definir · 0 duplicadas |
| `contrast_audit.mjs --strict` | 480 pares + 6 guardas · **0 bloqueantes** · `audit: V3.92.0-contraste-wcag` |
| Playwright (rutas tocadas: **Listening, Home, Diccionario**) | `integratedCircuitV392` (nuevo), `listeningReplayStop`, `homeDailyPlan`, `dictionarySmoke`, `dictionaryFlashcardsBridge` y `responsiveOverflow` en los **3 breakpoints** · **6/6** en el E2E nuevo |
| `validation_gate.py auto --require-dist` | **10/10** (8 gates) |
| `check_release_consistency` | OK en los **6 orígenes** (`3.92.0`) |

**E2E del circuito** (`frontend/tests/visual/integratedCircuitV392.spec.ts`): verifica, en `desktop`,
`tablet` y `mobile`, que (i) un fallo de Listening pinta y explica la evidencia de dificultad, (ii) las
tres acciones quedan **siempre** disponibles —un fallo **nunca** bloquea la sesión—, y (iii) la
métrica del día aparece en Home cuando `words_flagged > 0`.

## 7. Honestidad: lo que NO trae

- **La evidencia de dificultad NO es un repaso.** No sube `reps`, no reinicia `stability` y no
  certifica nada: solo sube `difficulty` y reclama la palabra para hoy.
- **El emparejamiento es morfológico y por lemma, no semántico.** Una frase fallada puede **no**
  señalar ninguna palabra, y eso es un resultado **válido**: no se inventa evidencia.
- **La tabla es append-only y por usuario.** Crece con el uso y **todavía no se poda**.
- **`sense_json` no cambia el scoring** ni la cara B: es **contexto declarado**, no una segunda fuente
  de verdad.
- **El arreglo del contrato de Listening es un fallo PREVIO** a esta release (V3.27), no una
  funcionalidad nueva: se documenta porque salió al cerrar el circuito.
- **Los ocho gates humanos siguen `pending`** y `docs/audit/validation-evidence.json` sigue sin
  existir.

## 8. Archivos tocados (resumen)

- **Backend:** `services/listening_bridge.py` (nuevo), `services/fsrs.py`
  (`DIFFICULTY_EVIDENCE_DELTA`, `apply_difficulty_evidence`), `services/daily_plan.py`
  (`difficulty_evidence`, `words_flagged`), `repositories/db.py` (tabla
  `listening_difficulty_evidence` + índice, columna `vocabulary.sense_json`),
  `repositories/listening.py` (`record_difficulty_evidence`, `list_difficulty_evidence`),
  `repositories/vocabulary.py` (`sense_json`), `domain/listening.py` (puente en el fallo),
  `domain/vocabulary.py` y `domain/retention.py` (persistencia de la acepción),
  `domain/academy.py` (métricas del plan), `routers/vocabulary.py`, `schemas/listening.py`,
  `schemas/vocabulary.py`, `schemas/academy.py`.
- **Frontend:** `api/listening.ts` (`toListeningQuestion`), `api/vocabulary.ts` (`sense`),
  `features/listening/ListeningPractice.tsx` (evidencia en la tarjeta de fallo),
  `features/vocabulary/DictionaryLookup.tsx` (feedback de acepción),
  `features/vocabulary/LexiconInventory.tsx` (sentido en solo lectura),
  `components/TodayPlan.tsx` (línea de evidencia), `types/api.ts`, `utils/i18n.ts`.
- **Tests:** `backend/tests/test_listening_bridge_v392.py` (nuevo),
  `backend/tests/test_sense_adoption_v392.py` (nuevo), `backend/tests/test_daily_plan_v390.py`,
  `frontend/src/api/listening.test.ts`, `frontend/src/api/vocabulary.test.ts`,
  `frontend/src/components/TodayPlan.test.tsx`,
  `frontend/src/features/vocabulary/DictionaryLookup.test.tsx`,
  `frontend/src/features/vocabulary/LexiconInventory.test.tsx`,
  `frontend/tests/visual/integratedCircuitV392.spec.ts` (nuevo).
- **Versión y docs:** `backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
  `README.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`, `docs/audit/PARKED.md`.

## Para auditar esta release

1. Fallar una frase de Listening que contenga una palabra **ya** en el léxico: la tarjeta de fallo debe
   **explicar** que esa palabra se ha vuelto más difícil, y `difficulty_evidence.count` debe ser `> 0`.
2. Comprobar en BD que la carta de esa palabra **subió `difficulty`** y **venció hoy**, con `reps`,
   `stability` y `state` **intactos**, y que existe la fila en `listening_difficulty_evidence`.
3. Repetir el fallo con una palabra **dominada** (`review`, dificultad baja): **no** debe recibir
   evidencia.
4. Fallar una frase con palabras que el alumno **no** tiene: **no** debe crearse vocabulario alguno y
   `words_flagged` debe quedarse en `0` (la línea de Home **no** aparece).
5. Añadir una palabra desde el diccionario **eligiendo acepción**: el inventario debe mostrarla en
   solo lectura. Añadirla **sin** acepción: no debe mostrarse ningún significado.
6. Comprobar las **tres acciones** de la tarjeta de fallo en los **3 breakpoints** (el defecto de
   contrato V3.27 las ocultaba).
7. Abrir Home con evidencia del día: la línea de evidencia debe aparecer **sin** alterar el
   porcentaje del objetivo ni los repasos pendientes.
