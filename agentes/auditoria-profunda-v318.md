# Runbook — Auditoría profunda de V3.18 → lista P0/P1/P2 previa a V3.19

> Fecha: 2026-09-07 · Rol: **auditor interno read-only** (gerente + subagentes
> autocontenidos). Objetivo: auditar **código por código** la posición v3.18.0
> antes de diseñar/implementar V3.19, y producir una lista priorizada
> P0/P1/P2 de deuda previa + entradas de diseño para V3.19. Sigue el método y
> la plantilla `docs/audit/TEMPLATE.md` de las auditorías v3.16/v3.17/v3.18.

## 0. Contexto y por qué existe esta auditoría

La auditoría externa de v3.18 (veredicto: **APROBADO CON OBSERVACIONES**) pide
explícitamente **no implementar V3.19 todavía**: el siguiente salto de calidad no
es más infraestructura, sino demostrar que el Student Model representa lo que el
alumno sabe hacer (Recognition → Production → Transfer). Antes de codificar hay
que cerrar el diseño (eventos léxicos → evidencia por destreza → transfer gap →
speaking micro-drill → integración con el Evidence Graph).

Esta auditoría entrega el **mapa real del código actual** con hallazgos
`archivo:línea` y su test de respaldo, para que la redefinición de V3.19 y la
lista de deuda previa se apoyen en evidencia y no en inferencia.

**Decisiones ya tomadas (no se reabren):**
- No se cambia la versión (`backend/config.py::VERSION = "3.18.0"` se mantiene).
- No se modifica código de producción; solo se escribe en `docs/audit/`.
- Hallazgos `V319-09` (ADMIN_PIN fail-closed) y `V319-10` (bool-as-int) quedan
  registrados como deuda a implementar junto a V3.19 (no ahora).
- El candidato V3.19 actual (`docs/RELEVO.md` final + `PLAN.md`) queda congelado
  durante esta auditoría; las entradas de diseño que surjan se marcan como
  "alimenta redefinición V3.19", sin ejecutarlas.

## 1. Cómo arrancar (auditor, contexto nuevo)

Lee en orden:
`docs/PREMISAS.md` (en especial 5, 12, 13 y 21),
`docs/CONSTITUCION-PEDAGOGICA.md` (§1.1 R1–R7, §2 estados, §3.2 lexical units,
§6.3 retención, §6.4 evidence depth, §7 modalidades REC/CP/FP y estructura por
destreza), `docs/RELEVO.md` (solo Notas superiores + entradas 37.34–37.36 +
sección final "Próximos incrementos"), `PLAN.md`, y los dossieres de mecanismo
`docs/FSRS.md`, `docs/EVIDENCE_GRAPH.md`, `docs/ASSESSMENT_2.md`,
`docs/SPEAKING_MISSION.md`, `docs/LISTENING_CURRICULUM.md`.

Confirma el punto de partida:
```powershell
git log --oneline -3          # HEAD esperado: 661d7b3 (v3.18.0)
git status --short            # limpio
```

## 2. Método

1. Cada área A1–A6 se audita con un subagente read-only autocontenido.
2. Ejes de revisión transversales (aplican a todo hallazgo):
   - **Mecanismo:** puntuación/decisiones en servidor (premisa 21), determinismo,
     single-writer, append-only, aislamiento por usuario (premisa 13), sin
     claims de dominio desde mecanismos de práctica (D5/E3).
   - **Constitución:** R1 (practice ≠ mastery), R2 (mastery ≠ certificación),
     R5 (recognition ≠ production), R6 (éxito ≠ retención), R7 (muestra pequeña
     ≠ competencia demostrada); FUNCTIONAL como techo de práctica; bancos cortos
     ≤ `QUIZ_SHORT_BANK` (12) leen depth LOW.
   - **Lente V3.19** (marcar como entrada de diseño, NO cambiar código): dónde la
     producción léxica llega hoy solo del chat libre (`useChat` →
     `/api/vocabulary/analyze` → `domain.vocabulary.analyze_text` →
     `record_words`); qué `submit_*` reciben texto del alumno y no lo vuelcan al
     léxico; si `recognized_not_produced` (`services/lexicon.py`) tiene
     consumidor; huecos de "tests pedagógicos" (p. ej. high recognition / low
     production → qué debería derivar el modelo).
   - **Cobertura:** qué test fija cada comportamiento crítico (citar archivo) y
     qué comportamiento crítico NO está fijado.
3. Cada hallazgo se reporta en formato uniforme (sección 5) y **solo se escribe
   en `docs/audit/`** al consolidar.

## 3. Severidad (escala del proyecto)

- **P0** — contradice PREMISAS o CONSTITUCIÓN (bug pedagógico de prioridad
  máxima), o rompe aislamiento/dominio del motor determinista.
- **P1** — bug real de correctez/seguridad o claim que la UI muestra por encima
  de lo que el backend sustenta; requiere acción antes de V3.19.
