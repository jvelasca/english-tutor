# v3.39.0 — Diccionario reversible EN↔ES + persistencia de la pestaña

**Fase 1 del plan maestro V3.39+ (diccionario reversible → Traductor → motor de
tarea óptima → transferencia real). Release ADITIVA que abre la primera fase: el
diccionario de consulta deja de ser unidireccional y gana la dirección ES→EN en
dos escalones (inversa instantánea sobre la caché + generación con el modelo
local solo si no hay coincidencia), y la pestaña Personal/Consultar se recuerda
entre sesiones. Una tabla nueva y todo el contrato HTTP aditivo; sin migración
destructiva, sin cambios de semántica en los campos existentes y sin tocar
scoring, FSRS ni evidencia (la consulta sigue siendo SOLO LECTURA, D3).**

Versión de app `3.38.1 → 3.39.0`. Backend (`repositories/db.py`,
`repositories/dictionary.py`, `services/dictionary_reverse.py` nuevo,
`services/dictionary_content.py`, `domain/vocabulary.py`,
`schemas/vocabulary.py`, `routers/vocabulary.py`) + frontend (`DictionaryLookup`,
`utils/dictionaryView.ts` y `hooks/useDictionaryView.ts` nuevos,
`DictionaryScreen`, `QuizRoutePage`, `api/vocabulary.ts`, `types/api.ts`, i18n) +
tests y docs. Contrato HTTP **aditivo**: `direction` (defecto `"en-es"`) en la
petición; `direction`/`alternatives` en la respuesta. El bump de
`GENERATOR_VERSION` 1.2.1 → 1.3.0 regenera una sola vez la caché directa previa.

## Contexto

El diccionario de consulta (V3.30) nació unidireccional **EN→ES**: se busca una
palabra inglesa y se devuelve su definición en inglés simple y su traducción al
español, con la caché global `dictionary_entries` indexada por la palabra
inglesa. La petición del proyecto era hacerlo **reversible** y, además, recordar
la pestaña activa (Personal / Consultar) entre sesiones.

El obstáculo de diseño era la PK de `dictionary_entries`:

```text
dictionary_entries    word (PK, INGLÉS) | pos | definition | translation | situation
                      ↑ una palabra española ("banco") tiene VARIAS traducciones
                      ↑ y list_entries() es el banco de distractores del MCQ
```

Cambiar la PK a un par (dirección, término) rompía `list_entries()`, que
`services/dictionary_mcq.py` usa como banco de candidatos de significado para el
paso de Recognition. La solución elegida evita tocar la caché directa:

```text
1. INVERSO INSTANTÁNEO   término ES → segmenta dictionary_entries.translation
                         (glosa múltiple, acentos, artículos) → palabras EN
                         (sin modelo, sin latencia)

2. GENERACIÓN (fallback) término ES → modelo local (prompt ES→EN) →
                         dictionary_reverse_entries (tabla PROPIA, aislada)
```

## Qué cambia

### 1. Inversa instantánea (`services/dictionary_reverse.py`, nuevo)

Servicio **puro** (recibe las filas ya leídas: sin I/O, sin BD, sin red) y
determinista:

- **Segmentación de la glosa** por `, ; / |`, descartando el contenido entre
  paréntesis (`"el perro (animal)"` → `perro`) y los artículos iniciales
  (`"la casa"` ≈ `"casa"`).
- **Plegado de acentos que conserva la eñe**: `camión` ~ `camion`, pero
  `año` ≠ `ano` (confundirlas sería un falso positivo grave).
- **Ranking**: coincidencia exacta (2) antes que parcial (1) y, a igualdad,
  alfabética; **sin duplicados**, conservando la grafía original.
- `match_translation(term, entries) -> list[str]` devuelve las palabras inglesas
  ordenadas por calidad de coincidencia.

### 2. Caché inversa aislada (`repositories/db.py`, `repositories/dictionary.py`)

Nueva tabla **aditiva e idempotente** (`CREATE TABLE IF NOT EXISTS`):

```text
dictionary_reverse_entries
  word (PK, ESPAÑOL normalizado) | english | pos | definition | situation
  | generator_version | created_at | updated_at
```

Aislada de `dictionary_entries`, así que `list_entries()` (banco de distractores
del MCQ) sigue conteniendo solo inglés — fijado por test. El repositorio expone
`get_reverse_entry`, `save_reverse_entry` (`ON CONFLICT DO UPDATE`, igual que la
directa) y `list_reverse_entries`.

### 3. Contrato de contenido 1.3.0 (`services/dictionary_content.py`)

- `GENERATOR_VERSION` **1.2.1 → 1.3.0**: una sola política de frescura para ambas
  direcciones; la caché directa previa se regenera una vez.
