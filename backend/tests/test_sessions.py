"""Sesiones firmadas: firma, caducidad, cookie y 401 (V3.75, Fase 2 del P0).

Lo que estos tests fijan no es «existe una cookie», sino que la identidad **no la
elige el cliente**: un token sin el secreto del equipo no vale, uno manipulado no
vale, y uno caducado no vale. El otro borde —que con una sesión de A no se lean ni
escriban datos de B— vive en `test_identity_source.py` y `test_users_self_only.py`.

V3.82: `POST /api/session` deja de aceptar `user_id` y pasa a exigir **email +
contraseña**. Los tests de la cookie y de la sesión usan ya esa puerta porque es
la única que existe; las cuentas se preparan por repositorio para no probar el
alta y la sesión a la vez.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import credentials, sessions

# Credencial del escenario. Cualquier valor sirve mientras cumpla la política: lo
# que importa es que el login la **demuestre**, no que sea difícil.
EMAIL = "ana@example.com"
PASSWORD = "caballo-bateria-grapa"


def _setup(
    monkeypatch,
    tmp_path,
    *,
    email: str = EMAIL,
    password: str | None = PASSWORD,
) -> str:
    """Crea «Ana» ya activada y devuelve su id.

    `password=None` deja la cuenta tal como la deja una invitación sin abrir: con
    email y sin credencial. Es el estado que V3.82 convierte en «no se entra».
    """
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("Ana", email=email)["id"]
    if password is not None:
        assert users_repo.set_password_hash(uid, credentials.hash_password(password))
    return uid


def _entrar(client, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/api/session", json={"email": email, "password": password})


def _cookie_header(response) -> str:
    return response.headers.get("set-cookie", "").lower()


def _firma_ajena(body: str) -> str:
    """Firma `body` con **otro** secreto: lo que tendría quien no tiene el fichero."""
    mac = hmac.new(b"secreto-de-otro-equipo", body.encode("ascii"), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).rstrip(b"=").decode("ascii")


# --- La firma ---------------------------------------------------------------


def test_el_token_sale_y_vuelve_con_el_mismo_perfil(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert sessions.verify(sessions.issue(uid)) == uid


def test_un_token_firmado_con_otro_secreto_no_vale(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    body, _, _ = sessions.issue(uid).partition(".")
    assert sessions.verify(f"{body}.{_firma_ajena(body)}") is None


def test_un_token_manipulado_no_vale(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    body, separator, signature = sessions.issue(uid).partition(".")
    # Cambiar el cuerpo (por ejemplo, el perfil) invalida la firma.
    assert sessions.verify(f"{body[:-2]}XY{separator}{signature}") is None
    # Y cambiar la firma, también.
    assert sessions.verify(f"{body}{separator}{signature[:-2]}XY") is None


@pytest.mark.parametrize("basura", ["", "sin-punto", "a.b.c", "....", "no-base64.="])
def test_lo_que_no_es_un_token_no_vale(monkeypatch, tmp_path, basura):
    _setup(monkeypatch, tmp_path)
    assert sessions.verify(basura) is None


def test_sin_token_tampoco_hay_perfil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert sessions.verify(None) is None


def test_un_token_caducado_no_vale(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    viejo = sessions.issue(
        uid, now=int(time.time()) - sessions.SESSION_TTL_SECONDS - 10
    )
    assert sessions.verify(viejo) is None


def test_un_token_del_futuro_lejano_no_vale(monkeypatch, tmp_path):
    """Un reloj movido hacia adelante no alarga la vida de una sesión."""
    uid = _setup(monkeypatch, tmp_path)
    futuro = sessions.issue(uid, now=int(time.time()) + 3600)
    assert sessions.verify(futuro) is None


def test_un_desajuste_pequeno_de_reloj_no_invalida(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert sessions.verify(sessions.issue(uid, now=int(time.time()) + 5)) == uid


# --- El secreto del equipo --------------------------------------------------


def test_el_secreto_se_crea_la_primera_vez_y_no_cambia(monkeypatch, tmp_path):
    ruta = tmp_path / "session.secret"
    monkeypatch.setattr(sessions, "secret_path", lambda: ruta)
    uid = _setup(monkeypatch, tmp_path)
    assert not ruta.exists()
    primero = sessions.issue(uid)
    assert ruta.exists()
    # Una segunda llamada **reutiliza** el secreto: si se regenerara, cada emisión
    # invalidaría las sesiones abiertas por la anterior.
    assert sessions.verify(primero) == uid


def test_un_secreto_vacio_se_regenera_en_vez_de_firmar_con_nada(monkeypatch, tmp_path):
    """El fallo grave sería *firmar con una clave vacía*: cualquiera forjaría.

    Solo puede venir de una escritura interrumpida, y como esa clave nunca llegó a
    firmar nada, regenerarla no invalida ninguna sesión real.
    """
    ruta = tmp_path / "session.secret"
    ruta.write_bytes(b"")
    monkeypatch.setattr(sessions, "secret_path", lambda: ruta)
    uid = _setup(monkeypatch, tmp_path)
    token = sessions.issue(uid)
    assert ruta.read_bytes(), "el secreto vacío tenía que regenerarse"
    assert sessions.verify(token) == uid


# --- La cookie --------------------------------------------------------------


def test_abrir_sesion_devuelve_el_perfil_y_una_cookie_httponly(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _entrar(client)
        assert r.status_code == 200
        assert r.json()["id"] == uid
        cookie = _cookie_header(r)
        assert f"{sessions.SESSION_COOKIE}=" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        assert "path=/" in cookie
        assert "max-age=" in cookie
        # En HTTP (modo desarrollo) no lleva `Secure`: el navegador la descartaría
        # y la sesión no se abriría nunca.
        assert "secure" not in cookie


def test_la_cookie_lleva_secure_cuando_la_peticion_va_por_https(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app, base_url="https://testserver") as client:
        r = _entrar(client)
        assert r.status_code == 200
        assert "secure" in _cookie_header(r)


def test_un_email_sin_cuenta_y_una_contrasena_mala_no_se_distinguen(
    monkeypatch, tmp_path
):
    """V3.82: el login no puede servir para averiguar qué correos tienen cuenta.

    Si «no existe ese email» y «esa contraseña no es» respondieran distinto, quien
    quisiera una lista de cuentas la tendría probando correos. Por eso comparten
    cuerpo: `401 INVALID_CREDENTIALS` para los dos.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        sin_cuenta = client.post(
            "/api/session",
            json={"email": "no-existe@example.com", "password": PASSWORD},
        )
        mala = client.post(
            "/api/session", json={"email": EMAIL, "password": "no-es-esta"}
        )

        assert sin_cuenta.status_code == 401
        assert mala.status_code == 401
        assert sin_cuenta.json() == mala.json()
        assert sin_cuenta.json()["detail"] == "INVALID_CREDENTIALS"


