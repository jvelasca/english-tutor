# AD · Auditoría de validez de la afirmación de maestría (V3.70 · Eje 4)

> **Release:** V3.70 (auditoría pedagógica + CEFR) · **Eje 4 de 5**
> **Fecha:** 2026-09-15 · **Instrumento:**
> `python -m scripts.audit_dossier mastery-claims` (solo lectura)
> **Evidencia cruda:** `docs/audit/generated/mastery-claims.{md,json}`

## Alcance

La pregunta del eje es: **¿«demostrado» significa lo que dice?**

Se auditan los cuatro estados de competencia (`services/competence.py`), sus
gates, los mínimos de `backend/curriculum/cefr_matrix.json` (v2.1.0), el gate
espaciado (`services/learner_skill.py`), la profundidad de evidencia
(`services/evidence_depth.py`) y los **tres registros de modalidades** que el
sistema mantiene en paralelo.

**No se audita** el contenido (eje 1), la cobertura (eje 2), el feedback (eje 3)
ni los instrumentos (eje 5). **No se audita** tampoco la calibración empírica de
los umbrales con alumnos reales: eso requiere tráfico y está en
`docs/audit/PARKED.md`.

## Método

1. Instrumento `mastery-claims`: cruza los tres registros de modalidades, cuenta
   los requisitos de la matriz (48 celdas = 6 niveles × 8 destrezas) y ejecuta
   las funciones **puras** del Student Model con entradas fijas.
2. **Verificación en código** de las dos afirmaciones estructurales del briefing
   que debían comprobarse, no asumirse: el emisor de `novel` y la acreditación
   de las filas sin `objective_id`.
3. **Medición conductual** del hueco de acreditación: se construyen filas
   sintéticas de `academy_evidence` y se observa qué acredita éxito.

## Evidencia

### 1. Tres registros, tres tamaños

| Registro | Fuente | Tamaño |
|---|---|---|
| Modalidades evaluables | `services/mastery.MASTERY_SKILLS` (`mastery.py:84`) | **9** |
| Destrezas con requisitos | `cefr_matrix.json` v2.1.0 | **8** |
| Canales de evidencia | `MODALITY_CHANNEL` (`skill_state.py:102`) | **7** |

- **Sin canal de evidencia:** `interaction`, `mediation`.
- **Sin requisitos en matriz:** `pronunciation`.
- **Sin competencias declaradas:** `interaction`, `mediation`
  (`skill_axis.py:276-277`).

### 2. Gates declarados

- **Estados:** `not_started → developing → functional → demonstrated`
  (`competence.py:41`).
- **Producción (R5):** `grammar`, `speaking`, `writing` (`competence.py:45`).
- **Apoyo, tope `functional`:** `vocabulary` (`competence.py:50`).
- **Gate espaciado:** `2` muestras × `2` días (`learner_skill.py:59-60`).
- **Ítems de producción:** `speaking`, `writing`, `pronunciation`,
  `controlled_production` (`evidence_depth.py:33`).

### 3. Mínimos de la matriz (medidos)

| Nivel | `minimum_evidence` | `minimum_mastery` (vocabulary/grammar) | `transfer_required` | `novel_required` |
|---|---|---|---|---|
| A1 | 2–3 | 0,70 | 0 | 0 |
| A2 | 3 | 0,70 | 0 | 0 |
| B1 | 3 | 0,70 | 1 | 0 |
| B2 | 4 | 0,75 | 2 | 0 |
| C1 | 5 | 0,80 | 3 | 0 |
| C2 | 6 | 0,85 | 4 | 0 |

La tabla completa (48 filas, nivel × destreza) está en el `.md` generado.

### 4. Línea base sin evidencia (propiedad positiva)

Con el perfil vacío, las **9** modalidades devuelven `state = not_started`,
`demonstrated = False` y `estimated_band = "—"`. Y
`evidence_depth_report("grammar", "A1", 0)` da `depth = "low"` y
`meets_matrix = False`.

**El sistema no afirma nada sin evidencia.** Es la propiedad anti-sobreafirmación
y hay que preservarla.

### 5. El requisito `novel`: medido, y con una corrección al briefing

El briefing de este eje afirmaba que `novel` «no tiene emisor». **La
verificación en código muestra que esa afirmación está desactualizada**: desde
**V3.26** existe un emisor real documentado en `services/speaking.py:861-889`
(`mission_evidence_kind`), que emite `novel` cuando el alumno practica por
primera vez un escenario de **B2 o superior** (`NOVEL_MIN_CEFR = "B2"`), con
anti-bombeo (los reintentos del mismo escenario son `familiar`).

Lo que **sí** se mantiene, y es el hallazgo: la matriz conserva
**`novel_required = 0` en las 48 celdas**, por decisión explícita documentada en
el propio código («mantener `novel_required = 0` y fuera del gate MASTERED»).
Consecuencia medida: **la señal existe y el gate no la exige nunca**.

### 6. El hueco de acreditación (F-K3), medido conductualmente

`skill_state.py:29-32` documenta que una fila de `academy_evidence` **sin
objetivo resoluble** (speaking assessment y misión escriben `objective_id=''`)
entra como INTENTO con su `result` pero **no acredita éxito**, porque el éxito
se decide contra el umbral del objetivo (`Objective.threshold`), y sin objetivo
no hay umbral (`skill_state.py:360-391`).

Verificado con filas sintéticas idénticas salvo el `objective_id`:

