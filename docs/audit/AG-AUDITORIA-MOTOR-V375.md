# AG · Auditoría del motor de dominio/pedagogía — V3.75.0

> **Release auditada:** V3.75.0 · **commit:** `aa9dbaaa94e361f9673197de4cb797ee97888743`
> **Tag:** `v3.75.0` (anotado) · **rama:** `main` · **árbol:** limpio (solo
> `backend/data/tutor.db-shm` / `-wal` sin seguimiento)
> **Fecha de la auditoría:** 2026-09-19
> **Instrumento:** lectura de fuente + `rg` + ejecución de las funciones puras
> del motor con el intérprete del proyecto (`backend/.venv`)
> **Dossieres que NO repite:** `AA`–`AF` (V3.70), `RE`/`RF` (V3.71), `RC`/`RD`,
> `VERIFICACION-SEGURIDAD-V373`, `TEMPLATE`

## Alcance

**Entra:** la **coherencia interna del motor de dominio/pedagogía** del backend.

- Fuente única de verdad de umbrales, pesos y constantes del motor (AG-1).
- Caminos de decisión paralelos: planners, scorers, agregadores y derivadores de
  banda (AG-2).
- Modelos de retención y programación paralelos (AG-3).
- Fragilidad estructural: ciclos latentes, estado de módulo, reloj, aleatoriedad
  y dirección de dependencia (AG-4).
- Fallos silenciosos en la ruta de decisión (AG-5).
- Cobertura de test de los hubs del motor (AG-6).

**No entra (declarado):**

- **Contenido, currículum, corpus, instrumentos y adecuación CEFR**: son el
  objeto de `AA`–`AE` y de los nueve subcomandos de `scripts/audit_dossier.py`
  (V3.70). Este dossier **no** regenera esos ejes ni los reinterpreta.
- **Eficacia pedagógica, aprendizaje real y calibración de umbrales con
  alumnos**: sin cohortes no es medible (declarado en `AA:32`, `AD:19-21`,
  `AE:22-23` y `PARKED.md:8-16`).
- **Frontend, launcher, CI, seguridad de sesión y red**: fuera por decisión de
  alcance de esta auditoría.
- **Runtime, instalación y hardware**: objeto de `RE`/`RF` y de los gates G1–G6.
- No se re-audita el eje cerrado **AE-06** (corte de banda): se **verifica** que
  sigue cerrado y con candado (§AG-2.4).

## Método

1. **Solo lectura.** No se ha modificado ningún fichero de producto, ni
   configuración, ni umbral. El único fichero creado es este dossier.
2. **Evidencia exigida.** Cada hallazgo lleva `archivo:línea` o comando
   reproducible. Se descartó toda afirmación que la lectura no pudiera sostener.
3. **Distinción declarado / árbol / reproducible.** Se separa lo que la release
   **declara**, lo que el **árbol contiene** y lo que un **comando reproduce**.
4. **Las funciones puras se ejecutan.** Los dos hallazgos que afirman
   *divergencia de resultado con la misma entrada* (AG-2.2 y AG-2.3) y el de
   *intervalos de repaso divergentes* (AG-3.1) se comprobaron con el intérprete
   del proyecto, no por inspección (§Regenerar).
5. **Regla de honestidad de la casa** (`Y` §28, citada en `AF:26`): distinguir
   siempre **«el motor no cumple»** de **«esta lectura no lo demuestra»**, y
   **«riesgo funcional»** de **«deuda de mantenibilidad»**.
6. **Corrección de las sospechas de partida.** La lectura previa a la auditoría
   dio por no cubiertos `skill_axis.py`, `services/cefr.py` y
   `domain/vocabulary.py`. El §AG-6 **desmiente** esa sospecha con evidencia: la
   cobertura existe. Se registra la corrección en lugar de silenciarla.

## Evidencia

### Baseline y trazabilidad

| Concepto | Valor | Procedencia |
|---|---|---|
| Commit | `aa9dbaaa94e361f9673197de4cb797ee97888743` | `git rev-parse HEAD` |
| Tag | `v3.75.0` | `git describe --tags --exact-match` |
| Rama | `main` | `git rev-parse --abbrev-ref HEAD` |
| Árbol | limpio | `git status --porcelain` |
| Líneas del motor | 43 módulos en `domain/` + `services/` | `Get-ChildItem` |
| Único gate de motor en el arnés | **G7 `pedagogia`**, estado `pending` | `scripts/validation_gate.py:143`; `KIT-VALIDACION-GATES.md:12-14` |

**Regla de evidencia aplicada en todo el documento:**

- `[D]` **declarado**: aparece escrito en el código o en un documento.
- `[A]` **árbol**: se verificó leyendo el fichero en este commit.
- `[R]` **reproducible**: se ejecutó y el resultado está en este documento.

---

### AG-1 · Fuente única de verdad de umbrales y constantes

Se distinguen dos casos que **no** deben tratarse igual:

- **(D)** **regla duplicada**: dos definiciones del *mismo* concepto. Si una
  cambia, la otra queda obsoleta en silencio.
- **(C)** **coincidencia de valor**: dos conceptos *distintos* con el mismo
  número. Unificarlas sería el error.

#### AG-1.1 — `MASTERY_MIN_PRODUCTIONS` / `MASTERY_MIN_DAYS` — (D) `[A]`

```python
# backend/services/vocabulary.py:39-40
MASTERY_MIN_PRODUCTIONS = 3
MASTERY_MIN_DAYS = 2
```

```python
# backend/services/lexicon.py:69-72
# Mínimos de producción espaciada para considerar una palabra dominada
# (coinciden con `services.vocabulary`).
MASTERY_MIN_PRODUCTIONS = 3
MASTERY_MIN_DAYS = 2
```

**Misma regla, dos definiciones.** El comentario de `lexicon.py:70` **admite**
que coinciden en lugar de importarlas. La misma pareja de valores se usa con
**dos semánticas distintas en el mismo commit**:

- `vocabulary.classify:53-54` las usa como **puerta** (`mastered` sí/no).
- `lexicon.item_mastery:317-326` las usa como **saturación** de una escala 0..1.
- `lexicon.item_status:388` vuelve a usarlas como **puerta**.

Verificado: `rg -n "MASTERY_MIN_PRODUCTIONS" backend` → definiciones en
`vocabulary.py:39` y `lexicon.py:71`; usos en `vocabulary.py:53`,
`lexicon.py:317,322,388`. **No existe ningún import entre ambos.**

#### AG-1.2 — El umbral de aprobación de pronunciación: 3 definiciones, 1 viva — (D) `[A]`

```python
# backend/services/pronunciation.py:10-11
# Umbral de "buena pronunciación" (porcentaje de similitud).
PASS_THRESHOLD = 80
```

```python
# backend/services/pronunciation_routes.py:33-34
# Es el mismo PASS_THRESHOLD del scorer de read-aloud (`score_pronunciation`).
PRONUNCIATION_PASS_THRESHOLD = 80
```

```python
# backend/services/listening.py:212
PRODUCTION_PASS_SCORE = 80
```

Los tres números son el mismo sobre `services.phonetics.composite_score`
(escala 0..100); `pronunciation.py:19,39` y `listening.py` lo aplican.

**Hallazgo concreto:** `PRONUNCIATION_PASS_THRESHOLD` está **muerto**. Caso
`[R]` y `[A]`:

```
rg -n "PRONUNCIATION_PASS_THRESHOLD" .        → solo backend/services/pronunciation_routes.py:34 (la definición)
```

El código que realmente aplica el umbral es `services.pronunciation.PASS_THRESHOLD`
(importado como `PRONUNCIATION_PASS_SCORE` en `services/skill_state.py:78` y vía
`score_pronunciation` en `domain/pronunciation_routes.py:20`,
`routers/pronunciation.py:16`, `domain/vocabulary.py:49`). Es decir: existe una
constante que **se declara para documentar una regla que no gobierna**, y su
comentario afirma ser la misma regla que otra. Es exactamente el patrón
«propiedad declarada sin respaldo» que `AF:64-71` elevó como P1 en el eje de
contenido; aquí se reproduce en el código del motor.

#### AG-1.3 — El mínimo de transferencia: 6 definiciones, 4 módulos — (D+declarado) `[A]`

| Módulo | Constante | Valor | Cantidad que mide |
|---|---|---|---|
| `backend/services/evidence.py:301` | `CONTEXT_TRANSFER_MIN` | 2 | contextos distintos con éxito |
| `backend/services/evidence.py:654` | `TRANSFER_MIN_SUCCESSES` | 2 | éxitos **limpios** totales |
| `backend/services/planner.py:167` | `TRANSFER_MIN_SUCCESS_CONTEXTS` | 2 | contextos distintos |
| `backend/services/planner.py:171` | `TRANSFER_MIN_SUCCESSES` | 2 | éxitos totales |
| `backend/services/decision_projection.py:125` | `TRANSFER_MIN_CONTEXTS` | 2 | contextos distintos |
| `backend/services/transfer.py:177` | `CONTEXT_DIVERSITY_MIN` | 2 | **dimensiones distintas** |

Los espejos están **declarados a propósito** en el propio código:

- `evidence.py:652-653`: *«espejo de `planner.TRANSFER_MIN_SUCCESSES`; ambos se
  mantienen en 2»*.
- `planner.py:166`: *«espejo de `services.evidence.CONTEXT_TRANSFER_MIN`»*.
- `decision_projection.py:122-124`: *«espejo declarado de
  `planner.TRANSFER_MIN_SUCCESS_CONTEXTS`; **no se importa** para no acoplar la
  proyección al planner»*.

**Lo que esta auditoría añade:** no son 6 copias de un solo número, son **tres
cantidades distintas con el mismo valor 2** (contextos, éxitos, dimensiones) más
un cuarto caso (`transfer.CONTEXT_DIVERSITY_MIN` no es «2 contextos» sino
«2 dimensiones diferentes»). `planner.py` contiene **dos de las tres** a dos
líneas de distancia (`:167` y `:171`). El riesgo no es que hoy discrepen —hoy
coinciden— sino que **un cambio de uno de los tres conceptos se lea como un
cambio de los otros dos**, porque el número no los distingue.

**Mitigación ya existente:** `tests/test_transfer_evidence_v347.py:264` fija
`evidence.TRANSFER_MIN_SUCCESSES == 2`; `tests/test_transfer_v343.py:131` fija
`transfer.CONTEXT_DIVERSITY_MIN == 2`. Ninguno fija que los espejos **coincidan
entre sí** (no hay test que compare `planner.TRANSFER_MIN_SUCCESS_CONTEXTS` con
`evidence.CONTEXT_TRANSFER_MIN`).

#### AG-1.4 — El umbral `0.7` — una regla duplicada y varios literales mágicos — (D) `[A]`

La **misma cantidad física** (probabilidad de recuperación de la curva de
olvido) tiene dos umbrales idénticos en dos módulos que no se importan:

| Módulo | Constante | Valor | Semántica |
|---|---|---|---|
| `backend/services/forgetting.py:22` | `REVIEW_THRESHOLD` | 0.7 | «toca repasar» |
| `backend/services/adaptive.py:129` | `STABILITY_RETRIEVAL_THRESHOLD` | 0.7 | «la destreza es inestable» |

La misma fórmula subyacente (`forgetting.retrieval_probability`) gobierna ambas.
Es **regla duplicada**, no coincidencia.

Además, el mismo `0.7` aparece como **literal sin nombre** en puertas del motor:

- `backend/domain/academy.py:1983` — `float(entry.get("score") or 0.0) < 0.7`
  decide si se crea o se mantiene una carta FSRS de destreza. El módulo **ya
  importa** la regla de olvido en la línea 33
  (`from services.forgetting import review_due as forgetting_review_due`) y sin
  embargo escribe el umbral a mano. (Nota honesta: aquí compara `score` de
  dominio, no `retrievability`; el literal no es *la misma* regla, pero tampoco
  está declarado en ninguna parte.)
- `backend/domain/academy.py:1497` —
  `assessment_v2.PASS_THRESHOLDS.get(session["kind"], 0.7)`: un **default
  silencioso** que no existe en la tabla `PASS_THRESHOLDS`
  (`assessment_v2.py:38-44`). Un `kind` no contemplado se aprueba con un umbral
  que ninguna tabla declara.

#### AG-1.5 — Pares de valor idéntico con semántica distinta — (C) `[A]`

Deben **quedar documentados como no unificables**, o alguien los unificará por
error:

| Concepto A | Concepto B | Valor | Por qué no son la misma regla |
|---|---|---|---|
| `grammar.py:13` `CONFIRMED_THRESHOLD` (confianza mínima para confirmar un error detectado) | `curriculum.py:190` `DEFAULT_THRESHOLD` (dominio mínimo de una destreza de objetivo) | 0.8 | Uno es confianza de un **detector**; el otro, dominio de un **alumno** |
| `academy.py:41` `STREAK_TARGET` (racha que satura el bonus de consistencia del mastery EMA) | `grammar.py:16` `MASTERY_STREAK` (usos correctos consecutivos para retirar un error) | 3 | Uno alimenta una **fórmula de score**; el otro **cierra un error** |
| `assessment_v2.py:62` `RETENTION_STABLE_RATIO` (ratio delayed/initial) | `listening.py:1065` `ROUTE_RETENTION_STABLE_RATIO` (ratio de ruta) | 0.9 | Distinto instrumento y distinta población |
| `fsrs.py:45` `REQUEST_RETENTION` (objetivo del scheduler) | `fsrs.py:66` `DUE_RETRIEVABILITY` (corte de la cola due) | 0.9 | Coinciden hoy; son parámetros independientes del mismo modelo |
| `assessment_v2.py:59` `RETENTION_MIN_DAYS` | `unit_review.py:33` `UNIT_REVIEW_WINDOWS_DAYS[0]` | 7 | Ventana formal de reevaluación vs primera ventana de repaso de unidad |
| `lexicon.py:99` `RETENTION_MIN_INTERVAL_DAYS` | `assessment_v2.py:59` `RETENTION_MIN_DAYS` | 1 vs 7 | **Colisión de nombres**: dos «mínimo de retención» que miden cosas distintas (días naturales entre recuperación léxica vs días entre evaluación formal y reassessment) |

El último caso es el más delicado **por el nombre**, no por el valor: dos
constantes que empiezan por `RETENTION_MIN_` en dos módulos del motor y que
significan intervalos de naturaleza distinta y magnitud distinta (1 día vs
7 días). `lexicon.py:1229` la documenta bien; el problema es que un lector que
cambie una creerá estar cambiando la otra.

