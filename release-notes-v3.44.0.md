# v3.44.0 — Lexicón sense-aware + scoring semántico 2.0

**Cierre quirúrgico de los dos P1 conceptuales que la auditoría de V3.43.0
(puntuada 9,6/10) deja abiertos: el proxy semántico usaba la `pos` GLOBAL como
sustituto de sentido (falsos positivos en palabras noun/verb) y la taxonomía
`fit`/`suspect`/`unknown` confundía «parece raro» con «es incorrecto». Release
ADITIVA y SIN migración de datos: la unidad léxica gana SENTIDOS —contenido
generado una vez por el modelo local dentro del contrato del diccionario y
cacheado—, y la adecuación se decide de forma DETERMINISTA comparando la función
de la ocurrencia con las familias POS de esos sentidos. La premisa 21 se
mantiene: el LLM genera contenido (sentidos), NUNCA decide evidencia.**

Versión de app `3.43.0 → 3.44.0`. Backend (`services/semantics.py` nuevo,
`services/dictionary_content.py`, `services/lexicon.py`, `services/evidence.py`,
`repositories/db.py`, `repositories/dictionary.py`, `domain/vocabulary.py`,
`schemas/vocabulary.py`) + frontend (`types/api.ts`,
`features/vocabulary/wordDrill.tsx`, `utils/i18n.ts`) + tests y docs.

## Contexto

La auditoría externa de V3.43.0 da por cerrados los 4 P1 de V3.42.0 y señala como
principal problema real el **proxy semántico**:

- **P1-01 — POS global como sustituto de sense.** El proxy usaba la categoría
  global de la entrada, así que palabras que son legítimamente noun y verb según
  contexto (`travel`, `water`, `plan`, `work`, `change`, `answer`, `phone`,
  `email`) podían marcar `semantic_mismatch` en usos correctos (`I plan my
  trip.` con la entrada `plan = noun`) e **impedir un clean success**.
- **P1-02 — falta `incorrect`.** `suspect` no debía tener el mismo peso que una
  incompatibilidad demostrable; solo el veredicto fuerte debe bloquear el clean
  transfer, y `suspect` debe ser advisory (warning + menos confianza).

Fuera de alcance (diferido a V3.45+): `transfer_condition`, CEFR/
`difficulty_vector` del contexto, Context Bank 2.0, `expected_learning_value` /
Adaptive Planner 2.0 y cualquier decisión que dé al LLM autoridad sobre el
Student Model.

## Qué cambia

- **Modelo de sentidos como CONTENIDO (`services/dictionary_content.py`,
  P1-01).** `GENERATOR_VERSION` `1.3.0 → 1.4.0` (regeneración lazy una sola vez,
  misma política de V3.38/V3.39). `_SYSTEM_PROMPT` y `_REVERSE_SYSTEM_PROMPT`
  piden `senses`: array de `{pos, gloss}` (1..`MAX_SENSES = 4`, `pos` en la
  taxonomía canónica, glosa corta acotada a `MAX_GLOSS_CHARS = 120`). Nuevo
  helper PURO `normalize_senses(raw)`: descarta `pos` inválido y entradas no
  diccionario, colapsa espacios, recorta la glosa, deduplica por `(pos, gloss)`,
  limita a `MAX_SENSES` y conserva el orden de entrada; nunca invalida
  definición/traducción si falta o es inválida (`[]`). El `pos` superior se
  deriva del primer sentido válido (fallback al `pos` del modelo) para no tener
  dos fuentes divergentes.
- **Persistencia aditiva (`repositories/db.py`, `repositories/dictionary.py`,
  P1-01).** Columna `senses_json TEXT NOT NULL DEFAULT ''` en
  `dictionary_entries` y `dictionary_reverse_entries`, con migración idempotente
  guardada por `PRAGMA table_info` + `ALTER TABLE` (también para la tabla inversa
  ya creada). `get_entry`/`get_reverse_entry` decodifican a `senses` (lista),
  `save_entry`/`save_reverse_entry` aceptan `senses` y serializan JSON compacto y
  orden estable; un `senses_json` ilegible degrada a `[]` sin romper la consulta.
  Sin migración de datos ni cambios de PK.
- **Adecuación semántica determinista (`services/semantics.py` nuevo,
  P1-01/P1-02).** Módulo PURO y sin LLM: `pos_family` (por palabras, no
  subcadenas: "adverbio" ≠ "verb"), `families_from_senses` (con fallback a la
  `pos` global), `unit_positions` y `occurrence_role` (cues FUERTES: pronombre
  sujeto, auxiliar/`to`, flexión `-ed`/`-ing`; cues DÉBILES: determinante y
  flexión `-s`/`-ies`) y `semantic_adequacy`. Regla conservadora: si ALGUNA
  ocurrencia encaja con las familias → `fit`; si ninguna encaja y hay
  contradicción fuerte → `incorrect`; si solo débil → `suspect`; sin
  datos/sentidos → `unknown`. Las unidades multi-palabra se abstienen (nunca
  riesgo de falso `incorrect`).
