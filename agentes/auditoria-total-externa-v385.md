# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.85.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el arco de DOS releases que va
> de `v3.84.0` a `v3.85.0`**: el **patch de robustez `v3.84.1`** —el alta del diccionario deja
> de decir «error» sobre una operación que ya estaba a medias— y la **minor `v3.85.0`** —el
> diccionario pasa a **dos pestañas** y «Repasar hoy» deja de ser una lista de estados para
> convertirse en una **acción**—. La revisión es **de solo lectura**: no se cambia código,
> datos, configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué AHORA.** Porque las dos releases comparten el mismo patrón
> y ninguna de las dos es «compila»: **las dos cambian lo que la UI dice de sí misma**.
> `v3.84.1` corrige una **mentira** (pintaba «No se pudo añadir la palabra» cuando el aprendizaje
> sí se había guardado) y `v3.85.0` sustituye una **lista de estados** por una **acción**
> («Repasar ahora (N)»), retirando de paso dos componentes enteros. Lo que hay que dictaminar no
> es si el botón aparece: es **(a)** si el estado parcial se declara donde importa y el reintento
> no puede duplicar la tarjeta, **(b)** si la sesión encadenada es de verdad una sesión —recorre
> la cola, no se atasca, no promete más de lo que sirve— o es un botón nuevo sobre la misma
> pantalla, y **(c)** si el recorte de superficies dejó alguna puerta sin sustituto.
>
> **Aviso de encuadre (léelo antes de puntuar).** El arco **no cambia el contrato de la API**,
> **no migra la BD** y **no añade endpoints**: eso invita a una auditoría blanda porque «no hay
> nada que romper». No la hagas. En `v3.85.0` **no hay una sola línea de lógica de backend** (el
> diff de `backend/` son dos ficheros: el bump de `VERSION` y un candado documental) y en
> `v3.84.1` el único cambio de backend de producto es el `detail` de un `400` que ya existía. El
> riesgo no está en el runtime: está en **afirmaciones de UI** que ningún test de backend puede
> desmentir, y en **un cambio visible de comportamiento que su propio tag no declara** (§6-D3).
>
> **Continuidad con los puntos de entrada vecinos — los cuatro siguen vivos.**
> `agentes/auditoria-total-externa-v382.md` cubre el eslabón `v3.81.2..v3.82.0` (**contrato +
> migración**) y **sigue esperando su informe `AV`** —es la mayor deuda de auditoría de la
> serie—; `agentes/auditoria-cierre-global-v383.md` cubre el cierre de la serie V3.83.x y espera
> su informe **`AW`**; `agentes/auditoria-total-externa-v384.md` cubre `v3.83.1..v3.84.0` y
> espera su informe **`AX`**. Este documento **no repite** ninguna de sus preguntas: las
> **hereda** y pregunta por el delta `v3.84.0..v3.85.0`.
>
> **Informe esperado:** `docs/audit/AY-AUDITORIA-TOTAL-V385.md`. Prefijo **`AY`** porque **es el
> primer prefijo libre**: `AA`–`AF` los ocupan los dossiers de V3.70, `AG`–`AM` la pausa
> pedagógica y psicometría, `AN` el arco de `v3.75.1`, `AO` la política psicométrica de V4.0, y
> **`AP` (`v3.75.7`), `AQ` (`v3.77.1`), `AR` (`v3.80.0`), `AS` (`v3.81.1`), `AT` (`v3.81.2`),
> `AU` (`v3.83.0`, dictaminado), `AV` (`v3.82.0`, pendiente), `AW` (cierre V3.83.x, pendiente) y
> `AX` (`v3.84.0`, pendiente) siguen reservados**. Ver la nota de prefijos en §8.
>
> **Estado del punto de entrada:** entregado 2026-09-26 en un **commit documental POSTERIOR a
> los dos tags**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md`). Las anclas siguen siendo `v3.84.1` y `v3.85.0`, y el
> producto **no se mueve** para entregar esto.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera**, y en particular las **dos notas nuevas** (`V3.85.0` y
   `V3.84.1`), en ese orden.
2. `release-notes-v3.85.0.md` — las notas **de la release mayor**. Su **§12 «Honestidad»**
   declara **siete** límites, y cada uno es una pregunta encubierta. Su §3 es la afirmación
   central que hay que intentar tumbar.
3. `release-notes-v3.84.1.md` — las notas **del patch**. Su **§7 «Honestidad»** declara **seis**
   límites; el §2 declara la política elegida (opción A frente a B).
4. `frontend/src/features/vocabulary/ReviewToday.tsx` — **el núcleo de `v3.85.0`**: el hook
   `useReviewToday`, el resumen y la **sesión encadenada** (`ReviewSession`). Es el fichero que
   decide si la release es una acción o un botón.
5. `frontend/src/features/vocabulary/FlashcardsScreen.tsx` — **el contenedor**: las cinco
   sub-pestañas, la pestaña **controlada** y el bloque de estudio con las **dos** acciones.
6. `frontend/src/features/vocabulary/DictionaryScreen.tsx` — **la proyección** de los tres
   valores persistidos sobre las dos pestañas.
7. `frontend/src/features/vocabulary/LexiconInventory.tsx` — el inventario resultado de retirar
   `StudyEntryCard` y `<ReviewQueueSection>`.
8. `frontend/src/features/vocabulary/DictionaryLookup.tsx` — **el núcleo de `v3.84.1`**: el
   estado parcial, el reintento de la tarjeta y el `DECK_NAME_TAKEN`.
9. `frontend/tests/visual/reviewSession.spec.ts` (nuevo) y
   `frontend/tests/visual/dictionaryFlashcardsBridge.spec.ts` — **las dos guardias**. Son los
   artefactos que deciden si el defecto puede volver.
10. `backend/tests/test_docs_drift_v372.py` y `docs/audit/F-UX-JOURNEY.md` — **el candado
    documental** que exige que el nombre viejo y el nuevo convivan declarados.
11. `docs/audit/PARKED.md` — **§V3.85.0** y **§V3.84.1**: lo cerrado, lo que sigue abierto y la
    deuda heredada, en el formato que la casa usa para no perder deudas.
12. `CHANGELOG.md` (las entradas `3.85.0` y `3.84.1`) y `docs/audit/TEMPLATE.md` (formato del
    informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
```

