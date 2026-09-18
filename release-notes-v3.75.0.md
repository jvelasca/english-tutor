# Release notes — English Tutor v3.75.0

**Fecha:** 2026-09-18 · **Tipo:** release de **PRODUCTO (minor)** que cambia el
**contrato de la API** · **Versión de app:** `3.74.0 → 3.75.0`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** Ninguna
capacidad pedagógica nueva. Esta release entrega la **Fase 2 del P0 de identidad**
—la identidad deja de viajar en la URL y pasa a una cookie firmada por el
servidor— y cierra los **dos P3** que quedaban abiertos de la verificación de
seguridad de V3.73 (`VG-N5`, `VG-N6`).

> **Cambia el contrato para clientes que hablan con la API a mano:** los endpoints
> que antes leían `?user_id=<id>` ya **no** lo miran; exigen la cookie de sesión
> (`POST /api/session` la abre). La app se adapta sola. Ver §7.

---

## Qué es esta release

Cierra la **segunda mitad** del P0 de identidad que quedó declarada como no
resuelta en `release-notes-v3.73.7.md`:

1. la **superficie** (dejar de exponerse por defecto) la cerró **V3.74.0**, y
2. la **identidad** (que el cliente no sea quien decide quién eres) la cierra esta
   release.

El plan por fases, con las mediciones, los acoplamientos descubiertos y las
alternativas descartadas, está en `docs/audit/PLAN-P0-IDENTIDAD.md` (§6 diseño,
§14 estado de la Fase 2).

**Fuera de alcance (declarado).** Esto **no es autenticación** y la **Fase 3**
sigue sin decidir. `POST /api/session` acepta cualquier `user_id` **existente** sin
credencial, porque el producto es «sin cuentas, sin contraseñas» por diseño
(`docs/PREMISAS.md`). Lo que cambia es **quién es la autoridad** sobre la
identidad, no quién puede pedirla. §6 lo desarrolla sin adornos.

---

## 1. El problema: la identidad la elegía el cliente

Hasta V3.74.0 el perfil activo viajaba en **cada** URL:

```text
antes   GET /api/profile?user_id=<el-que-yo-quiera>
        Cookie et_user_id: la escribía JavaScript (no HttpOnly)
        -> el servidor aceptaba el perfil que le pidieras, si existía
```

Con la frontera de red ya en loopback por defecto (V3.74.0), quien alcanzaba la API
seguía pudiendo **elegir a quién leer y escribir** con un parámetro. Y la cookie que
recordaba la elección no era una credencial en ningún sentido: la escribía el propio
JavaScript de la página (`frontend/src/utils/cookie.ts`), así que se reescribía
desde la consola del navegador.

---

## 2. La solución: la identidad la firma el servidor

```text
POST /api/session {user_id}   ->  404 si el perfil no existe
                                   Set-Cookie: et_session=<token firmado>
                                   HttpOnly · SameSite=Lax · Secure en HTTPS

GET    /api/settings          ->  200 con el perfil de la cookie
GET    /api/settings          ->  401 SESSION_REQUIRED (sin cookie válida)
GET    /api/settings?user_id=B->  200 con los datos de la SESIÓN, no de B
```

- **`backend/services/sessions.py`** (nuevo): token
  `base64url(payload).base64url(hmac_sha256(secreto, payload))` con
  `payload = {iat, uid}`, **stdlib** a propósito (`itsdangerous` haría lo mismo con
  más superficie por treinta líneas) y **comparación en tiempo constante**
  (`hmac.compare_digest`): comparar firmas con `==` filtra por temporización.
- **`backend/routers/session.py`** (nuevo): `POST` / `GET` / `DELETE /api/session`.
- **`backend/dependencies.py`**: `current_user` verifica la cookie; sin ella,
  manipulada o caducada ⇒ **401 `SESSION_REQUIRED`**.
- **Autorización, no solo identidad:** `PATCH /api/users/{id}` y
  `PUT /api/settings` exigen sesión **y** que el id coincida con el de la sesión
  (**403** si no). Antes, con sesión de A, se podía editar el perfil de B.
- **El secreto de firma** vive en `backend/data/session.secret` (permisos de
  usuario, creado al primer uso) y **no viaja en los backups**: un ZIP sin cifrar con
  la clave dentro permite **forjar sesiones**. Restaurar **no** borra el secreto del
  equipo receptor, así que las sesiones abiertas siguen valiendo.
- **`et_user_id` se retira** (`frontend/src/utils/cookie.ts` y su test, borrados):
  la identidad ya no la escribe el cliente.

---

## 3. El frontend: preguntar en vez de creer

El cliente **no puede leer** la cookie (es `HttpOnly`, y ese es el punto), así que
al arrancar **pregunta**:

- `GET /api/session` ⇒ el perfil activo, o `null` si no hay sesión (401 tratado
  como estado normal, no como error).
- Elegir perfil en el selector **abre sesión** (`openSession`) y el estado local se
  fija con el perfil que devuelve **el servidor**, no con lo que pidió el cliente.
- Crear un perfil **también** abre sesión: sin ese paso la app lo pintaría como
  activo y **cada** petición respondería 401 — el fallo más fácil de dejar pasar en
  esta fase, y por eso la decisión es una función pura con test propio
  (`utils/session.ts::planSession`): adoptar la sesión existente, abrirla, o no
  hacer nada.
- Los **17 módulos** de `frontend/src/api/` dejan de añadir `?user_id=…` a las URLs.
  El parámetro se conserva con prefijo `_userId` para no tocar a ~85 llamantes
  (`noUnusedParameters` está activo en `tsconfig.json`; retirarlo del todo es la
  *Fase 2b* opcional, declarada y no hecha).

---

## 4. La suite de tests no se reescribió: se adaptó (y qué se pierde)

Las **109 suites** existentes llamaban a la API con `params={"user_id": uid}`. En
vez de tocar 109 ficheros (revisión enorme, mismo poder de prueba), un **adaptador
en `backend/tests/conftest.py`** traduce ese parámetro a una **sesión firmada de
verdad** y **delega en el camino real** de `current_user`: la firma, la caducidad,
el 401 y el 404 se ejecutan igual.

**Lo que se pierde, declarado:** esas 109 suites ya no prueban «la identidad viene
de la cookie». Lo cubren los tests nuevos, que hablan con la app **en crudo**
(marcador `identidad_cruda`, registrado en `backend/pyproject.toml`) porque el
adaptador haría inexpresable el caso «sin sesión + `?user_id=`». El test clave manda
**las dos cosas a la vez** —sesión de A y `?user_id=B`— y exige los datos de **A**.

---

## 5. Los dos P3 que quedaban (`VG-N5` y `VG-N6`)

### 5.1 `VG-N5` — dependencias y cadena de suministro (y lo que destapó)

- **Actions fijadas por SHA de commit** (`checkout@11bd719…`, `setup-python@a26af69…`,
  `setup-node@49933ea…`), con la etiqueta en comentario. `@v4`/`@v5` son referencias
  **móviles**: si la acción cambia, el CI ejecuta otro código sin que nada del
  repositorio cambie. Se añade `permissions: contents: read` (el CI solo lee).
- **Job `deps-audit`, bloqueante:** `pip-audit -r backend/requirements.txt` (árbol de
  **producto**, no el de desarrollo) y `npm audit --omit=dev --audit-level=high`.
- **El escaneo destapó deuda real:** 10 avisos conocidos en **`starlette 0.50.0`**,
  arrastrado por `fastapi==0.128.0`, cuyos parches solo existen en
  `starlette>=1.0.1`. Se sube **`fastapi` a 0.141.1** (→ `starlette 1.6.0`) y la
  suite completa pasa **idéntica** (2875 passed en el árbol intermedio, antes de los
  tests nuevos). Un job de auditoría que se añade y se deja en rojo no es un job: es
  un adorno.
- **Dependabot** (`.github/dependabot.yml`) para `pip` (`/backend`), `npm`
  (`/frontend`) y `github-actions` — el tercero es el que mantiene **frescos** los
  pines por SHA.

### 5.2 `VG-N6` — la superficie sin credencial, declarada y acotada

`/api/system/status`, `/api/network` y `/api/models` respondían **sin credencial** y
la auditoría dejó la decisión abierta: *declararlos aceptados o restringirlos*.
Se **aceptan por escrito** (`docs/ARQUITECTURA.md` §«Superficie sin sesión») porque
exponen **reconocimiento barato** —modelos instalados, IP/hostname de LAN, trabajos
de generación en curso, rechazos por rate limit de 60 s— que **no** permite leer ni
escribir datos de ningún alumno, y porque quien puede alcanzarlas ya está dentro
para lo demás: la frontera real es la **red**.

El candado (`backend/tests/test_public_surface.py`) mira en **las dos direcciones**:
lo declarado sin sesión **debe** seguir respondiendo (si no, se rompe el launcher o
la puerta de perfil, que funcionan antes de que exista ningún perfil) y lo declarado
con sesión **no** puede salir sin ella. Y la declaración es obligatoria: borrar la
sección del documento **hace fallar** el test.

---

## 6. Honestidad

