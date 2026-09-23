"""Tests del cliente de administración del launcher (V3.77, ampliado en V3.81).

Es el **único** sitio del launcher que escribe en el producto, así que lo que se
prueba aquí no es «devuelve algo» sino la forma exacta de lo que sale: el PIN en su
cabecera, el método y la ruta de cada acción, y que lo que no puede viajar en vano
viaje de verdad —el `confirm_name` del borrado irreversible, el `reason` de una baja
forzada y el `to` de un correo de prueba—.

V3.81 cambia dos cosas de forma y las dos se fijan aquí. **(1) El alta ya no decide
la credencial:** `create_user` manda `name`, `email` y `password` como tres campos
independientes, y una contraseña vacía significa «genérala tú» —el alta y la
credencial son dos decisiones, y `set_credentials` es la segunda—. **(2) Aprobar o
rechazar una solicitud ya no lleva PIN de perfil:** el PIN desapareció del producto,
así que el cuerpo de esas dos llamadas solo lleva la nota, y aprobar un alta crea la
cuenta **sin** credencial a propósito.

Nada de esto toca un servidor: `urlopen` se sustituye y se inspecciona la petición.
"""
from __future__ import annotations

import io
import json
import urllib.error

import admin


class _FakeResp:
    def __init__(self, payload: bytes = b"{}", code: int = 200):
        self._payload = payload
        self.status = code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _n=None):
        return self._payload


class _Recorder:
    """Captura la última petición para poder afirmar sobre ella."""

    def __init__(self, response: bytes = b"{}", code: int = 200):
        self.request = None
        self.timeout = None
        self._response = response
        self._code = code

    def __call__(self, request, timeout=None, context=None):
        self.request = request
        self.timeout = timeout
        return _FakeResp(self._response, self._code)

    @property
    def body(self) -> dict:
        return json.loads(self.request.data.decode("utf-8"))


def _install(monkeypatch, response=b"{}", code=200) -> _Recorder:
    recorder = _Recorder(response, code)
    monkeypatch.setattr("admin.urllib.request.urlopen", recorder)
    return recorder


def _http_error(code: int, payload: bytes = b""):
    """Sustituto de `urlopen` que responde con un error HTTP concreto."""

    def _raise(request, timeout=None, context=None):
        raise urllib.error.HTTPError(
            request.full_url, code, "error", {}, io.BytesIO(payload)
        )

    return _raise


# --- Cola de solicitudes ------------------------------------------------------

def test_la_lista_de_pendientes_pide_solo_las_pendientes(monkeypatch):
    rec = _install(monkeypatch, b'{"requests": [], "pending": 0}')

    result = admin.pending_requests("secreto-largo")

    assert result.ok
    assert result.data["pending"] == 0
    assert rec.request.method == "GET"
    assert rec.request.full_url.endswith("/api/admin/profile-requests?status=pending")
    assert rec.request.get_header("X-admin-pin") == "secreto-largo"


def test_la_lista_de_cuentas_incluye_las_desactivadas(monkeypatch):
    """Una desactivada no está borrada: tiene que poder reactivarse."""
    rec = _install(monkeypatch, b'{"users": [], "pending": 0}')

    assert admin.list_users("secreto-largo").ok

    assert "include_disabled=true" in rec.request.full_url


def test_aprobar_ya_no_manda_pin_de_perfil(monkeypatch):
    """V3.81: aprobar un alta crea la cuenta **sin** credencial, y eso es decisión
    aparte (`set_credentials`). Mandar un `pin` aquí sería resucitar el concepto."""
    rec = _install(monkeypatch, b'{"id": 7, "status": "approved"}')

    assert admin.approve_request("secreto-largo", 7, note="vale").ok

    assert rec.request.method == "POST"
    assert rec.request.full_url.endswith("/api/admin/profile-requests/7/approve")
    assert rec.body == {"note": "vale"}


