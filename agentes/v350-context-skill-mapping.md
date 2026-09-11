# Briefing de subagente — V3.50 (Context→Skill mapping + difficulty matching)

> **Estado:** briefing del incremento V3.50, acordado por el gerente el
> 2026-09-11 a partir del cierre de V3.49.0 (candidato diferido en
> `release-notes-v3.49.0.md`, apartado «Fuera de alcance (V3.50+)»).
> Ver `release-notes-v3.50.0.md` para el resultado final.

## Rol

Ingeniero de backend (+ tipo del contrato en frontend) del proyecto English
Tutor, con foco en el motor de transferencia (`services/transfer.py`), el
planner (`services/planner.py`) y la frontera pura↔SQL del Evidence Ledger.

## Objetivo

Cerrar el candidato diferido por V3.49.0: los datos que el banco de contextos
declara desde V3.47/V3.48 (`cefr` y `difficulty_vector` por contexto) **hoy no
los consume nadie al elegir la tarea**. V3.50 hace dos cosas, ambas sin tocar la
escalera `transfer_state`, sus umbrales, el scoring (`score_transfer_attempt`)
ni FSRS:

- **Context→Skill mapping:** cada contexto del banco declara qué competencias
  ejercita, y la elección del contexto de transferencia **prioriza la modalidad
  limitante** del ítem (lo que ya decide `planner.limiting_skill`).
- **Difficulty matching:** la elección deja de coger el contexto más fácil
  alcanzable y pasa a preferir un contexto dentro de una **banda de dificultad**
  derivada del CEFR del ítem (evita servir el contexto más plano a un alumno
  avanzado), sin migración de BD.

Todo es **aditivo en el contrato HTTP**, determinista y sin LLM en el camino de
la decisión (premisa 21). El cambio de selección NO altera la evidencia: el
`context_id` sigue siendo el del contexto realmente servido y el gate de
`transfer_state` no se toca.

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local.
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia. El banco, la
  skill objetivo y la banda son tablas y funciones puras; no hay modelo en el
  camino.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **Premisa 6:** un incremento a la vez, con su release.
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisión de alcance (cerrada por el gerente)

- **V3.50 = conductual completo.** Cada contexto declara qué skills ejercita y
  `context_for` **cambia la selección** por skill limitante + banda de
  dificultad. No es solo informativo (el precedente informativo fue V3.48).
- **Dificultad objetivo SIN migración.** La banda se deriva del CEFR del ítem
  (`vocabulary.cefr`), no de un techo demostrado persistido. Se evitan los
  contextos demasiado fáciles y demasiado difíciles, favoreciendo el más alto
  alcanzable. (Persistir la dificultad del contexto por evento queda como
  frontera documentada, fuera de alcance.)
- **La escalera y el gate NO cambian.** `transfer_state`, sus umbrales
  (V3.46/V3.47), `context_signals`, `context_diversity`, FSRS y el Evidence
  Ledger se conservan tal cual. Cero regresión.
- **Los 6 contextos originales se CONGELAN** (mismos `id` y mismos valores core)
  para no alterar la evidencia ya registrada que referencia sus `context_id`;
  solo se les **añade** `skills`.
- **Sin cambio de UI**: solo se declara el campo opcional en `types/api.ts`.
- **Diferido (V3.51+):** Sense Engine 2.0, semantic appropriateness,
  `expected_learning_value` / Adaptive Planner 2.0 y la migración de la
  dificultad del contexto por evento.

## Archivos clave

- `backend/services/transfer.py` — **núcleo**: `CONTEXT_SKILLS` (nuevo),
  `TRANSFER_DIFFICULTY_BAND` (nuevo), `skills` en cada uno de los 20 contextos
  de `TRANSFER_CONTEXTS`, helper puro `context_skills` y banda de dificultad en
  `context_for` (firma con `skill=""` aditivo).
- `backend/domain/vocabulary.py` — `get_transfer_context` (≈780) y el fallback
  de `submit_transfer_attempt` (≈874) calculan y pasan la skill objetivo.
- `backend/schemas/vocabulary.py` — `TransferContextOut.skills` (aditivo).
- `frontend/src/types/api.ts` — `DrillTransferContext.skills?` (espejo opcional).
- Tests nuevos: `backend/tests/test_context_skill_v350.py`. Ajustes posibles en
  `backend/tests/test_transfer_v343.py`, `test_context_bank_v348.py` y
  `test_transfer_cefr_v347.py` (contrato exacto del retorno).

## Tarea detallada

### 1. Context→Skill mapping (declarado en el banco)

