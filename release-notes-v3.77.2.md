# Release notes — English Tutor v3.77.2

**Fecha:** 2026-09-22 · **Tipo:** release **DE PRODUCTO** (patch) ·
**Versión de app:** `3.77.1 → 3.77.2`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el currículum (`CURRICULUM_VERSION` sigue
`1.3.1`), SIN tocar las evaluaciones y SIN tocar `LISTENING_BANK_VERSION`.** No
añade ni retira un gate: **G1–G7 siguen `pending`** y el árbol que se certifica
sigue siendo el de `v3.75.8`.

Es un **patch de endurecimiento**: no añade producto, cierra lo que la V3.77.1
dejó abierto alrededor del diccionario personal. Siete cosas, y la primera no es
de UI.

---

## 1. Qué arregla

### (A) P0 — Control de acceso roto en `collection_id` (IDOR)

`enroll_collection` ya comprobaba de quién era la colección antes de escribir en
ella. **La ingestión no.** `add_item` y `add_bulk` aceptaban el `collection_id`
que mandara el cliente y escribían en el catálogo sin preguntar nada:
`POST /api/vocabulary/items` y `POST /api/vocabulary/items/bulk`, los dos
endpoints nuevos de la V3.77.0.

El alcance, medido antes de decidir qué se cierra: lo que **no** era un fallo es
que un pack global sea destino de todos —eso es lo que significa «global» y es la
semántica que `enroll_collection` ya aplicaba—. Lo que **sí** era un fallo es que
**un perfil pudiera escribir en la lista privada de otro perfil**, y que
apuntar a una colección inexistente no fuera un «no puedes» sino una excepción.
`collection_id` es **entrada pública del cliente**, y ahí está la definición de
IDOR. El daño, en el caso real, es además **escritura** y no lectura: persistente,
y sufrido por quien no lo provoca.

El arreglo es la misma puerta que ya existía, extraída a un predicado puro
(`_collection_writable`) que usan los tres sitios: `enroll_collection` (como
antes), `add_item` y `add_bulk`. Un pack global (`user_id=''`) sigue siendo de
todos y sigue siendo destino válido; la lista privada de otro perfil y la
colección inexistente **no**. No se cierra más de lo que `enroll_collection`
cerraba: la ingestión pasa a tener **exactamente** el mismo criterio, que es lo
que permite decir «ya no hay dos puertas» en vez de «hay una puerta nueva».

### (B) P1 — `ErrorBoundary` en el root y por ruta

Hasta ahora **no había ningún boundary**. Un `throw` en render no rompía «la
tarjeta»: desmontaba el árbol entero y dejaba al alumno en blanco. Eso es lo que
convirtió el fallo de la V3.77.0 —un campo que faltaba en una respuesta HTTP— en
una pantalla muerta, y es lo que la V3.77.1 parcheó **solo en el componente donde
se había visto**.

`ErrorBoundary` declara dos radios porque el coste de fallar no es el mismo:

- `scope="app"` en `main.tsx`: captura lo que ningún boundary interno pudo
  atrapar. No hay contexto de i18n por encima de `<App />`, así que lee las
  cadenas con `translate()` a partir del idioma **persistido**.
- `scope="route"` en el `Workspace`: un fallo en una pantalla deja navegación,
  cabecera y perfil utilizables.

El detalle técnico se muestra plegado (`<details>`): información honesta sin
convertir el aviso en una traza ilegible.

### (C) P1 — Normalización runtime de contratos (H4 y hermanas)

Este era el hallazgo de fondo: **la V3.77.1 arregló una frontera y el padre tenía
el mismo defecto sin tocar.** `PersonalDictionary` —el componente que monta
`RetentionSession`, `ReviewQueueSection` y el `AddVocabSection` ya parcheado—
guardaba dos respuestas de red sin comprobar la forma (`setLexicon(data)`,
`setCandidates(drill.words)`), y pintaba `summary.by_cefr.map(...)` y
`sortLexicalItems(items)`. Un contrato incompleto mataba **la pantalla del
diccionario** y, con ella, a los tres hijos: el parche del hijo nunca llegaba a
actuar porque el árbol moría en el padre.

Nuevo módulo `frontend/src/api/normalize.ts`: `asArray`, `asNumber`, `asString`,
`asBoolean`, `asStringArray` y normalizadores por contrato (`normalizeLexicon`,
`normalizeDrillCandidates`, `normalizeVocabCollections`, `normalizeRetentionDue`,
`normalizeDictionaryEntry`, `normalizeReviewQueue`). **El estado de React nunca
recibe una forma sin comprobar**, y la defensa está en la frontera de API
(`api/vocabulary.ts`, `api/learning.ts`) **y** otra vez en los componentes, para
que sigan siendo seguros aunque se monten con un cliente sustituido.

