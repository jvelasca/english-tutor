# Auditoría EXTERNA de CIERRE GLOBAL — punto de entrada anclado a `v3.83.1`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) dictamine **si la serie V3.83.x
> puede declararse lista para empezar la certificación final (G0–G7 → V4.0.0)**. No
> vuelve a auditar el producto de `v3.83.0` (ya dictaminado en
> `docs/audit/AU-AUDITORIA-TOTAL-V383.md`) ni el arco que cambia el contrato
> (`AV`, pendiente): los **hereda** y se centra en el **cierre**: los ocho gates, el
> inventario de deuda y el árbol de certificación. La revisión es **de solo lectura**:
> no se cambia código, datos, configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué AHORA.** Porque la instrumentación ya está
> congelada: `v3.83.1` cierra la fase de **instrumento y honestidad** —el gate
> `reduced-motion` deja de emular en vacío (H2), la letra de las notas de `v3.83.0`
> queda coherente (E5/i) y H1 se declara como deuda aceptada—, y con el ancla
> reproducible por fin fija, lo que falta **no es más producto**: es decidir si se
> arranca la campaña física de los ocho gates o si queda deuda **P1** que la bloquee.
> La pregunta central de este documento no es «¿compila?», es **«¿está el proyecto en
> condiciones de empezar a certificar, y qué lo bloquea?»**.
>
> **Aviso de encuadre (léelo antes de puntuar).** Esta serie **no** añade producto
> nuevo: `v3.83.1` es un patch de instrumento. Por eso invita a una auditoría blanda
> o a dar por cerrado lo que solo está **instrumentado**. No lo hagas: un gate
> declarado desde `V3.73.1` que emulaba **en vacío** es exactamente la clase de
> engaño que una auditoría de cierre debe buscar, y el hecho de que aquí ya esté
> corregido **no** significa que los demás gates estén ejecutados —los **ocho**
> siguen `pending` y `docs/audit/validation-evidence.json` **no existe**—.
>
> **Continuidad con los puntos de entrada vecinos.** `agentes/auditoria-total-externa-v383.md`
> **no se retira**: cubre el delta de producto `v3.82.0..v3.83.0` con **siete
> invariantes y veinticinco preguntas** (`A1`–`E6`) y produjo el informe **`AU`**, que
> ya dictaminó ese arco y **pidió este parche**. `agentes/auditoria-total-externa-v382.md`
> cubre el eslabón `v3.81.2..v3.82.0` (contrato + migración) y **sigue esperando su
> informe `AV`**. Este documento **no repite** las preguntas de ninguno de los dos:
> las **hereda** y solo pregunta lo que es de **cierre de serie**.
>
> **Estado del punto de entrada:** entregado 2026-09-24 en un **commit documental
> POSTERIOR al tag `v3.83.1`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md`). El ancla sigue siendo `v3.83.1` y el producto
> **no se mueve** para entregar esto; el invariante que lo demuestra está declarado y
> se comprueba por comando (§1.1, invariante 6).
>
> **Informe esperado:** `docs/audit/AW-AUDITORIA-CIERRE-V383.md`. Prefijo **`AW`**
> porque **es el primer prefijo libre**: `AA`–`AF` los ocupan los dossiers de V3.70,
> `AG`–`AM` la pausa pedagógica y psicometría, `AN` el arco de `v3.75.1`, `AO` la
> política psicométrica de V4.0, y **`AP` (`v3.75.7`), `AQ` (`v3.77.1`), `AR`
> (`v3.80.0`), `AS` (`v3.81.1`), `AT` (`v3.81.2`), `AU` (ya dictaminado, `v3.83.0`) y
> `AV` (`v3.82.0`, pendiente) siguen reservados**. Ver la nota de prefijos en §8.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (§0 «START HERE») y, en particular, la **nota
   `V3.83.1`**.
2. `release-notes-v3.83.1.md` — las notas **de la release que se audita**. Su §6
   «Honestidad» declara los cinco límites, y cada uno es una pregunta encubierta.
3. `docs/audit/AU-AUDITORIA-TOTAL-V383.md` — **el informe que motivó este parche**: su
   §5 (H1–H6), §8 (veredicto y contenido mínimo de `v3.83.1`) y §12 (H1 aparcado).
4. `docs/audit/KIT-VALIDACION-GATES.md` — **la planilla de campo de los 8 gates** y la
   sección del gate **`G0 · identidad-cuentas`**: sigue `pending` y esta serie **no lo
   toca**. Ojo al **desfase de ancla** (§1.1-7).
5. `docs/audit/VALIDATION-RELEASE-V373.md` — el **runbook** que define los 8 gates.
6. `scripts/validation_gate.py` — **el instrumento**: la tupla `GATES` (ocho) y
   `status --strict` / `--same-tree`.
7. `docs/audit/PARKED.md` — el **inventario de deuda**, en particular §V3.70
   (pedagogía), §V3.81.2 y §V3.82.0.
8. `backend/domain/retention.py` (`_collection_writable`, línea ~185) — **H1 sigue
   vivo** aquí.
9. `docs/audit/TEMPLATE.md` — el formato del informe.

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
```

