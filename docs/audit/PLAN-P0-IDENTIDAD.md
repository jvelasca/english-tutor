# Plan P0 — Identidad y superficie de red (propuesta)

> **Qué es:** plan de implementación del P0 que dejó abierto
> `docs/audit/VERIFICACION-SEGURIDAD-V373.md`. **No es una auditoría**: es el
> diseño concreto que se propone ejecutar, con su coste, su orden y sus criterios
> de aceptación.
>
> **Estado:** **Fase 1 PUBLICADA como `v3.74.0`** y **Fase 2 IMPLEMENTADA en el
> árbol de `v3.75.0`** (§14), junto con los dos P3 que quedaban abiertos
> (`VG-N5` y `VG-N6`). La **Fase 3** (autenticación real) sigue fuera y sigue
> siendo una decisión de producto.
>
> **Punto de partida:** `v3.74.0` · árbol con el lote V3.73.7 (`v3.73.7`) **y** la
> Fase 1 (`v3.74.0`) publicados **por separado**, cada uno medido en su propio
> árbol (3.73.7: 2817 / 717 / 113 · 3.74.0: 2840 / 719 / 139).
>
> **Alcance aprobado:** **Fase 1 + Fase 2.** La Fase 3 (autenticación real) queda
> fuera y requiere decisión de producto.
>
> **Fecha:** 2026-09-18 · **Autor:** agente de la sesión de auditoría.

---

## 1. Alcance

**Entra:**

- Colocar la API en **loopback por defecto** y convertir el modo LAN en **opt-in
  explícito** (Fase 1).
- Sacar la identidad del cliente de la **URL** y pasarla a una **cookie de sesión
  emitida y firmada por el servidor** (Fase 2).
- Cerrar el borde de autorización de los endpoints de perfil: **solo puedes
  editar tu propio perfil** (Fase 2).

**No entra (declarado):**

- **Autenticación real** (contraseña o PIN por perfil, emparejamiento de
  dispositivo): es la Fase 3 y es una **decisión de producto**, no una corrección.
- **Tocar los 138 `Depends(current_user…)` de los 20 routers.** Ver §3: el cuello
  de botella es **uno**.
- **Retirar el parámetro `userId` de los componentes React** (~85 ficheros): la
  Fase 2 lo deja en la firma de la capa `api/` marcado como no usado, para que el
  diff no se propague a la UI. La limpieza es una Fase 2b **opcional**.
- Cualquier cambio pedagógico, de banco o de currículum.

---

## 2. Método

Medición por lectura de fuente y `rg` sobre el árbol `v3.73.7`, no por estimación.

---

## 3. Evidencia: el alcance real

| Superficie | Medición | Comando |
|---|---|---|
| Backend: usos de la dependencia | **138** en **20** routers | `rg -c "Depends\(current_user" backend` |
| Backend: definición | **1** función | `backend/dependencies.py:30-41` |
| Frontend: módulos de API con `user_id` | **77** referencias en **17** módulos | `rg -c "user_id" frontend/src/api` |
| Frontend: componentes que pasan `userId` | ~**85** ficheros `.tsx` | `rg -c "userId" frontend/src --glob "*.tsx"` |
| Tests backend con `user_id` | **109** ficheros | `rg -l "user_id" backend/tests` |

**La conclusión que hace viable el plan:** los 138 usos de los routers **no hay
que tocarlos**. Todos atraviesan una sola función:

```python
# backend/dependencies.py
   30|async def current_user(user_id: str = Query(...)) -> dict:
   31|    """Resuelve y valida el perfil activo. 404 si no existe."""
   32|    user = await user_service.get_user(user_id)
```

Cambiar la **fuente** de la identidad es un cambio de un fichero; los 138 call
sites siguen recibiendo el diccionario del perfil sin enterarse.

---

## 4. Hallazgo estructural: por qué «sesión» no es «autenticación»

**Los perfiles no tienen credencial.** No hay contraseña, ni PIN, ni token: el
producto es «sin cuentas, sin contraseñas» **por diseño** (`README.md`), y
`GET/POST/PATCH/DELETE /api/users` no exigen autenticación ninguna
(`backend/routers/users.py:12-41`).

De ahí una consecuencia que reordena el plan:

> Si `POST /api/session` acepta un `user_id` y devuelve una cookie válida,
> **cualquiera que alcance la API pide sesión para el perfil de otro y la
> obtiene.** La identidad dejaría de viajar en la URL, pero seguiría
> **eligiéndola el cliente** — un cambio de forma con apariencia de arreglo.

Por tanto:

- La amenaza que describe el dossier («otro equipo de la LAN cambia
  `?user_id=` y ve, renombra o borra los datos del alumno») **no se cierra
  autenticando: se cierra quitando el alcance.** Eso es la Fase 1.
- La Fase 2 tiene un valor real pero **acotado y distinto**: la identidad deja de
  viajar en URLs (no se filtra en enlaces, historiales ni logs, y no es forjable
  desde fuera del servidor), y el servidor pasa a ser la única autoridad sobre
  quién eres. **Sigue sin autenticar.** Hacer la Fase 2 sin la Fase 1 sería
  exactamente el «endurecer el síntoma» que el proyecto rechaza.

