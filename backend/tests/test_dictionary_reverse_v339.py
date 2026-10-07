"""Tests del diccionario reversible ES→EN (V3.39).

Cubre las dos piezas de la dirección inversa:

- la búsqueda INSTANTÁNEA (`services.dictionary_reverse`, pura) sobre las
  traducciones ya cacheadas en `dictionary_entries`, y
- la GENERACIÓN ES→EN con el modelo local cuando no hay coincidencia, cacheada
  en la tabla propia `dictionary_reverse_entries`.

Invariantes del proyecto que se verifican aquí: la consulta sigue siendo SOLO
LECTURA (D3: ni `vocabulary` ni `vocabulary_events` cambian) y la caché inversa
está AISLADA de `dictionary_entries`, que es el banco de distractores del MCQ
de Recognition (`services/dictionary_mcq.py`).
"""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_content, dictionary_reverse


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


@pytest.fixture(autouse=True)
def _clear_generation_state():
    """Limpia el estado global de generación (vuelos, negative cache, cupos)."""
    vocabulary_domain._clear_generation_state()
    yield
    vocabulary_domain._clear_generation_state()


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _payload(
    english: str = "cat",
    pos: str = "noun",
    definition: str = "A small domesticated carnivorous mammal.",
    situation: str = "",
) -> str:
    return json.dumps(
        {
            "english": english,
            "pos": pos,
            "definition": definition,
            "situation": situation,
        }
    )


def _stub_reverse_fetcher(monkeypatch, payload: str, calls: list):
    async def _fake(word: str, model: str | None) -> str:
        calls.append((word, model))
        return payload

    monkeypatch.setattr(dictionary_content, "_reverse_fetcher", _fake)
    # V3.95.0: el guardarraíl de retrotraducción se APRUEBA en los tests de
    # plomería (la verificación tiene sus propios tests más abajo); sin esto la
    # generación intentaría una segunda llamada al modelo real.
    monkeypatch.setattr(
        dictionary_content, "_default_reverse_verifier", _accept_reverse_verifier
    )


def _offline_reverse_fetcher(monkeypatch, calls: list):
    async def _offline(word: str, model: str | None) -> str:
        calls.append((word, model))
        raise dictionary_content.ContentUnavailableError("test: sin modelo")

    monkeypatch.setattr(dictionary_content, "_reverse_fetcher", _offline)
    monkeypatch.setattr(
        dictionary_content, "_default_reverse_verifier", _accept_reverse_verifier
    )


async def _accept_reverse_verifier(
    _word: str, _english: str, _model: str | None
) -> bool:
    """Verificador de pruebas: siempre acepta (aísla la plomería del guardarraíl)."""
    return True


def _reverse_lookup(uid: str, word: str) -> dict:
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={uid}",
            json={"word": word, "direction": "es-en"},
        )
        assert res.status_code == 200, res.text
        return res.json()


def _seed_direct(word: str, translation: str, definition: str = "A meaning.") -> None:
    assert dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=definition,
        translation=translation,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )


# --- matcher puro ------------------------------------------------------------


def test_normalize_term_folds_accents_but_keeps_ene():
    assert dictionary_reverse.normalize_term("  Camión, ") == "camion"
    # La eñe NO se pliega: "año" y "ano" son palabras distintas.
    assert dictionary_reverse.normalize_term("Mañana") == "mañana"
    assert dictionary_reverse.fold("AÑO") == "año"
    assert dictionary_reverse.normalize_term("…") == ""


def test_match_translation_exact_and_gloss_segments():
    entries = [{"word": "cat", "translation": "gato, felino"}]
    assert dictionary_reverse.match_translation("gato", entries) == ["cat"]
    assert dictionary_reverse.match_translation("felino", entries) == ["cat"]
    assert dictionary_reverse.match_translation("perro", entries) == []


