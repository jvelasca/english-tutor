# AY — Auditoría externa total — arco `v3.84.0..v3.85.0`

> **Encargo:** `agentes/auditoria-total-externa-v385.md` (prefijo `AY`), entregado el 2026-09-26 en
> un **commit documental posterior a los dos tags** (`6098d88`), porque un tag publicado no se
> recrea.
> **Autor:** auditoría externa con ancla verificada **por comando** contra el árbol local y el
> repositorio remoto.
> **Alcance:** el arco completo — `v3.84.1` (**patch**) y `v3.85.0` (**minor**).
> **Cierre:** los hallazgos `P0`/`P1` se corrigen en `v3.85.1`; este informe **declara** su
> disposición en un addendum (`§9`) con el comando que la demuestra.
>
> **Nota posterior (2026-09-26, antes de publicar `v3.86.0`) — léase «`v3.85.1`» como «el delta
> absorbido por `v3.86.0`».** La versión `v3.85.1` **nunca llegó a etiquetarse**: el trabajo se
> quedó en el árbol de trabajo y el `HEAD` público siguió en `v3.85.0`. Por eso **`v3.85.1` no
> existe como tag** y **no se recrea**, y su contenido va **incluido íntegro en `v3.86.0`**. Las
> referencias a `v3.85.1` de este informe deben leerse como el **delta absorbido por el tag
> `v3.86.0`**; no hay, por tanto, un tag intermedio que auditar. Esta nota **no altera** el
> contenido del informe —lo deja tal como se emitió— y se añade solo para que nadie persiga una
> etiqueta inexistente. Ver `release-notes-v3.86.0.md` (§8-ix) y
> `agentes/auditoria-total-externa-v386.md` (§6).

---

## 0. Método y ancla por comando

La regla de esta casa es **no dar un veredicto sin su comando**. Eso vale también aquí, y con una
advertencia methodológica que este arco exige:

> **La suite del proyecto NO se usa como evidencia de corrección.** El P0 de este informe
> (`§3-C1`) sobrevivió a un E2E **verde** y a **1041** pruebas unitarias verdes. La suite era fiel
> a lo que probaba y ciega a lo que no: **fixture sesgado** (`activity: "write"` en el 100 % de los
> ítems). Por eso el método aquí es (1) resolver anclas por comando, (2) leer el código de la ruta
> crítica, (3) **construir una sonda que muerda** y (4) **reproducir el fallo desactivando el
> arreglo**. Un informe que solo pegara la salida de `npm test` habría firmado el P0 como verde.

| Paso | Comando | Qué se buscó |
|---|---|---|
| Ancla del patch | `git rev-list -n 1 v3.84.1` | `5bc9050126e3c488e037c6ce4f027232fc9e2da8` |
| Ancla de la minor | `git rev-list -n 1 v3.85.0` | `b1b502f1fb7c3d8f5380f3473d8e33b560f3f336` |
| Tipo de tag | `git cat-file -t v3.84.1` / `v3.85.0` | `tag` en los dos (anotados) |
| Rango de la minor | `git log --oneline v3.84.1..v3.85.0` | **1 commit** (`b1b502f`) |
| Rango del patch | `git log --oneline v3.84.0..v3.84.1` | **2 commits** (release + heredado `6467e58`) |
| Log de backend del patch | `git diff --numstat v3.84.1^..v3.84.1 -- backend` | `1/1` config · `10/0` collections · `6/1` vocabulary · `23/0` test |
| Log de backend de la minor | `git diff --name-only v3.84.1..v3.85.0 -- backend` | `config.py` + `test_docs_drift_v372.py` |
| Log de BD | `git diff --name-only v3.84.0..v3.85.0 -- backend/db.py` | **vacío** (sin migración) |
| Desfase post-tag | `git log --oneline v3.85.0..main` | **1** commit documental (`6098d88`) |
| Sonda del P0 | `git show v3.85.0:frontend/src/features/vocabulary/ReviewToday.tsx` | `const [produced…]` · `{produced ? (` |
| Sonda del fixture | `git show v3.85.0:frontend/tests/visual/reviewSession.spec.ts` | `activity: "write"` ×2 |
| Sonda del disparador | `git show v3.85.0:.../wordDrill.tsx \| Select-String "onProduced\(\)"` | **solo 3** sitios: write, transfer, sentence |
| Cada cifra de `§4` | `npx tsc`, `npx vitest run`, `pytest -q`, `ruff check`, `check_i18n_coverage.py --strict`, `contrast_audit.mjs --strict`, `check_release_consistency.py` | reproducible |

