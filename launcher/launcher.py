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
            ttk.Label(services, text=name).grid(
                row=i, column=0, sticky="w", padx=12, pady=2
            )
            ttk.Label(services, textvariable=var).grid(
                row=i, column=1, sticky="e", padx=12, pady=2
            )

        buttons = ttk.Frame(self.root)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Button(buttons, text="Iniciar app", command=self.start).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Detener app", command=self.stop).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Abrir app", command=self.open_app).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Actualizar", command=self.refresh).pack(
            side="left", padx=4
        )

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
                error = f"Error: {exc}"
                health, frontend_up, counts, users = None, False, {}, []
                self.root.after(0, lambda: self._msg.set(error))
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
