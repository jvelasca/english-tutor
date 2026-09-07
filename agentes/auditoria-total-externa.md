# Briefing — Auditoría TOTAL externa (read-only) de v3.18.0

> Fecha: 2026-09-07 · Rol: **auditor externo read-only** (subagente autocontenido).
> Objetivo: reproducir y verificar **todas** las afirmaciones de la posición v3.18.0
> y del estado global del producto antes de declararlo auditable. Sigue la
> metodología de las auditorías externas v3.16/v3.17 y la plantilla
> `docs/audit/TEMPLATE.md`.

## 0. Cómo arrancar (auditor, contexto nuevo)

1. Lee en orden: `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`,
   `docs/RELEVO.md` (solo encabezado + secciones 0, 9 y 37), `PLAN.md`
   (estado actual + siguiente incremento), `README.md`, `CHANGELOG.md`,
   `docs/BETA_V3.md`, `docs/AUDITORIA-V3.md` y los dossieres `docs/audit/*.md`.
2. Confirma el punto de partida del repo con:
   ```powershell
   git log --oneline -5
   git status --short          # debe estar limpio (o solo cambios del auditor)
   git describe --tags
   ```
   La posición es **v3.18.0** (`backend/config.py::VERSION = "3.18.0"`,
   `frontend/package.json`/`package-lock.json` idénticos).
3. Entorno Windows/PowerShell. Backend: Python en `backend\.venv`. Frontend:
   Node en `frontend`. No instalar dependencias; no modificar código.

## 1. Alcance (TOTAL)

- **Núcleo v3.18** (Knowledge Graph remainder + deuda del grafo, P3): I2, O1,
  M4, O3, H5, H6 + observaciones de la auditoría v3.17.
- **Estado global declarado** (claims del encabezado de `docs/RELEVO.md` y de
  `release-notes-v3.18.0.md`): números de tests, gates, consistencia de versión.
- **Estabilidad del sistema completo**: sin romper CONSTITUCIÓN, premisas,
  arquitectura ni los mecanismos previos (v3.13–v3.17).
- **NO se audita** (frontera honesta): ejecución física en dispositivos
  (`docs/audit/G-DEVICES.md`), variabilidad LLM con Ollama real
  (`docs/audit/C-SPEAKING-CALIBRATION.md`), calibración con alumnos reales
  (dossieres D/E), audio humano real (manifest vacío, TTS como proxy). Son
  acciones abiertas conocidas, no defectos a detectar.

## 2. Tarea — batería automática (reproducir, no creer)

Ejecuta cada gate y anota el resultado real. El **orden** importa poco; la
**cita de comando** sí (queda en el dossier).

### Backend (`cd backend`)
```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
#   claim: 1345 passed
.venv\Scripts\python.exe -m ruff check .
#   claim: All checks passed!
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict --quality
#   claim: exit 0 (sin huecos empty; Curriculum Quality Dashboard OK)
.venv\Scripts\python.exe -m scripts.content_validation
#   claim: exit 0 (CONTENT INTEGRITY CHECK sin errores)
```

### Raíz
```powershell
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py
#   claim: OK: Release consistency (3.18.0) en todos los orígenes, exit 0
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py
#   claim: OK: Beta V3.0 gate, exit 0
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py
#   claim: exit 0, 0 claves usadas-no-definidas / duplicadas / vacías
```

### Frontend (`cd frontend`)
```powershell
npm test        # claim: vitest 414 passed (52 archivos)
npm run build   # claim: tsc + vite build OK
```

### Visual (Playwright, región Home/grafo — desktop)
Requiere el backend arriba en `:8000` (el webServer de Playwright levanta Vite
solo, HTTPS autofirmado, `reuseExistingServer`). Si no puedes dejar el backend
corriendo, márcalo como *no reproducido* (honesto) en vez de inventarlo:
```powershell
# terminal 1: cd backend; .venv\Scripts\python.exe -m uvicorn main:app --port 8000
# terminal 2: cd frontend
npx playwright test tests/visual/smoke.spec.ts tests/visual/homeGraphChip.spec.ts --project=desktop
#   claim: verdes; captura tests/visual/screenshots/desktop/home-graph-chip.png
```

## 3. Verificación de las afirmaciones v3.18 contra el código

