# Release notes — English Tutor v3.82.0

**Fecha:** 2026-09-24 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.81.2 → 3.82.0`

**Cierra el P0 de identidad para las cuentas activas**, porque por primera vez
**entrar sin contraseña deja de existir**. El alta deja de ser un nombre en una
lista y pasa a ser un ciclo profesional: **solicitud** con nombre, email y avatar →
**autorización del webmaster** → **invitación por correo** → la persona **elige su
propia contraseña** → entra **solo con email + contraseña** → y si la olvida, hay
**recuperación por correo**. Nadie puede entrar como otra persona.

**CON migración de BD aditiva** (cuatro columnas en `profile_requests` y cuatro en
`users`) y **CON un cambio incompatible de contrato** (`POST /api/session` pasa de
`{user_id}` a `{email, password}`), coordinado en el mismo lanzamiento entre
backend, frontend, lanzador y sus tests. `GENERATOR_VERSION`,
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`),
`LISTENING_BANK_VERSION` y las evaluaciones **no se tocan**.

**No se añade ni se retira un gate** —siguen los **ocho** `pending`—, pero **la
definición de `G0 · identidad-cuentas` cambia de sentido**: deja de vigilar un
agujero abierto y pasa a vigilar una **cola de tareas**, porque el agujero se cierra
**por construcción**.

---

## 0. El diagnóstico: por qué el alta no era profesional

El gerente pidió revisar si el procedimiento de alta era «100 % profesional» con
vistas a un uso público. No lo era, y los cinco motivos son concretos:

1. **El formulario de solicitud no capturaba email ni avatar.** `ProfileRequestCreate`
   era `display_name` + `note`, así que la solicitud no traía **con qué** autorizar
   ni **con qué** crear la cuenta.
2. **Aprobar no mandaba nada.** `approve()` creaba la cuenta con `email=''` y
   `password_hash=''` y **no enviaba correo**. Autorizar y dar credencial eran dos
   pasos manuales del webmaster, y el segundo no dejaba rastro de que se hubiera
   hecho.
3. **No existía recuperación de contraseña.** Solo el webmaster restablecía una
   **temporal**, que es una solución de administrador, no un flujo del usuario.
4. **El enlace de verificación del correo estaba roto desde V3.81.**
   `mailer.verification_link()` apuntaba a `/#/cuenta/verificar?token=…`, una ruta
   que **no existía** en `frontend/src/router/routeMap.ts`: pulsarla caía en Inicio
   y **no confirmaba nada**, en silencio.
5. **Se entraba eligiendo un nombre de la lista, y una cuenta sin contraseña abría
   sesión.** `GET /api/users` enumeraba las cuentas **sin sesión** y
   `password_hash == ''` entraba sin pedir nada: cualquiera podía entrar como `J.A`
   o como `Paz`. Es el hueco que `G0` vigilaba.

---

## 1. El flujo nuevo, de punta a punta

### (A) La solicitud captura email y avatar

`ProfileRequestCreate` pasa a `name` + `email` + `avatar_color` + `avatar_emoji` +
`avatar_image` + `note`, reutilizando `is_valid_email`/`normalize_email` de
`services/credentials.py`. El correo se valida **antes** de encolar (un correo sin
forma se rechaza con `422 EMAIL_FORMAT` y **sin culpar al nombre**, que es el error
que la persona sí puede arreglar) y no se admite uno que ya use una cuenta activa
(`409 EMAIL_TAKEN`). El formulario de la puerta gana el campo de email y el selector
de avatar, y la imagen se reduce a **data URL** con el `resizeImageToDataUrl` que ya
existía para las cuentas: ni un formato ni una dependencia nuevos.

### (B) Aprobar crea la cuenta, emite el token y manda la invitación

- `users` gana `activation_token_hash` y `activation_sent_at`.
- `credentials.py` gana `new_activation_token()` y
  `ACTIVATION_TOKEN_TTL_SECONDS` (**7 días**: una invitación se lee cuando se puede,
  y un enlace que caduca en una hora se convierte en una llamada al webmaster).