- **P2** — deuda que conviene corregir al implementar V3.19 (no bloqueante).
- **P3** — endurecimiento técnico/menor o mejora opcional.

## 4. Áreas de auditoría (archivos y tests de respaldo)

### A1 — Núcleo Academy, dominio y repaso por unidad
- Archivos: `backend/domain/academy.py` (~3.200 líneas; dueño A1),
  `backend/domain/learning.py`, `backend/services/unit_review.py`,
  `backend/services/adaptive.py`, `backend/services/quiz_routes.py`,
  `backend/repositories/academy.py`, `backend/repositories/db.py` (esquema,
  migraciones idempotentes, `unit_review_anchors`, FKs),
  `backend/routers/academy.py`, `backend/schemas/academy.py`.
- Enfocar: mastery por objetivo y consistencia (premisa 21), gating curricular,
  ancla congelada I2, cascade O1, cartas `objective` single-writer M4, plan por
  niveles O3, coste lazy H6, y TODOS los `submit_*` de producción
  (`submit_speaking`, `submit_speaking_task`, `submit_speaking_assessment_part`,
  `submit_speaking_mission_attempt/retry`, `submit_writing`,
  `submit_writing_task`) → ¿dónde va el texto del alumno? ¿Llega al léxico?
- Tests: `test_unit_review.py`, `test_unit_review_endpoints.py`,
  `test_session_graph.py`, `test_graph_plan.py`, `test_academy.py`,
  `test_academy_goal.py`, `test_adaptive.py`, `test_course.py`,
  `test_mastery.py`, `test_learning_events.py`, `test_domain_async.py`,
  `test_evidence_invariants.py`, `test_competence.py`, `test_pedagogy.py`,
  `test_pedagogical_invariants.py`, `test_foreign_keys.py`.

### A2 — Evidence Graph, FSRS y léxico (señal sin consumidor)
- Archivos: `backend/services/evidence_graph.py`, `backend/services/fsrs.py`,
  `backend/services/lexicon.py`, `backend/domain/vocabulary.py`,
  `backend/services/vocabulary.py`, `backend/repositories/vocabulary.py`,
  `backend/routers/vocabulary.py`, `backend/services/evidence_depth.py`,
  `backend/services/cefr_matrix.py`.
- Enfocar: fuente de verdad del grafo (`rank_weakness_objectives` y nodos),
  dimensiones vs subskills; FSRS (targets skill/lexicon/objective, cola due,
  exclusiones M4); **modelo léxico actual**: columnas de `vocabulary`
  (fuente, kind, appearances, producción), `recognized_not_produced` y `coverage
  indicator`; ¿dónde y cómo se etiqueta "producción"? ¿distingue destreza
  (hablada/tecleada)? Ledger/append-only de eventos.
- Tests: `test_evidence_graph.py`, `test_golden_evidence_graph.py`,
  `test_fsrs.py`, `test_golden_fsrs.py`, `test_lexicon.py`,
  `test_vocabulary.py`, `test_vocabulary_routes.py`,
  `test_evidence_invariants.py`, `test_store_append_only.py`.

### A3 — Speaking, evaluación oral y pronunciación
- Archivos: `backend/services/speaking.py`, `speaking_routes.py`,
  `speaking_assessment.py`, `speaking_llm.py`, `speaking_scenarios.py`,
  `speaking_mission.py`, `speaking_generate.py`, `backend/domain/speaking_routes.py`,
  `backend/services/pronunciation_routes.py`, `backend/domain/pronunciation_routes.py`,
  `backend/services/pronunciation.py`, `backend/services/interaction.py`.
- Enfocar: pipeline LLM→evidencia (qué se extrae, qué se descarta), scorer de
  pronunciación (proxy honesto), separación lexical production vs pronunciation,
  modalidades FP reales, `submit_attempt` de speaking y de pronunciación (¿llega
  al léxico?), intentos no puntuados en falso (503 transitorio).
- Tests: `test_speaking.py`, `test_speaking_routes.py`,
  `test_speaking_assessment.py`, `test_speaking_llm.py`,
  `test_speaking_scenarios.py`, `test_speaking_mission.py`,
  `test_golden_speaking.py`, `test_pronunciation.py`,
  `test_pronunciation_routes.py`, `test_pronunciation_academy.py`,
  `test_phonemes.py`, `test_interaction.py`.

### A4 — Writing, conversación guiada y cross-skill
- Archivos: `backend/services/writing.py`, `writing_llm.py`,
  `backend/domain/conversation_routes.py`, `backend/services/conversation_routes.py`,
  `backend/services/cross_skill.py`, `backend/services/interaction.py`.
- Enfocar: si la producción escrita llega al léxico por destreza; reconstrucción
  de turnos de conversación guiada; bindings CP→estructura en los 6 niveles
  (`PRODUCTION_BINDINGS_BY_LEVEL`); matriz cross-skill (¿qué demuestra cada
  celda, REC o CP?).
