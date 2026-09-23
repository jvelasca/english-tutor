# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.81.1`

> **ERRATA (2026-09-23, `v3.81.2`) — el invariante 3 de §1.1 ya no se cumple, y es
> correcto que no se cumpla.** Este documento sigue siendo válido **para el arco que
> audita** (`v3.80.0..v3.81.1`), pero declara como invariante que
> `git diff --stat v3.81.1..main -- backend frontend launcher scripts` sale
> **vacío** (§1.1, invariante 3). Eso era cierto cuando se entregó —`main` iba un
> commit por delante y era documental— y **deja de serlo con la publicación de
> `v3.81.2`**, que **sí** toca producto: el cierre de G0 (el historial deja de
> guardar el correo, el orden de `EVENT_PURGED` y el **octavo gate**
> `identidad-cuentas`). No es una violación del punto de entrada, es que **el ancla
> se ha movido**: para auditar el arco nuevo hace falta un punto de entrada propio
> anclado a `v3.81.2` (ver `release-notes-v3.81.2.md`, §«Para auditar esta
> release»). El detalle del cambio está en `release-notes-v3.81.2.md`.

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **la gestión de usuarios
> que convirtió «perfiles» en «cuentas»**, tal y como quedó publicada en el tag
> **`v3.81.1`**. La revisión es **de solo lectura**: no se cambia código, datos,
> configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué ahora.** La última entrada externa entregada es
> `agentes/auditoria-total-externa-v380.md` (ancla `v3.80.0`, informe esperado `AR`,
> **sin recibir**). Después de ella se publicaron **dos releases** sin punto de
> entrada propio: `V3.81.0` (la Fase 3 del P0 de identidad: cuentas con contraseña y
> email, alta y baja autoservicio, el PIN retirado y la consola de Usuarios del
> programa de gestión) y `V3.81.1` (el parche que arregló la **prueba visual que el
> CI de `v3.81.0` encontró roja**). Este documento cubre **las dos** con una sola
> etiqueta, porque `v3.81.1` **no toca ni una línea del producto**: es el mismo
> árbol más un fichero de pruebas, y separarlas daría dos auditorías del mismo
> código.
>
> **Aviso de encuadre (léelo antes de puntuar).** Esto **no** es la auditoría de un
> parche, y **tampoco** es la del arco anterior. `V3.81.0` hace algo que ninguna
> release de esta casa desde el P0 de identidad había hecho: **cambia el contrato de
> API de forma NO aditiva** (`PUT /api/session/pin` **desaparece** y
> `POST /api/session` **cambia de semántica**), **añade PII nueva** (el email),
> **añade la segunda excepción de red del producto** (el correo saliente), **retira
> un concepto entero** (el PIN), **toca por primera vez el lanzador en un arco de
> producto** y **abre una superficie sin sesión que antes no existía** (el registro
> de cuentas). Por eso **no se declaran** ni el invariante clásico «el diff de
> producto sale vacío» (sería falso: **50 ficheros** de producto no-test) ni el
> invariante «el contrato solo crece» (sería **falso por diseño**, y está declarado
> en `docs/audit/KIT-VALIDACION-GATES.md`). En su lugar se declaran **siete
> invariantes acotados** que sí pueden cumplirse o salir exactos (§1.1). Un
> invariante que no se puede cumplir **no se escribe**.
>
> **Estado del punto de entrada:** entregado 2026-09-23 en un **commit documental
> POSTERIOR al tag `v3.81.1`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md` y errata §0.1 de
> `agentes/auditoria-total-externa-v3757.md`). El ancla sigue siendo `v3.81.1` y el
> producto **no se ha movido** para entregar esto; el invariante que lo demuestra
> está declarado y se comprueba por comando (§1.1, invariante 3).
>
> **Informe esperado:** `docs/audit/AS-AUDITORIA-TOTAL-V381.md`. Prefijo **`AS`**
> porque es **el primer prefijo libre** (`AA`–`AF` los ocupan los dossiers de V3.70,
> `AG`–`AM` la serie de la pausa pedagógica además de los puntos de entrada de motor
> y pausa, `AO` la política psicométrica, `AN` el arco de `v3.75.1` y **`AR` el arco
> de `v3.80.0`**): **`AP`, `AQ` y `AR` siguen reservados por puntos de entrada sin
> informe recibido**. Ver la nota de prefijos en `PLAN.md`.

---

## 0.1 Errata heredada — el rango tiene TRES commits y el primero post-data el tag `v3.80.0`

> **Qué es esta nota y por qué va antes de todo.** Es la corrección de la única
> discrepancia de trazabilidad que ya sangró en la auditoría anterior, repetida aquí
> **a propósito** para que no vuelva a ocurrir: el rango `v3.80.0..v3.81.1` tiene
> **tres** commits, y **el primero** (`276fd8b`, `docs(audit): el punto de entrada de
> ARCO anclado a v3.80.0, post-tag y sin mover producto`) **no es de este arco**: es
> el **commit documental con el que se entregó la entrada externa anterior**, y por
> definición **post-data** el tag `v3.80.0` que aquella auditaba. El arco real son
> los **dos** commits de release que vienen después.

Es la deriva que V3.73.5 declaró cerrada y que **aquí se declara, no se oculta**. Si
el auditor considera que un commit documental posterior al tag deja desfasado el
ancla, **tiene razón por definición**, y el hallazgo es de proceso, no de producto:
la regla de que un tag publicado no se recrea hace **imposible** entregar un punto de
entrada *dentro* de su propio tag sin mover producto. El compromiso de esta casa es
declararlo.

```bash
git log --oneline v3.80.0..v3.81.1
# 3 líneas: 1 documental (276fd8b) + 2 de release (V3.81.0, V3.81.1)
git show --stat 276fd8b
# PLAN.md y agentes/auditoria-total-externa-v380.md: SOLO documentación
```

---

## 0.2 Errata propia — cuatro cifras del §1 estaban calculadas sobre el rango viejo

> **Qué es esta nota.** La corrección de un error **mío**, encontrado al preparar la
> publicación del Release de `v3.81.1`, y declarado aquí **antes** de que lo encuentre
> el auditor, porque este documento se publica **dentro** del tag y no se reescribe.

Este punto de entrada se commiteó en `2c413f9` (tag `v3.81.1`). Sus cifras del §1.1 y
el §1.3 se habían calculado sobre el rango `v3.80.0..v3.81.0` —**antes** de que
existiera el hotfix—, así que **no describían el rango que el propio documento
declara auditar** (`v3.80.0..v3.81.1`). Las cuatro cifras corregidas:

| Cifra | Declarada (mal) | Real (`v3.80.0..v3.81.1`) |
| --- | --- | --- |
| Ficheros totales del arco | 95 | **98** |
| Líneas totales | +12 520 / −2 094 | **+13 611 / −2 098** |
| Ficheros de `frontend/` | 37 | **38** |
| Ficheros `*.md` | 15 | **17** |

Las cifras de `backend/` (**31**) y `launcher/` (**10**) y la de **50 ficheros
no-test de producto** ya eran correctas: el hotfix solo añade un fichero de pruebas.
El error es **de método y tiene causa**: los números se midieron al escribir el
documento y **no se volvieron a medir cuando el rango ganó un commit**. Es
exactamente la misma clase de fallo que la errata heredada del §0.1 —**el rango se
movió y la prosa no**—, lo que la hace más incómoda y más útil de declarar.

**Cómo se entrega la corrección, y por qué así:** con un **cuarto commit
documental en `main`, POSTERIOR al tag `v3.81.1`** (`docs(audit): corrige el recuento
del arco y resuelve el CI del tag`). No se mueve el tag: **un tag publicado no se
recrea**. Consecuencias que el auditor debe tener en cuenta, y comprobar:

```bash
git log --oneline v3.81.1..main
# un commit documental: corrige el recuento del arco
git diff --stat v3.81.1..main -- backend frontend launcher scripts   # VACÍO
```

- **`main` va un commit por delante de `v3.81.1`**, y ese commit **no toca producto
  ni pruebas**: solo `agentes/auditoria-total-externa-v381.md`. El invariante de que
  el diff `v3.81.1..main` de `backend frontend launcher scripts` sale **vacío** sigue
  cumpliéndose, y es el que el auditor debe ejecutar **antes** de dar por bueno este
  texto.
- **Las cifras del §1.1 y el §1.3, tal y como las lee, son las corregidas.** Si el
  auditor quiere ver el error, está en el diff `v3.81.1..main` de este fichero.
- **La lección, escrita:** un recuento citado en un documento **caduca cuando el
  rango crece**. En este arco el rango creció *después* de escribirlo, y la disciplina
  que faltó es la que el §G2 pide al auditor: **volver a medir al cerrar**, no al
  escribir.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (la nota del rótulo que dejó el CI rojo y la de
   gestión de usuarios) y **§0 «START HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. Las **dos notas de release** de este arco: `release-notes-v3.81.0.md` (el cuerpo)
   y `release-notes-v3.81.1.md` (el parche del CI). La segunda existe **porque la
   primera salió con un job rojo**, y eso es parte de lo que se audita.
4. `docs/audit/PLAN-P0-IDENTIDAD.md` — el briefing del P0 de identidad. Su **§16** es
   la decisión de producto que este arco implementa, y sus **§15/§15.1** son las
   alternativas que se descartaron. Es la lectura que explica *por qué* hay cuentas.
5. `docs/audit/PARKED.md` — lo **aparcado a propósito**; su sección **`V3.81.0`** es
   la declaración honesta de lo que el arco **no** cierra.
6. `docs/PREMISAS.md` — la premisa «sin cuentas, sin contraseñas» que este arco
   **reescribe**: si el auditor encuentra esa premisa en una versión anterior, la
   que manda es la del árbol.
7. `docs/ARQUITECTURA.md` (§«Credencial por cuenta (V3.81)», §«Superficie sin
   sesión», §«Lanzador») — el mapa de lo que se añade y de lo que se retira.
8. `agentes/auditoria-total-externa-v380.md` — la entrada externa anterior (ancla
   `v3.80.0`), **cuyos dos invariantes este arco rompe a propósito**; conviene
   leerla para ver qué se prometió entonces y qué se ha decidido después.
9. `docs/BETA_GATES.md`, `docs/audit/KIT-VALIDACION-GATES.md` y
   `docs/audit/G7-MATRIZ-LECTURA.md` — los **7 gates**: **siguen en `pending`**.
10. `CHANGELOG.md` (las dos entradas), `backend/scripts/e2e_accounts_v381.py` (la
    prueba end-to-end que este arco añade) y `docs/audit/TEMPLATE.md` (formato del
    informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -6 main
```

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.81.1`** (el último del arco; `v3.81.0` está
  **dentro** del rango). Los identificadores exactos se **resuelven con git** en vez
  de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.81.1            # objeto del tag anotado
git rev-parse 'v3.81.1^{commit}' # commit de release (el SHA exacto que se audita)
git rev-parse 'v3.81.0^{commit}' # el commit del tag anterior
git rev-parse 'v3.80.0^{commit}' # commit base del arco (el ancla de `AR`)
git log -1 --format='%H %s' 'v3.81.1^{commit}'
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run de CI que dispara su
  push: son datos que solo existen **después** de publicar. Fijarlos obligaba a un
  commit de re-anclaje **posterior al tag**, que quedaba a su vez fuera del tag
  siguiente, y por eso `main` iba siempre por delante en documentación. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando** y este archivo es coherente **dentro de su propio tag**. Si un documento
  de este tipo vuelve a fijar un SHA o un run a mano, es una **regresión**.

- **Base de comparación:** `v3.80.0` (el ancla de la entrada externa anterior,
  `agentes/auditoria-total-externa-v380.md`). No es una comparación neutra y conviene
  decirlo: el arco de `v3.80.0` tiene su punto de entrada entregado y **su informe
  (`AR`) sin recibir**, así que la cadena heredada sigue acumulando **tres prefijos
  reservados sin dictamen** (`AP` de `v3.75.7`, `AQ` de `v3.77.1` y `AR` de
  `v3.80.0`), más los cuatro de motor y pausa (`AG`, `AH`, `AI`, `AJ`). Dictaminar si
  eso compromete la auditabilidad del producto es parte del trabajo (§2-A5).

- **Dos releases, un solo punto de entrada.** `v3.81.1` **no toca producto**: es
  `v3.81.0` más un fichero de pruebas (`frontend/tests/visual/profileDialog.spec.ts`)
  y los bumps de versión. `CHANGELOG.md` lleva una entrada por release y **solo
  `v3.81.0` y `v3.81.1` tienen tag**; el lote de estabilización que se iba a publicar
  como `v3.80.1` **nunca se publicó** y sus notas viven en
  `release-notes-v3.80.1.md` **como registro, no como release** — verifícalo:
  `git tag --points-at` no encuentra nada para él.

- **El árbol de certificación se mueve a `v3.81.0`, y solo ahí.** Los gates G1–G7 se
  congelaron en `v3.75.8`, siguen en **`pending`** y la campaña tiene **0 `record`**;
  este arco **re-ancla la base a `v3.81.0`** (por tag, sin SHA a mano) porque las
  cuatro releases desde `v3.75.8` añadieron producto y no había nada que invalidar.
  `v3.81.1` **no vuelve a moverla**: se diferencia en un fichero de pruebas.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Este arco **cambia producto** (**50 ficheros** no-test de `backend/`, `frontend/` y
`launcher/`; **98** en total contando documentación y pruebas: **+13 611 / −2 098**),
así que **no se declaran** ni el invariante «el diff de producto sale vacío» ni el de
«el contrato solo crece» —**serían falsos**, y el segundo **a propósito**—. Se
declaran **siete invariantes acotados**, cada uno con el comando que lo comprueba.

**(1) El contenido de currículum y evaluaciones: VACÍO.** Ni una línea, y con los
packs de vocabulario incluidos.

```bash
git diff --stat v3.80.0..v3.81.1 -- backend/curriculum
```

Debe salir **vacío**. Los tres packs (`backend/curriculum/vocab_packs/{food,travel,work}.json`)
y los exámenes no se tocan: este arco añade **identidad**, no contenido.
**Lo falsaría:** cualquier línea de salida. Sería un hallazgo **P0**.

**(2) Sin bumps pedagógicos ni de instrumento.** La **única** línea que cambia de
versión en `backend/` es `VERSION`:

```bash
git diff -U0 v3.80.0..v3.81.1 -- backend/config.py | grep -E '^[+-].*(VERSION|GENERATOR_VERSION|DECISION_POLICY|CURRICULUM_VERSION|LISTENING_BANK_VERSION)'
# solo: -VERSION = "3.80.0"  /  +VERSION = "3.81.1"
```

Los valores vigentes y **sin mover** son: `CURRICULUM_VERSION = "1.3.1"`,
`LISTENING_BANK_VERSION = "7.0.0"` (`backend/services/curriculum.py`),
`GENERATOR_VERSION = "1.4.0"` (`backend/services/dictionary_content.py`) y
`DECISION_POLICY_VERSION = "v3.68.0"`
(`backend/repositories/decision_records.py`). **Aviso para no confundir una cita con
un cambio:** el `grep` sobre `CHANGELOG.md`, `PLAN.md` o las notas **sí** nombra esas
constantes; lo que este invariante acota es el **diff de `backend/config.py`**, y por
eso el comando lo acota. **Lo falsaría:** una línea `+`/`-` con esas constantes.

**(3) El producto no se ha movido desde el tag.** El commit documental con el que se
entrega este punto de entrada **no toca producto**:

```bash
git diff --stat v3.81.1..main -- backend frontend launcher scripts
```

Debe salir **vacío** (verificado al entregar). Y el diff **completo** del rango
`v3.81.1..main` debe contener **solo documentación**: `agentes/auditoria-total-externa-v381.md`
y la fila de trazabilidad en `PLAN.md`, exactamente como se entregó la entrada
anterior (`276fd8b`: `PLAN.md` + `agentes/…v380.md`, sin más). **Lo falsaría:**
cualquier línea de producto en el diff, o cualquier fichero de más en el diff
completo. Sería **P0**.

**(4) La migración de BD es aditiva, idempotente y NO rellena nada.** `V3.81.0` añade
**ocho columnas** a `users` (`email`, `email_verified_at`,
`email_verify_token_hash`, `email_verify_sent_at`, `password_hash`,
`must_change_password`, `auth_epoch`, `unenrolled_at`) y **una tabla** (`user_events`),
con el idioma `PRAGMA table_info` + `ALTER TABLE` idempotente que ya existía. Las
filas viejas quedan con `email = ''` y `password_hash = ''` —la lectura honesta de
«esta cuenta no tiene credencial», que es la **deuda declarada** del P0— y **no se
inventa** una credencial ni un correo para tapar el hueco.

```bash
grep -n -A3 'user_cols' backend/repositories/db.py | head -40
cd backend && python -m pytest -q tests/test_foreign_keys.py::test_fk_migration_idempotent
# 1 passed: llama a db.init_db() DOS veces sobre la misma BD.
```

Ese test es **el que muerde** si alguien quita el `if`: sustituyendo la guarda por una
ejecución incondicional del `ALTER`, el candado falla con
`sqlite3.OperationalError: duplicate column name`. Es decir: **la idempotencia no
depende de un test que solo este arco conoce, sino de un candado que ya existía**.

La **aditividad sin pérdida** se demuestra además **por construcción**: el guion
end-to-end de este arco (`backend/scripts/e2e_accounts_v381.py`) trabaja sobre una
**copia** de una BD real —la del alumno, con sus datos y **sin** las columnas
nuevas—, la abre con el código de `main` y comprueba al final que **la BD original
conserva su sha256**. El auditor puede reproducirlo: es un comando, no una promesa
(§1.4). **Lo falsaría:** que el `ALTER` fallara sobre una BD vieja, que perdiera
filas, o que un valor por defecto distinto de `''` apareciera.

**(5) La superficie sin sesión está declarada, acotada y no crece por descuido.**
`V3.81.0` **abre dos escrituras nuevas sin sesión** (`POST /api/users`, el registro, y
`POST /api/account/verify`, la confirmación del correo) y **acota** las que exigen
sesión, incluida la ruta que cambia un secreto:

```bash
cd backend && python -m pytest -q tests/test_public_surface.py   # 6 passed
```

El candado comprueba **las dos direcciones**: que las rutas declaradas sin sesión
sigan respondiendo, y que las de datos **sigan dando 401 `SESSION_REQUIRED`** —con
`?user_id=` incluido, que es el parámetro que dejó de abrir nada en V3.75—. Además
**fija por escrito** que lo aceptado esté declarado en `docs/ARQUITECTURA.md`
(`test_la_superficie_sin_sesion_esta_declarada_por_escrito`). **Lo falsaría:** abrir
una ruta de datos sin sesión, cerrar una de las declaradas, o añadir una escritura
anónima nueva sin tocar la lista y la documentación.

**(6) El correo de las demás cuentas NO sale por la puerta de entrada.**
`GET /api/users` responde **sin sesión** (la puerta de entrada es un selector y tiene
que pintar nombres antes de que exista sesión), y en modo LAN eso significa que un
equipo de la red puede **enumerar nombres**. Lo que **no** puede es cosechar correos:
`backend/routers/users.py` los recorta en el borde HTTP y solo devuelve el de la
**propia** cuenta (el de la sesión, que ya lo conoce).

```bash
grep -n -B4 -A14 'def _without_foreign_email' backend/routers/users.py   # users.py:80
```

**Este invariante es verdad en el código y NO tiene candado.** Se declara aquí
**antes** de que lo encuentre el auditor, y el hallazgo de cobertura es suyo: **no hay
un test que lo fije** (§6-v, §2-D4). Es el hueco que esta entrada entrega a
propósito, porque taparlo habría movido el tag.

**(7) La consola de gestión tiene doble candado en las 14 rutas.** Todas las rutas
`/api/admin/*` —aprobar y rechazar solicitudes, alta directa, edición de datos,
credenciales, verificación a mano, activar/desactivar, baja forzada, historial,
purga y SMTP— exigen `dependencies.require_admin_local`: **PIN de administración
`y` petición desde el propio equipo**, fail-closed en las dos direcciones.

```bash
grep -c 'Depends(require_admin_local)' backend/routers/admin.py   # 14
grep -c '^@router\.' backend/routers/admin.py                     # 14
```

**Aviso honesto:** el candado **de regresión** que existe
(`test_toda_la_consola_exige_el_candado`) ejercita **4** de las 14 rutas, no las 14.
Que las 14 lo lleven es cierto **hoy** y se comprueba con los dos `grep` de arriba;
que siga siendo cierto mañana depende de leer el fichero, no del test (§6-vi).

### 1.2 Lista cerrada — los tres commits del rango

| # | Commit | Qué publica | Tag |
| --- | --- | --- | --- |
| 1 | `276fd8b` | **Documental, POSTERIOR a `v3.80.0`** (§0.1): el punto de entrada del arco anterior. No toca producto. | — |
| 2 | `6724d8b` | `release(v3.81.0)`: cuentas locales con contraseña, la baja que no borra y la consola de usuarios | **`v3.81.0`** |
| 3 | `2c413f9` | `release(v3.81.1)`: el rótulo que dejó el CI rojo (`Edit profile` → `Edit user` en un spec visual) | **`v3.81.1`** |

### 1.3 Lista cerrada — el diff del arco, por área

```bash
git diff --shortstat v3.80.0..v3.81.1            #  98 files changed, 13611+/2098-
git diff --shortstat v3.80.0..v3.81.1 -- backend #  31 files changed,  4628+/ 864-
git diff --shortstat v3.80.0..v3.81.1 -- frontend#  38 files changed,  3628+/ 839-
git diff --shortstat v3.80.0..v3.81.1 -- launcher#  10 files changed,  1928+/ 273-
git diff --shortstat v3.80.0..v3.81.1 -- '*.md'  #  17 files changed,  3418+/ 117-
```

**`backend/` (31).** Nuevos: `services/credentials.py` (el relevo de `pins.py`:
PBKDF2, política, freno por cuenta, tokens de email), `services/mailer.py` (correo
saliente fail-closed), `routers/account.py` (verificación de email, reenvío y baja
autoservicio), `scripts/e2e_accounts_v381.py` (la prueba end-to-end) y los tests
`test_accounts_v381.py` (**34**), `test_credentials.py` (**52**) y
`test_mailer_v381.py` (**17**). **Borrado:** `services/pins.py` y su `tests/test_pin.py`
(el PIN se retira como concepto). Modificados: `config.py` (bump + ajustes SMTP),
`security.py` (los cupos de las rutas nuevas), `dependencies.py` (época de
autenticación, baja y contraseña temporal), `repositories/db.py` (migración aditiva),
`repositories/users.py` (eventos y estados), `routers/{session,users,admin}.py`,
`schemas/{users,profiles}.py`, `services/{sessions,backup}.py`,
`domain/{users,profile_requests}.py`, `main.py` y los tests
`test_{sessions,public_surface,user_profile,profile_requests_v377,runtime_audit_v371}.py`.

**`frontend/` (38).** Nuevos: `components/AccountDialog.tsx` (+ **21** tests),
`utils/credentials.ts` (+ **8** tests) y los dos specs visuales permanentes
(`tests/visual/dictionarySmoke.spec.ts`, `flashcardsSmoke.spec.ts`). **Borrados:** la
pestaña de PIN de Ajustes con sus cadenas, y `utils/pin.ts` con su
`utils/pin.test.ts`. Modificados: `components/{UserMenu,
ProfileGate,ProfileDialog,SettingsDialog}.tsx`, `App.tsx`, `app/Header.tsx`,
`hooks/{useChat,useTabList}.ts`, `api/{session,users}.ts`, `utils/{i18n,session}.ts`,
`types/api.ts`, la familia de `features/vocabulary/` (los arreglos del lote 1) y sus
tests, más `tests/visual/profileDialog.spec.ts` (**el fichero de `v3.81.1`**).

**`launcher/` (10) — por primera vez en un arco de producto.** `admin.py` (el cliente
de la consola), `ui.py` (la sección de Usuarios y la conciliación del SMTP),
`launcher.py` (aplicar el PIN de verdad, reiniciando), `status.py` (el contador
honesto de solicitudes leyendo la BD), `core.py` y `config_store.py` (ajustes SMTP),
más cuatro ficheros de test. **Total del lanzador: 244 tests.**

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
SHA=$(git rev-parse 'v3.81.1^{commit}')
gh run list --commit "$SHA" --limit 5
gh run view <run_id> --json jobs -q '.jobs[] | .conclusion + "  " + .name'
python scripts/check_release_consistency.py  # OK: Release consistency (3.81.1)
git diff --stat v3.81.1..main -- backend frontend launcher scripts   # vacío
```

**A fecha de entrega (2026-09-23)**, y el auditor debe **re-resolverlo** porque los
datos de CI **no forman parte del repositorio**: la run del commit del tag
(`35851931672`, workflow `CI`, evento `push`, `headSha = 2c413f9`) terminó con
**`conclusion = success`: 12 jobs y los 12 en `success`**, incluido el
`Playwright E2E (visual)` que estaba rojo en `v3.81.0`. La consistencia de versión
salió `OK` —una fuente de verdad (`backend/config.py::VERSION`) y **cinco** sitios
comprobados por el gate (`SOURCES` de `scripts/check_release_consistency.py`:
`frontend/package.json`, `frontend/package-lock.json`, `README.md`, `CHANGELOG.md` y
`PLAN.md`; las notas los llaman «**6 orígenes**» contando también la fuente de
verdad— **es el mismo hecho contado de dos formas, no una discrepancia**) y el
invariante 3 salió vacío.

**El dato que hace honesto este punto de entrada: el CI de `v3.81.0` NO estaba
verde.** La run de su commit (`gh run list --commit 6724d8be…`) salió **11 de 12** y
el rojo era **`Playwright E2E (visual)`**, con `6 failed · 28 skipped · 50 passed`:
las dos pruebas de `profileDialog.spec.ts` en los tres breakpoints, por buscar el
rótulo `"Edit profile"` cuando la app dice `"Edit user"` desde el renombrado de
V3.81.0. Eso es **`v3.81.1`**, y el detalle completo está en `release-notes-v3.81.1.md`.
**Si el auditor audita solo `v3.81.0`, está auditando una release con un job rojo**;
el ancla de esta entrada es `v3.81.1` precisamente por eso.

**Aviso para no atribuir a la etiqueta lo que no es suyo:** el CI **no corre en
tags** (`.github/workflows/ci.yml` dispara en `push: branches: [main]` y en
`pull_request`). La run que **certifica** el commit del tag es, por tanto, la del
**push a `main`** de ese mismo commit —mismo árbol, misma run—, y así se resuelve con
`gh run list --commit "$SHA"`. Un tag no dispara ni puede disparar nada: quien audite
«el CI del tag» está auditando el CI del commit al que apunta el tag.

**Y una advertencia de método que este arco deja escrita:** el CI de `v3.81.0` pasó
**once** jobs verdes y **uno** rojo, y ese uno era visual. El barrido visual **no es
el que más corre en local** (§6-x). Un job rojo hace roja la release entera, y esta
casa lo aprendió publicando: **el CI es la autoridad, y mirarlo es parte de publicar,
no un extra.**

---

## 2. Preguntas falsables por área

Cada pregunta se responde **con evidencia del repositorio** (fichero:línea, comando
o test). «El test no lo demuestra» y «el motor no lo cumple» son **dos veredictos
distintos** y hay que elegir uno.

### A. El ancla, el historial y el carril de cierre

- **A1.** ¿El rango `v3.80.0..v3.81.1` tiene **tres** commits y el primero es
  **documental** (§0.1)? `git log --oneline v3.80.0..v3.81.1`. **Dictamina:** ¿es
  aceptable que un commit ajeno al arco viaje dentro del rango auditado?
- **A2.** ¿Es coherente anclar en `v3.81.1` y entregar el punto de entrada en un
  commit **posterior** al tag? ¿La alternativa (mover el tag) habría sido peor?
  **Dictamina** con la regla de `KIT-VALIDACION-GATES.md` delante — y ten en cuenta
  que **`v3.81.1` existe precisamente porque no se movió `v3.81.0`**.
- **A3.** Solo `v3.81.0` y `v3.81.1` tienen tag. ¿El lote `v3.80.1` **sin publicar**
  (con notas propias) es una **decisión declarada** o un hueco de trazabilidad?
  Compáralo con `V3.77.2`/`V3.78.0`/`V3.79.0`, que tampoco llevan etiqueta.
- **A4.** `scripts/check_release_consistency.py` toma **una** fuente de verdad
  (`backend/config.py::VERSION`) y la comprueba contra **cinco** sitios. Desde
  V3.75.8 la Ayuda del alumno muestra además la versión de la **compilación**
  (`frontend/src/utils/buildInfo.ts`, que la lee del `package.json` en tiempo de
  compilación). ¿Es esa una sexta fuente que el guion **no** cubre —y puede
  divergir del `dist` que hay en disco—? Si el auditor encuentra un origen real
  fuera del guion, es un hallazgo de **gate**, no de producto.
- **A5.** **La cadena heredada:** siete prefijos reservados sin informe (`AG`, `AH`,
  `AI`, `AJ`, `AP`, `AQ`, `AR`). ¿Es auditable un producto que acumula entradas
  externas sin dictamen? ¿Debería el proceso bloquear la entrega de una entrada nueva
  hasta recibir la anterior, o el desbloqueo es precisamente acumular contexto?
- **A6.** ¿El CI del commit del tag está verde **hoy** y **con todos sus jobs**?
  (§1.4). Si algún job hubiera cambiado de estado, **eso** es el hallazgo. Y
  comprueba explícitamente el job **`Playwright E2E (visual)`**, que es el que
  `v3.81.1` viene a arreglar.

### B. El lote de estabilización (lo que se publicó con `v3.81.0`)

- **B1.** **La carrera entre generar el reverso y editarlo.** `hydrate()` lanza una
  promesa que puede tardar hasta 120 s (modelo local) y `saveOwnBack()` escribe
  después: ¿el **token por tarjeta** (`hydrationEpoch`) más el espejo síncrono
  (`ownBacksRef`) cierran la carrera **en los dos sentidos** (respuesta tardía del
  modelo que llega después de guardar; y guardar/borrar que llega después de la
  respuesta)? Busca el candado en `frontend/src/features/vocabulary/StudySession.test.tsx`
  y **dictamina si una promesa diferida de un test demuestra algo sobre un modelo
  real que tarda 120 s**.
- **B2.** **El badge «Tu versión» sobre una traducción borrada.** ¿Borrar la
  traducción propia **desmarca** el badge y **restaura** la cara efectiva que sirvió
  el backend, o queda un badge sobre un texto que ya no existe? ¿Y si no había cara
  previa? Compara `saveOwnBack()`/`clearOwnBack()` con lo que afirma la nota.
- **B3.** **La `X` del diccionario.** `clearQuery()` limpia **todo** lo que depende de
  la consulta sin disparar ninguna petición. ¿Queda algún estado de la consulta
  anterior vivo (contador de práctica, error de red, «añadido», `lastQuery`)? Un
  estado que sobrevive a la limpieza es un estado que **miente**.
- **B4.** **Las pestañas ARIA.** Los tres modos del diccionario y las cuatro vistas de
  Flashcards pasan a `tablist`/`tab`/`tabpanel` con el hook `useTabList` (roving
  tabindex y flechas). ¿La asociación `tab`↔`tabpanel` es **completa y única**
  (`aria-controls`/`aria-labelledby` sin ids huérfanos ni duplicados)? ¿Y el foco
  vuelve donde debe al cambiar de vista?
- **B5.** **El `lang` de las tarjetas manuales.** Se aplica solo cuando el idioma se
  conoce y se omite en las manuales. ¿Queda algún sitio donde una tarjeta manual siga
  declarando `lang="en"` o `lang="es"`? `grep -rn 'lang=' frontend/src` y dictamina
  si «omitir» es la lectura honesta o una deuda.
- **B6.** **La sonda visual permanente.** `dictionarySmoke.spec.ts` y
  `flashcardsSmoke.spec.ts` corren en tres breakpoints sin `skip` y mockean `/api/**`.
  Verifica que los mocks se anclan al **origen** y no a globs por endpoint: la trampa
  está documentada en el propio repo (`**/api/settings*` casa también con el módulo
  `/src/api/settings.ts` y **la app no arranca**). ¿Hay un helper compartido que la
  haga imposible, o sigue siendo disciplina de quien escribe el spec? **Dictamina
  qué clase de candado es.**
- **B7.** **La cola de solicitudes del lanzador.** `read_pending_requests` lee la BD
  en solo-lectura y distingue `0` («cola vacía») de `None` («no se pudo leer»), y
  `pending_view` separa los estados. ¿Se mantiene la promesa «**contar no es
  decidir**» (sin PIN se cuenta y se anuncia, pero no se resuelve)? ¿Y el reinicio del
  servidor al guardar el PIN es aceptable desde el punto de vista del alumno que está
  usando la app en ese momento?

### C. La cuenta y su credencial (el núcleo de la Fase 3)

- **C1.** **El KDF.** `services/credentials.py` usa **PBKDF2-HMAC-SHA256** con
  **200 000** iteraciones, **sal por cuenta** y `hmac.compare_digest`. ¿La iteración
  se guarda **dentro** del valor (para poder subirla sin invalidar los hashes
  existentes)? ¿`verify_password` falla **cerrado** ante un valor corrupto o truncado
  en vez de lanzar excepción hacia la ruta? Un `verify` que revienta con una fila
  manipulada es un hallazgo de disponibilidad.
- **C2.** **La política de contraseña.** `is_valid_password` rechaza longitudes fuera
  de rango, espacios en los extremos y el carácter único repetido, y la lista de
  contraseñas **obvias** vive **solo** en el servidor. ¿Puede el cliente (o un
  formulario) saltarse esa lista y crear una cuenta con `12345678`? Si puede,
  **dictamina** si eso es una decisión declarada o un agujero —y busca qué la acota
  realmente (¿el freno? ¿nada?).
- **C3.** **El freno por cuenta.** 5 fallos no frenan; después el retardo dobla con
  techo de **300 s** y se limpia al acertar. Verifica: (a) que es **por cuenta** y no
  por IP (una familia tras un NAT no se frena entre sí); (b) que es **en memoria del
  proceso** —y por tanto se reinicia con el servidor— y que eso está **declarado**;
  (c) que el `Retry-After` que se devuelve aquí es el **tiempo real**
  (`int(espera) + 1`) y no una constante. Compáralo con el `Retry-After` del
  middleware, que **sí** es una constante (§6-iv).
- **C4.** **La revocación por época.** `users.auth_epoch` se comprueba en
  `dependencies.current_user` en **cada** petición, y un desajuste da **401
  `SESSION_STALE`** (no 403). Verifica que: (a) cambiar la contraseña **sube** la
  época y tumba las sesiones vivas; (b) **forzar la baja** también; (c) el que
  cambia su contraseña **no se echa a sí mismo** (se reemite la cookie); y (d) la
  sesión de la **baja autoservicio** queda inservible al instante. Si algún camino
  cambia la credencial **sin** subir la época, es un **P0** de seguridad.
- **C5.** **La contraseña temporal.** `must_change_password` bloquea con **403
  `PASSWORD_CHANGE_REQUIRED`** en cada petición, y la exención es literal
  (`_PASSWORD_CHANGE_ALLOWED_PATHS = {"/api/session", "/api/session/password"}`).
  **Dictamina la lista de excepciones**: ¿es lo bastante corta? ¿Puede el alumno, con
  una temporal puesta, hacer algo que contradiga «una contraseña temporal deja de ser
  temporal en cuanto se usa»?
- **C6.** **El PIN se retira.** `PUT /api/session/pin` **desaparece**,
  `services/pins.py` y `tests/test_pin.py` se **borran**, `frontend/src/utils/pin.ts`
  y su test también, y `pin_hash` se **conserva** en la tabla sin leerse. Verifica que
  (a) **no queda ninguna ruta** que lo lea o lo escriba; (b) **no queda ninguna
  cadena de UI** de PIN ni ninguna referencia al módulo borrado
  (`grep -rn 'utils/pin\|pin_hash\|PIN' frontend/src backend --include=*.ts* --include=*.py`);
  (c) retirar un endpoint sin versionado es **una ruptura declarada**, y está
  declarada en `docs/audit/KIT-VALIDACION-GATES.md` y en las notas. **Dictamina** si
  declararla basta.
- **C7.** **La cuenta heredada sin credencial sigue entrando nombrando.**
  `_require_password_if_set` no hace nada si `password_hash == ''`, y eso es **deuda
  declarada**, no un descuido: la consola las lista con el contador `without_password`
  como «lista de tareas». **Dictamina:** ¿es aceptable publicar una gestión de
  usuarios profesional con una puerta que sigue abierta para las cuentas viejas,
  mientras el contador no llegue a cero? ¿Y es medible ese contador en una
  instalación real, o solo en la consola del webmaster?

### D. Registro, email, baja y PII

- **D1.** **El registro autoservicio.** `POST /api/users` **sin sesión**, acotado por
  `is_admin_loopback_host`. Verifica: (a) que un equipo de la **LAN** no puede crear
  cuentas (por la red solo se **solicita**); (b) que el `409` distingue
  `USER_NAME_TAKEN` de `EMAIL_TAKEN` **a propósito** y que eso no es un oráculo
  inaceptable; (c) que el KDF se paga **antes** de decir que sí, y que el cupo de
  `/api/users` (60/min) acota un barrido. Si el registro es alcanzable desde la LAN,
  es **P0**.
- **D2.** **El token de verificación.** 256 bits, de un solo uso, guardado
  **hasheado** (`email_verify_token_hash`), con caducidad de una hora y consumido al
  usarlo. Verifica que (a) un token **caducado** no verifica y `_is_expired` falla
  **cerrado** ante una fecha ilegible; (b) el canje **no exige sesión** (el enlace
  puede abrirse en otro navegador) y por eso lo que autoriza es el token, no la
  cookie; (c) **no se filtra** en la respuesta ni en un log.
- **D3.** **El correo saliente es la segunda excepción de red.** Declarado en
  `backend/scripts/audit_dossier.py::RUNTIME_TOUCHPOINTS` (`kind: "internet"`) y
  **fail-closed**: sin SMTP configurado **no se abre ninguna conexión** (se comprueba
  **antes** de tocar `smtplib`) y un fallo de envío **no rompe** la petición. Verifica
  las dos cosas **por su candado** (`tests/test_mailer_v381.py`, **17** tests) y
  comprueba que el candado **muerde**: orden de comprobación, `STARTTLS` en 587, TLS
  implícito en 465 y **timeout de 10 s** (un SMTP que no responde no puede dejar
  colgada la pantalla de alta). **Dictamina** el `except Exception` ancho del envío.
- **D4.** **El recorte de PII (§1.1, invariante 6).** El email de las demás cuentas se
  recorta en el borde HTTP de `GET /api/users`, y solo la propia cuenta lo ve. **No
  tiene candado.** Escribe el test que lo falsaría (dos cuentas, petición sin sesión,
  exigir `email == ""` en la ajena) y **dictamina la severidad**: ¿es un hallazgo de
  cobertura o de producto? Ojo al detalle: la ruta **también** recorta
  `must_change_password`, y el email **sí** viaja entero en `/api/admin/users` detrás
  del doble candado, que es deliberado.
- **D5.** **La baja no borra nada.** `POST /api/account/unenroll` (con la contraseña)
  marca la cuenta, sube la época, cierra la sesión y **no toca la evidencia**. La
  purga es del webmaster, con **copia previa** y confirmación **por nombre**.
  Verifica: (a) que la baja **no** borra ni una fila de datos del alumno; (b) que
  reactivar devuelve la cuenta al servicio y el historial lo distingue de una
  desactivación; (c) que la purga **exige** que la cuenta esté fuera de servicio; (d)
  que el `409` de la purga **no distingue** cuál de las condiciones falló (para no
  dar un oráculo de qué cuentas existen). **Dictamina** si ese hermetismo es
  aceptable en un producto local de un solo webmaster.
- **D6.** **El historial sobrevive a la purga.** `user_events` **no** se borra con la
  cuenta, y es el único sitio que responde «¿quién borró esto y por qué?». Verifica
  que cada acción que cambia el estado de una cuenta deja fila, y que la purga
  **añade** la suya en vez de llevarse las anteriores.
- **D7.** **El email es un dato de persona y un `PATCH` lo cambia.** Cambiar el correo
  exige contraseña (aunque haya sesión) y **reinicia la verificación**. ¿Por qué es
  obligatorio? ¿Y qué pasa con el email **anterior**: queda en el historial, se
  sobrescribe? Dictamina la trazabilidad de una PII que cambia.

### E. La consola de gestión (el lanzador)

- **E1.** **El doble candado (§1.1, invariante 7).** PIN **y** loopback, fail-closed
  en las dos direcciones. Verifica las 14 rutas por `grep` **y** dictamina la fuerza
  del candado de regresión, que ejercita **4**.
- **E2.** **El PIN de administración viaja en una cabecera.** Está declarado como
  aceptable porque la administración es **local** y va detrás del loopback. **Dictamina
  si un PIN en una cabecera por HTTP en claro (el backend puede servirse por HTTP en
  el equipo) es aceptable**, y qué pasa si alguien activa el modo LAN.
- **E3.** **La consola edita los datos de una cuenta con más autoridad que su dueño.**
  El webmaster puede corregir el email (el alumno necesita su contraseña para eso) y
  cambiar el nombre. ¿Deja eso **traza** en `user_events` con el sujeto correcto —la
  cuenta afectada— y no con el webmaster? Si el historial se atribuye a quien actúa y
  no a quien lo sufre, la respuesta a «¿por qué mi cuenta está así?» se pierde.
- **E4.** **La contraseña temporal se muestra una vez.** `POST /api/admin/users` y
  `…/credentials` devuelven `temporary_password` **en la respuesta** y la marcan
  `must_change_password`. Verifica que **no** se guarda en claro en ningún sitio
  (ni log, ni BD, ni `config.json`) y que el webmaster **no puede** recuperarla
  después. Si se puede recuperar, es **P0**.
- **E5.** **El SMTP del lanzador.** La contraseña vive en `data/mail.secret` y **no**
  sale por `/api/admin/smtp` (solo `has_password`). Verifica: (a) que la frase de la
  consola **concilia** lo guardado con lo que ve el backend **en marcha** (el backend
  resuelve su entorno al arrancar, así que un cambio no aplica sin reiniciar); (b) que
  «probar envío» dice la verdad cuando no hay SMTP; (c) que el secreto **no** viaja en
  el backup (y `session.secret` tampoco) mientras el `password_hash` **sí**
  (§6-viii), que es lo coherente: el hash es estado de la cuenta, los secretos de
  máquina no.
- **E6.** **Los contadores de la consola.** `without_password` y `unverified_email`
  son «listas de tareas». ¿Se calculan sobre las **mismas** filas que se pintan, o
  pueden contradecirse (un contador que dice 3 y una lista que enseña 2)? Busca el
  candado.

### F. La prueba end-to-end y la evidencia del arco

- **F1.** **El guion E2E trabaja sobre una COPIA de la BD real.** Verifica el
  invariante que lo hace honesto: copia, arranca el backend de verdad en loopback,
  recorre el contrato y **comprueba al final que la BD original conserva su sha256**.

```bash
cd backend && python scripts/e2e_accounts_v381.py
# 62/62 pasos, 0 fallos (declarado en release-notes-v3.81.0.md)
```

  **Dictamina** dos cosas: (a) que la prueba **no** toca la BD de la que copia; (b)
  que un guion de verificación que arranca un servidor **está declarado** donde
  toca —lo está, en `tests/test_runtime_audit_v371.py::NON_PRODUCT_NETWORK_FILES`,
  con su motivo— y que eso **no** es una puerta por la que entre red en ruta de
  producto. El auditor debe intentar **romper la declaración**: ¿hay alguna otra
  primitiva de red sin declarar en el repo?
- **F2.** **La cifra `62/62` no es reproducible sin SMTP ni sin Ollama**, y eso hay
  que decirlo. ¿Qué pasos del guion **dependen de un servicio externo** y cuáles no?
  La regla de esta casa es **declarar** las cifras no reproducibles (§5).
- **F3.** **La prueba visual que se quedó atrás.** `v3.81.1` existe porque un
  **renombrado de i18n** rompió un spec que buscaba un texto. Verifica que (a) no
  queda **ningún otro** spec visual buscando cadenas renombradas por V3.81.0 —
  `grep -rn 'Edit profile\|Choose your profile\|Ask for a profile\|Remove this
  profile\|Enter your PIN' frontend/tests/` debe salir **vacío**—; (b) que el spec
  arreglado busca el rótulo por **una** constante; y (c) **dictamina el hueco de
  método**: ¿debería el barrido visual completo ser un **pre-requisito** de publicar,
  del lado del desarrollador y no solo del CI?
