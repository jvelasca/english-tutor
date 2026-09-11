"""Tests de V3.36 — Learning Evidence 2.0.

V3.35 convirtió el ledger `learning_evidence` en una historia longitudinal, pero
cada evento solo sabía QUÉ se recuperó y CUÁNDO. Faltaba el CÓMO: con cuánto
apoyo, con qué dificultad de ítem, en qué contexto/actividad, con qué latencia y
—si falló— con qué TIPO de fallo.

Aquí se cubren las cinco capas:

- la MIGRACIÓN aditiva de las columnas nuevas en `learning_evidence`;
- la capa PURA (`EVIDENCE_SUPPORT_LEVELS`, `classify_recall_error` y los nuevos
  agregados de `summarize_evidence`);
- la PERSISTENCIA (`record_evidence` / `record_evidence_bulk`) y la paridad del
  contrato con `summarize_by_target`;
- la CAPTURA end-to-end (recall, producción por canal y latencia);
- la exposición en el léxico.

Principio rector (decisión de alcance): `error_type` es OBSERVACIONAL. Clasifica
el intento para el tutor (distinguir "no lo sabe" de "lo sabe y lo escribió mal")
sin tocar scoring, evidencia ni FSRS: una errata sigue siendo `correct=false`.
"""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from domain import vocabulary as domain_vocabulary
from main import app
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from services import academy as academy_svc
from services import evidence as evidence_svc
from services import lexicon


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _columns() -> set[str]:
    return {
        row[1]
        for row in db._conn().execute("PRAGMA table_info(learning_evidence)")
    }


# --- Capa pura: apoyo y taxonomía de error ----------------------------------


def test_support_levels_match_the_academy_axis():
    """La capa pura no puede inventar un segundo eje de apoyo (V3.36).

    Si `services.academy` gana o renombra un nivel, este test lo detecta antes
    de que el ledger léxico y `academy_evidence` empiecen a hablar dialectos
    distintos."""
    assert evidence_svc.EVIDENCE_SUPPORT_LEVELS == academy_svc.SUPPORT_LEVELS
    assert evidence_svc.INDEPENDENT_SUPPORT_LEVELS == {"independent", "spontaneous"}
    assert set(evidence_svc.INDEPENDENT_SUPPORT_LEVELS) <= set(
        evidence_svc.EVIDENCE_SUPPORT_LEVELS
    )


def test_classify_recall_error_taxonomy():
    assert evidence_svc.classify_recall_error("beautiful", "beautiful") == "correct"
    assert evidence_svc.classify_recall_error("beautiful", "  Beautiful ") == "correct"
    assert evidence_svc.classify_recall_error("beautiful", "") == "empty"
    assert evidence_svc.classify_recall_error("beautiful", "   ") == "empty"
    # Errata: misma inicial, longitud suficiente, 1-2 caracteres de diferencia.
    assert (
        evidence_svc.classify_recall_error("beautiful", "beautifull")
        == "orthographic_error"
    )
    assert (
        evidence_svc.classify_recall_error("receive", "recieve")
        == "orthographic_error"
    )
    # Recuperación parcial: prefijo de la palabra esperada.
    assert evidence_svc.classify_recall_error("beautiful", "beauti") == "partial"
    # Otra palabra: no se excusa como errata.
    assert evidence_svc.classify_recall_error("beautiful", "wonderful") == "wrong_word"
    assert evidence_svc.classify_recall_error("quokka", "quilt") == "wrong_word"


def test_classify_recall_error_is_conservative_on_short_words():
    """Con palabras cortas una diferencia de un carácter suele ser OTRA palabra
    (cat/cut, sun/son): no se excusa como errata, porque excusar de más
    reenseñaría menos de lo que el alumno necesita."""
    assert evidence_svc.classify_recall_error("cat", "cut") == "wrong_word"
    assert evidence_svc.classify_recall_error("sun", "son") == "wrong_word"
    # En cambio, si la diana está ENTERA dentro de la respuesta el alumno sí la
    # sabe: la errata no bloquea el reencuentro con el ítem.
    assert evidence_svc.classify_recall_error("cat", "cats") == "orthographic_error"
    assert evidence_svc.classify_recall_error("cat", "ca") == "partial"


