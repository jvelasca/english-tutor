# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.82.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **la release que cambia el
> contrato de arranque de sesión y migra la base de datos**: el alta profesional de
> cuentas —solicitud autorizada, invitación, activación, entrada por email y
> recuperación—. Es la revisión **de solo lectura**: no se cambia código, datos,
> configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué AHORA.** Porque este arco **no tenía punto de
> entrada** y es, con diferencia, **el más grande y el más arriesgado de la serie**.
> Los puntos de entrada de `v3.81.2` y de `v3.83.0` **lo declaran como deuda** —el
> segundo lo hace por escrito, en su §6-D1, y el primero no lo cubre—, y mientras
> tanto el arco ha quedado **sin encargo** entre dos auditorías que sí lo tienen.
> `agentes/auditoria-total-externa-v3812.md` audita el **parche de privacidad**
> (`v3.81.1..v3.81.2`); `agentes/auditoria-total-externa-v383.md` audita el
> **diccionario a Flashcards** (`v3.82.0..v3.83.0`). **Ninguno audita esto.**
>
> **Aviso de encuadre (léelo antes de puntuar).** Este es el arco que **retira** una
> ruta de registro, **despublica** un listado de cuentas, **elimina** la entrada sin
> contraseña, **introduce ocho columnas** y **cambia la forma del cuerpo de
> `POST /api/session`** —con frontend, lanzador y sus tests coordinados en el mismo
> lanzamiento—. No es un arco «de UI»: es el que **define quién puede entrar y cómo**.
> Y trae un hallazgo **ya visible desde la primera comprobación** (§1.4): **el commit
> de la release no tiene ninguna run de CI que lo certifique.**
>
> **Continuidad con los puntos de entrada vecinos.**
> `agentes/auditoria-total-externa-v381.md` **no se retira**: cubre el cuerpo de la
> gestión de usuarios. `agentes/auditoria-total-externa-v3812.md` cubre el cierre de
> G0 (privacidad del historial, orden del evento de purga, migración heredada) y
> **se añade en este mismo arco**. `agentes/auditoria-total-externa-v383.md` cubre el
> delta siguiente. Este documento cubre **solo el delta `v3.81.2..v3.82.0`** y **no
> repite** aquellas preguntas: las hereda y las referencia.
>
> **Estado del punto de entrada:** entregado 2026-09-24 en un **commit documental
> POSTERIOR al tag `v3.82.0`** —y posterior incluso a `v3.83.0`—, porque **un tag
> publicado no se recrea** (regla de `docs/audit/KIT-VALIDACION-GATES.md`). El ancla
> sigue siendo `v3.82.0` y **el producto no se mueve** para entregar esto; el
> invariante que lo demuestra está declarado y se comprueba por comando (§1.1,
> invariante 9).
>
> **Informe esperado:** `docs/audit/AV-AUDITORIA-TOTAL-V382.md`. Prefijo **`AV`**
> porque **`AU` quedó reservado por el punto de entrada de `v3.83.0`** (que lo dice
> por escrito). `AP` (`v3.75.7`), `AQ` (`v3.77.1`), `AR` (`v3.80.0`), `AS`
> (`v3.81.1`) y `AT` (`v3.81.2`) **siguen reservados y sin informe**. Ver §8.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — la entrada `V3.82.0`, y el «START HERE» de cabecera.
2. `release-notes-v3.82.0.md` — las notas **de la release que se audita**. Su §5
   «Honestidad» enumera **siete** límites declarados, y cada uno es una pregunta
   encubierta.
3. `CHANGELOG.md §3.82.0` — la misma release contada al detalle, con la **verificación**
   completa.
4. `backend/routers/session.py` — **el cambio de contrato**: `{user_id}` → `{email,
   password}`, el **401 genérico** y el **403 `ACCOUNT_NOT_ACTIVATED`**.
5. `backend/routers/account.py` — las **tres escrituras nuevas sin sesión**
   (`activate`, `forgot-password`, `reset-password`).
6. `backend/routers/users.py` — `POST /api/profile-requests` (la solicitud) y
   `GET /api/users` (ya con sesión); y `backend/routers/admin.py` —
   `POST /api/admin/users/{id}/resend-activation` (el reenvío de la invitación).
7. `backend/repositories/db.py` — **la migración**: las **cuatro** columnas de
   `users` y las **cuatro** de `profile_requests`, con el `ALTER TABLE` idempotente.
8. `backend/repositories/users.py` — el ciclo de vida: `auth_epoch`, hash de
   contraseña, búsqueda por email.
9. `backend/tests/test_public_surface.py` — **el candado** de la superficie sin sesión.
10. `backend/scripts/migrate_legacy_accounts.py` — la migración heredada (simula por
    defecto) y `backend/scripts/e2e_accounts_v382.py` — el protocolo de `G0`.
11. El lanzador: `launcher/launcher.py`, `launcher/widgets.py`, `launcher/ui.py` — la
    cola de solicitudes, el enlace copiable y «📨 Reenviar invitación».