#### AG-1.6 — `PASS_THRESHOLDS`: la tabla declarada y su default no declarado — (C) `[A]`

`assessment_v2.PASS_THRESHOLDS` (`assessment_v2.py:38-44`) declara
`formative 0.70 · unit 0.75 · progress 0.80 · level 0.80 · retention 0.70`.
En `domain/academy.py:1497` el fallback es `0.7`. La tabla **no tiene clave
`default`**, de modo que el fallback es un literal fuera de la tabla. La
coincidencia con `formative`/`retention` (0.70) es accidental.

---

### AG-2 · Motores de decisión paralelos

#### AG-2.1 — Dos motores de «qué toca ahora», cada uno con su propia aritmética

| | Motor A | Motor B |
|---|---|---|
| Función | `planner.priority_score` (`planner.py:1239`) | `adaptive.priority_score` (`adaptive.py:793`) |
| Pesos | **declarados** en `PRIORITY_WEIGHTS` (`planner.py:50-56`): `forgetting 0.35 · gap 0.30 · weakness 0.20 · support 0.10 · latency 0.05` | **inline**: `0.4 * base + 0.3 * forgetting + 0.2 * weakness + 0.1 * evidence` (`adaptive.py:806`) |
| Base | — | `NEXT_BEST_PRIORITY` (`adaptive.py:719-725`) |
| Normalización | `LATENCY_CEILING_MS` declarado (`planner.py:63`) | `/ 10.0` literal (`adaptive.py:807`) |
| Predicción de éxito | sí, `SUCCESS_BY_MARGIN` + ELV (`planner.py:82-91`, `select_task_by_elv:832`) | no (`adaptive.py:800-801` lo declara: «No es un modelo predictivo») |
| Superficie | cola léxica: `lexicon.recommend_review_activity:614` y `:1021` | `GET .../next-best-activity`: `routers/academy.py:214` → `domain/academy.py:2930` |

Ambos producen un `why` con funciones homónimas
(`planner.explain_priority:1316`, `adaptive.explain_priority:828`).

**Hallazgo:** los pesos del Motor B son los únicos **no declarados** de los dos.
El proyecto aplica su propio principio («pesos declarados») en `planner` y no en
`adaptive`.

**Lo que esta lectura NO demuestra:** que los dos motores se contradigan. Operan
sobre **pools distintos** (pasos de sesión del currículum vs ítems léxicos), así
que una discrepancia entre ellos no es necesariamente un error. Lo que sí se
demuestra es que **no existe un árbitro único** y que nada comprueba que
coincidan. Severidad: coherencia/UX, no corrección.

#### AG-2.2 — Dos fórmulas de `overall` para el mismo concepto — (D, verificado) `[A][R]`

```python
# backend/services/academy.py:700 (score_items)
"overall": round(correct / answered, 3) if answered else 0.0,
```

```python
# backend/services/academy.py:1246-1249 (exam_result)
overall = (
    round(sum(s["score"] for s in skills.values()) / len(skills), 3)
    if skills else 0.0
)
```

`score_items` pondera por **ítem**; `exam_result` pondera por **destreza** (media
de medias). Con los mismos ítems y las mismas respuestas:

```
[R] 4 ítems: 1 de 1 correcto en `grammar`, 0 de 3 en `writing`
    exam_result.overall               = 0.5     (media de 1.0 y 0.0)
    score_answers/score_items.overall = 0.25    (1 acierto de 4)
```

**Factor 2 de diferencia en el mismo concepto.** `assessment_v2.py:36-38`
**declara** la distinción («aquí el overall es la regla uniforme de la
escalera»), lo cual es mejor que nada, pero el campo se llama igual (`overall`)
y se consume en dos caminos distintos del mismo dominio: la escalera
Assessment 2.0 (`domain/academy.py:1814`, `score_answers`) y el examen de nivel
heredado (`domain/academy.py:3842`, `exam_result`). Las dos rutas pueden
describir el **mismo nivel** (A1/B1 tienen examen final, `AE`; y la escalera
tiene el `kind` `level`). Un informe que compare ambos `overall` comparará dos
definiciones.

#### AG-2.3 — Tres `difficulty_from_vector`, una defensiva y dos no — (D, verificado) `[A][R]`

| Módulo | Línea | Filtra valores no numéricos |
|---|---|---|
| `backend/services/listening.py` | 278 | no |
| `backend/services/speaking.py` | 109 | no |
| `backend/services/transfer.py` | 269 | **sí** (`isinstance(..., (int, float)) and not isinstance(..., bool)`) |

Los docstrings **declaran** que es la misma regla: `speaking.py:112` («Misma
regla que `services.listening.difficulty_from_vector`») y `transfer.py:271-272`.
Pero ante la misma entrada divergen:

```
[R] vector {"a": True, "b": 4}
    listening.difficulty_from_vector → 2
    speaking.difficulty_from_vector  → 2
    transfer.difficulty_from_vector  → 4
```

`transfer` descarta el booleano; los otros dos lo suman (`True == 1`). Además,
con un valor no numérico (`{"a": "x", "b": 4}`) `listening`/`speaking` **lanzan
`TypeError`** y `transfer` devuelve `1`.

**Honestidad de severidad:** en producción los vectores llegan como
`dict[str, int]` 1..5 desde el currículum, así que la divergencia es **latente**
hoy. Se registra porque el docstring afirma equivalencia y la equivalencia no es
demostrable por lectura: solo dos de las tres son defensivas.

#### AG-2.4 — El corte de banda CEFR: verificado **cerrado** (AE-06)

Se confirma que el hallazgo AE-06 de V3.72 **sigue cerrado** en este commit:

- El corte vive en **un solo** sitio: `backend/services/cefr.py:62`
  (`BAND_BOUNDARIES = (1.5, 2.5, 3.5, 4.5, 5.5)`) + `level_for_numeric:75`.
- Los tres estimadores **delegan**: `adaptive.numeric_to_level:52-57`,
  `academy.theta_to_level:1034-1039`, `cefr.heuristic_band:100`.
- `rg -n "1\.5, 2\.5, 3\.5"` en `backend/` solo devuelve la definición y su test.
- Candado: `tests/test_band_thresholds_v372.py:98-106,117`.

**Sin hallazgo nuevo en este subeje.** Los restantes estimadores
(`student_state.floor_level:75`, `learner_skill.level_from_capacity:186` y
`level_from_skill_capacity:197`, `listening.current_level:1747`,
`academy._demonstrated_level:620`, `adaptive.estimated_level:60`) **no son
duplicados del corte**: miden conceptos distintos (suelo, capacidad equivalente,
nivel de ruta, nivel certificado, nivel estimado). Su prioridad de resolución
está declarada en `student_state.floor_level:82-84` (demostrado > observado >
estimado > declarado). Se registra como **coherencia resuelta por diseño**.

#### AG-2.5 — Dos scorers MCQ casi idénticos — (D) `[A]`

