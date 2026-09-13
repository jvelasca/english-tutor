# Briefing de subagente — V3.58 (Sense Engine 2.0: `surface → lemma → sense → semantic_fit`)

> **Estado:** incremento V3.58 **EJECUTADO** (2026-09-13, release **v3.58.0**),
> escrito sobre el árbol de `v3.57.0` (commit `a40b58d` + docs `7ecad27`). Es el
> candidato que el proyecto arrastra como **diferido** desde V3.44: la auditoría
> de V3.43.0 (punto 11, P1) pidió
> `surface → lemma → lexical_unit → sense → context → semantic_fit` y V3.44 solo
> entregó la mitad —**sustituyó la `pos` global por sentidos declarados
> `[{pos, gloss}]`, pero la decisión siguió siendo de FAMILIA POS**—. La `gloss`
> se genera, se valida, se cachea y **no la lee nadie**: es dato **INERTE**.
> V3.58 la hace decidir el SENTIDO (nunca el veredicto). Resultado verificado:
> `pytest` **2296 passed**, `ruff` limpio, launcher **75 passed**, `tsc` OK,
> `vitest` **651**, `check_release_consistency` **3.58.0**; ver
> `release-notes-v3.58.0.md`. **Histórico.**
> Antes de reutilizar este briefing, **verifica el estado real del árbol**
> (premisa 8): los nombres y las líneas de abajo se citan del árbol de `v3.57.0`
> y pueden haber cambiado.

## Rol

Ingeniero de backend del proyecto English Tutor, con foco en el **proxy
semántico determinista** de la evidencia (`services/semantics.py`), su
**cableado en el scoring de transferencia** (`services/lexicon.py`) y el
**contrato de contenido del diccionario** (`services/dictionary_content.py`,
`repositories/dictionary.py`).

## Objetivo

Resolver el problema que la auditoría de V3.43.0 dejó abierto: **el proxy
semántico distingue categorías, no SENTIDOS**. Con `bank` declarando
`[{pos: noun, gloss: "financial place"}, {pos: noun, gloss: "river side"}]`,
V3.44 no puede separar «el banco del río» de «el banco financiero», porque
ambos usos son `noun` y ambos «encajan» con la familia nominal: el proxy dice
`fit` para los dos. V3.58 introduce la pata que falta:

```text
surface  → lemma        (flexión regular → forma base, declarada y determinista)
lemma    → SENSE        (selección del sentido por función + SOLAPAMIENTO con la glosa)
sense    → semantic_fit (fit / suspect / incorrect / unknown, ADVISORY)
```

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.13, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`), lanzador Tkinter
  (`launcher/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia ni planifica.
  El modelo local **produce** los sentidos y sus glosas; el juicio sobre el uso
  es **código determinista**. Esto NO se negocia en este incremento.
- **Premisa 12:** cada pieza va precedida de un test; tests rápidos y sin red.
- **Premisa 6:** un incremento a la vez, con su release (`v3.58.0`).
- **Premisa 10/18:** responsabilidades claras y docstrings que expliquen el PORQUÉ
  de cada tabla, umbral y peso.
- **Arranque y gates** (todo debe salir 0):
  - `cd backend; ..\backend\.venv\Scripts\python.exe -m ruff check .` y
    `..\backend\.venv\Scripts\python.exe -m pytest -q`;
  - lo mismo en `launcher/` (tiene su propio `pyproject.toml` y sus tests);
  - `cd frontend; npm test; npx tsc --noEmit; npm run build`;
  - desde la raíz: `backend\.venv\Scripts\python.exe scripts\check_release_consistency.py`
    (**3.58.0**), `backend\.venv\Scripts\python.exe scripts\check_beta_v3.py`,
    `backend\.venv\Scripts\python.exe scripts\content_validation.py` y
    `backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py`.

## Estado de partida verificado (árbol `v3.57.0`)

