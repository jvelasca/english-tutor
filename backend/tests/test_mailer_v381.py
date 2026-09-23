"""Correo saliente (V3.81): la mitad que no se puede probar mandando correo.

`services/mailer.py` promete dos cosas que se pueden falsificar sin salir a
Internet, y son las que se fijan aquí: **fail-closed** (sin SMTP configurado no se
abre ni una conexión, porque la app se anuncia offline) y **degradación honesta**
(un fallo de envío devuelve `False` y no tumba la acción que lo pedía).

Se fijan sustituyendo `smtplib` por un servidor de mentira que **apunta lo que le
hacen**: comprobar solo que `send()` devuelve `True` no probaría nada, porque el
defecto que importa no es devolver `True` sino *hacer* cosas indebidas —abrir un
socket sin configurar, autenticarse sin credencial o abortar por un STARTTLS que
el servidor no ofrece—.

Se añaden los dos endpoints de la consola de gestión (`GET /api/admin/smtp`,
`POST /api/admin/smtp/test`), y con ellos lo único que de verdad importa de la
pantalla del correo: que la **contraseña del SMTP no sale** en la respuesta —una
pantalla que enseña un secreto es una pantalla desde la que se copia—. El secreto
se aísla por ruta, como `conftest.py` hace con el de las sesiones, así que nada de
esto toca la red ni el `data/` real del proyecto.
"""
from __future__ import annotations

import smtplib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from services import mailer

_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}
_SECRETO = "contrasena-del-smtp"


class _ServidorFalso:
    """Servidor SMTP de mentira: apunta lo que le hacen y no abre nada."""

    def __init__(self, *, sin_starttls: bool = False, falla_envio: bool = False):
        self.llamadas: list[tuple] = []
        self._sin_starttls = sin_starttls
        self._falla_envio = falla_envio

    def __enter__(self):
        self.llamadas.append(("enter",))
        return self

    def __exit__(self, *args):
        self.llamadas.append(("exit",))
        return False

    def ehlo(self):
        self.llamadas.append(("ehlo",))

    def starttls(self, context=None):
        self.llamadas.append(("starttls",))
        if self._sin_starttls:
            raise smtplib.SMTPException("el servidor no ofrece STARTTLS")

    def login(self, user, password):
        self.llamadas.append(("login", user, password))

    def send_message(self, message):
        self.llamadas.append(("send", message))
        if self._falla_envio:
            raise OSError("se cayó a mitad del envío")

    @property
    def nombres(self) -> list[str]:
        return [llamada[0] for llamada in self.llamadas]

    @property
    def enviados(self) -> list:
        return [llamada[1] for llamada in self.llamadas if llamada[0] == "send"]


def _sin_smtp(monkeypatch) -> None:
    for var in (
        config.SMTP_HOST_ENV,
        config.SMTP_PORT_ENV,
        config.SMTP_USER_ENV,
        config.SMTP_FROM_ENV,
    ):
        monkeypatch.delenv(var, raising=False)


def _configurar(
    monkeypatch,
    *,
    host: str = "smtp.ejemplo.es",
    port: str = "587",
    user: str = "",
    remitente: str = "",
) -> None:
    monkeypatch.setenv(config.SMTP_HOST_ENV, host)
    monkeypatch.setenv(config.SMTP_PORT_ENV, port)
    if user:
        monkeypatch.setenv(config.SMTP_USER_ENV, user)
    if remitente:
        monkeypatch.setenv(config.SMTP_FROM_ENV, remitente)


def _instalar_servidor(monkeypatch, servidor: _ServidorFalso) -> list[tuple]:
    """Sustituye las dos clases de conexión y apunta **cuál** se usó."""
    construidos: list[tuple] = []

    def _fabrica(nombre: str):
        def _construir(*args, **kwargs):
            construidos.append((nombre, args, kwargs))
            return servidor

        return _construir

    monkeypatch.setattr(mailer.smtplib, "SMTP", _fabrica("SMTP"))
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", _fabrica("SMTP_SSL"))
    return construidos


def _prohibido_con_registro(usos: list):
    """Sonda que **apunta** el uso antes de fallar.

    Lanzar sin más no serviría: `mailer.send` atrapa cualquier excepción y
    devuelve `False`, así que una conexión indebida se confundiría con un fallo
    de red. Lo que hay que poder afirmar es que **no se llamó**.
    """

    def _prohibido(*args, **kwargs):
        usos.append(args)
        raise OSError("no se debía haber abierto ninguna conexión")

    return _prohibido


@pytest.fixture
def secreto(monkeypatch, tmp_path: Path) -> Path:
    """Ruta aislada de la contraseña del SMTP (nunca la del `data/` real)."""
    ruta = tmp_path / "mail.secret"
    monkeypatch.setattr(mailer, "secret_path", lambda: ruta)
    return ruta


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    monkeypatch.setenv(config.ADMIN_PIN_ENV, _ADMIN_PIN)