- El mailer gana `KIND_ACTIVATION`, con asunto y cuerpo propios, y el enlace apunta
  a `/#/cuenta/activar?token=…` — al **fragmento** del frontend, que no se queda en
  los logs del servidor ni en una cabecera `Referer`.
- `approve()` crea la cuenta **con el email y el avatar solicitados**, emite el token
  y envía el correo. **Fail-closed y sin romper:** sin SMTP configurado no se abre
  ninguna conexión y el fallo **se registra**, no tumba la aprobación — porque el
  enlace sigue siendo válido y se puede entregar a mano.
- `POST /api/admin/profile-requests/{id}/approve` devuelve `email_sent` y
  **`activation_link` en claro**, una única vez, y se añade
  `POST /api/admin/users/{id}/resend-activation` para reemitir la invitación (el
  token anterior deja de valer).

### (C) La activación: la persona pone su contraseña

`POST /api/account/activate {token, password}` (**sin sesión**, porque el enlace se
abre en el móvil o en otro navegador) valida el token **hasheado**, su caducidad y su
**único uso** (`400 ACTIVATION_TOKEN_INVALID` / `ACTIVATION_TOKEN_EXPIRED`), aplica
la política (`400 PASSWORD_FORMAT`), guarda el hash, **marca el email como
verificado** —pulsar el enlace prueba la posesión del correo—, limpia el token,
**sube `auth_epoch`** y registra el evento en el historial.

En el frontend nace `/#/cuenta/activar` (`AccountActivate` + el compartido
`NewPasswordForm`), con contraseña y repetir, y las tres páginas de cuenta
(`activar`, `restablecer`, `verificar`) comparten armazón (`AccountPage`): son una
**parada**, no un destino, así que se pintan fuera del armazón de la app y sin
navegación, con un pie que dice que en este equipo puede **no haber correo
configurado** y que el enlace se entrega a mano.

**Y se arregla el enlace roto de V3.81:** `/#/cuenta/verificar` existe, llama a
`verifyEmail` y **dice lo que ha pasado** (no promete lo que no ocurrió).

### (D) La entrada: solo email + contraseña

- `SessionCreate` pasa a `email` + `password`.
- **No se enumera:** si el email no existe o la contraseña no es, la respuesta es la
  misma (**401 `INVALID_CREDENTIALS`**). La puerta ya no pide la lista de nombres.
- **Se retira el acceso sin contraseña:** una cuenta con `password_hash == ''`
  responde **403 `ACCOUNT_NOT_ACTIVATED`** («mira el enlace de tu correo»). Esto es
  lo que **cierra G0 por construcción**.
- `GET /api/users` **deja de ser público** y pasa a exigir sesión: el catálogo de «a
  quién intentar entrar» deja de publicarse.
- **Se retira el alta instantánea** `POST /api/users` del registro público (el alta
  directa del webmaster sigue en `POST /api/admin/users`).
- En la puerta, «Solicitar acceso» y «Olvidé mi contraseña» son dos caminos reales,
  y el selector de nombres desaparece con su lista de avatares.

### (E) La recuperación por correo

- `users` gana `password_reset_token_hash` y `password_reset_sent_at`.
- `POST /api/account/forgot-password {email}` responde **200 siempre** —no revela si
  el correo tiene cuenta, que es lo que convierte un «olvidé mi contraseña» en un
  buscador de correos dados de alta— y, si la cuenta existe **y está activa**, emite
  el token y manda el correo. Freno de **5/min por IP** (`security._PATH_LIMITS`),
  porque con SMTP configurado cada llamada **emite un token y envía un mensaje a un
  tercero**.
- `POST /api/account/reset-password {token, password}`: token de **un solo uso** con
  caducidad de **1 hora**, guarda el hash, limpia el token, **sube `auth_epoch`**
  —así las demás sesiones mueren al instante— y registra evento.
