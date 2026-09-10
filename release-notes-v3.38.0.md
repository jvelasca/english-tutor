# v3.38.0 — La siguiente tarea óptima: `situación`, planner y automaticidad por skill

**El incremento que V3.37 dejó abierto, cerrado en tres frentes. (1) P1-03: la
automaticidad deja de ser un booleano global — cada evento léxico declara su
MODALIDAD (`recall`, `written_production`, `spoken_production`,
`spontaneous_use`), el resumen segmenta los éxitos por skill (puro + SQL con
paridad exacta) y `automatic_skills` responde por modalidad. (2) Planner
(Optimal Next Task): un servicio puro combina olvido, hueco, debilidad,
dependencia de apoyo y latencia en una PRIORIDAD explicable con pesos
declarados, y añade razones dirigidas por la evidencia fina (`error_prone`,
`skill_gap`, `slow_recall`); la cola de repaso se ordena por esa prioridad. (3)
`situación`: el contrato de contenido de la caché sube a `generator_version`
1.2.0 y gana un enunciado situacional autorado (un solo hueco `_____`, sin
spoiler) que pasa a ser el TECHO de la escalera de recall — `situation`, apoyo
`guided` — servido por el drill y recomendado por la cola, degradando siempre
hacia más apoyo.** Una migración aditiva e idempotente
(`dictionary_entries.situation`); contrato HTTP aditivo; sin tocar scoring,
FSRS ni la semántica del intervalo de evidencia (V3.35.1 P1-01).

Versión de app `3.37.1 → 3.38.0`. Backend (skills canónicos + agregados puros/SQL
+ `services/planner.py` + integración en la cola + contrato de contenido + 4.º
peldaño + dominio/schemas) + frontend (tipos + i18n) + tests y docs.

## Contexto

V3.35–V3.37 construyeron la infraestructura adaptativa: ledger longitudinal
(`learning_evidence`), dimensiones del evento (apoyo, dificultad, contexto,
latencia, tipo de error) y cues graduados por evidencia. Quedaban tres huecos
que V3.37 documentó explícitamente:

```text
    EVIDENCIA por peldaño        ¿POR QUÉ esta tarea?         CONTENIDO
    ─────────────────────        ────────────────────         ─────────
    translation                  ❌ solo urgencia FSRS        ❌ falta el techo
    definition                   ❌ skill="" en el ledger       situacional
    cloze (techo V3.37)          ❌ automaticidad global      (exige autoría)
```

- **P1-03** — `skill=""` en todos los eventos léxicos: la automaticidad era un
  único booleano, así que un ítem con aciertos de recall y de producción mezclados
  podía declararse «automático» sin serlo en ninguna modalidad concreta.
- **Planner** — la cola de repaso ordenaba por `retrievability` (urgencia del
  scheduler) y elegía actividad por hueco de competencia, sin usar la evidencia
  fina ya persistida (modalidad, latencia, tipo de error, apoyo).
- **`situación`** — la escalera tenía techo en `cloze`, que reutiliza una frase
  REAL del banco de pronunciación: para pedir más había que AUTORAR contenido.

## Qué cambia

### 1. P1-03 — modalidad canónica y automaticidad segmentada

`services/evidence.py`, `repositories/evidence.py`, `domain/vocabulary.py`.

- Vocabulario canónico `LEXICAL_SKILLS = ("recall", "written_production",
  "spoken_production", "spontaneous_use")` y mapeo canal→skill
  (`production_skill`). El ledger deja de escribir `skill=""`: el recall declara
  `recall`, el drill/retrieval su modalidad y la producción su modalidad (no el
  canal crudo).
- `summarize_evidence`/`empty_summary` añaden `skill_successes`,
  `skill_success_days`, `skill_independent_successes` y
  `skill_independent_days`; `summarize_by_target` los replica en SQL con
  **paridad exacta pura↔SQL** fijada por test.
- `automatic_skills(summary)` responde «¿en qué modalidades es automático?» con
  la MISMA exigencia de `is_automatic` (éxito independiente en días naturales
  distintos), pero por skill.
- **Sin migración**: `skill` ya existía como columna desde V3.36.0.

### 2. Planner — Optimal Next Task (`services/planner.py`, nuevo)

Servicio PURO que responde «¿por qué esta tarea, por qué ahora, con qué apoyo?».

- `planned_signals` — `forgetting` (1 − `retrievability`), `gap` (1.0 producción /
  0.5 transferencia / 0.0), `weakness` (1 − `success_rate`), `support`
  (proporción de éxitos no independientes; 0 sin éxitos) y `latency` (media
  normalizada), más los derivados `automatic`/`automatic_skills`/`skill_gaps`/
  `error_prone`/`slow_recall`.
- `priority_score` — suma ponderada con `PRIORITY_WEIGHTS` declarados y
  calibrables: olvido 0.35, hueco 0.30, debilidad 0.20, apoyo 0.10, latencia 0.05.