---

## 0.1 El arco tiene DOS releases etiquetadas y un commit heredado

A diferencia de los puntos de entrada anteriores —cuyo rango era un solo commit más, a veces, un
commit documental—, aquí el rango **contiene dos releases publicadas**, cada una con **su propio
tag anotado**:

```bash
git log --oneline v3.84.0..v3.85.0
# b1b502f release(v3.85.0): diccionario en dos pestanas y "Repasar hoy" accionable ...
# 5bc9050 release(v3.84.1): estado parcial del alta Diccionario -> lexico + mazo ...
# 6467e58 docs(audit): punto de entrada externo del arco v3.83.1..v3.84.0 (prefijo AX) ...
```

Los **subrangos son limpios** y así se declaran, porque es lo que permite auditar cada release
sin desenredarla de la otra:

```bash
git log --oneline v3.84.1..v3.85.0     # b1b502f   (UN commit: exactamente la minor)
git log --oneline v3.84.0..v3.84.1     # 5bc9050   + el heredado 6467e58
```

`6467e58` es **documental puro** (`agentes/auditoria-total-externa-v384.md`, +435 líneas): es el
punto de entrada `AX` que se entregó **después** del tag `v3.84.0`, porque un tag publicado no se
recrea. **No toca producto** y por eso queda fuera de los dos tags de este arco, pero **sí**
aparece en el rango `v3.84.0..v3.84.1` de `git diff`. Quien audite «el diff del tag» de `v3.84.1`
verá **21 ficheros** donde el release commit tiene **20**: el que sobra es este documento, y no
está en `frontend/src`, `backend/` ni `launcher/`.

**Por qué las dos van en un solo encargo.** Porque `v3.84.1` **nació sin punto de entrada** —se
publicó como patch en el mismo acto que la minor, para que el rango de `v3.85.0` no arrastrase su
diff— y porque las dos comparten la misma superficie (`features/vocabulary`). Dejarlas en dos
encargos habría alargado una **cola de auditoría ya atrasada** (§6-D5) sin ganar aislamiento: los
tags ya las separan. Si prefieres acotar el informe, **audita solo el subrango
`v3.84.1..v3.85.0`** y dilo en el informe; el encargo se declaró para el arco completo.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

```bash
git ls-remote --tags origin 'refs/tags/v3.84.1*' 'refs/tags/v3.85.0*'
git rev-list -n 1 v3.84.1                            # el commit de release del patch
git rev-list -n 1 v3.85.0                            # el commit de release de la minor
git cat-file -t v3.84.1                              # debe ser 'tag' (anotado)
git cat-file -t v3.85.0                              # debe ser 'tag' (anotado)
git log -1 --format=%s v3.84.1                       # 'release(v3.84.1): ...'
git log -1 --format=%s v3.85.0                       # 'release(v3.85.0): ...'
python scripts/check_release_consistency.py          # OK en los 6 orígenes
```

