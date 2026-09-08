# L — Auditoría TOTAL externa V3.24.0: calibración de salida del Student Model (verificada sobre el código)

> Fecha: 2026-09-08 · Rol: **auditor externo (verificación read-only + cierre)**.
> Posición auditada: **main = `016f8b7`** (solo commit documental de cierre
> sobre el release) y **release v3.24.0 = `8970634`**. `VERSION = "3.24.0"`
> confirmado en `backend/config.py`. El commit de main posterior al release es
> únicamente documental, por lo que la implementación auditada es la publicada.
> Método: plantilla `docs/audit/TEMPLATE.md`, dossier K (v3.23.0) como línea
> base de los pendientes que V3.24 declara cerrar (F-K1/F-K2/F-K8) y aplazar
> (F-K3..F-K7), más verificación claim → `archivo:línea` y reproducción de la
> batería de tests núcleo.
>
> Cadena auditada: **Evidence → Mastery → Assessment 2.0 → CEFR Matrix →
> Estimated Level → Academy (matrículas)**, más el Student Model léxico en su
> relación con la capa académica, la semántica `estimated`/`demonstrated` en
> el contrato frontend y las fronteras explícitas de V3.24.

## Alcance

- **Se audita**: el gate MASTERED (`mastery_evidence_gate`), la nueva escala
  continua Pre-A1(0.5)–C2(6.0) y `estimated_level` anclado (F-K2), el salto
  A1→A2 completo (F-K8), `certification_gate` y `ladder_status`, la matriz
  CEFR multidimensional, los escritores reales de `evidence_kind`, el modelo
  léxico agregado y la semántica UI del nivel estimado/demostrado.
- **NO se audita** (fronteras declaradas V3.24): F-K3 (doble vía speaking
  assessment/misión), F-K4 (band por destreza), F-K5 (colisión semántica
  transfer/retention), F-K6 (historia fina de eventos léxicos), F-K7
  (renombrado `appearances`/`exposures`) y el emisor real de `novel`. Sí se
  comprueba **si alguno de esos elementos aplazados provoca ya una
  incoherencia observable** en V3.24 (resultado en cada hallazgo).
- **Verificación de claims externos**: la auditoría externa otorgó 9,5/10 y
  declaró cerrados F-K1 y F-K2. Este dossier reproduce cada afirmación contra
  el código y clasifica el resultado (BUG REAL / RIESGO / DEUDA
  ARQUITECTÓNICA / MEJORA PEDAGÓGICA / MEJORA UX / NO PROBLEMA).

## Método

1. **Lectura previa**: `release-notes-v3.24.0.md`, `docs/RELEVO.md`
   (notas de cierre), dossier K (v3.23.0), `PLAN.md`, `CHANGELOG.md`.
2. **Punto de partida**: `git rev-parse HEAD` → `016f8b7` (punta main);
   `git log --oneline -3` confirma release `8970634` como padre inmediato;
   `git diff --stat f3739a9 8970634` delimita el cambio funcional V3.24.
