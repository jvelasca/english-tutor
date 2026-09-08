"""Tests de V3.21 (F6): drill en escalera.

Cubre F6.1 (paso "Sentence" determinista sin LLM) y F6.2 (graduación espaciada:
una producción del día no elimina a la palabra de la lista "pendiente"; solo la
consolidan 2 días de éxito de drill u otra señal de speaking espaciada).

Se mantiene "señal ≠ evidencia": nada de esto declara dominio ni crea evidencia
curricular o FSRS (D5/E3).
"""
from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.lexicon import drill_candidates, drill_ok_days
from services.pronunciation_routes import sentence_context_for


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _fake_transcribe(text):
    def fake(_audio, _lang):
        return {"text": text, "duration": 2.0}

    return fake


def _insert_event(uid: str, detail: str, created_at: str) -> None:
    """Inserta un evento de aprendizaje con fecha controlada (para simular el
    espaciado de días en F6.2 sin depender del reloj)."""
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_events (user_id, type, detail, created_at) "
            "VALUES (?, 'exercise', ?, ?)",
            (uid, detail, created_at),
        )


def _seed_word(a: str, word: str, cefr: str = "A1") -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


# ------------------------------------------------------------------ F6.1 puro

def test_sentence_context_uses_route_phrase_when_contains_unit():
    pool = [
        {"id": "x1", "level": "A1", "script": "Good morning."},
        {"id": "x2", "level": "A1", "script": "My living room is nice."},
    ]
    got = sentence_context_for("living room", "A1", phrase_pool=pool)
    assert got["source"] == "route"
    assert got["phrase"] == "My living room is nice."


def test_sentence_context_template_when_no_phrase_contains_unit():
    pool = [
        {"id": "x1", "level": "A1", "script": "Good morning."},
        {"id": "x2", "level": "A1", "script": "Hello, nice to meet you."},
    ]
    got = sentence_context_for("travel", "A1", phrase_pool=pool)
    assert got["source"] == "template"
    assert got["phrase"] == 'Say the word "travel".'


def test_sentence_context_deterministic_first_route_match():
    pool = [
        {"id": "x1", "level": "A1", "script": "I like living room music."},
        {"id": "x2", "level": "A1", "script": "My living room is nice."},
    ]
    got = sentence_context_for("living room", "A1", phrase_pool=pool)
    assert got["phrase"] == "I like living room music."


def test_sentence_context_multiword_kept_atomic_in_template():
    got = sentence_context_for("get up", "A2", phrase_pool=[])
    assert got["source"] == "template"
    assert got["phrase"] == 'Say the word "get up".'


# ------------------------------------------------------------------ F6.2 puro

def test_drill_ok_days_parses_word_and_sentence_events():
    events = [
        {
            "detail": "drill:travel:ok",
            "created_at": "2026-09-01T10:00:00+00:00",
        },
        {
            "detail": "drill:living room:sentence:ok",
            "created_at": "2026-09-02T09:00:00+00:00",
        },
        {
            "detail": "drill:get up:sentence:ko",
            "created_at": "2026-09-02T11:00:00+00:00",
        },
        {
            "detail": "drill:travel:ko",
            "created_at": "2026-09-02T12:00:00+00:00",
        },
        {
            "detail": "message:hola",
            "created_at": "2026-09-02T13:00:00+00:00",
        },
        {
            "detail": "drill:word:with:colon:ok",
            "created_at": "2026-09-03T08:00:00+00:00",
        },
    ]
    assert drill_ok_days(events) == {
        "travel": {"2026-09-01"},
        "living room": {"2026-09-02"},
        "word:with:colon": {"2026-09-03"},
    }


def test_drill_candidates_hides_word_produced_today_until_spaced():
    rows = [
        {
            "word": "travel",
            "exposures": 3,
            "speaking_prod": 1,
            "appearances": 1,
            "production_days": 1,
        }
    ]
    ok_days = {"travel": {"2026-09-07"}}
    # La produjo hoy pero aún no consolida (1 día): se oculta hoy.
    assert drill_candidates(rows, ok_days=ok_days, today="2026-09-07") == []
    # Mañana vuelve a estar pendiente (sigue sin éxito espaciado).
    assert drill_candidates(rows, ok_days=ok_days, today="2026-09-08") == ["travel"]


