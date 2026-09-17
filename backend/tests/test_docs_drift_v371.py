"""Deriva documental de gates/CI (eje RE) y runtime de producto (eje RC) (V3.71).

Cada test fija **una** de las derivas corregidas en los ejes RE y RC y **falla si
vuelve a aparecer**, de modo que el CI avisa en lugar de dejar que la
documentación se separe del código otra vez. La fuente de verdad es siempre el
**código** (`backend/config.py`, `launcher/core.py`, `.github/workflows/ci.yml`)
y las **medidas reales** (ficheros del launcher, filas de la matriz de
dispositivos), nunca la documentación.

Derivas fijadas:
1. `docs/PREMISAS.md` / `README.md` declaraban `qwen3.5:9b` como modelo por
   defecto, cuando `config.py` fija `llama3.1:8b` y **veta** `qwen3.5:9b`.
2. `docs/ARQUITECTURA.md` no listaba `browser_cookies.py`, `state_store.py`,
   `allow-firewall.ps1` ni el módulo de tests `test_state_store`.
3. Los **75 tests** del launcher no se ejecutaban en CI y `docs/BETA_GATES.md`
   declaraba «CI completa» igualmente.
4. `docs/BETA_GATES.md` declaraba verde la matriz de dispositivos mientras
   `docs/DEVICE_MATRIX.md` estaba 10/10 en ⬜.
5. (RC) Nadie declaraba **quién sirve la UI** ni que `frontend/dist` no lo servía
   nadie: el runtime de producto era el dev server de Vite, y Node + npm eran
   requisito de **ejecución**. **V3.72 (eje UA) cerró RC-01** e invirtió esa
   frontera; sus candados vivos están en `test_docs_drift_v372.py`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LAUNCHER = ROOT / "launcher"
LAUNCHER_TESTS = LAUNCHER / "tests"
CI = ROOT / ".github" / "workflows" / "ci.yml"

# Marcador de la corrección: si se borra, la nota deja de ser verificable.
NOTA_V371 = "corrección de derivas documentales"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ci_jobs() -> dict:
    return yaml.safe_load(_read(CI))["jobs"]


def _job_text(job: dict) -> str:
    """Todo el texto del job (steps incluidos) para buscarlo literalmente."""
    return yaml.safe_dump(job, allow_unicode=True, sort_keys=False)


def _launcher_sources() -> list[str]:
    return sorted(
        p.name
        for p in LAUNCHER.iterdir()
        if p.is_file() and p.suffix in {".py", ".ps1"}
    )


def _launcher_test_modules() -> list[str]:
    return sorted(p.stem for p in LAUNCHER_TESTS.glob("test_*.py"))


def _count_launcher_tests() -> int:
    # No hay `parametrize` en el launcher: 1 `def test_` == 1 test.
    return sum(
        line.lstrip().startswith("def test_")
        for path in LAUNCHER_TESTS.glob("test_*.py")
        for line in _read(path).splitlines()
    )


def _device_matrix_rows() -> list[list[str]]:
    """Filas de la tabla de `## Matriz` (sin cabecera ni separador)."""
    section = _read(DOCS / "DEVICE_MATRIX.md")
    section = section.split("## Matriz", 1)[1].split("\n## ", 1)[0]
    rows: list[list[str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not any(cells) or set("".join(cells)) <= set("-: "):
            continue
        if cells[0] == "Dispositivo":
            continue
        rows.append(cells)
    return rows


def _beta_gates_row(prefix: str) -> str:
    matches = [
        line
        for line in _read(DOCS / "BETA_GATES.md").splitlines()
        if line.startswith(prefix)
    ]
    assert len(matches) == 1, (
        f"esperaba 1 fila '{prefix}' en BETA_GATES, hay {len(matches)}"
    )
    return matches[0]


# --- Deriva 1: modelo por defecto (docs vs config.py) -----------------------


def test_docs_declaran_el_modelo_por_defecto_real():
    """`config.py` es la fuente de verdad: las docs deben nombrar su modelo."""
    import config  # `backend/tests/conftest.py` ya puso `backend/` en sys.path

    for doc in (DOCS / "PREMISAS.md", ROOT / "README.md"):
        assert config.DEFAULT_MODEL in _read(doc), (
            f"{doc.name} no nombra el modelo por defecto real ({config.DEFAULT_MODEL})"
        )


def test_docs_no_presentan_un_modelo_vetado_como_por_defecto():
    import config

    assert config.DEFAULT_MODEL not in config.UNUSABLE_MODELS

    for doc in (DOCS / "PREMISAS.md", ROOT / "README.md"):
        for line in _read(doc).splitlines():
            if "por defecto" not in line.lower():
                continue
            for model in config.UNUSABLE_MODELS:
                if model in line and "vetado" not in line.lower():
                    raise AssertionError(
                        f"{doc.name} presenta {model} como modelo por defecto "
                        f"(está vetado en config.UNUSABLE_MODELS): {line.strip()}"
                    )


# --- Deriva 2: árbol del launcher en ARQUITECTURA ---------------------------


def test_arquitectura_documenta_los_ficheros_del_launcher():
    text = _read(DOCS / "ARQUITECTURA.md")
    missing = [name for name in _launcher_sources() if name not in text]
    assert missing == [], (
        f"ARQUITECTURA.md no documenta ficheros del launcher: {missing}"
    )


def test_arquitectura_documenta_los_tests_del_launcher():
    text = _read(DOCS / "ARQUITECTURA.md")
    missing = [stem for stem in _launcher_test_modules() if stem not in text]
    assert missing == [], f"ARQUITECTURA.md no documenta módulos de test: {missing}"

    count = _count_launcher_tests()
    assert str(count) in text, (
        f"ARQUITECTURA.md no declara el número real de tests del launcher ({count})"
    )


# --- Deriva 3: el launcher, en CI -------------------------------------------


def test_ci_ejecuta_los_tests_y_el_lint_del_launcher():
    jobs = _ci_jobs()
    assert "launcher" in jobs, (
        "el CI no tiene job `launcher` (los 75 tests solo correrían en local)"
    )

    job = jobs["launcher"]
    assert job["defaults"]["run"]["working-directory"] == "launcher"
    text = _job_text(job)
    assert "pytest tests/" in text, "el job `launcher` no ejecuta los tests"
    assert "ruff check" in text, "el job `launcher` no ejecuta el lint"


def test_el_job_del_launcher_pinea_las_mismas_versiones_que_el_backend():
    """La promesa «mismas versiones que el gate de backend» debe ser verificable."""
    dev = _read(ROOT / "backend" / "requirements-dev.txt")
    pins = [
        line.strip()
        for line in dev.splitlines()
        if line.strip().startswith(("pytest==", "ruff=="))
    ]
    assert len(pins) == 2, (
        f"esperaba pins de pytest y ruff en requirements-dev.txt: {pins}"
    )

    text = _job_text(_ci_jobs()["launcher"])
    for pin in pins:
        assert pin in text, f"el job `launcher` no usa el pin del backend: {pin}"


# --- Deriva 3 y 4: gates honestos -------------------------------------------


def test_beta_gates_declara_el_job_del_launcher_y_su_correccion():
    row = _beta_gates_row("| CI completa ")
    assert "launcher" in row, "BETA_GATES declara «CI completa» sin el job del launcher"
    assert "launcher" in _ci_jobs(), "BETA_GATES anuncia un job que no existe en ci.yml"

    assert NOTA_V371 in _read(DOCS / "BETA_GATES.md"), (
        "BETA_GATES.md perdió la nota de corrección de derivas de V3.71"
    )


def test_beta_gates_no_declara_verde_una_matriz_de_dispositivos_pendiente():
    rows = _device_matrix_rows()
    assert len(rows) == 10, (
        f"la matriz de dispositivos debería tener 10 filas, tiene {len(rows)}"
    )

    pendientes = [row for row in rows if all(cell in ("⬜", "") for cell in row[2:])]
    verde = "✅" in _beta_gates_row("| Matriz de dispositivos ")

    assert verde == (len(pendientes) < len(rows)), (
        f"BETA_GATES dice {'verde' if verde else 'pendiente'} y la matriz tiene "
        f"{len(pendientes)}/{len(rows)} filas sin probar"
    )


# --- Deriva RC: quién sirve la UI (V3.71, eje RC) ---------------------------
#
# V3.72 (eje UA) cerró RC-01: el backend **sí** sirve `frontend/dist` y el
# launcher **compila** el artefacto en vez de arrancar el dev server de Vite. Los
# candados de V3.71 afirmaban la frontera **contraria** («nadie sirve el dist»,
# «el launcher arranca `npm run dev`»), así que se sustituyen por los de
# `backend/tests/test_docs_drift_v372.py`, que fijan la frontera actual. Se dejan
# aquí estas constantes para que la suite siga siendo el índice de los candados
# vivos por release en vez de un fichero que miente.

