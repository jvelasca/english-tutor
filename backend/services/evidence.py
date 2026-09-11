"""Modelo de evidencia LONGITUDINAL (V3.35, Longitudinal Learning Evidence 1.0).

El motor de recall de V3.34 sabía responder "¿puede el alumno recuperar una
palabra?", pero medía la retención con repeticiones ancladas a la PRIMERA
exposición. Eso confunde volumen con historia: cuatro aciertos seguidos en días
consecutivos parecían cuatro recuperaciones demoradas cuando el intervalo real
era de un día entre ellos.

Este módulo puro (sin I/O ni FastAPI) define la capa que faltaba:

    evento_1 → intervalo_1 → evento_2 → intervalo_2 → evento_3 → ...

Cada intento es un EVENTO con su propio intervalo (`interval_since_last_evidence`)
y su propio rol (`event_role`). Con eso:

- los INTENTOS se separan de los ÉXITOS (`attempts` vs `successes`): un fallo es
  evidencia (negativa) y no un evento inexistente;
- los ÉXITOS se separan de los DÍAS distintos (`distinct_success_days`): acertar
  dos veces el mismo día no duplica la evidencia temporal;
- los INTERVALOS se conservan (`intervals`): la historia fina que el scheduler
  necesita para programar el siguiente repaso.

`event_role` evita que `learning_events` siga mezclando señales heterogéneas:
una pregunta de Recognition (informativa, no demuestra destrezas productivas) no
es lo mismo que una recuperación de Recall (evidencia) ni que un log de
telemetría.

Puro y determinista: recibe filas ya agregadas o construidas por el repositorio.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from services import transfer

# Roles del ledger de eventos (V3.35). `evidence` = señal que puede acreditar
# aprendizaje; `informative` = señal que informa pero no acredita (p. ej. el MCQ
# de Recognition, V3.13); `telemetry` = traza operativa sin valor pedagógico.
EVIDENCE_ROLES: tuple[str, ...] = ("evidence", "telemetry", "informative")

# Resultados de un intento de micro-drill. `unclear` no es ni acierto ni fallo:
# el ASR no reconoció el audio (V3.21, V20-14/V20-15), así que no se penaliza.
_DRILL_OUTCOMES = frozenset({"ok", "ko", "unclear"})

# Campos de una fila de `learning_evidence` (documentación del contrato).
EVIDENCE_FIELDS: tuple[str, ...] = (
    "occurred_at",
    "skill",
    "target_type",
    "target_id",
    "surface_form",
    "lexical_unit",
    "task",
    "activity",
    "activity_id",
    "context_id",
    "success",
    "support_level",
    "difficulty",
    "response_time_ms",
    "error_type",
    "interval_since_last_evidence",
    "event_role",
)

# V3.36 (Learning Evidence 2.0): niveles de apoyo del ledger léxico. Son los
# MISMOS valores canónicos que `services.academy.SUPPORT_LEVELS` (eje
# `copied → guided → cued → independent → spontaneous`); se declaran aquí para
# que esta capa pura no dependa del servicio de academia (que sí toca BD). Un
# test de paridad garantiza que ambas listas no divergen.
EVIDENCE_SUPPORT_LEVELS: tuple[str, ...] = (
    "copied",
    "guided",
    "cued",
    "independent",
    "spontaneous",
)

# Niveles que representan logro atribuible al alumno sin apoyo externo: la
# evidencia lograda con ellos es la que puede pesar en el modelo de
# automaticidad (V3.36/V3.37). `cued`/`guided`/`copied` cuentan como evidencia,
# pero con apoyo declarado.
INDEPENDENT_SUPPORT_LEVELS: frozenset[str] = frozenset(
    {"independent", "spontaneous"}
)

# V3.37 (cues graduados): umbral de AUTOMATICIDAD. Un ítem es `automatic` cuando
# acumula >= este nº de éxitos SIN apoyo en DÍAS NATURALES DISTINTOS. Una
# producción del día no consolida (D5/E3) y un acierto suelto tampoco: la
# automaticidad exige éxito independiente y ESPACIADO. Declarado y calibrable.
#
# V3.38.1 (P1-04 de la auditoría de V3.38.0): el volumen + espaciado era una
# definición DEMASIADO DÉBIL — 100 intentos con 98 fallos y 2 aciertos sueltos
# en 2 días declaraban automaticidad. Se añaden dos condiciones declaradas y
# calibrables: una RATIO mínima de éxito y la ausencia de fallo "grave"
# (`wrong_word`, confusión real y no errata). Se aplican por igual a la
# automaticidad GLOBAL (`is_automatic`) y a la segmentada por modalidad
# (`automatic_skills`).
AUTOMATIC_MIN_INDEPENDENT = 3

# V3.38.1: ratio mínima de éxito para declarar automaticidad. Se mide sobre el
# `success_rate` global (item) o sobre `skill_successes`/`skill_attempts`
# (modalidad). Un ítem que acierta casi siempre pero falla en la mayoría de
# intentos no es automático por mucha racha que acumule.
AUTOMATIC_MIN_SUCCESS_RATIO = 0.80

# V3.38.1: nº máximo de fallos `wrong_word` (confusión real) tolerados para
# declarar automaticidad. Aproximación determinista a "sin fallo reciente
# grave": hoy el resumen no pondera recencia (deuda de V3.39); `> 1` (2 o más)
# bloquea. Una errata (`orthographic_error`) no cuenta: no es confusión.
AUTOMATIC_MAX_WRONG_WORD_ERRORS = 1

# V3.38 (P1-03 de la auditoría de V3.37.0): MODALIDAD del aprendizaje léxico.
# La automaticidad de V3.37 era GLOBAL — por ítem —, así que dos éxitos
# independientes podían venir de modalidades distintas (uno escrito y otro oral)
# y el ítem se declaraba `automatic` sin que NINGUNA modalidad concreta lo
# fuera: una palabra escrita bien dos días no demuestra automaticidad oral ni
# viceversa. V3.38 segmenta el ledger por la modalidad en la que se demostró el
# logro, con este vocabulario declarado:
#
#   recall              recuperar la forma desde su significado (drill:recall:*)
#   written_production  producirla escribiendo (canal writing)
#   spoken_production   producirla hablando (speaking, conversation, drill:word,
#                       drill:sentence: el alumno la dice tras un modelo)
#   spontaneous_use     usarla sin guion (chat libre)
#
# NO incluye `receptive`: el MCQ de Recognition es INFORMATIVO (V3.13) y no
# escribe evidencia longitudinal, así que hoy no existe modalidad receptiva en
# el ledger; cuando esa señal exista se añadirá aquí (aditivo).
LEXICAL_SKILLS: tuple[str, ...] = (
    "recall",
    "written_production",
    "spoken_production",
    "spontaneous_use",
)

# Modalidad que declara cada canal de PRODUCCIÓN (`context_id="lexicon:<canal>"`).
# El canal concreto NO se pierde — sigue en `context_id`/`activity_id` —, pero
# `skill` declara la modalidad para poder segmentar la automaticidad.
PRODUCTION_CHANNEL_SKILL: dict[str, str] = {
    "chat": "spontaneous_use",
    "conversation": "spoken_production",
    "speaking": "spoken_production",
    "writing": "written_production",
}

# Modalidad de la recuperación por texto (escalera de recall) y de los peldaños
# de micro-drill que se dicen en voz alta (palabra y frase).
RECALL_SKILL = "recall"
DRILL_SKILL = "spoken_production"


def production_skill(channel: str) -> str:
    """Modalidad declarada de un canal de producción ("" si no está declarado)."""
    return PRODUCTION_CHANNEL_SKILL.get((channel or "").strip().lower(), "")


# V3.37: vocabulario del peldaño servido en un intento de recall
# (`activity_id = "drill:recall:<peldaño>"`). El dominio lo ESCRIBE y el
# servicio puro lo LEE para decidir el siguiente peldaño, de modo que el ledger
# y la decisión compartan un único vocabulario y no puedan divergir.
# Un `activity_id` legacy (`drill:recall`, sin peldaño) no declara rung.
RECALL_RUNG_EVIDENCE = "drill:recall:"


def recall_rung_activity(rung: str) -> str:
    """`activity_id` con el que el ledger declara el peldaño servido (V3.37)."""
    return f"{RECALL_RUNG_EVIDENCE}{rung}"


def recall_rung_from_activity(activity_id: str) -> str:
    """Peldaño declarado por un `activity_id` de recall ("" si no lo declara).

    Solo reconoce la forma V3.37 `drill:recall:<peldaño>`; el `activity_id`
    legacy de V3.36 (`drill:recall`) devuelve "" porque no declara apoyo.
    """
    text = (activity_id or "").strip()
    if not text.startswith(RECALL_RUNG_EVIDENCE):
        return ""
    return text[len(RECALL_RUNG_EVIDENCE):]

# V3.36: taxonomía del error de Recall. `correct` está incluido para que el
# histograma de `error_types` sea completo (una entrada por evento clasificado).
# OBSERVACIONAL: clasificar NO cambia el scoring (`correct` del payload sigue
# siendo igualdad estricta de superficie), ni la evidencia, ni FSRS.
RECALL_ERROR_TYPES: tuple[str, ...] = (
    "correct",
    "empty",
    "wrong_word",
    "orthographic_error",
    "partial",
    "multiple_word_error",
)

# V3.39 (Fase 3, actividad de escritura): taxonomía del intento de la actividad
# `write`. Paralela a `RECALL_ERROR_TYPES` y también OBSERVACIONAL: distingue
# "no usó la palabra objetivo" (`missing_target`, hueco real de producción) de
# "frase demasiado corta para ser producción propia" (`too_short`), sin cambiar
# la puntuación.
WRITE_ERROR_TYPES: tuple[str, ...] = (
    "correct",
    "empty",
    "missing_target",
    "too_short",
)

# V3.43 (Transfer 2.0, P1-02): la transferencia separa el TRANSFER LÉXICO (la
# unidad quedó alineada, `passed`) de la ADECUACIÓN SEMÁNTICA del uso.
# `semantic_mismatch` es la señal OBSERVACIONAL de "la unidad se usó en una
# función incompatible con su categoría gramatical declarada" (p. ej. un
# sustantivo conjugado como verbo: `I bank yesterday`). NO cambia el scoring
# léxico (`passed` sigue siendo el resultado léxico); clasifica el intento para
# que el estado de transferencia no lo cuente como ÉXITO LIMPIO.
#
# V3.44 (P1-02 de la auditoría de V3.43.0): se separa «incorrecto» de
# «sospechoso». `semantic_mismatch` es ahora el veredicto FUERTE (adecuación
# `incorrect`, contradicción con TODAS las familias POS y pista fuerte) y es el
# ÚNICO que bloquea el clean success; `semantic_doubt` es el veredicto DÉBIL
# (adecuación `suspect`): advierte y reduce confianza, pero NO destruye la
# evidencia léxica.
SEMANTIC_MISMATCH_ERROR = "semantic_mismatch"
SEMANTIC_DOUBT_ERROR = "semantic_doubt"
TRANSFER_ERROR_TYPES: tuple[str, ...] = (
    "correct",
    "empty",
    "missing_target",
    "too_short",
    SEMANTIC_MISMATCH_ERROR,
    SEMANTIC_DOUBT_ERROR,
)

# Longitud mínima de la forma esperada para admitir `orthographic_error`. Por
# debajo, una diferencia de un carácter suele ser OTRA palabra (cat/cut, sun/son)
# y no una errata: mejor no excusarla (clasificación conservadora).
_ORTHOGRAPHIC_MIN_LENGTH = 4


def _truthy(value: object) -> bool:
    """Normaliza un booleano que puede llegar como int de SQLite."""
    if isinstance(value, str):
        return value not in ("", "0", "False", "false")
    return bool(value)


def _parse_iso(value: str) -> datetime | None:
    """`datetime` UTC de una marca ISO-8601 (None si vacía o inválida)."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def interval_days(previous_at: str, now: str) -> float | None:
    """Días transcurridos entre dos marcas ISO (None si falta alguna).

    Es el `interval_since_last_evidence` de un evento: el hueco REAL desde la
    EVIDENCIA anterior del mismo ítem (`learning_evidence → learning_evidence`),
    no desde la primera exposición ni desde el ancla de retención FSRS (V3.35.1,
    P1-01). Sin evidencia previa no hay intervalo (None), y esa ausencia es
    información: es la primera observación de la cadena longitudinal.
    """
    previous = _parse_iso(previous_at)
    current = _parse_iso(now)
    if previous is None or current is None:
        return None
    return round(max(0.0, (current - previous).total_seconds() / 86400.0), 4)


