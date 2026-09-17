"""Genera (si falta) el certificado TLS autofirmado con el que el backend sirve
la app por HTTPS (V3.72).

Uso:
    python -m scripts.ensure_tls_cert
    python -m scripts.ensure_tls_cert --force      # regenera aunque exista
    python -m scripts.ensure_tls_cert --print-args # solo imprime los flags

Es **idempotente**: si el certificado existe, cubre los SANs requeridos y no está
cerca de caducar, no escribe nada. Pensado para invocarse desde el launcher justo
antes de arrancar `uvicorn --ssl-certfile ... --ssl-keyfile ...`.

El certificado es un **artefacto de máquina**: vive en `backend/data/certs/`, que
está ignorado por git, y nunca se versiona.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.tls_cert import ensure_tls_certificate, ssl_command_flags  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="regenera el certificado aunque ya exista y sea válido",
    )
    parser.add_argument(
        "--print-args",
        action="store_true",
        help="imprime solo los flags de uvicorn (sin generar nada)",
    )
    args = parser.parse_args()

    if args.print_args:
        print(" ".join(ssl_command_flags()))
        return 0

    result = ensure_tls_certificate(force=args.force)
    state = "creado" if result.created else "reutilizado"
    print(f"TLS {state}: {result.cert_path}")
    print(f"  clave: {result.key_path}")
    print(f"  SANs:  {', '.join(result.sans)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