- **F4.** **El CI no corre en tags** (§1.4) y el estado se **re-resuelve**. ¿Es
  aceptable que «una release está verificada» signifique «la run del push a `main` de
  ese mismo commit salió verde»? **Dictamina el proceso**, no el producto.

### G. Deriva documental

- **G1.** Las notas de `v3.81.0` citan la evidencia visual así: «Playwright
  `dictionarySmoke` + `flashcardsSmoke` | **6/6** en los 3 breakpoints». Es **cierto**
  y a la vez **insuficiente**: no dice nada del barrido completo, que es donde estaba
  el fallo. **Dictamina** si una nota puede declarar solo lo que se corrió, y si eso
  es honestidad o es una forma de no mentir diciendo poco.
- **G2.** ¿Los números de las notas cuadran con el árbol publicado? Empieza por los
  que se pueden contar: `pytest --collect-only -q | tail -1`,
  `frontend` → `npx vitest run`, `launcher` → `pytest --collect-only -q`, y los
  recuentos citados (`test_accounts_v381.py` **34**, `test_credentials.py` **52**,
  `test_mailer_v381.py` **17**, `AccountDialog.test.tsx` **21**,
  `credentials.test.ts` **8**).
- **G3.** ¿`PLAN.md` dice lo mismo que las notas y que `CHANGELOG.md`, y `README.md`
  anuncia `3.81.1`? (El gate comprueba la **cadena** de versión, no la **coherencia de
  las afirmaciones**: eso lo dictamina el auditor.)
