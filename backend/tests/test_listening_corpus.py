"""Tests del corpus de audio humano (V1.36): loader del banco, pack de grabación
e importación masiva."""
import json
import wave

from scripts.generate_recording_pack import (
    CORPUS_TARGET,
    build_summary,
    file_for,
    grabbable_items,
    write_recording_pack,
)
from scripts.import_audio import _batch_import, entry_from_item
from services.audio_library import AUDIO_LIBRARY_VERSION, load_manifest
from services.listening import (
    LISTENING_CONTEXTS,
    LISTENING_SUBSKILLS,
    LISTENING_TOPICS,
    QUESTION_BANK,
    validate_listening_bank,
)


def _corpus_ids() -> list[str]:
    return [q["id"] for q in QUESTION_BANK if q["id"].startswith("c")]


# --- Loader del corpus -------------------------------------------------------


def test_corpus_is_loaded_and_valid():
    assert validate_listening_bank() == []
    assert len(_corpus_ids()) >= 10


def test_legacy_bank_comes_first():
    # El banco heredado (l1..l23) precede al corpus para preservar la progresión.
    assert QUESTION_BANK[0]["id"] == "l1"
    assert any(q["id"] == "l23" for q in QUESTION_BANK)
    l23_idx = QUESTION_BANK.index(
        next(q for q in QUESTION_BANK if q["id"] == "l23")
    )
    assert l23_idx < len(QUESTION_BANK) - len(_corpus_ids())


def test_corpus_items_default_to_tts():
    # Los ítems del corpus son tts hasta que el manifest respalda su audio_id.
    corpus = [q for q in QUESTION_BANK if q["id"].startswith("c")]
    assert corpus
    assert all(q.get("audio_type", "tts") == "tts" for q in corpus)


def test_corpus_items_declare_audio_and_metadata():
    corpus = [q for q in QUESTION_BANK if q["id"].startswith("c")]
    for q in corpus:
        assert (q.get("audio_id") or "").startswith("audio-c")
        assert q["skill"] in LISTENING_SUBSKILLS
        assert q["topic"] in LISTENING_TOPICS
        assert q["context"] in LISTENING_CONTEXTS
        assert q.get("speaker_id")
        assert q.get("gender") in ("female", "male", "unknown")
        assert q.get("age_band") in ("child", "teen", "adult", "senior", "unknown")
        assert int(q.get("speaker_count", 1)) >= 1


def test_corpus_covers_all_levels_and_is_diverse():
    corpus = [q for q in QUESTION_BANK if q["id"].startswith("c")]
    levels = {q["level"] for q in corpus}
    assert levels == {"A1", "A2", "B1", "B2", "C1", "C2"}
    # Diversidad real: más de un hablante, más de un acento y más de un contexto.
    assert len({q["speaker_id"] for q in corpus}) >= 3
    assert len({q["accent"] for q in corpus}) >= 3
    assert len({q["context"] for q in corpus}) >= 4


# --- Pack de grabación -------------------------------------------------------


def test_grabbable_items_includes_legacy_and_corpus():
    items = grabbable_items()
    ids = {q["audio_id"] for q in items}
    assert "audio-l15" in ids
    assert "audio-c001" in ids


def test_file_for_uses_convention():
    item = {"level": "B1", "speaker_id": "speaker_004", "audio_id": "audio-c021"}
    assert file_for(item) == "B1/speaker_004/audio-c021.wav"


def test_build_summary_reports_targets():
    summary = build_summary()
    assert summary["total_grabbable"] >= 40
    by_level = {lv["level"]: lv for lv in summary["by_level"]}
    assert set(by_level) == set(CORPUS_TARGET)
    for level, lv in by_level.items():
        assert lv["target_min"] == CORPUS_TARGET[level][0]
        assert lv["target_max"] == CORPUS_TARGET[level][1]
        assert lv["specified"] >= 1


def test_write_recording_pack_writes_csv_and_summary(tmp_path):
    summary = write_recording_pack(None, tmp_path)
    csv_path = tmp_path / "recording_pack.csv"
    summary_path = tmp_path / "recording_pack_summary.json"
    assert csv_path.exists()
    assert summary_path.exists()
    assert summary["csv_rows"] == summary["total_grabbable"]
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert "transcript" in header
    assert "audio_id" in header


# --- Importación masiva ------------------------------------------------------


def test_entry_from_item_maps_metadata():
    item = {
        "audio_id": "audio-c021",
        "level": "B1",
        "speaker_id": "speaker_004",
        "accent": "Irish",
        "speaker_count": 2,
        "noise_level": 1,
        "transcript": "I'm gonna be late.",
        "gender": "male",
        "age_band": "adult",
        "region": "IE",
        "speech_rate": 140.0,
        "spontaneity": "semi_scripted",
        "recording_environment": "quiet_room",
        "overlap": False,
        "connected_speech": True,
        "prosody": "apologetic",
        "task_type": "dialogue",
        "context": "conversation",
    }
    entry = entry_from_item(item, 7.0)
    assert entry.audio_id == "audio-c021"
    assert entry.file == "B1/speaker_004/audio-c021.wav"
    assert entry.cefr == "B1"
    assert entry.duration == 7.0
    assert entry.gender == "male"
    assert entry.connected_speech is True
    assert entry.context == "conversation"


def _write_wav(path, duration=1.0, framerate=8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * int(framerate * duration))


def test_batch_import_imports_wavs(monkeypatch, tmp_path):
    lib_dir = tmp_path / "library"
    lib_dir.mkdir()
    (lib_dir / "manifest.json").write_text(
        json.dumps({"version": AUDIO_LIBRARY_VERSION, "entries": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("services.audio_library.library_dir", lambda: lib_dir)
    monkeypatch.setattr(
        "services.audio_library.manifest_path", lambda: lib_dir / "manifest.json"
    )

    wav_dir = tmp_path / "wavs"
    # Convención {cefr}/{speaker_id}/{audio_id}.wav para el primer ítem del corpus.
    first = next(q for q in QUESTION_BANK if q["id"].startswith("c"))
    _write_wav(
        wav_dir / first["level"] / first["speaker_id"] / f"{first['audio_id']}.wav",
        duration=2.0,
    )

    assert _batch_import(wav_dir, None) == 0
    manifest = load_manifest()
    assert len(manifest.entries) == 1
    entry = manifest.entries[0]
    assert entry.audio_id == first["audio_id"]
    assert entry.cefr == first["level"]
    # La duración medida se usa (no la declarada).
    assert abs(entry.duration - 2.0) < 0.1


def test_batch_import_skips_missing_wavs(monkeypatch, tmp_path):
    lib_dir = tmp_path / "library"
    lib_dir.mkdir()
    (lib_dir / "manifest.json").write_text(
        json.dumps({"version": AUDIO_LIBRARY_VERSION, "entries": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr("services.audio_library.library_dir", lambda: lib_dir)
    monkeypatch.setattr(
        "services.audio_library.manifest_path", lambda: lib_dir / "manifest.json"
    )

    assert _batch_import(tmp_path / "empty_wavs", None) == 0
    assert load_manifest().entries == []
