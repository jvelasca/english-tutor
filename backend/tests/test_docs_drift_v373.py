"""Deriva documental y de frontera de V3.73 (release de validación).

V3.73 endurece dos cosas y construye un instrumento:

1. el runtime de producto es **fail-closed** (no arranca sin la UI compilada),
2. el descubrimiento de la IP de LAN **no usa direcciones públicas**,
3. los 7 gates de validación física son **estado registrado**, no prosa.

La fuente de verdad es el código (`launcher/core.py`,
`launcher/process_manager.py`, `backend/services/frontend_dist.py`,
`backend/services/net_interfaces.py`, `scripts/validation_gate.py`) y el CI. Este
candado falla si el código o la documentación vuelven a separarse, siguiendo el
patrón de `test_docs_drift_v372.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BACKEND = ROOT / "backend"
LAUNCHER = ROOT / "launcher"
SCRIPTS = ROOT / "scripts"
CI = ROOT / ".github" / "workflows" / "ci.yml"

GATES = (
    "offline-fisico",
    "maquina-limpia",
    "launcher-windows",
    "dispositivos",
    "audio-stt-tts",
    "journeys",
    "pedagogia",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    """Texto con los espacios colapsados (las frases cruzan líneas)."""
    return " ".join(_read(path).split())


# --- 1. Fail-closed del runtime de producto ---------------------------------


def test_el_launcher_exige_la_ui_compilada():
    core = _read(LAUNCHER / "core.py")
    manager = _read(LAUNCHER / "process_manager.py")

    assert 'REQUIRE_UI_ENV = "ENGLISH_TUTOR_REQUIRE_UI"' in core
    assert "def backend_env(" in core, "desapareció el entorno del proceso de producto"
    assert "env=backend_env()" in manager, (
        "el backend dejó de recibir la exigencia de UI: arrancaría sin interfaz"
    )


def test_el_launcher_no_arranca_sin_artefacto():
    manager = _read(LAUNCHER / "process_manager.py")
    start = manager.split("def start_backend(")[1].split("def ")[0]

    assert "frontend_dist_available()" in start, (
        "arrancar el producto sin comprobar el artefacto deja el fail-closed a medias"
    )
    assert "PreparationError" in start


def test_el_backend_declara_el_modo_de_montaje():
    main = _read(BACKEND / "main.py")

    assert "require_ui_from_env()" in main
    assert "mount_frontend(app, require_ui=" in main, (
        "main.py volvió a montar la UI sin declarar el modo (fail-closed latente)"
    )


def test_el_montaje_distingue_desarrollo_de_producto():
    module = _read(BACKEND / "services" / "frontend_dist.py")

    assert "def require_ui_from_env(" in module
    assert "RuntimeError" in module, "se perdió el camino fail-closed del producto"
    assert "return False" in module, "se perdió el camino fail-open de desarrollo"


def test_los_docs_declaran_el_fail_closed():
    for doc in (
        DOCS / "PREMISAS.md",
        DOCS / "ARQUITECTURA.md",
        ROOT / "README.md",
    ):
        text = _normalized(doc)
        assert "ENGLISH_TUTOR_REQUIRE_UI" in text, (
            f"{doc.name} no declara la variable del runtime de producto"
        )
        assert "fail-closed" in text.lower(), (
            f"{doc.name} no declara el fail-closed del runtime de producto"
        )


# --- 2. Descubrimiento de la IP de LAN sin referencias externas -------------


def test_existe_el_modulo_de_descubrimiento_local():
    module = BACKEND / "services" / "net_interfaces.py"

    assert module.is_file(), "desapareció el descubrimiento de LAN sin salida a red"
    text = _read(module)
    for symbol in ("select_lan_ipv4", "lan_ipv4", "LAN_IP_ENV"):
        assert symbol in text, f"net_interfaces.py perdió {symbol}"


def test_los_consumidores_delegan_en_el_modulo_local():
    for rel, needle in (
        ("services/network.py", "net_interfaces"),
        ("services/tls_cert.py", "net_interfaces"),
    ):
        assert needle in _read(BACKEND / rel), (
            f"backend/{rel} volvió a descubrir la IP por su cuenta"
        )
    core = _read(LAUNCHER / "core.py")
    assert "def select_lan_ipv4(" in core, (
        "el launcher perdió su copia del algoritmo puro de selección"
    )


def test_los_docs_declaran_el_descubrimiento_local():
    for doc in (DOCS / "PREMISAS.md", DOCS / "ARQUITECTURA.md"):
        text = _normalized(doc)
        assert "net_interfaces.py" in text, (
            f"{doc.name} no declara el descubrimiento de LAN sin referencias externas"
        )
        assert "ENGLISH_TUTOR_LAN_IP" in text, (
            f"{doc.name} no declara el override de la IP de LAN"
        )


def test_el_instrumento_de_red_ya_no_declara_la_referencia_publica():
    """El par generado por el eje RA refleja la retirada del socket a 8.8.8.8."""
    data = json.loads(_read(DOCS / "audit" / "generated" / "runtime-audit.json"))
    lan = [t for t in data["touchpoints"] if t["kind"] == "lan"]

    assert lan, "el instrumento de red se quedó sin puntos de LAN"
    for touchpoint in lan:
        assert "8.8.8.8" not in json.dumps(touchpoint["needle"]), (
            "el instrumento sigue declarando la referencia pública retirada"
        )
    assert any(t["file"] == "services/net_interfaces.py" for t in lan), (
        "el descubrimiento local no está declarado en el instrumento"
    )


def test_el_dossier_ra_declara_ra_08_cerrado():
    dossier = _normalized(DOCS / "audit" / "RA-RUNTIME-OFFLINE.md")

    assert "RA-08" in dossier, "el dossier RA no recoge el hallazgo del descubrimiento"
    assert "cerrado en v3.73" in dossier.lower()


# --- 3. El arnés de validación ----------------------------------------------


def test_existe_el_arnes_con_los_tres_subcomandos():
    path = SCRIPTS / "validation_gate.py"

    assert path.is_file(), "no existe el arnés de validación de la release"
    text = _read(path)
    for command in ('"auto"', '"record"', '"status"'):
        assert command in text, f"el arnés perdió el subcomando {command}"
    assert "--strict" in text and "--require-dist" in text


def test_el_arnes_declara_los_siete_gates():
    text = _read(SCRIPTS / "validation_gate.py")

    for gate in GATES:
        assert f'id="{gate}"' in text, f"el arnés no declara el gate {gate}"


def test_el_runbook_declara_los_gates_y_la_puerta():
    runbook = _normalized(DOCS / "audit" / "VALIDATION-RELEASE-V373.md")

    for gate in GATES:
        assert gate in runbook, f"el runbook no declara el gate {gate}"
    assert "status --strict" in runbook, (
        "el runbook no declara la puerta real de V4.0"
    )
    assert "record" in runbook


def test_el_ci_ejecuta_las_comprobaciones_automaticas():
    text = _read(CI)

    assert "validation-gate:" in text, "el CI no ejecuta el arnés de validación"
    assert "validation_gate.py auto" in text
    # `--strict` no puede estar en CI: los gates humanos están pendientes por diseño.
    assert "validation_gate.py status --strict" not in text, (
        "el CI no puede exigir gates de validación física (son acción humana)"
    )


def test_el_arnes_escribe_solo_bajo_docs():
    """Medir la release no puede tocar código, currículum ni datos."""
    text = _read(SCRIPTS / "validation_gate.py")

    for target in ("release-validation.json", "release-validation.md"):
        assert f'GENERATED / "{target}"' in text
    assert '"validation-evidence.json"' in text
    assert text.count("GENERATED = DOCS") == 1
    assert "EVIDENCE = DOCS" in text


def test_la_evidencia_del_repo_es_integra():
    """Si existe evidencia registrada, no puede tener gates ni estados inventados."""
    path = DOCS / "audit" / "validation-evidence.json"
    if not path.is_file():
        return

    data = json.loads(_read(path))
    for gate_id, entry in data.get("gates", {}).items():
        assert gate_id in GATES, f"evidencia de un gate desconocido: {gate_id}"
        assert entry["status"] in ("pending", "pass", "fail", "skip")


# --- 4. Cobertura Windows y matriz de dispositivos --------------------------


def test_el_ci_prueba_windows():
    text = _read(CI)

    assert "launcher-windows:" in text, "el launcher no se prueba en Windows"
    assert "product-origin-windows:" in text, (
        "el origen de producto no se prueba en Windows"
    )
    assert text.count("runs-on: windows-latest") >= 2


def test_la_matriz_de_dispositivos_apunta_al_origen_de_producto():
    text = _read(DOCS / "DEVICE_MATRIX.md")

    assert ":8000" in text
    assert ":5173" not in text, (
        "la matriz sigue documentando el dev server de Vite como runtime"
    )
    assert "touch" in text.lower(), "la matriz no cubre la capa táctil"
    assert "orientación" in text.lower() or "orientacion" in text.lower()


# --- 5. Los P2/P3 de la auditoría de V3.72 ----------------------------------


def test_parked_declara_lo_cerrado_en_v3_73():
    parked = _normalized(DOCS / "audit" / "PARKED.md")

    assert "V3.73" in parked, "PARKED.md no recoge la release de validación"
    assert "RA-08" in parked, "PARKED.md no declara el cierre del descubrimiento de LAN"
    assert "fail-closed" in parked.lower(), (
        "PARKED.md no declara el cierre del runtime de producto"
    )