def test_classify_recall_error_multiple_word_units():
    assert (
        evidence_svc.classify_recall_error("living room", "living room") == "correct"
    )
    # Recuperó el PRINCIPIO de la unidad: parcial, no fallo de unidad.
    assert evidence_svc.classify_recall_error("living room", "living") == "partial"
    # Se quedó a medias en el último token: parcial, no errata.
    assert evidence_svc.classify_recall_error("living room", "living roo") == "partial"
    # Recuperó un componente exacto de la unidad.
    assert evidence_svc.classify_recall_error("living room", "room") == "partial"
    # Errata sobre la unidad completa: comparte tokens, pero es una errata.
    assert (
        evidence_svc.classify_recall_error("living room", "livin room")
        == "orthographic_error"
    )
    # Otra unidad multi-palabra: no comparte tokens.
    assert (
        evidence_svc.classify_recall_error("living room", "dining table")
        == "multiple_word_error"
    )


def test_classify_recall_error_covers_the_declared_taxonomy():
    """Toda salida del clasificador pertenece a `RECALL_ERROR_TYPES`."""
    samples = [
        ("beautiful", "beautiful"),
        ("beautiful", ""),
        ("beautiful", "beautifull"),
        ("beautiful", "beauti"),
        ("beautiful", "wonderful"),
        ("living room", "dining table"),
    ]
    for expected, given in samples:
        assert (
            evidence_svc.classify_recall_error(expected, given)
            in evidence_svc.RECALL_ERROR_TYPES
        )


def test_cefr_difficulty_uses_the_shared_1_6_scale():
    assert lexicon.cefr_difficulty({"cefr": "A1"}) == 1.0
    assert lexicon.cefr_difficulty({"cefr": "b2"}) == 4.0
    assert lexicon.cefr_difficulty({"cefr": "C2"}) == 6.0
    # No declarada: 0.0, no se inventa una dificultad.
    assert lexicon.cefr_difficulty({}) == 0.0
    assert lexicon.cefr_difficulty({"cefr": "Z9"}) == 0.0


def test_duration_ms_converts_seconds_and_never_invents_latency():
    assert domain_vocabulary._duration_ms(2.5) == 2500
    assert domain_vocabulary._duration_ms(0) == 0
    assert domain_vocabulary._duration_ms(None) is None
    assert domain_vocabulary._duration_ms("basura") is None


# --- Migración ---------------------------------------------------------------


