"""Tests del módulo de extracción de evidencia de speaking con LLM."""

from services import speaking_llm


def test_build_speaking_prompt_has_roles_and_content():
    msgs = speaking_llm.build_speaking_prompt("Introduce yourself", "I am a student")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Introduce yourself" in msgs[1]["content"]
    assert "I am a student" in msgs[1]["content"]
    for key in (
        "task_achieved",
        "grammar_errors",
        "lexical_tokens",
        "coherence",
        "discourse_markers",
        "self_corrections",
        "hesitations",
        "repetitions",
        "interaction",
    ):
        assert key in msgs[0]["content"]


def test_parse_speaking_evidence_valid_json():
    raw = (
        '{"task_achieved": true, "grammar_errors": 2, '
        '"lexical_tokens": ["Student", "Live"], "coherence": 0.75}'
    )
    assert speaking_llm.parse_speaking_evidence(raw) == {
        "task_achieved": True,
        "grammar_errors": 2,
        "lexical_tokens": ["student", "live"],
        "coherence": 0.75,
        "discourse_markers": 0,
        "self_corrections": 0,
        "hesitations": 0,
        "repetitions": 0,
    }


def test_parse_speaking_evidence_extracts_optional_discourse_fields():
    raw = (
        '{"task_achieved": true, "grammar_errors": 1, '
        '"lexical_tokens": ["student"], "coherence": 0.8, "cohesion": 0.7, '
        '"discourse_markers": 3, "self_corrections": 1, "hesitations": 2, '
        '"repetitions": 1}'
    )
    assert speaking_llm.parse_speaking_evidence(raw) == {
        "task_achieved": True,
        "grammar_errors": 1,
        "lexical_tokens": ["student"],
        "coherence": 0.8,
        "cohesion": 0.7,
        "discourse_markers": 3,
        "self_corrections": 1,
        "hesitations": 2,
        "repetitions": 1,
    }


def test_parse_speaking_evidence_invalid_optional_counts_fall_back():
    # Counts con tipo inválido caen a default (0), sin invalidar la evidencia.
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": [], "coherence": 0.5, "discourse_markers": -1, '
        '"self_corrections": "dos"}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert result is not None
    assert result["discourse_markers"] == 0
    assert result["self_corrections"] == 0


def test_parse_speaking_evidence_tolerates_code_fence():
    raw = (
        '```json\n{"task_achieved": false, "grammar_errors": 0, '
        '"lexical_tokens": [], "coherence": 0.5}\n```'
    )
    assert speaking_llm.parse_speaking_evidence(raw) == {
        "task_achieved": False,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "coherence": 0.5,
        "discourse_markers": 0,
        "self_corrections": 0,
        "hesitations": 0,
        "repetitions": 0,
    }


def test_parse_speaking_evidence_extracts_interaction():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 0.8, "interaction": 0.7}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert result["interaction"] == 0.7


def test_parse_speaking_evidence_interaction_absent_omits_key():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 0.8}'
    )
    assert "interaction" not in speaking_llm.parse_speaking_evidence(raw)


def test_parse_speaking_evidence_clamps_coherence():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["ok"], "coherence": 1.5}'
    )
    assert speaking_llm.parse_speaking_evidence(raw)["coherence"] == 1.0


def test_parse_speaking_evidence_invalid_returns_none():
    # JSON malformado.
    assert speaking_llm.parse_speaking_evidence("no es json") is None
    # Falta una clave.
    assert speaking_llm.parse_speaking_evidence('{"task_achieved": true}') is None
    # grammar_errors negativo.
    assert (
        speaking_llm.parse_speaking_evidence(
            '{"task_achieved": true, "grammar_errors": -1, '
            '"lexical_tokens": [], "coherence": 0.5}'
        )
        is None
    )
    # task_achieved no booleano.
    assert (
        speaking_llm.parse_speaking_evidence(
            '{"task_achieved": "yes", "grammar_errors": 0, '
            '"lexical_tokens": [], "coherence": 0.5}'
        )
        is None
    )
    # grammar_errors booleano (type(True) is int es False).
    assert (
        speaking_llm.parse_speaking_evidence(
            '{"task_achieved": true, "grammar_errors": true, '
            '"lexical_tokens": [], "coherence": 0.5}'
        )
        is None
    )
    # lexical_tokens con un elemento no string.
    assert (
        speaking_llm.parse_speaking_evidence(
            '{"task_achieved": true, "grammar_errors": 0, '
            '"lexical_tokens": [1], "coherence": 0.5}'
        )
        is None
    )