# ---------------------------------------------------------------------------
# V3.39 (Fase 3C, robustez de señales): RECENCIA y DISTRIBUCIÓN de latencia.
#
# El resumen de V3.38 medía todo el histórico: un `wrong_word` de hace cuarenta
# repasos bloqueaba la automaticidad igual que uno de ayer, y la latencia era
# una media única que ocultaba la cola lenta (un p90 de 15 s con mediana de 3 s
# es un problema de fluidez que la media no muestra). Estas señales se calculan
# con funciones PURAS reutilizadas por la capa SQL (`repositories.
# evidence.summarize_by_target`), de modo que no exista un segundo dialecto.
# ---------------------------------------------------------------------------

# Nº de eventos más recientes que forman la VENTANA de recencia. Declarado y
# calibrable: no es una ventana temporal (el alumno puede pasar semanas sin
# practicar y su último repaso sigue siendo "reciente" en su propia cadena).
RECENT_WINDOW_EVENTS = 10

# V3.40 (Fase 4, transferencia contextual real): nº mínimo de contextos
# DISTINTOS con al menos un éxito para declarar transferencia contextual. Un
# éxito no acredita transferencia: usarla bien en el mismo contexto de siempre
# es recuperación contextualizada, no transferencia (auditoría de V3.38.1).
CONTEXT_TRANSFER_MIN = 2


def _row_sort_key(row: dict) -> tuple[str, int]:
    """Clave de orden cronológico de una fila del ledger (pura).

    Por `(occurred_at, id)` y en TEXTO la fecha (las marcas ISO de la aplicación
    ordenan lexicográficamente); el id se normaliza a entero (0 si falta o no es
    numérico), de modo que dos eventos del mismo instante se desempatan por
    orden de inserción y nunca mezclando int y str.
    """
    try:
        ident = int(row.get("id") or 0)
    except (TypeError, ValueError):
        ident = 0
    return (str(row.get("occurred_at") or ""), ident)


def recent_events(
    rows: list[dict], limit: int = RECENT_WINDOW_EVENTS
) -> list[dict]:
    """Últimos `limit` eventos del ítem, en orden cronológico (V3.39, pura).

    Ordena una COPIA por `(occurred_at, id)`: nunca muta ni reordena la lista
    del llamador (el orden de las filas recibidas sigue siendo el contrato de
    `intervals`). Determinista ante empates y ante filas sin fecha.
    """
    if limit <= 0:
        return []
    ordered = sorted(rows, key=_row_sort_key)
    return ordered[-limit:]


def _percentile(ordered_values: list[float], pct: float) -> float | None:
    """Percentil por RANGO MÁS CERCANO sobre valores YA ordenados (pura).

    `pct` en 0..100. Es la definición que puede replicar SQL sin interpolación
    (nearest-rank): `None` sin valores. Nunca lanza.
    """
    if not ordered_values:
        return None
    if pct <= 0:
        return ordered_values[0]
    if pct >= 100:
        return ordered_values[-1]
    rank = max(1, math.ceil(pct / 100.0 * len(ordered_values)))
    return ordered_values[min(rank, len(ordered_values)) - 1]


