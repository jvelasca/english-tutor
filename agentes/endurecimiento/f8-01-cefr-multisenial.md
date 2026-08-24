# Subagente F8.1 — CEFR real: evaluador multi-señal (backend)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Convertir la estimación CEFR **heurística v1** en una **evaluación multi-señal rica**, determinista
y sin LLM (premisa 12). Se añade un `evaluate_cefr` que devuelve nivel global + **bandas por
destreza** (vocabulario, gramática, fluidez, pronunciación) + **descriptor**, y el perfil
(`/api/profile`) empieza a exponer esa riqueza. Se mantiene `estimate_cefr` como API compatible
(delegando en `evaluate_cefr`) para no romper los tests existentes.

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/services/cefr.py` (LEERLO): hoy define `CEFR_LEVELS`, `estimate_cefr(signals) -> str`
  (heurística por puntos: vocab + pron + exercises) y `recommendations(profile) -> list[str]`.
- `backend/domain/profile.py` (LEERLO): `_compute_profile(user_id)` obtiene `vocab` (lista de
  dicts con `word`), `errors` (dicts con `rule`, `message`, `count`, ...), y `progress` (dict de
  `get_progress` con `messages`, `exercises`, `corrections`, `pronunciation.average`). Hoy llama
  `estimate_cefr` y `recommendations`.
- `backend/schemas/profile.py` (LEERLO): `LearningProfile` con `cefr_level`, `vocabulary_size`,
  `top_words`, `recurring_errors`, `pronunciation_average`, `recommendations`.
- `backend/tests/test_profile.py` (LEERLO): tests existentes que **deben seguir verdes**:
  - `estimate_cefr({"vocab_size":0,"pronunciation_avg":None,"exercises":0}) == "A1"`.
  - `estimate_cefr({"vocab_size":200,"pronunciation_avg":75,"exercises":10}) == "B2"`.
  - `estimate_cefr({"vocab_size":1000,"pronunciation_avg":95,"exercises":100}) == "C2"`.
  - `test_profile_endpoint_shape` (chequea `cefr_level in ("A1","A2")` y otras claves).
- Estilo: `from __future__ import annotations`, docstrings en español, imports ordenados (ruff/isort).
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/cefr.py` — ampliar (mantén `recommendations` intacta)
Sustituye la función `estimate_cefr` actual por el código siguiente (conserva `CEFR_LEVELS` y
`recommendations` tal cual; añade las nuevas funciones). El objetivo es **un solo origen de
verdad**: `estimate_cefr` delega en `evaluate_cefr`.

