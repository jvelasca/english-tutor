# Release notes — English Tutor v3.81.0

**Fecha:** 2026-09-23 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.80.0 → 3.81.0`

**Publica DOS LOTES BAJO UNA SOLA ETIQUETA:** (1) la **estabilización pre-freeze**
que se iba a publicar como `v3.80.1` —los hallazgos de la auditoría externa de
V3.80.0, más la cola de perfiles invisible del lanzador— y (2) **la Fase 3 del P0
de identidad**: la **gestión de usuarios** como una app profesional (cuenta con
nombre + email + contraseña, alta y baja autoservicio, verificación de email
opcional y consola de gestión con la última palabra).

**CON migración de BD aditiva** (columnas de cuenta en `users` + tabla
`user_events`), **endpoints nuevos** (`/api/account/*`, `PUT /api/session/password`,
`PUT /api/session/email`, el bloque `/api/admin/users/*`) y **endpoints retirados**
(`PUT /api/session/pin`). **SIN bump** de `GENERATOR_VERSION` /
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) /
`LISTENING_BANK_VERSION`. No se añade ni se retira un gate: **G1–G7 siguen
`pending`**; lo único que cambia **fuera** del producto es a qué árbol apuntan:
la base de certificación se re-ancla de `v3.75.8` a **`v3.81.0`** (por tag, sin
fijar SHA a mano) porque V3.78.0/V3.79.0/V3.80.0/V3.81.0 añadieron producto y la
campaña tenía **0 `record`** — nada que invalidar.

---

## 0. Por qué dos lotes en una sola etiqueta

El lote 1 ya estaba implementado y verificado como `v3.80.1` cuando el gerente
decidió repensar la parte de perfiles **el mismo día**: convertirlos en cuentas de
usuario de verdad. Publicar `v3.80.1` y `v3.81.0` con horas de diferencia habría
dejado **dos etiquetas para un mismo árbol de trabajo** —una de ellas sin valor
para quien audita— y un `CHANGELOG` que cuenta dos veces los mismos arreglos. Se
publica **una** etiqueta con **dos lotes declarados**, y las notas del lote 1 se
conservan en `release-notes-v3.80.1.md` como su registro detallado (no como una
release publicada).

**Consecuencia que hay que decir:** el lote 1 no traía migración ni endpoints;
el lote 2 sí. Quien audite el rango `v3.80.0 → v3.81.0` está auditando **las dos
cosas de golpe**.

---

## 1. Lote 1 · La estabilización pre-freeze (lo que iba a ser `v3.80.1`)

Ninguno de estos arreglos **añade capacidad**: todos hacen que lo que ya existía
**no mienta**. El detalle apartado por apartado está en
`release-notes-v3.80.1.md`; aquí queda el mapa y la razón de cada uno.

- **(A) P1 · La carrera entre generar la cara B y editarla a mano.** `hydrate()`
  lanzaba una promesa que puede tardar hasta 120 s (modelo local) y
  `saveOwnBack()` escribía después, así que una respuesta **tardía** pisaba la
  traducción recién guardada y la pantalla contradecía la fuente de verdad del
  alumno. Se cierra con **token por tarjeta** (`hydrationEpoch`) + **espejo
  síncrono** (`ownBacksRef`): `hydrate()` descarta su resultado si el token cambió
  o si ya hay versión propia, y guardar o borrar sube el token e invalida lo que
  esté en vuelo. Candado con **promesa diferida**.
- **(B) P2 · El badge «Tu versión» sobre una traducción borrada:** borrar
  **desmarca**, olvida la hidratación y **restaura la cara que sirvió el backend**
  (o reintenta la caché).
- **(C) P2 · La `X` del diccionario** limpiaba el campo pero no el resultado (un
  campo vacío con la tarjeta anterior debajo es un estado que miente): ahora
  limpia todo lo que depende de la consulta y vuelven los ejemplos.
- **(D) P2 · Los selectores tipo pestaña son pestañas ARIA reales**
  (`tablist`/`tab`/`tabpanel`, `aria-selected`, `aria-controls`) con el hook
  `frontend/src/hooks/useTabList.ts`: **roving tabindex** y
  `ArrowLeft`/`ArrowRight`/`Home`/`End`.
- **(E) P2 · El `lang` de las tarjetas manuales:** solo se declara cuando el
  idioma **se conoce** (léxico EN→ES); en las manuales se omite, porque declararlo
  era mentir.
- **(F) Sonda visual permanente:** `tests/visual/dictionarySmoke.spec.ts` y
  `tests/visual/flashcardsSmoke.spec.ts`, en los **tres breakpoints**
  (390/768/1280) y sin `skip`. Sus mocks de `/api/**` van anclados al **origen**
  (`/^https?:\/\/[^/]+\/api\//`): un glob como `**/api/settings*` casa también con
  el módulo de la app `/src/api/settings.ts` y, al servirle JSON, **la app no
  arranca**.
- **(G) La cola de perfiles que el lanzador no podía ver** (hallazgo de uso real).
  Sin PIN de administración, el lanzador no consultaba al backend y
  `_apply_profiles` no miraba `result.ok`, así que un 401, un 403 o un servidor
  caído se pintaban como **«Sin solicitudes pendientes»**. Ahora el contador se lee
  **siempre** de la BD en solo-lectura (`launcher/status.py::read_pending_requests`:
  `0` = vacía, `None` = no se pudo leer), la vista es una función pura
  (`ui.pending_view`) y guardar o retirar el PIN **reinicia el servidor**.

---

## 2. Lote 2 · Gestión de usuarios (Fase 3 del P0 de identidad)

El gerente decidió que el producto **sí tiene cuentas** y que la credencial es
**por cuenta**, no por dispositivo: cada persona se crea la suya, entra con su
contraseña y puede darse de baja; la última palabra la tiene el programa de
gestión. El **PIN de perfil de V3.76 desaparece**: era una mitigación *opt-in* y
esto es identidad.

### (A) La cuenta y su credencial

`users` gana `email`, `email_verified_at`, `email_verify_token_hash`,
`email_verify_sent_at`, `password_hash`, `must_change_password`, `auth_epoch` y
`unenrolled_at`, más la tabla **`user_events`** (historial de la cuenta) con su
índice por sujeto y fecha.

`backend/services/credentials.py` sustituye a `services/pins.py` (**borrado**,
con su `test_pin.py`; en el frontend se van `utils/pin.ts` y `pin.test.ts`):

- **PBKDF2-HMAC-SHA256**, 200 000 iteraciones y sal de 16 bytes **por cuenta**,
  guardado como `pbkdf2-sha256$<iter>$<sal>$<hash>` —las iteraciones van dentro
  del valor, así que **subirlas más adelante no invalida lo guardado**— y
  comparación con `hmac.compare_digest` (comparar con `==` filtra por
  temporización cuántos bytes acertó el atacante). Stdlib puro: cero dependencias
  nuevas.
- **Política de forma:** 8–128 caracteres, sin espacios en los extremos (casi
  siempre es un pegote de copiar y pegar), no una de las obvias de la lista corta
  del servidor, y no un solo carácter repetido. La lista de contraseñas obvias
  vive **solo** en el servidor: repetirla en la UI sería duplicar una lista que se
  desincroniza.
- **Freno de intentos por cuenta:** los primeros 5 fallos no frenan (dedos torpes
  no son un ataque); a partir de ahí el retardo **dobla** (1 s, 2 s, 4 s…) con
  techo de 300 s, y una contraseña correcta limpia el contador. Es la pieza que de
  verdad sostiene la política: sin freno, una contraseña de 8 es fuerza bruta
  barata por muy buen KDF que haya.
- **Contraseña temporal** que el webmaster entrega a mano: tres bloques de cuatro
  caracteres de un alfabeto sin `0/O/1/l/I` (las que se confunden al dictarlas).
- **Token de verificación de email:** 32 bytes de entropía en claro (viaja en el
  enlace), guardado **hasheado** (SHA-256) y con **caducidad de una hora**. Sin sal
  a propósito: no es una contraseña elegida por una persona, así que no hay
  diccionario que lo ataque; lo que evita el hash es que leer la fila de la BD
  baste para confirmar un email ajeno.

### (B) Alta, baja y email

- **El registro es autoservicio** en el propio equipo: `POST /api/users` (nombre +
  email + contraseña), acotado por `config.is_admin_loopback_host` —por la **red**
  se sigue **solicitando**, el reparto de V3.77— y por el cupo nuevo de
  `security._PATH_LIMITS` (`/api/users`: 60/min, porque hashea antes de decir que
  sí). Los dos conflictos se distinguen a propósito: `409 USER_NAME_TAKEN` y
  `409 EMAIL_TAKEN`, y los formatos son `400 EMAIL_FORMAT` / `400 PASSWORD_FORMAT`.
- **El email es una señal, no un muro.** `POST /api/account/verify` (sin sesión:
  el enlace puede abrirse en otro navegador) consume el token de un solo uso
  —`400 VERIFY_TOKEN_INVALID` / `400 VERIFY_TOKEN_EXPIRED`— y
  `POST /api/account/resend-verification` (bajo sesión, porque emite tokens)
  responde con la **verdad**: `SMTP_NOT_CONFIGURED`, `EMAIL_MISSING`,
  `ALREADY_VERIFIED`.
- **La baja autoservicio no borra nada.** `POST /api/account/unenroll` **exige la
  contraseña** aunque ya haya sesión (sin ella, pasar por delante de un equipo con
  la sesión abierta bastaría para dar de baja a quien esté dentro), marca la cuenta
  como retirada, sube su época de autenticación —así **tumba las sesiones vivas al
  instante**— y **retira la cookie**. La evidencia se queda intacta: el borrado
  definitivo es la **purga**, que es del webmaster, con copia previa y confirmación
  por nombre. Mezclar «darme de baja» con «borrar mis datos» es cómo las apps
  borran el historial de un alumno porque alguien pulsó el botón equivocado.
- **El correo saliente es la segunda excepción de red del producto**, declarada en
  `backend/scripts/audit_dossier.py::RUNTIME_TOUCHPOINTS` (`kind: "internet"`) y
  **fail-closed** (`backend/services/mailer.py`): sin SMTP configurado **no se abre
  ninguna conexión** (se comprueba antes de tocar `smtplib`), STARTTLS en los
  puertos normales y TLS implícito en 465, timeout de 10 s —el envío ocurre dentro
  de una petición HTTP y un SMTP que no responde no puede dejar colgada el alta—,
  correo en **texto plano** y el enlace apuntando al **fragmento** de la ruta del
  frontend (`/#/cuenta/verificar?token=…`), que no se queda en los logs del
  servidor ni en una cabecera `Referer`. Un fallo de envío **se registra y no
  rompe** la acción que lo pedía.
