"""V3.94.9: «¿Cuál es?» no usa las otras palabras del mazo."""
from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.study_quiz import rank_distractors


def test_rank_prefers_the_same_syllable_count_and_skips_the_lesson():
    chosen = rank_distractors(
        "martillo",
        ["casa", "camión", "cuchillo", "destornillador", "llave", "libro"],
        ["llave", "casa"],
    )
    assert "llave" not in chosen
    assert "casa" not in chosen
    assert chosen[0] in {"camión", "cuchillo"}
    assert "destornillador" not in chosen[:2]


def test_rank_fills_from_the_dictionary_when_few_are_close():
    chosen = rank_distractors("sol", ["destornillador", "electricidad"], [])
    assert chosen == ["destornillador", "electricidad"] or set(chosen) == {
        "destornillador",
        "electricidad",
    }


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_quiz_endpoint_uses_the_dictionary_and_not_the_lesson(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    with closing(db._conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO dictionary_entries (word, translation, created_at) VALUES (?, ?, ?)",
            [
                ("hammer", "martillo", "2020-01-01"),
                ("truck", "camión", "2020-01-01"),
                ("knife", "cuchillo", "2020-01-01"),
                ("house", "casa", "2020-01-01"),
                ("river", "río", "2020-01-01"),
                ("train", "tren", "2020-01-01"),
                ("book", "libro", "2020-01-01"),
            ],
        )
    client = TestClient(app)
    response = client.post(
        "/api/vocabulary/study/quiz",
        params={"user_id": user_id},
        json={
            "word": "hammer",
            "translation": "martillo",
            "exclude": ["casa", "río", "tren", "libro"],
        },
    )
    assert response.status_code == 200, response.text
    choices = response.json()["choices"]
    assert "martillo" in choices
    assert "casa" not in choices
    assert "cuchillo" in choices or "camión" in choices
    with closing(db._conn()) as conn:
        items = conn.execute("SELECT COUNT(*) FROM study_lesson_items").fetchone()[0]
    assert items == 0


def test_reverse_quiz_uses_english_lemmas_and_skips_the_lesson(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    with closing(db._conn()) as conn, conn:
        conn.executemany(
            "INSERT INTO dictionary_entries (word, translation, created_at) VALUES (?, ?, ?)",
            [
                ("hammer", "martillo", "2020-01-01"),
                ("truck", "camión", "2020-01-01"),
                ("knife", "cuchillo", "2020-01-01"),
                ("house", "casa", "2020-01-01"),
                ("river", "río", "2020-01-01"),
                ("train", "tren", "2020-01-01"),
                ("book", "libro", "2020-01-01"),
            ],
        )
    client = TestClient(app)
    response = client.post(
        "/api/vocabulary/study/quiz",
        params={"user_id": user_id},
        json={
            "word": "hammer",
            "translation": "martillo",
            "exclude": ["truck"],
            "direction": "es-en",
        },
    )
    assert response.status_code == 200, response.text
    choices = response.json()["choices"]
    assert "hammer" in choices
    assert "truck" not in choices
    assert "martillo" not in choices
    assert "casa" not in choices
    assert "knife" in choices or "river" in choices
