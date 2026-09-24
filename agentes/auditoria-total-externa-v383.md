# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.83.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **la release
> Diccionario → Flashcards y la sesión de estudio tipo juego**: la release que hace
> **visible** el vínculo «todo uno» entre lo que se busca en el diccionario y las
> palabras que se estudian en PERSONAL, y que rediseña la sesión de estudio para que
> parezca un juego. La revisión es **de solo lectura**: no se cambia código, datos,
> configuración ni etiquetas publicadas.
>
10|> **Por qué esta auditoría y por qué ahora.** Porque es la primera release de la
> serie que **promete algo sobre el significado de los datos del alumno** —«esto es
> una palabra en aprendizaje y sigue el proceso de estudio completo»— usando
> **código que ya existía**. Esa es exactamente la clase de promesa que se cuela sin
> auditoría: no hay endpoint nuevo que mirar, no hay migración que revisar, y aun
> así el producto **afirma** una equivalencia. La pregunta central de este documento
> no es «¿compila?», es **«¿es verdad lo que la pantalla dice?»**.
>
> **Aviso de encuadre (léelo antes de puntuar).** Esta release es **pequeña y
> frontend**, y por eso invita a una auditoría blanda. No la hagas: **18 ficheros,
20|> +877/−92**, de los cuales **5 son de producto** (`frontend/src`) y **2, pruebas**.
> El backend cambia **una sola línea** (`VERSION`). El riesgo de esta release **no
> está en lo que ejecuta, está en lo que declara**, y las preguntas del §2-B existen
> para que la equivalencia «añadir desde el diccionario = palabra en aprendizaje» se
> compruebe **en el código**, no en las notas.
>
> **Continuidad con el punto de entrada anterior.** `agentes/auditoria-total-externa-v3812.md`
> **no se retira**: cubre el cierre de G0 (privacidad del historial, orden del evento
> de purga, migración heredada) con **siete invariantes y siete áreas de preguntas**.
> Este documento cubre **solo el delta `v3.82.0..v3.83.0`** y **no repite** aquellas
>30|> preguntas: las hereda. Y hay un eslabón que **falta y se declara** (§6-D1): el arco
> `v3.81.2..v3.82.0` —que **sí** cambia el contrato de la API y **sí** migra la BD—
> **no tiene punto de entrada propio**.
>
> **Estado del punto de entrada:** entregado 2026-09-24 en un **commit documental
> POSTERIOR al tag `v3.83.0`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md`). El ancla sigue siendo `v3.83.0` y el
> producto **no se mueve** para entregar esto; el invariante que lo demuestra está
> declarado y se comprueba por comando (§1.1, invariante 6).
>
40|> **Informe esperado:** `docs/audit/AU-AUDITORIA-TOTAL-V383.md`. Prefijo **`AU`**
> porque **es el primer prefijo libre**: `AA`–`AF` los ocupan los dossiers de V3.70,
> `AG`–`AM` la serie de pausa pedagógica y psicometría, `AN` el arco de `v3.75.1`,
> `AO` la política psicométrica de V4.0, y **`AP` (`v3.75.7`), `AQ` (`v3.77.1`),
> `AR` (`v3.80.0`), `AS` (`v3.81.1`) y `AT` (`v3.81.2`) siguen reservados por puntos
> de entrada sin informe recibido**. Ver la nota de prefijos en §8.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

50|
1. `docs/RELEVO.md` — **cabecera** (§0 «START HERE»), y en particular la **nota
   `V3.83.0`**.
2. `release-notes-v3.83.0.md` — las notas **de la release que se audita**. Es el
   cuerpo del asunto y está escrita para ser leída en contra: su §5 «Honestidad»
   enumera lo que la release **no** hace, y cada punto es una pregunta encubierta.
3. `frontend/src/features/vocabulary/DictionaryLookup.tsx` — **el núcleo de la
   promesa**: el panel «Añadir a Flashcards», el selector de lista y el estado
   «ya está en tu léxico».
4. `frontend/src/features/vocabulary/StudySession.tsx` — el rediseño de la sesión:
60|   volteo 3D, barra de progreso, notas con atajo y cierre con acierto.
5. `frontend/src/components/ui/progress.tsx` — **el arreglo de accesibilidad**: el
   `value` que antes no llegaba a la raíz de Radix y dejaba `aria-valuenow` sin
   pintar.
6. `frontend/src/utils/i18n.ts` — las **12** cadenas nuevas/actualizadas, en `en` y
   `es`.
7. `frontend/src/api/vocabulary.ts` (`addVocabularyItem`) y
   `backend/routers/vocabulary.py` (`add_vocabulary_item`) — **lo que NO se tocó**, y
   que es donde vive la equivalencia que la UI promete (alta → léxico + carta FSRS).
   La vista del léxico que sostiene el «mazo automático» está en
   `backend/repositories/flashcards.py` (`AUTO_DECK_ID`) y se consume en
   `backend/domain/flashcards.py`.
70|8. `frontend/src/features/vocabulary/DictionaryLookup.test.tsx` y
   `StudySession.test.tsx` — **los 14 casos nuevos**.
9. `docs/audit/KIT-VALIDACION-GATES.md` — la sección del gate **`G0 ·
   identidad-cuentas`**: sigue `pending` y esta release **no lo toca**.
10. `CHANGELOG.md` (la entrada `3.83.0`) y `docs/audit/TEMPLATE.md` (formato del
    informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
```

