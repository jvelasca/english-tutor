# Subagente F7.1 — Evaluador compuesto de pronunciación (backend)

## Rol
Programador backend Python (FastAPI + SQLite). Sin acceso a Git ni al frontend.

## Objetivo
Sustituir el evaluador único actual de pronunciación (un `difflib.SequenceMatcher` a nivel de
caracteres) por un **evaluador compuesto determinista** (sin LLM, premisa 12) que devuelva,
además del `score` global, un **desglose por palabra** (correctas / omitidas / sustituidas /
extra) y un **score fonético** (Soundex). El breakdown viaja **solo en la respuesta** (no se
persiste: `pronunciation_attempts` sigue guardando `score`/`level` agregados, así F6 queda
intacta y no hay migración de BD).

## Contexto (autocontenido)
- Arquitectura: `Router → Service (domain) → Repository (repositories) → SQLite`.
- `backend/services/pronunciation.py` (LEERLO): hoy define `_normalize`, `_level`, `PASS_THRESHOLD = 80`
  y `score_pronunciation(expected, heard) -> dict` con `{expected, heard, score, level, ok}`.
  `level`: `good` (≥80), `fair` (≥50), `needs_practice` (<50).
- `backend/schemas/pronunciation.py` (LEERLO): `Level = Literal["good","fair","needs_practice"]`
  y `PronunciationResponse {expected, heard, score, level, ok}`.
- `backend/routers/pronunciation.py` (LEERLO, NO lo toques): hace
  `result = score_pronunciation(expected, heard)`, luego `PronunciationResponse(**result)` y
  `record_pronunciation(user_id, result["expected"], result["heard"], result["score"], result["level"])`.
  **Este router NO necesita cambios** si el dict que devuelve `score_pronunciation` y el schema
  `PronunciationResponse` crecen a la vez.
- `backend/tests/test_pronunciation.py` (LEERLO): tests existentes de `score_pronunciation` que
  **deben seguir verdes**:
  - `score_pronunciation("Hello world", "Hello world")` → `score == 100`, `ok is True`, `level == "good"`.
  - `score_pronunciation("Hello, world!", "hello world")` → `score == 100`.
  - `score_pronunciation("Hello", "")` → `score == 0`, `ok is False`, `level == "needs_practice"`.
  - `score_pronunciation("I have twenty years old", "I am twenty years old")` → `50 <= score < 100`.
- Estilo: `from __future__ import annotations`, docstrings en español, imports ordenados (ruff/isort).
- Verificación (desde `backend/`):
  ```powershell
  python -c "import main"
  python -m pytest tests/ -q
  python -m ruff check .
  ```

## Tarea detallada

### 1. `backend/services/phonetics.py` (nuevo, puro)

