"""Banco de Estudiar: contadores por ámbito, tope del día y lección saltables."""
from __future__ import annotations

from fastapi.testclient import TestClient

from domain import study_bank
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_interleave_touches_every_level_before_repeating_one():
    items = [
        {"word": "ant", "cefr": "A1"},
        {"word": "ape", "cefr": "A1"},
        {"word": "boat", "cefr": "B1"},
    ]
    order = [item["cefr"] for item in study_bank.interleave_by_level(items)]
    assert order == ["A1", "B1", "A1"]


def test_learned_ignores_a_pending_step_until_the_learner_requires_it():
    card = {"state": "review"}
    pending = {"meaning": "done", "pronunciation": "pending"}
    assert study_bank.is_learned(card, pending, []) is True
    assert study_bank.is_learned(card, pending, ["pronunciation"]) is False
    # Sin JSON de lección no se retira un repaso ya consolidado.
    assert study_bank.is_learned(card, {}, []) is True
    learning = {"state": "learning"}
    assert study_bank.is_learned(learning, {"meaning": "done"}, []) is False


def test_summary_scopes_the_bank_and_picks_up_a_cefr_dictionary_row(
    monkeypatch, tmp_path
):
    user_id = _setup(monkeypatch, tmp_path)
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO dictionary_entries (word, cefr, created_at) "
            "VALUES ('zzxquark', 'B2', '2026-01-01T00:00:00')"
        )
    client = TestClient(app)
    everything = client.get(
        "/api/vocabulary/study/summary",
        params={"user_id": user_id, "scope": "all"},
    )
    assert everything.status_code == 200, everything.text
    body = everything.json()
    assert body["total"] > 10
    assert body["studied"] == 0
    assert body["times_studied"] == 0

    a1 = client.get(
        "/api/vocabulary/study/summary",
        params={"user_id": user_id, "scope": "level", "level": "A1"},
    )
    assert a1.status_code == 200
    assert 0 < a1.json()["total"] < body["total"]

    b2 = client.get(
        "/api/vocabulary/study/summary",
        params={"user_id": user_id, "scope": "level", "level": "B2"},
    )
    assert b2.status_code == 200
    index = study_bank.bank_index(vocabulary_repo.cefr_by_word(user_id))
    assert index["zzxquark"] == "B2"
    assert b2.json()["total"] >= 1

    missing = client.get(
        "/api/vocabulary/study/summary",
        params={"user_id": user_id, "scope": "deck", "deck_id": 99},
    )
    assert missing.status_code == 404


