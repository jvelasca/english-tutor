"""Tests de aislamiento cross-user entre perfiles (repositorios y prompt).

Verifica que los datos pedagógicos de un usuario nunca se vean desde otro
(conversaciones, vocabulario, gramática, pronunciación, listening, eventos y
perfil) y que el prompt personalizado del tutor no contenga errores de otro
usuario.
"""
import asyncio

from domain import profile as profile_service
from repositories import conversations as conversations_repo
from repositories import db
from repositories import grammar as grammar_repo
from repositories import learning as learning_repo
from repositories import listening as listening_repo
from repositories import profile as profile_repo
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.context import build_system_prompt
from services.grammar import find_errors


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def test_cross_user_conversation_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    cid = conversations_repo.create_conversation(a)["id"]
    assert conversations_repo.get_conversation(cid, b) is None
    assert conversations_repo.get_conversation(cid, a) is not None
    assert conversations_repo.list_conversations(b) == []


def test_cross_user_vocabulary_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat"])
    assert vocabulary_repo.get_vocabulary(b) == []


def test_cross_user_grammar_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(a, find_errors("He go to school"))
    assert grammar_repo.get_recurring_errors(b) == []


def test_cross_user_pronunciation_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    pronunciation_repo.record_pronunciation(a, "Hello", "Hello", 90, "good")
    assert pronunciation_repo.get_progress(b)["pronunciation"]["attempts"] == 0
    assert pronunciation_repo.get_progress(a)["pronunciation"]["attempts"] == 1


def test_cross_user_listening_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    listening_repo.record_attempt(a, "q1", 0, True)
    assert listening_repo.get_stats(b)["attempts"] == 0
    assert listening_repo.get_stats(a)["attempts"] == 1


def test_cross_user_learning_event_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    learning_repo.record_event(a, "message", "hello")
    assert learning_repo.list_events(b) == []


def test_cross_user_profile_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    profile_repo.set_cefr(a, "B1")
    assert profile_repo.get_profile(b) is None
    assert profile_repo.get_profile(a)["cefr_level"] == "B1"


def test_cross_user_prompt_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(a, find_errors("He go to school"))
    grammar_repo.record_errors(b, find_errors("i like it"))

    profile_a = asyncio.run(profile_service.get_profile_context(a))
    profile_b = asyncio.run(profile_service.get_profile_context(b))
    prompt_a = build_system_prompt("conversation", profile_a)
    prompt_b = build_system_prompt("conversation", profile_b)

    assert prompt_a != prompt_b
    assert "Falta la -s" in prompt_a
    assert "Falta la -s" not in prompt_b
    assert "pronombre 'I'" in prompt_b
    assert "pronombre 'I'" not in prompt_a
