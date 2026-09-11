# P — Auditoría externa total de V3.43.0 (y resolución de alcance V3.44)

> Fecha: 2026-09-11 · Rol: **auditoría externa de la release v3.43.0 sobre el
> estado de `main`, contrastada contra los P1/P2 abiertos de la auditoría de
> V3.42.0**, seguida de la resolución de alcance para V3.44.
> Posición auditada: **release v3.43.0** (`VERSION = "3.43.0"`, commit
> `04d8db92df8ea12c247c460ee263bf46a189a406`, tag `v3.43.0`, run
> [34571938704](https://github.com/jvelasca/english-tutor/actions/runs/34571938704)).
> Método: lectura del código y de las notas de release, contraste explícito
> V3.42 → V3.43 y juicio sobre la madurez del modelo pedagógico.

## Veredicto

🟢 **V3.43.0 — 9,6 / 10**. Sin P0. Los **cuatro P1 principales de V3.42.0 están
realmente atacados y, en lo esencial, cerrados**. Los P1/P2 residuales son ya
problemas de **madurez del modelo pedagógico**, no fallos estructurales como los
de V3.37–V3.42.

## 1. Comparación V3.42 → V3.43

| Problema V3.42 | V3.43 | Estado |
| --- | --- | --- |
| Target visible en Transfer | Target oculto | 🟢 CERRADO |
| `passed` = transferencia limpia | `semantic_fit` separado | 🟢 CERRADO |
| `2 context_id` = diversidad | diversidad por dimensiones | 🟢 CERRADO |
| `transfer = true/false` | `transfer_state` | 🟢 CERRADO |
| Contexto nuevo elegido sin geometría | distancia contextual | 🟢 MEJORADO |
| Planner ignora parcialmente Transfer | usa `transfer_state` | 🟢 CERRADO |
| Lexical unit sin sense | sigue pendiente | 🟠 V3.44 |
| Context Bank pequeño | sigue pendiente | 🟠 V3.44 |
| Expected Learning Value | sigue pendiente | 🟠 V3.44 |

La dirección es exactamente la recomendada.

## 2. 🔴 P1 — El proxy semántico puede producir falsos positivos

Es el principal problema real de V3.43. El sistema hace `POS = noun` +
`"I bank yesterday"` → `semantic_mismatch`, y eso está bien, pero el mecanismo
reconoce que trabaja con una heurística basada en POS y patrones superficiales.
La propia release deja abierto que palabras que funcionan legítimamente como
sustantivo y verbo puedan clasificarse como sospechosas:

`travel`, `water`, `plan`, `work`, `change`, `answer`, `phone`, `email`.

Ejemplo: con la entrada `plan = noun`, la frase **`I plan my trip.`** podría
sospechar `semantic_mismatch` aunque sea perfectamente correcta. El sistema hace
bien en que `semantic_mismatch` **no destruye `lexical_transfer`**, pero puede
impedir que el intento sea un *clean success*.

**🔴 P1-01:** no usar la POS de una entrada global como sustituto de
sense/context. V3.44 debe implementar
`LEXICAL UNIT → SENSE → POS → CONTEXT → EVIDENCE`, y no
`LEXICAL UNIT → POS global → semantic_fit`.

## 3. 🟢 P1 anterior — Target oculto, correctamente solucionado

El nuevo banco usa `scenario + communicative_goal` sin introducir la palabra
objetivo (p. ej. «Tell a short story about something that happened to you
recently.» en vez de «Tell a story using "travel".»). Cambia radicalmente la
tarea: `scenario → retrieve lexical item → decide whether it is useful →
produce`, mucho más cerca de la transferencia léxica auténtica. El backend sigue
conociendo el target y puede verificarlo después. **P1 cerrado.**

## 4. 🟢 Muy buena solución — `context_distance()`

Cada contexto declara `topic`, `communicative_goal`, `discourse_type`,
`social_relation`, `time_reference`, `interaction_type`, y la distancia se
calcula como número de dimensiones diferentes. Es bastante más serio que
`context_a != context_b`. Excluir `register` (todos `neutral`) evita falsear la
diversidad. Buena decisión técnica.

## 5. 🟢 `context_for()` mejora mucho

`unused contexts → compare with successful contexts → maximize minimum distance
→ stable hash tie-break` es razonable. `novelty(C) = min(distance(C,
success_context_i))` y se elige `max novelty(C)`. Evita elegir un contexto que
solo difiere del último, pero es muy parecido a otro ya dominado. Mejor que una
rotación simple.

## 6. 🟠 P1 — La diversidad contextual sigue siendo una métrica simple

`2 dimensiones diferentes` no implica necesariamente `2 contextos pedagógicamente
diferentes`: `topic = employment / goal = describe` y `topic = employment /
goal = explain` pueden exigir casi el mismo repertorio. `diverse_dimensions >= 2`
es útil como proxy, pero **no debería convertirse todavía en una afirmación
fuerte de «transferencia demostrada»**. Recomendación futura: sumar
`communicative_distance`, `lexical_context_distance`, `syntactic_distance` y
`discourse_distance` (V3.44/V3.45).

## 7. 🟢 `transfer_state` es una mejora importante

`not_ready → emerging → contextualized → transfer_demonstrated →
transfer_stable → automatic` distingue primer éxito, transferencia demostrada y
transferencia estable. `transfer_state()` es la fuente formal del eje y el
booleano antiguo queda como compatibilidad legacy. **P1 cerrado.**

## 8. 🔴 P1 — Los nombres de los estados pueden sugerir más evidencia de la disponible

`transfer_demonstrated` (`2 clean contexts + 2 diverse dimensions`) es un
criterio operacional interno correcto, pero **no** significa que el alumno use la
palabra espontáneamente en cualquier contexto. Debe entenderse como
«transferencia contextual demostrada bajo el protocolo de evaluación interno»,
no como «transferencia generalizada». Importante cuando el Student Model lo use
para CEFR.

## 9. 🟢 Excelente decisión — `semantic_mismatch` no destruye la evidencia léxica

`passed = True` y `semantic_fit = suspect` pueden coexistir, lo que separa «¿usó
la unidad?» de «¿la usó probablemente de forma adecuada?». Un heurístico nunca
debe destruir evidencia objetiva. La V3.43 mantiene esta separación explícita.

## 10. 🔴 P1 — Falta una tercera categoría más importante que `suspect`: `incorrect`

Hoy `fit / suspect / unknown` es prudente pero limitado: `unknown` = «no puedo
evaluar», `suspect` = «parece extraño», y falta `incorrect` para una
incompatibilidad semántica demostrable. **Solo `incorrect` debería bloquear un
clean transfer**; `suspect` debería generar warning y quizá reducir confianza.

## 11. 🔴 P1 — El scoring semántico todavía no evalúa realmente el significado

`POS + morfología + determinantes + patrones` detecta `I bank yesterday`, pero no
resuelve de forma robusta `I went to the bank yesterday` / `I banked the river
yesterday` / `The river bank was beautiful`. El problema es *word sense
disambiguation*. La solución definitiva:
`surface → lemma → lexical_unit → sense → context → semantic_fit`. No convertir
el heurístico en un pseudo-LLM: mantenerlo como **advisory signal** hasta tener
el modelo de sentidos.

## 12. 🟢 La compatibilidad hacia atrás está bien pensada

Un resumen legacy con `transfer = true` no se interpreta como `transfer_stable`
sino como `transfer_demonstrated`, evitando una regresión conceptual al leer
datos antiguos. Y `no migration` mantiene la release quirúrgica. Correcto.

## 13. 🟠 P1 — El Context Bank sigue siendo demasiado pequeño

`story / question / work / future / opinion / problem` sirve para probar el
motor, pero no para A1 → C2: tras pocas sesiones el alumno puede memorizar la
estructura del contexto en lugar de transferir. Eventualmente:
A1 30–50 templates · A2 50–100 · B1 100–200 · B2 200+ · C1/C2 dinámicos/
auténticos, parametrizables.

## 14. 🟠 P2 — El contexto debería tener CEFR

Falta explícitamente `cefr_target` / `difficulty_vector`: «Talk about your plans»
puede ser A1 mientras «Defend a nuanced position about the long-term
consequences…» es otra cosa. Fundamental para que el planner no pida un contexto
B2 a un alumno A1 solo porque la palabra esté en su vocabulario.

## 15. 🟠 P1 — `spontaneous_use` sigue siendo demasiado amplio

El target oculto lo justifica mucho mejor, pero son pedagógicamente distintos:
(A) escenario + «try to use the target word»; (B) escenario sin mención +
«use any vocabulary you need»; (C) conversación libre donde el alumno elige la
palabra; (D) conversación natural donde aparece sin provocarla. Introducir
`retrieval_condition`: `prompted / cued_context / open_context / free_choice /
naturally_emergent`.

## 16. 🟢 La separación `lexical_transfer` / `semantic_fit` es excelente para el futuro

Permite construir `LEXICAL SUCCESS → {semantic fit, fluency, grammar,
pronunciation, appropriateness}` y que el Student Model sepa «el alumno conoce
la palabra y puede recuperarla, pero todavía no la usa correctamente en
contexto», mucho más útil que `word = 82 %`.

## 17. 🟠 El modelo de lexical unit sigue teniendo la deuda de sense

`bank` sigue siendo aproximadamente `lexical_unit = bank`, pero se necesita
`bank → {sense: financial, sense: river_edge}` (y para `run` la diferencia es
mayor). Prioridad de V3.44.

## 18. 🟢 No detecto regresión en el Evidence Model

`attempt / success / failure / support / context / activity / latency / error /
interval` siguen consistentes, y el resumen incluye `clean_contexts`,
`clean_successes`, `clean_success_contexts`, `clean_success_days` y
`context_diversity`. La capa pura y el resumen SQL comparten las mismas señales.
Exactamente lo deseado.

## 19. 🟢 Muy buena decisión — No migrar DB

Añadir información mediante campos derivados y `error_type` mantiene el esquema
estable y la semántica nueva derivada. Decisión correcta para esta fase.

## 20. 🟢 Tests

`pytest 1989 passed`, `vitest 607 tests / 70 files`, `ruff` limpio, `tsc` limpio,
Vite build OK, release consistency 3.43.0 y run verde `34571938704` (6/6 jobs,
incluido E2E Playwright). Mejora de confianza importante respecto a releases
anteriores.

## 21. Un punto que NO cambiar

`LLM → content generation` pero `LLM ⊗ → learning evidence`. El LLM puede
generar situaciones, definiciones, ejemplos, proponer feedback y ayudar a
interpretar lenguaje, pero **no debe tener autoridad unilateral para modificar el
Student Model**. La evidencia primaria debe seguir siendo
determinista/auditable, y cualquier inferencia probabilística debe vivir en otro
nivel: `observed evidence → derived inference → confidence`.

## 22. Arquitectura correcta para V3.44

`EVENT → EVIDENCE → {SKILL, LEXICAL UNIT, CONTEXT}`; `LEXICAL UNIT → SENSE →
SEMANTIC EVIDENCE → RETENTION STATE → TRANSFER STATE → SKILL STATE → LEARNING
NEEDS → CANDIDATE TASKS → EXPECTED LEARNING VALUE → NEXT BEST TASK`. El objetivo
real es **Optimal Next Task 2.0**: no «¿qué palabra toca?» sino «¿qué debería
hacer el alumno ahora para obtener la mayor ganancia pedagógica esperada?».

## 23. Lista definitiva para V3.44

**🔴 P1**

1. **Sense-aware Lexical Model** (`lexical_unit → sense`). El siguiente gran paso.
2. **Semantic scoring robusto** (`fit / suspect / incorrect / unknown`), sin
   permitir que un heurístico destruya evidencia.
3. **Transfer condition** (`prompted / cued_context / open_context / free_choice /
   naturally_emergent`).
4. **Context difficulty / CEFR** (`cefr`, `difficulty_vector` por contexto).

**🟠 P2**

5. **Context Bank 2.0** (muchos más contextos).
6. **Context diversity 2.0** (no solo nº de dimensiones: `topic`, `goal`,
   `discourse`, `social relation`, `interaction`, `time`, `syntax`, `lexical
   environment`).
7. **Semantic appropriateness** (separar lexical / semantic / grammatical
   correctness).
8. **Mejor estado de Transfer**, acompañado de `confidence`, `evidence_count`,
   `context_diversity`, `independence`, `recency`.

## 24. El cambio de arquitectura posterior

Construir el **Student Model multidimensional** (`RETENTION / SKILLS /
TRANSFER`) que alimente `LEARNING NEEDS → TASK CANDIDATES → EXPECTED VALUE`
(`gap`, `retention`, `transfer`, `skill weakness`, `difficulty fit`, `novelty`,
`repetition cost`, `latency`, `recent failures`) → **NEXT BEST TASK**. Ese es el
salto de Planner → **Adaptive Learning Engine**.

## Resolución de V3.44 (alcance ejecutado)

V3.44 adopta **la lista 1 + 2** del punto 23 como alcance cerrado (decisión del
gerente, opción A), manteniendo la premisa 6 (un incremento) y la 21 (el LLM
genera contenido, nunca decide evidencia):

- **P1-01 → Sense-aware Lexical Model.** `GENERATOR_VERSION` `1.3.0 → 1.4.0`; el
  contrato de contenido gana `senses` (`[{pos, gloss}]`) con `normalize_senses`
  puro; migración aditiva `senses_json` en `dictionary_entries` y
  `dictionary_reverse_entries`; nuevo módulo puro `services/semantics.py`
  (`families_from_senses`, `occurrence_role`, `semantic_adequacy`).
- **P1-02 → Semantic scoring robusto.** `score_transfer_attempt(..., senses=())`
  con `fit / suspect / incorrect / unknown`; `incorrect` (contradicción fuerte
  con TODAS las familias) es el **único** que bloquea el clean success
  (`semantic_mismatch`); `suspect` es advisory (`semantic_doubt`, nueva const y
  ampliación de `TRANSFER_ERROR_TYPES`). Sin sentidos → `unknown`, que nunca
  bloquea. Contratos HTTP aditivos (`DictionaryEntryOut.senses`, `adequacy`
  admite `incorrect`).

Puntos 3, 4 y 5–8 del punto 23 quedan **fuera de alcance (V3.45+)**: la
`transfer_condition`, el CEFR/`difficulty_vector` del contexto, el Context Bank
2.0, `expected_learning_value` / Adaptive Planner 2.0 y cualquier decisión que
dé al LLM autoridad sobre el Student Model.
