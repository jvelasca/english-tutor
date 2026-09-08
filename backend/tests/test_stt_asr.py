"""Tests de V3.21 (V20-14/V20-15) y V3.22 (ASR-01): taxonomía ASR.

Cubre la clasificación `services.stt.classify_asr_status` (pura, sobre métricas
agregadas), la agregación `aggregate_asr_segments` (sintética, con fakes
duck-typed de Segment/TranscriptionInfo) y el gating en los intentos puntuados:
cuando el audio no se reconoce con fiabilidad (silencio, audio ininteligible o
confianza baja) NO se penaliza al alumno (ni drill, ni read-aloud, ni speaking
abierto).
"""
from types import SimpleNamespace as NS

import pytest
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
    aggregate_asr_segments,
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


# ---------------------------------------------------------------- helpers

def _metrics(
    *,
    segment_count: int = 1,
    mean_logprob: float | None = None,
    duration: float | None = 2.0,
    max_no_speech_prob: float | None = None,
    no_speech_ratio: float | None = None,
) -> dict:
    """Dict de métricas mínimo para `classify_asr_status` (el resto es telemetría)."""
    return {
        "duration": duration,
        "language_probability": 0.9,
        "segment_count": segment_count,
        "mean_logprob": mean_logprob,
        "min_logprob": mean_logprob,
        "max_no_speech_prob": max_no_speech_prob,
        "no_speech_ratio": no_speech_ratio,
        "speech_ratio": None,
        "compression_ratio": None,
    }


def _seg(
    start: float,
    end: float,
    *,
    text: str = "",
    avg_logprob: float | None = -0.2,
    no_speech_prob: float | None = 0.02,
    compression_ratio: float | None = 1.1,
) -> NS:
    """Fake duck-typed de `faster_whisper.Segment`."""
    return NS(
        start=start,
        end=end,
        text=text,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
    )


def _info(
    duration: float | None = 4.0, language_probability: float | None = 0.98
) -> NS:
    """Fake duck-typed de `faster_whisper.TranscriptionInfo` (sin métricas por
    segmento)."""
    return NS(duration=duration, language_probability=language_probability)


# ---------------------------------------------------------------- puro: classify

def test_classify_no_speech_when_silence_long_enough():
    # Silencio: 0 segmentos (Whisper no emite habla) y audio >= umbral.
    assert (
        classify_asr_status(
            text="", metrics=_metrics(segment_count=0, duration=2.0)
        )
        == ASR_NO_SPEECH
    )


def test_classify_no_speech_when_noise_discarded():
    # Ruido: Whisper lo descarta entero (0 segmentos) con audio largo.
    assert (
        classify_asr_status(
            text="", metrics=_metrics(segment_count=0, duration=5.0)
        )
        == ASR_NO_SPEECH
    )


def test_classify_unintelligible_when_attempt_too_short():
    # Captura fallida / audio demasiado corto: sin señal para decir "silencio".
    assert (
        classify_asr_status(
            text="", metrics=_metrics(segment_count=0, duration=0.3)
        )
        == ASR_UNINTELLIGIBLE
    )
    assert (
        classify_asr_status(
            text="", metrics=_metrics(segment_count=0, duration=None)
        )
        == ASR_UNINTELLIGIBLE
    )


def test_classify_unintelligible_segments_without_text():
    # Defensivo: hay segmentos pero nada decodificable.
    assert (
        classify_asr_status(text="", metrics=_metrics(segment_count=1))
        == ASR_UNINTELLIGIBLE
    )


def test_classify_no_speech_when_text_is_silence_hallucination():
    # Texto alucinado por Whisper sobre silencio: toda la señal decodificada
    # está marcada como no-habla -> NO es un fallo lingüístico del alumno.
    # (Caso real medido: silencio digital decodifica "You" con no_speech_prob
    # 0.85 y avg_logprob -0.91.)
    assert (
        classify_asr_status(
            text="you",
            metrics=_metrics(
                mean_logprob=-0.9, max_no_speech_prob=0.85, no_speech_ratio=1.0
            ),
        )
        == ASR_NO_SPEECH
    )


def test_classify_low_confidence_when_text_but_bad_logprob():
    # Voz con baja confianza: texto presente pero logprob agregado muy bajo.
    assert (
        classify_asr_status(
            text="hello", metrics=_metrics(mean_logprob=-2.4)
        )
        == ASR_LOW_CONFIDENCE
    )


def test_classify_ok_with_clean_text():
    # Voz limpia: texto con confianza agregada aceptable.
    assert (
        classify_asr_status(
            text="hello", metrics=_metrics(mean_logprob=-0.3)
        )
        == ASR_OK
    )