def _mean(values: list[float]) -> float | None:
    """Media redondeada a 1 decimal (None sin valores)."""
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _latency_of(row: dict) -> float | None:
    """Latencia medida de una fila (None si no se midió o no es numérica)."""
    raw = row.get("response_time_ms")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def recency_signals(
    rows: list[dict], window: int = RECENT_WINDOW_EVENTS
) -> dict:
    """Señales de RECENCIA y DISTRIBUCIÓN de latencia (V3.39, pura).

    Devuelve, sobre la ventana de los `window` eventos MÁS RECIENTES y sobre el
    histórico de latencias:

    - `recent_attempts` / `recent_error_rate` — intentos y tasa de fallo de la
      ventana: distingue "le cuesta AHORA" de "le costaba";
    - `recent_wrong_word` — confusión real (`wrong_word`) DENTRO de la ventana:
      lo que `_has_grave_error` consulta para no bloquear la automaticidad con
      un fallo ya corregido;
    - `median_response_time_ms` / `p75_response_time_ms` /
      `p90_response_time_ms` — distribución de la latencia medida (la media
      sola oculta la cola lenta);
    - `recent_response_time_ms` — media de la latencia medida en la ventana;
    - `latency_trend` — `recent - histórico anterior` (positivo = se está
      volviendo MÁS lento): la dirección de la fluidez, no solo su nivel.

    Reutilizada tal cual por el resumen SQL (paridad por construcción). Nunca
    lanza: filas incompletas se ignoran donde corresponda.
    """
    ordered_rows = sorted(rows, key=_row_sort_key)
    if window > 0:
        recent = ordered_rows[-window:]
        older = ordered_rows[:-window]
    else:
        recent, older = [], ordered_rows
    measured = [
        value for value in (_latency_of(row) for row in rows) if value is not None
    ]
    ordered = sorted(measured)
    recent_latencies = [
        value for value in (_latency_of(row) for row in recent) if value is not None
    ]
    older_latencies = [
        value for value in (_latency_of(row) for row in older) if value is not None
    ]
    recent_mean = _mean(recent_latencies)
    older_mean = _mean(older_latencies)
    recent_attempts = len(recent)
    recent_failures = sum(1 for row in recent if not _truthy(row.get("success")))
    recent_wrong_word = sum(
        1
        for row in recent
        if (row.get("error_type") or "").strip().lower() == "wrong_word"
    )
    return {
        "recent_attempts": recent_attempts,
        "recent_error_rate": (
            round(recent_failures / recent_attempts, 4) if recent_attempts else 0.0
        ),
        "recent_wrong_word": recent_wrong_word,
        "median_response_time_ms": _percentile(ordered, 50),
        "p75_response_time_ms": _percentile(ordered, 75),
        "p90_response_time_ms": _percentile(ordered, 90),
        "recent_response_time_ms": recent_mean,
        "latency_trend": (
            round(recent_mean - older_mean, 1)
            if recent_mean is not None and older_mean is not None
            else None
        ),
    }


def context_signals(rows: list[dict]) -> dict:
    """Señales de TRANSFERENCIA por CONTEXTO (V3.40 → V3.46, pura).

    La auditoría de V3.38.1 recordó que `situation` (completar un hueco) es
    recuperación CONTEXTUALIZADA, no transferencia: transferir es usar la unidad
    en un contexto DISTINTO del de aprendizaje. Estas señales agrupan el ledger
    por `context_id` para poder demostrarlo y para que el planner tenga una
    tarea de transferencia que proponer.

    Devuelve:

    - `contexts` — `{context_id: {attempts, successes}}` de los contextos
      registrados (las filas sin `context_id` se ignoran: no son contexto);
    - `context_attempts` — nº de contextos distintos con algún intento;
    - `success_contexts` — contextos con al menos un ÉXITO (orden estable);
    - `home_context` — contexto con más intentos (desempate alfabético): el
      contexto "de casa" del ítem; `""` si no hay contextos;
    - `clean_contexts` / `clean_successes` / `clean_success_contexts` /
      `clean_success_days` (V3.43, P1-03): el ÉXITO LIMPIO excluye los intentos
      clasificados `semantic_mismatch` (la unidad quedó alineada pero se usó en
      una función incompatible con su POS). Solo los éxitos limpios avanzan la
      transferencia;
    - `context_diversity` (V3.43, P1-03): diversidad contextual REAL de los
      contextos con éxito limpio (`transfer.context_diversity`). V3.48 añade su
      clave informativa `variety` (no entra en el gate);
    - `transfer` — `True` si hay éxito LIMPIO en >= `CONTEXT_TRANSFER_MIN`
      contextos distintos **y** diversidad contextual real
      (`diverse_dimensions >= CONTEXT_DIVERSITY_MIN`). Antes bastaba con dos
      `context_id` distintos, que podían ser el mismo tipo de producción.
    - `transfer_conditions` / `success_conditions` /
      `unscaffolded_clean_successes` (V3.46, P1-03): la CONDICIÓN de recuperación
      de cada intento (`services.transfer`). `transfer_conditions` es
      `{condición: {attempts, clean_successes}}` solo de los intentos con
      condición DECLARADA (las filas legacy sin condición no aparecen: no se
      puede afirmar de qué condición eran); `success_conditions` son las
      condiciones con >= 1 éxito limpio, en orden de andamiaje decreciente; y
      `unscaffolded_clean_successes` cuenta los éxitos limpios en condiciones NO
      andamiadas — lo que `transfer_state` exige para declarar transferencia
      demostrada.
    - `unscaffolded_clean_success_contexts` / `unscaffolded_clean_success_days`
      (V3.47): contextos y días distintos con éxito limpio NO andamiado, la
      evidencia fina que la escalera endurecida exige (>= 2 éxitos no
      andamiados para `transfer_demonstrated`).
    - `clean_success_goals` (V3.47): objetivos comunicativos distintos de los
      contextos con éxito limpio, derivados del banco (`communicative_goal`).
    - `last_clean_success_at` / `last_unscaffolded_clean_success_at` (V3.47):
      marca ISO del éxito limpio (y no andamiado) más reciente, para
      explicabilidad. La decisión de `transfer_state` NO usa reloj: solo la
      evidencia registrada.

    Reutilizada tal cual por el resumen SQL (paridad por construcción). Nunca
    lanza: filas incompletas se ignoran donde corresponda.
    """
    buckets: dict[str, dict[str, int]] = {}
    clean_successes: dict[str, int] = {}
    clean_days: set[str] = set()
    condition_attempts: dict[str, int] = {}
    condition_clean: dict[str, int] = {}
    # V3.47: evidencia fina de la escalera endurecida (contextos/días/timestamps
    # de los éxitos limpios NO andamiados).
    unscaffolded_contexts: set[str] = set()
    unscaffolded_days: set[str] = set()
    clean_timestamps: list[str] = []
    unscaffolded_timestamps: list[str] = []
    for row in rows:
        context = (row.get("context_id") or "").strip()
        condition = transfer.normalize_condition(row.get("transfer_condition"))
        if condition:
            condition_attempts[condition] = condition_attempts.get(condition, 0) + 1
        if not context:
            continue
        success = _truthy(row.get("success"))
        bucket = buckets.setdefault(context, {"attempts": 0, "successes": 0})
        bucket["attempts"] += 1
        if not success:
            continue
        bucket["successes"] += 1
        if (row.get("error_type") or "").strip().lower() == SEMANTIC_MISMATCH_ERROR:
            # Éxito léxico con uso semánticamente INCORRECTO: cuenta como
            # intento y como éxito léxico, pero NO como éxito limpio.
            # V3.44: `semantic_doubt` (adecuación `suspect`) es advisory y SÍ
            # cuenta como limpio: no destruye evidencia léxica.
            continue
        clean_successes[context] = clean_successes.get(context, 0) + 1
        at = (row.get("occurred_at") or "").strip()
        day = at[:10]
        if day:
            clean_days.add(day)
        if at:
            clean_timestamps.append(at)
        if condition:
            condition_clean[condition] = condition_clean.get(condition, 0) + 1
            if transfer.is_unscaffolded(condition):
                # V3.47: éxito limpio SIN andamiaje. Es lo que la escalera
                # endurecida exige (>= 2) para declarar transferencia.
                unscaffolded_contexts.add(context)
                if day:
                    unscaffolded_days.add(day)
                if at:
                    unscaffolded_timestamps.append(at)
    success_contexts = sorted(
        context for context, bucket in buckets.items() if bucket["successes"] > 0
    )
    clean_success_contexts = sorted(clean_successes)
    diversity = transfer.context_diversity(clean_success_contexts)
    home_context = ""
    if buckets:
        home_context = min(
            buckets,
            key=lambda context: (-buckets[context]["attempts"], context),
        )
    return {
        "contexts": {context: dict(buckets[context]) for context in sorted(buckets)},
        "context_attempts": len(buckets),
        "success_contexts": success_contexts,
        "home_context": home_context,
        "clean_contexts": {
            context: {"successes": clean_successes[context]}
            for context in clean_success_contexts
        },
        "clean_successes": sum(clean_successes.values()),
        "clean_success_contexts": clean_success_contexts,
        "clean_success_days": len(clean_days),
        "context_diversity": diversity,
        "transfer": (
            len(clean_success_contexts) >= CONTEXT_TRANSFER_MIN
            and diversity["diverse_dimensions"] >= transfer.CONTEXT_DIVERSITY_MIN
        ),
        # V3.46: condición de recuperación (solo intentos con condición declarada).
        "transfer_conditions": {
            condition: {
                "attempts": condition_attempts.get(condition, 0),
                "clean_successes": condition_clean.get(condition, 0),
            }
            for condition in transfer.TRANSFER_CONDITIONS
            if condition_attempts.get(condition, 0) or condition_clean.get(condition, 0)
        },
        "success_conditions": [
            condition
            for condition in transfer.TRANSFER_CONDITIONS
            if condition_clean.get(condition, 0) > 0
        ],
        "unscaffolded_clean_successes": sum(
            condition_clean.get(condition, 0)
            for condition in transfer.UNSCAFFOLDED_CONDITIONS
        ),
        # V3.47: evidencia fina de la escalera endurecida (contextos/días/última
        # marca de los éxitos limpios no andamiados) y objetivos comunicativos
        # distintos de los contextos con éxito limpio.
        "unscaffolded_clean_success_contexts": sorted(unscaffolded_contexts),
        "unscaffolded_clean_success_days": len(unscaffolded_days),
        "clean_success_goals": list(
            transfer.context_dimensions(clean_success_contexts).get(
                "communicative_goal", []
            )
        ),
        "last_clean_success_at": (
            max(clean_timestamps) if clean_timestamps else ""
        ),
        "last_unscaffolded_clean_success_at": (
            max(unscaffolded_timestamps) if unscaffolded_timestamps else ""
        ),
    }


