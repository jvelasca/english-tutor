# Briefing de subagente — V3.60 (Context Engine 4.0: Instance Specification → Parameterized Instance)

> **Estado:** incremento V3.60 **EJECUTADO** (2026-09-14, release **v3.60.0**),
> escrito sobre el árbol de `v3.59.0` (commit `e721fce`). Cierra los cuatro
> hallazgos de la auditoría externa **R** de V3.59: **P1-1** «3 superficies
> deterministas siguen siendo memorizables», **P1-2** «la instancia puede cambiar
> la dificultad real sin poder declararlo», **P2-6** «Context Engine todavía
> manual/finito» y **P2-7** «la instancia no genera dificultad». V3.60 sustituye
> las 60 consignas escritas a mano por un **ESPACIO de instancias PARAMETRIZADO**
> por familia (**FAMILIA → ESPECIFICACIÓN → INSTANCIA**) **sin tocar la identidad
> de evidencia** (`context_id` sigue siendo la familia) y **sin migración de BD**.
> Resultado verificado: `pytest` **2335 passed**, `ruff` limpio, launcher
> **75 passed**, `tsc` OK, `vitest` **651**, build OK y `check_release_consistency`
> **3.60.0**; ver `release-notes-v3.60.0.md`.
> **Histórico.**
> Antes de reutilizar este briefing, **verifica el estado real del árbol**
> (premisa 8): los nombres y las líneas de abajo se citan del árbol de `v3.59.0`
> y pueden haber cambiado.

## Rol

Agente de implementación del incremento V3.60 sobre el repo `english-tutor`, en la
rama `main`, con el estándar del proyecto: determinista, sin LLM en el camino de la
evidencia (premisa 21), cambios **aditivos**, cero regresión de la evidencia ya
registrada y **tests-first**.

## Objetivo

Que el banco de contextos de transferencia **no se agote ni se memorice** y que la
**dificultad de la superficie servida sea explícita**. V3.59 dejó dos límites
declarados:

1. **El banco seguía siendo finito y escrito a mano** (20 familias × 3
   redacciones): la cuarta estancia en una familia repite redacción.
2. **La superficie no podía declarar su carga** (`CONTEXT_INSTANCE_KEYS` era
   `("instance", "prompt")`): una redacción que exige más discurso no podía decirlo
   y el ledger persistía siempre el vector de la **familia**.

La solución **no** es generar texto con un LLM (rompería la premisa 21), sino
**parametrizar la combinación de contenido declarado**: cada familia declara un
`template` con slots y de él se derivan superficies deterministas de la MISMA
identidad.

## Contexto del proyecto

- **Qué es una familia aquí:** uno de los 20 contextos de `TRANSFER_CONTEXTS`
  (`services/transfer.py`), con `id` (=`context_id` del ledger), seis dimensiones
  core, `register`, `cefr`, `difficulty_vector`, `skills`, `lexical_environment`,
  `syntactic_focus` y `prompt`. Los seis primeros contextos están **congelados**.
- **Qué depende de la familia (y NO puede moverse):** `transfer_state` y sus
  umbrales (`services/evidence.py`), `context_distance`, `context_diversity`,
  `CONTEXT_DIVERSITY_MIN`, `_novelty_score` y el ajuste de dificultad
  (`services/difficulty.py`).
- **Qué llega al drill:** `domain/vocabulary.py` → `transfer.context_for` con los
  `used_context_ids`/`success_context_ids` y el mapa `summary["contexts"]`
  (`{context_id: {"attempts": n, "successes": m}}`), el `level` del ítem, la
  `skill` limitante, el suelo del alumno y su capacidad observada.
- **Qué persiste el ledger:** `_record_transfer_evidence` escribe la dificultad de
  la tarea servida (`served_difficulty` + proyección legacy `observed_difficulty`),
  con las columnas aditivas de V3.55.

## Estado de partida verificado (árbol `v3.59.0`)

- `services/transfer.py`: `TRANSFER_CONTEXTS` (20 familias, 60 superficies),
  `CONTEXT_INSTANCE_KEYS = ("instance", "prompt")`, `CONTEXT_INSTANCES_MIN = 2`,
  `context_instances`, `context_instance_index`, `_count`, `_attempts_for`,
  `context_for` (con `attempts_by_context` y 3 claves aditivas).
- `services/difficulty.py`: `normalize_vector`, `DIFFICULTY_DIMENSIONS`,
  `_MIN_LOAD`/`_MAX_LOAD`.
