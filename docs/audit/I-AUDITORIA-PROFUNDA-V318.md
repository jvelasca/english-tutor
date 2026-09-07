# Dossier — Auditoría profunda de V3.18 (read-only) · lista P0/P1/P2 previa a V3.19

> Fecha: 2026-09-07 · Rol: auditor interno read-only (runbook
> `agentes/auditoria-profunda-v318.md`). Posición auditada: **v3.18.0**
> (HEAD `661d7b3`, `backend/config.py::VERSION = "3.18.0"`, árbol limpio).
> Método y plantilla: `docs/audit/TEMPLATE.md`. Objetivo: producir la lista
> priorizada de deuda y las entradas de diseño para la redefinición de V3.19,
> sin cambiar código ni versión.

## Alcance

- **Qué se audita (código por código):** A1 Núcleo Academy/dominio/repaso por
  unidad · A2 Evidence Graph/FSRS/léxico · A3 Speaking/evaluación oral/
  pronunciación · A4 Writing/conversación guiada/cross-skill · A5 Assessment 2.0
  y contenido CEFR (bancos) · A6 Frontend (rutas y claims pedagógicos).
- **Qué NO se audita** (fronteras honestas ya declaradas en auditorías previas):
  ejecución física en dispositivos, variabilidad LLM con Ollama real, audio
  humano real, calibración con alumnos reales. El micro-review/micro-drill se
  revisaron solo por invariantes de mecanismo (D5/E3), no por su contenido.
- **Sin cambios normativos:** la CONSTITUCIÓN no se toca; R8/R9 quedan como
  propuesta abierta para el diseño V3.19.

## Método

1. Seis subagentes read-only en paralelo (A1–A6), cada uno con su checklist
   común (premisas 13 y 21, R1–R7, determinismo, single-writer, append-only,
   claims por destreza) y el lente V3.19 (Recognition → Production → Transfer).
2. Cada hallazgo con `archivo:línea` real (leído/verificado) y su test de
   respaldo (leído antes de citar) o "sin test".
3. Los hallazgos P1 más críticos fueron **re-verificados por el gerente** sobre
   el código antes de consolidar:
   - `V318A1-01` gating: `routers/academy.py:96-160` solo llama
     `enrollment_blocked` (nivel); ningún endpoint valida objetivo `locked`.
   - `V318A5-01` retención: `assessment_v2.py:370-408` (`certification_gate`
     cuenta solo presencia de filas `delayed`) y `:440-455` (`retention_due`
     definida pero no usada en el arranque); `domain/academy.py:1439-1566`
     arranca la retención sin ventana y el submit escribe `delayed` con
     `evidence_kind_for(kind)` sin comprobar ratio estable.
   - `V318A6-01` claim oral: `SpeakingLevelPanel.tsx:146-147`
     (`demonstrated = assessedLevel === level`, EMA sin gate de retención).

## Evidencia por área (veredictos de los subagentes)

| Área | Nota | Resumen del veredicto | Hallazgos |
|---|---|---|---|
| A1 Academy/dominio | 8/10 | Mastery por objetivo y repaso I2/O1/M4/O3/H6 correctos y fijados; confirmada la tesis V3.19 (ningún submit vuelca al léxico) | 1×P1, 2×P2, 2×P3 |
| A2 Evidence/FSRS/léxico | 7/10 | FSRS M4 y evidence depth correctos; modelo léxico sin destreza ni modalidad; señal sin consumidor | 1×P1, 4×P2, 2×P3 |
| A3 Speaking/pronunciación | 8,5/10 | LLM=extractor, scorer determinista, 503 sin puntuar en falso; producción oral nunca llega al léxico | 1×P1, 5×P2/P3 |
| A4 Writing/conversación/cross-skill | 7/10 | Scoring honesto; ninguna producción escrita vuelca al léxico; modalidad oral/tecleado no distinguible | 2×P1, 4×P2, 1×P3 |
| A5 Assessment/contenido CEFR | 7,5/10 | Assessment 2.0 y bancos C1/C2 sólidos; retención R6 sin enforcement; foco listening A1/A2 no servible | 1×P1, 3×P2, 3×P3 |
| A6 Frontend claims/rutas | 6,5/10 | Honestidad estructural buena; claim "demostrado" oral sin gate y chips de drill inertes | 1×P1, 1×P2, 2×P3 |
| Auditoría externa v3.18 | — | V319-09 (ADMIN_PIN fail-closed) y V319-10 (bool-as-int) → deuda diferida a V3.19 | 1×P1, 1×P3 |

## Lista consolidada P0/P1/P2 → decisión