def _int(value: object) -> int:
    """Entero tolerante (0 si no es convertible): los resúmenes pueden ser parciales."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _clamp(value: object, low: float = 0.0, high: float = 1.0) -> float:
    """Acota a `[low, high]` (0.0 si no es numérico). Nunca lanza."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def _unscaffolded_transfer_ok(evidence: dict) -> bool:
    """¿La transferencia está acreditada SIN andamiaje? (V3.46 → V3.47, pura).

    V3.43 declaraba `transfer_demonstrated` con «2 contextos limpios y diversidad
    real», sin mirar CÓMO se había usado la unidad: un éxito en tareas que
    nombran o insinúan el objetivo (`prompted`/`cued_context`) bastaba. V3.46
    empezó a exigir >= 1 éxito limpio en condición NO andamiada
    (`open_context`/`free_choice`/`naturally_emergent`); V3.47 endurece el
    requisito a `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED` (2), porque un único
    acierto sin ayuda no demuestra que la unidad se transfiera de forma estable.

    Sin datos de condición (resumen legacy/parcial, o transferencia registrada
    antes de V3.46) devuelve True: no se puede afirmar que falte el requisito, así
    que se conserva la regla anterior y no hay regresión. Nunca lanza.
    """
    conditions = evidence.get("transfer_conditions")
    if not (isinstance(conditions, dict) and conditions):
        return True
    return (
        _int(evidence.get("unscaffolded_clean_successes"))
        >= TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED
    )


# V3.43 (P1-04): estados del eje de transferencia. Un booleano `transfer = true`
# se quedaba corto: dos contextos con éxito solo son la PRIMERA demostración, no
# estabilidad. El estado es un refinamiento del booleano (que se conserva).
TRANSFER_STATES: tuple[str, ...] = (
    "not_ready",
    "emerging",
    "contextualized",
    "transfer_demonstrated",
    "transfer_stable",
    "automatic",
)

# Mínimo de éxitos LIMPIOS para empezar a hablar de transferencia (espejo de
# `planner.TRANSFER_MIN_SUCCESSES`; ambos se mantienen en 2).
TRANSFER_MIN_SUCCESSES = 2

# V3.47 (P1-02): éxitos limpios NO andamiados exigidos para declarar
# `transfer_demonstrated`. V3.46 bastaba con 1; un único acierto sin ayuda no
# demuestra que la unidad se recupere de forma estable, así que se exigen 2.
TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED = 2

# Estabilidad: exige variedad (más contextos), tiempo (días distintos con éxito
# limpio) y variedad de OBJETIVO comunicativo. Un solo día (o un único tipo de
# producción) demuestra transferencia, no estabilidad.
TRANSFER_STABLE_MIN_CONTEXTS = 3
TRANSFER_STABLE_MIN_DAYS = 3
TRANSFER_STABLE_MIN_GOALS = 2

# Estados que cuentan como transferencia DEMOSTRADA (los lee
# `planner.has_contextual_transfer`).
TRANSFER_DEMONSTRATED_STATES: tuple[str, ...] = (
    "transfer_demonstrated",
    "transfer_stable",
    "automatic",
)


def _clean_success_goals(evidence: dict, contexts: list[str]) -> list[str]:
    """Objetivos comunicativos distintos de los contextos con éxito limpio (V3.47).

    Prefiere el campo declarado en el resumen (`clean_success_goals`, que ya
    computa `context_signals`); si un resumen parcial no lo trae, lo deriva del
    banco con `transfer.context_dimensions`, la única fuente de verdad de los
    atributos de un contexto. Nunca lanza.
    """
    declared = evidence.get("clean_success_goals")
    if isinstance(declared, list):
        return [str(goal).strip() for goal in declared if str(goal).strip()]
    return list(
        transfer.context_dimensions(contexts).get("communicative_goal", [])
    )


# ---------------------------------------------------------------------------
# V3.49 (Transfer Evidence 3.0): CONFIANZA del eje de transferencia.
#
# La auditoría de V3.43.0 (punto 8) avisó de que los nombres de los estados
# (`transfer_demonstrated`, `transfer_stable`) pueden sugerir más evidencia de
# la disponible. V3.49 NO cambia la escalera: sintetiza la evidencia fina ya
# registrada en una confianza EXPLICABLE (`score`/`level`/`drivers`), para poder
# decir no solo en qué estado está la unidad sino con cuánta evidencia se
# afirma. Todo se deriva de campos que `context_signals` ya calcula: no hay
# migración, ni LLM, ni reloj en el `score`.
# ---------------------------------------------------------------------------

# Niveles declarados (de menos a más). `none` = sin evidencia limpia que
# cuantificar (nunca se inventa confianza).
TRANSFER_CONFIDENCE_LEVELS: tuple[str, ...] = ("none", "low", "medium", "high")

# Pesos DECLARADOS y calibrables de los `drivers` (suman 1.0). `independence`
# pesa más porque es lo que distingue recuperar CON ayuda de transferir de
# verdad; `successes` pesa menos porque es volumen, no calidad.
TRANSFER_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "contexts": 0.20,
    "successes": 0.10,
    "diversity": 0.20,
    "independence": 0.25,
    "variety": 0.15,
    "spacing": 0.10,
}

# Umbrales del nivel (0..1). Calibrados para que `transfer_stable` (3 contextos,
# 3 días, 2 objetivos, >= 2 éxitos no andamiados) caiga en `high` y
# `transfer_demonstrated` quede por debajo.
TRANSFER_CONFIDENCE_HIGH = 0.80
TRANSFER_CONFIDENCE_MEDIUM = 0.45


def _confidence_ratio(value: object, ceiling: int) -> float:
    """Componente 0..1 de un contador sobre su techo declarado (0 si no hay).

    Monótono no decreciente en `value`: es lo que garantiza que añadir evidencia
    limpia no baje la confianza. Nunca lanza.
    """
    if ceiling <= 0:
        return 0.0
    return min(1.0, max(0.0, _int(value) / ceiling))


def _confidence_recency_days(evidence: dict, now: str) -> int | None:
    """Días desde el último éxito limpio (`None` sin `now` o sin marca) (V3.49).

    INFORMATIVO: no entra en el `score` (la decisión de confianza no usa reloj,
    igual que `transfer_state`). Nunca lanza.
    """
    if not (now or "").strip():
        return None
    last = (evidence.get("last_clean_success_at") or "").strip()
    start = _parse_iso(last)
    end = _parse_iso(now)
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() // 86400))


