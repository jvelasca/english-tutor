# v3.67.0 — Task Identity 2.0 + Decision Lifecycle + Provenance Analytics

> Release **SIN migración destructiva** (migración ADITIVA e idempotente sobre
> `decision_records`), **SIN bump de `GENERATOR_VERSION`**, **SIN tocar el banco**
> y **SIN cambios de UI** que cierra los DOS P1 de la auditoría de V3.66: la
> **identidad de tarea** deja de ser el `target_id` y pasa a ser `task_signature`
> (la firma canónica de SEIS componentes), y el **Decision Provenance** deja de
> ser append-only escrito en el GET y pasa a ser un **UPSERT idempotente** con
> `decision_id` determinista y **ciclo de vida**
> `computed → served → started → completed/abandoned`, con round-trip del cliente.
> Añade además la **analítica del provenance** (lectura + calibración descriptiva).

## Contexto

V3.66 cerró el P1-01 de V3.65 a medias: la granularidad fina `P(éxito | alumno,
tarea)` que se inyectó al Planner 3.0 era en realidad por **ítem**
(`target_id`), no por **tarea**. El MISMO `target_id` con distinta actividad
(`recall` vs `write`), distinto apoyo (`cued` vs `independent`) o distinta carga
servida es una TAREA distinta, y V3.66 las colapsaba en una sola tasa. Ese error
de identidad es el P1-01 de la auditoría de V3.66.

Además, el Decision Provenance de V3.66 era **append-only y se escribía en el
GET**: cada GET→GET→GET de la misma decisión creaba una fila nueva con `uuid4`,
así que el registro no podía reconstruir un ciclo de vida ni una tasa de acierto
(P1-02).

V3.67 cierra ambos de forma aditiva, sin romper la pureza del planner ni la
degradación byte-idéntica de los caminos sin proyección.

## Cambios

### A · Task Identity 2.0 (`services/observed_difficulty.py`)

`task_signature_parts()` es la firma canónica y determinista de una tarea:

    (target_id, activity, support_level, served_difficulty, context, assessed_skill)

- `served_difficulty` se serializa con `difficulty.format_vector` (el MISMO
  formato canónico del ledger).
- Los componentes ausentes se normalizan a `""`: la clave es estable byte a byte
  y nunca lanza.
- `task_signature(row)` deriva la firma de una FILA del estado leyendo los hechos
  ya proyectados por `skill_state._lexicon_rows` (`facts.activity`,
  `facts.support_level`, `facts.served_load`, `facts.context_instance`/
  `facts.context_id`) y la skill evaluada vía
  `task_semantics.assessed_skill_for(activity)` — NO el `modality` canónico del
  estado, que habla otro vocabulario (`vocabulary`/`writing`/`speaking`). Así la
  firma del **ledger** y la del **candidato** usan el MISMO idioma y la búsqueda
  empírica por firma puede CASAR.
- `empirical_success_by_task(rows)` agrupa por FIRMA (Nivel `task_empirical` de la
  jerarquía) reutilizando la MISMA puerta espaciada de V3.54
  (`OBSERVED_MIN_SAMPLES`/`OBSERVED_MIN_DAYS`). Sin muestra espaciada la firma NO
  aparece; una fila sin identidad de tarea (firma vacía) no aporta clave.

### B · Estadística honesta (P2-06/P2-07, `services/observed_difficulty.py`)

`_empirical_entry()` sustituye la tasa única por un payload honesto:

- `p_success_observed` — nombre honesto de la tasa observada;
- `raw_rate` = `long_term_rate` — tasa global CRUDA del grupo;
- `recent_rate` — tasa de los últimos `RECENT_ATTEMPTS = 5` intentos,
  **descriptiva** (no es una tendencia, no hay suavizado);
- `p_success` — se CONSERVA como alias retrocompatible de V3.66 (se retirará
  cuando exista una capa calibrada que reclame ese nombre).

Sin ML ni suavizado: todas son tasas crudas. `empirical_success_by_target` pasa a
devolver el payload completo (Nivel A de la jerarquía).

### C · Jerarquía de resolución de CUATRO niveles (`services/planner.py`)

