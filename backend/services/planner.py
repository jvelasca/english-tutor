"""Planner del repaso léxico: la SIGUIENTE TAREA ÓPTIMA (V3.38).

V3.35-V3.37 construyeron la infraestructura adaptativa: evidencia longitudinal
(`learning_evidence`), dimensiones del evento (apoyo, dificultad, contexto,
latencia, tipo de error), cues graduados y la política de consolidación y
regresión de la escalera de recall. Faltaba USAR esa evidencia para planificar:
responder "¿por qué esta tarea, por qué ahora, con qué apoyo?".

Este módulo puro (sin I/O ni FastAPI) aporta dos cosas:

1. `planned_signals` + `priority_score` — una PUNTUACIÓN de la siguiente tarea
   óptima que combina la urgencia del scheduler (`forgetting`) con el hueco
   pedagógico (`gap`), la debilidad observada (`weakness`), la dependencia de
   apoyo (`support`) y la latencia (`latency`). Los pesos son declarados y
   calibrables; el orden de la cola de repaso pasa a ser una decisión explicable
   en lugar de solo "menor retrievability primero".
2. `evidence_reason` — razones ADITIVAS dirigidas por la evidencia fina que
   V3.36 empezó a registrar y V3.38 sabe leer por modalidad:
   `error_prone` (confusión real, no errata), `skill_gap` (consolidado en una
   modalidad pero sin producción en la otra) y `slow_recall` (aciertos que aún
   no son fluidos). Ninguna sustituye a las razones de hueco de V3.35: solo
   entran cuando el ledger las justifica.

La segmentación por modalidad (`services.evidence.automatic_skills`) alimenta
`skill_gaps`: qué modalidades NO tienen ningún éxito. Es lo que permite decir
"puede recuperarla, pero nunca la ha producido por escrito".

Puro y determinista: recibe el resumen de evidencia y la matriz de competencia
ya calculados. Nunca lanza.
"""

from __future__ import annotations

from collections.abc import Mapping

from services import difficulty, task_semantics
from services.evidence import (
    LEXICAL_SKILLS,
    RECALL_SKILL,
    TRANSFER_DEMONSTRATED_STATES,
    automatic_skills,
    is_automatic,
    transfer_confidence,
    transfer_state,
)

# Pesos declarados de la prioridad (suman 1.0). El olvido manda — es la razón de
# que la carta esté vencida —, pero un hueco de producción pesa casi tanto como
# la urgencia: es la diferencia entre "repasar" y "cerrar el hueco".
PRIORITY_WEIGHTS: dict[str, float] = {
    "forgetting": 0.35,
    "gap": 0.30,
    "weakness": 0.20,
    "support": 0.10,
    "latency": 0.05,
}

# Latencia (ms) a partir de la cual un acierto de recall NO es fluido: hay
# recuperación, pero no automaticidad en velocidad. Declarado y calibrable.
SLOW_RECALL_MS = 8000.0

# Techo de normalización de la latencia (ms): por encima, `latency` = 1.0.
LATENCY_CEILING_MS = 20000.0

# ---------------------------------------------------------------------------
# V3.56 (Planner 2.0): valor ESPERADO de aprendizaje.
#
# Hasta V3.55 el planner solo sabía cuánto URGE repasar un ítem (suma ponderada
# de olvido, hueco, debilidad, apoyo y latencia). No predecía si el alumno PODRÁ
# con la tarea. El ELV combina las dos mitades:
#
#   P(éxito)   ← margen de CAPACIDAD (capacidad del alumno − dificultad declarada
#                de la tarea, en la dimensión limitante);
#   V(valor)   ← `priority_score` (mismos pesos declarados; no se añade ninguno);
#   ELV        = dificultad_deseable(P) × V   (máximo en P ≈ 0.5).
#
# La curva `SUCCESS_BY_MARGIN` es una tabla DECLARADA, monótona no decreciente y
# acotada en (0, 1): nada de parámetros estimados por datos ni de meterse
# `retrievability` en `p` (el olvido sigue pesando donde ya pesaba, dentro del
# valor). El margen se declara en PASOS de carga (1..5): −1 significa que la
# tarea pide una unidad más que la capacidad del alumno en su eslabón más débil.
SUCCESS_BY_MARGIN: dict[int, float] = {
    -3: 0.05,
    -2: 0.15,
    -1: 0.35,
    0: 0.55,
    1: 0.75,
    2: 0.90,
    3: 0.95,
}

# Sin capacidad del alumno o sin dificultad declarada del ítem la predicción es
# NEUTRA: `p = 0.5` → `desirability(0.5) = 1.0` → `ELV = priority`. Es el
# invariante de no-regresión de V3.56: la cola queda idéntica a la de V3.55.0.
P_SUCCESS_UNKNOWN = 0.5

# Umbrales DECLARADOS de la explicación (`why`): por debajo, la tarea está por
# encima de la capacidad observada; por encima, sobra. Aditivos.
P_SUCCESS_LOW = 0.35
P_SUCCESS_HIGH = 0.75

# Fallos "otra palabra" (NO errata) que exigen volver a practicar el ítem: una
# errata dice que el alumno sabe la palabra; `wrong_word` dice que no.
ERROR_PRONE_MIN_WRONG = 2

# Modalidades de PRODUCCIÓN: su ausencia en el ledger es el hueco que cierra la
# actividad `sentence`.
PRODUCTION_SKILLS: tuple[str, ...] = ("written_production", "spoken_production")

# V3.57: orden canónico de las candidatas de PRODUCCIÓN del argmax. El hueco
# ORAL se propone antes que el escrito: es la preferencia histórica de V3.38.1 y
# hace que el desempate del argmax no dependa del orden de `PRODUCTION_SKILLS`.
GAP_CANDIDATE_ORDER: tuple[str, ...] = ("spoken_production", "written_production")

# V3.38.1 (P1-03): modalidad que la actividad `sentence` SÍ puede cerrar — la
# producción ORAL. El hueco parcial `written ✓ / spoken ✗` debe ser accionable;
# el simétrico (`spoken ✓ / written ✗`) se sigue exponiendo en `skill_gaps` pero
# no emite razón hasta que la cola tenga un drill de escritura (V3.39).
SPEAKING_SKILL = "spoken_production"

