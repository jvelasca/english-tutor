# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.81.2`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el cierre de G0**: el
> parche de privacidad que quita el correo del historial de auditoría, arregla el
> orden del evento de purga y convierte la transición de las cuentas heredadas en un
> candado de la puerta de V4.0. La revisión es **de solo lectura**: no se cambia
> código, datos, configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué ahora.** La auditoría de la gestión de usuarios
> —`agentes/auditoria-total-externa-v381.md`, ancla `v3.81.1`— **todavía no tiene
> informe recibido** (`AS`), y su prompt sigue siendo válido **para el arco que
> audita** (`v3.80.0..v3.81.1`). Pero ese arco termina en `v3.81.1`, y **después se
> publicó `v3.81.2`**, que sí toca producto. Entre las dos cosas hay una consecuencia
> incómoda y declarada: **el invariante 3 del punto de entrada anterior** —«el diff
> `v3.81.1..main` de producto sale vacío»— **deja de ser cierto a partir de este
> tag**, y por eso ese documento lleva ahora una **errata en su cabecera**. Este
> documento es el ancla que sustituye a esa invariante para el delta nuevo.
>
> **Aviso de encuadre (léelo antes de puntuar).** Este parche es **pequeño en
> líneas** (27 ficheros, **+1089/−99** contando documentación; **7 ficheros** de
> producto con **+94/−15**) y **enorme en consecuencia**: es el primero de la casa
> que **añade un gate de validación** a mitad de campaña, y ese gate **no es una
> mejora del producto sino de la puerta**. Cambia qué significa «release validada»
> (de **7/7** a **8/8**), y por eso se audita con el mismo cuidado que un cambio de
> contrato: **un instrumento que se endurece después de haber aprobado cosas es
> sospechoso; uno que se endurece con la evidencia a cero es defendible.** Ese «con
> la evidencia a cero» es comprobable por comando (§1.1, invariante 7) y es la
> primera pregunta que este documento pone sobre la mesa.
>
> **Continuidad con el punto de entrada anterior.** `agentes/auditoria-total-externa-v381.md`
> **no se retira**: cubre el cuerpo de la gestión de usuarios (el renombrado
> PERFILES → USUARIOS, las credenciales, el email, la consola, la baja, la purga) con
> **siete invariantes, una lista cerrada de 98 ficheros y 42 preguntas**. Este
> documento cubre **solo el delta `v3.81.1..v3.81.2`** y **no repite** aquellas
> preguntas: las hereda. Un auditor que quiera cubrir todo el arco hasta hoy debe
> usar **los dos** (ver §6-D1, donde se declara la alternativa).
>
> **Estado del punto de entrada:** entregado 2026-09-23 en un **commit documental
> POSTERIOR al tag `v3.81.2`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md`). El ancla sigue siendo `v3.81.2` y el
> producto **no se mueve** para entregar esto; el invariante que lo demuestra está
> declarado y se comprueba por comando (§1.1, invariante 6).
>
> **Informe esperado:** `docs/audit/AT-AUDITORIA-TOTAL-V3812.md`. Prefijo **`AT`**
> porque **es el primer prefijo libre** (`AA`–`AM` los ocupan los dossiers de la
> pausa pedagógica y de psicometría, `AO` la política psicométrica de V4.0, `RA`–`RF`
> los del runtime, y **`AS` está reservado** por el punto de entrada de `v3.81.1`,
> cuyo informe sigue **sin recibir**). Ver la nota de prefijos en §8.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (§0 «START HERE»), y en particular la **nota
   `V3.81.2`**.
2. `release-notes-v3.81.2.md` — las notas **del parche que se audita**. Es el cuerpo
   del asunto y está escrita para ser leída en contra.
3. `agentes/auditoria-total-externa-v381.md` — el punto de entrada **anterior**, con
   su **errata de cabecera**: es el documento cuyo invariante 3 este parche rompe, y
   el sitio donde se explica por qué el ancla tenía que moverse.
4. `docs/audit/PARKED.md` — la sección **`V3.81.2`**: lo que este parche cierra, lo
   que **no** cierra y lo que declara como deuda con su etiqueta de tipo.
5. `docs/audit/KIT-VALIDACION-GATES.md` — la sección **«G0 · identidad-cuentas»**: el
   protocolo, las precondiciones, las condiciones de fallo y el registro.
6. `scripts/validation_gate.py` — **el instrumento**. No se audita un candado sin
   leer la cerradura: `GATES`, `check_gates_declared`, `status --strict` y `record`.
7. `backend/scripts/e2e_accounts_v381.py` — **la prueba end-to-end**, y en particular
   su sección **8** (la migración heredada) y el paso **7.6c** (PII tras la purga).
8. `backend/repositories/db.py` (`redact_emails`, `_scrub_user_event_emails`),
   `backend/repositories/users.py` (`redact_subject_notes`, `purge_user`) y
   `backend/domain/profile_requests.py` (`purge_profile`) — **el núcleo del cambio**.
9. `backend/tests/test_accounts_v381.py` — **los cuatro candados nuevos**.
10. `CHANGELOG.md` (la entrada `3.81.2`) y `docs/audit/TEMPLATE.md` (formato del
    informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
```

---

## 0.1 Errata heredada — el rango tiene DOS commits y el primero es documental y post-tag

No es una errata de este documento, es una **trampa del rango**, y se declara antes de
que la encuentre el auditor: `git log --oneline v3.81.1..v3.81.2` devuelve **dos**
commits, y el primero **no es** el release.

