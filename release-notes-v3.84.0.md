# Release notes — English Tutor v3.84.0

**Fecha:** 2026-09-25 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.83.1 → 3.84.0`

**Con backend y frontend, SIN migración de BD y SIN endpoints nuevos.** Los packs se
siembran solos por `slug` desde `backend/curriculum/vocab_packs/*.json`; el flujo de mazos
reutiliza `listFlashcardDecks` / `createFlashcardDeck` / `createFlashcard` y el filtro
reutiliza el `collection_id` que la cola FSRS ya aceptaba. **SIN cambio de contrato de
API y SIN bump** de `GENERATOR_VERSION` / `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION`
sigue `1.3.1`) / `LISTENING_BANK_VERSION` ni de las evaluaciones. **No se añade ni se
retira gate** —siguen los **ocho**, todos en `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** La app deja de **recortar botones** en pantallas estrechas (con una
guardia que lo impide a partir de ahora), el alta del diccionario **elige MAZO** (y lo crea
sin salir del panel), y el vocabulario pasa de **3 packs de ~25 palabras** a **15 packs de
40–60**.

---

## 1. El defecto reportado, y la clase a la que pertenece

«Practicar esta palabra» se **cortaba** en DICCIONARIO/CONSULTAR. La causa **no** era un
ancho mal puesto: el cluster de acciones de la tarjeta de resultado era
`flex items-center gap-2` **sin `flex-wrap`**, dentro de un `Card` con `overflow-hidden`.
A 320–390 px el navegador **recortaba en silencio**: no aparecía scroll horizontal, así que
tampoco lo veía ningún test que midiera `scrollWidth`. Ese es el modo de fallo peligroso —
lo que sobra **desaparece** en lugar de provocar una barra—.

Se arregla el defecto y **la clase entera** (auditoría previa, por orden de gravedad):

- **`DictionaryLookup`** — el cluster del `ResultCard` pasa a envolverse, con `min-w-0`
  para que el texto largo de la palabra no lo empuje fuera. Es el arreglo del botón
  reportado:

```1024:1024:frontend/src/features/vocabulary/DictionaryLookup.tsx
          <div className="flex min-w-0 flex-wrap items-center gap-2">
```

- **`wordDrill`** — el conmutador de los 5 peldaños era `flex w-fit` **sin wrap** y este
  **sí** provocaba scroll horizontal real (el único defecto con barra visible).
- **`Header`** — el cluster de acciones (`HandsFree` + iconos + menú de usuario) no cabía a
  320 px: pasa a envolver y a dejar encoger lo secundario.
- **`StudySession`** — la cabecera con 3 badges `whitespace-nowrap` y las dos caras del
  volteo ganan `flex-wrap` y `break-words` (un reverso largo ya no desborda).
- **`FlashcardsScreen`**, **`DictionaryScreen`**, **`AddVocabSection`** y
  **`PersonalDictionary`** — filas con cluster `shrink-0` dentro de contenedores
  `overflow-hidden`, y pestañas `flex w-fit`: `min-w-0` + truncado / envoltura.

---

## 2. La guardia automática (lo que evita que vuelva)

El recorte por `overflow` **no lo detecta** una aserción de `scrollWidth`, porque no hay
scroll: hay que **comparar rectángulos** contra el ancestro que recorta. No existía ninguna
herramienta para eso, así que se crea:

- **`frontend/tests/visual/layoutHelper.ts`** — dos helpers compartidos:

```24:24:frontend/tests/visual/layoutHelper.ts
export async function expectNoHorizontalOverflow(
```

```48:48:frontend/tests/visual/layoutHelper.ts
export async function expectInsideClippingAncestor(
```

- **`frontend/tests/visual/responsiveOverflow.spec.ts`** — recorre **11 rutas** y las
  **3 pestañas del diccionario** afirmando que **no hay desborde horizontal** a
  390 / 768 / 1280, y en un `describe` propio a **320 px** (un ancho que la suite **no
  probaba**), sin multiplicar toda la suite con un cuarto proyecto:

```65:70:frontend/tests/visual/responsiveOverflow.spec.ts
test.describe("ancho mínimo 320 px", () => {
  // El 320 px se afirma una sola vez (proyecto mobile); repetirlo en los tres
  // proyectos triplicaría el coste sin añadir cobertura.
  test.use({ viewport: { width: 320, height: 720 } });

  test("ninguna ruta desborda a 320 px", async ({ page }, testInfo) => {
```

- **`dictionarySmoke.spec.ts`** — además, la regresión concreta: los botones de acción del
  diccionario se comprueban con `expectInsideClippingAncestor` contra el `Card` que los
  recortaba. Es lo único que detecta esta clase de defecto.

---

## 3. Diccionario → alta en un MAZO manual

El panel de alta deja de archivar en **listas** (un destino que no se correspondía con la
promesa de «estudiar») y ofrece **elegir mazo**:

- **`Solo aprendizaje`** (comportamiento de siempre: léxico + carta FSRS), **mazos propios**
  (`listFlashcardDecks` filtrando `!is_auto`) y **`Crear mazo nuevo…`** con input en línea
  (`createFlashcardDeck`), que crea el mazo y lo deja seleccionado:

```60:60:frontend/src/features/vocabulary/DictionaryLookup.tsx
const NEW_DECK_OPTION = "__new__";
```

- Al confirmar se mantiene `addVocabularyItem(...)` (léxico + FSRS + PERSONAL + mazo
  automático «Mi diccionario») y, **si hay mazo elegido**, además se crea la **tarjeta**
  (`createFlashcard(userId, deckId, { front, back })`). El éxito declara **las dos cosas**
  —en aprendizaje **y** guardada en el mazo—:

```652:652:frontend/src/features/vocabulary/DictionaryLookup.tsx
            {t("dictionary.lookup.addOkDeck").replace(
```

- **Cableado del foco:** `onOpenFlashcards(deckId)` → `StudyFocus.deckId` en
  `DictionaryScreen` → `focusDeckId` en `FlashcardsScreen`, aplicado en el efecto de
  `focusNonce` (`setDeckId(deckId)`, `setCollection(null)`). «Estudiar en Flashcards» abre
  **ese** mazo, no el automático.

---

## 4. Contenido: 12 packs nuevos y 3 enriquecidos

| Pack | Ítems | Pack | Ítems | Pack | Ítems |
|---|---|---|---|---|---|
| `food` | 60 | `city` | 47 | `nature` | 46 |
| `work` | 55 | `clothes` | 47 | `sports` | 46 |
| `travel` | 51 | `health` | 47 | `feelings` | 45 |
| `computing` | 48 | `home` | 47 | `body` | 45 |
| `business` | 47 | `school` | 47 | `tools` | 47 |

**15 packs de 40–60 palabras, 725 ítems en total** (~650 entradas nuevas sumando los 12
packs nuevos y el enriquecimiento de los 3 existentes). Cada ítem lleva
`word`/`lemma`/`translation`/`pos` y el pack su `title`/`title_es`. **Sin migración:**
`ensure_theme_packs_seeded()` los inserta por `slug` (idempotente) en el siguiente
arranque o consulta, así que aparecen solos en *Mazos listos* y en el bloque de packs de
PERSONAL.

Test nuevo **`backend/tests/test_vocab_packs_content.py`**: cada `*.json` parsea, tiene los
campos requeridos, `slug` único entre packs, **40–60 ítems** y **palabras únicas**
normalizadas dentro del pack.

---

## 5. Ruta genérica con filtros

En el mazo automático (que es **todo** el léxico, «Mi diccionario»), la pestaña Estudiar
gana un **selector de filtro** —**Todas / por pack / por lista**— cargado con
`listVocabCollections` y mapeado al `collectionId` que `getFlashcardQueue` **ya aceptaba**:
reutiliza el estado `collection`, el chip de filtro y el salto `onStudyCollection` que ya
existían. **Frontend puro: sin endpoint nuevo.** «Estudiar un mazo concreto» sigue como
estaba (cada fila de Mazos tiene su *Estudiar*).

---

## 6. i18n

Claves nuevas (**en** + **es**) para el selector/creación de mazo y los filtros de la ruta:
`dictionary.lookup.addDeckLabel` · `addDeckNone` · `addDeckNew` · `addDeckCreate` ·
`addDeckNamePlaceholder` · `addDeckError` · `addOkDeck` · `flashcards.study.filterLabel` ·
`filterAll` · `filterPacks` · `filterLists`. `check_i18n_coverage.py --strict` verde.

---

## 7. Verificación

| Comprobación | Resultado |
|---|---|
| `python scripts/check_release_consistency.py` | **OK en los 6 orígenes** (`3.84.0`) |
| `npx tsc --noEmit` | limpio |
| `npm run test` (vitest) | **1036/1036** (109 ficheros) |
| `python -m ruff check .` (backend) | limpio |
| `python -m pytest -q` | **3140/3140** |
| `python scripts/check_i18n_coverage.py --strict` | **1780** cadenas · 0 huérfanas · 0 sin definir · 0 duplicadas · 0 vacías |
| `node scripts/contrast_audit.mjs --strict` | **480 pares + 6 guardas · 0 bloqueantes** |
| `npm run build` | correcto (`dist` reconstruido, `package.json` en `3.84.0`) |
| `python scripts/validation_gate.py auto --require-dist` | **10/10** (8 gates) |
| `npx playwright test` (barrido **COMPLETO**) | **90 passed · 0 failed · 30 skipped** |

El barrido visual **completo** se corrió —no solo los specs nuevos— y fue el que cazó
`dictionaryFlashcardsBridge`, que aún exigía el panel de listas retirado: se actualizó a los
mocks y aserciones del flujo de mazo manual (`POST /api/vocabulary/decks/7/cards`).

---

## 8. Honestidad

1. **El alta en un mazo manual DUPLICA el ítem.** La palabra queda en el léxico
   («Mi diccionario»/PERSONAL) **y** como tarjeta manual del mazo. Es el precio de que los
   dos modelos de tarjeta no se compartan; la UI lo declara y consolidarlo queda **aparcado**.
2. **Archivar en listas desde el panel del diccionario se retira.** Las listas siguen
   existiendo y se crean desde PERSONAL; lo que cambia es el destino por defecto del
   diccionario, que pasa a ser el mazo elegido.
3. **El contenido de los packs es autoría acotada.** El test garantiza **forma**, `slug`
   único, unicidad intra-pack y 40–60 ítems; **no** garantiza calidad léxica ni traducción
   perfecta. ~650 entradas nuevas son una contribución de contenido, no una validación
   lingüística.
4. **320 px es un ancho nuevo** que la suite no probaba y reveló más defectos de los
   enumerados en el plan; los encontrados se cerraron y el ancho queda dentro de la guardia
   desde ahora, pero puede haber rincones que solo aparezcan con contenido real.
5. **`frontend/dist` se reconstruyó** en esta release (`npm run build` + gate con
   `--require-dist`), así que **deja** de estar desfasado respecto a `3.84.0`.
6. **Los 8 gates humanos siguen `pending`** y `validation-evidence.json` **no existe**; el
   ancla de certificación sigue en `v3.83.1`. **H1** (`_collection_writable` devuelve `True`
   para un pack global) **sigue vivo** como deuda aceptada `P2`, igual que **H5** y **H3**.

---

## Para auditar esta release

- **Ancla:** el tag **`v3.84.0`**.
- **Alcance:** `frontend/src` (responsive, panel de mazo, filtros), `frontend/tests/visual`
  (helpers y specs nuevos), `backend/curriculum/vocab_packs/*.json` (12 nuevos + 3
  enriquecidos), `backend/tests/test_vocab_packs_content.py`, claves de i18n, y el **bump**
  de `VERSION` / `package.json` / `package-lock.json` / documentación.
- **Lo que NO toca:** esquema de BD, contrato de API, `GENERATOR_VERSION`,
  `DECISION_POLICY_VERSION`, `CURRICULUM_VERSION`, `LISTENING_BANK_VERSION`, evaluaciones y
  el número o la definición de los gates.
- **Punto de entrada al detalle:** `docs/audit/PARKED.md §V3.84.0` y `docs/RELEVO.md`
  (nota del 2026-09-25).