---

## 1. Invariantes del encargo (§1.1), comprobados uno a uno

| # | Invariante | Veredicto | Evidencia |
|---|---|---|---|
| 1 | Cada ancla es un tag **anotado** apuntando a su commit de release | **Cumple** | `git cat-file -t` → `tag`; `git rev-list -n 1` → los dos SHAs distintos |
| 2 | Los dos tags **no** son el mismo commit y el rango de la minor es **1** commit | **Cumple** | `v3.84.1..v3.85.0` = `b1b502f` |
| 3 | En `v3.85.0` **no hay lógica de backend** | **Cumple** | el diff de `backend/` es `VERSION` + el candado documental |
| 4 | En `v3.84.1` el único cambio de backend de producto es el `detail` de un `400` | **Cumple** | `backend/repositories/collections.py` son **10 líneas de docstring**, no lógica |
| 5 | **No** hay migración de BD en ninguna de las dos | **Cumple** | diff de `backend/db.py` vacío |
| 6 | La persistencia **no se migra: se proyecta** (`"personal"` sigue vivo) | **Cumple** | ver `§5-E` |
| 7 | La versión es consistente en los **6 orígenes** y cada tag lo dice | **Cumple** | `check_release_consistency.py` OK en `v3.84.1` y en `v3.85.0` |
| 8 | **Las guardias muerden** | **FALLA en `v3.85.0`** | la guardia del núcleo era **ciega por fixture** (ver `§3-C1`); ver el experimento de `§9` |
| 9 | El CI certifica el **tip** de cada push y cada release tiene su run | **No verificable desde este árbol** | los runs `36230797482` (`5bc9050`) y `36231733861` (`b1b502f`) están declarados en el encargo; este informe **no** los reverifica contra GitHub y lo declara |

> **La invariante 8 es el hallazgo estructural de este arco.** Las notas de `v3.85.0` declaran que
> la sesión «solo avanza si el intento supera el peldaño» y el E2E lo verifica; las dos cosas son
> ciertas **y a la vez** el núcleo estaba roto, porque el E2E eligió el único peldaño que hace
> verdadera la premisa. **Una guardia que prueba un subconjunto elegido por comodidad no es una
> guardia: es una confirmación.**

---

## 2. Dictamen de proceso (las dos preguntas de política)

### D1 — Certificación

**Dictamen: la serie está lista para EMPEZAR la certificación, no para declararla.** El ancla de
certificación sigue en **`v3.83.1`** y **los ocho gates humanos siguen `pending`**;
`docs/audit/validation-evidence.json` **no existe**. Este arco **no** re-congela el ancla: publica
producto (UI) sobre un árbol que no es el que se certificará. Consecuencia que este informe escribe
en letra: **cualquier campaña de gates ejecutada hoy sobre `v3.85.0` mediría un árbol que ya no es
el tip** en cuanto entra `v3.85.1`. La re-congelación del ancla es una decisión del gerente y este
informe la deja **abierta**, no la resuelve.

### D5 — Cola de auditorías

**Dictamen: la cola sigue atrasada y este informe no la reduce, la reordena.** Con `AY`
dictaminado, la deuda es:

| Prefijo | Arco | Estado | Por qué importa |
|---|---|---|---|
| `AV` | `v3.81.2..v3.82.0` | **pendiente** | es el **único** que cambia contrato (`POST /api/session`) y hace migración de BD |
| `AW` | cierre V3.83.x | **pendiente** | sintetiza la serie del ancla de certificación |
| `AX` | `v3.83.1..v3.84.0` | **pendiente** | guardia de layout (¿muerde?) y deriva de ancla declarada |
| `AY` | `v3.84.0..v3.85.0` | **dictaminado aquí** | — |

`AV` sigue siendo **la mayor deuda de auditoría de la serie** y es la única que no se puede
reducir a «UI»: si el contrato de sesión no se audita antes de certificar, la campaña de gates
certifica un contrato que nadie ha dictaminado.

---

## 3. Hallazgos

Severidad en la escala de la casa: **P0** = bloquea el uso de la función central de la release;
**P1** = promesa incumplida o regresión de capacidad declarada como virtud; **P2** = instrumento,
letra o accesibilidad; **P3** = cosmético/documental.

### C1 — `ReviewSession` se queda **clavada** en los peldaños reconductivos · 🔴 **P0**