---

## 0.1 El rango `v3.83.0..v3.83.1` arrastra NUEVE commits, y solo uno es «el release»

Al revés que el rango de `v3.83.0` (que era **un solo commit**), aquí el rango
**contiene la cola que `AU` dejó en `main`** y que el tag **absorbe**:

```bash
git log --oneline v3.83.0..v3.83.1
# 4ee32e5 release(v3.83.1): instrumento y honestidad - publica la version que el informe AU pedia (H2, E5/i, H1 aparcado)
# dfe9898 docs(audit): reproduce la causa del invariante 9 (el CI solo certifica el tip del push)
# acb9fde docs(audit): dictamina E6 (PRs de Dependabot) y anota AV en el encargo de v3.83.0
# c1e5706 docs(audit): abre el punto de entrada del eslabon v3.81.2..v3.82.0 (deficit D1)
# 4a7e70f docs(audit): informe AU de la segunda pasada de v3.83.0 (arco v3.81.2..v3.83.0)
# 54a32fd test(visual): sonda del puente diccionario-flashcards, atajos y reduced-motion real
# 5a5e600 docs(audit): punto de entrada externo anclado a v3.83.0 (diccionario a Flashcards y sesion tipo juego)
# fd086e8 test(visual): fija workers en serie para evitar falsos negativos por contencion
# 240e5c9 docs(audit): documenta el relevo de v3.82.0 y v3.83.0 y parkea la deuda de la release visual
```

**Ocho** de esos nueve commits **ya estaban en `main`** (6 `docs(audit)` + 2
`test(visual)`); el noveno (`4ee32e5`) es el **commit de release** de este parche. Y
**esos ocho commits se etiquetan aquí** —incluido `fd086e8`, que toca
`frontend/playwright.config.ts`—, así que el tag **sí** cubre la corrección del arnés:
el hallazgo **H4** de `AU` («un cambio de arnés posterior al tag no lleva tag
propio») queda **resuelto de facto** por esta release. **Que el rango «contenga»
nueve commits no dice nada malo del arco**: dice que la cola de auditoría del tag
anterior cayó **dentro** de este.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.83.1`.** Los identificadores se **resuelven
  con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.83.1                 # objeto del tag anotado
git rev-parse 'v3.83.1^{commit}'      # commit de release (el SHA exacto que se audita)
git rev-parse 'v3.83.0^{commit}'      # commit del tag anterior (base del delta)
git rev-parse 'v3.82.0^{commit}'      # base del arco grande (AV, pendiente)
git log -1 --format='%H %s' 'v3.83.1^{commit}'
```

| Tag | Commit |
|---|---|
| `v3.82.0` | `3f686a031d194974f284e590dc39746633aef6f0` |
| `v3.83.0` | `e05b3dd6a6ef531c993c3340aa921417d8cbca5d` |
| **`v3.83.1`** | **`4ee32e543e49c3a8d056d2ae36cc15c092825cf5`** |

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run que dispara su push:
  son datos que solo existen **después** de publicar. El ancla es el **tag**, el estado
  de publicación se **verifica por comando**, y este archivo es coherente **dentro de
  su propio tag**.
- **Base de comparación:** `v3.83.0`. **Ojo:** el arco previo
  (`v3.81.2..v3.82.0`) tiene **punto de entrada (`AV`) pero no informe**, y **sí era
  grande** (contrato + migración): ver §6-D1. Este documento **no lo cubre**.
- **El árbol de certificación SÍ se mueve con esta serie, y aquí es donde se decide.**
  El ancla documental de la campaña sigue en `v3.81.0`
  (`docs/audit/KIT-VALIDACION-GATES.md`), pero después se publicó **producto**
  (`V3.82.0` cambió el contrato de `POST /api/session` y migró la BD; `V3.83.0` movió
  la UI) y **no se ha re-anclado**. Sigue habiendo **ocho** gates, todos `pending`.
  Ver §1.1-7 y §2-B.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Se declaran **siete** invariantes, cada uno con el comando que lo comprueba. Todos se
