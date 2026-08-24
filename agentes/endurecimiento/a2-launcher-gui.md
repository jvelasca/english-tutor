# Subagente A.2 — Launcher de escritorio: GUI + procesos + atajo/icono

## Rol
Programador Python (stdlib) + PowerShell (Windows). Sin acceso a Git (no hagas commit).
Puedes tocar **solo** `launcher/`. NO toques `backend/` ni `frontend/`.

## Objetivo
Completar el launcher de escritorio de English Tutor: GUI mínima con `tkinter` que
arranca/para la app (backend `uvicorn` + frontend `npm run dev`) y muestra el estado de
servicios, la base de datos y los usuarios. Incluye gestión de procesos, lectura de estado
(HTTP + SQLite), y scripts para generar el icono y crear el acceso directo del escritorio.

## Contexto (autocontenido)
- Ya existe `launcher/core.py` (A.1) con: `REPO_ROOT`, `BACKEND_DIR`, `FRONTEND_DIR`,
  `DB_PATH`, `BACKEND_PORT`, `FRONTEND_PORT`, `backend_command()`, `frontend_command()`,
  `backend_url()`, `frontend_url()`, `app_summary()`, `health_status()`, `db_summary()`,
  `user_overview()`. **No lo modifiques**.
- El backend expone `GET /api/health/dependencies` → `{"api","database","ollama","stt","tts"}`
  (valores `ok`/`error`/`ready`/`unavailable`).
- La BD es `backend/data/tutor.db` (SQLite) con tablas `users`, `conversations`, `messages`.
- El venv del proyecto está en `backend/.venv` (Python 3.13.7, con `python.exe` y
  `pythonw.exe` y pytest). El frontend se arranca con `npm run dev` (Vite, puerto 5173).
- Estilo: `from __future__ import annotations`, docstrings en español, línea ≤ 88.
  Ruff usa las mismas reglas del backend (`select E,F,W,I,B`, `ignore B008`, line 88),
  configuradas en `launcher/pyproject.toml`.
- **Nota ruff/subprocess:** si `ruff check .` marca `B603`/`B604`/`B602` en los usos de
  `subprocess`, añade `# noqa: B603` en la línea (los comandos son fijos, sin `shell=True`).

## Tarea

### 1. `launcher/status.py` (nuevo) — contenido exacto

```python
"""Lectura de estado: HTTP (health) y SQLite (contadores/usuarios), solo lectura."""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from contextlib import closing

from core import backend_url, frontend_url


def _get_json(url: str, timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def fetch_health() -> dict | None:
    """Devuelve el dict de /api/health/dependencies, o None si no hay backend."""
    return _get_json(backend_url() + "/api/health/dependencies")


def fetch_frontend() -> bool:
    """True si el frontend responde (GET /)."""
    try:
        with urllib.request.urlopen(frontend_url(), timeout=1.5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def _connect_readonly(path: str) -> sqlite3.Connection:
    uri_path = path.replace("\\", "/")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_db_counts(db_path: str) -> dict:
    """Contadores globales de la BD (0 si no se puede abrir)."""
    try:
        with closing(_connect_readonly(db_path)) as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conversations = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {
            "users": int(users),
            "conversations": int(conversations),
            "messages": int(messages),
        }
    except Exception:  # noqa: BLE001
        return {"users": 0, "conversations": 0, "messages": 0}


def read_users(db_path: str) -> list[tuple]:
    """Lista de (id, name, conversations, messages) por usuario."""
    try:
        with closing(_connect_readonly(db_path)) as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.name,
                       COUNT(DISTINCT c.id) AS conversations,
                       COUNT(m.id) AS messages
                FROM users u
                LEFT JOIN conversations c ON c.user_id = u.id
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY u.id
                ORDER BY u.name
                """
            ).fetchall()
        return [(r["id"], r["name"], r["conversations"], r["messages"]) for r in rows]
    except Exception:  # noqa: BLE001
        return []
```

### 2. `launcher/process_manager.py` (nuevo) — contenido exacto

```python
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
```