- Mailer `KIND_RESET` + enlace `/#/cuenta/restablecer?token=…` + ruta y página
  (`AccountReset`).

### (F) La migración heredada, preparada y probada

`backend/scripts/migrate_legacy_accounts.py` lleva una cuenta con
`password_hash == ''` al flujo nuevo: le asigna email, emite la invitación y la deja
«pendiente de activación». Es **idempotente**, **simula por defecto** (`--apply`
escribe) y hace **copia previa**.

- `J.A` → `josealberto.vel+ja@gmail.com`
- `Paz` → `josealberto.vel+paz@gmail.com`

El *plus-addressing* es lo que permite que **dos cuentas únicas** (dos identidades,
dos historiales aislados) lleguen a la **misma bandeja**. El lanzador añade
**«📨 Reenviar invitación»** para entregar los enlaces sin SMTP, y el estado de una
cuenta sin contraseña deja de pintarse como alarma («⚠️ Sin contraseña») para
pintarse como lo que es: **«⏳ Sin activar»**.

**El `1234` no se usa.** No cumple la política (mínimo 8) y no es defendible en
público; cada persona elige su contraseña, que es justo el punto del flujo.

---

## 2. El contrato, antes y después

| Pieza | Antes (`v3.81.2`) | Ahora (`v3.82.0`) |
|---|---|---|
| Abrir sesión | `POST /api/session {user_id}` (+ contraseña si la tenía) | `{email, password}`; **401 `INVALID_CREDENTIALS`** genérico si el email no existe o la contraseña no es; **403 `ACCOUNT_NOT_ACTIVATED`** si nace sin contraseña |
| Identidad | nombre + email opcional | **el email es la identidad** (único y con forma validada) |
| Alta | `POST /api/users` autoservicio (loopback) + solicitud por red | **solicitud** con email y avatar → autorización → **invitación** |
| Autorizar | creaba la cuenta sin email, sin contraseña y **sin avisar** | crea la cuenta **con los datos solicitados**, emite token (7 días) y **manda la invitación** (o devuelve el enlace) |
| Primer acceso | el webmaster entregaba una **temporal** | la persona **elige su contraseña** en `/#/cuenta/activar` |
| Contraseña olvidada | el webmaster asignaba otra temporal | `forgot-password` + `reset-password` con token de un uso (1 h) |
| Verificación de email | enlace **roto** (`/#/cuenta/verificar` no existía) | la ruta existe; la activación además **verifica el email** |
| Cuenta sin contraseña | **entraba sin contraseña** (el agujero de G0) | **403 `ACCOUNT_NOT_ACTIVATED`** |
| `GET /api/users` | público (enumeraba nombres) | **exige sesión** |
| `POST /api/users` | registro público | **retirado** (el alta del webmaster sigue en `/api/admin/users`) |
| Superficie sin sesión | 4 escrituras | **6 declaradas y con candado** (`profile-requests`, `activate`, `forgot-password`, `reset-password`, `session` y `verify`) |
| `G0 · identidad-cuentas` | «no puede estar en `pass` con `without_password > 0`» | el agujero se cierra **por construcción**; el gate vigila que **ninguna cuenta pendiente se quede sin invitación entregada** |

---

## 3. Migración: aditiva e idempotente

- **Cuatro columnas nuevas en `profile_requests`** (`email`, `avatar_color`,
  `avatar_emoji`, `avatar_image`) y **cuatro en `users`** (`activation_token_hash`,
  `activation_sent_at`, `password_reset_token_hash`, `password_reset_sent_at`), con
  el `ALTER TABLE` de siempre (se comprueba `PRAGMA table_info` antes de añadir).
- **Una BD de `v3.81.2` se abre intacta.** Las solicitudes anteriores llegan con
  `email = ''` y el webmaster puede completarlas desde la consola; las cuentas
  existentes quedan **pendientes de activación**, que es la lectura honesta de «esta
  cuenta es anterior a la invitación».
