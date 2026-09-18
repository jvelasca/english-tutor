"""Cadena de suministro del CI: pines, auditoría y Dependabot (VG-N5, V3.75).

La auditoría de V3.73 lo dejó como hallazgo P3 (`docs/audit/VERIFICACION-
SEGURIDAD-V373.md`, VG-N5): *«sin escaneo de dependencias en CI ni Dependabot, y
las Actions van fijadas por etiqueta mayor (`@v4`/`@v5`), no por SHA»*. Un `@v4`
es una referencia **móvil**: si la acción publica otro código con la misma
etiqueta, el CI ejecuta otra cosa sin que cambie nada del repositorio.

Esto no comprueba que las dependencias estén sanas (eso lo hace el job
`deps-audit` ejecutándose de verdad); comprueba que el **instrumento** sigue
siendo el que se aprobó y que nadie lo desmonta en silencio.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ci() -> dict:
    return yaml.safe_load(_read(CI))


def _uses() -> list[str]:
    return [
        line.split("uses:", 1)[1].strip()
        for line in _read(CI).splitlines()
        if "uses:" in line
    ]


def test_todas_las_actions_van_fijadas_por_sha():
    pines = {}
    sueltas = []
    for use in _uses():
        _, _, ref = use.partition("@")
        sha = ref.split()[0] if ref else ""
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha.lower()):
            pines[sha] = pines.get(sha, 0) + 1
        else:
            sueltas.append(use)
    assert sueltas == [], (
        f"Actions sin SHA (referencia móvil reintroducida): {sueltas}"
    )
    assert len(pines) == 3, (
        "se esperaban las 3 Actions fijadas (checkout, setup-python, setup-node); "
        f"hay {len(pines)}: {sorted(pines)}. Si se añade una acción nueva, fíjala "
        "por SHA y actualiza este número."
    )


def test_el_ci_solo_lee_el_repositorio():
    """Permisos mínimos: ningún job necesita escribir en el repo."""
    assert _ci()["permissions"] == {"contents": "read"}


def test_existe_el_job_de_auditoria_de_dependencias():
    job = _ci()["jobs"]["deps-audit"]
    texto = yaml.safe_dump(job, allow_unicode=True, sort_keys=False)

    assert "pip_audit -r requirements.txt" in texto, (
        "el job de auditoría no audita el árbol de producto del backend"
    )
    assert "npm audit --omit=dev --audit-level=high" in texto, (
        "el job de auditoría no audita las dependencias de producción del frontend"
    )
    assert job.get("continue-on-error") is not True, (
        "el job de auditoría dejó de ser bloqueante sin registrar la deuda; si es "
        "deliberado, documenta el criterio en docs/audit/PARKED.md (VG-N5)"
    )


def test_dependabot_cubre_los_tres_ecosistemas():
    data = yaml.safe_load(_read(DEPENDABOT))
    pares = {(u["package-ecosystem"], u["directory"]) for u in data["updates"]}

    assert ("pip", "/backend") in pares, "Dependabot no vigila el backend"
    assert ("npm", "/frontend") in pares, "Dependabot no vigila el frontend"
    assert ("github-actions", "/") in pares, (
        "sin `github-actions` los pines por SHA se quedan viejos para siempre"
    )
