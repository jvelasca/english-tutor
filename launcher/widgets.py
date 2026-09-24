"""Widgets de presentación del launcher (tkinter, sin lógica de negocio).

Aquí vive la pieza que hacía que las columnas **no se pudieran recorrer con la
rueda**: un contenedor con scroll vertical real y un enrutado de la rueda que
decide quién debe atenderla. Antes solo se movían arrastrando la barra.

Se mantiene aparte de `ui.py` a propósito: `ui.py` son funciones puras sin
tkinter (se prueban sin abrir ventanas); esto es presentación y necesita una
ventana de verdad.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator
from tkinter import ttk

from ui import COLORS

# Widgets con scroll propio: mientras les quede recorrido, la rueda es suya y no
# se reenvía a la columna que los contiene (si no, se desplazarían los dos).
_NATIVE_SCROLLERS = (ttk.Treeview, tk.Text, tk.Listbox)


class ScrollableFrame(ttk.Frame):
    """Marco con scroll vertical (barra + rueda) y cuerpo empaquetable.

    El canvas es quien se desplaza y `body` es donde se empaquetan las secciones.
    El cuerpo se fija al ancho visible del canvas para que las tarjetas usen toda
    la ventana en vez de quedarse a su ancho natural.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        horizontal: bool = False,
        style: str = "TFrame",
    ) -> None:
        super().__init__(parent, style=style)
        self._canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        self._vbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.body = ttk.Frame(self._canvas, style=style)
        self._window = self._canvas.create_window(
            (0, 0), window=self.body, anchor="nw"
        )
        self.body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.configure(yscrollcommand=self._vbar.set)

        self._hbar: ttk.Scrollbar | None = None
        if horizontal:
            self._hbar = ttk.Scrollbar(
                self, orient="horizontal", command=self._canvas.xview
            )
            self._canvas.configure(xscrollcommand=self._hbar.set)
            self._hbar.pack(side="bottom", fill="x")
        # La vertical se reserva antes que el canvas para que este ocupe el resto.
        self._vbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

    def _on_body_configure(self, _event: object) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window, width=event.width)

    def scroll_steps(self, steps: int) -> None:
        """Desplaza el marco ``steps`` unidades (positivo = hacia abajo)."""
        self._canvas.yview_scroll(steps, "units")

    def scroll_to_top(self) -> None:
        self._canvas.yview_moveto(0.0)


def attach_scrollbars(tree: ttk.Treeview, wrap: tk.Misc) -> None:
    """Empaqueta ``tree`` con scroll vertical y horizontal dentro de ``wrap``.

    El orden de empaquetado importa: la barra horizontal reserva su franja
    abajo, luego la vertical reserva la derecha y el árbol ocupa lo que queda.
    Con el árbol empaquetado antes que las barras, ya no habría hueco para
    ellas (se quedarían fuera de la ventana, que es justo el fallo que se está
    corrigiendo).
    """
    vbar = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    hbar = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
    hbar.pack(side="bottom", fill="x")
    vbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)


def _wheel_steps(event: tk.Event) -> int:
    """Pasos de rueda (positivo = hacia abajo) para Windows y X11."""
    num = getattr(event, "num", None)
    if num == 4:
        return -1
    if num == 5:
        return 1
    delta = getattr(event, "delta", 0) or 0
    if delta == 0:
        return 0
    steps = -int(delta / 120)
    return steps if steps != 0 else (-1 if delta > 0 else 1)


def _ancestors(widget: tk.Misc) -> Iterator[tk.Misc]:
    """Cadena de ancestros de ``widget``, de él mismo hacia la raíz."""
    current: tk.Misc | None = widget
    while current is not None:
        yield current
        current = getattr(current, "master", None)


def _can_scroll(widget: tk.Misc, steps: int) -> bool:
    """True si ``widget`` puede moverse en la dirección pedida."""
    try:
        first, last = widget.yview()  # type: ignore[attr-defined]
    except (tk.TclError, AttributeError):
        return False
    return first > 0.0 if steps < 0 else last < 1.0


def _widget_under_pointer(root: tk.Misc, event: tk.Event) -> tk.Misc | None:
    """Widget bajo el puntero (con el del evento como respaldo)."""
    try:
        x, y = root.winfo_pointerxy()
        found = root.winfo_containing(x, y)
    except (tk.TclError, KeyError):
        found = None
    return found or getattr(event, "widget", None)


def wheel_column(widget: tk.Misc | None, steps: int) -> ScrollableFrame | None:
    """Qué columna debe atender la rueda, o `None` si la atiende otro widget.

    Regla: **manda el widget más específico**. Si el puntero está sobre una tabla
    o sobre el registro y le queda recorrido, se desplaza él (y aquí se devuelve
    `None`, para no mover los dos a la vez); si ya está en el tope, la rueda sigue
    con la columna que lo contiene. Se separa del binding para poder probar la
    decisión —que es la parte fácil de equivocar— sin mover el ratón.
    """
    if widget is None or steps == 0:
        return None
    column: ScrollableFrame | None = None
    for node in _ancestors(widget):
        if isinstance(node, _NATIVE_SCROLLERS) and _can_scroll(node, steps):
            return None
        if column is None and isinstance(node, ScrollableFrame):
            column = node
    return column


def enable_mousewheel_scrolling(root: tk.Misc) -> None:
    """Enruta la rueda del ratón a los ``ScrollableFrame`` (una vez por ventana).

    Sin esto los canvas con scroll solo respondían a la barra: la rueda no hacía
    nada. Quién atiende cada evento lo decide `wheel_column`.
    """

    def _handler(event: tk.Event) -> str | None:
        steps = _wheel_steps(event)
        column = wheel_column(_widget_under_pointer(root, event), steps)
        if column is None:
            return None
        column.scroll_steps(steps)
        return "break"

    root.bind_all("<MouseWheel>", _handler, add="+")
    root.bind_all("<Button-4>", _handler, add="+")
    root.bind_all("<Button-5>", _handler, add="+")
