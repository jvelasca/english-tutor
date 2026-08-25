# Subagente: V1.7 — Placement 2.0 (calibración IRT + perfil multiskill)

## Rol
Desarrollador backend senior (Python / FastAPI / Pydantic / SQLite). Trabajas SOLO en el backend.

## Objetivo
Convertir el placement adaptativo actual ("IRT-lite / 1PL") en un CAT más serio: añadir
calibración empírica de ítems y un perfil de resultado **multiskill** (θ por destreza), sin
perder la trazabilidad de sesión ya existente (V1.5.3).

## Contexto del proyecto
- Repo: `e:\SINCRONIZADO\Informatica\Proyectos Cursor\Ingles con IA`
- Lee ANTES: `docs/ARQUITECTURA.md` y `docs/PREMISAS.md`.
- Documenta el motor como **"IRT-lite / 1PL"**, NO como "IRT completo": la matemática IRT
  (θ, información de Fisher, error estándar) ya está implementada; lo que falta es la
  **calibración** con población real (hoy `difficulty` es un valor diseñado por nosotros).

### Estado actual (NO lo rehagas, evolucionalo)
- `backend/services/academy.py`:
  - `ability_theta(responses)` — estima θ por MAP (Newton-Raphson, prior débil).
  - `_p_correct(theta, difficulty)` — modelo logístico 1PL.
  - `_item_information(theta, difficulty)` — Fisher.
  - `select_next_item(items, answered_ids, theta)` — ítem de máxima información.
  - `placement_standard_error(theta, responses)`, `placement_adaptive_confidence(...)`.
  - `placement_should_stop(answered, total, se)` — parada por SE + mínimo + máximo.
  - `placement_result_adaptive(items, answers)` — devuelve un ÚNICO nivel + θ + skills breakdown.
- `backend/domain/academy.py`:
  - `start_placement(user_id)` — crea `placement_sessions`, devuelve primer ítem.
  - `next_placement(user_id, answers, session_id=None)` — persiste traza (answers/theta_trace/final_result).
- `backend/repositories/academy.py`: `create_placement_session`, `update_placement_session`,
  `get_placement_session`, `list_placement_sessions`.
- `backend/repositories/db.py`: tabla `placement_sessions`.
- `backend/schemas/academy.py`: `PlacementItemOut`, `PlacementAdaptiveOut`, `PlacementResultOut`,
  `PlacementStartOut`.
- `backend/routers/assessment.py`: `GET /api/academy/placement`, `POST /placement/submit`,
  `POST /placement/next`, `POST /placement/start`.
- Contenido del placement: `backend/curriculum/assessments.json` (ítems `pl-01..pl-12`, skills
  hoy solo `grammar`, `vocabulary`, `reading`, dificultad 1..6).
- `PLACEMENT_VERSION = "1.0.0"` en `backend/services/curriculum.py`.
- Tests que DEBEN seguir pasando (no los rompas): `backend/tests/test_placement.py`,
  `backend/tests/test_placement_validity.py`, `backend/tests/test_placement_session.py`,
  `backend/tests/test_reproducibility.py`, `backend/tests/test_e2e_regression.py`.

## Tarea detallada

### A. Calibración IRT (tabla de calibración + estadísticas observadas)
1. Nueva tabla `placement_item_calibration` en `backend/repositories/db.py` con columnas:
   `item_id TEXT PRIMARY KEY`, `responses INTEGER NOT NULL DEFAULT 0`,
   `correct INTEGER NOT NULL DEFAULT 0`, `correct_rate REAL`, `sample_size INTEGER`,
   `estimated_difficulty REAL`, `standard_error REAL`, `discrimination REAL`.
   (Añade migración idempotente con el patrón `PRAGMA table_info` ya usado en el repo.)
