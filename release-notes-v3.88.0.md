# Release notes — English Tutor v3.88.0

**Fecha:** 2026-09-29 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.87.1 → 3.88.0`

**Con backend y frontend, SIN migración de BD** (todo es aditivo: el precalentado reutiliza la tabla
`dictionary_entries` y **no crea ninguna tabla**), **CON dos endpoints nuevos**
(`POST /api/vocabulary/dictionary/warmup` → **202** + trabajo de fondo en memoria, y
`GET /api/vocabulary/dictionary/warmup/{job_id}`) y **CON bump de `GENERATOR_VERSION`
(`1.5.0 → 1.6.0`)**. `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate** —siguen los **ocho**, todos
en `pending`— y `docs/audit/validation-evidence.json` **sigue sin existir**. Incluye el **estudio de
viabilidad del diccionario offline** (`docs/DISENO-V388-DICCIONARIO-OFFLINE.md`), que **no
implementa** el empaquetado.

**En una frase.** La app deja de parecer colgada cuando el modelo local tarda, el diccionario deja de
servir un significado único cuando la palabra tiene varios, y la caché del diccionario se puede
**precalentar** y **medir**.

---

## 1. La espera se ve (spinner y aviso de que va para largo)

Cinco operaciones reales se presentaban como una pantalla inocente o un botón mudo:

| Dónde | Qué se veía | Qué se ve ahora |
|---|---|---|
| Cola de repaso del día (`ReviewToday`) | «nada que repasar» **mientras la petición volaba** | `LoadingNotice` |
| Mazos y fichas (`DecksTab`/`CardsTab`/`DeckEditor`/`ReadyDecks`) | un `disabled` silencioso | spinner **en el botón activo** |
| `loadDecks()` del panel de alta | «no hay mazos» **mientras cargaba** | `LoadingNotice` con `dictionary.lookup.decksLoading` |
| Léxico (`LexiconInventory`), carga inicial y refresco | nada | `LoadingNotice` |
| Altas de vocabulario (`AddVocabSection`), palabra / bloque / pack | tres botones deshabilitados | spinner y etiqueta por acción |
| Pestañas de estudio y estadísticas | texto plano | `LoadingNotice` |

**El componente** es `frontend/src/components/LoadingNotice.tsx`:

- `role="status"` + `aria-busy="true"` + `aria-live="polite"` (región viva, `<Loader2>` con la
  misma convención que `PanelState`/`TabLoading`).
- Pasados **`slowAfterMs = 4000`** sin resolverse, el spinner **se convierte en reloj** (`Clock`) y
  aparece `common.stillWorking` («Seguimos trabajando… el modelo local puede tardar un poco»). Esto
  es exactamente lo pedido: *«si va a tardar bastante, un mensaje de espera o un reloj»*.
- El temporizador se limpia al desmontar y **no** se dispara si la operación termina antes.

**Una decisión que evita un defecto:** los estados ocupados de acciones **distintas** sobre la misma
lista van **separados** (`deletingId` para mazos, `deletingCardId` para fichas, `busyAction` para el
resto). Con un solo booleano, borrar un mazo habría pintado de «ocupado» el botón de añadir otro.

---

## 2. Los dos o tres significados principales (y el fallo era de datos)

La plomería existía **de punta a punta** desde V3.86.0: columna `meanings_json` en las dos tablas,
`normalize_meanings`, `DictionaryMeaningOut` y el selector de significado en la tarjeta. Lo que
faltaba era **contenido**: el prompt pedía *«at most 6» significados* **sin exigir mínimo**, y en la
BD de uso solo **6 de 33** entradas tenían alguno.

**Backend — el contrato de contenido (`services/dictionary_content.py`):**

- Nueva constante **`MIN_MEANINGS = 2`**, inyectada como **regla dura en los DOS prompts**
  (`_SYSTEM_PROMPT` EN→ES y `_REVERSE_SYSTEM_PROMPT` ES→EN): *si la palabra tiene más de un
  significado común, se dan **al menos los 2 más comunes** (hasta 6), **ordenados del más común al
  menos***. Las reglas de nombre propio al final y el contrato JSON quedan **intactos**, así que
  `parse_content` no se toca.
- **`GENERATOR_VERSION` sube a `1.6.0`.** Es la palanca correcta: `_content_is_fresh` **invalida y
  regenera de forma perezosa** las **33 + 13** filas cacheadas (la primera consulta de cada palabra
  vuelve a pagar el modelo). No hay barrido en el arranque y no hay migración de datos.