- **Los secretos, otra vez separados:** la contraseña del SMTP vive en
  `backend/data/mail.secret` (fuera de git) y **no viaja en los backups**
  (`_NON_PORTABLE_TOP_NAMES` la suma a `certs`, `backups` y `session.secret`),
  porque en un ZIP sin cifrar es una credencial de correo en claro. **El hash de la
  contraseña de la cuenta sí viaja** (es estado de la cuenta, dentro de la BD) y eso
  está declarado como deuda, no escondido.

### (C) El cuelgue de «Elige tu perfil»

Lo reportado en uso real no era del flujo de cuentas sino de la **sesión
guardada**: una cookie que apuntaba a una cuenta ya purgada (404) o desactivada
(403) hacía que `getSession()` **lanzara**, el arranque en `Promise.all` se quedaba
a medias y la puerta se pintaba sin lista y sin salida. Se cierra en tres capas:

1. `frontend/src/api/session.ts`: **404 y 403 se tratan como «sin sesión»** y la
   cookie inservible se limpia.
2. `frontend/src/hooks/useChat.ts`: el arranque pasa a `Promise.allSettled`, así
   que una sonda caída **no puede** vaciar la pantalla.
3. `frontend/src/components/ProfileGate.tsx`: distingue **«no hay cuentas»**,
   **«no se pudo cargar»** (con **reintentar**) y la **lista normal** — tres
   estados que antes se veían igual. Y ofrece **«Crear cuenta»** solo cuando la
   pestaña se abrió **en el propio equipo** (`frontend/src/utils/localDevice.ts`,
   espejo de `is_admin_loopback_host`): ofrecer un formulario que el servidor va a
   rechazar con 403 sería peor que no ofrecerlo.

