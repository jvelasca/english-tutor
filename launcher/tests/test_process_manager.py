"""Tests de process_manager.py (preparación del entorno y proceso de producto)."""
import pytest

from process_manager import PreparationError, ProcessManager, taskkill_command


def test_taskkill_command():
    assert taskkill_command(1234) == ["taskkill", "/F", "/T", "/PID", "1234"]


def test_initial_state_not_running():
    pm = ProcessManager()
    assert pm.backend is None
    assert pm.backend_running() is False


def test_no_hay_segundo_proceso_de_producto():
    """V3.72 (RC-01): la UI la sirve el backend, no un dev server de Vite."""
    pm = ProcessManager()
    assert not hasattr(pm, "frontend")
    assert not hasattr(pm, "start_frontend")
    assert not hasattr(pm, "frontend_running")


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stderr: str = "", stdout: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def test_ensure_certificate_no_falla_si_el_certificado_ya_existe(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompleted()

    monkeypatch.setattr("process_manager.subprocess.run", fake_run)
    pm = ProcessManager()

    pm.ensure_certificate()

    assert len(calls) == 1
    assert calls[0][-2:] == ["-m", "scripts.ensure_tls_cert"]


def test_ensure_certificate_falla_con_mensaje_claro_si_el_python_no_existe(
    monkeypatch,
):
    def boom(cmd, **kwargs):
        raise FileNotFoundError("python.exe")

    monkeypatch.setattr("process_manager.subprocess.run", boom)

    with pytest.raises(PreparationError, match="venv"):
        ProcessManager().ensure_certificate()


def test_ensure_certificate_falla_si_el_script_devuelve_error(monkeypatch):
    monkeypatch.setattr(
        "process_manager.subprocess.run",
        lambda cmd, **kwargs: _FakeCompleted(returncode=1, stderr="boom"),
    )

    with pytest.raises(PreparationError, match="certificado"):
        ProcessManager().ensure_certificate()


def test_ensure_frontend_dist_no_compila_si_el_artefacto_ya_existe(monkeypatch):
    monkeypatch.setattr(
        "process_manager.frontend_dist_available", lambda: True
    )

    def boom(*args, **kwargs):  # pragma: no cover — no debe llamarse
        raise AssertionError("no debe compilar si el dist ya existe")

    monkeypatch.setattr("process_manager.subprocess.run", boom)

    assert ProcessManager().ensure_frontend_dist() is False


def test_ensure_frontend_dist_compila_y_devuelve_que_lo_hizo(monkeypatch, tmp_path):
    compilado = {"value": False}
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        "process_manager.frontend_dist_available", lambda: compilado["value"]
    )

    def fake_run(cmd, **kwargs):
        compilado["value"] = True  # el build deja el artefacto en disco
        assert cmd[-1] == "build"
        return _FakeCompleted()

    monkeypatch.setattr("process_manager.subprocess.run", fake_run)

    assert ProcessManager().ensure_frontend_dist() is True


def test_ensure_frontend_dist_falla_sin_npm(monkeypatch, tmp_path):
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("process_manager.frontend_dist_available", lambda: False)

    def boom(cmd, **kwargs):
        raise FileNotFoundError("npm")

    monkeypatch.setattr("process_manager.subprocess.run", boom)

    with pytest.raises(PreparationError, match="Node"):
        ProcessManager().ensure_frontend_dist()


