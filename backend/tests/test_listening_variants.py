"""Tests de la escalera de variantes de velocidad (P1.9): funciones puras, digest
y endpoint con cache por variante."""
import hashlib

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import (
    AUDIO_VARIANTS,
    DEFAULT_SPEECH_RATE,
    QUESTION_BANK,
    audio_digest,
    audio_text,
    audio_variants,
    length_scale_for_rate,
    spoken_text,
    variant_length_scale,
    variant_speech_rate,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


# --- Funciones puras ---------------------------------------------------------


def test_variant_speech_rate_normal_preserves_value():
    q = {"speech_rate": 150.0}
    assert variant_speech_rate(q, "normal") == 150.0
    assert variant_speech_rate(q) == 150.0
    # Sin speech_rate declarado, normal devuelve 0.0 (no inventa velocidad).
    assert variant_speech_rate({}, "normal") == 0.0


def test_variant_speech_rate_slow_fast_scale_wpm():
    q = {"speech_rate": 160.0}
    slow = variant_speech_rate(q, "slow")
    fast = variant_speech_rate(q, "fast")
    assert slow == round(160.0 * 0.75, 1) == 120.0
    assert fast == round(160.0 * 1.25, 1) == 200.0
    assert slow < 160.0 < fast


def test_variant_speech_rate_zero_uses_default_for_slow_fast():
    q = {"speech_rate": 0.0}
    assert variant_speech_rate(q, "normal") == 0.0
    assert variant_speech_rate(q, "slow") == round(DEFAULT_SPEECH_RATE * 0.75, 1)
    assert variant_speech_rate(q, "fast") == round(DEFAULT_SPEECH_RATE * 1.25, 1)


def test_variant_speech_rate_unknown_falls_back_to_normal():
    q = {"speech_rate": 150.0}
    assert variant_speech_rate(q, "bogus") == 150.0


def test_variant_length_scale_normal_matches_current():
    # Regresión de cache: la variante normal equivale a length_scale_for_rate.
    for rate in (0.0, 140.0, 185.0):
        q = {"speech_rate": rate}
        assert variant_length_scale(q, "normal") == length_scale_for_rate(rate)


def test_variant_length_scale_slow_fast_ordering():
    q = {"speech_rate": 140.0}
    slow = variant_length_scale(q, "slow")
    normal = variant_length_scale(q, "normal")
    fast = variant_length_scale(q, "fast")
    # Más lento ⇒ mayor length_scale; más rápido ⇒ menor.
    assert slow > normal > fast


def test_audio_digest_normal_preserves_cache():
    # Digest actual: texto + length_scale_for_rate(speech_rate) + repetición.
    q = {
        "id": "l18",
        "transcript": "Hello.",
        "speech_rate": 130.0,
        "repetition_policy": "twice",
    }
    payload = "|".join(
        [
            spoken_text(q),
            str(length_scale_for_rate(q.get("speech_rate") or 0.0)),
            q.get("repetition_policy", "none"),
        ]
    )
    expected = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    assert audio_digest(q, "normal") == expected


def test_audio_digest_variants_are_distinct():
    q = {
        "id": "l15",
        "transcript": "Could you help me?",
        "speech_rate": 140.0,
        "repetition_policy": "none",
    }
    digests = {audio_digest(q, v) for v in AUDIO_VARIANTS}
    assert len(digests) == 3


def test_audio_variants_returns_ordered_labels():
    q = {"speech_rate": 140.0}
    variants = audio_variants(q)
    assert [v["variant"] for v in variants] == ["slow", "normal", "fast"]
    assert [v["label"] for v in variants] == ["Slow", "Normal", "Fast"]
    by = {v["variant"]: v for v in variants}
    assert by["normal"]["speech_rate"] == 140.0
    assert by["slow"]["speech_rate"] == round(140.0 * 0.75, 1)
    assert by["fast"]["speech_rate"] == round(140.0 * 1.25, 1)


# --- Endpoint ----------------------------------------------------------------


def test_audio_endpoint_variant_invalid_400(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.get(
            f"/api/listening/audio/{q['id']}",
            params={"user_id": uid, "variant": "bogus"},
        )
    assert r.status_code == 400


def test_audio_endpoint_variant_fast_200(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    monkeypatch.setattr("services.tts.is_ready", lambda: True)

    calls = []

    def fake_synthesize(text, length_scale=1.0):
        calls.append((text, length_scale))
        return b"RIFF-fake-wav-bytes"

    monkeypatch.setattr("services.tts.synthesize", fake_synthesize)

    with TestClient(app) as client:
        r = client.get(
            f"/api/listening/audio/{q['id']}",
            params={"user_id": uid, "variant": "fast"},
        )

    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content == b"RIFF-fake-wav-bytes"
    assert len(calls) == 1
    assert calls[0][0] == audio_text(q)
    assert calls[0][1] == variant_length_scale(q, "fast")


def test_audio_endpoint_variant_normal_same_cache_path(monkeypatch, tmp_path):
    # La variante normal y la llamada sin variante comparten digest/cache: una
    # segunda petición (sin variante) sirve del cache de la primera (sin síntesis).
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    monkeypatch.setattr("services.tts.is_ready", lambda: True)

    calls = []

    def fake_synthesize(text, length_scale=1.0):
        calls.append((text, length_scale))
        return b"RIFF-fake-wav-bytes"

    monkeypatch.setattr("services.tts.synthesize", fake_synthesize)

    with TestClient(app) as client:
        first = client.get(
            f"/api/listening/audio/{q['id']}",
            params={"user_id": uid, "variant": "normal"},
        )
        second = client.get(
            f"/api/listening/audio/{q['id']}", params={"user_id": uid}
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1
