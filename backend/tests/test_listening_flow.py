"""V3.27 (Listening Engine 4.0): política del micro-flujo por ítem
(services.listening_flow). Verifica el contrato `{flow, transcript_policy}` y el
barrido determinista sobre todo el banco."""
from services.listening import QUESTION_BANK
from services.listening_flow import (
    FLOW_STAGES,
    REVELATION_MODES,
    build_item_flow,
    flow_for_question,
    transcript_policy,
)


def _policy_of(level: str, layer: str | None = None) -> dict:
    return transcript_policy(level, layer)


def test_policy_a1_is_permissive():
    p = _policy_of("A1")
    assert p["revelation"] == "on_first_fail"
    assert p["max_attempts_per_stage"] == 2
    assert p["allow_manual_reveal"] is True


def test_policy_a2_second_fail():
    p = _policy_of("A2")
    assert p["revelation"] == "on_second_fail"
    assert p["max_attempts_per_stage"] == 2


def test_policy_b2_plus_strict():
    for level in ("B2", "C1", "C2"):
        p = _policy_of(level)
        assert p["revelation"] == "never_before_post"
        assert p["max_attempts_per_stage"] == 1
        assert p["allow_manual_reveal"] is False


def test_policy_unknown_level_falls_back_to_on_finish():
    p = _policy_of("Z9")
    assert p["revelation"] == "on_finish"
    assert p["max_attempts_per_stage"] == 1


def test_policy_recognition_relaxes_revelation_in_strict_levels():
    p = _policy_of("B2", layer="recognition")
    assert p["revelation"] == "on_second_fail"
    assert p["allow_manual_reveal"] is True


def test_policy_returns_copy():
    p1 = _policy_of("A1")
    p1["revelation"] = "tampered"
    assert _policy_of("A1")["revelation"] == "on_first_fail"


def _find(flow: list[dict], stage: str) -> dict:
    return next(step for step in flow if step["stage"] == stage)


def test_production_item_flow_is_single_task():
    flow = build_item_flow({"skill": "dictation", "level": "A1"})
    assert len(flow) == 1
    assert flow[0]["stage"] == "while2"
    assert flow[0]["task"] == "production"
    assert flow[0]["transcript_state_inicial"] == "hidden"
    assert flow[0]["allow_skip"] is False
    # shadowing (skill) también es producción.
    shadowing_item = build_item_flow({"skill": "shadowing", "level": "A1"})
    assert shadowing_item[0]["task"] == "production"


def test_receptive_item_flow_has_five_stages():
    flow = build_item_flow({"skill": "gist", "level": "B1"})
    stages = [s["stage"] for s in flow]
    assert stages == ["pre", "while1", "while2", "post", "shadowing"]
    assert flow[0]["task"] == "activate"
    assert flow[1]["task"] == "listen_global"
    assert flow[2]["task"] == "native_question"
    assert _find(flow, "while2")["transcript_state_inicial"] == "hidden"
    assert _find(flow, "post")["transcript_state_inicial"] == "partial"
    assert _find(flow, "shadowing")["transcript_state_inicial"] == "full"
    # Modo rápido: pre y while1 saltables; la pregunta real no.
    assert flow[0]["allow_skip"] is True
    assert flow[1]["allow_skip"] is True
    assert flow[2]["allow_skip"] is False


def test_shadowing_optional_from_policy():
    policy = {"shadowing_optional": False}
    flow = build_item_flow({"skill": "detail", "level": "B1"}, policy)
    assert _find(flow, "shadowing")["allow_skip"] is False
    policy = {"shadowing_optional": True}
    flow = build_item_flow({"skill": "detail", "level": "B1"}, policy)
    assert _find(flow, "shadowing")["allow_skip"] is True


def test_flow_for_question_payload_contract():
    payload = flow_for_question({"skill": "gist", "level": "A1", "id": "x"})
    assert set(payload) == {"flow", "transcript_policy"}
    assert isinstance(payload["flow"], list) and payload["flow"]
    policy = payload["transcript_policy"]
    assert policy["revelation"] in REVELATION_MODES
    assert policy["max_attempts_per_stage"] >= 1
    for step in payload["flow"]:
        assert step["stage"] in FLOW_STAGES
        assert step["transcript_state_inicial"] in ("hidden", "partial", "full")


def test_flow_profile_overrides_shadowing_optional():
    base = flow_for_question({"skill": "detail", "level": "B1"})
    assert base["transcript_policy"]["shadowing_optional"] is True
    perfil = {"intervention": "bottom_up_path"}
    adaptado = flow_for_question({"skill": "detail", "level": "B1"}, perfil)
    assert adaptado["transcript_policy"]["shadowing_optional"] is False


def test_whole_bank_produces_valid_flows():
    """Barrido determinista: ningún ítem del banco rompe el builder."""
    assert len(QUESTION_BANK) >= 400
    for question in QUESTION_BANK:
        flow = build_item_flow(question)
        assert flow, question.get("id")
        for step in flow:
            assert set(step) == {
                "stage",
                "task",
                "transcript_state_inicial",
                "allow_skip",
                "requires_audio",
            }, question.get("id")
            assert step["stage"] in FLOW_STAGES, question.get("id")
