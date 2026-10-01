# Release notes — English Tutor v3.86.0

**Fecha:** 2026-09-26 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.85.1 → 3.86.0`

> **Nota de alcance — esta release ABSORBE a `v3.85.1`.** El trabajo de `v3.85.1` (la sesión de
> repaso que dejaba de atascarse, el panel APRENDER que recuperaba el repaso, la accesibilidad y
> el sello del informe de contraste) se redactó, se verificó y **se quedó sin etiquetar** en el
> árbol de trabajo: la etiqueta `v3.85.1` **no existe** en el repositorio y **no se recrea**.
> Este tag **`v3.86.0` lo incluye íntegro**. `release-notes-v3.85.1.md` se conserva con una
> errata en cabecera para que nadie persiga un tag inexistente.

**CON backend y frontend, CON migración de BD ADITIVA e idempotente, CON endpoints nuevos y CON
bump de `GENERATOR_VERSION` (`1.4.0 → 1.5.0`).** `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION`
sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate** —siguen
los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** El diccionario deja de servir **un solo** significado por palabra (se acaba el
«lima → capital del Perú»), el alta en mazo deja de atascarse **aunque la palabra ya esté
rastreada**, y una ficha puede vivir en **varios mazos** con su **recordatorio** editable.

Esta es la **fase 1 de 2**. El estudio configurable (elegir mazos, dirección ES↔EN, escribir la
respuesta, ayudas de sílabas) queda **declarado fuera** y se implementa en la fase 2.

---

## 1. El defecto reportado, y era de datos: «lima» era la capital del Perú

La caché del diccionario guardaba **una sola** traducción por palabra, con `word` como clave
única, en `dictionary_entries` (EN→ES) y `dictionary_reverse_entries` (ES→EN). `senses_json`
separaba por **categoría gramatical**, no por **significado**. Y el prompt pedía *«the most common
English equivalent»*: **no prohibía nombres propios** y recibía **solo la palabra, sin contexto**,
mientras `parse_reverse_content` aceptaba cualquier texto no vacío. Un `lima → Lima` se guardaba
bajo `word="lima"` y se servía **a todos los alumnos para siempre**.

Y lo peor: **la traducción curada correcta ya existía** (`file → lima`, `screw → tornillo`) en los
packs de vocabulario del currículum, pero la búsqueda **no la consultaba**.

### 1.1 El contrato gana significados elegibles

Ambos prompts devuelven además `meanings: [{term, pos, gloss, domain, proper_noun}]`, con la regla
explícita: **nunca** un nombre propio como equivalente de un nombre común; si existe un sentido de
nombre propio, va **el último** y marcado `proper_noun: true`. Se conservan
`translation`/`english`/`definition`/`situation`/`senses` (compatibilidad y scoring semántico
V3.44). Normalizador nuevo `normalize_meanings` (tope 6, dedupe por término + `pos`, recorte) y
**el defecto es el primer significado que NO es nombre propio**. En filas antiguas se degrada a
`senses` + `translation`, así que la UI siempre tiene al menos una opción.

- Nuevo `DictionaryMeaningOut {id, term, pos, gloss, domain, proper_noun}` y
  `DictionaryEntryOut.meanings`; **`senses` no se toca**.
- Columna aditiva `meanings_json TEXT NOT NULL DEFAULT ''` en **las dos** tablas de caché, con el
  mismo `PRAGMA`-guard que `senses_json`.

### 1.2 La corrección de la caché envenenada es perezosa, y se declara así

`GENERATOR_VERSION` sube **`1.4.0 → 1.5.0`**. El dominio solo sirve caché cuya `generator_version`
coincide, así que la fila envenenada de `lima` **deja de servirse** y se regenera **la primera vez
que alguien la consulte**. No hay barrido de caché en el arranque: es perezoso a propósito.

### 1.3 Autoridad determinista y gratis: los packs curados

`dictionary_reverse.py` gana `match_pack_translation(term, items)`: lee `vocab_collection_items`
(los packs **globales**) y devuelve los equivalentes ingleses curados del término español,
ordenados por calidad de coincidencia (exacta antes que parcial) y, a igualdad, alfabéticamente
(**determinista**), sin duplicados. Es lo que hace que `tornillo → screw` y `lima → file` sean
correctos, **instantáneos y sin coste de modelo**. Los candidatos curados se **fusionan** con los
del modelo en la lista de significados.

### 1.4 El alumno elige, y lo elegido manda

`DictionaryLookup` gana un **selector de significado** en la tarjeta de resultado: término, `pos`,
ámbito y glosa. Los significados de **nombre propio se marcan** («nombre propio») y **nunca** se
preseleccionan. El elegido manda sobre el término de práctica, el audio, el bloque «In English» y
la carga útil del alta; cambiar de significado invalida la práctica anterior (era de **otro**
significado).

## 2. El alta en mazo deja de atascarse

| Antes | Ahora |
|---|---|
| Con `usage.tracked` verdadero **no se pintaba** el botón de añadir | El panel está **siempre** disponible |
| Solo quedaba «Estudiar en Flashcards», que saltaba al mazo automático **sin mazo elegido** | El CTA viaja **siempre** con el mazo elegido; con varios, abre el principal y **lo dice** |
| Un `deckError` escondía el selector **y no se reintentaba nunca** | Se ofrece **«Reintentar»**; un fallo de red no esconde los mazos |
| Un mazo por alta | **Casillas**: la ficha nace en **todos** los marcados, en una sola escritura |
| `translation: null` → ninguna acción | Se pide el **reverso a mano** y la tarjeta se crea honestamente |
| Sin mnemónico | Campo opcional **«Recordatorio»** en el propio panel |
| El diccionario **incrustado** (APRENDER → Vocabulario) no recibía ninguna salida | Recibe el salto a la pantalla central **con el mazo elegido** |

Si la palabra **ya está rastreada**, el panel lo dice y **no reescribe el léxico**: solo crea o
actualiza la ficha y sus mazos, así que no se duplica el aprendizaje.

### 2.1 Un fallo real que destapó la sonda: el arranque con una cola ajena

Al montar la sonda del puente apareció un defecto **de verdad**: `StudyTab` arrancaba la sesión en
cuanto la cola estuviera cargada, **sin comprobar de qué mazo era**. Al llegar del diccionario con
un mazo manual, la primera carga (la del mazo automático, que aún estaba seleccionado) podía
resolverse **después** del foco: el encargo se gastaba con una cola ajena y el alumno se quedaba
**en el panel, sin sesión**, aunque su mazo sí tuviera tarjetas. El arranque automático ahora exige
`queue.deck.id === deck`. Está fijado con una prueba unitaria que reproduce el orden adverso.

## 3. Una ficha, varios mazos, con recordatorio

### 3.1 Migración aditiva e idempotente (en `init_db()`)

- Tabla puente `flashcard_deck_cards (card_id, deck_id, created_at, PK(card_id, deck_id))` con FK
  a `flashcard_cards` (`ON DELETE CASCADE`) y a `flashcard_decks`, más índice por `deck_id`.
- Columna `flashcard_cards.mnemonic TEXT NOT NULL DEFAULT ''`.
- **Backfill solo la primera vez que nace la tabla**: `INSERT OR IGNORE ... SELECT id, deck_id,
  created_at FROM flashcard_cards`. Repetirlo en cada arranque **resucitaría** una pertenencia que
  el alumno quitó a propósito (el `deck_id` deprecado seguiría apuntando ahí).
- `flashcard_cards.deck_id` queda **deprecada** como «mazo principal» (un único escritor en el
  dominio) para que el esquema viejo siga abriendo.

Una BD de `v3.85.1` se abre **intacta** y sus fichas quedan con su pertenencia de siempre y sin
recordatorio. `init_db()` es idempotente y hay prueba que lo fija (índices de `PRAGMA table_info`
incluidos).

### 3.2 API **ficha-primero** (el id de ficha es global del usuario)

```
GET    /api/vocabulary/cards                      → todas las fichas (o las de `deck_id`)
POST   /api/vocabulary/cards                      → crea con `deck_ids` + `mnemonic`
PATCH  /api/vocabulary/cards/{card_id}            → parche PARCIAL (front/back/mnemonic/deck_ids)
DELETE /api/vocabulary/cards/{card_id}            → borra la ficha y sus pertenencias
POST   /api/vocabulary/cards/{card_id}/decks      → añade una pertenencia
DELETE /api/vocabulary/cards/{card_id}/decks/{deck_id} → la quita
```

- El parcheo es **parcial de verdad**: editar solo el recordatorio **no** obliga a reenviar el
  anverso. Si llega `deck_ids`, el conjunto **no puede quedar vacío**.
- `set_card_decks` reemplaza el conjunto **en una transacción**.
- **No se duplica**: si ya existe una ficha del usuario con el mismo anverso normalizado, se
  **reutiliza** y solo se añade la pertenencia.
- Las rutas legacy `/decks/{id}/cards...` se conservan como **envoltorios finos** con docstring
  marcado como **deprecado**: no rompen a ningún consumidor, pero ya no son la fuente de verdad. El
  pegado masivo sigue en su endpoint y acepta el tercer campo opcional
  (`anverso,reverso,recordatorio`).
- Cliente HTTP tolerante a `204 No Content`: un borrado aplicado sin cuerpo ya no se lee como
  «falló el borrado» (antes `res.json()` lanzaba `SyntaxError`).

### 3.3 Borrar un mazo ya no se lleva por delante lo compartido

`delete_deck` borra **las pertenencias** de ese mazo, **conserva** las fichas que siguen en otro y
borra las huérfanas **con sus cartas FSRS** (recolectando los ids antes, para no dejar estado a
medias). Antes de borrar el mazo, la columna deprecada `deck_id` de las fichas supervivientes se
repunta a `MIN(dc.deck_id)` de las pertenencias que quedan, para satisfacer el FK. La UI **dice
cuántas se borran y cuántas se conservan** antes de confirmar.

### 3.4 La cola no sirve una ficha dos veces

`deck_queue` resuelve por la tabla puente y devuelve cada ficha **una sola vez** (`dedupe`), aunque
pertenezca a varios mazos.

### 3.5 UI

- **Pestaña «Fichas»** rediseñada: sin mazo forzado; cada ficha muestra sus **mazos como etiquetas**
  y se editan con **casillas**; el formulario tiene anverso, reverso y **recordatorio**; el
  buscador, los filtros y el orden se mantienen; el pegado masivo acepta el recordatorio. El
  recordatorio se puede **editar y borrar** (botón con icono).
- **Pestaña «Mazos»**: contadores por tabla puente y borrado con **aviso explícito**.
- **`StudySession`** muestra el recordatorio en el **reverso**, en pequeño y separado: es una ayuda
  para recordar, no la respuesta de la tarjeta. **No se toca la máquina de estudio** (eso es fase 2).

## 4. La salida del diccionario incrustado

El panel de APRENDER → Vocabulario **no hospeda la sesión** (el modo `flashcards` se proyecta con
`toPanelView`), así que una palabra ya rastreada se quedaba **sin ninguna acción**. Ahora la vista
de **consulta** del panel declara que admite el salto
(`RouteDictionaryConfig.allowFlashcardsJump`), y la página construye el callback: **persiste la
vista** y **navega** a `#/diccionario`, con el **mazo elegido viajando en un recado de un solo uso**
(`utils/studyFocus`). Sin transportar el mazo, el alumno aterrizaría en el mazo automático y
creería que su tarjeta no entró. El recado se consume en el montaje de la pantalla central: no es
una preferencia, es un encargo de un clic.

