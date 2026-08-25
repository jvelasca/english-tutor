# Changelog

Todas las versiones notables de English Tutor. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y este proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

## [1.5.3] — 2026-08-25

Release de hardening: cierra los hallazgos de la auditoría externa de V1.5.2 (validez y
trazabilidad). Sin funcionalidad nueva para el alumno.

### Corregido
- **Evidencia inválida ya no se omite en silencio**: `validate_evidence_record` se renombra a
  `evidence_record_errors` (lista de violaciones, vacía = válido) y `_record_evidence_validated`
  ahora registra en logs y lanza `EvidenceInvariantError` (HTTP 500 estructurado) en vez de
  saltarse el registro. Un intento nunca termina "sin evidencia" de forma silenciosa.
- **Docstrings obsoletos**: `services/academy.py` y `services/curriculum.py` ya no afirman que las
  destrezas de producción "aún no integran evidencia"; se distingue auto-scorable (check MC) de
  performance-scorable (rúbrica/LLM), ambas evaluables.
- **Regresión del vector de dificultad de listening**: se fija con tests el invariante de que el
  `difficulty_vector` de cada ítem debe coincidir exactamente con `DIFFICULTY_FACTORS`
  (factor faltante y factor sobrante).

### Añadido
- **Trazabilidad de la sesión de placement**: nueva tabla `placement_sessions` y endpoints
  `POST /api/academy/placement/start` + `session_id` en `/placement/next`. Persiste ítems,
  respuestas, historial de θ y resultado final para reconstruir un resultado CEFR (qué versión,
  qué ítems, qué respuestas, qué θ/SE).
- **Tests de reproducibilidad**: determinismo de placement/evidencia/listening/perfil CEFR y
  monotonicidad de θ (acierto no reduce θ, fallo no lo aumenta).

## [1.5.2] — 2026-08-25

Release de Quality & Validity: sin funcionalidad nueva, endurece la reproducibilidad y la
validez pedagógica de los motores de evaluación (evidencia, CEFR, placement y listening).

### Añadido
- **Versionado de instrumentos de evaluación**: `ASSESSMENT_VERSION`, `PLACEMENT_VERSION`,
  `RUBRIC_VERSION` y `LISTENING_BANK_VERSION` (`services/curriculum.py`). Toda evidencia persiste
  `assessment_version` y `curriculum_version`, de modo que cada resultado es reproducible aunque
  el contenido evolucione.
- **Invariantes de evidencia**: `validate_evidence_record` (`services/academy.py`) valida
  `user_id`/`objective_id`/`skill`/`item_type`/`source`/versiones/`result` antes de persistir;
  todo el dominio pasa por el helper único `_record_evidence_validated`.
- **Semántica CEFR ponderada**: `overall_cefr_score` sustituye la media aritmética por una media
  ponderada por destreza con mínimos críticos (grammar/vocabulary), y el perfil expone las
  sub-destrezas de listening dentro de `listening`.
- **Placement con validez estadística**: selección del ítem por máxima información (Fisher),
  parada por error estándar con mínimo de ítems, desglose multi-destreza del resultado y
  `placement_version` reportado.
- **Listening: first-pass accuracy**: distingue comprensión (acierto a la primera) de aprendizaje
  por repetición, por sub-destreza y global.
- **Listening: banco versionado con vector de dificultad**: `ListeningAsset` + factores
  (`speed`/`vocabulary`/`accent`/`syntactic`/`length`), sub-destreza `attitude` y `bank_version`
  expuesto en el diagnóstico.
- **Tests**: invariantes de evidencia, E2E de regresión (placement/remediación/listening),
  semántica CEFR, validez del placement y arquitectura de listening (450 tests).

### Cambiado
- La revisión de listening (`review_due`) integra la dependencia de repeticiones y el tiempo de
  respuesta, además de la precisión.

## [1.5.0] — 2026-08-25

