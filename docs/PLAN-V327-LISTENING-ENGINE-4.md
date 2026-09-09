# PLAN V3.27 — LISTENING ENGINE 4.0 (Fase 1: micro-flujo por ítem + evidencia ampliada + perfil auditivo)

> Plan técnico derivado de la especificación aprobada `docs/LISTENING_ENGINE_4.0.md` (§14 hoja de ruta, Fase 1).
> Base: freeze arquitectónico V3.26.0 (`backend/config.py:20` → `VERSION = "3.26.0"`).
> Alcance: solo Fase 1. Las Fases 2-4 (AudioController rico, cloze `task_type`, karaoke, contenido multi-voz) quedan fuera y se planificarán después de cerrar esta fase.
> Estado: borrador para revisión antes de ejecutar.

---

## 1. Objetivo

Convertir la práctica de listening actual (audio → pregunta → respuesta → diagnóstico) en un **micro-flujo pedagógico por ítem** con estados Pre/While/Post y **evidencia ampliada por intento**, manteniendo intactos el Evidence Graph, el gate de ruta, la certificación MASTERED y el ledger `vocabulary_events` (reglas de freeze de `docs/LISTENING_ENGINE_4.0.md` §13).

Al final de V3.27 (Fase 1), el sistema debe ser capaz de:

1. Servir cada ítem con una **política de fases y de transcripción** (`hidden → partial → full`) derivada de la capa del ítem y del nivel del alumno.
2. Persistir por intento **qué apoyo se usó** (`speed_used`, `stage`, `transcript_used`, `segments_replayed`, `layer`) para poder medir "precisión con apoyo decreciente" (principio rector de la spec §2.3).
3. Calcular un **perfil auditivo** (casos A-D de la spec §5) a partir del diagnóstico existente y exponer la **intervención recomendada**.
4. Usar ese perfil para **priorizar la siguiente pregunta por capa/operación cognitiva** dentro del nivel de trabajo (spec §9).
5. **Mostrar el perfil auditivo en la UI** (decisión de alcance): una tarjeta visible en la pantalla de listening que indique la capa de trabajo actual y la intervención recomendada (si hay muestra suficiente), sin bloquear la práctica. El perfil no queda como dato interno del diagnóstico.

## 2. Fuera de alcance de la Fase 1

- Cloze/dictado parcial como tarea (`task_type="cloze"`) → **Fase 2**.
- `AudioController` rico (seek/loop segmento/bucle A-B/rate en vivo) y playback de la grabación en shadowing → **Fase 2**.
- Sincronización por palabra / karaoke (`word_alignment_proxy`) → **Fase 3**.
- Asignación multi-voz Piper por ítem y contenido de audio humano → **Fase 4**.
- Lección orquestada multi-ítem (Pre/While/Post sobre pasaje largo) → fuera del roadmap inmediato (spec §6.1).
- Cualquier cambio en Student Model, Evidence Graph, SQLite, React, FastAPI o nuevo LLM (spec §13).

## 3. Decisiones técnicas adoptadas (respuestas a las preguntas abiertas de la spec §16)

| Pregunta de la spec | Decisión para V3.27 (Fase 1) |
|---|---|
| ¿Cloze como skill o como `task_type`? | Como `task_type` (cuando llegue en Fase 2). No se añade a `LISTENING_SUBSKILLS`. |
| ¿Dónde vive la lógica de fases? | **Decidido tras análisis (§3.1): el backend es la fuente única de la política pedagógica y la expone en el payload del ítem; el frontend ejecuta una máquina de estados de presentación con los parámetros recibidos (sin constantes pedagógicas propias).** |
| ¿El micro-flujo se activa para todos los niveles? | Despliegue por nivel: activo para todos los niveles, pero la política de transcript es más permisiva en A1 (revela antes) y más estricta en B2+ (spec §6.3). |
| ¿Capas/umbrales? | Constantes configurables en el módulo nuevo (valores por defecto de la spec §5, a calibrar): recognition baja < 70, comprehension alta ≥ 85, inference baja < 60, condición natural/connected < 60 con clear ≥ 80. |