12. `docs/audit/TEMPLATE.md` — el formato del informe.

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
```

---

## 0.1 El rango tiene CUATRO commits: uno de producto y TRES documentales

A diferencia de `v3.82.0..v3.83.0` (que era **un solo commit**), aquí el rango
arrastra documentación y hay que declararlo antes de contar:

```bash
git log --oneline v3.81.2..v3.82.0
# 3f686a0 release(v3.82.0): alta profesional de cuentas - solicitud autorizada, invitacion, entrada por email y recuperacion
# 88e998a docs(audit): publica la Release de v3.81.2 y ancla el candado post-tag por invariante, no por SHA
# 0b85e69 docs(audit): punto de entrada externo anclado a v3.81.2 y la deriva del recuento de gates
# ea65561 docs(v3.81.2): sella la run de CI en las notas y declara la errata del commit posterior al tag
```

**Tres** de esos cuatro commits son `docs(...)`: son la **publicación del punto de
entrada y de la Release de `v3.81.2`**, que se entregaron **después** de su tag y
quedaron por debajo de `v3.82.0` al avanzar la rama. **Solo `3f686a0` es producto**, y
es el que lleva el tag. Que el rango «contenga» cuatro commits **no** dice nada malo
del arco: dice que el anterior dejó su cola **dentro** de este rango.

La lista cerrada del **release** está en §1.2; la de **todo el arco**, en §1.3.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.82.0`.** Los identificadores se resuelven
  con git, no se fijan a mano:

```bash
git fetch --tags
git rev-parse v3.82.0                 # objeto del tag anotado (b85b20f)
git rev-parse 'v3.82.0^{commit}'      # commit de release (3f686a0)
git rev-parse 'v3.81.2^{commit}'      # commit del tag anterior (base del delta)
git log -1 --format='%H %s' 'v3.82.0^{commit}'
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA. El ancla es el **tag**, el estado de
  publicación se **verifica por comando**, y este archivo es coherente **dentro de su
  propio tag**.
- **Base de comparación:** `v3.81.2`. Los puntos de entrada **vecinos** existen y se
  referencian (§0); lo que **faltaba** era **este**.
- **El árbol de certificación NO se mueve con esta release** en el sentido de que
  **no se re-anclan** los gates: siguen **ocho** (verificado, §1.1-7). Lo que **sí**
  cambia es **la definición de `G0 · identidad-cuentas`**, que pasa de vigilar un
  agujero abierto a vigilar una **cola de tareas**.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

Se declaran **nueve** invariantes, cada uno con el comando que lo comprueba. **Ocho se
cumplen; el noveno FALLA y es el hallazgo principal del arco** (§1.4).

**(1) La migración es ADITIVA: ninguna tabla ni ningún índice nuevos.**

```bash
git diff v3.81.2..v3.82.0 -- backend/repositories/db.py \
  | grep -E '^\+.*(CREATE TABLE|CREATE INDEX|CREATE UNIQUE INDEX)'
```

Debe salir **vacío**. Comprobado además que el índice único de email
(`idx_users_email`) **ya existía** en `v3.81.2`: no es nuevo. Una BD de `v3.81.2` se
abre intacta. **Lo falsaría:** cualquier línea de salida (**P0**).

**(2) La migración son OCHO columnas exactas, con `ALTER TABLE` idempotente.**

```bash
git diff v3.81.2..v3.82.0 -- backend/repositories/db.py
# users:              activation_token_hash, activation_sent_at,
#                     password_reset_token_hash, password_reset_sent_at
# profile_requests:   email, avatar_color, avatar_emoji, avatar_image
```

Las cuatro de `profile_requests` van precedidas de un `PRAGMA table_info(...)` **que
no existía** en `v3.81.2` (verificado). **Lo falsaría:** una columna `NOT NULL` sin
`DEFAULT` (rompería la migración de una BD con filas) o un `DROP`/`RENAME`
(**P0**).

**(3) El contrato de `POST /api/session` CAMBIA: `{user_id}` → `{email, password}`.**

```bash
git diff v3.81.2..v3.82.0 -S'user_id' -- backend/routers/session.py
# -    user = await user_service.get_user(body.user_id)
# -    await _require_password_if_set(body.user_id, body.password)
# +    email = credentials.normalize_email(body.email)
# +    user = await user_service.find_by_email(email) if email else None
# +        raise HTTPException(status_code=403, detail="ACCOUNT_NOT_ACTIVATED")
# +    if not credentials.verify_password(stored, body.password): …
```

Es **el** cambio incompatible del arco. **Lo falsaría:** que un `user_id` siguiera
bastando para abrir sesión (**P0**).

**(4) El registro autoservicio SE RETIRA.**

```bash
git diff v3.81.2..v3.82.0 -- backend/routers | grep -E '^-\s*@router'
# -@router.post("/api/users", response_model=User)
```

**(5) `GET /api/users` deja de ser público.**

```bash
git diff v3.81.2..v3.82.0 -- backend/routers | grep -n 'Depends(current_user)'
# +    include_test: bool = False, session_user: dict = Depends(current_user)
```

La puerta ya no enumera a nadie sin sesión. **Lo falsaría:** que el listado volviera a
responder `200` sin credencial (**P0**).

**(6) La superficie sin sesión queda PINADA por un candado que muerde.**

```bash
git log --oneline v3.81.2..v3.82.0 -- backend/tests/test_public_surface.py   # 3f686a0
```

El fichero **ya existía desde V3.75** y **se amplía aquí**. Debe declarar la lista de
rutas que **sí** responden sin sesión (`/api/health*`, `/api/profile-requests`,
`/api/models`, `/api/network`, `/api/system/status`) y la de las que **no**
(`/api/users: 401`, `/api/settings: 401`, `/api/progress: 401`, …). **Lo falsaría:**
un endpoint de datos que responda sin sesión y **no** esté en ninguna de las dos
listas (**P0**).

**(7) Sin bumps pedagógicos ni de instrumento.**

```bash
git diff v3.81.2..v3.82.0 -- backend/config.py \
  | grep -E '^[+-].*(VERSION|GENERATOR_VERSION|DECISION_POLICY|CURRICULUM_VERSION|LISTENING_BANK_VERSION)'