Evidence & Performance Engine, Listening Engine y Placement adaptativo. Cierra el ciclo
`Evidence → Mastery → CEFR Skill Profile → Remediación → Olvido` para las destrezas de
producción (speaking/writing/pronunciation) y convierte el listening y el test de nivel en
motores adaptativos.

### Añadido
- **Speaking Evidence Engine (V1.3.0)**: scorer determinista CEFR de 6 dimensiones
  (`services/speaking.py`), extracción de evidencia con LLM (`services/speaking_llm.py`,
  el LLM extrae, el scorer puntúa), puente a mastery y endpoints read-aloud/tarea (JSON y
  audio → Whisper).
- **Writing Evidence Engine**: mismo patrón que speaking (rubric de 6 criterios +
  `services/writing_llm.py`), con `writing` declarado en el currículum.
- **Pronunciación fonémica (P6)**: `services/phonemes.py` (grapheme→phoneme ARPAbet +
  precisión de fonemas por Levenshtein), `phoneme_accuracy` expuesto en el evaluador, y
  puente pronunciation → mastery. Declarado `pronunciation` en el currículum.
- **CEFR Skill Profile (V1.3.1)**: `GET /api/academy/profile` devuelve, por destreza,
  `score`/`confidence`/`evidence_count`/`last_evidence`/`review_due`.
- **Remediación adaptativa (V1.3.2)**: `GET /api/academy/remediation` devuelve las destrezas
  débiles y sus objetivos; el AI Teacher lee el perfil CEFR en su system prompt.
- **Modelo de olvido (V1.4)**: `services/forgetting.py` (curva de olvido exponencial,
  `retrieval_probability` y `review_due` real en función del tiempo, sustituyendo la
  heurística por umbral).
- **Listening Engine**: sub-destrezas (`gist`/`detail`/`inference`/`vocabulary`/`numbers`) y
  dificultad en el banco, métricas (`response_time_ms`, `replay_count`), diagnóstico
  adaptativo (`GET /api/listening/diagnostic`) y panel en el frontend.
- **Placement Engine adaptativo (V1.5)**: IRT-lite (estimación de habilidad θ, selección de
  ítem por dificultad más cercana a θ) con `POST /api/academy/placement/next` (flujo stateless).
- **UI**: favicon de la app y selector de modelo IA con favorito integrado en el desplegable.

### Cambiado
- Currículum: `writing` y `pronunciation` declarados en los objetivos de A1/A2;
  `CURRICULUM_VERSION` → `1.2.5`.
- Listening pasa de banco plano a motor con sub-destrezas y diagnóstico.
- Placement pasa de scoring por bandas a estimación adaptativa de habilidad (θ).

## [1.2.2] — 2026-08-25

Hardening de la Academy antes del Evidence & Performance Engine (V1.3). Sin funcionalidad nueva:
refuerza la seguridad del gating curricular, elimina deuda de hardcodes y consolida la
documentación/versionado.

### Añadido
- **Gating de lectura del detalle de nivel**: `GET /api/academy/levels/{level_id}` devuelve
  `403` para niveles bloqueados (prerequisito no completado) y `404` solo para niveles
  inexistentes, alineado con `enroll`/`submit_exam`.
- **Invariante curricular ampliada a todos los niveles** (`load_all_levels`): cada objetivo
  valida `can_do`, destrezas canónicas, umbrales válidos y `minimum_attempts ≥ 1`, y sus checks
  cubren exactamente sus destrezas evaluables.
- **Test de migración** `academy_certificates → academy_level_completions` (copia filas y elimina
  la tabla antigua).

### Cambiado
- **UI de Academy sin hardcodes `"a1"`**: el examen usa el nivel seleccionado
  (`getExam(selectedLevel.level_id)` / `submitExam(...)`), con textos dinámicos
  ("Examen final A2", "Evaluación A2 superada") y cabecera "Currículum CEFR · A1 → C2".
- **Documentación y versionado consistentes**: `README`, `PLAN`, `docs/RELEVO`,
  `docs/ARQUITECTURA` y `package-lock.json` actualizados a `1.2.2`; arquitectura reescrita con
  la estructura real de la Academy.

## [1.2.1] — 2026-08-25

Integridad curricular de la Academy y apariencia configurable. Refuerza el modelo de mastery
determinista (evidencia repetida + decay + gating) y corrige la semántica de "certificado".

### Añadido
- **Gating CEFR estricto**: `enroll()` y `submit_exam()` exigen el nivel anterior completado
  (A1 → A2 → B1 → ...); el examen no puede saltarse la progresión.
- **Mastery por objetivo**: clave `(user, level, objective, skill)`; el dominio de una destreza
  en un objetivo no se contagia a otros objetivos que compartan destreza.
- **Mínimo de evidencias**: `minimum_attempts = 3`; un único acierto ya no marca un objetivo
  como dominado (evidencia + consistencia antes que mastery).
- **Decay del mastery**: sustituye `MAX(score, new)` por EMA (`recent_score`) + `confidence` +
  `streak`; el dominio puede bajar si el rendimiento reciente empeora.
- **Separación knowledge/performance**: `ASSESSABLE_SKILLS` (grammar/vocabulary/reading/listening)
  gatean el dominio; `PERFORMANCE_SKILLS` (speaking/writing/pronunciation) quedan a la espera de
  evidencia de rendimiento real.
- **Listening con progresión**: `current_level()`/`level_status()`/`pick_next_question()` avanzan
  A1→A2→B1 por dominio de preguntas (fix del bug de "se queda en 12 aciertos").
- **Apariencia configurable (M16)**: tema claro/oscuro, acento (7 colores), tamaño de letra y
  densidad; persistido por usuario (`settings` + `localStorage`). Botón de ayuda (`HelpDialog`).

### Cambiado
- **`certificates` → `level_completions`** (tabla + endpoint + esquemas + UI), con migración
  idempotente `academy_certificates → academy_level_completions`.
- **Semántica honesta del examen**: "Evaluación A1 superada" (y explícita que no mide producción
  oral/escrita), en lugar de un "certificado" que el sistema aún no puede emitir.

### Corregido
- Bloqueo de progresión: `objective_progress` solo exige las destrezas con evidencia determinista
  (`assessable_skills`), desbloqueando la cadena de gating.

## [1.2.0] — 2026-08-25

Academy curricular: A1/A2 funcional de extremo a extremo con mastery por objetivo y desbloqueo
secuencial. Corrige el bloqueo pedagógico detectado en la auditoría: las destrezas de producción
(speaking/writing/pronunciation) ya no impiden dominar un objetivo hasta que exista evidencia real
de rendimiento.

### Añadido
- **Academy (curriculum CEFR)**: módulos/unidades/lecciones/objetivos `can_do` para A1 y A2, motor
  de mastery determinista por `(user, level, objective, skill)`, `minimum_attempts` (evidencia
  repetida), gating curricular secuencial y selección adaptativa del siguiente objetivo
  (`adaptive_next`).
- **Evaluación determinista**: checks de opción múltiple (`ObjectiveCheck`) para todos los objetivos
  de A1/A2, cubriendo sus destrezas evaluables (grammar/vocabulary/reading/listening).
- **Placement, examen final y certificados**: test de nivel CAT-lite, examen de nivel por destreza y
  certificado de nivel con desbloqueo en cascada del siguiente nivel.
- **Invariante de currículum** en tests: todo objetivo debe tener checks que cubran exactamente sus
  destrezas evaluables (impide regresiones futuras).

### Corregido
- **Bloqueo de progresión**: `objective_progress` exigía dominio de *todas* las skills (incluido
  speaking, sin vía de evidencia), por lo que ningún objetivo podía dominarse y el gating bloqueaba
  toda la Academy. Ahora solo gatean las destrezas con evidencia determinista (`assessable_skills`),
  dejando speaking/listening/writing como metas de rendimiento pendientes de un pipeline real.