- `schemas/vocabulary.py`: `TransferContextOut` (28 campos en V3.59).
- `domain/vocabulary.py`: `_record_transfer_evidence` y los dos llamadores de
  `context_for`.
- **Tests que blindan el banco:** `tests/test_context_bank_v348.py`,
  `tests/test_context_engine_v359.py` (16).

## Decisiones de alcance (CERRADAS)

1. **Family/Instance sigue intocable.** `context_id` sigue siendo la FAMILIA y la
   unidad de EVIDENCIA: ninguna clave nueva entra en `CONTEXT_DIMENSIONS`,
   `context_distance`, `context_diversity`, `_novelty_score`, `transfer_state` ni
   sus umbrales. La superficie **no participa** en la selección.
2. **Contenido DECLARADO, combinación parametrizada.** El texto de las consignas
   sale de una plantilla declarada y valores declarados: **sin LLM, sin
   aleatoriedad con estado** (premisa 21). La expansión recorre el producto
   cartesiano en orden declarado y la rotación es `attempts % len(espacio)`.
3. **Lista blanca ampliada solo con metadatos NO identitarios:**
   `scenario`/`goal`/`register`/`difficulty_delta`/`skill_delta`. La identidad
   (`id`, 6 dimensiones core, `cefr`, `difficulty_vector`, `skills`,
   `lexical_environment`, `syntactic_focus`) sigue **prohibida** en una instancia.
4. **La familia declara carga ABSOLUTA; la superficie solo el MATIZ.** El delta es
   simétrico y corto (**±2**) a propósito: describe matices de la MISMA familia, no
   otro nivel CEFR. El resultado se recorta al envelope canónico 1..5.
5. **Degradación EXACTA.** Sin intentos la superficie es la 0 (consigna histórica,
   byte a byte) y el delta efectivo es `{}`: payload y dificultad persistida son
   los de V3.59. `space[:3]` reproduce byte a byte las tres superficies de V3.59.
6. **SIN migración, SIN bump de `GENERATOR_VERSION` y SIN cambios de UI.** No hay
   columnas nuevas: la carga efectiva se persiste en las columnas de V3.55.
7. **Contrato aditivo:** 8 claves nuevas; las 28 de V3.59 intactas y fijadas por
   test.

## Plan de implementación (tests-first)

1. `tests/test_context_engine_v360.py`: frontera de identidad, mínimo del espacio
   por familia y total, preservación de V3.59, expansión determinista y cap,
   especificación (incluida la inservible), **equivalencia pedagógica**, dificultad
   efectiva y `served_difficulty`, rotación, robustez de `details`/`metadata`,
   contrato aditivo y end-to-end HTTP de la superficie generada con el vector
   efectivo persistido.
2. `services/difficulty.py`: `_DELTA_MIN`/`_DELTA_MAX`, `_as_delta`,
   `normalize_delta` y `apply_delta` (puras, con test de paridad
   `apply_delta(v, {}) == normalize_vector(v)`).
3. `services/transfer.py`: lista blanca ampliada, `CONTEXT_INSTANCE_SPACE_MIN`/`MAX`,
   `_slug`, `_skill_delta`, `_instance_value`, `_template_fields`, `_slot_order`,
   `context_instance_spec`, `_merge_partial`, `_render_template`, `_expand_spec`,
   `_surface_details`, `context_instance_details`, `context_instances` (vista de 2
   claves), `context_instance_index`, `context_instance_metadata`,
   `context_instance_difficulty`, `served_difficulty` y las 8 claves aditivas de
   `context_for`.
4. `instance_space` en las 20 familias conservando las `instances` de V3.59 en los
   índices 1–2.
5. Cableado en `domain/vocabulary.py`: `served_difficulty` con el MISMO resumen de
   evidencia que el GET/POST.
6. Contrato: `TransferContextOut` + espejo TS `DrillTransferContext`.
7. Gates y cierre de release (ver `release-notes-v3.60.0.md`).

## Fuera de alcance (V3.61+)

`context_instance` **en el ledger** (evidencia instance-aware), el motor de
**política de instancia** (spacing / fallo / dificultad), **Student Skill State
3.0**, WSD real, aprendizaje de `P(success | learner, task)`, Observed Task
Difficulty 2.0 y **Planner 3.0**. Y, del arrastre de V3.59: el contrato/prompt de
generación de sentidos con su bump de `GENERATOR_VERSION` y la ponderación de la
adecuación en `transfer_confidence`.
