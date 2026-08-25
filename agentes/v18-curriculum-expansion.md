# Subagente: V1.8 — Curriculum Expansion (A1..C2 + matriz CEFR × subskill)

## Rol
Diseñador de contenido + desarrollador backend (Python / Pydantic). Trabajas sobre el contenido
curricular (JSON) y su modelo de validación, sin tocar los motores.

## Objetivo
Ampliar el currículum de `A1`/`A2` a **B1, B2, C1, C2**, con estructura canónica
`CEFR descriptor → can-do objective → subskills → activities → evidence → assessment`, e
introducir la **matriz CEFR × skill × subskill** (desglosar cada destreza en sub-destrezas),
aprovechando la infraestructura de `Evidence` que ya existe.

## Contexto del proyecto
- Repo: `e:\SINCRONIZADO\Informatica\Proyectos Cursor\Ingles con IA`
- Lee ANTES: `docs/ARQUITECTURA.md` y `docs/PREMISAS.md`.
- El contenido vive en `backend/curriculum/<level_id>.json` (hoy `a1.json` y `a2.json`); la
  fuente de verdad de la estructura es `backend/services/curriculum.py`.

### Modelo actual (NO lo rehagas, extiéndelo)
- `backend/services/curriculum.py` define los modelos Pydantic: `Activity`, `ObjectiveCheck`,
  `Objective` (con `can_do`, `title`, `skills`, `concepts`, `vocabulary`, `thresholds`,
  `minimum_attempts`, `activities`, `checks`), `Lesson`, `Unit`, `Module`, `Level`.
- `Level` tiene `level_id`, `level`, `title`, `description`, `modules`. Progresión fijada por
  `CEFR_ORDER = ("A1","A2","B1","B2","C1","C2")`.
- `CANONICAL_SKILLS` = grammar, vocabulary, pronunciation, listening, speaking, reading, writing.
- `ASSESSABLE_SKILLS` (auto-scorable, check MC) = grammar, vocabulary, reading, listening.
  `PERFORMANCE_SKILLS` (rúbrica/LLM) = speaking, writing, pronunciation.
- `load_level(level_id)` carga y valida cada JSON; `available_level_ids()` enumera los archivos.
- El Mastery Engine (`backend/services/academy.py`) agrega por `skill` y construye el perfil CEFR;
  la evidencia (`academy_evidence`) ya tiene campo `skill` (y se ampliará a `subskill` en paralelo
  a Listening 2.0 / V1.6).
- Formato de un objetivo de ejemplo (mira `backend/curriculum/a1.json` líneas 22-60).

## Tarea detallada

### A. Matriz CEFR × skill × subskill (primero, define el vocabulario)
1. Define en `backend/services/curriculum.py` una constante `SUBSKILLS: dict[str, tuple[str, ...]]`
   que mapee cada destreza canónica a sus sub-destrezas. Propuesta base (ajústala con criterio):
   - `listening`: gist, detail, inference, attitude, vocabulary, numbers, speaker_intention,
     fast_speech, connected_speech, note_taking.
   - `speaking`: production, interaction, fluency, coherence, pronunciation, lexical_range,
     grammatical_control.
   - `writing`: task_achievement, coherence, cohesion, lexical_range, grammatical_control.
   - `reading`: gist, detail, inference, vocabulary, text_organization, reading_speed.
   - `grammar`: accuracy, range, form, usage.
   - `vocabulary`: range, precision, collocation, word_formation.
   - `pronunciation`: phonemes, stress, intonation, connected_speech.
2. Añade a `Objective` un campo opcional `subskills: list[str] = []` (sub-destrezas que el
   objetivo trabaja, tomadas de `SUBSKILLS` de sus skills). Añade una validación en
   `validate_curriculum` (o donde valides el nivel) de que cada `subskill` pertenece a la tupla
   de la destreza correspondiente. NO rompas el resto de niveles; `subskills` es opcional.

### B. Ampliación del banco curricular (B1, B2, C1, C2)
3. Crea `backend/curriculum/b1.json`, `b2.json`, `c1.json`, `c2.json` con la MISMA estructura que
   `a1.json`/`a2.json`. Para cada nivel, define como mínimo:
   - 2 módulos, cada uno con 1-2 unidades, cada unidad con 1-2 lecciones, cada lección con 1-3
     objetivos.
   - Cada objetivo con: `can_do` (descriptor CEFR realista para ese nivel), `skills` (de las 7
     canónicas), `concepts`/`vocabulary` coherentes, `activities` (al menos 1) y `checks`
     (al menos 1 check MC por destreza auto-scorable declarada: grammar/vocabulary/reading/listening).
   - Asigna `thresholds` (default 0.8) y `minimum_attempts` (default 3).
4. **Población objetivo** (mínimo de objetivos por nivel; no rellenes todo con relleno, prioriza
   calidad del descriptor `can_do`):
   - B1: 6+ objetivos · B2: 6+ · C1: 5+ · C2: 5+.
5. Asegura que los IDs sean únicos y sigan la convención `<level>-m<n>-u<n>-l<n>-o<n>` y checks
   `-c<n>`, actividades `-a<n>` (mira `a1.json`).

### C. Validación y progresión
6. Actualiza `validate_curriculum` (si existe en `services/curriculum.py` o en los tests) para
   que verifique: IDs únicos, `correct_index` en rango de `options`, skills canónicas,
   subskills pertenecientes a sus skills, y `level` dentro de `CEFR_ORDER`.
7. Asegura que `available_level_ids()` ahora devuelve A1..C2 y que `next_level_id` progresa
   correctamente por `CEFR_ORDER`. Revisa que el dominio que usa `load_all_levels()` no asume
   solo A1/A2.
8. Revisa los `remediation` maps en `backend/curriculum/assessments.json`: añade entradas de
   remediación para los niveles nuevos (o deja un TODO claro si prefieres no duplicar).

### D. Tests
9. Añade `backend/tests/test_curriculum_expansion.py` con: (a) `load_level` valida B1..C2 sin
   errores; (b) toda skill declarada es canónica; (c) todo subskill pertenece a su skill;
   (d) `available_level_ids()` cubre A1..C2; (e) cada check tiene `correct_index` en rango.
10. NO rompas los tests existentes (`test_academy.py`, etc.) que puedan iterar niveles.

## Criterios de aceptación
- `python -m pytest -q` (en `backend/`) — todo verde.
- `python -m ruff check .` (en `backend/`) — sin errores.
- `load_all_levels()` devuelve 6 niveles (A1..C2) y cada uno valida.

## Restricciones
- 100% local. NO toques `frontend/`. Sin dependencias nuevas.
- NO hagas `git commit`/`tag`/`push`. NO toques `VERSION` de la app.
- NO modifiques los motores de scoring/mastery/placement/listening: solo el contenido JSON y el
  modelo/validación de `services/curriculum.py`.
- El contenido debe ser pedagógicamente coherente con el nivel CEFR declarado (no copies/pegues
  ítems entre niveles cambiando solo el id).

## Salida esperada
- Lista de archivos creados/modificados.
- Nº de objetivos/checks/actividades por nivel nuevo.
- Resultado de los gates y nº de tests (total y nuevos).
- Riesgos o decisiones de diseño (p. ej. cómo trataste speaking/writing/pronunciation en los
  checks).