han ejecutado **antes** de entregar este documento.

**(1) `v3.83.1` es instrumento y honestidad: el diff de producto es UNA línea.**

```bash
git diff --stat v3.83.0..v3.83.1 -- backend frontend/src launcher scripts
# backend/config.py | 2 +-   (la línea VERSION)
git diff v3.83.0..v3.83.1 -- backend
# -VERSION = "3.83.0"
# +VERSION = "3.83.1"
```

Debe salir **exactamente eso** (`backend/config.py`, la línea `VERSION`) y **nada** de
`frontend/src` ni de `launcher/`. El resto del diff son **pruebas visuales**
(`frontend/tests/visual/*.spec.ts`), **el arnés** (`frontend/playwright.config.ts`),
**la versión** (`frontend/package.json`/`package-lock.json`) y **documentación**.
**Lo falsaría:** cualquier línea de lógica en `backend/` que no sea esa, o cualquier
`frontend/src/` (sería **P0**).

**(2) Sin DDL nuevo y sin bumps pedagógicos.**

```bash
git diff v3.83.0..v3.83.1 -- backend/repositories backend/repositories/db.py   # VACÍO
git diff -U0 v3.83.0..v3.83.1 -- backend/config.py \
  | grep -E '^[+-].*(VERSION|GENERATOR_VERSION|DECISION_POLICY|CURRICULUM_VERSION|LISTENING_BANK_VERSION)'
# solo: -VERSION = "3.83.0"  /  +VERSION = "3.83.1"
```

Los valores vigentes y **sin mover** son: `CURRICULUM_VERSION = "1.3.1"`,
`LISTENING_BANK_VERSION = "7.0.0"`, `GENERATOR_VERSION = "1.4.0"` y
`DECISION_POLICY_VERSION = "v3.68.0"`. **Lo falsaría:** una columna nueva o un bump de
motor (**P0**).

**(3) El contrato de la API no crece: cero rutas nuevas.**

```bash
git diff v3.83.0..v3.83.1 -- backend/routers \
  | grep -E '^\+.*@router\.(get|post|put|patch|delete)'   # VACÍO
```

**Lo falsaría:** una ruta nueva o un cambio de forma en una respuesta (**P1**).

**(4) Existen OCHO gates y NINGUNO está en `pass`; la evidencia está a CERO.**

```bash
backend\.venv\Scripts\python.exe scripts\validation_gate.py status
#   [pending] G0 … [pending] G7   →  PENDIENTE: 8 de 8 gates sin `pass`.
Test-Path docs/audit/validation-evidence.json     # NO EXISTE
```

El candado **test** que lo fija en el CI es `backend/tests/test_docs_drift_v373.py`:

```bash
Select-String -Path backend/tests/test_docs_drift_v373.py -Pattern 'len\(GATES\) == 8'
# assert len(GATES) == 8, "el instrumento declara ocho gates, no otra cifra"
```

`validation-evidence.json` **no existe**, así que **ningún gate tiene un `record`**. Si
el auditor encuentra un `record` en cualquier forma (fichero, rama, nota en un doc,
captura en un informe), este invariante **cae**. Es el invariante más importante del
documento, igual que en los puntos de entrada de toda la serie.

**(5) El instrumento automático sigue en 10/10 y la evidencia no se ha inventado.**

```bash
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
#   10 pass · 0 fail · 0 skip
```

Debe salir **10/10** y los generados (`docs/audit/generated/release-validation.{md,json}`)
no deben cambiar al re-ejecutarlo. **Lo falsaría:** un informe regenerado a mano
(**P2**, instrumento viciado).

**(6) El producto NO se ha movido desde el tag — y ahora SÍ sin excepción.**

```bash
git diff --stat v3.83.1..main -- backend frontend/src launcher scripts   # VACÍO
```

Debe salir **VACÍO**. A diferencia de `v3.83.0` —cuyo candado tenía la **excepción
declarada** de `frontend/playwright.config.ts`—, esta serie **absorbe** ese cambio
dentro del propio tag (lo etiqueta `v3.83.1`), así que el candado fuerte se cumple
**literalmente**. **Lo falsaría:** cualquier fichero de producto con diferencia
(**P0** en `frontend/src`/`backend`, **P1** en lanzador).