> *Nota para quien audite desde PowerShell:* `v3.85.0^{commit}` **se rompe** en PowerShell (el `^`
> se interpreta como escape). Usa `git rev-list -n 1 v3.85.0`, que es equivalente y funciona en
> cualquier shell. Este punto de entrada lo usa así a propósito.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

1. **Cada ancla es un tag anotado que apunta a su commit de release.** Si `git cat-file -t`
   devuelve `commit`, el punto de entrada está roto: el tag sería ligero y no llevaría su mensaje
   de release.
2. **Los dos tags no son el mismo commit.** `v3.84.1` y `v3.85.0` apuntan a commits **distintos**,
   y el rango `v3.84.1..v3.85.0` contiene **un solo** commit: verificar la separación es el primer
   paso para poder auditar una release sin la otra.
3. **En `v3.85.0` no hay lógica de backend.** Verificable:

```bash
git diff --name-only v3.84.1..v3.85.0 -- backend
# backend/config.py
# backend/tests/test_docs_drift_v372.py
git diff v3.84.1..v3.85.0 -- backend/config.py
# VERSION = "3.84.1" -> "3.85.0"  (una sola línea)
```

4. **En `v3.84.1` el único cambio de backend de producto es un `detail`.** Verificable:

```bash
git diff v3.84.1^..v3.84.1 -- backend/routers
# -  raise HTTPException(status_code=400, detail="No se pudo crear el mazo")
# +  raise HTTPException(status_code=400, detail="DECK_NAME_TAKEN")
```

5. **No hay migración de BD en ninguna de las dos.** El diff de `backend/db.py` está **vacío** y
   no hay ningún `ALTER TABLE` nuevo:

```bash
git diff --name-only v3.84.0..v3.85.0 -- backend/db.py    # (sin salida)
git grep -n "ALTER TABLE" v3.85.0 -- backend | grep -v tests || true
```

6. **La persistencia no se migra: se proyecta.** `DictionaryView` conserva sus **tres** valores
   (`"lookup" | "personal" | "flashcards"`) y `"personal"` sigue existiendo como valor
   almacenado aunque ya no haya una pestaña con ese nombre. Verificable:

```bash
git grep -n "tabs.personal" v3.85.0 -- frontend/src      # (sin salida: la clave i18n murió)
git grep -n '"personal"' v3.85.0 -- frontend/src         # (viva: es un valor persistido)
```

7. **La versión es consistente en los 6 orígenes y cada tag lo dice.** `check_release_consistency.py`
   en `v3.84.1` informa `3.84.1` y en `v3.85.0` informa `3.85.0`.
8. **Las guardias muerden.** Ni `reviewSession.spec.ts` ni el caso «fallo de la tarjeta» de
   `dictionaryFlashcardsBridge.spec.ts` deben pasar por vacío: revertir el comportamiento tiene
   que **romperlos** (§2-B1 y §2-C1 piden el experimento, no la opinión).
9. **El CI certifica el tip de cada push, y aquí se usó a propósito.** Este proyecto tiene
   declarado que el CI **no** certifica estados intermedios de un mismo push (invariante 9 del
   informe `AT`). Por eso las dos releases se publicaron en **dos pushes separados**: cada commit
   de release tiene su **propio** run verde. Verificar en la pestaña Actions que el run
   correspondiente a **cada** `rev` está en `success` es parte del encargo, no un adorno.

### 1.2 Lista cerrada — los commits del arco

| Commit | Tipo | Qué es |
|---|---|---|
| `6467e58` | documental | Punto de entrada `AX` del arco anterior, entregado **después** de `v3.84.0` |
| `5bc9050` | **release** | **`v3.84.1`** — estado parcial del alta Diccionario → léxico + mazo |
| `b1b502f` | **release** | **`v3.85.0`** — diccionario en dos pestañas y «Repasar hoy» accionable |

### 1.3 Estado de publicación (verificado por comando, no fijado a mano)

| Comprobación | Resultado |
|---|---|
| `git ls-remote --tags origin` | `v3.84.1` y `v3.85.0` presentes, **ambos anotados** (`^{}`) |
| `git cat-file -t v3.84.1` / `v3.85.0` | `tag` en los dos |
| CI en `5bc9050` (`v3.84.1`) | `success` — run `36230797482` |
| CI en `b1b502f` (`v3.85.0`) | `success` — run `36231733861` |
| `main` vs `origin/main` | al día en el momento de entregar este documento |
| Última versión declarada en `README.md` | `v3.85.0` |

### 1.4 Verificación que las releases declaran