# solo: -VERSION = "3.81.2"  /  +VERSION = "3.82.0"
```

Los valores sin mover: `CURRICULUM_VERSION = "1.3.1"`, `LISTENING_BANK_VERSION =
"7.0.0"`, `GENERATOR_VERSION = "1.4.0"`, `DECISION_POLICY_VERSION = "v3.68.0"`.

**(8) Siguen OCHO gates y la evidencia sigue a CERO.**

```bash
git show v3.82.0:backend/tests/test_docs_drift_v373.py | grep 'len(GATES)'
# assert len(GATES) == 8, "el instrumento declara ocho gates, no otra cifra"
git show v3.82.0:docs/audit/validation-evidence.json     # NO EXISTE
```

No añade gate ni lo retira; **no hay ninguna aprobación física** que la release pueda
estar blanqueando.

**(9) [FALLA] El commit del tag está certificado por una run de CI.**

```bash
gh api repos/jvelasca/english-tutor/commits/$(git rev-parse 'v3.82.0^{commit}')/check-runs \
  --jq '.total_count'
# 0
gh api repos/jvelasca/english-tutor/commits/$(git rev-parse 'v3.82.0^{commit}')/status \
  --jq '.state, .total_count'
# pending
# 0
```

**Y no es un fallo de la API: no hay ninguna run que lo cubra.** Las runs de sus
**ancestros** existen (`ea65561` → `35927208170`, `0b85e69` → `35928498666`,
`88e998a` → `35962273497`, las tres `success`) y la de su **hijo** también
(`e05b3dd` → `35995172219`, `success`)… pero **la del commit intermedio no existe**.
Comparativa en la misma consulta:

```bash
gh api repos/jvelasca/english-tutor/commits/$(git rev-parse 'v3.83.0^{commit}')/check-runs --jq '.total_count'
# 14
```

**La causa más probable, que hay que dictaminar y no dar por segura:** el CI **no
dispara en tags** (`ci.yml` escucha `push: branches: [main]` y `pull_request` —lo dice
por escrito el punto de entrada de `v3.83.0`—), y si el commit de la release se hizo
alcanzable **por el push de su tag** antes de que la rama lo llevara, **nunca fue el
tip de un push a `main`** y por tanto **nunca tuvo run propia**. La run de `e05b3dd`
**sí ejercita su árbol**, pero **combinado con v3.83.0**, nunca en aislamiento.
**Lo falsaría:** una run borrada (no hay rastro) o un push a `main` cuyo tip fuera
`3f686a0` (no lo hay en la ventana que lo rodea). **Severidad si se confirma: P1** —
la Release se publicó marcando un commit **sin certificar**.

### 1.2 Lista cerrada — el único commit de producto del rango

| # | SHA | Mensaje | Naturaleza |
|---|---|---|---|
| 1 | `3f686a0` | `release(v3.82.0)`: alta profesional de cuentas — solicitud autorizada, invitación, entrada por email y recuperación | **PRODUCTO — `v3.82.0`** |

Los otros tres commits del rango (`ea65561`, `0b85e69`, `88e998a`) son **documentales**
y pertenecen a la **cola de `v3.81.2`**, no a esta release.

### 1.3 Lista cerrada — el diff del arco, por área

```bash
git diff --shortstat v3.81.2..v3.82.0              # 96 files changed, 9378+/ 3537-
git diff --shortstat v3.81.2..v3.82.0 -- backend   # 29 files changed, 3778+/ 1468-
git diff --shortstat v3.81.2..v3.82.0 -- frontend/src  # 34 files changed, 2369+/ 1647-
git diff --shortstat v3.81.2..v3.82.0 -- launcher  #  9 files changed, 1335+/  154-
git diff --shortstat v3.81.2..v3.82.0 -- backend/scripts  # 3 files changed, 1396+/ 943-
git diff --shortstat v3.81.2..v3.82.0 -- backend/tests    # 10 files changed, 1346+/ 274-
```

**Ficheros AÑADIDOS (16)** — la lista es cerrada:

| Grupo | Ficheros |
|---|---|
| Backend | `backend/scripts/e2e_accounts_v382.py`, `backend/scripts/migrate_legacy_accounts.py`, `backend/tests/test_accounts_v382.py` |
| Frontend (cuenta) | `components/{RequestAccessForm,ForgotPasswordForm}.tsx`, `features/account/{AccountPage,AccountActivate,AccountReset,AccountVerify,NewPasswordForm}.tsx`, `features/account/AccountPages.test.tsx` |
| Frontend (sonda) | `tests/visual/accountPages.spec.ts` |
| Lanzador | `launcher/widgets.py`, `launcher/tests/test_widgets.py` |
| Documentación | `release-notes-v3.82.0.md`, `agentes/auditoria-total-externa-v3812.md` |

**Ficheros BORRADOS (4)** — y **estos son los que hay que mirar dos veces**:

| Fichero | Qué era |
|---|---|
| `backend/scripts/e2e_accounts_v381.py` | el E2E anterior: se retira porque mantenía una API que ya no existe |
| `frontend/src/utils/session.ts` | la sesión **de cliente** (el «dispositivo local») |
| `frontend/src/utils/session.test.ts` | su test |
| `frontend/src/utils/localDevice.ts` | el almacén del perfil recordado en el navegador |

Que **desaparezca `session.ts`** es la mitad cliente del cambio de contrato, y es tan
importante como el `POST /api/session` del servidor: **si algo siguiera leyendo ese
almacén, se estaría entrando por una puerta que el servidor ya no abre.** Compruébalo
(§2-B, §2-F).

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
git tag --list 'v3.82*'                  # v3.82.0
gh api repos/jvelasca/english-tutor/git/ref/tags/v3.82.0   # tag anotado en el remoto
gh release view v3.82.0                  # la Release publicada (cuerpo = notas)
gh api repos/jvelasca/english-tutor/releases/latest --jq .tag_name   # v3.83.0 (ya avanzó)
```

