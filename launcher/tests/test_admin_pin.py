"""Tests del PIN de administración del launcher (V3.77).

El PIN es lo que separa «mirar el estado» de «crear y borrar perfiles». Lo que se
prueba aquí es el **cableado** del que depende esa frontera: qué PIN se considera
válido, cuál manda cuando hay dos fuentes, y qué pasa en el entorno del backend
cuando no hay ninguno. Todo es lógica pura, sin pantalla y sin red.
"""
from __future__ import annotations

import config_store
import core

# Un PIN con forma válida, para no repetir el literal en cada caso.
_PIN = "secreto-largo"


def test_un_pin_valido_tiene_longitud_y_no_lleva_espacios_pegados():
    assert core.is_valid_admin_pin(_PIN)
    assert core.is_valid_admin_pin("abcdef")  # el mínimo, 6
    assert core.is_valid_admin_pin("x" * 64)  # el máximo, 64

    # Espacios en los extremos: un error de tecleo, no un secreto más fuerte.
    assert not core.is_valid_admin_pin(" secreto-largo")
    assert not core.is_valid_admin_pin("secreto-largo ")
    # Longitudes fuera de rango.
    assert not core.is_valid_admin_pin("")
    assert not core.is_valid_admin_pin("corto")
    assert not core.is_valid_admin_pin("x" * 65)
    # Y lo que ni siquiera es cadena (lo mismo que puede venir del JSON).
    for valor in (None, 123456, True, ["secreto-largo"]):
        assert not core.is_valid_admin_pin(valor)


def test_sin_pin_la_administracion_esta_cerrada(monkeypatch):
    """Fail-closed: ausencia de PIN no es «administración abierta»."""
    monkeypatch.delenv(core.ADMIN_PIN_ENV, raising=False)

    assert core.admin_pin({}, {}) == ""
    assert core.admin_pin(None, {}) == ""
    # Ni con una forma que no vale: se trata como ausente.
    assert core.admin_pin({"admin_pin": "corto"}, {}) == ""
    assert core.admin_pin({"admin_pin": " con-espacios "}, {}) == ""


def test_la_preferencia_guardada_manda_sobre_el_entorno():
    """Es la decisión explícita del webmaster y tiene que sobrevivir al cierre."""
    assert core.admin_pin({"admin_pin": _PIN}, {core.ADMIN_PIN_ENV: "otro-pin"}) == _PIN
    # Y sin preferencia, manda el entorno (arranque manual y tests).
    assert core.admin_pin({}, {core.ADMIN_PIN_ENV: "otro-pin"}) == "otro-pin"
    # Y una preferencia **vacía** es una decisión, no un hueco: manda el entorno.
    assert core.admin_pin({"admin_pin": ""}, {core.ADMIN_PIN_ENV: "otro-pin"}) == (
        "otro-pin"
    )


def test_apply_admin_config_declara_el_pin_vigente():
    """Declara el vigente, no solo el guardado: el arranque manual tiene que servir."""
    env: dict[str, str] = {}

    core.apply_admin_config({"admin_pin": _PIN}, env)
    assert env[core.ADMIN_PIN_ENV] == _PIN

    # Arranque manual: hay PIN en el entorno y ninguna preferencia guardada.
    heredado = {core.ADMIN_PIN_ENV: "otro-pin"}
    core.apply_admin_config({"admin_pin": ""}, heredado)
    assert heredado[core.ADMIN_PIN_ENV] == "otro-pin"

    # Y sin ninguna de las dos fuentes, no se declara nada.
    vacio: dict[str, str] = {}
    core.apply_admin_config({"admin_pin": ""}, vacio)
    assert core.ADMIN_PIN_ENV not in vacio


def test_apply_admin_config_no_declara_un_pin_con_mala_forma():
    """Un `config.json` tocado a mano no habilita administración con «a»."""
    env: dict[str, str] = {}

    core.apply_admin_config({"admin_pin": "a"}, env)

    assert core.ADMIN_PIN_ENV not in env


def test_set_admin_pin_guarda_valida_y_declara(tmp_path):
    """«Validar → declarar → guardar», en un solo sitio y probado sin pantalla."""
    path = tmp_path / "config.json"
    config = dict(config_store.DEFAULTS)
    env: dict[str, str] = {}

    assert core.set_admin_pin("corto", config, path, env) is None
    assert config["admin_pin"] == "", "un PIN que no vale no puede haberse guardado"
    assert not path.exists(), "un PIN que no vale no puede llegar al disco"

    assert core.set_admin_pin(_PIN, config, path, env) is not None
    assert config["admin_pin"] == _PIN
    assert env[core.ADMIN_PIN_ENV] == _PIN
    assert path.exists()

    # Y retirar vuelve al estado cerrado, en los tres sitios a la vez.
    assert core.set_admin_pin("", config, path, env) is not None
    assert config["admin_pin"] == ""
    assert core.ADMIN_PIN_ENV not in env, (
        "retirar el PIN deja la administración abierta si el entorno conserva el viejo"
    )


def test_generate_admin_pin_ofrece_siempre_un_pin_valido():
    """El botón «Generar» no puede proponer algo que el propio candado rechace."""
    for _ in range(20):
        assert core.is_valid_admin_pin(core.generate_admin_pin())


def test_el_pin_llega_al_backend_al_arrancar_por_eso_hay_que_reiniciar(tmp_path):
    """Guardar declara el PIN en el entorno; `backend_env()` lo copia al arrancar.

    Es la razón por la que el lanzador **reinicia** al guardar o retirar el PIN: el
    backend que ya está en marcha no vuelve a leer el entorno, así que hasta el
    reinicio `/api/admin/*` responde 401 y la cola de solicitudes parece vacía.
    """
    env: dict[str, str] = {}
    core.set_admin_pin(_PIN, dict(config_store.DEFAULTS), tmp_path / "c.json", env)

    assert core.backend_env(env)[core.ADMIN_PIN_ENV] == _PIN

    # Retirar también viaja: el backend reiniciado queda cerrado de verdad.
    core.set_admin_pin("", {}, tmp_path / "c.json", env)
    assert core.ADMIN_PIN_ENV not in core.backend_env(env)
