"""El alta profesional de cuentas (V3.82), que es el contrato de esta release.

Este fichero fija el flujo **nuevo** completo —solicitud, autorización,
invitación, activación, entrada por email y recuperación— porque es donde vive la
diferencia entre «un nombre en una lista» y una cuenta de verdad. Lo que se prueba
aquí, y por qué importa cada pieza:

1. **La solicitud trae lo que hace falta para autorizar**: email y avatar. Sin
   correo no hay a quién invitar, y una solicitud que no lo trae obliga al
   webmaster a teclear datos que la persona ya escribió.
2. **Aprobar crea la cuenta y manda la invitación**, no una credencial inventada:
   ni el webmaster ni la base de datos ven nunca una contraseña provisional, y por
   eso no hay nada que interceptar.
3. **El agujero de G0 se cierra por construcción**: una cuenta que nace sin
   contraseña **no entra** (`403 ACCOUNT_NOT_ACTIVATED`). Hasta V3.81 entraba
   nombrando, y ese era el camino por el que cualquiera podía ser otro.
4. **Los tokens son de un solo uso y caducan** (invitación: 7 días; restablecimiento:
   1 hora). Un token que valiera dos veces, o para siempre, convertiría el correo en
   una llave permanente.
5. **«Olvidé mi contraseña» no es un oráculo**: la respuesta es idéntica exista o no
   la cuenta. Sin eso, el formulario sirve para cosechar qué correos tienen cuenta —
   que es PII que nadie debería poder preguntar sin sesión.
6. **Restablecer la contraseña tumba las sesiones abiertas**: si alguien cambia la
   contraseña porque sospecha que otro la tiene, el otro se queda fuera en el mismo
   acto, no cuando caduque su cookie.

El ciclo de vida de una cuenta ya existente (baja autoservicio, consola, purga)
tiene su contrato en `test_accounts_v381.py`; aquí se prueba **cómo se llega** a
tener una cuenta.
"""
from __future__ import annotations

import re
import smtplib
from contextlib import closing

from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from repositories import users as users_repo
from services import credentials, mailer, sessions

_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}
_BUENA = "caballo-bateria-grapa"
_OTRA = "ventana-lampara-vertedero"


# --- Escenario ---------------------------------------------------------------


