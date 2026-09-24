# -*- coding: utf-8 -*-
"""Prueba end-to-end del **alta profesional de cuentas** (V3.82) sobre una copia.

Es la segunda capa de verificación de la release, la que las suites no pueden dar:
arranca el backend **de verdad** (`uvicorn`, en un hilo, en `127.0.0.1` y un puerto
local configurable —`--port`, por defecto 8138—) sobre una **copia** de
`data/tutor.db` y recorre por HTTP real el flujo entero del alta:

1. La **solicitud** trae nombre, email y avatar y queda en la cola del webmaster.
2. La **autorización** crea la cuenta con esos datos y emite una **invitación**.
   Sin SMTP, el enlace vuelve en la respuesta para entregarlo a mano.
3. La **activación**: la propia persona elige su contraseña desde el enlace.
4. La **entrada** es por email + contraseña. Sin contraseña no se entra
   (`403 ACCOUNT_NOT_ACTIVATED`): eso es el cierre de G0 **por construcción**.
5. La **recuperación** por correo, probada **con un servidor de correo de verdad**
   (uno mínimo, en `127.0.0.1`) y también **sin** él, para comprobar las dos
   mitades del modo híbrido: con SMTP el correo sale; sin SMTP no se abre red.
6. La **migración** de una cuenta heredada con `migrate_legacy_accounts.py`
   (simulacro y aplicación), que es la deuda que G0 vigila.
7. La **consola** que sigue en pie: verificación a mano, baja, reactivación,
   purga con copia previa e historial que sobrevive **sin PII**.

**Por qué existe.** `e2e_accounts_v381.py` recorría el alta autoservicio
(`POST /api/users`) y la entrada por `user_id`. Las dos cosas **ya no existen**:
aquel guion no puede pasar contra este producto, y su sitio es este. La copia de
partida no se toca nunca (se comprueba al final con `sha256` y con los recuentos).

Uso (desde la raíz del repositorio, con el intérprete del backend):

    backend\\.venv\\Scripts\\python.exe backend\\scripts\\e2e_accounts_v382.py

Opciones:

    --db RUTA     BD de partida (por defecto `backend/data/tutor.db`). **Se copia**;
                  el fichero indicado no se modifica nunca.
    --port N      puerto del backend efímero (por defecto 8138).
    --keep        no borra el directorio temporal (para mirar la copia a mano).

Devuelve 0 si todos los pasos pasan y 1 si alguno falla.
"""

from __future__ import annotations

import argparse
import email
import hashlib
import http.cookiejar
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BACKEND_DIR / "data" / "tutor.db"

ADMIN_PIN = "pin-de-prueba-e2e-382"
PASSWORD = "caballo-bateria-grapa"
PASSWORD2 = "bateria-caballo-grapa"
EMAIL = "e2e.solicitante@example.test"
NAME = "E2E Solicitante"
AVATAR_COLOR = "#7c3aed"
AVATAR_EMOJI = "🦉"

