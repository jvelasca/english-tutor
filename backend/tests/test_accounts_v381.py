"""Cuentas de la Fase 3 del P0 (V3.81): registro, sesión con contraseña, cambio de
credencial, baja autoservicio, verificación de email y consola del webmaster.

Este archivo es el **contrato** de la release, así que cada test dice qué se rompe
si falla, no qué línea ejecuta. Las reglas que fija, en orden de importancia:

1. **Sin la contraseña no se entra** cuando la cuenta tiene una. Es la Fase 3
   entera: hasta V3.80 bastaba con nombrar a alguien.
2. **El PIN ya no existe** y una contraseña temporal **obliga a cambiarla** antes
   de usar la app (si no, dejaría de ser temporal).
3. **Cambiar la contraseña tumba las sesiones vivas** de esa cuenta (época de
   autenticación), incluida la del intruso que hubiera dentro.
4. **La baja autoservicio no borra nada**: cierra la sesión y deja la cuenta
   fuera de servicio, pero la evidencia se queda donde estaba.
5. **La consola manda**: asignar credenciales, verificar el email a mano, forzar
   la baja con motivo y purgar solo lo que ya está fuera de servicio. Y cada una
   de esas decisiones deja historial.
"""
from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from repositories import users as users_repo
from services import credentials, sessions

_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}
_BUENA = "caballo-bateria-grapa"


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    credentials.reset_state()
    monkeypatch.setenv(config.ADMIN_PIN_ENV, _ADMIN_PIN)
    return tmp_path


def _registro(client, name: str, email: str, password: str = _BUENA):
    return client.post(
        "/api/users", json={"name": name, "email": email, "password": password}
    )


def _abrir(client, uid: str, password: str | None = None):
    body: dict = {"user_id": uid}
    if password is not None:
        body["password"] = password
    return client.post("/api/session", json=body)


# --- 1. Registro --------------------------------------------------------------


