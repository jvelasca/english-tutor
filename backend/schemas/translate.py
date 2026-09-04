"""Esquemas Pydantic del endpoint de traducción de apoyo."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import DEFAULT_MODEL

# Texto corto de práctica (una frase de enunciado, transcripción o referencia);
# no admitimos párrafos largos: esta ayuda no es un traductor de documentos.
MAX_SOURCE_CHARS = 800


class TranslateRequest(BaseModel):
    """Cuerpo de POST /api/translate: frase en inglés a traducir al español."""

    text: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_CHARS,
        description="Frase o texto corto en inglés de una pantalla de práctica",
    )
    model: str = Field(default=DEFAULT_MODEL, min_length=1)


class TranslateResponse(BaseModel):
    """Traducción al español (neutro) generada por el modelo local."""

    translation: str = Field(min_length=1)