def test_rechazar_lleva_el_motivo_y_nada_mas(monkeypatch):
    rec = _install(monkeypatch, b'{"id": 7, "status": "rejected"}')

    assert admin.reject_request("secreto-largo", 7, note="nombre repetido").ok

    assert rec.body == {"note": "nombre repetido"}


# --- Cuentas ------------------------------------------------------------------

def test_crear_cuenta_sin_password_pide_que_la_genere_el_servidor(monkeypatch):
    """Contraseña vacía = «genérala tú»: el webmaster no inventa la definitiva."""
    rec = _install(monkeypatch, b'{"id": "u1", "name": "Ana"}')

    assert admin.create_user("secreto-largo", "Ana").ok

    assert rec.request.method == "POST"
    assert rec.request.full_url.endswith("/api/admin/users")
    assert rec.body == {"name": "Ana", "email": "", "password": ""}


def test_crear_cuenta_con_credencial_manda_los_tres_campos(monkeypatch):
    rec = _install(monkeypatch, b'{"id": "u1", "name": "Ana"}')

    assert admin.create_user(
        "secreto-largo", "Ana", email="a@b.c", password="lisa-y-corta-8"
    ).ok

    assert rec.body == {
        "name": "Ana",
        "email": "a@b.c",
        "password": "lisa-y-corta-8",
    }


def test_desactivar_y_reactivar_usan_la_misma_ruta(monkeypatch):
    rec = _install(monkeypatch, b'{"id": "u1", "status": "disabled"}')

    admin.set_user_status("secreto-largo", "u1", "disabled")
    assert rec.request.full_url.endswith("/api/admin/users/u1/status")
    assert rec.body == {"status": "disabled"}

    admin.set_user_status("secreto-largo", "u1", "active")
    assert rec.body == {"status": "active"}


def test_las_credenciales_son_la_recuperacion_de_password(monkeypatch):
    """Asignar credencial es también el restablecimiento: mismo camino, sin ramas."""
    rec = _install(monkeypatch, b'{"id": "u1"}')

    assert admin.set_credentials("secreto-largo", "u1", email="a@b.c").ok

    assert rec.request.method == "POST"
    assert rec.request.full_url.endswith("/api/admin/users/u1/credentials")
    assert rec.body == {"email": "a@b.c", "password": ""}


def test_editar_manda_solo_los_campos_presentes(monkeypatch):
    """Un campo ausente **no se toca**: mandar `None` sería un intento de vaciarlo."""
    rec = _install(monkeypatch, b'{"id": "u1"}')

    assert admin.edit_user("secreto-largo", "u1", name="Ana", email=None).ok

    assert rec.request.method == "PATCH"
    assert rec.request.full_url.endswith("/api/admin/users/u1")
    assert rec.body == {"name": "Ana"}


def test_verificar_email_no_manda_cuerpo(monkeypatch):
    """Sellar el email es un POST sin datos: el token no lo elige el webmaster."""
    rec = _install(monkeypatch)

    assert admin.verify_email("secreto-largo", "u1").ok

    assert rec.request.method == "POST"
    assert rec.request.full_url.endswith("/api/admin/users/u1/verify-email")
    assert rec.request.data is None


def test_forzar_la_baja_exige_y_manda_el_motivo(monkeypatch):
    """Una baja forzada sin motivo es un botón; con motivo, una decisión."""
    rec = _install(monkeypatch, b'{"id": "u1", "status": "unenrolled"}')

    assert admin.force_unenroll("secreto-largo", "u1", "suplantación").ok

    assert rec.request.full_url.endswith("/api/admin/users/u1/unenroll")
    assert rec.body == {"reason": "suplantación"}


def test_el_historial_sobrevive_a_la_purga(monkeypatch):
    """Cuando ya no queda fila en `users`, es el único sitio que responde."""
    rec = _install(monkeypatch, b'{"events": []}')

    assert admin.user_history("secreto-largo", "u1").ok

    assert rec.request.method == "GET"
    assert rec.request.full_url.endswith("/api/admin/users/u1/events")