`academy.score_items:673` y `assessment_v2.score_answers:332` implementan la
misma agregación (`per_skill` con `correct`/`total`/`score` redondeado a 3,
`overall = correct/answered`). La diferencia es de **firma**: `score_items`
exige objetos con atributos; `score_answers` acepta `ObjectiveCheck` o `dict`.
No hay divergencia de resultado en las entradas válidas (a diferencia de
AG-2.2, aquí las dos fórmulas del `overall` **sí** coinciden). Es deuda de
mantenibilidad, no un defecto de cálculo.

#### AG-2.6 — Dos agregaciones incompatibles del `score` por destreza — (D) `[A]`

| Fuente | Regla del `score` | Consumidor |
|---|---|---|
| `services/academy.build_skill_profile:480` | **media de los `score` de los objetivos** (`sum(scores)/len(scores)`) | `readiness` y el perfil CEFR del nivel |
| `services/skill_state._entry:666-671` | **media de los `score` de las filas de evidencia**, con fallback a `len(successes)/attempts` | `domain/profile.py:173,221`, `domain/decision.py:141` |
| `services/learner_skill.observed_skill_state` | capacidad observada por dimensión | suelo de dificultad (`student_state`) |
| `services/evidence_graph.dimension_scores:159` | por dimensión del grafo | panel de grafo |

`build_skill_profile:441` **declara** que su fuente de verdad es
`academy_objective_mastery`. `skill_state` **declara** su propia puerta
espaciada (`skill_state.py:657-659`, `gate_for`). Es decir, la divergencia es
**por construcción y está declarada en cada módulo por separado**.

El hallazgo es que **el campo se llama igual (`score`) y ningún consumidor sabe
que está leyendo una cantidad distinta**, ni existe comprobación alguna de que
las dos visiones del mismo alumno sean coherentes entre sí. Es el hallazgo
central de AG-2: el «Student Model» tiene **dos definiciones de dominio por
destreza**, cada una correcta en su contrato, sin reconciliación.

---

### AG-3 · Modelos de retención y programación paralelos

Inventario de lo que decide «cuándo toca repasar»:

| Mecanismo | Fichero | Naturaleza | Horizonte |
|---|---|---|---|
| FSRS con estado (cartas `skill`/`lexicon`/`objective`) | `fsrs.schedule:224`, `due_queue:351` | modelo con estado, `due_at` | `MAX_INTERVAL_DAYS = 365` (`fsrs.py:46`) |
| Curva de olvido sin estado | `forgetting.retrieval_probability:44`, `review_due:53` | exponencial sobre `score`+fecha | booleano |
| Intervalo de repaso de destreza | `mastery.review_interval_days:100` | usa `forgetting.stability_days` | `MAX_REVIEW_INTERVAL_DAYS = 30` (`mastery.py:97`) |
| Recuperación demorada léxica | `lexicon.delayed_retrieval_decision:1215` | `max(1, hueco hasta el `due_at` de la carta)` | hereda de FSRS |
| Ventanas fijas de repaso de unidad | `unit_review.UNIT_REVIEW_WINDOWS_DAYS:33` = (7, 30, 90) | calendario fijo desde el ancla | 90 días |
| Ventana formal de retención | `assessment_v2.RETENTION_MIN_DAYS:59` = 7 | días entre evaluación formal y reassessment | 7 días |
| Retención retardada descriptiva de listening | `listening.delayed_retention:2118` | **solo describe**, no programa | buckets 0-2/2-7/7-30/30+ |

#### AG-3.1 — `next_review_days` contradice al scheduler del mismo ítem — (D, verificado) `[A][R]`

```python
# backend/services/lexicon.py:395-397
def next_review_days(row: dict) -> int:
    """Días hasta el próximo repaso del ítem (mismo scheduler que las destrezas)."""
    return mastery.review_interval_days(item_mastery(row), item_confidence(row))
```

Ese «siguiente repaso» está **acotado a 30 días** (`mastery.py:97,112`). El mismo
ítem, si tiene carta FSRS `lexicon`, se programa con `fsrs.schedule`, acotado a
**365 días**. Comprobado con el intérprete del proyecto:

```
[R] fila léxica fuerte (20 producciones en 20 días, 50 exposiciones en 30 días),
    ancla 2026-01-01, carta FSRS con vencimiento 2026-01-31, consulta 2026-03-02:
    lexicon.next_review_days(...)                        = 20
    lexicon.delayed_retrieval_decision(...).required_days = 30.0
```

Es decir: **el número que la app muestra como «próximo repaso» (20) es inferior
al intervalo que el propio scheduler exige para acreditar la recuperación
(30)**. No es un error de cálculo de ninguna de las dos —cada una es correcta en
su contrato— sino **dos respuestas distintas a la misma pregunta**, expuestas
ambas al alumno:

- `next_review_days` → `domain/vocabulary.py:288` y `:1638` →
  `schemas/vocabulary.py:198,375` → UI en
  `frontend/src/features/vocabulary/PersonalDictionary.tsx:323` y
  `DictionaryLookup.tsx:288`.
- El vencimiento FSRS → cola `GET /api/learning/review`
  (`fsrs.due_queue:351`, `domain/academy.py:2186`).

**Mitigación ya declarada:** `lexicon.py:32` llama a `next_review_days`
«estimación ligera» y `lexicon.py:1574-1577` declara que la programación
espaciada vive en la cola FSRS y **no** en el micro-drill (separación de V3.35).
Esa declaración cubre el *cálculo*; **no** cubre que la etiqueta de UI sea la
misma idea con dos números distintos.

#### AG-3.2 — Lo que sí está bien resuelto (verificado, no es hallazgo)

- **La separación drill / repaso espaciado** (`lexicon.py:1574-1577`) es real:
  el micro-drill ordena por `item_recall` y **no** inyecta la cola espaciada.
- **`delayed_retrieval_decision` respeta el suelo**
  (`max(RETENTION_MIN_INTERVAL_DAYS, from_fsrs)`, `lexicon.py:1239-1242`): un
  lapse no acredita recuperación demorada, y sin carta conserva el suelo de
  V3.23. La interacción con FSRS está declarada y es monotónica.
- **`listening.delayed_retention` no programa nada** (`listening.py:2118-2141`):
  es descriptivo y no compite con ningún scheduler.
- **`unit_review` es determinista y sin reloj en la semilla**
  (`unit_review.py:261`, `del now`) y **comparte el scheduler** en lugar de
  duplicarlo: importa `services.fsrs` (`unit_review.py:30`).
- **`forgetting` y `fsrs` no se solapan en el mismo ítem**: `forgetting` es la
  capa sin estado que usa el léxico y el perfil; `fsrs` solo actúa donde existe
  carta. La convivencia está declarada.

#### AG-3.3 — Colisión de nombres en los umbrales de retención — (C) `[A]`

`lexicon.RETENTION_MIN_INTERVAL_DAYS = 1` (`lexicon.py:99`) y
`assessment_v2.RETENTION_MIN_DAYS = 7` (`assessment_v2.py:59`) se leen como la
misma clase de umbral y no lo son (días naturales entre recuperaciones léxicas
vs días entre evaluación formal y reassessment). Ver §AG-1.5.

---

### AG-4 · Fragilidad estructural

#### AG-4.1 — Ciclos latentes resueltos con import diferido — (D, aceptado) `[A]`