## 5. Riesgos y límites declarados

1. **El léxico (`vocabulary`) y la ficha manual siguen separados** (no se reabre la consolidación
   aparcada desde V3.77). El **recordatorio vive en la ficha**, así que el **mazo automático (id 0)
   no lo muestra**. Se declara, no se disimula.
2. **`flashcard_cards.deck_id` es una columna deprecada de un solo escritor.** Deuda declarada con
   plan de retirada en una ventana de reconstrucción de tabla.
3. **La corrección de la caché es perezosa**: `lima` seguirá mal hasta que alguien la consulte tras
   el bump. No hay barrido.
4. **`QUEUE_MAX` (100) y los límites diarios no cambian** en esta release.
5. **La fase 2 no está**: elegir mazos al estudiar, dirección ES↔EN, escribir la respuesta y ayudas
   de sílabas quedan fuera y documentadas.

---

## 6. Pruebas

**Backend (pytest).**

| Fichero | Qué fija |
|---|---|
| `test_multi_deck_v386.py` (**nuevo**) | una ficha en varios mazos **sin duplicar la fila**; alta/baja de pertenencias una a una; el recordatorio se edita solo y se puede borrar; **borrar un mazo conserva las fichas compartidas y lo dice**; el mismo anverso se **reutiliza**; una ficha exige un mazo real y **el automático nunca lo es**; fichas y pertenencias **no cruzan entre usuarios**; `init_db()` **idempotente** y con backfill **una sola vez** |
| `test_dictionary_reverse_v339.py` | `normalize_meanings` manda los nombres propios al final y deduplica; `parse_reverse_content` **nunca** cae a un nombre propio; el candidato **curado del pack** se prefiere sin modelo; **`lima` sirve la herramienta y no la capital**; fusión de significados curados; la caché directa expone significados y término por defecto; el repositorio hace round-trip de los significados |
| `test_dictionary_content_v330.py`, `test_senses_v344.py`, `test_situational_cue_v338.py` | el contrato gana `meanings` en los prompts y `GENERATOR_VERSION == "1.5.0"` |
| `test_flashcards_v378.py` | el envoltorio legacy sigue sirviendo la ficha con sus mazos |