**El hecho, en el código del tag:**

```bash
git show v3.85.0:frontend/src/features/vocabulary/ReviewToday.tsx | Select-String "produced|onProduced"
#  const [produced, setProduced] = useState(false);
#    setProduced(false);
#        onProduced={() => setProduced(true)}
#      {produced ? (
```

```bash
git show v3.85.0:frontend/src/features/vocabulary/wordDrill.tsx | Select-String "onProduced\(\)"
#        if (outcome.passed) onProduced();   ← submitWrite
#        if (outcome.passed) onProduced();   ← submitTransfer
#          if (attempt.passed) onProduced(); ← submitSentence
```

**Solo tres sitios.** `submitRecognition` y `submitRecall` **no** disparan `onProduced`: su acierto
es señal léxica, no producción —la decisión es correcta y está documentada desde V3.13/V3.34—.
Pero `ReviewSession` usaba **esa misma señal** como puerta del avance:

| Peldaño servido | ¿Enciende `produced`? | Consecuencia |
|---|---|---|
| `recognition` | **no** | **sesión clavada** |
| `recall` | **no** | **sesión clavada** |
| `sentence` | sí (si pasa) | avanza |
| `write` | sí (si pasa) | avanza |
| `transfer` | sí (si pasa) | avanza |

Como `ReviewSession` pasa `initialStep={current.activity}` y el planner sirve el peldaño
recomendado por hueco de competencia, **bastaba con que la cola recomendara Recognition o Recall**
para que «Siguiente palabra» no apareciera **nunca**: el alumno quedaba encerrado en ese ítem y la
única salida era cerrar el drill, que **aborta la sesión entera**. La función central de la release
—«la cola del día deja de ser una lista y pasa a ser una sesión que se maneja»— **no se podía
manejar** en el camino que el propio planner elige.

**Por qué el E2E no lo vio (el agravante):**

```bash
git show v3.85.0:frontend/tests/visual/reviewSession.spec.ts | Select-String "activity"
#  * Los ítems se sirven con `activity: "write"` porque es el único peldaño que
#      activity: "write",
#      activity: "write",
```

El fixture sirve **el 100 %** de los ítems con el único peldaño que hace verdadera la premisa del
test. La elección está **declarada** en el comentario y es honesta para correr sin micrófono —y es
**exactamente** lo que convierte la guardia en decorativa—. `ReviewToday.test.tsx` hace lo mismo
(dos ítems, ambos `write`).

**Veredicto:** **P0 confirmado.** No es «un caso raro»: es el camino por defecto cuando la cola
recomienda el peldaño reconductivo, que es el más barato de servir y por tanto el más probable.

### C2 — «Repasar hoy» no consume vencimiento FSRS, y las notas no lo dicen · 🟠 **P1 (semántica)**

`ReviewSession` termina, vuelve al resumen y llama a `onExit` → el contenedor **refresca el
recuento**. Ninguno de los peldaños de `WordDrill` —salvo el POST de attempt, que actualiza señal
léxica— **califica ni reprograma la carta FSRS**: completar la sesión **no** «paga» la deuda del
día. Por eso `GET /api/learning/review` puede volver a servir la misma palabra y el botón **puede
seguir diciendo N > 0** inmediatamente después.

`due_count = len(served_items)` (el `N` del botón es la longitud de lo que el backend sirve, no un
total teórico) — esa parte es **honesta** y se confirma leyendo `backend/domain/review.py`.

**Dictamen:** **no es un bucle técnico**, es una **semántica no declarada**. El rótulo «Repasar
hoy» invita a leer «esto cancela lo de hoy», y no lo hace. Se elige la lectura **competencia**
(«Repasar hoy **trabaja competencia**; **no** consume vencimiento FSRS») y se escribe en la letra.
Severidad **P1** porque una promesa implícita incumplida es lo que este proyecto llama
«mentir en la letra», y aquí no había letra.

### D4 — El panel APRENDER → Vocabulario se quedó **sin ninguna vía al repaso** · 🟠 **P1 (regresión)**

