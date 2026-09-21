# Release notes — English Tutor v3.76.0

**Fecha:** 2026-09-21 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.75.8 → 3.76.0`

**CON migración de BD** — la única del ciclo pre-V4.0: `users` gana
`pin_hash TEXT NOT NULL DEFAULT ''` con el idioma idempotente que ya existía
(`PRAGMA table_info` + `ALTER TABLE`), aditiva y con defecto vacío, así que una BD
de V3.75.8 se actualiza **sin que nadie pierda el acceso**. **SIN bump de
`GENERATOR_VERSION` ni `DECISION_POLICY_VERSION`, SIN tocar el currículum
(`CURRICULUM_VERSION` sigue `1.3.1`), SIN tocar las evaluaciones
(`assessments.json`) y SIN tocar `LISTENING_BANK_VERSION`.** No añade ni retira un
gate: el árbol se congeló en `v3.75.8` y **G1–G7 siguen `pending`**.

---

## 1. Qué es esta release

Es la **Fase 3 del P0 de identidad** (`docs/audit/PLAN-P0-IDENTIDAD.md`): el
problema que quedaba abierto desde V3.75 —`POST /api/session` aceptaba cualquier
`user_id` existente **sin credencial**— recibe una mitigación **opcional por
perfil**.

Y es, sobre todo, una release **honesta sobre lo que es**: **no** es
autenticación de persona, **no** cierra el P0 para el producto, y **no** convierte
el equipo en multiusuario seguro. Es una **llave de la puerta que el dueño del
perfil activa**, con la consecuencia declarada de que quien no la active sigue
entrando como siempre.

Además, en la misma sesión se preparó **G7**: los **9 dossiers** de auditoría se
regeneraron sobre el árbol congelado y resultaron **reproducibles byte a byte**
(§5).

---

## 2. La puerta: tres desenlaces distinguibles

`POST /api/session` acepta un campo **opcional** `pin`:

| Situación | Respuesta |
| --- | --- |
| El perfil **no** tiene PIN (`pin_hash = ''`) | `200` + cookie, **como siempre** |
| Tiene PIN y la petición no lo trae | `401 PIN_REQUIRED` |
| Tiene PIN y no cuadra | `401 PIN_INVALID` |
| El freno de intentos está activo | `429 PIN_THROTTLED` + `Retry-After` |

Los tres códigos de error son **distinguibles a propósito** —la UI tiene que saber
qué pintar— y **ninguno revela si el PIN estaba cerca**: no hay respuesta distinta
para «0000» que para «4822» que para «48211».

`User` gana **`has_pin: bool`**: la puerta necesita saber si preguntar. **El hash
no se serializa en ninguna respuesta**, ni en el perfil ni en la sesión, y hay dos
tests que lo comprueban sobre el **cuerpo crudo** de la respuesta (`"pin_hash"` y
`"pbkdf2"` no aparecen).

---

## 3. El hash y el freno

### 3.1 El hash (`backend/services/pins.py`)

- **PBKDF2-HMAC-SHA256** con **200 000 iteraciones** y **sal aleatoria por
  perfil** (dos perfiles con el mismo PIN no comparten hash).
- Las **iteraciones viajan dentro del valor**
  (`pbkdf2-sha256$<iter>$<sal>$<hash>`), así que subirlas más adelante no
  invalida los PIN ya guardados.
- Verificación con **`hmac.compare_digest`**. Un valor corrupto, vacío o de otro
  algoritmo **no autentica** (fail-closed, con test parametrizado).
- **Cero dependencias nuevas**: stdlib, la misma doctrina que
  `services/sessions.py`.

### 3.2 El freno de intentos — la pieza que sostiene todo

Un PIN de 4-6 dígitos es **fuerza bruta trivial sin freno**. Por eso el freno vive
en el mismo módulo que el hash y no como adorno:

- **5 fallos no frenan.** Dedos torpes no son un ataque; un alumno que se equivoca
  dos o tres veces no debe notar nada.
- A partir del sexto, el retardo **dobla**: 1 s, 2 s, 4 s… con **techo de 300 s**.
- Es **por perfil**, no global: un perfil bajo ataque **no deja fuera a los demás**
  del mismo equipo (hay test).
- **Se limpia al acertar.** Es la otra dirección, y sin ella un contador que nunca
  se vacía convertiría el PIN en una condena a la primera equivocación.
- Mientras está activo, **el PIN correcto tampoco pasa**: si no, el atacante
  tendría una ventana gratis justo cuando más ha insistido.
- `/api/session` entra además en `_PATH_LIMITS` (**120/min**). Declarado en el
  código como **primera valla, no como defensa**: el cupo por IP es holgado a
  propósito y una familia tras un NAT comparte IP.

---

## 4. Poner, cambiar y retirar el PIN

`PUT /api/session/pin` (ruta nueva) opera **bajo la sesión**, sin `{id}` en la
ruta: **no existe la forma de tocar el PIN de otro perfil ni por descuido**.

- Cambiar o **retirar** un PIN existente **exige el anterior**, con la misma puerta
  y el mismo freno. Sin eso, quien se sienta ante un equipo con la sesión abierta
  podría poner su propio PIN y **quedarse el perfil**.
- `new_pin` **vacío** retira el PIN: el perfil vuelve a entrar sin credencial (con
  su consecuencia declarada).
- `new_pin` con mala forma devuelve **400 `PIN_FORMAT`** y **no toca la BD**.
- Ajustes gana la pestaña **«PIN de este perfil»**, que declara en su propio texto
  qué protege y qué no.

### El arranque deja de fallar en silencio

Hasta esta release, un `POST /api/session` que no fuera 200 moría en un **`catch`
vacío**. Con un perfil con PIN eso habría pasado **siempre**: la app se habría
quedado sin perfil activo y el alumno habría visto una puerta que no responde, sin
un solo mensaje.

- `planSession` (`utils/session.ts`) gana el desenlace **`pin`**. Sigue siendo
  **función pura**, así que la matriz entera se prueba sin navegador.
- `useChat` centraliza la apertura en **un único camino** (`openProfile`) que usan
  los **tres** puntos que abren sesión: **arranque automático**, **selector de
  perfil** y **alta**.
- Como cambiar de perfil **dentro** de la app también puede pedir PIN, `App`
  muestra la puerta **aunque ya hubiera un perfil activo**. Si no, el paso habría
  quedado invisible detrás de la app y el selector habría parecido roto.
- Cancelar el paso de PIN **devuelve a la app con el perfil anterior intacto**.

### La UI no adivina

- `ApiError` (`api/client.ts`) pasa a conservar el **`detail`** y el
  **`Retry-After`**; `SessionPinError` los traduce a un desenlace tipado. Antes
  todos los 401 se convertían en un `Error` de texto y la UI solo podía decir
  «algo falló».
- `utils/pin.ts` es **espejo deliberado** de la validación del backend (4-6
  dígitos): la UI no ofrece un botón que el servidor va a rechazar.
- `ProfileGate` **filtra el tecleo a dígitos** en vez de validar «12ab» a
  posteriori.
- Quién decide que hace falta PIN es el **servidor**: `has_pin` solo evita el
  `POST` condenado del arranque. La lista de perfiles puede estar desactualizada,
  así que la puerta nunca da por hecho lo que no le han confirmado.

---

## 5. G7 preparado: los 9 dossiers son reproducibles

Los **9 dossiers** de `python -m scripts.audit_dossier` —`corpus-stats`,
`curriculum-stats`, `speaking-stats`, `mc-bias`, `cefr-adequacy`, `skill-coverage`,
`feedback-coverage`, `mastery-claims`, `assessment-instruments`— se regeneraron
sobre el **árbol congelado** (`v3.75.8` · `7134e538`) y
`git status docs/audit/generated/` quedó **vacío**: **ni un byte de diferencia**.

Es el mejor insumo posible para el veredicto humano de G7: los instrumentos
versionados **describen el árbol que se va a certificar**. Si algún día dejara de
cumplirse, ese diff sería un **hallazgo** (el artefacto versionado estaría
obsoleto), no un fallo del gate.

**`record pedagogia` no se ha ejecutado.** G7 **no se cierra con una
regeneración**: se cierra con la revisión humana de la matriz de los 9 ejes.

---

## 6. Verificación

| Instrumento | Resultado |
| --- | --- |
| `tsc --noEmit` | limpio |
| `vitest run` | **850/850** (98 ficheros) |
| `npm run build` | correcto; el bundle publica `3.76.0` |
| i18n `--strict` | **1533 claves / 0 huérfanas / 0 usadas sin definir** |
| contraste `--strict` | **480 pares + 6 guardas / 0 bloqueantes** (17 pares de acento reportados, no bloqueantes) |
| `check_release_consistency` | OK en los **6 orígenes** (`3.76.0`) |
| `validation_gate.py auto` | **10/10** |
| `pytest` (backend) | **2942 passed** / 0 skipped |
| `ruff` (backend) | limpio |
| Dossiers de G7 | regenerados sobre el árbol congelado, **sin diff** |

### Instrumentos nuevos

| Instrumento | Qué fija |
| --- | --- |
| `backend/tests/test_pin.py` (31 casos) | hash y verificación, la puerta en sus cuatro desenlaces, **el freno en las dos direcciones**, `has_pin` sin fuga del hash, ida y vuelta **real** por el ZIP de backup y la migración de una BD de V3.75.8 **sin** la columna |
| `api/session.test.ts` | los tres desenlaces del PIN llegan **tipados**, `SESSION_REQUIRED` **no** se confunde con ellos, y `setSessionPin` manda el actual y el nuevo |
| `utils/session.test.ts` | la matriz de `planSession` con el desenlace **`pin`** |
| `components/ProfileGate.test.tsx` | el paso de PIN: no deja enviar hasta tener 4 dígitos, filtra el tecleo, explica el PIN incorrecto y el freno, y **ofrece volver** |
| `utils/pin.test.ts` | la forma del PIN, espejo de la del backend |
| `hooks/useChat.test.tsx` | el arranque con PIN: no se abre a ciegas, el PIN correcto activa el perfil, el incorrecto **se explica**, y el selector también pide el PIN |

La migración tiene test propio **en las dos direcciones**: una BD **sin** la
columna recibe el `ALTER` y sus perfiles siguen entrando, y el hash **sobrevive**
a una ida y vuelta por el ZIP de backup (extrayendo la BD del archivo y
verificando el PIN contra ella).

---

## 7. Honestidad

1. **Esto NO cierra el P0 por defecto.** Un perfil **sin** PIN sigue entrando sin
   credencial. Es una mitigación que el dueño **activa**, y así hay que
   declararlo: el P0 queda cerrado **para los perfiles que la usan**, no para el
   producto.
2. **La pieza que carga el peso es el freno, no la longitud.** 4-6 dígitos son
   fuerza bruta trivial **sin** el freno de intentos.
3. **La cookie de un año significa un tecleo por navegador.** Protege ante *otro
   equipo sin la cookie*; **no** protege ante quien se sienta delante del tuyo, que
   es justo el caso frente al que una llave de este tamaño no puede hacer nada.
4. **No es autenticación de persona.** No hay recuperación ni identidad: quien
   olvide el PIN **no puede demostrar que es él**. Lo único honesto es declararlo.
5. **`GET /api/users` sigue enumerando nombres** (ahora con `has_pin`). Es la
   consecuencia declarada del producto sin cuentas, y no cambia con esta release.
6. **El hash viaja en el backup.** Es estado del perfil y vive **dentro de la BD**,
   así que va en el ZIP; `session.secret` (la clave de firma) **sigue sin viajar**,
   por la misma razón que `key.pem`. Es una decisión **declarada**, no un
   accidente, y tiene test.
7. **Provenance:** esta release **sí** mueve `VERSION` (`3.75.8` → `3.76.0`) y
   **sí** migra la BD, pero **no** toca ninguna versión pedagógica. Un mismo
   `LISTENING_BANK_VERSION` sigue nombrando dos contenidos servidos distintos desde
   V3.75.7; ese hueco ya está declarado allí y esta release no lo empeora.
8. **La evidencia documental del 401 cambia de forma.** `test_public_surface.py`
   gana la ruta nueva en un **test propio**, no en el diccionario `CON_SESION`:
   esa lista se recorre con `GET` y esta ruta responde **405**, no 401. Meterlas
   juntas habría debilitado el candado del otro lado sin avisar.
9. **El PIN entra DESPUÉS de congelar el árbol.** Cambiar el contrato de la API en
   medio de la campaña de validación habría invalidado cualquier `record` ya
   hecho. La identidad sellada en el kit (`v3.75.8` · `7134e538`, tag en
   `c858e88`) es la que hay que validar, y **los 7 gates siguen en `pending`**.
10. **El `dist` no se versiona** (`.gitignore`): hay que recompilar y reiniciar el
    backend para ver la UI nueva.

---

## 8. Archivos del diff de producto

### Backend

- `backend/repositories/db.py` — `pin_hash` en el `CREATE TABLE` y en el bloque
  idempotente de `ALTER TABLE`.
- `backend/repositories/users.py` — `_row_to_user` (deriva `has_pin` y **saca el
  hash** del diccionario), `get_pin_hash`, `set_pin_hash`.
- `backend/domain/users.py` — el par `get_pin_hash` / `set_pin_hash` en
  `run_in_threadpool`.
- `backend/services/pins.py` *(nuevo)* — PBKDF2, validación de forma y freno de
  intentos por perfil.
- `backend/schemas/users.py` — `User.has_pin`, `SessionCreate.pin`, `PinSet`.
- `backend/routers/session.py` — la puerta del PIN en `open_session` y
  `PUT /api/session/pin`.
- `backend/security.py` — `/api/session` en `_PATH_LIMITS` (120/min).

### Frontend

- `frontend/src/api/client.ts` — `ApiError` con `detail` y `Retry-After`.
- `frontend/src/api/session.ts` — `openSession(userId, pin?)`, `SessionPinError`,
  `setSessionPin`.
- `frontend/src/utils/session.ts` — el desenlace `pin` de `planSession`.
- `frontend/src/utils/pin.ts` *(nuevo)* — forma del PIN y `SetPinOutcome`.
- `frontend/src/types/api.ts` — `User.has_pin`.
- `frontend/src/hooks/useChat.ts` — `openProfile`, `pinPromptUserId`,
  `pinFeedback`, `pinRetryAfter`, `submitPin`, `cancelPin`, `setProfilePin`.
- `frontend/src/components/ProfileGate.tsx` — el paso de PIN.
- `frontend/src/components/SettingsDialog.tsx` — pestaña «PIN de este perfil».
- `frontend/src/App.tsx` — la puerta se muestra con un PIN pendiente aunque haya
  perfil activo.
- `frontend/src/utils/i18n.ts` — claves `pin.*` y `settings.pin.*`.

### Documentación

- `CHANGELOG.md`, `PLAN.md`, `README.md`, `release-notes-v3.76.0.md` *(nuevo)*,
  `docs/audit/PARKED.md`, `docs/audit/PLAN-P0-IDENTIDAD.md`,
  `docs/audit/KIT-VALIDACION-GATES.md`, `docs/RELEVO.md`.

### Artefactos regenerados

- `docs/audit/generated/release-validation.{json,md}`, `i18n-report.{json,md}`,
  `contrast-report.{json,md}` — regenerados por sus instrumentos.
- `docs/audit/generated/` — los **9 dossiers de G7** verificados **sin diff**.