**(7) El ancla de certificación está DESFASADA — y es un hallazgo, no un invariante que se cumpla.**

```bash
Select-String -Path docs/audit/KIT-VALIDACION-GATES.md -Pattern 'v3.81.0'
# las re-congelaciones fechadas siguen ancladas en v3.75.8, v3.76.0, v3.80.1 y v3.81.0
```

El **árbol congelado de la campaña** sigue siendo el de **`v3.81.0`**
(`6724d8be…`), pero desde entonces se publicó **producto que mueve el contrato y la
BD**: `V3.82.0` (contrato de sesión + migración) y `V3.83.0` (UI). **Este invariante
NO se cumple: es un hallazgo declarado**, y se somete a dictamen en §2-B. Lo que debe
hacer el auditor es **confirmar el desfase**, no tolerarlo por ser «documental».

### 1.2 Lista cerrada — el diff del arco, por área

```bash
git diff --shortstat v3.83.0..v3.83.1            #  20 files changed, 2990+/ 16-
git diff --shortstat v3.83.0..v3.83.1 -- backend #   1 file  changed,    1+/  1-
git diff --shortstat v3.83.0..v3.83.1 -- launcher        # (vacío)
git diff --shortstat v3.83.0..v3.83.1 -- scripts         # (vacío)
```

| Grupo | Ficheros | Notas |
|---|---|---|
| Producto | `backend/config.py` | **solo** la línea `VERSION` |
| Pruebas visuales | `reducedMotionAndZoom.spec.ts` (modificado) + `dictionaryFlashcardsBridge.spec.ts`, `studySessionKeyboard.spec.ts`, `studySessionVisual.spec.ts` (nuevos) | la corrección de H2 y las tres sondas de `AU` §6 |
| Arnés | `frontend/playwright.config.ts` (`workers`) | el `fd086e8` de `AU` **H4**, ahora **dentro** del tag |
| Versión | `frontend/package.json`, `frontend/package-lock.json` | `3.83.0 → 3.83.1` |
| Documentación | `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md`, `docs/audit/AU-…`, `docs/audit/PARKED.md`, `agentes/*-v382.md`, `agentes/*-v383.md`, `release-notes-v3.83.0.md`, `release-notes-v3.83.1.md` | — |
| Generados | `docs/audit/generated/release-validation.{json,md}` | regenerados con `3.83.1` |

### 1.3 La trampa de esta serie: el commit del tag SÍ tiene run; el de `v3.82.0` NO

A diferencia del arco `AV` —cuyo commit de tag **no tenía ninguna run de CI**
(`agentes/auditoria-total-externa-v382.md` §1.4)—, aquí el commit del tag es **el tip
de `main`** y **sí** fue certificado por el push:

| Certificación | Valor |
|---|---|
| Workflow | `CI` · evento `push` · rama `main` |
| Run del commit del tag (`4ee32e5`) | **`36042834375`** — `conclusion = success` |
| `v3.83.0` (`e05b3dd`) | `35995172219` — `success` |
| `v3.82.0` (`3f686a0`) | **NINGUNA** |
| Los ocho gates | **`pending`** · sin `validation-evidence.json` |

**El CI no dispara en tags** (`.github/workflows/ci.yml` escucha `push: branches:
[main]` y `pull_request`): quien audite «el CI del tag» audita el CI del commit al que
apunta. Y aquí, por suerte, **existe y está verde**; en `v3.82.0`, no —lo que **no**
queda resuelto por este parche—.

---

## 2. Preguntas falsables por área

### A. El ancla, el rango y la serie

- **A1.** ¿El rango `v3.83.0..v3.83.1` tiene **nueve** commits, de los cuales **ocho
  ya estaban en `main`** y solo **uno** es el release? `git log --oneline
  v3.83.0..v3.83.1`. **Dictamina:** ¿es sano que el tag **absorba** la cola de
  auditoría del tag anterior, o convierte al tag en «la cola + el parche» (como el
  propio release-notes declara)? ¿Mejora o empeora la auditabilidad frente a `v3.83.0`,
  cuyo rango era de **un** commit?
- **A2.** **H4 quedó resuelto por absorción.** `fd086e8` (el arnés) está **dentro** del
  tag `v3.83.1`, así que la pregunta «¿un cambio de arnés posterior a un tag debe
  llevar su propio tag?» se responde **sí, y aquí lo tiene**. **Dictamina** si eso
  cierra H4 del todo o si deja una regla sin escribir (¿todo cambio no-`.md`
  posterior a un tag exige tag nuevo?).
