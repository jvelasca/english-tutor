# Briefing — Auditoría TOTAL externa (read-only) de v3.46.0

> Fecha: 2026-09-11 · Rol: **auditor externo read-only** (subagente autocontenido).
> Objetivo: reproducir y verificar las afirmaciones de la posición **v3.46.0** y
> que el tramo **V3.43.0 → V3.46.0** (V3.44 *sense-aware* + scoring semántico
> 2.0, V3.45 Traductor de viaje + voz española real, V3.46
> `transfer_condition`) cierra lo que declara sin romper CONSTITUCIÓN, premisas
> ni mecanismos previos. Sigue la metodología de las auditorías externas
> v3.16–v3.43 y la plantilla `docs/audit/TEMPLATE.md`.

## 0. Cómo arrancar (auditor, contexto nuevo)

1. Lee en orden: `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`,
   `docs/RELEVO.md` (solo encabezado + sección 0), `PLAN.md` (estado actual),
   `README.md`, `CHANGELOG.md`, `release-notes-v3.44.0.md`,
   `release-notes-v3.45.0.md`, `release-notes-v3.46.0.md`, el dossier previo
   `docs/audit/P-AUDITORIA-TOTAL-V343.md` y los briefings
   `agentes/v344-sense-aware.md`, `agentes/v345-translator.md` y
   `agentes/v346-transfer-condition.md`.
