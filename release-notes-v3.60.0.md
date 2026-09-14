# v3.60.0 — Context Engine 4.0 (Instance Specification → Parameterized Instance)

> Release **SIN migración de BD, SIN bump de `GENERATOR_VERSION` y SIN cambios de
> UI** que cierra los cuatro hallazgos de la auditoría externa **R** de V3.59:
> **P1-1** «3 superficies deterministas siguen siendo memorizables» (una familia
> se agotaba en **3 intentos**), **P1-2** «la instancia puede cambiar la dificultad
> real sin poder declararlo» (`CONTEXT_INSTANCE_KEYS = ("instance", "prompt")` no
> dejaba expresar `scenario`/`goal`/`register`/`difficulty_delta`/`skill_delta`),
> **P2-6** «Context Engine todavía manual/finito» (20 × 3 = 60 consignas escritas
> a mano) y **P2-7** «la instancia no genera dificultad» (la superficie era solo
> `presentation_surface`).
> V3.60 sustituye las consignas escritas a mano por un **ESPACIO de instancias
> PARAMETRIZADO** por familia: **FAMILIA → ESPECIFICACIÓN → INSTANCIA**. La
> **identidad de evidencia NO se toca** (`context_id` sigue siendo la FAMILIA y el
> ledger no cambia de forma), el contenido sigue siendo **DECLARADO** (no hay LLM
> en el camino de la evidencia: lo que se genera es la COMBINACIÓN de valores
> declarados, no el texto) y la dificultad de la **superficie servida** pasa a ser
> **explícita y persistida de forma aditiva**. Determinista (premisa 21).

## Contexto

V3.59 separó **FAMILIA** de **INSTANCIA** y amplió el banco de **20 consignas a 60
superficies**, pero dejó el problema a medias en dos dimensiones:

1. **El banco seguía siendo FINITO y escrito a mano.** Tres redacciones por familia
   se agotan en tres estancias: a partir de la cuarta el motor vuelve a rotar sobre
   las mismas tres y el alumno puede memorizar la estructura. El límite no era de
   datos, era de **contrato**: cada superficie era una cadena literal en el banco.
2. **La superficie no podía declarar su carga.** `CONTEXT_INSTANCE_KEYS` era
   `("instance", "prompt")`, así que una redacción que exige MÁS discurso (una
   contribución escrita formal, una audiencia crítica) no podía decirlo: el ledger
   persistía siempre el vector de la **familia**. La instancia era pura
   `presentation_surface`.

Pasar a **contenido generado por LLM** habría roto la premisa 21 (el juicio y la
evidencia deben ser deterministas y offline). V3.60 hace lo contrario: mantiene el
contenido **declarado** y parametriza su **combinación**.

## Cambio

```text
FAMILIA   = identidad pedagógica + unidad de EVIDENCIA (context_id del ledger)
            topic / communicative_goal / discourse_type / social_relation /
            time_reference / interaction_type / register / cefr /
            difficulty_vector / skills / lexical_environment / syntactic_focus
          = NO cambia en V3.60 (ni una dimensión, ni un umbral)

ESPECIFICACIÓN = instance_space DECLARADO por la familia
            {"template": "... {when} ...", "selection": ("when", "who"),
             "slots": {"when": [valores], "who": [valores]},
             "difficulty_delta": {...}}
          = plantilla + slots DECLARADOS (nada se inventa)

INSTANCIA = superficie concreta de la MISMA familia
            {instance: slug estable, prompt: plantilla interpolada,
             scenario / goal / register, difficulty_delta, skill_delta,
             generated: True}

ESPACIO   = [0]      la consigna HISTÓRICA de la familia (byte a byte)
            [1..2]   las `instances` DECLARADAS de V3.59 (mismos índices)
            [3..]    las superficies GENERADAS por la especificación

ROTACIÓN  = el intento N del ítem en esa familia sirve la superficie N % len(espacio)
CARGA     = familia + delta de la superficie (clamp 1..5) = carga EFECTIVA servida
```

### A. Lista blanca ampliada, NO identitaria — `services/transfer.py`

`CONTEXT_INSTANCE_KEYS` pasa de dos claves a siete:

```python
CONTEXT_INSTANCE_KEYS = (
    "instance", "prompt", "scenario", "goal", "register",
    "difficulty_delta", "skill_delta",
)
```