- **A3.** El `release-notes-v3.83.1.md` §6.2 declara que **el diff del tag incluye los
  ocho commits que ya estaban en `main`**. ¿La declaración es **exacta y suficiente**
  para que un auditor no se sorprenda, o el rango de nueve commits sigue siendo una
  trampa sin declarar? Contrástalo con la lista de §1.2.

### B. Los ocho gates y el árbol de certificación (el núcleo)

- **B1.** **La pregunta central de este documento.** El ancla de la campaña
  (`docs/audit/KIT-VALIDACION-GATES.md`) sigue en **`v3.81.0`**, pero entre ella y el
  árbol actual se publicó **producto que cambia el contrato de sesión y migra la BD**
  (`V3.82.0`) y **producto de UI** (`V3.83.0`). **Dictamina:** ¿puede arrancar la
  campaña con un ancla que **no** es la del árbol actual? ¿Basta la re-congelación
  fechada —sin `record` grabados que invalidar— o hay que re-derivar
  `docs/audit/generated/` (los nueve dossiers de G7) **antes** de la primera sesión?
  **Esta es la pregunta que decide si la serie está lista para certificar.**
- **B2.** ¿Los **ocho** gates están **definidos** y **documentados**, y el instrumento
  lo fija? Comprueba `len(GATES) == 8`, la presencia de cada id en el runbook y que
  `validation_gate.py auto` lo declare. ¿La cifra vigente es **8** —no 7— en todas las
  secciones **sin fecha**?
- **B3.** ¿`G0 · identidad-cuentas` puede declararse `pass` hoy? La respuesta depende
  del contador `without_password` de la **BD de uso**: en este equipo es **2**
  (`J.A`, `Paz`), ambas pendientes de activación. **Dictamina** si eso deja G0
  `pending` **por acción de uso** (no por código) y si el gate está bien definido
  para vigilar una **cola de tareas** y no un agujero.
- **B4.** Los otros siete gates exigen **acción humana/hardware** (corte de red físico,
  máquina limpia, Windows real, dispositivos, audio real, recorridos, pedagogía).
  ¿Ninguno es simulable con honestidad en CI? ¿La clasificación `human=True` de los
  ocho es correcta, o alguno podría cerrarse con evidencia de CI?
- **B5.** `status --strict` y `status --strict --same-tree`. ¿Cuál es la puerta real de
  V4.0 y qué exige exactamente? `--same-tree` **no puede** cerrarse hoy porque **no hay
  evidencia**: ¿queda claro en la documentación, o algún texto sin fecha da a entender
  que los gates están cerca de cerrarse?

### C. La deuda P1/P2/P3 y su clasificación

- **C1.** **H1 (`_collection_writable` → `not owner`) sigue vivo** en
  `backend/domain/retention.py` (línea ~185). **Dictamina** si su severidad real es
  `P2` (heredado, no alcanzable desde la UI, con filtro de cliente fijado por E2E) o
  si su existencia **bloquea** la certificación. ¿Aceptar deuda `P2` es compatible con
  declarar «serie lista para certificar»?
- **C2.** **H5** (`add_item` no atómico: un fallo posterior puede pintar «No se pudo
  añadir» cuando la palabra **ya está** en el léxico). ¿Es `P2` de mensaje o `P1` de
  honestidad al alumno? **Dictamina** con la matriz de severidades de §4.
- **C3.** **H3** (`Sparkles` celebra también el 0 %). ¿Cosmético (`P3`) o engaño de
  gamificación (`P2`)? Compáralo con la definición de «acierto de la sesión» que la
  release `v3.83.0` declara al alumno.
- **C4.** **H4 · `P2`** (arnés posterior al tag). ¿Sigue abierto tras `v3.83.1`, que lo
  absorbe (ver A2)? **Dictamina** si hay que retirarlo del inventario por resuelto.
- **C5.** **Cola pedagógica heredada de V3.70** (`docs/audit/PARKED.md` §V3.70: 1 P0 ·
  15 P1 · 12 P2 · 5 P3). El **P0** se cerró en `V3.75.1`. ¿Cuáles de los **P1/P2**
  siguen abiertos contra el árbol actual y cuáles se cerraron en V3.75–V3.83 sin
  actualizar la lista? Reconcilia y **dictamina**: ¿alguna de esas deudas es
  **bloqueante** de la certificación pedagógica (G7)?
