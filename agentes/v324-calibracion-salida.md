# V3.24 — Calibración de salida del Student Model (F-K1 relajar + F-K2 anclaje + F-K8)

## Rol

Backend de dominio + tests + higiene documental. Sin frontend salvo verificación de que
ninguna UI asume la escala antigua.

## Objetivo

Cerrar los dos hallazgos **P1** del dossier
`docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md` (Eje 1, v3.23.0) y su prerequisito
de cobertura **F-K8**:

- **F-K1**: el evidence_kind `novel` no tiene emisor, pero `mastery_evidence_gate`
  (MASTERED), la readiness B2+ de `cefr_matrix.json` (`novel_required`) y el grafo lo
  exigen → la escalera Assessment 2.0 muestra `mastery_missing: novel` para siempre y
  MASTERED/readiness B2+ son inalcanzables por vía real. **Decisión (b): relajar a lo
  emisible** (familiar×2 + transfer×2 + delayed) y dejar `novel` **reservado**.
- **F-K2**: `estimated_level` proyecta `numeric = 1 + 5·overall` del nivel actual al
  eje CEFR absoluto → dominar A1 estima **B2** y aprobar el examen A1 (matricular A2)
  devuelve el estimado a **Pre-A1**. **Decisión (a): anclar la escala a los niveles
  completados + progreso en el tramo actual** (sin saltos ni caídas al pasar nivel).
- **F-K8**: no hay test e2e del salto A1→A2; añadirlos (tests-first, fallan hoy).

## Contexto

- Release base `3.23.0` (main `bb3f253`), versión declarada en `backend/config.py`.
- Gates hoy en verde: pytest total 1455 · baterías Eje 1 G1 310 + G2 328 · vitest 450.
- Fuentes: dossier K (`docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md`, hallazgos F-K1/F-K2/F-K8,
  tablas §Hallazgos y veredicto), `docs/RELEVO.md` sección 38, `docs/ASSESSMENT_2.md`
  (regla MASTERED), `services/adaptive.py`, `services/assessment_v2.py`,
  `domain/academy.py`, `curriculum/cefr_matrix.json`.
- Fronteras que NO se tocan: kind `novel` se conserva como kind válido (invariantes,
  conteos, `evidence_by_kind`) pero ningún gate lo exige; `F-K3/F-K4` y los P2 quedan
  fuera de alcance.

## Tarea detallada

### Fase 0 — test que fija F-K8/F-K2 (e2e, hoy RED)

En `backend/tests/test_academy.py` (junto a los tests del Student Model) añadir:

1. Helper `_dominate_level_a1(client, user)` — POST `/api/academy/objective/assessment`
   con todas las respuestas correctas por objetivo de A1, `minimum_attempts` veces por
   objetivo, en orden curricular (desbloqueo lineal). No requiere matrícula.
2. `test_endpoint_estimated_level_after_dominating_a1_stays_a1` (F-K2a / K-C12 del dossier):
   tras dominar A1 completo → GET `/api/academy/student-model`:
   `estimated_level == "A1"` y `estimated_numeric < 2.0` (hoy falla: B2 / ~3.78).
3. `test_endpoint_estimated_level_does_not_drop_after_exam` (F-K2b / K-C11): tras dominar
   A1 y aprobar `/api/academy/exam/a1/submit` (todas correctas) → matrícula A2 (revisar
   `/api/academy/enrollment`) y GET student-model: `estimated_level == "A1"` y
   `estimated_numeric == 1.0` (hoy falla: Pre-A1 / 1.0+cero evidencia).

### Fase 1 — test que fija F-K1 (hoy RED)

- `backend/tests/test_assessment_v2.py::test_mastery_evidence_gate_requires_full_ladder`:
  el gate **solo con kinds emitibles** `{familiar:2, transfer:2, delayed:1}` → `met=True`,
  `missing=[]`; con `transfer:1` → `missing=["transfer"]`; `novel` jamás en `missing`.
- `backend/tests/golden/assessment/thresholds.json` (`mastery_gate_cases`): re-apuntar
  los 3 casos a la semántica nueva (met sin `novel`, `gate-missing-transfer`, sin
  `novel` en missing). Anotar en `description` la justificación (dossier K F-K1).
- `backend/tests/test_adaptive.py::test_readiness_b2_blocked_without_novel`: sustituir por
  (a) B2 listening con `{transfer:2, novel:0}` → `ready=True`, `novel_required==0`,
  `transfer_required==2`; (b) caso bloqueado solo por `transfer:1`.
- `backend/tests/test_cefr_matrix.py::test_requirements_for_c1_and_c2_are_declared`:
  `c2.novel_required == 0` (y `c1.transfer_required == 3` intacto).

### Fase 2 — implementar F-K2