Se cierran además las hermanas del mismo defecto: `ReviewQueueSection` usaba
`queue?.items ?? []`, que es **más débil** que el `Array.isArray(...)` de
`AddVocabSection` —`??` deja pasar un `items` truthy que no sea array—,
`DictionaryLookup` guardaba `entry` sin normalizar y `wordDrill`/`wordDrillSteps`
hacían `.map` sobre `options` sin guardia.

Y el camino que no se había contado: **`userId === null` dejaba el spinner
infinito**. `refresh()` salía temprano y `lexicon` se quedaba en `null` para
siempre; la vista giraba sin pedir nada. Ahora dice que hace falta elegir perfil.

### (D) P1 — `PersonalDictionary` en modo incrustado

`DictionaryScreen` ya es dueño del layout y pinta `h1` + subtítulo + ancho de
página. `PersonalDictionary` hacía lo mismo, así que la pantalla del diccionario
tenía **dos `h1`** y el ancho reducido dos veces. La prop `showHeader` replica el
patrón que `DictionaryLookup` ya usaba: **un solo dueño del layout**.

### (E) P2 — El cierre de sesión de retención no se veía nunca

Al calificar la última tarjeta, el camino de fin llamaba a `load()` e inmediatamente
reseteaba `index`/`done`. Resultado: la pantalla de resumen —«N tarjetas
revisadas»— **no se veía jamás**; el alumno volvía a la cola sin saber qué había
pasado. Ahora el índice avanza hasta el resumen, que se queda hasta que el alumno
decide, con acción de actualizar.

### (F) P2 — Mis listas y packs, interactivos

Los packs de tema y «Mis listas» eran badges **decorativos**: decían que existían
y no ofrecían ningún camino. Ahora son filas con `item_count` y una acción que
abre una `RetentionSession` acotada a esa colección. La semántica de «Re-enroll»
se sustituye por el estado real —«En mi diccionario»— más «Repasar»: inscribirse
dos veces siempre fue idempotente, así que la etiqueta prometía un efecto que no
existía.

### (G) P3 — Batch de membresías y siembra FSRS

`add_membership` y `_ensure_fsrs_lexicon` abrían **una conexión por palabra**.
`enroll_collection` y `add_bulk` insertan ahora las membresías en **una sola
transacción** (`collections_repo.add_memberships`) y siembran las tarjetas FSRS
en un solo paso (`fsrs_cards_by_ids` + `upsert_fsrs_cards`). Con 40 palabras:
**≤ 2 conexiones** para las membresías y **≤ 3** para FSRS, constantes y no
proporcionales al tamaño del lote.

---

## 2. La comprobación que importa: que los candados muerdan

Cuatro candados nuevos, y **los dos primeros se comprobaron revirtiendo el
código**, no razonando sobre él.

**(A) El candado de seguridad.** Se neutralizó la guardia en `add_item` y
`add_bulk` (`and False`) y se corrió el módulo:

```
FAILED tests/test_retention_personal_v377.py::test_add_item_rejects_collection_of_another_user
FAILED tests/test_retention_personal_v377.py::test_bulk_rejects_collection_of_another_user
FAILED tests/test_retention_personal_v377.py::test_bulk_rejects_missing_collection
3 failed, 6 deselected
```

Y el tercero falla de una forma que hay que contar: **no falla la aserción, salta
un `sqlite3.IntegrityError: FOREIGN KEY constraint failed`** desde
`repositories/collections.py`. Es decir, sin la guardia, apuntar a una colección
inexistente no daba un «no puedes» limpio: daba **una excepción sin capturar** —
un 500— en mitad de la escritura.

**(B) El candado de H4.** Se hizo `normalizeLexicon`/`normalizeDrillCandidates`
un passthrough (que es exactamente el comportamiento de la V3.77.1: guardar la
respuesta tal cual) y se corrió el test del componente:

```
❯ sortLexicalItems src/features/vocabulary/dictionary.ts:13:14
❯ PersonalDictionary src/features/vocabulary/PersonalDictionary.tsx:130:18
Tests  2 failed | 11 passed (13)
```

**Muere en la línea 130, en render, que es el mismo sitio y el mismo modo que
describe el hallazgo.** El H4 no era teórico.