### (D) La consola de «Usuarios» del lanzador

El panel de perfiles pasa a ser una **consola de gestión con la última palabra**:

- **Cola de solicitudes** de alta y de baja (aprobar/rechazar con motivo).
- **Alta y edición** de cuentas (nombre, email, avatar).
- **Credenciales**: asignar y restablecer, entregando una contraseña **temporal**
  (`must_change_password`) cuando toca — es la recuperación de contraseña del
  producto, y se dice así.
- **Verificación de email a mano** (modo híbrido sin SMTP).
- **Activar / desactivar** y **baja forzada con motivo**.
- **Historial** (`user_events`), que **sobrevive a la purga** (por eso la columna se
  llama `subject_id` y guarda también el nombre: el purgado borra dinámicamente
  toda tabla con `user_id`, y el registro del purgado es justo el que debe quedar).
- **Purga**, solo de cuentas **dadas de baja o desactivadas**, con **copia previa**
  y confirmación por nombre.
- **SMTP**: configurar y probar, con una frase que **concilia** lo guardado con lo
  que ve el backend en marcha (el backend resuelve el SMTP de su entorno al
  arrancar; el lanzador lo dice en vez de fingir que ya está aplicado).

La vista es **pura** (`launcher/ui.py`: `accounts_tasks`, `user_row`,
`credential_label`, `email_label`, `event_row`, `smtp_state_label`,
`smtp_reconcile_label`, `purge_block_reason`, `duplicate_user_ids`) y por eso se
prueba sin pantalla. Los ajustes **no secretos** del correo y el candado de
administración se guardan en `launcher/config.json` (`config_store.py`).

