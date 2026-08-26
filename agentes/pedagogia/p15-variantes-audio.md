# V1.18 (3/3) — Listening: escalera de variantes de audio (P1.9 de la auditoría V1.14)

## Rol
Subagente **full-stack** que añade una **escalera de dificultad auditiva** sobre el audio de
listening: variantes del **mismo contenido** a distinta velocidad (slow → normal → fast), servidas
desde el endpoint de audio ya existente. Es la pieza P1.9 de la auditoría V1.14 (§27.8 de
`docs/RELEVO.md`).

**Límite honesto (premisa local-first):** Piper es una única voz. La velocidad (`speed`) es la
única dimensión que se puede *realizar* hoy de forma determinista; `accent`, `noise` y
`speaker_count` siguen siendo límite de **contenido** (necesitan biblioteca de audio humano). Por
eso esta escalera cubre **velocidad** (slow/normal/fast); no inventes variantes de acento/ruido
que no se pueden servir.

## Contexto (contratos exactos, NO romper)

### Backend — estado actual
- `backend/services/listening.py`:
  - `DEFAULT_SPEECH_RATE = 140.0`, `LENGTH_SCALE_MIN = 0.6`, `LENGTH_SCALE_MAX = 1.6`.
  - `length_scale_for_rate(speech_rate: float) -> float`: mapea wpm → `length_scale` de Piper
    (`speech_rate <= 0` → `1.0`; clamp `[0.6, 1.6]`).
  - `audio_digest(question: dict) -> str`: hash de `spoken_text(question)` +
    `length_scale_for_rate(speech_rate)` + `repetition_policy`.
  - `audio_text(question)`, `spoken_text(question)`.
- `backend/domain/listening.py`:
  - `_audio_cache_dir()`, `_audio_path(question)` → `{id}-{audio_digest(question)}.wav`.
  - `get_audio(question_id) -> (bytes|None, int|None)`: sintetiza a
    `length_scale_for_rate(speech_rate)`, cachea en `_audio_path` y sirve del cache.
  - `_public(question)`: expone `difficulty`, `realized_difficulty`, `realization`,
    `audio_type`, `audio_ready`.
- `backend/routers/listening.py`: `GET /api/listening/audio/{question_id}` (sin parámetro de
  variante hoy).
- `backend/schemas/listening.py`: `ListeningQuestion` (tiene `speech_rate`, `audio_ready`,
  `audio_type`, `realized_difficulty`, `realization`).

### Frontend — estado actual
- `frontend/src/api/listening.ts`: `getListeningAudioUrl(questionId, userId)` →
  `/api/listening/audio/${questionId}?user_id=...`.
- `frontend/src/types/api.ts`: `ListeningQuestion` (tiene `speech_rate`).
- `frontend/src/components/ListeningPractice.tsx`: `play()` usa
  `getListeningAudioUrl(question.id, userId)` cuando `question.audio_ready` (y respeta
  `replayCount`); ya muestra metadatos de audio (`speech_rate`, `accent`, `duration`).

## Objetivo
Añadir variantes de velocidad (`slow`/`normal`/`fast`) al audio servido, con cache por variante,
metadatos expuestos en `ListeningQuestion` y botones de variante en el frontend. La variante
`normal` debe **preservar el digest/cache actuales** (no invalidar el audio ya pre-renderizado).

## Tarea

### 1. Backend — `services/listening.py`
Añade (puro y determinista):
- `AUDIO_VARIANTS: tuple[str, ...] = ("slow", "normal", "fast")`.
- `VARIANT_SPEED_FACTORS: dict[str, float] = {"slow": 0.75, "normal": 1.0, "fast": 1.25}`.
- `variant_speech_rate(question: dict, variant: str = "normal") -> float`:
  - base = `question.get("speech_rate") or 0.0`.
  - `normal` → devuelve `base` (0.0 si no declarada), preservando el comportamiento actual.
  - `slow`/`fast` → `round((base or DEFAULT_SPEECH_RATE) * VARIANT_SPEED_FACTORS[variant], 1)`.
- `variant_length_scale(question: dict, variant: str = "normal") -> float`:
  `length_scale_for_rate(variant_speech_rate(question, variant))`. Para `normal` debe devolver
  exactamente lo que hoy devuelve `length_scale_for_rate(speech_rate)`.
- `audio_variants(question: dict) -> list[dict]`: lista `{variant, speech_rate, label}` para las
  tres variantes (`label` en inglés legible: "Slow", "Normal", "Fast"). Orden: slow, normal, fast.
- Extiende `audio_digest(question: dict, variant: str = "normal") -> str` para usar
  `variant_length_scale(question, variant)` en lugar de `length_scale_for_rate(speech_rate)`. El
  payload debe quedar **idéntico al actual cuando `variant == "normal"`** (mismo orden de campos)
  para no invalidar el cache existente. Documenta esta invariante en el docstring.

