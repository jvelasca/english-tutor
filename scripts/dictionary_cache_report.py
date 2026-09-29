"""Informe de cobertura de la caché del diccionario (V3.88.0).

Responde a una pregunta concreta y medible: **¿está la BD del diccionario al
día con el contrato de contenido vigente, y cuántas palabras ofrecen de verdad
los 2+ significados que exige el prompt?** Es la comprobación de que el bump de
`GENERATOR_VERSION` a `1.6.0` (`MIN_MEANINGS = 2`, V3.88.0) está surtiendo
efecto sobre datos reales, y no solo sobre los tests.

Qué mide, por cada tabla de caché (`dictionary_entries`, la directa EN→ES, y
`dictionary_reverse_entries`, la inversa ES→EN):

1. **Volumen y frescura**: filas totales, cuántas coinciden con la
   `GENERATOR_VERSION` vigente (las únicas que el dominio sirve como frescas:
   `_content_is_fresh`) y el desglose de las obsoletas por versión. Una caché
   con muchas filas viejas no ayuda: se regeneran de forma perezosa y pagan la
   latencia del modelo local en la cara del alumno.
2. **Significados por fila**: cuántas filas traen 0, 1 y 2+ significados
   (`meanings_json`), contadas sobre el total y sobre las frescas. El porcentaje
   de 2+ es la métrica que el Incremento B de V3.88.0 viene a mover.
3. **Muestra de huecos**: unas pocas palabras frescas por debajo del mínimo, con
   su versión, para saber por dónde empezar a mirar.

El script es de LECTURA: abre SQLite en modo `mode=ro` (con repliegue a conexión
normal si el WAL lo impide, ver `_connect`) y no ejecuta ningún `INSERT`,
`UPDATE` ni `DELETE`. Una fila con `meanings_json` ilegible se cuenta aparte
como `corrupt` y nunca rompe el informe.

Uso:

    python scripts/dictionary_cache_report.py
    python scripts/dictionary_cache_report.py --json
    python scripts/dictionary_cache_report.py --sample 20
    python scripts/dictionary_cache_report.py --db ruta/a/otra.db

Códigos de salida: 0 = informe emitido; 2 = no se pudo leer la BD o el contrato
de contenido (en ambos casos con explicación en stderr).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# El script vive en <repo>/scripts/, así que la raíz es el padre de `scripts`.
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "tutor.db"
CONTENT_MODULE = ROOT / "backend" / "services" / "dictionary_content.py"

# (tabla, etiqueta legible). El orden importa solo para la salida.
TABLES: tuple[tuple[str, str], ...] = (
    ("dictionary_entries", "EN→ES (directa)"),
    ("dictionary_reverse_entries", "ES→EN (inversa)"),
)

# Marca de compatibilidad de `repositories/db.py` para el contenido anterior a
# V3.30.1: se etiqueta a propósito con una versión DISTINTA de la vigente para
# que el dominio lo regenere en lugar de servirlo como fresco.
LEGACY_VERSION = "1.0.0"


def _read_contract() -> tuple[str, int]:
    """Lee `GENERATOR_VERSION` y `MIN_MEANINGS` del módulo de contenido.

    Se leen del CÓDIGO con dos expresiones regulares en vez de importar el
    módulo: `services.dictionary_content` arrastra el cliente LLM y el arranque
    de `config`, que este informe no necesita para nada. Son dos constantes de
    nivel de módulo y la versión vigente tiene que salir del código, no de un
    valor duplicado aquí que se desincronice. Si la lectura falla, el informe lo
    dice (exit 2) en lugar de comparar contra una versión inventada.
    """
    if not CONTENT_MODULE.exists():
        raise ValueError(f"no existe {CONTENT_MODULE}")
    text = CONTENT_MODULE.read_text(encoding="utf-8")
    version = re.search(r'^GENERATOR_VERSION = "([^"]+)"', text, re.MULTILINE)
    minimum = re.search(r"^MIN_MEANINGS = (\d+)", text, re.MULTILINE)
    if version is None or minimum is None:
        raise ValueError(
            "no se pudieron leer GENERATOR_VERSION/MIN_MEANINGS en "
            f"{CONTENT_MODULE}"
        )
    return version.group(1), int(minimum.group(1))


def _connect(db_path: Path) -> sqlite3.Connection:
    """Conexión de solo lectura, con repliegue si el WAL no la permite.

    Con `journal_mode=WAL` y la app abierta, una conexión `mode=ro` puede
    fracasar al no poder crear el `-shm`. El repliegue abre la BD con permisos
    normales pero el informe no escribe nada: el modo estricto es una garantía
    de intención, no la única defensa.
    """
    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        return sqlite3.connect(db_path)


def _meaning_count(raw: object) -> tuple[int, bool]:
    """`(nº de significados, ilegible)` de una celda `meanings_json`.

    Cuenta los elementos con `term` no vacío (el mismo criterio que
    `_decode_meanings`: una entrada sin término no es un significado elegible).
    `ilegible=True` cuando el texto no vacío no decodifica a una lista; esas
    filas se cuentan aparte para no confundirlas con "sin significados".
    """
    text = str(raw or "").strip()
    if not text:
        return 0, False
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return 0, True
    if not isinstance(data, list):
        return 0, True
    count = sum(
        1
        for item in data
        if isinstance(item, dict) and str(item.get("term") or "").strip()
    )
    return count, False


def _pct(part: int, whole: int) -> str:
    """Porcentaje legible; `—` cuando no hay denominador (nunca `ZeroDivision`)."""
    if whole <= 0:
        return "—"
    return f"{part * 100 / whole:.1f}%"


def _empty_buckets() -> dict[str, int]:
    return {"total": 0, "none": 0, "one": 0, "many": 0, "corrupt": 0}


def _table_report(
    conn: sqlite3.Connection,
    table: str,
    label: str,
    version: str,
    min_meanings: int,
    sample: int,
) -> dict:
    """Cobertura de una tabla de caché: frescura y significados."""
    rows = conn.execute(
        f"SELECT word, generator_version, meanings_json FROM {table}"
    ).fetchall()

    overall = _empty_buckets()
    fresh = _empty_buckets()
    by_version: dict[str, dict[str, int]] = {}
    # `palabra (1.5.0)` de las filas FRESCAS por debajo del mínimo.
    gaps: list[str] = []

    for word, row_version, meanings_json in rows:
        row_version = str(row_version or "")
        count, corrupt = _meaning_count(meanings_json)
        is_fresh = row_version == version

        overall["total"] += 1
        by_version.setdefault(row_version, _empty_buckets())["total"] += 1
        if is_fresh:
            fresh["total"] += 1

        # `many` exige el mínimo del contrato: si el mínimo subiera mañana, el
        # informe cambia de criterio sin tocar el script.
        bucket = (
            "corrupt"
            if corrupt
            else "none"
            if count == 0
            else "many"
            if count >= min_meanings
            else "one"
        )
        overall[bucket] += 1
        by_version[row_version][bucket] += 1
        if is_fresh:
            fresh[bucket] += 1
            if bucket in ("none", "one", "corrupt") and len(gaps) < sample:
                gaps.append(f"{word} ({row_version or 'sin versión'})")

    return {
        "table": table,
        "label": label,
        "overall": overall,
        "fresh": fresh,
        "stale": overall["total"] - fresh["total"],
        "by_version": dict(
            sorted(by_version.items(), key=lambda item: item[0], reverse=True)
        ),
        "gaps": gaps,
    }


def _print_table(report: dict, version: str, min_meanings: int) -> None:
    """Bloque legible de una tabla."""
    overall = report["overall"]
    fresh = report["fresh"]
    print(f"\n{report['label']}  [{report['table']}]")
    print(f"  Entradas:                {overall['total']}")
    print(f"    frescas ({version}): {fresh['total']}")
    print(f"    obsoletas:              {report['stale']}")
    for ver, bucket in report["by_version"].items():
        mark = " (vigente)" if ver == version else ""
        if not ver:
            ver = "sin versión"
        elif ver == LEGACY_VERSION:
            ver = f"{ver} (legacy)"
        print(f"      {ver}{mark}: {bucket['total']}")
    if overall["total"] == 0:
        print("    (tabla vacía: nada consultado todavía)")
        return
    for scope_name, bucket in (("todas", overall), ("solo frescas", fresh)):
        if bucket["total"] == 0:
            continue
        print(f"  Significados ({scope_name}):")
        print(
            f"    >= {min_meanings} significados:  {bucket['many']} "
            f"({_pct(bucket['many'], bucket['total'])})"
        )
        print(
            f"    1 significado:        {bucket['one']} "
            f"({_pct(bucket['one'], bucket['total'])})"
        )
        print(
            f"    sin significados:     {bucket['none']} "
            f"({_pct(bucket['none'], bucket['total'])})"
        )
        if bucket["corrupt"]:
            print(
                f"    JSON ilegible:        {bucket['corrupt']} "
                f"({_pct(bucket['corrupt'], bucket['total'])})"
            )
    if report["gaps"]:
        print("  Frescas por debajo del mínimo:")
        for gap in report["gaps"]:
            print(f"    - {gap}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cobertura y frescura de la caché del diccionario (solo lectura)."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Ruta de la base de datos (por defecto: {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=10,
        help="Cuántas palabras frescas sin 2+ significados listar (por defecto: 10).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emite el informe como JSON (para CI o para volcar a un fichero).",
    )
    args = parser.parse_args(argv)

    try:
        version, min_meanings = _read_contract()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    db_path: Path = args.db
    if not db_path.exists():
        print(f"ERROR: no existe la base de datos {db_path}", file=sys.stderr)
        return 2

    try:
        conn = _connect(db_path)
    except sqlite3.Error as exc:
        print(f"ERROR: no se pudo abrir {db_path}: {exc}", file=sys.stderr)
        return 2

    sample = max(0, args.sample)
    try:
        present = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        reports = []
        for table, label in TABLES:
            if table not in present:
                print(
                    f"AVISO: la BD no tiene la tabla {table} "
                    "(instalación anterior a su migración).",
                    file=sys.stderr,
                )
                continue
            reports.append(
                _table_report(
                    conn, table, label, version, min_meanings, sample
                )
            )
    except sqlite3.Error as exc:
        print(f"ERROR: fallo leyendo {db_path}: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    data = {
        "database": str(db_path),
        "generator_version": version,
        "min_meanings": min_meanings,
        "tables": reports,
    }

    if args.as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(f"Base de datos:    {db_path}")
    print(f"Contrato vigente: GENERATOR_VERSION={version}  MIN_MEANINGS={min_meanings}")
    for report in reports:
        _print_table(report, version, min_meanings)
    print(
        "\nNota: las filas obsoletas NO se regeneran solas al mirarlas; se "
        "regeneran perezosamente\nen la primera consulta (o al precalentar el "
        "léxico), que es cuando pagan la latencia\nlocal. El porcentaje de 2+ "
        "significados sobre las frescas es la métrica que\npersigue el "
        "Incremento B de V3.88.0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
