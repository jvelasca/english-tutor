# V1.19 (1/2) — Listening: infraestructura de biblioteca de audio humano (P1.5–P1.8 de la auditoría V1.14)

## Rol
Subagente **backend** que añade la **infraestructura de biblioteca de audio humano** que faltaba
para servir grabaciones reales (varios hablantes, connected speech real, acentos reales, ruido
real). Son los P1.5–P1.8 pendientes de la auditoría V1.14 (§27.8 de `docs/RELEVO.md`).

**Límite honesto (premisa local-first y límite de contenido):** este incremento NO graba audio. Es
la **infraestructura de código** (manifest + resolución + servido) que permite que, cuando existan
grabaciones reales, el sistema las sirva sin tocar lógica. Hoy el banco sigue siendo `tts` (una voz
Piper). No inventes metadatos de acento/ruido/hablantes que no estén respaldados por un WAV real.

## Contexto (contratos exactos, NO romper)

### Backend — estado actual
- `backend/services/listening.py`:
  - `AUDIO_TYPES = ("tts", "recorded", "mixed", "synthetic_multispeaker", "real_world")`. Los tipos
    no-`tts` ya están **reservados** para audio humano (V1.15+).
  - `ListeningAsset` ya declara `audio_id`, `duration`, `speaker_id`, `accent`, `speech_rate`,
    `transcript`, `clean_transcript`, `noise_level`, `repetition_policy`, `audio_type`.
  - `realized_vector(question)`: para `audio_type != "tts"` ya confía en la realización declarada
    (la audita el proceso de grabación). NO hace falta tocarlo.
- `backend/domain/listening.py`:
  - `audio_ready(question)`: hoy `bool(audio_text(question)) and tts.is_ready()` (solo Piper).
  - `get_audio(question_id, variant="normal") -> (bytes|None, int|None)`: hoy valida `variant`
    (400), busca el ítem (404), exige Piper (503), sintetiza y cachea en
    `DATA_DIR/listening/{bank}/{voice}/{id}-{digest}.wav`.
- `backend/routers/listening.py`: `GET /api/listening/audio/{question_id}?variant=...` mapea
  `(None, status)` a `HTTPException` con detalle (400 variante / 404 ítem / 503 Piper).
- `backend/schemas/listening.py`: `ListeningQuestion` expone `audio_type`, `audio_ready`, etc.

### Convención de contenido versionado (espejo de `services/curriculum.py`)
- `services/curriculum.py` usa `CURRICULUM_DIR = backend/curriculum` y constantes de versión
  (`LISTENING_BANK_VERSION = "3.0.0"`). El contenido vive como JSON fuera del código.

## Objetivo
Añadir un **manifest versionado** de la biblioteca de audio humano y la **resolución + servido** de
grabaciones reales a partir de un ítem que declare `audio_type="recorded"` y un `audio_id` presente
en el manifest. No cambia el scoring, el banco ni los endpoints de respuesta/diagnóstico.

## Tarea

### 1. Backend — `services/audio_library.py` (nuevo, puro + IO fino)
Crea el módulo con:
- `AUDIO_LIBRARY_VERSION = "1.0.0"`.
- `AUDIO_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "audio_library"`.
- `AudioLibraryEntry(BaseModel)`: `audio_id: str`, `file: str`, `speaker_id: str = ""`,
  `accent: str = "neutral"`, `speaker_count: int = Field(default=1, ge=1)`,
  `noise_level: int = Field(default=0, ge=0, le=5)`, `duration: float = Field(default=0.0, ge=0)`,
  `transcript: str = ""`.
- `AudioLibraryManifest(BaseModel)`: `version: str`, `entries: list[AudioLibraryEntry] = []`.
- `manifest_path() -> Path` → `AUDIO_LIBRARY_DIR / "manifest.json"`.
- `library_dir() -> Path` → `AUDIO_LIBRARY_DIR` (los WAV viven aquí).
- `load_manifest(path: Path | None = None) -> AudioLibraryManifest` (lee y valida; lanza
  `FileNotFoundError` si no existe).
- `entry_for(manifest, audio_id) -> AudioLibraryEntry | None`.
- `resolve_file(entry, base: Path | None = None) -> Path | None`: resuelve `base / entry.file`
  y devuelve None si la ruta escapa de `base` (seguridad, `Path.is_relative_to`).
