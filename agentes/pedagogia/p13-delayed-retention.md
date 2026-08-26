# V1.18 (1/3) — Listening: Delayed retention (P1.2 de la auditoría V1.14)

## Rol
Subagente **full-stack** que añade la medición de **retention retardada** al diagnóstico de
listening: `immediate_accuracy` (primera exposición, Day 0) frente a `delayed_accuracy`
(re-exposición tras N días), con buckets Day 2/7/30. Es la pieza P1.2 que quedó pendiente en
V1.14 (§27.8 de `docs/RELEVO.md`). El listening ya persiste `created_at` por intento; solo falta
**derivar** la curva de retention y exponerla en el diagnóstico y en el frontend. **No se cambia
el scoring ni el banco.**

## Contexto (contratos exactos, NO romper)

### Backend — estado actual
- `backend/services/listening.py`:
  - `listening_diagnostic(attempt_rows: list[dict]) -> dict` (línea ~1289). `attempt_rows` son las
    filas de `listening_attempts` con claves: `question_id`, `answer_index`, `correct`, `skill`,
    `difficulty`, `response_time_ms`, `replay_count`, `topic`, `realized_difficulty`,
    `created_at` (ISO UTC). Devuelve `subskills`, `weak`, `recommendation`,
    `first_pass_accuracy`, `automaticity`, `by_difficulty`, `by_topic`, `trend`, `recurrence`,
    `bank_version`, `realization`.
  - Ya existe `_first_pass_rows(rows)` que devuelve la primera exposición de cada `question_id`
    (reutilízala para la precisión inmediata).
- `backend/repositories/listening.py`: `list_attempts(user_id)` devuelve las filas **incluyendo
  `created_at`** (ordenadas por `id ASC`, es decir, cronológicas). `record_attempt(...)` usa
  `_now()` de `repositories/db.py` (UTC ISO).
- `backend/services/forgetting.py`: `days_since(last_seen_at: str, now: str) -> float` — días
  entre dos timestamps ISO (0.0 si falta/inválido). **Reutilízala** para calcular días desde la
  primera exposición.
- `backend/domain/listening.py`: `get_diagnostic(user_id)` (línea ~123) llama
  `listening_diagnostic(attempts)` **sin** `now`. Tendrás que pasarle el `now` actual.
- `backend/repositories/db.py`: `_now() -> str` (UTC ISO) para el "ahora" de la API.

### Frontend — estado actual
- `frontend/src/types/api.ts`: `ListeningDiagnostic` (línea ~335) y subtipos
  (`ListeningSubskillProgress`, `ListeningTrend`, `ListeningRecurrence`,
  `ListeningRealizationSummary`). Añadirás un nuevo subtipo `ListeningRetention`.
- `frontend/src/components/ListeningPractice.tsx`: renderiza el diagnóstico (~líneas 239-311),
  con bloques por sub-destreza, tendencia, `by_topic`, `by_difficulty` y `recurrence`. Añadirás
  un bloque de retention con el mismo estilo.
- `frontend/src/index.css`: clases `.listening-*` existentes (`.listening-breakdown`,
  `.listening-pills`, `.listening-pill`, etc.).

## Objetivo
Añadir `delayed_retention(attempt_rows, now="")` en `services/listening.py`, integrarlo en
`listening_diagnostic`, exponerlo en el schema `ListeningDiagnostic` y mostrarlo en el frontend.

## Tarea

### 1. Backend — `services/listening.py`
Añade una función pura y testeable:

- `delayed_retention(attempt_rows: list[dict], now: str = "") -> dict`
  - Agrupa las filas por `question_id`. La **primera exposición** (fila más antigua por
    `created_at`) es `immediate` (Day 0). El resto son re-exposiciones (`delayed`).
  - `immediate_accuracy`: % de acierto entre las primeras exposiciones (todas las preguntas
    vistas). `None` si no hay ninguna.
  - `delayed_accuracy`: % de acierto entre las re-exposiciones con **≥ 2 días** desde su primera
    exposición. `None` si no hay ninguna.
  - `retention_rate`: `delayed_accuracy / immediate_accuracy` redondeado a 3 decimales, o `None`
    si alguno de los dos es `None` o `immediate_accuracy == 0`.
  - `by_bucket`: lista de `{bucket, attempts, correct, accuracy}` ordenada, con buckets de días
    desde la primera exposición:
    - `"0-2"`  → `0 <= days < 2`
    - `"2-7"`  → `2 <= days < 7`
    - `"7-30"` → `7 <= days < 30`
    - `"30+"`  → `days >= 30`
    Solo incluye re-exposiciones (excluye la primera exposición de cada pregunta). Omite filas sin
    `created_at`. `accuracy` = `round(correct/attempts*100, 1)`; `None` si `attempts == 0` (no
    incluir buckets vacíos).
  - `total_questions`: nº de preguntas distintas con al menos una exposición.
  - `now` default `""` significa "usar el máximo `created_at` de las filas"; si no hay filas,
    devolver el dict vacío sin error. Si `now` viene relleno (string ISO), úsalo como referencia
    (patrón de `forgetting.days_since`). Reutiliza `from services.forgetting import days_since`
    para el cálculo de días.
  - Documenta con docstring el propósito y la definición exacta de cada bucket.

