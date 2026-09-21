"""Launcher de escritorio de English Tutor (GUI con tkinter).

Arranca/para el **proceso de producto** (uvicorn, que sirve la API y la UI
compilada en el mismo origen HTTPS — V3.72/RC-01) y muestra el estado de la app,
las dependencias, la base de datos, los usuarios y los logs recientes. 100%
local.

Antes de arrancar, prepara el entorno si hace falta: genera el certificado TLS
autofirmado y compila `frontend/dist` con `npm run build` la primera vez (Node
sigue siendo necesario para **compilar**, ya no para **ejecutar**).

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
from tkinter import messagebox, simpledialog, ttk

from admin import (
    approve_request,
    create_profile,
    list_profiles,
    pending_requests,
    purge_profile,
    reject_request,
    set_profile_status,
)
from browser_cookies import (
    collect_cookies,
    format_cookie_diagnosis,
    format_cookie_summary,
)
from core import (
    DB_PATH,
    admin_pin,
    app_summary,
    apply_admin_config,
    apply_stored_lan_config,
    author_line,
    db_summary,
    frontend_dist_available,
    frontend_url,
    generate_admin_pin,
    health_status,
    icon_file,
    lan_mode,
    lan_url,
    local_url,
    mdns_available,
    port_in_use,
    set_admin_pin,
    toggle_lan_config,
    user_overview,
)
from process_manager import ProcessManager
from state_store import load_state, save_state
from status import (
    fetch_frontend,
    fetch_health,
    fetch_server_status,
    fetch_version,
    read_db_counts,
    read_db_details,
    read_db_info,
    read_users,
)
from ui import (
    ACTION_ICONS,
    COLORS,
    SECTION_ICONS,
    SERVICE_ICONS,
    admin_state_label,
    backend_failure_hint,
    interface_state,
    pending_summary,
    profile_row,
    read_log_tail,
    request_row,
    server_activity,
    status_color,
    status_dot,
)

REFRESH_MS = 2000
POLL_MS = 100
# V3.77: cada cuánto se pregunta al backend si han llegado solicitudes de perfil.
# Es un solo GET y es lo que hace que «la solicitud llegue al webmaster» de
# verdad: sin esto habría que pulsar «Actualizar» para enterarse. Más lento que
# el refresco general a propósito —una cola de solicitudes no cambia cada dos
# segundos— y lo bastante vivo para que el contador no se quede viejo mientras
# alguien la mira.
PROFILES_MS = 15000
BROWSER_DELAY_S = 2.0

# Reloj animado mostrado en la cabecera mientras se arranca/para/reinicia.
SPINNER_CHARS = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"]
SPINNER_MS = 120

# Tamaño por defecto de la ventana y posición inicial del divisor entre columnas.
# Ambos se redimensionan y se persisten al cerrar (ver state_store.py).
WINDOW_W = 1160
WINDOW_H = 800
COLUMN_W = 540

_SERVICE_ORDER = ["Backend", "Interfaz", "Ollama", "STT", "TTS", "Base de datos"]


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
        # V3.75.3: la configuración del launcher (hoy, el modo LAN) se lee y se
        # declara ANTES de construir la interfaz: `_refresh_access` pinta el modo
        # vigente en el primer pintado. La preferencia guardada manda sobre el
        # entorno heredado —es lo que hace que «red local» sobreviva al cierre— y
        # sin fichero el valor por defecto es cerrado (`lan: False`), así que una
        # ausencia de preferencia nunca expone la API. La lectura y la aplicación
        # van en una sola llamada de `core` para que su orden sea verificable sin
        # pantalla (`toggle_lan_config` es la otra mitad).
        self._config = apply_stored_lan_config()
        # V3.77: el PIN de administración guardado se declara en el entorno antes
        # de nada, para que el backend que arranque este launcher lo reciba
        # (`backend_env` copia este entorno). Sin PIN no hay administración, y el
        # launcher lo dice en la propia sección en vez de fallar al pulsar.
        apply_admin_config(self._config)
        self._sections_map: dict[str, Collapsible] = {}
        self._spinner_id: str | None = None
        self._spinner_idx = 0
        self._action_running = False
        # Estado de la sección «Perfiles»: lo que hay pintado (para saber sobre
        # qué fila actúa un botón) y lo que vamos a pedirle al backend.
        self._pending_rows: list[dict] = []
        self._profile_rows: list[dict] = []
        self._profiles_busy = False
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
        # V3.77: la cola de solicitudes se refresca sola (ver `PROFILES_MS`).
        root.after(PROFILES_MS, self._poll_profiles)

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

        # Botón de acción positiva (verde): "Iniciar app" cuando está detenida.
        style.configure(
            "Success.TButton",
            background=c["success"],
            foreground="#ffffff",
            borderwidth=0,
            focuscolor=c["success"],
            padding=(12, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Success.TButton",
            background=[("active", c["success_hover"]), ("disabled", "#d1d5db")],
            foreground=[("disabled", "#9ca3af")],
        )

        # Botón de acción destructiva (rojo): "Detener app" cuando está en marcha.
        style.configure(
            "Danger.TButton",
            background=c["error"],
            foreground="#ffffff",
            borderwidth=0,
            focuscolor=c["error"],
            padding=(12, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Danger.TButton",
            background=[("active", c["error_hover"]), ("disabled", "#d1d5db")],
            foreground=[("disabled", "#9ca3af")],
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
        self._status_dot_label = ttk.Label(
            pill, textvariable=self._status_dot, style="Card.TLabel"
        )
        self._status_dot_label.pack(side="left")
        self._status_label = ttk.Label(
            pill,
            textvariable=self._status,
            style="Status.TLabel",
        )
        self._status_label.pack(side="left", padx=(6, 0))

        # Acciones.
        actions = ttk.Frame(root, style="TFrame")
        actions.pack(fill="x", padx=16, pady=(12, 6))
        self._start_btn = ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['start']}  Iniciar app",
            style="Success.TButton",
            command=self.start,
        )
        self._start_btn.pack(side="left")
        self._stop_btn = ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['stop']}  Detener app",
            style="Ghost.TButton",
            command=self.stop,
        )
        self._stop_btn.pack(side="left", padx=(8, 0))
        self._restart_btn = ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['restart']}  Reiniciar servidor",
            style="Ghost.TButton",
            command=self.restart,
        )
        self._restart_btn.pack(side="left", padx=(8, 0))
        self._open_btn = ttk.Button(
            actions,
            text=f"  {ACTION_ICONS['open']}  Abrir app",
            style="Ghost.TButton",
            command=self.open_app,
        )
        self._open_btn.pack(side="left", padx=(8, 0))
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

        # El wraplength del detalle de la BD y del diagnóstico de cookies sigue
        # al ancho real de su columna.
        self._col_left.bind("<Configure>", lambda e: self._update_detail_wrap())
        self._col_right.bind("<Configure>", lambda e: self._update_detail_wrap())

        self._build_services(self._col_left)
        self._build_activity(self._col_left)
        self._build_access(self._col_left)
        self._build_database(self._col_left)
        # V3.77: «Perfiles» va arriba de «Usuarios» porque es donde el webmaster
        # tiene algo que hacer; «Usuarios» es el recuento de lo que hay.
        self._build_profiles(self._col_right)
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
        self._svc_value_labels: dict[str, ttk.Label] = {}
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
            val = ttk.Label(grid, textvariable=var, style="Service.TLabel")
            val.grid(row=i, column=2, sticky="e", padx=(20, 0), pady=3)
            self._svc_value_labels[name] = val
            grid.columnconfigure(1, weight=1)

    def _build_activity(self, parent: tk.Misc) -> None:
        """Sección «Actividad del servidor»: generación en curso y rechazos 429.

        Muestra si el backend está trabajando (p. ej. generando práctica extra
        de listening con IA local) y si está rechazando peticiones por
        saturación. El texto se colorea según el estado (V3.6.2).
        """
        sec = self._section(parent, "Actividad del servidor")
        body = ttk.Frame(sec.body, style="Card.TFrame")
        body.pack(fill="x", padx=14, pady=(4, 12))
        self._activity_var = tk.StringVar(value="…")
        self._activity_label = ttk.Label(
            body, textvariable=self._activity_var, style="Service.TLabel"
        )
        self._activity_label.pack(anchor="w")
        self._reject_var = tk.StringVar(value="")
        self._reject_label = ttk.Label(
            body, textvariable=self._reject_var, style="Service.TLabel"
        )
        self._reject_label.pack(anchor="w", pady=(2, 0))

    def _build_access(self, parent: tk.Misc) -> None:
        """Panel de acceso: este equipo siempre; la LAN **según el modo** (V3.73.x).

        Con el bind en loopback la URL de LAN no responde, así que la fila no se
        anuncia como si funcionara: dice el estado y ofrece el botón que cambia el
        modo. El modo viaja al backend por su entorno, así que aplicarlo exige
        volver a arrancarlo: `toggle_lan_mode` reutiliza el «Reiniciar» que ya
        existe en la barra de acciones (con la app parada solo deja declarado el
        modo, y lo dice).
        """
        sec = self._section(parent, "Acceso a la app")
        grid = ttk.Frame(sec.body, style="Card.TFrame")
        grid.pack(fill="x", padx=14, pady=(4, 12))

        self._access_row(grid, 0, "🖥️", "Este equipo (HTTPS)", frontend_url())

        # Fila de LAN: valor dinámico + botón de modo (las dos cosas se refrescan
        # en `_refresh_access`, sin reconstruir el panel).
        ttk.Label(grid, text="📡", style="Service.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Label(grid, text="Red local (LAN)", style="Service.TLabel").grid(
            row=1, column=1, sticky="w", pady=3
        )
        self._lan_value = ttk.Frame(grid, style="Card.TFrame")
        self._lan_value.grid(row=1, column=2, sticky="e", padx=(20, 0), pady=3)
        self._lan_toggle = ttk.Button(
            grid, style="Ghost.TButton", command=self.toggle_lan_mode
        )
        self._lan_toggle.grid(row=1, column=3, sticky="e", padx=(10, 0), pady=3)
        self._lan_toggle.bind("<Enter>", self._on_lan_toggle_hover)

        ttk.Label(grid, text="🏷️", style="Service.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Label(grid, text="Nombre local (mDNS)", style="Service.TLabel").grid(
            row=2, column=1, sticky="w", pady=3
        )
        self._mdns_value = ttk.Frame(grid, style="Card.TFrame")
        self._mdns_value.grid(row=2, column=2, sticky="e", padx=(20, 0), pady=3)
        grid.columnconfigure(1, weight=1)

        self._access_note = ttk.Label(
            sec.body, style="DimCard.TLabel", wraplength=COLUMN_W - 30
        )
        self._access_note.pack(anchor="w", fill="x", padx=14, pady=(0, 12))
        self._refresh_access()

    # Aviso con el que se explica el botón (deja claro que reinicia el backend).
    _LAN_TOGGLE_HINT = (
        "Activa o desactiva el acceso desde otros equipos. Se aplica "
        "reiniciando el servidor (la app se recarga)."
    )

    def _on_lan_toggle_hover(self, _event: object) -> None:
        """Explica el botón al pasar el ratón, sin pisar un mensaje en curso."""
        if not self._action_running:
            self._msg.set(self._LAN_TOGGLE_HINT)

    def _access_row(
        self, grid: ttk.Frame, row: int, icon: str, label: str, url: str
    ) -> None:
        """Fila fija icono + texto + enlace (el propio equipo)."""
        ttk.Label(grid, text=icon, style="Service.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Label(grid, text=label, style="Service.TLabel").grid(
            row=row, column=1, sticky="w", pady=3
        )
        self._link(grid, url).grid(row=row, column=2, sticky="e", padx=(20, 0), pady=3)

    def _set_access_value(self, frame: ttk.Frame, url: str | None, dim: str) -> None:
        """Pinta la columna de valor: enlace si hay URL, texto apagado si no."""
        for child in frame.winfo_children():
            child.destroy()
        if url is None:
            ttk.Label(frame, text=dim, style="DimCard.TLabel").pack(anchor="e")
            return
        self._link(frame, url).pack(anchor="e")

    def _refresh_access(self) -> None:
        """Reescribe LAN y mDNS según el modo vigente (sin reconstruir el panel)."""
        expuesta = lan_mode()
        self._set_access_value(
            self._lan_value,
            lan_url() if expuesta else None,
            "desactivada (solo este equipo)",
        )
        # `mdns_available()` resuelve un nombre: solo se consulta si la fila
        # puede ofrecer algo.
        if not expuesta:
            self._set_access_value(self._mdns_value, None, "—")
        elif mdns_available():
            self._set_access_value(self._mdns_value, local_url(), "")
        else:
            self._set_access_value(self._mdns_value, None, "no resuelve, usa la IP")

        self._lan_toggle.configure(
            text="Desactivar red local" if expuesta else "Activar red local"
        )
        if expuesta:
            self._access_note.configure(
                text=(
                    "🔓 Red local activa: cualquiera en esta red puede abrir la app "
                    "y ver los perfiles (todavía no hay contraseñas). Primera "
                    "conexión desde un móvil: instala/confía el certificado local "
                    "(Ayuda → Conectar un dispositivo)."
                )
            )
        else:
            self._access_note.configure(
                text=(
                    "🔒 La red local está desactivada: la app solo responde en este "
                    "equipo. Actívala para usarla desde el móvil y abre el puerto "
                    "con launcher\\allow-firewall.ps1."
                )
            )

    def toggle_lan_mode(self) -> None:
        """Activa/desactiva el acceso desde la red local y lo aplica reiniciando.

        El modo lo lee el **proceso del backend** de su entorno
        (`core.backend_env`), así que cambiar la variable aquí no basta: hay que
        volver a arrancarlo para que uvicorn se enlace a la interfaz nueva. Con la
        app parada el modo queda declarado y se aplica al arrancar.

        V3.75.3: el cambio se **persiste en el acto** (`config.json`), no al
        cerrar la ventana: es una preferencia de red y no debería depender de que
        el launcher se cierre bien. Se relee `lan_mode()` para guardar lo que de
        verdad quedó declarado, no lo que se creía declarar.
        """
        if self._action_running:
            return
        # V3.75.3: invertir, declarar y persistir es una sola operación de `core`
        # (con test sin pantalla); aquí solo se repinta el panel de acceso.
        toggle_lan_config(self._config)
        self._refresh_access()

        en_marcha = self.pm.backend_running() or fetch_health() is not None
        if not en_marcha:
            self._msg.set(
                "Modo de red guardado: se aplicará al arrancar la app."
                if lan_mode()
                else "Red local desactivada: se aplicará al arrancar la app."
            )
            return
        self.restart()

    def _link(self, parent: tk.Misc, url: str) -> ttk.Label:
        """Etiqueta de enlace clicable que abre la URL en el navegador."""
        lbl = ttk.Label(parent, text=url, style="Link.TLabel", cursor="hand2")
        lbl.bind("<Button-1>", lambda e: webbrowser.open(url))
        return lbl

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
        self._db_file_var = tk.StringVar(value="")
        self._db_file_label = ttk.Label(
            body,
            textvariable=self._db_file_var,
            style="DimCard.TLabel",
            wraplength=COLUMN_W - 30,
        )
        self._db_file_label.pack(anchor="w", fill="x", pady=(6, 0))

    def _build_profiles(self, parent: tk.Misc) -> None:
        """Perfiles (V3.77): solicitudes que resolver y perfiles que gestionar.

        Es la mitad visible de la decisión de producto: **el webmaster no es un rol
        de la app, es quien ejecuta este launcher**. Aquí están las cuatro cosas que
        solo él puede hacer: resolver solicitudes, crear un perfil, desactivarlo o
        reactivarlo, y purgarlo.

        Todo lo que escribe pasa por `admin.py` (HTTP con el PIN), nunca por la BD
        directamente, aunque el launcher tenga el fichero a mano: el borrado tiene
        que pasar por el mismo sitio que el resto (validación, copia previa, tabla
        de solicitudes) o habría dos definiciones de «purgar» y la de aquí sería la
        que nadie prueba.
        """
        sec = self._section(parent, "Perfiles")

        # --- Candado: el PIN de administración ---
        pin_box = ttk.Frame(sec.body, style="Card.TFrame")
        pin_box.pack(fill="x", padx=14, pady=(4, 0))
        self._admin_state_var = tk.StringVar(
            value=admin_state_label(bool(admin_pin(self._config)))
        )
        self._admin_state_label = ttk.Label(
            pin_box,
            textvariable=self._admin_state_var,
            style="Service.TLabel",
            wraplength=COLUMN_W - 30,
        )
        self._admin_state_label.pack(anchor="w")

        pin_row = ttk.Frame(sec.body, style="Card.TFrame")
        pin_row.pack(fill="x", padx=14, pady=(6, 0))
        self._admin_pin_var = tk.StringVar(value="")
        self._admin_pin_entry = ttk.Entry(
            pin_row, textvariable=self._admin_pin_var, show="•", width=24
        )
        self._admin_pin_entry.pack(side="left")
        self._admin_pin_entry.bind("<Return>", lambda _e: self.save_admin_pin())
        ttk.Button(
            pin_row,
            text="💾 Guardar PIN",
            style="Ghost.TButton",
            command=self.save_admin_pin,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            pin_row,
            text="🎲 Generar",
            style="Ghost.TButton",
            command=self.generate_admin_pin_value,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            pin_row,
            text="🧹 Retirar",
            style="Ghost.TButton",
            command=self.clear_admin_pin,
        ).pack(side="left", padx=(6, 0))

        # --- Solicitudes pendientes ---
        self._pending_var = tk.StringVar(value="Solicitudes: …")
        ttk.Label(
            sec.body, textvariable=self._pending_var, style="Service.TLabel"
        ).pack(anchor="w", padx=14, pady=(10, 0))

        pending_wrap = ttk.Frame(sec.body, style="Card.TFrame")
        pending_wrap.pack(fill="both", expand=True, padx=14, pady=(4, 0))
        self._pending_tree = ttk.Treeview(
            pending_wrap, columns=("kind", "who", "when"), show="headings", height=4
        )
        for column, title, width, anchor in (
            ("kind", "Tipo", 90, "w"),
            ("who", "Perfil", 250, "w"),
            ("when", "Llegó", 130, "e"),
        ):
            self._pending_tree.heading(column, text=title)
            self._pending_tree.column(column, width=width, anchor=anchor)
        self._pending_tree.pack(fill="both", expand=True)

        decision_row = ttk.Frame(sec.body, style="Card.TFrame")
        decision_row.pack(fill="x", padx=14, pady=(6, 0))
        ttk.Button(
            decision_row,
            text="✅ Aprobar",
            style="Success.TButton",
            command=self.approve_selected_request,
        ).pack(side="left")
        ttk.Button(
            decision_row,
            text="🚫 Rechazar",
            style="Ghost.TButton",
            command=self.reject_selected_request,
        ).pack(side="left", padx=(6, 0))

        # --- Perfiles existentes ---
        ttk.Label(
            sec.body, text="Perfiles", style="Service.TLabel"
        ).pack(anchor="w", padx=14, pady=(12, 0))
        profiles_wrap = ttk.Frame(sec.body, style="Card.TFrame")
        profiles_wrap.pack(fill="both", expand=True, padx=14, pady=(4, 0))
        self._profiles_tree = ttk.Treeview(
            profiles_wrap,
            columns=("name", "status", "pin", "created"),
            show="headings",
            height=6,
        )
        for column, title, width, anchor in (
            ("name", "Nombre", 190, "w"),
            ("status", "Estado", 100, "w"),
            ("pin", "Credencial", 90, "w"),
            ("created", "Creado", 120, "e"),
        ):
            self._profiles_tree.heading(column, text=title)
            self._profiles_tree.column(column, width=width, anchor=anchor)
        self._profiles_tree.pack(fill="both", expand=True)

        profile_row_buttons = ttk.Frame(sec.body, style="Card.TFrame")
        profile_row_buttons.pack(fill="x", padx=14, pady=(6, 0))
        ttk.Button(
            profile_row_buttons,
            text="➕ Crear…",
            style="Ghost.TButton",
            command=self.create_profile_dialog,
        ).pack(side="left")
        ttk.Button(
            profile_row_buttons,
            text="⏸️ Desactivar / ▶️ Reactivar",
            style="Ghost.TButton",
            command=self.toggle_profile_status,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            profile_row_buttons,
            text="🗑️ Purgar…",
            style="Danger.TButton",
            command=self.purge_selected_profile,
        ).pack(side="left", padx=(6, 0))

        self._profiles_note_var = tk.StringVar(
            value=(
                "Purgar es irreversible: se lleva toda la evidencia del perfil. "
                "Se toma una copia de seguridad antes de borrar."
            )
        )
        ttk.Label(
            sec.body,
            textvariable=self._profiles_note_var,
            style="DimCard.TLabel",
            wraplength=COLUMN_W - 30,
        ).pack(anchor="w", fill="x", padx=14, pady=(6, 12))

    # --- Perfiles: candado de administración (V3.77) ---
    def _refresh_admin_state(self) -> None:
        self._admin_state_var.set(admin_state_label(bool(admin_pin(self._config))))
        activated = bool(admin_pin(self._config))
        self._admin_state_label.configure(
            foreground=COLORS["success"] if activated else COLORS["warning"]
        )

    def save_admin_pin(self) -> None:
        """Guarda el PIN del campo (o retira la administración si está vacío)."""
        pin = self._admin_pin_var.get().strip()
        if pin == "":
            self.clear_admin_pin()
            return
        if set_admin_pin(pin, self._config) is None:
            self._msg.set(
                "El PIN de administración debe tener entre 6 y 64 caracteres y no "
                "llevar espacios en los extremos."
            )
            return
        self._admin_pin_var.set("")
        self._refresh_admin_state()
        self._msg.set(
            "PIN de administración guardado. Reinicia el servidor para que el "
            "backend lo aplique."
        )
        self.refresh()

    def generate_admin_pin_value(self) -> None:
        """Rellena el campo con un PIN aleatorio (lo guarda quien lo confirme)."""
        self._admin_pin_var.set(generate_admin_pin())
        self._msg.set("PIN generado. Pulsa «Guardar PIN» y apunta el valor.")

    def clear_admin_pin(self) -> None:
        """Retira la administración (vuelve a estar deshabilitada, no abierta)."""
        if not messagebox.askyesno(
            "Retirar el PIN de administración",
            "Sin PIN, la administración de perfiles queda DESHABILITADA (fallar "
            "cerrado): no podrás crear, desactivar ni borrar perfiles hasta que "
            "pongas otro.\n\n¿Retirar el PIN?",
            parent=self.root,
        ):
            return
        set_admin_pin("", self._config)
        self._admin_pin_var.set("")
        self._refresh_admin_state()
        self._msg.set("Administración deshabilitada (sin PIN).")
        self.refresh()

    # --- Perfiles: lectura ---
    def _poll_profiles(self) -> None:
        """Refresco periódico de la cola de solicitudes, sin bloquear la ventana."""
        self._load_profiles()
        self.root.after(PROFILES_MS, self._poll_profiles)

    def _load_profiles(self) -> None:
        if self._profiles_busy:
            return
        self._profiles_busy = True
        pin = admin_pin(self._config)

        def work() -> None:
            # Sin PIN no se llama al backend: la administración está deshabilitada
            # y pedirla solo generaría un 401 cada quince segundos.
            if not pin:
                self._queue.put(("profiles", (None, None, None)))
                return
            pending = pending_requests(pin)
            profiles = list_profiles(pin)
            self._queue.put(("profiles", (pending, profiles, None)))

        threading.Thread(target=work, daemon=True).start()

    def _run_admin_action(self, call, success_message) -> None:
        """Ejecuta una acción admin en un hilo y refresca la sección al terminar."""
        if self._profiles_busy:
            return
        self._profiles_busy = True
        pin = admin_pin(self._config)

        def work() -> None:
            if not pin:
                self._queue.put(
                    ("admin_msg", ("Define un PIN de administración primero."))
                )
                return
            result = call(pin)
            message = success_message if result.ok else result.message()
            if result.ok:
                # Tras escribir, se relee: el contador y las filas tienen que
                # reflejar el estado del backend, no lo que creíamos que iba a pasar.
                pending = pending_requests(pin)
                profiles = list_profiles(pin)
                self._queue.put(("profiles", (pending, profiles, message)))
            else:
                self._queue.put(("admin_msg", (message,)))
                # La lista puede haberse quedado vieja (p. ej. si la solicitud ya
                # estaba resuelta desde otro sitio): se relee igual.
                self._queue.put(
                    (
                        "profiles",
                        (pending_requests(pin), list_profiles(pin), None),
                    )
                )

        threading.Thread(target=work, daemon=True).start()

    def _apply_profiles(self, pending, profiles, message) -> None:
        """Pinta la sección «Perfiles» (hilo principal)."""
        self._profiles_busy = False

        if pending is None or profiles is None:
            self._pending_var.set(
                pending_summary(0) if pending is None else ""
            )
            if pending is None and profiles is None:
                self._pending_var.set("Solicitudes: administración deshabilitada")
            self._pending_rows = []
            self._profile_rows = []
            self._pending_tree.delete(*self._pending_tree.get_children())
            self._profiles_tree.delete(*self._profiles_tree.get_children())
            if message:
                self._msg.set(str(message))
            return

        # Las bajas guardan el `user_id`: se traduce a nombre con los perfiles ya
        # cargados para que la cola se pueda leer sin descifrar identificadores.
        names = {
            str(u.get("id")): str(u.get("name")) for u in profiles.data.get("users", [])
        }
        self._pending_rows = list(pending.data.get("requests", []))
        self._profile_rows = list(profiles.data.get("users", []))

        self._pending_tree.delete(*self._pending_tree.get_children())
        for request in self._pending_rows:
            self._pending_tree.insert("", "end", values=request_row(request, names))

        self._profiles_tree.delete(*self._profiles_tree.get_children())
        for profile in self._profile_rows:
            self._profiles_tree.insert("", "end", values=profile_row(profile))

        self._pending_var.set(pending_summary(int(pending.data.get("pending", 0))))
        if message:
            self._msg.set(str(message))

    def _selected_pending(self) -> dict | None:
        selection = self._pending_tree.selection()
        if not selection:
            self._msg.set("Selecciona una solicitud de la lista.")
            return None
        index = self._pending_tree.index(selection[0])
        return self._pending_rows[index] if index < len(self._pending_rows) else None

    def _selected_profile(self) -> dict | None:
        selection = self._profiles_tree.selection()
        if not selection:
            self._msg.set("Selecciona un perfil de la lista.")
            return None
        index = self._profiles_tree.index(selection[0])
        return self._profile_rows[index] if index < len(self._profile_rows) else None

    # --- Perfiles: acciones ---
    def approve_selected_request(self) -> None:
        request = self._selected_pending()
        if request is None:
            return
        request_id = int(request["id"])
        if request.get("kind") == "delete":
            nombre = next(
                (
                    str(u.get("name"))
                    for u in self._profile_rows
                    if str(u.get("id")) == str(request.get("user_id"))
                ),
                "(perfil ya inexistente)",
            )
            if not messagebox.askyesno(
                "Aprobar la baja",
                f"Se DESACTIVARÁ el perfil «{nombre}»: dejará de aparecer y no "
                "podrá abrir sesión, pero su evidencia se conserva y se puede "
                "reactivar.\n\nPara borrarla de verdad hay que purgar el perfil, "
                "que es un paso aparte.\n\n¿Aprobar la baja?",
                parent=self.root,
            ):
                return
        self._run_admin_action(
            lambda pin: approve_request(pin, request_id),
            "Solicitud aprobada.",
        )

    def reject_selected_request(self) -> None:
        request = self._selected_pending()
        if request is None:
            return
        request_id = int(request["id"])
        note = simpledialog.askstring(
            "Rechazar la solicitud",
            "Motivo (opcional, se guarda con la solicitud):",
            parent=self.root,
        )
        if note is None:
            return
        self._run_admin_action(
            lambda pin: reject_request(pin, request_id, note=note),
            "Solicitud rechazada.",
        )

    def create_profile_dialog(self) -> None:
        name = simpledialog.askstring(
            "Crear un perfil", "Nombre del perfil:", parent=self.root
        )
        if not name or not name.strip():
            return
        pin = simpledialog.askstring(
            "PIN del perfil (opcional)",
            "PIN de 4-6 dígitos para que el perfil pida credencial al entrar.\n"
            "Déjalo vacío si no quieres PIN:",
            parent=self.root,
        )
        if pin is None:
            return
        self._run_admin_action(
            lambda configured: create_profile(
                configured, name.strip(), profile_pin=pin.strip()
            ),
            f"Perfil «{name.strip()}» creado.",
        )

    def toggle_profile_status(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        user_id = str(profile["id"])
        if str(profile.get("status")) == "active":
            if not messagebox.askyesno(
                "Desactivar el perfil",
                f"«{profile.get('name')}» saldrá del selector y no podrá abrir "
                "sesión. Su evidencia se conserva y puedes reactivarlo cuando "
                "quieras.\n\n¿Desactivar?",
                parent=self.root,
            ):
                return
            target = "disabled"
            message = f"Perfil «{profile.get('name')}» desactivado."
        else:
            target = "active"
            message = f"Perfil «{profile.get('name')}» reactivado."
        self._run_admin_action(
            lambda pin: set_profile_status(pin, user_id, target),
            message,
        )

    def purge_selected_profile(self) -> None:
        """Purga irreversible: confirmación por nombre + copia que hace el backend."""
        profile = self._selected_profile()
        if profile is None:
            return
        user_id = str(profile["id"])
        name = str(profile.get("name") or "")
        if str(profile.get("status")) == "active":
            messagebox.showinfo(
                "Desactiva antes de purgar",
                "Purgar se lleva toda la evidencia del perfil. Desactívalo primero "
                "y comprueba que nadie lo echa de menos; después, purga.",
                parent=self.root,
            )
            return
        typed = simpledialog.askstring(
            "Purgar el perfil",
            f"Esto borra «{name}» y TODA su evidencia (progreso, mastery, "
            "conversaciones, grabaciones). Es irreversible.\n\nEl backend tomará "
            "una copia de seguridad antes de borrar.\n\nEscribe el nombre exacto "
            "del perfil para confirmar:",
            parent=self.root,
        )
        if typed is None or typed.strip() != name:
            if typed is not None:
                self._msg.set("El nombre no coincide: no se ha purgado nada.")
            return
        self._run_admin_action(
            lambda pin: purge_profile(pin, user_id, name),
            f"Perfil «{name}» purgado (con copia de seguridad previa).",
        )

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
        self._session_var = tk.StringVar(value="")
        self._session_label = ttk.Label(
            wrap, textvariable=self._session_var, style="Status.TLabel"
        )
        self._session_label.pack(anchor="w", pady=(4, 0))
        self._cookie_diag_var = tk.StringVar(value="")
        self._cookie_diag_label = ttk.Label(
            wrap,
            textvariable=self._cookie_diag_var,
            style="DimCard.TLabel",
            justify="left",
            wraplength=COLUMN_W - 30,
        )
        self._cookie_diag_label.pack(anchor="w", fill="x", pady=(4, 0))
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
                wrap="char",
                height=14,
                bg=COLORS["surface"],
                fg=COLORS["text"],
                relief="flat",
                # Terminal compacta: fuente mono pequeña e interlineado mínimo
                # para que backend.log/frontend.log se lean densos (V3.7.0).
                font=("Consolas", 8),
                spacing1=0,
                spacing2=0,
                spacing3=0,
                padx=2,
                pady=1,
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
        elif kind == "profiles":
            # V3.77: resultado de una lectura/acción de la sección «Perfiles».
            self._apply_profiles(*item[1])
        elif kind == "admin_msg":
            # Solo el mensaje: lo usa el guardado del PIN, que no cambia datos del
            # backend y por tanto no necesita volver a pedir la lista.
            self._profiles_busy = False
            self._msg.set(str(item[1]))
        elif kind == "error":
            self._action_running = False
            self._stop_spinner()
            self._status.set("Error")
            self._status_dot.set(status_dot("error"))
            self._status_label.configure(foreground=COLORS["error"])
            self._msg.set(f"Error: {item[1]}")
            self._busy = False
        elif kind == "started":
            self._action_running = False
            if item[1]:
                webbrowser.open(frontend_url())
            self.refresh()
        elif kind == "stopped":
            self._action_running = False
            self.refresh()
        elif kind == "prepared":
            self._msg.set(str(item[1]))
        elif kind == "open_app":
            servida, dist_available = item[1]
            if servida:
                webbrowser.open(frontend_url())
                self._msg.set("Abriendo app…")
            elif dist_available:
                # V3.75.3: compilada pero sin responder no es «sin compilar».
                self._msg.set(
                    "La interfaz está compilada pero no responde. Pulsa "
                    "'Iniciar app' para arrancarla."
                )
                self.refresh()
            else:
                self._msg.set(
                    "La interfaz no está compilada. Pulsa 'Iniciar app' para "
                    "compilarla y arrancarla."
                )
                self.refresh()

    def _next_refresh(self) -> None:
        self._busy = False
        self.refresh()

    # --- Indicador de actividad (reloj animado) ---
    def _start_spinner(self, text: str) -> None:
        """Arranca el reloj animado y un mensaje de estado en la cabecera."""
        self._stop_spinner()
        self._spinner_idx = 0
        self._status.set(text)
        self._status_label.configure(foreground=COLORS["warning"])
        self._animate_spinner()

    def _animate_spinner(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER_CHARS)
        self._status_dot.set(SPINNER_CHARS[self._spinner_idx])
        self._spinner_id = self.root.after(SPINNER_MS, self._animate_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner_id is not None:
            try:
                self.root.after_cancel(self._spinner_id)
            except tk.TclError:
                pass
            self._spinner_id = None

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
                server_status = fetch_server_status()
                # V3.75.3: el estado de la interfaz se decide con DOS datos, no
                # uno. «El artefacto no está compilado» y «el origen no responde»
                # son problemas distintos y la GUI no puede confundirlos.
                dist_available = frontend_dist_available()
                counts = read_db_counts(str(DB_PATH))
                details = read_db_details(str(DB_PATH))
                db_info = read_db_info(str(DB_PATH))
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
                        dist_available,
                        version,
                        server_status,
                        counts,
                        details,
                        db_info,
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
        dist_available,
        version,
        server_status,
        counts,
        details,
        db_info,
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
        self._svc_vars["Backend"].set(
            "🟢 Activo" if backend_up else "🔴 Detenido"
        )
        # V3.75.3: la interfaz tiene TRES estados, no dos. `frontend_on` es el
        # resultado de una sonda de red y su `False` significa «el origen no
        # respondió», que puede ser un puerto ocupado, un servidor HTTP en vez de
        # HTTPS o un arranque a medias. Llamarlo «No compilada» mandaba al usuario
        # a compilar algo que ya estaba compilado: el artefacto se comprueba en
        # disco, que es lo que sí sabe si falta.
        self._svc_vars["Interfaz"].set(
            interface_state(frontend_on, dist_available)
        )
        self._svc_vars["Ollama"].set(self._svc_text(svc["ollama"]))
        self._svc_vars["STT"].set(self._svc_text(svc["stt"]))
        self._svc_vars["TTS"].set(self._svc_text(svc["tts"]))
        self._svc_vars["Base de datos"].set(self._svc_text(svc["database"]))

        self._color_service("Backend", "on" if backend_up else "off")
        self._color_service("Interfaz", "on" if frontend_on else "off")
        self._color_service("Ollama", svc["ollama"])
        self._color_service("STT", svc["stt"])
        self._color_service("TTS", svc["tts"])
        self._color_service("Base de datos", svc["database"])

        running = backend_up and frontend_on
        activity_line, rejected = server_activity(server_status)
        generating = bool(
            server_status
            and int((server_status.get("generation") or {}).get("running", 0) or 0)
            > 0
        )
        busy = running and (generating or rejected > 0)
        if not self._action_running:
            self._stop_spinner()
            if running and busy:
                label = "generando…" if generating else "saturado"
                self._status.set(f"En marcha · {label}")
                self._status_dot.set(status_dot("unavailable"))
                self._status_label.configure(foreground=COLORS["warning"])
            else:
                self._status.set("En marcha" if running else "Detenida")
                self._status_dot.set(status_dot("ok" if running else "off"))
                self._status_label.configure(
                    foreground=COLORS["success"] if running else COLORS["error"]
                )
        self._version.set(f"v{version}" if version else "Launcher de escritorio")
        self._apply_action_buttons(running)

        # Sección «Actividad del servidor» (V3.6.2): qué hace el backend ahora.
        if running:
            self._activity_var.set(activity_line)
            self._activity_label.configure(
                foreground=(
                    COLORS["warning"] if busy else COLORS["success"]
                )
            )
            self._reject_var.set(
                f"Rechazos por saturación (último minuto): {rejected}"
            )
            self._reject_label.configure(
                foreground=COLORS["warning"] if rejected else COLORS["text_dim"]
            )
        else:
            self._activity_var.set("Detenida")
            self._activity_label.configure(foreground=COLORS["error"])
            self._reject_var.set("")

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
        if not db_info.get("exists"):
            self._db_file_var.set("La base de datos todavía no se ha creado.")
        else:
            self._db_file_var.set(
                f"📁 {db_info['size_human']} · {db_info['tables']} tablas · "
                f"modificada {db_info['modified']}"
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

    def _apply_action_buttons(self, running: bool) -> None:
        """Refleja el estado de la app en los botones (verde/rojo/deshabilitado).

        - Detenida: "Iniciar app" en verde, "Detener"/"Reiniciar"/"Abrir"
          deshabilitados.
        - En marcha: "Detener app" en rojo, "Reiniciar"/"Abrir" habilitados,
          "Iniciar app" deshabilitado.
        """
        if running:
            self._start_btn.configure(style="Ghost.TButton", state="disabled")
            self._stop_btn.configure(style="Danger.TButton", state="normal")
            self._restart_btn.configure(style="Ghost.TButton", state="normal")
            self._open_btn.configure(state="normal")
        else:
            self._start_btn.configure(style="Success.TButton", state="normal")
            self._stop_btn.configure(style="Ghost.TButton", state="disabled")
            self._restart_btn.configure(style="Ghost.TButton", state="disabled")
            self._open_btn.configure(state="disabled")

    def _apply_cookies(self, rows: list[dict], summary: dict) -> None:
        # V3.75: se informa de **si hay sesión**, no de qué perfil es. El perfil va
        # dentro del token firmado y esta pantalla no lo descifra (no debe: el token
        # en claro sería una sesión copiable de la pantalla).
        if summary["session_open"]:
            self._session_label.configure(foreground=COLORS["success"])
            self._session_var.set("🔑 Sesión abierta en el navegador")
        else:
            self._session_label.configure(foreground=COLORS["text_dim"])
            self._session_var.set("🔑 Sin sesión abierta todavía")

        self._cookie_var.set(format_cookie_summary(summary))
        self._cookie_diag_var.set(
            format_cookie_diagnosis(summary.get("diagnosis", []))
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
        """Ajusta el wraplength de detalle y diagnóstico al ancho de su columna."""
        width = self._col_left.winfo_width()
        if width > 60:
            self._db_detail_label.configure(wraplength=width - 30)
            self._db_file_label.configure(wraplength=width - 30)
        rwidth = self._col_right.winfo_width()
        if rwidth > 60:
            self._cookie_diag_label.configure(wraplength=rwidth - 30)

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

    def _svc_text(self, state: str) -> str:
        """Texto de estado de un servicio con su punto de color (🟢/🔴/🟡/⚪)."""
        return f"{status_dot(state)} {self._label(state)}"

    def _color_service(self, name: str, state: str) -> None:
        """Tiñe el texto de estado de un servicio según su estado normalizado."""
        label = self._svc_value_labels.get(name)
        if label is not None:
            label.configure(foreground=status_color(state))

    def start(self) -> None:
        self._action_running = True
        self._msg.set("Arrancando servicios…")
        self._start_spinner("Arrancando…")

        def work() -> None:
            try:
                preparado = False
                log_offset = 0
                with self._lock:
                    # No duplicar un servicio ya activo (p. ej. lanzado con F5).
                    backend_up = fetch_health() is not None
                    if not self.pm.backend_running() and not backend_up:
                        # V3.75.3: si el puerto responde pero la sonda HTTPS no,
                        # lo que hay ahí es otro proceso. Se comprueba ANTES de
                        # preparar nada: fallar rápido es mejor que compilar la UI
                        # para morir contra el puerto ocupado.
                        self.pm.ensure_port_free()
                        self.pm.prepare()
                        preparado = True
                        log_offset = self.pm.backend_log_size()
                        self.pm.start_backend()
                if preparado:
                    self._queue.put(
                        ("prepared", "Certificado y UI listos; arrancando…")
                    )
                    # V3.75.3: se comprueba que el producto LLEGA a servir, en vez
                    # de dar por bueno el arranque por haber lanzado el proceso.
                    motivo = self._wait_product(log_offset)
                    if motivo:
                        self._queue.put(("error", motivo))
                        return
                time.sleep(BROWSER_DELAY_S)
                self._queue.put(("started", fetch_frontend()))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def stop(self) -> None:
        self._action_running = True
        self._msg.set("Deteniendo servicios…")
        self._start_spinner("Deteniendo…")

        def work() -> None:
            try:
                with self._lock:
                    self.pm.stop_all()
                self._queue.put(("stopped", None))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def restart(self) -> None:
        self._action_running = True
        self._msg.set("Reiniciando servicios…")
        self._start_spinner("Reiniciando…")

        def work() -> None:
            try:
                log_offset = 0
                with self._lock:
                    self.pm.stop_all()
                    self._wait_ports_free()
                    # Evita duplicar un servicio ya activo (p. ej. lanzado con F5).
                    backend_up = fetch_health() is not None
                    if not self.pm.backend_running() and not backend_up:
                        self.pm.ensure_port_free()
                        self.pm.prepare()
                        log_offset = self.pm.backend_log_size()
                        self.pm.start_backend()
                motivo = self._wait_product(log_offset)
                if motivo:
                    self._queue.put(("error", motivo))
                    return
                time.sleep(BROWSER_DELAY_S)
                self._queue.put(("started", fetch_frontend()))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _wait_product(self, offset: int, timeout: float = 20.0) -> str | None:
        """Espera a que el producto sirva la UI. Devuelve el motivo si no lo hace.

        V3.75.3: antes se dormían 2 s fijos y se daba el arranque por hecho, así
        que un backend que moría (certificado ilegible, dependencia que falta,
        puerto que se ocupó entre la comprobación y el *bind*) dejaba la GUI en
        «🔴 Detenido» sin explicación. El motivo ya estaba en `logs/backend.log`;
        ahora se lee y se muestra.

        Si el proceso muere se sale enseguida (no tiene sentido esperar); si sigue
        vivo pero no sirve, se agota el plazo. ``offset`` es el tamaño del log
        antes de arrancar, para no atribuir a este arranque un fallo anterior.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if fetch_frontend():
                return None
            if self.pm.backend is not None and not self.pm.backend_running():
                break
            time.sleep(0.3)
        if self.pm.backend is None or not self.pm.backend_running():
            base = "El backend se cerró al arrancar."
        else:
            base = "El backend arrancó pero no llegó a servir la interfaz."
        motivo = backend_failure_hint(self.pm.backend_log_since(offset))
        if motivo:
            return f"{base} {motivo}"
        return f"{base} Revisa el registro del backend en el launcher."

    @staticmethod
    def _wait_ports_free(timeout: float = 15.0) -> None:
        """Espera a que el proceso de producto libere su puerto tras parar.

        V3.75.3: se espera al **socket**, no a las sondas HTTP. Las sondas
        (`fetch_health`, `fetch_frontend`) son HTTPS y contra un servidor HTTP en
        el mismo puerto devuelven «no hay nada», así que daban por libre un puerto
        que seguía ocupado y el reinicio chocaba después.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not port_in_use():
                return
            time.sleep(0.3)

    def open_app(self) -> None:
        def work() -> None:
            self._queue.put(
                ("open_app", (fetch_frontend(), frontend_dist_available()))
            )

        threading.Thread(target=work, daemon=True).start()


def main() -> None:
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
