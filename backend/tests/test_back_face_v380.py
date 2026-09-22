"""Tests de la cara B editable (V3.80.0): precedencia, PATCH y aviso honesto.

La promesa de este cambio es que la cara B de una tarjeta deje de ser un callejón
sin salida. Se apoya en cuatro cosas que serían caras de descubrir en producción:

1. La precedencia está DECLARADA y se respeta: lo que escribió el alumno manda
   sobre el catálogo del pack, y el pack manda sobre la caché del diccionario.
2. Si no hay ninguna de las tres fuentes, `card_face` devuelve vacío: **no
   inventa** un reverso de relleno. Una tarjeta sin cara B es un dato.
3. `PATCH /api/vocabulary/items` corrige SOLO la fila del alumno de la sesión y
   **no crea vocabulario**: editar una traducción no es una puerta trasera al
   léxico (invariante D3).
4. La corrección llega hasta la cola de Flashcards, que es donde el alumno la
   necesita: no se queda en la tabla sin que la tarjeta la vea.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from domain import retention as retention_domain
from main import app
from repositories import collections as collections_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _count(table: str, where: str = "1=1", params=()) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
    finally:
        conn.close()


def _add_word(client: TestClient, user_id: str, word: str, **extra) -> None:
    res = client.post(
        "/api/vocabulary/items",
        params={"user_id": user_id},
        json={"word": word, **extra},
    )
    assert res.status_code == 200, res.text


def _patch_translation(
    client: TestClient, user_id: str, word: str, translation: str
):
    return client.patch(
        "/api/vocabulary/items",
        params={"user_id": user_id},
        json={"word": word, "translation": translation},
    )


# --- Precedencia declarada ---------------------------------------------------


def test_own_translation_beats_pack_and_cache(monkeypatch, tmp_path):
    """El orden es alumno → pack → caché. Se comprueba levantando cada fuente."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        # La palabra entra al léxico SIN traducción propia (el caso normal: el
        # alumno añade una palabra que ha visto, no una que ya sabe traducir).
        _add_word(client, a, "anchor")
        assert retention_domain.card_face(a, "anchor")["translation"] == ""

        # Nivel 3: solo la caché del diccionario.
        dictionary_repo.save_entry(
            "anchor", translation="ancla (caché)", definition="A device..."
        )
        assert retention_domain.card_face(a, "anchor")["translation"] == "ancla (caché)"
        # La definición viaja aparte y no la pisa nadie.
        assert retention_domain.card_face(a, "anchor")["definition"] == "A device..."

        # Nivel 2: el catálogo del pack, que es contenido curado y gana a la
        # caché generada a máquina.
        pack = collections_repo.create_user_list(a, title="Náutica")
        assert pack is not None
        collections_repo.add_items_to_collection(
            int(pack["id"]), [{"word": "anchor", "translation": "ancla (pack)"}]
        )
        assert retention_domain.card_face(a, "anchor")["translation"] == "ancla (pack)"

        # Nivel 1: lo que escribe el alumno, que manda sobre todo lo demás.
        assert _patch_translation(client, a, "anchor", "mi ancla").status_code == 200
        assert retention_domain.card_face(a, "anchor")["translation"] == "mi ancla"

        # Y borrar su corrección (cadena vacía) devuelve la precedencia al pack:
        # es una corrección legítima, no una trampa sin salida.
        assert _patch_translation(client, a, "anchor", "").status_code == 200
        assert retention_domain.card_face(a, "anchor")["translation"] == "ancla (pack)"