def test_migration_adds_evidence_dimension_columns(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    columns = _columns()
    assert {
        "activity_id",
        "context_id",
        "support_level",
        "difficulty",
        "response_time_ms",
        "error_type",
    } <= columns
    # Idempotente: volver a inicializar no rompe ni duplica migración.
    db.init_db()
    assert _columns() == columns


# --- Persistencia ------------------------------------------------------------


def test_record_evidence_persists_and_returns_the_new_dimensions(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    row = evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        activity="drill",
        activity_id="drill:recall",
        context_id="lexicon:drill",
        success=True,
        support_level="cued",
        difficulty=3.0,
        response_time_ms=4100,
        error_type="correct",
    )
    assert row is not None
    assert row["support_level"] == "cued"
    assert row["difficulty"] == 3.0
    assert row["response_time_ms"] == 4100
    assert row["error_type"] == "correct"
    assert row["context_id"] == "lexicon:drill"
    assert row["activity_id"] == "drill:recall"

    stored = evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    assert len(stored) == 1
    assert stored[0]["support_level"] == "cued"
    assert stored[0]["difficulty"] == 3.0
    assert stored[0]["response_time_ms"] == 4100
    assert stored[0]["error_type"] == "correct"


def test_record_evidence_defaults_are_undeclared_not_invented(monkeypatch, tmp_path):
    """Sin dimensiones el evento queda con apoyo/contexto '' y dificultad 0:
    'no declarado' no es lo mismo que un valor por defecto con significado."""
    uid = _setup(monkeypatch, tmp_path)
    row = evidence_repo.record_evidence(
        uid, target_type="lexicon", target_id="plain", task="production"
    )
    assert row["support_level"] == ""
    assert row["context_id"] == ""
    assert row["activity_id"] == ""
    assert row["difficulty"] == 0.0
    assert row["response_time_ms"] is None
    assert row["error_type"] == ""


def test_record_evidence_bulk_persists_per_entry_dimensions(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    inserted = evidence_repo.record_evidence_bulk(
        uid,
        [
            {
                "target_type": "lexicon",
                "target_id": "travel",
                "skill": "chat",
                "task": "production",
                "activity": "free_chat",
                "activity_id": "free_chat",
                "context_id": "lexicon:chat",
                "support_level": "spontaneous",
                "success": True,
            },
            {
                "target_type": "lexicon",
                "target_id": "travel",
                "skill": "writing",
                "task": "production",
                "activity": "writing_task",
                "activity_id": "writing_task",
                "context_id": "lexicon:writing",
                "support_level": "independent",
                "difficulty": 2.0,
                "response_time_ms": 900,
                "success": True,
            },
        ],
    )
    assert inserted == 2
    stored = evidence_repo.list_evidence(uid, "travel", target_type="lexicon")
    by_skill = {row["skill"]: row for row in stored}
    assert by_skill["chat"]["support_level"] == "spontaneous"
    assert by_skill["chat"]["context_id"] == "lexicon:chat"
    assert by_skill["writing"]["support_level"] == "independent"
    assert by_skill["writing"]["difficulty"] == 2.0
    assert by_skill["writing"]["response_time_ms"] == 900


def test_record_evidence_bulk_dedupe_still_ignores_dimensions(monkeypatch, tmp_path):
    """El dedupe de V3.35.1 sigue midiéndose por el EVENTO (target + tarea +
    actividad + instante): repetir la misma entrada no duplica el ledger aunque
    las dimensiones vengan rellenas."""
    uid = _setup(monkeypatch, tmp_path)
    entry = {
        "target_type": "lexicon",
        "target_id": "travel",
        "task": "production",
        "activity": "free_chat",
        "context_id": "lexicon:chat",
        "support_level": "spontaneous",
        "success": True,
        "occurred_at": "2026-09-01T10:00:00+00:00",
    }
    assert evidence_repo.record_evidence_bulk(uid, [entry, dict(entry)]) == 1


# --- Agregados y paridad de contrato ----------------------------------------


def test_summarize_evidence_aggregates_the_new_dimensions():
    rows = [
        {
            "occurred_at": "2026-09-01T10:00:00+00:00",
            "success": 1,
            "interval_since_last_evidence": None,
            "support_level": "cued",
            "error_type": "correct",
            "response_time_ms": 2000,
        },
        {
            "occurred_at": "2026-09-02T10:00:00+00:00",
            "success": 0,
            "interval_since_last_evidence": None,
            "support_level": "cued",
            "error_type": "orthographic_error",
            "response_time_ms": 4000,
        },
        {
            "occurred_at": "2026-09-03T10:00:00+00:00",
            "success": 1,
            "interval_since_last_evidence": 1.0,
            "support_level": "independent",
            "error_type": "correct",
        },
    ]
    out = evidence_svc.summarize_evidence(rows)
    assert out["attempts"] == 3
    assert out["successes"] == 2
    assert out["success_rate"] == 0.6667
    assert out["independent_successes"] == 1
    assert out["support_levels"] == {"cued": 2, "independent": 1}
    assert out["error_types"] == {
        "correct": 2,
        "orthographic_error": 1,
    }
    # La latencia media ignora los eventos sin medida (3º) y las no válidas.
    assert out["mean_response_time_ms"] == 3000.0


def test_summarize_evidence_never_invents_latency_or_flags():
    out = evidence_svc.summarize_evidence(
        [
            {
                "occurred_at": "2026-09-01T10:00:00+00:00",
                "success": 0,
                "support_level": "",
                "error_type": "",
                "response_time_ms": None,
            }
        ]
    )
    assert out["mean_response_time_ms"] is None
    assert out["success_rate"] == 0.0
    assert out["support_levels"] == {}
    assert out["error_types"] == {}
    assert out["independent_successes"] == 0
    # Un apoyo no canónico no entra en el histograma.
    non_canonical = evidence_svc.summarize_evidence(
        [{"occurred_at": "", "success": 1, "support_level": "telepatía"}]
    )
    assert non_canonical["support_levels"] == {}


def test_empty_summary_matches_the_extended_contract():
    assert evidence_svc.empty_summary() == {
        "attempts": 0,
        "successes": 0,
        "success_rate": 0.0,
        "distinct_success_days": 0,
        "intervals": [],
        "independent_successes": 0,
        "independent_success_days": 0,
        "support_levels": {},
        "error_types": {},
        "recall_rungs": {},
        # V3.37.1 (consolidación y regresión): histogramas de días con éxito y
        # fallos por peldaño, aditivos al contrato del resumen.
        "recall_rung_days": {},
        "recall_rung_failures": {},
        # V3.38 (P1-03): histogramas por modalidad (aditivos).
        "skill_successes": {},
        "skill_success_days": {},
        "skill_independent_successes": {},
        "skill_independent_days": {},
        # V3.38.1 (P1-02): intentos y latencia media por modalidad (aditivos).
        "skill_attempts": {},
        "skill_mean_response_time_ms": {},
        "mean_response_time_ms": None,
        # V3.39 (Fase 3C): recencia y distribución de latencia (aditivos).
        "recent_attempts": 0,
        "recent_error_rate": 0.0,
        "recent_wrong_word": 0,
        "median_response_time_ms": None,
        "p75_response_time_ms": None,
        "p90_response_time_ms": None,
        "recent_response_time_ms": None,
        "latency_trend": None,
        # V3.40 (Fase 4): contextos de transferencia contextual (aditivos).
        "contexts": {},
        "context_attempts": 0,
        "success_contexts": [],
        "home_context": "",
        # V3.43 (P1-03/P1-04): éxito limpio, diversidad contextual real y estado
        # de transferencia (aditivos).
        "clean_contexts": {},
        "clean_successes": 0,
        "clean_success_contexts": [],
        "clean_success_days": 0,
        "context_diversity": {
            "distinct_contexts": 0,
            "dimensions": {},
            "diverse_dimensions": 0,
            "score": 0.0,
            # V3.48: variedad informativa (no entra en el gate de evidencia).
            "variety": {"dimensions": {}, "varied_dimensions": 0, "score": 0.0},
        },
        "transfer": False,
        # V3.46 (P1-03): condición de recuperación (aditivos).
        "transfer_conditions": {},
        "success_conditions": [],
        "unscaffolded_clean_successes": 0,
        # V3.47 (P1-02): evidencia fina de la escalera endurecida (aditivos).
        "unscaffolded_clean_success_contexts": [],
        "unscaffolded_clean_success_days": 0,
        "clean_success_goals": [],
        "last_clean_success_at": "",
        "last_unscaffolded_clean_success_at": "",
        "transfer_state": "not_ready",
        # V3.49 (Transfer Evidence 3.0): confianza explicable del eje (aditiva).
        "transfer_confidence": {
            "score": 0.0,
            "level": "none",
            "sample": 0,
            "drivers": {
                "contexts": 0.0,
                "successes": 0.0,
                "diversity": 0.0,
                "independence": 0.0,
                "variety": 0.0,
                "spacing": 0.0,
            },
            "recency_days": None,
        },
    }


def test_summarize_by_target_matches_the_pure_contract(monkeypatch, tmp_path):
    """El agregado SQL no puede introducir un segundo dialecto del resumen."""
    uid = _setup(monkeypatch, tmp_path)
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        success=True,
        support_level="cued",
        difficulty=3.0,
        response_time_ms=2000,
        error_type="correct",
        occurred_at="2026-09-01T10:00:00+00:00",
    )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        success=False,
        support_level="cued",
        difficulty=3.0,
        response_time_ms=6000,
        error_type="wrong_word",
        occurred_at="2026-09-02T10:00:00+00:00",
    )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        task="recall",
        success=True,
        support_level="independent",
        difficulty=3.0,
        response_time_ms=3000,
        error_type="correct",
        occurred_at="2026-09-04T10:00:00+00:00",
    )
    aggregated = evidence_repo.summarize_by_target(uid, target_type="lexicon")
    rows = evidence_repo.list_evidence(uid, "river", target_type="lexicon")
    pure = evidence_svc.summarize_evidence(rows)
    assert aggregated["river"] == pure
    assert aggregated["river"]["independent_successes"] == 1
    assert aggregated["river"]["support_levels"] == {
        "cued": 2,
        "independent": 1,
    }
    assert aggregated["river"]["error_types"] == {"correct": 2, "wrong_word": 1}
    assert aggregated["river"]["mean_response_time_ms"] == 3666.7


