"""Tests del núcleo puro del launcher (launcher/core.py)."""
from core import (
    BACKEND_DIR,
    BACKEND_PORT,
    FRONTEND_DIR,
    FRONTEND_PORT,
    REPO_ROOT,
    app_summary,
    backend_command,
    backend_url,
    db_summary,
    frontend_command,
    frontend_url,
    health_status,
    user_overview,
)


def test_repo_root_contains_backend_and_frontend():
    assert BACKEND_DIR.name == "backend"
    assert FRONTEND_DIR.name == "frontend"
    assert REPO_ROOT == BACKEND_DIR.parent


def test_backend_command_uses_venv_python():
    cmd = backend_command()
    assert cmd[0].endswith("python.exe") or cmd[0].endswith("python")
    assert "-m" in cmd
    assert "uvicorn" in cmd
    assert "main:app" in cmd
    assert str(BACKEND_PORT) in cmd


def test_frontend_command_runs_dev():
    cmd = frontend_command()
    assert "run" in cmd
    assert cmd[-1] == "dev"


def test_urls():
    assert backend_url() == f"http://127.0.0.1:{BACKEND_PORT}"
    assert frontend_url() == f"http://localhost:{FRONTEND_PORT}"


def test_app_summary_on():
    assert app_summary(True, True) == {"backend": "on", "frontend": "on"}


def test_app_summary_off():
    assert app_summary(False, False) == {"backend": "off", "frontend": "off"}


def test_app_summary_mixed():
    assert app_summary(True, False) == {"backend": "on", "frontend": "off"}


def test_health_status_none():
    status = health_status(None)
    assert status["api"] == "off"
    assert status["database"] == "unknown"


def test_health_status_ok():
    deps = {
        "api": "ok",
        "database": "ok",
        "ollama": "ok",
        "stt": "ready",
        "tts": "unavailable",
    }
    status = health_status(deps)
    assert status["database"] == "ok"
    assert status["stt"] == "ok"
    assert status["tts"] == "unavailable"


def test_health_status_error():
    status = health_status(
        {"database": "error", "ollama": "ok", "stt": "ready", "tts": "ready"}
    )
    assert status["database"] == "error"


def test_db_summary_defaults():
    assert db_summary({}) == {"users": 0, "conversations": 0, "messages": 0}


def test_db_summary_counts():
    assert db_summary({"users": 3, "conversations": 10, "messages": 42}) == {
        "users": 3,
        "conversations": 10,
        "messages": 42,
    }


def test_user_overview():
    rows = [("a", "Ana", 2, 5), ("b", "Bob", 0, 0)]
    overview = user_overview(rows)
    assert overview[0] == {
        "id": "a",
        "name": "Ana",
        "conversations": 2,
        "messages": 5,
    }
    assert overview[1]["messages"] == 0