---

## 0.1 El rango es LIMPIO (un solo commit), y eso es distinto del documento anterior

Al revés que el punto de entrada de `v3.81.2` —cuyo rango arrastraba un commit
documental heredado y hubo que avisar de ello—, aquí el rango tiene **un solo
commit** y **es** el release:

```bash
git log --oneline v3.82.0..v3.83.0
# e05b3dd release(v3.83.0): diccionario a Flashcards y sesion de estudio tipo juego
```

No hay trampa de rango que declarar. **Lo que sí hay es una trampa de cola
posterior al tag**, y es nueva respecto a los documentos anteriores:

```bash
git log --oneline v3.83.0..main
# fd086e8 test(visual): fija workers en serie para evitar falsos negativos por contencion
# 240e5c9 docs(audit): documenta el relevo de v3.82.0 y v3.83.0 y parkea la deuda de la release visual
```

`240e5c9` es **documental** (el patrón conocido: la cola de documentación detrás de
un tag no se congela por SHA). `fd086e8` **no lo es**: toca
`frontend/playwright.config.ts`, que **no acaba en `.md`**. Es el **arnés de E2E**,
no producto, y se declara en §1.1 (invariante 6) y §6-D3 con su pregunta.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.83.0`.** Los identificadores se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.83.0            # objeto del tag anotado
git rev-parse 'v3.83.0^{commit}' # commit de release (el SHA exacto que se audita)
git rev-parse 'v3.82.0^{commit}' # commit del tag anterior (base del delta)
git log -1 --format='%H %s' 'v3.83.0^{commit}'
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run que dispara su push:
  son datos que solo existen **después** de publicar. El ancla es el **tag**, el
  estado de publicación se **verifica por comando**, y este archivo es coherente
  **dentro de su propio tag**. Si un documento de este tipo vuelve a fijar un SHA o
  un run a mano, es una **regresión**.
- **Base de comparación:** `v3.82.0`. **Ojo:** el arco inmediatamente anterior
  (`v3.81.2..v3.82.0`) **no tiene punto de entrada** y **sí era grande** (contrato +
  migración): ver §6-D1. Este documento **no lo cubre**.
- **El árbol de certificación NO se mueve con esta release.** Los gates siguen
  anclados donde estaban y aquí **no se re-anclan**: `v3.83.0` no cambia el contrato
  ni el currículum. Sigue habiendo **ocho** gates, todos `pending`.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Esta release es **frontend**: **5 ficheros de producto** en `frontend/src` con
**+515/−77**, **2 ficheros de prueba** con **+182/−0**, la **versión** en tres
sitios (`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
**+4/−4**) y **documentación/generados** (**8 ficheros, +176/−8**). Se declaran
**siete invariantes**, cada uno con el comando que lo comprueba. Todos se han
ejecutado **antes** de entregar este documento.

**(1) El backend no cambia de comportamiento: UNA línea, y es la versión.**

```bash
git diff v3.82.0..v3.83.0 -- backend/
# -VERSION = "3.82.0"
# +VERSION = "3.83.0"
```

Debe salir **exactamente eso, y nada más**. **Aviso para no confundir «solo
frontend» con «cero cambios en `backend/`»:** la release se declara **SOLO
FRONTEND**
(`release-notes-v3.83.0.md` §5.1) y es correcto **en el sentido de que no hay lógica
de backend, ni ruta nueva, ni migración**; lo que sí hay es el **bump de `VERSION`**,
que vive en `backend/config.py`. **Lo falsaría:** cualquier línea de `backend/` que
no sea esa (sería **P0**).

**(2) Sin DDL nuevo: cero migración.**

```bash
git diff v3.82.0..v3.83.0 -- backend/repositories backend/repositories/db.py \
  | grep -E '^\+.*(ALTER TABLE|CREATE TABLE|CREATE INDEX|CREATE UNIQUE INDEX)'
git diff --stat v3.82.0..v3.83.0 -- backend/repositories      # VACÍO
```

Debe salir **vacío**. Una BD de `v3.82.0` se abre intacta. **Lo falsaría:** cualquier
línea de salida (**P0**).

**(3) Sin bumps pedagógicos ni de instrumento.** La **única** línea que cambia de
versión en `backend/config.py` es `VERSION`:

```bash
git diff -U0 v3.82.0..v3.83.0 -- backend/config.py \
  | grep -E '^[+-].*(VERSION|GENERATOR_VERSION|DECISION_POLICY|CURRICULUM_VERSION|LISTENING_BANK_VERSION)'
# solo: -VERSION = "3.82.0"  /  +VERSION = "3.83.0"
```

Los valores vigentes y **sin mover** son: `CURRICULUM_VERSION = "1.3.1"`,
`LISTENING_BANK_VERSION = "7.0.0"`, `GENERATOR_VERSION = "1.4.0"` y
`DECISION_POLICY_VERSION = "v3.68.0"`. **Aviso para no confundir una cita con un
cambio:** `CHANGELOG.md`, `PLAN.md` y las notas **sí** nombran esas constantes; lo
que este invariante acota es el **diff de `backend/config.py`**.

