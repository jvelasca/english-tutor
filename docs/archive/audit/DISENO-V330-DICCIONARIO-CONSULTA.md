# Documento de diseño — V3.30: Diccionario de consulta con marcas de uso y aprendizaje

> **Estado:** dossier de diseño (alcance y decisiones cerradas por el gerente, 2026-09-09).
> **Fase A (núcleo determinista, sin LLM) implementada y verificada (2026-09-09):**
> `POST /api/vocabulary/dictionary` sirve marca de uso/aprendizaje (forma + unidad),
> frase de ejemplo determinista y lectura de la caché `dictionary_entries`
> (`definition_source="none"`). Briefing de ejecución:
> `agentes/v330-diccionario-fase-a.md`.
> **Fase B (generador LLM + caché) implementada y verificada (2026-09-09):**
> `services/dictionary_content.py` genera `{pos, definition, translation}` con el modelo
> local (`temperature=0`, prompt JSON, parseo tolerante y degradación a
> `ContentUnavailableError`); el dominio persiste con `INSERT OR IGNORE` en
> `dictionary_entries` y la 1.ª consulta es la única que paga el modelo (las siguientes
> son deterministas). Modelo caído o respuesta inválida → 200 con
> `definition_source="none"`. pytest backend **1684 passed** (25 tests nuevos en
> `backend/tests/test_dictionary_content_v330.py`) + `ruff check .` limpio.
> **Fase C (UI «Consultar») implementada y verificada (2026-09-09):**
> `DictionaryLookup.tsx` + `DictionaryLookup.test.tsx` (6 tests) en el hub Vocabulario
> (APRENDER → Vocabulario): vista alterna «Consultar» junto al diccionario personal
> (conmutador en `QuizRoutePage`, solo Vocabulario la declara), cliente
> `lookupDictionaryWord` + tipo `DictionaryEntry`. Feature **publicada en v3.30.0**
> (2026-09-09): release `3.29.0 → 3.30.0` (CHANGELOG `[3.30.0]`,
> `release-notes-v3.30.0.md`, `check_release_consistency` exit 0, pytest backend
> **1684 passed** + ruff limpio, vitest **538 passed** (63 archivos) + `tsc
> --noEmit` limpio).
> Fuentes: candidato en `PLAN.md` → «Siguiente incremento»; notas de cierre V3.27–V3.29 de
> `docs/RELEVO.md`. Antes de implementar, leer `docs/PREMISAS.md` (fuente de verdad) y la
> sección de proceso de `docs/RELEVO.md`.

## 1. Resumen ejecutivo

El alumno encuentra palabras desconocidas en toda la app (mensajes del tutor, frases de
rutas, transcripts de listening) y hoy solo dispone de:

1. **Traducción de frase completa EN→ES** a demanda (`POST /api/translate`), sin registro de
   evidencia ni estado de la palabra;
2. **Personal Dictionary** (`GET /api/vocabulary/lexicon`), que lista **solo** las palabras
   que la app ya registra (curriculum sembrado, expuestas o producidas) con su estado, pero
   sin dar el *significado* de la palabra y sin permitir consultar una palabra **arbitraria**.

V3.30 añade un **diccionario de consulta**: el alumno busca **cualquier palabra** (esté o no en
su evidencia) y recibe:

- su **definición** en inglés simplificado + **traducción** al español, generadas por el
  **modelo local** (Ollama, premisa 2: 100 % local) **a demanda y cacheadas** en SQLite
  (la primera consulta paga la latencia; las siguientes son instantáneas y deterministas);
- una **frase de ejemplo determinista** extraída de los corpus de la app cuando la palabra
  existe en ellos (sin LLM, sin inventar significado);
- las **marcas de uso y aprendizaje** de esa palabra *en la app del alumno*, derivadas del
  modelo léxico existente (`vocabulary`, `services/lexicon.py`): si está registrada, su
  estado (`mastered/known/learning/weak`), contadores por superficie y unidad, y la matriz de
  competencia; si no, se marca como **nueva** (nunca registrada).