---

## 5. Fase 1 — Loopback por defecto, LAN opt-in

### 5.1 El estado actual

El producto se enlaza **siempre** a `0.0.0.0` y el launcher **anuncia** la LAN en
su panel de acceso:

```python
# launcher/core.py
   84|def backend_command() -> list[str]:
   85|    """Comando para arrancar el backend con el venv del proyecto (uvicorn).
   86|
   87|    Se enlaza a ``0.0.0.0`` para que otros equipos de la LAN puedan acceder y se
   88|    sirve por **HTTPS autofirmado** ...
    93|    return [
    97|        "--host",
    98|        "0.0.0.0",
```

No hay modo: `0.0.0.0` es el único comportamiento, y `ALLOWED_ORIGIN_REGEX`
(`backend/config.py:37-55`) acepta cualquier IP privada **siempre**.

### 5.2 Diseño propuesto

1. **`ENGLISH_TUTOR_LAN`** (variable de entorno, `1`/`0`) es la **única** fuente de
   verdad del modo. Ausente ⇒ loopback. El launcher la exporta al backend en
   `backend_env()` (que ya existe y ya añade `ENGLISH_TUTOR_REQUIRE_UI`), de modo
   que **backend y launcher no pueden discrepar**. *(V3.75.3: la variable sigue
   siendo la única fuente del **modo** —nada la relee por otra vía—, pero el
   launcher ahora la **declara al arrancar** desde `launcher/config.json` en vez de
   partir siempre de «ausente»; ver §5.9.)*
2. `backend_command()` pasa a `--host 127.0.0.1` por defecto y `0.0.0.0` **solo**
   con la variable activa. El certificado TLS **se mantiene siempre**: en
   `localhost` también hace falta *secure context* para el micrófono (es la razón
   por la que el producto es HTTPS desde V3.72).
3. `ALLOWED_ORIGIN_REGEX` (las IPs privadas) **solo se activa en modo LAN**. Sin
   la variable, la lista blanca es la de `ALLOWED_ORIGINS` (localhost). El backend
   lee la variable **fail-closed**: lo que no está declarado, no se permite.
4. `launcher/allow-firewall.ps1` deja de ser un paso «recomendado» y pasa a ser
   **parte del modo LAN** (el script ya abre solo el 8000; se documenta como
   requisito del modo, no como instalación).
5. El panel de acceso del launcher (`launcher/launcher.py:506-535`) muestra la fila
   LAN **con el estado del modo**: activa, o «desactivado — pulsa para habilitar».
   Un enlace a la API que no responde porque el bind es loopback y el usuario no
   sabe por qué es peor que el riesgo que se cierra.

### 5.3 Cambios por fichero

| Fichero | Cambio |
|---|---|
| `launcher/core.py` | `LAN_ENV` + `lan_mode()`; `backend_command()` con host según modo (`backend_host()`); `backend_env()` canoniza y propaga el modo; `lan_url()` avisa de que solo responde en modo LAN |
| `backend/config.py` | `LAN_MODE_ENV` + `lan_mode()` (fail-closed, leído al decidir); `LOCAL_ORIGIN_REGEX` (loopback, siempre) separada de `LAN_ORIGIN_REGEX` (IPs privadas); `cors_origin_regex()` y `ALLOWED_ORIGIN_REGEX` |
| `backend/security.py` | **Sí cambia** (ver §5.7): `origin_allowed` consulta `lan_mode()` por petición y usa `fullmatch`; dos patrones en vez de uno |
| `backend/routers/network.py` | informa del modo (`lan_mode`, `bind`) y **no anuncia** la URL de LAN si no responde |
| `backend/main.py` | comentario del CORS + log del modo de red en el arranque |
| `launcher/launcher.py` | fila LAN con estado («desactivada (solo este equipo)») y pie con el paso que falta, en vez de un enlace muerto |
| `launcher/allow-firewall.ps1` | avisa de que la regla sola no da acceso sin el modo LAN |
| `frontend/src/api/network.ts` + `components/ConnectDeviceCard.tsx` + `i18n.ts` | la tarjeta de conexión no ofrece QR ni enlace si el modo está apagado |
| `README.md`, `docs/PREMISAS.md`, `docs/ARQUITECTURA.md`, `docs/DEVICE_MATRIX.md`, `docs/audit/RC-RUNTIME-PRODUCTO.md` | declarar la frontera nueva (loopback por defecto) y corregir la deriva del `--host` |

### 5.4 Tests (el que falla sin el cambio) — implementado

- `launcher/tests/test_core.py::test_backend_command_binds_loopback_by_default`:
  sin la variable, `--host` es `127.0.0.1` y `0.0.0.0` **no** aparece. (Hoy el
  primer caso falla: siempre devuelve `0.0.0.0`.)
- `launcher/tests/test_core.py::test_backend_command_binds_lan_when_declared`:
  con la variable, `0.0.0.0`.
- `launcher/tests/test_lan_mode.py::test_el_launcher_declara_el_modo_en_el_entorno_del_backend`
  y `test_el_bind_y_el_entorno_no_pueden_discrepar`: la deriva launcher↔backend,
  que es el fallo silencioso clásico de este diseño.
