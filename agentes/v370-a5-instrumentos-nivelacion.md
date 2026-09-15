# Briefing de subagente — V3.70 · Eje 5: instrumentos de nivelación

> **Estado:** **PENDIENTE** (V3.70, 2026-09-15). Quinto eje de la auditoría
> pedagógica. **Solo medición**.
> **Qué es:** el dossier `docs/audit/AE-PED-INSTRUMENTOS.md` más el test
> `backend/tests/test_ped_instruments_v370.py`.
> **Qué NO cierra:** ampliar el banco de placement, escribir exámenes B2/C1/C2,
> unificar los umbrales de banda ni emitir sub-bandas `+`. Todo eso se
> **declara**.
> **Regla dura:** *no se toca `backend/curriculum/assessments.json` ni
> `services/academy.py`/`adaptive.py`/`cefr.py`*.
> **Briefing maestro:** `agentes/v370-auditoria-pedagogica.md`.

## Rol

**Auditor de instrumentos.** Dossier `AE` (plantilla `docs/audit/TEMPLATE.md`) +
`test_ped_instruments_v370.py`. No modifica `backend/curriculum/**` ni
`backend/services/**`.

## Objetivo

Responder: **¿son suficientes y coherentes los instrumentos de nivelación?**
Placement adaptativo, exámenes finales de nivel, bancos de remediación, gate de
unidad y los umbrales de banda CEFR.

## Estado de partida ya medido (no lo re-derives: verifícalo y cítalo)

Evidencia en `docs/audit/generated/assessment-instruments.json` y `.md`
(`python -m scripts.audit_dossier assessment-instruments`).

### Placement (`placement-v1`)

- **24 ítems** en el banco, con **4 ítems por nivel de dificultad (1..6)** —
  reparto perfecto.
- Sesión: `MAX_PLACEMENT_ITEMS = 8`, `PLACEMENT_MIN_ITEMS = 4`,
  `PLACEMENT_SE_THRESHOLD = 0.5`.
- **Hallazgo fuerte (analítico, 1PL):** el máximo de información de un ítem
  logístico es `p(1-p) ≤ 0.25`, así que con 8 ítems el error estándar **no puede
  bajar de** `1/sqrt(8 × 0.25) = 0.7071`. Como `0.7071 > 0.5`, la parada
  adaptativa por precisión es **INALCANZABLE**: el placement siempre agota los 8
  ítems (o para por otras razones). `se_threshold_reachable = False`.
- **Sesgo de forma:** la opción correcta es la más larga en **12 de 24 ítems
  (50,0 %)**.

### Exámenes finales (solo dos, y no en los niveles que la escalera declara)

| Nivel | Ítems | Destrezas | `min_per_skill` |
|---|---|---|---|
| A1 | 10 | grammar, listening, reading, vocabulary | 0,75 |
| B1 | 12 | grammar, listening, reading, vocabulary | 0,75 |

- **Niveles SIN examen final: A2, B2, C1, C2** — es decir, **cuatro de los seis
  niveles** de `CEFR_ORDER` no tienen instrumento de cierre.

### Remediación y gate de unidad

- Bancos de remediación: `grammar` 6 · `vocabulary` 6 · `reading` **3** ·
  `listening` 5 · `speaking` 6.
- Secciones de unidad (7): `vocabulary, grammar, listening, speaking,
  interaction, review, assessment`.
- Umbrales de gate: `vocabulary 0.8 · grammar 0.8 · listening 0.75 ·
  speaking 0.7`.

### Umbrales de banda CEFR

- Los **tres** estimadores (`adaptive.numeric_to_level`,
  `academy.theta_to_level`, `cefr.heuristic_band`) producen el **mismo** nivel en
  toda la rejilla 0,5–6,0 ⇒ **0 desacuerdos**. Es una **propiedad positiva** y
  el dossier debe fijarla: la duplicación es un riesgo de **mantenimiento**, no
  un defecto actual.
- La escalera `cefr_descriptors.band_for_numeric` **sí** puede emitir las
  sub-bandas `a2+`, `b1+`, `b2+`; **ningún estimador las emite nunca**
  (`plus_bands_emitted_by_estimators = []`), y `cefr_descriptors.CEFR_LADDER`
  declara además `pre-a1`, que ningún estimador produce.

## Diseño del dossier `docs/audit/AE-PED-INSTRUMENTOS.md`

