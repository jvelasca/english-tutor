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

from datetime import datetime, timezone

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
AUTOMATIC_MIN_INDEPENDENT = 2

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
        raw_latency = row.get("response_time_ms")
        if raw_latency is not None:
            try:
                latencies.append(max(0.0, float(raw_latency)))
            except (TypeError, ValueError):
                pass
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
        # paridad EXACTA con el `GROUP BY skill` de SQL.
        skill = (row.get("skill") or "").strip().lower()
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
    return {
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
        "mean_response_time_ms": (
            round(sum(latencies) / len(latencies), 1) if latencies else None
        ),
    }


def empty_summary() -> dict:
    """Resumen de evidencia de un ítem sin eventos (mismo contrato que
    `summarize_evidence`). Dict nuevo en cada llamada: nunca compartir estado."""
    return {
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
        "mean_response_time_ms": None,
    }


def is_automatic(evidence: dict) -> bool:
    """¿El ítem es `automatic`? (V3.37, puro y determinista).

    Exige DOS condiciones sobre el resumen de evidencia:

    - `independent_successes >= AUTOMATIC_MIN_INDEPENDENT` — logro sin apoyo
      (no basta con `cued`/`guided`: eso es recuperación CON ayuda);
    - `independent_success_days >= AUTOMATIC_MIN_INDEPENDENT` — esos éxitos
      caen en DÍAS NATURALES distintos.

    Un acierto suelto no es automaticidad (D5/E3) y cued/guided no cuentan como
    independientes aunque se repitan. Nunca lanza: un resumen vacío o incompleto
    no es automaticidad.
    """
    if not evidence:
        return False
    try:
        successes = int(evidence.get("independent_successes") or 0)
        days = int(evidence.get("independent_success_days") or 0)
    except (TypeError, ValueError):
        return False
    return (
        successes >= AUTOMATIC_MIN_INDEPENDENT
        and days >= AUTOMATIC_MIN_INDEPENDENT
    )


def automatic_skills(evidence: dict) -> list[str]:
    """Modalidades en las que el ítem es `automatic` (V3.38, puro).

    Aplica el MISMO umbral que `is_automatic` (`AUTOMATIC_MIN_INDEPENDENT`
    éxitos independientes en días naturales distintos) pero POR MODALIDAD, no
    al ítem entero. Es la respuesta a P1-03 de la auditoría de V3.37.0:
    `automatic` global podía mezclar una producción escrita con un recall oral
    y declarar automático un ítem que ninguna modalidad domina.

    Lee `skill_independent_successes` / `skill_independent_days` (histogramas
    del resumen) y devuelve las modalidades en orden canónico (`LEXICAL_SKILLS`).
    Nunca lanza: un resumen vacío o incompleto devuelve [].
    """
    if not evidence:
        return []
    successes = evidence.get("skill_independent_successes") or {}
    days = evidence.get("skill_independent_days") or {}
    if not isinstance(successes, dict) or not isinstance(days, dict):
        return []
    result: list[str] = []
    for skill in LEXICAL_SKILLS:
        try:
            volume = int(successes.get(skill, 0) or 0)
            spaced = int(days.get(skill, 0) or 0)
        except (TypeError, ValueError):
            continue
        if volume >= AUTOMATIC_MIN_INDEPENDENT and spaced >= AUTOMATIC_MIN_INDEPENDENT:
            result.append(skill)
    return result