def transfer_confidence(evidence: dict | None, *, now: str = "") -> dict:
    """Confianza EXPLICABLE del eje de transferencia (V3.49, pura).

    Devuelve `{score, level, sample, drivers, recency_days}`:

    - `score` — 0..1, suma ponderada (`TRANSFER_CONFIDENCE_WEIGHTS`) de los
      `drivers`; NO usa reloj ni LLM;
    - `level` — `none`/`low`/`medium`/`high` (`TRANSFER_CONFIDENCE_LEVELS`);
    - `sample` — nº de éxitos LIMPIOS observados (tamaño de muestra);
    - `drivers` — componentes 0..1 de evidencia YA registrada: `contexts`
      (contextos con éxito limpio / `TRANSFER_STABLE_MIN_CONTEXTS`), `successes`
      (`clean_successes` normalizado con techo
      `2 * TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED`), `diversity`
      (`diverse_dimensions` / nº de ejes core), `independence`
      (`unscaffolded_clean_successes` / `clean_successes`), `variety`
      (objetivos comunicativos distintos / `TRANSFER_STABLE_MIN_GOALS`) y
      `spacing` (`clean_success_days` / `TRANSFER_STABLE_MIN_DAYS`);
    - `recency_days` — INFORMATIVO (`now` opcional), fuera del `score`.

    Monótona no decreciente al añadir evidencia NO andamiada (cada driver lo es).
    Un resumen legacy/parcial no infla: sin los campos finos de V3.43 en adelante
    devuelve `none`. Nunca lanza.
    """
    ev = evidence or {}
    contexts = ev.get("clean_success_contexts")
    if not isinstance(contexts, list):
        contexts = []
    context_values = [str(c).strip() for c in contexts if str(c).strip()]
    distinct_contexts = len(set(context_values))
    clean_successes = _int(ev.get("clean_successes"))
    unscaffolded = _int(ev.get("unscaffolded_clean_successes"))
    diversity = ev.get("context_diversity")
    if isinstance(diversity, dict):
        diverse_dimensions = _int(diversity.get("diverse_dimensions"))
    else:
        diverse_dimensions = 0
    goals = _clean_success_goals(ev, context_values)
    drivers = {
        "contexts": _confidence_ratio(
            distinct_contexts, TRANSFER_STABLE_MIN_CONTEXTS
        ),
        "successes": _confidence_ratio(
            clean_successes, 2 * TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED
        ),
        "diversity": _confidence_ratio(
            diverse_dimensions, len(transfer.CONTEXT_DIMENSIONS)
        ),
        # Ratio (no contador): de los éxitos limpios, cuántos fueron SIN apoyo.
        # Añadir un éxito no andamiado nunca lo baja; sin éxitos es 0.0.
        "independence": (
            min(1.0, unscaffolded / clean_successes) if clean_successes > 0 else 0.0
        ),
        "variety": _confidence_ratio(
            len(set(goals)), TRANSFER_STABLE_MIN_GOALS
        ),
        "spacing": _confidence_ratio(
            _int(ev.get("clean_success_days")), TRANSFER_STABLE_MIN_DAYS
        ),
    }
    score = 0.0
    for key, weight in TRANSFER_CONFIDENCE_WEIGHTS.items():
        score += weight * _clamp(drivers.get(key, 0.0))
    score = round(_clamp(score), 4)
    if clean_successes <= 0:
        level = "none"
    elif score >= TRANSFER_CONFIDENCE_HIGH:
        level = "high"
    elif score >= TRANSFER_CONFIDENCE_MEDIUM:
        level = "medium"
    else:
        level = "low"
    return {
        "score": score,
        "level": level,
        "sample": clean_successes,
        "drivers": {key: round(value, 4) for key, value in drivers.items()},
        "recency_days": _confidence_recency_days(ev, now),
    }


def transfer_state(evidence: dict | None) -> str:
    """Estado del eje de TRANSFERENCIA contextual (V3.43 → V3.47, pura).

    Sustituye la lectura booleana `transfer = true` por un estado gradual:

    - `not_ready` — sin éxitos limpios suficientes (< `TRANSFER_MIN_SUCCESSES`);
    - `emerging` — éxito limpio en 1 contexto;
    - `contextualized` — >= 2 contextos limpios pero diversidad insuficiente
      (casi el mismo tipo de producción: no es transferencia real) **o** menos de
      `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED` éxitos limpios sin andamiaje
      (V3.46 pedía 1; V3.47 exige 2);
    - `transfer_demonstrated` — >= 2 contextos limpios, diversidad real **y**
      >= `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED` éxitos limpios no andamiados;
    - `transfer_stable` — además >= `TRANSFER_STABLE_MIN_CONTEXTS` contextos,
      >= `TRANSFER_STABLE_MIN_DAYS` días con éxito limpio y
      >= `TRANSFER_STABLE_MIN_GOALS` objetivos comunicativos distintos;
    - `automatic` — estable y la modalidad `spontaneous_use` ya es automática.

    Acepta resúmenes parciales o legacy (cae a `success_contexts`/`successes` y
    respeta el booleano `transfer` cuando no traen los campos de V3.43; sin datos
    de condición de V3.46 se conserva la regla anterior). No usa LLM ni reloj.
    Nunca lanza.
    """
    ev = evidence or {}
    has_v43_fields = (
        isinstance(ev.get("clean_success_contexts"), list)
        or isinstance(ev.get("context_diversity"), dict)
        or ev.get("clean_successes") is not None
    )
    if not has_v43_fields and _truthy(ev.get("transfer")):
        # Resumen legacy (sin ningún campo de V3.43) cuyo booleano `transfer` ya
        # certificaba éxito en >= CONTEXT_TRANSFER_MIN contextos (regla V3.42).
        # Sin diversidad ni días no se puede refinar más: es transferencia
        # DEMOSTRADA, nunca estable. Se respeta el fallback pedido por el plan en
        # lugar de degradar el estado por falta de contadores nuevos.
        return "transfer_demonstrated"
    contexts = ev.get("clean_success_contexts")
    if not isinstance(contexts, list):
        contexts = ev.get("success_contexts") or []
    context_values = [str(c).strip() for c in contexts if str(c).strip()]
    distinct = len(set(context_values))
    clean_successes = _int(ev.get("clean_successes"))
    if not clean_successes:
        # Resumen parcial/legacy sin el contador limpio: se usa el total.
        clean_successes = _int(ev.get("successes"))
    if not clean_successes:
        # Último recurso: cada contexto con éxito garantiza >= 1 éxito. Sin
        # contadores nuevos no se puede afirmar más, pero tampoco menos.
        clean_successes = distinct
    days = _int(ev.get("clean_success_days"))
    diversity = ev.get("context_diversity")
    if isinstance(diversity, dict):
        diverse_dimensions = _int(diversity.get("diverse_dimensions"))
    else:
        # Resumen parcial/legacy SIN la diversidad de V3.43: la única regla
        # disponible era el booleano `transfer` de V3.42 («éxito en
        # >= CONTEXT_TRANSFER_MIN contextos»), que NO medía dimensiones. Se
        # respeta esa semántica en lugar de degradar el estado: sin datos de
        # diversidad no se puede afirmar que sea insuficiente. Si el booleano
        # tampoco viaja, se asume 0 (no se inventa transferencia).
        diverse_dimensions = (
            transfer.CONTEXT_DIVERSITY_MIN if _truthy(ev.get("transfer")) else 0
        )
    automatic = "spontaneous_use" in (ev.get("automatic_skills") or [])
    if distinct < 1 or clean_successes < TRANSFER_MIN_SUCCESSES:
        return "not_ready"
    if distinct < CONTEXT_TRANSFER_MIN:
        return "emerging"
    if (
        diverse_dimensions < transfer.CONTEXT_DIVERSITY_MIN
        or not _unscaffolded_transfer_ok(ev)
    ):
        # Diversidad insuficiente O menos de 2 éxitos limpios sin andamiaje: la
        # unidad se usa en contextos distintos, pero aún no se ha demostrado que
        # se recupere SIN ayuda (V3.46 pedía 1; V3.47 exige 2).
        return "contextualized"
    if (
        distinct >= TRANSFER_STABLE_MIN_CONTEXTS
        and days >= TRANSFER_STABLE_MIN_DAYS
        and len(_clean_success_goals(ev, context_values))
        >= TRANSFER_STABLE_MIN_GOALS
    ):
        return "automatic" if automatic else "transfer_stable"
    return "transfer_demonstrated"


def with_transfer_state(summary: dict) -> dict:
    """Añade el `transfer_state` y la `transfer_confidence` a un resumen (pura).

    El estado se DERIVA de los campos de contexto; no se persiste. Se computa en
    la frontera (resumen puro y resumen SQL) para que ambos expongan el mismo
    valor sin un segundo dialecto de cálculo. V3.49 añade la confianza explicable
    (`transfer_confidence`) en la MISMA frontera, por la misma razón: paridad
    pura↔SQL por construcción.
    """
    summary["transfer_state"] = transfer_state(summary)
    summary["transfer_confidence"] = transfer_confidence(summary)
    return summary