La consulta es **solo lectura** (decisión D3): no registra eventos, no mueve contadores, no
influye en mastery ni en la curva de olvido. La marca de uso es señal **decidida en servidor**
(premisa 21), reutilizando los mismos cómputos puros que ya usa `get_lexicon`.

### 1.1 Decisiones cerradas (2026-09-09)

| ID | Decisión | Opción elegida | Alternativas descartadas (por qué) |
|---|---|---|---|
| **D1** | Fuente de definición/traducción | **LLM local a demanda con caché persistente en BD** (patrón de `services/translate.py`, ampliado con tabla `dictionary_entries`) | Dataset empaquetado: sin fuente con licencia y bilingüe EN→ES disponible, autoría enorme, desalineación con el léxico real de la app; descartado para V3.30. Solo traducción (sin definición): no aporta significado útil para palabras ambiguas; descartado. |
| **D2** | Punto de entrada del núcleo V3.30 | **Hub Vocabulario (APRENDER → Vocabulario): nueva vista alterna «Consultar»** junto a la actual «Diccionario personal» | Palabras tocables en transcripts/karaoke y en mensajes del chat: mismas piezas backend, pero integración UI de más superficies; se difiere como candidato V3.31 (frontera §9). |
| **D3** | ¿La consulta registra evidencia? | **No (solo lectura del histórico)** | Registrar `event_type="lookup"` en `vocabulary_events`: la consulta no es exposición ni producción del idioma y contaminaría la semántica del ledger (D5/E3); además es decisión de negocio reversible. Si algún día interesa «palabras que el alumno consulta», se añade como evento informativo nuevo (frontera §9). |

## 2. Contexto y problema

### 2.1 Qué hay hoy (verificado 2026-09-09 sobre v3.29.0)

- **Modelo léxico por forma superficial y por unidad.** La tabla `vocabulary` guarda una fila
  por `(user_id, word)` con contadores canónicos `production_count`/`exposure_count`, días
  distintos (`production_days`/`exposure_days`), contexto curricular (`cefr`/`level_id`/
  `objective_id`/`source`/`lemma`/`kind`) y desglose de producción por canal
  (`chat_prod`/`speaking_prod`/`writing_prod`/`conversation_prod`), además de la unidad léxica
  canónica `lexical_unit` (V3.25, P2-02) y las señales de retención por recuperación demorada
  (`retrieval_successes`/`retrieval_days`/`last_retrieval_at`, V3.23).
- **Servicio puro `services/lexicon.py`** — el mismo que alimenta el Personal Dictionary:
  `item_status`, `item_mastery`, `item_recall`, `item_competence_matrix`,
  `production_contexts`, `units_from_rows`/`summary_units` (agregado por `lexical_unit`).
- **Ledger `vocabulary_events`** (V3.26, F-B2): historia append-only por superficie con
  `event_type ∈ {produced, exposed, retrieval}`. Empezó en V3.26, **sin backfill**.
- **Traducción EN→ES de apoyo** (`backend/services/translate.py` + `POST /api/translate`):
  LLM local, `temperature=0`, elección de modelo rápido (`PREFERRED_TRANSLATION_MODELS`), caché
  **en memoria** por frase; `502` si el modelo no está disponible. Frontend: componente
  `PhraseTranslate`/`PhraseTranslateButton` usado en frases de rutas, listening y speaking.
- **UI del léxico** en APRENDER → Vocabulario (`QuizRoutePage` con modos alternos
  `assessment`/`dictionary`): la vista «Diccionario personal» la sirve
  `features/vocabulary/PersonalDictionary.tsx` (resumen por estado + matriz de competencia +
  CEFR + lista de ítems ordenados por `sortLexicalItems`). i18n bajo el namespace `dictionary.*`.
