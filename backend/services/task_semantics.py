"""Semántica explícita de TAREA → SKILL (V3.51).

Hasta V3.50 el proyecto declaraba la modalidad limitante del ítem
(`planner.limiting_skill`) y la usaba para ELEGIR el contexto de transferencia
(`services.transfer.context_for(skill=...)`), pero el ledger seguía registrando
todo intento de transferencia como `skill="spontaneous_use"`. Eso dejaba una
ambigüedad real (P1-01 de la auditoría externa de V3.50): la `skill` del
contexto limitaba la SELECCIÓN, pero no necesariamente era la modalidad
EVALUADA por la actividad.

Este módulo puro separa las cuatro dimensiones que V3.50 mezclaba:

- ``target_skill``    — la competencia que la tarea QUIERE provocar (eje de
                        transferencia para ``transfer``: ``spontaneous_use``);
- ``assessed_skill``  — la competencia que la tarea REALMENTE puede medir con
                        su modo de entrega (el drill Transfer se entrega por
                        TEXTO: mide producción ESCRITA, no oral);
- ``assessment_mode`` — el canal de observación: ``written``/``spoken``/
                        ``receptive``;
- ``evidence_skill``  — el valor que HOY se persiste en ``learning_evidence.skill``
                        (contrato del gate de transferencia, V3.46/V3.47). Se
                        reproduce LITERALMENTE para no alterar la escalera; un
                        test de paridad contra los ``skill=`` reales lo fija.

Es una tabla declarativa, sin I/O, sin LLM, sin reloj y sin aleatoriedad. Nunca
lanza: una actividad desconocida devuelve un registro vacío (no se inventa
semántica).
"""

from __future__ import annotations

# Canales de observación de un intento. `receptive` existe en el vocabulario
# para que la taxonomía sea única y admita el MCQ de Recognition cuando algún
# día escriba evidencia (hoy es informativo y no toca el ledger).
ASSESSMENT_MODES: tuple[str, ...] = ("written", "spoken", "receptive")

# Orden canónico del vocabulario de modalidades. Espejo local de
# `services.evidence.LEXICAL_SKILLS` (no se importa para no acoplar la capa
# pura al ledger; un test de paridad falla si divergen), usado para devolver
# conjuntos en un orden ESTABLE.
SKILL_ORDER: tuple[str, ...] = (
    "recall",
    "written_production",
    "spoken_production",
    "spontaneous_use",
)

# Actividad del micro-drill → semántica declarada. La clave es el nombre de la
# actividad del planner (`ACTIVITY_FOR_SKILL`) o del paso del drill (`drill:*`).
#
#   word      — el alumno DICE la palabra tras un modelo (ASR): oral;
#   sentence  — el alumno DICE una frase con la unidad (ASR): oral;
#   write     — el alumno ESCRIBE una frase propia: escrito;
#   recall    — el alumno TECLEA la forma desde su significado: escrito;
#   transfer  — el alumno produce en un contexto nuevo. El drill lo entrega por
#               TEXTO (textarea), así que la modalidad evaluada es ESCRITA
#               (`written_production`), mientras que el eje sigue siendo el uso
#               espontáneo (`spontaneous_use`) que acredita la transferencia.
TASK_SEMANTICS: dict[str, dict[str, str]] = {
    "word": {
        "target_skill": "spoken_production",
        "assessed_skill": "spoken_production",
        "assessment_mode": "spoken",
        "evidence_skill": "spoken_production",
    },
    "sentence": {
        "target_skill": "spoken_production",
        "assessed_skill": "spoken_production",
        "assessment_mode": "spoken",
        "evidence_skill": "spoken_production",
    },
    "write": {
        "target_skill": "written_production",
        "assessed_skill": "written_production",
        "assessment_mode": "written",
        "evidence_skill": "written_production",
    },
    "recall": {
        "target_skill": "recall",
        "assessed_skill": "recall",
        "assessment_mode": "written",
        "evidence_skill": "recall",
    },
    "transfer": {
        "target_skill": "spontaneous_use",
        "assessed_skill": "written_production",
        "assessment_mode": "written",
        "evidence_skill": "spontaneous_use",
    },
}