- Nuevo `_REVERSE_SYSTEM_PROMPT` (equivalente inglés + definición simple EN +
  enunciado situacional EN con hueco), `parse_reverse_content` (exige `english`,
  valida `pos`/`definition` y reutiliza el validador puro
  `services/situation.py`) y `generate_reverse_content`.
- La fontanería de generación (single-flight, negative cache, rate limit) se
  parametriza por dirección y se indexa por `(direction, word)`: EN→ES y ES→EN
  del mismo término son generaciones distintas (p. ej. `pie` existe en ambas
  lenguas).

### 4. Dominio y HTTP (`domain/vocabulary.py`, `schemas`, `routers`)

`lookup_dictionary(user_id, word, model, direction)`: para `es-en`, primero
`match_translation` sobre `list_entries()` y, si hay coincidencias, se sirve el
equivalente (y las **alternativas**) reutilizando el contenido directo del
inglés; si no, se genera y cachea el contenido inverso. `DictionaryEntryOut`
gana `direction`/`alternatives` y la petición `direction` (defecto `"en-es"`).
La marca de uso que se muestra es siempre la del **equivalente inglés**, que es
la palabra que el alumno aprende. La consulta NO registra evidencia (D3).

### 5. Frontend

- **Conmutador de dirección** en `DictionaryLookup`: EN→ES / ES→EN, con `lang` y
  placeholder por dirección. Al cambiar de dirección se invalida el resultado
  anterior (la palabra era de la otra lengua).
- **Tarjeta reetiquetada** en ES→EN: término español de cabecera, equivalente
  inglés como traducción con etiqueta «In English», definición en inglés y lista
  de `alternatives` («Other translations»).
- **Puente de práctica**: en ES→EN se practica SIEMPRE el término inglés
  (`entry.translation`), nunca el español; sin equivalente no se ofrece el CTA.
- **Persistencia de la pestaña** (`useDictionaryView` +
  `utils/dictionaryView.ts`): patrón doble como la apariencia — arranque
  inmediato desde `localStorage` (`english-tutor.dictionary-view`, válido sin
  perfil), hidratación desde `GET /api/settings` al cambiar de usuario y
  escritura a `localStorage` + `PUT /api/settings` (`dictionary_view`). Se
  integra en `DictionaryScreen` y en el conmutador incrustado de
  `QuizRoutePage` (coherencia entre ambas superficies).

## Compatibilidad

| Elemento | Antes | Ahora |
| --- | --- | --- |
| `POST /api/vocabulary/dictionary` | `{word, model?}` | `{word, model?, direction?}` (defecto `"en-es"`) |
| Respuesta | `word`, `translation`, … | + `direction`, `alternatives` |
| `dictionary_entries` | PK `word` (EN) | Intacta |
| `list_entries()` (MCQ) | Solo inglés | Solo inglés (test de aislamiento) |
| `GENERATOR_VERSION` | `1.2.1` | `1.3.0` (regeneración lazy única) |

Ningún campo existente cambia de semántica.

## Tests

- **Backend pytest 1910 passed** (+20). Nuevo `test_dictionary_reverse_v339.py`:
  normalización con eñe, glosa múltiple, ranking exacto > parcial, artículos,
  tolerancia a acentos, deduplicación, inversa instantánea sin modelo,
  generación/persistencia/caché/versionado, aislamiento del banco MCQ,
  degradación sin modelo, 422, solo lectura (sin `vocabulary`/`vocabulary_events`),
  `alternatives`, contrato por defecto `en-es` y `parse_reverse_content`.
  Actualizados `test_situational_cue_v338.py` (versión 1.3.0 + prompt inverso) y
  `test_dictionary_hardening_v3311.py` (claves de negative cache prefijadas por
  dirección).
- **Frontend vitest 68 ficheros/578 tests** (nuevos casos ES→EN en
  `DictionaryLookup.test.tsx`, `vocabulary.test.ts` con dirección y
  `DictionaryScreen.test.tsx` con arranque/hidratación/escritura),
  `tsc --noEmit` limpio.
- `ruff check backend/` limpio y
  `python scripts/check_release_consistency.py` → **3.39.0** exit 0.

## Fuera de alcance (fases siguientes)

- **Fase 2** — 5.º destino **Traductor** bidireccional por voz (tipo viaje) con
  voces Piper `es_*`.
- **Fase 3** — motor de tarea óptima por skill
  (`skill_priority`/`limiting_skill`/`select_task`), ruta de escritura
  `written_production` y robustez de señales.
- **Fase 4** — transferencia contextual real, actividad `spontaneous_use`,
  agregación por `lexical_unit` y descomposición de `wordDrill.tsx`.