Leyenda de decisión: **(a)** deuda a corregir al implementar V3.19 (o antes) ·
**(b)** entrada de diseño para la redefinición V3.19 · **(c)** descartado/informativo
con rationale.

### P0 — Ninguno confirmado

No se encontró ningún hallazgo P0 (bug pedagógico máximo que rompa premisas de
forma activa). El más cercano es **R6-01** (abajo): el motor escribe evidencia
`delayed` con una garantía temporal que no impone, lo que acopla dos conceptos
que la CONSTITUCIÓN §6.3 separa. Se mantiene P1 top con nota de "candidata a
P0" para decidir al priorizar V3.19.

### P1 — Corregir en/antes de V3.19

| ID | Fuente | Dónde (verificado) | Hallazgo | Decisión |
|---|---|---|---|---|
| **R6-01** | V318A5-01 | `domain/academy.py:1439-1566`, `services/assessment_v2.py:370-408,440-455` | La retención (R6) no se impone en servidor: `start_assessment_v2(kind="retention")` no llama a `retention_due`; el submit escribe `evidence_kind="delayed"` el mismo día y sin ratio estable `≥ 0.9`; `certification_gate`/`level_certified` solo cuentan presencia de `delayed`. Contradice la CONSTITUCIÓN §6.3 y el propio docstring de `assessment_v2.py:63-68`. Un alumno puede salir `certified` sin ventana de ≥7 días ni estabilidad. **Candidata a P0** (R2/R6 en el motor). | **(a)** imponer la ventana y el ratio en arranque/submit + test HTTP de rechazo (hoy `test_assessment_v2.py:285-335` fija que retención el mismo día responde 200) |
| **GATE-01** | V318A1-01 | `routers/academy.py:96-160,265-374`, `services/course.py:56-95` | El gating curricular (`available`/`review`/`locked`) solo se *expone* (`objective_gated_status`); ningún endpoint de intento/evaluación/completar lección valida el objetivo y un `locked` es evaluable por API directa. Contradice la letra de la premisa 21. Sin test que fije el rechazo (`test_academy.py:802-842` solo fija nivel bloqueado). | **(a)** validar en dominio (punto único) antes de evaluar → 403/409 + test con objetivo `locked` |
| **CLAIM-01** | V318A6-01 | `frontend/.../SpeakingLevelPanel.tsx:146-147,187-195`, `PronunciationLevelPanel.tsx:132`, `ConversationLevelPanel.tsx:132`, i18n `speaking.demoTitle/demoMet` | La UI muestra "Nivel oral demostrado / {level} Speaking — demostrado" derivado de `assessedLevel === level` donde `assessedLevel` es el EMA de `/speaking/level` (`services/speaking.py:1154-1191`, sin gate de retención). Convive con `demoRequires` ("no de esta ruta") en la misma pantalla; listening solo muestra "demostrado" con estado real del backend. Dos semánticas de "demostrado". | **(a)** re-etiquetar a "nivel oral actual (examen)" con calificador estimado, o engancharlo a un `demonstrated` real; replicar esquema listening |
| **SIGNAL-01** | V318A2-01 (+ A4-07, A6-02) | `services/lexicon.py:273-284`, `PersonalDictionary.tsx:77,137-161`, i18n `dictionary.recognizedNotProducedHint`, `routers/chat.py:66,100` | `recognized_not_produced` se calcula sobre `appearances` = palabras *tecleadas* en el chat libre; la UI afirma "aún no produces / candidatas a practicar hablando" (producción oral) sobre un modelo que no sabe nada de producción oral; chips inertes sin acción. Claim de UI por encima del backend (R5). | **(a)** corregir la copia hoy; **(b)** en V3.19 la señal pasa a `spoken==0` real (P0) y el chip gana acción (P1) |
| **PROD-01** | V318A3-01 + V318A4-01 | `domain/academy.py:868,1078,2901-3185`, `domain/speaking_routes.py:276-330`, `domain/pronunciation_routes.py:86-140`, `services/writing.py` | Confirmado en código: **ningún** flujo real de producción (speaking rutas/assessment/misión, pronunciación, writing) vuelca el texto del alumno al léxico; el chat libre es la única vía (`useChat.ts:518` → `/api/vocabulary/analyze`). Es exactamente el problema P0 que el candidato V3.19 declara. | **(b)** es el P0 de V3.19 (volcado por destreza); invariante: agregados actuales no cambian de semántica |
| **WR-UI-01** | V318A4-02 | `routers/academy.py:348-382`, grep frontend | Los endpoints `objective/writing` (y `objective/speaking`) existen con test pero ningún flujo UI los llama; la evidencia de writing solo se crea por llamada directa. Caveat ya declarado en RELEVO V3.19. | **(b)** decidir en V3.19 si writing entra por estos endpoints (y cablear UI) o por otra superficie real |

