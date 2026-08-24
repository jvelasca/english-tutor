# Subagente F8.2 — Fluidez oral (speaking) con duración (backend)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Añadir **fluidez oral** (speaking) al feedback de pronunciación: palabras por minuto (WPM) y
nivel de fluidez, calculados de forma **determinista y sin LLM** (premisa 12). Para ello el STT
expone la **duración del audio** (faster-whisper ya la proporciona en `info.duration`) y un
servicio puro `compute_fluency` calcula WPM. La respuesta de `/api/pronunciation` incorpora el
bloque `fluency`.

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/services/stt.py` (LEERLO): `transcribe(audio_bytes, language) -> str` usa
  `model.transcribe(...)` y devuelve SOLO el texto. `is_ready()`. `_get_model()`.
  faster-whisper devuelve `(segments, info)` donde `info.duration` es la duración total del audio
  en segundos.
- `backend/routers/pronunciation.py` (LEERLO): importa `from services.stt import transcribe as
  transcribe_audio`, hace `heard = await run_in_threadpool(transcribe_audio, audio, language)`,
  luego `result = score_pronunciation(expected, heard)`, `record_pronunciation(...)`,
  `record_event(...)` y `PronunciationResponse(**result)`.
- `backend/routers/voz.py` (NO tocar): usa `from services.stt import transcribe as transcribe_audio`
  en `/api/transcribe` (devuelve texto). Debe seguir funcionando igual.
- `backend/schemas/pronunciation.py` (LEERLO): `PronunciationResponse` con `expected, heard,
  score, level, ok, word_accuracy, phonetic_score, breakdown` (F7.1).
- **Dos tests existentes hacen monkeypatch de `routers.pronunciation.transcribe_audio`** y
  devuelven un string `"Hello world"`. Como el router pasará a usar `transcribe_with_timing`
  (que devuelve un dict), **deben actualizarse** para devolver un dict:
  - `backend/tests/test_activity.py` (línea ~103): `test_pronunciation_records_event`.
  - `backend/tests/test_api_security.py` (línea ~101): `test_pronunciation_records_only_for_declared_user`.
  Sustituye el lambda por `lambda audio, language="en": {"text": "Hello world", "duration": 2.0}`.
  Cambia la cadena del `setattr` a `"routers.pronunciation.transcribe_with_timing"`.
- `backend/tests/test_robustness.py` usa `/api/transcribe` (voz), NO `/api/pronunciation`: no se
  toca. `voz.py` usa `transcribe` (string): no se toca.
- Estilo: `from __future__ import annotations`, docstrings en español, imports ordenados (ruff/isort).
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/fluency.py` (nuevo, puro)

```python
"""Métricas de fluidez oral (puro, determinista).

Calcula palabras por minuto (WPM) a partir del texto oído y la duración del audio.
"""
from __future__ import annotations


def compute_fluency(heard: str, duration_seconds: float | None) -> dict:
    """Devuelve word_count, duration_seconds, wpm (float|None) y level.

    level: "fluent" (wpm ≥ 120), "good" (60–119), "slow" (< 60), o "—" cuando no
    se puede calcular (sin audio válido o sin palabras).
    """
    words = [w for w in heard.split() if w.strip()]
    word_count = len(words)

    duration = (
        round(duration_seconds, 2) if duration_seconds is not None else None
    )
    wpm: float | None = None
    level = "—"
    if duration and duration > 0 and word_count > 0:
        wpm = round(word_count / (duration / 60), 1)
        if wpm >= 120:
            level = "fluent"
        elif wpm >= 60:
            level = "good"
        else:
            level = "slow"

    return {
        "word_count": word_count,
        "duration_seconds": duration,
        "wpm": wpm,
        "level": level,
    }
```

### 2. `backend/services/stt.py` — exponer duración
Añade `transcribe_with_timing` y haz que `transcribe` delegue (manteniendo su contrato de string
para `voz.py`):

```python
def transcribe_with_timing(audio_bytes: bytes, language: str = "en") -> dict:
    """Convierte audio a texto y devuelve también la duración en segundos.
    Bloqueante: ejecutar en un threadpool."""
    model = _get_model()
    segments, info = model.transcribe(
        io.BytesIO(audio_bytes), language=language, beam_size=5
    )
    text = "".join(segment.text for segment in segments).strip()
    duration = round(info.duration, 2) if info.duration else 0.0
    return {"text": text, "duration": duration}
```