### 3.1 Decisión de arquitectura: dónde vive la política de fases (análisis)

**Pregunta**: ¿quién decide el orden de pasos (Pre/While1/While2/Post/shadowing) y la política de transcripción (`hidden → partial → full`), el backend o el frontend?

**Opciones valoradas contra la arquitectura real:**

| Opción | Descripción | Ventajas | Inconvenientes |
|---|---|---|---|
| A | Backend expone la política; frontend ejecuta la máquina | Decisiones pedagógicas junto al nivel CEFR y el perfil (que ya viven en backend); testeable con pytest sobre los 513 ítems (barrido determinista); el vocabulario de `stage`/`transcript_used` que se persiste lo define el backend → evidencia fiable | Ninguno relevante: la política viaja en el payload de la pregunta, así que **no añade round-trips** entre fases |
| B | Todo en frontend (reglas pedagógicas en el cliente) | Menos cambios backend; iteración de UX sin desplegar backend | Duplica en TS el mapa skill→capa y las reglas por nivel (riesgo de divergencia); `stage`/`transcript_used` los inventa el cliente → contamina la métrica "precisión con apoyo decreciente"; el perfil del alumno no está en el cliente (exigiría re-sincronizar constantes con cada diagnóstico) |
| C | Híbrido con contrato explícito | El backend envía no solo los pasos, sino los parámetros que el frontend necesita (`max_attempts_per_stage`, `revelation`, `allow_manual_reveal`, `allow_skip`) | Es la opción A llevada al detalle: exige definir bien el contrato del payload |

**Decisión: opción A con el contrato de la opción C.**

- El backend decide y expone por ítem, en `_public()` (`backend/domain/listening.py:128`), un payload con `flow` y `transcript_policy` (módulo puro `listening_flow.py`, §4.5). El frontend **no contiene constantes pedagógicas** (ni umbrales de nivel, ni mapa skill→capa, ni reglas de revelado): solo lee el payload y ejecuta la transición de UI (`microFlow.ts`, §5.3).
- Justificación de que no hay coste de red: el micro-flujo avanza **sin llamadas extra**; todas las decisiones para el ítem completo se sirven de una vez al cargar la pregunta. Cada respuesta (POST answer/dictation/shadowing) solo reenvía los metadatos `stage`/`transcript_used`/`speed_used`/`segments_replayed`, cuyos valores válidos son exactamente los que la política declaró.
- La evidencia "precisión con apoyo decreciente" (principio rector, spec §2.3) depende de que `transcript_used` sea fiable: al ser el backend quien fija cuándo se permite revelar, el alumno no puede ver el transcript antes de tiempo (lo que sí podría ocurrir si la regla fuera local y editable en el cliente).
- El "modo rápido" heredado se conserva porque cada paso declara `allow_skip`; el frontend solo ofrece el salto si el paso lo permite.

Contrato del payload expuesto al cliente (fijado aquí; lo implementa §4.5):

```
flow: [ { stage, task, transcript_state_inicial, allow_skip }, ... ]
transcript_policy: {
  revelation: "on_first_fail" | "on_second_fail" | "on_finish" | "never_before_post",
  max_attempts_per_stage: int,
  allow_manual_reveal: bool,
  shadowing_optional: bool
}
```


## 4. Backend — cambios y orden de ejecución

Todas las extensiones son **aditivas y retrocompatibles**. Orden propuesto (cada punto es un commit verificable):

### 4.1 Migración idempotente de `listening_attempts`

Archivo: `backend/repositories/db.py` (junto a las migraciones existentes de `listening_attempts`, ~líneas 909-951).

Añadir, con el mismo patrón `PRAGMA table_info` → `ALTER TABLE ... ADD COLUMN`:

