"""V3.46 — Condición de recuperación de la transferencia (P1-03 de V3.43.0).

La auditoría de V3.43.0 (§15) señaló que `spontaneous_use` era una etiqueta
DEMASIADO amplia: no es lo mismo usar la unidad porque la tarea la nombra
(`prompted`) que recuperarla por decisión propia en un escenario abierto
(`open_context`). Sin esa dimensión, `transfer_demonstrated` podía declararse
con tareas andamiadas.

V3.46 introduce:

- la taxonomía `prompted / cued_context / open_context / free_choice /
  naturally_emergent` (`services.transfer`), con la escalera determinista
  `condition_for_state` que decide qué condición SERVIR;
- la persistencia ADITIVA de `transfer_condition` en `learning_evidence`;
- la agregación en `context_signals` y el ENDURECIMIENTO de
  `transfer_demonstrated` (exige >= 1 éxito limpio NO andamiado), con fallback
  legacy cuando el resumen no trae datos de condición;
- el contrato HTTP aditivo (`condition`/`required_target`/`unscaffolded`) y la
  regla de que un intento `open_context` que no usa la unidad NO se registra.

Premisa 21: la condición la DERIVA el servidor del estado de evidencia; el
cliente nunca la declara.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import transfer
from services.evidence import (
    context_signals,
    summarize_evidence,
    transfer_state,
    with_transfer_state,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "A1") -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


def _row(
    context_id: str,
    *,
    condition: str = "",
    error_type: str = "correct",
    day: str = "2026-01-01",
    success: int = 1,
) -> dict:
    return {
        "context_id": context_id,
        "success": success,
        "error_type": error_type,
        "occurred_at": f"{day}T10:00:00+00:00",
        "transfer_condition": condition,
    }


def _summary(rows: list[dict]) -> dict:
    summary = {
        "attempts": len(rows),
        "successes": sum(1 for row in rows if row.get("success")),
    }
    summary.update(context_signals(rows))
    return with_transfer_state(summary)


def _seed_transfer_evidence(
    uid: str, word: str, context_id: str, *, condition: str
) -> None:
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id=word,
        surface_form=word,
        lexical_unit=word,
        skill="spontaneous_use",
        task="transfer",
        activity="drill",
        activity_id="drill:transfer",
        context_id=context_id,
        success=True,
        support_level="spontaneous",
        error_type="correct",
        transfer_condition=condition,
    )


# ------------------------------------------------------------- taxonomía pura


def test_condition_vocabulary_is_declared_and_consistent():
    assert transfer.TRANSFER_CONDITIONS == (
        "prompted",
        "cued_context",
        "open_context",
        "free_choice",
        "naturally_emergent",
    )
    # Las servidas por el drill son un subconjunto de las registrables.
    assert set(transfer.SERVABLE_CONDITIONS) <= set(transfer.TRANSFER_CONDITIONS)
    assert set(transfer.UNSCAFFOLDED_CONDITIONS) <= set(transfer.TRANSFER_CONDITIONS)
    # Una condición no puede ser a la vez servible-andamiada y no andamiada: la
    # única intersección legítima es `open_context` (servible y sin andamiaje).
    assert set(transfer.SERVABLE_CONDITIONS) & set(
        transfer.UNSCAFFOLDED_CONDITIONS
    ) == {"open_context"}
    # `prompted`/`cued_context` exigen la unidad; las no andamiadas no.
    assert transfer.requires_target("prompted") is True
    assert transfer.requires_target("cued_context") is True
    assert transfer.requires_target("open_context") is False
    assert transfer.requires_target("free_choice") is False
    assert transfer.requires_target("naturally_emergent") is False
    # Sin condición declarada se conserva la semántica de V3.43.
    assert transfer.requires_target("") is True
    assert transfer.requires_target("telepatía") is True


def test_normalize_condition_is_tolerant():
    assert transfer.normalize_condition("  Open_Context ") == "open_context"
    assert transfer.normalize_condition("PROMPTED") == "prompted"
    assert transfer.normalize_condition("") == ""
    assert transfer.normalize_condition(None) == ""
    assert transfer.normalize_condition("inventada") == ""
    assert transfer.is_unscaffolded("open_context") is True
    assert transfer.is_unscaffolded("cued_context") is False
    assert transfer.is_unscaffolded("legacy") is False


def test_condition_instruction_only_prompted_names_the_word():
    assert "plan" in transfer.condition_instruction("prompted", "plan")
    assert transfer.condition_instruction("cued_context", "plan") == ""
    opened = transfer.condition_instruction("open_context", "plan")
    assert opened and "plan" not in opened


def test_condition_for_state_follows_the_scaffolding_ladder():
    # Sin intentos o con aciertos: escenario (comportamiento V3.43).
    assert (
        transfer.condition_for_state("not_ready") == "cued_context"
    )
    assert (
        transfer.condition_for_state("not_ready", attempted=True, clean_successes=1)
        == "cued_context"
    )
    assert transfer.condition_for_state("emerging") == "cued_context"
    # Intento sin ningún éxito limpio: se nombra la unidad (backoff).
    assert (
        transfer.condition_for_state(
            "not_ready", attempted=True, clean_successes=0
        )
        == "prompted"
    )
    # Ya se usa en contextos: escenario abierto que NO exige la palabra.
    for state in (
        "contextualized",
        "transfer_demonstrated",
        "transfer_stable",
        "automatic",
    ):
        assert transfer.condition_for_state(state) == "open_context"
    # Resumen desconocido/parcial: condición por defecto.
    assert transfer.condition_for_state("") == "cued_context"


# ------------------------------------------------------- consigna y contexto


def test_context_for_default_condition_is_the_v343_behaviour():
    got = transfer.context_for("travel")
    assert got["condition"] == "cued_context"
    assert got["required_target"] is True
    assert got["unscaffolded"] is False
    # V3.43 (P1-01): el escenario no contiene la unidad.
    assert "travel" not in got["prompt"].lower()


def test_context_for_prompted_names_the_word_and_requires_it():
    got = transfer.context_for("travel", condition="prompted")
    assert got["condition"] == "prompted"
    assert got["required_target"] is True
    assert got["unscaffolded"] is False
    assert "travel" in got["prompt"].lower()


def test_context_for_open_context_never_requires_the_word():
    got = transfer.context_for("travel", condition="open_context")
    assert got["condition"] == "open_context"
    assert got["required_target"] is False
    assert got["unscaffolded"] is True
    assert "travel" not in got["prompt"].lower()
    assert got["prompt"] != transfer.context_for("travel")["prompt"]


def test_context_for_normalizes_an_unknown_condition():
    got = transfer.context_for("travel", condition="inventada")
    assert got["condition"] == "cued_context"
    assert got["required_target"] is True


# ------------------------------------------------------------- evidencia pura


def test_context_signals_aggregate_conditions():
    rows = [
        _row("transfer:story", condition="cued_context"),
        _row("transfer:work", condition="cued_context"),
        _row("transfer:future", condition="open_context"),
        _row("transfer:opinion", condition="open_context", error_type="missing_target",
             success=0),
        _row("transfer:problem", error_type="correct"),  # legacy sin condición
    ]
    signals = context_signals(rows)
    assert signals["transfer_conditions"]["cued_context"] == {
        "attempts": 2,
        "clean_successes": 2,
    }
    assert signals["transfer_conditions"]["open_context"] == {
        "attempts": 2,
        "clean_successes": 1,
    }
    # Una fila legacy SIN condición no se atribuye a ninguna condición.
    assert "legacy" not in signals["transfer_conditions"]
    assert signals["success_conditions"] == ["cued_context", "open_context"]
    assert signals["unscaffolded_clean_successes"] == 1


def test_transfer_state_requires_two_unscaffolded_clean_successes():
    scaffolded = _summary(
        [
            _row("transfer:story", condition="cued_context"),
            _row("transfer:future", condition="cued_context"),
        ]
    )
    assert scaffolded["transfer"] is True  # contextos + diversidad (V3.43)
    assert scaffolded["unscaffolded_clean_successes"] == 0
    assert transfer_state(scaffolded) == "contextualized"

    # V3.47 (P1-02): UN solo éxito no andamiado ya no acredita transferencia.
    one_unscaffolded = _summary(
        [
            _row("transfer:story", condition="cued_context"),
            _row("transfer:future", condition="cued_context"),
            _row("transfer:work", condition="open_context"),
        ]
    )
    assert one_unscaffolded["unscaffolded_clean_successes"] == 1
    assert transfer_state(one_unscaffolded) == "contextualized"

    # Con DOS éxitos limpios no andamiados en contextos distintos sí se demuestra.
    opened = _summary(
        [
            _row("transfer:story", condition="cued_context"),
            _row("transfer:future", condition="cued_context"),
            _row("transfer:work", condition="open_context"),
            _row("transfer:opinion", condition="open_context"),
        ]
    )
    assert opened["unscaffolded_clean_successes"] == 2
    assert transfer_state(opened) == "transfer_demonstrated"


def test_transfer_state_keeps_the_legacy_rule_without_condition_data():
    # Filas de V3.43 (sin condición): no se puede afirmar que falte el requisito,
    # así que la regla anterior se conserva (cero regresión).
    legacy = _summary(
        [
            _row("transfer:story"),
            _row("transfer:future"),
        ]
    )
    assert legacy["transfer_conditions"] == {}
    assert transfer_state(legacy) == "transfer_demonstrated"


# --------------------------------------------------------- persistencia/paridad


def test_transfer_condition_column_is_additive_and_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    db.init_db()  # segunda pasada: la migración aditiva es idempotente
    with db._conn() as conn:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(learning_evidence)")
        }
    assert "transfer_condition" in cols


def test_record_evidence_round_trips_the_condition(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    created = evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="travel",
        context_id="transfer:story",
        success=True,
        transfer_condition="open_context",
    )
    assert created["transfer_condition"] == "open_context"
    stored = evidence_repo.list_evidence(uid, "travel")
    assert stored[0]["transfer_condition"] == "open_context"
    # Las filas sin condición quedan con '' (no se inventa una condición).
    evidence_repo.record_evidence(
        uid, target_type="lexicon", target_id="travel", success=True
    )
    assert evidence_repo.list_evidence(uid, "travel")[0]["transfer_condition"] == ""


def test_summarize_by_target_matches_the_pure_contract_with_conditions(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_transfer_evidence(uid, "travel", "transfer:story", condition="cued_context")
    _seed_transfer_evidence(uid, "travel", "transfer:future", condition="cued_context")
    _seed_transfer_evidence(uid, "travel", "transfer:work", condition="open_context")
    _seed_transfer_evidence(uid, "travel", "transfer:opinion", condition="open_context")

    sql = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    pure = summarize_evidence(evidence_repo.list_evidence(uid, "travel"))
    for key in (
        "transfer_conditions",
        "success_conditions",
        "unscaffolded_clean_successes",
        "unscaffolded_clean_success_contexts",
        "unscaffolded_clean_success_days",
        "clean_success_goals",
        "last_clean_success_at",
        "last_unscaffolded_clean_success_at",
        "transfer_state",
    ):
        assert sql[key] == pure[key]
    assert sql["unscaffolded_clean_successes"] == 2
    assert sql["transfer_state"] == "transfer_demonstrated"


# ------------------------------------------------------------------ API drill


def _post(client: TestClient, uid: str, word: str, text: str, context_id: str = ""):
    res = client.post(
        "/api/vocabulary/drill/transfer-attempt",
        params={"user_id": uid},
        json={"word": word, "text": text, "context_id": context_id},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _get_context(client: TestClient, uid: str, word: str) -> dict:
    res = client.get(
        "/api/vocabulary/drill/transfer-context",
        params={"word": word, "user_id": uid},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_api_serves_open_context_and_does_not_record_an_optional_miss(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    _seed_transfer_evidence(uid, "travel", "transfer:story", condition="cued_context")
    _seed_transfer_evidence(uid, "travel", "transfer:future", condition="cued_context")

    with TestClient(app) as client:
        served = _get_context(client, uid, "travel")
        assert served["condition"] == "open_context"
        assert served["required_target"] is False
        assert served["unscaffolded"] is True
        assert "travel" not in served["prompt"].lower()

        before = evidence_repo.list_evidence(uid, "travel")
        # La unidad NO es obligatoria: no usarla no es un fallo ni evidencia.
        miss = _post(
            client,
            uid,
            "travel",
            "I went to the beach with my family.",
            served["context_id"],
        )
        assert miss["passed"] is False
        assert miss["error_type"] == "missing_target"
        assert miss["required_target"] is False
        assert miss["condition"] == "open_context"
        assert evidence_repo.list_evidence(uid, "travel") == before

        # Usarla SÍ acredita el éxito limpio no andamiado.
        hit = _post(
            client,
            uid,
            "travel",
            "I travel to Chile every summer.",
            served["context_id"],
        )
        assert hit["passed"] is True
        assert hit["required_target"] is False
        assert hit["condition"] == "open_context"
        rows = evidence_repo.list_evidence(uid, "travel")
        assert rows[0]["transfer_condition"] == "open_context"
        summary = evidence_repo.summarize_by_target(
            uid, target_type="lexicon"
        )["travel"]
        # V3.47 (P1-02): UN éxito no andamiado aún no demuestra transferencia.
        assert summary["unscaffolded_clean_successes"] == 1
        assert transfer_state(summary) == "contextualized"

        # Un SEGUNDO contexto abierto con éxito limpio completa la demostración.
        second = _get_context(client, uid, "travel")
        assert second["condition"] == "open_context"
        second_hit = _post(
            client,
            uid,
            "travel",
            "I will travel to Chile again next winter.",
            second["context_id"],
        )
        assert second_hit["passed"] is True
        summary = evidence_repo.summarize_by_target(
            uid, target_type="lexicon"
        )["travel"]
        assert summary["unscaffolded_clean_successes"] == 2
        assert transfer_state(summary) == "transfer_demonstrated"


def test_api_serves_prompted_after_a_failure_without_clean_success(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        first = _get_context(client, uid, "travel")
        assert first["condition"] == "cued_context"
        # Intento fallido (no usa la unidad) en una condición que sí la exige: se
        # registra como evidencia y habilita el backoff a `prompted`.
        _post(
            client,
            uid,
            "travel",
            "I went to the beach yesterday.",
            first["context_id"],
        )
        second = _get_context(client, uid, "travel")
        assert second["condition"] == "prompted"
        assert second["required_target"] is True
        assert "travel" in second["prompt"].lower()

        body = _post(
            client,
            uid,
            "travel",
            "I travel by train every week.",
            second["context_id"],
        )
        assert body["condition"] == "prompted"
        assert body["passed"] is True
        rows = evidence_repo.list_evidence(uid, "travel")
        assert rows[0]["transfer_condition"] == "prompted"


def test_api_derives_the_condition_server_side_and_ignores_client_input(
    monkeypatch, tmp_path
):
    """El cliente no puede declarar una condición más espontánea que la servida."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")

    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I travel by train every week.",
                "context_id": "transfer:story",
                "condition": "naturally_emergent",  # extra ignorado por el contrato
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["condition"] == "cued_context"

    rows = evidence_repo.list_evidence(uid, "travel")
    assert rows[0]["transfer_condition"] == "cued_context"
    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    assert summary["transfer_conditions"] == {
        "cued_context": {"attempts": 1, "clean_successes": 1}
    }
