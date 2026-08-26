# V1.21 (6/6) — P1-6: Matriz de assessment CEFR (A1–B2 × 4 destrezas)

## Rol
Backend (contenido curricular + Adaptive Engine). Creas una **matriz de assessment CEFR** por nivel y destreza, con umbrales de dominio, confianza, evidencia y transferencia, y haces que la decisión de *readiness* (¿está listo para subir de nivel?) la consuma en vez del mínimo plano actual. **No** certificas CEFR: esto sigue siendo una estimación heurística.

## Contexto
La auditoría externa (puntos 32–38) critica que el "nivel" siga siendo una media simple y pide que la decisión CEFR sea **multidimensional**: `minimum mastery + confidence + evidence + transfer + novelty` por nivel y destreza. La infraestructura ya existe (`services/adaptive.py` → `readiness`), pero usa un único `READINESS_MINIMUMS` plano (independiente del nivel) y no distingue evidencia transfer/novel.

Depende del briefing **P1-4 (p21)**: `build_skill_profile` ya añade `evidence_by_kind` (`{familiar, transfer, novel}`) y `generalized_score` a cada entrada del perfil.

### Contratos exactos actuales (NO romper)
- `services/adaptive.py`:
  - `READINESS_MINIMUMS` (línea 104): mínimos **planos** por destreza (grammar 0.7, vocabulary 0.7, pronunciation 0.6, listening 0.7, speaking 0.6, reading 0.7, writing 0.6).
  - `READINESS_MIN_CONFIDENCE = 0.6` (línea 114), `READINESS_MIN_EVIDENCE = 3` (línea 116), `READINESS_DEFAULT_MINIMUM = 0.7` (línea 118).
  - `readiness(profile, target_level)` (línea 121): por cada destreza calcula `minimum = READINESS_MINIMUMS.get(skill, DEFAULT)` y `is_ready = evaluated and score >= minimum and confidence >= READINESS_MIN_CONFIDENCE and evidence_count >= READINESS_MIN_EVIDENCE`. Devuelve `{target_level, skills, overall, blocking_skills, ready}` con cada `skill` → `{skill, score, confidence, evidence_count, minimum, ready}`.
- `services/curriculum.py`:
  - `CANONICAL_SKILLS` (línea 23): `vocabulary, grammar, pronunciation, listening, speaking, reading, writing`.
  - `CURRICULUM_DIR = .../curriculum` (línea 154) y `_NON_LEVEL_FILES = frozenset({"assessments.json", "speaking_assessment.json"})` (línea 157). **`load_all_levels()` hace glob de `*.json` excluyendo `_NON_LEVEL_FILES`** (línea 290), así que un nuevo `cefr_matrix.json` en ese directorio DEBE añadirse a `_NON_LEVEL_FILES` o `load_all_levels` intentará parsearlo como `Level` y fallará.
  - El contenido curricular vive en `backend/curriculum/*.json` (a1.json, a2.json, b1.json, b2.json, assessments.json, speaking_assessment.json).
- `schemas/academy.py` → `ReadinessSkillOut` (línea 532): `skill, score, confidence, evidence_count, minimum, ready`. `ReadinessOut` (línea 541): `target_level, skills, overall, blocking_skills, ready`.
- `domain/academy.py` → `build_student_model` (línea 525) llama `adaptive.readiness(skills, target)`; `get_readiness` (línea 550) también.
- Tests: `backend/tests/test_adaptive.py` usa `_entry(skill, score, confidence, evidence_count, **kwargs)` **sin** `evidence_by_kind` (línea 10), y `test_readiness_*` (líneas 76–110) esperan `ready` con score 0.9 / confidence 0.9 / evidence 4–5 en destrezas auto-scorables.

## Objetivo
Crear `backend/curriculum/cefr_matrix.json` + cargador Pydantic + `readiness` que lo consuma, con gate de transferencia/novedad **retrocompatible** (solo se aplica si el perfil trae `evidence_by_kind`).

