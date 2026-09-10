# V3.37 — Learning Evidence 3.0: cues graduados y automaticidad

> Rol: documento de diseño e implementación del candidato **V3.37**. Es el
> eslabón que convierte el dato en decisión: V3.36 ya **captura** el CÓMO de
> cada evento (`support_level`, `difficulty`, `context_id`/`activity_id`,
> `response_time_ms`, `error_type`); V3.37 **usa** el apoyo para graduar la
> exigencia. Se publica como **v3.37.0**.
>
> Normas que este eslabón respeta:
>
> - **Premisa 21**: la UI nunca declara acierto. El cliente dice QUÉ peldaño le
>   sirvieron; el servidor re-deriva ese peldaño de forma pura y determinista y
>   puntúa. El GET nunca expone la forma esperada.
> - **D3 (V3.30)**: «consultar ≠ aprender». El diccionario de consulta sigue
>   siendo SOLO lectura.
> - **V3.13**: un MC de reconocimiento no demuestra destrezas productivas.
>   Recognition sigue siendo SOLO informativo.
> - **D5/E3**: una producción del día no consolida; el drill no crea
>   `academy_evidence` curricular. La automaticidad exige éxito **espaciado**.
> - **Sin LLM en los cues**: toda la escalera se deriva de contenido que ya
>   existe (caché del diccionario + banco de pronunciación). No se inventa
>   contenido (ver «Qué NO entra en V3.37»).
>
> Borrador: 2026-09-10.

## Relevo rápido (leer antes de tocar nada)

- Versión estable actual: **3.36.0** (`backend/config.py::VERSION`).
- Árbol de trabajo limpio; CI en verde (6/6).
- **No hace falta migración de BD en V3.37**: `learning_evidence` ya tiene
  `support_level` y `activity_id` desde V3.36.0. Si crees que necesitas una
  columna nueva, párate y revisa el esquema real antes de escribir la migración.
- Fuente de verdad del estado: `CHANGELOG.md` + `docs/RELEVO.md` (nota superior).

## El hallazgo que motiva V3.37

Hoy el peldaño `2 · Recall` tiene **un solo cue**: traducción y, *si no hay
traducción*, definición. Eso es un **fallback**, no una **progresión**:

```python
# services/recall.py::recall_prompt_for  (V3.34, estado actual)
if translation:                 # casi todas las palabras tienen traducción
    return translation          # ← el peldaño NUNCA escala
if definition and not leaks:
    return definition           # ← solo se usa si falta la traducción
```

Consecuencias reales:

1. Una palabra con traducción **jamás** se enfrenta a un cue más difícil: el
   alumno puede acertar `2 · Recall` indefinidamente sin que el sistema suba la
   exigencia.
2. El evento de Recall declara siempre `support_level="cued"`
   (`domain/vocabulary.py::submit_recall_attempt`), se haya acertado con la
   traducción delante o sin nada. El dato no distingue apoyos porque **no hay
   apoyos que distinguir**.
3. `independent_successes` (agregado en V3.36) se queda sin uso: la escalera
   léxica nunca produce evidencia `independent`.

V3.37 cierra el arco: convierte la escalera en **progresión**, hace que cada
peldaño declare su propio `support_level`, y lee la historia resultante para
decidir el siguiente peldaño (**automaticidad**).

## Relación con la escalera de 5 peldaños de la auditoría

La auditoría pidió `translation → definition → cloze → situación → free recall`.
Contrastado con el código real, la escalera queda así:

| Peldaño auditado | Estado real hoy | Decisión V3.37 |
|---|---|---|
| `translation` | ✅ existe (V3.34) | Se mantiene como peldaño 1 (`cued`) |
| `definition` | ⚠️ existe solo como *fallback* | **Pasa a peldaño 2 de pleno derecho** (`cued`) |
| `cloze` | ❌ no existe | **Peldaño 3 nuevo** (`guided`), determinista desde el corpus |
| `situación` | ❌ no existe | **Fuera de alcance**: exige contenido autorado por palabra (V3.38) |
| `free recall` | ✅ **ya existe**, pero no es un cue | Es el paso `3 · Sentence` + producción espontánea (chat/writing) |

Dos matices importantes, para no confundir el alcance:

- **`free recall` no es un peldaño que falte.** Producir la palabra sin apoyo
  ya existe: es el paso `3 · Sentence` (producción oral en contexto) y la
  producción espontánea (`chat` → `spontaneous`, `conversation` → `guided`,
  `speaking`/`writing` → `independent`). Lo que faltaba no era el techo de la
  escalera, sino su **tramo medio** y la lectura de su evidencia.
