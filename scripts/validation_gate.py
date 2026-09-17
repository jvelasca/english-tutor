"""Arnés de validación de la release (V3.73).

V3.72 dejó cinco bloques de validación **física** pendientes de acción humana
(corte de red real, máquina limpia, launcher en Windows, matriz de dispositivos,
audio real). El riesgo de dejarlos como prosa es doble: se olvidan, o se declaran
cerrados sin evidencia. Este script los convierte en **gates con estado
registrado**.

Tres subcomandos:

- ``auto``      — comprobaciones **estáticas** del repositorio (sin dependencias
                  del backend, sin red). Escribe el informe determinista
                  ``docs/audit/generated/release-validation.{md,json}`` y falla
                  (exit 1) si alguna comprobación no pasa.
- ``record``    — registra el resultado de un gate humano en
                  ``docs/audit/validation-evidence.json`` (con notas y la versión
                  del árbol). Un gate no se puede cerrar sin decir quién/cuándo
                  ni cómo.
- ``status``    — tabla de los gates y su estado. Con ``--strict`` sale 1 si
                  algún gate no está en ``pass``: es la puerta real de V4.0.

El script **no ejecuta** ningún flujo de la app: certifica lo que una persona
hizo. Un ``pass`` sin evidencia es exactamente lo que este instrumento existe para
impedir.

Uso:
    python scripts/validation_gate.py auto [--require-dist]
    python scripts/validation_gate.py record G1 pass --notes "..."
    python scripts/validation_gate.py status [--strict]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
LAUNCHER = ROOT / "launcher"
DOCS = ROOT / "docs"
CI = ROOT / ".github" / "workflows" / "ci.yml"

GENERATED = DOCS / "audit" / "generated"
REPORT_JSON = GENERATED / "release-validation.json"
REPORT_MD = GENERATED / "release-validation.md"

EVIDENCE = DOCS / "audit" / "validation-evidence.json"
RUNBOOK = DOCS / "audit" / "VALIDATION-RELEASE-V373.md"

# El chequeo más importante: ``--strict`` es la puerta de V4.0.
STATUSES = ("pending", "pass", "fail", "skip")


@dataclass(frozen=True)
class Gate:
    """Un gate de validación física: qué se prueba, dónde y qué se registra."""

    id: str
    title: str
    protocol: str
    evidence: str
    human: bool = True


# --- Los 7 gates de la release de validación --------------------------------

GATES: tuple[Gate, ...] = (
    Gate(
        id="offline-fisico",
        title="G1 · Los 12 flujos con la red cortada",
        protocol="docs/audit/RA-RUNTIME-OFFLINE.md §5",
        evidence=(
            "Los 12 veredictos de la tabla E5 (✅/⚠️/❌) con fecha y VERSION. "
            "Un solo FALLO no declarado invalida el gate."
        ),
    ),
    Gate(
        id="maquina-limpia",
        title="G2 · Instalación en una máquina limpia",
        protocol="README.md (runbook) · docs/audit/RB-INSTALACION.md",
        evidence=(
            "Runbook ejecutado en un clon/sistema recién instalado: Python + "
            "dependencias + Ollama + modelo + `download_models.py --check` + build."
        ),
    ),
    Gate(
        id="launcher-windows",
        title="G3 · Launcher en Windows real",
        protocol="release-notes-v3.73.0.md §Verificación (bloque C)",
        evidence=(
            "Inicio desde el launcher: HTTPS en :8000, navegador, micrófono, TTS, "
            "STT, chat y persistencia. Es el gate que el CI de Linux no puede dar."
        ),
    ),
    Gate(
        id="dispositivos",
        title="G4 · Matriz de dispositivos (móvil/tablet)",
        protocol="docs/DEVICE_MATRIX.md",
        evidence=(
            "Filas de la matriz cubiertas con micrófono, audio, touch, viewport, "
            "teclado y orientación. No basta con capturas."
        ),
    ),
    Gate(
        id="audio-stt-tts",
        title="G5 · STT/TTS con audio real",
        protocol="release-notes-v3.73.0.md §Verificación",
        evidence=(
            "Grabación y transcripción reales, reproducción real y aviso de voz "
            "degradada con la voz realmente usada."
        ),
    ),
    Gate(
        id="journeys",
        title="G6 · Todos los recorridos completos",
        protocol="docs/audit/F-UX-JOURNEY.md",
        evidence=(
            "Home, Today, Curso, Aprender, Listening, Vocabulary, Grammar, "
            "Reading, Speaking, Conversation, Review y Progress de principio a fin."
        ),
    ),
    Gate(
        id="pedagogia",
        title="G7 · Auditoría pedagógica final",
        protocol="docs/CONSTITUCION-PEDAGOGICA.md · docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md",
        evidence=(
            "Calidad del contenido (léxico, gramática, listening, speaking) y la "
            "regla de no confundir palabras conocidas con nivel CEFR."
        ),
    ),
)

GATES_BY_ID = {gate.id: gate for gate in GATES}


def source_version() -> str:
    """Versión canónica del árbol (fuente de verdad: `backend/config.py`)."""
    text = (BACKEND / "config.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("No se encontró VERSION en backend/config.py")
    return match.group(1)


# --- Comprobaciones automáticas ---------------------------------------------


@dataclass
class Check:
    id: str
    title: str
    ok: bool | None  # None = skip
    detail: str


def _run_script(check_id: str, title: str, relative: str, *args: str) -> Check:
    """Ejecuta otro gate del repo como subproceso (mismo intérprete)."""
    script = ROOT / relative
    if not script.is_file():
        return Check(check_id, title, False, f"{relative} no encontrado")
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (result.stdout or result.stderr or "").strip().splitlines()
    # El informe se commitea: se quita el prefijo de la raíz y se normalizan los
    # separadores para que el artefacto sea idéntico en Windows y en Linux (donde
    # corre el CI). Sin esto filtraría rutas absolutas del equipo que lo generó.
    message = detail[-1] if detail else "(sin salida)"
    for prefix in (f"{ROOT}\\", f"{ROOT}/"):
        message = message.replace(prefix, "")
    message = message.replace("\\", "/")
    return Check(
        check_id,
        title,
        result.returncode == 0,
        message,
    )


def _code_string_literals(path: Path) -> list[str]:
    """Literales de cadena que son código (los docstrings no cuentan)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