| Columna | Tipo | Default | Semántica |
|---|---|---|---|
| `layer` | TEXT | `''` | Snapshot de la capa del skill (`recognition`/`comprehension`/`inference` o vacío) en el momento del intento |
| `speed_used` | TEXT | `'normal'` | Variante de la escalera usada (`slow`/`normal`/`fast`) |
| `stage` | TEXT | `''` | Fase del micro-flujo en que se produjo el intento (`pre`/`while1`/`while2`/`post`/`shadowing`; vacío en intentos legacy) |
| `transcript_used` | TEXT | `''` | Estado de transcripción con el que se respondió (`hidden`/`partial`/`full`; `cloze` queda reservado para Fase 2; vacío en legacy) |
| `segments_replayed` | INTEGER | `0` | Fragmentos en bucle usados antes de responder (Fase 1: 0 salvo el contador de reproducciones completo ya existente `replay_count`) |

Sin migración de datos (los intentos existentes conservan los defaults). Índice nuevo opcional: `idx_listening_attempts_layer` solo si el diagnóstico por capa sobre SQL lo justifica (no se prevé: el diagnóstico agrega en Python). El número de columnas nuevas queda **fijado en 5** (confirmado en la revisión de alcance); cualquier campo adicional futuro (p. ej. para cloze en Fase 2) se añadirá con el mismo patrón aditivo.

Aceptación: arranque idempotente (2ª ejecución sin errores); `test_store_isolation`/`test_store_append_only` verdes.

### 4.2 Repositorio

Archivo: `backend/repositories/listening.py`.

- `record_attempt(...)` (~líneas 13-57): añadir kwargs con default (`layer=""`, `speed_used="normal"`, `stage=""`, `transcript_used=""`, `segments_replayed=0`) e incluir las columnas en el `INSERT`.
- `list_attempts(...)` (~líneas 60-73): añadir las columnas al `SELECT` para que el diagnóstico las lea.

Aceptación: los flujos MCQ/producción sin los nuevos kwargs siguen funcionando (retrocompatibilidad).

### 4.3 Schemas

Archivo: `backend/schemas/listening.py`.

- `ListeningAnswerRequest` (~línea 56): añadir campos opcionales `layer: str = ""`, `speed_used: str = "normal"`, `stage: str = ""`, `transcript_used: str = ""`, `segments_replayed: int = 0`.
- `ListeningProductionRequest` (~línea 73): añadir los mismos campos opcionales (`stage`, `transcript_used`, `speed_used`).
- `ListeningQuestion` (~línea 15): añadir `flow: list[dict]` y `transcript_policy: dict` (ver 4.5) con defaults vacíos para no romper consumidores antiguos.
- `ListeningDiagnostic`: añadir un bloque `profile: dict` (ver 4.6) opcional.

### 4.4 Domain

Archivo: `backend/domain/listening.py`.

- `submit_answer(...)` (~línea 210): calcular `layer = skill_layer(question.get("skill",""))` (import de `services.listening`), pasar los campos nuevos a `record_attempt`. `layer` se **persiste**, aunque el cliente no lo envíe (fuente de verdad en backend).
- `submit_production(...)` (~línea 249): igual (persistir `layer` de su skill; en producción el layer es `None`/vacío).
- `next_question(...)` (~línea 147) y el modo `_public(...)` (~línea 128): enriquecer la respuesta con `flow` y `transcript_policy` del módulo nuevo (4.5).

### 4.5 Nuevo módulo puro `backend/services/listening_flow.py`

Motor de política de fases. Funciones puras (sin I/O), testables:

```python
# Constantes de la política (defaults a calibrar; reutilizan LEVEL_ORDER y skill_layer).
FLOW_STAGES = ("pre", "while1", "while2", "post", "shadowing")
REVELATION_MODES = ("on_first_fail", "on_second_fail", "on_finish", "never_before_post")

def transcript_policy(level: str, layer: str | None) -> dict:
    """Política de transcripción por nivel/capa (contrato §3.1). Devuelve:
    {revelation, max_attempts_per_stage, allow_manual_reveal, shadowing_optional}.
    Ej. A1: revelation="on_first_fail", max_attempts=2, allow_manual_reveal=True.
    B2+: revelation="never_before_post", max_attempts=1, allow_manual_reveal=False.
    """

def build_item_flow(question: dict) -> list[dict]:
    """Pasos del micro-flujo: [{stage, task, transcript_state_inicial, allow_skip}, ...].
    La tarea de while2 se deriva de la capa del skill (recognition → percepción/
    detalle; comprehension → detalle/orden; inference → intención/actitud).
    Cada paso declara `allow_skip` (modo rápido heredado). Los ítems con skill
    `dictation`/`shadowing` conservan su flujo de producción actual (sin pre/while/post)."""

def flow_for_question(question: dict, perfil: dict | None = None) -> dict:
    """Payload expuesto al cliente (§3.1): `{flow, transcript_policy}` compuesto
    por build_item_flow + transcript_policy, con overrides del perfil auditivo
    (p. ej. shadowing_optional=False si la intervención activa es connected_speech)."""
```