| Sitio | Comentario |
|---|---|
| `backend/services/curriculum.py:601-602` | `# late import (anti-ciclo)` |
| `backend/repositories/evidence.py:134-135` | «la capa pura vive en `services` y no debe acoplarse en tiempo de import» (y `:243`, `:527`) |
| `backend/repositories/learning.py:23` | import dentro de función |
| `backend/repositories/vocabulary.py:305` | import dentro de función |
| `backend/services/curriculum_coverage.py:281-283` | import diferido |

**Los ciclos están declarados y justificados.** El coste real no es el ciclo
—está resuelto— sino que **oculta la arista a cualquier análisis estático** (un
`ruff`/`mypy`/grafo de imports no verá `curriculum → listening`). Es deuda
aceptada, no un defecto.

#### AG-4.2 — Estado de módulo mutable — (D, aceptado) `[A]`

| Estado | Sitio | Naturaleza |
|---|---|---|
| `_negative_until`, `_user_gen_times`, `_global_gen_times`, `_inflight_content` | `domain/vocabulary.py:1790-1792` | cupo y caché negativa **por proceso**, con helper de limpieza para tests (`_clear_generation_state:1795`) |
| `_PROVENANCE_RECORD_FAILURES` | `domain/review.py:57` | contador global |
| `_MATRIX_CACHE`, `_FRAMEWORK_CACHE`, `_LEVEL_CACHE` | `cefr_matrix.py:48`, `cefr_descriptors.py:93`, `quiz_routes.py:64` | cachés de contenido |
| `_levels_by_id` | `domain/academy.py:294` | caché de niveles |
| `QUESTION_BANK`, `DERIVED_BY_ID`, `DERIVED_*_POOL` | `listening.py:1010-1033` | banco construido al importar |
| `_client`, `_model` | `services/llm.py:12`, `services/stt.py:13` | singletons de cliente/modelo |

**Declarado y con helper de test** (el docstring `vocabulary.py:1797-1800`
explica por qué los tests deben limpiarlo). Implicación honesta: el cupo y la
caché negativa **se reinician con el proceso** y no son válidos para más de un
worker. Coherente con una app local de un proceso; incompatible con un
despliegue multi-worker. No es un defecto en la arquitectura actual.

#### AG-4.3 — Reloj no inyectado — (D, aceptado con matiz) `[A]`

Funciones puras con `now: str = ""` que **caen a `datetime.now`** si el llamador
no lo pasa: `fsrs.schedule:235`, `fsrs.explain:293`, `fsrs.is_due:338`,
`fsrs.due_queue:351`, `assessment_v2.retention_due:790`, y múltiples escritores
de `domain/academy.py`
(`:160, 532, 565, 697, 852, 903, 1083, 1547, 1969, 2186, 2204, 2248, 2423, 2504,
2929, 2954, 2994, 3055, 3096`).

**Matiz honesto:** el patrón `now or datetime.now()` **preserva la pureza cuando
se inyecta `now`**, y los tests del proyecto lo inyectan (p. ej.
`tests/test_decision_projection_v364.py:421`). El riesgo residual es el
contrario al habitual: una llamada de producción **que olvide** pasar `now` no
falla, simplemente usa el reloj real — y eso no se detecta.

#### AG-4.4 — Aleatoriedad: dos diseños **correctos** verificados

- **Micro-review de unidad** (`unit_review.py:265`):
  `random.Random(f"{user_id}|{unit.id}|{window_days}")` — semilla determinista y
  **deliberadamente sin reloj** (`unit_review.py:261`, `del now`) para que GET y
  POST muestreen igual. Correcto.
- **MCQ de reconocimiento léxico** (`domain/vocabulary.py:1239`): el nonce
  `secrets.token_urlsafe(8)` actúa de **semilla de barajado**, no de estado; el
  POST recomputa la misma permutación a partir del `question_id`
  (`vocabulary.py:1270-1276`). Barajado por intento sin guardar estado de
  servidor: correcto y bien documentado (`vocabulary.py:1230-1234`).

**Residuo real detectado (P3):** la reconstrucción del MCQ asume que el
diccionario **no cambia entre el GET y el POST**. `recognition_options_for` toma
los distractores de `dictionary_repo.list_entries()`
(`vocabulary.py:1236-1241`); si una entrada se añade o se borra entre ambas
llamadas, la permutación se recalcula sobre un conjunto distinto y el
`selected_index` puede puntuar contra otra opción. En una app local monousuario
es improbable, pero **no hay ninguna comprobación de que la pregunta siga siendo
la misma**.

#### AG-4.5 — Dirección de dependencia invertida — (D, trade-off declarado) `[A]`

```python
# backend/services/observed_difficulty.py:41-42
from services import difficulty, task_semantics
from services.learner_skill import OBSERVED_MIN_DAYS, OBSERVED_MIN_SAMPLES
from services.planner import LATENCY_CEILING_MS, SLOW_RECALL_MS
```

Una capa de **calibración/observación** importa dos constantes del **planner**
(una capa de decisión). `observed_difficulty.py:58-60` **declara** el porqué:
«Se reutilizan las constantes declaradas del planner (no se inventan)». Es
**SSOT aplicado correctamente** (reutilizar en vez de duplicar) y a la vez una
inversión de capas: `planner` importa `evidence`, `skill_state` importa ambos, y
`observed_difficulty` se cuela entre medias. Se registra como coste declarado,
no como defecto. Ningún ciclo actual lo rompe (los tests pasan), pero es el
punto donde aparecerá si el planner crece.

---

### AG-5 · Fallos silenciosos

#### AG-5.1 — El planner se traga toda excepción sin dejar rastro — (P1) `[A]`

```python
# backend/services/planner.py:775-785
    ...
    try:
        for reason in EVIDENCE_REASON_ORDER:
            skill = resolvers[reason]()
            if skill:
                return _task(skill, reason)
    except Exception:  # noqa: BLE001 — el planner nunca rompe la cola
        return {"skill": "", "activity": "", "reason": "", "support_level": ""}
    return {"skill": "", "activity": "", "reason": "", "support_level": ""}
```

```python
# backend/services/planner.py:824-829
    except Exception:  # noqa: BLE001 — el planner nunca rompe la cola
        return []
```

Dos hechos verificados:

1. El valor devuelto en el `except` es **idéntico** al de la salida legítima
   («no hay directriz» / «no hay candidatas»): `{"skill": "", ...}` y `[]`.
2. **`planner.py` no tiene logging en absoluto**:
   `rg -n "logger|import logging" backend/services/planner.py` → **sin
   coincidencias**.

Por tanto, un error real en `error_prone`, `skill_gaps`, `transfer_gap` o en
cualquiera de los resolutores **es indistinguible de un resultado correcto** y no
deja evidencia en ningún sitio. El diseño «el planner nunca rompe la cola» es
correcto como política de disponibilidad; lo que falta es que el fallo sea
**observable**. Contrasta con los escritores de evidencia, que sí lo hacen bien:

```python
# backend/domain/vocabulary.py:486-490
    except Exception:  # noqa: BLE001 — señal no bloqueante
        logger.warning(
            "No se pudo registrar retrieval user=%s word=%s",
            user_id, word, exc_info=True,
        )
```

(el mismo patrón en `vocabulary.py:879-885`). La diferencia entre ambos es
exactamente la que el proyecto exige en sus auditorías: **un `pass` sin
evidencia no es un `pass`**.

#### AG-5.2 — Degradaciones silenciosas declaradas (no son hallazgos nuevos)