```bash
git log --oneline v3.81.1..v3.81.2
# dd43514 release(v3.81.2): el historial deja de guardar el correo, ...
# 91b2ff7 docs(audit): corrige el recuento del arco y resuelve el CI del tag
```

`91b2ff7` es el **commit documental de `v3.81.1`**: se publicó **después** de aquel
tag —un tag no puede contener la corrección de sus propias cifras— y toca **dos
ficheros, los dos `.md`** (`release-notes-v3.81.1.md` y
`agentes/auditoria-total-externa-v381.md`), **sin tocar producto ni pruebas**. Es
decir: el rango `v3.81.1..v3.81.2` contiene **un commit documental heredado y un
release**, y quien cuente «los commits del release» sin mirar se equivocará en uno.

```bash
git show --name-only --format='%h %s' 91b2ff7   # 2 ficheros, ambos .md
git show --shortstat --format='%h %s' dd43514   # el release: 26 ficheros, +989/-87
```

**Y después del tag hay un tercer commit, también documental:** `ea65561`
(«sella la run de CI en las notas y declara la errata del commit posterior al tag»),
de **un solo fichero** (`release-notes-v3.81.2.md`) y sin tocar producto, pruebas ni
versiones. Es el patrón declarado en las notas (§«Para auditar esta release»): el id
de la run no cabe dentro del commit que la dispara.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.81.2`.** Los identificadores se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.81.2            # objeto del tag anotado
git rev-parse 'v3.81.2^{commit}' # commit de release (el SHA exacto que se audita)
git rev-parse 'v3.81.1^{commit}' # commit del tag anterior (base del delta)
git log -1 --format='%H %s' 'v3.81.2^{commit}'
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run que dispara su push:
  son datos que solo existen **después** de publicar. Fijarlos obligaba a un commit
  de re-anclaje posterior al tag que quedaba a su vez fuera del tag siguiente. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando**, y este archivo es coherente **dentro de su propio tag**. Si un documento
  de este tipo vuelve a fijar un SHA o un run a mano, es una **regresión**.
- **Base de comparación:** `v3.81.1`. La cadena anterior (`v3.80.0..v3.81.1`) tiene su
  propio punto de entrada y **su informe sin recibir**: ver §6-D1.
- **El árbol de certificación NO se mueve con este parche.** Los gates se re-anclaron
  a `v3.81.0` en su día y aquí **no se vuelven a mover**: `v3.81.2` no cambia el
  contrato ni el currículum, así que no hay nada que invalidar. Lo que **sí** cambia
  es el número de gates (§2-A).

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Este arco es un **parche acotado**: **7 ficheros** de producto (`backend/` sin
pruebas ni el guion, y `scripts/`) con **+94/−15**, más `frontend/` tocado **solo en
la versión** (3 líneas), más pruebas y documentación. Se declaran **siete
invariantes**, cada uno con el comando que lo comprueba. Todos se han ejecutado
**antes** de entregar este documento.

**(1) Sin DDL nuevo: la base de datos no cambia de forma.**

```bash
git diff v3.81.1..v3.81.2 -- backend/repositories/db.py \
  | grep -E '^\+.*(ALTER TABLE|CREATE TABLE|CREATE INDEX|CREATE UNIQUE INDEX)'
```

Debe salir **vacío**. Este parche **no añade columnas ni tablas**: lo que hace es
**leer y limpiar** filas de `user_events`. Una BD de `v3.81.1` se abre intacta.
**Lo falsaría:** cualquier línea de salida. Sería **P0** (una migración no declarada).

**(2) Sin bumps pedagógicos ni de instrumento.** La **única** línea que cambia de
versión en `backend/config.py` es `VERSION`:

```bash
git diff -U0 v3.81.1..v3.81.2 -- backend/config.py \
  | grep -E '^[+-].*(VERSION|GENERATOR_VERSION|DECISION_POLICY|CURRICULUM_VERSION|LISTENING_BANK_VERSION)'
# solo: -VERSION = "3.81.1"  /  +VERSION = "3.81.2"
```

Los valores vigentes y **sin mover** son: `CURRICULUM_VERSION = "1.3.1"`,
`LISTENING_BANK_VERSION = "7.0.0"`, `GENERATOR_VERSION = "1.4.0"` y
`DECISION_POLICY_VERSION = "v3.68.0"`. **Aviso para no confundir una cita con un
cambio:** `CHANGELOG.md`, `PLAN.md` y las notas **sí** nombran esas constantes; lo
que este invariante acota es el **diff de `backend/config.py`**, y por eso el comando
lo acota.

**(3) El contrato de la API no crece: cero rutas nuevas.**

```bash
git diff v3.81.1..v3.81.2 -- backend/routers \
  | grep -E '^\+.*@router\.(get|post|put|patch|delete)'
