# P4 — Listening como competencia (dificultad / tema / tendencia / reincidencia)

## Rol
Subagente full-stack que convierte la práctica de listening de un "contador de intentos" en una
señal de **competencia** real: añade la dimensión de **tema** (`topic`) y métricas deterministas de
**precisión por dificultad**, **precisión por tema**, **tendencia reciente** y **reincidencia**
(reintentos y recuperación), sin LLM y sin red.

## Contexto
Hoy `listening_attempts` ya guarda `correct`, `skill`, `difficulty` (derivada del vector de 8
dimensiones), `response_time_ms` y `replay_count`, y `services/listening.py::listening_diagnostic`
ya expone un perfil por sub-destreza con `first_pass_accuracy`, `automaticity` y `review_due`.

Lo que falta (hueco real de P4, ver `docs/PLAN-ETAPA-PEDAGOGICA.md`):
1. **Tema (`topic`)**: los ítems del banco no declaran tema, y los intentos no lo guardan.
2. **Precisión por dificultad**: el diagnóstico agrupa por sub-destreza, no por dificultad.
3. **Precisión por tema**: inexistente (no hay tema).
4. **Tendencia reciente**: no se compara la precisión reciente con la anterior.
5. **Reincidencia**: no se mide el reintento de la misma pregunta ni su recuperación.

Arquitectura congelada (`routers → domain → repositories → SQLite`; `services` puros). Este cambio
es aditivo: no rompe endpoints existentes, solo añade campos a las respuestas de diagnóstico.

## Archivos (backend)
- `backend/services/listening.py` (puro)
- `backend/repositories/db.py` (migración idempotente de `topic`)
- `backend/repositories/listening.py`
- `backend/domain/listening.py`
- `backend/schemas/listening.py`
- Tests: `backend/tests/test_listening.py`, `backend/tests/test_listening_architecture.py`

## Tarea

### 1. Taxonomía de temas (`services/listening.py`)
- Añadir `LISTENING_TOPICS` (tupla canónica, en minúscula y snake_case):
  `daily_routine`, `shopping`, `travel`, `work`, `weather`, `free_time`, `food`,
  `education`, `sports`, `functional`.
- Añadir `topic: str = ""` a `ListeningAsset` y un campo `"topic"` a **cada** ítem de
  `QUESTION_BANK` con un valor de `LISTENING_TOPICS` (mapeo razonable según el contenido del
  script). Ej.: `l1` → `daily_routine`, `l2`/`l4`/`l16` → `shopping`, `l5`/`l9`/`l23` → `travel`,
  `l6`/`l14`/`l15` → `work`, `l22` → `weather`, `l13`/`l17`/`l21` → `free_time`,
  `l11`/`l20` → `food`, `l8`/`l12` → `education`, `l3`/`l7` → `sports`, `l19` → `functional`,
  `l10`/`l18` → `daily_routine`.
- En `validate_listening_bank`, exigir que `topic` pertenezca a `LISTENING_TOPICS` (error
  `"{id}: invalid topic {topic!r}"` si no).

### 2. Métricas puras y deterministas (`services/listening.py`)
Añadir funciones puras (reutilizando `_accuracy`), todas tolerantes a filas sin el campo:
- `accuracy_by_difficulty(rows) -> list[dict]`: agrupa por `difficulty`, devuelve
  `{difficulty, attempts, correct, accuracy}` ordenado por dificultad ascendente. Omite filas sin
  dificultad.
- `accuracy_by_topic(rows) -> list[dict]`: agrupa por `topic`, devuelve
  `{topic, attempts, correct, accuracy}` ordenado alfabético. Omite `topic` vacío.
- `recent_trend(rows, window=TREND_WINDOW) -> dict` (con `TREND_WINDOW = 10`): compara la
  precisión de los últimos `window` intentos (orden cronológico, `rows[-window:]`) con la de los
  anteriores (`rows[:-window]`). Devuelve `{recent_accuracy, prior_accuracy, delta, direction}`
  con `direction` en `{"up","down","flat","n/a"}` (`n/a` si no hay datos o no hay ventana previa).
- `recurrence_stats(rows) -> dict`: agrupa por `question_id` y devuelve
  `{questions_seen, retried, recovered, retry_rate, recovery_rate}` donde `retried` = preguntas
  con más de un intento, `recovered` = preguntas falladas al menos una vez y luego acertadas,
  `retry_rate = retried/questions_seen`, `recovery_rate = recovered/retried` (`None` si el
  denominador es 0).
- Extender `listening_diagnostic` para devolver, además de lo actual, `by_difficulty`,
  `by_topic`, `trend` y `recurrence` (calculados con las funciones anteriores sobre las mismas
  filas).

### 3. Persistencia (`repositories/db.py` y `repositories/listening.py`)
- En `db.py`, migración idempotente: `ALTER TABLE listening_attempts ADD COLUMN topic TEXT NOT
  NULL DEFAULT ''` (junto a las migraciones existentes de `skill`/`difficulty`/etc.).
- En `listening.py`: `record_attempt(..., topic: str = "")` inserta `topic`;
  `list_attempts` añade `topic` al `SELECT`.

### 4. Dominio y esquemas
- `domain/listening.py::submit_answer`: pasar `question.get("topic", "")` a `record_attempt`.
- `schemas/listening.py`: añadir `topic: str = ""` a `ListeningQuestion`; nuevas clases
  `ListeningDifficultyOut`, `ListeningTopicOut`, `ListeningTrend`, `ListeningRecurrence`; extender
  `ListeningDiagnostic` con `by_difficulty`, `by_topic`, `trend`, `recurrence`.

### 5. Frontend
- `frontend/src/types/api.ts`: `topic` en `ListeningQuestion`; nuevas interfaces
  `ListeningDifficultyProgress`, `ListeningTopicProgress`, `ListeningTrend`, `ListeningRecurrence`;
  extender `ListeningDiagnostic`.
- `frontend/src/components/ListeningPractice.tsx`: mostrar, bajo el diagnóstico por sub-destreza,
  la precisión por tema, la precisión por dificultad, la tendencia reciente (sube/baja/estable) y
  la reincidencia (reintentos/recuperados). Responsive, con tokens y estados vacíos.
- Tests: actualizar/ampliar `frontend/src/api/listening.test.ts` si se afirma la forma del
  diagnóstico (los mocks son `unknown`, así que basta con no romperlos).

### 6. Tests backend
- `test_listening.py`: `accuracy_by_difficulty`, `accuracy_by_topic`, `recent_trend`,
  `recurrence_stats` (casos: vacío, agrupación, ventana, recuperación, denominador 0).
- `test_listening_architecture.py`: `validate_listening_bank` detecta `topic` inválido; el banco
  declara `topic` válido en todos los ítems.
- Comprobar que `listening_diagnostic` incluye las claves nuevas y que el endpoint
  `/api/listening/diagnostic` las expone.

## Criterios de aceptación
- Backend `pytest` verde + `ruff check .` limpio; frontend `tsc --noEmit` + `vitest run` verdes.
- Los endpoints existentes no cambian de contrato (solo añaden campos).
- Todo determinista, sin LLM ni red; tests rápidos.

## Restricciones
- No tocar `services/curriculum.py`, `services/adaptive.py` ni los endpoints de Academy.
- No migrar datos históricos más allá de `DEFAULT ''` (los intentos legacy quedan sin tema).
- Mantener los docstrings (premisa 18).

## Salida
- Diff backend + frontend + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde.
