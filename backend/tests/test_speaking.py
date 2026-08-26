"""Tests del scorer determinista de speaking (rubric CEFR de 7 dimensiones)."""

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo
from routers import academy as academy_router
from services import llm
from services import speaking as speaking_svc
from services.curriculum import load_level
from services.speaking import (
    CRITERION_WEIGHTS,
    SPEAKING_CRITERIA,
    SpeakingTaskProfile,
    difficulty_from_vector,
    realization_gap_factors,
    realized_vector,
    weights_for_task_type,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _first_speaking_objective():
    objs = load_level("a1").objectives()
    for o in objs:
        if "speaking" in o.skills:
            return o
    return objs[0]


class FakeOllamaClient:
    def __init__(self, content="Hi!"):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        return {"message": {"content": self.content}}

    async def list(self):
        return {"models": [{"model": "qwen3.5:9b"}]}


def test_score_speaking_keys_and_range():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert set(result.keys()) == {
        "heard",
        "expected",
        "criteria",
        "observed",
        "overall",
    }
    assert set(result["criteria"].keys()) == set(SPEAKING_CRITERIA)
    assert set(result["observed"].keys()) == set(SPEAKING_CRITERIA)
    for criterion in SPEAKING_CRITERIA:
        score = result["criteria"][criterion]
        if score is not None:
            assert 0.0 <= score <= 1.0
    assert 0.0 <= result["overall"] <= 1.0


def test_score_speaking_perfect_high():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert result["overall"] >= 0.7
    assert result["criteria"]["pronunciation"] >= 0.9


def test_score_speaking_mismatch_low():
    result = speaking_svc.score_speaking("banana banana banana", "I am a student")
    assert result["overall"] < 0.5
    assert result["criteria"]["task_achievement"] < 0.5
    assert result["criteria"]["lexical_resource"] < 0.5


def test_score_speaking_fluency_unknown_is_unobserved():
    result = speaking_svc.score_speaking("I am a student", "I am a student", None)
    assert result["criteria"]["fluency"] is None
    assert result["observed"]["fluency"] is False


def test_score_speaking_empty_expected():
    result = speaking_svc.score_speaking("anything", "")
    assert result["criteria"]["lexical_resource"] == 1.0
    assert result["criteria"]["task_achievement"] == 1.0


def test_rubric_weights_sum_to_one():
    assert sum(CRITERION_WEIGHTS.values()) == pytest.approx(1.0)


# --- Criterios no observados + diversidad léxica (P0 Speaking scoring) -------


def test_scores_from_evidence_pronunciation_unobserved():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 1,
        "lexical_tokens": ["student", "live", "city"],
        "coherence": 0.8,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 3.0)
    assert result["criteria"]["pronunciation"] is None
    assert result["observed"]["pronunciation"] is False
    # El overall se recalcula solo sobre criterios observados (pronunciación fuera).
    assert result["overall"] > 0.0


def test_scores_from_evidence_no_audio_pronunciation_never_half():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student")
    assert result["criteria"]["pronunciation"] is None
    assert result["criteria"]["fluency"] is None
    assert result["observed"]["fluency"] is False
    # Ningún criterio no observado entra en el overall.
    assert 0.0 <= result["overall"] <= 1.0


def test_lexical_diversity_measures_repetition():
    assert speaking_svc.lexical_diversity([]) == 0.0
    # Sin repetición → TTR = 1.0.
    assert speaking_svc.lexical_diversity(["i", "am", "a", "student"]) == 1.0
    # Repetición baja la diversidad.
    assert speaking_svc.lexical_diversity(["banana", "banana", "banana"]) < 0.5


def test_scores_from_evidence_lexical_resource_is_diversity_not_overlap():
    # Una respuesta rica en variedad (aunque no comparta tokens con un "expected"
    # inexistente aquí) debe puntuar alta en lexical_resource.
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
    }
    rich = "I travelled to Italy with my wife and we visited Rome for five days"
    result = speaking_svc.scores_from_evidence(evidence, rich, 60.0)
    assert result["criteria"]["lexical_resource"] >= 0.8


