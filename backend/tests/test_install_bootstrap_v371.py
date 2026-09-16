"""Eje RB de V3.71: instalación limpia (bootstrap y verificación previa).

Absorbe los dos hallazgos que los ejes RA y RD trasladaron aquí:

- **RA-04**: en un clon limpio `backend/models/` está vacío (está en `.gitignore`)
  y no había **verificación previa** que dijera qué falta. La respuesta es
  `download_models.py --check`, que informa **sin descargar** y distingue lo que
  es **descarga** de lo que es **local**. El runbook vive en `README.md`.
- **RD-06**: el bootstrap usaba `urlretrieve` **sin timeout** (cuelgue mudo si
  Hugging Face no responde) y la voz **inglesa por defecto** no estaba en el
  catálogo curado, así que `ensure_voice_for_language("en")` **no podía**
  auto-descargarla: en una instalación limpia el inglés solo se obtenía por este
  script o a mano, mientras el español sí se auto-descargaba.

Lo que fijan estos tests es **comportamiento observable**: el catálogo, el
informe y la ruta de auto-descarga. Nada de red ni de descargas reales.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]

# `download_models.py` vive en la raíz del backend (no en `scripts/`), así que se
# importa por ruta para no depender del `sys.path` de `conftest.py`.
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
import download_models  # noqa: E402
from services import tts, voice_downloads  # noqa: E402

# --- RB-01 · La voz inglesa por defecto es alcanzable ------------------------


def test_la_voz_inglesa_por_defecto_esta_en_el_catalogo_curado():
    """RD-06: sin esto, `ensure_voice_for_language("en")` sale sin descargar.

    El default inglés (`config.PIPER_VOICE`) se ofrecía en la UI y se usaba para
    dar clase, pero **no estaba** en `CATALOG`, y `ensure_voice_for_language`
    abandona cuando `spec_for(target)` es `None`. Consecuencia medida: en una
    instalación limpia el español se auto-descargaba y el inglés **no**.
    """
    assert voice_downloads.spec_for(config.PIPER_VOICE) is not None, (
        f"{config.PIPER_VOICE} (voz inglesa por defecto) no está en el catálogo "
        "curado: la descarga en caliente no puede instalarla"
    )
    for voice_id in config.DEFAULT_VOICES.values():
        assert voice_downloads.spec_for(voice_id) is not None, (
            f"la voz por defecto {voice_id} no está en el catálogo curado"
        )


def test_la_voz_inglesa_por_defecto_tiene_la_ruta_real_de_hugging_face():
    """El id y la subcarpeta del catálogo deben cuadrar con el repo de Piper."""
    spec = voice_downloads.spec_for(config.PIPER_VOICE)
    assert spec is not None
    assert spec.path == "en/en_US/lessac/medium", (
        "la ruta del catálogo no coincide con la del repo rhasspy/piper-voices: "
        "la descarga daría 404"
    )


def test_el_ingles_por_defecto_se_puede_auto_descargar(monkeypatch):
    """La consecuencia observable de RB-01: la ruta de auto-descarga llega al final.

    Se doblan la lista de voces instaladas (vacía) y la descarga (no-op), así que
    el test mide **si se decide descargar**, no si hay red.
    """
    descargas: list[str] = []
    monkeypatch.setattr(tts, "list_voices", lambda: [])
    monkeypatch.setattr(tts, "_VOICE_ENSURE_FAILED", {})
    monkeypatch.setattr(
        voice_downloads, "download_voice", lambda voice_id: descargas.append(voice_id)
    )

    assert tts.ensure_voice_for_language("en") is True
    assert descargas == [config.PIPER_VOICE], (
        "el inglés por defecto no se intentó descargar: el catálogo no lo cubre"
    )


# --- RB-02 · El bootstrap no descarga sin límite -----------------------------


def _bootstrap_code() -> str:
    """Código de `download_models.py` sin docstrings ni comentarios.

    El guard busca **implementación**, no prosa: el docstring *sí* debe poder
    explicar que antes se usaba `urlretrieve` (es la evidencia del hallazgo).
    """
    import ast

    source = (BACKEND / "download_models.py").read_text(encoding="utf-8")
    code = source
    for node in ast.walk(ast.parse(source)):
        if isinstance(
            node,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                code = code.replace(doc, "")
    return "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith("#")
    )


def test_el_bootstrap_no_usa_urlretrieve_ni_construye_urls():
    """RD-06: el `timeout` era inerte porque `urlretrieve` no lo acepta.

    El bootstrap tenía su propia copia de la URL base y de la ruta de la voz. Al
    delegar en el catálogo, hereda el timeout real y la verificación de tamaño de
    `services/voice_downloads`, y no puede desviarse del id que usa la app.

    Se prohíbe **construir URLs** (`https://`) y toda primitiva de red propia;
    nombrar el origen como dato (`huggingface.co`) sí está bien: es justo lo que
    el informe debe declarar.
    """
    code = _bootstrap_code()
    for prohibido in ("urlretrieve", "PIPER_BASE", "urlopen", "https://"):
        assert prohibido not in code, (
            f"`download_models.py` vuelve a tener {prohibido!r}: la descarga debe "
            "delegar en el catálogo curado (que es quien aplica el timeout real)"
        )


def test_el_bootstrap_instala_todas_las_voces_por_defecto(monkeypatch):
    """Recorre `config.DEFAULT_VOICES`, no una lista escrita a mano."""
    instaladas: list[str] = []
    monkeypatch.setattr(download_models, "_ensure_voice", instaladas.append)

    download_models.download_piper()

    assert set(instaladas) == set(config.DEFAULT_VOICES.values())


# --- RB-03 · Verificación previa (RA-04) ------------------------------------


def test_el_informe_de_instalacion_cubre_todas_las_voces_por_defecto():
    """Una voz por defecto nueva no puede quedarse fuera de la verificación."""
    report = download_models.install_report()
    ids = {item["id"] for item in report}
    for voice_id in config.DEFAULT_VOICES.values():
        for suffix in (".onnx", ".onnx.json"):
            assert f"piper:{voice_id}{suffix}" in ids


def test_el_informe_distingue_descarga_de_local():
    """RA-04: hay que poder decir qué falta, qué es descarga y qué es local."""
    report = download_models.install_report()
    assert report, "el informe de instalación está vacío"

    for item in report:
        assert item["kind"] in (download_models.DOWNLOAD, download_models.LOCAL), (
            f"{item['id']} declara un tipo desconocido: {item['kind']!r}"
        )
        assert item["origin"], f"{item['id']} no declara de dónde sale"

    kinds = {item["kind"] for item in report}
    assert kinds == {download_models.DOWNLOAD, download_models.LOCAL}, (
        "el informe debe incluir descargas y datos locales"
    )


def test_el_informe_declara_que_ollama_no_lo_comprueba_este_script():
    """`ollama pull` es un paso manual (decisión B): el script no puede verificarlo.

    Se declara `exists=None` en lugar de mentir con un `False` que parecería un
    artefacto de disco que falta.
    """
    items = [
        i
        for i in download_models.install_report()
        if i["id"].startswith("ollama:")
    ]
    assert len(items) == 1
    assert items[0]["exists"] is None
    assert config.DEFAULT_MODEL in items[0]["id"]


def test_la_base_de_datos_es_un_dato_local_no_una_descarga():
    """El fichero SQLite se crea al arrancar: no debe contar como descarga.

    Y su ruta sale de `repositories.db` (fuente única), no de una copia local.
    """
    from repositories import db

    items = [
        i
        for i in download_models.install_report()
        if i["kind"] == download_models.LOCAL
    ]
    assert [i["id"] for i in items] == [f"sqlite:{db.DB_PATH.name}"]


def test_la_verificacion_previa_no_descarga_nada(monkeypatch, capsys):
    """`--check` es de SOLO LECTURA: es una verificación, no una instalación."""

    def _explota(*args, **kwargs):
        raise AssertionError("la verificación previa intentó descargar")

    monkeypatch.setattr(voice_downloads, "download_voice", _explota)
    monkeypatch.setattr(download_models, "_ensure_voice", _explota)
    monkeypatch.setattr(sys, "argv", ["download_models.py", "--check"])

    code = download_models.main()
    salida = capsys.readouterr().out

    assert code in (0, 1), "el informe debe devolver un código de salida predecible"
    assert "tipo:" in salida, "el informe no declara el tipo de cada artefacto"


def test_el_modo_check_json_es_parseable(monkeypatch, capsys):
    """El informe tiene una salida legible por máquina (para el runbook y CI)."""
    import json

    monkeypatch.setattr(sys, "argv", ["download_models.py", "--json"])
    download_models.main()

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"items", "missing"}
    assert payload["items"]


def test_faltantes_solo_cuenta_lo_comprobable_en_disco():
    """Lo que este script no puede comprobar (Ollama) no es un «falta»."""
    report = download_models.install_report()
    faltan = download_models.missing_offline_artifacts(report)

    assert all(item["exists"] is False for item in faltan)
    assert not any(item["id"].startswith("ollama:") for item in faltan)


def test_el_runbook_del_readme_incluye_ollama_y_la_verificacion_previa():
    """RA-04: el runbook debe existir y decir el paso de Ollama y el de `--check`."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "ollama pull" in readme, "el runbook no dice cómo obtener el modelo"
    assert "--check" in readme, "el runbook no documenta la verificación previa"
    assert config.DEFAULT_MODEL in readme, (
        f"el runbook no nombra el modelo por defecto real ({config.DEFAULT_MODEL})"
    )
