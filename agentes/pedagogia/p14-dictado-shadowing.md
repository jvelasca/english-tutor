# V1.18 (2/3) — Listening: tareas reales de dictado y shadowing (P1.3/P1.4)

## Rol
Subagente **full-stack** que convierte las sub-destrezas `dictation` y `shadowing` en **tareas de
producción reales** (no MCQ), cerrando los puntos P1.3 (shadowing con alineamiento) y P1.4
(dictado real) de la auditoría V1.14 (§27.8 de `docs/RELEVO.md`). Hoy `l18` (dictation) y `l19`
(shadowing) se sirven como opción múltiple; este incremento los convierte en: **dictado** (el
alumno escribe lo que oye) y **shadowing** (el alumno graba su repetición, se transcribe con
Whisper y se alinea contra la referencia). El scoring es **determinista** (sin LLM) reutilizando
`services/phonetics.py`.

## Contexto (contratos exactos, NO romper)

### Backend — estado actual
- `backend/services/phonetics.py` (ya existe, NO tocar):
  - `composite_score(expected: str, heard: str) -> dict` → `{score (0..100),
    word_accuracy (0..100), phonetic_score (0..100), phoneme_accuracy (0..100),
    breakdown (word_alignment → {correct, missing, extra, substituted, total})}`.
  - `word_accuracy(expected, heard)`, `word_alignment(expected, heard)`, `tokenize(text)`.
- `backend/services/listening.py`:
  - `LISTENING_SUBSKILLS` ya incluye `"dictation"` y `"shadowing"`.
  - `get_question(question_id)`, `audio_text(question)`, `listening_diagnostic(attempt_rows,
    now="")` (este último recién modificado en P13 con la clave `retention`).
  - `QUESTION_BANK`: `l18` (`skill="dictation"`, B1) y `l19` (`skill="shadowing"`, B1). Ambos
    declaran `transcript`, `clean_transcript` y `script`.
- `backend/repositories/listening.py`:
  - `record_attempt(user_id, question_id, answer_index, correct, skill="", difficulty=1,
    response_time_ms=None, replay_count=0, topic="", realized_difficulty=0)`.
  - `list_attempts(user_id)` devuelve filas con `question_id`, `answer_index`, `correct`,
    `skill`, `difficulty`, `response_time_ms`, `replay_count`, `topic`, `realized_difficulty`,
    `created_at`.
- `backend/repositories/db.py`: migraciones idempotentes con `PRAGMA table_info(...)` +
  `ALTER TABLE ... ADD COLUMN`. La tabla `listening_attempts` ya tiene `skill`, `difficulty`,
  `response_time_ms`, `replay_count`, `topic`, `realized_difficulty`.
- `backend/domain/listening.py`: `submit_answer(...)` (MCQ), `next_question(...)`, `get_audio(...)`,
  `get_diagnostic(...)`. `_public(question)` quita `answer_index` y añade `difficulty`,
  `realized_difficulty`, `realization`, `audio_type`, `audio_ready`.
- `backend/routers/listening.py`: endpoints `question`, `audio`, `answer`, `stats`, `diagnostic`.
- `backend/services/stt.py`: `transcribe(audio_bytes, language)` → str (Whisper). No tocar.
- `backend/routers/voz.py`: `POST /api/transcribe` ya existe (el frontend lo usa para pasar audio
  → texto).

### Frontend — estado actual
- `frontend/src/api/voz.ts`: `transcribe(blob): Promise<string>` (sube audio a `/api/transcribe`
  y devuelve el texto). Reutilízalo para el shadowing.
- `frontend/src/components/PronunciationPractice.tsx`: patrón de grabación con `MediaRecorder`
  (`navigator.mediaDevices.getUserMedia({audio:true})`, `chunksRef`, `recorder.onstop` →
  `Blob`). **Míralo y reutiliza el mismo patrón** para el botón de grabación del shadowing.
- `frontend/src/components/ListeningPractice.tsx`: hoy siempre renderiza `question.options` como
  botones MCQ (líneas ~191-209) y llama `choose(index)` → `submitListeningAnswer`.
- `frontend/src/types/api.ts`: `ListeningQuestion` (tiene `skill`, `transcript`,
  `clean_transcript`), `ListeningDiagnostic`, `ListeningSubskillProgress`.