**(4) El contrato de la API no crece: cero rutas nuevas.**

```bash
git diff v3.82.0..v3.83.0 -- backend/routers \
  | grep -E '^\+.*@router\.(get|post|put|patch|delete)'
git diff --stat v3.82.0..v3.83.0 -- backend/routers   # VACÍO
```

Debe salir **vacío**. **Y esto es el corazón del asunto (§2-B):** la release promete
que añadir una palabra desde el diccionario la vuelve palabra en aprendizaje
**reutilizando el endpoint que ya existía**. Si esa promesa fuera cierta **solo** con
un endpoint nuevo, este invariante la habría cazado. **Lo falsaría:** una ruta nueva,
o un **cambio de forma** en una respuesta (aunque no haya ruta nueva): eso sería
**P1**.

**(5) Currículum, evaluaciones y lanzador: VACÍO.**

```bash
git diff --stat v3.82.0..v3.83.0 -- backend/curriculum
git diff --stat v3.82.0..v3.83.0 -- launcher
git diff --stat v3.82.0..v3.83.0 -- scripts
```

Los tres deben salir **vacíos**. La release es de UI; **lo falsaría** cualquier línea
de salida (**P0** en currículum, **P1** en lanzador, porque el lanzador es donde el
webmaster **opera**).

**(6) El producto no se ha movido desde el tag — con UNA excepción declarada.**

```bash
git diff --stat v3.83.0..main -- backend frontend/src launcher scripts
```

Debe salir **VACÍO**, y sale vacío: **ningún** fichero de producto, backend,
lanzador ni script se ha tocado desde el tag `v3.83.0`. Pero el candado **fuerte**
del documento anterior —«desde el tag solo se ha tocado documentación»— **no se
cumple literalmente aquí**, y se declara en vez de esconderlo:

```bash
git diff --name-only v3.83.0..main | grep -v '\.md$'
# frontend/playwright.config.ts
```

Es el commit `fd086e8`: **solo el arnés de Playwright** (fija `workers` en serie
para eliminar falsos negativos por contención). **No es producto**, no se compila en
la app, no cambia ninguna respuesta y su run de CI está **verde**. **Lo falsaría:**
cualquier **otro** fichero no-`.md` en esa salida; y **merece dictamen** (§2-E3) si
un cambio de arnés posterior a un tag publicado debería llevar **su propio tag de
parche**, dado el precedente de `v3.73.2`.

**(7) La evidencia de los gates está a CERO.** No hay ninguna aprobación previa que
esta release pueda estar blanqueando:

```bash
ls docs/audit/validation-evidence.json    # NO EXISTE
python scripts/validation_gate.py status  # 8 gates, los 8 en `pending`
```

`validation-evidence.json` **no existe** en el árbol, así que **ningún gate tiene un
`record`**. Si el auditor encuentra un `record` en cualquier forma (fichero, rama,
nota en un doc, captura en un informe), este invariante **cae**. Es el invariante
más importante del documento, igual que en el punto de entrada anterior.

### 1.2 Lista cerrada — el único commit del rango `v3.82.0..v3.83.0`

| # | SHA | Mensaje | Ficheros | ¿Tag? |
|---|---|---|---|---|
| 1 | `e05b3dd` | `release(v3.83.0)`: diccionario a Flashcards y sesión de estudio tipo juego | 18, +877/−92 | **`v3.83.0`** |

Y **fuera del rango, posterior al tag**: `240e5c9` (**documental**, 3 ficheros `.md`),
`fd086e8` (**el arnés**: `frontend/playwright.config.ts`), más el commit documental
que trae **este documento**. Esa cola **no se congela por SHA a propósito**: se
congela por *invariante*:

```bash
git diff --stat v3.83.0..main -- backend frontend/src launcher scripts   # debe salir VACÍO
```

### 1.3 Lista cerrada — el diff del arco, por área

```bash
git diff --shortstat v3.82.0..v3.83.0                  #  18 files changed, 877+/ 92-
git diff --shortstat v3.82.0..v3.83.0 -- backend       #   1 file  changed,   1+/  1-
git diff --shortstat v3.82.0..v3.83.0 -- frontend      #   9 files changed, 700+/ 80-
git diff --shortstat v3.82.0..v3.83.0 -- launcher      #  (vacío)
git diff --shortstat v3.82.0..v3.83.0 -- scripts       #  (vacío)
git diff --shortstat v3.82.0..v3.83.0 -- '*.md'        #   6 files changed, 171+/  6-
```

Separado por naturaleza (esta es la lista **cerrada**):

```bash
# producto: 5 ficheros, +515/-77
git diff --numstat v3.82.0..v3.83.0 -- frontend/src \
  ':!frontend/src/**/*.test.tsx' ':!frontend/src/**/*.test.ts'
# pruebas: 2 ficheros, +182/-0
git diff --numstat v3.82.0..v3.83.0 -- 'frontend/src/**/*.test.tsx'
# versión: 3 ficheros, +4/-4 (backend/config.py, package.json, package-lock.json)
```