- **Juez semántico** (`services/semantics.py`, puro, ~245 líneas):
  - `SEMANTIC_ADEQUACIES = (fit, suspect, incorrect, unknown)`; `SENSE_FIT`,
    `SENSE_SUSPECT`, `SENSE_INCORRECT`, `SENSE_UNKNOWN`.
  - `pos_family(pos)` → `"noun"`/`"verb"`/`""` (por PALABRAS, no subcadenas:
    «adverbio» no se confunde con «verb»; una categoría no nominal ni verbal
    devuelve `""` y **no participa** — no se inventa contradicción).
  - `families_from_senses(senses, pos=…)` → conjunto de familias POS de los
    sentidos, con **fallback a la `pos` global** (retrocompatible con V3.43).
  - `unit_positions(tokens, word)` → posiciones de la unidad o de sus flexiones
    (`-ed`/`-ing` fuertes; `-s`/`-ies` débiles). Misma lógica que V3.43, extraída.
  - `occurrence_role(tokens, index, word)` → `(rol, fuerza)` con
    `rol ∈ {noun, verb, ""}` y `fuerza ∈ {strong, weak, ""}`. Solo se pronuncia
    con unidades de UNA palabra (multi-palabra se abstiene). Pistas: pronombre
    sujeto/auxiliar delante → verbo FUERTE; determinante/posesivo delante →
    nombre DÉBIL; sufijo `-ed`/`-ing` → verbo FUERTE; `-s`/`-ies` → verbo DÉBIL.
  - `semantic_adequacy(word, text, *, senses=(), pos="")` → reglas en orden:
    sin familias o sin ocurrencias → `unknown`; **alguna** ocurrencia encaja con
    las familias → `fit`; ninguna encaja y hay contradicción FUERTE →
    `incorrect`; ninguna y solo contradicción DÉBIL → `suspect`; si no, `unknown`.
  - **LA GLOSA NO SE USA EN NINGUNA PARTE DEL JUICIO.** `normalize_senses` la
    valida y la acota, la caché la guarda, y el juez la ignora.
- **Contrato de contenido** (`services/dictionary_content.py`):
  - `GENERATOR_VERSION = "1.4.0"` (bump de V3.44 para introducir `senses`).
  - `MAX_SENSES = 4`, `MAX_GLOSS_CHARS = 120`, `_VALID_POS` = `{noun, verb,
    adjective, adverb, pronoun, preposition, conjunction, interjection,
    determiner, phrase}`.
  - `normalize_senses(raw)` → `[{pos, gloss}]` deduplicado por `(pos, gloss)`,
    recortado y limitado; descarta elementos sin `pos` canónico; nunca lanza.
  - `pos` superior = primer sentido válido, con fallback al `pos` del modelo.
- **Cableado del scoring** (`services/lexicon.py`):
  - `_semantic_fit(pos, word, text, senses=())` (línea ~423) delega en
    `semantics.semantic_adequacy`.
  - `score_transfer_attempt(word, text, *, pos="", senses=())` (línea ~486)
    calcula `_score_production_text` (unidad alineada + longitud mínima, la MISMA
    acreditación que `write`) y la adecuación; devuelve `adequacy` y, cuando
    corresponde, `error_type ∈ {semantic_mismatch (incorrect), semantic_doubt
    (suspect)}`. **`incorrect` es el ÚNICO valor que bloquea un clean success**;
    `passed` NUNCA se destruye por el proxy (no destruye evidencia léxica).
- **Origen de los datos** (`domain/vocabulary.py`, ~1058–1069): el drill de
  transferencia lee la entrada de la UNIDAD léxica (`dictionary_repo.get_entry`),
  prefiere los sentidos de la unidad (`go/went/gone` comparten sentido) y cae a
  la superficie buscada; pasa `pos` y `senses` a `score_transfer_attempt`.
  `save_entry`/`save_reverse_entry` persisten `senses_json` y
  `generator_version`. **La `gloss` YA ESTÁ en la caché de los usuarios.**
- **Contratos** (`schemas/vocabulary.py`): `semantic_fit: bool | None` y
  `adequacy` en la respuesta de transferencia; espejo en
  `frontend/src/types/api.ts` (~línea 619). **No cambian en V3.58.**
- **Tests que fijan el comportamiento actual (deben seguir verdes):**
  `tests/test_senses_v344.py`, `tests/test_transfer_v344.py`,
  `tests/test_transfer_v343.py`.

## Decisiones de alcance (a CERRAR con el gerente)

