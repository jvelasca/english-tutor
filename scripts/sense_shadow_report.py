"""Informe del veredicto sense-aware de Listening (V3.94, solo lectura).

V3.93 cableó el Sense Resolver para **guardar el veredicto**
(`sense_key`/`sense_match`/`sense_reason`) en la tabla
`listening_difficulty_evidence`. V3.94 lo **aplica** (fase ENFORCE): un `mismatch`
PROBADO no sube la carta y se registra como exposición; todo lo demás conserva la
evidencia de V3.92. Este informe responde, con datos reales, a la pregunta que
gobierna esa política:

    ¿cuánta evidencia de dificultad SOBREVIVIRÍA con `allows_difficulty_evidence`?

Qué mide:

1. **Cobertura del veredicto**: cuántas filas llevan veredicto (post-V3.93) y
   cuántas son anteriores (sin veredicto, que el informe no proyecta: la política
   se aplica hacia delante, no reescribe el pasado).
2. **Reparto `matched` / `mismatch` / `ambiguous`** y, dentro de `ambiguous`, la
   razón (`declared:none`, `alternatives:none`, `tie`…). El caso dominante suele ser
   `declared:none` —palabras que el alumno nunca declaró con qué acepción—.
3. **Proyección ENFORCE con la política REAL** (V3.94): qué evidencia se conservaría
   y qué se suprimiría, aplicando la MISMA `allows_difficulty_evidence` que decide en
   producción. Desde V3.94 solo un `mismatch` PROBADO suprime; `declared:none` y
   `ambiguous` se conservan. Es una proyección sobre lo ya registrado, no una promesa.
   V3.94.1 añade el contador `possible_mismatch` (`gloss:other:weak`, un solo token):
   señales a favor de otra acepción que NO suprimen evidencia, para medir cuántos
   falsos positivos habría producido el umbral anterior.

El script es de LECTURA: abre SQLite en modo `mode=ro` (con repliegue si el WAL lo
impide) y no ejecuta ningún `INSERT`, `UPDATE` ni `DELETE`.

Uso:

    python scripts/sense_shadow_report.py
    python scripts/sense_shadow_report.py --json
    python scripts/sense_shadow_report.py --db ruta/a/otra.db

Códigos de salida: 0 = informe emitido; 2 = no se pudo leer la BD.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# El script vive en <repo>/scripts/, así que la raíz es el padre de `scripts`.
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "tutor.db"

# La política de decisión vive en el BACKEND y este informe usa LA MISMA función que
# decide en producción: una copia local podría desviarse de la verdad y proyectar
# algo que la app no hace.
sys.path.insert(0, str(ROOT / "backend"))
from services.sense_context import REASON_GLOSS_OTHER_WEAK, allows_difficulty_evidence

TABLE = "listening_difficulty_evidence"
VERDICTS = ("matched", "mismatch", "ambiguous")


def _connect(db_path: Path) -> sqlite3.Connection:
    """Conexión de solo lectura, con repliegue si el WAL no la permite."""
    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return sqlite3.connect(db_path)


def _pct(part: int, whole: int) -> str:
    """Porcentaje legible; `—` cuando no hay denominador (nunca `ZeroDivision`)."""
    if whole <= 0:
        return "—"
    return f"{part * 100 / whole:.1f}%"


def _report(conn: sqlite3.Connection) -> dict:
    """Agrega el ledger por veredicto y proyecta la fase ENFORCE."""
    rows = conn.execute(
        f"SELECT sense_match, sense_reason, sense_key FROM {TABLE}"
    ).fetchall()
    total = len(rows)
    by_match: dict[str, int] = {verdict: 0 for verdict in VERDICTS}
    by_reason: dict[str, int] = {}
    without_verdict = 0
    declared = 0
    kept = 0
    for match, reason, key in rows:
        match = str(match or "")
        reason = str(reason or "")
        if not match:
            without_verdict += 1
            continue
        by_match[match] = by_match.get(match, 0) + 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
        if str(key or ""):
            declared += 1
        # La MISMA política que decide en producción (V3.94, ENFORCE).
        if allows_difficulty_evidence({"match": match}):
            kept += 1
    with_verdict = total - without_verdict
    return {
        "total": total,
        "with_verdict": with_verdict,
        "without_verdict": without_verdict,
        "declared_sense": declared,
        "by_match": by_match,
        "by_reason": dict(sorted(by_reason.items(), key=lambda item: -item[1])),
        # V3.94.1: posibles mismatch (`gloss:other:weak`, un solo token) que NO
        # suprimen evidencia. Se cuentan aparte para medir falsos positivos evitados.
        "possible_mismatch": by_reason.get(REASON_GLOSS_OTHER_WEAK, 0),
        "enforce_kept": kept,
        "enforce_suppressed": with_verdict - kept,
    }


def _print_report(report: dict) -> None:
    print(f"Tabla del ledger: {TABLE}")
    print(f"Registros totales: {report['total']}")
    print(f"  con veredicto (V3.93+): {report['with_verdict']}")
    print(f"  sin veredicto (legacy): {report['without_verdict']}")
    print(f"  con acepción declarada: {report['declared_sense']}")
    with_verdict = report["with_verdict"]
    print("\nReparto del veredicto (solo con veredicto):")
    for verdict in VERDICTS:
        count = report["by_match"].get(verdict, 0)
        print(f"  {verdict:<10} {count:>7}  ({_pct(count, with_verdict)})")
    if report["by_reason"]:
        print("\nRazones dentro de mismatch/ambiguous:")
        for reason, count in report["by_reason"].items():
            print(f"  {reason:<18} {count:>7}  ({_pct(count, with_verdict)})")
    possible = report.get("possible_mismatch", 0)
    if possible:
        print(
            f"\nPosibles mismatch (gloss:other:weak, 1 token): {possible}"
            f"  ({_pct(possible, with_verdict)})"
        )
    kept = report["enforce_kept"]
    suppressed = report["enforce_suppressed"]
    print("\nProyección ENFORCE (política V3.94: solo un `mismatch` probado suprime):")
    print(f"  se conservaría {kept}  ({_pct(kept, with_verdict)})")
    print(f"  se suprimiría  {suppressed}  ({_pct(suppressed, with_verdict)})")
    print(
        "\nNota: usa la MISMA `allows_difficulty_evidence` que decide en producción. "
        "Desde\nV3.94 (ENFORCE) solo un `mismatch` PROBADO suprime evidencia; "
        "`declared:none` y\n`ambiguous` se CONSERVAN por decisión (la duda no RESTA "
        "evidencia igual que no la\nFABRICA). Como `mismatch` exige alternativas "
        "conocidas, sin volumen de estas la\nproyección ve poco que suprimir."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Informe del veredicto sense-aware del puente de Listening "
            "(política ENFORCE de V3.94, solo lectura)."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Ruta de la base de datos (por defecto: {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emite el informe como JSON (para CI o para volcar a un fichero).",
    )
    args = parser.parse_args(argv)

    db_path: Path = args.db
    if not db_path.exists():
        print(f"ERROR: no existe la base de datos {db_path}", file=sys.stderr)
        return 2

    try:
        conn = _connect(db_path)
    except sqlite3.Error as exc:
        print(f"ERROR: no se pudo abrir {db_path}: {exc}", file=sys.stderr)
        return 2

    try:
        present = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if TABLE not in present:
            print(
                f"AVISO: la BD no tiene {TABLE} (instalación anterior a V3.92).",
                file=sys.stderr,
            )
            report = {
                "total": 0,
                "with_verdict": 0,
                "without_verdict": 0,
                "declared_sense": 0,
                "by_match": {},
                "by_reason": {},
                "possible_mismatch": 0,
                "enforce_kept": 0,
                "enforce_suppressed": 0,
            }
        else:
            report = _report(conn)
    except sqlite3.Error as exc:
        print(f"ERROR: fallo leyendo {db_path}: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    data = {"database": str(db_path), "table": TABLE, **report}
    if args.as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"Base de datos: {db_path}")
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
