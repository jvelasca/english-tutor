# 37.2 — Code-splitting del frontend (React.lazy / Suspense)

## Rol
Subagente **frontend** que divide el bundle principal por rutas con `React.lazy`/`Suspense` para
reducir el chunk inicial (hoy ~537 kB minificado, con aviso de Vite al construir).

## Contexto
- Stack: Vite + React + TS estricto. Ruta de trabajo: `frontend/`.
- Enrutado actual (sin router externo; estado `route` en `App.tsx`):
  - `frontend/src/App.tsx` renderiza `<Workspace route={route} …/>`.
  - `frontend/src/app/Workspace.tsx` despacha por `route`:
    - `"home"` → `features/home/HomeScreen.tsx` (`export function HomeScreen`)
    - `"course"` → `features/course/CourseScreen.tsx` (`export function CourseScreen`)
    - `"progress"` → `features/progress/ProgressScreen.tsx` (`export function ProgressScreen`)
    - `"learn"`/`"chat"` → `app/PracticeView.tsx` (`export function PracticeView`), que a su vez
      importa estáticamente `AnalysisPanel`, `ChatMessage`, `Composer`, `Sidebar`, `ListeningPractice`,
      `ReadingPractice`, `PronunciationPractice` y más.
- Los componentes usan **named exports**, no default. `React.lazy` exige default export, así que usa
  el patrón `lazy(() => import("…").then((m) => ({ default: m.X })))`.
- Hay tests visuales Playwright (`tests/visual/smoke.spec.ts`) que navegan por Home/Course/Progress/
  Chat/Learn y capturan screenshots tras `waitForTimeout(600)` por ruta. Un `Suspense` con fallback
  estable debe resolverse dentro de esa ventana en local; verifica que Playwright siga en verde.
- i18n: hook `useI18n()`; cualquier texto visible va por `t("clave")` (no hardcodear).

## Objetivo
Dividir el bundle en chunks por ruta con `React.lazy` + `Suspense`, manteniendo TODA la lógica y la
experiencia intactas, y reduciendo de forma medible el tamaño del chunk inicial.

## Tarea
1. En `frontend/src/app/Workspace.tsx`, convierte `HomeScreen`, `CourseScreen`, `ProgressScreen` y
   `PracticeView` a `React.lazy` (patrón named→default). Mantén `PracticeView` como el resto de
   rutas (`learn`/`chat`).
2. Envuelve el render con `<Suspense fallback={…}>` usando un fallback **mínimo y coherente con el
   design system** (p. ej. un spinner de `lucide-react` o un `Loader2` animado, centrado, con
   `aria-busy`/`role="status"`). Si añades texto, que sea vía i18n.
3. (Opcional, si aporta) Carga diferida también de `AnalysisPanel` dentro de `PracticeView` (es el
   panel de insights, solo visible al abrirlo) para reducir aún más el chunk de práctica. Si lo
   haces, que no rompa el test visual de redimensionado ni el render del panel de Análisis.
4. No cambies props, contratos ni lógica de negocio. No toques `backend/` ni `launcher/`.

## Criterios de aceptación
- `npx tsc --noEmit` OK; `npm test` (vitest) en verde; `npm run build` OK.
- `npm run test:visual` → 4 passed + 2 skipped (sin pantallas en blanco por carga lazy).
- El `build` muestra **varios chunks** (no un único `index-*.js` gigante) y el chunk inicial baja
  respecto a ~537 kB. Reporta el desglose de tamaños (`dist/assets/*.js`).
- Sin regresiones funcionales (los tests existentes pasan).

## Restricciones
- Solo frontend. No `git commit`/`push`. No bump de versión ni edición de `CHANGELOG`/`RELEVO`
  (lo integra el gerente).
- Sin dependencias nuevas.

## Salida
- Archivos modificados, patrón de `lazy` usado, y el desglose de chunks antes/después del `build`.
- Salida de `tsc` / `vitest` / `build` / `playwright` en verde.
