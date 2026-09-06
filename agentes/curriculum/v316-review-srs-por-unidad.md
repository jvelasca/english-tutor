# V3.16 — v316-review-srs-por-unidad: Review/SRS por unidad (micro-review + ventanas 7/30/90)

## Decisiones de diseño para aprobar (resumen para el gerente)

> El gerente revisa estas decisiones ANTES de ejecutar el briefing. La implementación
> asume las marcadas como *(recomendado)*.

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| D1 | Granularidad del repaso por unidad | (a) cartas FSRS `target_type="objective"` + plan de unidad derivado; (b) añadir tipo `unit` al motor FSRS | **(a)** — el motor ya soporta `objective` sin sembrar; cero cambios de motor; la unidad se modela como agregación (coherente con E3 de `docs/audit/E-FSRS-RETENTION.md`: mantener mecanismos separados y etiquetados) |
| D2 | Alcance del plan de repaso | (a) solo nivel actual enrollado; (b) todos los niveles con unidades completadas | **(a) para v1** — el plan se calcula sobre el nivel actual (`_current_level_id`), que es el que el alumno está consolidando; (b) queda documentado como extensión futura |
| D3 | Ventanas fijas | constantes puras `(7, 30, 90)` días desde el ancla de la unidad; sin recalendarización por grade | **(fijas desde el ancla)** — "ventanas 7/30/90" es calendario de hitos de retención, distinto del scheduling FSRS continuo; un grade nunca mueve la ventana, solo la marca como superada/fallida y reprograma la carta del objetivo |
| D4 | Definición de unidad "completada" (ancla temporal) | todas las destrezas de todos sus objetivos `mastered` | **(mastery de todos sus objetivos)** — reutiliza `mastered_objective_ids`; ancla = `max(updated_at)` de las filas de mastery de la unidad (momento en que aterrizó la última evidencia que la completó); verificación en la Fase A |
| D5 | ¿El micro-review alimenta mastery/evidencia? | (a) no: solo tabla propia de intentos + cartas FSRS de objetivo; (b) sí: crea evidencia delayed | **(a)** — evita doble contabilidad y mantiene el significado de la evidencia del currículo; el micro-review es práctica de recuperación para retención (E3: etiquetar cada mecanismo) |
| D6 | Umbral de superado del micro-review | ratio aciertos ≥ 0.7 constante `MICRO_REVIEW_PASS_RATIO` | **(≥ 0.7)** — alineado con los umbrales de práctica del proyecto; ventana fallida queda "a repetir" hasta superar |
| D7 | Integración UI | bloque nuevo `UnitReviewPanel` en INICIO + endpoints propios; el plan del día adaptativo (`adaptive.today_plan`) NO se toca | **(bloque propio)** — menor invasión; el panel INICIO ya aloja `FsrsReviewPanel`; el plan adaptativo queda para v3.17 |
| D8 | Contenido del micro-review | checks MC oficiales de los objetivos de la unidad (muestreo determinista balanceado) | **(checks oficiales)** — cero contenido nuevo (regla del proyecto: nada artificial) |

## Rol
Implementador **full-stack** (backend servicios/domain/repos/schemas/routers + frontend + tests).
Cierras el frente abierto del candidato "🟠 P1 — Review/SRS por unidad" (v3.16, auditado ABIERTO
2026-09-05). NO haces bump de versión ni docs de release (README/CHANGELOG/PLAN/RELEVO/release-notes):
eso lo cierra el gerente tras tu informe, replicando el patrón del commit `9100a81`.

## Auditoría previa (deltas medibles, fuente de la verdad)
Medido sobre el código actual (rama `main`, v3.15.0):
1. **Motor FSRS** (`backend/services/fsrs.py`) soporta `TARGET_TYPES = ("skill","lexicon","objective")`
   pero **nada siembra `objective`**: `sync_fsrs_cards` (`backend/domain/academy.py:1646-1731`) solo
   crea cartas `skill` (perfil) y `lexicon` (débil/learning/known).
2. **No hay plan de repaso por unidad**: ni servicio puro, ni endpoint, ni UI que diga "la unidad X
   toca repasar hoy".
3. **No hay ventanas fijas 7/30/90**: no existe constante de ventanas, ni ancla temporal de unidad,
   ni persistencia de intentos de repaso de unidad.
4. **El micro-review no existe**: hoy la carta FSRS se autogradera sin contenido accionable
   (`FsrsReviewPanel`); no hay sesión de práctica de recuperación sobre los checks del currículo.
