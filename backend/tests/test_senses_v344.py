"""V3.44 (P1-01) — modelo de sentidos (`lexical_unit → sense`) como CONTENIDO.

La auditoría de V3.43.0 señaló que el proxy semántico usaba la `pos` GLOBAL de
la entrada como sustituto de sentido, de modo que palabras legítimamente
noun/verb podían marcar `semantic_mismatch` en usos correctos. V3.44 dota a la
unidad de SENTIDOS (`[{pos, gloss}]`), generados por el modelo local dentro del
contrato de contenido del diccionario (premisa 21: el LLM genera contenido,
nunca decide evidencia) y cacheados.

Esta suite cubre el contrato de contenido (`normalize_senses`, prompts y bump de
`GENERATOR_VERSION`), la persistencia aditiva (`senses_json` en ambas tablas) y
la migración idempotente, incluida una BD legacy.
"""

from __future__ import annotations

import json
import sqlite3

from repositories import db
from repositories import dictionary as dictionary_repo
from services import dictionary_content


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def _payload(**extra: object) -> str:
    body: dict = {
        "pos": "noun",
        "definition": "A small domesticated carnivorous mammal.",
        "translation": "gato",
        "situation": "The _____ purred softly.",
    }
    body.update(extra)
    return json.dumps(body)


# --- Contrato de contenido: normalize_senses (puro) --------------------------


def test_normalize_senses_keeps_only_canonical_pos_and_orders_by_input():
    assert dictionary_content.normalize_senses(
        [
            {"pos": "Verb", "gloss": "  to decide  "},
            {"pos": "noun", "gloss": "an arrangement"},
        ]
    ) == [
        {"pos": "verb", "gloss": "to decide"},
        {"pos": "noun", "gloss": "an arrangement"},
    ]


def test_normalize_senses_drops_invalid_entries_without_raising():
    assert dictionary_content.normalize_senses(None) == []
    assert dictionary_content.normalize_senses("noun") == []
    assert dictionary_content.normalize_senses([1, "x", {"pos": ""}]) == []
    # Categoría fuera de la taxonomía canónica: se descarta (no se inventa).
    assert dictionary_content.normalize_senses([{"pos": "adverbio"}]) == []


def test_normalize_senses_deduplicates_and_caps():
    duplicated = [
        {"pos": "noun", "gloss": "a place"},
        {"pos": "noun", "gloss": "a place"},
        {"pos": "noun", "gloss": "another sense"},
    ]
    assert dictionary_content.normalize_senses(duplicated) == [
        {"pos": "noun", "gloss": "a place"},
        {"pos": "noun", "gloss": "another sense"},
    ]
    many = [
        {"pos": "noun", "gloss": f"sense {index}"}
        for index in range(dictionary_content.MAX_SENSES + 3)
    ]
    assert len(dictionary_content.normalize_senses(many)) == (
        dictionary_content.MAX_SENSES
    )


def test_normalize_senses_truncates_the_gloss():
    long_gloss = "a" * (dictionary_content.MAX_GLOSS_CHARS + 40)
    out = dictionary_content.normalize_senses([{"pos": "noun", "gloss": long_gloss}])
    assert len(out[0]["gloss"]) == dictionary_content.MAX_GLOSS_CHARS


# --- parse_content / parse_reverse_content -----------------------------------


def test_parse_content_extracts_senses_and_derives_top_pos():
    out = dictionary_content.parse_content(
        _payload(
            pos="adverbio",  # inválido: manda el primer sentido
            senses=[
                {"pos": "verb", "gloss": "to decide"},
                {"pos": "noun", "gloss": "an arrangement"},
            ],
        ),
        word="plan",
    )
    assert out["senses"] == [
        {"pos": "verb", "gloss": "to decide"},
        {"pos": "noun", "gloss": "an arrangement"},
    ]
    assert out["pos"] == "verb"


def test_parse_content_without_senses_keeps_the_model_pos():
    out = dictionary_content.parse_content(_payload(pos="Verb"))
    assert out["senses"] == []
    assert out["pos"] == "verb"


