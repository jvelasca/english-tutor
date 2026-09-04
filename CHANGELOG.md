# Changelog

Todas las versiones notables de English Tutor. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y este proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

## [3.6.2] — 2026-09-04

**Estado del servidor en el lanzador + corrección del 429 espurio.**
El 429 «Demasiadas peticiones» que aparecía en la app cuando el servidor local
estaba saturado lo devolvía el rate limiter propio (`SecurityMiddleware`), no
Ollama: cuenta peticiones por IP en ventanas de 60 s y, al saturarse el
servidor (generación de práctica extra con IA local, TTS Piper), las ráfagas
de pollers, reintentos del usuario y sondas del lanzador superaban los topes y
se rechazaban en cascada. Además, el launcher solo mostraba «Activo/Detenido» y
no permitía ver cuándo el backend estaba trabajando. En esta versión se
endurece el rate limiter para uso local (topes holgados, `/api/health` exento
de cupo y de 429), se telemetrifican los rechazos y el launcher muestra la
«Actividad del servidor».

### Cambiado (backend)
- `security.py`: las peticiones GET/HEAD a `/api/health` quedan exentas del rate
  limit (nunca consumen cupo ni pueden recibir 429, así el health-check y el
  launcher siguen vivos aunque el servidor esté saturado); topes subidos para
  uso local razonable (`_DEFAULT_LIMIT` 600 → 1200; `/api/chat` 120 → 240,
  `/api/voz/transcribe` 60 → 180, `upload`/`backup` 30 → 60, `restore`
  10 → 20); el 429 ahora responde con `{"detail", "code": "RATE_LIMITED"}` y
  `Retry-After: 5`, con mensaje accionable y `logger.warning` al rechazar.
- `security.py`: nuevo `rate_limit_snapshot(window_seconds)` que cuenta los
  rechazos del último minuto, y `is_exempt(path)` (V3.6.2).

### Añadido (backend)
- `GET /api/system/status` (sin candado admin, como `/api/health`): devuelve
  `generation.running/jobs` (trabajos de práctica extra en curso, por nivel) y
  `rate_limited.rejected_last_minute` desde `security.rate_limit_snapshot()`.
- `repositories/listening.py`: `list_running_generation_jobs()`.

### Cambiado (launcher)
- Nueva sección desplegable **«Actividad del servidor»**: línea de trabajo
  («En reposo» / «Generando práctica extra (A1)…») y rechazos por saturación
  del último minuto; verde en reposo y ámbar al trabajar o rechazar. Cuando el
  backend está generando o rechazando, la píldora de cabecera pasa a
  «En marcha · generando…» / «En marcha · saturado» en ámbar.
- `status.py`: `fetch_server_status()`; `ui.py`: helper puro `server_activity`.

### Cambiado (frontend)
- `api/client.ts`: ante un 429 con `code: RATE_LIMITED`, el mensaje de error se
  traduce a la lengua activa (`errors.rateLimited`) en vez de mostrar el texto
  interno del backend. `utils/i18n.ts`: clave `errors.rateLimited` (EN/ES).

### Verificación
- Backend: `pytest tests/test_security.py tests/test_system_status.py` en verde
  (exención de `/api/health`, payload `code`/`Retry-After`, `rate_limit_snapshot`,
  endpoint `/api/system/status` con/sin trabajos y rechazos).
- Launcher: `pytest tests` (74 tests) en verde (helpers puros de la nueva
  sección y `fetch_server_status` con mock).
- Frontend: `npx tsc --noEmit` y `npx vitest run src/api/client.test.ts` en verde
  (429 localizado en ES/EN y `detail` conservado para otros errores).

## [3.6.1] — 2026-09-04

**Atajos de APRENDER + coherencia de idioma.**
La franja superior de cada práctica de APRENDER (Listening, Speaking,
Pronunciation, Conversation, Vocabulary, Grammar) deja de ser solo una flecha de
vuelta al hub: ahora muestra un **selector con las 6 actividades** (icono +
nombre; solo iconos en pantallas estrechas, con `title`/aria) que navega por
hash y resalta la activa. Los **nombres de actividad se unifican en inglés en
ambos idiomas** (Grammar/Pronunciation/Vocabulary/Conversation, igual que ya
estaban Listening/Speaking/Reading/Writing) y se barre el chrome que se pintaba
en inglés fijo aunque la UI estuviera en español.

### Añadido (frontend)
- `components/LearnActivitySwitcher.tsx` (nuevo): atajo entre actividades,
  reutiliza los iconos del hub y `learnActivityPath`; integrado en la franja de
  `PracticeView` (práctica libre de Listening/Pronunciación/Gramática y de
  Conversar, oculto durante una lección del curso), en `SpeakingFreePractice` y
  en el `SubpageHeader` de Vocabulario.

### Cambiado
- `utils/i18n.ts`: `skill.grammar/pronunciation/vocabulary` y
  `learn.conversation` con el mismo valor en `en` y `es` (nombres en inglés).
- Chrome localizado con la UI en español: tipo de audio y buckets de retención
  de listening (`listening.audioType.*`, `listening.retentionBucket.*`,
  `utils/listeningLabels.ts`), resumen del dictado y fila de sub-destrezas del
  diagnóstico (`auto/mean/audio not backed`), fluidez/palabras por minuto y
  avisos por palabra de pronunciación (`pron.*`), píldoras y estabilidad del
  plan del día (`today.kind.*`, `today.stability`), foco y botón de Writing
  (`writing.nextFocus/practiceNow`), marcador del recorrido (`writing.you`),
  título del Speaking Assessment y delta en puntos (`assessment.titleScore`,
  `speaking.deltaPts`), marcadores de puerta del curso (`course.gatePass/Due`)
  y skip-link (`common.skipToContent`).

### Sin traducir (a propósito)
Se mantienen intencionalmente en inglés y se anotan aquí para no reabrirlos:
nombres de *topic* del banco y sub-destrezas de listening (datos), frases de
ejemplo conversacionales y nombres de criterios de rúbrica de speaking/writing
("Task achievement", "Grammatical control", … — jerga de assessment).

### Verificación
- Frontend: `npx tsc --noEmit` y `npx vitest run` (320 tests) en verde;
  Playwright en verde (smoke ampliado: el atajo de actividades es visible en
  APRENDER/LISTENING y pulsar Vocabulario navega a su hoja).
- Comprobación manual con la UI en español: nombres de actividad en inglés y
  resto de la interfaz en español en el hub de APRENDER y sus 6 prácticas.

## [3.6.0] — 2026-09-04

**Listening: práctica ilimitada con ítems generados + repaso de lo aprendido.**
Cada ruta (A1..C2) era un banco curado finito: al dominarlo no quedaban frases
nuevas que practicar en ese nivel. Ahora el alumno puede pedir más práctica
dentro de la ruta y el backend genera ítems completos
(`{script, question, options, …}`) con el modelo local *utilizable* (nunca los
`UNUSABLE_MODELS`), validados de forma determinista antes de publicarse —la
opción correcta debe ser un fragmento literal del guion normalizado, así la
respuesta siempre es verificable por audio— y con el audio sintetizado por Piper
bajo demanda con la caché existente.

La práctica generada es **contenido complementario, no oficial**: la puerta de
ruta, `completed`, el estado `functional`/`demonstrated` y el routing adaptativo
se calculan siempre solo sobre el banco curado, así que añadir extras nunca
revoca una ruta superada ni encarece certificarla. El anillo de la ruta muestra
el desglose «205 oficiales · +55 extra» y el denominador crece («Dominadas 205
de 260»), y desde cada ruta se puede **repasar lo aprendido** (rotación solo
sobre las frases ya dominadas, además del drill de falladas y de la ruta
completa).

### Añadido (backend)
- `repositories/db.py`: tablas `listening_generated` (catálogo global de ítems
  generados), `listening_route_extras` (activación por usuario, reversible) y
  `listening_generation_jobs` (trabajos de generación en segundo plano).
- `services/listening_generate.py` (nuevo): generador con prompt CEFR por nivel
  (tema/sub-destreza), parseo estricto del JSON, validación determinista
  (opción correcta literal en el guion, distractores sin colisión) y
  `GENERATOR_VERSION`.
- `services/listening.py`: `route_questions`/`resolve_question` con extras
  (dedupe por id), selector de repaso `only_mastered`; `route_gate`,
  `level_status` y `current_level` siguen sobre el banco curado sin recibir
  extras.
- `domain/listening_extras.py` (nuevo): orquestación del trabajo de generación
  (lotes, dedupe por script contra banco curado y catálogo, activación en la
  ruta al terminar).
- `domain/listening.py` + `schemas/listening.py` + `routers/listening.py`:
  `POST/GET/DELETE /api/listening/routes/{level}/extras[…]`; stats por ruta con
  `base_total`/`extras`/`extras_mastered`; ítems con `source` `"base"`/`"generated"`;
  ids `g-*` resueltos en `submit_answer`/`get_audio`; modo de sesión `mastered`.

### Añadido (frontend)
- `api/listening.ts` + `types/api.ts`: clientes y tipos de extras (trabajo,
  activación por ruta) y de los nuevos campos de stats/ítems.
- `features/listening/ListeningPractice.tsx`: anillo base+extras con desglose
  «oficiales + extra», estado del trabajo de generación (en marcha / hecho /
  error) y aviso honesto de que los ítems generados no alteran la certificación.
- `features/listening/ListeningLevelPanel.tsx`: botón **«Repasar lo aprendido
  (N)»**, etiqueta «práctica generada» en las filas generadas y bloque **«Añadir
  más práctica a {level}»** (cantidades 10/25/50), visible al dominar el banco
  oficial.
- `features/listening/listeningSession.ts`: nueva variante de sesión
  `mode: "mastered"` (misma vuelta LRU que `level` pero solo dominadas).
- `utils/i18n.ts`: claves `listening.reviewLearned*`, `listening.extra*`,
  `listening.generatedTag` y el aviso honesto, en ES y EN.

### Verificación
- Backend: tests del generador con cliente Ollama simulado, no-regresión de la
  puerta al añadir extras, repaso solo-dominadas y endpoints.
- Frontend: `npx tsc --noEmit` y `npx vitest run` (319 tests) en verde; smoke
  visual de Playwright ampliado con la captura `listening-route` (panel de ruta
  desplegado), en verde.

## [3.5.8] — 2026-09-04

**Auditoría de UI (contraste claro/oscuro + QR).** El código QR de
"Conectar un dispositivo" (Ajustes → Sistema y popover "Ready" del footer) se
pintaba con módulos negros sobre el fondo de tarjeta, que en modo oscuro es casi
negro: el QR quedaba invisible. Ahora el QR vive siempre sobre una tarjeta
blanca independiente del tema, así que se escanea igual en claro y en oscuro.

Además se hizo una pasada de auditoría por contraste (ratio WCAG calculado por
elemento con texto en todas las pantallas, en ambos temas) que corrigió los
puntos de legibilidad más claros.

### Cambiado (frontend)
- `components/ConnectDeviceCard.tsx`: el QR se muestra sobre tarjeta blanca fija
  (`bg-white`, módulos `#000`), sin depender de `bg-background`.
- `styles/legacy.css`: nuevos tokens de acento para texto (`--color-accent-soft`;
  índigo claro en oscuro, índigo oscuro en claro) usados por
  `.cefr-badge.intermediate` (la insignia "B1" era ilegible en oscuro, ratio 2.65);
  `--color-warning` en claro más oscuro (`#b45309`) para el texto ámbar sobre
  blanco (A1/A2, etiquetas de estado); `--color-text-faint` más legible en ambos
  temas (fechas, ejes y subtítulos de la línea de tiempo).
- `components/UserMenu.tsx` + `.user-avatar--placeholder`: el avatar provisional
  "?" sin perfil tenía texto blanco sobre fondo blanco en modo claro; ahora lleva
  fondo neutro y borde visibles.
- Tests visuales estables (`tests/visual/`): con la ProfileGate (V3.5.7), un
  navegador con varios perfiles y sin cookie mostraba la puerta y bloqueaba la
  interacción. Nuevo helper `gateHelper.ts` que crea/recupera el perfil de test
  "Visual Tester" vía API y mockea `GET /api/users` con un único perfil para que
  la app lo auto-seleccione; aplicado a `smoke`, `mobile` y `resize`.

### Verificación
- Sonda de contraste en 9 pantallas × 2 temas: insignia B1 oscuro 2.65 → ≥4.5;
  ámbar claro 3.19 → 4.43–4.98; faint oscuro 3.76 → ≥4.9, claro 2.70 → 3.74.
- Suite visual Playwright completa (desktop/tablet/mobile): 24 tests en verde
  (14 ejecutados, 10 skips de breakpoint previstos).
- `npx tsc --noEmit` y `npx vitest run` (318 tests) en verde.

## [3.5.7] — 2026-09-04

**Selector de perfil al arrancar.** Si la app se abre en un navegador nuevo y
no hay ningún usuario definido (sin cookie recordada y con varios perfiles, o
todavía sin perfiles creados), en lugar de quedarse con un usuario sin
seleccionar o crear uno en silencio, ahora muestra la puerta **"Selecciona un
usuario o crea uno nuevo"** con la lista de perfiles y el campo para crear uno.
Hasta que no se elige un perfil la app no se puede usar (todo cuelga de
`userId`), así que la puerta no se puede cerrar sin elegir.