5. El **panel INICIO** (`frontend/src/features/home/HomeScreen.tsx`) monta `TodayPlan` +
   `FsrsReviewPanel`; no hay bloque de repaso por unidad.

## Contexto técnico (lee antes de tocar nada)

- `docs/FSRS.md`, `docs/audit/E-FSRS-RETENTION.md` — qué programa el scheduler, qué son los
  mecanismos separados (E3: etiquetar cada mecanismo; no mezclar ventana de retención con FSRS).
- `docs/PREMISAS.md` (12 tests obligatorios, 18 docstrings, 19/20 UI), `docs/ARQUITECTURA.md`
  (capas: routers → domain → repositories/servicios → schemas; frontend api/features/hooks/types).
- `docs/CONSTITUCION-PEDAGOGICA.md` — reglas R1–R7 (en especial R6 "éxito inmediato ≠ retención";
  el micro-review NO declara dominio: es práctica; decidir dominio sigue siendo del Mastery Engine).
- **Motor FSRS** `backend/services/fsrs.py`: `empty_card`, `seed_card_from_evidence`,
  `schedule(card, grade)`, `explain`, `is_due`, `due_queue`, `grade_from_score(score)`,
  `why_for_skill`, `why_for_lexicon`, `GRADES`, `TARGET_TYPES`. Añade `why_for_objective` aquí
  (función pura) si procede.
- **Persistencia** `backend/repositories/db.py`: esquema idempotente (`CREATE TABLE IF NOT EXISTS`).
  Tabla actual `fsrs_cards` (líneas ~418-440): PK `(user_id, target_type, target_id)`. Patrón de
  migración: añadir la tabla nueva en el mismo bloque de init; nunca migraciones destructivas.
- **Repos FSRS** `backend/repositories/academy.py:975-1057`: `upsert_fsrs_card`, `get_fsrs_card`,
  `list_fsrs_cards`. Patrón de repo: sin lógica de negocio.
- **Orquestación** `backend/domain/academy.py`:
  - `_current_level_id(user_id)`, `_annotated_profile`, `_levels_by_id` (cache de currículo).
  - `sync_fsrs_cards(user_id, now)` (1646-1731) — extiende aquí la siembra de `objective`.
  - `get_today_plan` (1809+) — patrón para componer `lv + obj_mastery + mastered`: usa
    `academy_repo.list_objective_mastery(user_id, lv.level_id)` → `_split_objective_mastery` →
    `academy_svc.mastered_objective_ids(lv, scores, attempts)`. REUTILIZA este patrón.
  - `submit_objective_assessment` (2168+) y `record_lesson_completed` (2143+) — NO los toques.
- **Mastery** `backend/services/academy.py`: `mastered_objective_ids`, `objective_progress`,
  `next_mastery_state`. `score_items(obj.checks, answers)` y `evidence_from_items` en el mismo
  servicio (referencia para puntuar checks MC del currículo).
- **Estructura del currículo** `backend/services/curriculum.py`: `Level.modules[].units[].lessons[]
  .objectives[]`. Cada objetivo: `id`, `title`, `can_do`, `skills`, `subskills`, `checks` (MC con
  `id/skill/prompt/options/correct_index`, todos auto-scorables; NO hay checks abiertos en el
  currículo), `thresholds`. El nivel actual se itera como `mod.units` → `unit.id`/`title`.
- **Frontend**:
  - `frontend/src/features/home/HomeScreen.tsx` — donde viven `TodayPlan` y `FsrsReviewPanel`
    (líneas ~219 y ~288). Añade aquí el bloque nuevo.
  - `frontend/src/features/review/FsrsReviewPanel.tsx` — patrón de panel con cola, estados
    empty/error/loading y 4 grades (lo imita el nuevo panel, NO lo modificas en su contrato).
  - `frontend/src/api/academy.ts` (getJson + `userQuery`), `frontend/src/types/api.ts`
    (interfaces espejo), `frontend/src/hooks/useI18n.ts` + `frontend/src/utils/i18n.ts` (claves
    por idioma; hay test de parity `i18n.parity.test.ts` que EXIGE las mismas claves en es/en).
  - Sistema de diseño: tokens en `index.css`; componentes UI en `frontend/src/components/ui/*`
    (`Card`, `Button`, `RadioGroup`/botones de opción…); responsive y estados obligatorios.
