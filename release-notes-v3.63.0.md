# v3.63.0 — Observed Task Difficulty 2.0 y honestidad del Student Skill State

> Release **SIN migración destructiva** (una columna aditiva idempotente más en
> `learning_profile`), **SIN bump de `GENERATOR_VERSION`**, **SIN tocar el banco**
> y **SIN cambios de UI** que cierra la deuda de **honestidad** que V3.62 dejó
> declarada por escrito, más los hallazgos **P1-02** y
> **P2-11/P2-12/P2-13/P2-14/P2-18/P2-19/P2-20** de la auditoría profunda `U` de
> V3.62.
>
> **La invariante central de V3.62 se mantiene:** la **decisión de tareas** queda
> **byte-idéntica** (ELV, planner, `difficulty` y `transfer.context_for`) y el
> guard estructural (`backend/tests/test_skill_state_v362.py`, **sin tocarse**)
> sigue verde. V3.63 hace el estado más **honesto**, no más **decisivo**: el
> recableado (**P1-01**) es **V3.64** con **Decision Projection + Planner 3.0**,
> comprometido y fechado en `docs/RELEVO.md` y en el briefing
> `agentes/v363-observed-task-difficulty-2.md`.

## Contexto

La auditoría `U` de V3.62 dio **9,5 / 10 APROBADA** y reconoció lo importante: V3.62
cierra el problema arquitectónico (ya no hay dos modelos del alumno aislados) y
evita tres errores graves (no convierte dificultad en competencia, no inventa
competencias y no mezcla modalidades). Pero dejó escrito un diagnóstico incómodo y
**correcto**: el estado nuevo **todavía no gobierna ninguna decisión**, y varias de
sus piezas eran honestas solo a medias.

V3.63 ataca exactamente eso, sin tocar la decisión:

- **P1-02 — el canal no se mira.** `spontaneous_use → interaction` es correcto
  **hoy** (su único emisor es `chat`, que es TEXTO), pero la modalidad se resolvía
  con un mapa duro `skill → modalidad` que no podía expresar el día que exista
  conversación ORAL real.
- **P2-13 — muestras ≠ ocasiones.** Una evaluación que se expande a N competencias
  contaba como N mediciones independientes: el estado podía acreditar de más.
- **P2-20 — la dificultad no era empírica.** Las tres dificultades de V3.55
  (`declared`/`served`/`observed_task_difficulty`) son **hechos de la tarea**;
  ninguna mira el **RESULTADO**.
- **P2-19 — una sola confianza para dos preguntas.** `confidence` es estadística
  (éxitos / intentos); *cuánto cubre la medición de lo que dice medir* es otra cosa
  y no se declaraba.
- **P2-11/P2-12 — vocabulario declarado que no se usaba.** La ruta de pronunciación
  **sí** puntúa un criterio (`item_id`) y el motor de listening **sí** declara capas
  (`SKILL_LAYER`), pero el estado no lo reflejaba.
- **P2-14 — una regla general para todas las parejas.** El estado
  `functional`/`demonstrated` sale de un gate único que no tiene exactamente la
  misma semántica en toda pareja (modalidad, competencia).
- **P2-18 — la caché no sabía si estaba vieja.** El estado se cacheaba en cada
  refresco del perfil y **nada** podía decir si seguía describiendo las fuentes.

## Cambio

### A · Identidad de evidencia y OCASIONES (P2-13)

- La fila canónica gana `evidence_id`, `activity_id`, `assessment_id` (vacíos si la
  fuente no los declara) y `occasion_key(row)`: la clave se compone de identidad
  **ya declarada**, sin inventar datos.
- Cada adaptador rellena lo que **ya existe**: `learning_evidence.id`/`activity_id`,
  `academy_evidence.id`/`activity_id`, `listening_attempts.id`/`question_id`,
  `pronunciation_attempts.id`.
- La entrada expone `observations` (filas) y `occasions` (mediciones
  independientes). La expansión de una evaluación a N competencias fija que las N
  comparten **UNA** ocasión, y el dedup **solo puede acreditar menos**: sin
  identidad declarada la degradación es **EXACTA** a V3.62 (`occasions == samples`).

### B · Canal OBSERVADO del evento (P1-02)

- `services/skill_axis.py` declara `MODALITIES_BY_ASSESSED_CHANNEL`, **derivado**
  de `LEXICAL_MODALITY` × `ASSESSMENT_MODE_MODALITY` (no se inventa vocabulario) y
  con dos entradas explícitas y probadas:
  `("spontaneous_use", "written") → interaction` (el `chat`/transfer de hoy) y
  `("spontaneous_use", "spoken") → speaking` (el canal que V3.62 no podía
  expresar).
