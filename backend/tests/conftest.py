"""Raíz de la suite de backend: imports resueltos e **identidad de los tests**.

Dos cosas:

1. Que `import config`, `import services…` resuelvan al ejecutar `pytest` desde
   cualquier `cwd` (el `sys.path` de abajo).
2. El **adaptador de identidad** de la Fase 2 del P0 (V3.75): las suites que ya
   existían piden la API con `params={"user_id": uid}`, y desde V3.75 la identidad
   viaja en una **sesión firmada**, no en la query.
"""
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
# Permite `from golden import loader` en los tests de golden datasets.
sys.path.insert(0, str(_TESTS))


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Limpia el estado en memoria del rate limiter entre tests (V1.41)."""
    import security

    security._clients.clear()
    security._rejections.clear()
    yield
    security._clients.clear()
    security._rejections.clear()


# ---------------------------------------------------------------------------
# Identidad de los tests: de `?user_id=` a una sesión firmada de verdad (V3.75)
# ---------------------------------------------------------------------------
#
# La Fase 2 del P0 (`docs/audit/PLAN-P0-IDENTIDAD.md`) movió la identidad de la
# query a una cookie firmada por el servidor. Las suites existentes declaran la
# identidad con `params={"user_id": uid}` (556 llamadas) o dentro de la URL (83) y
# **no se reescriben**: el adaptador de abajo traduce ese parámetro a una sesión
# **emitida de verdad** y deja que la petición siga el camino real —`current_user`
# lee la cookie, verifica la firma en tiempo constante y carga el perfil—.
#
# Se adapta: el **origen** de la identidad (query de test → cookie).
# No se adapta: la firma, la caducidad, el 401 y el 404, que se ejecutan igual.
# Se pierde, y se declara: estas suites dejan de probar «la identidad viene de la
# cookie»; de eso se ocupan los tests nuevos (`test_sessions.py`,
# `test_identity_source.py`, `test_users_self_only.py`). Es el precio acordado en
# el plan §7.2 a cambio de no migrar 109 ficheros dentro de un cierre de P0.
#
# La otra mitad del adaptador es el aislamiento del **secreto**: sin él, la
# primera petición de la suite crearía `backend/data/session.secret` en el árbol
# de trabajo (un artefacto de máquina que nadie ha pedido).


def _identity_from_params(params: object) -> tuple[object | None, object]:
    """`(user_id, params sin la identidad)` si el test la declara por `params=`."""
    if isinstance(params, dict):
        if "user_id" not in params:
            return None, params
        return params["user_id"], {k: v for k, v in params.items() if k != "user_id"}
    if isinstance(params, (list, tuple)):
        claimed: object | None = None
        rest: list[object] = []
        for item in params:
            pair = isinstance(item, (list, tuple)) and len(item) == 2
            if pair and item[0] == "user_id":
                claimed = item[1]
            else:
                rest.append(item)
        return (claimed, rest) if claimed is not None else (None, params)
    return None, params


def _identity_from_url(url: object) -> tuple[object | None, object]:
    """`(user_id, url sin la identidad)` si el test la declara en la URL."""
    parts = urlsplit(str(url))
    if not parts.query or "user_id" not in parts.query:
        return None, url
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    claimed = next((value for key, value in pairs if key == "user_id"), None)
    if claimed is None:
        return None, url
    rest = [(key, value) for key, value in pairs if key != "user_id"]
    clean = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(rest), parts.fragment)
    )
    return claimed, clean


def _cookie_names(cookies: object) -> set[str]:
    """Nombres de cookie, venga un `dict`, un listado de pares o un `httpx.Cookies`.

    Ojo con el último: `httpx.Cookies` itera **nombres** (cadenas), no pares. Darlo
    por supuesto hacía que el adaptador no viera la sesión que un test ya tenía
    abierta y la pisara con la del `?user_id=`.
    """
    if isinstance(cookies, dict):
        return set(cookies)
    if cookies is None:
        return set()
    names: set[str] = set()
    try:
        for item in cookies:  # type: ignore[union-attr]
            names.add(item if isinstance(item, str) else item[0])
    except (TypeError, ValueError):
        return set()
    return names


def _header_cookie_value(headers: object) -> str:
    if not headers:
        return ""
    items = headers.items() if isinstance(headers, dict) else headers
    try:
        pairs = list(items)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    return " ".join(str(value) for key, value in pairs if str(key).lower() == "cookie")


def _has_own_session(client: object, cookies: object, headers: object) -> bool:
    """¿El test ya trae una sesión propia? Entonces **no** se le inyecta ninguna.

    Es la regla que deja escribir los tests nuevos: `test_identity_source` manda a
    la vez una sesión del perfil A y un `?user_id=B` para probar que el parámetro
    ya no significa nada, y el adaptador no debe «traducirlo».
    """
    from services import sessions

    if sessions.SESSION_COOKIE in _cookie_names(cookies):
        return True
    if sessions.SESSION_COOKIE in _cookie_names(getattr(client, "cookies", None)):
        return True
    return sessions.SESSION_COOKIE in _header_cookie_value(headers)


@pytest.fixture(scope="session")
def _session_secret_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Carpeta del secreto de firma para toda la sesión de `pytest`."""
    return tmp_path_factory.mktemp("sesion")