- **Corpus de frases** (`backend/curriculum/pronunciation_corpus.json`, corpora de listening/
  speaking/conversation) y `services/pronunciation_routes.py::sentence_context_for`, que hoy
  devuelve una frase que contiene la palabra desde el banco del nivel **o** una plantilla
  neutra «Say the word …» cuando el banco no la contiene.

### 2.2 Problemas concretos que resuelve V3.30

- P-1: no existe **significado por palabra**; la traducción disponible es solo por frase y no
  informa del uso de la palabra en la app.
- P-2: el Personal Dictionary **no permite consultar palabras nuevas** (una palabra que el
  alumno acaba de oír en el tutor y no está registrada no aparece en ningún sitio).
- P-3: el estado de aprendizaje de una palabra **está enterrado en listas largas**; el alumno
  no tiene una respuesta directa a «esta palabra, ¿la he usado? ¿la domino?».
- P-4: no hay **ejemplo real** contextual de la palabra procedente del contenido de la app.

## 3. Propuesta (qué se construye)

### 3.1 Endpoint backend

`POST /api/vocabulary/dictionary` (en `backend/routers/vocabulary.py`, junto al resto del
léxico), cuerpo `{word, model?}` y respuesta tipada:

```json
{
  "word": "break",
  "kind": "word",
  "cefr": "A2",
  "definition_source": "llm",
  "pos": "verb",
  "definition": "to separate into pieces, often suddenly; to stop working for a short time.",
  "translation": "romper",
  "example": {
    "phrase": "I need a break after two hours of study.",
    "source": "pronunciation_corpus",
    "level": "A2"
  },
  "usage": {
    "tracked": true,
    "surface": {
      "status": "learning",
      "mastery": 0.42,
      "recall": 0.61,
      "next_review_days": 2,
      "production_count": 2,
      "exposure_count": 7,
      "production_channels": ["chat", "speaking"],
      "competence": {
        "recognition": true,
        "production": true,
        "transfer": false,
        "retention": false,
        "production_gap": false,
        "transfer_gap": true
      },
      "last_activity_at": "2026-09-08T18:02:11Z"
    },
    "unit": {
      "lexical_unit": "break",
      "status": "learning",
      "surface_count": 1,
      "mastered_surfaces": 0,
      "recognized": true,
      "produced": true,
      "transfer": false
    }
  }
}
```

Para una palabra **no registrada** en la app, `usage.tracked=false`,
`usage.status=null` (contrato «nueva»), y el resto de campos de `usage` van a 0/`null`.
Si el modelo local no está disponible, `definition_source="none"`, `definition=null`,
`translation=null` y la respuesta se sirve **igualmente** con la marca de uso y el ejemplo
(la UI muestra el estado de error/retry del contenido, no un fallo duro).

### 3.2 Reglas de la marca de uso (determinista, premisa 21)

- La marca se calcula **solo con datos del servidor**: filas de `vocabulary` del usuario que
  matchean la palabra buscada, reutilizando `services/lexicon.py` (mismos cómputos puros de
  `get_lexicon`). **No hay lógica de estado en el cliente**.
- **Granularidad por forma y por unidad** (decisión de granularidad que ya soporta el modelo):
  - `usage` describe la **forma superficial** exacta buscada (p. ej. `going`);
  - `usage.unit` describe el agregado por `lexical_unit` cuando la forma pertenece a una
    unidad con más de una superficie o cuando la forma buscada coincide con su `lexical_unit`
    (p. ej. `go`). Si no aplica, `unit=null`.
- Normalización de la búsqueda: minúsculas, recorte de puntuación circundante y espacios
  (reutiliza la semántica de `lexicon.lexical_unit`/`classify`); longitud máxima acotada.
- La búsqueda **no crea filas** en `vocabulary` y **no** se añade ningún `event_type` nuevo al
  ledger (D3).

### 3.3 Contenido generado (D1)