- **C6.** **E6/H6 · Dependabot.** `AU` §11 dictaminó los dos rojos (`#10`
  `react`/`react-dom` desparejados, `#13` `vite` 8 no instalable). Hoy hay **12 PRs
  abiertos** (`#7`–`#18`) y **los dos siguen rojos**; los otros **diez** siguen **sin
  dictaminar**. ¿Es deuda `P2` de mantenimiento —no bloquea release— o puede un bump
  no instalable enmascarar una rotura real? **Dictamina** el plan de cierre.

### D. Readiness para la certificación final

- **D1.** ¿**Qué bloquea exactamente** empezar la campaña de los ocho gates, y qué
  **no**? Separa: (a) la **campaña física** (los ocho `record` que faltan), (b) el
  **ancla de certificación** desfasado (§2-B), (c) el **informe `AV` pendiente** del
  arco que cambia el contrato, (d) las deudas `P2` aceptadas (H1, H5, Dependabot).
- **D2.** ¿`v3.83.1` es el **árbol correcto** para congelar la campaña, o habría que
  congelar en `v3.83.0` por ser «la release de producto»? **Dictamina** con la regla de
  re-congelación del kit: el árbol que se certifica es **el que incluye toda la
  instrumentación** (el arreglo de H2), no el último producto.
- **D3.** ¿La **serie V3.83.x** puede declararse **cerrada** con `v3.83.1` como última
  etiqueta, o falta algo antes de V4.0.0? En particular: ¿basta el parche de
  instrumento, o el cierre exige también el **informe `AV`** del eslabón crítico?
- **D4.** ¿Hay **alguna promesa sin cerrar** en `CHANGELOG.md §3.83.1`, `PLAN.md` o
  `docs/audit/PARKED.md` que se presente como cerrada sin estarlo? Un cierre de serie
  no puede apoyarse en deuda disfrazada.

### E. Deriva documental y honestidad de la release

- **E1.** ¿Queda algún texto **sin fecha** que afirme una versión vigente distinta de
  `3.83.1`, o un recuento de gates distinto de **8**?
  `git grep -n -E '3\.8[0-2]\.[0-9]' -- '*.md'` y distingue lo **fechado** (correcto
  para su fecha) de lo que describe el **estado actual**.
- **E2.** `release-notes-v3.83.1.md` §6 «Honestidad» hace **cinco** afirmaciones
  (no arregla producto; el diff incluye los 8 commits; **H1 sigue vivo**; el árbol de
  certificación no se mueve; el CI no dispara en tags). **Contradice una** de ellas con
  el árbol y tendrás el hallazgo. **Es el ejercicio más rentable de este documento.**
- **E3.** La afirmación «**el árbol de certificación no se mueve**» (§6.4) — ¿es cierta
  o es una **ambigüedad peligrosa**? El instrumento no cambia, pero **el ancla
  documental sí está desfasada** (§1.1-7). **Dictamina** si la frase induce a error.
- **E4.** ¿La corrección de **H2** es verificable **en el tag** y **muerde**? Ejecuta el
  spec de `reducedMotionAndZoom` y comprueba que usa `page.emulateMedia` **y** la
  guarda `matchMedia(...).matches === true`; si alguien volviera a `test.use({
  reducedMotion })`, ¿fallaría el test? **Un gate que se corrige a posteriori debe
  demostrar que ahora muerde.**
- **E5.** `docs/audit/PARKED.md` §V3.83.0 declara que `frontend/dist` **no se
  reconstruyó**. ¿Sigue el artefacto de la UI desfasado respecto a `3.83.1`? Compáralo
  y **dictamina** si eso afecta a `check_dist_artifact` / `--require-dist` (que hoy
  pasa) o solo a la afirmación «el artefacto de la UI está construido».

---

## 3. Matriz de cierre (la rellena el auditor)

