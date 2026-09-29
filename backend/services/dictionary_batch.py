"""Lote de operador del lexicón offline (V3.91, fase 2).

La consulta de una palabra sin caché paga una generación con el modelo local
(≈ 9 s medidos con el contrato de acepción 1.7.0, hasta 90 s de tope). La caché
evita repetirlo, pero **la primera vez la paga el alumno**. Este módulo es la
lógica pura del script que convierte ese coste en un trabajo de operador de UNA
sola pasada: recorre el vocabulario que la app usa de verdad, genera lo que
falte y lo deja en la caché global.

Decisiones deliberadas (y por qué):

- **No es el precalentado de V3.88.0.** `domain/dictionary_warmup.py` prepara el
  léxico de UN usuario, por la puerta de la consulta (con sus cuotas, su
  single-flight y su negative cache) y con un tope de 60 palabras. Ese camino es
  correcto para «mis palabras» y no sirve para preparar el currículum entero:
  con la cuota de 10 palabras nuevas por usuario y minuto, una pasada de 1.041
  palabras exigiría **al menos 1 h 45 min de reloj** aunque el modelo fuera
  instantáneo, y 1.041 consultas disparadas a mano. Un lote de operador tiene
  que poder **saltarse las cuotas** (es trabajo de mantenimiento, no una
  consulta) y eso es exactamente lo que hace el script: llama al generador
  directamente y persiste por el repositorio.
- **Puro y con la E/S inyectada.** Aquí no se abre SQLite ni se importa el
  cliente del modelo: `plan_batch` ordena el trabajo y `run_batch` lo ejecuta
  contra un `generate` y un `persist` que le pasa el llamante. Es lo que permite
  probar la reanudación, el tope de tiempo y el recuento de fallos sin modelo ni
  BD.
- **La reanudación no necesita fichero de estado: la caché ES el estado.** Una
  palabra preparada es una palabra fresca, así que un relanzamiento vuelve a
  planificar y salta sola lo ya hecho. Interrumpir (Ctrl-C, corte de luz, tope de
  tiempo) no deja trabajo a medias: cada palabra se persiste entera de una vez.
  Un fichero de estado sería una segunda fuente de verdad que puede
  desincronizarse de la BD.
- **Best-effort por palabra.** Una palabra que falla (modelo caído, respuesta
  inválida, timeout) se cuenta y se sigue: el lote no se aborta por una palabra
  y la siguiente pasada la reintenta, porque sigue sin ser fresca.

Higiene de ingesta (`normalize_word`, `parse_word_list`, `map_pos`, `clean_term`):
la lista de trabajo de un operador llega sucia (BOM, comillas, viñetas, mayúsculas,
duplicados, categorías de otra taxonomía). Estas funciones la dejan canónica. Se
aplican a la ENTRADA del lote, **no** a la salida del modelo: dos caminos que
escriben la misma caché no pueden tener dos semánticas distintas para la misma
palabra (el contenido del modelo ya lo normalizan `dictionary_content` y el
repositorio). `map_pos`/`clean_term` son, además, la puerta prevista para un
dataset léxico externo (fase 3), que hoy está **aparcado** a la espera de la
decisión de licencia (`docs/audit/PARKED.md`).
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field

from services.dictionary_content import VALID_POS

# --- Higiene de la lista de trabajo ------------------------------------------

# Una palabra del currículum es una palabra o una locución corta: letras, y
# dentro apóstrofo o guion («don't», «well-known»). Nada de dígitos, símbolos ni
# puntuación suelta. Es el mismo criterio con el que la app rechaza una consulta
# inválida, aplicado aquí para no gastar 4 s de modelo en un token basura.
_WORD_PART_RE = re.compile(r"^[a-z]+(?:['\u2019-][a-z]+)*$")
_MAX_WORD_CHARS = 80
# Ruido de ingesta: entidades HTML/XML sin resolver, viñetas de lista, BOM,
# marcas de orden y controles. Se retira por DELETE y no con un `strip` porque
# el ruido aparece también EN MEDIO del término («bank&nbsp;» → «bank»).
_TERM_NOISE_RE = re.compile(r"&[a-zA-Z#0-9]{1,10};|[\u200b-\u200f\ufeff]")
_TERM_SPACE_RE = re.compile(r"\s+")
# Puntuación de borde («- bank -», «• bank», «“bank”»), ya en minúsculas. Se
# define por NEGACIÓN de lo que forma parte de un término en lugar de con una
# lista de símbolos: un carácter raro nuevo no obliga a tocar el normalizador.
# `\W` es Unicode-aware: una LETRA acentuada NO es puntuación de borde y por
# tanto no se recorta («café» no puede quedar en «caf», que sería otro término).
_TERM_EDGE_RE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)

# Categorías de otras taxonomías → la taxonomía de la app (`VALID_POS`). Cubre
# las abreviaturas de los lexicones bilingües (FreeDict, Apertium) y los nombres
# largos que un modelo puede devolver en español.
_POS_ALIASES: dict[str, str] = {
    # abreviaturas de lexicón
    "n": "noun",
    "n.": "noun",
    "nn": "noun",
    "v": "verb",
    "v.": "verb",
    "vb": "verb",
    "adj": "adjective",
    "adj.": "adjective",
    "a": "adjective",
    "adv": "adverb",
    "adv.": "adverb",
    "pron": "pronoun",
    "pron.": "pronoun",
    "prep": "preposition",
    "prep.": "preposition",
    "conj": "conjunction",
    "conj.": "conjunction",
    "interj": "interjection",
    "interj.": "interjection",
    "int": "interjection",
    "det": "determiner",
    "art": "determiner",
    "article": "determiner",
    "phr": "phrase",
    "phr.": "phrase",
    "expr": "phrase",
    # nombres largos (inglés y español) por si el dataset no usa abreviaturas
    "sustantivo": "noun",
    "nombre": "noun",
    "verbo": "verb",
    "adjetivo": "adjective",
    "adverbio": "adverb",
    "pronombre": "pronoun",
    "preposición": "preposition",
    "preposicion": "preposition",
    "conjunción": "conjunction",
    "conjuncion": "conjunction",
    "interjección": "interjection",
    "interjeccion": "interjection",
    "determinante": "determiner",
    "locución": "phrase",
    "locucion": "phrase",
    "frase": "phrase",
}


def normalize_word(raw: object) -> str:
    """Forma canónica de una palabra de trabajo, o `""` si no es utilizable.

    Minúsculas, espacios colapsados, sin puntuación de borde, sin ruido de
    ingesta y con la comilla tipográfica reducida a la recta. Se RECHAZA (→ `""`)
    lo que no sea una palabra o una locución corta (varias palabras separadas por
    UN espacio, cada una con letras, apóstrofos y guiones): un token con dígitos
    o símbolos, o más largo que un término razonable, es ruido de la lista, no
    vocabulario.
    """
    text = str(raw or "")
    text = _TERM_NOISE_RE.sub("", text)
    text = text.replace("\u2019", "'").strip().lower()
    text = _TERM_SPACE_RE.sub(" ", text)
    text = _TERM_EDGE_RE.sub("", text)
    if not text or len(text) > _MAX_WORD_CHARS:
        return ""
    if not all(_WORD_PART_RE.match(part) for part in text.split(" ")):
        return ""
    return text


def parse_word_list(text: str) -> list[str]:
    """Limpia una lista de trabajo escrita a mano (una palabra por línea).

    Acepta también comas y punto y coma como separadores (una lista pegada de
    una hoja de cálculo), ignora comentarios (`#`) y líneas vacías, y descarta
    duplicados conservando el PRIMER orden de aparición: el orden de la lista es
    el orden de trabajo y debe ser reproducible entre pasadas.
    """
    words: list[str] = []
    seen: set[str] = set()
    for chunk in text.replace(";", "\n").replace(",", "\n").splitlines():
        line = chunk.split("#", 1)[0]
        word = normalize_word(line)
        if not word or word in seen:
            continue
        seen.add(word)
        words.append(word)
    return words


def clean_term(raw: object, *, limit: int = 120) -> str:
    """Término de un lexicón externo, sin ruido ni controles y acotado.

    Retira entidades sin resolver (`&amp;`, `&nbsp;`), marcas de orden y
    controles, colapsa espacios y RECORTA por longitud. **No** valida que sea
    inglés ni que sea una palabra: un término de lexicón puede ser una locución
    («to look after»). Devuelve `""` cuando no queda nada: un término vacío
    nunca se escribe (una fila sin término no es contenido).
    """
    text = str(raw or "")
    text = _TERM_NOISE_RE.sub("", text)
    # Controles (incluido \t y \n: un término es UNA línea).
    text = "".join(" " if ch < " " or ch == "\x7f" else ch for ch in text)
    text = _TERM_SPACE_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text


def map_pos(raw: object) -> str:
    """Categoría gramatical de otra taxonomía → la de la app, o `""`.

    Nunca inventa: lo que no reconoce se queda en `""`, que es lo que la UI
    entiende por «sin categoría declarada» (no se pinta una POS adivinada).
    """
    text = str(raw or "").strip().lower().strip(".")
    if not text:
        return ""
    if text in VALID_POS:
        return text
    mapped = _POS_ALIASES.get(text, "")
    return mapped if mapped in VALID_POS else ""


# --- Planificación del trabajo -----------------------------------------------


@dataclass(frozen=True)
class BatchPlan:
    """Qué hay que hacer en ESTA pasada, y qué se descartó por el camino."""

    words: list[str]
    universe: int
    fresh: int
    duplicates: int
    invalid: int
    limited: int

    @property
    def pending(self) -> int:
        """Palabras pendientes ANTES de aplicar el tope de la pasada."""
        return self.universe - self.fresh - self.duplicates - self.invalid

    @property
    def truncated(self) -> bool:
        """`True` si el tope de la pasada dejó trabajo fuera (se dice, no se calla)."""
        return self.limited > 0


def plan_batch(
    raw_words: Iterable[object],
    *,
    fresh: Iterable[str] = (),
    limit: int | None = None,
) -> BatchPlan:
    """Ordena el trabajo de una pasada: limpia, deduplica y salta lo fresco.

    `fresh` son las palabras que la caché ya sirve con el contrato vigente (el
    llamante las lee de la BD). El tope (`limit`) acota la pasada para poder
    trabajar por tramos: **no** se aplica un desplazamiento porque no hace falta
    —una palabra preparada deja de estar pendiente, así que la pasada siguiente
    continúa sola donde quedó esta—.
    """
    fresh_set = {str(word).strip().lower() for word in fresh if str(word).strip()}
    words: list[str] = []
    seen: set[str] = set()
    universe = 0
    duplicates = 0
    invalid = 0
    for raw in raw_words:
        universe += 1
        word = normalize_word(raw)
        if not word:
            invalid += 1
            continue
        if word in seen:
            duplicates += 1
            continue
        seen.add(word)
        if word in fresh_set:
            continue
        words.append(word)
    pending = len(words)
    limited = 0
    if limit is not None and limit >= 0 and pending > limit:
        limited = pending - limit
        words = words[:limit]
    return BatchPlan(
        words=words,
        universe=universe,
        fresh=sum(1 for word in seen if word in fresh_set),
        duplicates=duplicates,
        invalid=invalid,
        limited=limited,
    )


def estimate_seconds(count: int, seconds_per_word: float) -> float:
    """Coste estimado de `count` palabras con el ritmo medido del modelo local."""
    return max(0, int(count)) * max(0.0, float(seconds_per_word))


def format_duration(seconds: float) -> str:
    """Duración legible: `2 h 31 min`, `48 s`, `35 min` (nunca `0.0 s`)."""
    total = max(0, int(round(float(seconds))))
    if total < 60:
        return f"{total} s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} min {secs} s" if secs else f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


# --- Ejecución ---------------------------------------------------------------

GenerateFn = Callable[[str], Awaitable[dict | None]]
PersistFn = Callable[[str, dict], bool]
Clock = Callable[[], float]


@dataclass
class BatchReport:
    """Resultado de UNA pasada: lo intentado, lo logrado y lo que falló.

    `remaining` es lo que quedó pendiente por el tope de tiempo (o por un fallo
    previo), no por el tope de la lista: es lo que dice si hay que relanzar.
    """

    planned: int
    attempted: int = 0
    prepared: int = 0
    failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    stopped_early: bool = False

    @property
    def remaining(self) -> int:
        return max(0, self.planned - self.attempted)

    def as_dict(self) -> dict:
        return {
            "planned": self.planned,
            "attempted": self.attempted,
            "prepared": self.prepared,
            "failed": self.failed,
            "remaining": self.remaining,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stopped_early": self.stopped_early,
            "errors": [
                {"word": word, "reason": reason} for word, reason in self.errors
            ],
        }


async def run_batch(
    words: Sequence[str],
    *,
    generate: GenerateFn,
    persist: PersistFn,
    max_seconds: float | None = None,
    progress_every: int = 0,
    on_progress: Callable[[BatchReport], None] | None = None,
    clock: Clock = time.monotonic,
) -> BatchReport:
    """Recorre `words` generando y persistiendo, palabra a palabra.

    - **Nunca lanza por una palabra**: un fallo se cuenta con su motivo y se
      sigue. El lote es mantenimiento; una palabra mala no puede tumbar 2 horas
      de trabajo.
    - **Tope de tiempo** (`max_seconds`): se comprueba ANTES de cada palabra, así
      que se para en un límite de palabra (no a mitad de generación) y el
      llamante puede relanzar para continuar. Es la forma de trabajar por tramos
      sin dejar la caché a medias.
    - **Progreso** (`progress_every` + `on_progress`): el operador ve avanzar el
      lote en lugar de un salto final.
    """
    report = BatchReport(planned=len(words))
    started = clock()
    for index, word in enumerate(words):
        if max_seconds is not None and index > 0 and clock() - started >= max_seconds:
            report.stopped_early = True
            break
        report.attempted += 1
        try:
            content = await generate(word)
        except Exception as exc:  # noqa: BLE001 — una palabra no aborta el lote
            _record_failure(report, word, type(exc).__name__)
            continue
        if not content:
            _record_failure(report, word, "empty")
            continue
        try:
            written = persist(word, content)
        except Exception as exc:  # noqa: BLE001 — la BD caída no aborta el lote
            _record_failure(report, word, f"persist:{type(exc).__name__}")
            continue
        if not written:
            _record_failure(report, word, "not_persisted")
            continue
        report.prepared += 1
        if (
            progress_every > 0
            and on_progress
            and report.attempted % progress_every == 0
        ):
            on_progress(report)
    report.elapsed_seconds = clock() - started
    if on_progress is not None:
        on_progress(report)
    return report


def _record_failure(report: BatchReport, word: str, reason: str) -> None:
    report.failed += 1
    report.errors.append((word, reason))
