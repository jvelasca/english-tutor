# Briefing de subagente — V3.70 · Eje 4: validez de la afirmación de maestría

> **Estado:** **PENDIENTE** (V3.70, 2026-09-15). Cuarto eje de la auditoría
> pedagógica. **Solo medición**.
> **Qué es:** el dossier `docs/audit/AD-PED-MAESTRIA.md` más el test
> `backend/tests/test_ped_mastery_v370.py`.
> **Qué NO cierra:** cambiar los umbrales, la matriz CEFR, el gate funcional o
> el spacing gate. Se **mide y declara** si «demostrado» significa lo que dice.
> **Regla dura:** *no se toca `services/**` ni `backend/curriculum/cefr_matrix.json`*.
> **Briefing maestro:** `agentes/v370-auditoria-pedagogica.md`.

## Rol

**Auditor del Student Model.** Dossier `AD` (plantilla
`docs/audit/TEMPLATE.md`) + `test_ped_mastery_v370.py`. Puedes **ampliar**
`backend/tests/golden/pedagogy/` **solo** si el dossier lo justifica, siguiendo
la regla de `backend/tests/golden/README.md` (un golden se edita **solo** tras
re-auditoría, con su id `audit:` y actualizando el README).

## Objetivo

Responder: **¿«demostrado» significa lo que dice?** Es decir: ¿los cuatro
estados de competencia, sus gates y la matriz CEFR describen una realidad
medible, o hay destrezas que nunca podrán alcanzar el estado que declaran?

## Estado de partida ya medido (no lo re-derives: verifícalo y cítalo)

Evidencia en `docs/audit/generated/mastery-claims.json` y `.md`
(`python -m scripts.audit_dossier mastery-claims`).

### Tres registros que deberían coincidir (y no coinciden)

| Registro | Fuente | Tamaño |
|---|---|---|
| Modalidades declaradas | `services/mastery.MASTERY_SKILLS` | **9** |
| Destrezas con requisitos | `backend/curriculum/cefr_matrix.json` (v2.1.0) | **8** |
| Canales de evidencia | `services/skill_state.MODALITY_CHANNEL` | **7** |

- **Sin canal de evidencia: `interaction`, `mediation`.**
- **Sin requisitos en matriz: `pronunciation`** (exclusión declarada a propósito).
- **Sin competencias declaradas: `interaction`, `mediation`**
  (`COMPETENCES_BY_MODALITY` devuelve tupla vacía).

### Gates declarados

- **Estados:** `not_started → developing → functional → demonstrated`.
- **Destrezas de producción** (R5: reconocer ≠ producir):
  `grammar`, `speaking`, `writing`.
- **Destrezas de apoyo** (tope en `functional`): `vocabulary`.
- **Gate espaciado:** `2` muestras × `2` días
  (`learner_skill.OBSERVED_MIN_SAMPLES/OBSERVED_MIN_DAYS`).
- **Tipos de ítem de producción:** `speaking`, `writing`, `pronunciation`,
  `controlled_production`.
- **`novel_required` sumado en toda la matriz: `0`** ⇒ el requisito `novel`
  está **declarado pero inerte** (coincide con la deuda F-K1 ya documentada).
- **`transfer_required` sumado: `80`** (0 en A1/A2, 1 en B1, 2 en B2, 3 en C1,
  4 en C2).

### Mínimos por nivel (patrón medido)

| Nivel | `minimum_evidence` | `minimum_mastery` (vocabulary/grammar) | `transfer_required` | `novel_required` |
|---|---|---|---|---|
| A1 | 2–3 | 0,70 | 0 | 0 |
| A2 | 3 | 0,70 | 0 | 0 |
| B1 | 3 | 0,70 | **1** | 0 |
| B2 | 4 | 0,75 | **2** | 0 |
| C1 | 5 | 0,80 | **3** | 0 |
| C2 | 6 | 0,85 | **4** | 0 |

(La tabla completa — 48 filas, nivel × destreza — está en el `.md` generado y
debe reproducirse en el dossier.)

### Línea base sin evidencia (comportamiento puro, reproducible)

- Las **9** modalidades devuelven `state = not_started`, `demonstrated = False`,
  `estimated_band = "—"`.
- `evidence_depth_report("grammar", "A1", 0)` ⇒ `depth = low`,
  `meets_matrix = False`.

Es decir: **sin evidencia el sistema no afirma nada**, que es la propiedad
correcta. El dossier debe fijarlo como propiedad positiva.

### Huecos ya documentados en código que el dossier debe **verificar**, no asumir

- `services/skill_state.py` documenta que **speaking assessment y speaking
  mission escriben `objective_id=''`** (deuda F-K3): esas filas entran como
  intentos pero **no acreditan éxito** y no cruzan el gate espaciado.
- `novel`: **corrección medida al briefing.** El briefing de este eje afirmaba
  que «`novel` no tiene emisor» (deuda F-K1). **Es falso desde V3.26/F-B1**: el
  emisor real existe (`speaking.mission_evidence_kind`, primera misión B2+ jamás
  practicada; `NOVEL_MIN_CEFR == "B2"`). El hueco real es que
  `novel_required = 0` en las 48 celdas de la matriz por decisión explícita
  documentada en el código, así que el gate **nunca exige** novedad contextual.
  El dossier debe **verificar** esto en código y reportar la versión corregida.