def test_sequence_coherence_preserves_order():
    # Orden exacto → coherencia total.
    assert speaking_svc._sequence_coherence(
        ["i", "am", "a", "student"], ["i", "am", "a", "student"]
    ) == 1.0
    # Palabras desordenadas → coherencia parcial (no total).
    scrambled = speaking_svc._sequence_coherence(
        ["student", "a", "am", "i"], ["i", "am", "a", "student"]
    )
    assert 0.0 < scrambled < 1.0
    # Repetir la frase entera no infla la coherencia (no mide longitud).
    repeated = speaking_svc._sequence_coherence(
        ["i", "am", "a", "student", "i", "am", "a", "student"],
        ["i", "am", "a", "student"],
    )
    assert repeated == 1.0
    # Sin solapamiento → coherencia cero.
    assert (
        speaking_svc._sequence_coherence(
            ["banana", "banana", "banana"], ["i", "am", "a", "student"]
        )
        == 0.0
    )


def test_score_speaking_interaction_unobserved_read_aloud():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    assert result["criteria"]["interaction"] is None
    assert result["observed"]["interaction"] is False


def test_scores_from_evidence_interaction_observed():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
        "interaction": 0.8,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 120.0)
    assert result["criteria"]["interaction"] == 0.8
    assert result["observed"]["interaction"] is True


def test_scores_from_evidence_interaction_absent_unobserved():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 120.0)
    assert result["criteria"]["interaction"] is None
    assert result["observed"]["interaction"] is False


def test_scores_from_evidence_discourse_penalties_reduce_fluency():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
        "self_corrections": 3,
        "hesitations": 4,
        "repetitions": 2,
    }
    clean = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    heard = "I am a student and I live in a city near the coast with my family"
    dirty = speaking_svc.scores_from_evidence(evidence, heard, 120.0)
    base = speaking_svc.scores_from_evidence(clean, heard, 120.0)
    assert dirty["criteria"]["fluency"] < base["criteria"]["fluency"]


# --- V1.16 S3: LexicalEvidence 2.0 + FluencyEvidence 2.0 -------------------


def test_lexical_evidence_shape_and_range():
    le = speaking_svc.lexical_evidence(["i", "am", "a", "student"])
    assert set(le.keys()) == {
        "types",
        "tokens",
        "diversity",
        "diversity_normalized",
        "range",
    }
    assert le["types"] == 4
    assert le["tokens"] == 4
    assert le["diversity"] == 1.0
    # 4 tipos < mínimo de 20 → range < 1 (muestra corta no es "rica").
    assert le["range"] < 1.0


def test_msttr_normalizes_length():
    # Muestra corta (< segmento): MSTTR = TTR.
    assert speaking_svc._msttr(["a", "b", "c"]) == 1.0
    # Repetición de los mismos 10 tokens en dos segmentos: TTR global = 0.5 pero
    # cada segmento es diverso → MSTTR mayor (estable ante longitud).
    tokens = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"] * 2
    assert speaking_svc.lexical_diversity(tokens) == 0.5
    assert speaking_svc._msttr(tokens) == 1.0


def test_speech_rate_score_fluent_band():
    # Rango apropiado/fluido (90–140 wpm) puntúa 1.0.
    assert speaking_svc._speech_rate_score(90.0) == 1.0
    assert speaking_svc._speech_rate_score(120.0) == 1.0
    assert speaking_svc._speech_rate_score(140.0) == 1.0
    # Hablar demasiado rápido penaliza por inteligibilidad.
    assert speaking_svc._speech_rate_score(170.0) == 0.75
    assert speaking_svc._speech_rate_score(200.0) == 0.5
    # Lento rampa: 60 wpm → 0.6; muy lento → suelo 0.2.
    assert speaking_svc._speech_rate_score(60.0) == 0.6
    assert speaking_svc._speech_rate_score(20.0) == 0.2


def test_lexical_score_penalizes_short_sample():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
    }
    # 2 palabras, 2 tipos: TTR 1.0, pero range 2/20 → score < 1 (no "B2").
    result = speaking_svc.scores_from_evidence(evidence, "I am", 60.0)
    assert result["criteria"]["lexical_resource"] < 0.8


def test_lexical_score_combines_llm_fields():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "lexical_sophistication": 0.9,
        "lexical_precision": 0.8,
        "collocations": 0.7,
    }
    heard = "I travelled to Italy with my wife and we visited Rome"
    result = speaking_svc.scores_from_evidence(evidence, heard, 60.0)
    # 0.25·1 + 0.25·1 + 0.20·0.55 + 0.15·0.9 + 0.10·0.8 + 0.05·0.7 = 0.86.
    assert result["criteria"]["lexical_resource"] == pytest.approx(0.86)


