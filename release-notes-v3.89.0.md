# Release notes — English Tutor v3.89.0

**Fecha:** 2026-09-29 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.88.0 → 3.89.0`

**Con backend y frontend, CON migración de BD aditiva e idempotente** (nueva tabla
`listening_review_queue`, nueva columna `outcome` en `listening_attempts` y un índice por usuario),
**CON tres endpoints nuevos** (`GET /api/listening/review-queue`,
`POST /api/listening/review-queue/{question_id}/defer`,
`DELETE /api/listening/review-queue/{question_id}`) y **SIN bump** de `GENERATOR_VERSION` (sigue
`1.6.0`) ni de `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) ni de
`LISTENING_BANK_VERSION`. **No se añade ni se retira gate** —siguen los **ocho**, todos en
`pending`— y `docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** En Listening, fallar deja de ser un bucle: se **registra** con su desenlace, se
**explica**, se puede **continuar** y el ítem entra en una **cola de repaso propia** con su
prioridad y su próxima fecha, porque el fallo es **evidencia**, no una barrera de navegación.

---

## 1. El bucle no estaba donde parecía (lo que se verificó antes de tocar nada)

El «reintentar hasta acertar» de Listening **no era del backend**: `submit_answer` solo puntuaba y
persistía. El reintento de la misma pregunta vivía en el **frontend** y existía **una sola vez** en
A1/A2; el «hasta acertar» real era el **drill** de fallidos, **en memoria** y **sin persistencia**.

De ahí el recorte de esta release: no reescribir el motor de ejercicios, sino quitar el bucle de la
interfaz, **acotarlo** (una repetición), **dar salidas explícitas** y **persistir el fallo** para que
sobreviva a la sesión.

## 2. Tres salidas explícitas al fallo (y ninguna obliga a acertar)

Ante un fallo, la vista de práctica ofrece tres acciones:

- **`Continuar`** — el ítem se cierra como fallado y la sesión avanza.
- **`Repasar ahora`** — **como máximo una** repetición inmediata (no hay segunda).
- **`Repasar después`** — el ítem se va a la cola sin gastar un reintento.

En `frontend/src/features/listening/microFlow.ts`, el fallo **ya no fuerza la salida**:
`completeStageWithAnswer` se queda en el escenario de respuesta revelando la transcripción cuando la
política lo pide, `retriesRemain` consulta el tope real y `skipAnswerStage` permite **avanzar sin
acertar**. La revelación pedagógica (`on_first_fail`) se conserva: el apoyo sigue apareciendo al
primer fallo, lo que cambia es que **no secuestra la navegación**.

Y el drill deja de ser infinito: `frontend/src/features/listening/listeningSession.ts`
(`drillAnswered`) **suelta la frase al responderla**, acierte o falle, así que el drill **termina con
pendientes** en vez de repetir la misma frase.

## 3. La cola es propia, persistente y no es FSRS

> **Objeto pedagógico distinto.** Listening no entra en FSRS como flashcards: la cola es de
> **ejercicios/frases**, con su propio espaciado. El puente hacia FSRS —como **evidencia de
> dificultad**, nunca como tarjeta— es el objeto de **V3.92** y **no** se adelanta aquí.

**Migración aditiva e idempotente** en `backend/repositories/db.py`:

- Tabla `listening_review_queue` con `PK(user_id, question_id)` y columnas `level`, `skill`,
  `task_type`, `fail_count`, `last_failed_at`, `next_review_at`, `priority`, `state`,
  `created_at`, `updated_at`.
- Columna `outcome` en `listening_attempts`, para dejar por escrito **cómo** se resolvió:
  `correct_first` / `correct_retry` / `wrong` / `hint_used` / `solution_shown`.
- Índice `idx_listening_review_queue_user` sobre `(user_id, state, priority)`.

**La política es un módulo puro y testeable sin BD** (`backend/services/listening_review.py`):

- `outcome_for` clasifica el desenlace.
- `can_retry_immediately` acota la repetición inmediata (**tope = 1**).
- `review_interval_hours` programa la reapertura con espaciado propio: **24 h → 72 h → 168 h →
  336 h**.
- `priority` ordena la cola de forma **determinista**: número de fallos + ventana de recencia +
  peso pedagógico del skill.

**Repositorio** (`backend/repositories/listening.py`): `enqueue_failure`, `get_queue_entry`,
`list_queue`, `due_queue`, `mark_queue_reviewed`, `defer_queue_entry`, `queue_fail_counts`.

**Y la plomería de producto**: `submit_answer` **encola el fallo** automáticamente y devuelve
`outcome`, `queued_for_review` e `immediate_retry_available`, de modo que el frontend **no improvisa
política**; un acierto posterior **resuelve** la entrada de la cola (deja de estar pendiente).

## 4. La cola se ve

- **Por nivel** (`ListeningLevelPanel`): «Repaso pendiente: N» con acción para practicar lo pendiente.
- **En la práctica** (`ListeningPractice`): resumen del total pendiente y de cuántas entradas **vencen
  hoy**.
- Cadenas nuevas en `frontend/src/utils/i18n.ts` (es/en) y `check_i18n_coverage --strict` en verde.

## 5. Contrato de API

| Método y ruta | Para qué |
|---|---|
| `GET /api/listening/review-queue` | Cola pendiente del usuario, ordenada por prioridad |
| `POST /api/listening/review-queue/{question_id}/defer` | «Repasar después»: pospone sin gastar reintento |
| `DELETE /api/listening/review-queue/{question_id}` | Resuelve la entrada (la saca de pendientes) |
| `POST /api/listening/answer` (ampliado) | Encóla el fallo y devuelve `outcome` / `queued_for_review` / `immediate_retry_available` |

Los campos del request (`attempt_number`, `hint_used`, `solution_shown`) y de la respuesta
(`outcome`, `queued_for_review`, `immediate_retry_available`) son **aditivos**: el contrato anterior
sigue siendo válido.

## 6. Verificación

| Puerta | Resultado |
|---|---|
| `ruff check .` (backend y launcher) | limpio |
| `pytest` backend | **3231 passed** (incluye `test_listening_review_queue_v389.py`: migración, política pura, repositorio y API) |
| `vitest run` | **1081 passed** (111 ficheros) |
| `tsc --noEmit` | limpio |
| `npm run build` | correcto |
| `check_i18n_coverage.py --strict` | 0 huérfanas · 0 sin definir |
| `contrast_audit.mjs --strict` | 480 pares + 6 guardas · **0 bloqueantes** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.89.0`) |

