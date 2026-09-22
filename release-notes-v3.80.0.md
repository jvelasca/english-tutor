# Release notes — English Tutor v3.80.0

**Fecha:** 2026-09-22 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.79.0 → 3.80.0`

**CON migración de BD aditiva** —una columna, `vocabulary.translation TEXT NOT
NULL DEFAULT ''`, con el `ALTER TABLE` idempotente que ya usaba el proyecto—, así
que **una BD de V3.79.0 se abre sin que nadie pierda nada**: las filas viejas
quedan en `''`, que es la lectura honesta de «no consta» y deja mandar al pack y a
la caché. **SIN bump de `GENERATOR_VERSION` ni `DECISION_POLICY_VERSION`, SIN
tocar el currículum (`CURRICULUM_VERSION` sigue `1.3.1`), SIN tocar las
evaluaciones y SIN tocar `LISTENING_BANK_VERSION`.** No añade ni retira un gate:
**G1–G7 siguen `pending`** y el árbol que se certifica sigue siendo el de
`v3.75.8`.

Es la segunda mitad del trabajo que abrió V3.78.0. Aquella release construyó la
superficie de Flashcards (mazos, tarjetas, FSRS, una sola sesión de estudio) y
**el alumno la probó y no funcionaba como una app de tarjetas**: al dar a
«Mostrar respuesta» la cara B decía que aún no estaba en caché, en Mazos creaba
un mazo y no había forma de meterle palabras, y no había mazos con los que
empezar. Ninguna de las tres cosas era un fallo de pintura.

---

## 1. Qué publica

### (A) La cara B deja de ser un callejón sin salida

**El síntoma exacto: «Mostrar respuesta» no mostraba respuesta.** Y no era un
fallo de pintado, era un dato que no existía:

```
vocabulary (léxico del alumno): 139 de 145 cartas SIN traducción
vocab_collection_items (packs): 75 pares curados
dictionary_entries (caché LLM): 9 filas (se puebla al consultar)
```

`card_face` miraba **solo los dos últimos**, y `vocabulary` **no tenía columna
donde guardar una traducción**. Peor: el dato ya estaba entrando en la app y se
estaba tirando —`add_item`/`add_bulk` reciben `translation` desde V3.77.0 y lo
usaban solo para el catálogo del pack, no para la fila del alumno—.

El arreglo tiene cuatro piezas, y la primera es la que hace que el resto importe:

| Pieza | Por qué |
| --- | --- |
| `vocabulary.translation` (columna aditiva) | El sitio donde vive lo que escribió el alumno. Sin él, **cualquier** corrección sería efímera |
| La precedencia pasa a estar **declarada** en `card_face` | Antes no había nada que pudiera mandar; ahora el orden es una decisión escrita: **lo que escribió el alumno** → catálogo del pack (autoría curada) → caché del diccionario (generada a máquina) |
| `PATCH /api/vocabulary/items` (`{word, translation}`) | Corregir el reverso sin inventar un segundo camino de escritura del léxico: escribe **solo** la fila del usuario de la sesión, acota a 500 caracteres y es idempotente |
| `seed_study_items` guarda la traducción del pack al inscribirse | Efecto buscado, no colateral: **añadir un pack deja sus palabras ya con reverso**, porque el pack es contenido curado y su autoría es mejor que la generada |

Y si no hay ninguna de las tres fuentes, `card_face` devuelve **vacío a
propósito**: una tarjeta sin reverso es un dato («no consta»), no un error que
haya que disimular con una traducción de relleno. Por eso la UI **ofrece**
resolverlo en vez de dar por hecho que siempre hay algo que enseñar.

`user_id` deja de ser opcional en `card_face` y se declara: la precedencia depende
de un dato **por alumno**, así que una firma que lo omitiera mentiría sobre lo que
hace. Los tres llamantes lo tenían a mano.

### (B) La sesión de estudio rellena el reverso al voltear, y se puede corregir

En `StudySession`:

- **Al voltear una tarjeta sin reverso se pide la traducción** con el cliente que
  ya existía (`lookupDictionaryWord`: caché global + generación del modelo local
  con su timeout), y se pinta con un «Generando el reverso con el modelo local…»
  honesto. A partir de ahí la caché la sirve gratis para siempre.
- **Si el modelo local no está, la sesión no se bloquea:** se dice qué pasa y se
  puede **calificar igual** (la tarjeta se programa; el reverso es información,
  no el acto de estudiar). Ese era el fallo de fondo del «aún no está en caché»:
  bloqueaba el estudio por un dato accesorio.
- **Un lápiz sobre el reverso revelado** abre un campo para escribirlo o
  corregirlo; se guarda con el PATCH y **pasa a mandar** sobre la generada.
- **El lápiz solo aparece en tarjetas del léxico.** Una tarjeta manual ya tiene su
  reverso editable, y su sitio es Tarjetas: ofrecerlo aquí sería un segundo
  editor del mismo campo.
- `flashcards.study.noFace` **deja de ser el estado normal**: solo aparece si ni
  pidiéndolo al modelo ni escribiéndolo hay reverso.

### (C) El mazo es UNA selección, no una por pestaña

**El síntoma exacto: «creo un mazo nuevo y no sé cómo añadir palabras».**

`FlashcardsScreen` guardaba `deckId` para Estudiar/Estadísticas, pero `CardsTab`
tenía **su propio** estado y arrancaba en `manual[0]` —el primero por orden
alfabético, no el que el alumno acababa de crear—. El backend servía y calificaba
mazos manuales perfectamente: **faltaba el cableado**.

Ahora la selección se sube a la pantalla (el patrón de Anki: el mazo es global, no
un estado por pestaña) y hay camino explícito:

- `deckId` vive en `FlashcardsScreen` y se pasa a **Estudiar**, **Tarjetas** y
  **Estadísticas**. `CardsTab` deja de tener estado propio y de arrancar en
  `manual[0]`.
- **Crear un mazo** lo selecciona y salta a Tarjetas con el campo del anverso
  enfocado, más una línea que dice qué hacer ahora. Es la respuesta directa al
  «no sé cómo añadir palabras».
- **«Añadir tarjetas»** aparece en cada fila de mazo manual, junto a Estudiar,
  Límites y Borrar: dos acciones distintas que se necesitan las dos.
- **Estudiar un mazo vacío** no abre una sesión de 0 tarjetas: lo dice y ofrece
  añadir palabras. Y si el **mazo automático** está vacío (diccionario vacío), no
  ofrece un atajo inerte: manda a Personal, que es donde se llena.

### (D) Pegar una lista de tarjetas, con el MISMO parser que el léxico

- `POST /api/vocabulary/decks/{deck_id}/cards/bulk` (`{text}`): una tarjeta por
  línea, `anverso,reverso` (coma **o** tabulador), `#` comenta y las líneas vacías
  se ignoran.