def _setup(monkeypatch, tmp_path):
    """BD y secretos aislados: nada de esto toca el `data/` del proyecto."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    credentials.reset_state()
    monkeypatch.setenv(config.ADMIN_PIN_ENV, _ADMIN_PIN)
    monkeypatch.setattr(mailer, "secret_path", lambda: tmp_path / "mail.secret")
    return tmp_path


def _sin_smtp(monkeypatch) -> None:
    for var in (
        config.SMTP_HOST_ENV,
        config.SMTP_PORT_ENV,
        config.SMTP_USER_ENV,
        config.SMTP_FROM_ENV,
    ):
        monkeypatch.delenv(var, raising=False)


class _Servidor:
    """Servidor SMTP de mentira que **guarda los mensajes** que le entregan.

    Guarda el mensaje entero y no solo el hecho del envío porque el cuerpo es lo
    que se prueba: el enlace de la invitación viaja ahí, y sacar el token de él es
    lo que demuestra que el correo sirve para algo. Comprobar `send() is True` no
    probaría nada.
    """

    def __init__(self) -> None:
        self.mensajes: list = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        self.mensajes.append(message)

    @property
    def cuerpo(self) -> str:
        if not self.mensajes:
            raise AssertionError("no salió ningún correo")
        return str(self.mensajes[-1].get_content())


def _configurar_smtp(monkeypatch) -> tuple[_Servidor, list]:
    """Configura el correo y sustituye `smtplib` por el servidor de mentira."""
    monkeypatch.setenv(config.SMTP_HOST_ENV, "smtp.ejemplo.es")
    monkeypatch.setenv(config.SMTP_PORT_ENV, "587")
    monkeypatch.setenv(config.SMTP_FROM_ENV, "tutor@ejemplo.es")
    servidor = _Servidor()
    construidos: list = []

    def _fabrica(*args, **kwargs):
        construidos.append(args)
        return servidor

    monkeypatch.setattr(mailer.smtplib, "SMTP", _fabrica)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", _fabrica)
    return servidor, construidos


def _prohibido_con_registro(usos: list):
    """Sustituto de `smtplib` que **apunta** el uso antes de fallar.

    Lanzar sin registrar no serviría: `mailer.send` atrapa cualquier excepción y
    devuelve `False`, así que una conexión indebida se leería como un fallo de red.
    Lo que hay que poder afirmar es que **no se llamó**.
    """

    def _prohibido(*args, **kwargs):
        usos.append(args)
        raise OSError("no se debía haber abierto ninguna conexión")

    return _prohibido


def _token_del_enlace(cuerpo: str, ruta: str) -> str:
    """Saca el token del enlace de la app que va dentro del correo."""
    hallado = re.search(rf"{re.escape(ruta)}\?token=([A-Za-z0-9_\-]+)", cuerpo)
    assert hallado is not None, f"el correo no trae un enlace a {ruta}: {cuerpo!r}"
    return hallado.group(1)


def _solicitar(client, *, nombre: str, email: str, emoji: str = "🐢") -> dict:
    r = client.post(
        "/api/profile-requests",
        json={
            "display_name": nombre,
            "email": email,
            "avatar_color": "#123456",
            "avatar_emoji": emoji,
            "avatar_image": "",
            "note": "quiero practicar",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _aprobar(client, request_id: int) -> dict:
    r = client.post(
        f"/api/admin/profile-requests/{request_id}/approve",
        json={"note": ""},
        headers=_ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _abrir(client, email: str, password: str = _BUENA):
    return client.post("/api/session", json={"email": email, "password": password})


def _cuenta_en_marcha(name: str, email: str, password: str = _BUENA) -> str:
    """Una cuenta activa de verdad, para probar la recuperación desde ella.

    Se prepara por repositorio a propósito: el **alta** es el objeto de los tests
    de arriba, y llegar aquí por la API obligaría a arrastrar la invitación en
    cada test de contraseña olvidada, que es otra cosa.
    """
    uid = users_repo.create_user(name, email=email)["id"]
    assert users_repo.set_password_hash(uid, credentials.hash_password(password))
    assert users_repo.mark_activated(uid)
    return uid


# --- 1. La solicitud: lo que hace falta para autorizar -----------------------


def test_la_solicitud_guarda_el_email_normalizado_y_el_avatar(monkeypatch, tmp_path):
    """El email se guarda en minúsculas porque un correo no distingue caja.

    Sin normalizar, `Ana@Casa.es` y `ana@casa.es` serían dos solicitudes distintas
    y la unicidad del email —que es lo que sostiene la identidad— se caería.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        pedida = _solicitar(
            client, nombre="Ana", email="Ana@Casa.ES", emoji="🦉"
        )

    assert pedida["email"] == "ana@casa.es"
    assert pedida["avatar_emoji"] == "🦉"
    assert pedida["avatar_color"] == "#123456"
    assert pedida["status"] == "pending"
    assert pedida["display_name"] == "Ana"


def test_un_email_sin_forma_se_rechaza_antes_de_encolar(monkeypatch, tmp_path):
    """`422 EMAIL_FORMAT`, y no se crea fila: una cola con correos rotos es una
    cola que el webmaster tiene que limpiar a mano."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/profile-requests",
            json={"display_name": "Ana", "email": "ana-arroba-casa"},
        )

    assert r.status_code == 422
    assert r.json()["detail"] == "EMAIL_FORMAT"
    with closing(db._conn()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM profile_requests").fetchone()[0] == 0


def test_un_email_que_ya_tiene_cuenta_no_se_encola(monkeypatch, tmp_path):
    """`409 EMAIL_TAKEN`: el email es único, así que la invitación iría a la
    cuenta equivocada —a una que ya existe— y el que pide no tendría ninguna."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _cuenta_en_marcha("Paz", "paz@casa.es")
        r = client.post(
            "/api/profile-requests",
            json={"display_name": "Otra Paz", "email": "Paz@Casa.es"},
        )

    assert r.status_code == 409
    assert r.json()["detail"] == "EMAIL_TAKEN"


# --- 2. Aprobar: la cuenta nace y la invitación sale ------------------------


