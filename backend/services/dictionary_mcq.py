"""Pregunta MCQ de reconocimiento definición ↔ palabra (V3.33, eslabón del
puente V3.32).

Segundo eslabón del Dictionary → Learning Bridge: el peldaño "Recognition" de la
escalera compartida de drill. El alumno ve la palabra (surface form) y elige su
significado entre opciones que sirve el backend. La pregunta es PURA y
DETERMINISTA dado (palabra, seed de intento) (premisa 21, sin estado servidor):
el servidor la vuelve a derivar con esta misma función al puntuar el intento
(mismo patrón que `submit_sentence_attempt` con la frase de contexto), usando el
`question_id` que el GET entregó como seed.

Reglas de honestidad:
- La opción correcta es un texto de significado REAL de la diana (traducción si
  existe, definición si no) de la caché global `dictionary_entries`;
- Los distractores son textos de significado (mismo modo, un solo idioma entre
  opciones) de OTRAS entradas globales, preferentemente del mismo `pos`; nunca
  se inventan significados (sin LLM);
- Si no hay suficientes distractores distintos (>= 2), la pregunta NO está
  disponible (`None`): el peldaño degrada con aviso en lugar de forzar una
  pregunta mala;
- El barajado oculta la correcta con una permutación derivada de
  `palabra + seed` (V3.33.1): el seed es un nonce por intento que el GET entrega
  como `question_id`, de modo que reintentar la MISMA palabra rebaraja las
  opciones (no se puede aprender la posición de la correcta) sin guardar estado
  servidor. Sin seed el orden sigue siendo estable entre procesos/máquinas.
"""

from __future__ import annotations

import hashlib

_MAX_OPTIONS = 4
_MIN_DISTRACTORS = 2


def _stable_int(text: str) -> int:
    """Entero estable entre procesos para una cadena (hash no aleatorizado).

    V3.33.1: SHA-256 en lugar de la suma ponderada por posición (que colisionaba
    entre palabras distintas). Es estable entre procesos/máquinas (a diferencia
    de `hash()`, aleatorizado por `PYTHONHASHSEED`) y reparte mucho mejor el
    índice de la correcta. No necesita resistencia criptográfica: solo una
    dispersión buena y reproducible.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _place_options(key: str, options: list[str]) -> tuple[list[str], int]:
    """Ordena las opciones de forma estable y devuelve el índice de la correcta.

    Mismo patrón que `listening_bottom_up._place_options`: permutación
    determinista derivada de la clave `palabra + seed`, de modo que la correcta
    no queda siempre en la primera posición y el orden cambia entre intentos
    (sin estado servidor).
    """
    n = len(options)
    shift = _stable_int(key) % n
    ordered = [options[(i - shift) % n] for i in range(n)]
    return ordered, shift % n  # la correcta (índice 0 pre-barajado) acaba en `shift`


def _candidate_meanings(entries: list[dict], target: dict, field: str) -> list[str]:
    """Textos de significado (modo `field`) de otras entradas, como distractores.

    Pura y determinista: descarta la propia diana, entradas sin texto en el
    modo y textos duplicados entre sí o idénticos a la correcta (por `casefold`,
    para no ofrecer dos opciones indistinguibles). Prefiere las entradas del
    MISMO `pos` que la diana y, dentro de cada franja, orden alfabético por
    `word` (independiente del orden de inserción en la caché).
    """
    target_word = (target.get("word") or "").strip().lower()
    target_pos = (target.get("pos") or "").strip()
    target_text = (target.get(field) or "").strip()
    by_text: dict[str, tuple[str, str, str]] = {}
    for entry in entries:
        word = (entry.get("word") or "").strip()
        text = (entry.get(field) or "").strip()
        if not word or not text or word.lower() == target_word:
            continue
        key = text.casefold()
        if key == target_text.casefold() or key in by_text:
            continue
        by_text[key] = (text, word, (entry.get("pos") or "").strip())
    ordered = sorted(
        by_text.values(),
        key=lambda item: (
            0 if target_pos and item[2] == target_pos else 1,
            item[1].lower(),
        ),
    )
    return [text for text, _word, _pos in ordered]


def recognition_options_for(
    word: str, entries: list[dict], seed: str = ""
) -> tuple[list[str], int] | None:
    """Opciones `(options, correct_index)` del MCQ de la palabra, o `None`.

    - Modo de la opción correcta: `translation` si la diana tiene traducción y
      hay >= 2 distractores con traducción; si no, `definition` (mismas
      condiciones). Nunca se mezclan idiomas entre opciones de una pregunta.
    - `options` no incluye metadatos: el cliente no puede distinguir cuál es la
      correcta; `correct_index` solo lo devuelve el servidor al puntuar.
    - `seed` (V3.33.1) es el nonce de intento (`question_id`): solo altera el
      orden barajado, nunca qué opciones componen la pregunta (la selección de
      distractores sigue siendo determinista por palabra). Reintentar con otro
      seed rebaraja la posición de la correcta.
    - `None` si la diana no existe o no hay suficientes significados distintos
      en la caché global (el peldaño degrada con aviso, sin evento).
    """
    target_word = (word or "").strip().lower()
    target = next(
        (e for e in entries if (e.get("word") or "").strip().lower() == target_word),
        None,
    )
    if target is None:
        return None
    for field in ("translation", "definition"):
        correct = (target.get(field) or "").strip()
        if not correct:
            continue
        candidates = _candidate_meanings(entries, target, field)
        if len(candidates) < _MIN_DISTRACTORS:
            continue
        distractors = candidates[: _MAX_OPTIONS - 1]
        place_key = f"{target_word}:{seed}"
        return _place_options(place_key, [correct, *distractors])
    return None