- `interaction` y `mediation` están en `MASTERY_SKILLS` pero **nada escribe su
  evidencia** (coherente con el eje 2).

## Diseño del dossier `docs/audit/AD-PED-MAESTRIA.md`

1. **Alcance** — los 4 estados de `services/competence.py`, el gate funcional,
   los mínimos de `cefr_matrix.json`, el spacing gate, `evidence_depth` y los
   tres registros de modalidades. **NO** se audita el contenido (eje 1), la
   cobertura (eje 2), el feedback (eje 3) ni los instrumentos (eje 5).
2. **Método** — instrumento `mastery-claims`; funciones **puras**
   (`competence_state`, `competence_states`, `evidence_depth_report`) sobre
   entradas fijas; lectura de la matriz; **verificación en código** de las
   rutas que escriben evidencia (`objective_id` vacío, emisor de `novel`).
3. **Evidencia** — las tablas de arriba + la tabla completa de la matriz + la
   línea base sin evidencia + las **citas `archivo:línea`** de los huecos
   verificados.
4. **Hallazgos** — tabla P0/P1/P2/P3. Candidatos ya medidos:
   - **Tres registros con tres tamaños distintos** (9/8/7) para el mismo
     concepto de «destreza evaluable».
   - `novel_required = 0` en **toda** la matriz: requisito declarado e inerte.
   - `interaction` y `mediation`: exigidas por la matriz, **sin canal de
     evidencia y sin competencias** ⇒ **no pueden** alcanzar `functional` ni
     `demonstrated` por ninguna vía.
   - `pronunciation` **no tiene requisitos de matriz** pero sí corpus (120
     ítems) y scorer determinista.
   - `objective_id=''` en speaking assessment/mission ⇒ acreditación perdida.
5. **Veredicto** — 2–3 líneas. Debe distinguir «el gate es demasiado laxo» de
   «la destreza nunca recibe evidencia». Lo segundo es lo medido aquí.
6. **Regenerar / Verificar**.
7. **Tests que respaldan**.

## Tests: `backend/tests/test_ped_mastery_v370.py`

Tests requeridos:

- `test_mastery_matrix_and_channel_registers_do_not_coincide` — afirma los
  tamaños **9 / 8 / 7** y los conjuntos exactos de diferencias
  (`{interaction, mediation}` sin canal; `{pronunciation}` sin matriz).
- `test_interaction_and_mediation_cannot_earn_evidence` — ninguna entrada de
  `MODALITY_CHANNEL` los cubre y sus competencias son vacías ⇒ el test declara
  que **no existe vía** de acreditación.
- `test_novel_requirement_is_inert_in_the_matrix` — `novel_required` sumado
  sobre las 48 celdas es **0**.
- `test_transfer_requirement_grows_with_level` — `transfer_required` es 0 en
  A1/A2, 1 en B1, 2 en B2, 3 en C1 y 4 en C2 (propiedad **correcta**: pínneala).
- `test_spacing_gate_is_two_samples_two_days` — `OBSERVED_MIN_SAMPLES == 2` y
  `OBSERVED_MIN_DAYS == 2`.
- `test_no_evidence_means_not_started_and_no_band` — para las 9 modalidades,
  `competence_states([], "A1")` da `not_started`, `demonstrated False`,
  `estimated_band "—"` (propiedad positiva anti-sobreafirmación).
- `test_evidence_depth_without_samples_is_low` — `evidence_depth_report`
  devuelve `depth == "low"` y `meets_matrix is False` con 0 muestras.
- `test_production_skills_are_the_three_declared` — `PRODUCTION_SKILLS` es
  `("grammar","speaking","writing")` y `SUPPORT_SKILLS` es `("vocabulary",)`.
- (Si el dossier lo justifica) ampliar `tests/golden/pedagogy/` con un caso
  nuevo de la calibración medida, con `audit: "AD-2026-09-15"`, y actualizar
  `backend/tests/golden/README.md`.

## Criterios de salida

1. `docs/audit/AD-PED-MAESTRIA.md` creado con la plantilla completa.
2. `backend/tests/test_ped_mastery_v370.py` creado y **verde**; la batería
   existente de goldens (`test_golden_pedagogy.py`) sigue **verde**.
3. `python -m ruff check .` limpio; `python -m pytest -q` verde con el total
   anterior + los nuevos.
4. `python -m scripts.audit_dossier mastery-claims` reproducible.
5. Cero ficheros de `backend/services/**` o `backend/curriculum/**`
   modificados.

## Fuera de alcance

- Cambiar umbrales, la matriz CEFR, el gate funcional o el spacing gate.
- Crear el emisor de `novel`, arreglar `objective_id=''` o dotar de canal a
  interaction/mediation (todo eso es motor → Planner 4.0 / V4.0.x).