def classify_event_role(event_type: str, detail: str) -> str:
    """Rol de un evento de `learning_events` (evidence/telemetry/informative).

    Reglas deterministas por (tipo, detalle):

    - `drill:<word>:recognition:<ok|ko>` → `informative`: el MCQ de
      reconocimiento no demuestra destrezas productivas (V3.13) y por eso nunca
      acredita nada, aunque siempre se registre.
    - `drill:<word>:recall:<ok|ko>` → `evidence`: recuperar la forma desde el
      significado SÍ es una señal de recuperación real (V3.34).
    - `drill:<word>[:sentence]:<ok|ko>` → `evidence`: la recuperación del
      micro-drill (palabra o frase) acredita retención si supera el intervalo.
    - `drill:*:unclear` → `telemetry`: el ASR no reconoció el audio, no hubo ni
      acierto ni fallo (no se penaliza al alumno).
    - Cualquier otro evento → `telemetry`.
    """
    event_type = (event_type or "").strip()
    detail = (detail or "").strip()
    if event_type != "exercise" or not detail.startswith("drill:"):
        return "telemetry"
    parts = detail[len("drill:") :].split(":")
    outcome = parts[-1] if parts else ""
    if outcome not in _DRILL_OUTCOMES:
        return "telemetry"
    if outcome == "unclear":
        return "telemetry"
    if len(parts) >= 2 and parts[-2] == "recognition":
        return "informative"
    return "evidence"


def _normalize_form(text: str) -> str:
    """Forma normalizada para comparar respuestas (minúsculas, espacios simples).

    La normalización fina del scoring (tildes, puntuación) vive en el dominio
    (`_normalize_lookup_word`); aquí solo se prepara el texto para clasificar."""
    return " ".join((text or "").strip().lower().split())