| ID | Área | Dictamen (`pass`/`fail`/`no verificado`) | Evidencia (comando o fichero) | Severidad si `fail` |
|---|---|---|---|---|
| A1 | Rango de 9 commits (8 + release) | | `git log --oneline v3.83.0..v3.83.1` | P2 |
| A2 | H4 resuelto por absorción | | `fd086e8` dentro de `v3.83.1` | P2 |
| A3 | Declaración de la cola en notas | | `release-notes-v3.83.1.md §6.2` | P2 |
| B1 | Ancla de certificación desfasada | | `KIT-VALIDACION-GATES.md` (v3.81.0) | P1 |
| B2 | Ocho gates definidos y documentados | | `len(GATES) == 8` + runbook | P1 |
| B3 | `G0` y `without_password` | | `validation_gate.py status` + BD (2) | P1 |
| B4 | Los ocho son de acción humana | | `Gate.human = True` ×8 | P2 |
| B5 | Puerta real de V4.0 (`--strict`/`--same-tree`) | | `validation_gate.py status --strict` | P1 |
| C1 | H1 (`not owner`) | | `retention.py` ~185 + `AU §12` | P2 |
| C2 | H5 (alta no atómica) | | `retention.py::add_item` | P2 |
| C3 | H3 (celebración 0 %) | | `AU §5-H3` | P3 |
| C4 | H4 en inventario | | `AU §5-H4` + `v3.83.1` | P3 |
| C5 | Cola pedagógica V3.70 vigente | | `PARKED.md §V3.70` | P1–P2 |
| C6 | Dependabot (12 PRs) | | `gh pr checks 10` / `13` | P2 |
| D1 | Qué bloquea y qué no | | síntesis de B/C | — |
| D2 | Árbol correcto para congelar | | `v3.83.1` vs `v3.83.0` | P1 |
| D3 | ¿Serie cerrada o falta AV? | | `agentes/auditoria-total-externa-v382.md` | P1 |
| D4 | Promesas sin cerrar | | `CHANGELOG §3.83.1`, `PLAN.md`, `PARKED.md` | P1 |
| E1 | Deriva de versión / gates | | `git grep -n '3.8[0-2]' -- '*.md'` | P3 |
| E2 | Las cinco de «Honestidad» | | `release-notes-v3.83.1.md §6` | P1–P3 |
| E3 | «El árbol de certificación no se mueve» | | §6.4 vs §1.1-7 | P2 |
| E4 | H2 muerde en el tag | | `reducedMotionAndZoom.spec.ts` + `npx playwright test` | P2 |
| E5 | `frontend/dist` desfasado | | `PARKED.md §V3.83.0` + mtime de `dist` | P3 |

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se recrea ningún tag, no se fuerza ningún push, no se
   reescribe historia. Si el auditor necesita una corrección, va **después** del tag,
   en un commit documental, y se declara.
2. **Nada se da por bueno por lo que diga un documento de la casa**, y eso incluye
   **estas notas** y el informe **`AU`**, que aquí se hereda pero se puede contradecir:
   cada cifra de este prompt se ha verificado por comando **antes** de entregarlo.
3. **El ancla es el tag, no la página de Release.**
4. **Los invariantes se comprueban antes de puntuar**, y si alguno no se cumple, eso
   **es** el hallazgo: no se reinterpreta el invariante para que encaje. El invariante 7
   (ancla desfasada) **NO se cumple** y es un hallazgo declarado.
5. **Severidades:** `P0` = rompe una promesa de seguridad, privacidad o **de datos del
   alumno**; `P1` = engaña al operador o al alumno sobre el estado real, o **bloquea la
   certificación**; `P2` = deuda declarada o fragilidad de instrumento; `P3` =
   cosmético o de rastro.
6. **Un cierre de serie vale lo que vale su ancla.** Si el árbol que se certifica no es
   el árbol actual, ningún `10/10` de instrumento lo tapa.

---

## 5. Honestidad esperada del informe

El informe (`AW`) debe declarar explícitamente, aunque nadie lo pregunte:

- Que **`v3.83.1` no arregla el producto**: etiqueta el árbol y cierra la letra; el
  único cambio en `backend/` es `VERSION` y `frontend/src`/`launcher/` están **intactos**.
- Que **el diff del tag incluye los ocho commits que ya estaban en `main`** (6
  `docs(audit)` + 2 `test(visual)`), no solo el commit de release.
- Que **H1 sigue vivo en el código** y esta serie lo **sitúa** fuera de un patch de
  instrumento; **no** lo rebaja ni lo cierra.
- Que **los ocho gates siguen `pending`** y `validation-evidence.json` **no existe**:
  no hay ninguna aprobación física que la release pueda estar blanqueando.
- Que **el CI no dispara en tags**: la run que certifica el commit del tag es la del
  push a `main` (`36042834375`, `success`), y eso **contrasta** con `v3.82.0`, cuyo
  commit **no tiene ninguna run** (`AV` §1.4).
- Que **el ancla de certificación está desfasada** (`v3.81.0`) y **eso no lo arregla**
  un parche de instrumento: es una decisión de cierre.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