### (E) La superficie sin sesión, otra vez declarada

Pasa a tener **cuatro escrituras** —`POST /api/users` (registro), `POST
/api/account/verify` (token), `POST /api/session` (abrir sesión) y `POST
/api/profile-requests` (la solicitud inerte de V3.77)—; `resend-verification` y
`unenroll` **sí** exigen sesión. El candado que fija la lista es
`backend/tests/test_public_surface.py`, para que no crezca sin querer.

`GET /api/users` sigue enumerando **nombres** sin sesión (la puerta es un selector
y los necesita antes de que exista sesión), pero **no correos**: el email de las
demás cuentas se recorta en el borde HTTP (`routers/users.py::_without_foreign_email`).
Sin ese recorte, cualquier equipo de la red podría cosechar los correos de la casa
sin escribir una contraseña.

---

## 3. El contrato, antes y después

| Pieza | Antes (`v3.80.0`) | Ahora (`v3.81.0`) |
|---|---|---|
| Abrir sesión | `POST /api/session {user_id}` + PIN **opcional** | exige `password` si la cuenta tiene credencial: `401 PASSWORD_REQUIRED` / `PASSWORD_INVALID`, `429 PASSWORD_THROTTLED` (+`Retry-After`) |
| Alta | solo del webmaster (por LAN se solicitaba) | **registro autoservicio** en loopback (`POST /api/users`) + solicitud por red |
| Credencial | `services/pins.py` (PIN de 4-6 dígitos) | `services/credentials.py` (PBKDF2-SHA256, política, freno por cuenta, tokens de email) |
| Identidad | nombre | nombre + **email** (PII nueva), verificación opcional por token |
| Baja | no existía | `POST /api/account/unenroll`: autoservicio, exige la contraseña, **no borra** |
| Revocación | freno en memoria | **época de autenticación** (`users.auth_epoch`, comparada en `dependencies.current_user`): cambiar la contraseña o forzar la baja tumban las sesiones vivas **ya** |
| Contraseña temporal | — | `must_change_password` + `403 PASSWORD_CHANGE_REQUIRED` en cada petición hasta cambiarla |
| Gestión | panel de perfiles | consola de **Usuarios**: cola, alta, credenciales, verificación manual, activar/desactivar, baja forzada con motivo, historial, purga y SMTP |
| Superficie sin sesión | 1 escritura (`profile-requests`) | **4 declaradas**, con candado en `test_public_surface.py` |
| Red saliente | ninguna | **correo** (segunda excepción declarada, fail-closed) |

---

## 4. Migración: aditiva e idempotente

- **Ocho columnas nuevas** en `users` y **una tabla nueva** (`user_events`) con su
  índice. Una BD de `v3.80.0` **se abre intacta**: el `ALTER TABLE` es el de
  siempre (se comprueba `user_cols` antes de añadir) y las filas existentes quedan
  con `email = ''` y `password_hash = ''`, que es la lectura honesta de «esta
  cuenta es anterior a las cuentas».
