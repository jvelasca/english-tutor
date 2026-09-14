"""Taxonomía declarada del estado del alumno por MODALIDAD × COMPETENCIA (V3.62).

V3.62 (Student Skill State 4.0) unifica los DOS modelos del alumno que hasta
V3.61 convivían sin tocarse (briefing `agentes/v362-student-skill-state-4.md`):
el **adaptativo léxico** (`services.evidence.LEXICAL_SKILLS` ×
`services.difficulty.DIFFICULTY_DIMENSIONS`) y el **curricular**
(`services.mastery.MASTERY_SKILLS` × 4 estados pedagógicos). Este módulo declara
el VOCABULARIO de esa unificación y **no toca** ninguno de los vocabularios
existentes: los MAPEA. La consolidación de los ~15 vocabularios del árbol llega
cuando los consumidores lo pidan (y con test).

Tres piezas declaradas:

- `SKILL_MODALITIES` — las 9 modalidades canónicas del estado (las de
  `MASTERY_SKILLS`). El eje de COMPETENCIA vive DENTRO de la modalidad
  (`COMPETENCES_BY_MODALITY`), nunca al revés.
- `MODALITY_OF` / `MODALITY_BY_VOCABULARY` — mapeo TOTAL de las cadenas de cada
  vocabulario del árbol hacia una modalidad canónica. `MODALITY_BY_VOCABULARY`
  es el mapa preciso por vocabulario; `MODALITY_OF` es su aplanado, que sirve de
  puerta de TOTALIDAD (el test de la release recorre los vocabularios reales y
  falla si una cadena nueva no está aquí ni en `UNMAPPED`) y de diagnóstico. Ojo
  con el aplanado: varias cadenas son legítimamente ambiguas (`register`,
  `discourse`, `nuance`, `pragmatics`, `coherence`, `interaction`, `vocabulary`,
  `grammar`, `pronunciation`, `spelling`… pertenecen a VARIAS destrezas; ver
  `AMBIGUOUS_STRINGS`), así que el estado NUNCA resuelve una competencia con
  `MODALITY_OF`: eso es trabajo de `COMPETENCES_BY_MODALITY`, que es por
  modalidad.
- `COMPETENCES_BY_MODALITY` — competencias canónicas de cada modalidad,
  DERIVADAS de `curriculum.SUBSKILLS` y de los vocabularios de rúbrica ya
  declarados. Regla dura: toda cadena que el estado consuma pertenece a esta
  tupla; sin coincidencia el consumidor declara competencia `""` y **nunca**
  inventa una competencia que la evidencia no declare.

Decisiones declaradas (y por qué):

- `recall` → `vocabulary`: recuperar la forma desde su significado es práctica
  léxica sin canal de producción propio (`services.evidence` ya lo separa de
  `written_production`/`spoken_production`).
- `written_production` → `writing` y `spoken_production` → `speaking`: el canal
  SÍ está declarado en el ledger (`PRODUCTION_CHANNEL_SKILL`).
- `spontaneous_use` → `interaction`: es una CONDICIÓN (sin guion) más que una
  modalidad, y en esta app su único emisor es `chat`, que es TEXTO
  (`PRODUCTION_CHANNEL_SKILL["chat"] = "spontaneous_use"`). No se puede declarar
  producción oral sin canal oral, así que se sitúa como interacción escrita
  espontánea (CEFR: interacción en línea) y **no** como `speaking`.
- `interaction` y `mediation` se declaran SIN competencias: `mediation` no tiene
  descomposición declarada en el currículum e `interaction` aparece como
  SUBDESTREZA de `speaking`, no como destreza con subdestrezas propias. Se dejan
  vacías en lugar de inventarlas.
- `receptive` queda en `UNMAPPED` con su motivo: existe en `ASSESSMENT_MODES`
  para que la taxonomía admita el MCQ de Recognition el día que escriba
  evidencia, pero hoy es INFORMATIVO (V3.13) y no toca el ledger. Mapearlo
  sugeriría una modalidad medida que no existe.
- Discrepancia `LISTENING_SUBSKILLS` vs `SUBSKILLS["listening"]`: se resuelve
  como la UNIÓN, explícita y probada. El currículum declara la descomposición
  "can-do" de la destreza (validada por el cargador) y el motor de listening
  SERVIDO declara además subdestrezas que graba de verdad en
  `listening_attempts.skill` (`vocabulary`, `numbers`, `note_taking`,
  `prediction`, `sequencing`). Descartar cualquiera de las dos dejaría evidencia
  real fuera del estado o competencias curriculares sin puerta.

Módulo PURO y determinista: no hace I/O de alumno, no usa reloj ni aleatoriedad.
El único acceso a contenido declarado es `objective_competences_index()`, que lee
los JSON del currículum (contenido, no datos) y se cachea; el agregador puro lo
recibe como argumento.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from services.curriculum import CANONICAL_SKILLS, SUBSKILLS, load_all_levels
from services.evidence import LEXICAL_SKILLS, PRODUCTION_CHANNEL_SKILL
from services.listening import LISTENING_LAYERS, LISTENING_SUBSKILLS, SKILL_LAYER
from services.mastery import MASTERY_SKILLS
from services.pronunciation import PRONUNCIATION_CRITERIA
from services.speaking import SPEAKING_CRITERIA
from services.task_semantics import ASSESSMENT_MODES
from services.writing import WRITING_CRITERIA

# ---------------------------------------------------------------------------
# Eje mayor: MODALIDAD
# ---------------------------------------------------------------------------

# Modalidades canónicas del estado. Es el vocabulario del Student Model
# (`MASTERY_SKILLS`), declarado aquí como fuente única del eje de modalidad.
SKILL_MODALITIES: tuple[str, ...] = MASTERY_SKILLS

# Modalidad de cada skill del ledger LÉXICO (V3.38). El ledger no se toca: se
# MAPEA. `recall` es recuperación léxica y `spontaneous_use` una condición
# (interacción escrita espontánea), no canales de producción propios.
LEXICAL_MODALITY: dict[str, str] = {
    "recall": "vocabulary",
    "written_production": "writing",
    "spoken_production": "speaking",
    "spontaneous_use": "interaction",
}

# Totalidad en tiempo de import (fallo RUIDOSO, no silencioso): una skill del
# ledger léxico sin modalidad declarada dejaría evidencia real fuera del estado.
_MISSING_LEXICAL: tuple[str, ...] = tuple(
    skill for skill in LEXICAL_SKILLS if skill not in LEXICAL_MODALITY
)
if _MISSING_LEXICAL:
    raise RuntimeError(
        f"skills léxicas sin modalidad declarada: {_MISSING_LEXICAL}"
    )

# Canales de observación (`ASSESSMENT_MODES`): `written`/`spoken` sitúan la
# evidencia en su canal de producción; `receptive` está declarado sin emisor.
ASSESSMENT_MODE_MODALITY: dict[str, str] = {
    "written": "writing",
    "spoken": "speaking",
}

# ---------------------------------------------------------------------------
# Canal OBSERVADO del evento (V3.63, P1-02)
# ---------------------------------------------------------------------------

# Modalidad declarada de un evento por (SKILL DEL EVENTO, CANAL OBSERVADO). Hasta
# V3.62 la modalidad salía de un mapa duro skill → modalidad y `spontaneous_use`
# caía SIEMPRE en `interaction`, porque su único emisor era `chat` (TEXTO). Eso
# es correcto hoy, pero la auditoría de V3.62 (P1-02) avisa de que el día que
# exista conversación ORAL real el mismo concepto debe distinguir interacción
# escrita y oral por el CANAL realmente observado, no por la skill.
#
# El mapa se DERIVA de `LEXICAL_MODALITY` × `ASSESSMENT_MODE_MODALITY` (no se
# inventa vocabulario) y declara DOS entradas explícitas para `spontaneous_use`:
# escrito → `interaction` (el `chat`/transfer de hoy) y oral → `speaking` (el
# canal que V3.62 no podía expresar). El valor es una TUPLA para que el día que
# una actividad declare a la vez canal y eje se pueda expandir por declaración
# (nunca por reinterpretación); hoy toda entrada declara exactamente una.
MODALITIES_BY_ASSESSED_CHANNEL: dict[tuple[str, str], tuple[str, ...]] = {
    (skill, mode): (modality,)
    for skill, modality in LEXICAL_MODALITY.items()
    for mode in ASSESSMENT_MODE_MODALITY
}
MODALITIES_BY_ASSESSED_CHANNEL[("spontaneous_use", "written")] = ("interaction",)
MODALITIES_BY_ASSESSED_CHANNEL[("spontaneous_use", "spoken")] = ("speaking",)


def modalities_by_assessed_channel(skill: object, channel: object) -> tuple[str, ...]:
    """Modalidades declaradas de un evento por su skill y su CANAL observado.

    Sin canal declarado devuelve la tupla VACÍA: el llamador debe caer al mapa
    por skill (`LEXICAL_MODALITY`), que es la degradación EXACTA a V3.62. Nunca
    lanza.
    """
    key = (
        str(skill or "").strip().lower(),
        str(channel or "").strip().lower(),
    )
    return MODALITIES_BY_ASSESSED_CHANNEL.get(key, ())


# Motivo escrito de cada canal de observación declarado SIN modalidad. Un canal
# nuevo sin modalidad Y sin motivo rompe el import (no puede colarse en silencio).
_UNMAPPED_MODE_REASONS: dict[str, str] = {
    "receptive": (
        "canal declarado en ASSESSMENT_MODES sin emisor: el MCQ de Recognition "
        "es informativo (V3.13) y no escribe evidencia, así que no hay modalidad "
        "receptiva que medir"
    ),
}

# Cadenas declaradas en algún vocabulario del árbol que NO se mapean a ninguna
# modalidad, con su motivo escrito (mismo patrón que la nota de `receptive` de
# V3.13/V3.38).
UNMAPPED_REASONS: dict[str, str] = {
    mode: _UNMAPPED_MODE_REASONS[mode]
    for mode in ASSESSMENT_MODES
    if mode not in ASSESSMENT_MODE_MODALITY
}
UNMAPPED: tuple[str, ...] = tuple(UNMAPPED_REASONS)

# Subdestreza → destreza declarada del currículum (preciso, por destreza). Es la
# fuente del aplanado de `curriculum.SUBSKILLS` y la que un consumidor debe usar
# cuando SABE de qué destreza viene la cadena.
SUBSKILL_MODALITY: dict[str, dict[str, str]] = {
    skill: {raw: skill for raw in subskills}
    for skill, subskills in SUBSKILLS.items()
}

# Mapa PRECISO por vocabulario: nombre → {cadena: modalidad}. El test de
# totalidad recorre ESTE diccionario (importando los vocabularios reales), así
# que un vocabulario nuevo rompe el test en lugar de colarse.
MODALITY_BY_VOCABULARY: dict[str, dict[str, str]] = {
    "evidence.LEXICAL_SKILLS": dict(LEXICAL_MODALITY),
    "evidence.PRODUCTION_CHANNEL_SKILL": {
        channel: LEXICAL_MODALITY[skill]
        for channel, skill in PRODUCTION_CHANNEL_SKILL.items()
    },
    "curriculum.CANONICAL_SKILLS": {skill: skill for skill in CANONICAL_SKILLS},
    "mastery.MASTERY_SKILLS": {skill: skill for skill in MASTERY_SKILLS},
    "curriculum.SUBSKILLS": {
        raw: skill for skill, subskills in SUBSKILLS.items() for raw in subskills
    },
    "listening.LISTENING_SUBSKILLS": {raw: "listening" for raw in LISTENING_SUBSKILLS},
    "listening.SKILL_LAYER": {raw: "listening" for raw in SKILL_LAYER},
    "speaking.SPEAKING_CRITERIA": {raw: "speaking" for raw in SPEAKING_CRITERIA},
    "writing.WRITING_CRITERIA": {raw: "writing" for raw in WRITING_CRITERIA},
    "pronunciation.PRONUNCIATION_CRITERIA": {
        raw: "pronunciation" for raw in PRONUNCIATION_CRITERIA
    },
    "task_semantics.ASSESSMENT_MODES": dict(ASSESSMENT_MODE_MODALITY),
}

# Precedencia DECLARADA del aplanado: primero los vocabularios que declaran
# MODALIDAD (skills), luego los que declaran subdestrezas/criterios. En una
# colisión gana el primero (el aplanado es de diagnóstico, no la vía de
# resolución del estado).
_PLANAR_ORDER: tuple[str, ...] = (
    "mastery.MASTERY_SKILLS",
    "curriculum.CANONICAL_SKILLS",
    "evidence.LEXICAL_SKILLS",
    "evidence.PRODUCTION_CHANNEL_SKILL",
    "task_semantics.ASSESSMENT_MODES",
    "listening.LISTENING_SUBSKILLS",
    "listening.SKILL_LAYER",
    "speaking.SPEAKING_CRITERIA",
    "writing.WRITING_CRITERIA",
    "pronunciation.PRONUNCIATION_CRITERIA",
    "curriculum.SUBSKILLS",
)

# Cadenas AMBIGUAS del aplanado (pertenecen a más de una destreza del
# currículum). Se declaran para que la ambigüedad sea explícita y no un
# accidente del orden de recorrido.
AMBIGUOUS_STRINGS: tuple[str, ...] = tuple(
    sorted(
        raw
        for raw in {s for subskills in SUBSKILLS.values() for s in subskills}
        if sum(1 for subskills in SUBSKILLS.values() if raw in subskills) > 1
    )
)


def _planar() -> dict[str, str]:
    """Aplanado de `MODALITY_BY_VOCABULARY` con la precedencia declarada."""
    planar: dict[str, str] = {}
    for name in _PLANAR_ORDER:
        for raw, modality in MODALITY_BY_VOCABULARY.get(name, {}).items():
            planar.setdefault(raw, modality)
    return planar


MODALITY_OF: dict[str, str] = _planar()

# ---------------------------------------------------------------------------
# Eje menor: COMPETENCIA (por modalidad)
# ---------------------------------------------------------------------------


def _union(*groups: Iterable[str]) -> tuple[str, ...]:
    """Unión determinista (orden alfabético) de varios vocabularios declarados."""
    seen: set[str] = set()
    for group in groups:
        for raw in group:
            text = str(raw).strip().lower()
            if text:
                seen.add(text)
    return tuple(sorted(seen))


# Competencias canónicas por modalidad. Derivadas de los vocabularios ya
# declarados; `interaction`/`mediation` quedan vacías (ver docstring).
COMPETENCES_BY_MODALITY: dict[str, tuple[str, ...]] = {
    "vocabulary": _union(SUBSKILLS["vocabulary"]),
    "grammar": _union(SUBSKILLS["grammar"]),
    "pronunciation": _union(SUBSKILLS["pronunciation"], PRONUNCIATION_CRITERIA),
    "listening": _union(SUBSKILLS["listening"], LISTENING_SUBSKILLS),
    "speaking": _union(SUBSKILLS["speaking"], SPEAKING_CRITERIA),
    "reading": _union(SUBSKILLS["reading"]),
    "writing": _union(SUBSKILLS["writing"], WRITING_CRITERIA),
    "interaction": (),
    "mediation": (),
}


def canonical_competence(modality: object, raw: object) -> str:
    """Competencia canónica de `raw` dentro de `modality` ("" si no la declara).

    Normalización determinista (casefold + strip) y SIN fuzzy matching: una
    cadena desconocida devuelve "" para que el consumidor declare competencia
    vacía en lugar de inventar una.
    """
    key = str(modality or "").strip().lower()
    declared = COMPETENCES_BY_MODALITY.get(key, ())
    text = str(raw or "").strip().lower()
    if not text or text not in declared:
        return ""
    return text


def modality_for(raw: object) -> str:
    """Modalidad canónica de una cadena del vocabulario ("" si no se declara)."""
    return MODALITY_OF.get(str(raw or "").strip().lower(), "")


def competence_key(modality: object, competence: object) -> str:
    """Clave estable de la pareja (modalidad, competencia). Sin `hash()`."""
    left = str(modality or "").strip().lower()
    right = str(competence or "").strip().lower()
    return f"{left}:{right}"


# ---------------------------------------------------------------------------
# Eje DECLARADO de capas (V3.63, P2-12)
# ---------------------------------------------------------------------------

# Capas cognitivas declaradas por modalidad. Se REUTILIZA el vocabulario del
# motor de listening (`services.listening.LISTENING_LAYERS`) SIN añadir ni una
# cadena nueva: la auditoría de V3.62 (P2-12) pide distinguir la competencia
# OPERACIONAL (p. ej. `numbers`, que es decodificación) de la CURRICULAR, no
# renombrar nada. Hoy solo listening declara capas.
LAYERS_BY_MODALITY: dict[str, tuple[str, ...]] = {"listening": LISTENING_LAYERS}

# Competencia → capa, por modalidad (subconjunto DECLARADO de las competencias).
COMPETENCE_LAYERS_BY_MODALITY: dict[str, dict[str, str]] = {
    "listening": {
        competence: layer
        for competence, layer in SKILL_LAYER.items()
        if competence in _union(SUBSKILLS["listening"], LISTENING_SUBSKILLS)
    }
}

# Subdestrezas de listening DECLARADAS fuera del eje de capas, con motivo: son
# tareas de PRODUCCIÓN (`services.listening.skill_layer` devuelve `None`), no
# comprensión receptiva, así que reportarlas por capa mentiría sobre el proceso.
UNLAYERED_COMPETENCE_REASONS: dict[str, str] = {
    "dictation": (
        "tarea de PRODUCCIÓN (transcribir), no de comprensión receptiva: "
        "`services.listening.skill_layer` la declara fuera de la taxonomía"
    ),
    "shadowing": (
        "tarea de PRODUCCIÓN (repetir), no de comprensión receptiva: "
        "`services.listening.skill_layer` la declara fuera de la taxonomía"
    ),
}


def layer_for(modality: object, competence: object) -> str:
    """Capa declarada de una competencia ("" si la modalidad no la declara).

    Una competencia fuera del eje (o una modalidad sin capas) devuelve "": no se
    inventa una capa, se declara que no pertenece a ninguna.
    """
    key = str(modality or "").strip().lower()
    text = str(competence or "").strip().lower()
    return COMPETENCE_LAYERS_BY_MODALITY.get(key, {}).get(text, "")


def layers_for(modality: object) -> tuple[str, ...]:
    """Capas declaradas de una modalidad (tupla vacía si no declara ninguna)."""
    return LAYERS_BY_MODALITY.get(str(modality or "").strip().lower(), ())


@lru_cache(maxsize=1)
def objective_competences_index() -> dict[tuple[str, str], tuple]:
    """Índice `(level_id, objective_id) → (subskills, thresholds) del currículum`.

    Contenido DECLARADO (los JSON del currículum), no datos de alumno: el
    agregador puro recibe este índice como argumento y no lee ficheros. Las
    competencias de una fila de `academy_evidence` son las subdestrezas del
    objetivo RESTRINGIDAS a las declaradas por la modalidad de esa fila.
    """
    index: dict[tuple[str, str], tuple] = {}
    for level in load_all_levels():
        for objective in level.objectives():
            index[(level.level_id, objective.id)] = (
                tuple(objective.subskills),
                dict(objective.thresholds),
            )
    return index
