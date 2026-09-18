"""Tests de browser_cookies.py (lectura de cookies del navegador)."""
import sqlite3
from contextlib import closing

import browser_cookies as bc


def test_is_app_host_loopback():
    for host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "LOCALHOST"):
        assert bc._is_app_host(host) is True


def test_is_app_host_private_lan():
    for host in ("192.168.1.42", "10.0.0.5", "172.16.3.3", "172.31.9.9"):
        assert bc._is_app_host(host) is True


def test_is_app_host_rejects_other_domains():
    for host in ("example.com", ".google.com", "172.32.0.1", "192.169.0.1", ""):
        assert bc._is_app_host(host) is False


def test_format_expiry_webkit_session():
    assert bc._format_expiry_webkit(0) == "sesión"
    assert bc._format_expiry_webkit(None) == "sesión"


def test_format_expiry_webkit_date():
    # 133_000_000_000_000 microsegundos desde 1601 -> una fecha con formato ISO.
    out = bc._format_expiry_webkit(133_000_000_000_000)
    assert len(out) == 10 and out[4] == "-" and out[7] == "-"


def test_format_expiry_unix():
    assert bc._format_expiry_unix(0) == "sesión"
    assert bc._format_expiry_unix(None) == "sesión"
    assert bc._format_expiry_unix(1_700_000_000) == "2023-11-14"


def _make_chromium_db(path):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE cookies (host_key TEXT, name TEXT, path TEXT, "
            "expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER, "
            "encrypted_value BLOB, value TEXT)"
        )
        conn.execute(
            "INSERT INTO cookies VALUES "
            "('localhost','et_session','/',0,0,1,X'0102',''),"
            "('localhost','theme','/',133000000000000,1,0,X'0102',''),"
            "('.google.com','sid','/',133000000000000,1,1,X'0102','')"
        )


def test_read_chromium_filters_app_hosts(tmp_path):
    db = tmp_path / "c.db"
    _make_chromium_db(db)
    store = {
        "browser": "Chrome",
        "profile": "Default",
        "kind": "chromium",
        "db": str(db),
    }
    rows = bc.read_store(store)
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"et_session", "theme"}
    et = next(r for r in rows if r["name"] == "et_session")
    assert et["host"] == "localhost"
    assert et["value"].startswith("(cifrado")
    assert et["browser"] == "Chrome"
    assert et["profile"] == "Default"


def _make_firefox_db(path, session_value="TOKEN-FIRMADO"):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE moz_cookies (name TEXT, value TEXT, host TEXT, path TEXT, "
            "expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER)"
        )
        conn.execute(
            "INSERT INTO moz_cookies VALUES "
            f"('et_session','{session_value}','localhost','/',0,0,1),"
            "('x','y','example.com','/',0,0,0)"
        )


def test_read_firefox_reads_clear_value(tmp_path):
    db = tmp_path / "f.sqlite"
    _make_firefox_db(db)
    store = {"browser": "Firefox", "profile": "p", "kind": "firefox", "db": str(db)}
    rows = bc.read_store(store)
    assert len(rows) == 1
    assert rows[0]["name"] == "et_session"
    assert rows[0]["browser"] == "Firefox"


def test_read_firefox_masks_session_token(tmp_path):
    """El token de sesión no se imprime: verlo en pantalla es poder usarlo (V3.75).

    Firefox guarda las cookies en claro, así que sin este enmascarado el panel del
    launcher mostraría la sesión firmada en texto plano —una sesión copiable de una
    captura de pantalla—.
    """
    db = tmp_path / "f.sqlite"
    _make_firefox_db(db, session_value="TOKEN-FIRMADO")
    rows = bc.read_store(
        {"browser": "Firefox", "profile": "p", "kind": "firefox", "db": str(db)}
    )
    et = rows[0]
    assert "TOKEN-FIRMADO" not in et["value"]
    assert et["value"] == "(sesión firmada · 13 caracteres)"
    assert et["httponly"] is True  # el resto del diagnóstico sigue intacto


def test_mask_value_leaves_other_cookies_untouched():
    """La máscara es solo para la cookie de sesión: el resto se ve tal cual."""
    assert bc._mask_value("theme", "dark") == "dark"
    assert bc._mask_value("et_session", "abc") == "(sesión firmada · 3 caracteres)"


def test_mask_value_respeta_la_descripcion_de_una_cookie_cifrada():
    """Si el valor no se pudo leer (cifrado), no se disfraza de «sesión firmada»."""
    assert bc._mask_value("et_session", "(cifrado · 8 bytes)") == "(cifrado · 8 bytes)"


