# -*- coding: utf-8 -*-
"""Prueba end-to-end de la **gestión de usuarios** (V3.81) sobre una copia de la BD.

Es la segunda capa de verificación de la release, la que las suites no pueden dar:
arranca el backend **de verdad** (`uvicorn`, en un hilo, en `127.0.0.1` y un puerto
local configurable —`--port`, por defecto 8137—) sobre una **copia** de
`data/tutor.db` y ejerce el flujo completo por HTTP real —
alta autoservicio, contraseña y freno de intentos, verificación de email en modo
híbrido (sin SMTP), baja autoservicio, consola de administración, revocación por
época, purga con copia previa e historial que sobrevive a la purga— comprobando
además lo que **no** puede cambiar: la evidencia de los demás y la BD original.

**Por qué existe.** La auditoría de V3.80.0 señaló como defecto una cifra «medida
en la BD real» que no se podía reproducir desde el repositorio. Esta prueba no
vuelve a caer en eso: **cualquiera puede correrla** con su propia copia y obtener
el mismo recorrido.

Uso (desde la raíz del repositorio, con el intérprete del backend):

    backend\\.venv\\Scripts\\python.exe backend\\scripts\\e2e_accounts_v381.py

Opciones:

    --db RUTA     BD de partida (por defecto `backend/data/tutor.db`). **Se copia**;
                  el fichero indicado no se modifica nunca.
    --port N      puerto del backend efímero (por defecto 8137).
    --keep        no borra el directorio temporal (para mirar la copia a mano).

No toca la app en marcha ni sus ficheros: `config.DATA_DIR` se redirige al
directorio temporal **antes** de importar `main`, así que la copia, sus copias de
seguridad y su `session.secret` viven y mueren en el temporal. La última
comprobación del guion lo verifica de forma explícita (sha256 de la BD real).

Devuelve 0 si todos los pasos pasan y 1 si alguno falla.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
DEFAULT_DB = BACKEND_DIR / "data" / "tutor.db"

ADMIN_PIN = "pin-de-prueba-e2e-381"
PASSWORD = "caballo-bateria-grapa"
PASSWORD2 = "bateria-caballo-grapa"
# Cuenta heredada que se **siembra** en la copia (no se depende de la BD de
# entrada): el escenario de migración de V3.81.x tiene que ser reproducible en
# cualquier copia, no saltarse «porque no había ninguna».
LEGACY_ID = "e2e-legacy-sin-credencial-381"
LEGACY_NAME = "E2E Heredada"
TABLES = ["users", "vocabulary", "learning_events", "conversations", "messages"]

failures: list[str] = []
steps = 0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def counts(path: Path) -> dict:
    """Recuentos de las tablas que **no** deben moverse, más el historial."""
    con = _ro(path)
    try:
        out = {
            t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES
        }
        out["user_events"] = con.execute("SELECT COUNT(*) FROM user_events").fetchone()[
            0
        ]
        return out
    finally:
        con.close()


def identities(path: Path) -> set:
    con = _ro(path)
    try:
        return set(con.execute("SELECT id, name FROM users").fetchall())
    finally:
        con.close()


def _insert_legacy_account(path: Path) -> None:
    """Siembra una cuenta heredada **sin credencial** en la copia de trabajo.

    Solo se escriben las columnas que existen en cualquier versión del esquema
    (`id`, `name`, `created_at`): el `init_db()` del backend, al arrancar, añade
    las demás con sus valores por defecto —`password_hash = ''` entre ellas—, que
    es exactamente el estado de una cuenta anterior a V3.81. Escribirla aquí (y no
    en el original) mantiene la garantía de que el fichero de partida no se toca.
    """
    con = sqlite3.connect(path)
    try:
        with con:
            con.execute(
                "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
                (LEGACY_ID, LEGACY_NAME, "2024-01-01T00:00:00+00:00"),
            )
    finally:
        con.close()


def check(label: str, ok: bool, detail: str = "") -> bool:
    global steps
    steps += 1
    mark = "OK  " if ok else "FALLO"
    print(f"[{mark}] {label}" + (f" :: {detail}" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


class Client:
    """Un «navegador»: jar de cookies propio, como si fuera otro dispositivo."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def call(
        self,
        method: str,
        path: str,
        body=None,
        pin: str | None = None,
        cookie: str | None = None,
    ) -> tuple[int, dict | list | str]:
        data = None
        headers: dict[str, str] = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if pin:
            headers["X-Admin-Pin"] = pin
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                code = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            code = exc.code
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return code, parsed

    def session_cookie(self) -> str:
        for c in self.jar:
            if c.name == "et_session":
                return f"{c.name}={c.value}"
        return ""


