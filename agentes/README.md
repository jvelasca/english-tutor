# Cómo lanzar los subagentes (sin gastar tokens)

El gerente del proyecto (el asistente) **no ejecuta** estos subagentes. Tú los
lanzas desde tus propios agentes locales. Cada subagente es un archivo Markdown
**autocontenido**: incluye todo lo que el agente necesita para trabajar sin
pedir más contexto.

> **Estado actual (2026-09-11): `v3.52.2`** — ver `docs/RELEVO.md` (nota superior
> y sección 0 "START HERE"). V3.52.2 cierra los **dos P2 de la auditoría externa
> Q** (`docs/audit/Q-AUDITORIA-TOTAL-V352.md`): `CEFR_CAPACITY` pasa a ser el
> **envelope monótono** del banco real (con el invariante «todo contexto del banco
> encaja en su propio nivel con tolerancia estricta») y la tolerancia queda
> documentada como red de seguridad con test de inercia y de discriminación
> sintética; la etiqueta `v3.52.1` ya está creada. La release V3.52.1 sigue siendo
> el **hotfix de producto** (usuarios fantasma «Visual Tester», «RUTA ACTUAL» de
> Listening y bucle A/B) que cerró el **P1-01** de la auditoría de V3.52. Release
> verificada: **CI 6/6 en verde** (runs
> [34622637688](https://github.com/jvelasca/english-tutor/actions/runs/34622637688)
> sobre `89eff0b` y [34623244239](https://github.com/jvelasca/english-tutor/actions/runs/34623244239)
> sobre `bdaaff9`). V3.52.2 también verificada: **CI 6/6 en verde** (run
> [34627238005](https://github.com/jvelasca/english-tutor/actions/runs/34627238005)
> sobre `a5e2d38`, pytest **2164 passed + 2 skipped**). La **auditoría externa de
> V3.52 ya está ejecutada** (informe Q,
> sin P0/P1) y su briefing se conserva como histórico del método. Los P3-01/P3-02
> quedan abiertos y aceptados. El siguiente incremento es **V3.53 (P1-02 Learner
> Skill State 2.0 + `observed_difficulty` persistido por evento) y su briefing YA
> ESTÁ ESCRITO Y LISTO PARA LANZAR**: `agentes/v353-learner-skill-state.md`
> (2026-09-11). Sin briefing todavía: P1-03 (Planner 2.0 / Expected Learning
> Value), Sense Engine 2.0, `assessed_skill`→planner y `skill_priorities`→
> `select_task` (V3.55) y la entrega oral real del transfer. Antes de
> lanzar cualquier subagente, lee esa sección para no partir de un estado obsoleto
> (premisa 8 y 12: relevo al saturar y ancla contra la alucinación).

## Cómo usar un subagente

1. Abre el archivo `agentes/<nombre>.md`.
2. Copia su contenido completo y pégalo como prompt en tu agente local
   (o ábrelo como archivo de contexto/tarea en tu agente).
3. El agente local trabaja y devuelve el resultado.
4. Pega el resultado de vuelta aquí; el gerente revisa e integra o genera el siguiente paso.

## Estado de la biblioteca de briefings

- `agentes/v353-learner-skill-state.md` — **V3.53 (LISTO PARA LANZAR, escrito
  2026-09-11 sobre `v3.52.2`)**: cierra el candidato **P1-02** (Learner Skill
  State 2.0 + `observed_difficulty` persistido por evento). Parte A: persistir el
  `difficulty_vector` del contexto SERVIDO en el evento de transferencia
  (columna aditiva `learning_evidence.observed_difficulty`, vector canónico con
  `format_vector`/`parse_vector` puros). Parte B: capacidad observada por
  modalidad y dimensión (`observed_signals` con muestra/días espaciados) →
  `services/learner_skill.py` (nivel equivalente + capacidad del alumno) →
  fuente `observed` en `LEVEL_SOURCES` (entre `demonstrated` y `estimated`) y
  caché O(1) en `learning_profile`, con **no-regresión exhaustiva** cuando no hay
  datos. NO toca `CEFR_CAPACITY`, la escalera, el scoring ni FSRS; el planner no
  la consume (eso es P1-03). **Pendiente de ejecutar.**
- `agentes/v3522-cierre-p2-auditoria-q.md` — **no existe**: V3.52.2 (**ejecutado
  directamente por el gerente**, 2026-09-11) se resolvió sin briefing separado,
  como V3.38.1 y las FASES 1–5. Cierra los **dos P2** de la auditoría Q
  (`CEFR_CAPACITY` = envelope monótono del banco + invariante de encaje por
  nivel; tolerancia documentada como red de seguridad con test de inercia y de
  discriminación sintética) y crea la etiqueta `v3.52.1`. **Histórico, hecho**;
  ver `release-notes-v3.52.2.md` y `docs/audit/Q-AUDITORIA-TOTAL-V352.md`.
- `agentes/v3521-hotfix.md` — **V3.52.1 (ejecutado, 2026-09-11, v3.52.1)**: hotfix
  de producto (usuarios fantasma «Visual Tester» con guarda `users.is_test`,
  «RUTA ACTUAL» de Listening y bucle A/B) + cierre del P1-01 de la auditoría
  externa de V3.52 (cobertura dimensional en `difficulty.fit`). **Histórico,
  hecho**; ver `release-notes-v3.52.1.md`.
- `agentes/auditoria-externa-v352.md` — **auditoría EXTERNA de V3.52.1
  (EJECUTADA, 2026-09-11)**: prompt autocontenido para un auditor que solo ve
  GitHub (árbol `bdaaff9`, base tag `v3.52.0`/commit `23cbad7`, runs de CI 6/6),
  con punto de entrada, contexto de los dos P1 de V3.51 + el delta del hotfix
  V3.52.1, alcance dentro/fuera, método reproducible, 17 preguntas concretas
  (política del suelo, calibración de `CEFR_CAPACITY` **contra el banco real**,
  semántica de `challenge_vector`/`fit`, tolerancias, determinismo, O(1) del
  camino caliente, paridad GET↔POST, contrato aditivo, cobertura de tests y el
  delta del hotfix) y formato de informe. **Informe entregado**:
  `docs/audit/Q-AUDITORIA-TOTAL-V352.md` → **sin P0/P1**; 2 P2 (calibración de
  `CEFR_CAPACITY` frente al banco y tolerancia por fuente hoy inerte con la
  justificación invertida) y 3 P3, recomendados para V3.53.
- `agentes/auditoria-externa-v350.md` — auditoría EXTERNA de V3.50.0
  **ya entregada y resuelta** (sus tres P1 se cerraron en V3.51.0; V3.50 la dejó
  como briefing «listo para lanzar»). Se conserva como histórico del método.
- `agentes/v352-student-state-difficulty.md` — **V3.52 (ejecutado, 2026-09-11,
  v3.52.0)**: Student level state (separación `practice`/`estimated`/`demonstrated`
  con el demostrado como suelo, migración aditiva de `learning_profile` y lectura
  O(1) en el drill) + Difficulty Engine 2.0 por dimensión (`CEFR_CAPACITY`,
  `challenge_vector`, `fit`, `select_by_difficulty` con degradación por mínima
  distancia). Cierra los dos P1 de la auditoría externa de V3.51. **Histórico,
  hecho**; ver `release-notes-v3.52.0.md`.
- `agentes/v351-task-skill-semantics.md` — **V3.51 (ejecutado, 2026-09-11,
  v3.51.0)**: Task/Skill semantics (separación `target_skill`/`assessed_skill`/
  `assessment_mode`/`evidence_skill` con el transfer midiendo producción ESCRITA,
  columna aditiva `learning_evidence.assessed_skill`) + vector completo
  `planner.skill_priorities` + dificultad anclada al nivel DEMOSTRADO del alumno
  (suelo) sin perder el CEFR del ítem (techo). Cierra los tres P1 de la auditoría
  externa de V3.50. **Histórico, hecho**; ver `release-notes-v3.51.0.md`.
- `agentes/v350-context-skill-mapping.md` — **V3.50 (ejecutado, 2026-09-11,
  v3.50.0)**: Context→Skill mapping (cada contexto declara qué competencias
  ejercita y `context_for` prioriza la modalidad limitante) + difficulty matching
  por banda derivada del CEFR del ítem, sin migración, sin tocar la escalera
  `transfer_state` ni el gate. Cierra el candidato diferido por V3.49.0.
  **Histórico, hecho**; ver `release-notes-v3.50.0.md`.
- `agentes/v348-context-bank.md` — **V3.48 (ejecutado, 2026-09-11, v3.48.0)**:
  Context Bank 2.0 (banco de 6 → 20 contextos con cobertura A1–C2, 6 originales
  congelados) + diversidad 2.0 informativa (`register`/`lexical_environment`/
  `syntactic_focus` en `context_diversity.variety`, sin entrar en el gate de
  evidencia). Cierra los P2-04/P2-05 de la auditoría de V3.43.0. **Histórico,
  hecho**; ver `release-notes-v3.48.0.md`.
- `agentes/v347-transfer-evidence-cefr.md` — **V3.47 (ejecutado, 2026-09-11,
  v3.47.0)**: Transfer Evidence 2.0 (escalera endurecida: ≥2 éxitos no andamiados
  para `transfer_demonstrated`, 3 días + 2 objetivos para `transfer_stable`) +
  CEFR/`difficulty_vector` del contexto (banco etiquetado y `context_for(level)`).
  Cierra los dos P1 de la auditoría de V3.46.0. **Histórico, hecho**; ver
  `release-notes-v3.47.0.md`.
- `agentes/v346-transfer-condition.md` — **V3.46 (ejecutado, 2026-09-11,
  v3.46.0)**: condición de recuperación en la transferencia
  (`prompted`/`cued_context`/`open_context`/`free_choice`/`naturally_emergent`),
  escalera pura por evidencia, persistencia aditiva y endurecimiento de
  `transfer_demonstrated` (exige ≥1 éxito limpio NO andamiado). Cierra el P1
  `transfer_condition` de la auditoría de V3.43.0. **Histórico, hecho**; ver
  `release-notes-v3.46.0.md`.
- `agentes/v345-translator.md` — **V3.45 (ejecutado, 2026-09-11, v3.45.0)**:
  Traductor de viaje práctico (modo Conversación con dos botones grandes, VAD,
  auto-traducción y auto-reproducción, «cara a cara») + voz española real
  (`es_ES-davefx-medium`, default por idioma y auto-descarga en `/api/tts`).
  **Histórico, hecho**; ver `release-notes-v3.45.0.md`.
- `agentes/v344-sense-aware.md` — **V3.44 (ejecutado, 2026-09-11, v3.44.0)**:
  Lexicón sense-aware (`lexical_unit → sense`) + scoring semántico 2.0
  (`fit`/`suspect`/`incorrect`/`unknown`, solo `incorrect` bloquea el clean
  success). Cierra los dos P1 conceptuales de la auditoría de V3.43.0.
  **Histórico, hecho**; ver `release-notes-v3.44.0.md`.
- `agentes/v343-transfer-2.md` — **V3.43 (ejecutado, 2026-09-11, v3.43.0)**:
  Transfer 2.0 (target oculto, semanticidad determinista, diversidad contextual
  real y `transfer_state`). Cierra los 4 P1 de la auditoría de V3.42.0.
  **Histórico, hecho**; ver `release-notes-v3.43.0.md`.
- `agentes/v338-situacion-planner.md` — **V3.38 (ejecutado, 2026-09-10,
  v3.38.0)**: `situación` como techo de la escalera + planner (Optimal Next Task)
  + automaticidad por skill. **Histórico, hecho**; ver
  `release-notes-v3.38.0.md`. Su cierre quirúrgico (**V3.38.1**, ejecutado por el
  gerente sin briefing separado) cierra los 4 P1 de su auditoría y añade la UI de
  diccionario/estado; ver `release-notes-v3.38.1.md`.
- `agentes/v3371-politica-recall.md` — **V3.37.1 (ejecutado, 2026-09-10,
  v3.37.1)**: política de consolidación (≥2 éxitos en ≥2 días) y regresión
  (≥2 fallos sin éxito) de la escalera de recall. **Histórico, hecho**; ver
  `release-notes-v3.37.1.md`.
- `agentes/v337-cues-graduados.md` — **V3.37 (ejecutado, 2026-09-10, v3.37.0)**:
  cues graduados + automaticidad. **Histórico, hecho**; ver
  `release-notes-v3.37.0.md`. El siguiente briefing vivo (V3.39: decisión por
  skill + routing de escritura de `written_production`) está por escribir.
- `agentes/v330-*.md`, `v332-*`, `v333-*`, `v3331-*`, `v334-*` — puente
  Dictionary → Learning (V3.30–V3.34): **históricos, hechos**.
- `agentes/m*-*.md` — milestones M0–M10 y `v17`/`v18`: **históricos, todos hechos**.
- `agentes/endurecimiento/` — Release Audit 1.1 (RA1–RA7), launcher (A1/A2) y
  endurecimiento (E1–E4, F4–F9): **históricos, todos hechos**.
- `agentes/pedagogia/` — Etapa pedagógica (P1–P23): **históricos, todos hechos**.
- `agentes/ui2/` — Rediseño UI 2.0 (u1–u3): **históricos, todos hechos**.
- `agentes/curriculum/` — V2.5 Curriculum Completion (c1–c4): **hechos** (37.22–37.25). Ver
  `docs/RELEVO.md` sección 37.21 y `docs/CURRICULUM_COVERAGE.md` (huecos que cierran).

Las **FASE 1–5 de la auditoría externa (V1.30–V1.34)** — LAN/móvil, Adaptive 2.0,
Curriculum 2.0, Listening 2.0 y Speaking 2.0 — fueron ejecutadas **directamente por el
gerente** (sin briefings separados). Para esos incrementos, la fuente de verdad es
`CHANGELOG.md` + `docs/RELEVO.md` (sección 37), no un archivo `agentes/*.md`.

### ¿Qué queda?

Ver `docs/RELEVO.md` sección 37: **37.3** (contenido WAV real, pendiente del usuario),
**37.4** (Vercel, diferido) y el **commit `feat:` de cierre de V1.30–V1.34**. Si la
auditoría define **FASE 6 (Beta)**, se crea un nuevo briefing en esta carpeta antes de ejecutarla.

## Plantilla estándar de un subagente

Cada archivo contendrá las siguientes secciones:

- **Rol:** qué papel juega (backend, frontend, voz, testing…).
- **Objetivo:** qué debe conseguir exactamente.
- **Contexto:** stack, rutas de archivos, dependencias, cómo arrancar.
- **Tarea detallada:** pasos concretos.
- **Criterios de aceptación:** cómo saber que está bien hecho.
- **Restricciones:** qué NO debe hacer (no salir del scope, no tocar otros archivos, mantener tipado fuerte, 100% local…).
- **Salida esperada:** qué debe devolver (diff, archivos, explicación).

## Reglas anti-saturación / anti-alucinación

- Un subagente = una tarea acotada y autocontenida; **no** encadenar trabajo histórico.
- Si el contexto del agente se satura, **reiniciar** desde `docs/RELEVO.md` (sección 0) en lugar
  de seguir acumulando.
- Verificar rutas de archivos y nombres de funciones contra el código real (`docs/ARQUITECTURA.md`
  y `docs/PREMISAS.md`) antes de asumir que siguen existiendo.
