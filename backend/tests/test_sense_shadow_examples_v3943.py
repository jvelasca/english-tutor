"""`--examples N` lista filas por razón con la transcripción del corpus."""
import importlib.util
import json
import sqlite3
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "sense_shadow_report.py"
_spec = importlib.util.spec_from_file_location("sense_shadow_report", _PATH)
assert _spec is not None and _spec.loader is not None
_report_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_report_mod)


def _ledger() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE listening_difficulty_evidence ("
        "word TEXT, question_id TEXT, "
        "sense_match TEXT, sense_reason TEXT, sense_key TEXT)"
    )
    rows = [
        ("bank", "c001", "mismatch", "gloss:other", "bank|noun"),
        ("bank", "c001", "mismatch", "gloss:other", "bank|noun"),
        ("light", "c999", "ambiguous", "occurrence:split", "light|adj"),
        ("park", "c002", "matched", "gloss:declared", "park|noun"),
    ]
    conn.executemany(
        "INSERT INTO listening_difficulty_evidence "
        "(word, question_id, sense_match, sense_reason, sense_key) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    return conn


def _corpus(tmp_path: Path) -> Path:
    path = tmp_path / "listening_corpus.json"
    items = [
        {
            "id": "c001",
            "script": "A: Is there a bank?",
            "transcript": "Is there a bank?",
        },
        {"id": "c002", "script": "The park is closed."},
    ]
    path.write_text(json.dumps({"version": 1, "items": items}), encoding="utf-8")
    return path


def test_examples_list_rows_per_reason_with_transcript(tmp_path):
    transcripts = _report_mod._load_transcripts(_corpus(tmp_path))
    report = _report_mod._report(_ledger(), 1, transcripts)
    examples = report["examples"]

    gloss = examples["gloss:other"]
    assert len(gloss) == 1
    assert gloss[0]["word"] == "bank"
    assert gloss[0]["transcript"] == "Is there a bank?"

    split = examples["occurrence:split"]
    assert len(split) == 1
    assert split[0]["question_id"] == "c999"
    assert split[0]["transcript"] is None

    words = {item["word"] for items in examples.values() for item in items}
    assert "park" not in words
    assert all(
        item["sense_match"] != "matched"
        for items in examples.values()
        for item in items
    )


def test_examples_off_by_default():
    assert "examples" not in _report_mod._report(_ledger())
    assert "examples" not in _report_mod._report(_ledger(), 0)
