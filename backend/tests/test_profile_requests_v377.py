"""Perfiles con autorización del webmaster (V3.77).

Los candados que fija este archivo, en el orden en que importan:

1. **Una petición es inerte.** Pedir un perfil no crea ninguno, ni con el nombre
   más razonable del mundo. Si esto se rompe, la cola deja de ser una cola y pasa
   a ser un alta sin autorización.
2. **Aprobar crea exactamente uno**, y aprobar dos veces no crea dos. El segundo
   intento tiene que chocar con la petición ya resuelta.
3. **La administración exige las dos llaves**: PIN y estar en el equipo. Sin PIN
   (fail-closed) o desde fuera, no pasa — y las dos se prueban por separado,
   porque un candado que solo se prueba junto al otro no se sabe si funciona.
4. **Desactivar conserva la evidencia; purgar se la lleva.** Y purgar exige el
   nombre exacto y deja copia.
5. **Un perfil desactivado no abre sesión**, aunque la cookie vieja siga firmada.

`ADMIN_PIN` se declara por **entorno** (`ENGLISH_TUTOR_ADMIN_PIN`), que es como lo
declara el lanzador: estos tests ejercen la vía real, no una constante de adorno.
"""
from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from repositories import profile_requests as requests_repo
from repositories import users as users_repo
from services import backup as backup_svc

_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}
# Cliente que **no** es el equipo: lo que vería un móvil de la LAN.
_FOREIGN_CLIENT = ("203.0.113.9", 45000)


def _setup(monkeypatch, tmp_path):
    """BD aislada + backup aislado + PIN de administración declarado."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    # El backup escribe en `DATA_DIR/backups` y lee `DB_PATH` **por valor** al
    # importar, así que se reapunta también aquí: si no, purgar escribiría una
    # copia en el `data/` real del proyecto.
    monkeypatch.setattr(backup_svc, "DATA_DIR", tmp_path)
    monkeypatch.setattr(backup_svc, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(backup_svc, "AUDIO_LIBRARY_DIR", tmp_path / "audio_library")
    monkeypatch.setenv(config.ADMIN_PIN_ENV, _ADMIN_PIN)
    return users_repo.create_user("Ana")["id"]


def _pendientes() -> list[dict]:
    return requests_repo.list_requests(requests_repo.STATUS_PENDING)


# --- 1. La petición es inerte ------------------------------------------------


def test_una_peticion_pendiente_no_crea_ningun_perfil(monkeypatch, tmp_path):
    """El candado central: pedir no es obtener."""
    _setup(monkeypatch, tmp_path)
    antes = len(users_repo.list_users(include_disabled=True))
    with TestClient(app) as client:
        r = client.post(
            "/api/profile-requests",
            json={"display_name": "Marta", "note": "es para mi hija"},
        )
    assert r.status_code == 201
    assert r.json()["status"] == requests_repo.STATUS_PENDING
    despues = users_repo.list_users(include_disabled=True)
    assert len(despues) == antes, "una petición pendiente creó un perfil"
    assert not any(u["name"] == "Marta" for u in despues)


def test_pedir_dos_veces_el_mismo_nombre_no_llena_la_cola(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        primera = client.post("/api/profile-requests", json={"display_name": "Marta"})
        repetida = client.post(
            "/api/profile-requests", json={"display_name": "  marta "}
        )
    assert primera.status_code == 201
    # Ni las mayúsculas ni los espacios de más esquivan la regla: es la misma
    # persona pidiendo el mismo perfil.
    assert repetida.status_code == 409
    assert len(_pendientes()) == 1


def test_un_nombre_que_no_sirve_no_registra_nada(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        vacio = client.post("/api/profile-requests", json={"display_name": "   "})
    assert vacio.status_code == 422
    assert _pendientes() == []


def test_la_cola_llena_rechaza_con_429_y_no_registra(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "PROFILE_REQUEST_MAX_PENDING", 1)
    with TestClient(app) as client:
        primera = client.post("/api/profile-requests", json={"display_name": "Marta"})
        llena = client.post("/api/profile-requests", json={"display_name": "Luis"})
    assert primera.status_code == 201
    assert llena.status_code == 429
    assert [r["display_name"] for r in _pendientes()] == ["Marta"]


def test_la_peticion_de_baja_exige_sesion_y_no_borra_nada(monkeypatch, tmp_path):
    """Sin sesión no hay baja, y con sesión sigue sin borrarse nada."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        sin_sesion = client.post("/api/profile-requests/delete", json={"note": ""})
        assert sin_sesion.status_code == 401, "la baja de un perfil no es pública"

        con_sesion = client.post(
            "/api/profile-requests/delete",
            json={"note": "quiero empezar de cero"},
            params={"user_id": uid},
        )
        assert con_sesion.status_code == 201
        repetida = client.post(
            "/api/profile-requests/delete",
            json={"note": ""},
            params={"user_id": uid},
        )
    assert repetida.status_code == 409
    ana = users_repo.get_user(uid)
    assert ana is not None, "la petición de baja borró el perfil"
    assert ana["status"] == users_repo.STATUS_ACTIVE


