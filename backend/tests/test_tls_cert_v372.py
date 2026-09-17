"""Certificado TLS autofirmado para servir la app por HTTPS (V3.72).

Cada test fija una propiedad observable del artefacto (SANs, idempotencia,
renovación por SANs incompletos, atomicidad) sin depender de la red ni del
certificado real de la máquina: se trabaja siempre contra ``tmp_path``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from services import tls_cert
from services.tls_cert import (
    CERT_VALIDITY_DAYS,
    certificate_covers,
    certificate_needs_renewal,
    certificate_sans,
    ensure_tls_certificate,
    required_sans,
    ssl_command_flags,
)

SANS_TEST = ("localhost", "127.0.0.1", "mi-pc", "mi-pc.local", "192.168.1.42")


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "certs" / "cert.pem", tmp_path / "certs" / "key.pem"


def test_genera_un_certificado_autofirmado_con_los_sans_requeridos(tmp_path):
    cert, key = _paths(tmp_path)

    result = ensure_tls_certificate(cert, key, sans=SANS_TEST)

    assert result.created is True
    assert result.reloaded is False
    assert cert.is_file() and key.is_file()
    assert certificate_covers(SANS_TEST, cert) is True
    # Autofirmado: issuer == subject y no es una CA.
    parsed = x509.load_pem_x509_certificate(cert.read_bytes())
    assert parsed.issuer == parsed.subject
    assert parsed.extensions.get_extension_for_class(
        x509.BasicConstraints
    ).value.ca is False


def test_la_clave_privada_se_escribe_sin_cifrar_y_es_usable(tmp_path):
    cert, key = _paths(tmp_path)

    ensure_tls_certificate(cert, key, sans=SANS_TEST)

    loaded = serialization.load_pem_private_key(key.read_bytes(), password=None)
    assert loaded.key_size == 2048


def test_es_idempotente_cuando_el_certificado_ya_cubre_los_sans(tmp_path):
    cert, key = _paths(tmp_path)

    first = ensure_tls_certificate(cert, key, sans=SANS_TEST)
    mtime = cert.stat().st_mtime_ns
    second = ensure_tls_certificate(cert, key, sans=SANS_TEST)

    assert first.created is True
    assert second.created is False
    assert second.reloaded is True
    assert cert.stat().st_mtime_ns == mtime  # no se reescribió el fichero
    assert set(second.sans) >= set(SANS_TEST)


def test_regenera_cuando_el_certificado_no_cubre_todos_los_sans(tmp_path):
    cert, key = _paths(tmp_path)
    ensure_tls_certificate(cert, key, sans=("localhost",))

    result = ensure_tls_certificate(cert, key, sans=SANS_TEST)

    assert result.created is True
    assert certificate_covers(SANS_TEST, cert) is True


def test_force_regenera_aunque_el_certificado_sea_valido(tmp_path):
    cert, key = _paths(tmp_path)
    ensure_tls_certificate(cert, key, sans=SANS_TEST)
    before = cert.read_bytes()

    result = ensure_tls_certificate(cert, key, sans=SANS_TEST, force=True)

    assert result.created is True
    assert cert.read_bytes() != before


def test_regenera_si_la_clave_privada_falta(tmp_path):
    cert, key = _paths(tmp_path)
    ensure_tls_certificate(cert, key, sans=SANS_TEST)
    key.unlink()

    result = ensure_tls_certificate(cert, key, sans=SANS_TEST)

    assert result.created is True
    assert key.is_file()


def test_no_deja_ficheros_temporales_tras_generar(tmp_path):
    cert, key = _paths(tmp_path)

    ensure_tls_certificate(cert, key, sans=SANS_TEST)

    leftovers = sorted(p.name for p in cert.parent.iterdir())
    assert leftovers == ["cert.pem", "key.pem"]


def test_el_certificado_no_cubre_nada_si_no_existe(tmp_path):
    cert, _ = _paths(tmp_path)

    assert certificate_sans(cert) == ()
    assert certificate_covers(SANS_TEST, cert) is False


def test_un_certificado_ilegible_necesita_renovacion(tmp_path):
    cert, _ = _paths(tmp_path)
    cert.parent.mkdir(parents=True)
    cert.write_text("no soy un certificado", encoding="utf-8")

    assert certificate_needs_renewal(cert) is True


def test_un_certificado_vigente_no_necesita_renovacion(tmp_path):
    cert, key = _paths(tmp_path)
    ensure_tls_certificate(cert, key, sans=SANS_TEST)

    assert certificate_needs_renewal(cert) is False


def test_un_certificado_a_punto_de_caducar_necesita_renovacion(tmp_path):
    """Se fija con reloj inyectado, sin esperar 10 años."""
    cert, key = _paths(tmp_path)
    ensure_tls_certificate(cert, key, sans=SANS_TEST)

    casi_caducado = dt.datetime.now(dt.UTC) + dt.timedelta(
        days=CERT_VALIDITY_DAYS - 1
    )

    assert certificate_needs_renewal(cert, now=casi_caducado) is True


def test_los_sans_requeridos_incluyen_los_nombres_de_acceso_de_la_app():
    sans = required_sans(hostname="mi-pc", lan_ip="192.168.1.42")

    assert sans == (
        "localhost",
        "127.0.0.1",
        "mi-pc",
        "mi-pc.local",
        tls_cert.TLS_ALT_HOSTNAME,
        "192.168.1.42",
    )
    # Sin duplicados aunque host e IP coincidan con los fijos.
    assert len(set(required_sans(hostname="localhost", lan_ip="127.0.0.1"))) == len(
        required_sans(hostname="localhost", lan_ip="127.0.0.1")
    )


def test_los_sans_separan_dns_de_direcciones_ip(tmp_path):
    cert, key = _paths(tmp_path)

    ensure_tls_certificate(cert, key, sans=("localhost", "10.0.0.7"))

    parsed = x509.load_pem_x509_certificate(cert.read_bytes())
    extension = parsed.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    )
    assert [str(n) for n in extension.value.get_values_for_type(x509.DNSName)] == [
        "localhost"
    ]
    assert [
        str(n) for n in extension.value.get_values_for_type(x509.IPAddress)
    ] == ["10.0.0.7"]


def test_los_flags_de_uvicorn_apuntan_al_certificado(tmp_path):
    cert, key = _paths(tmp_path)

    flags = ssl_command_flags(cert, key)

    assert flags == ["--ssl-certfile", str(cert), "--ssl-keyfile", str(key)]
