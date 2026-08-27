# 37.1 — Rediseño UI 2.0: fases 3–6 (solo frontend)

## Rol
Subagente **frontend** que migra las pantallas de práctica (listening, speaking, progress) de las
clases CSS legacy a Tailwind v4 + shadcn/ui + Motion, y retira de `legacy.css` las reglas que queden
huérfanas.

## Contexto
- Stack fijado (premisa 3–4): Vite + React + TypeScript estricto. Tailwind v4
  (`@tailwindcss/vite`), shadcn/ui (primitivas), `motion` (Motion/react), `lucide-react`.
- `src/index.css` importa Tailwind + `@theme inline` con tokens semánticos (`--color-primary`,
  `--color-card`, `--radius-*`, `--color-border`, …). `src/styles/legacy.css` contiene ~6400 líneas
  de CSS legacy que aún estilizan las pantallas de práctica. NO reescribas los tokens ni rompas el
  sistema de apariencia (`data-theme`/`data-accent`/`data-font`/`data-density`).
- Primitivas disponibles (reutilízalas, no reinventes):
  - `src/components/ui/{button,card,badge,progress}.tsx` (shadcn).
  - `src/components/SkillBar.tsx`, `LevelBadge.tsx`, `JourneyNode.tsx`, `Milestone.tsx`,
    `NextBestCard.tsx`, `NextStep.tsx`, `ActivityResult.tsx`, `SystemStatus.tsx`.
  - Utilidad `cn()` en `src/lib/utils.ts`.
- Pantallas objetivo (aún con clases legacy, definidas en `legacy.css`):
  - Fase 3: `src/features/listening/ListeningPractice.tsx`.
  - Fase 4: `src/features/speaking/{SpeakingPanel,SpeakingDiagnostic,SpeakingAssessment,SpeakingRolePlay,SpeakingJourney}.tsx`
    y `src/components/PronunciationPractice.tsx`.
  - Fase 5: `src/features/progress/ProgressScreen.tsx`.
- i18n: hook `useI18n()` (`src/hooks/useI18n.tsx`) → `t("clave")`. Todo string visible va por i18n;
  no hardcodees texto en inglés/castellano fuera de `src/utils/i18n.ts`.
- Verificación (parte de "terminado", premisas 12/20): `npx tsc --noEmit`, `npm test` (vitest),
  `npm run build`, `npm run test:visual` (Playwright, 3 viewports). Los screenshots se revisan.

## Objetivo
Migrar listening, speaking y progress a Tailwind/shadcn/Motion con aspecto "PRO" (premisa 14/16),
manteniendo TODA la lógica de negocio intacta (props, hooks, estado, llamadas a API) y sin romper
responsive, a11y ni i18n. Al final (fase 6), retirar de `legacy.css` solo las reglas huérfanas y
documentar las que sigan en uso.

## Tarea (por fases; verifica en verde entre fases)

### Fase 3 — Listening: entorno auditivo inmersivo
Reescribe el JSX/estilos de `ListeningPractice.tsx` con Tailwind + `Card`/`Badge`/`SkillBar` + Motion:
- Reproductor destacado: botón play grande, indicador de reproducción, y variantes de velocidad
  (0.8x/1.0x/1.2x — ya existen `variant` (state) y `question.variants`; mantén la lógica).
- "Onda" animada con Motion mientras `playing` (puede ser una barra/pulso sutil).
- Mantén íntegra la lógica: `load`, `refreshStats`, `play`, `choose`, `submitDictation`,
  `toggleRecording`, resultado con `ActivityResult` + `NextStep`, stats y diagnóstico
  (retención, precisión por tema/dificultad, reincidencia, sub-destrezas).

### Fase 4 — Speaking: "estudio de conversación"
Aplica el mismo tratamiento a `SpeakingPanel`, `SpeakingDiagnostic`, `SpeakingAssessment`,
`SpeakingRolePlay`, `SpeakingJourney` y `PronunciationPractice`:
- "Mic que respira": pulso animado Motion en los flujos de grabación/escucha (mientras graba).
- Feedback de fluidez/coherencia con `SkillBar`/`Badge`.
- Mantén lógica y props intactas (p. ej. `SpeakingPanel` recibe `userId`/`onPractice`).

### Fase 5 — Progress: dashboard pedagógico limpio
Reescribe `ProgressScreen.tsx` con Tailwind + `Card`/`SkillBar`/`LevelBadge`/`Motion`:
- Cabecera con nivel CEFR (`LevelBadge`), overall con barra (`Progress`/`SkillBar`), lista de
  destrezas expandible y `SkillDetail`. Mantén los componentes anidados (`SpeakingDiagnostic`,
  `WritingJourney`).

### Fase 6 — Móvil específico + retirada de legacy.css
- Pasada móvil: tap targets ≥40px (`min-h-10`), sin overflow horizontal, drawers a pantalla completa
  en móvil (premisa 20).
- Retira de `src/styles/legacy.css` SOLO las reglas cuyas clases ya no aparecen en ningún `.tsx`
  (verifica con `rg`). NO borres `legacy.css` entero si aún quedan clases en uso (chat/shell/header/
  composer/etc.). Anota en el commit qué bloques legacy quedan y por qué.

## Criterios de aceptación
- `npx tsc --noEmit` OK; `npm test` en verde; `npm run build` OK.
- `npm run test:visual` (Playwright) → 4 passed + 2 skipped; screenshots revisados (sin overflow
  horizontal en móvil/tablet).
- Ninguna regresión funcional: los tests existentes siguen pasando.
- Las pantallas migradas ya no usan clases legacy (`rg "listening-|speaking-panel|speaking-criterion|progress-screen|skill-detail"` vacío en los `.tsx` migrados).
- i18n respetado (nada hardcodeado fuera de `src/utils/i18n.ts`).

## Restricciones
- SOLO frontend. No toques `backend/` ni `launcher/`.
- No cambies lógica de negocio, contratos de API ni props de los componentes (solo presentación/estilos).
- No introduzcas dependencias nuevas.
- No hagas `git push`. Haz commits `feat:` por fase (o un commit por fase).
- Premisas 14/16/19/20/21/22 intactas.

## Salida
- Resumen por fase: archivos migrados, qué bloques legacy se retiraron y cuáles quedan.
- Salida de `tsc` / `vitest` / `build` / `playwright` en verde.
