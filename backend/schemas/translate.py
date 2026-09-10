"""Esquemas Pydantic del endpoint de traducción de apoyo."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Texto corto de práctica (una frase de enunciado, transcripción o referencia);
# no admitimos párrafos largos: esta ayuda no es un traductor de documentos.
MAX_SOURCE_CHARS = 800


class TranslateRequest(BaseModel):
    """Cuerpo de POST /api/translate: frase a traducir.

    V3.39 (Fase 2): `direction` elige la dirección. `en-es` (defecto) traduce
    del inglés al español (contrato histórico de las pantallas de práctica);
    `es-en` traduce del español al inglés (Traductor).
    """

    text: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_CHARS,
        description="Frase o texto corto de una pantalla de práctica",
    )
    model: str | None = Field(
        default=None,
        description=(
            "Modelo Ollama con el que traducir. Si se omite, el servidor elige "
            "el modelo ligero más rápido que tenga instalado."
        ),
    )
    direction: Literal["en-es", "es-en"] = Field(
        default="en-es",
        description="Dirección de traducción; `en-es` es la histórica.",
    )


class TranslateResponse(BaseModel):
    """Traducción generada por el modelo local (idioma según `direction`)."""

    translation: str = Field(min_length=1)