def test_card_face_without_any_source_stays_empty(monkeypatch, tmp_path):
    """Sin traducción en ningún sitio, la cara B queda vacía: no se inventa."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add_word(client, a, "quixotic")
        face = retention_domain.card_face(a, "quixotic")
        assert face["translation"] == ""
        assert face["definition"] == ""
        assert face["word"] == "quixotic"


def test_card_face_is_per_user(monkeypatch, tmp_path):
    """La traducción propia es de quien la escribió, no del equipo."""
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for user in (a, b):
            _add_word(client, user, "anchor")
        assert _patch_translation(client, a, "anchor", "el ancla de A").status_code == (
            200
        )

        assert retention_domain.card_face(a, "anchor")["translation"] == "el ancla de A"
        assert retention_domain.card_face(b, "anchor")["translation"] == ""


def test_corrected_translation_reaches_the_auto_deck_queue(monkeypatch, tmp_path):
    """La corrección no se queda en la tabla: la tarjeta la ve al estudiarla."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add_word(client, a, "quixotic")
        queue = client.get(
            "/api/vocabulary/decks/0/queue", params={"user_id": a}
        ).json()
        assert next(i for i in queue["items"] if i["front"] == "quixotic")["back"] == ""

        assert (
            _patch_translation(client, a, "quixotic", "quijotesco").status_code == 200
        )

        queue = client.get(
            "/api/vocabulary/decks/0/queue", params={"user_id": a}
        ).json()
        assert next(i for i in queue["items"] if i["front"] == "quixotic")[
            "back"
        ] == "quijotesco"


# --- El endpoint de edición -------------------------------------------------


def test_patch_does_not_create_vocabulary(monkeypatch, tmp_path):
    """Corregir no es dar de alta: una palabra fuera del léxico es 404 (D3)."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        before = _count("vocabulary", "user_id = ?", (a,))
        res = _patch_translation(client, a, "unseen", "nunca vista")
        assert res.status_code == 404, res.text
        assert _count("vocabulary", "user_id = ?", (a,)) == before
        # Y tampoco deja rastro en el ledger léxico.
        assert _count("vocabulary_events", "user_id = ?", (a,)) == 0


def test_patch_is_isolated_and_idempotent(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add_word(client, a, "anchor")

        # B no puede escribir en el léxico de A (ni leerlo): es 404, no un 200
        # silencioso sobre una fila ajena.
        assert _patch_translation(client, b, "anchor", "ajena").status_code == 404
        assert retention_domain.card_face(a, "anchor")["translation"] == ""

        for _ in range(2):  # idempotente: repetir el mismo valor no molesta
            res = _patch_translation(client, a, "anchor", "ancla")
            assert res.status_code == 200, res.text
            assert res.json() == {
                "word": "anchor",
                "translation": "ancla",
                "updated": True,
            }
        assert _count("vocabulary", "user_id = ? AND word = 'anchor'", (a,)) == 1


def test_patch_normalizes_case_and_spaces(monkeypatch, tmp_path):
    """La clave es la forma normalizada, como en el resto del léxico."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add_word(client, a, "anchor")
        res = _patch_translation(client, a, "  Anchor  ", "  ancla  ")
        assert res.status_code == 200, res.text
        assert res.json()["word"] == "anchor"
        assert res.json()["translation"] == "ancla"
        assert retention_domain.card_face(a, "anchor")["translation"] == "ancla"


def test_patch_rejects_overlong_translation(monkeypatch, tmp_path):
    """Acotado en longitud: 500 caracteres, no un campo libre sin fondo."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add_word(client, a, "anchor")
        assert _patch_translation(client, a, "anchor", "x" * 501).status_code == 422
        assert _patch_translation(client, a, "anchor", "x" * 500).status_code == 200


# --- Lectura desde PERSONAL -------------------------------------------------


def test_lexicon_exposes_own_translation_read_only(monkeypatch, tmp_path):
    """PERSONAL la muestra; el contrato por fila la lleva sin cambiar nada más."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add_word(client, a, "anchor", translation="ancla de entrada")
        _add_word(client, a, "quixotic")

        items = {
            i["word"]: i
            for i in client.get(
                "/api/vocabulary/lexicon", params={"user_id": a}
            ).json()["items"]
        }
        assert items["anchor"]["translation"] == "ancla de entrada"
        # Sin traducción propia el campo viaja igual, vacío: la UI no tiene que
        # distinguir «no viene» de «no hay».
        assert items["quixotic"]["translation"] == ""