- `backend/services/adaptive.py::estimated_level(profile, *, current_level="A1",
  completed_levels=())`:
  - Suelo (base): con `completed_levels` → `CEFR_NUMERIC[mayor completado]`; sin ellos →
    `max(0.5, CEFR_NUMERIC[current_level] - 1.0)` (A1 → 0.5, centro Pre-A1).
  - `numeric = round(min(6.0, base + clamp01(overall_cefr_score)), 2)`.
  - Etiqueta: sin completados y sin evidencia (o `overall <= 0`) → `Pre-A1`; en otro caso
    `numeric_to_level(numeric)` y, **sin completados**, la etiqueta nunca supera
    `current_level` (no se afirma el nivel siguiente sin certificación previa).
  - Docstring: la escala pasa a expresar "nivel anclado (certificados) + progreso del
    tramo actual", no una proyección lineal absoluta.
- `adaptive.reassessment_due(..., current_level="A1", completed_levels=())`: aceptar y
  propagar el contexto al `estimated_level` interno (mismo comportamiento en defaults).
- `backend/domain/academy.py::build_student_model`: derivar `completed_levels` de
  `academy_repo.list_enrollments` (rows con `status == "completed"` → `level`) y pasar
  `current_level=lv.level` + `completed_levels` a `estimated_level` y a `reassessment_due`.
- Re-apuntar tests puros de escala en `backend/tests/test_adaptive.py`
  (`test_estimated_level_*`): el usuario vacío queda `Pre-A1` con `numeric == 0.5`; los
  perfiles con mastery alto pasan contexto (`current_level`, `completed_levels`) para
  probar el anclaje (p. ej. completado B1 + nivel B2 alto → `numeric >= 4.0`).

### Fase 3 — implementar F-K1

- `backend/services/assessment_v2.py`:
  - `MASTERY_EVIDENCE_REQUIREMENTS = {"initial": 1, "practice": 2, "transfer": 2,
    "delayed": 1}` con comentario: `novel` reservado sin emisor (frontera), requisito 0.
  - Docstrings (cabecera del módulo y `mastery_evidence_gate`): MASTERED = familiar×2 +
    transfer×2 + delayed; `novel` reservado.
- `backend/curriculum/cefr_matrix.json`: `novel_required: 0` en las 12 celdas macro
  (B2/C1/C2 × listening/speaking/reading/writing). No tocar `transfer_required`.
- `backend/services/adaptive.py` (readiness): docstrings/comentarios que citen
  transfer/novedad → transferencia (transfer×n) con `novel` reservado; el código lee
  `req.novel_required` (queda 0) sin cambios funcionales.
- `backend/services/evidence_depth.py`: sin cambio de código (lee matriz); revisar
  docstrings si mencionan "transferencia/novedad".
- `docs/ASSESSMENT_2.md` (regla MASTERED): tabla → transfer `≥ 2`, fila `novel` marcada
  como reservada (requisito 0, sin emisor, frontera V3.24).

### Fase 4 — re-apuntar lectores de la escala antigua

- `backend/tests/test_academy.py:1440` (ladder usuario vacío): `estimated_numeric == 0.5`
  (banda sigue `pre-a1`).
- `backend/tests/test_profile.py:105`: cota inferior `overall_ability` 1.0 → 0.5.
- Correr la suite completa y re-apuntar cualquier otro test que fije la semántica OLD
  (justificando cada cambio; no "pintar de verde" a ciegas).

### Fase 5 — baterías

- Backend: pytest total, G1+G2 del dossier K (ver comandos al pie del dossier), ruff.
- Frontend: vitest + `tsc` + `vite build` (no debería haber cambios; verificar que
  `TrayectoriaTab`/`JourneyScreen`, que usan `estimated_numeric` solo para posicionar en
  la escalera 0..6, siguen verdes).
- `check_release_consistency` (la versión sigue `3.23.0` hasta el cierre del release).

## Criterios de aceptación

- Con kinds **solo emitibles** (familiar/transfer/delayed) MASTERED es alcanzable y
  `mastery_missing` nunca contiene `novel`.
- Readiness B2+ concluye `ready` con transfer requerida y `novel_required == 0`.
- Reproducción G4 corregida: dominar A1 no estima ≥ B2; aprobar A1 mantiene estimado A1
  (sin Pre-A1). El estimado es monótono a través del salto A1→A2 y coherente entre
  `estimated_numeric` y la etiqueta/banda.
- Suite backend verde + ruff + frontend sin regresiones.

## Restricciones

- No tocar CONSTITUCIÓN (R8/R9 siguen propuesta abierta).
- No crear un emisor de `novel`; no borrar el kind del esquema/invariantes.
- No tocar F-K3/F-K4 ni el resto del backlog de la sección 38.
- No cambiar la versión declarada (`3.23.0`) ni abrir release hasta cerrar el incremento.
- Frontend: ningún cambio de código (salvo que una prueba lo exija).

## Salida esperada

- Dif de código (services + domain + matriz) y de tests (nuevos + re-apuntados con su
  justificación).
- `PLAN.md` y `docs/RELEVO.md` actualizados (estado de V3.24), y nota breve de cierre
  si se cierra el incremento.