### 2. Backend — `domain/listening.py`
- `_audio_path(question, variant="normal")` → usa `audio_digest(question, variant)`.
- `get_audio(question_id, variant="normal")`:
  - Si `variant` no está en `AUDIO_VARIANTS` → devuelve `(None, 400)` (o trátalo como error en el
    router; elige el patrón que mantenga el router simple).
  - Sintetiza con `variant_length_scale(question, variant)` y cachea en `_audio_path(question,
    variant)`.
- `_public(question)`: añade `variants = audio_variants(question)` y `default_variant = "normal"`
  al dict público.

### 3. Backend — `routers/listening.py`
- `GET /api/listening/audio/{question_id}`: añade query param opcional `variant: str = "normal"`.
  Pásalo a `get_audio`. Si `get_audio` devuelve `(None, 400)`, responde `HTTPException(400,
  "Variante no válida")` (o el detalle que corresponda); mantén 404 (ítem) y 503 (Piper).

### 4. Backend — `schemas/listening.py`
Añade:
- `ListeningAudioVariant { variant: str, speech_rate: float, label: str }`.
- `variants: list[ListeningAudioVariant] = Field(default_factory=list)` y
  `default_variant: str = "normal"` a `ListeningQuestion`.

### 5. Frontend — `types/api.ts`
Añade:
- `ListeningAudioVariant { variant: string; speech_rate: number; label: string }`.
- `variants: ListeningAudioVariant[]` y `default_variant: string` a `ListeningQuestion`.

### 6. Frontend — `api/listening.ts`
- Cambia `getListeningAudioUrl(questionId, userId, variant = "normal")` para incluir
  `&variant=${variant}` en la query (mantén `user_id`). Retrocompatible: sin `variant` sigue
  funcionando como `normal`.

### 7. Frontend — `components/ListeningPractice.tsx`
- Añade estado `variant` (default `"normal"`).
- Cuando `question.audio_ready` y `question.variants.length > 1`, renderiza botones de variante
  (Slow/Normal/Fast) que cambian el `variant`; `play()` usa
  `getListeningAudioUrl(question.id, userId, variant)`.
- Al cargar una nueva pregunta (`load`), resetea `variant` a `"normal"`.
- Muestra la velocidad de la variante seleccionada (p. ej. `Math.round(speech_rate) wpm`).

### 8. Frontend — `index.css`
Clases `.listening-variants*` (botones de variante activo/inactivo) coherentes con tokens y tema
claro/oscuro (premisa 14).

### 9. Tests

#### Backend (pytest)
- Nuevo `backend/tests/test_listening_variants.py` (o amplía `test_listening.py`):
  - `variant_speech_rate` / `variant_length_scale`: `normal` preserva el valor actual;
    `slow` < `normal` < `fast` en wpm; con `speech_rate=0` usa `DEFAULT_SPEECH_RATE` para
    slow/fast.
  - `audio_digest(question, "normal")` == digest previo (regresión de cache); los digests de las
    tres variantes son distintos.
  - `audio_variants(question)` devuelve 3 variantes ordenadas con labels.
  - Endpoint: `GET /api/listening/audio/{id}?variant=fast` responde 200 (con Piper disponible o
    mock de `tts.synthesize`); `variant=bogus` responde 400. Si no hay Piper, al menos verifica
    el 400/404 (mockea `tts.is_ready`/`tts.synthesize` como en `test_listening_audio.py` si lo
    hay).

#### Frontend (vitest)
- Amplía `frontend/src/api/listening.test.ts`: `getListeningAudioUrl` incluye `variant` en la URL
  cuando se pasa, y lo omite (o usa `normal`) cuando no.

## Criterios de aceptación
- Backend: `pytest` en verde + `ruff` limpio. Frontend: `npx tsc --noEmit` + `npx vitest run`
  en verde.
- Tres variantes de velocidad (`slow`/`normal`/`fast`) servidas desde el endpoint de audio, con
  cache independiente por variante.
- `normal` **no invalida** el cache/audio existente (mismo digest que hoy).
- `ListeningQuestion` expone `variants` + `default_variant`; el frontend las renderiza.
- No se toca el scoring, el banco ni los endpoints de respuesta/diagnóstico.
- Todo nuevo con docstrings/JSdoc (premisa 18). Sin dependencias nuevas.

## Restricciones
- La escalera es solo de **velocidad** (límite honesto de Piper). No implementes acento/ruido.
- No rompas `test_listening_audio.py` ni el resto de tests; no cambies la firma pública de
  `getListeningAudioUrl` de forma que rompa llamadas existentes (el `variant` es opcional).
- Crea **un único commit `feat:`** descriptivo (no hagas push). No incluyas el archivo de briefing
  en el commit (déjalo untracked).

## Salida
- Diff backend + frontend, y salida de pytest/ruff, tsc y vitest en verde.