- `evidence_reason` — razones dirigidas por la evidencia fina en orden declarado:
  - `error_prone` — ≥ `ERROR_PRONE_MIN_WRONG` errores `wrong_word` (confusión
    real: una errata no cuenta);
  - `skill_gap` — el ítem ya logra algo pero no tiene NINGÚN éxito en las dos
    modalidades de producción;
  - `slow_recall` — hay aciertos pero su latencia media supera `SLOW_RECALL_MS`.
- `recommend_review_activity` las integra SIN sustituir a las razones de hueco de
  V3.35, y `explain_priority` produce el `why` (inglés, mismo registro que el
  motor adaptativo).
- La cola de repaso (`domain/review.py`) se ordena por `priority` (desempate por
  `retrievability` y palabra) y cada ítem expone `priority`/`signals`/`why`/
  `automatic_skills`. Sigue SIN exponer el cue ni la forma esperada.

### 3. `situación` — contrato de contenido y techo de la escalera

`repositories/db.py`, `repositories/dictionary.py`,
`services/dictionary_content.py`, `services/recall.py`.

- `GENERATOR_VERSION` 1.1.0 → **1.2.0**; `_SYSTEM_PROMPT` pide `situation`: UNA
  frase de escenario con EXACTAMENTE un hueco `_____` donde encaja la diana y sin
  la diana en ningún otro sitio.
- `_situation_from` valida de forma determinista: normaliza cualquier racha de
  guiones bajos a `_____`, exige exactamente un hueco, acota a
  `MAX_SITUATION_CHARS` y descarta el spoiler (`\b<diana>\b`). Si no cumple, se
  descarta la situación **sin invalidar definición ni traducción**.
- `dictionary_entries` gana la columna `situation` con migración **aditiva e
  idempotente** (backfill `''`), cubierta por test también sobre una BD legacy.
- `RECALL_CUES` pasa a `("translation", "definition", "cloze", "situation")` con
  apoyo `guided` para el nuevo techo: `next_recall_rung` solo llega a él con
  `cloze` consolidado y `resolve_recall_cue` sigue degradando SOLO hacia más
  apoyo (`situation` → `cloze` → `definition` → `translation`).
- El dominio sirve el enunciado (GET) y lo re-deriva al puntuar (POST),
  declarando `support_level="guided"` y `activity_id="drill:recall:situation"`;
  `_available_recall_cues` lo detecta y `_build_dictionary_entry` lo expone en la
  consulta del diccionario.

### 4. Contrato (aditivo)

- `LexicalEvidence` (schema Pydantic y tipo TS) amplía los cuatro histogramas por
  skill.
- `ReviewQueueItem` amplía `priority`, `signals`, `why` y `automatic_skills`.
- `DictionaryEntry`/`DictionaryEntryOut` amplían `situation`.
- `DrillRecallPrompt.cue_kind` admite `situation` y el i18n estrena la etiqueta
  del peldaño. El resto del contrato HTTP no cambia.

### 5. Sin cambios

Scoring, FSRS, `blank_out`, la semántica del intervalo de evidencia,
`error_type` (observacional) y el mecanismo de degradación de la cola (sigue sin
spoiler). El frontend solo necesita los tipos nuevos.

## Verificación

- Backend: `ruff check .` limpio y `pytest` → **1880 passed** (+56 sobre
  v3.37.1), con los nuevos `tests/test_skill_segmentation_v338.py`,
  `tests/test_planner_v338.py` y `tests/test_situational_cue_v338.py`.
- Frontend: `tsc --noEmit` limpio, `vitest` → **65 ficheros/560 tests** y
  `npm run build` OK.
- `python scripts/check_release_consistency.py` → **3.38.0** exit 0.

### Matriz de pruebas nueva (resumen)

| Frente | Qué fija el test |
|---|---|
| Skills | vocabulario canónico, mapeo canal→skill, histogramas por modalidad, `automatic_skills` (espaciado/volumen/mezcla), paridad pura↔SQL, e2e recall/producción |
| Planner | `planned_signals` (incl. sin evidencia y `support` 0), `priority_score`, orden de `evidence_reason`, integración en `recommend_review_activity` y orden de la cola por prioridad |
| `situación` | contrato de contenido (un hueco, spoiler, longitud), round-trip y migración legacy, techo de la escalera y degradación, disponibilidad, e2e GET/POST + diccionario + cola |

## CI

- Commit pendiente de publicar; se completará con el run de GitHub Actions
  (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build, release consistency,
  Beta V3.0 gate, content validation, Playwright E2E).

## Fuera de alcance (V3.39)

- Deudas diferidas de V3.30, transferencia por contexto V3.23, `cloze_coverage`
  del corpus, `example_for_many` de la Review Queue y el refactor de
  `wordDrill.tsx`.
- Cualquier migración no aditiva, cambio de scoring/FSRS o cambio de contrato
  incompatible.
