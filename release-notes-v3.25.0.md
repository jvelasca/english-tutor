# v3.25.0 — Calibración del Student Model: evidencia con contexto, transfer por experiencias y semántica demostrado/estimado

**El plan V3.25 (derivado de la auditoría TOTAL verificada de V3.24.0 — dossier
`docs/audit/L-AUDITORIA-TOTAL-V324.md`) absorbe los pendientes F-K3…F-K7 que
V3.24 declaró fuera de alcance y los convierte en la fase de calibración del
Student Model: la evidencia se escribe como evento con contexto (tarea,
actividad, `support_level`), el `transfer` del gate MASTERED exige experiencias
**distintas** (no filas repetidas del mismo contexto), la certificación verifica
la retención demorada desde las filas (con reporte de intervalos), la UI separa
el nivel **demostrado** del **estimado**, y la pila léxica se renombra al
dominio canónico con unidad léxica real.**

## Qué cambia

### Fase 1 — Modelo de eventos con contexto (base de todo el incremento)

- `academy_evidence` gana `context_id`/`activity_id`/`task_type`/`support_level`
  con migración idempotente e índice `idx_evidence_context`
  (`repositories/db.py`).
- `record_evidence` y `evidence_from_items` enriquecen cada evento; los 10
  emisores pasan un `context` con su tarea/actividad. Los agregados
  (`evidence_count`, `evidence_by_kind`, `generalized_mastery_score`) se siguen
  derivando igual: no se rompe ningún contrato.
- Las filas legacy (sin contexto) siguen contando por nº de filas; las nuevas
  permiten responder "¿cuántas experiencias distintas?".

### Fase 2 — `support_level` canónico por emisor (P1-01)

- Enumerado `copied/guided/cued/independent/spontaneous`
  (`SUPPORT_LEVELS` en `services/academy.py`) y persistido en el evento.
- Mapa por emisor: formative → `guided`/`cued`, objective assessment → `cued`,
  speaking assessment y misión → `independent`, chat libre → `independent`,
  read-aloud → `guided`, comprensión → `cued`.
- `build_skill_profile` expone por destreza `support_levels` y
  `independent_count` (la evidencia "independiente" queda separable en el perfil
  para mastery y UI).

### Fase 3 — Transfer por contextos/tareas distintos + desambiguación F-K5 (P1-02)

- `mastery_evidence_gate`, `adaptive.readiness`, el unit gate de `course` y los
  pesos de evidence_graph cuentan **experiencias distintas**
  (`evidence_context_count`/`effective_evidence_context_count`, con fallback a
  nº de filas para datos legacy).
- Dos transfers del mismo contexto/tarea ya **no** satisfacen `transfer ≥ 2`;
  un `familiar` repetido en el mismo contexto no duplica experiencia
  independiente.
- Documentada en schemas la colisión semántica `transfer`/`delayed` académicos
  (evidencia de Assessment 2.0) vs `transfer`/`retention` léxicos
  (`LexicalCompetence`).

### Fase 4 — Retention longitudinal verificada (P1-03)

- `certification_gate` deja de confiar en la mera existencia de `delayed`:
  verifica `created_at` por fila (rechaza la evidencia sin fecha) y emite
  `retention_report` con los intervalos alcanzados (`RETENTION_INTERVALS`
  D+1/D+3/D+7/D+21) calculados desde los timestamps.

### Fase 5 — Semántica UI demostrado vs estimado (P1-04 + F-K4 parcial)

- El Student Model separa `demonstrated_level` (máximo nivel certificable:
  examen aprobado + `delayed` verificable, `_demonstrated_level`),
  `estimated_level` (anclado de V3.24) y `level_progress` del tramo actual.
- El header de Progreso los muestra sin ambigüedad ("demostrado" / "en nivel X")
  con claves i18n nuevas (`progress.certified*`, `progress.inLevel*`); la UI ya
  consumía `estimated_band` por destreza.

### Fase 6 — Renombrado canónico + unidad léxica (F-K7/P2-01/P2-02)