## Tareas

1. **Contenido** — crea `backend/curriculum/cefr_matrix.json` (sobre las 4 macro-destrezas: `listening`, `speaking`, `reading`, `writing`; `grammar`/`vocabulary`/`pronunciation` siguen gobernadas por `READINESS_MINIMUMS` como fallback):
   ```json
   {
     "version": "1.0.0",
     "levels": {
       "A1": {
         "listening": {"minimum_mastery": 0.60, "minimum_confidence": 0.50, "minimum_evidence": 2, "transfer_required": 0, "novel_required": 0},
         "speaking":  {"minimum_mastery": 0.55, "minimum_confidence": 0.50, "minimum_evidence": 2, "transfer_required": 0, "novel_required": 0},
         "reading":   {"minimum_mastery": 0.60, "minimum_confidence": 0.50, "minimum_evidence": 2, "transfer_required": 0, "novel_required": 0},
         "writing":   {"minimum_mastery": 0.55, "minimum_confidence": 0.50, "minimum_evidence": 2, "transfer_required": 0, "novel_required": 0}
       },
       "A2": {
         "listening": {"minimum_mastery": 0.65, "minimum_confidence": 0.55, "minimum_evidence": 3, "transfer_required": 0, "novel_required": 0},
         "speaking":  {"minimum_mastery": 0.60, "minimum_confidence": 0.55, "minimum_evidence": 3, "transfer_required": 0, "novel_required": 0},
         "reading":   {"minimum_mastery": 0.65, "minimum_confidence": 0.55, "minimum_evidence": 3, "transfer_required": 0, "novel_required": 0},
         "writing":   {"minimum_mastery": 0.60, "minimum_confidence": 0.55, "minimum_evidence": 3, "transfer_required": 0, "novel_required": 0}
       },
       "B1": {
         "listening": {"minimum_mastery": 0.70, "minimum_confidence": 0.60, "minimum_evidence": 3, "transfer_required": 1, "novel_required": 0},
         "speaking":  {"minimum_mastery": 0.65, "minimum_confidence": 0.60, "minimum_evidence": 3, "transfer_required": 1, "novel_required": 0},
         "reading":   {"minimum_mastery": 0.70, "minimum_confidence": 0.60, "minimum_evidence": 3, "transfer_required": 1, "novel_required": 0},
         "writing":   {"minimum_mastery": 0.65, "minimum_confidence": 0.60, "minimum_evidence": 3, "transfer_required": 1, "novel_required": 0}
       },
       "B2": {
         "listening": {"minimum_mastery": 0.75, "minimum_confidence": 0.65, "minimum_evidence": 4, "transfer_required": 2, "novel_required": 1},
         "speaking":  {"minimum_mastery": 0.70, "minimum_confidence": 0.65, "minimum_evidence": 4, "transfer_required": 2, "novel_required": 1},
         "reading":   {"minimum_mastery": 0.75, "minimum_confidence": 0.65, "minimum_evidence": 4, "transfer_required": 2, "novel_required": 1},
         "writing":   {"minimum_mastery": 0.70, "minimum_confidence": 0.65, "minimum_evidence": 4, "transfer_required": 2, "novel_required": 1}
       }
     }
   }
   ```
   (Los valores son **contenido** ajustable por el equipo pedagógico; no los cifres en Python.)

2. **`services/curriculum.py`**: añade `"cefr_matrix.json"` a `_NON_LEVEL_FILES` (línea 157).

3. **Nuevo `backend/services/cefr_matrix.py`** (puro, determinista; carga con cache):
   - Modelos Pydantic: `CefrSkillRequirement` (`minimum_mastery`, `minimum_confidence`, `minimum_evidence`, `transfer_required=0`, `novel_required=0`), `CefrLevelRequirements` (`level`, `skills: dict[str, CefrSkillRequirement]`), `CefrMatrix` (`version`, `levels: dict[str, CefrLevelRequirements]`).
   - `load_matrix() -> CefrMatrix` (lee `CURRICULUM_DIR / "cefr_matrix.json"`, cacheado a nivel de módulo).
   - `requirements_for(level_id: str, skill: str) -> CefrSkillRequirement | None`.

