"""Ampliar un pack ya sembrado añade palabras y no reescribe las existentes."""
from __future__ import annotations

import json
import sqlite3

from repositories import collections as collections_repo
from repositories import db


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    pack_dir = tmp_path / "packs"
    pack_dir.mkdir()
    monkeypatch.setattr(collections_repo, "PACKS_DIR", pack_dir)
    db.init_db()
    return pack_dir


def _write(pack_dir, items):
    payload = {
        "slug": "travel",
        "kind": "theme_pack",
        "title": "Travel",
        "title_es": "Viajes",
        "cefr_hint": "A2",
        "items": items,
    }
    (pack_dir / "travel.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _items():
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT word, translation FROM vocab_collection_items ORDER BY word"
            )
        ]
    finally:
        conn.close()


def test_existing_pack_gains_words_without_rewriting(monkeypatch, tmp_path):
    pack_dir = _setup(monkeypatch, tmp_path)
    _write(
        pack_dir,
        [
            {
                "word": "airport",
                "lemma": "airport",
                "translation": "aeropuerto",
                "pos": "noun",
            }
        ],
    )
    assert collections_repo.ensure_theme_packs_seeded() == 1

    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            "UPDATE vocab_collection_items SET translation = ? WHERE word = ?",
            ("pista", "airport"),
        )
        conn.commit()
    finally:
        conn.close()

    _write(
        pack_dir,
        [
            {
                "word": "airport",
                "lemma": "airport",
                "translation": "terminal",
                "pos": "noun",
            },
            {
                "word": "hotel",
                "lemma": "hotel",
                "translation": "hotel",
                "pos": "noun",
            },
        ],
    )
    assert collections_repo.ensure_theme_packs_seeded() == 0
    rows = {row["word"]: row["translation"] for row in _items()}
    assert rows["airport"] == "pista"
    assert rows["hotel"] == "hotel"
