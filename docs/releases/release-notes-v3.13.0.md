# v3.13.0 — Calibración de evidencia pedagógica

**Calibración de evidencia pedagógica: del "¿está implementada la actividad?" al "¿la evidencia demuestra competencia?".**

## Qué cambia

La iteración V3.13 no añade actividades nuevas: **recalibra el modelo pedagógico** que cerró la auditoría de V3.8 y lo fija en un único documento normativo (`docs/CONSTITUCION-PEDAGOGICA.md`) con **Reglas inmutables R1–R7** (Practice≠Mastery, Mastery≠Certificación CEFR, Vocabulary≠nivel, One skill≠Overall, Recognition≠Production, Éxito≠Retención, Muestra pequeña≠Competencia), **§6.4 evidence depth** y **§7 por modalidades de evidencia**:

- **Evidence depth por destreza/nivel**: cada competencia clasifica su evidencia formal en bandas **LOW / MEDIUM / HIGH** comparando las muestras reales contra los mínimos de `backend/curriculum/cefr_matrix.json` (`minimum_evidence`, transfer/novel, evidencia retardada). Se expone en `/api/profile` junto a `competence_states`. La evidencia de `academy_evidence` se atribuye a nivel desde ahora (retrocompatible).
- **Claims honestos para bancos cortos**: `stats` por nivel incluyen `bank_size` y `evidence_depth`. Los bancos de ≤ 12 checks (Grammar B2 y C2) muestran la etiqueta **"practice coverage · evidence depth LOW"** en lugar de invitar a leer competencia, y el techo `functional` de la ruta se mantiene: la práctica nunca certifica.
- **Suelo de "demostrado" por destreza**: `demonstrated` exige ahora gate funcional **y** `minimum_evidence` de la matriz **y** retención retardada estable ≥ 7 días; en las destrezas productivas (grammar/speaking/writing) exige además **muestras de producción** — solo MC de reconocimiento jamás demuestra. Vocabulary es condición de apoyo (§3) y queda techado en `functional`.
- **`current_level` no mecánico**: deja de ser "primer nivel cuyo banco no está 100% dominado"; es una **sugerencia de material** y, con todo dominado, elige por repaso pendiente (`review_due`). La UI nunca lo lee como banda CEFR del alumno.
- **Grammar en 3 niveles (R5)**: nuevos ítems **`controlled_production`** en el currículo (A2–C1, ~6-10 por nivel): prompt con hueco + respuestas aceptadas y corrección **determinista por normalización** (sin LLM) sobre el motor compartido de rutas quiz. La UI los sirve como *"type the answer"* con feedback y revelación de lo esperado.
- **Cross-skill evidence (prototipo B1)**: registro de estructuras que cruza la misma estructura por **grammar recognition / production / listening / speaking / transfer**; matriz por estructura con endpoint `/api/cross-skill` y panel en Grammar B1.
- **Golden pedagogical dataset**: `backend/tests/golden/pedagogy/evidence_depth_cases.json` + `test_golden_pedagogy.py` congelan la calibración auditada para que los invariantes no regresionen.
- **LearnRoutePage compartido (V3.13 P2.1)**: `frontend/src/features/routes/QuizRoutePage.tsx` unifica en un shell config-driven las páginas de ruta de Grammar, Vocabulary, Pronunciation, Conversation y Speaking (header + ejercicio + mapa CEFR A1–C2 + panel de nivel + modos + gate + assessment formal), con la máquina de sesión consolidada en `routeSession.ts`. **Listening no migra por diseño**: es la única práctica del hub servida dentro del runner `PracticeView` del workspace, no una página de ruta standalone.
- **Parity i18n automática**: `frontend/src/utils/i18n.parity.test.ts` garantiza claves `en`/`es` no vacías, sin duplicados y sin claves usadas sin resolver.

## Técnica

- Backend (`3.12.0 → 3.13.0`, fuente única `backend/config.py`):
  - `services/evidence_depth.py` (nuevo, puro): `depth` LOW/MEDIUM/HIGH + `meets_matrix` + `minimum_evidence` contra `cefr_matrix.json`; `PRODUCTION_ITEM_TYPES`.
  - `services/competence.py`: `PRODUCTION_SKILLS` (grammar/speaking/writing) y `SUPPORT_SKILLS` (vocabulary) — el estado `demonstrated` exige muestras mínimas, retención y producción donde aplica.
  - `services/quiz_routes.py`: motor compartido con ítems `mcq` y `controlled_production`; `normalize_typed`/`typed_matches`; `stats` con `bank_size` y `evidence_depth`; `current_level` como sugerencia con fallback `review_due`.
  - Currículo: array `production_checks` por nivel (A2–C1) sin tocar los checks MC (retrocompatibilidad de intentos).
  - `services/cross_skill.py` + `schemas/cross_skill.py` + `routers/cross_skill.py` (endpoint `/api/cross-skill`, prototipo B1).
  - `domain/profile.py`: evidencia por nivel + reports de evidence depth en `/api/profile`.
  - Golden `backend/tests/golden/pedagogy/` + `test_golden_pedagogy.py`; `test_pedagogical_invariants.py` (R1–R7).
- Frontend:
  - `features/routes/QuizRoutePage.tsx` (shell compartido), `routeSession.ts` (máquina de sesión única), `quizRouteTypes.ts`.
  - Grammar/Vocabulary/Pronunciation/Conversation/Speaking como configs del shell (escenas personalizadas, práctica extra, bloques contextuales, assessment ladder o speaking).
  - `features/evidence/CrossSkillMatrix.tsx` y UI *"type the answer"* con claves i18n nuevas `en`/`es`.
  - `utils/i18n.parity.test.ts`.

## Tests

- Backend: **1290 pytest en verde** (antes 1259; +31: producción controlada, evidence depth, invariantes pedagógicas, cross-skill, golden).
- Frontend: **382 vitest en verde** (antes 379; +3: parity i18n, controlled production, cross-skill).
- Playwright desktop en verde: `grammarRoutesReview`, `vocabularyRoutesReview`, `pronunciationRoutesReview`, `conversationRoutesReview` y `speakingRoutesReview` (regresión visual de cada ola de la migración UI).
