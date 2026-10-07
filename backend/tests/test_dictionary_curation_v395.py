"""Curación manual del diccionario (V3.95.0).

Verifica la autoridad MÁS alta de la consulta: una corrección del webmaster
(`dictionary_curated`) manda sobre el glosario, los packs, la caché del modelo y
el guardarraíl, en las DOS direcciones, y se identifica por una clave normalizada
con la misma normalización que la consulta.

También fija el candado: sin PIN de administración no se cura nada.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import config
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from services import dictionary_content

_ADMIN_PIN = "test-pin"
_ADMIN_HEADERS = {"X-Admin-Pin": _ADMIN_PIN}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    monkeypatch.setenv(config.ADMIN_PIN_ENV, _ADMIN_PIN)
    return users_repo.create_user("A")["id"]


def _lookup(uid: str, word: str, direction: str = "en-es") -> dict:
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": word, "direction": direction},
        )
        assert res.status_code == 200, res.text
        return res.json()


def _curate(payload: dict, *, expect: int = 200) -> dict:
    with TestClient(app) as client:
        res = client.put(
            "/api/admin/dictionary/curated", json=payload, headers=_ADMIN_HEADERS
        )
        assert res.status_code == expect, res.text
        return res.json()


def _seed_direct(word: str, translation: str, definition: str = "A meaning.") -> None:
    dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=definition,
        translation=translation,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )


def test_curated_reverse_override_beats_the_glossary(monkeypatch, tmp_path):
    """Una corrección ES→EN manda sobre el equivalente por defecto del glosario."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_direct("drill", "broca", definition="A drilling tool.")

    # El glosario por defecto da «drill bit»; el webmaster fuerza «drill».
    _curate(
        {
            "direction": "es-en",
            "word": "broca",
            "translation": "drill",
            "pos": "noun",
            "definition": "A drilling tool.",
            "note": "preferimos el término corto",
        }
    )
    data = _lookup(uid, "broca", "es-en")
    assert data["translation"] == "drill"
    assert data["meanings"][0]["term"] == "drill"


def test_curated_direct_override_serves_the_manual_translation(monkeypatch, tmp_path):
    """Una corrección EN→ES se sirve sin tocar la caché ni el modelo."""
    uid = _setup(monkeypatch, tmp_path)
    _curate(
        {
            "direction": "en-es",
            "word": "bank",
            "translation": "banco",
            "pos": "noun",
            "definition": "A financial institution.",
        }
    )
    data = _lookup(uid, "bank", "en-es")
    assert data["translation"] == "banco"
    assert data["definition"] == "A financial institution."


def test_curated_key_is_normalized(monkeypatch, tmp_path):
    """La clave se normaliza igual que la consulta: «  Broca, » cura «broca»."""
    uid = _setup(monkeypatch, tmp_path)
    saved = _curate(
        {
            "direction": "es-en",
            "word": "  Broca, ",
            "translation": "drill bit",
        }
    )
    assert saved["word"] == "broca"
    assert dictionary_repo.get_curated("es-en", "broca") is not None
    # La consulta con mayúsculas y puntuación encuentra la MISMA corrección.
    assert _lookup(uid, "BROCA.", "es-en")["translation"] == "drill bit"


def test_deleting_curation_restores_the_lower_authority(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_direct("drill bit", "broca", definition="A cutting tool.")
    _curate(
        {"direction": "es-en", "word": "broca", "translation": "auger"}
    )
    assert _lookup(uid, "broca", "es-en")["translation"] == "auger"

    with TestClient(app) as client:
        res = client.delete(
            "/api/admin/dictionary/curated/es-en/broca", headers=_ADMIN_HEADERS
        )
        assert res.status_code == 200, res.text
        assert res.json()["deleted"] is True

    # Vuelve a mandar el glosario curado.
    assert _lookup(uid, "broca", "es-en")["translation"] == "drill bit"


def test_curation_requires_the_admin_pin(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.put(
            "/api/admin/dictionary/curated",
            json={"direction": "es-en", "word": "broca", "translation": "drill bit"},
        )
    assert res.status_code in (401, 403)
