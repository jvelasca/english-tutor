# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.77.1`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el arco no auditado
> desde `v3.75.7`**, tal y como quedó publicado en el tag **`v3.77.1`**. La revisión
> es **de solo lectura**: no se cambia código, datos, configuración ni etiquetas
> publicadas.
>
> **Por qué esta auditoría y por qué ahora.** La última entrada externa entregada es
> `agentes/auditoria-total-externa-v3757.md` (ancla `v3.75.7`). Después de ella se
> publicaron **cuatro releases** sin punto de entrada propio: `V3.75.8` (el
> diccionario de consulta), `V3.76.0` (el PIN opcional por perfil), `V3.77.0` (la
> retención léxica **y** los perfiles con autorización del webmaster) y `V3.77.1`
> (el parche de la pantalla que moría por un campo que faltaba). Este documento
> cubre **el arco entero** con una sola etiqueta de auditoría, porque las cuatro
> releases se apoyan unas en otras y leerlas sueltas esconde las dependencias.
>
> **Aviso de encuadre (léelo antes de puntuar).** Esto **no** es la auditoría de un
> parche. Es una auditoría **de arco** sobre **10 commits** que sí cambian producto
> (backend, frontend y lanzador), y su primer commit **post-data el tag `v3.75.7`**
> (§0.1). Además, `v3.77.1` no es una release «de mejora»: es un **parche de un
> fichero** que existe **porque `v3.77.0` se publicó con un defecto real**. Las dos
> cosas se declaran aquí para que nadie cuente mal ni atribuya al arco lo que es de
> un solo parche.
>
> **Estado del punto de entrada:** entregado 2026-09-21 en un **commit documental
> POSTERIOR al tag `v3.77.1`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md` y errata §0.1 de `agentes/auditoria-total-externa-v3757.md`).
> El ancla sigue siendo `v3.77.1` y el producto **no se ha movido** para entregar
> esto; el invariante que lo demuestra está declarado y se comprueba por comando
> (§1.1, invariante 5).
>
> **Informe esperado:** `docs/audit/AQ-AUDITORIA-TOTAL-V3771.md`. Prefijo **`AQ`**
> porque es **el primer prefijo libre** (`AN` lo reservó el punto de entrada de
> `v3.75.1`, `AP` el de `v3.75.7`, `AO` lo ocupa la política psicométrica, y
> `AG`/`AH`/`AI`/`AJ` siguen reservados por puntos de entrada **sin informe
> recibido**). Ver la nota de prefijos en `PLAN.md`.

---

## 0.1 Errata heredada — el rango tiene DIEZ commits y el primero post-data el tag `v3.75.7`

> **Qué es esta nota y por qué va antes de todo.** Es la corrección de la única
> discrepancia de trazabilidad que ya sangró en la auditoría anterior, repetida aquí
> **a propósito** para que no vuelva a ocurrir: el rango `v3.75.7..v3.77.1` tiene
> **diez** commits, y **el primero de ellos no pertenece a ninguna de las cuatro
> releases**: es la **errata de la propia `v3.75.7`**. Si el auditor no lo sabe,
> cuenta once cosas donde hay diez, o atribuye a `V3.75.8` un commit que no es suyo.

**(A) La cifra correcta.** `git rev-list --count v3.75.7..v3.77.1` devuelve **`10`**.
La enumeración 1:1 con la salida de `git log` está en **§1.2**.

**(B) El primero de los diez no es de este arco.** El commit `5ae4950`
(`docs(v3.75.7): el rango tiene ocho commits (no siete) y la evidencia CI del tag
queda sellada`) toca **solo** `PLAN.md`, `agentes/auditoria-total-externa-v3757.md`
y `docs/RELEVO.md`: es **la errata de `v3.75.7`**. Post-data el tag `v3.75.7`
—porque un tag publicado no se recrea— y **no cambia producto**. Los **nueve**
commits restantes son las cuatro releases y su documentación de cierre.

**(C) La consecuencia para el encuadre.** Este arco audita **cuatro releases**, pero
su primer commit es de la release **anterior**. Es exactamente el fenómeno que
`v3.75.7` declaró y que se repite aquí: **la documentación va por delante del tag**.
La regla se mantiene: **el ancla es el tag y el estado se resuelve por comando**; un
commit documental posterior nunca cambia lo que el tag publica. Si el auditor
considera que esto invalida la lectura del arco como «cerrado», **tiene razón por
definición**, y el hallazgo es **de proceso**, no de producto.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (nota de la posición vigente) y **§0 «START
   HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. Las **cuatro notas de release**, que son el cuerpo documental de este arco:
   `release-notes-v3.75.8.md`, `release-notes-v3.76.0.md`,
   `release-notes-v3.77.0.md` y `release-notes-v3.77.1.md`.
4. `docs/audit/PARKED.md` — lo **aparcado a propósito**. Sus secciones **`V3.75.8`**
   a **`V3.77.1`** son la declaración honesta de lo que el arco **no** cierra.
5. Los dos briefings del bloque grande: `agentes/v377-personal-retention.md` (la
   retención léxica) y `agentes/v377-perfiles-webmaster.md` (los perfiles con
   autorización del webmaster), **con su §4bis** —la corrección declarada del
   diseño, que es una de las discrepancias que hay que dictaminar (§6-i)—.
6. `docs/FSRS.md` — el planificador de retención **declarado** (`FSRS-lite`,
   `2.11.0-lite`), que es lo que hace auditable «por qué toca hoy esta tarjeta».
7. `docs/audit/PLAN-P0-IDENTIDAD.md` (el P0 **sigue abierto**, con el briefing de la
   Fase 3) y `docs/audit/G7-MATRIZ-LECTURA.md` (la matriz de los nueve ejes).
8. `docs/UI_V3.1.md` §3.2–3.5 — las convenciones de UI (rampa de color, dos
   acentos, composición de la repetición, icono del desplegable) y el color por
   sentido que `V3.75.8` añade.
9. `docs/BETA_GATES.md`, `docs/audit/KIT-VALIDACION-GATES.md` y
   `docs/audit/VALIDATION-RELEASE-V373.md` — los **7 gates**: **siguen en
   `pending`**; el kit es la planilla de campo, no una validación.
10. `docs/ARQUITECTURA.md` (§«Superficie sin sesión», §«Lanzador»),
    `docs/PREMISAS.md`, `docs/CONSTITUCION_PEDAGOGICA.md`, `CHANGELOG.md` y
    `docs/audit/TEMPLATE.md` (formato del informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -3 main
```

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.77.1`** (el último del arco; `v3.77.0` y
  `v3.76.0`/`v3.75.8` están **dentro** del rango). Los identificadores exactos se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.77.1            # objeto del tag anotado
git rev-parse v3.77.1^{commit}   # commit de release (el SHA exacto que se audita)
git rev-parse v3.77.0^{commit}   # commit de la release anterior del arco
git log -1 --format='%H %s' v3.77.1^{commit}
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run de CI que dispara su
  push: son datos que solo existen **después** de publicar. Fijarlos obligaba a un
  commit de re-anclaje **posterior al tag**, que quedaba a su vez fuera del tag
  siguiente, y por eso `main` iba siempre por delante en documentación. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando** y este archivo es coherente **dentro de su propio tag**. Si un documento
  de este tipo vuelve a fijar un SHA o un run a mano, es una **regresión**.

- **Base de comparación:** `v3.75.7` (el ancla de la última entrada externa
  entregada, `agentes/auditoria-total-externa-v3757.md`). Para el arco largo,
  `v3.75.8` es además **el árbol de certificación congelado** al que se refieren
  todos los gates: **`v3.76.0`, `v3.77.0` y `v3.77.1` no lo mueven**.

- **Cuatro releases, un solo punto de entrada.** `v3.75.7` publicó cinco
  iteraciones bajo una etiqueta; este arco publica **cuatro releases bajo una sola
  etiqueta de auditoría**. `CHANGELOG.md` lleva una entrada por release y solo
  `v3.75.8`, `v3.76.0`, `v3.77.0` y `v3.77.1` tienen tag. Que `V3.75.8`… no tengan
  otra etiqueta **es una decisión declarada**, no un hueco.

- **Una advertencia de higiene que el auditor debe conocer:** el rango
  `v3.75.7..v3.77.1` contiene **diez** commits, y **el primero** (`5ae4950`) es la
  **errata de `v3.75.7`**, no de este arco (§0.1). Es la deriva que V3.73.5 declaró
  cerrada y que **aquí se declara, no se oculta**. Si el auditor considera que un
  commit documental posterior al tag lo deja desfasado, **tiene razón por
  definición**, y el hallazgo es de proceso, no de producto.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Este arco **cambia producto** (80 ficheros, +8 539 / −300), así que **el invariante
clásico de esta casa («el diff de producto sale vacío») NO se declara**: sería
falso. En su lugar se declaran **cinco invariantes acotados**, cada uno con el
comando que lo comprueba y el comando que lo **falsaría**.

**(1) El contenido de currículum y evaluaciones: VACÍO.** Ni una línea.

```bash
git diff --stat v3.75.7..v3.77.1 -- backend/curriculum/assessments.json backend/curriculum/listening_corpus.json backend/curriculum/a1.json backend/curriculum/a2.json backend/curriculum/b1.json backend/curriculum/b2.json backend/curriculum/c1.json backend/curriculum/c2.json backend/curriculum/cefr_matrix.json
```

Debe salir **vacío**. Es decir: **no se reabre nada de checks, evaluaciones ni
corpus**, y los sesgos declarados del banco siguen **exactamente** como estaban.
**Lo falsaría:** cualquier línea de salida. Sería un hallazgo **P0**.

**(2) Sin bumps pedagógicos ni de instrumento.** Ninguna línea `+`/`−` del rango
asigna ni cambia `CURRICULUM_VERSION`, `LISTENING_BANK_VERSION`, `GENERATOR_VERSION`
ni `DECISION_POLICY_VERSION`.

```bash
git diff -U0 v3.75.7..v3.77.1 -- backend | grep -E '^[+-].*(CURRICULUM_VERSION|LISTENING_BANK_VERSION|GENERATOR_VERSION|DECISION_POLICY_VERSION)' || echo VACIO
```

Debe salir **`VACIO`**. Los valores vigentes y **sin mover** son:
`CURRICULUM_VERSION = "1.3.1"` (`backend/services/curriculum.py:205`),
`LISTENING_BANK_VERSION = "7.0.0"` (`backend/services/curriculum.py:215`),
`GENERATOR_VERSION = "1.4.0"` (`backend/services/dictionary_content.py:74`) y
`DECISION_POLICY_VERSION = "v3.68.0"` (`backend/repositories/decision_records.py:61`).
**Aviso para no confundir una cita con un cambio:** el `grep` sobre `CHANGELOG.md`,
`PLAN.md` y las notas de release **sí** encuentra esas cadenas, porque las notas
**dicen** «SIN bump de `GENERATOR_VERSION`…». Son **prosa**, no asignaciones; el
comando de arriba acota a `backend` justamente para que la prosa no cuente como
cambio. **Lo falsaría:** una línea `+`/`−` en `backend` que toque una de esas
constantes.

**(3) El currículum crece en EXACTAMENTE tres ficheros nuevos, y son un alta.**

```bash
git diff --stat v3.75.7..v3.77.1 -- backend/curriculum
```

Esperado, y **nada más**: `backend/curriculum/vocab_packs/food.json`,
`.../travel.json` y `.../work.json`, **3 ficheros, +102, 0 borrados**. Son un
**alta**, no un cambio: el contenido de esos packs **no estaba en el repositorio**
(estaba en `backend/data/vocab_packs/`, **ignorado por git** — ver §2-b y la
honestidad §5). **Lo falsaría:** un cuarto fichero, una línea borrada, o un fichero
de currículum de checks/evaluaciones.

**(4) La versión de producto cambia en el triplete declarado, y solo en él.**
`backend/config.py::VERSION` (`3.75.7 → 3.77.1`), `frontend/package.json` y
`frontend/package-lock.json` (`3.75.7 → 3.77.1`).

```bash
git diff -U0 v3.75.7..v3.77.1 -- backend/config.py frontend/package.json frontend/package-lock.json
```

Esperado: **solo** las líneas `VERSION` / `"version"`. **Lo falsaría:** cualquier
otra línea `+`/`−` en esos tres ficheros.

**(5) El adendo documental no mueve producto.** Entre el tag `v3.77.1` y el commit
que **contiene este documento**, el producto no cambia:

```bash
git diff --stat v3.77.1..HEAD -- backend frontend launcher scripts
```

Debe salir **vacío**. Es el invariante que permite usar este adendo **sin inventar
una release**: el ancla sigue siendo `v3.77.1` y lo que se añade es **papel**, no
producto. **Lo falsaría:** cualquier línea de salida (significaría que el adendo no
es documental y el SHA de certificación no equivale al del tag).

### 1.2 Lista cerrada — los diez commits del rango

```bash
git log --oneline v3.75.7..v3.77.1
```

El comando imprime **diez** líneas. La enumeración, en el orden en que las devuelve
`git log` —más reciente primero—, es **esta y ninguna otra**:

| # | Commit | Qué es | Ficheros (total · **de producto**) |
|---|---|---|---|
| 1 | `52fe0db` `release(v3.77.1)` | **El commit del tag.** El parche del diccionario personal | 13 · **5** |
| 2 | `d97254c` `release(v3.77.0)` | **El commit del tag.** Retención léxica **+** perfiles con autorización del webmaster | 73 · **60** |
| 3 | `667bedf` `docs(g7)` | La matriz de lectura de los nueve ejes (para leer y firmar) | 3 · **0** |
| 4 | `d7fbfab` `release(v3.76.0)` | **El commit del tag.** El PIN opcional por perfil y G7 preparado | 41 · **28** |
| 5 | `7134e53` `docs(p0-identidad)` | Briefing de decisión de la Fase 3 y su disparador de reapertura | 2 · **0** |
| 6 | `80ab438` `docs(v3.75.8)` | La identidad del kit no puede quedar desmentida por un commit documental | 1 · **0** |
| 7 | `6e4888f` `docs(v3.75.8)` | El pre-vuelo de la campana de certificación, con el árbol congelado | 1 · **0** |
| 8 | `f9567e6` `test(v3.75.8)` | La semántica de la `X` del diccionario queda fijada por test | 3 · **1** (solo el test) |
| 9 | `c858e88` `release(v3.75.8)` | **El commit del tag.** El diccionario de consulta y la versión de compilación en la Ayuda | 27 · **14** |
| 10 | `5ae4950` `docs(v3.75.7)` | **La errata de `v3.75.7`** — post-data su tag, **no** es de este arco (§0.1) | 3 · **0** |

**Los nueve commits «del arco»** son los #1–#9: **cuatro de release** (los cuatro
tags) y **cinco de cierre documental/test** (matriz G7, briefing del P0, dos de
identidad del kit y un candado de test). El #10 **no** pertenece al arco: se
enumera porque **está dentro del rango** y el auditor lo va a ver. Si la salida de
`git log` **no** coincide línea a línea con esta tabla, es un hallazgo.

**Cómo leer la columna «Ficheros».** «Producto» = rutas bajo `backend/`,
`frontend/`, `launcher/` o `scripts/`; **incluye los tests de producto**, que en esta
casa viven dentro de esos árboles. **Los cinco commits que no tocan producto son el
#3, #5, #6, #7 y #10**; el **#8** toca **un solo test** y ningún fichero de código.
Los recuentos son **por commit** y **no suman 80**: el mismo fichero lo tocan varios
commits del arco (por ejemplo `docs/audit/PARKED.md` y
`docs/audit/generated/release-validation.*` los toca casi cada release). Los 80
ficheros de producto son la cuenta **de conjunto** (§1.3), no la suma de esta
columna.

**Cada commit toca exactamente lo que declara.** Los cinco de cierre documental
tocan **solo** `docs/`, `agentes/`, `PLAN.md` y (el #8) un test — **ningún** fichero
de producto con código. Es comprobable por commit:

```bash
git show --stat --oneline 5ae4950 7134e53 80ab438 6e4888f 667bedf f9567e6
```

### 1.3 Lista cerrada — el diff del arco, por área

`git diff --shortstat v3.75.7..v3.77.1` da **103 ficheros, +11 256 / −348**. De
ellos, **producto = 80 ficheros, +8 539 / −300** y **documentación = 23 ficheros,
+2 717 / −48**. Por área:

| Área | Ficheros | Inserción / borrado | Dónde mirar |
|---|---|---|---|
| **Backend** | 31 | +3 458 / −82 | `services/pins.py` (**nuevo**), `domain/retention.py` (**nuevo**), `domain/profile_requests.py` (**nuevo**), `repositories/collections.py` (**nuevo**), `repositories/profile_requests.py` (**nuevo**), `routers/admin.py` (**nuevo**), `schemas/profiles.py` (**nuevo**), `curriculum/vocab_packs/*.json` (**nuevos**), más `config.py`, `dependencies.py`, `main.py`, `security.py`, `repositories/{db,users,vocabulary}.py`, `routers/{users,session,vocabulary,audio_library,system}.py`, `schemas/{users,vocabulary}.py`, `services/evidence.py` y 5 tests |
| **Frontend** | 40 | +3 822 / −215 | `src/` (37: `features/vocabulary/{RetentionSession,AddVocabSection}.tsx` **nuevos**, `api/profileRequests.ts` **nuevo**, `utils/{pin,buildInfo,dictionaryDirection}.ts` **nuevos**, `components/ProfileGate.tsx`, `hooks/useChat.ts`, `app/Header.tsx`, `components/{UserMenu,ProfileDialog}.tsx`, `utils/i18n.ts`, `styles/legacy.css`…), más `scripts/contrast_audit.mjs`, `package.json` y `package-lock.json` |
| **Launcher** | 9 | +1 259 / −3 | `admin.py` (**nuevo**), `core.py`, `config_store.py`, `ui.py`, `launcher.py` y 4 tests |
| **Scripts** | 0 | — | **Nada.** El instrumento de validación no se toca en este arco |

**Frontend `src/` = 37 ficheros**; los otros **3** son `scripts/contrast_audit.mjs`
(el arnés de contraste, que `V3.75.8` extiende con las dos guardas de dirección) y el
`package.json` + `package-lock.json` (**solo** la línea `version`, por el invariante
4). Por eso la tabla dice 40: el `--shortstat` por área de `frontend` los suma, y el
desglose se declara para que el recuento no parezca arbitrario.

Cualquier ruta **fuera** de las áreas declaradas es un hallazgo. **No** se toca
`backend/data/` (`vocab_packs` **sale** de ahí), `backend/models/`,
`frontend/dist/` (no versionado) ni `scripts/`.

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
git rev-parse v3.77.1^{commit}
git rev-parse main
gh run list --commit $(git rev-parse v3.77.1^{commit}) --limit 1
```

**(a) El tag y `main`.** `v3.77.1` es un **tag anotado** (`git cat-file -t v3.77.1`
→ `tag`) y su commit **coincide con `main` en el momento de publicar**. Los cuatro
tags del arco (`v3.75.8`, `v3.76.0`, `v3.77.0`, `v3.77.1`) son anotados y están en
el remoto.

**(b) El CI NO corre en tags, y hay que saberlo para no buscar en el sitio
equivocado.** El workflow dispara con `on: push: branches: [main]`
(`.github/workflows/ci.yml:12-14`), así que **no existe una run «del tag»**: la
evidencia del tag se resuelve contra la run de `main` **del mismo commit**. El
comando de arriba devuelve la run de evento `push` de ese SHA.

**(c) La run de `v3.77.1` está en verde con los 12 jobs.** Los nombres, uno por
línea para que un `grep` literal funcione:

- `Backend (ruff + pytest)`
- `Frontend (tsc + vitest + build)`
- `Release consistency`
- `Validation gate (checks automáticos)`
- `Beta V3.0 gate`
- `Content validation`
- `Playwright E2E (visual)`
- `Launcher (ruff + pytest)`
- `Dependency audit (pip-audit + npm audit)` (**bloqueante**)
- `Product origin (UI served over HTTPS)`
- `Launcher (Windows, ruff + pytest)` (**bloqueante**)
- `Product origin (Windows, informativo)` (**informativo declarado**,
  `continue-on-error: true`)

**(d) La run de `v3.77.0` está en ROJO, y es a propósito.** Con el mismo comando
sobre `git rev-parse v3.77.0^{commit}` sale **`failure`**, con **`Playwright E2E
(visual)`** como único job rojo. **No es un accidente ni un CI poco fiable: es el
defecto que arregla `v3.77.1`**, declarado en el `CHANGELOG` y en
`release-notes-v3.77.1.md`. El auditor **debe** encontrarlo y **debe** comprobar
que la causa declarada (una respuesta sin el campo `collections` tumbaba la pantalla
entera del diccionario, §2-f) es la que explica el fallo de `drillProvenance.spec.ts`
y no otra.

**(e) No hay GitHub Release desde `v3.33.0`, y la página de Releases engaña.**
`gh release list --limit 3` devuelve `v3.33.0` como `Latest` (78 tags en el repo,
la última release publicada hace muchas decenas de tags). Es **decisión declarada
desde `v3.34.0`** — la convención de esta casa es **tag sí, Release no** —, pero
la página de Releases dice `Latest: v3.33.0` y despista. **El auditor debe entrar
por `Tags`, no por `Releases`**, o creerá que el producto se quedó en V3.33.

**(f) Consistencia de versión.** `backend/config.py::VERSION` es la fuente única
(`scripts/check_release_consistency.py`) y `3.77.1` debe aparecer en **6 orígenes**:
`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
`README.md`, `CHANGELOG.md` y `PLAN.md`.

---

## 2. Preguntas falsables por área

Cada pregunta debe responderse con **evidencia del árbol publicado**
(`archivo:línea`), **comando de reproducción** y **qué la falsaría**. Si no se puede
comprobar sin hardware o persona: **NO COMPROBABLE**.

### A. El ancla, el historial y el carril de cierre

1. ¿Se sostienen los **cinco invariantes acotados** de §1.1, y **solo** esos? ¿O hay
   algo más movido? (El clásico **no** se declara: producto = 80 ficheros,
   +8 539 / −300.)
2. **Los diez commits del rango** (§1.2): ¿es correcta la lista 1:1 con `git log`?
   ¿Y es cierto que **el primero** (`5ae4950`) es la errata de `v3.75.7` y no toca
   producto? Compruébalo con `git show --stat 5ae4950`.
3. **Cuatro releases, una etiqueta de auditoría** (§1): ¿es defendible auditar las
   cuatro juntas, habiendo cuatro tags y una sola entrada? El proyecto lo declara;
   dictamínala.
4. ¿Está `3.77.1` en los **6 orígenes** y coinciden entre sí?
5. **Este documento, ¿está dentro del tag `v3.77.1` o en un commit posterior?** Por
   diseño está **posterior** (§«Estado del punto de entrada»). Compruébalo:
   `git merge-base --is-ancestor HEAD v3.77.1` debe ser **falso**, y
   `git diff --stat v3.77.1..HEAD -- backend frontend launcher scripts` **vacío**.
   Si el auditor considera que un adendo post-tag invalida el ancla, el hallazgo es
   de **proceso**, no de producto.
6. **La página de Releases dice `Latest: v3.33.0`** (§1.4e). ¿Es suficiente la
   declaración de que «tag sí, Release no», o alguien que llegue por el navegador
   recibirá una impresión falsa? Dictamina el coste de no publicar Releases.

### B. `V3.75.8` — el diccionario de consulta y la versión de compilación

7. **Un solo `h1` en `/diccionario`.** Se declara que la vista de consulta traía su
   propia cabecera y `showHeader` (defecto `true`) la apaga en `DictionaryScreen`.
   Reproduce el conteo de `h1` en la página servida y comprueba que es **1**. Si son
   dos, la declaración es falsa.
8. **El color por sentido no es una preferencia.** Se declara que EN→ES (azul) y
   ES→EN (fucsia) **no** siguen el acento del perfil, a diferencia de la rampa de
   niveles. Revisa si hay alguna vía por la que el acento pueda cambiar esos dos
   colores; si la hay, la declaración es falsa.
9. **`directionClass()` devuelve una clase, no interpolación.** Se declara que
   devuelve `.dir-en-es` / `.dir-es-en` porque una interpolación de Tailwind sería
   purgada al compilar. **Intenta falsarlo:** busca interpolaciones de clase
   dinámica en `dictionaryDirection.ts` y comprueba que las clases existen en
   `styles/legacy.css`.
10. **El resultado no miente sobre el sentido de la consulta.** Se declara que la
    tarjeta usa `entry.direction` (el sentido **de la búsqueda**) y no el del
    conmutador activo. Comprueba que conmutar el buscador después de buscar **no**
    repinta la tarjeta. Si lo hace, es un hallazgo.
11. **La versión de la compilación que pinta la Ayuda.** `utils/buildInfo.ts` lee
    solo el campo `version` del `package.json` **en tiempo de compilación**. Se
    declara que el resto del fichero **no** entra en el bundle. Compruébalo en el
    artefacto compilado: si aparece cualquier otra clave del `package.json`, la
    declaración es falsa.
12. **La Ayuda no distingue dos compilaciones de la misma versión.** Se declara que
    muestra la versión, **no** la fecha ni el hash del build. Busca un `dist`
    recompilado con otro contenido y la misma versión: la Ayuda los pinta igual.
    El proyecto lo declara como límite, no como fallo; dictamínalo.
13. **El diccionario se queda sin spec visual permanente, y a la vez lo atraviesa
    uno.** Se declara que la medición de `V3.75.8` usó un spec **temporal** que se
    borró, de modo que una regresión de **layout** en esa pantalla solo la vería una
    revisión manual. Pero `drillProvenance.spec.ts` —**permanente y en CI**— abre el
    drill **desde la cola de repaso del diccionario**, y fue justo lo que destapó el
    fallo de `V3.77.0` (§2-46…50). Comprueba las dos cosas: (a) que **no** queda un
    spec dedicado a medir el **layout** de `/diccionario`, y (b) que el spec
    permanente **sí** pasa por esa pantalla. Dictamina la tensión: ¿la declaración
    «sin spec visual permanente» es correcta, o hay una red de seguridad **parcial**
    que el proyecto no se está apuntando?

### C. `V3.76.0` — el PIN por perfil, su freno, y lo que NO cierra

14. **Identidad:** el proyecto declara que **el P0 sigue abierto** y que el PIN es
    **opt-in**. Un perfil **sin** PIN sigue entrando sin credencial. Verifícalo:
    `POST /api/session` con un `user_id` existente y sin PIN debe abrir sesión. El
    proyecto lo declara; dictamina si «mitigación» es la palabra correcta.
15. **El PIN se guarda con hash y sal, nunca en claro.** Compruébalo en
    `backend/services/pins.py`: `pbkdf2-sha256`, `PBKDF2_ITERATIONS = 200_000`
    (`:32`), sal aleatoria por perfil. Y comprueba que **el hash no se devuelve** en
    las respuestas: `has_pin` es un booleano, no el hash.
16. **La pieza que carga el peso es el freno, no la longitud.** Se declara que 4–6
    dígitos son fuerza bruta trivial **y que el freno lo compensa**: `_FREE_ATTEMPTS
    = 5` (`:44`) y `_MAX_DELAY_SECONDS = 300.0` (`:45`). **Intenta falsarlo:** busca
    una ruta que verifique el PIN sin pasar por el freno (¿la petición de baja?,
    ¿el alta del webmaster?, ¿alguna migración?), o un caso en que el freno no
    acumule entre procesos/workers.
17. **El freno en las dos direcciones.** Se declara que sube el retardo con los
    fallos **y lo baja/limpia** con los aciertos. Verifica la segunda mitad: un
    freno que solo sube convierte una sesión legítima en un castigo.
18. **La cookie de un año es un tecleo por navegador, no autenticación.**
    Compruébalo: ¿viaja la cookie `HttpOnly`? ¿Se puede leer desde JavaScript? ¿Qué
    protege exactamente (otro equipo sin la cookie) y qué **no** (quien se sienta
    delante del tuyo)?
19. **`GET /api/users` sigue enumerando nombres** (ahora con `has_pin`). Se declara
    como consecuencia del producto sin cuentas. Compruébalo sin sesión y con
    sesión: si algún camino devolviera más que nombre y `has_pin`, es un hallazgo.
20. **`POST /api/session` con el PIN mal → `401 PIN_INVALID` sin decir «casi».**
    Y el freno activo → **`429 PIN_THROTTLED`** (`backend/routers/session.py:96,100,103`).
    Comprueba que un PIN «casi» correcto **no** recibe un mensaje distinto.
21. **La migración de una BD de `V3.75.8` sin la columna `pin_hash`.** Se declara
    `ALTER` idempotente y aditivo con `DEFAULT ''`. **Intenta falsarlo:** parte de
    una BD sin la columna, arranca y comprueba que nadie pierde el acceso.

### D. `V3.77.0` (A) — la retención léxica, y el reto central

22. **Retención ≠ dominio, y está en el código.** El evento de repaso debe entrar
    clasificado como **papel de retención** y **no** como prueba de competencia:
    `backend/services/evidence.py:955-956` (`detail.startswith("retention:")`).
    Compruébalo de punta a punta: haz un grade en `/api/vocabulary/retention/review`
    (`backend/routers/vocabulary.py:764`), mira el evento grabado
    (`backend/domain/retention.py:351-356`, `exercise` con
    `retention:<word>:<grade>`) y **comprueba que la matriz de destrezas y el
    Assessment no se mueven**. Si un grade de tarjeta sube un `mastery`, la decisión
    de fondo del bloque está rota y es **P0**.
23. **El planificador es FSRS-lite, no un SM-2 improvisado.** Cuatro salidas
    (Again/Hard/Good/Easy) y `schedule()` mueve intervalo y facilidad
    (`docs/FSRS.md`). **Falsación honesta:** `docs/FSRS.md` se titula «FSRS-lite —
    Retention Scheduler (**V2.11**)» y declara `2.11.0-lite` **sin** los pesos que
    FSRS completo ajusta con el historial. Llamarlo «FSRS» a secas daría más crédito
    del que tiene; el proyecto lo dice. Dictamina si la versión declarada en la
    cabecera del documento (`V2.11`) es coherente con un arco de V3.77.
24. **El puente candidato → añadido NO es automático.** Se declara que lo trabajado
    en conversación, escritura, lectura y drill llega como **candidato**
    (`GET /api/vocabulary/drill/candidates`, `backend/routers/vocabulary.py:218`) y
    que **es el alumno quien decide** qué entra. **Intenta falsarlo:** busca
    cualquier camino por el que un ítem entre al diccionario personal **sin** un
    acto explícito del alumno (una sincronización, un `seed`, una migración).
25. **Tres formas de añadir, una sola puerta.** Palabra suelta
    (`/api/vocabulary/items`, `:690`), lista pegada (`/api/vocabulary/items/bulk`,
    `:706`) y pack por tema. La validación, el deduplicado y el tope viven en **un
    solo sitio** (`backend/repositories/vocabulary.py:531`,
    `seed_study_items`; tope `BULK_MAX_WORDS = 200` en
    `backend/repositories/collections.py:23`). **Intenta falsarlo:** si hay una
    segunda ruta con su propia validación, es un hallazgo.
26. **Los packs son contenido versionado.** Estaban en `backend/data/vocab_packs/`
    (**ignorado por git**) y se movieron a `backend/curriculum/vocab_packs/`
    (`PACKS_DIR`, `backend/repositories/collections.py:21`). Verifica que **no**
    queda ninguna lectura de la ruta vieja y que los tres JSON **están en el
    repositorio** (no en un `data/` ignorado).
27. **Los packs son TRES y no cubren un currículum.** Comida, viaje, trabajo. El
    proyecto lo declara como límite. **Intenta falsarlo por exceso:** si hay más de
    tres packs servidos, la declaración se queda corta.
28. **La sesión de tarjetas tiene tope declarado.** `SESSION_LIMIT = 20`
    (`backend/domain/retention.py:25`) y `limit` acotado a `[1, 20]`
    (`backend/routers/vocabulary.py:753`). Comprueba que no se puede pedir una
    sesión mayor.
29. **La normalización de la palabra tiene forma cerrada.** `_WORD_RE` acepta
    1–80 caracteres de letras/espacio/`'`/`-` y **exige empezar por letra**
    (`backend/domain/retention.py:24`). **Intenta falsarlo:** pasa una cadena con
    `..`, `/`, un dígito inicial o 81 caracteres; debe rechazarse. Si un `word` llega
    crudo a la BD o a una ruta de fichero, es un hallazgo.
30. **«Frases funcionales», no solo palabras.** El motor debe aceptar unidades de
    varias palabras («how long does it take»). Comprueba que una unidad con espacios
    y apóstrofo entra, se guarda **normalizada** y se lista tal cual. Si el módulo
    solo admitiera una palabra, la release estaría vendiendo algo que no hace.
31. **El diccionario personal no puede morir por un contrato incompleto** (esto es
    `V3.77.1`, §2-f). Añadir de las tres formas con una respuesta **incompleta** del
    servidor no debe tumbar la pantalla.

### E. `V3.77.0` (B) — los perfiles con autorización del webmaster

32. **Una petición es INERTE.** Se declara que pedir **no crea ni borra nada**. Haz
    `POST /api/profile-requests` (sin sesión) y comprueba que **no** aparece ningún
    usuario nuevo, y que la fila queda `pending`. Lo peor que puede hacer quien
    llame es dejar una fila. **Si una petición crea algo, es P0.**
33. **El alta anónima por LAN está cerrada.** `POST /api/users` exige **loopback**
    (`backend/routers/users.py:65`, con `config.is_admin_loopback_host`,
    `backend/config.py:162`). **Intenta falsarlo desde fuera de loopback:** la
    petición debe rechazarse. Y comprueba **lo que sí queda abierto a propósito**:
    el primer arranque en el propio equipo y el perfil `is_test` de los tests
    visuales.
34. **El doble candado de `/api/admin/*`: loopback **y** PIN.** Cada endpoint usa
    `require_admin_local` (`backend/dependencies.py:37`; rutas en
    `backend/routers/admin.py:40,50,79,97,118,133,145`). **Intenta falsarlo en las
    dos direcciones:** (a) PIN correcto desde **fuera** de loopback → `403`; (b) sin
    PIN desde loopback → `403`. Si cualquiera de las dos pasa, el candado no es doble.
35. **Fail-closed de verdad.** Sin PIN declarado, la administración está
    **deshabilitada, no abierta** — también en el cliente del lanzador, que **no
    manda ninguna petición sin PIN** (`launcher/admin.py:68`). Arranca el backend a
    mano sin `ENGLISH_TUTOR_ADMIN_PIN` y comprueba que no hay administración.
36. **Desactivar primero, purgar después.** Aprobar una baja **desactiva** el perfil
    (`backend/domain/profile_requests.py:151`), y purgar **exige que ya esté
    desactivado** (`:226`). Intenta purgar un perfil **activo**: debe rechazarse.
    El proyecto declara que es la diferencia entre un borrado deliberado y un clic
    de más; dictamina si dos pasos bastan.
37. **Purgar es irreversible y la copia es la única red.** `purge_profile` toma un
    snapshot **antes** y **si la copia falla, no purga** (`:227-230`). Comprueba el
    orden: ¿se puede purgar con el ZIP fallido? ¿Se puede quedar un perfil borrado
    sin copia si el proceso muere en medio?
38. **El ZIP no está cifrado.** Se declara: quien lo reciba tiene los datos,
    **incluido el hash del PIN**. Abre un snapshot y compruébalo. El proyecto lo
    declara como precio, no lo esconde.
39. **Un perfil desactivado no abre sesión.** `403 PROFILE_DISABLED`
    (`backend/routers/session.py:75,121`; `dependencies.current_user:81-86`).
    Comprueba además el caso incómodo: **una sesión ya abierta** de ese perfil.
40. **Una petición de baja no puede apuntar a otro perfil.** Se declara que la ruta
    **no lleva `{id}`**: solo se puede pedir la baja de uno mismo
    (`POST /api/profile-requests/delete`, `backend/routers/users.py:104`). Intenta
    falsarlo con un payload que nombre a otro perfil.
41. **La superficie sin sesión está declarada y acotada.**
    `POST /api/profile-requests` es la única puerta nueva sin sesión, y está en
    `docs/ARQUITECTURA.md` §«Superficie sin sesión» y en
    `backend/tests/test_public_surface.py` (el candado falla si se borra la
    declaración). Comprueba que lo declarado sin sesión responde sin sesión y que lo
    declarado **con** sesión **no** sale sin ella.
42. **Los límites de la petición pública.** Cupo por IP **`5`**
    (`backend/security.py:80`, `"/api/profile-requests": 5`), tope de pendientes
    `PROFILE_REQUEST_MAX_PENDING = 20` y longitudes máximas
    (`backend/config.py:173-175`). **Intenta falsarlo:** una petición por nombre,
    sin PII más allá del nombre y la nota, y el cupo mordiendo.
43. **El PIN de administración vive fuera del repositorio.** Se declara en
    `launcher/config.json` (**ignorado por git**) y en el entorno del backend que el
    lanzador arranca (`launcher/core.py:259`, `_declare_admin_pin`). Confirma que
    **no** está versionado y que **retirar** el PIN lo retira **también del entorno**
    —el fallo que encontró `test_admin_pin.py` antes de publicar—.
44. **Sin el lanzador delante nadie crea un perfil.** Es el precio declarado de no
    tener cuentas. Dictamina si eso es aceptable para el producto que se vende.
45. **La decisión de fondo sigue aparcada.** `docs/audit/PARKED.md` y
    `docs/audit/PLAN-P0-IDENTIDAD.md`: esto responde «¿quién puede crear y borrar
    perfiles?», **no** «¿tendrá cuentas el producto?». Sigue contradiciendo «sin
    cuentas, sin contraseñas» de `docs/PREMISAS.md`. Verifica que **no** se ha
    colado un rol, un correo ni una cuenta por la puerta de atrás.

### F. `V3.77.1` — el parche, y la sonda que lo encontró

46. **El defecto y su causa.** `AddVocabSection` guardaba `setPacks(data.collections)`
    **sin comprobar la forma**; con una respuesta sin `collections` el estado quedaba
    `undefined` y el `packs.filter` **al pintar** tumbaba el árbol de React entero.
    La línea arreglada es `frontend/src/features/vocabulary/AddVocabSection.tsx:45`
    (`Array.isArray(data?.collections) ? data.collections : []`), con la misma
    defensa en los avisos (`:68`, `:91`, `:110`).
47. **¿Se arregló la causa o el síntoma?** El proyecto declara que **no** se tocó el
    `mockApi` de la spec (que se queda **vacío a propósito**) ni se aflojó el
    localizador. **Intenta falsarlo:** mira el diff de `V3.77.1` en la spec visual;
    si el mock ganó endpoints, el arreglo es cosmético y es un hallazgo.
48. **El candado nuevo muerde.** `AddVocabSection.test.tsx` fija tres casos, y el
    proyecto declara que **con el código anterior el caso 1 falla**. **Reproduce la
    reversión** (vuelve a `setPacks(data.collections)`) y comprueba que el test
    falla. Si con el código roto sigue verde, el test es decorativo.
49. **La sonda visual es oportunista, no sistemática.** Se declara que el hallazgo
    salió de `drillProvenance.spec.ts` **sin proponérselo**, porque el harness
    mockea `/api/**` con respuestas vacías. Comprueba que el harness **sigue**
    mockeando vacío y razona la cobertura: **¿cuántas pantallas más podrían morir
    igual sin que ningún test se entere?** El proyecto lo declara como límite.
50. **El fallo llegó al tag publicado.** Se declara que lo encontró el CI **quince
    minutos después** de publicar `v3.77.0`, y que **ninguna unidad del producto** se
    había pedido qué pasa con un contrato incompleto. Verifica que `v3.77.0` **no se
    reescribe** (su tag y su commit siguen como se publicaron) y que el informe del
    arco lo declara.
51. **En el producto real el campo siempre viaja.** Se declara que el defecto **no**
    se habría visto en uso normal con el backend de verdad. Si eso es cierto, la
    release publicada funcionaba para el alumno y el daño fue de **cobertura**, no
    de dato. Comprueba el dato incómodo: ¿perdía el alumno **vocabulario** o perdía
    **la vista**? (El proyecto declara que el dato **no** se perdía.)

### G. Deriva documental

52. ¿Declara `docs/RELEVO.md` la posición vigente correcta en su **cabecera**?
53. ¿Está `PLAN.md` sin declarar ningún prefijo de auditoría como libre cuando ya
    está ocupado? (`AN` reservado por `v3.75.1`, `AP` reservado por `v3.75.7`, `AO`
    ocupado, `AQ` = primer libre, el de este informe.)
54. **`agentes/README.md` NO indexa los puntos de entrada desde `v3.73.4`.** El
    último que lista es `agentes/auditoria-total-externa-v373.md`. Se declara que la
    **lista viva es `PLAN.md`** y que el README se ha quedado atrás (§6-vi: es una
    discrepancia declarada, para que la dictamines). Compruébalo: `v3751`, `v3757`
    y este `v3771` **no** aparecen en `agentes/README.md`.
55. ¿Sigue `docs/DEVICE_MATRIX.md` **entero en ⬜**? El proyecto lo declara: si el
    auditor encuentra una celda rellena sin evidencia, es un hallazgo **al revés**.
56. ¿Declara `docs/ARQUITECTURA.md` el número **real** de tests del lanzador y que
    `admin.py` es el **único** sitio del launcher que **escribe** en el producto
    (`docs/ARQUITECTURA.md:330,363`)? Hay un test de deriva que lo exige: ¿muerde?
57. **Los artefactos generados son deterministas.** `docs/audit/generated/*` se
    regenera en el arco (`i18n-report`, `release-validation`). Reproduce la
    regeneración y comprueba que **no hay deriva** (el proyecto declara que estos
    artefactos no pueden quedar desfasados de la versión).
58. **La afirmación «SIN tocar el currículum» se repite en las cuatro notas de
    release.** ¿Es cierta en las cuatro? El invariante §1.1-1 y §1.1-2 la cubren
    para el rango entero; comprueba que **ninguna** release del arco la contradice.

---

## 3. Matriz de cierre (la rellena el auditor)

Cada fila debe sostenerse en **evidencia de código o de test** del árbol publicado.
Si un área no se puede comprobar sin hardware o sin persona, se marca **NO
COMPROBABLE** con el motivo; **no** se puntúa por lo que la documentación promete.

| Área | 🟢/🟡/🔴 | Evidencia (archivo:línea, test o comando) | DEMOSTRADO / DECLARADO / NO COMPROBABLE |
|---|---|---|---|
| Arquitectura | | | |
| Backend | | | |
| Adaptive Engine | | | |
| Pedagogía | | | |
| Contenido (currículum, corpus y evaluaciones) | | | |
| **Los tres packs de vocabulario (§1.1-3)** | | | |
| **Retención léxica (A) — tarjetas y FSRS-lite** | | | |
| **Retención ≠ dominio (§2-22)** | | | |
| **El puente candidato→añadido, no automático (§2-24)** | | | |
| **Perfiles: petición inerte y alta LAN cerrada (§2-32/33)** | | | |
| **Perfiles: doble candado y fail-closed (§2-34/35)** | | | |
| **Perfiles: desactivar antes de purgar (§2-36/37)** | | | |
| GUI | | | |
| **Diccionario de consulta (V3.75.8)** | | | |
| **Versión de compilación en la Ayuda (§2-11)** | | | |
| Rampa de color y contraste | | | |
| Responsive | | | |
| Listening | | | |
| Speaking | | | |
| TTS/voz | | | |
| STT | | | |
| Offline | | | |
| Instalación | | | |
| **Identidad y sesión (P0 declarado abierto)** | | | |
| **El PIN por perfil y su freno (§2-15/16/17)** | | | |
| Frontera de red | | | |
| Superficie sin sesión | | | |
| **`/api/admin/*`: loopback + PIN (§2-34)** | | | |
| **Borrado y copia (ZIP sin cifrar, §2-38)** | | | |
| Cadena de suministro | | | |
| Seguridad | | | |
| CI | | | |
| **El parche V3.77.1 y su candado (§2-46…51)** | | | |
| **La sonda visual: oportunista, no sistemática (§2-49)** | | | |
| Ancla, invariantes y lista cerrada | | | |
| Documentación | | | |

**Criterio de veredicto:** `APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`
para **el arco `v3.75.7..v3.77.1`** (con nota aparte para el **parche
`v3.77.1`**, que se dictamina por su causa, no por su tamaño), con la lista de lo
que debe cerrarse. Recordatorio: la puerta declarada de V4.0 sigue siendo
`validation_gate.py status --strict` saliendo **0**, y **no** depende de este arco.

---

## 4. Reglas duras para el auditor

Rigen las mismas de siempre (solo lectura; separar verificado de declarado;
severidad `P0`–`P3`; una afirmación por hallazgo con `archivo:línea` y comando;
falsabilidad primero — nada de «podría»/«convendría» sin dato; lo no comprobable se
declara **NO COMPROBABLE**; sin cortesía; **no confundir el instrumento con la
validación**; **no confundir «firmado» con «autenticado»**), más las **cuatro
nuevas de este arco**:

1. **No confundir «retención» con «dominio».** Un grade de tarjeta mueve un
   intervalo de repaso; **no** es una prueba de competencia. Si un hallazgo cuenta
   un grade como dominio, está leyendo mal la decisión central de `V3.77.0` (A).
   La evidencia está en `backend/services/evidence.py:955-956` y en el evento
   `retention:<word>:<grade>`.
2. **No confundir «tiene PIN» con «autenticación de persona».** El PIN es una
   mitigación **opt-in** por perfil: un perfil sin PIN entra sin credencial, y no
   hay identidad ni recuperación. El P0 **sigue abierto y declarado**. Un hallazgo
   que diga «ya hay autenticación» está sumando lo que el propio proyecto resta.
3. **No leer un PIN compartido como un rol.** Quien sepa el PIN de administración y
   esté en el equipo administra; **no** hay identidad de administrador ni registro
   de quién aprobó qué más allá de la nota de la decisión. «Administración» aquí
   significa **poder ejecutar el lanzador**, no un rol de la app.
4. **No confundir «la petición existe» con «la petición hace algo».** Una petición
   de perfil es **inerte**: pedir no crea ni borra. Y **ausencia de petición no es
   ausencia de capacidad**: la administración vive en el lanzador, así que revisar
   el producto **sin** el lanzador te deja viendo **la mitad** del mecanismo.
   Declara esa mitad como **NO COMPROBABLE** desde el clon si no levantas el
   lanzador, en vez de puntuarla de memoria.

---

## 5. Honestidad esperada del informe

El auditor debe pronunciarse **explícitamente** sobre estas declaraciones del propio
proyecto, que acotan lo que puede leerse como demostrado:

- **FSRS-lite no es FSRS.** Cuatro salidas y un planificador **declarado y
  simplificado**, **sin** los parámetros por alumno que FSRS completo ajusta con el
  historial. El ítem «FSRS por tipo de memoria» **sigue aparcado**. Llamarlo «FSRS» a
  secas daría más crédito del que tiene.
- **Los packs por tema son TRES** (comida, viaje, trabajo) y **no cubren un
  currículum**: son un punto de partida, no una biblioteca.
- **El P0 de identidad sigue abierto** y el PIN es **opt-in**. Un perfil sin PIN
  entra sin credencial; no hay identidad ni recuperación. Esta arco responde «¿quién
  puede crear y borrar perfiles?», **no** «¿tendrá cuentas el producto?».
- **Purgar es irreversible y el ZIP no está cifrado.** Quien reciba la copia tiene
  los datos, **incluido el hash del PIN**. La copia es la **única** red, y si la
  copia falla, **no se purga**.
- **Desactivar corta el acceso pero no protege los datos.** La evidencia sigue en la
  BD hasta que se purgue; una sesión ya abierta de ese perfil recibe `403`, pero el
  dato no se mueve.
- **El PIN de administración es una credencial compartida, no por persona.**
- **Sin el lanzador delante nadie crea un perfil.** Es el precio declarado de no
  tener cuentas: la administración vive en la máquina.
- **La sonda visual es oportunista, no sistemática.** El defecto de `V3.77.0` lo
  encontró el harness **sin proponérselo**, porque mockea `/api/**` con respuestas
  vacías. No es una red de seguridad: es una coincidencia afortunada. `V3.77.1`
  añadió **un** candado (la pantalla del diccionario), no una revisión de contrato de
  toda la app.
- **El fallo llegó al tag publicado**, y **`v3.77.0` no se reescribe**: la
  corrección viaja en su propia etiqueta, que es lo que permite auditar **qué se
  publicó, cuándo y con qué defecto**.
- **Nadie perdía vocabulario: se perdía la vista.** Con el backend de verdad el campo
  siempre viaja; el daño de `V3.77.0` fue de **cobertura**, y lo que `V3.77.1` compra
  es que un contrato incompleto **no pueda tumbar la pantalla**.
- **El `dist` no se versiona** (`.gitignore`): hay que **recompilar y reiniciar** el
  backend para ver la UI nueva. Es la causa más probable de «no veo nada nuevo».
- **Los 7 gates siguen en `pending`** y el árbol que se certifica sigue siendo el de
  **`v3.75.8`**. Nadie ha hecho el corte de red real (`RA-05`), ni una instalación en
  máquina limpia (`RB-05`), ni pruebas en móvil real, ni pruebas con audio real.
- **El kit es una planilla, no una validación.** `KIT-VALIDACION-GATES.md` ordena y
  registra la ejecución humana; **no** mueve ningún gate a `pass`.
- **La fragilidad del arnés visual bajo carga en Windows** (`PARKED.md` §V3.75.2)
  **sigue aparcada**, y **no** es lo que falló en `V3.77.0`: en local la tanda
  completa da fallos en specs que este arco **no** toca, mientras que
  `drillProvenance` pasa en aislamiento. **La autoridad es el CI.**
- **El rango tiene DIEZ commits y el primero post-data el tag `v3.75.7`** (§0.1). Se
  declara; si eso invalida la lectura del arco como «cerrado», es un hallazgo de
  proceso y debe decirlo.
- **Este punto de entrada NO está dentro del tag `v3.77.1`**: se entrega en un commit
  **posterior**, sin recrear el tag. El invariante del adendo (§1.1-5) demuestra que
  el producto no se movió para entregarlo.
- **`agentes/README.md` no indexa los puntos de entrada desde `v3.73.4`** (§6-vi).
- **La accesibilidad y la matriz de dispositivos no tienen evidencia ejecutada:**
  `docs/DEVICE_MATRIX.md` está **en ⬜** y no hay motor de accesibilidad (`axe`). Lo
  que hay son contratos de UI en Playwright: acotado, no es una auditoría.
- **Sigue abierto y aceptado:** `RA-02` (endpoint de Ollama sin declarar en
  `config.py`), `RA-05`, `RB-05`, `RD-05`, los cinco hallazgos de la pausa
  pedagógica (`AH`–`AM`, política en `AO-POLITICA-PSICOMETRICA-V40.md`) y los ítems
  aparcados de este arco («FSRS por tipo de memoria», «drills de producción por
  aspecto»).

---

## 6. Discrepancias declaradas a propósito, para que las dictamine

Estas **no** son preguntas al azar: son puntos donde el proyecto **decidió** algo
discutible y lo **declara** en vez de esconderlo. El auditor debe dictaminarlas
**explícitamente**, no darlas por buenas ni por malas sin razonar.

**(i) La sustitución del token en fichero por el PIN.** El diseño de
`agentes/v377-perfiles-webmaster.md` §4 pedía un **token en fichero**
(`backend/data/admin.secret`, creado por el lanzador). Se implementó, en cambio, el
**PIN de administración que ya existía** (`X-Admin-Pin`, `config.admin_pin()`), por
tres razones que el propio documento §4bis declara. **Pregunta al auditor:** ¿es
aceptable **cambiar un diseño declarado** durante la implementación, aunque la
corrección quede registrada? ¿Y es correcto que el diseño original **no se borre**
(deja el rastro de lo que se decidió primero)?

**(ii) Sin GitHub Release, y `Latest: v3.33.0` engañoso.** Desde `v3.34.0` la
convención es **tag sí, Release no**. Consecuencia: la página de Releases dice
`Latest: v3.33.0` y un auditor que llegue por ahí creerá que el producto se paró
hace decenas de versiones. El proyecto lo declara y manda entrar por **Tags**.
**Pregunta:** ¿basta la declaración, o el daño de la impresión falsa justifica
publicar Releases o al menos una nota?

**(iii) El CI no corre en tags, y el commit de `v3.77.0` está en ROJO.** El workflow
dispara con `on: push: branches: [main]`, así que **no hay run del tag**: la
evidencia se resuelve contra la run de `main` del mismo SHA. Y la run de `v3.77.0`
está en `failure` **a propósito** (es el defecto que arregla `v3.77.1`). **Pregunta:**
¿es aceptable que la evidencia de una release publicada dependa de la run de `main`,
y que un tag publicado quede con CI rojo sabiendo que la corrección va aparte?

**(iv) El invariante clásico NO se declara.** Producto = **80 ficheros,
+8 539 / −300**. Escribir «el diff de producto sale vacío» sería **falso**. En su
lugar hay **cinco invariantes acotados** (§1.1). **Pregunta:** ¿son suficientes y
están bien elegidos, o dejan fuera algo que debería estar sujeto?

**(v) Los flags `admin_required` pasan de mentir a decir la verdad, sin cambio de
comportamiento.** En `backend/routers/audio_library.py` y
`backend/routers/system.py`, el campo `"admin_required": bool(config.ADMIN_PIN)`
usaba una **constante siempre vacía** y se cambia a `bool(config.admin_pin())`, que
es la función que **sí** puede leer el PIN. **El comportamiento de los endpoints no
cambia** (el candado los protege igual); lo que cambia es que el campo declara la
verdad. **Pregunta:** ¿es aceptable un cambio de información **sin** cambio de
comportamiento dentro de una release de producto, y está bien declarado como tal?

**(vi) `agentes/README.md` no indexa los puntos de entrada desde `v3.73.4`.** El
último que lista es `agentes/auditoria-total-externa-v373.md`; `v3751`, `v3757` y
`v3771` **no** aparecen. La lista viva es `PLAN.md` (§2-54). **Pregunta:** ¿debe
corregirse el README, o es aceptable que el índice canónico sea `PLAN.md` y el README
quede como índice histórico de `agentes/`?

---

## 7. Alcance

- **Qué se audita:** el **arco `v3.75.7..v3.77.1`** = `V3.75.8` + `V3.76.0` +
  `V3.77.0` + `V3.77.1` (9 commits del arco + la errata de `v3.75.7` que abre el
  rango), con **alcance total** sobre el stack (backend, frontend, launcher),
  **incluido el parche `V3.77.1`**, que se dictamina **por su causa**, no por su
  tamaño.
- **Qué NO se audita aquí:** el arco anterior (`..v3.75.7`) ya tiene su entrada
  (`agentes/auditoria-total-externa-v3757.md`); los **7 gates** (`G1`–`G7`) son la
  validación **física**, que sigue **`pending`** y **no** la cierra este informe; y
  las **acciones humanas** (`RA-05` corte de red, `RB-05` máquina limpia, pruebas en
  móvil real y con audio real) se marcan **NO COMPROBABLE** desde el clon.
- **Tipo de release, para encuadrar la severidad:** `V3.75.8` y `V3.76.0` son
  **frontend + PIN** (producto); `V3.77.0` es **minor** con **migración de BD
  aditiva** (dos tablas de colecciones/retención, `profile_requests` y
  `users.status`); `V3.77.1` es un **parche de un fichero**. `V3.76.0` y `V3.77.0`
  tienen **una migración idempotente** cada uno; `V3.75.8` y `V3.77.1` **no migran
  nada**.
- **Sobre `docs/audit/PARKED.md`:** lo que este arco **no** cierra está declarado
  allí con su precio. Un hallazgo que descubra algo ya declarado en `PARKED` **no**
  es un hallazgo nuevo: es una **confirmación** de que la declaración es cierta.

---

## 8. Nota de prefijos y cierre

**Nota de prefijos.** Los prefijos de dos letras de `docs/audit/` no significan una
sola cosa: `AA`–`AF` son los dossiers de V3.70; `AG`–`AM` están ocupados por la serie
pedagógica y por los puntos de entrada externos que reservaron `AG`/`AH`/`AI`/`AJ`
(**ninguno con informe recibido**); `AN` lo reservó el punto de entrada de `v3.75.1`
y `AP` el de `v3.75.7`; `AO` lo ocupa el dossier de decisión
`AO-POLITICA-PSICOMETRICA-V40.md`. **El primer libre es `AQ`**, y lo ocupa el informe
de esta auditoría: **`docs/audit/AQ-AUDITORIA-TOTAL-V3771.md`**. No se renombra
ningún dossier ya publicado: la reserva la declararon los propios puntos de entrada
dentro de sus tags y reescribirla sería falsear historia.

**Estado del punto de entrada: entregado (2026-09-21) en un commit DOCUMENTAL
POSTERIOR al tag `v3.77.1`** —un tag publicado no se recrea—, **sin mover producto**
(invariante §1.1-5, sale **vacío**) y **sin crear un tag nuevo**: el ancla sigue
siendo `v3.77.1`, y este documento lo declara dentro de sí mismo en vez de
aparentar que nació dentro del tag. Verificado por comando contra GitHub, no contra
el árbol local:

- **Release auditada:** el tag anotado **`v3.77.1`**; el commit y el objeto del tag
  se resuelven con `git rev-parse` (§1), **no** se fijan a mano. Nada de SHA ni de
  id de run en este documento.
- **Base de comparación:** **`v3.75.7`**, con el aviso de que el rango contiene
  **diez commits** y el primero es la **errata de `v3.75.7`** (§0.1, §1.2).
- **Los invariantes que sí se pueden declarar** son los **cinco acotados** de §1.1;
  el clásico de «producto sin cambios» **no se declara porque sería falso**
  (producto = 80 ficheros, +8 539 / −300).
- **CI:** se resuelve por comando sobre el commit del tag (§1.4), sabiendo que **el
  CI no corre en tags** y que la run de `v3.77.0` está **roja a propósito**.
- **Consistencia de versión:** `3.77.1` en los **6 orígenes**.
- **Historial:** cinco commits de cierre documental/tests + cuatro commits de
  release, y **una sola etiqueta de auditoría** para las cuatro releases.
- **Lo que queda después de esto:** sellar el baseline con **`v3.77.1`** y ejecutar
  **G1–G7**; los 7 gates siguen en `pending` y **nada** de este arco los adelanta.