Las cinco claves nuevas son **METADATOS NO IDENTITARIOS**: describen la situación
concreta y con qué registro se sirve, y el **AJUSTE** de carga o las competencias
que la redacción añade. Lo que sigue **PROHIBIDO** en una instancia es la
identidad: `id`, las seis dimensiones core, `cefr`, `difficulty_vector`, `skills`,
`lexical_environment` y `syntactic_focus`. Un test fija la frontera: la
intersección entre `CONTEXT_INSTANCE_KEYS` y las claves de familia es exactamente
`{"prompt"}` (y solo porque la consigna es la única clave compartida por los dos
niveles: la familia la usa en su superficie 0, la instancia en la suya).
`_surface_details` **lee solo** las claves de la lista blanca: cualquier otra
declaración se **IGNORA** —esa es la garantía de no-fragmentación del ledger—.

### B. Espacio mínimo y techo — `CONTEXT_INSTANCE_SPACE_MIN`/`MAX`

- `CONTEXT_INSTANCE_SPACE_MIN = 12`: mínimo de superficies **TOTALES** por familia
  (la 0, las declaradas y las generadas). Es el invariante anti-memorización de
  Context Engine 4.0: con **≥12** redacciones la rotación no se puede aprender de
  memoria y sigue siendo determinista y explicable. Verificado por test **sobre el
  banco real**.
- `CONTEXT_INSTANCE_SPACE_MAX = 96`: **techo** del espacio de una familia. El
  recorte deja un **prefijo** del producto cartesiano en orden declarado, así que
  el espacio no puede crecer sin control al añadir slots.

### C. Especificación → superficie (núcleo puro y determinista)

- `_slug(value)`: etiqueta canónica derivada del **CONTENIDO** declarado (minúsculas
  y `_`), nunca de `hash()` (sembrado por proceso) ni del orden de un diccionario:
  es estable entre ejecuciones.
- `_skill_delta(raw)`: competencias que **AÑADE** una superficie, restringidas al
  vocabulario `CONTEXT_SKILLS` (deduplicadas y en su orden). Una superficie **no
  puede inventar** competencias.
- `_instance_value(raw)`: un valor de slot es texto (`"a longer trip"`) o un dict
  `{value, scenario, goal, register, difficulty_delta, skill_delta}`. `value` es
  **OBLIGATORIA**: sin texto el valor se **DESCARTA** (no se inventa contenido).
- `_template_fields(template)` / `_slot_order(selection, fields)`: la plantilla usa
  placeholders `{nombre}` en minúsculas; una plantilla con llaves sueltas es
  **INSERVIBLE**. `selection` declara el orden en que se **MEZCLAN** los slots, así
  que son los que entran siempre que el techo recorte el producto.
- `context_instance_spec(context)`: normaliza el `instance_space` y **valida** que
  todos los placeholders tengan un slot con al menos un valor utilizable; si algo
  falta devuelve `{}` y la familia conserva sus superficies declaradas.
- `_expand_spec(spec)`: producto cartesiano determinista (orden declarado, recorte
  a `CONTEXT_INSTANCE_SPACE_MAX`, dedup por slug), suma los deltas por dimensión
  (`difficulty.normalize_delta`) y descarta toda combinación que no se pueda
  renderizar. **Sin aleatoriedad con estado y sin LLM.**
- `context_instance_details(context)`: el espacio **COMPLETO** en un único orden
  (histórica → declaradas de V3.59 → generadas), deduplicado por consigna
  normalizada. Las claves de `CONTEXT_INSTANCE_DETAIL_KEYS` están **siempre**
  presentes, con `""`/`{}`/`()` cuando la superficie no aporta nada.
- `context_instances(context)`: se conserva como **vista de dos claves**
  (`{"instance", "prompt"}`) sobre el espacio completo, para no romper el contrato
  puro que fijó V3.59.
- `context_instance_metadata(context, index)`: metadatos normalizados de una
  superficie más `skills` = unión entre las competencias de la **familia** y las
  que la superficie **añade** (orden canónico `CONTEXT_SKILLS`). `skill_delta` es
  **explicabilidad**: no entra en el eje de evidencia `spontaneous_use` ni cambia
  la modalidad que la tarea evalúa (`assessed_skill`).

### D. Dificultad efectiva — `services/difficulty.py`

Dos funciones **puras** nuevas (`_DELTA_MIN = -2`, `_DELTA_MAX = 2`):