```python
"""Evaluadores fonéticos compuestos para pronunciación (puros, deterministas).

Combina precisión por palabra (alineación), similitud fonética (Soundex) y
similitud de caracteres para puntuar una lectura frente a lo esperado.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Pesos del score compuesto (deben sumar 1.0).
W_WORD = 0.6
W_PHONETIC = 0.3
W_CHAR = 0.1

_SOUNDEX_MAP = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
    "d": "3", "t": "3",
    "l": "4",
    "m": "5", "n": "5",
    "r": "6",
}


def tokenize(text: str) -> list[str]:
    """Normaliza y trocea en palabras: minúsculas y sin puntuación."""
    return re.findall(r"[a-z0-9']+", text.lower())


def soundex(word: str) -> str:
    """Codificación Soundex clásica simplificada (letra + 3 dígitos).

    - Conserva la primera letra en mayúscula.
    - Mapea el resto de consonantes según `_SOUNDEX_MAP`; vocales se descartan y
      reinician el dígito anterior (evita colapsar dobles separados por vocal).
    - `h` y `w` se descartan sin reiniciar (no separan dobles).
    - Se truncan/rellenan a 3 dígitos.
    Ejemplos: hello→H400, world→W643, coffee→C100, helo→H400.
    """
    w = word.lower()
    if not w:
        return ""
    first = w[0].upper()
    digits = ""
    prev = ""
    for ch in w[1:]:
        if ch in "hw":
            continue
        code = _SOUNDEX_MAP.get(ch)
        if code is None:
            prev = ""
            continue
        if code != prev:
            digits += code
            prev = code
    return first + (digits + "000")[:3]


def word_alignment(expected: str, heard: str) -> dict:
    """Alinea palabra a palabra con SequenceMatcher sobre listas de tokens."""
    e = tokenize(expected)
    h = tokenize(heard)
    correct: list[str] = []
    missing: list[str] = []
    extra: list[str] = []
    substituted: list[dict] = []
    sm = SequenceMatcher(None, e, h, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            correct.extend(e[i1:i2])
        elif tag == "delete":
            missing.extend(e[i1:i2])
        elif tag == "insert":
            extra.extend(h[j1:j2])
        elif tag == "replace":
            es = e[i1:i2]
            hs = h[j1:j2]
            substituted.extend(
                {"expected": ew, "heard": hw} for ew, hw in zip(es, hs)
            )
            if len(es) > len(hs):
                missing.extend(es[len(hs):])
            elif len(hs) > len(es):
                extra.extend(hs[len(es):])
    return {
        "correct": correct,
        "missing": missing,
        "extra": extra,
        "substituted": substituted,
        "total": len(e),
    }


def word_accuracy(expected: str, heard: str) -> float:
    """Ratio (0-1) de palabras esperadas dichas correctamente."""
    e = tokenize(expected)
    h = tokenize(heard)
    if not e:
        return 1.0 if not h else 0.0
    sm = SequenceMatcher(None, e, h, autojunk=False)
    matched = sum(i2 - i1 for tag, i1, i2, _, _ in sm.get_opcodes() if tag == "equal")
    return matched / len(e)


def phonetic_similarity(expected: str, heard: str) -> float:
    """Ratio (0-1) de palabras esperadas con Soundex coincidente (greedy, sin
    reutilizar palabras oídas)."""
    e = tokenize(expected)
    h = tokenize(heard)
    if not e:
        return 1.0 if not h else 0.0
    h_keys = [soundex(w) for w in h]
    used = [False] * len(h_keys)
    matched = 0
    for ew in e:
        key = soundex(ew)
        for i, hk in enumerate(h_keys):
            if not used[i] and hk == key:
                matched += 1
                used[i] = True
                break
    return matched / len(e)


def composite_score(expected: str, heard: str) -> dict:
    """Devuelve el score compuesto (0-100), sus componentes y el breakdown."""
    wa = word_accuracy(expected, heard)
    ps = phonetic_similarity(expected, heard)
    e = tokenize(expected)
    h = tokenize(heard)
    char_ratio = SequenceMatcher(None, " ".join(e), " ".join(h)).ratio() if (e or h) else 0.0
    score = round(100 * (W_WORD * wa + W_PHONETIC * ps + W_CHAR * char_ratio))
    return {
        "score": score,
        "word_accuracy": round(wa * 100),
        "phonetic_score": round(ps * 100),
        "breakdown": word_alignment(expected, heard),
    }
```

### 2. `backend/services/pronunciation.py` — delegar en el compuesto
Mantén `_normalize`, `_level`, `PASS_THRESHOLD` (no cambies sus umbrales). Refactoriza
`score_pronunciation` para devolver el contrato ampliado:

```python
from services.phonetics import composite_score


def score_pronunciation(expected: str, heard: str) -> dict:
    """Devuelve score/level/ok + word_accuracy + phonetic_score + breakdown."""
    comp = composite_score(expected, heard)
    score = comp["score"]
    return {
        "expected": expected.strip(),
        "heard": heard.strip(),
        "score": score,
        "level": _level(score),
        "ok": score >= PASS_THRESHOLD,
        "word_accuracy": comp["word_accuracy"],
        "phonetic_score": comp["phonetic_score"],
        "breakdown": comp["breakdown"],
    }
```

### 3. `backend/schemas/pronunciation.py` — ampliar el contrato
Mantén `Level` y añade:

