"""PIN opcional por perfil (V3.76, Fase 3 del P0 de identidad).

Lo que este archivo fija, en orden de importancia:

1. **Compatibilidad**: un perfil sin PIN sigue entrando sin credencial. Es la
   propiedad que hace que esta fase no rompa a nadie.
2. **Puerta cerrada de verdad** para el perfil que sí lo tiene: 401 distinguibles
   (`PIN_REQUIRED` / `PIN_INVALID`) y nunca una pista de «casi».
3. **El freno de intentos en las dos direcciones**: frena al que insiste y
   *deja de frenar* al que acierta. Sin la segunda mitad, un contador que nunca
   se limpia convertiría el PIN en una condena a la primera equivocación.
4. **El hash no sale nunca**: `has_pin` es lo único que viaja en el perfil.
5. **El hash viaja en el backup** (es estado del perfil, dentro de la BD), con
   ida y vuelta real por el ZIP.
"""
import io
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import backup as backup_svc
from services import pins

_PIN = "4821"


@pytest.fixture(autouse=True)
def _freno_limpio():
    """El freno vive en memoria del proceso: sin esto, un test contamina a otro."""
    pins.reset_state()
    yield
    pins.reset_state()


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("Ana")["id"]


def _con_pin(uid: str, pin: str = _PIN) -> None:
    users_repo.set_pin_hash(uid, pins.hash_pin(pin))


# ---------------------------------------------------------------------------
# El hash (unidad, sin app)
# ---------------------------------------------------------------------------


def test_el_hash_no_guarda_el_pin_y_verifica():
    stored = pins.hash_pin(_PIN)
    assert _PIN not in stored, "el PIN en claro no puede quedar dentro del hash"
    assert stored.startswith("pbkdf2-sha256$")
    assert pins.verify_pin(stored, _PIN) is True
    assert pins.verify_pin(stored, "4822") is False


def test_dos_perfiles_con_el_mismo_pin_no_comparten_hash():
    """La sal es por perfil: si no, mirar la BD diría quién comparte PIN."""
    assert pins.hash_pin(_PIN) != pins.hash_pin(_PIN)


@pytest.mark.parametrize(
    "basura",
    ["", "pbkdf2-sha256$no-es-un-numero$a$b", "otro$1$a$b", "pbkdf2-sha256$1$$", "$"],
)
def test_un_hash_corrupto_no_autentica(basura):
    assert pins.verify_pin(basura, _PIN) is False


@pytest.mark.parametrize("pin", ["123", "1234567", "12a4", "", " 1234"])
def test_la_forma_del_pin_es_4_a_6_digitos(pin):
    assert pins.is_valid_pin(pin) is False


@pytest.mark.parametrize("pin", ["1234", "12345", "123456"])
def test_un_pin_bien_formado_se_acepta(pin):
    assert pins.is_valid_pin(pin) is True


# ---------------------------------------------------------------------------
# El freno de intentos, en las dos direcciones
# ---------------------------------------------------------------------------


def test_el_freno_empieza_a_frenar_y_crece():
    """Los primeros fallos no molestan; a partir de ahí el retardo dobla."""
    assert [pins.note_failure("u") for _ in range(pins._FREE_ATTEMPTS)] == [0.0] * 5
    primero = pins.note_failure("u")
    segundo = pins.note_failure("u")
    assert primero > 0 and segundo > primero
    assert pins.seconds_to_wait("u") > 0


def test_acertar_limpia_el_freno():
    """La otra dirección: el que acierta no arrastra el castigo de sus fallos."""
    for _ in range(pins._FREE_ATTEMPTS):
        pins.note_failure("u")
    pins.note_success("u")
    assert pins.seconds_to_wait("u") == 0.0
    # Con el contador limpio, vuelve a haber holgura completa.
    assert [pins.note_failure("u") for _ in range(pins._FREE_ATTEMPTS)] == [0.0] * 5


def test_el_freno_es_por_perfil_no_global():
    """Un perfil bajo ataque no puede dejar fuera a los demás del mismo equipo."""
    for _ in range(pins._FREE_ATTEMPTS + 3):
        pins.note_failure("ana")
    assert pins.seconds_to_wait("ana") > 0
    assert pins.seconds_to_wait("beto") == 0.0


def test_el_retardo_tiene_techo():
    for _ in range(pins._FREE_ATTEMPTS + 50):
        pins.note_failure("u")
    assert pins.seconds_to_wait("u") <= pins._MAX_DELAY_SECONDS


