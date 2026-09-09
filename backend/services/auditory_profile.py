"""Perfil auditivo del alumno y detección de intervención (V3.27, Listening 4.0).

Interpreta el diagnóstico existente (`listening_diagnostic`) como un perfil en
tres ejes —capas recognition/comprehension/inference— más las condiciones de
escucha (resiliencia) y devuelve la intervención pedagógica recomendada según
los casos A-D de la especificación `docs/LISTENING_ENGINE_4.0.md` §5:

- Caso D (condición acústica): solo entiende habla clara; `connected_speech_path`.
- Caso A (bottom-up): pierde palabras en el flujo acústico; `bottom_up_path`.
- Caso B (comprensión): oye pero no construye el significado; `comprehension_path`.
- Caso C (top-down/pragmática): comprende lo literal pero no infiere;
  `top_down_path`.

Ninguna capa se declara fuerte/débil con menos de `PROFILE_MIN_ATTEMPTS`. La
`automaticity` NO participa: es señal auxiliar, nunca CEFR ni mastery.
"""
from __future__ import annotations

# Muestras mínimas por capa para declarar una señal (alineado con la resiliencia
# auditiva de services.listening: RESILIENCE_MIN_ATTEMPTS = 3).
PROFILE_MIN_ATTEMPTS = 3

# Umbrales por defecto del perfil (a calibrar; spec §5.2).
R_LOW = 70.0  # precisión de capa considerada débil
HIGH = 85.0  # precisión considerada sólida
INF_LOW = 60.0  # umbral de inferencia débil
COND_LOW = 60.0  # condición natural/connected débil
COND_HIGH = 80.0  # condición clara sólida

_LAYERS = ("recognition", "comprehension", "inference")


def _entry(entries: list[dict], key: str, value: str) -> dict | None:
    """Entrada de una lista `{clave: valor, attempts, correct, accuracy}`."""
    for entry in entries:
        if entry.get(key) == value:
            return entry
    return None


def _has_min(entry: dict | None) -> bool:
    """True si la entrada tiene muestra suficiente y precisión medible."""
    return (
        entry is not None
        and int(entry.get("attempts") or 0) >= PROFILE_MIN_ATTEMPTS
        and entry.get("accuracy") is not None
    )


def _acc(entry: dict | None) -> float:
    if entry is None or entry.get("accuracy") is None:
        return 0.0
    return float(entry["accuracy"])


def _by_layer(diagnostic: dict, layer: str) -> dict | None:
    return _entry(list(diagnostic.get("by_layer", [])), "layer", layer)


def _res_dim(diagnostic: dict, dimension: str) -> dict | None:
    return _entry(
        list(diagnostic.get("resilience", {}).get("dimensions", [])),
        "dimension",
        dimension,
    )


def _any_layer_signal(diagnostic: dict) -> bool:
    return any(_has_min(_by_layer(diagnostic, layer)) for layer in _LAYERS)


def auditory_profile(diagnostic: dict) -> dict:
    """Capa objetivo, intervención y motivo a partir del diagnóstico.

    Entra el dict devuelto por `listening_diagnostic(...)` (con `by_layer` y
    `resilience`) y devuelve:
    {layer: "recognition"|"comprehension"|"inference"|None,
     intervention: "bottom_up_path"|"comprehension_path"|"top_down_path"
                   |"connected_speech_path"|None,
     reason: str, needs_min_attempts: bool}.

    Precedencia D → A → B → C (spec §5.2): la condición acústica se evalúa
    primero porque condiciona la lectura de las demás (no se puede medir
    inferencia sobre audio que no se percibe).
    """
    rec = _by_layer(diagnostic, "recognition")
    com = _by_layer(diagnostic, "comprehension")
    inf = _by_layer(diagnostic, "inference")
    clear = _res_dim(diagnostic, "clear_speech")
    natural = _res_dim(diagnostic, "natural_speech")
    connected = _res_dim(diagnostic, "connected_speech")

    # Caso D: solo entiende habla clara y controlada.
    cond = connected if _has_min(connected) else natural
    if (
        cond is not None
        and _acc(cond) < COND_LOW
        and _has_min(clear)
        and _acc(clear) >= COND_HIGH
    ):
        dimension = "connected_speech" if cond is connected else "natural_speech"
        return {
            "layer": None,
            "intervention": "connected_speech_path",
            "reason": dimension,
            "needs_min_attempts": False,
        }

    # Caso A: comprehension sólida pero recognition débil → bottom-up.
    if _has_min(rec) and rec["accuracy"] < R_LOW and _acc(com) >= HIGH:
        return {
            "layer": "recognition",
            "intervention": "bottom_up_path",
            "reason": "recognition",
            "needs_min_attempts": False,
        }

    # Caso B: recognition sólida pero comprehension débil → comprensión.
    if _has_min(com) and com["accuracy"] < R_LOW and _acc(rec) >= HIGH:
        return {
            "layer": "comprehension",
            "intervention": "comprehension_path",
            "reason": "comprehension",
            "needs_min_attempts": False,
        }

    # Caso C: comprehension sólida pero inference débil → top-down/pragmática.
    if _has_min(inf) and inf["accuracy"] < INF_LOW and _acc(com) >= HIGH:
        return {
            "layer": "inference",
            "intervention": "top_down_path",
            "reason": "inference",
            "needs_min_attempts": False,
        }

    return {
        "layer": None,
        "intervention": None,
        "reason": "",
        "needs_min_attempts": not _any_layer_signal(diagnostic),
    }


def intervention_label(intervention: str) -> str:
    """Clave i18n de la intervención para la UI (frontend la traduce)."""
    if not intervention:
        return "listening.profile.intervention.none"
    return f"listening.profile.intervention.{intervention}"