```python
class WordSubstitution(BaseModel):
    expected: str
    heard: str


class PronunciationBreakdown(BaseModel):
    correct: list[str]
    missing: list[str]
    extra: list[str]
    substituted: list[WordSubstitution]
    total: int


class PronunciationResponse(BaseModel):
    expected: str
    heard: str
    score: int
    level: Level
    ok: bool
    word_accuracy: int
    phonetic_score: int
    breakdown: PronunciationBreakdown
```

### 4. `backend/routers/pronunciation.py` — SIN cambios
Verifica que no necesita modificación: `PronunciationResponse(**result)` aceptará los campos
nuevos porque `score_pronunciation` y el schema crecen a la vez. No lo edites si no es necesario.

### 5. Test nuevo `backend/tests/test_phonetics.py` (12 tests)
Importa de `services.phonetics` (`tokenize`, `soundex`, `word_alignment`, `word_accuracy`,
`phonetic_similarity`, `composite_score`) y de `services.pronunciation` (`score_pronunciation`):

1. `test_tokenize_lowercases_and_strips_punct`: `tokenize("Hello, world!") == ["hello", "world"]`.
2. `test_soundex_hello`: `soundex("hello") == "H400"`.
3. `test_soundex_world`: `soundex("world") == "W643"`.
4. `test_soundex_coffee`: `soundex("coffee") == "C100"`.
5. `test_soundex_empty_word`: `soundex("") == ""`.
6. `test_word_alignment_exact_match`: `word_alignment("Hello world", "Hello world")` →
   `correct == ["hello", "world"]`, `missing == []`, `extra == []`, `substituted == []`, `total == 2`.
7. `test_word_alignment_substitution`: `word_alignment("I have twenty years old", "I am twenty years old")`
   → `substituted == [{"expected": "have", "heard": "am"}]`, `correct == ["i", "twenty", "years", "old"]`.
8. `test_word_alignment_missing_words`: `word_alignment("Hello world", "Hello")` →
   `missing == ["world"]`, `correct == ["hello"]`.
9. `test_word_alignment_extra_words`: `word_alignment("Hello", "Hello world")` →
   `extra == ["world"]`, `correct == ["hello"]`.
10. `test_word_accuracy_partial`: `word_accuracy("I have twenty years old", "I am twenty years old")`
    ≈ `0.8` (usa `pytest.approx(0.8)` o compara con 4/5).
11. `test_phonetic_similarity_catches_near_miss`: `phonetic_similarity("hello", "helo") == 1.0`
    (ambos `H400`).
12. `test_composite_score_exact_empty_partial`:
    - `composite_score("Hello world", "Hello world")["score"] == 100`.
    - `composite_score("Hello", "")["score"] == 0`.
    - `50 <= composite_score("I have twenty years old", "I am twenty years old")["score"] < 100`.

Además, en `test_pronunciation.py` los tests existentes **deben seguir pasando** (ver Contexto).
No los modifiques. Si quieres, añade UN test más en `test_pronunciation.py` que verifique que
`score_pronunciation("Hello world", "Hello world")["breakdown"]["total"] == 2` y
`["word_accuracy"] == 100` (opcional, no obligatorio).

## Criterios de aceptación
- `python -c "import main"` no falla.
- `python -m pytest tests/ -q` **verde: 163 tests** (151 previos + 12 nuevos).
- `python -m ruff check .` **sin errores**.
- Los tests existentes de `test_pronunciation.py`, `test_progress.py` y `test_api_security.py`
  siguen verdes. No se modifica ningún test ni módulo existente salvo `services/pronunciation.py`
  y `schemas/pronunciation.py`.

## Restricciones
- NO tocar el frontend.
- NO tocar `routers/pronunciation.py`, `domain/`, `repositories/`, `main.py`, `dependencies.py`.
- NO persistir el breakdown (sin migración de `pronunciation_attempts`).
- NO cambiar los umbrales de `level` (`good ≥80`, `fair ≥50`) ni `PASS_THRESHOLD`.
- Mantener el estilo: docstrings en español, `from __future__ import annotations`,
  imports ordenados (ruff/isort).

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de
`python -m pytest tests/ -q`, de `python -m ruff check .`, y cualquier desviación.