- **Generador** `services/dictionary_content.py` (nuevo), análogo a `services/translate.py`:
  - *Modelo:* se reutiliza la política de `translate.pick_model` (modelo rápido instalado
    primero; nunca modelos de `config.UNUSABLE_MODELS`), porque la consulta es interactiva.
  - *Prompt:* devuelve **solo** un objeto JSON `{"pos": "noun|verb|adjective|…",
    "definition": "<definición EN en inglés simple, 1–2 frases>", "translation":
    "<traducción ES neutra>"}`; `temperature=0`.
  - *Validación:* parseo tolerante del JSON (regex del bloque `{…}`), longitudes acotadas y
    campos opcionales. Si el parseo/validación falla, se trata como «modelo no disponible»
    (degradación, nunca 500 por contenido).
- **Caché persistente** (nuevo `repositories/dictionary.py` + tabla global
  `dictionary_entries`):
  - La definición es **contenido de idioma, no evidencia de alumno** → la tabla es **global**
    (no por usuario): una vez generada, cualquier usuario la lee sin pagar el LLM.
  - `INSERT OR IGNORE` idempotente; si la entrada existe, se devuelve sin llamar al modelo
    (determinismo y ahorro de latencia tras la primera consulta).
  - Nunca se persiste una generación fallida (degradación limpia y reintento posible).
  - Creación de tabla idempotente en `repositories/db.py::init_db` con el patrón
    `CREATE TABLE IF NOT EXISTS` usado por `vocabulary_events`.

### 3.4 Frase de ejemplo determinista

`services/example_sentences.py` (nuevo, puro):

- Índice en memoria (cargado una vez) sobre las frases `script` de los corpus de la app
  (`pronunciation_corpus.json` y, si aportan, listening/conversation), mapeando cada palabra
  del script a la frase que la contiene (misma normalización/alineación que
  `unit_produced`).
- `example_for(word)` devuelve `{"phrase", "source", "level"}` de la **primera frase real
  que contiene la palabra** o `null` si no existe. **Nunca** la plantilla neutra «Say the
  word …» (esa semántica es del micro-drill y no debe colarse en un ejemplo de diccionario).

### 3.5 UI (D2)

- Nueva vista alterna **«Consultar»** en APRENDER → Vocabulario, junto a «Diccionario
  personal». Se registra como un modo más en `QuizRoutePage` (tipo `kind: "lookup"` en la
  unión de vistas, con su CTA/hint), pero **solo** el config de Vocabulario la declara — el
  resto de destrezas no se toca.
- Componente `frontend/src/features/vocabulary/DictionaryLookup.tsx` (nuevo):
  - *Estados obligatorios* (premisa 14): vacío con hint, cargando, error de red con retry,
    y error de contenido (modelo caído) con la tarjeta de uso servida igualmente.
  - *Caja de búsqueda*: input (submit con Enter y botón), accesible, con ejemplo visible.
  - *Tarjeta de resultado*: palabra + `pos`/CEFR/kind (badges), botón de audio de la palabra
    (`ListenButton` existente), definición EN en `lang="en"`, traducción ES, frase de ejemplo
    con su botón de audio y nota de fuente («ejemplo del banco de la app»); a continuación la
    **sección de uso**: si `tracked=false`, badge «Aún no registrada en tu app»; si
    `tracked=true`, badge de estado reutilizando la taxonomía y colores de `PersonalDictionary`
    (`STATUS_TONE`), barra de recall, chips de competencia (Recognized/Produced/Transfer/
    Retention) y detalle de última actividad.
  - *i18n*: claves `dictionary.lookup.*` en es/en (con paridad, como exige
    `i18n.parity.test.ts`).
  - *Responsive y a11y* según premisas 14/20 (verificable a 3 viewports).
- Cliente API: `frontend/src/api/vocabulary.ts` gana `lookupDictionaryWord(userId, word)` y el
  tipo `DictionaryEntry` en `types/api`.

## 4. Estado actual — referencias de código (anclas para el subagente)

- Modelo de datos y semántica por superficie/unidad:
  `backend/repositories/db.py` (tablas `vocabulary`/`vocabulary_events` y migraciones
  idempotentes, patrón `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`);
  `backend/repositories/vocabulary.py` (`get_vocabulary`, `record_production`,
  `record_exposures`, `seed_curriculum_items`, ledger `_insert_event`).