- Modifica `listening_diagnostic(attempt_rows, now="")` añadiendo `now: str = ""` como keyword
  (compatible hacia atrás: los tests existentes que la llaman sin `now` siguen pasando) y añade
  `"retention": delayed_retention(attempt_rows, now)` al dict devuelto.

### 2. Backend — `schemas/listening.py`
Añade:
- `ListeningRetentionBucket { bucket: str, attempts: int, correct: int, accuracy: float | None }`.
- `ListeningRetention { total_questions: int, immediate_accuracy: float | None,
  delayed_accuracy: float | None, retention_rate: float | None,
  by_bucket: list[ListeningRetentionBucket] }`.
- Añade `retention: ListeningRetention` a `ListeningDiagnostic` (campo requerido).

### 3. Backend — `domain/listening.py`
En `get_diagnostic(user_id)` pasa el `now` actual: `listening_diagnostic(attempts, now=db._now())`.
Añade `from repositories import db` (o el import que corresponda) para `_now`. No cambies la
firma pública del endpoint.

### 4. Frontend — `types/api.ts`
Añade:
- `ListeningRetentionBucket { bucket: string; attempts: number; correct: number;
  accuracy: number | null }`.
- `ListeningRetention { total_questions: number; immediate_accuracy: number | null;
  delayed_accuracy: number | null; retention_rate: number | null;
  by_bucket: ListeningRetentionBucket[] }`.
- Añade `retention: ListeningRetention` a `ListeningDiagnostic`.

### 5. Frontend — `components/ListeningPractice.tsx`
Renderiza un bloque de retention dentro del bloque `diagnostic` (después de `recurrence`, antes
del cierre), coherente con los estilos existentes:
- Texto tipo: "Retention: {immediate}% inmediata → {delayed}% retardada" (o "—" si `null`).
- Si `retention_rate !== null`, muestra el ratio como % con signo/color según sea alto (>=90%),
  medio o bajo.
- Lista de buckets: `{bucketLabel(bucket)} · {accuracy}%` (p. ej. `0-2 · 80%`), reutilizando las
  clases `.listening-pills`/`.listening-pill` o equivalentes. Solo si `by_bucket.length > 0`.
- Añade un helper local `retentionBucketLabel(bucket: string): string` (p. ej. `"0-2"` → "0–2
  días", `"2-7"` → "2–7 días", `"7-30"` → "7–30 días", `"30+"` → "más de 30 días").
- Añade clases `.listening-retention-*` en `index.css` si necesitas algo nuevo; reutiliza tokens
  de color (tema claro/oscuro, premisa 14).

### 6. Tests

#### Backend (pytest)
- Nuevo `backend/tests/test_listening_retention.py` (o amplía `test_listening.py`): tests de
  `delayed_retention` con filas sintéticas y `created_at` controlados (ej. `now` fijo ISO):
  - Sin filas → dict vacío (o con `total_questions=0`, precisiones `None`, `by_bucket=[]`).
  - Una sola exposición por pregunta → `immediate_accuracy` correcta, `delayed_accuracy=None`,
    `retention_rate=None`, `by_bucket=[]`.
  - Re-exposición a 1 día → bucket `"0-2"` (no cuenta como delayed ≥2 días).
  - Re-exposición a 3, 10 y 40 días → buckets `"2-7"`, `"7-30"`, `"30+"` correctos y
    `delayed_accuracy`/`retention_rate` calculados.
  - Verifica que la primera exposición **no** entra en `by_bucket`.
- Amplía `test_diagnostic_endpoint` (o añade uno nuevo) para comprobar que
  `GET /api/listening/diagnostic` devuelve `retention` con la estructura esperada.

#### Frontend (vitest)
- No hay helper nuevo obligatorio; si añades `retentionBucketLabel` como util exportado, testéalo.
  En caso de dejarlo local al componente, no hace falta test unitario. Asegúrate de que `tsc`
  pase.

## Criterios de aceptación
- Backend: `pytest` en verde + `ruff` limpio. Frontend: `npx tsc --noEmit` + `npx vitest run`
  en verde.
- `delayed_retention` es puro, determinista y testable (toma `now` explícito).
- La precisión inmediata usa la **primera** exposición por pregunta; la retardada usa
  re-exposiciones a ≥2 días, agrupadas en buckets 0-2/2-7/7-30/30+.
- No se altera el scoring, el banco ni los endpoints existentes (solo se añade `retention`).
- Frontend muestra el bloque de retention con estados vacío (todo `null`) sin romper.
- Todo nuevo con docstrings/JSdoc (premisa 18).

## Restricciones
- Reutiliza `services.forgetting.days_since` para el cálculo de días; no reinventes parsing de
  fechas.
- No rompas tests existentes; no introduzcas dependencias nuevas.
- Crea **un único commit `feat:`** descriptivo (no hagas push).

## Salida
- Diff backend + frontend, y salida de pytest/ruff, tsc y vitest en verde.