def test_queue_caps_at_words_per_day_and_mixes_levels(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    saved = client.put(
        "/api/study/config",
        params={"user_id": user_id},
        json={"words_per_day": 4},
    )
    assert saved.status_code == 200
    assert saved.json()["words_per_day"] == 4

    queued = client.get(
        "/api/vocabulary/study/queue",
        params={"user_id": user_id, "scope": "all", "mode": "all"},
    )
    assert queued.status_code == 200, queued.text
    items = queued.json()["items"]
    assert len(items) == 4
    assert len({item["cefr"] for item in items}) >= 2
    assert all(item["is_new"] for item in items)


def _queue_course_word(client: TestClient, user_id: str) -> dict:
    """Un ítem de léxico servido de verdad: una colección de una palabra del curso."""
    from repositories import collections as collections_repo

    word = next(item for item in sorted(study_bank.course_words()) if item.isalpha())
    coll = collections_repo.create_user_list(user_id, title="Una")
    assert coll is not None
    collections_repo.add_membership(user_id, int(coll["id"]), word)
    queued = client.get(
        "/api/vocabulary/study/queue",
        params={
            "user_id": user_id,
            "scope": "all",
            "mode": "all",
            "collection_id": coll["id"],
        },
    )
    assert queued.status_code == 200, queued.text
    items = queued.json()["items"]
    assert [item["word"] for item in items] == [word]
    assert items[0]["item_id"]
    return items[0]


def test_complete_enrolls_the_word_and_keeps_a_skipped_step_pending(
    monkeypatch, tmp_path
):
    user_id = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    served = _queue_course_word(client, user_id)
    assert served["word"] not in vocabulary_repo.words_of(user_id)
    done = client.post(
        "/api/vocabulary/study/complete",
        params={"user_id": user_id},
        json={
            "item_id": served["item_id"],
            "grade": 3,
            "translation": "una cosa",
            "word": "mentira",
            "facets": {
                "meaning": "done",
                "pronunciation": "pending",
                "context": "done",
                "senses": "na",
                "related": "na",
            },
        },
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["word"] == served["word"]
    assert "mentira" not in vocabulary_repo.words_of(user_id)
    assert body["facets"]["pronunciation"] == "pending"
    # La casilla de pronunciación viene apagada: el paso queda pendiente y,
    # aun así, la palabra puede contar como aprendida.
    assert body["learned"] is True
    assert served["word"] in vocabulary_repo.words_of(user_id)
    assert (
        vocabulary_repo.lesson_facets_by_word(user_id)[served["word"]]["pronunciation"]
        == "pending"
    )
    card = academy_repo.get_fsrs_card(user_id, "lexicon", served["word"])
    assert card is not None

    # Con la pronunciación obligatoria, un repaso FSRS no basta para «aprendida».
    card["state"] = "review"
    assert academy_repo.upsert_fsrs_card(user_id, card) is not None
    client.put(
        "/api/study/config",
        params={"user_id": user_id},
        json={"required_facets": ["pronunciation"]},
    )
    summary = client.get(
        "/api/vocabulary/study/summary",
        params={"user_id": user_id, "scope": "all"},
    )
    assert summary.json()["studied"] >= 1
    assert summary.json()["times_studied"] >= 1
    learned_while_required = summary.json()["learned"]

    client.put(
        "/api/study/config",
        params={"user_id": user_id},
        json={"required_facets": []},
    )
    relaxed = client.get(
        "/api/vocabulary/study/summary",
        params={"user_id": user_id, "scope": "all"},
    )
    assert relaxed.json()["learned"] == learned_while_required + 1


def test_deck_modes_stay_inside_that_deck(monkeypatch, tmp_path):
    user_id = _setup(monkeypatch, tmp_path)
    from repositories import flashcards as flashcards_repo

    tools = flashcards_repo.create_deck(user_id, name="Herramientas")
    other = flashcards_repo.create_deck(user_id, name="Otros")
    assert tools is not None and other is not None
    hammer = flashcards_repo.create_card(
        user_id, tools["id"], front="hammer", back="martillo"
    )
    saw = flashcards_repo.create_card(user_id, tools["id"], front="saw", back="sierra")
    wrench = flashcards_repo.create_card(
        user_id, tools["id"], front="wrench", back="llave"
    )
    flashcards_repo.create_card(user_id, other["id"], front="nail", back="clavo")
    assert hammer and saw and wrench

    def remember(card: dict, *, due: str, grade: int) -> None:
        scheduled = fsrs.empty_card(
            target_type="flashcard",
            target_id=str(card["id"]),
            label=card["front"],
            now="2020-01-01T00:00:00+00:00",
        )
        scheduled["due_at"] = due
        scheduled["state"] = "review"
        scheduled["reps"] = 2
        academy_repo.upsert_fsrs_card(user_id, scheduled)
        flashcards_repo.record_review(
            user_id,
            deck_id=tools["id"],
            card_type="flashcard",
            card_id=str(card["id"]),
            grade=grade,
            was_new=False,
        )

    remember(hammer, due="2099-01-01T00:00:00+00:00", grade=3)
    remember(saw, due="2099-01-01T00:00:00+00:00", grade=1)
    remember(wrench, due="2020-01-01T00:00:00+00:00", grade=3)

    client = TestClient(app)

    def words(mode: str) -> set[str]:
        response = client.get(
            "/api/vocabulary/study/queue",
            params={
                "user_id": user_id,
                "scope": "deck",
                "deck_id": tools["id"],
                "mode": mode,
            },
        )
        assert response.status_code == 200, response.text
        return {item["word"] for item in response.json()["items"]}

    assert words("pending") == {"wrench"}
    assert words("failed") == {"saw"}
    assert words("all") == {"hammer", "saw", "wrench"}


def test_list_decks_syncs_the_lexicon_once(monkeypatch, tmp_path):
    import asyncio

    from domain import academy as academy_domain
    from domain import flashcards as flashcards_domain
    from repositories import flashcards as flashcards_repo

    user_id = _setup(monkeypatch, tmp_path)
    assert flashcards_repo.create_deck(user_id, name="Uno") is not None
    assert flashcards_repo.create_deck(user_id, name="Dos") is not None
    calls = {"n": 0}
    real = academy_domain.sync_fsrs_cards

    async def wrapped(uid, now=None):
        calls["n"] += 1
        return await real(uid, now=now)

    monkeypatch.setattr(academy_domain, "sync_fsrs_cards", wrapped)
    asyncio.run(flashcards_domain.list_decks(user_id))
    assert calls["n"] == 1


def test_grade_constant_stays_in_range():
    assert fsrs.GRADE_GOOD in fsrs.GRADES