- `launcher/tests/test_lan_mode.py::test_la_variable_se_llama_igual_en_launcher_y_backend`:
  el contrato de nombre se fija leyendo `backend/config.py` como texto (el
  launcher no puede importar el backend), igual que ya se hacía con
  `ENGLISH_TUTOR_REQUIRE_UI`.
- `backend/tests/test_security.py::test_los_origenes_de_la_red_local_exigen_modo_lan`:
  un `Origin` de `https://192.168.1.20:8000` se **rechaza** sin modo LAN y se
  **acepta** con él.
- `backend/tests/test_cors.py::test_cors_rejects_lan_ip_origin_without_lan_mode`.
- `backend/tests/test_lan_mode.py::test_las_dos_mitades_de_la_politica_de_origen_coinciden`:
  el patrón de `CORSMiddleware` y el 403 de `security.py`, comparados sobre 14
  orígenes en los dos modos.
- `backend/tests/test_lan_mode.py::test_los_docs_declaran_la_frontera_de_loopback`:
  la deriva documental que impide que el usuario sepa qué hacer.

### 5.5 Criterio de aceptación

Arrancar el producto **sin tocar nada** deja la API inalcanzable desde otro
equipo, y el panel del launcher **dice por qué** y cómo cambiarlo.

### 5.6 Respuestas del gerente (2026-09-18)

| Pregunta | Decisión |
|---|---|
| ¿Se aprueba el plan? | **Fase 1 ahora**, y parar para revisión antes de la Fase 2 |
| ¿Cómo se activa el modo LAN? | **Variable de entorno** (una sola fuente de verdad) |
| ¿Qué se hace con `et_user_id`? | **Retirarla** en la Fase 2 (`GET /api/session` como única fuente) |

### 5.7 Corrección al plan: `security.py` sí cambia de código

El plan (§5.3, primera versión) decía que bastaba con vaciar
`ALLOWED_ORIGIN_REGEX` y que `security.py` no necesitaba cambios. **Es falso, y
por una razón que conviene dejar escrita:** `origin_allowed` comprobaba con
`_ORIGIN_RE.match(...)`, y un patrón **vacío** casa con cualquier cadena. Vaciar
la regex habría **abierto** CORS en lugar de cerrarlo: el 403 habría dejado pasar
todo. Es el fallo clásico de «desactivar una validación» dejándola vacía.

Lo implementado: `security.py` mantiene la decisión explícita
(`config.lan_mode() and _LAN_ORIGIN_RE.fullmatch(origin)`), separa los orígenes de
loopback (siempre válidos) de los de red privada (opt-in) y usa `fullmatch`. Un
test compara las **dos** mitades de la política —el 403 y el patrón de
`CORSMiddleware`— sobre 14 orígenes en los dos modos: si una se relaja sola, falla.

### 5.8 Alcance ajustado: el botón del panel (Fase 1b, implementado)

El plan pedía un botón de habilitar en el panel. Con la variable de entorno como
única fuente de verdad, un botón no puede **persistir** el modo (sería un ajuste
persistido, la opción descartada), pero sí puede **declararlo y reiniciar**: el
modo viaja al backend por su entorno, así que basta con volver a arrancarlo.

Lo implementado: el panel de acceso tiene un botón «Activar/Desactivar red local»
que declara el modo (`core.set_lan_mode`), refresca la fila —enlace si responde,
«desactivada (solo este equipo)» si no— y reutiliza el **«Reiniciar servidor»**
que ya existía en la barra de acciones. Con la app parada solo deja el modo
declarado, y lo dice. La decisión vive en `core.py`, no en la GUI, para que tenga
test: la GUI de `tkinter` no se puede probar sin pantalla.

> **V3.75.3 — §5.8 revisado.** El gerente decidió después (pregunta abierta nº 1 de
> §9) que el launcher **recuerde** la última configuración. El modo LAN ya no vive
> solo en el entorno del proceso: se persiste en `launcher/config.json`. El botón
> se conserva y significa lo mismo, pero deja de ser una decisión de sesión. Las
> consecuencias, en §5.9.

### 5.9 V3.75.3 — la preferencia de red se persiste (reversión asumida)

Pedido del gerente: «si se activa RED LOCAL, al abrir el launcher otra vez debe
seguir activa». Se implementa como **ajuste persistido del launcher**, que es
justo la opción que §5.8 descartaba. Queda escrito y con su porqué:

- **`launcher/config_store.py`** (nuevo, calcado de `state_store.py`): lee y escribe
  `launcher/config.json` con `{"lan": false}`. El valor por defecto es **cerrado**
  (fichero ausente, corrupto o con un valor que no sea booleano ⇒ LAN desactivada).
- **Arranque** (`LauncherApp.__init__`): `load_config()` + `core.apply_lan_config`
  **antes** de `_build_ui()`, así que `_refresh_access` pinta el modo vigente en el
  primer pintado. La preferencia guardada **manda sobre el entorno heredado** (un
  `ENGLISH_TUTOR_LAN=1` de una consola no deja la casilla activada sin reflejarlo).