def detail_of(payload) -> str:
    if isinstance(payload, dict):
        return str(payload.get("detail") or payload.get("reason") or payload)
    return str(payload)[:120]


def _failed_login(base: str, user_id: str, password: str) -> tuple[int, str]:
    """Intento de apertura de sesión **a pelo**: permite leer el 429 y su cabecera."""
    req = urllib.request.Request(
        base + "/api/session",
        data=json.dumps({"user_id": user_id, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code, exc.headers.get("Retry-After", "")


def run(db_path: Path, port: int, keep: bool) -> int:
    base = f"http://127.0.0.1:{port}"
    tmp = Path(tempfile.mkdtemp(prefix="et-e2e-v381-"))
    data = tmp / "data"
    data.mkdir(parents=True)
    copy_db = data / "tutor.db"
    shutil.copy2(db_path, copy_db)
    _insert_legacy_account(copy_db)

    real_before = counts(db_path)
    real_sha = sha(db_path)
    copy_before = counts(copy_db)
    ids_before = identities(copy_db)
    print(f"# BD de partida: {db_path}")
    print(f"# copia de trabajo: {copy_db}")
    print(f"# sha256 de la original: {real_sha}")
    print(f"# filas (original): {real_before}")
    print(f"# cuentas que ya existían: {len(ids_before)}")

    sys.path.insert(0, str(BACKEND_DIR))
    os.environ["ENGLISH_TUTOR_ADMIN_PIN"] = ADMIN_PIN
    import config  # noqa: E402

    # Redirección del almacén **antes** de importar la app: los módulos que hacen
    # `from config import DATA_DIR` fijan el valor al importarse.
    config.DATA_DIR = data
    config.CERTS_DIR = data / "certs"
    config.TLS_CERT_PATH = data / "certs" / "cert.pem"
    config.TLS_KEY_PATH = data / "certs" / "key.pem"

    import uvicorn  # noqa: E402

    import main  # noqa: E402

    server = uvicorn.Server(
        uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{base}/api/health/live", timeout=2) as resp:
                if resp.status == 200:
                    break
        except Exception:  # noqa: BLE001 - el servidor aún no escucha
            time.sleep(0.5)
    else:
        print("FATAL: el backend no arrancó")
        return 2
    print(f"# backend efímero escuchando en {base}\n")

    anon = Client(base)
    a_client = Client(base)
    b_client = Client(base)
    c_client = Client(base)
    admin = Client(base)

    # --- 0 · La puerta: nombres sin sesión, correos nunca ------------------
    code, users = anon.call("GET", "/api/users")
    check("0.1 GET /api/users responde 200 sin sesión", code == 200, f"{code}")
    emails = [u.get("email") for u in users if isinstance(u, dict)]
    check(
        "0.2 sin sesión NO se filtra ningún correo de otra cuenta",
        all(e == "" for e in emails),
        f"{len(users)} cuentas, correos vacíos: {emails.count('')}/{len(emails)}",
    )
    legacy = next((u for u in users if u.get("id") == LEGACY_ID), None)
    check(
        "0.3 la cuenta heredada sembrada en la copia sale sin credencial",
        legacy is not None and legacy.get("has_password") is False,
        (
            f"{sum(1 for u in users if not u.get('has_password'))} de {len(users)}"
            " sin credencial"
        ),
    )

    # --- 1 · Alta autoservicio --------------------------------------------
    code, a = a_client.call(
        "POST",
        "/api/users",
        {"name": "E2E Ana", "email": "e2e.ana@example.test", "password": PASSWORD},
    )
    check(
        "1.1 alta autoservicio en loopback",
        code == 200 and a.get("name") == "E2E Ana",
        f"{code} {detail_of(a)}",
    )
    a_id = a.get("id", "")
    check(
        "1.2 la cuenta nace sin verificar y con credencial",
        a.get("email_verified") is False and a.get("has_password") is True,
        f"verified={a.get('email_verified')} has_password={a.get('has_password')}",
    )

    code, payload = anon.call(
        "POST",
        "/api/users",
        {"name": "E2E Ana", "email": "otra@example.test", "password": PASSWORD},
    )
    check(
        "1.3 nombre repetido -> 409 USER_NAME_TAKEN",
        code == 409 and payload.get("detail") == "USER_NAME_TAKEN",
        f"{code}",
    )

    code, payload = anon.call(
        "POST",
        "/api/users",
        {"name": "E2E Otra", "email": "E2E.Ana@Example.Test", "password": PASSWORD},
    )
    check(
        "1.4 email repetido (otra caja/espacios) -> 409 EMAIL_TAKEN",
        code == 409 and payload.get("detail") == "EMAIL_TAKEN",
        f"{code}",
    )

    code, payload = anon.call(
        "POST",
        "/api/users",
        {"name": "E2E Corta", "email": "corta@example.test", "password": "corta"},
    )
    check(
        "1.5 contraseña con mala forma -> 400 PASSWORD_FORMAT",
        code == 400 and payload.get("detail") == "PASSWORD_FORMAT",
        f"{code}",
    )

    code, payload = anon.call(
        "POST",
        "/api/users",
        {"name": "E2E Mala", "email": "no-es-un-email", "password": PASSWORD},
    )
    check(
        "1.6 email con mala forma -> 400 EMAIL_FORMAT",
        code == 400 and payload.get("detail") == "EMAIL_FORMAT",
        f"{code}",
    )

    # --- 2 · Abrir sesión: contraseña exigida y freno ----------------------
    code, payload = anon.call("POST", "/api/session", {"user_id": a_id})
    check(
        "2.1 sin contraseña -> 401 PASSWORD_REQUIRED",
        code == 401 and payload.get("detail") == "PASSWORD_REQUIRED",
        f"{code}",
    )

    statuses = []
    retry_after = ""
    for _ in range(7):
        status, wait = _failed_login(base, a_id, "no-es-esta-clave")
        statuses.append(status)
        retry_after = retry_after or wait
    check(
        "2.2 contraseña incorrecta -> 401, y el 6º fallo ya frena (429)",
        statuses[:6] == [401] * 6 and statuses[6] == 429,
        f"{statuses}",
    )
    check(
        "2.3 el 429 trae Retry-After", bool(retry_after), f"Retry-After={retry_after}"
    )

    code, payload = anon.call(
        "POST", "/api/session", {"user_id": a_id, "password": PASSWORD}
    )
    check(
        "2.4 con el freno activo, la contraseña correcta tampoco entra (429)",
        code == 429,
        f"{code} {detail_of(payload)}",
    )

    # --- 3 · Sesión real de B, y la revocación por época -------------------
    code, b = b_client.call(
        "POST",
        "/api/users",
        {"name": "E2E Bea", "email": "e2e.bea@example.test", "password": PASSWORD},
    )
    b_id = b.get("id", "")
    check("3.1 segunda cuenta creada", code == 200, f"{code}")

    code, payload = b_client.call(
        "POST", "/api/session", {"user_id": b_id, "password": PASSWORD}
    )
    check(
        "3.2 con la contraseña correcta abre sesión",
        code == 200 and payload.get("id") == b_id,
        f"{code} {detail_of(payload)}",
    )
    old_cookie = b_client.session_cookie()
    check(
        "3.3 la cookie de sesión existe",
        old_cookie.startswith("et_session="),
        old_cookie[:22],
    )

    code, me = b_client.call("GET", "/api/session")
    check(
        "3.4 con sesión, su propio correo sí se ve",
        code == 200 and me.get("email") == "e2e.bea@example.test",
        f"{code} {me.get('email')}",
    )

    code, payload = b_client.call(
        "PUT",
        "/api/session/password",
        {"current_password": "no-es-esta", "new_password": PASSWORD2},
    )
    check(
        "3.5 cambiar la contraseña exige la actual -> 401 PASSWORD_INVALID",
        code == 401 and payload.get("detail") == "PASSWORD_INVALID",
        f"{code}",
    )

    code, payload = b_client.call(
        "PUT",
        "/api/session/password",
        {"current_password": PASSWORD, "new_password": PASSWORD2},
    )
    check(
        "3.6 con la actual, la contraseña cambia",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    code, payload = b_client.call("GET", "/api/session", cookie=old_cookie)
    check(
        "3.7 la cookie ANTERIOR deja de valer al instante (401 SESSION_STALE)",
        code == 401 and payload.get("detail") == "SESSION_STALE",
        f"{code} {detail_of(payload)}",
    )

    code, _ = b_client.call(
        "POST", "/api/session", {"user_id": b_id, "password": PASSWORD}
    )
    check("3.8 la contraseña vieja ya no abre", code == 401, f"{code}")
    code, payload = b_client.call(
        "POST", "/api/session", {"user_id": b_id, "password": PASSWORD2}
    )
    check(
        "3.9 con la nueva, vuelve a entrar", code == 200, f"{code} {detail_of(payload)}"
    )

    # --- 4 · Email: señal, no muro (sin SMTP) ------------------------------
    code, _ = b_client.call(
        "PUT",
        "/api/session/email",
        {"email": "otra.bea@example.test", "password": "no-es-esta"},
    )
    check("4.1 cambiar el correo exige la contraseña", code == 401, f"{code}")

    code, payload = b_client.call(
        "PUT",
        "/api/session/email",
        {"email": "e2e.ana@example.test", "password": PASSWORD2},
    )
    check(
        "4.2 correo ya en uso -> 409 EMAIL_TAKEN",
        code == 409 and payload.get("detail") == "EMAIL_TAKEN",
        f"{code}",
    )

    code, payload = b_client.call(
        "PUT",
        "/api/session/email",
        {"email": "bea.v2@example.test", "password": PASSWORD2},
    )
    check(
        "4.3 con la contraseña, el correo cambia y vuelve a estar sin verificar",
        code == 200
        and payload.get("email") == "bea.v2@example.test"
        and payload.get("email_verified") is False,
        f"{code} {payload.get('email') if isinstance(payload, dict) else payload}",
    )

    code, payload = b_client.call("POST", "/api/account/resend-verification")
    check(
        "4.4 sin SMTP, el reenvío dice la VERDAD (sent=false, SMTP_NOT_CONFIGURED)",
        code == 200
        and payload.get("sent") is False
        and payload.get("reason") == "SMTP_NOT_CONFIGURED",
        f"{code} {payload}",
    )

    code, payload = anon.call(
        "POST", "/api/account/verify", {"token": "token-inventado"}
    )
    check(
        "4.5 token inválido -> 400 VERIFY_TOKEN_INVALID",
        code == 400 and payload.get("detail") == "VERIFY_TOKEN_INVALID",
        f"{code}",
    )

    code, _ = anon.call("POST", "/api/account/resend-verification")
    check("4.6 el reenvío SÍ exige sesión (401)", code == 401, f"{code}")

    # --- 5 · La consola de administración ---------------------------------
    code, _ = admin.call("GET", "/api/admin/users")
    check("5.1 consola sin PIN -> 401 (fail-closed)", code == 401, f"{code}")

    code, _ = admin.call("GET", "/api/admin/users", pin="pin-malo")
    check("5.2 consola con PIN equivocado -> 401", code == 401, f"{code}")

    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    shown = listing.get("users", []) if isinstance(listing, dict) else []
    check(
        "5.3 con PIN, la consola lista TODAS las cuentas con sus correos",
        code == 200 and len(shown) >= len(users),
        f"{code} n={len(shown)}",
    )
    if isinstance(listing, dict):
        print(
            f"       sin credencial: {listing.get('without_password')} · "
            f"correo sin verificar: {listing.get('unverified_email')} · "
            f"solicitudes pendientes: {listing.get('pending')}"
        )

    code, payload = admin.call(
        "POST", f"/api/admin/users/{a_id}/verify-email", pin=ADMIN_PIN
    )
    check(
        "5.4 el webmaster sella la verificación a mano (modo híbrido)",
        code == 200 and payload.get("email_verified") is True,
        f"{code} {detail_of(payload)}",
    )

    code, payload = admin.call(
        "POST", f"/api/admin/users/{a_id}/verify-email", pin=ADMIN_PIN
    )
    check(
        "5.5 sellarlo dos veces es idempotente (200, no un error)",
        code == 200 and payload.get("email_verified") is True,
        f"{code}",
    )

    code, _ = admin.call(
        "POST", f"/api/admin/users/{legacy['id']}/verify-email", pin=ADMIN_PIN
    )
    check(
        "5.5b sellar una cuenta SIN correo sí se rechaza (409)", code == 409, f"{code}"
    )

    code, _ = admin.call(
        "POST",
        f"/api/admin/users/{a_id}/purge",
        {"confirm_name": "E2E Ana"},
        pin=ADMIN_PIN,
    )
    check("5.6 purgar una cuenta ACTIVA se rechaza (409)", code == 409, f"{code}")

    code, payload = admin.call(
        "POST",
        f"/api/admin/users/{b_id}/unenroll",
        {"reason": "prueba forzada del webmaster"},
        pin=ADMIN_PIN,
    )
    check(
        "5.7 la baja forzada del webmaster funciona con motivo",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    # --- 6 · Baja autoservicio (no borra nada) ----------------------------
    code, c = c_client.call(
        "POST",
        "/api/users",
        {"name": "E2E Celes", "email": "e2e.celes@example.test", "password": PASSWORD},
    )
    c_id = c.get("id", "")
    code, _ = c_client.call(
        "POST", "/api/session", {"user_id": c_id, "password": PASSWORD}
    )
    check("6.1 tercer alta y sesión", code == 200, f"{code}")
    live_cookie = c_client.session_cookie()

    code, _ = c_client.call("POST", "/api/account/unenroll", {"password": "no-es-esta"})
    check("6.2 la baja autoservicio exige la contraseña", code == 401, f"{code}")

    code, payload = c_client.call(
        "POST", "/api/account/unenroll", {"password": PASSWORD}
    )
    check(
        "6.3 con la contraseña, la baja se hace (y no borra nada)",
        code == 200 and payload.get("unenrolled") is True,
        f"{code} {detail_of(payload)}",
    )

    code, payload = c_client.call("GET", "/api/session", cookie=live_cookie)
    check(
        "6.4 su sesión viva murió al instante (401 SESSION_STALE)",
        code == 401 and payload.get("detail") == "SESSION_STALE",
        f"{code}",
    )

    code, payload = anon.call(
        "POST", "/api/session", {"user_id": c_id, "password": PASSWORD}
    )
    check(
        "6.5 ya no puede volver a entrar: 403 ACCOUNT_UNENROLLED",
        code == 403 and payload.get("detail") == "ACCOUNT_UNENROLLED",
        f"{code}",
    )

    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    check(
        "6.6 la cuenta dada de baja SIGUE en la BD (no se ha borrado)",
        c_id in {u.get("id") for u in listing.get("users", [])},
    )
    check(
        "6.6b y desaparece del selector público (solo se listan cuentas activas)",
        c_id not in {u.get("id") for u in anon.call("GET", "/api/users")[1]},
    )

    code, payload = admin.call("GET", f"/api/admin/users/{c_id}/events", pin=ADMIN_PIN)
    actions = (
        [e.get("action") for e in payload.get("events", [])]
        if isinstance(payload, dict)
        else []
    )
    check(
        "6.7 el historial tiene la baja autoservicio",
        code == 200 and any("unenroll" in str(x) for x in actions),
        f"{actions}",
    )

    code, payload = admin.call(
        "POST", f"/api/admin/users/{c_id}/status", {"status": "active"}, pin=ADMIN_PIN
    )
    check(
        "6.8 el webmaster puede reactivarla",
        code == 200,
        f"{code} {detail_of(payload)}",
    )
    code, payload = anon.call(
        "POST", "/api/session", {"user_id": c_id, "password": PASSWORD}
    )
    check(
        "6.9 reactivada, vuelve a entrar con su contraseña",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    # --- 7 · Desactivar, y la purga con confirmación por nombre -----------
    code, payload = admin.call(
        "POST", f"/api/admin/users/{c_id}/status", {"status": "disabled"}, pin=ADMIN_PIN
    )
    check("7.1 desactivar desde la consola", code == 200, f"{code}")
    code, payload = anon.call(
        "POST", "/api/session", {"user_id": c_id, "password": PASSWORD}
    )
    check(
        "7.2 una cuenta desactivada no entra: 403 PROFILE_DISABLED",
        code == 403 and payload.get("detail") == "PROFILE_DISABLED",
        f"{code}",
    )

    code, _ = admin.call(
        "POST",
        f"/api/admin/users/{c_id}/purge",
        {"confirm_name": "otro-nombre"},
        pin=ADMIN_PIN,
    )
    check("7.3 purgar con el nombre equivocado -> 409", code == 409, f"{code}")

    code, before_purge = admin.call(
        "GET", f"/api/admin/users/{c_id}/events", pin=ADMIN_PIN
    )
    events_before = (
        before_purge.get("events", []) if isinstance(before_purge, dict) else []
    )
    actions_before = [e.get("action") for e in events_before]

    code, payload = admin.call(
        "POST",
        f"/api/admin/users/{c_id}/purge",
        {"confirm_name": "E2E Celes"},
        pin=ADMIN_PIN,
    )
    check(
        "7.4 con el nombre exacto, la purga se hace",
        code == 200,
        f"{code} {detail_of(payload)}",
    )
    purge_payload = payload if isinstance(payload, dict) else {}

    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    check(
        "7.5 la cuenta purgada ya no está en la consola",
        c_id not in {u.get("id") for u in listing.get("users", [])},
    )

    code, payload = admin.call("GET", f"/api/admin/users/{c_id}/events", pin=ADMIN_PIN)
    events_after = payload.get("events", []) if isinstance(payload, dict) else []
    actions_after = [e.get("action") for e in events_after]
    check(
        "7.6 el HISTORIAL sobrevive a la purga (y la purga queda registrada)",
        code == 200
        and len(events_after) == len(events_before) + 1
        and "purged" in actions_after
        and all(x in actions_after for x in actions_before),
        f"antes={actions_before} después={actions_after}",
    )
    check(
        "7.6b y la copia previa se escribió antes de borrar",
        bool(purge_payload.get("backup")),
        str(purge_payload.get("backup", "")),
    )
    # La garantía de privacidad de V3.81.x: el historial sobrevive para poder
    # explicar la purga, pero **sin** la PII que antes guardaba en sus notas.
    history_text = json.dumps(events_after, ensure_ascii=False)
    check(
        "7.6c el historial que sobrevive NO conserva ningún correo (PII)",
        "@" not in history_text,
        history_text[:160],
    )

    code, payload = admin.call(
        "POST",
        f"/api/admin/users/{b_id}/purge",
        {"confirm_name": "E2E Bea"},
        pin=ADMIN_PIN,
    )
    check(
        "7.7 también se purga una cuenta dada de baja",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    admin.call(
        "POST", f"/api/admin/users/{a_id}/status", {"status": "disabled"}, pin=ADMIN_PIN
    )
    code, payload = admin.call(
        "POST",
        f"/api/admin/users/{a_id}/purge",
        {"confirm_name": "E2E Ana"},
        pin=ADMIN_PIN,
    )
    check(
        "7.8 purgar una cuenta desactivada (tras desactivarla)",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    # --- 8 · La migración de una cuenta heredada, entera (V3.81.x) --------
    #
    # El escenario que el P0 dejó abierto: una cuenta anterior a V3.81 (sin
    # `password_hash`, entra nombrando) recorre el camino completo hasta
    # `without_password = 0` para esa cuenta, sin perder sus datos por el camino.
    if legacy is not None:
        legacy_id = legacy["id"]
        legacy_client = Client(base)

        code, payload = legacy_client.call(
            "POST", "/api/session", {"user_id": legacy_id}
        )
        check(
            "8.1 la cuenta heredada entra sin contraseña (compatibilidad declarada)",
            code == 200,
            f"{code} {detail_of(payload)}",
        )
        code, payload = legacy_client.call(
            "POST", "/api/session", {"user_id": legacy_id, "password": ""}
        )
        check(
            "8.2 y lo hace también con la contraseña vacía",
            code == 200,
            f"{code} {detail_of(payload)}",
        )
        code, payload = legacy_client.call("GET", "/api/vocabulary/lexicon")
        check(
            "8.3 antes de migrar, ve sus datos de siempre",
            code == 200 and isinstance(payload, dict),
            f"{code}",
        )

        _, listing_before = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
        sin_credencial_antes = (
            int(listing_before.get("without_password", 0))
            if isinstance(listing_before, dict)
            else 0
        )

        code, payload = admin.call(
            "POST",
            f"/api/admin/users/{legacy_id}/credentials",
            {"email": "heredada.migrada@example.test"},
            pin=ADMIN_PIN,
        )
        body = payload if isinstance(payload, dict) else {}
        temporary = str(body.get("temporary_password") or "")
        check(
            "8.4 la consola le asigna credenciales y devuelve una temporal legible",
            code == 200 and bool(temporary),
            f"{code} {detail_of(payload)}",
        )
        check(
            "8.5 la credencial nace temporal (must_change_password)",
            body.get("user", {}).get("must_change_password") is True,
            f"{body.get('user', {}).get('must_change_password')}",
        )

        _, listing_after = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
        sin_credencial_despues = (
            int(listing_after.get("without_password", 0))
            if isinstance(listing_after, dict)
            else 0
        )
        check(
            "8.6 el contador de cuentas sin contraseña baja exactamente en uno",
            sin_credencial_despues == sin_credencial_antes - 1,
            f"{sin_credencial_antes} -> {sin_credencial_despues}",
        )

        code, payload = legacy_client.call(
            "POST", "/api/session", {"user_id": legacy_id, "password": temporary}
        )
        check(
            "8.7 entra con la temporal", code == 200, f"{code} {detail_of(payload)}"
        )
        legacy_cookie = legacy_client.session_cookie()
        code, payload = legacy_client.call("GET", "/api/vocabulary/lexicon")
        check(
            "8.8 con la temporal puesta, el resto de la app está bloqueado",
            code == 403 and payload.get("detail") == "PASSWORD_CHANGE_REQUIRED",
            f"{code} {detail_of(payload)}",
        )
        code, payload = legacy_client.call("GET", "/api/session")
        check(
            "8.9 consultar la propia sesión sí está permitido (dice qué pedir)",
            code == 200 and payload.get("must_change_password") is True,
            f"{code}",
        )

        code, payload = legacy_client.call(
            "PUT",
            "/api/session/password",
            {"current_password": temporary, "new_password": PASSWORD2},
        )
        check(
            "8.10 el cambio obligatorio se completa",
            code == 200 and payload.get("must_change_password") is False,
            f"{code} {detail_of(payload)}",
        )

        code, payload = legacy_client.call("GET", "/api/session", cookie=legacy_cookie)
        check(
            "8.11 la cookie con la temporal deja de valer: 401 SESSION_STALE",
            code == 401 and payload.get("detail") == "SESSION_STALE",
            f"{code} {detail_of(payload)}",
        )

        migrado = Client(base)
        code, _ = migrado.call(
            "POST", "/api/session", {"user_id": legacy_id, "password": PASSWORD2}
        )
        check(
            "8.12 con la contraseña definitiva vuelve a entrar",
            code == 200,
            f"{code}",
        )
        code, _ = migrado.call(
            "POST", "/api/session", {"user_id": legacy_id, "password": temporary}
        )
        check("8.13 la temporal ya no abre", code == 401, f"{code}")
        code, payload = migrado.call("GET", "/api/vocabulary/lexicon")
        check(
            "8.14 y sus datos siguen intactos tras la migración",
            code == 200 and isinstance(payload, dict),
            f"{code}",
        )

        code, payload = admin.call(
            "GET", f"/api/admin/users/{legacy_id}/events", pin=ADMIN_PIN
        )
        events = payload.get("events", []) if isinstance(payload, dict) else []
        actions = [e.get("action") for e in events]
        check(
            "8.15 el historial de la migración queda registrado",
            code == 200 and "credentials" in actions,
            f"{actions}",
        )
        check(
            "8.16 y no guarda el correo en ninguna nota (PII fuera del historial)",
            "@" not in json.dumps(events, ensure_ascii=False),
            json.dumps(events, ensure_ascii=False)[:160],
        )

    # --- 9 · La evidencia de los demás sigue intacta ----------------------
    copy_after = counts(copy_db)
    print(f"\n# filas (copia, después): {copy_after}")
    check(
        "9.1 ninguna tabla de evidencia cambió de tamaño",
        all(copy_after[t] == copy_before[t] for t in TABLES if t != "users"),
        f"antes={copy_before} después={copy_after}",
    )
    check(
        "9.2 el censo de cuentas vuelve al de partida (las de prueba se purgaron)",
        copy_after["users"] == copy_before["users"],
        f"{copy_before['users']} -> {copy_after['users']}",
    )
    check(
        "9.3 el historial creció (es el único que debe crecer)",
        copy_after["user_events"] > copy_before["user_events"],
        f"{copy_before['user_events']} -> {copy_after['user_events']}",
    )
    check(
        "9.4 las cuentas que ya existían siguen siendo exactamente las mismas",
        identities(copy_db) == ids_before,
        f"{len(ids_before)} cuentas",
    )
    check(
        "9.5 la BD original no se ha tocado (mismo sha256 y mismos recuentos)",
        sha(db_path) == real_sha and counts(db_path) == real_before,
        f"sha={sha(db_path)[:16]}…",
    )

    server.should_exit = True
    time.sleep(1)
    print(f"\n# pasos: {steps} · fallos: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    if keep:
        print(f"# copia conservada en {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--port", type=int, default=8137)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if not args.db.is_file():
        print(f"No existe la BD de partida: {args.db}")
        return 2
    return run(args.db, args.port, args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
