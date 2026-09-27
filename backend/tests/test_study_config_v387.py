"""Tests de V3.87.0 · FASE 2 (incremento 1): configuración de estudio.

Fija las promesas de la release que serían caras de descubrir en producción:

1. **La preferencia es del alumno y se normaliza.** Un valor desconocido cae al
   defecto (nunca rompe la sesión); un PATCH parcial no toca lo demás; y el
   defecto NO cambia nada hasta que el alumno guarda (no-regresión declarada).
2. **La dirección es PRESENTACIÓN.** `front`/`back` no cambian; `prompt`/`answer`
   se intercambian y la ayuda (`hint`) va en la cara de la pregunta, nunca la
   respuesta.
3. **La carga se siente sin tocar el calendario.** `gentle` recorta el techo de
   nuevas; `intensive` sirve los repasos que vencen en 24 h SIN reescribir su
   `due_at`.
4. **El Planner 3.0 solo FILTRA actividades.** El modo restringe las candidatas
   (una razón de producción no se sirve en modo reconocimiento y al revés), y un
   filtro que dejaría el conjunto vacío NO vacía la sesión (fallback declarado).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from domain import flashcards as flashcards_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, planner, study_config


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _make_deck(client: TestClient, user_id: str, name: str, **limits) -> int:
    res = client.post(
        "/api/vocabulary/decks",
        params={"user_id": user_id},
        json={"name": name, **limits},
    )
    assert res.status_code == 200, res.text
    return int(res.json()["id"])


def _create_card(
    client: TestClient, user_id: str, *, front: str, back: str = "",
    mnemonic: str = "", deck_ids: list[int] | None = None,
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


def _get_config(client: TestClient, user_id: str) -> dict:
    res = client.get("/api/study/config", params={"user_id": user_id})
    assert res.status_code == 200, res.text
    return res.json()


def _put_config(client: TestClient, user_id: str, patch: dict) -> dict:
    res = client.put("/api/study/config", params={"user_id": user_id}, json=patch)
    assert res.status_code == 200, res.text
    return res.json()


def _queue(client: TestClient, user_id: str, deck_id: int) -> dict:
    res = client.get(
        f"/api/vocabulary/decks/{deck_id}/queue", params={"user_id": user_id}
    )
    assert res.status_code == 200, res.text
    return res.json()


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    """Carta FSRS `lexicon` ya revisada y VENCIDA (due ayer)."""
    now = datetime.now(timezone.utc)
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": (now - timedelta(days=days_ago)).isoformat(),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


# --- 1. Normalización (pura) -------------------------------------------------


def test_normalize_falls_back_to_defaults_and_accepts_case():
    assert study_config.normalize_study_config(None) == {
        "direction": "en-es",
        "mode": "recognition",
        "hints": "off",
        "difficulty": "auto",
    }
    # Basura y valores fuera del contrato → defecto, sin lanzar.
    assert study_config.normalize_study_config(["no", "es", "un", "dict"])[
        "mode"
    ] == "recognition"
    partial = study_config.normalize_study_config({"mode": "NOPE", "hints": " All "})
    assert partial["mode"] == "recognition"
    assert partial["hints"] == "all"
    assert study_config.normalize_study_config({"direction": "ES-EN"})[
        "direction"
    ] == "es-en"


def test_allowed_activities_and_fallback_activity():
    assert (
        study_config.allowed_activities({"mode": "recognition"})
        == study_config.RECOGNITION_ACTIVITIES
    )
    assert (
        study_config.allowed_activities({"mode": "production"})
        == study_config.PRODUCTION_ACTIVITIES
    )
    assert study_config.allowed_activities({"mode": "mixed"}) is None
    assert study_config.allowed_activities(None) is None

    # Reconocimiento no produce: una razón de producción baja a `recall`.
    assert (
        study_config.fallback_activity("sentence", study_config.RECOGNITION_ACTIVITIES)
        == "recall"
    )
    # Producción sube la recuperación a construir…
    assert (
        study_config.fallback_activity("recall", study_config.PRODUCTION_ACTIVITIES)
        == "sentence"
    )
    # …pero sin base receptiva NO se fuerza a producir.
    assert (
        study_config.fallback_activity(
            "recognition", study_config.PRODUCTION_ACTIVITIES
        )
        == "recognition"
    )
    # Sin filtro, no se toca nada.
    assert study_config.fallback_activity("recall", None) == "recall"


# --- 2. Caras por dirección y ayudas (pura) ----------------------------------


def test_faces_by_direction_and_hints():
    entry = {
        "front": "house",
        "back": "casa",
        "definition": "a building",
        "mnemonic": "hogar",
    }
    assert flashcards_domain._faces(entry, {"direction": "en-es", "hints": "off"}) == (
        "house",
        "casa",
        "",
    )
    assert flashcards_domain._faces(entry, {"direction": "es-en", "hints": "off"}) == (
        "casa",
        "house",
        "",
    )
    assert flashcards_domain._faces(entry, {"direction": "en-es", "hints": "all"}) == (
        "house",
        "casa",
        "a building\nhogar",
    )
    assert flashcards_domain._faces(
        entry, {"direction": "es-en", "hints": "definition"}
    ) == ("casa", "house", "a building")
    assert flashcards_domain._faces(
        entry, {"direction": "es-en", "hints": "mnemonic"}
    ) == ("casa", "house", "hogar")
    # ES→EN sin traducción: el prompt cae al inglés antes que quedar en blanco.
    assert flashcards_domain._faces({"front": "house", "back": ""}, {
        "direction": "es-en"
    })[0] == "house"


# --- 3. API de configuración -------------------------------------------------


def test_config_endpoint_defaults_partial_merge_and_persistence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert _get_config(client, a) == {
            "direction": "en-es",
            "mode": "recognition",
            "hints": "off",
            "difficulty": "auto",
            "configured": False,
        }
        # PATCH parcial: solo cambia lo enviado.
        saved = _put_config(client, a, {"mode": "production"})
        assert saved["mode"] == "production"
        assert saved["direction"] == "en-es"
        assert saved["configured"] is True

        saved = _put_config(client, a, {"direction": "es-en", "hints": "all"})
        assert saved["mode"] == "production"  # se conserva
        assert saved["direction"] == "es-en"
        assert saved["hints"] == "all"

        # Persiste entre peticiones.
        assert _get_config(client, a)["mode"] == "production"


def test_config_is_per_user_and_rejects_unknown_values(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _put_config(client, a, {"mode": "production"})
        # B nunca guardó nada: sigue en los defectos.
        assert _get_config(client, b)["mode"] == "recognition"
        assert _get_config(client, b)["configured"] is False

        # Un valor fuera de los `Literal` lo rechaza el contrato de la API.
        res = client.put(
            "/api/study/config", params={"user_id": a}, json={"mode": "listen"}
        )
        assert res.status_code == 422, res.text


# --- 4. La cola aplica dirección, ayudas y carga -----------------------------


def test_queue_exposes_direction_hint_and_config(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        card = _create_card(
            client, a, front="house", back="casa", mnemonic="hogar",
            deck_ids=[deck],
        ).json()

        # Sin configurar: la cara preguntada es el anverso y no hay ayuda.
        default_body = _queue(client, a, deck)
        default_item = default_body["items"][0]
        assert default_item["prompt"] == "house"
        assert default_item["answer"] == "casa"
        assert default_item["hint"] == ""
        assert default_body["study_config"]["configured"] is False

        _put_config(client, a, {"direction": "es-en", "hints": "mnemonic"})
        body = _queue(client, a, deck)
        item = body["items"][0]
        # La identidad de la ficha NO cambia; sí la presentación.
        assert item["front"] == "house" and item["back"] == "casa"
        assert item["prompt"] == "casa"
        assert item["answer"] == "house"
        assert item["hint"] == "hogar"
        assert body["study_config"]["direction"] == "es-en"
        assert body["study_config"]["configured"] is True
        assert item["card_id"] == str(card["id"])


def test_gentle_halves_the_new_cap(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa", new_per_day=10)
        _create_card(client, a, front="house", back="casa", deck_ids=[deck])

        assert _queue(client, a, deck)["limits"]["new_per_day"] == 10
        _put_config(client, a, {"difficulty": "gentle"})
        assert _queue(client, a, deck)["limits"]["new_per_day"] == 5


def test_intensive_serves_reviews_due_within_24h_without_touching_schedule(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        deck = _make_deck(client, a, "Casa")
        card = _create_card(
            client, a, front="house", back="casa", deck_ids=[deck]
        ).json()
        assert _review(client, a, deck, card["id"], grade=3).status_code == 200

        # Se adelanta el vencimiento a 2 h (dentro de la ventana de `intensive`),
        # SIN pasar por FSRS: el calendario no lo toca la configuración.
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        conn = sqlite3.connect(db.DB_PATH)
        try:
            conn.execute(
                "UPDATE fsrs_cards SET due_at = ? "
                "WHERE user_id = ? AND target_type = 'flashcard' AND target_id = ?",
                (future, a, str(card["id"])),
            )
            conn.commit()
        finally:
            conn.close()

        auto_ids = {i["card_id"] for i in _queue(client, a, deck)["items"]}
        assert str(card["id"]) not in auto_ids  # todavía no vence

        _put_config(client, a, {"difficulty": "intensive"})
        intensive_ids = {i["card_id"] for i in _queue(client, a, deck)["items"]}
        assert str(card["id"]) in intensive_ids  # se sirve dentro de 24 h

        # El `due_at` guardado sigue siendo el de 2 h: no se reescribió.
        conn = sqlite3.connect(db.DB_PATH)
        try:
            row = conn.execute(
                "SELECT due_at FROM fsrs_cards WHERE user_id = ? "
                "AND target_type = 'flashcard' AND target_id = ?",
                (a, str(card["id"])),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == future


# --- 5. Planner 3.0: solo filtra actividades --------------------------------


def test_recommend_activity_respects_allowed_activities():
    recognized = {
        "exposure_count": 3,
        "production_count": 0,
        "last_exposed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert lexicon.recommend_review_activity(recognized)["activity"] == "recall"
    # Modo producción: la recuperación sube a construir en contexto.
    assert (
        lexicon.recommend_review_activity(
            recognized, allowed_activities=study_config.PRODUCTION_ACTIVITIES
        )["activity"]
        == "sentence"
    )
    assert (
        lexicon.recommend_review_activity(
            recognized, allowed_activities=study_config.RECOGNITION_ACTIVITIES
        )["activity"]
        == "recall"
    )
    # Producción sobre un ítem sin base receptiva: se respeta `recognition`.
    weak = {"exposure_count": 0, "production_count": 0}
    assert (
        lexicon.recommend_review_activity(
            weak, allowed_activities=study_config.PRODUCTION_ACTIVITIES
        )["activity"]
        == "recognition"
    )


def test_task_candidates_filter_and_empty_fallback():
    # `recall` (error_prone) + los huecos de producción de la matriz.
    evidence = {"recent_wrong_word": 99, "skill_successes": {"recall": 1}}
    matrix = {"production": True}

    base = {c["activity"] for c in planner.task_candidates(matrix, evidence)}
    assert "recall" in base
    assert base & set(study_config.PRODUCTION_ACTIVITIES)

    production = {
        c["activity"]
        for c in planner.task_candidates(
            matrix, evidence, allowed_activities=study_config.PRODUCTION_ACTIVITIES
        )
    }
    assert "recall" not in production
    assert production & set(study_config.PRODUCTION_ACTIVITIES)

    recognition = {
        c["activity"]
        for c in planner.task_candidates(
            matrix, evidence, allowed_activities=study_config.RECOGNITION_ACTIVITIES
        )
    }
    assert recognition == {"recall"}

    # Fallback: sin candidatas de producción, el filtro NO vacía la sesión.
    fallback = {
        c["activity"]
        for c in planner.task_candidates(
            {"production": False},
            {"recent_wrong_word": 99},
            allowed_activities=study_config.PRODUCTION_ACTIVITIES,
        )
    }
    assert fallback == {"recall"}


def test_review_queue_endpoint_honours_saved_mode(monkeypatch, tmp_path):
    """El defecto no cambia la cola; un modo guardado sí la filtra."""
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["river"])
    _due_lexicon_card(a, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        # Sin configurar: comportamiento de V3.86.1 (recuperación).
        body = client.get("/api/learning/review", params={"user_id": a}).json()
        assert body["items"][0]["activity"] == "recall"

        _put_config(client, a, {"mode": "production"})
        body = client.get("/api/learning/review", params={"user_id": a}).json()
        assert body["items"][0]["activity"] == "sentence"

        _put_config(client, a, {"mode": "recognition"})
        body = client.get("/api/learning/review", params={"user_id": a}).json()
        assert body["items"][0]["activity"] == "recall"
