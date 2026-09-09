# v3.27.0 — Listening Engine 4.0 (Fase 1): micro-flujo por ítem, política de fases en backend y perfil auditivo visible

**V3.27 implementa la Fase 1 de la especificación `docs/LISTENING_ENGINE_4.0.md`
(vía `docs/PLAN-V327-LISTENING-ENGINE-4.md`): cada frase/audio del corpus gana
un micro-flujo interno (Pre → While1 → While2 → Post → shadowing), el backend se
convierte en la fuente única de la política pedagógica (`flow` +
`transcript_policy` viajan en cada pregunta), la evidencia de cada intento se
amplía con 5 columnas nuevas y el diagnóstico expone un perfil auditivo (casos
A-D) que se muestra en la UI y prioriza el siguiente ítem por capa.
Verificación íntegra local: backend pytest **1647 passed** + ruff; frontend
vitest **472 passed** (59 archivos) + `tsc --noEmit` OK;
`check_release_consistency` 3.27.0 exit 0.**

## Qué cambia

### Política de fases: decisión de arquitectura (§3.1 del plan)

El análisis comparó tres opciones (backend expone y frontend ejecuta; todo en
frontend; híbrido con contrato explícito). **Decisión: el backend es la fuente
única de la política pedagógica.** El payload de `next_question` incluye:

- **`flow`**: lista de pasos del micro-flujo del ítem (`stage`
  `pre|while1|while2|post|shadowing`, `task`, `transcript_state_inicial`
  `hidden|partial|full`, `allow_skip`, `requires_audio`). Los ítems de
  producción (dictation/shadowing) llegan con un único paso `while2`
  (`task=production`) y conservan su tarea directa.
- **`transcript_policy`**: contrato de revelado (`revelation`
  `hidden_until_post`/`on_first_fail`/`never_before_post` según CEFR y capa,
  `max_attempts_per_stage`, `allow_manual_reveal`, `shadowing_optional`).

Esto garantiza que la métrica "precisión con apoyo decreciente" no se contamina:
el frontend no tiene constantes pedagógicas propias y el `transcript_used` de
cada intento refleja realmente lo que el alumno vio. Sin `flow` (llamadores
antiguos, sesiones de nivel/drill) la pantalla conserva su comportamiento
anterior — todo el contrato es opcional y backward compatible.

### Micro-flujo frontend como máquina de presentación

Nuevo módulo puro `frontend/src/features/listening/microFlow.ts` que ejecuta la
política servida por el backend: `initialFlow`, `advanceToNext`, `revealFull`
(respeta `allow_manual_reveal`), `completeStageWithAnswer` (reintentos según
`max_attempts_per_stage` y apoyo `on_first_fail`), `completeShadowing`/
`skipShadowingStage` (respetan `allow_skip`), sin mutación de estado. En
`ListeningPractice.tsx` las tarjetas Pre/While1/Shadowing se intercalan con la
tarjeta de audio (siempre disponible); la pregunta solo se muestra en
While2/Post, el fallo con reintentos no filtra el guion si la política no
concede apoyo, y `ActivityResult` ofrece continuar/reintentar según la etapa.
Los metadatos de cada intento (`layer`, `speed_used`, `stage`,
`transcript_used`, `segments_replayed`) se envían en `answer`/`dictation`/
`shadowing` sin romper el envío anterior.

### Perfil auditivo visible en la UI (objetivo 5)

Nuevo módulo puro `backend/services/auditory_profile.py`: a partir de los
agregados del diagnóstico detecta los casos pedagógicos **A-D** (bottom-up /
comprensión / top-down / cadena hablada), con `PROFILE_MIN_ATTEMPTS = 3` y
umbrales centralizados (70/85/60). El diagnóstico expone `profile` y la tarjeta
`AuditoryProfileCard` lo muestra de forma persistente y **no bloqueante** en el
panel de Listening con tres estados: sin perfil (no renderiza) → muestra
insuficiente (`needsMore`) → intervención activa (badge de capa +
recomendación i18n). Cuando el perfil indica una capa con muestra suficiente,
`next_question` la usa para priorizar el siguiente ítem
(`pick_next_question(layer=...)`, sin saltar niveles ni romper la selección
existente).

### Evidencia ampliada (5 columnas en `listening_attempts`)

Migración idempotente que añade `layer`, `speed_used`, `stage`,
`transcript_used`, `segments_replayed`; `submit_answer`/`submit_production`
las persisten (la capa se deriva del ítem en backend como fuente de verdad);
`list_attempts`, schemas, routers y los tipos/API del frontend las propagan de
forma opcional. Los agregados y gates existentes leen las filas con las columnas
nuevas sin cambios.

## Técnica

- Backend (versión de app `3.26.0 → 3.27.0`, fuente única `backend/config.py`):
  - `services/listening_flow.py` (nuevo, puro): `_POLICY_BY_LEVEL`,
    `_production_flow`/`_receptive_flow`, `build_item_flow`,
    `flow_for_question` (aplica overrides del perfil auditivo).
  - `services/auditory_profile.py` (nuevo, puro): casos A-D,
    `intervention_label`, `auditory_profile` con `needs_min_attempts`.
  - `services/listening.py`: `pick_next_question(..., layer=None)`.
  - `domain/listening.py`: persistencia de los 5 campos en
    `submit_answer`/`submit_production`; `next_question` sirve `flow`/
    `transcript_policy` y aplica la capa recomendada; `get_diagnostic`
    expone `auditory_profile`.
  - `repositories/db.py` (migración idempotente) y
    `repositories/listening.py` (`record_attempt` con kwargs opcionales,
    `list_attempts` con las columnas nuevas).
  - `schemas/listening.py` y `routers/listening.py`: contrato opcional.
- Frontend: `types/api.ts` (tipos espejo de `flow`/`transcript_policy`/
  `profile`/metadatos), `api/listening.ts` (opts de apoyo en answer/dictation/
  shadowing), `features/listening/microFlow.ts` (+ `.test.ts`),
  `AuditoryProfileCard.tsx` (+ `.test.tsx`), integración en
  `ListeningPractice.tsx`, i18n es/en (`listening.flow.*`,
  `listening.layer.*`, `listening.profile.*`).
- Docs: `PLAN.md`, `CHANGELOG.md` (`[3.27.0]`), `README.md`, `docs/RELEVO.md`,
  especificación `docs/LISTENING_ENGINE_4.0.md`, plan
  `docs/PLAN-V327-LISTENING-ENGINE-4.md`.

## Tests

- Backend: **1647 pytest en verde** — incluye los nuevos
  `test_listening_attempts_v327.py` (migración idempotente + persistencia +
  integración de endpoints), `test_listening_flow.py` (contrato y barrido
  determinista del banco completo), `test_auditory_profile.py` (casos A-D y
  precedencia) y `test_listening_selector_layer_v327.py` (selección por capa)
  + `ruff check .` limpio. Goldens en verde (la evidencia ampliada no altera
  gates).
- Frontend: vitest **472 passed** (59 archivos); `tsc --noEmit` OK.
- `scripts/check_release_consistency.py` exit 0 (3.27.0).

## Fuera de alcance (Fase 2 de la especificación, deuda documentada)

- Reproductor rico (AudioController de la spec §6.4: karaoke, control de
  segmentos): se usan los controles actuales (play, variante slow/normal/fast,
  replay ya contado).
- Calibración de los umbrales del perfil auditivo (70/85/60) y de la política
  por nivel con datos reales de uso.
- Autoría de ítems para la capa recognition (deuda ya documentada en V3.26).