def test_match_translation_ranks_exact_before_partial():
    entries = [
        {"word": "country house", "translation": "casa de campo"},
        {"word": "house", "translation": "casa"},
    ]
    # La coincidencia EXACTA ("casa" == "casa") va antes que la parcial
    # ("casa" ~ "casa de campo").
    assert dictionary_reverse.match_translation("casa", entries) == [
        "house",
        "country house",
    ]


def test_match_translation_strips_leading_articles_and_parentheses():
    entries = [{"word": "dog", "translation": "el perro (animal)"}]
    assert dictionary_reverse.match_translation("perro", entries) == ["dog"]


def test_match_translation_is_accent_tolerant():
    entries = [{"word": "truck", "translation": "camión"}]
    assert dictionary_reverse.match_translation("camion", entries) == ["truck"]
    assert dictionary_reverse.match_translation("camión", entries) == ["truck"]


def test_match_translation_dedupes_and_ignores_empty():
    entries = [
        {"word": "home", "translation": "casa"},
        {"word": "home", "translation": "hogar, casa"},
        {"word": "", "translation": "casa"},
    ]
    assert dictionary_reverse.match_translation("casa", entries) == ["home"]
    assert dictionary_reverse.match_translation("", entries) == []


# --- inversa instantánea (sin modelo) ----------------------------------------


def test_reverse_lookup_uses_cached_translation_without_model(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato, felino", definition="A small carnivorous mammal.")
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "gato")

    assert data["direction"] == "es-en"
    assert data["word"] == "gato"
    assert data["translation"] == "cat"
    assert data["definition_source"] == "llm"
    assert data["definition"] == "A small carnivorous mammal."
    assert data["alternatives"] == []
    # La inversa instantánea no llama al modelo ni escribe caché inversa.
    assert calls == []
    assert _count_rows("dictionary_reverse_entries") == 0


def test_reverse_lookup_exposes_alternatives(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato")
    _seed_direct("kitty", "gato")
    _seed_direct("pussycat", "gato, felino")

    data = _reverse_lookup(a, "gato")

    assert data["translation"] == "cat"
    assert set(data["alternatives"]) == {"kitty", "pussycat"}


def test_reverse_lookup_tracks_english_word_usage(monkeypatch, tmp_path):
    """La marca de uso es la del EQUIVALENTE INGLÉS, no la del término español."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato")
    assert vocabulary_repo.record_words(a, ["cat"]) is True

    data = _reverse_lookup(a, "gato")

    assert data["usage"]["tracked"] is True
    assert data["usage"]["surface"]["production_count"] == 1


# --- generación ES→EN --------------------------------------------------------


def test_reverse_lookup_generates_persists_and_caches(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(
        monkeypatch,
        _payload(
            english="house",
            definition="A building where people live.",
        ),
        calls,
    )

    first = _reverse_lookup(a, "morada")

    assert first["direction"] == "es-en"
    assert first["word"] == "morada"
    assert first["translation"] == "house"
    assert first["definition"] == "A building where people live."
    assert first["definition_source"] == "llm"
    assert calls == [("morada", None)]
    assert _count_rows("dictionary_reverse_entries") == 1

    # Segunda consulta: caché fresca, sin nueva llamada al modelo.
    second = _reverse_lookup(a, "Morada")
    assert second["translation"] == "house"
    assert calls == [("morada", None)]


def test_reverse_lookup_uses_reverse_cache_even_if_direct_cache_present(
    monkeypatch, tmp_path
):
    """Sin coincidencia de traducción se genera aunque haya caché directa."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("house", "casa, hogar")
    # El término "vivienda" no aparece en ninguna traducción cacheada.
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="dwelling"), calls)

    data = _reverse_lookup(a, "vivienda")

    assert calls == [("vivienda", None)]
    assert data["translation"] == "dwelling"
    assert data["definition_source"] == "llm"


def test_reverse_lookup_degrades_when_model_unavailable(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "vivienda")

    assert data["definition_source"] == "none"
    assert data["translation"] is None
    assert data["word"] == "vivienda"
    assert calls == [("vivienda", None)]
    assert _count_rows("dictionary_reverse_entries") == 0


