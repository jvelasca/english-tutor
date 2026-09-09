"""Tests del motor `word_alignment_proxy` (V3.29, Fase 3) — sin ASR real.

Cubren el módulo puro (`align_words`, sidecar round-trip) y la idempotencia de
`ensure_word_alignment` con un transcriptor inyectable (doble), sin tocar el
modelo faster-whisper.
"""
from services.word_alignment_proxy import (
    MIN_COVERAGE,
    SYNC_ASR,
    align_words,
    ensure_word_alignment,
    read_sidecar,
    sidecar_path,
    sidecar_words,
    write_sidecar,
)

_SENTENCE = "She said she'd meet us at half past six."


def _asr(*words: tuple[str, float, float]) -> list[dict]:
    """Construye la salida cruda de `transcribe_words` desde tuplas."""
    return [
        {"word": word.strip(), "start": start, "end": end}
        for word, start, end in words
    ]


def test_align_words_full_match_assigns_times():
    words = _asr(
        ("She", 0.0, 0.2),
        ("said", 0.24, 0.4),
        ("she'd", 0.44, 0.6),
        ("meet", 0.64, 0.8),
        ("us", 0.84, 0.95),
        ("at", 0.99, 1.1),
        ("half", 1.14, 1.3),
        ("past", 1.34, 1.5),
        ("six", 1.54, 1.8),
    )
    result = align_words(words, _SENTENCE)
    assert result["coverage"] == 1.0
    texts = [w["text"] for w in result["words"]]
    assert texts == ["She", "said", "she'd", "meet", "us", "at", "half", "past", "six"]
    assert result["words"][0]["start"] == 0.0
    assert result["words"][0]["end"] == 0.2
    # Monótono creciente.
    starts = [w["start"] for w in result["words"]]
    assert starts == sorted(starts)


def test_align_words_ignores_asr_punctuation_and_case():
    # El ASR suele pegar puntuación ("said,") y normalizar mayúsculas.
    words = _asr(
        ("she", 0.0, 0.2),
        ("said,", 0.24, 0.4),
        ("she'd", 0.44, 0.6),
        ("meet", 0.64, 0.8),
    )
    result = align_words(words, "She said, she'd meet")
    assert result["coverage"] == 1.0
    assert result["words"][1]["text"] == "said"
    assert result["words"][1]["start"] == 0.24


def test_align_words_interpolates_unrecognized_word():
    # El ASR no reconoce "she'd" (hueco interior): se interpola entre vecinas.
    words = _asr(
        ("She", 0.0, 0.2),
        ("said", 0.24, 0.4),
        ("meet", 0.8, 1.0),
    )
    result = align_words(words, "She said she'd meet")
    # 3 de 4 palabras alineadas 1:1.
    assert result["coverage"] == 0.75
    assert [w["text"] for w in result["words"]] == ["She", "said", "she'd", "meet"]
    # La interpolada queda entre el fin de "said" y el inicio de "meet".
    gap = result["words"][2]
    assert result["words"][1]["end"] <= gap["start"]
    assert gap["end"] <= result["words"][3]["start"]


def test_align_words_low_coverage_below_threshold():
    # Texto con reducción que el ASR oye como grafía distinta en exceso: la
    # cobertura cae por debajo del umbral y el llamador debe descartar.
    words = _asr(
        ("Gonna", 0.0, 0.5),
        ("go", 0.6, 1.0),
        ("store", 1.2, 1.8),
    )
    result = align_words(words, "Going to go to the store and grab some milk")
    assert result["words"]  # hay respaldo parcial (interior)
    assert result["coverage"] < MIN_COVERAGE


def test_align_words_empty_on_no_match():
    result = align_words(_asr(("hello", 0.0, 0.3)), "completely different text here")
    assert result["words"] == []
    assert result["coverage"] == 0.0


