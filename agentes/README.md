# Cómo lanzar los subagentes (sin gastar tokens)

El gerente del proyecto (el asistente) **no ejecuta** estos subagentes. Tú los
lanzas desde tus propios agentes locales. Cada subagente es un archivo Markdown
**autocontenido**: incluye todo lo que el agente necesita para trabajar sin
pedir más contexto.

> **Estado actual (2026-08-28): `v1.34`** — ver `docs/RELEVO.md` (sección 0 "START HERE").
> Antes de lanzar cualquier subagente, lee esa sección para no partir de un estado
> obsoleto (premisa 8 y 12: relevo al saturar y ancla contra la alucinación).

## Cómo usar un subagente

1. Abre el archivo `agentes/<nombre>.md`.
2. Copia su contenido completo y pégalo como prompt en tu agente local
   (o ábrelo como archivo de contexto/tarea en tu agente).
3. El agente local trabaja y devuelve el resultado.
4. Pega el resultado de vuelta aquí; el gerente revisa e integra o genera el siguiente paso.

## Estado de la biblioteca de briefings

- `agentes/m*-*.md` — milestones M0–M10 y `v17`/`v18`: **históricos, todos hechos**.
- `agentes/endurecimiento/` — Release Audit 1.1 (RA1–RA7), launcher (A1/A2) y
  endurecimiento (E1–E4, F4–F9): **históricos, todos hechos**.
- `agentes/pedagogia/` — Etapa pedagógica (P1–P23): **históricos, todos hechos**.
- `agentes/ui2/` — Rediseño UI 2.0 (u1–u3): **históricos, todos hechos**.

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
