# v3.31.0 — Cierre de la auditoría V3.30.1: robustez del single-flight, invalidación de la caché legacy y contrato del diccionario

**Release de estabilización que cierra los hallazgos residuales de la auditoría
profunda de V3.30.1 sobre el diccionario de consulta: el single-flight ya no
puede colgar a los waiters si el dueño del vuelo se cancela, el contenido de
caché previo a V3.31 (indistinguible por fila, posiblemente generado con el
parser greedy de V3.30) deja de servirse como fresco y regenera una sola vez, y
el contrato del diccionario queda blindado en ambos lados: tests de la
migración de upgrade y del path real con modelo no utilizable en backend, tipo
`DictionaryLookupRequest` + test del endpoint + timeout en el cliente.**
Versión de app `3.30.1 → 3.31.0`. Backend + frontend de contrato (tipos y API);
sin cambios de UI.

## Qué cambia

### 1. Single-flight robusto a cancelación (`domain/vocabulary.py`)

La auditoría encontró un caso límite del endurecimiento de V3.30.1: si el
primer cliente (dueño del vuelo de una palabra) se cancelaba a mitad de la
generación —p. ej. una desconexión—, su `CancelledError` (derivada de
`BaseException`) no la capturaba el `except Exception`, el `finally` retiraba la
clave del registro de vuelos **sin resolver el Future**, y los waiters que ya
estaban en `await asyncio.shield(fut)` se quedaban colgados indefinidamente.

- `_ensure_cached_content` captura ahora `asyncio.CancelledError`: resuelve el
  Future con `None` antes de propagar la cancelación (los waiters degradan a
  `definition_source="none"` y una consulta posterior regenera con normalidad).
- Los waiters esperan con un tope defensivo (`_INFLIGHT_WAIT_SECONDS = 60.0`,
  `asyncio.wait_for` + `shield`): si el ganador colgara por cualquier causa
  (Ollama sin responder), degradan a `None` en vez de esperar para siempre.
- Test negativo determinista `test_inflight_leader_cancel_resolves_waiters_without_hanging`
  (cancela al líder con sincronización por evento; fallaría con timeout de 1 s
  si el bug regresara).

### 2. Invalidación del contenido de caché previo a V3.31

V3.30.1 cambió el parser JSON (regex greedy → `raw_decode`) pero etiquetó el
contenido ya cacheado como `1.0.0`, la misma versión que el parser nuevo: el
contenido generado por el parser viejo quedaba servido como «fresco» y ya es
indistinguible por fila.

- `services/dictionary_content.py`: `GENERATOR_VERSION` sube a **`1.1.0`**
  (prompt + parseador + política POS). Todo el contenido cacheado antes de
  V3.31 deja de cumplir `_content_is_fresh` y **regenera de forma perezosa una
  sola vez** al primer lookup de cada palabra.
- `repositories/db.py`: la migración define **`DICTIONARY_LEGACY_VERSION =
  "1.0.0"`**, deliberadamente DISTINTA de la versión actual del generador, y la
  aplica (parámetro, no literal) a las filas sin versión de instalaciones que
  vengan de V3.30.x. El comentario de migración documenta la semántica: esas
  filas no se sirven como frescas.
- Test `test_legacy_content_regenerates_lazily_once`: una entrada con la marca
  LEGACY regenera una vez y sobrescribe la fila con la versión actual.
- Test `test_migration_upgrade_from_v330_adds_version_and_keeps_content`:
  simula una BD creada por V3.30.0 (tabla `dictionary_entries` sin la columna)
  y verifica la migración aditiva (`ALTER` con guarda `PRAGMA table_info`),
  conservación del contenido, backfill a la marca LEGACY, idempotencia en
  re-arranque y que el dominio NO la sirve como fresca.

### 3. Blindaje del path real del diccionario con modelo no utilizable

- Test `test_dictionary_path_never_uses_unusable_explicit_model`: ejercita la
  cadena real `lookup_dictionary → _ensure_cached_content → _fetch_chat →
  translate.pick_model` (con `llm.chat_once` y `installed_models` inyectados,
  sin Ollama) pidiendo un modelo explícito en `config.UNUSABLE_MODELS`
  (`qwen3.5:9b`) y verifica que **nunca llega a `chat_once`** — el fallback de
  `pick_model` lo descarta. Cubre el hueco que dejaban los tests de V3.30.1,
  que inyectaban el fetcher por debajo de la llamada a `pick_model`.

### 4. Contrato del cliente anclado y timeout (`frontend`)

- `types/api.ts`: nuevo tipo `DictionaryLookupRequest` (`word` + `model?`) y
  cuerpo tipado en `lookupDictionaryWord` (un campo requerido nuevo del backend
  rompería `tsc`, no pasaría desapercibido).
- `api/vocabulary.test.ts`: test del contrato HTTP del diccionario que verifica
  `POST /api/vocabulary/dictionary?user_id=…`, header
  `Content-Type: application/json` y body `{ word }` (un cambio accidental a
  GET/otra query/otro body rompería CI).
- `api/vocabulary.ts`: la llamada se envuelve en `withTimeout` (120 s, etiqueta
  «dictionary lookup») para que la tarjeta no se quede en «cargando» para
  siempre si Ollama se cuelga (el servidor ya acota a 60 s la espera de los
  waiters del vuelo).

## Verificación

- Backend: `pytest` → **1697 passed** (+4 sobre v3.30.1: cancelación del líder
  del vuelo sin colgar a los waiters, path real del diccionario con modelo
  explícito no utilizable, regeneración del contenido LEGACY, migración de
  upgrade desde una BD V3.30.0) + `ruff check .` limpio.
- Frontend: `vitest` (suite completa) + `tsc --noEmit` limpio; sin cambios de
  UI (solo tipos y API del diccionario).
- `python scripts/check_release_consistency.py` → **3.31.0** exit 0.

## Documentación

- `PLAN.md`: hito estable V3.31 al frente de «Estado actual» y cierre en
  «Siguiente incremento»; el candidato Dictionary → Learning Bridge se mueve a
  **V3.32** (`agentes/v332-dictionary-learning-bridge.md`).
- `CHANGELOG.md` con la entrada `[3.31.0]`; nota de cierre en `docs/RELEVO.md`.
