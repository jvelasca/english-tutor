"""Contenido de los packs temáticos de vocabulario (V3.84.0).

`ensure_theme_packs_seeded` siembra los packs desde
`backend/curriculum/vocab_packs/*.json` sin migración: un JSON mal formado o con
palabras repetidas se colaría en el catálogo global sin que ningún test mordiera.
Aquí se valida la **forma** del contenido (no la calidad léxica, que es autoría).

Se comprueba, por cada archivo:

- que parsea y tiene `slug`, `title` e `items`;
- que `slug` es único en todo el directorio y coincide con el nombre del fichero;
- que hay entre 40 y 60 ítems (decisión de V3.84.0: packs «grandes»);
- que cada ítem tiene `word`, `lemma`, `translation` y `pos` no vacíos;
- que no hay palabras normalizadas repetidas dentro del mismo pack.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PACKS_DIR = (
    Path(__file__).resolve().parent.parent / "curriculum" / "vocab_packs"
)

MIN_ITEMS = 40
MAX_ITEMS = 60

# Packs que V3.84.0 debe dejar disponibles (ampliables sin tocar el test).
REQUIRED_SLUGS = {
    "food",
    "travel",
    "work",
    "tools",
    "computing",
    "health",
    "home",
    "city",
    "nature",
    "body",
    "sports",
    "clothes",
    "feelings",
    "school",
    "business",
}


def _pack_files() -> list[Path]:
    return sorted(PACKS_DIR.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_packs_directory_exists_and_is_non_empty():
    assert PACKS_DIR.is_dir(), f"no existe el directorio de packs: {PACKS_DIR}"
    assert _pack_files(), "no hay ningún pack JSON"


def test_required_slugs_present():
    slugs = {str(_load(p).get("slug") or p.stem) for p in _pack_files()}
    faltan = REQUIRED_SLUGS - slugs
    assert not faltan, f"faltan packs requeridos: {sorted(faltan)}"


def test_slugs_unique_and_match_filename():
    seen: dict[str, str] = {}
    for path in _pack_files():
        slug = str(_load(path).get("slug") or "").strip().lower()
        assert slug, f"{path.name}: slug vacío"
        assert slug == path.stem, (
            f"{path.name}: el slug '{slug}' no coincide con el nombre del fichero"
        )
        assert slug not in seen, (
            f"slug duplicado '{slug}' en {path.name} y {seen[slug]}"
        )
        seen[slug] = path.name


@pytest.mark.parametrize("path", _pack_files(), ids=lambda p: p.stem)
def test_pack_shape_and_items(path: Path):
    payload = _load(path)

    for key in ("slug", "title", "items"):
        assert payload.get(key), f"{path.name}: falta '{key}'"
    assert isinstance(payload["items"], list), f"{path.name}: 'items' no es lista"

    items = payload["items"]
    assert MIN_ITEMS <= len(items) <= MAX_ITEMS, (
        f"{path.name}: {len(items)} ítems (se esperan {MIN_ITEMS}-{MAX_ITEMS})"
    )

    seen_words: dict[str, int] = {}
    for idx, item in enumerate(items):
        assert isinstance(item, dict), f"{path.name}[{idx}]: no es un objeto"
        for key in ("word", "lemma", "translation", "pos"):
            value = str(item.get(key) or "").strip()
            assert value, f"{path.name}[{idx}]: '{key}' vacío"
        word = str(item["word"]).strip().lower()
        assert word not in seen_words, (
            f"{path.name}: palabra duplicada '{word}' "
            f"({idx} y {seen_words[word]})"
        )
        seen_words[word] = idx