- **`situación` no se implementa sin contenido.** Un enunciado situacional
  («Estás en un restaurante y quieres pedir la cuenta: ______») no se puede
  derivar de forma determinista de la caché del diccionario (traducción +
  definición) ni del banco de pronunciación. Inventarlo rompería la regla de
  «no inventar contenido» y el principio de cues puros y deterministas. Requiere
  extender el contrato de generación de contenido de la caché
  (`generator_version`, V3.30) y se planifica como V3.38.

## Decisiones cerradas de V3.37

1. **La escalera es una progresión, no un fallback.** `recall_prompt_for` deja
   de elegir «el primer cue disponible» y pasa a servir el peldaño **pedido**,
   con degradación explícita cuando ese peldaño no tiene contenido.
2. **Cada peldaño declara su `support_level`** (no lo hereda del paso):

   | Peldaño (`cue_kind`) | Qué ve el alumno | `support_level` |
   |---|---|---|
   | `translation` | La traducción (L1) | `cued` |
   | `definition` | La definición (L2) sin spoiler | `cued` |
   | `cloze` | Una frase real de la app con la palabra en blanco | `guided` |

3. **La escalera solo asciende con evidencia.** El peldaño recomendado se
   deriva de qué peldaños ha superado ya el ítem (`next_recall_rung`). No
   se sube por tiempo ni por número de intentos, sino por **éxito en el peldaño
   anterior**.
4. **El orden de dificultad es una hipótesis declarada, medible.** Se declara
   `translation < definition < cloze` como orden pedagógico, y V3.37 deja los
   datos para calibrarlo: `error_types`/`successes` por `activity_id` permiten
   comparar la tasa de acierto por peldaño. Si el corpus demuestra que el cloze
   es más fácil que la definición, el orden se corrige con datos, no con
   opiniones.
5. **Automaticidad = éxito independiente y espaciado.** Un ítem es `automatic`
   cuando acumula ≥ `AUTOMATIC_MIN_INDEPENDENT` éxitos con apoyo
   `independent`/`spontaneous` en **días naturales distintos** (mismo rigor que
   `distinct_success_days`). Un acierto suelto no es automaticidad (D5/E3).
6. **La escalera nunca es una puerta.** Igual que la cola de repaso: informa el
   peldaño recomendado; el alumno puede practicar cualquier peldaño disponible.

## Qué implementa V3.37

### 1. Servicio puro — la escalera (`services/recall.py`)

- `RECALL_CUES: tuple[str, ...] = ("translation", "definition", "cloze")` —
  peldaños soportados, ordenados de MAYOR a MENOR apoyo.
- `RECALL_CUE_SUPPORT: dict[str, str]` — mapeo peldaño → `support_level`
  (`translation`/`definition` → `cued`, `cloze` → `guided`). El mapeo vive
  junto a la escalera, en la capa pura, para que dominio, repositorio y tests
  no puedan divergir.
- `recall_prompt_for(word, entries, *, cue=None, example=None)`:
  - `cue=None` → comportamiento V3.34 conservado (traducción, si no definición)
    para no romper llamadas existentes;
  - `cue="translation"|"definition"|"cloze"` → sirve ESE peldaño o devuelve
    `None` si no tiene contenido (degradación controlada, sin evento);
  - `cloze` construye la frase en blanco a partir de `example`
    (`{"phrase": …}` de `services.example_sentences.example_for`), sustituyendo
    la unidad léxica por un hueco `_____`. Reglas de honestidad:
    - la frase **no puede contener la palabra en otro sitio** tras el blanqueo
      (si queda cualquier aparición, el cue se descarta: sería un spoiler);
    - se aplica la misma comprobación anti-spoiler que la definición
      (`_definition_leaks_word`) sobre el resultado;
    - si no hay frase real en el corpus, `None` (nunca se inventa una frase).
- `blank_out(phrase, word) -> str | None` — función pura y testeable del
  blanqueo (alineación reutilizando `services.phonetics.unit_produced`, la
  misma que acredita la producción del drill, V20-01).
- `next_recall_rung(row, evidence) -> str` — peldaño recomendado, puro:
  - sin éxito en `translation` → `translation`;
  - `translation` superado, sin éxito en `definition` → `definition`;
  - `definition` superado, sin éxito en `cloze` → `cloze`;
  - `cloze` superado → `cloze` (mantenimiento espaciado; el techo de la
    escalera es el cloze hasta que exista `situación`).
  El «éxito en el peldaño X» se lee del ledger por `activity_id`
  (`drill:recall:<peldaño>`), no de contadores nuevos.
