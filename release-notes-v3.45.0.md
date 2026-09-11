# v3.45.0 — Traductor de viaje práctico + voz española real

**Cierre de la experiencia del Traductor de viaje en dos frentes. (A) La salida
en español sonaba a «un inglés hablando español» porque `language="es"` degradaba
en silencio a la voz inglesa: no había ninguna voz `es_*` instalada,
`download_models.py` solo bajaba la inglesa y `resolve_voice` caía al fallback
global. Ahora hay una VOZ POR DEFECTO para cada idioma
(`SPANISH_VOICE = es_ES-davefx-medium`), `resolve_voice` prioriza el default del
idioma y `/api/tts` auto-descarga la voz si falta (con fallback si no hay red). (B) El Traductor gana un modo CONVERSACIÓN
con dos botones grandes (uno por hablante), cierre por silencio (VAD),
auto-traducción y auto-reproducción, más «cara a cara» y tamaño de texto,
siguiendo el patrón de Google Translate (`Live translate` → `Conversation` /
`Face to face`). Sigue siendo una utilidad AUXILIAR: no registra evidencia.**

Versión de app `3.44.0 → 3.45.0`. Backend (`config.py`, `services/tts.py`,
`routers/voz.py`, `routers/voices.py`, `schemas/voices.py`,
`download_models.py`) + frontend (`features/translator/*`, `types/api.ts`,
`utils/i18n.ts`) + tests y docs.

## Contexto

El Traductor de viaje (V3.39, Fase 2) ya era bidireccional ES↔EN por voz o texto,
pero al usarlo aparecían dos problemas reales:

- **La voz española no era española.** En `backend/models/piper/` solo había
  voces `en_*`; `download_models.py` solo instalaba `en_US-lessac-medium` y
  `resolve_voice(prefs, "es")` no encontraba voz del idioma, así que degradaba a
  `_fallback_voice()` (una voz inglesa). El catálogo curado ya ofrecía tres voces
  `es_*` descargables, pero ninguna se instalaba por defecto.
- **Poco práctico para una conversación real.** Un único `MicButton` (46 px) en
  el lado origen y dos `ListenButton` (32 px) obligaban a leer el texto en lugar
  de pasar el dispositivo al interlocutor.

Fuera de alcance (diferido a V3.46): los P1 de transferencia
(`transfer_condition` y CEFR/`difficulty_vector` del contexto). Después, el resto
de P2 (Context Bank 2.0, diversidad 2.0, semantic appropriateness,
transfer_state enriquecido y Adaptive Planner 2.0 / `expected_learning_value`).

## Qué cambia

- **Voz por defecto de cada idioma (`config.py`, `services/tts.py`).**
  `SPANISH_VOICE = "es_ES-davefx-medium"` y `DEFAULT_VOICES = {"en":
  PIPER_VOICE, "es": SPANISH_VOICE}`. Nueva función PURA
  `default_voice_for(language)` (idiomas sin default declarado caen al histórico
  `config.PIPER_VOICE`). `resolve_voice(prefs, language)` pasa a priorizar la
  preferencia del usuario del idioma → **el default del idioma si está
  instalado** → la primera voz instalada del idioma → fallback global. Con
  `language="en"` el comportamiento es idéntico al histórico.
- **Auto-descarga de la voz del idioma (`services/tts.py`, `routers/voz.py`).**
  Nueva `ensure_voice_for_language(language) -> bool`: si ya hay una voz del
  idioma instalada es un no-op; si falta y el default está en el catálogo curado
  (`services.voice_downloads`), lo descarga (thread-safe); si falla (sin red,
  disco) devuelve `False` y NUNCA lanza. Un fallo se recuerda un TTL
  (`_VOICE_ENSURE_FAILED_TTL_SECONDS = 300`) para no reintentar la descarga en
  cada petición. `/api/tts` la ejecuta en el threadpool antes de resolver la voz,
  así que la primera petición en español instala la voz y sintetiza con ella; si
  no puede, se sigue con el fallback sin devolver 500.
- **Instalación inicial (`download_models.py`).** Se instala también la voz
  española por defecto reutilizando `services.voice_downloads.download_voice`
  (una sola fuente de ids y URLs), de modo que una instalación nueva ya trae
  español real.
- **Contrato de voces aditivo (`schemas/voices.py`, `routers/voices.py`).**
  `VoicesResponse` añade `defaults: dict[str, str]` (idioma → voz por defecto)
  para que el Traductor conozca el id del español sin hardcodearlo.
