# v3.31.1 — Cierre de la auditoría V3.31.0: `pick_model` con explícito instalado, negative cache, rate limit y tope del dueño del vuelo

**Patch de endurecimiento del diccionario de consulta tras la auditoría
profunda de V3.31.0: el modelo explícito debe estar INSTALADO (no solo ser
utilizable), los fallos de generación dejan de reintentar en bucle (negative
cache con TTL), la generación de contenido nuevo queda limitada por usuario y
global, y el dueño de un vuelo ya no puede dejar la palabra clavada si Ollama
se cuelga (tope servidor de 90 s).**
Versión de app `3.31.0 → 3.31.1`. Solo backend + docs; sin cambios de UI ni de
esquema de BD (todo el estado nuevo es en memoria, best-effort por proceso).

## Qué cambia

### 1. `pick_model` exige modelo explícito INSTALADO (`services/translate.py`)

La auditoría de V3.31.0 dejó un P1-01 residual: `pick_model` devolvía un modelo
explícito con solo comprobar que no estuviera en `config.UNUSABLE_MODELS`; la
comprobación de instalación solo ocurría en el fallback. Un cliente podía pedir
`model="llama3.1:8b"` sin tenerlo instalado y la llamada llegaba a Ollama (en
el diccionario, degradación evitable a `definition_source="none"`; en
traducción, error 502).

- `pick_model` consulta ahora siempre `installed_models()` (caché en memoria de
  300 s, sin coste por frase) y solo devuelve el explícito si **está instalado
  y es utilizable**; si no, cae al mismo fallback automático que un modelo no
  explícito (preferido instalado → primer utilizable instalado → por defecto).
  La semántica queda: el explícito es una *preferencia segura*, nunca una orden
  que pueda llegar a un modelo inexistente.
- `test_translate.py` se hace hermético: el fixture inyecta por defecto un
  parque con `llama3.1:8b` instalado (los tests que necesitan otro lo
  sobrescriben) y se añaden 3 casos negativos: explícito utilizable pero NO
  instalado → cae al preferido instalado; sin preferidos → primer usable
  instalado; sin ningún modelo → por defecto.

### 2. Negative cache del generador (`domain/vocabulary.py`)

Un fallo de generación (Ollama caído, respuesta inválida, timeout) marca la
palabra en memoria durante `DICTIONARY_NEGATIVE_CACHE_TTL_SECONDS` (30 s). Las
consultas siguientes degradan a `definition_source="none"` **sin volver a
llamar al modelo**; la entrada expira de forma perezosa al vencer el TTL o se
limpia en cuanto una generación consigue contenido. Evita la tormenta
`cat → retry → cat → retry` cuando el modelo está caído. El single-flight se
mantiene: si la palabra está en negative cache, el dueño del vuelo degrada y
los waiters reciben el mismo None.

### 3. Rate limit de generación nueva (por usuario y global)

`DICTIONARY_MAX_GENERATIONS_PER_USER_MINUTE` (10) y
`DICTIONARY_MAX_GENERATIONS_PER_MINUTE_GLOBAL` (40) limitan las palabras NUEVAS
por minuto (el caché evita repeticiones, no cardinalidad). Aplicación: solo el
dueño de un vuelo genera, así que cada palabra consume cupo una vez y las
palabras ya cacheadas no consumen. Sin cupo → degradación normal (200 con
`definition_source="none"`), nunca un error 5xx. Es un límite local por proceso
(suficiente para la app de un solo proceso en LAN; igual que el single-flight,
si mañana hay varios workers el límite correcto pasa a la BD/lock distribuido).

### 4. Tope servidor del dueño del vuelo

La generación del dueño se envuelve en `asyncio.wait_for` con
`DICTIONARY_GENERATION_TIMEOUT_SECONDS` (90 s). Antes, los waiters tenían su
tope defensivo de 60 s pero el dueño no: un Ollama colgado podía dejar el vuelo
de la palabra en curso indefinidamente (los waiters degradaban a None a los
60 s, pero la entrada `_inflight_content[word]` no se liberaba hasta que el
dueño terminara). Ahora el dueño también tiene tope: al agotarlo degrada, se
marca la negative cache y el vuelo se libera (ningún Future huérfano).

### 5. Semántica documentada del contenido canónico

La caché `dictionary_entries` es global y canónica y no lleva `model_id`: una
definición/traducción vale para cualquier usuario y cualquier modelo. Se
documenta en los docstrings de `services/dictionary_content.py`,
`domain/vocabulary.py` y `schemas/vocabulary.py` que el parámetro `model` de la
consulta NO elige «con qué modelo se sirve mi contenido»: significa «si hay que
generar contenido nuevo, prefiero este modelo». No se añade `model_id` a la
caché (decisión de la auditoría).

## Verificación

- Backend: `pytest` → **1708 passed** (+11 sobre v3.31.0: 3 de `pick_model`
  con explícito no instalado en `test_translate.py` y 8 del nuevo
  `test_dictionary_hardening_v3311.py`: la negative cache suprime el reintento
  inmediato y expira, el éxito limpia la marca, el cupo por usuario bloquea
  palabras nuevas pero no las cacheadas, el cupo global se comparte entre
  usuarios, sin cupo nunca lanza, el timeout del dueño degrada y libera el
  vuelo, y ninguna ruta crea evidencia — D3 intacto) + `ruff check .` limpio.
- Frontend: `vitest` (suite completa) + `tsc --noEmit` limpio; sin cambios de
  UI ni de contrato HTTP.
- `python scripts/check_release_consistency.py` → **3.31.1** exit 0.

## Documentación

- `PLAN.md`: hito estable V3.31.1 al frente de «Estado actual» y cierre en
  «Siguiente incremento»; el candidato Dictionary → Learning Bridge sigue en
  **V3.32** (`agentes/v332-dictionary-learning-bridge.md`).
- `CHANGELOG.md` con la entrada `[3.31.1]`; nota de cierre en `docs/RELEVO.md`.