| Fila | `objective_id` | `result` | `success` |
|---|---|---|---|
| A | `a1-m01-u01-l01-o01` (real) | 1,0 | **True** |
| B | `""` | 1,0 | **False** |

Es decir: **un acierto perfecto en una misión de speaking no acredita éxito**
si la fila no resuelve objetivo. La frontera es consistente (el Student Model ya
se comportaba así), pero **deja fuera del gate espaciado** a dos de los flujos
de producción oral más importantes del producto.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| 1 | **P1** | **Tres registros con tres tamaños para el mismo concepto** de «destreza evaluable»: 9 modalidades, 8 en matriz, 7 canales. Ninguna estructura es la fuente única. | `mastery.py:84`, `cefr_matrix.json` v2.1.0, `skill_state.py:102` | Unificar en una única taxonomía declarada y derivar los tres registros de ella | Abierto |
| 2 | **P1** | **`interaction` y `mediation` no pueden acreditar evidencia por ninguna vía**: la matriz les exige requisitos en los 6 niveles, pero no tienen canal de evidencia ni competencias declaradas. | `skill_state.py:102` (sin entradas), `skill_axis.py:276-277` (`()`), matriz v2.1.0 | Retirarlas de `MASTERY_SKILLS`/matriz o construir su canal → **Planner 4.0 / V4.0.x** | Abierto |
| 3 | **P2** | **El requisito `novel` está inerte**: `novel_required = 0` en las 48 celdas pese a que el emisor real existe desde V3.26. El gate nunca exige novedad contextual. | `adaptive.py:201` (comentario «reservado»), `speaking.py:861-889`, `test_cefr_matrix.py:88-89` | Reactivar progresivamente `novel_required` (Eje C ya previsto) o declarar el requisito como retirado | Abierto |
| 4 | **P2** | **Filas de speaking assessment y misión no acreditan éxito** al escribir `objective_id=''`: entran como intento pero no cruzan la puerta espaciada ni el gate funcional. Medido: `result 1,0` → `success False`. | `skill_state.py:29-32` y `:360-391`; `test_evidence_invariants.py:62` (objetivo vacío permitido) | Resolver el `objective_id` en el emisor de esas filas (F-K3) | Abierto |
| 5 | **P3** | `pronunciation` está **fuera de la matriz** (sin requisitos) pero **dentro** de `MASTERY_SKILLS` y con corpus y scorer propios. | `mastery-claims.json` → `modalities_without_matrix: ["pronunciation"]` | Constancia documental de la exclusión (coherente con el eje 2) | Abierto |
| 6 | **P3** | Propiedades positivas a preservar: sin evidencia no se afirma nada (9/9 en `not_started`, banda `—`) y `transfer_required` crece monótonamente 0 → 4. | `mastery-claims.json` → `no_evidence_baseline`, `matrix_per_level` | Preservar; son la garantía anti-sobreafirmación | **Correcto** |

## Veredicto

El gate de maestría es **conservador y coherente en su lógica**: exige
producción real (R5), muestra espaciada (2×2) y un mínimo de evidencias que crece
con el nivel; sin evidencia no afirma nada; y `transfer_required` escala de 0 a 4.
Eso es lo correcto y está medido.

Lo que **no** es válido es el supuesto de que las 9 modalidades sean evaluables.
Tres registros distintos describen la misma taxonomía con tamaños distintos
(9/8/7), y **`interaction` y `mediation` no pueden acreditar evidencia por
ninguna vía**: están en la lista de lo evaluable, tienen requisitos en la matriz
y no tienen canal. Además, el requisito `novel` existe en la matriz con valor 0
(el emisor ya existe, la exigencia no), y dos flujos centrales de producción oral
(speaking assessment y misión) **pierden la acreditación** al no resolver el
objetivo de la fila.

Traducido a la pregunta del eje: **«demostrado» es fiable cuando se alcanza**
(los gates son duros), pero **hay destrezas que declaran poder alcanzarlo y no
pueden**, y hay evidencia de producción que se registra sin acreditar.

**Qué no demuestra este eje:** que los umbrales estén bien calibrados. Eso
necesita datos de alumnos reales.

## Regenerar / Verificar

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.audit_dossier mastery-claims
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_mastery_v370.py
```

## Tests que respaldan

`backend/tests/test_ped_mastery_v370.py` (10 tests):

| Test | Qué pinnea |
|---|---|
| `test_mastery_matrix_and_channel_registers_do_not_coincide` | 9 / 8 / 7 y las diferencias exactas |
| `test_interaction_and_mediation_cannot_earn_evidence` | sin canal y sin competencias |
| `test_novel_signal_exists_but_the_matrix_never_requires_it` | emisor V3.26 con `NOVEL_MIN_CEFR == "B2"` y suma `novel_required == 0` |
| `test_transfer_requirement_grows_with_level` | 0, 0, 1, 2, 3, 4 |
| `test_spacing_gate_is_two_samples_two_days` | 2 × 2 |
| `test_no_evidence_means_not_started_and_no_band` | 9/9 `not_started`, banda `—` |
| `test_evidence_depth_without_samples_is_low` | `depth low`, `meets_matrix False` |
| `test_production_skills_are_the_three_declared` | R5 y destrezas de apoyo |
| `test_rows_without_objective_do_not_accredit_success` | measured F-K3 behaviorally |
| `test_pronunciation_has_no_matrix_requirements` | exclusión declarada |
