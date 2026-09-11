"""Estado de NIVEL del alumno: practice / estimated / demonstrated (V3.52).

V3.51 usaba como "nivel demostrado" la caché `learning_profile.cefr_level`, pero
esa columna la escribe `domain.profile` con `estimated_level`: una banda de
PRÁCTICA continua (suelo por niveles completados + progreso ponderado), no una
certificación. La auditoría externa de V3.51 lo señaló como P1: se podía
sobreestimar el nivel del alumno y elevar el suelo de dificultad sin evidencia
que lo respaldara.

El Student Model ([`domain/academy.py`](../../domain/academy.py)
`build_student_model`) ya produce DOS nociones distintas, y este módulo las
formaliza junto a una tercera:

- ``practice_level``   — el nivel CEFR del currículo en el que el alumno está
  matriculado (`current_level`). Es CONTEXTO, no una estimación de competencia.
- ``estimated_cefr``   — el nivel ESTIMADO (`adaptive.estimated_level`): banda
  continua de práctica. Puede quedar por encima del demostrado (un nivel
  completado aprobando examen da suelo, sin certificar retención).
- ``demonstrated_cefr`` — el nivel DEMOSTRADO (`_demonstrated_level`): exige
  matrícula completada **y** `certification_gate` certificado (retención
  retardada). Es la única fuente con garantía; `""` hasta la primera
  certificación.

La política de suelo de dificultad es deliberadamente conservadora: SOLO el
nivel demostrado se usa con la máxima confianza; el estimado y el declarado son
proxies de menor confianza (el motor de dificultad les da más margen de
tolerancia, ver `services.difficulty`).

Módulo PURO: sin I/O, sin reloj, sin aleatoriedad. Nunca lanza.
"""

from __future__ import annotations

from services import transfer

# Orden de PRIORIDAD de las fuentes de suelo (de mayor a menor confianza). No es
# un orden alfabético ni de nivel: es el orden en el que `floor_level` elige.
LEVEL_SOURCES: tuple[str, ...] = (
    "demonstrated",
    "estimated",
    "practice",
    "none",
)

# Fuentes cuya evidencia es una CERTIFICACIÓN formal (retención demostrada). Son
# las únicas que merecen la tolerancia estricta del motor de dificultad.
CERTIFIED_SOURCES: frozenset[str] = frozenset({"demonstrated"})

_EMPTY_STATE: dict[str, str] = {
    "practice_level": "",
    "estimated_cefr": "",
    "demonstrated_cefr": "",
    "floor_level": "",
    "floor_source": "none",
}


def _normalize_level(value: object) -> str:
    """Nivel CEFR canónico en mayúsculas ("" si no se reconoce). Nunca lanza."""
    text = str(value or "").strip().upper()
    return text if transfer.cefr_index(text) >= 0 else ""


def floor_level(
    practice_level: object = "",
    estimated_cefr: object = "",
    demonstrated_cefr: object = "",
) -> tuple[str, str]:
    """Nivel que actúa de SUELO de dificultad y su FUENTE (V3.52, pura).

    Prioridad: demostrado > estimado > declarado (nivel de práctica) > ninguno.
    Devuelve `(nivel, fuente)` con fuente en `LEVEL_SOURCES`. Un valor no CEFR
    (o `None`) no participa: no se inventa un suelo con datos que no se
    reconocen. Nunca lanza.
    """
    candidates = (
        ("demonstrated", demonstrated_cefr),
        ("estimated", estimated_cefr),
        ("practice", practice_level),
    )
    for source, raw in candidates:
        level = _normalize_level(raw)
        if level:
            return level, source
    return "", "none"


def level_state(
    *,
    practice_level: object = "",
    estimated_cefr: object = "",
    demonstrated_cefr: object = "",
) -> dict[str, str]:
    """Estado de nivel del alumno con el suelo ya derivado (V3.52, pura).

    Devuelve `{practice_level, estimated_cefr, demonstrated_cefr, floor_level,
    floor_source}` con los tres niveles normalizados ("" si no se reconocen) y
    el resultado de `floor_level`. Un estado vacío es válido: significa "sin
    nivel conocido" y deja el comportamiento en el de V3.46/V3.47 (el motor de
    dificultad no filtra). Nunca lanza.
    """
    practice = _normalize_level(practice_level)
    estimated = _normalize_level(estimated_cefr)
    demonstrated = _normalize_level(demonstrated_cefr)
    floor, source = floor_level(practice, estimated, demonstrated)
    return {
        "practice_level": practice,
        "estimated_cefr": estimated,
        "demonstrated_cefr": demonstrated,
        "floor_level": floor,
        "floor_source": source,
    }


def is_certified(source: object) -> bool:
    """¿La fuente del suelo es una certificación formal demostrada? (V3.52)."""
    return str(source or "").strip().lower() in CERTIFIED_SOURCES


def empty_state() -> dict[str, str]:
    """Estado neutro (sin nivel conocido). Dict nuevo en cada llamada."""
    return dict(_EMPTY_STATE)
