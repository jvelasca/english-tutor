"""Eje RA de V3.71: el manifiesto de runtime y offline (instrumento de solo lectura).

Fijan dos cosas distintas:

1. **Las dependencias de red están declaradas.** El instrumento
   (`scripts/audit_dossier.py::runtime_audit`) declara cada punto del backend que
   toca la red y de qué tipo es. Estos tests comprueban que la declaración no
   deriva del código y, sobre todo, que **no aparece una descarga nueva sin
   declarar**: si alguien añade `urlretrieve`/`urlopen` en código de producto, el
   CI falla y obliga a decidir si es una dependencia de Internet aceptable.

2. **La medición es reproducible y de solo lectura.** El par generado en
   `docs/audit/generated/` es determinista (por eso el sondeo de Ollama es una
   medición aparte, explícita) y el instrumento no escribe en `data/` ni en
   `curriculum/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import audit_dossier

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]

# Código de PRODUCTO: el que corre cuando el alumno usa la app. Una primitiva de
# red aquí es una dependencia de Internet del producto, no del instalador.
PRODUCT_DIRS = ("services", "routers", "repositories", "domain")

URL_PRIMITIVES = ("urlretrieve", "urlopen", "requests.get", "requests.post", "httpx.")

# Primitivas de red FUERA del código de producto: herramientas de desarrollo y el
# bootstrap de instalación, que sí puede necesitar Internet la primera vez.
# Un fichero nuevo aquí obliga a declararlo (y a decidir de qué lado está).
NON_PRODUCT_NETWORK_FILES = frozenset(
    {
        "download_models.py",  # bootstrap explícito de instalación
        "scripts/smoke_test.py",  # herramienta de desarrollo
        "scripts/audit_dossier.py",  # el propio instrumento (sonda de loopback)
        # V3.82: verificación end-to-end que arranca el backend en un puerto local
        # sobre una COPIA de la BD y levanta además un buzón SMTP local para
        # probar el correo de verdad. No es producto ni instalación: no lo
        # ejecuta nadie al usar la app, y sus conexiones son contra sí misma.
        "scripts/e2e_accounts_v382.py",
    }
)


def _declared_touchpoints() -> list[dict]:
    return [dict(t) for t in audit_dossier.RUNTIME_TOUCHPOINTS]


def _declared_files() -> set[str]:
    return {str(t["file"]) for t in _declared_touchpoints()}


def _files_with_url_primitives() -> dict[str, list[str]]:
    """Ficheros `.py` del backend con primitivas de red, relativos a `backend/`.

    Se excluye `tests/`: una primitiva de red en un test es un mock o un fixture,
    no una dependencia de Internet del producto ni de las herramientas.
    """
    hits: dict[str, list[str]] = {}
    for path in BACKEND.rglob("*.py"):
        rel = str(path.relative_to(BACKEND)).replace("\\", "/")
        if rel.startswith((".venv/", "tests/")) or "__pycache__" in rel:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found = [prim for prim in URL_PRIMITIVES if prim in text]
        if found:
            hits[rel] = found
    return hits


def _snapshot(directory: Path) -> dict[str, float]:
    if not directory.is_dir():
        return {}
    return {
        str(p.relative_to(ROOT)).replace("\\", "/"): p.stat().st_mtime
        for p in directory.rglob("*")
        if p.is_file()
    }


# --- 1. Las dependencias de red están declaradas ----------------------------


def test_todo_punto_de_red_declarado_sigue_en_el_codigo():
    """Anti-deriva: cada needle declarado debe existir todavía en su fichero."""
    drifted = [
        f"{t['file']}:{t['needle']}"
        for t in audit_dossier.network_touchpoints()
        if not t["match"]
    ]
    assert drifted == [], (
        "el manifiesto de runtime declara puntos de red que el código ya no "
        f"tiene (actualizar RUNTIME_TOUCHPOINTS): {drifted}"
    )


def test_no_hay_descargas_de_internet_sin_declarar_en_codigo_de_producto():
    """Si aparece una primitiva de red en producto, tiene que estar declarada."""
    declared = _declared_files()
    undeclared: dict[str, list[str]] = {}
    for rel, primitives in _files_with_url_primitives().items():
        if not rel.startswith(PRODUCT_DIRS):
            continue
        if rel in declared:
            continue
        undeclared[rel] = primitives

    assert undeclared == {}, (
        "hay código de producto con acceso a red que NO está declarado en "
        f"RUNTIME_TOUCHPOINTS (¿es una dependencia de Internet asumida?): "
        f"{undeclared}"
    )


def test_las_primitivas_de_red_fuera_de_producto_estan_declaradas():
    """Nada de red fuera de producto sin declararlo explícitamente."""
    declared = _declared_files()
    unexpected = [
        rel
        for rel in _files_with_url_primitives()
        if not rel.startswith(PRODUCT_DIRS)
        and rel not in declared
        and rel not in NON_PRODUCT_NETWORK_FILES
    ]
    assert unexpected == [], (
        "ficheros con acceso a red que no están clasificados como producto ni "
        f"como herramienta declarada: {unexpected}"
    )


def test_las_descargas_ocultas_conocidas_siguen_declaradas():
    """Las 3 dependencias NO declaradas al usuario son un hallazgo del dossier.

    Si alguna deja de existir (p. ej. se cachea el fallo de forma persistente o
    se empaqueta la voz), este test obliga a actualizar el dossier en lugar de
    dejar que el hallazgo se quede obsoleto en silencio.
    """
    hidden = {
        str(t["file"])
        for t in _declared_touchpoints()
        if t["hidden"] and t["kind"] == "internet"
    }
    assert hidden == {
        "services/tts.py",
        "routers/voz.py",
        "services/stt.py",
    }, f"las dependencias ocultas declaradas cambiaron: {hidden}"


def test_el_manifiesto_cubre_todas_las_voces_por_defecto():
    """Una voz por defecto nueva no puede quedar fuera del manifiesto offline."""
    import config

    voice_ids = set(config.DEFAULT_VOICES.values())
    manifest_ids = {a["id"] for a in audit_dossier.model_manifest()}

    for voice_id in voice_ids:
        for suffix in (".onnx", ".onnx.json"):
            expected = f"piper:{voice_id}{suffix}"
            assert expected in manifest_ids, (
                f"la voz por defecto {voice_id} no declara {suffix} en el "
                "manifiesto offline"
            )


# --- 2. La medición es reproducible y de solo lectura -----------------------


def test_el_manifiesto_es_determinista():
    """Dos mediciones seguidas deben producir el mismo markdown, byte a byte."""
    first = audit_dossier.runtime_audit_markdown(audit_dossier.runtime_audit())
    second = audit_dossier.runtime_audit_markdown(audit_dossier.runtime_audit())
    assert first == second


def test_el_sondeo_de_ollama_no_entra_en_la_medicion_determinista():
    """El sondeo en vivo es aparte: si entrara, el par generado no sería estable."""
    assert audit_dossier.runtime_audit()["ollama"] is None
    assert audit_dossier.runtime_audit(probe_ollama=False)["ollama"] is None
    markdown = audit_dossier.runtime_audit_markdown(audit_dossier.runtime_audit())
    assert "no sondeado" in markdown


def test_el_instrumento_no_escribe_en_data_ni_en_curriculum():
    """Solo lectura: el instrumento no puede tocar datos ni contenido."""
    watched = (BACKEND / "data", ROOT / "curriculum")
    before = {str(d): _snapshot(d) for d in watched}

    audit_dossier.runtime_audit()
    audit_dossier.runtime_audit_markdown(audit_dossier.runtime_audit())

    after = {str(d): _snapshot(d) for d in watched}
    assert before == after, "runtime-audit escribió en data/ o en curriculum/"


@pytest.mark.parametrize("kind", ("loopback", "lan", "internet"))
def test_los_tipos_de_punto_de_red_son_los_declarados(kind: str):
    """`kind` es un conjunto cerrado: sin valores libres que nadie interprete."""
    kinds = {str(t["kind"]) for t in _declared_touchpoints()}
    assert kinds <= {"loopback", "lan", "internet"}
    assert kind in kinds
