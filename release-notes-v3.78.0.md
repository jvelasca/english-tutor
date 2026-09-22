# Release notes — English Tutor v3.78.0

**Fecha:** 2026-09-22 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.77.2 → 3.78.0`

**CON migración de BD aditiva** (tres tablas nuevas: `flashcard_decks`,
`flashcard_cards` y `flashcard_reviews`, `CREATE TABLE IF NOT EXISTS` + sus dos
índices), así que **una BD de V3.77.2 se actualiza sin que nadie pierda nada**.
**SIN bump de `GENERATOR_VERSION` ni `DECISION_POLICY_VERSION`, SIN tocar el
currículum (`CURRICULUM_VERSION` sigue `1.3.1`), SIN tocar las evaluaciones y SIN
tocar `LISTENING_BANK_VERSION`.** No añade ni retira un gate: **G1–G7 siguen
`pending`** y el árbol que se certifica sigue siendo el de `v3.75.8`.

El diccionario deja de tener dos pestañas y pasa a tener **tres modos**:
**Consultar · Personal · Flashcards**. El cambio de fondo no es una pestaña más,
es un reparto de responsabilidades: **Personal pasa a ser posesión y gestión** y
**Flashcards se convierte en la única superficie de estudio**.

---

## 1. Qué publica

### (A) Tres modos, y el defecto cambia de sitio

`DictionaryView` pasa de `"personal" | "lookup"` a
`"lookup" | "personal" | "flashcards"`, y `DEFAULT_DICTIONARY_VIEW` cambia a
`"lookup"`. El orden de las pestañas es el orden en que se usan —
**Consultar · Personal · Flashcards** — y el modo que se abre primero es el que
responde a la pregunta con la que se entra a un diccionario («¿qué significa esta
palabra?»), no el que exige tener léxico propio.

Es un cambio de defecto **visible**, y se declara: quien tuviera `"personal"`
persistido **lo conserva** (un valor guardado de una versión anterior sigue siendo
válido y manda sobre el defecto), así que nadie pierde su pestaña al actualizar;
lo que cambia es lo que ve quien entra por primera vez. La doble persistencia no
se toca: `localStorage` para el arranque sin parpadeo y `settings` por usuario
(`dictionary_view`) para que la preferencia viaje con el perfil.

**El panel incrustado sigue siendo de dos modos y ahora es una frontera
explícita.** El diccionario que vive dentro de la práctica de rutas
(`QuizRoutePage`) no puede hospedar una sesión de estudio: tiene su propio
recorrido, sus límites del día y su resumen. En lugar de repetir esa restricción
como convención en cada consumidor, `toPanelView()` la declara en un sitio
(`"flashcards" → "personal"`) y `PANEL_DICTIONARY_VIEWS` enumera los dos modos que
el panel sí sabe mostrar. Es lo que evita que el panel pueda dejar **persistido**
un modo que no sabe pintar en el ajuste que comparte con la pantalla dedicada.

### (B) PERSONAL es el inventario

Deja de estudiar y pasa a responder «¿qué tengo y cómo lo tengo?»:

- **Buscador** sobre el léxico y **filtro por estado**
  (`mastered` / `known` / `learning` / `weak`, la clasificación que el servidor ya
  calculaba y que hasta ahora no se podía usar para nada).
- **Procedencia** por fila, desde `vocabulary.source`
  (`curriculum` / `user` / `imported`): el dato se guardaba desde V3.77.0 y no se
  mostraba, así que «de dónde salió esta palabra» era invisible.
- **Fuerza de memoria** por fila: estado FSRS, `due_at`, estabilidad,
  recuperabilidad y «próxima en N d». Es el estado del **scheduler**
  (`fsrs_cards`), y se muestra junto al `recall` derivado de la evidencia —que ya
  venía— porque **responden a preguntas distintas**: `recall` dice lo que la app
  infiere de lo que el alumno hizo; la memoria dice cuándo toca repasarla.
  Mezclarlas fue justo lo que M4 tuvo que separar, así que el enriquecimiento
  vive en `domain/vocabulary.py` (fuente: el scheduler) y no en
  `services/lexicon.py` (fuente: la curva de olvido de la tabla `vocabulary`).
  Se calcula **puro** sobre una sola lectura de cartas: enriquecer 500 palabras no
  añade ni una conexión más.
- La sección «Practicar hoy» **pierde la sesión de repaso incrustada** y gana una
  tarjeta de entrada: «N tarjetas pendientes hoy» + botón **Estudiar** que cambia
  a Flashcards. Si el contenedor no ofrece el salto (el diccionario incrustado),
  el botón **no se pinta** y el texto explica dónde se estudia, en lugar de
  ofrecer un botón que no llevaría a ninguna parte.
- **`ReviewQueueSection` se queda donde está**, y se declara para que no parezca
  un olvido: la cola de competencia del drill es superficie de **producción**, no
  de calificación de tarjetas. Practicar una palabra usándola no es repasarla.

### (C) Una sola superficie de estudio

`RetentionSession` se generaliza a **`StudySession`**: deja de pedir la cola por
su cuenta y **recibe los ítems** y un `onGrade`, así que sirve para el mazo
automático y para uno manual sin saber cuál es. El contenedor decide el endpoint y
el mazo.

- Desde **Personal**, el botón «Estudiar» salta a Flashcards con el mazo
  automático.
- Desde **«Mis listas» y packs**, la acción salta a Flashcards con
  **esa colección filtrada** y la sesión **arranca sola** (el alumno ya pidió
  estudiar al pulsar). El estado `reviewing` y la sesión acotada de
  `AddVocabSection` desaparecen; en su lugar hay un `onStudy(collectionId, label)`
  que **no sabe** cómo se navega —se lo dice el dueño de la navegación—.
- El **foco** (qué mazo abrir y con qué etiqueta) vive en `DictionaryScreen`, no
  en la vista: es un encargo de **un solo salto**, no una preferencia, así que no
  se persiste y muere al salir. Lleva un `nonce` para que un segundo clic sobre la
  misma lista vuelva a abrir la sesión en vez de ser un no-op.
- Se conserva el arreglo de V3.77.2 y su candado: el resumen («N tarjetas
  revisadas») **tiene que seguir siendo alcanzable**, y además ofrece
  **actualizar** cuando el contenedor sabe recargar la cola (si no lo sabe, el
  botón no existe: un botón que no puede hacer lo que promete es peor que no
  tenerlo).

### (D) Backend: mazos y tarjetas

Tres tablas nuevas, sin tocar ninguna existente:

- `flashcard_decks (id, user_id, name, new_per_day, review_per_day, created_at,
  updated_at)` con `UNIQUE (user_id, name)`.
- `flashcard_cards (id, user_id, deck_id, front, back, created_at, updated_at)`.
- `flashcard_reviews (id, user_id, deck_id, card_type, card_id, grade, was_new,
  created_at)`: **ledger append-only** de cada calificación.

**El mazo automático es VIRTUAL** (`id = 0`, slug `auto`, nombre «My dictionary»):
no es una fila, se sintetiza a partir del léxico y no se puede borrar. Al no ser
una fila no hay que sembrarlo, no puede quedar desincronizado del léxico y no
existe el caso raro de «el alumno borró el mazo del sistema». Sus cartas son las
`lexicon` —todo lo que la app ha registrado: currículum, chat, speaking, listas y
packs—, que se **siembran de forma perezosa** (`sync_fsrs_cards`) antes de leerlas:
depender de que el alumno abra el panel de REVISAR para que su propio léxico
aparezca en el mazo automático sería un mazo que no enseña lo que promete.

`repositories/flashcards.py` (CRUD y contadores, sin lógica de negocio, al estilo
de `collections.py`) y `domain/flashcards.py` (mazos con sus recuentos, cola
unificada y despacho de grade) son los dos módulos nuevos.

### (E) FSRS: un tipo de carta nuevo, sin un segundo planificador

`TARGET_TYPES` gana `"flashcard"` y se añade `why_for_flashcard()` («flashcard-manual»:
no hay señal del alumno que explique por qué existe la carta —la escribió él—, y
la razón lo dice). **No se escribe un segundo planificador**: las tarjetas a mano
se programan con el mismo `fsrs.schedule` y se explican con el mismo
`fsrs.explain`, con los cuatro grados de siempre.

Y **eso no era gratis, así que se cerró en el mismo commit.** El panel
autograduable (`get_fsrs_due`, `get_fsrs_summary`, `review_fsrs_card`) solo
excluía `objective`. Sin excluir también `flashcard`, **las tarjetas manuales se
colaban en el panel de REVISAR** y el alumno las habría calificado en dos sitios a
la vez: exactamente el doble escritor que M4 cerró. Ahora la exclusión se declara
**una sola vez** (`_PANEL_EXCLUDED_TARGET_TYPES`) y la usan los tres sitios, con
el trato idéntico al de `objective`: fuera de la cola y de `due_count`, y `by_type`
conservando el total como diagnóstico.

**Los límites del día salen del ledger, no del scheduler.** `flashcard_reviews`
cuenta **cada calificación**, no cada tarjeta distinta, porque Anki mide repasos:
una tarjeta fallada y repetida tres veces son tres repasos. Y `was_new` marca la
primera vez, que es lo que aplica el tope de nuevas. Contar «cartas distintas con
`last_review_at` de hoy» no distingue nuevas de repaso ni cuenta repeticiones, que
son justo las dos cosas que hacen falta para que el número sea el que el alumno ve
en Anki y el que la sesión respeta.

Y de ahí sale la definición de **nueva**: «nunca calificada en esta superficie»,
leída del ledger, **no** el `reps` del scheduler. La diferencia es real: la
siembra de retención marca `reps = 1` en las cartas que deriva de la evidencia de
las lecciones, así que una palabra recién añadida puede llegar con `reps = 1` y
una `due_at` de dentro de diez horas —clasificada por `reps` desaparecería del
mazo en vez de ofrecerse como nueva—.

El evento del ledger pedagógico también se clasifica: `flashcard:<id>:<grade>` →
**`informative`**, igual que `retention:<word>:<grade>`. Sin esa rama caería a
`telemetry`, que no es incorrecto pero describe mal lo que pasó. **Nada de esto
acredita mastery**: no toca `learning_evidence`, ni Assessment, ni CEFR.

Endpoints nuevos (todos con sesión, todos por usuario):

| Método y ruta | Qué hace |
| --- | --- |
| `GET /api/vocabulary/decks` | Auto + manuales, con `due`/`new` de **hoy** y total de tarjetas |
| `POST/PATCH/DELETE /api/vocabulary/decks[/{id}]` | CRUD; el automático **rechaza** escritura |
| `GET /api/vocabulary/decks/{id}/queue` | Cola unificada (`limit` 1–100) |
| `POST /api/vocabulary/decks/{id}/review` | Grade 1–4 → reprograma y anota en el ledger |
| `GET/POST/PATCH/DELETE /api/vocabulary/decks/{id}/cards[/{card_id}]` | Navegador y CRUD |
| `GET /api/vocabulary/decks/{id}/stats` | Hoy, 30 días, acierto, 14 días y previsión a 7 |

Dos detalles que se decidieron y conviene no deshacer:

- **Borrar arrastra.** Borrar una tarjeta borra su carta FSRS, y borrar un mazo
  borra las cartas FSRS de sus tarjetas: si no, quedarían cartas de repaso de
  tarjetas que ya no existen. El borrado de la tarjeta devuelve la fila antes de
  borrarla para saber qué carta limpiar.
- **El endpoint viejo no se convierte en un segundo escritor.**
  `POST /api/vocabulary/retention/review` (V3.77.0) **delega** en el mismo
  servicio con el mazo automático, así que una palabra calificada por ahí también
  cuenta en el ledger. Si siguiera agendando por su cuenta, una palabra calificada
  por ese camino contaría como nueva para siempre y su revisión no aparecería en
  ninguna estadística. El léxico **no** se reagenda en el módulo nuevo: se delega
  en `retention_review`, que ya es el dueño de esa carta y de su evento.

### (F) La UI de Flashcards

`FlashcardsScreen.tsx`, con cuatro subpestañas en el orden en que se usan:

- **Estudiar**: cola unificada, frente/dorso, los 4 grados, contador de la sesión,
  límites del día respetados y **resumen final alcanzable con acción de
  actualizar**. Orden: primero los repasos vencidos y después las nuevas —el orden
  clásico de Anki, y además el que respeta el dinero del alumno: lo que ya se sabe
  y se está olvidando va antes que lo que nunca ha visto—.
- **Mazos**: el automático («todo mi diccionario», con sus contadores y **sin
  renombrar ni borrar**) y los manuales, con `due` + nuevas, crear, editar
  (`new_per_day`/`review_per_day`, por defecto 10 y 50) y borrar **con
  confirmación** que dice cuántas tarjetas se lleva por delante.
- **Tarjetas**: navegador con **filtro por texto**, **filtro por estado**,
  **orden** (recientes / anverso / vencimiento) y CRUD. Cada fila muestra su
  fuerza de memoria, porque sin ella el navegador no distingue una tarjeta recién
  creada de una repasada cinco veces. El orden por vencimiento manda al final las
  tarjetas **sin carta programada**: no es «vence ya», es «aún no está en el
  scheduler».
- **Estadísticas**: repasos de hoy, total de 30 días, tasa de acierto
  (`good`+`easy` frente a `again`), histograma de los últimos 14 días y previsión
  de los próximos 7.

**La previsión excluye las nuevas, a propósito**: su `due_at` no anticipa cuándo
las estudiará el alumno —eso lo decide su plan— y contarlas prometería un día que
no depende de ellas. Se calcula con el `due_at` que el scheduler ya guarda y no
con una proyección de estabilidad: es lo que el alumno va a ver de verdad.

### (G) Contratos en la frontera

`normalize.ts` gana `normalizeDeckList`, `normalizeStudyQueue`,
`normalizeFlashcardList` y `normalizeFlashcardStats`, y los clientes viven en
`api/vocabulary.ts`. Es la regla que dejó V3.77.2 y se cumple: **el estado de React
no recibe una forma sin comprobar.** El tipo del frontend espeja el contrato del
backend, incluido el detalle de que las dos series (`by_day`, `forecast`) comparten
una sola forma con `day`/`total`/`good`/`count` y ceros por defecto, que es lo que
el backend emite.

---

## 2. La comprobación que importa: que los candados muerdan

Los tres candados que el plan exigía se comprobaron **revirtiendo el código**, no
razonando sobre él. Los tres mordieron, y después se restauró y se volvió a
comprobar que la suite queda verde (16/16 backend, 5/5 del componente).

**(A) Que una tarjeta manual no se cuele en el panel FSRS.** Quitando
`"flashcard"` de `_PANEL_EXCLUDED_TARGET_TYPES`:

```
FAILED tests/test_flashcards_v378.py::test_manual_cards_do_not_leak_into_fsrs_panel
1 failed, 15 passed
```

**(B) Que la cola respete el tope de nuevas del día.** Haciendo que
`new_remaining` fuera un número grande:

```
FAILED tests/test_flashcards_v378.py::test_queue_respects_new_per_day
1 failed, 15 passed
```

**(C) Que el resumen final sea alcanzable.** Quitando el avance del índice en
`StudySession` (que es exactamente el fallo de V3.77.2):

```
❯ src/features/vocabulary/StudySession.test.tsx (5 tests | 3 failed)
 FAIL  al gradear la última tarjeta se ve el resumen, no una recarga silenciosa
 FAIL  solo ofrece «Refresh» cuando el contenedor sabe reiniciar la sesión
 FAIL  sale con «Back» desde el resumen y ofrece actualizar si el contenedor sabe reiniciar
