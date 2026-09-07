# v3.14.0 — Registro cross-skill de B1 a los 6 niveles (A1–C2)

**Registro cross-skill por estructura en los seis niveles: el canal de producción se ofrece en todos y el panel deja de ser prototipo.**

## Qué cambia

La iteración escala el registro cross-skill por estructura (V3.13 P1.2) del prototipo B1 a **A1–C2** con datos reales por nivel. Antes, `CROSS_SKILL_LEVELS = ("b1",)`, el resto de niveles devolvía lista vacía y el panel solo se montaba en Grammar B1; además A1 y C2 no tenían ningún ítem `controlled_production`, así que el canal `production` no se ofrecía en sus estructuras. Ahora cada nivel declara qué instrumentos ofrece su currículo por destreza y qué evidencia real tiene el usuario, con el binding de producción controlada normativo (verificado por tests: sin CP huérfanos):

- **Contenido — ítems `controlled_production` en A1 y C2**: A1 gana **6 ítems** (`a1-cp-01..06`: verb `to be`, present simple 3.ª persona, adverbios de frecuencia, `have/has got`, preposiciones de lugar, past simple) y C2 gana **4** (`c2-cp-01..04`: inversión enfática, cleft sentence, mixed conditional, pasiva formal de registro), con `accepted_answers` deterministas. El banco de la ruta Grammar crece (A1 38→44; C2 4→8): **C2 sigue en banco corto (≤12)**, así que su claim honesto "practice coverage · evidence depth LOW" se conserva sin etiquetas falsas nuevas.
- **Registro generalizado**: `backend/services/cross_skill.py` deja de ser "prototipo B1 de solo lectura" y pasa a ser el registro de nivel (sigue solo lectura). `CROSS_SKILL_LEVELS = (a1..c2)`; `structure_registry(level)` sirve las estructuras de cualquier nivel (objetivos con checks MC de grammar). `PRODUCTION_BINDINGS_BY_LEVEL` declara el binding normativo CP → estructura en los **seis** niveles: A1/C2 nuevos, A2/B2/C1 validados contra `can_do`/topic y B1 intacto. Un mismo objetivo puede agrupar varios CP (p. ej. C1 `c1-m03-u01-l01-o04` y C2 `c2-m01-u01-l01-o04`) y `production.evidence` cuenta CP superados, no filas.
- **Sin marca de prototipo en API y tipos**: se elimina `proto` de `CrossSkillMatrixOut` (`backend/schemas/cross_skill.py`) y de `CrossSkillMatrix` (`frontend/src/types/api.ts`). `/api/cross-skill` acepta `a1..c2`, devuelve 400 `cross_skill.level_unknown` solo para niveles desconocidos y mantiene el default `"b1"` inofensivo (el frontend pasa siempre el nivel explícito).
- **Panel cross-skill en todos los niveles**: `frontend/src/features/evidence/CrossSkillMatrix.tsx` se monta en el panel del nivel Grammar para cualquier nivel (no solo B1). Se retira el pie "prototipo B1", título/nota se generalizan ("por estructura del nivel") y la clave i18n `crossSkill.protoNote` desaparece de `en`/`es`.
- **Invariantes por nivel**: `backend/tests/test_cross_skill.py` se reescribe con invariantes por nivel: el registro devuelve exactamente los objetivos con checks MC de grammar, los bindings son normativos (cada CP del currículo enlazado a una estructura grammar real, sin huérfanos), la oferta de `listening`/`speaking` refleja el wiring del currículo, y la semántica de matriz (un fallo no cuenta; transfer/novel/delayed → transfer; producción por CP superado) se prueba sobre un nivel no-B1 y sobre estructuras con múltiples CP. El endpoint devuelve 200 en los seis niveles y 400 solo en nivel inválido. Un invariante de contenido protege que A1/C2 mantengan producción enlazada.

## Técnica

- Backend (`3.13.0 → 3.14.0`, fuente única `backend/config.py`):
  - Currículo: array `production_checks` nuevo en `a1.json` (6 ítems) y `c2.json` (4 ítems), sin tocar los checks MC existentes (retrocompatibilidad de intentos).
  - `services/cross_skill.py`: `CROSS_SKILL_LEVELS` completo, constantes `A1..C2_PRODUCTION_BINDINGS` + `PRODUCTION_BINDINGS_BY_LEVEL`, `structure_registry` sin guard de prototipo y `cross_skill_matrix` sin `proto`.
  - `schemas/cross_skill.py`: `proto` eliminado de `CrossSkillMatrixOut`.
  - `routers/cross_skill.py`: validación de `level ∈ CROSS_SKILL_LEVELS` (400 `cross_skill.level_unknown`).
  - Tests: `test_cross_skill.py` reescrito (invariantes por nivel y de contenido A1/C2); `test_grammar_routes.py` → `test_production_pool_items_present_in_every_level`; docstrings de los invariantes pedagógicos de C2 sincronizados (4 MC → 4 MC + 4 CP = 8, sigue banco corto).
- Frontend:
  - `features/grammar/GrammarLevelPanel.tsx`: `CrossSkillMatrix` montado para cualquier nivel.
  - `features/evidence/CrossSkillMatrix.tsx`: copia generalizada, sin pie de prototipo ni dependencia de `proto`.
  - `types/api.ts` sin `proto`; `api/crossSkill.ts` con `level` requerido.
  - `utils/i18n.ts`: título/nota genéricos y clave `crossSkill.protoNote` retirada (`en`/`es`); parity automática intacta.
  - Playwright `tests/visual/grammarRoutesReview.spec.ts`: mock determinista de `/api/cross-skill` (el panel A1 ahora también pide el registro).

## Tests

- Backend: **1293 pytest en verde** (antes 1290; +3 netos: invariantes por nivel del registro, contenido A1/C2 y actualización del pool de producción).
- Frontend: **382 vitest en verde** (sin cambio de conteo; tsc limpio y build de producción OK).
- Playwright desktop en verde: `grammarRoutesReview` (captura de la página única de Grammar con el panel cross-skill del nivel A1).