2. Repo en `backend/repositories/academy.py`: `record_placement_response(item_id, correct)`,
   `get_placement_calibration(item_id)`, `list_placement_calibration()`. Cada respuesta a un
   ítem de placement actualiza `responses`/`correct` y recalcula `correct_rate` y
   `sample_size`. Deja `estimated_difficulty`/`standard_error`/`discrimination` como columnas
   que un proceso de calibración posterior rellena (no implementes el algoritmo de calibración
   completo; solo persiste y expone los contadores observados + un método para escribir las
   estimaciones).
3. Cablea `record_placement_response` en `next_placement`/`submit_placement` para que cada
   respuesta quede registrada. Documenta que hoy es "calibración observacional" (contadores),
   y que la estimación de dificultad/discriminación es el siguiente paso.

### B. Perfil multiskill (θ por destreza)
4. Nueva función pura `placement_profile(items, answers)` en `services/academy.py` que estime θ
   **por destreza** (agrupando las respuestas de cada skill), devolviendo un dict por skill:
   `{"theta", "level", "confidence", "answered"}`. Reutiliza `ability_theta`,
   `theta_to_level` y `placement_adaptive_confidence`. Para skills sin respuestas: `theta` None
   y `level` None.
5. Nuevo schema `PlacementSkillProfileOut` (`skill`, `theta: float | None`, `level: str | None`,
   `confidence: float | None`, `answered: int`) y `PlacementProfileOut` (`profile: list[...]`,
   `overall_level`, `overall_theta`, `overall_confidence`, `placement_version`).
6. Expón el perfil multiskill: amplía `placement_result_adaptive` (o añade una variante) para
   incluir `profile` junto al `level` global, y añade el campo `profile` a `PlacementResultOut`.
   El resultado final del bucle `/placement/next` (cuando `done`) debe devolver el perfil
   multiskill además del nivel global. Añade también un endpoint `GET /api/academy/placement/profile`
   (o `POST` que reciba answers) que devuelva `PlacementProfileOut`.

### C. Ampliar el banco de placement a todas las destrezas
7. En `backend/curriculum/assessments.json` añade ítems de placement para `listening`,
   `speaking`, `writing`, `pronunciation` (hoy solo hay grammar/vocabulary/reading). Añade al
   menos 3 ítems por destreza nueva, con dificultad variada (1..6) y `correct_index` correcto.
   Especifica en cada prompt cómo se evalúa (para speaking/writing/pronunciation serán ítems de
   opción múltiple de meta-lenguaje o de reconocimiento, NO evaluación de voz; documenta esa
   limitación en el código).
8. Ajusta los tests de placement existentes solo si asumen un número/lista fija de ítems; hazlo
   de forma mínima y justificada. Añade tests nuevos: `test_placement_profile_is_multiskill`,
   `test_placement_calibration_records_responses`.

### D. Versión y documentación
9. Eleva `PLACEMENT_VERSION` de "1.0.0" a "2.0.0".
10. Actualiza docstrings de `ability_theta`, `placement_result_adaptive` y `next_placement` para
    reflejar "IRT-lite / 1PL" y el perfil multiskill.

## Criterios de aceptación
- `python -m pytest -q` (en `backend/`) — todo verde (incluidos los tests de placement ya existentes).
- `python -m ruff check .` (en `backend/`) — sin errores.
- `validate_listening_bank()` y el resto de invariantes no se ven afectados.
- El endpoint de placement devuelve `profile` multiskill y la calibración persiste respuestas.

## Restricciones
- 100% local. NO toques `frontend/`. Sin dependencias nuevas.
- NO hagas `git commit`/`tag`/`push`. NO toques `VERSION` de la app (`backend/config.py`,
  `frontend/package.json`).
- NO implementes el algoritmo completo de calibración (Joint MLE/EM); solo contadores + columnas
  para estimaciones futuras.
- Respeta la separación de capas: domain → services (puro) → repositories → SQLite.

## Salida esperada
- Lista de archivos modificados/creados y resumen de decisiones de diseño.
- Nº de tests (total y nuevos) y resultado de los gates.
- Riesgos y cualquier cosa dejada fuera de alcance.