### 3. `launcher/launcher.py` (nuevo) — contenido exacto

```python
"""Launcher de escritorio de English Tutor (GUI mínima con tkinter).

Arranca/para el backend (uvicorn) y el frontend (Vite), y muestra el estado de
la app, las dependencias, la base de datos y los usuarios. 100% local.

Uso:
    python launcher.py
"""
from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

from core import (
    DB_PATH,
    app_summary,
    db_summary,
    frontend_url,
    health_status,
    user_overview,
)
from process_manager import ProcessManager
from status import fetch_frontend, fetch_health, read_db_counts, read_users

REFRESH_MS = 2000


class LauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.pm = ProcessManager()
        self._busy = False
        root.title("English Tutor — Launcher")
        root.geometry("560x520")
        root.minsize(500, 460)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 4}

        self._status = tk.StringVar(value="Comprobando…")
        header = ttk.Label(
            self.root, textvariable=self._status, font=("Segoe UI", 12, "bold")
        )
        header.grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        services = ttk.LabelFrame(self.root, text="Servicios")
        services.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        services.columnconfigure(1, weight=1)
        self._svc_vars: dict[str, tk.StringVar] = {}
        for i, name in enumerate(
            ["Backend", "Frontend", "Ollama", "STT", "TTS", "Base de datos"]
        ):
            var = tk.StringVar(value="…")
            self._svc_vars[name] = var
            ttk.Label(services, text=name).grid(row=i, column=0, sticky="w", padx=12, pady=2)
            ttk.Label(services, textvariable=var).grid(row=i, column=1, sticky="e", padx=12, pady=2)

        buttons = ttk.Frame(self.root)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Button(buttons, text="Iniciar app", command=self.start).pack(side="left", padx=4)
        ttk.Button(buttons, text="Detener app", command=self.stop).pack(side="left", padx=4)
        ttk.Button(buttons, text="Abrir app", command=self.open_app).pack(side="left", padx=4)
        ttk.Button(buttons, text="Actualizar", command=self.refresh).pack(side="left", padx=4)

        db_frame = ttk.LabelFrame(self.root, text="Base de datos")
        db_frame.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self._db_var = tk.StringVar(value="…")
        ttk.Label(db_frame, textvariable=self._db_var).grid(
            row=0, column=0, sticky="w", padx=12, pady=2
        )

        users_frame = ttk.LabelFrame(self.root, text="Usuarios")
        users_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        self.root.rowconfigure(4, weight=1)
        self.root.columnconfigure(0, weight=1)
        cols = ("name", "conversations", "messages")
        self._tree = ttk.Treeview(users_frame, columns=cols, show="headings", height=6)
        self._tree.heading("name", text="Nombre")
        self._tree.heading("conversations", text="Conversaciones")
        self._tree.heading("messages", text="Mensajes")
        self._tree.column("name", width=220, anchor="w")
        self._tree.column("conversations", width=120, anchor="e")
        self._tree.column("messages", width=120, anchor="e")
        self._tree.pack(fill="both", expand=True, padx=6, pady=6)

        self._msg = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self._msg, foreground="#6b7280").grid(
            row=5, column=0, columnspan=2, sticky="w", **pad
        )

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._msg.set("Comprobando estado…")

        def work() -> None:
            try:
                health = fetch_health()
                frontend_up = fetch_frontend()
                counts = read_db_counts(str(DB_PATH))
                users = read_users(str(DB_PATH))
            except Exception as exc:  # noqa: BLE001
                health, frontend_up, counts, users = None, False, {}, []
                self.root.after(0, lambda: self._msg.set(f"Error: {exc}"))
            self.root.after(0, lambda: self._apply(health, frontend_up, counts, users))

        threading.Thread(target=work, daemon=True).start()

    def _apply(self, health, frontend_up, counts, users) -> None:
        svc = health_status(health)
        summary = app_summary(svc["api"] == "ok", frontend_up)
        backend_up = summary["backend"] == "on"
        self._svc_vars["Backend"].set("Activo" if backend_up else "Detenido")
        self._svc_vars["Frontend"].set(
            "Activo" if summary["frontend"] == "on" else "Detenido"
        )
        self._svc_vars["Ollama"].set(self._label(svc["ollama"]))
        self._svc_vars["STT"].set(self._label(svc["stt"]))
        self._svc_vars["TTS"].set(self._label(svc["tts"]))
        self._svc_vars["Base de datos"].set(self._label(svc["database"]))

        c = db_summary(counts)
        self._db_var.set(
            f"{c['users']} usuarios · {c['conversations']} conversaciones · "
            f"{c['messages']} mensajes"
        )

        self._tree.delete(*self._tree.get_children())
        for u in user_overview(users):
            self._tree.insert(
                "", "end", values=(u["name"], u["conversations"], u["messages"])
            )

        running = backend_up and summary["frontend"] == "on"
        self._status.set("English Tutor — " + ("En marcha" if running else "Detenida"))
        self._busy = False

    @staticmethod
    def _label(value: str) -> str:
        return {
            "ok": "OK",
            "error": "Error",
            "unavailable": "No disponible",
            "unknown": "—",
        }.get(value, value)

    def start(self) -> None:
        self._msg.set("Arrancando servicios…")

        def work() -> None:
            if not self.pm.backend_running():
                self.pm.start_backend()
            if not self.pm.frontend_running():
                self.pm.start_frontend()
            self.root.after(2500, self._open_browser_when_ready)

        threading.Thread(target=work, daemon=True).start()

    def _open_browser_when_ready(self) -> None:
        if fetch_frontend():
            webbrowser.open(frontend_url())
        self.refresh()

    def stop(self) -> None:
        self._msg.set("Deteniendo servicios…")
        self.pm.stop_all()
        self.root.after(500, self.refresh)

    def open_app(self) -> None:
        if fetch_frontend():
            webbrowser.open(frontend_url())
            self._msg.set("Abriendo app…")
        else:
            self._msg.set("El frontend no está activo. Pulsa 'Iniciar app'.")
            self.refresh()


def main() -> None:
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

### 4. `launcher/tests/test_status.py` (nuevo, 7 tests) — contenido exacto

```python
"""Tests de status.py (lectura de estado)."""
import sqlite3
from contextlib import closing