Reproduce cada ítem del encabezado de `docs/RELEVO.md` (2026-09-07) en el
código y en tests. Guía de localización:

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| **I2** ancla congelada al completar | `backend/repositories/db.py` (tabla `unit_review_anchors`, `INSERT OR IGNORE`), `repositories/academy.py` (`get_unit_anchor`/`set_unit_anchor_if_absent`), `services/unit_review.py` (`build_unit_review_plan(anchor=)`), backfill lazy en `domain/academy.py` | `test_unit_review.py`, `test_unit_review_endpoints.py` |
| **O1** cascade 7→30→90 | `services/unit_review.py` (`window_due_at`, intento propio manda, superado tardío cierra) | `test_unit_review.py` |
| **M4** cartas FSRS `objective` fuera del autograduable (single writer) | `domain/academy.py` (`_sync_objective_cards_for_level` con gating due/failed o `reps>0`; exclusión en `get_fsrs_due`/`get_fsrs_summary`; `review_fsrs_card` → router 400) | `test_unit_review_endpoints.py` |
| **O3** plan de repaso por niveles | `schemas/academy.py` (`UnitReviewPlanOut{levels,due_count}`), routers con `level_id`, validación de la unidad en su nivel; frontend `features/review` (`flattenReviewLevels`, `UnitReviewPanel`) | endpoints + vitest |
| **H5** etiquetas humanas del grafo | `frontend/src/utils/learningLabels.ts` (`GRAPH_DIMENSION_LABELS`, `dimensionLabel`) y su uso en `TodayPlan`/`NextBestCard`/`ObjectiveNodeCard`/`EvidenceGraphPanel` | `learningLabels.test.ts` |
| **H6** coste lazy `/session` y `/next-best` | `domain/academy.py` (`_session_steps`, cap ≤ `SESSION_CAPS["weakness"]`, una sola `list_evidence` y solo si hay nodos) | `test_session_graph.py` |
| Auditoría v3.17 (fixes) | `ObjectiveNodeCard.tsx` (error vs 404/empty + reintento), `_as_float` en `services/evidence_graph.py`, `getJsonNullable` en `api/client.ts` | vitest `ObjectiveNodeCard.test.tsx`, puro `_as_float` |

**Reglas del juego (premisas):** el micro-review y el micro-drill no declaran
dominio (mecanismos separados); `/session` y `/next-best` nunca divergen; no hay
claims de dominio sin evidencia; la versión vive solo en `backend/config.py`.

## 4. Puntos de atención (comprobar explícitamente)

- **Candidatos cerrados vs abiertos** (`docs/RELEVO.md` final): P0–P3 ✅
  cerrados; queda **V3.19 abierto** (léxico por destreza + speaking micro-drill)
  definido como candidato y reflejado en `PLAN.md`. No debe haber otras deudas
  no listadas.
- **Árbol git**: no debe haber artefactos sin versionar que ensucien el repo
  (release-notes v3.10–v3.18 ya versionadas; `docs/audit/generated/*` al día).
- **Estados vacíos/carga/error de la Home** (F1/F3/F4 de `AUDITORIA-V3.md`) y
  aislamiento cross-user: `backend/tests/test_cross_user_isolation.py`.
- **i18n**: parity es/en (el checker debe salir exit 0; los "sin uso" son
  candidatas a limpieza, no errores).
- Busca **roturas de premisas**: si un hallazgo contradice `PREMISAS.md` o la
  CONSTITUCIÓN, es severidad alta aunque el gate pase.

## 5. Criterios de aceptación del auditor

1. Cada claim de la sección 2 y 3 queda **reproducido** o marcado *no
   reproducible* con su causa (comando + resultado real).
2. Ningún hallazgo de severidad alta sin acción; los medios/bajos quedan
   registrados con recomendación y estado.
3. Veredicto final en formato del proyecto: **APROBADO / APROBADO CON
   OBSERVACIONES / NO APROBADO** + resumen de 2–3 líneas.

## 6. Salida

- Dossier en `docs/audit/` siguiendo `docs/audit/TEMPLATE.md` (alcance, método,
  evidencia, hallazgos, veredicto, "Regenerar / Verificar") — el nombre y la
  consolidación los decide el gerente.
- Informe final con: veredicto, tabla de gates con resultados reales, tabla de
  claims I2/O1/M4/O3/H5/H6 con su test de respaldo, y lista de hallazgos.

## 7. Restricciones

- **Solo lectura** en código/BD de producción. No escribir fuera de `docs/audit/`
  si el gerente autoriza el dossier.
- No ejecutar nada que dependa de Ollama/Whisper/Piper salvo que el gerente lo
  pida (los flujos auditados no los requieren; el LLM real es frontera honesta).
- No instalar dependencias ni lanzar migraciones destructivas. BD de tests =
  temporales (pytest con `tmp_path`).