| Fichero | Δ | Qué cambia |
|---|---|---|
| `frontend/src/features/vocabulary/DictionaryLookup.tsx` | +278/−29 | el panel «Añadir a Flashcards», el selector de lista, los estados y el CTA de estudiar |
| `frontend/src/features/vocabulary/StudySession.tsx` | +177/−43 | volteo 3D, barra de progreso, notas con icono/color/atajo, cierre con acierto |
| `frontend/src/utils/i18n.ts` | +49/−4 | **12** cadenas nuevas/actualizadas, en `en` y `es` |
| `frontend/src/features/vocabulary/DictionaryScreen.tsx` | +8/−1 | conecta `onOpenFlashcards` con la vista de Flashcards |
| `frontend/src/components/ui/progress.tsx` | +3/−0 | reenvía `value` a la raíz de Radix para que `aria-valuenow` se pinte |

Y el resto del release (**13 ficheros**) es **pruebas, versión y documentación**:

| Grupo | Ficheros | Δ |
|---|---|---|
| Pruebas | `DictionaryLookup.test.tsx`, `StudySession.test.tsx` | +182/−0 |
| Versión | `backend/config.py`, `frontend/package.json`, `frontend/package-lock.json` | +4/−4 |
| Documentación viva | `CHANGELOG.md`, `PLAN.md`, `README.md`, `release-notes-v3.83.0.md` | +166/−1 |
| Generados | `docs/audit/generated/i18n-report.{json,md}`, `docs/audit/generated/release-validation.{json,md}` | +10/−10 |