def test_aprobar_crea_la_cuenta_con_lo_que_se_pidio_y_sin_contrasena(
    monkeypatch, tmp_path
):
    """La cuenta nace **sin** contraseña: la elige la persona, no el webmaster.

    Que no tenga contraseña no es un descuido: es la diferencia entre una
    invitación pendiente y una credencial que alguien más eligió por ti.
    """
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])

    assert resuelta["user"] is not None
    assert resuelta["user"]["email"] == "ana@casa.es"
    assert resuelta["user"]["avatar_emoji"] == "🐢"
    assert resuelta["user"]["has_password"] is False
    assert resuelta["user"]["email_verified"] is False
    token_hash, sent_at = users_repo.get_activation(resuelta["user"]["id"]) or ("", "")
    assert token_hash, "aprobar tiene que emitir la invitación"
    assert sent_at, "y dejar constancia de cuándo se emitió"


def test_aprobar_manda_la_invitacion_con_el_enlace_de_la_app(monkeypatch, tmp_path):
    """El correo lleva el enlace **en el fragmento**, que no queda en los logs del
    servidor ni en un `Referer`: el token es de un solo uso y no debe pasearse."""
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])

    assert resuelta["email_sent"] is True
    assert "/#/cuenta/activar?token=" in resuelta["activation_link"]
    assert servidor.mensajes[-1]["To"] == "ana@casa.es"
    assert resuelta["activation_link"] in servidor.cuerpo, (
        "el enlace que se devuelve para entregar a mano es el mismo que se manda"
    )


def test_sin_smtp_la_invitacion_no_sale_pero_el_enlace_vuelve(
    monkeypatch, tmp_path
):
    """Modo híbrido, con la promesa de la app en pie: **sin SMTP no se abre ni una
    conexión**, y el webmaster recibe el enlace para entregarlo a mano.

    Que el enlace vuelva cuando el correo no ha salido no es un detalle: es la
    única forma de que una instalación sin correo tenga altas.
    """
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    usos: list = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", _prohibido_con_registro(usos))
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", _prohibido_con_registro(usos))

    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])

    assert usos == [], "se abrió una conexión SMTP sin estar configurado"
    assert resuelta["email_sent"] is False
    assert resuelta["activation_link"]


def test_aprobar_dos_veces_la_misma_solicitud_no_crea_dos_cuentas(
    monkeypatch, tmp_path
):
    """Una solicitud resuelta no se vuelve a resolver: si no, un doble clic del
    webmaster crearía una segunda cuenta con el mismo email (y el índice único
    lo rechazaría con un error que la consola no sabría contar)."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        _aprobar(client, pedida["id"])
        segunda = client.post(
            f"/api/admin/profile-requests/{pedida['id']}/approve",
            json={"note": ""},
            headers=_ADMIN_HEADERS,
        )

    assert segunda.status_code == 409


# --- 3. El agujero de G0, cerrado por construcción --------------------------


def test_una_cuenta_invitada_no_entra_hasta_que_activa(monkeypatch, tmp_path):
    """**Este es el candado de G0.**

    Hasta V3.81 una cuenta con `password_hash == ''` abría sesión: bastaba con
    nombrarla. Ahora responde `403 ACCOUNT_NOT_ACTIVATED`, así que el único camino
    a una sesión es una contraseña que eligió la persona. Si este test se cae, el
    agujero ha vuelto.
    """
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        _aprobar(client, pedida["id"])
        r = _abrir(client, "ana@casa.es", _BUENA)

    assert r.status_code == 403
    assert r.json()["detail"] == "ACCOUNT_NOT_ACTIVATED"


def test_un_email_sin_cuenta_y_una_contrasena_mala_son_indistinguibles(
    monkeypatch, tmp_path
):
    """Sin enumeración: la misma respuesta para «no existe» y «no es tu
    contraseña». Distinguirlas convertiría la entrada en un buscador de correos."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _cuenta_en_marcha("Ana", "ana@casa.es")
        sin_cuenta = _abrir(client, "nadie@casa.es")
        mala = _abrir(client, "ana@casa.es", "no-es-mi-contrasena")

    assert sin_cuenta.status_code == 401
    assert mala.status_code == 401
    assert sin_cuenta.json() == mala.json() == {"detail": "INVALID_CREDENTIALS"}


# --- 4. La activación: la persona elige su contraseña -----------------------