- `normalize_delta(vector, minimum=-2, maximum=2)`: deltas **enteros** por
  dimensión canónica, recortados a ±2, ignorando claves desconocidas y valores
  fraccionarios o basura. `{}` si no queda nada válido o si el valor no es un
  `Mapping`: **sin delta declarado el ajuste es NULO, nunca inventado**.
- `apply_delta(vector, delta)`: `base + delta` recortado al envelope canónico
  **1..5**. Un delta que apunte a una dimensión que la base **no declara** se
  **IGNORA** (no se inventa carga donde la familia no la declaró). Con delta vacío
  o inválido el resultado es `normalize_vector(vector)` **exacto**: es la garantía
  de degradación de la release.

La familia sigue declarando la carga **ABSOLUTA**; la superficie solo declara el
**MATIZ** (±2) dentro del mismo escenario, que es la frontera que impide
reinterpretar la identidad.

### E. Degradación EXACTA (invariante de no-regresión)

- `context_instance_index(context, 0)` devuelve **0**: la superficie servida sin
  intentos es la consigna **histórica**, byte a byte.
- `space[:3]` reproduce byte a byte las **tres superficies de V3.59**: la rotación
  no cambia, solo se **prolonga**.
- Sin delta declarado, `context_instance_difficulty` devuelve el vector de la
  familia **exacto**.

### F. El ledger persiste la superficie servida — `domain/vocabulary.py`

`_record_transfer_evidence` sustituye `served=transfer.context_difficulty(context_id)`
por `served=transfer.served_difficulty(context_id, attempts_by_context)`, resuelto
con el **MISMO** resumen de evidencia que el GET/POST. `served_difficulty` cuenta
los intentos con `_attempts_for` —el mismo insumo que la rotación de `context_for`—
y devuelve la carga **EFECTIVA** de la superficie que ese intento sirve. Así la
dificultad guardada por evento corresponde a la **tarea realmente servida**,
incluida su superficie. `observed_difficulty` sigue siendo la **proyección legacy**
de `served_difficulty`, de modo que V3.53–V3.59 leen exactamente lo mismo.

**Sin columnas nuevas, sin `GENERATOR_VERSION` y sin reinterpretar filas pasadas:**
las superficies sin delta (incluida siempre la 0) escriben **bytes idénticos** a
V3.59.

### G. Banco: `instance_space` en las 20 familias

Cada familia declara `template` + **2 slots** (4 valores cada uno) → ≥12
combinaciones, con **`selection`** ordenando la mezcla y deltas **solo donde son
reales** (p. ej. `debate`/`mediation`/`academic` con `discourse +1`, audiencia
crítica con `interaction +1`, contribución escrita formal con
`skill_delta: written_production`). Las **dos `instances` escritas a mano de V3.59
se conservan tal cual** y ocupan los índices **1 y 2**, así que el contenido
histórico no se reescribe. El `template` **no contiene la unidad objetivo** (la
consigna sigue dando ESCENARIO, no palabra) y no deja llaves sueltas: los mismos
invariantes que fijó el test de V3.59.

**El banco pasa de 60 a 358 superficies** (20 familias; 16–19 por familia) sin
tocar ninguna `id` y sin fragmentar el ledger.

## NO cambia

- `transfer_state` ni sus umbrales; `context_signals`; `context_diversity` ni
  `CONTEXT_DIVERSITY_MIN`; `context_distance`; `_novelty_score`; `_stable_index`.
- **Ninguna** clave nueva entra en `CONTEXT_DIMENSIONS`: la superficie **no
  participa** en la selección de familia. El test de no-regresión compara el
  payload con y sin `attempts_by_context` **clave por clave** salvo las volátiles.
- `context_difficulty()` (la carga de la **familia**): los llamadores de solo
  lectura quedan intactos. `CEFR_CAPACITY` y el Difficulty Engine de V3.52–V3.55.
- La **identidad** de las 20 familias, los seis contextos **congelados** y sus
  consignas como superficie 0.
- El scoring (`score_transfer_attempt`), FSRS, el planner y el Sense Engine de
  V3.58.
- El contrato de V3.59: nada se quita ni se renombra (solo se **añaden** 8 claves).

## Contrato aditivo

`context_for` gana 8 claves en **todos** los retornos, incluido el temprano de
banco vacío:

| Clave | Qué declara |
| --- | --- |
| `instance_scenario` | escenario concreto de la superficie servida |
| `instance_goal` | objetivo comunicativo concreto de esa redacción |
| `instance_register` | registro específico de la superficie (`""` = el de la familia) |
| `instance_difficulty_delta` | ajuste declarado por dimensión |
| `instance_difficulty_vector` | carga **EFECTIVA** = familia + delta (clamp 1..5) |
| `instance_difficulty` | la anterior proyectada a entero (1..5) |
| `instance_skills` | competencias efectivas (familia ∪ `skill_delta`) |
| `instance_generated` | `True` si la superficie la generó la especificación |

Las **28 claves** del payload de V3.59 quedan intactas y **fijadas por test**
(**36** en total). `TransferContextOut` (`schemas/vocabulary.py`) las declara con
espejo opcional en `frontend/src/types/api.ts`. **Sin cambio de UI.**

## Tests

Nuevo `backend/tests/test_context_engine_v360.py` (**23**):

- **Frontera de identidad:** la lista blanca nunca toca la familia
  (intersección `{"prompt"}`) y una superficie que intente declarar
  `cefr`/`topic`/`difficulty_vector` es **IGNORADA**.
- **Anti-memorización:** **cada** familia alcanza `CONTEXT_INSTANCE_SPACE_MIN`
  (≥12 superficies) y el banco declarado no se agota en tres intentos.
- **Preservación de V3.59:** `space[:3]` es **byte a byte** la histórica + las dos
  declaradas, y las superficies declaradas conservan sus índices.
- **Expansión determinista:** dos llamadas dan lo mismo, el `selection` fija el
  orden de mezcla, el cap trunca el **prefijo** del producto y las consignas
  generadas son **limpias y distintas** (sin llaves sueltas ni duplicados).
- **Especificación:** normalización de slots/valores/delta, `value` obligatoria,
  `skill_delta` restringido al vocabulario, y una especificación **inservible**
  (plantilla sin placeholders válidos, slot sin valores) deja a la familia **solo**
  con sus superficies declaradas.
- **Equivalencia pedagógica (el test que pide la auditoría):** todas las
  superficies de una familia comparten sus **6 dimensiones core**, `cefr` y las
  `skills` de familia; solo difieren en las claves declaradas.
- **Dificultad efectiva:** `normalize_delta` respeta el vocabulario canónico y
  recorta a ±2; `apply_delta(v, {})` es `normalize_vector(v)` **exacto**;
  `served_difficulty` **coincide** con el vector de la superficie que sirve
  `context_for` y degrada a `{}` sin familia reconocible.
- **Rotación sobre el espacio completo** y robustez de `details`/`metadata`
  (ids, `None`, basura, índices fuera de rango; nunca lanzan) con las claves
  siempre presentes.
- **Contrato:** payload aditivo sobre V3.59 (36 claves), banco vacío con los
  **mismos defaults** y la elección de **familia** intacta.
- **End-to-end HTTP:** la cuarta estancia en la misma familia sirve una superficie
  **GENERADA** (no una de las tres históricas) y el evento persistido lleva el
  vector **efectivo**.

Ajuste deliberado y documentado en `backend/tests/test_context_engine_v359.py`:
`len(...) == 1 + MIN` → `>= 1 + MIN` (V3.60 **amplía** el espacio por diseño); el
resto de invariantes de V3.59 se mantiene sin cambios.

## Verificación

```text
ruff check .                                  All checks passed
pytest tests/ -q                              2335 passed
pytest launcher/tests -q                      75 passed
npx tsc --noEmit                              OK
npm test                                      76 ficheros / 651 tests
npm run build                                 OK
python scripts/check_release_consistency.py   3.60.0
```

## Fuera de alcance (V3.61+)

- `context_instance` **en el ledger** (evidencia instance-aware): hoy la evidencia
  sigue siendo de FAMILIA por diseño.
- Motor de **política** de instancia (spacing / fallo / dificultad) y
  `Context Engine 5.0`.
- **Student Skill State 3.0**, WSD real, aprendizaje de `P(success | learner,
  task)`, Observed Task Difficulty 2.0 y **Planner 3.0**.
- El contrato/prompt de generación de sentidos y su bump de `GENERATOR_VERSION`, y
  la ponderación de la adecuación en `transfer_confidence`.
- Cualquier uso del LLM en el camino de la evidencia (premisa 21).

## Siguiente paso

V3.61 — el **motor de política de instancia** (cuándo repetir una superficie,
cuándo forzar una nueva, cómo pesa el fallo) y la **evidencia instance-aware** como
decisión aparte, con migración declarada si toca el ledger.