1. **La glosa DECIDE, pero solo como DESEMPATE dentro de la misma familia POS.**
   La función sintáctica (`occurrence_role`) sigue siendo la señal FUERTE y no se
   debilita: V3.58 **no** cambia cuándo se emite `incorrect` (sigue exigiendo
   contradicción fuerte con TODAS las familias) ni introduce un `incorrect` nuevo
   por desacuerdo de glosa. Lo que añade es poder separar dos sentidos de la
   MISMA familia: hoy eso es imposible por construcción.
2. **Sin glosa, comportamiento V3.44 EXACTO.** Un sentido con `gloss == ""` (o
   una entrada sin sentidos) no aporta nada al desempate y el juicio degrada
   **byte a byte** al de V3.44. Es el invariante de no-regresión y se prueba por
   igualdad literal, no por aproximación.
3. **El desempate es determinista y DECLARADO:** solapamiento léxico entre la
   VENTANA de contexto de la ocurrencia y los tokens de contenido de la glosa,
   con lista de paradas declarada y umbral declarado. Nada de embeddings, nada de
   sinónimos, nada de LLM en el camino de la evidencia (premisa 21).
4. **Advisory, no autoridad.** El proxy sigue siendo conservador: ante duda,
   `unknown`. Solo `incorrect` bloquea el clean success y `suspect` advierte.
   `passed` sigue siendo verdadero aunque la adecuación sea `incorrect`.
5. **SIN migración, SIN bump de `GENERATOR_VERSION`, SIN UI.** La `gloss` ya está
   cacheada con 1.4.0; se re-interpreta un dato existente (exactamente el patrón
   de V3.57 con `skill_priorities`). Si al verificar el árbol resultara que la
   glosa NO está persistida de forma utilizable, **para y consulta al gerente**
   antes de tocar el contrato de contenido o el generador.

## Plan de implementación (tests-first)

1. **Tests primero** (`backend/tests/test_semantics_sense_engine_v358.py`):
   - `surface → lemma`: `banked`/`banking`/`banks` resuelven a `bank` como forma
     candidata de comparación con la glosa.
   - **Selección de sentido por glosa**: con
     `senses=[{noun,"financial place"},{noun,"river side"}]`,
     `"I went to the bank yesterday"` y `"The river bank was beautiful"` deben
     separarse (el segundo, `fit` o `suspect` según la ventana; el primero, `fit`).
     Con `[{noun,"financial place"}]` (solo un sentido), `"The river bank was
     beautiful"` NO debe declararse `incorrect` (conservador).
   - **No-regresión**: `senses=[{pos:"verb"}]` y `senses=[]` con `pos="noun"`
     reproducen EXACTAMENTE la salida de V3.44 en la batería de casos de
     `test_senses_v344.py`/`test_transfer_v344.py` (parametrizado).
   - **`incorrect` no se amplía**: ningún caso con glosa produce `incorrect` si su
     `pos`-family-only equivalente no lo producía.
   - **Robustez**: sentidos con tipos raros, glosas vacías, texto no‐str, unidad
     multi-palabra → degradan a `unknown`, nunca lanzan.
2. **Núcleo puro** (`services/semantics.py`, aditivo):
   - `SENSE_STOPWORDS` declarada; `gloss_tokens(gloss)`; `context_window(tokens,
     index, size=_CONTEXT_WINDOW)`; `sense_overlap(window_tokens, gloss)`.
   - `select_sense(word, tokens, index, senses)` → `(sense_index, score,
     reasons)` determinista y explicable; empate → el primer sentido declarado
     (estable).
   - `semantic_fit(word, text, *, senses=(), pos="")` (o extensión de
     `semantic_adequacy` conservando su firma y contrato) que incorpora el
     desempate sin cambiar la taxonomía ni cuándo bloquea.
3. **Cableado**: `lexicon._semantic_fit` pasa a la nueva función; el contrato de
   `score_transfer_attempt` y de los `adequacy`/`error_type` **no cambia**.
4. **Gates completos** (los de arriba) y **subir el número de tests** en el
   relevo/changelog con la cifra real.

## Fuera de alcance (V3.59+)

- Cambiar el prompt/contrato de generación de sentidos o subir
  `GENERATOR_VERSION`.
- Ponderar la adecuación semántica dentro de `transfer_confidence` (los pesos
  declarados de V3.49 no se tocan).
- **Context Engine 3.0**.
- Cualquier uso del LLM en el camino de la evidencia (premisa 21).