# Actividad del drill que cierra cada razón dirigida por la evidencia.
# V3.39/V3.40: mapa LEGACY conservado por retrocompatibilidad; la fuente de
# verdad es `ACTIVITY_FOR_SKILL` (una razón puede cerrarse con más de una
# actividad: `skill_gap` → `sentence` o `write` según la modalidad que falte).
ACTIVITY_FOR_REASON: dict[str, str] = {
    "error_prone": "recall",
    "skill_gap": "sentence",
    "slow_recall": "recall",
    "transfer_gap": "transfer",
}

# V3.39 (Fase 3, motor de tarea óptima): ACTIVIDAD que cierra cada MODALIDAD.
# Es la tabla que separa la SELECCIÓN DE ACTIVIDAD ("¿qué ejercicio toca?") de
# la PUNTUACIÓN DE PRIORIDAD ("¿qué ítem primero?"), que V3.38 tenía mezcladas
# en el mapeo razón→actividad (P1-02 de la auditoría de V3.38.1).
#   recall            → el propio peldaño de recuperación;
#   spoken_production → frase oral guiada (`sentence`);
#   written_production→ escritura de una frase propia (`write`, V3.39);
#   spontaneous_use   → producción ABIERTA en un contexto nuevo (`transfer`,
#                       V3.40): la transferencia contextual es su propia tarea.
ACTIVITY_FOR_SKILL: dict[str, str] = {
    RECALL_SKILL: "recall",
    "spoken_production": "sentence",
    "written_production": "write",
    "spontaneous_use": "transfer",
}

# Nivel de apoyo que DECLARA cada actividad del drill (mismos valores canónicos
# que el ledger: `copied → guided → cued → independent → spontaneous`). La
# decisión lo expone para que la cola sea explicable sin re-derivarlo.
ACTIVITY_SUPPORT_LEVEL: dict[str, str] = {
    "recognition": "cued",
    "recall": "cued",
    "sentence": "guided",
    "write": "independent",
    # V3.40: la consigna de transferencia ofrece un contexto nuevo, no ayuda con
    # la unidad: la producción es del alumno (uso espontáneo).
    "transfer": "spontaneous",
}

# Modalidad de la TRANSFERENCIA contextual (V3.40, P1-03 de la auditoría de
# V3.38.1): usar la unidad en un contexto distinto del de aprendizaje.
TRANSFER_SKILL = "spontaneous_use"

# V3.40: éxitos en contextos distintos exigidos para declarar transferencia
# (espejo de `services.evidence.CONTEXT_TRANSFER_MIN`).
TRANSFER_MIN_SUCCESS_CONTEXTS = 2

# V3.40: éxitos totales mínimos antes de proponer transferencia. Con un solo uso
# la unidad aún se está aprendiendo; transferir exige cierta solidez.
TRANSFER_MIN_SUCCESSES = 2

# Orden de prioridad de las razones dirigidas por la evidencia (el primero que
# se cumpla gana). Declarado para que el desempate no dependa del diccionario.
EVIDENCE_REASON_ORDER: tuple[str, ...] = (
    "error_prone",
    "skill_gap",
    "slow_recall",
    # V3.40: la transferencia va AL FINAL: solo cuando no hay nada más urgente
    # (ni confusión, ni hueco de modalidad, ni fluidez pendiente) tiene sentido
    # pedir uso en un contexto nuevo.
    "transfer_gap",
)


