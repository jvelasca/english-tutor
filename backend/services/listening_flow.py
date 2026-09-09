"""Política del micro-flujo por ítem de listening (V3.27, Listening Engine 4.0).

El backend es la fuente única de la política pedagógica (§3.1 del plan V3.27):
este módulo decide la secuencia de pasos de cada ítem (`flow`) y el contrato de
revelado de la transcripción (`transcript_policy`). El frontend solo ejecuta la
máquina de presentación con estos datos, sin constantes pedagógicas propias.

Contrato expuesto al cliente:
```
flow: [ { stage, task, transcript_state_inicial, allow_skip, requires_audio }, ... ]
transcript_policy: {
  revelation: "on_first_fail" | "on_second_fail" | "on_finish" | "never_before_post",
  max_attempts_per_stage: int,
  allow_manual_reveal: bool,
  shadowing_optional: bool
}
```
"""
from __future__ import annotations

from services.listening import skill_layer

FLOW_STAGES: tuple[str, ...] = ("pre", "while1", "while2", "post", "shadowing")

REVELATION_MODES: tuple[str, ...] = (
    "on_first_fail",
    "on_second_fail",
    "on_finish",
    "never_before_post",
)

# Política por defecto por nivel CEFR (a calibrar; la permisividad de la
# transcripción decrece al subir de nivel, spec §6.3).
_POLICY_BY_LEVEL: dict[str, dict] = {
    "A1": {
        "revelation": "on_first_fail",
        "max_attempts_per_stage": 2,
        "allow_manual_reveal": True,
        "shadowing_optional": True,
    },
    "A2": {
        "revelation": "on_second_fail",
        "max_attempts_per_stage": 2,
        "allow_manual_reveal": True,
        "shadowing_optional": True,
    },
    "B1": {
        "revelation": "on_finish",
        "max_attempts_per_stage": 1,
        "allow_manual_reveal": True,
        "shadowing_optional": True,
    },
    "B2": {
        "revelation": "never_before_post",
        "max_attempts_per_stage": 1,
        "allow_manual_reveal": False,
        "shadowing_optional": True,
    },
    "C1": {
        "revelation": "never_before_post",
        "max_attempts_per_stage": 1,
        "allow_manual_reveal": False,
        "shadowing_optional": True,
    },
    "C2": {
        "revelation": "never_before_post",
        "max_attempts_per_stage": 1,
        "allow_manual_reveal": False,
        "shadowing_optional": True,
    },
}

_DEFAULT_POLICY: dict = {
    "revelation": "on_finish",
    "max_attempts_per_stage": 1,
    "allow_manual_reveal": True,
    "shadowing_optional": True,
}


def transcript_policy(level: str, layer: str | None = None) -> dict:
    """Contrato de revelado y reintentos para un nivel (y capa) determinados.

    Devuelve una copia para que el llamador pueda aplicar overrides sin mutar la
    tabla. `layer` queda en la firma como afinación futura (p. ej. la capa
    `recognition` podría permitir revelar antes); hoy solo depende del nivel.
    """
    policy = dict(_POLICY_BY_LEVEL.get(level or "", _DEFAULT_POLICY))
    # Afinación por capa (reservada): recognition puede revelar tras un fallo en
    # cualquier nivel porque el objeto de la tarea es la palabra, no el discurso.
    if layer == "recognition" and policy.get("revelation") == "never_before_post":
        policy["revelation"] = "on_second_fail"
        policy["allow_manual_reveal"] = True
    return policy


def _production_flow() -> list[dict]:
    """Ítems de producción (dictation/shadowing): se sirven directos a la tarea,
    conservando el comportamiento actual (sin pre/while/post de recepción)."""
    return [
        {
            "stage": "while2",
            "task": "production",
            "transcript_state_inicial": "hidden",
            "allow_skip": False,
            "requires_audio": True,
        }
    ]


def _receptive_flow(shadowing_optional: bool) -> list[dict]:
    """Secuencia receptiva del micro-flujo para un ítem de comprensión.

    Fase 1 sin cloze: `while2` usa la pregunta nativa del ítem (su `question` y
    `options`, que ya son de su skill). `while1` es una escucha global sin
    respuesta (exposición inicial). `post` revela de forma parcial→completa según
    la política. `shadowing` es opcional según la política/el perfil.
    """
    return [
        {
            "stage": "pre",
            "task": "activate",
            "transcript_state_inicial": "hidden",
            "allow_skip": True,
            "requires_audio": False,
        },
        {
            "stage": "while1",
            "task": "listen_global",
            "transcript_state_inicial": "hidden",
            "allow_skip": True,
            "requires_audio": True,
        },
        {
            "stage": "while2",
            "task": "native_question",
            "transcript_state_inicial": "hidden",
            "allow_skip": False,
            "requires_audio": True,
        },
        {
            "stage": "post",
            "task": "review",
            "transcript_state_inicial": "partial",
            "allow_skip": False,
            "requires_audio": True,
        },
        {
            "stage": "shadowing",
            "task": "shadowing",
            "transcript_state_inicial": "full",
            "allow_skip": shadowing_optional,
            "requires_audio": True,
        },
    ]


def build_item_flow(question: dict, policy: dict | None = None) -> list[dict]:
    """Pasos del micro-flujo para un ítem.

    Los ítems de producción (`skill` dictation/shadowing) se sirven directos a su
    tarea; el resto recibe la secuencia receptiva. `policy` (opcional) permite
    fijar `shadowing_optional` en `allow_skip`.
    """
    skill = question.get("skill", "")
    if skill in ("dictation", "shadowing"):
        return _production_flow()
    shadowing_optional = True
    if policy:
        shadowing_optional = bool(policy.get("shadowing_optional", True))
    return _receptive_flow(shadowing_optional)


def flow_for_question(question: dict, perfil: dict | None = None) -> dict:
    """Payload `{flow, transcript_policy}` servido al cliente para un ítem.

    Aplica overrides del perfil auditivo (inc.5): si la intervención activa exige
    entrenar la producción (bottom-up / connected speech), el shadowing deja de
    ser opcional para ese ítem.
    """
    policy = transcript_policy(
        question.get("level", ""), skill_layer(question.get("skill", ""))
    )
    if perfil and perfil.get("intervention") in (
        "connected_speech_path",
        "bottom_up_path",
    ):
        policy["shadowing_optional"] = False
    return {
        "flow": build_item_flow(question, policy),
        "transcript_policy": policy,
    }