- Nuevo vocabulario declarado `CONTEXT_SKILLS: tuple[str, ...]` en
  `services/transfer.py`. **No** puede importar `LEXICAL_SKILLS` de
  `services/evidence.py` (ciclo: `evidence` ya importa `transfer`), así que se
  declara en local como **espejo** de `LEXICAL_SKILLS` (hoy `recall`,
  `written_production`, `spoken_production`, `spontaneous_use`) con un test de
  paridad que falle si divergen.
- Cada uno de los 20 contextos de `TRANSFER_CONTEXTS` gana
  `skills: tuple[str, ...]`, **curado** (no derivado de otros atributos):
  - subconjunto no vacío de `CONTEXT_SKILLS`;
  - al menos una modalidad de producción (`written_production` o
    `spoken_production`) para que discrimine de verdad;
  - `spontaneous_use` cuando el escenario admita uso libre de la unidad.
  - Regla de autoría orientativa (el subagente puede ajustar con criterio
    pedagógico, siempre dentro del vocabulario):
    - `interaction_type == "dialogue"` → `spoken_production` +
      `spontaneous_use`;
    - monólogo narrativo/descriptivo → `written_production` (+
      `spoken_production` si el contexto se puede decir en voz alta);
    - `difficulty_vector["lexical"] >= 3` → incluye `recall` (exige
      recuperación, no solo reconocimiento).
  - Los 6 contextos originales conservan `id` y valores core congelados; solo se
    les **añade** `skills`.
- Helper puro `context_skills(context: object) -> tuple[str, ...]`: normaliza
  (dedupe, orden estable por `CONTEXT_SKILLS`, ignora valores fuera del
  vocabulario) y nunca lanza. Se usa para validar y para exponer el contrato.

### 2. Difficulty matching (banda desde el CEFR del ítem)

- Constante declarada `TRANSFER_DIFFICULTY_BAND = 1` (banda de tolerancia por
  debajo del objetivo; calibrable).
- Con un `level` CEFR reconocible, tras la cota superior actual
  (`_within_level`, V3.47):
  - `reachable` = contextos con `cefr_index(context["cefr"]) <= cefr_index(level)`
    (ya lo calcula `_within_level`; reutilizar);
  - `target = max(difficulty_from_vector(c["difficulty_vector"]) for c in reachable)`;
  - preferir contextos con `difficulty >= target - TRANSFER_DIFFICULTY_BAND`;
  - si el filtro deja el pool vacío, **degradar con gracia** ignorándolo;
  - sin `level` reconocible (p. ej. `Pre-A1`/vacío) o sin `reachable`, el
    comportamiento es exactamente el de V3.47 (fallback al nivel más cercano por
    arriba).

### 3. Pipeline determinista de `context_for`

Firma aditiva (retrocompatible):

```python
context_for(
    word, used_context_ids=(), *,
    success_context_ids=(), condition="", level="", skill="",
) -> dict
```

Orden del pipeline (cada filtro degrada con gracia; nunca deja al alumno sin
tarea, `available` sigue `True`):

1. filtrar contextos usados (`used_context_ids`); si vacío → banco completo con
   `exhausted=True` (comportamiento actual);
2. `_within_level(pool, level)` (V3.47);
3. **skill** (nuevo): si `skill` viene declarada, preferir los contextos que la
   incluyen en `skills`; si ninguno la declara, ignorar el filtro;
4. **banda de dificultad** (nuevo): preferir `difficulty >= target - BAND`;
5. **novedad** (V3.43): si hay `success_context_ids`, quedarse con los de máxima
   distancia mínima;
6. `_stable_index(word)` sobre el pool final → contexto servido.

- Determinismo intacto: misma palabra + misma evidencia + mismo `skill`/`level`
  → misma consigna (no usar `hash()` ni reloj).
- El dict de retorno gana `skills` (lista, aditivo). `cefr`/`difficulty_vector`/
  `difficulty` ya existen desde V3.47.

### 4. Punto de consumo (planner → context_for)

En `backend/domain/vocabulary.py` (añadir `planner` al bloque `from services
import (...)`):

- La **skill objetivo** se calcula en ambos caminos con la MISMA expresión:
  `planner.limiting_skill(planner.planned_signals(summary, matrix))`, donde
  `matrix = lexicon.item_competence_matrix(row)` y `summary` es el resumen del
  ledger que ya se lee (`evidence_repo.summarize_by_target`).
- Si no hay segmentación por modalidad, `limiting_skill` devuelve `""` → sin
  filtro de skill (comportamiento V3.49).
- Pasar `skill=skill` en `get_transfer_context` (GET) **y** en el fallback de
  `submit_transfer_attempt` (POST sin `context_id`), para que ambos deriven el
  mismo `context_id` (paridad GET↔POST).
