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


# --- Perfiles (V3.77): el webmaster lee la cola en el lanzador -----------------


def test_pending_summary_concuerda_en_singular_y_plural():
    assert ui.pending_summary(0) == "Sin solicitudes pendientes"
    assert ui.pending_summary(1) == "1 solicitud pendiente"
    # Un contador negativo no existe, pero si llegara no puede decir «-1 solicitud».
    assert ui.pending_summary(-3) == "Sin solicitudes pendientes"
    assert ui.pending_summary(4) == "4 solicitudes pendientes"


def test_la_seccion_perfiles_tiene_icono_y_etiquetas_de_estado():
    """La sección se pinta desde `SECTION_ICONS`: sin clave, sale sin icono."""
    assert "Perfiles" in ui.SECTION_ICONS
    assert ui.PROFILE_STATUS_LABELS["active"] == "Activo"
    assert ui.PROFILE_STATUS_LABELS["disabled"] == "Desactivado"
    assert set(ui.REQUEST_KIND_LABELS) == {"create", "delete"}


def test_request_row_de_una_alta_muestra_el_nombre_y_la_nota():
    kind, target, when = ui.request_row(
        {
            "kind": "create",
            "display_name": "Marta",
            "note": "3.º ESO",
            "requested_at": "2026-09-21T22:34:00Z",
        }
    )

    assert kind == "🆕 Alta"
    assert target == "Marta — 3.º ESO"
    assert when == "2026-09-21 22:34"


def test_request_row_de_una_baja_traduce_el_id_a_nombre():
    """El webmaster decide sobre un nombre, no sobre un identificador."""
    kind, target, _ = ui.request_row(
        {"kind": "delete", "user_id": "abc123", "requested_at": "2026-09-21T10:00:00Z"},
        {"abc123": "Marta"},
    )

    assert kind == "🗑️ Baja"
    assert target == "Marta"


def test_request_row_de_una_baja_de_un_perfil_que_ya_no_esta():
    """Ni un id crudo en pantalla: se dice que el perfil ya no existe."""
    _, target, _ = ui.request_row({"kind": "delete", "user_id": "abc123"}, {})

    assert target == "(perfil que ya no existe)"


def test_request_row_de_un_tipo_desconocido_no_se_traga_la_fila():
    """Un `kind` nuevo del backend tiene que verse, no desaparecer."""
    kind, _, _ = ui.request_row({"kind": "traslado"})

    assert kind == "traslado"


def test_profile_row_informa_del_pin_sin_ensenarlo():
    fila = ui.profile_row(
        {
            "name": "Marta",
            "status": "disabled",
            "has_pin": True,
            "created_at": "2026-09-21T22:34:00Z",
        }
    )

    assert fila == ("👤 Marta", "Desactivado", "🔑 Con PIN", "2026-09-21 22:34")
    # Y un perfil sin credencial lo dice explícitamente: es una consecuencia
    # declarada que el webmaster debe poder ver de un vistazo.
    assert ui.profile_row({"name": "Luis", "has_pin": False})[2] == "Sin PIN"


def test_admin_state_label_dice_las_dos_caras_del_candado():
    habilitada = ui.admin_state_label(True)
    cerrada = ui.admin_state_label(False)

    assert "habilitada" in habilitada
    assert "deshabilitada" in cerrada
    # Y cierra diciendo qué hacer, no solo qué falta.
    assert "PIN" in cerrada