`expected_learning_value` y `select_task_by_elv` ganan `target_empirical_success`
y resuelven `p_success` con el orden declarado:

1. `task_empirical` — `P(éxito | alumno, TAREA)` (la firma completa; la
   observación más específica);
2. `target_empirical` — `P(éxito | alumno, TARGET)` (lo que V3.66 llamaba
   erróneamente "task");
3. `skill_empirical` — `P(éxito | alumno, SKILL)` (base rate de V3.65);
4. margen declarado de capacidad (V3.64).

`_task_empirical_for(by_activity, activity)` resuelve la tasa por TAREA por
ACTIVIDAD del drill y acepta un payload escalar retrocompatible. El payload añade
`p_success_source = "target_empirical"` y `target_p_success`. Sin estimación la
salida es EXACTAMENTE la de V3.64/V3.65.

### D · Decision Lifecycle (P1-02, `repositories/decision_records.py` + `db.py`)

- `decision_id` pasa de `uuid4` a **hash determinista**: `build_decision_id()`
  calcula sha256 de `user_id`, `target_id`, `task_signature`,
  `decision_start_fingerprint` y `policy_version`. La MISMA decisión produce el
  MISMO id.
- `record_decision()` pasa de `INSERT` a **UPSERT**
  (`ON CONFLICT(decision_id) DO UPDATE`), respaldado por el índice único
  `idx_decision_records_decision_id`: el ciclo GET→GET→GET ya no duplica filas y
  conserva `id`/`created_at` originales.
- Nuevas transiciones del ciclo de vida: `mark_served`, `mark_started` y
  `mark_completed(decision_id, outcome)` sobre los estados `computed`, `served`,
  `started`, `completed` y `abandoned`. Una transición sobre un id inexistente
  devuelve `False` y no actualiza nada.
- `DECISION_POLICY_VERSION = "v3.67.0"`.

### E · Migración aditiva e idempotente (`repositories/db.py`)

- **P3-09:** se elimina el alias confuso `evidence_fingerprint` (duplicaba
  `decision_start_fingerprint`), con guarda para SQLite < 3.35 que no soporta
  `DROP COLUMN` (la columna sobrante es inofensiva: ya no se lee ni se escribe).
- Se añaden 12 columnas con defaults vía `ALTER TABLE ... ADD COLUMN` guardado por
  `PRAGMA table_info`: `task_signature`, `context_id`, `context_instance`,
  `served_load_json`, `support_level`, `assessment_mode`, `decision_status`,
  `served_at`, `started_at`, `completed_at`, `outcome`, `provenance_status`.
- Las filas legacy quedan con los defaults (status `computed`, timestamps vacíos).

### F · Snapshot coherente (P2, `domain/decision.py`)

`_empirical_maps()` lee el ledger y deriva AMBOS mapas (por tarea y por ítem);
`_recompute()` los devuelve DENTRO del mismo lazo de sellado que el estado, de
modo que `state_fingerprint` y el mapa empírico describen el MISMO snapshot de
evidencia (la decisión es válida contra `state_fingerprint`). En el camino de
caché fresca los mapas se derivan del ledger actual mediante la misma función
(best-effort: sin mapa se degrada a la granularidad por skill). `project_state`
expone la clave aditiva `empirical_success_by_target` junto a
`empirical_success_by_task`, que ahora es por FIRMA y no por `target_id`.

### G · Seam del léxico (`services/lexicon.py`)

`_task_empirical_by_activity()` resuelve, para CADA actividad posible del drill,
la firma del candidato con sus parámetros conocidos en la cola (ítem, apoyo
declarado por actividad, carga declarada y modalidad evaluada); el contexto se
resuelve vacío porque se elige en el GET del peldaño. `_task_signature_for()`
produce la firma de la tarea FINAL servida (la MISMA que agrupa el ledger), de
modo que el provenance de la decisión y la evidencia empírica hablen el mismo
idioma. El ítem servido expone `task_signature`, `served_load` y
`assessment_mode`. Sin proyección degrada byte-idéntico a V3.65.

### H · Round-trip del ciclo de vida (`domain/review.py` + `routers/vocabulary.py`)

