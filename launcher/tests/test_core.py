"""Tests del núcleo puro del launcher (launcher/core.py)."""
from core import (
    AUTHOR_EMAIL,
    AUTHOR_NAME,
    BACKEND_DIR,
    BACKEND_PORT,
    FRONTEND_DIR,
    FRONTEND_DIST,
    FRONTEND_PORT,
    ICON_PATH,
    LAN_ENV,
    REPO_ROOT,
    TLS_CERT_PATH,
    TLS_KEY_PATH,
    app_summary,
    author_line,
    backend_command,
    backend_python,
    backend_url,
    db_summary,
    ensure_cert_command,
    frontend_build_command,
    frontend_dev_command,
    frontend_dist_available,
    frontend_url,
    health_status,
    icon_file,
    lan_url,
    local_url,
    mdns_available,
    user_overview,
)


def test_author_line():
    assert AUTHOR_NAME and AUTHOR_EMAIL
    assert author_line() == f"{AUTHOR_NAME} · {AUTHOR_EMAIL}"


def test_icon_file_points_to_launcher_icon():
    assert ICON_PATH.name == "icon.ico"
    assert icon_file().endswith("icon.ico")


def test_repo_root_contains_backend_and_frontend():
    assert BACKEND_DIR.name == "backend"
    assert FRONTEND_DIR.name == "frontend"
    assert REPO_ROOT == BACKEND_DIR.parent


def test_backend_command_uses_venv_python():
    cmd = backend_command()
    assert cmd[0].endswith("python.exe") or cmd[0].endswith("python")
    assert cmd[0] == str(backend_python())
    assert "-m" in cmd
    assert "uvicorn" in cmd
    assert "main:app" in cmd
    assert str(BACKEND_PORT) in cmd


def test_backend_command_binds_loopback_by_default(monkeypatch):
    """V3.73.x: sin modo LAN declarado, la API **no** se expone en la red.

    Antes se enlazaba siempre a `0.0.0.0`: exponerse a la LAN era el
    comportamiento por defecto sin que nadie lo hubiera pedido, y con la
    identidad viajando en la URL (P0 abierto) eso dejaba los datos del alumno al
    alcance de cualquier equipo de la red.
    """
    monkeypatch.delenv(LAN_ENV, raising=False)
    cmd = backend_command()

    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "0.0.0.0" not in cmd


def test_backend_command_binds_lan_when_declared(monkeypatch):
    monkeypatch.setenv(LAN_ENV, "1")
    cmd = backend_command()

    assert cmd[cmd.index("--host") + 1] == "0.0.0.0"


def test_backend_command_keeps_https_in_both_modes(monkeypatch):
    """El TLS no depende del modo: en `localhost` también hace falta el micrófono."""
    for valor in ("1", "0"):
        monkeypatch.setenv(LAN_ENV, valor)
        cmd = backend_command()
        assert "--ssl-certfile" in cmd
        assert cmd[cmd.index("--ssl-certfile") + 1] == str(TLS_CERT_PATH)
        assert cmd[cmd.index("--ssl-keyfile") + 1] == str(TLS_KEY_PATH)


def test_backend_command_serves_https_with_the_local_certificate():
    """Sin *secure context* se rompe el micrófono desde otro equipo (V3.72)."""
    cmd = backend_command()

    assert cmd[cmd.index("--ssl-certfile") + 1] == str(TLS_CERT_PATH)
    assert cmd[cmd.index("--ssl-keyfile") + 1] == str(TLS_KEY_PATH)
    assert TLS_CERT_PATH.name == "cert.pem" and TLS_KEY_PATH.name == "key.pem"
    # Artefacto de máquina: dentro de backend/data/ (ignorado por git).
    assert TLS_CERT_PATH.parent == BACKEND_DIR / "data" / "certs"


def test_ensure_cert_command_is_idempotent_script_of_the_backend():
    cmd = ensure_cert_command()
    assert cmd[0] == str(backend_python())
    assert cmd[-2:] == ["-m", "scripts.ensure_tls_cert"]