PUBLIC_IPS = ("8.8.8.8", "8.8.4.4", "1.1.1.1")


def check_fail_closed() -> Check:
    """El runtime de producto no puede arrancar sin la UI compilada."""
    core = (LAUNCHER / "core.py").read_text(encoding="utf-8")
    manager = (LAUNCHER / "process_manager.py").read_text(encoding="utf-8")
    main = (BACKEND / "main.py").read_text(encoding="utf-8")
    dist = (BACKEND / "services" / "frontend_dist.py").read_text(encoding="utf-8")

    problems: list[str] = []
    if 'REQUIRE_UI_ENV = "ENGLISH_TUTOR_REQUIRE_UI"' not in core:
        problems.append("el launcher no declara la variable de producto")
    if "backend_env()" not in manager:
        problems.append("el proceso de producto no recibe el entorno exigente")
    if "frontend_dist_available()" not in manager:
        problems.append("el launcher no comprueba el artefacto antes de arrancar")
    if "require_ui=" not in main:
        problems.append("main.py no declara el modo de montaje")
    if "RuntimeError" not in dist:
        problems.append("el backend no tiene el camino fail-closed")

    return Check(
        "fail-closed-producto",
        "El producto no arranca sin la UI compilada",
        not problems,
        "; ".join(problems) or "fail-closed cableado en launcher y backend",
    )


def check_lan_discovery() -> Check:
    """Sin direcciones públicas en el descubrimiento de la IP de LAN (V3.73)."""
    files = [
        BACKEND / "services" / "net_interfaces.py",
        BACKEND / "services" / "network.py",
        BACKEND / "services" / "tls_cert.py",
        LAUNCHER / "core.py",
    ]
    findings: list[str] = []
    for path in files:
        for literal in _code_string_literals(path):
            findings.extend(
                f"{path.name}:{ip}" for ip in PUBLIC_IPS if ip in literal
            )

    return Check(
        "lan-sin-referencias-externas",
        "El descubrimiento de la LAN no usa direcciones públicas",
        not findings,
        "; ".join(findings) or "net_interfaces.py enumera el propio equipo",
    )


def check_ci_windows() -> Check:
    """El CI tiene que ejercitar Windows, no solo Linux."""
    text = CI.read_text(encoding="utf-8")
    problems: list[str] = []
    for job in ("launcher-windows", "product-origin-windows"):
        if f"{job}:" not in text:
            problems.append(f"falta el job {job}")
    windows_runners = text.count("runs-on: windows-latest")
    if windows_runners < 2:
        problems.append(f"solo {windows_runners} job(s) en windows-latest")

    return Check(
        "ci-windows",
        "El CI prueba el launcher y el origen de producto en Windows",
        not problems,
        "; ".join(problems) or "2 jobs en windows-latest",
    )


def check_device_matrix() -> Check:
    """La matriz no puede seguir documentando el dev server de Vite (:5173)."""
    path = DOCS / "DEVICE_MATRIX.md"
    if not path.is_file():
        return Check("device-matrix", "Matriz de dispositivos", False, "no existe")

    text = path.read_text(encoding="utf-8")
    problems = ["sigue documentando :5173"] if ":5173" in text else []
    if ":8000" not in text:
        problems.append("no documenta el puerto de producto :8000")

    return Check(
        "device-matrix",
        "La matriz de dispositivos apunta al origen de producto",
        not problems,
        "; ".join(problems) or ":8000 y sin rastro del dev server",
    )