- **`pin_hash` sigue en la tabla, sin leerse** (desde V3.81), para que una copia
  antigua restaurada sobre esta versión siga abriendo.
- **Ninguna cuenta se desactiva, ninguna evidencia se toca.** El censo de
  `vocabulary`, `learning_events`, `conversations` y `messages` **no cambia**: lo
  comprueba el E2E.

---

## 4. Lo que cambia de significado (y hay que decir)

`without_password` **deja de ser una vulnerabilidad** y pasa a ser un **contador
operativo** («cuentas pendientes de activación»). El hueco se cierra **por
construcción** —entrar sin contraseña ya no existe, y lo demuestra el E2E con un
`403 ACCOUNT_NOT_ACTIVATED`—, así que lo que `G0` vigila ahora es otra cosa: que
**ninguna cuenta pendiente se quede sin invitación emitida y entregada**. Quien esté
en esa lista tiene que poder activar su cuenta, y de cada una tiene que constar que
su enlace salió o se entregó a mano. Es un cambio de criterio **declarado**, no un
gate que se relaja: el agujero que G0 protegía **ya no existe**, y lo que queda es
una tarea del webmaster visible en la consola.

**Consecuencia operativa, dicha sin adornos:** en esta instalación, `J.A` y `Paz`
**no pueden entrar** hasta que se ejecute la migración (o se les ponga el email desde
la consola y se pulse «Reenviar invitación»). Eso es la deuda de esta release, y está
en `docs/audit/PARKED.md` §`V3.82.0`.

---

