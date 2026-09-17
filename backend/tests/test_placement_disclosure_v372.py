"""AE-04 (V3.72): el placement declara **qué mide**, y el candado avisa en cuanto
exista una superficie que lo muestre.

Hallazgo AE-04 de la auditoría pedagógica V3.70
(`docs/audit/AE-PED-INSTRUMENTOS.md`): el placement usa opción múltiple también
para listening/speaking/writing/pronunciation, de modo que mide
**reconocimiento/meta-lenguaje**, no producción —lo declara el propio modelo en
`PlacementTest`—, pero eso no se le dice a nadie que vea el resultado.

Estado real verificado en V3.72 (y fijado por estos tests):

- **no existe superficie**: `frontend/src/api/academy.ts` expone el placement y
  **ningún componente lo consume** (la app no ejecuta ni muestra la nivelación);
- por tanto la divulgación va **en el instrumento** (contenido + contrato: la
  `description` que devuelve `GET /api/academy/placement`), y el candado
  `test_ninguna_superficie_consume_el_placement_sin_divulgarlo` **falla** el día
  que alguien conecte una pantalla, obligando a divulgar allí la limitación.

No se inventa una pantalla de nivelación: el hallazgo queda **re-declarado** para
la fase en la que el placement tenga superficie (V4.0.x, ver `PARKED.md`).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.curriculum import PlacementTest, load_assessments

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND_SRC = BACKEND.parent / "frontend" / "src"
PLACEMENT_API = FRONTEND_SRC / "api" / "academy.ts"

# Consumo real del placement en la UI (no la capa `api/`).
_PLACEMENT_CALLS = re.compile(
    r"\b(getPlacement|submitPlacement|startAdaptivePlacement|nextAdaptivePlacement)\s*\("
)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def test_el_instrumento_declara_que_mide_reconocimiento_y_no_produccion() -> None:
    """La declaración vive en el contenido del instrumento, no en un docstring."""
    placement = load_assessments().placement
    text = _normalized(f"{placement.title} {placement.description}").lower()
    assert "recognition" in text, placement.description
    assert "production" in text, placement.description
    assert "not" in text or "does not" in text, placement.description


def test_el_modelo_del_instrumento_declara_la_limitacion() -> None:
    doc = _normalized(PlacementTest.__doc__ or "").lower()
    assert "reconocimiento o meta-lenguaje" in doc
    assert "no captura audio ni producción libre" in doc


def test_la_api_del_placement_expone_la_declaracion(monkeypatch, tmp_path) -> None:
    """Quien consuma el contrato recibe la limitación con el propio instrumento."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]

    with TestClient(app) as client:
        body = client.get("/api/academy/placement", params={"user_id": uid}).json()

    assert body["items"], "el placement no sirve ítems"
    description = _normalized(body["description"]).lower()
    assert "recognition" in description
    assert "production" in description


def test_ninguna_superficie_consume_el_placement_sin_divulgarlo() -> None:
    """Candado-tripwire: si el placement gana pantalla, hay que divulgar allí.

    Mientras no exista superficie, la divulgación del instrumento (arriba) es todo
    lo que el producto puede honestamente afirmar. Cuando alguien conecte la
    nivelación a la UI, este test falla a propósito: el trabajo es añadir en esa
    pantalla que el test mide reconocimiento/meta-lenguaje y no producción.
    """
    consumers: list[str] = []
    for path in FRONTEND_SRC.rglob("*.ts*"):
        if "node_modules" in path.parts or ".test." in path.name:
            continue
        if path == PLACEMENT_API:
            continue
        if _PLACEMENT_CALLS.search(path.read_text(encoding="utf-8")):
            consumers.append(path.relative_to(BACKEND.parent).as_posix())
    assert consumers == [], (
        "el placement ya tiene superficie en la UI: "
        f"{consumers}. Divulga en ella que mide reconocimiento/meta-lenguaje y no "
        "producción (AE-04) o retira el consumo; después actualiza este candado y "
        "`docs/audit/AE-PED-INSTRUMENTOS.md`."
    )
