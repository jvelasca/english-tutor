# AE · Auditoría de instrumentos de nivelación (V3.70 · Eje 5)

> **Release:** V3.70 (auditoría pedagógica + CEFR) · **Eje 5 de 5**
> **Fecha:** 2026-09-15 · **Instrumento:**
> `python -m scripts.audit_dossier assessment-instruments` (solo lectura)
> **Evidencia cruda:** `docs/audit/generated/assessment-instruments.{md,json}`

## Alcance

Los instrumentos con los que el producto decide **en qué nivel está un alumno** y
**si ha superado un nivel**:

- **placement** `placement-v1` (`services/academy.py`, `backend/curriculum/assessments.json`);
- **exámenes finales de nivel** (`assessments.exams`);
- **bancos de remediación** (`assessments.remediation`);
- **gate de unidad** (`services/course.py`);
- **umbrales de banda CEFR** de los tres estimadores (`services/adaptive.py`,
  `services/academy.py`, `services/cefr.py`) y la escalera de sub-bandas
  (`services/cefr_descriptors.py`).

**No se audita** el contenido de los ítems (eje 1), la cobertura (eje 2), el
feedback (eje 3) ni la maestría (eje 4). **No se audita** la validez empírica del
placement con alumnos reales: requiere tráfico (`docs/audit/PARKED.md`).

## Método

1. Instrumento `assessment-instruments`, de solo lectura.
2. **Cota analítica del modelo declarado**, no simulación: el placement declara
   un modelo logístico de un parámetro (1PL, `academy._p_correct`). Para un ítem
   1PL la información es `p(1-p) ≤ 0,25`, de modo que tras `n` ítems
   `SE ≥ 1/sqrt(n · 0,25)`. Con el máximo declarado (`n = 8`) la cota es
   **0,7071**.
3. **Rejilla determinista** de 0,5 a 6,0 (paso 0,25) para comparar los tres
   estimadores de banda y comprobar qué bandas puede emitir cada uno.

## Evidencia

### 1. Placement (`placement-v1`)

| Métrica | Valor |
|---|---|
| Ítems en el banco | **24** |
| Reparto por dificultad | **4 por cada nivel 1..6** (sin huecos) |
| Destrezas cubiertas | grammar, listening, pronunciation, reading, speaking, vocabulary, writing (**7**) |
| `MAX_PLACEMENT_ITEMS` | 8 |
| `PLACEMENT_MIN_ITEMS` | 4 |
| `PLACEMENT_SE_THRESHOLD` | 0,5 |
| **Mejor `SE` alcanzable con 8 ítems** | **0,7071** |
| **¿Umbral alcanzable?** | **No** |
| Correcta = opción más larga **única** | 12/24 (**50,0 %**) |
| Correcta = la más larga **o empatada al máximo** | 18/24 (**75,0 %**) |
| Reparto de posiciones | 0: 6 · **1: 17 (70,8 %)** · 2: 1 · **3: 0** |

**El criterio de parada por precisión no puede dispararse**: pide `SE < 0,5` y la
mejor cota con 8 ítems es `0,7071`. El placement siempre agota el presupuesto de
ítems (o para por `PLACEMENT_MIN_ITEMS`, que es otro criterio).

### 2. Exámenes finales

| Nivel | Ítems | Destrezas | `min_per_skill` | Dificultades de los ítems |
|---|---|---|---|---|
| A1 (`a1`) | 10 | grammar, listening, reading, vocabulary | 0,75 | **1 (los 10)** |
| B1 (`b1`) | 12 | grammar, listening, reading, vocabulary | 0,75 | **1 (los 12)** |

- **Niveles SIN examen final: A2, B2, C1 y C2** — cuatro de los seis niveles de
  `CEFR_ORDER`.
- El examen de **B1 tiene todos sus ítems en dificultad 1**, exactamente igual
  que el de A1: como instrumento **no se escala** entre A1 y B1.

### 3. Remediación y gate de unidad

| Banco | Ítems |
|---|---|
| `grammar` | 6 |
| `vocabulary` | 6 |
| **`reading`** | **3** |
| `listening` | 5 |
| `speaking` | 6 |

- Secciones de unidad (7): `vocabulary`, `grammar`, `listening`, `speaking`,
  `interaction`, `review`, `assessment`.
- Umbrales de gate: `vocabulary 0,8 · grammar 0,8 · listening 0,75 ·
  speaking 0,7`.

### 4. Umbrales de banda

- Los **tres** estimadores (`adaptive.numeric_to_level`, `academy.theta_to_level`,
  `cefr.heuristic_band`) coinciden en **toda** la rejilla 0,5–6,0:
  **0 desacuerdos**. Es una **propiedad positiva** (misma semántica en tres
  sitios) y a la vez un **riesgo de mantenimiento** (tres implementaciones del
  mismo corte, `adaptive.py:52`, `academy.py:1033`, `cefr.py:58`).
- La escalera `cefr_descriptors.band_for_numeric` **puede** emitir `a2+`, `b1+`,
  `b2+` y `pre-a1`; **ningún estimador emite sub-bandas**: son
  `A1..C2` discretos siempre.
