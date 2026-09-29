"""Tests de la búsqueda dirigida del diccionario (V3.91, fase 1).

El incremento retira el O(N) de la caché de consulta: la inversa ES→EN ya no
volca la tabla entera para recorrerla en Python, y los peldaños de recall ya no
leen la caché global para encontrar la fila que ya sabían nombrar.

Lo que se fija aquí es que ese cambio **no cambia nada de lo que el alumno ve**:

1. **Equivalencia con el volcado completo.** `list_entries()` se conserva como
   REFERENCIA y los tests comprueban que la consulta dirigida produce, tras el
   matcher puro, exactamente lo mismo. La propiedad que se explota es que el
   índice es un SUPERCONJUNTO de candidatos: si filtrara de más, faltarían
   respuestas; si filtra de más poco, el matcher descarta.
2. **Degradación declarada.** Sin FTS5 (build de Python sin la extensión) la
   consulta se repliega a `LIKE` y el resultado tiene que ser el mismo. Se
   comprueba con la sonda forzada y con el índice BORRADO, para que el test no
   pueda pasar por accidente usando FTS5.
3. **Migración aditiva sobre una BD anterior.** Se construye una base con el
   esquema de V3.90 (sin columna plegada, sin índice) y se comprueba que
   `init_db()` la abre, la rellena y la indexa.
4. **Los caminos de producción no vuelcan la tabla.** Con `list_entries`
   envenenado (lanza si se llama) los cuatro caminos que la usaban —MCQ de
   reconocimiento, sus dos peldaños de recall, la disponibilidad por palabra y la
   inversa ES→EN— siguen funcionando.
"""

import asyncio
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from domain import review as review_domain
from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from services import dictionary_content, dictionary_mcq, dictionary_reverse

# Términos de la prueba de equivalencia. Incluye a propósito los casos que el
# matcher distingue: glosa múltiple, paréntesis, acentos, eñe, una palabra que
# CONTIENE el término y una locución.
_TERMS = (
    "casa",
    "casa de campo",
    "banco",
    "año",
    "ano",
    "camión",
    "cafe",
    "café",
    "tornillo",
    "lima",
    "no existe",
)

