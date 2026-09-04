export type Lang = "en" | "es";

export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "es", label: "Español" },
];

export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "es";
}

type Entry = { en: string; es: string };

const STRINGS: Record<string, Entry> = {
  // Navegación principal
  "nav.home": { en: "Home", es: "Inicio" },
  "nav.formation": { en: "Course", es: "Formación" },
  "nav.learn": { en: "Learn", es: "Aprender" },

  // Destrezas. Nombres de destreza/actividad en inglés también para la UI en
  // español (decisión V3.6.1): "Grammar/Pronunciation/Vocabulary/…" mantienen
  // su nombre en inglés como es habitual en apps de idiomas; el resto de la
  // interfaz sí se traduce al español.
  "skill.listening": { en: "Listening", es: "Listening" },
  "skill.speaking": { en: "Speaking", es: "Speaking" },
  "skill.reading": { en: "Reading", es: "Reading" },
  "skill.writing": { en: "Writing", es: "Writing" },
  "skill.grammar": { en: "Grammar", es: "Grammar" },
  "skill.pronunciation": { en: "Pronunciation", es: "Pronunciation" },
  "skill.vocabulary": { en: "Vocabulary", es: "Vocabulary" },

  // Aprender (hub de práctica libre, V3.1)
  "learn.title": { en: "Learn", es: "Aprender" },
  "learn.subtitle": {
    en: "Free practice that adapts to you — choose what you want to work on.",
    es: "Práctica libre que se adapta a ti — elige en qué quieres trabajar.",
  },
  "learn.pickActivity": {
    en: "What would you like to practice today?",
    es: "¿Qué quieres practicar hoy?",
  },
  "learn.recommended": { en: "Recommended for you", es: "Recomendado para ti" },
  "learn.back": { en: "Back to Learn", es: "Volver a Aprender" },
  "learn.conversation": { en: "Conversation", es: "Conversation" },
  "learn.switchActivity": {
    en: "Switch activity",
    es: "Cambiar de actividad",
  },
  "learn.desc.listening": {
    en: "Level-by-level listening exercises with instant feedback.",
    es: "Ejercicios de listening por niveles con feedback inmediato.",
  },
  "learn.desc.speaking": {
    en: "Real-life scenarios and missions with structured feedback.",
    es: "Escenarios reales y misiones con feedback estructurado.",
  },
  "learn.desc.pronunciation": {
    en: "Read aloud and get instant feedback on your accent.",
    es: "Lee en voz alta y recibe feedback inmediato sobre tu acento.",
  },
  "learn.desc.conversation": {
    en: "Chat with the tutor and keep your conversation history.",
    es: "Conversa con el tutor y conserva el historial de conversaciones.",
  },
  "learn.desc.vocabulary": {
    en: "Your personal dictionary, word by word.",
    es: "Tu diccionario personal, palabra a palabra.",
  },
  "learn.desc.grammar": {
    en: "Write sentences and get grammar corrections and feedback.",
    es: "Escribe frases y recibe correcciones y feedback de gramática.",
  },
  "learn.speakingSubtitle": {
    en: "Free speaking practice: choose a scenario or run a mission.",
    es: "Práctica oral libre: elige un escenario o lanza una misión.",
  },
  "learn.activityAria": { en: "Open activity", es: "Abrir actividad" },

  // Grupos de destrezas
  "group.primary": { en: "Primary skills", es: "Destrezas principales" },
  "group.support": { en: "Support", es: "Apoyo" },

  // Marca
  "brand.subtitle": { en: "100% local · Ollama", es: "100% local · Ollama" },

  // Home
  "home.morning": { en: "Good morning", es: "Buenos días" },
  "home.afternoon": { en: "Good afternoon", es: "Buenas tardes" },
  "home.evening": { en: "Good evening", es: "Buenas noches" },
  "home.nextStep": { en: "Today's next step", es: "El siguiente paso de hoy" },
  "home.continue": { en: "Continue", es: "Continuar" },
  "home.whyThisActivity": { en: "Why?", es: "¿Por qué?" },
  "home.because": { en: "Because:", es: "Porque:" },
  "home.limitingFactor": {
    en: "Limiting factor",
    es: "Factor limitante",
  },
  "home.missing": { en: "missing", es: "falta" },
  "home.yourProgress": { en: "Your progress", es: "Tu progreso" },
  "home.nextFocus": { en: "Next focus", es: "Siguiente foco" },
  "home.practiceNow": { en: "Practice now", es: "Practicar ahora" },
  "home.streak": { en: "day streak", es: "días de racha" },
  "home.min": { en: "min", es: "min" },
  "home.allDone": {
    en: "All done for today. Great work!",
    es: "Todo hecho por hoy. ¡Buen trabajo!",
  },
  "home.unavailable": {
    en: "Couldn't load your next step right now.",
    es: "Ahora mismo no se ha podido cargar tu siguiente paso.",
  },
  "home.retry": { en: "Try again", es: "Reintentar" },
  "home.todayGoal": {
    en: "Your goal today",
    es: "Tu objetivo de hoy",
  },
  "home.recommended": {
    en: "Recommended for you",
    es: "Recomendado para ti",
  },
  "home.seeProgress": {
    en: "See my progress",
    es: "Ver mi progreso",
  },
  "home.reviewUnavailable": {
    en: "Review isn't available right now.",
    es: "El repaso no está disponible ahora.",
  },

  // Razones de la siguiente actividad
  "reason.due_for_review": { en: "Due for review", es: "Repaso pendiente" },
  "reason.weak_subskill": { en: "Weak sub-skill", es: "Sub-destreza débil" },
  "reason.weak_skill": { en: "Weak skill", es: "Destreza débil" },
  "reason.next_in_path": { en: "Next in your path", es: "Siguiente en tu camino" },
  "reason.confidence_boost": { en: "Confidence boost", es: "Refuerzo de confianza" },

  // Progress
  "progress.title": { en: "My progress", es: "Mi progreso" },
  "progress.overall": { en: "Overall", es: "General" },

  // MI PROGRESO V3.1 — pantalla de 5 pestañas (docs/UI_V3.1.md §4.4)
  "progress.subtitle": {
    en: "How you're learning English, at a glance.",
    es: "Cómo estás aprendiendo inglés, de un vistazo.",
  },
  "progress.overviewTab": { en: "Overview", es: "Resumen" },
  "progress.courseTab": { en: "Course", es: "Curso" },
  "progress.skillsTab": { en: "Skills", es: "Habilidades" },
  "progress.journeyTab": { en: "Journey", es: "Trayectoria" },
  "progress.tracksTab": { en: "Tracks", es: "Recorridos" },
  "progress.tabAria": {
    en: "Progress sections",
    es: "Secciones de mi progreso",
  },
  "progress.continueFormation": {
    en: "Continue in Course",
    es: "Continuar en Formación",
  },
  "progress.currentCourseLevel": {
    en: "Current course level",
    es: "Nivel actual del curso",
  },
  "progress.unitsCompleted": {
    en: "Units completed",
    es: "Unidades completadas",
  },
  "progress.nextUp": { en: "Next up", es: "Lo que sigue" },
  "progress.levelComplete": {
    en: "This level is complete.",
    es: "Este nivel está completo.",
  },
  "progress.limitingSkill": {
    en: "Limiting skill",
    es: "Destreza limitante",
  },
  "progress.skillsHint": {
    en: "All your skills, from your latest model. Expand a skill for its detail.",
    es: "Todas tus destrezas, según tu modelo más reciente. Expande una para ver su detalle.",
  },
  "progress.tracksIntro": {
    en: "Your evolution across each practice route.",
    es: "Tu evolución en cada recorrido de práctica.",
  },
  "progress.assessmentTab": { en: "Assessment", es: "Evaluación" },
  "progress.activityTitle": {
    en: "Recent activity",
    es: "Actividad reciente",
  },
  "mastery.strong": { en: "Strong", es: "Fuerte" },
  "mastery.developing": { en: "Developing", es: "En desarrollo" },
  "mastery.needsPractice": { en: "Needs practice", es: "Necesita práctica" },
  "mastery.reviewIn": {
    en: "Review in {days} days",
    es: "Repasar en {days} días",
  },
  "mastery.reviewNow": { en: "Review now", es: "Repasar ahora" },
  "readiness.ready": { en: "Ready", es: "Preparado" },
  "readiness.approaching": { en: "Approaching", es: "Cerca" },
  "readiness.developing": { en: "Developing", es: "En desarrollo" },

  // Tríada Progress / Mastery / Readiness (V2.2)
  "triad.progress": { en: "Progress", es: "Progreso" },
  "triad.mastery": { en: "Mastery", es: "Dominio" },
  "triad.readiness": { en: "Readiness", es: "Preparación" },
  "triad.progressHint": { en: "course coverage", es: "cobertura del curso" },
  "triad.masteryHint": {
    en: "of practiced skills",
    es: "de destrezas practicadas",
  },

  // Course
  "course.title": { en: "Your English journey", es: "Tu viaje en inglés" },
  "course.subtitle": { en: "CEFR curriculum", es: "Currículum CEFR" },
  "course.mastered": { en: "mastered", es: "dominados" },
  "course.continue": { en: "Continue", es: "Continuar" },
  "course.you": { en: "You", es: "Tú" },
  "course.milestones": { en: "milestones", es: "hitos" },
  "course.completed": { en: "Completed", es: "Completado" },
  "course.inProgress": { en: "In progress", es: "En curso" },
  "course.locked": { en: "Locked", es: "Bloqueado" },
  "course.cefrLevel": { en: "CEFR level", es: "Nivel CEFR" },
  "course.unit": { en: "Unit", es: "Unidad" },
  "course.currentLesson": { en: "Current lesson", es: "Lección actual" },
  "course.byTheEnd": {
    en: "By the end of this unit you will be able to…",
    es: "Al terminar esta unidad serás capaz de…",
  },
  "course.sections": { en: "Unit sections", es: "Secciones de la unidad" },
  "course.needsContent": { en: "needs content", es: "sin contenido" },
  "course.unitMastered": { en: "Unit mastered", es: "Unidad dominada" },
  "course.masteryGate": { en: "Mastery gate", es: "Puerta de dominio" },
  "course.gates": { en: "gates met", es: "requisitos cumplidos" },
  "course.myLevel": { en: "My level", es: "Mi nivel" },
  "course.continueCourse": { en: "Continue course", es: "Continuar curso" },
  "course.levelComplete": { en: "Level completed", es: "Nivel completado" },
  "course.lockedHint": {
    en: "Complete the previous level to unlock it.",
    es: "Completa el nivel anterior para desbloquearlo.",
  },
  "course.units": { en: "Units", es: "Unidades" },
  "course.evaluations": { en: "Evaluations", es: "Evaluaciones" },
  "section.interaction": { en: "Interaction", es: "Interacción" },
  "section.review": { en: "Review", es: "Repaso" },
  "section.assessment": { en: "Assessment", es: "Evaluación" },

  // Learning Journey (V2.2)
  "journey.title": { en: "Learning Journey", es: "Trayecto de aprendizaje" },
  "journey.subtitle": {
    en: "Your path through the CEFR levels",
    es: "Tu recorrido por los niveles CEFR",
  },
  "journey.you": { en: "You", es: "Tú" },
  "journey.unitsMastered": { en: "Units mastered", es: "Unidades dominadas" },
  "journey.skillsReady": { en: "Skills ready", es: "Destrezas listas" },
  "journey.retention": { en: "Retention", es: "Retención" },
  "journey.nextMilestone": { en: "Next milestone", es: "Próximo hito" },
  "journey.empty": {
    en: "Complete a few activities to start your journey.",
    es: "Completa algunas actividades para iniciar tu trayecto.",
  },

  // Diccionario personal (V2.3)
  "dictionary.title": { en: "Personal dictionary", es: "Diccionario personal" },
  "dictionary.subtitle": {
    en: "Your words and structures, item by item.",
    es: "Tus palabras y estructuras, ítem a ítem.",
  },
  "dictionary.total": { en: "items", es: "ítems" },
  "dictionary.known": { en: "Known", es: "Reconocidas" },
  "dictionary.learning": { en: "Learning", es: "Aprendiendo" },
  "dictionary.weak": { en: "Weak", es: "Débiles" },
  "dictionary.mastered": { en: "Mastered", es: "Dominadas" },
  "dictionary.byCefr": { en: "Vocabulary by CEFR", es: "Vocabulario por CEFR" },
  "dictionary.items": { en: "Lexical items", es: "Ítems léxicos" },
  "dictionary.recall": { en: "Recall", es: "Recuerdo" },
  "dictionary.nextReviewIn": {
    en: "Review in {days}d",
    es: "Repasar en {days}d",
  },
  "dictionary.status.mastered": { en: "Mastered", es: "Dominada" },
  "dictionary.status.known": { en: "Known", es: "Reconocida" },
  "dictionary.status.learning": { en: "Learning", es: "Aprendiendo" },
  "dictionary.status.weak": { en: "Weak", es: "Débil" },
  "dictionary.kind.word": { en: "word", es: "palabra" },
  "dictionary.kind.collocation": { en: "collocation", es: "colocación" },
  "dictionary.kind.phrasal_verb": { en: "phrasal verb", es: "verbo frasal" },
  "dictionary.kind.expression": { en: "expression", es: "expresión" },
  "dictionary.kind.sentence_frame": {
    en: "sentence frame",
    es: "plantilla de frase",
  },
  "dictionary.kind.functional_chunk": {
    en: "functional chunk",
    es: "bloque funcional",
  },
  "dictionary.kind.structure": { en: "structure", es: "estructura" },
  "dictionary.kind.other": { en: "lexical unit", es: "unidad léxica" },
  "dictionary.recognizedNotProduced": {
    en: "Recognized but not produced",
    es: "Reconocidas pero no producidas",
  },
  "dictionary.recognizedNotProducedHint": {
    en: "Words you understand when reading but haven't produced yet — great speaking-drill candidates.",
    es: "Palabras que entiendes al leer pero aún no produces — candidatas a practicar hablando.",
  },
  "dictionary.empty": {
    en: "No words yet. Complete course objectives to grow your dictionary.",
    es: "Aún no hay palabras. Completa objetivos del curso para hacer crecer tu diccionario.",
  },

  // Settings
  "settings.title": { en: "Settings", es: "Ajustes" },
  "settings.appearance": { en: "Appearance", es: "Apariencia" },
  "settings.audio": { en: "Audio", es: "Audio" },
  "settings.ai": { en: "AI model", es: "Modelo IA" },
  "settings.system": { en: "System", es: "Sistema" },
  "settings.voices": { en: "Voices", es: "Voces" },
  "voices.defaultBadge": { en: "Default", es: "Por defecto" },
  "voices.selectProfile": {
    en: "Select a profile to save its preferred voice.",
    es: "Selecciona un perfil para guardar su voz preferida.",
  },
  "voices.saveError": {
    en: "Could not save the voice. Try again.",
    es: "No se pudo guardar la voz. Inténtalo de nuevo.",
  },
  "voices.empty.title": {
    en: "No additional Piper voices installed",
    es: "No hay voces Piper adicionales instaladas",
  },
  "voices.empty.hint": {
    en: "The app currently uses its default Piper voice.\n\nTo add voices, place a Piper voice pair (<voice>.onnx and <voice>.onnx.json) in the backend/models/piper folder and reopen Settings. Voice files are ~60 MB each.\n\nExamples: en_GB-alan-medium (British, male), en_GB-cori-medium (Scottish), en_US-amy-medium (American, female).",
    es: "La aplicación usa ahora su voz Piper por defecto.\n\nPara añadir voces, coloca el par de una voz Piper (<voz>.onnx y <voz>.onnx.json) en la carpeta backend/models/piper y vuelve a abrir Ajustes. Cada voz pesa ~60 MB.\n\nEjemplos: en_GB-alan-medium (británico, masculina), en_GB-cori-medium (escocesa), en_US-amy-medium (estadounidense, femenina).",
  },
  "voices.download.title": {
    en: "Add a voice",
    es: "Añadir una voz",
  },
  "voices.download.hint": {
    en: "Download a Piper voice from the official catalog. It is stored in backend/models/piper (one time only) and appears in the list above once downloaded.",
    es: "Descarga una voz Piper del catálogo oficial. Se guarda en backend/models/piper (una sola vez) y aparece en la lista superior al terminar.",
  },
  "voices.download.button": {
    en: "Download",
    es: "Descargar",
  },
  "voices.download.loading": {
    en: "Downloading…",
    es: "Descargando…",
  },
  "voices.download.size": {
    en: "~{mb} MB",
    es: "~{mb} MB",
  },
  "voices.download.allInstalled": {
    en: "All curated voices are installed. To add another, drop its .onnx and .onnx.json into backend/models/piper.",
    es: "Todas las voces del catálogo están instaladas. Para añadir otra, coloca su .onnx y .onnx.json en backend/models/piper.",
  },
  "voices.note": {
    en: "Current voice for this profile: {voice}. Changing the voice also affects listening practice: items without a human recording are regenerated with the new voice on first playback and then cached.",
    es: "Voz actual de este perfil: {voice}. Cambiar la voz afecta también a la práctica de listening: los ítems sin grabación humana se regeneran con la nueva voz en la primera reproducción y quedan en caché.",
  },
  "settings.interfaceLanguage": {
    en: "Interface language",
    es: "Idioma de la interfaz",
  },
  "settings.model": { en: "AI model", es: "Modelo IA" },

  // Estado del sistema
  "status.ready": { en: "Ready", es: "Listo" },
  "status.systemStatus": { en: "System status", es: "Estado del sistema" },
  "status.api": { en: "API", es: "API" },
  "status.database": { en: "Database", es: "Base de datos" },
  "status.ollama": { en: "Ollama", es: "Ollama" },
  "status.stt": { en: "STT", es: "STT" },
  "status.tts": { en: "TTS", es: "TTS" },
  "status.audioLibrary": { en: "Audio library", es: "Biblioteca de audio" },
  "status.secureContext": { en: "Secure context", es: "Conexión segura" },
  "status.microphone": { en: "Microphone", es: "Micrófono" },
  "status.scanToConnect": { en: "Scan to connect", es: "Escanea para conectar" },
  "status.urlTitle": { en: "Access URL on your network", es: "URL de acceso en tu red" },

  // Copias de seguridad (V1.41)
  "backup.title": { en: "Backup & restore", es: "Copias de seguridad" },
  "backup.subtitle": {
    en: "Your progress, evidence and audio library are stored locally. Download a backup to keep it safe, or restore a previous backup.",
    es: "Tu progreso, evidencia y biblioteca de audio se guardan localmente. Descarga una copia para guardarla a salvo o restaura una copia anterior.",
  },
  "backup.create": { en: "Create backup", es: "Crear copia" },
  "backup.download": { en: "Download latest", es: "Descargar última" },
  "backup.list": { en: "Stored backups", es: "Copias guardadas" },
  "backup.empty": { en: "No backups yet", es: "Aún no hay copias" },
  "backup.restoreTitle": { en: "Restore from file", es: "Restaurar desde archivo" },
  "backup.chooseFile": { en: "Choose backup (.zip)", es: "Elegir copia (.zip)" },
  "backup.created": { en: "Backup created", es: "Copia creada" },
  "backup.restored": { en: "Backup restored", es: "Copia restaurada" },
  "backup.adminRequired": {
    en: "Enter the admin PIN to manage backups.",
    es: "Introduce el PIN de administrador para gestionar las copias.",
  },
  "backup.keep": { en: "Keeps the last 7 backups automatically", es: "Conserva las últimas 7 copias automáticamente" },
  "backup.error": { en: "Could not complete the operation", es: "No se pudo completar la operación" },

  // Biblioteca de audio (gestión en-app)
  "audio.subtitle": {
    en: "Replace the real recordings used in the listening exercises. Upload an uncompressed WAV and that exercise will use it instead of the synthetic voice.",
    es: "Reemplaza las grabaciones reales de los ejercicios de listening. Sube un WAV sin comprimir y ese ejercicio lo usará en lugar de la voz sintética.",
  },
  "audio.upload": { en: "Upload WAV", es: "Subir WAV" },
  "audio.chooseFile": { en: "Choose file", es: "Elegir archivo" },
  "audio.remove": { en: "Remove recording", es: "Quitar grabación" },
  "audio.preview": { en: "Preview", es: "Escuchar" },
  "audio.state.recorded": { en: "Real recording", es: "Grabación real" },
  "audio.state.missing": { en: "File missing", es: "Archivo no encontrado" },
  "audio.state.empty": { en: "Synthetic voice (TTS)", es: "Voz sintética (TTS)" },
  "audio.field.transcript": { en: "Transcript", es: "Transcripción" },
  "audio.field.speaker": { en: "Speaker ID", es: "ID de hablante" },
  "audio.field.accent": { en: "Accent", es: "Acento" },
  "audio.field.cefr": { en: "CEFR", es: "CEFR" },
  "audio.field.speechRate": { en: "Speech rate (WPM)", es: "Velocidad (WPM)" },
  "audio.field.noise": { en: "Noise level (0–5)", es: "Nivel de ruido (0–5)" },
  "audio.field.gender": { en: "Gender", es: "Género" },
  "audio.field.region": { en: "Region", es: "Región" },
  "audio.field.context": { en: "Context", es: "Contexto" },
  "audio.hint.wav": {
    en: "The file must be an uncompressed WAV (PCM).",
    es: "El archivo debe ser un WAV sin comprimir (PCM).",
  },
  "audio.error.load": {
    en: "Could not load the audio library.",
    es: "No se pudo cargar la biblioteca de audio.",
  },
  "audio.error.upload": {
    en: "Could not upload the audio. Make sure it is an uncompressed WAV.",
    es: "No se pudo subir el audio. Comprueba que es un WAV sin comprimir.",
  },
  "audio.error.remove": {
    en: "Could not remove the recording.",
    es: "No se pudo quitar la grabación.",
  },
  "audio.none": {
    en: "No replaceable audio slots yet.",
    es: "Aún no hay audios reemplazables.",
  },
  "audio.tab.library": { en: "Library", es: "Biblioteca" },
  "audio.tab.audit": { en: "Content audit", es: "Auditoría de contenido" },
  "audio.admin.required": {
    en: "Administration is protected by a local PIN.",
    es: "La administración está protegida por un PIN local.",
  },
  "audio.admin.pin": { en: "Admin PIN", es: "PIN de admin" },
  "audio.admin.unlock": { en: "Unlock", es: "Desbloquear" },
  "audio.admin.lock": { en: "Lock", es: "Bloquear" },
  "audio.admin.unlocked": { en: "Admin unlocked", es: "Admin desbloqueado" },
  "audio.admin.error": {
    en: "Invalid admin PIN.",
    es: "PIN de administración incorrecto.",
  },
  "audio.qa.title": { en: "AUDIO QUALITY", es: "CALIDAD DEL AUDIO" },
  "audio.qa.duration": { en: "Duration", es: "Duración" },
  "audio.qa.sampleRate": { en: "Sample rate", es: "Frecuencia" },
  "audio.qa.channels": { en: "Channels", es: "Canales" },
  "audio.qa.peak": { en: "Peak", es: "Pico" },
  "audio.qa.clipping": { en: "Clipping", es: "Clipping" },
  "audio.qa.silence": { en: "Silence", es: "Silencio" },
  "audio.qa.dc": { en: "DC offset", es: "Offset DC" },
  "audio.audit.title": { en: "CONTENT INTEGRITY CHECK", es: "CHEQUEO DE INTEGRIDAD DEL CONTENIDO" },
  "audio.audit.fail": { en: "Issues found.", es: "Se encontraron problemas." },
  "audio.audit.items": { en: "Items", es: "Ítems" },
  "audio.audit.recorded": { en: "Recorded", es: "Grabados" },
  "audio.audit.tts": { en: "Synthetic (TTS)", es: "Sintéticos (TTS)" },
  "audio.audit.bySeverity": { en: "Issues by severity", es: "Problemas por severidad" },
  "audio.audit.validatedItems": {
    en: "Total validated learning items",
    es: "Ítems de aprendizaje validados",
  },
  "audio.audit.listeningCorpus": {
    en: "Listening corpus",
    es: "Corpus de listening",
  },
  "audio.audit.speakingScenarios": {
    en: "Speaking scenarios",
    es: "Escenarios de speaking",
  },
  "audio.audit.empty": { en: "No issues.", es: "Sin problemas." },
  "audio.audit.error": {
    en: "Could not load the audit. Check the admin PIN.",
    es: "No se pudo cargar la auditoría. Comprueba el PIN de admin.",
  },

  // Común
  "common.loading": { en: "Loading…", es: "Cargando…" },
  "common.close": { en: "Close", es: "Cerrar" },
  "common.done": { en: "Done", es: "Hecho" },
  "common.cancel": { en: "Cancel", es: "Cancelar" },
  "common.save": { en: "Save", es: "Guardar" },
  "common.saving": { en: "Saving…", es: "Guardando…" },
  "common.delete": { en: "Delete", es: "Eliminar" },
  "common.edit": { en: "Edit", es: "Editar" },

  // Cabecera / navegación
  "nav.aria": { en: "Main navigation", es: "Navegación principal" },
  "nav.skills": { en: "Skills", es: "Destrezas" },
  "header.goHome": { en: "Go to Home", es: "Ir a Inicio" },
  "header.openSettings": { en: "Open settings", es: "Abrir ajustes" },

  // Ajustes (apariencia)
  "settings.theme": { en: "Theme", es: "Tema" },
  "settings.theme.light": { en: "Light", es: "Claro" },
  "settings.theme.dark": { en: "Dark", es: "Oscuro" },
  "settings.accentColor": { en: "Accent color", es: "Color de acento" },
  "settings.fontSize": { en: "Font size", es: "Tamaño de letra" },
  "settings.density": { en: "Density", es: "Densidad" },
  "settings.reset": { en: "Reset", es: "Restablecer" },
  "appearance.accent.indigo": { en: "Indigo", es: "Índigo" },
  "appearance.accent.violet": { en: "Violet", es: "Violeta" },
  "appearance.accent.blue": { en: "Blue", es: "Azul" },
  "appearance.accent.teal": { en: "Teal", es: "Turquesa" },
  "appearance.accent.emerald": { en: "Emerald", es: "Esmeralda" },
  "appearance.accent.rose": { en: "Rose", es: "Rosa" },
  "appearance.accent.amber": { en: "Amber", es: "Ámbar" },
  "appearance.font.small": { en: "Small", es: "Pequeño" },
  "appearance.font.medium": { en: "Medium", es: "Normal" },
  "appearance.font.large": { en: "Large", es: "Grande" },
  "appearance.density.compact": { en: "Compact", es: "Compacto" },
  "appearance.density.comfortable": { en: "Comfortable", es: "Cómodo" },

  // Ayuda
  "help.title": { en: "Help", es: "Ayuda" },
  "help.subtitle": {
    en: "A short guide to the three areas. For the full technical documentation, visit the project docs.",
    es: "Una guía breve de los tres mundos. Para la documentación técnica completa, consulta los docs del proyecto.",
  },
  "help.viewDocs": { en: "View documentation", es: "Ver en la documentación" },
  "help.documentation": { en: "Documentation", es: "Documentación" },
  "help.what.title": { en: "What is English Tutor?", es: "¿Qué es English Tutor?" },
  "help.what.body": {
    en: "An English tutor that runs 100% on your computer — no internet, accounts or cloud. The app is organised into three areas: Inicio (daily plan and recommendations), Formación (guided CEFR course from A1 to C2) and Aprender (free practice).",
    es: "Un profesor de inglés que funciona 100% en tu ordenador, sin Internet, cuentas ni nube. La app se organiza en tres mundos: INICIO (plan del día y recomendaciones), FORMACIÓN (curso CEFR guiado de A1 a C2) y APRENDER (práctica libre).",
  },
  "help.start.title": { en: "Getting started", es: "Cómo empezar" },
  "help.start.body": {
    en: "Choose a profile in the header and speak or type in any conversation. Use Formación to follow the course level by level, Aprender to practise a skill freely, and Inicio to pick up your daily goal and review.",
    es: "Elige un perfil en la cabecera y habla o escribe en cualquier conversación. Usa FORMACIÓN para seguir el curso nivel a nivel, APRENDER para practicar una destreza libremente e INICIO para retomar tu objetivo del día y el repaso.",
  },
  "help.modes.title": { en: "The three areas", es: "Los tres mundos" },
  "help.modes.body": {
    en: "Inicio is your day-to-day command centre: today's goal, pending review and what to do next. Formación is the structured CEFR course with units and assessments. Aprender groups all free practice: listening, speaking, pronunciation, conversation, vocabulary, grammar and adaptive review.",
    es: "INICIO es tu centro de mando diario: objetivo de hoy, repaso pendiente y siguiente paso recomendado. FORMACIÓN es el curso CEFR estructurado, con unidades y evaluaciones. APRENDER agrupa toda la práctica libre: listening, speaking, pronunciación, conversación, vocabulario, gramática y repaso adaptativo.",
  },
  "help.course.title": { en: "CEFR course", es: "Curso CEFR" },
  "help.course.body": {
    en: "A guided path through the six CEFR levels (A1, A2, B1, B2, C1, C2). Each level is divided into units with objectives; you unlock units and take assessments as you progress, at your own pace.",
    es: "Un camino guiado por los seis niveles CEFR (A1, A2, B1, B2, C1, C2). Cada nivel se divide en unidades con objetivos; desbloqueas unidades y superas evaluaciones a tu ritmo según avanzas.",
  },
  "help.listening.title": { en: "Listening comprehension", es: "Comprensión auditiva" },
  "help.listening.body": {
    en: "Listen to real sentences, answer the question and check your accuracy level by level. Practise it on its own in Aprender → Listening or inside your course units.",
    es: "Escucha frases reales, responde la pregunta y comprueba tu precisión nivel a nivel. Practícalo por libre en APRENDER → Listening o dentro de las unidades del curso.",
  },
  "help.troubleshooting.title": { en: "Common issues", es: "Problemas frecuentes" },
  "help.troubleshooting.body": {
    en: "If the tutor does not answer, check that Ollama is running. If the microphone or a connected device fails, see the full guide in the project documentation.",
    es: "Si el profesor no responde, comprueba que Ollama esté arrancado. Si el micrófono o un dispositivo conectado falla, consulta la guía completa en la documentación del proyecto.",
  },
  "help.connectTitle": { en: "Use it on your phone or tablet", es: "Usarla en tu móvil o tableta" },
  "help.connectBody": {
    en: "To open the app from another device, go to Settings (gear icon at the top) → System → “Scan to connect”. There you will find the QR code and the steps for your platform.",
    es: "Para abrir la app desde otro dispositivo ve a Ajustes (icono de engranaje, arriba) → Sistema → «Escanea para conectar». Allí encontrarás el código QR y los pasos de tu plataforma.",
  },

  // Conectar un dispositivo (LAN / móvil)
  "connect.cardTitle": { en: "Connect a device", es: "Conectar un dispositivo" },
  "connect.cardSubtitle": {
    en: "Scan with your phone",
    es: "Escanea con tu teléfono",
  },
  "connect.noNetwork": {
    en: "Start the app and connect to your local network to see the QR code.",
    es: "Inicia la app y conéctate a tu red local para ver el código QR.",
  },
  "connect.localOnly": {
    en: "Local network only. No internet required.",
    es: "Solo red local. No requiere Internet.",
  },
  "connect.trustTitle": {
    en: "First connection: trust the local certificate",
    es: "Primera conexión: confiar el certificado local",
  },
  "connect.trustBody": {
    en: "English Tutor uses a self-signed certificate so the microphone works over HTTPS on your local network. The first time you connect, your device will warn you that the certificate is not trusted. Follow the steps for your platform to continue safely.",
    es: "English Tutor usa un certificado autofirmado para que el micrófono funcione por HTTPS en tu red local. La primera vez que conectes, tu dispositivo avisará de que el certificado no es de confianza. Sigue los pasos de tu plataforma para continuar con seguridad.",
  },
  "connect.windows.title": { en: "Windows", es: "Windows" },
  "connect.windows.body": {
    en: "Open the LAN URL in your browser. On the \"Your connection is not private\" page, click Advanced, then Continue to the site. Your own PC is already the source of the app, so this is safe.",
    es: "Abre la URL LAN en tu navegador. En la página «Tu conexión no es privada», pulsa Avanzado y luego Continuar al sitio. Tu propio PC es el origen de la app, así que es seguro.",
  },
  "connect.android.title": { en: "Android", es: "Android" },
  "connect.android.body": {
    en: "Scan the QR code with your phone camera, or type the LAN URL in Chrome. On the \"Your connection is not private\" warning, tap Advanced, then Proceed. If the microphone still doesn't work, allow microphone access in the browser settings.",
    es: "Escanea el código QR con la cámara del teléfono, o escribe la URL LAN en Chrome. En el aviso «Tu conexión no es privada», pulsa Avanzado y luego Continuar. Si el micrófono sigue sin funcionar, permite el acceso al micrófono en los ajustes del navegador.",
  },
  "connect.ios.title": { en: "iPhone / iPad", es: "iPhone / iPad" },
  "connect.ios.body": {
    en: "Open the LAN URL in Safari. On the \"This Connection Is Not Private\" page, tap Show Details, then visit this website. If the microphone doesn't work, go to Settings → Safari → Advanced → Experimental Features and make sure microphone access is enabled for this site.",
    es: "Abre la URL LAN en Safari. En la página «Esta conexión no es privada», pulsa Mostrar detalles y luego Visitar este sitio web. Si el micrófono no funciona, ve a Ajustes → Safari → Avanzado → Funciones experimentales y asegúrate de que el acceso al micrófono esté habilitado para este sitio.",
  },

  // Menú de usuario
  "user.profile": { en: "Profile", es: "Perfil" },
  "user.profiles": { en: "Profiles", es: "Perfiles" },
  "user.profileTitle": { en: "User profile", es: "Perfil de usuario" },
  "user.newProfile": { en: "New profile", es: "Nuevo perfil" },
  "user.editProfile": { en: "Edit profile", es: "Editar perfil" },
  "user.name": { en: "Name", es: "Nombre" },
  "user.add": { en: "Add", es: "Añadir" },
  // Puerta de perfil al arrancar en un navegador sin usuario definido.
  "user.chooseTitle": { en: "Choose your profile", es: "Elige tu perfil" },
  "user.choosePrompt": {
    en: "Select a user or create a new one to start.",
    es: "Selecciona un usuario o crea uno nuevo para empezar.",
  },
  "user.noProfilesYet": {
    en: "There are no profiles yet. Create the first one below.",
    es: "Todavía no hay perfiles. Crea el primero abajo.",
  },
  "user.createProfile": { en: "Create profile", es: "Crear perfil" },
  "user.createError": {
    en: "Could not create the profile. Is the server running?",
    es: "No se pudo crear el perfil. ¿Está activo el servidor?",
  },

  // Diálogo de perfil
  "profile.editTitle": { en: "Edit profile", es: "Editar perfil" },
  "profile.uploadImage": { en: "Upload image", es: "Subir imagen" },
  "profile.removeImage": { en: "Remove image", es: "Quitar imagen" },
  "profile.name": { en: "Name", es: "Nombre" },
  "profile.icon": { en: "Icon", es: "Icono" },
  "profile.chooseIcon": { en: "Choose icon", es: "Elegir icono" },
  "profile.color": { en: "Color", es: "Color" },
  "profile.chooseColor": { en: "Choose color", es: "Elegir color" },
  "profile.noIcon": { en: "No icon", es: "Sin icono" },
  "profile.auto": { en: "Auto", es: "Automático" },
  "profile.imageError": {
    en: "Could not process the image.",
    es: "No se pudo procesar la imagen.",
  },
  "profile.saveError": {
    en: "Could not save the profile.",
    es: "No se pudo guardar el perfil.",
  },

  // Micrófono
  "mic.stop": { en: "Stop recording", es: "Detener grabación" },
  "mic.record": { en: "Record message", es: "Grabar mensaje" },
  "mic.transcribeError": { en: "Error transcribing: ", es: "Error al transcribir: " },
  "mic.accessError": {
    en: "Could not access the microphone: ",
    es: "No se pudo acceder al micrófono: ",
  },
  "mic.unavailableTitle": {
    en: "Microphone unavailable",
    es: "Micrófono no disponible",
  },
  "mic.unavailable.not_secure_context": {
    en: "This device is connected over an insecure connection (HTTP). The microphone only works over HTTPS or on localhost.",
    es: "Este dispositivo está conectado por una conexión insegura (HTTP). El micrófono solo funciona por HTTPS o en localhost.",
  },
  "mic.unavailable.no_media_devices": {
    en: "This browser does not expose media devices on this connection.",
    es: "Este navegador no expone los dispositivos multimedia en esta conexión.",
  },
  "mic.unavailable.no_get_user_media": {
    en: "This browser does not support microphone access.",
    es: "Este navegador no admite el acceso al micrófono.",
  },
  "mic.unavailable.no_media_recorder": {
    en: "This browser does not support audio recording.",
    es: "Este navegador no admite la grabación de audio.",
  },
  "mic.unavailable.permission_denied": {
    en: "Microphone permission was denied. Allow access in your browser settings and try again.",
    es: "El permiso del micrófono fue denegado. Permite el acceso en los ajustes del navegador e inténtalo de nuevo.",
  },
  "mic.unavailable.no_microphone": {
    en: "No microphone was found on this device.",
    es: "No se encontró ningún micrófono en este dispositivo.",
  },
  "mic.unavailable.not_supported": {
    en: "The microphone could not be started on this device.",
    es: "No se pudo iniciar el micrófono en este dispositivo.",
  },
  "mic.unavailable.unknown": {
    en: "The microphone could not be accessed.",
    es: "No se pudo acceder al micrófono.",
  },
  "mic.unavailable.checkTitle": {
    en: "Check these things:",
    es: "Comprueba lo siguiente:",
  },
  "mic.unavailable.checkSecure": {
    en: "Use HTTPS or a secure local connection (https://…).",
    es: "Usa HTTPS o una conexión local segura (https://…).",
  },
  "mic.unavailable.checkPermission": {
    en: "Allow microphone access in the browser.",
    es: "Permite el acceso al micrófono en el navegador.",
  },
  "mic.unavailable.checkBrowser": {
    en: "Try Chrome, Edge or Safari.",
    es: "Prueba con Chrome, Edge o Safari.",
  },

  // Test de micrófono
  "micTest.button": { en: "Test microphone", es: "Probar micrófono" },
  "micTest.buttonAgain": {
    en: "Check microphone again",
    es: "Volver a comprobar el micrófono",
  },
  "micTest.stop": { en: "Stop test", es: "Detener prueba" },
  "micTest.speakNow": { en: "Speak now…", es: "Habla ahora…" },
  "micTest.inputLevel": { en: "Input level", es: "Nivel de entrada" },
  "micTest.working": { en: "Microphone working", es: "El micrófono funciona" },
  "micTest.testPlayback": { en: "Test playback", es: "Probar reproducción" },
  "micTest.playbackSample": {
    en: "English Tutor audio test.",
    es: "Prueba de audio de English Tutor.",
  },
  "micTest.playbackOk": { en: "Playback works", es: "La reproducción funciona" },
  "micTest.playbackError": {
    en: "Playback failed. Check your speakers or volume.",
    es: "La reproducción falló. Comprueba los altavoces o el volumen.",
  },

  // Voz / reproducción
  "speak.listen": { en: "Listen to reply", es: "Escuchar respuesta" },
  "speak.phrase": { en: "Listen to the phrase", es: "Escuchar la frase" },
  "speak.answer": { en: "Listen to the answer", es: "Escuchar la respuesta" },
  "speak.error": { en: "Error playing: ", es: "Error al reproducir: " },

  // Chat / barra lateral
  "chat.new": { en: "New chat", es: "Nuevo chat" },
  "composer.placeholder": { en: "Type your message…", es: "Escribe tu mensaje…" },
  "composer.aria": { en: "Message", es: "Mensaje" },
  "composer.send": { en: "Send", es: "Enviar" },
  "chat.empty": { en: "No conversations yet.", es: "Aún no hay conversaciones." },
  "chat.emptyHint": { en: "Create one to start.", es: "Crea una para empezar." },
  "chat.activeLesson": { en: "Active lesson", es: "Lección activa" },
  "chat.finishLesson": { en: "Finish lesson", es: "Terminar lección" },
  "chat.exit": { en: "Exit", es: "Salir" },
  "chat.close": { en: "Close", es: "Cerrar" },
  "chat.closeConversations": { en: "Close conversations", es: "Cerrar conversaciones" },
  "chat.openConversations": { en: "Open conversations", es: "Abrir conversaciones" },
  "chat.resizeConversations": {
    en: "Resize conversations panel",
    es: "Redimensionar panel de conversaciones",
  },
  "chat.resizeInsights": {
    en: "Resize analysis panel",
    es: "Redimensionar panel de análisis",
  },
  "chat.hello": { en: "Hello", es: "Hola" },
  "chat.intro": {
    en: "I'm your local English tutor. Write to me in English or Spanish to start practicing.",
    es: "Soy tu profesor de inglés local. Escríbeme en inglés o en español para empezar a practicar.",
  },

  // Paneles de análisis
  "panels.analysis": { en: "Analysis", es: "Análisis" },
  "panels.closeAnalysis": { en: "Close analysis panel", es: "Cerrar panel de análisis" },
  "panels.openAnalysis": { en: "Open analysis panel", es: "Abrir panel de análisis" },
  "panels.yourProfile": { en: "Your profile", es: "Tu perfil" },
  "panels.speaking": { en: "Speaking", es: "Expresión oral" },
  "panels.writing": { en: "Writing", es: "Escritura" },
  "panels.speakingJourney": { en: "Speaking journey", es: "Recorrido oral" },
  "panels.writingJourney": { en: "Writing journey", es: "Recorrido escrito" },
  "panels.speakingAssessment": { en: "Speaking assessment", es: "Evaluación oral" },
  "panels.tutorQuality": { en: "Tutor quality", es: "Calidad del tutor" },

  // Kickers de sección
  "kicker.speaking": { en: "Conversation practice", es: "Práctica de conversación" },
  "kicker.writing": { en: "Writing practice", es: "Práctica de escritura" },
  "kicker.grammar": { en: "Grammar practice", es: "Práctica de gramática" },
  "kicker.default": { en: "Practice", es: "Práctica" },

  // Plan de hoy
  "today.goal": { en: "Goal", es: "Objetivo" },
  "today.targetCefr": { en: "CEFR target", es: "Meta CEFR" },
  "today.minPerDay": { en: "Min/day", es: "Min/día" },
  "today.daysPerWeek": { en: "Days/week", es: "Días/semana" },
  "today.saved": { en: "Saved", es: "Guardado" },
  "today.nextMilestone": { en: "next milestone", es: "próximo hito" },
  "today.readyFor": { en: "Readiness for", es: "Preparación para" },
  "today.blocking": { en: "Blocking skill:", es: "Destreza bloqueante:" },
  "today.review": { en: "review", es: "repasa" },
  "today.practice": { en: "practice", es: "practica" },
  "today.readyToReassess": {
    en: "Ready to reassess",
    es: "Listo para reevaluar",
  },
  "today.startSession": { en: "Start today's session", es: "Empezar la sesión de hoy" },
  "today.noModel": {
    en: "No learning model yet. Practice and your daily plan will appear here.",
    es: "Aún no hay modelo de aprendizaje. Practica y aquí verás tu plan de hoy.",
  },
  "today.subskill": { en: "Sub-skill:", es: "Sub-destreza:" },
  "today.goalType.general": { en: "General conversation", es: "Conversación general" },
  "today.goalType.travel": { en: "Travel", es: "Viajar" },
  "today.goalType.work": { en: "Work", es: "Trabajo" },
  "today.goalType.interview": { en: "Interview", es: "Entrevista" },
  "today.goalType.exam": { en: "Exam", es: "Examen" },

  // Estados vacíos
  "empty.noSpeaking": {
    en: "No speaking practice recorded yet.",
    es: "Aún no hay práctica de expresión oral registrada.",
  },
  "empty.noWriting": {
    en: "No writing practice recorded yet.",
    es: "Aún no hay práctica de expresión escrita registrada.",
  },
  "empty.noSpeakingJourney": {
    en: "No speaking journey recorded yet.",
    es: "Aún no hay recorrido de expresión oral registrado.",
  },
  "empty.noWritingJourney": {
    en: "No writing journey recorded yet.",
    es: "Aún no hay recorrido de expresión escrita registrado.",
  },
  "empty.noProfile": {
    en: "No learning profile yet. Write in English and here you'll see your level, vocabulary and recommendations.",
    es: "Aún no hay perfil de aprendizaje. Escribe en inglés y aquí verás tu nivel, vocabulario y recomendaciones.",
  },
  "empty.noProgress": {
    en: "No progress yet. Start chatting or practicing pronunciation and here you'll see your progress, streak and milestones.",
    es: "Aún no hay progreso. Empieza a conversar o a practicar pronunciación y aquí verás tu evolución, racha e hitos.",
  },

  // Diagnósticos / tendencias
  "diag.trend": { en: "Recent trend", es: "Tendencia reciente" },
  "diag.review": { en: "review", es: "revisar" },
  "diag.improving": { en: "improving", es: "mejorando" },
  "diag.gettingWorse": { en: "getting worse", es: "empeorando" },
  "diag.stable": { en: "stable", es: "estable" },
  "diag.proxy": { en: "proxy", es: "proxy" },
  "diag.proxyAutomated": { en: "automated proxy", es: "proxy automático" },
  "diag.proxyFull": {
    en: "Score derives from text alignment, not acoustic analysis of your voice.",
    es: "La puntuación deriva de la alineación de texto, no del análisis acústico de tu voz.",
  },
  "diag.confHigh": { en: "high", es: "alta" },
  "diag.confMedium": { en: "medium", es: "media" },
  "diag.confLow": { en: "low", es: "baja" },

  // Speaking 2.0 (Interaction Quality + Conversation Endurance)
  "speaking.interactionQuality": {
    en: "Interaction quality",
    es: "Calidad de interacción",
  },
  "speaking.iq.initiation": { en: "Initiation", es: "Inicio" },
  "speaking.iq.response": { en: "Response", es: "Respuesta" },
  "speaking.iq.follow_up": { en: "Follow-up", es: "Continuación" },
  "speaking.iq.repair": { en: "Repair", es: "Reparación" },
  "speaking.iq.turn_taking": { en: "Turn-taking", es: "Toma de turnos" },
  "speaking.endurance": {
    en: "Conversation endurance",
    es: "Resistencia conversacional",
  },
  "speaking.enduranceGoal": {
    en: "Next goal",
    es: "Siguiente objetivo",
  },
  "speaking.enduranceTurns": {
    en: "spoken turns",
    es: "turnos hablados",
  },

  // Role-play
  "roleplay.hint": { en: "Role-play", es: "Role-play" },
  "roleplay.turnPlaceholder": {
    en: "Type your turn in English…",
    es: "Escribe tu turno en inglés…",
  },
  "roleplay.turnAria": { en: "Your turn in the role-play", es: "Tu turno en el role-play" },
  "roleplay.send": { en: "Send", es: "Enviar" },
  "roleplay.finish": { en: "Finish interaction", es: "Terminar interacción" },

  // Escenarios comunicativos (Speaking 3.0)
  "scenarios.title": { en: "Speaking scenarios", es: "Escenarios de conversación" },
  "scenarios.subtitle": {
    en: "Pick a real-life situation and practice the conversation to reach a clear goal.",
    es: "Elige una situación real y practica la conversación para lograr un objetivo claro.",
  },
  "scenarios.objective": { en: "Your goal", es: "Tu objetivo" },
  "scenarios.metrics": { en: "What is measured", es: "Qué se mide" },
  "scenarios.practice": { en: "Practice", es: "Practicar" },
  "scenarios.back": { en: "All scenarios", es: "Todos los escenarios" },
  "scenarios.completed": { en: "Interaction completed", es: "Interacción completada" },
  "scenarios.completedNote": {
    en: "Your turns (duration and response time) were captured and will inform your speaking diagnostic.",
    es: "Tus turnos (duración y tiempo de respuesta) quedaron registrados y alimentarán tu diagnóstico oral.",
  },
  "scenarios.metric.task_completion": { en: "Task completion", es: "Cumplir la tarea" },

  // Speaking Mission Performance (V2.9)
  "mission.title": { en: "Speaking mission", es: "Misión de speaking" },
  "mission.subtitle": {
    en: "Attempt → evaluation → targeted drill → retry → see your improvement.",
    es: "Intento → evaluación → drill dirigido → reintento → mira tu mejora.",
  },
  "mission.empty": {
    en: "No scenarios available yet.",
    es: "Aún no hay escenarios disponibles.",
  },
  "mission.reset": { en: "New mission", es: "Nueva misión" },
  "mission.evaluation": { en: "Evaluation", es: "Evaluación" },
  "mission.overall": { en: "Overall", es: "Global" },
  "mission.weak": { en: "Focus", es: "Foco" },
  "mission.drills": { en: "Targeted drills", es: "Drills dirigidos" },
  "mission.improvement": { en: "Improvement", es: "Mejora" },
  "mission.improved": {
    en: "You improved on the retry. Keep that version.",
    es: "Has mejorado en el reintento. Quédate con esa versión.",
  },
  "mission.notImproved": {
    en: "No gain yet — try another mission or drill again.",
    es: "Todavía sin ganancia — prueba otra misión o repite el drill.",
  },
  "mission.attempt": { en: "Submit attempt", es: "Enviar intento" },
  "mission.retry": { en: "Submit retry", es: "Enviar reintento" },
  "mission.attemptPlaceholder": {
    en: "Type (or paste) what you would say…",
    es: "Escribe (o pega) lo que dirías…",
  },
  "mission.retryPlaceholder": {
    en: "Try again after the drills…",
    es: "Inténtalo de nuevo tras los drills…",
  },
  "mission.errorStart": {
    en: "Could not start the mission.",
    es: "No se pudo iniciar la misión.",
  },
  "mission.errorAttempt": {
    en: "Could not score the attempt.",
    es: "No se pudo puntuar el intento.",
  },
  "mission.errorRetry": {
    en: "Could not score the retry.",
    es: "No se pudo puntuar el reintento.",
  },
  "panels.speakingMission": { en: "Mission loop", es: "Loop de misión" },
  "panels.assessmentLadder": {
    en: "Assessment ladder",
    es: "Escalera de evaluación",
  },

  "assessmentV2.title": {
    en: "Assessment 2.0",
    es: "Assessment 2.0",
  },
  "assessmentV2.subtitle": {
    en: "Formative → unit → progress → level → retention",
    es: "Formative → unidad → progreso → nivel → retención",
  },
  "assessmentV2.kind.formative": { en: "Formative", es: "Formative" },
  "assessmentV2.kind.unit": { en: "Unit", es: "Unidad" },
  "assessmentV2.kind.progress": { en: "Progress", es: "Progreso" },
  "assessmentV2.kind.level": { en: "Level", es: "Nivel" },
  "assessmentV2.kind.retention": { en: "Retention", es: "Retención" },
  "assessmentV2.next": { en: "Next recommended", es: "Siguiente recomendado" },
  "assessmentV2.nextNone": {
    en: "Ladder complete for now",
    es: "Escalera completa por ahora",
  },
  "assessmentV2.mastery": { en: "Mastery gate", es: "Gate de dominio" },
  "assessmentV2.masteryOk": {
    en: "Eligible (full evidence ladder)",
    es: "Elegible (escalera de evidencia completa)",
  },
  "assessmentV2.masteryMissing": {
    en: "Still missing",
    es: "Aún falta",
  },
  "assessmentV2.retentionDue": {
    en: "Retention reassessment is due",
    es: "Toca reevaluación de retención",
  },
  "assessmentV2.threshold": { en: "Pass at", es: "Aprobado desde" },
  "assessmentV2.submit": { en: "Submit answers", es: "Enviar respuestas" },
  "assessmentV2.passed": { en: "Passed", es: "Aprobado" },
  "assessmentV2.failed": { en: "Not yet", es: "Aún no" },
  "assessmentV2.failedSkills": {
    en: "Weak skills",
    es: "Destrezas débiles",
  },
  "assessmentV2.retentionTitle": {
    en: "Retention delta",
    es: "Delta de retención",
  },
  "assessmentV2.retentionStable": { en: "stable", es: "estable" },
  "assessmentV2.back": { en: "Back to ladder", es: "Volver a la escalera" },
  "assessmentV2.errorStart": {
    en: "Could not start this assessment.",
    es: "No se pudo iniciar este assessment.",
  },
  "assessmentV2.errorSubmit": {
    en: "Could not score the assessment.",
    es: "No se pudo puntuar el assessment.",
  },

  "panels.evidenceGraph": {
    en: "Evidence graph",
    es: "Grafo de evidencia",
  },

  "evidenceGraph.title": {
    en: "Evidence graph",
    es: "Grafo de evidencia",
  },
  "evidenceGraph.subtitle": {
    en: "Can-do → dimensions → limiting factor → mastery",
    es: "Can-do → dimensiones → factor limitante → dominio",
  },
  "evidenceGraph.level": { en: "Level", es: "Nivel" },
  "evidenceGraph.avgMastery": {
    en: "avg mastery",
    es: "dominio medio",
  },
  "evidenceGraph.open": { en: "Open", es: "Abiertos" },
  "evidenceGraph.mastered": { en: "Mastered", es: "Dominados" },
  "evidenceGraph.topLimiting": {
    en: "Top limiting factor",
    es: "Factor limitante principal",
  },
  "evidenceGraph.canDo": { en: "Can-do", es: "Can-do" },
  "evidenceGraph.mastery": { en: "Mastery", es: "Dominio" },
  "evidenceGraph.missing": { en: "missing", es: "falta" },
  "evidenceGraph.limiting": { en: "limiting", es: "limitante" },
  "evidenceGraph.focus": { en: "Recommended focus", es: "Foco recomendado" },
  "evidenceGraph.empty": {
    en: "No evidence graph yet.",
    es: "Aún no hay grafo de evidencia.",
  },
  "fsrs.title": { en: "FSRS review", es: "Repaso FSRS" },
  "fsrs.subtitle": {
    en: "What · Why · When · How strong · Last · Next",
    es: "Qué · Por qué · Cuándo · Fuerza · Última · Siguiente",
  },
  "fsrs.dueCount": { en: "Due now", es: "Pendientes" },
  "fsrs.empty": {
    en: "Nothing due right now.",
    es: "Nada pendiente ahora.",
  },
  "fsrs.what": { en: "What", es: "Qué" },
  "fsrs.why": { en: "Why", es: "Por qué" },
  "fsrs.when": { en: "When", es: "Cuándo" },
  "fsrs.howStrong": { en: "How strong", es: "Fuerza" },
  "fsrs.lastEvidence": { en: "Last evidence", es: "Última evidencia" },
  "fsrs.dueNow": { en: "due now", es: "ahora" },
  "fsrs.never": { en: "never", es: "nunca" },
  "fsrs.grade.again": { en: "Again", es: "Otra vez" },
  "fsrs.grade.hard": { en: "Hard", es: "Difícil" },
  "fsrs.grade.good": { en: "Good", es: "Bien" },
  "fsrs.grade.easy": { en: "Easy", es: "Fácil" },
  "fsrs.errorReview": {
    en: "Could not record the review.",
    es: "No se pudo registrar el repaso.",
  },
  "fsrs.whyReason.forgetting-curve": {
    en: "forgetting curve",
    es: "curva de olvido",
  },
  "fsrs.whyReason.weak-skill": { en: "weak skill", es: "destreza débil" },
  "fsrs.whyReason.missing-delayed-evidence": {
    en: "missing delayed evidence",
    es: "falta evidencia retardada",
  },
  "fsrs.whyReason.maintenance": { en: "maintenance", es: "mantenimiento" },
  "fsrs.whyReason.weak-lexicon": { en: "weak word", es: "palabra débil" },
  "fsrs.whyReason.learning-lexicon": {
    en: "learning word",
    es: "palabra en aprendizaje",
  },
  "fsrs.whyReason.recognition-only": {
    en: "recognized but not produced",
    es: "reconocida sin producir",
  },
  "fsrs.whyReason.lexicon-maintenance": {
    en: "lexicon maintenance",
    es: "mantenimiento léxico",
  },
  "fsrs.whyReason.manual-review": {
    en: "manual review",
    es: "repaso manual",
  },
  "fsrs.whyReason.new": { en: "new card", es: "carta nueva" },
  "fsrs.whyReason.evidence": { en: "from evidence", es: "desde evidencia" },
  "fsrs.whyReason.scheduled": { en: "scheduled", es: "programado" },
  "fsrs.whyReason.review": { en: "review", es: "repaso" },

  "scenarios.metric.interaction": { en: "Interaction", es: "Interacción" },
  "scenarios.metric.fluency": { en: "Fluency", es: "Fluidez" },
  "scenarios.metric.repair": { en: "Repair", es: "Reparación" },
  "scenarios.metric.turn_taking": { en: "Turn-taking", es: "Toma de turnos" },
  "scenarios.empty": {
    en: "No scenarios available yet.",
    es: "Aún no hay escenarios disponibles.",
  },

  // Lectura
  "reading.status.mastered": { en: "Mastered", es: "Dominado" },
  "reading.status.review": { en: "Review", es: "A repasar" },
  "reading.status.available": { en: "Available", es: "Disponible" },
  "reading.status.locked": { en: "Locked", es: "Bloqueado" },
  "reading.title": { en: "Reading practice", es: "Práctica de lectura" },
  "reading.subtitle": {
    en: "CEFR curriculum guided reading",
    es: "Lectura guiada por el currículum CEFR",
  },
  "reading.viewCourse": { en: "View course", es: "Ver curso" },
  "reading.empty": {
    en: "No reading objectives available for your level yet. Explore the course to enroll in a level.",
    es: "Aún no hay objetivos de lectura disponibles para tu nivel. Explora el curso para matricularte en un nivel.",
  },
  "reading.start": { en: "Start", es: "Empezar" },
  "reading.review": { en: "Review", es: "Repasar" },

  // Pronunciación
  "pron.title": { en: "Pronunciation practice", es: "Práctica de pronunciación" },
  "pron.prompt": {
    en: "Read the sentence aloud and tap the microphone:",
    es: "Lee la frase en voz alta y pulsa el micrófono:",
  },
  "pron.evaluating": { en: "Evaluating…", es: "Evaluando…" },
  "pron.stop": { en: "Stop", es: "Detener" },
  "pron.record": { en: "Record", es: "Grabar" },
  "pron.expected": { en: "Expected", es: "Esperado" },
  "pron.heard": { en: "Heard", es: "Oído" },
  "pron.level": { en: "Level", es: "Nivel" },
  "pron.wordAccuracy": { en: "Word accuracy", es: "Precisión por palabra" },
  "pron.phoneticScore": { en: "Phonetic similarity", es: "Similitud fonética" },
  "pron.phonemeAccuracy": {
    en: "Phoneme accuracy (text proxy)",
    es: "Precisión de fonemas (proxy de texto)",
  },
  "pron.prosody": {
    en: "Syllabic rhythm (proxy, no audio)",
    es: "Ritmo silábico (proxy, sin audio)",
  },
  "pron.fluency": { en: "Fluency", es: "Fluidez" },
  "pron.level.good": { en: "Great", es: "Muy bien" },
  "pron.level.fair": { en: "Fair", es: "Aceptable" },
  "pron.level.needsPractice": { en: "Keep practicing", es: "Sigue practicando" },
  "pron.evalError": {
    en: "Error evaluating pronunciation: ",
    es: "Error al evaluar la pronunciación: ",
  },
  "pron.micError": {
    en: "Could not access the microphone: ",
    es: "No se pudo acceder al micrófono: ",
  },

  // Speaking assessment
  "assessment.startDesc": {
    en: "Complete the 4 parts of the speaking assessment to get your continuous CEFR level, with a microphone or by typing your answers.",
    es: "Completa las 4 partes del assessment oral para obtener tu nivel CEFR continuo, con micrófono o escribiendo tus respuestas.",
  },
  "assessment.start": { en: "Start Speaking Assessment", es: "Iniciar Speaking Assessment" },
  "assessment.starting": { en: "Starting…", es: "Iniciando…" },
  "assessment.another": { en: "Take another assessment", es: "Hacer otro assessment" },
  "assessment.part": { en: "Part", es: "Parte" },
  "assessment.of": { en: "of", es: "de" },
  "assessment.confidence": { en: "Confidence", es: "Confianza" },
  "assessment.attempts": { en: "attempts", es: "intentos" },
  "assessment.record": { en: "Record answer", es: "Grabar respuesta" },
  "assessment.stop": { en: "Stop", es: "Detener" },
  "assessment.transcribing": { en: "Transcribing…", es: "Transcribiendo…" },
  "assessment.orType": { en: "Or type your answer:", es: "O escribe tu respuesta:" },
  "assessment.placeholder": {
    en: "Type here what you would say aloud…",
    es: "Escribe aquí lo que dirías en voz alta…",
  },
  "assessment.submit": { en: "Send", es: "Enviar" },
  "assessment.sending": { en: "Sending…", es: "Enviando…" },
  "assessment.ofThisPart": { en: "for this part", es: "de esta parte" },
  "assessment.viewResult": { en: "View result", es: "Ver resultado" },
  "assessment.nextPart": { en: "Next part", es: "Siguiente parte" },
  "assessment.processing": { en: "Processing…", es: "Procesando…" },
  "assessment.startError": {
    en: "Could not start the assessment: ",
    es: "No se pudo iniciar el assessment: ",
  },
  "assessment.submitError": {
    en: "Error sending the answer: ",
    es: "Error al enviar la respuesta: ",
  },
  "assessment.finishError": {
    en: "Could not finish the assessment: ",
    es: "No se pudo finalizar el assessment: ",
  },
  "assessment.noNextPart": {
    en: "No next part available.",
    es: "No hay siguiente parte disponible.",
  },
  "assessment.transcribeError": {
    en: "Could not transcribe the audio: ",
    es: "No se pudo transcribir el audio: ",
  },
  "assessment.micError": {
    en: "Could not access the microphone: ",
    es: "No se pudo acceder al micrófono: ",
  },

  // Listening
  "listening.loading": { en: "Loading exercise…", es: "Cargando ejercicio…" },
  "listening.playing": { en: "Playing…", es: "Reproduciendo…" },
  "listening.play": { en: "Listen to audio", es: "Escuchar audio" },
  "listening.audioSettings": {
    en: "Audio settings",
    es: "Ajustes de audio",
  },
  "listening.speed": { en: "Speed:", es: "Velocidad:" },
  "listening.audioUnavailable": {
    en: "Reference audio not available; using live generated voice.",
    es: "Audio de referencia no disponible; usando voz generada en vivo.",
  },
  "listening.ttsRealVoice": {
    en: "Actual local synthetic voice of your profile (Settings → Voices). Synthetic items have no real accent.",
    es: "Voz local sintética real de tu perfil (Ajustes → Voces). Los ítems sintéticos no tienen un acento real.",
  },
  "listening.dictationPlaceholder": {
    en: "Write what you hear…",
    es: "Escribe lo que escuchas…",
  },
  "listening.evaluating": { en: "Evaluating…", es: "Evaluando…" },
  "listening.submitDictation": { en: "Send dictation", es: "Enviar dictado" },
  "listening.record": { en: "Record", es: "Grabar" },
  "listening.stop": { en: "Stop", es: "Detener" },
  "listening.transcribed": { en: "Transcribed", es: "Transcrito" },
  "listening.correct": { en: "Correct!", es: "¡Correcto!" },
  "listening.incorrect": { en: "Incorrect.", es: "Incorrecto." },
  "listening.wordAccuracy": { en: "Word accuracy", es: "Precisión por palabra" },
  "listening.phoneticScore": { en: "Phonetic similarity", es: "Similitud fonética" },
  "listening.reference": { en: "Reference", es: "Referencia" },
  "listening.heard": { en: "Heard", es: "Oído" },
  "listening.accuracy": { en: "Accuracy", es: "Precisión" },
  "listening.currentLevel": { en: "Current route", es: "Ruta actual" },
  "listening.routeLabel": { en: "Route {level}", es: "Ruta {level}" },
  "listening.routeCompleted": {
    en: "{level} route completed",
    es: "Ruta {level} completada",
  },
  // Lectura honesta del progreso: completar la ruta de un nivel es un hito de
  // práctica, no un certificado CEFR. Un nivel CEFR real exige cientos de
  // palabras y decenas de horas guiadas.
  "listening.routeNote": {
    en: "A real CEFR {level} means hundreds of known words and dozens of guided hours. This route trains step by step: finishing it is a practice milestone, not a CEFR certificate.",
    es: "Un nivel CEFR {level} real implica cientos de palabras y decenas de horas guiadas. Esta ruta entrena paso a paso: completarla es un hito de práctica, no un certificado CEFR.",
  },
  // La cobertura completa del banco no certifica la ruta: aún falta la puerta
  // (precisión y aciertos a la primera).
  "listening.routePendingCert": {
    en: "Covered, not certified yet",
    es: "Cubierta, aún sin certificar",
  },
  // Detalle de la puerta de ruta (listening.levelPanelGateIntro + línea numérica).
  "listening.routeGateIntro": {
    en: "Mastering the phrases isn't enough to pass this route. To certify {level} you need:",
    es: "Dominar las frases no basta para superar la ruta. Para certificar {level} necesitas:",
  },
  "listening.routeGateLine": {
    en: "{coverage}% of the bank mastered (≥{coverageRequired}%) · accuracy ≥{accuracyRequired}% ({accuracy}) · {topics}/{topicsRequired} topics · {checkpoint}/{checkpointRequired} first-try answers",
    es: "{coverage}% del banco dominado (≥{coverageRequired}%) · precisión ≥{accuracyRequired}% ({accuracy}) · {topics}/{topicsRequired} temas · {checkpoint}/{checkpointRequired} aciertos a la primera",
  },
  // P2 (H7): lectura honesta por ruta. La puerta otorga `functional` (hito de
  // práctica); la retención retardada estable (≥7 días, ratio ≥90%) decide
  // `demonstrated`. Hasta entonces la ruta se lee "aún no demostrado".
  "listening.routeState.not_started": {
    en: "Not started yet",
    es: "Sin empezar aún",
  },
  "listening.routeState.developing": {
    en: "Training — route not passed yet",
    es: "Entrenando — ruta aún sin superar",
  },
  "listening.routeState.functional": {
    en: "Route passed — practice milestone, not demonstrated",
    es: "Ruta superada — hito de práctica, sin demostrar",
  },
  "listening.routeState.demonstrated": {
    en: "Demonstrated",
    es: "Demostrado",
  },
  "listening.demoTitle": {
    en: "{level} Listening — demonstrated",
    es: "{level} Listening — demostrado",
  },
  "listening.demoNotYet": {
    en: "{level} Listening — not yet demonstrated",
    es: "{level} Listening — aún no demostrado",
  },
  "listening.demoRequires": {
    en: "Demonstrating {level} Listening also requires stable delayed retention: ≥{ratio}% of your immediate accuracy on re-exposures after ≥{days} days. Keep reviewing — until then this route is a practice milestone, not a certificate.",
    es: "Demostrar {level} Listening exige además retención retardada estable: ≥{ratio}% de tu precisión inmediata en re-exposiciones tras ≥{days} días. Sigue repasando: hasta entonces esta ruta es un hito de práctica, no un certificado.",
  },
  "listening.demoMet": {
    en: "Stable delayed retention over ≥{days} days — certificate-level evidence met for this route.",
    es: "Retención retardada estable durante ≥{days} días: la evidencia de nivel certificable de esta ruta está superada.",
  },
  "listening.routeCompetenceTitle": {
    en: "Competence by route (per CEFR level)",
    es: "Competencia por ruta (por nivel CEFR)",
  },
  "listening.routeCompetenceNote": {
    en: "\"Functional\" means the route gate is passed: a practice milestone, not a CEFR certificate. Only \"Demonstrated\" — route gate plus stable delayed retention (≥90%) over ≥7 days — reads as \"Listening — demonstrated\".",
    es: "«Funcional» significa que la puerta de la ruta está superada: un hito de práctica, no un certificado CEFR. Solo «Demostrado» —puerta de ruta + retención retardada estable (≥90%) durante ≥7 días— se lee como «Listening — demostrado».",
  },
  "listening.demoRetentionStatus": {
    en: "Delayed retention so far: {rate} after {exposures} long re-exposure(s) (needs ≥{ratio}%).",
    es: "Retención retardada hasta ahora: {rate} tras {exposures} re-exposición(ones) larga(s) (se necesita ≥{ratio}%).",
  },
  // Lectura de los anillos de ruta (P2/legibilidad): la cifra bajo cada nivel son
  // frases dominadas sobre el banco completo de la ruta, no el tamaño de la ruta.
  "listening.masteredOfTotal": {
    en: "Mastered {mastered} of {total}",
    es: "Dominadas {mastered} de {total}",
  },
  "listening.coveragePct": {
    en: "{pct}% of the bank",
    es: "{pct}% del banco",
  },
  // Requisito mínimo de la puerta (cobertura), en cada anillo con progreso.
  "listening.routeGateShort": {
    en: "Gate: master ≥{coverage}% (≥{min} of {total})",
    es: "Puerta: dominar ≥{coverage}% (≥{min} de {total})",
  },
  "listening.routeRingHelp": {
    en: "Each route trains its full bank. The number under a level is how many phrases you have mastered (e.g. \"30 of 205\"); passing the route is a practice milestone, not a CEFR level. Once the official bank of a route is mastered you can add generated extra practice from that route: the ring grows (e.g. \"205 of 260\") but the route gate and certification never change.",
    es: "Cada ruta entrena su banco completo. El número bajo cada nivel son las frases que dominas (p. ej. «30 de 205»); superar la ruta es un hito de práctica, no un nivel CEFR. Cuando dominas el banco oficial de una ruta puedes añadir práctica extra generada desde esa ruta: el anillo crece (p. ej. «205 de 260») pero la puerta de ruta y la certificación no cambian.",
  },
  "listening.routeCertNote": {
    en: "A CEFR level is certified separately from this route: level exam + evidence per skill + stable retention (≥7 days). This route only trains.",
    es: "El nivel CEFR se certifica aparte de esta ruta: examen de nivel + evidencia por destreza + retención estable (≥7 días). Esta ruta solo entrena.",
  },
  "listening.diagnostic": {
    en: "Your listening diagnostic",
    es: "Tu diagnóstico de listening",
  },
  "listening.showAnalysis": { en: "Show analysis", es: "Ver análisis" },
  "listening.hideAnalysis": { en: "Hide analysis", es: "Ocultar análisis" },
  "listening.accuracyByTopic": { en: "Accuracy by topic", es: "Precisión por tema" },
  "listening.accuracyByDifficulty": {
    en: "Accuracy by difficulty",
    es: "Precisión por dificultad",
  },
  "listening.retries": { en: "Retries", es: "Reintentos" },
  "listening.recovered": { en: "recovered", es: "recuperados" },
  "listening.retention": { en: "Retention", es: "Retención" },
  "listening.immediate": { en: "immediate", es: "inmediata" },
  "listening.delayed": { en: "delayed", es: "retardada" },
  "listening.completed": {
    en: "You've completed every listening route!",
    es: "¡Has completado todas las rutas de listening!",
  },
  "listening.next": { en: "Next", es: "Siguiente" },
  "listening.errorSkip": {
    en: "Skip to next question",
    es: "Saltar a la siguiente pregunta",
  },
  "listening.speakQuestion": {
    en: "Listen to the question",
    es: "Escuchar la pregunta",
  },
  "listening.levelHistoryTitle": {
    en: "Level {level} history",
    es: "Historial del nivel {level}",
  },
  "listening.skip": { en: "Skip", es: "Saltar" },
  "listening.reviewProgress": {
    en: "Reviewing level {level} · {done}/{total}",
    es: "Repasando nivel {level} · {done}/{total}",
  },
  "listening.reviewNext": {
    en: "Next phrase of the level",
    es: "Siguiente frase del nivel",
  },
  "listening.reviewFinish": {
    en: "Finish review",
    es: "Terminar repaso",
  },
  "listening.exitReview": {
    en: "Exit review",
    es: "Salir del repaso",
  },
  "listening.exitSession": {
    en: "Exit session",
    es: "Salir de la sesión",
  },
  "listening.drillProgress": {
    en: "Failed drill · level {level} · {done}/{total} mastered",
    es: "Drill de falladas · nivel {level} · {done}/{total} dominadas",
  },
  "listening.drillDone": {
    en: "You mastered all {total} failed phrases of level {level}!",
    es: "¡Has dominado las {total} frases falladas del nivel {level}!",
  },
  "listening.drillFinish": {
    en: "Finish practice",
    es: "Terminar práctica",
  },
  "listening.levelStates.failed": {
    en: "Failed ({count})",
    es: "Falladas ({count})",
  },
  "listening.levelStates.mastered": {
    en: "Mastered ({count})",
    es: "Dominadas ({count})",
  },
  "listening.levelStates.unseen": {
    en: "Not seen ({count})",
    es: "Sin ver ({count})",
  },
  "listening.levelItemsPhrases": {
    en: "phrases",
    es: "frases",
  },
  "listening.levelItemsSummary": {
    en: "{mastered} mastered · {failed} failed · {unseen} unseen",
    es: "{mastered} dominadas · {failed} falladas · {unseen} sin ver",
  },
  "listening.completedShort": {
    en: "Route completed",
    es: "Ruta completada",
  },
  "listening.levelItemsEmpty": {
    en: "No phrases in this group yet.",
    es: "Aún no hay frases en este grupo.",
  },
  "listening.repeatFailed": {
    en: "Repeat failed ({count})",
    es: "Repetir falladas ({count})",
  },
  "listening.practiceLevel": {
    en: "Practice level {level}",
    es: "Practicar nivel {level}",
  },
  "listening.reviewLevel": {
    en: "Review level {level}",
    es: "Repasar nivel {level}",
  },
  // Repaso de lo aprendido (V3.6): rotación solo por las frases ya dominadas.
  "listening.reviewLearned": {
    en: "Review learned ({count})",
    es: "Repasar lo aprendido ({count})",
  },
  "listening.reviewLearnedProgress": {
    en: "Reviewing what you learned · level {level} · {done}/{total}",
    es: "Repasando lo aprendido · nivel {level} · {done}/{total}",
  },
  // Práctica extra generada (V3.6): práctica ilimitada sobre ítems generados.
  "listening.generatedTag": {
    en: "generated practice",
    es: "práctica generada",
  },
  "listening.extraAddTitle": {
    en: "Add more practice to {level}",
    es: "Añadir más práctica a {level}",
  },
  "listening.extraAddLabel": {
    en: "Add",
    es: "Añadir",
  },
  "listening.extraAddCta": {
    en: "{count} more",
    es: "{count} más",
  },
  "listening.extraBreakdown": {
    en: "{base} official · +{extras} extra",
    es: "{base} oficiales · +{extras} extra",
  },
  "listening.extraHonestNote": {
    en: "These phrases are generated practice (local AI + synthetic voice), not official content. The route gate and your functional/demonstrated status are always calculated only over the official bank: adding extra practice never revokes a completed route or changes your certification.",
    es: "Estas frases son práctica generada (IA local + voz sintética), no contenido oficial. La puerta de ruta y tu estado funcional/demostrado se calculan siempre solo sobre el banco oficial: añadir práctica extra nunca revoca una ruta superada ni cambia tu certificación.",
  },
  "listening.extraGenerating": {
    en: "Generating extra practice… the local AI model is working and may take a few minutes. This tab can stay open.",
    es: "Generando práctica extra… el modelo de IA local está trabajando y puede tardar unos minutos. Puedes dejar esta pestaña abierta.",
  },
  "listening.extraDone": {
    en: "Added {added} extra phrase(s) to {level}.",
    es: "Se añadieron {added} frase(s) extra a {level}.",
  },
  "listening.extraError": {
    en: "Couldn't generate extra practice: {error}",
    es: "No se pudo generar la práctica extra: {error}",
  },
  "listening.levelItemsError": {
    en: "Could not load the level history.",
    es: "No se pudo cargar el historial del nivel.",
  },
  "listening.levelItemsDifficulty": {
    en: "difficulty",
    es: "dificultad",
  },
  "listening.levelItemsAttempts": {
    en: "attempts",
    es: "intentos",
  },
  "listening.audioGap": {
    en: "This audio realizes difficulty {realized} of the {declared} declared: part of the difficulty is not backed by the audio.",
    es: "Este audio realiza una dificultad {realized} de las {declared} declaradas: parte de la dificultad no está respaldada por el audio.",
  },
  "listening.audioGapTitle": {
    en: "Audio difficulty gap",
    es: "Diferencia de dificultad del audio",
  },
  "listening.resilience": {
    en: "Listening resilience",
    es: "Resiliencia auditiva",
  },
  "listening.resilienceMainWeakness": {
    en: "Main weakness",
    es: "Debilidad principal",
  },
  "listening.resilience.clear_speech": {
    en: "Clear speech",
    es: "Habla clara",
  },
  "listening.resilience.natural_speech": {
    en: "Natural speech",
    es: "Habla natural",
  },
  "listening.resilience.connected_speech": {
    en: "Connected speech",
    es: "Habla conectada",
  },
  "listening.resilience.fast_speech": {
    en: "Fast speech",
    es: "Habla rápida",
  },
  "listening.resilience.noise": {
    en: "Noise",
    es: "Ruido",
  },
  "listening.resilience.accents": {
    en: "Accents",
    es: "Acentos",
  },

  // Learning profile
  "profile.globalAbility": { en: "Global ability", es: "Capacidad global" },
  "profile.globalAbilityTitle": {
    en: "Continuous global ability (A1=1 … C2=6)",
    es: "Capacidad global continua (escala A1=1 … C2=6)",
  },
  "profile.bandTitle": {
    en: "Heuristic band aligned with CEFR (not an official certification)",
    es: "Banda heurística alineada con CEFR (no es una certificación oficial)",
  },
  // P2 (H7): cualquier badge del nivel *estimado* lleva el calificador explícito
  // "estimado · no certificado"; "demostrado" se reserva para los gates.
  "profile.estimatedQualifier": {
    en: "estimated · not certified",
    es: "estimado · no certificado",
  },
  "profile.bandNote": {
    en: "Per-skill bands are estimates aligned with CEFR — they are not certifications.",
    es: "Las bandas por destreza son estimaciones alineadas con el CEFR: no son certificaciones.",
  },
  "profile.readyFor": { en: "Ready for", es: "Preparado para" },
  "profile.workOn": { en: "Work on:", es: "Trabaja en:" },
  "profile.samples": { en: "samples", es: "muestras" },
  "profile.recentTrend": { en: "Recent trend", es: "Tendencia reciente" },
  "profile.vocabulary": { en: "Vocabulary", es: "Vocabulario" },
  "profile.mastered": { en: "mastered", es: "dominadas" },
  "profile.seen": { en: "seen", es: "vistas" },
  "profile.noWords": { en: "No words recorded.", es: "Sin palabras registradas." },
  "profile.avgPronunciation": {
    en: "Average pronunciation",
    es: "Pronunciación media",
  },
  "profile.recurringErrors": { en: "Recurring errors", es: "Errores recurrentes" },
  "profile.noErrors": {
    en: "No recurring errors detected.",
    es: "Sin errores recurrentes detectados.",
  },
  "profile.errorsOvercome": { en: "Errors overcome:", es: "Errores superados:" },
  "profile.recommendations": { en: "Recommendations", es: "Recomendaciones" },

  // Progress dashboard
  "progress.streak": { en: "Streak", es: "Racha" },
  "progress.days": { en: "days", es: "días" },
  "progress.bestStreak": { en: "Best streak", es: "Mejor racha" },
  "progress.lastActivity": { en: "Last activity", es: "Última actividad" },
  "progress.activity": { en: "Activity", es: "Actividad" },
  "progress.noActivity": { en: "No activity recorded.", es: "Sin actividad registrada." },
  "progress.messages": { en: "Messages", es: "Mensajes" },
  "progress.pronunciation": { en: "Pronunciation", es: "Pronunciación" },
  "progress.errorMastery": { en: "Error mastery", es: "Dominio de errores" },
  "progress.active": { en: "Active", es: "Activos" },
  "progress.resolved": { en: "Resolved", es: "Resueltos" },
  "progress.noActiveErrors": {
    en: "No active recurring errors.",
    es: "Sin errores recurrentes activos.",
  },
  "progress.noResolved": {
    en: "No resolved errors yet.",
    es: "Aún no hay errores resueltos.",
  },
  "progress.milestones": { en: "Milestones", es: "Hitos" },
  "progress.score": { en: "Score", es: "Puntuación" },
  "progress.confidence": { en: "Confidence", es: "Confianza" },
  "progress.evidence": { en: "Evidence", es: "Evidencia" },
  "progress.stability": { en: "Stability", es: "Estabilidad" },
  "progress.recentActivity": { en: "Recent activity", es: "Actividad reciente" },
  "progress.noRecentActivity": {
    en: "No recent activity.",
    es: "Sin actividad reciente.",
  },
  "progress.bucketAria": { en: "Grouping period", es: "Período de agrupación" },

  // Calidad del tutor
  "tutor.total": { en: "Total", es: "Total" },
  "tutor.english": { en: "English", es: "Inglés" },
  "tutor.conciseness": { en: "Conciseness", es: "Concisión" },
  "tutor.engagement": { en: "Engagement", es: "Engagement" },
  "tutor.aria": { en: "Tutor quality", es: "Calidad del tutor" },

  // Traducción de apoyo EN→ES (listening): ayuda a demanda que no cuenta como
  // intento ni afecta a las métricas. El alumno la pulsa solo cuando duda.
  "translate.showEs": {
    en: "Show Spanish translation (support aid)",
    es: "Mostrar traducción al español (ayuda)",
  },
  "translate.showEn": {
    en: "Back to English",
    es: "Volver al inglés",
  },
  "translate.unavailable": {
    en: "Translation unavailable: is the local AI model active?",
    es: "Traducción no disponible: ¿está activo el modelo local?",
  },

  // Barrido V3.6.1: textos de interfaz que antes se pintaban en inglés fijo.
  // Los nombres de actividad (skill.*, learn.conversation) quedan en inglés
  // en ambos idiomas por decisión de coherencia; el resto de chrome se traduce.
  "common.skipToContent": { en: "Skip to content", es: "Saltar al contenido" },

  // 429 del rate limiter local (V3.6.2): mensaje accionable en la lengua de la
  // UI, coherente con el `code: RATE_LIMITED` que devuelve el backend.
  "errors.rateLimited": {
    en: "The local server is busy: wait a few seconds and try again",
    es: "El servidor local está saturado: espera unos segundos e inténtalo de nuevo",
  },

  // Listening: tipo de audio (etiqueta honesta), buckets de retención, resumen
  // de producción y fila de sub-destrezas del diagnóstico.
  "listening.audioType.recorded": {
    en: "Real recording",
    es: "Grabación real",
  },
  "listening.audioType.mixed": {
    en: "Mix of recorded + synthetic",
    es: "Mezcla de grabación + sintética",
  },
  "listening.audioType.synthetic_multispeaker": {
    en: "Several synthetic voices",
    es: "Varias voces sintéticas",
  },
  "listening.audioType.real_world": {
    en: "Real-world audio (natural environment)",
    es: "Audio real (entorno natural)",
  },
  "listening.audioType.tts": {
    en: "Local synthetic voice (TTS)",
    es: "Voz sintética local (TTS)",
  },
  "listening.retentionBucket.0-2": { en: "0–2 days", es: "0–2 días" },
  "listening.retentionBucket.2-7": { en: "2–7 days", es: "2–7 días" },
  "listening.retentionBucket.7-30": { en: "7–30 days", es: "7–30 días" },
  "listening.retentionBucket.30plus": {
    en: "over 30 days",
    es: "más de 30 días",
  },
  "listening.breakdownWords": {
    en: "Correct words: {correct} · missing: {missing} · extra: {extra}",
    es: "Palabras correctas: {correct} · faltan: {missing} · sobran: {extra}",
  },
  "listening.dictationTitle": {
    en: "Dictation/Shadowing · {score}/100",
    es: "Dictado/Shadowing · {score}/100",
  },
  "listening.diagAuto": {
    en: "auto {pct}%",
    es: "auto {pct}%",
  },
  "listening.diagMean": {
    en: "mean {pct}%",
    es: "media {pct}%",
  },
  "listening.diagAudioGap": {
    en: "audio not backed",
    es: "audio sin respaldo",
  },

  // Pronunciación: fluidez, palabras por minuto y avisos por palabra.
  "pron.wpm": { en: "{count} words/min", es: "{count} palabras/min" },
  "pron.fluencyLevel.fluent": { en: "Fluent", es: "Fluido" },
  "pron.fluencyLevel.good": { en: "Good pace", es: "Buen ritmo" },
  "pron.fluencyLevel.slow": { en: "Slow", es: "Lento" },
  "pron.hint.missing": {
    en: "You missed: {words}",
    es: "Te faltaron: {words}",
  },
  "pron.hint.substituted": {
    en: "You substituted: {items}",
    es: "Sustituiste: {items}",
  },
  "pron.hint.extra": {
    en: "You added extra: {words}",
    es: "Añadiste de más: {words}",
  },
  "pron.wordsCorrect": {
    en: "{correct} of {total} words correct",
    es: "{correct} de {total} palabras correctas",
  },

  // Progreso: buckets de agrupación y tipos de evento.
  "progress.bucket.day": { en: "Day", es: "Día" },
  "progress.bucket.week": { en: "Week", es: "Semana" },
  "progress.bucket.month": { en: "Month", es: "Mes" },
  "progress.event.message": { en: "Message", es: "Mensaje" },
  "progress.event.exercise": { en: "Exercise", es: "Ejercicio" },
  "progress.event.correction": { en: "Correction", es: "Corrección" },
  "progress.event.pronunciation": {
    en: "Pronunciation",
    es: "Pronunciation",
  },
  "progress.event.conversation": {
    en: "Conversation",
    es: "Conversation",
  },

  // Plan del día (TodayPlan): píldoras de tipo, frase de repaso/refuerzo y
  // estabilidad. La destreza se muestra en inglés vía skill.*.
  "today.kind.weakness": { en: "Weakness", es: "Debilidad" },
  "today.kind.review": { en: "Review", es: "Repaso" },
  "today.kind.new": { en: "New", es: "Nuevo" },
  "today.kind.easy_wins": { en: "Boost", es: "Refuerzo" },
  "today.kindPhrase.review": { en: "Review", es: "Repasar" },
  "today.kindPhrase.easy_wins": { en: "Boost", es: "Refuerzo" },
  "today.stability": {
    en: "stability {pct}%",
    es: "estabilidad {pct}%",
  },

  // Writing: foco y botón del panel, marcador del recorrido.
  "writing.nextFocus": { en: "NEXT FOCUS", es: "PRÓXIMO FOCO" },
  "writing.practiceNow": { en: "PRACTICE NOW", es: "PRACTICAR AHORA" },
  "writing.you": { en: "YOU", es: "TÚ" },

  // Speaking: título del assessment y delta en puntos del diagnóstico.
  "assessment.titleScore": {
    en: "Speaking Assessment · {score}",
    es: "Evaluación de Speaking · {score}",
  },
  "speaking.deltaPts": {
    en: "{delta} pts",
    es: "{delta} puntos",
  },

  // Curso: marcadores de puerta de dominio superada/pendiente.
  "course.gatePass": { en: "PASS", es: "SUPERADO" },
  "course.gateDue": { en: "DUE", es: "PENDIENTE" },

  // --- Speaking por rutas de micro-conversación (V3.8) -----------------------
  // Cada nivel CEFR es una ruta de tarjetas de micro-conversación guiada
  // (situación + rol + línea del interlocutor con voz; el alumno responde
  // hablando y, tras la evaluación, se revela una respuesta modelo). Superar la
  // ruta es un hito de PRÁCTICA (estado techo `functional`); demostrar el nivel
  // exige el Speaking Assessment + evidencia de escenarios/misiones + retención,
  // no la ruta. Lectura honesta siempre: "rutas", nunca "certificado".
  "speaking.routesSubtitle": {
    en: "Each level is a route of guided micro-conversations: read the situation, listen to your interlocutor and answer out loud. After each answer you get feedback by criteria and a model response to compare. Passing a route is a practice milestone — demonstrating the level needs the oral exam, missions and retention, not the route.",
    es: "Cada nivel es una ruta de micro-conversaciones guiadas: lees la situación, oyes a tu interlocutor y respondes en voz alta. Tras cada respuesta recibes feedback por criterios y una respuesta modelo con la que compararte. Superar una ruta es un hito de práctica: demostrar el nivel exige el examen oral, las misiones y la retención, no la ruta.",
  },
  "speaking.loading": { en: "Loading…", es: "Cargando…" },
  "speaking.loadError": {
    en: "Couldn't load your speaking routes. Please try again.",
    es: "No se pudieron cargar tus rutas de speaking. Inténtalo de nuevo.",
  },
  "speaking.retry": { en: "Try again", es: "Reintentar" },
  "speaking.accuracy": { en: "Pass rate", es: "Aciertos" },
  "speaking.masteredOfTotal": {
    en: "Mastered {mastered} of {total}",
    es: "Dominadas {mastered} de {total}",
  },
  "speaking.routeFunctional": {
    en: "Practice milestone",
    es: "Hito de práctica",
  },
  "speaking.demoTitle": {
    en: "{level} Speaking — demonstrated",
    es: "{level} Speaking — demostrado",
  },
  "speaking.assessedLevel": {
    en: "Oral level demonstrated: {level}",
    es: "Nivel oral demostrado: {level}",
  },
  "speaking.assessedLevelNone": {
    en: "No oral exam taken yet",
    es: "Aún no has hecho el examen oral",
  },
  "speaking.completedShort": {
    en: "Route passed",
    es: "Ruta superada",
  },
  "speaking.routePendingCert": {
    en: "Covered, not certified yet",
    es: "Cubierta, aún sin certificar",
  },
  "speaking.routeGateIntro": {
    en: "Mastering the phrases isn't enough to pass {level}:",
    es: "Dominar las frases no basta para superar {level}:",
  },
  "speaking.routeGateLine": {
    en: "{coverage}% of the official cards mastered (≥{coverageRequired}%) · pass rate ≥{accuracyRequired}% ({accuracy}) · {topics}/{topicsRequired} topics · {checkpoint}/{checkpointRequired} passed on first try",
    es: "{coverage}% del banco oficial de tarjetas dominado (≥{coverageRequired}%) · aciertos ≥{accuracyRequired}% ({accuracy}) · {topics}/{topicsRequired} temas · {checkpoint}/{checkpointRequired} superadas a la primera",
  },
  "speaking.demoNotYet": {
    en: "{level} Speaking — not yet demonstrated",
    es: "{level} Speaking — aún no demostrado",
  },
  "speaking.demoRequires": {
    en: "Demonstrating {level} Speaking comes from the oral exam (Speaking Assessment) plus evidence from scenarios and missions and stable retention — not from this route. The route only trains; open the assessment to get certified.",
    es: "Demostrar {level} Speaking viene del examen oral (Speaking Assessment) más evidencia de escenarios y misiones y retención estable, no de esta ruta. La ruta solo entrena; abre el examen para certificar.",
  },
  "speaking.demoMet": {
    en: "You have demonstrated this oral level with the assessment and sustained evidence.",
    es: "Has demostrado este nivel oral con el examen y evidencia sostenida.",
  },
  // Bloques "demostrar el nivel" del panel de ruta.
  "speaking.demonstrateTitle": {
    en: "Demonstrate {level}",
    es: "Demostrar {level}",
  },
  "speaking.demonstrateNote": {
    en: "The route does not certify: {level} is demonstrated with the Speaking Assessment (oral exam) plus scenarios/missions and retention evidence.",
    es: "La ruta no certifica: {level} se demuestra con el Speaking Assessment (examen oral) más escenarios/misiones y evidencia de retención.",
  },
  "speaking.demonstrateCta": {
    en: "Take the Speaking Assessment",
    es: "Hacer el Speaking Assessment",
  },
  "speaking.backRoutes": {
    en: "Back to routes",
    es: "Volver a las rutas",
  },

  // Práctica extra generada (V3.7) por ruta.
  "speaking.extraAddTitle": {
    en: "Add more practice to route {level}",
    es: "Añadir más práctica a la ruta {level}",
  },
  "speaking.extraBreakdown": {
    en: "{base} official + {extras} generated",
    es: "{base} oficiales + {extras} generadas",
  },
  "speaking.extraHonestNote": {
    en: "You have mastered the official bank. Extra micro-conversation cards are generated locally by AI to keep training and consolidating. The route gate and certification never change: this practice extends the route, it doesn't raise it.",
    es: "Has dominado el banco oficial. Las tarjetas de micro-conversación extra se generan en local con IA para seguir entrenando y consolidando. La puerta de la ruta y la certificación no cambian: esta práctica amplía la ruta, no la sube de nivel.",
  },
  "speaking.extraGenerating": {
    en: "Generating conversation cards… this can take a minute.",
    es: "Generando tarjetas de conversación… puede tardar un minuto.",
  },
  "speaking.extraDone": {
    en: "{added} new cards added to route {level}.",
    es: "{added} tarjetas nuevas añadidas a la ruta {level}.",
  },
  "speaking.extraError": {
    en: "Couldn't add extra practice: {error}",
    es: "No se pudo añadir práctica extra: {error}",
  },
  "speaking.extraAddLabel": { en: "Add:", es: "Añadir:" },
  "speaking.extraAddCta": {
    en: "+{count} cards",
    es: "+{count} tarjetas",
  },
  "speaking.generatedTag": { en: "Generated", es: "Generada" },

  // Historial por tarjeta del panel de nivel.
  "speaking.levelItemsError": {
    en: "Couldn't load this route's cards.",
    es: "No se pudieron cargar las tarjetas de esta ruta.",
  },
  "speaking.levelItemsPhrases": { en: "cards", es: "tarjetas" },
  "speaking.levelItemsSummary": {
    en: "{mastered} mastered · {failed} failed · {unseen} unseen",
    es: "{mastered} dominadas · {failed} falladas · {unseen} sin intentar",
  },
  "speaking.levelItemsEmpty": {
    en: "Nothing here yet.",
    es: "Nada por aquí todavía.",
  },
  "speaking.levelStates.failed": {
    en: "Failed ({count})",
    es: "Falladas ({count})",
  },
  "speaking.levelStates.mastered": {
    en: "Mastered ({count})",
    es: "Dominadas ({count})",
  },
  "speaking.levelStates.unseen": {
    en: "Unseen ({count})",
    es: "Sin intentar ({count})",
  },
  "speaking.levelItemsDifficulty": { en: "level", es: "nivel" },
  "speaking.levelItemsAttempts": { en: "attempts", es: "intentos" },
  "speaking.repeatFailed": {
    en: "Repeat failed ({count})",
    es: "Repetir fallidas ({count})",
  },
  "speaking.reviewLearned": {
    en: "Review learned ({count})",
    es: "Repasar aprendidas ({count})",
  },
  "speaking.practiceLevel": {
    en: "Practice {level}",
    es: "Practicar {level}",
  },
  "speaking.reviewLevel": {
    en: "Review {level}",
    es: "Repasar {level}",
  },

  // Sesión read-aloud.
  "speaking.modeLevel": {
    en: "Practice {level}",
    es: "Practicar {level}",
  },
  "speaking.modeDrill": {
    en: "Repeating failed cards",
    es: "Repitiendo fallidas",
  },
  "speaking.modeReview": {
    en: "Reviewing {level}",
    es: "Repasando {level}",
  },
  "speaking.exitSession": {
    en: "Exit this practice",
    es: "Salir de esta práctica",
  },
  "speaking.sessionEnded": {
    en: "Practice session completed",
    es: "Sesión de práctica completada",
  },
  "speaking.doneDrillLine": {
    en: "You have mastered the {total} pending cards of {level}. Great work!",
    es: "Has dominado las {total} tarjetas pendientes de {level}. ¡Buen trabajo!",
  },
  "speaking.doneReviewLine": {
    en: "You reviewed {total} mastered cards of {level}.",
    es: "Has repasado {total} tarjetas dominadas de {level}.",
  },
  "speaking.doneLevelLine": {
    en: "You completed a full round over the {total} cards of {level}.",
    es: "Has completado una vuelta por las {total} tarjetas de {level}.",
  },
  "speaking.record": { en: "Record your answer", es: "Grabar respuesta" },
  "speaking.stop": { en: "Stop", es: "Parar" },
  "speaking.evaluating": { en: "Evaluating…", es: "Evaluando…" },
  "speaking.recordHint": {
    en: "Answer out loud in English, in a quiet place",
    es: "Responde en voz alta en inglés, en un sitio tranquilo",
  },
  "speaking.attemptError": {
    en: "Couldn't evaluate your answer: ",
    es: "No se pudo evaluar tu respuesta: ",
  },
  "speaking.skip": { en: "Skip to another card", es: "Saltar a otra tarjeta" },
  "speaking.continue": { en: "Continue", es: "Continuar" },
  "speaking.passedTitle": { en: "Nice answer!", es: "¡Bien respondido!" },
  "speaking.notPassedTitle": {
    en: "Not quite — compare with the model answer",
    es: "Casi — compara con la respuesta modelo",
  },
  "speaking.resultPassed": { en: "Passed", es: "Superada" },
  "speaking.resultNotPassed": { en: "Not passed", es: "No superada" },
  "speaking.overallShort": { en: "overall", es: "global" },
  "speaking.youSaidLabel": { en: "What you said", es: "Lo que has dicho" },
  "speaking.criteriaIntro": {
    en: "Feedback by criteria",
    es: "Feedback por criterios",
  },
  "speaking.resultHonestNote": {
    en: "This scores your spoken answer to the situation on the spot. It is training feedback for the route — it doesn't certify a CEFR level by itself.",
    es: "Esto puntúa tu respuesta hablada a la situación al momento. Es retroalimentación de entrenamiento de la ruta: no certifica por sí solo un nivel CEFR.",
  },

  // Escenario superior de micro-conversación (tarjeta de intercambio).
  "speaking.exchangeHint": {
    en: "Answer out loud",
    es: "Responde en voz alta",
  },
  "speaking.setupLabel": { en: "Situation", es: "Situación" },
  "speaking.roleLabel": { en: "You", es: "Tú" },
  "speaking.interlocutorLabel": { en: "Interlocutor", es: "Interlocutor" },
  "speaking.playOpening": {
    en: "Hear your interlocutor",
    es: "Oír al interlocutor",
  },
  "speaking.playModel": {
    en: "Hear the model answer",
    es: "Oír la respuesta modelo",
  },
  "speaking.modelResponseTitle": {
    en: "Model answer",
    es: "Respuesta modelo",
  },
  "speaking.drillHint": {
    en: "Repeat until you master the failed cards",
    es: "Repite hasta dominar las tarjetas fallidas",
  },
  "speaking.sessionHint": {
    en: "Answer out loud — each response is scored.",
    es: "Responde en voz alta — cada respuesta se puntúa.",
  },

  // Mapa de rutas bajo el escenario (tira de anillos + panel del nivel).
  "speaking.routesMapTitle": { en: "Routes", es: "Rutas" },
  "speaking.routesMapHint": {
    en: "Open a route to practice, drill or review",
    es: "Abre una ruta para practicar, repasar o añadir práctica",
  },
  "speaking.routeNote": {
    en: "{level} is your current route — practice it here whenever you want.",
    es: "{level} es tu ruta actual — practícala aquí cuando quieras.",
  },
  "speaking.routeCertNote": {
    en: "Passing a route is a practice milestone. Demonstrating the level requires the oral exam (Speaking Assessment) plus evidence from scenarios, missions and stable retention — never the route by itself.",
    es: "Superar una ruta es un hito de práctica. Demostrar el nivel exige el examen oral (Speaking Assessment) más evidencia de escenarios, misiones y retención estable — nunca la ruta por sí sola.",
  },
  "speaking.routeRingHelp": {
    en: "Tap a level to open its practice panel below.",
    es: "Toca un nivel para abrir su panel de práctica.",
  },
  "speaking.levelHistoryTitle": {
    en: "{level} route — open its practice panel",
    es: "Ruta {level} — abrir su panel de práctica",
  },
  "speaking.coveragePct": {
    en: "{pct}% covered",
    es: "{pct}% cubierto",
  },
};

export function translate(lang: Lang, key: string): string {
  const entry = STRINGS[key];
  if (!entry) return key;
  return entry[lang];
}
