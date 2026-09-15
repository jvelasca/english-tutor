# Briefing de subagente — V3.70 · Eje 2: cobertura de destrezas

> **Estado:** **PENDIENTE** (V3.70, 2026-09-15). Segundo eje de la auditoría
> pedagógica. **Solo medición**.
> **Qué es:** el dossier `docs/audit/AB-PED-COBERTURA.md` más el test
> `backend/tests/test_ped_coverage_v370.py`.
> **Qué NO cierra:** rellenar los huecos de contenido (corpus B1–C2, escenarios
> A1/C1, escribir un motor de reading, activar mediation). Los huecos se
> **declaran con número y severidad**; su remediación va a **V4.0.x**.
> **Regla dura:** *no se toca contenido, banco ni currículum*.
> **Briefing maestro:** `agentes/v370-auditoria-pedagogica.md`.

## Rol

**Auditor de cobertura.** Dossier `AB` (plantilla `docs/audit/TEMPLATE.md`) +
`test_ped_coverage_v370.py`. No modifica `backend/curriculum/**`,
`backend/services/**`, `backend/data/**` ni `frontend/**`.

## Objetivo

Responder con números: **¿está el alumno expuesto a las 9 modalidades
declaradas, y con qué volumen?** Y dejar escrito **qué está declarado pero
inerte**.

## Estado de partida ya medido (no lo re-derives: verifícalo y cítalo)

Evidencia en `docs/audit/generated/skill-coverage.json` y `.md`
(`python -m scripts.audit_dossier skill-coverage`).

### Matriz modalidad × artefacto (existencia comprobada en disco)

| Modalidad | Competencias | En matriz | Canal de evidencia | Objetivos | Checks | Corpus | Scorer | UI |
|---|---|---|---|---|---|---|---|---|
| vocabulary | 8 | sí | written | 110 | 180 | 0 | `lexicon.py` | `vocabulary` |
| grammar | 11 | sí | written | 56 | 104 | 0 | `grammar.py` | `grammar` |
| pronunciation | 10 | **NO** | spoken | 38 | 0 | 120 | `pronunciation.py` | `pronunciation` |
| listening | 24 | sí | receptive | 38 | 66 | 490 | `listening.py` | `listening` |
| speaking | 18 | sí | spoken | 70 | 0 | 174 | `speaking.py` | `speaking` |
| reading | 10 | sí | receptive | 15 | 18 | 0 | `reading.py` **AUSENTE** | `reading` |
| writing | 15 | sí | written | 67 | 0 | 0 | `writing.py` | `writing` |
| interaction | **0** | sí | **NO** | 0 | 0 | 66 | `interaction.py` | `conversation` |
| mediation | **0** | sí | **NO** | 0 | 0 | **0** | **AUSENTE** | **AUSENTE** |

### Huecos medidos por el instrumento

| Modalidad | Hueco |
|---|---|
| reading | sin scorer propio |
| interaction | sin canal de evidencia |
| mediation | sin competencias ni corpus |
| mediation | sin canal de evidencia |
| mediation | sin scorer propio |
| mediation | sin feature de UI |

### Volumen frente a objetivo declarado (listening)

`services/curriculum.LISTENING_CORPUS_TARGETS = {A1:200, A2:200, B1:180,
B2:160, C1:120, C2:100}`:

| Nivel | Corpus declarado | Objetivo | % del objetivo |
|---|---|---|---|
| A1 | 200 | 200 | 100,0 % |
| A2 | 200 | 200 | 100,0 % |
| B1 | 25 | 180 | **13,9 %** |
| B2 | 25 | 160 | **15,6 %** |
| C1 | 20 | 120 | **16,7 %** |
| C2 | 20 | 100 | **20,0 %** |

### Escenarios de speaking por `cefr_target`

`A1: 1 · A2: 6 · B1: 7 · B2: 5 · C1: 1 · C2: 6` (**total 26**). Los extremos
(A1 y C1) tienen **un solo escenario** cada uno.

### Audio

- `backend/audio_library/manifest.json` versión **1.2.0** con
  **`entries: []`** ⇒ **cero ítems grabados a voz humana**; todo el listening es
  TTS on-demand. El `Quality Gate` de `services/content_validation.py` mide
  diversidad **declarada** (≥10 hablantes, ≥4 acentos, ruido, multi-hablante) y
  el propio módulo advierte en su docstring que **no** mide el audio realizado.
- Ítems de aprendizaje validados (`content_stats()`): **539**
  (listening 513 = corpus 490 + legacy 23, más 26 escenarios), `with_audio_id`
  499, cobertura curricular **42/49 celdas = 85,7 %** con **`pre-a1` 0/7** (no
  existe curso Pre-A1 aunque `cefr_descriptors` declare la banda).

