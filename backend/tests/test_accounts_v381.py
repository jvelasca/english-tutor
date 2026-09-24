"""Cuentas de la Fase 3 del P0 (V3.81): ciclo de vida, contraseña, cambio de
credencial, baja autoservicio, verificación de email y consola del webmaster.

Este archivo es el **contrato** de la release, así que cada test dice qué se rompe
si falla, no qué línea ejecuta. Las reglas que fija, en orden de importancia:

1. **Sin la contraseña no se entra.** Es la Fase 3 entera: hasta V3.80 bastaba con
   nombrar a alguien. V3.82 lo cierra del todo —la entrada es email + contraseña y
   una cuenta sin contraseña es una **invitación pendiente**, no una cuenta— y por
   eso aquí también se prueba que el alta pública por API ya no existe.
2. **El PIN ya no existe** y una contraseña temporal **obliga a cambiarla** antes
   de usar la app (si no, dejaría de ser temporal).
3. **Cambiar la contraseña tumba las sesiones vivas** de esa cuenta (época de
   autenticación), incluida la del intruso que hubiera dentro.
4. **La baja autoservicio no borra nada**: cierra la sesión y deja la cuenta
   fuera de servicio, pero la evidencia se queda donde estaba.
5. **La consola manda**: alta directa, credenciales, verificar el email a mano,
   forzar la baja con motivo y purgar solo lo que ya está fuera de servicio. Y
   cada una de esas decisiones deja historial.

El flujo **nuevo** de V3.82 —solicitud con email y avatar, aprobación con
invitación, activación por enlace, olvido de contraseña— tiene su propio
contrato en `test_accounts_v382.py`; aquí se prueba el ciclo de vida de una
cuenta que ya existe.
"""
from __future__ import annotations

import sqlite3
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


def _alta(client, name: str, email: str = "", password: str = _BUENA):
    """Alta **del webmaster** (V3.82): `POST /api/admin/users`, con el PIN.

    Hasta V3.81 esto era `POST /api/users`, abierto a cualquiera. V3.82 retira esa
    puerta: una cuenta nace de una **solicitud** que el webmaster autoriza, o de
    esta alta directa cuando tiene a la persona delante. Este fichero prueba el
    ciclo de vida de una cuenta ya creada, así que usa la vía que queda.

    Devuelve la respuesta (no el id) porque varios tests afirman sobre el **cuerpo**
    —que la contraseña no vuelva, que el email venga normalizado—.
    """
    return client.post(
        "/api/admin/users",
        json={"name": name, "email": email, "password": password},
        headers=_ADMIN_HEADERS,
    )


def _cuenta(name: str, email: str, password: str = _BUENA) -> str:
    """Crea una cuenta **ya en marcha** (email + contraseña) por repositorio.

    Es la preparación del escenario, no el objeto de la prueba: el **alta** tiene
    sus propios tests arriba (la del webmaster) y su camino nuevo en
    `test_accounts_v382.py` (solicitud + invitación). Se hace por repositorio
    porque el alta por API marca `must_change_password`, y pasar por ella
    obligaría a cambiar la contraseña en cada test que solo quiere una cuenta
    normal. El alta se prueba donde se prueba; aquí solo se necesita el punto de
    partida.
    """
    uid = users_repo.create_user(name, email=email)["id"]
    assert users_repo.set_password_hash(uid, credentials.hash_password(password))
    # El alta de verdad deja este hito (`EVENT_CREATED`, sin nota). Se replica para
    # que el historial de la cuenta preparada sea el mismo que el de una cuenta
    # creada por la API: si no, los tests de historial probarían una cuenta que
    # nunca pasó por el alta.
    users_repo.record_event(
        subject_id=uid, subject_name=name, action=users_repo.EVENT_CREATED
    )
    return uid


def _abrir(client, email: str, password: str = _BUENA):
    """Abre sesión como esa cuenta. V3.82: **email + contraseña**, sin `user_id`."""
    return client.post("/api/session", json={"email": email, "password": password})


# --- 1. Alta y credencial -----------------------------------------------------


