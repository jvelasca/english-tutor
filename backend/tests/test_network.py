from fastapi.testclient import TestClient

from main import app
from services import network


def test_get_lan_ip_returns_non_empty_string():
    ip = network.get_lan_ip()
    assert isinstance(ip, str)
    assert ip


def test_get_lan_hostname_returns_non_empty_string():
    hostname = network.get_lan_hostname()
    assert isinstance(hostname, str)
    assert hostname


def test_api_network_info(monkeypatch):
    monkeypatch.setattr(network, "get_lan_ip", lambda: "192.168.1.42")
    monkeypatch.setattr(network, "get_lan_hostname", lambda: "english-tutor-pc")
    monkeypatch.setattr(network, "local_url_resolves", lambda: True)
    with TestClient(app) as client:
        r = client.get("/api/network")
        assert r.status_code == 200
        body = r.json()
        assert body["ip"] == "192.168.1.42"
        assert body["hostname"] == "english-tutor-pc"
        assert body["frontend_port"] == "5173"
        assert body["backend_port"] == "8000"
        assert body["url"] == "https://192.168.1.42:5173"
        assert body["local_url"] == "https://english-tutor-pc.local:5173"
        assert body["local_url_available"] is True


def test_local_url_resolves_when_mdns_present(monkeypatch):
    monkeypatch.setattr(network, "get_lan_hostname", lambda: "english-tutor-pc")
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("192.168.1.42", 0))],
    )
    assert network.local_url_resolves() is True


def test_local_url_resolves_false_when_no_mdns(monkeypatch):
    monkeypatch.setattr(network, "get_lan_hostname", lambda: "english-tutor-pc")

    def _fail(*args, **kwargs):
        raise OSError("no mDNS")

    monkeypatch.setattr(network.socket, "getaddrinfo", _fail)
    assert network.local_url_resolves() is False
