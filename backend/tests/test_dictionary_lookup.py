"""Tests del diccionario de consulta (V3.30).

Cubre la marca de uso/aprendizaje (solo lectura, D3), la frase de ejemplo
determinista del banco, la normalización de la búsqueda y el contrato del
endpoint `POST /api/vocabulary/dictionary`. La caché `dictionary_entries` está
vacía en todas estas pruebas (el generador de contenido —Fase B— se aísla con
un fetcher caído: `definition_source="none"`). Los tests del generador y de la
persistencia de caché viven en `test_dictionary_content_v330.py`.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_content, example_sentences


@pytest.fixture(autouse=True)
def _no_generator(monkeypatch):
    """Aísla las consultas del modelo local: el generador cae al instante.

    Sin este aislamiento, una consulta sin entrada en la caché intentaría
    llamar a Ollama y el test dependería de la red. Con el fetcher caído el
    flujo degrada a `definition_source="none"` de forma determinista.
    """

    async def _offline(_word: str, _model: str | None) -> str:
        raise dictionary_content.ContentUnavailableError("test: sin modelo")

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _offline)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _lookup(uid: str, word: str) -> dict:
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": word},
        )
        assert res.status_code == 200, res.text
        return res.json()


# --- example_sentences (puro) -------------------------------------------------


def test_example_for_returns_real_phrase_from_bank():
    entry = example_sentences.example_for("coffee")
    assert entry is not None
    assert entry["source"] == "pronunciation_corpus"
    assert "coffee" in entry["phrase"].lower()


def test_example_for_never_returns_template():
    # "flabbergasted" no está en el banco oficial de read-aloud A1-C2: el
    # diccionario debe devolver None (el micro-drill sí tiene plantilla, pero
    # aquí no es un ejemplo válido).
    assert example_sentences.example_for("flabbergasted") is None


def test_example_for_matches_with_punctuation():
    entry = example_sentences.example_for("Coffee")
    assert entry is not None
    assert "coffee" in entry["phrase"].lower()


# --- normalización -----------------------------------------------------------


def test_lookup_normalizes_case_and_padding(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = _lookup(a, "  Coffee,  ")
    assert data["word"] == "coffee"


def test_lookup_keeps_phrase_collapsed(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = _lookup(a, "   LIVING    ROOM   ")
    assert data["word"] == "living room"


def test_lookup_punctuation_only_is_422(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "…"},
        )
        assert res.status_code == 422


def test_lookup_word_too_long_is_422(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "x" * 81},
        )
        assert res.status_code == 422


# --- marca de uso (solo lectura, D3) ------------------------------------------


def test_lookup_tracked_word_returns_surface_usage(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True

    data = _lookup(a, "cat")

    assert data["definition_source"] == "none"
    assert data["definition"] is None
    usage = data["usage"]
    assert usage["tracked"] is True
    assert usage["surface"] is not None
    # Producida 1 vez en 1 día: mastery bajo (0.29) -> recall bajo el umbral,
    # el mismo resultado determinista que `get_lexicon` (services/lexicon.py).
    assert usage["surface"]["status"] == "weak"
    assert usage["surface"]["production_count"] == 1
    assert usage["surface"]["exposure_count"] == 0
    # Forma == unidad canónica sin lemma: no hay dato extra de unidad.
    assert usage["unit"] is None
    # Kind/cefr: fila de usuario sin contexto curricular.
    assert data["kind"] == "word"
    assert data["cefr"] == ""


def test_lookup_new_word_is_tracked_false(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = _lookup(a, "nebula")
    usage = data["usage"]
    assert usage["tracked"] is False
    assert usage["surface"] is None
    assert usage["unit"] is None
    assert data["cefr"] == ""
    assert data["definition_source"] == "none"


def test_lookup_is_read_only_no_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    before_vocab = _count_rows("vocabulary")
    before_events = _count_rows("vocabulary_events")
    before_cache = _count_rows("dictionary_entries")

    _lookup(a, "cat")

    assert _count_rows("vocabulary") == before_vocab
    assert _count_rows("vocabulary_events") == before_events
    # El generador está caído en esta suite: sin contenido no se escribe caché.
    # La escritura (`INSERT OR IGNORE`) se prueba en test_dictionary_content_v330.py.
    assert _count_rows("dictionary_entries") == before_cache == 0


def test_lookup_aggregates_unit_when_surface_missing(monkeypatch, tmp_path):
    """Buscar la unidad canónica sin fila de forma exacta muestra el agregado.

    Se siembra la fila `goes` (lemma `go`): su `lexical_unit` es `go`, pero no
    existe una fila con `word == "go"`. Al buscar "go" la marca de uso viene del
    agregado por unidad."""
    a, _b = _setup(monkeypatch, tmp_path)
    assert (
        vocabulary_repo.seed_curriculum_items(
            a,
            [
                {
                    "word": "goes",
                    "lemma": "go",
                    "cefr": "A1",
                    "level_id": "a1",
                    "objective_id": "a1-o1",
                    "kind": "word",
                }
            ],
        )
        is True
    )
    assert vocabulary_repo.record_words(a, ["goes"]) is True

    data = _lookup(a, "go")
    usage = data["usage"]
    assert usage["tracked"] is True
    assert usage["surface"] is None
    assert usage["unit"] is not None
    assert usage["unit"]["lexical_unit"] == "go"
    assert usage["unit"]["surface_count"] == 1
    assert usage["unit"]["produced"] is True


def test_lookup_unit_isolation_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    # B nunca ha visto la palabra.
    data_a = _lookup(a, "cat")
    data_b = _lookup(b, "cat")
    assert data_a["usage"]["tracked"] is True
    assert data_b["usage"]["tracked"] is False
    # El contenido del diccionario es global: aun sin generador (Fase B) ambos
    # leen la misma caché vacía.
    assert data_a["definition_source"] == data_b["definition_source"] == "none"


# --- ejemplo en la respuesta --------------------------------------------------


def test_lookup_includes_deterministic_example(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = _lookup(a, "coffee")
    assert data["example"] is not None
    assert data["example"]["source"] == "pronunciation_corpus"
    assert "coffee" in data["example"]["phrase"].lower()


def test_lookup_without_example_returns_null(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    data = _lookup(a, "flabbergasted")
    assert data["example"] is None