| Certificación | Valor |
|---|---|
| Release publicada | **`v3.82.0`** — `draft = false` · `prerelease = false` · publicada **2026-09-24 12:39:37Z** |
| **Run del commit del tag** | **NINGUNA** — `check-runs: 0`, `statuses: []`, `state: pending` (§1.1-9) |
| Run del hijo (`e05b3dd`, `v3.83.0`) | `35995172219` — `success` — 2026-09-24 11:48:20Z |
| Run del padre documental (`88e998a`) | `35962273497` — `success` — 2026-09-24 05:57:57Z |
| Commit de release, fecha | `2026-09-24 13:43:52 +02:00` (= `11:43:52Z`) |

**Lectura de la tabla, que es el corazón de §1.1-9:** el commit se creó a las
`11:43:52Z`, la Release se creó **67 segundos después** (`11:44:59Z`) y **la primera
run que lo abraza es la de su hijo, a las `11:48:20Z`**. Es decir: **la Release de
`v3.82.0` se publicó antes de que existiera ninguna run que cubriera su código**, y
esa run, cuando llegó, cubría **otro** commit.

> **Aviso de anclaje.** `/releases/tag/v3.82.0` **sí** responde hoy (la Release se
> publicó el 2026-09-24), pero hasta ese día `v3.82.0` existía **solo como tag**.
> Quien audite por la página de Releases verá **`v3.83.0` como «Latest»**: la release
> auditada es **este documento**, no la que anuncia esa página.

---

## 2. Preguntas falsables por área

### A. El ancla, el rango y la trampa del tag

- **A1.** ¿El rango `v3.81.2..v3.82.0` tiene **cuatro** commits, de los cuales **uno
  solo** es producto? ¿Es sano que un arco «contenga» la cola documental del
  anterior, o debería haber avanzado por otro camino? Clasifícalos tú mismo:
  `git log --oneline v3.81.2..v3.82.0`.
- **A2.** **La pregunta central del arco.** El commit del tag **no tiene ninguna run
  de CI** (§1.1-9, §1.4). **Dictamina:** ¿puede declararse «publicada» una Release
  cuyo commit **nunca fue certificado por el CI de la rama**? ¿Basta la run del
  hijo, que ejercita su árbol **combinado con otra release**? ¿Y basta
  **declararlo**, o esto debería haber llevado un tag/commit que sí disparara CI?
  Compara con cómo lo hizo `v3.81.2` —que **selló su run en las notas** (`ea65561`)
  precisamente para que este problema no ocurriera—.
- **A3.** ¿`3f686a0` es **ancestro de `main`** y **padre inmediato** de `e05b3dd`?
  `git merge-base --is-ancestor`, `git log -1 --format='%H' e05b3dd^`. ¿Cambia algo
  que el hijo tenga su propia run?
- **A4.** Este arco **añade** `agentes/auditoria-total-externa-v3812.md`, y ese
  documento audita el **parche de privacidad**, no este arco. ¿Es un descuido del
  arco o una consecuencia de que la cola documental del tag anterior cayera aquí?
  **Dictamina** si el efecto neto es que **este** arco se quedó sin encargo.
- **A5.** Contrasta **cada cifra** de §1.3 (96 / +9378−3537, 29 ficheros de backend,
  34 de frontend, 9 del lanzador, 16 añadidos y 4 borrados) con el árbol. Y el
  recuento que las notas dan en `Checklist`/`Verificación`. **Un arco grande es donde
  una cifra equivocada pasa desapercibida.**

### B. El contrato, la identidad y la puerta

- **B1.** `POST /api/session` debe responder **401 genérico** cuando el email no
  existe **o** la contraseña no es —**sin enumerar quién tiene cuenta**— y **403
  `ACCOUNT_NOT_ACTIVATED`** cuando la cuenta existe y aún no tiene contraseña.
  **Estas dos respuestas dicen cosas distintas y hay que ver si juntas revelan la
  existencia de una cuenta.** ¿El 403 es un oráculo de enumeración? **Dictamina** si
  el mensaje de ayuda («tu invitación está en el correo») es una ayuda o una fuga.
- **B2.** ¿Queda **algún** camino por el que se entre **sin contraseña**? Busca
  `password_hash`, `''`, `without_password` y cualquier cortocircuito. El acceso sin
  contraseña debía **desaparecer**: `without_password` deja de ser vulnerabilidad y
  pasa a ser **contador**. Si queda un cortocircuito, es **P0**.
- **B3.** `GET /api/users` — ¿deja de **enumerar** sin sesión, y con sesión **qué**
  devuelve? ¿Aparece el **email de otras cuentas**? El arco declara que el correo es
  PII nueva; busca el filtro que lo recorta (`_without_foreign_email`).