@pytest.fixture(autouse=True)
def _session_secret_aislado(_session_secret_dir: Path, monkeypatch) -> None:
    """El secreto de sesión no se escribe en el `data/` real del proyecto.

    Se fija la **ruta**, no el valor: el valor se crea en el primer uso, que es
    justo lo que hay que ejercitar (y `test_sessions.py` comprueba la creación).
    """
    from services import sessions

    monkeypatch.setattr(
        sessions,
        "secret_path",
        lambda: _session_secret_dir / sessions.SESSION_SECRET_NAME,
    )


@pytest.fixture(autouse=True)
def _identidad_por_sesion(request, monkeypatch, _session_secret_aislado: None) -> None:
    """Traduce el `?user_id=` de los tests a una sesión firmada (ver arriba).

    Los tests marcados con `identidad_cruda` quedan fuera: son los que necesitan
    mandar el parámetro **sin** que nadie lo traduzca (justo lo que comprueban).
    """
    if request.node.get_closest_marker("identidad_cruda"):
        return
    from fastapi.testclient import TestClient

    from services import sessions

    original = TestClient.request

    def request_with_session(self, method, url, **kwargs):
        from_params, params = _identity_from_params(kwargs.get("params"))
        from_url, clean_url = _identity_from_url(url)
        claimed = from_params if from_params is not None else from_url
        if claimed is None or _has_own_session(
            self, kwargs.get("cookies"), kwargs.get("headers")
        ):
            return original(self, method, url, **kwargs)
        if params is not None:
            kwargs["params"] = params
        # La cookie se pone en el tarro del cliente y se retira al terminar. Es lo
        # que `httpx` recomienda (`cookies=` por petición está deprecado y con 556
        # llamadas serían 556 avisos) y **conserva la semántica por petición**: una
        # petición POSTERIOR sin identidad sigue llegando sin identidad, como antes
        # de V3.75, en vez de heredar la sesión del tarro.
        #
        # V3.82: el token se emite con la **época real** de la cuenta. Antes se
        # emitía con la de defecto (cero), que funcionaba mientras ninguna suite
        # preparase su escenario con una contraseña (`set_password_hash` sube la
        # época). Con V3.82 varias la preparan, y un token de época cero llegaría
        # como `SESSION_STALE`: el adaptador tiene que emitir la sesión que emitiría
        # un login de verdad, no una caducada.
        from repositories import users as users_repo

        epoch = users_repo.get_auth_epoch(str(claimed)) or 0
        self.cookies.set(
            sessions.SESSION_COOKIE, sessions.issue(str(claimed), epoch=epoch)
        )
        try:
            return original(self, method, clean_url, **kwargs)
        finally:
            self.cookies.delete(sessions.SESSION_COOKIE)

    monkeypatch.setattr(TestClient, "request", request_with_session)


@pytest.fixture
def production_items(monkeypatch):
    """Fábrica de **ítems de producción** sintéticos para los endpoints de producción.

    El banco no puede contener un ítem de producción: `ListeningAsset` exige
    `question`, `options` y `answer_index` en **todos** sus ítems. Un ítem con
    opciones etiquetado de dictado es una pregunta de opción múltiple a la que el
    flujo de producción tira el enunciado (el defecto que impide
    `test_production_items_do_not_carry_multiple_choice_options`) y uno sin ellas
    no valida. Los skills `dictation`/`shadowing` se sirven por la capa derivada
    bottom-up (`d-`).

    Para ejercitar el camino **del banco** del endpoint, esta fábrica inyecta ítems
    con la forma que tendrían si el esquema los representara: la copia de un ítem
    real con el `skill` cambiado. Uso: `items = production_items("dictation",
    "shadowing")` → `{id: ítem}`, y esos ids se resuelven durante el test.
    """
    from domain import listening as listening_domain
    from services.listening import get_question

    def _build(*kinds: str) -> dict[str, dict]:
        items = {
            f"prod-{kind}": dict(get_question("l18"), id=f"prod-{kind}", skill=kind)
            for kind in kinds
        }
        monkeypatch.setattr(
            listening_domain,
            "get_question",
            lambda qid: items.get(qid) or get_question(qid),
        )
        return items

    return _build