- **`pin_hash` se conserva aunque el producto ya no la lea.** Borrar una columna en
  SQLite es una reconstrucción de la tabla, y una copia antigua restaurada sobre
  esta versión tiene que seguir abriendo. No se pierde nada y no se gana riesgo.
- **`status` sigue `active` para todos**: esta migración no desactiva a nadie.

---

## 5. Re-anclaje de la base de certificación: `v3.75.8` → `v3.81.0`

El árbol que se certifica pasa a ser el de **`v3.81.0`**, identificado **por tag** y
**sin fijar un SHA a mano** (regla V3.73.5). No invalida nada: la campaña de gates
tiene **0 `record`** y los 7 siguen `pending`. Queda declarado en
`docs/audit/KIT-VALIDACION-GATES.md` y en `docs/audit/G7-MATRIZ-LECTURA.md`.

**Aviso que no tenían las re-congelaciones anteriores:** este salto **no es solo
aditivo**. `PUT /api/session/pin` **desaparece** y `POST /api/session` **cambia**
(exige contraseña si la cuenta la tiene), así que cualquier instrumento de campo
que abriera sesión con un `user_id` a secas debe conocer el contrato nuevo.

---

## 6. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff check` (backend) | limpio |
| `ruff check` (launcher) | limpio |
| `pytest` (backend) | **3085/3085** |
| `pytest` (launcher) | **244/244** |
| `tsc --noEmit` | limpio |
| `vitest run` | **1028/1028** (109 ficheros) |
| `npm run build` | correcto (`package.json` en `3.81.0`) |
| i18n `--strict` | **1733** cadenas, 0 huérfanas / 0 usadas sin definir / 0 duplicadas |
| `contrast_audit.mjs` | 480 pares (+6 guardas), **0 bloqueantes** |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.81.0`) |
| `validation_gate.py auto` | **10/10** |
| Playwright `dictionarySmoke` + `flashcardsSmoke` | **6/6** en los 3 breakpoints |
| `backend/scripts/e2e_accounts_v381.py` (E2E sobre una **copia** de la BD real) | **62/62 pasos, 0 fallos** |

**La prueba end-to-end, y por qué se puede reproducir.** Las suites anteriores
prueban piezas; lo que ninguna prueba es el **flujo completo sobre la BD de
verdad** con el backend en marcha. Eso es lo que hace
`backend/scripts/e2e_accounts_v381.py`: copia `backend/data/tutor.db` a un
directorio temporal, redirige `config.DATA_DIR` ahí (antes de importar la app),
levanta `uvicorn` en `127.0.0.1` (puerto configurable, por defecto 8137) y ejerce
el contrato entero por HTTP real.
**62 pasos, 0 fallos**, entre ellos:

- El **freno**: seis `401` seguidos y el séptimo intento `429` con `Retry-After`,
  y con el freno activo **tampoco entra la contraseña correcta**.
- La **revocación**: cambiar la contraseña deja la cookie anterior en `401
  SESSION_STALE` **en la petición siguiente**, y la contraseña vieja ya no abre.
- El **modo híbrido**: sin SMTP, `resend-verification` responde `sent: false` con
  `SMTP_NOT_CONFIGURED` (no finge un envío), y el webmaster sella la verificación
  a mano; sellarla dos veces es **idempotente** (200, no un error), y sellar una
  cuenta **sin correo** sí es 409.
- La **baja autoservicio**: exige la contraseña, mata la sesión viva, la cuenta
  **sigue en la BD** y desaparece del selector público; el webmaster puede
  reactivarla y vuelve a entrar.
- La **purga**: se rechaza con la cuenta activa y con el nombre equivocado; con el
  nombre exacto purga **con copia previa**, y el historial **sobrevive** contando
  además el propio `purged`.
- La **deuda declarada, evidenciada**: una cuenta heredada entra con su
  `user_id` y sin contraseña, y sigue viendo su léxico.
- **Y lo que no puede cambiar:** ninguna tabla de evidencia (`vocabulary`,
  `learning_events`, `conversations`, `messages`) mueve su recuento, el censo de
  cuentas vuelve al de partida, y **la BD original queda con el mismo sha256** —
  la prueba no toca el fichero del que copia.

El guion se documenta como herramienta declarada en
`backend/tests/test_runtime_audit_v371.py::NON_PRODUCT_NETWORK_FILES`: usa
primitivas de red (contra su propio backend local), así que el candado del
manifiesto de runtime obliga a clasificarlo, y por eso está ahí con su motivo.

**Candados nuevos, y se comprobó que muerden** revirtiendo el código a propósito:

- `frontend/src/components/AccountDialog.test.tsx` (21) y
  `frontend/src/utils/credentials.test.ts` (8): con la validación de forma
  puenteada o sin el Portal, fallan.
- `backend/tests/test_credentials.py` (KDF, política, freno por cuenta, token),
  `backend/tests/test_mailer_v381.py` (**fail-closed**: sin SMTP no se llama a
  `smtplib` **ni una vez**; STARTTLS/TLS y autenticación) y
  `backend/tests/test_accounts_v381.py` (flujo completo de la cuenta).
- `backend/tests/test_public_surface.py` (la lista de rutas sin sesión) y
  `backend/tests/test_sessions.py` (contraseña exigida, revocación por época).
- `launcher/tests/test_admin_client.py` y `test_ui.py` (la consola y sus vistas
  puras), reescritos al cambiar el cliente `admin.py`.

**Imprevisto que merece quedar escrito:** el primer candado del `mailer` **no
mordía**. La sabotaje hacía que `smtplib` lanzara, y el `except Exception` del
propio envío se lo comía: un test que lanza dentro del `try` no puede probar «no
se llama a esta función». Se reescribió el doble para que **registre la llamada
antes** de fallar, y entonces sí falla cuando debe. Es la misma lección de
V3.80.1: un candado sin sabotaje es una opinión.

---

## 7. Lo declarado y NO cerrado

1. **Las cuentas heredadas sin credencial siguen entrando sin contraseña.**
   `password_hash == ''` abre como siempre, para no dejar a nadie fuera de sus
   datos. **El P0 sigue abierto para ellas**: la consola las lista como tarea
   pendiente y el objetivo es llevarlas a cero. Es la deuda central de esta release.
2. **No hay recuperación de contraseña por correo:** la restablece el webmaster y
   la entrega como **temporal**. Un flujo con token exigiría decidir su caducidad y
   su propio freno: es funcionalidad nueva, no estabilización.
3. **No hay segundo factor** (TOTP, passkeys) ni verificación **obligatoria** para
   usar la app.
4. **`GET /api/users` sigue enumerando nombres** en modo LAN (decisión de diseño del
   selector, declarada desde V3.75). Los correos ya no.
5. **El hash de la contraseña sí viaja en el backup**; `session.secret` y
   `mail.secret` no. Quien reciba un backup puede atacar la contraseña **fuera de
   línea**, sin el freno del servidor.
6. **El freno vive en memoria del proceso**: un reinicio lo vacía (mismo límite que
   el PIN de V3.76).
7. **La verificación por correo depende de que el webmaster configure SMTP.** Sin
   él todo funciona igual y la verificación es manual — y la UI lo dice con esas
   palabras.
8. **El transporte de correo no se ha probado contra un servidor SMTP real.** Los
   candados cubren el modo fail-closed, la negociación STARTTLS/TLS implícito y la
   autenticación con y sin contraseña, pero una prueba contra un proveedor de
   verdad (uno que exija OAuth en vez de contraseña de aplicación) queda
   **pendiente**.
9. **La consola sigue detrás del doble candado** (PIN de administración +
   loopback): sin PIN se **cuenta** la cola, pero no se resuelve, edita, fuerza una
   baja ni se purga.
10. **Todo lo declarado abierto en V3.80.0/V3.80.1 sigue abierto**: el timeout de
    hidratación de 120 s, el idioma por mazo, el pack listado en dos sitios y la
    duplicación de plantillas/cloze/import, entre otros.

---

## 8. Qué NO trae esta release

- **Nada de currículum, corpus, evaluaciones ni banco de listening:** ningún bump
  de versión de motor. Los **9 dossiers de G7 no se re-derivan** por estos cambios
  (los instrumentos no leen mazos, tarjetas, traducción propia, cuentas ni correo).
- **Ningún gate nuevo** y ninguno cerrado: G1–G7 siguen `pending` y esta release
  solo mueve el ancla sobre la que se correrán.
- **Ni una dependencia nueva:** PBKDF2 y `smtplib` son stdlib.