def test_scores_from_evidence_fluency_separates_speed():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
    }
    heard = " ".join(f"w{i}" for i in range(20))  # 20 palabras
    # 90 wpm es apropiado para B1 → fluidez 1.0 (aunque no sea "rápido").
    appropriate = speaking_svc.scores_from_evidence(evidence, heard, 13.3333)
    assert appropriate["criteria"]["fluency"] == 1.0
    # 170 wpm es demasiado rápido → fluidez penalizada (inteligibilidad).
    too_fast = speaking_svc.scores_from_evidence(evidence, heard, 7.0588)
    assert too_fast["criteria"]["fluency"] == 0.75


def test_scores_from_evidence_fluency_blends_smoothness_rhythm():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "smoothness": 0.5,
        "rhythm": 0.5,
    }
    heard = " ".join(f"w{i}" for i in range(20))
    result = speaking_svc.scores_from_evidence(evidence, heard, 13.3333)
    # base 1.0 mezclada con smoothness/rhythm 0.5 (peso 0.15 cada uno).
    expected = (1.0 + 0.15 * 0.5 + 0.15 * 0.5) / 1.3
    assert result["criteria"]["fluency"] == pytest.approx(round(expected, 3))


# --- V1.16 S4: InteractionEvidence 2.0 + pronunciación en flujo libre --------


def test_interaction_score_combines_subdims():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "appropriate_responses": 0.9,
        "turn_completion": 0.8,
        "follow_up_questions": 0.7,
        "topic_maintenance": 0.8,
        "clarification_requests": 0.5,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 60.0)
    # (0.28·0.9 + 0.22·0.8 + 0.18·0.7 + 0.14·0.8 + 0.09·0.5) / 0.91 = 0.781.
    assert result["criteria"]["interaction"] == pytest.approx(0.781)
    assert result["observed"]["interaction"] is True


def test_interaction_score_falls_back_to_single():
    # Sin sub-dimensiones, se conserva el fallback `interaction` (backward-compat).
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
        "interaction": 0.65,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 60.0)
    assert result["criteria"]["interaction"] == 0.65


def test_interaction_score_includes_repair():
    # Con `repair` presente, entra en la combinación semántica con peso 0.09.
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "appropriate_responses": 0.9,
        "turn_completion": 0.8,
        "follow_up_questions": 0.7,
        "topic_maintenance": 0.8,
        "clarification_requests": 0.5,
        "repair": 0.6,
    }
    # 0.28·0.9 + 0.22·0.8 + 0.18·0.7 + 0.14·0.8 + 0.09·0.5 + 0.09·0.6 = 0.765.
    assert speaking_svc._interaction_score(evidence) == pytest.approx(0.765)


def test_scores_from_evidence_pronunciation_with_expected():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    result = speaking_svc.scores_from_evidence(
        evidence, "I am a student", 3.0, expected="I am a student"
    )
    assert result["criteria"]["pronunciation"] == 1.0
    assert result["observed"]["pronunciation"] is True


def test_scores_from_evidence_pronunciation_unobserved_without_expected():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 3.0)
    assert result["criteria"]["pronunciation"] is None
    assert result["observed"]["pronunciation"] is False


# --- P0-1: task_achievement continuo --------------------------------------


def test_scores_from_evidence_task_achievement_continuous():
    evidence = {
        "task_achieved": False,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
        "task_completion": 0.8,
        "task_relevance": 0.9,
        "task_coverage": 0.7,
        "task_appropriateness": 0.6,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 3.0)
    # 0.35·0.8 + 0.25·0.9 + 0.25·0.7 + 0.15·0.6 = 0.77 (graduado, no binario).
    assert result["criteria"]["task_achievement"] == pytest.approx(0.77)


def test_scores_from_evidence_task_achievement_binary_fallback():
    # Sin sub-dimensiones, se conserva el fallback binario `task_achieved`.
    true_evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
    }
    false_evidence = {
        "task_achieved": False,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
    }
    assert (
        speaking_svc.scores_from_evidence(true_evidence, "I am a student", 3.0)
        ["criteria"]["task_achievement"]
        == 1.0
    )
    assert (
        speaking_svc.scores_from_evidence(false_evidence, "I am a student", 3.0)
        ["criteria"]["task_achievement"]
        == 0.0
    )