# ---------------------------------------------------------------------------
# La puerta: POST /api/session
# ---------------------------------------------------------------------------


def test_un_perfil_sin_pin_sigue_entrando_sin_credencial(monkeypatch, tmp_path):
    """La compatibilidad: la Fase 3 no puede cerrar la puerta de nadie."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/session", json={"user_id": uid})
        assert r.status_code == 200
        assert r.json()["id"] == uid
        assert r.json()["has_pin"] is False


def test_un_perfil_con_pin_no_abre_sin_pin(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _con_pin(uid)
    with TestClient(app) as client:
        r = client.post("/api/session", json={"user_id": uid})
        assert r.status_code == 401
        assert r.json()["detail"] == "PIN_REQUIRED"
        # Y no se ha abierto nada: la sesión sigue sin existir.
        assert client.get("/api/session").status_code == 401


def test_un_pin_incorrecto_no_revela_si_estaba_cerca(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _con_pin(uid, "4821")
    with TestClient(app) as client:
        for intento in ("4822", "0000", "48211"):
            r = client.post("/api/session", json={"user_id": uid, "pin": intento})
            assert r.status_code == 401
            assert r.json()["detail"] == "PIN_INVALID"
        assert client.get("/api/session").status_code == 401


def test_con_el_pin_correcto_abre_y_deja_cookie(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _con_pin(uid)
    with TestClient(app) as client:
        r = client.post("/api/session", json={"user_id": uid, "pin": _PIN})
        assert r.status_code == 200
        assert r.json()["id"] == uid
        assert "httponly" in r.headers["set-cookie"].lower()
        assert client.get("/api/session").json()["id"] == uid


def test_un_pin_de_mala_forma_cuenta_como_fallo(monkeypatch, tmp_path):
    """«1a» o «12» no aciertan nunca: no pueden esquivar el freno por su forma."""
    uid = _setup(monkeypatch, tmp_path)
    _con_pin(uid)
    with TestClient(app) as client:
        r = client.post("/api/session", json={"user_id": uid, "pin": "12"})
        assert r.status_code == 401
        assert r.json()["detail"] == "PIN_INVALID"


def test_el_freno_corta_por_la_api_con_retry_after(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _con_pin(uid)
    with TestClient(app) as client:
        for _ in range(pins._FREE_ATTEMPTS + 1):
            assert (
                client.post(
                    "/api/session", json={"user_id": uid, "pin": "0000"}
                ).status_code
                == 401
            )
        r = client.post("/api/session", json={"user_id": uid, "pin": "0000"})
        assert r.status_code == 429
        assert r.json()["detail"] == "PIN_THROTTLED"
        # Con la espera declarada, para que la UI pueda contarla en vez de
        # inventarse un «inténtalo más tarde» sin fondo.
        assert int(r.headers["retry-after"]) >= 1
        # Y el PIN correcto tampoco pasa mientras el freno está activo: si no, el
        # atacante tendría una ventana gratis justo cuando ha insistido más.
        assert (
            client.post(
                "/api/session", json={"user_id": uid, "pin": _PIN}
            ).status_code
            == 429
        )


# ---------------------------------------------------------------------------
# Poner, cambiar y retirar el PIN (bajo sesión)
# ---------------------------------------------------------------------------


def test_poner_cambiar_y_retirar_el_pin(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": uid}).status_code == 200

        # Poner: sin PIN previo no hace falta el actual.
        r = client.put("/api/session/pin", json={"new_pin": _PIN})
        assert r.status_code == 200
        assert r.json()["has_pin"] is True

        # Cambiar sin el actual: no. Es lo que impide quedarse el perfil ajeno
        # desde un equipo con la sesión ya abierta.
        r = client.put("/api/session/pin", json={"new_pin": "1111"})
        assert r.status_code == 401
        assert r.json()["detail"] == "PIN_REQUIRED"

        r = client.put(
            "/api/session/pin", json={"current_pin": "9999", "new_pin": "1111"}
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "PIN_INVALID"

        r = client.put(
            "/api/session/pin", json={"current_pin": _PIN, "new_pin": "1111"}
        )
        assert r.status_code == 200
        assert users_repo.get_pin_hash(uid) != ""
        assert pins.verify_pin(users_repo.get_pin_hash(uid) or "", "1111") is True

        # Retirar: `new_pin` vacío, con el actual.
        r = client.put("/api/session/pin", json={"current_pin": "1111", "new_pin": ""})
        assert r.status_code == 200
        assert r.json()["has_pin"] is False


def test_la_ruta_del_pin_exige_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put("/api/session/pin", json={"new_pin": _PIN})
        assert r.status_code == 401
        assert r.json()["detail"] == "SESSION_REQUIRED"


def test_un_pin_de_mala_forma_no_se_guarda(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/session", json={"user_id": uid}).status_code == 200
        r = client.put("/api/session/pin", json={"new_pin": "12ab"})
        assert r.status_code == 400
        assert r.json()["detail"] == "PIN_FORMAT"
        assert users_repo.get_pin_hash(uid) == ""


# ---------------------------------------------------------------------------
# El hash no se filtra
# ---------------------------------------------------------------------------


def test_has_pin_viaja_pero_el_hash_no(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _con_pin(uid)
    with TestClient(app) as client:
        r = client.get("/api/users")
        assert r.status_code == 200
        perfil = next(u for u in r.json() if u["id"] == uid)
        assert perfil["has_pin"] is True
        # Ni el campo ni el valor, en ningún rincón del cuerpo.
        assert "pin_hash" not in perfil
        assert "pbkdf2" not in r.text

        # Y el propio perfil de la sesión tampoco lo lleva.
        sesion = client.post(
            "/api/session", json={"user_id": uid, "pin": _PIN}
        ).json()
        assert sesion["has_pin"] is True
        assert "pin_hash" not in sesion


# ---------------------------------------------------------------------------
# El PIN viaja en el backup (decisión declarada, no accidente)
# ---------------------------------------------------------------------------


def test_el_pin_sobrevive_a_una_ida_y_vuelta_por_el_backup(monkeypatch, tmp_path):
    """El hash es estado del perfil y vive en la BD, así que viaja en el ZIP.

    `session.secret` **no** viaja (es la clave de firma, no estado del alumno);
    esto comprueba la otra mitad de esa decisión con el artefacto de verdad.
    """
    # Nombre de producción (`tutor.db`): `_write_zip` deriva el arcname del
    # fichero, y el ZIP real guarda el estado bajo `data/tutor.db`.
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tutor.db")
    db.init_db()
    uid = users_repo.create_user("Ana")["id"]
    _con_pin(uid)

    monkeypatch.setattr(backup_svc, "DATA_DIR", tmp_path)
    monkeypatch.setattr(backup_svc, "DB_PATH", tmp_path / "tutor.db")
    monkeypatch.setattr(backup_svc, "AUDIO_LIBRARY_DIR", tmp_path / "audio")
    monkeypatch.setattr(
        backup_svc,
        "backups_dir",
        lambda: tmp_path / "backups",
    )
    (tmp_path / "backups").mkdir(exist_ok=True)

    creado = backup_svc.create_backup()
    archivo = backup_svc.read_backup(creado["name"])

    with zipfile.ZipFile(io.BytesIO(archivo)) as zf:
        assert "session.secret" not in zf.namelist()
        with zf.open("data/tutor.db") as f:
            copia = tmp_path / "restaurada.db"
            copia.write_bytes(f.read())

    conn = sqlite3.connect(copia)
    fila = conn.execute("SELECT pin_hash FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    assert fila is not None, "el perfil restaurado tiene que seguir existiendo"
    assert pins.verify_pin(fila[0], _PIN) is True
    assert users_repo.get_user(uid)["has_pin"] is True


# ---------------------------------------------------------------------------
# Migración: la columna se añade sin bloquear a nadie
# ---------------------------------------------------------------------------


def test_una_bd_sin_la_columna_recibe_el_alter_sin_perder_perfiles(
    monkeypatch, tmp_path
):
    """Una BD de V3.75.8 no tiene `pin_hash`: el `ALTER` la añade vacía."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
        "created_at TEXT NOT NULL, is_test INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO users (id, name, created_at, is_test) VALUES "
        "('viejo', 'Ana', '2026-01-01T00:00:00Z', 0)"
    )
    conn.commit()
    conn.close()

    db.init_db()

    perfil = users_repo.get_user("viejo")
    assert perfil is not None
    assert perfil["has_pin"] is False
    assert users_repo.get_pin_hash("viejo") == ""
