"""Lote de operador: construye el lexicón offline del diccionario (V3.91, fase 2).

Convierte «la primera consulta de una palabra la paga el alumno con ~9 s de
modelo local» en «ya está generada» para el vocabulario que la app usa de
verdad. Es un trabajo de MANTENIMIENTO, no una consulta: va por su cuenta, sin
las cuotas de la API (10 palabras nuevas por usuario y minuto, 40 globales) que
harían imposible preparar el currículum —1.041 palabras por la puerta de la
consulta son 1.041 clics y **al menos 1 h 45 min de reloj** aunque el modelo
fuera instantáneo—, y por eso vive en un script y no en un endpoint.

**Licencia (decisión de V3.91, fase 2).** Este lote usa SOLO el modelo local: no
empaqueta ningún dato de terceros, así que no arrastra licencia, atribución ni
obligación de compartir. Empaquetar FreeDict eng-spa (35.935 entradas, 24,52 MiB
con índice, CC BY-SA 3.0) sigue **aparcado** a la espera de una decisión
explícita del gerente, porque cambia la naturaleza legal del producto; el
razonamiento medido está en `docs/DISENO-V388-DICCIONARIO-OFFLINE.md` §6 y el
estado en `docs/audit/PARKED.md`.

**Reanudable sin estado propio.** Una palabra preparada es una palabra fresca en
`dictionary_entries`, así que el relanzamiento vuelve a planificar y salta sola
lo hecho. No hay fichero de marcas: la caché es el estado. Interrumpir (Ctrl-C,
tope de tiempo, corte) no deja nada a medias, porque cada palabra se persiste
entera de una vez.

Universo de trabajo: el vocabulario QUE LA APP DECLARA (`objective.vocabulary` de
los 6 niveles + los packs temáticos), no todo el texto del currículum. Medido en
este equipo (`--dry-run`): **1.268 entradas crudas → 10 descartes → 217
duplicados → 1.041 palabras pendientes `[M]`**. Es el conjunto que el alumno puede
encontrarse en una lección; preparar los artículos y las preposiciones que solo
aparecen dentro de las frases de los corpus sería gastar horas de CPU en
palabras que la app nunca ofrece como vocabulario. Con `--words-file` el operador
manda su propia lista.

Uso (desde `backend/`):

    python -m scripts.dictionary_lexicon_batch --dry-run
    python -m scripts.dictionary_lexicon_batch --limit 200
    python -m scripts.dictionary_lexicon_batch --max-seconds 1800 --json
    python -m scripts.dictionary_lexicon_batch --words-file mi_lista.txt

Códigos de salida: 0 = lote terminado (aunque alguna palabra falle: es
best-effort); 2 = error de configuración o de BD; 3 = se intentó algo y NO se
preparó nada (modelo caído, base de datos de solo lectura), que es lo que un
operador o un CI deben notar.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# El script vive en <repo>/backend/scripts/, así que el paquete `backend` es el
# padre de `scripts` (mismo arranque que los demás scripts del backend).
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config  # noqa: E402
from repositories import db as db_repo  # noqa: E402
from repositories import dictionary as dictionary_repo  # noqa: E402
from repositories.collections import PACKS_DIR  # noqa: E402
from services import curriculum as curriculum_service  # noqa: E402
from services import dictionary_batch, dictionary_content  # noqa: E402

# Ritmo medido del modelo local con el contrato de acepción VIGENTE (1.7.0):
# 3 palabras reales preparadas en 26 s de lote sobre una BD temporal con
# `llama3.1:8b` → **8,7 s/palabra**. Es mucho más caro que los 4,05 s que medía
# el estudio de V3.88 con `{pos, gloss}`: el prompt de acepción pide además
# ejemplo, contexto, lemma y dominio, así que el texto generado es ~3× mayor.
# Solo sirve para la ESTIMACIÓN que se imprime antes de empezar; el operador
# puede corregirlo con `--seconds-per-word` si su equipo es más rápido o más
# lento. Con este ritmo, las 1.041 palabras del currículum son ≈ 2 h 31 min.
MEASURED_SECONDS_PER_WORD = 8.7
DEFAULT_UNIVERSE_LABEL = "currículum declarado (objective.vocabulary + packs)"


def _words_from_packs() -> list[str]:
    """Palabras de los packs temáticos versionados (`curriculum/vocab_packs`)."""
    words: list[str] = []
    if not PACKS_DIR.is_dir():
        return words
    for path in sorted(PACKS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Un pack ilegible no invalida el lote: se avisa y se sigue (los
            # packs ya están cubiertos por sus propios tests de contenido).
            print(f"AVISO: pack ilegible, se omite: {path.name}", file=sys.stderr)
            continue
        for item in payload.get("items") or []:
            if isinstance(item, dict):
                words.append(str(item.get("word") or ""))
    return words


def curriculum_words() -> list[str]:
    """Vocabulario declarado por el currículum, sin limpiar ni deduplicar.

    Se devuelve la lista CRUDA a propósito: la limpieza, la deduplicación y el
    descarte de lo inválido son responsabilidad de `dictionary_batch.plan_batch`,
    que es donde están probadas y donde el recuento de descartes es visible.
    """
    words: list[str] = []
    for level in curriculum_service.load_all_levels():
        for objective in level.objectives():
            words.extend(str(word) for word in objective.vocabulary)
    words.extend(_words_from_packs())
    return words


def _read_words_file(path: Path) -> list[str]:
    """Primera columna de cada línea de la lista del operador, sin limpiar.

    Se admite el mismo formato que la lista de vocabulario de la app («palabra,
    traducción»): se toma la PRIMERA columna (separada por coma, punto y coma o
    tabulador) y se ignoran los comentarios `#`, porque la traducción que el
    operador escriba al lado no es una palabra que preparar. No se valida, ni se
    pasa a minúsculas, ni se deduplica aquí a propósito: eso —y su recuento— es
    de `dictionary_batch.plan_batch`. Limpiar en dos sitios daría dos cifras
    distintas de lo mismo.
    """
    fields: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        head = re.split(r"[#\t,;]", line, maxsplit=1)[0]
        if head.strip():
            fields.append(head)
    return fields


def _make_generate(model: str | None, timeout: float):
    """Generador inyectable: el del producto, con tope y sin cuotas.

    Es el MISMO `dictionary_content.generate_content` que usa la consulta (mismo
    prompt, mismo parseo, misma `GENERATOR_VERSION`), envuelto con el tope de
    `config.DICTIONARY_GENERATION_TIMEOUT_SECONDS` para que un Ollama colgado no
    bloquee el lote. Lo único que NO comparte con la consulta es la puerta de
    cuotas: aquí no hay alumno al que servir, hay mantenimiento que hacer.
    """

    async def generate(word: str) -> dict | None:
        try:
            return await asyncio.wait_for(
                dictionary_content.generate_content(word, model=model),
                timeout=timeout,
            )
        except dictionary_content.ContentUnavailableError:
            # Contenido no disponible es «no se pudo preparar», no un fallo del
            # lote: `run_batch` lo cuenta como `empty` y sigue con la siguiente.
            return None
        except asyncio.TimeoutError:
            return None

    return generate


def _make_persist():
    """Persistencia inyectable: el `save_entry` del producto (dispara el FTS5)."""

    def persist(word: str, content: dict) -> bool:
        return dictionary_repo.save_entry(
            word,
            pos=content.get("pos", ""),
            definition=content.get("definition", ""),
            translation=content.get("translation", ""),
            situation=content.get("situation", ""),
            senses=content.get("senses") or [],
            meanings=content.get("meanings") or [],
            generator_version=dictionary_content.GENERATOR_VERSION,
        )

    return persist


def _progress_printer(plan_words: int):
    """Progreso por palabra: una línea por tramo, no una por palabra."""

    def on_progress(report) -> None:
        print(
            f"  [{report.attempted:>5}/{plan_words}] "
            f"preparadas={report.prepared} fallidas={report.failed} "
            f"({dictionary_batch.format_duration(report.elapsed_seconds)})",
            file=sys.stderr,
        )

    return on_progress


def _print_plan(plan: dictionary_batch.BatchPlan, seconds_per_word: float) -> None:
    print(f"  Universo:            {plan.universe} entradas de la lista")
    print(f"  Descartes:           {plan.invalid} no son palabra/locución")
    if plan.duplicates:
        print(f"  Duplicados:          {plan.duplicates} (ya contaban una vez)")
    print(f"  Ya frescas:          {plan.fresh} (no se tocan)")
    print(f"  Pendientes:          {plan.pending}")
    if plan.truncated:
        print(f"  Tope de esta pasada: {len(plan.words)} (se dejan {plan.limited})")
    print(f"  Esta pasada:         {len(plan.words)} palabras")
    estimate = dictionary_batch.estimate_seconds(len(plan.words), seconds_per_word)
    print(
        "  Coste estimado:      "
        f"{dictionary_batch.format_duration(estimate)} "
        f"({seconds_per_word:.2f} s/palabra)"
    )


def _print_report(report: dictionary_batch.BatchReport) -> None:
    print("\nResultado de la pasada")
    print(f"  Intentadas:          {report.attempted}")
    print(f"  Preparadas:          {report.prepared}")
    print(f"  Fallidas:            {report.failed}")
    if report.remaining:
        print(f"  Sin intentar:        {report.remaining} (relanza el script)")
    if report.stopped_early:
        print("  Parada por el tope de tiempo (--max-seconds): relanza para seguir.")
    elapsed = dictionary_batch.format_duration(report.elapsed_seconds)
    print(f"  Tiempo:              {elapsed}")
    for word, reason in report.errors[:10]:
        print(f"    - {word}: {reason}")
    if len(report.errors) > 10:
        print(f"    (+{len(report.errors) - 10} fallos más)")
    if report.attempted and not report.prepared:
        print(
            "\nAVISO: no se preparó ninguna palabra. ¿Está el modelo local "
            "arrancado (Ollama) y descargado el modelo que usa la app?",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara con el modelo local el vocabulario del currículum "
            "(lote reanudable de operador, sin cuotas de API)."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Ruta de la base de datos (por defecto: la del producto).",
    )
    parser.add_argument(
        "--words-file",
        type=Path,
        default=None,
        help="Lista de trabajo propia (una palabra por línea) en lugar del currículum.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Modelo local a usar (por defecto: el que elige la app).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de palabras en ESTA pasada (para trabajar por tramos).",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Tope de tiempo de la pasada; al agotarse, para y se puede relanzar.",
    )
    parser.add_argument(
        "--seconds-per-word",
        type=float,
        default=MEASURED_SECONDS_PER_WORD,
        help=f"Ritmo para la estimación (por defecto: {MEASURED_SECONDS_PER_WORD}).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help=(
            "Cada cuántas palabras se imprime el progreso "
            "(0 = silencio, por defecto: 25)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Planifica y estima, sin llamar al modelo ni escribir nada.",
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

    # Universo de trabajo. Con lista propia se usa SOLO la lista: mezclarla con
    # el currículum haría que la estimación y el recuento no cuadraran con lo
    # pedido.
    if args.words_file is not None:
        if not args.words_file.exists():
            print(f"ERROR: no existe {args.words_file}", file=sys.stderr)
            return 2
        try:
            universe = _read_words_file(args.words_file)
        except OSError as exc:
            print(f"ERROR: no se pudo leer {args.words_file}: {exc}", file=sys.stderr)
            return 2
        universe_label = str(args.words_file)
    else:
        universe = curriculum_words()
        universe_label = DEFAULT_UNIVERSE_LABEL

    try:
        db_repo.init_db()
    except Exception as exc:  # noqa: BLE001 — se reporta como error de configuración
        print(f"ERROR: no se pudo preparar la base de datos: {exc}", file=sys.stderr)
        return 2

    version = dictionary_content.GENERATOR_VERSION
    try:
        fresh = dictionary_repo.fresh_entry_words(universe, version=version)
    except Exception as exc:  # noqa: BLE001 — se reporta como error de configuración
        print(f"ERROR: no se pudo leer la caché: {exc}", file=sys.stderr)
        return 2

    plan = dictionary_batch.plan_batch(universe, fresh=fresh, limit=args.limit)

    if not args.as_json:
        print("Lote del lexicón offline (V3.91, fase 2)")
        print(f"  Base de datos:       {db_repo.DB_PATH}")
        print(f"  Contrato vigente:    GENERATOR_VERSION={version}")
        print(f"  Fuente del universo: {universe_label}")
        _print_plan(plan, args.seconds_per_word)

    if args.dry_run:
        if args.as_json:
            print(
                json.dumps(
                    {
                        "database": str(db_repo.DB_PATH),
                        "generator_version": version,
                        "universe": universe_label,
                        "plan": {
                            "universe": plan.universe,
                            "fresh": plan.fresh,
                            "duplicates": plan.duplicates,
                            "invalid": plan.invalid,
                            "pending": plan.pending,
                            "selected": len(plan.words),
                            "limited": plan.limited,
                            "estimated_seconds": round(
                                dictionary_batch.estimate_seconds(
                                    len(plan.words), args.seconds_per_word
                                ),
                                1,
                            ),
                        },
                        "dry_run": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0

    # El progreso va a stderr a propósito: con `--json`, stdout queda limpio para
    # el objeto y el operador sigue viendo avanzar la pasada en la terminal.
    on_progress = (
        _progress_printer(len(plan.words)) if args.progress_every > 0 else None
    )
    report = asyncio.run(
        dictionary_batch.run_batch(
            plan.words,
            generate=_make_generate(
                args.model, config.DICTIONARY_GENERATION_TIMEOUT_SECONDS
            ),
            persist=_make_persist(),
            max_seconds=args.max_seconds,
            progress_every=args.progress_every,
            on_progress=on_progress,
        )
    )

    if args.as_json:
        payload = {
            "database": str(db_repo.DB_PATH),
            "generator_version": version,
            "universe": universe_label,
            "plan": {
                "universe": plan.universe,
                "fresh": plan.fresh,
                "duplicates": plan.duplicates,
                "invalid": plan.invalid,
                "pending": plan.pending,
                "selected": len(plan.words),
                "limited": plan.limited,
            },
            "report": report.as_dict(),
            "dry_run": False,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    # Fallar del todo es un error de operador (modelo caído, BD de solo lectura),
    # no un lote parcial: la pasada parcial es un resultado legítimo.
    if report.attempted > 0 and report.prepared == 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