# --- P0-2: GrammarEvidence 2.0 (severidad de errores) ---------------------


def test_scores_from_evidence_grammar_severity_penalizes_critical_more():
    # 10 errores leves no deben hundir el score; 2 críticos sí pesan más.
    many_minor = {
        "task_achieved": True,
        "grammar_errors": 10,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
        "grammar_error_details": [{"type": "article", "severity": "minor"}] * 10,
    }
    two_critical = {
        "task_achieved": True,
        "grammar_errors": 2,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
        "grammar_error_details": [
            {"type": "word_order", "severity": "critical"},
            {"type": "verb_tense", "severity": "critical"},
        ],
    }
    a = speaking_svc.scores_from_evidence(many_minor, "I am a student", 3.0)
    b = speaking_svc.scores_from_evidence(two_critical, "I am a student", 3.0)
    assert a["criteria"]["grammatical_control"] == pytest.approx(0.5)
    assert b["criteria"]["grammatical_control"] == pytest.approx(0.4)
    assert b["criteria"]["grammatical_control"] < a["criteria"]["grammatical_control"]


def test_scores_from_evidence_grammar_legacy_fallback():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 2,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
    }
    result = speaking_svc.scores_from_evidence(evidence, "I am a student", 3.0)
    # Fallback plano: 1 - 0.25·2 = 0.5.
    assert result["criteria"]["grammatical_control"] == pytest.approx(0.5)


# --- V1.16 S2: SpeakingTaskProfile, dificultad y pesos por task_type --------


def test_difficulty_from_vector_empty_is_minimum():
    assert difficulty_from_vector({}) == 1


def test_difficulty_from_vector_rounds_mean_and_clamps():
    # media 3.5 → round (al par) → 4.
    assert difficulty_from_vector({"lexical_demand": 3, "grammar_demand": 4}) == 4
    # Clamp a [1, 6].
    assert difficulty_from_vector({"lexical_demand": 6, "grammar_demand": 6}) == 6


def test_weights_for_task_type_monologue_has_no_interaction():
    mono = weights_for_task_type("monologue")
    assert mono["interaction"] == 0.0
    assert sum(mono.values()) == pytest.approx(1.0)


def test_weights_for_task_type_conversation_weights_interaction():
    conv = weights_for_task_type("conversation")
    assert conv["interaction"] == 0.20
    assert sum(conv.values()) == pytest.approx(1.0)
    # Tipos conversacionales sin perfil propio usan el perfil conversation.
    assert weights_for_task_type("role_play")["interaction"] == 0.20
    # Tipos desconocidos caen al perfil por defecto (backward-compat).
    assert weights_for_task_type("nonsense") is CRITERION_WEIGHTS


def test_scores_from_evidence_task_type_changes_overall_when_interaction():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["w0"],
        "coherence": 0.9,
        "interaction": 0.0,
    }
    # 20 palabras en 10 s → WPM 120 → fluency 1.0; resto de criterios 1.0.
    heard = " ".join(f"w{i}" for i in range(20))
    default = speaking_svc.scores_from_evidence(evidence, heard, 10.0)
    conv = speaking_svc.scores_from_evidence(
        evidence, heard, 10.0, task_type="conversation"
    )
    # interaction baja pesa más en conversation → overall más bajo.
    assert conv["overall"] < default["overall"]


def test_evidence_from_speaking_records_difficulty():
    result = speaking_svc.score_speaking("I am a student", "I am a student", 3.0)
    rows = speaking_svc.evidence_from_speaking(
        result,
        level_id="a1",
        objective_id="o1",
        curriculum_version="1.2.5",
        difficulty=3,
    )
    assert rows, "no se generó evidencia"
    assert all(r["difficulty"] == 3 for r in rows)


def test_realized_vector_interaction_only_in_conversation():
    mono = SpeakingTaskProfile(
        task_type="monologue",
        difficulty_vector={"lexical_demand": 4, "interaction_demand": 5},
    )
    conv = SpeakingTaskProfile(
        task_type="conversation",
        difficulty_vector={"lexical_demand": 4, "interaction_demand": 5},
    )
    assert realized_vector(mono)["interaction_demand"] == 1
    assert realized_vector(conv)["interaction_demand"] == 5
    assert realization_gap_factors(mono) == ["interaction_demand"]
    assert realization_gap_factors(conv) == []