# --- Fail-closed --------------------------------------------------------------

def test_sin_smtp_no_se_abre_ninguna_conexion(monkeypatch, secreto):
    """La promesa del módulo: sin configurar no hay ni un intento de red.

    Una app que se anuncia offline no puede abrir un socket «por si acaso», y el
    defecto solo se ve sustituyendo `smtplib` por algo que **apunte** su uso: si
    lanzara sin registrar, `send` lo confundiría con un fallo de red.
    """
    _sin_smtp(monkeypatch)
    usos: list = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", _prohibido_con_registro(usos))
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", _prohibido_con_registro(usos))

    assert mailer.send(kind=mailer.KIND_TEST, to="yo@ejemplo.es") is False
    assert usos == [], "se abrió una conexión SMTP sin estar configurado"


def test_un_host_sin_remitente_tampoco_basta(monkeypatch, secreto):
    """`configured` exige host **y** remitente: un servidor al que no se le puede
    decir de parte de quién va el correo no es un servidor utilizable."""
    _sin_smtp(monkeypatch)
    monkeypatch.setenv(config.SMTP_HOST_ENV, "smtp.ejemplo.es")

    assert mailer.is_configured() is False


def test_sin_destinatario_no_se_envia_aunque_haya_smtp(monkeypatch, secreto):
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    servidor = _ServidorFalso()
    construidos = _instalar_servidor(monkeypatch, servidor)

    assert mailer.send(kind=mailer.KIND_TEST, to="") is False
    assert construidos == [], "no hacía falta ni conectar"


# --- Negociación y autenticación ---------------------------------------------

def test_587_negocia_starttls_y_no_se_autentica_sin_credencial(
    monkeypatch, secreto
):
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    servidor = _ServidorFalso()
    construidos = _instalar_servidor(monkeypatch, servidor)

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is True

    nombre, args, kwargs = construidos[0]
    assert nombre == "SMTP"
    assert args[:2] == ("smtp.ejemplo.es", 587)
    assert kwargs["timeout"] == mailer.SMTP_TIMEOUT_SECONDS
    assert "starttls" in servidor.nombres
    assert "login" not in servidor.nombres, "sin usuario no hay nada que autenticar"
    assert servidor.enviados[0]["To"] == "alumno@ejemplo.es"
    assert servidor.enviados[0]["From"] == "yo@ejemplo.es"


def test_465_usa_tls_implicito_y_no_niega_starttls(monkeypatch, secreto):
    """465 ya es TLS desde el primer byte: volver a negociarlo sería un error de
    protocolo, así que la elección de clase es la que se fija."""
    _configurar(monkeypatch, port="465", remitente="yo@ejemplo.es")
    servidor = _ServidorFalso()
    construidos = _instalar_servidor(monkeypatch, servidor)

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is True

    assert construidos[0][0] == "SMTP_SSL"
    assert "starttls" not in servidor.nombres


def test_un_servidor_sin_starttls_no_aborta_el_envio(monkeypatch, secreto):
    """Un reenvío local puede no ofrecer STARTTLS. Se continúa en claro a
    propósito: es una decisión de quien configura, no un fallo que inventar."""
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    servidor = _ServidorFalso(sin_starttls=True)
    _instalar_servidor(monkeypatch, servidor)

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is True
    assert len(servidor.enviados) == 1


def test_con_usuario_y_password_guardada_se_autentica_y_el_remitente_cae_al_usuario(
    monkeypatch, secreto
):
    secreto.write_text(_SECRETO, encoding="utf-8")
    _configurar(monkeypatch, user="bot@ejemplo.es")
    servidor = _ServidorFalso()
    _instalar_servidor(monkeypatch, servidor)

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is True

    assert ("login", "bot@ejemplo.es", _SECRETO) in servidor.llamadas
    assert servidor.enviados[0]["From"] == "bot@ejemplo.es", (
        "sin remitente declarado, el usuario es el remitente"
    )


def test_con_usuario_pero_sin_password_no_se_pierde_el_envio(monkeypatch, secreto):
    """Un servidor que no pide contraseña y sí declara usuario: no se llama a
    `login` con una cadena vacía, que sería un intento de autenticación fallido."""
    _configurar(monkeypatch, user="bot@ejemplo.es", remitente="yo@ejemplo.es")
    servidor = _ServidorFalso()
    _instalar_servidor(monkeypatch, servidor)

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is True
    assert "login" not in servidor.nombres


def test_un_fallo_de_envio_no_lanza_y_devuelve_false(monkeypatch, secreto):
    """El alta de una cuenta no puede caerse porque el correo falle: ese es el
    contrato que hace posible el modo híbrido."""
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    _instalar_servidor(monkeypatch, _ServidorFalso(falla_envio=True))

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is False