- **B4.** `auth_epoch`: se declara que **sube al activar** y **al restablecer**, y que
  eso **tumba las demás sesiones**. ¿Se cumple en los dos caminos? ¿Y también al
  **cambiar la contraseña** desde dentro? Si un camino no sube la época, cambiar la
  contraseña **no expulsa** a quien ya estaba dentro.
- **B5.** Los tokens de activación y de restablecimiento viven en **columnas de
  `users`**, **hasheados**, con caducidad, y son **de un solo uso**. Verifica que
  **no se canjean entre sí** (el de activación no abre un restablecimiento y al
  revés) y que **emitir uno nuevo anula el anterior**. Las notas declaran que **no
  hay historial** de emisiones: ¿eso impide responder «¿cuántos enlaces se
  mandaron?»?
- **B6.** `POST /api/account/forgot-password` responde **200 siempre**. ¿Es **de
  verdad** siempre —incluido email inexistente, cuenta sin activar y cuenta
  deshabilitada—? El cupo declarado es **5/min por IP y por proceso**, así que **un
  reinicio lo vacía**: **dictamina** si eso es aceptable en un producto **local** o
  si es una defensa que se cae con `Ctrl+C`.
- **B7.** La frontera que decide quién alcanza la API **no es la lista de rutas, es la
  red** (loopback por defecto, LAN opt-in). ¿Es cierto en el código? Si alguien
  expone el puerto, ¿qué queda del «P0 de identidad cerrado»?
- **B8.** `POST /api/profile-requests` es una **escritura sin sesión** (§1.1-6). ¿Tiene
  cupo? ¿Puede inundarse la cola del webmaster? ¿Se valida el email
  (`422 EMAIL_FORMAT`) y se rechaza el duplicado (`409 EMAIL_TAKEN`) **sin** revelar
  si el correo ya tenía cuenta?

### C. La migración y los datos heredados

- **C1.** ¿La migración es **aditiva e idempotente**, y una BD de `v3.81.2` se abre
  **intacta**? Ejecútala **dos veces** mentalmente (o de verdad, sobre copia): el
  segundo arranque no debe re-aplicar nada. `PRAGMA table_info` es la herramienta.
- **C2.** Las **ocho** columnas exactas (§1.1-2). ¿Alguna es `NOT NULL` **sin**
  `DEFAULT`? ¿Alguna debería haber sido `UNIQUE` y no lo es? En particular: el índice
  único de email es **parcial** (`WHERE email <> ''`, `COLLATE NOCASE`). ¿Por qué
  **parcial** —y qué pasaría si dos cuentas heredadas recibieran el mismo correo?
- **C3.** La migración heredada **está preparada y probada, pero NO aplicada**
  (`migrate_legacy_accounts.py` **simula por defecto**, `--apply` escribe con copia de
  seguridad previa). Verifica esa seguridad por defecto **en el código**, no en las
  notas: **¿puede escribir sin `--apply`?** Si puede, es **P0**.
- **C4.** El *plus-addressing* (`vel+ja@`, `vel+paz@`) es una **dependencia del
  proveedor**. **Dictamina** si eso es una limitación declarada o una bomba de
  relojería para quien use un proveedor que no lo soporte.
- **C5.** El E2E declara que **comprueba el sha256 de la BD original al final**. ¿Es
  cierto en el guion? ¿Y trabaja siempre **sobre copia**, sin tocar el fichero de uso?
- **C6.** **Las dos cuentas reales** de este equipo siguen **pendientes de activación**
  (`J.A`, `Paz`, sin email ni contraseña). **Dictamina** si eso deja `G0` abierto
  **por código o por tarea** —y si la respuesta está escrita donde debe estar—.

### D. La superficie sin sesión y su candado

- **D1.** Enumera **todas** las rutas que responden sin sesión y compáralas con la
  lista de `backend/tests/test_public_surface.py`. ¿Coinciden **exactamente**? Una
  ruta nueva sin sesión que **no** esté declarada es **P0**.
- **D2.** El candado se **amplía** en este arco. ¿**Muerde** de verdad —comprueba que
  falla si abres una ruta— o es una lista que se lee y se aprueba? Un candado que
  nunca se ha visto fallar no es un candado: es un comentario.
- **D3.** De las **cuatro escrituras sin sesión** declaradas (`profile-requests`,
  `activate`, `forgot-password`, `reset-password`) más `POST /api/session` y los
  `verify`: ¿**falta alguna** en la lista? ¿Sobra alguna?
- **D4.** `POST /api/users` se **retira**. ¿Queda **algún** cliente que lo llame
  —frontend, lanzador, tests, documentación—? Una llamada a una ruta retirada es un
  fallo silencioso esperando a ocurrir. `git grep -n 'api/users'` y separa «lo que
  debe seguir» de «lo que quedó».
- **D5.** ¿La **despublicación** de `GET /api/users` rompe algún consumidor legítimo?
  El lanzador **sí** necesita listar cuentas: ¿por qué camino lo hace ahora, y está
  **autenticado**?

### E. El lanzador (donde el webmaster opera)

- **E1.** La cola de solicitudes debe mostrar **email** y **avatar** de cada alta.
  ¿Está? ¿Y qué pasa con las solicitudes **antiguas**, sin esos campos?
- **E2.** **«📨 Reenviar invitación»** emite un token **nuevo** y **anula el
  anterior**. Verifícalo. Y **dictamina** el caso peor: si el reenvío se pulsa **dos
  veces**, ¿el segundo enlace invalida el primero **que ya salió por correo**?