4. **`services/adaptive.py`** — reescribe `readiness` para consumir la matriz, manteniendo la forma de salida:
   - Por destreza: `req = requirements_for(target_level, skill)`.
   - `minimum = req.minimum_mastery if req else READINESS_MINIMUMS.get(skill, READINESS_DEFAULT_MINIMUM)`.
   - `min_conf = req.minimum_confidence if req else READINESS_MIN_CONFIDENCE`.
   - `min_evidence = req.minimum_evidence if req else READINESS_MIN_EVIDENCE`.
   - Gate de transfer/novel **retrocompatible**:
     ```python
     by_kind = entry.get("evidence_by_kind")
     if req is not None and isinstance(by_kind, dict):
         transfer_ok = by_kind.get("transfer", 0) >= req.transfer_required
         novel_ok = by_kind.get("novel", 0) >= req.novel_required
     else:
         transfer_ok = novel_ok = True  # perfil legacy sin evidence_by_kind
     ```
   - `is_ready = evaluated and score >= minimum and confidence >= min_conf and evidence_count >= min_evidence and transfer_ok and novel_ok`.
   - En el dict de cada `skill`, añade `transfer_required` y `novel_required` (0 si no hay `req`) y `transfer_count`/`novel_count` (de `by_kind`, default 0). Mantén `minimum` y `ready`.
   - Conserva el cálculo de `overall` (%), `blocking_skills` y `ready` global intactos.

5. **`schemas/academy.py`** → `ReadinessSkillOut`: añade `transfer_required: int = 0`, `novel_required: int = 0`, `transfer_count: int = 0`, `novel_count: int = 0` (con defaults para no romper otros consumidores).

6. **Tests**
   - Nuevo `backend/tests/test_cefr_matrix.py`: `load_matrix` valida el JSON; `requirements_for("B1", "listening").transfer_required == 1`; `requirements_for("C1", "listening") is None`; `requirements_for("B1", "grammar") is None` (fallback esperado).
   - `test_adaptive.py`: actualiza el helper `_entry` para aceptar `evidence_by_kind` (default `{}`). Ajusta `test_readiness_all_ready` (línea 100) si el nivel objetivo exige transferencia: pasa `evidence_by_kind={"transfer": 1, "novel": 0}` a las destrezas de la matriz. Añade casos:
     - B1 con `listening` score 0.9 / conf 0.9 / evidence 4 pero `evidence_by_kind={"transfer": 0}` → `ready=False` (bloqueada por transferencia).
     - B2 con `novel_required=1` y sin `novel` → `ready=False`.
     - Perfil legacy (sin `evidence_by_kind`) en B1 → no bloquea por transferencia (retrocompatible).
   - Verifica que `test_profile.py`/`test_academy.py` (endpoint `readiness`) siguen pasando.

## Restricciones
- `readiness` mantiene su firma `(profile, target_level)` y la forma de `ReadinessOut`. No cambies el contrato del endpoint `/api/academy/readiness`.
- Los niveles C1/C2 no están en la matriz (fuera del alcance A1→B2): `requirements_for` devuelve `None` y se usa el fallback plano.
- La matriz es **contenido**, no lógica: los umbrales viven solo en `cefr_matrix.json`.
- No implementes certificación CEFR ni nuevo endpoint. Es solo la matriz + consumo en `readiness`.
- Pasa `pytest` y `ruff`. No toques frontend.
- Crea un único commit `feat: matriz de assessment CEFR A1-B2 (thresholds + confianza + transfer)` (no hagas push). Deja el briefing untracked.