3. **Verificación por trazado**: para cada claim se localizó el
   escritor/lector `archivo:línea`, se confirmó el test que fija el
   comportamiento y se reprodujo la batería núcleo (sección "Evidencia —
   Gates").
4. **Clasificación**: cada hallazgo se etiqueta con su naturaleza
   (BUG REAL / RIESGO / DEUDA ARQUITECTÓNICA / MEJORA PEDAGÓGICA /
   MEJORA UX / NO PROBLEMA) y severidad (P0–P3 / informativo).
5. Sin ejecución de Ollama/Whisper/Piper ni cambios de código en esta fase de
   verificación; la batería de tests se ejecuta tal cual (comandos citados).
   El plan V3.25 que sigue a este dossier (ficheros `PLAN.md` / `agentes/`)
   se elabora sobre estos hallazgos.

## Evidencia — Gates (resultados reales reproducidos)

| # | Gate (comando) | Resultado real | Veredicto |
|---|---|---|---|
| L1 | `cd backend; .venv\Scripts\python.exe -m pytest tests/test_adaptive.py tests/test_assessment_v2.py tests/test_cefr_matrix.py tests/test_lexicon.py tests/test_academy.py -q -p no:cacheprovider` | `185 passed, 1 warning (deprecación upstream httpx/starlette)` — exit 0 | ✔ reproducido |
| L2 | `git rev-parse HEAD; git log --oneline -3; git diff --name-only f3739a9 8970634` | HEAD `016f8b7` · release `8970634` padre · 27 ficheros tocados (cambio funcional concentrado) | ✔ reproducido |
| L3 | conteo estático `rg "^(\s*)(async )?def test_" backend/tests -g "test_*.py"` | **1457** funciones `test_` (coincide con la cifra declarada en release notes) | ✔ reproducido (declarado) |

**185 tests del núcleo V3.24 en verde, 0 fallos** (L1). La suite completa
(1457) no se ejecuta en esta verificación; el claim "1457 en verde" de las
release notes se corresponde con el conteo estático (L3) y con la batería
núcleo reproducida. Los claims de CI (workflows asociados al SHA), frontend
vitest 450, tsc y Vite **no son verificables desde el repositorio local** y se
marcan como *declarado, no reproducido* (igual que señaló la auditoría externa:
`statuses: []` en el endpoint público para `8970634`).

## Claims verificados contra el código (con test que los fija)

| Claim | Evidencia de código | Test que lo fija | Resultado |
|---|---|---|---|
| **L-C1** F-K1 cerrado: MASTERED ya no exige `novel` | `services/assessment_v2.py::mastery_evidence_gate` (416-445): checks `initial/practice/transfer/delayed`; `novel` solo en `counts` como señal. Constantes `MASTERY_EVIDENCE_REQUIREMENTS = {initial:1, practice:2, transfer:2, delayed:1}` (79-81) | `test_assessment_v2.py::test_mastery_evidence_gate_requires_full_ladder` (156-172): sin transfer → `missing`, sin delayed → `missing`, `novel not in missing`, con familiar×2+transfer×2+delayed → `met` | ✔ NO PROBLEMA (ver hallazgo F-L6) |
| **L-C2** F-K1: matriz CEFR con `novel_required = 0` | `curriculum/cefr_matrix.json`: 12 celdas macro (listening/speaking/reading/writing en B2/C1/C2) con `novel_required: 0` | `test_adaptive.py::test_readiness_b2_ready_with_transfer_without_novel` (165-188): B2 listening ready con transfer×2 y novel 0 | ✔ NO PROBLEMA |
| **L-C3** F-K2 cerrado: `estimated_level` anclado a completados + tramo actual | `services/adaptive.py::estimated_level(profile, *, current_level, completed_levels)` (64-135): `floor = CEFR_NUMERIC[mayor completado]` o `max(PRE_A1_NUMERIC, CEFR_NUMERIC[current]-1)`; `numeric = min(6, floor+overall)`; cap de etiqueta al nivel actual sin certificaciones (111-117). `PRE_A1_NUMERIC = 0.5` (45). `numeric_to_level` media-banda 1.5/2.5/… (49-62) | `test_adaptive.py::test_estimated_level_anchored_by_completed_levels` (45-68): `([], current_level="A2", completed_levels=("A1",))` → A1/numeric 1.0; con B1 completado + dominio alto B2 → ≥3.5 | ✔ NO PROBLEMA en el anclaje (ver hallazgo F-L3) |
| **L-C4** F-K2: sin completados nunca se reclama el siguiente nivel | `services/adaptive.py` cap `if CEFR_LEVELS.index(level) > index(current_level): level = current_level` (111-117) | `test_adaptive.py::test_estimated_level_without_completed_levels_never_claims_next` (71-81): dominio máximo en A1 → etiqueta A1, numeric ≤ 1.5 | ✔ NO PROBLEMA |
| **L-C5** F-K2: `build_student_model` deriva y propaga niveles | `domain/academy.py::build_student_model` (609-660): `completed_levels = tuple(e["level"] for e in enrollments if status=="completed")` (625-627); propaga a `estimated_level` (629-631) y `reassessment_due` (641-647). `_current_level_id` = matrícula más alta (580-591) | `test_academy.py::test_endpoint_student_model_empty` (1389-1408) | ✔ NO PROBLEMA |
| **L-C6** F-K8: E2E del salto A1→A2 | `test_academy.py::_dominate_a1` (1413-1428) + `test_endpoint_estimated_level_anchored_across_a1_exam` (1431-1471): dominar A1 → estimado A1, numeric < 2.0; aprobar examen → a1 completed, a2 matriculado, estimado A1, numeric 1.0 | L1 (pasa) | ✔ NO PROBLEMA (ver hallazgo F-L9) |
| **L-C7** `certification_gate` confía en presencia de `delayed` | `services/assessment_v2.py::certification_gate` (374-414): `certified = bool(exam_skills) and all(checks)` donde cada check es `delayed_by_skill >= 1` (399-402) | `test_assessment_v2.py::test_certification_gate_requires_delayed_per_skill` (97-128), `::test_ladder_level_certified_requires_retention_step` (133-153) | ✔ estructuralmente cierto, **mitigado** por escritor único (ver hallazgo F-L4) |
| **L-C8** La única vía de escritura de `delayed` valida ventana y ratio | `domain/academy.py::submit_assessment_v2` (1634-1666): enforcement R6-01 — `source_session_id` obligatorio, `retention_due` (≥7 días) y `stable` (≥0.9) → si no, 409 | `test_assessment_v2.py::test_assessment_v2_retention_rejects_before_window` (332) y `::test_assessment_v2_retention_rejects_unstable_ratio` (394) | ✔ NO PROBLEMA |
| **L-C9** `novel` no tiene emisor real | Ningún call site escribe `evidence_kind="novel"`: toda la evidencia pasa por `services/academy.py::evidence_from_items` (635-672) con default `"familiar"` o por `evidence_kind_for` (553-559) que solo devuelve `familiar/transfer/delayed`; `_record_evidence_validated` (411-437) valida kinds canónicos | `test_evidence_invariants.py` (novel válido como kind pero sin emisor, 126-128) | ✔ confirmado — frontera declarada correcta (ver F-L5) |
| **L-C10** `familiar`/`transfer` son contadores agregados sin garantía de experiencias distintas | `mastery_evidence_gate` lee `familiar>=2` (checks initial/practice 430-431); `transfer` crece por cada unit/progress/level completado (`evidence_kind_for`) sin `context_id`/`task_type` distintos | `test_assessment_v2.py::test_mastery_evidence_gate_requires_full_ladder` (156-172) (pasa con contadores, no con eventos) | ✔ RIESGO confirmado (F-L6) |
| **L-C11** `support_level` inexistente en V3.24 | grep en todo el backend: sin apariciones | — (ausencia) | ✔ confirmado como frontera (F-L7) |
| **L-C12** `ladder_complete` ≠ `level_certified` | `services/assessment_v2.py::ladder_status` (466-550): `ladder_complete` = avance desbloqueado (no exige retention); `level_certified` = `level` + `retention` en `completed_kinds` (539-543) | `test_assessment_v2.py::test_ladder_level_certified_requires_retention_step` (133-153) | ✔ NO PROBLEMA — diseño correcto |
| **L-C13** Matriz CEFR multidimensional con umbrales progresivos solo en macro-destrezas | `curriculum/cefr_matrix.json`: listening/speaking/reading/writing suben (0.60→0.85 etc., evidencia 2→6); vocabulary/grammar/interaction/mediation planas en 0.70/0.60/3 en todos los niveles | `test_cefr_matrix.py` | ✔ confirmado (F-L10) |
| **L-C14** Contrato frontend: `estimated_level`/`estimated_numeric` como nivel mostrado | `frontend/src/features/progress/ProgressScreen.tsx:142` (`EstimatedLevelBadge`), `HomeScreen.tsx:173`, `TodayPlan.tsx:233-243`, `TrayectoriaTab.tsx:69-70` / `JourneyScreen.tsx:70-71` (`estimated_band`); paneles de ruta distinguen `functional`/`demonstrated` (`SpeakingLevelPanel.tsx:146-187`, `ListeningLevelPanel.tsx:38`, etc.) | tests frontend existentes | ✔ base para F-L3 (semántica UI) |
| **L-C15** Separación LLM → evidencia → motores deterministas | Los LLM producen texto/checks; mastery/CEFR/adaptación corren en motores puros (`services/adaptive.py`, `assessment_v2.py`, `academy.py`); sin ruta "LLM decide nivel" | K dossier P4 + trazado de escritores | ✔ NO PROBLEMA — principio preservado |

## Las 4 preguntas del auditor (para V3.24)

### P1 — ¿Qué eventos se PIERDEN?

1. **Contexto fino de cada evidencia** (F-K6/F-K7 del dossier K, frontera V3.24):
   `academy_evidence` guarda `skill/item_type/difficulty/source/evidence_kind`
   pero **no** `context_id`/`activity_id`/`task_type`/`support_level`. Un
   `transfer` es "superar un peldaño" sin saber desde qué contexto/tarea. Sin
   impacto en el gate actual, pero bloquea transfer real (F-L6) y support
   level (F-L7).
2. **Recuperaciones demoradas del nivel léxico**: siguen sin entrar en la
   cadena académica (correcto por D5/E3); `retrieval_successes` acumula el
   mismo día (K dossier P3-1).

### P2 — ¿Qué se DUPLICA?

1. Nada nuevo en V3.24: el cambio de release no toca escritores de evidencia.
   `_record_evidence_validated` + validación siguen siendo el escritor único
   (K dossier §1).

### P3 — ¿Qué se MAL AGREGA?

1. **`numeric = floor + progress` mezcla dos escalas en la etiqueta**: con A1
   completado (`floor=1.0`) y overall de A2 al 50%, `numeric=1.5` →
   `numeric_to_level` devuelve **"A2"**, etiqueta que el frontend muestra como
   badge de nivel sin distinguir "A2 certificado" de "mitad del tramo A2".
   Internamente es coherente con la escala continua, pero la UI no lo
   diferencia (ver F-L3).
2. **El overall del nivel actual se usa como "progreso" sin ventana propia**:
   `overall_cefr_score` está acotado por los mínimos críticos
   (`CRITICAL_MINIMUMS` grammar/vocabulary 0.4, `services/academy.py:509-514`),
   de modo que un alumno con una destreza crítica baja no puede superar ese
   mínimo en el overall → progreso capado. Correcto para no certificar, pero
   conviene que la UI lo explique como "progreso en el tramo", no como nota.

### P4 — ¿Qué alimenta REALMENTE mastery?

Sin cambios en V3.24: mastery se mueve solo por `apply_objective_evidence` /
`apply_skill_evidence` (K dossier P4). La salida (estimated_level) sí cambió
de motor: ya no se proyecta el mastery de un único nivel al eje absoluto.

## Hallazgos

| # | Naturaleza | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|---|
| **F-L1** | NO PROBLEMA | — | **F-K1 cerrado correctamente.** El gate MASTERED ya no exige `novel`; la implementación es coherente con los kinds realmente emitidos (familiar/transfer/delayed). | `assessment_v2.py:416-445`, `79-81`; tests `test_assessment_v2.py:156-172`, `test_adaptive.py:165-204` | Mantener `novel` reservado hasta tener emisor real (F-L5). | cerrado en V3.24 ✔ |
| **F-L2** | NO PROBLEMA | — | **F-K2 cerrado correctamente.** El estimado se ancla a niveles completados; aprobar A1 y matricular A2 ya no devuelve Pre-A1 ni rebasa a B2. | `adaptive.py:64-135`; `domain/academy.py:609-660`; E2E `test_academy.py:1431-1471` | Mantener el cap de etiqueta por nivel actual sin certificación. | cerrado en V3.24 ✔ |
| **F-L3** | MEJORA PEDAGÓGICA / MEJORA UX | **P1** | **Semántica UI de `estimated_level` ambigua.** La etiqueta devuelta por `numeric_to_level` (media banda) se presenta como badge de nivel CEFR sin distinguir "nivel demostrado/certificado" de "estimación de tramo". Un alumno con A1 certificado y A2 al 50% ve **"A2"** (que puede leer como "tengo A2") cuando el modelo quiere decir "he completado A1 y voy por la mitad de A2". El contrato expone `estimated_numeric` (1.5) y `current_level`, pero la UI solo muestra la etiqueta. | `adaptive.py:49-62` (`numeric_to_level`) + `64-135`; `ProgressScreen.tsx:142`, `HomeScreen.tsx:173`, `TodayPlan.tsx:233-243`, `TrayectoriaTab.tsx:69-70` | Separar en la UI y en el contrato del Student Model: `demonstrated_level` (certificado), `estimated_level` + `estimated_numeric` (banda continua) y progreso del tramo (p. ej. "A2 · 50%"). Es el P1-04 de la auditoría externa. | abierto (V3.25) |
| **F-L4** | RIESGO (robustez) | P2 | **`certification_gate` confía en la existencia de `delayed`, no en su edad/ratio.** Correcto estructuralmente porque el único escritor de `delayed` (submit retention) valida ventana ≥7 días y ratio ≥0.9 con 409 en caso contrario (`domain/academy.py:1634-1666`). Es una invariante de pipeline, no una verificación directa en el gate. | `assessment_v2.py:374-414`; `domain/academy.py:1634-1666`; tests `test_assessment_v2.py:332/394` | Endurecer el gate para que verifique edad/ratio desde las filas (o un `retention_metric` derivado) si en V3.25 se abren más escritores de `delayed` (p. ej. retention multi-intervalo F-L8). | abierto (V3.25, robustez) |
| **F-L5** | NO PROBLEMA (frontera correcta) | — | **`novel_required = 0` bien decidido, con matiz documental.** No exigir `novel` sin emisor es correcto; pero `novel` sigue en `EVIDENCE_KIND_WEIGHTS` con peso 0.5 (`services/academy.py:705`) y en `counts` como señal, por lo que conviene dejar explícito que C1/C2 no están "demostrados" solo con familiar+transfer+delayed. | `services/academy.py:698-708`; `mastery.py:174`; `evidence_depth.py:44,103`; `cross_skill.py:112`; `course.py:231` | Documentar en schemas/UI que la evidencia de niveles altos deberá incorporar `novel` + `independent` cuando exista emisor (V3.25+). | informativo |
| **F-L6** | RIESGO (pedagógico) | P1 | **`familiar×2` y `transfer×2` no demuestran dos experiencias independientes.** `familiar≥2` satisface a la vez `initial` y `practice`; `transfer` crece con cada peldaño completado sin garantizar contexto/tarea/actividad distintos. Dos transfers casi idénticos (misma actividad, mismo formato) cuentan como 2. La frontera no bloquea MASTERED, pero diluye su significado. | `assessment_v2.py:427-443` (checks sobre el mismo contador), `553-559` (`evidence_kind_for`); K dossier (SKILL-01/GRAPH-01) | Convertir en V3.25 `transfer_count ≥ N` en `distinct_transfer_contexts` con `context_id`/`activity_id`/`task_type`, y exigir para `familiar×2` dos experiencias separadas (no el mismo check repetido). Es el P1-02 de la auditoría. | abierto (V3.25) |
| **F-L7** | DEUDA ARQUITECTÓNICA | P1 | **Falta `support_level` en el evento de evidencia.** Sin distinguir `copied/guided/cued/independent/spontaneous`, una producción con plantilla y opciones múltiples pesa igual que una producción libre. Bloquea la mejora pedagógica más importante pendiente. | grep backend: sin apariciones de `support_level` | Añadir `support_level` al modelo de eventos y declarar el nivel por emisor (formative = guided/cued, speaking libre = independent, etc.). P1-01 de la auditoría. | abierto (V3.25) |
| **F-L8** | MEJORA PEDAGÓGICA | P2 | **Retención longitudinal: `delayed` es binario por destreza.** Un único reassessment estable certifica; no hay intervalos (D+1/D+3/D+7/D+21) ni métrica de estabilidad longitudinal. Suficiente para V3.24 (validación posterior al examen), pobre como modelo de retención. | `assessment_v2.py` (`RETENTION_MIN_DAYS=7`, `RETENTION_STABLE_RATIO=0.9`, gate) | V3.25: infraestructura de intervalos + `certification_gate` leyendo métricas derivadas (F-L4). P1-03 de la auditoría. | abierto (V3.25) |
| **F-L9** | MEJORA DE UX | P3 | **El E2E A1→A2 domina objetivos artificialmente.** `_dominate_a1` (respuestas perfectas directas) es un E2E del motor, no un recorrido de usuario (formative→unit→progress→exam). Valioso para fijar la regresión, insuficiente como prueba de journey. | `test_academy.py:1413-1428` | Añadir en V3.25 un E2E de recorrido completo por la escalera real + otro con retención simulada (7+ días) hasta certificación. | abierto (V3.25, tests) |
| **F-L10** | MEJORA PEDAGÓGICA (calibración futura) | P2 | **Matriz CEFR: macro-destrezas progresivas, dimensiones de soporte planas.** Vocabulary/grammar/interaction/mediation mantienen el mismo suelo (0.70/0.60/3) en A1..C2; deliberado por falta de calibración, pero no debe leerse como modelo CEFR definitivo (C1/C2 necesitarán precisión, registro, error density, turn-taking, mediación real). | `curriculum/cefr_matrix.json` | Calibración progresiva en V3.26+; documentar la frontera mientras tanto. | abierto (V3.26+) |
| **F-L11** | DEUDA ARQUITECTÓNICA | P2 | **El modelo léxico sigue agregado por palabra.** `vocabulary` guarda contadores y últimos timestamps; la historia fina vive en `learning_events`. `appearances`/`exposures` (naming heredado F-K7) y `transfer`/`retention` léxicos colisionan semánticamente con la capa académica (F-K5). Sin impacto en la cadena académica (D5/E3). | `repositories/vocabulary.py`; `services/lexicon.py:468-472` (deuda comentada); `schemas/vocabulary.py` | V3.25: renombrado `appearances→production_count`/`exposures→exposure_count` y documentación del mapeo léxico vs académico. | abierto (V3.25) |
| **F-L12** | NO PROBLEMA (declarado, no reproducido) | — | **Claims de CI/frontend/E2E no verificables localmente.** El release declara 1457 tests backend (coincide con L3), ruff limpio, 450 vitest, tsc, Vite y Playwright verdes; el endpoint público para el SHA de release devuelve `statuses: []`/`workflow_runs: []`. | `release-notes-v3.24.0.md`; L3 | Verificación en CI real; documentar los workflows por SHA (P3 de la auditoría externa). | informativo |

### Estado de los hallazgos del dossier K en V3.24

| Ítem dossier K | Estado en V3.24 | Evidencia |
|---|---|---|
| F-K1 (novel sin emisor → gate MASTERED inalcanzable) | **cerrado** ✔ | L-C1/L-C2/F-L1 |
| F-K2 (estimado descalibrado, rebase al matricular) | **cerrado** ✔ | L-C3/L-C4/L-C5/F-L2 |
| F-K3 (doble vía speaking assessment/misión) | **sigue abierta** (frontera V3.24); sin incoherencia nueva en la cadena (la evidencia de misión sigue sin mover el score de destreza, como en v3.23) | K dossier; fronteras de release notes |
| F-K4 (band por destreza sin marca de estimado) | **sigue abierta** (frontera V3.24); agravada por F-L3 (la etiqueta global `estimated_*` ya se muestra sin marca en la UI) | L-C14; frontend |
| F-K5 (colisión semántica transfer/retention léxica vs académica) | **sigue abierta** (frontera V3.24); sin efecto en V3.24 porque las capas no se cruzan | F-L11 |
| F-K6 (historia fina de eventos léxicos) | **sigue abierta** (frontera V3.24) | F-L11 |
| F-K7 (renombrado `appearances`/`exposures`) | **sigue abierta** (frontera V3.24) | F-L11 |
| F-K8 (sin cobertura E2E del salto de nivel) | **cerrado** ✔ | L-C6/F-L2 (con el matiz F-L9) |

## Veredicto

**APROBADO PARA CIERRE DE LOS DOS P1 DEL DOSSIER K (v3.24.0) — con tres
frentes abiertos para V3.25 que no bloquean esta versión.**

La auditoría externa otorgó 9,5/10; la verificación sobre el código confirma
sus dos cierres centrales: **F-K1** (el gate MASTERED se relaja a lo emisible
`familiar×2 + transfer×2 + delayed`, con `novel` reservado y sin emisor real —
L-C1/L-C2) y **F-K2** (el nivel estimado se ancla a niveles completados y al
tramo actual, eliminando el rebase B2→Pre-A1 al aprobar el examen A1 — L-C3 a
L-C5, reproducido por el E2E F-K8 en L-C6). La separación completar/certificar
(`ladder_status`), la retención como validación posterior (no bloqueo del
avance) y el determinismo del Student Model (LLM nunca decide nivel) siguen
siendo correctos.

No hay ningún BUG REAL demostrado en V3.24. Los pendientes son de calibración
pedagógica y robustez: **(F-L3)** la semántica UI de `estimated_level` puede
leerse como "nivel certificado" cuando es "banda estimada de tramo" (P1),
**(F-L6)** `familiar×2/transfer×2` no garantizan experiencias independientes
(P1), **(F-L7)** falta `support_level` por evento (P1 arquitectónico), y en
P2: robustez de `certification_gate` (F-L4), retención longitudinal (F-L8) y
la deuda léxica de naming/modelo agregado (F-L11). Los aplazados F-K3..F-K7 no
provocan incoherencia nueva demostrable en V3.24, pero F-K4 se agrava con
F-L3.

**Recomendación**: V3.25 como fase de calibración profunda del Student Model
(support_level + transfer/retention reales + semántica estimated/demonstrated
en UI + modelo de eventos), antes de añadir funcionalidad nueva de superficie.

## Regenerar / Verificar

```powershell
git rev-parse HEAD                  # 016f8b7 (main, solo documental)
git log --oneline -3                # release v3.24.0 = 8970634 (padre)
git diff --stat f3739a9 8970634     # delta funcional V3.24
cd backend
# Batería núcleo V3.24 (L1)
.venv\Scripts\python.exe -m pytest tests/test_adaptive.py tests/test_assessment_v2.py tests/test_cefr_matrix.py tests/test_lexicon.py tests/test_academy.py -q -p no:cacheprovider
# Conteo estático de tests backend (L3)
rg "^(\s*)(async )?def test_" tests -g "test_*.py" | Measure-Object | Select-Object -ExpandProperty Count
```

Resultados reproducidos: L1 **185 passed** · L3 **1457** funciones `test_` ·
release notes v3.24.0 reproducidas contra el código en los claims L-C1..L-C15.

## Tests que respaldan

- `test_adaptive.py` — estimado anclado (45-81), readiness B2 sin novel
  (165-204), usuario vacío → Pre-A1/0.5 (34-43).
- `test_assessment_v2.py` — gate MASTERED sin novel (156-172), certificación
  por delayed por destreza (97-128), ladder complete≠certified (133-153),
  retention window/ratio (175-181, 332, 394).
- `test_academy.py` — E2E A1→A2 (1413-1471), estudiante vacío (1389-1408),
  examen completa/desbloquea/certifica (515-583).
- `test_cefr_matrix.py` / `test_lexicon.py` — matriz con novel_required 0 y
  semántica léxica (L1).