`v3.85.0` retira `<ReviewQueueSection>` del inventario y el panel incrustado
(`VocabularyRoutesPractice` → `QuizRoutePage`) **pierde el drill de repaso**. El PARKED lo declara
como decisión («el estudio vive en Flashcards»), pero el efecto neto para quien trabaja desde
APRENDER → Vocabulario es **una capacidad menos y ninguna puerta**: no hay CTA, ni enlace, ni
proyección. La decisión es defendible; **quedarse sin salida no**. La pregunta `F4` del encargo
—«¿es aceptable, o el panel debería ofrecer al menos un enlace?»— se responde con **sí, debe
ofrecerlo**: es exactamente la clase de regresión que una release no debe introducir mientras se
presenta como «menos ruido».

### D3 — El límite de la cola pasó de **20 → 50** y el tag no lo declara · 🟠 **P2 (letra + UX)**

`useReviewToday` pide `REVIEW_LIMIT = 50` (= `REVIEW_QUEUE_MAX_LIMIT`); `ReviewQueueSection`
(retirada) llamaba sin límite y aplicaba `REVIEW_QUEUE_DEFAULT_LIMIT = 20`. Como
`due_count = len(served_items)`, **el N del botón y la longitud de la sesión pueden pasar de 20 a
50**. Las notas de `v3.85.0` §3 describen el «antes» y **no declaran el cambio**, así que la cifra
del botón cambia de escala sin letra que lo respalde. El **coste** no declarado es el que importa:
hasta **50 ítems con un clic obligatorio por ítem** y **sin estado persistido** (salirse la pierde
entera). Severidad **P2** por letra, **P1** por UX; se declara y se decide (ver `§9`).

### G3 — El artefacto de contraste **no identificaba la release** · 🟠 **P2 (instrumento)**

`docs/audit/generated/contrast-report.json` de `v3.85.0` declaraba:

```json
{ "audit": "V3.75.8-rampa-niveles-direccion", ... }
```

El sello estaba **en duro** en `frontend/scripts/contrast_audit.mjs`. La consecuencia es la que
importa y la pregunta `G3` del encargo la formuló bien: el informe mide **480 pares + 6 guardas**
igual que en `v3.75.8`, así que **un artefacto correcto y otro viejo son indistinguibles por su
cabecera**. No es que el cálculo esté mal —las 17 incidencias de acento reportadas son las
mismas—: es que **la cifra no se puede atribuir a la release auditada**. Y sobre la letra: los
rótulos nuevos («Mi léxico», «Repasar ahora (N)», «Estudiar tarjetas (N)», «Práctica oral»)
**reutilizan pares ya medidos** (tipografía base sobre superficie y acento), así que «0
bloqueantes» **sí** dice algo de ellos —pero solo si el artefacto declara de dónde viene—.

### A11y — El contador de la sesión no se anunciaba y el CTA no recibía el foco · 🟠 **P2**

Pregunta `D4` del encargo. En `v3.85.0` el contador `{index} de {total}` era un `<span>`
puramente visual —sin `role="status"` ni `aria-live`— y «Siguiente palabra»/«Terminar» aparecía
**sin mover el foco**: un usuario de teclado debía tabular por todo el drill hasta el final para
avanzar, y el progreso de la sesión no se anunciaba a un lector de pantalla. En una release cuyo
argumento central es «la cola se maneja como una sesión», la sesión **no era navegable**.

### D2 — Las notas nombran un `ReviewTodayCard` que **no existe** · 🟡 **P3 (documental)**

`release-notes-v3.85.0.md` §3 describe el resumen como `ReviewTodayCard`. No hay ningún componente
con ese nombre: el resumen se renderiza **en línea dentro de `StudyTab`** y su estado vive en el
hook `useReviewToday`. No falta producto; falta precisión en la letra.

### Otros puntos comprobados (sin hallazgo)

| Punto | Veredicto | Evidencia |
|---|---|---|
| `v3.84.1` — estado parcial + reintento de la tarjeta | **Correcto** | la opción A (dos escrituras + estado parcial + reintento) está implementada y su E2E cubre los cuatro desenlaces; el `400 DECK_NAME_TAKEN` es un **código máquina**, no texto para el alumno |
| `E4` — `FlashcardsScreen` es pestaña controlada | **Premisa confirmada** | `git grep "<FlashcardsScreen" v3.85.0 -- frontend/src` → **un solo montaje** de producto (`DictionaryScreen.tsx:207`) |
| `F3` — no quedan referencias vivas a `PersonalDictionary` en producto | **Confirmado** | las 5 apariciones en `frontend/src` son **comentarios** (`wordDrill.tsx`, `DictionaryLookup.tsx`, tests) |
| `C4` — decisiones `served`/`started` huérfanas al cerrar la sesión | **Sin dato sucio** | la FSM declara `served → abandoned` y `started → completed/abandoned`, y hay **barrido de higiene** que cierra como `abandoned` las decisiones que quedaron abiertas (`backend/domain/review.py:60,99,172`) |
| `G4` — i18n: prefijos dinámicos | **Sin rotura** | **80** prefijos dinámicos y **0** claves usadas sin definir, que es el guardián real (`check_i18n_coverage.py --strict`) |
| `A4` — desfase post-tag del punto de entrada | **Correcto y verificable** | `git log --oneline v3.85.0..main` → **1** commit documental (`6098d88`); los tags no se reescriben |
| `G1` — el candado documental | **Vivo, no reverificado aquí** | `backend/tests/test_docs_drift_v372.py` existe y `len(GATES) == 8` lo comprueba la batería; el experimento de «borrarlo y ver si falla» **no** se ejecutó en este informe |