**Frontend — la presentación (`DictionaryLookup.tsx`):**

- Los **3 primeros significados se ven desplegados por defecto** en el `fieldset` que ya pintaba
  término, categoría, ámbito y glosa.
- Si hay más de 3, el resto se pliega tras **`InfoDisclosure` con `content="options"`** —el patrón
  «...» = «abre para configurar» de V3.75.7—, **reaprovechando la misma lista de radios**.
- Copia: `dictionary.lookup.meanings` pasa a «Main meanings» / «Significados principales» y aparece
  `dictionary.lookup.moreMeanings` («Ver los otros {count} significados»).
- **La semántica de selección NO cambia:** `meaningIndex`, `onPickMeaning` y el `equivalent` siguen
  igual, así que el significado elegido manda sobre el audio, la práctica y el alta.

**Lo medido con el modelo real, y se declara tal cual** (§5, honestidad): de 4 palabras,
`lantern` devolvió **un** significado y `quaint` coló el topónimo **`San Miguel`** como tercero. El
filtro de nombres propios de V3.86.0 lo deja **al final** y **nunca preseleccionado**, pero **el
modelo lo propone**: el prompt **orienta**, no **garantiza**.

---

## 3. Precalentado del léxico (la espera convertida en algo que el alumno adelanta)

**Endpoints nuevos** (`backend/routers/vocabulary.py`):

| Método y ruta | Respuesta |
|---|---|
| `POST /api/vocabulary/dictionary/warmup` (`{words: [...]}`) | **202** + `DictionaryWarmupJobOut` |
| `GET /api/vocabulary/dictionary/warmup/{job_id}` | `DictionaryWarmupJobOut` |

`DictionaryWarmupJobOut` publica `id`, `status` (`running`/`done`/`error`), `total`, `prepared`,
`skipped`, `pending` y `error`. El ciclo de vida vive en `backend/domain/dictionary_warmup.py`
(**en memoria**, con `DICTIONARY_WARMUP_JOBS_KEPT = 20` y `DICTIONARY_WARMUP_MAX_WORDS = 60` en
`config.py`), siguiendo el patrón de job asíncrono que ya usa `routers/listening.py`.

**La decisión que lo hace honesto:** el trabajo reutiliza **el camino de generación que ya existía**
(`_ensure_cached_content`), así que hereda **single-flight, negative cache y las MISMAS cuotas**.

- **Precalentar no genera nada que una consulta no generaría**, solo **antes**. No hay contenido
  nuevo ni camino de datos nuevo.
- Sin cupo (10 palabras nuevas por usuario y minuto; 40 por minuto global), la palabra cuenta como
  **`skipped`**, que **no es un error**: es cuota agotada, modelo caído o timeout, y se reintenta.
- El **resultado real no es el trabajo, es la caché global `dictionary_entries`**, que es
  persistente y compartida: perder el registro del trabajo (reinicio del proceso) solo pierde la
  barra de progreso, no el trabajo hecho.
- Una petición **vacía** marca el trabajo `done` **sin encolar un bucle vacío**.

**UI:** `frontend/src/features/vocabulary/DictionaryWarmupAction.tsx` en la vista de consulta
—donde el alumno sufre la primera espera—, por **encima** del buscador, para poder adelantar el coste
antes de chocarlo. Arranca el trabajo, sigue el progreso con `LoadingNotice` (con el reloj si se
alarga) y declara el resultado real: «N preparadas. M no se pudieron preparar (el modelo local puede
estar ocupado); inténtalo más tarde». Sin palabras que preparar lo dice tal cual, y un fallo al
arrancar deja reintentar.

---

## 4. La caché se puede medir

Nuevo **`scripts/dictionary_cache_report.py`**: **solo lectura** (abre SQLite en `mode=ro`, con
repliegue documentado si el WAL lo impide; **no ejecuta ningún `INSERT`/`UPDATE`/`DELETE`**).

- Cuenta entradas **por tabla** (`dictionary_entries`, `dictionary_reverse_entries`) y **por
  `generator_version`**, y separa **frescas** (las que el dominio sirve) de **obsoletas**.
- Calcula el **porcentaje con 2+ significados** sobre el total **y sobre las frescas** —la métrica
  que persigue el Incremento B—, contando aparte las filas con **JSON ilegible** para no
  confundirlas con «sin significados».
- Lista una **muestra de huecos** (frescas por debajo del mínimo) y admite `--json`, `--sample` y
  `--db`.