## Diseño del dossier `docs/audit/AB-PED-COBERTURA.md`

1. **Alcance** — las 9 modalidades de `services/skill_axis.SKILL_MODALITIES`;
   contenido, scorer, canal de evidencia, instrumento de estimación y UI de cada
   una. **NO** se audita la calidad del contenido (eje 1), la validez de la
   maestría (eje 4) ni los instrumentos (eje 5).
2. **Método** — instrumento `skill-coverage` (existencia de artefactos
   comprobada en disco, no declarada); `content_stats()` como métrica canónica;
   el manifest de audio como fuente de verdad de lo **grabado**.
3. **Evidencia** — las tres tablas de arriba + la lista de huecos. Debe
   **separar explícitamente** tres categorías: (a) **declarado y operativo**,
   (b) **declarado pero sin emisor de evidencia**, (c) **declarado pero inerte**.
4. **Hallazgos** — `| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`
   con P0/P1/P2/P3. Candidatos ya medidos:
   - `reading`: **15 objetivos y 18 checks** lo declaran, pero **no existe
     `backend/services/reading.py`** ni corpus propio: la evidencia de reading
     solo puede venir de checks MC genéricos.
   - `mediation`: **0 competencias, 0 corpus, sin canal, sin scorer, sin UI** —
     está en `MASTERY_SKILLS` y en la matriz CEFR pero **nada la produce**.
   - `interaction`: sin competencias declaradas y **sin canal**
     (`MODALITY_CHANNEL` no la tiene), aunque `conversation_corpus.json` (66
     ítems) y `services/interaction.py` existen.
   - `pronunciation`: **fuera de la matriz CEFR a propósito** (no tiene
     requisitos de nivel).
   - Corpus B1–C2 al **14–20 %** de su objetivo declarado.
   - Escenarios A1/C1 = **1**.
   - **Cero audio humano grabado.**
   - No existe curso **Pre-A1** (0/7 celdas).
5. **Veredicto** — 2–3 líneas, distinguiendo «el contenido es escaso» de «la
   arquitectura no lo soporta».
6. **Regenerar / Verificar**.
7. **Tests que respaldan**.

## Tests: `backend/tests/test_ped_coverage_v370.py`

Tests requeridos (uno por hallazgo — todos pinnean **el hueco medido**, no una
esperanza):

- `test_every_mastery_modality_is_accounted_for` — las 9 modalidades de
  `MASTERY_SKILLS` aparecen en la matriz del dossier con sus cinco atributos.
- `test_reading_has_no_dedicated_scorer` — `backend/services/reading.py` **no
  existe** y, sin embargo, hay objetivos y checks que declaran `reading`
  (afirma los conteos medidos).
- `test_mediation_is_declared_but_inert` — `mediation` ∈ `MASTERY_SKILLS`, ∉
  `MODALITY_CHANNEL`, sin competencias en `COMPETENCES_BY_MODALITY`, sin corpus
  y sin feature de UI.
- `test_interaction_has_no_evidence_channel` — `interaction` ∉
  `MODALITY_CHANNEL` y sus competencias declaradas son la tupla vacía.
- `test_listening_corpus_meets_a1_a2_and_not_b1_c2` — usa
  `LISTENING_CORPUS_TARGETS` y el conteo real por nivel: A1/A2 al 100 %,
  B1–C2 por debajo del 25 %.
- `test_no_recorded_human_audio` — `load_manifest().entries == []` (pinnea que
  el audio es 100 % TTS; si algún día se graba, el test falla y obliga a
  actualizar el dossier).
- `test_pre_a1_has_no_course` — la banda `pre-a1` de
  `cefr_descriptors.CEFR_LADDER` existe pero no hay curso Pre-A1
  (`coverage by_level pre-a1 populated == 0`).
- `test_speaking_scenarios_extremes_are_thin` — A1 y C1 tienen exactamente 1
  escenario cada uno.

Convención: `from services import ...`; los tests son de **medición**, sin HTTP.

## Criterios de salida

1. `docs/audit/AB-PED-COBERTURA.md` creado con la plantilla completa.
2. `backend/tests/test_ped_coverage_v370.py` creado y **verde**.
3. `python -m ruff check .` limpio; `python -m pytest -q` verde con el total
   anterior + los nuevos.
4. `python -m scripts.audit_dossier skill-coverage` reproducible.
5. Cero ficheros de `backend/curriculum/**`, `backend/services/**`,
   `backend/data/**` o `frontend/**` modificados.

## Fuera de alcance

- Escribir `services/reading.py`, activar `mediation`, grabar audio humano,
  ampliar corpus o escenarios, crear el curso Pre-A1.
- Auditar adecuación CEFR (eje 1), feedback (eje 3), maestría (eje 4),
  instrumentos (eje 5).
