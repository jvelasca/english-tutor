"""V3.92 (integración pedagógica): el fallo de Listening es evidencia para FSRS.

La frontera que fija esta release: la FRASE fallada sigue siendo un ejercicio de
su propia cola (V3.89) y **no** entra en FSRS; lo que entra es la evidencia de
que las PALABRAS que el alumno ya tiene y que aparecían en esa frase son más
difíciles de lo que su carta decía.

Lo que se prueba, en el orden en que se puede romper:

1. la migración añade `listening_difficulty_evidence` y `vocabulary.sense_json`
   de forma aditiva e idempotente;
2. el emparejamiento frase ↔ léxico es puro, determinista y NO inventa
   vocabulario (una palabra que el alumno no tiene no recibe nada);
3. la evidencia sube `difficulty`, adelanta `due_at` y deja intactos `reps` y
   `stability` (no hubo recuperación: fingirla corrompería la curva de olvido);
4. un dominio demostrado no se castiga, y la sesión nunca se bloquea;
5. la métrica del día cuenta la evidencia y las palabras distintas por separado.
"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs
from services import listening as listening_svc
from services import listening_bridge as bridge
from services.daily_plan import day_metrics
from services.listening import QUESTION_BANK


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


def _seed_word(user_id: str, word: str, *, card: dict | None = None) -> None:
    """Da de alta una palabra en el léxico del alumno y, si toca, su carta."""
    vocabulary_repo.seed_study_items(
        user_id, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    if card is not None:
        academy_repo.upsert_fsrs_card(user_id, card)


def _seed_word_with_empty_card(user_id: str, word: str) -> None:
    """Palabra del léxico con carta VACÍA (nunca programada, dificultad base).

    Es el caso del puente «palabra que ya es suya pero jamás se programó»: la
    carta nace con la evidencia. Se aísla aquí para que la ruta larga
    (`fsrs.empty_card(...)`) no obligue a partir la línea en cada test.
    """
    _seed_word(
        user_id,
        word,
        card=fsrs.empty_card(
            target_type="lexicon", target_id=word, label=word
        ),
    )


def _phrase_words(q: dict, count: int = 2) -> list[str]:
    """Palabras largas de la frase, estables para el test."""
    units = [u for u in bridge.phrase_units(listening_svc.audio_text(q)) if len(u) >= 4]
    assert len(units) >= count, "frase demasiado corta para la sonda"
    return units[:count]


# --- Migración ---------------------------------------------------------------


def test_migration_creates_difficulty_evidence_table(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    tables = {
        row[0]
        for row in db._conn().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "listening_difficulty_evidence" in tables


def test_migration_adds_vocabulary_sense_column(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cols = {row[1] for row in db._conn().execute("PRAGMA table_info(vocabulary)")}
    assert "sense_json" in cols


def test_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # re-arranque: no debe fallar ni duplicar
    cols = {row[1] for row in db._conn().execute("PRAGMA table_info(vocabulary)")}
    assert "sense_json" in cols


# --- Emparejamiento puro -----------------------------------------------------


def test_phrase_units_drops_stopwords_and_punctuation():
    assert bridge.phrase_units("The bank, of the river!") == ["bank", "river"]


def test_phrase_units_is_deduplicated_and_ordered():
    assert bridge.phrase_units("bank river bank") == ["bank", "river"]


def test_phrase_units_tolerates_junk():
    assert bridge.phrase_units(None) == []
    assert bridge.phrase_units(42) == []


def test_match_units_finds_inflected_form_of_a_known_word():
    known = [{"word": "bank", "lemma": "bank"}]
    assert bridge.match_units("The banks are open", known) == [
        {"word": "bank", "surface": "banks"}
    ]


def test_match_units_ignores_words_the_student_does_not_have():
    known = [{"word": "river", "lemma": "river"}]
    assert bridge.match_units("The bank is closed", known) == []


def test_match_units_without_lexicon_is_empty():
    assert bridge.match_units("The bank is closed", []) == []


def test_match_units_is_capped():
    # Tokens de solo letras y distintos (el módulo normaliza a minúsculas).
    tokens = [f"{a}{b}zz" for a in "abcdef" for b in "ghij"]
    known = [{"word": token} for token in tokens]
    assert len(tokens) > bridge.MAX_MATCHES
    assert len(bridge.match_units(" ".join(tokens), known)) == bridge.MAX_MATCHES


def test_is_weak_card_covers_states_and_difficulty():
    assert bridge.is_weak_card(None) is True
    assert bridge.is_weak_card({"state": "new", "difficulty": 5.0}) is True
    assert bridge.is_weak_card({"state": "learning", "difficulty": 4.0}) is True
    assert bridge.is_weak_card({"state": "relearning", "difficulty": 9.0}) is True
    # Dificultad alta aunque la carta esté en repaso: sigue admitiendo evidencia.
    assert bridge.is_weak_card({"state": "review", "difficulty": 7.5}) is True
    # Dominio demostrado: NO se castiga por no entender una frase.
    assert bridge.is_weak_card({"state": "review", "difficulty": 3.0}) is False


def test_select_targets_reports_the_card_or_none():
    matches = [
        {"word": "bank", "surface": "banks"},
        {"word": "river", "surface": "river"},
    ]
    cards = {"bank": {"state": "new", "difficulty": 5.0}}
    targets = bridge.select_targets(matches, cards)
    assert [t["word"] for t in targets] == ["bank", "river"]
    assert targets[0]["card"] == cards["bank"]
    assert targets[1]["card"] is None


def test_select_targets_skips_strong_cards():
    matches = [{"word": "bank", "surface": "bank"}]
    cards = {"bank": {"state": "review", "difficulty": 2.0}}
    assert bridge.select_targets(matches, cards) == []


# --- Evidencia de dificultad (fsrs) -----------------------------------------


def test_apply_difficulty_evidence_raises_difficulty_only():
    card = fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank")
    before = dict(card)
    updated = fsrs.apply_difficulty_evidence(
        card, source="listening-evidence", now="2026-09-29T10:00:00+00:00"
    )
    assert updated is not None
    assert updated["difficulty"] == round(
        before["difficulty"] + fsrs.DIFFICULTY_EVIDENCE_DELTA, 3
    )
    # No hubo recuperación: ni repaso, ni estabilidad, ni estado.
    assert updated["reps"] == before["reps"] == 0
    assert updated["stability"] == before["stability"]
    assert updated["state"] == before["state"]
    # La palabra vuelve HOY y la razón declara el origen.
    assert updated["due_at"] == "2026-09-29T10:00:00+00:00"
    assert updated["why"] == "listening-evidence"


def test_apply_difficulty_evidence_does_not_delay_a_due_date():
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank"),
        "due_at": "2000-01-01T00:00:00+00:00",
    }
    updated = fsrs.apply_difficulty_evidence(
        card, source="listening-evidence", now="2026-09-29T10:00:00+00:00"
    )
    assert updated["due_at"] == "2000-01-01T00:00:00+00:00"


def test_apply_difficulty_evidence_is_capped():
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank"),
        "difficulty": 9.9,
    }
    updated = fsrs.apply_difficulty_evidence(
        card, source="listening-evidence", now="2026-09-29T10:00:00+00:00"
    )
    assert updated["difficulty"] == fsrs.DIFFICULTY_EVIDENCE_MAX


def test_apply_difficulty_evidence_without_card_is_none():
    assert fsrs.apply_difficulty_evidence(None, source="x") is None


def test_apply_difficulty_evidence_does_not_move_last_evidence():
    """`last_evidence_at` es el ancla de urgencia de `due_queue`: si se adelantara
    al momento del fallo, la palabra recién señalada se ordenaría la ÚLTIMA."""
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank"),
        "last_evidence_at": "2026-01-01T00:00:00+00:00",
        "reps": 3,
    }
    updated = fsrs.apply_difficulty_evidence(
        card, source="listening-evidence", now="2026-09-29T10:00:00+00:00"
    )
    assert updated["last_evidence_at"] == "2026-01-01T00:00:00+00:00"


# --- Endpoint: el puente en el fallo ----------------------------------------


def _fail(client, uid: str, q: dict, attempt: int = 1):
    return client.post(
        "/api/listening/answer",
        params={"user_id": uid},
        json={
            "question_id": q["id"],
            "answer_index": _wrong_index(q),
            "attempt_number": attempt,
        },
    )


def test_failure_raises_difficulty_of_own_words(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    words = _phrase_words(q)
    for word in words:
        _seed_word(
            uid,
            word,
            card=fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        )
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == len(words)
    assert sorted(body["difficulty_evidence"]["words"]) == sorted(words)
    for word in words:
        card = academy_repo.get_fsrs_card(uid, "lexicon", word)
        assert card["difficulty"] > 5.0
        assert card["reps"] == 0  # sin recuperación fingida
        assert card["why"] == bridge.SOURCE
        assert card["due_at"] <= datetime.now(timezone.utc).isoformat()


def test_failure_does_not_touch_words_outside_the_lexicon(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"] == {"words": [], "count": 0}
    assert listening_repo.list_difficulty_evidence(uid) == []
    assert academy_repo.list_fsrs_cards(uid) == []


def test_failure_creates_the_missing_card_of_a_word_already_owned(
    monkeypatch, tmp_path
):
    """La palabra es suya (está en su léxico) pero nunca se programó: la carta
    nace aquí, ya con la dificultad subida. No se crea VOCABULARIO nuevo."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word(uid, word)  # sin carta
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["words"] == [word]
    card = academy_repo.get_fsrs_card(uid, "lexicon", word)
    assert card is not None
    assert card["difficulty"] > 5.0
    # El léxico no se amplió con palabras de la frase que el alumno no tenía.
    assert {row["word"] for row in vocabulary_repo.get_vocabulary(uid)} == {word}