# --- 2. Aprobar y rechazar ---------------------------------------------------


def test_aprobar_un_alta_crea_exactamente_un_perfil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        pedida = client.post(
            "/api/profile-requests", json={"display_name": "Marta"}
        ).json()
        creada = client.post(
            f"/api/admin/profile-requests/{pedida['id']}/approve",
            json={"note": "adelante"},
            headers=_ADMIN_HEADERS,
        )
        repetida = client.post(
            f"/api/admin/profile-requests/{pedida['id']}/approve",
            json={"note": ""},
            headers=_ADMIN_HEADERS,
        )
    assert creada.status_code == 200
    creado = creada.json()
    assert creado["status"] == requests_repo.STATUS_APPROVED
    assert creado["resolved_user_id"]

    marta = users_repo.get_user(creado["resolved_user_id"])
    assert marta is not None
    assert marta["name"] == "Marta"
    # V3.81: aprobar ya **no** crea credencial. El PIN se retiró y la contraseña
    # se asigna después desde la consola de gestión (con `must_change_password`),
    # así que la cuenta nace «sin credencial» y el lanzador la lista como tarea.
    assert marta["has_password"] is False
    assert len([u for u in users_repo.list_users() if u["name"] == "Marta"]) == 1

    assert repetida.status_code == 409, "aprobar dos veces creó dos perfiles"
    assert len([u for u in users_repo.list_users() if u["name"] == "Marta"]) == 1


