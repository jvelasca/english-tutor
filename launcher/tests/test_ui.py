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


# --- Cuentas (V3.81): la consola del webmaster en el lanzador ------------------


def test_pending_summary_concuerda_en_singular_y_plural():
    assert ui.pending_summary(0) == "Sin solicitudes pendientes"
    assert ui.pending_summary(1) == "1 solicitud pendiente"
    # Un contador negativo no existe, pero si llegara no puede decir «-1 solicitud».
    assert ui.pending_summary(-3) == "Sin solicitudes pendientes"
    assert ui.pending_summary(4) == "4 solicitudes pendientes"


def test_la_seccion_usuarios_tiene_icono_y_etiquetas_de_estado():
    """La sección se pinta desde `SECTION_ICONS`: sin clave, sale sin icono."""
    assert "Usuarios" in ui.SECTION_ICONS
    assert "Actividad por usuario" in ui.SECTION_ICONS
    # El nombre viejo ya no existe: dos secciones con el mismo título serían
    # indistinguibles en la ventana.
    assert "Perfiles" not in ui.SECTION_ICONS
    assert ui.USER_STATUS_LABELS["active"] == "Activo"
    assert ui.USER_STATUS_LABELS["disabled"] == "Desactivado"
    # V3.81: la baja autoservicio es un estado propio y tiene que poder leerse.
    assert ui.USER_STATUS_LABELS["unenrolled"] == "Dado de baja"
    assert set(ui.REQUEST_KIND_LABELS) == {"create", "delete"}


def test_duplicate_user_ids_marca_los_nombres_repetidos():
    """V3.80.2: dos «J.A» activos son indistinguibles en esta tabla.

    El webmaster purga por nombre, así que marcar el repetido es lo que evita
    que borre la evidencia del usuario equivocado.
    """
    users = [
        {"id": "1", "name": "J.A"},
        {"id": "2", "name": "Paz"},
        {"id": "3", "name": "J.A"},
    ]
    assert ui.duplicate_user_ids(users) == {"1", "3"}


def test_duplicate_user_ids_ignora_espacios_y_mayusculas():
    """«ana» y «Ana  » son el mismo nombre, igual que para el alta del backend."""
    users = [{"id": "1", "name": "ana"}, {"id": "2", "name": "Ana  "}]
    assert ui.duplicate_user_ids(users) == {"1", "2"}


def test_duplicate_user_ids_sin_repetidos_es_vacio():
    users = [{"id": "1", "name": "Ana"}, {"id": "2", "name": "Beto"}]
    assert ui.duplicate_user_ids(users) == set()


def test_duplicate_user_ids_con_nombres_vacios_no_marca():
    # Un nombre en blanco no es «repetido»: es otra cosa (y el alta lo rechaza).
    users = [{"id": "1", "name": "  "}, {"id": "2", "name": ""}]
    assert ui.duplicate_user_ids(users) == set()


def test_user_row_label_avisa_del_nombre_repetido():
    repetido = {"id": "1", "name": "J.A"}
    unico = {"id": "2", "name": "Paz"}
    dups = {"1"}
    assert ui.user_row_label(repetido, dups) == "⚠️ J.A (nombre repetido)"
    assert ui.user_row_label(unico, dups) == "👤 Paz"


def test_user_row_label_no_inventa_marcas_sin_repetidos():
    user = {"id": "9", "name": "Ana"}
    assert ui.user_row_label(user, set()) == "👤 Ana"



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


def test_request_row_de_una_baja_de_una_cuenta_que_ya_no_esta():
    """Ni un id crudo en pantalla: se dice que la cuenta ya no existe."""
    _, target, _ = ui.request_row({"kind": "delete", "user_id": "abc123"}, {})

    assert target == "(cuenta que ya no existe)"


def test_request_row_de_un_tipo_desconocido_no_se_traga_la_fila():
    """Un `kind` nuevo del backend tiene que verse, no desaparecer."""
    kind, _, _ = ui.request_row({"kind": "traslado"})

    assert kind == "traslado"


def test_user_row_ensena_estado_email_y_credencial_sin_ensenar_secretos():
    fila = ui.user_row(
        {
            "name": "Marta",
            "status": "disabled",
            "email": "marta@example.com",
            "email_verified": True,
            "has_password": True,
            "created_at": "2026-09-21T22:34:00Z",
        },
        set(),
    )

    assert fila == (
        "👤 Marta",
        "Desactivado",
        "✉️ marta@example.com",
        "🔑 Con contraseña",
        "2026-09-21 22:34",
    )
    # Y una cuenta sin credencial lo dice explícitamente: es la lista de tareas
    # que esta release viene a cerrar, y tiene que verse de un vistazo.
    assert ui.user_row({"name": "Luis", "has_password": False}, set())[3] == (
        "⚠️ Sin contraseña"
    )


