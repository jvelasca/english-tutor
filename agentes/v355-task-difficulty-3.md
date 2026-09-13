# Briefing de subagente — V3.55 (Task Difficulty 3.0)

> **Estado:** V3.55 **EJECUTADA** (2026-09-13, `v3.55.0`) por el gerente, sobre el
> árbol de `v3.54.0` (commit `1ee9d97`). Este documento registra el alcance, las
> decisiones de diseño y la verificación del incremento; se conserva como
> histórico del método (premisa 8: verifica siempre el estado real del árbol).

## Rol

Ingeniero de backend con foco en el **Evidence Ledger** (`learning_evidence`), el
**Difficulty Engine** (`services/difficulty.py`) y el **Student Skill State**
(`services/learner_skill.py`, `services/evidence.py`).

## Objetivo

Dar nombres honestos a la dificultad de la TAREA y hacer que la capacidad
observada acredite lo que el alumno **superó**, no lo que se le **sirvió**:

```text
EVENTO → DECLARED → SERVED → (descuento por andamiaje) → OBSERVED_TASK → CAPACIDAD
```

Cierra los **P2-01** y **P2-02** de la auditoría de V3.53.1. Todo aditivo en
contrato y esquema, determinista, sin LLM, y sin tocar `level_from_capacity`, el
gate CEFR global de V3.53.1, `observed_skill_capacity`, `learner_capacity`,
`CEFR_CAPACITY`, `transfer_state`, sus umbrales, `context_signals`,
`context_diversity`, el scoring, el planner ni FSRS.

## Estado de partida verificado (árbol `v3.54.0`)

- `learning_evidence.observed_difficulty` (V3.53) guardaba el vector del contexto
  **SERVIDO**, no lo superado, y **solo la escribía Transfer**: `recall`,
  `sentence` y `write` la dejaban `''`, así que `written_production`,
  `spoken_production` y `recall` no acumulaban capacidad NUNCA.
- `services.evidence.observed_signals` acreditaba **igual** cualquier éxito con
  vector, ignorando el `support_level` que el ledger ya guardaba: `guided`
  engordaba la capacidad tanto como `independent`.
- El ledger ya tenía `support_level`, `response_time_ms` y `error_type`, así que
  el P2-02 no requería columnas nuevas.
- El volcado de producción del chat libre
  (`domain.vocabulary._record_production_evidence`) recibe solo formas
  producidas, no filas del diccionario.

## Cambios

- **`services/difficulty.py`** — `SUPPORT_DISCOUNT_STEPS` (monótona con la
  escalera canónica), `declared_difficulty` (el `0` de `lexicon.cefr_difficulty`
  = no declarado), `observed_task_difficulty`, `task_difficulty_vectors`
  (serializa las tres + la proyección legacy `observed_difficulty` = `served`) y
  `earned_difficulty` (marca de fila V3.55 vs. legacy).
- **Persistencia aditiva** — `learning_evidence.declared_difficulty` /
  `served_difficulty` / `observed_task_difficulty` (`CREATE` + `ALTER TABLE`
  idempotente), plumbing en `record_evidence`/`record_evidence_bulk`/
  `list_evidence`/`list_observed_rows`/`summarize_by_target` y en
  `EVIDENCE_FIELDS`.
- **`services/evidence.py`** — `observed_signals` lee la carga ACREDITADA, sin
  cambiar el contrato del resumen; la paridad pura↔SQL se mantiene porque
  `summarize_by_target` sigue delegando en la MISMA función pura.
- **`domain/vocabulary.py`** — helper `_item_task_difficulty` y cableado de las
  cuatro vías: Word/Sentence (`guided`), Recall (`cued`/`guided`), Write
  (`independent`) y Transfer (`spontaneous`, con `declared` = carga léxica del
  ítem y `served` = vector del contexto). El volcado del chat libre queda fuera
  de alcance, documentado en el docstring de la función.

## Verificación

- `backend/tests/test_task_difficulty_v355.py` (17 tests): tabla de descuento y
  monotonicidad, `declared_difficulty` (incluido el `0`), serialización de las
  tres dificultades y del fallo, marca V3.55 vs. legacy, capacidad acreditada por
  apoyo, suelo alcanzado por `guided` vs. `independent` vía `learner_skill`,
  helper del drill léxico, escritura y transferencia de punta a punta, caché del
  perfil con capacidad léxica de `written_production`, migración idempotente y
  paridad pura↔SQL.
- `pytest -q` **2223 passed** en local (cero regresión; el bloque V3.51-V3.54 da
  236 verdes), `ruff check` limpio, `check_release_consistency` (**3.55.0**).

## Fuera de alcance (V3.56+)

`expected_learning_value` y el Planner 2.0 (P1-03), la dificultad en el volcado
de producción del chat libre, latencia y errores como moduladores de la
capacidad, el Sense Engine 2.0 y el Context Engine 3.0.
