# Plan — Etapa 2: Pedagogía (Learning Engine v2)

> **Contexto.** La parte informática está congelada tras la Release Audit 1.1 (v1.1.1): el
> backend, frontend, launcher, la arquitectura (`routers → domain → repositories → SQLite`,
> `services` puros) y los gates están verdes. Esta etapa **no toca arquitectura**: añade rigor
> pedagógico a lo que ya medimos, para que "lo que medimos represente aprendizaje".

## Objetivo

Convertir el Learning Engine de un *contador de actividad* en un sistema que distinga el
aprendizaje real:

- Errores: **cometido / corregido / superado / recurrente / dominado**.
- Vocabulario: **exposure / production / mastery**.
- Listening: **competencia** (no solo intentos/aciertos).
- CEFR: **basado en evidencia** (no puntos acumulados).
- Pronunciación: **fonémica** (no solo `SequenceMatcher`).

## Orden de trabajo (hito a hito, un subagente a la vez)

| Id | Track | Impacto | Depende de | Estado |
|---|---|---|---|---|
| **P1** | Política pedagógica formal (`CORRECT`/`NATURAL`/`OPTIONAL`/`STYLE`/`PRONUNCIATION`) | Alto (todo el prompt del tutor) | — | ✔ hecho |
| **P2** | Error Mastery (cometido/corregido/superado/dominado) | Alto (núcleo adaptativo) | P1 | ✔ hecho |
| **P3** | Vocabulario: exposure/production/mastery | Medio | — | ✔ hecho |
| **P4** | Listening como competencia (dificultad/tema/tendencia/tiempo/reincidencia) | Medio | — | ✔ hecho |
| **P5** | CEFR basado en evidencia (muestras por destreza + confianza) | Medio | P2, P4 | ✔ hecho |
| **P6** | Pronunciación fonémica (alineación de fonemas) | Medio | — | 🔁 diferido (a favor de Student Model 2.0) |
| **V1.12** | Student Model 2.0 + Assessment Loop (unificación + snapshots + naming CEFR + Speaking 2.0) | Alto (bucle completo) | P5 | ✔ hecho |
| **V1.13** | Listening 3.0 (audio TTS pre-renderizado + cierre A1→B2 + evidencia por sub-destreza) | Alto (contenido + audio) | P4, V1.12 | ✔ hecho |
| **V1.14** | Listening Evidence & Adaptive Selection (modelo de realización + integridad de evidencia + selector adaptativo) | Alto (validez pedagógica) | V1.13 | ✔ hecho |
| **V1.15** | Speaking 3.0 (diagnóstico longitudinal por criterio + `interaction`) | Alto (speaking como competencia) | V1.12 | ✔ hecho |

## Detalle por track

### P1 — Política pedagógica formal
El prompt actual dice "correct mistakes gently" y "explain briefly", sin codificar una política
estricta. Añadir una taxonomía formal de categorías de corrección y exponerla en el system prompt
para que el tutor distinga un error real de una sugerencia de estilo o una variante opcional.
- `services/policy.py`: `FEEDBACK_CATEGORIES` + `feedback_policy()` (puro, determinista).
- `services/context.py`: integrar `feedback_policy()` en `build_system_prompt`.

### P2 — Error Mastery
Hoy `grammar_errors` acumula `count`/`last_example`/`last_seen` (ya con `confidence`/`confirmed`).
No distingue si el alumno ya superó el error. Añadir:
- Esquema/migración: `first_seen`, `correct_after`, `streak`, `mastered`.
- Evidencia positiva: detectar cuándo el alumno usa la forma correcta (patrón "positivo" por regla).
- Perfil/prompt: separar errores **activos** de **dominados**; el tutor prioriza los activos.

### P3 — Vocabulario exposure/production/mastery
Hoy `vocabulary` mide producción (`appearances` = mensajes en que el alumno escribió la palabra).
Añadir exposición (palabras de las respuestas del tutor) y una señal de dominio (producción
repetida y espaciada en el tiempo), separando los tres conceptos.

