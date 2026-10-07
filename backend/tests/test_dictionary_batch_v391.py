"""Tests del lote de operador del lexicón offline (V3.91, fase 2).

Dos piezas, dos suites:

1. **La lógica pura** (`services.dictionary_batch`): limpieza de la lista de
   trabajo, mapeo de POS desde otra taxonomía, planificación con descartes
   contados y ejecución best-effort con tope de tiempo. Se prueba sin modelo y
   sin BD porque es justo lo que permite inyectarlos.
2. **La consulta de frescura** (`repositories.dictionary.fresh_entry_words`), que
   es lo que hace REANUDABLE al lote: si esa consulta no coincidiera con el
   criterio del dominio (`_content_is_fresh`), el lote volvería a generar
   palabras ya preparadas o se saltaría palabras sin contenido servible.
"""

from __future__ import annotations

import asyncio

import pytest

from domain import vocabulary as vocabulary_domain
from repositories import db
from repositories import dictionary as dictionary_repo
from services import dictionary_batch, dictionary_content


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch, tmp_path):
    """Cada test corre sobre una BD temporal: el lote escribe de verdad."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


# --- normalize_word -----------------------------------------------------------


def test_normalize_word_leaves_a_plain_word_alone():
    assert dictionary_batch.normalize_word("bank") == "bank"


def test_normalize_word_folds_case_spaces_and_edge_punctuation():
    assert dictionary_batch.normalize_word("  Bank.  ") == "bank"
    assert dictionary_batch.normalize_word('"well done"') == "well done"
    assert dictionary_batch.normalize_word("- bank -") == "bank"


def test_normalize_word_strips_the_noise_of_a_pasted_list():
    # BOM, viñeta, comillas tipográficas y espacios de no separación: lo que
    # aparece al pegar una lista desde un documento o una hoja de cálculo.
    assert dictionary_batch.normalize_word("\ufeff• Bank") == "bank"
    assert dictionary_batch.normalize_word("don\u2019t") == "don't"
    assert dictionary_batch.normalize_word("bank\u00a0") == "bank"


def test_normalize_word_rejects_what_is_not_a_word_or_short_phrase():
    assert dictionary_batch.normalize_word("") == ""
    assert dictionary_batch.normalize_word("   ") == ""
    assert dictionary_batch.normalize_word("bank2") == ""
    assert dictionary_batch.normalize_word("???") == ""
    assert dictionary_batch.normalize_word("a" * 81) == ""
    # Una locución corta SÍ es vocabulario; una frase entera no.
    assert dictionary_batch.normalize_word("look after") == "look after"


def test_normalize_word_rejects_an_accented_word_instead_of_truncating_it():
    # Regresión: recortar la puntuación de borde con una clase ASCII convertía
    # «café» en «caf» y «über» en «ber» — dos términos VÁLIDOS y distintos de los
    # que la lista pedía. El universo del lote es inglés: lo que no encaja se
    # rechaza, no se recorta a otra palabra.
    assert dictionary_batch.normalize_word("café") == ""
    assert dictionary_batch.normalize_word("über") == ""
    assert dictionary_batch.normalize_word("naïve") == ""


# --- parse_word_list ----------------------------------------------------------


def test_parse_word_list_cleans_and_keeps_the_first_order():
    text = "\n".join(
        [
            "# comentario",
            "",
            "Bank",
            "  bank  ",
            "look after",
            "12345",
            "coffee, café",
        ]
    )
    # «bank» duplicado se queda una vez; el token numérico se descarta; una línea
    # con coma se corta por la coma (formato «palabra, traducción»).
    assert dictionary_batch.parse_word_list(text) == ["bank", "look after", "coffee"]


def test_parse_word_list_accepts_semicolons_and_commas_as_separators():
    assert dictionary_batch.parse_word_list("bank; coffee, table") == [
        "bank",
        "coffee",
        "table",
    ]


# --- map_pos ------------------------------------------------------------------


def test_map_pos_translates_the_abbreviations_of_a_lexicon():
    assert dictionary_batch.map_pos("n") == "noun"
    assert dictionary_batch.map_pos("V.") == "verb"
    assert dictionary_batch.map_pos("adj") == "adjective"
    assert dictionary_batch.map_pos("adv") == "adverb"
    assert dictionary_batch.map_pos("pron") == "pronoun"
    assert dictionary_batch.map_pos("prep") == "preposition"
    assert dictionary_batch.map_pos("conj") == "conjunction"
    assert dictionary_batch.map_pos("interj") == "interjection"
    assert dictionary_batch.map_pos("art") == "determiner"
    assert dictionary_batch.map_pos("expr") == "phrase"


def test_map_pos_translates_long_names_in_both_languages():
    assert dictionary_batch.map_pos("Noun") == "noun"
    assert dictionary_batch.map_pos("sustantivo") == "noun"
    assert dictionary_batch.map_pos("adverbio") == "adverb"
    assert dictionary_batch.map_pos("preposición") == "preposition"
    assert dictionary_batch.map_pos("locución") == "phrase"


def test_map_pos_never_invents_a_category():
    assert dictionary_batch.map_pos("") == ""
    assert dictionary_batch.map_pos(None) == ""
    assert dictionary_batch.map_pos("gerundio") == ""
    assert dictionary_batch.map_pos("num") == ""


def test_map_pos_only_returns_the_taxonomy_the_engine_understands():
    # Una POS que el scoring no reconoce es una POS que la UI pinta y el motor
    # ignora: el mapeo usa la MISMA lista que el modelo, no una copia.
    assert dictionary_content.VALID_POS is dictionary_content._VALID_POS
    for raw in ("n", "v", "adj", "adv", "pron", "prep", "conj", "interj", "art", "phr"):
        assert dictionary_batch.map_pos(raw) in dictionary_content.VALID_POS


# --- clean_term ---------------------------------------------------------------


def test_clean_term_removes_unresolved_entities_and_controls():
    assert dictionary_batch.clean_term("bank&nbsp;") == "bank"
    assert dictionary_batch.clean_term("&amp;") == ""
    assert dictionary_batch.clean_term("file\t\tto\tshape") == "file to shape"
    assert dictionary_batch.clean_term("a\x00b") == "a b"


def test_clean_term_collapses_spaces_and_clamps_the_length():
    assert dictionary_batch.clean_term("  to   look   after  ") == "to look after"
    assert len(dictionary_batch.clean_term("x" * 200)) == 120
    assert len(dictionary_batch.clean_term("x " * 120)) <= 120


# --- plan_batch ---------------------------------------------------------------


def test_plan_batch_counts_invalid_duplicates_and_fresh():
    plan = dictionary_batch.plan_batch(
        ["bank", "Bank", "1234", "coffee", "bank", ""],
        fresh={"coffee"},
    )
    assert plan.universe == 6
    assert plan.invalid == 2  # el numérico y la cadena vacía
    assert plan.duplicates == 2  # «Bank» y el segundo «bank»
    assert plan.fresh == 1  # coffee
    assert plan.pending == 1
    assert plan.words == ["bank"]  # bank queda pendiente; coffee ya está fresca
    assert plan.truncated is False


def test_plan_batch_keeps_the_order_of_the_universe():
    plan = dictionary_batch.plan_batch(["zebra", "apple", "bank"])
    assert plan.words == ["zebra", "apple", "bank"]


def test_plan_batch_truncates_and_declares_what_it_leaves():
    plan = dictionary_batch.plan_batch(["a", "b", "c", "d"], limit=2)
    assert plan.words == ["a", "b"]
    assert plan.limited == 2
    assert plan.truncated is True
    assert plan.pending == 4  # el pendiente real, no el de la pasada


def test_plan_batch_with_a_limit_wider_than_the_work_is_not_truncated():
    plan = dictionary_batch.plan_batch(["a", "b"], limit=10)
    assert plan.words == ["a", "b"]
    assert plan.limited == 0
    assert plan.truncated is False


# --- estimación ---------------------------------------------------------------


def test_estimate_seconds_uses_the_measured_rhythm():
    assert dictionary_batch.estimate_seconds(100, 4.05) == pytest.approx(405)
    assert dictionary_batch.estimate_seconds(0, 4.05) == 0
    assert dictionary_batch.estimate_seconds(-5, 4.05) == 0


def test_format_duration_is_human_and_never_zero_seconds():
    assert dictionary_batch.format_duration(0) == "0 s"
    assert dictionary_batch.format_duration(48) == "48 s"
    assert dictionary_batch.format_duration(120) == "2 min"
    assert dictionary_batch.format_duration(125) == "2 min 5 s"
    assert dictionary_batch.format_duration(3600) == "1 h"
    assert dictionary_batch.format_duration(9060) == "2 h 31 min"


# --- run_batch ----------------------------------------------------------------


def _content(word: str) -> dict:
    return {
        "pos": "noun",
        "definition": f"a definition of {word}",
        "translation": f"tr-{word}",
        "situation": "",
        "senses": [],
        "meanings": [],
    }


def test_run_batch_prepares_and_persists_every_word():
    saved: dict[str, dict] = {}

    async def generate(word: str) -> dict:
        return _content(word)

    report = asyncio.run(
        dictionary_batch.run_batch(
            ["bank", "coffee"],
            generate=generate,
            persist=lambda word, content: bool(saved.setdefault(word, content)),
        )
    )

    assert report.planned == 2
    assert report.attempted == 2
    assert report.prepared == 2
    assert report.failed == 0
    assert report.remaining == 0
    assert report.stopped_early is False
    assert saved["bank"]["translation"] == "tr-bank"


def test_run_batch_survives_a_failing_word_and_keeps_going():
    async def generate(word: str) -> dict | None:
        if word == "bank":
            raise RuntimeError("modelo caído")
        return _content(word)

    prepared: list[str] = []
    report = asyncio.run(
        dictionary_batch.run_batch(
            ["bank", "coffee", "table"],
            generate=generate,
            persist=lambda word, content: bool(prepared.append(word)) or True,
        )
    )

    assert report.attempted == 3
    assert report.prepared == 2
    assert report.failed == 1
    assert report.errors == [("bank", "RuntimeError")]
    assert prepared == ["coffee", "table"]


def test_run_batch_counts_empty_and_unpersisted_content_as_failures():
    async def generate(word: str) -> dict | None:
        return None if word == "bank" else _content(word)

    report = asyncio.run(
        dictionary_batch.run_batch(
            ["bank", "coffee"],
            generate=generate,
            persist=lambda word, content: False,
        )
    )

    assert report.attempted == 2
    assert report.prepared == 0
    assert report.failed == 2
    assert report.errors == [("bank", "empty"), ("coffee", "not_persisted")]


def test_run_batch_declares_a_persistence_failure_with_its_reason():
    async def generate(word: str) -> dict:
        return _content(word)

    def persist(word: str, content: dict) -> bool:
        raise OSError("base de datos de solo lectura")

    report = asyncio.run(
        dictionary_batch.run_batch(["bank"], generate=generate, persist=persist)
    )

    assert report.failed == 1
    assert report.errors == [("bank", "persist:OSError")]


def test_run_batch_stops_at_the_time_budget_without_leaving_the_word_halfway():
    ticks = iter(range(0, 1000, 10))

    async def generate(word: str) -> dict:
        return _content(word)

    report = asyncio.run(
        dictionary_batch.run_batch(
            ["a", "b", "c", "d", "e"],
            generate=generate,
            persist=lambda word, content: True,
            max_seconds=25,
            clock=lambda: next(ticks),
        )
    )

    # El tope se comprueba ANTES de cada palabra: se para en un límite de palabra.
    assert report.attempted == 3
    assert report.prepared == 3
    assert report.stopped_early is True
    assert report.remaining == 2


def test_run_batch_reports_progress_and_finishes_with_a_snapshot():
    async def generate(word: str) -> dict:
        return _content(word)

    snapshots: list[int] = []

    asyncio.run(
        dictionary_batch.run_batch(
            ["a", "b", "c"],
            generate=generate,
            persist=lambda word, content: True,
            progress_every=2,
            on_progress=lambda report: snapshots.append(report.prepared),
        )
    )

    # Progreso tras la 2.ª palabra y el snapshot final (con las 3 preparadas).
    assert snapshots == [2, 3]


def test_run_batch_report_is_json_serializable():
    async def generate(word: str) -> dict:
        return _content(word)

    report = asyncio.run(
        dictionary_batch.run_batch(
            ["bank"],
            generate=generate,
            persist=lambda word, content: True,
        )
    )
    payload = report.as_dict()
    assert payload["prepared"] == 1
    assert payload["errors"] == []


# --- fresh_entry_words (reanudación) ------------------------------------------


def test_fresh_entry_words_matches_the_domain_criterion():
    version = dictionary_content.GENERATOR_VERSION
    dictionary_repo.save_entry(
        "bank", definition="a place for money", generator_version=version
    )
    # Versión vigente pero SIN definición: no es contenido servible, así que el
    # dominio la trata como no fresca y el lote tiene que reintentarla.
    dictionary_repo.save_entry(
        "coffee", definition="   ", generator_version=version
    )
    # Definición buena pero de una versión anterior: se regenera.
    dictionary_repo.save_entry(
        "table", definition="furniture", generator_version="1.6.0"
    )

    fresh = dictionary_repo.fresh_entry_words(
        ["bank", "coffee", "table", "absent"], version=version
    )

    assert fresh == {"bank"}

    # Y la consulta SQL coincide con el criterio del DOMINIO palabra por palabra:
    # si divergieran, el lote regeneraría lo ya servible o se saltaría lo que la
    # consulta degrada a `definition_source="none"`.
    for word in ("bank", "coffee", "table", "absent"):
        in_domain = vocabulary_domain._content_is_fresh(
            dictionary_repo.get_entry(word)
        )
        assert (word in fresh) is in_domain


def test_fresh_entry_words_chunks_a_long_list_without_asking_for_the_whole_table():
    version = dictionary_content.GENERATOR_VERSION
    words = [f"word{i}" for i in range(500)]
    for word in words[:450]:
        dictionary_repo.save_entry(word, definition="x", generator_version=version)
    # Ruido que NO se pregunta: no puede colarse en la respuesta.
    dictionary_repo.save_entry("unrelated", definition="y", generator_version=version)

    fresh = dictionary_repo.fresh_entry_words(words, version=version)

    assert len(fresh) == 450
    assert "unrelated" not in fresh


# --- V3.95.0: normalización española y lote ES→EN ------------------------------


def test_normalize_term_es_keeps_accents_and_ene():
    # A diferencia del inglés, la inversa NO pliega acentos ni la eñe: son claves
    # distintas, no variantes.
    assert dictionary_batch.normalize_term_es("  Camión.  ") == "camión"
    assert dictionary_batch.normalize_term_es("Mañana") == "mañana"
    assert dictionary_batch.normalize_term_es("pingüino") == "pingüino"
    assert dictionary_batch.normalize_term_es("broca") == "broca"
    # El inglés, en cambio, rechaza un término acentuado (no es su alfabeto).
    assert dictionary_batch.normalize_word("camión") == ""
    assert dictionary_batch.normalize_term_es("") == ""
    assert dictionary_batch.normalize_term_es("¡¿?") == ""


def test_plan_batch_can_use_the_spanish_normalizer():
    """El lote inverso no puede descartar los acentos por usar el normalizador inglés."""
    plan = dictionary_batch.plan_batch(
        ["camión", "mañana", "Bank", "camion"],
        normalize=dictionary_batch.normalize_term_es,
    )
    # «camión» y «mañana» sobreviven; «camion» (sin tilde) es OTRA clave y también
    # entra; «Bank» se minusculiza.
    assert set(plan.words) == {"camión", "mañana", "bank", "camion"}
    assert plan.invalid == 0


def test_fresh_reverse_entry_words_matches_the_reverse_cache():
    version = dictionary_content.GENERATOR_VERSION
    dictionary_repo.save_reverse_entry(
        "casa", english="house", definition="x", generator_version=version
    )
    # Versión vigente pero sin equivalente inglés: no es servible.
    dictionary_repo.save_reverse_entry(
        "perro", english="   ", definition="x", generator_version=version
    )
    # Equivalente bueno pero de versión anterior: se regenera.
    dictionary_repo.save_reverse_entry(
        "gato", english="cat", definition="x", generator_version="1.6.0"
    )

    fresh = dictionary_repo.fresh_reverse_entry_words(
        ["casa", "perro", "gato", "ausente"], version=version
    )

    assert fresh == {"casa"}