- **Cambio** (`toggle_lan_mode`): se guarda **en el acto**, no al cerrar la ventana.
  Una preferencia de red no debería depender de que el launcher se cierre bien.
- `config.json` se ignora en git (preferencia por equipo, igual que `state.json`).
- `apply_lan_config` abre **solo** con el booleano `True` (`is True`): un `1` o un
  `"sí"` editados a mano en el JSON se leen como cerrado.

**Lo que cambia en el análisis de riesgo de este plan:** el modo LAN pasa de
decisión de sesión a **decisión de instalación**. Un equipo con `{"lan": true}`
arranca con uvicorn en `0.0.0.0` y aceptando orígenes de red privada **sin que
nadie lo declare en esa sesión**. Mientras no exista la Fase 3 (credencial o
emparejamiento), el P0 sigue abierto y R5 (`GET /api/users` enumera perfiles sin
credencial) sigue alcanzable para quien esté en esa red.

**Mitigación honesta (no elimina el riesgo):** el modo es **visible** —la fila LAN
muestra el enlace y el botón «Desactivar red local» desde el primer pintado, no hay
modo silencioso—, el fichero es local, y desactivar se persiste igual de inmediato.
Lo que **no** cambia: la superficie de la API en modo LAN y la prioridad de la Fase 3.

---

## 6. Fase 2 — La identidad sale de la URL

**Depende de la Fase 1.** Sin ella, no cierra nada (§4).

### 6.1 Diseño propuesto

- **`backend/services/sessions.py`** (nuevo, solo stdlib):
  - Secreto de firma en `DATA_DIR/session.secret` (32 bytes `secrets.token_urlsafe`,
    permisos de usuario, creado en el primer uso).
  - `issue(user_id) -> str`: `base64url(payload).base64url(hmac_sha256(secreto, payload))`
    con `payload = {uid, iat}`.
  - `verify(token) -> str | None`: comparación en **tiempo constante**
    (`hmac.compare_digest`) y caducidad declarada.
- **`backend/routers/session.py`** (nuevo):
  - `POST /api/session` `{user_id}` → 404 si el perfil no existe; `Set-Cookie` y
    devuelve el perfil.
  - `GET /api/session` → el perfil de la sesión (la UI lo pregunta en vez de
    fiarse de una cookie que JavaScript puede leer).
  - `DELETE /api/session` → cierra sesión.
  - Cookie `et_session`: **`HttpOnly`**, `SameSite=Lax`, `Path=/`, `Secure`
    cuando la petición es HTTPS, `Max-Age` largo (mismo «recuerda mi perfil» de
    hoy, pero **fuera del alcance de JavaScript**).
- **`backend/dependencies.py`**: `current_user` pasa a leer la cookie.
  - Sin cookie o firma inválida ⇒ **401 `SESSION_REQUIRED`**.
  - Cookie válida pero perfil borrado ⇒ 404 (igual que hoy).
  - `current_user_optional` ⇒ `None` sin cookie (su semántica no cambia).
- **`backend/dependencies.py`**: la autoridad del perfil deja de ser una
  convención.
- **`backend/routers/users.py`**: `PATCH /api/users/{id}` exige sesión **y que
  `id` sea el de la sesión** (403 si no). `POST /api/users` (alta, primer arranque)
  sigue abierto; `DELETE` (perfiles de prueba) sigue exigiendo PIN de admin.

### 6.2 Frontend

| Fichero | Cambio |
|---|---|
| `frontend/src/api/session.ts` (nuevo) | `openSession`, `getSession`, `closeSession` |
| `frontend/src/api/*.ts` (**17**) | dejan de añadir `?user_id=…`; el parámetro pasa a `_userId` (ver §7.3) |
| `frontend/src/App.tsx` | al arrancar pregunta `GET /api/session`; seleccionar o crear perfil abre sesión; cambiar de perfil la reabre |
| `frontend/src/utils/cookie.ts` | **se retira** `et_user_id` (§7.1) |
| `frontend/src/components/ProfileGate.tsx` | sin cambio de contrato: `onSelect` ahora abre sesión |

### 6.3 Tests (los que fallan sin el cambio)

- **`test_identity_source.py` (nuevo, el test clave):** con sesión válida del
  perfil **A**, pedir `/api/profile?user_id=B` devuelve **los datos de A**. Es el
  test que fija la vulnerabilidad, no un detalle de implementación.
- **`test_sessions.py` (nuevo):** ida y vuelta de firma; token manipulado ⇒ 401;
  caducado ⇒ 401; sin cookie ⇒ 401 `SESSION_REQUIRED`; `HttpOnly` y `SameSite`
  presentes; `Secure` **solo** en HTTPS; `POST /api/session` con perfil inexistente
  ⇒ 404.
- **`test_users_self_only.py` (nuevo):** con sesión de A, `PATCH /api/users/{B}`
  ⇒ 403; `PATCH /api/users/{A}` ⇒ 200.
- **`conftest.py`:** adaptador para las **109** suites existentes (§7.2).
- **Frontend:** `api/session.test.ts` nuevo; los 17 `*.test.ts` que hoy afirman
  `user_id=` en la URL se actualizan (afirmarán su **ausencia**).

