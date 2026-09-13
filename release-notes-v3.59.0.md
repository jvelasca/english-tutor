# v3.59.0 — Context Engine 3.0 (Context Bank Family/Instance)

> Release **SIN migración de BD, SIN bump de `GENERATOR_VERSION` y SIN cambios de
> UI** que cierra el candidato que V3.48 dejó diferido («Context Bank
> Family/Instance») y el hallazgo **P2-04** de la auditoría de V3.43: un banco
> finito de consignas **FIJAS** se **MEMORIZA**. Al agotarlo, el alumno vuelve a
> recibir la misma redacción y puede reciclar una respuesta aprendida en lugar de
> transferir la unidad.
> V3.59 separa **FAMILIA** de **INSTANCIA**: la familia (los 20 contextos, su
> `id` incluido) sigue siendo la identidad pedagógica y la **unidad de EVIDENCIA**
> —el `id` es el `context_id` del ledger—, así que el banco **no se fragmenta**;
> la instancia es una superficie **DECLARADA** de esa misma familia (otra
> redacción del mismo escenario) que se sirve por **ROTACIÓN de intentos**.
> Determinista, sin LLM en el camino de la evidencia (premisa 21).

## Contexto

El banco de transferencia es contenido **curado** (V3.40 → V3.48): 20 contextos
con nivel, carga, competencias y seis dimensiones de identidad, con los seis
originales **congelados** para no reescribir la evidencia ya registrada. El
`context_id` que se guarda en el ledger es el de la **familia** —de él dependen
`transfer_state`, sus umbrales, `context_distance`, `context_diversity` y
`_novelty_score`—, así que ampliar el banco «a lo bruto» habría movido la
evidencia y los umbrales.

El límite que quedaba era de **superficie**: cada familia tiene UNA consigna. Con
el pool agotado (`exhausted=True`), el motor **rota sobre el mismo banco** y
sirve otra vez la consigna idéntica. Ese es el escenario exacto que la auditoría
de V3.43 describía: el alumno puede memorizar la estructura en lugar de
transferir.

## Cambio

```text
FAMILIA  = identidad pedagógica + unidad de EVIDENCIA (context_id del ledger)
           topic / communicative_goal / discourse_type / social_relation /
           time_reference / interaction_type / register / cefr /
           difficulty_vector / skills / lexical_environment / syntactic_focus
         = NO cambia en V3.59
INSTANCIA = superficie declarada de la MISMA familia
           {instance: etiqueta, prompt: otra redacción del mismo escenario}
SUPERFICIE = [0] la consigna HISTÓRICA de la familia (byte a byte)
             [1..n-1] las `instances` declaradas
ROTACIÓN  = el intento N del ítem en esa familia sirve la superficie N % n
```

### A. FAMILIA vs INSTANCIA — `services/transfer.py`

Cada uno de los 20 contextos declara `instances`: una tupla de superficies
adicionales `{instance, prompt}`. Dos constantes declaran el contrato y lo hacen
verificable:

- `CONTEXT_INSTANCE_KEYS = ("instance", "prompt")`: **lista blanca**. Una
  instancia **solo** puede aportar su etiqueta y su consigna: `context_instances`
  reconstruye cada superficie con esas dos claves y **descarta cualquier otra**,
  así que una superficie no puede declarar
  `id`/`topic`/`communicative_goal`/`discourse_type`/`social_relation`/
  `time_reference`/`interaction_type`/`register`/`cefr`/`difficulty_vector`/
  `skills`/`lexical_environment`/`syntactic_focus` y **reinterpretar evidencia ya
  registrada**. El test fija además las claves legítimas de una familia
  (`FAMILY_KEYS`): la **única** clave nueva del banco es `instances`.
- `CONTEXT_INSTANCES_MIN = 2`: mínimo de superficies adicionales por familia, para
  que la rotación no sea inerte. El banco pasa de **20 consignas a 60
  superficies** sin tocar ninguna `id`.

### B. Núcleo puro

- `context_instances(context)`: acepta el dict del banco, un `id` (`"story"`) o
  un `context_id` (`"transfer:story"`) y devuelve
  `({"instance": "", "prompt": <consigna histórica>}, *declaradas)`. Normaliza
  (recorta), descarta superficies sin consigna o que no son dicts y **nunca
  lanza**.
- `context_instance_index(context, attempts)`: rotación
  `attempts % nº_superficies`, con `_count` **tolerante** (el bucket
  `{"attempts": n}` del resumen de evidencia, un entero, su forma textual; `bool`,
  negativos y `None` valen 0) y **0 sin intentos** → superficie histórica.
  Una familia con una sola superficie devuelve 0 siempre (rotación inerte).
- `_attempts_for(attempts_by_context, context_id)`: acepta el mapa `contexts` del
  resumen de evidencia, un mapa de enteros o nada, y prueba el `context_id` del
  ledger y el `id` desnudo.

### C. La elección NO cambia