**Ninguno de los tres últimos grupos es producto**, y por eso el invariante 6 los
ignora al acotar el candado a `backend frontend/src launcher scripts`.

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
git tag --list 'v3.8*'                  # v3.8.0, v3.80.0, v3.81.0, v3.81.1, v3.81.2, v3.82.0, v3.83.0
gh run list --commit <sha-de-v3.83.0>   # la run que certifica el commit del tag
gh release view v3.83.0                 # la Release publicada (cuerpo = notas)
gh api repos/jvelasca/english-tutor/releases/latest --jq .tag_name   # v3.83.0
```

| Certificación | Valor |
|---|---|
| Workflow | `CI` · evento `push` · rama `main` |
| Run del commit del tag (`e05b3dd`) | **`35995172219`** — `conclusion = success`, **12/12 jobs** |
| Run del commit documental posterior (`240e5c9`) | **`35995527317`** — `conclusion = success` |
| Run del commit del arnés (`fd086e8`) | **`35998603280`** — `conclusion = success` |
| `Playwright E2E (visual)` | ✅ verde en las tres |
| Release publicada | **`v3.83.0`** — creada el **2026-09-24**, `draft = false` · `prerelease = false`; es la que GitHub marca como **Latest** |

**Aviso de anclaje (evita auditar la versión equivocada).** Hasta el **2026-09-24**,
`v3.82.0` y `v3.83.0` existían **solo como tag**: no tenían *Release object*, así que
`/releases/tag/v3.83.0` respondía **404** y la página
[`/releases`](https://github.com/jvelasca/english-tutor/releases) anunciaba
**`v3.81.2` como «Latest»** — con un título («Cierre de G0…») que describe **dos
arcos** atrás. Un auditor que entrase por ahí habría auditado el **parche de
privacidad** creyendo que era la última release. Se publicaron **las dos** Releases
(`v3.82.0` y `v3.83.0`), con **cuerpo = `release-notes-vX.Y.Z.md`**, **idéntico al
fichero salvo la normalización `LF → CRLF`**, que es la única diferencia y no es
corrupción. Comprobado por comando:

```bash
# el cuerpo remoto y el fichero local coinciden tras normalizar saltos de línea
gh api repos/jvelasca/english-tutor/releases/tags/v3.83.0 --jq .body > /tmp/remoto.md
python -c "import io;a=io.open('/tmp/remoto.md',encoding='utf-8').read().replace(chr(13)+chr(10),chr(10)).strip();b=io.open('release-notes-v3.83.0.md',encoding='utf-8').read().strip();print(a==b)"
```

> **Trampa para el auditor de hoy en día:** si algún documento, memoria o
> automatismo cita `v3.81.2` como «la última release», es **deriva documental
> heredada** del día en que se publicó (y es correcta para su fecha). La cifra
> vigente es `v3.83.0`.

**El CI no dispara en tags** (`ci.yml` escucha `push: branches: [main]` y
`pull_request`): quien audite «el CI del tag» audita el CI del commit al que apunta.
Y **el CI de los PRs sigue rojo de forma sistemática** por `Playwright E2E (visual)`
en los PRs de Dependabot: es un hallazgo **heredado** del documento anterior (§2-F en
`agentes/auditoria-total-externa-v3812.md`) y se pregunta aquí otra vez (§2-E6),
porque **no se ha cerrado**.

---

## 2. Preguntas falsables por área

### A. El ancla, el rango y la promesa

- **A1.** ¿El rango `v3.82.0..v3.83.0` tiene **exactamente un** commit, y es el
  release? `git log --oneline v3.82.0..v3.83.0`. **Dictamina:** ¿es sano que este
  rango sea limpio mientras el anterior (`v3.81.2..v3.82.0`) arrastra **tres**
  commits documentales y **un** release de **96 ficheros**?
- **A2.** La release se declara **«SOLO FRONTEND»** y a la vez `backend/config.py`
  cambia. ¿Es honesta la etiqueta, o «solo frontend» debería decir «sin lógica de
  backend»? Contrástalo con lo que la etiqueta **sugiere** a un lector que no abra el
  diff. Invariante 1.
- **A3.** ¿La promesa «esto es una palabra en aprendizaje y sigue el proceso de
  estudio completo» **se sostiene en el código**, o es una afirmación de la UI?
  Rastréala hasta el endpoint y comprueba que el alta crea **las dos** cosas (fila de
  léxico con estado `learning` **y** carta FSRS) sin que la UI las cree por su
  cuenta. Si la UI añadiera estado local, la promesa sería **falsa tras recargar**.
- **A4.** ¿`AUTO_DECK_ID` es **realmente** una vista del léxico —y no una fila de
  mazo—, de forma que una palabra añadida al léxico **aparece sin que nadie escriba
  nada** en ese mazo? Compruébalo en `backend/repositories/flashcards.py` y en los
  puntos que lo consumen en `backend/domain/flashcards.py`. Si alguien pudiera crear
  un mazo con ese id, ¿qué pasaría?
- **A5.** ¿El README / `PLAN.md` / `CHANGELOG.md` prometen algo que el diff **no**
  hace? Contrasta **cada** cifra verificable (18 ficheros, +877/−92, 1033/1033
  vitest, 1772 cadenas i18n, 480 pares de contraste, 10/10 del arnés) con el árbol
  y con la run `35995172219`.

### B. La equivalencia «Diccionario → Flashcards → PERSONAL» (el núcleo)

- **B1.** ¿Queda **algún** camino por el que la pantalla diga «añadida y en
  aprendizaje» **sin** que la palabra esté de verdad en el léxico? Mira el camino de
  error: si `addVocabularyItem` falla **después** de pintar el éxito, ¿qué ve el
  alumno? Un «OK» optimista aquí es **P0 de confianza**, no cosmética.
- **B2.** El panel ofrece **archivar en una lista propia** (`collection_id`) además
  de dar de alta. ¿Archivar y dar de alta son **dos** operaciones, y son
  **atómicas**? Si la primera triunfa y la segunda falla, ¿en qué estado queda la
  palabra? **Dictamina** si eso puede producir una palabra «archivada que no se
  estudia».
- **B3.** Al **volver a añadir** una palabra que ya está en el léxico: ¿el alta es
  **idempotente** (no duplica) y **conserva el estado FSRS** de la carta existente,
  o la **reinicia**? Un reinicio silencioso del historial de repaso de un alumno es
  el hallazgo más grave posible de esta área.
- **B4.** La UI declara «ya está en tu léxico» y ofrece **estudiar** en lugar de
  añadir. ¿Ese `tracked` es **autoritativo del servidor** (viene del léxico) o
  depende de estado del cliente que puede quedar obsoleto? Y si dos pestañas añaden
  la misma palabra a la vez, ¿qué gana?
- **B5.** El selector de listas se filtra a **listas propias** (`user_list`). ¿Se
  filtran **en el cliente** o vienen ya filtradas? Si vienen todas y el cliente
  esconde las demás, ¿qué pasa con una petición manipulada?
- **B6.** Las **12** cadenas nuevas ¿dicen exactamente lo que el sistema hace? Lee
  `en` y `es` **por separado**: una traducción que prometa más que el original (o al
  revés) es una promesa distinta para cada idioma.
- **B7.** ¿La release introduce algún **estado nuevo** de palabra («nuevo»,
  «buscado»…) o reutiliza `learning`? Las notas dicen que **comparte la misma cola**.
  Compruébalo: si existiera un estado «nuevo» paralelo, el «todo uno» sería falso.

### C. La sesión de estudio tipo juego

- **C1.** El volteo 3D mete las caras en `span` decorativos y deja el **botón** con
  `aria-label` «Flip card». ¿El control sigue siendo **alcanzable y anunciable** por
  teclado y lector de pantalla, y el `.test.tsx` lo fija, o solo lo dice la nota?
- **C2.** `prefers-reduced-motion`: ¿apaga **el volteo y la celebración**, o solo
  alguna animación? Y con el movimiento reducido, ¿la **información** (qué cara es
  cuál, que la sesión terminó) **sigue** estando disponible, o se pierde lo único que
  la transmitía?
- **C3.** Los **atajos 1–4** para calificar: ¿se disparan cuando el foco está en un
  campo de texto o en un botón, produciendo una calificación **no intencionada**? ¿Y
  se pueden **pulsar dos veces** grados sobre la carta ya calificada (doble
  registro)? Un doble registro falsea la programación FSRS.
- **C4.** La barra de progreso: el arreglo reenvía `value` a la raíz de Radix.
  ¿`aria-valuenow` se pinta **en los extremos** (0 % y 100 %) y **con `aria-label`**,
  o queda una barra anunciada a medias? ¿Y el test comprueba el **anuncio** o solo la
  presencia del nodo?
- **C5.** El «acierto de la sesión» se define como **grados ≥ 3** sobre lo repasado.
  ¿Es una definición **declarada al alumno** o solo interna? ¿Y es la correcta para
  FSRS, donde `3 = Good` y `4 = Easy` son cosas distintas? **Dictamina** si llamar
  «acierto» a esa suma es informativo o engañoso.
- **C6.** Si la sesión se **interrumpe y se retoma** (recarga, cierre, otra
  pestaña), ¿el progreso y el acierto se calculan del estado real o de estado local
  que se reinicia? Si el marcador es local, el «acierto» puede resetearse a 0 sin que
  el alumno lo haya hecho mal.
- **C7.** ¿La celebración de cierre aparece **también** cuando la sesión tuvo **cero**
  aciertos (todas «Again»)? Un cierre que felicita un 0 % es el defecto clásico de la
  gamificación. **Dictamina** con la severidad que merezca.

### D. i18n, accesibilidad y el instrumento

- **D1.** i18n pasa de **1762** a **1772** cadenas. ¿Cero huérfanas, cero usadas sin
  definir y cero duplicadas **de verdad** —ejecutado, no citado—?
  `python scripts/check_i18n_coverage.py --strict`.
- **D2.** El contraste se declara **480 pares + 6 guardas / 0 bloqueantes**, con los
  **tonos nuevos** de los botones de nota. Ejecuta `contrast_audit.mjs --strict` y
  comprueba que los **iconos** (que son los que distinguen los grados) tienen
  alternativa no cromática para quien no distingue rojo/ámbar/verde.
- **D3.** ¿Los **generados** (`docs/audit/generated/*`) se **regeneraron** o se
  editaron a mano? Re-ejecuta `python scripts/validation_gate.py auto` y compara. Un
  informe de validación tocado a mano es **instrumento viciado**.
- **D4.** El candado `test_docs_drift_v373.py` declara **ocho** gates
  (`len(GATES) == 8`) y esta release **no lo toca**. ¿Sigue verde, y sigue siendo el
  recuento la cifra correcta tras un release que **no** añade ningún gate?

### E. Deriva documental, la cola post-tag y la señal del CI

- **E1.** La release **no** crea gate ni mueve cifras de gates. ¿Queda algún texto
  **sin fecha** que diga otra cosa sobre los gates o sobre la versión vigente?
  `git grep -n -E '3\.82\.0|v3\.82\.0' -- '*.md'` y distingue lo **fechado** (correcto
  para su fecha) de lo que describe el **estado actual** (hallazgo si difiere).
- **E2.** El punto de entrada anterior declaraba que el **invariante 6** era «desde
  el tag solo se ha tocado documentación». Aquí **no** se cumple literalmente
  (§1.1-6). **Dictamina** si la formulación nueva —acotar el candado al producto y
  **declarar** la excepción— es más honesta, o si es **rebajar el invariante para que
  encaje** (lo que §4.4 prohíbe).
- **E3.** `fd086e8` cambia el **arnés** después de un tag publicado. Existe el
  precedente de **`v3.73.2`**, que fue un **tag de parche** precisamente para
  corregir la CI de `v3.73.1`. **Dictamina**: ¿un cambio de arnés posterior a un tag
  debe llevar **su propio tag** (`v3.83.1`), o basta declararlo en el commit
  documental como se ha hecho?
- **E4.** ¿`CHANGELOG.md §3.83.0` y `PLAN.md` cierran lo que prometían **en el mismo
  commit**, o queda alguna promesa («se publicará como…») en el aire ya cumplida (o
  no)? Y `docs/audit/PARKED.md §V3.83.0`: ¿declara la deuda de la release visual con
  su **etiqueta de tipo** y **sin** presentarla como cerrada?
- **E5.** `release-notes-v3.83.0.md` §5 «Honestidad» hace **cinco** afirmaciones
  autoexculpatorias («solo frontend», «sin gamificación de datos», «el acierto es de
  la sesión», «el alta deja la palabra en `learning`», «el selector solo archiva»).
  Contradice **una** de ellas con el árbol y tendrás el hallazgo. **Es el ejercicio
  más rentable de este documento.**
- **E6.** **Heredado y sin cerrar:** `Playwright E2E (visual)` está rojo en los PRs
  de Dependabot **y** la release tocó precisamente el arnés de Playwright (la suite
  local era no determinista en paralelo: pasaba de **15** fallos a **0** al fijar
  `workers`). **Dictamina** si (a) el arreglo del arnés **reduce** el ruido de los
  PRs, (b) era la causa de los rojos, o (c) son **dos** problemas distintos que la
  casa ha juntado sin declararlo.

---

## 3. Matriz de cierre (la rellena el auditor)

| ID | Área | Dictamen (`pass`/`fail`/`no verificado`) | Evidencia (comando o fichero) | Severidad si `fail` |
|---|---|---|---|---|
| A1 | Ancla y rango (1 commit) | | `git log --oneline v3.82.0..v3.83.0` | — |
| A2 | «SOLO FRONTEND» y el bump | | `git diff v3.82.0..v3.83.0 -- backend/` | P2 |
| A3 | La promesa en el código | | `addVocabularyItem` + router de vocabulario | P0 |
| A4 | `AUTO_DECK_ID = 0` es vista | | `backend/routers/vocabulary.py` | P1 |
| A5 | CHANGELOG vs diff | | entrada `3.83.0` + run `35995172219` | P2 |
| B1 | Éxito optimista | | `DictionaryLookup.tsx` (camino de error) | P0 |
| B2 | Alta y archivo atómicos | | `DictionaryLookup.tsx` + endpoint | P1 |
| B3 | Re-alta no reinicia FSRS | | endpoint de alta + cola FSRS | P0 |
| B4 | `tracked` autoritativo | | `DictionaryLookup.tsx` + léxico | P1 |
| B5 | Filtro del selector | | `GET /api/vocabulary/collections` | P2 |
| B6 | 12 cadenas en `en` y `es` | | `frontend/src/utils/i18n.ts` | P2 |
| B7 | ¿Estado nuevo? | | modelo de léxico | P1 |
| C1 | Volteo 3D accesible | | `StudySession.tsx` + su test | P1 |
| C2 | `reduced-motion` completo | | `useReducedMotion` | P2 |
| C3 | Atajos 1–4 (foco / doble) | | `StudySession.tsx` + su test | P1 |
| C4 | `aria-valuenow` extremos | | `progress.tsx` + su test | P2 |
| C5 | Definición de «acierto» | | `StudySession.tsx` + notas §5.3 | P2 |
| C6 | Acierto con sesión retomada | | estado de sesión | P2 |
| C7 | Celebración con 0 % | | cierre de sesión | P2 |
| D1 | i18n `--strict` | | `check_i18n_coverage.py --strict` | P1 |
| D2 | Contraste + iconos | | `contrast_audit.mjs --strict` | P2 |
| D3 | Generados no editados | | `validation_gate.py auto` | P2 |
| D4 | Candado de 8 gates | | `test_validation_gate_v373.py` | P1 |
| E1 | Deriva documental | | `git grep -n '3.82.0' -- '*.md'` | P3 |
| E2 | ¿Invariante rebajado? | | §1.1-6 + `git diff --name-only v3.83.0..main` | P1 |
| E3 | ¿Arnés con tag propio? | | `fd086e8` vs precedente `v3.73.2` | P2 |
| E4 | Promesas cerradas / PARKED | | `PLAN.md`, `PARKED.md §V3.83.0` | P3 |
| E5 | Las cinco de «Honestidad» | | `release-notes-v3.83.0.md §5` | P0–P3 |
| E6 | La señal de CI en PRs | | `gh pr checks <n>` en los PRs de Dependabot | P2 |

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se recrea ningún tag, no se fuerza ningún push, no se
   reescribe historia. Si el auditor necesita una corrección, va **después** del tag,
   en un commit documental, y se declara.
2. **Nada se da por bueno por lo que diga un documento de la casa**, y eso incluye
   **estas notas**: cada cifra de este prompt se ha verificado por comando **antes**
   de entregarlo, y el auditor debe **volver a verificarla**.
3. **El ancla es el tag, no la página de Release.**
4. **Los invariantes se comprueban antes de puntuar**, y si alguno no se cumple, eso
   **es** el hallazgo: no se reinterpreta el invariante para que encaje. El
   invariante 6 de este documento tiene una **excepción declarada**; decidir si
   declararla basta **es** parte de la auditoría (§2-E2).
5. **Severidades:** `P0` = rompe una promesa de seguridad, privacidad o **de datos del
   alumno**; `P1` = engaña al operador o al alumno sobre el estado real; `P2` = deuda
   declarada o fragilidad de instrumento; `P3` = cosmético o de rastro.
6. **Una promesa de UI vale lo que vale su camino de error.** En una release que
   consiste casi toda en **decir cosas en pantalla**, un hallazgo no declarado vale
   doble.

---

## 5. Honestidad esperada del informe

El informe (`AU`) debe declarar explícitamente, aunque nadie lo pregunte:

- Que **la release no añade ninguna capacidad al backend**: el alta de vocabulario
  **ya existía** y **ya** creaba la fila de léxico y la carta FSRS. Lo que esta
  release cambia es que **se ve y se dice**. Quien venda «Diccionario → Flashcards
  como funcionalidad nueva» está vendiendo algo que ya estaba.
- Que **el «juego» no son datos**: no hay XP, niveles ni rachas —ni en la UI ni en la
  BD—, y eso era el encargo.
- Que **los ocho gates siguen `pending`** y esta release **no los toca**: no hay
  ninguna aprobación física nueva y la evidencia sigue a cero.
- Que **el arco `v3.81.2..v3.82.0` no tiene punto de entrada**, pese a ser el que
  **cambia el contrato de la API y migra la BD** (96 ficheros, +9378/−3537): es la
  deuda de auditoría más grande que este documento deja al descubierto (§6-D1).
- Que **la cola posterior al tag NO es solo documental**: `fd086e8` toca el arnés de
  Playwright (§1.1-6, §6-D3).
- Que **la señal de CI en pull requests sigue roja de forma sistemática** por
  `Playwright E2E (visual)`, y que **no** se ha cerrado desde el documento anterior.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

- **D1. Falta el punto de entrada de `v3.82.0`, y es el arco GRANDE.** Este documento
  cubre `v3.82.0..v3.83.0` (**1 commit, 18 ficheros**). El arco anterior,
  `v3.81.2..v3.82.0` —**4 commits, 96 ficheros, +9378/−3537**, con **cambio
  incompatible de contrato** (`POST /api/session` pasa de `{user_id}` a
  `{email, password}`) y **migración de BD aditiva**— **no tiene punto de entrada de
  auditoría externa**. `agentes/auditoria-total-externa-v3812.md` audita el parche de
  privacidad, **no** el alta profesional de cuentas. **Pregunta:** ¿puede declararse
  auditado el producto hasta hoy con el eslabón que más riesgo introduce **sin
  encargo**? **Dictamina** si hace falta un punto de entrada propio para `v3.82.0`
  antes de dar por cubierta la serie.
- **D2. La Release no existía y la página de Releases engañaba.** Ya se ha contado en
  §1.4: hasta hoy, `/releases` mostraba `v3.81.2` como «Latest». No es un defecto de
  esta release, es una **trampa de anclaje** que este documento declara antes de que
  la encuentre el auditor.
- **D3. La cola post-tag incluye un fichero que no es `.md`.** `fd086e8`
  (`frontend/playwright.config.ts`) se commiteó **después** del tag `v3.83.0`. Es el
  **arnés de E2E**, no producto: no se compila en la app, no cambia respuestas y su
  CI está verde. Se declara en §1.1-6 y se somete a dictamen en §2-E3, con el
  precedente de `v3.73.2`.
- **D4. El arnés local era no determinista y se ha arreglado en el mismo día.** La
  suite visual, en paralelo, producía **falsos negativos** (la app se quedaba en
  `Loading…` al competir varios workers por el arranque en frío de Vite): **15**
  fallos en frío, **0** con `workers: 1`. El arreglo fija la suite en serie. Esto
  **puede** ser la causa —o no— de los rojos de Playwright en los PRs (§2-E6): son
  **dos** observaciones y la casa **no** ha demostrado que sean la misma.
- **D5. `release-notes-v3.83.0.md §5` se autoexculpa.** Cinco afirmaciones de
  honestidad escritas por quien hizo la release. Se dejan **íntegras** y se convierten
  en el ejercicio de contradicción de §2-E5: una release que se declara honesta es
  justamente la que hay que verificar que lo es.
- **D6. La cifra de cadenas «12» de las notas no cuadra con el fichero de i18n.** Las
  notas dicen «**12** cadenas nuevas/actualizadas», pero el diff de
  `frontend/src/utils/i18n.ts` es **+49/−4** (53 líneas tocadas) y el contador global
  sube **+10** (1762 → 1772). Son tres cifras distintas de lo mismo. **Dictamina** si
  es una imprecisión de redacción o una cifra inflada; ninguna de las tres miente
  necesariamente, pero **no dicen lo mismo**.

---

## 7. Alcance

**Dentro:** el delta `v3.82.0..v3.83.0` completo —los **cinco** ficheros de producto,
los **dos** de prueba, la versión en tres sitios, la documentación viva, los
generados y las **tres** runs de CI—, con el foco en **la equivalencia que la UI
promete** (Diccionario → Flashcards → PERSONAL → FSRS) y en **la accesibilidad de la
sesión tipo juego**.

**Fuera (y se hereda):** el cierre de G0 y la privacidad del historial se auditan con
`agentes/auditoria-total-externa-v3812.md`; el cuerpo de la gestión de usuarios, con
`agentes/auditoria-total-externa-v381.md`. **Este documento no repite sus preguntas.**

**Fuera también, y declarado como deuda:** el arco `v3.81.2..v3.82.0` (§6-D1), que
**no tiene punto de entrada**.

---

## 8. Nota de prefijos y cierre

- **El primer prefijo libre es `AU`**, y **este es el punto de entrada que lo
  reserva**: el informe esperado es `docs/audit/AU-AUDITORIA-TOTAL-V383.md`.
  Reservados y **sin dictamen** a fecha de este commit: **`AP`** (`v3.75.7`),
  **`AQ`** (`v3.77.1`), **`AR`** (`v3.80.0`), **`AS`** (`v3.81.1`), **`AT`**
  (`v3.81.2`) y **`AU`** (este).
- **Cadena de puntos de entrada:** `v321` → `v322` → `v323` → `v346` → `v373` →
  `v375` → `v3751` → `v3757` → `v3771` → `v380` → `v381` → `v3812` → **`v383`**
  (este).
- **Este documento se entrega en un commit documental posterior al tag `v3.83.0`**,
  con el ancla en `v3.83.0` y **sin mover producto**: el invariante 6 de §1.1 es la
  prueba, y el auditor debe ejecutarlo antes de empezar a puntuar.
- **Lo que este documento NO es:** no es la auditoría, es el encargo. No adelanta
  veredictos, no maquilla los invariantes para que se cumplan y no promete que todo
  vaya a salir verde. La release que describe **promete una equivalencia sin escribir
  una línea de backend**, y eso —que una promesa se pueda cumplir solo con UI y aun
  así ser verificable— es justamente lo que hay que auditar.