| Comprobación | `v3.84.1` (patch) | `v3.85.0` (minor) |
|---|---|---|
| `npx tsc --noEmit` | limpio | limpio |
| `npm run test` (vitest) | **1038/1038** (109 ficheros) | **1041/1041** (109 ficheros) |
| `python -m pytest -q` (backend) | **3141/3141** | **3141/3141** |
| `python -m pytest -q` (lanzador) | **269/269** | **269/269** |
| `check_i18n_coverage.py --strict` | **1785** cadenas, 0 huérfanas | **1774** cadenas, 0 huérfanas |
| `contrast_audit.mjs --strict` | 480 pares + 6 guardas / **0 bloqueantes** | 480 pares + 6 guardas / **0 bloqueantes** |
| `validation_gate.py auto --require-dist` | **10/10** (8 gates) | **10/10** (8 gates) |
| `npx playwright test` (barrido completo) | **96 passed · 0 failed · 30 skipped** | **99 passed · 0 failed · 30 skipped** |
| `check_release_consistency.py` | OK en los 6 orígenes | OK en los 6 orígenes |

> Que `pytest` dé el **mismo** número en las dos releases es correcto y no un copia-pega: el
> patch añade un test de backend y la minor **no toca** ningún test de backend de producto (solo
> el candado documental). Si ese número te parece raro, verifícalo: es exactamente la clase de
> detalle que un informe debe comprobar en vez de asumir.

---

## 2. Preguntas falsables por área

Cada pregunta se responde con **un comando, un experimento o una lectura**, y cada veredicto debe
llevar su evidencia pegada en el informe. Las preguntas marcadas **[NÚCLEO]** son las que deciden
el dictamen.

### A. El ancla, el arco y la promesa

- **A1.** ¿Los dos tags son anotados y apuntan a sus commits de release? ¿Y el mensaje de cada tag
  describe **su** release y no la del vecino?
- **A2.** ¿El rango `v3.84.1..v3.85.0` contiene **un solo** commit? Si contiene más, ¿está
  declarado cuáles y por qué?
- **A3.** `v3.84.1` se publicó **sin punto de entrada propio** (nació en el mismo acto que la
  minor). ¿Es aceptable, o deja una release de producto sin encargo externo durante un tiempo
  indefinido? Dictamina la **política**, no solo el hecho.
- **A4.** Este documento se entrega en un commit **posterior** a los tags. ¿Es verificable el
  desfase (`git log --oneline v3.85.0..main`) y el rango de cada tag queda intacto y sin reescritura?
- **A5.** ¿`docs/audit/PARKED.md §V3.84.1` y `§V3.85.0` cubren toda la deuda que las notas
  declaran? Busca un «cerrado» que no lo esté: es el defecto clásico de este proyecto.

### B. `v3.84.1` — el patch de honestidad

- **B1. [NÚCLEO]** ¿La guardia del estado parcial **muerde**? Revertido el `try/catch` propio del
  alta del léxico en `DictionaryLookup.tsx` (haciendo que un fallo de `createFlashcard` vuelva a
  pintar el error simple), ¿**falla** `dictionaryFlashcardsBridge.spec.ts`, y concretamente cuál
  de sus cuatro casos? Si no falla ninguno, la guardia es decorativa y el patch es una promesa.
- **B2.** `handleRetryDeckCard` limpia `pendingDeck` **antes** de reintentar o después? Con
  `adding` como única puerta, ¿un doble clic rápido sobre «Reintentar guardar en el mazo» puede
  crear **dos** tarjetas en el mazo? Inténtalo de verdad (dos `click` sin `await`), no lo razones.
- **B3.** `pendingDeck` se limpia en `runLookup`, `closeAddPanel`, `changeDirection` y
  `clearQuery`. ¿Queda algún camino que deje un `pendingDeck` **huérfano** y ofrezca un reintento
  que ya no corresponde a la palabra en pantalla?
- **B4.** `DECK_NAME_TAKEN` es un **código máquina** que viaja en el campo `detail` de un `400`.
  ¿Algún consumidor pinta `detail` en crudo al alumno? Rastrea el manejo de errores del cliente y
  decide si un alumno puede llegar a leer `DECK_NAME_TAKEN` en pantalla.
- **B5.** En el estado parcial, el CTA «Estudiar en Flashcards» sigue disponible **sin el
  `deckId`** (porque la tarjeta no entró). ¿A qué mazo lleva entonces, y se confunde «reintentar
  la tarjeta» con «estudiar lo que sí entró»?
- **B6.** El patch declara que la opción **B** (endpoint transaccional «alta de léxico + tarjeta de
  mazo») queda aparcada. Con la BD actual, ¿era **viable** una transacción conjunta, o el
  aparcamiento se apoya en un imposible? Si era viable, el aparcamiento es una decisión de coste,
  no una imposibilidad técnica, y el informe debe decirlo así.