- `is_recorded(question) -> bool`: `(question.get("audio_type") or "tts") == "recorded"`.
- `recorded_audio_path(question) -> Path | None`: para `recorded`, resuelve el WAV del manifest
  (None si no hay `audio_id`, no está en el manifest, o escapa del directorio). None también para
  no-`recorded`.
- `library_summary(manifest=None) -> list[dict]`: metadatos sin audio (`audio_id`, `file`,
  `speaker_id`, `accent`, `speaker_count`, `noise_level`, `duration`, `transcript`).
- `validate_manifest(manifest=None) -> list[str]`: invariantes (versión coincide, `audio_id` y
  `file` únicos y no vacíos, `file` dentro del directorio). Vacía = ok.

Docstrings completos (premisa 18). Imports ordenados para `ruff` (select I).

### 2. Backend — `backend/audio_library/manifest.json` (nuevo, contenido)
```json
{
  "version": "1.0.0",
  "entries": []
}
```
Vacío: aún no hay grabaciones reales. El esquema queda documentado en el docstring del módulo y en
`validate_manifest`. Cuando el equipo aporte una grabación, añade una entrada
`{audio_id, file, speaker_id, accent, speaker_count, noise_level, duration, transcript}` y coloca el
WAV en `backend/audio_library/`.

### 3. Backend — `domain/listening.py`
- Importa `is_recorded`, `recorded_audio_path` desde `services.audio_library` (orden isort: entre
  `from services import tts` y `from services.curriculum import ...`).
- `audio_ready(question)`: si `is_recorded(question)`, devuelve `path is not None and
  path.exists()` (no depende de Piper); si no, mantén el comportamiento actual.
- `get_audio(question_id, variant="normal")`:
  - Busca el ítem primero (404 si no existe) — mantén el 404 de `test_listening_audio.py`.
  - Si `is_recorded(question)`: sirve el WAV grabado si existe; si no, devuelve `(None, 404)` (audio
    grabado referenciado pero ausente). NO caigas a TTS para ítems `recorded`.
  - Si no es `recorded`: conserva el flujo actual (variant 400 → Piper 503 → síntesis/cache).
  - Actualiza el docstring para documentar la rama de audio grabado.

### 4. Tests — `backend/tests/test_audio_library.py` (nuevo)
- Puras: `load_manifest`/`entry_for`/`resolve_file` (incl. escape `../`), `is_recorded`,
  `recorded_audio_path` (tts → None; recorded con entrada → ruta; sin `audio_id` → None; sin entrada
  → None; escape → None), `validate_manifest` (válido → []; versión/duplicados/escape detectados),
  `library_summary`.
- Integración (`TestClient` + monkeypatch, como `test_listening_audio.py`): monkeypatch
  `services.audio_library.load_manifest` y `services.audio_library.library_dir` a `tmp_path`, y
  `domain.listening.get_question` a un dict `{"id": "rec-1", "audio_type": "recorded",
  "audio_id": "a1", ...}`. Escribe un WAV de prueba en `tmp_path`. Verifica:
  - `GET /api/listening/audio/rec-1` → 200, `audio/wav`, contenido == bytes del WAV.
  - Con el WAV ausente → 404 (no cae a TTS ni a 503).
  - `domain.listening.audio_ready(recorded_item)` True/False según exista el WAV.
- Verifica que los tests existentes (`test_listening_audio.py`, `test_listening_variants.py`,
  `test_listening_realization.py`) sigan en verde.

## Criterios de aceptación
- `pytest` en verde + `ruff` limpio (select E/F/W/I/B, line-length 88).
- `recorded_audio_path`/`resolve_file` no permiten rutas fuera de la biblioteca.
- `get_audio` sirve audio grabado del manifest sin depender de Piper, y devuelve 404 (no TTS) si el
  grabado falta.
- El banco de listening, el scoring y los endpoints de respuesta/diagnóstico no cambian.
- Manifest vacío versionado en `backend/audio_library/manifest.json`.

## Restricciones
- NO grabes audio ni añadas entradas falsas al manifest (límite de contenido).
- No rompas los tests existentes de listening/audio/variantes.
- Sin dependencias nuevas.
- Crea un único commit `feat:` descriptivo (no hagas push). No incluyas el briefing en el commit
  (déjalo untracked).

## Salida
- Diff backend + salida de `pytest` y `ruff` en verde.
