# Changelog

Todas las versiones notables de English Tutor. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y este proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

## [1.19.0] — 2026-08-26

Refresco visual y de consistencia del frontend (sin cambios de backend ni de lógica de negocio).
Unifica los ~11 paneles del panel de análisis en tarjetas colapsables (`InsightCard`) para eliminar
la "pared de paneles" y dar jerarquía visual, pule el header (sticky con blur + menú secundario en
móvil), enriquece el estado vacío del chat y las burbujas del tutor, y consolida primitivas CSS
(`.card`, `.badge`, `.pill`, `.section-divider`) respetando el sistema de apariencia existente
(`data-theme` / `data-accent` / `data-font` / `data-density`). Se refuerza el diseño responsivo con
un breakpoint nuevo a ≤480px y accesibilidad (`aria-expanded`/`aria-controls`).

### Añadido
- **Primitivas CSS** `.card`/`.card__header`/`.card__toggle`/`.card__body`/`.badge`/`.pill`/
  `.section-divider` y tokens `--color-surface-3`/`--shadow-card`; escala tipográfica por defecto
  afinada (`--text-sm` 14px, `--text-xs` 12.5px).
- **`InsightCard`** (tarjeta colapsable accesible) y envoltura de los 11 paneles del análisis;
  `ProgressDashboard`, `TodayPlan` y `ListeningPractice` expandidos por defecto.
- **Header** sticky con `backdrop-filter: blur()` y fondo translúcido; menú desplegable de
  acciones secundarias (apariencia/ayuda) a ≤768px.
- **Chat**: avatar circular del tutor en las respuestas y estado vacío más rico (kicker + badge).
- **Responsive ≤480px**: header compacto, `composer` sin desbordamiento y drawer de análisis a
  100% de ancho.

### Cambiado
- Controles del header con altura uniforme (36px).
- Versión → `1.19.0`.

## [1.18.0] — 2026-08-26

Retoma los **P1 de listening** de la auditoría V1.14 (§27.8). Añade la medición de **delayed
retention** (precisión inmediata vs. retardada), convierte **dictado** y **shadowing** en tareas
de producción reales (no opción múltiple) con scoring determinista, y añade una **escalera de
variantes de velocidad** (slow/normal/fast) al audio servido. El LLM sigue sin puntuar; todo el
scoring es determinista y local (Whisper + Piper).

### Añadido
- **Delayed retention (P1.2)**: `delayed_retention(attempt_rows, now="")` en
  `services/listening.py` — `immediate_accuracy` (primera exposición por pregunta) vs.
  `delayed_accuracy` (re-exposición a ≥2 días) con buckets `0-2`/`2-7`/`7-30`/`30+` y
  `retention_rate`; expuesto en `listening_diagnostic` (clave `retention`) y en el frontend.
- **Dictado real (P1.4) y shadowing real (P1.3)**: sub-destrezas `dictation`/`shadowing` servidas
  como tareas de producción (escribir lo oído / grabar la repetición), con scoring determinista
  vía `services/phonetics.composite_score`. Columnas `task_type`/`score` en `listening_attempts`
  (migración idempotente), `mean_score` por sub-destreza en el diagnóstico, endpoints
  `POST /api/listening/dictation` y `POST /api/listening/shadowing`, y UI de producción en
  `ListeningPractice.tsx`.
- **Escalera de variantes de audio (P1.9)**: `slow`/`normal`/`fast` sobre el mismo contenido
  (`variant_speech_rate`/`variant_length_scale`/`audio_variants`), con cache por variante
  (`audio_digest(..., variant=...)` preserva el digest de `normal`), query param `variant` en
  `GET /api/listening/audio/{id}` y botones de variante en el frontend.

### Cambiado
- Versión → `1.18.0`.

## [1.17.0] — 2026-08-26

Cierre de tres incrementos naturales sobre V1.16 (Speaking Assessment & Evidence 2.0). Añade la
**pantalla del Speaking Assessment**, cierra el **puente conversación→speaking** (la telemetría
objetiva de interacción pasa a capturarse de extremo a extremo y a consumirse en el scorer) y
convierte el **writing** en una señal longitudinal sobre el Student Model (espejo de speaking).
El LLM sigue siendo solo extractor de evidencia; todo el scoring es determinista.

### Añadido
- **UI del flujo de Speaking Assessment** (`components/SpeakingAssessment.tsx`): start → 4 partes →
  resultado, con micrófono (grabar → transcribir → medir duración) y entrada manual (sin
  micrófono). Tipos + API (`start`/`submit part`/`finish`/`get`) sobre los endpoints ya existentes.
- **Puente conversación→speaking**: `duration_ms`/`latency_ms` en el `ChatMessage` persistido;
  captura de la telemetría del turno del alumno en el chat (`utils/telemetry.ts`) y envío de
  `conversation_id`/`message_id` en `/api/chat/stream`. El scorer de speaking fusiona
  `evidence["interaction_objective"]` (señal objetiva de turnos vía `conversation_id` opcional en
  `submit_speaking_assessment_part` y `submit_speaking_task`).
- **Writing 3.0**: `writing_diagnostic`/`writing_level`/`writing_journey` (espejo de speaking) con
  señales del Student Model (EMA, lifetime, confidence, stability, review_due) por criterio;
  endpoints `GET /api/academy/writing/diagnostic|level|journey`; frontend `WritingPanel` +
  `WritingJourney`.

### Cambiado
- Versión → `1.17.0`.

## [1.16.0] — 2026-08-26

Speaking Assessment & Evidence 2.0. Convierte el scoring de speaking de un agregador
`mean/min/max` en un modelo de competencia determinista por criterio, añade un **Speaking
Assessment** estructurado (4 partes) con sesión trazable y la **evidencia objetiva de
interacción** (telemetría de turnos). El LLM sigue siendo solo extractor de evidencia; todo el
scoring es determinista y un criterio no observado no se inventa (`score=None`).

### Añadido
- **task_achievement continuo** (4 sub-dimensiones de tarea) y **GrammarEvidence 2.0** (penalización
  por severidad en lugar de `1 - 0.25·errores`).
- **SpeakingTaskProfile**: `task_type`, dificultad `declared/realized/verified` y pesos de rúbrica por
  tipo de tarea (`weights_for_task_type`, `realized_difficulty`).
- **LexicalEvidence 2.0** (MSTTR por segmentos + sophistication/precision/collocations del LLM) y
  **FluencyEvidence 2.0** (bandas CEFR de WPM + smoothness/rhythm; `fluency ≠ speed`).
- **InteractionEvidence 2.0**: 5 sub-dimensiones semánticas del LLM fusionadas con la señal objetiva
  de interacción (`services/interaction.py`): turn_balance, latencia, completitud de turno e
  interrupciones. Telemetría de turnos (`duration_ms`/`latency_ms` en `messages`) y
  `GET /api/conversations/{id}/interaction`.
- **Diagnóstico por criterio como vista del Student Model**: `recent_score` (EMA), `lifetime_score`,
  `confidence` y `stability` por criterio (adiós al `mean/min/max`).
- **Speaking level continuo** (`speaking_level`: `numeric = 1.0 + 5.0·score`) y **Speaking Journey**
  (trayectoria CEFR): `GET /api/academy/speaking/level` y `GET /api/academy/speaking/journey`.
- **Speaking Assessment 1.0**: instrumento versionado (`curriculum/speaking_assessment.json`, 4
  partes: interview → individual task → interaction → follow-up), sesión trazable
  (`speaking_assessment_sessions`) y endpoints `start`/`part`/`finish`/`{session_id}`.
- **Frontend**: `SpeakingPanel` (NEXT FOCUS + PRACTICE NOW) y `SpeakingJourney` (barra A2→B1→B2 con
  marcador "YOU").

### Cambiado
- `speaking_diagnostic` pasa a ser una vista de las señales del Student Model (`recent_score`/EMA),
  ampliando `SpeakingCriterionOut` y `SpeakingDiagnostic.overall_recent`.
- Versión → `1.16.0`.

## [1.15.0] — 2026-08-26

Speaking 3.0. Convierte la destreza `speaking` de un *scorer por intento* en una señal de
**competencia longitudinal**, sobre el mismo Student Model unificado: mide los criterios del rubric
(fluency/grammar/lexical/pronunciation/coherence/interaction) en el tiempo, añade `interaction`
como séptimo criterio y lo expone con tendencia y criterios débiles.

### Añadido
- **Diagnóstico longitudinal de speaking** (`services/speaking.py::speaking_diagnostic`): agrupa la
  evidencia de speaking por criterio de rúbrica (`attempts`/`mean`/`min`/`max`/`review_due`), deriva
  `weak` + `recommendation` y expone `trend` global (media reciente vs previa sobre las filas
  `overall`) y `overall_mean`. Determinista, sin LLM ni red.
- **`interaction` como séptimo criterio** del rubric (`SPEAKING_CRITERIA` + `CRITERION_WEIGHTS`):
  extraída del LLM en el flujo libre (`speaking_llm.py`), no observable en read-aloud.
- **Endpoint** `GET /api/academy/speaking/diagnostic` (`SpeakingDiagnostic` + schemas
  `SpeakingCriterionOut`/`SpeakingTrend`).
- **Puente de sub-destrezas de speaking** en el Student Model (`_annotated_profile`): la entrada
  `speaking` del perfil recibe sus criterios como `subskills` (mismo patrón que listening).
- **Frontend**: tipos + `getSpeakingDiagnostic`, y panel `SpeakingDiagnostic.tsx` (desglose por
  criterio, tendencia y criterios a revisar), con estilos de tokens.

### Cambiado
- `SpeakingResultOut`/`SpeakingTaskResultOut` pasan de 6 a 7 criterios (`interaction`).
- Versión → `1.15.0`.

## [1.14.0] — 2026-08-26

Listening Evidence & Adaptive Selection. Convierte el listening de "arquitectura muy buena" a
"evidencia auditiva pedagógicamente válida": separa lo que el ítem **declara** de lo que el audio
**realiza**, evita que la metadata falsa contamine el Student Model y hace que el selector consuma
de verdad las sub-destrezas débiles del alumno. Corrige además la terminología "audio real" →
**audio TTS pre-renderizado local** (Piper).

### Añadido
- **Modelo de realización del audio** (`services/listening.py`): `AUDIO_TYPES`
  (`tts`/`recorded`/`mixed`/`synthetic_multispeaker`/`real_world`), `realized_vector`,
  `realization_status` (`declared`/`realized`/`verified`), `realized_difficulty`,
  `realization_gap_factors` y `subskill_realization_gap`. Una voz Piper única no "realiza"
  `accent`, `speaker_count` ni `noise` (quedan en 1); `connected_speech` se realiza solo si el
  texto escribe la reducción; `speed` solo si el ítem fija `speech_rate`.
- **`audio_type`** en `ListeningAsset`/`ListeningQuestion` para distinguir el tipo de audio servido.
- **Integridad de evidencia** en `listening_diagnostic`: `realization_gap` por sub-destreza y
  resumen `realization` (`verified` vs `gap`), para no contar como dominio real una sub-destreza
  entrenada con audio que no la respalda.
- **Selector adaptativo**: `pick_next_question(..., weak_subskills=...)` prioriza, dentro del nivel
  de trabajo del alumno, las sub-destrezas débiles (con realización válida); `domain.next_question`
  lo alimenta con el diagnóstico del Student Model.
- **Cache de audio versionado** (`P1.1`): path `DATA_DIR/listening/{bank}/{voice}/{id}-{digest}.wav`
  (`audio_digest` = texto + velocidad + repetición). Un cambio de script/voz/velocidad/modelo
  invalida el WAV antiguo. `scripts/generate_listening_audio.py` usa el mismo path.
- **`realized_difficulty`** persistido en `listening_attempts` (migración idempotente) y expuesto
  en `ListeningQuestion`/`ListeningAnswerResponse`.

### Cambiado
- **Terminología honesta**: "audio real" → "audio TTS pre-renderizado local" en CHANGELOG, README,
  PLAN, RELEVO y comentarios de código.
- Frontend `ListeningPractice` muestra la **etiqueta honesta del tipo de audio** (voz sintética
  local vs. grabación real), avisa cuando la dificultad realizada es menor que la declarada y
  marca las sub-destrezas con evidencia no respaldada.

## [1.13.0] — 2026-08-26

Listening 3.0. Convierte el listening de "scripts de texto + TTS genérico en vivo" a **audio TTS
pre-renderizado por ítem** (sintetizado y cacheado con Piper), cierra el currículo **A1→B2** y
garantiza evidencia independiente por sub-destreza. Todo local y determinista en el score; sin
LLM ni red.

### Añadido
- **Audio TTS pre-renderizado por ítem**: `GET /api/listening/audio/{question_id}` sirve
  `audio/wav` reproducible, pre-renderizado y cacheado en disco (`DATA_DIR/listening/`). Respeta
  `speech_rate` (mapeado a `length_scale` de Piper) y `repetition_policy="twice"`. 404 si el ítem
  no existe, 503 honesto si Piper no está disponible.
- **`audio_ready`** en `ListeningQuestion` para que el frontend reproduzca el audio TTS
  pre-renderizado o degrade al TTS en vivo con aviso.
- **Cierre A1→B2**: `curriculum/b2.json` (8 objetivos, checks de opción múltiple) y
  `LEVEL_ORDER = ["A1", "A2", "B1", "B2"]` en el banco de listening.
- **Herramienta reproducible**: `scripts/generate_listening_audio.py` pre-renderiza todo el banco
  (idempotente, `--force`).
- **Evidencia por sub-destreza**: test que garantiza que cada sub-destreza canónica
  (`fast_speech`, `connected_speech`, `multiple_speakers`, `dictation`, `shadowing`,
  `speaker_intention`) produce su fila independiente en `listening_diagnostic`.

### Cambiado
- `LISTENING_BANK_VERSION` → `3.0.0`.
- Frontend `ListeningPractice` reproduce el audio TTS pre-renderizado cuando `audio_ready` y muestra
  metadatos; `api/listening.ts` expone `getListeningAudioUrl`.

## [1.12.0] — 2026-08-26

Student Model unificado + Assessment Loop. Reconciliar los dos estimadores CEFR divergentes en
una única fuente de verdad (el Student Model de la Academy), corregir los P0 de Speaking y añadir
snapshots de evaluación históricos reproducibles.

### Añadido
- **Student Model como fuente única**: `build_student_model()` en `domain/academy.py` centraliza el
  modelo del alumno (nivel, `overall_ability`, confianza, `readiness`, `reassessment`);
  `/api/profile` pasa a ser una proyección de este modelo (mismo nivel, misma confianza).
- **Snapshots de evaluación**: tabla `cefr_assessment_snapshots` (reproducible con
  `instrument_version`/`curriculum_version`) y `cefr_history` expuesto en `/api/profile`.
- **Speaking scoring 2.0**: `task_achievement` por `task_achieved` del LLM, `lexical_resource` por
  diversidad léxica (TTR), `coherence` por marcadores discursivos y `pronunciation` con
  `observed=false` sin audio (el `overall` se recalcula solo sobre criterios observados).
- **Evidencia de discurso ampliada**: `cohesion`, `discourse_markers`, `self_corrections`,
  `hesitations`, `repetitions` en la extracción del LLM (`speaking_llm.py`).
- **Naming CEFR**: `heuristic_band` + `CEFR_MODEL_VERSION`; las bandas se documentan como
  "heuristic CEFR-aligned band" (no certificación oficial) y se exponen `overall_ability` y
  `readiness`.

### Cambiado
- `EstimatedBands` pasa de 5 a 7 destrezas (`speaking`, `reading`, `writing`).
- `LearningProfile` expone `skills` (con `samples`/`confidence`/`stability`/`trend`/`subskills`),
  `readiness` y `cefr_history`.
- Frontend `LearningProfile` muestra la barra de `overall_ability`, la `readiness` (con
  `blocking_skills`) y el desglose por destreza.

### Corregido
- Versión de release desactualizada (`config.py`, `README.md`, `package.json`) → `1.12.0`.

## [1.11.0] — 2026-08-25

CEFR basado en evidencia: sustituye el "punto-sum" por muestras por destreza + confianza. Cada
destreza exige un mínimo de muestras (`MIN_SAMPLES`) y aporta banda + confianza; el perfil expone
`estimated_confidence` y `estimated_evidence` (incluye listening).

## [1.10.0] — 2026-08-25

Listening como competencia: `topic` en el banco y métricas de precisión por dificultad/tema,
tendencia reciente y reincidencia (`listening_diagnostic`).

## [1.9.0] — 2026-08-25

Vocabulario exposure/production/mastery (P3): separa exposición (leer), producción (escribir) y
dominio (producción repetida y espaciada), con `classify` determinista.

## [1.8.1] — 2026-08-25

Marcar pasos de la sesión como hechos: `session_completions` + `POST /api/academy/session/complete`
con reseteo diario, para que los pasos completados desaparezcan del plan de hoy.

## [1.8.0] — 2026-08-25