---

## 4. Verificación declarada por las releases vs. reproducida

| Comprobación | `v3.84.1` (declarado) | `v3.85.0` (declarado) | Reproducido aquí |
|---|---|---|---|
| `npx tsc --noEmit` | limpio | limpio | limpio (108 ficheros, 0 errores) |
| `npm run test` (vitest) | 1038/1038 | 1041/1041 | **1048/1048** (109 ficheros) tras `v3.85.1` |
| `pytest` backend | 3141/3141 | 3141/3141 | **3141/3141** |
| `ruff` | limpio (backend + lanzador) | limpio (backend + lanzador) | limpio en el mismo alcance; **1 hallazgo preexistente** en `scripts/purge_virtual_testers.py:198` con `ruff check .` desde la raíz — ver `§9-H` |
| i18n `--strict` | 1785 cadenas | 1774 cadenas | **1776** cadenas, 0 huérfanas / 0 usadas sin definir / 0 duplicadas |
| contraste `--strict` | 480 + 6 / 0 bloqueantes | 480 + 6 / 0 bloqueantes | **480 + 6 / 0 bloqueantes**, `audit: V3.85.1-contraste-wcag` |
| `check_release_consistency.py` | OK (6 orígenes) | OK (6 orígenes) | OK en los **6 orígenes** (`3.85.1`) |

> **Que `pytest` dé el mismo número en las dos releases es correcto** y no un copia-pega: `v3.85.0`
> solo toca un test de backend, el candado documental. La lectura contraria —«misma cifra ⇒ no se
> ejecutó»— es precisamente la que un auditor debe descartar con el `git diff`, no con la intuición.

---

## 5. Matriz de cierre (§3 del encargo)

| # | Área | Veredicto | Evidencia (comando + salida) |
|---|---|---|---|
| A | Ancla, arco y promesa | **Cumple con matiz** | tags anotados y rangos limpios; el punto de entrada es post-tag y verificable (`v3.85.0..main` = `6098d88`); `v3.84.1` nació **sin encargo propio** (`D1`/`D5`: política de cola, no defecto del patch) |
| B | `v3.84.1`: estado parcial y duplicado | **Correcto** | `git diff --numstat v3.84.1^..v3.84.1 -- backend` = `1/1` + `10/0` (docstring) + `6/1` (un `detail`) + `23/0` (test); el E2E cubre los cuatro desenlaces |
| C | `v3.85.0`: «Repasar hoy» como acción **[NÚCLEO]** | **NO CUMPLE en la forma publicada** | **C1 (P0)**: `ReviewToday.tsx` usa `{produced ? (` y `wordDrill.tsx` solo dispara `onProduced` en **3** de **5** peldaños; el fixture del E2E sirve todo como `activity: "write"` |
| C2 | «Repasar hoy» y el vencimiento FSRS | **Semántica no declarada** | la sesión no reprograma la carta; `due_count = len(served_items)` en `backend/domain/review.py` ⇒ el `N` puede reaparecer |
| D | Sesión encadenada: modos de fallo | **Falla en accesibilidad y avance** | `D4` (a11y) confirmado por lectura del render; el modo de fallo catastrófico es `C1` |
| E | Dos pestañas y proyección de la persistencia | **Cumple** | `FlashcardsScreen` con **un solo** montaje de producto; `"personal"` sigue vivo como valor persistido y la clave i18n `dictionary.tabs.personal` murió |
| F | Retiradas: inventario y panel incrustado **[NÚCLEO]** | **Cumple con una regresión** | `PersonalDictionary` solo sobrevive en **comentarios**; el panel incrustado **pierde el repaso sin ninguna puerta** ⇒ **D4 (P1)** |
| G | Instrumento: i18n, responsive y candados | **Falla en atribución, cumple en cobertura** | **G3 (P2)**: el sello del informe de contraste estaba en duro (`V3.75.8-…`); i18n **80** prefijos dinámicos y **0** claves sin definir |