Reglas (spec §6.2 y §6.3), ahora codificadas en el contrato:
- `pre`: solo contexto/topic + chunks a activar; transcript `hidden`; `allow_skip=True`.
- `while1`: escucha global, pregunta de idea general; transcript `hidden`; reintento según `max_attempts_per_stage`.
- `while2`: tarea de proceso según capa; transcript `hidden` (Fase 1 sin cloze: se usa la pregunta nativa del ítem); fallo tras agotar reintentos → pasa a `post` con reveal según `revelation`.
- `post`: reveal `partial` (si hubo fallo) → `full`; toggle manual solo si `allow_manual_reveal`.
- `shadowing`: opcional (`shadowing_optional`); ítems `dictation`/`shadowing` conservan su flujo actual.

Aceptación: tests unitarios sobre ítems de las 6 capas/niveles; ningún ítem del banco rompe el builder (los 513 ítems deben producir un flujo válido); el payload de un ítem A1 y uno B2 difieren según lo esperado (permisividad de transcript).

### 4.6 Nuevo módulo puro `backend/services/auditory_profile.py`

Perfil auditivo + detección de intervención (spec §5). Función principal pura:

```python
PROFILE_MIN_ATTEMPTS = 3          # alineado con RESILIENCE_MIN_ATTEMPTS
R_LOW = 70.0                      # precisión de capa considerada débil
HIGH = 85.0                       # precisión considerada sólida
INF_LOW = 60.0                    # umbral de inferencia
COND_LOW = 60.0                   # condición natural/connected débil
COND_HIGH = 80.0                  # condición clara sólida

def auditory_profile(diagnostic: dict) -> dict:
    """Entra el dict de `listening_diagnostic(...)` (by_layer + resilience +
    subskills) y devuelve:
    {layer: "recognition"|"comprehension"|"inference"|None,
     intervention: "bottom_up_path"|"comprehension_path"|"top_down_path"
                   |"connected_speech_path"|None,
     reason: str, needs_min_attempts: bool}
    con la precedencia D → A → B → C de la spec §5.2 y muestras mínimas."""

def intervention_label(intervention: str) -> str:  # clave i18n para UI
```

Reglas:
- Precedencia: Caso D (condición acústica) primero; luego A (recognition), B (comprehension), C (inference).
- Ninguna capa se declara fuerte/débil con menos de `PROFILE_MIN_ATTEMPTS`.
- La `automaticity` NO participa en el perfil (sigue siendo señal auxiliar; spec §5.2).

Aceptación: tests con diagnósticos sintéticos para los 4 casos + caso sin datos.

### 4.7 Selector por capa

Archivo: `backend/services/listening.py`, `pick_next_question(...)` (~línea 1619).

- Añadir parámetro opcional `layer: str | None = None` (retrocompatible): cuando viene, filtrar el pool del nivel de trabajo a ítems cuya `skill_layer(skill) == layer` **y** que realicen su sub-destreza (`_realizes_subskill`), manteniendo el orden actual (débiles → no vistas → falladas → rotación).
- `backend/domain/listening.py:next_question(...)`: cuando el perfil auditivo de 4.6 indique una capa con suficiente muestra, pasarla al selector.

Aceptación: tests de selección por capa dentro del nivel (no salta de nivel); sin capa el comportamiento es idéntico al actual (los 1538 tests existentes en verde).

### 4.8 Endpoint de diagnóstico