- Lee `GENERATOR_VERSION` y `MIN_MEANINGS` **del propio módulo** (dos regex) en lugar de
  duplicarlos: si la lectura falla, el informe lo dice en vez de comparar contra una versión
  inventada.

Medido sobre la BD de uso el 2026-09-29:

```
Contrato vigente: GENERATOR_VERSION=1.6.0  MIN_MEANINGS=2
EN→ES (directa)  [dictionary_entries]
  Entradas: 33 · frescas (1.6.0): 0 · obsoletas: 33  (1.5.0: 11, 1.4.0: 17, 1.2.0: 5)
  Significados (todas): >=2 → 6 (18,2 %) · 1 → 5 (15,2 %) · sin significados → 22 (66,7 %)
ES→EN (inversa)  [dictionary_reverse_entries]
  Entradas: 13 · frescas: 0 · obsoletas: 13 (1.4.0: 13)
  Significados (todas): sin significados → 13 (100,0 %)
```

---

## 5. El diccionario offline: estudio, NO implementación

`docs/DISENO-V388-DICCIONARIO-OFFLINE.md` existe para **responder con datos**, no para justificar una
idea. Su veredicto: **NO** se empaqueta un diccionario completo ahora; **SÍ** conviene (fase 1) un
**índice FTS5** sobre la caché y (fase 2) un **precalentado por lotes** de las **2.238** palabras del
currículum, **≈ 2 h 31 min de CPU** una sola vez, **sin licencias de terceros**.

Cifras **medidas** (no estimadas) que sostienen el veredicto:

| Medición | Valor |
|---|---|
| Palabra nueva con el modelo que la app elige (`llama3.1:8b`) | **4,05 s** de media (3,57–4,59 s en 4 palabras reales) |
| Tope configurado por generación / espera de los *waiters* | **90 s** / **60 s** |
| Palabras inglesas distintas en todo `backend/curriculum/**` | **2.238** |
| FreeDict **eng-spa** 2025.11.23 | **64.258 entradas · 3,54 MiB · CC BY-SA 3.0** (leído del `COPYING` del tarball) |
| Ese dataset convertido al esquema de la app | **35.935 entradas · 19,94 MiB · 44,7 % con ≥2 equivalentes ES** |
| Índice FTS5 sobre él | **+4,58 MiB** y **0,2 s** de construcción |
| Inversa ES→EN hoy (escaneo O(N) en Python) a 64.258 filas | **192 ms de SQL + 76 ms de bucle** por consulta |
| La misma búsqueda con índice FTS5 | **0,034 ms** (prefijo) / **0,078 ms** (frase) |
| FreeDict **spa-eng** (la inversa) | **4.502** entradas, marcada `too small` por su propio índice |

**La premisa de V3.30 era falsa.** El diseño de V3.30 descartó el dataset empaquetado alegando
«sin fuente con licencia y bilingüe EN→ES disponible». **Existe** (FreeDict eng-spa, con licencia
declarada dentro de su propio paquete). La conclusión se mantiene, pero por **otras tres razones**
que sí se sostienen: el léxico real de la app es de **2.238** palabras (empaquetar 35.935 es 16×
peso muerto), **CC BY-SA 3.0 obliga a atribución y *ShareAlike* de la obra derivada**, y la fuente
**no cubre la inversa**. Y aparece una cuarta que V3.30 no pudo ver porque la caché era diminuta: **la
arquitectura interna de la inversa no escala** (el O(N)).

---

## 6. Verificación

