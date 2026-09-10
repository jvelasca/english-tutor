"""Pregunta de RECALL del drill (V3.34 → V3.37.1, cues graduados).

Tercer eslabón del Dictionary → Learning Bridge: el peldaño "Recall" de la
escalera compartida de drill. Frente a Recognition (elegir el significado de la
palabra), aquí el alumno hace el camino INVERSO: ve el SIGNIFICADO (cue) y debe
RECUPERAR y teclear la palabra. Es recuperación productiva por texto, sin
micrófono, y por eso no comparte la evidencia de Recognition (informativa) ni la
de Sentence (producción oral).

Reglas de honestidad (puras y deterministas, sin LLM):
- El cue es la traducción de la diana si existe; si no, su definición, pero
  SOLO si esa definición no contiene ya la palabra diana (evitar filtrar la
  respuesta con un cue circular: "bank: a bank is ...").
- Si no hay cue utilizable (palabra sin entrada, sin traducción ni definición
  válida), la pregunta NO está disponible (`None`): el peldaño degrada con
  aviso en lugar de forzar una pregunta que revele la respuesta.
- La función NUNCA devuelve la forma esperada como respuesta: el servidor la
  re-deriva al puntuar y solo la revela tras el intento.

V3.37 (cues graduados y automaticidad): la escalera deja de ser un FALLBACK
(traducción y, si no, definición) y pasa a ser una PROGRESIÓN de peldaños
declarados:

    translation (cued) < definition (cued) < cloze (guided) < situation (guided)

`recall_prompt_for` sirve el peldaño PEDIDO (o el de V3.34 cuando no se pide
ninguno, para no romper clientes antiguos); `next_recall_rung` decide el peldaño
siguiente a partir de los ÉXITOS ya registrados en el ledger por peldaño
(`drill:recall:<peldaño>`); y `resolve_recall_cue` separa la decisión pedagógica
de la disponibilidad real de contenido, degradando SIEMPRE hacia más apoyo
(nunca al revés). Todo se deriva de contenido que ya existe (caché del
diccionario + banco de pronunciación): no se inventa contenido.

V3.37.1 (política de consolidación y regresión, auditoría de V3.37.0 P1-01/
P1-02): `next_recall_rung` deja de ascender con UN éxito. Un peldaño está
SUPERADO solo con varios éxitos en DÍAS NATURALES distintos
(`RECALL_RUNG_PASS_MIN_SUCCESSES`/`RECALL_RUNG_PASS_MIN_DAYS`), y fallos
repetidos en el peldaño ideal (sin ningún éxito) hacen RETROCEDER la
recomendación hacia más apoyo (`RECALL_REGRESSION_FAILURES`). La progresión
pasa a ser EVIDENCIA → CONSOLIDACIÓN → MÁS EXIGENCIA, y el sistema empieza a
responder también "¿dónde puede rendir el alumno AHORA?".
"""

from __future__ import annotations

import re

from services import situation as situation_service
from services.phonetics import tokenize, unit_produced

# Peldaños soportados, ordenados de MAYOR a MENOR apoyo. El orden ES la
# hipótesis pedagógica declarada (`translation < definition < cloze <
# situation`), y V3.37/V3.38 dejan los datos (`recall_rungs` por `activity_id`)
# para corregirla si el corpus demuestra lo contrario.
#
# V3.38 añade `situation`: un enunciado SITUACIONAL autorado (una frase de
# escenario con un único hueco `_____` donde encaja la diana) que exige más que
# el cloze — que reutiliza una frase REAL del banco de pronunciación — porque no
# da la estructura sintáctica ya montada. Es contenido del contrato de la caché
# (`dictionary_entries.situation`, `generator_version` 1.2.0), no del corpus.
RECALL_CUES: tuple[str, ...] = (
    "translation",
    "definition",
    "cloze",
    "situation",
)

# Apoyo que declara cada peldaño en el ledger. Vive junto a la escalera, en la
# capa pura, para que dominio, repositorio y tests no puedan divergir.
RECALL_CUE_SUPPORT: dict[str, str] = {
    "translation": "cued",
    "definition": "cued",
    "cloze": "guided",
    "situation": "guided",
}