- Es una **preferencia**, no una obligación: la skill objetivo no se persiste ni
  cambia el scoring; solo ordena la elección del escenario.

### 5. Contratos (estrictamente aditivos)

- `backend/schemas/vocabulary.py` → `TransferContextOut.skills: list[str] = []`.
- `frontend/src/types/api.ts` → `DrillTransferContext.skills?: string[]`.
- Sin migración de BD y sin tocar `TransferAttemptIn`/`TransferAttemptOut`.

## Criterios de aceptación

- Los 20 contextos declaran `skills` no vacío, subconjunto válido de
  `CONTEXT_SKILLS` y con al menos una modalidad de producción.
- `CONTEXT_SKILLS` coincide exactamente con `services.evidence.LEXICAL_SKILLS`
  (test de paridad).
- Los 6 contextos originales conservan `id` y valores core congelados (guardia
  por test); solo ganan `skills`.
- `context_for(skill=...)` prefiere un contexto que declara esa skill; si
  ninguno la declara, la elección es idéntica a la de V3.49 (fallback).
- Banda: con un ítem B1, `context_for` no sirve el contexto A1 más plano si hay
  uno más difícil alcanzable; sin `level` el resultado es idéntico a V3.47/V3.48
  (regresión).
- Determinismo y rotación `exhausted` siguen funcionando.
- GET y el fallback del POST derivan el mismo `context_id`.
- No regresión del gate: `test_transfer_v343.py`, `test_transfer_cefr_v347.py`,
  `test_transfer_condition_v346.py`, `test_context_bank_v348.py`,
  `test_learning_evidence_v336.py` y `test_transfer_confidence_v349.py` verdes.
- `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.50.0**
  exit 0.

## Restricciones

- Contratos HTTP estrictamente aditivos; **sin migración de BD**.
- Sin LLM en el camino de la evidencia (premisa 21) y sin reloj en la decisión.
- No tocar `services/evidence.py` en su lógica de gate (`transfer_state`,
  umbrales, `context_signals`, `context_diversity`), ni FSRS, ni el scoring
  (`services/lexicon.score_transfer_attempt`), ni la CONSTITUCIÓN (R8/R9 sigue
  como propuesta abierta).
- No reordenar ni reinterpretar los valores core de los 6 contextos originales.
- Un cambio grande a la vez (premisa 6): nada de Sense Engine 2.0,
  semantic appropriateness ni Adaptive Planner 2.0.
- `CONTEXT_SKILLS` se declara en `transfer.py` (espejo), nunca importando
  `services.evidence` (evita el ciclo de importación).

## Salida esperada

- Código + tests + `release-notes-v3.50.0.md` + actualización de `CHANGELOG.md`,
  `PLAN.md`, `README.md`, `docs/RELEVO.md` y `agentes/README.md`, y bump
  `3.49.0 → 3.50.0` en las fuentes verificadas por
  `scripts/check_release_consistency.py` (backend `config.py` como fuente única
  + `frontend/package.json`/`package-lock.json`).
- Commit de release limpio y CI 6/6 en verde.

## Resultado (V3.50.0, implementado — 2026-09-11)

Ejecutado tal cual salvo dos **refinamientos de calibración** descubiertos al
probar con los datos reales del banco (ver `release-notes-v3.50.0.md`, que es la
fuente de verdad del resultado):

1. **Objetivo de dificultad anclado al nivel.** La fórmula literal
   `target = max(difficulty del alcance)` no cumplía su propio criterio de
   aceptación con los datos reales: para un ítem B1 el techo alcanzable es 2 y
   `2 − TRANSFER_DIFFICULTY_BAND(1) = 1`, así que los contextos A1 seguían
   entrando. Se usa `target = max(techo_alcanzable, cefr_index(level) + 1)` (la
   escala 1..6 es la misma que `difficulty_from_vector`), y el mínimo de la banda
   se calcula sobre TODO el alcance del nivel antes de filtrar por modalidad.
2. **Degradación de la banda más útil.** Si la banda pedida no existe en el pool
   ya filtrado por modalidad, no se devuelve el pool entero (podía colar un
   contexto A1 a un ítem C2): se conserva el tramo MÁS DIFÍCIL disponible
   (`_within_band`).

Además, el helper `domain.vocabulary._transfer_target_skill` hace explícito el
`""` sin segmentación comprobando que `skill_attempts` tenga algún valor > 0
(`planner.limiting_skill` por sí solo nunca devuelve `""` con el bloque `skills`
presente, porque `skill_signals` emite zeros por modalidad).
