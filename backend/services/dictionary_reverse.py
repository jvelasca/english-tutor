"""Búsqueda inversa del diccionario de consulta (V3.39, puro).

El diccionario de consulta (V3.30) es unidireccional EN→ES: se busca una
palabra inglesa y se sirve su definición en inglés simple más la traducción al
español. Esta capa añade la dirección ES→EN SIN tocar la caché directa:

1. **Inversa instantánea** — `match_translation(term, entries)` compara el
   término español contra las traducciones ya cacheadas en
   `dictionary_entries.translation`. Si la traducción es una glosa múltiple
   ("casa, hogar"), se segmenta y basta con que UN segmento coincida. Es
   instantáneo (no paga latencia del modelo) y funciona con la caché existente.
2. **Generación** — si no hay coincidencia, el dominio genera el contenido
   ES→EN con el modelo local y lo cachea en `dictionary_reverse_entries`
   (`services.dictionary_content.generate_reverse_content`).

Puro y determinista: recibe las entradas ya leídas (`dictionary_repo`) y no
toca BD ni red. La comparación es tolerante a acentos y mayúsculas, pero NO
pliega la eñe (`ñ` ≠ `n`): "año" y "ano" son palabras distintas y confundirlas
sería un falso positivo grave. Ignora el contenido entre paréntesis y los
artículos iniciales de la glosa ("la casa" ≈ "casa").
"""

from __future__ import annotations

import re
import unicodedata

# Separadores de glosa en las traducciones del generador: "casa, hogar",
# "coger / tomar", "grande; alto". Las barras y los puntos y coma aparecen
# cuando el modelo devuelve varias acepciones en una sola cadena.
_GLOSS_SPLIT = re.compile(r"[,;/|]+")

# Contenido entre paréntesis (aclaraciones del generador: "banco (dinero)").
_PARENTHETICAL = re.compile(r"\([^)]*\)")

# Artículos/determinantes iniciales de una glosa en español: "la casa" y
# "casa" deben coincidir. No se tocan dentro de locuciones ("casa de campo").
_LEADING_ARTICLES = frozenset(
    {"el", "la", "los", "las", "un", "una", "unos", "unas"}
)

_SPACES = re.compile(r"\s+")


def fold(text: str) -> str:
    """Minúsculas sin acentos (la eñe se conserva como letra distinta).

    `unicodedata.normalize("NFD")` descompone "á" en "a" + tilde combinante y
    el filtrado de marcas la convierte en "a"; "ñ" también se descompone en
    "n" + virgulilla, así que se restaura explícitamente para no confundir
    "año" con "ano" ni "mañana" con "manana".
    """
    lowered = (text or "").strip().lower().replace("ñ", "\u0000")
    decomposed = unicodedata.normalize("NFD", lowered)
    without_marks = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    )
    return without_marks.replace("\u0000", "ñ")


def normalize_term(text: str) -> str:
    """Normaliza un término de búsqueda (español o inglés) para comparar.

    Recorta puntuación circundante, colapsa espacios y pliega acentos. Devuelve
    "" si queda vacío (solo puntuación/espacios).
    """
    folded = fold(text)
    folded = re.sub(r"^[^a-z0-9ñ]+", "", folded)
    folded = re.sub(r"[^a-z0-9ñ]+$", "", folded)
    folded = _SPACES.sub(" ", folded).strip()
    return folded


def _gloss_segments(translation: str) -> list[str]:
    """Segmentos comparables de una traducción (glosa múltiple → varios)."""
    cleaned = _PARENTHETICAL.sub(" ", translation or "")
    segments: list[str] = []
    for raw in _GLOSS_SPLIT.split(cleaned):
        segment = normalize_term(raw)
        if not segment:
            continue
        parts = segment.split(" ")
        if len(parts) > 1 and parts[0] in _LEADING_ARTICLES:
            segment = " ".join(parts[1:]).strip()
            if not segment:
                continue
        segments.append(segment)
    return segments


def _segment_score(segment: str, term: str) -> int:
    """Calidad de la coincidencia de un segmento de glosa con el término.

    2 — coincidencia exacta ("casa" == "casa");
    1 — el segmento empieza por el término y sigue una palabra
        ("casa" ~ "casa de campo");
    0 — el término aparece como palabra completa en cualquier posición.
    Devuelve -1 si no hay coincidencia.
    """
    if segment == term:
        return 2
    if segment.startswith(term + " "):
        return 1
    if re.search(rf"(?:^| ){re.escape(term)}(?: |$)", segment):
        return 1
    return -1


def match_translation(term: str, entries: list[dict]) -> list[str]:
    """Palabras inglesas cuya traducción ES coincide con `term` (V3.39, puro).

    Devuelve las palabras inglesas ordenadas por CALIDAD de coincidencia (exacta
    antes que parcial) y, a igualdad, alfabéticamente para que el resultado sea
    determinista. Sin duplicados: una misma palabra inglesa que coincide por
    varios segmentos aparece una sola vez con su mejor puntuación.

    `entries` son filas de `dictionary_entries` con `word` (inglés) y
    `translation` (español). Un término vacío o sin coincidencias devuelve [].
    """
    normalized = normalize_term(term)
    if not normalized:
        return []
    best: dict[str, tuple[str, int]] = {}
    for entry in entries or []:
        english = (entry.get("word") or "").strip()
        if not english:
            continue
        score = -1
        for segment in _gloss_segments(entry.get("translation") or ""):
            score = max(score, _segment_score(segment, normalized))
        if score < 0:
            continue
        key = english.lower()
        current = best.get(key)
        if current is None or score > current[1]:
            best[key] = (english, score)
    ordered = sorted(best.values(), key=lambda item: (-item[1], item[0].lower()))
    return [english for english, _ in ordered]