def test_reverse_lookup_punctuation_only_is_422(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "…", "direction": "es-en"},
        )
    assert res.status_code == 422


def test_reverse_lookup_is_read_only_no_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="house"), calls)
    before_vocab = _count_rows("vocabulary")
    before_events = _count_rows("vocabulary_events")

    _reverse_lookup(a, "morada")

    assert _count_rows("vocabulary") == before_vocab
    assert _count_rows("vocabulary_events") == before_events


def test_reverse_cache_does_not_pollute_mcq_bank(monkeypatch, tmp_path):
    """`list_entries()` (banco de distractores) sigue solo con inglés."""
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="house"), calls)

    _reverse_lookup(a, "morada")

    assert dictionary_repo.list_entries() == []
    assert len(dictionary_repo.list_reverse_entries()) == 1


def test_reverse_content_version_is_current(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    calls: list = []
    _stub_reverse_fetcher(monkeypatch, _payload(english="house"), calls)

    _reverse_lookup(a, "morada")

    stored = dictionary_repo.get_reverse_entry("morada")
    assert stored is not None
    assert stored["english"] == "house"
    assert stored["generator_version"] == dictionary_content.GENERATOR_VERSION


# --- compatibilidad de la dirección por defecto ------------------------------


def test_direction_defaults_to_en_es(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("cat", "gato")

    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "cat"},
        )
        assert res.status_code == 200, res.text
        data = res.json()

    assert data["direction"] == "en-es"
    assert data["word"] == "cat"
    assert data["translation"] == "gato"
    assert data["alternatives"] == []
    assert dictionary_repo.list_reverse_entries() == []


# --- parse_reverse_content (puro) --------------------------------------------


def test_parse_reverse_content_requires_english():
    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_reverse_content(
            json.dumps({"pos": "noun", "definition": "A meaning."})
        )


def test_parse_reverse_content_validates_definition():
    out = dictionary_content.parse_reverse_content(_payload())
    assert out["english"] == "cat"
    assert out["pos"] == "noun"
    assert out["definition"].startswith("A small")

    with pytest.raises(dictionary_content.ContentUnavailableError):
        dictionary_content.parse_reverse_content(
            json.dumps({"english": "cat", "definition": ""})
        )


def test_generate_reverse_content_uses_injected_fetcher():
    import asyncio

    async def _fake(_word: str, _model: str | None) -> str:
        return _payload(english="house")

    out = asyncio.run(
        dictionary_content.generate_reverse_content(
            "casa", fetcher=_fake, verifier=_accept_reverse_verifier
        )
    )
    assert out["english"] == "house"


# --- V3.95.0: guardarraíl de retrotraducción (calidad del diccionario) ---------


def _stub_direct_fetcher(monkeypatch, payload: str, calls: list):
    """Stub del prompt DIRECTO (EN→ES): lo usa el verificador de retrotraducción."""

    async def _fake(word: str, model: str | None) -> str:
        calls.append((word, model))
        return payload

    monkeypatch.setattr(dictionary_content, "_fetch_chat", _fake)


def _direct_payload(translation: str, meanings: list[str] | None = None) -> str:
    return json.dumps(
        {
            "pos": "noun",
            "definition": "A thing.",
            "translation": translation,
            "meanings": [{"term": t} for t in (meanings or [])],
        }
    )


def test_guardrail_rejects_an_equivalent_confused_with_another_word(monkeypatch):
    """El caso reportado: «broca» → «rock» (confusión con «roca») se rechaza."""
    import asyncio

    async def _reverse(_word: str, _model: str | None) -> str:
        return _payload(english="rock", definition="A large stone or boulder")

    calls: list = []
    _stub_direct_fetcher(
        monkeypatch, _direct_payload("roca", ["roca", "piedra"]), calls
    )

    with pytest.raises(dictionary_content.ContentUnavailableError):
        asyncio.run(
            dictionary_content.generate_reverse_content("broca", fetcher=_reverse)
        )
    # La retrotraducción SÍ se intentó (una llamada al prompt directo de «rock»).
    assert calls == [("rock", None)]