def test_el_registro_crea_una_cuenta_con_credencial_y_email_sin_verificar(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _registro(client, "Marta", "Marta@Example.COM")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["has_password"] is True
    assert cuerpo["email"] == "marta@example.com", "el email se guarda normalizado"
    assert cuerpo["email_verified"] is False
    assert _BUENA not in r.text, "la contraseña no vuelve en la respuesta"
    assert "password_hash" not in r.text, "ni su hash"


def test_el_registro_rechaza_email_repetido_aunque_cambie_la_caja(
    monkeypatch, tmp_path
):
    """El índice único es `NOCASE`: la comprobación previa tiene que coincidir.

    Si no coincidiera, el segundo alta reventaría con un error de integridad en vez
    de con un 409 que la UI puede explicar.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert _registro(client, "Marta", "marta@example.com").status_code == 200
        repetido = _registro(client, "Otra", "MARTA@example.com")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "EMAIL_TAKEN"


def test_el_registro_rechaza_un_email_que_no_lo_es(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _registro(client, "Marta", "sin-arroba")
    assert r.status_code == 400
    assert r.json()["detail"] == "EMAIL_FORMAT"


def test_el_registro_rechaza_una_contrasena_debil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _registro(client, "Marta", "marta@example.com", password="12345678")
    assert r.status_code == 400
    assert r.json()["detail"] == "PASSWORD_FORMAT"


def test_el_registro_deja_el_token_de_verificacion_emitiendo_y_sin_enviar(
    monkeypatch, tmp_path
):
    """Modo híbrido: sin SMTP **no se envía nada**, pero el token queda emitido.

    Es lo que permite que el webmaster confirme a mano (él ve el estado) y que el
    día que haya SMTP el flujo funcione sin cambiar el alta.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
    token_hash, sent_at = users_repo.get_email_verification(uid) or ("", "")
    assert token_hash, "la verificación queda emitida"
    assert sent_at, "y con fecha, que es lo que le da caducidad"


# --- 2. Sesión con contraseña -------------------------------------------------


def test_sin_contrasena_no_se_entra_cuando_la_cuenta_tiene_una(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        sin_nada = _abrir(client, uid)
        mala = _abrir(client, uid, "otra-cosa-que-no-es")
    assert sin_nada.status_code == 401
    assert sin_nada.json()["detail"] == "PASSWORD_REQUIRED"
    assert mala.status_code == 401
    assert mala.json()["detail"] == "PASSWORD_INVALID"


def test_con_la_contrasena_correcta_se_abre_la_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        r = _abrir(client, uid, _BUENA)
        assert r.status_code == 200
        assert f"{sessions.SESSION_COOKIE}=" in r.headers.get("set-cookie", "")
        assert client.get("/api/session").json()["id"] == uid


def test_una_cuenta_heredada_sin_credencial_sigue_entrando(monkeypatch, tmp_path):
    """La compatibilidad declarada: nadie queda fuera de la app por actualizar.

    El precio está escrito en el docstring del router: hasta que el webmaster
    asigne credenciales, esas cuentas entran nombrando. La consola las cuenta
    (`without_password`) para que ese número baje.
    """
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Heredada")["id"]
    with TestClient(app) as client:
        assert _abrir(client, uid).status_code == 200
        assert client.get("/api/session").json()["has_password"] is False


def test_una_cuenta_dada_de_baja_no_abre_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        r = _abrir(client, uid)
    assert r.status_code == 403
    assert r.json()["detail"] == "ACCOUNT_UNENROLLED"


def test_el_freno_frena_los_intentos_repetidos(monkeypatch, tmp_path):
    """Contra la fuerza bruta, lo que carga el peso no es la política: es el freno."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        for _ in range(credentials._FREE_ATTEMPTS + 1):
            _abrir(client, uid, "no-es-esta")
        frenada = _abrir(client, uid, "no-es-esta")
        # Y con la buena tampoco: el freno es de la cuenta, no del intento.
        correcta = _abrir(client, uid, _BUENA)
    assert frenada.status_code == 429
    assert frenada.json()["detail"] == "PASSWORD_THROTTLED"
    assert int(frenada.headers["retry-after"]) >= 1
    assert correcta.status_code == 429


# --- 3. Cambio de contraseña y épocas -----------------------------------------


def test_la_contrasena_temporal_obliga_a_cambiarla_antes_de_usar_la_app(
    monkeypatch, tmp_path
):
    """Una contraseña temporal que sobrevive al primer acceso no es temporal."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.set_credentials(
        uid, email="marta@example.com", password_hash=credentials.hash_password(_BUENA)
    )
    with TestClient(app) as client:
        assert _abrir(client, uid, _BUENA).status_code == 200
        bloqueado = client.get("/api/profile")
        assert bloqueado.status_code == 403
        assert bloqueado.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"
        # La sesión sí se puede consultar: es lo que deja a la UI saber qué pedir.
        assert client.get("/api/session").status_code == 200
        # Y el cambio está permitido, que es la salida del bloqueo.
        cambiada = client.put(
            "/api/session/password",
            json={"current_password": _BUENA, "new_password": "otra-cosa-larga-2026"},
        )
        assert cambiada.status_code == 200
        assert cambiada.json()["must_change_password"] is False
        assert client.get("/api/profile").status_code == 200


def test_el_cambio_de_contrasena_tumba_las_sesiones_vivas(monkeypatch, tmp_path):
    """El objetivo real del cambio: echar al que ya estaba dentro.

    Se guarda la cookie vieja a mano porque el cambio **reemite** la del que
    cambia (no debe echarse a sí mismo): lo que se comprueba es que ese mismo
    token, presentado otra vez, ya no vale.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        assert _abrir(client, uid, _BUENA).status_code == 200
        cookie_vieja = client.cookies.get(sessions.SESSION_COOKIE)
        assert cookie_vieja
        assert (
            client.put(
                "/api/session/password",
                json={
                    "current_password": _BUENA,
                    "new_password": "otra-cosa-larga-2026",
                },
            ).status_code
            == 200
        )
        client.cookies.set(sessions.SESSION_COOKIE, cookie_vieja)
        rancia = client.get("/api/session")
    assert rancia.status_code == 401
    assert rancia.json()["detail"] == "SESSION_STALE"


def test_el_cambio_exige_la_contrasena_actual(monkeypatch, tmp_path):
    """Sin esto, quien pase por delante de un equipo abierto se queda la cuenta."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        r = client.put(
            "/api/session/password",
            json={"current_password": "no-es-esta", "new_password": "otra-larga-2026"},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "PASSWORD_INVALID"


def test_el_cambio_rechaza_la_contrasena_nueva_debil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        r = client.put(
            "/api/session/password",
            json={"current_password": _BUENA, "new_password": "12345678"},
        )
    assert r.status_code == 400
    assert r.json()["detail"] == "PASSWORD_FORMAT"


def test_cerrar_sesion_retira_la_cookie(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        assert client.delete("/api/session").status_code == 200
        assert client.get("/api/session").status_code == 401


def test_cambiar_el_email_exige_la_contrasena_y_reinicia_la_verificacion(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        users_repo.mark_email_verified(uid)  # como si ya estuviera confirmado
        sin_permiso = client.put(
            "/api/session/email",
            json={"password": "no-es-esta", "email": "otra@example.com"},
        )
        con_permiso = client.put(
            "/api/session/email",
            json={"password": _BUENA, "email": "otra@example.com"},
        )
    assert sin_permiso.status_code == 401
    assert con_permiso.status_code == 200
    assert con_permiso.json()["email"] == "otra@example.com"
    assert con_permiso.json()["email_verified"] is False, (
        "el sello pertenecía al correo anterior"
    )


# --- 4. Verificación de email -------------------------------------------------


def _emitir_token(uid: str) -> str:
    """Emite un token como lo haría el alta, y devuelve el valor en claro.

    El alta no lo devuelve (viaja en el correo, que aquí no existe), así que el
    test lo emite por el mismo servicio que lo emitiría el envío: `credentials`.
    """
    token = credentials.new_email_token()
    assert users_repo.set_email_verification(uid, credentials.hash_email_token(token))
    return token


def test_el_enlace_de_verificacion_sella_el_email_sin_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        token = _emitir_token(uid)
        # Cliente **sin** cookie: el enlace puede abrirse en otro navegador.
        r = TestClient(app).post("/api/account/verify", json={"token": token})
    assert r.status_code == 200
    assert r.json()["email_verified"] is True
    assert users_repo.get_email_verification(uid)[0] == "", "el token se consume"


def test_el_token_de_verificacion_es_de_un_solo_uso(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        token = _emitir_token(uid)
        primero = client.post("/api/account/verify", json={"token": token})
        segundo = client.post("/api/account/verify", json={"token": token})
    assert primero.status_code == 200
    assert segundo.status_code == 400
    assert segundo.json()["detail"] == "VERIFY_TOKEN_INVALID"


def test_un_token_caducado_no_verifica(monkeypatch, tmp_path):
    """Una hora es la vida del enlace: un enlace filtrado no sirve dentro de un mes."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        token = _emitir_token(uid)
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "UPDATE users SET email_verify_sent_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00+00:00", uid),
            )
        r = client.post("/api/account/verify", json={"token": token})
    assert r.status_code == 400
    assert r.json()["detail"] == "VERIFY_TOKEN_EXPIRED"


def test_reenviar_la_verificacion_sin_smtp_no_finge_un_envio(monkeypatch, tmp_path):
    """El modo híbrido, dicho en la respuesta: `sent: false` y el porqué.

    Es la diferencia entre una app honesta y una que dice «correo enviado» cuando
    no hay ningún correo configurado.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        r = client.post("/api/account/resend-verification")
    assert r.status_code == 200
    assert r.json() == {"sent": False, "reason": "SMTP_NOT_CONFIGURED"}


def test_reenviar_sobre_un_email_ya_verificado_no_emite_token(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        users_repo.mark_email_verified(uid)
        r = client.post("/api/account/resend-verification")
    assert r.status_code == 200
    assert r.json() == {"sent": False, "reason": "ALREADY_VERIFIED"}


# --- 5. Baja autoservicio -----------------------------------------------------


def test_darse_de_baja_no_borra_nada_y_cierra_la_sesion(monkeypatch, tmp_path):
    """La frontera de la release: «baja» y «borrado» son cosas distintas.

    Se deja evidencia antes (una conversación) para poder afirmar que sigue ahí
    después: lo que se pierde al darse de baja es el **acceso**, no el trabajo.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        import asyncio

        from domain import conversations as conversation_service

        conversation = asyncio.run(conversation_service.create_conversation(uid))
        baja = client.post("/api/account/unenroll", json={"password": _BUENA})
        despues = client.get("/api/session")
    assert baja.status_code == 200
    assert baja.json()["unenrolled"] is True

    cuenta = users_repo.get_user(uid)
    assert cuenta is not None, "la cuenta sigue existiendo: solo se da de baja"
    assert cuenta["status"] == users_repo.STATUS_UNENROLLED
    assert conversation is not None
    assert (
        asyncio.run(conversation_service.get_conversation(conversation["id"], uid))
        is not None
    ), "la evidencia se queda donde estaba: lo que se pierde es el acceso"
    assert despues.status_code == 401, "la cookie se retiró al dar de baja"


def test_la_baja_exige_la_contrasena(monkeypatch, tmp_path):
    """Una baja que se puede provocar desde fuera no es un derecho, es un agujero."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        _abrir(client, uid, _BUENA)
        r = client.post("/api/account/unenroll", json={"password": "no-es-esta"})
        assert r.status_code == 401
        assert r.json()["detail"] == "PASSWORD_INVALID"
        assert users_repo.get_user(uid)["status"] == users_repo.STATUS_ACTIVE


# --- 6. La consola del webmaster ----------------------------------------------


def test_la_consola_lista_las_cuentas_con_sus_pendientes_y_sus_avisos(
    monkeypatch, tmp_path
):
    """Los tres números que el lanzador pinta, y que no pueden contradecirse.

    `without_password` es la lista de tareas de la migración: mientras no sea cero,
    esas cuentas siguen entrando nombrando. `unverified_email` es la otra mitad del
    modo híbrido.
    """
    _setup(monkeypatch, tmp_path)
    users_repo.create_user("Heredada")  # sin credencial
    with TestClient(app) as client:
        _registro(client, "Marta", "marta@example.com")
        r = client.get("/api/admin/users", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    cuerpo = r.json()
    # El recuento se compara contra la lista que el propio endpoint devuelve: el
    # `init_db` crea una cuenta por defecto *sin credencial* («Usuario»), y fijar un
    # número aquí convertiría este test en un test de esa cuenta. Lo que se afirma
    # es lo importante: «Heredada» sale en la lista de tareas y el contador la
    # cuenta.
    sin_credencial = [u for u in cuerpo["users"] if not u["has_password"]]
    assert "Heredada" in {u["name"] for u in sin_credencial}
    assert "Marta" not in {u["name"] for u in sin_credencial}
    assert cuerpo["without_password"] == len(sin_credencial) == 2
    assert cuerpo["unverified_email"] == 1
    assert cuerpo["pending"] == 0
    nombres = {u["name"] for u in cuerpo["users"]}
    assert {"Heredada", "Marta"} <= nombres


def test_la_consola_asigna_credenciales_con_temporal_si_no_se_da_contrasena(
    monkeypatch, tmp_path
):
    """El webmaster no tiene que inventarse una contraseña para poder entregarla."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Heredada")["id"]
    with TestClient(app) as client:
        r = client.post(
            f"/api/admin/users/{uid}/credentials",
            json={"email": "heredada@example.com"},
            headers=_ADMIN_HEADERS,
        )
    assert r.status_code == 200
    cuerpo = r.json()
    temporal = cuerpo["temporary_password"]
    assert temporal, "sin contraseña se genera una temporal"
    assert credentials.verify_password(
        users_repo.get_password_hash(uid) or "", temporal
    ), "y es la que quedó guardada"
    assert cuerpo["user"]["must_change_password"] is True
    assert cuerpo["user"]["email"] == "heredada@example.com"
    # Y ya no entra nombrando: la credencial existe.
    with TestClient(app) as client:
        assert _abrir(client, uid).status_code == 401


def test_la_consola_verifica_el_email_a_mano(monkeypatch, tmp_path):
    """Modo híbrido sin SMTP: la firma la pone el webmaster, que tiene a la persona
    delante."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        r = client.post(
            f"/api/admin/users/{uid}/verify-email", headers=_ADMIN_HEADERS
        )
    assert r.status_code == 200
    assert r.json()["email_verified"] is True


def test_verificar_a_mano_una_cuenta_sin_email_no_hace_nada(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Heredada")["id"]
    with TestClient(app) as client:
        r = client.post(
            f"/api/admin/users/{uid}/verify-email", headers=_ADMIN_HEADERS
        )
    assert r.status_code == 409


def test_forzar_la_baja_exige_motivo_y_lo_deja_escrito(monkeypatch, tmp_path):
    """Una decisión que se le impone a un alumno tiene que poder explicarse."""
    _setup(monkeypatch, tmp_path)
    users_repo.create_user("Marta")
    uid = users_repo.list_users()[0]["id"]
    with TestClient(app) as client:
        sin_motivo = client.post(
            f"/api/admin/users/{uid}/unenroll", json={"reason": ""},
            headers=_ADMIN_HEADERS,
        )
        forzada = client.post(
            f"/api/admin/users/{uid}/unenroll",
            json={"reason": "cuenta duplicada"},
            headers=_ADMIN_HEADERS,
        )
    assert sin_motivo.status_code == 422, "el motivo es obligatorio"
    assert forzada.status_code == 200
    assert forzada.json()["status"] == users_repo.STATUS_UNENROLLED
    eventos = users_repo.list_events(uid)
    assert any(e["action"] == users_repo.EVENT_FORCE_UNENROLLED for e in eventos)
    assert any("cuenta duplicada" in e["note"] for e in eventos)


def test_reactivar_devuelve_la_cuenta_al_servicio(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        r = client.post(
            f"/api/admin/users/{uid}/status",
            json={"status": "active"},
            headers=_ADMIN_HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["status"] == users_repo.STATUS_ACTIVE


def test_el_historial_se_lee_del_mas_reciente_al_mas_antiguo(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _registro(client, "Marta", "marta@example.com").json()["id"]
        client.post(
            f"/api/admin/users/{uid}/unenroll",
            json={"reason": "petición de la familia"},
            headers=_ADMIN_HEADERS,
        )
        r = client.get(f"/api/admin/users/{uid}/events", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    acciones = [e["action"] for e in r.json()["events"]]
    assert acciones[0] == users_repo.EVENT_FORCE_UNENROLLED
    assert users_repo.EVENT_CREATED in acciones
    assert r.json()["events"][0]["actor"] == "webmaster"


def test_purgar_exige_que_la_cuenta_este_fuera_de_servicio(monkeypatch, tmp_path):
    """Purgar una cuenta activa es destruir evidencia de alguien que la usa ahora."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    with TestClient(app) as client:
        activa = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Marta"},
            headers=_ADMIN_HEADERS,
        )
        assert activa.status_code == 409
        assert users_repo.get_user(uid) is not None, "el intento en falso no borró nada"

        users_repo.set_unenrolled(uid, enrolled=False)
        bien = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Marta"},
            headers=_ADMIN_HEADERS,
        )
    assert bien.status_code == 200
    assert users_repo.get_user(uid) is None


def test_purgar_exige_el_nombre_exacto(monkeypatch, tmp_path):
    """La confirmación por nombre es lo que evita un clic de más sobre la cuenta
    equivocada (y se perdona el tecleo: mayúsculas y espacios)."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        r = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Marta Ruiz"},
            headers=_ADMIN_HEADERS,
        )
    assert r.status_code == 409
    assert users_repo.get_user(uid) is not None


def test_la_purga_deja_el_historial_para_poder_explicarla(monkeypatch, tmp_path):
    """Es lo único que queda después: si se borra, nadie puede responder «¿quién y
    por qué?»."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "marta"},
            headers=_ADMIN_HEADERS,
        )
    eventos = users_repo.list_events(uid)
    assert any(e["action"] == users_repo.EVENT_PURGED for e in eventos)
    assert any("copia" in e["note"] for e in eventos)


def test_toda_la_consola_exige_el_candado(monkeypatch, tmp_path):
    """Sin PIN de administración no hay consola, ni siquiera desde el equipo."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    rutas = [
        ("get", "/api/admin/users", None),
        ("get", f"/api/admin/users/{uid}/events", None),
        ("post", f"/api/admin/users/{uid}/verify-email", None),
        ("post", f"/api/admin/users/{uid}/unenroll", {"reason": "x"}),
    ]
    with TestClient(app) as client:
        for metodo, ruta, body in rutas:
            r = getattr(client, metodo)(ruta, **({"json": body} if body else {}))
            assert r.status_code == 401, f"{ruta} respondió sin PIN: {r.status_code}"
