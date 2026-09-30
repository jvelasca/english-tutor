"""Contract E2E de V3.92: la forma REAL que cruza el borde backend <-> frontend.

V3.92 encontró un fallo de contrato que llevaba versiones oculto: el backend
servía `transcript_policy`/`sentence_timings`/`word_timings` en snake_case y el
cliente los leía en camelCase, así que llegaban `undefined` y con ellos se caían
la tarjeta de fallo de V3.89 y el karaoke de V3.29. Los tests de unidad de cada
lado no lo veían porque cada lado probaba su propia forma.

Esta categoría —**Contract E2E**— fija la forma EXACTA que viaja por el borde,
para que un renombrado silencioso vuelva a caer aquí. Cubre las cuatro superficies
que V3.92 tocó y la cadena completa Listening -> FSRS -> Plan diario:

- `GET /api/listening/question` (snake_case que consume `toListeningQuestion`);
- `POST /api/listening/answer` -> `difficulty_evidence: {words, count}`;
- `POST /api/vocabulary/items` + `GET /api/vocabulary/lexicon` -> `sense`;
- `GET /api/academy/daily-plan` -> `metrics.difficulty_evidence`/`words_flagged`.

El lado del cliente que consume estas formas se fija aparte, en
`frontend/src/api/contract.test.ts`.
"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs
from services import listening as listening_svc
from services import listening_bridge as bridge
from services.listening import QUESTION_BANK

SENSE_FIELDS = {"term", "pos", "gloss", "lemma", "source", "domain"}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _receptive_question() -> dict:
    for q in QUESTION_BANK:
        if q["skill"] not in ("dictation", "shadowing") and listening_svc.audio_text(q):
            return q
    raise AssertionError("banco sin ítems receptivos con texto")


def _wrong_index(q: dict) -> int:
    return (q["answer_index"] + 1) % len(q["options"])


def _phrase_word(q: dict) -> str:
    units = [
        u for u in bridge.phrase_units(listening_svc.audio_text(q)) if len(u) >= 4
    ]
    assert units, "frase demasiado corta para la sonda"
    return units[0]


def _seed_word_with_empty_card(uid: str, word: str) -> None:
    vocabulary_repo.seed_study_items(
        uid, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    academy_repo.upsert_fsrs_card(
        uid, fsrs.empty_card(target_type="lexicon", target_id=word, label=word)
    )


def _fail(client, uid: str, q: dict):
    return client.post(
        "/api/listening/answer",
        params={"user_id": uid},
        json={"question_id": q["id"], "answer_index": _wrong_index(q)},
    )


# --- 1. La forma del ítem de Listening que consume el adaptador del cliente ---


def test_listening_question_keeps_the_snake_case_contract(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.get("/api/listening/question", params={"user_id": uid})
    assert res.status_code == 200, res.text
    body = res.json()
    # Las tres claves que el cliente traduce en el borde existen con su nombre real.
    assert {"transcript_policy", "sentence_timings", "word_timings"} <= set(body)
    # Y NO llegan ya en camelCase: el borde es el ÚNICO punto de traducción.
    assert not ({"transcriptPolicy", "sentenceTimings", "wordTimings"} & set(body))


# --- 2. La evidencia del fallo --------------------------------------------------


def test_answer_difficulty_evidence_shape(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["correct"] is False
    # Contrato exacto: dos campos, ni uno más.
    assert set(body["difficulty_evidence"]) == {"words", "count"}
    assert body["difficulty_evidence"]["count"] == len(
        body["difficulty_evidence"]["words"]
    )
    assert body["difficulty_evidence"]["words"] == [word]
    # V3.94 (ENFORCE): la exposición a un sentido nuevo es ADITIVA y con la MISMA
    # forma `{words, count}`; en este caso (palabra sin alternativas conocidas) va
    # vacía, porque `mismatch` exige una alternativa probada.
    assert set(body["new_sense_exposure"]) == {"words", "count"}
    assert body["new_sense_exposure"] == {"words": [], "count": 0}


# --- 3. La acepción de la palabra ----------------------------------------------


def test_vocabulary_add_and_lexicon_sense_shape(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/items",
            params={"user_id": uid},
            json={
                "word": "bank",
                "translation": "banco (institución)",
                "sense": {
                    "term": "bank",
                    "pos": "noun",
                    "gloss": "A place where money is kept.",
                    "lemma": "bank",
                    "source": "lexicon",
                    "domain": "finance",
                },
            },
        )
        assert res.status_code == 200, res.text
        lexicon = client.get(
            "/api/vocabulary/lexicon", params={"user_id": uid}
        ).json()
    item = next(i for i in lexicon["items"] if i["word"] == "bank")
    assert item["sense"] is not None
    assert set(item["sense"]) == SENSE_FIELDS
    assert item["translation"] == "banco (institución)"


def test_vocabulary_without_sense_reads_as_none(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items", params={"user_id": uid}, json={"word": "anchor"}
        )
        lexicon = client.get(
            "/api/vocabulary/lexicon", params={"user_id": uid}
        ).json()
    item = next(i for i in lexicon["items"] if i["word"] == "anchor")
    assert item["sense"] is None


# --- 4. Las métricas honestas del día ------------------------------------------


def test_daily_plan_metrics_shape(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        metrics = client.get(
            "/api/academy/daily-plan", params={"user_id": uid}
        ).json()["metrics"]
    # Las dos cifras V3.92 son aditivas y siguen existiendo las clásicas.
    assert {"difficulty_evidence", "words_flagged"} <= set(metrics)
    assert isinstance(metrics["difficulty_evidence"], int)
    assert isinstance(metrics["words_flagged"], int)
    assert {"units", "minutes", "reviews", "new", "listening"} <= set(metrics)


# --- 5. La cadena completa: Listening -> FSRS -> Plan diario -------------------


def test_listening_failure_reaches_fsrs_plan_and_due_queue(monkeypatch, tmp_path):
    """E2E real (TestClient): el fallo sube la carta, cuenta en el día y vence hoy."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    before = academy_repo.get_fsrs_card(uid, "lexicon", word)

    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
        plan = client.get(
            "/api/academy/daily-plan", params={"user_id": uid}
        ).json()
        due = client.get(
            "/api/vocabulary/retention/due", params={"user_id": uid}
        ).json()

    assert body["difficulty_evidence"]["words"] == [word]
    card = academy_repo.get_fsrs_card(uid, "lexicon", word)
    # Sube dificultad y vence hoy, SIN fingir una recuperación.
    assert card["difficulty"] > before["difficulty"]
    assert card["reps"] == before["reps"] == 0
    assert card["stability"] == before["stability"]
    assert card["due_at"] <= datetime.now(timezone.utc).isoformat()
    # El día lo cuenta una vez, y la palabra queda debida para repasar.
    assert plan["metrics"]["difficulty_evidence"] == 1
    assert plan["metrics"]["words_flagged"] == 1
    assert plan["pending"]["fsrs"] >= 1
    assert word in [item["word"] for item in due["items"]]