- Tests: `test_writing.py`, `test_writing_llm.py`, `test_conversation_routes.py`,
  `test_conversations_interaction.py`, `test_interaction.py`,
  `test_cross_skill.py`.

### A5 — Assessment 2.0 y calidad de contenido CEFR (bancos)
- Archivos: `backend/services/assessment_v2.py`, `backend/services/curriculum.py`,
  `backend/services/cefr.py`, `backend/curriculum/*.json` (a1–c2, assessments,
  `listening_corpus.json`, `speaking_corpus.json`, `speaking_assessment.json`,
  `speaking_scenarios.json`, `pronunciation_corpus.json`,
  `conversation_corpus.json`, `cefr_matrix.json`, `cefr_descriptors.json`).
- Enfocar: escalera de evaluaciones y readiness; **progresión real de Listening**
  por nivel (A1 word recognition → A2 specific info → B1 connected speech/implicit
  → B2 inference → C1/C2 reduced forms/irony/pragmatics): ¿el corpus respalda la
  taxonomía o solo la declara? checks MC oficiales que usa el micro-review como
  muestra; bancos cortos (≤12); coherencia versión de bancos vs constantes.
- Tests: `test_assessment_v2.py`, `test_golden_assessment.py`,
  `test_cefr_descriptors.py`, `test_cefr_matrix.py`, `test_cefr_semantics.py`,
  `test_listening_corpus.py`, `test_listening_architecture.py`,
  `test_golden_listening.py`, `test_listening_retention.py`,
  `test_curriculum_*.py`, `test_content_quality.py`, `test_bank_wiring.py`,
  `test_golden_pedagogy.py`.

### A6 — Frontend: rutas y claims pedagógicos
- Archivos: `frontend/src/features/routes/QuizRoutePage.tsx`,
  `features/speaking/SpeakingRoutesPractice.tsx`, `SpeakingPanel.tsx`,
  `SpeakingAssessment.tsx`, `SpeakingMission.tsx`, `SpeakingScenarios.tsx`,
  `features/listening/ListeningRecorridoPanel.tsx`, `ListeningLevelPanel.tsx`,
  `features/vocabulary/VocabularyRoutesPractice.tsx`, `PersonalDictionary.tsx`
  (chips `recognizedNotProduced`, hoy sin acción),
  `features/grammar/GrammarRoutesPractice.tsx`,
  `features/pronunciation/PronunciationRoutesPractice.tsx`,
  `features/conversation/ConversationRoutesPractice.tsx`,
  `features/writing/WritingPanel.tsx`, `features/review/UnitReviewPanel.tsx`,
  `frontend/src/api/` (cliente, `getJsonNullable`), tipos, `utils/learningLabels.ts`,
  i18n `es`/`en`.
- Enfocar: que la UI **nunca** afirme mastery/certificación donde el backend solo
  da práctica (R1/R2/R5 en pantalla); estados vacíos/carga/error; viabilidad de la
  futura acción "Speaking micro-drill" en `PersonalDictionary`.
- Tests: vitest asociados a cada feature (`*.test.ts(x)`), parity i18n.

## 5. Formato uniforme de hallazgo

Cada subagente devuelve una tabla/lista con:

```
ID: V318A-<area>-NN          # A1..A6
Sev: P0|P1|P2|P3
Dónde: <archivo>:<línea>     # y archivo de test que lo fija o "sin test"
Qué: <descripción del problema, 1-3 frases>
Lente V3.19: <cómo afecta a léxico por destreza / transfer gap / micro-drill /
             tests pedagógicos, o "no aplica">
Recomendación: <acción concreta propuesta>
```

Prohibido: inventar líneas, APIs o tests inexistentes; si un archivo no se
encuentra, decirlo y seguir (nunca alucinar la ruta).

## 6. Entregables de la auditoría (los consolida el gerente)

1. Este runbook (`agentes/auditoria-profunda-v318.md`).
2. Dossier consolidado `docs/audit/` siguiendo `docs/audit/TEMPLATE.md`
   (alcance, método, evidencia por área, hallazgos, veredicto por área,
   "Regenerar / Verificar") con la **lista P0/P1/P2 final** y cada hallazgo
   mapeado a una decisión: (a) deuda a corregir al implementar V3.19,
   (b) entrada de diseño para la redefinición V3.19, o (c) descartado con
   rationale. Incluye V319-09 y V319-10 como deuda diferida.
3. Registro en `PLAN.md` y `docs/RELEVO.md` (deuda priorizada previa a V3.19;
   versión sigue 3.18.0).

## 7. Restricciones

- **Solo lectura** en código y BD de producción. No ejecutar nada que dependa de
  Ollama/Whisper/Piper (el LLM real es frontera honesta). No instalar
  dependencias ni lanzar migraciones. BD de tests = temporales (`pytest`).
- No cambiar la CONSTITUCIÓN (R8/R9 son propuesta a decidir en el diseño V3.19).
- No escribir fuera de `docs/audit/` salvo el registro de estado acordado
  (PLAN/RELEVO).
