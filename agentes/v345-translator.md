# Briefing de subagente — V3.45 (Traductor de viaje práctico + voz española real)

> **Estado:** ejecutado por el gerente el 2026-09-11 (release `v3.45.0`). Se
> mantiene como registro del alcance acordado.
> Ver `release-notes-v3.45.0.md` para el resultado final.
> Escrito por el gerente el 2026-09-11 a partir del feedback de uso del
> Traductor de viaje (V3.39, Fase 2) y del roadmap de la auditoría de V3.43.0.

## Rol

Ingeniero de backend + frontend del proyecto English Tutor, con foco en la
utilidad de viaje (Traductor ES↔EN) y el subsistema de voz (Piper TTS / Whisper
STT).

## Objetivo

Cerrar la experiencia del Traductor de viaje en dos frentes, sin tocar el motor
de aprendizaje (el Traductor es auxiliar y NO registra evidencia):

- **A — Voz española real.** Hoy `language="es"` degrada en silencio a una voz
  INGLESA: en `backend/models/piper/` solo hay voces `en_*`, `download_models.py`
  solo instala la inglesa y `resolve_voice()` cae a `_fallback_voice()`. Por eso
  la salida en español suena «un inglés hablando español». Hay que elegir una
  voz del idioma, instalarla por defecto y auto-descargarla si falta.
- **B — Modo Conversación (2 botones grandes).** El Traductor actual tiene un
  único `MicButton` (46 px) y dos `ListenButton` (32 px); no hay turnos
  alternos ni auto-reproducción. Se añade una pantalla de conversación con dos
  botones grandes (uno por hablante), auto-parada por silencio (VAD),
  auto-traducción y auto-reproducción, siguiendo el patrón de Google Translate
  (`Live translate` → `Conversation` / `Face to face`).

## Contexto del proyecto

- **Stack:** backend FastAPI + Pydantic + SQLite (Python 3.12, `backend/.venv`),
  frontend Vite + React + TypeScript (`frontend/`). 100 % local (Ollama + Piper
  + Whisper).
- **Premisa 21:** el LLM GENERA CONTENIDO, nunca decide evidencia.
- **Premisa 12:** cada fix va precedido de un test que falle hoy.
- **El Traductor es auxiliar:** no declara dominio, no toca FSRS, no registra
  intentos ni evidencia. Funciona sin perfil (con perfil solo aprovecha su voz
  del idioma).
- **Arranque:** `cd backend && .venv\Scripts\python.exe -m pytest`;
  `cd frontend && npm run test && npx tsc --noEmit && npm run build`;
  `python scripts/check_release_consistency.py` (exit 0).

## Decisión de alcance (cerrada por el gerente)

Alcance **A**: Traductor (UX conversación) + voz española real. Los P1 de
transferencia (`transfer_condition` y CEFR/`difficulty_vector` del contexto)
pasan a **V3.46**. Después, el resto de P2 (Context Bank 2.0, diversidad 2.0,
semantic appropriateness, transfer_state enriquecido y Adaptive Planner 2.0 /
`expected_learning_value`).

Voz española por defecto elegida: **`es_ES-davefx-medium`** (España, masculina,
~63 MB). Disponibilidad: descarga en la instalación inicial + auto-descarga
perezosa la primera vez que se pide TTS en español, con fallback si no hay red.

## Archivos clave

- `backend/config.py` — `SPANISH_VOICE`, `DEFAULT_VOICES` (idioma → voz).
- `backend/services/tts.py` — `default_voice_for` (pura) y `resolve_voice`
  priorizando el default del idioma; `ensure_voice_for_language` (auto-descarga,
  nunca lanza).
- `backend/routers/voz.py` — `/api/tts` asegura la voz del idioma antes de
  sintetizar (fallback si falla, sin 500 nuevo).
- `backend/download_models.py` — instala también la voz española reutilizando
  `services/voice_downloads.download_voice`.
- `backend/services/voice_downloads.py` — catálogo curado (ya incluye las voces
  `es_*`); no cambia salvo necesidad.
- `backend/schemas/voices.py` + `backend/routers/voices.py` — `VoicesResponse`
  expone `defaults` (idioma → voz por defecto).
- `frontend/src/features/translator/TranslatorScreen.tsx` — pestañas
  Conversación (por defecto) / Escribir (modo texto actual, intacto).
- `frontend/src/features/translator/useVoiceTurn.ts` — **nuevo**: turno de voz
  (MediaRecorder + AnalyserNode + VAD + transcripción).
