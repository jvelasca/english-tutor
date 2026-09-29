"""V3.92 (integración pedagógica): la acepción elegida viaja con el alta.

El circuito empieza en el diccionario: el alumno busca `lima`, elige un
significado y lo añade a su léxico. Hasta V3.91 esa elección decidía la palabra y
su reverso, pero el POR QUÉ (qué acepción) se perdía: la práctica y el repaso no
podían distinguir un sentido de otro.

Aquí se fija el contrato de esa pieza:

- la acepción viaja en el alta (`sense`) y se persiste con la palabra;
- se expone en el lexicón (`sense`) para que la UI pueda decir con qué
  significado se aprendió, y `None` cuando no consta (nunca un `{}` fingido);
- una decisión nueva MANDA (pisa la anterior) y un vacío NO borra la que había;
- campos ajenos o gigantes no llegan a la BD: la lista de campos es cerrada.
"""
from sqlite3 import connect

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _add(client: TestClient, user_id: str, word: str, **extra):
    return client.post(
        "/api/vocabulary/items",
        params={"user_id": user_id},
        json={"word": word, **extra},
    )


def _lexicon_item(client: TestClient, user_id: str, word: str) -> dict:
    body = client.get("/api/vocabulary/lexicon", params={"user_id": user_id}).json()
    for item in body["items"]:
        if item["word"] == word:
            return item
    raise AssertionError(f"{word} no está en el lexicón")


def _raw_sense_json(user_id: str, word: str) -> str:
    with connect(db.DB_PATH) as conn:
        row = conn.execute(
            "SELECT sense_json FROM vocabulary WHERE user_id = ? AND word = ?",
            (user_id, word),
        ).fetchone()
    return row[0] if row else ""


# --- Alta y lectura ---------------------------------------------------------


def test_adopting_a_sense_persists_it(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = _add(
            client,
            uid,
            "bank",
            translation="banco (institución)",
            sense={
                "term": "bank",
                "pos": "noun",
                "gloss": "A place where money is kept.",
                "lemma": "bank",
                "source": "lexicon",
            },
        )
        assert res.status_code == 200, res.text
        item = _lexicon_item(client, uid, "bank")
    assert item["sense"] == {
        "term": "bank",
        "pos": "noun",
        "gloss": "A place where money is kept.",
        "lemma": "bank",
        "source": "lexicon",
        "domain": "",
    }
    # La traducción propia sigue siendo la del reverso de la tarjeta.
    assert item["translation"] == "banco (institución)"


def test_word_without_sense_reads_as_none(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(client, uid, "anchor")
        item = _lexicon_item(client, uid, "anchor")
    assert item["sense"] is None


def test_empty_sense_is_not_persisted(monkeypatch, tmp_path):
    """Un `sense` sin campos útiles NO se guarda como `'{}'`: «no consta» y
    «consta vacío» no son lo mismo."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(client, uid, "anchor", sense={"pos": "", "gloss": ""})
        item = _lexicon_item(client, uid, "anchor")
    assert item["sense"] is None
    assert _raw_sense_json(uid, "anchor") == ""


def test_unknown_sense_fields_never_reach_the_database(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(
            client,
            uid,
            "bank",
            sense={"pos": "noun", "gloss": "A place for money.", "hack": "x" * 500},
        )
        item = _lexicon_item(client, uid, "bank")
    assert "hack" not in item["sense"]
    assert "hack" not in _raw_sense_json(uid, "bank")


def test_oversized_sense_field_is_rejected_by_the_api(monkeypatch, tmp_path):
    """La validación de forma es la PRIMERA barrera: una glosa de 400 caracteres no
    entra por el contrato (el almacén, además, vuelve a recortar)."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = _add(client, uid, "bank", sense={"pos": "noun", "gloss": "g" * 400})
    assert res.status_code == 422


def test_repository_truncates_sense_fields(monkeypatch, tmp_path):
    """Segunda barrera: aunque el llamador no sea el router, el repositorio recorta.
    La validación de forma no es la del almacén."""
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_study_items(
        uid,
        [{"word": "bank", "gloss": "", "sense": {"pos": "noun", "gloss": "g" * 400}}],
        source="user",
    )
    rows = vocabulary_repo.get_vocabulary(uid)
    assert len(rows[0]["sense"]["gloss"]) == 300


# --- Precedencia entre decisiones -------------------------------------------


def test_new_sense_overrides_the_previous_one(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(client, uid, "bank", sense={"pos": "noun", "gloss": "river side"})
        _add(client, uid, "bank", sense={"pos": "noun", "gloss": "financial place"})
        item = _lexicon_item(client, uid, "bank")
    assert item["sense"]["gloss"] == "financial place"


def test_empty_sense_does_not_erase_the_previous_one(monkeypatch, tmp_path):
    """Elegir «no consta» no es una decisión: no puede borrar la que había."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(client, uid, "bank", sense={"pos": "noun", "gloss": "river side"})
        _add(client, uid, "bank")
        item = _lexicon_item(client, uid, "bank")
    assert item["sense"]["gloss"] == "river side"


def test_lista_pegada_sin_acepcion_no_la_borra(monkeypatch, tmp_path):
    """El canal masivo (`bulk`) tampoco declara acepción: no debe pisar la del
    diccionario."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(client, uid, "bank", sense={"pos": "noun", "gloss": "river side"})
        res = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": uid},
            json={"text": "bank,banco\nriver,río"},
        )
        assert res.status_code == 200, res.text
        item = _lexicon_item(client, uid, "bank")
    assert item["sense"]["gloss"] == "river side"


# --- Repositorio (unidad de la pieza) ---------------------------------------


def test_repository_reads_a_corrupted_sense_as_not_declared(monkeypatch, tmp_path):
    """Una fila con JSON ilegible no puede esconder la palabra del alumno."""
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _add(client, uid, "anchor")
    with connect(db.DB_PATH) as conn, conn:
        conn.execute(
            "UPDATE vocabulary SET sense_json = '{no-json' "
            "WHERE user_id = ? AND word = 'anchor'",
            (uid,),
        )
    rows = vocabulary_repo.get_vocabulary(uid)
    assert [r["word"] for r in rows] == ["anchor"]
    assert rows[0]["sense"] == {}
