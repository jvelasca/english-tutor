# Briefing — V3.30 Diccionario de consulta · Fase B (contenido LLM local + caché)

> Rol: subagente implementador · Autocontenido: lee este briefing + `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`
> + el briefing de la Fase A (`agentes/v330-diccionario-fase-a.md`, ya implementada) y las
> anclas de código citadas. Fecha: 2026-09-09 · Release v3.30.0 (todavía **sin** bump).

## Objetivo

Completar el backend del diccionario de consulta con la **generación de contenido por el
modelo local (Ollama)** y su **caché persistente**, respetando la decisión **D1** y la
degradación del diseño. La Fase A ya dejó el endpoint, la marca de uso (solo lectura) y la
lectura de la caché; aquí se añade la **escritura** (`INSERT OR IGNORE`) y el **generador**.

## Alcance de esta fase (backend)

1. **`backend/services/dictionary_content.py`** (nuevo):
   - `ContentUnavailableError(RuntimeError)` para señalar «contenido no disponible» (modelo
     caído o respuesta que no valida).
   - Prompt de sistema fijo (estilo `services/translate.py`) que pide **solo** un objeto JSON
     `{"pos": "<categoría>", "definition": "<EN simple, 1–2 frases>", "translation":
     "<ES neutro>"}`; sin texto fuera del JSON.
   - Llamada LLM con `temperature=0` y elección de modelo reutilizando
     `services.translate.pick_model` (modelo rápido instalado; nunca
     `config.UNUSABLE_MODELS`).
   - `parse_content(raw)`: parseo **tolerante** (regex del primer bloque `{…}` aunque venga
     dentro de cercas ``` ``` ```), validación (objeto, claves, definición no vacía, longitudes
     acotadas: `MAX_DEFINITION_CHARS=600`, `MAX_TRANSLATION_CHARS=200`, `pos` en un set
     canónico; si no valida → `ContentUnavailableError`).
   - `async generate_content(word, *, model=None, fetcher=None)` → `{pos, definition,
     translation}`; `fetcher` inyectable para tests (default: llamada real al LLM).
2. **`backend/repositories/dictionary.py`** (ampliar): `insert_entry(word, *, pos="",
   definition="", translation="") -> bool` con `INSERT OR IGNORE` (True si insertó, False si
   ya existía) usando `_now()` de `repositories.db`. Contenido global (sin user_id).
3. **`backend/domain/vocabulary.py`** (ampliar `lookup_dictionary`): si la caché no tiene
   definición, intentar `dictionary_content.generate_content(normalized, model=model)`;
   si hay contenido → `insert_entry` + releer y exponer `definition_source="llm"`; si el
   generador lanza (`ContentUnavailableError` o cualquier excepción) → registrar aviso con
   `logger` y **degradar** a `definition_source="none"` (respuesta 200 con marca de uso y
   ejemplo; nunca 500). Guardar el `pos`/`definition`/`translation` devueltos por el parseo.

## Criterios de aceptación (tests)

Extender `backend/tests/test_dictionary_lookup.py` (integración vía `TestClient`, usuarios de
`users_repo`) y añadir `backend/tests/test_dictionary_content.py` (puro). Tests:

1. `parse_content`: JSON válido con y sin cercas ``` ``` ```; POS inválido → `pos=""`; JSON
   corrupto/ausente o definición vacía → `ContentUnavailableError`.
2. `generate_content` usa el fetcher inyectado (no toca Ollama) y devuelve el dict parseado.
3. Integración caché: primera consulta con fetcher fake inserta una fila en
   `dictionary_entries` y responde `definition_source="llm"` con `pos`/`definition`/
   `translation`; segunda consulta **no** llama al fetcher (contador) y sirve la misma caché.
4. Caché global: el usuario B consulta la misma palabra ya cacheada por A → sin llamada LLM,
   misma definición, marca de uso propia (aislamiento).
5. Degradación: fetcher que lanza (o contenido que no valida) → 200 con
   `definition_source="none"`, `definition=null`, marca de uso intacta y **cero** filas nuevas
   en `dictionary_entries`.
6. Regresión: la suite de vocabulario/lexicon y `test_dictionary_lookup.py` completa siguen
   en verde.

Restricciones: igual que Fase A (sin bump, sin tocar contrato de lexicon/ledger, tests
deterministas sin red/modelos reales, docstrings en todo lo nuevo). Verificación:
`pytest` de los archivos de vocabulario/lexicon/diccionario + suite backend completa y
`ruff check .` limpio.

## Salida esperada

Cambios descritos + tests en verde + resumen de 1 pantalla (archivos, decisiones de
implementación y resultado de verificación).