- `_lexicon_rows` resuelve el canal desde la actividad **declarada** en el evento
  (`task_semantics.assessment_mode_for` sobre `activity_from_activity_id`) y **solo**
  cae al mapa por skill cuando la fila no declara canal: un evento oral alimenta el
  canal evaluado (`speaking`) por **expansión declarada**, nunca por
  reinterpretación. Sin canal, la lectura es **exactamente** la de V3.62.

### C · Observed Task Difficulty 2.0 empírica (P2-20, núcleo)

Nuevo módulo **puro** `backend/services/observed_difficulty.py` (sin I/O, sin reloj,
sin `hash()`/`random()`, nunca lanza) que lee las filas canónicas:

- `served_ceiling(rows)` — techo **SERVIDO** por dimensión (lo que se pidió).
- `credited_ceiling(rows)` — techo **ACREDITADO** (la misma lectura que alimenta el
  estado), y `scaffolding_gap(rows)`: su distancia al servido, es decir la
  **dependencia de andamiaje**.
- `experienced_load(row)` — carga servida modulada por coste **OBSERVADO** y ya
  persistido (latencia, `error_type`, repeticiones, transcripción y audio
  ralentizado) con tablas **DECLARADAS y monótonas** (`LATENCY_STEP` reutiliza
  `planner.SLOW_RECALL_MS`/`LATENCY_CEILING_MS`: no hay umbrales nuevos) y recorte
  al rango 1..5. Un coste **desconocido no modula**: no se imputa nada.
- `observed_task_difficulty_2(rows)` — `{served_ceiling, credited_ceiling,
  experienced_load, success_rate, samples, days}` aplicando la **MISMA puerta
  espaciada** de V3.54 (`learner_skill.OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`):
  sin 2 éxitos en 2 días naturales **no se declara ninguna medida**.

### D · Confianza de EVALUACIÓN separada de la estadística (P2-19)

- `assessment_confidence(row)` → banda declarada (`low`/`medium`/`high`) +
  **motivos**, derivada SOLO de hechos ya persistidos: canal observado,
  `support_level` (`copied`/`guided` → banda mínima; `cued` → un escalón),
  transcripción visible, audio ralentizado, repeticiones y una instancia de
  transferencia **no declarada**. Al agregar varias filas se toma la banda
  **mínima** y se unen los motivos.
- `confidence` sigue siendo la **estadística** (éxitos / intentos) y **no cambia de
  fórmula**: son dos preguntas distintas y ahora se llaman distinto.

### E · Pronunciación con el criterio DECLARADO (P2-11)

- `_academy_rows` usa `item_id` como competencia cuando la ruta **ya declara** un
  criterio de rúbrica (`services/pronunciation` escribe ahí el criterio que
  puntúa), sin expandir por las subdestrezas del objetivo y **sin inventar** una
  rúbrica que no existe.
- La **práctica libre** (`pronunciation_attempts`) mantiene la competencia `""` con
  el motivo escrito (`PRONUNCIATION_PRACTICE_REASON`): su tabla no declara criterio.

### F · Capas DECLARADAS de listening (P2-12)

- `COMPETENCE_LAYERS_BY_MODALITY` **reutiliza** el vocabulario que ya usa el motor
  (`services.listening.LISTENING_LAYERS` y `SKILL_LAYER`) **sin añadir una sola
  cadena**: 16 de las 18 competencias de listening se agrupan en
  `recognition`/`comprehension`/`inference`.
- `dictation`/`shadowing` quedan **fuera del eje con motivo escrito**
  (`UNLAYERED_COMPETENCE_REASONS`): son tareas de **PRODUCCIÓN**, no de
  comprensión receptiva, y reportarlas por capa mentiría sobre el proceso.
- `skill_state_summary` gana `layers` (derivado): distingue la competencia
  OPERACIONAL de la curricular **sin** reescribir la unión de competencias de V3.62.

### G · Seam de política del gate (P2-14)

- `services/competence.py` declara `CompetenceGate` (estructura **congelada**) y
  `gate_for(modality, competence, source)`, que devuelve **siempre** la puerta por
  defecto de V3.54/V3.62. `COMPETENCE_GATE_POLICIES` está **vacía** y un test lo
  fija: parametrizar la puerta por pareja pasa a ser una **decisión explícita** (que
  rompe el test) y no un descuido.
- **Cero umbrales nuevos** y estado **byte-idéntico**.

### H · Frescura del estado cacheado (P2-18)

- `repositories.evidence.evidence_fingerprint(user_id)` sella las **cuatro**
  fuentes (una consulta con `COUNT(*)`/`MAX(id)` por tabla; las tablas son
  append-only, así que la huella solo cambia cuando entra evidencia).
- Columna aditiva idempotente `learning_profile.skill_state_source TEXT NOT NULL
  DEFAULT ''` por el patrón de V3.52/V3.54/V3.62; `set_skill_state(user_id,
  skill_state, source="")` (firma extendida con default) sella la caché al
  escribirla y `skill_state_is_fresh(user_id)` compara.