- El parseo **se comparte** con el que ya usaba el léxico: `_parse_bulk_lines` se
  promueve a función pública (`parse_bulk_lines` en `domain/retention.py`) y la
  usan los dos. **El alumno pega lo mismo en las dos pantallas**, así que con dos
  parsers la sintaxis acabaría divergiendo y le obligaría a recordar dos formatos
  para lo que él ve como una sola acción. Lo que **no** se comparte es la
  validación, y a propósito: el léxico normaliza palabras (minúsculas, sin
  dígitos, 80 caracteres) y una tarjeta admite una frase entera («break a leg»).
- La escritura va en **una transacción** (`create_cards`), no en un bucle: pegar
  40 tarjetas con `create_card` abriría 40 conexiones, el mismo defecto que
  V3.77.2 cerró para el léxico.
- Deduplica por anverso normalizado y topa el lote. **El recuento que se enseña es
  el que entró de verdad**, no el de las líneas pegadas: con duplicados o líneas
  inválidas no coinciden, y prometer el segundo sería mentir.
- UI: textarea + «Añadir todas» en la pestaña Tarjetas.

### (E) Mazos listos: los packs que ya existen

En Mazos, sección **«Mazos listos»** con los `theme_pack` globales que ya siembra
`repositories/collections.py` (comida, trabajo, viajes…), reutilizando
`GET /api/vocabulary/collections` y `POST .../enroll` — **cero backend nuevo**:

- **Sin activar → «Añadir»**: materializa sus palabras en el léxico **con su carta
  FSRS** y se dice qué pasará antes de pulsarlo.
- **Activado → «Estudiar»**: abre Estudiar con el **mazo automático filtrado por
  ese pack** (`collection_id`, que la cola ya soportaba y `StudyTab` ya pintaba).
  No se copia contenido: son las mismas palabras vistas por su etiqueta.