```

---

## 3. Verificación

| Instrumento | Resultado |
| --- | --- |
| `pytest` (backend) | **2988/2988** |
| `ruff check .` (backend) | limpio |
| `scripts.transfer_validation` | `OK=True` |
| `tsc --noEmit` | limpio |
| `vitest run` | **939/939** (106 ficheros) |
| `npm run build` | correcto (`package.json` en `3.78.0`) |
| i18n `--strict` | 1679 cadenas · **0 huérfanas / 0 usadas sin definir / 0 duplicadas** |
| contraste `--strict` | 480 pares (+6 guardas) · **0 bloqueantes** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.78.0`) |
| `validation_gate.py auto` | **10/10** |
| `pytest` (launcher) | **205/205** + `ruff` limpio |
| `Playwright` (visual) | `drillProvenance` **2/2** y `vocabularyRoutesReview` **1/1** (desktop). El barrido completo **no** se corrió en local (§4.6) |

Tests nuevos: `backend/tests/test_flashcards_v378.py` (**16 casos**),
`frontend/src/features/vocabulary/FlashcardsScreen.test.tsx` (**9**),
`frontend/src/features/vocabulary/StudySession.test.tsx` (**5**) y
`frontend/src/utils/dictionaryView.test.ts` (**8**). Los recuentos suben
exactamente por los tests nuevos y por las reformas en sitio: backend
2972 → **2988** (+16), frontend 910 → **939** (+29 netos, con
`RetentionSession.test.tsx` retirado y `StudySession.test.tsx` en su lugar).

