"""Tests de seguridad LAN (V1.41): protección de origen + rate limiting."""

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import security


def _app():
    app = FastAPI()

    @app.post("/x")
    async def create():
        return {"ok": True}

    @app.get("/y")
    async def read():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    return app


def test_origin_allowed_del_propio_equipo():
    """Loopback siempre vale, y a cualquier puerto (dev server de Vite)."""
    assert security.origin_allowed(None) is True
    assert security.origin_allowed("http://localhost:5173") is True
    assert security.origin_allowed("http://127.0.0.1:5173") is True
    # V3.72 (RC-01): origen de producto (UI + API en el mismo HTTPS :8000).
    assert security.origin_allowed("https://localhost:8000") is True
    assert security.origin_allowed("http://localhost:8000") is True
    assert security.origin_allowed("http://localhost:9999") is True
    assert security.origin_allowed("https://evil.example.com") is False


def test_los_origenes_de_la_red_local_exigen_modo_lan(monkeypatch):
    """V3.73.x: exponerse a la LAN es opt-in declarado, no el defecto.

    Antes de este cambio, cualquier IP privada era un origen válido **siempre**:
    un equipo de la misma red podía hablar con la API sin que nadie lo hubiera
    pedido.
    """
    monkeypatch.delenv("ENGLISH_TUTOR_LAN", raising=False)
    for origen in (
        "https://192.168.1.20:8000",
        "http://192.168.1.20:5173",
        "https://192.168.1.20",
        "http://10.0.0.5:3000",
        "http://172.16.0.9",
    ):
        assert security.origin_allowed(origen) is False, (
            f"{origen} sigue valiendo sin modo LAN: la red local entra sola"
        )

    monkeypatch.setenv("ENGLISH_TUTOR_LAN", "1")
    for origen in (
        "https://192.168.1.20:8000",
        "http://192.168.1.20:5173",
        "https://192.168.1.20",
        "http://10.0.0.5:3000",
        "http://172.16.0.9",
    ):
        assert security.origin_allowed(origen) is True, (
            f"{origen} debería valer en modo LAN"
        )


def test_un_dominio_que_imita_una_ip_privada_no_cuela(monkeypatch):
    """El patrón va anclado: `192.168.1.20.evil.com` no es una IP privada."""
    monkeypatch.setenv("ENGLISH_TUTOR_LAN", "1")
    assert security.origin_allowed("https://192.168.1.20.evil.com") is False
    assert security.origin_allowed("https://evil.example.com") is False


def test_unsafe_method_bad_origin_rejected():
    with TestClient(_app()) as client:
        r = client.post("/x", headers={"origin": "https://evil.example.com"})
    assert r.status_code == 403


