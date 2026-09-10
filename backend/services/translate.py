"""Traducción a demanda con el modelo local.

Es una ayuda de apoyo en pantallas de práctica (listening, speaking,
pronunciación) y, desde V3.39, el motor del destino auxiliar Traductor. Por
diseño NO registra evidencia, no cuenta como intento y no mueve ninguna métrica
ni puerta de dominio.

V3.39 (Fase 2): el servicio es BIDIRECCIONAL. `direction="en-es"` es la
dirección histórica y la de DEFECTO (las pantallas de práctica no cambian);
`direction="es-en"` es la del Traductor (se habla/escribe en español y se
devuelve inglés). La caché está indexada por `(dirección, frase)`, así que un
mismo texto no colisiona entre direcciones.

Elección de modelo: la traducción es interactiva y debe responder en pocos
segundos, así que se prefiere un modelo ligero e instalado (llama3.1:8b o
qwen2.5-coder:1.5b) al modelo por defecto del chat, que en CPU puede tardar
decenas de segundos por frase. Nunca se eligen modelos marcados como no
utilizables en `config.UNUSABLE_MODELS`. Si no hay ningún modelo rápido
instalado, se usa el primero utilizable o, en último caso, el modelo por
defecto.

Caché: en memoria, por frase. Los textos de práctica se repiten mucho (repaso,
rutas, dictados) y la primera traducción de una frase es la única que paga la
latencia del modelo.
"""

from __future__ import annotations

import time

from config import DEFAULT_MODEL, UNUSABLE_MODELS
from schemas.chat import ChatMessage
from services import llm
from services.llm import chat_once

MAX_SOURCE_CHARS = 800

# Modelos candidatos para la traducción interactiva, en orden de preferencia.
# Deben estar instalados en Ollama; si ninguno lo está se elige el primero
# utilizable instalado.
PREFERRED_TRANSLATION_MODELS = (
    "llama3.1:8b",
    "qwen2.5-coder:1.5b",
)

_SYSTEM_PROMPT_EN_ES = (
    "You are a professional translator from English into Spanish. "
    "The user sends a short English phrase that appears in a language-learning "
    "app (a question, a listening transcript or a reference sentence). "
    "Reply with ONLY its natural translation into neutral Spanish. "
    "Do not add explanations, notes, quotation marks or the original text."
)

# V3.39 (Fase 2, Traductor): dirección inversa ES→EN. Mismo contrato de salida
# (solo la traducción, sin notas ni comillas) y español neutro de entrada.
_SYSTEM_PROMPT_ES_EN = (
    "You are a professional translator from Spanish into English. "
    "The user sends a short Spanish phrase (spoken by a traveller in a "
    "language-learning app). "
    "Reply with ONLY its natural, everyday English translation. "
    "Do not add explanations, notes, quotation marks or the original text."
)

# V3.39: direcciones soportadas. `en-es` es la histórica y la de DEFECTO, para
# no alterar las llamadas existentes de las pantallas de práctica.
DIRECTION_EN_ES = "en-es"
DIRECTION_ES_EN = "es-en"
DIRECTIONS: tuple[str, ...] = (DIRECTION_EN_ES, DIRECTION_ES_EN)

_SYSTEM_PROMPTS: dict[str, str] = {
    DIRECTION_EN_ES: _SYSTEM_PROMPT_EN_ES,
    DIRECTION_ES_EN: _SYSTEM_PROMPT_ES_EN,
}

# Compatibilidad: el nombre histórico apunta al prompt EN→ES.
_SYSTEM_PROMPT = _SYSTEM_PROMPT_EN_ES

# Clave (dirección, frase recortada) → traducción.
_cache: dict[tuple[str, str], str] = {}

# Modelos instalados vistos la última vez (para no consultar a Ollama en cada
# frase): set[str] o None si aún no se ha consultado.
_installed: set[str] | None = None
_installed_at = 0.0
_INSTALLED_TTL_SECONDS = 300.0


async def installed_models() -> set[str]:
    """Devuelve los modelos instalados, con caché de pocos minutos."""
    global _installed, _installed_at
    now = time.monotonic()
    if _installed is None or now - _installed_at > _INSTALLED_TTL_SECONDS:
        try:
            _installed = set(await llm.list_models())
        except Exception:  # noqa: BLE001
            # Ollama caído: conserva lo que hubiera y reintenta pronto.
            _installed = _installed or set()
            _installed_at = now - (_INSTALLED_TTL_SECONDS - 60)
        else:
            _installed_at = now
    return _installed


async def pick_model(explicit: str | None) -> str:
    """Elige el modelo: el explícito si se aporta y es utilizable E INSTALADO,
    si no el más rápido instalado.

    El modelo explícito es una PREFERENCIA, nunca una orden: si está marcado en
    `config.UNUSABLE_MODELS` (V3.30.1, P1-02) o NO está instalado (V3.31.1,
    auditoría V3.31.0, P1-01) se descarta y se cae al mismo fallback que un
    modelo no explícito — la política de modelos no utilizables no se puede
    saltar por petición del cliente y un modelo no instalado no debe llegar a
    Ollama. Si no hay ningún preferido instalado, se usa el primer modelo
    utilizable que haya o, en último caso, el modelo por defecto.
    """
    installed = await installed_models()
    if explicit and explicit not in UNUSABLE_MODELS and explicit in installed:
        return explicit
    for candidate in PREFERRED_TRANSLATION_MODELS:
        if candidate in installed:
            return candidate
    usable = sorted(installed - UNUSABLE_MODELS)
    if usable:
        return usable[0]
    return DEFAULT_MODEL


async def translate_text(
    text: str,
    model: str | None = None,
    direction: str = DIRECTION_EN_ES,
) -> str:
    """Traduce `text` con caché por `(dirección, frase)` (V3.30 → V3.39).

    `direction` es `"en-es"` (defecto) o `"es-en"`; una dirección desconocida
    cae a `"en-es"` para no romper a los clientes existentes.
    """
    source = text.strip()
    if not source:
        raise ValueError("text vacío")
    if len(source) > MAX_SOURCE_CHARS:
        source = source[:MAX_SOURCE_CHARS]

    chosen_direction = (
        direction if direction in _SYSTEM_PROMPTS else DIRECTION_EN_ES
    )
    key = (chosen_direction, source)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    chosen = await pick_model(model)
    reply = await chat_once(
        messages=[ChatMessage(role="user", content=source)],
        model=chosen,
        temperature=0.0,
        system_prompt=_SYSTEM_PROMPTS[chosen_direction],
    )
    translation = reply.content.strip()
    if not translation:
        raise RuntimeError("el modelo devolvió una traducción vacía")

    _cache[key] = translation
    return translation