# V3.37.1 (política de consolidación): umbrales de "peldaño SUPERADO".
# Un único éxito no consolida (auditoría V3.37, P1-01): pasar el peldaño exige
# ≥ este nº de éxitos en ≥ este nº de DÍAS NATURALES distintos. Se mide sobre
# los ÉXITOS DEL PROPIO PELDAÑO (histograma `recall_rungs`) y no sobre
# `independent_successes`, porque `cued`/`guided` nunca son `independent` y
# exigir automaticidad bloquearía la escalera por completo. Declarado y
# calibrable, como el resto de umbrales pedagógicos del proyecto.
RECALL_RUNG_PASS_MIN_SUCCESSES = 2
RECALL_RUNG_PASS_MIN_DAYS = 2

# V3.37.1 (política de regresión): nº de FALLOS en el peldaño ideal que, sin
# ningún éxito en él, hacen bajar la recomendación al peldaño inmediatamente
# inferior (más apoyo). Un solo fallo solo repite el peldaño; la remediación
# exige un patrón, no un tropiezo (auditoría V3.37, P1-02).
RECALL_REGRESSION_FAILURES = 2

# Tokenizador alineado con `services.phonetics.tokenize` (mismo patrón, sin
# bajar el texto: se normaliza cada token por separado conservando los índices
# reales de la frase original para poder blanquear el hueco).
_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