- Si el catálogo viniera vacío, **el bloque no se pinta**: no se promete lo que no
  existe.
- **Declarado: el mismo pack sigue listado en el bloque «Añadir» de PERSONAL.** No
  es duplicación accidental —uno es «añadir a mi diccionario» y el otro «empezar a
  estudiar»— y consolidarlo queda **aparcado** en `docs/audit/PARKED.md`, no
  olvidado.

---

## 2. La comprobación que importa: que los candados muerdan

Los cinco candados se comprobaron **revirtiendo el código**, no razonando sobre
él. Los cinco mordieron, y después se restauró y se comprobó que la suite queda
verde.

**(A) La precedencia** — devuelto `card_face` a «solo pack y caché»:

```
FAILED tests/test_back_face_v380.py::test_own_translation_beats_pack_and_cache
FAILED tests/test_back_face_v380.py::test_card_face_is_per_user
FAILED tests/test_back_face_v380.py::test_corrected_translation_reaches_the_auto_deck_queue
FAILED tests/test_back_face_v380.py::test_patch_normalizes_case_and_spaces
E  AssertionError: assert '' == 'ancla'
4 failed, 5 passed
```

**(B) El parser compartido** — quitado el tabulador de `parse_bulk_lines` (la
divergencia más probable entre dos parsers):

```
FAILED tests/test_flashcards_v378.py::test_parser_is_shared_between_lexicon_and_cards
FAILED tests/test_flashcards_v378.py::test_bulk_cards_accept_phrases_the_lexicon_would_reject
FAILED tests/test_flashcards_v378.py::test_bulk_cards_dedupes_and_reports_only_what_entered
FAILED tests/test_flashcards_v378.py::test_bulk_cards_are_capped_and_leave_a_schedulable_state
FAILED tests/test_flashcards_v378.py::test_bulk_cards_with_nothing_usable_is_a_no_op
FAILED tests/test_flashcards_v378.py::test_auto_deck_queue_serves_lexicon_and_can_filter_by_collection
6 failed, 60 passed
```

**(C) El relleno del reverso** — quitado `hydrate` del volteo:

```
❯ src/features/vocabulary/StudySession.test.tsx (11 tests | 3 failed)
      Tests  3 failed | 8 passed (11)
```

**(D) El mazo creado es el que se edita** — quitado el `setDeckId` de
`openCardsFor`:

```
FAIL FlashcardsScreen > crear un mazo lo selecciona y abre Tarjetas con el anverso enfocado
```

**(E) Un mazo listo se estudia filtrado** — pasado `null` en vez del
`collection_id`:

```
FAIL FlashcardsScreen > un mazo listo sin activar se añade y ya activo se estudia filtrado
```

---

## 3. Verificación