La superficie **no participa** en `_within_level`, `_filter_skill`,
`select_by_difficulty`, `_novelty_score` ni `_stable_index`. La familia servida
es función de **la misma evidencia** que en V3.58: hay un test que recorre una
batería de entradas con y sin `attempts_by_context` y compara el payload clave
por clave **salvo** `prompt`/`context_instance`/`instance_index`.

El único cambio de comportamiento es el **texto de la consigna** cuando el ítem
ya tiene intentos en esa familia. Sin intentos, la consigna es la de V3.58,
byte a byte.

### D. Contrato aditivo

`context_for` gana el kwarg **opcional** `attempts_by_context` y tres campos en
**todos** los retornos (incluido el temprano de banco vacío):

- `context_instance`: etiqueta de la superficie servida (`""` = la histórica).
- `instance_index`: `0..instance_count-1`.
- `instance_count`: nº de superficies de la familia.

Las **25 claves** del payload de V3.58 quedan intactas y **fijadas por test**
(28 en total). `TransferContextOut` (`schemas/vocabulary.py`) los declara con
espejo opcional en `frontend/src/types/api.ts`. **Sin cambio de UI.**

### E. Cableado

Los **dos** caminos del drill (`domain/vocabulary.py`: el GET de la consigna y la
derivación del `context_id` al registrar sin contexto) pasan
`attempts_by_context=summary.get("contexts")`, el mismo mapa del que salen los
`used_context_ids`. Así la superficie servida en el GET y la registrada en el
ledger no pueden divergir, y el GET↔POST mantiene su paridad.

### F. Sin migración y sin regenerar contenido

Las superficies son **contenido declarado en el banco** (como los 20 contextos
de V3.48), no contenido generado: no hay columnas nuevas, no se sube
`GENERATOR_VERSION` y no se reinterpreta ninguna caché. La unidad de evidencia
(el `context_id` = `transfer:<id>`) es la de siempre.

## NO cambia

- `transfer_state` ni sus umbrales; `context_signals`; `context_diversity` ni
  `CONTEXT_DIVERSITY_MIN`; `context_distance`; `_novelty_score`; `_stable_index`.
- La **identidad** de las 20 familias: los seis contextos congelados conservan
  sus valores core y su consigna como superficie 0.
- `CEFR_CAPACITY`, el Difficulty Engine (`services/difficulty`) y el scoring
  (`score_transfer_attempt`), FSRS, el planner y el Sense Engine de V3.58.
- El contrato de V3.58: nada se quita ni se renombra (solo se añaden 3 claves).

## Tests

Nuevo `backend/tests/test_context_engine_v359.py` (**16**):

- **Banco:** mínimo de superficies por familia (`CONTEXT_INSTANCES_MIN`),
  superficie 0 **byte a byte** la histórica (incluidos los seis congelados),
  lista blanca de identidad (la **única** clave nueva del banco es `instances`),
  consignas limpias (sin llaves ni plantillas) y distintas.
- **Núcleo puro:** `context_instances` con ids/`context_id`/basura/normalización;
  rotación `N % n` con estabilidad; degradación a 0 sin evidencia o con valores
  no reconocibles; familia de una sola superficie.
- **No-regresión de la decisión:** la familia servida es idéntica con y sin
  `attempts_by_context` (payload clave por clave salvo las 3 volátiles).
- **Contrato:** las 28 claves exactas del payload (normal y banco vacío) y la
  coherencia `instance_index ↔ prompt ↔ context_instance`.
- **Invariantes del banco:** 20 familias, distribución CEFR, distancia mínima,
  `context_distance("transfer:story", "transfer:work") == 5`, variedad.
- **End-to-end HTTP:** la consigna servida expone la superficie, y con el **pool
  agotado** una segunda estancia en la **misma** familia sirve **otra** superficie
  (el objetivo anti-memorización), comprobado sobre la evidencia real del ledger.

## Verificación

```text
ruff check .                                  All checks passed
pytest tests/ -q                              2312 passed (142,5 s)
pytest launcher/tests -q                      75 passed
npx tsc --noEmit                              OK
npm test                                      76 ficheros / 651 tests
npm run build                                 OK
python scripts/check_release_consistency.py   3.59.0
python scripts/check_beta_v3.py               OK
python backend/scripts/content_validation.py  OK
```

## Fuera de alcance (V3.60+)

- El contrato/prompt de generación de sentidos y su bump de `GENERATOR_VERSION`.
- Ponderar la adecuación semántica dentro de `transfer_confidence` (los pesos
  declarados de V3.49 no se tocan).
- Cualquier uso del LLM en el camino de la evidencia (premisa 21).

## Siguiente paso

V3.60 — el contrato/prompt de generación de sentidos y la ponderación de la
adecuación en `transfer_confidence`. La auditoría externa de esta release se
prepara en `agentes/auditoria-externa-v359.md` (punto de entrada desde GitHub) y
su informe se espera en `docs/audit/R-AUDITORIA-TOTAL-V359.md`.
