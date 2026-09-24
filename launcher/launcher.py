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
    create_user,
    edit_user,
    force_unenroll,
    pending_requests,
    purge_user,
    reject_request,
    resend_activation,
    set_credentials,
    set_user_status,
    smtp_config,
    test_smtp,
    user_history,
    verify_email,
)
from admin import (
    list_users as list_admin_users,
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
    apply_smtp_config,
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
    mail_secret,
    mdns_available,
    port_in_use,
    set_admin_pin,
    set_smtp_settings,
    smtp_settings,
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
    read_pending_requests,
    read_users,
)
from ui import (
    ACTION_ICONS,
    COLORS,
    LOG_DIR,
    SECTION_ICONS,
    SERVICE_ICONS,
    TAB_ICONS,
    TAB_ORDER,
    accounts_tasks,
    admin_state_label,
    backend_failure_hint,
    centered_position,
    clamp_window_size,
    duplicate_user_ids,
    event_row,
    interface_state,
    invitation_copy_text,
    invitation_message,
    pending_view,
    purge_block_reason,
    read_log_tail,
    server_activity,
    smtp_reconcile_label,
    smtp_state_label,
    status_color,
    status_dot,
    statusbar_right,
    user_row,
    user_row_label,
    window_position_visible,
)
from widgets import ScrollableFrame, attach_scrollbars, enable_mousewheel_scrolling

REFRESH_MS = 2000
POLL_MS = 100
# V3.77: cada cuánto se pregunta al backend si han llegado solicitudes de alta/baja.
# Es un solo GET y es lo que hace que «la solicitud llegue al webmaster» de
# verdad: sin esto habría que pulsar «Actualizar» para enterarse. Más lento que
# el refresco general a propósito —una cola de solicitudes no cambia cada dos
# segundos— y lo bastante vivo para que el contador no se quede viejo mientras
# alguien la mira.
ACCOUNTS_MS = 15000
BROWSER_DELAY_S = 2.0

# Reloj animado mostrado en la cabecera mientras se arranca/para/reinicia.
SPINNER_CHARS = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"]
SPINNER_MS = 120