**(C) El caso de `userId === null`.** Se devolvió la rama a su estado anterior
(mostrar «Cargando…») y el test `sin perfil activo no se queda en «Cargando…»
indefinidamente` **falla**. Con el código anterior no había mensaje ni parada.

---

## 3. Verificación

| Instrumento | Resultado |
| --- | --- |
| `pytest` (backend) | **2972/2972** |
| `ruff check .` (backend) | limpio |
| `scripts.transfer_validation` | `OK=True` |
| `tsc --noEmit` | limpio |
| `vitest run` | **910/910** (104 ficheros) |
| `npm run build` | correcto (`package.json` en `3.77.2`) |
| i18n `--strict` | 1590 cadenas · **0 huérfanas / 0 usadas sin definir / 0 duplicadas** |
| `npm run audit:contrast` | 480 pares (+6 guardas) · **0 bloqueantes** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.77.2`) |
| `validation_gate.py auto` | **10/10** |
| `check_beta_v3.py` | OK (congelación pedagógica V2.7–V2.12) |
| `content_validation.py` | `OK=True quality=True` |
| `pytest` (launcher) | **205/205** + `ruff` limpio |
| `Playwright` (visual) | **NO ejecutado en local en esta release** (§4.2) |

---

## 4. Honestidad

1. **El P0 es el hallazgo de verdad de esta release, y no venía de la UI.** La
   V3.77.1 arregló un parche de pantalla; esto era **una autorización que
   faltaba** en dos endpoints nuevos de la V3.77.0. Los dos escriben en la BD de
   un perfil y los dos aceptaban un destino elegido por el cliente. Se declara
   aquí, con su severidad, en vez de enterrarlo entre las mejoras de UX: el orden
   de las secciones de este documento es la prioridad, no la cronología.
2. **La suite visual NO se ha corrido en local para esta release.** Es el
   instrumento que destapó la V3.77.1, y por eso el hueco se declara en vez de
   disimularse: la autoridad es el CI. Dicho eso, hay **una decisión tomada
   contra esa suite a propósito**: los botones nuevos de «Repasar» en
   `AddVocabSection` exponen `aria-expanded`, **no** `aria-pressed`, porque
   `drillProvenance.spec.ts` localiza la entrada al drill con
   `li:has(button[aria-pressed]) button[aria-pressed]`. `aria-expanded` describe
   mejor lo que hace el botón —abre un panel— y de paso no compite por un
   selector del que el test no es dueño. **Eso lo tiene que confirmar el CI, no
   este documento.**
3. **La normalización es un contrato de FORMA, no de SIGNIFICADO, y tiene un
   precio.** Un léxico incompleto ya no tumba la pantalla, pero se degrada al
   estado vacío: el alumno ve «no hay palabras» en vez de ver un error. Es un
   fallo **silencioso** donde antes había uno **ruidoso**, y es un intercambio
   deliberado: una pantalla en blanco lo pierde todo y no se puede recuperar; un
   estado vacío engaña pero se puede navegar y reintentar. Lo que mitigaría el
   engaño es distinguir «vacío porque no hay» de «vacío porque no entendí»; hoy
   `loadError` solo cubre el fallo de red, no el contrato raro. Queda declarado
   como deuda, no como resuelto.
4. **El radio de la V3.77.1 era mayor de lo que decía su release note.** Decía
   que el diccionario personal «no puede morir por un campo que falta» y lo
   cierto es que **sí podía**, en el componente padre, con dos llamadas de red en
   vez de una. Se deja escrito porque una release note es una promesa: si la
   promesa era más amplia que el código, el fallo no estaba solo en el código.
5. **La regresión de layout la habría dejado pasar `DictionaryScreen.test.tsx`.**
   Ese fichero mockea la vista, así que puede verificar que la pantalla monta
   pero **no** que haya un solo `h1`. El test de layout nuevo monta el componente
   **real** y cuenta encabezados; sin él, el doble `h1` de V3.77.0→V3.77.1 no
   estaba cubierto por nadie.
6. **Nada de las releases anteriores cambia de significado.** La retención
   léxica, los perfiles con autorización del webmaster, el PIN y el doble candado
   siguen exactamente como se publicaron. Esta release **no** añade producto: no
   hay ni una pantalla nueva, ni un endpoint nuevo, ni una tabla nueva. Lo que
   añade es que lo publicado **se sostenga** y que un destino se elija por
   derecho propio y no porque el cliente lo diga.
