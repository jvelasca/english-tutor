# P5 — CEFR basado en evidencia (muestras por destreza + confianza)

## Rol
Subagente full-stack que sustituye la estimación CEFR por "puntos acumulados" por un modelo de
**evidencia**: cada destreza aporta una banda y un número de **muestras**; una destreza solo cuenta
como evidencia si alcanza su mínimo de muestras, y el perfil expone la **confianza** del nivel. Todo
determinista, sin LLM y sin red.

## Contexto
`services/cefr.py::evaluate_cefr` hoy suma puntos de 5 señales (`_vocab_points`, `_pron_points`,
`_exercise_points`, `_grammar_points`, `_fluency_points`) y mapea la suma a un nivel. Es un
"contador": un alumno con mucho vocabulario sube de nivel aunque no tenga ni una muestra de
pronunciación, listening o gramática.

P4 ya dejó `repositories/listening.py::get_stats` (intentos, aciertos y precisión) y
`repositories/pronunciation.py::get_progress` (intentos y media). El hueco real de P5 es **sustituir
el punto-sum por el modelo de evidencia** y **exponer la confianza + el detalle por destreza**.

Arquitectura congelada (`routers → domain → repositories → SQLite`; `services` puros). El cambio es
aditivo en el contrato del perfil (añade campos) pero **cambia la semántica del nivel**.

## Archivos
- Backend: `services/cefr.py`, `domain/profile.py`, `schemas/profile.py`.
- Tests: `backend/tests/test_cefr_evaluation.py`, `backend/tests/test_profile.py`.
- Frontend: `frontend/src/types/api.ts`, `frontend/src/utils/cefr.ts`,
  `frontend/src/components/LearningProfile.tsx`, `frontend/src/index.css`.
- Tests frontend: `frontend/src/utils/cefr.test.ts`.

## Tarea

### 1. Modelo de evidencia (`services/cefr.py`)
- Añadir `MIN_SAMPLES: dict[str, int]` con el mínimo de muestras por destreza:
  `vocabulary=50`, `grammar=5`, `fluency=5`, `pronunciation=3`, `listening=5`.
- Añadir `TRACKED_SKILLS: tuple[str, ...] = ("vocabulary", "grammar", "fluency",
  "pronunciation", "listening")` (mismo orden que `MIN_SAMPLES`).
- Añadir `listening_band(accuracy: float | None) -> str` (misma convención que
  `pronunciation_band`, con umbrales 85/70/50 y `"—"` si es `None`).
- Añadir `_band_rank(level: str) -> int` (`CEFR_LEVELS.index`, `-1` para `"—"`).
- **Sustituir** `evaluate_cefr` por el modelo de evidencia:
  - Señales: `vocab_size`, `pronunciation_avg`, `pronunciation_attempts`,
    `grammar_error_rate`, `messages`, `user_messages`, `listening_accuracy`,
    `listening_attempts`. `exercises` se acepta por compatibilidad pero ya no participa.
  - `bands` por destreza (incluye `listening`), `samples` por destreza.
  - `evidence`: lista de `{skill, band, samples, required, confidence}` donde
    `confidence = round(min(1.0, samples/required), 2)`.
  - `level` = banda más baja entre las destrezas con `confidence >= 1.0` y `band != "—"`;
    si ninguna, `"A1"`.
  - `confidence` global = media (redondeada a 2) de las confianzas por destreza.
  - Devolver `{level, bands, evidence, confidence, descriptor}`.
- **Eliminar** las funciones privadas de puntos (`_vocab_points`, `_pron_points`,
  `_exercise_points`, `_grammar_points`, `_fluency_points`, `_level_from_points`).
- Mantener `vocabulary_band`, `grammar_band`, `fluency_band`, `pronunciation_band`,
  `level_descriptor`, `estimate_cefr` (delega) y `recommendations` sin cambios de contrato.

### 2. Dominio (`domain/profile.py`)
- Importar `repositories.listening` y llamar `listening_repo.get_stats(user_id)`.
- Pasar a `evaluate_cefr` las señales nuevas: `pronunciation_attempts`
  (`progress["pronunciation"]["attempts"]`), `user_messages`, `listening_accuracy`
  (`stats["accuracy"]`), `listening_attempts` (`stats["attempts"]`).
- Exponer en el dict devuelto: `estimated_confidence` (de `evaluation["confidence"]`) y
  `estimated_evidence` (de `evaluation["evidence"]`).

### 3. Esquemas (`schemas/profile.py`)
- `EstimatedBands`: añadir `listening: str`.
- Nueva clase `CefrEvidence(BaseModel)`: `skill`, `band`, `samples`, `required`, `confidence`.
- `LearningProfile`: añadir `estimated_confidence: float` y `estimated_evidence: list[CefrEvidence]`.

### 4. Tests backend
- `test_cefr_evaluation.py`: reescribir los casos del punto-sum por casos de evidencia:
  - sin evidencia → `A1` y `confidence == 0.0`.
  - nivel = banda más baja entre destrezas con evidencia suficiente.
  - `confidence` parcial (< 1) cuando faltan muestras.
  - `grammar_band(0.02) == "B2"`, `listening_band` con umbrales.
  - `evaluate_cefr` devuelve `evidence` con 5 destrezas y `confidence` en `[0, 1]`.
  - conservar `test_vocabulary_band_thresholds`, `test_grammar_band_unknown`,
    `test_estimate_cefr_delegates` y el test del endpoint.
- `test_profile.py`: actualizar `test_estimate_cefr_medium_*` y `test_estimate_cefr_high_*`
  al nuevo modelo; ampliar `test_profile_endpoint_shape` para afirmar `estimated_confidence`
  y `estimated_evidence`; conservar el resto.

### 5. Frontend
- `types/api.ts`: `listening: string` en `EstimatedBands`; nueva interfaz `CefrEvidence`;
  `estimated_confidence: number` y `estimated_evidence: CefrEvidence[]` en `LearningProfile`.
- `utils/cefr.ts`: `bandLabel("listening") → "Listening"`.
- `components/LearningProfile.tsx`: incluir `listening` en las bandas; mostrar la **confianza**
  del nivel (porcentaje) y el **detalle por destreza** (banda + muestras/requeridas), con estado
  vacío y tokens. Responsive.
- `index.css`: estilos con tokens para la confianza y la lista de evidencia.
- `utils/cefr.test.ts`: añadir `bandLabel("listening")`.

## Criterios de aceptación
- Backend `pytest` verde + `ruff check .` limpio; frontend `tsc --noEmit` + `vitest run` verdes.
- `/api/profile` sigue devolviendo `estimated_level`, `estimated_bands` y `estimated_descriptor`
  (compatibles), y añade `estimated_confidence` + `estimated_evidence`.
- Todo determinista, sin LLM ni red; tests rápidos.

## Restricciones
- No tocar `services/academy.py`, `services/adaptive.py` ni los endpoints de Academy/placement
  (su CEFR por destreza es independiente).
- No tocar `services/curriculum.py` ni `config.py`/`CHANGELOG` (convención de P3/P4: solo `docs/`).
- Mantener los docstrings (premisa 18).

## Salida
- Diff backend + frontend + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde.
