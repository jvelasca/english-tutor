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

    V3.91: esta función deja de ser solo del comparador. El índice FTS5 de la
    caché guarda el texto YA plegado por ella (columna
    `dictionary_entries.translation_fold`) y la consulta dirigida se pliega
    igual, porque un índice que no plegara como el matcher escondería
    candidatos que el matcher sí acepta.
    """
    lowered = (text or "").strip().lower().replace("ñ", "\u0000")
    decomposed = unicodedata.normalize("NFD", lowered)
    without_marks = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    )
    return without_marks.replace("\u0000", "ñ")


# Tokenizador de las FRASES FTS5 (V3.91): letras y dígitos, con la eñe como
# letra propia. Se aplica al término YA plegado, así que indexación y consulta
# parten de la misma forma del texto.
_FTS_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def phrase_tokens(term: str) -> list[str]:
    """Tokens FTS5 de un término, ya plegados: `["casa", "de", "campo"]` (V3.91).

    Es la ÚNICA definición de «qué palabras forman el término»: la usan la frase
    del índice y el filtro `LIKE` del repliegue, así que las dos vías de la
    consulta no pueden acabar buscando cosas distintas. Solo letras y dígitos
    (con la eñe como letra propia), de modo que un token no puede contener un
    comodín de `LIKE` ni un operador de FTS5.
    """
    return _FTS_TOKEN.findall(fold(term))


def phrase_query(term: str) -> str:
    """Frase FTS5 de un término: `"casa" "de" "campo"` (V3.91, puro).

    Devuelve la consulta que pide los tokens del término como secuencia
    CONTIGUA, que es exactamente la condición que `_segment_score` exige para
    dar una coincidencia de palabra completa. El matcher sigue siendo quien
    puntúa: esto solo acota el conjunto que se le entrega.

    Cada token va entre comillas dobles (nunca contiene comillas: el tokenizador
    solo admite letras y dígitos), así que la cadena no puede inyectar operadores
    de FTS5. Un término sin tokens (solo puntuación) devuelve "".
    """
    return " ".join(f'"{token}"' for token in phrase_tokens(term))


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


def _pack_term_score(translation: str, term: str) -> int:
    """Mejor puntuación de `term` contra los segmentos de una traducción curada."""
    score = -1
    for segment in _gloss_segments(translation or ""):
        score = max(score, _segment_score(segment, term))
    return score


def match_pack_translation(term: str, items: list[dict]) -> list[dict]:
    """Equivalentes INGLESES curados del término español `term` (V3.86.0).

    Autoridad determinista y GRATIS (sin latencia del modelo) sobre el catálogo
    global de packs: `items` son filas de `vocab_collection_items` con `word`
    (inglés), `translation` (español) y `pos`. Es lo que hace que «tornillo» dé
    «screw» y «lima» dé «file» aunque la caché no tenga la entrada o el modelo
    devuelva un nombre propio.

    Devuelve `[{word, pos}]` ordenados por calidad de coincidencia (exacta antes
    que parcial) y, a igualdad, alfabéticamente (determinista). Sin duplicados:
    un mismo equivalente que coincide por varios packs aparece una sola vez con
    su mejor puntuación. Un término vacío o sin coincidencias devuelve [].
    """
    normalized = normalize_term(term)
    if not normalized:
        return []
    best: dict[str, tuple[dict, int]] = {}
    for item in items or []:
        english = (item.get("word") or "").strip()
        if not english:
            continue
        score = _pack_term_score(item.get("translation") or "", normalized)
        if score < 0:
            continue
        key = english.lower()
        current = best.get(key)
        if current is None or score > current[1]:
            best[key] = (
                {"word": english, "pos": str(item.get("pos") or "").strip().lower()},
                score,
            )
    ordered = sorted(
        best.values(), key=lambda item: (-item[1], item[0]["word"].lower())
    )
    return [entry for entry, _ in ordered]
