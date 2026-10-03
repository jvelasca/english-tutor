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

2. **`mode` es una PREFERENCIA declarada sobre la taxonomía del Planner 3.0**
   (Política B, V3.87.1), no un filtro duro ni una segunda taxonomía. Las
   actividades viven en `services.lexicon.REVIEW_ACTIVITIES`; aquí solo se dice
   a qué modo pertenece cada una. Si el planner añade una actividad hay que
   clasificarla aquí (y `mixed` no filtra, así que una actividad nueva nunca
   queda inalcanzable por olvido). El modo orienta la selección; no garantiza la
   exclusión absoluta: `fallback_activity` conserva `recognition` como
   prerrequisito en producción y el conjunto filtrado vacío se degrada al
   conjunto sin filtrar.

3. **Un valor desconocido no rompe: cae al defecto.** La configuración viaja como
   JSON en la tabla `settings` y puede llegar de una versión anterior o de una
   edición manual; `normalize_study_config` es la frontera que garantiza que
   dentro del motor solo entran valores del contrato.
"""
from __future__ import annotations

#: Direcciones de la tarjeta: el idioma del que se pregunta y el que se responde.
DIRECTIONS: tuple[str, ...] = ("en-es", "es-en")

#: Modo de la sesión. `mixed` admite la taxonomía entera (sin preferencia).
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

#: Tope de la cola de Estudiar (nuevas + repasos) en el banco y el mazo automático.
DEFAULT_WORDS_PER_DAY = 20
WORDS_PER_DAY_MIN = 1
WORDS_PER_DAY_MAX = 200

#: Pasos que el alumno PUEDE marcar como obligatorios para contar una palabra
#: como aprendida. El significado siempre cuenta y no viaja en esta lista.
OPTIONAL_FACETS: tuple[str, ...] = (
    "pronunciation",
    "context",
    "senses",
    "related",
)

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


def _words_per_day(value: object) -> int:
    """Entero dentro del tope.

    Un valor ilegible cae al defecto; uno fuera, se recorta.
    """
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_WORDS_PER_DAY
    return max(WORDS_PER_DAY_MIN, min(WORDS_PER_DAY_MAX, number))


def _required_facets(value: object) -> list[str]:
    """Subconjunto ordenado de los pasos opcionales. El significado no se lista."""
    if not isinstance(value, list):
        return []
    wanted = {
        item.strip().lower()
        for item in value
        if isinstance(item, str) and item.strip()
    }
    return [name for name in OPTIONAL_FACETS if name in wanted]


def normalize_study_config(raw: object) -> dict:
    """Devuelve SIEMPRE el contrato completo con valores válidos.

    Acepta lo que venga (un dict de JSON, `None`, basura): la normalización es la
    frontera del motor, así que un valor raro cae al defecto en vez de propagarse.
    `words_per_day` es un entero y `required_facets` una lista; el resto sigue
    siendo texto.
    """
    data = raw if isinstance(raw, dict) else {}
    config: dict = {
        key: _one_of(data.get(key), allowed, DEFAULTS[key])
        for key, allowed in _ALLOWED.items()
    }
    config["words_per_day"] = _words_per_day(data.get("words_per_day"))
    config["required_facets"] = _required_facets(data.get("required_facets"))
    return config


def allowed_activities(config: dict | None) -> tuple[str, ...] | None:
    """Actividades PREFERIDAS del Planner 3.0 para este modo, o `None` sin filtro.

    `None` significa «no restrinjas»: es el caso de `mixed` y también el de una
    configuración ausente o corrupta, para que la preferencia nunca vacíe la
    sesión por un valor que no se entiende.

    Ojo: esto es la PRIMERA capa de la Política B (ver `fallback_activity`). NO
    es un filtro duro: restringe las candidatas del argmax, pero si el conjunto
    queda vacío el Planner sirve el conjunto SIN filtrar, y una recomendación de
    cascada fuera del modo se sirve como la actividad admisible más cercana.
    """
    mode = (config or {}).get("mode")
    if mode == "production":
        return PRODUCTION_ACTIVITIES
    if mode == "recognition":
        return RECOGNITION_ACTIVITIES
    return None


def fallback_activity(activity: str, allowed: tuple[str, ...] | None) -> str:
    """Actividad admisible más cercana a la recomendada por la cascada.

    `mode` es una **preferencia pedagógica**, no un filtro estricto (Política B,
    congelada en V3.87.1). El modo no borra la pedagogía: cuando la evidencia
    pide una actividad fuera del conjunto, se sirve la admisible más cercana en
    vez de saltarse el ítem (que sigue vencido y hay que atender). Dos reglas
    explícitas:

    - modo reconocimiento → `recall` (nunca se produce si el alumno pidió no
      producir);
    - modo producción → `sentence`, SALVO si la cascada pide `recognition`: sin
      base receptiva no hay con qué producir, así que se respeta el primer
      peldaño como PRERREQUISITO (mejor reconocer que forzar).

    Por tanto `production` no garantiza la exclusión de `recognition`: el modo
    orienta la selección, no la encierra. La otra capa de la misma política vive
    en `planner.task_candidates` (un filtro que deja el conjunto vacío se degrada
    al conjunto SIN filtrar). Ver la release V3.87.1.
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