### P2 — Prioridad media

| ID | Fuente | Dónde | Hallazgo | Decisión |
|---|---|---|---|---|
| CAP-01 | V318A1-02 | `domain/academy.py:868-...3185` | El texto del alumno (`heard`/`text`) se descarta tras puntuar (no se persiste; única excepción: `heard` de misión en el JSON del intento). Un volcado V3.19 no puede ser retroactivo. | **(a)** captura en submit-time (punto único, ver REFAC-01) |
| REFAC-01 | V318A1-03 | `domain/academy.py` (≥7 bloques) | Patrón `read → next_mastery_state → apply_objective_evidence` duplicado en assessment/speaking/task/writing/pronunciation/assessment_v2. Añadir el volcado léxico a cada bloque por separado = alto riesgo de divergencia. | **(a)** extraer helpers compartidos antes de V3.19; el volcado se añade en 1 lugar |
| LEX-01 | V318A2-02 | `repositories/db.py:93-106,550-601` | Modelo léxico de una fila por `(user_id, word)` con contadores agregados; sin columna de destreza/modalidad; `source` solo `user`/`curriculum` (valor `imported` sin escritor). No puede alojar el desglose sin migración. | **(b)** entrada de diseño P0: columna por destreza o ledger; decidir histórico previo |
| LEX-02 | V318A2-03 | `repositories/vocabulary.py:15-72`, rutas de práctica | La señal léxica (estado, coverage, candidatos, cartas FSRS lexicon) vive solo del chat libre; la práctica académica (rutas MC, dictado CP, reading) no genera exposiciones ni producción. | **(b)** alimentar el léxico desde evidencia académica y submit_*; decidir si la exposición de ítems de ruta cuenta |
| LEX-03 | V318A2-04 | `domain/academy.py:1708-1739`, `services/lexicon.py:216-234` | `sync_fsrs_cards` siembra cartas `lexicon` para semillas curriculares `appearances=0/exposures=0` (status `learning`), ensuciando la cola de repaso con ítems sin señal (la evidencia de la ruta que SÍ superó el alumno no llega a la fila). | **(b)** no sembrar sin evento real o graduar desde la evidencia académica |
| GRAPH-01 | V318A2-05 | `services/evidence_graph.py:159-308` | El grafo no distingue reconocimiento de producción dentro de una destreza: `dimension_scores` mezcla REC con CP/FP y "transfer" = `evidence_kind`, no modalidad. Un transfer gap real por modalidad no es expresable. | **(b)** `dimension_scores` consume producción por destreza; GRAPH_VERSION subirá |
| TOK-01 | V318A3-02 | `services/speaking_llm.py:265-309`, `services/speaking.py:791-858`, `services/writing_llm.py:123-126` | El LLM extrae `lexical_tokens` ("palabras usadas correctamente") y el pipeline las descarta: no entran al scorer ni se persisten (único consumidor real: writing para un criterio). Sería la señal exacta "produjo y usó bien la palabra". | **(b)** persistir `lexical_tokens` **validados contra el transcripto** por tokenizador determinista; decidir si "uso correcto" lo declara el LLM o el motor |
| SKILL-01 | V318A3-03 | `domain/academy.py:813-838,1055-1101`, `services/speaking.py:861-936` | Evidencia de práctica (misión) y formal (assessment) se mezclan en el mismo pool `skill=speaking` con `objective_id=""`; el nivel se estampa al del alumno (no al `cefr_target` de la tarea); toda evidencia es `familiar` → depth máx. MEDIUM. | **(a)** registrar `cefr_target`/`difficulty` y separar source en la agregación del claim |
| ERR-01 | V318A3-04 | `domain/academy.py:899-907,1091-1095`, `routers/academy.py:476,499,755,826` | En misiones/assessment/task el fallo transitorio del extractor se responde 404 (indistinguible de sesión inválida); en rutas es 503 reintentable. Al añadir micro-drill con LLM local la semántica debe ser uniforme. | **(a)** traducir fallo de extracción a 503 en esos flujos; reservar 404 a estados reales |
| USE-01 | V318A3-05 | `domain/academy.py:913-915`, `services/speaking.py:313`, `services/phonetics.py:64-98` | Ningún componente distingue "produjo la palabra" de "la usa correctamente" (la cobertura de read-aloud basta con producir; la señal de uso correcto, `lexical_tokens`, se descarta). Insumo del micro-drill de 3 niveles. | **(b)** señal explícita por nivel de uso en V3.19, sin confundirla con el score de pronunciación |
| CONV-01 | V318A4-03 | `domain/conversation_routes.py:92-127,197-261`, `repositories/conversations.py:178` | `submit_attempt` reconstruye turnos sin mirar `mode` (oral vs tecleado); la conversación guiada real es un mini-chat tecleado y `duration_ms` mide tiempo de redacción → `turn_duration` interpreta tecleo como turno oral. | **(a)** reconstruir por `mode`/telemetría; excluir `turn_duration` cuando no sea oral |
| CONV-02 | V318A4-04 (+ A4-06) | `domain/conversation_routes.py:238-244` | El intento de conversación guiada no escribe `academy_evidence` ni alimenta la dimensión `interaction`; la señal de interacción no se persiste como evidencia propia. Sin camino hacia la evidencia FP que exige la CONSTITUCIÓN §7 para Interaction. | **(b)** decidir si conversación emite evidencia o se documenta como práctica sin acceso al modelo (D5/E3) |
| CP-01 | V318A4-05 | `services/cross_skill.py:169-222`, `services/evidence_depth.py:32-37` | Los CP superados viven en `grammar_route_attempts` y no alimentan `production_count` (academy_evidence); posible divergencia matriz "producida" vs Student Model con producción=0. | **(a)** documentar o unificar la doble vía de "producción" al cablear léxico por destreza |
| LIST-01 | V318A5-02 | `services/curriculum.py:158-167`, `services/listening.py:13-29`, `listening_corpus.json` | El foco declarado A1/A2/B1 (`word_recognition`/`sound_recognition`/`phrase_recognition`) no es servible: esos tokens no son `skill` válido en el corpus (0 ítems) y la validación los descarta. La progresión existe solo como etiqueta de objetivos. | **(a)** añadir tokens a `LISTENING_SUBSKILLS` o mapeo foco→skill + etiquetar muestra A1/A2 con test "≥1 ítem servible por nivel del foco" |
| LIST-02 | V318A5-03 | `listening_corpus.json` (c141/c316/c011/c021/c007) | Desajuste etiqueta-vs-contenido sistemático en A1/B1: ítems etiquetados `attitude`/`inference`/`speaker_intention` con guion de comprensión explícita; C1/C2 muestreados sí respaldan su etiqueta. | **(a)** auditar/re-etiquetar A1–B1 y añadir campo `reduced_forms` |
| LIST-03 | V318A5-04 | `listening_corpus.json` (c031/c086, c027/c079) | Pares cuasi-duplicados en B1/B2 (los bancos más pequeños) inflan la diversidad efectiva; sin test de unicidad de script. | **(a)** test de unicidad de `script` normalizado + sustituir un miembro del par |