### 6.4 Criterio de aceptación

`rg "user_id=" frontend/src/api --glob "!*.test.ts"` ⇒ **0 coincidencias**: no queda
ninguna URL con la identidad dentro. El `user_id` que **sí** sobrevive es el de
cuerpo de dos contratos que lo exigen por diseño (`POST /api/session` —lo que pides
abrir— y el `user_id` de `PUT /api/settings`, que el servidor contrasta con el de la
sesión y rechaza con 403 si no coincide); buscarlo sin filtrar por `=` mezclaría
ambos casos, y el criterio decía `user_id` a secas antes de que existieran.

Con una sesión de A, ninguna petición puede leer ni escribir datos de B.

---

## 7. Acoplamientos descubiertos (no visibles desde el dossier)

### 7.1 El launcher diagnostica `et_user_id`

`launcher/browser_cookies.py:24` lee `APP_COOKIE_NAME = "et_user_id"` de las bases
de cookies de Chrome/Edge/Firefox para mostrar **qué perfil recuerda el navegador**
(`cookie_summary`, `:288-296`). Retirar esa cookie en la Fase 2 **deja el
diagnóstico mudo** sin que ningún test lo note (lee bases reales del sistema, que
en CI no existen). La Fase 2 debe actualizar ese diagnóstico a «sesión activa:
sí/no», y el plan lo declara aquí porque es el tipo de acoplamiento que un plan
centrado en el backend no ve.

**Cómo se cerró (§14.1).** `APP_COOKIE_NAME = "et_session"` y el resumen devuelve
presencia (`session_open: bool`), no identidad: **qué** perfil hay abierto lo sabe
el servidor, y esta pantalla no descifra el token. Además se **enmascara su valor**
(`_mask_value`): Firefox guarda las cookies en claro, así que sin eso el panel
imprimiría la sesión firmada —una sesión copiable de una captura de pantalla—.
El resto del diagnóstico (caducidad, `Secure`, `HttpOnly`, navegador y perfil de
navegador) queda intacto: es para lo que sirve el panel.

### 7.2 El adaptador de `conftest` y su trampa

Las **109** suites llaman a la API con `params={"user_id": uid}`. Para no reescribir
109 ficheros, el adaptador de `conftest` traducirá ese parámetro a una **sesión
emitida de verdad** y **delegará en el camino real** de `current_user`.

- **Lo que se adapta:** el *origen* de la identidad (query de test → cookie).
- **Lo que NO se adapta:** la verificación de firma, la caducidad, el 401 y el 404,
  que se ejecutan igual.
- **Lo que se pierde, y hay que declararlo:** las 109 suites dejan de probar «la
  identidad viene de la cookie». Eso lo cubren los tests nuevos de §6.3. La
  alternativa (tocar 109 ficheros) tiene un coste de revisión mucho mayor y el
  mismo poder de prueba.

### 7.3 `noUnusedParameters` está activo

`frontend/tsconfig.json:15-16` activa `noUnusedLocals` y `noUnusedParameters`. Dejar
el parámetro `userId` sin usar en los 17 módulos de la capa `api/` **rompería
`tsc`**. Se renombra a `_userId` (permitido por la convención y **sin tocar a
ningún llamante**, porque los argumentos son posicionales). Retirar el parámetro y
limpiar los ~85 componentes es la **Fase 2b opcional**.

### 7.4 El secreto de sesión no puede viajar en el backup

`DATA_DIR/session.secret` es una clave de firma. Un ZIP sin cifrar con la clave
dentro permite **forjar sesiones**. Se añade a `_NON_PORTABLE_TOP_NAMES`
(`backend/services/backup.py:44`), que ya excluye del ZIP **y** conserva al
restaurar; el mecanismo comprueba `p.name` antes de `is_file()`, así que sirve
tanto para la carpeta `certs/` como para un fichero suelto. Restaurar un backup no
invalidará las sesiones abiertas.

### 7.5 URL de LAN contra bind loopback

Con la Fase 1, el panel del launcher puede anunciar una URL de LAN que **no
responde** (bind a `127.0.0.1`). Es deliberado, pero hay que hacerlo visible (§5.2
punto 5) o se convierte en un fallo confuso.

---

## 8. Orden, versionado y verificación

**Orden:** Fase 1 → Fase 2 → (opcional) Fase 2b. Cada fase es un commit y una
release independiente, para que un problema en la segunda no arrastre a la primera.

**Versionado:** cada fase se publica **por separado**, así que le corresponde un
minor a cada una: la Fase 1 cambia la frontera de red del producto (deja de
exponerse sola) y la Fase 2 cambia el **contrato de la API** de forma incompatible
(un cliente que hoy manda `?user_id=` deja de funcionar). Ninguna de las dos cabe
en un parche de la línea 3.73.x. *(La primera versión de este plan asignaba V3.74.0
al par: era inconsistente con «cada fase, una release».)*

**Verificación por fase:** suites completas (backend, frontend, launcher),
`ruff`/`tsc`, i18n `--strict`, `validation_gate.py auto`, `check_release_consistency`
en los 6 orígenes, y **prueba explícita de que los tests nuevos fallan sin el
cambio** (stash temporal del fuente), como se hizo en V3.73.7.

