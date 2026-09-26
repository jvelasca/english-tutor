# Playwright — clasificación de los skips (V3.86.1)

> **Encargo:** la auditoría externa de V3.86.0 pidió clasificar individualmente los
> **34 skipped** del informe de release antes de dar por cerrada la UI. Este
> documento es ese inventario, hecho sobre el commit de V3.86.0 y actualizado con
> lo que cambia V3.86.1.
>
> **Fecha:** 2026-09-26 · **Tag de partida:** `v3.86.0`.

## 1. Método

- **Config:** `frontend/playwright.config.ts` — `testDir: "./tests/visual"`, tres
  proyectos: `desktop` (1280×800), `tablet` (768×1024) y `mobile` (Pixel 7,
  390×844), `channel: "chrome"`.
- **Universo:** 26 ficheros de spec, **150 tests × 3 proyectos = 450 ejecuciones**.
  Los tests del diccionario polisémico y de multi-mazo viven en
  `vocabularyRoutesReview.spec.ts` y `dictionaryFlashcardsBridge.spec.ts`.
- **Mecanismo de skip:** **todos** son `test.skip(condición, motivo)` evaluados en
  tiempo de ejecución dentro del cuerpo del test. No hay `test.fixme`,
  `test.describe.skip`, `skip: true`, `test.describe.configure` ni guardas por
  variable de entorno. Esto es lo que hace el recuento **determinista** en CI.
- **Recuento V3.86.0:** 116 passed · 0 failed · **34 skipped**.
- **Recuento V3.86.1:** 118 passed · 0 failed · **32 skipped** (ver §4).

## 2. Inventario (todas las llamadas a `test.skip`)

Rutas relativas a `frontend/tests/visual/`.

| # | Fichero | Línea | Test | Condición | Motivo escrito | Superficie | Clase |
|---|---------|-------|------|-----------|----------------|------------|-------|
| 1 | `accentContrast.spec.ts` | 68 | los 7 acentos cumplen AA en los dos temas | `once` | «guarda de token: basta una vez» | accesibilidad | Legítima |
| 2 | `analysis.spec.ts` | 51 | desktop: MI PROGRESO muestra las 5 pestañas | `project !== "desktop"` | «Solo desktop» | responsive | Legítima (pareja de la fila 3) |
| 3 | `analysis.spec.ts` | 80 | móvil: MI PROGRESO muestra el tablist | `width >= 1024` | «Solo móvil/tablet» | responsive | Legítima (pareja de la fila 2) |
| 4 | `conversationRoutesReview.spec.ts` | 257 | capturar Conversation guiada (mock) | `project !== "desktop"` | «Solo desktop» | rutas | Cobertura silenciada |
| 5 | `drillProvenance.spec.ts` | 226 | desktop: el drill devuelve el decision_id | `width < 1024` | «Solo desktop» | rutas | Cobertura silenciada |
| 6 | `drillProvenance.spec.ts` | 287 | desktop: sin decision_id no se declara nada | `width < 1024` | «Solo desktop» | rutas | Cobertura silenciada |
| 7 | `grammarRoutesReview.spec.ts` | 188 | capturar Grammar: página única MC (mock) | `project !== "desktop"` | «Solo desktop» | rutas | Cobertura silenciada |
| 8 | `mobile.spec.ts` | 22 | móvil: la ayuda general se abre desde el header | `width >= 1024` | «Solo móvil/tablet» | responsive | Legítima |
| 9 | `mobile.spec.ts` | 52 | móvil: el test de micrófono se renderiza | `width >= 1024` | «Solo móvil/tablet» | responsive | Legítima |
| 10 | `mobile.spec.ts` | 67 | móvil: permiso denegado → aviso | `width >= 1024` | «Solo móvil/tablet» | responsive | Legítima |
| 11 | `pronunciationRoutesReview.spec.ts` | 267 | capturar Pronunciation read-aloud (mock) | `project !== "desktop"` | «Solo desktop» | rutas | Cobertura silenciada |
| 12 | `resize.spec.ts` | 16 | redimensiona el panel y persiste el ancho | `width < 1024` | «Solo desktop» | responsive | Legítima |
| 13 | `responsiveOverflow.spec.ts` | 88 | ninguna ruta desborda a 320 px | `project !== "mobile"` | «320 px se mide una sola vez» | responsive | Legítima |
| 14 | `routeExtraReview.spec.ts` | 249 | capturar ruta A1 dominada con práctica extra | `project !== "desktop"` | «Solo desktop» | rutas | Cobertura silenciada |
| 15 | `speaking.spec.ts` | 112 | desktop: Speaking 2.0 muestra proxy/Endurance | `width < 1024` | «Solo desktop» | rutas | Cobertura silenciada |
| 16 | `speakingRoutesReview.spec.ts` | 279 | capturar Speaking por micro-conversaciones | `project !== "desktop"` | «Solo desktop» | rutas | Cobertura silenciada |
| 17 | `vocabularyRoutesReview.spec.ts` | 276 | capturar Vocabulary: MC + diccionario | `project !== "desktop"` | «Solo desktop» | rutas | Cobertura silenciada |
| 18 | `vocabularyRoutesReview.spec.ts` | 372 | V3.85.1: APRENDER → Vocabulario recupera el repaso | `project !== "desktop"` | «Solo desktop» | diccionario | Cobertura silenciada |
| 19 | ~~`vocabularyRoutesReview.spec.ts`~~ | ~~406~~ | **V3.86.0: el diccionario incrustado da salida a una palabra ya rastreada** | ~~`project !== "desktop"`~~ | — | diccionario | **Eliminada en V3.86.1 (§4)** |

