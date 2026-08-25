"""Tests del módulo de extracción de evidencia de writing con LLM."""

from services import writing_llm


def test_build_writing_prompt_has_roles_and_content():
    msgs = writing_llm.build_writing_prompt("Introduce yourself", "I am a student")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Introduce yourself" in msgs[1]["content"]
    assert "I am a student" in msgs[1]["content"]
    for key in (
        "task_completed",
        "grammar_errors",
        "lexical_tokens",
        "organization",
        "coherence",
        "register",
    ):
        assert key in msgs[0]["content"]


def test_parse_writing_evidence_valid_json():
    raw = (
        '{"task_completed": true, "grammar_errors": 2, '
        '"lexical_tokens": ["Student", "Live"], "organization": 0.8, '
        '"coherence": 0.75, "register": 0.6}'
    )
    assert writing_llm.parse_writing_evidence(raw) == {
        "task_completed": True,
        "grammar_errors": 2,
        "lexical_tokens": ["student", "live"],
        "organization": 0.8,
        "coherence": 0.75,
        "register": 0.6,
    }


def test_parse_writing_evidence_tolerates_code_fence():
    raw = (
        '```json\n{"task_completed": false, "grammar_errors": 0, '
        '"lexical_tokens": [], "organization": 0.5, "coherence": 0.5, '
        '"register": 0.5}\n```'
    )
    assert writing_llm.parse_writing_evidence(raw) == {
        "task_completed": False,
        "grammar_errors": 0,
        "lexical_tokens": [],
        "organization": 0.5,
        "coherence": 0.5,
        "register": 0.5,
    }


def test_parse_writing_evidence_clamps_scores():
    raw = (
        '{"task_completed": true, "grammar_errors": 0, '
        '"lexical_tokens": ["ok"], "organization": 1.5, "coherence": -0.2, '
        '"register": 0.5}'
    )
    evidence = writing_llm.parse_writing_evidence(raw)
    assert evidence["organization"] == 1.0
    assert evidence["coherence"] == 0.0


def test_parse_writing_evidence_invalid_returns_none():
    # JSON malformado.
    assert writing_llm.parse_writing_evidence("no es json") is None
    # Falta una clave.
    assert writing_llm.parse_writing_evidence('{"task_completed": true}') is None
    # grammar_errors negativo.
    assert (
        writing_llm.parse_writing_evidence(
            '{"task_completed": true, "grammar_errors": -1, '
            '"lexical_tokens": [], "organization": 0.5, "coherence": 0.5, '
            '"register": 0.5}'
        )
        is None
    )
    # task_completed no booleano.
    assert (
        writing_llm.parse_writing_evidence(
            '{"task_completed": "yes", "grammar_errors": 0, '
            '"lexical_tokens": [], "organization": 0.5, "coherence": 0.5, '
            '"register": 0.5}'
        )
        is None
    )
    # grammar_errors booleano (type(True) is int es False).
    assert (
        writing_llm.parse_writing_evidence(
            '{"task_completed": true, "grammar_errors": true, '
            '"lexical_tokens": [], "organization": 0.5, "coherence": 0.5, '
            '"register": 0.5}'
        )
        is None
    )
    # lexical_tokens con un elemento no string.
    assert (
        writing_llm.parse_writing_evidence(
            '{"task_completed": true, "grammar_errors": 0, '
            '"lexical_tokens": [1], "organization": 0.5, "coherence": 0.5, '
            '"register": 0.5}'
        )
        is None
    )
    # organization booleano (bool rechazado como número).
    assert (
        writing_llm.parse_writing_evidence(
            '{"task_completed": true, "grammar_errors": 0, '
            '"lexical_tokens": [], "organization": true, "coherence": 0.5, '
            '"register": 0.5}'
        )
        is None
    )
