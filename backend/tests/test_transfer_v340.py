"""V3.40 (Fase 4) — transferencia contextual real y gobierno por `lexical_unit`.

La auditoría de V3.38.1 (P1-03) recordó que `situation` (completar un hueco) es
recuperación CONTEXTUALIZADA, no transferencia: transferir es usar la unidad en
un contexto DISTINTO del de aprendizaje. Esta fase cierra dos huecos:

- la modalidad `spontaneous_use` (se medía pero no tenía tarea): nueva actividad
  `transfer` del drill, con consigna de un contexto NUEVO
  (`services.transfer`), scoring determinista, evidencia
  `activity_id="drill:transfer"` + `context_id` del contexto nuevo;
- el estado pedagógico por `lexical_unit` (P1-04): `lexicon.unit_evidence`
  agrega irregulares/chunks (go/went/gone/going) sin tocar la evidencia por
  forma.

Se mantiene "señal ≠ evidencia": el drill no declara dominio ni toca FSRS (D5/E3).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import evidence as evidence_repo
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, planner, transfer
from services.evidence import context_signals, transfer_state


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(
    a: str, word: str, *, lemma: str = "", cefr: str = "A1"
) -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": lemma or word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


def _due_lexicon_card(uid: str, word: str) -> None:
    """Carta FSRS `lexicon` ya revisada y VENCIDA (due ayer)."""
    now = datetime.now(timezone.utc)
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": 5.0,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": (now - timedelta(days=3)).isoformat(),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


def _post_transfer(
    client: TestClient,
    uid: str,
    word: str,
    text: str,
    context_id: str = "",
) -> dict:
    res = client.post(
        "/api/vocabulary/drill/transfer-attempt",
        params={"user_id": uid},
        json={
            "word": word,
            "text": text,
            "context_id": context_id,
            "response_time_ms": 5200,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


# ------------------------------------------------- banco de contextos (puro)


def test_context_for_prefers_a_context_the_item_never_used():
    got = transfer.context_for("travel", used_context_ids=["transfer:story"])
    assert got["available"] is True
    assert got["context_id"] != "transfer:story"
    assert got["context_id"].startswith("transfer:")
    assert got["prompt"]
    # V3.43 (P1-01): la consigna NUNCA contiene la unidad objetivo.
    assert "travel" not in got["prompt"].lower()


def test_context_for_is_deterministic_and_stable_across_calls():
    first = transfer.context_for("travel")
    second = transfer.context_for("travel")
    assert first["context_id"] == second["context_id"]
    # Estabilidad entre procesos: la elección NO usa el `hash()` sembrado.
    assert transfer._stable_index("travel", len(transfer.TRANSFER_CONTEXTS)) == (
        transfer._stable_index("travel", len(transfer.TRANSFER_CONTEXTS))
    )


def test_context_for_rotates_when_the_bank_is_exhausted():
    used = [transfer.context_id_for(c) for c in transfer.TRANSFER_CONTEXTS]
    got = transfer.context_for("travel", used_context_ids=used)
    assert got["available"] is True
    assert got["context_id"] in used
    # Con el banco agotado la elección es por rotación estable.
    assert got["exhausted"] is True


def test_context_for_survives_a_non_iterable_and_empty_word():
    assert transfer.context_for("")["available"] is True
    assert transfer.context_for("travel", used_context_ids=42)["available"] is True
    assert transfer.context_for("travel", used_context_ids={})["available"] is True


# --------------------------------------------------------- señales de contexto


def test_context_signals_count_transfer_by_distinct_success_contexts():
    rows = [
        {"context_id": "lexicon:writing", "success": 1},
        {"context_id": "lexicon:writing", "success": 1},
        {"context_id": "drill:recall", "success": 0},
    ]
    signals = context_signals(rows)
    assert signals["contexts"]["lexicon:writing"] == {
        "attempts": 2,
        "successes": 2,
    }
    assert signals["success_contexts"] == ["lexicon:writing"]
    assert signals["home_context"] == "lexicon:writing"
    assert signals["transfer"] is False
    # V3.43 (P1-03): un contexto NO reconocido del banco no aporta diversidad;
    # con un único contexto del banco la transferencia sigue sin demostrarse.
    rows.append({"context_id": "transfer:story", "success": 1})
    assert context_signals(rows)["transfer"] is False
    # Dos contextos del banco con dimensiones distintas: transferencia real.
    rows.append({"context_id": "transfer:future", "success": 1})
    diverse = context_signals(rows)
    assert diverse["transfer"] is True
    assert set(diverse["clean_success_contexts"]) == {
        "lexicon:writing",
        "transfer:future",
        "transfer:story",
    }
    assert diverse["context_diversity"]["diverse_dimensions"] >= 2


def test_transfer_gap_and_has_contextual_transfer():
    learning = {
        "contexts": {"lexicon:writing": {"attempts": 2, "successes": 2}},
        "context_attempts": 1,
        "success_contexts": ["lexicon:writing"],
        "transfer": False,
    }
    assert planner.transfer_gap(learning) is True
    assert planner.has_contextual_transfer(learning) is False

    transferred = dict(learning)
    transferred["contexts"] = {
        "lexicon:writing": {"attempts": 2, "successes": 2},
        "transfer:story": {"attempts": 1, "successes": 1},
    }
    transferred["context_attempts"] = 2
    transferred["success_contexts"] = ["lexicon:writing", "transfer:story"]
    transferred["transfer"] = True
    assert planner.transfer_gap(transferred) is False
    assert planner.has_contextual_transfer(transferred) is True


def test_transfer_gap_does_not_fire_without_enough_successes_or_context():
    assert planner.transfer_gap({}) is False
    assert planner.transfer_gap({"contexts": {}}) is False
    only_one = {
        "contexts": {"lexicon:writing": {"attempts": 1, "successes": 1}},
        "context_attempts": 1,
        "success_contexts": ["lexicon:writing"],
        "transfer": False,
    }
    # Un solo éxito: aún se está aprendiendo, no toca transferir.
    assert planner.transfer_gap(only_one) is False
    # Dos éxitos pero SIEMPRE en el mismo contexto: aún no hay transferencia que
    # pedir (ya se usó ese contexto); el hueco se declara con >= 2 éxitos.
    same_context = {
        "contexts": {"lexicon:writing": {"attempts": 2, "successes": 2}},
        "context_attempts": 1,
        "success_contexts": ["lexicon:writing"],
        "transfer": False,
    }
    assert planner.transfer_gap(same_context) is True
    # Sin contextos registrados no se inventa la transferencia.
    assert planner.transfer_gap({"context_attempts": 0, "transfer": False}) is False


def test_select_task_routes_to_transfer_when_everything_else_is_covered():
    matrix = {"recognition": True, "recall": True, "production": True}
    evidence = {
        "skill_attempts": {"recall": 3, "spoken_production": 1},
        "skill_successes": {
            "recall": 3,
            "spoken_production": 1,
            "written_production": 1,
        },
        "skill_independent_successes": {"recall": 3},
        "skill_mean_response_time_ms": {"recall": 900},
        "recent_wrong_word": 0,
        "recent_error_rate": 0.0,
        "contexts": {"lexicon:writing": {"attempts": 2, "successes": 2}},
        "context_attempts": 1,
        "success_contexts": ["lexicon:writing"],
        "transfer": False,
    }
    task = planner.select_task(matrix, evidence)
    assert task["skill"] == planner.TRANSFER_SKILL
    assert task["activity"] == "transfer"
    assert task["reason"] == "transfer_gap"
    assert task["support_level"] == "spontaneous"


# ---------------------------------------------------------- unidad léxica


def test_unit_evidence_rolls_up_the_forms_of_an_irregular():
    rows = [
        {"word": "go", "lexical_unit": "go"},
        {"word": "went", "lexical_unit": "go"},
        {"word": "gone", "lexical_unit": "go"},
    ]
    summaries = {
        "go": {
            "attempts": 2,
            "successes": 2,
            "distinct_success_days": 1,
            "success_contexts": ["lexicon:recall"],
            "automatic_skills": ["recall"],
            "skill_attempts": {"recall": 2},
            "skill_successes": {"recall": 2},
        },
        "went": {
            "attempts": 1,
            "successes": 0,
            "error_types": {"wrong_word": 1},
            "success_contexts": ["transfer:story"],
        },
    }
    units = lexicon.unit_evidence(rows, summaries)
    assert len(units) == 1
    unit = units[0]
    assert unit["lexical_unit"] == "go"
    assert unit["surfaces"] == ["go", "gone", "went"]
    assert unit["attempts"] == 3
    assert unit["successes"] == 2
    assert unit["success_rate"] == round(2 / 3, 4)
    assert unit["error_types"] == {"wrong_word": 1}
    assert unit["automatic"] is True
    assert unit["automatic_skills"] == ["recall"]
    assert unit["success_contexts"] == ["lexicon:recall", "transfer:story"]
    assert unit["transfer"] is True


def test_unit_evidence_ignores_rows_without_unit_or_word():
    assert lexicon.unit_evidence([{"word": "", "lexical_unit": "go"}]) == []
    assert lexicon.unit_evidence([{"word": "go", "lexical_unit": ""}])[0][
        "lexical_unit"
    ] == "go"


# ------------------------------------------------------------- endpoints


def test_transfer_context_endpoint_is_read_only_and_new(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    before = evidence_repo.list_evidence(uid, "travel")
    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"user_id": uid, "word": "travel"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] is True
    assert body["context_id"].startswith("transfer:")
    # V3.43 (P1-01): la consigna da un escenario, nunca la unidad objetivo.
    assert body["prompt"]
    assert "travel" not in body["prompt"].lower()
    assert body["communicative_goal"]
    assert body["discourse_type"]
    # El GET no escribe nada.
    assert evidence_repo.list_evidence(uid, "travel") == before
    # Pero el contexto nuevo queda en el ledger al intentar.
    with TestClient(app) as client:
        _post_transfer(
            client, uid, "travel", "I will travel next summer.", body["context_id"]
        )
    summaries = evidence_repo.summarize_by_target(uid, target_type="lexicon")
    assert body["context_id"] in summaries["travel"]["contexts"]


def test_transfer_attempt_passed_accredits_spontaneous_use(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        body = _post_transfer(
            client,
            uid,
            "travel",
            "If I had time, I would travel to Japan.",
            "transfer:story",
        )

    assert body["passed"] is True
    assert body["used_word"] is True
    assert body["context_id"] == "transfer:story"

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["travel"]["writing_prod"] == 1

    events = learning_repo.list_events(uid, "exercise")
    assert any(e["detail"] == "drill:travel:transfer:ok" for e in events)

    rows = evidence_repo.list_evidence(uid, "travel")
    assert len(rows) == 1
    event = rows[0]
    assert event["skill"] == "spontaneous_use"
    assert event["task"] == "transfer"
    assert event["activity_id"] == "drill:transfer"
    assert event["context_id"] == "transfer:story"
    assert event["support_level"] == "spontaneous"
    assert event["success"] == 1
    assert event["response_time_ms"] == 5200


def test_transfer_attempt_failure_is_recorded_and_never_accredits(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        body = _post_transfer(client, uid, "travel", "travel", "transfer:story")

    assert body["passed"] is False
    assert body["error_type"] == "too_short"
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["travel"]["writing_prod"] == 0

    rows = evidence_repo.list_evidence(uid, "travel")
    assert len(rows) == 1
    assert rows[0]["success"] == 0
    assert rows[0]["skill"] == "spontaneous_use"


def test_two_diverse_contexts_need_two_unscaffolded_successes(monkeypatch, tmp_path):
    """V3.46 (P1-03) → V3.47 (P1-02): dos contextos distintos con ayuda NO
    demuestran transferencia; hacen falta DOS éxitos limpios SIN andamiaje
    (`open_context`), no uno."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        _post_transfer(
            client, uid, "travel", "I travel to work by train.", "transfer:work"
        )
        _post_transfer(
            client, uid, "travel", "I always travel to work by bus.", "transfer:work"
        )
        first = evidence_repo.summarize_by_target(
            uid, target_type="lexicon"
        )["travel"]
        assert first["transfer"] is False
        # Dos éxitos, pero en un solo contexto: toca transferir al siguiente.
        assert planner.transfer_gap(first) is True

        # Contexto distinto con diversidad real, pero aún ANDAMIADO
        # (`cued_context`): la unidad se usa, no se demuestra transferencia.
        _post_transfer(
            client,
            uid,
            "travel",
            "Next year I will travel to Chile.",
            "transfer:future",
        )
        scaffolded = evidence_repo.summarize_by_target(
            uid, target_type="lexicon"
        )["travel"]
        assert scaffolded["transfer"] is True
        assert scaffolded["clean_success_contexts"] == [
            "transfer:future",
            "transfer:work",
        ]
        assert scaffolded["unscaffolded_clean_successes"] == 0
        assert transfer_state(scaffolded) == "contextualized"
        assert planner.transfer_gap(scaffolded) is True

        # Estado `contextualized` → el drill sirve `open_context`, que NO exige la
        # unidad: un éxito limpio aquí es el PRIMER uso sin ayuda (aún no basta).
        served = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        ).json()
        assert served["condition"] == "open_context"
        assert served["required_target"] is False
        _post_transfer(
            client,
            uid,
            "travel",
            "I travel to Chile every summer.",
            served["context_id"],
        )

        one = evidence_repo.summarize_by_target(
            uid, target_type="lexicon"
        )["travel"]
        assert one["unscaffolded_clean_successes"] == 1
        assert transfer_state(one) == "contextualized"

        # Un SEGUNDO contexto abierto con éxito limpio completa la demostración.
        second = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        ).json()
        assert second["condition"] == "open_context"
        _post_transfer(
            client,
            uid,
            "travel",
            "I will travel to Chile again next winter.",
            second["context_id"],
        )

    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    assert summary["unscaffolded_clean_successes"] == 2
    assert summary["success_conditions"] == ["cued_context", "open_context"]
    assert transfer_state(summary) == "transfer_demonstrated"
    assert planner.transfer_gap(summary) is False


def test_review_queue_exposes_units_and_unit_surfaces(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "go")
    _seed_word(uid, "went", lemma="go")
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="went",
        surface_form="went",
        lexical_unit="go",
        skill="spoken_production",
        success=True,
        support_level="independent",
    )
    _due_lexicon_card(uid, "go")
    with TestClient(app) as client:
        res = client.get("/api/learning/review", params={"user_id": uid})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "units" in body
    units = {u["lexical_unit"]: u for u in body["units"]}
    assert units["go"]["surfaces"] == ["go", "went"]
    assert units["go"]["attempts"] == 1
    assert units["go"]["successes"] == 1
    assert units["go"]["skill_successes"] == {"spoken_production": 1}
    assert body["items"], "la carta vencida debe servirse"
    for item in body["items"]:
        assert isinstance(item["unit_surfaces"], list)
        assert isinstance(item["transfer"], bool)
        assert isinstance(item["success_contexts"], list)
    assert body["items"][0]["unit_surfaces"] == ["go", "went"]