def test_user_row_marca_el_email_sin_verificar_y_la_ausencia_de_email():
    """El chip «sin verificar» no es un error: es lo que el webmaster sella a mano."""
    sin_verificar = ui.user_row(
        {"name": "Ana", "email": "ana@example.com", "email_verified": False}, set()
    )
    sin_email = ui.user_row({"name": "Beto"}, set())

    assert sin_verificar[2] == "✉️ ana@example.com · sin verificar"
    assert sin_email[2] == "—"


def test_user_row_marca_el_nombre_repetido_igual_que_la_etiqueta():
    fila = ui.user_row({"name": "J.A", "has_password": True}, {"u1"})
    fila_con_id = ui.user_row({"id": "u1", "name": "J.A", "has_password": True}, {"u1"})

    assert fila[0] == "👤 J.A", "sin id no hay nada que marcar"
    assert fila_con_id[0] == "⚠️ J.A (nombre repetido)"


def test_un_estado_desconocido_se_ensena_en_crudo_no_se_oculta():
    """Un estado nuevo del backend tiene que verse, no pintarse como activo."""
    fila = ui.user_row({"name": "Ana", "status": "suspendido"}, set())

    assert fila[1] == "suspendido"


def test_accounts_tasks_cuenta_las_dos_tareas_del_webmaster():
    todo_ok = ui.accounts_tasks(0, 0)
    pendiente = ui.accounts_tasks(2, 1)

    assert "✅" in todo_ok
    assert "2 cuentas sin contraseña" in pendiente
    assert "1 email sin verificar" in pendiente


def test_accounts_tasks_concuerda_en_singular():
    assert "1 cuenta sin contraseña" in ui.accounts_tasks(1, 0)
    assert "1 email sin verificar" in ui.accounts_tasks(0, 1)


def test_event_row_traduce_las_acciones_del_historial():
    when, what, who, note = ui.event_row(
        {
            "created_at": "2026-09-22T18:05:00Z",
            "action": "force_unenrolled",
            "actor": "webmaster",
            "note": "suplantación",
        }
    )

    assert when == "2026-09-22 18:05"
    assert "Baja forzada" in what
    assert who == "webmaster"
    assert note == "suplantación"


def test_event_row_de_una_accion_desconocida_no_se_traga_la_fila():
    """Si el backend añade un evento nuevo, tiene que verse que pasó algo."""
    assert ui.event_row({"action": "traslado"})[1] == "traslado"


def test_purge_block_reason_exige_la_cuenta_fuera_de_servicio():
    """El backend no purga una cuenta activa; la consola lo dice antes de pedir
    que se teclee el nombre."""
    assert ui.purge_block_reason({"status": "active"})
    assert ui.purge_block_reason({"status": "disabled"}) == ""
    assert ui.purge_block_reason({"status": "unenrolled"}) == ""


def test_smtp_state_label_distingue_tres_estados_no_dos():
    """«Configurado» y «con contraseña» son cosas distintas: un servidor local de
    reenvío no pide credenciales, y confundirlos manda a buscar una que no existe."""
    assert "sin configurar" in ui.smtp_state_label(False, False)
    assert "contraseña guardada" in ui.smtp_state_label(True, True)
    assert "no pide contraseña" in ui.smtp_state_label(True, False)


def test_sin_poder_preguntar_al_servidor_no_se_afirma_nada_sobre_el():
    """Sin respuesta del backend (sin PIN, servidor caído) la frase es la local y
    no se añade ninguna promesa sobre lo que el servidor ve."""
    assert ui.smtp_reconcile_label(True, True, None) == ui.smtp_state_label(True, True)
    assert ui.smtp_reconcile_label(False, False, None) == ui.smtp_state_label(
        False, False
    )


def test_si_el_servidor_coincide_la_frase_no_se_ensucia():
    backend = {"configured": True, "has_password": False}

    assert ui.smtp_reconcile_label(True, False, backend) == ui.smtp_state_label(
        True, False
    )


