"""Launcher de escritorio de English Tutor (GUI con tkinter).

Arranca/para el backend (uvicorn) y el frontend (Vite), y muestra el estado de
la app, las dependencias, la base de datos, los usuarios y los logs recientes.
100% local.

Uso:
    python launcher.py

Concurrencia: todo el I/O (HTTP, SQLite, subprocesos, lectura de logs) se ejecuta
en hilos de trabajo; los resultados se comunican al hilo principal (tkinter) a
través de una cola. El hilo principal solo toca la UI y nunca llama `after` desde
un hilo secundario. El acceso al `ProcessManager` se protege con un candado.
"""
from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

from browser_cookies import collect_cookies
from core import (
    DB_PATH,
    app_summary,
    author_line,
    db_summary,
    frontend_url,
    health_status,
    icon_file,
    lan_url,
    user_overview,
)
from process_manager import ProcessManager
from state_store import load_state, save_state
from status import (
    fetch_frontend,
    fetch_health,
    fetch_version,
    read_db_counts,
    read_db_details,
    read_users,
)
from ui import (
    ACTION_ICONS,
    COLORS,
    SECTION_ICONS,
    SERVICE_ICONS,
    read_log_tail,
    status_dot,
)

REFRESH_MS = 2000
POLL_MS = 100
BROWSER_DELAY_S = 2.0

# Tamaño por defecto de la ventana y posición inicial del divisor entre columnas.
# Ambos se redimensionan y se persisten al cerrar (ver state_store.py).
WINDOW_W = 1160
WINDOW_H = 800
COLUMN_W = 540

_SERVICE_ORDER = ["Backend", "Frontend", "Ollama", "STT", "TTS", "Base de datos"]


class Collapsible(ttk.Frame):
    """Panel desplegable con cabecera clicable (título + icono + flecha)."""

    def __init__(
        self, parent: tk.Misc, title: str, icon: str = "", expanded: bool = True
    ) -> None:
        super().__init__(parent, style="Card.TFrame")
        self.title = title
        self.icon = icon
        self._expanded = tk.BooleanVar(value=expanded)
        self._btn = ttk.Button(
            self,
            text=self._label(),
            style="Section.TButton",
            command=self.toggle,
            cursor="hand2",
        )
        self._btn.pack(fill="x")
        self.body = ttk.Frame(self, style="Card.TFrame")
        if expanded:
            self.body.pack(fill="both", expand=True)
        ttk.Separator(self, style="Card.TSeparator").pack(fill="x")

    def _label(self) -> str:
        arrow = "▾" if self._expanded.get() else "▸"
        return f"  {arrow}   {self.icon}   {self.title}"

    def toggle(self) -> None:
        if self._expanded.get():
            self.body.pack_forget()
            self._expanded.set(False)
        else:
            self.body.pack(fill="both", expand=True)
            self._expanded.set(True)
        self._btn.configure(text=self._label())

    def is_expanded(self) -> bool:
        """True si el panel está expandido (para persistir el estado)."""
        return self._expanded.get()


class LauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.pm = ProcessManager()
        self._busy = False
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._state = load_state()
        self._sections_map: dict[str, Collapsible] = {}
        root.title("English Tutor — Launcher")
        # La ventana es redimensionable; el tamaño y la posición del divisor se
        # restauran del estado persistido (state.json) y se guardan al cerrar.
        root.resizable(True, True)
        self._apply_window_icon()
        self._build_style()
        self._build_ui()
        self._restore_window()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Programar desde el hilo principal (antes de mainloop es seguro).
        root.after(0, self.refresh)
        root.after(POLL_MS, self._poll_queue)

    def _apply_window_icon(self) -> None:
        """Icono de la ventana (icon.ico); si falta, se usa el icono por defecto."""
        path = icon_file()
        if os.path.exists(path):
            try:
                self.root.iconbitmap(path)
            except tk.TclError:
                pass

    # --- Estilos ---
    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        c = COLORS
        font = ("Segoe UI", 10)
        style.configure(".", background=c["bg"], foreground=c["text"], font=font)
        style.configure("Card.TFrame", background=c["surface"])
        style.configure("TFrame", background=c["bg"])

        style.configure(
            "Section.TButton",
            background=c["surface"],
            foreground=c["text"],
            anchor="w",
            relief="flat",
            padding=(2, 10),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Section.TButton",
            background=[("active", c["surface"])],
            foreground=[("active", c["accent"])],
        )
        style.configure("Card.TSeparator", background=c["border"])

        style.configure(
            "Accent.TButton",
            background=c["accent"],
            foreground=c["on_accent"],
            borderwidth=0,
            focuscolor=c["accent"],
            padding=(12, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", c["accent_hover"]), ("disabled", "#c7d2fe")],
        )

        style.configure(
            "Ghost.TButton",
            background=c["surface"],
            foreground=c["text"],
            borderwidth=1,
            bordercolor=c["border"],
            padding=(10, 8),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", c["bg"])],
            bordercolor=[("active", c["accent"])],
        )

        style.configure("Header.TLabel", background=c["surface"], foreground=c["text"])
        style.configure(
            "Badge.TLabel",
            background=c["accent"],
            foreground=c["on_accent"],
            font=("Segoe UI", 13, "bold"),
            padding=(10, 8),
        )
        style.configure(
            "Card.TLabel", background=c["surface"], foreground=c["text"], font=font
        )
        style.configure(
            "Status.TLabel",
            background=c["surface"],
            foreground=c["text"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Link.TLabel",
            background=c["surface"],
            foreground=c["accent"],
            font=font,
        )
        style.configure(
            "Title.TLabel",
            background=c["surface"],
            foreground=c["text"],
            font=("Segoe UI", 15, "bold"),
        )
        style.configure(
            "Sub.TLabel", background=c["surface"], foreground=c["text_dim"], font=font
        )
        style.configure(
            "Dim.TLabel", background=c["bg"], foreground=c["text_dim"], font=font
        )
        style.configure(
            "DimCard.TLabel",
            background=c["surface"],
            foreground=c["text_dim"],
            font=font,
        )
        style.configure(
            "Service.TLabel", background=c["surface"], foreground=c["text"], font=font
        )

        style.configure(
            "Treeview",
            background=c["surface"],
            fieldbackground=c["surface"],
            foreground=c["text"],
            rowheight=26,
            bordercolor=c["border"],
        )
        style.configure(
            "Treeview.Heading",
            background=c["bg"],
            foreground=c["text_dim"],
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", c["accent"])])

        style.configure(
            "TNotebook", background=c["surface"], borderwidth=0, tabmargins=(4, 6, 4, 0)
        )
        style.configure(
            "TNotebook.Tab",
            background=c["bg"],
            foreground=c["text_dim"],
            padding=(14, 6),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", c["surface"])],
            foreground=[("selected", c["text"])],
        )

    # --- UI ---
    def _build_ui(self) -> None:
        root = self.root

        # Cabecera (banner).
        header = ttk.Frame(root, style="Card.TFrame")
        header.pack(fill="x")
        brand = ttk.Frame(header, style="Card.TFrame")
        brand.pack(side="left", padx=16, pady=12)
        ttk.Label(brand, text="EN", style="Badge.TLabel").pack(side="left")
        txt = ttk.Frame(brand, style="Card.TFrame")
        txt.pack(side="left", padx=(10, 0))
        ttk.Label(txt, text="English Tutor", style="Title.TLabel").pack(anchor="w")
        self._version = tk.StringVar(value="")
        ttk.Label(
            txt, textvariable=self._version, style="Sub.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            txt, text=author_line(), style="DimCard.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        self._status = tk.StringVar(value="Comprobando…")
        self._status_dot = tk.StringVar(value=status_dot("unknown"))
        pill = ttk.Frame(header, style="Card.TFrame")
        pill.pack(side="right", padx=16, pady=12)
        ttk.Label(pill, textvariable=self._status_dot, style="Card.TLabel").pack(
            side="left"
        )
        ttk.Label(
            pill,
            textvariable=self._status,
            style="Status.TLabel",
        ).pack(side="left", padx=(6, 0))

        # Acciones.
        actions = ttk.Frame(root, style="TFrame")
        actions.pack(fill="x", padx=16, pady=(12, 6))
        ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['start']}  Iniciar app",
            style="Accent.TButton",
            command=self.start,
        ).pack(side="left")
        ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['stop']}  Detener app",
            style="Ghost.TButton",
            command=self.stop,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['open']}  Abrir app",
            style="Ghost.TButton",
            command=self.open_app,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['refresh']}  Actualizar",
            style="Ghost.TButton",
            command=self.refresh,
        ).pack(side="left", padx=(8, 0))

        # Panel de estado final (footer): se empaqueta primero para que quede
        # anclado abajo.
        self._msg = tk.StringVar(value="")
        footer = ttk.Frame(root, style="Card.TFrame")
        footer.pack(fill="x", side="bottom")
        ttk.Separator(footer, style="Card.TSeparator").pack(fill="x")
        ttk.Label(
            footer, textvariable=self._msg, style="DimCard.TLabel"
        ).pack(anchor="w", padx=16, pady=6)

        # PanedWindow horizontal: dos columnas redimensionables arrastrando el
        # divisor central. Cada columna tiene su propio scroll vertical.
        paned = ttk.PanedWindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        left_outer, self._col_left = self._make_scrollable_column(paned)
        right_outer, self._col_right = self._make_scrollable_column(paned)
        paned.add(left_outer, weight=1)
        paned.add(right_outer, weight=1)
        self._paned = paned

        # El wraplength del detalle de la BD sigue al ancho real de la columna.
        self._col_left.bind("<Configure>", lambda e: self._update_detail_wrap())

        self._build_services(self._col_left)
        self._build_access(self._col_left)
        self._build_database(self._col_left)
        self._build_users(self._col_right)
        self._build_cookies(self._col_right)
        self._build_logs(self._col_right)

    def _make_scrollable_column(self, parent: tk.Misc) -> tuple[ttk.Frame, ttk.Frame]:
        """Columna con scroll vertical: devuelve (contenedor, frame interior)."""
        outer = ttk.Frame(parent, style="TFrame")
        canvas = tk.Canvas(outer, bg=COLORS["bg"], highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="TFrame")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        return outer, inner

    def _section(
        self, parent: tk.Misc, title: str, expanded: bool = True
    ) -> Collapsible:
        saved = self._state["sections"].get(title)
        if saved is not None:
            expanded = saved
        sec = Collapsible(parent, title, SECTION_ICONS.get(title, ""), expanded)
        sec.pack(fill="x", padx=16, pady=(10, 0))
        self._sections_map[title] = sec
        return sec

    def _build_services(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Servicios")
        grid = ttk.Frame(sec.body, style="Card.TFrame")
        grid.pack(fill="x", padx=14, pady=(4, 12))
        self._svc_vars: dict[str, tk.StringVar] = {}
        for i, name in enumerate(_SERVICE_ORDER):
            var = tk.StringVar(value="…")
            self._svc_vars[name] = var
            icon = SERVICE_ICONS.get(name, "•")
            ttk.Label(grid, text=icon, style="Service.TLabel").grid(
                row=i, column=0, sticky="w", padx=(0, 6), pady=3
            )
            ttk.Label(grid, text=name, style="Service.TLabel").grid(
                row=i, column=1, sticky="w", pady=3
            )
            ttk.Label(grid, textvariable=var, style="Service.TLabel").grid(
                row=i, column=2, sticky="e", padx=(20, 0), pady=3
            )
            grid.columnconfigure(1, weight=1)

    def _build_access(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Acceso a la app")
        grid = ttk.Frame(sec.body, style="Card.TFrame")
        grid.pack(fill="x", padx=14, pady=(4, 12))
        ttk.Label(grid, text="🖥️", style="Service.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Label(grid, text="Este equipo", style="Service.TLabel").grid(
            row=0, column=1, sticky="w", pady=3
        )
        ttk.Label(
            grid, text=frontend_url(), style="Link.TLabel"
        ).grid(row=0, column=2, sticky="e", padx=(20, 0), pady=3)

        ttk.Label(grid, text="📡", style="Service.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Label(grid, text="Red local (LAN)", style="Service.TLabel").grid(
            row=1, column=1, sticky="w", pady=3
        )
        ttk.Label(grid, text=lan_url(), style="Link.TLabel").grid(
            row=1, column=2, sticky="e", padx=(20, 0), pady=3
        )
        grid.columnconfigure(1, weight=1)

    def _build_database(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Base de datos")
        body = ttk.Frame(sec.body, style="Card.TFrame")
        body.pack(fill="x", padx=14, pady=(4, 12))
        self._db_var = tk.StringVar(value="…")
        ttk.Label(body, textvariable=self._db_var, style="Service.TLabel").pack(
            anchor="w"
        )
        self._detail_var = tk.StringVar(value="")
        self._db_detail_label = ttk.Label(
            body,
            textvariable=self._detail_var,
            style="DimCard.TLabel",
            wraplength=COLUMN_W - 30,
        )
        self._db_detail_label.pack(anchor="w", fill="x", pady=(6, 0))

    def _build_users(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Usuarios")
        wrap = ttk.Frame(sec.body, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        cols = ("name", "conversations", "messages")
        self._tree = ttk.Treeview(wrap, columns=cols, show="headings", height=6)
        self._tree.heading("name", text="Nombre")
        self._tree.heading("conversations", text="Conversaciones")
        self._tree.heading("messages", text="Mensajes")
        self._tree.column("name", width=230, anchor="w")
        self._tree.column("conversations", width=110, anchor="e")
        self._tree.column("messages", width=100, anchor="e")
        self._tree.pack(fill="both", expand=True)

    def _build_cookies(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Cookies navegador")
        wrap = ttk.Frame(sec.body, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self._cookie_var = tk.StringVar(value="…")
        ttk.Label(wrap, textvariable=self._cookie_var, style="Service.TLabel").pack(
            anchor="w"
        )
        cols = ("browser", "profile", "name", "host", "expires", "value")
        self._cookie_tree = ttk.Treeview(
            wrap, columns=cols, show="headings", height=8
        )
        self._cookie_tree.heading("browser", text="Navegador")
        self._cookie_tree.heading("profile", text="Perfil")
        self._cookie_tree.heading("name", text="Nombre")
        self._cookie_tree.heading("host", text="Host")
        self._cookie_tree.heading("expires", text="Caducidad")
        self._cookie_tree.heading("value", text="Valor")
        self._cookie_tree.column("browser", width=90, anchor="w")
        self._cookie_tree.column("profile", width=110, anchor="w")
        self._cookie_tree.column("name", width=130, anchor="w")
        self._cookie_tree.column("host", width=130, anchor="w")
        self._cookie_tree.column("expires", width=90, anchor="w")
        self._cookie_tree.column("value", width=280, anchor="w")
        self._cookie_tree.pack(fill="both", expand=True, pady=(6, 0))

    def _build_logs(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Registros", expanded=False)
        wrap = ttk.Frame(sec.body, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        nb = ttk.Notebook(wrap)
        nb.pack(fill="both", expand=True)
        self._log_widgets: dict[str, tk.Text] = {}
        for name in ("backend", "frontend"):
            tab = ttk.Frame(nb, style="Card.TFrame")
            text = tk.Text(
                tab,
                wrap="word",
                height=14,
                bg=COLORS["surface"],
                fg=COLORS["text"],
                relief="flat",
                font=("Consolas", 9),
                state="disabled",
            )
            scroll = ttk.Scrollbar(tab, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            text.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            nb.add(tab, text=f"  {name}.log  ")
            self._log_widgets[name] = text

    # --- Bucle de eventos (hilo principal) ---
    def _poll_queue(self) -> None:
        try:
            while True:
                self._handle(self._queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll_queue)

    def _handle(self, item: tuple) -> None:
        kind = item[0]
        if kind == "refresh":
            self._apply(*item[1])
            self.root.after(REFRESH_MS, self._next_refresh)
        elif kind == "error":
            self._msg.set(f"Error: {item[1]}")
            self._busy = False
        elif kind == "started":
            if item[1]:
                webbrowser.open(frontend_url())
            self.refresh()
        elif kind == "stopped":
            self.refresh()
        elif kind == "open_app":
            if item[1]:
                webbrowser.open(frontend_url())
                self._msg.set("Abriendo app…")
            else:
                self._msg.set("El frontend no está activo. Pulsa 'Iniciar app'.")
                self.refresh()

    def _next_refresh(self) -> None:
        self._busy = False
        self.refresh()

    # --- Acciones ---
    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._msg.set("Comprobando estado…")

        def work() -> None:
            try:
                health = fetch_health()
                frontend_up = fetch_frontend()
                version = fetch_version()
                counts = read_db_counts(str(DB_PATH))
                details = read_db_details(str(DB_PATH))
                users = read_users(str(DB_PATH))
                cookies, cookies_summary = collect_cookies()
                backend_log = read_log_tail("backend")
                frontend_log = read_log_tail("frontend")
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("error", str(exc)))
                return
            self._queue.put(
                (
                    "refresh",
                    (
                        health,
                        frontend_up,
                        version,
                        counts,
                        details,
                        users,
                        cookies,
                        cookies_summary,
                        backend_log,
                        frontend_log,
                    ),
                )
            )

        threading.Thread(target=work, daemon=True).start()

    def _apply(
        self,
        health,
        frontend_up,
        version,
        counts,
        details,
        users,
        cookies,
        cookies_summary,
        backend_log,
        frontend_log,
    ) -> None:
        svc = health_status(health)
        summary = app_summary(svc["api"] == "ok", frontend_up)
        backend_up = summary["backend"] == "on"
        frontend_on = summary["frontend"] == "on"
        self._svc_vars["Backend"].set("Activo" if backend_up else "Detenido")
        self._svc_vars["Frontend"].set("Activo" if frontend_on else "Detenido")
        self._svc_vars["Ollama"].set(self._label(svc["ollama"]))
        self._svc_vars["STT"].set(self._label(svc["stt"]))
        self._svc_vars["TTS"].set(self._label(svc["tts"]))
        self._svc_vars["Base de datos"].set(self._label(svc["database"]))

        running = backend_up and frontend_on
        self._status.set("En marcha" if running else "Detenida")
        self._status_dot.set(status_dot("ok" if running else "off"))
        self._version.set(f"v{version}" if version else "Launcher de escritorio")

        c = db_summary(counts)
        self._db_var.set(
            f"{c['users']} usuarios · {c['conversations']} conversaciones · "
            f"{c['messages']} mensajes"
        )
        self._detail_var.set(
            f"Vocabulario: {details.get('vocabulario', 0)} · "
            f"Errores: {details.get('errores_gramaticales', 0)} · "
            f"Eventos: {details.get('eventos_aprendizaje', 0)} · "
            f"Pronunciación: {details.get('intentos_pronunciacion', 0)} · "
            f"Listening: {details.get('intentos_listening', 0)} · "
            f"Preferencias: {details.get('preferencias', 0)}"
        )

        self._tree.delete(*self._tree.get_children())
        for u in user_overview(users):
            self._tree.insert(
                "", "end", values=("👤 " + u["name"], u["conversations"], u["messages"])
            )

        self._apply_cookies(cookies, cookies_summary)

        self._set_log("backend", backend_log)
        self._set_log("frontend", frontend_log)

        self._msg.set("Última comprobación realizada.")
        self._busy = False

    def _apply_cookies(self, rows: list[dict], summary: dict) -> None:
        browser_txt = (
            ", ".join(f"{b} ({n})" for b, n in summary["browsers"].items())
            or "ningún navegador detectado"
        )
        remembered = summary["remembered"]
        if remembered:
            remembered_txt = f" · usuario recordado: {remembered}"
        else:
            remembered_txt = " · sin usuario recordado todavía"
        self._cookie_var.set(
            f"{summary['total']} cookies de la app · {browser_txt}{remembered_txt}"
        )

        self._cookie_tree.delete(*self._cookie_tree.get_children())
        for c in rows:
            self._cookie_tree.insert(
                "",
                "end",
                values=(
                    c["browser"],
                    c["profile"],
                    c["name"],
                    c["host"],
                    c["expires"],
                    c["value"],
                ),
            )

    def _set_log(self, name: str, content: str) -> None:
        widget = self._log_widgets[name]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if content:
            widget.insert("1.0", content)
        else:
            widget.insert("1.0", f"(sin registro todavía para {name}.log)")
        widget.configure(state="disabled")
        widget.see("end")

    def _update_detail_wrap(self) -> None:
        """Ajusta el wraplength del detalle de la BD al ancho real de su columna."""
        width = self._col_left.winfo_width()
        if width > 60:
            self._db_detail_label.configure(wraplength=width - 30)

    def _restore_window(self) -> None:
        """Restaura tamaño/posición de la ventana y el divisor desde el estado."""
        win = self._state["window"]
        x, y = win["x"], win["y"]
        if x is not None and y is not None:
            self.root.geometry(f"{win['width']}x{win['height']}+{x}+{y}")
        else:
            self.root.geometry(f"{win['width']}x{win['height']}")
        # Fijar el divisor una vez la ventana esté mapeada.
        self.root.after(50, lambda: self._paned.sashpos(0, self._state["sash"]))

    def _on_close(self) -> None:
        """Guarda el estado visual y cierra la ventana."""
        try:
            self._state["window"] = {
                "width": self.root.winfo_width(),
                "height": self.root.winfo_height(),
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
            }
            self._state["sash"] = self._paned.sashpos(0)
            self._state["sections"] = {
                title: sec.is_expanded() for title, sec in self._sections_map.items()
            }
            save_state(self._state)
        except (tk.TclError, ValueError):
            pass
        self.root.destroy()

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
            with self._lock:
                # No duplicar un servicio que ya está activo (p. ej. lanzado con F5).
                backend_up = fetch_health() is not None
                frontend_up = fetch_frontend()
                if not self.pm.backend_running() and not backend_up:
                    self.pm.start_backend()
                if not self.pm.frontend_running() and not frontend_up:
                    self.pm.start_frontend()
            time.sleep(BROWSER_DELAY_S)
            self._queue.put(("started", fetch_frontend()))

        threading.Thread(target=work, daemon=True).start()

    def stop(self) -> None:
        self._msg.set("Deteniendo servicios…")

        def work() -> None:
            with self._lock:
                self.pm.stop_all()
            self._queue.put(("stopped", None))

        threading.Thread(target=work, daemon=True).start()

    def open_app(self) -> None:
        def work() -> None:
            self._queue.put(("open_app", fetch_frontend()))

        threading.Thread(target=work, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