| Sitio | Comportamiento | Valoración |
|---|---|---|
| `domain/learner_state.py:69-71` | error de BD al leer el perfil → `empty_learner_level_state()` | Declarado «preferencia no bloqueante». El valor de fallo **coincide** con «sin datos», pero el impacto está acotado (el drill no filtra por dificultad). Aceptado |
| `planner.select_task:781`, `task_candidates:826` | ver AG-5.1 | **Hallazgo** por falta de observabilidad |
| Escritores de evidencia de `domain/vocabulary.py:488,879` | log con `exc_info=True` | Correcto |

---

### AG-6 · Cobertura de test de los hubs del motor

**Esta sección corrige la sospecha de partida de la auditoría.** Los cuatro
puntos que se presumían sin cubrir **sí están cubiertos**:

| Sospecha | Realidad verificada |
|---|---|
| `services/skill_axis.py` sin test | **Cubierto**: `tests/test_skill_state_v362.py:33,187-253,316,410,548,565,638-639,764`; `tests/test_ped_coverage_v370.py:32,144-231`; `tests/test_observed_task_difficulty_v363.py:37,305-320,547-567`; `tests/test_decision_projection_v364.py:40,267`; `tests/test_ped_mastery_v370.py:23,52,126` |
| `services/cefr.py` sin test | **Cubierto**: `tests/test_band_thresholds_v372.py:98-106,117` cubre el corte; `test_ped_instruments_v370.py:129,142`; `test_profile.py:13`, `test_policy.py:2` |
| `domain/vocabulary.py` sin test dedicado | **Cubierto directamente por 10+ suites** que lo importan como `vocabulary_domain`: `test_learner_skill_v353.py:17`, `test_learner_skill_v354.py:25`, `test_longitudinal_evidence_v335.py:25`, `test_skill_segmentation_v338.py:26`, `test_task_semantics_v351.py:25`, `test_student_state_v352.py:32`, `test_learning_evidence_v336.py:28`, `test_expected_learning_value_v356.py:29`, `test_dictionary_*`, `test_task_difficulty_v355.py:27` |
| Integración `select_task_by_elv` × `decision_projection` probada indirectamente | **Cubierta de forma directa**: `tests/test_decision_projection_v364.py:232-331,360-421` ejercita `projection.project`; `tests/test_planner_argmax_v357.py:204-288`, `test_observed_difficulty_v365.py:369-389`, `test_decision_v366.py:228-232`, `test_adaptive_e2e_v369.py:786` ejercitan `select_task_by_elv` |

**Huecos reales que quedan (por ausencia, no por módulo):**

1. **Ningún test compara dos superficies del motor entre sí.** Todo lo hallado en
   AG-2.2, AG-2.6 y AG-3.1 existe porque **cada módulo se prueba contra su propio
   contrato** y nunca contra el del vecino. No es un hueco de cobertura por
   fichero: es la ausencia de una clase de test.
2. **Ningún test fija que los espejos de transferencia coincidan**
   (§AG-1.3): cada constante tiene su test de valor, ninguno compara las parejas.
3. **Ningún test cubre la mutación del diccionario entre GET y POST** del MCQ de
   reconocimiento (§AG-4.4).

---

## Hallazgos

### Matriz consolidada

| # | Eje | Hallazgo | Evidencia | Severidad | Naturaleza |
|---|---|---|---|---|---|
| AG-1.2 | SSOT | `PRONUNCIATION_PASS_THRESHOLD` declarado y **nunca usado**; el umbral vivo es otro | `pronunciation_routes.py:34`; `rg` sin usos | **P2** | declaración sin respaldo |
| AG-1.1 | SSOT | `MASTERY_MIN_*` duplicado en dos módulos que no se importan | `vocabulary.py:39-40`; `lexicon.py:71-72` | **P2** | regla duplicada |
| AG-1.4 | SSOT | Umbral de recuperación `0.7` duplicado + dos literales `0.7` en puertas | `forgetting.py:22`; `adaptive.py:129`; `academy.py:1983,1497` | **P2** | regla duplicada + literal mágico |
| AG-1.3 | SSOT | Mínimo de transferencia: 3 cantidades distintas con valor 2 en 6 definiciones, 2 de ellas contiguas en `planner.py` | `evidence.py:301,654`; `planner.py:167,171`; `decision_projection.py:125`; `transfer.py:177` | **P2** | espejos declarados sin candado cruzado |
| AG-1.5 | SSOT | Pares con valor idéntico y semántica distinta (incl. colisión `RETENTION_MIN_*`) | tabla §AG-1.5 | **P3** | riesgo de unificación errónea |
| AG-2.6 | Coherencia | Dos reglas incompatibles de `score` por destreza, sin reconciliación | `academy.py:480` vs `skill_state.py:666` | **P1** | Student Model con dos definiciones |
| AG-2.2 | Coherencia | Dos fórmulas de `overall` para nivel: por ítem vs por destreza (factor 2 verificado) | `academy.py:700` vs `:1246` | **P2** | concepto con dos definiciones |
| AG-2.3 | Coherencia | Tres `difficulty_from_vector`; solo una defensiva; divergen y lanzan distinto | `listening.py:278`; `speaking.py:109`; `transfer.py:269` | **P2** | latente (vectores bien formados) |
| AG-2.1 | Coherencia | Dos motores de prioridad sin árbitro; el segundo con pesos **no declarados** | `planner.py:50` vs `adaptive.py:806-807` | **P2** | deuda de diseño declarada a medias |
| AG-2.5 | Mantenibilidad | Dos scorers MCQ casi idénticos | `academy.py:673` vs `assessment_v2.py:332` | **P3** | duplicación sin divergencia |
| AG-3.1 | Coherencia | `next_review_days` (≤30 d) contradice el intervalo exigido por el scheduler (FSRS) del mismo ítem | `lexicon.py:397`; `mastery.py:97`; `fsrs.py:46` | **P2** | dos respuestas a la misma pregunta |
| AG-3.3 | SSOT | Colisión de nombres `RETENTION_MIN_INTERVAL_DAYS` (1 d) / `RETENTION_MIN_DAYS` (7 d) | `lexicon.py:99`; `assessment_v2.py:59` | **P3** | riesgo de lectura |
| AG-4.1 | Estructura | 5 imports diferidos anti-ciclo (declarados) | §AG-4.1 | **P3** | deuda aceptada; oculta aristas al análisis estático |
| AG-4.2 | Estructura | Estado de módulo por proceso (cupo, cachés, banco) | §AG-4.2 | **P3** | deuda aceptada; no multi-worker |
| AG-4.3 | Estructura | `now` opcional con caída a `datetime.now` | §AG-4.3 | **P3** | riesgo de olvido de inyección |
| AG-4.4 | Estructura | MCQ de reconocimiento asume diccionario inmutable entre GET y POST | `vocabulary.py:1239,1276` | **P3** | residuo de concurrencia |
| AG-4.5 | Estructura | `observed_difficulty` importa constantes de `planner` (capa invertida) | `observed_difficulty.py:42` | **P3** | trade-off declarado (SSOT > capas) |
| AG-5.1 | Observabilidad | El planner se traga toda excepción con el mismo valor que el caso legítimo y **sin logging** | `planner.py:781,826`; sin `logger` en el módulo | **P1** | fallo indistinguible del éxito |
| AG-6 | Cobertura | Huecos reales: ninguna prueba cruzada entre superficies; sin candado de espejos; sin mutación de diccionario | §AG-6 | **P3** | ausencia de una clase de test |

