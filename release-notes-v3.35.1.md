# v3.35.1 — Cierre de la auditoría V3.35.0: integridad del ledger de evidencia y fuga de la palabra en Recall

**Patch quirúrgico del modelo de evidencia longitudinal tras la auditoría
externa de V3.35.0: el intervalo guardado vuelve a significar lo que dice su
contrato, la secuencia de intervalos deja de reordenarse por valor, la cola de
repaso deja de revelar la palabra antes de un Recall/Sentence y
`record_evidence_bulk` protege el ledger contra lotes degenerados.**
Versión de app `3.35.0 → 3.35.1`. Backend + frontend + docs; sin cambios de
esquema de BD, sin migración y sin contrato HTTP nuevo.

## Contexto

La auditoría de V3.35.0 dio **9,5/10** y confirmó que los dos P1 de V3.34.0
(ancla de retención encadenada y separación Review Queue / Speaking Drill) están
bien cerrados, pero encontró **dos P1 nuevos de integridad del modelo
longitudinal** y **un P1 pedagógico**, más dos P2. Este patch los cierra sin
tocar la arquitectura base (React/Vite, FastAPI, SQLite, FSRS, routers,
`current_user`, Recognition, separación Review Queue / Speaking Drill).

## Qué cambia

### 1. P1-01 — `interval_since_last_evidence` significa lo que dice (`domain/vocabulary.py`)

El campo se define como *intervalo desde la EVIDENCIA anterior del mismo ítem*,
pero `_record_retrieval` y `submit_recall_attempt` escribían el
`decision["interval_days"]` de `delayed_retrieval_decision`, que es el hueco
desde el **ancla de retención** (última recuperación válida / FSRS `due_at`).
Son dos conceptos distintos.

Escenario real del audit:

```
t0  producción   → evidencia
t1  recall       → ancla de retención = t1
t2  producción   → evidencia (no mueve el ancla)
t5  retrieval    → decisión: 4 días desde t1; evidencia: 3 días desde t2
```

Antes se podía guardar `4` en un campo cuyo contrato dice `3`. Ahora:

- `_record_retrieval` y `submit_recall_attempt` **no pasan** intervalo;
- `repositories/evidence.record_evidence` lo deriva SIEMPRE de
  `last_evidence_at()` (`learning_evidence → learning_evidence`);
- el intervalo de retención (`interval_days`, `required_days`, `credited`) se
  queda en la decisión y NO se persiste como intervalo de evidencia (no se
  añaden columnas: queda para V3.36 si se decide conservarlo).

### 2. P1-02 — Los intervalos conservan el orden cronológico (`services/evidence.py`, `repositories/evidence.py`)

`summarize_evidence` hacía `intervals.sort()` y `summarize_by_target` ordenaba
por `interval_since_last_evidence`. `[1, 7, 3, 14]` se convertía en
`[1, 3, 7, 14]`: se perdía la historia.

- `summarize_evidence` ya no ordena: respeta el orden de las filas recibidas.
- `summarize_by_target` ordena por `occurred_at ASC, id ASC` (cronología real).
- La secuencia queda como la cadena que el scheduler podrá leer; las
  estadísticas derivadas (media/mediana/mín/máx) se dejan para V3.36.

### 3. P1-03 — La cola de repaso no revela la palabra en Recall/Sentence (`ReviewQueueSection.tsx`, `i18n.ts`)

«Repaso de hoy» mostraba `word + activity + reason` antes de abrir el drill.
Para `recall` eso spoileaba justo la recuperación que se quería medir.

- `recognition` → muestra la palabra (el objetivo ES reconocerla);
- `recall` → etiqueta neutra (`Word hidden — recall from meaning`) y botón sin
  la palabra en el `aria-label`;
- `sentence` → etiqueta neutra (`Word hidden — produce it in a sentence`).

El `WordDrill` ya ocultaba la diana en Recall (`hideTarget`), así que la cola
era la única fuga.

### 4. P2-02 — `record_evidence_bulk` a prueba de lotes degenerados (`repositories/evidence.py`)

Dos entradas del mismo target en un lote podían compartir el `previous` leído de
la BD. Ahora:

- **dedupe** por `(target_type, target_id, task, activity, occurred_at)`: dos
  entradas idénticas del mismo evento insertan UNA fila;
- **cadena secuencial**: el lote se procesa en orden cronológico y `previous` se
  actualiza en memoria tras cada fila, así que dos eventos distintos del mismo
  target encadenan su intervalo real;
- `occurred_at` admitido por entrada (antes solo a nivel de lote).

## Verificación

- Backend: `ruff check .` limpio y `pytest` → **1769 passed** (+5 sobre
  v3.35.0).
- Frontend: `tsc --noEmit` limpio y `vitest` → **65 ficheros/558 tests** (+1).
- `python scripts/check_release_consistency.py` → **3.35.1** exit 0.

## Documentación

- `CHANGELOG.md`: entrada `[3.35.1]`.
- `PLAN.md`: hito V3.35.1 al frente de «Estado actual» y candidato V3.36
  (Learning Evidence 2.0) en «Siguiente incremento».
- `docs/RELEVO.md`: nota de cierre al frente.

## Fuera de alcance (V3.36)

`support_level`, `difficulty`, `response_time_ms`, `error_type`,
`context_id`/`activity_id`, escalera de cues graduados (translation → definition
→ cloze → situación → free recall) y estadísticas derivadas del ledger.