- **E3.** El estado de una cuenta sin contraseña deja de pintarse como alarma
  («⚠️ Sin contraseña») y pasa a **«⏳ Sin activar»**. ¿Es solo un cambio de etiqueta
  o cambia también lo que el lanzador **permite hacer** con esa cuenta? Si el cambio
  es solo cosmético, **dilo**.
- **E4.** El lanzador mueve **+1335/−154 en 9 ficheros** y el de `v3.83.0` lo declara
  **producto** («es donde el **webmaster opera**», P1 si se toca). **Aquí sí se toca.**
  ¿Está **auditado** en algún sitio, o es el bloque más grande del arco y el menos
  mirado? Revisa que aprobar una solicitud **no** pueda crear una cuenta con
  `email` vacío **ni** saltarse la emisión de token.
- **E5.** ¿El lanzador maneja el caso **sin SMTP** —que es el de este equipo— diciendo
  la verdad («el enlace se entrega a mano») en vez de prometer un correo que no ha
  salido?

### F. Deriva documental, la cola post-tag y la señal del CI

- **F1.** El arco **cambia la definición de `G0`**. Busca frases **sin fecha** que
  sigan definiendo el gate por el criterio **viejo** (`without_password == 0`).
  **Pista verificada:** `docs/audit/KIT-VALIDACION-GATES.md` **línea 294** (tabla de
  sesiones, **sin fecha**) dice «se confirma que la BD de uso llega a
  `without_password = 0`», mientras que la **hoja del gate** (§C, paso 3) dice que el
  contador es ahora una **lista de tareas**. **Distínguelo** de la línea 17, que está
  en un bloque **fechado (2026-09-23)** y por tanto es **correcta para su fecha**.
  **Dictamina** si la línea 294 es deriva (**hallazgo**) o historicidad.
- **F2.** `CHANGELOG.md §3.82.0`, `PLAN.md` y `docs/RELEVO.md`: ¿**cierran** lo que
  prometían, o queda alguna promesa («se publicará como…») en el aire ya cumplida (o
  no)? Y `docs/audit/PARKED.md §V3.82.0`: ¿declara la deuda **con etiqueta de tipo** y
  **sin** presentarla como cerrada?
- **F3.** **La retirada de `frontend/src/utils/session.ts` y `localDevice.ts`** (§1.3):
  ¿está **declarada** en algún sitio, o son dos ficheros de producto que
  **desaparecen en silencio**? El comportamiento sí se cuenta; los ficheros, no.
- **F4.** `release-notes-v3.82.0.md §5` «Honestidad» hace **siete** afirmaciones
  autoexculpatorias. **Contradice una** con el árbol y tendrás el hallazgo. Candidatas
  verificables: «(iv) los tokens viven en columnas de `users`… **sin historial**»,
  «(v) el cupo es **por IP y por proceso**» y «(vii) **no se reescriben** las notas
  históricas».
- **F5.** **La señal del CI en los PRs de Dependabot.** **Confirmado en este árbol**
  (no heredado): hay runs de `pull_request` con **`conclusion = failure`** —
  `35995393581` (`deps(frontend): bump react and @types/react`) y `35995418666`
  (`deps(frontend): bump vite from 6.4.3 to 8.3.0`)—. Y el arco **anterior** a esta
  release tocó precisamente el arnés de Playwright (§6-D3 del punto de entrada de
  `v3.83.0`). **Dictamina** si (a) es un problema de **este** arco, (b) es un
  **defecto del arnés** que se arrastra, o (c) son **dos** cosas que la casa ha
  juntado. Y si **el commit del tag sin run** (§1.1-9) y los PRs rojos **comparten
  causa raíz** o no.

---

## 3. Matriz de cierre (la rellena el auditor)

