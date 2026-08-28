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
  "nav.learn": { en: "Learn", es: "Aprender" },
  "nav.course": { en: "Course", es: "Curso" },
  "nav.progress": { en: "Progress", es: "Progreso" },
  "nav.chat": { en: "Chat", es: "Chat" },

  // Destrezas
  "skill.listening": { en: "Listening", es: "Listening" },
  "skill.speaking": { en: "Speaking", es: "Speaking" },
  "skill.reading": { en: "Reading", es: "Reading" },
  "skill.writing": { en: "Writing", es: "Writing" },
  "skill.grammar": { en: "Grammar", es: "Gramática" },
  "skill.pronunciation": { en: "Pronunciation", es: "Pronunciación" },
  "skill.vocabulary": { en: "Vocabulary", es: "Vocabulario" },

  // Grupos de destrezas
  "group.primary": { en: "Primary skills", es: "Destrezas principales" },
  "group.support": { en: "Support", es: "Apoyo" },

  // Marca
  "brand.subtitle": { en: "100% local · Ollama", es: "100% local · Ollama" },

  // Home
  "home.morning": { en: "Good morning", es: "Buenos días" },
  "home.afternoon": { en: "Good afternoon", es: "Buenas tardes" },
  "home.evening": { en: "Good evening", es: "Buenas noches" },
  "home.subtitle": {
    en: "Continue your English journey.",
    es: "Continúa tu camino con el inglés.",
  },
  "home.nextStep": { en: "Today's next step", es: "El siguiente paso de hoy" },
  "home.continue": { en: "Continue", es: "Continuar" },
  "home.whyThisActivity": { en: "Why?", es: "¿Por qué?" },
  "home.start": { en: "Start", es: "Empezar" },
  "home.review": { en: "Review", es: "Repasar" },
  "home.today": { en: "Today", es: "Hoy" },
  "home.yourProgress": { en: "Your progress", es: "Tu progreso" },
  "home.readyFor": {
    en: "Ready for the next level",
    es: "Preparación para el siguiente nivel",
  },
  "home.nextFocus": { en: "Next focus", es: "Siguiente foco" },
  "home.practiceNow": { en: "Practice now", es: "Practicar ahora" },
  "home.yourSkills": { en: "Your skills", es: "Tus destrezas" },
  "home.streak": { en: "day streak", es: "días de racha" },
  "home.bestStreak": { en: "best streak", es: "mejor racha" },
  "home.activity": { en: "recent activity", es: "actividad reciente" },
  "home.improving": { en: "Improving", es: "Mejorando" },
  "home.stable": { en: "Stable", es: "Estable" },
  "home.needsReview": { en: "Needs review", es: "Repasar" },
  "home.min": { en: "min", es: "min" },
  "home.reviewN": { en: "review", es: "repasa" },
  "home.practiceN": { en: "practice", es: "practica" },
  "home.youAreHere": { en: "You are here", es: "Estás aquí" },
  "home.allDone": {
    en: "All done for today. Great work!",
    es: "Todo hecho por hoy. ¡Buen trabajo!",
  },

  // Categorías de sesión
  "kind.weakness": { en: "Weakness", es: "Debilidad" },
  "kind.review": { en: "Review", es: "Repaso" },
  "kind.listening": { en: "Listening", es: "Listening" },
  "kind.new": { en: "New", es: "Nuevo" },
  "kind.easyWins": { en: "Boost", es: "Refuerzo" },

  // Razones de la siguiente actividad
  "reason.due_for_review": { en: "Due for review", es: "Repaso pendiente" },
  "reason.weak_subskill": { en: "Weak sub-skill", es: "Sub-destreza débil" },
  "reason.weak_skill": { en: "Weak skill", es: "Destreza débil" },
  "reason.next_in_path": { en: "Next in your path", es: "Siguiente en tu camino" },
  "reason.confidence_boost": { en: "Confidence boost", es: "Refuerzo de confianza" },

  // Progress
  "progress.title": { en: "Your progress", es: "Tu progreso" },
  "progress.overall": { en: "Overall", es: "General" },
  "progress.mainFocus": { en: "Main focus", es: "Foco principal" },
  "progress.seeDetails": { en: "See details", es: "Ver detalles" },
  "progress.improving": { en: "Improving", es: "Mejorando" },
  "progress.stable": { en: "Stable", es: "Estable" },
  "progress.needsReview": { en: "Needs review", es: "Repasar" },
  "mastery.strong": { en: "Strong", es: "Fuerte" },
  "mastery.developing": { en: "Developing", es: "En desarrollo" },
  "mastery.needsPractice": { en: "Needs practice", es: "Necesita práctica" },

  // Course
  "course.title": { en: "Your English journey", es: "Tu viaje en inglés" },
  "course.subtitle": { en: "CEFR curriculum", es: "Currículum CEFR" },
  "course.mastered": { en: "mastered", es: "dominados" },
  "course.continue": { en: "Continue", es: "Continuar" },
  "course.placementTest": { en: "Placement test", es: "Test de nivel" },
  "course.finalExam": { en: "Final exam", es: "Examen final" },
  "course.back": { en: "Back", es: "Volver" },
  "course.you": { en: "You", es: "Tú" },
  "course.milestones": { en: "milestones", es: "hitos" },
  "course.completed": { en: "Completed", es: "Completado" },
  "course.inProgress": { en: "In progress", es: "En curso" },
  "course.notStarted": { en: "Not started", es: "Sin empezar" },
  "course.locked": { en: "Locked", es: "Bloqueado" },
  "course.cefrLevel": { en: "CEFR level", es: "Nivel CEFR" },
  "course.canDo": { en: "What you can do", es: "Qué puedes hacer" },
  "course.youAreHere": { en: "You are here", es: "Estás aquí" },

  // Settings
  "settings.title": { en: "Settings", es: "Ajustes" },
  "settings.appearance": { en: "Appearance", es: "Apariencia" },
  "settings.audio": { en: "Audio", es: "Audio" },
  "settings.ai": { en: "AI model", es: "Modelo IA" },
  "settings.advanced": { en: "Advanced", es: "Avanzado" },
  "settings.system": { en: "System", es: "Sistema" },
  "settings.interfaceLanguage": {
    en: "Interface language",
    es: "Idioma de la interfaz",
  },
  "settings.model": { en: "AI model", es: "Modelo IA" },
  "settings.back": { en: "Back", es: "Volver" },
  "settings.version": { en: "Version", es: "Versión" },
  "settings.lanUrl": { en: "LAN URL", es: "URL LAN" },

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

  // Común
  "common.loading": { en: "Loading…", es: "Cargando…" },
  "common.close": { en: "Close", es: "Cerrar" },
  "common.back": { en: "Back", es: "Volver" },
  "common.done": { en: "Done", es: "Hecho" },
  "common.next": { en: "Next", es: "Siguiente" },
  "common.completed": { en: "Completed", es: "Completado" },
  "common.great": { en: "Great.", es: "Genial." },
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
  "help.viewDocs": { en: "View documentation", es: "Ver en la documentación" },
  "help.documentation": { en: "Documentation", es: "Documentación" },
  "help.author": {
    en: "Author: José Alberto Velasco · josealberto.vel@gmail.com",
    es: "Autor: José Alberto Velasco · josealberto.vel@gmail.com",
  },
  "help.what.title": { en: "What is English Tutor?", es: "¿Qué es English Tutor?" },
  "help.what.body": {
    en: "An English tutor that converses with you by text or voice. It runs 100% on your computer, with no internet or accounts: your privacy is guaranteed.",
    es: "Un profesor de inglés que conversa contigo por texto o voz. Funciona 100% en tu ordenador, sin Internet ni cuentas: tu privacidad está garantizada.",
  },
  "help.start.title": { en: "Getting started", es: "Cómo empezar" },
  "help.start.body": {
    en: "Choose your profile in the top right and type or tap the microphone. You can change practice mode at any time.",
    es: "Elige tu perfil arriba a la derecha y escribe o pulsa el micrófono. Puedes cambiar de modo de práctica en cualquier momento.",
  },
  "help.modes.title": { en: "Practice modes", es: "Modos de práctica" },
  "help.modes.body": {
    en: "Conversation (chat freely), Grammar (correct sentences), Exercises (guided practice) and Pronunciation (speak and measure your accent).",
    es: "Conversación (charlar libre), Gramática (corregir frases), Ejercicios (práctica guiada) y Pronunciación (hablar y medir tu acento).",
  },
  "help.course.title": { en: "CEFR course", es: "Curso CEFR" },
  "help.course.body": {
    en: "A journey through levels (A1, A2, B1…) with objectives, quick assessments and a final exam. You advance level by level at your own pace.",
    es: "Un recorrido por niveles (A1, A2, B1…) con objetivos, evaluaciones rápidas y un examen final. Avanzas nivel a nivel a tu ritmo.",
  },
  "help.listening.title": { en: "Listening comprehension", es: "Comprensión auditiva" },
  "help.listening.body": {
    en: "Listen to a sentence, answer the question and pass each level. Your results are saved per profile and tell you when you advance.",
    es: "Escucha una frase, responde la pregunta y supera cada nivel. Tus aciertos se guardan por perfil y te indican cuándo avanzas.",
  },
  "help.troubleshooting.title": { en: "Common issues", es: "Problemas frecuentes" },
  "help.troubleshooting.body": {
    en: "If the tutor doesn't respond, make sure Ollama is running. Technical details and the full guide are in the documentation.",
    es: "Si el profesor no responde, asegúrate de que Ollama esté arrancado. Los detalles técnicos y la guía completa están en la documentación.",
  },

  // Conectar un dispositivo (LAN / móvil)
  "connect.title": {
    en: "Connect a device",
    es: "Conectar un dispositivo",
  },
  "connect.subtitle": {
    en: "Use English Tutor from your phone or tablet on the same local network.",
    es: "Usa English Tutor desde tu móvil o tableta en la misma red local.",
  },
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
  "connect.trustHelp": {
    en: "How to connect and trust the certificate",
    es: "Cómo conectar y confiar el certificado",
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
  "panels.yourProgress": { en: "Your progress", es: "Tu progreso" },
  "panels.todayPlan": { en: "Today's plan", es: "Plan de hoy" },
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
  "listening.speed": { en: "Speed:", es: "Velocidad:" },
  "listening.audioUnavailable": {
    en: "Reference audio not available; using live generated voice.",
    es: "Audio de referencia no disponible; usando voz generada en vivo.",
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
  "listening.scoreOf": { en: "Correct", es: "Aciertos" },
  "listening.currentLevel": { en: "Current level", es: "Nivel actual" },
  "listening.accuracyByTopic": { en: "Accuracy by topic", es: "Precisión por tema" },
  "listening.accuracyByDifficulty": {
    en: "Accuracy by difficulty",
    es: "Precisión por dificultad",
  },
  "listening.retries": { en: "Retries", es: "Reintentos" },
  "listening.seen": { en: "seen", es: "vistos" },
  "listening.recovered": { en: "recovered", es: "recuperados" },
  "listening.retention": { en: "Retention", es: "Retención" },
  "listening.immediate": { en: "immediate", es: "inmediata" },
  "listening.delayed": { en: "delayed", es: "retardada" },
  "listening.completed": {
    en: "You've completed all listening comprehension levels!",
    es: "¡Has completado todos los niveles de comprensión auditiva!",
  },
  "listening.next": { en: "Next", es: "Siguiente" },
  "listening.review": { en: "review", es: "revisar" },
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
};

export function translate(lang: Lang, key: string): string {
  const entry = STRINGS[key];
  if (!entry) return key;
  return entry[lang];
}