- **Resolución de disponibilidad (importante)**: `next_recall_rung` es puro y
  NO sabe si el peldaño ideal tiene contenido — y no todos lo tienen: el
  `cloze` exige que la palabra aparezca en el banco de pronunciación
  (`example_for` devuelve `None` si no está). Por eso se separa la decisión
  pedagógica de la disponibilidad con una segunda función pura:

  `resolve_recall_cue(ideal, available) -> str | None`

  - recorre la escalera desde `ideal` hacia ABAJO (hacia más apoyo) y devuelve
    el primer peldaño disponible;
  - `None` si no hay ninguno (el peldaño degrada con `available=false`, sin
    evento, como en V3.34);
  - **nunca degrada hacia ARRIBA**: si el ideal es `translation` y no hay
    traducción ni definición, devuelve `None`; jamás sube a `cloze` (subir la
    exigencia sin evidencia que lo justifique es justo lo contrario de lo que
    V3.37 quiere).

  El dominio calcula `available` a partir del contenido real (traducción,
  definición sin spoiler y frase de corpus) y resuelve; así la decisión
  pedagógica (`next_recall_rung`) y la operativa (`resolve_recall_cue`) se
  testean por separado.

### 2. Servicio puro — automaticidad (`services/evidence.py`)

- `AUTOMATIC_MIN_INDEPENDENT = 2` — umbral declarado y calibrable.
- `is_automatic(evidence: dict) -> bool` — pura: exige
  `independent_successes >= AUTOMATIC_MIN_INDEPENDENT` **y** que esos éxitos
  caigan en días distintos. Como `summarize_evidence` agrega
  `independent_successes` pero no los días independientes, se añade
  `independent_success_days` al resumen (mismo patrón que
  `distinct_success_days`), tanto en la versión pura como en el agregado SQL de
  `summarize_by_target` — con el test de paridad ya existente como red.
- `RECALL_RUNG_EVIDENCE` — nombre del peldaño tal y como se persiste en
  `activity_id`, para que el ledger y el servicio puro compartan un único
  vocabulario.

### 3. Repositorio (`repositories/evidence.py`)

- `summarize_by_target` añade `independent_success_days` (días naturales
  distintos con éxito `independent`/`spontaneous`) y
  `recall_rungs` (histograma de `activity_id` de los eventos de recall). Sin
  migración: `activity_id` ya existe.
- **Paridad pura↔SQL obligatoria** (la fija el test que ya existe desde V3.36:
  el agregado no puede introducir un segundo dialecto del resumen).

### 4. Dominio (`domain/vocabulary.py`)

- `get_recall_prompt(user_id, word, cue=None)` — sirve el peldaño pedido.
  `RecallPromptOut` no cambia de FORMA: `cue_kind` pasa a admitir el tercer
  valor (`cloze`) y el payload gana `support_level` (aditivo) para que la UI sepa
  qué apoyo declara lo que está mostrando. **No se añade un campo `rung`**: cada
  peldaño tiene exactamente un `cue_kind`, así que un segundo identificador sería
  redundante (y dos fuentes de verdad para lo mismo).
- `submit_recall_attempt(user_id, word, answer, *, cue=None,
  response_time_ms=None)`:
  - el servidor **re-deriva** el peldaño con la misma función pura (premisa 21)
    y rechaza con 422 un `cue` no soportado o un peldaño sin contenido para esa
    palabra (sin evento);
  - el evento declara `support_level = RECALL_CUE_SUPPORT[cue]` y
    `activity_id = f"drill:recall:{cue}"` (antes: `drill:recall`, `cued` fijo);
  - **no cambia el scoring**: `correct` sigue siendo igualdad estricta de
    superficie y `classify_recall_error` (V3.36) sigue siendo observacional. Un
    acierto con cloze vale lo mismo que con traducción *para el contador de
    recall*; lo que cambia es lo que el ledger sabe del apoyo.
- La producción ya declara apoyo desde V3.36: **no se toca**.

### 5. Cola de repaso (`services/lexicon.py`, `domain/review.py`)