- **G4.** **La premisa que este arco reescribe.** `docs/PREMISAS.md` decía «sin
  cuentas, sin contraseñas». ¿Está reescrita de forma que un lector nuevo **no**
  pueda encontrarla en su versión vieja y creerla vigente? ¿Queda algún documento del
  repo afirmando lo contrario de lo que hace el código?
- **G5.** Los artefactos generados (`docs/audit/generated/i18n-report.{json,md}`,
  `release-validation.{json,md}`, `contrast-report.md`) se regeneran con un comando
  del repo. ¿Es reproducible lo publicado? Si el comando no existe o no reproduce, es
  un hallazgo de trazabilidad.

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
| B7 | | | |
| C1 | | | |
| C2 | | | |
| C3 | | | |
| C4 | | | |
| C5 | | | |
| C6 | | | |
| C7 | | | |
| D1 | | | |
| D2 | | | |
| D3 | | | |
| D4 | | | |
| D5 | | | |
| D6 | | | |
| D7 | | | |
| E1 | | | |
| E2 | | | |
| E3 | | | |
| E4 | | | |
| E5 | | | |
| E6 | | | |
| F1 | | | |
| F2 | | | |
| F3 | | | |
| F4 | | | |
| G1 | | | |
| G2 | | | |
| G3 | | | |
| G4 | | | |
| G5 | | | |