- `frontend/src/features/translator/BigMicButton.tsx` — **nuevo**: botón grande.
- `frontend/src/features/translator/ConversationPanel.tsx` — **nuevo**: panel de
  un idioma (botón, estado, texto y traducción, repetir audio).
- `frontend/src/features/translator/ConversationTranslator.tsx` — **nuevo**:
  orquesta los dos paneles, auto-play, «cara a cara» e historial de turnos.
- `frontend/src/utils/i18n.ts` — claves `translator.mode.*` y
  `translator.conversation.*` con paridad ES/EN.
- Reutilizables: `frontend/src/api/voz.ts` (`transcribe`, `speak`),
  `frontend/src/api/translate.ts` (`translateText`), `frontend/src/utils/vad.ts`,
  `frontend/src/utils/microphoneLevel.ts`, `frontend/src/utils/browserCapabilities.ts`,
  `frontend/src/hooks/useRecordingSession.ts`, `frontend/src/api/voices.ts`.

## Tarea detallada

1. **Voces por idioma.** `DEFAULT_VOICES = {"en": PIPER_VOICE, "es":
   SPANISH_VOICE}` y `default_voice_for(language)` pura. `resolve_voice` pasa a:
   preferencia del usuario del idioma → **default del idioma si está instalado**
   → primera instalada del idioma → fallback global. Con `language="en"` el
   comportamiento es idéntico al histórico.
2. **Auto-descarga.** `ensure_voice_for_language(language) -> bool`: si ya hay
   voz del idioma instalada, no-op; si el default está en el catálogo curado,
   descargarla (thread-safe, vía `services.voice_downloads`); nunca lanza
   (loguea y devuelve `False`). `/api/tts` la invoca en el threadpool antes de
   resolver la voz; si falla, se sigue con el fallback actual.
3. **Instalación inicial.** `download_models.py` instala `SPANISH_VOICE` además
   de la inglesa, reutilizando el catálogo curado.
4. **Contrato de voces.** `VoicesResponse.defaults: dict[str, str]` para que el
   frontend conozca el id por defecto del español sin hardcodearlo.
5. **Modo Conversación.** `ConversationTranslator` mantiene dos paneles (ES y
   EN); cada turno: grabar con VAD y auto-stop → `transcribe(blob, lang)` →
   `translateText(text, dir)` → mostrar texto+traducción → `speak(trad, lang)`
   si el auto-play está activo → añadir al historial. Estados de un turno
   `idle | listening | transcribing | error`; el botón del idioma se deshabilita
   mientras el otro turno está activo. Fallback: si la transcripción falla, se
   puede editar el texto y re-traducir sin regrabar. Toggles «Reproducir
   automáticamente» (por defecto ON) y «Cara a cara» (rota 180° el panel del
   interlocutor) + control de tamaño de texto. Historial persistido en
   `localStorage` (`english-tutor.translator-conversation`).
6. **Aviso de voz.** Al montar, si falta la voz del idioma, chip «Preparando voz
   en español…» y descarga en segundo plano con `downloadVoice(defaults.es)`;
   oculto si ya está instalada.
7. **i18n y tests.** Claves nuevas en ES/EN (paridad forzada). Tests backend de
   resolución por idioma, `ensure_voice_for_language` y `/api/tts` en español;
   tests frontend del hook y del panel, y actualización de
   `TranslatorScreen.test.tsx` para las pestañas.

## Criterios de aceptación

- `pytest` 0 fallos y `ruff check backend/` limpio.
- `npm run test`, `npx tsc --noEmit` y `npm run build` limpios.
- `check_release_consistency` **3.45.0** exit 0.
- Con una voz `es_*` instalada, `/api/tts` con `language="es"` NO usa voz
  inglesa; sin voz y sin red, degrada sin romper.
- Contratos HTTP estrictamente aditivos (`/api/tts`, `/api/voices`, `/api/translate`
  conservan su semántica; `defaults` es aditivo).
- El modo Escribir del Traductor conserva su comportamiento y sus tests.

## Restricciones

- **No** tocar el motor de aprendizaje ni registrar evidencia desde el Traductor.
- **No** migración destructiva ni cambios de esquema.
- **No** dar al LLM autoridad sobre la evidencia.
- Mantener la paridad ES/EN de i18n y no romper `legacy.css` (reutilizar las
  clases `mic-button`).

## Salida esperada

Diff en backend y frontend, tests nuevos (`useVoiceTurn.test.ts`,
`ConversationPanel.test.tsx`) y ajustes de los existentes, y documentación de
release (`release-notes-v3.45.0.md`, `CHANGELOG.md`, `PLAN.md`,
`docs/RELEVO.md`, `agentes/README.md`).