---

## 9. Riesgos y preguntas abiertas

| # | Riesgo | Mitigación propuesta |
|---|---|---|
| R1 | Que la Fase 2 se lea como «el P0 está cerrado» cuando sin la Fase 3 no hay autenticación | Declararlo en las notas de release y en `PARKED.md`, con las palabras de §4 |
| R2 | El adaptador de `conftest` podría enmascarar una regresión en `current_user` | Delega en el camino real y hay tests dedicados (§7.2) |
| R3 | Retirar `et_user_id` afecta al diagnóstico del launcher | §7.1, con su cambio en la misma fase |
| R4 | Un usuario con el móvil configurado pierde el acceso tras la Fase 1 | El launcher lo dice y lo ofrece; el paso queda documentado en README |
| R5 | `GET /api/users` sigue enumerando perfiles sin credencial en modo LAN | **Sigue abierto en modo LAN** y se declara: es la razón de ser de la Fase 3 |
| R6 | Los 7 gates físicos están `pending` y anclados a `3.73.6`/`13cc30b` | Orden indiferente por decisión del gerente; si la campaña se ejecuta después, sellará el SHA nuevo |
| R7 | El plan cita líneas y cifras del árbol `v3.73.7`: si el árbol se mueve antes de ejecutarlo, la medición caduca | Re-medir (§11) antes de empezar cada fase |

**Preguntas abiertas para el gerente:**

1. ~~¿El modo LAN se activa con **variable de entorno**, con un **ajuste
   persistido** del launcher, o con un **flag de línea de comandos**?~~
   **Respondida en V3.75.3: ajuste persistido del launcher** (`launcher/config.json`
   + `launcher/config_store.py`, §5.9). La variable de entorno no desaparece: sigue
   siendo el **transporte** hacia el backend (`ENGLISH_TUTOR_LAN`), que no cambia.
2. ¿La Fase 2 debe **retirar** `et_user_id` (una sola fuente de verdad) o
   **conservarla** como pista inocua de «último perfil»? El plan propone retirarla.
3. ¿`POST /api/users` (crear perfil) debe seguir **abierto** —es el flujo de primer
   arranque— o pasar a exigir PIN de admin en modo LAN?

---

## 10. Criterios de parada

Este plan **no se ejecuta** y se vuelve a diseñar si:

- el gerente decide que el modo LAN con **varios alumnos** es un requisito real: en
  ese caso, sin credencial o emparejamiento (Fase 3) la Fase 2 es decoración y el
  orden cambia (Fase 3 antes que Fase 2); o
- el adaptador de `conftest` resulta exigir tocar ficheros de test más allá del
  propio `conftest` y los tests nuevos: se replanteará el alcance antes de seguir,
  en vez de arrastrar una migración de 115 ficheros dentro de un «cierre de P0».

---

## 11. Verificar (comandos de la medición)

```powershell
# El cuello de botella es uno: 1 definición y 138 usos
rg -c "Depends\(current_user" backend                      # 20 routers
rg -n "async def current_user" backend\dependencies.py      # 1 función

# El alcance del frontend
rg -c "user_id" frontend\src\api                            # 17 módulos de producción
rg -n "noUnusedParameters" frontend\tsconfig.json           # true -> el parámetro debe renombrarse

# Lo que hoy se enlaza y lo que hoy se anuncia
rg -n "0\.0\.0\.0" launcher\core.py
rg -n "LAN_IP_ENV|def lan_url" launcher\core.py

# El acoplamiento que el plan no puede olvidar
rg -n "APP_COOKIE_NAME|et_user_id" launcher\browser_cookies.py

# La superficie de perfiles, hoy sin credencial
rg -n "Depends|async def" backend\routers\users.py
```

## 12. Tests que respaldarán este plan

| Test | Qué fija | Estado |
|---|---|---|
| `launcher/tests/test_core.py::test_backend_command_binds_loopback_by_default` | Sin modo LAN no se expone la API (Fase 1) | **implementado** |
| `launcher/tests/test_lan_mode.py::test_el_bind_y_el_entorno_no_pueden_discrepar` | Bind y modo declarado son una sola decisión (Fase 1) | **implementado** |
| `backend/tests/test_security.py::test_los_origenes_de_la_red_local_exigen_modo_lan` | CORS deja de aceptar IPs privadas por defecto (Fase 1) | **implementado** |
| `backend/tests/test_lan_mode.py::test_las_dos_mitades_de_la_politica_de_origen_coinciden` | El 403 y el patrón de CORS no pueden divergir (Fase 1) | **implementado** |
| `backend/tests/test_lan_mode.py::test_los_docs_declaran_la_frontera_de_loopback` | README/PREMISAS/ARQUITECTURA declaran la frontera (Fase 1) | **implementado** |
| `frontend/src/components/ConnectDeviceCard.test.tsx` | La tarjeta no ofrece QR ni enlace muertos (Fase 1) | **implementado** |
| `backend/tests/test_identity_source.py` | La identidad **no** la elige el cliente (Fase 2) | **implementado** |
| `backend/tests/test_sessions.py` | Firma, caducidad, atributos de la cookie y 401 (Fase 2) | **implementado** |
| `backend/tests/test_users_self_only.py` | Un perfil no edita a otro (Fase 2) | **implementado** |
| `backend/tests/test_backup.py::test_backup_excludes_session_secret` | El secreto de firma no sale en el ZIP (§7.4) | **implementado** |
| `backend/tests/test_public_surface.py` | La superficie sin sesión está declarada y acotada (`VG-N6`) | **implementado** (§14.3) |
| `backend/tests/test_supply_chain_v375.py` | Actions por SHA, auditoría de dependencias y Dependabot (`VG-N5`) | **implementado** (§14.3) |
| `frontend/src/utils/session.test.ts` | `planSession`: adoptar o abrir sesión al arrancar (Fase 2) | **implementado** |
| `launcher/tests/test_browser_cookies.py::test_read_firefox_masks_session_token` | El token de la sesión no se imprime en el panel (§7.1) | **implementado** |

