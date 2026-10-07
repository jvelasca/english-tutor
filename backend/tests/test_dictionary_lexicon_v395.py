"""Léxico externo opcional del diccionario (V3.95.0).

Fija las dos propiedades que importan: la tabla sirve AMBAS direcciones sin
modelo, y su autoridad es INFERIOR a la curada (glosario/packs/corrección). Y el
importador no empaqueta datos: exige aceptación explícita de licencia.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from scripts import import_freedict
from services import dictionary_content


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _lookup(uid: str, word: str, direction: str = "en-es") -> dict:
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": word, "direction": direction},
        )
        assert res.status_code == 200, res.text
        return res.json()


def test_lexicon_serves_both_directions_without_model(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    dictionary_repo.add_lexicon_entries(
        [{"headword": "widget", "translation": "artilugio", "pos": "noun"}],
        source="test-lexicon",
        license="CC0",
    )

    forward = _lookup(uid, "widget", "en-es")
    assert forward["translation"] == "artilugio"

    reverse = _lookup(uid, "artilugio", "es-en")
    assert reverse["translation"] == "widget"


def test_lexicon_authority_is_below_the_curated_glossary(monkeypatch, tmp_path):
    """El glosario «broca»→«drill bit» gana al léxico externo «drill»."""
    uid = _setup(monkeypatch, tmp_path)
    # El equivalente elegido por el glosario necesita su contenido directo ya
    # cacheado para no llamar al modelo en el test.
    dictionary_repo.save_entry(
        "drill bit",
        definition="A cutting tool.",
        translation="broca",
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    dictionary_repo.add_lexicon_entries(
        [{"headword": "drill", "translation": "broca"}],
        source="test-lexicon",
        license="CC0",
    )
    data = _lookup(uid, "broca", "es-en")
    assert data["translation"] == "drill bit"


def test_add_lexicon_entries_is_replaceable_and_attributable(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    dictionary_repo.add_lexicon_entries(
        [{"headword": "cat", "translation": "gato"}],
        source="src",
        license="CC BY-SA 3.0",
    )
    dictionary_repo.add_lexicon_entries(
        [{"headword": "dog", "translation": "perro"}],
        source="src",
        license="CC BY-SA 3.0",
        replace_source=True,
    )
    sources = dictionary_repo.lexicon_sources()
    assert sources == [
        {"source": "src", "license": "CC BY-SA 3.0", "entries": 1}
    ]
    assert dictionary_repo.lookup_lexicon_en_es("cat") == []


def test_import_parser_cleans_and_skips_the_header():
    rows, skipped = import_freedict._parse_rows(
        "headword\ttranslation\nCrowbar\tpalanca\n\t\nbank\t",
        "\t",
    )
    assert rows == [{"headword": "crowbar", "translation": "palanca", "pos": ""}]
    assert skipped == 1


def test_import_requires_an_explicit_license_decision(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    source = tmp_path / "lex.tsv"
    source.write_text("crowbar\tpalanca\n", encoding="utf-8")

    # Sin --accept-license: se niega (no escribe nada).
    code = import_freedict.main(
        ["--file", str(source), "--source", "s", "--license", "CC BY-SA 3.0"]
    )
    assert code == 2
    assert dictionary_repo.lexicon_sources() == []

    # Dry-run: no exige la aceptación y tampoco escribe.
    code = import_freedict.main(
        ["--file", str(source), "--source", "s", "--license", "L", "--dry-run"]
    )
    assert code == 0
    assert dictionary_repo.lexicon_sources() == []

    # Con la aceptación: importa de verdad.
    code = import_freedict.main(
        [
            "--file",
            str(source),
            "--source",
            "s",
            "--license",
            "CC BY-SA 3.0",
            "--accept-license",
        ]
    )
    assert code == 0
    assert dictionary_repo.lexicon_sources() == [
        {"source": "s", "license": "CC BY-SA 3.0", "entries": 1}
    ]
