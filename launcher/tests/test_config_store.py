"""Tests de config_store.py (preferencias del launcher, hoy el modo LAN)."""
import json

import config_store


def test_load_config_missing_file_returns_defaults(tmp_path):
    """Sin preferencia guardada el modo LAN queda cerrado (fail-closed)."""
    config = config_store.load_config(tmp_path / "no-existe.json")

    assert config["lan"] is False
    assert config == config_store.DEFAULTS


def test_load_config_corrupt_json_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert config_store.load_config(path)["lan"] is False


def test_load_config_reads_true(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"lan": True}), encoding="utf-8")

    assert config_store.load_config(path)["lan"] is True


def test_load_config_descarta_valores_que_no_son_booleanos(tmp_path):
    """Un `1` numérico o un `"true"` textual no activan la LAN por accidente.

    En Python `True` es un `int`, así que la comprobación es `isinstance(val, bool)`
    a propósito: sin ella, un `1` del JSON colaría como modo declarado.
    """
    path = tmp_path / "config.json"

    for valor in (1, 0, "true", "sí", None, [], {}):
        path.write_text(json.dumps({"lan": valor}), encoding="utf-8")
        assert config_store.load_config(path)["lan"] is False, (
            f"un valor que no es booleano ({valor!r}) no puede declarar el modo"
        )


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = {"lan": True}

    config_store.save_config(config, path)
    loaded = config_store.load_config(path)

    assert loaded == config


def test_save_config_ignora_errores_de_escritura(tmp_path):
    """No poder guardar la preferencia no puede impedir cerrar el launcher."""
    # Un directorio donde se espera un fichero: el renombrado falla con OSError.
    path = tmp_path / "como-directorio"
    path.mkdir()

    config_store.save_config({"lan": True}, path)

    assert path.is_dir()
    # Ni se convirtió el directorio en fichero ni quedó un temporal huérfano.
    assert list(tmp_path.iterdir()) == [path]


def test_save_config_es_atomico_y_no_deja_temporales(tmp_path):
    """Se escribe en un temporal y se renombra: el destino nunca está a medias."""
    path = tmp_path / "config.json"

    config_store.save_config({"lan": True}, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"lan": True}
    assert list(tmp_path.iterdir()) == [path]


def test_un_fallo_al_renombrar_conserva_la_preferencia_anterior(tmp_path, monkeypatch):
    """Un corte a mitad no puede dejar el fichero sin preferencia ni basura.

    Importa por el fail-closed: un `config.json` truncado se leería como «sin
    preferencia» y **cerraría** el modo que el usuario había dejado activo.
    """
    path = tmp_path / "config.json"
    config_store.save_config({"lan": True}, path)

    def _renombrado_imposible(*args, **kwargs):
        raise OSError("renombrado imposible")

    monkeypatch.setattr(config_store.os, "replace", _renombrado_imposible)

    config_store.save_config({"lan": False}, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"lan": True}
    assert not (tmp_path / "config.json.tmp").exists()