**Totales: 0 P0 · 2 P1 · 8 P2 · 10 P3.**

### Propiedades positivas verificadas (no tocar)

- **El corte de banda CEFR sigue siendo fuente única** (`cefr.py:62`) con los
  tres estimadores delegando y candado en
  `test_band_thresholds_v372.py:98-106`. AE-06 **cerrado y verificado**.
- **La separación micro-drill / repaso espaciado es real y está declarada**
  (`lexicon.py:1574-1577`): el drill no inyecta la cola espaciada.
- **La recuperación demorada respeta el suelo y es monotónica respecto a FSRS**
  (`lexicon.py:1239-1242`).
- **El micro-review de unidad es determinista y sin reloj en la semilla**
  (`unit_review.py:261,265`), y **reutiliza** el scheduler en vez de duplicarlo
  (`unit_review.py:30`).
- **El MCQ de reconocimiento es sin estado de servidor** y rota la posición de la
  correcta por intento (`vocabulary.py:1230-1234`).
- **Los escritores de evidencia registran el fallo con traza**
  (`vocabulary.py:486-490,879-885`).
- **Los espejos de constantes están declarados en el propio código**
  (`evidence.py:652`, `planner.py:166`, `decision_projection.py:122`), que es la
  razón por la que esta auditoría puede listarlos en vez de descubrirlos.

## Veredicto

**El motor es coherente en su lógica y divergente en su contabilidad.**

Ninguna de las dos P1 es una avería: son **dos definiciones de la misma
magnitud** y **un fallo que no deja rastro**. El motor calcula bien lo que cada
módulo se propone calcular; lo que no existe es un contrato que obligue a que
dos módulos que responden a la misma pregunta den la misma respuesta, ni un
registro que distinga «no hay nada que proponer» de «el planner falló».

- **Arquitectura del motor:** sólida. Corte de banda único y verificado, capas
  declaradas, separación drill/repaso real, schedulers que no se pisan donde
  importa.
- **Fuente única de verdad:** **parcial**. Los umbrales *grandes* están
  declarados y documentados (y los espejos se confiesan en el código); los
  *pequeños* están duplicados o literales (`AG-1.1`, `AG-1.4`), y hay una
  constante declarada que no gobierna nada (`AG-1.2`).
- **Coherencia entre superficies:** **no garantizada y no vigilada**
  (`AG-2.2`, `AG-2.6`, `AG-3.1`). Es el núcleo del hallazgo.
- **Observabilidad de la decisión:** **insuficiente en el planner**
  (`AG-5.1`); correcta en los escritores de evidencia.
- **Cobertura de test del motor:** **buena**, y la sospecha inicial era
  infundada (`AG-6`).

**Ninguna de estas conclusiones pide cambiar la pedagogía.** Todas piden
**declarar** una regla, **reutilizarla** en vez de reescribirla, o **hacer
observable** un fallo. No se ha encontrado ningún defecto de cálculo en la
dirección de banda, en el gate de maestría, en el scheduler ni en la
acreditación de evidencia.

## Honestidad: qué NO demuestra esta auditoría

1. **No demuestra que un alumno aprenda peor.** Mide coherencia interna del
   motor, no eficacia. Los dos P1 pueden ser inocuos en la práctica si las
   superficies nunca se comparan entre sí; lo que se demuestra es que **no hay
   nada que impida** que se contradigan.
2. **No calibra ningún umbral.** No se ha medido con alumnos si `0.8`, `0.7`,
   `3` o `2` son los valores correctos. Eso sigue aparcado (`AD:19-21`,
   `PARKED.md:8-24`).
3. **No audita el contenido ni los instrumentos.** Es el objeto de `AA`–`AE` y
   de `audit_dossier.py`; este dossier no los regenera ni los reinterpreta.
4. **No audita el texto del LLM en ejecución** ni la calidad acústica: quedan
   fuera por la misma razón declarada en `AF:147-168`.
5. **Las divergencias verificadas son de laboratorio.** Se han reproducido con
   entradas construidas (vectores con booleanos, respuestas desbalanceadas entre
   destrezas, cartas FSRS con vencimiento forzado). Que la divergencia **exista**
   está probado; que **ocurra en uso real** no se ha medido.
6. **No he leído línea a línea 43 módulos.** El método ha sido muestreo dirigido
   sobre los puntos de mayor riesgo declarados (fuente única, caminos paralelos,
   modelos de retención, fragilidad, fallos silenciosos). Un módulo no
   inspeccionado puede contener un patrón de los de arriba que no aparece aquí.
7. **No he ejecutado la suite completa.** Las cifras de test de la release
   (2882/721/142) son **declaradas** por V3.75.0 y no se han re-verificado en
   esta auditoría; solo se han ejecutado las funciones puras del §Regenerar.
8. **No hay P0.** No se ha encontrado ningún defecto que rompa la corrección del
   motor. Si se esperaba uno, esta auditoría no lo aporta, y decirlo es parte
   del resultado.

## Qué necesitaría un test para dejar de ser opinión

Se enuncia **sin implementarlo** (fuera de alcance de este dossier). Cada punto
es un candado con la forma que el proyecto ya usa (`test_identity_source`,
`test_path_limits_match_real_routes`, `test_docs_drift_*`):

1. **Candado de espejos de transferencia** (`AG-1.3`): comparar las tres
   cantidades declaradas entre módulos y exigir que los espejos coincidan, del
   modo en que `test_ped_*` fija un hecho medido.
2. **Candado de unicidad de umbral de recuperación** (`AG-1.4`): exigir que el
   umbral «toca repasar» tenga una sola definición, o que las dos se importen
   entre sí.
3. **Candado de constante viva** (`AG-1.2`): exigir que toda constante exportada
   que documente una regla del motor tenga al menos un consumidor distinto de su
   definición. Es el mismo principio que
   `test_path_limits_match_real_routes` aplica a `security.py`.
4. **Candado cruzado de `score` por destreza** (`AG-2.6`): comprobar sobre el
   mismo alumno y la misma evidencia que las vistas que exponen un `score` por
   destreza no se contradicen más allá de lo declarado.
5. **Candado de `overall`** (`AG-2.2`): un caso mínimo con respuestas
   desbalanceadas, fijando qué fórmula produce cada camino y por qué.
6. **Candado de equivalencia de `difficulty_from_vector`** (`AG-2.3`):
   parametrizar las tres implementaciones sobre el mismo conjunto de vectores
   (válidos e inválidos) y exigir el mismo resultado —o exigir una sola
   implementación.
7. **Candado de intervalo de repaso único** (`AG-3.1`): para un ítem con carta
   FSRS, exigir que el número mostrado como «próximo repaso» no sea inferior al
   intervalo que el scheduler exige para acreditarlo.
8. **Candado de observabilidad del planner** (`AG-5.1`): inyectar un resolutor
   que falle y exigir que el fallo sea distinguible del caso legítimo (log,
   contador o marca en la salida).

## Regenerar / Verificar

