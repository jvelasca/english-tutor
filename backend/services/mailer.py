"""Correo saliente de la app (V3.81): verificación de email, **fail-closed**.

**Qué problema resuelve.** La Fase 3 del P0 prometía «se confirmará desde el email
que es cierta» y el producto es local: puede no haber Internet, ni SMTP, ni
proveedor. La decisión (tomada con el usuario) es **híbrida**: el correo es una
**señal**, no un muro. Si hay SMTP configurado, el enlace de verificación sale de
verdad; si no, no se envía nada, la app funciona igual y el webmaster sella la
verificación a mano desde la consola de gestión.

**Fail-closed, y eso significa dos cosas concretas:**

1. Sin SMTP configurado **no se abre ninguna conexión**: `is_configured()` se
   comprueba antes de tocar `smtplib`, así que una instalación sin correo no hace
   ni un intento de red (importa en una app que se promete offline).
2. Un fallo de envío **no rompe** la acción que lo pedía. El alta de una cuenta
   sigue adelante sin verificación: es la misma degradación honesta que declarar
   «sin verificar» en el perfil.

**Dependencia de red declarada.** `smtplib` sale a Internet, así que aparece en
`scripts/audit_dossier.py::RUNTIME_TOUCHPOINTS` con `kind: "internet"`. Ese candado
es justo el que tiene que saltar cuando se añade una salida de red, y el test
`test_runtime_audit_v371.py` lo vigila.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# Tiempo máximo de conversación con el servidor de correo. Corto a propósito: el
# envío ocurre dentro de una petición HTTP, y un SMTP que no responde no puede
# dejar colgada la pantalla de alta.
SMTP_TIMEOUT_SECONDS = 10

# Nombres de los envíos que sabe hacer el producto. Son códigos para que el
# lanzador («Probar envío») y el alta pidan cosas distintas sin duplicar lógica.
KIND_VERIFICATION = "verification"
KIND_TEST = "test"


def secret_path() -> Path:
    """Ruta de la contraseña del SMTP (`DATA_DIR/mail.secret`)."""
    return config.DATA_DIR / config.SMTP_SECRET_NAME


def smtp_password() -> str:
    """Contraseña del SMTP, o `""`. Se lee en cada llamada (el lanzador la escribe).

    Mismo criterio que `services/sessions.py::_secret`: no se cachea al importar,
    así el webmaster puede cambiarla sin reiniciar el backend y los tests pueden
    aislar `DATA_DIR` sin invalidar nada.
    """
    path = secret_path()
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_configured() -> bool:
    """¿Hay SMTP utilizable? Falso = no se envía nada y la app sigue igual."""
    return bool(config.smtp_settings()["configured"])


def verification_link(base_url: str, token: str) -> str:
    """Enlace que el alumno pulsa en el correo.

    Va a una ruta del **frontend** (`/#/cuenta/verificar?token=…`), no a la API:
    el token se canjea desde la app, que es la que sabe pintar el resultado. El
    parámetro viaja en el fragmento (`#`), así que no se queda en los logs del
    servidor ni en una cabecera `Referer`.
    """
    return f"{base_url.rstrip('/')}/#/cuenta/verificar?token={token}"


def _message(
    *, kind: str, to: str, link: str, lang: str, sender: str
) -> EmailMessage:
    """Correo en texto plano. Sin HTML: es más difícil de falsificar y de leerlo
    un filtro de spam, y el enlace se ve igual."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    if kind == KIND_TEST:
        message["Subject"] = (
            "English Tutor: prueba de envío"
            if lang == "es"
            else "English Tutor: test message"
        )
        message.set_content(
            (
                "Si estás leyendo esto, el envío de correo de English Tutor "
                "funciona."
            )
            if lang == "es"
            else "If you are reading this, English Tutor can send email."
        )
        return message
    message["Subject"] = (
        "English Tutor: confirma tu email"
        if lang == "es"
        else "English Tutor: confirm your email"
    )
    message.set_content(
        (
            "Abre este enlace para confirmar tu email:\n\n"
            f"{link}\n\n"
            "Caduca en una hora. Si no has creado ninguna cuenta, ignora este mensaje."
        )
        if lang == "es"
        else (
            "Open this link to confirm your email:\n\n"
            f"{link}\n\n"
            "It expires in one hour. If you did not create an account, ignore this."
        )
    )
    return message


def send(*, kind: str, to: str, link: str = "", lang: str = "es") -> bool:
    """Envía un correo. `False` si no se pudo (y **nunca** lanza).

    El valor de retorno es información, no un error: quien llama decide si
    contarlo (el alta lo menciona) o ignorarlo (el reenvío de verificación).
    """
    settings = config.smtp_settings()
    if not settings["configured"]:
        logger.info("SMTP sin configurar: no se envía el correo %s", kind)
        return False
    if not to:
        return False

    try:
        message = _message(
            kind=kind,
            to=to,
            link=link,
            lang=lang,
            sender=settings["sender"],
        )
        # 465 es TLS implícito (el contexto se pasa al conectar); cualquier otro
        # puerto se negocia con STARTTLS, que es lo que espera un 587.
        if settings["port"] == 465:
            with smtplib.SMTP_SSL(
                settings["host"],
                settings["port"],
                timeout=SMTP_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            ) as server:
                _login_and_send(server, settings, message)
        else:
            with smtplib.SMTP(
                settings["host"], settings["port"], timeout=SMTP_TIMEOUT_SECONDS
            ) as server:
                server.ehlo()
                try:
                    server.starttls(context=ssl.create_default_context())
                except smtplib.SMTPException:
                    # Un servidor local de reenvío (p. ej. en el propio equipo)
                    # puede no ofrecer STARTTLS. No se aborta: es una decisión de
                    # quien configura, no un fallo que debamos inventar.
                    logger.info("El SMTP no ofreció STARTTLS: se continúa en claro")
                _login_and_send(server, settings, message)
        return True
    except Exception as exc:  # noqa: BLE001 - red, TLS y credenciales: todo eso
        # Un fallo de correo no puede tumbar la acción que lo pedía (ver el
        # docstring del módulo). Se registra para que el lanzador pueda enseñarlo.
        logger.warning("No se pudo enviar el correo %s a %s: %s", kind, to, exc)
        return False


def _login_and_send(server, settings: dict, message: EmailMessage) -> None:
    """Autentica si hay credenciales y envía. Sin usuario, servidor abierto."""
    password = smtp_password()
    if settings["user"] and password:
        server.login(settings["user"], password)
    server.send_message(message)
