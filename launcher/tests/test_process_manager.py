"""Tests de process_manager.py (partes puras)."""
from process_manager import ProcessManager, taskkill_command


def test_taskkill_command():
    assert taskkill_command(1234) == ["taskkill", "/F", "/T", "/PID", "1234"]


def test_initial_state_not_running():
    pm = ProcessManager()
    assert pm.backend is None
    assert pm.frontend is None
    assert pm.backend_running() is False
    assert pm.frontend_running() is False
