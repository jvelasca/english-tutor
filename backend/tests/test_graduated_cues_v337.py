"""Tests de aceptación de V3.37 — cues graduados y automaticidad.

V3.36 ya CAPTURABA el CÓMO de cada evento (`support_level`, `difficulty`,
`context_id`/`activity_id`...); V3.37 USA ese apoyo para graduar la exigencia:

- la escalera de recall deja de ser un FALLBACK (traducción y, si no,
  definición) y pasa a ser una PROGRESIÓN (`translation < definition < cloze`)
  que sirve el peldaño PEDIDO y declara su `support_level`/`activity_id`;
- el `cloze` se construye de forma determinista desde el banco de
  pronunciación (`blank_out`), sin inventar contenido y sin LLM;
- `next_recall_rung` decide el siguiente peldaño por EVIDENCIA (éxitos por
  `drill:recall:<peldaño>`), y `resolve_recall_cue` degrada hacia MÁS apoyo
  cuando el peldaño ideal no tiene contenido (nunca hacia arriba);
- la automaticidad exige éxito independiente en DÍAS DISTINTOS
  (`is_automatic`), con paridad pura↔SQL del resumen.

Se cubre la capa pura, la persistencia/paridad y la captura e2e.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import evidence as evidence_svc
from services import fsrs, lexicon, recall


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _dictionary_word(word: str, translation: str, definition: str = "") -> None:
    dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=definition or f"definition of {word}",
        translation=translation,
        generator_version="test",
    )


def _evidence(uid: str, word: str) -> list[dict]:
    return evidence_repo.list_evidence(uid, word, target_type="lexicon")


def _drill_events(uid: str) -> list[str]:
    return [e["detail"] for e in learning_repo.list_events(uid, "exercise")]


def _post_recall(
    client: TestClient, uid: str, word: str, answer: str, cue=None
) -> dict:
    payload: dict = {"word": word, "answer": answer}
    if cue is not None:
        payload["cue"] = cue
    res = client.post(
        "/api/vocabulary/drill/recall-attempt",
        params={"user_id": uid},
        json=payload,
    )
    assert res.status_code == 200, res.text
    return res.json()


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
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


# --- Capa pura: la escalera ------------------------------------------------


def test_ladder_vocabulary_is_declared_and_consistent():
    assert recall.RECALL_CUES == ("translation", "definition", "cloze", "situation")
    # El apoyo declarado vive junto a la escalera, en la capa pura.
    assert recall.RECALL_CUE_SUPPORT == {
        "translation": "cued",
        "definition": "cued",
        "cloze": "guided",
        "situation": "guided",
    }
    assert set(recall.RECALL_CUE_SUPPORT) == set(recall.RECALL_CUES)
    # Todos los apoyos de la escalera pertenecen al eje canónico del ledger.
    assert set(recall.RECALL_CUE_SUPPORT.values()) <= set(
        evidence_svc.EVIDENCE_SUPPORT_LEVELS
    )


def test_blank_out_replaces_the_unit_with_a_gap():
    assert (
        recall.blank_out("My name is Lisa and I am a student.", "student")
        == "My name is Lisa and I am a _____."
    )
    # Unidad multi-palabra: se blanquea la secuencia completa.
    assert (
        recall.blank_out("My living room is big.", "living room")
        == "My _____ is big."
    )


def test_blank_out_discards_a_spoiler_or_missing_phrase():
    # Otra aparición de la diana tras blanquear: se descarta (sería un spoiler).
    assert recall.blank_out("The cat sat on the cat.", "cat") is None
    # La unidad no está en la frase (o falta la frase/diana): nunca se inventa.
    assert recall.blank_out("Hello there.", "cat") is None
    assert recall.blank_out("", "cat") is None
    assert recall.blank_out("The cat sat.", "") is None


def test_recall_prompt_for_each_rung():
    entries = [
        {
            "word": "quokka",
            "translation": "marsupial australiano",
            "definition": "a small Australian marsupial",
        }
    ]
    example = {"phrase": "The quokka is a small marsupial from Australia."}
    assert recall.recall_prompt_for(
        "quokka", entries, cue="translation"
    ) == {"word": "quokka", "cue": "marsupial australiano", "cue_kind": "translation"}
    assert recall.recall_prompt_for(
        "quokka", entries, cue="definition"
    ) == {
        "word": "quokka",
        "cue": "a small Australian marsupial",
        "cue_kind": "definition",
    }
    assert recall.recall_prompt_for(
        "quokka", entries, cue="cloze", example=example
    ) == {
        "word": "quokka",
        "cue": "The _____ is a small marsupial from Australia.",
        "cue_kind": "cloze",
    }


def test_recall_prompt_for_degrades_without_content():
    entries = [
        {
            "word": "quokka",
            "translation": "marsupial australiano",
            "definition": "a small Australian marsupial",
        }
    ]
    # Peldaño inexistente → nada.
    assert recall.recall_prompt_for("quokka", entries, cue="bogus") is None
    # Cloze sin frase real en el corpus → nada (nunca se inventa).
    assert recall.recall_prompt_for("quokka", entries, cue="cloze") is None
    # Definición que filtra la palabra → nada.
    leaky = [{"word": "bank", "translation": "", "definition": "a bank is a bank"}]
    assert recall.recall_prompt_for("bank", leaky, cue="definition") is None


def test_recall_prompt_default_is_the_v334_regression():
    with_translation = [
        {
            "word": "quokka",
            "translation": "marsupial australiano",
            "definition": "a small Australian marsupial",
        }
    ]
    # Sin cue se conserva la preferencia de V3.34: traducción.
    assert recall.recall_prompt_for("quokka", with_translation) == {
        "word": "quokka",
        "cue": "marsupial australiano",
        "cue_kind": "translation",
    }
    # Y, si no hay traducción, definición sin spoiler.
    only_definition = [
        {
            "word": "quokka",
            "translation": "",
            "definition": "a small Australian marsupial",
        }
    ]
    assert recall.recall_prompt_for("quokka", only_definition) == {
        "word": "quokka",
        "cue": "a small Australian marsupial",
        "cue_kind": "definition",
    }


def test_next_recall_rung_ascends_only_with_consolidated_evidence():
    # Sin éxito previo → primer peldaño (máximo apoyo).
    assert recall.next_recall_rung({}, {}) == "translation"
    assert recall.next_recall_rung({}, {"recall_rungs": {}}) == "translation"
    # Un solo éxito NO consolida el peldaño (V3.37.1, P1-01): sigue en él.
    one_success = {
        "recall_rungs": {"translation": 1},
        "recall_rung_days": {"translation": 1},
    }
    assert recall.next_recall_rung({}, one_success) == "translation"
    # Volumen el mismo día tampoco consolida (exige DÍAS distintos).
    same_day = {
        "recall_rungs": {"translation": 3},
        "recall_rung_days": {"translation": 1},
    }
    assert recall.next_recall_rung({}, same_day) == "translation"
    # Dos éxitos en dos días distintos SÍ superan el peldaño...
    translation_passed = {
        "recall_rungs": {"translation": 2},
        "recall_rung_days": {"translation": 2},
    }
    assert recall.next_recall_rung({}, translation_passed) == "definition"
    # ...y con `definition` consolidado, el ideal es `cloze`.
    assert (
        recall.next_recall_rung(
            {},
            {
                "recall_rungs": {"translation": 2, "definition": 2},
                "recall_rung_days": {"translation": 2, "definition": 2},
            },
        )
        == "cloze"
    )
    # V3.38: con `cloze` consolidado, el ideal es el peldaño situacional.
    assert (
        recall.next_recall_rung(
            {},
            {
                "recall_rungs": {"translation": 2, "definition": 2, "cloze": 2},
                "recall_rung_days": {"translation": 2, "definition": 2, "cloze": 2},
            },
        )
        == "situation"
    )
    # El techo de la escalera es `situation` (mantenimiento espaciado).
    assert (
        recall.next_recall_rung(
            {},
            {
                "recall_rungs": {
                    "translation": 2,
                    "definition": 2,
                    "cloze": 2,
                    "situation": 2,
                },
                "recall_rung_days": {
                    "translation": 2,
                    "definition": 2,
                    "cloze": 2,
                    "situation": 2,
                },
            },
        )
        == "situation"
    )


def test_resolve_recall_cue_degrades_down_never_up():
    rungs = {"translation", "definition", "cloze", "situation"}
    # El ideal disponible se sirve tal cual.
    assert recall.resolve_recall_cue("situation", rungs) == "situation"
    assert recall.resolve_recall_cue("cloze", rungs) == "cloze"
    assert recall.resolve_recall_cue("definition", rungs) == "definition"
    # Sin contenido, baja hacia MÁS apoyo (nunca hacia menos).
    assert recall.resolve_recall_cue("situation", {"cloze"}) == "cloze"
    assert recall.resolve_recall_cue("situation", {"definition"}) == "definition"
    assert recall.resolve_recall_cue("cloze", {"translation"}) == "translation"
    assert recall.resolve_recall_cue("definition", {"translation"}) == "translation"
    # Sin ningún peldaño disponible → None (degradación `available=false`).
    assert recall.resolve_recall_cue("situation", set()) is None
    # NUNCA sube la exigencia sin evidencia que lo justifique.
    assert recall.resolve_recall_cue("translation", {"cloze"}) is None
    assert recall.resolve_recall_cue("translation", {"definition", "cloze"}) is None
    assert recall.resolve_recall_cue("cloze", {"situation"}) is None
    assert recall.resolve_recall_cue("bogus", rungs) is None


# --- Automaticidad ----------------------------------------------------------


def test_is_automatic_requires_spaced_independent_success():
    assert evidence_svc.is_automatic({}) is False
    # Volumen sin espaciado no es automaticidad (mismo día).
    assert (
        evidence_svc.is_automatic(
            {"independent_successes": 3, "independent_success_days": 1}
        )
        is False
    )
    # Acierto suelto tampoco.
    assert (
        evidence_svc.is_automatic(
            {"independent_successes": 1, "independent_success_days": 1}
        )
        is False
    )
    assert (
        evidence_svc.is_automatic(
            {"independent_successes": 2, "independent_success_days": 2}
        )
        is True
    )


def test_cued_successes_do_not_count_as_automatic():
    # `cued` es recuperación CON apoyo: no es automaticidad.
    cued = evidence_svc.summarize_evidence(
        [
            {
                "occurred_at": "2026-09-01T10:00:00+00:00",
                "success": 1,
                "support_level": "cued",
            },
            {
                "occurred_at": "2026-09-02T10:00:00+00:00",
                "success": 1,
                "support_level": "cued",
            },
        ]
    )
    assert cued["independent_successes"] == 0
    assert cued["independent_success_days"] == 0
    assert evidence_svc.is_automatic(cued) is False
    # `spontaneous` (sin apoyo) sí cuenta.
    spontaneous = evidence_svc.summarize_evidence(
        [
            {
                "occurred_at": "2026-09-01T10:00:00+00:00",
                "success": 1,
                "support_level": "spontaneous",
            },
            {
                "occurred_at": "2026-09-02T10:00:00+00:00",
                "success": 1,
                "support_level": "spontaneous",
            },
        ]
    )
    assert spontaneous["independent_success_days"] == 2
    assert evidence_svc.is_automatic(spontaneous) is True


def test_summarize_evidence_histograms_recall_rungs():
    rows = [
        {
            "occurred_at": "2026-09-01T10:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall:translation",
        },
        {
            "occurred_at": "2026-09-02T10:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall:cloze",
        },
        {
            # Un fallo no habilita el peldaño (solo los ÉXITOS cuentan).
            "occurred_at": "2026-09-02T11:00:00+00:00",
            "success": 0,
            "activity_id": "drill:recall:cloze",
        },
        {
            # El activity_id legacy no declara peldaño: no entra.
            "occurred_at": "2026-09-02T12:00:00+00:00",
            "success": 1,
            "activity_id": "drill:recall",
        },
    ]
    out = evidence_svc.summarize_evidence(rows)
    assert out["recall_rungs"] == {"translation": 1, "cloze": 1}


def test_independent_success_days_and_rungs_pure_sql_parity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    for day, support in (
        ("2026-09-01T10:00:00+00:00", "independent"),
        ("2026-09-02T10:00:00+00:00", "spontaneous"),
    ):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            task="recall",
            activity_id="drill:recall:translation",
            success=True,
            support_level=support,
            occurred_at=day,
        )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")["river"]
    pure = evidence_svc.summarize_evidence(
        evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    )
    assert aggregated == pure
    assert aggregated["independent_success_days"] == 2  # 09-01 y 09-02
    assert aggregated["recall_rungs"] == {"translation": 2}
    assert evidence_svc.is_automatic(aggregated) is True


# --- Captura e2e del recall ------------------------------------------------


def test_recall_cloze_declares_guided_support_and_rung(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # `student` está en el banco de pronunciación: tiene cloze determinista.
    _dictionary_word("student", "estudiante")
    with TestClient(app) as client:
        body = _post_recall(client, uid, "student", "student", cue="cloze")
    assert body["correct"] is True
    row = _evidence(uid, "student")[0]
    assert row["support_level"] == "guided"
    assert row["activity_id"] == "drill:recall:cloze"


def test_recall_translation_declares_cued_support(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        body = _post_recall(client, uid, "quokka", "quokka", cue="translation")
    assert body["correct"] is True
    row = _evidence(uid, "quokka")[0]
    assert row["support_level"] == "cued"
    assert row["activity_id"] == "drill:recall:translation"


def test_recall_without_cue_keeps_the_default_rung_declared(monkeypatch, tmp_path):
    """Sin `cue` (cliente antiguo) se conserva la escalera por defecto, pero el
    ledger ya declara el peldaño realmente servido."""
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        _post_recall(client, uid, "quokka", "quokka")
    row = _evidence(uid, "quokka")[0]
    assert row["support_level"] == "cued"
    assert row["activity_id"] == "drill:recall:translation"


def test_get_prompt_serves_the_requested_rung_and_its_support(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("student", "estudiante")
    with TestClient(app) as client:
        cloze = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "student", "cue": "cloze"},
        )
        assert cloze.status_code == 200, cloze.text
        body = cloze.json()
        default = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "student"},
        ).json()
    assert body["available"] is True
    assert body["cue_kind"] == "cloze"
    assert body["support_level"] == "guided"
    assert body["cue"] == "My name is Lisa and I am a _____."
    assert "expected" not in body
    # Sin cue se conserva el comportamiento V3.34 (traducción) + apoyo declarado.
    assert default["cue"] == "estudiante"
    assert default["cue_kind"] == "translation"
    assert default["support_level"] == "cued"


def test_invalid_cue_is_422_without_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        get_res = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "quokka", "cue": "telepatía"},
        )
        post_res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "quokka", "answer": "quokka", "cue": "telepatía"},
        )
    assert get_res.status_code == 422
    assert post_res.status_code == 422
    # Sin evento: no se registra ni evidencia ni intento.
    assert _evidence(uid, "quokka") == []
    assert _drill_events(uid) == []


def test_rung_without_content_is_422_without_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # `quokka` está en la caché pero NO en el banco: no hay cloze real.
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "quokka", "answer": "quokka", "cue": "cloze"},
        )
        prompt = client.get(
            "/api/vocabulary/drill/recall",
            params={"user_id": uid, "word": "quokka", "cue": "cloze"},
        ).json()
    assert res.status_code == 422
    assert prompt["available"] is False
    assert prompt["support_level"] == "guided"
    assert _evidence(uid, "quokka") == []
    assert _drill_events(uid) == []


def test_scoring_does_not_change_with_the_rung(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("student", "estudiante")
    with TestClient(app) as client:
        cloze = _post_recall(client, uid, "student", "nope", cue="cloze")
        translation = _post_recall(
            client, uid, "student", "nope", cue="translation"
        )
    assert cloze["correct"] is False and translation["correct"] is False
    assert cloze["expected"] == translation["expected"] == "student"
    # La clasificación es la misma: el peldaño no toca el scoring.
    assert cloze["error_type"] == translation["error_type"] == "wrong_word"


# --- Cola de repaso ---------------------------------------------------------


def test_review_queue_item_exposes_recommended_cue_and_automatic():
    row = {
        "word": "student",
        "exposure_count": 2,
        "exposure_days": 2,
        "production_count": 1,
        "production_days": 1,
        "speaking_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    card = {
        "target_id": "student",
        "due_at": "2026-09-09T10:00:00+00:00",
        "state": "review",
        "stability": 5.0,
        "last_review_at": "2026-09-06T10:00:00+00:00",
    }
    evidence = {
        "independent_successes": 2,
        "independent_success_days": 2,
        "recall_rungs": {"translation": 1, "definition": 1},
    }
    item = lexicon.review_queue_item(
        row,
        card,
        now="2026-09-09T10:00:00+00:00",
        evidence=evidence,
        available_cues={"translation", "definition", "cloze"},
    )
    assert item["activity"] == "recall"
    assert item["reason"] == "automatic_maintenance"
    assert item["automatic"] is True
    assert item["recommended_cue"] == "cloze"
    # La cola nunca sirve el cue ni la forma esperada (premisa 21 / P1-03).
    assert "cue" not in item
    assert "expected" not in item


def test_review_queue_item_recommends_the_next_rung_and_resolves_content():
    row = {
        "word": "river",
        "exposure_count": 2,
        "exposure_days": 2,
        "production_count": 1,
        "production_days": 1,
        "speaking_prod": 1,
        "recall_successes": 1,
        "recall_days": 1,
    }
    card = {"target_id": "river", "due_at": "2026-09-09T10:00:00+00:00"}
    # V3.37.1: `translation` superado exige 2 éxitos en 2 días distintos.
    evidence = {
        "recall_rungs": {"translation": 2},
        "recall_rung_days": {"translation": 2},
    }
    now = "2026-09-09T10:00:00+00:00"
    # Tras superar `translation`, el ideal es `definition`...
    item = lexicon.review_queue_item(row, card, now=now, evidence=evidence)
    assert item["recommended_cue"] == "definition"
    # ...y si la definición no tiene contenido, la cola degrada hacia más apoyo.
    resolved = lexicon.review_queue_item(
        row, card, now=now, evidence=evidence, available_cues={"translation"}
    )
    assert resolved["recommended_cue"] == "translation"
    assert resolved["automatic"] is False


def test_review_queue_route_exposes_the_new_fields_without_leaking(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("student", "estudiante")
    vocabulary_repo.record_exposures(uid, ["student"])
    vocabulary_repo.record_recalls(uid, ["student"])
    vocabulary_repo.record_production(uid, ["student"], channel="speaking")
    for day in ("2026-09-01T10:00:00+00:00", "2026-09-02T10:00:00+00:00"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="student",
            task="production",
            activity_id="speaking_task",
            success=True,
            support_level="independent",
            occurred_at=day,
        )
    _due_lexicon_card(uid, "student", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        res = client.get("/api/learning/review", params={"user_id": uid})
        assert res.status_code == 200, res.text
        item = res.json()["items"][0]

    assert item["automatic"] is True
    assert item["recommended_cue"] == "cloze"
    assert "cue" not in item
    assert "expected" not in item
