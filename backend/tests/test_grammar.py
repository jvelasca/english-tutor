"""Tests de errores gramaticales: reglas, persistencia, aislamiento y endpoints."""
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import grammar as grammar_repo
from repositories import users as users_repo
from services.grammar import find_errors


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def _rules(errors: list[dict]) -> set[str]:
    return {e["rule"] for e in errors}


def test_grammar_errors_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("grammar_errors")


def test_find_errors_third_person_s(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "he_she_it_s" in _rules(find_errors("He go to school"))
    assert "he_she_it_s" not in _rules(find_errors("He goes to school"))


def test_find_errors_a_an(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "a_an" in _rules(find_errors("I ate a apple"))
    assert "a_an" not in _rules(find_errors("I ate an apple"))


def test_find_errors_double_negative(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "double_negative" in _rules(find_errors("I don't have no money"))


def test_find_errors_there_their(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "there_their_theyre" in _rules(find_errors("their going home"))


def test_find_errors_your_youre(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "your_youre" in _rules(find_errors("your nice"))


def test_find_errors_capitalization_i(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "capitalization_i" in _rules(find_errors("i like it"))
    assert "capitalization_i" not in _rules(find_errors("I like it"))


def test_record_errors_increments_count(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    errors = find_errors("He go to school")
    assert grammar_repo.record_errors(a, errors) is True
    assert grammar_repo.record_errors(a, errors) is True
    recurring = grammar_repo.get_recurring_errors(a)
    assert recurring[0]["rule"] == "he_she_it_s"
    assert recurring[0]["count"] == 2


def test_record_errors_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert grammar_repo.record_errors("no-existe", find_errors("He go")) is False


def test_grammar_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(a, find_errors("He go to school"))
    assert grammar_repo.get_recurring_errors(b) == []


def test_get_recurring_errors_ordered(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(a, find_errors("He go to school"))
    grammar_repo.record_errors(a, find_errors("I ate a apple"))
    grammar_repo.record_errors(a, find_errors("He go again"))
    recurring = grammar_repo.get_recurring_errors(a)
    assert recurring[0]["rule"] == "he_she_it_s"
    assert recurring[0]["count"] == 2
    assert recurring[1]["rule"] == "a_an"
    assert recurring[1]["count"] == 1


def test_grammar_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/grammar/analyze",
            params={"user_id": a},
            json={"text": "He go to school"},
        )
        assert r.status_code == 200
        assert r.json()["errors"][0]["rule"] == "he_she_it_s"

        got = client.get("/api/grammar/errors", params={"user_id": a})
        assert got.status_code == 200
        assert got.json()[0]["rule"] == "he_she_it_s"
        assert got.json()[0]["count"] == 1


def test_grammar_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get(
                "/api/grammar/errors", params={"user_id": "no-existe"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/grammar/analyze",
                params={"user_id": "no-existe"},
                json={"text": "hello"},
            ).status_code
            == 404
        )