### C. `v3.85.0` — «Repasar hoy»: ¿acción o botón? (el núcleo)

- **C1. [NÚCLEO]** La sesión **solo avanza** si `produced` es `true`, y `produced` solo se pone a
  `true` cuando `WordDrill` dispara `onProduced`, que según sus propias notas ocurre **cuando el
  intento pasa el peldaño**. Preguntas encadenadas:
  - ¿**Todos** los peldaños (`recognition`, `recall`, `sentence`, `write`, `transfer`) disparan
    `onProduced` al superarse, o hay alguno que **no**?
  - Si hay un peldaño que no lo dispara, el alumno queda **encerrado en ese ítem**: no aparece
    «Siguiente palabra», `index` no avanza y la única salida es cerrar el drill (que **aborta la
    sesión entera**). **Ese** es el modo de fallo catastrófico de esta release: búscalo.
  - `reviewSession.spec.ts` sirve los ítems con `activity: "write"`, y las notas **declaran el
    motivo** («es el único peldaño que acredita producción sin micrófono»). Es una elección
    honesta **y** es exactamente lo que puede estar tapando el agujero. Cambia el fixture a
    `recognition` y a `recall` y **repite el spec**: ¿la sesión avanza, o se queda clavada?
- **C2.** `ReviewSession` sale con `onExit()` cuando `index >= items.length`. Al volver al resumen,
  ¿el recuento refrescado puede ser **mayor que 0** otra vez (porque la cola se recalculó o porque
  el POST del último peldaño reprogramó la carta)? Si sí, el botón nunca llega a `0`: ¿es un
  bucle infinito de repaso o una función del planner? Dictamínalo con el dato, no con la intuición.
- **C3.** La traza declarada (`reason`, `WhyThisActivity`, `DecisionSignals`) se muestra **una vez
  por palabra** y solo para la que se está trabajando. ¿Puedes **confirmarlo o desmentirlo**
  leyendo el render? Si en algún momento se pinta fuera de la sesión, la afirmación de las notas
  es falsa.
- **C4.** `WordDrill` recibe `decisionId` = `current.decision_id` y declara el ciclo de vida
  (`started`/`abandoned`). Si el alumno cierra el drill en el ítem 3 de 50, ¿los ítems 4..50
  quedan anotados como `abandoned`, como nada, o como `started` sin cerrar? Busca la evidencia en
  el backend: un `started` huérfano sería un dato sucio que nadie limpiaría.
- **C5.** [`ReviewToday.tsx`](../../frontend/src/features/vocabulary/ReviewToday.tsx) pide
  `REVIEW_LIMIT = 50` y el endpoint devuelve `due_count = len(items)`, así que el **N** del botón
  es **exactamente** la longitud de la sesión y no promete de más — verifícalo en
  `backend/domain/review.py` antes de dar por buena esa parte. Pero convierte C5 en la pregunta
  de producto de §6-D3: una sesión de hasta 50 ítems con **un clic obligatorio por ítem** y **sin
  estado persistido** (salirse la pierde entera), ¿es una sesión o una condena?

### D. La sesión encadenada — los modos de fallo

- **D1.** `onExit` viaja dentro de un `useEffect` con `[index, items.length, onExit]`. Si `onExit`
  cambiase de identidad en cada render, el efecto se reevaluaría: aquí solo actúa si
  `index >= items.length`, pero **comprueba la estabilidad** de `exitReview` y si el efecto puede
  disparar una salida antes de tiempo.
- **D2.** `produced` se resetea al cambiar de índice. Si el alumno **produce dos veces** el mismo
  ítem (dos intentos superados), ¿aparece un solo «Siguiente palabra» (idempotente) o la sesión
  se desordena?
- **D3.** El drill cierra con `onClose={onExit}` y las notas dicen que se retiró un botón «Cerrar»
  duplicado. ¿`exitReview` **refresca** el recuento al salir? Si no lo refresca, el botón puede
  seguir anunciando un `N` que ya no es cierto.
- **D4.** Accesibilidad de la sesión: el contador `{index} de {total}` que añade esta release,
  ¿se **anuncia** (región viva) o solo se ve? ¿«Siguiente palabra» / «Terminar» reciben el foco al
  aparecer, o el usuario de teclado tiene que tabular hasta el final del drill para avanzar?
  Navega la sesión **solo con el teclado** y cuéntalo.

### E. Las dos pestañas y la proyección de la persistencia

- **E1.** `"personal"` guardado **antes** de esta versión debe abrir Flashcards en `Mi léxico`.
  Verifícalo **a mano** (no en test): escribe `"personal"` en el almacenamiento persistido,
  recarga y mira dónde abres. El test dice que sí; el encargo pregunta si el **camino real** del
  usuario pasa por ahí.