**Verificación del núcleo (`C1`) — el experimento que decide el dictamen:**

```
git show v3.85.0:frontend/src/features/vocabulary/ReviewToday.tsx  →  {produced ? (
git show v3.85.0:frontend/tests/visual/reviewSession.spec.ts       →  activity: "write" (×2)
```

Con el fixture en `recognition`, la sesión **no avanza**: es el modo de fallo que el encargo pedía
buscar y que este informe **reproduce por comando** en `§9` (una vez corregido, desactivando el
arreglo).

---

## 6. Evidencia nueva producida por este informe

1. **La sonda de los cinco peldaños.** `frontend/tests/visual/reviewSession.spec.ts` gana un caso
   que recorre **Recognition, Recall, Sentence** (con micrófono falso), **Write** y **Transfer**,
   exigiendo que la sesión **avance en cada uno**. Es la guardia que el fixture original no podía
   dar y **falla si la sesión se vuelve a atar a `onProduced`**.
2. **La reproducción del P0.** Desactivada la corrección, el caso falla en
   `reviewSession.spec.ts:502` (`Next word` no visible tras el veredicto de Recognition); restaurada,
   pasa. Queda registrado en `§9` con la imagen del fallo.
3. **La sonda de teclado/foco** de la sesión: región viva del contador y foco en el CTA,
   verificado en E2E además de en unitario.
4. **La medición del sesgo de fixture**: `activity: "write"` en el **100 %** de los ítems del E2E
   y de `ReviewToday.test.tsx`. No es una opinión: está en el fichero.

---

## 7. Declaraciones de honestidad (§5 del encargo)

1. **Este informe se escribe DESPUÉS de que exista la corrección.** El arco se auditó sobre
   `v3.85.0`; `v3.85.1` es **posterior** y su disposición va en un addendum (`§9`), no en el
   cuerpo. Un lector debe poder distinguir «lo que estaba mal en el tag» de «lo que se hizo con
   ello».
2. **No reverifiqué el CI contra GitHub.** Los runs de `5bc9050` y `b1b502f` están **declarados**
   en el encargo; este informe no los comprueba y lo dice (invariante 9).
3. **No ejecuté todos los experimentos que el encargo propone.** `B1` (hacer que la guardia del
   estado parcial muerda), `B2` (doble clic en el reintento) y `G1` (borrar el candado documental)
   quedan **declarados como no ejecutados aquí**. Lo que no se probó, no se firma.
4. **La severidad `P0` es una decisión, no una medida.** La justifico: la función central de la
   release no funcionaba en el camino que el planner elige por defecto, y su guardia era ciega.
5. **El informe no certifica nada.** Los ocho gates siguen `pending`, `validation-evidence.json`
   no existe y el ancla sigue en `v3.83.1`.
6. **La corrección `v3.85.1` no arregla todo lo que este informe declara.** El techo de 50 ítems
   con un clic obligatorio y sin reanudación **sigue sin resolverse**: se declara y se aparca
   (§9-F), no se cierra.

---

## 8. Veredicto

> **No aprobado en su forma publicada (`v3.85.0`). Aprobado con matices tras `v3.85.1`.**

La release se publica con su función central —«la cola del día pasa a ser una sesión que se
maneja»— **clavada en los peldaños que el propio planner recomienda** (`C1`, P0), y la guardia que
debía protegerla **probaba un subconjunto elegido por comodidad**. Alrededor hay tres defectos de
promesa (`C2` semántica no declarada, `D3` cambio de escala sin letra, `D4` capacidad retirada sin
puerta), un defecto de instrumento (`G3`, artefacto sin sello) y un defecto de accesibilidad
(`A11y`). Nada de eso es cosmético: los cuatro primeros son **promesas que la letra o la UI hacían
y no se cumplían**.

La corrección `v3.85.1` cierra `C1` (con guardia que muerde y reproducción del fallo), `A11y`,
`D4`, `G3`, y **declara** `C2`, `D2` y `D3` con decisión escrita. Con eso el arco pasa a
**aprobado con matices** —los matices son el techo de 50 sin resolver y la cola de auditoría
atrasada (`AV`, `AW`, `AX`)—.

