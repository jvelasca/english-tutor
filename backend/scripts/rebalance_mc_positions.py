#!/usr/bin/env python
"""Reequilibra la posición de la respuesta correcta en los checks MC del currículum.

Instrumento de CONTENIDO (V3.75.1), NO ruta de producto: reescribe los JSON de
`backend/curriculum/<nivel>.json` permutando las opciones de cada check para que
la respuesta correcta no se concentre en una posición.

Origen: hallazgo **P0** de la auditoría pedagógica V3.70
(`docs/audit/AA-PED-CONTENIDO-CEFR.md` §3 y §Hallazgos): **329 de 368** checks
del currículum (89,4 %) tenían la correcta en la posición 0, de modo que marcar
siempre la primera opción acertaba casi 9 de cada 10.

Regla de reposicionamiento (determinista, declarada e **idempotente**):

    Dentro de cada grupo de checks con el MISMO número de opciones `k`,
    ordenados por `id` ascendente, el check que ocupa la posición `j` del grupo
    lleva la correcta a la posición `j % k`.

Solo se **mueve la opción correcta** a su posición destino; los distractores
conservan su orden relativo original. Eso mantiene el cambio en el mínimo
posible (un elemento cambia de sitio) y respeta el orden en que se autoriaron
los distractores. La auditoría V3.70 lo llamó «rotación determinista»; aquí se
implementa como reposicionamiento porque una rotación cíclica alteraría el orden
lineal de los distractores al extraer la correcta.

No cambia ningún texto de opción ni ninguna respuesta: solo reordena `options` y
ajusta `correct_index` para que la misma opción siga siendo la correcta. No toca
`production_checks` (que usan `accepted_answers`) ni `assessments.json`
(exámenes/placement, que son otro eje y siguen su propia medición).

La reescritura es **quirúrgica por líneas**: solo se sustituyen las líneas de
`options` y el valor de `correct_index`, de modo que el diff no arrastra
reformateo del resto del fichero.

Uso:
    python -m scripts.rebalance_mc_positions --check   # informa; exit 1 si hay deriva
    python -m scripts.rebalance_mc_positions --write   # aplica el reposicionamiento
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.curriculum import CURRICULUM_DIR, available_level_ids  # noqa: E402

# Ninguna posición debe superar este % de los checks de su grupo. Es el
# invariante que fija `tests/test_ped_content_cefr_v370.py` (recomendación del P0
# de `AA-PED-CONTENIDO-CEFR.md`: «≤ 35 % por posición»).
MAX_POSITION_SHARE = 0.35

_ID_RE = re.compile(r'^(\s*)"id":\s*"([^"]+)",?\s*$')
_OPTIONS_OPEN_RE = re.compile(r'^(\s*)"options":\s*\[\s*$')
_OPTIONS_CLOSE_RE = re.compile(r"^(\s*)\],?\s*$")
_OPTION_LINE_RE = re.compile(r'^(\s*)("(?:[^"\\]|\\.)*")(,?)([ \t]*)$')
_CORRECT_INDEX_RE = re.compile(r'^(\s*)"correct_index":\s*(\d+)(,?)([ \t]*)$')


def level_files() -> list[Path]:
    """JSON de nivel (`a1.json`..`c2.json`), en orden determinista."""
    return [CURRICULUM_DIR / f"{level}.json" for level in available_level_ids()]


def _level_data(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_checks(data: dict):
    """Itera los checks MC (`options` + `correct_index`) de un nivel.

    Ruta del contenido: `modules → units → lessons → objectives → checks`.
    """
    for module in data.get("modules", []):
        for unit in module.get("units", []):
            for lesson in unit.get("lessons", []):
                for objective in lesson.get("objectives", []):
                    for check in objective.get("checks", []):
                        if len(check.get("options") or []) >= 2:
                            yield check


def rotation_plan() -> dict[str, int]:
    """`{check_id: posición destino}` según la regla declarada.

    Se calcula **por grupo de `k` opciones**, ordenando cada grupo por `id`
    ascendente. Es idempotente: aplicar el plan a un contenido ya corregido no lo
    vuelve a mover.
    """
    by_k: dict[int, list[str]] = {}
    for path in level_files():
        for check in _iter_checks(_level_data(path)):
            by_k.setdefault(len(check["options"]), []).append(check["id"])
    plan: dict[str, int] = {}
    for k, ids in by_k.items():
        for j, cid in enumerate(sorted(ids)):
            plan[cid] = j % k
    return plan


def _reposition(options: list[str], correct_index: int, target: int) -> list[str]:
    """Mueve la opción correcta a `target` conservando el orden de los distractores.

    Equivale a extraer la correcta y reinsertarla en `target`: los demás
    elementos mantienen su orden relativo original, así que el único cambio es la
    posición de la correcta. Es idempotente (`target` ya alcanzado ⇒ lista igual).
    """
    k = len(options)
    if not 0 <= correct_index < k:
        raise ValueError(f"correct_index {correct_index} fuera de rango (k={k})")
    if not 0 <= target < k:
        raise ValueError(f"target {target} fuera de rango (k={k})")
    if correct_index == target:
        return list(options)
    correct = options[correct_index]
    distractors = [
        option for j, option in enumerate(options) if j != correct_index
    ]
    return distractors[:target] + [correct] + distractors[target:]


def _rewrite_text(raw: str, plan: dict[str, int], *, path: Path) -> tuple[str, int]:
    """Reescribe `raw` rotando solo los checks presentes en `plan`.

    Cirugía por líneas: sustituye los TEXTOS de las líneas de `options` (misma
    posición, misma indentación, misma coma) y el valor de `correct_index`; todo
    lo demás se copia literal. Falla en alto si la estructura no es la esperada
    (mejor un error que un contenido corrupto).
    """
    lines = raw.splitlines(keepends=True)
    eol = "\r\n" if "\r\n" in raw else "\n"
    out: list[str] = []
    changed = 0
    i = 0
    while i < len(lines):
        match = _ID_RE.match(lines[i])
        cid = match.group(2) if match else None
        if cid is None or cid not in plan:
            out.append(lines[i])
            i += 1
            continue

        out.append(lines[i])  # la línea del id, literal
        i += 1
        # Copia literal hasta la apertura del array de opciones.
        while i < len(lines) and not _OPTIONS_OPEN_RE.match(lines[i]):
            if _ID_RE.match(lines[i]):
                raise ValueError(f"{path.name}: {cid} sin bloque `options`")
            out.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError(f"{path.name}: {cid} sin bloque `options`")
        open_line = lines[i]
        i += 1

        # Líneas de opción: se guarda (indentación, texto, coma) y se reordena
        # SOLO el texto.
        option_lines: list[tuple[str, str, str]] = []
        while i < len(lines) and not _OPTIONS_CLOSE_RE.match(lines[i]):
            opt = _OPTION_LINE_RE.match(lines[i])
            if opt is None:
                raise ValueError(
                    f"{path.name}: {cid} línea de opción inesperada: {lines[i]!r}"
                )
            option_lines.append((opt.group(1), opt.group(2), opt.group(3)))
            i += 1
        if i >= len(lines):
            raise ValueError(f"{path.name}: {cid} bloque `options` sin cerrar")
        close_line = lines[i]
        i += 1

        # Todo lo que hay entre el cierre de `options` y `correct_index` se
        # copia literal (al día de hoy, nada).
        middle: list[str] = []
        while i < len(lines) and not _CORRECT_INDEX_RE.match(lines[i]):
            if _ID_RE.match(lines[i]):
                raise ValueError(f"{path.name}: {cid} sin `correct_index`")
            middle.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError(f"{path.name}: {cid} sin `correct_index`")
        ci = _CORRECT_INDEX_RE.match(lines[i])

        options = [json.loads(text) for _, text, _ in option_lines]
        k = len(options)
        target = plan[cid] % k
        current = int(ci.group(2))
        repositioned = _reposition(options, current, target)

        # Emisión en el orden real del fichero: apertura, opciones, cierre,
        # intermedio y `correct_index`.
        out.append(open_line)
        if repositioned == options and target == current:
            # Ya cumple la regla: se copian las líneas originales tal cual.
            for indent, text, comma in option_lines:
                out.append(f"{indent}{text}{comma}{eol}")
            out.append(close_line)
            out.extend(middle)
            out.append(lines[i])
        else:
            changed += 1
            for (indent, _, comma), value in zip(
                option_lines, repositioned, strict=True
            ):
                out.append(
                    f"{indent}{json.dumps(value, ensure_ascii=False)}{comma}{eol}"
                )
            out.append(close_line)
            out.extend(middle)
            out.append(
                f'{ci.group(1)}"correct_index": {target}{ci.group(3)}'
                f"{ci.group(4)}{eol}"
            )
        i += 1

    return "".join(out), changed


def _canonical(data: dict) -> dict:
    """Forma canónica de un nivel: la correcta siempre primera, índice 0.

    Dos contenidos con la misma forma canónica tienen **las mismas opciones en el
    mismo orden relativo y la misma opción correcta**, aunque la correcta esté en
    posiciones distintas. Es la verificación de que el reposicionamiento no cambió
    nada semántico: la correcta sigue siendo la misma y los distractores conservan
    su orden relativo.
    """
    data = copy.deepcopy(data)
    for check in _iter_checks(data):
        options = check["options"]
        correct_index = check["correct_index"]
        correct = options[correct_index]
        check["options"] = [correct] + [
            option for j, option in enumerate(options) if j != correct_index
        ]
        check["correct_index"] = 0
    return data


def observed_shares() -> dict[int, dict[int, int]]:
    """Reparto de posiciones observado en disco, por nº de opciones."""
    out: dict[int, dict[int, int]] = {}
    for path in level_files():
        for check in _iter_checks(_level_data(path)):
            k = len(check["options"])
            bucket = out.setdefault(k, {})
            pos = check["correct_index"]
            bucket[pos] = bucket.get(pos, 0) + 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check", action="store_true",
        help="no escribe; exit 1 si el contenido no cumple la regla",
    )
    group.add_argument(
        "--write", action="store_true", help="aplica el reposicionamiento a los JSON"
    )
    args = parser.parse_args()

    plan = rotation_plan()
    total_changed = 0
    for path in level_files():
        raw = path.read_text(encoding="utf-8")
        new_text, changed = _rewrite_text(raw, plan, path=path)
        total_changed += changed
        before = _level_data(path)
        after = json.loads(new_text)
        if _canonical(before) != _canonical(after):
            raise AssertionError(
                f"{path.name}: el reposicionamiento alteró contenido semántico"
            )
        # La cirugía solo reordena textos y cambia un número: el nº de líneas no
        # puede moverse (delata líneas en blanco o pérdidas de formato).
        if len(new_text.splitlines()) != len(raw.splitlines()):
            raise AssertionError(
                f"{path.name}: el nº de líneas cambió "
                f"({len(raw.splitlines())} → {len(new_text.splitlines())})"
            )
        if args.write and changed:
            path.write_text(new_text, encoding="utf-8")

    shares = observed_shares()
    print(f"checks MC: {len(plan)}  ·  ficheros de nivel: {len(level_files())}")
    print(f"checks que la regla mueve: {total_changed}")
    print("Reparto observado por posición (nº de checks y % de su grupo):")
    worst = 0.0
    for k in sorted(shares):
        counts = shares[k]
        n = sum(counts.values())
        detail = "  ".join(
            f"{p}:{counts.get(p, 0)}({counts.get(p, 0) / n * 100:.1f}%)"
            for p in range(k)
        )
        worst = max(worst, max(counts.get(p, 0) / n for p in range(k)))
        print(f"  k={k}  n={n:3d}  {detail}")
    print(
        f"Peor posición: {worst * 100:.1f}%  (límite {MAX_POSITION_SHARE * 100:.0f}%)"
    )

    if args.check:
        if total_changed or worst > MAX_POSITION_SHARE:
            over = worst > MAX_POSITION_SHARE
            print(
                f"DERIVA: {total_changed} checks fuera de la regla"
                f"{' y reparto por encima del límite' if over else ''}",
                file=sys.stderr,
            )
            return 1
        print("OK: el contenido cumple la regla de reparto y el límite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