1. **Alcance** — placement (`assessments.placement`, `services/academy.py`),
   exámenes finales (`assessments.exams`), remediación, gate de unidad
   (`services/course.py`) y los umbrales de banda de los tres estimadores.
   **NO** se audita el contenido de los ítems (eje 1), la cobertura (eje 2), el
   feedback (eje 3) ni la maestría (eje 4).
2. **Método** — instrumento `assessment-instruments`; el argumento del SE es un
   **cota analítica del modelo 1PL declarado** (`_p_correct`), **no** una
   simulación: hay que decirlo así en el dossier.
3. **Evidencia** — las tablas de arriba + el reparto de dificultades del
   placement + el sesgo de forma + la rejilla de bandas.
4. **Hallazgos** — tabla P0/P1/P2/P3. Candidatos ya medidos:
   - **La parada por precisión del placement es inalcanzable** con 8 ítems bajo
     el modelo declarado (la constante existe, el criterio no puede dispararse).
   - **Cuatro de seis niveles sin examen final** (A2, B2, C1, C2).
   - **Sesgo de forma del placement**: correcta = opción más larga en el 50 %.
   - **Umbrales de banda triplicados** (tres implementaciones del mismo corte) y
     **sub-bandas `+` que la escalera declara y ningún estimador emite**.
   - Banco de remediación de `reading` con **3 ítems** (el más pequeño, y reading
     es justo la destreza sin scorer propio — cruzar con el eje 2).
5. **Veredicto** — 2–3 líneas distinguiendo «el instrumento es escaso» de «el
   instrumento es incoherente» (aquí hay de ambas cosas: escasez de exámenes,
   incoherencia del criterio de parada y de las bandas).
6. **Regenerar / Verificar**.
7. **Tests que respaldan**.

## Tests: `backend/tests/test_ped_instruments_v370.py`

Tests requeridos:

- `test_placement_stop_rule_is_unreachable_with_the_declared_model` — calcula la
  cota `1/sqrt(MAX_PLACEMENT_ITEMS × 0.25)` y afirma
  `> PLACEMENT_SE_THRESHOLD`; además
  `academy.MAX_PLACEMENT_ITEMS == 8`, `PLACEMENT_MIN_ITEMS == 4`,
  `PLACEMENT_SE_THRESHOLD == 0.5`.
- `test_placement_bank_has_four_items_per_difficulty` — 24 ítems y 4 por nivel
  de dificultad 1..6 (propiedad positiva: sin huecos de dificultad).
- `test_placement_has_form_bias` — la opción correcta es la más larga en al
  menos la mitad del banco (afirma el hecho medido; si se reequilibra, el test
  falla y obliga a revisar el hallazgo).
- `test_only_a1_and_b1_have_final_exams` — `set(exams) == {"a1","b1"}` y los
  niveles sin examen son exactamente `{"A2","B2","C1","C2"}`.
- `test_exam_min_per_skill_is_declared` — `min_per_skill == 0.75` en los dos
  exámenes.
- `test_remediation_banks_are_declared_and_reading_is_the_smallest` — las cinco
  claves y sus tamaños (6, 6, **3**, 5, 6).
- `test_unit_gate_thresholds_are_pinned` — `UNIT_GATE_THRESHOLDS` es
  `{vocabulary 0.8, grammar 0.8, listening 0.75, speaking 0.7}` y
  `UNIT_SECTIONS` tiene 7 secciones.
- `test_three_band_estimators_agree_on_the_whole_grid` — para la rejilla
  0,5–6,0 los tres estimadores coinciden (propiedad positiva).
- `test_plus_bands_are_declared_but_never_emitted` — `a2+`, `b1+`, `b2+` están
  en `CEFR_LADDER` y ninguno aparece en la salida de los tres estimadores.

## Criterios de salida

1. `docs/audit/AE-PED-INSTRUMENTOS.md` creado con la plantilla completa.
2. `backend/tests/test_ped_instruments_v370.py` creado y **verde**.
3. `python -m ruff check .` limpio; `python -m pytest -q` verde con el total
   anterior + los nuevos.
4. `python -m scripts.audit_dossier assessment-instruments` reproducible.
5. Cero ficheros de `backend/curriculum/**` o `backend/services/**`
   modificados.

## Fuera de alcance

- Ampliar el banco de placement, escribir exámenes A2/B2/C1/C2, unificar los
  umbrales de banda o emitir sub-bandas `+`.
- Auditar la validez empírica del placement con alumnos (requiere tráfico;
  `docs/audit/PARKED.md`).