- **Modo Conversación (frontend, `features/translator/`).** `TranslatorScreen`
  pasa a tener dos pestañas: **Conversación** (por defecto) y **Escribir** (el
  modo texto histórico, intacto: dirección, ⇄, historial y sus tests).
  - `useVoiceTurn.ts` (nuevo): gobierna UN turno —micrófono, `MediaRecorder`,
    `AnalyserNode` para nivel y VAD, transcripción con `transcribe(blob,
    language)`— y libera stream/AudioContext al terminar. Helper PURO
    `nextTurnVadState(prev, energy, nowMs)`: cierra el turno cuando hay voz
    sostenida (≥ `MIN_SPEECH_MS`) seguida de silencio (≥ `SILENCE_MS`) y descarta
    los picos de ruido. Auto-stop de seguridad a 120 s con `useRecordingSession`.
  - `BigMicButton.tsx` (nuevo): botón circular grande (`size-24`) con anillo que
    late según el nivel y estados inactivo/escuchando/transcribiendo.
  - `ConversationPanel.tsx` (nuevo): panel por idioma (etiqueta del hablante,
    botón grande, estado, par texto/traducción, repetir audio, avisos de micro y
    transcripción) con rotación opcional para «cara a cara».
  - `ConversationTranslator.tsx` (nuevo): orquesta los dos paneles; al terminar
    un turno traduce, lo añade al historial persistido
    (`english-tutor.translator-conversation`) y, si el auto-play está activo,
    reproduce la traducción en el idioma del interlocutor. Toggles «Reproducir
    automáticamente» (ON por defecto) y «Cara a cara» (rota el panel del
    interlocutor 180°) + control del tamaño del texto. Si falta la voz española,
    muestra «Preparando la voz en español…» y la descarga en segundo plano con
    `downloadVoice(defaults.es)`.
- **i18n.** Nuevas claves `translator.mode.*` y `translator.conversation.*` con
  paridad ES/EN (`i18n.parity.test.ts` sigue pasando).

## Tests

- Backend pytest **2030 passed** (+10): `test_voices.py` cubre
  `default_voice_for` (conocidos/desconocidos), `resolve_voice` con `es` (default
  del idioma por delante del orden alfabético, y caída a la primera voz del
  idioma), `ensure_voice_for_language` (no-op, descarga del default, `False` sin
  red con caché negativa para no reintentar, `False` si el default no está en el
  catálogo), `GET /api/voices` con `defaults` y `/api/tts` en español que
  auto-descarga la voz ausente y sintetiza con ella.
- Frontend vitest **72 ficheros/621 tests** (+2 ficheros/+13): nuevo
  `useVoiceTurn.test.ts` (VAD puro: silencio, cierre tras habla, pico corto
  descartado, reinicio al volver la voz), nuevo `ConversationPanel.test.tsx`
  (estados del botón, par texto/traducción, repetir audio, rotación, error) y
  `TranslatorScreen.test.tsx` actualizado a las pestañas + modo Conversación.
- Verificación: `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.45.0**
  exit 0.

## Fuera de alcance (V3.46+)

- `transfer_condition` (`prompted`/`cued_context`/`open_context`/`free_choice`/
  `naturally_emergent`) y CEFR/`difficulty_vector` del contexto (P1).
- Context Bank 2.0, diversidad 2.0, semantic appropriateness y transfer_state
  enriquecido (`confidence`, `evidence_count`, `recency`).
- `expected_learning_value` / Adaptive Planner 2.0 y Student Model
  multidimensional (salto de arquitectura).

## Decisiones de diseño

- **El Traductor sigue siendo AUXILIAR.** El modo Conversación no registra
  evidencia ni intentos, no toca FSRS y funciona sin perfil (con perfil solo
  aprovecha su voz del idioma). La premisa 21 se mantiene: nada del LLM decide
  evidencia.
- **Voz real, degradación honesta.** Con una voz del idioma instalada, el TTS
  NUNCA usa otra; sin ella intenta instalarla y, si no puede, degrada sin romper
  (nunca un 500 por este motivo).
- **Cierre de turno determinista y testeable.** El VAD vive en `utils/vad.ts` y
  la decisión de cierre en una función pura (`nextTurnVadState`), de modo que la
  lógica crítica se prueba sin DOM ni micrófono.