Veredicto por **área** (A–G) y **veredicto global**, con la misma escala que las
auditorías anteriores: **P0** (rompe una promesa publicada, corrompe datos o expone al
alumno) · **P1** (funciona mal de verdad para el alumno) · **P2** (deuda con riesgo) ·
**P3** (limpieza). Y, como siempre, **la distinción que más importa**: «el test no
demuestra» **no** es lo mismo que «el motor no cumple».

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
   el guion E2E trabaja sobre una **copia** y su resultado en una BD real del alumno
   con diez años de historia puede diferir de una BD recién creada. Si una cifra solo
   se sostiene con la BD real, el hallazgo es **de método** (F2).
6. **El CI vive en GitHub, no en el repo.** El estado de publicación se
   **re-resuelve** (§1.4); un run de hoy no prueba lo que pasó al publicar. Y un tag
   **no dispara CI**: se audita la run del push de su commit.
7. **Pregunta cuando no puedas falsar.** Es mejor «no concluyente» con el motivo
   escrito que un veredicto inventado.
8. **La release que se audita tiene una historia incómoda y está en el repo.** El CI
   de `v3.81.0` salió rojo y por eso existe `v3.81.1`. No es un detalle a ignorar
   ni un pecado a castigar dos veces: es la evidencia de que el CI **funciona**.