### P3 / menores (para registrar, no bloquean)

| ID | Fuente | Hallazgo | Decisión |
|---|---|---|---|
| ADMIN-01 | V319-09 (auditoría externa) | `config.py:47` + `dependencies.py:19`: `ADMIN_PIN=""` deja los endpoints admin **abiertos** (fail-open). Secure-by-default exige fail-closed. | **(a)** `ADMIN_PIN=""` → endpoints admin deshabilitados; tests de `test_audio_qa.py:170-196` a adaptar |
| BOOL-01 | V319-10 (auditoría externa) | `services/unit_review.py:325,356,371`: `isinstance(selected, int)` admite `True` como índice; endurecer a `type(selected) is int`. | **(a)** fix P3 junto a V3.19 |
| A1-04 | V318A1-04 | `domain/academy.py` ~3.500 líneas orquesta mastery+repaso+sesión+assessment_v2+FSRS; extraer módulos propios para el volcado de producción. | **(b)** al crecer la captura de producción, extraer módulo |
| A1-05 | V318A1-05 | Getters/updaters de sesión por `id` sin `user_id` en el WHERE (el dominio verifica ownership; defensa en profundidad). | **(a)** añadir `user_id` al WHERE |
| A2-06 | V318A2-06 | Clasificadores duplicados (`services/vocabulary.py:39-43` vs `services/lexicon.py:33-37`); endpoints con lecturas distintas. | **(a)** unificar o test de paridad al tocar V3.19 |
| A2-07 | V318A2-07 | `recognized_not_produced` y el coverage del lexicon sin consumidor backend; señal replicada en frontend (`dictionary.ts:22-26`). | **(b)** mover la señal a endpoint determinista en V3.19 (premisa 21) |
| A3-06 | V318A3-06 | Sin guard de transcripto vacío en flujos LLM abiertos (silencio → `""` puede puntuar); pronunciación sí lo tiene (`test_pronunciation.py:17-21`). | **(a)** guard de mínimo de tokens antes de extraer (422/400) |
| A3-07 | V318A3-07 | G2P ~90 entradas A1/A2 con fallback letra-a-letra; el proxy fonémico se degrada fuera del vocabulario. Al reutilizar el scorer en el drill, no confundir con producción espontánea. | **(c)** documentar; límites de claim en niveles altos |
| A5-05 | V318A5-05 | Versiones desalineadas: `speaking_scenarios.json` 2.0.0 vs `SPEAKING_SCENARIOS_VERSION=3.0.0`; `listening_corpus.json` 3.0.0 vs `LISTENING_BANK_VERSION=7.0.0`. Riesgo de trazabilidad. | **(a)** un único origen de verdad o test JSON.version==constante |
| A5-06 | V318A5-06 | Mecánica de banco corto correcta (`QUIZ_SHORT_BANK=12`), pero el ejemplo de CONSTITUCIÓN §6.4 ("Grammar B2=8/C2=4") quedó desactualizado (hoy 14/15) y **reading C2 = 6 checks** es el único banco corto real sin test que fije su lectura `low`. | **(a)** actualizar el ejemplo normativo; decidir si reading C2 se amplía o se documenta como banco corto intencional |
| A5-07 | V318A5-07 | Sin curso Pre-A1 (confirmado); la banda Pre-A1 es transitoria. Sin acción. | **(c)** documentar §7.1 |
| A6-03 | V318A6-03 | `PersonalDictionary` sin estado de error: si `getLexicon` falla, "Cargando…" infinito. | **(a)** error + reintento (patrón del resto de paneles) |
| A6-04 | V318A6-04 | `listening.routeGateIntro` dice "Para certificar {level} necesitas:" y lista solo la puerta (la retención aparece después); lectura posible "superar puerta = certificar". | **(a)** reescribir el titular para no confundir puerta con certificación |

