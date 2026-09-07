# Briefing — Auditoría TOTAL externa (read-only) de v3.21.0

> Fecha: 2026-09-07 · Rol: **auditor externo read-only** (subagente autocontenido).
> Objetivo: reproducir y verificar las afirmaciones de la posición **v3.21.0** —
> *Speaking & Evidence Calibration* — y que el cierre no rompe CONSTITUCIÓN,
> premisas ni mecanismos previos. Sigue la metodología de las auditorías
> externas v3.16/v3.17/v3.18/v3.20 y la plantilla `docs/audit/TEMPLATE.md`.

## 0. Cómo arrancar (auditor, contexto nuevo)

1. Lee en orden: `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`,
   `docs/RELEVO.md` (solo encabezado + secciones 0 y 9), `PLAN.md`
   (estado actual), `README.md`, `CHANGELOG.md`, `release-notes-v3.21.0.md`
   y los dossieres `docs/audit/*.md`.
2. Confirma el punto de partida del repo con:
   ```powershell
   git log --oneline -3
   git status --short          # debe estar limpio (o solo cambios del auditor)
   ```
   La posición es **v3.21.0**, commit de release `14a2f7f`
   (`backend/config.py::VERSION = "3.21.0"`, `frontend/package.json` /
   `package-lock.json` idénticos). `git status` limpio.
3. Entorno Windows/PowerShell. Backend: Python en `backend\.venv`. Frontend:
   Node en `frontend`. No instalar dependencias; no modificar código fuera de
   `docs/audit/` si el gerente autoriza el dossier.

## 1. Alcance (TOTAL con foco V3.21)

- **Núcleo v3.21 (plan del dossier de la auditoría externa V3.20)**:
  - **F1 P0** — verdad del micro-drill: producción por **alineación secuencial**
    (`unit_produced`) + acreditación atómica de unidades multi-palabra
    (V20-01).
  - **F2 P1** — feedback honesto y taxonomía ASR: metadata de Whisper,
    `asr_status ∈ {ok, no_speech, unintelligible, low_confidence}` y **gating de
    no-penalización** en los intentos puntuados; chips palabra a palabra
    re-etiquetados y mensajes de audio no reconocido (V20-02/V20-14/V20-15).
  - **F3** — quick wins: `DEFAULT_MODEL` fuente única, comentario `ADMIN_PIN`,
    hook `useRecordingSession` + red de seguridad backend de duración, aviso de
    audio vacío (V20-05/V20-09/V20-13).
  - **F4** — semántica de superficie Speaking: título del modo real y pies de
    stats con la competencia real (V20-03/04).
  - **F5** — matriz de competencia léxica por ítem
    (Recognition/Production/Transfer/Retention/gap) expuesta en
    API/diccionario + **Transfer Gap para FSRS** (V20-16/17).
  - **F6** — drill escalera MVP: paso Sentence determinista sin LLM +
    graduación espaciada de la lista "pendiente" (V20-06).
- **Estado global declarado** (`docs/RELEVO.md` encabezado, `CHANGELOG.md`,
  `release-notes-v3.21.0.md`): números de tests, gates, consistencia de versión,
  i18n.
- **NO se audita** (frontera honesta): ejecución física en dispositivos
  (`docs/audit/G-DEVICES.md`), variabilidad LLM con Ollama real
  (`docs/audit/C-SPEAKING-CALIBRATION.md`), calibración con alumnos reales
  (dossieres D/E), audio humano real (TTS como proxy), **F6.3 (Contexto/Transfer
  libre)** — aplazado por el plan a la auditoría pedagógica de Speaking/Listening
  (decisión pendiente, no defecto).

## 2. Tarea — batería automática (reproducir, no creer)

Ejecuta cada gate y anota el resultado real. La **cita de comando** queda en el
dossier.

### Backend (`cd backend`)
```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
#   claim: 1424 passed
.venv\Scripts\python.exe -m ruff check .
#   claim: All checks passed!
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict --quality
#   claim: exit 0 (sin huecos empty en niveles con curso)
.venv\Scripts\python.exe -m scripts.content_validation
#   claim: exit 0 (OK=True quality=True)
```

### Raíz
```powershell
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py
#   claim: OK: Release consistency (3.21.0) en todos los orígenes, exit 0
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py
#   claim: OK: Beta V3.0 gate, exit 0
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py
#   claim: exit 0; 0 claves usadas-no-definidas / duplicadas / con en|es vacío
#   (las "sin uso" son candidatas a limpieza, no errores)
```

### Frontend (`cd frontend`)
```powershell
npm test        # claim: vitest 450 passed (57 archivos)
npm run build   # claim: tsc + vite build OK
```

## 3. Verificación de las afirmaciones v3.21 contra el código

