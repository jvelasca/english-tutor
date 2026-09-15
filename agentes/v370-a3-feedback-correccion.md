# Briefing de subagente — V3.70 · Eje 3: feedback y corrección

> **Estado:** **PENDIENTE** (V3.70, 2026-09-15). Tercer eje de la auditoría
> pedagógica. **Solo medición**.
> **Qué es:** el dossier `docs/audit/AC-PED-FEEDBACK.md` más el test
> `backend/tests/test_ped_feedback_v370.py`.
> **Qué NO cierra:** escribir un motor de feedback determinista por destreza ni
> cambiar los prompts. Se **declara** dónde hay corrección real, dónde es solo
> puntuación y dónde no hay nada.
> **Regla dura:** *no se toca `services/**` ni los prompts del tutor*.
> **Briefing maestro:** `agentes/v370-auditoria-pedagogica.md`.

## Rol

**Auditor de feedback.** Dossier `AC` (plantilla `docs/audit/TEMPLATE.md`) +
`test_ped_feedback_v370.py`. No modifica `backend/services/**` ni
`frontend/**`.

## Objetivo

Responder: **¿el tutor corrige bien?** Concretamente: qué se corrige de forma
**determinista**, qué se delega al **LLM**, qué es **solo puntuación** y qué
**no se corrige en absoluto**.

## Estado de partida ya medido (no lo re-derives: verifícalo y cítalo)

Evidencia en `docs/audit/generated/feedback-coverage.json` y `.md`
(`python -m scripts.audit_dossier feedback-coverage`).

### Canal declarado por destreza

| Destreza | Determinista | LLM |
|---|---|---|
| grammar | `services/grammar.py` (regex + `confidence`) | `policy.CORRECTNESS_GUIDANCE` vía `context.build_system_prompt` |
| writing | `services/writing.py` (rúbrica) | `services/writing_llm.py` (**solo extrae evidencia**) |
| speaking | `services/speaking.py` (rúbrica) | `services/speaking_llm.py` (**solo extrae evidencia**) |
| pronunciation | `services/phonetics.py` + `pronunciation.py` | NO |
| listening | scoring por respuesta (MC) | NO |
| vocabulary | ledger léxico (`lexicon`/`evidence`) | NO |
| **reading** | **NO** | **NO** |
| interaction | `services/interaction.py` (telemetría) | NO |
| **mediation** | **NO** | **NO** |

### Cobertura de la política de corrección

- **Grammar determinista:** **7 reglas** (`services/grammar.RULES`), umbral de
  confirmación `CONFIRMED_THRESHOLD = 0.8`, racha de dominio
  `MASTERY_STREAK = 3`.
- **Rúbricas:** writing **6** criterios (`WRITING_CRITERIA`), speaking **7**
  (`SPEAKING_CRITERIA`).
- **Categorías formales de feedback:** **5** — CORRECT, NATURAL, OPTIONAL,
  PRONUNCIATION, STYLE (`policy.FEEDBACK_CATEGORIES`).
- **Guía de corrección por nivel:** `CORRECTNESS_GUIDANCE` cubre
  **Pre-A1, A1, A2, B1, B2, C1, C2** — **ningún nivel sin guía**.
- **Destrezas SIN ningún canal de corrección: `mediation` y `reading`.**
- **Destrezas con canal SOLO de puntuación (sin feedback textual):
  `interaction`, `listening`, `pronunciation`, `vocabulary`.**

### Contexto arquitectónico que el dossier debe explicar

La premisa del proyecto es «**el LLM extrae evidencia, el scorer decide**»
(repetida en los docstrings de `writing.py` y `speaking.py`). Por tanto el
feedback **textual** del tutor vive en el system prompt
(`policy.feedback_policy()` + `CORRECTNESS_GUIDANCE`), mientras que lo
determinista **detecta** (regex de grammar) y **puntúa** (rúbricas). El dossier
debe distinguir con precisión esas tres cosas, porque decirlas todas «feedback»
es lo que oculta el hueco.

## Diseño del dossier `docs/audit/AC-PED-FEEDBACK.md`

1. **Alcance** — los canales de corrección de las 9 destrezas, la política
   (`services/policy.py`), el detector (`services/grammar.py`) y las rúbricas
   (`writing.py`, `speaking.py`, `phonetics.py`, `pronunciation.py`,
   `interaction.py`). **NO** se audita el contenido (eje 1), la cobertura
   (eje 2), la maestría (eje 4) ni los instrumentos (eje 5). **NO** se audita la
   calidad lingüística del texto que produce el LLM en tiempo de ejecución (no
   es reproducible sin modelo): se audita **la política declarada**.