| ID | Área | Dictamen (`pass`/`fail`/`no verificado`) | Evidencia (comando o fichero) | Severidad si `fail` |
|---|---|---|---|---|
| A1 | Rango de 4 commits (1 release) | | `git log --oneline v3.81.2..v3.82.0` | — |
| A2 | La Release sin run en su commit | | `gh api .../check-runs` (total_count) | P1 |
| A3 | Ancestro de `main` / padre de `v3.83.0` | | `git merge-base --is-ancestor`, `e05b3dd^` | — |
| A4 | `v3812` cubre el arco anterior, no este | | `agentes/auditoria-total-externa-v3812.md` | P3 |
| A5 | Cifras de §1.3 vs el árbol | | `git diff --shortstat` + `--name-status` | P2 |
| B1 | 401 genérico / 403 como oráculo | | `backend/routers/session.py` | P1 |
| B2 | Ningún acceso sin contraseña | | `repositories/users.py`, `password_hash` | P0 |
| B3 | `GET /api/users` no enumera / PII del email | | `backend/routers/users.py` | P0 |
| B4 | `auth_epoch` sube en los 3 caminos | | `repositories/users.py` + router | P1 |
| B5 | Tokens hasheados, un uso, sin canje cruzado | | `services/credentials.py`, `mailer` | P0 |
| B6 | `forgot-password` 200 siempre / cupo volátil | | router de cuenta | P2 |
| B7 | La frontera real es la red | | `docs/audit/RA-RUNTIME-OFFLINE.md`, `net_interfaces` | P2 |
| B8 | Solicitud: validación, cupo y 409 | | `backend/routers/users.py` + candado | P2 |
| C1 | Migración aditiva e idempotente | | `repositories/db.py` (`ALTER TABLE`) | P0 |
| C2 | 8 columnas exactas / índice parcial | | `repositories/db.py` + `PRAGMA` | P1 |
| C3 | `migrate_legacy_accounts.py` seguro por defecto | | `backend/scripts/migrate_legacy_accounts.py` | P0 |
| C4 | *Plus-addressing* como dependencia | | `release-notes-v3.82.0.md §5` | P3 |
| C5 | E2E sobre copia y con sha256 | | `backend/scripts/e2e_accounts_v382.py` | P2 |
| C6 | G0 abierto por tarea, no por código | | `KIT-VALIDACION-GATES.md §G0` | P2 |
| D1 | Superficie sin sesión enumerada exactamente | | `backend/tests/test_public_surface.py` | P0 |
| D2 | El candado muerde | | `test_public_surface.py` (probarlo en rojo) | P1 |
| D3 | Las 4 escrituras + session + verify | | `test_public_surface.py` | P1 |
| D4 | Nadie llama a `POST /api/users` (retirado) | | `git grep -n 'api/users'` | P2 |
| D5 | Consumidores legítimos de `GET /api/users` | | `launcher/`, `frontend/src` | P1 |
| E1 | La cola muestra email y avatar | | `launcher/ui.py`, `launcher/launcher.py` | P2 |
| E2 | Reenviar invitación anula el token anterior | | `launcher/launcher.py` + router admin | P1 |
| E3 | «⏳ Sin activar»: etiqueta o permiso | | `launcher/ui.py` | P3 |
| E4 | Lanzador +1335/−154 auditado | | `launcher/` completo | P1 |
| E5 | Sin SMTP dice la verdad | | `launcher/ui.py` + `services/mailer.py` | P3 |
| F1 | Deriva de `G0` en texto sin fecha | | `KIT-VALIDACION-GATES.md:294` | P2 |
| F2 | Promesas cerradas / PARKED etiquetado | | `CHANGELOG.md`, `PLAN.md`, `PARKED.md §V3.82.0` | P3 |
| F3 | Retirada de `session.ts`/`localDevice.ts` declarada | | `release-notes-v3.82.0.md` + §1.3 | P3 |
| F4 | Las siete de «Honestidad» | | `release-notes-v3.82.0.md §5` | P0–P3 |
| F5 | CI rojo en PRs de Dependabot | | `gh api .../actions/runs` (`failure`) | P2 |

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se recrea ningún tag, no se fuerza ningún push, no se
   reescribe historia. Si el auditor necesita una corrección, va **después** del tag,
   en un commit documental, y se declara.
2. **Nada se da por bueno por lo que diga un documento de la casa**, y eso incluye
   **estas notas**: cada cifra de este prompt se ha verificado por comando **antes**
   de entregarlo, y el auditor debe **volver a verificarla**.
3. **El ancla es el tag, no la página de Release.** `releases/latest` hoy dice
   `v3.83.0`: no es un defecto, es que la serie avanzó.
4. **Los invariantes se comprueban antes de puntuar**, y si alguno no se cumple, eso
   **es** el hallazgo: no se reinterpreta el invariante para que encaje. **Aquí uno
   ya falla** (§1.1-9) y **está declarado a propósito** para que no se descubra como
   sorpresa: decidir **qué severidad** tiene **es** la auditoría.
5. **Severidades:** `P0` = rompe una promesa de seguridad, privacidad o **de datos del
   alumno**; `P1` = engaña al operador o al alumno sobre el estado real; `P2` = deuda
   declarada o fragilidad de instrumento; `P3` = cosmético o de rastro.
6. **Una promesa de UI vale lo que vale su camino de error.** Pero **este arco no es
   de UI**: es de **contrato, datos y puerta**. Aquí un hallazgo vale lo que valga su
   **camino de fallo** —qué pasa cuando el token caduca, cuando el correo no sale,
   cuando la migración se corta a medias—.
7. **Un arco sin punto de entrada es un arco sin auditoría.** Si al terminar, el
   lector no puede decir **quién entró y cómo**, el informe no ha hecho su trabajo.

---

## 5. Honestidad esperada del informe

El informe (`AV`) debe declarar explícitamente, aunque nadie lo pregunte:

- Que **este arco estuvo sin punto de entrada** hasta este documento, y que lo
  detectaron **otros dos** documentos (el de `v3.81.2` y el de `v3.83.0`) **al
  declararlo como deuda**, no una revisión propia.
- Que **el commit de la release `v3.82.0` no tiene ninguna run de CI** que lo
  certifique (§1.1-9, §1.4): lo que hay es la run de **su hijo**. Si el auditor
  concluye que eso basta, **que lo diga y por qué**; si no, que lo diga con la
  severidad.
- Que **el arco cambia el contrato de la API y migra la BD**, y que por tanto **no es
  comparable** con los arcos de UI que lo rodean: es el que **más riesgo introduce**.
- Que **`G0` sigue `pending`**, pero **ya no por un agujero abierto**: entrar sin
  contraseña se cierra **por construcción**. Lo que queda pendiente es **una tarea
  humana** (que las dos cuentas heredadas reciban su invitación), no un defecto.
- Que **la migración heredada está preparada y probada, pero NO aplicada**, porque
  asignar los correos reales es **acción del gerente**.
- Que **lo que este arco declara abierto sigue abierto**: sin 2FA, sin verificación
  obligatoria, sin perfil de cobros, tokens **sin historial** y cupo **por proceso**.
- Que **la señal de CI en pull requests está roja de forma sistemática** por
  `Playwright E2E (visual)` en los PRs de Dependabot, y que **no** se ha cerrado.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

