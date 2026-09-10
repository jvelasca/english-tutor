"""Tests de aceptación de V3.34 — Recall 2.0 (recuperación por texto).

Tercer eslabón del Dictionary → Learning Bridge: el peldaño "Recall" de la
escalera compartida de drill. Camino INVERSO a Recognition (V3.33): el alumno ve
el SIGNIFICADO (cue) y teclea la palabra. Acceptance de integración HTTP
(TestClient) + helpers puros:

- la pregunta es pura y determinista sobre la caché global `dictionary_entries`
  (`services.recall`); el GET NUNCA expone la forma esperada (premisa 21);
- el cue prefiere la traducción y cae a la definición SOLO si no contiene la
  palabra diana (sin spoiler); sin cue utilizable → `available=false` y POST 409
  sin evento;
- acierto y fallo registran el evento `drill:<word>:recall:ok|ko`, dejan señal
  léxica PROPIA de recall (`recall_successes`/`recall_days` + ledger `recalled`)
  y NUNCA acreditan producción (ni `production_count` ni `<channel>_prod`);
- un acierto fuera del intervalo de retención acredita la recuperación demorada
  existente (`retrieval_successes`) y reprograma la carta FSRS `lexicon`;
- un fallo solo aplica el lapse FSRS si la palabra ya estaba rastreada;
- aislamiento entre usuarios (la señal solo aparece en el autor).

Cada test usa UN solo `with TestClient(app)` (el lifespan llama a `init_db()`)
y siembra la caché `dictionary_entries` directamente con el repositorio (el
recall nunca invoca al generador de contenido).
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import recall
from services.lexicon import item_competence_matrix, summary

# Banco de significados de prueba: la diana `quokka` traduce a un texto único.
_SEED = [
    ("quokka", "noun", "a small Australian marsupial", "marsupial australiano"),
    ("apple", "noun", "a round fruit", "manzana"),
    ("river", "noun", "a flowing water course", "río"),
]


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


def _get_prompt(client: TestClient, uid: str, word: str) -> dict:
    res = client.get(
        "/api/vocabulary/drill/recall",
        params={"user_id": uid, "word": word},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _post_attempt(client: TestClient, uid: str, word: str, answer: str) -> dict:
    res = client.post(
        "/api/vocabulary/drill/recall-attempt",
        params={"user_id": uid},
        json={"word": word, "answer": answer},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _drill_events(uid: str) -> list[str]:
    return [e["detail"] for e in learning_repo.list_events(uid, "exercise")]


def _row(uid: str, word: str) -> dict:
    return next(
        (r for r in vocabulary_repo.get_vocabulary(uid) if r["word"] == word),
        {},
    )


def _backdate_exposure(uid: str, word: str, days: int) -> None:
    """Retrasa el ancla de exposición para simular un recall demorado."""
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "UPDATE vocabulary SET first_exposed_at = ?, exposure_days = 2, "
            "exposure_count = 2 WHERE user_id = ? AND word = ?",
            (old, uid, word),
        )


# --- Acceptance: cue puro (traducción > definición sin spoiler) --------------


def test_pure_prompt_prefers_translation():
    entries = [
        {
            "word": "quokka",
            "pos": "noun",
            "translation": "marsupial australiano",
            "definition": "a small Australian marsupial",
        }
    ]
    assert recall.recall_prompt_for("quokka", entries) == {
        "word": "quokka",
        "cue": "marsupial australiano",
        "cue_kind": "translation",
    }


def test_pure_prompt_falls_back_to_definition_without_leak():
    entries = [
        {
            "word": "quokka",
            "pos": "noun",
            "translation": "",
            "definition": "a small Australian marsupial",
        }
    ]
    assert recall.recall_prompt_for("quokka", entries) == {
        "word": "quokka",
        "cue": "a small Australian marsupial",
        "cue_kind": "definition",
    }


def test_pure_prompt_discards_definition_that_leaks_the_word():
    """Una definición circular ("a bank is a bank...") regala la respuesta:
    no se ofrece como cue (`None` → degradación)."""
    entries = [
        {
            "word": "bank",
            "pos": "noun",
            "translation": "",
            "definition": "a bank is a place where you keep your money",
        }
    ]
    assert recall.recall_prompt_for("bank", entries) is None


def test_pure_prompt_none_for_unknown_or_empty_word():
    entries = [
        {"word": "apple", "pos": "noun", "translation": "manzana", "definition": ""}
    ]
    assert recall.recall_prompt_for("ghost", entries) is None
    assert recall.recall_prompt_for("", entries) is None


# --- Acceptance: el GET nunca expone la respuesta ---------------------------


def test_recall_prompt_never_exposes_answer(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        body = _get_prompt(client, a, "quokka")

    assert body["word"] == "quokka"
    assert body["available"] is True
    assert body["cue"] == "marsupial australiano"
    assert body["cue_kind"] == "translation"
    # El GET nunca revela la forma esperada (la revela el POST, premisa 21).
    assert "expected" not in body
    assert body["cue"] != body["word"]


def test_recall_unavailable_when_word_not_cached(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        body = _get_prompt(client, a, "ghost")
        assert body == {
            "word": "ghost",
            "available": False,
            "cue": "",
            "cue_kind": "",
        }
        # POST controlado: 409 sin evento (no hay pregunta que puntuar).
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": a},
            json={"word": "ghost", "answer": "ghost"},
        )
        assert res.status_code == 409

    assert _drill_events(a) == []


# --- Acceptance: scoring y normalización ------------------------------------


def test_recall_hit_and_miss_reveal_expected_after_answering(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _get_prompt(client, a, "quokka")
        # Acierto normalizado (mayúsculas/espacios).
        hit = _post_attempt(client, a, "quokka", "  Quokka ")
        assert hit["correct"] is True
        assert hit["expected"] == "quokka"
        assert hit["delayed"] is False
        assert hit["recall_days"] == 1

        # Fallo: revela la palabra correcta para el feedback.
        miss = _post_attempt(client, a, "apple", "orange")
        assert miss["correct"] is False
        assert miss["expected"] == "apple"
        assert miss["delayed"] is False

    # El ledger de eventos va de más reciente a más antiguo.
    assert _drill_events(a) == ["drill:apple:recall:ko", "drill:quokka:recall:ok"]


def test_recall_empty_answer_is_a_miss(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        miss = _post_attempt(client, a, "quokka", "   ")
    assert miss["correct"] is False
    assert _drill_events(a) == ["drill:quokka:recall:ko"]


# --- Acceptance: señal léxica PROPIA (nunca producción) ---------------------


def test_recall_hit_leaves_recall_signal_not_production(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.get_vocabulary(a) == []

    with TestClient(app) as client:
        _post_attempt(client, a, "quokka", "quokka")

    row = _row(a, "quokka")
    # El recall se acredita como RECUPERACIÓN, no como producción.
    assert row["recall_successes"] == 1
    assert row["recall_days"] == 1
    assert row["production_count"] == 0
    assert row["chat_prod"] == 0
    assert row["speaking_prod"] == 0
    assert row["writing_prod"] == 0
    assert row["conversation_prod"] == 0
    # Ledger léxico: evento `recalled` (nunca `produced`).
    events = vocabulary_repo.list_vocabulary_events(a, word="quokka")
    assert [e["event_type"] for e in events] == ["recalled"]
    # Matriz de competencia + resumen.
    matrix = item_competence_matrix(row)
    assert matrix["cued_recall"] is True
    assert matrix["recall_successes"] == 1
    assert matrix["production"] is False
    assert matrix["retention"] is False
    assert summary(vocabulary_repo.get_vocabulary(a))["recalled"] == 1


def test_recall_hit_twice_same_day_counts_successes_once_per_day(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _post_attempt(client, a, "quokka", "quokka")
        _post_attempt(client, a, "quokka", "quokka")

    row = _row(a, "quokka")
    assert row["recall_successes"] == 2
    assert row["recall_days"] == 1  # mismo día natural: un solo día con recall


def test_recall_hit_creates_row_for_untracked_word_without_production(
    monkeypatch, tmp_path
):
    """Palabra nunca expuesta ni producida (solo consultada): el recall crea la
    fila SIN inventar producción ni exposición."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _post_attempt(client, a, "apple", "apple")

    row = _row(a, "apple")
    assert row["recall_successes"] == 1
    assert row["production_count"] == 0
    assert row["exposure_count"] == 0
    assert row["first_seen"] == ""