2. **Método** — instrumento `feedback-coverage`; lectura de la política y del
   detector; enumeración de las reglas de `grammar.RULES` y de los criterios de
   cada rúbrica.
3. **Evidencia** — las dos tablas de arriba + la lista completa de las **7
   reglas** de grammar (con su `confidence`) y de los criterios de writing y
   speaking. Debe incluir una tabla de **trazabilidad**:
   `destreza → quién detecta → quién puntúa → quién redacta el feedback`.
4. **Hallazgos** — tabla P0/P1/P2/P3. Candidatos ya medidos:
   - **`reading` sin canal de corrección** pese a tener 15 objetivos y 18 checks.
   - **`mediation` sin canal** (coherente con el eje 2: está inerte).
   - El feedback **textual** de listening, pronunciation, vocabulary e
     interaction es **solo puntuación**: no hay mensaje correctivo declarado.
   - Toda la corrección textual **depende del LLM** vía prompt; el único
     detector determinista con umbral es grammar (7 reglas).
   - Grammar cubre 7 reglas: conviene declarar **qué errores quedan fuera**
     (p. ej. artículos, orden de palabras) frente a los 11 subskills declarados
     en `COMPETENCES_BY_MODALITY["grammar"]`.
5. **Veredicto** — 2–3 líneas. Distinguir «no hay feedback» de «no hay feedback
   *estructurado*» y de «el feedback depende del LLM, que es una decisión de
   diseño, no un defecto».
6. **Regenerar / Verificar**.
7. **Tests que respaldan**.

## Tests: `backend/tests/test_ped_feedback_v370.py`

Tests requeridos:

- `test_feedback_channels_cover_the_nine_modalities` — las 9 modalidades
  aparecen declaradas, y las que no tienen canal son exactamente
  `{"reading", "mediation"}`.
- `test_score_only_modalities_are_declared` — el conjunto con canal
  determinista y sin LLM es exactamente
  `{"interaction", "listening", "pronunciation", "vocabulary"}`.
- `test_grammar_rule_coverage_is_partial` — `len(grammar.RULES) == 7` y el
  umbral/racha son 0.8 y 3; el test declara que hay **11 subskills** de grammar
  declarados en `skill_axis.COMPETENCES_BY_MODALITY["grammar"]` frente a 7
  reglas (hueco medido).
- `test_rubric_sizes_are_pinned` — `len(writing.WRITING_CRITERIA) == 6` y
  `len(speaking.SPEAKING_CRITERIA) == 7`.
- `test_correctness_guidance_covers_every_level` — los niveles con guía son
  exactamente `{"Pre-A1","A1","A2","B1","B2","C1","C2"}` (hoy **no hay hueco**:
  pinnealo para que una regresión futura se detecte).
- `test_feedback_categories_are_the_five_declared` — el conjunto es
  `{CORRECT, NATURAL, OPTIONAL, PRONUNCIATION, STYLE}`.
- `test_llm_only_extracts_evidence_in_writing_and_speaking` — el prompt de
  writing/speaking no decide la nota: afirma que el scorer determinista
  (`writing.score_*` / `speaking.score_*`, o la función pública equivalente que
  localices) existe y es invocable sin LLM. **Documenta la función real que
  encuentres** en el dossier.

Convención: `from services import ...`; sin HTTP; sin LLM.

## Criterios de salida

1. `docs/audit/AC-PED-FEEDBACK.md` creado con la plantilla completa.
2. `backend/tests/test_ped_feedback_v370.py` creado y **verde**.
3. `python -m ruff check .` limpio; `python -m pytest -q` verde con el total
   anterior + los nuevos.
4. `python -m scripts.audit_dossier feedback-coverage` reproducible.
5. Cero ficheros de `backend/services/**` o `frontend/**` modificados.

## Fuera de alcance

- Añadir reglas a `grammar.RULES`, cambiar `CORRECTNESS_GUIDANCE` o crear
  feedback textual para reading/mediation.
- Auditar la calidad real del texto del LLM en ejecución (requiere modelo y
  tráfico; `docs/audit/PARKED.md`).