- Cómputos puros de estado/competencia/unidad:
  `backend/services/lexicon.py` (`item_status`, `item_mastery`, `item_recall`,
  `item_competence_matrix`, `units_from_rows`, `summary_units`, `LEXICAL_KINDS`).
- Orquestación de dominio y contrato actual:
  `backend/domain/vocabulary.py` (`get_lexicon`, `record_production_text`,
  `get_sentence_context`) y `backend/schemas/vocabulary.py` (`LexiconOut`,
  `LexicalItemOut`, `LexicalUnitOut`, `LexicalCompetence`).
- Patrón de contenido LLM local con caché y degradación:
  `backend/routers/translate.py` y `backend/services/translate.py` (`pick_model`,
  `PREFERRED_TRANSLATION_MODELS`, caché en memoria, `temperature=0`).
- UI del léxico y modos alternos:
  `frontend/src/features/routes/QuizRoutePage.tsx` (vistas `assessment`/`dictionary`),
  `frontend/src/features/vocabulary/VocabularyRoutesPractice.tsx` (config con `dictionary`),
  `frontend/src/features/vocabulary/PersonalDictionary.tsx`.

## 5. Estructura de archivos (backend y frontend)

```
backend/services/dictionary_content.py    # NUEVO: prompt/parseo/validación del LLM (puro+async)
backend/services/example_sentences.py      # NUEVO: índice de frases reales de los corpus (puro)
backend/repositories/dictionary.py         # NUEVO: caché dictionary_entries (get/insert)
backend/repositories/db.py                 # TOQUE: CREATE TABLE dictionary_entries (idempotente)
backend/domain/vocabulary.py               # TOQUE: lookup_dictionary(user_id, word, model=None)
backend/schemas/vocabulary.py              # TOQUE: DictionaryLookupRequest / DictionaryEntryOut
backend/routers/vocabulary.py              # TOQUE: POST /api/vocabulary/dictionary
backend/tests/test_dictionary_lookup.py    # NUEVO (pytest)
frontend/src/api/vocabulary.ts             # TOQUE: lookupDictionaryWord + tipo
frontend/src/types/api.ts                  # TOQUE: DictionaryEntry/DictionaryUsage
frontend/src/features/routes/QuizRoutePage.tsx   # TOQUE: vista alterna "lookup" (opcional para otras rutas)
frontend/src/features/vocabulary/VocabularyRoutesPractice.tsx  # TOQUE: declara lookup
frontend/src/features/vocabulary/DictionaryLookup.tsx          # NUEVO
frontend/src/features/vocabulary/DictionaryLookup.test.tsx     # NUEVO (vitest/jsdom)
frontend/src/utils/i18n.ts                 # TOQUE: claves dictionary.lookup.* es/en
```

## 6. Plan de implementación por fases (para el briefing del subagente)

- **Fase A — Núcleo determinista sin LLM.** ✅ Implementada y verificada (2026-09-09).
  Tabla `dictionary_entries`; `example_sentences`; `repositories/dictionary.py` (caché CRUD);
  normalización de palabra; agregado de `usage` desde `services/lexicon.py` sobre las filas de
  `vocabulary` del usuario. Schema + endpoint sirviendo una entrada **sin definición**
  (`definition_source="none"`) con `usage` y `example` correctos. 14 tests en
  `backend/tests/test_dictionary_lookup.py`.
- **Fase B — Contenido LLM con caché.** ✅ Implementada y verificada (2026-09-09).
  `services/dictionary_content.py` (prompt JSON, parseo tolerante, validación, límites,
  `ContentUnavailableError`) + integración en el dominio: `cache hit → no LLM`;
  `cache miss → generar → persistir → devolver`; `LLM caído/parseo fallido →
  definition_source="none"` sin perseguir error (si persistir falla se sirve en memoria).
  25 tests con generador inyectado (fake) en `backend/tests/test_dictionary_content_v330.py`
  (premisa 12: tests rápidos y deterministas).
