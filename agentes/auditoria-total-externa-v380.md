# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.80.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el arco no auditado
> desde `v3.77.1`**, tal y como quedó publicado en el tag **`v3.80.0`**. La revisión
> es **de solo lectura**: no se cambia código, datos, configuración ni etiquetas
> publicadas.
>
> **Por qué esta auditoría y por qué ahora.** La última entrada externa entregada es
> `agentes/auditoria-total-externa-v3771.md` (ancla `v3.77.1`). Después de ella se
> publicaron **cuatro releases** sin punto de entrada propio: `V3.77.2` (el
> endurecimiento del diccionario personal), `V3.78.0` (el diccionario en tres modos
> y la superficie de estudio única), `V3.79.0` (el diálogo del perfil y la baja que
> decía «saturado») y `V3.80.0` (la cara B de la tarjeta, el mazo como selección
> única y los packs como mazos listos). Este documento cubre **el arco entero** con
> una sola etiqueta de auditoría, porque las cuatro releases se apoyan unas en otras
> —`V3.78.0` construye la superficie cuyo defecto reporta el alumno y que `V3.80.0`
> arregla, y `V3.79.0` arregla dos fallos que el alumno encontró en la app en uso—
> y leerlas sueltas esconde esa dependencia.
>
> **Aviso de encuadre (léelo antes de puntuar).** Esto **no** es la auditoría de un
> parche ni de una release: es una auditoría **de arco** sobre **cuatro releases de
> producto** (backend, frontend y documentación; **el lanzador NO se toca**), con
> **una migración de BD aditiva** y **una pantalla nueva**. Por eso **el invariante
> clásico de esta casa («el diff de producto sale vacío») NO se declara**: sería
> falso —producto = **61 ficheros** de `backend/` y `frontend/`—; y **tampoco se
> declara** el invariante «solo documental», que también sería falso. En su lugar se
> declaran **cinco invariantes acotados** que sí pueden cumplirse o salir exactos
> (§1.1). Un invariante que no se puede cumplir **no se escribe**.
>
> **Estado del punto de entrada:** entregado 2026-09-22 en un **commit documental
> POSTERIOR al tag `v3.80.0`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md` y errata §0.1 de
> `agentes/auditoria-total-externa-v3757.md`). El ancla sigue siendo `v3.80.0` y el
> producto **no se ha movido** para entregar esto; el invariante que lo demuestra
> está declarado y se comprueba por comando (§1.1, invariante 3).
>
> **Informe esperado:** `docs/audit/AR-AUDITORIA-TOTAL-V380.md`. Prefijo **`AR`**
> porque es **el primer prefijo libre** (`AA`–`AF` los ocupan los dossiers de V3.70,
> `AG`–`AM` la serie de la pausa pedagógica, `AO` la política psicométrica, y
> `AG`/`AH`/`AI`/`AJ`/`AP`/`AQ` siguen reservados por puntos de entrada **sin informe
> recibido**). Ver la nota de prefijos en `PLAN.md`.

---

## 0.1 Errata heredada — el rango tiene CINCO commits y el primero post-data el tag `v3.77.1`

> **Qué es esta nota y por qué va antes de todo.** Es la corrección de la única
> discrepancia de trazabilidad que ya sangró en la auditoría anterior, repetida aquí
> **a propósito** para que no vuelva a ocurrir: el rango `v3.77.1..v3.80.0` tiene
> **cinco** commits, y **el primero** (`f67c78d`, `docs(audit): el punto de entrada de
> ARCO anclado a v3.77.1, post-tag y sin mover producto`) **no es de este arco**: es el
> **commit documental con el que se entregó la entrada externa anterior**, y por
> definición **post-data** el tag `v3.77.1` que aquella auditaba. El arco real son los
> **cuatro** commits de release que vienen después.

Es la deriva que V3.73.5 declaró cerrada y que **aquí se declara, no se oculta**. Si
el auditor considera que un commit documental posterior al tag deja desfasado el
ancla, **tiene razón por definición**, y el hallazgo es de proceso, no de producto:
la regla de que un tag publicado no se recrea hace **imposible** entregar un punto de
entrada *dentro* de su propio tag sin mover producto. El compromiso de esta casa es
declararlo.

```bash
git log --oneline v3.77.1..v3.80.0
# 5 líneas: 1 documental (f67c78d) + 4 de release (V3.77.2, V3.78.0, V3.79.0, V3.80.0)
git show --stat f67c78d
# PLAN.md (+11) y agentes/auditoria-total-externa-v3771.md (+888): SOLO documentación
```

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (nota de la posición vigente) y **§0 «START
   HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. Las **cuatro notas de release**, que son el cuerpo documental de este arco:
   `release-notes-v3.77.2.md`, `release-notes-v3.78.0.md`,
   `release-notes-v3.79.0.md` y `release-notes-v3.80.0.md`.
4. `docs/audit/PARKED.md` — lo **aparcado a propósito**. Sus secciones **`V3.77.2`**
   a **`V3.80.0`** son la declaración honesta de lo que el arco **no** cierra.
5. `agentes/auditoria-total-externa-v3771.md` — la entrada externa anterior (ancla
   `v3.77.1`), **cuyos hallazgos H4 y el menor de la cola de repaso cierra
   `V3.77.2`**; conviene leerlos porque son el `before` de la release B de §2.
6. `docs/FSRS.md` — el planificador de retención **declarado** (`FSRS-lite`,
   `2.11.0-lite`), que es lo que hace auditable «por qué toca hoy esta tarjeta», y
   `backend/services/fsrs.py`, que es lo que este arco usa sin cambiarlo.
7. `docs/audit/PLAN-P0-IDENTIDAD.md` (el P0 **sigue abierto**) y
   `docs/audit/G7-MATRIZ-LECTURA.md` (la matriz de los nueve ejes).
8. `docs/UI_V3.1.md` §3.2–3.5 — las convenciones de UI.
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
git log --oneline -5 main
```

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.80.0`** (el último del arco; `v3.79.0`,
  `v3.78.0` y `v3.77.2` están **dentro** del rango). Los identificadores exactos se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.80.0            # objeto del tag anotado
git rev-parse v3.80.0^{commit}   # commit de release (el SHA exacto que se audita)
git rev-parse v3.77.1^{commit}   # commit base del arco (el ancla anterior)
git log -1 --format='%H %s' v3.80.0^{commit}
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run de CI que dispara su
  push: son datos que solo existen **después** de publicar. Fijarlos obligaba a un
  commit de re-anclaje **posterior al tag**, que quedaba a su vez fuera del tag
  siguiente, y por eso `main` iba siempre por delante en documentación. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando** y este archivo es coherente **dentro de su propio tag**. Si un documento
  de este tipo vuelve a fijar un SHA o un run a mano, es una **regresión**.

- **Base de comparación:** `v3.77.1` (el ancla de la última entrada externa
  entregada, `agentes/auditoria-total-externa-v3771.md`). No es una comparación
  neutra y conviene decirlo: **`v3.77.1` es también el tag cuyo arco anterior sigue
  sin informe recibido** (`AQ` reservado y vacío), así que el auditor hereda una
  cadena con **seis prefijos reservados y ningún informe** (`AG`, `AH`, `AI`, `AJ`,
  `AP`, `AQ`). Dictaminar si eso compromete la auditabilidad del producto es parte
  del trabajo (§2-A5).

- **Cuatro releases, un solo punto de entrada.** `v3.75.7` publicó cinco
  iteraciones bajo una etiqueta; el arco anterior publicó cuatro; **este arco vuelve
  a publicar cuatro releases bajo una sola etiqueta de auditoría**. `CHANGELOG.md`
  lleva una entrada por release y **solo `v3.80.0` tiene tag**: `V3.77.2`, `V3.78.0`
  y `V3.79.0` **no llevan etiqueta propia**, y eso **es una decisión declarada**, no
  un hueco (verifícalo con `git tag --points-at <commit>` para los tres commits del
  medio).

- **El árbol de certificación no se mueve.** Los gates G1–G7 se congelaron en
  **`v3.75.8`** y **siguen en `pending`**. Este arco **no** los toca, **no** adelanta
  validación física y **no** añade ni retira un gate.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Este arco **cambia producto** (**61 ficheros** de `backend/` y `frontend/`, y
**75** en total contando documentación: **+12 892 / −601**), así que **el invariante
clásico («el diff de producto sale vacío») NO se declara**: sería falso. Se declaran
**cinco invariantes acotados**, cada uno con el comando que lo comprueba y el
comando que lo **falsaría**.

**(1) El contenido de currículum y evaluaciones: VACÍO.** Ni una línea, y con los
packs de vocabulario incluidos.

```bash
git diff --stat v3.77.1..v3.80.0 -- backend/curriculum
```

Debe salir **vacío**. Es decir: **no se reabre nada** de checks, evaluaciones,
corpus de listening ni los tres packs de vocabulario
(`backend/curriculum/vocab_packs/{food,travel,work}.json`, **25 pares cada uno = 75**,
`A1`/`A2`/`B1`), que en este arco se **leen** (se inscriben, se estudian) y **no** se
reescriben: `V3.80.0` los convierte en «mazos listos» **sin tocar el JSON**.
**Lo falsaría:** cualquier línea de salida. Sería un hallazgo **P0**.

**(2) Sin bumps pedagógicos ni de instrumento.** Ninguna línea `+`/`−` del rango
asigna ni cambia `CURRICULUM_VERSION`, `LISTENING_BANK_VERSION`, `GENERATOR_VERSION`
ni `DECISION_POLICY_VERSION`.

```bash
git diff -U0 v3.77.1..v3.80.0 -- backend | grep -E '^[+-].*(CURRICULUM_VERSION|LISTENING_BANK_VERSION|GENERATOR_VERSION|DECISION_POLICY_VERSION)' || echo VACIO
```

Debe salir **`VACIO`**. Los valores vigentes y **sin mover** son:
`CURRICULUM_VERSION = "1.3.1"` (`backend/services/curriculum.py:205`),
`LISTENING_BANK_VERSION = "7.0.0"` (`backend/services/curriculum.py:215`),
`GENERATOR_VERSION = "1.4.0"` (`backend/services/dictionary_content.py:74`) y
`DECISION_POLICY_VERSION = "v3.68.0"` (`backend/repositories/decision_records.py:61`).
**Aviso para no confundir una cita con un cambio:** el `grep` sobre `CHANGELOG.md`,
`PLAN.md` o las notas de release **sí** nombra esas constantes; lo que este
invariante acota es el **diff de `backend/`**, y por eso el comando lleva `--
backend`. **Lo falsaría:** una línea `+`/`-` con esas constantes en `backend/`.

**(3) El producto no se ha movido desde el tag.** El commit documental con el que se
entrega este punto de entrada **no toca producto**:

```bash
git diff --stat v3.80.0..main -- backend frontend launcher scripts
```

Debe salir **vacío** (verificado al entregar). Y el diff **completo** del rango
`v3.80.0..main` debe contener **solo documentación**: `agentes/auditoria-total-externa-v380.md`
y la fila de trazabilidad en `PLAN.md`, exactamente como se entregó la entrada
anterior (`f67c78d`: `PLAN.md` + `agentes/…v3771.md`, sin más). **Lo falsaría:**
cualquier línea de producto en el diff, o cualquier fichero de más en el diff
completo. Sería **P0**, porque significaría que lo que se audita no es lo que está
publicado.

**(4) La migración de BD es aditiva, idempotente y NO rellena nada.** `V3.80.0` añade
**una** columna (`vocabulary.translation TEXT NOT NULL DEFAULT ''`) con el idioma
`PRAGMA table_info` + `ALTER TABLE` idempotente que ya existía:

```bash
grep -n -A4 '"translation" not in vocab_cols' backend/repositories/db.py
# db.py:986 — ALTER TABLE vocabulary ADD COLUMN translation TEXT NOT NULL DEFAULT ''
# Las filas viejas quedan en '' (la lectura honesta de «no consta»), NO se inventa
# una traducción para tapar el hueco.
```

**Los dos candados que lo hacen no-decorativo**, y que el auditor debe intentar
romper:

```bash
cd backend && python -m pytest -q tests/test_foreign_keys.py::test_fk_migration_idempotent
# 1 passed: llama a db.init_db() DOS veces sobre la misma BD.
```

Ese test es **el que muerde** si alguien quita el `if`: sustituyendo la guarda por
una ejecución incondicional del `ALTER`, el candado falla con
`sqlite3.OperationalError: duplicate column name: translation` (comprobado al
entregar, y revertido). Es decir: **la idempotencia de esta columna no depende de un
test nuevo que solo este arco conoce, sino de un candado que ya existía**.

La **aditividad sin pérdida** se demuestra además por construcción, y así lo hice al
entregar: construyendo una BD con la tabla `vocabulary` **tal cual era en `v3.79.0`**
(6 columnas: `id, user_id, word, production_count, first_seen, last_seen`), metiendo
una fila dentro y abriéndola con el código de `main`: la tabla pasa a **31 columnas**,
la fila **sobrevive** y su `translation` queda en `''`; la segunda apertura es
idempotente. **No hay script de esto en el repo** (fue una comprobación de una vez) y
eso se declara: el auditor puede reproducirlo con el `CREATE TABLE` de
`git show v3.79.0:backend/repositories/db.py` o aceptar los dos candados de arriba.
**Lo falsaría:** que el `ALTER` fallara sobre una BD vieja, que perdiera filas, o que
un valor por defecto distinto de `''` apareciera.

**(5) La cara B tiene una precedencia declarada, y su candado muerde.** El orden es
**lo que escribió el alumno** → **catálogo del pack** (autoría curada) → **caché del
diccionario** (generada a máquina):

```bash
grep -n -B2 -A12 'def card_face' backend/domain/retention.py   # retention.py:122
cd backend && python -m pytest -q tests/test_back_face_v380.py  # 9 passed
```

El candado **muerde**: quitando de `card_face` la lectura de la traducción del alumno
(`vocabulary_repo.translation_for_word`) y dejándola en `""`, **4 de los 9** tests
fallan (comprobado al entregar, y revertido). Los 9 cubren precedencia,
aislamiento entre alumnos, propagación de una corrección a la cola del mazo
automático y que el `PATCH` **no** crea vocabulario (la invariante D3 del proyecto).
**Lo falsaría:** que la precedencia no fuera la declarada —por ejemplo que la caché
del diccionario pisara lo que el alumno escribió—, que la corrección de un alumno se
viera en otro, o que un `PATCH` sobre una palabra que no está en el léxico **la
creara**.

### 1.2 Lista cerrada — los cinco commits del rango

| # | Commit | Qué publica | Tag |
| --- | --- | --- | --- |
| 1 | `f67c78d` | **Documental, POSTERIOR a `v3.77.1`** (§0.1): el punto de entrada del arco anterior. No toca producto. | — |
| 2 | `f6520ac` | `release(v3.77.2)`: la autorización (IDOR) que faltaba, el `ErrorBoundary` que no existía y la familia de guardias incompletas | — |
| 3 | `5510901` | `release(v3.78.0)`: el diccionario en tres modos y la **única** superficie de estudio | — |
| 4 | `3e8af1f` | `release(v3.79.0)`: el perfil, el diálogo que se recortaba y la baja que decía «saturado» | — |
| 5 | `18fd86c` | `release(v3.80.0)`: la cara B que no existía, el mazo hecho selección única y los packs como mazos listos | **`v3.80.0`** |

### 1.3 Lista cerrada — el diff del arco, por área

```bash
git diff --shortstat v3.77.1..v3.80.0            #  75 files changed, 12892+/601-
git diff --shortstat v3.77.1..v3.80.0 -- backend #  19 files changed,  3406+/ 97-
git diff --shortstat v3.77.1..v3.80.0 -- frontend#  42 files changed,  6544+/492-
git diff --shortstat v3.77.1..v3.80.0 -- docs    #   6 files changed,   589+/ 11-
```

**`backend/` (19).** `config.py` (bump `VERSION`), `security.py` (el rate limiter por
clase de ruta), `repositories/db.py` (la columna aditiva), `domain/{retention,
flashcards,vocabulary,academy}.py`, `repositories/{flashcards,collections,vocabulary,
academy}.py`, `routers/vocabulary.py`, `schemas/vocabulary.py`,
`services/{evidence,fsrs}.py` y cuatro ficheros de test
(`tests/test_back_face_v380.py` **nuevo**, 9 tests; `tests/test_flashcards_v378.py`
**23** tests; `tests/test_retention_personal_v377.py`; `tests/test_security.py`).

**`frontend/` (42).** Nuevos: `api/normalize.ts` (+ su test),
`components/ErrorBoundary.tsx` (+ test), `components/ProfileDialog.test.tsx`,
`features/vocabulary/FlashcardsScreen.tsx` (17 tests), `StudySession.tsx` (11 tests)
y `styles/dialogLayout.test.ts` (4 tests), más `tests/visual/profileDialog.spec.ts`
(2 tests). **Borrados:** `features/vocabulary/RetentionSession.tsx` y su test — la
superficie de estudio **se sustituye**, no se duplica. Modificados: `styles/legacy.css`
(el patrón de diálogo), `utils/{i18n,dictionaryView}.ts`, `types/api.ts`,
`api/{vocabulary,profileRequests,learning}.ts`, `components/ProfileDialog.tsx`,
`app/Workspace.tsx`, `main.tsx`, y la familia entera de `features/vocabulary/`
(`DictionaryScreen`, `DictionaryLookup`, `PersonalDictionary`, `AddVocabSection`,
`ReviewQueueSection`, `wordDrill`, `wordDrillSteps`) con sus tests.

**Documentación (14).** `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md`,
`docs/audit/PARKED.md`, los cuatro `release-notes-v3.77.2…v3.80.0.md`, los
`docs/audit/generated/*` regenerados (informe i18n y validación de release) y
`agentes/auditoria-total-externa-v3771.md`.

**El lanzador (`launcher/`) NO aparece en el diff.** Verifícalo: es parte del
invariante 3.

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
SHA=$(git rev-parse v3.80.0^{commit})
gh run list --commit "$SHA" --limit 5        # la run de CI del commit del tag
gh run view <run_id> --json jobs -q '.jobs[] | .conclusion + "  " + .name'
python scripts/check_release_consistency.py  # OK: Release consistency (3.80.0) en todos los orígenes
git diff --stat v3.80.0..main -- backend frontend launcher scripts   # vacío
```

**A fecha de entrega (2026-09-22)**, y el auditor debe **re-resolverlo** porque los
datos de CI **no forman parte del repositorio**: la run del commit del tag tenía
**12 jobs** y **los 12 en `success`** (`Backend (ruff + pytest)`, `Validation gate
(checks automáticos)`, `Content validation`, `Release consistency`, `Frontend (tsc +
vitest + build)`, `Playwright E2E (visual)`, `Dependency audit (pip-audit + npm
audit)`, `Beta V3.0 gate`, `Launcher (ruff + pytest)`, `Launcher (Windows, ruff +
pytest)`, `Product origin (Windows, informativo)` y `Product origin (UI served over
HTTPS)`). La consistencia de versión salió `OK` —una fuente de verdad y **cinco**
sitios comprobados— y el invariante 3 salió vacío.

**Aviso para no atribuir a la etiqueta lo que no es suyo:** el CI **no corre en
tags** (`.github/workflows/ci.yml` dispara en `push: branches: [main]` y en
`pull_request`). La run que **certifica** el commit del tag es, por tanto, la del
**push a `main`** de ese mismo commit —mismo árbol, misma run—, y así se resuelve con
`gh run list --commit "$SHA"`. Un tag no dispara ni puede disparar nada: quien audite
«el CI del tag» está auditando el CI del commit al que apunta el tag.

---

## 2. Preguntas falsables por área

Cada pregunta se responde **con evidencia del repositorio** (fichero:línea, comando
o test). «El test no lo demuestra» y «el motor no lo cumple» son **dos veredictos
distintos** y hay que elegir uno.

### A. El ancla, el historial y el carril de cierre

- **A1.** ¿El rango `v3.77.1..v3.80.0` tiene **cinco** commits y el primero es
  **documental** (§0.1)? `git log --oneline v3.77.1..v3.80.0`. **Dictamina:** ¿es
  aceptable que un commit ajeno al arco viaje dentro del rango auditado, o contamina
  el veredicto?
- **A2.** ¿Es coherente anclar en `v3.80.0` y entregar el punto de entrada en un
  commit **posterior** al tag? ¿La alternativa (mover el tag o mover producto) habría
  sido peor? **Dictamina** con la regla de `KIT-VALIDACION-GATES.md` delante.
- **A3.** Solo `v3.80.0` tiene tag. ¿`V3.77.2`/`V3.78.0`/`V3.79.0` sin etiqueta propia
  es una **decisión declarada** o un hueco de trazabilidad?
  `git tag --points-at <commit>` para los tres.
- **A4.** `scripts/check_release_consistency.py` toma **una** fuente de verdad
  (`backend/config.py::VERSION`) y la comprueba contra **cinco** sitios
  (`frontend/package.json`, `frontend/package-lock.json`, `README.md`,
  `CHANGELOG.md`, `PLAN.md`). ¿Son esos los que importan? ¿Hay alguno fuera del
  guion que pueda quedar desincronizado —por ejemplo la versión que la **Ayuda**
  muestra al alumno (`frontend/src/utils/buildInfo.ts`) o `docs/RELEVO.md`—? Si el
  auditor encuentra un sexto origen, es un hallazgo de **gate**, no de producto.
- **A5.** **La cadena heredada:** seis prefijos reservados (`AG`, `AH`, `AI`, `AJ`,
  `AP`, `AQ`) y **ningún informe recibido**. ¿Es auditable un producto que acumula
  entradas externas sin dictamen? ¿Debería el proceso bloquear la entrega de una
  entrada nueva hasta recibir la anterior, o el desbloqueo es precisamente acumular
  contexto?
- **A6.** ¿El CI del commit del tag está verde **hoy** y **con todos sus jobs**?
  (§1.4). Si algún job hubiera cambiado de estado, **eso** es el hallazgo, no este
  documento.

### B. `V3.77.2` — el endurecimiento del diccionario personal

- **B1.** **El IDOR.** `enroll_collection` comprobaba de quién era la colección y la
  **ingestión no**. ¿Están cubiertas **todas** las rutas de escritura que asignan
  `collection_id` (`POST /api/vocabulary/items`, `/items/bulk`, y cualquier otra)?
  Búscalas y verifica que cada una pasa por la guardia de propiedad **antes** de
  escribir, y que hay **un test por ruta** (`grep` de `collection_id` en
  `backend/routers/vocabulary.py` y en `backend/tests/`). Si alguna ruta quedó sin
  guardia o sin test, es **P0**.
- **B2.** `frontend/src/api/normalize.ts` **normaliza en vez de lanzar**: un
  contrato roto degrada silenciosamente. Es una decisión declarada (la pantalla moría
  al pintar). **Dictamina:** ¿degradar es lo correcto en esa frontera o esconde la
  ruptura de contrato que la causó? ¿El `ErrorBoundary` hace que lanzar vuelva a ser
  una opción?
- **B3.** `ErrorBoundary.tsx`: ¿envuelve lo que dice envolver? ¿Captura errores **de
  render** y no de código asíncrono (y lo dice)? ¿Ofrece salida al alumno sin perder
  datos? ¿Manda algo fuera del equipo (privacidad)? ¿Hay un test que provoque un
  `throw` y compruebe que captura, o el test solo comprueba que se monta?
- **B4.** **Los hallazgos de la auditoría anterior.** El H4 de
  `agentes/auditoria-total-externa-v3771.md` señalaba `PersonalDictionary.refresh()`
  guardando la respuesta sin comprobar la forma (el mismo fallo del parche, en el
  padre, con doble superficie). Verifica que ahora se normaliza **en la frontera del
  estado** (`normalizeLexicon` / `normalizeDrillCandidates`) y que el menor
  (`queue?.items ?? []` de `ReviewQueueSection.tsx`) pasó a `asArray(...)`
  (`ReviewQueueSection.tsx:151`). ¿Queda algún `?? []`/`|| []` de esa familia en
  `frontend/src/features/vocabulary/`? `grep -rn '?? \[\]' frontend/src`.
- **B5.** Los arreglos de accesibilidad/forma de la release (un solo `<h1>`, resumen
  alcanzable) son **afirmaciones de DOM**. ¿Están respaldadas por un test que las
  falsaría (p. ej. contar los `<h1>`), o solo por la nota de release?
- **B6.** La release se declara de **endurecimiento sin producto nuevo**: sin
  endpoint nuevo, sin tabla nueva, sin pantalla nueva. ¿Lo sostiene el diff de
  `backend/` y `frontend/` (`git diff --stat v3.77.1..v3.77.2`)?

### C. `V3.78.0` — el diccionario en tres modos y la única superficie de estudio

- **C1.** `DictionaryView` pasa a `"lookup" | "personal" | "flashcards"` y
  `DEFAULT_DICTIONARY_VIEW` pasa a `"lookup"`. **La pregunta que importa:** si el
  alumno ya tenía una vista persistida, ¿gana la persistida o el nuevo defecto?
  (`frontend/src/utils/dictionaryView.ts` y su test). Un cambio de defecto que
  reescriba la preferencia del alumno en silencio es un hallazgo.
- **C2.** **Una sola superficie de estudio.** `RetentionSession.tsx` **se borra**.
  ¿Queda algún camino en la app que siguiera montando la superficie vieja (ruta,
  botón, `Mis listas`, la cola de repaso)? ¿El endpoint de retención anterior sigue
  existiendo y **delega**, o se rompió un contrato publicado sin declararlo?
  `grep -rn 'retention' backend/routers/vocabulary.py frontend/src --include=*.ts*`.
- **C3.** **El mazo automático.** ¿Es un mazo **virtual** (`AUTO_DECK_ID = 0`,
  `backend/repositories/flashcards.py:26`) o una fila? Si es virtual, ¿puede un
  alumno crear un mazo cuyo id colisione con él? ¿Dónde se guardan las revisiones de
  sus tarjetas y siguen el mismo calendario FSRS que las manuales?
- **C4.** **Borrar un mazo, ¿borra evidencia?** ¿El borrado cae en cascada sobre
  tarjetas y revisiones? La retención es **evidencia del alumno** en este producto;
  si borrar un mazo destruye revisiones ya registradas, **dictamina** si eso viola la
  separación «evidencia vs. superficie» que el resto de la app mantiene, y si está
  declarado en la nota de release.
- **C5.** Los **límites diarios** y la definición de «palabra nueva»: ¿se derivan del
  **libro mayor** (ledger) o de contadores? ¿Cuadra con lo que `docs/FSRS.md` declara?
- **C6.** **Dos fuentes de verdad para la misma palabra.** Las tarjetas manuales
  tienen su calendario por **tarjeta**; el léxico, por **palabra**. Si el anverso de
  una tarjeta manual coincide con una palabra del léxico, ¿hay doble repaso de lo
  mismo? ¿Está declarado o es un agujero?

### D. `V3.79.0` — el perfil: el diálogo que se recortaba y la baja que decía «saturado»

- **D1.** **El rate limiter.** La ventana pasa a estar partida por
  `(host, clase de ruta)` con **prefijo más largo** (`security.py:58` `_PATH_LIMITS`,
  `:99` `_clients`, `:141` `_route_class`, `:162` `_rate_limit_ok`), y
  `/api/profile-requests/delete` gana **30/min** propio. Verifica: (a) que el prefijo
  más largo es de verdad lo que se elige y no el primero del diccionario; (b) que
  `test_path_limits_match_real_routes` sigue pasando; (c) que hay un test que
  **reproduce el 429 con el código viejo** y demuestra que está cerrado.
- **D2.** **¿El arreglo debilita algo?** Antes, todas las peticiones de un equipo
  compartían cola; ahora cada clase tiene **su** cupo. Es decir: contra la ruta
  general el cupo sigue en **1200/min** (`_DEFAULT_LIMIT`) y contra las sensibles en
  el suyo. **Cuantifica** si un script hostil gana capacidad por el hecho de
  particionar, y si el tope por IP (holgado a propósito, con el PIN defendido por
  `services/pins.py`) sigue siendo la valla correcta. **Dictamina.**
- **D3.** **El `Retry-After` que ve el alumno es una constante.** El middleware
  responde 429 con `extra_headers=[(b"retry-after", b"5")]` **fijo**
  (`security.py:247`), mientras la ventana es de **60 s** (`_RATE_WINDOW_SECONDS`);
  el frontend lo convierte en «El servidor pide esperar 5 s»
  (`api/client.ts:51`, `ProfileDialog.tsx`). Es decir: **la frase no es falsa (el
  servidor pidió 5 s), pero puede quedarse corta hasta 12×** y el alumno puede volver
  a recibir 429 al reintentar. En la misma base de código, la ruta de sesión **sí**
  calcula el tiempo real (`routers/session.py:97`, `int(espera) + 1`). **Es una
  discrepancia declarada a propósito (§6-i) y hay que dictaminarla.**
- **D4.** **El portal.** El diálogo se monta con `createPortal` a `document.body`
  porque un `backdrop-filter` en el `<header>` lo convertía en **bloque contenedor**
  de un `position: fixed`, y el diálogo se recortaba por arriba. Verifica: que el
  patrón CSS (`legacy.css:2338` `.dialog-backdrop`, `:2358` `.dialog`, `:2409`
  `.dialog-body`) respeta el borde visible en pantallas pequeñas; que el portal **no**
  rompió Escape, el foco ni el cierre al clicar el fondo; y **dictamina la fuerza de
  los candados**: `styles/dialogLayout.test.ts` es un **test sobre el TEXTO del CSS**
  (leer el fichero y buscar `margin: auto`, `dvh`, `overflow-y`) mientras que
  `tests/visual/profileDialog.spec.ts` es el que mide píxeles de verdad. ¿Un `grep`
  del CSS merece llamarse candado? ¿Basta **un** viewport en el test visual?
- **D5.** **`dvh`.** Se usa `100dvh` con respaldo. ¿Cuál es el navegador objetivo del
  producto (el que sirve el lanzador) y lo soporta? ¿El respaldo hace algo o solo
  aparenta?
- **D6.** **La baja.** El botón se deshabilita mientras la petición está en vuelo
  (`deleteBusy`) y la baja es idempotente en el servidor: ¿un doble envío real (dos
  clics rápidos, o un reintento de red) crea **dos** solicitudes de baja? Busca el
  candado; si solo lo impide el `disabled` del botón, dilo.

### E. `V3.80.0` — Flashcards a fondo

- **E1.** **La precedencia** (invariante 5): ¿está donde dice y se cumple en los tres
  casos (el alumno corrige una palabra que **sí** tiene pack; corrige una que solo
  está en la caché; corrige una sin nada)? **Dictamina** el caso de la corrección
  **equivocada**: una vez que el alumno escribe una traducción, el pack curado
  **nunca** vuelve a verse para esa palabra. ¿Es la política que quieres defender?
  (Se puede volver a la precedencia borrando la propia: `translation=''`.)
- **E2.** **La invariante D3.** `PATCH /api/vocabulary/items` **no crea** vocabulario
  (`backend/routers/vocabulary.py:723`, `domain/vocabulary.py::set_item_translation`).
  Verifica que un `PATCH` sobre una palabra **fuera** del léxico: (a) no devuelve
  éxito, (b) **no deja fila nueva**. Y que el test que lo afirma falla si se cambia
  `set_translation` por un `INSERT`.
- **E3.** **La cifra que sostiene la decisión no es reproducible.** La nota de release
  afirma «**139 de 145** cartas del léxico sin traducción»
  (`release-notes-v3.80.0.md:33`) midiendo la **BD real del alumno**, que **no se
  publica**. **Dictamina:** ¿puede una cifra no reproducible sostener una decisión de
  producto, o el arreglo se sostiene igual solo con el código (que `card_face` no
  tenía **ninguna** fuente para el reverso de una palabra del léxico)? Esta casa
  declara las cifras no reproducibles como tales; comprueba que aquí se declara.
- **E4.** **El parser compartido.** El pegado de tarjetas usa
  **el mismo** `retention.parse_bulk_lines` (`backend/domain/retention.py:36`) que el
  pegado de palabras del léxico: `,` o tabulador separan anverso y reverso, `#`
  comenta, la línea vacía se ignora. Verifica que el léxico **sigue aceptando lo que
  aceptaba** (sin regresión para las listas que el alumno ya pegaba) y **dictamina el
  precio**: con `line.split(",", 1)` un anverso que contenga una coma es imposible
  («hello, world, hola» → anverso `hello`, reverso `world, hola`). ¿Está declarado?
- **E5.** **Los topes son silenciosos.** `CARDS_BULK_MAX = 200`,
  `MAX_CARD_FRONT = 400`, `MAX_CARD_BACK = 2000` (`domain/flashcards.py:45-47`).
  ¿La pantalla dice cuántas entraron **de verdad** (el contador devuelto por el
  servidor) o cuántas se pegaron? ¿Se avisa de lo truncado, o se recorta y se calla?
- **E6.** ¿Pegar tarjetas en el **mazo automático** está rechazado (como
  `create_card`), y con qué desenlace HTTP? ¿Hay test?
- **E7.** **Los mazos listos.** Inscribir un pack escribe léxico **y** tarjetas FSRS
  con su reverso. Verifica: (a) si es **una** transacción o N escrituras; (b) si
  inscribir dos veces **duplica**; (c) si se puede **deshacer** (salir de un pack) y,
  si no se puede, **dónde está declarado**. Y `ensure_theme_packs_seeded`
  (`repositories/collections.py:26`) sigue siendo idempotente por slug.
- **E8.** **Estudiar filtrado.** El estudio por pack filtra por `collection_id`.
  ¿Qué pasa con una palabra que está en **dos** packs? ¿Y con el **calendario** de
  una palabra ya estudiada fuera del filtro: el filtro cambia **lo que se ve** o
  **lo que se agenda**? Si cambia lo que se agenda, es un hallazgo de fondo.
- **E9.** El mazo recién creado ahora **se selecciona** y abre la pestaña de tarjetas
  con el anverso enfocado (`FlashcardsScreen.tsx:121` `openCardsFor`), y un mazo vacío
  da una guía. ¿La guía dice **por qué** está vacío y ofrece los **dos** caminos
  reales (pegar / añadir un mazo listo), o solo invita a crear?

### F. Deriva documental

- **F1.** ¿Los números de las notas de release cuadran con el árbol publicado
  (ficheros, tests, cifras)? Empieza por los que se pueden contar:
  `pytest --collect-only -q | tail -1`, el recuento de tests nuevos citados
  (`test_back_face_v380.py` = **9**, `test_flashcards_v378.py` = **23**,
  `FlashcardsScreen.test.tsx` = **17**, `StudySession.test.tsx` = **11**).
- **F2.** ¿`PLAN.md` dice lo mismo que las notas de release y que `CHANGELOG.md`, y
  `README.md` anuncia `3.80.0`? (El gate de consistencia comprueba la **cadena** de
  versión, no la **coherencia de las afirmaciones**: eso lo dictamina el auditor.)
- **F3.** ¿`docs/audit/PARKED.md` declara lo aparcado de **este** arco de forma
  específica (no un cajón genérico)? Enumera lo que el arco **no** cierra: ¿queda
  algo por decir que falte?
- **F4.** Los artefactos generados (`docs/audit/generated/i18n-report.{json,md}`,
  `release-validation.{json,md}`) se regeneran con un comando del repo. ¿Es
  reproducible **byte a byte** lo publicado, o hay deriva? Si el comando no existe o
  no reproduce, es un hallazgo de trazabilidad.

---

## 3. Matriz de cierre (la rellena el auditor)

| Pregunta | Veredicto | Severidad | Evidencia (fichero:línea / comando) |
| --- | --- | --- | --- |
| A1 | | | |
| A2 | | | |
| A3 | | | |
| A4 | | | |
| A5 | | | |
| A6 | | | |
| B1 | | | |
| B2 | | | |
| B3 | | | |
| B4 | | | |
| B5 | | | |
| B6 | | | |
| C1 | | | |
| C2 | | | |
| C3 | | | |
| C4 | | | |
| C5 | | | |
| C6 | | | |
| D1 | | | |
| D2 | | | |
| D3 | | | |
| D4 | | | |
| D5 | | | |
| D6 | | | |
| E1 | | | |
| E2 | | | |
| E3 | | | |
| E4 | | | |
| E5 | | | |
| E6 | | | |
| E7 | | | |
| E8 | | | |
| E9 | | | |
| F1 | | | |
| F2 | | | |
| F3 | | | |
| F4 | | | |

Veredicto por **área** (A–F) y **veredicto global**, con la misma escala que las
auditorías anteriores: **P0** (rompe una promesa publicada, corrompe datos o expone
al alumno) · **P1** (funciona mal de verdad para el alumno) · **P2** (deuda con
riesgo) · **P3** (limpieza). Y, como siempre, **la distinción que más importa**:
«el test no demuestra» **no** es lo mismo que «el motor no cumple».

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se cambia código, datos, configuración, ni etiquetas
   publicadas. **Un tag publicado no se recrea.** Si algo hay que corregir, se
   escribe en el informe.
2. **Todo veredicto lleva evidencia** del repositorio (fichero:línea, comando o
   test). Sin evidencia, no es un hallazgo: es una impresión.
3. **No se audita lo que el documento promete, sino lo que el código hace.** Las
   notas de release son la **hipótesis**, no la prueba.
4. **Separa las dos cosas.** «El test no demuestra X» y «el motor no cumple X» son
   veredictos diferentes; mezclarlos es el error más caro de este ejercicio.
5. **No hay datos de alumno publicados.** Nada de lo que se pida requiere la BD real:
   si una cifra solo se sostiene con ella, el hallazgo es **de método** (E3).
6. **El CI vive en GitHub, no en el repo.** El estado de publicación se
   **re-resuelve** (§1.4); un run de hoy no prueba lo que pasó al publicar.
7. **Pregunta cuando no puedas falsar.** Es mejor «no concluyente» con el motivo
   escrito que un veredicto inventado.

---

## 5. Honestidad esperada del informe

El informe debe declarar, en su propia sección de honestidad:

- **Qué no ha podido comprobar** (y por qué): el estado histórico del CI, la BD real
  del alumno, el comportamiento en el navegador objetivo si no lo tiene, el audio y
  la voz (el arco no los toca, pero el producto los tiene).
- **Qué ha dado por bueno sin ejercitarlo** (p. ej. que la migración se comporta
  igual en una BD de 2 GB que en una de tres filas).
- **Qué cifras del arco son no reproducibles** desde el repositorio (E3) y qué
  conclusiones **no** dependen de ellas.
- **La deuda que el arco hereda y no toca**: G1–G7 en `pending`, el P0 de identidad
  abierto, los seis prefijos reservados sin informe (A5) y lo aparcado en
  `PARKED.md`.

---

## 6. Discrepancias declaradas a propósito, para que las dictamine

Se declaran **antes** de que las encuentre el auditor, para que el veredicto no sea
«lo escondieron» sino «lo dictaminaron»:

- **(i) El `Retry-After` es una constante de 5 s** con una ventana de 60 s
  (`security.py:247`), mientras la ruta de sesión lo calcula de verdad
  (`session.py:97`). La UI del perfil convierte esa constante en «El servidor pide
  esperar 5 s». **V3.79.0 hizo visible el freno, no lo volvió exacto.**
- **(ii) El primer commit del rango es documental y post-data el tag `v3.77.1`**
  (§0.1). Es consecuencia directa de que un tag publicado no se recrea.
- **(iii) Los candados del diálogo son de dos clases muy distintas:** un test que
  lee el **texto del CSS** (`dialogLayout.test.ts`) y un test **visual** de un solo
  viewport (`profileDialog.spec.ts`). El primero no prueba layout; el segundo prueba
  un caso. Se declara para que no se cuente como dos candados equivalentes.
- **(iv) La cifra «139 de 145» no es reproducible** desde el repositorio (E3).
- **(v) Los topes del pegado masivo son silenciosos** (E5): se recorta y se acota sin
  pedir permiso, con el contador real devuelto por el servidor como única señal.
- **(vi) La precedencia de la cara B hace que el pack curado no vuelva a verse** para
  una palabra que el alumno corrigió (E1). Borrar la propia corrección lo devuelve.
- **(vii) `V3.78.0` cambió el defecto de vista a `lookup`** (C1) y `V3.80.0` cambió
  el mazo de «lo que estabas mirando» a «selección única compartida» (E9): son
  cambios de comportamiento para el alumno que ya usaba la app.
- **(viii) La página de *Releases* de GitHub no cuenta la historia del producto.**
  Estaba detenida en `v3.33.0` y con ese `Latest` engañoso —ya lo declaró la entrada
  de `v3.77.1`—; se publica **una** Release para `v3.80.0` y **no** para `V3.77.2`,
  `V3.78.0` ni `V3.79.0`, así que el carril visible sigue siendo más pobre que los
  tags. El **ancla de auditoría es el tag**, no la página de Releases: si el auditor
  puntúa por lo que ve allí, está puntuando otra cosa.

---

## 7. Alcance

**Dentro:** todo el stack publicado en `v3.80.0` — `backend/`, `frontend/`,
`launcher/` (para verificar que **no** cambia en este arco), `scripts/`,
`docs/` y la documentación de release. Las cuatro releases del arco, su migración
aditiva, sus candados y sus afirmaciones.

**Fuera, y se declara:** la validación **pedagógica** (los gates G1–G7 siguen
`pending` y el árbol certificado sigue siendo `v3.75.8`); el **P0 de identidad**
(sigue abierto, ver `PLAN-P0-IDENTIDAD.md`); la calidad **acústica** de la voz y el
audio (este arco no los toca); y cualquier cosa que exija la **BD real del alumno** o
una **máquina limpia** (no hay ninguna de las dos publicada).

---

## 8. Nota de prefijos y cierre

El primer prefijo libre es **`AR`**, y **este es el punto de entrada que lo reserva**:
`docs/audit/AR-AUDITORIA-TOTAL-V380.md`. No se renombra ningún dossier ya publicado:
las reservas anteriores (`AG`, `AH`, `AI`, `AJ` de motor y pausa pedagógica; `AP` de
`v3.75.7`; `AQ` de `v3.77.1`) las declararon los propios puntos de entrada **dentro
de sus tags**, y reescribirlas sería falsear historia.

Este documento se entrega **en un commit documental posterior al tag `v3.80.0`**
(§0.1-ii), con el ancla en `v3.80.0`, y **sin mover producto**: el invariante 3 de
§1.1 es la prueba, y el auditor debe ejecutarlo antes de empezar a puntuar.
