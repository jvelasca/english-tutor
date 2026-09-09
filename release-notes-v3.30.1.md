# v3.30.1 — Endurecimiento del diccionario de consulta: single-flight, política de modelo y caché versionada

**Patch de la auditoría profunda V3.30.0: una sola generación LLM por palabra
en concurrencia (P1-01), la política `UNUSABLE_MODELS` ya no se puede saltar
pidiendo un modelo explícito (P1-02) y la caché global `dictionary_entries`
versiona su contenido (`generator_version`) para poder regenerarse cuando
cambie el prompt/política (P1-03). Además, el parser JSON de la respuesta del
modelo es robusto ante varios objetos o llaves en prosa (P2).**
Versión de app `3.30.0 → 3.30.1`. Solo backend + docs; la UI no cambia.

## Qué cambia

### P1-01 — Single-flight de generación (`domain/vocabulary.py`)

`_ensure_cached_content` mantiene un registro de vuelos en curso por palabra
(`_inflight_content: dict[str, asyncio.Future]`, un Future por proceso): si N
consultas llegan a la vez sobre la misma palabra sin caché fresca, la primera
crea el vuelo y genera; las demás esperan el mismo Future. Resultado: **exactamente
una llamada al LLM y una fila en BD por palabra** — la carrera que la
persistencia `INSERT OR IGNORE` no deduplicaba (protegía la fila, no la
generación). El vuelo cubre leer → generar → persistir → releer (re-lectura de
BD dentro del vuelo para no pisar lo que otra consulta haya persistido entre
medias); los waiters reciben el mismo resultado y un fallo de generación no
provoca reintentos en cascada (todos degradan a `definition_source="none"`).

### P1-02 — La política `UNUSABLE_MODELS` no se salta con un modelo explícito (`services/translate.py`)

`pick_model` solo respeta el modelo explícito si NO está en
`config.UNUSABLE_MODELS`; si lo está (p. ej. `qwen3.5:9b`), cae al mismo
fallback que una petición sin modelo: preferido rápido instalado → primer
utilizable instalado → `DEFAULT_MODEL`. Un único punto de política que corrige a
la vez el diccionario (delegaba en `pick_model`) y la traducción a demanda;
también corrige el caso de que un cliente pida deliberadamente un modelo que la
configuración declara no utilizable.

### P1-03 — Caché versionada (`dictionary_entries.generator_version`)

- `services/dictionary_content.py`: `GENERATOR_VERSION = "1.0.0"` (versión del
  prompt + parseador + política POS; subirla al cambiar cualquiera de ellos).
- `repositories/db.py`: columna aditiva `generator_version TEXT NOT NULL
  DEFAULT ''` en `dictionary_entries` + migración idempotente (patrón
  `PRAGMA table_info`) con backfill `'1.0.0'` del contenido existente — el de
  V3.30 se generó con el mismo prompt/política, así que no se regenera en vano;
  una versión futura distinta invalidará las entradas por comparación.
- `repositories/dictionary.py`: `save_entry` (upsert `INSERT ... ON CONFLICT
  (word) DO UPDATE`) sustituye a `insert_entry`: mismo camino de escritura para
  fila nueva y para entrada obsoleta, y `updated_at` pasa a significar «última
  escritura/regeneración» (deja de ser un campo muerto).
- `domain/vocabulary.py`: `_content_is_fresh` exige definición y
  `generator_version == GENERATOR_VERSION` para servir caché; una entrada
  obsoleta o legacy (`''`) se regenera y sobrescribe. Se elimina el riesgo de
  «contenido obsoleto permanente» de la caché.

### P2 — Parser JSON robusto (`services/dictionary_content.py`)

`parse_content` ya no usa la regex greedy `{.*}` (que ante `{…} texto {…}`
intentaba interpretar todo desde el primer `{` hasta el último `}`): barre el
texto con `json.JSONDecoder().raw_decode` en cada posición de `{` y toma el
PRIMER objeto JSON válido, conservando la tolerancia a cercas de Markdown y
texto alrededor. Si no hay ningún objeto válido, `ContentUnavailableError`
(degradación habitual).

## Verificación

- Backend: `pytest` → **1693 passed** (+9 tests: single-flight con 3 consultas
  simultáneas de la misma palabra → 1 generación y 1 fila; dos usuarios
  concurrentes → 1 generación con `usage` aislado; fallo concurrente → 1
  intento y degradación para todos; regeneración por `generator_version`
  obsoleta que sobrescribe la misma fila; reuso de versión fresca sin llamar al
  generador; parser con dos objetos JSON → usa el primero y con llaves en prosa;
  `pick_model` con explícito en `UNUSABLE_MODELS` → fallback) + `ruff check .`
  limpio.
- Frontend: sin cambios de código (solo bump de versión en
  `package.json`/`package-lock.json`).
- `python scripts/check_release_consistency.py` → **3.30.1** exit 0.

## Documentación

- `PLAN.md`: hito estable V3.30.1 al frente de «Estado actual» y pendientes
  hacia V3.31.
- `CHANGELOG.md` con la entrada `[3.30.1]`; nota de cierre en `docs/RELEVO.md`.
