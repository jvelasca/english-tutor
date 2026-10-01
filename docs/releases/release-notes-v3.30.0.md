# v3.30.0 — Diccionario de consulta con marca de uso y aprendizaje: definición/traducción por el modelo local con caché persistente, ejemplo determinista del banco y estado de la palabra en el hub Vocabulario

**V3.30 cierra el candidato homónimo (diseño en
`docs/DISENO-V330-DICCIONARIO-CONSULTA.md`, decisiones D1/D2/D3): cualquier
palabra puede consultarse —esté o no en el léxico del alumno— y la respuesta
combina la marca de uso/aprendizaje derivada en servidor, una frase de ejemplo
determinista del banco y la definición/traducción generadas por el modelo local
y cacheadas en la tabla global `dictionary_entries`. Es contenido, no
evidencia (premisa 21): la consulta es solo lectura y nunca mueve mastery ni el
ledger. Implementado en tres fases: núcleo determinista (A), generador LLM con
caché y degradación (B) y la vista «Consultar» en la UI (C).**
Versión de app `3.29.0 → 3.30.0`.

## Qué cambia

### Fase A — Núcleo determinista sin LLM (backend)

- Migración idempotente inline en `repositories/db.py`: tabla global
  `dictionary_entries(word PK, pos, definition, translation, created_at,
  updated_at)` — caché compartida de contenido generado, independiente del
  léxico por usuario.
- `repositories/dictionary.py`: `get_entry` (lectura) e `insert_entry`
  (inserción idempotente `INSERT OR IGNORE`, devuelve si hubo fila nueva).
- Esquemas `DictionaryLookupRequest`/`DictionaryEntryOut` (en
  `schemas/vocabulary.py`) + endpoint **`POST /api/vocabulary/dictionary?user_id=…`
  con `{word}`** → `DictionaryEntryOut`: `word`, `definition`/`translation`/
  `definition_source` (`"cache"` | `"llm"` | `"none"`), `kind`/`cefr` del
  léxico, `example` determinista (frase + audio hash + `source` del banco) y
  `usage` con marca de uso/aprendizaje.
- Marca de uso/aprendizaje (D3, solo lectura, sin eventos): si la palabra
  existe en el léxico del alumno se agrega por **forma** (`status`/
  `mastery`/`recall`, contadores `produced`/`exposed`, matriz de competencia
  por destreza con `competent`/`chips`); si no, se busca el ítem canónico cuya
  `lexical_unit` coincide y se agrega por **unidad** (superficies que la
  realizan + contadores agregados). La normalización acota la búsqueda a
  cabeceras canónicas con `^…$` y evita matchear `say` contra `essay`.
- Frase de ejemplo determinista: `services/example_sentences.py` sirve la
  primera frase del banco por nivel que contiene la forma (evita siempre la
  plantilla del drill); `"unavailable"` si no hay candidata (solo uso).

### Fase B — Generador de contenido con el modelo local + caché

- `services/dictionary_content.py` (patrón de `services/translate.py`):
  prompt estructurado que pide UN objeto JSON `{pos, definition, translation}`
  (definición EN en inglés simple, traducción ES neutra, POS en vocabulario
  canónico), llamada `llm.chat_once` con `temperature=0` y la misma política de
  elección de modelo (rápido instalado, nunca `config.UNUSABLE_MODELS`).
  `parse_content` tolera cercas de Markdown/texto circundante, normaliza POS
  (`""` si no es válido) y valida límites; `ContentUnavailableError` separa
  fallos de modelo/parseo para la degradación.
- `domain/vocabulary.py::lookup_dictionary` orquesta: caché → si no hay
  definición, genera con el modelo y persiste `INSERT OR IGNORE` (la primera
  consulta de cada palabra paga el modelo; las siguientes son deterministas).
  Degradación controlada: modelo caído o respuesta inválida → 200 con
  `definition_source="none"` (uso y ejemplo se siguen sirviendo); si persistir
  falla se sirve el contenido en memoria (persistencia opcional).

### Fase C — Vista «Consultar» en el hub Vocabulario

- `frontend/src/features/vocabulary/DictionaryLookup.tsx`: caja de búsqueda
  accesible (Enter/botón), validación local previa al envío, estados
  vacío/cargando/error de red con reintento/entrada inválida/«perfil
  requerido», y tarjeta de resultado con: palabra + `kind`/CEFR + POS + audio
  TTS, definición EN, traducción ES, ejemplo del banco con audio, y la sección
  de uso (badge de estado, recall, contadores, chips de competencia o agregado
  por unidad cuando la forma canónica difiere de la buscada). Con modelo caído
  la tarjeta sigue mostrando uso y ejemplo (`definition_source="none"`).
- `QuizRoutePage` admite la vista alterna `{ kind: "lookup" }` y, cuando hay
  diccionario personal + consulta, muestra un conmutador; solo Vocabulario
  declara la configuración (`dictionaryLookup` en
  `VocabularyRoutesPractice.tsx`).
- API y tipos: `lookupDictionaryWord` en `api/vocabulary.ts` + `DictionaryEntry`
  y amigos en `types/api.ts`; claves i18n `dictionary.lookup.*` (es/en).

## Verificación

- Backend: `pytest backend/tests` → **1684 passed** (39 tests nuevos del
  diccionario en `test_dictionary_lookup.py` y `test_dictionary_content_v330.py`:
  contrato del endpoint, marca por forma/unidad, ejemplo determinista,
  normalización, parseo del generador, caché/regeneración, idempotencia,
  degradación y read-only sobre `vocabulary`/`vocabulary_events`) + `ruff
  check .` limpio.
- Frontend: `vitest run` → **538 passed** (63 archivos, incluido
  `DictionaryLookup.test.tsx`), `tsc --noEmit` limpio y `vite build` OK.
- `python scripts/check_release_consistency.py` → **3.30.0** exit 0.

## Documentación

- Dossier de diseño con el estado de fases: `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`.
- `PLAN.md`: hito estable V3.30 al frente de «Estado actual» y candidato
  cerrado en «Siguiente incremento» (los diferidos quedan abiertos hacia V3.31).
- `CHANGELOG.md` con la entrada `[3.30.0]`.
