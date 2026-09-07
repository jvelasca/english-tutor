"""Tests de V3.21 (V20-14/V20-15): taxonomía ASR y no-penalización.

Cubre `services.stt.classify_asr_status` (puro) y el gating en los intentos
puntuados: cuando el audio no se reconoce con fiabilidad (silencio, audio
ininteligible o confianza baja) NO se penaliza al alumno (ni drill, ni
read-aloud, ni speaking abierto).
"""
from fastapi.testclient import TestClient

from config import MAX_AUDIO_DURATION_SECONDS
from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.stt import (
    ASR_LOW_CONFIDENCE,
    ASR_NO_SPEECH,
    ASR_OK,
    ASR_UNINTELLIGIBLE,
    classify_asr_status,
    exceeds_max_duration,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _fake_transcribe(text, asr_status="ok", confidence=None):
    def fake(_audio, _lang):
        return {
            "text": text,
            "duration": 2.0,
            "asr_status": asr_status,
            "confidence": confidence,
        }

    return fake


# ---------------------------------------------------------------- puro

def test_classify_no_speech_when_empty_and_high_nospeech():
    assert (
        classify_asr_status(text="", avg_logprob=None, no_speech_prob=0.9)
        == ASR_NO_SPEECH
    )


def test_classify_unintelligible_when_empty_without_nospeech_mark():
    assert (
        classify_asr_status(text="", avg_logprob=None, no_speech_prob=0.2)
        == ASR_UNINTELLIGIBLE
    )
    assert (
        classify_asr_status(text="", avg_logprob=None, no_speech_prob=None)
        == ASR_UNINTELLIGIBLE
    )


def test_classify_low_confidence_when_text_but_bad_logprob():
    assert (
        classify_asr_status(text="hello", avg_logprob=-2.4, no_speech_prob=0.1)
        == ASR_LOW_CONFIDENCE
    )


def test_classify_ok_with_clean_text():
    assert (
        classify_asr_status(text="hello", avg_logprob=-0.3, no_speech_prob=0.05)
        == ASR_OK
    )


def test_classify_ok_when_text_present_despite_nospeech_mark():
    # Con texto no vacío no se descarta como no-speech (evita falsos "silencio"
    # sobre alucinaciones con texto).
    assert (
        classify_asr_status(text="hello", avg_logprob=-0.4, no_speech_prob=0.9)
        == ASR_OK
    )


def test_classify_ignores_whitespace():
    assert (
        classify_asr_status(text="   ", avg_logprob=None, no_speech_prob=0.9)
        == ASR_NO_SPEECH
    )


# ---------------------------------------------------------------- gating

def test_drill_attempt_asr_not_ok_never_produces(monkeypatch, tmp_path):
    """Con ASR no fiable, aunque la transcripción contenga la palabra, NO se
    acredita producción ni se saca de candidatas (V20-14/15)."""
    a = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])

    from routers import vocabulary as router_mod

    # Texto perfecto pero ASR con confianza baja: señal NO fiable.
    monkeypatch.setattr(
        router_mod,
        "transcribe_with_timing",
        _fake_transcribe("travel", asr_status=ASR_LOW_CONFIDENCE, confidence=0.12),
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["produced"] is False
        assert body["asr_status"] == ASR_LOW_CONFIDENCE
        assert body["asr_confidence"] == 0.12

        # Sigue siendo candidata.
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == ["travel"]

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 0
    assert vocab["travel"]["appearances"] == 0
    # El evento registrado es "unclear", no "ko".
    events = learning_repo.list_events(a, event_type="exercise")
    assert any(e["detail"] == "drill:travel:unclear" for e in events)
    assert not any(e["detail"] == "drill:travel:ko" for e in events)


def test_drill_attempt_asr_ok_still_records_ko(monkeypatch, tmp_path):
    """Con ASR fiable y palabra ausente, el KO sí se registra (fallo del alumno)."""
    a = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("banana")
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 200
        assert resp.json()["produced"] is False
        assert resp.json()["asr_status"] == ASR_OK

    events = learning_repo.list_events(a, event_type="exercise")
    assert any(e["detail"] == "drill:travel:ko" for e in events)


def test_readaloud_asr_not_ok_not_recorded_as_failure(monkeypatch, tmp_path):
    """Read-aloud con audio no reconocido: no se persiste un intento fallido."""
    a = _setup(monkeypatch, tmp_path)

    from routers import pronunciation_routes as router_mod
    from services.pronunciation_routes import phrases_for_level

    phrase = phrases_for_level("A1")[0]

    monkeypatch.setattr(
        router_mod,
        "transcribe_with_timing",
        _fake_transcribe("", asr_status=ASR_NO_SPEECH, confidence=0.0),
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/pronunciation/routes/attempt",
            params={"user_id": a},
            data={"phrase_id": phrase["id"]},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is False
        assert body["asr_status"] == ASR_NO_SPEECH
        # No se cuenta como intento en las stats.
        stats = client.get(
            "/api/pronunciation/routes/stats", params={"user_id": a}
        )
        assert stats.json()["attempts"] == 0


# ---------------------------------------------------------------- V20-13 duración

def test_exceeds_max_duration_pure():
    """Red de seguridad de duración: pura y con el límite como cota estricta."""
    assert not exceeds_max_duration(None)
    assert not exceeds_max_duration(0.0)
    assert not exceeds_max_duration(MAX_AUDIO_DURATION_SECONDS)
    assert not exceeds_max_duration(MAX_AUDIO_DURATION_SECONDS - 1)
    assert exceeds_max_duration(MAX_AUDIO_DURATION_SECONDS + 0.1)
    assert exceeds_max_duration(999.0)


def _fake_long_audio():
    def fake(_audio, _lang):
        return {
            "text": "travel",
            "duration": MAX_AUDIO_DURATION_SECONDS + 30,
            "asr_status": ASR_OK,
            "confidence": 0.95,
        }

    return fake


def test_drill_attempt_long_audio_rejected_400(monkeypatch, tmp_path):
    """Audio más largo que el máximo: 400 claro (V20-13), sin tocar el léxico."""
    a = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(router_mod, "transcribe_with_timing", _fake_long_audio())
    with TestClient(app) as client:
        resp = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 400
        assert "supera el máximo" in resp.json()["detail"]

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 0
    assert vocab["travel"]["appearances"] == 0
    # No se registra ningún resultado de intento (ni siquiera "unclear").
    events = learning_repo.list_events(a, event_type="exercise")
    assert not any(e["detail"].startswith("drill:travel:") for e in events)


def test_readaloud_long_audio_rejected_400(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)

    from routers import pronunciation_routes as router_mod
    from services.pronunciation_routes import phrases_for_level

    phrase = phrases_for_level("A1")[0]
    monkeypatch.setattr(router_mod, "transcribe_with_timing", _fake_long_audio())
    with TestClient(app) as client:
        resp = client.post(
            "/api/pronunciation/routes/attempt",
            params={"user_id": a},
            data={"phrase_id": phrase["id"]},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 400
        assert "supera el máximo" in resp.json()["detail"]


def test_speaking_attempt_long_audio_rejected_400(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)

    from routers import speaking_routes as router_mod

    monkeypatch.setattr(router_mod, "transcribe_with_timing", _fake_long_audio())
    with TestClient(app) as client:
        resp = client.post(
            "/api/speaking/attempt",
            params={"user_id": a},
            data={"phrase_id": "missing"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        # El guard de duración se evalúa antes de buscar la tarjeta.
        assert resp.status_code == 400
        assert "supera el máximo" in resp.json()["detail"]
