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
| **P5** | CEFR basado en evidencia (muestras por destreza + confianza) | Medio | P2, P4 | ⏳ pendiente |
| **P6** | Pronunciación fonémica (alineación de fonemas) | Medio | — | ⏳ pendiente |

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

### P6 — Pronunciación fonémica
Sustituir la similitud textual por alineación de fonemas: grapheme→phoneme (diccionario local),
phoneme accuracy y prosodia. Mantener `score` como proxy mientras no haya fonemas.

## Reglas de proceso

- Un commit `feat:` por subagente, **verificado en verde** antes de commitear
  (backend `pytest` + `ruff`; frontend `tsc` + `vitest`).
- Briefings autocontenidos en `agentes/pedagogia/p-*.md` (premisa 5).
- Tests **rápidos y deterministas**, sin LLM ni red (premisa 12).
- Todo cambio actualiza `docs/` y `PLAN.md` (premisa 9).
- La documentación y los tests forman parte de "terminado".