def test_purgar_manda_el_nombre_de_confirmacion_y_espera_mas(monkeypatch):
    """La copia de seguridad va antes del borrado: es el único que espera más."""
    rec = _install(monkeypatch, b'{"purged": true, "backup": "backup_1.zip"}')

    result = admin.purge_user("secreto-largo", "u1", "Ana")

    assert result.ok
    assert rec.request.full_url.endswith("/api/admin/users/u1/purge")
    assert rec.body == {"confirm_name": "Ana"}
    assert rec.timeout > admin._TIMEOUT_SECONDS


# --- Correo saliente ----------------------------------------------------------

def test_la_config_del_correo_viene_del_backend_en_marcha(monkeypatch):
    """El backend resuelve el SMTP de su entorno, no del JSON del launcher: su
    respuesta es la que dice si el servidor **en marcha** ve el correo."""
    rec = _install(monkeypatch, b'{"configured": true, "has_password": true}')

    result = admin.smtp_config("secreto-largo")

    assert result.ok
    assert result.data["has_password"] is True
    assert rec.request.method == "GET"
    assert rec.request.full_url.endswith("/api/admin/smtp")


def test_el_correo_de_prueba_espera_mas_que_una_consulta(monkeypatch):
    rec = _install(monkeypatch, b'{"sent": true}')

    assert admin.test_smtp("secreto-largo", "yo@ejemplo.es").ok

    assert rec.request.full_url.endswith("/api/admin/smtp/test")
    assert rec.body == {"to": "yo@ejemplo.es"}
    assert rec.timeout > admin._TIMEOUT_SECONDS


# --- Fail-closed y traducción de errores --------------------------------------

def test_sin_pin_no_se_llama_al_servidor(monkeypatch):
    """Fail-closed también en el cliente: sin PIN no sale ninguna petición."""
    rec = _install(monkeypatch)

    result = admin.list_users("")

    assert result.ok is False
    assert result.status == 401
    assert rec.request is None, "se mandó una petición admin sin PIN declarado"


def test_los_errores_del_servidor_se_traducen_a_frases(monkeypatch):
    """La GUI tiene que poder decir «no se pudo» sin que se le caiga el hilo."""
    casos = {
        401: "PIN",
        403: "solo se ejerce desde este equipo",
        404: "ya no existe",
        409: "conflicto",
        422: "Datos no válidos",
    }
    for code, esperado in casos.items():
        monkeypatch.setattr("admin.urllib.request.urlopen", _http_error(code))
        mensaje = admin.list_users("secreto-largo").message()
        assert esperado in mensaje, f"{code} no se tradujo: {mensaje!r}"

    monkeypatch.setattr(
        "admin.urllib.request.urlopen",
        _http_error(409, json.dumps({"detail": "Solicitud ya resuelta"}).encode()),
    )
    assert "Solicitud ya resuelta" in admin.list_users("secreto-largo").message()


def test_los_codigos_conocidos_se_explican_en_espanol(monkeypatch):
    """Un `detail` en crudo («EMAIL_TAKEN») no es una frase para el webmaster."""
    payload = json.dumps({"detail": "EMAIL_TAKEN"}).encode()
    monkeypatch.setattr("admin.urllib.request.urlopen", _http_error(409, payload))

    mensaje = admin.create_user("secreto-largo", "Ana").message()

    assert "EMAIL_TAKEN" not in mensaje
    assert "ya está en uso" in mensaje


def test_un_servidor_que_no_responde_no_lanza(monkeypatch):
    """El launcher tiene que seguir vivo con el backend caído."""

    def boom(request, timeout=None, context=None):
        raise OSError("connection refused")

    monkeypatch.setattr("admin.urllib.request.urlopen", boom)

    result = admin.list_users("secreto-largo")

    assert result.ok is False
    assert "No se pudo hablar con el servidor" in result.message()