# --- Endpoint / integración (puente speaking → mastery) --------------------


def test_speaking_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    assert "speaking" in obj.skills, "ningún objetivo A1 declara 'speaking'"
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 7
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in speaking_rows)
    # 6 criterios observados + 1 overall (interaction no observada en read-aloud).
    assert len(speaking_rows) >= 7
    assert academy_repo.get_objective_row(a, "a1", obj.id, "speaking") is not None


def test_speaking_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404  # A2 bloqueado hasta completar A1


def test_speaking_evidence_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
            },
        )
    assert academy_repo.list_evidence(b) == []


# --- Endpoint / integración (tarea abierta: LLM extrae, scorer puntúa) -------


def test_speaking_task_records_evidence_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    assert "speaking" in obj.skills, "ningún objetivo A1 declara 'speaking'"
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 1, '
        '"lexical_tokens": ["student", "live", "city"], "coherence": 0.8}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 7
    assert body["speaking_mastery"] > 0
    assert body["evidence"]["task_achieved"] is True

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["skill"] == "speaking" for row in speaking_rows)


def test_speaking_task_records_task_difficulty(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student", "live", "city"], "coherence": 0.8}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
                "duration_seconds": 3.0,
                "task_type": "conversation",
                "difficulty": 4,
            },
        )
    assert r.status_code == 200
    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"
    assert all(row["difficulty"] == 4 for row in speaking_rows)


def test_speaking_task_llm_invalid_returns_404(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    fake = FakeOllamaClient(content="not json")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404


def test_speaking_task_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 1.0}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a2",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
            },
        )
    assert r.status_code == 404


# --- Endpoint / integración (audio → Whisper → scorer) ----------------------


