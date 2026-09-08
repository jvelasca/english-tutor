# v3.24.0 — Calibración de salida del Student Model: MASTERED a lo emisible + nivel estimado anclado

**El plan V3.24 cierra los dos P1 del dossier K (auditoría profunda del Eje 1:
Student Model → Evidence → Mastery → Academy → CEFR, sobre v3.23.0) por
decisión del gerente: (F-K1) el gate MASTERED de Assessment 2.0 se relaja a lo
**emisible** — `familiar×2 + transfer×2 + delayed`, con el evidence_kind `novel`
**reservado** (requisito 0, sin emisor real) — y (F-K2) el nivel estimado se
**ancla** a niveles completados + progreso del tramo actual, eliminando el
rebase ilógico al matricular un nivel nuevo. Los tests e2e del salto A1→A2
(F-K8) se escribieron primero (rojos) y fijan hoy el comportamiento.**

## Qué cambia

- **F-K1 — MASTERED a lo emisible (`novel` reservado).** El dossier K confirmó
  que solo se emiten los kinds `familiar` (`initial`/`practice`), `transfer` y
  `delayed`, mientras que `mastery_evidence_gate` exigía `novel` para MASTERED
  → `mastery_missing: novel` permanente en la escalera Assessment 2.0.
  - `MASTERY_EVIDENCE_REQUIREMENTS` pasa a `initial 1 + practice 2 + transfer 2
    + delayed 1` (`backend/services/assessment_v2.py`); `novel` deja de ser un
    requisito bloqueante del gate.
  - `novel_required = 0` en las **12 celdas macro** de `cefr_matrix.json`
    (listening/speaking/reading/writing en B2, C1 y C2).
  - El kind `novel` queda **reservado** (requisito 0) hasta que exista una
    modalidad que lo emita de verdad; la frontera se documenta en
    `docs/ASSESSMENT_2.md` y la CONSTITUCIÓN (§2.1, §6.1, §6.2, §6.4) sin
    cambiar ninguna regla pedagógica de los estados `DEMONSTRATED`/`MASTERED`
    (la base sigue siendo familiar×2 + transfer×2 + delayed).
- **F-K2 — Nivel estimado anclado (sin rebase al matricular).** El estimado
  vivía en un único nivel con escala `numeric = 1 + 5·overall` no calibrada y
  rebasaba al matricular un nivel nuevo (escenario G4 del dossier: dominar A1
  estimaba **B2**; aprobar el examen A1 devolvía el estimado a **Pre-A1**).
  - `adaptive.estimated_level(profile, *, current_level, completed_levels)`
    ancla ahora el suelo: `floor = numeric(nivel completado más alto)` si hay
    niveles `completed`, o `max(PRE_A1_NUMERIC, numeric(current_level) − 1)` en
    caso contrario, y `numeric = round(min(6.0, floor + progreso), 2)` sobre la
    escala continua **0.5 (Pre-A1) – 6.0 (C2)**. Sin completados, la etiqueta
    nunca supera el `current_level`; con completados, el mínimo es el nivel
    certificado (un alumno con A1 completo nunca se estima por debajo de A1).
  - `build_student_model` (`backend/domain/academy.py`) deriva `current_level`
    y `completed_levels` de las matrículas del usuario
    (`status == "completed"`) y los propaga a `estimated_level` y
    `reassessment_due` (que ahora también los recibe).
  - Consistencia garantizada entre el valor numérico y la etiqueta CEFR
    (ambos se derivan del mismo `numeric` anclado).
- **F-K8 — Tests e2e del salto de nivel (prerequisito).** En
  `test_academy.py`: helper `_dominate_a1` (domina todos los objetivos A1) +
  `test_endpoint_estimated_level_anchored_across_a1_exam` — dominar A1 completo
  estima A1 (nunca ≥ B2) y aprobar el examen A1 (→ matrícula A2) mantiene el
  estimado en A1 con `numeric == 1.0` (nunca Pre-A1). Tests escritos primero
  (rojos sobre v3.23.0), hoy verdes.
- **Contratos.** Ningún schema/endpoint cambia de forma: `estimated_level`/
  `reassessment_due` ganan parámetros internos de contexto (derivados por
  `build_student_model`), y el contrato del Student Model (`estimated_level`/
  `estimated_numeric`/`overall_ability`) se mantiene con la semántica
  recalibrada. El único piso nuevo visible: usuario vacío → Pre-A1
  (`numeric 0.5`), coherente con la escala.

## Técnica

- Backend (versión de app `3.23.0 → 3.24.0`, fuente única `backend/config.py`):
  - `services/assessment_v2.py`: constantes `MASTERY_EVIDENCE_REQUIREMENTS` y
    `mastery_evidence_gate` sin `novel`; docstrings.
  - `curriculum/cefr_matrix.json`: `novel_required = 0` en las 12 celdas macro.
  - `services/adaptive.py`: `CEFR_NUMERIC` (0.5–6.0), `estimated_level` y
    `reassessment_due` con `current_level` + `completed_levels`, `numeric`
    anclado, docstrings (F-K1/F-K2).
  - `domain/academy.py`: `build_student_model` deriva y propaga los niveles.
  - `services/evidence_depth.py`: docstrings (novel reservado).
  - Re-apuntado de tests y golden fixture (`thresholds.json`): la semántica
    OLD de la escala (piso 1.0) y del gate (`novel` requerido) pasa a la nueva
    (piso 0.5 / `novel` no requerido).
- Frontend: **sin cambios de código** (contratos de respuesta intactos).
- Docs: `PLAN.md`, `CHANGELOG.md`, `docs/ASSESSMENT_2.md`,
  `docs/CONSTITUCION-PEDAGOGICA.md`, `docs/RELEVO.md`,
  `agentes/v324-calibracion-salida.md` (briefing), dossier K
  (`docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md`).

## Tests

- Backend: **1457 pytest en verde** (nuevos casos del gate sin `novel` con
  `familiar×2 + transfer×2 + delayed`, readiness B2 con transfer sin `novel`,
  matriz con `novel_required == 0`, estimado anclado por niveles completados,
  sin completados nunca reclamar nivel siguiente, e2e del salto A1→A2);
  `ruff check .` limpio.
- Eje 1 (dossier K): **G1 311 + G2 329** (640, +2 tests e2e).
- Frontend: sin cambios — vitest **450 passed** (57 archivos); `tsc --noEmit`
  y `vite build` OK (estado v3.23.0 reproducido).
- `scripts/check_release_consistency.py` exit 0 (3.24.0).

## Fuera de alcance (fronteras documentadas)

- **F-K3** (doble vía speaking assessment/misión y `cefr_target` persistido),
  **F-K4** (`band` por destreza → `estimated_band`), **F-K5** (colisión
  semántica `transfer`/`retention` léxica vs académica), **F-K6** (historia
  fina de eventos del modelo léxico) y **F-K7** (renombrado
  `appearances`/`exposures`) — P2/P3 del dossier K, candidatos del siguiente
  incremento.
- Emisor real del kind `novel` (uso en contexto nunca practicado): no existe en
  v3.24; `novel` permanece reservado con requisito 0 y la frontera está
  documentada en `ASSESSMENT_2.md` y la CONSTITUCIÓN.
