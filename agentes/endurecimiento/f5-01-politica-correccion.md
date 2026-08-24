# Subagente F5.1 — Tutor Policy (correctness policy)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Primera pieza de la Fase 5 (Tutor Policy + Context Builder): una **política de corrección** que
traduce el nivel CEFR del alumno a una guía de cómo debe corregir el tutor. Función pura y
determinista (premisa 12): sin LLM, sin red, sin FastAPI. Este subagente solo añade la función
y sus tests; el cableado al prompt llega en F5.2.

## Contexto (autocontenido)
- `backend/services/cefr.py` (F4.4, LEERLO): define `CEFR_LEVELS = ["A1","A2","B1","B2","C1","C2"]`.
- `backend/services/vocabulary.py` y `backend/services/grammar.py`: patrón de **función pura** en
  `services/` (docstrings en español, `from __future__ import annotations`).
- `backend/config.py`: `MODE_PROMPTS` (system prompts de tutor, en inglés).
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/policy.py` (nuevo)
```python
"""Política de corrección del tutor según el nivel CEFR (puro, determinista)."""
from __future__ import annotations

# Guía por nivel CEFR que se añade al system prompt del tutor (en inglés,
# coherente con MODE_PROMPTS).
CORRECTNESS_GUIDANCE: dict[str, str] = {
    "A1": (
        "The learner is a beginner (CEFR A1). Correct every error gently and in "
        "simple language; explain in Spanish when helpful."
    ),
    "A2": (
        "The learner is elementary (CEFR A2). Correct errors clearly and keep "
        "explanations brief."
    ),
    "B1": (
        "The learner is intermediate (CEFR B1). Correct errors but focus on the "
        "most important ones."
    ),
    "B2": (
        "The learner is upper-intermediate (CEFR B2). Correct subtle errors and "
        "idiomatic usage."
    ),
    "C1": (
        "The learner is advanced (CEFR C1). Only point out subtle errors or "
        "naturalness issues; do not over-explain."
    ),
    "C2": (
        "The learner is proficient (CEFR C2). Focus on nuance, register and style."
    ),
}


def correctness_guidance(cefr_level: str) -> str:
    """Devuelve la guía de corrección para un nivel CEFR; si el nivel no se
    reconoce, usa la del intermedio (B1)."""
    return CORRECTNESS_GUIDANCE.get(cefr_level, CORRECTNESS_GUIDANCE["B1"])
```

### 2. Test nuevo `backend/tests/test_policy.py`
```python
from services.cefr import CEFR_LEVELS
from services.policy import CORRECTNESS_GUIDANCE, correctness_guidance


def test_all_cefr_levels_have_guidance():
    assert set(CORRECTNESS_GUIDANCE.keys()) == set(CEFR_LEVELS)


def test_guidance_varies_by_level():
    assert correctness_guidance("A1") != correctness_guidance("C2")


def test_guidance_known_level():
    assert correctness_guidance("B2") == CORRECTNESS_GUIDANCE["B2"]


def test_guidance_unknown_falls_back_to_b1():
    assert correctness_guidance("Z9") == CORRECTNESS_GUIDANCE["B1"]
```

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 118 tests** (114 previos + 4 nuevos).
- `python -m ruff check .` **sin errores**.

## Restricciones
- NO tocar el frontend.
- NO tocar `domain/`, `repositories/`, `routers/`, `schemas/`, ni `services/` existentes.
- Mantener el estilo (docstrings en español, `from __future__ import annotations`, ruff limpio).

## Salida
Lista de archivos creados, salida de `python -m pytest tests/ -q`, de `python -m ruff check .`,
y cualquier desviación.
