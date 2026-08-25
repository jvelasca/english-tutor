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
            "('localhost','et_user_id','/',0,0,0,X'0102',''),"
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
    assert {r["name"] for r in rows} == {"et_user_id", "theme"}
    et = next(r for r in rows if r["name"] == "et_user_id")
    assert et["host"] == "localhost"
    assert et["value"].startswith("(cifrado")
    assert et["browser"] == "Chrome"
    assert et["profile"] == "Default"


def _make_firefox_db(path):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE moz_cookies (name TEXT, value TEXT, host TEXT, path TEXT, "
            "expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER)"
        )
        conn.execute(
            "INSERT INTO moz_cookies VALUES "
            "('et_user_id','u1','localhost','/',0,0,0),"
            "('x','y','example.com','/',0,0,0)"
        )


def test_read_firefox_reads_clear_value(tmp_path):
    db = tmp_path / "f.sqlite"
    _make_firefox_db(db)
    store = {"browser": "Firefox", "profile": "p", "kind": "firefox", "db": str(db)}
    rows = bc.read_store(store)
    assert len(rows) == 1
    assert rows[0]["name"] == "et_user_id"
    assert rows[0]["value"] == "u1"
    assert rows[0]["browser"] == "Firefox"


def test_read_store_missing_db_returns_empty():
    store = {"browser": "X", "profile": "p", "kind": "firefox", "db": "Z:/no/existe"}
    assert bc.read_store(store) == []


def test_cookie_summary_counts_and_remembers():
    rows = [
        {
            "browser": "Chrome",
            "name": "et_user_id",
            "value": "u1",
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
            "name": "et_user_id",
            "value": "(cifrado · 8 bytes)",
            "host": "localhost",
        },
    ]
    summary = bc.cookie_summary(rows)
    assert summary["total"] == 3
    assert summary["browsers"] == {"Chrome": 2, "Firefox": 1}
    assert summary["remembered"] == "u1"


def test_cookie_summary_ignores_encrypted_remembered():
    rows = [
        {
            "browser": "Chrome",
            "name": "et_user_id",
            "value": "(cifrado · 8 bytes)",
            "host": "localhost",
        }
    ]
    assert bc.cookie_summary(rows)["remembered"] is None


def test_collect_cookies_returns_rows_and_summary(monkeypatch):
    monkeypatch.setattr(bc, "discover_stores", lambda: [])
    rows, summary = bc.collect_cookies()
    assert rows == []
    assert summary["total"] == 0
    assert summary["remembered"] is None
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