**Frontend (Vitest).**

| Fichero | Qué fija |
|---|---|
| `DictionaryLookup.test.tsx` | el selector de significado y que el elegido **manda** en la práctica y en el alta; el alta con palabra **ya rastreada** (ficha sí, léxico no); el **recordatorio** viaja y los mazos marcados van juntos; el estado **PARCIAL** y el reintento que no repite el alta; el nombre de mazo duplicado **no** esconde los mazos |
| `FlashcardsScreen.test.tsx` | el alta con varios mazos y el recordatorio; etiquetas de mazo y edición por casillas; borrado de mazo con aviso de compartidas; **y el arranque que ya no se come una cola ajena** |
| `DictionaryScreen.test.tsx` | el salto del diccionario **incrustado** abre Flashcards **en el mazo pedido**, y el recado es de **un solo uso** |
| `StudySession.test.tsx` | el recordatorio se ve en el reverso |

**E2E (Playwright).**

- `dictionaryFlashcardsBridge.spec.ts`: la sonda del puente se amplía con los casos de la release
  —el nombre propio **nunca** preseleccionado y el elegido mandando en el alta, la ficha que nace en
  **todos** los mazos marcados con su recordatorio, la palabra **ya rastreada** que ya no se queda
  sin salida, y la consulta **sin equivalente** que pide el reverso a mano.