```

Debe salir **vacío**. Los tres routers tocados (`users`, `session`, `account`) cambian
**una nota de historial cada uno** —lo que se escribe, no lo que se responde—.
**Lo falsaría:** una ruta nueva, o un cambio de forma en una respuesta. Si el auditor
encuentra que alguna respuesta **cambió de forma** (no de contenido), es un hallazgo
**P1** aunque no haya ruta nueva.

**(4) Currículum y evaluaciones: VACÍO.**

```bash
git diff --stat v3.81.1..v3.81.2 -- backend/curriculum
```

Debe salir **vacío**. Este parche no toca contenido ni exámenes: **lo falsaría**
cualquier línea de salida (**P0**).

**(5) El lanzador no se toca (y esto es deliberado).**

```bash
git diff --stat v3.81.1..v3.81.2 -- launcher
```

Debe salir **vacío**. La consola de Usuarios **ya enseñaba** el contador
`without_password` como tarea pendiente desde `V3.81.0`; lo que este parche cambia es
**lo que ocurre con ese contador** (pasa a ser candado), no el lanzador.
**Lo falsaría:** cualquier línea de salida —y merecería explicación, porque el
lanzador es la superficie donde el webmaster **ejecuta** la migración.

**(6) El producto no se ha movido desde el tag.**

```bash
git diff --stat v3.81.2..main -- backend frontend launcher scripts
```

Debe salir **vacío**, y con él este segundo candado, que no depende de contar commits:

```bash
git diff --name-only v3.81.2..main | grep -v '\.md$'   # VACÍO: desde el tag solo se ha tocado documentación
```

Los commits posteriores al tag son **documentales** (hoy: `ea65561`, el que entregó
este documento y la nota de publicación de la Release). Esa cola **crece con cada
entrega y no se congela por SHA a propósito**: `main` va por delante del tag **en
documentación**, y ese es el precio declarado de no recrear un tag publicado.

**(7) La evidencia de los gates está a CERO.** No hay ninguna aprobación previa que
este parche pueda estar blanqueando:

```bash
ls docs/audit/validation-evidence.json    # NO EXISTE
python scripts/validation_gate.py status  # 8 gates, los 8 en `pending`
```

`validation-evidence.json` **no existe** en el árbol, así que **ningún gate tiene un
`record`**: subir el listón de 7 a 8 **no invalida ninguna aprobación anterior,
porque no hay ninguna**. Si el auditor encuentra un `record` en cualquier forma
(fichero, rama, nota en un doc, captura en un informe), este invariante **cae** y con
él la defensa del §2-A3. Es el invariante más importante del documento.

### 1.1 bis · La cifra «7 gates» está por medio mundo, y eso es correcto

Un aviso para que el grep no confunda a nadie, porque **este punto de entrada pide
ejecutarlo** (§2-A3): la cadena «7 gates» aparece en **37 ficheros** —las notas de
release de la serie V3.73–V3.80, los puntos de entrada de auditoría anteriores, el
`CHANGELOG.md`, `PLAN.md` y `docs/RELEVO.md`— y **debe** aparecer: son documentos
**fechados**, se publicaron cuando había siete gates, y la casa no reescribe el
pasado (es la misma regla por la que un tag no se recrea).

Lo que **sí** es hallazgo es un «7» en un texto que describe el **estado actual**.
Al preparar este documento se ejecutó ese barrido y **se corrigieron tres**, que eran
deriva real introducida por `V3.81.2`: el **título del runbook**
(`docs/audit/VALIDATION-RELEASE-V373.md`), la ficha del **instrumento** en
`docs/audit/PARKED.md` (decía «los 7 gates … los siete `head_sha`») y una frase de
estado en `docs/audit/G7-MATRIZ-LECTURA.md`. Y se añadió un **marcador de
historicidad** en `docs/audit/KIT-VALIDACION-GATES.md` y en `docs/audit/PARKED.md`,
que dice explícitamente que las notas fechadas de abajo hablan de la cifra **de su
fecha**. Los dos **candados ejecutables** del recuento siguen donde estaban:
`backend/tests/test_validation_gate_v373.py` (`EXPECTED_GATES`) y
`backend/tests/test_docs_drift_v373.py` (`len(GATES) == 8`).

**Nota de honestidad:** esto no es un invariante del parche, es una **corrección
encontrada al preparar este encargo**, y se declara para que el auditor no la lea
como parte del release. Va en el commit documental posterior al tag, **sin tocar
producto, pruebas ni versiones**.

### 1.2 Lista cerrada — los dos commits del rango `v3.81.1..v3.81.2`

| # | SHA | Mensaje | Ficheros | ¿Tag? |
|---|---|---|---|---|
| 1 | `91b2ff7` | `docs(audit)`: corrige el recuento del arco y resuelve el CI del tag | 2 (`*.md`), +100/−12 | — (documental, **posterior** al tag `v3.81.1`) |
| 2 | `dd43514` | `release(v3.81.2)`: el historial deja de guardar el correo, la purga se registra después y la migración heredada pasa a candado | 26, +989/−87 | **`v3.81.2`** |

Y **fuera del rango, posterior al tag**: `ea65561` (`docs(v3.81.2)`, 1 fichero, +31/−3),
más los commits documentales de las entregas siguientes —el que trae **este documento**
y la nota de publicación de la Release—. Esa cola **no se congela por SHA a propósito**:
se congela por *invariante*, que es lo que un auditor puede comprobar sin fiarse de
esta lista ni de mi palabra:

```bash
git diff --name-only v3.81.2..main | grep -v '\.md$'   # debe salir VACÍO
```

### 1.3 Lista cerrada — el diff del arco, por área

```bash
git diff --shortstat v3.81.1..v3.81.2                  #  27 files changed, 1089+/ 99-
git diff --shortstat v3.81.1..v3.81.2 -- backend       #  11 files changed,  429+/ 32-
git diff --shortstat v3.81.1..v3.81.2 -- frontend      #   2 files changed,    3+/  3-
git diff --shortstat v3.81.1..v3.81.2 -- scripts       #   1 file  changed,   36+/ 19-
git diff --shortstat v3.81.1..v3.81.2 -- '*.md'        #  11 files changed,  615+/ 39-
git diff --shortstat v3.81.1..v3.81.2 -- launcher      #  (vacío)
```

Del **release** (`91b2ff7..dd43514`), separado por naturaleza:

```bash
# producto: 7 ficheros, +94/-15
git diff --shortstat 91b2ff7..dd43514 -- backend ':!backend/tests' ':!backend/scripts'
# pruebas: 4 ficheros, +335/-17 (3 de test + el guion E2E, declarado herramienta)
git diff --shortstat 91b2ff7..dd43514 -- backend/tests backend/scripts
# frontend: 2 ficheros, +3/-3 (las tres líneas son de versión, ninguna de dependencia)
git diff v3.81.1..v3.81.2 -- frontend
```

Los **7 ficheros de producto** del release son, y esta lista es **cerrada**:

| Fichero | Qué cambia |
|---|---|
| `backend/repositories/db.py` | `_EMAIL_RE` + `redact_emails()` + `_scrub_user_event_emails()` llamada desde `init_db()` |
| `backend/repositories/users.py` | `redact_subject_notes()`; `purge_user` redacta al sujeto **antes** de borrar la fila |
| `backend/domain/profile_requests.py` | notas sin email; **orden invertido** de `EVENT_PURGED` |
| `backend/routers/users.py` | el alta deja de escribir el email en la nota |
| `backend/routers/session.py` | el cambio de email deja de escribir el correo en la nota |
| `backend/routers/account.py` | la verificación de email deja de escribirlo en la nota |
| `scripts/validation_gate.py` | **el octavo gate** `G0 · identidad-cuentas`; `8/8` en `--strict` |

Y el resto (**13 ficheros** del release) es **documentación e instrumento**:
`CHANGELOG.md`, `PLAN.md`, `README.md`, `release-notes-v3.81.2.md`, la errata de
`agentes/auditoria-total-externa-v381.md`, cuatro documentos de `docs/audit/`, los
dos ficheros generados de `docs/audit/generated/`, `.github/workflows/ci.yml` (un
comentario: «8 gates») y los **dos candados de recuento** en
`backend/tests/test_validation_gate_v373.py` y `backend/tests/test_docs_drift_v373.py`.

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
git tag --list 'v3.81*'                 # v3.81.0, v3.81.1, v3.81.2
gh run list --commit <sha-de-v3.81.2>   # la run que certifica el commit del tag
gh release view v3.81.2                 # la Release publicada (cuerpo = notas)
gh api repos/jvelasca/english-tutor/releases/latest --jq .tag_name   # v3.81.2
```

