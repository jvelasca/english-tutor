"""Tests de los helpers puros de la GUI del launcher (ui.py)."""
import ui


def test_status_dot_known_states():
    assert ui.status_dot("ok") == "🟢"
    assert ui.status_dot("ready") == "🟢"
    assert ui.status_dot("error") == "🔴"
    assert ui.status_dot("unavailable") == "🟡"
    assert ui.status_dot("off") == "🔴"


def test_status_dot_unknown_falls_back():
    assert ui.status_dot("anything-else") == "⚪"


def test_status_color_maps_states():
    assert ui.status_color("ok") == ui.COLORS["success"]
    assert ui.status_color("on") == ui.COLORS["success"]
    assert ui.status_color("error") == ui.COLORS["error"]
    assert ui.status_color("off") == ui.COLORS["error"]
    assert ui.status_color("unavailable") == ui.COLORS["warning"]
    assert ui.status_color("unknown") == ui.COLORS["neutral"]


def test_status_color_unknown_falls_back_to_neutral():
    assert ui.status_color("anything-else") == ui.COLORS["neutral"]


def test_interface_state_servida():
    assert ui.interface_state(served=True, dist_available=True) == "🟢 Servida"
    # Aunque el artefacto falte, si responde se informa de lo observado.
    assert ui.interface_state(served=True, dist_available=False) == "🟢 Servida"


def test_interface_state_compilada_pero_sin_respuesta():
    """V3.75.3: el caso que engañaba al usuario.

    Con la UI compilada y el origen sin responder (puerto ocupado, o un servidor
    HTTP donde se espera HTTPS) la GUI decía «🔴 No compilada» y mandaba a
    compilar algo que ya estaba compilado.
    """
    estado = ui.interface_state(served=False, dist_available=True)

    assert estado == "🔴 No responde"
    assert "compilada" not in estado


def test_interface_state_sin_artefacto():
    assert ui.interface_state(served=False, dist_available=False) == "🔴 No compilada"


def test_icons_have_expected_keys():
    assert ui.SERVICE_ICONS["Backend"] == "🖥️"
    assert ui.SERVICE_ICONS["Ollama"] == "🦙"
    assert ui.SECTION_ICONS["Servicios"] == "🛠️"
    assert ui.SECTION_ICONS["Actividad del servidor"] == "📊"
    assert ui.SECTION_ICONS["Cookies navegador"] == "🍪"
    assert ui.ACTION_ICONS["start"] == "▶️"
    assert ui.ACTION_ICONS["restart"] == "🔁"


def test_server_activity_idle():
    status = {
        "generation": {"running": 0, "jobs": []},
        "rate_limited": {"rejected_last_minute": 0},
    }
    line, rejected = ui.server_activity(status)
    assert line == "En reposo"
    assert rejected == 0


def test_server_activity_generating():
    line, rejected = ui.server_activity(
        {
            "generation": {
                "running": 2,
                "jobs": [
                    {"level": "A1", "requested": 20},
                    {"level": "B1", "requested": 10},
                ],
            },
            "rate_limited": {"rejected_last_minute": 0},
        }
    )
    assert line == "Generando práctica extra (A1, B1)…"
    assert rejected == 0


def test_server_activity_with_rejections():
    status = {
        "generation": {"running": 0, "jobs": []},
        "rate_limited": {"rejected_last_minute": 7},
    }
    line, rejected = ui.server_activity(status)
    assert line == "En reposo"
    assert rejected == 7


def test_server_activity_none_backend_down():
    line, rejected = ui.server_activity(None)
    assert line == "No disponible (backend apagado)"
    assert rejected == 0


def test_read_log_tail_returns_last_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    (tmp_path / "backend.log").write_text("l1\nl2\nl3\nl4\n", encoding="utf-8")
    assert ui.read_log_tail("backend", max_lines=2) == "l3\nl4"


def test_read_log_tail_missing_file_is_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    assert ui.read_log_tail("frontend") == ""


def test_read_log_tail_solo_lee_la_cola_no_el_fichero_entero(monkeypatch, tmp_path):
    """V3.75.3: el coste no puede depender del tamaño histórico del log.

    Antes se hacía `read_text()` completo y se descartaba todo menos 250 líneas.
    Con `backend.log` en 87 MB y un refresco cada 2 s eso costaba 586 ms por
    lectura. Aquí se comprueba que un fichero enorme se sirve igual: si la
    implementación volviese a leerlo entero, el marcador del principio (que queda
    fuera de la ventana de ``TAIL_BYTES``) aparecería en el resultado.
    """
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    monkeypatch.setattr(ui, "TAIL_BYTES", 200)

    relleno = "\n".join(f"ruido-{i}" for i in range(50_000))
    (tmp_path / "backend.log").write_text(
        f"MARCADOR-DEL-PRINCIPIO\n{relleno}\nULTIMA-LINEA\n", encoding="utf-8"
    )

    tail = ui.read_log_tail("backend", max_lines=1)

    assert tail == "ULTIMA-LINEA"
    assert "MARCADOR-DEL-PRINCIPIO" not in tail


def test_read_log_tail_descarta_la_primera_linea_cortada(monkeypatch, tmp_path):
    """Al hacer *seek* la primera línea puede estar a medias: no se muestra."""
    monkeypatch.setattr(ui, "LOG_DIR", tmp_path)
    monkeypatch.setattr(ui, "TAIL_BYTES", 12)

    (tmp_path / "backend.log").write_text(
        "linea-larga-que-queda-cortada\nbuena\n", encoding="utf-8"
    )

    assert ui.read_log_tail("backend") == "buena"


def test_backend_failure_hint_puerto_ocupado():
    """V3.75.3: el `WinError 10048` del log se traduce a algo accionable."""
    log = (
        "INFO:     Started server process [1]\n"
        "ERROR:    [Errno 10048] error while attempting to bind on address "
        "('127.0.0.1', 8000): solo se permite un uso de cada direcci\u00f3n\n"
    )

    hint = ui.backend_failure_hint(log)

    assert hint is not None
    assert "puerto" in hint.lower()


def test_backend_failure_hint_certificado():
    log = 'ERROR:    [SSL: SSLV3_ALERT] load_cert_chain failed\n'

    hint = ui.backend_failure_hint(log)

    assert hint is not None
    assert "certificado" in hint.lower()


def test_backend_failure_hint_dependencia_que_falta():
    log = "ModuleNotFoundError: No module named 'piper'\n"

    hint = ui.backend_failure_hint(log)

    assert hint is not None
    assert "dependencia" in hint.lower()


def test_backend_failure_hint_devuelve_none_si_no_reconoce():
    """Sin firma conocida se devuelve None: no se inventa un diagnóstico."""
    assert ui.backend_failure_hint("INFO: todo fue bien\n") is None
    assert ui.backend_failure_hint("") is None