**Lo que este arco enseña, y por eso está en el veredicto:** un E2E verde y 1041 unitarios verdes
**no** son evidencia de corrección si el fixture elige el caso que hace verdadera la premisa. La
lección no es «añadir un test»: es que **la guardia de un contrato tiene que recorrer el dominio
del contrato**, no el subconjunto cómodo.

---

## 9. Addendum (2026-09-26) — disposición de los hallazgos en `v3.85.1`

> `v3.85.1` es una release **posterior** al tag auditado. Este addendum es su disposición, **no**
> parte del cuerpo del informe: el cuerpo describe lo que estaba en `v3.85.0`.

**A · `C1` (P0) — cerrado, con guardia que muerde.** Se separan dos señales que estaban
confundidas: **`stepCompleted`** (`onStepCompleted`, nuevo — el peldaño dio **veredicto**, apruebe
o falle → es la puerta del avance) y **`produced`** (`onProduced`, **sin cambios** — acredita
**evidencia productiva** y sigue reservado a `sentence`/`write`/`transfer`). Completar un peldaño
reconductivo **avanza sin fabricar evidencia**: el arreglo no hace que Recognition y Recall
mientan. El veredicto se declara **una sola vez por palabra** (idempotente por montaje).

*Reproducción (el experimento que §5 del encargo pedía):* desactivado `onStepCompleted` en
`ReviewToday.tsx` y ejecutado el caso nuevo de los cinco peldaños:

```
npx playwright test reviewSession.spec.ts --project=desktop -g "cinco pelda"
#  Error: expect(locator).toBeVisible() failed
#  >  502 |  await expect(page.getByRole("button", { name: "Next word" })).toBeVisible({
#  1 failed
```

Restaurado:

```
#  ok 1 [desktop] › la sesión avanza en los cinco peldaños (V3.85.1, C1) (2.7s)
#  1 passed
```

El fallo ocurre **exactamente** en el punto que `§3-C1` predijo: tras el veredicto de Recognition,
«Next word» no existe. La guardia **muerde**.

**B · `C2` — semántica fijada en la letra.** «Repasar hoy» **trabaja competencia; NO consume
vencimiento FSRS**. El contador puede reaparecer tras una sesión completa y **eso no es un bucle**.
Declarado en `release-notes-v3.85.1.md §5` y en `docs/audit/PARKED.md §V3.85.1`.

**C · `D4` — cerrado con un CTA, no con una sesión duplicada.** `RouteQuizConfig` gana
`reviewCta`; `VocabularyRoutesPractice` lo declara y el panel incrustado muestra **un solo botón**
que proyecta `"flashcards"` y navega a `#/diccionario` (Flashcards → Estudiar). Caso E2E nuevo en
`vocabularyRoutesReview.spec.ts`.

**D · `A11y` — cerrado.** Contador como **región viva** (`role="status"` + `aria-live="polite"` +
`aria-atomic="true"`) y **foco al CTA** al aparecer. Sonda E2E de teclado/foco nueva.

**E · `G3` — cerrado.** `contrast_audit.mjs` deriva `audit` y `version` de
`frontend/package.json`; el informe regenerado declara `audit: "V3.85.1-contraste-wcag"` y
`version: "3.85.1"`.

**F · `D3` — declarado y decidido.** El paso 20 → 50 queda escrito (con la errata `E2` en
`release-notes-v3.85.0.md`, porque **el tag no se recrea**) y con **decisión de UX**: el techo de 50
es el máximo del endpoint, no una medida de carga razonable por sesión; hasta 50 ítems con un clic
obligatorio y sin reanudación ⇒ **segmentar la sesión queda aparcado** en
`docs/audit/PARKED.md §V3.85.1`, no cerrado.

**G · `D2` — declarado.** El `ReviewTodayCard` inexistente queda como errata `E1` de
`release-notes-v3.85.0.md`.

**H · Hallazgo preexistente declarado, no silenciado.** `python -m ruff check .` **desde la raíz**
del repositorio reporta **1** hallazgo (`scripts/purge_virtual_testers.py:198`, `DTZ005`). El
fichero es **idéntico al del tag** (`git diff v3.85.0 HEAD -- scripts/purge_virtual_testers.py`
vacío), así que **no lo introduce este arco**; el alcance de ruff que el proyecto declara es por
paquete (`backend`, `launcher`, cada uno con su `pyproject.toml`) y ese alcance pasa limpio. Se
declara en vez de arreglarse en silencio: no pertenece al alcance quirúrgico de la corrección.

