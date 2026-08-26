"""Tests del modelo de AudioRealization (V1.14): separa la dificultad declarada
de la realmente realizada por el audio, para que la metadata falsa no genere
evidencia auditiva no respaldada."""
from services.listening import (
    AUDIO_TYPES,
    DIFFICULTY_FACTORS,
    QUESTION_BANK,
    audio_digest,
    difficulty_from_vector,
    get_question,
    realization_gap_factors,
    realization_status,
    realized_difficulty,
    realized_vector,
    spoken_text,
    subskill_realization_gap,
    validate_listening_bank,
)


def _q(qid: str) -> dict:
    q = get_question(qid)
    assert q is not None, qid
    return q


def test_audio_types_declared():
    assert set(AUDIO_TYPES) == {
        "tts",
        "recorded",
        "mixed",
        "synthetic_multispeaker",
        "real_world",
    }


def test_bank_defaults_to_tts_and_is_valid():
    assert validate_listening_bank() == []
    assert all(q.get("audio_type", "tts") == "tts" for q in QUESTION_BANK)


def test_tts_realizes_text_intrinsic_factors():
    # vocabulary/syntactic/length dependen del texto, que sí se lee → realizados.
    q = _q("l8")
    realized = realized_vector(q)
    for factor in ("vocabulary", "syntactic", "length"):
        assert realized[factor] == q["difficulty_vector"][factor], factor


def test_tts_does_not_realize_accent_speakers_noise():
    # l8 declara accent=6, speaker_count=3, noise=6, pero el audio es una sola voz
    # Piper limpia → realización 1 en esas dimensiones.
    q = _q("l8")
    realized = realized_vector(q)
    assert realized["accent"] == 1
    assert realized["speaker_count"] == 1
    assert realized["noise"] == 1


def test_tts_speed_realized_only_with_rate():
    # l8 no fija speech_rate → la velocidad es la del modelo (realizado = 1).
    assert realized_vector(_q("l8"))["speed"] == 1
    # l16 fija speech_rate=185 → la velocidad se mapea y se realiza.
    l16 = _q("l16")
    assert realized_vector(l16)["speed"] == l16["difficulty_vector"]["speed"]


def test_connected_speech_strong_reduction_realizes_declared():
    # l16 ("Gonnago"/"d'you") y l17 ("Whaddaya") escriben la reducción → realizada.
    assert realized_vector(_q("l16"))["connected_speech"] == 6
    assert realized_vector(_q("l17"))["connected_speech"] == 6


def test_connected_speech_mild_contraction_partial():
    # l18 ("she'd") es contracción suave → realización parcial (máx 2), declarado 3.
    assert realized_vector(_q("l18"))["connected_speech"] == 2


def test_connected_speech_clean_text_minimal():
    # l8 no tiene reducción audible → realización mínima.
    assert realized_vector(_q("l8"))["connected_speech"] == 1


def test_realized_difficulty_l8_shows_large_gap():
    # l8 declara dificultad 6 pero el audio realiza dificultad 3: evidencia débil.
    q = _q("l8")
    assert q["difficulty_vector"]["speaker_count"] == 3
    assert realized_difficulty(q) == 3
    assert realized_difficulty(q) < difficulty_from_vector(q["difficulty_vector"])


def test_realization_gap_factors_l8():
    q = _q("l8")
    gaps = realization_gap_factors(q)
    assert "accent" in gaps
    assert "speaker_count" in gaps
    assert "noise" in gaps
    assert "connected_speech" in gaps
    assert "speed" in gaps
    # vocabulary/syntactic/length se realizan → no son brecha.
    assert "vocabulary" not in gaps


def test_realization_status_verified_flag():
    q = _q("l8")
    status = realization_status(q)
    assert status["accent"] == {"declared": 6, "realized": 1, "verified": False}
    assert status["vocabulary"] == {"declared": 6, "realized": 6, "verified": True}
    assert set(status) == set(DIFFICULTY_FACTORS)


def test_subskill_realization_gap_multiple_speakers():
    # l20 declara multiple_speakers con speaker_count=4, pero audio es 1 voz.
    assert subskill_realization_gap(_q("l20"), "multiple_speakers") is True
    # Las sub-destrezas de comprensión textual no dependen de un factor de audio.
    assert subskill_realization_gap(_q("l8"), "inference") is False


def test_non_tts_realizes_declared():
    q = dict(_q("l8"), audio_type="recorded")
    assert realized_vector(q) == q["difficulty_vector"]
    assert realization_gap_factors(q) == []


def test_audio_digest_changes_with_content():
    base = _q("l16")
    same = dict(base)
    assert audio_digest(base) == audio_digest(same)
    # Un cambio en el texto o en la velocidad cambia el digest (invalida el cache).
    assert audio_digest(dict(base, transcript="Another text.")) != audio_digest(base)
    assert audio_digest(dict(base, speech_rate=150.0)) != audio_digest(base)
    assert audio_digest(dict(base, repetition_policy="twice")) != audio_digest(base)


def test_spoken_text_honors_twice():
    q = {"transcript": "Hello.", "script": "Hello."}
    assert spoken_text(q) == "Hello."
    assert spoken_text(dict(q, repetition_policy="twice")) == "Hello.. Hello."


def test_validate_bank_rejects_bad_audio_type():
    bad = dict(_q("l1"), audio_type="nope")
    errors = validate_listening_bank([bad])
    assert any("audio_type" in e for e in errors)
