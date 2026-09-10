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

from services.evidence import (
    LEXICAL_SKILLS,
    RECALL_SKILL,
    automatic_skills,
    is_automatic,
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

# Fallos "otra palabra" (NO errata) que exigen volver a practicar el ítem: una
# errata dice que el alumno sabe la palabra; `wrong_word` dice que no.
ERROR_PRONE_MIN_WRONG = 2

# Modalidades de PRODUCCIÓN: su ausencia en el ledger es el hueco que cierra la
# actividad `sentence`.
PRODUCTION_SKILLS: tuple[str, ...] = ("written_production", "spoken_production")

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
    """¿La unidad se ha usado con éxito en >= 2 contextos distintos? (V3.40)."""
    return bool((evidence or {}).get("transfer"))


def transfer_gap(evidence: dict | None) -> bool:
    """¿Toca TRANSFERIR la unidad a un contexto nuevo? (V3.40, puro).

    La auditoría de V3.38.1 (P1-03) pidió separar `situation` (recuperación
    contextualizada) de la transferencia real: usar la unidad en un contexto
    DISTINTO del de aprendizaje. `services.evidence.context_signals` aporta los
    contextos con éxito; aquí se decide si es el momento de pedirla.

    Exige, para no adelantarse:
    - que el ledger tenga contexto registrado (`context_attempts > 0`);
    - al menos `TRANSFER_MIN_SUCCESSES` éxitos (un solo uso aún se está
      aprendiendo);
    - éxito en AL MENOS un contexto (hay algo que transferir) y en MENOS de
      `TRANSFER_MIN_SUCCESS_CONTEXTS` (aún no hay transferencia demostrada).

    Sin ventana por contexto (resumen parcial) devuelve `False`: no se inventa.
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


def limiting_skill(signals: dict) -> str:
    """Modalidad con mayor prioridad (argmax) (V3.39, puro).

    Desempate determinista por el orden canónico `LEXICAL_SKILLS` (recall antes
    que producción), de modo que sin evidencia segmentada la decisión cae en
    `recall` —el peldaño por defecto del repaso— y no en un orden accidental de
    diccionario. Devuelve "" si no hay bloque `skills`.
    """
    priorities = skill_priority(signals)
    if not priorities:
        return ""
    candidates = [skill for skill in LEXICAL_SKILLS if skill in priorities]
    candidates.extend(
        skill for skill in priorities if skill not in LEXICAL_SKILLS
    )
    return max(candidates, key=lambda skill: priorities[skill]) if candidates else ""


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


def explain_priority(signals: dict, reason: str = "") -> str:
    """Explicación legible (inglés) de por qué esta tarea es la siguiente.

    Mismo registro que `services.adaptive.explain_priority`: frases cortas
    separadas por `; `, deterministas y en inglés (el contrato `why` del
    proyecto). Nunca lanza.
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
    if not parts:
        parts.append("scheduled maintenance")
    return "; ".join(parts)
