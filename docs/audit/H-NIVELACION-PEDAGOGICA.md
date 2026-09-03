# H — Auditoría del modelo de nivelación pedagógica (V3.2)

> Dossier desk (documental). No genera artefactos `docs/audit/generated/`.
> Fecha: 2026-09-03. Relación con el freeze: posterior a la fase A–G de
> `docs/BETA_V3.md` (§4.1–§4.4). Complementa `B-LISTENING-CEFR.md` y
> `D-ASSESSMENT-READINESS.md` desde el ángulo del *modelo conceptual de nivel*,
> no del contenido. La especificación normativa que propone este dossier vive en
> `docs/CONSTITUCION-PEDAGOGICA.md`.
>
> **Actualización (v3.4.0):** los P1 5–7 de la Constitución (§9) se ejecutaron en
> backend. Estado de los hallazgos: H1–H5 **cerrados**; H6 y H7 **parciales**
> (pendientes de P2). El detalle está en la columna "Estado" de cada hallazgo
> (los *estados observados* de este dossier describen la foto V3.2.1 previa a
> esa iteración).
>
> **Actualización (v3.3.0):** los P0 de la Constitución (§9) se ejecutaron en
> backend. Estado de los hallazgos: H1, H2 y H3 **cerrados**; H5, H6 y H7
> **parciales**; H4 abierto.

## Alcance

- **Qué se audita:** cómo decide la aplicación qué nivel tiene un alumno y qué
  muestra la UI al respecto. Concretamente: las dos fuentes de nivel (modelo
  heurístico `services/cefr.py` y Student Model vivo), la relación entre práctica,
  mastery, nivel estimado y nivel certificado, el papel del vocabulario, la
  conexión del listening con el Student Model, la cobertura de la matriz de
  requisitos CEFR y la honestidad de los textos visibles.
- **Qué NO se audita:** calidad del contenido/corpus (fase A), calibración del
  corpus de listening (dossier B), calibración de speaking (C), escalera de
  evaluación (D), scheduler FSRS (E), UX/recorrido de pantallas (F).
- **Criterio de referencia:** el modelo conceptual definido en la sección 2 de
  `docs/CONSTITUCION-PEDAGOGICA.md` (Practice Level / Mastery / Estimated CEFR /
  Demonstrated CEFR) y la premisa 21 de `docs/PREMISAS.md`.

## Método

1. **Instrumentos:** inspección documental con citas `ruta:línea`; búsquedas
   dirigidas (`rg`) de símbolos de nivelación en `backend/` y `frontend/src/`.
   No se ejecutaron instrumentos automáticos nuevos (auditoría desk acordada).
2. **Muestreo:** modelo completo Pre-A1→C2 en sus dos implementaciones; sin
   muestreo de ítems (no depende del contenido).
3. **Criterios:** tabla de conceptos de la Constitución (sección 2 de
   `docs/CONSTITUCION-PEDAGOGICA.md`) y premisas 21 (`docs/PREMISAS.md`).

## Evidencia