## 5. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff check` (backend) | limpio |
| `ruff check` (launcher) | limpio |
| `pytest` (backend) | **3122/3122** |
| `pytest` (launcher) | **269/269** |
| `tsc --noEmit` | limpio |
| `vitest run` | **1028/1028** (109 ficheros) |
| i18n `--strict` | **1762** cadenas, 0 huérfanas / 0 usadas sin definir / 0 duplicadas |
| `contrast_audit.mjs` | 480 pares (+6 guardas), **0 bloqueantes** |
| Playwright `accountPages` (visual) | **6/6** en los 3 breakpoints (2 pruebas × 390/768/1280) |
| `validation_gate.py auto` | **10/10** (8 gates) |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.82.0`) |
| `backend/scripts/e2e_accounts_v382.py` (E2E sobre una **copia** de la BD real) | **83/83 pasos, 0 fallos** |

**La prueba end-to-end, y por qué se puede reproducir.** Las suites anteriores
prueban piezas; lo que ninguna prueba es el **flujo completo sobre la BD de
verdad**. Eso es lo que hace `backend/scripts/e2e_accounts_v382.py`: copia
`backend/data/tutor.db` a un directorio temporal, redirige `config.DATA_DIR` ahí
(antes de importar la app), **levanta un buzón SMTP local**, arranca `uvicorn` en
`127.0.0.1` (puerto configurable, por defecto 8137) y ejerce el contrato entero por
HTTP real. **83 pasos, 0 fallos**, entre ellos:

- La **solicitud** con email y avatar, el correo repetido (`409`) y el correo sin
  forma (`422`, sin culpar al nombre).
- La **invitación** de verdad: el correo **llega al buzón local**, el token se
  **extrae del cuerpo del mensaje** (no del log del servidor) y el enlace abre la
  activación.
- La **activación**: token bueno, token **caducado**, token **ya usado** y contraseña
  que no cumple la política; y, al activar, el email queda **verificado**.
- La **entrada por email**: email inexistente y contraseña mala dan **el mismo 401**
  (sin enumeración), la cuenta sin activar da **403 `ACCOUNT_NOT_ACTIVATED`**, y con
  la contraseña buena entra.
- La **recuperación**: `forgot-password` responde **lo mismo** con un correo que
  existe y con uno que **no** existe (y un email sin forma se rechaza antes de
  mirar nada, con `422`); el token del correo restablece la contraseña,
  **mata la sesión anterior** y **no vale dos veces**; y el cupo de 5/min corta la
  sexta petición.
- La **migración heredada** recorrida con el **guion real**: una cuenta sembrada sin
  email ni credencial pasa a tener invitación, token, activación y contraseña — y
  `--dry-run` **no escribe nada**.
- La **purga** con copia previa, y el historial que **sobrevive** y **no conserva
  ningún correo**.
- **Y lo que no puede cambiar:** ninguna tabla de evidencia mueve su recuento, el
  censo de cuentas vuelve al de partida y **la BD original queda con el mismo
  sha256** — la prueba no toca el fichero del que copia.

El guion se documenta como herramienta declarada en
`backend/tests/test_runtime_audit_v371.py::NON_PRODUCT_NETWORK_FILES`: usa
primitivas de red (contra su propio backend y contra su propio buzón), así que el
candado del manifiesto de runtime obliga a clasificarlo, y por eso está ahí con su
motivo. **Sustituye a `e2e_accounts_v381.py`, que se retira:** mantener el viejo
obligaba a arrastrar una API que ya no existe (sesión por `user_id`, alta pública,
política de contraseña laxa) y un guion que no puede pasar por diseño.

**Candados nuevos, y los que cambiaron de sitio:**

- `backend/tests/test_accounts_v382.py` (**28**): el contrato entero del alta
  profesional —la solicitud con email y avatar, el `EMAIL_TAKEN` y el
  `EMAIL_FORMAT`, la aprobación que crea la cuenta sin contraseña y manda la
  invitación, el modo híbrido sin SMTP (con el servidor de mentira que **apunta**
  el uso para poder afirmar que no se abrió ninguna conexión), la activación
  (token inventado, contraseña débil, caducado, de un solo uso, reemisión que anula
  el anterior), el candado de G0 (`403 ACCOUNT_NOT_ACTIVATED`), la entrada sin
  enumeración y la recuperación (respuesta idéntica, token caducado, un solo uso,
  y la sesión abierta que muere al restablecer). **Se comprobó que muerde**
  revirtiendo a propósito el cierre de G0 (vuelven a entrar sin contraseña y fallan
  este fichero y `test_accounts_v381.py`) y la comprobación de caducidad de la
  invitación (falla el suyo).
- `backend/tests/test_public_surface.py`: la lista de rutas sin sesión, con las seis
  escrituras declaradas.
- `backend/tests/test_sessions.py`: el 401 único sin enumeración, el 403
  `ACCOUNT_NOT_ACTIVATED` y la cuenta heredada **sin email** (que no es ni
  localizable: no hay a dónde mandarle nada).
- `backend/tests/test_accounts_v381.py` y `test_profile_requests_v377.py`: los
  flujos de cuenta y de solicitud reescritos al contrato nuevo, con el caso del email
  sin forma.
- `launcher/tests/test_admin_client.py` y `test_ui.py`: el reenvío de invitación (un
  POST sin cuerpo que **sí** devuelve el enlace) y la tarea «pendiente de activación»
  que **deja de llamarse alarma**.
- `frontend/tests/visual/globalSetup.ts` y `gateHelper.ts`: las pruebas visuales ya
  **no crean un perfil por API** (ese endpoint no existe); la identidad se mockea y el
  handshake es un fichero local.
- `frontend/tests/visual/accountPages.spec.ts` (**nuevo**, 2 pruebas × 3 breakpoints):
  las tres páginas que llegan por enlace de correo y las tres pantallas de la puerta
  —entrar, solicitar acceso y recuperar—, con los cuatro endpoints implicados
  respondidos desde el navegador, así que **no necesita backend** y no depende de la
  BD.

### La sonda visual encontró un defecto que el unitario no podía ver

La página de verificación se quedaba en **«Confirmando…» para siempre** bajo el doble
montaje de `StrictMode`, que es como arranca la app en desarrollo: el primero de los
dos efectos descartaba su respuesta con la clásica bandera de «sigo vivo» y el segundo
**no volvía a preguntar** —el token es de un solo uso—, así que nadie recogía el
resultado. La guarda que parecía prudente era exactamente la causa, y no la veía
ninguna prueba unitaria porque todas montaban una sola vez.

Se arregla aplicando el resultado sin bandera (lo único que hay que proteger es que el
token se canjee **una** vez, y eso lo fija el token guardado en la referencia, no la
vida del efecto) y queda **fijado en las dos capas**: el spec visual y
`AccountPages.test.tsx`, que ahora monta también bajo `StrictMode`. Se comprobó que el
candado **muerde**: devolviendo la bandera a su sitio, el caso nuevo falla.

---

## 6. Lo declarado y NO cerrado

1. **La migración heredada de este equipo está preparada, no ejecutada.** `J.A` y
   `Paz` siguen sin email ni contraseña y, por el punto siguiente, **no pueden
   entrar** hasta que se ejecute el guion o se les asigne el correo desde la consola.
2. **`G0` sigue `pending`, y ahora por tareas y no por agujero.** Es exactamente lo
   que el gate debe vigilar: que nadie declare cerrado el P0 con gente fuera de sus
   datos sin que conste que se le invitó.
3. **No hay segundo factor** (TOTP, passkeys) ni verificación **obligatoria** para
   usar la app.
4. **La entrega del correo depende de que el webmaster configure SMTP.** Sin él, la
   invitación y el restablecimiento **no se pierden** (el enlace se entrega a mano),
   pero deja de ser autoservicio de verdad, y la UI lo dice con esas palabras.
5. **El *plus-addressing* es una dependencia del proveedor.** Gmail y Outlook
   soportan `+`; otro obligaría a correos distintos.
6. **Los tokens viven en columnas de `users`**, hasheados y con caducidad, pero **sin
   historial**: emitir uno nuevo anula el anterior sin dejar rastro de cuántos se
   emitieron.
7. **El cupo de recuperación es por IP y por proceso**: un reinicio lo vacía, y una
   red con una sola salida lo comparte. Es el mismo límite ya declarado del freno de
   contraseña.
8. **No hay aviso al titular** cuando alguien pide un restablecimiento de su
   contraseña: quien tenga acceso al correo puede pedirlo sin que la persona se
   entere hasta que llegue (o no llegue).
9. **El hash de la contraseña sigue viajando en el backup** (es estado de la cuenta,
   dentro de la BD); `session.secret` y `mail.secret` no.
10. **Sin perfil de cobros ni nada económico** (a petición expresa del gerente): la
    estructura es la que necesitaría un uso público —solicitud, autorización, estado
    de la cuenta, recuperación—, pero no hay planes, facturación ni límites por tipo
    de cuenta.
11. **El transporte de correo no se ha probado contra un SMTP real.** El E2E usa un
    buzón local propio; un proveedor de verdad (uno que exija OAuth en vez de
    contraseña de aplicación) queda pendiente de acción humana.
12. **Todo lo declarado abierto en `v3.81.x` sigue abierto** salvo lo que esta
    release cierra de forma explícita: ya no hay entrada sin contraseña, ya no hay
    registro autoservicio, ya no se enumera quién tiene cuenta y sí hay recuperación
    por correo.

---

## 7. Qué NO trae esta release

- **Nada de currículum, corpus, evaluaciones ni banco de listening:** ningún bump de
  versión de motor, y los **9 dossiers de G7 no se re-derivan** por estos cambios
  (los instrumentos no leen cuentas, correos ni avatares).
- **Ningún gate nuevo y ninguno cerrado:** los **8** siguen `pending`; lo que cambia
  es la **definición** de `G0`, que pasa de vigilar un agujero a vigilar una tarea.
- **Ni una dependencia nueva:** PBKDF2, `hashlib`, `smtplib` y `sqlite3` son stdlib.
