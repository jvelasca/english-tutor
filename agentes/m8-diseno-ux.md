# Subagente M8 — Diseño y UX nivel top del mercado

## Rol
Diseñador/desarrollador frontend React + TypeScript (Vite, CSS puro, sin librerías UI).
Sin acceso a Git ni al backend.

## Objetivo
Rediseñar la interfaz para alcanzar el nivel de apps líderes (ChatGPT/Duolingo/Grammarly),
cumpliendo la **premisa 14**: sistema de **tokens de diseño**, **tema claro/oscuro**,
**responsive** (móvil y escritorio), **accesibilidad (a11y)**, estados vacíos/de carga/de
error cuidados y **micro-interacciones**. Todo 100% local, sin añadir dependencias.

## Contexto (autocontenido)
- Stack y reglas: `docs/PREMISAS.md` (leer premisas 2, 8, 12, 14).
- Estructura y responsabilidades: `docs/ARQUITECTURA.md`.
- El CSS actual está **todo** en `frontend/src/index.css` (~600 líneas). Usa variables en
  `:root` (`--bg`, `--card`, `--border`, `--text`, `--text-dim`, `--accent`, `--accent-2`)
  pero **solo tema oscuro**, sin toggle, sin sistema de tokens formal, sin breakpoints
  responsive ni soporte de `prefers-reduced-motion`.
- Componentes (presentación pura, NO tocar su lógica ni sus props):
  - `src/components/Sidebar.tsx` — lista de conversaciones + botón "Nuevo chat".
  - `src/components/UserSelect.tsx` — selector de perfil (dropdown + añadir).
  - `src/components/ModeSelect.tsx` — selector de modo de tutor.
  - `src/components/ChatMessage.tsx` — burbuja de mensaje (+ `SpeakButton`).
  - `src/components/Composer.tsx` — textarea + `MicButton` + botón Enviar.
  - `src/components/MicButton.tsx`, `SpeakButton.tsx`, `PronunciationPractice.tsx`.
- `src/App.tsx` compone la página: `Sidebar` + cabecera (brand + controles) + chat + `Composer`.
- `src/main.tsx` monta `App` e importa `index.css`.
- Los `className` actuales están repartidos por el CSS; puedes reestructurarlos, pero debes
  actualizar los componentes de forma coherente.
- Tests: `npm test` (vitest, 14 tests sobre utilidades puras) y `npx tsc --noEmit`.
  **No deben romperse.**

## Tarea
1. **Sistema de tokens** en `index.css`:
   - Formalizar variables en `:root`: paleta completa (fondos, superficies, bordes, texto,
     acento, éxito/advertencia/error), tipografía (familia y escala), espaciado (escala),
     radios y sombras. Nombres claros y reutilizables (`--color-*`, `--space-*`, `--radius-*`,
     `--font-*`, `--shadow-*`).
2. **Tema claro/oscuro**:
   - Soportar ambos temas con `data-theme="light|dark"` en `<html>` (o `:root`), con variables
     por tema. Mantener el oscuro como **default**.
   - Añadir un **toggle de tema** accesible en la cabecera (p. ej. botón con icono sol/luna),
     con estado persistido en `localStorage` y respetando `prefers-color-scheme` la primera vez.
   - Implementar el estado del tema con un hook nuevo `src/hooks/useTheme.ts` (sin librerías).
3. **Responsive**:
   - Móvil (≤ ~768px): sidebar colapsable (botón hamburguesa o drawer), cabecera compacta,
     controles apilados o en overflow, burbujas a ancho completo razonable.
   - Escritorio: mantener el layout actual (sidebar fija + columna central).
4. **Accesibilidad (a11y)**:
   - `aria-label`/`title` en controles iconográficos, foco visible (`:focus-visible`),
     contraste AA en ambos temas, `prefers-reduced-motion` para desactivar animaciones.
5. **Estados y micro-interacciones**:
   - Transiciones sutiles (hover/focus en botones, items de conversación, tarjetas).
   - Mejorar los estados vacíos (lista de conversaciones vacía, chat vacío), de carga
     (typing indicator ya existe; refinarlo) y de error (mensaje claro en caso de fallo).
   - Feedback visual al hablar/escuchar (micrófono y altavoz).

## Criterios de aceptación
- `npx tsc --noEmit` sin errores.
- `npm test` (vitest) verde (no romper los 14 tests existentes).
- Añadir tests de la lógica nueva que sea **pura y testable** (p. ej. resolver tema inicial
  a partir de `localStorage`/`prefers-color-scheme` como función pura en `src/utils/theme.ts`).
- `npm run build` no rompe.
- El tema por defecto sigue siendo oscuro y la app se ve coherente en ambos temas.

## Restricciones
- **NO añadir dependencias** (nada de Tailwind, CSS modules nuevos, ni librerías UI).
- **NO cambiar la lógica** de los componentes (no tocar `fetch`, ni props, ni el estado de
  negocio en `useChat.ts`; sí puedes ajustar JSX/`className` si es necesario para el diseño,
  pero sin alterar comportamiento).
- No tocar `src/api/`, `src/utils/title.ts`, `src/utils/sse.ts`, `src/utils/modes.ts` ni sus tests.
- Mantener `index.css` como única fuente de estilos (puedes reorganizarlo por secciones).
- Tipado fuerte, sin `any`.

## Salida
Lista de archivos creados/modificados, resumen de decisiones de diseño (tokens, cómo
implementaste el tema y el responsive) y resultado de `npx tsc --noEmit`, `npm test` y `npm run build`.