def test_guardrail_accepts_an_equivalent_that_back_translates(monkeypatch):
    """Un equivalente correcto vuelve al término español y se acepta."""
    import asyncio

    async def _reverse(_word: str, _model: str | None) -> str:
        return _payload(english="chisel", definition="A hand tool.")

    calls: list = []
    _stub_direct_fetcher(monkeypatch, _direct_payload("cincel", ["cincel"]), calls)

    out = asyncio.run(
        dictionary_content.generate_reverse_content("cincel", fetcher=_reverse)
    )
    assert out["english"] == "chisel"
    assert calls == [("chisel", None)]


def test_guardrail_rejects_when_the_back_translation_is_unavailable(monkeypatch):
    """Si el modelo no puede retrotraducir, no se da el equivalente por bueno."""
    import asyncio

    async def _reverse(_word: str, _model: str | None) -> str:
        return _payload(english="house")

    async def _down(_word: str, _model: str | None) -> str:
        raise dictionary_content.ContentUnavailableError("test: modelo caído")

    monkeypatch.setattr(dictionary_content, "_fetch_chat", _down)

    with pytest.raises(dictionary_content.ContentUnavailableError):
        asyncio.run(
            dictionary_content.generate_reverse_content("morada", fetcher=_reverse)
        )


def test_guardrail_accepts_accent_and_morphology_tolerance(monkeypatch):
    """El plegado de acentos y las variantes no provocan falsos negativos."""
    import asyncio

    async def _reverse(_word: str, _model: str | None) -> str:
        return _payload(english="truck")

    _stub_direct_fetcher(monkeypatch, _direct_payload("camión"), [])

    out = asyncio.run(
        dictionary_content.generate_reverse_content("camion", fetcher=_reverse)
    )
    assert out["english"] == "truck"


