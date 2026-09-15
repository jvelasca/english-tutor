# AC · Auditoría de feedback y corrección (V3.70 · Eje 3)

> **Release:** V3.70 (auditoría pedagógica + CEFR) · **Eje 3 de 5**
> **Fecha:** 2026-09-15 · **Instrumento:**
> `python -m scripts.audit_dossier feedback-coverage` (solo lectura)
> **Evidencia cruda:** `docs/audit/generated/feedback-coverage.{md,json}`

## Alcance

Los **canales de corrección** de las 9 modalidades de
`services/mastery.MASTERY_SKILLS`: quién **detecta** el error, quién **puntúa**
el rendimiento y quién **redacta** el mensaje al alumno.

Fuentes auditadas: `services/policy.py` (política declarada),
`services/grammar.py` (detector determinista), `services/writing.py` y
`services/speaking.py` (rúbricas), `services/phonetics.py` /
`services/pronunciation.py`, `services/interaction.py` (telemetría) y
`services/context.py` (punto de inyección del prompt).

**No se audita** en este eje:

- la **adecuación CEFR** del contenido (eje 1) ni la **cobertura** de destrezas
  (eje 2);
- la **validez de la maestría** (eje 4) ni los **instrumentos** (eje 5);
- **la calidad lingüística real del texto que produce el LLM en ejecución**:
  requiere el modelo y tráfico real, no es reproducible en CI y está declarado
  en `docs/audit/PARKED.md`. Aquí se audita la **política declarada** y la
  **cobertura de canales**, no la salida del modelo.

## Método

1. Instrumento de solo lectura `feedback-coverage`, que declara el canal de cada
   destreza y cuenta las reglas y criterios reales.
2. **Verificación en código** de las afirmaciones estructurales: umbral de
   confirmación, patrones positivos, punto de inyección del prompt y uso real
   del detector por las rúbricas.
3. **Ejecución determinista** de los scorers (`score_writing`,
   `score_speaking`) sin LLM, para demostrar que la puntuación no depende del
   modelo.

## Evidencia

### 1. Canal declarado por destreza

| Destreza | Detecta / puntúa (determinista) | Redacta el feedback |
|---|---|---|
| grammar | `services/grammar.py` — 7 reglas + `confidence`; racha de dominio | prompt del tutor (`policy`) |
| writing | `services/writing.py:69` `score_writing` (6 criterios) | prompt + `writing_llm.py` (**extrae evidencia, no puntúa**) |
| speaking | `services/speaking.py:545` `score_speaking` (7 criterios) | prompt + `speaking_llm.py` (**extrae evidencia, no puntúa**) |
| pronunciation | `services/pronunciation.py:26` `score_pronunciation` | — |
| listening | `services/listening.py:1944` `score_answer` (binario MC) | — |
| vocabulary | `services/lexicon.py:476` `score_write_attempt` | — |
| **reading** | **—** | **—** |
| interaction | `services/interaction.py:84` `interaction_evidence` (telemetría) | — |
| **mediation** | **—** | **—** |

### 2. El detector determinista de grammar, medido

`services/grammar.py` declara **7 reglas**, un umbral
`CONFIRMED_THRESHOLD = 0.8` (`grammar.py:13`) y una racha
`MASTERY_STREAK = 3` (`grammar.py:16`). La marca de confirmación es
`confirmed = rule["confidence"] >= CONFIRMED_THRESHOLD` (`grammar.py:103`).

| Regla | `confidence` | ¿Puede confirmarse? |
|---|---|---|
| `he_she_it_s` | 0,90 | **sí** |
| `double_negative` | 0,85 | **sí** |
| `capitalization_i` | 0,95 | **sí** |
| `there_their_theyre` | 0,70 | **no** (candidato permanente) |
| `your_youre` | 0,70 | **no** (candidato permanente) |
| `to_too` | 0,60 | **no** (candidato permanente) |
| `a_an` | 0,50 | **no** (candidato permanente) |

