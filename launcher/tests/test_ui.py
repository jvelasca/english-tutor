"""Tests de los helpers puros de la GUI del launcher (ui.py)."""
import ui


def test_status_dot_known_states():
    assert ui.status_dot("ok") == "🟢"
    assert ui.status_dot("ready") == "🟢"
    assert ui.status_dot("error") == "🔴"
    assert ui.status_dot("unavailable") == "🟡"
    assert ui.status_dot("off") == "⚪"


def test_status_dot_unknown_falls_back():
    assert ui.status_dot("anything-else") == "⚪"


def test_icons_have_expected_keys():
    assert ui.SERVICE_ICONS["Backend"] == "🖥️"
    assert ui.SERVICE_ICONS["Ollama"] == "🦙"
    assert ui.SECTION_ICONS["Servicios"] == "🛠️"
    assert ui.ACTION_ICONS["start"] == "▶️"


def test_read_log_tail_returns_last_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    (tmp_path / "backend.log").write_text("l1\nl2\nl3\nl4\n", encoding="utf-8")
    assert ui.read_log_tail("backend", max_lines=2) == "l3\nl4"


def test_read_log_tail_missing_file_is_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    assert ui.read_log_tail("frontend") == ""