- `backend/routers/listening.py:160` (`GET /api/listening/diagnostic`) y `backend/domain/listening.py` (función de diagnóstico): añadir `profile` al resultado llamando a `auditory_profile(diagnostic)`.
- `backend/schemas/listening.py` `ListeningDiagnostic`: campo `profile: dict`.

### 4.9 Tests backend

Nuevos archivos en `backend/tests/`:
- `test_listening_flow.py`: `transcript_policy` por nivel/capa; `build_item_flow` sobre ítems representativos y sobre todo el banco (barrido determinista); respuesta `flow` en `_public`.
- `test_auditory_profile.py`: casos A/B/C/D, precedencia, mínimos de muestra, perfil vacío.
- `test_listening_attempts_v327.py`: migración de columnas (idempotente), persistencia de los 5 campos nuevos vía `record_attempt`, lectura en `list_attempts`, retrocompatibilidad de kwargs.
- Extensiones de `test_listening_taxonomy.py`/`test_listening.py`: `layer` persistido coincide con `skill_layer(skill)`; `pick_next_question(layer=...)` dentro de nivel.

## 5. Frontend — cambios y orden de ejecución

### 5.1 Tipos

Archivo: `frontend/src/types/api.ts`:
- `ListeningQuestion` (~línea 517): `flow?: ListeningFlowStep[]`, `transcriptPolicy?: Record<string, string>`.
- `ListeningAnswerRequest`/llamadas: campos opcionales `layer?`, `speedUsed?`, `stage?`, `transcriptUsed?`, `segmentsReplayed?`.
- `ListeningDiagnostic` (~línea 1221): `profile?: ListeningAuditoryProfile | null`.

### 5.2 API

Archivo: `frontend/src/api/listening.ts`:
- `submitListeningAnswer(userId, questionId, answerIndex, opts)` con los campos nuevos opcionales.
- `submitListeningDictation`/`submitListeningShadowing(...)`: aceptar `stage`, `transcriptUsed`, `speedUsed`.
- `getListeningQuestion`: el tipo ya lleva `flow`/`transcriptPolicy`.

### 5.3 Máquina de estados del micro-flujo (util puro)

Nuevo archivo `frontend/src/features/listening/microFlow.ts` (mismo patrón que `listeningSession.ts`, testeable). Es una máquina de **presentación**: no contiene umbrales ni reglas pedagógicas; ejecuta el contrato `flow` + `transcript_policy` que llega en la pregunta (§3.1).

```ts
export type Stage = "pre" | "while1" | "while2" | "post" | "shadowing";
export type TranscriptState = "hidden" | "partial" | "full";

export interface FlowStep { stage: Stage; task: string; transcriptState: TranscriptState; allowSkip: boolean; }
export interface TranscriptPolicy {
  revelation: "on_first_fail" | "on_second_fail" | "on_finish" | "never_before_post";
  maxAttemptsPerStage: number;
  allowManualReveal: boolean;
  shadowingOptional: boolean;
}

export interface MicroFlowState {
  stepIndex: number;
  stage: Stage;
  transcript: TranscriptState;
  revealed: boolean;      // ya se mostró transcript completo
  attemptCount: number;   // reintentos dentro de la fase actual
  shadowingDone: boolean;
  finished: boolean;
}

export function initialFlow(question: ListeningQuestion): MicroFlowState;
// Avanza según el contrato: si correct y hay siguiente paso → avanza; si no y
// attemptCount < policy.maxAttemptsPerStage → reintento en la misma fase; si no,
// pasa a "post" y revela según policy.revelation.
export function onStageComplete(state: MicroFlowState, correct: boolean, policy: TranscriptPolicy): MicroFlowState;
export function revealTranscript(state: MicroFlowState, policy: TranscriptPolicy): MicroFlowState;
export function skipToStage(state: MicroFlowState, stage: Stage, flow: FlowStep[]): MicroFlowState;
export function onAttempt(state: MicroFlowState): MicroFlowState;  // contador
```

Transiciones mínimas: `pre → while1 → while2 → post → (shadowing opcional) → finished`. El `revealTranscript` solo permite el toggle si `policy.allowManualReveal`; en otro caso el revelado lo decide `onStageComplete` según `revelation`. El "modo rápido" heredado se consigue con `skipToStage`, y solo a etapas cuyo paso declare `allowSkip`.