| Dimensión | Estado observado | Fuente (cita) |
|---|---|---|
| Modelo heurístico 5 señales (legacy) | Implementado, **no cableado** a endpoints | `backend/services/cefr.py:180-253`; solo tests `test_cefr_evaluation.py`, `test_profile.py` |
| Student Model vivo (estimado) | Es la fuente real del nivel mostrado | `backend/domain/academy.py:558-594` (build_student_model) |
| "Palabras → banda CEFR" | Solo en módulo legacy y en recomendación `<150` | `backend/services/cefr.py:68-88`; `backend/services/cefr.py:265-278` |
| Certificación de nivel | Binaria: examen MCQ `min_per_skill=0.75` (o escalera Assessment 2.0, dossier D) | `backend/domain/academy.py:2747-2818`; `backend/services/curriculum.py:331-336` |
| Puerta de ruta listening | Cobertura/precisión/temas/subskills/checkpoint, **aislada** del Student Model | `backend/services/listening.py:925-948`, `1309-1390` |
| Retención | Modelada (curva + buckets + ventana 7d), sin gate en el examen | `backend/services/forgetting.py:18-22`; `backend/services/assessment_v2.py:58-63` |
| Matriz de requisitos CEFR | Solo A1–B2 × 4 macro-destrezas | `backend/curriculum/cefr_matrix.json` |
| UI: claims de nivel | Honesta en listening; `estimated_level` crudo en badges | `frontend/src/utils/i18n.ts:1166-1190`; `frontend/src/features/home/HomeScreen.tsx:172,204` |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| H1 | alta | La interpretación "cantidad de palabras → banda CEFR" sigue viva en el módulo legacy (`VOCABULARY_BAND_EDGES` 150/400/900/1900/3000/5000 y `MIN_SAMPLES["vocabulary"]=50`) y **los tests la fijan como norma** (`vocabulary_band(149)==Pre-A1`, `vocabulary_band(150)=="A1"`). Aunque hoy ningún endpoint la cablea, es una bomba de relojería conceptual: el
mecanismo en sí — derivar un nivel de un contador de palabras — contradice la
Constitución (sección 3), y los tests lo fijan como norma de modo que cualquier
reconexión futura lo resucitaría. | `backend/services/cefr.py:29-37,68-88,180-253`; `backend/tests/test_cefr_evaluation.py:113-124` | P0: eliminar/archivar el bloque palabras→banda y sus tests; si se conserva, renombrar a "indicador léxico" sin semántica CEFR | cerrado en v3.3.0 (P0-1) |
| H2 | alta | No existe el par **Estimado vs Demostrado** ni estados por competencia (NOT STARTED/DEVELOPING/FUNCTIONAL/DEMONSTRATED). La búsqueda de `demostrado` no halla nada; el único `functional` es un *topic* declarado en el corpus de audio, no un estado del modelo. Los estados existentes son `readiness_band` (ready/approaching/developing), `dimension_state` (mastered/in_progress/not_started) y `mastery_stage` (acquire→…→retention), todos con semántica distinta. | `backend/services/adaptive.py:115-147`; `backend/services/adaptive.py:260-277`; `backend/services/mastery.py:115-136` | P0: definir los 4 estados por competencia en la Constitución y un registro `demonstrated` separado del estimado | cerrado en v3.3.0 (P0-2: registro por competencia en `/api/profile.competence_states`) |
| H3 | alta | El listening de práctica no escribe evidencia en el Student Model: `POST /api/listening/*` solo registra un learning event (`record_event`) y escribe `listening_attempts`; no crea `academy_evidence` ni actualiza mastery de la destreza. La puerta `route_gate` (coverage≥80 %, accuracy≥70, ≥3 topics, ≥3 subskills, checkpoint) es el candidato natural a Mastery Gate de la competencia, pero **no alimenta** el nivel estimado global. | `backend/routers/listening.py:80-129`; `backend/services/listening.py:1309-1390`; `backend/domain/academy.py:498-523` (subskills solo decorativos) | P0: cablear evidencia de listening (gate por competencia) al modelo de destreza | cerrado en v3.3.0 (P0-4: `route_competence` + estado por ruta en el Student Model y en `/api/listening/stats`) |
| H4 | media | `cefr_matrix.json` solo define requisitos A1–B2 y solo para las 4 macro-destrezas; C1/C2 y grammar/vocabulary/pronunciation caen al fallback plano (`READINESS_MINIMUMS`) sin gate transfer/novel. No hay requisitos por subskill en ningún nivel. | `backend/curriculum/cefr_matrix.json`; `backend/services/adaptive.py:115-147` | P1: extender la matriz a C1/C2 y a las 8 destrezas; declarar subskills mínimos por competencia | cerrado en v3.4.0 (P1-5): matriz `cefr_matrix.json` 2.0.0 con los 6 niveles × las 8 destrezas de la Constitución §7, gates por destreza y evidencia por kind (transfer/novel desde B1); `pronunciation` queda por diseño como componente de Speaking (fallback plano). La declaración explícita de mínimos por subskill sigue abierta (se resuelve por competencia con `SUBSKILLS` del currículo) |
| H5 | media | La retención está modelada en tres niveles (curva exponencial por ítem/destreza, buckets delayed `0-2/2-7/7-30/30+`, ventana de reassessment ≥7d con ratio ≥0.9) pero **no es gate del examen de nivel** (el `retention` de V2 se evalúa aparte y el `checkpoint` de listening es primera-exposición, no retención retardada). | `backend/services/forgetting.py:18-22`; `backend/services/listening.py:1688-1793`; `backend/services/assessment_v2.py:58-63,337-360` | P1: definir "retención demostrada" (≥7 días, delayed vs immediate) como componente del Mastery Gate | parcial en v3.3.0 (listening DEMONSTRATED exige retención estable ≥7 días; el examen de nivel sigue sin retención, P1) → **cerrado en v3.4.0 (P1-6)**: la certificación de nivel pasa a exigir retención retardada por destreza del examen ("completado ≠ certificado", `certification_gate` + `CertificationOut`), y en la escalera el nivel se certifica solo con el peldaño `level` + el retention reassessment (`level_certified`) |
| H6 | media | Coexisten tres "mastery" con significados distintos en la API: la tabla legacy `academy_skill_mastery` (`GET /api/academy/mastery`), los `MasteryRecord` transversales (`student-model.mastery`, 9 destrezas) y el mastery por can-do del Evidence Graph (no persistido). | `backend/domain/academy.py:457-464`; `backend/services/mastery.py:199-211`; `backend/services/evidence_graph.py:257-288`; `backend/domain/academy.py:1593` (la escalera V2 también escribe `academy_skill_mastery`) | P1: unificar la terminología y declarar una sola fuente de "mastery por competencia" | parcial en v3.3.0 (endpoint legacy `/api/academy/mastery` retirado; `student-model.mastery` es la fuente expuesta; la tabla sigue como detalle interno de examen/escalera, P1) |
| H7 | media | La UI muestra el nivel estimado **crudo** (`LevelBadge` con "A1") en Home y Progreso, y el bloque de bandas por destreza de `LearningProfile` puede leer "A1" en una destreza mientras el global dice `Pre-A1` (incoherencia: `heuristic_band(0.0)="A1"`, nunca emite Pre-A1). La honestidad que sí existe está solo en listening (`routeNote`, `routePendingCert`, tooltip de bandas). | `frontend/src/features/home/HomeScreen.tsx:172,204`; `frontend/src/features/progress/ProgressScreen.tsx:142`; `backend/domain/profile.py:63-77` + `backend/services/cefr.py:156-177` | P2: etiquetar siempre el estimado ("estimado, no certificado"), emitir Pre-A1 también en bandas por destreza cuando no hay evidencia, y reservar "demostrado" para los gates | parcial en v3.3.0 (banda por destreza sin evidencia = "—", P0-3; etiquetado UI y `modeCefrLevel`/`modeCefrBand` pendientes, P2) |