Sesión diaria (Session Engine): plan de hoy (`/api/academy/session`) con objetivo editable y
placement adaptativo en la UI.

## [1.7.0] — 2026-08-25

Placement 2.0: convierte el placement adaptativo (IRT-lite/1PL) en un motor con
calibración observacional de ítems y perfil de resultado multiskill.

### Añadido
- **Calibración observacional de ítems**: nueva tabla `placement_item_calibration`
  (contadores poblacionales `responses`/`correct` + `correct_rate`/`sample_size` y columnas
  `estimated_difficulty`/`standard_error`/`discrimination` para estimaciones futuras).
  Cada respuesta de placement queda registrada (`record_placement_response`, vía
  `next_placement`/`submit_placement`), computando el delta contra la sesión para no
  duplicar contadores.
- **Perfil multiskill**: nueva `placement_profile(items, answers)` estima θ/nivel/confianza
  **por destreza** reutilizando `ability_theta`/`theta_to_level`/`placement_adaptive_confidence`.
  `placement_result_adaptive` ahora incluye `profile` y `PlacementResultOut` lo expone.
- **Endpoint** `POST /api/academy/placement/profile` que devuelve `PlacementProfileOut`.
- **Banco de placement ampliado** a las 7 destrezas: 12 ítems nuevos de listening, speaking,
  writing y pronunciation (meta-lenguaje/reconocimiento, sin voz ni audio real — ver nota).

### Cambiado
- `PLACEMENT_VERSION` → `2.0.0`.
- Docstrings de `ability_theta`, `placement_result_adaptive` y `next_placement` reflejan
  "IRT-lite/1PL" y el perfil multiskill.

### Nota
- Los ítems de placement de producción/listening son de opción múltiple de meta-lenguaje o
  reconocimiento (documentado en `PlacementTest`), no evaluación de voz/texto/audio real.
- La estimación IRT de dificultad/discriminación (Joint MLE/EM) queda como siguiente paso;
  hoy solo se persisten contadores observados.

## [1.6.0] — 2026-08-25

Listening 2.0: convierte el listening en un motor con audio como entidad de primer nivel,
vector de dificultad de 8 dimensiones y métrica de automaticidad.

### Añadido
- **Audio como entidad de primer nivel**: `ListeningAsset` ahora modela `audio_id`, `duration`,
  `speaker_id`, `accent`, `speech_rate`, `transcript`, `clean_transcript`, `noise_level` y
  `repetition_policy`, separando el contenido lingüístico del recurso multimedia.
- **Vector de dificultad de 8 dimensiones**: `DIFFICULTY_FACTORS` pasa a
  `speed`/`vocabulary`/`accent`/`syntactic`/`length`/`speaker_count`/`noise`/`connected_speech`.
- **Dificultad derivada por construcción**: `difficulty_from_vector` es la única fuente de verdad
  del escalar `difficulty` (media redondeada clampada a 1..6); `ListeningAsset.difficulty` es
  un campo computado, eliminando la posible incoherencia media↔dificultad.
- **Sub-destrezas ampliadas** (9 nuevas): `speaker_intention`, `fast_speech`, `connected_speech`,
  `dictation`, `shadowing`, `multiple_speakers`, `note_taking`, `prediction`, `sequencing`, con
  ítems nuevos en B1/B2 (`l15`–`l23`).
- **Métrica `automaticity`** (0..1) por sub-destreza y global, derivada de `replay_count` y
  `response_time_ms` como señal de fluidez procesal (no es un score CEFR directo).
- `LISTENING_BANK_VERSION` → `2.0.0`.

### Añadido (cierre de P1 de la auditoría de V1.5.2)
- **`critical_skills` en el perfil CEFR**: nueva `critical_skills(skill_profile)` expone las
  destrezas críticas (grammar/vocabulary) evaluadas por debajo de su mínimo; `CefrProfileOut`
  devuelve ahora `critical_skills` y `get_skill_profile` lo rellena, completando la regla de
  mínimo crítico que antes solo topaba el `overall` sin señalar qué destreza lo provocaba.

### Cambiado
- Frontend (`ListeningPractice`) muestra `automaticity` y metadatos de audio (accent/wpm/duración).

### Nota
- `LEVEL_ORDER` de listening sigue en A1/A2/B1; los ítems B2 existen y se sirven en rotación tras
  dominar A1–B1, pero aún no gatean la progresión por nivel (pendiente de la expansión A1..C2).

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
