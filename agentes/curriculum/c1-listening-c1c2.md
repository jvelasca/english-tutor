# V2.5 (1/4) — C1: Ampliar el corpus de listening a C1/C2

## Rol
Backend (contenido curricular + validador de contenido). Autor del **contenido de listening C1/C2**
y ajuste del motor para que lo reconozca. No tocas frontend ni el Course Engine.

## Objetivo
Cerrar el hueco detectado por la auditoría V2.4 (`docs/CURRICULUM_COVERAGE.md`): el banco de
listening solo cubre **A1–B2** (100 ítems de corpus + 23 legacy TTS). Debes añadir ítems de
listening **C1 y C2** y hacer que el validador, el quality gate y la métrica los cuenten.

## Contexto

### Dónde vive el contenido
- Corpus: `backend/curriculum/listening_corpus.json` — objeto `{ "version": "1.0.0", "items": [...] }`.
  Hoy 100 ítems (`c001`–`c100`) con `level` ∈ {A1, A2, B1, B2} (25 por nivel).
- Banco heredado TTS: `services/listening.py` → `_LEGACY_BANK` (l1–l23, en el código).
- `QUESTION_BANK = _LEGACY_BANK + _load_corpus_items()` (línea ~919). `_load_corpus_items()` lee
  `listening_corpus.json` y devuelve `data["items"]` tal cual (los ítems del corpus declaran `audio_id`
  y son `tts` hasta que el manifest de la biblioteca de audio respalda su `audio_id`).
- `LEVEL_ORDER: list[str] = ["A1", "A2", "B1", "B2"]` (línea ~922) — **no incluye C1/C2**.
- `LISTENING_BANK_VERSION = "5.0.0"` en `services/curriculum.py`.

### Forma de un ítem de corpus (obligatoria)
Cada ítem tiene exactamente estas claves (mira un ítem existente en `listening_corpus.json`):
`id`, `level`, `skill`, `topic`, `context`, `task_type`, `difficulty_vector`, `script`, `question`,
`options` (lista de 4), `answer_index`, `audio_id`, `duration`, `speaker_id`, `accent`, `speech_rate`,
`transcript`, `clean_transcript`, `noise_level`, `repetition_policy`, `gender`, `age_band`, `region`,
`speaker_count`, `spontaneity`, `recording_environment`, `overlap`, `connected_speech`, `prosody`.

- `difficulty_vector` debe contener exactamente los 8 factores de `DIFFICULTY_FACTORS`:
  `speed`, `vocabulary`, `accent`, `syntactic`, `length`, `speaker_count`, `noise`, `connected_speech`
  (valores int 1..6). El escalar `difficulty` se deriva por construcción; no lo pongas a mano.
- `skill` debe ser una sub-destreza canónica de listening (ver `SUBSKILLS["listening"]` en
  `services/curriculum.py`: gist/detail/inference/speaker_intention/attitude/multiple_speakers/
  fast_speech/accents/dictation/shadowing/connected_speech/…).
- `context` ∈ `LISTENING_CONTEXTS` (conversation/announcement/message/instructions/news/interview/
  narrative/presentation).
- Para C1/C2 sube la dificultad real del `difficulty_vector` (p. ej. speed 5–6, connected_speech 5–6,
  vocabulary 5–6, syntactic 5–6, speaker_count ≥1, noise 2–4) y usa temas/registros avanzados
  (idioms, discurso académico, matiz, ironía, inferencia alta, hablantes múltiples).

### Umbrales de calidad (a actualizar)
`services/content_validation.py` → `QUALITY_THRESHOLDS`:
- `min_items_per_level` es hoy `{"A1": 20, "A2": 20, "B1": 20, "B2": 20}`.
- El test `backend/tests/test_content_quality.py::test_quality_thresholds_are_defined` afirma
  `set(QUALITY_THRESHOLDS["min_items_per_level"]) == {"A1", "A2", "B1", "B2"}` — **hay que actualizarlo**.

### Tests que hoy afirman el hueco (a invertir)
`backend/tests/test_curriculum_coverage.py`:
- `test_bank_intersection_exposes_listening_gap_c1_c2` afirma `banks["C1"]["listening"] == 0` y
  `banks["C2"]["listening"] == 0`. Al añadir C1/C2, cambia el test para afirmar `> 0` (y mantenlo
  como invariante de que ya NO hay hueco).

### Métrica única (anti-drift)
`content_stats()` deriva `total_validated_learning_items = len(QUESTION_BANK) + len(scenarios)`
dinámicamente, pero `README.md`/`CHANGELOG.md`/`PLAN.md` citan la cifra **143** y **"100 corpus +
23 legacy"**. Al añadir ítems, actualiza esas cifras en los tres documentos (o el anti-drift queda
roto para el siguiente lector, aunque `check_release_consistency` solo valida la versión).

## Tarea detallada

1. **Contenido** — añade al array `items` de `listening_corpus.json`:
   - **C1**: 20 ítems nuevos (`c101`–`c120`, `level: "C1"`).
   - **C2**: 20 ítems nuevos (`c121`–`c140`, `level: "C2"`).
   - Diversifica `speaker_id`/`accent`/`region`/`context`/`task_type`/`skill` como el corpus actual.
   - Bump de `version` del corpus (p. ej. `1.0.0` → `1.1.0`).
2. **`services/listening.py`**: `LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]`.
3. **`services/curriculum.py`**: `LISTENING_BANK_VERSION = "6.0.0"`.
4. **`services/content_validation.py`**: `QUALITY_THRESHOLDS["min_items_per_level"]` añade
   `"C1": 20, "C2": 20`.
5. **Tests**: actualiza `test_content_quality.py` (umbrales) y `test_curriculum_coverage.py`
   (invierte el test del hueco C1/C2). Añade un test de invariante: el banco tiene ≥20 ítems por
   nivel para los 6 niveles A1..C2.
6. **Docs**: actualiza la cifra `143` y `"100 corpus + 23 legacy"` en `README.md`, `CHANGELOG.md`
   y `PLAN.md` con la nueva cifra derivada de `content_stats()`. Actualiza la tabla de
   `docs/CURRICULUM_COVERAGE.md` (listening deja de ser hueco en C1/C2).

## Criterios de aceptación
- `python -m scripts.content_validation` sale 0 y reporta el nuevo total.
- `python -m scripts.curriculum_coverage` sale 0 y `bank_count` de listening C1/C2 > 0.
- `pytest tests/ -q` en verde (incluye los tests actualizados) + `ruff check .` limpio.
- `check_release_consistency` OK (no cambias versión, sigue `2.4.0`).

## Restricciones
- No toques frontend, ni `services/course.py`, ni el Course Engine.
- No fabriques audio real (premisa 2): los ítems C1/C2 son contenido + metadata (serán TTS hasta que
  exista WAV real). El `audio_id` sigue el patrón `audio-cNNN`.
- El contenido es **contenido** (JSON), no lógica; no cifres umbrales ni ítems en Python.
- Mantén tipado fuerte y docstrings en los cambios de Python.
- Un único commit `feat: listening C1/C2 (corpus 100→140, LEVEL_ORDER ampliado)`. No hagas push.

## Salida esperada
Resumen de: nº de ítems C1/C2 añadidos, diff de `LEVEL_ORDER`/`LISTENING_BANK_VERSION`/umbrales,
tests actualizados y nueva cifra de `total_validated_learning_items` que debe reflejarse en docs.
