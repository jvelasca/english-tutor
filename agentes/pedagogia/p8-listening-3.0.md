# P8 — Listening 3.0: audio real + cierre A1→B2 + evidencia por sub-destreza

## Rol
Subagente full-stack que convierte el listening de "scripts de texto + TTS genérico en vivo" a
**audio real por ítem** (Listening 3.0), cierra el currículo **A1→B2** de comprensión auditiva y
garantiza que cada sub-destreza genere **evidencia independiente**. Todo 100% local y determinista
en el score; sin LLM y sin red.

## Contexto
El listening ya tiene una arquitectura sólida (P4/V1.10 y V1.11): 23 ítems en
`services/listening.py::QUESTION_BANK` con **vector de dificultad de 8 dimensiones**, 15
sub-destrezas canónicas (`LISTENING_SUBSKILLS`), 10 temas (`LISTENING_TOPICS`), métricas de
competencia (`accuracy_by_difficulty`, `accuracy_by_topic`, `recent_trend`, `recurrence_stats`) y
`listening_diagnostic`. Los ítems `l15`–`l23` ya declaran metadatos de audio (`audio_id`,
`duration`, `speaker_id`, `accent`, `speech_rate`, `transcript`, `clean_transcript`,
`noise_level`, `repetition_policy`)…

…pero **no existe ningún fichero de audio real**: esos `audio_id` son placeholders. El frontend
(`ListeningPractice.tsx`) "escucha" llamando a `speak(question.script)`, que sintetiza el script
genérico en vivo con la única voz Piper, ignorando `accent`/`speech_rate`/`noise_level` del ítem.

Además hay un hueco de contenido: `LEVEL_ORDER = ["A1", "A2", "B1"]` y solo existen
`backend/curriculum/{a1,a2,b1}.json` (+ `assessments.json`). No hay `b2.json`, aunque el banco ya
tiene ítems B2 (`l16`, `l17`, `l20`, `l21`). La auditoría externa pidió **cerrar A1→B2 primero**
en listening (y speaking) antes de aspirar a C1/C2.

**Restricción honesta (crítica):** la app es 100% local. La síntesis disponible es Piper
(`services/tts.py`, una sola voz `en_US-lessac-medium`, `length_scale` controla la velocidad). Por
tanto "audio real" significa **audio pre-renderizado por ítem** que honra `speech_rate` y la
transcripción; los acentos múltiples, el ruido de fondo y los hablantes distintos son límites de
**contenido** (se necesitarían voces/grabaciones adicionales), no solo de código. Este incremento
debe ser honesto con ese límite: no fingir acentos/ruido que no existen.

## Archivos
- Backend: `services/listening.py`, `routers/listening.py`, `domain/listening.py`,
  `repositories/listening.py`, `services/tts.py` (solo lectura del contrato `synthesize`),
  `services/curriculum.py` (`LISTENING_BANK_VERSION`), `curriculum/b2.json` (nuevo),
  `backend/scripts/generate_listening_audio.py` (nuevo).
- Tests: `backend/tests/test_listening.py`, `backend/tests/test_listening_architecture.py`.
- Frontend: `frontend/src/api/listening.ts`, `frontend/src/types/api.ts`,
  `frontend/src/components/ListeningPractice.tsx`, `frontend/src/index.css`.
- Tests frontend: `frontend/src/api/listening.test.ts` (o el archivo de tests de API existente).

## Tarea

### 1. Audio real por ítem (servir + cachear)
- Nuevo endpoint `GET /api/listening/audio/{question_id}` en `routers/listening.py` que devuelve
  `audio/wav` del ítem (`Response(content=..., media_type="audio/wav")`). Si el ítem no existe →
  404; si el modelo Piper no está disponible (`tts.is_ready()` False) → 503 con mensaje claro.
- El audio se **pre-renderiza y se cachea en disco** (`backend/data/listening/<question_id>.wav`)
  para no sintetizar en cada reproducción: primera petición sintetiza y guarda, siguientes sirven
  del caché. Usa `tts.synthesize(transcript)` en un threadpool; la velocidad se controla vía el
  `length_scale` del modelo (documentar cómo mapear `speech_rate` → `length_scale`, p. ej.
  `length_scale = 140 / speech_rate` clampado). `repetition_policy="twice"` implica duplicar el
  texto (o dos pasadas concatenadas).