- **Tests existentes que fijan el estado FSRS** (no romper, ampliar):
  - `backend/tests/test_fsrs.py` (motor puro), `backend/tests/test_golden_fsrs.py` (golden).
  - Tests de academy/dominio que ejercen `sync_fsrs_cards`, `/api/academy/fsrs/*`,
    `get_today_plan` (búscalos con `rg "fsrs" backend/tests`). La siembra nueva de `objective`
    debe convivir: los tests existentes que cuenten tipos (`by_type`) pueden necesitar
    actualización HONESTA si ahora aparece `objective` en escenarios con unidades completadas.

## Tarea

### Fase A — Servicio puro de plan de repaso por unidad (nuevo `backend/services/unit_review.py`)

Servicio SIN FastAPI ni BD (como `fsrs.py`). Responsabilidades y firma sugerida:

- Constantes puras: `UNIT_REVIEW_WINDOWS_DAYS: tuple[int, ...] = (7, 30, 90)`,
  `MICRO_REVIEW_PASS_RATIO = 0.7`, `MICRO_REVIEW_TARGET_ITEMS = 8`,
  `MICRO_REVIEW_MAX_PER_OBJECTIVE = 2`, `UNIT_REVIEW_SOURCE = "unit_micro_review"`.
- `window_due_at(anchor_iso: str, window_days: int, now: str = "") -> dict` → estado de la ventana:
  `{window_days, due_at, state}` con `state ∈ {"upcoming","due_now","passed","failed"}`
  derivado de `now` y de los intentos (regla D3/D6: intento más reciente de la ventana
  `passed` si ratio ≥ umbral; si hay intento fallido y ahora ≥ due → `failed`/reintentable; si no
  hay intento: `upcoming` si `now < due_at`, `due_now` si `now ≥ due_at`).
- `unit_completed(unit, mastered_ids: set[str]) -> bool` → todos los objetivos de la unidad en
  `mastered_ids`.
- `unit_anchor(unit_mastery_rows: list[dict]) -> str | None` → `max(updated_at)` de las filas de
  mastery de la unidad si la unidad está completada; `None` si no.
- `build_unit_review_plan(*, unit, unit_mastery_rows, mastered_ids, now) -> dict` → estructura por
  unidad: `{level_id, unit_id, module_title?, title, objectives_total, objectives_mastered,
  completed, anchor, windows: [...]}`.
- `sample_micro_review(*, unit, user_id, window_days, previous_failed_ids, now) -> list[dict]` →
  muestreo **determinista y balanceado** de checks MC de los objetivos de la unidad
  (`MICRO_REVIEW_TARGET_ITEMS` items, máx. `MICRO_REVIEW_MAX_PER_OBJECTIVE` por objetivo):
  - semilla determinista derivada de `(user_id, unit_id, window_days)` — misma sesión = mismo orden;
  - en un reintento de la MISMA ventana, prioriza los ítems fallados en el último intento
    (`previous_failed_ids`), luego rellena con checks no usados del último intento, luego rota;
  - cada item: `{item_id, objective_id, objective_title, skill, prompt, options}` (NO incluyas
    `correct_index` en la salida al cliente).
- `score_micro_review(*, answers: dict[str, int], unit, sample) -> dict` → por ítem correcto +
  agregado por objetivo `{per_objective: [{objective_id, correct, total}], correct, total,
  accuracy, passed}`. El servidor puntúa con `correct_index` (el cliente solo envía índices,
  nunca puntuaciones — premisa 21).
- `grade_for_accuracy(accuracy: float) -> int` → delega en `fsrs.grade_from_score`.

Docstrings completos (premisa 18). Tests puros en `backend/tests/test_unit_review.py`
(determinismo del muestreo, balance por objetivo, prioridad de fallidos en reintento, estados de
ventana con `now` fijo, ancla, `unit_completed`, umbral de passed).

### Fase B — Siembra de cartas FSRS `objective` + persistencia de intentos

1. **Siembra** en `sync_fsrs_cards` (`backend/domain/academy.py`): tras las cartas skill/lexicon,
   añade cartas `("objective", objective_id)` para los objetivos de las unidades **completadas del
   nivel actual**:
   - `why = fsrs.why_for_objective(unit, entry)` (función pura nueva en `fsrs.py`: p. ej.
     `"unit-window-7"` / `"unit-window-30"` / `"unit-window-90"` para la ventana más próxima no
     superada, o `"unit-maintenance"` si las 3 superadas).
   - Si la carta ya tiene `reps > 0`: conserva scheduling y refresca solo `why`/`label` (mismo
     patrón que skill/lexicon).
   - Si es nueva: `fsrs.seed_card_from_evidence(...)` con `score` del mastery del objetivo y
     `last_evidence_at = updated_at` de la fila; `target_id = objective_id`, `label = title`.
   - Verifica que `fsrs.TARGET_TYPES` no cambia (ya incluye `objective`).
