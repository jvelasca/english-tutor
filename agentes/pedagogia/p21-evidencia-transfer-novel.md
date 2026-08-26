# V1.21 (4/6) — P1-4: Evidencia transfer / novel (familiar / transfer / novel)

## Rol
Backend (modelo de datos + Student Model). Añades una dimensión `evidence_kind` a la evidencia para distinguir **práctica familiar** de **transferencia** y de **novedad**, y expones un score de dominio *generalizado* separado del mastery de práctica. **No** cambias todavía la lógica de actualización de `next_mastery_state` (eso es del motor adaptativo de V1.22).

## Contexto
La auditoría externa (puntos 28–30) señala que hoy `mastery` puede crecer por pura repetición del mismo tipo de ejercicio, sin distinguir si el alumno puede aplicar la destreza a audio/voz/situación **nueva**. Propone tres niveles de evidencia:

- **Familiar** — mismo tipo de ejercicio (práctica).
- **Transfer** — nuevo audio/ítem, misma habilidad.
- **Novel** — nuevo audio + nuevo hablante + nueva situación.

Y solo la **novel** debe tener peso alto para *confirmar dominio generalizado*.

### Contratos exactos actuales (NO romper)
- Tabla `academy_evidence` (`backend/repositories/db.py`, líneas 283–299) tiene columnas: `id, user_id, level_id, objective_id, skill, item_id, item_type, difficulty, source, result, curriculum_version, assessment_version, created_at`. **No existe `evidence_kind` todavía.**
- Migración idempotente: el patrón es `PRAGMA table_info(<tabla>)` + `ALTER TABLE ... ADD COLUMN ...` (ver `db.py` líneas ~378+ y ~525). Úsalo para añadir la columna sin romper BDs existentes.
- `repositories/academy.py`:
  - `record_evidence(user_id, level_id, objective_id, skill, item_id, item_type="mcq", difficulty=1, source="objective_assessment", result=0.0, curriculum_version="", assessment_version="")` (línea 371). Inserta en `academy_evidence`.
  - `list_evidence(user_id, level_id=None)` (línea 402) hace `SELECT` explícito de columnas.
- `domain/academy.py` → `_record_evidence_validated` (línea 335) llama `academy_repo.record_evidence(user_id, **ev)` y valida con `evidence_record_errors`. Como pasa `**ev`, cualquier clave nueva que metas en el dict del record **fluirá sola** a `record_evidence`.
- `services/academy.py`:
  - `evidence_from_items(...)` (línea 616) devuelve dicts con las claves que consume `record_evidence`.
  - `EVIDENCE_ITEM_TYPES` / `EVIDENCE_SOURCES` (líneas 657–670) son los conjuntos reconocidos.
  - `evidence_record_errors(record, ...)` (línea 673) valida invariantes (incluida `source`/`item_type` conocidos).
  - `build_skill_profile(level, objective_mastery, evidence_rows, now)` (línea 397) agrega evidencia por destreza.
- Generadores de evidencia que debes ampliar con `evidence_kind`:
  - `services/speaking.py` → `evidence_from_speaking` (línea 778).
  - `services/writing.py` → `evidence_from_writing` (línea 166).
  - `services/pronunciation.py` → `evidence_from_pronunciation` (línea 86).
  - `services/academy.py` → `evidence_from_items` (línea 616).

## Objetivo
Persistir y validar `evidence_kind` en cada registro, y derivar un **dominio generalizado** (novel > transfer > familiar) expuesto en el perfil de destreza, sin tocar la actualización de mastery existente.

## Tareas

1. **Migración** — en `backend/repositories/db.py`, añade tras la creación de `academy_evidence`:
   ```python
   evidence_cols = {row[1] for row in conn.execute("PRAGMA table_info(academy_evidence)")}
   if "evidence_kind" not in evidence_cols:
       conn.execute(
           "ALTER TABLE academy_evidence ADD COLUMN evidence_kind TEXT NOT NULL DEFAULT 'familiar'"
       )
   ```

