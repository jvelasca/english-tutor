"""Tests de aceptación de V3.33 — Recognition (MCQ definición ↔ palabra).

Segundo eslabón del Dictionary → Learning Bridge (V3.32): el peldaño
"Recognition" de la escalera compartida de drill. El alumno ve la palabra y
elige su significado entre opciones servidas por el backend (premisa 21, sin
estado servidor: pregunta pura y determinista por palabra sobre la caché global
`dictionary_entries`). Acceptance de integración HTTP (TestClient):

- el GET nunca expone la correcta y la pregunta es determinista (mismas
  `options` entre llamadas);
- acierto y fallo registran SOLO el evento informativo `learning_events`
  `drill:<word>:recognition:ok|ko`: CERO cambios en filas/eventos de
  `vocabulary` (ni retrievals ni production), igual que la consulta del
  diccionario (D3) y sin "mastery de clic" (V3.13);
- los eventos de recognition NO alteran la salida de candidatas del drill
  (seguir pendiente exige éxito de producción espaciada);
- aislamiento entre usuarios (evento solo en el autor);
- palabra sin entrada cacheada o sin distractores → `available=false` (GET, sin
  evento) y POST controlado 4xx sin evento.

Cada test usa UN solo `with TestClient(app)` (el lifespan llama a `init_db()`),
y siembra la caché `dictionary_entries` directamente con el repositorio (el
MCQ nunca invoca al generador de contenido).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_mcq
from services.lexicon import drill_candidates, drill_ok_days

# Banco de significados de prueba: la diana `quokka` traduce a un texto único y
# hay suficientes entradas con traducción para 4 opciones (3 distractores).
_SEED = [
    ("quokka", "noun", "", "marsupial australiano"),
    ("apple", "noun", "", "fruta de pepita"),
    ("banana", "noun", "", "fruta tropical"),
    ("carrot", "noun", "", "raíz comestible"),
    ("river", "noun", "", "corriente de agua"),
    ("library", "noun", "", "sitio de libros"),
]
_CORRECT_ES = "marsupial australiano"


def _setup(monkeypatch, tmp_path, entries=_SEED):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    for word, pos, definition, translation in entries:
        dictionary_repo.save_entry(
            word,
            pos=pos,
            definition=definition,
            translation=translation,
            generator_version="test",
        )
    return a, b


def _get_question(client: TestClient, uid: str, word: str) -> dict:
    res = client.get(
        "/api/vocabulary/drill/recognition",
        params={"user_id": uid, "word": word},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _post_attempt(
    client: TestClient, uid: str, word: str, selected_index: int
) -> dict:
    res = client.post(
        "/api/vocabulary/drill/recognition-attempt",
        params={"user_id": uid},
        json={"word": word, "selected_index": selected_index},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _index_of(options: list[str], text: str) -> int:
    """Índice de la opción cuyo texto coincide (p. ej. la traducción real)."""
    return next(i for i, option in enumerate(options) if option == text)


def _wrong_index(options: list[str], correct_text: str) -> int:
    """Un índice garantizado INCORRECTO (cualquier opción que no sea la real)."""
    return next(
        i for i, option in enumerate(options) if option != correct_text
    )


def _drill_events(uid: str) -> list[str]:
    return [e["detail"] for e in learning_repo.list_events(uid, "exercise")]


# --- Acceptance: pregunta determinista y sin respuesta en el GET ------------


def test_recognition_question_deterministic_and_never_exposes_answer(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = _get_question(client, a, "quokka")
        second = _get_question(client, a, "quokka")

    assert first["word"] == "quokka"
    assert first["available"] is True
    # Determinista: dos GET consecutivos, misma pregunta y mismo orden.
    assert first["options"] == second["options"]
    # El GET nunca filtra la correcta (la puntúa el POST, premisa 21).
    assert "correct_index" not in first
    # 4 opciones (1 correcta + 3 distractores) que incluyen el significado real.
    assert len(first["options"]) == 4
    assert _CORRECT_ES in first["options"]


def test_recognition_mode_falls_back_to_definition(monkeypatch, tmp_path):
    """Sin traducción suficiente, la pregunta usa el modo `definition` (siempre
    un solo idioma entre opciones: nunca se mezclan traducción y definición)."""
    entries = [
        ("aurora", "noun", "lights in the polar sky", ""),
        ("comet", "noun", "icy body orbiting the sun", ""),
        ("eclipse", "noun", "covering of one body by another", ""),
        ("galaxy", "noun", "system of stars and dust", ""),
    ]
    a, _b = _setup(monkeypatch, tmp_path, entries=entries)
    with TestClient(app) as client:
        question = _get_question(client, a, "aurora")

    assert question["available"] is True
    # La opción correcta es la DEFINICIÓN de la diana (no hay traducciones).
    assert "lights in the polar sky" in question["options"]
    for option in question["options"]:
        assert option in {e[2] for e in entries}


# --- Acceptance: acierto/fallo SOLO informativo (D3 + V3.13) ----------------


def test_recognition_hit_records_only_informative_event(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.get_vocabulary(a) == []
    assert _drill_events(a) == []

    with TestClient(app) as client:
        body = _get_question(client, a, "quokka")
        hit = _post_attempt(
            client, a, "quokka", _index_of(body["options"], _CORRECT_ES)
        )

    assert hit["correct"] is True
    assert hit["word"] == "quokka"
    # El servidor recomputa la pregunta con la misma función pura (premisa 21).
    assert hit["correct_index"] == _index_of(body["options"], _CORRECT_ES)
    assert hit["selected_index"] == hit["correct_index"]
    # Único rastro: el evento informativo. Cero filas/eventos de vocabulario.
    assert _drill_events(a) == ["drill:quokka:recognition:ok"]
    assert vocabulary_repo.get_vocabulary(a) == []
    assert vocabulary_repo.list_vocabulary_events(a) == []


def test_recognition_miss_records_ko_without_effects(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert _drill_events(a) == []

    with TestClient(app) as client:
        body = _get_question(client, a, "quokka")
        wrong = _wrong_index(body["options"], _CORRECT_ES)
        miss = _post_attempt(client, a, "quokka", wrong)

    assert miss["correct"] is False
    # El fallo revela la opción correcta para el feedback (solo tras responder).
    assert miss["correct_index"] == _index_of(body["options"], _CORRECT_ES)
    assert miss["selected_index"] == wrong
    assert _drill_events(a) == ["drill:quokka:recognition:ko"]
    assert vocabulary_repo.get_vocabulary(a) == []
    assert vocabulary_repo.list_vocabulary_events(a) == []


def test_recognition_normalizes_word_and_validates_index(monkeypatch, tmp_path):
    """La palabra se normaliza como en el lookup y un índice fuera de rango se
    rechaza (422) sin registrar evento."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        body = _get_question(client, a, "Quokka!")
        assert body["word"] == "quokka"
        assert body["available"] is True

        res = client.post(
            "/api/vocabulary/drill/recognition-attempt",
            params={"user_id": a},
            json={"word": "quokka", "selected_index": 99},
        )
        assert res.status_code == 422

    assert _drill_events(a) == []