def test_un_correo_recien_guardado_avisa_de_que_el_servidor_aun_no_lo_ve():
    """El launcher escribe el JSON y el backend lo lee al arrancar: entre guardar y
    reiniciar hay un hueco en el que los dos estados discrepan, y callarlo sería
    enseñar lo local como si fuera lo del servidor."""
    backend = {"configured": False, "has_password": False}

    frase = ui.smtp_reconcile_label(True, True, backend)

    assert "configurado" in frase
    assert "todavía no lo ve" in frase
    assert "al arrancar" in frase


def test_un_correo_que_solo_ve_el_servidor_se_denuncia_no_se_esconde():
    """Variables de entorno puestas a mano: el servidor manda correo y esta consola
    no lo sabe. Decir «sin configurar» sería mentir sobre lo que de verdad pasa."""
    backend = {"configured": True, "has_password": True}

    frase = ui.smtp_reconcile_label(False, False, backend)

    assert "sin configurar" not in frase
    assert "no está guardado en esta consola" in frase
    assert "no se puede gestionar" in frase


def test_admin_state_label_dice_las_dos_caras_del_candado():
    habilitada = ui.admin_state_label(True)
    cerrada = ui.admin_state_label(False)

    assert "habilitada" in habilitada
    assert "deshabilitada" in cerrada
    # Y cierra diciendo qué hacer, no solo qué falta.
    assert "PIN" in cerrada


# --- La cola: que un fallo no se lea como «no hay nada» (V3.80.1) --------------
#
# El fallo que motivó estos tests: `_apply_accounts` pintaba «Sin solicitudes
# pendientes» tanto cuando la cola estaba vacía como cuando la consulta al backend
# había fallado (401 sin PIN, 403 fuera del equipo, servidor caído). Estas son las
# dos mitades del candado: nunca afirmar un cero que no se ha comprobado.


def test_pending_view_sin_pin_con_pendientes_las_anuncia():
    """La baja del alumno no puede quedarse invisible por no haber PIN."""
    frase, filas = ui.pending_view(
        pin_set=False, db_count=1, ok=False, requests=None
    )

    assert "1 solicitud pendiente" in frase
    assert "PIN" in frase
    assert "Sin solicitudes pendientes" not in frase
    assert filas == []


def test_pending_view_sin_pin_con_la_cola_vacia_lo_dice_como_deshabilitada():
    frase, _ = ui.pending_view(pin_set=False, db_count=0, ok=False)

    assert "deshabilitada" in frase
    assert "Sin solicitudes pendientes" not in frase


def test_pending_view_sin_pin_y_sin_poder_leer_la_bd_lo_admite():
    """`None` no es cero: se admite que no se sabe, no se afirma que no hay."""
    frase, _ = ui.pending_view(pin_set=False, db_count=None, ok=False)

    assert "no se pudo leer" in frase
    assert "Sin solicitudes pendientes" not in frase


def test_pending_view_con_pin_y_fallo_muestra_el_motivo_no_un_cero():
    frase, filas = ui.pending_view(
        pin_set=True,
        db_count=1,
        ok=False,
        error="El backend no acepta el PIN de administración.",
    )

    assert "No se pudo consultar la cola" in frase
    assert "PIN" in frase
    assert "Sin solicitudes pendientes" not in frase
    assert filas == []


def test_pending_view_con_pin_y_ok_lista_las_filas_y_traduce_la_baja():
    requests = [
        {"kind": "delete", "user_id": "abc123", "requested_at": "2026-09-22T12:47:0"},
    ]
    frase, filas = ui.pending_view(
        pin_set=True,
        db_count=1,
        ok=True,
        requests=requests,
        names={"abc123": "JA"},
    )

    assert frase == "1 solicitud pendiente"
    assert filas == [("🗑️ Baja", "JA", "2026-09-22 12:47")]


def test_pending_view_con_pin_y_ok_pero_vacia_si_dice_que_no_hay_nada():
    """El «Sin solicitudes pendientes» legítimo: se ha comprobado y no hay."""
    frase, filas = ui.pending_view(pin_set=True, db_count=0, ok=True, requests=[])

    assert frase == "Sin solicitudes pendientes"
    assert filas == []


def test_pending_view_cuenta_lo_que_pinta_no_lo_que_le_dicen():
    """El número y la lista no se contradicen: manda lo que se va a pintar."""
    requests = [
        {"kind": "create", "display_name": "Ana"},
        {"kind": "create", "display_name": "Luis"},
    ]
    frase, filas = ui.pending_view(
        pin_set=True, db_count=5, ok=True, requests=requests
    )

    assert frase == "2 solicitudes pendientes"
    assert len(filas) == 2