## Veredicto

**Aprobado con matices (diagnóstico).** El modelo es honesto en la superficie —
las rutas de listening ya se releen como práctica con puerta y la UI matiza que no
es certificación CEFR — pero **no sabe responder "qué ha demostrado el alumno"**:
no existe el concepto de nivel demostrado por gates (Practice/Mastery/Estimado/
Demostrado), la práctica de listening no alimenta el Student Model, la
interpretación palabras→nivel sobrevive en un módulo legacy con tests que la
defienden, y la matriz de requisitos llega solo a B2. La corrección es conceptual
y debe fijarse como especificación (Constitución) antes de tocarse el código.

## Regenerar / Verificar

```powershell
# Auditoría desk: no hay instrumento automático. Verificación manual de citas:
rg -n "VOCABULARY_BAND_EDGES|evaluate_cefr" backend --type py
rg -n "route_gate|ROUTE_MIN_" backend/services/listening.py
rg -n "demostrado|functional|readiness_band" backend --type py
```

## Tests que respaldan (comportamiento actual, a revisar en los incrementos)

- `backend/tests/test_cefr_evaluation.py:113-124` — fija el mapeo palabras→banda (bloquea H1).
- `backend/tests/test_profile.py:38-60,134,259` — usa el modelo legacy y `estimated_bands`.
- `backend/tests/test_listening.py:155-223` — fija `route_gate`/`level_status` (base de H3).
- `backend/tests/test_pedagogy.py:108-183` — gates de unidad y tríada (referencia de estados).
- `frontend/src/features/listening/listeningSession.test.ts` — modo level/drill (superficie de H3).
- `frontend/src/utils/modes.test.ts` — fija `modeCefrLevel/modeCefrBand`, código **sin uso** en componentes (H7).