# --- Captura end-to-end ------------------------------------------------------


def _dictionary_word(word: str, translation: str) -> None:
    dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=f"definition of {word}",
        translation=translation,
        generator_version="test",
    )


def test_recall_attempt_records_observational_dimensions(monkeypatch, tmp_path):
    """El intento de Recall declara apoyo (cue), contexto, actividad, latencia y
    clasificación; ninguna de esas dimensiones cambia la puntuación."""
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={
                "word": "quokka",
                "answer": "quokka",
                "response_time_ms": 2500,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
    assert body["correct"] is True
    assert body["error_type"] == "correct"

    row = evidence_repo.list_evidence(uid, "quokka", target_type="lexicon")[0]
    assert row["support_level"] == "cued"
    # V3.37: el ledger declara el PELDAÑO servido en el activity_id.
    assert row["activity_id"] == "drill:recall:translation"
    assert row["context_id"] == "lexicon:drill"
    assert row["response_time_ms"] == 2500
    assert row["error_type"] == "correct"
    # La palabra no declara CEFR en el léxico: dificultad "no declarada" (0.0),
    # no un valor inventado.
    assert row["difficulty"] == 0.0


def test_recall_orthographic_error_is_observational_and_does_not_credit(
    monkeypatch, tmp_path
):
    """Una errata se CLASIFICA, no se perdona: `correct=false`, sin recuperación
    demorada y sin acierto de recall. Es la garantía de que V3.36 añade
    información sin tocar el scoring (decisión de alcance)."""
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "quokka", "answer": "quoka", "response_time_ms": 3000},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        lexicon_res = client.get(
            "/api/vocabulary/lexicon", params={"user_id": uid}
        )
    assert body["correct"] is False
    assert body["delayed"] is False
    assert body["error_type"] == "orthographic_error"

    row = evidence_repo.list_evidence(uid, "quokka", target_type="lexicon")[0]
    assert row["success"] == 0
    assert row["error_type"] == "orthographic_error"

    item = next(
        i for i in lexicon_res.json()["items"] if i["word"] == "quokka"
    )
    assert item["competence"]["recall_successes"] == 0
    assert item["competence"]["recall_attempts"] == 1