def _edit_distance(a: str, b: str, *, limit: int) -> int:
    """Distancia de Levenshtein acotada (devuelve `limit + 1` si la supera).

    La cota evita el coste O(len(a)·len(b)) completo en respuestas arbitrarias:
    solo interesa saber si la distancia cae por debajo del umbral de errata.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        best = i
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            value = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + cost,
            )
            current.append(value)
            if value < best:
                best = value
        if best > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _orthographic_threshold(length: int) -> int:
    """Erratas admisibles según la longitud de la forma esperada."""
    return 1 if length <= 6 else 2


def classify_recall_error(expected: str, given: str) -> str:
    """Clasifica el intento de Recall en la taxonomía V3.36 (pura).

    Devuelve uno de `RECALL_ERROR_TYPES`:

    - `correct` — la respuesta coincide con la diana (igualdad estricta);
    - `empty` — no se escribió nada;
    - `partial` — se recuperó PARTE de la unidad, sin errata: un prefijo de la
      palabra (`beauti`) o el comienzo de una unidad multi-palabra (`living`);
    - `orthographic_error` — la forma contiene/roza la diana con 1-2 caracteres
      de diferencia (`beautifull` por `beautiful`, `living roo`): el alumno SABE
      la palabra y la escribió mal;
    - `multiple_word_error` — unidad multi-palabra con tokens equivocados;
    - `wrong_word` — otra palabra (`wonderful` por `beautiful`), el fallo que sí
      merece volver a enseñar el ítem.

    OBSERVACIONAL (V3.36): no altera el scoring ni la evidencia. El objetivo es
    que el tutor (y el futuro planner) distingan "no lo sabe" de "lo sabe y lo
    escribió mal", sin excusar por error una palabra que el alumno no domina:
    por eso la errata exige misma inicial y longitud suficiente (una diferencia
    de un carácter en `cat`/`cut` es otra palabra, no una errata).
    """
    exp = _normalize_form(expected)
    got = _normalize_form(given)
    if not exp:
        return "wrong_word"
    if not got:
        return "empty"
    if got == exp:
        return "correct"
    if " " in exp:
        return _classify_multi_word_error(exp, got)
    # Unidad de una sola palabra. Se comprueba primero la recuperación
    # INCOMPLETA (el alumno escribió menos y lo que escribió es el principio).
    if len(got) < len(exp) and exp.startswith(got):
        return "partial"
    # La diana completa está presente con caracteres de más ("beautifull",
    # "cats" por "cat"): sabe la palabra, la escribió de más.
    if len(got) > len(exp) and got.startswith(exp):
        return "orthographic_error"
    # Errata del mismo tamaño: misma inicial y 1-2 caracteres de diferencia.
    if _is_orthographic(exp, got):
        return "orthographic_error"
    return "wrong_word"


def _is_orthographic(exp: str, got: str) -> bool:
    """¿`got` es una errata admisible de `exp` (misma inicial, 1-2 caracteres)?"""
    if len(exp) < _ORTHOGRAPHIC_MIN_LENGTH or exp[0] != got[0]:
        return False
    limit = _orthographic_threshold(len(exp))
    return _edit_distance(exp, got, limit=limit) <= limit


def _classify_multi_word_error(exp: str, got: str) -> str:
    """Clasifica un intento sobre una unidad multi-palabra.

    El orden importa: una errata global (`living roo` → `living room`) NO es una
    recuperación parcial, aunque comparta tokens; y una recuperación del
    principio (`living` → `living room`) NO es un fallo de unidad."""
    expected_tokens = exp.split()
    given_tokens = got.split()
    # Recuperó el PRINCIPIO de la unidad, token a token.
    if (
        len(given_tokens) < len(expected_tokens)
        and given_tokens == expected_tokens[: len(given_tokens)]
    ):
        return "partial"
    # Recuperó la unidad casi entera y se quedó a medias en el último token:
    # es INCOMPLETO (no una errata), aunque falte un solo carácter.
    if (
        len(given_tokens) == len(expected_tokens)
        and given_tokens[:-1] == expected_tokens[:-1]
        and expected_tokens[-1].startswith(given_tokens[-1])
        and given_tokens[-1] != expected_tokens[-1]
    ):
        return "partial"
    # Unidad entera casi correcta (1-2 caracteres, misma inicial): errata.
    if _is_orthographic(exp, got):
        return "orthographic_error"
    # Recuperación mixta: algún token de la unidad es exacto.
    if any(token in expected_tokens for token in given_tokens):
        return "partial"
    return "multiple_word_error"


def summarize_evidence(rows: list[dict]) -> dict:
    """Resumen longitudinal de una lista de filas de `learning_evidence`.

    Devuelve:

    - `attempts` — nº de eventos (incluye fallos);
    - `successes` — nº de eventos con `success` verdadero;
    - `distinct_success_days` — días naturales distintos con éxito (dos aciertos
      el mismo día cuentan una sola vez, igual que `recall_days`);
    - `intervals` — intervalos (en días) de los eventos CON éxito, en orden
      CRONOLÓGICO (el de las filas recibidas), no ordenados por valor. Es la
      historia que el scheduler puede leer como cadena de repasos: `[1, 7, 3]`
      no es `[1, 3, 7]` (V3.35.1, P1-02: no se pierde la secuencia real).

    V3.36 (Learning Evidence 2.0) añade las dimensiones del evento:

    - `success_rate` — `successes / attempts` (0.0 sin intentos);
    - `independent_successes` — aciertos logrados sin apoyo (`support_level`
      `independent`/`spontaneous`): lo único que podrá pesar en automaticidad;
    - `support_levels` — histograma del apoyo declarado (solo valores canónicos);
    - `error_types` — histograma de la clasificación del intento (incluye
      `correct`, para que el total cuadre con los eventos clasificados);
    - `mean_response_time_ms` — latencia media de los eventos que la midieron
      (None si ninguno la trae).

    V3.37 (cues graduados) añade las señales de automaticidad y de peldaño:

    - `independent_success_days` — DÍAS NATURALES distintos con éxito sin apoyo
      (`independent`/`spontaneous`). `independent_successes` cuenta volumen;
      este campo exige que ese volumen esté ESPACIADO (mismo rigor que
      `distinct_success_days`), que es lo que `is_automatic` necesita;
    - `recall_rungs` — histograma de ÉXITOS de recall por PELDAÑO servido
      (`drill:recall:<peldaño>`): la evidencia con la que `next_recall_rung`
      decide el siguiente peldaño. Los eventos legacy sin peldaño no entran.

    V3.37.1 (política de consolidación y regresión) añade los otros dos ejes
    que la escalera necesita para no ascender con un acierto suelto y para
    retroceder ante fallos repetidos:

    - `recall_rung_days` — DÍAS NATURALES distintos con ÉXITO por peldaño: lo
      que exige `_rung_passed` para dar un peldaño por superado (espaciado,
      mismo rigor que `distinct_success_days`);
    - `recall_rung_failures` — intentos FALLIDOS por peldaño: lo que lee la
      política de regresión. Los eventos legacy sin peldaño no entran en
      ninguno de los tres histogramas (no son evidencia negativa).

    V3.38 (P1-03 de la auditoría de V3.37.0) añade la segmentación por
    MODALIDAD (`LEXICAL_SKILLS`), para que la automaticidad deje de ser un
    booleano global y pase a leerse por modalidad:

    - `skill_successes` / `skill_success_days` — volumen y días con éxito POR
      MODALIDAD;
    - `skill_independent_successes` / `skill_independent_days` — los mismos
      contadores restringidos a éxito SIN apoyo: la base de `automatic_skills`.
      Un `skill` fuera de `LEXICAL_SKILLS` (p. ej. el canal legacy `chat` de
      V3.36-V3.37) no entra en ningún histograma.

    V3.38.1 (P1-02 de la auditoría de V3.38.0) añade las señales por modalidad
    que faltaban para no recomprimir la evidencia en una sola media global:

    - `skill_attempts` — nº de eventos POR MODALIDAD (aciertos y fallos): lo que
      permite calcular la ratio de éxito de cada skill (automaticidad robusta);
    - `skill_mean_response_time_ms` — latencia media POR MODALIDAD (clave
      ausente si la modalidad no midió latencia): lo que permite medir
      `slow_recall` sobre `recall` y no sobre una media que mezcla speaking con
      recuperación de texto.

    V3.39 (Fase 3C, robustez de señales) añade las señales de RECENCIA y de
    DISTRIBUCIÓN de latencia que aporta `recency_signals` (ventana de
    `RECENT_WINDOW_EVENTS` eventos más recientes + percentiles): `recent_
    attempts`, `recent_error_rate`, `recent_wrong_word`, `median/p75/p90_
    response_time_ms`, `recent_response_time_ms` y `latency_trend`. Las calcula
    la MISMA función pura que usa el resumen SQL (paridad por construcción).

    V3.40 (Fase 4, transferencia contextual real) añade las señales por CONTEXTO
    que aporta `context_signals` (`contexts`, `context_attempts`,
    `success_contexts`, `home_context`, `transfer`): el éxito en un contexto
    distinto del de aprendizaje es una dimensión SEPARADA de `situation`
    (recuperación contextualizada) y habilita la tarea de transferencia.

    Nunca lanza: una fila incompleta se cuenta como intento sin éxito.
    """
    attempts = 0
    successes = 0
    days: set[str] = set()
    intervals: list[float] = []
    independent_successes = 0
    independent_days: set[str] = set()
    support_levels: dict[str, int] = {}
    error_types: dict[str, int] = {}
    recall_rungs: dict[str, int] = {}
    recall_rung_days: dict[str, set[str]] = {}
    recall_rung_failures: dict[str, int] = {}
    skill_successes: dict[str, int] = {}
    skill_success_days: dict[str, set[str]] = {}
    skill_independent_successes: dict[str, int] = {}
    skill_independent_days: dict[str, set[str]] = {}
    # V3.38.1 (P1-02): intentos y latencia POR MODALIDAD. Antes solo existía una
    # `mean_response_time_ms` global, así que una producción oral lenta y un
    # recall rápido se promediaban y ninguna señal representaba la fluidez real
    # de la recuperación. `skill_attempts` cuenta TODOS los eventos del skill
    # (aciertos y fallos), como el `attempts` global.
    skill_attempts: dict[str, int] = {}
    skill_latencies: dict[str, list[float]] = {}
    latencies: list[float] = []
    for row in rows:
        attempts += 1
        day = (row.get("occurred_at") or "")[:10]
        level = (row.get("support_level") or "").strip().lower()
        if level in EVIDENCE_SUPPORT_LEVELS:
            support_levels[level] = support_levels.get(level, 0) + 1
        error = (row.get("error_type") or "").strip().lower()
        if error:
            error_types[error] = error_types.get(error, 0) + 1
        skill = (row.get("skill") or "").strip().lower()
        if skill in LEXICAL_SKILLS:
            skill_attempts[skill] = skill_attempts.get(skill, 0) + 1
        raw_latency = row.get("response_time_ms")
        if raw_latency is not None:
            try:
                measured = max(0.0, float(raw_latency))
            except (TypeError, ValueError):
                measured = None
            if measured is not None:
                latencies.append(measured)
                if skill in LEXICAL_SKILLS:
                    skill_latencies.setdefault(skill, []).append(measured)
        # El peldaño se declara en `activity_id` tanto en ÉXITOS como en FALLOS:
        # la progresión lee los éxitos y la regresión, los fallos (V3.37.1).
        rung = recall_rung_from_activity(row.get("activity_id") or "")
        if not _truthy(row.get("success")):
            if rung:
                recall_rung_failures[rung] = recall_rung_failures.get(rung, 0) + 1
            continue
        successes += 1
        if day:
            days.add(day)
        if level in INDEPENDENT_SUPPORT_LEVELS:
            independent_successes += 1
            if day:
                independent_days.add(day)
        # V3.38: segmentación por modalidad. La clave se crea en el ÉXITO
        # (aunque falte el día) para que el valor sea 0 y no una clave ausente:
        # paridad EXACTA con el `GROUP BY skill` de SQL. El `skill` ya se
        # normalizó arriba (V3.38.1: también cuenta intentos por modalidad).
        if skill in LEXICAL_SKILLS:
            skill_successes[skill] = skill_successes.get(skill, 0) + 1
            skill_day_set = skill_success_days.setdefault(skill, set())
            if day:
                skill_day_set.add(day)
            if level in INDEPENDENT_SUPPORT_LEVELS:
                skill_independent_successes[skill] = (
                    skill_independent_successes.get(skill, 0) + 1
                )
                skill_ind_days = skill_independent_days.setdefault(skill, set())
                if day:
                    skill_ind_days.add(day)
        if rung:
            recall_rungs[rung] = recall_rungs.get(rung, 0) + 1
            # La clave se crea aunque falte el día, para que el valor sea 0 y no
            # una clave ausente (paridad EXACTA con el `COUNT DISTINCT` de SQL).
            rung_day_set = recall_rung_days.setdefault(rung, set())
            if day:
                rung_day_set.add(day)
        raw = row.get("interval_since_last_evidence")
        if raw is None:
            continue
        try:
            intervals.append(round(float(raw), 4))
        except (TypeError, ValueError):
            continue
    return with_transfer_state({
        "attempts": attempts,
        "successes": successes,
        "success_rate": round(successes / attempts, 4) if attempts else 0.0,
        "distinct_success_days": len(days),
        "intervals": intervals,
        "independent_successes": independent_successes,
        "independent_success_days": len(independent_days),
        "support_levels": support_levels,
        "error_types": error_types,
        "recall_rungs": recall_rungs,
        "recall_rung_days": {
            rung: len(rung_days) for rung, rung_days in recall_rung_days.items()
        },
        "recall_rung_failures": recall_rung_failures,
        "skill_successes": skill_successes,
        "skill_success_days": {
            skill: len(skill_days) for skill, skill_days in skill_success_days.items()
        },
        "skill_independent_successes": skill_independent_successes,
        "skill_independent_days": {
            skill: len(skill_days)
            for skill, skill_days in skill_independent_days.items()
        },
        # V3.38.1 (P1-02): intentos y latencia media por modalidad (0/None si la
        # modalidad no tiene eventos). La latencia se redondea a 1 decimal para
        # paridad EXACTA con el `AVG(response_time_ms)` de SQL.
        "skill_attempts": skill_attempts,
        "skill_mean_response_time_ms": {
            skill: round(sum(measured) / len(measured), 1)
            for skill, measured in skill_latencies.items()
            if measured
        },
        "mean_response_time_ms": (
            round(sum(latencies) / len(latencies), 1) if latencies else None
        ),
        # V3.39 (Fase 3C): recencia + distribución de latencia. Se delega en la
        # función pura que también usa el resumen SQL: un solo dialecto.
        **recency_signals(rows),
        # V3.40 (Fase 4): transferencia contextual por `context_id` (misma
        # función pura que el resumen SQL).
        **context_signals(rows),
    })


def empty_summary() -> dict:
    """Resumen de evidencia de un ítem sin eventos (mismo contrato que
    `summarize_evidence`). Dict nuevo en cada llamada: nunca compartir estado."""
    return with_transfer_state({
        "attempts": 0,
        "successes": 0,
        "success_rate": 0.0,
        "distinct_success_days": 0,
        "intervals": [],
        "independent_successes": 0,
        "independent_success_days": 0,
        "support_levels": {},
        "error_types": {},
        "recall_rungs": {},
        "recall_rung_days": {},
        "recall_rung_failures": {},
        "skill_successes": {},
        "skill_success_days": {},
        "skill_independent_successes": {},
        "skill_independent_days": {},
        "skill_attempts": {},
        "skill_mean_response_time_ms": {},
        "mean_response_time_ms": None,
        # V3.39 (Fase 3C): recencia y distribución de latencia.
        "recent_attempts": 0,
        "recent_error_rate": 0.0,
        "recent_wrong_word": 0,
        "median_response_time_ms": None,
        "p75_response_time_ms": None,
        "p90_response_time_ms": None,
        "recent_response_time_ms": None,
        "latency_trend": None,
        # V3.40 (Fase 4): transferencia contextual por `context_id`.
        "contexts": {},
        "context_attempts": 0,
        "success_contexts": [],
        "home_context": "",
        # V3.43 (P1-03/P1-04): éxito limpio, diversidad contextual real y estado
        # de transferencia (lo añade `with_transfer_state` al final).
        "clean_contexts": {},
        "clean_successes": 0,
        "clean_success_contexts": [],
        "clean_success_days": 0,
        "context_diversity": {
            "distinct_contexts": 0,
            "dimensions": {},
            "diverse_dimensions": 0,
            "score": 0.0,
            # V3.48: variedad informativa (mismo contrato que `context_variety`).
            "variety": {"dimensions": {}, "varied_dimensions": 0, "score": 0.0},
        },
        "transfer": False,
        # V3.46: condición de recuperación ({} = sin datos de condición, se
        # aplica la regla legacy de `transfer_state`).
        "transfer_conditions": {},
        "success_conditions": [],
        "unscaffolded_clean_successes": 0,
        # V3.47: evidencia fina de la escalera endurecida (mismos defaults neutros
        # que un resumen real sin éxitos limpios no andamiados).
        "unscaffolded_clean_success_contexts": [],
        "unscaffolded_clean_success_days": 0,
        "clean_success_goals": [],
        "last_clean_success_at": "",
        "last_unscaffolded_clean_success_at": "",
    })


def _success_ratio(evidence: dict) -> float | None:
    """Ratio de éxito del resumen (None si no se puede confirmar).

    Prioriza `success_rate` (contrato del resumen); si falta, lo deriva de
    `successes`/`attempts` (dicts parciales). Sin intentos no hay ratio: la
    automaticidad NO se declara (no se inventa evidencia).
    """
    rate = evidence.get("success_rate")
    if rate is not None:
        try:
            return float(rate)
        except (TypeError, ValueError):
            pass
    try:
        attempts = int(evidence.get("attempts") or 0)
        successes = int(evidence.get("successes") or 0)
    except (TypeError, ValueError):
        return None
    return (successes / attempts) if attempts > 0 else None


def _has_grave_error(evidence: dict) -> bool:
    """¿El ítem acumula confusión real (`wrong_word`) por encima del umbral?

    V3.38.1: aproximación determinista a "sin fallo grave". Una errata
    (`orthographic_error`) no cuenta: no es no-saber.

    V3.39 (Fase 3C): si el resumen trae la VENTANA de recencia
    (`recent_wrong_word`, que sí aporta `summarize_evidence`/el resumen SQL), el
    juicio se hace SOLO sobre ella: una confusión de hace cuarenta repasos ya
    corregida no debe bloquear la automaticidad para siempre. Sin ventana (un
    resumen parcial construido a mano) se cae al histórico, como en V3.38.1.
    """
    recent = evidence.get("recent_wrong_word")
    if recent is not None:
        try:
            return int(recent) > AUTOMATIC_MAX_WRONG_WORD_ERRORS
        except (TypeError, ValueError):
            pass
    errors = evidence.get("error_types")
    if not isinstance(errors, dict):
        return False
    try:
        return int(errors.get("wrong_word") or 0) > AUTOMATIC_MAX_WRONG_WORD_ERRORS
    except (TypeError, ValueError):
        return False


def _has_skill_segmentation(evidence: dict) -> bool:
    """¿El resumen trae segmentación POR MODALIDAD con datos? (V3.39, pura).

    Un resumen de V3.38+ (`summarize_evidence`/`summarize_by_target`) siempre
    incluye las claves `skill_*`, pero pueden estar VACÍAS si el ledger no
    registró modalidad (filas legacy o actividades sin `skill`). En ese caso no
    hay segunda definición de automaticidad que aplicar y `is_automatic` cae al
    criterio GLOBAL, que es el único que el resumen puede sostener.
    """
    for key in (
        "skill_successes",
        "skill_attempts",
        "skill_independent_successes",
        "skill_independent_days",
    ):
        bucket = evidence.get(key)
        if isinstance(bucket, dict) and bucket:
            return True
    return False


def is_automatic(evidence: dict) -> bool:
    """¿El ítem es `automatic`? (V3.37 → V3.39, puro y determinista).

    V3.39 (Fase 3C): se UNIFICA la definición para acabar con las dos que podían
    divergir (P2 de la auditoría de V3.38.1). Si el resumen trae segmentación por
    modalidad (`_has_skill_segmentation`), el ítem es automático EXACTAMENTE
    cuando ALGUNA modalidad lo es (`automatic_skills`): dos modalidades distintas,
    ninguna consolidada, ya no suman automaticidad a nivel de ítem — el bug de
    P1-03 que V3.38 solo había cerrado por modalidad.

    Para resúmenes SIN segmentación (parciales construidos a mano o ledger
    legacy sin `skill`) se mantiene el criterio GLOBAL de V3.38.1 — 3 éxitos
    independientes en 3 días naturales distintos, ratio mínima y sin fallo grave
    —, que es el único que esos resúmenes pueden sostener. Así el cambio es
    aditivo para el contrato parcial y correctivo para el resumen real.

    Un acierto suelto no es automaticidad (D5/E3) y cued/guided no cuentan como
    independientes aunque se repitan. Nunca lanza: un resumen vacío o incompleto
    no es automaticidad.
    """
    if not evidence or _has_grave_error(evidence):
        return False
    if _has_skill_segmentation(evidence):
        return bool(automatic_skills(evidence))
    try:
        successes = int(evidence.get("independent_successes") or 0)
        days = int(evidence.get("independent_success_days") or 0)
    except (TypeError, ValueError):
        return False
    ratio = _success_ratio(evidence)
    return (
        successes >= AUTOMATIC_MIN_INDEPENDENT
        and days >= AUTOMATIC_MIN_INDEPENDENT
        and ratio is not None
        and ratio >= AUTOMATIC_MIN_SUCCESS_RATIO
    )


def automatic_skills(evidence: dict) -> list[str]:
    """Modalidades en las que el ítem es `automatic` (V3.38 → V3.38.1, puro).

    Aplica el MISMO umbral que `is_automatic` — `AUTOMATIC_MIN_INDEPENDENT`
    éxitos independientes en días naturales distintos, ratio mínima de éxito y
    sin fallo grave — pero POR MODALIDAD, no al ítem entero. Es la respuesta a
    P1-03 de la auditoría de V3.37.0: `automatic` global podía mezclar una
    producción escrita con un recall oral y declarar automático un ítem que
    ninguna modalidad domina.

    Lee `skill_independent_successes`/`skill_independent_days` y, para la ratio,
    `skill_successes`/`skill_attempts` (V3.38.1) del resumen. Devuelve las
    modalidades en orden canónico (`LEXICAL_SKILLS`). El fallo grave es global
    (el resumen no segmenta `error_types` por modalidad): un ítem con confusión
    real no declara ninguna modalidad automática. Nunca lanza.
    """
    if not evidence or _has_grave_error(evidence):
        return []
    successes = evidence.get("skill_independent_successes") or {}
    days = evidence.get("skill_independent_days") or {}
    skill_successes = evidence.get("skill_successes") or {}
    skill_attempts = evidence.get("skill_attempts") or {}
    if not all(
        isinstance(bucket, dict)
        for bucket in (successes, days, skill_successes, skill_attempts)
    ):
        return []
    result: list[str] = []
    for skill in LEXICAL_SKILLS:
        try:
            volume = int(successes.get(skill, 0) or 0)
            spaced = int(days.get(skill, 0) or 0)
            won = int(skill_successes.get(skill, 0) or 0)
            total = int(skill_attempts.get(skill, 0) or 0)
        except (TypeError, ValueError):
            continue
        rate = (won / total) if total > 0 else 0.0
        if (
            volume >= AUTOMATIC_MIN_INDEPENDENT
            and spaced >= AUTOMATIC_MIN_INDEPENDENT
            and rate >= AUTOMATIC_MIN_SUCCESS_RATIO
        ):
            result.append(skill)
    return result