- **Semántica del examen**: el resultado pasa de "¡A1 superado!" a "Evaluación A1 superada",
  explicitando que no mide producción oral/escrita.

## [1.1.1] — 2026-08-24

Release Audit 1.1: corrección de los 6 puntos señalados por la auditoría externa antes de
congelar la arquitectura. Sin funcionalidad nueva; se endurece la coherencia del API, la
semántica pedagógica y la cobertura de aislamiento multiusuario. (Nota: la fluidez ya estaba
expuesta como `FluencyStats` desde F8; se verificó y no requirió cambios de código.)

### Cambiado
- **Identidad unificada (`current_user`)**: `chat`, `chat/stream`, `conversations` (create/list),
  `pronunciation`, `vocabulary`, `grammar` y `learning` resuelven el perfil vía
  `Depends(current_user)` en lugar de confiar en un `user_id` enviado por el cliente. Se añade
  `current_user_optional` para el chat sin perfil. Coherencia total del API en endpoints sensibles.
- **Renombrado "CEFR estimate"**: los campos `cefr_level`/`cefr_bands`/`cefr_descriptor` pasan a
  `estimated_level`/`estimated_bands`/`estimated_descriptor` (backend + frontend), dejando claro
  que es un nivel estimado heurístico y no una certificación CEFR.
- **Semántica de vocabulario**: `occurrences` → `appearances` (número de mensajes en que aparece
  la palabra, no de veces), con migración idempotente de la base de datos existente.
- **Gramática con confianza**: cada hallazgo incorpora `confidence`, `source` y `confirmed`; el
  prompt del tutor solo usa errores `confirmed`, evitando que falsos positivos contaminen el
  Learning Profile.
- **Selector de perfil**: al iniciar con varios usuarios ya no se auto-selecciona el primero; se
  muestra "Selecciona perfil" (`resolveInitialUserId`).

### Añadido
- **Tests de aislamiento cross-user**: batería explícita que verifica que un usuario nunca ve ni
  modifica los datos de otro (conversaciones, vocabulario, gramática, pronunciación, listening,
  eventos y perfil).
- **Tests del prompt/contexto**: verifica que el prompt personalizado incluye solo los errores del
  propio usuario y no filtra datos de otros perfiles.

## [1.1.0] — 2026-08-24

Primera release estable tras el plan de endurecimiento (Fases 1–10). Añade seguimiento
pedagógico real, pronunciación fonética, listening/CEFR, evaluación objetiva del tutor y un
lanzador de escritorio.

### Añadido
- **Lanzador de escritorio** (`launcher/`, GUI `tkinter` sin dependencias nuevas): arranca y
  detiene la app (backend + frontend) y muestra el estado de los servicios, la base de datos
  y los usuarios. Acceso directo del escritorio con icono (`install_shortcut.ps1`).
- **Versión unificada** `1.1.0` expuesta en `/api/health` y en `/`.
- **Progreso pedagógico real (F6)**: eventos de aprendizaje, historial con tendencias, racha,
  dominio de errores e hitos (`GET /api/progress/history`).
- **Pronunciación fonética (F7)**: evaluador compuesto (palabras + Soundex + caracteres) y
  feedback fonético en el frontend.
- **Listening / Speaking / CEFR (F8)**: banco de preguntas de comprensión auditiva, fluidez
  oral (WPM) y evaluación CEFR multi-señal con bandas por destreza.
- **Evaluación objetiva del tutor (F9)**: evaluador determinista sin LLM-juez (backend, puro),
  informe agregado + script por lotes (`scripts/eval_tutor.py`) y panel de calidad en el frontend.

### Cambiado
- El resumen de progreso (`ProgressSummary`) se sustituye por el dashboard de progreso real.
- El CEFR deja de ser una heurística plana: ahora es multi-señal con descriptor.

## [1.0.0] — 2026-08 (release inicial)

Primera versión pública: tutor de inglés 100% local con chat por texto y voz (Ollama +
faster-whisper + piper-tts), modos de tutor, multi-usuario y diseño responsive.