# Mapa inverso declarado actividad → capacidad de producción del eje, para que
# el planner sepa con qué tarea se CIERRA cada modalidad. Se conserva local para
# no depender de `services.planner` (que sí puede importar este módulo).
ACTIVITY_FOR_TARGET: dict[str, str] = {
    "recall": "recall",
    "spoken_production": "sentence",
    "written_production": "write",
    "spontaneous_use": "transfer",
}

_EMPTY: dict[str, str] = {
    "target_skill": "",
    "assessed_skill": "",
    "assessment_mode": "",
    "evidence_skill": "",
}


def _normalize(activity: object) -> str:
    """Nombre canónico de una actividad ("" si no se reconoce)."""
    return str(activity or "").strip().lower()


def semantics_for(activity: object) -> dict[str, str]:
    """Semántica declarada de una actividad (copia; vacía si no se reconoce).

    Devuelve una COPIA para que el llamador no pueda mutar la tabla declarativa.
    Nunca lanza.
    """
    declared = TASK_SEMANTICS.get(_normalize(activity))
    if not declared:
        return dict(_EMPTY)
    return dict(declared)


def target_skill_for(activity: object) -> str:
    """Competencia que la actividad QUIERE provocar ("" si no se reconoce)."""
    return TASK_SEMANTICS.get(_normalize(activity), _EMPTY)["target_skill"]


def assessed_skill_for(activity: object) -> str:
    """Competencia que la actividad REALMENTE evalúa ("" si no se reconoce)."""
    return TASK_SEMANTICS.get(_normalize(activity), _EMPTY)["assessed_skill"]


def assessment_mode_for(activity: object) -> str:
    """Canal de observación de la actividad ("" si no se reconoce)."""
    return TASK_SEMANTICS.get(_normalize(activity), _EMPTY)["assessment_mode"]


def evidence_skill_for(activity: object) -> str:
    """Valor que la actividad persiste en `learning_evidence.skill` ("" si no).

    Es el contrato HISTÓRICO del ledger: se reproduce literalmente para no
    alterar el gate de transferencia ni la segmentación por modalidad.
    """
    return TASK_SEMANTICS.get(_normalize(activity), _EMPTY)["evidence_skill"]


def assessable_skills(activity: object) -> tuple[str, ...]:
    """Modalidades que la actividad puede evocar/medir (orden canónico, V3.51).

    Es la unión de `target_skill` (lo que quiere provocar) y `assessed_skill`
    (lo que puede medir). Es lo que permite restringir la orientación de una
    tarea a las competencias que de verdad puede observar: el transfer, por
    ejemplo, no debe orientarse a `spoken_production` porque su entrega es
    escrita. Unión vacía si la actividad no se reconoce. Nunca lanza.
    """
    declared = TASK_SEMANTICS.get(_normalize(activity))
    if not declared:
        return ()
    wanted = {declared["target_skill"], declared["assessed_skill"]}
    return tuple(skill for skill in SKILL_ORDER if skill in wanted)


def is_assessable(activity: object, skill: object) -> bool:
    """¿La actividad puede evocar o medir esa modalidad? (V3.51, pura)."""
    wanted = str(skill or "").strip().lower()
    return bool(wanted) and wanted in assessable_skills(activity)


def activity_for_target(skill: object) -> str:
    """Actividad declarada para cerrar una modalidad ("" si no se reconoce)."""
    return ACTIVITY_FOR_TARGET.get(str(skill or "").strip().lower(), "")


def activity_from_activity_id(activity_id: object) -> str:
    """Nombre de actividad a partir del `activity_id` del ledger (V3.51, pura).

    El ledger usa `drill:<actividad>` y, en el recall, `drill:recall:<peldaño>`.
    Devuelve el primer segmento tras el prefijo `drill:` (`"recall"` también en
    el caso con peldaño). Otros prefijos (`lexicon:<canal>`) no son actividades
    de TASK_SEMANTICS y devuelven el texto tal cual (normalizado), de modo que
    `assessed_skill_for` pueda responder "" sin inventar. Nunca lanza.
    """
    text = str(activity_id or "").strip().lower()
    if text.startswith("drill:"):
        text = text[len("drill:"):]
    return text.split(":", 1)[0]
