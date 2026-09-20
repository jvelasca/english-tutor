"""El modo LAN del launcher (V3.73.x): opt-in declarado y una sola verdad.

El launcher es quien decide dos cosas que **tienen** que ir juntas:

1. la interfaz a la que se enlaza uvicorn (`backend_host`), y
2. el modo que recibe el backend en su entorno (`backend_env`).

Si discreparan, el backend aceptaría orígenes de la red local mientras uvicorn
escucha solo en loopback (o al revés: escucharía expuesto con la política de
orígenes cerrada, que es el caso peligroso porque el puerto sí responde). Aquí se
fijan el fail-closed, la coherencia de las dos mitades y el contrato del nombre
de la variable con `backend/config.py` (que el launcher no puede importar).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import (
    LAN_ENV,
    REQUIRE_UI_ENV,
    apply_lan_config,
    apply_stored_lan_config,
    backend_command,
    backend_env,
    backend_host,
    lan_mode,
    set_lan_mode,
    toggle_lan_config,
)

BACKEND = Path(__file__).resolve().parents[2] / "backend"


@pytest.mark.parametrize("valor", ["0", "", "  ", "no", "false", "off", "quizá"])
def test_el_modo_es_fail_closed(monkeypatch, valor):
    """Solo un valor afirmativo abre la LAN: lo demás deja loopback."""
    monkeypatch.setenv(LAN_ENV, valor)
    assert lan_mode() is False
    assert backend_host() == "127.0.0.1"


@pytest.mark.parametrize("valor", ["1", "true", "TRUE", " yes ", "on", "si", "sí"])
def test_un_valor_afirmativo_activa_la_lan(monkeypatch, valor):
    monkeypatch.setenv(LAN_ENV, valor)
    assert lan_mode() is True
    assert backend_host() == "0.0.0.0"


def test_sin_la_variable_el_launcher_no_expone_la_api(monkeypatch):
    monkeypatch.delenv(LAN_ENV, raising=False)
    cmd = backend_command()

    assert backend_host() == "127.0.0.1"
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "0.0.0.0" not in cmd


def test_el_launcher_declara_el_modo_en_el_entorno_del_backend(monkeypatch):
    """El backend recibe una decisión explícita, no una variable que puede faltar."""
    monkeypatch.delenv(LAN_ENV, raising=False)
    assert backend_env()[LAN_ENV] == "0"
    assert backend_env()[REQUIRE_UI_ENV] == "1"

    monkeypatch.setenv(LAN_ENV, "1")
    assert backend_env()[LAN_ENV] == "1"


def test_el_entorno_canoniza_el_modo(monkeypatch):
    """Un valor raro se normaliza a `0`/`1`: el backend no tiene que interpretarlo."""
    monkeypatch.setenv(LAN_ENV, "yes")
    assert backend_env()[LAN_ENV] == "1"

    monkeypatch.setenv(LAN_ENV, "quizá")
    assert backend_env()[LAN_ENV] == "0"


def test_el_bind_y_el_entorno_no_pueden_discrepar(monkeypatch):
    """Es la razón de ser de este fichero: una sola decisión, dos consumidores."""
    for valor in ("1", "0"):
        monkeypatch.setenv(LAN_ENV, valor)
        expuesto = backend_env()[LAN_ENV] == "1"
        cmd = backend_command()
        assert (cmd[cmd.index("--host") + 1] == "0.0.0.0") is expuesto, (
            f"con {LAN_ENV}={valor} el bind y el modo declarado no coinciden"
        )


def test_el_modo_se_propaga_desde_el_entorno_base(monkeypatch):
    """`backend_env(base)` no inventa el modo: respeta el entorno que hereda."""
    monkeypatch.delenv(LAN_ENV, raising=False)
    assert backend_env({LAN_ENV: "1"})[LAN_ENV] == "1"
    assert backend_env({"PATH": "/usr/bin"})[LAN_ENV] == "0"


def test_el_entorno_no_muta_el_diccionario_de_entrada(monkeypatch):
    base = {"PATH": "/usr/bin"}
    backend_env(base)
    assert base == {"PATH": "/usr/bin"}


def test_el_boton_del_panel_declara_el_modo_y_lo_aplica_al_backend():
    """Lo que hace el botón, sin GUI: declarar y que el backend lo reciba.

    El botón no puede probarse sin pantalla (es `tkinter`), así que la decisión
    que cambia la frontera de red vive en `core.set_lan_mode` y se prueba aquí de
    extremo a extremo: declarar → bind → entorno del proceso.
    """
    env: dict[str, str] = {}
    set_lan_mode(True, env)
    assert lan_mode(env) is True
    assert backend_host(env) == "0.0.0.0"
    assert backend_env(env)[LAN_ENV] == "1"

    set_lan_mode(False, env)
    assert lan_mode(env) is False
    assert backend_host(env) == "127.0.0.1"
    assert backend_env(env)[LAN_ENV] == "0"


def test_desactivar_retira_la_variable_en_vez_de_escribir_un_cero():
    """Ausente y `"0"` se leen igual (cerrado), pero retirarla es más honesto."""
    env = {LAN_ENV: "1", "PATH": "/usr/bin"}
    set_lan_mode(False, env)
    assert LAN_ENV not in env
    assert env["PATH"] == "/usr/bin"


def test_la_variable_se_llama_igual_en_launcher_y_backend():
    """Contrato compartido: el launcher no puede importar el backend."""
    config = (BACKEND / "config.py").read_text(encoding="utf-8")

    assert f'LAN_MODE_ENV = "{LAN_ENV}"' in config, (
        "la variable del modo LAN dejó de coincidir entre launcher/core.py y "
        "backend/config.py: el backend se quedaría en un modo y uvicorn en el otro"
    )
    assert "def lan_mode(" in config, "el backend perdió la lectura del modo"


def test_el_script_de_firewall_avisa_de_que_hace_falta_el_modo():
    """Abrir el puerto sin modo LAN no sirve de nada: el script tiene que decirlo."""
    script = (Path(__file__).resolve().parents[1] / "allow-firewall.ps1").read_text(
        encoding="utf-8"
    )

    assert LAN_ENV in script, (
        "allow-firewall.ps1 no menciona el modo LAN: el usuario abriría el puerto "
        "del firewall y seguiría sin poder entrar"
    )


# --- V3.75.3: la preferencia guardada del launcher --------------------------


def test_la_preferencia_guardada_se_aplica_al_arrancar():
    """El modo LAN sobrevive al cierre: es lo que pidió el gerente.

    Arrancar con `{"lan": true}` en `config.json` tiene que declarar el modo, y
    el bind y el entorno del backend tienen que salir del mismo sitio (si no,
    volvería la discrepancia que fija este fichero).
    """
    env: dict[str, str] = {}

    apply_lan_config({"lan": True}, env)

    assert lan_mode(env) is True
    assert backend_host(env) == "0.0.0.0"
    assert backend_env(env)[LAN_ENV] == "1"


def test_sin_preferencia_guardada_el_arranque_no_expone_la_api():
    """Ausencia de preferencia ⇒ loopback, igual que el fail-closed de `lan_mode`."""
    for config in ({}, {"lan": False}):
        env: dict[str, str] = {}

        apply_lan_config(config, env)

        assert lan_mode(env) is False
        assert backend_host(env) == "127.0.0.1"
        assert backend_env(env)[LAN_ENV] == "0"


def test_un_valor_guardado_que_no_es_booleano_no_expone_la_api():
    """`config.json` es un fichero de texto: editarlo a mano no puede abrir la LAN."""
    for valor in ("sí", "true", 1, None):
        env: dict[str, str] = {}

        apply_lan_config({"lan": valor}, env)

        assert lan_mode(env) is False, f"{valor!r} no es una preferencia declarada"


def test_la_preferencia_guardada_manda_sobre_el_entorno_heredado():
    """Decisión explícita: la preferencia del launcher gana al entorno del proceso.

    La GUI es la que declara el modo, así que un `ENGLISH_TUTOR_LAN=1` heredado de
    una consola no puede dejar la casilla activada sin que el panel lo refleje:
    se desactiva y el usuario ve «desactivada (solo este equipo)».
    """
    env = {LAN_ENV: "1", "PATH": "/usr/bin"}

    apply_lan_config({"lan": False}, env)

    assert LAN_ENV not in env
    assert lan_mode(env) is False

    apply_lan_config({"lan": True}, env)
    assert lan_mode(env) is True


def test_el_arranque_lee_la_preferencia_y_la_declara(tmp_path):
    """`apply_stored_lan_config` es la mitad de arranque, en una sola llamada.

    La decisión pura ya está probada arriba; esto fija el cableado que hace la GUI
    en su constructor (leer y aplicar **antes** de pintar), que era lo único que
    ninguna prueba cubría: borrar la llamada dejaba la suite en verde.
    """
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"lan": True}), encoding="utf-8")
    env: dict[str, str] = {}

    config = apply_stored_lan_config(path, env)

    assert config["lan"] is True
    assert lan_mode(env) is True
    assert backend_host(env) == "0.0.0.0"
    assert backend_env(env)[LAN_ENV] == "1"


def test_el_arranque_sin_fichero_no_expone_la_api(tmp_path):
    env: dict[str, str] = {}

    config = apply_stored_lan_config(tmp_path / "no-existe.json", env)

    assert config["lan"] is False
    assert lan_mode(env) is False
    assert backend_host(env) == "127.0.0.1"


def test_el_boton_persiste_lo_que_declara(tmp_path):
    """`toggle_lan_config` invierte, declara y **guarda**: las tres cosas juntas.

    Si se saltara el guardado, el launcher dejaría de recordar el modo y la
    promesa de V3.75.3 se rompería sin que ninguna prueba de la decisión pura lo
    notara: el modo quedaría bien en memoria y se perdería al cerrar la ventana.
    """
    path = tmp_path / "config.json"
    config = {"lan": False}
    env: dict[str, str] = {}

    toggle_lan_config(config, path, env)
    assert config["lan"] is True
    assert lan_mode(env) is True
    assert json.loads(path.read_text(encoding="utf-8")) == {"lan": True}

    toggle_lan_config(config, path, env)
    assert config["lan"] is False
    assert LAN_ENV not in env
    assert json.loads(path.read_text(encoding="utf-8")) == {"lan": False}


def test_el_boton_guarda_lo_declarado_y_no_lo_que_se_creia(tmp_path):
    """Relee `lan_mode()` después de declarar: el fichero refleja el estado real.

    Con `ENGLISH_TUTOR_LAN=1` heredado, invertir el modo **cierra** la LAN; el
    fichero tiene que guardar ese cierre, no el `True` que el panel mostraba.
    """
    path = tmp_path / "config.json"
    env = {LAN_ENV: "1"}
    config = {"lan": True}

    toggle_lan_config(config, path, env)

    assert LAN_ENV not in env
    assert json.loads(path.read_text(encoding="utf-8")) == {"lan": False}

