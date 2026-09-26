"""Deriva documental del runtime de producto en V3.72 (eje UA, cierre de RC-01).

V3.71 declaró la frontera **contraria** («el backend no sirve `frontend/dist`; el
launcher arranca `npm run dev`; Node + npm son requisito de EJECUCIÓN»). V3.72
implementó el servido real del artefacto y el producto pasó a **un solo proceso
HTTPS en `:8000`**. Estos candados fijan la frontera **actual** y **fallan** si el
código o la documentación vuelven a separarse: la fuente de verdad es el código
(`launcher/core.py`, `backend/main.py`, `backend/services/frontend_dist.py`,
`.github/workflows/ci.yml`) y los artefactos reales, nunca la documentación.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LAUNCHER = ROOT / "launcher"
BACKEND = ROOT / "backend"
CI = ROOT / ".github" / "workflows" / "ci.yml"

# Frases-ancla de la declaración nueva. Si desaparecen, la documentación dejó de
# decir la verdad sobre el runtime.
ANCLA_FRONTERA = "Node + npm son requisito de COMPILACIÓN"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    """Texto con los espacios colapsados (las frases cruzan líneas)."""
    return " ".join(_read(path).split())


def _launcher_function_source(name: str) -> str:
    """Cuerpo de una función de `launcher/core.py`, leído como TEXTO.

    No se importa el módulo a propósito: `core` y `status` son nombres genéricos
    y meterlos en `sys.modules` desde la suite del backend podría ensombrecer
    otros imports.
    """
    lines = _read(LAUNCHER / "core.py").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(f"def {name}(")),
        None,
    )
    assert start is not None, f"launcher/core.py no define {name}()"
    body: list[str] = []
    for line in lines[start:]:
        if body and line and not line.startswith((" ", "\t")):
            break  # siguiente definición de nivel de módulo
        body.append(line)
    return "\n".join(body)


# --- RC-01 cerrado: el backend sirve el artefacto ---------------------------


def test_el_backend_monta_el_artefacto_de_produccion():
    """RC-01: `frontend/dist` lo sirve el backend (assets + fallback SPA)."""
    assert "mount_frontend" in _read(BACKEND / "main.py"), (
        "main.py ya no monta `frontend/dist`: la declaración de RC-01 "
        "(docs/PREMISAS.md §3, docs/ARQUITECTURA.md) dejaría de ser cierta"
    )
    module = _read(BACKEND / "services" / "frontend_dist.py")
    assert "StaticFiles" in module and "FileResponse" in module, (
        "el servido del artefacto perdió sus piezas (assets o fallback SPA)"
    )
    # Fail-open declarado: sin artefacto no se monta nada y no se rompe.
    assert "return False" in module, (
        "el montaje dejó de ser fail-open: sin `dist` el arranque debe seguir vivo"
    )


def test_el_launcher_no_arranca_el_dev_server_de_vite():
    """El runtime de producto ya no es `npm run dev` (queda como modo de dev)."""
    build = _launcher_function_source("frontend_build_command")
    assert '"build"' in build, (
        "el launcher dejó de compilar el artefacto: sin `dist` no hay UI"
    )
    dev = _launcher_function_source("frontend_dev_command")
    assert '"dev"' in dev, (
        "se perdió el comando del modo de desarrollo (documentado en README)"
    )

    manager = _read(LAUNCHER / "process_manager.py")
    for forbidden in ("start_frontend", "frontend_running"):
        assert forbidden not in manager, (
            f"`{forbidden}` volvió al launcher: el producto es un solo proceso"
        )
    assert "ensure_frontend_dist" in manager, (
        "desapareció la compilación del artefacto en la preparación del entorno"
    )


def test_el_producto_es_un_solo_origen_https_en_el_8000():
    core = _read(LAUNCHER / "core.py")
    assert "FRONTEND_PORT = BACKEND_PORT" in core, (
        "el launcher volvió a anunciar un segundo puerto para la UI"
    )
    assert "BACKEND_PORT = 8000" in core

    backend = _launcher_function_source("backend_command")
    assert "--ssl-certfile" in backend and "--ssl-keyfile" in backend, (
        "el backend dejó de servirse por HTTPS: en la LAN se rompería el micrófono"
    )

    network = _read(BACKEND / "routers" / "network.py")
    assert "FRONTEND_PORT = 8000" in network, (
        "/api/network vuelve a anunciar el puerto del dev server de Vite"
    )


def test_el_firewall_abre_solo_el_puerto_de_producto():
    script = _read(LAUNCHER / "allow-firewall.ps1")
    ports_line = next(
        line for line in script.splitlines() if line.strip().startswith("$ports")
    )
    assert "$ports = @(8000)" in ports_line, (
        "allow-firewall.ps1 debe abrir un único puerto (el de producto)"
    )
    assert "5173" not in ports_line, (
        "el firewall sigue abriendo el puerto del dev server de Vite"
    )


def test_el_certificado_tls_lo_genera_el_backend_y_no_se_versiona():
    script = BACKEND / "scripts" / "ensure_tls_cert.py"
    assert script.is_file(), "falta el generador del certificado TLS"
    assert "cryptography" in _read(BACKEND / "requirements.txt"), (
        "el generador del certificado depende de `cryptography`"
    )
    gitignore = _read(ROOT / ".gitignore")
    assert "backend/data/" in gitignore, (
        "el certificado vive en backend/data/: debe seguir ignorado por git"
    )


def test_el_ci_prueba_el_servido_estatico_por_https():
    """El humo del origen de producto: uvicorn+TLS sobre el `dist` construido."""
    text = _read(CI)
    assert "product-origin" in text, (
        "el CI perdió el job que arranca el producto de verdad (UI + API)"
    )
    assert "ensure_tls_cert" in text and "--ssl-certfile" in text, (
        "el CI no arranca uvicorn con TLS: el servido estático no estaría probado"
    )
    assert "127.0.0.1:8000" in text or "localhost:8000" in text, (
        "el humo del CI no comprueba el origen de producto"
    )
    # Debe comprobar que la RAÍZ sirve la UI (no basta con que la API responda).
    assert "grep -qi" in text and "<html" in text, (
        "el humo del CI no comprueba que la raíz devuelva el HTML de la UI"
    )


# --- §UC · «por qué esta actividad» en las superficies que lo descartaban ---

# Superficies que RECIBEN el `why` declarado por el motor y deben pintarlo.
# V3.85.0: la cola de repaso del diccionario deja de ser una lista de filas
# (`ReviewQueueSection`) y pasa a ser una sesión encadenada (`ReviewToday`), que
# es quien sigue pintando la traza de la palabra que se está trabajando.
SUPERFICIES_DEL_PORQUE = (
    "components/NextBestCard.tsx",
    "components/NextStep.tsx",
    "features/vocabulary/ReviewToday.tsx",
)


def test_las_superficies_del_porque_usan_la_pieza_compartida():
    """V3.72: el `why` declarado por el servidor se pinta donde se recibe.

    `NextStep` (el pie «Next» que ve el alumno al terminar cualquier práctica) y
    las filas de la cola de repaso **descartaban** el `why` que ya venía en la
    respuesta del motor. Si alguien vuelve a soltar esa línea, la explicación
    desaparece sin que nada avise; este candado lo dice.
    """
    frontend = ROOT / "frontend" / "src"
    piece = frontend / "components" / "WhyThisActivity.tsx"
    assert piece.is_file(), "desapareció la pieza compartida del «por qué»"
    body = _read(piece)
    assert "home.whyThisActivity" in body, (
        "la pieza dejó de usar la etiqueta declarada (`home.whyThisActivity`)"
    )
    assert body.count("return null") >= 1, (
        "la pieza dejó de ser honesta: sin `why` ni `because` no pinta nada"
    )
    for rel in SUPERFICIES_DEL_PORQUE:
        assert "WhyThisActivity" in _read(frontend / rel), (
            f"{rel} dejó de mostrar el «por qué» declarado por el motor"
        )


def test_los_docs_declaran_la_extension_del_porque():
    journey = _normalized(DOCS / "audit" / "F-UX-JOURNEY.md")
    # V3.85.0: la superficie de repaso se llama `ReviewToday`; el nombre viejo
    # (`ReviewQueueSection`) se conserva porque el documento es histórico.
    for surface in ("NextStep", "ReviewQueueSection", "ReviewToday", "WhyThisActivity"):
        assert surface in journey, (
            f"F-UX-JOURNEY.md no declara la superficie del «por qué» {surface}"
        )
    parked = _normalized(DOCS / "audit" / "PARKED.md")
    assert "«Por qué esta actividad» (Q5 de `F-UX-JOURNEY.md`)" in parked, (
        "PARKED.md no declara la extensión del «por qué» entre lo cerrado en V3.72"
    )


# --- La declaración escrita (PREMISAS/ARQUITECTURA/README/BETA_GATES) -------


def test_docs_declaran_la_nueva_frontera_del_runtime():
    for doc in (DOCS / "PREMISAS.md", DOCS / "ARQUITECTURA.md", ROOT / "README.md"):
        text = _normalized(doc)
        assert "frontend/dist" in text, f"{doc.name} no declara `frontend/dist`"
        assert ANCLA_FRONTERA in text, (
            f"{doc.name} no declara Node + npm como requisito de COMPILACIÓN"
        )
        assert "npm run dev" in text, (
            f"{doc.name} no declara el modo de desarrollo (`npm run dev`)"
        )

    for doc in (DOCS / "PREMISAS.md", DOCS / "ARQUITECTURA.md"):
        assert "rc-runtime-producto.md" in _normalized(doc).lower(), (
            f"{doc.name} no enlaza el dossier del eje RC"
        )
        assert "test_docs_drift_v372.py" in _normalized(doc), (
            f"{doc.name} no declara qué test fija la frontera"
        )


def test_el_dossier_rc_declara_rc_01_cerrado():
    dossier = _normalized(DOCS / "audit" / "RC-RUNTIME-PRODUCTO.md")
    assert "RC-01" in dossier and "CERRADO en V3.72" in dossier, (
        "el dossier RC no declara el cierre de RC-01 en V3.72"
    )


def test_parked_retira_rc_01_de_la_deuda_abierta():
    parked = _normalized(DOCS / "audit" / "PARKED.md")
    # Sigue nombrado (es historia), pero ya no como trabajo pendiente con fase.
    assert "RC-01" in parked, "PARKED perdió la referencia a RC-01"
    assert "RC-01 · Servido de `frontend/dist` → V3.72/V3.73" not in parked, (
        "PARKED sigue declarando RC-01 como deuda con fase abierta"
    )


# --- §UE · i18n: el informe es un artefacto y el checker es un gate ---------

def test_el_checker_i18n_es_gate_en_el_ci():
    """El checker de cobertura i18n corre en CI en modo estricto.

    Sin esto, «dejar el checker en el gate» es una promesa verbal: la higiene de
    claves huérfanas volvería a acumularse sin que nada fallara.
    """
    text = _read(CI)
    assert "check_i18n_coverage.py" in text, (
        "el CI no ejecuta el checker de cobertura i18n"
    )
    assert "--strict" in text, (
        "el checker i18n corre en CI sin `--strict`: las huérfanas no fallan"
    )


def test_el_informe_i18n_regenerado_no_tiene_huerfanas():
    """El artefacto real del checker declara 0 huérfanas / 0 duplicadas / 0 vacías.

    Se lee el JSON generado (no la promesa de la release note): si alguien vuelve
    a dejar claves muertas, este candado lo dice antes del gate.
    """
    import json

    report_path = DOCS / "audit" / "generated" / "i18n-report.json"
    report = json.loads(_read(report_path))
    assert report["unused_keys"] == [], (
        f"quedan claves i18n huérfanas: {report['unused_keys'][:10]}"
    )
    assert report["duplicate_keys"] == []
    assert report["empty_translations"] == []
    # El checker no puede declarar huérfana una familia dinámica viva: `ns:` de la
    # página compartida de quiz (`${ns}.${key}`) debe estar entre los prefijos.
    prefixes = report["dynamic_prefixes"]
    assert "gramRoutes." in prefixes and "vocRoutes." in prefixes, (
        "el checker perdió la indirección por namespace (`ns: \"gramRoutes\"`)"
    )