def test_rechazar_deja_la_peticion_resuelta_y_sin_perfil(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        pedida = client.post(
            "/api/profile-requests", json={"display_name": "Marta"}
        ).json()
        rechazada = client.post(
            f"/api/admin/profile-requests/{pedida['id']}/reject",
            json={"note": "habla conmigo antes", "pin": ""},
            headers=_ADMIN_HEADERS,
        )
    assert rechazada.status_code == 200
    assert rechazada.json()["status"] == requests_repo.STATUS_REJECTED
    assert rechazada.json()["decided_note"] == "habla conmigo antes"
    assert not any(u["name"] == "Marta" for u in users_repo.list_users())


def test_aprobar_una_baja_desactiva_pero_no_purga(monkeypatch, tmp_path):
    """Aprobar un borrado es la mitad reversible: el perfil sigue ahí."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        pedida = client.post(
            "/api/profile-requests/delete", json={"note": ""}, params={"user_id": uid}
        ).json()
        aprobada = client.post(
            f"/api/admin/profile-requests/{pedida['id']}/approve",
            json={"note": "", "pin": ""},
            headers=_ADMIN_HEADERS,
        )
    assert aprobada.status_code == 200
    ana = users_repo.get_user(uid)
    assert ana is not None, "aprobar una baja purgó el perfil"
    assert ana["status"] == users_repo.STATUS_DISABLED
    # Y sale del selector de la app, que es el efecto que sí se pidió.
    assert uid not in [u["id"] for u in users_repo.list_users()]
    assert uid in [u["id"] for u in users_repo.list_users(include_disabled=True)]


# --- 3. Las dos llaves de la administración ----------------------------------


def test_la_administracion_esta_deshabilitada_sin_pin(monkeypatch, tmp_path):
    """Fail-closed: sin PIN declarado, las rutas admin no existen para nadie."""
    _setup(monkeypatch, tmp_path)
    monkeypatch.delenv(config.ADMIN_PIN_ENV, raising=False)
    monkeypatch.setattr(config, "ADMIN_PIN", "")
    with TestClient(app) as client:
        r = client.get("/api/admin/users", headers=_ADMIN_HEADERS)
    assert r.status_code == 401
    assert "deshabilitada" in r.json()["detail"]


def test_la_administracion_no_pasa_sin_el_pin(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/admin/users")
    assert r.status_code == 401


def test_la_administracion_de_perfiles_no_se_ejerce_desde_la_red(monkeypatch, tmp_path):
    """La segunda llave: con el PIN correcto, pero desde fuera del equipo, no.

    Se prueba sobre una acción destructiva (purga) para que el test diga lo que
    de verdad está en juego: no es «no puedo ver la lista», es «no puedo borrar
    la evidencia de un alumno desde la red».
    """
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app, client=_FOREIGN_CLIENT) as client:
        listado = client.get("/api/admin/users", headers=_ADMIN_HEADERS)
        purga = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Ana"},
            headers=_ADMIN_HEADERS,
        )
    assert listado.status_code == 403
    assert purga.status_code == 403
    assert users_repo.get_user(uid) is not None, "se purgó desde fuera del equipo"


def test_crear_un_perfil_desde_la_red_esta_cerrado(monkeypatch, tmp_path):
    """V3.77 cierra el alta anónima por LAN: por la red se **solicita**.

    V3.81: el cuerpo tiene que ser un registro **completo** (nombre, email y
    contraseña) para que la petición llegue siquiera a la frontera de equipo. Con
    un cuerpo recortado el 422 de Pydantic salta antes y el test dejaría de
    comprobar lo que dice comprobar (que desde la red no se crea nada).
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app, client=_FOREIGN_CLIENT) as client:
        directa = client.post(
            "/api/users",
            json={
                "name": "Intruso",
                "email": "intruso@example.com",
                "password": "caballo-bateria-grapa",
            },
        )
        pedida = client.post("/api/profile-requests", json={"display_name": "Ana"})
    assert directa.status_code == 403
    assert not any(u["name"] == "Intruso" for u in users_repo.list_users())
    # La puerta que sí queda abierta desde la red es la petición, y sin sesión.
    assert pedida.status_code == 201


