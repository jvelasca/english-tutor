"""Esquemas Pydantic del endpoint de traducción de apoyo."""

from __future__ import annotations

from pydantic import BaseModel, Field

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
    model: str | None = Field(
        default=None,
        description=(
            "Modelo Ollama con el que traducir. Si se omite, el servidor elige "
            "el modelo ligero más rápido que tenga instalado."
        ),
    )


class TranslateResponse(BaseModel):
    """Traducción al español (neutro) generada por el modelo local."""

    translation: str = Field(min_length=1)