```python
def _vocab_points(vocab: int) -> int:
    if vocab >= 900:
        return 4
    if vocab >= 400:
        return 3
    if vocab >= 150:
        return 2
    if vocab >= 50:
        return 1
    return 0


def _pron_points(pron: float | None) -> int:
    if pron is None:
        return 0
    if pron >= 85:
        return 3
    if pron >= 70:
        return 2
    if pron >= 50:
        return 1
    return 0


def _exercise_points(exercises: int) -> int:
    if exercises >= 50:
        return 3
    if exercises >= 20:
        return 2
    if exercises >= 5:
        return 1
    return 0


def _grammar_points(error_rate: float | None) -> int:
    if error_rate is None:
        return 0
    if error_rate <= 0.05:
        return 2
    if error_rate <= 0.15:
        return 1
    return 0


def _fluency_points(messages: int) -> int:
    if messages >= 50:
        return 2
    if messages >= 10:
        return 1
    return 0


def _level_from_points(points: int) -> str:
    if points >= 9:
        return "C2"
    if points >= 7:
        return "C1"
    if points >= 5:
        return "B2"
    if points >= 3:
        return "B1"
    if points >= 1:
        return "A2"
    return "A1"


def vocabulary_band(vocab: int) -> str:
    if vocab >= 2000:
        return "C2"
    if vocab >= 900:
        return "C1"
    if vocab >= 400:
        return "B2"
    if vocab >= 150:
        return "B1"
    if vocab >= 50:
        return "A2"
    return "A1"


def grammar_band(error_rate: float | None) -> str:
    if error_rate is None:
        return "—"
    if error_rate <= 0.05:
        return "B2"
    if error_rate <= 0.15:
        return "B1"
    if error_rate <= 0.30:
        return "A2"
    return "A1"


def fluency_band(messages: int) -> str:
    if messages >= 100:
        return "C1"
    if messages >= 50:
        return "B2"
    if messages >= 20:
        return "B1"
    if messages >= 5:
        return "A2"
    return "A1"


def pronunciation_band(avg: float | None) -> str:
    if avg is None:
        return "—"
    if avg >= 85:
        return "B2"
    if avg >= 70:
        return "B1"
    if avg >= 50:
        return "A2"
    return "A1"


_LEVEL_DESCRIPTORS = {
    "A1": "Principiante: frases muy básicas y vocabulario esencial.",
    "A2": "Básico: comunicación en rutinas y temas cotidianos.",
    "B1": "Intermedio: desenvoltura en situaciones familiares y opiniones simples.",
    "B2": "Intermedio alto: argumentación clara y comprensión de textos complejos.",
    "C1": "Avanzado: uso flexible y preciso del idioma en contextos variados.",
    "C2": "Maestría: dominio cercano al nativo con precisión y matices.",
}


def level_descriptor(level: str) -> str:
    return _LEVEL_DESCRIPTORS.get(level, "")


def evaluate_cefr(signals: dict) -> dict:
    """Evalúa el nivel CEFR con señales múltiples y devuelve nivel + bandas +
    descriptor.

    Señales: vocab_size, pronunciation_avg, exercises, grammar_error_rate
    (errores/mensaje, float|None) y messages. Las nuevas señales (grammar y
    fluency) son opcionales: si faltan, aportan 0 puntos y el resultado coincide
    con la heurística v1 original.
    """
    vocab = signals.get("vocab_size", 0)
    pron = signals.get("pronunciation_avg")
    exercises = signals.get("exercises", 0)
    error_rate = signals.get("grammar_error_rate")
    messages = signals.get("messages", 0)

    points = (
        _vocab_points(vocab)
        + _pron_points(pron)
        + _exercise_points(exercises)
        + _grammar_points(error_rate)
        + _fluency_points(messages)
    )
    level = _level_from_points(points)
    return {
        "level": level,
        "bands": {
            "vocabulary": vocabulary_band(vocab),
            "grammar": grammar_band(error_rate),
            "fluency": fluency_band(messages),
            "pronunciation": pronunciation_band(pron),
        },
        "descriptor": level_descriptor(level),
    }


def estimate_cefr(signals: dict) -> str:
    """Estima el nivel CEFR (delega en `evaluate_cefr`, manteniendo la API v1)."""
    return evaluate_cefr(signals)["level"]
```

### 2. `backend/schemas/profile.py` — ampliar `LearningProfile`
Añade `CefrBands` y los campos nuevos:

```python
class CefrBands(BaseModel):
    vocabulary: str
    grammar: str
    fluency: str
    pronunciation: str


class LearningProfile(BaseModel):
    user_id: str
    cefr_level: str
    cefr_bands: CefrBands
    cefr_descriptor: str
    vocabulary_size: int
    top_words: list[str]
    recurring_errors: list[GrammarRecurringError]
    pronunciation_average: float | None
    recommendations: list[str]
```

### 3. `backend/domain/profile.py` — componer la evaluación rica
- Cambia el import a `from services.cefr import evaluate_cefr, recommendations` (quita
  `estimate_cefr` si queda sin uso).
- En `_compute_profile`, tras obtener `progress`, calcula:

