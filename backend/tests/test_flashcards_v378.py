"""Tests del modo Flashcards (V3.78.0): mazos, tarjetas, cola, ledger y límites.

Cubre las cuatro promesas que este cambio hace y que serían caras de descubrir
en producción:

1. El mazo automático es VIRTUAL (id 0) y rechaza la escritura; no existe fila.
2. Los límites del día (nuevas / repasos) se aplican de verdad y salen del
   ledger `flashcard_reviews`, no de una deducción.
3. Una tarjeta manual NO se filtra al panel de REVISAR (`/api/academy/fsrs/*`),
   que es el doble escritor que M4 cerró para los objetivos.
4. El aislamiento entre usuarios se comprueba también en el cruce
   mazo↔tarjeta (IDOR), no solo por `user_id` en la consulta.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from domain import flashcards as flashcards_domain
from domain import retention as retention_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import flashcards as flashcards_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from services.evidence import classify_event_role


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _count(table: str, where: str = "1=1", params=()) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
    finally:
        conn.close()


def _make_deck(client: TestClient, user_id: str, name: str, **limits) -> int:
    res = client.post(
        "/api/vocabulary/decks",
        params={"user_id": user_id},
        json={"name": name, **limits},
    )
    assert res.status_code == 200, res.text
    return int(res.json()["id"])


def _add_card(
    client: TestClient, user_id: str, deck_id: int, front: str, back: str = ""
):
    res = client.post(
        f"/api/vocabulary/decks/{deck_id}/cards",
        params={"user_id": user_id},
        json={"front": front, "back": back},
    )
    assert res.status_code == 200, res.text
    return int(res.json()["id"])


# --- Mazos ------------------------------------------------------------------


def test_auto_deck_is_virtual_and_not_a_row(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items", params={"user_id": a}, json={"word": "ticket"}
        )
        res = client.get("/api/vocabulary/decks", params={"user_id": a})
        assert res.status_code == 200, res.text
        body = res.json()
        auto = body["decks"][0]
        assert auto["is_auto"] is True
        assert auto["id"] == flashcards_repo.AUTO_DECK_ID
        assert auto["card_count"] >= 1
        assert body["auto_deck_id"] == flashcards_repo.AUTO_DECK_ID

    # El mazo automático NO existe como fila: no hay nada que sembrar ni borrar.
    assert _count("flashcard_decks") == 0


def test_manual_deck_crud(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(
            client, a, "Phrasal verbs", new_per_day=3, review_per_day=7
        )

        renamed = client.patch(
            f"/api/vocabulary/decks/{deck_id}",
            params={"user_id": a},
            json={"name": "Phrasal verbs II", "new_per_day": 5},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Phrasal verbs II"
        assert renamed.json()["new_per_day"] == 5
        # Los límites no enviados conservan su valor.
        assert renamed.json()["review_per_day"] == 7

        deleted = client.delete(
            f"/api/vocabulary/decks/{deck_id}", params={"user_id": a}
        )
        assert deleted.status_code == 204
        assert flashcards_repo.get_deck(a, deck_id) is None


def test_auto_deck_rejects_writes(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    auto = flashcards_repo.AUTO_DECK_ID
    with TestClient(app) as client:
        assert (
            client.patch(
                f"/api/vocabulary/decks/{auto}",
                params={"user_id": a},
                json={"name": "nope"},
            ).status_code
            == 400
        )
        assert (
            client.delete(
                f"/api/vocabulary/decks/{auto}", params={"user_id": a}
            ).status_code
            == 404
        )
        # El mazo automático es el léxico: no admite tarjetas escritas a mano.
        assert (
            client.post(
                f"/api/vocabulary/decks/{auto}/cards",
                params={"user_id": a},
                json={"front": "hello"},
            ).status_code
            == 400
        )


def test_decks_are_isolated_between_users(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_a = _make_deck(client, a, "Solo de A")
        _add_card(client, a, deck_a, "hello")

        assert client.get(
            f"/api/vocabulary/decks/{deck_a}/cards", params={"user_id": b}
        ).json()["cards"] == []
        assert client.get(
            f"/api/vocabulary/decks/{deck_a}/queue", params={"user_id": b}
        ).status_code == 404
        assert client.delete(
            f"/api/vocabulary/decks/{deck_a}", params={"user_id": b}
        ).status_code == 404
        assert flashcards_repo.get_deck(a, deck_a) is not None


# --- Tarjetas ---------------------------------------------------------------


def test_card_crud_and_fsrs_cleanup(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Mío")
        card_id = _add_card(client, a, deck_id, "to look up", "consultar")

        listed = client.get(
            f"/api/vocabulary/decks/{deck_id}/cards", params={"user_id": a}
        ).json()["cards"]
        assert [c["front"] for c in listed] == ["to look up"]
        assert listed[0]["state"] == "new"
        assert listed[0]["reps"] == 0

        # Calificar crea su carta FSRS `flashcard:<id>`…
        reviewed = client.post(
            f"/api/vocabulary/decks/{deck_id}/review",
            params={"user_id": a},
            json={"card_type": "flashcard", "card_id": str(card_id), "grade": 3},
        )
        assert reviewed.status_code == 200, reviewed.text
        assert academy_repo.get_fsrs_card(a, "flashcard", str(card_id)) is not None

        edited = client.patch(
            f"/api/vocabulary/decks/{deck_id}/cards/{card_id}",
            params={"user_id": a},
            json={"front": "to look up sth", "back": "buscar algo"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["back"] == "buscar algo"

        # …y borrar la tarjeta se la lleva por delante (sin huérfanos).
        assert (
            client.delete(
                f"/api/vocabulary/decks/{deck_id}/cards/{card_id}",
                params={"user_id": a},
            ).status_code
            == 204
        )
        assert academy_repo.get_fsrs_card(a, "flashcard", str(card_id)) is None


def test_delete_deck_removes_its_fsrs_cards(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Temporal")
        card_id = _add_card(client, a, deck_id, "one")
        client.post(
            f"/api/vocabulary/decks/{deck_id}/review",
            params={"user_id": a},
            json={"card_type": "flashcard", "card_id": str(card_id), "grade": 4},
        )
        assert (
            client.delete(
                f"/api/vocabulary/decks/{deck_id}", params={"user_id": a}
            ).status_code
            == 204
        )
    assert academy_repo.get_fsrs_card(a, "flashcard", str(card_id)) is None
    assert _count("flashcard_cards", "user_id = ?", (a,)) == 0


# --- Cola y límites del día -------------------------------------------------


def test_queue_respects_new_per_day(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Tope", new_per_day=2, review_per_day=50)
        for i in range(5):
            _add_card(client, a, deck_id, f"card {i}")

        queue = client.get(
            f"/api/vocabulary/decks/{deck_id}/queue", params={"user_id": a}
        )
        assert queue.status_code == 200, queue.text
        body = queue.json()
        assert len(body["items"]) == 2
        assert all(item["is_new"] for item in body["items"])
        assert body["limits"]["new_remaining"] == 2
        assert body["new_count"] == 5  # lo que hay, sin recortar por el tope

        # Al agotar el tope, la cola se vacía; el resto espera a mañana.
        for item in body["items"]:
            client.post(
                f"/api/vocabulary/decks/{deck_id}/review",
                params={"user_id": a},
                json={
                    "card_type": item["card_type"],
                    "card_id": item["card_id"],
                    "grade": 3,
                },
            )
        after = client.get(
            f"/api/vocabulary/decks/{deck_id}/queue", params={"user_id": a}
        ).json()
        assert [i for i in after["items"] if i["is_new"]] == []
        assert after["limits"]["new_remaining"] == 0


def test_queue_respects_review_per_day(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Repasos", new_per_day=10, review_per_day=2)
        for i in range(4):
            card_id = _add_card(client, a, deck_id, f"card {i}")
            client.post(
                f"/api/vocabulary/decks/{deck_id}/review",
                params={"user_id": a},
                json={
                    "card_type": "flashcard",
                    "card_id": str(card_id),
                    "grade": 1,  # Again: vuelve a vencer enseguida
                },
            )

        queue = client.get(
            f"/api/vocabulary/decks/{deck_id}/queue", params={"user_id": a}
        ).json()
        # 4 repasos ya hechos hoy con tope de 2 → no queda cupo de repaso.
        assert queue["limits"]["review_remaining"] == 0
        assert queue["due_count"] == 0
        assert [i for i in queue["items"] if not i["is_new"]] == []


def test_auto_deck_queue_serves_lexicon_and_can_filter_by_collection(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        bulk = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": a},
            json={"text": "airport,aeropuerto\npassport,pasaporte", "title": "Travel"},
        )
        assert bulk.status_code == 200, bulk.text
        list_id = bulk.json()["collection_id"]
        assert list_id is not None
        client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "serendipity", "translation": "serendipia"},
        )

        auto = flashcards_repo.AUTO_DECK_ID
        full = client.get(
            f"/api/vocabulary/decks/{auto}/queue", params={"user_id": a}
        ).json()
        assert full["deck"]["is_auto"] is True
        fronts = {i["front"] for i in full["items"]}
        assert {"airport", "passport", "serendipity"} <= fronts
        assert all(i["card_type"] == "lexicon" for i in full["items"])
        assert all(i["is_new"] for i in full["items"])
        # La cara B sale del catálogo de la lista: la misma que ve la sesión de
        # retención, no una segunda traducción inventada aquí.
        assert next(i for i in full["items"] if i["front"] == "airport")[
            "back"
        ] == "aeropuerto"

        scoped = client.get(
            f"/api/vocabulary/decks/{auto}/queue",
            params={"user_id": a, "collection_id": list_id},
        ).json()
        scoped_fronts = {i["front"] for i in scoped["items"]}
        assert scoped_fronts == {"airport", "passport"}


def test_lexicon_card_uses_retention_writer_and_records_ledger(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/items",
            params={"user_id": a},
            json={"word": "ticket", "translation": "billete"},
        )
        auto = flashcards_repo.AUTO_DECK_ID
        queue = client.get(
            f"/api/vocabulary/decks/{auto}/queue", params={"user_id": a}
        ).json()
        item = next(i for i in queue["items"] if i["front"] == "ticket")
        assert item["back"] == "billete"

        res = client.post(
            f"/api/vocabulary/decks/{auto}/review",
            params={"user_id": a},
            json={"card_type": "lexicon", "card_id": "ticket", "grade": 4},
        )
        assert res.status_code == 200, res.text
        assert res.json()["next_in_days"] > 0

        # Ledger: una fila, marcada como nueva.
        assert _count(
            "flashcard_reviews",
            "user_id = ? AND deck_id = 0 AND card_type = 'lexicon'",
            (a,),
        ) == 1
        # Y el evento informativo lo sigue escribiendo la retención (un solo
        # escritor para la carta lexicon).
        details = [
            e["detail"]
            for e in learning_repo.list_events(a, event_type="exercise")
        ]
        assert "retention:ticket:4" in details
        assert not any(d.startswith("flashcard:ticket") for d in details)


def test_manual_card_review_writes_ledger_and_informative_event(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Notas")
        card_id = _add_card(client, a, deck_id, "on purpose", "a propósito")
        res = client.post(
            f"/api/vocabulary/decks/{deck_id}/review",
            params={"user_id": a},
            json={"card_type": "flashcard", "card_id": str(card_id), "grade": 2},
        )
        assert res.status_code == 200, res.text

    events = learning_repo.list_events(a, event_type="exercise")
    mine = [e for e in events if e["detail"] == f"flashcard:{card_id}:2"]
    assert mine
    assert mine[0]["event_role"] == "informative"
    assert classify_event_role("exercise", "flashcard:7:1") == "informative"
    assert _count("flashcard_reviews", "user_id = ?", (a,)) == 1


# --- Candado del panel de REVISAR (no debe filtrarse) ----------------------


def test_manual_cards_do_not_leak_into_fsrs_panel(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Fuera del panel")
        card_id = _add_card(client, a, deck_id, "leak check", "no debe salir")
        client.post(
            f"/api/vocabulary/decks/{deck_id}/review",
            params={"user_id": a},
            json={"card_type": "flashcard", "card_id": str(card_id), "grade": 1},
        )

        due = client.get("/api/academy/fsrs/due", params={"user_id": a}).json()
        assert all(
            c["target_type"] != "flashcard" for c in due["cards"]
        ), due
        summary = client.get("/api/academy/fsrs/summary", params={"user_id": a}).json()
        assert summary["due_count"] == 0
        # `by_type` sí conserva el total (es diagnóstico, no cola).
        assert summary["by_type"].get("flashcard", 0) >= 1

        # Y el panel tampoco puede autogradearla (single writer).
        blocked = client.post(
            "/api/academy/fsrs/review",
            params={"user_id": a},
            json={"target_type": "flashcard", "target_id": str(card_id), "grade": 4},
        )
        assert blocked.status_code in (400, 404), blocked.text


def test_review_rejects_card_of_another_user(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Privado")
        card_id = _add_card(client, a, deck_id, "secreto")

        res = client.post(
            f"/api/vocabulary/decks/{deck_id}/review",
            params={"user_id": b},
            json={"card_type": "flashcard", "card_id": str(card_id), "grade": 4},
        )
        assert res.status_code in (400, 404), res.text
    assert _count("flashcard_reviews", "user_id = ?", (b,)) == 0
    assert _count("learning_events", "user_id = ?", (b,)) == 0


def test_review_rejects_card_declared_in_another_deck(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = _make_deck(client, a, "Uno")
        second = _make_deck(client, a, "Dos")
        card_id = _add_card(client, a, first, "mía")

        res = client.post(
            f"/api/vocabulary/decks/{second}/review",
            params={"user_id": a},
            json={"card_type": "flashcard", "card_id": str(card_id), "grade": 4},
        )
        assert res.status_code in (400, 404), res.text
        assert (
            client.patch(
                f"/api/vocabulary/decks/{second}/cards/{card_id}",
                params={"user_id": a},
                json={"front": "robada"},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/vocabulary/decks/{second}/cards/{card_id}",
                params={"user_id": a},
            ).status_code
            == 404
        )


def test_review_rejects_unknown_card_type_and_grade(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Validación")
        assert (
            client.post(
                f"/api/vocabulary/decks/{deck_id}/review",
                params={"user_id": a},
                json={"card_type": "skill", "card_id": "x", "grade": 3},
            ).status_code
            == 400
        )
        assert (
            client.post(
                f"/api/vocabulary/decks/{deck_id}/review",
                params={"user_id": a},
                json={"card_type": "flashcard", "card_id": "1", "grade": 9},
            ).status_code
            == 422
        )


# --- Pegado masivo (V3.80.0) -----------------------------------------------


def test_parser_is_shared_between_lexicon_and_cards():
    """Una sola sintaxis de pegado: la misma función parte las dos pantallas.

    Si esto se rompiera, el alumno tendría que recordar dos formatos para lo que
    él ve como la misma acción («pego una lista»).
    """
    text = (
        "# comentario\n\nbreak a leg, mucha suerte\n"
        "take off\ttakeoff\n  solo anverso  \n"
    )
    assert retention_domain.parse_bulk_lines(text) == [
        ("break a leg", "mucha suerte"),
        ("take off", "takeoff"),
        ("solo anverso", ""),
    ]


def test_bulk_cards_accept_phrases_the_lexicon_would_reject(monkeypatch, tmp_path):
    """La validación NO se comparte, y es a propósito.

    El léxico normaliza palabras (minúsculas, y «2nd place» no es una palabra
    porque empieza por dígito); una tarjeta admite una frase entera tal cual se
    escribe. Compartir el parser no debe arrastrar la validación de uno al otro.
    """
    a, _b = _setup(monkeypatch, tmp_path)
    text = "Break a leg,mucha suerte\n2nd place,segundo puesto"
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Frases")
        res = client.post(
            f"/api/vocabulary/decks/{deck_id}/cards/bulk",
            params={"user_id": a},
            json={"text": text},
        )
        assert res.status_code == 200, res.text
        assert res.json()["added"] == ["Break a leg", "2nd place"]

        # El léxico, con el mismo texto: minúsculas y fuera lo que no es palabra.
        lexicon = client.post(
            "/api/vocabulary/items/bulk",
            params={"user_id": a},
            json={"text": text},
        )
        assert lexicon.status_code == 200, lexicon.text
        assert lexicon.json()["added"] == ["break a leg"]


def test_bulk_cards_dedupes_and_reports_only_what_entered(monkeypatch, tmp_path):
    """`added` cuenta lo que entró de verdad, no lo que se intentó pegar."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Con duplicados")
        res = client.post(
            f"/api/vocabulary/decks/{deck_id}/cards/bulk",
            params={"user_id": a},
            json={
                "text": "one,uno\none,otra vez\n\n# nota\n\n  ,sin anverso\ntwo,dos"
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["added"] == ["one", "two"]
        cards = client.get(
            f"/api/vocabulary/decks/{deck_id}/cards", params={"user_id": a}
        ).json()["cards"]
        assert [c["front"] for c in cards] == ["one", "two"]
        assert cards[0]["back"] == "uno"


def test_bulk_cards_are_capped_and_leave_a_schedulable_state(monkeypatch, tmp_path):
    """El tope existe y las tarjetas pegadas nacen nuevas, como las de una en una."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Grande")
        text = "\n".join(f"card {i}" for i in range(250))
        res = client.post(
            f"/api/vocabulary/decks/{deck_id}/cards/bulk",
            params={"user_id": a},
            json={"text": text},
        )
        assert res.status_code == 200, res.text
        assert res.json()["count"] == flashcards_domain.CARDS_BULK_MAX

        cards = client.get(
            f"/api/vocabulary/decks/{deck_id}/cards", params={"user_id": a}
        ).json()["cards"]
        assert len(cards) == flashcards_domain.CARDS_BULK_MAX
        assert all(c["state"] == "new" and c["reps"] == 0 for c in cards)
        # Y la cola del mazo las ve: el pegado no deja tarjetas invisibles.
        queue = client.get(
            f"/api/vocabulary/decks/{deck_id}/queue", params={"user_id": a}
        ).json()
        assert len(queue["items"]) > 0
        assert {i["front"] for i in queue["items"]} <= {
            c["front"] for c in cards
        }


def test_bulk_cards_rejects_the_auto_deck_and_other_users(
    monkeypatch, tmp_path
):
    """El mazo automático no admite escritura, y el mazo de otro tampoco."""
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.post(
                f"/api/vocabulary/decks/{flashcards_repo.AUTO_DECK_ID}/cards/bulk",
                params={"user_id": a},
                json={"text": "one,uno"},
            ).status_code
            == 400
        )
        deck_id = _make_deck(client, a, "Privado")
        assert (
            client.post(
                f"/api/vocabulary/decks/{deck_id}/cards/bulk",
                params={"user_id": b},
                json={"text": "one,uno"},
            ).status_code
            == 400
        )
        assert _count("flashcard_cards", "user_id = ?", (b,)) == 0
        # El mazo ajeno no existe para él ni para leer.
        assert client.get(
            f"/api/vocabulary/decks/{deck_id}/cards", params={"user_id": b}
        ).json()["cards"] == []


def test_bulk_cards_with_nothing_usable_is_a_no_op(monkeypatch, tmp_path):
    """Un pegado sin tarjetas válidas no es un error: es cero y se dice."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Vacío")
        res = client.post(
            f"/api/vocabulary/decks/{deck_id}/cards/bulk",
            params={"user_id": a},
            json={"text": "\n\n# solo comentarios\n   "},
        )
        assert res.status_code == 200, res.text
        assert res.json() == {"deck_id": deck_id, "added": [], "count": 0}
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 0


def test_bulk_cards_requires_a_body_with_text(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Validación")
        assert (
            client.post(
                f"/api/vocabulary/decks/{deck_id}/cards/bulk",
                params={"user_id": a},
                json={"text": ""},
            ).status_code
            == 422
        )


# --- Estadísticas -----------------------------------------------------------


def test_stats_report_today_accuracy_and_forecast(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck_id = _make_deck(client, a, "Stats")
        good = _add_card(client, a, deck_id, "good one")
        bad = _add_card(client, a, deck_id, "bad one")
        for card_id, grade in ((good, 3), (bad, 1)):
            client.post(
                f"/api/vocabulary/decks/{deck_id}/review",
                params={"user_id": a},
                json={
                    "card_type": "flashcard",
                    "card_id": str(card_id),
                    "grade": grade,
                },
            )

        stats = client.get(
            f"/api/vocabulary/decks/{deck_id}/stats", params={"user_id": a}
        )
        assert stats.status_code == 200, stats.text
        body = stats.json()
        assert body["cards_total"] == 2
        assert body["reviewed_today"] == 2
        assert body["new_today"] == 2
        assert body["reviews_30d"] == 2
        assert body["accuracy_30d"] == 50.0
        assert len(body["forecast"]) == 7
        assert body["by_day"] and body["by_day"][-1]["total"] == 2

        auto_stats = client.get(
            "/api/vocabulary/decks/0/stats", params={"user_id": a}
        )
        assert auto_stats.status_code == 200
        assert auto_stats.json()["deck"]["is_auto"] is True
