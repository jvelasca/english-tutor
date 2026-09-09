# Briefing — V3.30 Diccionario de consulta · Fase A (núcleo determinista, sin LLM)

> Rol: subagente implementador · Autocontenido: lee este briefing + `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`
> y las anclas de código citadas; no dependas del historial del chat.
> Fecha: 2026-09-09 · Release objetivo: v3.30.0 (todavía **sin** bump de versión).

## Objetivo

Implementar la **Fase A** del diccionario de consulta: el núcleo **determinista sin LLM**
(endpoint `POST /api/vocabulary/dictionary` que devuelve la marca de uso/aprendizaje de una
palabra + frase de ejemplo determinista del corpus + caché de contenido vacía
`definition_source="none"`), con tests primero. La **generación de definiciones por LLM es la
Fase B** (futura) y queda **fuera** de este briefing: no llames a ningún modelo ni introduzcas
prompts.

## Decisiones ya cerradas (no reabrir)

- **D1** fuente de definiciones = LLM local a demanda con caché persistente en BD (Fase B). La
  tabla `dictionary_entries` se crea en Fase A, pero solo para la lectura de caché
  (repositorio `get`); la escritura/generación llega en Fase B.
- **D2** punto de entrada = hub Vocabulario, vista «Consultar» (frontend, **fuera** de esta
  fase backend).
- **D3** la consulta es **solo lectura**: no crea filas en `vocabulary`, no escribe eventos en
  `vocabulary_events`, no mueve contadores/mastery.

## Alcance de esta fase (backend)

1. Tabla global **`dictionary_entries`** en `backend/repositories/db.py::init_db`
   (`CREATE TABLE IF NOT EXISTS`, como `vocabulary_events`):
   columnas `word TEXT PRIMARY KEY`, `pos TEXT NOT NULL DEFAULT ''`,
   `definition TEXT NOT NULL DEFAULT ''`, `translation TEXT NOT NULL DEFAULT ''`,
   `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL DEFAULT ''`. Sin FK (contenido de
   idioma global, no evidencia de alumno).
2. **`backend/repositories/dictionary.py`** (nuevo): `get_entry(word) -> dict | None`
   devolviendo la fila si existe (usa `_conn`/`_now` de `repositories.db` como el resto de
   repositorios). Sin `insert` todavía (llega en Fase B con el generador).
3. **`backend/services/example_sentences.py`** (nuevo, puro): `example_for(word) -> dict |
   None` que delega en `services/pronunciation_routes.sentence_context_for(word, level=None)`
   y devuelve `None` cuando su `source == "template"` (nunca la plantilla «Say the word …»);
   si es frase real del banco devuelve `{"phrase", "source": "pronunciation_corpus",
   "level"}`.
4. **`backend/domain/vocabulary.py`** (ampliar): `lookup_dictionary(user_id, word, model=None)`
   async que:
   - normaliza la palabra (minúsculas, recorte de puntuación en los extremos, colapso de
     espacios; si queda vacía → `ValueError`);
   - lee las filas de `vocabulary` del usuario (`repositories.vocabulary.get_vocabulary`) y
     busca: **forma superficial** exacta (`word == normalizada`) y **unidad léxica**
     (`lexicon.lexical_unit(row)`, agregado) cuando la forma buscada es la unidad canónica;
   - calcula `usage` reutilizando **solo** cómputos puros de `services/lexicon.py`
     (`item_status`, `item_mastery`, `item_recall`, `next_review_days`,
     `item_competence_matrix`, `production_channels`, `units_from_rows`); no dupliques esas
     señales;
   - `usage.tracked` = existe forma o unidad; `surface` (estado de la forma) cuando hay forma
     exacta; `unit` (estado del agregado por `lexical_unit`) **solo** cuando la unidad difiere
     de la forma buscada; ambos `null` si no hay evidencia (palabra «nueva»);
   - incluye `kind`/`cefr` de la fila del usuario cuando existe; para palabra nueva, `kind`
     con `lexicon.classify_kind(normalizada, source="vocabulary")` y `cefr=""`;
   - lee `dictionary_repo.get_entry(normalizada)` y expone `definition_source="llm"` solo si
     hay `definition` cacheada, en otro caso `"none"` (Fase B rellenará la caché; la lectura
     ya queda cableada);
   - añade `example` con `services.example_sentences.example_for(normalizada)`.
   - **No escribe nada.**
5. **`backend/schemas/vocabulary.py`** (ampliar): `DictionaryLookupRequest {word: str
   (min 1, max 80), model: str | None}`, `DictionaryExampleOut`, `DictionarySurfaceUsageOut`,
   `DictionaryUnitUsageOut`, `DictionaryUsageOut` (con `tracked`, `surface`, `unit`) y
   `DictionaryEntryOut` (`word`, `kind`, `cefr`, `definition_source: "llm"|"none"`, `pos`,
   `definition: str | None`, `translation: str | None`, `example`, `usage`). Reutiliza
   `LexicalStatus`/`LexicalCompetence` existentes.
6. **`backend/routers/vocabulary.py`** (ampliar): endpoint
   `POST /api/vocabulary/dictionary` (auth `current_user`); `ValueError` → 422.

## Criterios de aceptación (tests primero)

Backend (`backend/tests/test_dictionary_lookup.py`, pytest, aislado con `monkeypatch` +
`tmp_path` + `db.init_db()` como `test_vocabulary.py`, usuario con
`users_repo.create_user(...)`):

1. Normalización: «Hello!»→`hello`; «  LIVING room  »→`living room`; puntuación suelta («…»)
   → 422 en el endpoint.
2. Palabra producida (`vocabulary_repo.record_words`) → `usage.tracked=true`, estado y
   contadores correctos por forma; sin escritura nueva tras la consulta (mismos contadores) y
   sin filas en `vocabulary_events`.
3. Unidad multi-superficie: sembrar con `seed_curriculum_items` un lemma (p. ej. fila
   `country` con `lemma=country` en A1) → al buscar la unidad se ve `usage.unit`; al buscar
   una superficie desconocida que no existe (`going`) con filas solo de `go` → `tracked=false`
   salvo que la unidad canónica coincida (fijar el caso en el test según el modelo: la
   búsqueda es por forma exacta o unidad canónica).
4. Palabra nunca vista → `tracked=false`, `surface=null`, `unit=null`, `cefr=""`, `example`
   correcto (frase del banco que la contiene) cuando existe; `definition_source="none"`.
5. Aislamiento: dos usuarios, la misma palabra con evidencia en uno solo → marcas distintas;
   `dictionary_entries` es global (misma fila para ambos, si existe).
6. `example_for`: frase real que contiene la palabra o `None`; nunca la plantilla «Say the
   word …».
7. Schema/endpoint: respuesta `200` con la forma de `DictionaryEntryOut`; `word` > 80 → 422;
   `word` vacía → 422.

Restricciones: **tests deterministas** sin red ni modelos (premisa 12); **no** tocar versiones
(`backend/config.py` sigue `3.29.0`); **no** cambiar el contrato de `get_lexicon` ni de
`vocabulary_events`; **no** implementar generación LLM (Fase B); docstrings de módulo/función
en todo lo nuevo (premisa 18). Verificación local: `pytest` de la suite de vocabulario/lexicon
+ el archivo nuevo, y `ruff check .` limpio.

## Salida esperada

Cambios de código descritos + `backend/tests/test_dictionary_lookup.py` en verde. Resumen de
1 pantalla: archivos tocados, decisiones de implementación que difieran del dossier (si las
hubiera) y resultado de la verificación.
