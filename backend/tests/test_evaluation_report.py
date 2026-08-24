"""Tests del informe agregado y el prompt del tutor (services/evaluation.py)."""
from services.evaluation import (
    TUTOR_PROMPTS,
    build_report,
    build_tutor_prompt,
    format_report,
)


def _result(total: int, case_id: str = "age") -> dict:
    return {
        "case_id": case_id,
        "correction": 100,
        "english": 100,
        "conciseness": 100,
        "engagement": 100,
        "total": total,
    }


def test_build_tutor_prompt_grammar():
    prompt = build_tutor_prompt({"mode": "grammar", "level": "A1"})
    assert "grammar" in prompt


def test_build_tutor_prompt_conversation():
    prompt = build_tutor_prompt({"mode": "conversation", "level": "A2"})
    assert "conversation" in prompt


def test_build_tutor_prompt_fallback_unknown():
    prompt = build_tutor_prompt({"mode": "unknown"})
    assert prompt == TUTOR_PROMPTS["conversation"]


def test_build_report_empty():
    report = build_report([])
    assert report["summary"]["cases"] == 0
    assert report["verdict"] == "sin datos"
    assert report["per_case"] == []


def test_build_report_verdict_excellent():
    report = build_report([_result(85)])
    assert report["verdict"] == "excelente"


def test_build_report_verdict_good():
    report = build_report([_result(65)])
    assert report["verdict"] == "bueno"


def test_build_report_verdict_regular():
    report = build_report([_result(45)])
    assert report["verdict"] == "regular"


def test_build_report_verdict_deficient():
    report = build_report([_result(20)])
    assert report["verdict"] == "deficiente"


def test_build_report_per_case_fields():
    report = build_report([_result(85, "age"), _result(20, "modal")])
    assert [c["case_id"] for c in report["per_case"]] == ["age", "modal"]
    assert report["per_case"][0]["correction"] == 100
    assert report["summary"]["cases"] == 2


def test_format_report_includes_verdict_and_cases():
    report = build_report([_result(85, "age")])
    text = format_report(report)
    assert "Veredicto: excelente" in text
    assert "[age]" in text
    assert "Casos evaluados: 1" in text