1. **No es autenticación, y la Fase 3 sigue sin decidir.** `POST /api/session`
   acepta cualquier `user_id` existente y `GET/POST /api/users` siguen sin
   credencial: en modo LAN, quien alcance la API puede **abrir sesión para cualquier
   perfil**. Lo que ya no puede es **forjar** una identidad (sin el secreto del
   equipo) ni **elegirla en cada petición**. Cerrar el acceso exige credencial, y
   eso contradice «sin cuentas, sin contraseñas»: es una **decisión de producto**, no
   una fase técnica pendiente.
2. **La identidad sigue siendo «el perfil que pidas», no «quien eres».** El token
   solo prueba que **el servidor** lo emitió, no que quien lo pide tenga derecho al
   perfil.
3. **`FastAPI` 0.141.1 / `starlette` 1.6.0 es un salto de versión mayor de
   Starlette** dentro de una release de seguridad. Se hizo porque dejarlo era
   publicar 10 avisos conocidos; la evidencia es la suite completa en verde
   (2882 passed), no una lectura del changelog de terceros. **Efecto observable
   declarado:** la suite emite **1 aviso** de `StarletteDeprecationWarning` («usar
   `httpx2` con `testclient`»). No rompe nada y no se silencia: se deja a la vista
   porque es lo que el salto trajo consigo.
4. **La `Secure` de la cookie depende del esquema de la petición.** El producto se
   sirve por HTTPS (certificado autofirmado), así que en el uso real va puesta; si
   alguien sirviera la API por HTTP plano, la cookie viajaría sin ese atributo. Es
   el mismo comportamiento que se declaró en V3.73.7.
5. **El candado de `VG-N6` fija una lista, no una demostración.** Dice que lo
   declarado se comporta como se declaró; no dice que la lista esté completa (y no
   puede: la completitud de una superficie no se prueba, se revisa).
6. **Los 7 gates siguen en `pending`.** Esta release no mueve la validación física;
   la identidad sellada en `docs/audit/KIT-VALIDACION-GATES.md` (`3.73.6` →
   `13cc30b`) es el registro del **pre-vuelo** y **no se reescribe**.

---

## 7. Verificación

Medido en el **árbol de trabajo** (con `frontend/dist` construido y los modelos
instalados), sobre el árbol que contiene esta release:

| Comprobación | Resultado |
|---|---|
| Backend `pytest tests/ -q` | **2882 passed** |
| Frontend `vitest run` | **721 passed** (87 ficheros) |
| Launcher `pytest tests/ -q` | **142 passed** |
| `ruff check .` / `npx tsc --noEmit` | limpios |
| i18n `check_i18n_coverage.py --strict` | 0 huérfanas / 0 duplicadas / 0 vacías |
| `validation_gate.py auto` | **10/10** |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.75.0`) |
| `check_beta_v3.py` · `content_validation.py` · `transfer_validation` | OK |
| `npm audit --omit=dev --audit-level=high` | 0 vulnerabilidades |
| `pip-audit -r requirements.txt` | 0 vulnerabilidades conocidas |
| CI (GitHub Actions) | **12 jobs**, incluido el nuevo `deps-audit` |

Los recuentos suben **exactamente** por los tests nuevos: backend 2840 → 2882
(**+42**), frontend 719 → 721 (**+2** netos: +7 nuevos, −5 del `cookie.test.ts`
retirado) y launcher 139 → 142 (**+3**).

**Mordida de los candados.** Cinco sabotajes controlados (aplicados y revertidos por
script, cada uno contra su test): reintroducir una **etiqueta móvil** de Action,
volver **informativo** el job de auditoría, **borrar** la declaración de superficie
sin sesión, quitar **`HttpOnly`** de la cookie de sesión, y hacer que el adaptador de
`conftest` traduzca **también** las peticiones crudas. Los cinco hicieron **fallar**
su test.

---

## 8. Notas de actualización

- **Nada que hacer en la app.** Al abrirla tras actualizar: si hay **un** perfil, la
  sesión se abre sola; si hay varios, aparece el selector (como antes) y elegir abre
  sesión. La cookie vieja `et_user_id` se ignora y queda huérfana en el navegador.
- **Clientes de la API a mano:** hay que llamar a `POST /api/session` y **conservar
  la cookie**. Los endpoints que antes aceptaban `?user_id=` responderán **401
  `SESSION_REQUIRED`**.
- **El panel del launcher** ya no muestra «usuario recordado: \<id\>»: muestra
  **si hay sesión** y enmascara el valor de la cookie (es un token firmado; verlo en
  pantalla sería poder usarlo).
- **Dependencias:** `fastapi` 0.128.0 → **0.141.1** (`starlette` 1.6.0). Si tienes un
  entorno virtual propio, reinstala con `pip install -r backend/requirements.txt`.