---

## 13. Estado de la Fase 1 (2026-09-18)

**Publicada como `v3.74.0`.** Pendiente de empaquetado solo lo que corresponde a la
Fase 2.

**Implementado y verde:**

- `launcher/core.py` (`LAN_ENV`, `lan_mode`, `backend_host`, `backend_env`
  canonizado, `backend_command`), `launcher/launcher.py` (panel con estado),
  `launcher/allow-firewall.ps1`.
- `backend/config.py`, `backend/security.py`, `backend/routers/network.py`,
  `backend/main.py` (log del modo).
- `frontend/src/api/network.ts`, `ConnectDeviceCard.tsx`, claves i18n `connect.lanOff`
  / `connect.lanOffHow`.
- Frontera declarada en `README.md`, `docs/PREMISAS.md`, `docs/ARQUITECTURA.md`,
  `docs/DEVICE_MATRIX.md` y corregida la deriva de `docs/audit/RC-RUNTIME-PRODUCTO.md`.
- Tests: `launcher/tests/test_lan_mode.py` + los de `test_core.py`,
  `backend/tests/test_lan_mode.py` + los de `test_security.py`, `test_cors.py`,
  `test_network.py`, y `frontend/src/components/ConnectDeviceCard.test.tsx`.

**Empaquetado (decidido y ejecutado):**

- **Versión y release.** Se publicaron **dos releases separadas**, cada una medida
  en **su propio árbol**: primero el lote de endurecimiento como **`v3.73.7`**
  (2817 / 717 / 113) y después la Fase 1 como **`v3.74.0`** (2840 / 719 / 139). El
  árbol mezclaba los dos lotes y varios ficheros (`backend/config.py`,
  `backend/security.py`, `backend/main.py`, `frontend/src/utils/i18n.ts`, tests y
  documentación) llevaban hunks de ambos, así que se **desmezcló** antes de
  commitear y las cifras del parche se reprodujeron exactas en el árbol aislado: es
  la comprobación de que la separación fue fiel.
- **`PARKED.md`.** Sección nueva `V3.74` que declara qué cierra la fase (la
  exposición por defecto) y qué **no** (la identidad sin autenticar: **P0 sigue
  abierto**, y en modo LAN `/api/users` sigue enumerando y creando perfiles sin
  credencial). Es la mitigación `R1`.
- **Notas y changelog:** `release-notes-v3.74.0.md`, entrada en `CHANGELOG.md`,
  `PLAN.md` y la nota de `docs/RELEVO.md`.
- **Botón «Activar/Desactivar red local»** (Fase 1b): implementado y reutilizando
  el «Reiniciar servidor» existente, ver §5.8.

**Siguiente paso (cuando el gerente lo dé):** Fase 2 — identidad derivada de una
sesión firmada, retirada de `et_user_id` y cierre del borde de autorización por
perfil. Cambia el **contrato de la API**, así que merece su propia release.

---

## 14. Estado de la Fase 2 (2026-09-18) — implementada en `v3.75.0`

**Aprobada y ejecutada sobre el árbol de `v3.74.0`**, junto con los dos P3 que
seguían abiertos (`VG-N5`, `VG-N6`). Cifras del árbol medido: backend **2882**
(2840 → +42), frontend **721** (719 → +2 netos: +7 nuevos y −5 del `cookie.test.ts`
retirado), launcher **142** (139 → +3), `ruff`/`tsc` limpios, i18n `--strict` 0/0/0,
`validation_gate.py auto` 10/10, `check_release_consistency` en los **6** orígenes.

### 14.1 Lo que se implementó, y dónde

