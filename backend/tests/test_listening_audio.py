"""Tests del audio real de listening (V1.13): síntesis bajo demanda, cache y
degradación del endpoint."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import (
    QUESTION_BANK,
    audio_text,
    length_scale_for_rate,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Funciones puras ---------------------------------------------------------


def test_length_scale_for_rate_maps_faster_to_lower_scale():
    assert length_scale_for_rate(140.0) == 1.0
    assert length_scale_for_rate(175.0) == 0.8
    assert length_scale_for_rate(112.0) == 1.25


def test_length_scale_for_rate_defaults_and_clamps():
    assert length_scale_for_rate(0.0) == 1.0
    assert length_scale_for_rate(-5.0) == 1.0
    # Clamp: velocidades extremas no deforman la voz más allá del rango permitido.
    assert length_scale_for_rate(1000.0) == 0.6
    assert length_scale_for_rate(20.0) == 1.6


def test_audio_text_prefers_transcript_over_script():
    q = {"transcript": "I'm gonna call you.", "script": "I am going to call you."}
    assert audio_text(q) == "I'm gonna call you."


def test_audio_text_falls_back_to_script():
    q = {"transcript": "", "script": "Hello there."}
    assert audio_text(q) == "Hello there."


def test_audio_text_empty_when_nothing():
    assert audio_text({"transcript": "", "script": ""}) == ""


# --- Endpoint de audio -------------------------------------------------------


def test_audio_endpoint_404_unknown_question(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/audio/nope", params={"user_id": uid})
    assert r.status_code == 404


def test_audio_endpoint_503_when_tts_not_ready(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr("services.tts.is_ready", lambda: False)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.get(f"/api/listening/audio/{q['id']}", params={"user_id": uid})
    assert r.status_code == 503


def test_audio_endpoint_synthesizes_and_caches(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    monkeypatch.setattr("services.tts.is_ready", lambda: True)

    calls = []

    def fake_synthesize(text, length_scale=1.0):
        calls.append((text, length_scale))
        return b"RIFF-fake-wav-bytes"

    monkeypatch.setattr("services.tts.synthesize", fake_synthesize)

    with TestClient(app) as client:
        first = client.get(f"/api/listening/audio/{q['id']}", params={"user_id": uid})
        second = client.get(f"/api/listening/audio/{q['id']}", params={"user_id": uid})

    assert first.status_code == 200
    assert first.headers["content-type"] == "audio/wav"
    assert first.content == b"RIFF-fake-wav-bytes"
    # La segunda petición sirve del cache en disco: no vuelve a sintetizar.
    assert second.status_code == 200
    assert len(calls) == 1
    # Se sintetizó con la velocidad derivada del ítem y el texto de referencia.
    assert calls[0][0] == audio_text(q)
    assert calls[0][1] == length_scale_for_rate(q.get("speech_rate") or 0.0)
