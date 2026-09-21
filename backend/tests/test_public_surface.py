"""La superficie **sin sesión** está declarada, no olvidada (VG-N6, V3.75).

La auditoría de V3.73 (`docs/audit/VERIFICACION-SEGURIDAD-V373.md`, VG-N6) señaló
tres endpoints que respondían sin credencial ninguna —`/api/system/status`,
`/api/network` y `/api/models`— y dejó la decisión abierta: **declararlos
aceptados de forma explícita o restringirlos**. Esto es la mitad «declararlos»,
con la parte que suele faltar: un candado que lo comprueba.

**Qué fija este archivo.** La lista de rutas que deben seguir respondiendo sin
sesión (romperlas en silencio rompe el arranque del producto: el launcher y la
puerta de perfil las usan antes de que exista ningún perfil) y la lista de las que
**no** pueden responder sin sesión. Si alguien abre una de las segundas o cierra
una de las primeras por descuido, el test lo dice con el nombre de la ruta.

**Por qué se aceptan (y no se restringen).** El producto no tiene cuentas: el
alumno elige perfil, no se autentica (Fase 3 del P0,
`docs/audit/PLAN-P0-IDENTIDAD.md`). En ese marco, lo que estas rutas exponen es
**reconocimiento barato** —modelos instalados, IP/hostname de LAN, trabajos de
generación en curso y rechazos por rate limit— que **no** permite leer ni escribir
los datos de ningún alumno: para eso están los endpoints de datos, que desde V3.75
exigen sesión firmada. Y la frontera que decide quién alcanza la API no es esta
lista, es la **red** (loopback por defecto, LAN opt-in). Cuando llegue la
autenticación real, cada ruta de la primera lista recibe su credencial o pasa a
admin; hasta entonces, la decisión está escrita y sujeta a test.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo

# Rutas que **deben** responder sin sesión y qué se espera de cada una.
# (Se declara el código esperado para que el test no se conforme con «no es 401»:
# `/api/health/ready` responde 503 legítimamente cuando falta una dependencia.)
SIN_SESION: dict[str, tuple[int, ...]] = {
    # El launcher mide el pulso antes de que haya ningún perfil.
    "/api": (200,),
    "/api/health": (200,),
    "/api/health/live": (200,),
    "/api/health/ready": (200, 503),
    "/api/health/dependencies": (200,),
    # La puerta de perfil necesita listar/crear perfiles y abrir sesión: si esto
    # exigiera sesión, no habría forma de conseguir la primera.
    "/api/users": (200,),
    # El selector de Ajustes → IA y la tarjeta de conexión se pintan antes de
    # cualquier elección de perfil.
    "/api/models": (200, 502),  # 502 = Ollama no responde (no es un 401)
    "/api/network": (200,),
    # El estado operativo que el launcher muestra («trabajando»).
    "/api/system/status": (200,),
}

# Rutas de datos: sin sesión firmada, **401 `SESSION_REQUIRED`** y nada más.
CON_SESION: dict[str, tuple[int, ...]] = {
    "/api/settings": (401,),
    "/api/profile": (401,),
    "/api/progress": (401,),
    "/api/conversations": (401,),
    "/api/vocabulary": (401,),
    "/api/grammar/errors": (401,),
    "/api/academy/levels": (401,),
    "/api/listening/stats": (401,),
}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("Ana")["id"]


def test_la_superficie_sin_sesion_responde_sin_sesion(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        raros: list[str] = []
        for ruta, esperados in SIN_SESION.items():
            r = client.get(ruta)
            if r.status_code not in esperados:
                raros.append(f"{ruta} → {r.status_code} (esperaba {esperados})")
        assert raros == [], (
            "rutas declaradas sin sesión que dejaron de responder: "
            f"{raros}. Si el cambio es intencionado, mueve la ruta de lista y "
            "actualiza docs/ARQUITECTURA.md (sección de superficie sin sesión)."
        )


@pytest.mark.identidad_cruda
def test_la_superficie_con_sesion_no_responde_sin_sesion(monkeypatch, tmp_path):
    """El otro lado del candado: sin sesión, los datos del alumno no salen.

    Va marcado `identidad_cruda` a propósito: aquí el `?user_id=` **debe** viajar
    sin traducirse, porque lo que se comprueba es justo que ese parámetro ya no
    abre nada (el adaptador de `conftest.py` lo convertiría en una sesión válida y
    el test se estaría midiendo a sí mismo).
    """
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        abiertas: list[str] = []
        for ruta, (esperado,) in CON_SESION.items():
            r = client.get(ruta, params={"user_id": uid})
            if r.status_code != esperado:
                abiertas.append(f"{ruta} → {r.status_code}")
        assert abiertas == [], (
            f"rutas de datos que respondieron sin sesión: {abiertas}"
        )


def test_la_ruta_del_pin_es_de_datos_y_exige_sesion(monkeypatch, tmp_path):
    """`PUT /api/session/pin` (V3.76) cambia un secreto del perfil: no es pública.

    Va aparte de `CON_SESION` porque el diccionario de arriba se recorre con
    `GET` y esta ruta no admite `GET` (405, no 401): mezclarlas debilitaría el
    candado del otro lado sin avisar.
    """
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put("/api/session/pin", json={"new_pin": "1234"})
        assert r.status_code == 401
        assert r.json()["detail"] == "SESSION_REQUIRED"


def test_la_peticion_de_perfil_es_la_unica_escritura_sin_sesion(monkeypatch, tmp_path):
    """`POST /api/profile-requests` (V3.77): sin sesión **y** sin efecto.

    Es la única escritura de la app que no exige credencial, porque quien pide un
    perfil no tiene ninguno todavía. Se comprueba en el mismo test que lo que
    consigue es exactamente una fila en la cola: si algún día empezara a crear un
    perfil, este es el test que lo dice.
    """
    _setup(monkeypatch, tmp_path)
    antes = len(users_repo.list_users(include_disabled=True))
    with TestClient(app) as client:
        r = client.post("/api/profile-requests", json={"display_name": "Nueva"})
    assert r.status_code == 201
    assert len(users_repo.list_users(include_disabled=True)) == antes

    # Y la de baja, que es la otra mitad, sí exige sesión.
    with TestClient(app) as client:
        assert (
            client.post("/api/profile-requests/delete", json={"note": ""}).status_code
            == 401
        )


def test_la_superficie_sin_sesion_esta_declarada_por_escrito():
    """Candado anti-deriva documental: lo aceptado tiene que estar escrito.

    Sin esto, «declarar aceptado» se queda en un comentario de un test y la
    próxima auditoría vuelve a abrir el mismo hallazgo.
    """
    from pathlib import Path

    doc = (
        Path(__file__).resolve().parents[2] / "docs" / "ARQUITECTURA.md"
    ).read_text(encoding="utf-8")

    assert "Superficie sin sesión" in doc, (
        "ARQUITECTURA.md no declara la superficie que responde sin sesión"
    )
    for ruta in (
        "/api/system/status",
        "/api/network",
        "/api/models",
        # V3.77: la única escritura sin sesión y su justificación.
        "/api/profile-requests",
    ):
        assert ruta in doc, f"ARQUITECTURA.md no declara {ruta} como aceptada"
