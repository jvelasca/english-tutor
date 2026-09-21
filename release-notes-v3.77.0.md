# Release notes — English Tutor v3.77.0

**Fecha:** 2026-09-21 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.76.0 → 3.77.0`

**CON migración de BD aditiva:** dos tablas nuevas de colecciones/retención, la tabla
`profile_requests` y la columna `users.status TEXT NOT NULL DEFAULT 'active'`
(`ALTER` idempotente con el idioma que ya existía: `PRAGMA table_info` +
`ALTER TABLE`), así que **una BD de V3.76.0 se actualiza sin que nadie pierda el
acceso ni su vocabulario**. **SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el currículum (`CURRICULUM_VERSION` sigue
`1.3.1`), SIN tocar las evaluaciones (`assessments.json`) y SIN tocar
`LISTENING_BANK_VERSION`.** No añade ni retira un gate: el árbol se congeló en
`v3.75.8` y **G1–G7 siguen `pending`**.

---

## 1. Qué es esta release, y por qué son dos trabajos en la misma etiqueta

Publica **dos trabajos** que se pidieron y se hicieron en la misma sesión:

- **(A) La retención léxica del diccionario personal**: añadir vocabulario (palabra
  suelta, lista pegada o pack por tema) y practicarlo con tarjetas y repetición
  espaciada, siguiendo de cerca a Anki, Memrise, Drops y Lingvist **solo** en esta
  parte.
- **(B) Los perfiles con autorización del webmaster**: el alumno **pide** un perfil
  (o su baja) y el webmaster lo resuelve **desde el lanzador**.

Van en **una sola release a propósito**, y el orden es una decisión de producto, no
una casualidad de calendario: **(A) escribe vocabulario personal en la BD de un
perfil**, y hasta V3.76 `POST /api/users` estaba abierto a la LAN, así que
**cualquiera en la red podía crearse un perfil** en la BD del alumno. Publicar (A)
primero habría añadido un módulo de escritura sobre una puerta abierta.

---

## 2. (A) Retención léxica

### 2.1 Unidades léxicas, no palabras sueltas

El motor trabaja sobre **unidades léxicas**: una palabra **o una frase funcional**
(«how long does it take»), con su forma, su sentido y **el contexto donde apareció**.

La diferencia importa: las frases de alta frecuencia son las que sostienen una
conversación, y un módulo que solo aceptara palabras las tiraba a la basura.

### 2.2 El puente con el resto de la app, y por qué no es automático

Lo trabajado en conversación, escritura, lectura y drill de vocabulario llega al
diccionario personal como **candidato**, con su **procedencia declarada**, y es **el
alumno** quien decide qué entra a la cola de retención.

Nada entra «solo». Un diccionario que se llena solo acaba siendo **un archivo que
nadie repasa**: la cola de retención se compra con una decisión, y por eso añadir es
un acto explícito y no un efecto secundario de usar la app.

### 2.3 Añadir de tres formas, con una sola puerta

| Forma | Qué es |
| --- | --- |
| **Palabra suelta** | Una unidad, con su sentido y su contexto |
| **Lista pegada** | Una por línea, tolerante a formato |
| **Pack por tema** | Comida, viaje, trabajo |

La lista y el pack son **azúcar sobre la misma entrada**: por debajo pasan por
`repositories/vocabulary.py::seed_study_items`, así que la validación, el
**deduplicado** y el **tope** viven **en un solo sitio**. Tres puertas distintas
habrían sido tres comportamientos que se separan al primer cambio.

### 2.4 Los packs son contenido, y el contenido se versiona

Los packs vivían en `backend/data/vocab_packs/`, que está **ignorado por git**.
Consecuencia: el contenido de los temas **no estaba en el repositorio** y no habría
viajado en la release —invisible para cualquiera que clonara el proyecto—. Se mueven
a `backend/curriculum/vocab_packs/`, que es donde vive el currículum que sí se
audita.

Se descubrió **al verificar la release**, y por eso se cuenta: era una fuga de
contenido, no un cambio de gusto.

### 2.5 La sesión de tarjetas y el planificador

- `domain/retention.py` programa el repaso con **FSRS-lite**, documentado en
  `docs/FSRS.md`. **No** es un SM-2 improvisado: cada unidad tiene **intervalo**,
  **facilidad** y **fecha de vencimiento**, y el desenlace de la tarjeta («otra
  vez», «difícil», «bien», «fácil») mueve el intervalo en consecuencia.
- `RetentionSession.tsx` es la pantalla. **Lo que decide «qué toca hoy» es lógica
  pura**, con test propio: la parte que puede estar mal es la que se puede probar sin
  navegador.

### 2.6 Retención ≠ dominio (la decisión de fondo de este bloque)

Recordar una palabra a largo plazo y **demostrar dominio** usándola bien en contexto
son **dos cosas distintas**, y se miden por separado.

El evento de repaso entra en la evidencia clasificado con **papel de retención**
(`services/evidence.py`), **no** como prueba de competencia. Si se contara como
dominio, **la matriz de destrezas subiría por recordar tarjetas** — que es
exactamente el tipo de inflación que la auditoría pedagógica persigue.

Esto está en el **código**, no solo en la intención, y tiene test.

---

## 3. (B) Perfiles con autorización del webmaster

### 3.1 El principio: el webmaster no es un rol, es quien ejecuta el lanzador

No se inventan **cuentas, contraseñas, roles ni correo**. La autoridad viene de
**tener el equipo**, y la decisión de fondo —¿tendrá cuentas el producto?— **sigue
aparcada** (`docs/audit/PARKED.md`): esto no la prejuzga y se puede sustituir sin
deshacer nada.

### 3.2 El alumno pide; el webmaster decide

| Ruta | Sesión | Qué hace |
| --- | --- | --- |
| `POST /api/profile-requests` | **sin sesión** | Pide un perfil nuevo (quien lo pide todavía no tiene ninguno) |
| `POST /api/profile-requests/delete` | **con sesión** | Pide la baja del perfil de la sesión |

La ruta de baja **no lleva `{id}`**: **no existe la forma de pedir la baja de otro
perfil**, ni por descuido.

La petición pública está **acotada**: cupo por IP, tope de peticiones pendientes y
una sola petición viva por nombre. Y, sobre todo, **una petición es inerte**: no crea
ni borra nada. Lo peor que puede hacer quien la llame es **dejar una fila que el
webmaster verá y podrá rechazar**.

### 3.3 El alta anónima por LAN se cierra

`POST /api/users` **estaba abierto a propósito** y eso significaba que **cualquier
equipo de la red podía crear perfiles** en la BD del alumno. Pasa a exigir
**loopback**.

- El **primer arranque en el propio equipo** sigue funcionando igual.
- Los **tests visuales** conservan su perfil `is_test` (también corren en el equipo).
- La frontera es el **loopback**, no la eliminación de la ruta.

### 3.4 Desactivar primero, purgar después y a mano

**Aprobar una baja desactiva el perfil:**

- sale del selector,
- **no puede abrir sesión** → `403 PROFILE_DISABLED`,
- su evidencia queda **intacta**,
- y se puede **reactivar**.

**Purgar** —borrar de verdad— es un acto **aparte** y exige:

1. el **nombre exacto** del perfil,
2. un **snapshot ZIP previo**,
3. y que el perfil **ya esté desactivado**.

Así el borrado irreversible tiene **siempre un momento anterior** en que la decisión
se podía deshacer. Si la copia **falla, no se purga**.

### 3.5 Doble candado en la administración

`/api/admin/*` exige **loopback Y** el PIN de administración (`X-Admin-Pin`), y es
**fail-closed**: **sin PIN declarado la administración está deshabilitada, no
abierta**.

Ninguno de los dos basta solo:

- el PIN **viaja en una cabecera** y en una red compartida eso es material expuesto;
- estar **en el equipo sin el PIN** no debería bastar para borrarle el historial a
  nadie.

El PIN es el que **ya existía** (V1.37) para la biblioteca de audio, copias y
ajustes. Lo que faltaba **no era otro secreto, sino poder declararlo**: el lanzador
lo guarda en su `config.json` (**ignorado por git**) y lo declara en
`ENGLISH_TUTOR_ADMIN_PIN` del entorno del backend que **él mismo arranca**, así que
los dos lados tienen el mismo valor **por construcción**.

**Corrección registrada.** El diseño original pedía un token en fichero
(`backend/data/admin.secret`). Se sustituye por el PIN, y el porqué está escrito en
`agentes/v377-perfiles-webmaster.md` §4bis: añadir un segundo secreto habría dejado
**dos** mecanismos de administración en el producto, y el día que uno se cambie el
otro se queda atrás sin que nadie lo note.

### 3.6 El lanzador gana la sección «Perfiles»

Es donde el webmaster trabaja:

- **contador de pendientes** con **refresco periódico** mientras el lanzador está
  abierto (para que «la solicitud llega al webmaster» sea verdad **sin ir a mirar**),
- **aprobar / rechazar** (con nota),
- **crear perfil** (nombre + PIN opcional),
- **desactivar / reactivar**,
- **purgar**, con confirmación por nombre y el aviso de qué se lleva,
- y **el estado del candado a la vista**: sin PIN, la sección está cerrada y **lo
  dice**.

`launcher/admin.py` es el **único** sitio del lanzador que escribe en el producto, y
lo hace **por HTTP**, no tocando la BD aunque la tenga a mano. El borrado tiene que
pasar por el mismo sitio que todo lo demás (validación, copia previa, tabla de
solicitudes) o habría **dos definiciones de «purgar»** y la del lanzador sería la que
nadie prueba.

### 3.7 La app deja de «crear» y pasa a «pedir», y lo dice

La puerta de perfil **ya no ofrece crear un perfil** —el backend lo cierra fuera del
equipo, así que prometerlo sería mentir— y explica el desenlace: **«solicitud
enviada; el webmaster tiene que autorizarla desde el lanzador»**.

El diálogo de perfil gana la sección de baja con el mismo criterio: **pide, no
borra**, y **no promete** que el perfil desaparezca.

---

## 4. Verificación

| Instrumento | Resultado |
| --- | --- |
| `pytest` (backend) | **2967 passed** / **0 skipped** |
| `pytest` (launcher, Windows) | **205 passed** |
| `tsc --noEmit` | limpio |
| `vitest run` | **872/872** (100 ficheros) |
| `npm run build` | correcto (`package.json` en `3.77.0`) |
| `ruff` (backend) | limpio |
| `ruff` (launcher) | limpio |
| i18n `--strict` | **1581 claves / 0 huérfanas / 0 usadas sin definir** |
| contraste `--strict` | **480 pares + 6 guardas / 0 bloqueantes** (17 pares de acento reportados, no bloqueantes) |
| `check_release_consistency` | OK en los **6 orígenes** (`3.77.0`) |
| `validation_gate.py auto` | **10/10** |

### Instrumentos nuevos

| Instrumento | Qué fija |
| --- | --- |
| `backend/tests/test_retention_personal_v377.py` | las unidades léxicas, el **deduplicado y el tope** de la puerta única, el puente con el resto de la app (candidato ≠ añadido) y la **clasificación del evento de repaso como retención, no como dominio** |
| `backend/tests/test_profile_requests_v377.py` | la petición **inerte**, aprobar crea **exactamente uno**, el **doble candado** (sin PIN y con PIN desde fuera de loopback), el borrado **en dos pasos**, el alta desde la LAN cerrada, el perfil desactivado que **no abre sesión**, y **purgar un perfil activo se rechaza** |
| `frontend/src/api/profileRequests.test.ts` | la traducción de desenlaces (duplicado, cola llena, inválido, frenado, sin servidor) a algo que la UI pueda **explicar** |
| `launcher/tests/test_admin_pin.py` | la forma del PIN, la preferencia que **manda** sobre el entorno, declararlo y **retirarlo** del entorno, y que `generate_admin_pin` ofrece **siempre** un PIN válido |
| `launcher/tests/test_admin_client.py` | el cliente `/api/admin/*`: que **no manda ninguna petición sin PIN**, que traduce los errores a frases en vez de lanzar, y que un servidor que no responde **no rompe la GUI** |

`test_public_surface.py` declara la superficie nueva **sin sesión**. El candado
muerde en las dos direcciones: **lo declarado responde sin sesión y lo declarado con
sesión no sale sin ella.**

### Dos fallos que encontraron los tests, no una lectura

1. **La suite de deriva documental** pedía que `launcher/admin.py` estuviera
   documentado en `ARQUITECTURA.md`. Se documentó (y con él la razón de que el
   lanzador hable por HTTP en vez de tocar la BD).
2. **`core.apply_admin_config` declaraba en el entorno el PIN heredado** cuando la
   preferencia se retiraba. Consecuencia real: el botón **«Retirar»** del lanzador
   decía «retirado» con la administración **todavía abierta**. Ahora retirar retira
   también del entorno (`_declare_admin_pin`), y `test_admin_pin.py` lo fija.

Y una tercera, de contenido: **los packs estaban en una carpeta ignorada por git**
(§2.4). Las tres se arreglaron **antes** de publicar; las tres se cuentan.

---

## 5. Honestidad

1. **Los packs por tema son tres** (comida, viaje, trabajo) y **no cubren un
   currículum**: son un punto de partida, no una biblioteca.
2. **FSRS-lite no es FSRS.** Es una versión **declarada y simplificada** del
   planificador: mismas cuatro salidas, pero **sin** los parámetros por alumno que
   FSRS completo ajusta con el historial. Llamarlo «FSRS» a secas daría más crédito
   del que tiene.
3. **La retención no mide dominio**, y el evento está clasificado para que no lo
   parezca (§2.6). Es la decisión de fondo del bloque (A).
4. **Esto NO cierra el P0 de identidad por defecto.** Un perfil **sin PIN** sigue
   entrando sin credencial y **sigue sin haber autenticación de persona**: ni
   identidad, ni recuperación. Lo que cambia es que **crear y borrar perfiles ya no
   es algo que cualquiera en la red pueda hacer**.
5. **Desactivar corta el acceso, pero no protege los datos.** La evidencia sigue en
   la BD hasta que se purgue, y una sesión ya abierta de ese perfil recibe `403`.
6. **Purgar es irreversible** y la copia previa es la **única** red. El ZIP **no
   está cifrado**: quien lo reciba tiene los datos, incluido el hash del PIN.
7. **El PIN de administración es una credencial compartida, no por persona.** Quien
   lo sepa y esté en el equipo administra; no hay registro de quién aprobó qué más
   allá de la nota de la decisión.
8. **La administración vive en el lanzador.** Sin el lanzador delante, **no hay
   forma de crear un perfil**: es el precio declarado de no tener cuentas.
9. **`POST /api/users` sigue existiendo** para el primer arranque del propio equipo.
   La frontera es el **loopback**, no la eliminación de la ruta.
10. **La decisión de fondo sigue abierta: ¿tendrá el producto cuentas?** Esta
    release responde «¿quién puede crear y borrar perfiles?», no «¿habrá cuentas?».
    Sigue contradiciendo «sin cuentas, sin contraseñas» de `docs/PREMISAS.md`.
11. **El orden de publicación es una decisión declarada**, no un accidente: (A) va
    **junto** a (B) porque (A) escribe vocabulario personal en la BD de un perfil
    (§1).
12. **Los 7 gates siguen en `pending`** y el árbol que se certifica sigue siendo el
    de `v3.75.8`.
13. **El `dist` no se versiona** (`.gitignore`): hay que **recompilar y reiniciar**
    el backend para ver la UI nueva. Es la causa más probable de «no veo nada
    nuevo»: una UI compilada antes de esta release.
14. **Los ítems aparcados siguen aparcados.** «FSRS por tipo de memoria» y «drills
    de producción por aspecto» siguen en `PARKED.md`: esta release no los toca.

---

## 6. Archivos del diff de producto

### Backend

- `backend/repositories/db.py` — `vocab_collections`, `vocab_collection_items`,
  `vocab_collection_membership`, `vocab_collection_enrollments`, `profile_requests`
  y la columna `users.status` (en el `CREATE TABLE` y en el bloque idempotente de
  `ALTER TABLE`), con el índice de la cola de solicitudes.
- `backend/repositories/collections.py` *(nuevo)* — colecciones y membresía;
  `PACKS_DIR` apunta a `curriculum/vocab_packs/`.
- `backend/repositories/vocabulary.py` — `seed_study_items` (la puerta única de las
  tres formas de añadir).
- `backend/repositories/profile_requests.py` *(nuevo)* — la cola: crear, listar,
  contar pendientes, resolver.
- `backend/repositories/users.py` — `status` en `_COLUMNS`, `set_status`,
  `purge_user`, `_purge_user_rows` y filtrado de desactivados en `list_users`.
- `backend/domain/retention.py` *(nuevo)* — FSRS-lite y «qué toca hoy».
- `backend/domain/profile_requests.py` *(nuevo)* — normalización, petición, decisión,
  alta, estado y purga (con la exigencia de desactivar antes).
- `backend/domain/users.py` — `STATUS_ACTIVE` / `STATUS_DISABLED` e `is_disabled`.
- `backend/schemas/vocabulary.py`, `backend/schemas/profiles.py` *(nuevo)*,
  `backend/schemas/users.py` — contratos nuevos (`status`) y de administración.
- `backend/routers/vocabulary.py` — endpoints de añadir, colecciones y repaso.
- `backend/routers/admin.py` *(nuevo)* — `/api/admin/*` bajo `require_admin_local`.
- `backend/routers/users.py` — `POST /api/users` solo desde loopback y las dos
  puertas públicas de solicitud.
- `backend/routers/session.py` — `403 PROFILE_DISABLED` al abrir y al leer sesión.
- `backend/dependencies.py` — `require_admin_local` y el corte del perfil
  desactivado.
- `backend/services/evidence.py` — el papel de **retención** en `classify_event_role`.
- `backend/security.py` — cupo para `/api/profile-requests`.
- `backend/config.py` — topes de la cola, contador de notas/nombres y
  `is_admin_loopback_host`.
- `backend/curriculum/vocab_packs/*.json` — los packs, **ahora versionados**.

### Frontend

- `frontend/src/api/profileRequests.ts` *(nuevo)* — las dos puertas de solicitud y la
  traducción de desenlaces.
- `frontend/src/api/vocabulary.ts` *(nuevo)* — añadir, colecciones y repaso.
- `frontend/src/features/vocabulary/RetentionSession.tsx` *(nuevo)* — las tarjetas.
- `frontend/src/features/vocabulary/AddVocabSection.tsx` *(nuevo)* — palabra, lista y
  tema.
- `frontend/src/features/vocabulary/PersonalDictionary.tsx` — reorganizado.
- `frontend/src/features/vocabulary/DictionaryLookup.tsx` — «añadir a personal».
- `frontend/src/components/ProfileGate.tsx` — de «crear» a «**pedir**».
- `frontend/src/components/UserMenu.tsx` — el desplegable pide y explica.
- `frontend/src/components/ProfileDialog.tsx` — la sección de baja (pide, no borra).
- `frontend/src/hooks/useChat.ts` — `requestProfileForGate` y `requestProfileRemoval`.
- `frontend/src/App.tsx`, `frontend/src/app/Header.tsx` — el cableado nuevo.
- `frontend/src/types/api.ts` — `User.status` y `ProfileRequest`.
- `frontend/src/utils/i18n.ts` — claves `user.request*` y `profile.delete*`; **se
  retiran** las de «crear perfil» que ya no usaba nadie.
- `frontend/src/styles/legacy.css` — el desenlace de «pedir un perfil».

### Lanzador

- `launcher/admin.py` *(nuevo)* — el cliente de `/api/admin/*`.
- `launcher/core.py` — el PIN de administración: forma, generación, preferencia,
  entorno (`apply_admin_config`, `set_admin_pin`, `_declare_admin_pin`).
- `launcher/config_store.py` — `admin_pin` en `DEFAULTS` y en `load_config`.
- `launcher/ui.py` — `pending_summary`, `request_row`, `profile_row`,
  `admin_state_label` y las etiquetas nuevas.
- `launcher/launcher.py` — la sección **«Perfiles»** y sus acciones.

### Documentación

- `CHANGELOG.md`, `PLAN.md`, `README.md`, `release-notes-v3.77.0.md` *(nuevo)*,
  `docs/RELEVO.md`, `docs/audit/PARKED.md`, `docs/ARQUITECTURA.md` (incluye
  `launcher/admin.py` y el `config.json` con el PIN) y
  `agentes/v377-perfiles-webmaster.md` (con la **corrección** §4bis registrada).

### Artefactos regenerados

- `docs/audit/generated/release-validation.{json,md}`, `i18n-report.{json,md}`,
  `contrast-report.{json,md}` — regenerados por sus instrumentos.
