"""Tests de los helpers puros de la GUI del launcher (ui.py)."""
import ui


def test_status_dot_known_states():
    assert ui.status_dot("ok") == "🟢"
    assert ui.status_dot("ready") == "🟢"
    assert ui.status_dot("error") == "🔴"
    assert ui.status_dot("unavailable") == "🟡"
    assert ui.status_dot("off") == "🔴"


def test_status_dot_unknown_falls_back():
    assert ui.status_dot("anything-else") == "⚪"


def test_status_color_maps_states():
    assert ui.status_color("ok") == ui.COLORS["success"]
    assert ui.status_color("on") == ui.COLORS["success"]
    assert ui.status_color("error") == ui.COLORS["error"]
    assert ui.status_color("off") == ui.COLORS["error"]
    assert ui.status_color("unavailable") == ui.COLORS["warning"]
    assert ui.status_color("unknown") == ui.COLORS["neutral"]


def test_status_color_unknown_falls_back_to_neutral():
    assert ui.status_color("anything-else") == ui.COLORS["neutral"]


def test_icons_have_expected_keys():
    assert ui.SERVICE_ICONS["Backend"] == "🖥️"
    assert ui.SERVICE_ICONS["Ollama"] == "🦙"
    assert ui.SECTION_ICONS["Servicios"] == "🛠️"
    assert ui.SECTION_ICONS["Actividad del servidor"] == "📊"
    assert ui.SECTION_ICONS["Cookies navegador"] == "🍪"
    assert ui.ACTION_ICONS["start"] == "▶️"
    assert ui.ACTION_ICONS["restart"] == "🔁"


def test_server_activity_idle():
    line, rejected = ui.server_activity(
        {"generation": {"running": 0, "jobs": []}, "rate_limited": {"rejected_last_minute": 0}}
    )
    assert line == "En reposo"
    assert rejected == 0


def test_server_activity_generating():
    line, rejected = ui.server_activity(
        {
            "generation": {
                "running": 2,
                "jobs": [
                    {"level": "A1", "requested": 20},
                    {"level": "B1", "requested": 10},
                ],
            },
            "rate_limited": {"rejected_last_minute": 0},
        }
    )
    assert line == "Generando práctica extra (A1, B1)…"
    assert rejected == 0


def test_server_activity_with_rejections():
    line, rejected = ui.server_activity(
        {"generation": {"running": 0, "jobs": []}, "rate_limited": {"rejected_last_minute": 7}}
    )
    assert line == "En reposo"
    assert rejected == 7


def test_server_activity_none_backend_down():
    line, rejected = ui.server_activity(None)
    assert line == "No disponible (backend apagado)"
    assert rejected == 0


def test_read_log_tail_returns_last_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    (tmp_path / "backend.log").write_text("l1\nl2\nl3\nl4\n", encoding="utf-8")
    assert ui.read_log_tail("backend", max_lines=2) == "l3\nl4"


def test_read_log_tail_missing_file_is_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    assert ui.read_log_tail("frontend") == ""