# --- Acceptance: sin entrada o sin distractores → degradación controlada -----


def test_recognition_unavailable_when_word_not_cached(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        # Palabra jamás generada en la caché global.
        body = _get_question(client, a, "ghost")
        assert body == {"word": "ghost", "available": False, "options": []}

        # POST controlado: 4xx sin evento.
        res = client.post(
            "/api/vocabulary/drill/recognition-attempt",
            params={"user_id": a},
            json={"word": "ghost", "selected_index": 0},
        )
        assert res.status_code == 409

    assert _drill_events(a) == []


def test_recognition_unavailable_without_distractors(monkeypatch, tmp_path):
    """Una única entrada global no puede formar pregunta (sin distractores)."""
    entries = [("solo", "noun", "", "único significado")]
    a, _b = _setup(monkeypatch, tmp_path, entries=entries)
    with TestClient(app) as client:
        body = _get_question(client, a, "solo")
        assert body["available"] is False
        assert body["options"] == []

    assert _drill_events(a) == []


def test_recognition_duplicate_meanings_never_become_options(
    monkeypatch, tmp_path
):
    """Textos de significado duplicados entre entradas se descartan: nunca dos
    opciones indistinguibles (aunque hubiera muchas filas con el mismo texto)."""
    entries = [
        ("word", "noun", "", "meaning one"),
        ("dup1", "noun", "", "meaning two"),
        ("dup2", "noun", "", "meaning two"),
        ("dup3", "noun", "", "meaning three"),
        ("dup4", "noun", "", "meaning four"),
    ]
    a, _b = _setup(monkeypatch, tmp_path, entries=entries)
    with TestClient(app) as client:
        body = _get_question(client, a, "word")

    assert body["available"] is True
    assert "meaning one" in body["options"]
    assert "meaning two" in body["options"]
    # Ninguna opción se repite (case-insensitive).
    folded = [option.casefold() for option in body["options"]]
    assert len(set(folded)) == len(folded)


# --- Acceptance: no altera la salida de candidatas del drill -----------------


def test_recognition_events_do_not_change_drill_candidates():
    """`drill:<word>:recognition:ok` no consolida: la palabra sigue pendiente
    (solo la producción espaciada del drill la saca de candidatas)."""
    rows = [
        {
            "word": "quokka",
            "exposures": 3,
            "speaking_prod": 1,
            "appearances": 1,
            "production_days": 1,
        }
    ]
    events = [
        {
            "detail": "drill:quokka:recognition:ok",
            "created_at": "2026-09-06T09:00:00+00:00",
        },
        {
            "detail": "drill:quokka:recognition:ok",
            "created_at": "2026-09-07T09:00:00+00:00",
        },
        {
            "detail": "drill:quokka:ko",
            "created_at": "2026-09-07T10:00:00+00:00",
        },
    ]
    ok_days = drill_ok_days(events)
    # El parseo NO atribuye el día a la palabra (la clave informativa es
    # `quokka:recognition`): no hay éxito de producción espaciado real.
    assert ok_days.get("quokka") is None
    assert drill_candidates(rows, ok_days=ok_days, today="2026-09-07") == [
        "quokka"
    ]

    # Contrafactual: si esos días se atribuyeran a la palabra, saldría de
    # candidatas — este test detectaría esa regresión.
    counted = {"quokka": {"2026-09-06", "2026-09-07"}}
    assert drill_candidates(rows, ok_days=counted, today="2026-09-07") == []


# --- Acceptance: aislamiento entre usuarios ----------------------------------


def test_recognition_events_isolated_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        question_a = _get_question(client, a, "quokka")
        question_b = _get_question(client, b, "quokka")
        # Misma pregunta global para ambos (la caché no es de un alumno).
        assert question_a["options"] == question_b["options"]

        _post_attempt(
            client,
            a,
            "quokka",
            _wrong_index(question_a["options"], _CORRECT_ES),
        )
        # B no ve ningún rastro de A hasta que responde por su cuenta.
        assert _drill_events(b) == []
        assert vocabulary_repo.get_vocabulary(b) == []

        _post_attempt(
            client,
            b,
            "quokka",
            _wrong_index(question_b["options"], _CORRECT_ES),
        )

    assert _drill_events(a) == ["drill:quokka:recognition:ko"]
    assert _drill_events(b) == ["drill:quokka:recognition:ko"]
    assert vocabulary_repo.get_vocabulary(a) == []
    assert vocabulary_repo.get_vocabulary(b) == []


# --- Acceptance: determinismo puro del helper --------------------------------


def test_pure_helper_returns_none_without_pool():
    """El helper puro (sin HTTP) devuelve None sin distractores suficientes."""
    entries = [
        {"word": "solo", "pos": "noun", "translation": "único", "definition": ""},
        {"word": "par", "pos": "noun", "translation": "", "definition": ""},
    ]
    assert dictionary_mcq.recognition_options_for("solo", entries) is None