### 5.4 Integración en `ListeningPractice.tsx`

Archivo: `frontend/src/features/listening/ListeningPractice.tsx` (componente principal, hoy ~1500 líneas).

- Añadir estado local de micro-flujo por ítem (5.3), iniciado al cargar cada `question` con su `flow`/`transcriptPolicy`.
- Render por fases:
  - **Pre**: tarjeta corta con `context`/`topic` (datos ya presentes en `ListeningQuestion`) y, si aplica, los chunks de activación; botón "continuar" sin reproducir.
  - **While1/While2**: los modos de tarea existentes (MCQ por skill, dictation, shadowing) se reutilizan tal cual; solo cambia el orquestador (qué se muestra y qué se envía).
  - **Post**: mantener el `ActivityResult` existente y añadir el control "ver transcripción" (toggle) que pasa `transcript` a `full` — hoy ya se revela el `script`; la novedad es hacerlo **progresivo** y registrarlo.
- Al enviar cada intento, adjuntar `stage`, `transcriptUsed`, `speedUsed` (la variante ya está en estado), `segmentsReplayed`.
- **Perfil auditivo visible en la UI** (decisión de alcance, objetivo 5): tarjeta/card `AuditoryProfileCard` (nuevo subcomponente en `features/listening/`) que se muestra de forma persistente en el panel de listening mientras hay diagnóstico disponible. Contenido: capa de trabajo actual (badge `recognition`/`comprehension`/`inference`), intervención recomendada (`listening.profile.intervention.*`, clave i18n), motivo corto y, si no hay muestra suficiente, el aviso `listening.profile.needsMore` (sin bloquear la práctica ni ocultar el resto de la UI). Cuando el perfil indique una capa con suficiente muestra, esa capa se usa además para priorizar el siguiente ítem (§4.7).
- NO se introduce aún el nuevo reproductor rico (Fase 2): se usan los controles actuales (play, variante slow/normal/fast, replay ya contado).

Aceptación visual: con los tests de componentes existentes en verde; sin regresión en dictado/shadowing actuales; revisión manual de un flujo A1 y uno B2 (diferencias de transcript policy visibles) y de la tarjeta de perfil (estados: sin datos → needsMore → intervención activa).

### 5.5 i18n

Archivos: `frontend/src/utils/i18n.ts` (claves es/en). Nuevas claves:
- `listening.flow.pre`, `listening.flow.while1`, `listening.flow.while2`, `listening.flow.post`, `listening.flow.shadowing`.
- `listening.profile.intervention.*` (4 intervenciones) y `listening.profile.needsMore`.
- `listening.transcript.reveal` / `listening.transcript.hide`.

### 5.6 Tests frontend

- `frontend/src/features/listening/microFlow.test.ts`: transiciones, reveal según `policy.revelation`, reintentos máximos (`maxAttemptsPerStage`), `skipToStage` solo con `allowSkip`, no mutación.
- `frontend/src/features/listening/AuditoryProfileCard.test.tsx`: tres estados (sin datos → `needsMore`; con intervención activa y su clave i18n; con `shadowingOptional=false` heredado del perfil).
- `frontend/src/api/listening.test.ts`: parámetros nuevos en `submitListeningAnswer`/dictation/shadowing.
- `frontend/src/features/listening/ListeningPractice.test.tsx` (si existe) o test de integración ligero: el render en `pre` no muestra la pregunta hasta `while1`.

## 6. Orden de ejecución (incrementos)

