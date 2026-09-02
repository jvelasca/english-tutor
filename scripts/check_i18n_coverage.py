"""Checker de cobertura i18n del frontend (auditoría F, V3.0).

Escanea `frontend/src` y cruza las claves usadas por `t(...)` con las definidas
en `frontend/src/utils/i18n.ts` (STRINGS). Reporta:

- claves definidas pero nunca usadas (warnings: candidatas a limpieza),
- claves usadas pero NO definidas (error: rompería en runtime),
- claves duplicadas en STRINGS (error),
- entradas con `en` o `es` vacíos (error),
- familias dinámicas `t(`prefix.${...}`)` (las marca como usadas por prefijo).

Salida: stdout + `docs/audit/generated/i18n-report.{json,md}`.

Uso:
    python scripts/check_i18n_coverage.py
    python scripts/check_i18n_coverage.py --strict   # exit 1 con warnings
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N_FILE = ROOT / "frontend" / "src" / "utils" / "i18n.ts"
SRC_DIR = ROOT / "frontend" / "src"
OUT = ROOT / "docs" / "audit" / "generated"

_Q_STR = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_EN_RE = re.compile(r"\ben:\s*(" + _Q_STR.pattern + ")")
_ES_RE = re.compile(r"\bes:\s*(" + _Q_STR.pattern + ")")
# t("literal") / t('literal')
_T_LIT = re.compile(r"""\bt\(\s*(['"])((?:\\.|(?!\1).)+?)\1\s*\)""")
# t(`...`) con/sin interpolación (tolera cast de TS `as "..."` antes del cierre)
_T_TPL = re.compile(r"""\bt\(\s*`([^`]*)`(?:\s+as\s+[^)]*)?\s*\)""")
# prefijo literal antes del primer ${ de un template
_TPL_PREFIX = re.compile(r"^([A-Za-z0-9_.-]*)\$\{")


def _scan_balanced(text: str, open_index: int) -> int:
    """Devuelve el índice justo después de la llave que cierra el bloque que
    comienza en `text[open_index] == '{'`, ignorando llaves dentro de strings
    (p. ej. `{days}` en una traducción)."""
    depth = 0
    i = open_index
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _defined_keys() -> tuple[dict[str, dict[str, str | None]], list[str]]:
    text = I18N_FILE.read_text(encoding="utf-8")
    start = text.find("const STRINGS")
    open_idx = text.find("{", start)
    end_idx = _scan_balanced(text, open_idx)
    text = text[open_idx + 1 : end_idx - 1]

    keys: dict[str, dict[str, str | None]] = {}
    raw: list[str] = []
    pos = 0
    key_re = re.compile(r'"([^"]+)"\s*:\s*\{')
    while True:
        m = key_re.search(text, pos)
        if not m:
            break
        block_end = _scan_balanced(text, text.find("{", m.start()))
        block = text[m.end() : block_end - 1]
        raw.append(m.group(1))
        en = _EN_RE.search(block)
        es = _ES_RE.search(block)
        keys[m.group(1)] = {
            "en": json.loads(en.group(1)) if en else None,
            "es": json.loads(es.group(1)) if es else None,
        }
        pos = block_end
    return keys, raw


def _scanned() -> list[Path]:
    return [
        p
        for p in SRC_DIR.rglob("*.ts*")
        if p.suffix in {".ts", ".tsx"}
        and p.name not in {"i18n.ts"}
        and "node_modules" not in p.parts
    ]


def _boundary_ok(text: str, at: int, length: int) -> tuple[bool, bool]:
    """(limite_izquierdo_ok, limite_derecho_ok) para una ocurrencia en `at`."""
    left_ok = at == 0 or not (text[at - 1].isalnum() or text[at - 1] in {"_", "$"})
    at_end = at + length
    if at_end < len(text):
        ch = text[at_end]
        right_ok = not (ch.isalnum() or ch in {"_", "$"})
    else:
        right_ok = True
    return left_ok, right_ok


def _key_referenced(text: str, key: str) -> bool:
    """¿Aparece la clave como literal con fronteras limpias en el código?

    Cubre los usos indirectos (`i18nKey: "nav.home"`, `titleKey:`, retornos de
    helpers que luego pasan por `t(...)`), no solo `t("clave")`.
    """
    length = len(key)
    start = 0
    while True:
        at = text.find(key, start)
        if at < 0:
            return False
        left_ok, right_ok = _boundary_ok(text, at, length)
        if left_ok and right_ok:
            return True
        start = at + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Checker de cobertura i18n.")
    parser.add_argument("--strict", action="store_true", help="exit 1 con warnings")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    defined, raw_keys = _defined_keys()
    files = _scanned()
    blob = "\n".join(p.read_text(encoding="utf-8") for p in files)
    referenced = {k for k in defined if _key_referenced(blob, k)}

    used: set[str] = set()  # claves usadas como literal directo en t(...)
    dynamic_prefixes: set[str] = set()
    dynamic_odd: set[str] = set()

    for m in _T_LIT.finditer(blob):
        used.add(m.group(2))
    for m in _T_TPL.finditer(blob):
        raw = m.group(1)
        if "${" not in raw:
            used.add(raw)  # t(`literal`) sin interpolación
            continue
        prefix = _TPL_PREFIX.match(raw)
        if prefix:
            dynamic_prefixes.add(prefix.group(1))
        else:
            dynamic_odd.add(raw)

    # Una clave se considera en uso si aparece como literal en el código fuente
    # (directo en `t(...)`, vía indirección como `i18nKey:`/`titleKey:`, o por
    # prefijo de plantilla dinámica `t(`prefix.${x}`)`).
    unused = sorted(k for k in defined if k not in referenced)
    unused = sorted(
        k
        for k in unused
        if not any(k.startswith(p) for p in dynamic_prefixes if p)
    )
    undefined = sorted(used - set(defined))
    undefined += sorted(dynamic_odd)
    duplicates = [k for k, n in Counter(raw_keys).items() if n > 1]
    empty = sorted(
        k for k, v in defined.items() if not v["en"] or not v["es"]
    )

    report = {
        "audit": "F-2026-09-02",
        "defined": len(defined),
        "literal_uses": len(used),
        "referenced_keys": len(referenced),
        "dynamic_prefixes": sorted(dynamic_prefixes),
        "unused_keys": unused,
        "undefined_keys": undefined,
        "duplicate_keys": duplicates,
        "empty_translations": empty,
    }

    print(f"STRINGS definidas: {report['defined']}")
    print(f"Prefijos dinámicos t(`x.${{...}}`): {len(dynamic_prefixes)}")
    print(f"Claves sin uso: {len(unused)}")
    print(f"Claves usadas y NO definidas (runtime error): {len(undefined)}")
    print(f"Claves duplicadas: {len(report['duplicate_keys'])}")
    print(f"Entradas con en/es vacío: {len(empty)}")
    if undefined:
        print("\nNO DEFINIDAS:")
        for k in undefined:
            print(f"  - {k}")
    if report["duplicate_keys"]:
        print("\nDUPLICADAS:")
        for k in report["duplicate_keys"]:
            print(f"  - {k}")
    if empty:
        print("\nVACÍAS (en/es):")
        for k in empty:
            print(f"  - {k}")
    if unused:
        print("\nSIN USO (candidatas a limpieza; no fallan salvo --strict):")
        for k in unused[:80]:
            print(f"  - {k}")
        if len(unused) > 80:
            print(f"  ... y {len(unused) - 80} mas (ver JSON)")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "i18n-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT / "i18n-report.md").write_text(
        "# Informe de cobertura i18n (auditoría F)\n\n"
        "> Generado por `python scripts/check_i18n_coverage.py`.\n\n"
        "```json\n" + json.dumps(report, ensure_ascii=False, indent=1) + "\n```\n",
        encoding="utf-8",
    )
    print(f"  -> {OUT / 'i18n-report.{json,md}'}")

    if undefined or report["duplicate_keys"] or empty:
        return 1
    if args.strict and unused:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
