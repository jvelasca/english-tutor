# V1.21 (5/6) — P1-5: Interaction 3.0 (bajar turn_balance, desambiguar turn_completion, añadir repair)

## Rol
Backend. Corriges tres defectos de la señal de interacción señalados por la auditoría externa (puntos 11–14): el `turn_balance` no debe premiar exclusivamente el 50/50, la duración de turno no debe llamarse "completion" (duración ≠ completitud), y falta la señal semántica de **repair** (reformulación/recuperación de la comunicación). Sin dependencias nuevas.

## Contexto
La V1.20 fusiona señal OBJETIVA (telemetría de turnos, `services/interaction.py`) con señal SEMÁNTICA (LLM, `speaking_llm.py`). El auditor considera que:
1. `turn_balance` al 50/50 es "demasiado simplista": un alumno con 40% de turnos puede estar interactuando perfectamente.
2. `turn_completion` objetiva mapea **duración** (500ms→0, 4000ms→1), pero duración ≠ completitud. La completitud real es semántica (ya la da el LLM).
3. Falta `repair` en la capa semántica.
4. Hay que **reducir el peso de las heurísticas de duración/balance** frente a la señal semántica.

### Contratos exactos actuales (NO romper)
- `services/interaction.py`:
  - `_turn_balance_score(student_turns, assistant_turns)` (línea 47): hoy `1 - 2·|proportion - 0.5|`.
  - `_turn_completion_score(avg_duration_ms)` (línea 58) + constantes `TURN_COMPLETION_MIN_MS = 500`, `TURN_COMPLETION_FULL_MS = 4000` (líneas 21–22).
  - `interaction_evidence(turns)` (línea 68) devuelve clave `"turn_completion"` (línea 124).
- `services/speaking.py`:
  - `INTERACTION_SUBDIM_WEIGHTS` (línea 249): `appropriate_responses 0.30, turn_completion 0.25, follow_up_questions 0.20, topic_maintenance 0.15, clarification_requests 0.10` (suma 1.0). **Sin `repair`.**
  - `INTERACTION_OBJECTIVE_WEIGHT = 0.5` (línea 260).
  - `INTERACTION_OBJECTIVE_SUBDIM_WEIGHTS` (línea 267): `turn_balance 0.5, turn_completion 0.5`.
  - `_semantic_interaction_score` (línea 638) y `_interaction_objective_score` (línea 660) iteran las claves de esos dicts, así que **basta con cambiar las claves/pesos de los dicts** (la lógica se adapta sola).
- `services/speaking_llm.py`:
  - `SPEAKING_EVIDENCE_OPTIONAL_FIELDS` (línea 25) termina en `"clarification_requests"` (línea 58). **Sin `repair`.**
  - El prompt lista las claves opcionales (desde línea 107); `repair` no aparece.
  - `parse_speaking_evidence` parsea cada campo con `_parse_float_field` y lo añade a `result` (líneas ~289–338).
- `domain/academy.py` → `_inject_interaction_objective` (línea 675) comprueba `objective["turn_balance"]`/`objective["turn_completion"]` (líneas 696–699).
- `schemas/conversations.py` → `turn_completion: float | None` (línea 31).
- Tests afectados: `tests/test_interaction.py`, `tests/test_speaking.py` (helper `_interaction_objective` línea 1068), `tests/test_speaking_llm.py` (línea ~251), `tests/test_conversations_interaction.py` (líneas 63–78).

## Objetivo
Renombrar la señal objetiva de duración a `turn_duration`, suavizar `turn_balance` (meseta), añadir `repair` semántico, y re-ponderar para que la señal semántica domine sobre las heurísticas objetivas.

## Tareas

1. **`services/interaction.py`**
   - Renombra `_turn_completion_score` → `_turn_duration_score`; constantes `TURN_COMPLETION_MIN_MS`/`TURN_COMPLETION_FULL_MS` → `TURN_DURATION_MIN_MS`/`TURN_DURATION_FULL_MS` (valores 500/4000 intactos). Actualiza docstrings para dejar claro que es **duración**, no completitud.
   - `_turn_balance_score`: meseta en vez de pico en 0.5:
     ```python
     TURN_BALANCE_IDEAL_LOW = 0.3
     TURN_BALANCE_IDEAL_HIGH = 0.7

     def _turn_balance_score(student_turns: int, assistant_turns: int) -> float:
         total = student_turns + assistant_turns
         proportion = student_turns / total
         if TURN_BALANCE_IDEAL_LOW <= proportion <= TURN_BALANCE_IDEAL_HIGH:
             return 1.0
         if proportion < TURN_BALANCE_IDEAL_LOW:
             return round(_clamp(proportion / TURN_BALANCE_IDEAL_LOW), 3)
         return round(_clamp((1.0 - proportion) / (1.0 - TURN_BALANCE_IDEAL_HIGH)), 3)
     ```
   - En `interaction_evidence`, cambia la clave de retorno `"turn_completion"` → `"turn_duration"` (línea 124) y su docstring (línea 76). Llama a `_turn_duration_score` (línea 117).