def test_recall_attempt_latency_is_optional(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "quokka", "answer": "quokka"},
        )
        assert res.status_code == 200, res.text
    row = evidence_repo.list_evidence(uid, "quokka", target_type="lexicon")[0]
    assert row["response_time_ms"] is None
    assert (
        evidence_repo.summarize_by_target(uid, target_type="lexicon")["quokka"][
            "mean_response_time_ms"
        ]
        is None
    )


def test_recall_attempt_rejects_a_negative_latency(monkeypatch, tmp_path):
    """La latencia es una medida: un valor imposible se rechaza en el contrato
    (422) en vez de envenenar las medias agregadas."""
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "quokka", "answer": "quokka", "response_time_ms": -1},
        )
    assert res.status_code == 422


def test_production_evidence_declares_channel_context_and_support(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    asyncio.run(
        domain_vocabulary.record_production_text(
            uid, "I love travel", "chat", activity="free_chat"
        )
    )
    rows = evidence_repo.list_evidence(uid, target_type="lexicon")
    produced = [row for row in rows if row["task"] == "production"]
    assert produced, "la producción debe dejar evidencia en el ledger"
    for row in produced:
        assert row["support_level"] == "spontaneous"
        assert row["context_id"] == "lexicon:chat"
        assert row["activity_id"] == "free_chat"


def test_lexicon_exposes_the_extended_evidence(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _dictionary_word("quokka", "marsupial australiano")
    with TestClient(app) as client:
        client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={
                "word": "quokka",
                "answer": "quokka",
                "response_time_ms": 1800,
            },
        )
        res = client.get("/api/vocabulary/lexicon", params={"user_id": uid})
        assert res.status_code == 200, res.text
        body = res.json()

    item = next(i for i in body["items"] if i["word"] == "quokka")
    evidence = item["evidence"]
    assert evidence["attempts"] == 1
    assert evidence["success_rate"] == 1.0
    assert evidence["independent_successes"] == 0
    assert evidence["support_levels"] == {"cued": 1}
    assert evidence["error_types"] == {"correct": 1}
    assert evidence["mean_response_time_ms"] == 1800.0
