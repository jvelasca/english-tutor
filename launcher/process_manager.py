"""Preparación del entorno y gestión del proceso de producto (V3.72).

Desde V3.72 (RC-01) el producto es **un solo proceso**: uvicorn sirve la API y la
UI compilada (`frontend/dist`) en el mismo origen HTTPS. Antes eran dos procesos
(uvicorn + dev server de Vite) y Node era requisito de **ejecución**.

Lo que queda como trabajo previo en una instalación limpia es:
1. generar el **certificado TLS autofirmado** (si falta), y
2. **compilar la UI** con `npm run build` (si `frontend/dist` no existe).

Ambas cosas son idempotentes y se hacen una sola vez; después arrancar es solo
levantar uvicorn. Node sigue siendo necesario para **compilar**, no para ejecutar.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from core import (
    BACKEND_DIR,
    FRONTEND_DIR,
    backend_command,
    backend_env,
    ensure_cert_command,
    frontend_build_command,
    frontend_dist_available,
)

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_IS_WINDOWS = os.name == "nt"

# Cotas holgadas: compilar la UI en un portátil lento puede tardar, pero nunca
# debe colgar la preparación de forma indefinida.
_CERT_TIMEOUT_S = 60
_BUILD_TIMEOUT_S = 600


class PreparationError(RuntimeError):
    """El entorno no se puede preparar (falta Node, falla el build o el cert)."""


def taskkill_command(pid: int) -> list[str]:
    """Comando para matar el árbol de procesos (Windows)."""
    return ["taskkill", "/F", "/T", "/PID", str(pid)]


class ProcessManager:
    """Prepara el entorno y arranca/para el proceso de producto (uvicorn)."""

    def __init__(self) -> None:
        self.backend: subprocess.Popen | None = None

    @staticmethod
    def _log_path(name: str) -> Path:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        return _LOG_DIR / f"{name}.log"

    def ensure_certificate(self) -> None:
        """Genera el certificado TLS autofirmado si falta (idempotente)."""
        try:
            result = subprocess.run(
                ensure_cert_command(),
                cwd=str(BACKEND_DIR),
                capture_output=True,
                text=True,
                timeout=_CERT_TIMEOUT_S,
            )
        except FileNotFoundError as exc:
            raise PreparationError(
                "No se encuentra el Python del backend (backend/.venv). "
                "Revisa la instalación de requisitos."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise PreparationError(
                "La generación del certificado TLS tardó demasiado."
            ) from exc
        if result.returncode != 0:
            detalle = (result.stderr or result.stdout or "").strip()[-400:]
            raise PreparationError(
                f"No se pudo generar el certificado TLS local. {detalle}"
            )

    def ensure_frontend_dist(self) -> bool:
        """Compila `frontend/dist` si falta. Devuelve True si compiló ahora.

        Solo se compila lo que falta: si el artefacto existe se reutiliza, así
        que un arranque normal no cuesta nada. La salida de `npm` va al log del
        launcher (`frontend.log`) para que sea diagnosticable desde la GUI.
        """
        if frontend_dist_available():
            return False
        with open(self._log_path("frontend"), "ab") as log:
            log.write(b"\n=== npm run build (V3.73) ===\n")
            log.flush()
            try:
                result = subprocess.run(
                    frontend_build_command(),
                    cwd=str(FRONTEND_DIR),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=_BUILD_TIMEOUT_S,
                )
            except FileNotFoundError as exc:
                raise PreparationError(
                    "No se encuentra `npm`. Instala Node.js 18+ para compilar la "
                    "interfaz la primera vez (después ya no hace falta para usar "
                    "la app)."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise PreparationError(
                    "La compilación de la interfaz tardó demasiado "
                    f"(>{_BUILD_TIMEOUT_S}s). Revisa el log de la UI."
                ) from exc
        if result.returncode != 0:
            raise PreparationError(
                "No se pudo compilar la interfaz (`npm run build`). Revisa el log "
                "de la UI para ver el error."
            )
        # V3.73: doble condición explícita. Un build con código 0 que no deja el
        # artefacto (o que lo deja a medias) no puede arrancar el producto.
        if not frontend_dist_available():
            raise PreparationError(
                "`npm run build` terminó sin error pero no dejó el artefacto de "
                "la UI (`frontend/dist/index.html`). Revisa el log de la UI."
            )
        return True

    def prepare(self) -> None:
        """Deja el entorno listo para arrancar: certificado + UI compilada."""
        self.ensure_certificate()
        self.ensure_frontend_dist()

    def start_backend(self) -> None:
        if self.backend_running():
            return
        # V3.73: guardia de última hora. `prepare()` ya compila el artefacto y
        # eleva si no puede, pero arrancar sin UI debe ser imposible por diseño:
        # el producto es fail-closed y no puede parecer listo sin interfaz.
        if not frontend_dist_available():
            raise PreparationError(
                "La interfaz no está compilada (falta `frontend/dist/index.html`). "
                "Compílala con `npm run build` en `frontend/` (o pulsa «Iniciar "
                "app», que la compila la primera vez)."
            )
        with open(self._log_path("backend"), "ab") as log:
            self.backend = subprocess.Popen(
                backend_command(),
                cwd=str(BACKEND_DIR),
                stdout=log,
                stderr=subprocess.STDOUT,
                # El backend exige la UI compilada: mismo contrato que la guardia
                # de arriba, pero del lado del servidor (V3.73).
                env=backend_env(),
            )

    def stop_all(self) -> None:
        self._stop(self.backend)
        self.backend = None

    def _stop(self, proc: subprocess.Popen | None) -> None:
        if proc is None:
            return
        if _IS_WINDOWS:
            try:
                subprocess.run(
                    taskkill_command(proc.pid), capture_output=True, timeout=10
                )
            except Exception:  # noqa: BLE001
                pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    def backend_running(self) -> bool:
        return self.backend is not None and self.backend.poll() is None