- `frontend/src/api/listening.ts`: `submitListeningAnswer`, `getListeningQuestion`, etc.

## Objetivo
Añadir el modo de producción (dictado/shadowing) al flujo de listening, con scoring determinista,
persistencia en `listening_attempts` y feedback en el frontend. La evidencia fluye al diagnóstico
`dictation`/`shadowing` con una métrica continua `mean_score` además del `correct` binario.

## Tarea

### 1. Backend — migración (`repositories/db.py`)
Añade dos columnas idempotentes a `listening_attempts` (patrón existente con `PRAGMA
table_info`):
- `task_type TEXT NOT NULL DEFAULT 'mcq'`
- `score REAL` (nullable; solo para tareas de producción)

### 2. Backend — `repositories/listening.py`
- Amplía `record_attempt(...)` con kwargs opcionales **compatibles hacia atrás**:
  `task_type: str = "mcq"`, `score: float | None = None`. Inserta ambas columnas.
- Amplía `list_attempts(...)` para devolver `task_type` y `score` en cada fila.

### 3. Backend — `services/listening.py`
Añade (puro y determinista):
- Constante `PRODUCTION_PASS_SCORE = 80` (0..100; umbral para `correct`).
- `production_score(reference: str, heard: str) -> dict`: delega en
  `from services.phonetics import composite_score` y devuelve `{score, word_accuracy,
  phonetic_score, phoneme_accuracy, breakdown}` (enteros 0..100, salvo `breakdown` que es el dict
  de `word_alignment`).
- `production_reference(question: dict) -> str`: `transcript` si no vacío; si no,
  `clean_transcript`; si no, `script`. Es la referencia contra la que se puntúa.
- En `listening_diagnostic`: por sub-destreza, añade `mean_score` = media de `score*100` sobre las
  filas con `score` no nulo (redondeada a 1 decimal), o `None` si no hay filas de producción.
  (Las filas de producción también cuentan en `attempts`/`correct`/`accuracy` como hasta ahora.)

### 4. Backend — `domain/listening.py`
Añade:
- `submit_production(user_id, question_id, transcript, task_type) -> dict | None`, con
  `task_type ∈ {"dictation", "shadowing"}`:
  - `question = get_question(question_id)`; si no existe → `None`.
  - Valida `question.get("skill") == task_type`; si no coincide → `None` (o lanza/None según el
    patrón del router; usa `None` y 404 en el router).
  - `reference = production_reference(question)`. `heard = (transcript or "").strip()`.
  - `result = production_score(reference, heard)`. `correct = result["score"] >=
    PRODUCTION_PASS_SCORE`.
  - Persiste con `record_attempt(..., answer_index=-1, correct=correct, skill=task_type,
    difficulty=difficulty_from_vector(...), topic=question.get("topic",""),
    realized_difficulty=realized_difficulty(question), task_type=task_type,
    score=result["score"]/100.0)` (score continuo 0..1).
  - Devuelve `{question_id, task_type, correct, score, word_accuracy, phonetic_score,
    phoneme_accuracy, breakdown, reference, level, skill}` (score/word_accuracy/etc. enteros
    0..100).
- No cambies `submit_answer` (MCQ) ni `next_question`.

### 5. Backend — `schemas/listening.py`
Añade:
- `ListeningProductionRequest { question_id: str, transcript: str }`.
- `ListeningProductionResult { question_id, task_type, correct: bool, score: int, word_accuracy:
  int, phonetic_score: int, phoneme_accuracy: int, breakdown: dict, reference: str, level: str,
  skill: str }`.
- Añade `mean_score: float | None = None` a `ListeningSubskillOut`.

### 6. Backend — `routers/listening.py`
Añade dos POST (autenticados con `current_user`):
- `POST /api/listening/dictation` (body `ListeningProductionRequest`) → `submit_production(...,
  task_type="dictation")` → `ListeningProductionResult`; 404 si `None`.
- `POST /api/listening/shadowing` (body `ListeningProductionRequest`) → `submit_production(...,
  task_type="shadowing")` → `ListeningProductionResult`; 404 si `None`.
- Tras persistir, registra `learning_service.record_event(user["id"], "exercise",
  f"listening:{task_type}:{question_id}:{'ok' if correct else 'ko'}")` (mismo patrón que
  `/answer`).