def test_classify_ok_when_some_window_flagged_no_speech():
    # Voz real con una ventana concreta marcada como no-habla: si el grueso de
    # la señal es habla clara (no_speech_ratio < 0.5), no se descarta.
    assert (
        classify_asr_status(
            text="hello",
            metrics=_metrics(
                mean_logprob=-0.4, max_no_speech_prob=0.9, no_speech_ratio=0.25
            ),
        )
        == ASR_OK
    )


def test_classify_asr_ok_does_not_decide_linguistic_ko():
    # Frase "incorrecta" pero bien transcrita: el ASR es fiable; la corrección
    # es lingüística (la hace el scorer), no del reconocimiento.
    assert (
        classify_asr_status(
            text="banana", metrics=_metrics(mean_logprob=-0.3)
        )
        == ASR_OK
    )


def test_classify_ignores_whitespace():
    assert (
        classify_asr_status(
            text="   ", metrics=_metrics(segment_count=0, duration=2.0)
        )
        == ASR_NO_SPEECH
    )


# ---------------------------------------------------------------- puro: aggregate

def test_aggregate_clean_speech():
    segs = [_seg(0.0, 2.0, text="hello"), _seg(2.0, 4.0, text="world")]
    m = aggregate_asr_segments(segs, _info())
    assert m["segment_count"] == 2
    assert m["mean_logprob"] == pytest.approx(-0.2)
    assert m["min_logprob"] == pytest.approx(-0.2)
    assert m["max_no_speech_prob"] == pytest.approx(0.02)
    assert m["no_speech_ratio"] == pytest.approx(0.0)
    assert m["speech_ratio"] == pytest.approx(1.0)
    assert m["compression_ratio"] == pytest.approx(1.1)
    assert m["language_probability"] == pytest.approx(0.98)
    assert m["duration"] == pytest.approx(4.0)


def test_aggregate_mean_logprob_weighted_by_duration():
    # Media ponderada por duración: el segmento malo (corto) pesa menos.
    segs = [_seg(0.0, 3.0, avg_logprob=-0.1), _seg(3.0, 5.0, avg_logprob=-2.5)]
    m = aggregate_asr_segments(segs, _info(duration=5.0))
    expected = (3.0 * -0.1 + 2.0 * -2.5) / 5.0  # -1.06
    assert m["mean_logprob"] == pytest.approx(expected)
    assert m["min_logprob"] == pytest.approx(-2.5)


def test_aggregate_mean_logprob_simple_when_no_duration():
    # Fakes sin duración de segmento: respaldo a media simple.
    segs = [_seg(0.0, 0.0, avg_logprob=-0.2), _seg(0.0, 0.0, avg_logprob=-0.6)]
    m = aggregate_asr_segments(segs, _info(duration=2.0))
    assert m["segment_count"] == 2
    assert m["mean_logprob"] == pytest.approx(-0.4)


def test_aggregate_no_speech_ratio():
    segs = [
        _seg(0.0, 1.0, no_speech_prob=0.9),
        _seg(1.0, 3.0, no_speech_prob=0.1),
    ]
    m = aggregate_asr_segments(segs, _info(duration=3.0))
    assert m["no_speech_ratio"] == pytest.approx(1.0 / 3.0, rel=1e-3)
    assert m["max_no_speech_prob"] == pytest.approx(0.9)


def test_aggregate_speech_ratio_partial():
    # 2 s de habla en un audio de 4 s -> speech_ratio 0.5.
    segs = [_seg(0.5, 2.5, avg_logprob=-0.3)]
    m = aggregate_asr_segments(segs, _info(duration=4.0))
    assert m["speech_ratio"] == pytest.approx(0.5)
    assert m["speech_ratio"] <= 1.0


def test_aggregate_empty_returns_zeros():
    m = aggregate_asr_segments([], _info(duration=2.0))
    assert m["segment_count"] == 0
    assert m["mean_logprob"] is None
    assert m["min_logprob"] is None
    assert m["max_no_speech_prob"] is None
    assert m["no_speech_ratio"] is None
    assert m["speech_ratio"] is None
    assert m["compression_ratio"] is None
    assert m["duration"] == pytest.approx(2.0)
    assert m["language_probability"] == pytest.approx(0.98)


def test_aggregate_without_info():
    m = aggregate_asr_segments([])
    assert m["segment_count"] == 0
    assert m["duration"] is None
    assert m["language_probability"] is None


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