def test_unsafe_method_allowed_origin_passes():
    with TestClient(_app()) as client:
        r = client.post("/x", headers={"origin": "http://localhost:5173"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_unsafe_method_no_origin_passes():
    with TestClient(_app()) as client:
        r = client.post("/x")
    assert r.status_code == 200


def test_safe_method_ignores_origin():
    with TestClient(_app()) as client:
        r = client.get("/y", headers={"origin": "https://evil.example.com"})
    assert r.status_code == 200


def test_rate_limit_rejects_after_limit(monkeypatch):
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 2)
    security._clients.clear()
    with TestClient(_app()) as client:
        assert client.post("/x").status_code == 200
        assert client.post("/x").status_code == 200
        assert client.post("/x").status_code == 429
    security._clients.clear()


def test_una_ruta_no_gasta_el_cupo_de_otra():
    """V3.79.0: cada clase de ruta tiene su propia ventana.

    Es el fallo que vio el alumno: «Pedir dar de baja mi perfil» respondía «El
    servidor local está saturado» sin que nadie hubiera saturado nada. Con una
    sola cola por equipo, cualquier tráfico reciente —abrir el diccionario son
    varias peticiones— dejaba la cola por encima del cupo estrecho de la ruta de
    la baja, y la baja fallaba.

    Se reproduce con el cupo general REAL (1200), sin monkeypatch: seis
    peticiones normales pasan sin problema y bastan para que el cupo heredado de
    5/min rechace la baja. Con la ventana compartida, la de abajo es 429.
    """
    security._clients.clear()
    app = FastAPI()

    @app.post("/api/vocabulary/lexicon")
    async def lexicon():
        return {"ok": True}

    @app.post("/api/profile-requests/delete")
    async def baja():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    with TestClient(app) as client:
        # Tráfico normal y corriente: todas pasan, ninguna es la baja.
        for _ in range(6):
            assert client.post("/api/vocabulary/lexicon").status_code == 200
        # ...y la baja sigue pasando: no comparte ventana con lo de arriba.
        assert client.post("/api/profile-requests/delete").status_code == 200
    security._clients.clear()


def test_la_baja_no_hereda_el_cupo_antibarrido():
    """V3.79.0: `/api/profile-requests/delete` no comparte el 5/min del alta.

    Candado de configuración: si alguien retira la clave específica, la baja
    vuelve a caer bajo el prefijo corto (`/api/profile-requests`) y el fallo
    original reaparece sin que ningún test de comportamiento lo note —porque el
    cupo seguiría existiendo, solo que prestado—.
    """
    clase, limite = security._route_class("/api/profile-requests/delete")
    assert clase == "/api/profile-requests/delete"
    # El alta defiende una ruta SIN sesión de un barrido de la cola; la baja es
    # una escritura autenticada de un clic. No pueden medirse con la misma vara.
    assert limite > security._PATH_LIMITS["/api/profile-requests"]


def test_el_cupo_de_la_baja_sigue_mordiendo(monkeypatch):
    """No se afloja lo que protege: su propia ventana también rechaza."""
    monkeypatch.setitem(security._PATH_LIMITS, "/api/profile-requests/delete", 1)
    security._clients.clear()
    app = FastAPI()

    @app.post("/api/profile-requests/delete")
    async def baja():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    with TestClient(app) as client:
        assert client.post("/api/profile-requests/delete").status_code == 200
        assert client.post("/api/profile-requests/delete").status_code == 429
    security._clients.clear()


def test_gana_el_prefijo_mas_largo_no_el_orden_del_diccionario(monkeypatch):
    """El cupo aplicado no puede depender de dónde se escribió cada clave.

    Con `break` en el primer acierto, en cuanto una ruta pasó a ser prefijo de
    otra (`/api/profile-requests` lo es de `/api/profile-requests/delete`) el
    cupo que se aplicaba dependía del orden de inserción. El más largo manda.
    """
    monkeypatch.setitem(security._PATH_LIMITS, "/api/a", 7)
    monkeypatch.setitem(security._PATH_LIMITS, "/api/a/b", 11)
    assert security._route_class("/api/a/b/c") == ("/api/a/b", 11)
    assert security._route_class("/api/a/zzz") == ("/api/a", 7)
    # Sin coincidencia, la clase general.
    assert security._route_class("/api/otra") == ("", security._DEFAULT_LIMIT)


def test_health_exempt_never_rate_limited(monkeypatch):
    """Las sondas /api/health no consumen cupo ni pueden recibir 429 (V3.6.2)."""
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 1)

    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/y")
    async def read():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    with TestClient(app) as client:
        # Agotamos el cupo con rutas normales...
        assert client.get("/y").status_code == 200
        assert client.get("/y").status_code == 429
        # ...y /api/health sigue respondiendo aunque el cupo esté agotado.
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health").status_code == 200


def test_rate_limit_payload_and_retry_after(monkeypatch):
    """El 429 lleva body {detail, code} y cabecera Retry-After (V3.6.2)."""
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 1)
    security._clients.clear()
    with TestClient(_app()) as client:
        assert client.get("/y").status_code == 200
        r = client.get("/y")
        assert r.status_code == 429
        body = r.json()
        assert body["code"] == "RATE_LIMITED"
        assert "saturado" in body["detail"]
        assert r.headers.get("retry-after") == "5"
    security._clients.clear()


