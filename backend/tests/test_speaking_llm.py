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