| Pieza | Fichero | Qué hace |
|---|---|---|
| Firma de sesión | `backend/services/sessions.py` (nuevo) | Secreto en `DATA_DIR/session.secret`; `issue`/`verify` con HMAC-SHA256 y `hmac.compare_digest`; `SESSION_TTL_SECONDS` |
| Ciclo de sesión | `backend/routers/session.py` (nuevo) | `POST`/`GET`/`DELETE /api/session`; cookie `et_session` `HttpOnly`, `SameSite=Lax`, `Secure` si la petición es HTTPS |
| Identidad | `backend/dependencies.py` | `current_user` verifica la cookie ⇒ 401 `SESSION_REQUIRED`; `current_user_optional` ⇒ `None` |
| Autorización | `backend/routers/users.py`, `routers/settings.py` | editar perfil/preferencias exige sesión **y** que el id sea el de la sesión (403 si no) |
| Backup | `backend/services/backup.py` | `session.secret` fuera del ZIP y **conservado** al restaurar (§7.4) |
| Frontend | `api/session.ts`, `api/client.ts`, `hooks/useChat.ts`, `utils/session.ts`, 17 módulos de `api/` | la identidad sale de las URLs; al arrancar se pregunta `GET /api/session`; elegir o crear perfil **abre** sesión; `planSession` decide adoptar/abrir con test propio |
| Retirada | `frontend/src/utils/cookie.ts` (+ su test) | se va `et_user_id`: la identidad ya no la escribe JavaScript |
| Launcher | `browser_cookies.py`, `launcher.py` | «sesión abierta: sí/no» con el valor **enmascarado** (§7.1) |

**Tres correcciones de diseño que no estaban en el plan y se encontraron
implementando:**

1. **`_secret()` con fichero vacío** entraba en bucle (existía pero no era secreto).
   Ahora un `session.secret` vacío se considera «sin secreto» y se regenera.
2. **La máscara del token no debía pisar las descripciones.** Chromium cifra sus
   cookies y el panel muestra «(cifrado · N bytes)»: enmascarar eso diría «sesión
   firmada» de algo que no se ha podido leer. La máscara respeta la descripción.
3. **Los tests crudos no pueden usar `TestClient`.** El adaptador de `conftest.py`
   convierte `?user_id=` en sesión, así que «sin sesión + `?user_id=`» era
   inexpresable con él: los tests que fijan la vulnerabilidad van marcados
   `identidad_cruda` (marcador de pytest, registrado en `backend/pyproject.toml`).
   El primer intento usó `httpx.ASGITransport`, que es **solo asíncrono** y no
   funciona con un `httpx.Client` síncrono.

### 14.2 Alcance real de lo cerrado (no es «el P0 está cerrado»)

Lo que cambia es **quién es la autoridad sobre la identidad**: antes el cliente
(`?user_id=` en cada petición), ahora el servidor (cookie firmada). Lo que **no**
cambia es que **no hay autenticación**: `POST /api/session` acepta cualquier
`user_id` existente, `GET/POST /api/users` siguen sin credencial y, en modo LAN,
quien alcanza la API puede abrir sesión para cualquier perfil. Lo que ya no puede
es **forjar** una identidad sin el secreto del equipo ni elegirla por petición. La
Frontera de red (Fase 1) sigue siendo la mitad que decide **quién llega**.

### 14.3 Los dos P3 que quedaban

- **`VG-N5` (dependencias y cadena de suministro).** Las Actions van **fijadas por
  SHA** (`checkout@11bd719…`, `setup-python@a26af69…`, `setup-node@49933ea…`, con la
  etiqueta en comentario), el workflow declara `permissions: contents: read` y hay
  un job **bloqueante** `deps-audit` (`pip-audit -r requirements.txt` +
  `npm audit --omit=dev --audit-level=high`). El escaneo **destapó** 10 avisos
  conocidos en `starlette 0.50.0` (arrastrado por `fastapi==0.128.0`) cuyos parches
  solo existen en `starlette>=1.0.1`: se sube `fastapi` a **0.141.1** (→
  `starlette 1.6.0`) y la suite completa pasa idéntica (**2875 passed** en el árbol
  intermedio, antes de los tests nuevos). Se añade **Dependabot** para pip, npm y
  `github-actions` (que mantiene frescos los pines). Candado:
  `backend/tests/test_supply_chain_v375.py`.
- **`VG-N6` (superficie sin credencial).** Se **declara aceptada** y acotada, con
  la lista escrita en `docs/ARQUITECTURA.md` (§«Superficie sin sesión») y un candado
  en **las dos direcciones** (`backend/tests/test_public_surface.py`): lo declarado
  sin sesión sigue respondiendo (si no, se rompe el launcher o la puerta de perfil)
  y lo declarado con sesión **no** sale sin ella. La sección del documento es
  obligatoria para el test: borrarla falla.

### 14.4 Mordida de los candados (verificada)

Cinco sabotajes controlados (aplicados y revertidos por script, cada uno contra su
test): reintroducir una **etiqueta móvil** de Action, volver **informativo** el job
de auditoría, borrar la **declaración** de superficie sin sesión, quitar
`HttpOnly` de la cookie de sesión, y hacer que el adaptador de `conftest` traduzca
**también** las peticiones crudas. Los cinco hicieron fallar su test.

### 14.5 Siguiente paso (cuando el gerente lo dé)

**Fase 3 — autenticación real** (y con ella, la política de quién puede abrir
sesión: PIN por perfil, o credencial por dispositivo). Es una **decisión de
producto**, no una fase técnica: contradice «sin cuentas, sin contraseñas» de
`docs/PREMISAS.md` y hay que elegir con el gerente qué se rompe a cambio. Hasta
entonces, la lista de §14.2 y la de `PARKED.md` son la declaración honesta del
alcance.