def test_build_speaking_prompt_mentions_task_and_grammar_fields():
    msgs = speaking_llm.build_speaking_prompt("Introduce yourself", "I am a student")
    for key in (
        "task_completion",
        "task_relevance",
        "task_coverage",
        "task_appropriateness",
        "grammar_error_details",
    ):
        assert key in msgs[0]["content"]


def test_parse_speaking_evidence_extracts_task_subdims():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 0.8, '
        '"task_completion": 0.9, "task_relevance": 0.8}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert result["task_completion"] == 0.9
    assert result["task_relevance"] == 0.8
    # Sub-dimensiones ausentes no se añaden al dict (backward-compat).
    assert "task_coverage" not in result
    assert "task_appropriateness" not in result


def test_parse_speaking_evidence_extracts_grammar_details():
    raw = (
        '{"task_achieved": true, "grammar_errors": 2, '
        '"lexical_tokens": ["student"], "coherence": 0.8, '
        '"grammar_error_details": [{"type": "verb_tense", "severity": "minor"}, '
        '{"type": "Article", "severity": "critical"}]}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert result["grammar_error_details"] == [
        {"type": "verb_tense", "severity": "minor"},
        {"type": "article", "severity": "critical"},
    ]


def test_parse_speaking_evidence_invalid_grammar_details_dropped():
    # Entradas inválidas (severidad desconocida, sin type, type vacío) se descartan;
    # si no queda ninguna válida, la clave no se añade.
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": [], "coherence": 0.5, '
        '"grammar_error_details": [{"type": "x", "severity": "nope"}, '
        '{"severity": "minor"}, {"type": "", "severity": "minor"}]}'
    )
    assert "grammar_error_details" not in speaking_llm.parse_speaking_evidence(raw)


def test_parse_speaking_evidence_extracts_lexical_and_fluency_fields():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 0.8, '
        '"lexical_sophistication": 0.9, "lexical_precision": 0.7, '
        '"collocations": 0.6, "smoothness": 0.8, "rhythm": 0.7}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert result["lexical_sophistication"] == 0.9
    assert result["lexical_precision"] == 0.7
    assert result["collocations"] == 0.6
    assert result["smoothness"] == 0.8
    assert result["rhythm"] == 0.7


def test_parse_speaking_evidence_lexical_fields_absent_omitted():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 0.8}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert "lexical_sophistication" not in result
    assert "smoothness" not in result


def test_build_speaking_prompt_mentions_lexical_and_fluency_fields():
    msgs = speaking_llm.build_speaking_prompt("Introduce yourself", "I am a student")
    for key in (
        "lexical_sophistication",
        "lexical_precision",
        "collocations",
        "smoothness",
        "rhythm",
    ):
        assert key in msgs[0]["content"]


def test_parse_speaking_evidence_extracts_interaction_subdims():
    raw = (
        '{"task_achieved": true, "grammar_errors": 0, '
        '"lexical_tokens": ["student"], "coherence": 0.8, '
        '"turn_completion": 0.9, "follow_up_questions": 0.7, '
        '"appropriate_responses": 0.8, "topic_maintenance": 0.6, '
        '"clarification_requests": 0.4}'
    )
    result = speaking_llm.parse_speaking_evidence(raw)
    assert result["turn_completion"] == 0.9
    assert result["follow_up_questions"] == 0.7
    assert result["appropriate_responses"] == 0.8
    assert result["topic_maintenance"] == 0.6
    assert result["clarification_requests"] == 0.4


def test_build_speaking_prompt_mentions_interaction_subdims():
    msgs = speaking_llm.build_speaking_prompt("Introduce yourself", "I am a student")
    for key in (
        "turn_completion",
        "follow_up_questions",
        "appropriate_responses",
        "topic_maintenance",
        "clarification_requests",
    ):
        assert key in msgs[0]["content"]