- **E2.** `Mi léxico` vuelve a persistir `"personal"`; cualquier otra sub-pestaña persiste
  `"flashcards"`. ¿Hay una **tercera vía** que deje el valor inconsistente (cerrar el diccionario
  estando en Mazos, el panel incrustado de APRENDER → Vocabulario vía `toPanelView`, un enlace
  profundo)? Enumera todas las escrituras del valor persistido y di si son coherentes.
- **E3.** El «sin migración» es literal: la clave i18n `dictionary.tabs.personal` murió y el
  **valor persistido** sigue vivo. ¿Está declarado en algún sitio que la UI tiene **dos** pestañas
  y el dominio persistido **tres** valores? Un lector nuevo, ¿lo deduce solo del código?
- **E4.** `FlashcardsScreen` pasa a pestaña **controlada** (`tab` + `onTabChange`). Las notas
  declaran que es seguro «porque **solo** la monta `DictionaryScreen`». **Comprueba esa premisa**:
  un `grep` de todos los montajes de `FlashcardsScreen` debe dar exactamente uno. Si hay dos, la
  pestaña controlada puede romper el otro.

### F. Lo que se retira — el inventario y el panel incrustado

- **F1. [NÚCLEO]** `PersonalDictionary` → `LexiconInventory` con **retirada** de `StudyEntryCard` y
  `<ReviewQueueSection>`. Compara los dos ficheros (`git show v3.84.1:...` contra
  `git show v3.85.0:...`) y responde: ¿se retiró **solo** estudio y repaso, o se fue algo más que
  las notas no declaran? El inventario se vende como «posesión y producción»: verifica que
  **sigue estando todo** lo que la posesión y la producción necesitan.
- **F2.** El micro-drill oral se conserva con rótulo nuevo (`dictionary.speakingPractice`,
  «Práctica oral»). ¿El rótulo nuevo describe lo que hay, o el cambio de nombre tapa una pérdida?
- **F3.** El renombrado: `grep -rn "PersonalDictionary" frontend/src` debe estar vacío en el
  producto y vivo en los documentos que lo citan como referencia histórica. ¿Hay alguna referencia
  al nombre viejo **en el producto** que se haya quedado?
- **F4.** El **panel incrustado** (APRENDER → Vocabulario) **pierde el drill de repaso**. Es una
  decisión declarada, pero es una **pérdida de capacidad** para quien trabaja desde APRENDER.
  ¿Es aceptable, o el panel incrustado debería ofrecer al menos un enlace a la sesión?

### G. Instrumento: i18n, responsive y candados

- **G1.** `backend/tests/test_docs_drift_v372.py` exige que `docs/audit/F-UX-JOURNEY.md` declare
  **el nombre viejo y el nuevo**. Bórralo del journey y comprueba que **falla**: si no falla, el
  candado es un comentario caro.
- **G2.** La sub-tablist de **cinco** elementos se resuelve con `overflow-x-auto` (scroll
  horizontal) en anchos estrechos. La guardia de V3.84.0 (`expectNoHorizontalOverflow`) vigila
  que **la página** no desborde: ¿distingue **scroll legítimo dentro** de un contenedor de
  **recorte silencioso**, que fue el defecto de clase de V3.84.0? Si no lo distingue, esta release
  puede reabrir exactamente la misma clase sin que nada se ponga rojo.
- **G3.** El contraste sigue en **0 bloqueantes** con **480 pares + 6 guardas**. ¿Los rótulos
  nuevos («Mi léxico», «Repasar ahora (N)», «Estudiar tarjetas (N)», «Práctica oral») reutilizan
  pares ya medidos o introducen combinaciones nuevas **no** medidas? Si son nuevas,
  «0 bloqueantes» no dice nada de ellas.
- **G4.** `check_i18n_coverage.py --strict` baja de **1785** a **1774** cadenas: 17 retiradas, 7
  añadidas. ¿Alguna de las **retiradas** seguía usándose de forma **dinámica** (construida por
  concatenación) y por eso no aparece como huérfana? El checker declara 81→80 prefijos dinámicos:
  comprueba que no falta ninguno.

---

## 3. Matriz de cierre (la rellena el auditor)

