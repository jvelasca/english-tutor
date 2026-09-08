"""Tests de V3.21 (V20-01): producción de unidades léxicas por ALINEACIÓN
SECUENCIAL (no por pertenencia de tokens) en el speaking micro-drill.

Cubre `services.phonetics.unit_produced` (puro) y el flujo de extremo a extremo
del intento con frases multi-palabra (acreditación atómica de la unidad).
"""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.phonetics import unit_produced


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _fake_transcribe(text):
    def fake(_audio, _lang):
        return {"text": text, "duration": 2.0}

    return fake


# ---------------------------------------------------------------- puro

def test_unit_produced_single_word_exact():
    assert unit_produced("travel", "travel") is True


def test_unit_produced_single_word_within_sentence():
    assert unit_produced("travel", "I travel every day") is True


def test_unit_produced_single_word_absent():
    assert unit_produced("travel", "banana") is False


def test_unit_produced_single_word_empty_heard():
    assert unit_produced("travel", "") is False


def test_unit_produced_phrase_exact():
    assert unit_produced("living room", "living room") is True


def test_unit_produced_phrase_reversed_is_false():
    # El ejemplo de la auditoría: pertenencia diría True; la secuencia no.
    assert unit_produced("living room", "room living") is False
    assert unit_produced("go to the store", "the store go to") is False


def test_unit_produced_phrase_interleaved_extra_is_false():
    # "get it up" no es "get up": extra dentro de la frase.
    assert unit_produced("get up", "get it up") is False


def test_unit_produced_phrase_within_longer_sentence_is_true():
    # La unidad dentro de una oración más larga sí es producción.
    assert unit_produced("living room", "my living room is nice") is True
    assert unit_produced("turn on the light", "I turn on the light at night") is True


def test_unit_produced_phrase_partial_is_false():
    assert unit_produced("wake up", "wake") is False
    assert unit_produced("wake up", "week up") is False
    assert unit_produced("turn on the light", "turn on light") is False


def test_unit_produced_normalizes_case_and_punctuation():
    assert unit_produced("Check-in", "check in") is True
    assert unit_produced("TRAVEL", "travel") is True


def test_unit_produced_duplicate_tokens():
    # Duplicado fuera de la frase: sigue conteniendo "good morning" contiguo.
    assert unit_produced("good morning", "good good morning") is True


def test_unit_produced_empty_expected_false():
    assert unit_produced("", "anything") is False


# ---------------------------------------------------------------- endpoint

def test_drill_phrase_produced_accredits_atomic_unit(monkeypatch, tmp_path):
    """Una frase multi-palabra del drill acredita SU PROPIA fila (V3.21).

    Antes de V3.21, `record_production_text` tokenizaba la frase y solo sumaba
    `speaking_prod` a las filas de los tokens sueltos, con lo que "living room"
    jamás salía de candidatas. Ahora se registra la unidad atómica."""
    a = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": "living room",
                "lemma": "living room",
                "cefr": "A1",
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "collocation",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, ["living room"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("my living room is nice")
    )
    with TestClient(app) as client:
        ok = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "living room"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ok.status_code == 200
        assert ok.json()["produced"] is True

        # La frase ya no es candidata.
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == []

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["living room"]["speaking_prod"] == 1
    assert vocab["living room"]["production_count"] == 1
    # Invariante de trazabilidad por fila.
    assert vocab["living room"]["chat_prod"] == 0
    assert (
        vocab["living room"]["chat_prod"]
        + vocab["living room"]["speaking_prod"]
        + vocab["living room"]["writing_prod"]
        + vocab["living room"]["conversation_prod"]
    ) == vocab["living room"]["production_count"]


def test_drill_phrase_reversed_not_produced(monkeypatch, tmp_path):
    """Orden invertido de una frase NO produce: no se acredita (V20-01)."""
    a = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": "get up",
                "lemma": "get up",
                "cefr": "A1",
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "phrasal_verb",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, ["get up"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("up get")
    )
    with TestClient(app) as client:
        ko = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "get up"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ko.status_code == 200
        assert ko.json()["produced"] is False

        # Sigue siendo candidata (la producción NO se acredita en falso).
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == ["get up"]

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["get up"]["speaking_prod"] == 0
    assert vocab["get up"]["production_count"] == 0


def test_drill_phrase_interleaved_extra_not_produced(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": "get up",
                "lemma": "get up",
                "cefr": "A1",
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "phrasal_verb",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, ["get up"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("get it up")
    )
    with TestClient(app) as client:
        ko = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "get up"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ko.status_code == 200
        assert ko.json()["produced"] is False

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["get up"]["speaking_prod"] == 0