### P4 — Listening como competencia
Hoy `listening_attempts` solo tiene `correct`. Añadir `difficulty`, `topic`, `response_time` y
métricas: precisión por dificultad/tema, tendencia reciente, tiempo de respuesta y reincidencia.

### P5 — CEFR basado en evidencia
Sustituir el "punto-sum" por un modelo de **evidencia**: cada nivel exige un mínimo de muestras
por destreza (mensajes, listening, pronunciación, gramática) y se muestra la confianza del nivel.

### P6 — Pronunciación fonémica (diferido)
Sustituir la similitud textual por alineación de fonemas: grapheme→phoneme (diccionario local),
phoneme accuracy y prosodia. Mantener `score` como proxy mientras no haya fonemas.
**Diferido** a favor de V1.12 (Student Model 2.0 + Assessment Loop): primero se unifica el modelo
de alumno y se cierra el bucle de evaluación continua, y después se retoma la fonémica.

### V1.12 — Student Model 2.0 + Assessment Loop
Reconciliar los dos estimadores CEFR divergentes en una única fuente de verdad (el Student Model
de la Academy). `/api/profile` pasa a ser proyección del modelo unificado; se corrigen los P0
(Speaking scoring con `observed`, naming CEFR "heuristic CEFR-aligned band" + `overall_ability` +
`readiness`, versión de release) y se añaden snapshots históricos de evaluación reproducibles
(`cefr_assessment_snapshots` con `instrument_version`). Dos subagentes: `p6-speaking-2.0` y
`p7-student-model-unificado` (briefings en `agentes/pedagogia/`).

### V1.13 — Listening 3.0 (audio TTS pre-renderizado + cierre A1→B2)
Convertir el listening de "scripts + TTS genérico" a **audio TTS pre-renderizado por ítem**
(sintetizado y cacheado con Piper), servir `GET /api/listening/audio/{question_id}`, cerrar el
currículo **A1→B2** (`b2.json` + `LEVEL_ORDER`), y garantizar evidencia independiente por
sub-destreza. Briefing en `agentes/pedagogia/p8-listening-3.0.md` (formato P1–P5). Honesto con el
límite local: Piper es una sola voz; los acentos/ruido/hablantes múltiples son límite de contenido,
no de código.

### V1.14 — Listening Evidence & Adaptive Selection
Corregir los P0 de la auditoría de V1.13: (1) no llamar "audio real" al TTS Piper; (2) impedir que
la metadata (`accent`/`speaker_count`/`noise`/`connected_speech`) genere evidencia falsa; (3)
separar `declared`/`realized`/`verified` (modelo de realización del audio); (4) selector adaptativo
que consuma el Student Model. Incluye cache versionado (P1.1) y etiqueta honesta de audio en el
frontend. P1 restantes (delayed retention, shadowing/dictado reales, audio humano) quedan para V1.15+.

### V1.15 — Speaking 3.0 (diagnóstico longitudinal + interaction)
Medir los criterios de speaking (fluency/grammar/lexical/pronunciation/coherence/interaction)
**longitudinalmente** sobre el mismo Student Model: `speaking_diagnostic` agrupa la evidencia por
criterio de rúbrica (media/tendencia/débil), expuesto en `GET /api/academy/speaking/diagnostic` y
como sub-destrezas del perfil. Añade `interaction` como séptimo criterio del rubric (extraído del
LLM en el flujo libre; no observable en read-aloud). Briefing en
`agentes/pedagogia/p9-speaking-3.0.md`.

## Reglas de proceso

- Un commit `feat:` por subagente, **verificado en verde** antes de commitear
  (backend `pytest` + `ruff`; frontend `tsc` + `vitest`).
- Briefings autocontenidos en `agentes/pedagogia/p-*.md` (premisa 5).
- Tests **rápidos y deterministas**, sin LLM ni red (premisa 12).
- Todo cambio actualiza `docs/` y `PLAN.md` (premisa 9).
- La documentación y los tests forman parte de "terminado".