| # | Área | Veredicto | Evidencia (comando + salida) |
|---|---|---|---|
| A | Ancla, arco y promesa | | |
| B | `v3.84.1`: estado parcial y duplicado | | |
| C | `v3.85.0`: «Repasar hoy» como acción **[NÚCLEO]** | | |
| D | Sesión encadenada: modos de fallo | | |
| E | Dos pestañas y proyección de la persistencia | | |
| F | Retiradas: inventario y panel incrustado **[NÚCLEO]** | | |
| G | i18n, responsive y candados | | |
| D1 | Deriva del ancla de certificación (§6-D1) | | |
| D2 | `ReviewTodayCard` fantasma (§6-D2) | | |
| D3 | Límite de cola 20 → 50 sin declarar (§6-D3) | | |
| D4 | Cola de auditoría atrasada (§6-D5) | | |

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se modifica, etiqueta ni empuja nada del repositorio público. Los
   experimentos de reversión (B1, C1, G1) se hacen en un **clon de trabajo** y se documentan; el
   resultado que vale es la salida del comando, no la magnitud del cambio.
2. **Los tags no se recrean.** Si encuentras que un tag dice algo falso, **no se arregla el tag**:
   se declara en el informe y se corrige hacia delante (§6 es exactamente eso).
3. **Ningún veredicto sin comando.** «Parece que», «debería», «en principio» no son veredictos.
   Si no pudiste comprobarlo, escribe **«no verificado»** y di por qué.
4. **Distingue no-verificado de falso.** Un informe que declara lo que no miró vale más que uno
   que opina sobre todo.
5. **Cuidado con PowerShell** (§1): el `^` rompe las expresiones de git.
6. **No puntúes la ausencia de migración como virtud.** El encargo no premia que «no rompa»:
   premia que dictamine si **lo que promete la UI es verdad**.

---

## 5. Honestidad esperada del informe

Un informe aceptable para este proyecto:

- **Declara el entorno** (SO, versiones de node/python, si el barrido de Playwright se corrió
  completo o por ficheros) y **el rango real** que auditó.
- **Separa las dos releases** cuando el veredicto difiera: es perfectamente posible que el patch
  esté bien y la minor no, o al revés.
- **Nombra los modos de fallo encontrados con su reproducción** (pasos, resultado esperado,
  resultado obtenido).
- **Dice qué NO miró** (rendimiento, seguridad de sesión, accesibilidad completa, el contenido
  pedagógico de la cola) sin fingir cobertura.
- **No inventa una nota global** si la casa no la pide; y si la pide, que sea la consecuencia de
  la matriz, no un resumen del ánimo.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

Se declaran aquí, y no en las notas de release, porque **se descubrieron después de publicar los
tags** y **un tag publicado no se recrea**. Es el mecanismo que este proyecto usa para no
reescribir la historia: la discrepancia se **declara** y se dictamina.

- **D1. La deriva del ancla de certificación sigue abierta y ha crecido.**
  `docs/audit/KIT-VALIDACION-GATES.md` y `VALIDATION-RELEASE-V373.md` siguen apuntando a
  `v3.83.1` mientras se han publicado **tres** releases de producto desde entonces (`v3.84.0`,
  `v3.84.1`, `v3.85.0`). Ya era la pregunta `§6-D1` del encargo `AX`; este arco **no la cierra**
  (decisión declarada: los 8 gates humanos siguen `pending` y `validation-evidence.json` sigue sin
  existir). Dictamina si la deriva es tolerable o si debe re-congelarse el ancla **antes** de
  seguir publicando.

- **D2. Las notas de `v3.85.0` nombran un componente que no existe.**
  `release-notes-v3.85.0.md §3` describe el resumen como **`ReviewTodayCard`**, y **no hay ningún
  `ReviewTodayCard` en el código**: el resumen se renderiza **en línea** dentro de `StudyTab`
  (`FlashcardsScreen.tsx`) y el estado vive en el hook `useReviewToday`. Es un error de nombre en
  documentación de una release publicada, no un fichero que falte. Se declara en vez de
  arreglarse (el tag no se recrea). La pregunta: ¿tolerable, o exige un `docs(audit)` de errata
  antes del informe?

- **D3. El límite de presentación de la cola pasó de 20 a 50 y el tag no lo declara.**
  `ReviewQueueSection` (retirado) llamaba `getReviewQueue(userId)` **sin límite**, así que
  aplicaba `REVIEW_QUEUE_DEFAULT_LIMIT = 20` (`backend/domain/review.py:41`). `useReviewToday`
  pide `REVIEW_LIMIT = 50`, que es `REVIEW_QUEUE_MAX_LIMIT`. Como el endpoint devuelve
  `due_count = len(items)`, **el número que el alumno ve** («Repasar ahora (N)») y **la longitud
  de la sesión** pueden pasar de 20 a 50. Es un cambio **visible de producto** que las notas **no**
  declaran: no dicen «ahora servimos hasta 50 en vez de 20», dicen que la lista era «de hasta 20
  filas». El límite está justificado en un comentario del código («para que una sesión cubra el
  día entero de una tirada»), no en la letra de la release. **Pregunta:** ¿es una mejora
  declarada a medias, y es correcto que el tag no lo diga? Nótese que agrava C5: **50 ítems con
  un clic por ítem y sin estado persistido**.