# Cuenta heredada que se **siembra** en la copia (no se depende de la BD de
# entrada): el escenario de G0 tiene que ser reproducible en cualquier copia, no
# saltarse «porque no había ninguna».
LEGACY_ID = "e2e-legacy-sin-credencial-382"
LEGACY_NAME = "E2E Heredada"
LEGACY_EMAIL = "e2e.heredada@example.test"

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
        out["user_events"] = con.execute(
            "SELECT COUNT(*) FROM user_events"
        ).fetchone()[0]
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
    """Siembra una cuenta heredada **sin email ni credencial** en la copia.

    Solo se escriben las columnas que existen en cualquier versión del esquema
    (`id`, `name`, `created_at`): el `init_db()` del backend, al arrancar, añade
    las demás con sus valores por defecto —`password_hash = ''` y `email = ''`
    entre ellas—, que es exactamente el estado de una cuenta anterior a V3.81.
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


def _failed_login(base: str, email_addr: str, password: str) -> tuple[int, str]:
    """Intento de entrada **a pelo**: permite leer el 429 y su cabecera."""
    req = urllib.request.Request(
        base + "/api/session",
        data=json.dumps({"email": email_addr, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code, exc.headers.get("Retry-After", "")


_TOKEN_RE = re.compile(r"[?&]token=([A-Za-z0-9_\-]+)")


def token_of(link: str) -> str:
    """El token en claro de un enlace de la app (`…#/cuenta/x?token=…`)."""
    match = _TOKEN_RE.search(link or "")
    return match.group(1) if match else ""


class MailBox:
    """Servidor SMTP mínimo que **captura** lo que se envía (V3.82).

    Existe para probar las dos mitades del modo híbrido sin depender de un
    proveedor de correo: **con** SMTP el correo sale de verdad y el enlace se
    puede leer; **sin** SMTP no se abre ni una conexión (y eso se ve aquí, en
    `connections`, porque este buzón es el único destino posible).

    Es un servidor SMTP de verdad —habla el protocolo— pero **no anuncia
    capacidades**, así que no ofrece STARTTLS ni autenticación. Es exactamente el
    caso que `services/mailer.py` declara tolerar («un servidor local de reenvío
    puede no ofrecer STARTTLS; no se aborta»), y el que permite probarlo en una
    máquina sin proveedor de correo.
    """

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.connections = 0
        self._stop = threading.Event()
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self._sock.settimeout(0.5)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            self.connections += 1
            threading.Thread(target=self._talk, args=(conn,), daemon=True).start()

    def _talk(self, conn: socket.socket) -> None:
        with conn:
            reader = conn.makefile("rb")

            def reply(text: str) -> None:
                conn.sendall(f"{text}\r\n".encode())

            reply("220 e2e.local ESMTP")
            in_data = False
            body: list[str] = []
            while True:
                raw = reader.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if in_data:
                    if line == ".":
                        in_data = False
                        self.messages.append("\n".join(body))
                        body = []
                        reply("250 OK: mensaje aceptado")
                    else:
                        body.append(line)
                    continue
                verb = line.split(" ", 1)[0].upper()
                if verb in ("EHLO", "HELO"):
                    # Respuesta de una sola línea: sin extensiones anunciadas.
                    reply("250 e2e.local")
                elif verb in ("MAIL", "RCPT"):
                    reply("250 OK")
                elif verb == "DATA":
                    in_data = True
                    reply("354 Escribe el mensaje; termina con una línea con un punto")
                elif verb == "QUIT":
                    reply("221 Adiós")
                    return
                else:
                    reply("250 OK")

    def token_of_last_mail(self, route: str) -> str:
        """El token del último correo capturado que traiga un enlace de `route`.

        Se decodifica el mensaje con la librería estándar en vez de buscar el
        texto a pelo: el cuerpo lleva acentos («contraseña»), así que puede venir
        codificado, y un `regex` sobre el mensaje crudo dependería de cómo lo
        codifique el emisor. `get_payload(decode=True)` lo deshace.
        """
        pattern = re.compile(rf"cuenta/{route}\?token=([A-Za-z0-9_\-]+)")
        for raw in reversed(self.messages):
            msg = email.message_from_string(raw)
            text = (msg.get_payload(decode=True) or b"").decode("utf-8", "replace")
            match = pattern.search(text)
            if match:
                return match.group(1)
        return ""


def run(db_path: Path, port: int, keep: bool) -> int:
    base = f"http://127.0.0.1:{port}"
    tmp = Path(tempfile.mkdtemp(prefix="et-e2e-v382-"))
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
    # El buzón se levanta **antes** de configurar nada: sin SMTP configurado, su
    # contador de conexiones tiene que quedarse a cero.
    mailbox = MailBox()
    mailbox.start()

    import config  # noqa: E402

    # Redirección del almacén **antes** de importar la app: los módulos que hacen
    # `from config import DATA_DIR` fijan el valor al importarse.
    config.DATA_DIR = data
    config.CERTS_DIR = data / "certs"
    config.TLS_CERT_PATH = data / "certs" / "cert.pem"
    config.TLS_KEY_PATH = data / "certs" / "key.pem"

    import uvicorn  # noqa: E402

    import main  # noqa: E402
    from security import _clients  # noqa: E402

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
        mailbox.stop()
        return 2
    print(f"# backend efímero escuchando en {base}\n")

    anon = Client(base)
    solicitante = Client(base)
    otro = Client(base)
    admin = Client(base)

    def limpiar_cupo() -> None:
        """Vacía la ventana del cupo por IP del backend efímero.

        Este guion ejerce **flujos**, no el freno: cuando necesita más peticiones
        de las que caben en un minuto (la cola de solicitudes tiene un cupo de 5),
        borra las marcas en memoria —que es lo mismo que habría pasado esperando—
        en vez de dormir el guion entero. El cupo se comprueba aparte y a
        propósito en 5.4d.
        """
        _clients.clear()

    # --- 0 · La puerta: lo que ya no se puede hacer sin sesión -------------
    code, _ = anon.call("GET", "/api/users")
    check(
        "0.1 GET /api/users ya NO enumera cuentas sin sesión (401)",
        code == 401,
        f"{code}",
    )

    code, payload = anon.call("POST", "/api/users", {"name": "Intrusa"})
    check(
        "0.2 el alta pública POST /api/users ya no existe (405)",
        code == 405,
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call("POST", "/api/session", {"user_id": LEGACY_ID})
    check(
        "0.3 entrar «nombrando» ya no es un contrato válido (422)",
        code == 422,
        f"{code} {detail_of(payload)}",
    )

    # --- 1 · La solicitud: nombre, email y avatar (Fase A) ----------------
    code, pedida = solicitante.call(
        "POST",
        "/api/profile-requests",
        {
            "display_name": NAME,
            "email": EMAIL.upper(),
            "avatar_color": AVATAR_COLOR,
            "avatar_emoji": AVATAR_EMOJI,
            "note": "quiero practicar inglés",
        },
    )
    check(
        "1.1 la solicitud se registra con nombre, email y avatar (201)",
        code == 201
        and isinstance(pedida, dict)
        and pedida.get("display_name") == NAME
        and pedida.get("status") == "pending",
        f"{code} {detail_of(pedida)}",
    )
    check(
        "1.2 el email se normaliza a minúsculas al guardarlo",
        isinstance(pedida, dict) and pedida.get("email") == EMAIL,
        f"{pedida.get('email') if isinstance(pedida, dict) else pedida}",
    )
    check(
        "1.3 el avatar pedido viaja con la solicitud",
        isinstance(pedida, dict)
        and pedida.get("avatar_color") == AVATAR_COLOR
        and pedida.get("avatar_emoji") == AVATAR_EMOJI,
        f"{pedida.get('avatar_color') if isinstance(pedida, dict) else pedida}",
    )
    request_id = pedida.get("id", 0) if isinstance(pedida, dict) else 0

    code, payload = solicitante.call(
        "POST", "/api/profile-requests", {"display_name": NAME, "email": EMAIL}
    )
    check(
        "1.4 pedir dos veces lo mismo -> 409 (la cola no es un sumidero)",
        code == 409,
        f"{code} {detail_of(payload)}",
    )

    code, payload = solicitante.call(
        "POST",
        "/api/profile-requests",
        {"display_name": "E2E Otra", "email": "no-es-un-email"},
    )
    check(
        "1.5 un email sin forma -> 422 EMAIL_FORMAT (y no culpa al nombre)",
        code == 422 and payload.get("detail") == "EMAIL_FORMAT",
        f"{code} {detail_of(payload)}",
    )

    code, payload = solicitante.call(
        "POST",
        "/api/profile-requests",
        {"display_name": "E2E Terceira", "email": EMAIL},
    )
    check(
        "1.6 el mismo email con otro nombre -> 409 (una solicitud por correo)",
        code == 409,
        f"{code} {detail_of(payload)}",
    )

    limpiar_cupo()

    code, _ = anon.call("GET", "/api/admin/profile-requests")
    check("1.7 la cola del webmaster sin PIN -> 401", code == 401, f"{code}")

    code, cola = admin.call("GET", "/api/admin/profile-requests", pin=ADMIN_PIN)
    pendientes = cola.get("requests", []) if isinstance(cola, dict) else []
    check(
        "1.8 con PIN, la solicitud está en la cola con su email y su avatar",
        code == 200
        and any(
            r.get("id") == request_id and r.get("email") == EMAIL for r in pendientes
        ),
        f"{code} n={len(pendientes)}",
    )

    # --- 2 · La autorización: crear la cuenta e invitar (Fase B) ----------
    code, _ = anon.call(
        "POST", f"/api/admin/profile-requests/{request_id}/approve", {"note": ""}
    )
    check("2.1 aprobar sin PIN -> 401 (fail-closed)", code == 401, f"{code}")

    code, aprobada = admin.call(
        "POST",
        f"/api/admin/profile-requests/{request_id}/approve",
        {"note": "autorizada"},
        pin=ADMIN_PIN,
    )
    cuerpo = aprobada if isinstance(aprobada, dict) else {}
    user = cuerpo.get("user") or {}
    link1 = str(cuerpo.get("activation_link") or "")
    check(
        "2.2 aprobar crea la cuenta y devuelve la invitación",
        code == 200 and bool(user.get("id")) and bool(link1),
        f"{code} {detail_of(aprobada)}",
    )
    check(
        "2.3 sin SMTP configurado el correo NO sale… y se dice",
        cuerpo.get("email_sent") is False,
        f"email_sent={cuerpo.get('email_sent')}",
    )
    check(
        "2.4 el enlace de invitación apunta a la ruta de la app",
        link1.endswith("?") is False and "/#/cuenta/activar?token=" in link1,
        link1,
    )
    check(
        "2.5 la cuenta nace con el email y el avatar que se pidieron",
        user.get("email") == EMAIL
        and user.get("avatar_color") == AVATAR_COLOR
        and user.get("avatar_emoji") == AVATAR_EMOJI,
        f"{user.get('email')} · {user.get('avatar_color')}",
    )
    check(
        "2.6 y nace SIN contraseña: es una invitación pendiente, no una cuenta",
        user.get("has_password") is False,
        f"has_password={user.get('has_password')}",
    )
    user_id = str(user.get("id") or "")

    code, _ = admin.call(
        "POST",
        f"/api/admin/profile-requests/{request_id}/approve",
        {"note": ""},
        pin=ADMIN_PIN,
    )
    check(
        "2.7 aprobar dos veces -> 409 (no se crean dos cuentas)",
        code == 409,
        f"{code}",
    )

    code, reemitida = admin.call(
        "POST", f"/api/admin/users/{user_id}/resend-activation", pin=ADMIN_PIN
    )
    link2 = str((reemitida or {}).get("activation_link") or "")
    check(
        "2.8 reenviar la invitación emite un token NUEVO",
        code == 200 and bool(link2) and token_of(link2) != token_of(link1),
        f"{code} n={len(link2)}",
    )
    check(
        "2.9 sin email no hay a quién invitar (409)",
        admin.call(
            "POST", f"/api/admin/users/{LEGACY_ID}/resend-activation", pin=ADMIN_PIN
        )[0]
        == 409,
        "cuenta heredada sin email",
    )

    limpiar_cupo()
    code, payload = anon.call(
        "POST",
        "/api/profile-requests",
        {"display_name": "E2E Tarde", "email": EMAIL},
    )
    check(
        "2.10 pedir el alta con un email que YA tiene cuenta -> 409 EMAIL_TAKEN",
        code == 409 and payload.get("detail") == "EMAIL_TAKEN",
        f"{code} {detail_of(payload)}",
    )

    # --- 3 · La activación: la persona elige su contraseña (Fase C) -------
    code, payload = anon.call(
        "POST", "/api/account/activate", {"token": "x" * 43, "password": PASSWORD}
    )
    check(
        "3.1 un token inventado -> 400 ACTIVATION_TOKEN_INVALID",
        code == 400 and payload.get("detail") == "ACTIVATION_TOKEN_INVALID",
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call(
        "POST", "/api/account/activate", {"token": token_of(link2), "password": "corta"}
    )
    check(
        "3.2 una contraseña que no cumple la política -> 400 PASSWORD_FORMAT",
        code == 400 and payload.get("detail") == "PASSWORD_FORMAT",
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call(
        "POST",
        "/api/account/activate",
        {"token": token_of(link1), "password": PASSWORD},
    )
    check(
        "3.3 el token reemitido invalida el anterior (400)",
        code == 400,
        f"{code} {detail_of(payload)}",
    )

    activado = Client(base)
    code, payload = activado.call(
        "POST",
        "/api/account/activate",
        {"token": token_of(link2), "password": PASSWORD},
    )
    check(
        "3.4 con la invitación vigente, la cuenta queda activada",
        code == 200
        and payload.get("has_password") is True
        and payload.get("email_verified") is True,
        f"{code} {detail_of(payload)}",
    )
    check(
        "3.5 pulsar el enlace deja la sesión abierta (no hay que teclear dos veces)",
        activado.session_cookie().startswith("et_session="),
        activado.session_cookie()[:22],
    )

    code, payload = anon.call(
        "POST",
        "/api/account/activate",
        {"token": token_of(link2), "password": PASSWORD2},
    )
    check(
        "3.6 el token es de un solo uso -> 400 al repetirlo",
        code == 400,
        f"{code} {detail_of(payload)}",
    )

    # --- 4 · La entrada: email + contraseña (Fase D) ----------------------
    code, payload = solicitante.call(
        "POST", "/api/session", {"email": EMAIL.upper(), "password": PASSWORD}
    )
    check(
        "4.1 se entra con el email (sin distinguir mayúsculas) y la contraseña",
        code == 200 and payload.get("id") == user_id,
        f"{code} {detail_of(payload)}",
    )
    cookie_viva = solicitante.session_cookie()
    check(
        "4.2 la identidad viaja en la cookie firmada",
        cookie_viva.startswith("et_session="),
        cookie_viva[:22],
    )

    code, mala = anon.call(
        "POST", "/api/session", {"email": EMAIL, "password": "no-es-esta-clave"}
    )
    check(
        "4.3 la contraseña equivocada -> 401 INVALID_CREDENTIALS",
        code == 401 and mala.get("detail") == "INVALID_CREDENTIALS",
        f"{code} {detail_of(mala)}",
    )

    code, sin_cuenta = anon.call(
        "POST", "/api/session", {"email": "nadie@example.test", "password": PASSWORD}
    )
    check(
        "4.4 un email sin cuenta responde EXACTAMENTE lo mismo (no hay oráculo)",
        code == 401 and sin_cuenta == mala,
        f"{code} {detail_of(sin_cuenta)}",
    )

    statuses = []
    for _ in range(5):
        status, _ = _failed_login(base, EMAIL, "no-es-esta-clave")
        statuses.append(status)
    check(
        "4.5 los fallos de dedos torpes no frenan nada (holgura declarada)",
        statuses == [401] * 5,
        f"{statuses}",
    )

    code, retry_after = _failed_login(base, EMAIL, PASSWORD)
    check(
        "4.6 el 6º fallo ya frena: la contraseña correcta tampoco entra",
        code == 429 and bool(retry_after),
        f"{code} Retry-After={retry_after}",
    )

    time.sleep(1.5)  # el primer retardo del freno es de un segundo
    code, payload = otro.call(
        "POST", "/api/session", {"email": EMAIL, "password": PASSWORD}
    )
    check(
        "4.7 pasado el retardo, vuelve a entrar (y el freno se limpia)",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    # --- 5 · La recuperación por correo (Fase E) --------------------------
    #
    # Las dos mitades del modo híbrido, medidas: **sin** SMTP el enlace no sale
    # por ningún lado —y no se abre ni una conexión—, y **con** SMTP el correo
    # sale de verdad, que es lo único que permite recorrer el canje del token
    # entero. El buzón es el único destino posible, así que su contador de
    # conexiones es la prueba de que no se tocó la red.
    conexiones_antes = mailbox.connections
    code, sin_smtp = anon.call("POST", "/api/account/forgot-password", {"email": EMAIL})
    check(
        "5.1 sin SMTP, «olvidé mi contraseña» responde 200",
        code == 200 and sin_smtp == {"sent": True},
        f"{code} {sin_smtp}",
    )
    check(
        "5.2 y NO se abre ninguna conexión de red: el modo híbrido es fail-closed",
        mailbox.connections == conexiones_antes,
        f"conexiones={mailbox.connections}",
    )

    code, desconocido = anon.call(
        "POST", "/api/account/forgot-password", {"email": "nadie@example.test"}
    )
    check(
        "5.3 el cuerpo es idéntico exista o no la cuenta (no hay oráculo de correos)",
        code == 200 and desconocido == sin_smtp,
        f"{code} {desconocido}",
    )

    os.environ[config.SMTP_HOST_ENV] = "127.0.0.1"
    os.environ[config.SMTP_PORT_ENV] = str(mailbox.port)
    os.environ[config.SMTP_FROM_ENV] = "english-tutor@e2e.test"

    code, payload = anon.call(
        "POST", "/api/account/forgot-password", {"email": "nadie@example.test"}
    )
    check(
        "5.4 ya con SMTP, un correo SIN cuenta responde lo mismo y no manda nada",
        code == 200 and payload == sin_smtp and not mailbox.messages,
        f"{code} mensajes={len(mailbox.messages)}",
    )

    code, payload = anon.call("POST", "/api/account/forgot-password", {"email": EMAIL})
    check(
        "5.5 con SMTP, el correo de restablecimiento SALE (y se captura aquí)",
        code == 200 and len(mailbox.messages) == 1,
        f"{code} mensajes={len(mailbox.messages)}",
    )
    check(
        "5.6 y trae el enlace de la app (…/#/cuenta/restablecer?token=…)",
        bool(mailbox.token_of_last_mail("restablecer")),
        "token capturado" if mailbox.messages else "sin correo",
    )

    # 5.7 · El cupo de la ruta que manda correo. Se agota a propósito: mientras
    # haya cuentas que puedan recibir un enlace, esta es la ruta más abusable de
    # la API (un 429 aquí no molesta a quien la usa una vez al año), y es la
    # primera valla antes de que un tercero use la app de lanzadera de correo.
    limpiar_cupo()
    cupo = [
        anon.call("POST", "/api/account/forgot-password", {"email": EMAIL})[0]
        for _ in range(6)
    ]
    check(
        "5.7 el cupo corta el 6º intento por minuto (429)",
        cupo == [200] * 5 + [429],
        f"{cupo}",
    )
    # Cada emisión **sustituye** el token anterior (solo vale el último), así que
    # el enlace se lee del correo más reciente: el que se acaba de emitir.
    limpiar_cupo()
    anon.call("POST", "/api/account/forgot-password", {"email": EMAIL})
    reset_token = mailbox.token_of_last_mail("restablecer")
    check(
        "5.8 el enlace vigente es el del último correo emitido",
        bool(reset_token),
        f"token={'sí' if reset_token else 'no'}",
    )

    code, payload = anon.call(
        "POST",
        "/api/account/reset-password",
        {"token": "x" * 43, "password": PASSWORD2},
    )
    check(
        "5.9 un token de restablecimiento inventado -> 400",
        code == 400 and payload.get("detail") == "RESET_TOKEN_INVALID",
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call(
        "POST",
        "/api/account/reset-password",
        {"token": reset_token, "password": "corta"},
    )
    check(
        "5.10 una contraseña que no cumple la política -> 400 PASSWORD_FORMAT",
        code == 400 and payload.get("detail") == "PASSWORD_FORMAT",
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call(
        "POST",
        "/api/account/reset-password",
        {"token": reset_token, "password": PASSWORD2},
    )
    check(
        "5.11 con el token del correo, la contraseña se restablece (200)",
        code == 200 and payload.get("has_password") is True,
        f"{code} {detail_of(payload)}",
    )

    code, payload = solicitante.call("GET", "/api/session", cookie=cookie_viva)
    check(
        "5.12 y la sesión que estaba abierta muere al instante (401 SESSION_STALE)",
        code == 401 and payload.get("detail") == "SESSION_STALE",
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call(
        "POST",
        "/api/account/reset-password",
        {"token": reset_token, "password": PASSWORD},
    )
    check(
        "5.13 el token de restablecimiento es de un solo uso (400)",
        code == 400,
        f"{code} {detail_of(payload)}",
    )

    code, _ = anon.call("POST", "/api/session", {"email": EMAIL, "password": PASSWORD})
    check("5.14 la contraseña vieja ya no abre", code == 401, f"{code}")

    code, payload = otro.call(
        "POST", "/api/session", {"email": EMAIL, "password": PASSWORD2}
    )
    check(
        "5.15 y con la nueva vuelve a entrar",
        code == 200,
        f"{code} {detail_of(payload)}",
    )

    # --- 6 · La migración de la cuenta heredada (Fase F) ------------------
    #
    # Es la deuda que G0 vigila: una cuenta anterior a V3.81 (sin email y sin
    # contraseña) se queda fuera de la app desde V3.82, así que hay que llevarla
    # al flujo nuevo **sin inventarle una contraseña a nadie**. Lo hace el guion
    # de migración, y aquí se ejerce tal cual: se ejecuta como proceso aparte
    # contra la copia y se recorre el enlace que imprime.
    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    sin_credencial_antes = (
        int(listing.get("without_password", 0)) if isinstance(listing, dict) else 0
    )
    heredada = next(
        (
            u
            for u in listing.get("users", [])
            if u.get("id") == LEGACY_ID
        ),
        {},
    )
    check(
        "6.1 la cuenta heredada sembrada sigue sin email y sin contraseña",
        heredada.get("email") in ("", None) and heredada.get("has_password") is False,
        f"email={heredada.get('email')!r} has_password={heredada.get('has_password')}",
    )
    check(
        "6.2 y está en el contador de «pendientes de activación» del webmaster",
        sin_credencial_antes >= 1,
        f"pendientes={sin_credencial_antes}",
    )

    script = Path(__file__).resolve().with_name("migrate_legacy_accounts.py")
    common = [sys.executable, str(script), "--db", str(copy_db), "--base-url", base]
    sub_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    simulacro = subprocess.run(
        [*common, "--set", f"{LEGACY_NAME}={LEGACY_EMAIL}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=sub_env,
        timeout=120,
        check=False,
    )
    check(
        "6.3 el simulacro (sin --apply) dice lo que haría y no escribe nada",
        simulacro.returncode == 0
        and "SIMULACRO" in simulacro.stdout
        and LEGACY_EMAIL in simulacro.stdout
        and "cuenta(s) se migrarían" in simulacro.stdout,
        simulacro.stdout.strip().splitlines()[-1] if simulacro.stdout else "sin salida",
    )
    _, sin_email_todavia = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    sigue = next(
        (u for u in sin_email_todavia.get("users", []) if u.get("id") == LEGACY_ID),
        {},
    )
    check(
        "6.4 tras el simulacro, la cuenta sigue exactamente igual",
        sigue.get("email") in ("", None) and sigue.get("has_password") is False,
        f"email={sigue.get('email')!r}",
    )

    aplicado = subprocess.run(
        [*common, "--apply", "--set", f"{LEGACY_NAME}={LEGACY_EMAIL}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=sub_env,
        timeout=180,
        check=False,
    )
    check(
        "6.5 con --apply, la migración asigna el email y emite la invitación",
        aplicado.returncode == 0
        and "invitación emitida" in aplicado.stdout
        and "copia de seguridad" in aplicado.stdout,
        aplicado.stdout.strip().splitlines()[-1] if aplicado.stdout else "sin salida",
    )
    link_heredada = ""
    for line in aplicado.stdout.splitlines():
        if "/#/cuenta/activar?token=" in line:
            link_heredada = line.strip()
            break
    token_heredada = token_of(link_heredada)
    check(
        "6.6 el guion imprime el enlace para entregarlo a mano (modo híbrido)",
        bool(token_heredada),
        link_heredada or "sin enlace",
    )

    code, payload = anon.call(
        "POST", "/api/session", {"email": LEGACY_EMAIL, "password": PASSWORD}
    )
    check(
        "6.7 antes de activar, la migrada NO entra: el agujero de G0 está cerrado",
        code == 403 and payload.get("detail") == "ACCOUNT_NOT_ACTIVATED",
        f"{code} {detail_of(payload)}",
    )

    code, payload = anon.call(
        "POST",
        "/api/account/activate",
        {"token": token_heredada, "password": PASSWORD},
    )
    check(
        "6.8 con el enlace de la migración, elige su contraseña",
        code == 200 and payload.get("email_verified") is True,
        f"{code} {detail_of(payload)}",
    )

    migrada = Client(base)
    code, payload = migrada.call(
        "POST", "/api/session", {"email": LEGACY_EMAIL, "password": PASSWORD}
    )
    check(
        "6.9 y entra con su propio email y su contraseña (no la de nadie)",
        code == 200 and payload.get("id") == LEGACY_ID,
        f"{code} {detail_of(payload)}",
    )
    code, lexicon = migrada.call("GET", "/api/vocabulary/lexicon")
    check(
        "6.10 sus datos siguen intactos tras la migración",
        code == 200 and isinstance(lexicon, dict),
        f"{code}",
    )

    _, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    sin_credencial_despues = (
        int(listing.get("without_password", 0)) if isinstance(listing, dict) else 0
    )
    check(
        "6.11 el contador de «pendientes de activación» baja exactamente en uno",
        sin_credencial_despues == sin_credencial_antes - 1,
        f"{sin_credencial_antes} -> {sin_credencial_despues}",
    )

    code, listado = otro.call("GET", "/api/users")
    correos = [u.get("email") for u in listado if isinstance(u, dict)]
    check(
        "6.12 con sesión, la lista de cuentas tapa el email de las demás",
        code == 200
        and EMAIL in correos
        and all(e == "" for e in correos if e not in ("", EMAIL)),
        f"{correos}",
    )

    # --- 7 · La consola de gestión y la purga -----------------------------
    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    check(
        "7.1 la consola con PIN lista todas las cuentas y sus contadores",
        code == 200 and isinstance(listing, dict),
        f"{code}",
    )

    code, payload = admin.call(
        "POST", f"/api/admin/users/{user_id}/verify-email", pin=ADMIN_PIN
    )
    primero = code
    code, payload = admin.call(
        "POST", f"/api/admin/users/{user_id}/verify-email", pin=ADMIN_PIN
    )
    check(
        "7.2 sellar la verificación a mano es idempotente (200 y 200)",
        primero == 200 and code == 200 and payload.get("email_verified") is True,
        f"{primero} {code}",
    )

    code, _ = otro.call("POST", "/api/account/unenroll", {"password": "no-es-esta"})
    check("7.3 la baja autoservicio exige la contraseña (401)", code == 401, f"{code}")

    vivo = otro.session_cookie()
    code, payload = otro.call("POST", "/api/account/unenroll", {"password": PASSWORD2})
    check(
        "7.4 con la contraseña, la baja se hace y no borra nada",
        code == 200 and payload.get("unenrolled") is True,
        f"{code} {detail_of(payload)}",
    )

    code, payload = otro.call("GET", "/api/session", cookie=vivo)
    check(
        "7.5 su sesión viva murió al instante (401 SESSION_STALE)",
        code == 401 and payload.get("detail") == "SESSION_STALE",
        f"{code}",
    )

    code, payload = anon.call(
        "POST", "/api/session", {"email": EMAIL, "password": PASSWORD2}
    )
    check(
        "7.6 dada de baja, ya no entra: 403 ACCOUNT_UNENROLLED",
        code == 403 and payload.get("detail") == "ACCOUNT_UNENROLLED",
        f"{code}",
    )

    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    check(
        "7.7 la cuenta dada de baja SIGUE en la BD (no se ha borrado)",
        user_id in {u.get("id") for u in listing.get("users", [])},
    )

    code, payload = admin.call(
        "POST",
        f"/api/admin/users/{user_id}/status",
        {"status": "active"},
        pin=ADMIN_PIN,
    )
    check("7.8 el webmaster puede reactivarla", code == 200, f"{code}")
    code, _ = anon.call("POST", "/api/session", {"email": EMAIL, "password": PASSWORD2})
    check("7.9 reactivada, vuelve a entrar con su contraseña", code == 200, f"{code}")

    code, _ = admin.call(
        "POST",
        f"/api/admin/users/{user_id}/status",
        {"status": "disabled"},
        pin=ADMIN_PIN,
    )
    check("7.10 desactivar desde la consola", code == 200, f"{code}")
    code, payload = anon.call(
        "POST", "/api/session", {"email": EMAIL, "password": PASSWORD2}
    )
    check(
        "7.11 una cuenta desactivada no entra: 403 PROFILE_DISABLED",
        code == 403 and payload.get("detail") == "PROFILE_DISABLED",
        f"{code}",
    )

    code, _ = admin.call(
        "POST",
        f"/api/admin/users/{user_id}/purge",
        {"confirm_name": "otro-nombre"},
        pin=ADMIN_PIN,
    )
    check("7.12 purgar con el nombre equivocado -> 409", code == 409, f"{code}")

    code, before_purge = admin.call(
        "GET", f"/api/admin/users/{user_id}/events", pin=ADMIN_PIN
    )
    events_before = (
        before_purge.get("events", []) if isinstance(before_purge, dict) else []
    )
    actions_before = [e.get("action") for e in events_before]

    code, payload = admin.call(
        "POST",
        f"/api/admin/users/{user_id}/purge",
        {"confirm_name": NAME},
        pin=ADMIN_PIN,
    )
    check(
        "7.13 con el nombre exacto, la purga se hace",
        code == 200,
        f"{code} {detail_of(payload)}",
    )
    purge_payload = payload if isinstance(payload, dict) else {}
    check(
        "7.14 la copia previa se escribió antes de borrar",
        bool(purge_payload.get("backup")),
        str(purge_payload.get("backup", "")),
    )

    code, listing = admin.call("GET", "/api/admin/users", pin=ADMIN_PIN)
    check(
        "7.15 la cuenta purgada ya no está en la consola",
        user_id not in {u.get("id") for u in listing.get("users", [])},
    )

    code, payload = admin.call(
        "GET", f"/api/admin/users/{user_id}/events", pin=ADMIN_PIN
    )
    events_after = payload.get("events", []) if isinstance(payload, dict) else []
    actions_after = [e.get("action") for e in events_after]
    check(
        "7.16 el HISTORIAL sobrevive a la purga (y la purga queda registrada)",
        code == 200
        and len(events_after) == len(events_before) + 1
        and "purged" in actions_after
        and all(x in actions_after for x in actions_before),
        f"antes={actions_before} después={actions_after}",
    )
    history_text = json.dumps(events_after, ensure_ascii=False)
    check(
        "7.17 y NO conserva ningún correo: «borrar toda la evidencia» sigue cierto",
        "@" not in history_text,
        history_text[:160],
    )

    mailbox.stop()

    # --- 8 · La evidencia de los demás sigue intacta ---------------------
    copy_after = counts(copy_db)
    print(f"\n# filas (copia, después): {copy_after}")
    check(
        "8.1 ninguna tabla de evidencia cambió de tamaño",
        all(copy_after[t] == copy_before[t] for t in TABLES if t != "users"),
        f"antes={copy_before} después={copy_after}",
    )
    check(
        "8.2 el censo de cuentas vuelve al de partida (la de prueba se purgó)",
        copy_after["users"] == copy_before["users"],
        f"{copy_before['users']} -> {copy_after['users']}",
    )
    check(
        "8.3 el historial creció (es el único que debe crecer)",
        copy_after["user_events"] > copy_before["user_events"],
        f"{copy_before['user_events']} -> {copy_after['user_events']}",
    )
    check(
        "8.4 las cuentas que ya existían siguen siendo exactamente las mismas",
        identities(copy_db) == ids_before,
        f"{len(ids_before)} cuentas",
    )
    check(
        "8.5 la BD original no se ha tocado (mismo sha256 y mismos recuentos)",
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
    parser.add_argument("--port", type=int, default=8138)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if not args.db.is_file():
        print(f"No existe la BD de partida: {args.db}")
        return 2
    return run(args.db, args.port, args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