## 3. Proyección aritmética (por qué son 34)

| Condición | Tests | Proyectos que saltan | Ejecuciones |
|-----------|-------|----------------------|-------------|
| `project !== "desktop"` | 9 | tablet + mobile | 18 |
| `width < 1024` | 5 | tablet + mobile | 10 |
| `width >= 1024` | 4 | desktop | 4 |
| `project !== "mobile"` | 1 | desktop + tablet | 2 |
| **Total V3.86.0** | **19 sitios** | | **34** |

Reparto por proyecto: desktop 5, tablet 15, mobile 14 (45 + 35 + 36 = 116 passed).

## 4. Lo que cambia V3.86.1

1. **Se retira la guarda del test del diccionario polisémico** (fila 19). Era la
   superficie modificada de V3.86.0 y su flujo —consultar una palabra ya
   rastreada y saltar a Flashcards → Estudiar— es el mismo en los tres anchos.
2. **Se corrige un defecto real que la retirada destapó:** el CTA «Consult» y su
   gemelo «My dictionary» ocultaban el texto en móvil (`hidden sm:inline`), así
   que en un teléfono eran botones **sin nombre accesible** (solo icono). Ahora
   llevan `aria-label` en `features/routes/QuizRoutePage.tsx`. No era un problema
   del test: era un botón mudo para lectores de pantalla.
3. **Recuento resultante:** 118 passed · **32 skipped** · 0 failed (verificado:
   3 proyectos, `npx playwright test`).

## 5. Clasificación por superficie

- **Diccionario:** 2 sitios → 1 eliminado (fila 19); queda la fila 18 (V3.85.1,
  cubierta por su equivalente en la pantalla central).
- **Flashcards / multi-mazo / recordatorio (superficie V3.86.0):** **cero skips**.
  `dictionaryFlashcardsBridge.spec.ts` (líneas 619, 670, 704, 748) y
  `flashcardsSmoke.spec.ts` corren en los tres proyectos.
- **Rutas (`capturar … (mock)`):** 7 sitios. Construyen rutas de captura por
  proyecto pero se fuerzan a desktop; es **política de un solo breakpoint
  declarada**, no un fallo latente. Se dejan como están: son revisiones visuales
  de página completa y el objetivo es la imagen de desktop.
- **Responsive:** 8 sitios, todos con pareja en el ancho contrario o medición
  única justificada (`responsiveOverflow:88` mide 320 px solo en mobile).
- **Accesibilidad:** 1 sitio (`accentContrast:68`), guarda de token
  independiente del ancho: correcto que se mida una vez.

**Resumen:** de los 32 skips que quedan, ~12 son específicos de breakpoint por
diseño (con su cobertura en el ancho complementario) y ~20 son política de
un solo breakpoint en las revisiones de ruta. Ninguno oculta la superficie
modificada de V3.86.0.

## 6. Nota de CI (no bloqueante)

`.github/workflows/ci.yml` (job `playwright`) instala `npx playwright install
--with-deps chromium`, pero `playwright.config.ts` fija `channel: "chrome"`. En
`ubuntu-latest` se resuelve con el Chrome preinstalado del runner y el Chromium
descargado queda sin usar. No afecta al resultado (los 450 casos corren), pero
conviene alinear canal e instalación en una futura limpieza de CI.