- **D1. El commit de la release no tiene run.** Verificado por comando
  (`check-runs: 0`, `statuses: []`) y con la comparativa de su hijo (`14`). La
  explicación **más probable** —no confirmada— es que el commit se hizo alcanzable por
  el **push del tag** (que el CI **ignora**) antes de viajar en la rama. **Se declara
  aquí para que no sorprenda**; la severidad la pone el auditor.
- **D2. `KIT-VALIDACION-GATES.md` se contradice con sigo mismo sobre `G0`.** La
  **hoja del gate** (§C, paso 3) recoge la semántica nueva («ninguna cuenta pendiente
  sin invitación entregada»), pero la **tabla de sesiones** (línea 294, **sin fecha**)
  sigue diciendo «se confirma que la BD de uso llega a `without_password = 0`». Una de
  las dos frases es historia; la otra es **deriva**. **Decide tú cuál.**
- **D3. Dos ficheros de producto desaparecen sin que las notas los nombren.**
  `frontend/src/utils/session.ts` (y su test) y `frontend/src/utils/localDevice.ts`
  se **borran** en este arco. El **comportamiento** sí se cuenta en las notas; los
  **ficheros**, no. ¿Es una omisión inocente o esconde una puerta que tardó en
  cerrarse?
- **D4. El arco «contiene» la cola documental del anterior.** Tres de sus cuatro
  commits son `docs(...)` de `v3.81.2`. En un rango limpio de un solo commit como
  `v3.82.0..v3.83.0` eso **no** pasa. **Dictamina** si esto es sano (la cola se
  congela por invariante, no por SHA) o si ensucia los recuentos del arco.
- **D5. El E2E sustituye al anterior en vez de convivir.** `e2e_accounts_v381.py`
  **se retira** (−943 líneas) y `e2e_accounts_v382.py` lo sustituye (+1198). El
  argumento de las notas es que mantener el viejo obligaba a arrastrar una API que ya
  no existe. **Contrástalo**: ¿se pierde **cobertura** de algún caso del viejo?
- **D6. La superficie sin sesión se amplía y el candado se amplía con ella.** Cuatro
  escrituras nuevas sin sesión es **mucho** para una release que se presenta como «de
  identidad». **Dictamina** si cada una **tiene que** estar sin sesión (y por qué) o
  si alguna podría exigir credencial.
- **D7. El lanzador es el bloque más grande y el peor cubierto.** `+1335/−154` en
  9 ficheros, y su punto de entrada es el **único** que no existía. Si el webmaster
  **opera** desde ahí, es donde un fallo **se convierte en un dato**. El auditor
  debería tratarlo como producto, no como herramienta.

---

## 7. Alcance

**Dentro:** el delta `v3.81.2..v3.82.0` completo — el **commit de release**, los
**16 añadidos** y **4 borrados**, la versión, la documentación viva, los generados,
las **runs** y la **Release**—, con el foco en **quién puede entrar y cómo** (contrato,
identidad, migración) y en **lo que queda abierto sin sesión** (la superficie y su
candado).

**Fuera (y se hereda):** el cierre de G0 y la privacidad del historial con
`agentes/auditoria-total-externa-v3812.md`; el cuerpo de la gestión de usuarios con
`agentes/auditoria-total-externa-v381.md`; el diccionario y la sesión de estudio con
`agentes/auditoria-total-externa-v383.md`. **Este documento no repite sus preguntas.**

**Fuera también, y declarado:** el arco **`v3.82.0..v3.83.0`** ya tiene su punto de
entrada, y este documento **no lo sustituye**.

---

## 8. Nota de prefijos y cierre

- **El prefijo de este punto de entrada es `AV`**, porque **`AU` quedó reservado** por
  el punto de entrada de `v3.83.0` —que lo declara por escrito— y **`AP`–`AT` siguen
  reservados sin informe**. El informe esperado es
  `docs/audit/AV-AUDITORIA-TOTAL-V382.md`.
  **Nota para la casa:** la lista de prefijos del punto de entrada de `v3.83.0` (§8)
  **debe extenderse** con `AV` en cuanto este documento se acepte; si no, quedará una
  nota de prefijos **desactualizada** describiendo el estado del día anterior (que es
  exactamente el tipo de deriva que estas auditorías persiguen).
- **Reservados y sin dictamen** a fecha de este commit: **`AP`** (`v3.75.7`), **`AQ`**
  (`v3.77.1`), **`AR`** (`v3.80.0`), **`AS`** (`v3.81.1`), **`AT`** (`v3.81.2`),
  **`AU`** (`v3.83.0`) y **`AV`** (este).
- **Cadena de puntos de entrada:** `v321` → `v322` → `v323` → `v346` → `v373` →
  `v375` → `v3751` → `v3757` → `v3771` → `v380` → `v381` → `v3812` → **`v382`**
  (este) → `v383`.
- **Este documento se entrega en un commit documental POSTERIOR a los tags `v3.82.0` y
  `v3.83.0`**, con el ancla en `v3.82.0` y **sin mover producto**: el invariante 9 de
  §1.1 —que el árbol del tag no se ha tocado— es la prueba, y **nuestro trabajo previo
  ya lo comprobó** (`git diff --stat v3.83.0..main -- backend frontend/src launcher
  scripts` sale **vacío**).
- **Lo que este documento NO es:** no es la auditoría, es el encargo. No adelanta
  veredictos —**salvo el hecho ya verificado de que el commit de la release no tiene
  run**, que se declara porque callarlo sería exactamente lo contrario de lo que este
  arco necesita—, no maquilla los invariantes para que se cumplan y no promete que
  todo vaya a salir verde.