---

## 5. Honestidad esperada del informe

El informe debe declarar, en su propia sección de honestidad:

- **Qué no ha podido comprobar** (y por qué): el estado histórico del CI, la BD real
  del alumno, el comportamiento en el navegador objetivo si no lo tiene, y **el envío
  real de un correo** (sin SMTP configurado el producto no abre ninguna conexión, que
  es justo lo que promete).
- **Qué ha dado por bueno sin ejercitarlo** (p. ej. que la migración aditiva se
  comporta igual en una BD de 2 GB que en una de tres filas, o que un KDF a 200 000
  iteraciones es suficiente en el equipo del producto).
- **Qué cifras del arco son no reproducibles** desde el repositorio (F2) y qué
  conclusiones **no** dependen de ellas.
- **La deuda que el arco hereda y no toca**: G1–G7 en `pending` con la base re-anclada
  a `v3.81.0`, el **P0 de identidad abierto para las cuentas heredadas sin
  credencial** (C7), los siete prefijos reservados sin informe (A5) y lo aparcado en
  `PARKED.md`.
- **Lo que este arco decide y no implementa**, que es mucho y está declarado: sin
  recuperación de contraseña por correo, sin 2FA, sin verificación **obligatoria**
  para usar la app, `GET /api/users` enumerando **nombres**, freno **en memoria**, y
  el hash de la contraseña **viajando en el backup**.