def test_drill_candidates_exits_after_two_spaced_ok_days():
    rows = [
        {
            "word": "travel",
            "exposures": 3,
            "speaking_prod": 2,
            "appearances": 2,
            "production_days": 2,
        }
    ]
    ok_days = {"travel": {"2026-09-06", "2026-09-07"}}
    assert drill_candidates(rows, ok_days=ok_days, today="2026-09-07") == []


def test_drill_candidates_leaves_never_spoken_words_candidate():
    rows = [{"word": "culture", "exposures": 2, "speaking_prod": 0}]
    assert drill_candidates(rows, ok_days={}, today="2026-09-07") == ["culture"]


# ------------------------------------------------------- endpoints F6.1

def test_sentence_context_endpoint_returns_template(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    _seed_word(a, "travel")
    with TestClient(app) as client:
        got = client.get(
            "/api/vocabulary/drill/sentence-context",
            params={"user_id": a, "word": "travel"},
        )
    assert got.status_code == 200
    body = got.json()
    assert body["word"] == "travel"
    assert body["source"] == "template"
    assert body["phrase"] == 'Say the word "travel".'


def test_sentence_attempt_passed_accredits_word_within_phrase(
    monkeypatch, tmp_path
):
    """Decir la frase completa con la palabra alineada acredita la unidad."""
    a = _setup(monkeypatch, tmp_path)
    _seed_word(a, "travel")

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod,
        "transcribe_with_timing",
        _fake_transcribe('say the word "travel"'),
    )
    with TestClient(app) as client:
        ok = client.post(
            "/api/vocabulary/drill/sentence-attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["passed"] is True
        assert body["produced"] is True
        assert body["phrase_ok"] is True
        assert body["source"] == "template"

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 1
    assert vocab["travel"]["production_count"] == 1
    # Invariante de trazabilidad por fila.
    assert (
        vocab["travel"]["chat_prod"]
        + vocab["travel"]["speaking_prod"]
        + vocab["travel"]["writing_prod"]
        + vocab["travel"]["conversation_prod"]
    ) == vocab["travel"]["production_count"]

    # Se registró el evento de éxito del paso frase.
    events = learning_repo.list_events(a, "exercise")
    assert any(
        e["detail"] == "drill:travel:sentence:ok" for e in events
    )


def test_sentence_attempt_word_alone_does_not_pass_phrase(monkeypatch, tmp_path):
    """Decir solo la palabra (sin la frase) produce la palabra pero NO pasa el
    paso frase: la evidencia de este paso es la palabra dentro de la frase."""
    a = _setup(monkeypatch, tmp_path)
    _seed_word(a, "travel")

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("travel")
    )
    with TestClient(app) as client:
        ok = client.post(
            "/api/vocabulary/drill/sentence-attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["produced"] is True
        assert body["phrase_ok"] is False
        assert body["passed"] is False

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 0


# ------------------------------------------------------- endpoints F6.2

def test_one_drill_success_today_hides_word_until_tomorrow(monkeypatch, tmp_path):
    """Una producción del día NO consolida: la palabra deja de ofrecerse hoy
    (no se repite el mismo día) pero sigue pendiente en la lista."""
    a = _setup(monkeypatch, tmp_path)
    _seed_word(a, "travel")

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("travel")
    )
    with TestClient(app) as client:
        ok = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ok.status_code == 200
        assert ok.json()["produced"] is True
        # Hoy ya no se ofrece (éxito del día, sin consolidar).
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == []

    # Aunque esté oculta hoy, la fila registra la producción.
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 1


def test_two_spaced_drill_successes_exit_candidates(monkeypatch, tmp_path):
    """2 éxitos de drill en >= 2 días sacan la palabra de la lista pendiente."""
    a = _setup(monkeypatch, tmp_path)
    _seed_word(a, "travel")

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("travel")
    )
    with TestClient(app) as client:
        ok = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ok.json()["produced"] is True

        # Éxito de ayer (simulado): la palabra consolida (2 días espaciados) y
        # ya no vuelve a aparecer mañana ni nunca como pendiente.
        _insert_event(a, "drill:travel:ok", "2026-09-06T09:00:00+00:00")
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == []
