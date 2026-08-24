# Changelog

Todas las versiones notables de English Tutor. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y este proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

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
