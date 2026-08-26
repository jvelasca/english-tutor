# V1.20 — Pronunciación fonémica (P6 diferido): alineación de fonemas + prosodia

## Rol
Subagente **full-stack** que retoma el **P6 diferido** de la Etapa Pedagógica: sustituir la
similitud textual (`SequenceMatcher` sobre caracteres) como señal principal de pronunciación por
**alineación de fonemas** (grapheme→phoneme local) más una **prosodia proxy** (patrón silábico).
El `score` compuesto se conserva como proxy 0-100 (límite honesto: no hay audio fonético, solo
transcripción ortográfica).

**Límite honesto (premisa local-first + 19):** `faster-whisper` entrega texto ortográfico, no
fonemas ni pitch. Por eso (1) la alineación fonémica es un *proxy* sobre el diccionario G2P local
ya existente, y (2) la **prosodia** solo puede medirse como **patrón silábico/ritmo** a partir del
texto; el acento de palabra (sílaba tónica) y la entonación **requieren audio real** y NO se
inventan. Documentar esto en los docstrings.

## Contexto (contratos exactos, NO romper)

### Backend — estado actual
- `backend/services/phonemes.py`:
  - `G2P` (dict palabra → tupla de fonemas ARPAbet compacto, ~60 palabras) + `to_phonemes(text)`
    (fallback letra-a-letra, nunca falla) + `levenshtein(a, b)` + `phoneme_accuracy(expected, heard)
    -> float (0..1)`. NO hay alineación fonémica por fonema ni prosodia.
- `backend/services/phonetics.py`:
  - `tokenize`, `soundex`, `word_alignment`, `word_accuracy`, `phonetic_similarity`,
    `composite_score(expected, heard) -> dict`.
  - Pesos actuales: `W_WORD = 0.6`, `W_PHONETIC = 0.3`, `W_CHAR = 0.1`; `composite_score` calcula
    `score = round(100 * (W_WORD*wa + W_PHONETIC*ps + W_CHAR*char_ratio))` donde `char_ratio` es
    `SequenceMatcher` sobre la concatenación de tokens. Devuelve además `phoneme_accuracy` (0-100)
    PERO no lo incorpora al `score` ponderado.
- `backend/services/pronunciation.py`:
  - `score_pronunciation(expected, heard)` usa `composite_score` y devuelve
    `{expected, heard, score, level, ok, word_accuracy, phonetic_score, phoneme_accuracy, breakdown}`.
  - `PRONUNCIATION_CRITERIA = ("phoneme_accuracy", "word_accuracy", "phonetic_similarity")` y
    `PRONUNCIATION_WEIGHTS = {"phoneme_accuracy": 0.4, "word_accuracy": 0.4, "phonetic_similarity": 0.2}`.
  - `score_pronunciation_cefr(expected, heard)` normaliza `composite_score` a 0..1 por criterio y
    `overall` ponderado. `evidence_from_pronunciation` emite 1 fila por criterio + `overall`.
- `backend/schemas/pronunciation.py`: `WordSubstitution`, `PronunciationBreakdown`, `FluencyStats`,
  `PronunciationResponse` (tiene `word_accuracy`, `phonetic_score`, `phoneme_accuracy`,
  `breakdown`, `fluency`).
- `backend/routers/pronunciation.py`: `POST /api/pronunciation` → `score_pronunciation` +
  `compute_fluency` → `PronunciationResponse(**result)`.
- `backend/services/listening.py` `production_score` y `backend/domain/listening.py` usan
  `composite_score` (solo leen `score`, `word_accuracy`, `phonetic_score`, `phoneme_accuracy`,
  `breakdown`); `backend/services/speaking.py` (líneas ~527 y ~744) lee `composite_score(...)["score"]`.

### Frontend — estado actual
- `frontend/src/types/api.ts`: `PronunciationResponse` tiene `word_accuracy`, `phonetic_score`,
  `breakdown`, `fluency`; NO `phoneme_accuracy` ni `prosody_score`.