- **D1. El informe `AV` no existe todavía.** `agentes/auditoria-total-externa-v382.md`
  está entregado (reserva `AV`) pero `docs/audit/AV-AUDITORIA-TOTAL-V382.md` **no
  existe**. El arco `v3.81.2..v3.82.0` —el que **cambia el contrato de `POST
  /api/session` y migra la BD**— sigue **sin dictamen**. **Pregunta:** ¿puede la serie
  V3.83.x declararse **cerrada** y empezar la certificación con el eslabón crítico sin
  informe? **Dictamina** si es bloqueante de serie.
- **D2. El commit de `v3.82.0` no tiene ninguna run de CI.** Ya contado en §1.3: la
  Release de `v3.82.0` se publicó **antes** de que existiera una run que cubriera su
  código, y la primera que llegó cubría **otro** commit. **Dictamina** si el parche
  `v3.83.1` —cuyo commit **sí** tiene run verde— **resuelve** esa deuda o solo la deja
  a un lado.
- **D3. El ancla de certificación sigue en `v3.81.0`.** Declarado en §1.1-7 y §2-B1.
  No es una errata: es un **desfase real** entre el árbol que se dice certificar y el
  árbol actual, tras dos releases de producto.
- **D4. `frontend/dist` puede estar desfasado.** `PARKED.md §V3.83.0` declara que no se
  reconstruyó, y el artefacto en disco tiene fecha anterior a `3.83.1`. Como
  `check_dist_artifact` solo comprueba que el `index.html` sea servible, **pasa** sin
  decir de qué versión es. **Dictamina** si eso basta o si el kit debería exigir la
  versión de build.
- **D5. Los 12 PRs de Dependabot siguen abiertos.** `AU` §11 cerró el dictamen de
  **dos** (`#10`, `#13`); los **diez** restantes siguen sin dictaminar. **Pregunta:**
  ¿es `P2` de mantenimiento o hay rotura real escondida en un bump no instalable?

---

## 7. Alcance

**Dentro:** la serie **`v3.81.2..v3.83.1`** como unidad de cierre —con foco en
`v3.83.0..v3.83.1`—, los **ocho gates** y su ancla, el **inventario de deuda**
(`PARKED.md`, `AU §5`, `RE-GATES-DERIVA.md`) y el **veredicto de readiness** para
V4.0.0.

**Fuera (y se hereda):** la funcionalidad de producto de `v3.83.0` se audita con
`agentes/auditoria-total-externa-v383.md` (informe `AU`); el contrato, la identidad y la
migración de `v3.82.0`, con `agentes/auditoria-total-externa-v382.md` (informe `AV`,
**pendiente**); la gestión de usuarios, con `agentes/auditoria-total-externa-v381.md`.
**Este documento no repite sus preguntas.**

**Fuera también, y declarado como deuda:** el arco `v3.81.2..v3.82.0` sigue sin
**informe** (§6-D1), aunque ya tenga **encargo**.

---

## 8. Nota de prefijos y cierre

- **El primer prefijo libre es `AW`, y este es el punto de entrada que lo reserva**:
  el informe esperado es `docs/audit/AW-AUDITORIA-CIERRE-V383.md`. Reservados:
  **`AP`** (`v3.75.7`), **`AQ`** (`v3.77.1`), **`AR`** (`v3.80.0`), **`AS`**
  (`v3.81.1`), **`AT`** (`v3.81.2`), **`AU`** (dictaminado, `v3.83.0`) y **`AV`**
  (`v3.82.0`, pendiente).
- **Cadena de puntos de entrada:** `v321` → `v322` → `v323` → `v346` → `v373` →
  `v375` → `v3751` → `v3757` → `v3771` → `v380` → `v381` → `v3812` → `v382` →
  `v383` → **`cierre-global-v383`** (este).
- **Este documento se entrega en un commit documental posterior al tag `v3.83.1`**,
  con el ancla en `v3.83.1` y **sin mover producto**: el invariante 6 de §1.1 es la
  prueba, y el auditor debe ejecutarlo antes de empezar a puntuar.
- **Lo que este documento NO es:** no es la auditoría, es el encargo. No adelanta
  veredictos, no maquilla los invariantes para que se cumplan y no promete que todo
  vaya a salir verde. La serie que describe **cierra la instrumentación pero deja los
  ocho gates sin ejecutar y el ancla de certificación desfasada**, y eso —que una fase
  de instrumento se declare cerrada mientras la fase de certificación no ha empezado—
  es justamente lo que hay que dictaminar.