def test_read_store_missing_db_returns_empty():
    store = {"browser": "X", "profile": "p", "kind": "firefox", "db": "Z:/no/existe"}
    assert bc.read_store(store) == []


def test_cookie_summary_counts_and_detects_session():
    rows = [
        {
            "browser": "Chrome",
            "name": "et_session",
            "value": "(sesión firmada · 40 caracteres)",
            "host": "localhost",
        },
        {
            "browser": "Chrome",
            "name": "theme",
            "value": "dark",
            "host": "localhost",
        },
        {
            "browser": "Firefox",
            "name": "otra",
            "value": "x",
            "host": "localhost",
        },
    ]
    summary = bc.cookie_summary(rows)
    assert summary["total"] == 3
    assert summary["browsers"] == {"Chrome": 2, "Firefox": 1}
    assert summary["session_open"] is True


def test_session_cookie_without_session_is_reported_as_no_session():
    """Sin `et_session` no hay sesión: el resumen no adivina un perfil (V3.75)."""
    rows = [{"browser": "Chrome", "name": "theme", "value": "dark", "host": "l"}]
    assert bc.cookie_summary(rows)["session_open"] is False


def test_collect_cookies_returns_rows_and_summary(monkeypatch):
    monkeypatch.setattr(bc, "discover_stores", lambda: [])
    rows, summary = bc.collect_cookies()
    assert rows == []
    assert summary["total"] == 0
    assert summary["session_open"] is False
    assert isinstance(summary.get("diagnosis"), list)


def test_collect_cookies_includes_diagnosis(monkeypatch):
    monkeypatch.setattr(bc, "discover_stores", lambda: [])
    monkeypatch.setattr(
        bc,
        "diagnose_stores",
        lambda: [{"browser": "Chrome", "found": False, "root": "", "profiles": []}],
    )
    rows, summary = bc.collect_cookies()
    assert rows == []
    assert summary["diagnosis"] == [
        {"browser": "Chrome", "found": False, "root": "", "profiles": []}
    ]


def test_format_cookie_summary_with_browsers():
    summary = {"total": 3, "browsers": {"Chrome": 2, "Edge": 1}}
    assert (
        bc.format_cookie_summary(summary)
        == "3 cookies de la app · Chrome (2), Edge (1)"
    )


def test_format_cookie_summary_without_browsers():
    summary = {"total": 0, "browsers": {}}
    assert bc.format_cookie_summary(summary) == "0 cookies de la app"


def test_format_cookie_diagnosis_installed_and_missing():
    diagnosis = [
        {"browser": "Chrome", "found": True, "profiles": ["Default", "Trabajo"]},
        {"browser": "Edge", "found": True, "profiles": []},
        {"browser": "Firefox", "found": False, "profiles": []},
    ]
    out = bc.format_cookie_diagnosis(diagnosis)
    assert "Chrome: Default, Trabajo" in out
    assert "Edge: sin perfiles con cookies" in out
    assert "Firefox" in out
    assert out.startswith("Detectados ·")


def test_format_cookie_diagnosis_only_missing():
    diagnosis = [{"browser": "Chrome", "found": False, "profiles": []}]
    out = bc.format_cookie_diagnosis(diagnosis)
    assert out == "No instalados · Chrome"


def test_format_cookie_diagnosis_empty():
    assert bc.format_cookie_diagnosis([]) == ""


def test_browser_roots_include_chromium_family():
    names = {b for b, _e, _r in bc._BROWSER_ROOTS}
    assert {"Chrome", "Edge", "Brave", "Vivaldi", "Opera", "Opera GX"} <= names


def test_diagnose_stores_reports_browsers(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    (tmp_path / "BraveSoftware" / "Brave-Browser" / "User Data").mkdir(parents=True)
    (tmp_path / "Vivaldi" / "User Data").mkdir(parents=True)

    def fake_chromium(browser, root):
        if browser in ("Brave", "Vivaldi"):
            return [
                {
                    "browser": browser,
                    "profile": "Default",
                    "kind": "chromium",
                    "db": "x",
                }
            ]
        return []

    monkeypatch.setattr(bc, "_discover_chromium", fake_chromium)
    monkeypatch.setattr(bc, "_discover_firefox", lambda profiles: [])

    diag = bc.diagnose_stores()
    by_name = {d["browser"]: d for d in diag}
    browsers = {"Chrome", "Edge", "Brave", "Vivaldi", "Opera", "Opera GX", "Firefox"}
    assert browsers <= set(by_name)
    assert by_name["Brave"]["found"] is True
    assert by_name["Brave"]["profiles"] == ["Default"]
    assert by_name["Vivaldi"]["found"] is True
    assert by_name["Vivaldi"]["profiles"] == ["Default"]
    assert by_name["Chrome"]["found"] is False