`get_review_queue` propaga el `decision_id` devuelto por el upsert a cada ítem
servido. Los GET de peldaño (`sentence-context`, `transfer-context`,
`recognition-question`, `recall-prompt`) aceptan `decision_id` y llaman
`mark_served`; los POST de intento (`sentence`, `write`, `transfer`,
`recognition`, `recall`) llaman `mark_completed(decision_id, outcome)` con el
veredicto del intento (`ok`/`ko`/`unclear`). Los esquemas de intento ganan el
campo opcional `decision_id`. Todo es best-effort: un fallo de escritura nunca
rompe la cola ni el drill.

### I · Analítica del provenance (P3-10/P3-11/P3-12)

Nuevo `GET /api/learning/decisions` (solo lectura) que responde tres preguntas:

- `decisions` — `list_decisions` con filtros por `status` y `target_id` y
  paginación (más reciente primero);
- `calibration` — `calibration_report`: sobre las filas `completed`, agrupa por
  banda de `p_success` (ancho 0.2) y devuelve `count`,
  `mean_predicted_p_success`, `observed_success_rate` y `error` por banda, más
  `calibration_error` medio (ponderado por banda);
- `provenance_health` — `review.provenance_health()`: contador local y monotónico
  de decisiones que NO se pudieron registrar (pérdida silenciosa por excepción
  best-effort). `0` es lo sano.

Ninguna de las tres lecturas rompe la respuesta: ante un fallo devuelven el
informe vacío / contador, nunca una excepción.

## Tests

Nuevo `backend/tests/test_decision_v367.py` (**12**, escritos antes del código):

- Determinismo y sensibilidad de la firma: la actividad, el apoyo y la carga
  servida distinguen tareas; los componentes ausentes se normalizan.
- La firma distingue DOS actividades del MISMO `target_id` (el cierre del P1-01).
- `empirical_success_by_task` reutiliza la puerta espaciada y no declara sin
  muestra.
- Tasas `raw`/`recent`/`long_term` y `p_success_observed` sobre una serie con
  fallos recientes.
- Jerarquía completa `task → target → skill → margin` y `_task_empirical_for`
  (incluida la degradación con clave ausente y el payload escalar).
- Idempotencia del UPSERT: misma identidad → mismo `decision_id` y UNA sola fila.
- Metadata de tarea persistida (firma, carga servida, apoyo, canal) y status
  inicial `computed`.
- Transiciones del ciclo de vida (`served` → `completed` con `outcome`) y la
  transición fallida sobre un id inexistente.
- Informe de calibración: bandas, error simétrico (`0.0`) y caso vacío
  (`completed_count = 0`, `calibration_error = None`).

Actualizados `test_decision_v366.py` (la granularidad por ítem pasa a
`target_empirical`/`empirical_success_by_target` y `record_decision` ya no es
append-only) y `test_decision_projection_v364.py` (nueva aridad de `_recompute`).

## Honestidad

La identidad de tarea es AHORA la firma completa de seis componentes: el P1-01 de
V3.66 queda cerrado (el mismo ítem con distinta actividad ya no comparte tasa), y
la resolución sigue siendo determinista y audible vía `p_success_source`. El P1-02
queda cerrado con un `decision_id` determinista, escritura idempotente y ciclo de
vida con resultado.

Límites declarados:

- El informe de calibración es **DESCRIPTIVO**: compara la `p_success` heurística
  del planner con la tasa de acierto observada. No hay ML, ni suavizado, ni
  corrección de la predicción.
- `recent_rate` es la tasa CRUDA de los últimos 5 intentos, no una tendencia ni
  una señal de olvido.
- `p_success` se mantiene como alias de `p_success_observed` por
  retrocompatibilidad, así que el nombre sigue sobrecargado hasta que exista una
  capa calibrada que lo reclame.
- El contexto de la firma se resuelve vacío en la cola (se elige en el GET del
  peldaño): la firma del candidato y la del ledger casan en los cinco componentes
  restantes.

## Fuera de alcance

Adaptive Instance Selection (elegir la INSTANCIA dentro de la tarea por pareja),
Sense Engine 2.0 y los P2 de calibración pedagógica.