**Verificación de `v3.85.1`:** `tsc --noEmit` limpio · `vitest run` **1048/1048** (109 ficheros) ·
`pytest` backend **3141/3141** · `ruff` limpio (backend + lanzador) · i18n `--strict` **1776**
cadenas con 0 huérfanas / 0 usadas sin definir / 0 duplicadas · contraste `--strict` **480 + 6 / 0
bloqueantes** · `npm run build` correcto · `validation_gate.py auto --require-dist` **10/10**
(8 gates) · **barrido Playwright completo (26 ficheros): 106 passed · 0 failed** ·
`check_release_consistency` OK en los **6 orígenes** (`3.85.1`); dentro de ese barrido,
`reviewSession.spec.ts` **3/3** en desktop (incluida la guardia del P0 y la sonda de teclado) y
`vocabularyRoutesReview.spec.ts` **2/2** en desktop (incluido el CTA de `D4`).

---

## 10. Reproducir / verificar

```bash
# --- ancla y arco -------------------------------------------------------------
git rev-list -n 1 v3.84.1 && git rev-list -n 1 v3.85.0
git cat-file -t v3.84.1 && git cat-file -t v3.85.0        # 'tag' en los dos
git log --oneline v3.84.1..v3.85.0                        # UN commit (b1b502f)
git diff --name-only v3.84.1..v3.85.0 -- backend          # VERSION + candado documental
git diff --name-only v3.84.0..v3.85.0 -- backend/db.py    # (vacío: sin migración)

# --- C1: la lectura que lo demuestra ------------------------------------------
git show v3.85.0:frontend/src/features/vocabulary/ReviewToday.tsx | Select-String "produced"
git show v3.85.0:frontend/src/features/vocabulary/wordDrill.tsx | Select-String "onProduced\(\)"
git show v3.85.0:frontend/tests/visual/reviewSession.spec.ts | Select-String "activity"

# --- C1: el experimento (desactivar el arreglo y ver romper) -------------------
#  comentar onStepCompleted en ReviewToday.tsx y ejecutar:
npx playwright test reviewSession.spec.ts --project=desktop -g "cinco pelda"   # 1 failed
#  restaurarlo:
npx playwright test reviewSession.spec.ts --project=desktop                    # 3 passed

# --- C2: la semántica ---------------------------------------------------------
git show v3.85.0:backend/domain/review.py | Select-String "REVIEW_QUEUE_(DEFAULT|MAX)_LIMIT"
git grep -n "REVIEW_LIMIT" v3.85.0 -- frontend/src

# --- G3: el sello del artefacto ----------------------------------------------
Get-Content docs/audit/generated/contrast-report.json -TotalCount 3

# --- la batería (alcance del proyecto) ---------------------------------------
cd frontend && npx tsc --noEmit && npx vitest run
cd ../backend && python -m pytest -q
cd .. && python -m ruff check backend launcher
python scripts/check_i18n_coverage.py --strict
node frontend/scripts/contrast_audit.mjs --strict
python scripts/check_release_consistency.py
```

---

## 11. Anexo — prefijos y cierre

`AY` es el primer prefijo libre tras `AA`–`AX`. Con `AY` **dictaminado**, la cola queda:

| Prefijo | Arco | Estado |
|---|---|---|
| `AU` | `v3.81.2..v3.83.0` | dictaminado |
| `AV` | `v3.81.2..v3.82.0` (contrato + migración) | **pendiente — la mayor deuda** |
| `AW` | cierre V3.83.x | pendiente |
| `AX` | `v3.83.1..v3.84.0` | pendiente |
| `AY` | `v3.84.0..v3.85.0` | **dictaminado (este informe)** |

**Cierre.** El arco publicó dos releases etiquetadas y limpias en su mecánica —tags anotados,
subrangos separados, sin migración, sin contrato roto, letra verificada— y falló en **la promesa
central de la minor**, protegida por una guardia ciega por fixture. La corrección `v3.85.1` cierra
el P0 con la lección dentro: **la guardia de un contrato recorre el dominio del contrato.** Lo que
sigue abierto —el techo de 50 sin reanudación y la cola `AV`/`AW`/`AX`— queda escrito aquí y en
`docs/audit/PARKED.md §V3.85.1`.