- **Fase C — UI.** ✅ Implementada y verificada (2026-09-09). Vista «Consultar» en el
  hub Vocabulario (estados vacío/carga/error/contenido, degradación de contenido),
  tarjeta de entrada, sección de uso (forma y unidad), i18n, tests jsdom del
  componente (`DictionaryLookup.test.tsx`, 6 tests) y del cliente API. Conmutador
  «Diccionario personal / Consultar» en la vista alterna de `QuizRoutePage` (solo
  Vocabulario declara la vista). vitest **538 passed** + `tsc --noEmit` limpio.

## 7. Tests obligatorios (resumen; detalle en el briefing)

Backend (pytest, sin red ni modelo):
1. Normalización y límites de `word` (mayúsculas, puntuación, espacios, >80 chars → 422).
2. `usage` correcto para fila única (forma) y para unidad multi-superficie (`going` vs `go`).
3. Palabra sin evidencia → `tracked=false`/`status=null`; sin creación de filas en `vocabulary`
   y sin eventos nuevos en `vocabulary_events` (D3).
4. Aislamiento entre usuarios: misma palabra, marcas distintas por usuario; definición
   (caché global) compartida.
5. Caché: segunda consulta no llama al generador (generador fake contador de llamadas);
   `INSERT OR IGNORE` idempotente.
6. Degradación: generador lanza → respuesta 200 con `definition_source="none"` y el resto
   intacto; parseo inválido del LLM tratado igual.
7. `example_for` devuelve frase real que contiene la palabra o `null`; nunca la plantilla
   «Say the word …».
Frontend (vitest/jsdom): estados de la vista, render de marcas tracked/new, error de red con
retry, error de contenido (modelo caído) mostrando la tarjeta de uso, paridad i18n
(`dictionary.lookup.*`).

## 8. Alcance del release V3.30

**Dentro:** endpoint + caché + marca de uso + ejemplo determinista + definición/traducción
local (D1) + vista «Consultar» en el hub Vocabulario (D2) + tests + docs (PLAN/CHANGELOG/
README/RELEVO nota + `release-notes-v3.30.0.md`) + cierre de release (bump `3.29.0 → 3.30.0`,
`check_release_consistency` exit 0).

**Fuera (fronteras declaradas, no bugs):**
- Palabras tocables en transcripts/karaoke de listening y en mensajes del chat (candidato
  V3.31; la marca de uso y el endpoint quedan listos para reutilizarse).
- Registro de consultas (`event_type="lookup"`): decisión de negocio abierta, no se implementa
  en V3.30 (D3).
- Dataset de definiciones empaquetado y desambiguación multi-sentido del LLM (una acepción por
  consulta); diccionario bilingüe completo: frontera de contenido a largo plazo.
- Audio humano de la palabra en la tarjeta (sí se usa `ListenButton`/TTS existente; no se
  genera audio nuevo).
- Generar definiciones por lote para todo el léxico del currículo (backfill): opcional y
  posterior; la caché se rellena a demanda.

## 9. Resumen para el gerente

- V3.30 = **consultar el significado de cualquier palabra** (definición EN simple +
  traducción ES del modelo local, cacheadas en `dictionary_entries`) **más la respuesta a
  «¿la he usado?»** (marca de uso/aprendizaje determinista desde `services/lexicon.py`) y un
  **ejemplo real** del corpus de la app.
- Decisiones: **D1** LLM local con caché persistente · **D2** entrada en el hub Vocabulario
  (vista «Consultar») · **D3** solo lectura (sin evidencia nueva).
- Sin cambios en el modelo de evidencia ni en gates: la consulta no toca mastery, FSRS ni el
  ledger; premisa 21 intacta (toda la señal vive en servidor).
- Siguiente paso natural: briefing de subagente autocontenido (`agentes/*.md`) con el detalle
  de las fases A–C y ejecución incremental del release.
