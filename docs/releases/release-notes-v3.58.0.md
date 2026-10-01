# v3.58.0 — Sense Engine 2.0 (`surface → lemma → sense → semantic_fit`)

> Release **SIN migración de BD, SIN bump de `GENERATOR_VERSION` y SIN cambios de
> UI** que cierra la mitad que V3.44 dejó abierta. Desde V3.44 el diccionario
> declara los **sentidos** de cada unidad (`[{pos, gloss}]`, generados por el
> modelo local como CONTENIDO) y los cachea. Pero el juicio sobre el uso
> comparaba **FAMILIAS POS**: la `gloss` no la leía **nadie**. Era **dato
> INERTE**. Con `bank` declarando dos sentidos de la MISMA familia
> («financial place» / «river side»), el motor no podía separar «el banco del
> río» de «el banco financiero»: **límite del contrato, no de los datos**.
> V3.58 añade las dos patas que faltaban —`surface → lemma` y `lemma → sense`— y
> hace que la glosa **RESUELVA** qué sentido se entendió.
> **FRONTERA DECLARADA (invariante conservador):** la glosa decide el **SENTIDO**,
> nunca el **VEREDICTO**. Determinista, sin LLM en el camino de la evidencia
> (premisa 21).

## Contexto

La auditoría de V3.43.0 (punto 11, P1) pidió
`surface → lemma → lexical_unit → sense → context → semantic_fit`. V3.44 entregó
solo la mitad: sustituyó la `pos` global por sentidos declarados, pero la decisión
siguió siendo de familia POS. El resultado es que el motor **acierta el veredicto
y no sabe el sentido**: `I went to the bank`, `I banked the river` y
`The river bank was beautiful` salen los tres `fit`, y el sistema no puede decir
cuál de los sentidos declarados se usó. Ese es el hueco que V3.58 cierra.

## Cambio

```text
superficie de la ocurrencia (tokens + rol sintáctico + fuerza de la pista)
   ↓ lemma_of / lemma_variants        (flexión regular → forma base comparable)
   ↓ family = familia POS de cada sentido declarado
   ↓ ventana de contexto (CONTEXT_WINDOW = 4 a cada lado)
   ↓ sense_overlap(ventana, glosa)    (tokens de CONTENIDO, comparados por lema)
   ↓ select_sense: (role_family_match, score, orden declarado)   ← estable
   ↓ sense_fit = { adequacy (V3.44 LITERAL), sentido resuelto, confianza }
```

### A. `surface → lemma` — `services/semantics.py`

- `lemma_of(token)` — morfología **regular declarada**, sin diccionario, sin
  lematizador y sin LLM: plural/3ª persona (`-s`, `-ies`), sibilantes
  (`-ches`/`-shes`/`-xes`/`-zes`), pasado (`-ed`) y gerundio (`-ing`, con la
  consonante doble `running`→`run`). Por debajo de 4 caracteres no se toca:
  `go`, `was`, `is` se devuelven tal cual.
- `lemma_variants(token)` — la superficie, su lema y, cuando la flexión pudo
  comerse una `e` muda, la variante restaurada (`making`→`make`). Es lo que
  permite que una glosa-etiqueta corta solape con texto flexionado.
- Es deliberadamente **PARCIAL**: las formas irregulares (`went`/`gone`) no se
  tocan. Solo alimenta una señal **SUAVE** —no decide el veredicto—, así que una
  forma no reconocida no puede contaminar la evidencia.

### B. `lemma → sense` — `select_sense`

Clave de orden **declarada** y determinista:

1. **`role_family_match`** (señal MAYOR) — la función sintáctica de la ocurrencia
   pertenece a la familia del sentido. La gramática manda.
2. **`score`** — nº de tokens de **contenido** de la glosa presentes en la
   **ventana de contexto** (`CONTEXT_WINDOW = 4` a cada lado), medido entre
   variantes de lema de las dos partes y con `GLOSS_STOPWORDS` declaradas («a
   place for money and loans» aporta `place`/`money`/`loans`, no su gramática).
   **Es el desempate que V3.44 no podía hacer**: dos sentidos de la misma familia.
3. **orden declarado** — empate real: gana el primer sentido (estable).

Devuelve `{index, pos, gloss, score, role, strength, reasons}`; sin sentidos,
`index` es `None`.

### C. `semantic_fit` y la frontera

- `sense_fit(...)` → `{adequacy, sense_index, sense_pos, sense_gloss,
  sense_score, reasons}`. El sentido se elige entre TODAS las ocurrencias por
  (familia que encaja, solapamiento, orden).