def test_un_token_de_activacion_inventado_no_cambia_nada(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        r = client.post(
            "/api/account/activate",
            json={"token": "tok-inventado-de-la-nada", "password": _BUENA},
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "ACTIVATION_TOKEN_INVALID"
    assert users_repo.get_user(resuelta["user"]["id"])["has_password"] is False


def test_una_contrasena_debil_no_consume_la_invitacion(monkeypatch, tmp_path):
    """El orden importa: se valida la contraseña **antes** de gastar el token, así
    que equivocarse al elegirla no obliga a pedir otra invitación."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        token = _token_del_enlace(resuelta["activation_link"], "/#/cuenta/activar")
        r = client.post(
            "/api/account/activate", json={"token": token, "password": "corta"}
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "PASSWORD_FORMAT"
    token_hash, _ = users_repo.get_activation(resuelta["user"]["id"]) or ("", "")
    assert token_hash, "el token sigue vivo: no se ha consumido"


def test_activar_fija_la_contrasena_verifica_el_email_y_deja_sesion(
    monkeypatch, tmp_path
):
    """Canjear el token prueba que el correo llegó, así que el email queda
    **verificado**: pedir además un segundo enlace sería pedir dos veces lo mismo.
    Y deja la sesión abierta, que es lo que evita teclear otra vez lo que se acaba
    de escribir."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        token = _token_del_enlace(resuelta["activation_link"], "/#/cuenta/activar")
        r = client.post(
            "/api/account/activate", json={"token": token, "password": _BUENA}
        )
        en_sesion = client.get("/api/session")

    assert r.status_code == 200, r.text
    assert r.json()["email_verified"] is True
    assert r.json()["has_password"] is True
    assert users_repo.get_activation(resuelta["user"]["id"]) == ("", "")
    assert en_sesion.status_code == 200
    assert en_sesion.json()["email"] == "ana@casa.es"


def test_el_token_de_activacion_es_de_un_solo_uso(monkeypatch, tmp_path):
    """Si valiera dos veces, quien leyera el correo podría volver a poner la
    contraseña cuando quisiera — y ya no haría falta ni adivinarla."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        token = _token_del_enlace(resuelta["activation_link"], "/#/cuenta/activar")
        primero = client.post(
            "/api/account/activate", json={"token": token, "password": _BUENA}
        )
        segundo = client.post(
            "/api/account/activate", json={"token": token, "password": _OTRA}
        )

    assert primero.status_code == 200
    assert segundo.status_code == 400
    assert segundo.json()["detail"] == "ACTIVATION_TOKEN_INVALID"


def test_una_invitacion_caducada_no_sirve(monkeypatch, tmp_path):
    """Siete días es la vida de una invitación: un enlace olvidado en una bandeja
    no puede seguir siendo una llave dentro de un año. Se reemite, que para eso
    está «Reenviar invitación»."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        token = _token_del_enlace(resuelta["activation_link"], "/#/cuenta/activar")
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "UPDATE users SET activation_sent_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00+00:00", resuelta["user"]["id"]),
            )
        r = client.post(
            "/api/account/activate", json={"token": token, "password": _BUENA}
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "ACTIVATION_TOKEN_EXPIRED"


def test_reenviar_la_invitacion_invalida_la_anterior(monkeypatch, tmp_path):
    """Reemitir no es «mandar otro correo con el mismo enlace»: emite un token
    **nuevo** y el viejo deja de valer, porque si no habría dos llaves para la
    misma cuenta y nadie sabría cuántas quedan vivas."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        viejo = _token_del_enlace(resuelta["activation_link"], "/#/cuenta/activar")
        reenvio = client.post(
            f"/api/admin/users/{resuelta['user']['id']}/resend-activation",
            headers=_ADMIN_HEADERS,
        )
        nuevo = _token_del_enlace(
            reenvio.json()["activation_link"], "/#/cuenta/activar"
        )
        con_el_viejo = client.post(
            "/api/account/activate", json={"token": viejo, "password": _BUENA}
        )
        con_el_nuevo = client.post(
            "/api/account/activate", json={"token": nuevo, "password": _BUENA}
        )

    assert reenvio.status_code == 200, reenvio.text
    assert nuevo != viejo
    assert con_el_viejo.status_code == 400
    assert con_el_nuevo.status_code == 200


def test_no_se_puede_invitar_a_quien_no_tiene_email(monkeypatch, tmp_path):
    """`409`: sin correo no hay a quién invitar, y decirlo es mejor que emitir un
    token que nadie va a recibir."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Heredada", "")
        r = client.post(
            f"/api/admin/users/{uid}/resend-activation", headers=_ADMIN_HEADERS
        )

    assert r.status_code == 409


