# Cómo lanzar los subagentes (sin gastar tokens)

El gerente del proyecto (el asistente) **no ejecuta** estos subagentes. Tú los
lanzas desde tus propios agentes locales. Cada subagente es un archivo Markdown
**autocontenido**: incluye todo lo que el agente necesita para trabajar sin
pedir más contexto.

> **Estado actual (2026-09-11): `v3.48.0`** — ver `docs/RELEVO.md` (nota superior
> y sección 0 "START HERE").
> Antes de lanzar cualquier subagente, lee esa sección para no partir de un estado
> obsoleto (premisa 8 y 12: relevo al saturar y ancla contra la alucinación).

## Cómo usar un subagente

1. Abre el archivo `agentes/<nombre>.md`.
2. Copia su contenido completo y pégalo como prompt en tu agente local
   (o ábrelo como archivo de contexto/tarea en tu agente).
3. El agente local trabaja y devuelve el resultado.
4. Pega el resultado de vuelta aquí; el gerente revisa e integra o genera el siguiente paso.

## Estado de la biblioteca de briefings

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