- Migración idempotente `occurrences → appearances → production_count` y
  `exposures → exposure_count` en `vocabulary`, con retrocompatibilidad de
  lectura en `services/lexicon.py` (`production_count`/`exposure_count`
  accesores) y toda la pila actualizada: repo, schemas, servicios, dominio y
  frontend (`types/api.ts`, fixtures).
- Columna `lexical_unit` (lema o superficie normalizada) poblada en
  `record_production`/`record_exposures`/`seed_curriculum_items`: `go/going/
  went/gone` dejan de tratarse como conocimientos independientes.
- Decisión `novel` confirmada: el kind sigue **reservado** (sin emisor real) y
  fuera de los requisitos del gate MASTERED.

### Fase 7 — Doble vía speaking con `cefr_target` persistido (F-K3)

- `speaking_mission_sessions` gana la columna `cefr_target` (migración
  idempotente con backfill desde `mission_json` para instalaciones previas).
- La vía **assessment** (`context_id: speaking_assessment:<session>`) y la vía
  **misión** (`context_id: mission:<scenario>`) declaran su evidencia con
  `support_level = independent`, habilitando `novel` real en el futuro si una
  modalidad lo emite.

## Técnica

- Backend (versión de app `3.24.0 → 3.25.0`, fuente única `backend/config.py`):
  - `repositories/db.py`: columnas de contexto en `academy_evidence` + índice;
    columna `cefr_target` en `speaking_mission_sessions`; migraciones
    idempotentes de `vocabulary` (renombrados + `lexical_unit`).
  - `services/academy.py`: `SUPPORT_LEVELS`, `TASK_TYPES`,
    `evidence_context_count`, `effective_evidence_context_count`,
    `evidence_from_items` con contexto, `build_skill_profile` enriquecido.
  - `services/assessment_v2.py`: `mastery_evidence_gate` con contextos
    distintos; `certification_gate` verificado por `created_at` +
    `retention_report` (`RETENTION_INTERVALS`).
  - `services/adaptive.py`: readiness con contextos efectivos.
  - `services/course.py` y `services/evidence_graph.py`: transfer por contextos.
  - `domain/academy.py`: eventos con contexto en los 10 emisores;
    `demonstrated_level`/`level_progress` en `build_student_model`;
    `cefr_target` en las sesiones de misión.
  - `services/lexicon.py` y resto de la pila léxica: acceso
    `production_count`/`exposure_count`/`lexical_unit`.
  - Re-apuntado de tests y fixtures: nuevo `tests/test_evidence_context.py`,
    casos de renombrado/migración léxica y de misión con `cefr_target`.
- Frontend: tipos (`types/api.ts`) y header de Progreso con la semántica
  demostrado/estimado; fixtures de tests actualizadas.
- Docs: `PLAN.md`, `CHANGELOG.md`, `README.md`, `docs/RELEVO.md`,
  dossier L (`docs/audit/L-AUDITORIA-TOTAL-V324.md`).

## Tests

- Backend: **1481 pytest en verde** (modelo de eventos con contexto, gate
  MASTERED con contextos distintos, readiness, certification por intervalos,
  Student Model demostrado/estimado/progreso, migraciones léxicas y de misión,
  e2e del salto A1→A2); `ruff check .` limpio.
- Golden: `tests/test_golden_*.py` (incl. `thresholds.json`) en verde.
- Frontend: vitest **450 passed** (57 archivos); `tsc` y `vite build` OK.
- `scripts/check_release_consistency.py` exit 0 (3.25.0).

## Fuera de alcance (fronteras documentadas)

- Emisor real del kind `novel` (uso en contexto nunca practicado): sigue sin
  existir; `novel` permanece reservado con requisito 0. La infraestructura de
  contexto + `support_level` de esta versión es la base para emitirlo cuando
  exista una modalidad que lo justifique (candidato V3.26+, con la doble vía
  speaking ya capaz de declarar `independent`).
- Calibración progresiva de la CEFR matrix para vocabulary/grammar/interaction/
  mediation (P2-03) y listening real (recognition/comprehension/inference,
  P2-04): fuera de V3.25 (V3.26+).