| # | Incremento | Contenido | Criterio de aceptación |
|---|---|---|---|
| 1 | Migración + repositorio | 4.1 + 4.2 | pytest migración nuevo + suite existente verde |
| 2 | Schemas | 4.3 | `test_schemas` verde |
| 3 | Domain persistencia | 4.4 (`layer`/campos en `submit_answer`/`submit_production`) | `test_listening_attempts_v327` verde |
| 4 | Motor de flujo (backend) | 4.5 + exposición en `_public`/`next_question` | `test_listening_flow` verde |
| 5 | Perfil auditivo (backend) | 4.6 + 4.8 (diagnóstico) | `test_auditory_profile` verde |
| 6 | Selector por capa | 4.7 | tests de selección nuevos + 1538 legacy verdes |
| 7 | Frontend tipos/API | 5.1 + 5.2 | `tsc --noEmit` OK |
| 8 | Frontend máquina de estados | 5.3 | `microFlow.test.ts` verde |
| 9 | Frontend integración + i18n | 5.4 + 5.5 (incluye `AuditoryProfileCard` visible en UI) | vitest total verde; revisión manual de un flujo A1 y uno B2 (transcript policy distinta) y de la tarjeta de perfil (sin datos → needsMore → intervención) |
| 10 | Release V3.27 | bump + docs + verificación | checklist §7 |

## 7. Verificación y release (checklist V3.27)

Al cerrar la fase, replicando el patrón de releases anteriores:

1. `backend/config.py:20` → `VERSION = "3.27.0"`.
2. Backend: `pytest` completo (base 1538 + nuevos) en verde; `ruff check .` limpio.
3. Frontend: `vitest` completo en verde (base 450 + nuevos); `tsc --noEmit` OK.
4. `scripts/check_release_consistency.py` con `3.27.0` → exit 0.
5. Docs: `CHANGELOG.md` (entrada `[3.27.0]`), `release-notes-v3.27.0.md`, `README.md`, `docs/RELEVO.md` (§ nuevo V3.27) y actualización de `PLAN.md`.
6. Golden tests (`tests/test_golden_*.py`) en verde (la evidencia ampliada no debe alterar gates).

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Los 5 campos nuevos cambian el INSERT y algún test de invariantes falla | Incremento 1 verifica `test_store_append_only`/`test_store_isolation` antes de continuar |
| `next_question`/`pick_next_question` con firma extendida rompe llamadores | Parámetros opcionales con default; los llamadores antiguos no cambian |
| El micro-flujo alarga la sesión y reduce intentos/hora | La política de fases marca `post`/`shadowing` como opcionales según nivel; cada paso declara `allow_skip` (modo rápido heredado) |
| El frontend duplica reglas pedagógicas o revela transcript fuera de política (contamina la métrica "precisión con apoyo decreciente") | El backend es la fuente única (§3.1): `flow`/`transcript_policy` viajan en el payload y `revealTranscript` respeta `allowManualReveal`/`revelation`; el frontend no tiene constantes propias |
| `transcript_policy` con 513 ítems produce flujos inválidos | Barrido determinista del banco completo en `test_listening_flow` (incremento 4) |
| El perfil recomienda antes de tener muestra | `PROFILE_MIN_ATTEMPTS=3`; respuesta `needs_min_attempts: true` sin intervención; la UI muestra `needsMore` |
| Umbrales (70/85/60) arbitrarios | Constantes centralizadas en `auditory_profile.py`; deuda de calibración documentada (spec §16) |

## 9. Referencias cruzadas

- Especificación: `docs/LISTENING_ENGINE_4.0.md` — §5 (perfil/casos A-D), §6 (micro-flujo y transcript policy), §6.4 (AudioController, solo referencia), §8 (evidencia ampliada), §9 (selección por capa), §13 (freeze), §14 (Fase 1), §16 (decisiones abiertas).
- Código backend: `backend/repositories/db.py`, `backend/repositories/listening.py`, `backend/domain/listening.py`, `backend/services/listening.py` (`SKILL_LAYER`, `skill_layer`, `pick_next_question`, `listening_diagnostic`, `RESILIENCE_MIN_ATTEMPTS`), `backend/schemas/listening.py`, `backend/routers/listening.py`.
- Código frontend: `frontend/src/types/api.ts`, `frontend/src/api/listening.ts`, `frontend/src/features/listening/ListeningPractice.tsx`, `frontend/src/features/listening/listeningSession.ts` (+ `.test.ts` como patrón para `microFlow.ts`), `frontend/src/utils/i18n.ts`.
- Docs: `docs/CONSTITUCION-PEDAGOGICA.md` (§4, §6), `docs/LISTENING_CURRICULUM.md`.