2. Confirma el punto de partida del repo con:
   ```powershell
   git log --oneline -3
   git status --short          # debe estar limpio (o solo cambios del auditor)
   ```
   La posición es **v3.46.0** (`backend/config.py::VERSION = "3.46.0"`,
   `frontend/package.json` / `package-lock.json` idénticos), commit de release
   `107d8ec` (tag `v3.46.0`, run
   [34578101387](https://github.com/jvelasca/english-tutor/actions/runs/34578101387),
   6/6 jobs en `success`). `git status` limpio.
   > Nota: el commit de release agrupa los incrementos V3.44/V3.45/V3.46 porque
   > ninguno se había commiteado desde v3.43.0 (mismo caso documentado en v3.42.0).
3. Entorno Windows/PowerShell. Backend: Python en `backend\.venv`. Frontend:
   Node en `frontend`. No instalar dependencias; no modificar código fuera de
   `docs/audit/` si el gerente autoriza el dossier.

## 1. Alcance (TOTAL con foco V3.44–V3.46)

La última auditoría externa fue de **V3.43.0** (9,6/10). Este dossier audita los
**tres incrementos posteriores**, que son un solo tramo de evidencia:

- **V3.44 — Lexicón *sense-aware* + scoring semántico 2.0 (P1-01 y P1-02 de la
  auditoría de V3.43.0).**
  - `lexical_unit → sense`: el contrato de contenido gana `senses`
    (`GENERATOR_VERSION` `1.3.0 → 1.4.0`, regeneración lazy una sola vez) con el
    helper PURO `normalize_senses`; persistencia aditiva `senses_json TEXT NOT
    NULL DEFAULT ''` en `dictionary_entries` **y**
    `dictionary_reverse_entries` (migración idempotente, JSON ilegible → `[]`).
  - Nuevo módulo PURO `services/semantics.py`: `pos_family` (por palabras, no
    subcadenas), `families_from_senses` (con fallback a la `pos` global),
    `unit_positions`, `occurrence_role` (cues FUERTES vs DÉBILES, multi-palabra
    se abstiene) y `semantic_adequacy`.
  - Scoring: `score_transfer_attempt(word, text, *, pos="", senses=())` devuelve
    `adequacy` ∈ `fit`/`suspect`/`incorrect`/`unknown`; `incorrect` →
    `semantic_mismatch` es el **ÚNICO** valor que bloquea el clean success,
    `suspect` → `semantic_doubt` es **advisory**, sin sentidos/POS → `unknown`
    (nunca bloquea). `passed`/`lexical_transfer`/`semantic_fit` conservan su
    semántica y `score_write_attempt` mantiene su contrato exacto (4 claves).
- **V3.45 — Traductor de viaje práctico + voz española real.**
  - Voz por defecto por idioma: `SPANISH_VOICE = "es_ES-davefx-medium"`,
    `DEFAULT_VOICES = {"en": PIPER_VOICE, "es": SPANISH_VOICE}`, pura
    `default_voice_for(language)`; `resolve_voice(prefs, language)` prioriza
    preferencia del idioma → default del idioma instalado → primera instalada del
    idioma → fallback global (con `en` idéntico al histórico).
  - `ensure_voice_for_language(language) -> bool` (no-op si ya hay voz del
    idioma; descarga el default del catálogo curado; `False` sin red/disco con
    caché negativa de 300 s; **nunca lanza**) ejecutada en `/api/tts`;
    `download_models.py` instala también la voz española.
  - Modo Conversación (frontend): `useVoiceTurn.ts` (MediaRecorder +
    AnalyserNode + VAD + transcripción; helper PURO `nextTurnVadState`),
    `BigMicButton.tsx`, `ConversationPanel.tsx`, `ConversationTranslator.tsx`;
    `TranslatorScreen` con dos pestañas (Conversación / Escribir intacto). El
    Traductor sigue siendo **AUXILIAR**: no registra evidencia ni toca FSRS.
- **V3.46 — Condición de recuperación en la transferencia (`transfer_condition`,
  P1-03 de la auditoría de V3.43.0).**
  - Taxonomía `prompted` > `cued_context` > `open_context` > `free_choice` >
    `naturally_emergent`; `SERVABLE_CONDITIONS`, `UNSCAFFOLDED_CONDITIONS`,
    `REQUIRED_TARGET_CONDITIONS`, `CONDITION_INSTRUCTIONS`,
    `normalize_condition` y la escalera PURA `condition_for_state`.
  - La condición la **DERIVA el servidor** del resumen del ledger (el cliente no
    la declara); persistencia aditiva `transfer_condition TEXT NOT NULL DEFAULT
    ''` en `learning_evidence` (ALTER idempotente) con plumbing en
    `record_evidence`/lote/`list_evidence`/SELECT de detalle.
  - `context_signals` agrega `transfer_conditions`, `success_conditions` y
    `unscaffolded_clean_successes`; `transfer_demonstrated` exige **≥1 éxito
    limpio NO andamiado** además de 2 contextos limpios con diversidad real.
    Un intento de `open_context` que no usa la unidad NO se registra
    (`required_target=false`).

- **NO se audita** (frontera honesta): ejecución física en dispositivos
  (`docs/audit/G-DEVICES.md`), variabilidad LLM con Ollama real (el LLM genera
  contenido cacheado, no decide evidencia), calidad acústica de las voces Piper
  más allá de que el id instalado sea el correcto, calibración con alumnos
  reales, y los P1/P2 diferidos a V3.47: **CEFR/`difficulty_vector` del contexto**
  (único P1 de V3.43.0 aún abierto), Context Bank 2.0, diversidad 2.0, semantic
  appropriateness, transfer_state enriquecido
  (`confidence`/`evidence_count`/`recency`) y `expected_learning_value` /
  Adaptive Planner 2.0.

## 2. Tarea — batería automática (reproducir, no creer)

Ejecuta cada gate y anota el resultado real. La **cita de comando** queda en el
dossier.

### Backend (`cd backend`)
```powershell
.venv\Scripts\python.exe -m pytest -q
#   claim: 2047 passed, 1 warning
.venv\Scripts\python.exe -m ruff check .
#   claim: All checks passed!
```

### Raíz
```powershell
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py
#   claim: OK: Release consistency (3.46.0) en todos los orígenes, exit 0
```

### Frontend (`cd frontend`)
```powershell
npx vitest run
#   claim: 72 ficheros / 623 tests passed
npx tsc --noEmit
#   claim: sin errores
npm run build
#   claim: tsc + vite build OK
```

## 3. Verificación de las afirmaciones contra el código

Reproduce cada ítem del encabezado de `docs/RELEVO.md` (2026-09-11) y de las
tres notas de release en el código y en tests. Guía de localización:

### V3.44 — *sense-aware* + scoring 2.0

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| `GENERATOR_VERSION` 1.4.0 y prompts piden `senses` | `services/dictionary_content.py` (`GENERATOR_VERSION`, `_SYSTEM_PROMPT`/`_REVERSE_SYSTEM_PROMPT`) | `test_senses_v344.py::test_prompts_declare_senses_and_version_is_bumped` |
| `normalize_senses` puro (pos canónico, dedupe, tope `MAX_SENSES=4`, `MAX_GLOSS_CHARS`, orden estable, nunca invalida contenido) | `services/dictionary_content.py::normalize_senses` | `test_senses_v344.py` |
| Migración aditiva idempotente `senses_json` en AMBAS tablas, JSON ilegible → `[]` | `repositories/db.py` (ALTER + `PRAGMA table_info`), `repositories/dictionary.py` (`_encode_senses`/decode) | `test_senses_v344.py` (round-trip, corrupción tolerada, migración con BD legacy) |
| Módulo PURO `services/semantics.py` (`pos_family` por palabras, `families_from_senses` con fallback, `occurrence_role`, `semantic_adequacy`) | `services/semantics.py` | `test_senses_v344.py`, `test_transfer_v344.py` |
| `adequacy` ∈ `fit`/`suspect`/`incorrect`/`unknown`; solo `incorrect` bloquea clean success; `unknown` nunca bloquea | `services/lexicon.py::score_transfer_attempt`; `services/evidence.py::context_signals` | `test_transfer_v344.py` |
| `score_write_attempt` contrato exacto (4 claves) | `services/lexicon.py` | tests de escritura existentes |
| Paridad pura↔SQL del resumen | `services/evidence.py` reutilizado por `repositories/evidence.py::summarize_by_target` | `test_transfer_v344.py` |

### V3.45 — Traductor + voz española

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| `SPANISH_VOICE`/`DEFAULT_VOICES`/`default_voice_for` pura | `config.py`, `services/tts.py` | `test_voices.py` |
| `resolve_voice` prioriza default del idioma; con `en` idéntico al histórico | `services/tts.py::resolve_voice` | `test_voices.py` |
| `ensure_voice_for_language` (no-op / descarga / `False` + caché negativa / fuera de catálogo / nunca lanza) | `services/tts.py` | `test_voices.py` |
| `/api/tts` auto-descarga antes de resolver; `download_models.py` instala la española | `routers/voz.py`, `download_models.py` | `test_voices.py` |
| `VoicesResponse.defaults` (aditivo) | `schemas/voices.py`, `routers/voices.py` | `test_voices.py` |
| VAD puro `nextTurnVadState` (cierra por silencio tras habla mínima; descarta picos) | `frontend/src/features/translator/useVoiceTurn.ts` | `useVoiceTurn.test.ts` |
| Modo Conversación (dos paneles, auto-play, «cara a cara», historial) | `ConversationTranslator.tsx`, `ConversationPanel.tsx`, `BigMicButton.tsx`, `TranslatorScreen.tsx` | `ConversationPanel.test.tsx`, `TranslatorScreen.test.tsx` |
| El Traductor NO registra evidencia | ausencia de llamadas a evidencia en `features/translator/*` | revisión de código + tests |

### V3.46 — `transfer_condition`

| Claim | Dónde mirar (código) | Test que lo fija |
|---|---|---|
| Taxonomía + conjuntos (`TRANSFER_CONDITIONS`, `SERVABLE`, `UNSCAFFOLDED`, `REQUIRED_TARGET`) | `services/transfer.py` | `test_transfer_condition_v346.py` |
| `normalize_condition` (desconocido → `""`) y `condition_for_state` (escalera) | `services/transfer.py` | `test_transfer_condition_v346.py` |
| `context_for(..., condition=...)` compone el prompt y expone `condition`/`required_target`/`unscaffolded` | `services/transfer.py` | `test_transfer_condition_v346.py` |
| Persistencia aditiva e idempotente + round-trip en el ledger | `repositories/db.py`, `repositories/evidence.py` | `test_transfer_condition_v346.py` |
| `context_signals` agrega condiciones y `unscaffolded_clean_successes` | `services/evidence.py` | `test_transfer_condition_v346.py` |
| `transfer_demonstrated` exige ≥1 éxito limpio NO andamiado; fallback legacy sin datos de condición | `services/evidence.py::transfer_state`/`_unscaffolded_transfer_ok` | `test_transfer_condition_v346.py`, `test_transfer_v340.py::test_two_distinct_contexts_need_an_unscaffolded_success` |
| La condición la deriva el servidor (el cliente no la declara) y un `open_context` sin la unidad no se registra | `domain/vocabulary.py::_transfer_condition_for`, `get_transfer_context`, `submit_transfer_attempt` | `test_transfer_condition_v346.py` (endpoints) |
| Contratos aditivos `condition`/`required_target`/`unscaffolded` | `schemas/vocabulary.py`, `frontend/src/types/api.ts` | `wordDrill.test.tsx` (+2) |
| UI: condición visible y aviso neutro `transferNotRequired` | `wordDrillSteps.tsx`, `wordDrill.tsx`, `utils/i18n.ts` | `wordDrill.test.tsx` |

**Reglas del juego (premisas):** el LLM **genera contenido** (senses), **nunca
decide evidencia** (premisa 21); el scoring semántico sigue siendo DETERMINISTA;
la condición de recuperación la deriva el servidor del ledger, no el cliente ni
el LLM; `support_level` NO se toca (`spontaneous` sigue describiendo el andamiaje
de la ACTIVIDAD); contratos HTTP **estrictamente aditivos** (`passed`,
`lexical_transfer`, `semantic_fit`, `adequacy`, `transfer`, `transfer_state`
conservan semántica); migraciones **aditivas e idempotentes**, sin backfill ni
borrado; paridad pura↔SQL del resumen de evidencia.

## 4. Puntos de atención (comprobar explícitamente)

- **No regresión en resúmenes legacy.** Sin datos de `transfer_condition`
  (intentos previos a V3.46 o resumen parcial), `transfer_state` debe aplicar la
  regla de V3.43 y **no** degradar estados ya alcanzados. Igual con
  `senses_json = ''` (→ `[]`): el scoring debe caer a la `pos` global y nunca
  bloquear por falta de datos (`unknown`).
- **Clean success.** Solo `semantic_mismatch` (de `adequacy="incorrect"`) bloquea
  el clean success; `semantic_doubt` (de `suspect`) NO. Comprobar que
  `transfer`/`transfer_state` avanzan con `semantic_doubt` y no con
  `semantic_mismatch`.
- **Endurecimiento de `transfer_demonstrated`.** Un éxito solo en
  `prompted`/`cued_context` NO debe declarar transferencia; el mismo éxito en
  `open_context`/`free_choice`/`naturally_emergent` sí. Verificar que
  `condition_for_state` sirve `cued_context` en `emerging` (paridad V3.43) y
  `open_context` desde `contextualized`.
- **`open_context` sin la unidad.** No debe registrar evidencia ni mostrar el
  aviso de objetivo ausente (`required_target=false`), sino un mensaje neutro.
- **Voz española.** Con la voz del idioma instalada, `resolve_voice("es")` NUNCA
  debe devolver una voz `en_*`; sin ella, `ensure_voice_for_language` degrada sin
  lanzar (nunca 500 por este motivo). Comprobar la caché negativa para no
  reintentar la descarga en cada petición.
- **`GENERATOR_VERSION`.** Debe ser `1.4.0` y provocar una única regeneración
  lazy; contenido antiguo (`1.3.0`/legacy) se regenera sin romper.
- **Árbol git**: limpio en el commit de release; `release-notes-v3.44.0.md`,
  `v3.45.0.md` y `v3.46.0.md` versionadas; versión consistente en
  `config.py`/`package.json`/`package-lock.json`/`CHANGELOG`/`README`/`PLAN`.
- Busca **roturas de premisas**: si un hallazgo contradice `PREMISAS.md` o la
  CONSTITUCIÓN, es severidad alta aunque el gate pase.

## 5. Criterios de aceptación del auditor

1. Cada claim de las secciones 2 y 3 queda **reproducido** o marcado *no
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
  claims (V3.44/V3.45/V3.46) con su test de respaldo, y lista de hallazgos.

## 7. Restricciones

- **Solo lectura** en código/BD de producción. No escribir fuera de `docs/audit/`
  si el gerente autoriza el dossier.
- No ejecutar nada que dependa de Ollama/Whisper/Piper salvo que el gerente lo
  pida (los flujos auditados usan contenido cacheado; el LLM real es frontera
  honesta).
- No instalar dependencias ni lanzar migraciones destructivas. BD de tests =
  temporales (pytest con `tmp_path`).