---

## 4. Honestidad

1. **El defecto del diccionario cambia, y eso se ve.** Quien entrase con la app
   recién instalada abría «Personal»; ahora abre «Consultar». Un valor
   **persistido** de una versión anterior sigue mandando, así que nadie pierde su
   pestaña; lo que cambia es el arranque limpio. Está fijado con un test en las
   dos direcciones precisamente porque es un cambio de comportamiento, no un
   detalle de pintura.
2. **La consulta del diccionario sigue sin alimentar el léxico, y ahora se nota
   más.** Es la invariante D3 declarada en V3.77.0 y esta release **no** la toca:
   buscar «however» no añade «however» a Personal. Con PERSONAL presentado como
   «las palabras aprendidas en toda la app», la ausencia de lo consultado se lee
   como un hueco; se declara como hueco explícito (aparcado, con su propia
   decisión) y no como efecto colateral.
3. **El mazo automático y los manuales NO son simétricos, y el automático es el
   peor parado.** No se puede renombrar, no se puede borrar, **no se le pueden
   poner límites propios** (usa 10 y 50) y **no admite tarjetas escritas a
   mano** —añadir a mano es lo que hacen las listas—. Es coherente con que sea una
   vista del léxico y no una fila, pero significa que quien quiera «estudiar solo
   estas 20 palabras con tope 20» no lo consigue desde aquí: la herramienta que
   existe para eso es una lista, y su filtro se aplica al mazo automático.