def test_reverse_lookup_serves_the_glossary_and_never_poisons_the_cache(
    monkeypatch, tmp_path
):
    """«broca» la sirve el glosario curado («drill bit») sin consultar al modelo."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("drill bit", "broca", definition="A cutting tool for drilling.")
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "broca")

    assert data["translation"] == "drill bit"
    assert data["meanings"][0]["term"] == "drill bit"
    assert "rock" not in [m["term"] for m in data["meanings"]]
    assert calls == []


def test_reverse_lookup_degrades_when_the_equivalent_is_not_verifiable(
    monkeypatch, tmp_path
):
    """Sin curar y sin poder verificar, se degrada y NO se escribe caché inversa."""
    a, _b = _setup(monkeypatch, tmp_path)

    async def _reverse(_word: str, _model: str | None) -> str:
        return _payload(english="rock", definition="A large stone.")

    monkeypatch.setattr(dictionary_content, "_reverse_fetcher", _reverse)
    # «cantimplora» no está ni en el glosario ni en los packs ni en la caché: cae
    # al modelo, y el modelo retrotraduce su «rock» a «roca» (no a «cantimplora»),
    # así que no supera el guardarraíl.
    _stub_direct_fetcher(monkeypatch, _direct_payload("roca", ["roca"]), [])

    data = _reverse_lookup(a, "cantimplora")

    assert data["direction"] == "es-en"
    assert data["translation"] is None
    assert data["definition_source"] == "none"
    assert _count_rows("dictionary_reverse_entries") == 0


# --- V3.86.0: significados elegibles (polisemia) -----------------------------


def test_match_pack_translation_finds_curated_english():
    items = [
        {"word": "file", "translation": "lima", "pos": "noun"},
        {"word": "vice", "translation": "tornillo de banco", "pos": "noun"},
        {"word": "screw", "translation": "tornillo", "pos": "noun"},
    ]
    # Exacta antes que parcial: «screw» (tornillo) gana a «vice» (tornillo de
    # banco) y «file» es el único candidato de «lima».
    tornillo = dictionary_reverse.match_pack_translation("tornillo", items)
    assert [m["word"] for m in tornillo] == ["screw", "vice"]
    lima = dictionary_reverse.match_pack_translation("lima", items)
    assert [m["word"] for m in lima] == ["file"]
    assert dictionary_reverse.match_pack_translation("nada", items) == []


def test_match_pack_translation_priority_breaks_ties():
    """La `priority` curada decide el equivalente por defecto ante un empate."""
    items = [
        {"word": "drill", "translation": "broca", "pos": "noun", "priority": 0},
        {"word": "drill bit", "translation": "broca", "pos": "noun", "priority": 1},
    ]
    assert [
        m["word"] for m in dictionary_reverse.match_pack_translation("broca", items)
    ] == ["drill bit", "drill"]
    # Sin prioridad, el desempate sigue siendo alfabético (comportamiento previo).
    plain = [
        {"word": "drill", "translation": "broca", "pos": "noun"},
        {"word": "auger", "translation": "broca", "pos": "noun"},
    ]
    assert [
        m["word"] for m in dictionary_reverse.match_pack_translation("broca", plain)
    ] == ["auger", "drill"]


def test_normalize_meanings_sends_proper_nouns_last_and_dedupes():
    out = dictionary_content.normalize_meanings(
        [
            {"term": "Lima", "proper_noun": True, "domain": "geography"},
            {"term": "file", "pos": "noun", "domain": "tools"},
            {"term": "lime", "pos": "noun", "domain": "botany"},
            {"term": "file", "pos": "noun"},
        ]
    )
    assert [m["term"] for m in out] == ["file", "lime", "Lima"]
    assert out[-1]["proper_noun"] is True
    # El significado por defecto NUNCA es un nombre propio.
    assert dictionary_content.default_meaning_term(out, "x") == "file"


def test_parse_reverse_content_never_defaults_to_a_proper_noun():
    raw = json.dumps(
        {
            "english": "Lima",
            "pos": "noun",
            "definition": "The capital of Peru.",
            "meanings": [
                {"term": "Lima", "proper_noun": True, "domain": "geography"},
                {"term": "file", "pos": "noun", "domain": "tools"},
            ],
        }
    )
    out = dictionary_content.parse_reverse_content(raw, word="lima")
    # La regla dura: el equivalente por defecto es el común («file»), no la
    # capital. «Lima» queda como último significado, marcado.
    assert out["english"] == "file"
    assert out["meanings"][0]["term"] == "file"
    assert out["meanings"][-1]["proper_noun"] is True


def test_reverse_lookup_prefers_curated_pack_without_model(monkeypatch, tmp_path):
    """«tornillo» → «screw» por el par curado, sin consultar al modelo."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("screw", "tornillo", definition="A threaded fastener.")
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "tornillo")

    assert data["translation"] == "screw"
    assert data["meanings"][0]["term"] == "screw"
    assert all(not m["proper_noun"] for m in data["meanings"])
    assert calls == []


