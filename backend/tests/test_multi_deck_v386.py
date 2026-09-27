"""Tests de V3.86.0: una ficha en VARIOS mazos (tabla puente) y su recordatorio.

Fija las promesas de la release que serían caras de descubrir en producción:

1. **Pertenencia N:M real.** UNA fila de ficha, N pertenencias en
   `flashcard_deck_cards`; la cola de CADA mazo la sirve —una sola vez por
   mazo— y la pestaña «Fichas» la ve una sola vez con sus mazos.
2. **El recordatorio (mnemónico) es un campo de verdad.** Viaja en el alta, se
   edita SOLO (sin reenviar el anverso) y se borra con `""`.
3. **Borrar un mazo no se lleva por delante lo compartido.** Solo caen las fichas
   huérfanas (y sus cartas FSRS) y el borrado lo DECLARA con contadores, para que
   la UI pueda avisar antes y después.
4. **Regla de no duplicar.** El mismo anverso no genera una segunda ficha al
   entrar en otro mazo: se reutiliza la que hay y se añade la pertenencia.
5. **Migración aditiva e idempotente.** Al backfill inicial de la tabla puente se
   suma la reparación de arranque de V3.86.1 (identidad fuerte + salud N:M), que
   solo toca las fichas SIN pertenencia y no resucita una retirada a propósito.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import flashcards as flashcards_repo
from repositories import users as users_repo


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


def _create_card(
    client: TestClient,
    user_id: str,
    *,
    front: str,
    back: str = "",
    mnemonic: str = "",
    deck_ids: list[int] | None = None,
):
    body: dict = {"front": front, "back": back, "mnemonic": mnemonic}
    if deck_ids is not None:
        body["deck_ids"] = deck_ids
    return client.post("/api/vocabulary/cards", params={"user_id": user_id}, json=body)


def _review(client: TestClient, user_id: str, deck_id: int, card_id: int, grade=3):
    return client.post(
        f"/api/vocabulary/decks/{deck_id}/review",
        params={"user_id": user_id},
        json={"card_type": "flashcard", "card_id": str(card_id), "grade": grade},
    )


# --- 1. Una ficha, varios mazos ---------------------------------------------


def test_a_card_lives_in_several_decks_without_duplicating_the_row(
    monkeypatch, tmp_path
):
    """El candado del cambio: 1 fila de ficha, 2 pertenencias, 2 colas."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        tools = _make_deck(client, a, "Herramientas")
        home = _make_deck(client, a, "Casa")
        created = _create_card(
            client,
            a,
            front="lima",
            back="file",
            mnemonic="la lima no es la capital",
            deck_ids=[tools, home],
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["deck_ids"] == [tools, home]
        assert body["mnemonic"] == "la lima no es la capital"

        # Una ficha (no dos) y una pertenencia por mazo.
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 1
        assert _count("flashcard_deck_cards", "deck_id IN (?, ?)", (tools, home)) == 2

        # La lista global la trae UNA vez, con sus dos mazos…
        cards = client.get("/api/vocabulary/cards", params={"user_id": a}).json()[
            "cards"
        ]
        assert len(cards) == 1
        assert cards[0]["deck_ids"] == [tools, home]

        # …y el filtro por mazo la trae desde CADA uno de ellos.
        for deck_id in (tools, home):
            listed = client.get(
                "/api/vocabulary/cards",
                params={"user_id": a, "deck_id": deck_id},
            ).json()["cards"]
            assert [c["front"] for c in listed] == ["lima"]
            # La cola de ESE mazo la sirve, y una sola vez por mazo: el
            # deduplicado del planificador no puede depender de la pertenencia.
            queue = client.get(
                f"/api/vocabulary/decks/{deck_id}/queue", params={"user_id": a}
            ).json()
            assert [i["front"] for i in queue["items"]] == ["lima"]
            assert queue["items"][0]["mnemonic"] == "la lima no es la capital"

        # Los contadores de los dos mazos la cuentan, y sale COMPARTIDA en los dos.
        decks = client.get("/api/vocabulary/decks", params={"user_id": a}).json()
        by_id = {d["id"]: d for d in decks["decks"]}
        assert by_id[tools]["card_count"] == 1
        assert by_id[home]["card_count"] == 1
        assert by_id[tools]["shared_count"] == 1
        assert by_id[home]["shared_count"] == 1


def test_adding_and_removing_memberships_one_by_one(monkeypatch, tmp_path):
    """Añadir/quitar mazo no toca el contenido; quitar el ÚLTIMO borra la ficha."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        tools = _make_deck(client, a, "Herramientas")
        home = _make_deck(client, a, "Casa")
        card_id = _create_card(
            client, a, front="lima", back="file", deck_ids=[tools]
        ).json()["id"]

        added = client.post(
            f"/api/vocabulary/cards/{card_id}/decks",
            params={"user_id": a},
            json={"deck_id": home},
        )
        assert added.status_code == 200, added.text
        assert added.json()["deck_ids"] == [tools, home]
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 1

        # Quitar una pertenencia deja la ficha viva en la otra.
        assert (
            client.delete(
                f"/api/vocabulary/cards/{card_id}/decks/{home}",
                params={"user_id": a},
            ).status_code
            == 204
        )
        assert _count("flashcard_deck_cards", "card_id = ?", (card_id,)) == 1

        # Quitar la ÚLTIMA pertenencia equivale a borrar la ficha (una ficha sin
        # mazo no existe en este modelo).
        assert (
            client.delete(
                f"/api/vocabulary/cards/{card_id}/decks/{tools}",
                params={"user_id": a},
            ).status_code
            == 204
        )
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 0
        assert _count("flashcard_deck_cards", "card_id = ?", (card_id,)) == 0


# --- 2. Recordatorio (mnemónico) --------------------------------------------


def test_mnemonic_is_edited_alone_and_can_be_cleared(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        card_id = _create_card(
            client, a, front="nebula", back="nebulosa", mnemonic="nube rara",
            deck_ids=[deck],
        ).json()["id"]

        # Editar SOLO el recordatorio no exige reenviar el anverso.
        edited = client.patch(
            f"/api/vocabulary/cards/{card_id}",
            params={"user_id": a},
            json={"mnemonic": "nebulosa = nube"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["mnemonic"] == "nebulosa = nube"
        assert edited.json()["front"] == "nebula"
        assert edited.json()["back"] == "nebulosa"

        # Y borrarlo es un `""` explícito, no un silencio.
        cleared = client.patch(
            f"/api/vocabulary/cards/{card_id}",
            params={"user_id": a},
            json={"mnemonic": ""},
        )
        assert cleared.json()["mnemonic"] == ""

        # El pegado masivo acepta el recordatorio como TERCER campo.
        bulk = client.post(
            f"/api/vocabulary/decks/{deck}/cards/bulk",
            params={"user_id": a},
            json={"text": "tornillo,screw,de rosca\nsierra,saw"},
        )
        assert bulk.status_code == 200, bulk.text
        assert bulk.json()["added"] == ["tornillo", "sierra"]
        cards = client.get(
            "/api/vocabulary/cards", params={"user_id": a, "deck_id": deck}
        ).json()["cards"]
        by_front = {c["front"]: c for c in cards}
        assert by_front["tornillo"]["mnemonic"] == "de rosca"
        assert by_front["sierra"]["mnemonic"] == ""


# --- 3. Borrar un mazo con fichas compartidas -------------------------------


def test_delete_deck_keeps_shared_cards_and_says_so(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        tools = _make_deck(client, a, "Herramientas")
        home = _make_deck(client, a, "Casa")
        shared_id = _create_card(
            client, a, front="lima", back="file", deck_ids=[tools, home]
        ).json()["id"]
        orphan_id = _create_card(
            client, a, front="sierra", back="saw", deck_ids=[tools]
        ).json()["id"]
        # Las DOS tienen carta FSRS: la de la compartida debe SOBREVIVIR.
        for card_id in (shared_id, orphan_id):
            assert _review(client, a, tools, card_id).status_code == 200

        deleted = client.delete(
            f"/api/vocabulary/decks/{tools}", params={"user_id": a}
        )
        assert deleted.status_code == 200, deleted.text
        # El borrado declara lo que hizo: 1 huérfana borrada, 1 compartida viva.
        assert deleted.json() == {"deleted_count": 1, "shared_count": 1}
        assert flashcards_repo.get_deck(a, tools) is None

        # La compartida sigue existiendo, ahora solo en su otro mazo…
        cards = client.get("/api/vocabulary/cards", params={"user_id": a}).json()[
            "cards"
        ]
        assert [c["id"] for c in cards] == [shared_id]
        assert cards[0]["deck_ids"] == [home]
        # …y con su progreso FSRS intacto.
        assert (
            academy_repo.get_fsrs_card(a, "flashcard", str(shared_id)) is not None
        )
        # La huérfana se fue, y su carta FSRS con ella (sin estado a medias).
        assert academy_repo.get_fsrs_card(a, "flashcard", str(orphan_id)) is None
        assert _count("flashcard_deck_cards", "deck_id = ?", (tools,)) == 0


# --- 4. Regla de no duplicar ------------------------------------------------


def test_the_same_front_is_reused_instead_of_duplicated(monkeypatch, tmp_path):
    """Entrar en otro mazo REUTILIZA la ficha; lo escrito no se pierde."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        tools = _make_deck(client, a, "Herramientas")
        home = _make_deck(client, a, "Casa")
        first = _create_card(
            client, a, front="lima", back="file", deck_ids=[tools]
        ).json()

        # Mismo anverso con espacios y mayúsculas distintas: es la MISMA ficha.
        again = _create_card(
            client, a, front="  LIMA ", back="file (herramienta)",
            mnemonic="no es la capital", deck_ids=[home],
        ).json()
        assert again["id"] == first["id"]
        assert again["deck_ids"] == [tools, home]
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 1
        # El reverso que se acaba de escribir no se descarta…
        assert again["back"] == "file (herramienta)"
        assert again["mnemonic"] == "no es la capital"

        # …pero un campo VACÍO no borra lo que ya había.
        third = _create_card(client, a, front="lima", deck_ids=[home]).json()
        assert third["id"] == first["id"]
        assert third["back"] == "file (herramienta)"
        assert third["mnemonic"] == "no es la capital"


def test_a_card_needs_a_real_deck_and_the_auto_deck_is_never_one(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        # Sin mazo no hay ficha: el modelo no admite fichas sueltas.
        assert _create_card(client, a, front="lima").status_code == 400
        # Y el automático es el léxico: no admite notas escritas a mano.
        assert (
            _create_card(
                client, a, front="lima", deck_ids=[flashcards_repo.AUTO_DECK_ID]
            ).status_code
            == 400
        )
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 0


def test_cards_and_memberships_do_not_cross_between_users(monkeypatch, tmp_path):
    """IDOR: el id de ficha es global, pero SIEMPRE se busca por `user_id`."""
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        a_deck = _make_deck(client, a, "De A")
        b_deck = _make_deck(client, b, "De B")
        card_id = _create_card(
            client, a, front="lima", back="file", deck_ids=[a_deck]
        ).json()["id"]

        assert client.get("/api/vocabulary/cards", params={"user_id": b}).json()[
            "cards"
        ] == []
        # B no puede editar, borrar, ni añadir a SU mazo una ficha de A.
        assert (
            client.patch(
                f"/api/vocabulary/cards/{card_id}",
                params={"user_id": b},
                json={"front": "robada"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/vocabulary/cards/{card_id}/decks",
                params={"user_id": b},
                json={"deck_id": b_deck},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/vocabulary/cards/{card_id}/decks/{b_deck}",
                params={"user_id": b},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/vocabulary/cards/{card_id}", params={"user_id": b}
            ).status_code
            == 404
        )
        # Y A sigue teniendo su ficha intacta.
        cards = client.get(
            "/api/vocabulary/cards", params={"user_id": a, "deck_id": a_deck}
        ).json()["cards"]
        assert [c["front"] for c in cards] == ["lima"]


# --- 5. Migración aditiva e idempotente -------------------------------------


def test_init_db_is_idempotent_and_backfills_only_once(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    db.init_db()
    db.init_db()

    conn = sqlite3.connect(db.DB_PATH)
    try:
        columns = {
            row[1]: row for row in conn.execute("PRAGMA table_info(flashcard_cards)")
        }
        # `mnemonic` es aditiva y con valor neutro: una BD vieja abre sin migrar.
        assert "mnemonic" in columns
        assert columns["mnemonic"][3] == 1  # NOT NULL
        assert columns["mnemonic"][4] == "''"  # DEFAULT ''
        bridge = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'flashcard_deck_cards'"
        ).fetchone()
        assert bridge is not None
        # La clave es la PAREJA: una ficha no puede repetir mazo.
        assert "PRIMARY KEY (card_id, deck_id)" in bridge[0]
    finally:
        conn.close()

    with TestClient(app) as client:
        deck = _make_deck(client, a, "Legado")

    # Estado de una BD de V3.85.1: una ficha colgando de su `deck_id` y SIN tabla
    # puente. El arranque la backfillea una vez y no más.
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO flashcard_cards "
            "(user_id, deck_id, front, created_at, updated_at) "
            "VALUES (?, ?, 'legacy', '2026-01-01', '2026-01-01')",
            (a, deck),
        )
        conn.execute("DROP TABLE flashcard_deck_cards")
        conn.commit()
    finally:
        conn.close()

    db.init_db()
    assert _count("flashcard_deck_cards", "deck_id = ?", (deck,)) == 1
    db.init_db()
    assert _count("flashcard_deck_cards", "deck_id = ?", (deck,)) == 1


# --- 6. V3.86.1: identidad fuerte, atomicidad y salud de la BD --------------


def test_concurrent_creations_of_the_same_front_do_not_duplicate(monkeypatch, tmp_path):
    """El candado del arco: dos altas a la vez del mismo anverso → 1 ficha.

    La garantía es de la BD (`UNIQUE (user_id, front_key)`), no de un SELECT
    previo: antes, dos peticiones simultáneas o un doble clic podían crear dos
    fichas del mismo anverso. Las dos pertenencias deben quedar.
    """
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        tools = _make_deck(client, a, "Herramientas")
        home = _make_deck(client, a, "Casa")

        def create(deck_id: int):
            return client.post(
                "/api/vocabulary/cards",
                params={"user_id": a},
                json={"front": "lima", "back": "file", "deck_ids": [deck_id]},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [
                future.result()
                for future in [pool.submit(create, d) for d in (tools, home)]
            ]

        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 1
        assert _count("flashcard_deck_cards", "deck_id IN (?, ?)", (tools, home)) == 2
        # Las dos respuestas hablan de la MISMA ficha, no de dos gemelas.
        assert len({r.json()["id"] for r in responses}) == 1


def test_editing_a_front_into_another_cards_front_is_a_conflict(monkeypatch, tmp_path):
    """Editar el anverso hasta el de otra ficha no crea una gemela: 409."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        _create_card(client, a, front="house", deck_ids=[deck])
        home = _create_card(client, a, front="home", deck_ids=[deck]).json()

        res = client.patch(
            f"/api/vocabulary/cards/{home['id']}",
            params={"user_id": a},
            json={"front": "  HOUSE "},  # mismo anverso normalizado
        )
        assert res.status_code == 409, res.text
        assert res.json()["detail"] == "CARD_FRONT_TAKEN"

        cards = client.get("/api/vocabulary/cards", params={"user_id": a}).json()[
            "cards"
        ]
        assert {c["front"] for c in cards} == {"house", "home"}
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 2


def test_patch_is_atomic_when_the_decks_are_invalid(monkeypatch, tmp_path):
    """Un `deck_ids` inválido no deja el resto del PATCH aplicado."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        card = _create_card(
            client, a, front="nebula", back="nebulosa", mnemonic="nube rara",
            deck_ids=[deck],
        ).json()

        res = client.patch(
            f"/api/vocabulary/cards/{card['id']}",
            params={"user_id": a},
            json={"mnemonic": "otra cosa", "deck_ids": [999_999]},
        )
        assert res.status_code == 400, res.text

        # Ni el recordatorio ni los mazos cambiaron: la transacción entera se
        # deshizo (antes el mnemónico sí quedaba escrito).
        after = client.get("/api/vocabulary/cards", params={"user_id": a}).json()[
            "cards"
        ][0]
        assert after["mnemonic"] == "nube rara"
        assert after["deck_ids"] == [deck]


def test_init_db_fuses_duplicate_cards_and_builds_the_unique_index(
    monkeypatch, tmp_path
):
    """Una BD que ya venía con duplicados se sanea al arrancar, sin perder mazos."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        tools = _make_deck(client, a, "Herramientas")
        home = _make_deck(client, a, "Casa")

    # Estado pre-V3.86.1: sin índice único y con DOS fichas del mismo anverso,
    # cada una en un mazo distinto.
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute("DROP INDEX IF EXISTS idx_flashcard_cards_identity")
        now = "2026-01-01"
        ids = []
        for deck in (tools, home):
            cur = conn.execute(
                "INSERT INTO flashcard_cards "
                "(user_id, deck_id, front, front_key, back, mnemonic, "
                " created_at, updated_at) "
                "VALUES (?, ?, 'lima', '', 'file', '', ?, ?)",
                (a, deck, now, now),
            )
            ids.append(int(cur.lastrowid))
        for card_id, deck in zip(ids, (tools, home), strict=True):
            conn.execute(
                "INSERT INTO flashcard_deck_cards (card_id, deck_id, created_at) "
                "VALUES (?, ?, ?)",
                (card_id, deck, now),
            )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    # Una sola ficha (la de id menor) y sus DOS pertenencias fusionadas: no se
    # pierde el mazo al que solo apuntaba la copia.
    assert _count("flashcard_cards", "user_id = ?", (a,)) == 1
    assert _count("flashcard_deck_cards", "card_id = ?", (ids[0],)) == 2
    conn = sqlite3.connect(db.DB_PATH)
    try:
        index = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' "
            "AND name = 'idx_flashcard_cards_identity'"
        ).fetchone()
    finally:
        conn.close()
    assert index is not None


def test_init_db_repairs_a_card_without_membership(monkeypatch, tmp_path):
    """El health check detecta una ficha huérfana y el arranque la repara."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        card = _create_card(client, a, front="lima", deck_ids=[deck]).json()

    # Migración a medias: la ficha existe, su pertenencia no.
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            "DELETE FROM flashcard_deck_cards WHERE card_id = ?", (card["id"],)
        )
        conn.commit()
    finally:
        conn.close()

    assert flashcards_repo.cards_without_deck() == 1
    db.init_db()
    assert flashcards_repo.cards_without_deck() == 0
    assert _count("flashcard_deck_cards", "card_id = ?", (card["id"],)) == 1


# --- V3.87.0: el índice de identidad también bajo carrera --------------------


def _force_identity_race(monkeypatch):
    """Simula la ventana SELECT→UPDATE: la comprobación previa NO ve el choque.

    Devuelve un dict con el contador de llamadas para poder afirmar que el rescate
    del `IntegrityError` se usó de verdad (y no el camino feliz).
    """
    real = flashcards_repo._identity_conflict_id
    calls = {"n": 0}

    def racing(conn, user_id, key, card_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(conn, user_id, key, card_id)

    monkeypatch.setattr(flashcards_repo, "_identity_conflict_id", racing)
    return calls


def test_identity_race_in_patch_is_declared_as_a_conflict(monkeypatch, tmp_path):
    """Una carrera contra el índice único sale como 409, no como IntegrityError."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        _create_card(client, a, front="house", deck_ids=[deck])
        home = _create_card(client, a, front="home", deck_ids=[deck]).json()

        calls = _force_identity_race(monkeypatch)
        res = client.patch(
            f"/api/vocabulary/cards/{home['id']}",
            params={"user_id": a},
            json={"front": "HOUSE"},  # → choca con «house» ya existente
        )
        assert res.status_code == 409, res.text
        assert res.json()["detail"] == "CARD_FRONT_TAKEN"
        assert calls["n"] >= 2, "el rescate del IntegrityError no se llegó a usar"

        # El anverso NO cambió y no hay gemela: la transacción se deshizo entera.
        after = client.get("/api/vocabulary/cards", params={"user_id": a}).json()[
            "cards"
        ]
        assert {c["front"] for c in after} == {"house", "home"}
        assert _count("flashcard_cards", "user_id = ?", (a,)) == 2


def test_identity_race_in_update_card_repo_raises_the_typed_conflict(
    monkeypatch, tmp_path
):
    """El repositorio traduce la carrera a `CardFrontConflictError` (no la escapa)."""
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        _create_card(client, a, front="house", deck_ids=[deck])
        home = _create_card(client, a, front="home", deck_ids=[deck]).json()

    calls = _force_identity_race(monkeypatch)
    with pytest.raises(flashcards_repo.CardFrontConflictError):
        flashcards_repo.update_card(a, int(home["id"]), front="HOUSE")
    assert calls["n"] >= 2