| Comprobación | Resultado |
|---|---|
| `pytest` backend | **3202/3202** |
| `vitest run` | **1078/1078** (111 ficheros) |
| `tsc --noEmit` | limpio |
| `ruff check .` (backend y lanzador, cada uno con su `pyproject.toml`) | limpio |
| `check_i18n_coverage.py --strict` | **1833** cadenas · 0 huérfanas / sin definir / duplicadas / vacías |
| `contrast_audit.mjs --strict` | **480 pares + 6 guardas / 0 bloqueantes** |
| `npm run build` | correcto |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.88.0`) |
| Playwright (diccionario, puente, responsive y flashcards) | **34 passed · 2 skipped** |
| `scripts/dictionary_cache_report.py` | informe emitido (solo lectura) sobre la BD de uso |

---

## 7. Honestidad: lo que NO trae

1. **No se ha empaquetado ningún dataset.** El estudio existe justamente para **medir** la decisión,
   no para anunciarla. Empaquetar sigue siendo una **decisión del gerente** con obligaciones de
   licencia.
2. **La generación de significados está orientada por prompt, NO garantizada por el modelo.** De 4
   palabras medidas, `lantern` devolvió **un** significado (defendible: «lantern» es esencialmente
   «farol/linterna») y `quaint` coló el topónimo `San Miguel`. Quien quiera una garantía dura
   necesitará validación o una fuente no generativa.
3. **El escaneo O(N) de la inversa ES→EN sigue exactamente donde estaba.** Es la **fase 1
   recomendada** del estudio y **no** es trabajo hecho en esta release.
4. **El bump a `1.6.0` invalida toda la caché** (46 filas) y la primera consulta de cada palabra
   vuelve a pagar el modelo. Es intencional —la caché anterior **no cumplía** el mínimo de
   significados— y es exactamente lo que hace útil el precalentado.
5. **`senses_json` (hasta 4 sentidos gramaticales) sigue sin pintarse** en la UI, como estaba.
6. **El precalentado es en memoria y por proceso**: un reinicio pierde el **registro** del trabajo
   (no su resultado, que es la caché). Los trabajos se retienen hasta `DICTIONARY_WARMUP_JOBS_KEPT`.
7. **No hay tag `v3.87.1`.** Su delta —la errata del contrato de `mode`, los contadores de la cola,
   el comparador sin `casefold` y el panel de estudio plegado— **se publica dentro de `v3.88.0`**,
   por decisión explícita de no partirlo en dos commits ni re-sellar las versiones a `3.87.1`.
   `release-notes-v3.87.1.md` se conserva como nota de la etapa y su encabezado lo declara.
8. **Los ocho gates humanos siguen `pending`** y el ancla de certificación sigue en `v3.83.1`.

---

## 8. Archivos tocados (resumen)

**Backend:** `config.py` · `services/dictionary_content.py` · `domain/dictionary_warmup.py` (nuevo) ·
`schemas/vocabulary.py` · `routers/vocabulary.py` · `tests/test_dictionary_meanings_v388.py` (nuevo) ·
`tests/test_dictionary_warmup_v388.py` (nuevo).

**Frontend:** `components/LoadingNotice.tsx` (nuevo) · `components/LoadingNotice.test.tsx` (nuevo) ·
`utils/i18n.ts` · `features/vocabulary/DictionaryWarmupAction.tsx` (nuevo) ·
`features/vocabulary/DictionaryWarmupAction.test.tsx` (nuevo) · `features/vocabulary/DictionaryScreen.tsx`
· `features/vocabulary/DictionaryLookup.tsx` · `features/vocabulary/FlashcardsScreen.tsx` ·
`features/vocabulary/ReviewToday.tsx` · `features/vocabulary/LexiconInventory.tsx` ·
`features/vocabulary/AddVocabSection.tsx` · `api/vocabulary.ts` · `api/normalize.ts` · `types/api.ts` ·
`package.json` · `package-lock.json`.

**Instrumento nuevo:** `scripts/dictionary_cache_report.py`.

**Docs y release:** `docs/DISENO-V388-DICCIONARIO-OFFLINE.md` (nuevo) · `release-notes-v3.88.0.md`
(este fichero) · `CHANGELOG.md` · `PLAN.md` · `README.md` · `docs/RELEVO.md` · `docs/audit/PARKED.md`.

---

## Para auditar esta release

- **Ancla:** el tag **`v3.88.0`**, sobre `v3.87.1`.
- **Alcance:** el aviso de espera (`LoadingNotice` y sus siete puntos de cableado), el contrato de
  contenido de los significados (`MIN_MEANINGS = 2` + `GENERATOR_VERSION = "1.6.0"` + la presentación
  en 3 + resto), el precalentado (`domain/dictionary_warmup.py`, los dos endpoints, la acción de UI y
  su reutilización de `_ensure_cached_content`) y el instrumento `scripts/dictionary_cache_report.py`.
- **Lo que NO toca:** FSRS y su clave, `DECISION_POLICY_VERSION` / `CURRICULUM_VERSION` /
  `LISTENING_BANK_VERSION`, las evaluaciones, el esquema de BD (no hay columnas ni tablas nuevas en
  el precalentado), el contrato de la consulta del diccionario y el número o la definición de los
  gates.
- **La pregunta que este release pide al auditor:** ¿el aviso de espera **muerde** de verdad —es
  decir, aparece cuando la operación tarda y **no** cuando no tarda—, o se ha añadido un spinner
  decorativo a siete sitios? Y, en paralelo: el estudio del diccionario offline, ¿**mide** o
  **opina**?
