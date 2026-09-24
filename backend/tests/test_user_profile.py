from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from repositories import users as users_repo

_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}
_BUENA = "caballo-bateria-grapa"


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    monkeypatch.setenv(config.ADMIN_PIN_ENV, _ADMIN_PIN)
    return users_repo.create_user("Ana")["id"]


_ALTA_SEQ = itertools.count(1)


def _alta(client, name: str, *, email: str = "", password: str = _BUENA):
    """Alta **del webmaster** (V3.82): `POST /api/admin/users` con el PIN.

    Hasta V3.81 esto era `POST /api/users`. V3.82 cierra esa puerta (una cuenta se
    pide y el webmaster la autoriza, o la crea él directamente desde el equipo) y
    estos tests, que comprueban sobre todo la forma del **nombre**, usan la vía que
    queda. El email sale de un contador: dos altas con el mismo nombre (que es
    justo lo que prueba la regla de duplicados) necesitan **dos correos
    distintos** o chocarían por `EMAIL_TAKEN` y el test culparía a la regla
    equivocada.
    """
    body = {
        "name": name,
        "email": email or f"alta-{next(_ALTA_SEQ)}@example.com",
        "password": password,
    }
    return client.post("/api/admin/users", json=body, headers=_ADMIN_HEADERS)


def test_create_user_has_default_avatar_fields(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    user = users_repo.get_user(uid)
    assert user["avatar_color"] == ""
    assert user["avatar_emoji"] == ""
    assert user["avatar_image"] == ""


def test_update_user_avatar(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    updated = users_repo.update_user(
        uid, name="Ana M", avatar_emoji="🎧", avatar_color="#6366f1"
    )
    assert updated["name"] == "Ana M"
    assert updated["avatar_emoji"] == "🎧"
    assert updated["avatar_color"] == "#6366f1"
    assert updated["avatar_image"] == ""


def test_update_user_partial_preserves_others(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    users_repo.update_user(uid, avatar_emoji="🎧")
    updated = users_repo.update_user(uid, name="Otro")
    assert updated["name"] == "Otro"
    assert updated["avatar_emoji"] == "🎧"


def test_update_user_unknown_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert users_repo.update_user("no-existe", name="x") is None


def test_api_patch_user(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # V3.75 (Fase 2 del P0): `PATCH /api/users/{id}` exige **sesión** y solo deja
    # editar el perfil propio, así que el test declara con quién actúa (el
    # adaptador de `conftest.py` lo traduce a una sesión firmada de verdad). El
    # caso que faltaba —sesión de A editando a B ⇒ 403— vive en
    # `test_users_self_only.py`.
    with TestClient(app) as client:
        r = client.patch(
            f"/api/users/{uid}",
            json={"name": "Ana 2", "avatar_emoji": "🚀"},
            params={"user_id": uid},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Ana 2"
        assert body["avatar_emoji"] == "🚀"


def test_api_patch_user_unknown(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.patch(
                "/api/users/no-existe",
                json={"name": "x"},
                params={"user_id": "no-existe"},
            ).status_code
            == 404
        )


def test_api_hides_test_profiles_and_deletes_them(monkeypatch, tmp_path):
    # V3.52.1: el perfil de prueba no aparece en GET /api/users; DELETE lo limpia.
    # V3.82: ya no se crea por API (`POST /api/users` no existe), así que lo crea el
    # repo —que es lo único que puede marcar `is_test`— y la **lectura** sí se
    # prueba por HTTP, que es donde vive la garantía de invisibilidad. Como
    # `GET /api/users` dejó de ser público, se pide con sesión.
    uid = _setup(monkeypatch, tmp_path)
    tester = users_repo.create_user("Visual Tester", is_test=True)
    assert tester["is_test"] is True
    with TestClient(app) as client:
        listed = client.get("/api/users", params={"user_id": uid}).json()
        assert [u["name"] for u in listed] == ["Usuario", "Ana"]
        with_test = client.get(
            "/api/users", params={"include_test": True, "user_id": uid}
        ).json()
        assert "Visual Tester" in [u["name"] for u in with_test]
        deleted = client.delete(f"/api/users/{tester['id']}")
        assert deleted.status_code == 200, deleted.text
        remaining = client.get(
            "/api/users", params={"include_test": True, "user_id": uid}
        ).json()
        assert "Visual Tester" not in [u["name"] for u in remaining]
        # Un perfil real no se puede borrar por esta vía.
        assert client.delete(f"/api/users/{uid}").status_code == 404
        assert users_repo.get_user(uid) is not None


def test_sin_sesion_no_se_enumera_quien_tiene_cuenta(monkeypatch, tmp_path):
    """V3.82: la lista de cuentas vuelve detrás de la puerta.

    Era pública porque la entrada era un **selector** que tenía que pintar los
    nombres antes de que existiera sesión. Con el login por email esa necesidad
    desaparece, así que enumerar deja de ser gratis para quien alcance la API.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/users")
    assert r.status_code == 401


def test_create_user_rejects_an_overlong_name(monkeypatch, tmp_path):
    """El nombre lleva tope (V3.73.x).

    Antes solo `PATCH` acotaba `name`; crear un perfil con un nombre de tamaño
    arbitrario era una vía trivial de crecimiento de la base de datos. El tope se
    prueba con el resto de campos bien puestos: si no, el 422 lo daría un email
    ausente y el test pasaría sin haber mirado el nombre.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _alta(client, "x" * 10_000)
    assert r.status_code == 422


def test_create_user_accepts_a_name_at_the_limit(monkeypatch, tmp_path):
    """El tope no recorta el caso legítimo (80 caracteres)."""
    _setup(monkeypatch, tmp_path)
    nombre = "n" * 80
    with TestClient(app) as client:
        r = _alta(client, nombre)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["name"] == nombre


def test_create_user_rejects_a_duplicate_name(monkeypatch, tmp_path):
    """V3.80.2: dos usuarios activos con el mismo nombre son indistinguibles.

    El lanzador y la consola identifican a las cuentas por su nombre: con dos
    «Ana» no hay forma de saber a quién se le purga el historial. El `_setup` ya
    crea «Ana», así que esta alta choca.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _alta(client, "Ana")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "USER_NAME_TAKEN"


def test_the_duplicate_rule_ignores_spaces_and_case(monkeypatch, tmp_path):
    """«  ana  » es el mismo nombre que «Ana» para el ojo que lo lee."""
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = _alta(client, "  ANA  ")
    assert r.status_code == 409, r.text


def test_the_duplicate_rule_does_not_block_test_profiles(monkeypatch, tmp_path):
    """Los perfiles de prueba quedan fuera: los crea y borra el teardown visual.

    Si chocaran con esta regla, un residuo de un test fallido convertiría el
    siguiente alta en un error — justo al revés de lo que la regla busca. V3.82:
    el perfil de prueba ya no se puede crear por API, así que se prepara por
    repositorio y lo que se prueba por HTTP es que **no bloquea** un alta real con
    el mismo nombre.
    """
    _setup(monkeypatch, tmp_path)
    users_repo.create_user("Visual Tester", is_test=True)
    with TestClient(app) as client:
        r = _alta(client, "Visual Tester")
    assert r.status_code == 200, r.text


def test_a_disabled_user_frees_their_name(monkeypatch, tmp_path):
    """Una cuenta desactivada ya no compite por su nombre."""
    uid = _setup(monkeypatch, tmp_path)
    users_repo.set_status(uid, users_repo.STATUS_DISABLED)
    with TestClient(app) as client:
        r = _alta(client, "Ana")
    assert r.status_code == 200, r.text