| Certificación | Valor |
|---|---|
| Workflow | `CI` · evento `push` · rama `main` |
| Run del commit del tag | **`35926727880`** — `conclusion = success`, **12/12 jobs** |
| Run del commit documental posterior | **`35927208170`** — `conclusion = success`, **12/12 jobs** |
| `Playwright E2E (visual)` | ✅ verde en las dos (fue el rojo que abrió la saga de `v3.81.1`) |
| Release publicada | **`v3.81.2`** — creada el **2026-09-24**, `draft = false` · `prerelease = false`; es la que GitHub marca como **Latest** |

**Aviso de anclaje (evita auditar la versión equivocada).** Hasta el **2026-09-24**,
`v3.81.2` existía **solo como tag**: no tenía *Release object*, así que
`/releases/tag/v3.81.2` respondía **404** y la página
[`/releases`](https://github.com/jvelasca/english-tutor/releases) anunciaba
**`v3.81.1` como «Latest»**, con un título («Gestion de USUARIOS…») que describe el
arco anterior. Un auditor que entrase por ahí habría auditado **una versión por
detrás creyendo que era la última**. Se publicó la Release de `v3.81.2` (cuerpo =
`release-notes-v3.81.2.md`, **idéntico al fichero salvo la normalización `LF → CRLF`**,
que es la única diferencia y no es corrupción). Comprobado por comando:

```bash
# el cuerpo remoto y el fichero local coinciden tras normalizar saltos de línea
gh api repos/jvelasca/english-tutor/releases/tags/v3.81.2 --jq .body > /tmp/remoto.md
python -c "import io;a=io.open('/tmp/remoto.md',encoding='utf-8').read().replace(chr(13)+chr(10),chr(10)).strip();b=io.open('release-notes-v3.81.2.md',encoding='utf-8').read().strip();print(a==b)"
```

> **Trampa para el auditor de hoy en día:** si algún documento, memoria o
> automatismo cita `v3.81.1` como «la última release», es **deriva documental
> heredada** del día en que se publicó (y es correcta para su fecha). La cifra
> vigente es `v3.81.2`.

**El CI no dispara en tags** (`ci.yml` escucha `push: branches: [main]` y
`pull_request`): quien audite «el CI del tag» audita el CI del commit al que apunta.
Y **el CI de los PRs está rojo de forma sistemática**: los doce PRs abiertos de
Dependabot tienen **`Playwright E2E (visual)` en rojo en los doce**, incluidas las
subidas que **no pueden afectar a la app** (p. ej. `actions/checkout`), en runs del
**2026-09-18** que **nunca se han vuelto a lanzar**. No confundir eso con el CI de
`main`, que está verde; pero **sí** es un hallazgo sobre la calidad de la señal de PR
y está declarado como pregunta (**§2-F7**).

---

## 2. Preguntas falsables por área

### A. El ancla, el rango y el instrumento (el octavo gate)

- **A1.** ¿El rango `v3.81.1..v3.81.2` tiene **exactamente dos** commits, y el
  **primero** es documental y **posterior** al tag `v3.81.1`? (§0.1)
  `git log --oneline v3.81.1..v3.81.2`. **Dictamina:** ¿es honesto empaquetar un
  commit documental heredado dentro del rango del release, o debería el rango
  empezar en el release?
- **A2.** ¿Añadir un **octavo gate** a mitad de campaña está justificado, y **no**
  blanquea nada? El invariante 7 (§1.1) dice que la evidencia está a cero. Si
  encuentras **cualquier** `record` previo, el hallazgo es **P0**.
- **A3.** ¿El candado del recuento está actualizado en **todos** los sitios que
  declaran el **estado actual**, o en uno solo? Búscalo por el árbol entero, no solo
  en el diff:

  ```bash
  git grep -c -E "7 gates|siete gates"          # por fichero
  git grep -n -E "7 gates|siete gates" -- '*.md'
  ```

  **Lo que vas a encontrar, y por qué (§1.1 bis):** la cadena sale en **37
  ficheros**, casi todos **fechados** (notas de V3.73–V3.80, puntos de entrada
  anteriores, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`): ahí **es correcto**, son
  el registro de cuando había siete, y no se reescriben. Los **candados ejecutables**
  son dos y están en `backend/tests/`. **Dictamina:** ¿queda algún «7» en una sección
  **sin fecha** (el caso que sí es hallazgo), y bastan el **marcador de historicidad**
  de `docs/audit/KIT-VALIDACION-GATES.md` y el de `docs/audit/PARKED.md` para que un
  lector nuevo no se confunda, o el repositorio necesita algo más fuerte que un
  marcador?
- **A4.** ¿`status --strict` exige de verdad **8/8**, y falla si el octavo está
  `pending`? Léelo en `scripts/validation_gate.py` **y** compruébalo ejecutándolo.
  ¿El test `test_strict_aprueba_con_los_ocho_gates_en_pass` prueba el caso que dice
  probar (ocho en `pass`) y no un caso vecino?
- **A5.** ¿El gate `G0` es **humano** (`human=True`) y su evidencia **no se puede
  auto-sellar desde el CI**? ¿Puede el job `Validation gate (checks automáticos)`
  aprobarlo por su cuenta? Si puede, el candado es decorativo: **P0**.
- **A6.** ¿La condición de `pass` de `G0` —«`without_password == 0`»— está escrita
  como **condición de fallo verificable**, o solo como buena intención en prosa?
  Compárala con lo que el gate dice en `docs/audit/KIT-VALIDACION-GATES.md` §«G0».
- **A7.** La cadena de puntos de entrada externos **sin informe recibido** crece a
  **cinco** (`AP`, `AQ`, `AR`, `AS` y el `AT` que este documento reserva). ¿Sigue
  siendo auditoría externa, o es un archivo que se acumula? **Dictamina** —y di qué
  haría falta para que la cadena se cerrara.

### B. La PII y el purgado (el núcleo)

- **B1.** ¿Queda **algún** camino por el que una nota de `user_events` pueda seguir
  llevando un correo? No te fíes del diff: busca el árbol entero.
  `git grep -n 'note=' backend/` y `git grep -n 'email' backend/routers backend/domain`.
  **Dictamina** por camino encontrado.
- **B2.** La purga redacta **antes** de borrar la fila de `users`. ¿Es el orden
  correcto, o debería redactarse **después** (o en la misma transacción)? Si la
  redacción falla **después** de haber purgado filas de otras tablas, ¿en qué estado
  queda la cuenta?
- **B3.** ¿`redact_emails` es idempotente **por construcción** (el reemplazo no casa
  con su propio patrón) o por casualidad? ¿Y si el correo apareciera dentro de una
  frase: se conserva la frase o se destruye contexto?
- **B4.** El regex **no** cubre formas exóticas (comentarios RFC, direcciones entre
  corchetes, un correo partido por un salto de línea). El parche lo declara y dice
  que la garantía fuerte es **dejar de escribir**, no redactar. **Dictamina** si esa
  jerarquía es defendible o si el barniz da falsa seguridad.
- **B5.** El historial sigue guardando **`subject_name`**, y es deliberado: sin él,
  «¿a quién se purgó?» no tiene respuesta. **Dictamina** si un nombre propio en una
  fila que **sobrevive** a un borrado con promesa de «toda la evidencia» es
  aceptable, o si eso es PII retenida por conveniencia.
- **B6.** Al dejar de escribir el email en la nota de `EVENT_EDITED`, ¿el historial
  sigue **distinguiendo** qué se editó (email vs nombre), o el cambio se ha vuelto
  indistinguible? Comprueba si hay `changed` o cualquier otra columna que lo salve.
- **B7.** ¿La migración de arranque mira **solo** `user_events.note`? ¿Podría haber
  PII del mismo tipo en **otras** columnas o tablas que el barrido no mira (p. ej.
  `profile_requests`, `admin_log`, notas de solicitudes)? Si la respuesta es «no lo
  sé», eso también es un hallazgo.

### C. El orden de `EVENT_PURGED`

- **C1.** ¿El evento se registra **después** del borrado y **solo** si `purge_user`
  devuelve `True`? Léelo en `purge_profile` y comprueba que no hay un `record_event`
  alcanzable por otro camino.
- **C2.** El fallo que se arregla era «evento sin purga». ¿Cuál es el fallo
  **simétrico** ahora —purga sin evento, si `record_event` falla— y es **peor** o
  **mejor** que el anterior? **Dictamina** razonadamente; no aceptes «es mejor»
  como respuesta sin el porqué.
- **C3.** Si la fila de `users` **ya no existe** cuando se escribe el evento, ¿de
  dónde sale el nombre que se guarda? ¿Se captura antes, y de una fuente fiable?
- **C4.** ¿Qué ve el webmaster cuando `purge_profile` devuelve `None` (purga
  fallida)? ¿Se le dice **que no se purgó** y **por qué**, o la consola insinúa un
  éxito? Este es el mismo defecto de «no mientas» que la casa arregló en V3.81.0 con
  las solicitudes de baja.
- **C5.** El test que cubre el orden: ¿provoca el **fallo real** (nombre que no
  coincide, `purge_user` devolviendo `False`) o un **mock** que simula el fallo? Un
  mock que simula el fallo prueba el `if`, no la condición.

### D. La migración de arranque

- **D1.** ¿En qué momento de `init_db()` corre el barrido, y qué pasa en una BD de
  `V3.80.0` —que **no tiene** la tabla `user_events`— cuando se abre por primera vez
  con este árbol? ¿El orden de creación y de barrido está garantizado, o depende del
  camino de inicialización?
- **D2.** ¿Cuánto cuesta el barrido en una tabla grande? ¿Está acotado
  (`WHERE note LIKE '%@%'`, y `UPDATE` **solo** cuando el texto cambia) o recorre y
  reescribe todo? Un barrido que reescribe toda la tabla en cada arranque es un
  hallazgo de rendimiento y de desgaste (**P2** como mínimo).
- **D3.** ¿Es idempotente **de verdad** —segunda pasada: **cero** filas afectadas— o
  simplemente «no rompe»? La aserción del test ¿comprueba que la segunda pasada **no
  toca nada**, o solo que el resultado es el mismo?
- **D4.** Si el barrido **falla** (BD bloqueada, disco lleno), ¿arranca el producto
  igual o queda sin arrancar? **Dictamina** si un fallo de limpieza debe impedir el
  arranque de la aplicación: las dos respuestas son defendibles y la casa debe
  elegir una y escribirla.
- **D5.** ¿El barrido **deja rastro** de cuántas notas redactó, o es silencioso? Una
  migración que modifica datos de auditoría **sin dejar rastro** de cuánto modificó
  es, cuanto menos, irónica en un parche sobre auditoría. **Dictamina.**

### E. La migración heredada y el gate `G0`

- **E1.** ¿El E2E **siembra** la cuenta heredada, o depende de que la BD de entrada
  ya tenga una? ¿Es reproducible en una máquina limpia, sin BD previa?
- **E2.** ¿La semilla se escribe sobre la **copia** o sobre la BD real? Comprueba el
  `sha256` y los recuentos finales: el guion afirma que la BD original **no se toca**.
- **E3.** El contador `without_password` del endpoint `/api/admin/users`: ¿cuenta
  también las cuentas **desactivadas y dadas de baja**? (El default es
  `include_disabled=True`, así que **sí**.) ¿Y las de **prueba**? (`is_test=1`:
  **excluidas** por defecto.) **Dictamina** si ese perímetro es el correcto para un
  candado.
- **E4.** Con el perímetro de E3: ¿puede el gate declararse `pass` con el camino
  «entrar sin contraseña» **todavía vivo** —por ejemplo con una cuenta heredada
  `is_test=1`, o con una fila creada a mano en la BD? Si puede, el candado tiene un
  agujero y hay que decirlo con su severidad.
- **E5.** ¿Los **77 pasos** del E2E incluyen: login con la temporal, `403
  PASSWORD_CHANGE_REQUIRED` en el resto de la API, cambio obligatorio, **cookie
  anterior tumbada** (`401 SESSION_STALE`), login con la temporal **ya cerrado**,
  y login con la definitiva? Cuenta los pasos y di si sobra o falta alguno.
- **E6.** ¿El E2E comprueba que **los datos del alumno migrado siguen intactos**
  después de asignarle credenciales? Sin esa comprobación, la migración podría estar
  «arreglando» la autenticación a costa de los datos.
- **E7.** `must_change_password`: ¿se hace cumplir **en el servidor en cada
  petición**, o solo se pinta en la UI? Busca dónde se aplica y comprueba que no hay
  una ruta que se salte la exigencia.

### F. Deriva documental y la señal del CI

- **F1.** Las notas de `v3.81.0` y `v3.81.1` **no se reescriben**: siguen diciendo
  que la cuenta heredada entra sin contraseña y que había **7** gates. **Dictamina**
  si esa inmutabilidad es la decisión correcta o si deja el repositorio
  contradiciéndose a sí mismo para siempre.
- **F2.** ¿La entrada `3.81.2` de `CHANGELOG.md` coincide con el diff real, sin nada
  prometido y no hecho? Contrasta **cada** afirmación verificable (cifras de tests,
  el contador, el orden del evento) con el árbol.
- **F3.** `PLAN.md` y `PARKED.md` decían que el parche «**se publicará** como
  `v3.81.2`». ¿Quedó cerrado a `v3.81.2` en el mismo commit, o queda una promesa en
  el aire que ya se cumplió (o que no se cumplió)?
- **F4.** El punto de entrada anterior declara un invariante que este parche **rompe**;
  se le añadió una **errata en la cabecera**. ¿Basta eso, o el documento debería
  retirarse para no confundir a quien lo lea en el orden equivocado?
- **F5.** ¿`docs/audit/PARKED.md §V3.81.2` declara lo que este parche **no** cierra
  (política de contraseña, freno de intentos en memoria, terminología perfil/usuario)
  con su etiqueta de tipo, y **sin** presentarlo como cerrado?
- **F6.** ¿`docs/audit/generated/release-validation.{md,json}` se **regeneró** con la
  versión nueva y **no** se editó a mano? El generador es
  `scripts/validation_gate.py auto`: ejecútalo y comprueba que el resultado coincide.
- **F7.** La señal de CI en **pull requests** está muerta: `Playwright E2E (visual)`
  en rojo en los **12** PRs, con trazas de proxy al backend ausente
  (`connect ECONNREFUSED 127.0.0.1:8000`) **también en las runs verdes de `main`**.
  **Dictamina** si un gate que está rojo en el 100% de los PRs —incluidos los que no
  pueden afectar a la app— sigue siendo un gate, o es ruido que enseña a ignorar el
  rojo. Este hallazgo **no es de este parche**, y se declara aquí porque se descubrió
  auditándolo.

---

## 3. Matriz de cierre (la rellena el auditor)

| ID | Área | Dictamen (`pass`/`fail`/`no verificado`) | Evidencia (comando o fichero) | Severidad si `fail` |
|---|---|---|---|---|
| A1 | Ancla y rango | | `git log --oneline v3.81.1..v3.81.2` | |
| A2 | El octavo gate | | `ls docs/audit/validation-evidence.json` | P0 |
| A3 | Candados de recuento | | `git grep -n '8 gates'` | P2 |
| A4 | `--strict` 8/8 | | `python scripts/validation_gate.py status --strict` | P1 |
| A5 | G0 no auto-sellable | | `scripts/validation_gate.py::record` | P0 |
| A6 | Condición de `pass` de G0 | | `docs/audit/KIT-VALIDACION-GATES.md` §G0 | P1 |
| A7 | Cadena de prefijos | | `docs/audit/AS-*`, `AT-*` | — |
| B1 | Notas sin email | | `git grep -n 'note=' backend/` | P0 |
| B2 | Orden en la purga | | `backend/repositories/users.py` | P1 |
| B3 | Idempotencia | | `backend/tests/test_accounts_v381.py` | P2 |
| B4 | Límites del regex | | `backend/repositories/db.py` | P2 |
| B5 | `subject_name` | | `user_events` tras purga | P1 |
| B6 | ¿Se distingue qué se editó? | | `backend/routers/session.py` | P2 |
| B7 | PII fuera de `user_events` | | `profile_requests`, notas | P1 |
| C1 | Orden de `EVENT_PURGED` | | `backend/domain/profile_requests.py` | P1 |
| C2 | El fallo simétrico | | razonamiento + código | P2 |
| C3 | Origen del nombre | | `purge_profile` | P1 |
| C4 | La consola no miente | | `launcher/ui.py`, `domain/profile_requests.py` | P2 |
| C5 | El test muerde | | `test_accounts_v381.py` | P1 |
| D1 | Orden en `init_db()` | | `backend/repositories/db.py` | P1 |
| D2 | Coste del barrido | | SQL del barrido | P2 |
| D3 | Idempotencia real | | test de migración | P2 |
| D4 | Fallo de limpieza ≠ caída | | `init_db()` | P1 |
| D5 | Rastro de lo redactado | | `init_db()` | P3 |
| E1 | Semilla reproducible | | `e2e_accounts_v381.py` §8 | P1 |
| E2 | La BD real no se toca | | `sha256` final del guion | P0 |
| E3 | Perímetro del contador | | `backend/routers/admin.py` | P1 |
| E4 | ¿Agujero en el candado? | | `is_test`, filas a mano | P1 |
| E5 | Los 77 pasos | | salida del E2E | P1 |
| E6 | Datos intactos | | E2E §8.14 | P1 |
| E7 | `must_change_password` servidor | | middleware/dependencia | P0 |
| F1 | Notas históricas inmutables | | `release-notes-v3.81.0.md` | — |
| F2 | CHANGELOG vs diff | | entrada `3.81.2` | P2 |
| F3 | Promesa cerrada | | `PLAN.md`, `PARKED.md` | P3 |
| F4 | La errata basta | | `agentes/auditoria-total-externa-v381.md` | — |
| F5 | Deuda declarada | | `PARKED.md §V3.81.2` | — |
| F6 | Informe regenerado | | `validation_gate.py auto` | P2 |
| F7 | La señal de CI en PRs | | `gh pr checks <n>` en los 12 PRs | P2 |

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se recrea ningún tag, no se fuerza ningún push, no se
   reescribe historia. Si el auditor necesita una corrección, va **después** del tag,
   en un commit documental, y se declara.
2. **Nada se da por bueno por lo que diga un documento de la casa**, y eso incluye
   **estas notas**: cada cifra de este prompt se ha verificado por comando **antes**
   de entregarlo, y el auditor debe **volver a verificarla**. El punto de entrada
   anterior declaró cuatro cifras mal calculadas y tuvo que llevar errata; no se
   repite el patrón sin motivo.
3. **El ancla es el tag, no la página de Release.**
4. **Los invariantes se comprueban antes de puntuar**, y si alguno no se cumple, eso
   **es** el hallazgo: no se reinterpreta el invariante para que encaje.
5. **Severidades:** `P0` = rompe una promesa de seguridad, privacidad o contrato;
   `P1` = deja el P0 de identidad abierto o engaña al operador; `P2` = deuda
   declarada o fragilidad de instrumento; `P3` = cosmético o de rastro.
6. **Un hallazgo no declarado vale doble** en este arco: el parche entero consiste en
   que lo declarado y lo hecho coincidan.

---

## 5. Honestidad esperada del informe

El informe (`AT`) debe declarar explícitamente, aunque nadie lo pregunte:

- Que **`G0` queda `pending`** y que **este parche no lo cierra**: la BD de uso tiene
  **3 cuentas heredadas sin credencial**, así que `without_password > 0`. El gate
  **no puede** estar en `pass`, y decir lo contrario sería el hallazgo más grave
  posible de esta auditoría.
- Que en la **BD de uso no había PII que limpiar** (`user_events` tiene 0 filas): el
  hallazgo era un **riesgo de código**, no un dato expuesto. Quien venda «limpieza de
  datos» está vendiendo algo que no ocurrió.
- Que el parche **no toca** la política de contraseña, el freno de intentos en
  memoria ni la terminología «perfil/usuario», y que las tres siguen abiertas.
- Que **la señal de CI en pull requests está roja de forma sistemática** (§2-F7), que
  **no** es culpa de este parche y que **sí** degrada la confianza en el rojo.
- Que **la cadena de puntos de entrada sin informe recibido crece a cinco** (§2-A7).
- Que el E2E **se prueba contra una copia** de la BD y que la BD real se comprueba
  por `sha256`: si esa comprobación no existiera, el E2E sería peligroso.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

- **D1. Hay dos formas de cubrir el arco hasta hoy, y este documento elige una.**
  *(a)* Auditar `v3.81.1..v3.81.2` con este prompt, **heredando** el cuerpo de
  `v3.81.1` del documento anterior. *(b)* Extender el prompt anterior a
  `v3.80.0..v3.81.2` en **un solo** informe. Se elige **(a)** porque los invariantes
  y la lista cerrada del documento anterior valen para **su** arco y ampliarlos los
  invalidaría a todos; y porque el delta nuevo tiene un objeto propio (el gate) que
  merece su propio dictamen. **El auditor puede dictaminar lo contrario** y, si lo
  hace, este documento queda como anexo del anterior —no se borra—.
- **D2. El invariante 3 del punto de entrada anterior se rompe, y se declara.**
  `git diff --stat v3.81.1..main -- backend frontend launcher scripts` sale **vacío**
  en el documento anterior y **no** sale vacío hoy (**14 ficheros, +468/−54**): eso es
  exactamente este parche. No es una violación del prompt anterior: es que su ancla
  se ha movido. La errata está en su cabecera y aquí, en los dos sitios donde se lee.
- **D3. El perímetro del candado `G0` es el endpoint de administración, no la tabla.**
  `without_password` se cuenta sobre `/api/admin/users` con `include_disabled=True`
  (cubre desactivadas y dadas de baja) y `is_test=False` (**excluye** las de prueba).
  Declararlo importa: un candado que se apoya en un contador de API, no en una
  consulta a la tabla, tiene el perímetro que tenga ese endpoint. **Pregunta E4.**
- **D4. El E2E se siembra su propio caso.** La cuenta heredada la **crea** el guion en
  la copia, en vez de depender de las cuentas reales. Es deliberado —un test no debe
  mutar cuentas de una persona real— y a la vez es una debilidad: prueba el
  **mecanismo** de la migración, no el estado concreto de la instalación. Por eso el
  candado real es el **contador**, no el E2E.
- **D5. `subject_name` se conserva.** Ya declarado en §2-B5 y en `PARKED.md`: es una
  decisión, no un olvido, y se somete a dictamen.
- **D6. El barrido de arranque modifica datos de auditoría.** Un parche sobre
  auditoría que reescribe filas del historial merece la lectura más escéptica del
  documento: mira **qué** cambia, **cuándo**, **con qué rastro** y **qué pasa si
  falla** (§2-D).

---

## 7. Alcance

**Dentro:** el delta `v3.81.1..v3.81.2` completo —los siete ficheros de producto, los
cuatro de pruebas, la documentación viva, el instrumento de gates y las dos runs de
CI—, con el foco en **la PII del historial, el orden del evento de purga y el octavo
gate**.

**Fuera (y se hereda del prompt anterior):** el cuerpo de la gestión de usuarios
(renombrado PERFILES → USUARIOS, credenciales, email, verificación, baja, purga, la
consola del lanzador y el aislamiento entre cuentas) se audita con
`agentes/auditoria-total-externa-v381.md`; **este documento no repite sus 42
preguntas**. Lo que **sí** se pregunta aquí es lo que ese prompt **no podía**
preguntar porque aún no existía: el gate, la redacción y el orden del evento.

**Fuera también:** la deuda declarada (política de contraseña, freno en memoria,
terminología) no se audita aquí como defecto, se audita **su declaración**: que esté
aparcada, con tipo y sin disfraz.

---

## 8. Nota de prefijos y cierre

- **El primer prefijo libre es `AT`**, y **este es el punto de entrada que lo
  reserva**: el informe esperado es `docs/audit/AT-AUDITORIA-TOTAL-V3812.md`.
  **`AS` queda reservado** por `agentes/auditoria-total-externa-v381.md` (ancla
  `v3.81.1`), cuyo informe **sigue sin recibir**. Reservados y **sin dictamen** a
  fecha de este commit: **`AP`**, **`AQ`**, **`AR`**, **`AS`** y **`AT`**.
- **Cadena de puntos de entrada:** `v3757` → `v380` → `v381` → **`v3812`** (este).
- **Este documento se entrega en un commit documental posterior al tag `v3.81.2`**,
  con el ancla en `v3.81.2` y **sin mover producto**: el invariante 6 de §1.1 es la
  prueba, y el auditor debe ejecutarlo antes de empezar a puntuar.
- **Lo que este documento NO es:** no es la auditoría, es el encargo. No adelanta
  veredictos, no maquilla los invariantes para que se cumplan y no promete que todo
  vaya a salir verde. El parche que describe **deja `G0` en `pending` a propósito**,
  y eso —que el candado impida declarar cerrado lo que no lo está— es justamente lo
  que hay que auditar.