### Cambiado (frontend)
- `hooks/useChat.ts`: ya **no se crea un perfil por defecto en silencio** cuando
  no hay ninguno; nuevo estado `usersLoaded` para distinguir "cargando" de "sin
  perfil seleccionado". `addUser` ahora devuelve si el backend respondió.
- `components/ProfileGate.tsx` (nuevo): diálogo no cerrable con la lista de
  perfiles existentes (avatar + nombre) y el formulario "Nuevo perfil"; si el
  backend no responde al crear, muestra un aviso en vez de fallar en silencio.
- `App.tsx`: muestra `ProfileGate` cuando `usersLoaded && !currentUserId`.
- Claves i18n `user.choose*`, `user.noProfilesYet`, `user.createProfile` y
  `user.createError`.

Nota: el comportamiento de un solo perfil se conserva (al ser único se
auto-selecciona al abrir cualquier navegador, sin preguntar).

### Verificación
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (318 tests) en verde.

## [3.5.6] — 2026-09-04

**Modelos no utilizables fuera de la app.** `qwen3.5:9b` quedó diagnosticado como
inutilizable en este equipo (en CPU tarda 10–64 s por turno y se descarga/recarga
entre llamadas). Ya no aparece en las opciones de configuración (Ajustes → IA) ni
se usa como modelo por defecto en ningún flujo; la app trabaja con `llama3.1:8b`
(instalado y rápido). La lista de excluidos es configurable en
`config.UNUSABLE_MODELS`.

### Cambiado (backend)
- `config.py`: nuevo `UNUSABLE_MODELS = {"qwen3.5:9b"}` (instalados en Ollama
  pero no utilizables) y `DEFAULT_MODEL = "llama3.1:8b"` (el defecto ya no puede
  estar bloqueado).
- `GET /api/models` (`routers/models.py`): excluye los modelos de
  `UNUSABLE_MODELS`. El selector de Ajustes → IA deja de ofrecerlos.
- `services/translate.py`: la traducción a demanda nunca elige un modelo no
  utilizable; si no hay ninguno preferido, usa el primer modelo utilizable
  instalado y solo en último caso el defecto.
- Tests: `tests/test_models.py` (el endpoint filtra y el default no está
  bloqueado) y `tests/test_translate.py` ampliado (no elige no utilizables,
  primero utilizable, sin modelos → default).

### Cambiado (frontend)
- `hooks/useChat.ts`: modelo por defecto `llama3.1:8b`; al restaurar
  preferencias guardadas solo aplica un modelo si sigue ofertándose; nuevo efecto
  de saneo: si el modelo activo o el favorito persistido quedan excluidos por el
  backend, cae al primer modelo disponible y olvida el favorito inalcanzable
  (así una preferencia vieja con `qwen3.5:9b` no vuelve a ralentizar el chat).
- `features/speaking/SpeakingRolePlay.tsx`: el role-play conversacional usa el
  modelo utilizable por defecto.