def test_una_cuenta_sin_contrasena_no_entra_y_dice_que_mire_su_correo(
    monkeypatch, tmp_path
):
    """El cierre **por construcción** del agujero de G0 (V3.82).

    Hasta V3.81 una cuenta con `password_hash == ''` entraba con solo nombrarse, y
    eso es exactamente lo que permitía entrar como J.A o Paz. Ahora esa misma
    cuenta responde `403 ACCOUNT_NOT_ACTIVATED`: no es una puerta abierta, es una
    invitación sin abrir.
    """
    _setup(monkeypatch, tmp_path, password=None)
    with TestClient(app) as client:
        r = client.post("/api/session", json={"email": EMAIL, "password": "lo-que-sea"})

        assert r.status_code == 403
        assert r.json()["detail"] == "ACCOUNT_NOT_ACTIVATED"
        assert sessions.SESSION_COOKIE not in _cookie_header(r)


def test_la_cuenta_de_la_sesion_declara_has_password_y_nunca_el_hash(
    monkeypatch, tmp_path
):
    """V3.81: la cuenta declara si tiene credencial; el hash no sale de aquí.

    Se comprueba en las dos caras del contrato —`POST /api/session` y
    `GET /api/session`— porque la lista de cuentas y la sesión son superficies
    distintas y ninguna de las dos debe filtrarlo.
    """
    _setup(monkeypatch, tmp_path)
    credentials.reset_state()

    with TestClient(app) as client:
        abierta = _entrar(client)
        assert abierta.status_code == 200
        assert abierta.json()["has_password"] is True
        assert "password_hash" not in abierta.text

        leida = client.get("/api/session")
        assert leida.json()["has_password"] is True
        assert "pbkdf2" not in leida.text


def test_sin_cookie_no_hay_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/session")
        assert r.status_code == 401
        assert r.json()["detail"] == "SESSION_REQUIRED"


def test_una_cookie_manipulada_no_abre_la_sesion(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.cookies.set(sessions.SESSION_COOKIE, f"{sessions.issue(uid)}x")
        assert client.get("/api/session").status_code == 401
        # Y no solo en el endpoint de sesión: cualquier endpoint con perfil.
        assert client.get("/api/settings").status_code == 401


def test_la_sesion_se_consulta_y_se_cierra(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert _entrar(client).status_code == 200
        assert client.get("/api/session").json()["id"] == uid
        assert client.delete("/api/session").status_code == 200
        # El borrado caduca la cookie y el jar del cliente lo respeta, igual que un
        # navegador: después ya no hay sesión.
        assert client.get("/api/session").status_code == 401


def test_una_sesion_valida_de_un_perfil_borrado_no_finge_perfil(monkeypatch, tmp_path):
    """Firma correcta pero el perfil ya no está: 404, no una sesión fantasma."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.cookies.set(sessions.SESSION_COOKIE, sessions.issue("perfil-borrado"))
        assert client.get("/api/session").status_code == 404


def test_cambiar_de_cuenta_reemplaza_la_cookie(monkeypatch, tmp_path):
    """Dos cuentas, dos sesiones: la última abierta manda (no se acumulan)."""
    ana = _setup(monkeypatch, tmp_path)
    beto = users_repo.create_user("Beto", email="beto@example.com")["id"]
    assert users_repo.set_password_hash(
        beto, credentials.hash_password(PASSWORD)
    ) is True
    with TestClient(app) as client:
        assert _entrar(client).status_code == 200
        primero = unquote(client.cookies.get(sessions.SESSION_COOKIE, ""))
        assert _entrar(client, "beto@example.com").status_code == 200
        segundo = unquote(client.cookies.get(sessions.SESSION_COOKIE, ""))
        assert primero != segundo
        assert client.get("/api/session").json()["id"] == beto
    # `ana` se lee solo para dejar claro que la primera sesión era suya; el
    # aserto que importa es que el token cambió de dueño.
    assert ana != beto