def test_speaking_audio_read_aloud_records_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    monkeypatch.setattr(
        academy_router,
        "transcribe_with_timing",
        lambda audio, language="en": {"text": "I am a student", "duration": 3.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/audio",
            params={"user_id": a},
            data={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
            },
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["overall"] <= 1.0
    assert len(body["criteria"]) == 7
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"


def test_speaking_task_audio_records_evidence(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student", "live", "city", "name", "job"], '
        '"coherence": 0.9}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    monkeypatch.setattr(
        academy_router,
        "transcribe_with_timing",
        lambda audio, language="en": {"text": "I am a student", "duration": 3.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task/audio",
            params={"user_id": a},
            data={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
            },
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["evidence"]["task_achieved"] is True
    assert body["speaking_mastery"] > 0

    speaking_rows = [
        row for row in academy_repo.list_evidence(a) if row["source"] == "speaking"
    ]
    assert speaking_rows, "no se registró evidencia de speaking"


def test_speaking_audio_transcribe_error_500(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()

    def boom(audio, language="en"):
        raise Exception("boom")

    monkeypatch.setattr(academy_router, "transcribe_with_timing", boom)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/audio",
            params={"user_id": a},
            data={"level_id": "a1", "objective_id": obj.id, "expected": "hi"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 500


def test_speaking_audio_rejects_blocked_level(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = load_level("a2").objectives()[0]
    monkeypatch.setattr(
        academy_router,
        "transcribe_with_timing",
        lambda audio, language="en": {"text": "hi", "duration": 1.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/audio",
            params={"user_id": a},
            data={"level_id": "a2", "objective_id": obj.id, "expected": "hi"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
    assert r.status_code == 404


# --- Diagnóstico longitudinal de speaking (V1.15) -------------------------


def _evidence_row(item_id, result, created_at="2026-08-01T00:00:00"):
    return {
        "skill": "speaking",
        "item_id": item_id,
        "result": result,
        "created_at": created_at,
    }


def test_speaking_diagnostic_empty():
    diag = speaking_svc.speaking_diagnostic([])
    assert diag["attempts"] == 0
    assert diag["overall_mean"] is None
    assert diag["trend"]["direction"] == "n/a"
    assert len(diag["criteria"]) == len(SPEAKING_CRITERIA)
    assert all(c["attempts"] == 0 and c["mean"] is None for c in diag["criteria"])
    assert set(diag["weak"]) == set(SPEAKING_CRITERIA)
    assert diag["recommendation"].startswith("Focus on")


def test_speaking_diagnostic_strong():
    rows = []
    for criterion in SPEAKING_CRITERIA:
        rows.append(_evidence_row(criterion, 0.9))
        rows.append(_evidence_row(criterion, 0.95))
    rows.append(_evidence_row("overall", 0.9))
    rows.append(_evidence_row("overall", 0.95))
    diag = speaking_svc.speaking_diagnostic(rows)
    assert diag["attempts"] == 2
    assert diag["overall_mean"] == 0.925
    assert diag["weak"] == []
    assert diag["recommendation"] == "All speaking criteria look strong."


def test_speaking_diagnostic_weak_criterion():
    rows = []
    for _ in range(3):
        rows.append(_evidence_row("pronunciation", 0.4))
        rows.append(_evidence_row("fluency", 0.9))
    for _ in range(3):
        rows.append(_evidence_row("overall", 0.5))
    diag = speaking_svc.speaking_diagnostic(rows)
    assert "pronunciation" in diag["weak"]
    assert "fluency" not in diag["weak"]


def test_speaking_diagnostic_trend_up():
    rows = []
    for i, value in enumerate([0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]):
        rows.append(_evidence_row("overall", value, created_at=f"2026-08-{i + 1:02d}"))
    diag = speaking_svc.speaking_diagnostic(rows)
    assert diag["trend"]["direction"] == "up"
    assert diag["trend"]["delta"] > 0


def test_speaking_diagnostic_endpoint(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
        r = client.get("/api/academy/speaking/diagnostic", params={"user_id": a})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 1
    assert body["overall_mean"] is not None
    assert len(body["criteria"]) == len(SPEAKING_CRITERIA)
    assert "overall" not in [c["criterion"] for c in body["criteria"]]
    for criterion in body["criteria"]:
        assert set(criterion.keys()) >= {
            "criterion",
            "attempts",
            "mean",
            "min",
            "max",
            "review_due",
        }


# --- V1.16 S5: Student Model ownership (EMA + olvido + stability) -----------


def test_speaking_diagnostic_recent_score_is_ema_not_mean():
    rows = [
        _evidence_row("fluency", 0.5, "2026-08-01T00:00:00"),
        _evidence_row("fluency", 0.5, "2026-08-02T00:00:00"),
        _evidence_row("fluency", 0.9, "2026-08-03T00:00:00"),
    ]
    diag = speaking_svc.speaking_diagnostic(rows)
    fluency = next(c for c in diag["criteria"] if c["criterion"] == "fluency")
    assert fluency["mean"] == pytest.approx(0.633)
    # EMA da más peso a lo reciente: 0.7 > media 0.633.
    assert fluency["recent_score"] == pytest.approx(0.7)
    assert fluency["recent_score"] > fluency["mean"]
    assert fluency["lifetime_score"] == fluency["mean"]


def test_speaking_diagnostic_review_due_forgetting():
    rows = [_evidence_row("grammar", 0.9, "2026-08-01T00:00:00")]
    # 31 días después, la recuperación de un 0.9 ha caído bajo el umbral → due.
    diag = speaking_svc.speaking_diagnostic(rows, now="2026-09-01T00:00:00")
    grammar = next(c for c in diag["criteria"] if c["criterion"] == "grammar")
    assert grammar["review_due"] is True
    # Sin decaimiento (now vacío), un 0.9 reciente no está para repasar.
    fresh = speaking_svc.speaking_diagnostic(rows)
    fresh_grammar = next(c for c in fresh["criteria"] if c["criterion"] == "grammar")
    assert fresh_grammar["review_due"] is False


def test_speaking_diagnostic_recent_failure_triggers_review():
    rows = [
        _evidence_row("grammar", 0.9, "2026-08-01T00:00:00"),
        _evidence_row("grammar", 0.9, "2026-08-02T00:00:00"),
        _evidence_row("grammar", 0.4, "2026-08-03T00:00:00"),
    ]
    diag = speaking_svc.speaking_diagnostic(rows)
    grammar = next(c for c in diag["criteria"] if c["criterion"] == "grammar")
    # media > 0.6, pero el fallo reciente dispara review (recent_failure).
    assert grammar["mean"] > 0.6
    assert grammar["review_due"] is True


def test_speaking_diagnostic_exposes_model_signals():
    rows = [
        _evidence_row("coherence", 0.8, "2026-08-01T00:00:00"),
        _evidence_row("coherence", 0.9, "2026-08-02T00:00:00"),
    ]
    diag = speaking_svc.speaking_diagnostic(rows)
    coherence = next(c for c in diag["criteria"] if c["criterion"] == "coherence")
    assert coherence["confidence"] == 1.0
    assert coherence["stability"] is not None
    assert coherence["lifetime_score"] == coherence["mean"]


def test_speaking_diagnostic_overall_recent():
    rows = [
        _evidence_row("overall", 0.5, "2026-08-01T00:00:00"),
        _evidence_row("overall", 0.5, "2026-08-02T00:00:00"),
        _evidence_row("overall", 0.9, "2026-08-03T00:00:00"),
    ]
    diag = speaking_svc.speaking_diagnostic(rows)
    assert diag["overall_mean"] == pytest.approx(0.633)
    assert diag["overall_recent"] == pytest.approx(0.7)


# --- V1.16 S6: Speaking Assessment 1.0 + Speaking Journey ------------------


def test_speaking_level_empty():
    level = speaking_svc.speaking_level([])
    assert level["level"] is None
    assert level["numeric"] is None
    assert level["score"] is None
    assert level["confidence"] == 0.0
    assert level["attempts"] == 0


def test_speaking_level_computes_cefr():
    rows = [
        _evidence_row("overall", 0.8, "2026-08-01T00:00:00"),
        _evidence_row("overall", 0.9, "2026-08-02T00:00:00"),
    ]
    level = speaking_svc.speaking_level(rows)
    assert level["score"] == pytest.approx(0.85)
    assert level["numeric"] == pytest.approx(5.25)
    assert level["level"] == "C1"
    assert level["confidence"] == 1.0
    assert level["attempts"] == 2


def test_speaking_journey_steps_chronological():
    rows = [
        _evidence_row("overall", 0.5, "2026-08-01T00:00:00"),
        _evidence_row("overall", 0.7, "2026-08-02T00:00:00"),
        _evidence_row("overall", 0.9, "2026-08-03T00:00:00"),
    ]
    journey = speaking_svc.speaking_journey(rows)
    assert journey["attempts"] == 3
    assert len(journey["steps"]) == 3
    assert [s["numeric"] for s in journey["steps"]] == [3.5, 4.0, 4.75]
    assert [s["level"] for s in journey["steps"]] == ["B2", "B2", "C1"]
    assert [s["confidence"] for s in journey["steps"]] == [0.0, 0.5, 0.75]
    assert journey["current_level"] == "C1"
    assert journey["current_numeric"] == pytest.approx(4.75)
    assert journey["current_confidence"] == pytest.approx(0.75)


def test_speaking_level_and_journey_endpoint(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    with TestClient(app) as client:
        client.post(
            "/api/academy/objective/speaking",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "expected": "I am a student",
                "heard": "I am a student",
                "duration_seconds": 3.0,
            },
        )
        level = client.get("/api/academy/speaking/level", params={"user_id": a})
        journey = client.get("/api/academy/speaking/journey", params={"user_id": a})
    assert level.status_code == 200
    assert level.json()["attempts"] == 1
    assert level.json()["level"] is not None
    assert journey.status_code == 200
    assert journey.json()["attempts"] == 1
    assert len(journey.json()["steps"]) == 1


# --- V1.16 S4b: InteractionEvidence 2.0 — señal objetiva (fusión) ----------


def _interaction_objective(turn_balance=1.0, turn_duration=0.8):
    return {
        "turn_balance": turn_balance,
        "avg_response_latency_ms": 400,
        "turn_duration": turn_duration,
        "student_turns": 2,
        "assistant_turns": 2,
        "interruptions": 0,
    }


def test_interaction_score_fuses_objective_and_semantic():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "appropriate_responses": 0.9,
        "turn_completion": 0.8,
        "follow_up_questions": 0.7,
        "topic_maintenance": 0.8,
        "clarification_requests": 0.5,
        "interaction_objective": _interaction_objective(
            turn_balance=1.0, turn_duration=1.0
        ),
    }
    semantic = 0.781
    objective = 1.0
    # Fusión 0.3·objetiva + 0.7·semántica = 0.3·1.0 + 0.7·0.781 = 0.847.
    assert speaking_svc._interaction_score(evidence) == pytest.approx(
        round(0.3 * objective + 0.7 * semantic, 3)
    )


def test_interaction_score_objective_only():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "interaction_objective": _interaction_objective(
            turn_balance=1.0, turn_duration=0.5
        ),
    }
    # objetiva: (0.3·1.0 + 0.7·0.5) / 1.0 = 0.65.
    assert speaking_svc._interaction_score(evidence) == 0.65


def test_interaction_score_semantic_only_unchanged():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "appropriate_responses": 0.9,
        "turn_completion": 0.8,
        "follow_up_questions": 0.7,
        "topic_maintenance": 0.8,
        "clarification_requests": 0.5,
    }
    assert speaking_svc._interaction_score(evidence) == pytest.approx(0.781)


def test_interaction_score_legacy_fallback_unchanged():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": ["student"],
        "coherence": 0.9,
        "interaction": 0.65,
    }
    assert speaking_svc._interaction_score(evidence) == 0.65


def test_interaction_score_objective_empty_dict_is_none():
    assert speaking_svc._interaction_score({"interaction_objective": {}}) is None


# --- V1.17: puente conversación → speaking (inyección de interaction_objective)


def test_scores_from_evidence_interaction_objective_fused():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "appropriate_responses": 0.8,
        "turn_completion": 0.6,
        "follow_up_questions": 0.7,
        "topic_maintenance": 0.9,
        "clarification_requests": 0.5,
        "interaction_objective": {"turn_balance": 0.8, "turn_duration": 0.6},
    }
    result = speaking_svc.scores_from_evidence(
        evidence, "I am a student", 60.0, task_type="conversation"
    )
    assert result["observed"]["interaction"] is True
    # Señal semántica = 0.718; señal objetiva = (0.3·0.8 + 0.7·0.6) = 0.66.
    semantic = 0.718
    objective = 0.66
    fused = round(0.3 * objective + 0.7 * semantic, 3)
    interaction = result["criteria"]["interaction"]
    assert min(objective, semantic) <= interaction <= max(objective, semantic)
    assert interaction == pytest.approx(fused)


def test_scores_from_evidence_interaction_without_objective_unchanged():
    evidence = {
        "task_achieved": True,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.9,
        "appropriate_responses": 0.8,
        "turn_completion": 0.6,
        "follow_up_questions": 0.7,
        "topic_maintenance": 0.9,
        "clarification_requests": 0.5,
    }
    result = speaking_svc.scores_from_evidence(
        evidence, "I am a student", 60.0, task_type="conversation"
    )
    # Sin interaction_objective, interaction = señal semántica (backward-compat).
    assert result["observed"]["interaction"] is True
    assert result["criteria"]["interaction"] == pytest.approx(0.718)


def test_speaking_task_with_conversation_injects_interaction(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    obj = _first_speaking_objective()
    # Conversación con turnos que llevan telemetría (2 alumno, 1 asistente).
    cid = conversations_repo.create_conversation(a)["id"]
    conversations_repo.save_conversation(
        cid,
        a,
        "T",
        [
            {
                "id": "m1",
                "role": "user",
                "content": "Hi",
                "duration_ms": 2000,
                "latency_ms": 400,
            },
            {
                "id": "m2",
                "role": "assistant",
                "content": "Hello",
                "duration_ms": 1000,
                "latency_ms": 200,
            },
            {
                "id": "m3",
                "role": "user",
                "content": "Bye",
                "duration_ms": 3000,
                "latency_ms": 600,
            },
        ],
    )
    fake = FakeOllamaClient(
        content='{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student", "live", "city"], "coherence": 0.8}'
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/speaking/task",
            params={"user_id": a},
            json={
                "level_id": "a1",
                "objective_id": obj.id,
                "task": "Introduce yourself",
                "heard": "I am a student",
                "task_type": "conversation",
                "conversation_id": cid,
            },
        )
    assert r.status_code == 200
    body = r.json()
    # Sin evidencia semántica de interacción, la señal objetiva de turnos debe
    # hacer observable el criterio `interaction` (fusión end-to-end).
    assert body["observed"]["interaction"] is True
    assert body["criteria"]["interaction"] == pytest.approx(0.7)
