"""Smoke tests de los widgets de presentación (necesitan una ventana).

`ui.py` se prueba sin pantalla porque son funciones puras. `widgets.py` es lo
contrario: solo existe dentro de una ventana, y lo que se comprueba aquí es que
se construye, que deja las dos barras de las tablas y —sobre todo— que la rueda
del ratón se enruta al widget correcto, que es el fallo que esta pieza corrige.
Si el entorno no puede abrir una ventana (CI sin display), el módulo se salta.

La ventana es de **módulo**, no de test: crear y destruir varios intérpretes Tcl
seguidos es inestable en Windows (el segundo `Tk()` puede fallar de forma
intermitente), así que se abre una y se limpian sus hijos entre pruebas.
"""
from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")
ttk = pytest.importorskip("tkinter.ttk")


@pytest.fixture(scope="module")
def root():
    """Ventana oculta compartida; se salta el módulo sin display."""
    try:
        win = tk.Tk()
    except tk.TclError:
        pytest.skip("tkinter no puede abrir una ventana en este entorno")
    win.withdraw()
    yield win
    win.destroy()


@pytest.fixture(autouse=True)
def _limpiar_hijos(root):
    """Deja la ventana como estaba al terminar cada test."""
    yield
    for child in root.winfo_children():
        child.destroy()


def _columna_con_contenido_alto(root) -> tuple[tk.Misc, tk.Misc]:
    """Un `ScrollableFrame` con contenido más alto que su hueco.

    Devuelve (marco, etiqueta interior): la etiqueta es lo que estaría «bajo el
    puntero» en el caso normal.
    """
    from widgets import ScrollableFrame

    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    label = ttk.Label(frame.body, text="contenido")
    label.pack(fill="x")
    root.geometry("400x150+0+0")
    root.update_idletasks()
    return frame, label


def test_scrollable_frame_tiene_cuerpo_y_sabe_desplazarse(root):
    from widgets import ScrollableFrame

    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    root.update_idletasks()

    assert frame.body is not None
    frame.scroll_steps(1)
    frame.scroll_to_top()


def test_attach_scrollbars_deja_el_arbol_con_sus_dos_barras(root):
    from widgets import attach_scrollbars

    wrap = ttk.Frame(root)
    wrap.pack(fill="both", expand=True)
    tree = ttk.Treeview(wrap, columns=("a", "b", "c"), show="headings")
    attach_scrollbars(tree, wrap)
    root.update_idletasks()

    # El árbol y las dos barras (vertical y horizontal) están empaquetados.
    assert tree.winfo_manager() == "pack"
    assert len(wrap.pack_slaves()) == 3


def test_enable_mousewheel_scrolling_se_instala(root):
    from widgets import enable_mousewheel_scrolling

    enable_mousewheel_scrolling(root)
    root.update_idletasks()

    assert root.bind_all("<MouseWheel>") != ""


# --- Enrutado de la rueda (la decisión que hay que acertar) -------------------


def test_la_rueda_sobre_contenido_normal_mueve_su_columna(root):
    from widgets import wheel_column

    frame, label = _columna_con_contenido_alto(root)

    assert wheel_column(label, 1) is frame
    assert wheel_column(label, -1) is frame


def test_la_rueda_sobre_una_tabla_con_recorrido_la_deja_a_ella(root):
    """Dentro de una tabla, la rueda es de la tabla: si no, se moverían las dos."""
    from widgets import ScrollableFrame, wheel_column

    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame.body, columns=("a",), show="headings", height=3)
    for i in range(200):
        tree.insert("", "end", values=(i,))
    tree.pack(fill="x")
    root.geometry("400x150+0+0")
    root.update_idletasks()

    assert wheel_column(tree, 1) is None


def test_la_rueda_sobre_una_tabla_sin_recorrido_sigue_con_la_columna(root):
    """Al llegar al tope, la rueda no se queda muerta: continúa por fuera."""
    from widgets import ScrollableFrame, wheel_column

    frame = ScrollableFrame(root)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame.body, columns=("a",), show="headings", height=3)
    tree.pack(fill="x")
    root.geometry("400x150+0+0")
    root.update_idletasks()

    # Una tabla vacía no puede desplazarse: la rueda pasa a la columna.
    assert wheel_column(tree, 1) is frame


def test_sin_widget_o_sin_pasos_no_hay_columna(root):
    from widgets import wheel_column

    assert wheel_column(None, 1) is None
    assert wheel_column(root, 0) is None


def test_pasos_de_rueda_en_windows_y_x11():
    from widgets import _wheel_steps

    arriba = tk.Event()
    arriba.delta = 120
    abajo = tk.Event()
    abajo.delta = -120
    assert _wheel_steps(arriba) == -1
    assert _wheel_steps(abajo) == 1

    x11_arriba = tk.Event()
    x11_arriba.num = 4
    x11_abajo = tk.Event()
    x11_abajo.num = 5
    assert _wheel_steps(x11_arriba) == -1
    assert _wheel_steps(x11_abajo) == 1