2. **`services/academy.py`**:
   - Añade `EVIDENCE_KINDS: tuple[str, ...] = ("familiar", "transfer", "novel")` junto a `EVIDENCE_ITEM_TYPES`/`EVIDENCE_SOURCES`.
   - `evidence_from_items`: añade parámetro `evidence_kind: str = "familiar"` y añade `"evidence_kind": evidence_kind` al dict de cada registro.
   - `evidence_record_errors`: valida `evidence_kind` — si está presente debe estar en `EVIDENCE_KINDS`; si ausente, se trata como `"familiar"` (no error). Añade el error `f"evidence_kind '{x}' desconocido"` si es inválido.
   - Añade helper puro:
     ```python
     EVIDENCE_KIND_WEIGHTS = {"familiar": 0.2, "transfer": 0.3, "novel": 0.5}
     def generalized_mastery_score(rows: list[dict]) -> float | None:
         """Dominio generalizado (novel > transfer > familiar) sobre la evidencia.
         Media ponderada de `result` por `evidence_kind`, renomalizada a las filas
         presentes. Devuelve None si no hay evidencia."""
     ```
     - Usa `rows` de `list_evidence` (dicts con `evidence_kind` y `result`). Renormaliza los pesos a las clases presentes; ignora filas con `result` no numérico.
   - `build_skill_profile`: por cada destreza, añade al dict del perfil:
     - `"evidence_by_kind": {"familiar": n, "transfer": n, "novel": n}` (recuentos de `rows` por `evidence_kind`, default 0).
     - `"generalized_score"`: `generalized_mastery_score(rows)` (puede ser `None`).
     - Mantén intactos los campos existentes (`score`, `confidence`, `evidence_count`, `last_evidence`, `review_due`, `subskills`).

3. **`repositories/academy.py`**:
   - `record_evidence`: añade parámetro `evidence_kind: str = "familiar"` y la columna en el `INSERT` (y su valor en la tupla).
   - `list_evidence`: añade `evidence_kind` a las dos consultas `SELECT` (para que `build_skill_profile` y `generalized_mastery_score` lo reciban).

4. **Generadores de evidencia** — añade `evidence_kind: str = "familiar"` como keyword-only y añade `"evidence_kind": evidence_kind` a cada registro en:
   - `speaking.evidence_from_speaking`
   - `writing.evidence_from_writing`
   - `pronunciation.evidence_from_pronunciation`
   - (ya hecho) `academy.evidence_from_items`

   **No** cambies el default `"familiar"` en ningún call site existente: toda la evidencia actual queda como `familiar` (retrocompatible). Los callers de transfer/novel se conectarán en V1.22.

5. **Tests** — en `backend/tests/test_evidence_invariants.py` y `backend/tests/test_academy.py`:
   - Un registro con `evidence_kind="novel"` es válido; con `"raro"` produce error.
   - `record_evidence` con `evidence_kind="transfer"` persiste y `list_evidence` lo devuelve.
   - `generalized_mastery_score`: 3 filas (familiar=1.0, transfer=0.5, novel=0.0) → valor esperado con los pesos (0.2·1 + 0.3·0.5 + 0.5·0 = 0.35); lista vacía → `None`; filas con un solo kind renomalizan a 1.
   - `build_skill_profile` incluye `evidence_by_kind` y `generalized_score`.
   - Verifica que los tests existentes de `evidence_from_speaking`/`evidence_from_items` siguen pasando (el nuevo campo no rompe `**ev` → `record_evidence`).

## Restricciones
- **No cambies `next_mastery_state`** ni la persistencia de `academy_skill_mastery`/`academy_objective_mastery`. El mastery de práctica sigue igual; el dominio generalizado es una **señal derivada** expuesta para la matriz CEFR (P1-6) y el motor adaptativo (V1.22).
- Migración idempotente (no rompe BDs con datos). Default `'familiar'` para toda la evidencia previa.
- Pasa `pytest` y `ruff`. No toques frontend.
- Crea un único commit `feat: evidencia familiar/transfer/novel + dominio generalizado` (no hagas push). Deja el briefing untracked.
