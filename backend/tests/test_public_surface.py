"""La superficie **sin sesión** está declarada, no olvidada (VG-N6, V3.75).

La auditoría de V3.73 (`docs/audit/VERIFICACION-SEGURIDAD-V373.md`, VG-N6) señaló
tres endpoints que respondían sin credencial ninguna —`/api/system/status`,
`/api/network` y `/api/models`— y dejó la decisión abierta: **declararlos
aceptados de forma explícita o restringirlos**. Esto es la mitad «declararlos»,
con la parte que suele faltar: un candado que lo comprueba.

**Qué fija este archivo.** La lista de rutas que deben seguir respondiendo sin
sesión (romperlas en silencio rompe el arranque del producto: el launcher y la
puerta de perfil las usan antes de que exista ningún perfil) y la lista de las que
**no** pueden responder sin sesión. Si alguien abre una de las segundas o cierra
una de las primeras por descuido, el test lo dice con el nombre de la ruta.

**Por qué se aceptan (y no se restringen).** El producto es **local** y su entrada
pide **email + contraseña** (V3.82; hasta V3.81 era un selector con avatar). En ese
marco, lo que estas rutas exponen es **reconocimiento barato** —modelos instalados,
IP/hostname de LAN, trabajos de generación en curso y rechazos por rate limit— que
**no** permite leer ni escribir los datos de ninguna cuenta: para eso están los
endpoints de datos, que desde V3.75 exigen sesión firmada. V3.82 retira el
último resto del modelo «selector»: `GET /api/users` deja de enumerar cuentas sin
sesión, así que **ni los nombres** se regalan. Y la frontera que decide quién
alcanza la API no es esta lista, es la **red** (loopback por defecto, LAN opt-in).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo

# Rutas que **deben** responder sin sesión y qué se espera de cada una.
# (Se declara el método y el código esperado para que el test no se conforme con
# «no es 401»: `/api/health/ready` responde 503 legítimamente cuando falta una
# dependencia, y una ruta que solo admite POST daría 405 a un GET.)
SIN_SESION: dict[tuple[str, str], tuple[int, ...]] = {
    ("GET", "/api"): (200,),
    ("GET", "/api/health"): (200,),
    ("GET", "/api/health/live"): (200,),
    ("GET", "/api/health/ready"): (200, 503),
    ("GET", "/api/health/dependencies"): (200,),
    # El formulario de solicitud se manda **sin** sesión: quien pide una cuenta
    # todavía no tiene ninguna. No crea nada (ver más abajo), así que lo peor que
    # deja es una fila pendiente que el webmaster puede rechazar.
    ("POST", "/api/profile-requests"): (201, 409, 422, 429),
    # El selector de Ajustes → IA y la tarjeta de conexión se pintan antes de
    # cualquier elección de perfil.
    ("GET", "/api/models"): (200, 502),  # 502 = Ollama no responde (no es 401)
    ("GET", "/api/network"): (200,),
    # El estado operativo que el launcher muestra («trabajando»).
    ("GET", "/api/system/status"): (200,),
}

# Rutas de datos: sin sesión firmada, **401 `SESSION_REQUIRED`** y nada más.
CON_SESION: dict[str, tuple[int, ...]] = {
    # V3.82: la lista de cuentas deja de ser pública. Era el último resto del
    # modelo «selector»: la puerta pintaba los nombres antes de que existiera
    # sesión. Con el login por email nadie necesita enumerar quién existe.
    "/api/users": (401,),
    "/api/settings": (401,),
    "/api/profile": (401,),
    "/api/progress": (401,),
    "/api/conversations": (401,),
    "/api/vocabulary": (401,),
    "/api/grammar/errors": (401,),
    "/api/academy/levels": (401,),
    "/api/listening/stats": (401,),
}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("Ana")["id"]


def test_la_superficie_sin_sesion_responde_sin_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        raros: list[str] = []
        for (metodo, ruta), esperados in SIN_SESION.items():
            r = client.request(metodo, ruta, json={} if metodo == "POST" else None)
            if r.status_code not in esperados:
                raros.append(
                    f"{metodo} {ruta} → {r.status_code} (esperaba {esperados})"
                )
        assert raros == [], (
            "rutas declaradas sin sesión que dejaron de responder: "
            f"{raros}. Si el cambio es intencionado, mueve la ruta de lista y "
            "actualiza docs/ARQUITECTURA.md (sección de superficie sin sesión)."
        )


@pytest.mark.identidad_cruda
def test_la_superficie_con_sesion_no_responde_sin_sesion(monkeypatch, tmp_path):
    """El otro lado del candado: sin sesión, los datos del alumno no salen.

    Va marcado `identidad_cruda` a propósito: aquí el `?user_id=` **debe** viajar
    sin traducirse, porque lo que se comprueba es justo que ese parámetro ya no
    abre nada (el adaptador de `conftest.py` lo convertiría en una sesión válida y
    el test se estaría midiendo a sí mismo).
    """
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        abiertas: list[str] = []
        for ruta, (esperado,) in CON_SESION.items():
            r = client.get(ruta, params={"user_id": uid})
            if r.status_code != esperado:
                abiertas.append(f"{ruta} → {r.status_code}")
        assert abiertas == [], (
            f"rutas de datos que respondieron sin sesión: {abiertas}"
        )


def test_la_ruta_de_la_contrasena_es_de_datos_y_exige_sesion(monkeypatch, tmp_path):
    """`PUT /api/session/password` cambia la credencial de la cuenta: no es pública.

    Va aparte de `CON_SESION` porque el diccionario de arriba se recorre con
    `GET` y esta ruta no admite `GET` (405, no 401): mezclarlas debilitaría el
    candado del otro lado sin avisar.

    V3.81: sustituye a `PUT /api/session/pin` (retirado con el PIN). Se conserva el
    mismo candado porque la ruta que cambia un secreto es justo la que no puede
    quedar abierta «porque aún no había credencial».
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/session/password",
            json={"current_password": "vieja", "new_password": "caballo-bateria-grapa"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "SESSION_REQUIRED"


def test_las_escrituras_sin_sesion_estan_declaradas_y_son_solo_cuatro(
    monkeypatch, tmp_path
):
    """V3.82: la superficie sin sesión tiene **exactamente** cuatro escrituras.

    1. `POST /api/profile-requests` — la **solicitud** de cuenta: quien la manda
       todavía no tiene ninguna. No crea nada; el webmaster decide.
    2. `POST /api/account/activate` — el primer acto del alumno: poner su
       contraseña desde el enlace de la invitación. Lo autoriza un **token** de un
       solo uso con caducidad, no una cookie (el enlace se abre en cualquier
       navegador, también en el móvil).
    3. `POST /api/account/forgot-password` — pide el restablecimiento. Responde
       200 **siempre** (no revela si el correo tiene cuenta) y solo emite token si
       la cuenta existe y está activa.
    4. `POST /api/account/reset-password` — el canje del token anterior.
    Al margen queda `POST /api/account/verify`, que también va sin sesión y se
    comprueba aparte por su efecto distinto (sella el email; no cambia secretos).

    Lo que esta lista fija es que **no crezca sin querer**: las otras rutas de
    cuenta exigen sesión (`resend-verification`, `unenroll`, y la baja de perfil),
    y las cinco que sí van sin sesión están protegidas por token o no tienen
    efecto.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        # 1: alcanzable sin sesión, y con un cuerpo que no autoriza nada.
        alta = client.post("/api/profile-requests", json={"display_name": "Marta"})
        assert alta.status_code == 201
        # 2, 3 y 4: se atienden sin sesión (token inventado ⇒ 400, nunca 401).
        assert (
            client.post(
                "/api/account/activate",
                json={"token": "x" * 32, "password": "caballo-bateria-grapa"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/account/forgot-password", json={"email": "nadie@example.com"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/account/reset-password",
                json={"token": "x" * 32, "password": "caballo-bateria-grapa"},
            ).status_code
            == 400
        )
        assert (
            client.post("/api/account/verify", json={"token": "x" * 32}).status_code
            == 400
        ), "un token inventado es 400, no 401: la ruta se atiende sin sesión"
        # Y las que no: 401 por la puerta de sesión, como cualquier dato.
        assert client.post("/api/account/resend-verification").status_code == 401
        assert (
            client.post(
                "/api/account/unenroll", json={"password": "caballo-bateria-grapa"}
            ).status_code
            == 401
        )


def test_ninguna_ruta_sin_sesion_puede_cambiar_una_contrasena_sin_token(
    monkeypatch, tmp_path
):
    """El candado que importa de la superficie nueva (V3.82).

    Tres rutas sin sesión pueden acabar escribiendo una contraseña
    (`activate`, `reset-password` y, por la vía de la invitación, ninguna más).
    Ninguna lo hace con un token **inventado**, y la contraseña de la cuenta no
    cambia. Es lo que separa «hay más superficie sin sesión» de «hay una puerta
    abierta»: lo que autoriza es un secreto de 256 bits que solo viaja por correo.
    """
    _setup(monkeypatch, tmp_path)
    from services import credentials

    uid = users_repo.create_user("Ana", email="ana@example.com")["id"]
    assert users_repo.set_password_hash(
        uid, credentials.hash_password("la-de-antes-2026")
    )
    antes = users_repo.get_password_hash(uid)

    with TestClient(app) as client:
        for ruta in ("/api/account/activate", "/api/account/reset-password"):
            r = client.post(
                ruta,
                json={"token": "x" * 32, "password": "otra-cosa-larga-2026"},
            )
            assert r.status_code == 400, f"{ruta} aceptó un token inventado"
        assert users_repo.get_password_hash(uid) == antes


def test_la_peticion_de_perfil_no_crea_nada_sin_sesion(monkeypatch, tmp_path):
    """`POST /api/profile-requests` (V3.77): sin sesión **y** sin efecto.

    Es la escritura anónima que existe porque quien pide una cuenta no tiene
    ninguna todavía, y la que protege el modo LAN: por la red se puede **pedir**,
    nunca crear. Se comprueba en el mismo test que lo que consigue es exactamente
    una fila en la cola: si algún día empezara a crear una cuenta, este es el test
    que lo dice.

    V3.82: sigue sin ser «la única escritura sin sesión». El registro
    (`POST /api/users`) ya **no** existe, y la invitación, la recuperación de
    contraseña y la verificación de email añaden cuatro rutas que se atienden sin
    cookie porque lo que autoriza es un token. Todas están declaradas y
    comprobadas en
    `test_las_escrituras_sin_sesion_estan_declaradas_y_son_solo_cuatro`.
    """
    _setup(monkeypatch, tmp_path)
    antes = len(users_repo.list_users(include_disabled=True))
    with TestClient(app) as client:
        r = client.post("/api/profile-requests", json={"display_name": "Nueva"})
    assert r.status_code == 201
    assert len(users_repo.list_users(include_disabled=True)) == antes

    # Y la de baja, que es la otra mitad, sí exige sesión.
    with TestClient(app) as client:
        assert (
            client.post("/api/profile-requests/delete", json={"note": ""}).status_code
            == 401
        )


def test_la_superficie_sin_sesion_esta_declarada_por_escrito():
    """Candado anti-deriva documental: lo aceptado tiene que estar escrito.

    Sin esto, «declarar aceptado» se queda en un comentario de un test y la
    próxima auditoría vuelve a abrir el mismo hallazgo.
    """
    from pathlib import Path

    doc = (
        Path(__file__).resolve().parents[2] / "docs" / "ARQUITECTURA.md"
    ).read_text(encoding="utf-8")

    assert "Superficie sin sesión" in doc, (
        "ARQUITECTURA.md no declara la superficie que responde sin sesión"
    )
    for ruta in (
        "/api/system/status",
        "/api/network",
        "/api/models",
        # V3.77: la petición de cuenta y su justificación (no crea nada).
        "/api/profile-requests",
        # V3.82: las rutas de cuenta sin sesión —lo que autoriza es un token de
        # un solo uso, no una cookie— y la de recuperación, que responde 200
        # siempre para no revelar qué correos tienen cuenta.
        "/api/account/activate",
        "/api/account/forgot-password",
        "/api/account/reset-password",
    ):
        assert ruta in doc, f"ARQUITECTURA.md no declara {ruta} como aceptada"