def test_failure_does_not_punish_a_demonstrated_word(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    strong = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "difficulty": 2.0,
        "reps": 5,
    }
    _seed_word(uid, word, card=strong)
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == 0
    assert academy_repo.get_fsrs_card(uid, "lexicon", word)["difficulty"] == 2.0


def test_correct_answer_touches_no_card(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        body = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        ).json()
    assert body["correct"] is True
    assert body["difficulty_evidence"] == {"words": [], "count": 0}
    assert academy_repo.get_fsrs_card(uid, "lexicon", word)["difficulty"] == 5.0


def test_evidence_records_the_phrase_that_caused_it(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q)
        _fail(client, uid, q, attempt=2)
    rows = listening_repo.list_difficulty_evidence(uid)
    # Dos fallos, dos evidencias (y una sola carta, que se acota sola).
    assert [r["question_id"] for r in rows] == [q["id"], q["id"]]
    assert [r["word"] for r in rows] == [word, word]
    assert rows[1]["difficulty_after"] > rows[0]["difficulty_after"]


def test_evidence_is_isolated_per_user(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    other = users_repo.create_user("B")["id"]
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        body = _fail(client, other, q).json()
    # El otro usuario no tiene esa palabra en su léxico: no toca NADA.
    assert body["difficulty_evidence"]["count"] == 0
    assert listening_repo.list_difficulty_evidence(other) == []
    assert academy_repo.get_fsrs_card(uid, "lexicon", word)["difficulty"] == 5.0


def test_failure_still_queues_the_phrase(monkeypatch, tmp_path):
    """El puente es ADITIVO: el contrato de V3.89 (el fallo no bloquea y encola)
    sigue exactamente igual con el puente en marcha."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["correct"] is False
    assert body["queued_for_review"] is True
    assert body["immediate_retry_available"] is True
    assert listening_repo.get_queue_entry(uid, q["id"]) is not None


# --- Métrica del día --------------------------------------------------------


def test_day_metrics_counts_evidence_and_distinct_words():
    bridge_rows = [
        {"word": "bank", "created_at": "2026-09-29T09:00:00+00:00"},
        {"word": "bank", "created_at": "2026-09-29T09:05:00+00:00"},
        {"word": "river", "created_at": "2026-09-29T09:10:00+00:00"},
        # De otro día: NO cuenta.
        {"word": "river", "created_at": "2026-09-28T09:10:00+00:00"},
    ]
    metrics = day_metrics([], [], [], "2026-09-29", bridge_rows)
    assert metrics["difficulty_evidence"] == 3
    assert metrics["words_flagged"] == 2


def test_day_metrics_without_bridge_is_zero():
    metrics = day_metrics([], [], [], "2026-09-29")
    assert metrics["difficulty_evidence"] == 0
    assert metrics["words_flagged"] == 0


def test_daily_plan_endpoint_publishes_the_bridge_metrics(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q)
        plan = client.get(
            "/api/academy/daily-plan", params={"user_id": uid}
        ).json()
    assert plan["metrics"]["difficulty_evidence"] == 1
    assert plan["metrics"]["words_flagged"] == 1


def test_daily_plan_publishes_the_word_as_pending_review(monkeypatch, tmp_path):
    """El circuito se cierra en el plan: la palabra señalada queda DEBIDA, así que
    aparece en los repasos pendientes y en la cola de retención."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_words(q, 1)[0]
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q)
        plan = client.get("/api/academy/daily-plan", params={"user_id": uid}).json()
        due = client.get(
            "/api/vocabulary/retention/due", params={"user_id": uid}
        ).json()
    assert plan["pending"]["fsrs"] >= 1
    assert word in [item["word"] for item in due["items"]]
