"""Alineación por palabra offline (`word_alignment_proxy`) — V3.29, Fase 3.

Genera y cachea timestamps por palabra de cada audio de referencia (TTS o humano)
transcribiendo el propio WAV con faster-whisper `word_timestamps=True`, y guarda
el resultado en un sidecar `{wav}.words.json` junto a la caché de audio.

Regla de honestidad (lección P20, `*_proxy`): la señal se llama
`word_alignment_proxy` porque es ASR-derivada, **no** verdad acústica. El modelo
reconoce el WAV y alinea sus palabras contra el texto audible; los tiempos que no
tienen respaldo (palabras que el ASR no reconoció) se interpolan de forma
monótona entre vecinas reconocidas y la cobertura se reporta en el sidecar. Si la
cobertura cae por debajo de `MIN_COVERAGE` la alineación se descarta (degradación
controlada: el frontend sigue usando el sync grueso de frase).

Flujo:
- `generate_listening_audio.py` y `domain.get_audio` llaman a
  `ensure_word_alignment(wav_path, source_text)` justo tras sintetizar/cachear un
  WAV; `import_audio.py` hace lo mismo para WAV humanos.
- `ensure_word_alignment` es idempotente: si el sidecar ya existe no re-transcribe
  (salvo `force=True`). Nunca lanza en producción: si ASR no está listo o falla,
  degrada devolviendo `None` (sin karaoke, sin romper el audio).

El módulo es puro y testeable sin modelo: `align_words`/`sidecar_path`/
`read_sidecar`/`write_sidecar` no tocan el ASR; `ensure_word_alignment` acepta el
transcriptor como inyectable para tests.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path

from config import WHISPER_SIZE

# Fracción mínima de palabras del texto audible que el ASR debe reconocer
# (alineadas 1:1) para aceptar la alineación. Por debajo, la señal no es fiable y
# se descarta (degradación al sync de frase).
MIN_COVERAGE = 0.8

# Etiqueta de la señal en el sidecar y en el payload (`sync` de cada palabra).
SYNC_ASR = "asr_word_proxy"

# Palabras visibles del texto audible: tokens con apóstrofo interno (`d'you`,
# `I'm`, `she'll`) sin puntuación. Conserva mayúsculas del texto original.
_DISPLAY_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")

# Normalización de los tokens del ASR (minúsculas, sin puntuación pegada).
_TOKEN_RE = re.compile(r"[a-z0-9']+")


def sidecar_path(wav_path: Path) -> Path:
    """Ruta del sidecar de alineación de un WAV (`{wav}.words.json`)."""
    return wav_path.with_name(f"{wav_path.name}.words.json")


def _engine_label() -> str:
    return f"faster-whisper-{WHISPER_SIZE}"


def _display_words(text: str) -> list[str]:
    """Palabras visibles del texto en orden (sin puntuación suelta)."""
    return _DISPLAY_WORD_RE.findall(text or "")


def _normalize(word: str) -> str:
    """Minúsculas y sin puntuación de un token (apóstrofo interno conservado)."""
    return "".join(_TOKEN_RE.findall(word.lower()))


def align_words(asr_words: list[dict], text: str) -> dict:
    """Alinea las palabras ASR contra el texto audible y devuelve timings.

    `asr_words` es la lista cruda de `transcribe_words` (`[{word, start, end}]`);
    `text` es el texto que suena (`spoken_text`, ya con `repetition_policy`).

    Devuelve `{"words": [{index, text, start, end}], "coverage": float}`:
    - Cada entrada corresponde a una palabra visible del texto (conservando su
      grafía), en orden y con tiempos monótonos crecientes.
    - `coverage` = fracción de palabras del texto alineadas 1:1 contra el ASR
      (sin contar interpolación). Si `coverage < MIN_COVERAGE` el llamador debe
      descartar la señal (devolver `[]`), no servir timings poco fiables.

    Alineación: `SequenceMatcher` entre los tokens normalizados del ASR y del
    texto. Las palabras del texto que el ASR no reconoce (eliminadas o
    sustituidas por una grafía distinta) quedan sin par 1:1 y su tiempo se
    **interpola** de forma monótona entre la vecina reconocida anterior y la
    siguiente (reparto proporcional al tamaño del hueco); prefijo y sufijo sin
    respaldo se anclan a su vecino más cercano. La interpolación nunca aporta
    cobertura.
    """
    display = _display_words(text)
    expected = [_normalize(w) for w in display]
    asr_entries: list[dict] = []
    for item in asr_words or []:
        raw = str(item.get("word") or item.get("text") or "").strip()
        if not raw:
            continue
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        end = max(end, start)
        for piece in re.split(r"\s+", raw):
            for token in _TOKEN_RE.findall(piece.lower()):
                asr_entries.append({"token": token, "start": start, "end": end})
    if not expected or not asr_entries:
        return {"words": [], "coverage": 0.0}

    asr_tokens = [entry["token"] for entry in asr_entries]
    # Índice de la palabra del texto → índice del ASR que la respalda (1:1).
    matched: dict[int, int] = {}
    sm = SequenceMatcher(None, asr_tokens, expected, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                matched[j1 + offset] = i1 + offset
        elif tag == "replace":
            # Emparejamiento exacto greedy dentro de la región de sustitución:
            # conserva el orden y solo casa tokens idénticos (p. ej. el ASR oyó
            # `She said` por `she said` —grafía distinta— y ambos quedan sin par).
            exp_cursor, asr_cursor = j1, i1
            while exp_cursor < j2 and asr_cursor < i2:
                if asr_tokens[asr_cursor] == expected[exp_cursor]:
                    matched[exp_cursor] = asr_cursor
                    exp_cursor += 1
                    asr_cursor += 1
                else:
                    # El token ASR actual no casa con esta palabra esperada:
                    # busca hacia delante dentro de la región antes de descartarlo.
                    ahead = next(
                        (e for e in range(exp_cursor, j2)
                         if expected[e] == asr_tokens[asr_cursor]),
                        None,
                    )
                    if ahead is not None:
                        exp_cursor = ahead
                    else:
                        asr_cursor += 1

    n = len(expected)
    starts: list[float | None] = [None] * n
    ends: list[float | None] = [None] * n
    for exp_idx, asr_idx in matched.items():
        starts[exp_idx] = asr_entries[asr_idx]["start"]
        ends[exp_idx] = asr_entries[asr_idx]["end"]

    def _fill(start_: float, end_: float, first: int, last: int) -> None:
        """Reparte [start_, end_] entre `display[first..last]` (gap interior)."""
        count = last - first + 1
        if count <= 0 or end_ <= start_:
            return
        weights = [len(display[i]) + 1 for i in range(first, last + 1)]
        total = sum(weights)
        cursor = start_
        for i in range(first, last + 1):
            span = (end_ - start_) * weights[i - first] / total
            starts[i] = cursor
            ends[i] = min(end_, cursor + span)
            cursor = ends[i]

    matched_positions = [i for i in range(n) if starts[i] is not None]
    if not matched_positions:
        return {"words": [], "coverage": 0.0}

    # Huecos interiores: interpolar entre la vecina anterior y la siguiente.
    prev = matched_positions[0]
    for pos in matched_positions[1:]:
        if pos > prev + 1:
            _fill(ends[prev] or 0.0, starts[pos] or 0.0, prev + 1, pos - 1)
        prev = pos

    first, last = matched_positions[0], matched_positions[-1]
    # Prefijo sin respaldo: ancla creciente hasta la primera reconocida.
    if first > 0:
        _fill(0.0, starts[first] or 0.0, 0, first - 1)
    # Sufijo sin respaldo: tras la última reconocida, cada palabra hereda su fin
    # (no hay frontera posterior; el resaltado simplemente no llega a activarse).
    for i in range(last + 1, n):
        starts[i] = ends[last]
        ends[i] = ends[last]

    coverage = len(matched) / n if n else 0.0
    words = [
        {
            "index": i,
            "text": display[i],
            "start": round(starts[i] or 0.0, 3),
            "end": round(ends[i] or starts[i] or 0.0, 3),
        }
        for i in range(n)
    ]
    return {"words": words, "coverage": round(coverage, 3)}


def write_sidecar(
    wav_path: Path,
    words: list[dict],
    source_text: str,
    *,
    coverage: float = 1.0,
) -> None:
    """Escribe el sidecar `{wav}.words.json` (atómico: `.tmp` → rename)."""
    payload = {
        "format": "word_alignment_proxy",
        "engine": _engine_label(),
        "sync": SYNC_ASR,
        "source_text": source_text,
        "coverage": round(float(coverage), 3),
        "words": words,
    }
    sidecar = sidecar_path(wav_path)
    tmp = sidecar.with_name(f"{sidecar.name}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(sidecar)


def read_sidecar(wav_path: Path) -> dict | None:
    """Lee el sidecar de un WAV; `None` si no existe o no es válido."""
    sidecar = sidecar_path(wav_path)
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("words"), list):
        return None
    return payload


def sidecar_words(wav_path: Path) -> list[dict]:
    """Palabras alineadas del sidecar (`[]` si no hay sidecar válido)."""
    payload = read_sidecar(wav_path)
    if payload is None:
        return []
    return [w for w in payload["words"] if isinstance(w, dict)]


def ensure_word_alignment(
    wav_path: Path,
    source_text: str,
    *,
    force: bool = False,
    transcribe: Callable[[bytes], list[dict]] | None = None,
) -> list[dict] | None:
    """Garantiza el sidecar de alineación de un WAV (idempotente, nunca lanza).

    Si el sidecar ya existe y no se fuerza, devuelve sus palabras. Si no, pide al
    transcriptor (`services.stt.transcribe_words` por defecto; inyectable en
    tests) las palabras ASR del WAV y escribe el sidecar.

    Devuelve la lista `[{index, text, start, end}]` alineada contra
    `source_text`, o `None` si no se pudo alinear con cobertura suficiente o el
    ASR no está disponible (degradación controlada: quien llama sigue sirviendo
    el audio sin karaoke).
    """
    existing = read_sidecar(wav_path)
    if existing is not None and not force:
        return [w for w in existing["words"] if isinstance(w, dict)]
    try:
        if transcribe is None:
            from services import stt

            if not stt.is_ready():
                return None
            transcribe = stt.transcribe_words
        asr_words = transcribe(wav_path.read_bytes())
    except Exception:  # noqa: BLE001 - nunca rompe el flujo de audio
        return None
    aligned = align_words(asr_words, source_text)
    if aligned["coverage"] < MIN_COVERAGE or not aligned["words"]:
        return None
    write_sidecar(wav_path, aligned["words"], source_text, coverage=aligned["coverage"])
    return aligned["words"]
