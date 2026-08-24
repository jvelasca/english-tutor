"""Gestión de procesos: arrancar y parar backend (uvicorn) y frontend (Vite)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from core import BACKEND_DIR, FRONTEND_DIR, backend_command, frontend_command

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_IS_WINDOWS = os.name == "nt"


def taskkill_command(pid: int) -> list[str]:
    """Comando para matar el árbol de procesos (Windows)."""
    return ["taskkill", "/F", "/T", "/PID", str(pid)]


class ProcessManager:
    """Arranca y detiene los dos procesos de la app (backend y frontend)."""

    def __init__(self) -> None:
        self.backend: subprocess.Popen | None = None
        self.frontend: subprocess.Popen | None = None

    @staticmethod
    def _log_path(name: str) -> Path:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        return _LOG_DIR / f"{name}.log"

    def start_backend(self) -> None:
        if self.backend_running():
            return
        with open(self._log_path("backend"), "ab") as log:
            self.backend = subprocess.Popen(
                backend_command(),
                cwd=str(BACKEND_DIR),
                stdout=log,
                stderr=subprocess.STDOUT,
            )

    def start_frontend(self) -> None:
        if self.frontend_running():
            return
        with open(self._log_path("frontend"), "ab") as log:
            self.frontend = subprocess.Popen(
                frontend_command(),
                cwd=str(FRONTEND_DIR),
                stdout=log,
                stderr=subprocess.STDOUT,
            )

    def stop_all(self) -> None:
        self._stop(self.frontend)
        self._stop(self.backend)
        self.frontend = None
        self.backend = None

    def _stop(self, proc: subprocess.Popen | None) -> None:
        if proc is None:
            return
        if _IS_WINDOWS:
            try:
                subprocess.run(
                    taskkill_command(proc.pid), capture_output=True, timeout=10
                )
            except Exception:  # noqa: BLE001
                pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    def backend_running(self) -> bool:
        return self.backend is not None and self.backend.poll() is None

    def frontend_running(self) -> bool:
        return self.frontend is not None and self.frontend.poll() is None