2. **`services/speaking.py`**
   - `INTERACTION_OBJECTIVE_SUBDIM_WEIGHTS` → `{"turn_balance": 0.3, "turn_duration": 0.7}` (clave renombrada + balance secundario).
   - `INTERACTION_OBJECTIVE_WEIGHT` → `0.3` (la semántica pesa 0.7). Actualiza el comentario (líneas 257–260).
   - `INTERACTION_SUBDIM_WEIGHTS` → añade `repair` y renormaliza (suma 1.0):
     ```python
     INTERACTION_SUBDIM_WEIGHTS = {
         "appropriate_responses": 0.28,
         "turn_completion": 0.22,
         "follow_up_questions": 0.18,
         "topic_maintenance": 0.14,
         "clarification_requests": 0.09,
         "repair": 0.09,
     }
     ```
   - Actualiza los docstrings de `_semantic_interaction_score`, `_interaction_objective_score` y `_interaction_score` para reflejar las nuevas claves/pesos (la lógica de bucle no cambia).

3. **`services/speaking_llm.py`**
   - Añade `"repair"` a `SPEAKING_EVIDENCE_OPTIONAL_FIELDS` (tras `"clarification_requests"`).
   - Añade al prompt (tras la línea de `clarification_requests`, ~línea 146):
     `'- "repair": number between 0.0 and 1.0 — how well the student recovers or rephrases after a communication breakdown or misunderstanding.\n'`
   - En `parse_speaking_evidence`: `repair = _parse_float_field(data, "repair", None)` y, si no es `None`, `result["repair"] = repair`.

4. **`domain/academy.py`** → `_inject_interaction_objective` (líneas 696–699): cambia la comprobación a `objective["turn_balance"] is not None or objective["turn_duration"] is not None`. Actualiza el docstring (líneas 681–683).

5. **`schemas/conversations.py`** (línea 31): `turn_completion: float | None` → `turn_duration: float | None`. (`routers/conversations.py` devuelve `interaction_evidence(turns)` directamente, así que no requiere cambios.)

6. **Tests**
   - `test_interaction.py`: renombra todas las claves `turn_completion` → `turn_duration` (líneas 19, 70–106). Reescribe `test_turn_balance_imbalanced_lower` (línea 43) y añade: 40%/60% de turnos de alumno → `1.0` (dentro de la meseta), 10% → `round(0.1/0.3, 3)`, 90% → valor del tramo alto. Mantén `test_turn_balance_perfect_is_one` (50/50 → 1.0) y `test_turn_balance_unobservable_without_exchange`.
   - `test_speaking.py`: actualiza el helper `_interaction_objective` (línea 1068) y todos los dicts/fixtures que usen `turn_completion` objetiva (líneas ~1068–1182) a `turn_duration`. Actualiza las aserciones de scores fusionados si cambian por los nuevos pesos (0.3 objetiva / 0.7 semántica, y subdims). Añade un caso con `repair` presente en la evidencia semántica.
   - `test_speaking_llm.py`: añade `repair` al caso de campos opcionales (línea ~251–266).
   - `test_conversations_interaction.py`: `body["turn_completion"]` → `body["turn_duration"]` (líneas 63–78).
   - Añade un test de `_turn_duration_score` para confirmar que 500ms→0 y 4000ms→1 se mantienen.

## Criterios de aceptación
- `interaction_evidence` ya no expone `turn_completion` objetiva (solo `turn_duration`); la `turn_completion` semántica del LLM permanece en `speaking_llm`/`INTERACTION_SUBDIM_WEIGHTS`.
- `repair` se parsea del LLM y entra en la combinación semántica.
- La señal semántica domina (0.7) sobre la objetiva (0.3); dentro de la objetiva, `turn_balance` es secundaria (0.3).
- `turn_balance` = 1.0 en todo el rango [30%, 70%] de turnos del alumno.
- Pasa `pytest` y `ruff`. No toques frontend.
- Crea un único commit `feat: interaction 3.0 (balance con meseta, turn_duration, repair)` (no hagas push). Deja el briefing untracked.