```python
    pron_avg = progress["pronunciation"]["average"]
    messages = progress["messages"]
    total_errors = sum(e["count"] for e in errors)
    grammar_error_rate = (total_errors / messages) if messages > 0 else None

    evaluation = evaluate_cefr(
        {
            "vocab_size": len(vocab),
            "pronunciation_avg": pron_avg,
            "exercises": progress["exercises"],
            "grammar_error_rate": grammar_error_rate,
            "messages": messages,
        }
    )
```

- Sustituye el uso de `level = estimate_cefr(...)` y el `return` para incluir:

```python
    return {
        "user_id": user_id,
        "cefr_level": evaluation["level"],
        "cefr_bands": evaluation["bands"],
        "cefr_descriptor": evaluation["descriptor"],
        "vocabulary_size": len(vocab),
        "top_words": [v["word"] for v in vocab[:5]],
        "recurring_errors": errors,
        "pronunciation_average": pron_avg,
        "recommendations": recs,
    }
```

(El cálculo de `recs = recommendations({...})` existente se mantiene igual.)

### 4. Test nuevo `backend/tests/test_cefr_evaluation.py` (9 tests)
Importa de `services.cefr` (`evaluate_cefr`, `estimate_cefr`, `vocabulary_band`, `grammar_band`)
y usa `TestClient` + `_setup` (patrón de `test_profile.py`) para el test del endpoint:

1. `test_evaluate_cefr_low_a1`: `evaluate_cefr({"vocab_size":0,"pronunciation_avg":None,"exercises":0})["level"] == "A1"`.
2. `test_evaluate_cefr_medium_b2`: `evaluate_cefr({"vocab_size":200,"pronunciation_avg":75,"exercises":10})["level"] == "B2"`.
3. `test_evaluate_cefr_high_c2`: `evaluate_cefr({"vocab_size":1000,"pronunciation_avg":95,"exercises":100})["level"] == "C2"`.
4. `test_evaluate_cefr_grammar_fluency_boost`: `evaluate_cefr({"vocab_size":200,"pronunciation_avg":75,"exercises":10,"grammar_error_rate":0.02,"messages":60})["level"] == "C1"` y `["bands"]["grammar"] == "B2"`.
5. `test_evaluate_cefr_bands_and_descriptor`: `evaluate_cefr({"vocab_size":200,"pronunciation_avg":75,"exercises":10})` tiene `bands` con claves `vocabulary`, `grammar`, `fluency`, `pronunciation` y `descriptor` no vacío.
6. `test_vocabulary_band_thresholds`: `vocabulary_band(0)=="A1"`, `(60)=="A2"`, `(200)=="B1"`, `(500)=="B2"`, `(1000)=="C1"`, `(2500)=="C2"`.
7. `test_grammar_band_unknown`: `grammar_band(None) == "—"`.
8. `test_estimate_cefr_delegates`: `estimate_cefr({"vocab_size":500,"pronunciation_avg":80,"exercises":30}) == evaluate_cefr({"vocab_size":500,"pronunciation_avg":80,"exercises":30})["level"]`.
9. `test_profile_endpoint_has_cefr_bands_and_descriptor`: crea un usuario, siembra vocabulario y un error gramatical (patrón de `test_profile.py`), llama `GET /api/profile?user_id=<id>` y comprueba `body["cefr_bands"]["vocabulary"]` presente y `body["cefr_descriptor"]` no vacío.

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 172 tests** (163 previos + 9 nuevos).
- `python -m ruff check .` **sin errores**.
- Los tests existentes de `test_profile.py` (incluidos `test_estimate_cefr_*` y
  `test_profile_endpoint_shape`) siguen verdes. No se modifica ningún test ni módulo existente
  salvo `services/cefr.py`, `schemas/profile.py` y `domain/profile.py`.

## Restricciones
- NO tocar el frontend.
- NO tocar `routers/`, `repositories/`, `main.py`, `dependencies.py`, ni `services/*` salvo
  `cefr.py`.
- NO cambiar `recommendations`.
- Mantener el estilo: docstrings en español, `from __future__ import annotations`,
  imports ordenados (ruff/isort).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.