- **D4. El panel incrustado pierde capacidad, y eso es una regresión, no un añadido.**
  APRENDER → Vocabulario pierde el acceso al drill de repaso. Está declarado en las notas como
  decisión, pero se vende dentro del paquete «el estudio vive donde se trabaja». Dictamina si la
  pérdida tiene sustituto para quien trabaja desde el panel incrustado.

- **D5. La cola de auditoría está atrasada y este encargo la alarga siendo el cuarto abierto.**
  Pendientes de informe: **`AV`** (`v3.82.0` — el eslabón que **cambió el contrato de
  `POST /api/session`** y **migró la BD**), **`AW`** (cierre de la serie V3.83.x) y **`AX`**
  (`v3.84.0`). Este `AY` llega **antes** que el único que toca contrato y migración. No es un
  defecto de producto, es una **deuda de proceso**, y se declara para que el informe pueda
  dictaminar el orden.

---

## 7. Alcance

**`v3.84.1` — el patch.**

- `frontend/src/features/vocabulary/DictionaryLookup.tsx` (estado `partial`, `saveDeckCard`,
  `handleRetryDeckCard`, `deckCreateError`) y `DictionaryLookup.test.tsx`.
- `frontend/src/utils/i18n.ts` (5 claves nuevas: `addPartial`, `addPartialHint`,
  `addPartialRetry`, `addDeckDuplicate`, `addDeckCreateError`).
- `frontend/tests/visual/dictionaryFlashcardsBridge.spec.ts` (los **cuatro desenlaces** del
  puente, con la cola de cada mazo construida con lo que entró de verdad).
- `backend/routers/vocabulary.py` (**un** `detail`), `backend/tests/test_flashcards_v378.py`
  (test del duplicado), `backend/repositories/collections.py` (**solo docstring**: la política
  append-only por `slug`).
- Documentación (`CHANGELOG`, `PLAN`, `RELEVO`, `PARKED §V3.84.1`), informe generado y bump.

**`v3.85.0` — la minor.**

- `frontend/src/features/vocabulary/`: `ReviewToday.tsx` **nuevo**, `LexiconInventory.{tsx,test.tsx}`
  **nuevos** (procedentes de `PersonalDictionary.*`, **retirados**), `ReviewQueueSection.*`
  **retirados**, `DictionaryScreen.tsx`, `FlashcardsScreen.tsx`, `VocabularyRoutesPractice.tsx`.
- `frontend/src/utils/i18n.ts` (7 claves nuevas, 17 retiradas).
- `frontend/tests/visual/`: `reviewSession.spec.ts` **nuevo**, y `dictionarySmoke`,
  `flashcardsSmoke`, `responsiveOverflow`, `drillProvenance`, `studySessionVisual`,
  `studySessionKeyboard` adaptados.
- `backend/tests/test_docs_drift_v372.py` (candado documental) y `docs/audit/F-UX-JOURNEY.md`.
- Documentación, informes generados y bump.

**Lo que NO toca ninguna de las dos:** esquema de BD, contrato de API, endpoints,
`GENERATOR_VERSION`, `DECISION_POLICY_VERSION`, `CURRICULUM_VERSION` (sigue `1.3.1`),
`LISTENING_BANK_VERSION`, las evaluaciones y el número o la definición de los gates.
**`v3.85.0` no tiene una sola línea de lógica de backend.**

**Punto de entrada al detalle:** `docs/audit/PARKED.md §V3.85.0` y `§V3.84.1`, `docs/RELEVO.md` y
`docs/audit/F-UX-JOURNEY.md`.

---

## 8. Nota de prefijos y cierre

Los prefijos `AP`, `AQ`, `AR`, `AS`, `AT`, `AU`, `AV`, `AW` y `AX` están **reservados** por
encargos anteriores (`AV`, `AW` y `AX` **siguen esperando su informe**; `AU` se dictaminó).
**`AY` es el primer prefijo libre** y es el que corresponde a este informe. El siguiente sería
`AZ`, y a partir de ahí habría que decidir una convención nueva: **si el informe `AY` considera
que la cola de encargos abiertos es un problema (§6-D5), la convención de prefijos es parte de lo
que debe dictaminar**.

**Cierre.** Este documento es un **encargo**, no un informe. No declara que nada esté bien: declara
**qué hay que intentar tumbar** y con qué instrumento. Si una afirmación de las notas de release
no se puede verificar, el informe debe decirlo; si se puede y es falsa, el informe debe decirlo
**con la salida del comando delante**.