| Instrumento | Resultado |
| --- | --- |
| `pytest` (backend) | **3008/3008** |
| `ruff check .` (backend) | limpio |
| `tsc --noEmit` | limpio |
| `vitest run` | **965/965** (108 ficheros) |
| `npm run build` | correcto (`package.json` en `3.80.0`) |
| i18n `--strict` | **1706** cadenas · **0 huérfanas / 0 usadas sin definir / 0 duplicadas** |
| contraste `--strict` | 480 pares (+6 guardas) · **0 bloqueantes** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.80.0`) |
| `validation_gate.py auto` | **10/10** |
| `pytest` (launcher) | **205/205** + `ruff` limpio |
| `Playwright` (visual) | `vocabularyRoutesReview`, `drillProvenance` y `profileDialog`: **9 pasan / 6 se saltan** (las que se declaran solo-desktop) |

Tests nuevos: `backend/tests/test_back_face_v380.py` (**9**),
`backend/tests/test_flashcards_v378.py` (**7**), `FlashcardsScreen.test.tsx`
(**8**), `StudySession.test.tsx` (**7**), `PersonalDictionary.test.tsx` (**1**) y
`api/vocabulary.test.ts` (**2**). Los recuentos suben exactamente por ellos y por
una prueba reformada en sitio (`dice que no hay cara…` pasa a
`flashcards.study.noFace` como estado raro y no como estado normal): backend
2992 → **3008**; frontend 948 → **965**.

---

## 4. Honestidad

1. **La migración es aditiva y NO rellena nada.** Las 139 cartas sin reverso
   siguen sin él después de actualizar: lo que cambia es que ahora hay **una vía
   para arreglarlo** (generar al voltear, escribir a mano) y una fuente que antes
   se tiraba (la traducción del pack, que ahora sí se guarda al inscribirse). Una
   actualización **no** convierte la app en una que tiene todos los reversos.
2. **El relleno depende del modelo local.** Si el modelo no está o tarda, la
   tarjeta se queda sin reverso y la sesión sigue —a propósito—. Es una mejora
   **condicional**, no una garantía, y se dice porque el alumno ya se ha comido
   una vez un mensaje que prometía lo que no daba.
3. **La generación no se guarda en `vocabulary`.** El reverso generado por el
   modelo vive en la **caché del diccionario** (`dictionary_entries`) y se sirve
   de ahí; solo lo que **escribe el alumno** entra en su fila del léxico. Es
   deliberado —no se le atribuye al alumno un texto que no ha escrito— pero
   significa que el reverso generado no es «suyo» y no se edita desde PERSONAL.
4. **La precedencia tiene una consecuencia que conviene declarar:** si el alumno
   corrige una palabra que venía de un pack, su corrección **manda** sobre el
   pack, así que su copia de esa palabra y el pack dicen cosas distintas. Es lo
   que pidió («que mi versión gane») y es coherente, pero no se propaga al
   catálogo compartido: se corrige **su** tarjeta, no el pack.
5. **`card_face` pasa a ser una llamada por alumno y por palabra.** Es una
   consulta más por tarjeta servida, y se aceptó a cambio de que la corrección
   llegue de verdad. La cola sigue resolviendo la cara B **solo para los ítems que
   entran en la sesión** (no para los cientos del léxico), que era la optimización
   que ya existía y no se toca.
6. **El lápiz edita la traducción, no la definición.** La definición del modelo
   se conserva como apoyo y no es editable; si algún día se quiere corregir, es
   otra columna y otra decisión.
7. **Pegar una lista de tarjetas no valida el contenido, solo la forma.** Un
   anverso de 400 caracteres y un reverso de 2000, sin comprobar que el reverso
   sea correcto ni que el anverso sea una pregunta: sigue siendo un bloc de notas
   con memoria, y se presenta como tal.
8. **Los mazos listos se apoyan en el mazo automático, y eso tiene precio.** Se
   estudian con los **límites del mazo automático** (10 nuevas / 50 repasos), no
   con límites propios del pack: no hay fila de mazo que los guarde. Y el mismo
   pack aparece en dos sitios (PERSONAL para añadir, Mazos para estudiar), que es
   una duplicación **declarada** y no un olvido.
9. **Lo que NO se hace, y estaba en la lista de las apps top:** copiar un pack a
   un mazo propio editable, plantillas, cloze, import/export `.apkg`, mazos
   filtrados, suspender/enterrar, leech y opciones avanzadas por mazo. Todo
   **aparcado y declarado** en `docs/audit/PARKED.md`.
10. **La consulta del diccionario sigue sin alimentar el léxico** —invariante D3
    de V3.77.0, **no** tocada en esta release—: buscar «however» no lo añade a
    PERSONAL. Con PERSONAL presentado como «las palabras de toda la app», esa
    ausencia se lee como hueco, y sigue siendo un hueco **declarado**.
11. **El candado del guardia de `data/` es sensible al entorno, y se le vio fallar
    en esta release.** `test_el_instrumento_no_escribe_en_data_ni_en_curriculum`
    compara **mtime de todo `backend/data`**, incluido `tutor.db`: en la primera
    pasada de la suite falló porque **la app estaba abierta y escribiendo en su
    BD** en ese momento (comprobado: launcher + `uvicorn` vivos en `:8000`, y
    `tutor.db` con mtime de ese instante). En la segunda pasada, con la app
    ociosa, **3008/3008**. No es de esta release y no se ha tocado: se declara
    porque un fallo que depende de que el alumno tenga la app abierta no debe
    confundirse con una regresión.
12. **El barrido visual completo no se corrió en local** (la autoridad es el CI):
    se corrieron las specs que tocan el diccionario y el diálogo, y las 6 que se
    saltan son las que se declaran solo-desktop. Queda además flakiness local
    preexistente cuando el backend está apagado (`socket hang up` en el proxy de
    Vite), ya declarada en V3.79.0 y no de esta release.
13. **Los 7 gates siguen en `pending`** y el árbol que se certifica sigue siendo el
    de `v3.75.8`. Esta release no toca gates.