import status


def _make_db(path):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL "
            "DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "user_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT "
            "NULL, created_at TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO users VALUES ('u1','Ana','now'),('u2','Bob','now')")
        conn.execute(
            "INSERT INTO conversations VALUES ('c1','t','now','now','u1'),"
            "('c2','t2','now','now','u1')"
        )
        conn.execute(
            "INSERT INTO messages (conversation_id,role,content,created_at) VALUES "
            "('c1','user','hi','now'),('c1','assistant','hello','now'),"
            "('c1','user','bye','now')"
        )


def test_read_db_counts(tmp_path):
    db = tmp_path / "t.db"
    _make_db(db)
    assert status.read_db_counts(str(db)) == {
        "users": 2,
        "conversations": 2,
        "messages": 3,
    }


def test_read_users(tmp_path):
    db = tmp_path / "t.db"
    _make_db(db)
    users = status.read_users(str(db))
    assert len(users) == 2
    ana = [u for u in users if u[1] == "Ana"][0]
    assert ana[2] == 2
    assert ana[3] == 3


def test_read_db_counts_missing_file():
    assert status.read_db_counts("Z:/no/existe/tutor.db") == {
        "users": 0,
        "conversations": 0,
        "messages": 0,
    }


class _FakeResp:
    def __init__(self, payload=b"", code=200):
        self._payload = payload
        self.status = code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def test_fetch_health_ok(monkeypatch):
    monkeypatch.setattr(
        "status.urllib.request.urlopen",
        lambda url, timeout: _FakeResp(
            b'{"database":"ok","ollama":"ok","stt":"ready","tts":"ready"}'
        ),
    )
    assert status.fetch_health()["database"] == "ok"


def test_fetch_health_unreachable(monkeypatch):
    def boom(url, timeout):
        raise OSError("refused")

    monkeypatch.setattr("status.urllib.request.urlopen", boom)
    assert status.fetch_health() is None