Reproduce cada ítem del encabezado de `docs/RELEVO.md` (2026-09-07) en el
código y en tests. Guía de localización:

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| **F1.1** `unit_produced` por alineación secuencial (orden + contigüidad + misma normalización `tokenize`; "get it up" ≠ "get up"; frase en oración larga sí) | `backend/services/phonetics.py` (`unit_produced`, `_contains_run`, `word_alignment`, `tokenize`) y su uso en `domain/vocabulary.py::submit_drill_attempt` | `backend/tests/test_drill_alignment.py`, `test_phonetics.py` |
| **F1.2** acreditación atómica de unidades multi-palabra (invariante por fila `sum(channel_prod) == appearances`) | `domain/vocabulary.py::record_production_text(as_unit=True)` + `repositories/vocabulary.py::record_production` | `test_drill_alignment.py::test_drill_phrase_produced_accredits_atomic_unit`, tests de invariante existentes |
| **F2.1** metadata ASR capturada y taxonomía determinista | `backend/services/stt.py` (`classify_asr_status`, umbrales, `transcribe_with_timing` devuelve `asr_status`/`confidence`) | `backend/tests/test_stt_asr.py` |
| **F2.2** gating de no-penalización (drill/read-aloud/speaking/pronunciación legacy): `asr_status != ok` → sin KO ni fallo, evento `unclear` | `routers/vocabulary.py`, `routers/pronunciation_routes.py`, `routers/speaking_routes.py`, `routers/pronunciation.py` + servicios de dominio; `schemas/*` exponen `asr_status`/`asr_confidence` | `test_stt_asr.py`, tests de endpoints existentes |
| **F2.3** chips re-etiquetados a la verdad ASR + nota permanente | `frontend/src/utils/i18n.ts` (`pron.chip.ok/miss/sub`, `pron.chipsNote`, `asr.*`), `features/pronunciation/PronunciationRoutesPractice.tsx` | vitest de render/paridad i18n |
| **F2.4/F3.4** mensajes de audio no reconocido en flujos directos y estado `unclear` manos-libres | `features/vocabulary/PersonalDictionary.tsx` (WordDrill), `features/speaking/SpeakingRoutesPractice.tsx`, `components/MicButton.tsx`, `features/conversation/ConversationVoiceButton.tsx`, `hooks/useHandsFree.ts`, `components/HandsFreeToggle.tsx`, `styles/legacy.css` (`--unclear`), `i18n.ts` (`mic.noSpeech`) | vitest de componentes + paridad |
| **F3.1** `DEFAULT_MODEL` fuente única | `backend/routers/models.py` (`default_model` de `config.DEFAULT_MODEL`), `frontend/src/utils/models.ts` (`resolveDefaultChatModel`/`fallbackChatModel`), consumidores `hooks/useChat.ts`, `features/conversation/ConversationGuidedChat.tsx`, `features/speaking/SpeakingRolePlay.tsx` (sin constantes locales) | `backend/tests/test_models.py::test_models_exposes_default_model`, `frontend/src/utils/models.test.ts` |
| **F3.2** comentario `ADMIN_PIN` fail-closed (sin cambio de comportamiento) | `backend/config.py` | — (documentación) |
| **F3.3** cronómetro + auto-stop 120 s y red de seguridad backend de duración (400) | `frontend/src/hooks/useRecordingSession.ts` + integraciones (Speaking/pronunciación/WordDrill/voz/assessment); `backend/services/stt.py::exceeds_max_duration` + routers de intento | `useRecordingSession.test.tsx`, `backend/tests/test_stt_asr.py` (duración 400 en drill/readaloud/speaking) |
| **F4** semántica de superficie Speaking (título del modo + competencia real en pies de stats, sin puntuación única) | `features/speaking/SpeakingRoutesPractice.tsx` (`speakingConfigFor`), `features/routes/QuizRoutePage.tsx` (`statsCompetenceKey`), `i18n.ts` (`speaking.surfaceTitle*`, `speaking.competence*`) | `frontend/src/features/speaking/speakingSurfaceConfig.test.ts`, vitest de QuizRoutePage |
| **F5.1** matriz por ítem (pura, sin migrar columnas) | `backend/services/lexicon.py` (`item_competence_matrix`, `production_channels`, `_spaced_production`); `summary` con contadores | `backend/tests/test_lexicon.py` |
| **F5.2** exposición en API y diccionario | `schemas/vocabulary.py` (`LexicalCompetence`, `LexiconSummary`, `LexicalItemOut.competence`), `domain/vocabulary.py::get_lexicon`, router `GET /api/vocabulary/lexicon`; `frontend/src/types/api.ts`, `features/vocabulary/PersonalDictionary.tsx` (fila de stats) | `test_vocabulary.py::test_lexicon_endpoint_exposes_competence_matrix`, vitest PersonalDictionary |
| **F5.3** Transfer Gap para FSRS por objetivo | `backend/services/fsrs.py::why_for_lexicon(group_produced)`, `backend/domain/academy.py::sync_fsrs_cards` (producción por objetivo) | `backend/tests/test_fsrs_transfer_gap.py` |
| **F6.1** paso Sentence determinista sin LLM (banco del nivel o plantilla; `passed = produced AND phrase_ok`; servidor re-deriva la frase) | `services/pronunciation_routes.py::sentence_context_for`, `domain/vocabulary.py::get_sentence_context`/`submit_sentence_attempt`, `routers/vocabulary.py` (`GET /api/vocabulary/drill/sentence-context`, `POST /api/vocabulary/drill/sentence-attempt`), `schemas/vocabulary.py` (`SentenceContextOut`/`SentenceAttemptOut`); UI escalera Recall→Sentence en `PersonalDictionary.tsx::WordDrill` + `api/vocabulary.ts` | `backend/tests/test_drill_ladder.py`, `frontend` vitest `api/vocabulary.test.ts` + `PersonalDictionary.test.tsx` |
| **F6.2** graduación espaciada (una producción del día no elimina; salida con 2 días de éxito de drill u otra señal espaciada; oculta hoy si ya superada) | `backend/services/lexicon.py` (`drill_ok_days`, `DRILL_SPACED_OK_DAYS`, `drill_candidates(ok_days, today)`, `_is_pending_drill_candidate`), `domain/vocabulary.py::get_drill_candidates` (lee `learning_events` tipo `drill:<word>[:sentence]:ok`) | `test_drill_ladder.py` (F6.2 puro + endpoint), `test_lexicon.py`, `test_vocabulary.py` |