4. **`FSRS-lite` sigue sin ser FSRS, ahora también para las tarjetas a mano.** La
   V3.77.0 ya lo declaró y esta release lo hereda en vez de arreglarlo: los
   intervalos salen de la versión simplificada y declarada de
   `domain/retention.py`, **sin** los parámetros por alumno que FSRS completo
   ajusta con el historial. Una tarjeta escrita a mano no recibe un plan mejor que
   una palabra del currículum: recibe el mismo.
5. **Los límites del día son del ledger, y el ledger no distingue de dónde
   vino la calificación.** Una palabra del léxico calificada desde el endpoint
   viejo de retención cuenta como un repaso del mazo automático —eso es
   deliberado, es lo que evita dos contabilidades— pero significa que el número
   «repasos de hoy» incluye calificaciones que el alumno hizo en otra pantalla.
6. **El barrido visual completo no se ha corrido en local**, igual que en V3.77.2:
   la autoridad es el CI. Lo que sí se corrió son las **dos** specs que tocan el
   diccionario, y la de `drillProvenance` **tuvo que cambiar** —entra explícitamente
   a «Personal» antes de buscar la entrada al drill, porque el defecto ya no es esa
   pestaña—. Esa spec localiza la entrada con
   `li:has(button[aria-pressed]) button[aria-pressed]`; la fila del léxico
   **conserva** ese botón y esos dos tests pasan en desktop (la spec se salta
   tablet y móvil por diseño, `test.skip(width < 1024)`).