- Ningún estimador produce `pre-a1`, aunque `PRE_A1_NUMERIC = 0.5` existe
  (`adaptive.py:49`).

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| 1 | **P1** | **El criterio de parada por precisión del placement es inalcanzable**: exige `SE < 0,5` y la mejor cota con los 8 ítems declarados es `0,7071`. La constante existe y el criterio nunca puede dispararse. | `academy.py:989-995`, cota 1PL `1/sqrt(8·0,25)` | Elevar `MAX_PLACEMENT_ITEMS` (≥ 16 para `SE ≤ 0,5`) o rebajar el umbral a un valor alcanzable, y **declarar** cuál de los dos criterios manda | Abierto |
| 2 | **P1** | **El examen de B1 tiene los 12 ítems en dificultad 1, igual que el de A1**: como instrumento no discrimina por encima de A1. | `assessment-instruments.json` → `exams.B1.difficulties {1: 12}` | Recalibrar el banco de B1 con dificultades ≥ 3 o declarar el examen como «de umbral mínimo» y no como certificación de nivel | Abierto |
| 3 | **P1** | **Cuatro de los seis niveles no tienen examen final** (A2, B2, C1, C2): el producto certifica internamente A1 y B1 y no tiene instrumento de cierre para el resto. | `assessment-instruments.json` → `levels_without_exam` | Escribir los exámenes de A2/B2/C1/C2 → **V4.0.x** | Abierto |
| 4 | **P2** | El placement **mide reconocimiento o meta-lenguaje** para listening, speaking, writing y pronunciation: lo declara el propio modelo («miden conciencia de la destreza, no su ejecución»). No captura audio ni producción libre. | `curriculum.py:375-382` (docstring de `PlacementTest`) | Declararlo en la UI del placement para no prometer una nivelación de producción que el instrumento no hace | Abierto |
| 5 | **P2** | **Sesgo de forma del placement**: la opción correcta es la más larga (única) en el **50 %** de los 24 ítems y la más larga o empatada al máximo en el **75 %**; el **70,8 %** están en la posición 1 y la posición 3 **nunca** es correcta. Un alumno que siempre elija la opción más larga acierta tres cuartas partes del banco. | `assessment-instruments.json` → `placement.mc` | Reequilibrar posiciones y longitudes del banco | Abierto |
| 6 | **P2** | **Los umbrales de banda están triplicados** (tres implementaciones del mismo corte) y las **sub-bandas `+` que la escalera declara no las emite ningún estimador**, igual que `pre-a1`. | `adaptive.py:52`, `academy.py:1033`, `cefr.py:58`, `cefr_descriptors.py:34-45` | Un solo módulo de bandas; decidir si las sub-bandas entran en la estimación o se retiran de la escalera | Abierto |
| 7 | **P3** | El banco de remediación de **`reading` tiene 3 ítems**, el más pequeño, y reading es justo la destreza sin scorer propio (eje 2) y sin canal de corrección (eje 3). | `assessments.remediation`, `assessment-instruments.json` | Ampliar remediación de reading junto con su scorer | Abierto |
| 8 | **P3** | Propiedad positiva a preservar: los **tres estimadores coinciden** (0 desacuerdos en la rejilla 0,5–6,0) y el banco de placement **no tiene huecos de dificultad** (4 ítems por nivel 1..6). | `assessment-instruments.json` → `band_thresholds.disagreements: []`, `placement.difficulties` | Preservar; si se unifican los umbrales, mantener la equivalencia | **Correcto** |

## Veredicto

El placement está **bien construido como banco** (24 ítems, 4 por cada nivel de
dificultad, sin huecos) y sus umbrales de banda son **coherentes** entre los tres
estimadores. Pero tiene **dos defectos de instrumento** medidos: su criterio de
parada por precisión **no puede dispararse** con el presupuesto de ítems
declarado, y su forma tiene sesgo (la correcta es la más larga única en la mitad
del banco y la más larga o empatada al máximo en tres cuartas partes; la posición
3 nunca es correcta).

Los exámenes finales son el hueco mayor: **cuatro de seis niveles no tienen
examen**, y el de B1 **no se escala** respecto al de A1 (todos sus ítems en
dificultad 1). Es decir: el producto puede decir «estás en A2» con el placement,
pero **no puede certificar** A2, B2, C1 ni C2, ni discriminar de verdad en B1.

Y la parte de bandas: la semántica es consistente (bueno) pero está
triplicada (frágil) y declara sub-bandas y `pre-a1` que nadie emite (deuda de
coherencia entre lo declarado y lo producido).

**Qué no demuestra este eje:** que el placement acierte con un alumno real. Eso
requiere comparar la banda estimada con una evaluación externa, y es
precisamente lo que falta (`docs/audit/PARKED.md`).

## Regenerar / Verificar

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.audit_dossier assessment-instruments
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_instruments_v370.py
```

## Tests que respaldan

`backend/tests/test_ped_instruments_v370.py` (10 tests):

| Test | Qué pinnea |
|---|---|
| `test_placement_stop_rule_is_unreachable_with_the_declared_model` | cota 0,7071 > 0,5 y las tres constantes |
| `test_placement_bank_has_four_items_per_difficulty` | 24 ítems, 4 por dificultad 1..6 |
| `test_placement_has_form_bias` | 12 únicas / 18 con empates, posición 3 nunca correcta |
| `test_b1_exam_does_not_scale_above_a1_exam` | ambas dificultades planas en 1 |
| `test_only_a1_and_b1_have_final_exams` | y los cuatro niveles sin examen |
| `test_exam_min_per_skill_is_declared` | 0,75 en los dos exámenes |
| `test_remediation_banks_are_declared_and_reading_is_the_smallest` | 6, 6, 3, 5, 6 |
| `test_unit_gate_thresholds_are_pinned` | umbrales y 7 secciones |
| `test_three_band_estimators_agree_on_the_whole_grid` | 0 desacuerdos (propiedad positiva) |
| `test_plus_bands_are_declared_but_never_emitted` | `a2+`, `b1+`, `b2+` en la escalera y fuera de la salida |
