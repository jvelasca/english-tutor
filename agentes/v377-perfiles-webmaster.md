# V3.77.0 — Perfiles con autorización del webmaster (peticiones + lanzador)

**Estado:** implementado. Decisiones tomadas por el gerente (2026-09-21) y una
**corrección durante la implementación** (ver §4bis), registrada en vez de
escondida.

---

## 1. El principio que sostiene todo

> **El webmaster no es un rol de la app: es quien ejecuta el lanzador.**

El launcher corre en el equipo que hospeda el backend y ya abre la BD de la app
en solo-lectura (`launcher/status.py::_connect_readonly`, `mode=ro`) para pintar
contadores y la lista de perfiles. La autoridad viene de **tener el equipo**, no
de una credencial de la aplicación.

**Consecuencia deliberada:** no se inventan cuentas, ni contraseñas, ni un rol
`is_admin`, ni un correo. La pregunta «¿tendrá cuentas el producto?» sigue
**aparcada** (`docs/audit/PARKED.md`, Fase 3 del P0) y esto **no la prejuzga**:
cuando llegue la autenticación de persona, este mecanismo se puede sustituir sin
deshacer nada.

## 2. Decisiones aprobadas (2026-09-21)

| Decisión | Elegida | Coste declarado |
| --- | --- | --- |
| Borrado | **Desactivar primero** (reversible, sale del selector, los datos quedan) y **purgar** como segundo paso explícito, con **snapshot ZIP previo** y confirmación por nombre | Purgar sigue existiendo y sigue siendo irreversible: la copia es la única red |
| Alta | **Solo el webmaster por el lanzador.** El alumno **solicita**; se cierra el alta anónima desde la LAN | Sin webmaster disponible, nadie crea un perfil |
| Credencial del launcher | **Doble candado**: loopback **y** PIN de administración (`X-Admin-Pin`, el de V1.37 ampliado a perfiles), declarado por el lanzador y **fail-closed** | Arrancar el backend a mano deja la administración deshabilitada; el PIN vive en el `config.json` del launcher (ignorado por git) |
| Empaquetado | **Una sola release** con la retención léxica y esto | La retención no se publica hasta que esto esté cerrado |

## 3. Modelo de datos

Tabla nueva `profile_requests` (la BD de la app, no un fichero aparte: sobrevive
reinicios, viaja en el backup y el lanzador ya sabe leerla):

| Campo | Para qué |
| --- | --- |
| `id` | Clave |
| `kind` | `create` \| `delete` |
| `display_name` | Nombre pedido (solo en `create`) |
| `user_id` | Perfil afectado (solo en `delete`) |
| `note` | Nota corta del solicitante (acotada) |
| `requested_at` | Cuándo llegó |
| `status` | `pending` \| `approved` \| `rejected` |
| `decided_at`, `decided_note` | Quién/cuándo/cómo se resolvió |
| `resolved_user_id` | Perfil creado al aprobar (para poder deshacer la decisión a mano) |

`users` gana **`status`** (`active` \| `disabled`). **No** gana rol.

**Una petición es inerte:** pedir no crea ni borra nada. Solo el webmaster resuelve.

## 4. Superficie nueva

### Peticiones (del alumno)

- `POST /api/profile-requests` — **sin sesión** (quien pide aún no tiene perfil).
  Tipo `create` con nombre + nota. Acotado: rate limit por IP, una pendiente por
  nombre, tope de pendientes, longitudes máximas, y **nada de PII** más allá del
  nombre y la nota.
- `POST /api/profile-requests/delete` — **con sesión**: el perfil pide borrarse.

Esto **amplía la superficie sin sesión**, así que entra en
`docs/ARQUITECTURA.md` §«Superficie sin sesión» y en `test_public_surface.py`.
El candado muerde en las dos direcciones: lo declarado responde sin sesión y lo
declarado con sesión no sale sin ella.

### Administración (del webmaster, vía lanzador)

`/api/admin/*`, con **doble candado** (loopback + `X-Admin-Pin`):

- `GET  /api/admin/profile-requests?status=pending`
- `POST /api/admin/profile-requests/{id}/approve` → crea el perfil (PIN opcional)
- `POST /api/admin/profile-requests/{id}/reject`
- `GET  /api/admin/users` → con `has_pin`, `status` y contadores
- `POST /api/admin/users` → alta directa por el webmaster
- `POST /api/admin/users/{id}/status` → `active` | `disabled`
- `POST /api/admin/users/{id}/purge` → exige el nombre exacto **y que el perfil ya
  esté desactivado**, más snapshot ZIP previo

**Fail-closed:** sin PIN declarado, o desde fuera de loopback, `403`. Sin PIN, la
administración está deshabilitada, no abierta.

### 4bis. Corrección durante la implementación: el candado es el PIN, no un token nuevo