Tests añadidos o ampliados: `backend/tests/test_listening_review_queue_v389.py` (nuevo),
`frontend/src/features/listening/microFlow.test.ts` y
`frontend/src/features/listening/listeningSession.test.ts`.

## 7. Honestidad: lo que NO trae

- **Listening NO entra en FSRS.** La cola es de ejercicios, no de vocabulario. El puente de
  dificultad es V3.92.
- **La práctica de lo pendiente reutiliza la selección por nivel en modo `failed`.** No hay
  navegador de cola propio: la cola se **consume**, no se **gestiona** (no hay listado paginado,
  reordenar ni filtrar por skill).
- **La cola es por usuario** y vive en SQLite local, como el resto del progreso.
- **Los ocho gates humanos siguen `pending`** y `docs/audit/validation-evidence.json` sigue sin
  existir.

## 8. Archivos tocados (resumen)

- **Backend:** `repositories/db.py`, `repositories/listening.py`, `services/listening_review.py`
  (nuevo), `domain/listening.py`, `schemas/listening.py`, `routers/listening.py`.
- **Frontend:** `types/api.ts`, `api/listening.ts`, `features/listening/microFlow.ts`,
  `features/listening/listeningSession.ts`, `features/listening/ListeningPractice.tsx`,
  `features/listening/ListeningLevelPanel.tsx`, `utils/i18n.ts`.
- **Tests:** `backend/tests/test_listening_review_queue_v389.py` (nuevo),
  `features/listening/microFlow.test.ts`, `features/listening/listeningSession.test.ts`.
- **Versión y docs:** `backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
  `README.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`, `docs/audit/PARKED.md`.

## Para auditar esta release

1. Provocar un fallo en Listening y comprobar las **tres acciones** y que «Repasar ahora» **no** se
   ofrece por segunda vez.
2. Comprobar que `Continuar` **avanza** sin acertar y que el drill **termina** con pendientes.
3. Ver `GET /api/listening/review-queue` con orden por prioridad y `next_review_at` coherente con el
   intervalo (24/72/168/336 h).
4. Repetir la migración (abrir la BD dos veces) y confirmar que es **idempotente**.
5. Acertar la pregunta fallada y confirmar que la entrada **sale** de pendientes.