⇒ **3 de 7 reglas** pueden confirmarse; **4** quedan en «candidato» para
siempre.

Además, `find_correct_usage` depende de `POSITIVE_PATTERNS`
(`grammar.py:111`), que **solo tiene 2 entradas**: `he_she_it_s` y `to_too`.
Como la racha de dominio solo avanza con uso correcto detectable, **solo 2 de
las 7 reglas pueden alcanzar `MASTERY_STREAK = 3`**; las otras 5 no pueden
marcarse nunca como «dominadas».

### 3. Cobertura de la política de corrección (propiedad positiva)

- **Categorías formales:** 5 — `CORRECT`, `NATURAL`, `OPTIONAL`,
  `PRONUNCIATION`, `STYLE` (`policy.FEEDBACK_CATEGORIES`), emitidas por
  `policy.feedback_policy()`, que instruye a **no** reportar como error lo
  natural, opcional o estilístico.
- **Guía por nivel:** `policy.CORRECTNESS_GUIDANCE` cubre **Pre-A1, A1, A2, B1,
  B2, C1, C2** — **sin huecos**.
- **Inyección:** `services/context.py:6` importa `feedback_policy` y
  `correctness_guidance`; se inyectan en `context.py:17`, `:23`, `:93` y `:119`.
- **Rúbricas:** writing 6 criterios (`writing.py:18`), speaking 7
  (`speaking.py:29`).

### 4. Trazabilidad: quién detecta, quién puntúa, quién redacta

| Plano | Determinista | LLM |
|---|---|---|
| **Detectar** el error | grammar (7 reglas, 3 confirmables); rúbricas por penalización | `*_llm.py` extrae `grammar_errors` |
| **Puntuar** | todos los scorers de la tabla 1 | — (el LLM **no** puntúa, por diseño) |
| **Redactar** el mensaje | **nadie** | `policy.feedback_policy()` vía prompt |

**El único canal que redacta un mensaje correctivo es el prompt del tutor.**
Los detectores deterministas alimentan puntuación y perfil, no un mensaje.

### 5. Uso del detector dentro de las rúbricas

`writing.py:15` y `speaking.py:23` importan `find_errors`, pero lo usan como
**conteo de penalización**: `max(0.0, 1.0 - 0.25 * len(find_errors(...)))`
(`writing.py:79`, `speaking.py:567`). Es decir: el error detectado **baja la
nota**, pero **no genera la explicación** de por qué.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| 1 | **P1** | **4 de las 7 reglas de grammar nunca pueden confirmarse**: su `confidence` está por debajo de `CONFIRMED_THRESHOLD = 0.8`, así que quedan en «candidato» de forma permanente y no deben alimentar la personalización. | `grammar.py:13` (`0.8`), `grammar.py:103`, confianzas `a_an 0.5`, `to_too 0.6`, `there_their_theyre 0.7`, `your_youre 0.7` | Subir la confianza con evidencia real o **retirar** las reglas que no se pueden confirmar; hoy el catálogo promete 7 y confirma 3 | Abierto |
| 2 | **P1** | **5 de las 7 reglas no tienen patrón de uso correcto** (`POSITIVE_PATTERNS` solo define `he_she_it_s` y `to_too`): solo esas 2 pueden alcanzar `MASTERY_STREAK = 3`. Las otras 5 **nunca** pueden marcarse como «dominadas». | `grammar.py:111` (2 claves), `grammar.py:16` (`MASTERY_STREAK = 3`), `tests/test_grammar.py:149` | Definir patrones positivos para las reglas restantes o documentar que 5 reglas son solo detector de errores, sin ciclo de dominio | Abierto |
| 3 | **P1** | **`reading` y `mediation` no tienen ningún canal de corrección**: no hay detector ni scorer propios. Coherente con el eje 2, donde ya aparecían inertes. | `feedback-coverage.json` → `without_channel: ["mediation","reading"]`; `backend/services/` sin `reading.py` ni `mediation.py` | Decidir si reading entra con scorer propio; para `mediation`, decidir si es producto | Abierto |
| 4 | **P2** | **`listening`, `pronunciation`, `vocabulary` e `interaction` tienen corrección SOLO de puntuación**: no existe mensaje correctivo declarado para ninguna de las cuatro. | `feedback-coverage.json` → `score_only`, `FEEDBACK_CHANNELS` | Declarar explícitamente en `CONSTITUCION-PEDAGOGICA.md` qué destrezas son de puntuación pura, o darles canal textual | Abierto |
| 5 | **P2** | El error detectado por grammar **dentro de las rúbricas** solo resta puntuación; **no produce la explicación**. Todo el feedback textual es prompt de LLM, incluso cuando el error ya está identificado de forma determinista. | `writing.py:79`, `speaking.py:567` (`1.0 - 0.25 * len(find_errors(...))`), `context.py:17` | Plantilla determinista de mensaje por regla (`rule` → `message` ya existe en `grammar.RULES`) cuando `confirmed=True`; el LLM solo para lo no determinista | Abierto |
| 6 | **P3** | La política de corrección está **completa**: 5 categorías formales, guía para los 7 niveles (incluida Pre-A1) e instrucción explícita de no marcar como error lo natural/opcional/estilístico. | `policy.py:6` (`CORRECTNESS_GUIDANCE`), `policy.py:46` (`FEEDBACK_CATEGORIES`), `context.py:17` | Preservar: es una de las partes más sólidas del sistema pedagógico | **Correcto** |