def test_frontend_build_command_compila_la_ui():
    """Node deja de ser requisito de EJECUCIÓN: solo compila el artefacto."""
    cmd = frontend_build_command()
    assert "run" in cmd
    assert cmd[-1] == "build"


def test_frontend_dev_command_sigue_siendo_el_modo_desarrollo():
    cmd = frontend_dev_command()
    assert "run" in cmd
    assert cmd[-1] == "dev"


def test_frontera_de_runtime_un_solo_origen():
    """V3.72 (RC-01): la UI y la API comparten origen; Node no es runtime."""
    assert BACKEND_PORT == 8000
    assert FRONTEND_PORT == BACKEND_PORT
    assert FRONTEND_DIST == FRONTEND_DIR / "dist"


def test_frontend_dist_available_refleja_si_existe_el_index(monkeypatch, tmp_path):
    """`frontend/dist` no se versiona: el launcher lo compila si falta."""
    import core

    monkeypatch.setattr(core, "FRONTEND_DIST", tmp_path / "dist")
    assert frontend_dist_available() is False

    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html/>", encoding="utf-8")
    assert frontend_dist_available() is True


def test_urls():
    assert backend_url() == f"https://127.0.0.1:{BACKEND_PORT}"
    assert backend_url() == "https://127.0.0.1:8000"
    assert frontend_url() == f"https://localhost:{FRONTEND_PORT}"
    assert frontend_url() == "https://localhost:8000"


def test_lan_url(monkeypatch):
    monkeypatch.setattr("core.lan_ip", lambda: "192.168.1.42")
    assert lan_url() == f"https://192.168.1.42:{FRONTEND_PORT}"
    assert lan_url() == "https://192.168.1.42:8000"


def test_local_url_uses_hostname(monkeypatch):
    monkeypatch.setattr("core.lan_hostname", lambda: "english-tutor-pc")
    assert local_url() == f"https://english-tutor-pc.local:{FRONTEND_PORT}"
    assert local_url() == "https://english-tutor-pc.local:8000"


def test_mdns_available_when_resolves(monkeypatch):
    import core

    monkeypatch.setattr(core, "lan_hostname", lambda: "english-tutor-pc")
    monkeypatch.setattr(
        core.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("192.168.1.42", 0))],
    )
    assert mdns_available() is True


def test_mdns_available_false_when_no_mdns(monkeypatch):
    import core

    monkeypatch.setattr(core, "lan_hostname", lambda: "english-tutor-pc")

    def _fail(*args, **kwargs):
        raise OSError("no mDNS")

    monkeypatch.setattr(core.socket, "getaddrinfo", _fail)
    assert mdns_available() is False


def test_app_summary_on():
    assert app_summary(True, True) == {"backend": "on", "frontend": "on"}


def test_app_summary_off():
    assert app_summary(False, False) == {"backend": "off", "frontend": "off"}


def test_app_summary_mixed():
    assert app_summary(True, False) == {"backend": "on", "frontend": "off"}


def test_health_status_none():
    status = health_status(None)
    assert status["api"] == "off"
    assert status["database"] == "unknown"


def test_health_status_ok():
    deps = {
        "api": "ok",
        "database": "ok",
        "ollama": "ok",
        "stt": "ready",
        "tts": "unavailable",
    }
    status = health_status(deps)
    assert status["database"] == "ok"
    assert status["stt"] == "ok"
    assert status["tts"] == "unavailable"


def test_health_status_error():
    status = health_status(
        {"database": "error", "ollama": "ok", "stt": "ready", "tts": "ready"}
    )
    assert status["database"] == "error"


def test_db_summary_defaults():
    assert db_summary({}) == {"users": 0, "conversations": 0, "messages": 0}


def test_db_summary_counts():
    assert db_summary({"users": 3, "conversations": 10, "messages": 42}) == {
        "users": 3,
        "conversations": 10,
        "messages": 42,
    }


def test_user_overview():
    rows = [("a", "Ana", 2, 5), ("b", "Bob", 0, 0)]
    overview = user_overview(rows)
    assert overview[0] == {
        "id": "a",
        "name": "Ana",
        "conversations": 2,
        "messages": 5,
    }
    assert overview[1]["messages"] == 0