- **`score_transfer_attempt` 2.0 (`services/lexicon.py`, P1-02).**
  `score_transfer_attempt(word, text, *, pos="", senses=())` mantiene
  `passed`/`lexical_transfer` y devuelve `adequacy ∈ fit|suspect|incorrect|
  unknown`; `error_type`: `incorrect → semantic_mismatch`, `suspect →
  semantic_doubt` (nueva const `SEMANTIC_DOUBT_ERROR`, añadida a
  `TRANSFER_ERROR_TYPES`); `fit`/`unknown` no cambian el `error_type` léxico.
  `semantic_fit: bool | None` se conserva (`None` en `unknown`, `False` en
  `suspect`/`incorrect`). `score_write_attempt` NO cambia su contrato exacto (4
  claves).
- **Clean success (`services/evidence.py`, P1-02).** `context_signals` excluye
  SOLO `error_type == semantic_mismatch`. `semantic_doubt` cuenta como éxito
  limpio (advisory) y por tanto `transfer`/`transfer_state` avanzan con él; la
  paridad pura↔SQL se mantiene por construcción (`summarize_by_target` reutiliza
  `context_signals`).
- **Plumbing (`domain/vocabulary.py`, P1-01).** `submit_transfer_attempt` lee
  `senses` de la caché junto a `pos` y los pasa al scorer; si el ítem tiene
  `lexical_unit` distinta de la superficie se prefieren los sentidos de la
  unidad (fallback a la superficie). `_build_dictionary_entry` expone `senses` de
  forma aditiva.
- **Contratos y UI (aditivos).** `schemas/vocabulary.py`: `DictionarySenseOut` +
  `DictionaryEntryOut.senses`; documentado que `adequacy` gana `incorrect` y que
  `suspect` guarda `semantic_doubt`. `types/api.ts` añade `DictionarySense`/`senses`
  y amplía `adequacy`; `wordDrill.tsx` muestra
  `dictionary.drill.transferSemanticWrong` para `incorrect` (tono warning, sin
  bloquear `onProduced`, porque la evidencia léxica sigue siendo real) e i18n
  (`es`/`en`) con paridad. Sin endpoints nuevos ni migración.

## Tests

- Backend pytest **2020 passed** (+31): nuevos `test_senses_v344.py` (contrato de
  `normalize_senses`, derivación del `pos` superior, prompts y bump, round-trip
  de `senses_json` en ambas tablas, corrupción tolerada y migración idempotente
  con BD legacy) y `test_transfer_v344.py` (regresión P1-01 con `plan`
  `{noun, verb}` + «I plan my trip» → `fit`; `bank` solo-noun usado como verbo →
  `incorrect`/`semantic_mismatch`; cue débil → `suspect`/`semantic_doubt`; sin
  sentidos → `unknown`; clean success con `semantic_doubt` y no con
  `semantic_mismatch`; `transfer_state`; paridad pura↔SQL; endpoints con
  sentidos y lookup). Se ajustan `test_transfer_v343.py` (nueva taxonomía y
  regla de clean success), `test_dictionary_content_v330.py` y
  `test_situational_cue_v338.py` (`GENERATOR_VERSION` 1.4.0 y `senses` en el
  contrato).
- Frontend vitest **70 ficheros/608 tests** (+1): `wordDrill.test.tsx` cubre
  `adequacy: "incorrect"` con su aviso propio y confirma que `suspect` no
  bloquea. Verificación: `pytest` 0 fallos, `ruff check backend/` limpio,
  `npm run test`, `npx tsc --noEmit`, `npm run build` y
  `check_release_consistency` **3.44.0** exit 0.

## Fuera de alcance (V3.45+)

- `transfer_condition` (`prompted`/`cued_context`/`open_context`/`free_choice`/
  `naturally_emergent`).
- CEFR/`difficulty_vector` del contexto y Context Bank 2.0.
- `expected_learning_value` / Adaptive Planner 2.0 y Student Model
  multidimensional.
- R8/R9 de la CONSTITUCIÓN y cualquier decisión que dé al LLM autoridad sobre el
  Student Model.

## Decisiones de diseño

- **Los sentidos son CONTENIDO, no evidencia.** Se generan una vez por el modelo
  local y se cachean; el scoring los consume de forma determinista, sin LLM en el
  camino de la evidencia (premisa 21).
- **Un heurístico nunca destruye evidencia objetiva.** `incorrect` bloquea solo
  el clean success; `passed`/`lexical_transfer` conservan su semántica.
- **Compatibilidad total.** Sin `senses` (caché legacy o modelo que no los da) se
  cae a la `pos` global y, si tampoco hay, a `unknown`, que nunca bloquea.