- `frontend/src/components/PronunciationPractice.tsx`: muestra `score`, `expected`, `heard`, nivel,
  `word_accuracy`, `phonetic_score` y `fluency`; NO muestra `phoneme_accuracy` ni prosodia.
- `frontend/src/utils/pronunciationFeedback.ts`: `feedbackHints(breakdown)` y
  `wordsCorrectLabel(breakdown)` sobre el breakdown de **palabras** (no tocar).

## Objetivo
1. Añadir **alineación fonémica** (breakdown por fonema: correctos/sustituidos/faltantes/extra) y
   una **prosodia proxy** (patrón silábico) en `phonemes.py`.
2. Hacer que `composite_score` pondere **fonemas + prosodia** como señal principal, eliminando el
   `char_ratio` a nivel de caracteres, sin romper los casos límite (exacto=100, vacío=0).
3. Exponer `prosody_score` y `phoneme_breakdown` en `PronunciationResponse` y mostrarlos en el
   frontend (junto con `phoneme_accuracy`, hoy omitido en el tipo/UI).
4. Añadir `prosody` como cuarto criterio del rubric de pronunciación (read-aloud), coherente con
   el plan "phoneme accuracy y prosodia".

## Tarea

### 1. Backend — `services/phonemes.py`
Añade (puro y determinista, con docstrings):
- `phoneme_alignment(expected: str, heard: str) -> dict`:
  - Alinea las secuencias `to_phonemes(expected)` y `to_phonemes(heard)` con
    `difflib.SequenceMatcher(None, ep, hp, autojunk=False)` sobre las LISTAS de fonemas (espejo
    exacto del patrón de `word_alignment`).
  - Devuelve `{correct, missing, extra, substituted, total}` con `substituted` como lista de
    `{"expected": fonema, "heard": fonema}` y `total = len(ep)`. En `replace` con longitudes
    distintas, el excedente de `es` va a `missing` y el de `hs` a `extra` (igual que
    `word_alignment`).
- `syllables(word: str) -> int`: cuenta grupos vocálicos (`aeiouy`) de forma determinista y
  devuelve `max(1, grupos)`. Es un proxy; no intenta resolver "e" muda ni diptongos (documentar).
- `prosody_score(expected: str, heard: str) -> float`:
  - Ratio 0..1 de palabras esperadas cuyo **número de sílabas** coincide con el de alguna palabra
    oída no reutilizada (greedy, espejo de `phonetic_similarity` pero con `syllables` en vez de
    `soundex`). `not e` → `1.0 if not h else 0.0`.
  - Docstring: "proxy de prosodia (ritmo silábico) sin audio; acento/entonación no observables".

### 2. Backend — `services/phonetics.py`
- Importa `phoneme_alignment`, `phoneme_accuracy`, `prosody_score` desde `services.phonemes`.
- Sustituye los pesos por (deben sumar 1.0): `W_WORD = 0.35`, `W_PHONEME = 0.35`,
  `W_PHONETIC = 0.15`, `W_PROSODY = 0.15`. Elimina `W_CHAR` y el cálculo de `char_ratio`.
- `composite_score`: calcula `pa = phoneme_accuracy(...)`, `pro = prosody_score(...)` y
  `score = round(100 * (W_WORD*wa + W_PHONEME*pa + W_PHONETIC*ps + W_PROSODY*pro))`. Devuelve, además
  de lo actual, `prosody_score` (0-100) y `phoneme_breakdown` (`phoneme_alignment(...)`). Mantén
  `phoneme_accuracy` (0-100).
- Verifica invariantes: exacto → 100; `heard=""` → 0; "I have twenty years old" vs
  "I am twenty years old" sigue en 50..100.

