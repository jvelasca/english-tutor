"""Importa un léxico bilingüe externo a `dictionary_lexicon` (V3.95.0).

Herramienta de OPERADOR y **decisión de licencia explícita**. Este script NO
empaqueta ningún dato: lee un fichero que el operador aporta por su cuenta y lo
escribe en la tabla `dictionary_lexicon`, que nace vacía. Por eso exige
`--accept-license`, `--source` y `--license`: sin la aceptación explícita del
gerente se niega a correr (el caso que motivó la decisión es FreeDict eng-spa,
CC BY-SA 3.0, cuya integración estaba APARCADA; ver `docs/audit/PARKED.md`).

Formato de entrada: texto TABULAR, una fila por par bilingüe, con la cabeza en la
primera columna y la traducción en la segunda:

    bank<TAB>banco
    bank<TAB>orilla

El delimitador por defecto es el tabulador; `--delimiter` acepta otro (una coma
para un CSV exportado). La tercera columna, si existe, se interpreta como
categoría y se mapea con la taxonomía de la app. Las cabeceras se detectan y se
saltan; el BOM, las comillas y el ruido de ingesta se limpian con
`services.dictionary_batch` (misma semántica que el lote del modelo).

La misma fila sirve a las DOS direcciones: `headword` (inglés) alimenta EN→ES y
`translation` (español, plegada) alimenta ES→EN.

Uso (desde `backend/`):

    python -m scripts.import_freedict --file eng-spa.tsv \
        --source freedict-eng-spa --license "CC BY-SA 3.0" --accept-license
    python -m scripts.import_freedict --file eng-spa.tsv --dry-run \
        --source freedict-eng-spa --license "CC BY-SA 3.0"

Códigos de salida: 0 = importado (o dry-run); 2 = falta la aceptación de licencia
o el fichero no se puede leer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from repositories import db as db_repo  # noqa: E402
from repositories import dictionary as dictionary_repo  # noqa: E402
from services import dictionary_batch  # noqa: E402


def _parse_rows(text: str, delimiter: str) -> tuple[list[dict], int]:
    """Filas `{headword, translation, pos}` de un texto tabular y las descartadas.

    Salta cabeceras (la primera fila cuyas dos primeras celdas son «palabras de
    cabecera» conocidas) y líneas de comentario (`#`). Limpia la cabeza con
    `normalize_word` (inglés) y la traducción con `normalize_term_es` (español),
    y mapea la categoría. Una fila sin las dos columnas válidas se cuenta como
    descartada.
    """
    rows: list[dict] = []
    skipped = 0
    for index, line in enumerate(text.splitlines()):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = [cell.strip().strip('"') for cell in line.split(delimiter)]
        if len(cells) < 2:
            skipped += 1
            continue
        head_raw, trans_raw = cells[0], cells[1]
        if index == 0 and head_raw.lower() in {
            "headword",
            "word",
            "english",
            "palabra",
        }:
            # Cabecera de un export: no es un par.
            continue
        headword = dictionary_batch.normalize_word(head_raw)
        translation = dictionary_batch.normalize_term_es(trans_raw)
        if not headword or not translation:
            skipped += 1
            continue
        pos = dictionary_batch.map_pos(cells[2] if len(cells) > 2 else "")
        rows.append({"headword": headword, "translation": translation, "pos": pos})
    return rows, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importa un léxico bilingüe externo (opt-in, con licencia)."
    )
    parser.add_argument(
        "--file", type=Path, required=True, help="Fichero tabular de pares."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Identificador de la fuente (p. ej. freedict-eng-spa).",
    )
    parser.add_argument(
        "--license",
        required=True,
        help="Licencia de la fuente (p. ej. 'CC BY-SA 3.0'), para atribución.",
    )
    parser.add_argument(
        "--accept-license",
        action="store_true",
        help="Confirma que el gerente acepta la licencia de la fuente (obligatorio).",
    )
    parser.add_argument(
        "--delimiter",
        default="\t",
        help="Delimitador de columnas (por defecto: tabulador).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Vacía antes esa misma fuente para reimportar sin duplicar.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de filas a importar (prueba con un fichero grande).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Ruta de la base de datos (por defecto: la del producto).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parsea y cuenta, sin escribir en la base de datos.",
    )
    args = parser.parse_args(argv)

    if not args.accept_license and not args.dry_run:
        print(
            "ERROR: falta --accept-license. Integrar un léxico de terceros cambia "
            "la situación legal del producto; exige una decisión explícita "
            "(ver docs/audit/PARKED.md).",
            file=sys.stderr,
        )
        return 2

    if not args.file.exists():
        print(f"ERROR: no existe {args.file}", file=sys.stderr)
        return 2
    try:
        text = args.file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: no se pudo leer {args.file}: {exc}", file=sys.stderr)
        return 2

    rows, skipped = _parse_rows(text, args.delimiter)
    if args.limit is not None and args.limit >= 0:
        rows = rows[: args.limit]

    print("Importación de léxico externo (V3.95.0)")
    print(f"  Fuente:       {args.source}")
    print(f"  Licencia:     {args.license}")
    print(f"  Fichero:      {args.file}")
    print(f"  Pares válidos:{len(rows)}")
    print(f"  Descartadas:  {skipped}")

    if args.dry_run:
        print("  (dry-run: no se escribió nada)")
        return 0

    try:
        db_repo.init_db()
    except Exception as exc:  # noqa: BLE001 — error de configuración
        print(f"ERROR: no se pudo abrir la base de datos: {exc}", file=sys.stderr)
        return 2

    inserted = dictionary_repo.add_lexicon_entries(
        rows,
        source=args.source,
        license=args.license,
        replace_source=args.replace,
    )
    total = sum(item["entries"] for item in dictionary_repo.lexicon_sources())
    print(f"  Insertadas:   {inserted}")
    print(f"  Total en la tabla: {total}")
    print(
        "\nAtribución: incluye esta fuente en los créditos del diccionario "
        f"({args.source}, {args.license})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