def test_rate_limit_snapshot_counts_rejections(monkeypatch):
    """rate_limit_snapshot cuenta los 429 de la ventana (V3.6.2)."""
    monkeypatch.setattr(security, "_DEFAULT_LIMIT", 1)
    security._clients.clear()
    assert security.rate_limit_snapshot() == 0
    with TestClient(_app()) as client:
        assert client.get("/y").status_code == 200
        for _ in range(3):
            assert client.get("/y").status_code == 429
    assert security.rate_limit_snapshot() == 3
    assert security.rate_limit_snapshot(window_seconds=0) == 0
    security._clients.clear()
    security._rejections.clear()


def test_rate_limit_snapshot_prunes_old_entries():
    security._rejections.append(time.monotonic() - 10_000)
    security._rejections.append(time.monotonic())
    assert security.rate_limit_snapshot() == 1
    security._rejections.clear()


# --- Candados de `_PATH_LIMITS` (V3.73.x) ------------------------------------
#
# Contexto: `_PATH_LIMITS` declaraba `/api/voz/transcribe` (una ruta que no
# existe) mientras el router monta `/api/transcribe`, así que Whisper usó el cupo
# general (1200/min) en vez del reforzado (180/min) sin que nada fallara. Estos
# tests atan el mapa de límites a la app real: la siguiente errata (o la
# siguiente ruta cara sin cupo) no pasa.

# Rutas cuyo coste (CPU de Whisper/Piper/LLM, red y disco de las voces)
# justifica un cupo propio y no el general. Es política declarada, no un detalle.
COSTLY_ROUTES = (
    "/api/transcribe",
    "/api/tts",
    "/api/translate",
    "/api/voices/download",
)

# Mínimo de rutas que la app debe exponer: si FastAPI cambiara su forma de
# diferir `include_router` y el recorrido devolviera casi nada, el candado de
# abajo pasaría «por vacío» sin comprobar nada. Este suelo lo impide.
MIN_APP_ROUTES = 100


def _app_routes() -> set[str]:
    """Todas las rutas reales de la app, incluidos los routers incluidos.

    FastAPI no expande `include_router` en `app.routes`: deja un
    `_IncludedRouter` con el router original dentro, así que hay que descender.
    """
    from main import app

    found: set[str] = set()
    pending = list(app.routes)
    while pending:
        route = pending.pop()
        path = getattr(route, "path", None)
        if isinstance(path, str):
            found.add(path)
        for attr in ("original_router", "router"):
            sub = getattr(route, attr, None)
            sub_routes = getattr(sub, "routes", None)
            if sub_routes:
                pending.extend(sub_routes)
    return found


def test_el_recorrido_de_rutas_ve_la_app_entera():
    """El inventario de rutas no puede quedar vacío o a medias."""
    assert len(_app_routes()) >= MIN_APP_ROUTES


def test_path_limits_match_real_routes():
    """Cada clave de `_PATH_LIMITS` es prefijo de una ruta REAL montada."""
    paths = _app_routes()
    for prefix in security._PATH_LIMITS:
        assert any(path.startswith(prefix) for path in paths), (
            f"`_PATH_LIMITS` declara {prefix!r}, que no es prefijo de ninguna "
            f"ruta montada en la app: ese límite nunca se aplica"
        )


def test_costly_routes_have_own_rate_limit():
    """Ninguna ruta de coste alto cae en el cupo general."""
    for route in COSTLY_ROUTES:
        own = [
            limit
            for prefix, limit in security._PATH_LIMITS.items()
            if route.startswith(prefix)
        ]
        assert own, (
            f"{route} no tiene cupo propio: cae en el general "
            f"({security._DEFAULT_LIMIT}/min)"
        )
        assert min(own) < security._DEFAULT_LIMIT


def test_transcribe_uses_its_own_limit(monkeypatch):
    """`/api/transcribe` se limita con su cupo reforzado, no con el general.

    Prueba de comportamiento: con el general (1200) la segunda petición pasaría.
    """
    monkeypatch.setitem(security._PATH_LIMITS, "/api/transcribe", 1)
    app = FastAPI()

    @app.post("/api/transcribe")
    async def transcribe():
        return {"ok": True}

    app.add_middleware(security.SecurityMiddleware)
    with TestClient(app) as client:
        assert client.post("/api/transcribe").status_code == 200
        assert client.post("/api/transcribe").status_code == 429