## Veredicto

El sistema **puntúa** de forma determinista en siete de las nueve destrezas y
**no** delega la nota al LLM (el LLM extrae evidencia; el scorer decide), que es
la propiedad arquitectónica correcta y está verificada por ejecución.

Ahora bien, «feedback» en este producto significa hoy **tres cosas distintas**
que conviene no confundir: **(a)** detección determinista de errores (grammar: 7
reglas, 3 confirmables, 2 con ciclo de dominio), **(b)** puntuación por rúbrica
(writing, speaking, pronunciation, listening, vocabulary) y **(c)** un mensaje
correctivo redactado por el LLM desde un prompt. Lo que **no** existe es
**feedback textual determinista**: cuando el sistema ya sabe con certeza qué
error se cometió (`confirmed=True`), ese hallazgo no se convierte en explicación,
solo en un −0,25 de nota.

Y dos destrezas (`reading`, `mediation`) no se corrigen de ninguna manera.

**Qué no demuestra este eje:** que el tutor redacte bien en producción. Eso
depende del modelo y del tráfico, y no es reproducible en CI.

## Regenerar / Verificar

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.audit_dossier feedback-coverage
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_feedback_v370.py
```

## Tests que respaldan

`backend/tests/test_ped_feedback_v370.py` (9 tests):

| Test | Qué pinnea |
|---|---|
| `test_grammar_rules_are_seven_and_only_three_confirmable` | 7 reglas, 3 con `confidence >= 0.8` |
| `test_only_two_rules_can_track_mastery` | `POSITIVE_PATTERNS` con 2 claves y subconjunto de reglas |
| `test_reading_and_mediation_have_no_correction_channel` | sin scorer propio |
| `test_score_only_modalities_are_declared` | el conjunto exacto de 4 con puntuación sin texto |
| `test_rubric_sizes_are_pinned` | writing 6, speaking 7 |
| `test_correctness_guidance_covers_every_level` | los 7 niveles, sin hueco |
| `test_feedback_categories_are_the_five_declared` | las 5 categorías exactas |
| `test_feedback_policy_mentions_every_category` | `feedback_policy()` las incluye |
| `test_deterministic_scorers_run_without_llm` | `score_writing` y `score_speaking` puntúan sin LLM |