def test_parse_content_ignores_invalid_senses_without_invalidating_content():
    out = dictionary_content.parse_content(
        _payload(senses=[{"pos": "adverbio", "gloss": "x"}, {"gloss": "no pos"}])
    )
    assert out["senses"] == []
    assert out["definition"]


def test_parse_reverse_content_extracts_senses_and_derives_top_pos():
    out = dictionary_content.parse_reverse_content(
        json.dumps(
            {
                "english": "plan",
                "pos": "adverbio",
                "definition": "A plan is an arrangement.",
                "senses": [{"pos": "noun", "gloss": "an arrangement"}],
            }
        )
    )
    assert out["english"] == "plan"
    assert out["senses"] == [{"pos": "noun", "gloss": "an arrangement"}]
    assert out["pos"] == "noun"


def test_prompts_declare_senses_and_version_is_bumped():
    assert dictionary_content.GENERATOR_VERSION == "1.4.0"
    assert "senses" in dictionary_content._SYSTEM_PROMPT
    assert "senses" in dictionary_content._REVERSE_SYSTEM_PROMPT


# --- Persistencia y migración ------------------------------------------------


def test_repository_round_trips_the_senses(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    senses = [{"pos": "noun", "gloss": "a place"}, {"pos": "verb", "gloss": "to rely"}]
    assert dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="def",
        translation="banco",
        situation="The _____ closed.",
        senses=senses,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    stored = dictionary_repo.get_entry("bank")
    assert stored["senses"] == senses
    # El JSON persistido es la forma canónica compacta (round-trip exacto).
    assert stored["senses_json"] == json.dumps(
        senses, ensure_ascii=False, separators=(",", ":")
    )


def test_repository_round_trips_reverse_senses(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    senses = [{"pos": "verb", "gloss": "to decide"}]
    assert dictionary_repo.save_reverse_entry(
        "planear",
        english="plan",
        pos="verb",
        definition="def",
        senses=senses,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    stored = dictionary_repo.get_reverse_entry("planear")
    assert stored["senses"] == senses


def test_repository_tolerates_corrupt_senses_json(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    dictionary_repo.save_entry("cat", pos="noun", definition="def")
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "UPDATE dictionary_entries SET senses_json = 'no-json' WHERE word = 'cat'"
        )
    stored = dictionary_repo.get_entry("cat")
    # Un JSON ilegible no rompe la consulta: degrada a [] (scoring `unknown`).
    assert stored["senses"] == []


def test_migration_adds_senses_json_to_both_tables_idempotently(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # segunda ejecución: no debe fallar ni duplicar la columna
    with sqlite3.connect(db.DB_PATH) as conn:
        direct = {
            row[1] for row in conn.execute("PRAGMA table_info(dictionary_entries)")
        }
        reverse = {
            row[1]
            for row in conn.execute("PRAGMA table_info(dictionary_reverse_entries)")
        }
    assert "senses_json" in direct
    assert "senses_json" in reverse


def test_migration_adds_senses_json_on_a_legacy_database(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "CREATE TABLE dictionary_entries ("
        "word TEXT PRIMARY KEY, pos TEXT NOT NULL DEFAULT '', "
        "definition TEXT NOT NULL DEFAULT '', "
        "translation TEXT NOT NULL DEFAULT '', "
        "situation TEXT NOT NULL DEFAULT '', "
        "generator_version TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT '')"
    )
    conn.execute(
        "CREATE TABLE dictionary_reverse_entries ("
        "word TEXT PRIMARY KEY, english TEXT NOT NULL DEFAULT '', "
        "pos TEXT NOT NULL DEFAULT '', definition TEXT NOT NULL DEFAULT '', "
        "situation TEXT NOT NULL DEFAULT '', "
        "generator_version TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT '')"
    )
    conn.execute(
        "INSERT INTO dictionary_entries VALUES "
        "('cat','noun','def','gato','','1.3.0',"
        "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO dictionary_reverse_entries VALUES "
        "('gato','cat','noun','def','','1.3.0',"
        "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    db.init_db()

    assert dictionary_repo.get_entry("cat")["senses"] == []
    reverse = dictionary_repo.get_reverse_entry("gato")
    assert reverse["senses"] == []
    # El contenido legacy se conserva intacto.
    assert reverse["english"] == "cat"
