"""AE-06 (V3.72): un solo módulo de fronteras de banda y decisión declarada.

Hallazgo AE-06 de la auditoría pedagógica V3.70 (`docs/audit/AE-PED-INSTRUMENTOS.md`):
los umbrales de banda estaban **triplicados** (`adaptive.numeric_to_level`,
`academy.theta_to_level`, `cefr.heuristic_band`) y la escalera declaraba sub-bandas
`+` y `pre-a1` que "nadie emitía".

Cierre de V3.72:

- el corte vive **solo** en `services/cefr.py` (`BAND_BOUNDARIES` +
  `level_for_numeric`) y los tres estimadores delegan en él; la equivalencia en
  toda la rejilla (0 desacuerdos) se preserva y sigue fijada por
  `test_ped_instruments_v370.py`;
- decisión sobre `+` y `pre-a1`: **`pre-a1` tiene emisor** (banda del estimado sin
  evidencia: `adaptive.estimated_level`) y se conserva. Las **sub-bandas `+` se
  retiran de la emisión del producto** —ni la etiqueta ni la posición de la
  escalera las emiten— y se conservan como **contenido de descriptores** (CEFR
  Companion Volume) y como capacidad del mapeador de la escalera
  (`band_for_numeric`, que sí las expresa cuando se le pide). Motivo: afirmaban
  media banda de precisión que la evidencia no sostiene y, además, su centro caía
  a caballo del corte de etiqueta (un numeric 3.6 se etiquetaba B2 y marcaba B1+).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from domain import academy as academy_domain
from main import app
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services import adaptive, cefr, cefr_descriptors

BACKEND = Path(__file__).resolve().parents[1]
SERVICES = BACKEND / "services"
DOCS = BACKEND.parent / "docs"

# Rejilla del eje continuo (0.5 = centro Pre-A1 … 6.0 = C2), paso 0.1.
GRID = [round(0.5 + 0.1 * i, 2) for i in range(56)]

# La tabla de fronteras, literal, y una reimplementación por comparaciones.
_BOUNDARIES_LITERAL = re.compile(
    r"\(\s*1\.5\s*,\s*2\.5\s*,\s*3\.5\s*,\s*4\.5\s*,\s*5\.5\s*\)"
)
_BOUNDARY_COMPARISON = re.compile(r"<\s*[1-5]\.5\s*:")


def _service_sources() -> dict[str, str]:
    return {
        p.relative_to(BACKEND).as_posix(): p.read_text(encoding="utf-8")
        for p in SERVICES.glob("*.py")
    }


def test_el_dossier_ae_declara_el_cierre_y_la_decision() -> None:
    """La decisión no vive solo en el código: el dossier AE y PARKED la declaran."""
    dossier = " ".join(
        (DOCS / "audit" / "AE-PED-INSTRUMENTOS.md").read_text(encoding="utf-8").split()
    )
    assert "AE-06 · umbrales de banda — **cerrado**" in dossier
    assert "se retiran de la emisión" in dossier
    parked = " ".join(
        (DOCS / "audit" / "PARKED.md").read_text(encoding="utf-8").split()
    )
    assert "AE-06" in parked
    assert (
        "las `+` se retiran de la emisión y quedan como contenido de descriptores"
        in parked
    )


def test_las_fronteras_de_banda_se_declaran_en_un_solo_modulo() -> None:
    """Solo `services/cefr.py` declara el corte de media banda.

    Se lee el código como texto: si alguien vuelve a escribir la tabla de fronteras
    —o la reimplementa con comparaciones `x < 2.5`— este candado lo dice.
    """
    sources = _service_sources()
    declared = sorted(
        name for name, text in sources.items() if _BOUNDARIES_LITERAL.search(text)
    )
    assert declared == ["services/cefr.py"], (
        f"la tabla de fronteras de banda está duplicada: {declared}"
    )
    reimplemented = sorted(
        name for name, text in sources.items() if _BOUNDARY_COMPARISON.search(text)
    )
    assert reimplemented == [], (
        f"hay una reimplementación del corte de banda en: {reimplemented}"
    )


def test_el_corte_unico_cubre_la_rejilla_y_los_tres_estimadores() -> None:
    assert cefr.BAND_BOUNDARIES == (1.5, 2.5, 3.5, 4.5, 5.5)
    assert len(cefr.CEFR_LEVELS) == len(cefr.BAND_BOUNDARIES) + 1
    for numeric in GRID:
        score = cefr.score_for_numeric(numeric)
        assert (
            adaptive.numeric_to_level(numeric)
            == academy_svc.theta_to_level(numeric)
            == cefr.heuristic_band(score)
            == cefr.level_for_numeric(numeric)
        ), numeric
    # `score_for_numeric` es la inversa de `numeric_for_score` dentro del tramo
    # etiquetable (1.0 = A1 .. 6.0 = C2); por debajo manda el suelo Pre-A1.
    for numeric in [n for n in GRID if n >= 1.0]:
        score = cefr.score_for_numeric(numeric)
        assert abs(cefr.numeric_for_score(score) - numeric) < 1e-9


def test_las_etiquetas_nunca_emiten_subbandas_plus() -> None:
    """Los estimadores de etiqueta son A1..C2 discretos: ni `+` ni `Pre-A1`."""
    emitted = {cefr.level_for_numeric(numeric) for numeric in GRID}
    assert emitted == set(cefr.CEFR_LEVELS)
    assert not {level for level in emitted if level.endswith("+")}
    assert cefr.heuristic_band(None) == "—"


def test_las_subbandas_plus_siguen_como_contenido_de_la_escalera() -> None:
    """Retiradas de la emisión, pero no borradas: son descriptores del marco."""
    for band in ("pre-a1", "a2+", "b1+", "b2+"):
        assert band in cefr_descriptors.CEFR_LADDER, band
        assert cefr_descriptors.band_by_id(band) is not None, band
        assert cefr_descriptors.band_for_numeric(
            cefr_descriptors.BAND_NUMERIC[band]
        ) == band, band


class _MasteryRecord:
    """Doble mínimo de `MasteryRecord` (solo se usa `.model_dump()`)."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self) -> dict:
        return self._payload


def test_la_escalera_marca_la_etiqueta_discreta_del_estimado(
    monkeypatch, tmp_path
) -> None:
    """El numeric 3.6 se etiqueta B2 y marca `b2`: nunca `b1+` (AE-06)."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]

    async def _fake_student_model(_user_id: str) -> dict:
        return {
            "estimated_level": "B2",
            "estimated_numeric": 3.6,
            "mastery": [
                _MasteryRecord(
                    {
                        "skill": "listening",
                        "score": 0.8,
                        "confidence": 0.9,
                        "evidence_count": 5,
                    }
                )
            ],
        }

    monkeypatch.setattr(academy_domain, "build_student_model", _fake_student_model)
    with TestClient(app) as client:
        body = client.get("/api/academy/cefr-ladder", params={"user_id": uid}).json()

    assert body["estimated_numeric"] == 3.6
    assert body["estimated_band"] == "b2"
    current = [b["id"] for b in body["bands"] if b["is_current"]]
    assert current == ["b2"], current
    # Coherencia etiqueta ↔ posición: la misma banda.
    assert (
        cefr.level_for_numeric(body["estimated_numeric"]).lower()
        == body["estimated_band"]
    )
    # La capacidad de la escalera sigue expresando la sub-banda cuando se le pide.
    assert cefr_descriptors.band_for_numeric(3.6) == "b1+"