def test_el_alta_del_propio_equipo_sigue_funcionando(monkeypatch, tmp_path):
    """Lo que no puede pasar es cerrar de más: el primer arranque es local."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/users",
            json={
                "name": "Primer Arranque",
                "email": "arranque@example.com",
                "password": "caballo-bateria-grapa",
            },
        )
    assert r.status_code == 200
    assert r.json()["status"] == users_repo.STATUS_ACTIVE
    # Y nace con credencial: ya no hay «un nombre y a correr» (Fase 3 del P0).
    assert r.json()["has_password"] is True
    assert r.json()["email"] == "arranque@example.com"
    assert r.json()["email_verified"] is False


# --- 4. Desactivar conserva; purgar se lleva ---------------------------------


def test_desactivar_conserva_la_evidencia_y_purgar_la_elimina(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO vocabulary "
            "(user_id, word, production_count, first_seen, last_seen) "
            "VALUES (?, 'hello', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (uid,),
        )

    def _vocab() -> int:
        with closing(db._conn()) as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM vocabulary WHERE user_id = ?", (uid,)
                ).fetchone()[0]
            )

    assert _vocab() == 1
    with TestClient(app) as client:
        apagado = client.post(
            f"/api/admin/users/{uid}/status",
            json={"status": "disabled"},
            headers=_ADMIN_HEADERS,
        )
    assert apagado.status_code == 200
    assert _vocab() == 1, "desactivar se llevó evidencia"

    with TestClient(app) as client:
        mal_nombre = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Otra"},
            headers=_ADMIN_HEADERS,
        )
        assert mal_nombre.status_code == 409
        assert users_repo.get_user(uid) is not None, "se purgó sin confirmar el nombre"

        purgado = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "  ana  "},
            headers=_ADMIN_HEADERS,
        )
    assert purgado.status_code == 200
    cuerpo = purgado.json()
    assert cuerpo["purged"] is True
    assert cuerpo["backup"].startswith("backup_")
    # La copia existe de verdad: es la única red que hay.
    assert (tmp_path / "backups" / cuerpo["backup"]).exists()
    assert users_repo.get_user(uid) is None
    assert _vocab() == 0


def test_purgar_un_perfil_activo_se_rechaza(monkeypatch, tmp_path):
    """El candado que obliga a desactivar antes: purgar no es un clic de más.

    Sin esto, el camino corto («seleccionar perfil → purgar») destruiría la
    evidencia de un perfil que puede estar en uso. El lanzador ya lo bloquea, pero
    el candado tiene que estar donde se borra, no solo donde se pulsa.
    """
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        directa = client.post(
            f"/api/admin/users/{uid}/purge",
            json={"confirm_name": "Ana"},
            headers=_ADMIN_HEADERS,
        )
    assert directa.status_code == 409
    assert users_repo.get_user(uid) is not None, "se purgó un perfil activo"


# --- 5. Un perfil desactivado no abre sesión ---------------------------------


def test_un_perfil_desactivado_no_abre_sesion_ni_usa_la_que_tenia(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": uid}).status_code == 200
        # Con la sesión ya abierta, el webmaster desactiva el perfil.
        with TestClient(app) as admin:
            apagado = admin.post(
                f"/api/admin/users/{uid}/status",
                json={"status": "disabled"},
                headers=_ADMIN_HEADERS,
            )
        assert apagado.status_code == 200

        # La cookie sigue firmada y sin caducar: aun así, no vale.
        r = client.get("/api/session")
        assert r.status_code == 403
        assert r.json()["detail"] == "PROFILE_DISABLED"
        assert client.get("/api/settings").status_code == 403

        # Y no se puede volver a abrir sesión con ese perfil.
        reabrir = client.post("/api/session", json={"user_id": uid})
        assert reabrir.status_code == 403
        assert reabrir.json()["detail"] == "PROFILE_DISABLED"


def test_reactivar_devuelve_el_perfil_al_selector_y_a_la_sesion(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            f"/api/admin/users/{uid}/status",
            json={"status": "disabled"},
            headers=_ADMIN_HEADERS,
        )
        reactivado = client.post(
            f"/api/admin/users/{uid}/status",
            json={"status": "active"},
            headers=_ADMIN_HEADERS,
        )
    assert reactivado.status_code == 200
    assert uid in [u["id"] for u in users_repo.list_users()]
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": uid}).status_code == 200


# --- 6. La cola que ve el webmaster ------------------------------------------


def test_el_listado_de_pendientes_llega_ordenado_y_con_su_contador(
    monkeypatch, tmp_path
):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for nombre in ("Primera", "Segunda"):
            client.post("/api/profile-requests", json={"display_name": nombre})
        listado = client.get("/api/admin/profile-requests", headers=_ADMIN_HEADERS)
    assert listado.status_code == 200
    cuerpo = listado.json()
    assert [r["display_name"] for r in cuerpo["requests"]] == ["Primera", "Segunda"]
    assert cuerpo["pending"] == 2


def test_un_estado_de_filtro_inventado_no_se_traga(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get(
            "/api/admin/profile-requests?status=loquesea", headers=_ADMIN_HEADERS
        )
    assert r.status_code == 422


def test_el_alta_directa_del_webmaster_no_pasa_por_la_cola(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        # Contraseña con mala forma: se rechaza **antes** de tocar la BD.
        mala = client.post(
            "/api/admin/users",
            json={
                "name": "Directo",
                "email": "directo@example.com",
                "password": "corta",
            },
            headers=_ADMIN_HEADERS,
        )
        assert mala.status_code == 400
        assert mala.json()["detail"] == "PASSWORD_FORMAT"

        # Sin contraseña en el cuerpo, el backend **genera una temporal** y obliga
        # a cambiarla: el webmaster la entrega sin inventarse nada ni llegar a
        # conocer la definitiva del alumno.
        buena = client.post(
            "/api/admin/users",
            json={"name": "Directo", "email": "Directo@Example.COM"},
            headers=_ADMIN_HEADERS,
        )
    assert buena.status_code == 200
    cuerpo = buena.json()
    assert cuerpo["user"]["has_password"] is True
    assert cuerpo["user"]["email"] == "directo@example.com", "el email se normaliza"
    assert cuerpo["temporary_password"], "sin contraseña se genera una temporal"
    assert cuerpo["user"]["must_change_password"] is True
    assert _pendientes() == []
