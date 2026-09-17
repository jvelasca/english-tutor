"""Certificado TLS autofirmado para servir la app por HTTPS (V3.72).

**Por qué HTTPS y no HTTP.** El producto usa el micrófono (`getUserMedia`) desde
speaking, listening, pronunciación y conversación. Los navegadores solo exponen
`navigator.mediaDevices` en un *secure context*: por `http://<IP>` de la LAN es
`undefined` y la grabación se rompe. El dev server de Vite ya servía HTTPS
autofirmado por ese motivo (`@vitejs/plugin-basic-ssl`); al pasar el servido de
la UI al backend (RC-01), el TLS tiene que venir con él.

**Propiedades.** Generación **idempotente** (si el certificado existe y cubre los
SANs requeridos no se toca) y **determinista** en su decisión (misma entrada →
mismo resultado: `created` o no). **No usa la red**: la IP de la LAN se descubre
enumerando las direcciones del propio equipo (`services/net_interfaces.py`,
V3.73) y **no escribe** fuera de `backend/data/certs/`, que está ignorado por
git: el certificado es un artefacto de máquina, no un fichero versionado.

El certificado es **autofirmado**, así que el navegador pedirá aceptarlo una vez
(igual que hacía el dev server de Vite). No se pretende sustituir a una CA: es
una app 100 % local.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path

from config import TLS_ALT_HOSTNAME, TLS_CERT_PATH, TLS_KEY_PATH

# Validez larga: es un certificado de desarrollo local y regenerarlo cada año
# obligaría a que el usuario volviera a aceptar el aviso sin motivo.
CERT_VALIDITY_DAYS = 3650
_KEY_SIZE = 2048


@dataclass(frozen=True)
class CertResult:
    """Resultado de ``ensure_tls_certificate`` (hecho observable, sin ambigüedad)."""

    created: bool
    cert_path: Path
    key_path: Path
    sans: tuple[str, ...]

    @property
    def reloaded(self) -> bool:
        """True si se reutilizó el certificado existente en vez de generarlo."""
        return not self.created


def _local_hostname() -> str:
    """Nombre del host en la red local (sin dominio)."""
    return socket.gethostname().split(".")[0]


def _local_ip() -> str:
    """IP IPv4 de la LAN desde la que se sirve la app (o 127.0.0.1).

    V3.73: la descubre ``services.net_interfaces`` enumerando las direcciones del
    propio equipo, sin ninguna referencia externa (antes: socket UDP perezoso a
    ``8.8.8.8``).
    """
    from services.net_interfaces import lan_ipv4

    return lan_ipv4()


def required_sans(
    hostname: str | None = None,
    lan_ip: str | None = None,
    extra: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """SANs que el certificado debe cubrir, sin duplicados y en orden estable.

    Incluye los nombres por los que el usuario puede llegar a la app: `localhost`,
    `127.0.0.1`, el nombre del equipo, el nombre mDNS (`<equipo>.local`), el alias
    público (`english-tutor.local`) y la IP de la LAN.
    """
    host = hostname if hostname is not None else _local_hostname()
    ip = lan_ip if lan_ip is not None else _local_ip()
    candidates = [
        "localhost",
        "127.0.0.1",
        host,
        f"{host}.local" if host else "",
        TLS_ALT_HOSTNAME,
        ip,
        *extra,
    ]
    seen: list[str] = []
    for value in candidates:
        value = (value or "").strip()
        if value and value not in seen:
            seen.append(value)
    return tuple(seen)


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def certificate_sans(cert_path: Path | None = None) -> tuple[str, ...]:
    """SANs que cubre el certificado en disco (vacío si no se puede leer)."""
    from cryptography import x509

    path = Path(cert_path) if cert_path is not None else TLS_CERT_PATH
    try:
        cert = x509.load_pem_x509_certificate(path.read_bytes())
        extension = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        )
    except Exception:  # noqa: BLE001 — ausente, corrupto o sin SANs: no cubre nada
        return ()
    dns_names = extension.value.get_values_for_type(x509.DNSName)
    ip_addresses = extension.value.get_values_for_type(x509.IPAddress)
    # cryptography >= 42 devuelve los valores ya normalizados (str).
    normalized = {
        *(str(name) for name in dns_names),
        *(str(address) for address in ip_addresses),
    }
    return tuple(sorted(normalized))


def certificate_covers(
    sans: tuple[str, ...], cert_path: Path | None = None
) -> bool:
    """True si el certificado en disco ya cubre todos los SANs requeridos."""
    presente = set(certificate_sans(cert_path))
    return bool(sans) and all(san in presente for san in sans)


def certificate_needs_renewal(
    cert_path: Path | None = None, now: dt.datetime | None = None
) -> bool:
    """True si el certificado caduca en menos de 30 días (o ya caducó)."""
    from cryptography import x509

    path = Path(cert_path) if cert_path is not None else TLS_CERT_PATH
    try:
        cert = x509.load_pem_x509_certificate(path.read_bytes())
    except Exception:  # noqa: BLE001
        return True
    reference = now if now is not None else dt.datetime.now(dt.UTC)
    try:
        expiry = cert.not_valid_after_utc
    except AttributeError:  # pragma: no cover — cryptography < 42
        expiry = cert.not_valid_after.replace(tzinfo=dt.UTC)
    return (expiry - reference) < dt.timedelta(days=30)


def _generate(cert_path: Path, key_path: Path, sans: tuple[str, ...]) -> None:
    """Escribe un par (certificado, clave) autofirmado con los SANs dados."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    now = dt.datetime.now(dt.UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=_KEY_SIZE)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "english-tutor"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "English Tutor"),
        ]
    )
    alt_names: list[x509.GeneralName] = [
        x509.IPAddress(ipaddress.ip_address(san))
        if _is_ip(san)
        else x509.DNSName(san)
        for san in sans
    ]
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=CERT_VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    # Escritura atómica: un proceso concurrente nunca lee un fichero a medias.
    key_tmp = key_path.with_suffix(key_path.suffix + ".part")
    cert_tmp = cert_path.with_suffix(cert_path.suffix + ".part")
    key_tmp.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_tmp.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_tmp.replace(key_path)
    cert_tmp.replace(cert_path)


