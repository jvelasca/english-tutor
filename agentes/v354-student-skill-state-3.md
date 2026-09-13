# Briefing de subagente — V3.54 (Student Skill State 3.0)

> **Estado:** V3.54 **EJECUTADA** (2026-09-13, `v3.54.0`) por el gerente, sobre el
> árbol de `v3.53.1` (commit `6d8af47`). Este documento registra el alcance, las
> decisiones de diseño y la verificación del incremento; se conserva como
> histórico del método (premisa 8: verifica siempre el estado real del árbol).

## Rol

Ingeniero de backend (+ tipo del contrato en frontend) con foco en el **Student
Model** (`skill × dimensión`), el **Evidence Ledger** (`learning_evidence`) y el
**Difficulty Engine 2.0** (`services/difficulty.py`).

## Objetivo

V3.53/V3.53.1 dejaron la capacidad observada como un vector por DIMENSIÓN,
colapsando las modalidades. V3.54 conserva la modalidad:

```text
EVIDENCE → SKILL × DIMENSIÓN → CAPACIDAD OBSERVADA → SUELO POR SKILL
```

Además, impide que una capacidad PARCIAL eleve una tarea multidimensional (gate
de cobertura). Todo aditivo en contrato y esquema, determinista, sin LLM, y sin
tocar `level_from_capacity`, `transfer_state`, sus umbrales, `context_signals`,
`context_diversity`, el scoring, el planner ni FSRS.

## Estado de partida verificado (árbol `v3.53.1`)

- `services.evidence.observed_signals` YA agregaba `observed_capacity` por
  modalidad y dimensión, con muestra espaciada; la pérdida ocurría después.
- `services.learner_skill.observed_capacity` tomaba el **máximo entre skills** por
  dimensión: una capacidad escrita elevaba una tarea oral.
- `learner_capacity` (plano) entraba al `challenge` vectorial de
  `services.transfer` sin distinguir la modalidad que la tarea mide.
- `student_state.floor_level` usaba el `observed_cefr` GLOBAL.
- Solo el drill Transfer persiste `observed_difficulty`; recall/write/sentence lo
  dejan `''` (el enriquecimiento por drill es V3.55).

## Cambios

- **`services/learner_skill.py`** — `observed_skill_capacity` (fuente de verdad),
  `observed_capacity` (proyección legacy), `normalize_skill_capacity`,
  `level_from_skill_capacity` (cobertura COMPLETA por skill), `skill_coverage`,
  `skill_capacity` (`{capacity, coverage, covered_dimensions}`),
  `observed_skill_state`, `empty_state`.
- **`services/student_state.py`** — `floor_level_for_skill` (demostrado >
  observado del SKILL > estimado > declarado; sin herencia entre modalidades).
- **`services/difficulty.py`** — `challenge_for` y
  `select_by_difficulty(..., covered_dimensions, floor_challenge)`.
- **`services/transfer.py`** — `context_for(..., learner_skill_capacity,
  capacity_skill)`, `capacity_skill` en la salida.
- **Persistencia** — `learning_profile.observed_skill_capacity` (aditiva, JSON),
  `repositories/profile.py`, `domain/profile.py`, `schemas/profile.py`,
  `frontend/src/types/api.ts`; `domain/vocabulary.py` lee el estado por skill y
  conserva la paridad GET↔POST.

## Verificación

- `backend/tests/test_learner_skill_v354.py` (19 tests) + ajuste del estado
  neutro en `test_student_state_v352.py`; cero regresión en las suites de
  V3.51-V3.53.
- `ruff check .` y `pytest -q` en el backend; `check_release_consistency`
  (**3.54.0**).

## Fuera de alcance (V3.55+)

`declared`/`served`/`observed_task_difficulty`, `expected_learning_value`,
Planner 2.0, Sense Engine 2.0 y Context Engine 3.0.