---

## 6. Discrepancias declaradas a propósito, para que las dictamine

Se declaran **antes** de que las encuentre el auditor, para que el veredicto no sea
«lo escondieron» sino «lo dictaminaron»:

- **(i) El contrato de API deja de ser aditivo.** `PUT /api/session/pin` **se retira**
  y `POST /api/session` **cambia** (exige contraseña si la cuenta la tiene). Es la
  primera ruptura de contrato del P0 de identidad desde V3.75 y está declarada en
  `docs/audit/KIT-VALIDACION-GATES.md`, en `docs/audit/G7-MATRIZ-LECTURA.md` y en las
  notas. **No hay versionado de API** que la suavice: el producto es local y de un
  solo usuario por máquina, y esa es la justificación declarada.
- **(ii) El primer commit del rango es documental y post-data el tag `v3.80.0`**
  (§0.1). Es consecuencia directa de que un tag publicado no se recrea.
- **(iii) `v3.81.1` existe porque el CI de `v3.81.0` salió rojo.** Se declara el
  hecho, su causa (un rótulo de i18n renombrado sin actualizar el spec), su hueco de
  método (solo se corrió la parte nueva del barrido visual) y su arreglo. La release
  publicada con el job rojo **no se reescribe**.
- **(iv) El `Retry-After` del middleware sigue siendo una constante de 5 s**
  (`backend/security.py`) con una ventana de 60 s, mientras la ruta de sesión **sí**
  calcula el tiempo real. Es deuda **heredada** de V3.79.0 que este arco **no cierra**,
  y ahora convive con un tercer sitio que sí lo calcula bien (el freno de cuenta).
