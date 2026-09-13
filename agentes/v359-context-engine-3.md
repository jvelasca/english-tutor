# Briefing de subagente — V3.59 (Context Engine 3.0: Context Bank Family/Instance)

> **Estado:** incremento V3.59 **EJECUTADO** (2026-09-13, release **v3.59.0**),
> escrito sobre el árbol de `v3.58.0` (commit `82f17c4` + docs `7687f1b`). Es el
> candidato que el proyecto arrastra como **diferido** desde V3.48
> («Context Bank Family/Instance») y responde al hallazgo **P2-04** de la
> auditoría de V3.43: un banco finito de consignas **FIJAS** se **MEMORIZA**.
> V3.59 separa **FAMILIA** (identidad pedagógica + unidad de EVIDENCIA) de
> **INSTANCIA** (superficie declarada de la misma familia, servida por ROTACIÓN
> de intentos). Resultado verificado: `pytest` **2312 passed**, `ruff` limpio,
> launcher **75 passed**, `tsc` OK, `vitest` **651**, build OK y
> `check_release_consistency` **3.59.0**; ver `release-notes-v3.59.0.md`.
> **Histórico.**
> Antes de reutilizar este briefing, **verifica el estado real del árbol**
> (premisa 8): los nombres y las líneas de abajo se citan del árbol de `v3.58.0`
> y pueden haber cambiado.

## Rol

Agente de implementación del incremento V3.59 sobre el repo `english-tutor`, en
la rama `main`, con el estándar del proyecto: determinista, sin LLM en el camino
de la evidencia (premisa 21), cambios **aditivos**, cero regresión de la
evidencia ya registrada y **tests-first**.

## Objetivo

Que el banco de contextos de transferencia **no se memorice**. Hasta V3.58 cada
una de las 20 familias tenía **una sola** consigna: agotado el banco
(`exhausted=True`), el motor rotaba sobre las mismas 20 redacciones y el alumno
podía reciclar una respuesta aprendida en lugar de transferir la unidad. V3.59
añade **superficies** a cada familia —otra redacción del MISMO escenario— sin
tocar la identidad de la familia ni, por tanto, la evidencia, los umbrales ni la
selección.

## Contexto del proyecto

- **Qué es una familia aquí:** uno de los 20 contextos de `TRANSFER_CONTEXTS`
  (`services/transfer.py`), con `id` (=`context_id` del ledger), seis dimensiones
  core (`topic`, `communicative_goal`, `discourse_type`, `social_relation`,
  `time_reference`, `interaction_type`), `register`, `cefr`,
  `difficulty_vector`, `skills`, `lexical_environment`, `syntactic_focus` y
  `prompt`. Los seis primeros contextos están **congelados** (V3.43–V3.48).
- **Qué depende de la familia (y NO puede moverse):** `transfer_state` y sus
  umbrales (`services/evidence.py`), `context_distance`, `context_diversity`,
  `CONTEXT_DIVERSITY_MIN`, `_novelty_score` y el ajuste de dificultad
  (`services/difficulty.py`). Si la superficie cambiara alguno de esos atributos,
  reinterpretaría la evidencia pasada.
- **Qué llega al drill (V3.58):** `domain/vocabulary.py` → `transfer.context_for`
  con `used_context_ids` y `success_context_ids` del resumen de evidencia, el
  `level` del ítem, la `skill` limitante, el suelo del alumno y su capacidad
  observada.

## Estado de partida verificado (árbol `v3.58.0`)

- `services/transfer.py`: `TRANSFER_CONTEXTS` (20 familias), `context_for`
  (selección pura), `context_attributes`/`context_skills`/`context_difficulty`,
  `_as_attributes`, `_bare_context_id`, `_stable_index`, `_novelty_score`.
- `schemas/vocabulary.py`: `TransferContextOut` (25 campos en V3.58).
- `domain/vocabulary.py`: los dos llamadores de `context_for` (GET de la consigna
  y derivación del `context_id` en el POST).
- **Tests que blindan el banco:** `tests/test_context_bank_v348.py` (20 familias,
  distribución CEFR, distancia mínima, seis congelados) y
  `tests/test_context_skill_v350.py::test_skills_are_the_only_addition_to_the_frozen_contexts`
  (la consigna de `story` byte a byte).
- **Resumen de evidencia:** `summary["contexts"]` es
  `{context_id: {"attempts": n, "successes": m}}` (`services/evidence.py`).

## Decisiones de alcance (CERRADAS)

1. **Family/Instance, no banco nuevo.** Las 20 familias NO cambian de `id`: la
   evidencia, los umbrales y la diversidad quedan intactos por construcción.
   Ampliar el banco «a lo bruto» habría movido el ledger.
2. **La superficie 0 es la consigna histórica.** Degradación EXACTA a V3.58 sin
   evidencia (y byte a byte en los seis contextos congelados).
3. **Rotación por intentos de la FAMILIA** (`N % nº_superficies`), no por hash:
   el ítem recibe cada vez una redacción distinta hasta agotar la familia. Es
   determinista y explicable, y mantiene la invariante «misma evidencia → misma
   consigna».
4. **La glosa de identidad es lista blanca.** `CONTEXT_INSTANCE_KEYS` impide que
   una instancia declare atributos de la familia.
5. **SIN migración, SIN bump de `GENERATOR_VERSION` y SIN cambios de UI**: el
   contenido es declarado, no generado.
6. **Contrato aditivo:** 3 claves nuevas; las 25 de V3.58 intactas y fijadas por
   test.

## Plan de implementación (tests-first)

1. `tests/test_context_engine_v359.py`: banco, núcleo puro, no-regresión de la
   decisión, contrato exacto del payload, invariantes del banco y end-to-end HTTP
   de la rotación con el pool agotado.
2. Núcleo puro en `services/transfer.py`: `CONTEXT_INSTANCE_KEYS`,
   `CONTEXT_INSTANCES_MIN`, `context_instances`, `context_instance_index`,
   `_count`, `_attempts_for` y las `instances` de las 20 familias.
3. `context_for`: kwarg `attempts_by_context` y los tres campos aditivos en todos
   los retornos.
4. Cableado en `domain/vocabulary.py` (los dos caminos, mismo mapa de intentos).
5. Contrato: `TransferContextOut` + espejo TS `DrillTransferContext`.
6. Gates y cierre de release (ver `release-notes-v3.59.0.md`).

## Fuera de alcance (V3.60+)

El contrato/prompt de generación de sentidos y su bump de `GENERATOR_VERSION`,
la ponderación de la adecuación en `transfer_confidence` y cualquier uso del LLM
en el camino de la evidencia (premisa 21).