- `recommend_review_activity(row, matrix, evidence=None)`:
  - sin base receptiva → `recognition` (igual);
  - con base receptiva y recall sin superar → `recall` (igual), pero
    `review_queue_item` expone además `recommended_cue` (`next_recall_rung`);
  - `production_gap` → `sentence` (igual);
  - **nuevo**: si el ítem es `automatic` y no hay hueco de producción →
    `recall` de mantenimiento con `recommended_cue = "cloze"`.
- `review_queue_item` gana `recommended_cue` y `automatic` (aditivos). Sigue
  SIN exponer el cue ni la forma esperada: el cue lo sirve el GET del peldaño
  (premisa 21 + P1-03 de V3.35.1: la cola no spoilea).

### 6. Contrato HTTP (`schemas/vocabulary.py`, `routers/vocabulary.py`)

- `GET /api/vocabulary/drill/recall?user_id&word[&cue=cloze]` →
  `RecallPromptOut {word, available, cue, cue_kind, support_level}`.
  `cue_kind` es el identificador ÚNICO del peldaño servido y pasa a admitir
  `cloze` además de `translation`/`definition` (aditivo: los clientes antiguos
  solo lo ven con los dos valores de V3.34). En un cloze, `cue` es la frase con
  el hueco.
- `POST /api/vocabulary/drill/recall-attempt` (body
  `{word, answer, cue?, response_time_ms?}`) → `RecallAttemptOut` (sin cambios de
  forma; `cue` es aditivo y opcional). Sin `cue`, el servidor se comporta como
  V3.36 (escalera por defecto) para no romper clientes antiguos.
- 422 si `cue` no está en `RECALL_CUES` o si ese peldaño no tiene contenido para
  la palabra; 409 si la palabra ya no tiene pregunta (sin evento).

### 7. Frontend (`wordDrill.tsx`, `api/vocabulary.ts`, `types/api.ts`, `i18n.ts`)

- El peldaño `2 · Recall` renderiza el cue del peldaño servido sin saber de
  más: `RecallStep` ya muestra `prompt.cue` en texto, así que un cloze se pinta
  tal cual (la frase con `_____`), con un estilo monoespaciado para el hueco.
- `api/vocabulary.ts`: `getDrillRecallPrompt(userId, word, cue?)` y
  `submitDrillRecallAttempt(userId, word, answer, responseTimeMs?, cue?)`.
- La latencia de V3.36 se sigue midiendo igual (cue visible → envío).
- `i18n.ts`: claves nuevas para el rótulo del peldaño
  (`dictionary.drill.recallCue.translation|definition|cloze`), es/en, con el
  test de paridad de i18n en verde.
- **No hay UI nueva que spoilee**: el peldaño sigue ocultando la palabra diana
  (`hideTarget`, V3.34) y la cola sigue sin mostrarla en `recall` (V3.35.1).

### 8. Tests

- Backend — nuevo `backend/tests/test_graduated_cues_v337.py`:
  - **puro**: `blank_out` (blanqueo correcto, multi-palabra, descarte si queda
    una aparición, sin frase → `None`); `recall_prompt_for` por peldaño
    (incluida la degradación cuando el peldaño no tiene contenido, y que un
    `cue` no soportado no devuelve nada); `next_recall_rung` (progresión por
    evidencia, sin éxito previo → `translation`, techo en `cloze`);
    `resolve_recall_cue` (ideal disponible → el ideal; ideal sin contenido →
    baja hacia más apoyo; **nunca sube**; sin ningún peldaño → `None`).
  - **automaticidad**: `is_automatic` (umbral, días distintos, `cued` no
    cuenta, `spontaneous` sí) y `independent_success_days` puro↔SQL.
  - **e2e**: recall con `cue=cloze` declara `support_level="guided"` y
    `activity_id="drill:recall:cloze"`; con `cue=translation`, `cued`; un `cue`
    inválido responde 422 **sin evento**; el scoring no cambia (mismo
    `correct`/`error_type` sea cual sea el peldaño); la cola de repaso expone
    `recommended_cue`/`automatic` y **sigue sin exponer la palabra en recall**.
  - **regresión**: `cue=None` mantiene EXACTAMENTE el comportamiento V3.34
    (traducción y, si no, definición) y los tests de `test_recall_v334.py`,
    `test_longitudinal_evidence_v335.py` y `test_learning_evidence_v336.py`
    siguen en verde sin cambios.
- Frontend: vitest del peldaño con cloze (cue con hueco visible, palabra
  oculta, `cue` enviado en el intento) y de la latencia (ya existente).