- **Invariante: una caché vieja NUNCA se sirve como fresca.** Sin caché, caché
  vacía, caché **legacy sin sello** o sello desfasado → `False`. `GET /api/profile`
  sigue recomputando como hoy (ningún payload cambia); el «recomputar una vez si
  está vieja» del camino de decisión es **V3.64**.

### Contrato aditivo

`schemas/profile.py` y `frontend/src/types/api.ts` documentan las claves nuevas: la
entrada del estado gana `observations`, `occasions`, `assessment_confidence` y
`observed_task_difficulty_2`; el resumen gana `layers`. **Todas** las claves de
V3.62 (`state`, `samples`, `days`, `score`, `confidence`, `dimensions`, `sources`)
siguen ahí **con el mismo significado**. Ningún cambio visual ni de i18n.

## Tests

Nuevo `backend/tests/test_observed_task_difficulty_v363.py` (**26**), escrito
**antes** del código:

- **Identidad y ocasiones** — la identidad vacía cuando la fuente no la declara;
  identidad estable desde el ledger; una evaluación expandida a N competencias es
  **una** ocasión; el dedup **nunca** acredita más que V3.62 (`occasions <=
  samples`, y sin identidad `occasions == samples`).
- **Canal** — `spontaneous_use` escrito sigue en `interaction`; la misma skill con
  canal oral aterriza en `speaking`; el canal DECLARADO manda sobre el fallback por
  skill; un canal desconocido degrada **exactamente** a V3.62.
- **Empírico** — el andamiaje es `served_ceiling − credited_ceiling`; la carga
  experimentada es monótona, acotada al rango declarado e **ignora los hechos
  desconocidos**; sin muestra espaciada no se declara nada; la capa es determinista
  y el módulo **no lee reloj** (test de fuente: sin `import time`/`datetime`/
  `random`, sin `hash()`).
- **Confianza de evaluación** — es otra cosa que la `confidence` estadística; el TTS
  lento y la transcripción la bajan; los hechos desconocidos dan la banda mínima
  con su motivo.
- **Pronunciación** — el criterio declarado se convierte en la competencia; la ruta
  de práctica conserva `""` **con motivo escrito**.
- **Listening** — el eje de capas reutiliza `SKILL_LAYER` sin vocabulario nuevo; las
  subdestrezas de producción están fuera **con motivo**; el resumen expone las capas.
- **Gate** — solo hay política por defecto; el gate es byte-idéntico a V3.62.
- **Frescura** — la huella cambia cuando crece **cualquiera** de las cuatro fuentes;
  una caché vieja nunca se reporta fresca (y una legacy sin sello, tampoco); la
  migración es idempotente y las filas legacy quedan con `''`.
- **No-regresión (clave)** — `test_skill_state_v362.py` sigue **PASANDO SIN
  TOCARSE**, incluido el guard estructural de no-recableado, más un **e2e HTTP** de
  `/api/profile` que fija que el contrato es aditivo (todas las claves de V3.62
  presentes y las nuevas también).

## Verificación

```
backend:  ruff check .                        → All checks passed
backend:  pytest -q                           → 2430 passed
launcher: pytest launcher/tests -q            → 75 passed
frontend: npx tsc --noEmit                    → OK
frontend: npm run test                        → 76 ficheros / 651 passed
frontend: npm run build                       → OK
scripts:  python scripts/check_release_consistency.py   → OK: Release consistency (3.63.0)
scripts:  python scripts/check_beta_v3.py     → OK: Beta V3.0 gate
backend:  python backend/scripts/content_validation.py  → OK=True quality=True
backend:  python -m scripts.transfer_validation         → OK=True (esta release NO toca el banco)
```

## Honestidad: qué NO cierra V3.63

- **El estado nuevo sigue SIN gobernar la tarea.** ELV, planner, `difficulty` y
  `transfer.context_for` quedan **byte-idénticos** y el guard estructural permanece
  verde: **P1-01 sigue abierto** y comprometido a **V3.64** (Decision Projection +
  Planner 3.0, calculada desde las **MISMAS filas canónicas** que el estado, nunca
  desde la caché).
- **La dificultad empírica es una MEDIDA** con tablas declaradas de comparación,
  nunca un parámetro ajustado por datos; sin muestra espaciada no se declara nada y
  un coste desconocido no modula.
- **`syntax` sigue sin ser `grammar`**; `dimensions` sigue siendo carga 1..5 y
  `state` sigue saliendo del gate.
- **No se inventa rúbrica de pronunciación** ni competencia donde la fuente no la
  declara.
- La **frescura** se declara y se prueba, pero **nadie la consume todavía** en el
  camino de decisión (es exactamente la pieza que V3.64 necesita para recomputar una
  sola vez cuando la caché esté vieja).