- `vocabularyRoutesReview.spec.ts`: caso **nuevo** del diccionario incrustado dando salida a una
  palabra ya rastreada.
- `dictionarySmoke.spec.ts`: el bucle de medición de acciones comprueba que «Study in Flashcards»,
  «Practice this word» y «Add to Flashcards» **caben** en todos los breakpoints.
- `flashcardsSmoke.spec.ts`: deja de fijar la pestaña «Tarjetas» antigua (un mazo forzado) y pasa a
  comprobar la ficha con sus **etiquetas de mazo** y su **recordatorio**.

**Candado que muerde.** El caso del arranque (`FlashcardsScreen.test.tsx`) **falla** si el efecto
vuelve a arrancar con la cola del mazo anterior. El caso del incrustado
(`vocabularyRoutesReview.spec.ts`) **falla** si el panel deja de recibir el salto.

## 7. Verificación

| Comprobación | Resultado |
|---|---|
| `npx tsc --noEmit` | limpio |
| `npm test` (vitest) | **1055/1055** (109 ficheros) |
| `python -m pytest -q` (backend) | **3157/3157** |
| `python -m ruff check backend launcher` (alcance del proyecto) | limpio |
| `python scripts/check_i18n_coverage.py --strict` | **1797** cadenas, 0 huérfanas / 0 usadas sin definir / 0 duplicadas (80 prefijos dinámicos) |
| `node frontend/scripts/contrast_audit.mjs --strict` | **480 pares + 6 guardas / 0 bloqueantes** (`audit: V3.86.0-contraste-wcag`) |
| `npm run build` | correcto |
| `python scripts/validation_gate.py auto --require-dist` | **10/10** (8 gates) |
| `npx playwright test` (barrido completo, 26 ficheros) | **116 passed · 0 failed · 34 skipped** (150 en total) |
| `python scripts/check_release_consistency.py` | OK en los **6 orígenes** (`3.86.0`) |

---

## 8. Honestidad

1. **El recordatorio no llega al mazo automático.** Vive en la ficha manual y el mazo automático es
   una vista del léxico: no se disimula con un campo espejo.
2. **La corrección de `lima` es perezosa.** El bump invalida; la regeneración ocurre al consultar.
3. **`deck_id` sigue existiendo, deprecado y con un solo escritor.** Es deuda declarada, no un
   olvido; retirarla exige una ventana de reconstrucción de tabla.