- Docs y cierre V3.37.0: este briefing, `release-notes-v3.37.0.md`, bump a
  `3.37.0`, `CHANGELOG.md` `[3.37.0]`, hito en `PLAN.md`, nota en
  `docs/RELEVO.md`, versión en `README.md` y `check_release_consistency`
  **3.37.0** exit 0.

## Contrato de red (ejemplos)

GET `/api/vocabulary/drill/recall?user_id=…&word=quokka&cue=cloze` → 200:

```json
{
  "word": "quokka",
  "available": true,
  "cue": "The _____ is a small marsupial from Australia.",
  "cue_kind": "cloze",
  "support_level": "guided"
}
```

Peldaño sin contenido (degradación controlada, sin evento):

```json
{
  "word": "ghost",
  "available": false,
  "cue": "",
  "cue_kind": "",
  "support_level": "guided"
}
```

POST `/api/vocabulary/drill/recall-attempt`:

```json
{ "word": "quokka", "answer": "quokka", "cue": "cloze", "response_time_ms": 4200 }
```

→ 200:

```json
{ "word": "quokka", "correct": true, "expected": "quokka",
  "delayed": false, "recall_days": 1, "error_type": "correct" }
```

## Criterios de aceptación

- ✅ La escalera es una PROGRESIÓN: una palabra con traducción también recibe
  los peldaños `definition` y `cloze` (hoy nunca los recibe).
- ✅ Cada peldaño declara su `support_level` (`cued`/`cued`/`guided`) y su
  `activity_id` (`drill:recall:translation|definition|cloze`) en el ledger.
- ✅ `cue=None` reproduce EXACTAMENTE el comportamiento V3.34 (regresión).
- ✅ Un peldaño sin contenido degrada con `available=false` y **sin evento**;
  un `cue` inválido responde 422 **sin evento**.
- ✅ El scoring NO cambia: `correct` sigue siendo igualdad estricta y
  `error_type` sigue siendo observacional.
- ✅ `is_automatic` exige éxito independiente en días distintos; `cued` no
  cuenta como independiente.
- ✅ Paridad pura↔SQL del resumen (incluido `independent_success_days`).
- ✅ La cola de repaso expone `recommended_cue`/`automatic` sin revelar la
  palabra en `recall` (V3.35.1 P1-03 intacto).
- ✅ Suite completa verde: `ruff` + pytest + vitest + `tsc --noEmit` + build +
  `check_release_consistency` 3.37.0 exit 0 + CI GitHub 6/6.
- ✅ 100% local y determinista: ningún peldaño llama a un LLM.

## Restricciones (qué NO debe hacer el agente)

- **No** añadir migración de BD: `support_level`/`activity_id` ya existen.
- **No** tocar el scoring, FSRS, `error_type` (observacional), ni la semántica
  de `interval_since_last_evidence` (V3.35.1 P1-01).
- **No** implementar `situación` ni generar contenido nuevo con LLM: fuera de
  alcance (V3.38).
- **No** exponer la forma esperada en ningún GET, ni en la cola de repaso.
- **No** romper Recognition (informativo, V3.13) ni el paso Sentence
  (producción oral, micrófono).
- **No** cambiar el contrato de red de forma incompatible: todo aditivo.
- **No** salirse del alcance ni refactorizar módulos no listados.

## Salida esperada

- Diff implementado en los ficheros listados, con `ruff check backend/` limpio.
- Suites verdes (backend/vitest/tsc/build) y `check_release_consistency`
  3.37.0 exit 0.
- `release-notes-v3.37.0.md` + entradas en `CHANGELOG.md`, `PLAN.md`,
  `docs/RELEVO.md` y `README.md`.
- Commit(s) con CI de GitHub en verde (6/6) y la evidencia registrada.
- Resumen final: qué peldaños quedaron soportados, por qué `situación` y
  `free recall` no entran, y los números de tests antes/después.

## Después de V3.37 (para no perder el hilo)

- **V3.38 — `situación` + planner (Optimal Next Task)**: extender el contrato de
  contenido de la caché (`generator_version`) para un enunciado situacional por
  palabra, y generalizar `recommend_review_activity` con retención FSRS + hueco
  de producción + hueco de TRANSFERENCIA por contexto (`context_id`/
  `activity_id`, ya persistidos desde V3.36) + gradiente de apoyo.
- **V3.39 — deudas diferidas**: consumo de `word_breakdown_json` en agregados /
  práctica dirigida de las palabras falladas en listening y palabras tocables en
  transcripts/chat (arrastradas desde V3.30), y cierre de la transferencia por
  contexto de actividad V3.23.