def _int(value: object) -> int:
    """Entero no negativo (0 si falta o no es numérico)."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _ratio(part: int, total: int) -> float:
    """`part / total` acotado a [0, 1] (0.0 si no hay total)."""
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, part / total))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# V3.56: núcleo puro del valor esperado de aprendizaje (Planner 2.0).
# ---------------------------------------------------------------------------


def success_probability(margin: object) -> float:
    """Probabilidad de éxito por MARGEN de capacidad (V3.56, pura).

    `margin` es `capacidad − dificultad` en la dimensión limitante (ver
    `capacity_margin`). `None` (sin capacidad o sin dificultad declarada) y
    cualquier entrada no numérica degradan al NEUTRO `P_SUCCESS_UNKNOWN`: no se
    inventa predicción sin datos. Fuera de la tabla se recorta al extremo más
    cercano (clamp), de modo que un margen enorme nunca sale de (0, 1) ni lanza.
    """
    if margin is None or isinstance(margin, bool):
        return P_SUCCESS_UNKNOWN
    try:
        value = int(margin)
    except (TypeError, ValueError):
        return P_SUCCESS_UNKNOWN
    low = min(SUCCESS_BY_MARGIN)
    high = max(SUCCESS_BY_MARGIN)
    if value < low:
        return SUCCESS_BY_MARGIN[low]
    if value > high:
        return SUCCESS_BY_MARGIN[high]
    return SUCCESS_BY_MARGIN[value]


def capacity_margin(task_difficulty: object, learner_capacity: object) -> int | None:
    """Margen de capacidad de la tarea: mínimo de las dimensiones comparables.

    Normaliza ambos vectores (`difficulty.normalize_vector`) y devuelve el
    MÍNIMO margen de las dimensiones que la TAREA declara y existen en la
    capacidad: la tarea falla por su eslabón más débil, así que la restricción
    limitante manda.

    Una dimensión declarada por la tarea pero SIN capacidad no se cuenta como 0
    (no se inventa un margen negativo sin evidencia). Sin ninguna dimensión
    comparable, o sin dificultad declarada, devuelve `None` (predicción neutra).
    Nunca lanza.
    """
    task = difficulty.normalize_vector(task_difficulty)
    capacity = difficulty.normalize_vector(learner_capacity)
    if not task or not capacity:
        return None
    margins = [
        capacity[dimension] - load
        for dimension, load in task.items()
        if dimension in capacity
    ]
    if not margins:
        return None
    return min(margins)


def desirability(p_success: object) -> float:
    """Factor de dificultad DESEABLE (zona de desarrollo próximo) (V3.56, pura).

    `4·p·(1−p)` acotado a [0, 1]: máximo exacto en `p = 0.5` (ni trivial ni
    inalcanzable valen poco) y 0 en los extremos. Con el neutro `p = 0.5` da
    `1.0`, que es lo que hace que la degradación sin estado sea exacta
    (`ELV = priority`). Nunca lanza.
    """
    try:
        value = _clamp(float(p_success))
    except (TypeError, ValueError):
        value = P_SUCCESS_UNKNOWN
    return round(_clamp(4.0 * value * (1.0 - value)), 4)


def expected_learning_value(
    signals: dict,
    *,
    skill: str = "",
    task_difficulty: object = None,
    learner_capacity: object = None,
    value: float | None = None,
    capacity_skill: str = "",
) -> dict:
    """Valor ESPERADO de aprendizaje de la tarea (V3.56 → V3.57, puro).

    Combina el valor pedagógico declarado (`priority_score(signals)`, los MISMOS
    pesos) con la probabilidad de éxito por margen de capacidad:

        ELV = desirability(p_success) × value

    Devuelve `{expected_learning_value, p_success, desirability, value, margin,
    skill, capacity_skill}`. Sin capacidad ni dificultad declarada: `margin =
    None`, `p_success = 0.5`, `desirability = 1.0` y `ELV = value` (degradación
    neutra EXACTA de la cola). `skill` es la modalidad (EJE) que la tarea
    evalúa y `capacity_skill` el CANAL cuyo margen se midió (V3.57: aditivo,
    vacío cuando no se declaró). Nunca lanza.

    V3.57 añade dos parámetros OPCIONALES y aditivos: `value` (por defecto
    `None`, que reproduce el `priority_score` global de V3.56; el argmax de
    tarea pasa el valor POR MODALIDAD de `skill_priorities`) y `capacity_skill`
    (informativo). Los llamadores de V3.56 no cambian.
    """
    if value is None:
        base = priority_score(signals)
    else:
        try:
            base = round(_clamp(float(value)), 4)
        except (TypeError, ValueError):
            base = priority_score(signals)
    margin = capacity_margin(task_difficulty, learner_capacity)
    p_success = success_probability(margin)
    desirability_factor = desirability(p_success)
    return {
        "expected_learning_value": round(desirability_factor * base, 4),
        "p_success": p_success,
        "desirability": desirability_factor,
        "value": base,
        "margin": margin,
        "skill": skill,
        "capacity_skill": str(capacity_skill or ""),
    }


def capacity_skill(skill: object) -> str:
    """Canal EVALUADO cuyo margen mide esta modalidad de EJE (V3.57, pura).

    El ELV necesita la capacidad de lo que la actividad MIDE, no de lo que su
    eje QUIERE provocar: `transfer` tiene eje `spontaneous_use`, pero se entrega
    por texto y evalúa producción ESCRITA (`task_semantics`). Sin esta
    separación, el eje `spontaneous_use` no tendría capacidad observada (el
    ledger la acredita por canal) y `write`/`transfer` se leerían como dos
    mediciones distintas de `written_production` en lugar de una misma LECTURA.
    Una modalidad sin actividad declarada cae al propio eje (no se inventa
    canal) y vacío devuelve "". Nunca lanza.
    """
    text = str(skill or "").strip().lower()
    if not text:
        return ""
    activity = ACTIVITY_FOR_SKILL.get(text, "")
    assessed = task_semantics.assessed_skill_for(activity) if activity else ""
    return assessed or text


def error_prone(evidence: dict | None) -> bool:
    """¿El ítem acumula confusión real (`wrong_word` repetido)? (V3.38, puro).

    V3.39 (Fase 3C): si el resumen trae la VENTANA de recencia
    (`recent_wrong_word`, que ya aportan `summarize_evidence`/el resumen SQL), el
    juicio mira SOLO esa ventana: lo que importa es la confusión que sigue
    ocurriendo, no la de hace cuarenta repasos. Sin ventana (resumen parcial) se
    cae al histórico, como en V3.38.
    """
    if not evidence:
        return False
    recent = evidence.get("recent_wrong_word")
    if recent is not None:
        try:
            return int(recent) >= ERROR_PRONE_MIN_WRONG
        except (TypeError, ValueError):
            pass
    errors = evidence.get("error_types")
    if not isinstance(errors, dict):
        return False
    return _int(errors.get("wrong_word")) >= ERROR_PRONE_MIN_WRONG


def _successful_skills(evidence: dict | None) -> list[str]:
    """Modalidades con AL MENOS un éxito en el ledger (orden canónico).

    Vacía si el resumen no trae segmentación (evidencia legacy sin modalidad).
    """
    if not evidence:
        return []
    successes = evidence.get("skill_successes")
    if not isinstance(successes, dict):
        return []
    return [skill for skill in LEXICAL_SKILLS if _int(successes.get(skill))]


def skill_gaps(evidence: dict | None) -> list[str]:
    """Modalidades de PRODUCCIÓN sin ningún éxito, si el ítem ya logra algo.

    Es el hueco que cierra la actividad `sentence`: el ítem tiene evidencia de
    logro en alguna modalidad, pero ninguna de producción (ni escrita ni oral).
    Vacía si no hay ningún éxito (nada que transferir todavía) o si no hay
    segmentación por modalidad.
    """
    achieved = _successful_skills(evidence)
    if not achieved:
        return []
    return [skill for skill in PRODUCTION_SKILLS if skill not in achieved]


def has_production_evidence(evidence: dict | None) -> bool:
    """¿Hay algún éxito en una modalidad de PRODUCCIÓN? (V3.38, puro)."""
    achieved = _successful_skills(evidence)
    return any(skill in achieved for skill in PRODUCTION_SKILLS)


def is_slow_recall(evidence: dict | None) -> bool:
    """¿El RECALL es correcto pero aún no fluido? (V3.38 puro → V3.38.1).

    V3.38 leía la latencia MEDIA GLOBAL (`mean_response_time_ms`), que mezcla
    modalidades: una producción oral de 12 s y un recall de 2 s promedian 7 s y
    no revelan que la recuperación textual es rápida (ni al revés). V3.38.1
    (P1-02) lee la latencia DE RECALL (`skill_mean_response_time_ms["recall"]`).

    Exige latencia de recall medida Y al menos un ÉXITO de recall: la latencia
    de un fallo no mide fluidez, mide dificultad (señal que cubre `weakness`).
    Sin latencia de recall no hay señal: no se inventa.
    """
    if not evidence:
        return False
    latencies = evidence.get("skill_mean_response_time_ms")
    if not isinstance(latencies, dict):
        return False
    latency = latencies.get(RECALL_SKILL)
    if latency is None:
        return False
    try:
        measured = float(latency)
    except (TypeError, ValueError):
        return False
    recall_successes = _int(
        (evidence.get("skill_successes") or {}).get(RECALL_SKILL)
    )
    return measured >= SLOW_RECALL_MS and recall_successes > 0


def skill_signals(evidence: dict | None) -> dict[str, dict]:
    """Señales por MODALIDAD (V3.38.1, puro y determinista).

    El Evidence Model segmenta el ledger por modalidad, pero el planner V3.38
    lo volvía a recomprimir en una `weakness`/`support`/`latency` global: 20
    aciertos de recall y 2 de speaking sobre 8 fallos daban un único 0.3125 y
    se perdía el problema real. Estas señales conservan la segmentación para
    que el planner pueda razonar por modalidad sin migrar el contrato global.

    Devuelve una entrada por modalidad canónica (`LEXICAL_SKILLS`), con zeros
    donde no hay evidencia (determinista y de forma estable). No entra en
    `priority_score` todavía: V3.38.1 solo las usa para `slow_recall`, el
    `skill_gap` parcial y la explicabilidad; la prioridad por skill es V3.39.
    """
    ev = evidence or {}
    attempts = ev.get("skill_attempts") or {}
    successes = ev.get("skill_successes") or {}
    independent = ev.get("skill_independent_successes") or {}
    latencies = ev.get("skill_mean_response_time_ms") or {}
    if not all(
        isinstance(bucket, dict)
        for bucket in (attempts, successes, independent, latencies)
    ):
        attempts = successes = independent = latencies = {}
    result: dict[str, dict] = {}
    for skill in LEXICAL_SKILLS:
        total = _int(attempts.get(skill))
        won = _int(successes.get(skill))
        ind = _int(independent.get(skill))
        rate = _ratio(won, total)
        latency = 0.0
        raw = latencies.get(skill)
        if raw is not None:
            try:
                latency = _clamp(float(raw) / LATENCY_CEILING_MS)
            except (TypeError, ValueError):
                latency = 0.0
        result[skill] = {
            "attempts": total,
            "successes": won,
            "success_rate": round(rate, 4),
            "weakness": round(_clamp(1.0 - rate), 4),
            "support": round(1.0 - _ratio(ind, won), 4) if won > 0 else 0.0,
            "latency": round(latency, 4),
        }
    return result


def directed_production_gap(matrix: dict | None, evidence: dict | None) -> str:
    """Modalidad de PRODUCCIÓN sin éxito que el drill puede cerrar (V3.39, puro).

    Es la generalización del hueco de V3.38.1: antes solo `spoken_production`
    era accionable (la actividad `sentence`); con la actividad de escritura
    (`write`, V3.39) el hueco SIMÉTRICO `spoken ✓ / written ✗` también lo es.

    Orden declarado y estable: si falta la modalidad ORAL se devuelve esa (el
    comportamiento de V3.38.1 no cambia); si ya hay logro oral pero falta la
    escrita, se devuelve `written_production`.

    Vacía si no hay ningún logro previo (nada que transferir), si la matriz no
    declara producción o si no hay hueco de producción.
    """
    if not (matrix or {}).get("production"):
        return ""
    gaps = skill_gaps(evidence)
    if not gaps:
        return ""
    if SPEAKING_SKILL in gaps:
        return SPEAKING_SKILL
    for skill in gaps:
        if skill in ACTIVITY_FOR_SKILL:
            return skill
    return ""


def has_contextual_transfer(evidence: dict | None) -> bool:
    """¿La unidad tiene transferencia contextual DEMOSTRADA? (V3.40 → V3.43).

    V3.43 (P1-04): deja de bastar el booleano `transfer` (que exigía solo dos
    `context_id` distintos, aunque fueran el mismo tipo de producción) y manda el
    ESTADO: `transfer_demonstrated`, `transfer_stable` o `automatic`. Con un
    resumen parcial sin `transfer_state` se cae al booleano histórico.
    """
    ev = evidence or {}
    state = ev.get("transfer_state")
    if state:
        return state in TRANSFER_DEMONSTRATED_STATES
    return bool(ev.get("transfer"))


def transfer_gap(evidence: dict | None) -> bool:
    """¿Toca TRANSFERIR la unidad a un contexto nuevo? (V3.40 → V3.43, puro).

    La auditoría de V3.38.1 (P1-03) pidió separar `situation` (recuperación
    contextualizada) de la transferencia real: usar la unidad en un contexto
    DISTINTO del de aprendizaje. `services.evidence.context_signals` aporta los
    contextos con éxito limpio; aquí se decide si es el momento de pedirla.

    Exige, para no adelantarse:
    - que el ledger tenga contexto registrado (`context_attempts > 0`);
    - al menos `TRANSFER_MIN_SUCCESSES` éxitos (un solo uso aún se está
      aprendiendo).

    V3.43 (P1-04): con `transfer_state` formalizado, el hueco se dispara en
    `emerging` (un contexto limpio) y `contextualized` (varios contextos pero SIN
    diversidad real: es justo cuando hay que empujar a un contexto distinto).
    Desde `transfer_demonstrated` ya no hay hueco (`has_contextual_transfer`).

    Sin `transfer_state` (resumen parcial) se mantiene el criterio histórico:
    éxito en AL MENOS un contexto y en MENOS de `TRANSFER_MIN_SUCCESS_CONTEXTS`.
    """
    if not evidence:
        return False
    contexts = evidence.get("contexts")
    if not isinstance(contexts, dict) or not contexts:
        return False
    if _int(evidence.get("context_attempts")) <= 0:
        return False
    if has_contextual_transfer(evidence):
        return False
    successes = sum(
        _int(bucket.get("successes"))
        for bucket in contexts.values()
        if isinstance(bucket, dict)
    )
    if successes < TRANSFER_MIN_SUCCESSES:
        return False
    state = evidence.get("transfer_state")
    if state:
        return state in ("emerging", "contextualized")
    success_contexts = evidence.get("success_contexts")
    if isinstance(success_contexts, list):
        distinct = len([c for c in success_contexts if str(c or "").strip()])
    else:  # resumen parcial sin la lista: se deriva del mapa de contextos
        distinct = sum(
            1
            for bucket in contexts.values()
            if isinstance(bucket, dict) and _int(bucket.get("successes")) > 0
        )
    return 1 <= distinct < TRANSFER_MIN_SUCCESS_CONTEXTS


def skill_priority(signals: dict) -> dict[str, float]:
    """Prioridad 0..1 POR MODALIDAD (V3.39, puro).

    Aplica los MISMOS pesos declarados (`PRIORITY_WEIGHTS`) a las señales de cada
    modalidad (`signals["skills"]`): la debilidad, la dependencia de apoyo y la
    latencia son por modalidad, mientras que el olvido (`forgetting`) y el hueco
    (`gap`) son del ítem y se comparten. Es la pieza que permite responder "¿qué
    skill limita?" en lugar de "¿cuánto urge?".

    Devuelve una entrada por modalidad presente en `signals["skills"]` (dict
    vacío si no hay segmentación). Nunca lanza.
    """
    skills = signals.get("skills") if isinstance(signals, dict) else None
    if not isinstance(skills, dict):
        return {}
    try:
        forgetting = _clamp(float(signals.get("forgetting") or 0.0))
    except (TypeError, ValueError):
        forgetting = 0.0
    try:
        gap = _clamp(float(signals.get("gap") or 0.0))
    except (TypeError, ValueError):
        gap = 0.0
    result: dict[str, float] = {}
    for skill, data in skills.items():
        payload = data if isinstance(data, dict) else {}
        result[str(skill)] = priority_score(
            {
                "forgetting": forgetting,
                "gap": gap,
                "weakness": payload.get("weakness", 0.0),
                "support": payload.get("support", 0.0),
                "latency": payload.get("latency", 0.0),
            }
        )
    return result


def skill_priorities(signals: dict) -> dict[str, float]:
    """Vector COMPLETO de prioridad por modalidad, en orden canónico (V3.51).

    V3.50 exponía la modalidad limitante como un único argmax, lo que descartaba
    el resto de la información pedagógica (con `written_production=0.62` y
    `spoken_production=0.60` la segunda desaparecía de la decisión). Este vector
    conserva TODAS las prioridades para que el selector pueda razonar sobre
    ellas: la primera del orden canónico (`LEXICAL_SKILLS`) es siempre la
    limitante cuando hay empate.

    Es un diccionario ordenado: primero las modalidades canónicas (recall,
    written_production, spoken_production, spontaneous_use) y después cualquier
    clave no canónica presente en las señales. Vacío si no hay bloque `skills`.
    Nunca lanza.
    """
    priorities = skill_priority(signals)
    if not priorities:
        return {}
    ordered: dict[str, float] = {
        skill: priorities[skill] for skill in LEXICAL_SKILLS if skill in priorities
    }
    for skill, value in priorities.items():
        if skill not in ordered:
            ordered[skill] = value
    return ordered


def limiting_skill(signals: dict) -> str:
    """Modalidad con mayor prioridad (argmax) (V3.39 → V3.51, pura).

    Desempate determinista por el orden canónico `LEXICAL_SKILLS` (recall antes
    que producción), de modo que sin evidencia segmentada la decisión cae en
    `recall` —el peldaño por defecto del repaso— y no en un orden accidental de
    diccionario. Se implementa sobre `skill_priorities` (vector completo), así
    que el argmax y el vector no pueden divergir. Devuelve "" si no hay bloque
    `skills`. Nunca lanza.
    """
    priorities = skill_priorities(signals)
    if not priorities:
        return ""
    # `max` es estable sobre el orden de inserción: con prioridades empatadas
    # gana la primera del orden canónico.
    return max(priorities, key=lambda skill: priorities[skill])


def _task(skill: str, reason: str) -> dict:
    activity = ACTIVITY_FOR_SKILL.get(skill, "")
    return {
        "skill": skill,
        "activity": activity,
        "reason": reason,
        "support_level": ACTIVITY_SUPPORT_LEVEL.get(activity, ""),
    }


def select_task(
    matrix: dict | None,
    evidence: dict | None,
    signals: dict | None = None,
) -> dict:
    """Tarea ÓPTIMA por skill: `{skill, activity, reason, support_level}` (V3.39).

    Función PURA y determinista que decide QUÉ modalidad limita y QUÉ actividad
    la cierra, separando esa decisión de la puntuación de prioridad (P1-02 de la
    auditoría de V3.38.1). Orden declarado:

    1. `error_prone` — confusión real acumulada (`wrong_word` repetido) → volver
       a recuperar (`recall`);
    2. `skill_gap` — hay logro previo y falta una modalidad de producción → la
       actividad de ESA modalidad (oral → `sentence`; escrita → `write`);
    3. `slow_recall` — recuperación correcta pero lenta → `recall`.
    4. `transfer_gap` — la unidad ya se usa con éxito pero solo en un contexto →
       usarla en un contexto NUEVO (`transfer`, modalidad `spontaneous_use`).

    Si no hay directriz devuelve `{skill: "", activity: "", reason: "",
    support_level: ""}`: la escalera de competencia de V3.35 decide y el
    comportamiento previo no cambia. Nunca lanza.
    """
    try:
        resolvers = {
            "error_prone": lambda: (
                RECALL_SKILL if error_prone(evidence) else ""
            ),
            "skill_gap": lambda: directed_production_gap(matrix, evidence),
            "slow_recall": lambda: (
                RECALL_SKILL if is_slow_recall(evidence) else ""
            ),
            "transfer_gap": lambda: (
                TRANSFER_SKILL if transfer_gap(evidence) else ""
            ),
        }
        for reason in EVIDENCE_REASON_ORDER:
            # Cada resolutor devuelve la MODALIDAD que limita (o "" si esa razón
            # no aplica): la tabla `ACTIVITY_FOR_SKILL` cierra el resto.
            skill = resolvers[reason]()
            if skill:
                return _task(skill, reason)
    except Exception:  # noqa: BLE001 — el planner nunca rompe la cola
        return {"skill": "", "activity": "", "reason": "", "support_level": ""}
    return {"skill": "", "activity": "", "reason": "", "support_level": ""}


def task_candidates(matrix: dict | None, evidence: dict | None) -> list[dict]:
    """Tareas ADMISIBLES hoy, en orden canónico (V3.57, pura y determinista).

    Es el conjunto sobre el que V3.57 hace el argmax: las MISMAS razones que la
    cascada `select_task` ya sabe justificar, sin inventar tareas.

    1. `error_prone` (gana sobre `slow_recall`) → `recall`;
    2. cada modalidad de producción SIN éxito (`skill_gap`) que la matriz declare
       accionable, en el orden canónico `GAP_CANDIDATE_ORDER` (oral antes que
       escrita);
    3. `transfer_gap` → `spontaneous_use` (solo con su propio gate: base previa y
       menos contextos de los exigidos).

    Sin directriz devuelve `[]` (la escalera de V3.35 decide). Nunca lanza: una
    candidata por modalidad (sin duplicados) y `support_level` declarado por la
    actividad, de modo que el argmax devuelva el mismo contrato que `select_task`.
    """
    mx = matrix if isinstance(matrix, dict) else {}
    try:
        candidates: list[dict] = []
        seen: set[str] = set()

        def _add(skill: str, reason: str) -> None:
            if not skill or skill in seen:
                return
            seen.add(skill)
            candidates.append(_task(skill, reason))

        if error_prone(evidence):
            _add(RECALL_SKILL, "error_prone")
        elif is_slow_recall(evidence):
            _add(RECALL_SKILL, "slow_recall")
        if mx.get("production"):
            gaps = skill_gaps(evidence)
            for skill in GAP_CANDIDATE_ORDER:
                if skill in gaps and skill in ACTIVITY_FOR_SKILL:
                    _add(skill, "skill_gap")
        if transfer_gap(evidence):
            _add(TRANSFER_SKILL, "transfer_gap")
        return candidates
    except Exception:  # noqa: BLE001 — el planner nunca rompe la cola
        return []


def select_task_by_elv(
    matrix: dict | None,
    evidence: dict | None,
    signals: dict | None = None,
    *,
    capacity_by_skill: dict | None = None,
    task_difficulty: object = None,
    skill_values: dict | None = None,
    drivers: dict | None = None,
) -> dict:
    """Tarea ÓPTIMA por argmax de ELV entre las candidatas admisibles (V3.57).

    Función PURA y determinista. Con `capacity_by_skill` (capacidad por CANAL
    evaluado, calculada por el llamador desde el estado O(1) del alumno) puntúa
    cada candidata con `expected_learning_value` — `value` POR MODALIDAD
    (`skill_priorities`) y margen del CANAL que la actividad mide
    (`capacity_skill`) — y devuelve la de mayor valor esperado.

    Invariante de no-regresión: **solo compiten las candidatas con margen
    comparable** (una modalidad sin datos tiene `p = 0.5` → deseabilidad `1.0`,
    el MÁXIMO, y competiría premiada por ignorancia). Sin capacidad, sin
    candidatas o sin ningún margen comparable devuelve `select_task` EXACTO: sin
    estado del alumno la tarea servida es la de V3.56.0. El empate lo rompe el
    orden canónico de `task_candidates` (`>` estricto). Nunca lanza.

    V3.64 (Planner 3.0, ADITIVO) añade dos argumentos OPCIONALES que vienen de la
    **Decision Projection** (`services.decision_projection`), nunca del estado
    persistido:

    - `skill_values` — valor pedagógico PROYECTADO por eje (`{skill: 0..1}`), que
      sustituye a `skill_priorities` como `value` de la ELV. Incorpora la
      retención, la transferencia y el esfuerzo observado como señales de primera
      clase;
    - `drivers` — `{skill: drivers}` de la proyección, para explicar la decisión.

    Con ellos, la respuesta gana una clave ADITIVA `decision`
    (`expected_learning_value`, `p_success`, `margin`, `capacity_skill`, `value`,
    `drivers`, `why` y las alternativas puntuadas). **Sin** ellos la respuesta es
    **byte-idéntica** a V3.63. Nunca lanza.
    """
    if not isinstance(capacity_by_skill, dict) or not capacity_by_skill:
        return _attach_decision(
            select_task(matrix, evidence, signals),
            _cascade_decision(matrix, evidence, signals, skill_values, drivers),
        )
    candidates = task_candidates(matrix, evidence)
    if not candidates:
        return _attach_decision(
            select_task(matrix, evidence, signals),
            _cascade_decision(matrix, evidence, signals, skill_values, drivers),
        )
    priorities = skill_priorities(signals or {})
    base_value = priority_score(signals or {})
    best: dict | None = None
    best_value = -1.0
    scored: list[dict] = []
    for candidate in candidates:
        skill = candidate.get("skill") or ""
        channel = capacity_skill(skill)
        payload = expected_learning_value(
            signals or {},
            skill=skill,
            task_difficulty=task_difficulty,
            learner_capacity=capacity_by_skill.get(channel),
            value=_projected_value(skill_values, priorities, skill, base_value),
            capacity_skill=channel,
        )
        scored.append(
            {
                "skill": skill,
                "activity": candidate.get("activity") or "",
                "expected_learning_value": payload["expected_learning_value"],
                "p_success": payload["p_success"],
                "margin": payload["margin"],
                "value": payload["value"],
                "capacity_skill": channel,
                "comparable": payload["margin"] is not None,
            }
        )
        if payload["margin"] is None:
            continue
        if payload["expected_learning_value"] > best_value:
            best_value = payload["expected_learning_value"]
            best = candidate
    if best is None:
        return _attach_decision(
            select_task(matrix, evidence, signals),
            _cascade_decision(
                matrix, evidence, signals, skill_values, drivers, scored
            ),
        )
    return _attach_decision(
        best,
        (
            _decision_block(best, scored, signals, skill_values, drivers)
            if _has_projection(skill_values, drivers)
            else None
        ),
    )


def _has_projection(skill_values: object, drivers: object) -> bool:
    """¿El llamador aportó la Decision Projection? (V3.64, puro).

    Es la condición de la NO-REGRESIÓN de V3.57: sin proyección no se añade
    ninguna clave y `select_task_by_elv` es byte-idéntico a V3.63. Nunca lanza.
    """
    return isinstance(skill_values, Mapping) or isinstance(drivers, Mapping)


def _projected_value(
    skill_values: dict | None,
    priorities: Mapping,
    skill: str,
    base_value: float,
) -> float:
    """`value` de la ELV: proyectado si lo hay, `skill_priorities` si no (V3.64).

    Nunca lanza: un valor proyectado no numérico cae al de V3.57.
    """
    if not isinstance(skill_values, Mapping):
        return priorities.get(skill, base_value)
    projected = skill_values.get(skill)
    try:
        return round(_clamp(float(projected)), 4)
    except (TypeError, ValueError):
        return priorities.get(skill, base_value)


def _driver_of(drivers: object, skill: str) -> dict:
    """Drivers declarados de una skill ({} si no hay; nunca lanza)."""
    if not isinstance(drivers, Mapping):
        return {}
    declared = drivers.get(skill)
    return dict(declared) if isinstance(declared, Mapping) else {}


def _decision_block(
    chosen: Mapping,
    scored: list[dict],
    signals: dict,
    skill_values: object,
    drivers: object,
) -> dict:
    """Bloque `decision` de la tarea elegida (V3.64, puro y aditivo)."""
    skill = str(chosen.get("skill") or "")
    entry = next(
        (item for item in scored if item.get("skill") == skill),
        {
            "skill": skill,
            "activity": chosen.get("activity") or "",
            "expected_learning_value": 0.0,
            "p_success": P_SUCCESS_UNKNOWN,
            "margin": None,
            "value": priority_score(signals or {}),
            "capacity_skill": capacity_skill(skill),
            "comparable": False,
        },
    )
    driver = _driver_of(drivers, skill)
    return {
        **entry,
        "source": "argmax",
        "projected": isinstance(skill_values, Mapping),
        # Punto 26 del informe: el encaje de la tarea en la capacidad observada
        # (`difficulty_fit`) depende de la dificultad de la TAREA, así que vive
        # aquí (el planner ya mide el `margin`) y NO en la proyección del estado.
        "difficulty_fit": difficulty_fit(entry.get("p_success"), entry.get("margin")),
        "drivers": driver,
        "why": explain_drivers(driver),
        "alternatives": list(scored),
    }


def difficulty_fit(p_success: object, margin: object = None) -> str:
    """Encaje DECLARADO de la tarea en la capacidad observada (V3.64, puro).

    `"above"` (la tarea está por encima de lo observado), `"in_zone"` (zona de
    desarrollo próximo), `"below"` (por debajo: sobra capacidad) y `"unknown"`
    cuando no hay margen comparable. Reutiliza las bandas YA declaradas de V3.56
    (`P_SUCCESS_LOW`/`P_SUCCESS_HIGH`): **no** introduce umbrales nuevos. Nunca
    lanza.
    """
    if margin is None:
        return "unknown"
    try:
        probability = float(p_success)
    except (TypeError, ValueError):
        return "unknown"
    if probability <= P_SUCCESS_LOW:
        return "above"
    if probability >= P_SUCCESS_HIGH:
        return "below"
    return "in_zone"


def _cascade_decision(
    matrix: dict | None,
    evidence: dict | None,
    signals: dict | None,
    skill_values: object,
    drivers: object,
    scored: list[dict] | None = None,
) -> dict | None:
    """Bloque `decision` de la DEGRADACIÓN a la cascada (V3.64, puro).

    Solo se construye cuando el llamador ha pasado la proyección: sin ella la
    respuesta debe seguir siendo **byte-idéntica** a V3.63, así que no se añade
    ninguna clave. Nunca lanza.
    """
    if not _has_projection(skill_values, drivers):
        return None
    planned = select_task(matrix, evidence, signals)
    skill = str(planned.get("skill") or "")
    return {
        **_decision_block(planned, scored or [], signals or {}, skill_values, drivers),
        "source": "cascade",
        "skill": skill,
        "activity": planned.get("activity") or "",
    }


def _attach_decision(task: dict, decision: dict | None) -> dict:
    """Respuesta del planner con el bloque `decision` SOLO si procede (V3.64).

    Sin proyección (`decision is None`) devuelve `task` **tal cual**: la
    invariante de no-regresión de V3.57 exige byte-identidad.
    """
    if decision is None:
        return task
    return {**task, "decision": decision}


def evidence_reason(matrix: dict | None, evidence: dict | None) -> str:
    """Razón dirigida por la evidencia fina, o "" (V3.38 → V3.39, puro).

    Se conserva como fachada estable del vocabulario de razones: delega en
    `select_task` (única fuente de verdad). Un resumen vacío o legacy devuelve
    "": las razones de hueco de V3.35 siguen siendo la decisión por defecto.
    """
    return select_task(matrix, evidence).get("reason", "")



def planned_signals(
    evidence: dict | None,
    matrix: dict | None,
    *,
    retrievability: float | None = None,
) -> dict:
    """Señales deterministas de la siguiente tarea óptima (V3.38, puro).

    - `forgetting` — 1 - `retrievability` (0.0 si el scheduler no la conoce):
      cuánto se ha olvidado desde el último repaso;
    - `gap` — 1.0 si falta la producción (`production_gap`), 0.5 si falta
      transferencia (`transfer_gap`), 0.0 sin hueco declarado;
    - `weakness` — 1 - `success_rate` (0.0 sin intentos);
    - `support` — proporción de éxitos que NO fueron independientes (0.0 sin
      éxitos): un ítem que solo acierta con apoyo depende de él;
    - `latency` — latencia media normalizada por `LATENCY_CEILING_MS`;
    - `skills` — V3.38.1: las señales `weakness`/`support`/`latency` y la
      `success_rate` segmentadas POR MODALIDAD, que evitan recomprimir la
      evidencia fina en una sola media global.
    - `transfer` / `success_contexts` / `home_context` — V3.40: transferencia
      contextual (éxito en >= 2 contextos distintos) y los contextos con éxito,
      la señal que habilita la tarea `transfer` (`spontaneous_use`).
    - `transfer_state` / `context_diversity` — V3.43: estado formalizado del eje
      (sustituto gradual de `transfer`) y diversidad contextual real de los
      contextos con éxito limpio (explicabilidad).
    - `transfer_confidence` — V3.49: confianza explicable del eje
      (`services.evidence.transfer_confidence`: score/nivel/drivers).
    """
    ev = evidence or {}
    mx = matrix or {}
    try:
        forgetting = (
            1.0 - _clamp(float(retrievability)) if retrievability is not None else 0.0
        )
    except (TypeError, ValueError):
        forgetting = 0.0
    if mx.get("production_gap"):
        gap = 1.0
    elif mx.get("transfer_gap"):
        gap = 0.5
    else:
        gap = 0.0
    attempts = _int(ev.get("attempts"))
    successes = _int(ev.get("successes"))
    independent = _int(ev.get("independent_successes"))
    weakness = 0.0
    if attempts:
        rate = ev.get("success_rate")
        try:
            weakness = 1.0 - _clamp(float(rate))
        except (TypeError, ValueError):
            weakness = 1.0 - _ratio(successes, attempts)
    latency = 0.0
    if ev.get("mean_response_time_ms") is not None:
        try:
            latency = _clamp(float(ev["mean_response_time_ms"]) / LATENCY_CEILING_MS)
        except (TypeError, ValueError):
            latency = 0.0
    # Sin éxitos no hay dependencia de apoyo que medir (0.0, no 1.0).
    support = 1.0 - _ratio(independent, successes) if successes > 0 else 0.0
    return {
        "forgetting": round(_clamp(forgetting), 4),
        "gap": round(gap, 4),
        "weakness": round(_clamp(weakness), 4),
        "support": round(_clamp(support), 4),
        "latency": round(latency, 4),
        "automatic": is_automatic(ev),
        "automatic_skills": automatic_skills(ev),
        "skill_gaps": skill_gaps(ev),
        # V3.38.1 (P1-02): señales por modalidad (no entran aún en la prioridad
        # global; alimentan `slow_recall`, `skill_gap` y la explicabilidad).
        "skills": skill_signals(ev),
        "error_prone": error_prone(ev),
        "slow_recall": is_slow_recall(ev),
        # V3.40 (Fase 4): transferencia contextual (contexto distinto del de
        # aprendizaje). Señal del ítem, no de una modalidad.
        "transfer": has_contextual_transfer(ev),
        # V3.43 (P1-03/P1-04): estado formalizado y diversidad contextual real
        # (explicabilidad; `transfer` se conserva como booleano de compatibilidad).
        "transfer_state": ev.get("transfer_state") or transfer_state(ev),
        # V3.49 (Transfer Evidence 3.0): confianza explicable del eje (score,
        # nivel y drivers). Aditiva; no altera ninguna decisión previa.
        "transfer_confidence": transfer_confidence(ev),
        "context_diversity": (
            dict(ev["context_diversity"])
            if isinstance(ev.get("context_diversity"), dict)
            else {}
        ),
        "transfer_gap": transfer_gap(ev),
        "success_contexts": list(ev.get("success_contexts") or []),
        "home_context": ev.get("home_context") or "",
        "context_attempts": _int(ev.get("context_attempts")),
    }


def priority_score(signals: dict) -> float:
    """Prioridad 0..1 de la siguiente tarea (V3.38, puro).

    Suma ponderada de `PRIORITY_WEIGHTS`. Un diccionario incompleto cuenta 0 en
    las señales que falten: nunca lanza.
    """
    total = 0.0
    for key, weight in PRIORITY_WEIGHTS.items():
        try:
            total += weight * _clamp(float(signals.get(key, 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
    return round(_clamp(total), 4)


def _capacity_phrases(learning_value: dict | None) -> list[str]:
    """Frases ADITIVAS de capacidad para `why` (V3.56, pura).

    Solo cuando hay predicción (`learning_value` con `margin` no `None`): sin
    margen no se inventa explicación de capacidad. Los umbrales son declarados
    (`P_SUCCESS_LOW`/`P_SUCCESS_HIGH`). Nunca lanza.
    """
    if not isinstance(learning_value, dict):
        return []
    if learning_value.get("margin") is None:
        return []
    try:
        p_success = float(learning_value.get("p_success"))
    except (TypeError, ValueError):
        return []
    if p_success <= P_SUCCESS_LOW:
        return ["currently above your observed capacity"]
    if p_success >= P_SUCCESS_HIGH:
        return ["well within your observed capacity"]
    return [
        f"challenging but achievable (about {round(p_success * 100)}%"
        " expected success)"
    ]


def explain_drivers(driver: Mapping | None) -> list[str]:
    """Frases ADITIVAS (inglés) de los drivers de la proyección (V3.64, pura).

    Mismo registro que `explain_priority`: frases cortas, deterministas y en
    inglés, el contrato `why` del proyecto. Un driver VACÍO no aporta ninguna
    frase (nunca se inventa explicación): solo un driver medido o declarado como
    no medido produce texto. Nunca lanza.
    """
    if not isinstance(driver, Mapping) or not driver:
        return []
    if driver.get("measured") is False:
        return ["no spaced evidence yet"]
    parts: list[str] = []
    gap = str(driver.get("gap") or "")
    if gap == "high":
        parts.append("large competence gap in the limiting modality")
    elif gap == "medium":
        parts.append("competence gap still open")
    if driver.get("retention_due"):
        parts.append("review is due")
    transfer_gap = str(driver.get("transfer_gap") or "")
    if transfer_gap == "high":
        parts.append("no contextual transfer yet")
    elif transfer_gap == "medium":
        parts.append("transfer only partly demonstrated")
    effort = str(driver.get("effort") or "")
    if effort == "high":
        parts.append("success so far needed heavy support")
    elif effort == "some":
        parts.append("success so far needed some support")
    if driver.get("recent_failure"):
        parts.append("recent task errors in this modality")
    if str(driver.get("assessment_confidence") or "") == "low":
        parts.append("assessment coverage is low")
    return parts


def explain_priority(
    signals: dict,
    reason: str = "",
    learning_value: dict | None = None,
    drivers: Mapping | None = None,
) -> str:
    """Explicación legible (inglés) de por qué esta tarea es la siguiente.

    Mismo registro que `services.adaptive.explain_priority`: frases cortas
    separadas por `; `, deterministas y en inglés (el contrato `why` del
    proyecto). V3.56 añade frases ADITIVAS de capacidad cuando la predicción
    existe (`learning_value` con `margin` no `None`): por debajo de
    `P_SUCCESS_LOW` la tarea está por encima de lo observado, por encima de
    `P_SUCCESS_HIGH` sobra, y en medio se explica el porcentaje esperado. Sin
    predicción, las frases son exactamente las de V3.55. Nunca lanza.

    V3.64 añade `drivers` (OPCIONAL) y, con él, las frases de la Decision
    Projection al final de la explicación: sin `drivers` la salida es
    **byte-idéntica** a V3.63.
    """
    parts: list[str] = []
    if reason == "weak_recognition":
        parts.append("no receptive base yet")
    if reason == "no_recall_evidence":
        parts.append("recognition without recall evidence")
    if reason == "production_gap":
        parts.append("recognized but never produced")
    if reason == "error_prone":
        parts.append("repeated wrong-word errors")
    if reason == "skill_gap":
        gaps = signals.get("skill_gaps") or []
        if gaps:
            parts.append(f"no success yet in {', '.join(gaps)}")
        else:
            parts.append("production modality still missing")
    if reason == "slow_recall":
        parts.append("correct but not yet fluent")
    if reason == "transfer_gap":
        parts.append("used in one context only; time to transfer it")
    if reason == "automatic_maintenance":
        parts.append("automatic: spaced independent success")
    parts.extend(_capacity_phrases(learning_value))
    try:
        forgetting = float(signals.get("forgetting") or 0.0)
    except (TypeError, ValueError):
        forgetting = 0.0
    if forgetting >= 0.5:
        parts.append("due for review (memory decayed)")
    if signals.get("support"):
        try:
            if float(signals["support"]) >= 0.5:
                parts.append("successes still depend on support")
        except (TypeError, ValueError):
            pass
    # V3.64: frases de la Decision Projection (aditivas; nada sin `drivers`).
    parts.extend(explain_drivers(drivers))
    if not parts:
        parts.append("scheduled maintenance")
    return "; ".join(parts)
