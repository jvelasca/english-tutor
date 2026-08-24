# Changelog

Todas las versiones notables de English Tutor. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y este proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

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