### 7. Frontend — `types/api.ts`
Añade:
- `ListeningProductionRequest { question_id: string; transcript: string }`.
- `ListeningProductionResult { question_id: string; task_type: string; correct: boolean; score:
  number; word_accuracy: number; phonetic_score: number; phoneme_accuracy: number; breakdown:
  Record<string, unknown>; reference: string; level: string; skill: string }`.
- Añade `mean_score: number | null` a `ListeningSubskillProgress`.

### 8. Frontend — `api/listening.ts`
Añade:
- `submitListeningDictation(userId, questionId, transcript): Promise<ListeningProductionResult>`
  → `POST /api/listening/dictation`.
- `submitListeningShadowing(userId, questionId, transcript): Promise<ListeningProductionResult>`
  → `POST /api/listening/shadowing`.

### 9. Frontend — `components/ListeningPractice.tsx`
Bifurca según `question.skill`:
- Si `question.skill === "dictation"`: en lugar de las opciones MCQ, renderiza un `<textarea>` y
  un botón "Enviar dictado" que llama `submitListeningDictation(userId, question.id, text)`.
  Muestra el feedback (`score`, `word_accuracy`, palabras correctas/faltantes/extra de
  `breakdown`, y `reference`).
- Si `question.skill === "shadowing"`: en lugar de las opciones MCQ, renderiza un botón de
  grabación (patrón `MediaRecorder` de `PronunciationPractice.tsx`) que al parar transcribe con
  `transcribe(blob)` de `../api/voz` y llama `submitListeningShadowing(userId, question.id,
  textoTranscrito)`. Muestra el feedback (mismo bloque que dictado + el texto transcrito).
- Para el resto de skills mantiene el flujo MCQ intacto.
- Actualiza `onAttempt()` y `refreshStats()` tras cada envío de producción, igual que `choose`.
- Respeta estados de carga/error y el aviso honesto de audio (el ítem debe poder escucharse antes
  de escribir/grablar: usa `question.audio_ready`/botón "Escuchar audio" ya existente).

### 10. Frontend — `index.css`
Añade clases `.listening-production*` (textarea, botón de grabación, feedback) coherentes con
tokens y tema claro/oscuro (premisa 14). Reutiliza estilos de `.pronunciation-*` si es útil.

### 11. Tests

#### Backend (pytest)
- Nuevo `backend/tests/test_listening_production.py` (o amplía `test_listening.py`):
  - `production_score` y `production_reference` (unidades puras).
  - `submit_production` (vía API o domain) para dictation y shadowing: acierto (score alto) →
    `correct=True` y fila con `task_type`/`score` persistida; error → `correct=False`.
  - `question_id` inexistente → 404; `skill` que no coincide con `task_type` → 404.
  - `listening_diagnostic` expone `mean_score` en la sub-destreza cuando hay filas con `score`.
  - Verifica que el MCQ existente sigue pasando (no romper `test_listening.py`).

#### Frontend (vitest)
- Si existe `api/listening.test.ts`, añade tests de `submitListeningDictation`/
  `submitListeningShadowing` (URL y método con mock de fetch). Si no existe, crea uno mínimo.

## Criterios de aceptación
- Backend: `pytest` en verde + `ruff` limpio. Frontend: `npx tsc --noEmit` + `npx vitest run`
  en verde.
- Dictado y shadowing son tareas reales (escribir/grablar), no MCQ, con scoring **determinista**
  reutilizando `services/phonetics.composite_score` (el LLM no puntúa).
- La evidencia de producción se persiste en `listening_attempts` con `task_type` y `score`
  continuo, y aparece en el diagnóstico como `mean_score` (además de `correct`/`accuracy`).
- No se rompe el flujo MCQ ni los endpoints existentes.
- Frontend bifurca por `skill` y muestra feedback de producción; responsive y con estados
  vacío/carga/error.
- Todo nuevo con docstrings/JSdoc (premisa 18).

## Restricciones
- NO cambies `services/phonetics.py` ni `services/stt.py` ni `routers/voz.py`: solo reutilízalos.
- No introduzcas dependencias nuevas; no uses LLM para puntuar.
- Crea **un único commit `feat:`** descriptivo (no hagas push). No incluyas el archivo de briefing
  `agentes/pedagogia/p14-*.md` en el commit (déjalo untracked).

## Salida
- Diff backend + frontend, y salida de pytest/ruff, tsc y vitest en verde.