# --- Acceptance: recuperación demorada (fuera del intervalo) -----------------


def test_recall_hit_outside_interval_credits_delayed_retrieval(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    # Exposición con ancla antigua: el recall queda fuera del intervalo.
    vocabulary_repo.record_exposures(a, ["quokka"])
    _backdate_exposure(a, "quokka", days=3)
    before = _row(a, "quokka")["retrieval_successes"]

    with TestClient(app) as client:
        hit = _post_attempt(client, a, "quokka", "quokka")

    assert hit["delayed"] is True
    row = _row(a, "quokka")
    assert row["retrieval_successes"] == before + 1
    assert row["retrieval_days"] == 1
    assert row["recall_successes"] == 1
    # La recuperación demorada del recall también se refleja en la matriz.
    assert item_competence_matrix(row)["retention"] is True


def test_recall_hit_inside_interval_does_not_credit_delayed(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    # Exposición de HOY: sin intervalo, no hay recuperación demorada.
    vocabulary_repo.record_exposures(a, ["quokka"])

    with TestClient(app) as client:
        hit = _post_attempt(client, a, "quokka", "quokka")

    assert hit["delayed"] is False
    row = _row(a, "quokka")
    assert row["retrieval_successes"] == 0
    assert row["recall_successes"] == 1


# --- Acceptance: carta FSRS `lexicon` (intervalos reales) -------------------


def test_recall_hit_schedules_lexicon_card(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert academy_repo.get_fsrs_card(a, "lexicon", "quokka") is None

    with TestClient(app) as client:
        _post_attempt(client, a, "quokka", "quokka")

    card = academy_repo.get_fsrs_card(a, "lexicon", "quokka")
    assert card is not None
    assert card["reps"] == 1
    # Acierto inmediato = Good: due en el futuro (intervalo real > 0).
    assert card["due_at"] > datetime.now(timezone.utc).isoformat()


def test_recall_miss_without_existing_card_creates_nothing(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _post_attempt(client, a, "quokka", "nope")

    # No se inventa deuda de repaso por fallar una palabra no rastreada.
    assert academy_repo.get_fsrs_card(a, "lexicon", "quokka") is None


def test_recall_miss_with_existing_card_applies_lapse(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _post_attempt(client, a, "quokka", "quokka")  # siembra la carta (Good)
        _post_attempt(client, a, "quokka", "nope")  # lapse (Again)

    card = academy_repo.get_fsrs_card(a, "lexicon", "quokka")
    assert card["reps"] == 2
    assert card["lapses"] == 1
    assert card["last_grade"] == 1  # GRADE_AGAIN


# --- Acceptance: aislamiento entre usuarios ---------------------------------


def test_recall_signal_isolated_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _post_attempt(client, a, "quokka", "quokka")

    assert _row(a, "quokka")["recall_successes"] == 1
    # B no ve ningún rastro de A hasta que responde por su cuenta.
    assert vocabulary_repo.get_vocabulary(b) == []
    assert _drill_events(b) == []

    with TestClient(app) as client:
        _post_attempt(client, b, "quokka", "wrong")

    # V3.35: el fallo deja señal de INTENTO (attempts vs successes). No se puede
    # distinguir "no lo intentó" de "falló" sin este contador; el fallo no toca
    # el ancla ni acredita un acierto.
    row_b = _row(b, "quokka")
    assert row_b["recall_attempts"] == 1
    assert row_b["recall_successes"] == 0
    assert row_b["last_recall_at"] == ""
    assert _drill_events(b) == ["drill:quokka:recall:ko"]