def test_la_cuenta_activada_entra_con_su_email_y_su_contrasena(
    monkeypatch, tmp_path
):
    """El final del camino: con la contraseña elegida, se entra por email. Y el
    email no distingue mayúsculas, que es como lo escribe la gente."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])
        token = _token_del_enlace(resuelta["activation_link"], "/#/cuenta/activar")
        client.post("/api/account/activate", json={"token": token, "password": _BUENA})
        client.cookies.clear()
        r = _abrir(client, "Ana@Casa.es", _BUENA)

    assert r.status_code == 200
    assert r.json()["name"] == "Ana"


# --- 5. La recuperación: olvidar la contraseña sin llamar al webmaster ------


def test_olvidar_la_contrasena_responde_lo_mismo_siempre(monkeypatch, tmp_path):
    """La respuesta idéntica es la función, no una casualidad: si dijera «ese
    correo no está registrado», el formulario sería un oráculo para averiguar
    quién tiene cuenta."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    with TestClient(app) as client:
        _cuenta_en_marcha("Ana", "ana@casa.es")
        con_cuenta = client.post(
            "/api/account/forgot-password", json={"email": "ana@casa.es"}
        )
        sin_cuenta = client.post(
            "/api/account/forgot-password", json={"email": "nadie@casa.es"}
        )
        sin_forma = client.post(
            "/api/account/forgot-password", json={"email": "x"}
        )

    assert con_cuenta.status_code == 200
    assert sin_cuenta.status_code == 200
    assert con_cuenta.json() == sin_cuenta.json() == {"sent": True}
    # Un email que no puede serlo se rechaza **antes** de mirar nada: eso no
    # revela nada de nadie, y evita gastar cupo y correo en basura.
    assert sin_forma.status_code == 422