```powershell
cd backend

# --- AG-1: constantes duplicadas y literales ---
rg -n "MASTERY_MIN_PRODUCTIONS|MASTERY_MIN_DAYS" .
rg -n "PRONUNCIATION_PASS_THRESHOLD" ..            # solo la definición => constante muerta
rg -n "PASS_THRESHOLD" .\services\pronunciation.py .\services\listening.py
rg -n "TRANSFER_MIN_SUCCESSES|TRANSFER_MIN_SUCCESS_CONTEXTS|CONTEXT_TRANSFER_MIN|TRANSFER_MIN_CONTEXTS|CONTEXT_DIVERSITY_MIN" .
rg -n "RETENTION_MIN_INTERVAL_DAYS|RETENTION_MIN_DAYS" .
rg -n "STREAK_TARGET|MASTERY_STREAK|CONFIRMED_THRESHOLD|DEFAULT_THRESHOLD" .
rg -n "\.get\(session\[.kind.\], 0\.7\)" .    # default fuera de la tabla declarada

# --- AG-2: motores paralelos ---
rg -n "def priority_score|PRIORITY_WEIGHTS|NEXT_BEST_PRIORITY" .
rg -n "def difficulty_from_vector" .
rg -n "def score_items|def score_answers|def exam_result" .
rg -n "def build_skill_profile|def _entry\b" .
rg -n "select_task_by_elv\(|next_best_activity\(" . -g '!tests/**'

# --- AG-3: retención paralela ---
rg -n "MAX_REVIEW_INTERVAL_DAYS|MAX_INTERVAL_DAYS" .
rg -n "UNIT_REVIEW_WINDOWS_DAYS|RETENTION_BUCKETS" .
rg -n "next_review_days" ..          # incluye el consumo en frontend

# --- AG-4: fragilidad ---
rg -n "anti-ciclo|late import" .
rg -n "^_negative_until|^_user_gen_times|^_global_gen_times|_MATRIX_CACHE|_FRAMEWORK_CACHE" .
rg -n "random\.Random|secrets\.token_urlsafe" .
rg -n "from services\.planner import" .

# --- AG-5: fallos silenciosos ---
rg -n "except Exception" .\services\planner.py
rg -n "logger|import logging" .\services\planner.py   # sin coincidencias
rg -n "logger\.warning" .\domain\vocabulary.py        # contraste: sí trazabilidad

# --- AG-6: cobertura de los hubs ---
rg -n "skill_axis" .\tests\
rg -n "from services\.cefr import" .\tests\
rg -n "from domain import vocabulary" .\tests\
rg -n "projection\.project|select_task_by_elv" .\tests\
```

**Verificación empírica de las divergencias** (ejecutada en esta auditoría; el
resultado está en §AG-2.2, §AG-2.3 y §AG-3.1). Crear un fichero temporal
**fuera del repositorio** y ejecutarlo desde `backend/`:

```powershell
cd backend
$code = @'
import sys
sys.path.insert(0, ".")
from types import SimpleNamespace as NS
from services import listening, speaking, transfer
from services import academy, assessment_v2, mastery, fsrs, lexicon

v = {"a": True, "b": 4}
print("[AG-2.3]", listening.difficulty_from_vector(v),
      speaking.difficulty_from_vector(v), transfer.difficulty_from_vector(v))

It = lambda i, sk, c: NS(id=i, skill=sk, correct_index=c)
items = [It("i1", "grammar", 0), It("i2", "writing", 0),
         It("i3", "writing", 0), It("i4", "writing", 0)]
answers = {"i1": 0, "i2": 1, "i3": 1, "i4": 1}
exam = NS(items=items, skills=["grammar", "writing"], min_per_skill=0.5)
print("[AG-2.2] exam_result:",
      academy.exam_result(exam, answers)["overall"],
      "| score_answers:", assessment_v2.score_answers(items, answers)["overall"])

row = {"production_count": 20, "production_days": 20,
       "exposure_count": 50, "exposure_days": 30,
       "last_seen": "2026-01-01T00:00:00+00:00",
       "last_retrieval_at": "2026-01-01T00:00:00+00:00"}
d = lexicon.delayed_retrieval_decision(
    row, now="2026-03-02T00:00:00+00:00", due_at="2026-01-31T00:00:00+00:00")
print("[AG-3.1] next_review_days:", lexicon.next_review_days(row),
      "| required_days:", d["required_days"],
      "| caps:", mastery.MAX_REVIEW_INTERVAL_DAYS, fsrs.MAX_INTERVAL_DAYS)
'@
$tmp = Join-Path $env:TEMP "ag_crosscheck.py"
Set-Content -Path $tmp -Value $code -Encoding UTF8
.\.venv\Scripts\python.exe $tmp
```

Salida esperada (la obtenida en esta auditoría):

```
[AG-2.3] 2 2 4
[AG-2.2] exam_result: 0.5 | score_answers: 0.25
[AG-3.1] next_review_days: 20 | required_days: 30.0 | caps: 30 365.0
```

## Tests que respaldan

| Fichero | Protege | Relación con esta auditoría |
|---|---|---|
| `tests/test_band_thresholds_v372.py` | Corte de banda único y sub-bandas no emitidas | **Verifica que AE-06 sigue cerrado** (§AG-2.4) |
| `tests/test_planner_argmax_v357.py` | `select_task_by_elv` equivalente a `select_task` sin capacidad | Fija el contrato del Motor A (§AG-2.1) |
| `tests/test_decision_projection_v364.py` | Proyección por celda y su inyección en el planner | Cobertura del hub sospechado (§AG-6) |
| `tests/test_adaptive.py` | `session_plan`, `next_best_activity`, `adaptive.priority_score` | Fija el contrato del Motor B (§AG-2.1) |
| `tests/test_skill_state_v362.py` | Mapeo de `skill_axis` y puerta espaciada de `skill_state` | Cobertura de `skill_axis` (§AG-6) y regla de `score` (§AG-2.6) |
| `tests/test_lexicon.py` | `next_review_days` acotado y monótono | **No detecta** la divergencia con FSRS (§AG-3.1): prueba cada contrato por separado |
| `tests/test_mastery.py` | `review_interval_days` creciente con la fuerza | Igual: valida el modelo de 30 días en aislamiento |
| `tests/test_transfer_evidence_v347.py` | `evidence.TRANSFER_MIN_SUCCESSES == 2` | Fija **una** de las seis constantes (§AG-1.3) |
| `tests/test_transfer_v343.py` | `transfer.CONTEXT_DIVERSITY_MIN == 2` | Fija otra, sin compararlas entre sí (§AG-1.3) |
| `tests/test_ped_coverage_v370.py`, `test_ped_mastery_v370.py`, `test_observed_task_difficulty_v363.py` | Registros de modalidades/competencias de `skill_axis` | Cobertura del hub (§AG-6) |
| `tests/test_golden_assessment.py` | `PASS_THRESHOLDS` congelado | Fija la tabla declarada; **no** fija el default literal de `academy.py:1497` (§AG-1.6) |
| `tests/test_adaptive_e2e_v369.py` | Integración del planner con el estado del alumno | Cobertura de la integración (§AG-6) |

**Lectura de esta tabla:** la cobertura del motor es amplia y cada suite es
correcta en su contrato. El patrón que explica todos los hallazgos de AG-2 y
AG-3 es que **ninguna suite cruza dos módulos que responden a la misma
pregunta**. Esa es la deuda que este dossier deja declarada y medida.