7. **La migración es aditiva y no migra datos, y eso tiene una consecuencia.**
   Nada que trasladar: las tres tablas nacen vacías y las palabras que ya existían
   **no tienen carta** hasta que alguien sincronice —lo que hace el propio mazo
   automático al abrirse—. Una palabra sin carta sale en Personal como «sin
   estudiar», que es la lectura honesta de «no consta»; no es un error y no se
   disimula con una fecha inventada.
8. **Los mazos manuales se quedan cortos a propósito.** Anclan el trabajo real —lo
   que el alumno quiere recordar y la app no podía saber— pero no hay plantillas
   ni campos propios, ni cloze, ni import/export (`.apkg`/CSV), ni mazos filtrados,
   ni suspender/enterrar, ni leech, ni opciones avanzadas por mazo (pasos de
   aprendizaje, orden de las nuevas). Todo eso queda **aparcado y declarado** en
   `docs/audit/PARKED.md`, no como deuda escondida.
9. **La tarjeta a mano guarda texto, no conocimiento.** Un anverso de 400
   caracteres y un reverso de 2000, sin validación de que el reverso sea correcto
   ni de que el anverso sea una pregunta: la app no comprueba lo que el alumno se
   escribe. Es un bloc de notas con memoria, y se presenta como tal.
10. **Nada de esto acredita mastery**, y es la misma decisión de V3.77.0: la
    calificación de una tarjeta programa el próximo repaso y escribe un evento
    **informativo**. Si contara como competencia, la matriz de destrezas subiría
    por recordar tarjetas.
11. **Una sesión está topada en 100 tarjetas** (`QUEUE_MAX` y `limit ≤ 100`). No
    es una medida pedagógica, es defensiva: una sesión no debe convertirse en un
    atracón, y el alumno siempre puede volver.