def test_sidecar_round_trip_and_atomic(tmp_path):
    wav = tmp_path / "l18-abcdef.wav"
    wav.write_bytes(b"RIFFfake")
    words = [{"index": 0, "text": "She", "start": 0.0, "end": 0.2}]
    write_sidecar(wav, words, _SENTENCE, coverage=1.0)
    assert sidecar_path(wav).exists()
    assert not sidecar_path(wav).with_name(f"{sidecar_path(wav).name}.tmp").exists()
    payload = read_sidecar(wav)
    assert payload["format"] == "word_alignment_proxy"
    assert payload["sync"] == SYNC_ASR
    assert payload["source_text"] == _SENTENCE
    assert payload["words"] == words
    assert sidecar_words(wav) == words


def test_read_sidecar_returns_none_for_missing_or_invalid(tmp_path):
    wav = tmp_path / "l7-123456.wav"
    assert read_sidecar(wav) is None
    assert sidecar_words(wav) == []
    bad = tmp_path / "x.wav"
    bad.write_bytes(b"not json")
    assert read_sidecar(bad) is None


def test_ensure_word_alignment_writes_once_and_is_idempotent(tmp_path):
    wav = tmp_path / "l16-deadbeef.wav"
    wav.write_bytes(b"RIFFwav")

    source = "Gonna go to the store d'you want anything else"
    calls = {"n": 0}

    def fake_transcribe(_bytes: bytes) -> list[dict]:
        calls["n"] += 1
        return _asr(
            ("Gonna", 0.0, 0.4),
            ("go", 0.44, 0.7),
            ("to", 0.74, 0.9),
            ("the", 0.94, 1.05),
            ("store", 1.1, 1.4),
            ("d'you", 1.5, 1.7),
            ("want", 1.8, 2.0),
            ("anything", 2.1, 2.4),
            ("else", 2.5, 2.8),
        )

    first = ensure_word_alignment(wav, source, transcribe=fake_transcribe)
    assert first is not None
    assert calls["n"] == 1
    assert sidecar_path(wav).exists()

    # Segunda llamada: lee el sidecar sin re-transcribir.
    second = ensure_word_alignment(wav, source, transcribe=fake_transcribe)
    assert calls["n"] == 1
    assert second == first


def test_ensure_word_alignment_force_regenerates(tmp_path):
    wav = tmp_path / "l18-cafebabe.wav"
    wav.write_bytes(b"RIFFwav")
    write_sidecar(
        wav,
        [{"index": 0, "text": "She", "start": 0.0, "end": 0.2}],
        _SENTENCE,
    )

    def fake_transcribe(_bytes: bytes) -> list[dict]:
        return _asr(
            ("She", 0.0, 0.2),
            ("said", 0.24, 0.4),
            ("she'd", 0.44, 0.6),
            ("meet", 0.64, 0.8),
            ("us", 0.84, 0.95),
            ("at", 0.99, 1.1),
            ("half", 1.14, 1.3),
            ("past", 1.34, 1.5),
            ("six", 1.54, 1.8),
        )

    aligned = ensure_word_alignment(
        wav, _SENTENCE, force=True, transcribe=fake_transcribe
    )
    assert aligned is not None
    assert len(aligned) == 9


def test_ensure_word_alignment_low_coverage_does_not_write(tmp_path):
    wav = tmp_path / "l7-badcoverage.wav"
    wav.write_bytes(b"RIFFwav")

    def wrong(_bytes: bytes) -> list[dict]:
        return _asr(("zzz", 0.0, 0.5))

    assert (
        ensure_word_alignment(wav, "Despite the heavy rain", transcribe=wrong)
        is None
    )
    assert not sidecar_path(wav).exists()


def test_ensure_word_alignment_transcriber_raises_degrades(tmp_path):
    wav = tmp_path / "l17-crash.wav"
    wav.write_bytes(b"RIFFwav")

    def boom(_bytes: bytes) -> list[dict]:
        raise RuntimeError("ASR caído")

    assert ensure_word_alignment(wav, "Whaddaya think", transcribe=boom) is None
    assert not sidecar_path(wav).exists()


def test_sidecar_path_appends_suffix():
    from pathlib import Path

    assert sidecar_path(Path("/x/l18-a.wav")) == Path("/x/l18-a.wav.words.json")