# Tamaño por defecto de la ventana y posición inicial del divisor entre columnas.
# Ambos se redimensionan y se persisten al cerrar (ver state_store.py).
WINDOW_W = 1160
WINDOW_H = 800
COLUMN_W = 540
# Mínimo viable de la ventana: por debajo, las pestañas y las tablas dejan de
# ser legibles. La geometría restaurada se acota también contra la pantalla
# (`_clamp_size`), porque `state.json` puede venir de un monitor más alto.
MIN_W = 900
MIN_H = 620

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
        # V3.81: los ajustes SMTP guardados viajan al backend por el mismo canal
        # (mismo patrón, mismo motivo). La contraseña **no** viene de aquí: vive en
        # `data/mail.secret`, que el backend lee por su cuenta.
        apply_smtp_config(self._config)
        self._sections_map: dict[str, Collapsible] = {}
        self._spinner_id: str | None = None
        self._spinner_idx = 0
        self._action_running = False
        # Estado de la consola «Usuarios»: lo que hay pintado (para saber sobre qué
        # fila actúa un botón) y lo que vamos a pedirle al backend.
        self._pending_rows: list[dict] = []
        self._user_rows: list[dict] = []
        self._admin_busy = False
        # V3.81.3: qué pestaña está abierta (manda en la barra de estado y se
        # persiste), cuándo fue la última comprobación y si la barra de
        # herramientas se ve. Se leen del estado guardado antes de construir nada.
        self._current_tab_name = str(self._state.get("tab") or TAB_ORDER[0])
        self._checked_at = ""
        self._tab_var = tk.StringVar(value=self._current_tab_name)
        self._toolbar_visible = tk.BooleanVar(
            value=bool(self._state.get("toolbar", True))
        )
        self._tabs: dict[str, tk.Misc] = {}
        root.title("English Tutor — Gestión de la APP")
        # La ventana es redimensionable; el tamaño y la posición se restauran del
        # estado persistido (state.json) y se guardan al cerrar.
        root.resizable(True, True)
        root.minsize(MIN_W, MIN_H)
        self._apply_window_icon()
        self._build_style()
        self._build_ui()
        self._restore_window()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        # V3.81.3: la rueda del ratón se enruta una sola vez por ventana. Sin
        # esto los canvas con scroll solo respondían arrastrando la barra.
        enable_mousewheel_scrolling(root)
        # Atajos de teclado de los menús (los aceleradores se anuncian ahí).
        root.bind("<F5>", lambda _e: self.refresh())
        root.bind("<Control-o>", lambda _e: self.open_app())
        root.bind("<Control-q>", lambda _e: self._on_close())
        # Programar desde el hilo principal (antes de mainloop es seguro).
        root.after(0, self.refresh)
        root.after(POLL_MS, self._poll_queue)
        # V3.77: la cola de solicitudes se refresca sola (ver `ACCOUNTS_MS`).
        root.after(ACCOUNTS_MS, self._poll_accounts)

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
        """Cáscara de la app: menús, barra de herramientas, pestañas y estado.

        El orden de empaquetado no es libre: la barra de estado se ancla abajo
        **antes** de que el cuaderno central (que expande) ocupe el resto; si se
        empaquetara después, quedaría fuera de la ventana y no se vería —que es
        justo el síntoma que esta reorganización corrige—.
        """
        self._msg = tk.StringVar(value="")
        self._status = tk.StringVar(value="Comprobando…")
        self._status_dot = tk.StringVar(value=status_dot("unknown"))
        self._version = tk.StringVar(value="")

        self._build_menubar()
        self._build_toolbar()
        self._build_statusbar()
        self._build_tabs()
        if not self._toolbar_visible.get():
            self._toolbar_frame.pack_forget()

    # --- Barra de menús ---
    def _build_menubar(self) -> None:
        """Barra de menús nativa, sin duplicar lógica: llama a lo que ya existe.

        Cada entrada es un método que ya estaba detrás de un botón. No hay una
        segunda implementación de «purgar» ni de «activar red local» que se pueda
        desincronizar de la de la pantalla.
        """
        menubar = tk.Menu(self.root)

        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="Iniciar app", command=self.start)
        archivo.add_command(label="Detener app", command=self.stop)
        archivo.add_command(label="Reiniciar servidor", command=self.restart)
        archivo.add_separator()
        archivo.add_command(
            label="Abrir app", command=self.open_app, accelerator="Ctrl+O"
        )
        archivo.add_command(label="Actualizar", command=self.refresh, accelerator="F5")
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self._on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="Archivo", menu=archivo)

        ver = tk.Menu(menubar, tearoff=0)
        for name in TAB_ORDER:
            ver.add_radiobutton(
                label=f"{TAB_ICONS.get(name, '')}  {name}".strip(),
                value=name,
                variable=self._tab_var,
                command=lambda n=name: self.show_tab(n),
            )
        ver.add_separator()
        ver.add_command(
            label="Expandir todas las secciones",
            command=lambda: self._set_all_sections(True),
        )
        ver.add_command(
            label="Colapsar todas las secciones",
            command=lambda: self._set_all_sections(False),
        )
        ver.add_separator()
        ver.add_checkbutton(
            label="Mostrar barra de herramientas",
            variable=self._toolbar_visible,
            command=self._toggle_toolbar,
        )
        ver.add_command(label="Restablecer ventana", command=self._reset_window)
        menubar.add_cascade(label="Ver", menu=ver)

        herramientas = tk.Menu(menubar, tearoff=0)
        herramientas.add_command(
            label="Ir al PIN de administración…", command=self.focus_admin_pin
        )
        herramientas.add_command(
            label="Generar PIN aleatorio", command=self.generate_admin_pin_value
        )
        herramientas.add_command(
            label="Retirar PIN de administración…", command=self.clear_admin_pin
        )
        herramientas.add_separator()
        herramientas.add_command(
            label="Configurar correo saliente…", command=self.configure_smtp_dialog
        )
        herramientas.add_separator()
        # La variable se sincroniza en `_refresh_access`: el modo real lo manda
        # `core`, no lo que el menú creía haber marcado.
        self._lan_var = tk.BooleanVar(value=lan_mode())
        herramientas.add_checkbutton(
            label="Permitir el acceso desde la red local (LAN)",
            variable=self._lan_var,
            command=self._toggle_lan_from_menu,
        )
        herramientas.add_separator()
        herramientas.add_command(
            label="Abrir la carpeta de registros", command=self.open_logs_folder
        )
        menubar.add_cascade(label="Herramientas", menu=herramientas)

        usuarios = tk.Menu(menubar, tearoff=0)
        usuarios.add_command(
            label="Ir a Usuarios", command=lambda: self.show_tab("Usuarios")
        )
        usuarios.add_separator()
        usuarios.add_command(label="Crear cuenta…", command=self.create_user_dialog)
        usuarios.add_command(label="Credenciales…", command=self.credentials_dialog)
        usuarios.add_command(
            label="Verificar email", command=self.verify_email_selected
        )
        usuarios.add_command(
            label="Reenviar invitación", command=self.resend_activation_selected
        )
        usuarios.add_command(label="Editar…", command=self.edit_user_dialog)
        usuarios.add_separator()
        usuarios.add_command(label="Reactivar", command=self.reactivate_selected_user)
        usuarios.add_command(label="Desactivar", command=self.deactivate_selected_user)
        usuarios.add_command(
            label="Forzar baja…", command=self.force_unenroll_selected_user
        )
        usuarios.add_command(label="Historial…", command=self.user_history_dialog)
        usuarios.add_separator()
        usuarios.add_command(label="Purgar…", command=self.purge_selected_user)
        menubar.add_cascade(label="Usuarios", menu=usuarios)

        ayuda = tk.Menu(menubar, tearoff=0)
        ayuda.add_command(
            label="Conectar un dispositivo…", command=self.show_device_help
        )
        ayuda.add_separator()
        ayuda.add_command(label="Acerca de English Tutor…", command=self.show_about)
        menubar.add_cascade(label="Ayuda", menu=ayuda)

        self.root.config(menu=menubar)

    # --- Barra de herramientas ---
    def _build_toolbar(self) -> None:
        """Marca compacta + las acciones de siempre, en una franja superior.

        Los botones son los mismos (mismos comandos y estilos), solo cambian de
        sitio: la cabecera grande desaparece porque el estado, la versión y el
        crédito viven ahora en la barra de estado inferior y en «Acerca de».
        """
        container = ttk.Frame(self.root, style="Card.TFrame")
        ttk.Separator(container, style="Card.TSeparator").pack(side="bottom", fill="x")
        bar = ttk.Frame(container, style="Card.TFrame")
        bar.pack(fill="x")

        brand = ttk.Frame(bar, style="Card.TFrame")
        brand.pack(side="left", padx=16, pady=8)
        ttk.Label(brand, text="EN", style="Badge.TLabel").pack(side="left")
        ttk.Label(brand, text="English Tutor", style="Title.TLabel").pack(
            side="left", padx=(10, 0)
        )
        ttk.Separator(bar, orient="vertical", style="Card.TSeparator").pack(
            side="left", fill="y", padx=(0, 4), pady=10
        )

        tools = ttk.Frame(bar, style="Card.TFrame")
        tools.pack(side="left", pady=8)
        self._start_btn = ttk.Button(
            tools,
            text=f"  {ACTION_ICONS['start']}  Iniciar app",
            style="Success.TButton",
            command=self.start,
        )
        self._start_btn.pack(side="left", padx=(10, 0))
        self._stop_btn = ttk.Button(
            tools,
            text=f"  {ACTION_ICONS['stop']}  Detener app",
            style="Ghost.TButton",
            command=self.stop,
        )
        self._stop_btn.pack(side="left", padx=(8, 0))
        self._restart_btn = ttk.Button(
            tools,
            text=f"  {ACTION_ICONS['restart']}  Reiniciar servidor",
            style="Ghost.TButton",
            command=self.restart,
        )
        self._restart_btn.pack(side="left", padx=(8, 0))
        self._open_btn = ttk.Button(
            tools,
            text=f"  {ACTION_ICONS['open']}  Abrir app",
            style="Ghost.TButton",
            command=self.open_app,
        )
        self._open_btn.pack(side="left", padx=(8, 0))
        ttk.Button(
            tools,
            text=f"  {ACTION_ICONS['refresh']}  Actualizar",
            style="Ghost.TButton",
            command=self.refresh,
        ).pack(side="left", padx=(8, 0))

        container.pack(fill="x")
        self._toolbar_frame = container

    # --- Barra de estado ---
    def _build_statusbar(self) -> None:
        """Barra inferior: punto y estado, mensaje, versión, red/PIN y frescura.

        Se empaqueta antes que el cuaderno central a propósito (ver `_build_ui`).
        """
        container = ttk.Frame(self.root, style="Card.TFrame")
        ttk.Separator(container, style="Card.TSeparator").pack(side="top", fill="x")
        row = ttk.Frame(container, style="Card.TFrame")
        row.pack(fill="x")
        row.columnconfigure(2, weight=1)

        self._status_dot_label = ttk.Label(
            row, textvariable=self._status_dot, style="Card.TLabel"
        )
        self._status_dot_label.grid(row=0, column=0, padx=(12, 4), pady=5, sticky="w")
        self._status_label = ttk.Label(
            row, textvariable=self._status, style="Status.TLabel"
        )
        self._status_label.grid(row=0, column=1, pady=5, sticky="w")
        self._msg_label = ttk.Label(
            row, textvariable=self._msg, style="DimCard.TLabel", anchor="w"
        )
        self._msg_label.grid(row=0, column=2, padx=16, pady=5, sticky="ew")
        self._status_right = tk.StringVar(value="")
        self._status_right_label = ttk.Label(
            row, textvariable=self._status_right, style="DimCard.TLabel"
        )
        self._status_right_label.grid(row=0, column=3, padx=(0, 12), pady=5, sticky="e")

        container.pack(fill="x", side="bottom")
        self._statusbar_frame = container
        self._refresh_status_right()

    # --- Área central: pestañas ---
    def _build_tabs(self) -> None:
        """Reparte lo que antes vivían en dos columnas largas.

        Cada pestaña lleva su propio scroll, así que el contenido alto (la consola
        de Usuarios, sobre todo) se recorre con la rueda sin depender del tamaño
        de la ventana. «Registros» no lleva scroll propio: los `Text` de los logs
        ya tienen el suyo y deben ocupar todo el alto disponible.
        """
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)
        self._notebook = nb

        estado = self._add_tab(nb, "Estado")
        self._build_services(estado)
        self._build_activity(estado)
        self._build_access(estado)
        self._build_database(estado)

        usuarios = self._add_tab(nb, "Usuarios")
        # V3.81: «Usuarios» es la **consola de gestión** y va arriba porque es donde
        # el webmaster tiene algo que hacer; «Actividad por usuario» es el recuento
        # de lo que hay, leído de la BD sin depender del backend.
        self._build_users(usuarios)
        self._build_user_activity(usuarios)

        diagnostico = self._add_tab(nb, "Diagnóstico")
        self._build_cookies(diagnostico)

        registros = self._add_tab(nb, "Registros", scroll=False)
        self._build_logs(registros)

        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _add_tab(self, nb: ttk.Notebook, title: str, *, scroll: bool = True) -> tk.Misc:
        """Crea una pestaña y devuelve dónde empaquetar su contenido.

        Con scroll devuelve el **cuerpo** del `ScrollableFrame` (lo que se
        desplaza) y lo engancha al recálculo del wraplength; sin scroll devuelve
        la propia pestaña, que se estira para llenar el hueco.
        """
        icon = TAB_ICONS.get(title, "")
        frame: tk.Misc
        if scroll:
            frame = ScrollableFrame(nb)
            body: tk.Misc = frame.body
            body.bind("<Configure>", lambda _e: self._update_detail_wrap(), add="+")
        else:
            frame = ttk.Frame(nb, style="TFrame")
            body = frame
        nb.add(frame, text=f"  {icon}  {title}  ")
        self._tabs[title] = frame
        return body

    @staticmethod
    def _tab_body(frame: tk.Misc) -> tk.Misc:
        """Cuerpo empaquetable de una pestaña (el del `ScrollableFrame`, si lo es)."""
        return getattr(frame, "body", frame)

    def _tab_name(self) -> str:
        """Nombre de la pestaña activa, según el orden real de `TAB_ORDER`."""
        try:
            index = self._notebook.index(self._notebook.select())
        except (tk.TclError, AttributeError):
            return self._current_tab_name
        if 0 <= index < len(TAB_ORDER):
            return TAB_ORDER[index]
        return self._current_tab_name

    def show_tab(self, name: str) -> None:
        """Abre una pestaña por su nombre (menú Ver y «Ir a Usuarios»)."""
        if name not in TAB_ORDER:
            return
        try:
            self._notebook.select(TAB_ORDER.index(name))
        except (tk.TclError, AttributeError):
            return
        self._current_tab_name = name
        self._tab_var.set(name)
        self._update_detail_wrap()

    def _on_tab_changed(self, _event: object = None) -> None:
        """Cambio de pestaña: actualiza el nombre, la barra de estado y el wrap."""
        self._current_tab_name = self._tab_name()
        self._tab_var.set(self._current_tab_name)
        self._refresh_status_right()
        self._update_detail_wrap()

    def _refresh_status_right(self) -> None:
        """Repinta el extremo derecho de la barra de estado."""
        if not hasattr(self, "_status_right"):
            return
        self._status_right.set(
            statusbar_right(
                version=self._version.get(),
                lan=lan_mode(),
                pin_set=bool(admin_pin(self._config)),
                tab=self._current_tab_name,
                checked_at=self._checked_at,
            )
        )

    def _toggle_toolbar(self) -> None:
        """Muestra u oculta la barra de herramientas (menú Ver)."""
        if self._toolbar_visible.get():
            self._toolbar_frame.pack(fill="x", before=self._notebook)
        else:
            self._toolbar_frame.pack_forget()

    def _set_all_sections(self, expanded: bool) -> None:
        """Expande o colapsa todas las secciones desplegables (menú Ver)."""
        for section in self._sections_map.values():
            if section.is_expanded() != expanded:
                section.toggle()

    # --- Menús: acciones de apoyo ---
    def focus_admin_pin(self) -> None:
        """Lleva al campo del PIN de administración (pestaña Usuarios)."""
        self.show_tab("Usuarios")
        self._admin_pin_entry.focus_set()

    def _toggle_lan_from_menu(self) -> None:
        """Alterna la red local desde «Herramientas» sin duplicar la lógica.

        El checkbutton ya cambió su variable; si coincide con el modo real, no hay
        nada que hacer (así un doble clic no invierte dos veces).
        """
        if bool(self._lan_var.get()) == lan_mode():
            return
        self.toggle_lan_mode()

    def open_logs_folder(self) -> None:
        """Abre la carpeta de registros en el explorador (Windows)."""
        opener = getattr(os, "startfile", None)
        if opener is None:
            self._msg.set(f"Registros en: {LOG_DIR}")
            return
        try:
            opener(str(LOG_DIR))
        except OSError as exc:
            self._msg.set(f"No se pudo abrir la carpeta de registros: {exc}")

    def show_device_help(self) -> None:
        """Instrucciones para conectar un móvil/tablet (certificado autofirmado)."""
        activa = lan_mode()
        url = lan_url() if activa else "(activa antes la red local)"
        messagebox.showinfo(
            "Conectar un dispositivo",
            "Para usar la app desde un móvil o una tablet de la misma red:\n\n"
            "1. Activa la red local (menú Herramientas; reinicia el servidor).\n"
            "2. Abre el puerto con launcher\\allow-firewall.ps1 (una sola vez).\n"
            "3. Abre en el dispositivo la dirección:\n" + url + "\n\n"
            "El certificado es local y autofirmado: la primera vez el navegador "
            "avisará. Acepta la excepción (o instala el certificado) y listo.\n\n"
            "La entrada por LAN está cerrada: sigue haciendo falta pedir el alta.",
            parent=self.root,
        )

    def show_about(self) -> None:
        """Créditos, versión y rutas útiles (lo que antes iba en la cabecera)."""
        messagebox.showinfo(
            "Acerca de English Tutor",
            f"English Tutor\n{author_line()}\n\n"
            f"Versión: {self._version.get() or '—'}\n\n"
            f"Base de datos:\n{DB_PATH}\n\n"
            f"Registros:\n{LOG_DIR}",
            parent=self.root,
        )

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
                    "y ver las cuentas (la entrada por LAN está cerrada: sigue "
                    "haciendo falta pedir el alta). Primera "
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
        # El menú «Herramientas» marca el modo real, no lo que se creía marcar.
        self._lan_var.set(expuesta)
        self._refresh_status_right()

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

    def _build_users(self, parent: tk.Misc) -> None:
        """Usuarios (V3.81): la consola de gestión — solicitudes y cuentas.

        Es la mitad visible de la decisión de producto: **el webmaster no es un rol
        de la app, es quien ejecuta este programa**. Aquí están las cosas que solo él
        puede hacer: resolver solicitudes, crear cuentas, asignar o restablecer
        credenciales, verificar el email a mano, desactivar, reactivar, **forzar la
        baja con motivo**, editar los datos, leer el historial, purgar y configurar
        el correo.

        Todo lo que escribe pasa por `admin.py` (HTTP con el PIN), nunca por la BD
        directamente, aunque el launcher tenga el fichero a mano: el borrado tiene
        que pasar por el mismo sitio que el resto (validación, copia previa, tabla
        de solicitudes, registro de auditoría) o habría dos definiciones de «purgar»
        y la de aquí sería la que nadie prueba.
        """
        sec = self._section(parent, "Usuarios")

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

        # --- Correo saliente (modo híbrido de verificación) ---
        self._smtp_var = tk.StringVar(value=smtp_state_label(False, False))
        self._smtp_label = ttk.Label(
            sec.body,
            textvariable=self._smtp_var,
            style="DimCard.TLabel",
            wraplength=COLUMN_W - 30,
        )
        self._smtp_label.pack(anchor="w", fill="x", padx=14, pady=(8, 0))
        smtp_row = ttk.Frame(sec.body, style="Card.TFrame")
        smtp_row.pack(fill="x", padx=14, pady=(4, 0))
        ttk.Button(
            smtp_row,
            text="📧 Configurar correo…",
            style="Ghost.TButton",
            command=self.configure_smtp_dialog,
        ).pack(side="left")

        # --- Solicitudes pendientes ---
        self._pending_var = tk.StringVar(value="Solicitudes: …")
        ttk.Label(
            sec.body, textvariable=self._pending_var, style="Service.TLabel"
        ).pack(anchor="w", padx=14, pady=(10, 0))

        pending_wrap = ttk.Frame(sec.body, style="Card.TFrame")
        pending_wrap.pack(fill="both", expand=True, padx=14, pady=(4, 0))
        self._pending_tree = ttk.Treeview(
            pending_wrap,
            columns=("kind", "who", "email", "when"),
            show="headings",
            height=4,
        )
        for column, title, width, anchor in (
            ("kind", "Tipo", 90, "w"),
            ("who", "Cuenta", 230, "w"),
            ("email", "Email", 190, "w"),
            ("when", "Llegó", 130, "e"),
        ):
            self._pending_tree.heading(column, text=title)
            self._pending_tree.column(column, width=width, anchor=anchor)
        # V3.81.3: con scroll vertical y horizontal. En una ventana estrecha las
        # columnas de la derecha se quedaban fuera y no había forma de verlas.
        attach_scrollbars(self._pending_tree, pending_wrap)

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

        # --- Cuentas existentes ---
        self._accounts_var = tk.StringVar(value="Cuentas: …")
        ttk.Label(
            sec.body, textvariable=self._accounts_var, style="Service.TLabel"
        ).pack(anchor="w", padx=14, pady=(12, 0))
        profiles_wrap = ttk.Frame(sec.body, style="Card.TFrame")
        profiles_wrap.pack(fill="both", expand=True, padx=14, pady=(4, 0))
        self._profiles_tree = ttk.Treeview(
            profiles_wrap,
            columns=("name", "status", "email", "credential", "created"),
            show="headings",
            height=6,
        )
        for column, title, width, anchor in (
            ("name", "Nombre", 170, "w"),
            ("status", "Estado", 100, "w"),
            ("email", "Email", 190, "w"),
            ("credential", "Contraseña", 110, "w"),
            ("created", "Creada", 110, "e"),
        ):
            self._profiles_tree.heading(column, text=title)
            self._profiles_tree.column(column, width=width, anchor=anchor)
        # Igual que la cola: sin la barra horizontal, «Contraseña»/«Creada» se
        # cortaban en ventanas estrechas y no había manera de alcanzarlas.
        attach_scrollbars(self._profiles_tree, profiles_wrap)

        # Primera fila de botones: la identidad y la credencial.
        account_row_1 = ttk.Frame(sec.body, style="Card.TFrame")
        account_row_1.pack(fill="x", padx=14, pady=(6, 0))
        ttk.Button(
            account_row_1,
            text="➕ Crear cuenta…",
            style="Ghost.TButton",
            command=self.create_user_dialog,
        ).pack(side="left")
        ttk.Button(
            account_row_1,
            text="🔑 Credenciales…",
            style="Ghost.TButton",
            command=self.credentials_dialog,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            account_row_1,
            text="✉️ Verificar email",
            style="Ghost.TButton",
            command=self.verify_email_selected,
        ).pack(side="left", padx=(6, 0))
        # V3.82: la invitación se puede reemitir a mano. Es lo que hace falta
        # cuando el correo se perdió o cuando no hay SMTP y hay que entregar el
        # enlace uno mismo.
        ttk.Button(
            account_row_1,
            text="📨 Reenviar invitación",
            style="Ghost.TButton",
            command=self.resend_activation_selected,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            account_row_1,
            text="✏️ Editar…",
            style="Ghost.TButton",
            command=self.edit_user_dialog,
        ).pack(side="left", padx=(6, 0))

        # Segunda fila: el ciclo de servicio y el borrado.
        account_row_2 = ttk.Frame(sec.body, style="Card.TFrame")
        account_row_2.pack(fill="x", padx=14, pady=(6, 0))
        ttk.Button(
            account_row_2,
            text="▶️ Reactivar",
            style="Ghost.TButton",
            command=self.reactivate_selected_user,
        ).pack(side="left")
        ttk.Button(
            account_row_2,
            text="⏸️ Desactivar",
            style="Ghost.TButton",
            command=self.deactivate_selected_user,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            account_row_2,
            text="🚫 Forzar baja…",
            style="Ghost.TButton",
            command=self.force_unenroll_selected_user,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            account_row_2,
            text="🕘 Historial…",
            style="Ghost.TButton",
            command=self.user_history_dialog,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            account_row_2,
            text="🗑️ Purgar…",
            style="Danger.TButton",
            command=self.purge_selected_user,
        ).pack(side="left", padx=(6, 0))

        self._profiles_note_var = tk.StringVar(
            value=(
                "Dar de baja o desactivar no borra nada: la cuenta deja de operar y "
                "sus datos se conservan. Purgar sí es irreversible (se lleva toda la "
                "evidencia) y exige que la cuenta esté fuera de servicio; el backend "
                "toma antes una copia de seguridad."
            )
        )
        self._profiles_note_label = ttk.Label(
            sec.body,
            textvariable=self._profiles_note_var,
            style="DimCard.TLabel",
            wraplength=COLUMN_W - 30,
        )
        self._profiles_note_label.pack(anchor="w", fill="x", padx=14, pady=(6, 12))

        # El estado del correo depende solo de la configuración local, así que se
        # pinta al construir en vez de esperar a un refresco de red.
        self._refresh_smtp_state()

    # --- Usuarios: candado de administración (V3.77) ---
    def _refresh_admin_state(self) -> None:
        self._admin_state_var.set(admin_state_label(bool(admin_pin(self._config))))
        activated = bool(admin_pin(self._config))
        self._admin_state_label.configure(
            foreground=COLORS["success"] if activated else COLORS["warning"]
        )
        self._refresh_status_right()

    def _apply_admin_pin_change(self, applied: str, pending: str) -> None:
        """Aplica al backend un cambio del PIN: reinicia, o avisa si no corre.

        `set_admin_pin` declara el PIN en el entorno del launcher y `backend_env()`
        copia ese entorno al **arrancar** el backend. Consecuencia: el PIN del
        backend en marcha no cambia hasta que se reinicia. Antes la GUI se limitaba
        a pedirlo por texto («Reinicia el servidor para que el backend lo
        aplique») y quien no lo hiciera se comía un 401 en cada consulta de la cola
        sin entender por qué. Se hace como el cambio de modo LAN: reiniciar cuando
        el servidor está en marcha y decir que se aplicará al arrancar cuando no.
        """
        self._refresh_admin_state()
        if self.pm.backend_running() or fetch_health() is not None:
            self.restart()
            self._msg.set(applied)
            return
        self._msg.set(pending)
        # Sin servidor no hay nada que reiniciar, pero la sección sí puede
        # repintarse (el contador de la BD no depende del backend).
        self._load_accounts()

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
        self._apply_admin_pin_change(
            "PIN de administración guardado: reiniciando el servidor para "
            "aplicarlo…",
            "PIN de administración guardado. Se aplicará al arrancar la app.",
        )

    def generate_admin_pin_value(self) -> None:
        """Rellena el campo con un PIN aleatorio (lo guarda quien lo confirme)."""
        self._admin_pin_var.set(generate_admin_pin())
        self._msg.set("PIN generado. Pulsa «Guardar PIN» y apunta el valor.")

    def clear_admin_pin(self) -> None:
        """Retira la administración (vuelve a estar deshabilitada, no abierta)."""
        if not messagebox.askyesno(
            "Retirar el PIN de administración",
            "Sin PIN, la administración de cuentas queda DESHABILITADA (fallar "
            "cerrado): no podrás crear cuentas, asignar credenciales, forzar bajas "
            "ni purgar datos hasta que "
            "pongas otro.\n\n¿Retirar el PIN?",
            parent=self.root,
        ):
            return
        set_admin_pin("", self._config)
        self._admin_pin_var.set("")
        self._apply_admin_pin_change(
            "Administración deshabilitada (sin PIN): reiniciando el servidor…",
            "Administración deshabilitada (sin PIN). Se aplicará al arrancar la app.",
        )

    # --- Usuarios: lectura ---
    def _poll_accounts(self) -> None:
        """Refresco periódico de la consola, sin bloquear la ventana."""
        self._load_accounts()
        self.root.after(ACCOUNTS_MS, self._poll_accounts)

    def _load_accounts(self) -> None:
        if self._admin_busy:
            return
        self._admin_busy = True
        pin = admin_pin(self._config)

        def work() -> None:
            # El contador se lee SIEMPRE de la BD en solo-lectura, haya PIN o no.
            # Sin PIN no se llama al backend —la administración está cerrada y
            # pedirla solo generaría un 401 cada quince segundos—, pero el
            # contador es justo lo que hace visible que alguien ha pedido algo: si
            # solo se leyera con PIN, una baja registrada por el alumno podía
            # quedarse invisible en el lanzador, que es el fallo que motivó esta
            # ampliación de V3.80.1.
            db_count = read_pending_requests(str(DB_PATH))
            if not pin:
                self._queue.put(("accounts", (None, None, None, db_count, None)))
                return
            pending = pending_requests(pin)
            accounts = list_admin_users(pin)
            # El correo lo resuelve el **backend**, de su entorno, no del JSON de
            # aquí: se pide en la misma pasada para no abrir un ciclo de sondeo
            # propio —el backend es loopback y ya se le hacen dos llamadas—.
            smtp = smtp_config(pin)
            self._queue.put(("accounts", (pending, accounts, None, db_count, smtp)))

        threading.Thread(target=work, daemon=True).start()

    def _run_admin_action(self, call, success_message, *, invitation=False) -> None:
        """Ejecuta una acción admin en un hilo y refresca la sección al terminar.

        `invitation=True` (V3.82) pide además que el resultado se lleve a la
        ventana de invitación: aprobar un alta y reemitir una invitación devuelven
        el **enlace en claro**, y ese enlace solo existe en esa respuesta —en la
        BD queda su hash—, así que si no se enseña aquí no se puede recuperar sin
        emitir otro.
        """
        if self._admin_busy:
            return
        self._admin_busy = True
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
                if invitation:
                    self._queue.put(("invitation", (result.data,)))
                # Tras escribir, se relee: el contador y las filas tienen que
                # reflejar el estado del backend, no lo que creíamos que iba a pasar.
                pending = pending_requests(pin)
                accounts = list_admin_users(pin)
                db_count = read_pending_requests(str(DB_PATH))
                self._queue.put(
                    (
                        "accounts",
                        (pending, accounts, message, db_count, smtp_config(pin)),
                    )
                )
            else:
                self._queue.put(("admin_msg", (message,)))
                # La lista puede haberse quedado vieja (p. ej. si la solicitud ya
                # estaba resuelta desde otro sitio): se relee igual.
                self._queue.put(
                    (
                        "accounts",
                        (
                            pending_requests(pin),
                            list_admin_users(pin),
                            None,
                            read_pending_requests(str(DB_PATH)),
                            smtp_config(pin),
                        ),
                    )
                )

        threading.Thread(target=work, daemon=True).start()

    def _apply_accounts(
        self, pending, profiles, message, db_count=None, smtp=None
    ) -> None:
        """Pinta la consola «Usuarios» (hilo principal).

        La frase y las filas las decide `ui.pending_view`, que separa los estados
        que aquí se confundían: sin PIN con pendientes, consulta fallida y consulta
        correcta. Este método ya no compone la frase a mano ni puede volver a
        pintar «Sin solicitudes pendientes» cuando lo que ha pasado es un 401, un
        403 o un servidor caído.

        `smtp` es la respuesta del backend sobre el correo, que puede discrepar de
        lo que el launcher tiene guardado (lo ve al arrancar, no en cada cambio):
        la frase se concilia en `ui.smtp_reconcile_label` en vez de enseñar lo
        local como si fuera el estado del servidor.
        """
        self._admin_busy = False

        pin_set = pending is not None and profiles is not None
        requests = list(pending.data.get("requests", [])) if pin_set else []
        # Las bajas guardan el `user_id`: se traduce a nombre con las cuentas ya
        # cargadas para que la cola se pueda leer sin descifrar identificadores.
        self._pending_rows = requests
        self._user_rows = (
            list(profiles.data.get("users", [])) if profiles is not None else []
        )
        names = {str(u.get("id")): str(u.get("name")) for u in self._user_rows}
        # Las dos llamadas tienen que ir bien: sin la lista de cuentas, una baja
        # se leería como «(cuenta que ya no existe)» cuando lo que ha fallado es la
        # consulta. Mejor decir que no se pudo consultar.
        ok = pin_set and bool(pending.ok) and bool(profiles.ok)
        error = ""
        if pin_set and not ok:
            error = pending.message() if not pending.ok else profiles.message()
        frase, filas = pending_view(
            pin_set=pin_set,
            db_count=db_count,
            ok=ok,
            error=error,
            requests=requests,
            names=names,
        )

        self._pending_var.set(frase)
        self._pending_tree.delete(*self._pending_tree.get_children())
        for fila in filas:
            self._pending_tree.insert("", "end", values=fila)

        # V3.81: la lista de cuentas lleva su propia frase, que es la **lista de
        # tareas** (cuántas están pendientes de activación y cuántas con el email
        # sin verificar). Se pinta aparte de la cola de solicitudes porque una
        # puede estar vacía mientras la otra tiene trabajo.
        data = profiles.data if profiles is not None else {}
        self._accounts_var.set(
            "Cuentas: sin datos (define el PIN para verlas)"
            if profiles is None or not profiles.ok
            else (
                f"Cuentas ({len(self._user_rows)}) · "
                + accounts_tasks(
                    int(data.get("without_password", 0)),
                    int(data.get("unverified_email", 0)),
                )
            )
        )
        duplicates = duplicate_user_ids(self._user_rows)
        self._profiles_tree.delete(*self._profiles_tree.get_children())
        for user in self._user_rows:
            self._profiles_tree.insert("", "end", values=user_row(user, duplicates))

        self._refresh_smtp_state(smtp)
        if message:
            self._msg.set(str(message))

    def _selected_pending(self) -> dict | None:
        selection = self._pending_tree.selection()
        if not selection:
            self._msg.set("Selecciona una solicitud de la lista.")
            return None
        index = self._pending_tree.index(selection[0])
        return self._pending_rows[index] if index < len(self._pending_rows) else None

    def _selected_user(self) -> dict | None:
        selection = self._profiles_tree.selection()
        if not selection:
            self._msg.set("Selecciona una cuenta de la lista.")
            return None
        index = self._profiles_tree.index(selection[0])
        return self._user_rows[index] if index < len(self._user_rows) else None

    # --- Usuarios: acciones ---
    def approve_selected_request(self) -> None:
        request = self._selected_pending()
        if request is None:
            return
        request_id = int(request["id"])
        if request.get("kind") == "delete":
            nombre = next(
                (
                    str(u.get("name"))
                    for u in self._user_rows
                    if str(u.get("id")) == str(request.get("user_id"))
                ),
                "(cuenta ya inexistente)",
            )
            if not messagebox.askyesno(
                "Aprobar la baja",
                f"Se DESACTIVARÁ la cuenta «{nombre}»: dejará de aparecer y no "
                "podrá abrir sesión, pero sus datos se conservan y se puede "
                "reactivar.\n\nPara borrarla de verdad hay que purgarla, que es un "
                "paso aparte.\n\n¿Aprobar la baja?",
                parent=self.root,
            ):
                return
        self._run_admin_action(
            lambda pin: approve_request(pin, request_id),
            "Solicitud aprobada.",
            # V3.82: aprobar un alta emite la invitación, y su enlace solo existe
            # en la respuesta. Hay que enseñarlo aquí o se pierde.
            invitation=request.get("kind") != "delete",
        )

    def resend_activation_selected(self) -> None:
        """Reemite la invitación de activación de la cuenta seleccionada (V3.82).

        Es lo que hace falta cuando el correo se perdió, caducó o nunca salió por
        no haber SMTP. Emite un token nuevo —el anterior deja de valer— y enseña el
        enlace para entregarlo a mano.
        """
        user = self._selected_user()
        if user is None:
            return
        name = str(user.get("name") or "")
        if user.get("has_password"):
            if not messagebox.askyesno(
                "Reenviar la invitación",
                f"«{name}» ya tiene contraseña. Reemitir la invitación le permite "
                "elegir una nueva desde el correo (la actual dejará de valer).\n\n"
                "Para un restablecimiento normal, lo suyo es que lo pida desde "
                "«He olvidado la contraseña». ¿Emitir la invitación igualmente?",
                parent=self.root,
            ):
                return
        self._run_admin_action(
            lambda pin: resend_activation(pin, str(user["id"])),
            f"Invitación reemitida para «{name}».",
            invitation=True,
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

    def create_user_dialog(self) -> None:
        """Alta directa con credenciales (no pasa por la cola de solicitudes).

        Se piden los tres datos y la contraseña se puede **dejar vacía**: entonces
        el backend genera una temporal legible y marca la cuenta con
        `must_change_password`, así que el webmaster la entrega sin inventarse nada
        y sin llegar a saber nunca la contraseña definitiva del alumno. La temporal
        solo viene una vez, en la respuesta, y se enseña aquí.
        """
        name = simpledialog.askstring(
            "Crear una cuenta", "Nombre de la cuenta:", parent=self.root
        )
        if not name or not name.strip():
            return
        email = simpledialog.askstring(
            "Crear una cuenta",
            "Email (sirve para verificar y recuperar; se puede dejar vacío):",
            parent=self.root,
        )
        if email is None:
            return
        password = simpledialog.askstring(
            "Crear una cuenta",
            "Contraseña (déjala vacía y genero yo una temporal para entregar):",
            parent=self.root,
        )
        if password is None:
            return
        self._run_admin_action(
            lambda pin: create_user(
                pin, name.strip(), email=email.strip(), password=password.strip()
            ),
            f"Cuenta «{name.strip()}» creada.",
        )

    def credentials_dialog(self) -> None:
        """Asigna o **restablece** la credencial: es la recuperación de contraseña.

        El producto no promete un correo de recuperación (puede no haber SMTP), y
        no prometerlo es más honesto que prometerlo y no cumplirlo: quien olvide su
        contraseña se la pide al webmaster, que la restablece aquí con una temporal.
        """
        user = self._selected_user()
        if user is None:
            return
        name = str(user.get("name") or "")
        email = simpledialog.askstring(
            "Credenciales de la cuenta",
            f"Email de «{name}»:",
            initialvalue=str(user.get("email") or ""),
            parent=self.root,
        )
        if email is None or not email.strip():
            return
        password = simpledialog.askstring(
            "Credenciales de la cuenta",
            "Contraseña nueva (vacío = genero una temporal y la enseño aquí):",
            parent=self.root,
        )
        if password is None:
            return
        self._run_admin_action(
            lambda pin: set_credentials(
                pin, str(user["id"]), email=email.strip(), password=password.strip()
            ),
            f"Credencial de «{name}» actualizada.",
        )

    def verify_email_selected(self) -> None:
        """Sella el email a mano: la mitad híbrida del plan.

        Sin SMTP configurado el enlace de verificación no sale de ningún sitio, así
        que el webmaster confirma —normalmente con la persona delante— y la cuenta
        deja de arrastrar el chip de «sin verificar». Sin esto, la verificación
        sería un muro en una app que se promete local.
        """
        user = self._selected_user()
        if user is None:
            return
        name = str(user.get("name") or "")
        if not user.get("email"):
            messagebox.showinfo(
                "Sin email que verificar",
                f"«{name}» no tiene email. Asígnale unas credenciales primero y "
                "después podrás verificar el correo.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Verificar el email a mano",
            f"¿Confirmas que el email de «{name}» es suyo?\n\n{user.get('email')}",
            parent=self.root,
        ):
            return
        self._run_admin_action(
            lambda pin: verify_email(pin, str(user["id"])),
            f"Email de «{name}» verificado a mano.",
        )

    def edit_user_dialog(self) -> None:
        """El webmaster edita los datos con la misma autoridad que su dueño.

        Y una más: puede corregir el **email**, cosa que el alumno solo puede hacer
        con su contraseña delante (y que reinicia la verificación, porque el sello
        pertenecía al correo anterior).
        """
        user = self._selected_user()
        if user is None:
            return
        name = simpledialog.askstring(
            "Editar la cuenta",
            "Nombre:",
            initialvalue=str(user.get("name") or ""),
            parent=self.root,
        )
        if name is None or not name.strip():
            return
        email = simpledialog.askstring(
            "Editar la cuenta",
            "Email (cambiarlo reinicia su verificación):",
            initialvalue=str(user.get("email") or ""),
            parent=self.root,
        )
        if email is None:
            return
        emoji = simpledialog.askstring(
            "Editar la cuenta",
            "Avatar (emoji; vacío = sin cambio):",
            parent=self.root,
        )
        if emoji is None:
            return
        fields: dict = {"name": name.strip(), "email": email.strip()}
        if emoji.strip():
            fields["avatar_emoji"] = emoji.strip()
        self._run_admin_action(
            lambda pin: edit_user(pin, str(user["id"]), **fields),
            f"Cuenta «{name.strip()}» editada.",
        )

    def reactivate_selected_user(self) -> None:
        """Devuelve la cuenta al servicio (desactivada **o** dada de baja)."""
        user = self._selected_user()
        if user is None:
            return
        name = str(user.get("name") or "")
        if str(user.get("status")) == "active":
            self._msg.set(f"«{name}» ya está activa.")
            return
        self._run_admin_action(
            lambda pin: set_user_status(pin, str(user["id"]), "active"),
            f"Cuenta «{name}» reactivada.",
        )

    def deactivate_selected_user(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        name = str(user.get("name") or "")
        if str(user.get("status")) != "active":
            self._msg.set(
                f"«{name}» no está activa. Usa «Reactivar» para devolverla al "
                "servicio."
            )
            return
        if not messagebox.askyesno(
            "Desactivar la cuenta",
            f"«{name}» saldrá del selector y no podrá abrir sesión. Sus datos se "
            "conservan y puedes reactivarla cuando quieras.\n\n¿Desactivar?",
            parent=self.root,
        ):
            return
        self._run_admin_action(
            lambda pin: set_user_status(pin, str(user["id"]), "disabled"),
            f"Cuenta «{name}» desactivada.",
        )

    def force_unenroll_selected_user(self) -> None:
        """**Fuerza** la baja con motivo obligatorio.

        Va aparte de «desactivar» a propósito: forzar la baja tiene que poder
        explicarse después («¿por qué me sacasteis?»), y el motivo queda en el
        historial. Sin motivo, esto sería un botón anónimo.
        """
        user = self._selected_user()
        if user is None:
            return
        name = str(user.get("name") or "")
        reason = simpledialog.askstring(
            "Forzar la baja",
            f"«{name}» dejará de operar y se cerrarán sus sesiones al instante. No "
            "se borra nada: sus datos se conservan.\n\nMotivo (obligatorio, queda "
            "en el historial):",
            parent=self.root,
        )
        if reason is None:
            return
        if not reason.strip():
            self._msg.set("Sin motivo no se fuerza la baja: es lo que la explica.")
            return
        self._run_admin_action(
            lambda pin: force_unenroll(pin, str(user["id"]), reason.strip()),
            f"Baja forzada de «{name}» (motivo guardado).",
        )

    def user_history_dialog(self) -> None:
        """Historial de auditoría en una ventana aparte (solo lectura).

        Es lo que responde «¿quién hizo esto y por qué?», incluso después de purgar
        la cuenta: los eventos no se borran con ella.
        """
        user = self._selected_user()
        if user is None:
            return
        pin = admin_pin(self._config)
        if not pin:
            self._msg.set("Define un PIN de administración primero.")
            return
        name = str(user.get("name") or "")
        # La llamada es corta y de solo lectura, pero es red: se hace en un hilo
        # como todas las demás y la ventana se pinta desde el hilo principal.
        def work() -> None:
            self._queue.put(("history", (name, user_history(pin, str(user["id"])))))

        threading.Thread(target=work, daemon=True).start()

    def _show_invitation(self, data: dict) -> None:
        """Ventana con el enlace de invitación para copiarlo (V3.82).

        El modo híbrido, resuelto en el único sitio donde tiene sentido: si el
        correo salió, esto solo lo confirma y no hay nada que copiar; si no salió,
        el enlace se entrega desde aquí. Se pinta en el hilo principal porque es
        tkinter, y todo el texto lo compone `ui` —que es donde tiene test—.
        """
        win = tk.Toplevel(self.root)
        win.title("Invitación")
        win.geometry("640x300")
        frame = ttk.Frame(win, style="Card.TFrame")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            frame,
            text=invitation_message(data),
            style="Service.TLabel",
            wraplength=600,
        ).pack(anchor="w", pady=(0, 8))

        link = str(data.get("activation_link") or "")
        if not link:
            return

        ttk.Label(
            frame,
            text="Enlace de activación (caduca y solo sirve una vez):",
            style="DimCard.TLabel",
        ).pack(anchor="w")

        text = tk.Text(frame, height=6, wrap="word")
        text.insert("1.0", invitation_copy_text(data))
        text.pack(fill="both", expand=True, pady=(4, 6))

        def copiar() -> None:
            # Se copia **todo el texto**, no solo el enlace: lo normal es pegarlo
            # en un mensaje, y el contexto («invitación para …») es parte del
            # mensaje que el webmaster va a mandar.
            self.root.clipboard_clear()
            self.root.clipboard_append(text.get("1.0", "end-1c"))
            self._msg.set("Enlace de invitación copiado al portapapeles.")

        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x")
        ttk.Button(
            buttons, text="📋 Copiar", style="Success.TButton", command=copiar
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Cerrar",
            style="Ghost.TButton",
            command=win.destroy,
        ).pack(side="left", padx=(6, 0))

    def _show_history_window(self, name: str, result) -> None:
        """Ventana de historial (hilo principal). `result` es un `AdminResult`."""
        win = tk.Toplevel(self.root)
        win.title(f"Historial — {name}")
        win.geometry("760x420")
        frame = ttk.Frame(win, style="Card.TFrame")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        if not result.ok:
            ttk.Label(
                frame, text=result.message(), style="Service.TLabel", wraplength=700
            ).pack(anchor="w")
            return
        events = list(result.data.get("events", []))
        ttk.Label(
            frame,
            text=f"{len(events)} movimiento(s), del más reciente al más antiguo.",
            style="DimCard.TLabel",
        ).pack(anchor="w", pady=(0, 6))
        cols = ("when", "what", "who", "note")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        for column, title, width, anchor in (
            ("when", "Cuándo", 130, "w"),
            ("what", "Qué", 220, "w"),
            ("who", "Quién", 110, "w"),
            ("note", "Motivo", 260, "w"),
        ):
            tree.heading(column, text=title)
            tree.column(column, width=width, anchor=anchor)
        for event in events:
            tree.insert("", "end", values=event_row(event))
        tree.pack(fill="both", expand=True)

    def configure_smtp_dialog(self) -> None:
        """Configura el correo saliente (modo híbrido) con prueba de envío.

        La contraseña se guarda en `data/mail.secret` y **no** en el JSON del
        launcher ni en el entorno: es la misma familia de secreto que la clave TLS,
        y `services/backup.py` la deja fuera de las copias. Aquí se pide y se
        escribe, pero no se vuelve a enseñar.
        """
        current = smtp_settings(self._config)
        host = simpledialog.askstring(
            "Correo saliente",
            "Servidor SMTP (vacío = apagar el correo y verificar a mano):",
            initialvalue=current["host"],
            parent=self.root,
        )
        if host is None:
            return
        host = host.strip()
        if not host:
            if not messagebox.askyesno(
                "Apagar el correo",
                "Se guardará sin servidor: no se enviará ninguna verificación y "
                "las sellarás a mano desde esta consola.\n\n¿Continuar?",
                parent=self.root,
            ):
                return
            self._save_smtp(
                host="", port=current["port"], user="", sender="", password=""
            )
            return
        port = simpledialog.askstring(
            "Correo saliente",
            "Puerto (587 con STARTTLS es lo normal; 465 con TLS implícito):",
            initialvalue=str(current["port"]),
            parent=self.root,
        )
        if port is None:
            return
        user = simpledialog.askstring(
            "Correo saliente",
            "Usuario (vacío si el servidor no pide autenticación):",
            initialvalue=current["user"],
            parent=self.root,
        )
        if user is None:
            return
        sender = simpledialog.askstring(
            "Correo saliente",
            "Remitente (lo que verá quien reciba el correo):",
            initialvalue=current["sender"] or user,
            parent=self.root,
        )
        if sender is None:
            return
        # La contraseña se pregunta con `show="•"` para que no quede en pantalla.
        password = simpledialog.askstring(
            "Correo saliente",
            "Contraseña del SMTP (vacío = borrar la guardada):",
            show="•",
            parent=self.root,
        )
        if password is None:
            return
        self._save_smtp(
            host=host, port=port, user=user, sender=sender, password=password
        )

    def _save_smtp(
        self, *, host: str, port, user: str, sender: str, password: str
    ) -> None:
        """Guarda el SMTP, lo declara en el entorno y ofrece una prueba de envío."""
        if (
            set_smtp_settings(
                self._config,
                host=host,
                port=port,
                user=user,
                sender=sender,
                password=password,
            )
            is None
        ):
            self._msg.set(
                "Ese correo no vale: revisa el puerto (1-65535) y que haya "
                "servidor y remitente."
            )
            return
        self._refresh_smtp_state()
        # Probar el correo es la única forma de saber que funciona: la alternativa
        # —confiar en que el host y el puerto están bien— se descubre fallando
        # cuando alguien espera una verificación que nunca llega.
        if host and messagebox.askyesno(
            "Probar el envío",
            "¿Mando un correo de prueba ahora, para comprobar que funciona?",
            parent=self.root,
        ):
            to = simpledialog.askstring(
                "Correo de prueba",
                "Dirección a la que mando la prueba:",
                initialvalue=sender or user,
                parent=self.root,
            )
            if to and to.strip():
                self._run_admin_action(
                    lambda pin: test_smtp(pin, to.strip()),
                    "Correo de prueba enviado. Revisa esa bandeja.",
                )
                return
        self._refresh_smtp_state()
        if not (self.pm.backend_running() or fetch_health() is not None):
            self._msg.set(
                "Correo configurado. Se aplicará al arrancar la app."
                if host
                else "Correo apagado: la verificación la sellarás a mano."
            )
            return
        self.restart()
        self._msg.set(
            "Correo configurado: reiniciando el servidor para aplicarlo…"
            if host
            else "Correo apagado: reiniciando el servidor…"
        )

    def _refresh_smtp_state(self, backend=None) -> None:
        """Repinta la línea de estado del correo (configurado / con contraseña).

        `backend` es la lectura de `GET /api/admin/smtp` cuando se ha podido hacer
        (hilo de sondeo, con PIN). Sin ella —al construir la sección, o sin PIN— se
        enseña el estado local, que es todo lo que se sabe sin preguntar.
        """
        settings = smtp_settings(self._config)
        view = backend.data if (backend is not None and backend.ok) else None
        self._smtp_var.set(
            smtp_reconcile_label(settings["configured"], bool(mail_secret()), view)
        )

    def purge_selected_user(self) -> None:
        """Purga irreversible: confirmación por nombre + copia que hace el backend."""
        profile = self._selected_user()
        if profile is None:
            return
        user_id = str(profile["id"])
        name = str(profile.get("name") or "")
        bloqueo = purge_block_reason(profile)
        if bloqueo:
            messagebox.showinfo(
                "Fuera de servicio antes de purgar", bloqueo, parent=self.root
            )
            return
        typed = simpledialog.askstring(
            "Purgar la cuenta",
            f"Esto borra «{name}» y TODA su evidencia (progreso, mastery, "
            "conversaciones, grabaciones). Es irreversible.\n\nEl backend tomará "
            "una copia de seguridad antes de borrar.\n\nEscribe el nombre exacto "
            "de la cuenta para confirmar:",
            parent=self.root,
        )
        if typed is None or typed.strip() != name:
            if typed is not None:
                self._msg.set("El nombre no coincide: no se ha purgado nada.")
            return
        success = f"Cuenta «{name}» purgada (con copia de seguridad previa)."
        if self._session_open:
            # La cookie del navegador sigue siendo válida pero apunta a una cuenta
            # que ya no existe: la app se quedará en la puerta hasta que se
            # recargue. Se avisa aquí porque es el único momento en que alguien
            # puede relacionar las dos cosas.
            success += (
                " Ojo: la sesión abierta en el navegador ya no vale; si la app "
                "estaba abierta, recárgala y elige otra cuenta."
            )
        self._run_admin_action(
            lambda pin: purge_user(pin, user_id, name),
            success,
        )

    def _build_user_activity(self, parent: tk.Misc) -> None:
        """Actividad por usuario, **leída de la BD** (no depende del backend).

        Es información distinta de la consola: aquí no se administra nada, se mira
        cuánto hay de cada uno, y se puede leer con el servidor apagado. Se llama
        «Actividad por usuario» y no «Usuarios» porque ese nombre es ahora el de la
        consola de gestión, que es donde el webmaster tiene algo que hacer.
        """
        sec = self._section(parent, "Actividad por usuario")
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
        attach_scrollbars(self._tree, wrap)

    def _build_cookies(self, parent: tk.Misc) -> None:
        sec = self._section(parent, "Cookies navegador")
        wrap = ttk.Frame(sec.body, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self._cookie_var = tk.StringVar(value="…")
        ttk.Label(wrap, textvariable=self._cookie_var, style="Service.TLabel").pack(
            anchor="w"
        )
        self._session_var = tk.StringVar(value="")
        # V3.80.2: ¿hay una sesión abierta en algún navegador? Se guarda para
        # poder avisar al purgar: esa cookie pasa a apuntar a un usuario que ya
        # no existe, así que la app se quedará en la puerta hasta recargar.
        self._session_open = False
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
        attach_scrollbars(self._cookie_tree, wrap)

    def _build_logs(self, parent: tk.Misc) -> None:
        """Pestaña de registros: `backend.log` y `frontend.log` con su scroll.

        Ya no es un desplegable: ahora es una pestaña, así que puede quedarse con
        todo el alto de la pestaña y leer los logs sin encoger la ventana. El
        `Text` se lleva su propia rueda (lo enruta `enable_mousewheel_scrolling`).
        """
        wrap = ttk.Frame(parent, style="TFrame")
        wrap.pack(fill="both", expand=True, padx=10, pady=10)
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
        elif kind == "accounts":
            # V3.81: resultado de una lectura/acción de la consola «Usuarios».
            self._apply_accounts(*item[1])
        elif kind == "invitation":
            # V3.82: aprobar o reemitir devuelve el enlace de activación en claro
            # (en la BD queda su hash), así que se enseña para poder entregarlo
            # cuando no hay SMTP.
            self._show_invitation(dict(item[1]))
        elif kind == "history":
            # Ventana de historial (solo lectura): se pinta en el hilo principal,
            # que es el único que puede tocar tkinter.
            self._show_history_window(*item[1])
        elif kind == "admin_msg":
            # Solo el mensaje: lo usa una acción de administración que no llegó a
            # ejecutarse (sin PIN) o que falló y ya trae su propio «accounts».
            self._admin_busy = False
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
            # La consola «Usuarios» depende del backend (PIN y cola), así que un
            # arranque o un reinicio la deja obsoleta: se relee sin esperar al
            # siguiente ciclo de sondeo.
            self._load_accounts()
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
        # V3.80.2: los nombres repetidos se marcan. El selector de la app y esta
        # tabla identifican a los usuarios por nombre, así que dos «J.A» hacen
        # imposible saber a quién se le está dando de baja o purgando.
        overview = user_overview(users)
        duplicates = duplicate_user_ids(overview)
        for u in overview:
            self._tree.insert(
                "",
                "end",
                values=(
                    user_row_label(u, duplicates),
                    u["conversations"],
                    u["messages"],
                ),
            )

        self._apply_cookies(cookies, cookies_summary)

        self._set_log("backend", backend_log)
        self._set_log("frontend", frontend_log)

        # V3.81.3: la hora de esta lectura viaja a la barra de estado, para que se
        # distinga «no hay nada» de «hace rato que no se mira».
        self._checked_at = time.strftime("%H:%M")
        self._refresh_status_right()
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
        self._session_open = bool(summary.get("session_open"))
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
        """Ajusta el wraplength de los textos largos al ancho de su pestaña.

        Antes se medía cada columna del `PanedWindow`; ahora manda la pestaña
        visible, porque las ocultas miden 1 hasta que se muestran y no sirven de
        referencia. Se repasan todas las etiquetas de texto largo de golpe: cada
        una vive en una pestaña distinta y solo se ve la de la pestaña activa.
        """
        frame = self._tabs.get(self._current_tab_name)
        if frame is None:
            return
        width = self._tab_body(frame).winfo_width()
        if width <= 60:
            return
        wrap = max(width - 60, 200)
        for name in (
            "_db_detail_label",
            "_db_file_label",
            "_cookie_diag_label",
            "_access_note",
            "_admin_state_label",
            "_smtp_label",
            "_profiles_note_label",
        ):
            label = getattr(self, name, None)
            if label is not None:
                label.configure(wraplength=wrap)

    def _screen_size(self) -> tuple[int, int]:
        """Tamaño de la pantalla (0,0 si el entorno no lo sabe)."""
        try:
            return self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        except tk.TclError:
            return 0, 0

    def _clamp_size(self, width: int, height: int) -> tuple[int, int]:
        """Acota el tamaño a la pantalla actual y al mínimo usable."""
        screen_w, screen_h = self._screen_size()
        return clamp_window_size(
            width,
            height,
            screen_w=screen_w,
            screen_h=screen_h,
            min_w=MIN_W,
            min_h=MIN_H,
        )

    def _centered(self, width: int, height: int) -> tuple[int, int]:
        """Posición centrada (algo hacia arriba) para el tamaño dado."""
        screen_w, screen_h = self._screen_size()
        return centered_position(width, height, screen_w=screen_w, screen_h=screen_h)

    def _position_visible(self, x: int, y: int) -> bool:
        """True si la ventana cae dentro de la pantalla con margen suficiente."""
        screen_w, screen_h = self._screen_size()
        return window_position_visible(x, y, screen_w=screen_w, screen_h=screen_h)

    def _restore_window(self) -> None:
        """Restaura tamaño/posición y pestaña, encajándolos en la pantalla.

        El estado guardado puede venir de un monitor que ya no existe (o de una
        medición más alta que la pantalla): restaurarlo tal cual dejaba la parte
        de abajo —barra de estado incluida— fuera del escritorio. Se acota al
        área visible y se centra si la posición guardada cae fuera.
        """
        win = self._state["window"]
        width, height = self._clamp_size(win["width"], win["height"])
        x, y = win["x"], win["y"]
        if x is None or y is None or not self._position_visible(x, y):
            x, y = self._centered(width, height)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        # La pestaña guardada se abre una vez existe el cuaderno.
        self.show_tab(str(self._state.get("tab") or TAB_ORDER[0]))

    def _reset_window(self) -> None:
        """Devuelve la ventana a su tamaño por defecto, centrada (menú Ver)."""
        width, height = self._clamp_size(WINDOW_W, WINDOW_H)
        x, y = self._centered(width, height)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _on_close(self) -> None:
        """Guarda el estado visual y cierra la ventana."""
        try:
            self._state["window"] = {
                "width": self.root.winfo_width(),
                "height": self.root.winfo_height(),
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
            }
            # V3.81.3: se guarda la pestaña activa y si la barra de herramientas se
            # ve. `sash` se deja de escribir (ya no hay divisor) pero se conserva
            # en el JSON por compatibilidad con estados anteriores.
            self._state["tab"] = self._current_tab_name
            self._state["toolbar"] = bool(self._toolbar_visible.get())
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