def test_un_servidor_que_no_responde_no_lanza(monkeypatch, secreto):
    _configurar(monkeypatch, remitente="yo@ejemplo.es")

    def _boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(mailer.smtplib, "SMTP", _boom)

    assert mailer.send(kind=mailer.KIND_TEST, to="alumno@ejemplo.es") is False


# --- El enlace de verificación ------------------------------------------------

def test_el_token_de_verificacion_viaja_en_el_fragmento_no_en_la_query():
    """El fragmento (`#`) no se manda al servidor: no queda en los logs ni en un
    `Referer`. El token de un solo uso no debe pasearse por ahí."""
    enlace = mailer.verification_link("https://equipo.local:8000/", "tok-123")

    assert enlace == "https://equipo.local:8000/#/cuenta/verificar?token=tok-123"


def test_el_correo_de_verificacion_lleva_el_enlace_y_avisa_de_la_caducidad(
    monkeypatch, secreto
):
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    servidor = _ServidorFalso()
    _instalar_servidor(monkeypatch, servidor)

    enlace = mailer.verification_link("https://equipo.local:8000", "tok-123")
    assert mailer.send(
        kind=mailer.KIND_VERIFICATION, to="alumno@ejemplo.es", link=enlace
    )

    cuerpo = servidor.enviados[0].get_content()
    assert enlace in cuerpo
    assert "una hora" in cuerpo, "el enlace caduca y el correo tiene que decirlo"


# --- Los dos endpoints de la consola -----------------------------------------

def test_los_endpoints_de_correo_exigen_pin(monkeypatch, tmp_path, secreto):
    """Fail-closed: sin PIN declarado la administración está cerrada, y eso
    incluye leer a qué servidor manda correo el producto."""
    _setup(monkeypatch, tmp_path)
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    monkeypatch.delenv(config.ADMIN_PIN_ENV, raising=False)

    with TestClient(app) as client:
        assert client.get("/api/admin/smtp").status_code == 401
        assert (
            client.post("/api/admin/smtp/test", json={"to": "a@ejemplo.es"}).status_code
            == 401
        )


def test_la_config_del_correo_no_ensena_la_contrasena(monkeypatch, tmp_path, secreto):
    """La consola necesita saber **si** hay contraseña, no cuál es."""
    _setup(monkeypatch, tmp_path)
    secreto.write_text(_SECRETO, encoding="utf-8")
    _configurar(
        monkeypatch,
        user="bot@ejemplo.es",
        remitente="yo@ejemplo.es",
    )

    with TestClient(app) as client:
        r = client.get("/api/admin/smtp", headers=_ADMIN_HEADERS)

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["host"] == "smtp.ejemplo.es"
    assert cuerpo["port"] == 587
    assert cuerpo["sender"] == "yo@ejemplo.es"
    assert cuerpo["configured"] is True
    assert cuerpo["has_password"] is True
    assert "password" not in cuerpo
    assert _SECRETO not in r.text, "el secreto se ha ido en la respuesta"


def test_sin_smtp_la_config_lo_dice_y_no_hay_password(monkeypatch, tmp_path, secreto):
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)

    with TestClient(app) as client:
        cuerpo = client.get("/api/admin/smtp", headers=_ADMIN_HEADERS).json()

    assert cuerpo["configured"] is False
    assert cuerpo["has_password"] is False


def test_la_prueba_de_envio_sin_smtp_explica_el_fallo_no_lanza(
    monkeypatch, tmp_path, secreto
):
    """«Probar envío» es la única forma de saber que el correo funciona: si no hay
    SMTP tiene que decirlo, no devolver un 500 que la consola no sepa leer."""
    _setup(monkeypatch, tmp_path)
    _sin_smtp(monkeypatch)

    with TestClient(app) as client:
        r = client.post(
            "/api/admin/smtp/test",
            json={"to": "yo@ejemplo.es"},
            headers=_ADMIN_HEADERS,
        )

    assert r.status_code == 200, r.text
    assert r.json()["sent"] is False
    assert r.json()["error"], "un fallo sin motivo no se puede contar al webmaster"


def test_la_prueba_de_envio_manda_el_correo_de_prueba(monkeypatch, tmp_path, secreto):
    _setup(monkeypatch, tmp_path)
    _configurar(monkeypatch, remitente="yo@ejemplo.es")
    servidor = _ServidorFalso()
    _instalar_servidor(monkeypatch, servidor)

    with TestClient(app) as client:
        r = client.post(
            "/api/admin/smtp/test",
            json={"to": "jefe@ejemplo.es"},
            headers=_ADMIN_HEADERS,
        )

    assert r.status_code == 200, r.text
    assert r.json()["sent"] is True
    assert r.json()["error"] == ""
    assert servidor.enviados[0]["To"] == "jefe@ejemplo.es"
