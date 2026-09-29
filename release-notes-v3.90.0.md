# Release notes — English Tutor v3.90.0

**Fecha:** 2026-09-29 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.89.0 → 3.90.0`

**Con backend y frontend, CON migración de BD aditiva e idempotente** (cinco columnas nuevas en
`learning_goal` y tres en `session_completions`), **CON un endpoint nuevo**
(`GET /api/academy/daily-plan`) más `GET`/`PUT /api/academy/goal` **ampliados** y **SIN bump** de
`GENERATOR_VERSION` (sigue `1.6.0`) ni de `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue
`1.3.1`) ni de `LISTENING_BANK_VERSION`. **No se añade ni se retira gate** —siguen los **ocho**,
todos en `pending`— y `docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** El objetivo diario deja de ser solo «más o menos minutos»: se puede declarar por
**unidades**, por **tiempo** o por **las dos cosas**, el motor aplica **repaso antes que nuevo**, el
plan sirve **lo que falta** (y no el cupo entero otra vez) y la Home publica una **barra de
progreso** con los repasos pendientes **separados por su origen** y una **estimación honesta** de
los minutos.

---

## 1. Lo que se verificó antes de tocar nada

El objetivo diario **ya existía**, pero solo en minutos: `learning_goal.minutes_per_day` (5–180),
editable en Home y consumido por el Session Engine como `budget_minutes`. Lo que **no** existía:
unidades de trabajo, mezcla explícita nuevo/repaso, tope de material nuevo, destrezas incluidas,
métricas del día y una lectura del progreso que pudiera llegar al 100 %.

De ahí el recorte: **no** un subsistema paralelo de planificación, sino **extender la única fuente
de verdad** que ya presupuestaba la sesión.

## 2. Decisión: extender `learning_goal` (y no un «Plan diario» aparte)

> **Por qué.** Un segundo objeto de configuración habría duplicado la fuente de verdad del
> presupuesto: el Session Engine lee `learning_goal`, y dos orígenes divergen el día que uno de los
> dos se edita.

**Migración aditiva e idempotente** en `backend/repositories/db.py`:

- `learning_goal`: `plan_mode` (`time`|`units`|`mixed`), `target_units` (0–12), `max_new` (0–5),
  `include_listening`, `include_speaking`. Además del `ALTER TABLE` idempotente, las columnas van
  también en el `CREATE TABLE` de las instalaciones nuevas.
- `session_completions`: `kind`, `skill`, `minutes`.

Los valores por defecto **conservan el comportamiento anterior**: `time`, sin tope de unidades,
`max_new` = 1 (que es exactamente el tope que `SESSION_CAPS` ya aplicaba a la categoría `new`) y las
dos destrezas activas.

## 3. Repaso antes que nuevo, sin reordenar nada

La política se cumple **con el orden que ya existía**: `session_plan` entrega los pasos en orden
pedagógico (repaso → listening → debilidad → nuevo → refuerzo) y el recorte por unidades se aplica
**por la cola** (`max_units`). Lo que se cae al recortar es siempre lo menos prioritario, y el
**material nuevo es lo primero que desaparece**: con una sola unidad de presupuesto, el día se
queda con el repaso. `max_new` = 0 es un **día de solo repaso**.

`include_speaking = False` **no** añade una categoría nueva —el plan diario no presupuesta Speaking
como tiempo hasta V3.92—, pero sí **quita del día los pasos de Speaking** que ya podían aparecer por
debilidad o refuerzo: una preferencia declarada que no se aplicara sería una casilla que miente.

## 4. El plan sirve lo que FALTA (y el objetivo cumplido no sirve trabajo)

`_session_steps_with_day` (en `backend/domain/academy.py`) lee **una sola vez** las unidades
completadas hoy y calcula el progreso. De ahí salen tres cosas:

- el **presupuesto** del día es `remaining_minutes` (no el objetivo entero otra vez), que es lo que
  permite que la barra llegue al 100 % en vez de rellenarse mientras el alumno sigue trabajando;
- el **tope de unidades** de la lectura es `remaining_units`;
- con el objetivo **cumplido** (tiempo y, si se declaró, unidades) el plan devuelve **cero pasos**:
  la Home dice que está cumplido en vez de servir trabajo que ya no toca.

`GET /api/academy/session` y `GET /api/academy/daily-plan` comparten **el mismo** plan de pasos, así
que la barra de progreso y la lista de la sesión **no pueden divergir**.

## 5. Métricas honestas (y qué NO es cada número)

`backend/services/daily_plan.py` es un **módulo puro**: recibe filas ya leídas y devuelve números
—no toca la BD, no lee el reloj y no depende de FastAPI—, así que su comportamiento se fija con
tests sin `monkeypatch`.

- `units`: unidades del plan completadas hoy (una fila de `session_completions`).
- `minutes`: **estimación del motor** —los minutos que el plan había asignado a esas unidades cuando
  se completaron—, **no** tiempo de reloj. La app no tiene cronómetro y este módulo **no lo finge**:
  la UI lo etiqueta como `engine estimate`.
- `unknown_units`: unidades completadas sin metadata (filas anteriores a V3.90). Cuentan como
  trabajo hecho pero **no suman minutos**: mejor un 0 declarado que un dato inventado.
- `accuracy`: media **observada** de los resultados registrados hoy (evidencia de academia +
  intentos de listening, ponderada por número de intentos). **No es una nota del alumno.**
- `pending`: repasos pendientes **con su origen** (FSRS y cola de Listening de V3.89), para que la
  UI pueda decir de dónde sale cada uno en vez de sumar a ciegas.

El progreso (`goal_progress`) publica el **mínimo** de los objetivos declarados: en `mixed` el día
se cumple con las dos cosas, así que la barra no puede ir más rápido que la más atrasada.

## 6. Contrato de API

| Método y ruta | Para qué |
|---|---|
| `GET /api/academy/daily-plan` (**nuevo**) | Objetivo interpretado, lo que falta, progreso, métricas, repasos pendientes y el MISMO plan de pasos de `/session` |
| `GET /api/academy/goal` (ampliado) | Publica `plan_mode`, `target_units`, `max_new`, `include_listening`, `include_speaking` |
| `PUT /api/academy/goal` (ampliado) | Persiste el plan diario completo; las cotas las aplica el esquema (0–12 unidades, 0–5 nuevas) |

Aditivo: el `PUT` **sustituye el objetivo entero**, así que el plan diario viaja en el mismo cuerpo
(si no, se perdería al editar desde la UI). Un objetivo guardado antes de V3.90 se sigue leyendo: los
cinco campos nuevos llegan con los valores por defecto del backend.

## 7. La interfaz: modo, barra y replegado

- `frontend/src/components/TodayPlan.tsx`: selector de **modo** (por tiempo / por unidades / las
  dos), campos de unidades y de máximo de nuevas, toggles de Listening y Speaking, y la barra
  **«Today's goal»** con unidades hechas, minutos hechos (**con la etiqueta de estimación**),
  repasos pendientes desglosados por origen y el acierto de hoy (o «sin datos», nunca un 0
  disfrazado).
- `frontend/src/features/home/HomeScreen.tsx`: lee el plan **una vez** y lo reparte —la barra del
  encabezado y la lista de pasos salen del mismo objeto— y muestra el chip de progreso del objetivo.
- **Replegado declarado:** si la lectura del plan **falla** (endpoint ausente o backend caído),
  `TodayPlan` no desaparece: relee objetivo y sesión como en V3.89 y se pinta **sin** barra de
  progreso. Mientras Home sigue cargando **no** se pregunta nada por duplicado, y la barra **no se
  improvisa**: necesita las métricas que solo el plan trae.

## 8. Verificación

| Puerta | Resultado |
|---|---|
| `ruff check .` (backend) | limpio |
| `pytest` backend | **3276 passed** (incluye `test_daily_plan_v390.py`: migración, módulo puro, política del Session Engine, repositorio y API) |
| `vitest run` | **1094 passed** (111 ficheros) |
| `tsc --noEmit` | limpio |
| `npm run build` | correcto |
| `check_i18n_coverage.py --strict` | 0 huérfanas · 0 sin definir · 0 duplicadas |
| `contrast_audit.mjs --strict` | 480 pares + 6 guardas · **0 bloqueantes** |
| Playwright (rutas tocadas: **Home**) | `smoke`, `homeGraphChip`, `responsiveOverflow` y `homeDailyPlan` (nuevo) en los **3 breakpoints** · **19 passed**, 2 skipped |
| `check_release_consistency` | OK en los **6 orígenes** (`3.90.0`) |

Tests añadidos o ampliados: `backend/tests/test_daily_plan_v390.py` (nuevo, 45 tests),
`frontend/src/components/TodayPlan.test.tsx` (barra, modo, replegado y una sola lectura),
`frontend/src/features/home/HomeScreen.test.tsx`, `frontend/src/api/academy.test.ts` y
`frontend/tests/visual/homeDailyPlan.spec.ts` (nuevo).

## 9. Honestidad: lo que NO trae

- **No hay cronómetro.** Los minutos del plan son una **estimación del motor** y así se etiquetan;
  no se mide tiempo de reloj en ningún sitio.
- **Speaking no se presupuesta como tiempo todavía.** `include_speaking = False` **excluye** los
  pasos de Speaking del día (debilidad/refuerzo); convertirlo en un objetivo de tiempo es V3.92.
- **El plan no consume la cola de repaso.** Los repasos pendientes se **publican** con su origen y
  se consumen donde siempre (panel FSRS y práctica de Listening), no desde una lista de cola propia.
- **`max_new` > 1 no añade más material nuevo** mientras el motor solo conozca **un** siguiente
  objetivo del currículo: la subida es efectiva a 1 hasta que la progresión sirva más de uno por día.
  Se declara aquí en vez de prometer en la UI algo que el motor no hace.
- **Los ocho gates humanos siguen `pending`** y `docs/audit/validation-evidence.json` sigue sin
  existir.

## 10. Archivos tocados (resumen)

- **Backend:** `repositories/db.py`, `repositories/academy.py`, `services/daily_plan.py` (nuevo),
  `services/adaptive.py` (`session_plan`: `max_new`, `max_units`, `include_listening`,
  `include_speaking`), `domain/academy.py`, `schemas/academy.py`, `routers/academy.py`.
- **Frontend:** `types/api.ts`, `api/academy.ts`, `components/TodayPlan.tsx`,
  `features/home/HomeScreen.tsx`, `utils/i18n.ts`.
- **Tests:** `backend/tests/test_daily_plan_v390.py` (nuevo),
  `backend/tests/test_academy_goal.py`, `frontend/src/components/TodayPlan.test.tsx`,
  `frontend/src/features/home/HomeScreen.test.tsx`, `frontend/src/api/academy.test.ts`,
  `frontend/tests/visual/homeDailyPlan.spec.ts` (nuevo).
- **Versión y docs:** `backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
  `README.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`, `docs/audit/PARKED.md`.

## Para auditar esta release

1. Poner el objetivo en modo **por unidades** con 3 unidades y comprobar que la barra avanza al
   completar pasos y que **llega al 100 %**.
2. Poner `max_new` = 0 y comprobar que el día **no** sirve material nuevo.
3. Poner `max_units` = 1 (vía `target_units`) con repaso vencido y material nuevo pendiente:
   el plan debe quedarse con el **repaso**.
4. Cerrar el objetivo cumplido y comprobar que la Home dice que está cumplido y **no** lista trabajo.
5. Con `include_speaking` desactivado, comprobar que no aparece ningún paso de Speaking.
6. `GET /api/academy/daily-plan` dos veces seguidas sin completar nada: el plan **no** cambia (es
   determinista y sirve lo que falta).
7. Apagar el backend de la release anterior (sin `/daily-plan`): la Home debe seguir pintando
   objetivo y pasos, **sin** barra de progreso.