El diseño pedía un **token en fichero** (`backend/data/admin.secret`, creado por el
lanzador). Se implementó en cambio el **PIN de administración que ya existía**
(V1.37, `X-Admin-Pin`, `config.admin_pin()`), por tres razones concretas:

1. **Ya era el candado declarado** para la administración de la biblioteca de audio,
   las copias y los ajustes. Añadir un segundo secreto para perfiles habría dejado
   **dos** mecanismos de administración en el producto, y el día que uno se cambie
   el otro se queda atrás sin que nadie lo note.
2. **Estaba deshabilitado de facto:** `ADMIN_PIN` era una constante sin ninguna vía
   de fijarla en el producto (honestidad declarada en
   `agentes/v371-runtime-offline-instalacion.md`). Lo que faltaba no era otro
   secreto, sino **poder declararlo**, y eso es lo que se hizo: el lanzador lo
   guarda en `launcher/config.json` (ignorado por git) y lo declara en
   `ENGLISH_TUTOR_ADMIN_PIN` del entorno del backend que él mismo arranca, así que
   los dos lados tienen el mismo valor por construcción.
3. **No añade un fichero que haya que proteger:** el token habría exigido `0600`,
   una entrada en `_NON_PORTABLE_TOP_NAMES` (porque un ZIP con la credencial dentro
   permite administrar) y una ruta de lectura en el backend. El PIN vive en la
   preferencia del lanzador y en el entorno del proceso; no hay fichero nuevo que se
   pueda copiar por descuido, así que `_NON_PORTABLE_TOP_NAMES` **no** cambia.
   Esta sección del diseño queda **corregida, no pendiente**.

Lo que se conserva íntegro del diseño: el **doble candado** (el PIN viaja en una
cabecera y en una red compartida eso es material expuesto, así que la frontera de
loopback no es un adorno), el **fail-closed** en las dos direcciones, y poder
**retirar** el PIN desde el lanzador —retirarlo cierra la administración de verdad,
también en el entorno (`core._declare_admin_pin`)—.

### 4ter. `POST /api/users` sigue existiendo

El alta del propio equipo **no** se elimina: es lo que hace posible el primer
arranque sin abrir el lanzador y lo que usan los tests visuales (`is_test`). Lo que
cambia es que **exige loopback**, que es exactamente la frontera de la
administración.

## 5. Cierre del alta anónima

Hoy `POST /api/users` está abierto a propósito, así que **cualquiera en la LAN
puede crear perfiles**. Pasa a estar permitido **solo desde loopback**: el primer
arranque en el propio equipo sigue funcionando y por LAN se pasa a solicitud.
`is_test` se conserva para el teardown de los tests visuales.

## 6. Lanzador

Sección **Perfiles**:

- contador de pendientes y refresco periódico mientras el lanzador está abierto
  (así «la solicitud llega al webmaster» de verdad, sin tener que ir a mirar);
- aprobar / rechazar (con nota);
- crear perfil (nombre + PIN opcional);
- desactivar / reactivar;
- purgar, con la confirmación por nombre y el aviso de qué se lleva;
- **el PIN de administración**: guardarlo, generarlo o retirarlo, y el estado del
  candado a la vista (sin PIN la sección está cerrada y lo dice).

## 7. Candados (tests)

- Una petición `pending` **no** crea ningún usuario.
- Aprobar crea **exactamente uno** y marca la petición; no se puede aprobar dos veces.
- `/api/admin/*` → `403` sin PIN y **también** con el PIN correcto desde fuera de
  loopback.
- Sin PIN declarado, la administración está deshabilitada (no abierta), también en
  el cliente del lanzador (que no manda ninguna petición sin PIN).
- La superficie nueva queda declarada en el documento (el candado de
  `test_public_surface.py` falla si se borra la declaración).
- Desactivar **conserva** la evidencia; purgar la elimina.
- Purgar un perfil **activo** se rechaza: obliga a pasar por la desactivación.
- Un perfil desactivado **no abre sesión** (`403 PROFILE_DISABLED`).
- El PIN **no** se guarda en el repositorio (la preferencia vive en
  `launcher/config.json`, ignorado por git) y su forma se valida al **leer**, así
  que un fichero tocado a mano no habilita administración con un PIN inválido.
- `POST /api/users` desde fuera de loopback → rechazado.

## 8. Lo que NO se hace (y por qué)

- **Cuentas, contraseñas, roles, correo, notificaciones fuera del equipo.** La
  decisión de fondo sigue aparcada; el PIN opcional de V3.76 es lo único que hay
  y esto no lo cambia.
- **Un panel de administración web.** La administración vive en el lanzador, que
  es lo que otorga la autoridad. Un panel por LAN sería una superficie nueva sin
  frontera real.
- **Aprobación automática.** Aprobar exige que alguien con el equipo lo decida.
