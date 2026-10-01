"""El informe de sombra cuenta `occurrence:split` aparte de `possible_mismatch`."""
import importlib.util
import sqlite3
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "sense_shadow_report.py"
_spec = importlib.util.spec_from_file_location("sense_shadow_report", _PATH)
assert _spec is not None and _spec.loader is not None
_report_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_report_mod)


def test_shadow_report_counts_split_beside_possible_mismatch():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE listening_difficulty_evidence ("
        "sense_match TEXT, sense_reason TEXT, sense_key TEXT)"
    )
    rows = [
        ("ambiguous", "gloss:other:weak", "bank|noun"),
        ("ambiguous", "gloss:other:weak", "bank|noun"),
        ("ambiguous", "occurrence:split", "bank|noun"),
        ("mismatch", "gloss:other", "bank|noun"),
        ("matched", "gloss:declared", "bank|noun"),
    ]
    conn.executemany(
        "INSERT INTO listening_difficulty_evidence "
        "(sense_match, sense_reason, sense_key) VALUES (?, ?, ?)",
        rows,
    )
    report = _report_mod._report(conn)
    assert report["possible_mismatch"] == 2
    assert report["occurrence_split"] == 1
    assert report["enforce_suppressed"] == 1
    assert report["enforce_kept"] == 4
