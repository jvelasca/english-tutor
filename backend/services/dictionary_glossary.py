"""Glosario curado ES→EN del diccionario de consulta (V3.95.0).

Autoridad léxica DETERMINISTA para la búsqueda inversa: una tabla de pares
español → inglés curada a mano (herramientas, oficios y casa, más el vocabulario
que los packs temáticos no declaran). Es la PRIMERA autoridad de
`domain.vocabulary._lookup_dictionary_reverse`, por delante de los packs y de la
caché del modelo, porque un par escrito a mano no puede alucinar.

Por qué un fichero aparte y no un pack más:

- un pack es contenido de ESTUDIO (se siembra en `vocab_collections` y el alumno
  lo ve y se matricula); el glosario es una tabla de REFERENCIA para resolver la
  búsqueda inversa, y no debe aparecer en la pantalla de colecciones;
- un pack está indexado por la palabra INGLESA (`word`), que es justo lo contrario
  de lo que la inversa necesita: aquí la cabeza es el término ESPAÑOL (`es`).

El contenido vive en `curriculum/lexicon/es_en_glossary.json` (versionado en
git, como los packs), NO en `backend/data/` (ignorado por git).

El formato de salida imita al de `repositories.collections.list_pack_items`
(`{word, translation, pos, ...}`) para reutilizar el MISMO matcher probado
(`services.dictionary_reverse.match_pack_translation`) en vez de escribir un
segundo comparador: aquí `word` es el equivalente INGLÉS y `translation` el
término ESPAÑOL buscado. `priority` desempata entre varios equivalentes curados
del mismo término (gana el de más prioridad; sin ella, orden alfabético).

Puro respecto a la app: solo lee un fichero de datos del repositorio. La caché en
memoria se invalida por `mtime` para que editar el JSON se note sin reiniciar.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# El glosario vive junto a los packs curados, en el contenido versionado.
GLOSSARY_PATH = (
    Path(__file__).resolve().parent.parent
    / "curriculum"
    / "lexicon"
    / "es_en_glossary.json"
)

# Caché por `mtime`: (mtime del fichero, ítems cargados). Editar el JSON lo
# invalida en la siguiente consulta sin reiniciar el backend.
_CACHE: tuple[float, tuple[dict, ...]] | None = None


def _item(raw: object) -> dict | None:
    """Un ítem del JSON → la forma que consume el matcher, o None si inservible.

    Un ítem sin término español o sin equivalente inglés se descarta (no puede
    aportar nada a la inversa); el resto se limpia y se normaliza a la forma
    `{word, translation, pos, priority}`. `priority` es un entero; cualquier otro
    valor (o su ausencia) vale 0.
    """
    if not isinstance(raw, dict):
        return None
    spanish = str(raw.get("es") or "").strip()
    english = str(raw.get("en") or "").strip()
    if not spanish or not english:
        return None
    try:
        priority = int(raw.get("priority") or 0)
    except (TypeError, ValueError):
        priority = 0
    return {
        "word": english,
        "translation": spanish,
        "pos": str(raw.get("pos") or "").strip().lower(),
        "priority": priority,
    }


def _load() -> tuple[dict, ...]:
    """Lee el fichero del glosario y devuelve sus ítems ya normalizados."""
    try:
        payload = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # Sin fichero, la app sigue funcionando con packs + caché + modelo: el
        # glosario es una MEJORA de autoridad, no un requisito de arranque.
        return ()
    except (OSError, json.JSONDecodeError):
        logger.warning("glosario ES→EN ilegible: %s", GLOSSARY_PATH, exc_info=True)
        return ()
    entries = payload.get("entries") if isinstance(payload, dict) else None
    items: list[dict] = []
    for raw in entries or []:
        item = _item(raw)
        if item is not None:
            items.append(item)
    return tuple(items)


def glossary_items() -> tuple[dict, ...]:
    """Ítems curados ES→EN del glosario, cacheados por `mtime` del fichero.

    Devuelve la MISMA forma que `repositories.collections.list_pack_items`, para
    que el dominio pueda unir ambos catálogos sin adaptadores. Nunca lanza: un
    fichero ausente o corrupto devuelve una tupla vacía (se degrada a packs +
    caché + modelo).
    """
    global _CACHE
    try:
        mtime = GLOSSARY_PATH.stat().st_mtime
    except OSError:
        return ()
    if _CACHE is not None and _CACHE[0] == mtime:
        return _CACHE[1]
    items = _load()
    _CACHE = (mtime, items)
    return items


def reset_cache() -> None:
    """Limpia la caché en memoria del glosario (tests que reescriben el JSON)."""
    global _CACHE
    _CACHE = None
