# v3.48.1 — APRENDER más limpio + ruta CEFR seleccionada

**Patch de UI sobre APRENDER, sin cambios de contrato ni migración de BD. (A)
Listening deja de mostrar la etapa «Antes de escuchar». (B) Las notas largas
CEFR/`routeNote`/`routeRingHelp` se pliegan tras un botón «...». (C) La ruta CEFR
pasa a ser una selección persistente que gobierna de qué nivel se sirven las
preguntas. (D) Se eliminan los perfiles de prueba de la base de datos local.**

Versión de app `3.48.0 → 3.48.1`. Frontend (`microFlow.ts`,
`ListeningPractice.tsx`, `QuizRoutePage.tsx`, paneles de nivel, `InfoDisclosure`,
`useSelectedRoute`, i18n) + `scripts/purge_virtual_testers.py` + tests y docs.

## Contexto

La auditoría de V3.48.0 y la revisión de la UI de APRENDER señalaron tres cosas
de experiencia, no de motor: la etapa «Antes de escuchar» del Listening ocupaba
la zona principal de la pantalla sin aportar respuesta; la explicación de qué
implica un nivel CEFR real (y demás notas honestas) competía visualmente con el
trabajo; y pulsar una ruta (A1…C2) solo abría su historial, sin que la elección
gobernara de qué nivel se practicaba.

Fuera de alcance (diferido y documentado): Sense Engine 2.0, Context→Skill
mapping, difficulty matching por `difficulty_vector`, Transfer evidence 3.0 y
Adaptive Planner 2.0. No se tocan FSRS, el Evidence Ledger ni el gate de
transferencia.

## Qué cambia

### A — Listening sin «Antes de escuchar»

- **`microFlow` salta los pasos `pre`** (`firstRenderableIndex`), así que el
  flujo arranca en `while1`. El backend sigue sirviendo `pre` por contrato (es
  inocuo: no tiene respuesta ni evidencia) y no se altera `transcript_policy`.
- **Se elimina la tarjeta y las claves i18n**
  `listening.flow.preTitle`/`preHint`/`begin`.
- **El contexto se conserva** como caption compacta de una línea bajo el botón
  de reproducción (señal situacional sin ocupar la zona principal).

### B — Notas CEFR plegables (`components/InfoDisclosure.tsx`)

- **Nuevo desplegable compartido**: `button` + `aria-expanded`/`aria-controls` +
  icono `MoreHorizontal`, contenido montado solo al abrir. Variantes `inline`
  (con alineación inicio/fin) y `corner` (anclado a la esquina de una Card).
- **Listening** (`routeNote`/`routeCertNote`/`routeRingHelp`) y el **mapa de
  rutas de las cinco destrezas** (`QuizRoutesSection`: Speaking, Vocabulary,
  Grammar, Pronunciation y Conversation; incluye `routesMapHint`) pliegan sus
  notas largas.
- **Paneles de nivel** (los seis): la prosa explicativa
  (`demonstrateNote`/`demonstrateFormal`/`extraHonestNote`) pasa al «...». Los
  estados accionables (gate, `demoNotYet`, progreso) siguen visibles.

### C — Ruta CEFR seleccionada y persistente

- **`utils/selectedRoute.ts`**: validación `A1..C2`, parseo tolerante de
  `localStorage` (valor plano o JSON) y `resolveRouteLevel`.
- **`hooks/useSelectedRoute.ts`**: persistencia doble — `localStorage` inmediato
  (sin parpadeo y válido sin perfil) + `selected_route_level` vía
  `GET/PUT /api/settings` (**sin cambios de backend**: `settings` es clave/valor).
- **Prioridad al servir preguntas: sesión activa > ruta seleccionada > nivel
  recomendado**. Con «Auto» (`null`) el backend decide.
- **Pulsar un anillo A1–C2 selecciona y abre su panel**; el anillo activo se
  resalta y muestra «Ruta seleccionada». El **chip «Auto»** limpia la selección.
- **`exitSession` vuelve a la ruta seleccionada** (no al adaptativo puro),
  manteniendo la coherencia con lo que el alumno está trabajando.

### D — Limpieza de perfiles de prueba

- **`scripts/purge_virtual_testers.py`**: dry-run por defecto; con `--apply`
  hace copia de seguridad (`tutor.db.bak-<ts>`) y borra en una única transacción
  enumerando dinámicamente las tablas con `user_id` (los `messages` de sus
  conversaciones se borran aparte). Se documenta en `docs/DESARROLLO.md`.
- **Se han eliminado los 6 perfiles de prueba** (`Visual Tester`); quedan los 2
  perfiles reales.

## Tests

- Frontend vitest **75 ficheros/639 tests** (+3/+16): `InfoDisclosure.test.tsx`,
  `selectedRoute.test.ts`, `useSelectedRoute.test.tsx`; `microFlow.test.ts`
  actualizado al arranque en `while1` (el flujo salta `pre`).
- `check_i18n_coverage`: **0 claves indefinidas, 0 duplicadas** (se retiran las
  tres de `pre` y se añaden `common.moreInfo` y `learn.route*`).
- Verificación local: `npm run test`, `npx tsc --noEmit`, `npm run build`,
  `pytest` backend (**2075 passed**), `ruff check backend/` y
  `check_release_consistency` **3.48.1** exit 0.
- **CI 6/6 en verde** (run
  [34588975928](https://github.com/jvelasca/english-tutor/actions/runs/34588975928)
  sobre `6a0a757`): Release consistency, Backend (ruff + pytest), Frontend
  (tsc + vitest + build), Playwright E2E (visual), Beta V3.0 gate y Content
  validation.

## Fuera de alcance (V3.49+)

- Sense Engine 2.0 (`surface → lemma → lexical_unit → sense → context →
  semantic_fit`).
- Context→Skill mapping (cada contexto declara qué competencias ejercita).
- Difficulty matching por `difficulty_vector` (no solo `learner CEFR >= context
  CEFR`).
- Transfer evidence 3.0 y Adaptive Planner 2.0 / `expected_learning_value`.

## Decisiones de diseño

- **UI-only.** El contrato del backend no cambia: la etapa `pre` sigue en el
  flujo servido y la ruta seleccionada se persiste en `settings`. Sin migración
  ni riesgo para la evidencia.
- **Un solo patrón de divulgación.** En vez de reordenar cada pantalla, se
  introduce un `InfoDisclosure` reutilizable y se aplica la misma convención en
  todas las pantallas de práctica.
- **La selección no sustituye a la sesión.** La sesión focalizada (drill/repaso)
  sigue teniendo prioridad absoluta; la ruta seleccionada solo decide la
  práctica libre y es lo que se retoma al cerrar una sesión.
- **Borrado explícito.** Al no haber `ON DELETE CASCADE`, la limpieza se hace
  con un script auditable (dry-run + backup + transacción), nunca con SQL suelto.