### 3. Backend — `services/pronunciation.py`
- `score_pronunciation`: añade `prosody_score` y `phoneme_breakdown` al dict devuelto.
- `PRONUNCIATION_CRITERIA` = `("phoneme_accuracy", "word_accuracy", "phonetic_similarity", "prosody")`.
- `PRONUNCIATION_WEIGHTS` = `{"phoneme_accuracy": 0.35, "word_accuracy": 0.35, "phonetic_similarity":
  0.15, "prosody": 0.15}` (suman 1.0).
- `score_pronunciation_cefr`: añade `"prosody": comp["prosody_score"] / 100` a `criteria`.

### 4. Backend — `schemas/pronunciation.py`
- Añade `PhonemeSubstitution { expected: str; heard: str }` y
  `PhonemeBreakdown { correct, missing, extra, substituted, total }` (espejo de
  `PronunciationBreakdown`).
- Añade a `PronunciationResponse`: `prosody_score: int` y `phoneme_breakdown: PhonemeBreakdown`.

### 5. Frontend — `types/api.ts`
- Añade `PhonemeSubstitution`, `PhonemeBreakdown` y a `PronunciationResponse`:
  `phoneme_accuracy: number`, `prosody_score: number`, `phoneme_breakdown: PhonemeBreakdown`.

### 6. Frontend — `components/PronunciationPractice.tsx`
- Muestra dos líneas nuevas en el bloque `.lines`: "Precisión de fonemas" (`phoneme_accuracy`%) y
  "Prosodia (ritmo)" (`prosody_score`%). Colócalas junto a "Similitud fonética".

### 7. Tests

#### Backend (pytest)
- `backend/tests/test_phonemes.py`: añade tests para `phoneme_alignment` (exacto vacía
  missing/extra/substituted; sustitución de un fonema; missing/extra), `syllables` (min 1, conteo
  básico) y `prosody_score` (exacto=1.0, vacío=0.0/1.0, rango 0..1).
- `backend/tests/test_phonetics.py`: añade test de que `composite_score` incluye `prosody_score`
  (100 en exacto, 0 en vacío) y `phoneme_breakdown` con `total` correcto.
- `backend/tests/test_pronunciation.py`: añade test de que `score_pronunciation` incluye
  `prosody_score` y `phoneme_breakdown`.
- `backend/tests/test_pronunciation_academy.py`: actualiza `len(body["criteria"]) == 3` → `4` y
  `len(pronunciation_rows) >= 4` → `>= 5` (4 criterios + overall).

#### Frontend (vitest)
- No requiere util nueva; si se toca lógica de feedback, cubrirla. `npx tsc --noEmit` debe quedar
  limpio con los nuevos campos del tipo.

## Criterios de aceptación
- Backend: `pytest` en verde + `ruff` limpio. Frontend: `npx tsc --noEmit` + `npx vitest run` en
  verde.
- `composite_score` ya no usa `SequenceMatcher` a nivel de caracteres; pondera fonemas (0.35) +
  palabra (0.35) + Soundex (0.15) + prosodia (0.15).
- `PronunciationResponse` expone `prosody_score` y `phoneme_breakdown`; el frontend muestra
  `phoneme_accuracy` y `prosody_score`.
- El rubric de pronunciación read-aloud pasa de 3 a 4 criterios (añade `prosody`), suma de pesos 1.0.
- No se toca `production_score`, el banco, ni endpoints de respuesta/diagnóstico.
- Todo nuevo con docstrings/JSdoc (premisa 18). Sin dependencias nuevas.

## Restricciones
- No inventes acento/entonación: la prosodia es **solo ritmo silábico** (proxy documentado).
- No rompas `test_listening_production.py` ni `test_speaking.py`; `composite_score` mantiene los
  casos límite (exacto=100, vacío=0).
- Crea un **único commit `feat:`** descriptivo (no hagas push). No incluyas el archivo de briefing
  en el commit (déjalo untracked).

## Salida
- Diff backend + frontend, y salida de pytest/ruff, tsc y vitest en verde.