## Veredicto global

**Aprobado con matices (v3.18) — la deuda real está en el modelo de producción,
no en la mecánica.** El núcleo (mastery por objetivo, repaso por unidad
I2/O1/M4/O3/H6, FSRS single-writer, evidence depth, assessment v2 como
instrumento) es correcto y está bien fijado por tests. No hay P0 confirmado.
Los hallazgos P1 que más importan para V3.19 son dos y son de **pedagogía de
fondo**: la retención R6 no se impone en servidor (R6-01) y la UI afirma
"demostrado" oral sin gate (CLAIM-01); a ellos se suma el gating de objetivo no
validado (GATE-01). El resto de la lista confirma —ahora con evidencia
`archivo:línea`— el problema base del candidato V3.19: **el Student Model léxico
no sabe nada de producción oral/escrita** y la práctica académica real no
alimenta la señal léxica. La redefinición de V3.19 debe apoyarse en este dossier
para cerrar el diseño (eventos léxicos → destreza → transfer gap → micro-drill 3
niveles → integración con el grafo) antes de codificar, y debe incluir los fixes
(a) marcados.

## Regenerar / Verificar

```powershell
git log --oneline -3          # HEAD 661d7b3 (v3.18.0)
# Gates de la posición (reproducibles, no modificados por esta auditoría):
cd backend; .venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider   # 1345
.venv\Scripts\python.exe -m ruff check .
cd frontend; npm test          # vitest 414
npm run build                  # tsc + vite build
```

## Tests que respaldan (principales)

- `backend/tests/test_unit_review.py` + `test_unit_review_endpoints.py`
  (I2/O1/M4/O3/H6, aislamiento), `test_session_graph.py` (H6 lazy),
  `test_academy.py` (mastery por objetivo, decay, aislamiento),
  `test_evidence_graph.py` + `test_golden_evidence_graph.py` (grafo),
  `test_fsrs.py` + `test_golden_fsrs.py` (FSRS), `test_lexicon.py` +
  `test_vocabulary.py` (léxico), `test_golden_pedagogy.py` +
  `test_pedagogical_invariants.py` (R7/evidence depth),
  `test_speaking_routes.py:565-599` (503 sin puntuar en falso),
  `test_conversation_routes.py` (puerta honesta), `test_writing.py` (scoring
  determinista), `test_assessment_v2.py:285-335` (hoy fija retención el mismo
  día = 200; a re-apuntar en R6-01), `test_golden_listening.py` +
  `test_listening_corpus.py` (contenido listening),
  vitest `UnitReviewPanel.test.tsx`, `learningLabels.test.ts`,
  `dictionary.test.ts`.