def test_el_alta_del_webmaster_crea_una_cuenta_con_credencial_y_email_sin_verificar(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _alta(client, "Marta", "Marta@Example.COM")
    assert r.status_code == 200, r.text
    cuerpo = r.json()["user"]
    assert cuerpo["has_password"] is True
    assert cuerpo["email"] == "marta@example.com", "el email se guarda normalizado"
    assert cuerpo["email_verified"] is False
    assert _BUENA not in r.text, "la contraseña no vuelve en la respuesta"
    assert "password_hash" not in r.text, "ni su hash"


def test_la_puerta_publica_de_alta_ya_no_existe(monkeypatch, tmp_path):
    """V3.82 cierra `POST /api/users`: el alta se pide y se autoriza.

    Es lo que impide que cualquiera se cree una cuenta —y con ella un hueco en la
    app— sin pasar por el webmaster. La ruta desaparece, así que el método ya no
    está permitido en `/api/users` (que sigue existiendo para **leer** con sesión).
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/users",
            json={"name": "Colada", "email": "colada@example.com", "password": _BUENA},
        )
    assert r.status_code == 405


def test_el_alta_del_webmaster_rechaza_email_repetido_aunque_cambie_la_caja(
    monkeypatch, tmp_path
):
    """El índice único es `NOCASE`: la comprobación previa tiene que coincidir.

    Si no coincidiera, la segunda alta reventaría con un error de integridad en vez
    de con un 409 que la UI puede explicar.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert _alta(client, "Marta", "marta@example.com").status_code == 200
        repetido = _alta(client, "Otra", "MARTA@example.com")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "EMAIL_TAKEN"


def test_el_alta_del_webmaster_rechaza_un_email_que_no_lo_es(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _alta(client, "Marta", "sin-arroba")
    assert r.status_code == 400
    assert r.json()["detail"] == "EMAIL_FORMAT"


def test_el_alta_del_webmaster_rechaza_una_contrasena_debil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _alta(client, "Marta", "marta@example.com", password="12345678")
    assert r.status_code == 400
    assert r.json()["detail"] == "PASSWORD_FORMAT"


# --- 2. Sesión con contraseña -------------------------------------------------


def test_una_contrasena_que_no_cuadra_no_entra_y_no_distingue_de_un_email_sin_cuenta(
    monkeypatch, tmp_path
):
    """V3.82: la entrada es email + contraseña y falla con **un solo** mensaje.

    Si «ese correo no tiene cuenta» y «la contraseña no es» se distinguieran, el
    login sería un buscador de correos registrados.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _cuenta("Marta", "marta@example.com")
        mala = _abrir(client, "marta@example.com", "otra-cosa-que-no-es")
        sin_cuenta = _abrir(client, "nadie@example.com", _BUENA)

    assert mala.status_code == 401
    assert mala.json()["detail"] == "INVALID_CREDENTIALS"
    assert sin_cuenta.json() == mala.json()
    assert sessions.SESSION_COOKIE not in mala.headers.get("set-cookie", "")


def test_con_la_contrasena_correcta_se_abre_la_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
        r = _abrir(client, "marta@example.com")
        assert r.status_code == 200
        assert f"{sessions.SESSION_COOKIE}=" in r.headers.get("set-cookie", "")
        assert client.get("/api/session").json()["id"] == uid


def test_una_cuenta_sin_credencial_ya_no_entra_nombrando(monkeypatch, tmp_path):
    """La compatibilidad de V3.81 se retira: era el agujero que cerraba G0.

    Hasta V3.81 una cuenta con `password_hash == ''` entraba con solo nombrarse, y
    eso es exactamente lo que permitía entrar como J.A o Paz. Ahora esa cuenta es
    una **invitación pendiente**: existe, tiene email, y responde
    `ACCOUNT_NOT_ACTIVATED` en vez de dejar pasar.
    """
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Heredada", email="heredada@example.com")["id"]
    with TestClient(app) as client:
        r = _abrir(client, "heredada@example.com", "lo-que-sea")

    assert r.status_code == 403
    assert r.json()["detail"] == "ACCOUNT_NOT_ACTIVATED"
    assert sessions.SESSION_COOKIE not in r.headers.get("set-cookie", "")
    # Y la cuenta sigue siendo la misma: no se ha creado nada por el camino.
    assert users_repo.get_user(uid)["email"] == "heredada@example.com"


def test_una_cuenta_heredada_sin_email_no_es_ni_localizable(monkeypatch, tmp_path):
    """Sin email no hay forma de nombrarla en la entrada nueva.

    Es el caso de las cuentas anteriores a V3.81 que nunca recibieron correo: no
    pueden entrar **ni** con la contraseña correcta, porque el login se identifica
    por email. La salida es la migración (`backend/scripts/migrate_legacy_accounts.py`),
    no una puerta trasera.
    """
    _setup(monkeypatch, tmp_path)
    users_repo.create_user("Heredada")
    with TestClient(app) as client:
        r = _abrir(client, "heredada@example.com", _BUENA)
    assert r.status_code == 401
    assert r.json()["detail"] == "INVALID_CREDENTIALS"


def test_una_cuenta_dada_de_baja_no_abre_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        r = _abrir(client, "marta@example.com")
    assert r.status_code == 403
    assert r.json()["detail"] == "ACCOUNT_UNENROLLED"


def test_el_freno_frena_los_intentos_repetidos(monkeypatch, tmp_path):
    """Contra la fuerza bruta, lo que carga el peso no es la política: es el freno."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _cuenta("Marta", "marta@example.com")
        for _ in range(credentials._FREE_ATTEMPTS + 1):
            _abrir(client, "marta@example.com", "no-es-esta")
        frenada = _abrir(client, "marta@example.com", "no-es-esta")
        # Y con la buena tampoco: el freno es de la cuenta, no del intento.
        correcta = _abrir(client, "marta@example.com")
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
        assert _abrir(client, "marta@example.com").status_code == 200
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
        _cuenta("Marta", "marta@example.com")
        assert _abrir(client, "marta@example.com").status_code == 200
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
        _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
        r = client.put(
            "/api/session/password",
            json={"current_password": "no-es-esta", "new_password": "otra-larga-2026"},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "PASSWORD_INVALID"


def test_el_cambio_rechaza_la_contrasena_nueva_debil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
        r = client.put(
            "/api/session/password",
            json={"current_password": _BUENA, "new_password": "12345678"},
        )
    assert r.status_code == 400
    assert r.json()["detail"] == "PASSWORD_FORMAT"


def test_cerrar_sesion_retira_la_cookie(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
        assert client.delete("/api/session").status_code == 200
        assert client.get("/api/session").status_code == 401


def test_cambiar_el_email_exige_la_contrasena_y_reinicia_la_verificacion(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
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
    uid = _cuenta("Marta", "marta@example.com")
    token = _emitir_token(uid)
    # Cliente **sin** cookie: el enlace puede abrirse en otro navegador.
    r = TestClient(app).post("/api/account/verify", json={"token": token})
    assert r.status_code == 200
    assert r.json()["email_verified"] is True
    assert users_repo.get_email_verification(uid)[0] == "", "el token se consume"


def test_el_token_de_verificacion_es_de_un_solo_uso(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
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
        uid = _cuenta("Marta", "marta@example.com")
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
    no hay ningún correo configurado. Y el token queda **emitido** igualmente: es
    lo que permite que el webmaster confirme a mano y que el día que haya SMTP el
    flujo funcione sin cambiar nada.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
        r = client.post("/api/account/resend-verification")
    assert r.status_code == 200
    assert r.json() == {"sent": False, "reason": "SMTP_NOT_CONFIGURED"}
    token_hash, sent_at = users_repo.get_email_verification(uid) or ("", "")
    assert token_hash, "la verificación queda emitida aunque no se envíe"
    assert sent_at, "y con fecha, que es lo que le da caducidad"


def test_reenviar_sobre_un_email_ya_verificado_no_emite_token(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
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
        uid = _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
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
        uid = _cuenta("Marta", "marta@example.com")
        _abrir(client, "marta@example.com")
        r = client.post("/api/account/unenroll", json={"password": "no-es-esta"})
        assert r.status_code == 401
        assert r.json()["detail"] == "PASSWORD_INVALID"
        assert users_repo.get_user(uid)["status"] == users_repo.STATUS_ACTIVE


# --- 6. La consola del webmaster ----------------------------------------------


def test_la_consola_lista_las_cuentas_con_sus_pendientes_y_sus_avisos(
    monkeypatch, tmp_path
):
    """Los tres números que el lanzador pinta, y que no pueden contradecirse.

    `without_password` es la lista de tareas de la migración. V3.82 le cambia el
    **significado**: mientras no sea cero, esas cuentas no pueden entrar —son
    invitaciones pendientes—, pero ya no son un agujero (nadie entra nombrándose).
    `unverified_email` es la otra mitad del modo híbrido.
    """
    _setup(monkeypatch, tmp_path)
    users_repo.create_user("Heredada")  # sin credencial ni email (heredada pura)
    with TestClient(app) as client:
        _alta(client, "Marta", "marta@example.com")
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
    uid = users_repo.create_user("Heredada", email="heredada@example.com")["id"]
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
    # Y ya no entra con la credencial de verdad: la temporal obliga a cambiarla.
    with TestClient(app) as client:
        abierta = _abrir(client, "heredada@example.com", temporal)
        assert abierta.status_code == 200
        assert abierta.json()["must_change_password"] is True


def test_la_consola_verifica_el_email_a_mano(monkeypatch, tmp_path):
    """Modo híbrido sin SMTP: la firma la pone el webmaster, que tiene a la persona
    delante."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
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
        uid = _cuenta("Marta", "marta@example.com")
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


# --- 6. PII: el historial sobrevive a la purga, pero sin el correo -----------


def _notas(uid: str) -> list[str]:
    """Notas del historial leídas del SQLite, sin pasar por el borde HTTP.

    Es a propósito: la garantía de privacidad es sobre **la tabla**, no sobre lo
    que la API decida devolver.
    """
    con = sqlite3.connect(db.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT note FROM user_events WHERE subject_id = ? ORDER BY created_at, id",
            (uid,),
        ).fetchall()
        return [row["note"] for row in rows]
    finally:
        con.close()


def test_las_notas_del_historial_no_guardan_el_email(monkeypatch, tmp_path):
    """Alta, credenciales, edición y verificación anotan el **hecho**, no el correo.

    `user_events` sobrevive a la purga; si guardara el email, «borrar toda la
    evidencia de la cuenta» sería falso por la puerta de atrás.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta("Marta", "marta@example.com")
        assert "" in _notas(uid), "el alta no anota nada (mucho menos el correo)"

        asignada = client.post(
            f"/api/admin/users/{uid}/credentials",
            json={"email": "nueva@example.com"},
            headers=_ADMIN_HEADERS,
        )
        temporal = asignada.json()["temporary_password"]
        client.post(f"/api/admin/users/{uid}/verify-email", headers=_ADMIN_HEADERS)

        # Con la temporal puesta hay que cambiarla antes de tocar el email. La
        # credencial nueva apunta a `nueva@example.com`, así que es con ese correo
        # con el que se entra.
        _abrir(client, "nueva@example.com", temporal)
        client.put(
            "/api/session/password",
            json={"current_password": temporal, "new_password": _BUENA},
        )
        client.put(
            "/api/session/email",
            json={"email": "otra@example.com", "password": _BUENA},
        )

    notas = _notas(uid)
    assert "@" not in "\n".join(notas), f"hay un correo en el historial: {notas}"
    assert "credencial asignada · temporal" in notas
    assert "email verificado" in notas
    assert "email actualizado" in notas


def test_el_evento_de_purga_solo_se_escribe_si_la_purga_ocurrio(
    monkeypatch, tmp_path
):
    """La evidencia no puede afirmar una purga que no se hizo."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        malo = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Otra Persona"},
            headers=_ADMIN_HEADERS,
        )
        assert malo.status_code == 409
        assert users_repo.get_user(uid) is not None
        assert not any(
            e["action"] == users_repo.EVENT_PURGED for e in users_repo.list_events(uid)
        ), "se registró «datos purgados» sin haber purgado nada"

        bien = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Marta"},
            headers=_ADMIN_HEADERS,
        )
    assert bien.status_code == 200
    assert users_repo.get_user(uid) is None
    assert any(
        e["action"] == users_repo.EVENT_PURGED for e in users_repo.list_events(uid)
    ), "la purga que sí ocurrió dejó de registrarse"


def test_la_purga_redacta_los_correos_que_hubiera_en_el_historial(
    monkeypatch, tmp_path
):
    """Defensa en profundidad: una nota heredada con email no sobrevive al purge."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]
    users_repo.record_event(
        subject_id=uid,
        subject_name="Marta",
        action=users_repo.EVENT_CREATED,
        note="marta@example.com",  # como lo escribía V3.81.0
    )
    users_repo.set_unenrolled(uid, enrolled=False)
    with TestClient(app) as client:
        r = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Marta"},
            headers=_ADMIN_HEADERS,
        )
    assert r.status_code == 200
    notas = _notas(uid)
    assert "(email)" in notas, "el correo heredado no se redactó"
    assert "@" not in "\n".join(notas), f"sobrevive PII tras el purge: {notas}"


def test_la_migracion_de_arranque_redacta_correos_y_es_idempotente(
    monkeypatch, tmp_path
):
    """La limpieza de `init_db()` alcanza lo ya guardado y no reescribe de más."""
    _setup(monkeypatch, tmp_path)
    uid = users_repo.create_user("Marta")["id"]

    con = sqlite3.connect(db.DB_PATH)
    try:
        with con:
            con.execute(
                "INSERT INTO user_events "
                "(subject_id, subject_name, actor, action, note, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    uid,
                    "Marta",
                    "sistema",
                    users_repo.EVENT_CREATED,
                    "marta@example.com",
                    "2024-01-01T00:00:00+00:00",
                ),
            )
    finally:
        con.close()

    db.init_db()
    assert _notas(uid) == ["(email)"]

    # Segunda pasada: idempotente (no vuelve a tocar lo ya redactado).
    db.init_db()
    assert _notas(uid) == ["(email)"]
