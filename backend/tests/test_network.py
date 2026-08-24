from fastapi.testclient import TestClient

from main import app
from services import network


def test_get_lan_ip_returns_non_empty_string():
    ip = network.get_lan_ip()
    assert isinstance(ip, str)
    assert ip


def test_api_network_info(monkeypatch):
    monkeypatch.setattr(network, "get_lan_ip", lambda: "192.168.1.42")
    with TestClient(app) as client:
        r = client.get("/api/network")
        assert r.status_code == 200
        body = r.json()
        assert body["ip"] == "192.168.1.42"
        assert body["frontend_port"] == "5173"
        assert body["backend_port"] == "8000"
        assert body["url"] == "http://192.168.1.42:5173"