- Expón en `ListeningQuestion` (schema + `domain._public`) un flag `audio_ready` (True si el ítem
  declara `transcript` no vacío y Piper está listo) para que el frontend sepa si puede reproducir
  audio real o degradar.

### 2. Herramienta de generación (reproducible)
- `backend/scripts/generate_listening_audio.py`: recorre `QUESTION_BANK` y pre-renderiza los WAV
  en `backend/data/listening/` (idempotente, salta los ya generados salvo `--force`). Imprime un
  resumen (generados/saltados/errores). No requiere red; falla limpiamente si falta Piper.

### 3. Cierre A1→B2 del currículo
- Nuevo `backend/curriculum/b2.json` siguiendo el formato de `a1/a2/b1.json` (módulos/unidades/
  lecciones/objetivos `can_do` + checks de opción múltiple, cubriendo exactamente sus destrezas
  evaluables — invariante curricular existente).
- `services/listening.py`: `LEVEL_ORDER = ["A1", "A2", "B1", "B2"]` y asegurar que todos los ítems
  B2 del banco tengan `transcript` real (no placeholders) para poder servir audio.
- Bump `LISTENING_BANK_VERSION` (→ `3.0.0`) y reflejar el cierre A1→B2 en docstrings.

### 4. Evidencia independiente por sub-destreza
- Verificar (y testear) que cada ítem registra su `skill` como sub-destreza canónica en
  `listening_attempts`, de modo que `listening_diagnostic` ya expone evidencia independiente por
  sub-destreza. Cubrir con un test las sub-destrezas nuevas (`fast_speech`, `connected_speech`,
  `multiple_speakers`, `dictation`, `shadowing`, `speaker_intention`): un intento de cada una
  genera su fila y aparece en `subskills` con `attempts ≥ 1`.
- Si se detecta que un ítem B2 usa una sub-destreza fuera de `LISTENING_SUBSKILLS`, corregirla.

### 5. Frontend
- `api/listening.ts`: `getListeningAudioUrl(questionId)` (URL del nuevo endpoint) y usar un
  `<audio>`/`Audio` para reproducir el audio real en lugar de `speak(question.script)` cuando
  `question.audio_ready`; si no, degradar al TTS en vivo actual con un aviso ("audio de referencia
  no disponible").
- `types/api.ts`: `audio_ready: boolean` (y cualquier campo nuevo) en `ListeningQuestion`.
- `ListeningPractice.tsx`: botón de reproducción apunta al audio real; mostrar metadatos
  (`accent`, `speech_rate`, `noise_level`, `duration`) ya presentes; respetar `replayCount` para
  la métrica.
- `index.css`: estilos con tokens para el reproductor/aviso de degradación.

### 6. Tests
- Backend: endpoint de audio (200 con `audio/wav` usando un `synthesize` monkeypatcheado,
  404 para id inexistente, 503 sin Piper), cache (segunda petición no re-sintetiza), `b2.json`
  valida invariantes, `LEVEL_ORDER` incluye B2, y evidencia por sub-destreza independiente.
- Frontend: `api/listening.test.ts` (+`getListeningAudioUrl` y manejo de `audio_ready`).

## Criterios de aceptación
- Backend `pytest` verde + `ruff check .` limpio; frontend `tsc --noEmit` + `vitest run` verdes;
  launcher `pytest` verde.
- `GET /api/listening/audio/{question_id}` sirve WAV reproducible y cacheado; 503 honesto sin
  Piper; 404 para id inexistente.
- `LEVEL_ORDER` cierra A1→B2 con `b2.json` válido (invariantes curriculares en verde).
- Cada sub-destreza canónica genera evidencia independiente visible en `listening_diagnostic`.
- `LISTENING_BANK_VERSION` → `3.0.0` y docs actualizadas (`docs/RELEVO.md`, `PLAN.md`).
- Todo 100% local, determinista en el score, sin LLM ni red.

## Restricciones
- No tocar `services/speaking*.py`, `services/cefr.py` ni `domain/profile.py` (de V1.12).
- No fingir acentos/ruido de fondo: documentar el límite real de Piper (voz única, control de
  velocidad). No incluir grabaciones con derechos de autor.
- Mantener la filosofía "score determinista" (el listening no usa LLM para puntuar).
- Mantener los docstrings (premisa 18). Un commit `feat:` único, verificado en verde.

## Salida
- Diff backend + frontend + scripts + resultado de `pytest`/`ruff`/`tsc`/`vitest` en verde.