def check_runtime_audit() -> Check:
    """El instrumento de V3.71 no puede quedar con declaraciones derivadas."""
    path = GENERATED / "runtime-audit.json"
    if not path.is_file():
        return Check(
            "runtime-audit", "Instrumento de red sin deriva", False, "no generado"
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    drifted = [
        f"{t['file']}:{t['needle']}" for t in data["touchpoints"] if not t["match"]
    ]
    return Check(
        "runtime-audit",
        "Instrumento de red sin deriva",
        not drifted,
        "; ".join(drifted) or f"{len(data['touchpoints'])} puntos declarados y vigentes",
    )


def check_gates_declared() -> Check:
    """Los 7 gates existen como definición y están escritos en el runbook."""
    problems: list[str] = []
    if not RUNBOOK.is_file():
        problems.append("falta el runbook de la release de validación")
    else:
        text = RUNBOOK.read_text(encoding="utf-8")
        for gate in GATES:
            if gate.id not in text:
                problems.append(f"el runbook no declara el gate {gate.id}")
    if len(GATES) != 7:
        problems.append(f"se esperaban 7 gates y hay {len(GATES)}")

    return Check(
        "gates-declarados",
        "Los 7 gates están definidos y documentados",
        not problems,
        "; ".join(problems) or "7 gates declarados",
    )


def check_dist_artifact(require_dist: bool) -> Check:
    """El artefacto de la UI: obligatorio con `--require-dist`."""
    index = ROOT / "frontend" / "dist" / "index.html"
    if not index.is_file():
        if require_dist:
            return Check(
                "dist-artifact",
                "El artefacto de la UI está construido",
                False,
                "falta frontend/dist/index.html (ejecuta `npm run build`)",
            )
        return Check(
            "dist-artifact",
            "El artefacto de la UI está construido",
            None,
            "skip: no compilado en este árbol (usa --require-dist tras el build)",
        )

    text = index.read_text(encoding="utf-8", errors="replace")
    ok = "<html" in text.lower()
    return Check(
        "dist-artifact",
        "El artefacto de la UI está construido",
        ok,
        "index.html servible" if ok else "index.html sin estructura HTML",
    )


def check_evidence_not_invented() -> Check:
    """La evidencia registrada no puede tener gates ni estados desconocidos."""
    if not EVIDENCE.is_file():
        return Check(
            "evidencia-integra",
            "La evidencia registrada es válida",
            True,
            "sin evidencia todavía (los 7 gates están en `pending`)",
        )

    data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    problems: list[str] = []
    for gate_id, entry in data.get("gates", {}).items():
        if gate_id not in GATES_BY_ID:
            problems.append(f"gate desconocido: {gate_id}")
        status = entry.get("status")
        if status not in STATUSES:
            problems.append(f"{gate_id}: estado desconocido {status}")
        if not str(entry.get("notes", "")).strip():
            problems.append(f"{gate_id}: sin notas (una evidencia vacía no vale)")

    return Check(
        "evidencia-integra",
        "La evidencia registrada es válida",
        not problems,
        "; ".join(problems) or "gates y estados conocidos",
    )


def run_checks(require_dist: bool) -> list[Check]:
    """Todas las comprobaciones automáticas, en orden estable."""
    return [
        _run_script(
            "release-consistency",
            "La versión es consistente en todos los orígenes",
            "scripts/check_release_consistency.py",
        ),
        _run_script(
            "i18n-strict",
            "i18n sin claves huérfanas ni sin definir",
            "scripts/check_i18n_coverage.py",
            "--strict",
        ),
        check_fail_closed(),
        check_lan_discovery(),
        check_ci_windows(),
        check_device_matrix(),
        check_runtime_audit(),
        check_gates_declared(),
        check_dist_artifact(require_dist),
        check_evidence_not_invented(),
    ]

# --- Informe determinista ---------------------------------------------------


def _status_of(check: Check) -> str:
    if check.ok is None:
        return "skip"
    return "pass" if check.ok else "fail"


def report_markdown(checks: list[Check], version: str) -> str:
    """Informe determinista (mismo árbol → mismo texto)."""
    passed = sum(1 for c in checks if c.ok is True)
    failed = sum(1 for c in checks if c.ok is False)
    skipped = sum(1 for c in checks if c.ok is None)
    lines = [
        "# Validación automática de la release (V3.73)",
        "",
        (
            f"Versión del árbol: `{version}` · "
            f"**{passed} pass · {failed} fail · {skipped} skip**"
        ),
        "",
        "Generado por `scripts/validation_gate.py auto`. No sustituye a los gates",
        "humanos: solo cubre lo que se puede comprobar estáticamente.",
        "",
        "| # | Comprobación | Estado | Detalle |",
        "|---|---|---|---|",
    ]
    for i, check in enumerate(checks, start=1):
        icon = {"pass": "✅", "fail": "❌", "skip": "⬜"}[_status_of(check)]
        lines.append(f"| {i} | {check.title} | {icon} {_status_of(check)} | {check.detail} |")
    lines.append("")
    lines.append(
        "Los 7 gates de validación física se registran con "
        "`validation_gate.py record` y se consultan con `status --strict`."
    )
    lines.append("")
    return "\n".join(lines)


def report_json(checks: list[Check], version: str) -> dict:
    return {
        "version": version,
        "checks": [
            {
                "id": check.id,
                "title": check.title,
                "status": _status_of(check),
                "detail": check.detail,
            }
            for check in checks
        ],
    }


def write_report(checks: list[Check], version: str) -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report_markdown(checks, version), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(report_json(checks, version), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# --- Evidencia de los gates humanos ----------------------------------------


def load_evidence() -> dict:
    if not EVIDENCE.is_file():
        return {}
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def gate_status(evidence: dict, gate_id: str) -> dict:
    """Entrada de un gate, con `pending` explícito si no hay evidencia."""
    entry = (evidence.get("gates") or {}).get(gate_id) or {}
    return {
        "status": entry.get("status", "pending"),
        "notes": entry.get("notes", ""),
        "recorded_at": entry.get("recorded_at"),
        "tree_version": entry.get("tree_version"),
    }


def record(gate_id: str, status: str, notes: str) -> int:
    if gate_id not in GATES_BY_ID:
        print(f"FAIL: gate desconocido `{gate_id}`")
        print("Gates válidos: " + ", ".join(g.id for g in GATES))
        return 1
    if status not in STATUSES:
        print(f"FAIL: estado desconocido `{status}` (usa: {', '.join(STATUSES)})")
        return 1
    if not notes.strip():
        print("FAIL: registrar un gate exige --notes (no se cierra sin decir qué se observó)")
        return 1

    evidence = load_evidence()
    gates = evidence.setdefault("gates", {})
    gates[gate_id] = {
        "status": status,
        "notes": notes.strip(),
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tree_version": source_version(),
    }
    evidence["gates"] = {gate.id: gates[gate.id] for gate in GATES if gate.id in gates}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"OK: gate `{gate_id}` → {status}")
    return 0


def status_report(strict: bool) -> int:
    evidence = load_evidence()
    version = source_version()
    print(f"Validación de la release · árbol v{version}")
    print()
    pending = 0
    for gate in GATES:
        entry = gate_status(evidence, gate.id)
        state = entry["status"]
        if state != "pass":
            pending += 1
        stale = ""
        if entry["tree_version"] and entry["tree_version"] != version:
            stale = f"  (grabado en v{entry['tree_version']})"
        print(f"  [{state:>7}] {gate.title}{stale}")
        if entry["notes"]:
            print(f"            {entry['notes']}")
        print(f"            protocolo: {gate.protocol}")

    print()
    if pending == 0:
        print("OK: los 7 gates están en `pass` — V4.0 puede declararse.")
        return 0
    print(f"PENDIENTE: {pending} de {len(GATES)} gates sin `pass`.")
    if strict:
        print("FAIL: `--strict` exige los 7 gates en `pass`.")
        return 1
    return 0


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    auto = sub.add_parser("auto", help="comprobaciones estáticas del repositorio")
    auto.add_argument(
        "--require-dist",
        action="store_true",
        help="exige `frontend/dist/index.html` (tras `npm run build`)",
    )

    rec = sub.add_parser("record", help="registra el resultado de un gate humano")
    rec.add_argument("gate", help="id del gate (ver `status`)")
    rec.add_argument("result", choices=list(STATUSES))
    rec.add_argument("--notes", default="", help="qué se hizo y qué se observó")

    st = sub.add_parser("status", help="estado de los 7 gates de validación")
    st.add_argument(
        "--strict",
        action="store_true",
        help="sale 1 si algún gate no está en `pass` (puerta de V4.0)",
    )

    args = parser.parse_args(argv)

    if args.command == "auto":
        checks = run_checks(args.require_dist)
        version = source_version()
        write_report(checks, version)
        for check in checks:
            print(f"[{_status_of(check):>4}] {check.title} — {check.detail}")
        print(f"\nInforme: {REPORT_MD.relative_to(ROOT)}")
        return 1 if any(c.ok is False for c in checks) else 0

    if args.command == "record":
        return record(args.gate, args.result, args.notes)

    return status_report(args.strict)


if __name__ == "__main__":
    sys.exit(main())