def test_fetch_frontend_ok(monkeypatch):
    monkeypatch.setattr(
        "status.urllib.request.urlopen", lambda url, timeout: _FakeResp(b"", 200)
    )
    assert status.fetch_frontend() is True


def test_fetch_frontend_down(monkeypatch):
    def boom(url, timeout):
        raise OSError("refused")

    monkeypatch.setattr("status.urllib.request.urlopen", boom)
    assert status.fetch_frontend() is False
```

### 5. `launcher/tests/test_process_manager.py` (nuevo, 2 tests) — contenido exacto

```python
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
```

### 6. `launcher/make_icon.ps1` (nuevo) — genera `icon.ico`

```powershell
# Genera el icono del launcher (icon.ico) con System.Drawing (solo Windows).
# Uso:  powershell -ExecutionPolicy Bypass -File make_icon.ps1
$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$iconPath = Join-Path $launcherDir "icon.ico"

Add-Type -AssemblyName System.Drawing
$size = 256
$bmp = New-Object System.Drawing.Bitmap $size, $size
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::FromArgb(255, 37, 99, 235))
$font = New-Object System.Drawing.Font("Segoe UI", 110, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$white = [System.Drawing.Brushes]::White
$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center
$sf.LineAlignment = [System.Drawing.StringAlignment]::Center
$rect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
$g.DrawString("EN", $font, $white, $rect, $sf)
$g.Dispose()

$hIcon = $bmp.GetHicon()
$icon = [System.Drawing.Icon]::FromHandle($hIcon)
$fs = [System.IO.File]::Create($iconPath)
$icon.Save($fs)
$fs.Close()
$icon.Dispose()
$bmp.Dispose()

Write-Host "Icono generado: $iconPath"
```

### 7. `launcher/install_shortcut.ps1` (nuevo) — crea el acceso directo del escritorio

```powershell
# Crea un acceso directo del escritorio para el launcher (genera el icono si falta).
# Uso:  powershell -ExecutionPolicy Bypass -File install_shortcut.ps1
$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $launcherDir
$pythonw = Join-Path $repoRoot "backend\.venv\Scripts\pythonw.exe"
$script = Join-Path $launcherDir "launcher.py"
$iconPath = Join-Path $launcherDir "icon.ico"

if (-not (Test-Path $iconPath)) {
    & (Join-Path $launcherDir "make_icon.ps1")
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "English Tutor.lnk"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = $pythonw
$sc.Arguments = "`"$script`""
$sc.WorkingDirectory = $launcherDir
$sc.IconLocation = "$iconPath,0"
$sc.Description = "Arranca/detiene English Tutor y muestra su estado"
$sc.Save()

Write-Host "Acceso directo creado: $shortcutPath"
```

## Verificación (desde `launcher/`)

```powershell
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q
..\backend\.venv\Scripts\python.exe -m ruff check .
..\backend\.venv\Scripts\python.exe -c "import launcher"
powershell -ExecutionPolicy Bypass -File make_icon.ps1
```

Objetivo:
- `pytest` verde con **22 tests** (13 de A.1 + 9 nuevos).
- `ruff check .` → **All checks passed!**.
- `python -c "import launcher"` no falla (importa sin abrir GUI).
- `make_icon.ps1` genera `launcher/icon.ico` (verifica que existe y pesa > 0 bytes).

## Criterios de aceptación
- 22 tests verdes.
- `ruff` limpio.
- `import launcher` OK.
- `launcher/icon.ico` generado y presente.
- Sin tocar `backend/` ni `frontend/`.

## Restricciones
- NO tocar `backend/` ni `frontend/`.
- NO modificar `launcher/core.py` ni `launcher/tests/test_core.py` ni `launcher/pyproject.toml`.
- NO ejecutar `install_shortcut.ps1` (eso lo hará el gerente/usuario).
- NO hagas commit ni toques documentación.

## Salida
Lista de archivos creados, salida de `pytest`, de `ruff check .`, de `import launcher`,
confirmación de que `icon.ico` se generó, y cualquier desviación.