- **(v) El recorte de PII de `GET /api/users` NO tiene candado** (§1.1, invariante 6;
  §2-D4). El código lo hace; la prueba que lo fijaría, no existe.
- **(vi) El candado de la consola ejercita 4 de sus 14 rutas**
  (`test_toda_la_consola_exige_el_candado`). Que las 14 estén detrás del doble candado
  es cierto **hoy** y se comprueba con dos `grep`; lo que el test **no** garantiza es
  que una ruta **nueva** no se añada sin candado.
- **(vii) El lanzador se toca por primera vez en un arco de producto** (10 ficheros,
  +1 928/−273). El invariante «el lanzador no se mueve» **desaparece** respecto a la
  entrada de `v3.80.0`; en su lugar se declara uno propio (invariante 7).
- **(viii) El hash de la contraseña viaja en el backup** (`services/backup.py`) porque
  es **estado de la cuenta**, mientras `session.secret` y `mail.secret` **no** viajan
  (son secretos de máquina). Quien tenga un backup puede atacar el KDF **fuera de
  línea**, y el freno en memoria no le frena.
- **(ix) `pin_hash` sigue en la tabla, sin leerse.** Borrar una columna de una BD viva
  es un riesgo con cero beneficio; el coste es que la columna se queda como
  testigo del pasado.