_SEED = (
    ("house", "noun", "a building", "casa, hogar"),
    ("farmhouse", "noun", "a farm house", "casa de campo, granja"),
    ("casamiento", "noun", "a wedding", "casamiento"),
    ("bank", "noun", "a financial institution", "banco, orilla"),
    ("bench", "noun", "a long seat", "banco (asiento)"),
    ("year", "noun", "twelve months", "año"),
    ("anon", "noun", "soon", "ano"),
    ("truck", "noun", "a lorry", "camión"),
    ("cafe", "noun", "a coffee shop", "café"),
    ("screw", "noun", "a fastener", "tornillo"),
    ("file", "noun", "a tool", "lima"),
    ("lime", "noun", "a fruit", "lima (fruta)"),
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


@pytest.fixture(autouse=True)
def _clear_generation_state():
    """Limpia el estado global de generación (vuelos, negative cache, cupos)."""
    vocabulary_domain._clear_generation_state()
    yield
    vocabulary_domain._clear_generation_state()


def _seed_direct_cache() -> None:
    for word, pos, definition, translation in _SEED:
        assert dictionary_repo.save_entry(
            word,
            pos=pos,
            definition=definition,
            translation=translation,
            generator_version=dictionary_content.GENERATOR_VERSION,
        )


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


# --- phrase_query (puro) ------------------------------------------------------


def test_phrase_query_quotes_every_token():
    assert dictionary_reverse.phrase_query("casa de campo") == '"casa" "de" "campo"'


def test_phrase_query_folds_accents_but_keeps_ene():
    assert dictionary_reverse.phrase_query("Camión") == '"camion"'
    assert dictionary_reverse.phrase_query("AÑO") == '"año"'
    assert dictionary_reverse.phrase_query("ano") == '"ano"'


def test_phrase_query_drops_punctuation_and_empty_terms():
    assert dictionary_reverse.phrase_query("casa, hogar") == '"casa" "hogar"'
    assert dictionary_reverse.phrase_query("banco (dinero)") == '"banco" "dinero"'
    assert dictionary_reverse.phrase_query("…") == ""
    assert dictionary_reverse.phrase_query("") == ""


# --- sonda de FTS5 ------------------------------------------------------------


def test_probe_reports_boolean_and_is_cached(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert isinstance(db.fts5_available(), bool)
    # La sonda se paga UNA vez: el segundo acceso no vuelve a crear la tabla.
    assert db.fts5_available() is db.fts5_available()


# --- migración -----------------------------------------------------------------


def test_migration_adds_folded_column_and_indexes_a_v390_database(
    monkeypatch, tmp_path
):
    """Una BD de V3.90 (sin columna plegada ni índice) se abre y queda indexada."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE dictionary_entries (
            word TEXT PRIMARY KEY,
            pos TEXT NOT NULL DEFAULT '',
            definition TEXT NOT NULL DEFAULT '',
            translation TEXT NOT NULL DEFAULT '',
            situation TEXT NOT NULL DEFAULT '',
            senses_json TEXT NOT NULL DEFAULT '',
            meanings_json TEXT NOT NULL DEFAULT '',
            generator_version TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "INSERT INTO dictionary_entries "
        "(word, pos, definition, translation, generator_version, created_at) "
        "VALUES ('house', 'noun', 'a building', 'Casa, Hogar', '1.6.0', 'x')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    db.init_db()

    stored = dictionary_repo.get_entry("house")
    assert stored is not None
    with db._conn() as check:
        folded = check.execute(
            "SELECT translation_fold FROM dictionary_entries WHERE word = 'house'"
        ).fetchone()[0]
    # Plegado con la MISMA función del matcher: minúsculas y sin acentos.
    assert folded == dictionary_reverse.fold("Casa, Hogar")
    # Y la fila VIEJA ya se encuentra por la consulta dirigida.
    assert [entry["word"] for entry in dictionary_repo.find_by_translation("casa")] == [
        "house"
    ]


def test_index_is_rebuilt_when_it_does_not_match_the_table(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    assert db.fts5_available() is True
    # Desincronización deliberada: se inserta sin disparador (como haría una
    # escritura hecha con el índice a medias) y el arranque tiene que repararlo.
    with db._conn() as conn:
        conn.execute("DROP TRIGGER dictionary_entries_fts_insert")
        conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, translation, translation_fold, created_at) "
            "VALUES ('manual', 'casa', ? , 'x')",
            (dictionary_reverse.fold("casa"),),
        )
    db.init_db()
    with db._conn() as conn:
        indexed = conn.execute(
            f"SELECT count(*) FROM {db.DICTIONARY_FTS_TABLE}"
        ).fetchone()[0]
        total = conn.execute("SELECT count(*) FROM dictionary_entries").fetchone()[0]
    assert indexed == total
    assert "manual" in [
        entry["word"] for entry in dictionary_repo.find_by_translation("casa")
    ]


# --- consulta dirigida: equivalencia con el volcado completo ------------------


@pytest.mark.parametrize("term", _TERMS)
def test_find_by_translation_matches_the_full_dump(monkeypatch, tmp_path, term):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    assert db.fts5_available() is True

    targeted = dictionary_repo.find_by_translation(term)
    assert len(targeted) <= dictionary_repo._CANDIDATE_LIMIT
    assert dictionary_reverse.match_translation(
        term, targeted
    ) == dictionary_reverse.match_translation(term, dictionary_repo.list_entries())


@pytest.mark.parametrize("term", _TERMS)
def test_find_by_translation_like_fallback_matches_the_full_dump(
    monkeypatch, tmp_path, term
):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    # La sonda se fuerza a "sin FTS5" y el índice se BORRA: así el repliegue no
    # puede pasar el test por accidente usando el índice.
    monkeypatch.setattr(db, "_FTS5_AVAILABLE", False)
    with db._conn() as conn:
        conn.execute(f"DROP TABLE {db.DICTIONARY_FTS_TABLE}")
    assert db.fts5_available() is False

    targeted = dictionary_repo.find_by_translation(term)
    assert len(targeted) <= dictionary_repo._CANDIDATE_LIMIT
    assert dictionary_reverse.match_translation(
        term, targeted
    ) == dictionary_reverse.match_translation(term, dictionary_repo.list_entries())


@pytest.mark.parametrize(
    "term",
    ('casa" OR "banco', "casa*", "casa AND banco", "casa%", "casa_", "casa OR zzz"),
)
def test_adversarial_terms_cannot_inject_fts_operators(monkeypatch, tmp_path, term):
    """Un término del alumno es TEXTO: no puede actuar de operador ni de comodín."""
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    targeted = dictionary_repo.find_by_translation(term)
    assert dictionary_reverse.match_translation(
        term, targeted
    ) == dictionary_reverse.match_translation(term, dictionary_repo.list_entries())


def test_find_by_words_is_case_insensitive_and_ignores_missing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    found = dictionary_repo.find_by_words(["BANK", "  house ", "no-existe", ""])
    assert [entry["word"] for entry in found] == ["bank", "house"]


def test_distractor_pool_keeps_the_mcq_options_identical(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    full_dump = dictionary_repo.list_entries()
    for word in ("bank", "house", "file"):
        pool = dictionary_repo.distractor_pool(word)
        assert pool[0]["word"] == word
        assert len(pool) <= 1 + 2 * dictionary_repo._POOL_LIMIT
        for seed in ("", "nonce-1", "nonce-2"):
            assert dictionary_mcq.recognition_options_for(
                word, pool, seed=seed
            ) == dictionary_mcq.recognition_options_for(word, full_dump, seed=seed)


def test_distractor_pool_mirrors_the_mcq_bands_of_a_target_without_pos(
    monkeypatch, tmp_path
):
    """Sin `pos` en la diana no hay franja «del mismo pos»: todo va en una sola.

    Es la parte del helper puro fácil de reproducir mal: una entrada SIN `pos` no
    es «del mismo `pos`» que otra entrada sin `pos`. Si la consulta las separara
    en dos franjas, el ORDEN de los primeros candidatos cambiaría y la misma
    palabra devolvería otros tres distractores.
    """
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    for word, translation in (("blank", "blanco"), ("zeta", "zed"), ("alpha", "alfa")):
        dictionary_repo.save_entry(
            word,
            pos="",
            definition=f"definition of {word}",
            translation=translation,
            generator_version=dictionary_content.GENERATOR_VERSION,
        )
    full_dump = dictionary_repo.list_entries()
    pool = dictionary_repo.distractor_pool("blank")
    assert pool[0]["word"] == "blank"
    for seed in ("", "nonce-1", "nonce-2"):
        assert dictionary_mcq.recognition_options_for(
            "blank", pool, seed=seed
        ) == dictionary_mcq.recognition_options_for("blank", full_dump, seed=seed)


def test_index_follows_updates_and_deletes(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    # Actualización (mismo camino que la regeneración de caché: ON CONFLICT).
    dictionary_repo.save_entry(
        "house",
        pos="noun",
        definition="a building",
        translation="vivienda",
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    assert "house" not in [
        entry["word"] for entry in dictionary_repo.find_by_translation("hogar")
    ]
    assert "house" in [
        entry["word"] for entry in dictionary_repo.find_by_translation("vivienda")
    ]
    with db._conn() as conn:
        conn.execute("DELETE FROM dictionary_entries WHERE word = 'house'")
    assert dictionary_repo.find_by_translation("vivienda") == []


# --- los caminos de producción NO volcan la tabla -----------------------------


def _poison_list_entries(monkeypatch):
    def _explode(*_args, **_kwargs):
        raise AssertionError(
            "un camino de producción volvió a volcar dictionary_entries"
        )

    monkeypatch.setattr(dictionary_repo, "list_entries", _explode)


def test_recognition_and_recall_do_not_dump_the_cache(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    _poison_list_entries(monkeypatch)
    with TestClient(app) as client:
        recognition = client.get(
            f"/api/vocabulary/drill/recognition?user_id={uid}&word=bank"
        )
        assert recognition.status_code == 200, recognition.text
        question = recognition.json()
        assert question["available"] is True
        scored = client.post(
            f"/api/vocabulary/drill/recognition-attempt?user_id={uid}",
            json={
                "word": "bank",
                "selected_index": 0,
                "question_id": question["question_id"],
            },
        )
        assert scored.status_code == 200, scored.text

        recall = client.get(
            f"/api/vocabulary/drill/recall?user_id={uid}&word=bank"
        )
        assert recall.status_code == 200, recall.text
        assert recall.json()["available"] is True
        answer = client.post(
            f"/api/vocabulary/drill/recall-attempt?user_id={uid}",
            json={"word": "bank", "answer": "bank"},
        )
        assert answer.status_code == 200, answer.text


def test_available_recall_cues_does_not_dump_the_cache(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    _poison_list_entries(monkeypatch)
    cues = asyncio.run(review_domain._available_recall_cues(["bank", "house"]))
    assert cues["bank"], "la palabra cacheada tiene que declarar algún peldaño"
    assert cues["house"]


def test_reverse_lookup_does_not_dump_the_cache(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_direct_cache()
    _poison_list_entries(monkeypatch)
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": "casa", "direction": "es-en"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    # La inversa instantánea sale de la traducción cacheada («casa, hogar»).
    assert data["word"] == "casa"
    assert data["translation"] == "house"
    assert isinstance(data["alternatives"], list)


# --- sonda de volumen: el coste deja de crecer con la tabla -------------------


def _seed_bulk(rows: int) -> None:
    """Inserta `rows` filas de caché sintéticas SIN pasar por el modelo.

    Va directo a la BD a propósito (es una sonda de volumen, no de contenido):
    los datos son inventados y feos, pero el índice se mantiene por disparador
    igual que con `save_entry`.
    """
    now = db._now()
    payload = [
        (
            f"word{i:05d}",
            "noun",
            f"definition number {i}",
            f"gloss {i}, generic",
            dictionary_reverse.fold(f"gloss {i}, generic"),
            now,
            now,
        )
        for i in range(rows)
    ]
    with db._conn() as conn:
        conn.executemany(
            "INSERT INTO dictionary_entries "
            "(word, pos, definition, translation, translation_fold, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            payload,
        )


def test_targeted_query_does_not_scale_with_the_cache(monkeypatch, tmp_path):
    """Con 4.000 filas: la dirigida materializa unas pocas y el volcado, todas."""
    _setup(monkeypatch, tmp_path)
    _seed_bulk(4000)
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO dictionary_entries "
            "(word, translation, translation_fold, created_at) "
            "VALUES ('needle', 'casa, hogar', ?, 'x')",
            (dictionary_reverse.fold("casa, hogar"),),
        )

    targeted = dictionary_repo.find_by_translation("casa")
    assert [entry["word"] for entry in targeted] == ["needle"]
    assert len(targeted) <= dictionary_repo._CANDIDATE_LIMIT
    assert len(dictionary_repo.list_entries()) == 4001

    # Sonda de reloj con margen ancho: no se afirma un número, se afirma que el
    # coste dejó de crecer con la tabla. Si el volcado sale por debajo de 5 ms la
    # comparación no dice nada y no se hace.
    linear_ms = _median_ms(lambda: dictionary_reverse.match_translation(
        "casa", dictionary_repo.list_entries()
    ))
    if linear_ms >= 5.0:
        targeted_ms = _median_ms(
            lambda: dictionary_reverse.match_translation(
                "casa", dictionary_repo.find_by_translation("casa")
            )
        )
        assert targeted_ms * 5 < linear_ms, (targeted_ms, linear_ms)


def _median_ms(operation, repeats: int = 5) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return samples[len(samples) // 2]


# --- no-regresión del contrato que ya existía ---------------------------------


def test_meanings_and_senses_still_round_trip(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    meanings = [
        {
            "term": "banco",
            "pos": "noun",
            "gloss": "asiento",
            "domain": "furniture",
            "proper_noun": False,
        }
    ]
    senses = [{"pos": "noun", "gloss": "a seat"}]
    dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="a long seat",
        translation="banco",
        senses=senses,
        meanings=meanings,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    stored = dictionary_repo.get_entry("bank")
    assert stored is not None
    assert stored["senses"] == senses
    assert stored["meanings"] == meanings
    # La consulta dirigida devuelve la fila COMPLETA, con su JSON decodificado.
    assert dictionary_repo.find_by_translation("banco")[0]["meanings"] == meanings
    assert json.loads(
        json.dumps(dictionary_repo.distractor_pool("bank")[0]["senses"])
    ) == senses