2. **Tabla de intentos** (migración idempotente en `backend/repositories/db.py`):
   ```sql
   CREATE TABLE IF NOT EXISTS unit_review_attempts (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       user_id TEXT NOT NULL,
       level_id TEXT NOT NULL,
       unit_id TEXT NOT NULL,
       window_days INTEGER NOT NULL,
       correct INTEGER NOT NULL,
       total INTEGER NOT NULL,
       accuracy REAL NOT NULL,
       passed INTEGER NOT NULL,
       per_objective TEXT NOT NULL DEFAULT '[]',  -- JSON [{objective_id, correct, total}]
       failed_items TEXT NOT NULL DEFAULT '[]',   -- JSON [item_id...]
       created_at TEXT NOT NULL,
       FOREIGN KEY (user_id) REFERENCES users(id)
   );
   CREATE INDEX IF NOT EXISTS idx_unit_review_attempts_lookup
       ON unit_review_attempts(user_id, level_id, unit_id, window_days, created_at);
   ```
   (Ajusta el DDL al estilo exacto del archivo: `FOREIGN KEY`, `closing`, `_now()`, etc.)
3. **Repos** en `backend/repositories/academy.py` (o repo nuevo pequeño si el patrón lo pide):
   `insert_unit_review_attempt(...)`, `list_unit_review_attempts(user_id, level_id, unit_id,
   window_days)` y helper `latest_unit_review_attempt(...)`. Sin lógica de negocio.

### Fase C — Orquestación + endpoints (backend)

En `backend/domain/academy.py` (+ schemas en `backend/schemas/academy.py` y tipos espejo
en `frontend/src/types/api.ts`):

- `get_unit_review_plan(user_id, level_id=None)` → plan del nivel actual (o el pedido) con el
  patrón de `get_today_plan`: `lv` → `list_objective_mastery` → `_split_objective_mastery` →
  `mastered_objective_ids`; agrupa por unidad; solo unidades **completadas** o **con plan activo**
  (una unidad con al menos un intento sigue apareciendo aunque ya no esté completa); incluye
  `due_count` (unidades con ventana `due_now` o `failed`).
- `get_unit_micro_review(user_id, unit_id, window_days)` → valida unidad del nivel + calcula
  `sample_micro_review` con los fallidos del último intento de esa ventana si lo hay. Devuelve
  ítems SIN `correct_index`.
- `submit_unit_micro_review(user_id, unit_id, window_days, answers)` → puntúa (Fase A), persiste
  intento (Fase B), actualiza la carta FSRS de cada objetivo implicado con el grade derivado de su
  `accuracy` por objetivo (`fsrs.schedule` sobre la carta de la unidad/objetivo), y devuelve:
  `{correct, total, accuracy, passed, per_objective: [{objective_id, title, correct, total,
  grade, next_due_at}], plan: <plan actualizado de la unidad>}`.
- Endpoints en `backend/routers/academy.py` (estilo FSRS existente, con `current_user`):
  - `GET /api/academy/review/unit-plan` (query `level_id` opcional)
  - `GET /api/academy/review/unit/{unit_id}/micro-review` (query `window_days` int, validado ∈ 7/30/90)
  - `POST /api/academy/review/unit/{unit_id}/micro-review` (body `{window_days, answers}`)
  - Gating: 404 si la unidad no existe o no pertenece al nivel; 400 si `window_days` inválido o
    la ventana no está `due_now`/`failed` (no se puede repasar antes de tiempo salvo reintento);
    400 en answers mal formadas.
- Schemas Pydantic con docstrings. Sin lógica de negocio en routers.

### Fase D — Frontend (INICIO): bloque de repaso por unidad

- **Tipos** en `frontend/src/types/api.ts` (espejo de los schemas nuevos) y **cliente** en
  `frontend/src/api/academy.ts` (`getUnitReviewPlan`, `getUnitMicroReview`,
  `submitUnitMicroReview`, pasando `userQuery(userId)`).