def test_olvidar_la_contrasena_manda_el_enlace_de_restablecimiento(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        r = client.post(
            "/api/account/forgot-password", json={"email": "ana@casa.es"}
        )

    assert r.status_code == 200
    assert servidor.mensajes[-1]["To"] == "ana@casa.es"
    assert "/#/cuenta/restablecer?token=" in servidor.cuerpo
    token_hash, sent_at = users_repo.get_password_reset(uid) or ("", "")
    assert token_hash and sent_at


def test_sin_smtp_el_restablecimiento_emite_el_token_sin_abrir_conexion(
    monkeypatch, tmp_path
):
    """El token se emite aunque no haya correo (el webmaster puede entregar el
    enlace), pero no se abre ninguna conexión. Es la misma promesa que la
    invitación, y tiene que valer igual."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)
    usos: list = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", _prohibido_con_registro(usos))
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", _prohibido_con_registro(usos))
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        r = client.post(
            "/api/account/forgot-password", json={"email": "ana@casa.es"}
        )

    assert r.status_code == 200
    assert usos == [], "se abrió una conexión SMTP sin estar configurado"
    token_hash, _ = users_repo.get_password_reset(uid) or ("", "")
    assert token_hash, "el token queda emitido para entregarlo a mano"


def test_una_cuenta_dada_de_baja_no_recibe_restablecimiento(monkeypatch, tmp_path):
    """A una cuenta retirada no se le manda correo: reactivarla es una decisión
    del webmaster, no algo que se consigue pidiéndolo desde fuera."""
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        Users = users_repo
        assert Users.set_unenrolled(uid, enrolled=False) is not None
        r = client.post(
            "/api/account/forgot-password", json={"email": "ana@casa.es"}
        )

    assert r.status_code == 200
    assert servidor.mensajes == [], "no se manda correo a una cuenta fuera de servicio"


def test_restablecer_cambia_la_contrasena_y_tumba_la_sesion_abierta(
    monkeypatch, tmp_path
):
    """La mitad del valor de la función: si alguien restablece porque sospecha que
    otro tiene su contraseña, el otro se queda fuera **en el mismo acto**, no
    cuando caduque su cookie."""
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        _cuenta_en_marcha("Ana", "ana@casa.es")
        assert _abrir(client, "ana@casa.es").status_code == 200
        cookie_vieja = client.cookies.get(sessions.SESSION_COOKIE)
        assert cookie_vieja
        client.post("/api/account/forgot-password", json={"email": "ana@casa.es"})
        token = _token_del_enlace(servidor.cuerpo, "/#/cuenta/restablecer")
        r = client.post(
            "/api/account/reset-password", json={"token": token, "password": _OTRA}
        )
        # Se vuelve a poner la cookie que era válida hace un momento.
        client.cookies.set(sessions.SESSION_COOKIE, cookie_vieja)
        la_vieja = client.get("/api/session")
        client.cookies.clear()
        con_la_nueva = _abrir(client, "ana@casa.es", _OTRA)

    assert r.status_code == 200, r.text
    assert la_vieja.status_code == 401
    assert la_vieja.json()["detail"] == "SESSION_STALE"
    assert con_la_nueva.status_code == 200


def test_el_token_de_restablecimiento_es_de_un_solo_uso(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        _cuenta_en_marcha("Ana", "ana@casa.es")
        client.post("/api/account/forgot-password", json={"email": "ana@casa.es"})
        token = _token_del_enlace(servidor.cuerpo, "/#/cuenta/restablecer")
        primero = client.post(
            "/api/account/reset-password", json={"token": token, "password": _OTRA}
        )
        segundo = client.post(
            "/api/account/reset-password", json={"token": token, "password": _BUENA}
        )

    assert primero.status_code == 200
    assert segundo.status_code == 400
    assert segundo.json()["detail"] == "RESET_TOKEN_INVALID"


def test_un_token_de_restablecimiento_caducado_no_sirve(monkeypatch, tmp_path):
    """Una hora: el enlace viaja por correo, y un correo viejo no puede ser una
    llave que siga funcionando la semana siguiente."""
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        client.post("/api/account/forgot-password", json={"email": "ana@casa.es"})
        token = _token_del_enlace(servidor.cuerpo, "/#/cuenta/restablecer")
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "UPDATE users SET password_reset_sent_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00+00:00", uid),
            )
        r = client.post(
            "/api/account/reset-password", json={"token": token, "password": _OTRA}
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "RESET_TOKEN_EXPIRED"


def test_restablecer_una_contrasena_debil_no_gasta_el_token(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    servidor, _ = _configurar_smtp(monkeypatch)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        client.post("/api/account/forgot-password", json={"email": "ana@casa.es"})
        token = _token_del_enlace(servidor.cuerpo, "/#/cuenta/restablecer")
        r = client.post(
            "/api/account/reset-password", json={"token": token, "password": "corta"}
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "PASSWORD_FORMAT"
    token_hash, _ = users_repo.get_password_reset(uid) or ("", "")
    assert token_hash, "el token sigue vivo"


# --- 6. La superficie pública, sin sorpresas ---------------------------------


def test_la_entrada_ya_no_admite_un_user_id(monkeypatch, tmp_path):
    """Nombrar una cuenta dejó de ser una forma de entrar (V3.82). El cuerpo solo
    entiende email y contraseña, así que el campo sobra y la petición se rechaza."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        r = client.post("/api/session", json={"user_id": uid})

    assert r.status_code == 422


def test_no_se_puede_invitar_sin_el_candado_de_administracion(monkeypatch, tmp_path):
    """Reemitir una invitación es una acción del webmaster, no del alumno."""
    _setup(monkeypatch, tmp_path)
    monkeypatch.delenv(config.ADMIN_PIN_ENV, raising=False)
    with TestClient(app) as client:
        uid = _cuenta_en_marcha("Ana", "ana@casa.es")
        r = client.post(f"/api/admin/users/{uid}/resend-activation")

    assert r.status_code == 401


def test_sin_smtp_la_falta_de_correo_se_ve_en_el_error_no_en_una_excepcion(
    monkeypatch, tmp_path
):
    """`smtplib` roto no puede tumbar una aprobación: el correo es un aviso, y la
    cuenta tiene que nacer igual (si no, el alta dependería del proveedor)."""
    _setup(monkeypatch, tmp_path)
    _configurar_smtp(monkeypatch)

    def _boom(*args, **kwargs):
        raise smtplib.SMTPException("el servidor no está")

    monkeypatch.setattr(mailer.smtplib, "SMTP", _boom)
    with TestClient(app) as client:
        pedida = _solicitar(client, nombre="Ana", email="ana@casa.es")
        resuelta = _aprobar(client, pedida["id"])

    assert resuelta["email_sent"] is False
    assert resuelta["activation_link"]
    assert users_repo.get_user(resuelta["user"]["id"]) is not None