4. **No hay transacción entre léxico y ficha.** Siguen siendo dos escrituras con estado parcial
   declarado y reintento (decisión de V3.84.1, que se mantiene).
5. **La fase 2 no está**: nada de elegir mazos al estudiar, dirección ES↔EN, respuesta escrita ni
   ayudas de sílabas.
6. **Los nombres propios se pueden elegir**, pero solo de forma **explícita**: aparecen marcados y
   al final, y el defecto es siempre un nombre común si existe.
7. **Los 8 gates humanos siguen `pending`** y `validation-evidence.json` **no existe**.
8. **`python -m ruff check .` desde la RAÍZ del repositorio sigue reportando 1 hallazgo
   preexistente y ajeno**: `scripts/purge_virtual_testers.py:198` (`DTZ005`, `datetime.now()` sin
   zona horaria). El fichero es idéntico al del tag `v3.85.1`, y el alcance de ruff que declara el
   proyecto (`backend` y `launcher`, cada uno con su `pyproject.toml`) pasa **limpio**. Se declara
   en vez de arreglarse en silencio: no pertenece al alcance de esta release.
9. **`v3.85.1` no llegó a etiquetarse nunca, y eso se declara en vez de taparse.** El trabajo
   de esa versión (la sesión de repaso desatascada, el panel APRENDER con su CTA, la
   accesibilidad, el sello del contraste) se redactó y se verificó, pero se quedó **en el árbol
   de trabajo**: `git rev-parse v3.85.1` falla y **un tag publicado no se recrea**. El `HEAD`
   público seguía en `v3.85.0`, así que este tag **`v3.86.0` absorbe ambos deltas** y el rango
   `v3.85.0..v3.86.0` contiene **un solo commit de release**. `release-notes-v3.85.1.md` lleva
   ahora una errata en cabecera y el punto de entrada externo lo declara (§6). Consecuencia
   honesta: **no se puede auditar `v3.85.1` por separado** —no existe—, solo dentro de
   `v3.86.0`.

---

## Para auditar esta release

- **Ancla:** el tag **`v3.86.0`**. **`v3.85.1` no existe como tag**: su contenido va incluido
  aquí (ver el punto (ix) de §8 «Honestidad» y `release-notes-v3.85.1.md`).
- **Alcance backend:** `backend/repositories/db.py` (migración), `repositories/dictionary.py`,
  `repositories/flashcards.py`, `repositories/collections.py`, `domain/vocabulary.py`,
  `domain/flashcards.py`, `domain/retention.py`, `services/dictionary_content.py`,
  `services/dictionary_reverse.py`, `routers/vocabulary.py`, `schemas/vocabulary.py`,
  `config.py` (solo `VERSION`).
- **Alcance frontend:** `features/vocabulary/DictionaryLookup.tsx`, `FlashcardsScreen.tsx`,
  `StudySession.tsx`, `ReviewToday.tsx`, `wordDrill.tsx`, `features/routes/QuizRoutePage.tsx`,
  `features/vocabulary/VocabularyRoutesPractice.tsx`, `api/{client,vocabulary,normalize}.ts`,
  `types/api.ts`, `utils/i18n.ts`, `utils/studyFocus.ts` (**nuevo**),
  `scripts/contrast_audit.mjs`, más sus pruebas y las specs visuales.
  Los cinco últimos ficheros nombrados (`ReviewToday.tsx`, `wordDrill.tsx`,
  `contrast_audit.mjs` y sus pruebas) son el delta **absorbido** de `v3.85.1`.
- **Lo que NO toca:** `DECISION_POLICY_VERSION`, `CURRICULUM_VERSION` (sigue `1.3.1`),
  `LISTENING_BANK_VERSION`, las evaluaciones, el número o la definición de los gates, y la
  **consolidación léxico ↔ ficha manual** (sigue aparcada).
- **Punto de entrada al detalle:** `docs/audit/PARKED.md §V3.86.0`, `docs/RELEVO.md` y el plan
  `diccionario_polisemico_y_mazos` (fase 2 documentada al final).
- **Documentación absorbida, declarada:** este tag incorpora también
  `docs/audit/AY-AUDITORIA-TOTAL-V385.md` —el informe de la auditoría externa `AY`, que era su
  deliverable y seguía **sin commitear**— y `release-notes-v3.85.1.md`. **Higiene:** `.gitignore`
  gana `.ruff_cache/` (esa caché aparecía como no rastreada y podía colarse en un `git add -A`).