Y sustituye el cuerpo de `transcribe` por:

```python
def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """Convierte audio (WAV/WebM) a texto. Bloqueante: ejecutar en un threadpool."""
    return transcribe_with_timing(audio_bytes, language)["text"]
```

### 3. `backend/schemas/pronunciation.py` — añadir fluidez
Añade:

```python
class FluencyStats(BaseModel):
    word_count: int
    duration_seconds: float | None = None
    wpm: float | None = None
    level: str
```

Y en `PronunciationResponse` añade al final el campo `fluency: FluencyStats`.

### 4. `backend/routers/pronunciation.py` — cablear fluidez
- Sustituye el import `from services.stt import transcribe as transcribe_audio` por
  `from services.stt import transcribe_with_timing`.
- Añade `from services.fluency import compute_fluency`.
- Sustituye:
  ```python
      heard = await run_in_threadpool(transcribe_audio, audio, language)
  ```
  por:
  ```python
      timed = await run_in_threadpool(transcribe_with_timing, audio, language)
      heard = timed["text"]
  ```
- Justo después de `result = score_pronunciation(expected, heard)`, añade:
  ```python
      result["fluency"] = compute_fluency(heard, timed.get("duration"))
  ```
- Mantén el resto (`record_pronunciation`, `record_event`, `return`) igual.

### 5. Actualizar los 2 monkeypatch existentes
En `backend/tests/test_activity.py` y `backend/tests/test_api_security.py`, cambia:
```python
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_audio",
        lambda audio, language="en": "Hello world",
    )
```
por:
```python
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_with_timing",
        lambda audio, language="en": {"text": "Hello world", "duration": 2.0},
    )
```
(No cambies nada más de esos tests: su lógica sigue siendo válida.)

### 6. Test nuevo `backend/tests/test_fluency.py` (6 tests)

```python
"""Tests de fluidez oral: compute_fluency (puro) y endpoint."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.fluency import compute_fluency


def test_compute_fluency_empty():
    r = compute_fluency("", 5.0)
    assert r["word_count"] == 0
    assert r["wpm"] is None
    assert r["level"] == "—"


def test_compute_fluency_good():
    r = compute_fluency("Hello world how are you", 5.0)  # 5 palabras / 5s = 60 wpm
    assert r["word_count"] == 5
    assert r["wpm"] == 60.0
    assert r["level"] == "good"


def test_compute_fluency_fluent():
    r = compute_fluency("one two three four five six seven eight nine ten", 3.0)
    assert r["wpm"] == 200.0
    assert r["level"] == "fluent"


def test_compute_fluency_slow():
    r = compute_fluency("hello world", 10.0)  # 2 palabras / 10s = 12 wpm
    assert r["wpm"] == 12.0
    assert r["level"] == "slow"


def test_compute_fluency_no_duration():
    r = compute_fluency("hello world", None)
    assert r["wpm"] is None
    assert r["duration_seconds"] is None
    assert r["level"] == "—"


def test_pronunciation_endpoint_returns_fluency(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_with_timing",
        lambda audio, language="en": {"text": "Hello world", "duration": 2.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation",
            data={"expected": "Hello world", "user_id": uid},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
    assert r.status_code == 200
    fluency = r.json()["fluency"]
    assert fluency["word_count"] == 2
    assert fluency["wpm"] == 60.0
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 178 tests** (172 previos + 6 nuevos).
- `python -m ruff check .` **sin errores**.
- Los tests actualizados (`test_activity.py`, `test_api_security.py`) siguen verdes; el resto de
  tests existentes también. No se toca `voz.py`, `/api/transcribe` ni `test_robustness.py`.

## Restricciones
- NO tocar el frontend.
- NO tocar `voz.py`, `main.py`, `domain/`, `repositories/`, `dependencies.py`, ni `services/*`
  salvo `stt.py` y el nuevo `fluency.py`.
- NO cambiar el contrato de `transcribe` (sigue devolviendo string; solo delega).
- NO cambiar `score_pronunciation` ni los umbrales de nivel existentes.
- Mantener el estilo: docstrings en español, `from __future__ import annotations`,
  imports ordenados (ruff/isort).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.