def _normalize(text: str) -> str:
    """Minúsculas y espacios colapsados (comparación de superficies)."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _definition_leaks_word(definition: str, word: str) -> bool:
    """True si la definición ya contiene la palabra diana como token.

    Un cue que contiene la respuesta la regala (p. ej. definición "a bank is a
    place where..."), así que se descarta. Para unidades de una sola palabra se
    exige coincidencia de palabra completa (evita falsos positivos por
    subcadenas: `run` dentro de `running` no cuenta); para unidades
    multi-palabra se comprueba la subcadena normalizada.
    """
    norm_def = _normalize(definition)
    norm_word = _normalize(word)
    if not norm_def or not norm_word:
        return False
    if " " in norm_word:
        return norm_word in norm_def
    return re.search(rf"\b{re.escape(norm_word)}\b", norm_def) is not None


def blank_out(phrase: str, word: str) -> str | None:
    """Frase con la unidad léxica sustituida por un hueco `_____`, o `None`.

    Función pura y testeable del blanqueo del cue `cloze`. Reutiliza la MISMA
    alineación que acredita la producción del drill (`unit_produced`, V20-01)
    para confirmar que la unidad está de verdad en la frase; después localiza
    sus tokens en el texto ORIGINAL (conservando puntuación y mayúsculas) y los
    sustituye por el hueco.

    Reglas de honestidad:
    - si tras blanquear queda CUALQUIER otra aparición de la palabra, el cue se
      descarta (`None`): sería un spoiler;
    - si la frase no contiene la unidad o falta alguno de los dos, `None`
      (nunca se inventa una frase).
    """
    phrase = (phrase or "").strip()
    word = (word or "").strip()
    if not phrase or not word or not unit_produced(word, phrase):
        return None
    word_tokens = tokenize(word)
    if not word_tokens:
        return None
    spans = [
        (match.group(0).lower(), match.start(), match.end())
        for match in _TOKEN_RE.finditer(phrase)
    ]
    size = len(word_tokens)
    start = end = None
    for i in range(len(spans) - size + 1):
        if [token for token, _s, _e in spans[i : i + size]] == word_tokens:
            start, end = spans[i][1], spans[i + size - 1][2]
            break
    if start is None or end is None:
        return None
    blanked = f"{phrase[:start]}_____{phrase[end:]}"
    if _definition_leaks_word(blanked, word):
        return None
    return blanked


def recall_prompt_for(
    word: str,
    entries: list[dict],
    *,
    cue: str | None = None,
    example: dict | None = None,
) -> dict | None:
    """Cue `{word, cue, cue_kind}` del recall de la palabra, o `None`.

    - Busca la entrada de la diana en la caché global `dictionary_entries`
      (comparación por superficie normalizada).
    - `cue=None` conserva EXACTAMENTE el comportamiento V3.34: `translation` si
      existe; si no, `definition` siempre que no contenga la palabra diana.
    - `cue="translation"|"definition"|"cloze"|"situation"` sirve ESE peldaño o
      devuelve `None` si no tiene contenido (degradación controlada, sin
      evento). Un `cue` no soportado también devuelve `None`.
    - `cloze` construye la frase en blanco a partir de `example`
      (`{"phrase": …}` de `services.example_sentences.example_for`); si no hay
      frase real en el corpus, `None` (nunca se inventa una frase).
    - `situation` (V3.38) sirve el enunciado situacional cacheado de la entrada
      (`situation`), que ya viene validado por el generador (un solo hueco y sin
      la diana). Si la entrada no lo tiene, `None`.
    - `None` si la diana no existe en la caché.

    Nunca devuelve la forma esperada como respuesta.
    """
    target_word = _normalize(word)
    if not target_word:
        return None
    if cue is not None and cue not in RECALL_CUES:
        return None
    target = next(
        (e for e in entries if _normalize(e.get("word") or "") == target_word),
        None,
    )
    if target is None:
        return None

    if cue is None:
        translation = (target.get("translation") or "").strip()
        if translation:
            return {
                "word": target_word,
                "cue": translation,
                "cue_kind": "translation",
            }
        definition = (target.get("definition") or "").strip()
        if definition and not _definition_leaks_word(definition, target_word):
            return {
                "word": target_word,
                "cue": definition,
                "cue_kind": "definition",
            }
        return None

    if cue == "translation":
        translation = (target.get("translation") or "").strip()
        if not translation:
            return None
        return {
            "word": target_word,
            "cue": translation,
            "cue_kind": "translation",
        }

    if cue == "definition":
        definition = (target.get("definition") or "").strip()
        if not definition or _definition_leaks_word(definition, target_word):
            return None
        return {
            "word": target_word,
            "cue": definition,
            "cue_kind": "definition",
        }

    if cue == "situation":
        # V3.38: enunciado situacional del contrato de contenido. V3.38.1: se
        # revalida con el MISMO validador puro que la generación (un hueco, una
        # frase, sin fuga morfológica), de modo que una situación cacheada por
        # una versión previa con reglas más laxas no se sirva ni cuente como
        # peldaño disponible en la escalera.
        situation = situation_service.validate_situation(
            target.get("situation"), target_word
        )
        if not situation:
            return None
        return {
            "word": target_word,
            "cue": situation,
            "cue_kind": "situation",
        }

    # cue == "cloze": frase real del corpus con la unidad en blanco.
    blanked = blank_out((example or {}).get("phrase") or "", target_word)
    if blanked is None:
        return None
    return {"word": target_word, "cue": blanked, "cue_kind": "cloze"}


def _int_field(histogram: object, key: str) -> int:
    """Entero no negativo de un histograma del resumen (0 si falta o es inválido)."""
    if not isinstance(histogram, dict):
        return 0
    try:
        return max(0, int(histogram.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def _rung_stats(evidence: dict | None, rung: str) -> tuple[int, int, int]:
    """`(éxitos, días con éxito, fallos)` de un peldaño según la evidencia.

    Los tres histogramas se leen del ledger por `activity_id`
    (`drill:recall:<peldaño>`). Un valor ausente o no numérico cuenta 0: la
    evidencia legacy sin peldaño NUNCA alimenta la escalera (ni a favor ni en
    contra), tal y como documenta el contrato del ledger (V3.37).
    """
    data = evidence or {}
    return (
        _int_field(data.get("recall_rungs"), rung),
        _int_field(data.get("recall_rung_days"), rung),
        _int_field(data.get("recall_rung_failures"), rung),
    )


def _rung_passed(successes: int, days: int) -> bool:
    """¿Está SUPERADO el peldaño? (V3.37.1: consolidación, no un acierto suelto).

    Exige `RECALL_RUNG_PASS_MIN_SUCCESSES` éxitos en
    `RECALL_RUNG_PASS_MIN_DAYS` días naturales distintos. Un único acierto
    (aunque sea con mucha latencia, por ensayo o accidental) NO habilita subir
    la exigencia: primero se consolida (D5/E3).
    """
    return (
        successes >= RECALL_RUNG_PASS_MIN_SUCCESSES
        and days >= RECALL_RUNG_PASS_MIN_DAYS
    )


def next_recall_rung(row: dict, evidence: dict | None) -> str:
    """Peldaño RECOMENDADO de la escalera de recall (V3.37 → V3.37.1, puro).

    Combina DOS políticas separadas y deterministas:

    1. PROGRESIÓN (V3.37): se recorre la escalera de mayor a menor apoyo y se
       devuelve el primer peldaño que el ítem AÚN NO ha superado. V3.37.1
       endurece el significado de "superado" (`_rung_passed`): exige varios
       éxitos ESPACIADOS, de modo que la progresión es EVIDENCIA →
       CONSOLIDACIÓN → MÁS EXIGENCIA y no EVIDENCIA → MÁS EXIGENCIA. Sin ningún
       peldaño consolidado → `translation`; con los cuatro consolidados →
       `situation` (mantenimiento espaciado: es el techo de la escalera; el
       free recall de la producción vive en Sentence).

    2. REGRESIÓN (V3.37.1): si el peldaño ideal acumula
       `RECALL_REGRESSION_FAILURES` fallos SIN ningún éxito, la recomendación
       baja al peldaño inmediatamente inferior (MÁS apoyo). La adaptación real
       no es solo "¿hasta dónde ha llegado?", sino "¿dónde puede rendir
       AHORA?". Nunca baja de `translation`, y fallar jamás hace subir.

    El éxito/fallo por peldaño se lee del ledger por `activity_id`
    (`drill:recall:<peldaño>`; histogramas `recall_rungs`/`recall_rung_days`/
    `recall_rung_failures`), no de contadores nuevos. `row` se recibe por
    simetría con el resto de la cola de repaso; el peldaño es una propiedad del
    ÍTEM y hoy la evidencia ya llega agregada.
    """
    ideal = RECALL_CUES[-1]
    for rung in RECALL_CUES:
        successes, days, _failures = _rung_stats(evidence, rung)
        if not _rung_passed(successes, days):
            ideal = rung
            break
    # Regresión: el peldaño ideal se le atraganta (fallos repetidos y ningún
    # éxito). Se baja un peldaño: el de abajo SÍ está consolidado por
    # construcción, así que la recomendación es estable (sin oscilación).
    successes, _days, failures = _rung_stats(evidence, ideal)
    if failures >= RECALL_REGRESSION_FAILURES and successes == 0:
        index = RECALL_CUES.index(ideal)
        if index > 0:
            return RECALL_CUES[index - 1]
    return ideal


def resolve_recall_cue(ideal: str, available: object) -> str | None:
    """Peldaño realmente servible más cercano al ideal (V3.37, puro).

    `next_recall_rung` decide el peldaño IDEAL, pero no todos tienen contenido
    (el `cloze` exige que la palabra aparezca en el banco de pronunciación).
    Esta función separa la decisión pedagógica de la disponibilidad:

    - recorre la escalera desde `ideal` hacia ABAJO (hacia MÁS apoyo) y devuelve
      el primer peldaño disponible;
    - `None` si no hay ninguno (el peldaño degrada con `available=false`, sin
      evento, como en V3.34);
    - NUNCA degrada hacia ARRIBA: subir la exigencia sin evidencia que lo
      justifique es lo contrario de lo que V3.37 quiere.
    """
    if ideal not in RECALL_CUES:
        return None
    available_set = set(available or ())
    index = RECALL_CUES.index(ideal)
    for rung in reversed(RECALL_CUES[: index + 1]):
        if rung in available_set:
            return rung
    return None