### Verificación
- `pytest` (subset 30 tests, incluidos `test_models.py` y `test_translate.py`)
  en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` en verde.

## [3.5.5] — 2026-09-04

**Fix: la traducción de apoyo no respondía y ampliación al resto de pantallas.**
La traducción de la v3.5.4 usaba el modelo por defecto del chat (`qwen3.5:9b`),
que en CPU tarda **10–64 s por frase** (se descarga y recarga entre llamadas) y
superaba el timeout del cliente: el botón se quedaba dando vueltas y acababa en
"Traducción no disponible". Ahora el servidor **elige automáticamente el modelo
rápido instalado** para traducir y el botón cubre también Speaking y
Pronunciación.

### Cambiado (backend)
- `services/translate.py`: selección de modelo por latencia. Orden de
  preferencia `llama3.1:8b` → `qwen2.5-coder:1.5b` (con caché de la lista de
  modelos instalados de 5 min); si ninguno está instalado, se cae al modelo por
  defecto. Medido en este equipo: llama3.1 traduce en **~0,3–5 s** frente a
  10–64 s del modelo por defecto. La petición puede forzar un modelo concreto
  (`model`), ahora opcional en `schemas/translate.py`.
- Tests ampliados en `tests/test_translate.py` (13): preferencia de modelo,
  fallback, Ollama caído y endpoint herméticos (sin consultar a Ollama real).

### Cambiado (frontend)
- `api/translate.ts`: timeout de 45 → **60 s** (la primera frase de una sesión
  puede cargar el modelo ligero en CPU; después es instantánea gracias a la
  caché por frase del cliente y del servidor).
- El botón de traducción ya no está solo en listening: ahora también en
  **Speaking Assessment** (junto al prompt de la parte) y en
  **Pronunciación** (junto a la frase elegida y a la frase esperada del
  resultado). Cada uno se reinicia en inglés al cambiar de frase/intento.

### Verificación
- `pytest` (subset 41 tests, incluidos 13 de `test_translate.py`) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (318 tests) en verde.
- Prueba real end-to-end contra Ollama: traducción automática con `llama3.1:8b`
  en 0,6 s y 0,3 s para dos frases.

## [3.5.4] — 2026-09-04

**Traducción de apoyo EN→ES en listening.** Un botón nuevo junto al altavoz de
los textos de práctica traduce al español la frase que el alumno no entiende y,
al pulsarlo de nuevo, vuelve al inglés. Es una *ayuda a demanda*: nunca aparece
automáticamente, se reinicia en inglés en cada pregunta y **no cuenta como
intento ni afecta a evidencia, puertas o métricas** (coherente con la
Constitución: la comprensión en inglés sigue siendo la vía principal).

### Añadido (backend)
- `POST /api/translate` (`{text, model?}`) → `{translation}`: traduce con el
  modelo local (Ollama) y mantiene una caché en memoria por frase
  (`services/translate.py`): la primera vez paga la latencia del modelo y las
  siguientes son instantáneas. 422 si el texto está vacío; 502 con mensaje
  legible si el modelo local no está disponible. No registra ninguna actividad.
- Tests en `tests/test_translate.py` (servicio con caché + endpoint).

### Añadido (frontend)
- `api/translate.ts`: cliente con caché por frase y timeout de 45 s (el modelo
  local en CPU tarda en la primera traducción).
- `components/PhraseTranslate.tsx`: hook `usePhraseTranslation(text, resetKey)`
  (estado por frase, se reinicia al cambiar de pregunta) y botón circular "ES"
  junto al altavoz: activo (relleno) mientras muestra español, spinner durante
  la llamada y aviso transitorio si el modelo local no responde.
- **`ListeningPractice`**: botón de traducción en (1) el enunciado de la
  pregunta, (2) el texto oído del resultado MCQ y (3) la referencia de
  dictado/shadowing. Las opciones de respuesta **no** se traducen: hacerlo
  trivializaría el MCQ (emparejar traducciones en vez de escuchar).
- **`ListeningLevelPanel`**: botón en cada frase del historial/repaso por nivel.
- Claves i18n `translate.*` en `utils/i18n.ts`.

### Verificación
- `pytest tests/test_translate.py tests/test_voices.py tests/test_health.py
  tests/test_cors.py` en `backend/` (35 tests) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (318 tests, incl.
  `api/translate.test.ts` para la caché por frase) en verde.

## [3.5.3] — 2026-09-04

**Fix: el botón "Continuar" de listening ya no desaparece.** En iPad (por WiFi
hacia el backend del PC, sobre todo con otra sesión abierta en el PC) una
petición que no terminaba dejaba la pantalla sin salida tras responder: el CTA
dependía de una respuesta de red que podía quedarse colgada y solo se arreglaba
refrescando. Ahora el bucle de práctica nunca se queda sin salida.

### Cambiado (frontend)
- **Timeouts de red en el bucle de listening** (`api/client.ts::withTimeout`,
  aplicado en `api/listening.ts` a pregunta, respuesta, dictado, shadowing,
  stats y diagnóstico): si una llamada no responde en 10–20 s, falla con un
  error legible en vez de esperar para siempre.
- **`ListeningPractice`**: al pulsar una opción MCQ se muestra "Evaluando…"
  (estado `submitting`, opciones deshabilitadas para evitar dobles envíos); si el
  envío falla o expira, la alerta de error ofrece **"Saltar a la siguiente
  pregunta"** para avanzar sin refrescar.
- **`NextStep`**: mientras el Adaptive Engine calcula la recomendación se muestra
  un placeholder visible (antes devolvía `null`, parecía un fallo) y, si el
  endpoint no responde en 8 s, aparece igualmente el CTA de salida (fallback).
  Con esto el resultado siempre tiene un botón "Continuar"/"Siguiente".

### Verificación
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (312 tests, incl.
  `client.test.ts` para `withTimeout`) en verde. Sin cambios en backend.

## [3.5.2] — 2026-09-04

**Descarga de voces desde la propia UI.** La pestaña "Voces" de Ajustes ahora
ofrece un catálogo curado de voces Piper de inglés (calidad `medium`, ~63 MB)
con botón "Descargar": la voz se baja del repositorio oficial a
`backend/models/piper/` y aparece al momento en la lista de instaladas. También
se instaló el set inicial de acentos (británico Alan, escocés Cori, norteño
Alba y americano Amy) además del default.

### Añadido (backend)
- `services/voice_downloads.py`: catálogo curado de voces Piper de inglés
  (id/etiqueta/ruta en HF), `available_to_download(installed)` y
  `download_voice(voice_id)` con descarga atómica (`.part` → `rename`, nunca se
  sirve un modelo a medio bajar) y bloqueo por voz.
- `POST /api/voices/download` (`{voice_id}`): descarga en threadpool; 400 para
  ids fuera del catálogo, 502 con mensaje legible si falla la red/escritura.
- `GET /api/voices` ahora expone también `downloadable` (catálogo no instalado,
  con `size_mb`).

### Añadido (frontend)
- `VoicesPanel` con sección "Añadir una voz": cada voz del catálogo con su
  tamaño y botón Descargar (estado de descarga en curso y error legible); al
  terminar refresca el catálogo. `api/voices.ts::downloadVoice` y tipo
  `DownloadableVoice`.

### Verificación
- `pytest` en `backend/` (tests de catálogo/descarga añadidos en
  `tests/test_voices.py`) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (309 tests) en verde.

## [3.5.1] — 2026-09-04

**Voces TTS configurables por perfil.** Nuevo selector "Voces" en Ajustes
(Configuración → Voces) que ofrece las voces Piper instaladas en
`backend/models/piper/`, guarda la preferencia por usuario (`tts_voice`) y la
aplica al TTS en vivo y a la síntesis de los ítems de listening sin audio
humano. Además, la etiqueta del "modelo vocal" del ejercicio de listening deja de
mostrar el acento *declarado* del corpus ("… : AUSTRALIAN") en los ítems
sintetizados y muestra la voz real del perfil.

### Añadido (backend)
- `services/tts.py` con soporte multi-voz: `list_voices()` (scan de
  `models/piper/*.onnx.json` + `.onnx`, default primero), `resolve_voice(prefs)`
  (función pura: preferencia del usuario si está instalada; si no, default o
  primera voz disponible), `synthesize(..., voice=None)` e `is_ready(voice=None)`
  con instancias `PiperVoice` cacheadas por id (thread-safe). Catálogo amigable
  `VOICE_LABELS` para las voces oficiales de inglés (fallback: nombre derivado
  del id).
- `GET /api/voices?user_id=` (`routers/voices.py` + `schemas/voices.py`) que
  devuelve `{voices, default, selected}` resolviendo la preferencia del perfil
  contra lo instalado (`user_id` opcional → sin perfil, `selected` es el
  default).

### Cambiado (backend)
- La síntesis de listening es por voz y por usuario: `get_audio(user_id, …)`
  resuelve la voz preferida y cachea en
  `DATA_DIR/listening/{bank}/{voice}/{id}-{digest}.wav` (cada voz en su propia
  carpeta: cambiar de voz no invalida la caché anterior; la nueva se regenera
  bajo demanda en la primera reproducción y queda cacheada).
- `/api/tts` acepta `user_id` opcional (voz del perfil; sin perfil, la default).

### Añadido (frontend)
- Pestaña **Voces** en Ajustes (`VoicesPanel`): lista de voces instaladas con
  etiqueta amigable + id, insignia "por defecto", estado de guardado, y texto de
  ayuda para instalar más voces (colocar `<voz>.onnx` + `<voz>.onnx.json` en
  `backend/models/piper/`) y aviso de regeneración del audio de listening.
- `api/voices.ts` (`getVoices`) y tipos `VoiceInfo`/`VoicesResponse`.

### Cambiado (frontend)
- `speak(text, userId?)` pasa `user_id` a `/api/tts` para usar la voz del perfil.
- `ListeningPractice`: la tarjeta de audio de ítems sintéticos muestra la **voz
  real** del perfil (Ajustes → Voces) en vez del acento declarado del corpus; los
  ítems con audio humano conservan su acento declarado. La voz se refresca al
  abrir la tarjeta de audio (así refleja cambios hechos en Ajustes sin recargar).

### Verificación
- `pytest` en `backend/` (1108 tests, incl. `tests/test_voices.py`) en verde.
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (309 tests) en verde.

## [3.5.0] — 2026-09-03

**Tercera iteración de la Constitución pedagógica (P2, en la UI).** Cierra los
P2 8–10 del roadmap (§9): pantallas honestas de entrenamiento (la práctica de
listening se lee por estado de ruta, `functional` ≠ `demonstrated`), todo badge
de nivel estimado lleva el calificador "estimado · no certificado", y se elimina
el código muerto `modeCefrLevel`/`modeCefrBand`.

### Cambiado (frontend)
- **Pantallas honestas de entrenamiento (H7, P2-8)**: la UI tipa el estado
  pedagógico por ruta que ya expone el backend (`ListeningLevelProgress.state`:
  `not_started`/`developing`/`functional`/`demonstrated` + `retention`). La ruta
  se lee sin engaño en `ListeningPractice`, `ListeningLevelPanel` y
  `ListeningRecorridoPanel`:
  - `functional` (puerta de ruta superada) se muestra como *hito de práctica*:
    "A1 Listening — not yet demonstrated", con el requisito de demostración
    (retención retardada estable: ≥90 % de la precisión inmediata en
    re-exposiciones tras ≥7 días) y el estado de retención actual.
  - `demonstrated` (puerta + retención estable ≥7 días) muestra la pantalla
    "A1 Listening — demonstrated" con el desglose (gate y retención).
  - Nueva sección "Competencia por ruta" en el Recorrido Listening con los 4
    estados por nivel CEFR y la nota de que "Demostrado" es el único estado que
    certifica.
- **Etiquetado del estimado (H7, P2-9)**: nuevo `EstimatedLevelBadge`
  (`LevelBadge` + calificador localizado "estimado · no certificado",
  `profile.estimatedQualifier`) en los dos sitios que muestran el nivel estimado
  global (Home y cabecera de Progreso) y en ResumenTab; el perfil
  (`LearningProfile`) muestra la distribución por destreza con la nota de que las
  bandas son estimaciones alineadas con el CEFR, no certificaciones
  (`profile.bandNote`).
- **Código muerto eliminado (H7, P2-10)**: retirados `frontend/src/utils/modes.ts`
  y `modes.test.ts` (`modeCefrLevel`/`modeCefrBand` no tenían uso en componentes;
  los modos de chat viven en `TUTOR_MODES` de `hooks/useChat.ts`).

### Verificación
- `npx tsc --noEmit` y `npx vitest run` en `frontend/` (309 tests) en verde.

## [3.4.0] — 2026-09-03

**Segunda iteración de código de la Constitución pedagógica (P1).** Completa los
P1 5–7 del roadmap (§9): la matriz CEFR deja de tener huecos (C1/C2 y las 8
destrezas), la certificación de nivel incorpora la retención retardada como
requisito (completado ≠ certificado) y el Personal Dictionary evoluciona a
Lexical Units con el Vocabulary Coverage Indicator receptivo/productivo.

### Cambiado (backend)
- **Matriz CEFR completa (H4, P1-5)**: `backend/curriculum/cefr_matrix.json` 2.0.0
  cubre A1–C2 × las 8 destrezas de la Constitución §7. Las 4 macro-destrezas
  conservan su calibración A1–B2 y se extrapolan a C1/C2; vocabulary/grammar/
  interaction/mediation declaran en la matriz el mismo suelo que su fallback
  plano histórico (sin inventar escalados no calibrados) y `pronunciation` queda
  por diseño como componente de Speaking. `services/cefr_matrix.py` documenta el
  nuevo alcance y `services/adaptive.readiness` usa la matriz como fuente única
  de requisitos por destreza (retrocompatible con perfiles legacy).
- **Certificación con retención (H5, P1-6)**: nueva semántica *completado ≠
  certificado*. Aprobar el examen sigue completando el nivel y desbloqueando el
  siguiente, pero la certificación plena exige evidencia `delayed` por destreza
  del examen (solo se escribe tras el retention reassessment ≥ 7 días con ratio
  estable). Nuevo `certification_gate` en `services/assessment_v2.py`, expuesto
  como `certification` en el resultado del examen y en el listado de completados
  (`/api/academy/level-completions`). En la escalera, `readiness.level_certified`
  exige el peldaño `level` + el retention reassessment: la retención entra como
  requisito del nivel, no como evaluación aparte.
- **Lexical Units + cobertura (P1-7)**: `services/lexicon.py` amplía `kind` a la
  taxonomía `LEXICAL_KINDS` (§3.2) y tipa las semillas curriculares con
  `classify_kind` (solo patrones inequívocos; lo ambiguo queda `structure`). El
  repo refresca kinds heredados al resembrar. `/api/vocabulary/lexicon` expone el
  **Vocabulary Coverage Indicator** receptivo/productivo por nivel
  (`coverage`, §3.1, bandas de `LEXICAL_COVERAGE_TARGETS`): indicador interno,
  no puerta.

### Cambiado (frontend)
- `PersonalDictionary` etiqueta toda la taxonomía de Lexical Unit con fallback
  genérico (nunca "word" por defecto); i18n en `utils/i18n.ts` y tipos en
  `src/types/api.ts` (`Certification`, `level_certified`, `LexiconCoverage`).

### Tests
- Nuevos: `certification_gate` y `level_certified` (`test_assessment_v2.py`),
  clasificador `classify_kind` y `coverage_indicator` (`test_lexicon.py`),
  "aprobado pero certificación pendiente" y "certificado con evidencia delayed"
  (`test_academy.py`).
- Actualizados: `test_lexicon.py` a la taxonomía ampliada; el resto de la suite
  sin cambios de expectativa.

### Documentación
- `docs/CONSTITUCION-PEDAGOGICA.md` (§8 mapeo y §9 roadmap) y
  `docs/audit/H-NIVELACION-PEDAGOGICA.md`: estado de los hallazgos tras la
  ejecución de los P1 5–7 (H1–H5 cerrados; H6–H7 parciales, pendientes de P2).

## [3.3.0] — 2026-09-03

**Primera iteración de código de la Constitución pedagógica (P0).** Separa el nivel
estimado del demostrado y elimina la lectura "palabras → nivel CEFR" que la auditoría
(`docs/audit/H-NIVELACION-PEDAGOGICA.md`, H1) marcó como pedagógicamente inválida. Introduce
los 4 estados por competencia (Constitución §2.1) en el perfil y convierte la práctica de
listening en evidencia del Student Model con retención retardada (H3/H5).

### Cambiado (backend)
- **`services/cefr.py` sin interpretación palabras→nivel (H1)**: retirado el evaluador legacy
  (`VOCABULARY_BAND_EDGES`, `vocabulary_band`, `evaluate_cefr`, `estimate_cefr`) y sus tests.
  Queda como módulo de constantes compartidas, descriptores, `heuristic_band` (score de
  destreza del Student Model) y recomendaciones; el volumen léxico es un indicador de cobertura
  (`VOCAB_EXPANSION_HINT_WORDS`), nunca una banda CEFR.
- **Registro por competencia Estimado/Demostrado (H2/H7)**: nuevo `services/competence.py` con
  los 4 estados (`not_started`/`developing`/`functional`/`demonstrated`), gate y retención;
  `/api/profile` lo expone como `competence_states`. Una destreza sin evidencia se muestra "—",
  nunca "A1" por defecto.
- **Fuente única de mastery (H6)**: retirado el endpoint `/api/academy/mastery` y su cadena
  domain/schema/repo; la fuente expuesta es `student-model.mastery`.
- **Listening al Student Model (H3/H5)**: nuevo `route_competence` en `services/listening.py`
  que lee `listening_attempts` como estado por ruta (los 4 estados): `route_gate` superado →
  FUNCTIONAL, y retención retardada estable (re-exposiciones ≥ 7 días con ratio ≥ 0.9) →
  DEMONSTRATED. El Student Model expone las rutas de la destreza listening y
  `/api/listening/stats` su estado y retención por ruta.

### Tests
- Nuevos: `backend/tests/test_competence.py` (estados por competencia y combinación
  evidencia formal + ruta de práctica).
- Eliminados: `backend/tests/test_cefr_evaluation.py` (fijaba el evaluador legacy retirado).
- Actualizados: `test_profile.py`, `test_academy.py`, `test_listening.py`, `test_policy.py`.

### Documentación
- `docs/CONSTITUCION-PEDAGOGICA.md` (§8 mapeo y §9 roadmap) y
  `docs/audit/H-NIVELACION-PEDAGOGICA.md`: estado de los hallazgos tras la ejecución de los P0
  (H1–H3 cerrados; H5–H7 parciales; H4 abierto) con la foto V3.2.1 conservada como referencia.

## [3.2.1] — 2026-09-03

**Auditoría pedagógica del modelo de nivelación (solo documentación).** Sin cambios de código.
Corrige el concepto antes de seguir con la UI: se audita cómo decide la app el nivel de un alumno
(`docs/audit/H-NIVELACION-PEDAGOGICA.md`) y se publica la especificación normativa
**`docs/CONSTITUCION-PEDAGOGICA.md`** que separa *Practice Level / Mastery / Estimated CEFR /
Demonstrated CEFR* y prohíbe leer "cantidad de palabras → nivel CEFR".

### Añadido (documentación)
- **Dossier `docs/audit/H-NIVELACION-PEDAGOGICA.md`** (desk, plantilla TEMPLATE): inventario de las
  dos fuentes de nivel (heurístico legacy `services/cefr.py` vs Student Model), hallazgos H1–H7 y
  veredicto: el modelo es honesto en la superficie pero no responde "qué ha demostrado el alumno".
- **`docs/CONSTITUCION-PEDAGOGICA.md`**: principios, 4 conceptos + 4 estados por competencia
  (NOT STARTED → DEVELOPING → FUNCTIONAL → DEMONSTRATED), cobertura léxica receptiva/productiva
  como indicador (no puerta), taxonomía de **Lexical Units**, progresión de listening por fases y
  **Mastery Gate** general (coverage + accuracy + subskills + retención ≥ 7 días + checkpoint) con
  mapeo de los bloques que ya existen (`route_gate`, evidence kinds, `mastery_evidence_gate`,
  `cefr_matrix.json`).
- **Roadmap de implementación derivado** (P0/P1/P2, sección 9 de la constitución): eliminar la
  interpretación palabras→nivel, estados Estimado/Demostrado por competencia, listening conectado
  al Student Model, matriz CEFR a C1/C2 y 8 destrezas, retención en la certificación, Lexical
  Units, y UI "Entrenamiento A1" vs "A1 — demonstrated".

## [3.2.0] — 2026-09-03

**Calibración pedagógica de niveles.** Nadie "alcanza A1" con 30 audios o 30
palabras: se recalibra el nivel estimado global, los donuts de Listening pasan a
ser rutas de práctica con puerta de evidencia y el corpus A1/A2 se expande a
cientos de ítems por nivel con un pipeline reproducible (ver `PLAN.md`).

### Cambiado
- **Nivel estimado global honesto (Fase 1)**: tramo `Pre-A1` (sin evidencia suficiente
  ya no es "A1") y recalibración logarítmica de los umbrales de vocabulario
  (`services/cefr.py` 2.1.0: A1 ≈ 150–399 palabras). Soportado en frontend
  (`cefrLabel`/`cefrTone`/badges) y en el tutor (`policy`, escalera de la Academy).
- **Listening como rutas de práctica (Fase 2)**: la UI relee los donuts como
  "Ruta A1…" con nota de qué significa un nivel CEFR real; `level_status` informa
  `{mastered, total, gate}` y la **puerta de ruta** exige cobertura ≥ 80 %,
  precisión ≥ 70 %, variedad de temas/sub-destrezas y un checkpoint de aciertos a
  la primera sin replays (`services/listening.py`, `ROUTE_*`).

### Añadido
- **Pipeline de expansión del corpus (Fase 3)**: `scripts/generate_listening_corpus.py`
  reproducible, idempotente y validado (frames autorados en
  `scripts/_corpus_frames_a1a2.py`). Tranche A1/A2 aplicado: corpus de **140 → 490
  ítems** (A1 200, A2 200; B1→C2 pendientes de siguiente tranche), respetando las
  bandas auditadas y `validate_listening_bank`.
- **Cierre del sesgo posicional (auditoría B, mc-bias)**: rotación determinista de
  opciones por id (`crc32 % n`); la posición de la respuesta queda ~uniforme
  (123/122/122/123 en 490) en vez de 90,7 % en la opción 0.
- **Objetivos de contenido** `LISTENING_CORPUS_TARGETS` en `services/curriculum.py`
  (A1 200, A2 200, B1 180, B2 160, C1 120, C2 100) y bump `LISTENING_BANK_VERSION`
  a 7.0.0 (audio TTS cacheados por versión de banco).

## [3.1.0] — 2026-09-02

**UI V3.1 — Reorganización en 3 mundos.** Rediseño de la interfaz y la navegación
(ver `docs/UI_V3.1.md`). Sin cambios en el stack pedagógico (sigue congelado en 3.0.0).

### Añadido / Cambiado
- Navegación raíz reducida a 3 mundos (INICIO · FORMACIÓN · APRENDER) con URLs reales mediante hash-router propio, deep links y botón atrás.
- INICIO: dashboard de acción con objetivo de hoy, recomendación, repaso FSRS y acceso a MI PROGRESO.
- FORMACIÓN: escalera CEFR A1–C2, listado de unidades con gating, hero "Continuar curso" y bloque de evaluaciones.
- APRENDER: hub de 6 tarjetas (Listening, Speaking, Pronunciación, Conversar, Vocabulario, Gramática) con sub-rutas propias y pantalla de Speaking libre.
- MI PROGRESO: pantalla consolidada por pestañas (Resumen · Curso · Habilidades · Trayectoria · Recorridos); el antiguo panel Analysis queda como contexto ligero.
- Workspace único con barra de contexto lección vs. práctica libre.
- AYUDA real en la ruta de ayuda (enlaza a la documentación) y "Conectar dispositivo" movido a Ajustes → Sistema.
- Limpieza de claves i18n huérfanas y navegación EN/ES coherente.

## [3.0.0] — 2026-09-02

**Beta V3.0 — feature freeze pedagógico.** Cierra el ciclo V2.7–V2.12 y congela
funcionalidad nueva. La fase abierta es contenido + calibración + UX + pruebas
reales (ver `docs/BETA_V3.md`).

### Añadido (stack pedagógico V2.7–V2.12, consolidado en 3.0.0)
- **Curriculum Depth (V2.7)**: Unit Architecture + profundidad A1–C2 (depth media ≥ 80,
  loop 100%).
- **Listening Curriculum (V2.8)**: foco CEFR por nivel + alineación 100%.
- **Speaking Mission (V2.9)**: Mission → Attempt → Drill → Retry → Improvement.
- **Assessment 2.0 (V2.10)**: formative → unit → progress → level → retention + mastery gate.
- **FSRS-lite (V2.11)**: cola due auditable (What/Why/When/How strong/Last/Next).
- **Evidence Graph (V2.12)**: can-do → limiting factor → `because[]` en next-best.
- **Gate Beta V3**: `scripts/check_beta_v3.py` (módulos, rutas, docs, umbrales de calidad).

### Congelado
- No se abren features de producto nuevas hasta completar la checklist de
  `docs/BETA_V3.md` (§4 contenido/calibración/UX/dispositivos).

### Verificado
- Backend pytest + ruff; frontend `tsc`; Curriculum Quality Overall **95,7**;
  loop **100%**; listening alignment **100%**.
- `python scripts/check_beta_v3.py` + `check_release_consistency.py` OK (3.0.0).

## [2.5.0] — 2026-09-01

**Release de consolidación para auditoría externa.** Eleva a versión estable el trabajo
acumulado tras `2.4.0`: finalización del currículo (V2.5), capa de medición de calidad del
currículo (V2.6) y auditoría visual de UI (2.1).

### Añadido
- **Currículo A1→C2 completado (V2.5)**: listening C1/C2 (corpus 100 → 140 ítems), speaking C2
  (26 escenarios), subskills de interacción en A1/A2/B2/C1/C2 y wiring curso↔bancos
  (`Objective.listening_items`/`scenario_ids`). Cobertura total 42/49 celdas (85,7%).
- **Curriculum Quality Dashboard (V2.6)**: métricas de grano fino `unit_coverage`,
  `depth_score`, `unit_learning_loop`/`loop_coverage` y `curriculum_quality_report` con delta
  antes/después.
- **Unit Learning Loop etiquetado (V2.6-C5)**: las 31 unidades etiquetan las fases de cierre
  (`retrieve`/`transfer`/`review`/`assess`); loop por unidad 50,6% → 84,7%.
- **UI 2.1**: banner de lección activa estilizado, "Modelo IA" i18n, estados vacíos con icono.

### Corregido
- **Navegación responsive**: la barra inferior (móvil) y la del header (tablet) desbordaban con
  7 pestañas y tapaban otros controles; ahora desplazan horizontalmente sin desbordar.
- **Sistema de diseño unificado**: eliminado CSS duplicado y muerto legacy y unificados radios,
  espaciado y ancho de lectura entre `index.css` y `legacy.css` (una sola fuente de verdad).

### Verificado
- Backend `pytest` + `ruff` limpios (fases V2.5/V2.6 ya verificadas; 1005 passed).
- Frontend `vitest` (245 tests) y `tsc && vite build` OK.
- Visual (Playwright sobre Chrome del sistema): 14 passed / 10 skipped / 0 failed en
  desktop/tablet/móvil.
- `python scripts/check_release_consistency.py` OK (2.5.0).

## [2.4.0] — 2026-08-31

**Auditoría de cobertura curricular**: responde con datos a "¿el alumno puede recorrer
completo A1→C2?". Recorre el curso completo (Pre-A1 → C2) por las 7 secciones canónicas
(vocabulary/grammar/listening/speaking/interaction/review/assessment), cruza el contenido del
curso con los bancos de destrezas (listening corpus + speaking scenarios) y genera
`curriculum_coverage_report.json`. No añade contenido ni funcionalidad de alumno; es la
instrumentación que permitirá localizar y completar los huecos reales.

### Añadido
- **Servicio puro `services/curriculum_coverage.py`**: `coverage_sections` (conteo por sección a
  nivel de curso), `bank_intersection` (cruce del banco de listening por `level` y de los
  escenarios de speaking por `cefr_target` contra cada nivel), tri-estado
  `complete`/`partial`/`empty` por sección, `level_coverage` y `curriculum_coverage_report`.
- **Métrica "TOTAL CURRICULUM COVERAGE"** (`coverage_metric`): ratio de celdas pobladas sobre la
  matriz completa 7 niveles × 7 secciones (49 celdas), con desglose `by_level`/`by_section`.
  Distinta y complementaria de "TOTAL VALIDATED LEARNING ITEMS" (contenido validado vs. cobertura).
- **Integración en `content_stats()`** (`services/content_validation.py`): `total_curriculum_coverage`
  convive junto a `total_validated_learning_items` como fuente única (anti-drift).
- **CLI `scripts/curriculum_coverage.py`**: emite el JSON completo + resumen legible por nivel y
  sale con código 1 (`--strict`) si hay algún hueco `empty` en una sección con curso (guard de CI).
- **Mapa de cobertura en `docs/CURRICULUM_COVERAGE.md`**: tabla Pre-A1→C2 × 7 secciones con estado
  y la lista priorizada de huecos detectados.

### Verificado
- Backend `pytest` (971 passed) + `ruff` limpio; tests de invariantes `test_curriculum_coverage.py`
  (7 niveles × 7 secciones, Pre-A1 como banda sin curso, cruce con bancos, determinismo y
  coexistencia de las dos métricas).
- `python -m scripts.curriculum_coverage` OK (37/49 celdas, 75.5% de cobertura).

### V2.5-C1 — listening C1/C2 (sin bump de versión, sigue 2.4.0)
- **Corpus de listening 100 → 140** (`curriculum/listening_corpus.json` v1.1.0): 20 ítems C1
  (`c101`–`c120`) y 20 C2 (`c121`–`c140`) con registro y temática avanzados (inferencia, intención
  del hablante, actitud, ironía, hablantes múltiples, connected speech, habla rápida).
- **`LEVEL_ORDER` ampliado** a A1..C2 (`services/listening.py`); `LISTENING_BANK_VERSION` 5.0.0 →
  6.0.0; `QUALITY_THRESHOLDS["min_items_per_level"]` añade C1/C2 (20 cada uno).
- **TOTAL VALIDATED LEARNING ITEMS 143 → 183** (163 listening: 140 corpus + 23 legacy TTS; 20 speaking).

#### Verificado
- `python -m scripts.content_validation` OK (183 ítems validados; 14/14 checks PASS).
- `python -m scripts.curriculum_coverage` OK (`bank_count` listening C1/C2 > 0).
- Backend `pytest` (972 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.5-C2 — speaking C2 (sin bump de versión, sigue 2.4.0)
- **Escenarios de speaking 20 → 26** (`curriculum/speaking_scenarios.json` v1.0.0 → v2.0.0): 6
  escenarios C2 (`persuasion`, `conflict_mediation`, `academic_defence`, `abstract_conversation`,
  `stakes_negotiation`, `diplomatic_talk`) con objetivo comunicativo de nivel C2 (persuasión sutil,
  mediación de conflicto, defensa con evidencia, temas abstractos, negociación delicada y tacto
  diplomático).
- **`SPEAKING_SCENARIOS_VERSION` 2.0.0 → 3.0.0** (`services/curriculum.py`), alineando la discrepancia
  JSON↔constante (el JSON quedó en 1.0.0 y la constante en 2.0.0; sube uno cada uno).
- **TOTAL VALIDATED LEARNING ITEMS 183 → 189** (163 listening: 140 corpus + 23 legacy TTS; 26 speaking).

#### Verificado
- `python -m scripts.curriculum_coverage` OK (`bank_count` speaking C2 > 0).
- Backend `pytest` (973 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.5-C3 — interaction A1/A2/B2/C1/C2 (sin bump de versión, sigue 2.4.0)
- **Subskills de interacción en 5 niveles** (`curriculum/a1.json`, `a2.json`, `b2.json`, `c1.json`,
  `c2.json`): 39 objetivos que declaran `speaking` con actividad `dialogue` añaden
  `subskills: ["interaction", "turn_taking"]`. La sección `interaction` deja de estar `empty` en
  A1/A2/B2/C1/C2 (queda poblada en 6/7 niveles; solo Pre-A1, banda sin curso, sigue vacía).
- **Cobertura TOTAL CURRICULUM COVERAGE 37/49 → 42/49 (75,5% → 85,7%)**.
- **Test invariante nuevo** (`test_curriculum_coverage.py`): `interaction` con `count > 0` en
  A1/A2/B2/C1/C2.

#### Verificado
- `python -m scripts.curriculum_coverage` OK (interaction 6/7; 42/49 celdas).
- Backend `pytest` (974 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.5-C4 — wiring curso↔bancos (sin bump de versión, sigue 2.4.0)
- **Modelo `Objective`** (`services/curriculum.py`): dos campos retrocompatibles
  `listening_items: list[str]` y `scenario_ids: list[str]` (default `[]`) que referencian por ID
  los ítems del banco de listening y los escenarios de speaking.
- **Conteo** (`services/course.py::unit_sections`): `listening`/`speaking` suman
  `len(listening_items)`/`len(scenario_ids)`, de modo que la sección refleja las referencias
  reales al banco y no solo el `skill` declarado.
- **Wiring de contenido** en los 6 niveles (`curriculum/a1.json`–`c2.json`): cada objetivo con
  `listening` referencia 4 ítems del banco de su nivel (`c001`–`c140` + legacy `l1`–`l23`); cada
  objetivo con `speaking` referencia 1 escenario de su `cefr_target` (26 escenarios). Total
  cableado: 18 objetivos de listening y 50 de speaking.
- **Validación** (`services/curriculum.py::validate_level`): comprueba que cada ID referenciado
  existe y que su `level`/`cefr_target` coincide con el nivel del curso (imports diferidos
  anti-ciclo).

#### Verificado
- `python -m scripts.curriculum_coverage --strict` OK (exit 0; listening/speaking cableados por
  unidad, `count` crecido y sin huecos `empty`).
- Backend `pytest` (981 passed) + `ruff` limpio; `check_release_consistency` OK (2.4.0).

### V2.6-C1 — capa de medición: Unit Coverage + CEFR Depth + Unit Learning Loop + Dashboard (sin bump, sigue 2.4.0)
- **Hallazgo conceptual**: "cobertura" ≠ "profundidad". `42/49 celdas` no es "curso al 85,7%": una
  celda cuenta como poblada si *alguna* unidad tiene contenido en esa sección. Se añaden métricas de
  grano fino en `services/curriculum_coverage.py`:
  - `unit_coverage(level)` — **UNIT COVERAGE**: por unidad, las 7 secciones pobladas (`coverage_pct`,
    `missing`, `by_section`). Media A1..C2 = **61,7%**.
  - `depth_score(level)` — **CEFR DEPTH SCORE** (0..100): 4 componentes ponderados y auditables
    (`objective_density` 0.20 · `objective_volume` 0.35 · `section_coverage` 0.35 ·
    `subskill_breadth` 0.10). Media **55,7**; A1 74,2 · A2 52,3 · B1 55,7 · B2 61,7 · C1 48,0 ·
    C2 42,5. Ajuste C1b: volumen pesa más que densidad (la densidad sola premiaba a B2 por ser denso
    con solo 9 objetivos).
  - `unit_learning_loop(level, unit)` + `loop_coverage(level)` — **UNIT LEARNING LOOP** (9 fases).
    Media **50,6%**; introduce/practice 100%, listen 45,2%, speak 90,3%, interact 83,9%,
    retrieve/transfer 0%, assess/review 19,4% (solo módulos "Final").
  - `unit_detail(level_id, unit_id)`: drill-down LEVEL → UNIT → LESSON → OBJECTIVE.
  - `curriculum_quality_report()` — **Curriculum Quality Dashboard**: 7 dimensiones + `overall` +
    `by_level` + bloque `learning_loop`. Overall **56,8**; review/assessment 23,5 · listening 47,8 ·
    depth 55,7 · coverage 85,7.
  - `quality_report_delta(before, after)`: delta antes/después por dimensión y nivel.
- **CLI** (`scripts/curriculum_coverage.py`): dashboard + loop legibles + `--quality` (JSON completo).
- **Dato corregido**: objetivos reales por nivel A1 23 → A2 11 → B1 10 → B2 9 → C1 7 → C2 5; la caída
  es más abrupta de lo que sugería la auditoría previa (A2 y B1/B2 también son finos, no solo C1/C2).

#### Verificado
- Backend `pytest` (999 passed) + `ruff` limpio; tests `test_curriculum_quality.py` (18 invariantes).
- `python -m scripts.curriculum_coverage` OK (dashboard + loop) y `--strict` exit 0.
- `python -m scripts.content_validation` OK; `check_release_consistency` OK (2.4.0).

### V2.6-C2 — marcador de fase del Unit Learning Loop (`Activity.phase` + validación) (sin bump, sigue 2.4.0)
- **Modelo** (`services/curriculum.py`): `LEARNING_PHASES` (9 fases canónicas del loop) como fuente de
  verdad y `Activity.phase: str = ""` (default vacío = `practice`, retrocompatible). `validate_level()`
  rechaza `phase` no canónico.
- **Medición** (`services/curriculum_coverage.py`): re-exporta `LEARNING_LOOP_PHASES` desde
  `LEARNING_PHASES` (anti-drift) y `unit_learning_loop()` lee `retrieve`/`transfer`/`review`/`assess`
  desde el `phase` de las actividades. El hueco deja de ser un 0 hardcodeado: ahora es contenido
  etiquetable (hoy sigue 0/19,4% porque ningún JSON usa aún el marcador).
- **Briefing de contenido** `agentes/curriculum/c5-loop-phases.md`: etiquetar fases de cierre por
  unidad (piloto A1 → escalar), subir el loop de 50,6% → ≥ 77%.

#### Verificado
- Backend `pytest` (1005 passed) + `ruff` limpio; `validate_level` vacío para los 6 niveles.
- `python -m scripts.curriculum_coverage --strict` exit 0; `check_release_consistency` OK (2.4.0).

### V2.6-C5 — etiquetado de fases del Unit Learning Loop en el contenido (sin bump, sigue 2.4.0)
- **Contenido** (`backend/curriculum/*.json`): las 25 unidades normales (no módulo "Final") etiquetan
  las 4 fases de cierre del loop con el marcador `phase`:
  - `retrieve` (recuperación espaciada desde memoria) y `transfer` (can-do aplicado a un contexto nuevo
    no ensayado): 25/31 unidades cada una (80,6%).
  - `review` (micro-repaso del can-do en 1 frase) y `assess` (auto-evaluación abierta de cierre):
    31/31 unidades (100%), ya no solo en los módulos "Final".
- **Loop por unidad**: media **50,6% → 84,7%** (objetivo ≥ 77%). introduce/practice 100%, listen 45,2%,
  speak 90,3%, interact 83,9%, retrieve/transfer 80,6%, assess/review 100%.
- **Invariantes de snapshot** (`tests/test_curriculum_quality.py`): los dos tests frágiles que codificaban
  el hueco se actualizan: `test_loop_retrieve_and_transfer_are_still_ungapped` →
  `test_loop_retrieve_and_transfer_are_tagged` (covered_units > 0) y
  `test_loop_assess_and_review_only_in_final_module` → `test_loop_assess_and_review_cover_every_unit`
  (covered_units == total_units).

#### Verificado
- `python -m scripts.curriculum_coverage --strict` exit 0; `validate_level` vacío para los 6 niveles.
- Backend `pytest` (1005 passed) + `ruff` limpio.

## [2.3.0] — 2026-08-31

**Personal Dictionary + evidencia por ítem léxico**: se baja el modelo de evidencia de
"destreza" a "palabra/estructura". Cada entrada de `vocabulary` se convierte en un ítem léxico
de primer nivel sembrado desde el currículo, con estado y `recall` por ítem, expuesto en una
pantalla **Personal Dictionary**.

### Añadido
- **Ítem léxico con contexto curricular** (migración idempotente en `repositories/db.py`): columnas
  `cefr`/`level_id`/`objective_id`/`source`/`lemma`/`kind` en `vocabulary` (solo contexto; no tocan
  `appearances`/`exposures`).
- **Siembra desde el currículo** (`repositories/vocabulary.seed_curriculum_items` +
  `services/lexicon.items_from_objective`): `objective.vocabulary` + `objective.concepts`
  (estructuras como "I am") pueblan el diccionario al avanzar, cableado en
  `submit_objective_assessment` y `record_lesson_completed`.
- **Servicio puro `services/lexicon.py`**: `item_mastery`, `item_recall` (reutiliza la curva de
  olvido de `forgetting`), `item_status` (`mastered`/`known`/`learning`/`weak`), `next_review_days`
  (reutiliza el scheduler de `mastery`), `cefr_distribution`, `summary` y `recognized_not_produced`
  (señal de *speaking micro-drill*).
- **Endpoint `GET /api/vocabulary/lexicon`** → `LexiconOut { summary, items }` con estado, `recall`
  y `next_review_days` por ítem.
- **Pantalla Personal Dictionary** (`features/vocabulary/PersonalDictionary.tsx`): totales
  Known/Learning/Weak/Mastered, barra "Vocabulary by CEFR" (A1→C2), lista de ítems con `recall %` y
  "next review", y sección "Recognized but not produced". Ruta y entrada en la navegación + i18n ES/EN.

### Verificado
- Backend `pytest` (962 passed) + `ruff` limpio; tests de invariantes `test_lexicon.py` (seed sin
  incrementar producción, estado determinista, recall monótono, distribución CEFR, señal micro-drill).
- Frontend `tsc` + `vitest` (245 passed) + `build` en verde.

## [2.2.0] — 2026-08-31

**Academy / Course Engine (profundizar lo existente)**: el foco pasa de "tener contenido"
a "construir un curso completo y medible". Sin reescribir el Course Engine (V1.38),
Mastery 2.0 (V1.39) ni Adaptive 2.0 (V1.31): se les añade estructura y medición pedagógica.

### Añadido
- **Métrica única "TOTAL VALIDATED LEARNING ITEMS"** (`services/content_validation.py`:
  `content_stats()`): cifra canónica derivada de las dos fuentes (banco de listening +
  escenarios de speaking) = **143** (123 listening: 100 corpus + 23 legacy TTS; 20 speaking).
  `run_content_validation()` la reporta y README/CHANGELOG/UI derivan de ella (anti-drift,
  con test que falla si validador y métrica no coinciden).
- **Plantilla fija de unidad (7 secciones)** (`services/course.py`: `UNIT_SECTIONS` +
  `unit_sections`): cada unidad expone vocabulary/grammar/listening/speaking/interaction/
  review/assessment con conteo y huecos visibles (`needs_content`) que alimentan el Quality
  Gate en V2.3.
- **Learning Objectives de unidad** (`unit_objectives`): "By the end of this unit you will
  be able to…" agregando los `can_do` de los objetivos, renderizado en `CourseScreen`.
- **Contrato CEFR conectado al dominio** (`cefr-ladder`): cada dimensión "WHAT CAN I DO?"
  emite su estado real ✓/●/○ (`mastered`/`in_progress`/`not_started`) desde el Student Model
  (`adaptive.dimension_state`), sustituyendo el `Check` estático en `CourseScreen`.
- **Mastery Gates por unidad** (`services/course.py`: `unit_gates`): umbrales compuestos por
  sección (vocabulary/grammar ≥ 0.80, listening ≥ 0.75, speaking ≥ 0.70) + retención PASS +
  transferencia PASS. Una unidad solo se marca `mastered` con el gate compuesto; la UI
  muestra "qué falta para UNIT MASTERED" (`CourseUnit.sections/gates/gate_mastered`).
- **Tríada Progress / Mastery / Readiness** (`adaptive.student_dashboard` + endpoint
  `GET /api/academy/dashboard`): tres métricas explícitas y consistentes, reutilizadas por
  Home/Progress/Course (`TriadCard`).
- **Pantalla Learning Journey** (`features/journey/JourneyScreen.tsx`): escalera Pre-A1→C2
  con marcador "YOU", `units mastered`, `skills ready`, `retention %` y `next milestone`,
  enrutada desde la navegación principal.
- **Tests de regresión pedagógica** (`backend/tests/test_pedagogy.py`): invariantes de la
  métrica única, plantilla de 7 secciones, objetivos de unidad, Mastery Gates (sección
  bloqueante → no `mastered`), recomendación por sub-destreza débil (connected speech),
  contrato CEFR y tríada; `test_course.py` ampliado para secciones/objetivos/gates.

### Verificado
- `python -m scripts.content_validation` OK (143 ítems de aprendizaje validados; 12/12 checks PASS).
- Backend `pytest` (948 passed) + `ruff` limpio; `check_release_consistency` OK.
- Frontend `tsc` + `vitest` (240 passed) + `build` en verde.

## [2.1.0] — 2026-08-31

**Contenido y calidad pedagógica**: primera iteración centrada en volumen y diversidad
de contenido (recomendación inmediata de la auditoría externa), no en arquitectura.

### Añadido
- **Content Quality Gate** (`services/content_validation.py`): umbrales de calidad del banco
  de listening (mínimo de ítems por nivel CEFR, hablantes, acentos, contextos, connected
  speech, ruido, multihablante y habla rápida) con reporte `quality_pass`/`quality_warnings`.
  `scripts/content_validation.py` falla (exit 1) si no se cumplen los umbrales (guard de CI).
- **Corpus de listening 40 → 100** (`curriculum/listening_corpus.json`, c041–c100): 60 ítems
  TTS nuevos con perfil diversificado por nivel (A1 habla clara, A2 conversación natural,
  B1 connected speech/multihablante, B2 habla rápida/acentos/inferencia) y 15 destrezas.
  `LISTENING_BANK_VERSION` 4.0.0 → 5.0.0.
- **Escenarios de speaking 8 → 20** (`curriculum/speaking_scenarios.json`): banco, aeropuerto,
  vivienda, queja, negociación, presentación de equipo, small talk avanzado, soporte técnico,
  debate, narración, etc., cubriendo A1→C1. `SPEAKING_SCENARIOS_VERSION` 1.0.0 → 2.0.0.
- **Niveles de curso C1 y C2** (`curriculum/c1.json`, `curriculum/c2.json`): curso secuencial
  C1 (gramática avanzada, idioms, discurso académico) y C2 (retórica, registro, matiz cultural).
  `CURRICULUM_VERSION` 1.2.5 → 1.3.0.
- **Assessments finales por nivel**: módulos de repaso final añadidos a A2, B1 y B2 (A1 ya los
  tenía), cerrando cada nivel con una evaluación de cierre.

### Verificado
- `python -m scripts.content_validation` OK (integridad + umbrales de calidad; 123 ítems, 12/12 checks PASS).
- Backend `pytest` (936 passed) + `ruff` limpio; `check_release_consistency` OK.
- Frontend `tsc` + `vitest` (240 passed) + `build` + `playwright` (14 passed, 10 skipped) en verde.

## [2.0.0] — 2026-08-31

**Beta 1.0**: cierre del roadmap V1.36 → Beta. Los 5 gates de salida alcanzan 10/10
(Infra / Curriculum / Listening+Speaking / Adaptive+Mastery / UX+Reliability); ver
`docs/BETA_GATES.md`.

### Cambiado
- **Versión mayor** `1.41.0` → `2.0.0` para marcar el producto completo (feature-complete)
  y la entrada en Beta.

### Corregido
- **Seguridad (path traversal)** en `GET /api/system/backup/export`: `read_backup` ahora
  exige un `name` que sea basename `.zip` y lo resuelve confinado a `backups_dir()` (anti
  CWE-22). Hallazgo de la pre-auditoría interna.
- **Restore como reemplazo real** (`services/backup.py`): `restore_backup` ahora elimina los
  archivos que no están en el backup (en `data/` y `audio_library/`, conservando `backups/`
  y `_backups/`), alineando el comportamiento con el docstring "reemplaza el estado actual".

### Verificado
- Gates de salida 10/10 en `docs/BETA_GATES.md`.
- Backend `pytest` (929 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) +
  `build` OK; `check_release_consistency` OK; CI con `content-validation` y `playwright`.

## [1.41.0] — 2026-08-31

**Beta Hardening**: sin features nuevas, solo fiabilidad y seguridad para cerrar el producto.
Backup/restore/export local, seguridad LAN, a11y y performance.

### Añadido
- **Backup / restore / export local** (`services/backup.py` + `routers/system.py`): copias de
  seguridad ZIP deterministas del estado local (SQLite `tutor.db` — perfiles, progreso, vocabulario,
  evidencia, settings, mastery — + biblioteca de audio `manifest.json` + WAV). Endpoints admin:
  `GET /api/system/backup/status`, `POST /api/system/backup`, `GET /api/system/backups`,
  `GET /api/system/backup/export` y `POST /api/system/restore`.
- **Auto-backup diario** (keep 7): hilo `_auto_backup_daemon` en el lifespan de FastAPI que crea una
  copia si no existe ninguna del día UTC, y poda a `KEEP_BACKUPS = 7`.
- **Seguridad LAN** (`security.py::SecurityMiddleware`): middleware ASGI con (a) origin-check para
  métodos no seguros (protección tipo CSRF para la app accesible por LAN) y (b) rate limiting en
  memoria por IP cliente con límites más estrictos para endpoints sensibles.
- **Panel de backup en la UI** (`components/BackupPanel.tsx` + `api/system.ts`): en Ajustes →
  Sistema, permite crear copia, listar, descargar y restaurar desde un ZIP, reutilizando el PIN de
  administración.
- **A11y**: skip-link al contenido principal (`AppShell`) y sincronización de
  `document.documentElement.lang` con el idioma de la interfaz.

### Cambiado
- **Matriz de dispositivos** (`docs/DEVICE_MATRIX.md`): ampliada a PC/Android/iPhone/iPad con
  columnas explícitas HTTPS, mDNS, Mic, Audio, Listening, Speaking y Recuperación de permisos.
- **Performance**: `manualChunks` en `vite.config.ts` separa React, `motion` y `lucide-react` en
  chunks propios (el bundle principal baja de ~505 kB a ~393 kB, gzip de ~160 kB a ~124 kB).

### Verificado
- Backend `pytest` (926 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) + `build` OK.

## [1.40.0] — 2026-08-31

**Speaking 3.0**: escenarios comunicativos reales con objetivo comunicativo y métricas declaradas,
más honestidad del proxy de pronunciación en la UI.

### Añadido
- **Catálogo de escenarios comunicativos** (`backend/curriculum/speaking_scenarios.json` + nuevo
  `services/speaking_scenarios.py`): 8 escenarios (Restaurant, Doctor, Travel, Telephone,
  Work meeting, Small talk, Problem solving, Interview) versionados como contenido fuera del código.
  Cada escenario declara un `communicative_objective` (qué debe conseguir el alumno) y las métricas
  que observa (`task_completion`, `interaction`, `fluency`, `repair`, `turn_taking`), mapeadas a los
  criterios del rubric ya existentes (`services/speaking` + `services/interaction`).
- **Endpoint** `GET /api/academy/speaking/scenarios` (schemas `SpeakingScenarioOut`/
  `SpeakingScenariosOut`) que expone el catálogo estático.
- **UI de escenarios** (`frontend/features/speaking/SpeakingScenarios.tsx`): pestaña "Speaking
  scenarios" en el panel de análisis; cada tarjeta muestra título, nivel, categoría, objetivo
  comunicativo y las métricas; al practicar reutiliza `SpeakingRolePlay`, que registra la telemetría
  de turnos (`duration_ms`/`latency_ms`) para la señal objetiva de interacción.

### Cambiado
- **Honestidad del proxy de pronunciación** (`SpeakingDiagnostic.tsx`): el criterio `pronunciation`
  (marcado `proxy` desde V1.34) ahora muestra "Confidence: alta/media/baja · automated proxy" y una
  nota que distingue fonética real de la alineación speech/transcript (proxy), en lugar de un simple
  badge.

### Verificado
- Backend `pytest` (912 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) + `build` OK.

## [1.39.0] — 2026-08-31

**Mastery 2.0**: el dominio se abstrae como evidencia + preparación (readiness), no como una media
simple. `MasteryRecord` transversal para las 9 destrezas y CEFR readiness con banda cualitativa.

### Añadido
- **`MasteryRecord` transversal** (`services/mastery.py`): una sola abstracción de dominio para las 9
  destrezas (vocabulary/grammar/pronunciation/listening/speaking/reading/writing/interaction/
  mediation), de modo que el Adaptive Engine observa un conjunto homogéneo. Cada registro porta
  `score`, `confidence`, `evidence_count`, `retention`, `stability`, `review_due`, `review_in_days`,
  `transfer_count`, `novel_count` y la etapa del timeline
  acquire→practice→retrieve→transfer→novel→retention.
- **Curva de olvido conectada a todo el currículo** (`review_interval_days` + `mastery_stage`):
  cada destreza obtiene un "review in N days" determinista derivado de la estabilidad de
  `services.forgetting`, y `mastery_records()` devuelve siempre las 9 destrezas.
- **CEFR readiness sin media simple** (`services/adaptive.py::readiness_band`): combina mastery +
  evidencia + transfer + retención + confianza + gates mínimos y emite una banda cualitativa
  (`developing`/`approaching`/`ready`) en lugar de un "%" crudo. `adaptive.readiness` ahora incluye
  `band`.
- **Exposición en el Student Model** (`StudentModelOut.mastery` + `MasteryRecordOut`): el endpoint
  `/api/academy/student-model` devuelve la vista transversal y la banda de readiness; `/api/profile`
  hereda la banda por `ReadinessOut`.

### Cambiado
- UI de progreso (`ProgressScreen`, `HomeScreen`, `TodayPlan`, `LearningProfile`, `CourseScreen`):
  la preparación se muestra como "B1 developing" (banda) con el % como dato secundario; el detalle de
  destreza muestra "Repasar en N días" desde el `MasteryRecord`.

### Verificado
- Backend `pytest` (906 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) OK.

## [1.38.0] — 2026-08-31

**Course Engine**: el mapa CEFR se convierte en un curso secuencial (Course→Unit→Lesson→Practice→
Assessment→Review→Mastery) con gating de progreso por objetivo y una posición visible "¿dónde estoy?"
en pantalla.

### Añadido
- **Course Engine** (`services/course.py`): secuenciación explícita de módulos/unidades/lecciones a
  partir de `curriculum/a1.json` (y a2/b1/b2), con orden de lección y gate de progreso por objetivo
  (`gate_objective_ids`, `objective_gated_status` → `mastered`/`review`/`available`/`locked`).
- **Posición en el curso** (`unit_sequence` + `current_position` + `course_map`): calcula la unidad
  y lección actuales, el progreso `mastered/total` y el estado (`done`/`current`/`locked`) de cada
  unidad.
- **Endpoint** `GET /api/academy/course/{level_id}` → `CourseMapOut` (protegido por el bloqueo de
  inscripción), expone unidades, lecciones, posición actual y progreso.
- **Progreso visible en frontend** (`CourseScreen.tsx`): barra de unidades (✓/●/🔒) y lección actual
  "¿dónde estoy?" con el porcentaje de avance del nivel.

### Cambiado
- `domain/academy.py::_objective_state` consume el estado gated calculado por `course_svc` (fuente
  única de gating) en lugar de determinarlo internamente; el segundo objetivo de un nivel aparece
  `locked` hasta dominar el anterior.

### Verificado
- Backend `pytest` (900 tests, incl. `test_course.py`) + `ruff` limpio; frontend `tsc` + `vitest`
  (240 tests) OK.

## [1.37.0] — 2026-08-31

**Audio QA + Content Audit**: la subida de audio se convierte en un estudio de QA acústica y la
integridad del contenido se audita de extremo a extremo, con separación admin/estudiante por PIN.

### Añadido
- **QA acústica** (`services/audio_library.py`): análisis determinista de cada WAV (solo stdlib) —
  `peak`, `RMS`, `clipping %`, `DC offset` y `silence ratio` — con clasificación `PASS`/`WARNING`/
  `REJECT`. La subida devuelve un panel "AUDIO QUALITY" (formato, sample rate, canales, duración,
  clipping, silencio, peak dBFS) antes de aceptar la grabación.
- **Content integrity check** (`services/content_validation.py` + `scripts/content_validation.py`):
  recorre `question → audio_id → manifest → WAV → metadata → CEFR → difficulty → subskills` y emite
  el "CONTENT INTEGRITY CHECK" (ítems, grabados vs TTS, referencias rotas, ids duplicados,
  transcripciones ausentes, desfase CEFR y desfase de duración).
- **Content Audit Dashboard** (frontend): pestaña "Content audit" en Ajustes → Audio con el resumen
  de integridad y los issues por severidad.
- **Candado admin (PIN local)** (`dependencies.require_admin` + `ADMIN_PIN`): protege subida, borrado,
  previsualización y auditoría. Separación `student` (aprender) / `admin` (gestionar) sin OAuth/cloud.
- **Backup + auditoría de borrado**: `DELETE` copia el WAV y su entrada a `_backups` y registra la
  operación en `audit.log` (JSONL) antes de borrar, para recuperación.
- **Límites de subida**: MIME WAV estricto, `MAX_AUDIO_DURATION_SECONDS` y `MAX_AUDIO_BYTES`.

### Cambiado
- `POST /api/audio-library/upload` ahora devuelve el panel de QA y aplica límites de MIME/duración.
- Nuevos endpoints `GET /api/audio-library/status` y `GET /api/audio-library/audit` (admin).

### Verificado
- Backend `pytest` (889 tests) + `ruff` limpio; frontend `tsc` + `vitest` (240 tests) + `build` OK.
- CI ampliado con jobs `content-validation` y `playwright` (E2E visual).

## [1.36.0] — 2026-08-31

**Audio Corpus 1.0**: corpus de audio humano versionado en `curriculum/listening_corpus.json`
(40 ítems A1–B2 con diversidad real de hablantes, acentos, contextos, connected speech, ruido y
velocidad), pipeline de producción de grabación e importación masiva.

### Añadido
- **Corpus de audio humano** (`backend/curriculum/listening_corpus.json`): 40 ítems grabables
  (`c001`–`c040`) con la matriz multidimensional del auditor (nivel × hablante × contexto ×
  condiciones de escucha) y metadatos ampliados (`gender`, `age_band`, `region`, `accent`,
  `speaker_count`, `spontaneity`, `recording_environment`, `overlap`, `connected_speech`,
  `prosody`, `task_type`, `cefr`, `context`).
- **Loader del corpus** (`services/listening.py`): `QUESTION_BANK` ahora fusiona el banco heredado
  TTS (`l1`–`l23`) con el corpus; los ítems del corpus son `tts` hasta que el manifest respalda su
  `audio_id` (el manifest sigue siendo la fuente de verdad). `LISTENING_BANK_VERSION` → `4.0.0`.
- **Pack de grabación** (`backend/scripts/generate_recording_pack.py`): genera el CSV de guiones por
  hablante (transcripción, wpm objetivo, notas de connected speech, entorno, ruido) y un resumen de
  progreso frente al objetivo A1 30–40 / A2 40–50 / B1 60–80 / B2 60–80.
- **Importación masiva** (`backend/scripts/import_audio.py --batch`): incorpora los WAV grabados por
  convención `{cefr}/{speaker_id}/{audio_id}.wav`, mide su duración real y rellena el manifest.
- **Higiene de release** (`scripts/check_release_consistency.py`): comprueba que backend, frontend,
  README, CHANGELOG y PLAN declaran la misma versión; añadido a CI.

### Cambiado
- `PLAN.md` sincronizado a la versión de la app (eliminada la inconsistencia `1.34.0`).

### Verificado
- Backend `pytest` + `ruff` limpio; frontend `tsc` + `vitest` OK.

## [1.35.0] — 2026-08-31

**Gestión en-app de la biblioteca de audio humano**: subir, reemplazar y quitar las
grabaciones WAV de los ejercicios de listening desde la propia app (Ajustes → Audio),
sin tocar la terminal.

### Añadido
- **Switch runtime por manifest** (`services/audio_library.py`): `is_recorded` considera grabado un
  ítem también cuando su `audio_id` está presente en el manifest. Así, subir un WAV convierte el ítem
  de TTS a grabado (y borrarlo lo revierte) sin tocar el banco de preguntas.
- **Helpers de escritura/borrado**: `wav_probe_bytes` (lee el WAV en memoria), `write_entry` (upsert
  atómico + validación del manifest) y `remove_entry` (borra entrada + WAV).
- **Router `/api/audio-library`** (`routers/audio_library.py`): `GET /slots` (los 9 slots grabables
  con su estado), `POST /upload` (subir/reemplazar WAV con metadatos), `GET /{audio_id}/audio`
  (previsualizar) y `DELETE /{audio_id}` (quitar grabación).
- **Frontend**: pestaña **Audio** en Ajustes (`components/AudioLibrary.tsx`) con preview del WAV,
  edición de metadatos (transcripción, hablante, acento, CEFR, velocidad, ruido, género, región,
  contexto), subida y borrado. `domain/listening.py` expone `audio_type="recorded"` cuando el manifest
  respalda el ítem (la UI muestra "Real recording" y oculta la escalera de velocidad).

### Cambiado
- `postForm` en `api/client.ts` para subidas multipart.

### Verificado
- Backend **858 tests** + `ruff` limpio; frontend **237 tests** + `tsc` OK.

## [1.34.0] — 2026-08-28

**Speaking 2.0**: pronunciación marcada como proxy, desglose de Interaction Quality y
Conversation Endurance.

### Añadido
- **Pronunciation proxy** (`services/speaking.py`): `PROXY_CRITERIA` + `criterion_is_proxy()` marcan
  `pronunciation` como *proxy* porque deriva de similitud fonética de texto (no de análisis acústico
  real). El diagnóstico (`/api/academy/speaking/diagnostic`) emite `proxy: true` en ese criterio y la
  UI lo muestra con una insignia "proxy" para ser transparente con la limitación.
- **Interaction Quality** (`services/speaking.py`): `INTERACTION_QUALITY_DIMENSIONS`
  (initiation, response, follow_up, repair, turn_taking) con `interaction_quality_scores()`. Cada
  sub-dimensión se registra como evidencia propia (`interaction:<dim>`) y se agrega en
  `_interaction_quality_breakdown`, expuesta en el diagnóstico como `interaction_quality`.
- **Conversation Endurance** (`services/speaking.py` + `repositories/conversations.py`):
  `conversation_endurance()` mide cuánto puede sostener una conversación el alumno a partir de la
  telemetría de turnos hablados (hitos 30s/60s/90s/120s/180s). Nuevo repositorio
  `student_speaking_sessions()` y endpoint `GET /api/academy/speaking/endurance`.
- **LLM evidence**: `speaking_llm` solicita y parsea el nuevo campo `initiation` para alimentar la
  sub-dimensión de inicio de interacción.

### Cambiado
- **Frontend**: `SpeakingDiagnostic` renderiza la insignia "proxy", el desglose de Interaction
  Quality y los hitos de Conversation Endurance (con traducciones ES/EN).

## [1.33.0] — 2026-08-28

**Listening 2.0**: indicador de resiliencia auditiva y clasificación del corpus por
contexto comunicativo.

### Añadido
- **Listening Resilience** (`services/listening.py`): `resilience_dimensions()` clasifica cada ítem
  según la condición de escucha que su audio *realiza* (habla clara → natural → conectada → rápida →
  ruido → acentos) y `listening_resilience()` agrega la precisión por dimensión. El diagnóstico
  (`/api/listening/diagnostic`) ahora emite `resilience` con `main_weakness` ("Your main weakness is
  understanding connected speech") y `recommendation`, además de `dimensions`.
- **Honestidad de evidencia**: la resiliencia se calcula sobre el vector *realizado* (no el declarado),
  de modo que una voz TTS neutra no aporta evidencia a `noise`/`accents`; esas dimensiones se poblarán
  cuando exista el corpus real.
- **Contexto comunicativo** (`context`): nueva dimensión de clasificación del corpus en
  `ListeningAsset`/`ListeningQuestion` (`LISTENING_CONTEXTS`: conversation, announcement, message,
  instructions, news, interview, narrative, presentation) y en el manifest de audio humano
  (`AudioLibraryEntry.context`, con `by_context` en `library_summary`).

### Cambiado
- **`AUDIO_LIBRARY_VERSION` → `1.2.0`**: el manifest de la biblioteca de audio humano incorpora el
  campo `context` (comunicativo). El manifest vacío del repositorio se actualiza en consecuencia.

## [1.32.0] — 2026-08-28

**Curriculum 2.0**: escalera CEFR completa (Pre-A1 → C2, con bandas "plus") y descriptores
Can-Do por dimensión, visibles en el Course.

### Añadido
- **Marco de descriptores CEFR** (`curriculum/cefr_descriptors.json` + `services/cefr_descriptors.py`):
  la escalera completa `Pre-A1, A1, A2, A2+, B1, B1+, B2, B2+, C1, C2` con descriptores "Can-Do"
  para 9 dimensiones (listening, speaking, reading, writing, grammar, vocabulary, pronunciation,
  **interaction** y **mediation** — las dos nuevas del Companion Volume).
- **Banda continua** (`band_for_numeric`): la estimación puede expresar matices (p. ej. "B1+") sin
  alterar la progresión de matrícula (`CEFR_ORDER` sigue con los 6 cursos principales).
- **`/api/academy/cefr-ladder`**: devuelve dimensiones + bandas con `is_current` y sitúa al alumno
  (`estimated_band`/`estimated_numeric`) desde el Student Model.
- **Course**: escalera CEFR completa con "You are here" y una tarjeta "What you can do" con los
  descriptores Can-Do del nivel estimado, agrupados por dimensión.

### Nota
- Los niveles "plus" (A2+/B1+/B2+) y Pre-A1 son **bandas de competencia**, no cursos con contenido
  propio: el contenido de los cursos (A1..B2) no cambia. La progresión de matrícula permanece intacta.

## [1.31.0] — 2026-08-28

**Adaptive Engine 2.0**: motor de prioridad explicable y "Why this activity?" en la tarjeta de
siguiente mejor actividad.

### Añadido
- **Priority Engine** (`services/adaptive.py`): `priority_signals()` expone las señales observables
  de cada candidato (recencia, retención, confianza, estabilidad, volumen de evidencia,
  transferencia/novedad y dificultad) y `priority_score()` las combina con el orden pedagógico por
  categoría en una prioridad compuesta determinista (0..1).
- **"Why this activity?"**: `explain_priority()` genera una explicación pedagógica en inglés por
  categoría (repaso, listening, debilidad, nuevo, refuerzo); `next_best_activity()` emite `signals`
  y `why` junto a `priority`.
- **Transparencia en la API**: `/api/academy/next-best` incluye `signals` y `why`
  (`NextBestActivityOut`); la tarjeta `NextBestCard` muestra la explicación bajo el CTA.

### Cambiado
- **`priority` semántico**: deja de ser la proyección ordinal fija (`NEXT_BEST_PRIORITY`) y pasa a
  ser un score compuesto explicable (base por categoría + olvido + debilidad + evidencia).
- **`get_next_best_activity`** pasa el perfil CEFR anotado y el instante de referencia al motor
  para calcular las señales.

## [1.30.0] — 2026-08-28

**LAN + Mobile 100%**: verificación real de mDNS, recuperación de permisos de micrófono,
test de micrófono con medidor de nivel, tarjeta de conexión con QR pulido y página de ayuda
`/help/connect` para confiar el certificado por plataforma.

### Añadido
- **mDNS real**: `/api/network` añade `local_url_available` (comprueba si `<host>.local`
  resuelve vía mDNS); el launcher marca la fila "Nombre local (mDNS)" como `resuelve`/`no resuelve`.
- **Recuperación de permiso**: `watchMicrophoneAvailability()` observa `visibilitychange`,
  `focus`, `devicechange` y la Permissions API; `useAudioCapabilities` ahora es reactivo (estado +
  `refresh`) en lugar de `useMemo(..., [])`, resolviendo el caso denegado → ajustes → conceder → volver.
- **Test de micrófono** (`components/MicrophoneTest.tsx`): botón "Test microphone" con medidor de
  nivel de entrada en vivo (`utils/microphoneLevel.ts`) y "Test playback"; integrado en el estado
  del sistema.
- **Tarjeta "Connect a device"** (`components/ConnectDeviceCard.tsx`): QR pulido, URL por IP
  (siempre) y `.local` (solo si resuelve), con enlace a la ayuda.
- **Página `/help/connect`** (`features/help/ConnectHelp.tsx`): instrucciones para confiar el
  certificado autofirmado en Windows, Android e iPhone/iPad; accesible desde el header (botón Help)
  y desde la tarjeta de conexión.
- **E2E móvil** (`tests/visual/mobile.spec.ts`): renderizado de la página de conexión y del test de
  micrófono, y aviso `MicUnavailableNotice` ante permiso denegado, en viewport móvil.
- **`docs/DEVICE_MATRIX.md`**: matriz de validación física (Android/iPhone/Tablet × Mic/Audio/
  Speaking/Listening).

### Cambiado
- **StatusBar**: la barra de estado y su popover ya no se recortan (`overflow: hidden` eliminado) y
  el popover queda acotado al viewport (`max-height` + scroll) con `z-index` correcto.

## [1.29.0] — 2026-08-28

**Fiabilidad LAN + audio móvil (P0) y lanzador de escritorio**: corrección del micrófono en móvil,
acceso por HTTPS autofirmado en la red local, y lanzador con estado en color, reinicio y reloj de
arranque.

### Añadido
- **Detección de capacidades de audio** (`utils/browserCapabilities.ts` + `hooks/useAudioCapabilities.ts`):
  capa que protege el acceso a `navigator.mediaDevices`/`getUserMedia`/secure context y muestra un
  aviso pedagógico (`MicUnavailableNotice`) en lugar del error "Cannot read properties of undefined".
- **`/api/network`**: expone `hostname` y `local_url` (`https://<host>.local`), con `url` ahora en HTTPS.
- **`/api/health/dependencies`**: nuevo estado `audio_library` (infraestructura de la biblioteca de audio).
- **Launcher**: botón "Reiniciar servidor", enlaces de acceso clicables (equipo, LAN y mDNS) y detalle
  del archivo de base de datos (tamaño, nº de tablas, fecha de modificación).
- **`components/ui/tooltip.tsx`**: tooltip accesible para el aviso de diferencia de dificultad del audio
  en Listening.

### Cambiado
- **HTTPS en la LAN**: el frontend se sirve con `@vitejs/plugin-basic-ssl`; Playwright y el launcher
  verifican el estado por HTTPS aceptando el certificado autofirmado.
- **Launcher**: estado con colores reales (verde/rojo/ámbar) en cabecera y servicios, reloj animado
  durante arranque/parada/reinicio, y resumen/diagnóstico de cookies más legible.
- **Analysis panel**: ancho máximo ampliado, pestañas que se envuelven (responsive) y topes de
  redimensionado conscientes del viewport.
- **Footer**: la barra de estado queda anclada al fondo en todas las vistas.
- **Listening**: el aviso de diferencia de dificultad del audio pasa de texto fijo a tooltip sobre un
  icono de aviso (clave `listening.audioGap` con placeholders).

## [1.28.0] — 2026-08-27

**Biblioteca de audio humano — código (P1.5–P1.8)**: ajuste puntual de Listening para ítems
grabados. El contenido real (WAV de varios hablantes) sigue pendiente de grabaciones del usuario;
la infraestructura (manifest + resolución + servido + validación) y el importador
(`backend/scripts/import_audio.py`) ya existían.

### Cambiado
- `features/listening/ListeningPractice.tsx`: la escalera de velocidad slow/normal/fast solo se
  muestra en ítems TTS; en ítems `recorded` la velocidad es la real y no sintetizable.

## [1.27.0] — 2026-08-27

**Code-splitting por rutas**: división del bundle con `React.lazy`/`Suspense`. Cambio solo-frontend.

### Cambiado
- **`app/Workspace.tsx`**: `HomeScreen`, `CourseScreen`, `ProgressScreen` y `PracticeView` pasan a
  `React.lazy` (patrón named→default), envueltos en `Suspense` con fallback (`Loader2` animado,
  `role="status"`/`aria-busy`).
- **`app/PracticeView.tsx`**: `AnalysisPanel` también se carga diferido (panel de insights).
- **`utils/i18n.ts`**: nueva clave `common.loading`.

### Resultado
- Chunk inicial: **537 kB → 425 kB** (gzip 134 kB), con chunks por ruta (`HomeScreen`, `CourseScreen`,
  `ProgressScreen`, `PracticeView`, `AnalysisPanel`) y ya sin aviso de bundle >500 kB.

## [1.26.0] — 2026-08-27

**Rediseño UI 2.0 — fases 3–6**: migración de las pantallas de práctica (Listening, Speaking,
Pronunciation y Progress) del CSS legacy a Tailwind v4 + shadcn/ui + Motion, con retirada de las
reglas huérfanas de `legacy.css`. Cambio solo-frontend.

### Cambiado
- **Listening** (`features/listening/ListeningPractice.tsx`): reproductor destacado con onda animada
  (Motion), variantes de velocidad 0.8x/1.0x/1.2x y estadísticas/diagnóstico presentados con
  `Card`/`Badge`. Lógica intacta (dictado, shadowing, retención, precisión por tema/dificultad).
- **Speaking** (`features/speaking/*` + `PronunciationPractice.tsx`): "estudio de conversación" con
  micrófono que pulsa (Motion) al grabar/escuchar y feedback de fluidez/coherencia con
  `SkillBar`/`Badge`. Props y lógica intactas.
- **Progress** (`features/progress/ProgressScreen.tsx`): dashboard pedagógico limpio con `LevelBadge`,
  barra `SkillBar`, lista de destrezas expandible y `SkillDetail`.
- **`styles/legacy.css`**: poda de ~1.400 líneas de reglas cuyas clases ya no se usan en ningún
  `.tsx` (verificado con `rg`). Se conservan los bloques aún en uso (chat/shell/header/composer y
  `.journey-*`).
- **Móvil**: tap targets ≥40px y sin overflow horizontal en las pantallas migradas (premisa 20).

### Añadido
- Claves i18n nuevas: `roleplay.hint`, `progress.score/confidence/evidence/stability`.

## [1.25.0] — 2026-08-27

**Paneles del chat redimensionables y persistentes**: los tres paneles del CHAT
(conversaciones, zona central y Análisis) son redimensionables por el usuario, con asas
visibles y accesibles, y el ancho elegido se persiste por usuario. Cambio solo-frontend.

### Cambiado
- **`ResizeHandle`** reestilizado con Tailwind: asa de 8px con *grip* central visible
  (`bg-border` → `bg-primary` al hover/foco), cursor de redimensionado y `touch-action: none`.
  Se oculta en móvil/tablet (`hidden lg:flex`) donde los paneles son drawers.
- **Accesibilidad**: el asa expone `role="separator"`, `aria-orientation="vertical"`,
  `aria-valuenow/min/max` y es operativa por teclado (flechas ←/→, ±24px).
- **Persistencia eficiente**: `setLayout` (hook `useChat`) persiste el ancho una sola vez al
  terminar de arrastrar (debounce 400ms) en lugar de un `PUT` por cada `pointermove`.
- **`styles/legacy.css`**: eliminadas las reglas huérfanas de `.resize-handle` (la clase ya no
  se usa); se conserva `body.is-resizing`.

### Añadido
- **Test visual Playwright** (`tests/visual/resize.spec.ts`): redimensiona el panel Análisis por
  teclado, comprueba el cambio de ancho y verifica que el ancho persiste tras recargar.

### Próximos incrementos (fases 3–6)
- **Fase 3** — `features/listening/ListeningPractice.tsx`: entorno auditivo inmersivo.
- **Fase 4** — `features/speaking/*`: "estudio de conversación" (mic que respira, feedback).
- **Fase 5** — `features/progress/ProgressScreen.tsx`: dashboard pedagógico limpio.
- **Fase 6** — Móvil específico y consolidación; **retirar `legacy.css`** una vez migradas todas
  las pantallas.

## [1.24.0] — 2026-08-27

**Analysis redesign + responsive 100%**: el panel ANALYSIS del chat pasa de 10 acordeones colapsables
a **navegación por pestañas** (una sección a la vez, sin truncado de texto), se hace una **pasada
responsive completa** de toda la app y se añaden **tests visuales Playwright** en 3 breakpoints como
parte de la Definition of Done. Cambio solo-frontend.

### Añadido
- **`AnalysisPanel`** (`src/components/AnalysisPanel.tsx`): 7 pestañas (Overview, Today, Profile,
  Speaking, Writing, Assessment, Tutor) con iconos, indicador activo animado (`layoutId` de Motion),
  transición de contenido (`AnimatePresence`) y scroll vertical propio por pestaña. Speaking agrupa
  Diagnostic + Panel + Journey; Writing agrupa Panel + Journey (se elimina el título duplicado).
- **Tests visuales Playwright**: `@playwright/test` + `playwright.config.ts` (3 proyectos: desktop
  1280×800, tablet 768×1024, móvil 390×844), spec `tests/visual/smoke.spec.ts`, script npm
  `test:visual` y helper `scripts/visual.ps1`. Captura screenshots reproducibles de las rutas
  principales en `tests/visual/screenshots/<proyecto>/`.

### Cambiado
- **`PracticeView`**: sustituye las 10 `InsightCard` por `<AnalysisPanel />`.
- **Pasada responsive completa**: `ProgressScreen`, `ListeningPractice`, `ReadingPractice`,
  `PronunciationPractice`, `SpeakingAssessment`, `SpeakingRolePlay`, `SettingsDialog`,
  `ProfileDialog`, `HelpDialog`, `Composer` y `HandsFreeToggle` corrigen overflow horizontal,
  `flex-wrap`, `min-w-0`, tap targets ≥40px y pestañas con scroll horizontal en móvil.
- **`docs/PREMISAS.md`**: añadidas premisas 19–21 (panel de análisis por pestañas sin truncado,
  responsive 100% verificado en 3 breakpoints y tests visuales Playwright obligatorios).

### Eliminado
- **`InsightCard`**: quedó sin uso tras la migración al panel por pestañas.

### Próximos incrementos (fases 3–6)
- **Fase 3** — `features/listening/ListeningPractice.tsx`: entorno auditivo inmersivo (reproductor,
  onda, variantes 0.8x/1.0x/1.2x).
- **Fase 4** — `features/speaking/*`: "estudio de conversación" (mic que respira, fluidez/coherencia,
  feedback).
- **Fase 5** — `features/progress/ProgressScreen.tsx`: dashboard pedagógico limpio.
- **Fase 6** — Móvil específico y consolidación; **retirar `legacy.css`** una vez migradas todas las
  pantallas.

## [1.23.0] — 2026-08-27

**UI 2.0 (incremento 1)**: adopción de un *design system* real — Tailwind CSS v4 + shadcn/ui + Motion —
para sustituir el CSS custom (~6.450 líneas) por primitivas y microinteracciones. Cambio solo-frontend:
no se toca backend, Student Model ni pedagogía.

### Añadido
- **Stack de diseño**: `tailwindcss` + `@tailwindcss/vite`, `motion`, `lucide-react` y dependencias de
  shadcn (`class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, `@radix-ui/*`); alias
  `@/*` → `src/*` en `vite.config.ts` y `tsconfig.json`; `components.json` y `lib/utils.ts` (`cn`).
- **Tokens de identidad**: `index.css` con tokens semánticos shadcn (`--background`, `--foreground`,
  `--card`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`,
  `--ring`, `--radius`, `--success`, `--warning`) mapeados al sistema de apariencia existente
  (`data-theme`/`data-accent`/`data-font`/`data-density`), preservando claro/oscuro y los 7 acentos.
- **Aislamiento del CSS legacy**: `src/index.css` → `src/styles/legacy.css` envuelto en `@layer base`
  e importado al final, para no romper las pantallas aún no migradas.
- **Primitivas shadcn**: `Button`, `Card`, `Badge`, `Progress` (`src/components/ui/`).
- **Primitivas de dominio**: `SkillBar` (barra animada al entrar), `LevelBadge` (insignia CEFR por tramo),
  `JourneyNode` (nodo del recorrido con pulso suave en el actual) y `Milestone` (hito de objetivo con icono por estado).

### Cambiado
- **AppShell/Header/Navigation**: reestilizados con Tailwind; navegación activa con píldora animada
  (`layoutId` de Motion) y nav inferior en móvil.
- **Home**: rediseñada con saludo personalizado (nombre), hero protagonista (insignia CEFR + preparación
  animada + tendencia), *Next Best Activity* como protagonista, skills con `SkillBar` y racha; entrada
  escalonada de secciones con Motion.
- **Course**: recorrido A1→B2 rediseñado con `JourneyNode`, línea de progreso, panel de nivel
  (insignia + barra de progreso + readiness) e hitos `Milestone`; entrada escalonada Motion.
- Versión → `1.23.0`.

## [1.22.0] — 2026-08-27

**Learning UX 2.0**: simplificación radical de la interfaz sin añadir pedagogía nueva. El objetivo es que
en 3 segundos se responda a *¿dónde estoy? ¿cómo voy? ¿qué hago ahora? ¿y después?* — y nada más compita
con esas cuatro respuestas.

### Añadido
- **Idioma de interfaz configurable (Español/English)**: sistema i18n completo (`utils/i18n.ts` +
  `hooks/useI18n.tsx`), persistido por usuario (localStorage + `interface_language` en backend). El
  contenido pedagógico permanece en inglés; solo el *chrome* se traduce. Por defecto **English**.
- **Next Best Activity**: el frontend ya no decide pedagogía; una única acción priorizada derivada del
  Adaptive Engine (`/api/academy/next-best`) con un único CTA `Continuar` (`NextBestCard`/`NextStep`).
- **Flujo Activity → Result → Feedback → Next**: componentes compartidos `ActivityResult` y `NextStep`
  para un bucle de práctica uniforme.
- **Course (antes Academy)**: renombrado a *Course* y presentado como recorrido CEFR con hitos
  (`CourseScreen`), no como panel administrativo.
- **Barra de estado colapsable**: indicador mínimo `● Ready` que expande el estado detallado del sistema
  (API/BD/Ollama/STT/TTS + URL LAN) al pulsar.

### Cambiado
- **Inicio (HOME) como "¿qué hago ahora?"**: el dashboard se centra en la siguiente mejor actividad y
  en el estado del alumno, reduciendo la carga cognitiva.
- **Navegación por destrezas**: distinción entre *PRIMARY SKILLS* (Listening, Speaking, Reading, Writing)
  y *SUPPORT* (Grammar, Pronunciation); sin niveles CEFR en los botones.
- **Controles técnicos reubicados**: `Modelo` y `Herramientas` se mueven al menú de usuario / ajustes
  (`SettingsDialog`), dejando la cabecera limpia.
- **Eliminado el botón "Marcar como hecho"**: las actividades se marcan automáticamente al generarse
  evidencia (elimina una acción pedagógicamente peligrosa).
- **App.tsx dividido**: `AppShell`, `Header`, `Navigation`, `Workspace`, `PracticeView` y `routes/`,
  más organización por features (`features/home`, `features/course`, `features/progress`, etc.).
- **Progreso simplificado**: indicadores cualitativos (B1, barras, "Improving") combinados con el % en
  lugar de porcentajes crudos por todas partes.
- **Limpieza y reorganización de `index.css`**.
- **i18n completo del chrome**: cierre de todos los strings en castellano restantes en componentes y
  helpers de dominio (`cefr`, `progress`, `speaking`, `fluency`, `pronunciationFeedback`).
- Versión → `1.22.0`.

## [1.21.0] — 2026-08-26

Cierra la **auditoría pedagógica A1→B2** de V1.21 (los seis P0/P1 del diagnóstico externo) y añade
una **nueva UI de 3 paneles** con barra de estado y navegación por destrezas. Filosofía intacta: el
LLM solo extrae evidencia; todo el scoring es determinista, local y honesto (lo no verificable se
declara como tal, no se inventa).

### Añadido
- **Corpus de audio humano 1.0 (P0-1)**: `AudioLibraryEntry` ampliado con 11 metadatos auditivos
  (`gender`, `age_band`, `region`, `speech_rate`, `spontaneity`, `recording_environment`, `overlap`,
  `connected_speech`, `prosody`, `task_type`, `cefr`) usando `Literal`; `AUDIO_LIBRARY_VERSION` →
  `1.1.0`; `library_summary` con desgloses `by_cefr`/`by_speaker_id`/`by_accent`/`by_region`; CLI
  `backend/scripts/import_audio.py` (`wav_metadata` con solo `wave`).
- **Validación determinista audio↔metadata (P0-2)**: `wav_probe`, modelo `AudioValidationIssue`,
  `validate_audio_entry`/`validate_audio_entries` (duración verificable; `speaker_count` como proxy
  por canales; `speech_rate`/`noise_level`/`accent`/`recording_environment`/`prosody` como `info` "no
  verificable" sin inventar SNR) y flag `--validate-all` en el CLI de importación.
- **Separación del proxy de pronunciación del audio real (P0-3)**: `phoneme_accuracy` →
  `phoneme_accuracy_proxy` y `prosody_score` → `prosody_proxy`; `pronunciation_source:
  "transcript"` y rótulos honestos "proxy de texto / sin audio" en el frontend. Sin cambios de pesos.
- **Evidencia familiar/transfer/novel (P1-4)**: dimensión `evidence_kind` en el Student Model
  (columna `evidence_kind` con migración idempotente), `generalized_mastery_score` ponderado por
  tipo de evidencia y `evidence_by_kind` en `build_skill_profile`.
- **Interaction 3.0 (P1-5)**: `turn_balance` con meseta `[0.3, 0.7]`, renombrado del objetivo
  `turn_completion` → `turn_duration` (desambiguado del semántico del LLM), señal `repair` añadida y
  reponderación objetivo (0.3) / subdimensiones (`turn_balance` 0.3 + `turn_duration` 0.7).
- **Matriz de assessment CEFR A1–B2 (P1-6)**: `backend/curriculum/cefr_matrix.json` + cargador
  `services/cefr_matrix.py`; `adaptive.readiness` consume umbrales de `minimum_mastery`/
  `minimum_confidence`/`minimum_evidence` y gates `transfer_required`/`novel_required`
  (retrocompatible), con campos nuevos en `ReadinessSkillOut`.
- **UI de 3 paneles**: barra superior (logo + avatar de usuario + navegación de 6 destrezas +
  Academy + manos libres/modelo/herramientas/ayuda), panel central de desarrollo, panel derecho de
  análisis y **barra de estado inferior** (API/BD/Ollama/STT/TTS + URL LAN); sistema de iconos SVG
  coherente (`Icons.tsx`), `SectionNav`, `ReadingPractice`, `StatusBar` y persistencia de la sección
  por usuario. Script `launcher/allow-firewall.ps1` para exponer 5173/8000 en la red local.
- **Learning Home (HOME como centro)**: pantalla de inicio que responde a "¿qué debo hacer ahora y
  cómo voy?", con saludo, hero de nivel (banda CEFR + preparación para el siguiente nivel +
  tendencia), **plan de hoy como tarjetas de acción** (`LearnToday`, una acción por tarjeta), barras
  de destrezas, racha/actividad y un único CTA "Practice now" hacia la destreza a reforzar. Reutiliza
  `profile`/`history`/`getSession` existentes (sin backend nuevo); la marca del header vuelve a
  Inicio. Etiquetas compartidas extraídas a `utils/learningLabels.ts`.

### Cambiado
- Versión → `1.21.0`.
- La app abre ahora en **Inicio** (antes abría directamente en el chat).

## [1.20.0] — 2026-08-26

Cierra los tres incrementos naturales pendientes de V1.19: la **pronunciación fonémica (P6)**, la
**integración del turn-taking real** en la parte "Interaction" del Speaking Assessment, y la
**infraestructura de biblioteca de audio humano** (P1.5–P1.8). Filosofía intacta: el LLM solo
extrae evidencia; todo el scoring determinista y local.

### Añadido
- **Pronunciación fonémica (P6)**: `phoneme_alignment`/`syllables`/`prosody_score` en
  `services/phonemes.py` (alineación de fonemas con `SequenceMatcher` + prosodia proxy por nº de
  sílabas). `composite_score` rebalanceado a `word 0.35 / phoneme 0.35 / phonetic 0.15 / prosody
  0.15` (se elimina la similitud por caracteres) y expone `prosody_score` + `phoneme_breakdown`.
  El rubric de pronunciación pasa de 3 a 4 criterios (añade `prosody`); `PronunciationResponse`
  y `PronunciationPractice.tsx` muestran "Precisión de fonemas" y "Prosodia (ritmo)".
- **Turn-taking real → Interaction**: `components/SpeakingRolePlay.tsx` (role-play en vivo dentro
  del Speaking Assessment) con telemetría de turnos (`duration_ms`/`latency_ms`) y persistencia de
  la conversación; `SpeakingAssessment.tsx` bifurca por `task_type` conversacional
  (`isConversationalTaskType` en `utils/speaking.ts`) y `submitSpeakingAssessmentPart` envía
  `conversation_id` para inyectar `interaction_objective` (señal objetiva) en el scorer.
- **Biblioteca de audio humano (P1.5–P1.8)**: `services/audio_library.py` con manifest versionado
  (`backend/audio_library/manifest.json`, vacío hoy — límite de contenido), resolución segura del
  WAV grabado (rechaza rutas fuera de la biblioteca) y servido sin Piper: `get_audio` sirve audio
  `recorded` desde el manifest y devuelve 404 (no TTS) si falta; `audio_ready` ya no depende solo
  de Piper.

### Cambiado
- Versión → `1.20.0`.

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