- **(x) El barrido visual completo no es fiable en la máquina de desarrollo.** Ya está
  declarado en las notas de `v3.81.0` (honestidad (v)): bajo carga en paralelo da
  fallos que **pasan en aislamiento** —comprobado: `smoke.spec.ts` y
  `keyboard.spec.ts` pasan sueltos—. La autoridad del barrido completo es el **CI**.
  Esto **no** es la causa del rojo de `v3.81.0`: aquel fallo era determinista, y por
  eso llegó también al CI.
- **(xi) La página de *Releases* de GitHub no cuenta la historia del producto.** Estuvo
  detenida en `v3.33.0` hasta que se publicó una para `v3.80.0`; `V3.77.2`, `V3.78.0`,
  `V3.79.0` y `V3.80.1` **no** tienen página. El **ancla de auditoría es el tag**, no
  la página de Releases: si el auditor puntúa por lo que ve allí, está puntuando otra
  cosa.

---

## 7. Alcance

**Dentro:** todo el stack publicado en `v3.81.1` — `backend/`, `frontend/`,
`launcher/`, `scripts/`, `docs/` y la documentación de release. Las dos releases del
arco, su migración aditiva, sus candados, sus afirmaciones y **su historia de CI**.

**Fuera, y se declara:** la validación **pedagógica** (los gates G1–G7 siguen
`pending`); la calidad **acústica** de la voz y el audio (este arco no los toca); el
**envío real de correo** sin un SMTP configurado; y cualquier cosa que exija la **BD
real del alumno** o una **máquina limpia** (el guion E2E trabaja sobre una copia, y
eso es una copia, no la máquina del alumno).

---

## 8. Nota de prefijos y cierre

El primer prefijo libre es **`AS`**, y **este es el punto de entrada que lo reserva**:
`docs/audit/AS-AUDITORIA-TOTAL-V381.md`. No se renombra ningún dossier ya publicado:
las reservas anteriores (`AG`, `AH`, `AI`, `AJ` de motor y pausa pedagógica; `AP` de
`v3.75.7`; `AQ` de `v3.77.1`; `AR` de `v3.80.0`) las declararon los propios puntos de
entrada **dentro de sus tags**, y reescribirlas sería falsear historia.

Este documento se entrega **en un commit documental posterior al tag `v3.81.1`**
(§0.1-ii), con el ancla en `v3.81.1`, y **sin mover producto**: el invariante 3 de
§1.1 es la prueba, y el auditor debe ejecutarlo antes de empezar a puntuar.