def test_reverse_lookup_of_lima_serves_the_tool_not_the_capital(
    monkeypatch, tmp_path
):
    """El caso reportado: «lima» (herramienta) ya no se sirve como «Lima»."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("file", "lima", definition="A tool for smoothing surfaces.")
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "lima")

    assert data["translation"] == "file"
    assert data["meanings"][0]["term"] == "file"
    assert "Lima" not in [m["term"] for m in data["meanings"]]
    assert calls == []


def test_reverse_lookup_merges_curated_meanings(monkeypatch, tmp_path):
    """Los candidatos curados se exponen como significados elegibles."""
    a, _b = _setup(monkeypatch, tmp_path)
    _seed_direct("screw", "tornillo", definition="A threaded fastener.")
    calls: list = []
    _offline_reverse_fetcher(monkeypatch, calls)

    data = _reverse_lookup(a, "tornillo")

    terms = [m["term"] for m in data["meanings"]]
    # El principal primero y, detrás, el otro candidato curado del pack.
    assert terms[0] == "screw"
    assert "vice" in terms
    assert data["translation"] == "screw"


def test_direct_lookup_exposes_meanings_and_default_term(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="A financial institution.",
        translation="banco",
        meanings=[
            {"term": "Lima", "proper_noun": True, "domain": "geography"},
            {"term": "banco", "pos": "noun", "domain": "finance"},
            {"term": "orilla", "pos": "noun", "domain": "geography"},
        ],
        generator_version=dictionary_content.GENERATOR_VERSION,
    )

    with TestClient(app) as client:
        res = client.post(
            f"/api/vocabulary/dictionary?user_id={a}",
            json={"word": "bank", "direction": "en-es"},
        )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["direction"] == "en-es"
    assert data["translation"] == "banco"
    assert [m["term"] for m in data["meanings"]] == ["banco", "orilla", "Lima"]
    assert data["meanings"][-1]["proper_noun"] is True


def test_repository_round_trips_the_meanings(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    meanings = [
        {"term": "banco", "pos": "noun", "gloss": "seat", "domain": "home"},
        {"term": "orilla", "pos": "noun", "gloss": "river bank", "domain": "nature"},
    ]
    assert dictionary_repo.save_entry(
        "bank",
        pos="noun",
        definition="def",
        translation="banco",
        meanings=meanings,
        generator_version=dictionary_content.GENERATOR_VERSION,
    )
    stored = dictionary_repo.get_entry("bank")
    assert stored["meanings"] == [
        {**m, "proper_noun": False} for m in meanings
    ]
    assert stored["meanings_json"] == json.dumps(
        [
            {**m, "proper_noun": False} for m in meanings
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


# --- V3.86.1: contrato del parser de significados ---------------------------


def test_normalize_meanings_only_trusts_a_real_boolean_for_proper_noun():
    """Solo un boolean de verdad marca nombre propio (V3.86.1).

    El contenido lo genera un modelo: `"false"` es un string *truthy* en Python,
    así que `bool(...)` convertía una negación explícita en un nombre propio y
    podía colocar «Lima» como significado por defecto.
    """
    out = dictionary_content.normalize_meanings(
        [
            {"term": "file", "proper_noun": "false"},  # string truthy: NO
            {"term": "lime", "proper_noun": "true"},  # string: NO
            {"term": "saw", "proper_noun": 1},  # número: NO
            {"term": "Peru", "proper_noun": None},  # None: NO
            {"term": "Lima", "proper_noun": True},  # boolean de verdad
        ]
    )
    by_term = {m["term"]: m for m in out}
    assert by_term["file"]["proper_noun"] is False
    assert by_term["lime"]["proper_noun"] is False
    assert by_term["saw"]["proper_noun"] is False
    assert by_term["Peru"]["proper_noun"] is False
    assert by_term["Lima"]["proper_noun"] is True
    # El único nombre propio real va al final y no puede ser el por defecto.
    assert out[-1]["term"] == "Lima"
    assert dictionary_content.default_meaning_term(out, "x") == "file"


def test_normalize_meanings_dedupes_by_term_not_by_pos():
    """El contrato es dedupe por TÉRMINO: el término ES el significado.

    Dos apariciones del mismo equivalente con `pos` distinto —`file`/noun y
    `file`/verb— son una sola acepción; la documentación y el código dicen ahora
    lo mismo.
    """
    out = dictionary_content.normalize_meanings(
        [
            {"term": "file", "pos": "noun", "gloss": "herramienta"},
            {"term": "FILE", "pos": "verb", "gloss": "archivar"},
            {"term": "lime", "pos": "noun"},
        ]
    )
    assert [m["term"] for m in out] == ["file", "lime"]
    # Conserva la primera, que es la que trae la mejor metadata.
    assert out[0]["pos"] == "noun"
    assert out[0]["gloss"] == "herramienta"
