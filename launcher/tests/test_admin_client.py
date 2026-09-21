"""Tests del cliente de administración del launcher (V3.77).

Es el **único** sitio del launcher que escribe en el producto, así que lo que se
prueba aquí no es «devuelve algo» sino la forma exacta de lo que sale: el PIN en su
cabecera, el método y la ruta de cada acción, y que el `confirm_name` del purgado
viaje de verdad (es la confirmación de intención del borrado irreversible).

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


def test_la_lista_de_pendientes_pide_solo_las_pendientes(monkeypatch):
    rec = _install(monkeypatch, b'{"requests": [], "pending": 0}')

    result = admin.pending_requests("secreto-largo")

    assert result.ok
    assert result.data["pending"] == 0
    assert rec.request.method == "GET"
    assert rec.request.full_url.endswith("/api/admin/profile-requests?status=pending")
    assert rec.request.get_header("X-admin-pin") == "secreto-largo"


def test_la_lista_de_perfiles_incluye_los_desactivados(monkeypatch):
    """Un desactivado no está borrado: tiene que poder reactivarse."""
    rec = _install(monkeypatch, b'{"users": [], "pending": 0}')

    assert admin.list_profiles("secreto-largo").ok

    assert "include_disabled=true" in rec.request.full_url


def test_aprobar_manda_pin_de_perfil_y_nota(monkeypatch):
    rec = _install(monkeypatch, b'{"id": 7, "status": "approved"}')

    assert admin.approve_request("secreto-largo", 7, note="vale", profile_pin="1234").ok

    assert rec.request.method == "POST"
    assert rec.request.full_url.endswith("/api/admin/profile-requests/7/approve")
    assert rec.body == {"note": "vale", "pin": "1234"}


def test_rechazar_lleva_el_motivo(monkeypatch):
    rec = _install(monkeypatch, b'{"id": 7, "status": "rejected"}')

    assert admin.reject_request("secreto-largo", 7, note="nombre repetido").ok

    assert rec.body == {"note": "nombre repetido", "pin": ""}


def test_crear_perfil_no_inventa_pin_si_no_se_pide(monkeypatch):
    """Sin PIN el perfil entra sin credencial; eso lo decide el webmaster, no esto."""
    rec = _install(monkeypatch, b'{"id": "u1", "name": "Ana"}')

    assert admin.create_profile("secreto-largo", "Ana").ok

    assert rec.request.full_url.endswith("/api/admin/users")
    assert rec.body == {"name": "Ana", "pin": ""}


def test_desactivar_y_reactivar_usan_la_misma_ruta(monkeypatch):
    rec = _install(monkeypatch, b'{"id": "u1", "status": "disabled"}')

    admin.set_profile_status("secreto-largo", "u1", "disabled")
    assert rec.request.full_url.endswith("/api/admin/users/u1/status")
    assert rec.body == {"status": "disabled"}

    admin.set_profile_status("secreto-largo", "u1", "active")
    assert rec.body == {"status": "active"}


def test_purgar_manda_el_nombre_de_confirmacion_y_espera_mas(monkeypatch):
    """La copia de seguridad va antes del borrado: el único sitio que espera más."""
    rec = _install(monkeypatch, b'{"purged": true, "backup": "backup_1.zip"}')

    result = admin.purge_profile("secreto-largo", "u1", "Ana")

    assert result.ok
    assert rec.request.full_url.endswith("/api/admin/users/u1/purge")
    assert rec.body == {"confirm_name": "Ana"}
    assert rec.timeout > admin._TIMEOUT_SECONDS


def test_sin_pin_no_se_llama_al_servidor(monkeypatch):
    """Fail-closed también en el cliente: sin PIN no sale ninguna petición."""
    rec = _install(monkeypatch)

    result = admin.list_profiles("")

    assert result.ok is False
    assert result.status == 401
    assert rec.request is None, "se mandó una petición admin sin PIN declarado"


def test_los_errores_del_servidor_se_traducen_a_frases(monkeypatch):
    """La GUI tiene que poder decir «no se pudo» sin que se le caiga el hilo."""

    def http_error(code: int, payload: bytes = b""):
        def _raise(request, timeout=None, context=None):
            raise urllib.error.HTTPError(
                request.full_url, code, "error", {}, io.BytesIO(payload)
            )

        return _raise

    casos = {
        401: "PIN",
        403: "solo se ejerce desde este equipo",
        409: "ya estaba resuelta",
        422: "Datos no válidos",
    }
    for code, esperado in casos.items():
        monkeypatch.setattr("admin.urllib.request.urlopen", http_error(code))
        mensaje = admin.list_profiles("secreto-largo").message()
        assert esperado in mensaje, f"{code} no se tradujo: {mensaje!r}"

    monkeypatch.setattr(
        "admin.urllib.request.urlopen",
        http_error(409, json.dumps({"detail": "Perfil ya resuelto"}).encode()),
    )
    assert "Perfil ya resuelto" in admin.list_profiles("secreto-largo").message()


def test_un_servidor_que_no_responde_no_lanza(monkeypatch):
    """El launcher tiene que seguir vivo con el backend caído."""

    def boom(request, timeout=None, context=None):
        raise OSError("connection refused")

    monkeypatch.setattr("admin.urllib.request.urlopen", boom)

    result = admin.list_profiles("secreto-largo")

    assert result.ok is False
    assert "No se pudo hablar con el servidor" in result.message()
