"""Scorer determinista de speaking (rubric CEFR de 7 dimensiones).

Reutiliza los evaluadores deterministas existentes (phonetics, fluency, grammar,
vocabulary) para producir un score por criterio y un overall ponderado. Sigue la
premisa del proyecto: la evidencia la extrae el LLM, pero el score lo calcula SIEMPRE
un scorer determinista (nunca "el LLM te pone B1").

Un criterio puede no ser observable (p. ej. `pronunciation` sin audio o `fluency`
sin duración). En ese caso su `score` es `None`, `observed` es `False` y no entra en
el `overall`, que se recalcula solo sobre los criterios observados (renormalizando
los pesos). Así "desconocido" no se confunde con "50%".
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, computed_field

from services import adaptive
from services.curriculum import RUBRIC_VERSION
from services.fluency import compute_fluency
from services.forgetting import review_due as forgetting_review_due
from services.grammar import find_errors
from services.phonetics import composite_score

# Dimensiones del rubric de speaking (alineadas con CEFR). `interaction` (V1.15)
# captura la capacidad de turn-taking y respuesta conversacional, observable solo
# en el flujo libre (tarea) donde el LLM extrae la evidencia.
SPEAKING_CRITERIA: tuple[str, ...] = (
    "task_achievement",
    "grammatical_control",
    "lexical_resource",
    "fluency",
    "pronunciation",
    "coherence",
    "interaction",
)

# Pesos por defecto (suman 1). El overall es la media ponderada de los criterios
# observados (renormalizada sobre los presentes).
CRITERION_WEIGHTS: dict[str, float] = {
    "task_achievement": 0.20,
    "grammatical_control": 0.20,
    "lexical_resource": 0.20,
    "fluency": 0.15,
    "pronunciation": 0.10,
    "coherence": 0.10,
    "interaction": 0.05,
}

# --- LexicalEvidence 2.0 (V1.16) --------------------------------------------
# El TTR puro depende de la longitud: una muestra muy corta infla la diversidad
# (10 palabras → 9 distintas → TTR 0.9, sin implicar vocabulario B2). Se corrige
# con diversidad normalizada (MSTTR por segmentos) y un factor `range` que exige
# un mínimo de tipos distintos para considerar fiable la muestra.
_LEXICAL_SEGMENT_SIZE = 10
_LEXICAL_MIN_TYPES = 20

# Pesos de las sub-dimensiones de lexical_resource (suman 1). `diversity` (TTR),
# `diversity_normalized` (MSTTR) y `range` son deterministas (del texto oído);
# `lexical_sophistication`, `lexical_precision` y `collocations` las extrae el
# LLM y son opcionales. Cuando no llegan, se renormaliza sobre las señales
# deterministas presentes.
LEXICAL_SUBDIM_WEIGHTS: dict[str, float] = {
    "diversity": 0.25,
    "diversity_normalized": 0.25,
    "range": 0.20,
    "lexical_sophistication": 0.15,
    "lexical_precision": 0.10,
    "collocations": 0.05,
}

# --- Perfil de tarea de speaking (V1.16) ------------------------------------

# Tipos de tarea de speaking reconocidos. Cada uno observa criterios distintos y
# puede tener pesos de rúbrica propios (monólogo vs conversación).
TASK_TYPES: tuple[str, ...] = (
    "read_aloud",
    "monologue",
    "description",
    "story",
    "role_play",
    "conversation",
    "discussion",
    "interview",
    "presentation",
)

# Factores del vector de dificultad de una tarea de speaking. La dificultad escalar
# `difficulty` (1..6) se deriva como la media redondeada del vector (mismo patrón
# que listening), de modo que media↔dificultad se cumple por construcción.
SPEAKING_DIFFICULTY_FACTORS: tuple[str, ...] = (
    "lexical_demand",
    "grammar_demand",
    "discourse_demand",
    "interaction_demand",
    "spontaneity",
    "cognitive_demand",
    "novelty",
)

# Tipos de tarea que observan interacción conversacional (turn-taking real). Son
# los que realizan el factor `interaction_demand` declarado en el vector.
CONVERSATIONAL_TASK_TYPES: frozenset[str] = frozenset(
    {"role_play", "conversation", "discussion", "interview"}
)


def difficulty_from_vector(vector: dict[str, int]) -> int:
    """Deriva el escalar de dificultad (1..6) como la media redondeada del vector.

    Misma regla que `services.listening.difficulty_from_vector`: `round` de Python y
    clamp a [1, 6]. Un vector vacío se trata como dificultad mínima."""
    if not vector:
        return 1
    mean = round(sum(vector.values()) / len(vector))
    return max(1, min(6, mean))


class SpeakingTaskProfile(BaseModel):
    """Perfil declarado de una tarea de speaking (dificultad + tipo + duración).

    `difficulty` es un campo derivado del `difficulty_vector`; cualquier clave
    `difficulty` presente en un dict de entrada queda ignorada por ser redundante.
    `interaction_demand` > 1 solo se realiza en tareas conversacionales
    (`CONVERSATIONAL_TASK_TYPES`)."""

    task_type: str
    cefr_target: str = "B1"
    duration_target: float = 60.0
    difficulty_vector: dict[str, int] = Field(default_factory=dict)

    @computed_field
    @property
    def difficulty(self) -> int:
        return difficulty_from_vector(self.difficulty_vector)


# Pesos de rúbrica por tipo de tarea (suman 1 sobre los criterios que declara).
# `monologue` no observa interacción (peso 0); `conversation` le da 0.20. El perfil
# por defecto `CRITERION_WEIGHTS` sigue valiendo para el flujo read-aloud y como
# fallback cuando no se declara tipo de tarea.
TASK_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "monologue": {
        "task_achievement": 0.20,
        "grammatical_control": 0.20,
        "lexical_resource": 0.20,
        "fluency": 0.20,
        "coherence": 0.15,
        "pronunciation": 0.05,
        "interaction": 0.0,
    },
    "conversation": {
        "task_achievement": 0.15,
        "grammatical_control": 0.15,
        "lexical_resource": 0.15,
        "fluency": 0.15,
        "coherence": 0.10,
        "pronunciation": 0.10,
        "interaction": 0.20,
    },
}


def weights_for_task_type(task_type: str) -> dict[str, float]:
    """Pesos de rúbrica del tipo de tarea, o el perfil por defecto si no hay uno.

    Los tipos conversacionales usan el perfil `conversation` (interaction 20%); el
    resto de tareas productivas usan `monologue`; si el tipo no tiene perfil propio
    ni es conversacional, se conserva `CRITERION_WEIGHTS` (backward-compat)."""
    if task_type in TASK_TYPE_WEIGHTS:
        return TASK_TYPE_WEIGHTS[task_type]
    if task_type in CONVERSATIONAL_TASK_TYPES:
        return TASK_TYPE_WEIGHTS["conversation"]
    return CRITERION_WEIGHTS


def realized_vector(profile: SpeakingTaskProfile) -> dict[str, int]:
    """Vector de dificultad *realmente demandado* por la tarea de speaking.

    Ancla de integridad de evidencia (equivalente a `listening.realized_vector`):
    el vector declarado es lo que la tarea *pretende* exigir; `realized_vector` es
    lo que *exige de verdad*. Los factores lingüísticos se realizan tal como se
    declaran (el texto de la tarea los demanda); `interaction_demand` solo se
    realiza en tareas conversacionales (turn-taking real), y queda en 1 en caso
    contrario (una tarea `monologue` con `interaction_demand > 1` declara
    interacción que en la práctica no se produce).
    """
    declared = profile.difficulty_vector or {}
    realized: dict[str, int] = {}
    for factor in SPEAKING_DIFFICULTY_FACTORS:
        value = int(declared.get(factor, 1))
        if factor == "interaction_demand":
            realized[factor] = (
                value if profile.task_type in CONVERSATIONAL_TASK_TYPES else 1
            )
        else:
            realized[factor] = value
    return realized


def realized_difficulty(profile: SpeakingTaskProfile) -> int:
    """Dificultad escalar derivada del vector *realizado* (no del declarado)."""
    return difficulty_from_vector(realized_vector(profile))


def realization_gap_factors(profile: SpeakingTaskProfile) -> list[str]:
    """Factores donde la tarea exige menos de lo declarado (evidencia debilitada)."""
    declared = profile.difficulty_vector or {}
    realized = realized_vector(profile)
    return [
        factor
        for factor in SPEAKING_DIFFICULTY_FACTORS
        if int(realized.get(factor, 1)) < int(declared.get(factor, 1))
    ]

# Penalizaciones de fluidez por señal de discurso extraída por el LLM (por
# autocorrección, titubeo y repetición): una producción fluida no se autocorrige
# ni titubea en exceso.
_FLUENCY_PENALTY_SELF_CORRECTION = 0.05
_FLUENCY_PENALTY_HESITATION = 0.03
_FLUENCY_PENALTY_REPETITION = 0.03

# --- FluencyEvidence 2.0 (V1.16) --------------------------------------------
# Fluidez ≠ velocidad. `speech_rate` (WPM) se mapea a una banda con meseta en el
# rango apropiado/fluido (90–140 wpm): 90 wpm puede ser perfectamente apropiado
# para B1, y hablar a 170+ wpm puede perjudicar la inteligibilidad. Sobre esa
# banda el scorer resta penalizaciones de discurso y mezcla `smoothness`/`rhythm`
# del LLM cuando están disponibles.
_FLUENCY_BAND_LOW = 30.0
_FLUENCY_BAND_START = 90.0
_FLUENCY_BAND_END = 140.0
_FLUENCY_BAND_TOO_FAST = 200.0
_FLUENCY_TOO_FAST_PENALTY = 0.5

# Pesos de la fluidez compuesta: `speech_rate` (determinista) es la base; las
# señales de discurso (self_corrections/hesitations/repetitions) restan;
# `smoothness` y `rhythm` (LLM, opcionales) afinan. Cuando no hay LLM, la fluidez
# es solo la banda de velocidad menos las penalizaciones de discurso presentes.
FLUENCY_SMOOTHNESS_WEIGHT = 0.15
FLUENCY_RHYTHM_WEIGHT = 0.15

# --- InteractionEvidence 2.0 (V1.16) ----------------------------------------
# `interaction` deja de ser una única estimación subjetiva del LLM: se combina a
# partir de sub-dimensiones conversacionales ponderadas (P1-4). Si el LLM no las
# devuelve, se conserva el fallback `interaction` (backward-compat). La señal
# semántica del LLM (abajo) se complementa ahora con señal OBJETIVA de turnos
# (`services.interaction`): balance, latencia, duración e interrupciones.
INTERACTION_SUBDIM_WEIGHTS: dict[str, float] = {
    "appropriate_responses": 0.30,
    "turn_completion": 0.25,
    "follow_up_questions": 0.20,
    "topic_maintenance": 0.15,
    "clarification_requests": 0.10,
}

# Peso de la señal OBJETIVA (telemetría de turnos) frente a la SEMÁNTICA (LLM) al
# fusionar `interaction` (InteractionEvidence 2.0, señal objetiva). 0.5 → ambas
# fuentes pesan por igual; cuando solo una fuente está presente se usa esa.
INTERACTION_OBJECTIVE_WEIGHT = 0.5

# Pesos de las sub-dimensiones objetivas que entran en la señal objetiva (suman 1).
# `turn_balance` y `turn_completion` son scores [0,1] derivados de la telemetría de
# turnos por `services.interaction.interaction_evidence`. El resto de campos que
# devuelve esa función (avg_response_latency_ms, student_turns, assistant_turns,
# interruptions) son diagnósticos y NO se fusionan en el score.
INTERACTION_OBJECTIVE_SUBDIM_WEIGHTS: dict[str, float] = {
    "turn_balance": 0.5,
    "turn_completion": 0.5,
}

# Pesos de las sub-dimensiones de task_achievement (suman 1). Cuando el LLM las
# devuelve, task_achievement es su combinación ponderada (graduada, P0-1); si no,
# se conserva el fallback binario `task_achieved`.
TASK_SUBDIM_WEIGHTS: dict[str, float] = {
    "task_completion": 0.35,
    "task_relevance": 0.25,
    "task_coverage": 0.25,
    "task_appropriateness": 0.15,
}

# Penalización por severidad de error gramatical (GrammarEvidence 2.0, P0-2).
# Sustituye al "1 - 0.25·errores" plano: un error crítico (destruye significado)
# penaliza mucho más que varios leves, y varios leves no colapsan el score a 0.
_GRAMMAR_PENALTY_MINOR = 0.05
_GRAMMAR_PENALTY_MAJOR = 0.15
_GRAMMAR_PENALTY_CRITICAL = 0.30
# Penalización plana legacy por error (fallback cuando el LLM no devuelve detalle).
_GRAMMAR_LEGACY_PENALTY = 0.25

# Parámetros del diagnóstico longitudinal de speaking (V1.15). Un criterio está
# "débil" si no se ha practicado (attempts == 0) o si su media está por debajo del
# umbral con un mínimo de intentos (evidencia suficiente).
SPEAKING_WEAK_THRESHOLD = 0.6
SPEAKING_TREND_WINDOW = 5

# --- Student Model ownership del diagnóstico (V1.16 S5) ----------------------
# El diagnóstico deja de ser un agregador mean/min/max: cada criterio expone las
# mismas señales que el Student Model (EMA de recent_score y confidence, stability
# y review_due por olvido), de modo que el diagnóstico es una VISTA de esas señales
# y no un cálculo estadístico propio.
SPEAKING_EMA_ALPHA = 0.5
SPEAKING_CONFIDENCE_THRESHOLD = 0.6


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _tokens(text: str) -> list[str]:
    """Tokeniza en minúsculas, sin puntuación, conservando orden y repeticiones.

    No se apoya en vocabulary.extract_words a propósito: aquella devuelve palabras
    únicas ordenadas alfabéticamente y filtra stopwords, lo que anularía la
    semántica "con repetición/orden" de task_achievement. Aquí se conserva el flujo
    completo de tokens para que lexical (set) y task (lista) midan cosas distintas.
    """
    return re.findall(r"[a-z0-9']+", text.lower())


def lexical_diversity(tokens: list[str]) -> float:
    """Diversidad léxica (type-token ratio, TTR): vocabulario distinto / total.

    Sustituye al "conteo de palabras de contenido": mide riqueza léxica real
    (variedad frente a repetición), no solapamiento con un texto esperado. 0.0 si
    no hay tokens.
    """
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / len(tokens), 3)


def _msttr(tokens: list[str], segment_size: int = _LEXICAL_SEGMENT_SIZE) -> float:
    """Diversidad léxica normalizada por longitud (MSTTR: mean segmental TTR).

    El TTR puro depende de la longitud; el MSTTR segmenta la producción en bloques
    de `segment_size` tokens y promedia el TTR de cada bloque (descartando el
    último si queda incompleto), lo que lo hace comparativamente estable ante la
    longitud. Para muestras más cortas que un bloque devuelve el TTR (no hay
    suficiente texto para segmentar). 0.0 si no hay tokens.
    """
    if not tokens:
        return 0.0
    if len(tokens) < segment_size:
        return round(len(set(tokens)) / len(tokens), 3)
    segments = [
        tokens[i : i + segment_size] for i in range(0, len(tokens), segment_size)
    ]
    if len(segments[-1]) < segment_size:
        segments = segments[:-1]
    if not segments:
        return round(len(set(tokens)) / len(tokens), 3)
    ttrs = [len(set(seg)) / len(seg) for seg in segments]
    return round(sum(ttrs) / len(ttrs), 3)


def lexical_evidence(tokens: list[str]) -> dict:
    """LexicalEvidence 2.0 determinista: diversidad + range sobre la producción.

    Devuelve `types` (nº de tipos distintos), `tokens` (total), `diversity` (TTR),
    `diversity_normalized` (MSTTR) y `range` (factor 0..1 de cobertura de un
    mínimo de tipos para considerar la muestra fiable). No depende del LLM.
    """
    types = len(set(tokens))
    total = len(tokens)
    diversity = round(types / total, 3) if total else 0.0
    return {
        "types": types,
        "tokens": total,
        "diversity": diversity,
        "diversity_normalized": _msttr(tokens),
        "range": round(_clamp(types / _LEXICAL_MIN_TYPES), 3),
    }


def _sequence_coherence(heard_tokens: list[str], expected_tokens: list[str]) -> float:
    """Coherencia de secuencia (read-aloud): preservación del orden esperado.

    Mide cuánto de la frase esperada se reproduce en el orden correcto usando la
    subsecuencia común más larga (LCS) normalizada por la longitud esperada. Así
    decir las palabras desordenadas o repetir la frase entera no puntúa como
    coherente (a diferencia del ratio de longitud, que podía "engañarse" con
    cualquier producción de la misma extensión). 1.0 si no hay referencia.
    """
    if not expected_tokens:
        return 1.0
    n, m = len(heard_tokens), len(expected_tokens)
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        for j in range(1, m + 1):
            if heard_tokens[i - 1] == expected_tokens[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    return round(_clamp(prev[m] / len(expected_tokens)), 3)


def _speech_rate_score(wpm: float) -> float:
    """Mapea WPM a una banda de fluidez 0..1 (FluencyEvidence 2.0).

    El rango apropiado/fluido (90–140 wpm) puntúa 1.0; por debajo sube linealmente
    desde 0.2 (30 wpm) hasta 1.0 (90 wpm); por encima de 140 baja gradualmente por
    riesgo de inteligibilidad (hablar demasiado rápido no es más fluido). Fluidez
    ≠ velocidad: 90 wpm es apropiado para B1 aunque no sea "rápido".
    """
    if _FLUENCY_BAND_START <= wpm <= _FLUENCY_BAND_END:
        return 1.0
    if wpm < _FLUENCY_BAND_LOW:
        return 0.2
    if wpm < _FLUENCY_BAND_START:
        span = _FLUENCY_BAND_START - _FLUENCY_BAND_LOW
        return round(0.2 + (wpm - _FLUENCY_BAND_LOW) / span * 0.8, 3)
    span = _FLUENCY_BAND_TOO_FAST - _FLUENCY_BAND_END
    return round(1.0 - (wpm - _FLUENCY_BAND_END) / span * _FLUENCY_TOO_FAST_PENALTY, 3)


def _fluency_score(
    heard: str,
    duration_seconds: float | None,
    evidence: dict | None = None,
) -> float | None:
    """Fluidez compuesta (0..1) separando velocidad de fluidez; `None` sin audio.

    La base es la banda de velocidad (`_speech_rate_score`) sobre el WPM; sobre
    ella se restan las penalizaciones de discurso (self_corrections/hesitations/
    repetitions) y, si el LLM aporta `smoothness`/`rhythm`, se mezclan como señal
    de suavidad/ritmo. Sin LLM, es la banda menos penalizaciones presentes.
    """
    info = compute_fluency(heard, duration_seconds)
    wpm = info["wpm"]
    if wpm is None:
        return None
    rate = _speech_rate_score(wpm)

    if evidence is None:
        return round(rate, 3)

    penalty = (
        _FLUENCY_PENALTY_SELF_CORRECTION * evidence.get("self_corrections", 0)
        + _FLUENCY_PENALTY_HESITATION * evidence.get("hesitations", 0)
        + _FLUENCY_PENALTY_REPETITION * evidence.get("repetitions", 0)
    )
    base = _clamp(rate - penalty)

    smoothness = evidence.get("smoothness")
    rhythm = evidence.get("rhythm")
    if smoothness is None and rhythm is None:
        return round(base, 3)

    # Mezcla de la banda de velocidad con las señales de suavidad/ritmo del LLM.
    total = 1.0
    weighted = base
    if smoothness is not None:
        weighted += FLUENCY_SMOOTHNESS_WEIGHT * float(smoothness)
        total += FLUENCY_SMOOTHNESS_WEIGHT
    if rhythm is not None:
        weighted += FLUENCY_RHYTHM_WEIGHT * float(rhythm)
        total += FLUENCY_RHYTHM_WEIGHT
    return round(_clamp(weighted / total), 3)


def _lexical_score(evidence: dict, heard: str) -> float:
    """lexical_resource (0..1) combinando diversidad determinista + señales LLM.

    La base determinista es la diversidad normalizada (MSTTR) y el factor `range`
    (mínimo de tipos para muestra fiable); si el LLM aporta `lexical_sophistication`,
    `lexical_precision` o `collocations`, se combinan con sus pesos. Renormaliza
    sobre las sub-dimensiones presentes (P1-2: riqueza léxica más allá del TTR).
    """
    le = lexical_evidence(_tokens(heard))
    parts: dict[str, float] = {
        "diversity": le["diversity"],
        "diversity_normalized": le["diversity_normalized"],
        "range": le["range"],
    }
    if evidence.get("lexical_sophistication") is not None:
        parts["lexical_sophistication"] = float(evidence["lexical_sophistication"])
    if evidence.get("lexical_precision") is not None:
        parts["lexical_precision"] = float(evidence["lexical_precision"])
    if evidence.get("collocations") is not None:
        parts["collocations"] = float(evidence["collocations"])
    total_weight = sum(LEXICAL_SUBDIM_WEIGHTS[k] for k in parts)
    weighted = sum(LEXICAL_SUBDIM_WEIGHTS[k] * parts[k] for k in parts)
    return round(_clamp(weighted / total_weight), 3)


def _weighted_overall(
    criteria: dict, observed: dict, weights: dict | None = None
) -> float:
    """Overall = media ponderada de los criterios observados, con pesos
    renormalizados sobre los presentes. 0.0 si ninguno es observable.

    `weights` permite inyectar el perfil de pesos del tipo de tarea; si es None se
    usa `CRITERION_WEIGHTS`. Un criterio ausente del perfil cae al peso por defecto.
    """
    weights = weights if weights is not None else CRITERION_WEIGHTS
    total_weight = 0.0
    weighted_sum = 0.0
    for criterion in SPEAKING_CRITERIA:
        score = criteria.get(criterion)
        if observed.get(criterion, False) and score is not None:
            weight = weights.get(criterion, CRITERION_WEIGHTS[criterion])
            total_weight += weight
            weighted_sum += weight * score
    if total_weight == 0.0:
        return 0.0
    return round(weighted_sum / total_weight, 3)


def score_speaking(
    heard: str,
    expected: str,
    duration_seconds: float | None = None,
) -> dict:
    """Puntúa una producción oral frente a una frase/tarea esperada (read-aloud).

    Devuelve un dict con `heard`, `expected`, `criteria` (dict criterion → score
    0..1, o `None` si el criterio no es observable), `observed` (dict criterion →
    bool) y `overall` (media ponderada sobre los criterios observados).
    """
    heard_tokens = _tokens(heard)
    expected_tokens = _tokens(expected)

    # pronunciation: similitud palabra/fonética con lo esperado (0-100 → 0-1).
    pronunciation = round(composite_score(expected, heard)["score"] / 100, 3)

    # fluency: wpm frente a 120 wpm ≈ fluido; None si no se puede calcular.
    fluency = _fluency_score(heard, duration_seconds)

    # grammatical_control: 0 errores = 1.0; cada error resta 0.25; suelo 0.0.
    grammatical_control = round(
        max(0.0, 1.0 - 0.25 * len(find_errors(heard))), 3
    )

    # lexical_resource: cobertura del léxico esperado (tokens únicos, sin orden).
    # En read-aloud el objetivo es reproducir la frase esperada, así que la
    # cobertura es la señal correcta (no la diversidad).
    if expected_tokens:
        lexical_resource = round(
            _clamp(
                len(set(heard_tokens) & set(expected_tokens))
                / len(set(expected_tokens))
            ),
            3,
        )
    else:
        lexical_resource = 1.0

    # task_achievement: cobertura de tokens clave esperados (con repetición/orden).
    if expected_tokens:
        task_achievement = round(
            _clamp(
                len([t for t in expected_tokens if t in heard_tokens])
                / len(expected_tokens)
            ),
            3,
        )
    else:
        task_achievement = 1.0

    # coherence: preservación del orden de la frase esperada (read-aloud: sin
    # señal discursiva del LLM, la coherencia es "reproducir en el orden correcto").
    coherence = _sequence_coherence(heard_tokens, expected_tokens)

    # interaction: no observable en read-aloud (no hay turno conversacional).
    interaction = None

    criteria = {
        "task_achievement": task_achievement,
        "grammatical_control": grammatical_control,
        "lexical_resource": lexical_resource,
        "fluency": fluency,
        "pronunciation": pronunciation,
        "coherence": coherence,
        "interaction": interaction,
    }
    observed = {
        "task_achievement": True,
        "grammatical_control": True,
        "lexical_resource": True,
        "fluency": fluency is not None,
        "pronunciation": True,
        "coherence": True,
        "interaction": False,
    }

    overall = _weighted_overall(criteria, observed)

    return {
        "heard": heard,
        "expected": expected,
        "criteria": criteria,
        "observed": observed,
        "overall": overall,
    }


def _task_achievement_score(evidence: dict) -> float:
    """task_achievement (0..1) a partir de sub-dimensiones ponderadas si están.

    Si el LLM devolvió al menos una sub-dimensión (completion/relevance/coverage/
    appropriateness), se combina con sus pesos renormalizados sobre las presentes
    (P0-1: logro graduado, no binario). En caso contrario se conserva el fallback
    binario `task_achieved`.
    """
    present = [k for k in TASK_SUBDIM_WEIGHTS if evidence.get(k) is not None]
    if present:
        total_weight = sum(TASK_SUBDIM_WEIGHTS[k] for k in present)
        weighted = sum(TASK_SUBDIM_WEIGHTS[k] * float(evidence[k]) for k in present)
        return round(_clamp(weighted / total_weight), 3)
    return 1.0 if evidence["task_achieved"] else 0.0


def _grammar_score(evidence: dict) -> float:
    """grammatical_control (0..1) con severidad de errores (GrammarEvidence 2.0).

    Si el LLM devuelve `grammar_error_details` (lista de `{type, severity}`), se
    penaliza por severidad (minor < major < critical); si no, se conserva el
    fallback plano `1 - 0.25·grammar_errors`.
    """
    details = evidence.get("grammar_error_details")
    if details:
        minor = sum(1 for d in details if d.get("severity") == "minor")
        major = sum(1 for d in details if d.get("severity") == "major")
        critical = sum(1 for d in details if d.get("severity") == "critical")
        if minor + major + critical > 0:
            penalty = (
                _GRAMMAR_PENALTY_MINOR * minor
                + _GRAMMAR_PENALTY_MAJOR * major
                + _GRAMMAR_PENALTY_CRITICAL * critical
            )
            return round(_clamp(1.0 - penalty), 3)
    return round(_clamp(1.0 - _GRAMMAR_LEGACY_PENALTY * evidence["grammar_errors"]), 3)


def _semantic_interaction_score(evidence: dict) -> float | None:
    """interaction semántica (0..1) a partir de sub-dimensiones del LLM o fallback.

    Si el LLM devolvió al menos una sub-dimensión conversacional (turn_completion/
    follow_up_questions/appropriate_responses/topic_maintenance/clarification_requests),
    se combina con sus pesos renormalizados sobre las presentes (P1-4: señal
    estructurada, no una sola estimación subjetiva). En caso contrario se conserva
    el fallback `interaction`; `None` si tampoco existe (criterio no observado).
    """
    present = [k for k in INTERACTION_SUBDIM_WEIGHTS if evidence.get(k) is not None]
    if present:
        total_weight = sum(INTERACTION_SUBDIM_WEIGHTS[k] for k in present)
        weighted = sum(
            INTERACTION_SUBDIM_WEIGHTS[k] * float(evidence[k]) for k in present
        )
        return round(_clamp(weighted / total_weight), 3)
    interaction = evidence.get("interaction")
    if interaction is None:
        return None
    return round(_clamp(float(interaction)), 3)


def _interaction_objective_score(objective: dict) -> float | None:
    """interaction objetiva (0..1) a partir de sub-dimensiones de telemetría de turnos.

    `objective` es el dict devuelto por `services.interaction.interaction_evidence`.
    Se combinan sus sub-dimensiones en [0,1] (`turn_balance`, `turn_completion`) con
    pesos renormalizados sobre las presentes; `None` si no hay ninguna observable.
    """
    if not isinstance(objective, dict):
        return None
    present = [
        k
        for k in INTERACTION_OBJECTIVE_SUBDIM_WEIGHTS
        if objective.get(k) is not None
    ]
    if not present:
        return None
    total_weight = sum(INTERACTION_OBJECTIVE_SUBDIM_WEIGHTS[k] for k in present)
    weighted = sum(
        INTERACTION_OBJECTIVE_SUBDIM_WEIGHTS[k] * float(objective[k])
        for k in present
    )
    return round(_clamp(weighted / total_weight), 3)


def _interaction_score(evidence: dict) -> float | None:
    """interaction (0..1) fusionando señal objetiva (turnos) y semántica (LLM).

    La señal objetiva (`evidence["interaction_objective"]`, producida por
    `services.interaction.interaction_evidence`) se combina con la semántica del
    LLM mediante `INTERACTION_OBJECTIVE_WEIGHT`. Si solo hay una fuente se usa esa;
    si no hay ninguna, se conserva el fallback legacy `interaction`; `None` si
    tampoco existe (criterio no observado). Backward-compatible: sin
    `interaction_objective` el comportamiento es idéntico al anterior.
    """
    semantic = _semantic_interaction_score(evidence)
    objective = _interaction_objective_score(evidence.get("interaction_objective"))
    if objective is None:
        return semantic
    if semantic is None:
        return objective
    return round(
        _clamp(
            INTERACTION_OBJECTIVE_WEIGHT * objective
            + (1.0 - INTERACTION_OBJECTIVE_WEIGHT) * semantic
        ),
        3,
    )


def scores_from_evidence(
    evidence: dict,
    heard: str,
    duration_seconds: float | None = None,
    task_type: str | None = None,
    expected: str | None = None,
) -> dict:
    """Convierte evidencia extraída por el LLM en los 7 criterios + overall.

    `evidence` es el dict normalizado de `speaking_llm.parse_speaking_evidence`.
    La pronunciación no es evaluable sin una referencia de audio/texto en este
    flujo: queda `None`/no observada salvo que se pase `expected` (referencia de
    lectura), en cuyo caso se calcula con el módulo de fonética determinista.
    `lexical_resource` combina diversidad normalizada y `range` (deterministas)
    con señales léxicas del LLM; la fluidez separa la banda de velocidad de la
    suavidad/ritmo y las penalizaciones de discurso; `interaction` combina sus
    sub-dimensiones conversacionales. El `overall` se calcula solo sobre criterios
    observados, con los pesos del `task_type` (si se declara) o los por defecto.
    Devuelve {"criteria": {...}, "observed": {...}, "overall": float}.
    """
    task_achievement = _task_achievement_score(evidence)
    grammatical_control = _grammar_score(evidence)

    # lexical_resource: riqueza léxica (diversidad normalizada + range + señales
    # semánticas del LLM), no solapamiento con un texto esperado.
    lexical_resource = _lexical_score(evidence, heard)

    coherence = round(_clamp(float(evidence["coherence"])), 3)

    fluency = _fluency_score(heard, duration_seconds, evidence)

    # pronunciation: observable solo con referencia (integración del módulo de
    # pronunciación en el flujo libre, V1.16); sin referencia queda None.
    pronunciation: float | None = None
    if expected:
        pronunciation = round(composite_score(expected, heard)["score"] / 100, 3)

    interaction = _interaction_score(evidence)

    criteria = {
        "task_achievement": task_achievement,
        "grammatical_control": grammatical_control,
        "lexical_resource": lexical_resource,
        "fluency": fluency,
        "pronunciation": pronunciation,
        "coherence": coherence,
        "interaction": interaction,
    }
    observed = {
        "task_achievement": True,
        "grammatical_control": True,
        "lexical_resource": True,
        "fluency": fluency is not None,
        "pronunciation": pronunciation is not None,
        "coherence": True,
        "interaction": interaction is not None,
    }

    overall = _weighted_overall(
        criteria, observed, weights_for_task_type(task_type) if task_type else None
    )

    return {
        "criteria": criteria,
        "observed": observed,
        "overall": overall,
    }


def evidence_from_speaking(
    result: dict,
    *,
    level_id: str,
    objective_id: str,
    curriculum_version: str = "",
    assessment_version: str = RUBRIC_VERSION,
    difficulty: int = 1,
) -> list[dict]:
    """Convierte el resultado de score_speaking en registros de evidencia.

    Una fila por criterio observable del rubric (item_id = criterio) más una fila
    'overall'. Los criterios no observados (score `None`) NO se registran como
    evidencia: "desconocido" no contamina el mastery. Todas con source='speaking',
    item_type='speaking' y `difficulty` (escalar 1..6 derivado del perfil de tarea;
    V1.16). El instrumento de medida es la rúbrica, versionada en
    `assessment_version`."""
    observed = result.get("observed", {c: True for c in SPEAKING_CRITERIA})
    records = []
    for criterion in SPEAKING_CRITERIA:
        score = result["criteria"].get(criterion)
        if score is None or not observed.get(criterion, True):
            continue
        records.append(
            {
                "level_id": level_id,
                "objective_id": objective_id,
                "skill": "speaking",
                "item_id": criterion,
                "item_type": "speaking",
                "difficulty": difficulty,
                "source": "speaking",
                "result": float(score),
                "curriculum_version": curriculum_version,
                "assessment_version": assessment_version,
            }
        )
    records.append(
        {
            "level_id": level_id,
            "objective_id": objective_id,
            "skill": "speaking",
            "item_id": "overall",
            "item_type": "speaking",
            "difficulty": difficulty,
            "source": "speaking",
            "result": float(result["overall"]),
            "curriculum_version": curriculum_version,
            "assessment_version": assessment_version,
        }
    )
    return records


def _mean_trend(rows: list[dict], window: int = SPEAKING_TREND_WINDOW) -> dict:
    """Tendencia de la media de `result` (0..1) de los últimos `window` vs previos.

    Las filas llegan en orden cronológico (id ASC). Devuelve
    `{recent_mean, prior_mean, delta, direction}` con `direction` en
    `{"up", "down", "flat", "n/a"}`. Adapta `listening.recent_trend` (que trabaja
    sobre `correct`) a medias de scores continuos.
    """
    if not rows:
        return {
            "recent_mean": None,
            "prior_mean": None,
            "delta": None,
            "direction": "n/a",
        }

    def _mean(subset: list[dict]) -> float:
        return round(sum(r["result"] for r in subset) / len(subset), 3)

    if len(rows) <= window:
        return {
            "recent_mean": _mean(rows),
            "prior_mean": None,
            "delta": None,
            "direction": "n/a",
        }
    recent = _mean(rows[-window:])
    prior = _mean(rows[:-window])
    delta = round(recent - prior, 3)
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "recent_mean": recent,
        "prior_mean": prior,
        "delta": delta,
        "direction": direction,
    }


def _ema(values: list[float], alpha: float = SPEAKING_EMA_ALPHA) -> float:
    """EMA de una secuencia cronológica de valores (0..1); 0.0 si está vacía.

    Refleja el rendimiento *reciente* (más peso a lo último), frente a la media
    aritmética que pondera toda la historia por igual (misma idea que
    `next_mastery_state`).
    """
    if not values:
        return 0.0
    recent = float(values[0])
    for value in values[1:]:
        recent = alpha * float(value) + (1 - alpha) * recent
    return round(recent, 3)


def speaking_diagnostic(evidence_rows: list[dict], now: str = "") -> dict:
    """Vista longitudinal de speaking por criterio (Student Model ownership, V1.16).

    `evidence_rows` son las filas de `academy_evidence` con `skill="speaking"`
    (cada fila tiene `item_id` = criterio del rubric y `result` = score 0..1, más
    una fila `item_id="overall"` por intento). En lugar de un agregador mean/min/max
    propio, cada criterio expone las señales del Student Model:
    - `recent_score`: EMA del rendimiento (estado reciente, no toda la historia).
    - `lifetime_score`/`mean`: media de todo el historial.
    - `confidence`: EMA de "supera el umbral" (consistencia).
    - `stability`: dominio × retención (curva de olvido) vía `adaptive.skill_stability`.
    - `review_due`: olvido vencido, fallo reciente o confianza baja (no solo
      `mean < 0.6` con `attempts >= 3`).

    `now` (ISO) permite testear el olvido sin reloj de pared; vacío = sin decaimiento.
    Devuelve `criteria`, `weak`, `recommendation`, `attempts`, `overall_mean`,
    `overall_recent`, `trend` y `rubric_version`. Determinista, sin LLM ni red.
    """
    groups: dict[str, list[dict]] = {}
    overall_rows: list[dict] = []
    for row in evidence_rows:
        item_id = row.get("item_id") or ""
        if item_id == "overall":
            overall_rows.append(row)
            continue
        groups.setdefault(item_id, []).append(row)

    def _criterion(name: str, rows: list[dict]) -> dict:
        attempts = len(rows)
        results = [float(r["result"]) for r in rows if r.get("result") is not None]
        if not results:
            return {
                "criterion": name,
                "attempts": attempts,
                "mean": None,
                "recent_score": None,
                "lifetime_score": None,
                "confidence": None,
                "stability": None,
                "min": None,
                "max": None,
                "review_due": True,
            }
        mean = round(sum(results) / len(results), 3)
        recent = _ema(results)
        confidence = _ema(
            [1.0 if r >= SPEAKING_WEAK_THRESHOLD else 0.0 for r in results]
        )
        last_seen = max(
            r.get("created_at", "") for r in rows if r.get("result") is not None
        )
        review_due = (
            forgetting_review_due(recent, last_seen, now)
            or results[-1] < SPEAKING_WEAK_THRESHOLD
            or confidence < SPEAKING_CONFIDENCE_THRESHOLD
        )
        stability = adaptive.skill_stability(recent, confidence, last_seen, now)
        return {
            "criterion": name,
            "attempts": attempts,
            "mean": mean,
            "recent_score": recent,
            "lifetime_score": mean,
            "confidence": confidence,
            "stability": stability,
            "min": round(min(results), 3),
            "max": round(max(results), 3),
            "review_due": review_due,
        }

    criteria = [_criterion(c, groups.get(c, [])) for c in SPEAKING_CRITERIA]
    known = set(SPEAKING_CRITERIA)
    for name in sorted(set(groups) - known):
        criteria.append(_criterion(name, groups[name]))

    def _weak_key(name: str) -> tuple:
        entry = next(c for c in criteria if c["criterion"] == name)
        recent = entry["recent_score"]
        return (recent is None, recent if recent is not None else 0.0)

    weak = [c["criterion"] for c in criteria if c["review_due"]]
    weak.sort(key=_weak_key)

    recommendation = (
        "All speaking criteria look strong."
        if not weak
        else "Focus on: " + ", ".join(weak)
    )

    overall_results = [
        float(r["result"]) for r in overall_rows if r.get("result") is not None
    ]
    overall_mean = (
        round(sum(overall_results) / len(overall_results), 3)
        if overall_results
        else None
    )

    return {
        "criteria": criteria,
        "weak": weak,
        "recommendation": recommendation,
        "attempts": len(overall_rows),
        "overall_mean": overall_mean,
        "overall_recent": _ema(overall_results) if overall_results else None,
        "trend": _mean_trend(overall_rows),
        "rubric_version": RUBRIC_VERSION,
    }


def speaking_level(evidence_rows: list[dict], now: str = "") -> dict:
    """Speaking Assessment 1.0: nivel CEFR continuo + confianza (determinista).

    Agrega la evidencia de speaking (`item_id="overall"`, una fila por intento) en
    un `score` reciente (EMA), una `confidence` (EMA de "supera el umbral") y lo
    proyecta a la escala continua A1=1.0 … C2=6.0 → `{level, numeric}`. Produce la
    afirmación trazable "B1 · confidence 82%" a partir de evidencia versionada, sin
    LLM ni red. Sin evidencia → `level`/`numeric`/`score` None y confidence 0.0.

    `now` se acepta por simetría con `speaking_diagnostic`/`speaking_journey`
    (el nivel agregado no decae con el tiempo; la estabilidad por criterio ya lo
    refleja en el diagnóstico).
    """
    overall_rows = [r for r in evidence_rows if r.get("item_id") == "overall"]
    results = [
        float(r["result"]) for r in overall_rows if r.get("result") is not None
    ]
    if not results:
        return {
            "level": None,
            "numeric": None,
            "score": None,
            "confidence": 0.0,
            "attempts": 0,
        }
    score = _ema(results)
    confidence = _ema(
        [1.0 if r >= SPEAKING_WEAK_THRESHOLD else 0.0 for r in results]
    )
    numeric = round(1.0 + 5.0 * score, 2)
    return {
        "level": adaptive.numeric_to_level(numeric),
        "numeric": numeric,
        "score": score,
        "confidence": round(confidence, 3),
        "attempts": len(overall_rows),
    }


def speaking_journey(evidence_rows: list[dict], now: str = "") -> dict:
    """Speaking Journey (CEFR): trayectoria de nivel y confianza (V1.16 S6).

    Proyecta la evidencia de speaking (`item_id="overall"`, en orden cronológico)
    en una secuencia de snapshots acumulados (`numeric`, `level`, `confidence`),
    más el estado actual. Conecta el diagnóstico con el CEFR Journey: "A2.7 →
    B1.1 → B1.3" y "Confidence 72% → 79% → 86%". Determinista y sin LLM ni red.

    Devuelve `{current_level, current_numeric, current_confidence, attempts,
    steps}` con `steps` ordenados cronológicamente.
    """
    overall_rows = [r for r in evidence_rows if r.get("item_id") == "overall"]
    steps: list[dict] = []
    results_so_far: list[float] = []
    for row in overall_rows:
        if row.get("result") is None:
            continue
        results_so_far.append(float(row["result"]))
        score = _ema(results_so_far)
        confidence = _ema(
            [1.0 if r >= SPEAKING_WEAK_THRESHOLD else 0.0 for r in results_so_far]
        )
        numeric = round(1.0 + 5.0 * score, 2)
        steps.append(
            {
                "at": row.get("created_at", ""),
                "numeric": numeric,
                "level": adaptive.numeric_to_level(numeric),
                "confidence": round(confidence, 3),
            }
        )
    current = speaking_level(evidence_rows, now)
    return {
        "current_level": current["level"],
        "current_numeric": current["numeric"],
        "current_confidence": current["confidence"],
        "attempts": len(overall_rows),
        "steps": steps,
    }