def test_ensure_frontend_dist_falla_si_el_build_no_deja_artefacto(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("process_manager.frontend_dist_available", lambda: False)
    monkeypatch.setattr(
        "process_manager.subprocess.run",
        lambda cmd, **kwargs: _FakeCompleted(returncode=0),
    )

    with pytest.raises(PreparationError, match="artefacto"):
        ProcessManager().ensure_frontend_dist()


def test_prepare_hace_certificado_y_dist_en_orden(monkeypatch):
    events: list[str] = []
    pm = ProcessManager()
    monkeypatch.setattr(pm, "ensure_certificate", lambda: events.append("cert"))
    monkeypatch.setattr(
        pm, "ensure_frontend_dist", lambda: events.append("dist")
    )

    pm.prepare()

    assert events == ["cert", "dist"]


def test_ensure_port_free_falla_si_el_puerto_esta_ocupado(monkeypatch):
    """V3.75.3: un puerto tomado se explica antes de arrancar, no después.

    Antes, un `uvicorn --reload` de desarrollo olvidado en 8000 hacía que el
    arranque *pareciera* correcto: el backend moría al enlazar (`WinError 10048`)
    y la GUI solo decía «🔴 Detenido», sin motivo.
    """
    monkeypatch.setattr("process_manager.port_in_use", lambda **kwargs: True)

    with pytest.raises(PreparationError, match="puerto 8000"):
        ProcessManager().ensure_port_free()


def test_ensure_port_free_pasa_si_el_puerto_esta_libre(monkeypatch):
    monkeypatch.setattr("process_manager.port_in_use", lambda **kwargs: False)

    assert ProcessManager().ensure_port_free() is None


def test_rotate_log_if_large_rota_una_generacion(tmp_path):
    """V3.75.3: el log no puede crecer sin límite.

    `backend.log` llegó a 87 MB (1,3 M de líneas) en el equipo del autor: nada lo
    acotaba y cada refresco de la GUI lo leía entero.
    """
    from process_manager import rotate_log_if_large

    log = tmp_path / "backend.log"
    log.write_text("x" * 500, encoding="utf-8")

    assert rotate_log_if_large(log, max_bytes=100) is True
    assert not log.exists()
    assert (tmp_path / "backend.log.1").read_text(encoding="utf-8") == "x" * 500


def test_rotate_log_if_large_no_toca_un_log_pequeno(tmp_path):
    from process_manager import rotate_log_if_large

    log = tmp_path / "backend.log"
    log.write_text("corto", encoding="utf-8")

    assert rotate_log_if_large(log, max_bytes=10_000) is False
    assert log.read_text(encoding="utf-8") == "corto"


def test_rotate_log_if_large_sobrescribe_la_generacion_anterior(tmp_path):
    from process_manager import rotate_log_if_large

    (tmp_path / "backend.log.1").write_text("vieja", encoding="utf-8")
    log = tmp_path / "backend.log"
    log.write_text("nueva" * 100, encoding="utf-8")

    assert rotate_log_if_large(log, max_bytes=10) is True
    assert (tmp_path / "backend.log.1").read_text(encoding="utf-8") == "nueva" * 100


def test_open_log_rota_al_abrir(monkeypatch, tmp_path):
    """La rotación vive en el único punto de escritura, no en cada llamada."""
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path)
    monkeypatch.setattr("process_manager._MAX_LOG_BYTES", 10)

    (tmp_path / "backend.log").write_text("x" * 100, encoding="utf-8")

    pm = ProcessManager()
    with pm._open_log("backend") as handle:
        handle.write(b"nuevo\n")

    assert (tmp_path / "backend.log.1").read_text(encoding="utf-8") == "x" * 100
    assert (tmp_path / "backend.log").read_bytes() == b"nuevo\n"


def test_backend_log_since_lee_solo_el_tramo_nuevo(monkeypatch, tmp_path):
    """No se atribuye a este arranque un fallo de un arranque anterior."""
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path)

    pm = ProcessManager()
    (tmp_path / "backend.log").write_text("FALLO-ANTIGUO\n", encoding="utf-8")
    offset = pm.backend_log_size()
    with open(tmp_path / "backend.log", "ab") as handle:
        handle.write(b"arranque-de-ahora\n")

    tramo = pm.backend_log_since(offset)

    assert "arranque-de-ahora" in tramo
    assert "FALLO-ANTIGUO" not in tramo


def test_backend_log_since_resiste_una_rotacion(monkeypatch, tmp_path):
    """Si el log rotó, el fichero es más pequeño que el offset: se lee su cola."""
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path)

    pm = ProcessManager()
    (tmp_path / "backend.log").write_text("log-que-roto\n", encoding="utf-8")

    tramo = pm.backend_log_since(offset=10_000)

    assert "log-que-roto" in tramo


def test_start_backend_no_arranca_dos_veces(monkeypatch, tmp_path):
    monkeypatch.setattr("process_manager._LOG_DIR", tmp_path / "logs")
    # V3.73: arrancar el producto exige la UI compilada (fail-closed).
    monkeypatch.setattr("process_manager.frontend_dist_available", lambda: True)
    lanzados: list[list[str]] = []

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            lanzados.append(cmd)

        def poll(self):
            return None

    monkeypatch.setattr("process_manager.subprocess.Popen", _FakePopen)
    pm = ProcessManager()

    pm.start_backend()
    pm.start_backend()

    assert len(lanzados) == 1
    assert "uvicorn" in lanzados[0]


def test_stop_all_limpia_el_proceso(monkeypatch):
    pm = ProcessManager()

    class _FakePopen:
        pid = 4321

        def poll(self):
            return 0

    pm.backend = _FakePopen()
    monkeypatch.setattr(pm, "_stop", lambda proc: None)

    pm.stop_all()

    assert pm.backend is None
    assert pm.backend_running() is False