- **Componente** `frontend/src/features/review/UnitReviewPanel.tsx` (o carpeta `unitReview/` si el
  árbol lo prefiere), montado en `HomeScreen.tsx` junto a `FsrsReviewPanel`:
  - Sección "Repaso por unidad": lista de unidades con sus ventanas (7/30/90) y estado
    (pendiente/para hoy/superada/fallida) con tokens de color existentes; estados vacío/carga/
    error cuidados (premisa 19); responsive (premisa 20).
  - Una unidad con ventana `due_now`/`failed` ofrece **Repasar** → abre el micro-review: tarjeta
    con un check MC del currículo a la vez (feedback inmediato y respuesta correcta revelada al
    fallar, patrón de los practices de rutas), avance `x/N`, y al terminar muestra resultado
    (accuracy + ventana superada/fallida) y refresca el plan.
  - El micro-review NO muestra "correct_index" antes de responder; puntúa el backend.
  - No declara dominio: copia honesta tipo "Repaso de retención · no cuenta como demostración".
- **i18n**: claves nuevas en `frontend/src/utils/i18n.ts` en **es y en** (el test de parity rompe
  si falta una). Cero cadenas hardcodeadas en el componente.
- **Tests**: vitest del panel nuevo (render con estado vacío, con ventana due, submit y refresh)
  con fetch mockeado; parity i18n en verde. Si hay specs Playwright de la ruta/región tocada
  (busca con `rg "FsrsReviewPanel|HomeScreen|Today" frontend --glob "*.spec.ts"`), confirma que
  siguen verdes o actualiza goldens según convención visual del repo; si no hay cobertura de esa
  región, indícalo en el informe (el gerente decide si añadir captura al cierre).

### Fase E — Verificación local (obligatoria, misma secuencia que los cierres previos)

- Backend (desde `backend/`): `python -m pytest tests/ -q` → TODO verde (1293 actuales + nuevos);
  `ruff check .` limpio. Añade `backend/tests/test_unit_review.py` (puro) y tests de dominio/
  endpoints de las Fases B–C (invariantes: siembra objective solo para unidades completadas; el
  micro-review no crea filas de evidencia del currículo; reintento prioriza fallidos; ventana no
  repasable antes de due salvo `failed`).
- Frontend (desde `frontend/`): `npm test` (vitest) verde; `npm run build` (tsc + vite) OK.
- No ejecutes la batería de Playwright completa si no tocas layout de rutas principales; SÍ
  confirma el/los spec(s) que cubran la región tocada.

## Criterios de aceptación

1. Existe `services/unit_review.py` puro y testeado; `unit_review` con ventanas 7/30/90; estados
   de ventana correctos con `now` fijo.
2. `sync_fsrs_cards` siembra/refresca cartas `target_type="objective"` solo para objetivos de
   unidades completadas del nivel actual, sin pisar cartas con `reps > 0` (solo `why`/`label`).
3. Tabla `unit_review_attempts` creada idempotente + repo; intentos persistidos con
   `per_objective` y `failed_items`.
4. Endpoints nuevos responden con gating correcto y schemas tipados; el micro-review NUNCA envía
   `correct_index` al cliente antes de responder; el servidor puntúa con la respuesta (premisa 21).
5. El micro-review no crea evidencia de mastery/currículo ni declara dominio (D5) y su copia en la
   UI lo dice con honestidad.
6. Frontend: bloque nuevo en INICIO con estados vacío/carga/error, responsive, claves i18n en es/en
   con parity verde, tests vitest verdes.
7. Docstrings en todo código nuevo o modificado (premisa 18).
8. Verificación Fase E en verde y reportada con números en el informe.

## Restricciones

- NO tocar: bump de versión, `README.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`, release-notes
  (cierre del gerente). NO tocar `docs/CONSTITUCION-PEDAGOGICA.md` (v3.16 es mecanismo, no norma).
- NO modificar el motor `fsrs.py` más allá de añadir `why_for_objective` (puro); NO cambiar
  `TARGET_TYPES`. NO tocar la lógica de mastery/evidencia del currículo ni `adaptive.today_plan`.
- Cero contenido curricular artificial: el micro-review SOLO reutiliza checks MC oficiales.
- Sin LLM por intento (premisa 21/2): todo determinista.
- Capas estrictas (routers sin lógica; servicios sin FastAPI ni BD; repos sin negocio).
- i18n completa en es/en; no duplicar cadenas hardcodeadas.
- Aislamiento por usuario en toda consulta nueva (premisa 13).

## Salida
Informe final que reporte:
1. Archivos nuevos/modificados (ruta + función/rol de 1 línea).
2. Números de la Fase E (pytest/ruff/vitest/build) y si algún test preexistente se actualizó y
   por qué (honesto).
3. Confirmación explícita de cada criterio de aceptación (1–8).
4. Cualquier desviación de las decisiones D1–D8 (si una decisión se revela inviable en código,
   párala y documéntala en el informe con la alternativa; NO la resuelvas por tu cuenta).
