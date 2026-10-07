"""Valida la caché del diccionario contra el conocimiento CURADO (V3.95.0).

Instrumento de operador, SOLO LECTURA por defecto: recorre la caché global
(`dictionary_entries` y `dictionary_reverse_entries`) y señala las filas que
CONTRADICEN el conocimiento curado (glosario ES→EN + packs temáticos), que es la
única autoridad determinista y sin licencia que la app tiene.

Qué se considera sospechoso (determinista, SIN modelo):

- **Directa (EN→ES)**: la palabra inglesa tiene equivalente(s) español(es)
  curados y la traducción cacheada no coincide con ninguno.
- **Inversa (ES→EN)**: el término español tiene equivalente(s) inglés(es)
  curados y el `english` cacheado no es ninguno de ellos. Es el caso reportado
  «broca» → «rock»: el glosario dice «drill bit»/«drill», así que la fila se
  marca.

Una fila SIN conocimiento curado NO es sospechosa (no se puede juzgar sin
modelo): se cuenta como «sin referencia» y se deja intacta. Así el instrumento
nunca borra por ignorancia, solo por contradicción demostrable.

Uso (desde `backend/`):

    python -m scripts.dictionary_validate_cache              # informe
    python -m scripts.dictionary_validate_cache --json       # para CI
    python -m scripts.dictionary_validate_cache --apply      # BORRA las inversas (fiables)
    python -m scripts.dictionary_validate_cache --apply --include-direct   # + asesoras EN→ES

Códigos de salida: 0 = informe emitido (haya o no sospechosas); 2 = error de BD.

`--apply` es la única operación de escritura. Por defecto borra SOLO la dirección
inversa (ES→EN), que es determinista: los equivalentes ingleses curados son
canónicos y una fila que los contradice siempre es basura. La dirección directa
(EN→ES) es asesora —la sinonimia es legítima— y solo se purga con
`--include-direct`, asumiendo que puede arrastrar algún sinónimo válido.
Tras borrar, el siguiente lookup regenera las filas bajo el guardarraíl de
retrotraducción de V3.95.0 o las sirve desde el conocimiento curado, nunca repone
la fila envenenada.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from repositories import db as db_repo  # noqa: E402
from repositories import collections as collections_repo  # noqa: E402
from repositories import dictionary as dictionary_repo  # noqa: E402
from services import dictionary_glossary, dictionary_reverse  # noqa: E402


def _curated_items() -> list[dict]:
    """Conocimiento curado: correcciones a mano + glosario + ítems de los packs.

    Las correcciones del webmaster (`dictionary_curated`) entran CONVERTIDAS a la
    forma `{word: inglés, translation: español}` para que las dos comprobaciones
    las reconozcan: una fila de caché que coincide con una corrección manual NO
    es sospechosa (la corrección manda, y si difiere de la caché, la caché es la
    que sobra).
    """
    items: list[dict] = []
    for row in dictionary_repo.list_curated():
        spanish = (row.get("word") or "").strip()
        english = (row.get("translation") or "").strip()
        if not spanish or not english:
            continue
        if row.get("direction") == "es-en":
            items.append(
                {"word": english, "translation": spanish, "pos": row.get("pos") or ""}
            )
        else:
            items.append(
                {"word": spanish, "translation": english, "pos": row.get("pos") or ""}
            )
    items.extend(dictionary_glossary.glossary_items())
    items.extend(collections_repo.list_pack_items())
    return items


def _curated_spanish_for(english: str, items: list[dict]) -> set[str]:
    """Equivalentes españoles curados de una palabra INGLESA (set normalizado)."""
    target = (english or "").strip().casefold()
    if not target:
        return set()
    out: set[str] = set()
    for item in items:
        if (item.get("word") or "").strip().casefold() != target:
            continue
        term = dictionary_reverse.normalize_term(item.get("translation") or "")
        if term:
            out.add(term)
    return out


def _close(left: str, right: str) -> bool:
    """Coincidencia tolerante a plural/género: «alicate» ≈ «alicates».

    El matcher inverso compara glosas exactas; para VALIDAR una fila (no para
    servirla) se admite además el prefijo cuando la raíz es suficientemente
    larga, porque «alicate» y «alicates» son la misma traducción y marcarlas como
    contradictorias sería un falso positivo que haría borrar contenido válido.
    """
    if not left or not right:
        return False
    if left == right:
        return True
    return len(left) >= 4 and left.startswith(right) or len(right) >= 4 and right.startswith(left)


def direct_is_consistent(row: dict, items: list[dict]) -> bool | None:
    """¿Es plausible la traducción cacheada de una fila EN→ES? (None = sin juicio).

    Aviso (honesto): en la dirección directa la sinonimia es legítima («armchair»
    es «butaca» y «sillón»), así que esta comprobación es ASESORA —marca
    contradicciones claras, no toda diferencia—. La dirección inversa es la
    fiable (los equivalentes ingleses curados son canónicos).
    """
    curated = _curated_spanish_for(row.get("word") or "", items)
    if not curated:
        return None
    segments = set(dictionary_reverse._gloss_segments(row.get("translation") or ""))
    return any(_close(c, s) for c in curated for s in segments)


def reverse_is_consistent(row: dict, items: list[dict]) -> bool | None:
    """¿Es plausible el equivalente inglés cacheado de una fila ES→EN? (None = sin juicio)."""
    curated = dictionary_reverse.match_pack_translation(row.get("word") or "", items)
    if not curated:
        return None
    curated_en = {item["word"].casefold() for item in curated if item.get("word")}
    return (row.get("english") or "").strip().casefold() in curated_en


def _scan(items: list[dict]) -> dict:
    """Recorre ambas cachés y clasifica cada fila: ok / suspect / unreferenced."""
    report = {
        "direct": {"total": 0, "ok": 0, "suspect": [], "unreferenced": 0},
        "reverse": {"total": 0, "ok": 0, "suspect": [], "unreferenced": 0},
    }
    for row in dictionary_repo.list_entries():
        verdict = direct_is_consistent(row, items)
        report["direct"]["total"] += 1
        if verdict is None:
            report["direct"]["unreferenced"] += 1
        elif verdict:
            report["direct"]["ok"] += 1
        else:
            report["direct"]["suspect"].append(
                {
                    "word": row.get("word"),
                    "translation": row.get("translation"),
                    "generator_version": row.get("generator_version"),
                }
            )
    for row in dictionary_repo.list_reverse_entries():
        verdict = reverse_is_consistent(row, items)
        report["reverse"]["total"] += 1
        if verdict is None:
            report["reverse"]["unreferenced"] += 1
        elif verdict:
            report["reverse"]["ok"] += 1
        else:
            report["reverse"]["suspect"].append(
                {
                    "word": row.get("word"),
                    "english": row.get("english"),
                    "generator_version": row.get("generator_version"),
                }
            )
    return report


def _print_report(report: dict) -> None:
    print("Validación de la caché del diccionario (V3.95.0)")
    for label, key in (("EN→ES (directa)", "direct"), ("ES→EN (inversa)", "reverse")):
        block = report[key]
        print(
            f"\n{label}\n"
            f"  Entradas: {block['total']} · coherentes: {block['ok']} · "
            f"sin referencia curada: {block['unreferenced']} · "
            f"SOSPECHOSAS: {len(block['suspect'])}"
        )
        for item in block["suspect"][:20]:
            if key == "direct":
                print(
                    f"    - {item['word']} → {item['translation']!r} "
                    f"(v{item['generator_version']})"
                )
            else:
                print(
                    f"    - {item['word']} → {item['english']!r} "
                    f"(v{item['generator_version']})"
                )
        if len(block["suspect"]) > 20:
            print(f"    (+{len(block['suspect']) - 20} sospechosas más)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida la caché del diccionario contra el conocimiento curado."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Ruta de la base de datos (por defecto: la del producto).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Borra las filas sospechosas de la dirección FIABLE (ES→EN). "
            "Las de EN→ES son asesoras y no se tocan sin --include-direct."
        ),
    )
    parser.add_argument(
        "--include-direct",
        action="store_true",
        dest="include_direct",
        help=(
            "Extiende --apply a EN→ES. AVISO: esa comprobación es asesora "
            "(marca sinónimos legítimos como armchair→butaca), así que borra "
            "traducciones válidas; úsalo solo si asumes esa pérdida."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emite el resultado como JSON (para CI o para volcar a un fichero).",
    )
    args = parser.parse_args(argv)

    if args.db is not None:
        db_repo.DB_PATH = args.db

    try:
        db_repo.init_db()
    except Exception as exc:  # noqa: BLE001 — error de configuración
        print(f"ERROR: no se pudo abrir la base de datos: {exc}", file=sys.stderr)
        return 2

    items = _curated_items()
    report = _scan(items)

    deleted = {"direct": 0, "reverse": 0}
    if args.apply:
        # La dirección inversa es determinista (equivalente inglés canónico): su
        # purga es segura. La directa es solo asesora, así que por defecto NO se
        # toca para no borrar sinónimos legítimos (armchair→butaca).
        if args.include_direct:
            for item in report["direct"]["suspect"]:
                if dictionary_repo.delete_entry(item["word"]):
                    deleted["direct"] += 1
        for item in report["reverse"]["suspect"]:
            if dictionary_repo.delete_reverse_entry(item["word"]):
                deleted["reverse"] += 1

    if args.as_json:
        print(
            json.dumps(
                {
                    "database": str(db_repo.DB_PATH),
                    "curated_items": len(items),
                    "report": report,
                    "deleted": deleted,
                    "applied": bool(args.apply),
                    "include_direct": bool(args.include_direct),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print_report(report)
        if args.apply:
            print(
                f"\nBorradas: directas={deleted['direct']} inversas={deleted['reverse']}"
            )
            if not args.include_direct and report["direct"]["suspect"]:
                print(
                    "EN→ES: "
                    f"{len(report['direct']['suspect'])} sospechosas ASESORAS "
                    "conservadas (usa --include-direct para borrarlas, asumiendo "
                    "que puede caer algún sinónimo válido)."
                )
        elif report["direct"]["suspect"] or report["reverse"]["suspect"]:
            print(
                "\nRelanza con --apply para borrar las inversas (fiables) o "
                "con --apply --include-direct para incluir las asesoras."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
