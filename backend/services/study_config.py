"""Configuración de estudio del alumno (V3.87.0, FASE 2 · incremento 1).

Es la preferencia con la que el alumno dice CÓMO quiere estudiar, y es **pura**:
no lee ni escribe nada, solo normaliza y traduce el contrato a decisiones. Cuatro
dimensiones, deliberadamente pocas para que la sesión siga siendo una sesión y no
un panel de control:

    direction   qué cara se pregunta (EN→ES o ES→EN)
    mode        reconocer, producir o las dos
    hints       qué ayuda se ofrece ANTES de voltear (nunca la respuesta)
    difficulty  cuánta carga entra de una vez

Tres decisiones que conviene entender antes de tocar esto:

1. **La dirección es PRESENTACIÓN, no programación.** Una ficha tiene UNA carta
   FSRS (`fsrs_cards` se indexa por `(user_id, target_type, target_id)`) y la
   dirección solo elige qué cara se enseña y cuál se responde. Crear una carta
   por dirección sería un cambio de clave del scheduler que este incremento NO
   hace: el calendario de repaso no cambia al girar la tarjeta.

2. **`mode` es un FILTRO declarado sobre la taxonomía del Planner 3.0**, no una
   segunda taxonomía. Las actividades viven en `services.lexicon.
   REVIEW_ACTIVITIES`; aquí solo se dice a qué modo pertenece cada una. Si el
   planner añade una actividad hay que clasificarla aquí (y `mixed` no filtra,
   así que una actividad nueva nunca queda inalcanzable por olvido).

3. **Un valor desconocido no rompe: cae al defecto.** La configuración viaja como
   JSON en la tabla `settings` y puede llegar de una versión anterior o de una
   edición manual; `normalize_study_config` es la frontera que garantiza que
   dentro del motor solo entran valores del contrato.
"""
from __future__ import annotations

#: Direcciones de la tarjeta: el idioma del que se pregunta y el que se responde.
DIRECTIONS: tuple[str, ...] = ("en-es", "es-en")

#: Modo de la sesión. `mixed` admite la taxonomía entera (sin filtro).
MODES: tuple[str, ...] = ("recognition", "production", "mixed")

#: Qué se ofrece antes de voltear. La DEFINICIÓN (diccionario) y el RECORDATORIO
#: (mnemónico de la ficha) son las dos ayudas disponibles; la respuesta nunca.
HINT_LEVELS: tuple[str, ...] = ("off", "definition", "mnemonic", "all")

#: Carga de la sesión: cuánto material se sirve de una vez.
DIFFICULTIES: tuple[str, ...] = ("gentle", "auto", "intensive")

DEFAULT_DIRECTION = "en-es"
DEFAULT_MODE = "recognition"
DEFAULT_HINTS = "off"
DEFAULT_DIFFICULTY = "auto"

#: Actividades del Planner 3.0 (`services.lexicon.REVIEW_ACTIVITIES`) por modo.
#: `recognition` es reconocer/recuperar con apoyo; `production` es construir
#: (frase, escritura, transferencia). `mixed` no filtra: se traduce a `None`.
PRODUCTION_ACTIVITIES: tuple[str, ...] = ("sentence", "write", "transfer")
RECOGNITION_ACTIVITIES: tuple[str, ...] = ("recognition", "recall")

#: El defecto completo, en un solo sitio (lo consume la persistencia y la API).
DEFAULTS: dict[str, str] = {
    "direction": DEFAULT_DIRECTION,
    "mode": DEFAULT_MODE,
    "hints": DEFAULT_HINTS,
    "difficulty": DEFAULT_DIFFICULTY,
}

#: Dimensión → valores admitidos. Tabla única para normalizar sin repetir ramas.
_ALLOWED: dict[str, tuple[str, ...]] = {
    "direction": DIRECTIONS,
    "mode": MODES,
    "hints": HINT_LEVELS,
    "difficulty": DIFFICULTIES,
}


def _one_of(value: object, allowed: tuple[str, ...], default: str) -> str:
    """El valor si pertenece al contrato (sin distinguir mayúsculas), o el defecto."""
    candidate = value.strip().lower() if isinstance(value, str) else ""
    return candidate if candidate in allowed else default


def normalize_study_config(raw: object) -> dict[str, str]:
    """Devuelve SIEMPRE las cuatro claves con valores válidos.

    Acepta lo que venga (un dict de JSON, `None`, basura): la normalización es la
    frontera del motor, así que un valor raro cae al defecto en vez de propagarse.
    """
    data = raw if isinstance(raw, dict) else {}
    return {
        key: _one_of(data.get(key), allowed, DEFAULTS[key])
        for key, allowed in _ALLOWED.items()
    }


def allowed_activities(config: dict | None) -> tuple[str, ...] | None:
    """Actividades admisibles del Planner 3.0 para este modo, o `None` sin filtro.

    `None` significa «no restrinjas»: es el caso de `mixed` y también el de una
    configuración ausente o corrupta, para que el filtro nunca vacíe la sesión por
    un valor que no se entiende.
    """
    mode = (config or {}).get("mode")
    if mode == "production":
        return PRODUCTION_ACTIVITIES
    if mode == "recognition":
        return RECOGNITION_ACTIVITIES
    return None


def fallback_activity(activity: str, allowed: tuple[str, ...] | None) -> str:
    """Actividad admisible más cercana a la recomendada por la cascada.

    El modo no borra la pedagogía: cuando la evidencia pide una actividad fuera
    del conjunto, se sirve la admisible más cercana en vez de saltarse el ítem
    (que sigue vencido y hay que atender). Dos reglas explícitas:

    - modo reconocimiento → `recall` (nunca se produce si el alumno pidió no
      producir);
    - modo producción → `sentence`, SALVO si la cascada pide `recognition`: sin
      base receptiva no hay con qué producir, así que se respeta el primer
      peldaño (es el fallback declarado: mejor reconocer que forzar).
    """
    if not allowed or activity in allowed:
        return activity
    if allowed == RECOGNITION_ACTIVITIES:
        return "recall"
    if allowed == PRODUCTION_ACTIVITIES and activity == "recognition":
        return activity
    return allowed[0]


def hints_definition(config: dict | None) -> bool:
    """¿Se ofrece la definición de diccionario antes de voltear?"""
    return (config or {}).get("hints") in ("definition", "all")


def hints_mnemonic(config: dict | None) -> bool:
    """¿Se ofrece el recordatorio de la ficha antes de voltear?"""
    return (config or {}).get("hints") in ("mnemonic", "all")