**Reglas del juego (premisas):** el micro-drill (palabra y frase) y el
micro-review no declaran dominio (D5/E3); señal ≠ evidencia — ningún cambio de
F1–F6 crea evidencia curricular ni FSRS; el invariante de trazabilidad por fila
se conserva y se testea con unidades multi-palabra; toda clasificación nueva
(ASR, matriz léxica, produced) es determinista y con tests puros; ninguna
pantalla/página nueva top-level (la Fase 6 vive en la tarjeta existente del
drill).

## 4. Puntos de atención (comprobar explícitamente)

- **Fronteras del cierre**: F6.3 aplazado (sin código); deuda de modelo V20-17
  documentada en `services/lexicon.py` (`appearances`→`production_count` y
  `exposure_count`/`exposure_days` como migración futura). No debe haber otras
  deudas no listadas en `PLAN.md`/`RELEVO.md`.
- **Árbol git**: limpio en `14a2f7f`; `release-notes-v3.21.0.md` versionada;
  `docs/audit/generated/*` al día (i18n regenerado en el commit de release).
- **Gating ASR honesto**: con `asr_status != ok` la UI nunca debe mostrar "no lo
  dijiste" en rojo; el evento de actividad debe ser `unclear`, nunca `ko` (en
  los flujos con evento).
- **Espaciado del drill**: verificar que `GET /api/vocabulary/drill/candidates`
  devuelve candidatas que YA se produjeron hoy/una vez (siguen pendientes) y que
  el mensaje de éxito del frontend no promete "salir de la lista" tras una sola
  producción.
- **i18n**: parity es/en (checker exit 0; los "sin uso" son candidatas a
  limpieza, no errores).
- Busca **roturas de premisas**: si un hallazgo contradice `PREMISAS.md` o la
  CONSTITUCIÓN, es severidad alta aunque el gate pase.

## 5. Criterios de aceptación del auditor

1. Cada claim de la sección 2 y 3 queda **reproducido** o marcado *no
   reproducible* con su causa (comando + resultado real).
2. Ningún hallazgo de severidad alta sin acción; los medios/bajos quedan
   registrados con recomendación y estado.
3. Veredicto final en formato del proyecto: **APROBADO / APROBADO CON
   OBSERVACIONES / NO APROBADO** + resumen de 2–3 líneas.

## 6. Salida

- Dossier en `docs/audit/` siguiendo `docs/audit/TEMPLATE.md` (alcance, método,
  evidencia, hallazgos, veredicto, "Regenerar / Verificar") — el nombre y la
  consolidación los decide el gerente.
- Informe final con: veredicto, tabla de gates con resultados reales, tabla de
  claims F1–F6 con su test de respaldo, y lista de hallazgos.

## 7. Restricciones

- **Solo lectura** en código/BD de producción. No escribir fuera de `docs/audit/`
  si el gerente autoriza el dossier.
- No ejecutar nada que dependa de Ollama/Whisper/Piper salvo que el gerente lo
  pida (los flujos auditados no los requieren; el LLM real es frontera honesta).
- No instalar dependencias ni lanzar migraciones destructivas. BD de tests =
  temporales (pytest con `tmp_path`).
