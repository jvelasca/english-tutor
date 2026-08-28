"""Marco de descriptores Can-Do CEFR (Curriculum 2.0).

Carga y valida `curriculum/cefr_descriptors.json`: la escalera CEFR completa
(Pre-A1, A1, A2, A2+, B1, B1+, B2, B2+, C1, C2) con descriptores "Can-Do" por
dimensión (listening, speaking, reading, writing, grammar, vocabulary,
pronunciation, interaction y mediation).

El CEFR moderno (Companion Volume) reconoce explícitamente las bandas "plus"
(A2+, B1+, B2+) y añade la **mediación** y la **interacción** como dimensiones
comunicativas de primer nivel. Este marco es **contenido**, no lógica: los
descriptores viven solo en el JSON y aquí se cargan (Pydantic) y se consultan.

Separación de responsabilidades:
- `services.curriculum` define la progresión de **cursos** (`CEFR_ORDER`, A1..C2)
  y el contenido por objetivo.
- Este módulo describe la **escalera de competencia** continua, incluyendo bandas
  que no tienen curso propio (Pre-A1 y las "plus"), para que la estimación pueda
  expresar matices (p. ej. "B1+") sin alterar la progresión de matrícula.

No certifica niveles CEFR (el Consejo de Europa no valida exámenes): es una
referencia interna alineada al marco para preparación y evaluación.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from services.curriculum import CURRICULUM_DIR

# Escalera CEFR completa, de menor a mayor competencia. Los ids en minúscula son
# la identidad estable de cada banda; `label` es la etiqueta de presentación.
CEFR_LADDER: tuple[str, ...] = (
    "pre-a1",
    "a1",
    "a2",
    "a2+",
    "b1",
    "b1+",
    "b2",
    "b2+",
    "c1",
    "c2",
)

# Posición numérica continua de cada banda (A1=1.0 … C2=6.0; Pre-A1 < A1 y las
# bandas "plus" en el punto medio de la banda principal). Permite expresar
# "B1+" como 3.5 en lugar de redondear a una etiqueta discreta.
BAND_NUMERIC: dict[str, float] = {
    "pre-a1": 0.5,
    "a1": 1.0,
    "a2": 2.0,
    "a2+": 2.5,
    "b1": 3.0,
    "b1+": 3.5,
    "b2": 4.0,
    "b2+": 4.5,
    "c1": 5.0,
    "c2": 6.0,
}

# Dimensiones comunicativas del descriptor (orden canónico de presentación).
CEFR_DIMENSIONS: tuple[str, ...] = (
    "listening",
    "speaking",
    "reading",
    "writing",
    "grammar",
    "vocabulary",
    "pronunciation",
    "interaction",
    "mediation",
)


class CefrBand(BaseModel):
    id: str
    label: str
    numeric: float
    title: str
    description: str = ""
    can_do: dict[str, list[str]] = Field(default_factory=dict)


class CefrFramework(BaseModel):
    version: str
    dimensions: dict[str, str]
    bands: list[CefrBand]


# Cache a nivel de módulo: el contenido es estático durante el proceso.
_FRAMEWORK_CACHE: CefrFramework | None = None


def load_framework() -> CefrFramework:
    """Carga y valida el marco de descriptores (cacheado a nivel de módulo)."""
    global _FRAMEWORK_CACHE
    if _FRAMEWORK_CACHE is None:
        path = CURRICULUM_DIR / "cefr_descriptors.json"
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        _FRAMEWORK_CACHE = CefrFramework.model_validate(data)
    return _FRAMEWORK_CACHE


def bands() -> list[CefrBand]:
    """Bandas de la escalera en orden de competencia (Pre-A1 → C2)."""
    return load_framework().bands


def dimensions() -> dict[str, str]:
    """Mapa `dimension_id → label` en el orden canónico del framework."""
    dims = load_framework().dimensions
    return {d: dims.get(d, d.replace("_", " ").title()) for d in CEFR_DIMENSIONS}


def band_by_id(band_id: str) -> CefrBand | None:
    """Banda por id (p. ej. `b1+`), o None si no existe."""
    for band in bands():
        if band.id == band_id:
            return band
    return None


def band_for_numeric(numeric: float) -> str:
    """Banda de la escalera más cercana a un nivel continuo (0..6).

    Redondea al centro de banda más próximo; en empate gana la banda más baja
    (conservador). Permite que una estimación 3.2 se exprese como `b1` y una 3.6
    como `b1+`, en lugar de forzar la etiqueta discreta A1..C2.
    """
    n = max(0.0, min(6.0, numeric))
    return min(CEFR_LADDER, key=lambda b: abs(BAND_NUMERIC[b] - n))


def validate_framework() -> list[str]:
    """Invariantes estructurales del marco; lista vacía = válido.

    Cubre: una banda por cada id de `CEFR_LADDER`, `numeric` coherente con
    `BAND_NUMERIC`, todas las dimensiones declaradas con al menos un descriptor,
    e ids/labels no vacíos.
    """
    errors: list[str] = []
    fw = load_framework()
    by_id = {b.id: b for b in fw.bands}

    if set(by_id) != set(CEFR_LADDER):
        errors.append(
            f"bandas del JSON {sorted(by_id)} no coinciden con CEFR_LADDER"
        )
    for band in fw.bands:
        if not band.id or not band.label:
            errors.append("banda sin id o label")
        if band.numeric != BAND_NUMERIC.get(band.id):
            errors.append(
                f"banda {band.id} numeric={band.numeric} != "
                f"{BAND_NUMERIC.get(band.id)}"
            )
        for dim in CEFR_DIMENSIONS:
            if dim not in fw.dimensions:
                errors.append(f"dimensión {dim} no declarada")
                continue
            if not band.can_do.get(dim):
                errors.append(f"banda {band.id} sin descriptor para {dim}")
    return errors