- `_adequacy(...)` es la regla **LITERAL** de V3.44 extraída sin cambios de
  comportamiento, y `semantic_adequacy` delega en ella: la firma, la taxonomía y
  el veredicto **no cambian** y las dos rutas no pueden divergir.
- **La glosa NO amplía `incorrect`.** La AUSENCIA de solapamiento no demuestra
  incompatibilidad: `"The bank is closed"` no comparte ni una palabra con «a
  financial place» y es un uso correcto. Por eso `score` es **CONFIANZA**, no
  prueba, y `passed` sigue siendo verdadero aunque la adecuación sea `incorrect`.
  La invariante se prueba de forma explícita y parametrizada contra los literales
  históricos (no contra la implementación).

### D. Contrato aditivo

`lexicon.score_transfer_attempt` expone `sense_index`/`sense_pos`/`sense_gloss`/
`sense_score` **sin alterar** `passed`, `lexical_transfer`, `adequacy`,
`semantic_fit` ni `error_type`. `TransferAttemptOut` (`schemas/vocabulary.py`) los
declara, con espejo opcional en `frontend/src/types/api.ts`: **el sentido resuelto
ya no es dato inerte**, viaja en la respuesta HTTP. Sin cambio de UI.

### E. Sin migración y sin regenerar contenido

La `gloss` **ya estaba cacheada** con `GENERATOR_VERSION = "1.4.0"` (V3.44):
V3.58 la **re-interpreta**, exactamente el patrón de V3.57 con
`skill_priorities`. No hay migración, ni bump de generador, ni invalidación de
caché.

## NO cambia

- `semantic_adequacy` (firma, taxonomía y veredictos), `families_from_senses`,
  `occurrence_role`/`unit_positions`/`pos_family`, la frontera de `incorrect` y el
  hecho de que `suspect` es advisory.
- `GENERATOR_VERSION`, `normalize_senses`, `MAX_SENSES`, `MAX_GLOSS_CHARS` y el
  prompt de contenido.
- `transfer_state` y sus umbrales, `context_signals`, `context_diversity`,
  `CEFR_CAPACITY`, el scoring, FSRS, el planner y el Difficulty Engine.
- El contrato de `TransferAttemptOut`: los campos nuevos son **opcionales y
  aditivos**.

## Tests

Nuevo `backend/tests/test_semantics_sense_engine_v358.py` (**30**):

- `lemma_of`: flexión regular completa (incluido que `closes`→`close` y NO
  `clos`), guarda de palabras cortas y robustez ante basura.
- `lemma_variants`: restauración de la `e` muda (`making`→`make`) y de la
  consonante doble (`running`→`run`) .
- `gloss_tokens`: descarta palabras vacías, conserva orden y deduplica.
- `context_window`: acotada, recortada en los bordes, vacía sin tokens.
- `sense_overlap`: parecido por LEMAS (`decides` vs «to decide»), cero sin
  contacto léxico y robustez ante basura.
- `select_sense`: manda la familia del rol; **desempata la glosa dentro de la
  MISMA familia** (el caso que motivó la release: `bank` del río vs financiero en
  dos frases); estabilidad sin señal; sin sentidos → `None`.
- `sense_fit`: resuelve el sentido sin cambiar el veredicto; **equivalencia
  parametrizada** con el corpus histórico de V3.44 contra sus literales;
  degradación exacta sin glosa; `pos` como fallback; robustez ante basura;
  `incorrect` que NO se amplía.
- Contrato: payload aditivo del transfer, bloqueo intacto y ausencia de sentido
  sin sentidos declarados.
- End-to-end **HTTP**: el sentido resuelto viaja en la respuesta y la adecuación
  sigue siendo la de V3.44.

## Verificación

| Gate | Resultado |
| --- | --- |
| `pytest` (backend) | **2296 passed** (145,5 s) |
| `ruff check` | limpio |
| `launcher` tests | **75 passed** |
| `tsc --noEmit` | OK |
| `vitest` | **651 passed** |
| `npm run build` | OK |
| `check_release_consistency` | **3.58.0** |
| CI (6/6) | verde — [run 34780694687](https://github.com/jvelasca/english-tutor/actions/runs/34780694687) sobre `82f17c4` |

Cero regresión en el bloque V3.43/V3.44 (sentidos y scoring semántico) y en el
resto de la suite.

## Fuera de alcance (V3.59+)

- Cambiar el prompt/contrato de generación de sentidos o subir
  `GENERATOR_VERSION`.
- Ponderar la adecuación semántica dentro de `transfer_confidence` (los pesos
  declarados de V3.49 no se tocan).
- **Context Engine 3.0.**
- Cualquier uso del LLM en el camino de la evidencia (premisa 21).