def ensure_tls_certificate(
    cert_path: Path | None = None,
    key_path: Path | None = None,
    sans: tuple[str, ...] | None = None,
    force: bool = False,
) -> CertResult:
    """Garantiza que existe un certificado autofirmado que cubre los SANs.

    Es **idempotente**: si el certificado y la clave existen, cubren los SANs
    requeridos y no están cerca de caducar, no se regenera nada (``created``
    False) y la llamada es un no-op. Con ``force=True`` se regenera siempre.
    """
    cert = Path(cert_path) if cert_path is not None else TLS_CERT_PATH
    key = Path(key_path) if key_path is not None else TLS_KEY_PATH
    required = sans if sans is not None else required_sans()

    if not force and cert.is_file() and key.is_file():
        if certificate_covers(required, cert) and not certificate_needs_renewal(
            cert
        ):
            return CertResult(
                created=False,
                cert_path=cert,
                key_path=key,
                sans=tuple(certificate_sans(cert)),
            )

    _generate(cert, key, required)
    return CertResult(
        created=True, cert_path=cert, key_path=key, sans=tuple(required)
    )


def ssl_command_flags(
    cert_path: Path | None = None, key_path: Path | None = None
) -> list[str]:
    """Flags de uvicorn para servir por HTTPS con el certificado autofirmado."""
    cert = Path(cert_path) if cert_path is not None else TLS_CERT_PATH
    key = Path(key_path) if key_path is not None else TLS_KEY_PATH
    return ["--ssl-certfile", str(cert), "--ssl-keyfile", str(key)]
