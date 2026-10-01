# Release notes — English Tutor v3.79.0

**Fecha:** 2026-09-22 · **Tipo:** release **DE PRODUCTO** (patch) ·
**Versión de app:** `3.78.0 → 3.79.0`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el currículum (`CURRICULUM_VERSION` sigue
`1.3.1`), SIN tocar las evaluaciones y SIN tocar `LISTENING_BANK_VERSION`.** No
añade ni retira un gate: **G1–G7 siguen `pending`** y el árbol que se certifica
sigue siendo el de `v3.75.8`.

Cierra los **dos** fallos que el alumno reportó al usar el perfil. Ninguno era de
pintura, y en los dos **el mensaje que veía describía mal lo que pasaba**: uno
decía «el servidor local está saturado» cuando el servidor estaba ocioso, y el
otro no decía nada porque el asa de cerrar se había ido de la pantalla.

---

## 1. Qué publica

### (A) La baja fallaba por un bug del rate limiter, no por saturación

El síntoma exacto: pulsar **«Pedir dar de baja mi perfil»** devolvía en rojo
«El servidor local está saturado: espera unos segundos e inténtalo de nuevo», y
volver a intentarlo no arreglaba nada.

En `backend/security.py`, `_clients` guardaba **una sola cola por equipo** y la
comparaba contra el cupo de **la ruta concreta**:

```python
queue = _clients[host]          # TODAS las rutas del equipo comparten cola
if len(queue) >= limit:         # limit = 5 para /api/profile-requests
```

`/api/profile-requests` tiene **5/min**, y su comentario lo dice: es un tope
antibarrido para la única escritura de la app que **no** exige sesión. Pero como
la cola era compartida, cualquier ráfaga de cinco peticiones a rutas **ajenas**
—abrir el diccionario son varias— dejaba la cola por encima de 5 y el primer clic
en la baja recibía 429. **El cupo por ruta estaba midiendo el tráfico de todo el
equipo.** Los topes holgados (1200) no lo notaban nunca; los estrechos (5, 10, 20)
sí, y la baja era el único camino de un solo clic que caía bajo uno.

El arreglo tiene tres piezas, y las tres importan:

| Pieza | Por qué |
| --- | --- |
| La ventana se parte por **`(host, clase de ruta)`** | Cada cupo cuenta **solo lo suyo**, que es lo que su comentario prometía desde V3.77 |
| Se elige el **prefijo más largo** que casa, no el primero | Con `break` en el primer acierto, que `/api/profile-requests` sea prefijo de `/api/profile-requests/delete` convertía **el orden de escritura** de `_PATH_LIMITS` en una trampa silenciosa |
| La baja gana **cupo propio (30/min)** | Es una escritura autenticada, idempotente y de un solo clic; no puede medirse con la vara de una ruta **sin** sesión |

`rate_limit_snapshot` y `/api/system/status` **no cambian de forma**.

### (B) El diálogo se recortaba por arriba, y la causa no era el CSS

El síntoma exacto: al editar un perfil, el cuadro de selección de icono y colores
se salía por arriba de la pantalla y el botón de cerrar quedaba inalcanzable.

**La causa raíz era de contención, no de medidas.** El diálogo se abre desde el
menú de usuario, que vive **dentro del `<header>`**, y ese header lleva
`backdrop-blur-xl`. En CSS, **`backdrop-filter` crea bloque contenedor para
`position: fixed`**: el `inset: 0` del backdrop dejaba de medir el viewport y
pasaba a medir **la franja del header** (~80 px en una ventana baja). El diálogo,
mucho más alto que esa franja, se recortaba por arriba; y el `autoFocus` del campo
de nombre desplazaba el contenedor para colmo, dejando la cabecera fuera del área
visible.

Medido en el navegador, con el CSS ya «arreglado» y sin el portal:

```
DIV.dialog-backdrop | pos=fixed | rect=0,0 520x76     ← 76 px, no 300
HEADER.sticky … | backdropFilter=blur(24px) | rect=0,0 520x77
```

El arreglo es montarlo con un **portal a `document.body`**, que es donde debe
estar un modal y donde lo ponen las apps que no tienen este problema.

**El CSS se endurece además por su cuenta**, y no es adorno: protege a los otros
**tres** diálogos que comparten clases (`ProfileGate`, `SettingsDialog` y
`VoiceDownloadDialog`, que sí se montan fuera del header).

```css
.dialog-backdrop { display: flex; padding: var(--space-4); overflow-y: auto;
                   overscroll-behavior: contain; }
.dialog { margin: auto; max-height: calc(100dvh - 2 * var(--space-4)); }
.dialog-body { overflow-y: auto; min-height: 0; }
```

- Fuera `align-items: center`: es lo que empujaba el borde superior fuera del
  área desplazable. El centrado lo da `margin: auto`, que **respeta** el scroll y
  deja el desbordamiento hacia abajo, que sí se alcanza.
- `dvh` con respaldo `vh`, en vez de `vh` a secas: en móvil `vh` mide el viewport
  con la barra del navegador **oculta**, así que `90vh` puede ser más alto que el
  área realmente visible.
- El scroll pasa al **cuerpo**, con cabecera y pie fijos (`flex-shrink: 0`) y
  `min-height: 0`: así el asa de cerrar no se va con el scroll ni las acciones
  («Cancelar»/«Guardar») quedan tras él.

### (C) La baja deja de quemar su propio cupo

Dos arreglos pequeños que, juntos, son el motivo de que el primer intento del
alumno importe:

- **`busy` de verdad.** El botón se deshabilitaba solo *después* del éxito, así
  que un segundo clic de impaciencia mandaba otra petición **justo cuando el
  backend pedía esperar**, gastando cupo en el peor momento. Ahora `submitDelete`
  marca `busy` con la petición en vuelo y el botón se deshabilita antes de salir.
- **Un 429 dice cuánto esperar.** `ApiError` ya exponía `retryAfterSeconds` y se
  estaba tirando: el alumno veía «saturado» y ahí se quedaba, sin poder distinguir
  «espera 5 s» de «algo se ha roto». Ahora el mensaje dice los segundos
  (`profile.deleteThrottled`), y si el backend no manda la cabecera cae al aviso
  genérico —con el hueco ya sustituido, no un `{n}` en crudo—.

---

## 2. La comprobación que importa: que los candados muerdan

Los cuatro candados se comprobaron **revirtiendo el código**, no razonando sobre
él. Los cuatro mordieron, y después se restauró y se comprobó que la suite queda
verde.

**(A) La cola compartida.** Devuelto `_clients[host]` con el cupo de la ruta:

```
FAILED tests/test_security.py::test_una_ruta_no_gasta_el_cupo_de_otra
AssertionError: assert 429 == 200
```

Es **literalmente** el fallo del alumno: seis peticiones normales y la baja
devolviendo 429.

**(B) El portal.** Quitado `createPortal`:

```
AssertionError: expected <div class="app-header-stub" …> to be <body>…
FAIL  se monta fuera del header, que es lo que hacía inalcanzable su cabecera
```

y en el navegador el spec de cota vuelve a fallar con `Expected: >= 0`,
`Received: -186`.

**(C) El estado `busy`.** Quitados el guardia y el `disabled`:

```
AssertionError: expected "vi.fn()" to be called 1 times, but got 3 times
```

**(D) El CSS.** Devuelto `align-items: center` al backdrop:

```
FAIL  NO centra con align-items: es lo que empujaba el borde fuera de la pantalla
```

---

## 3. Verificación

| Instrumento | Resultado |
| --- | --- |
| `pytest` (backend) | **2992/2992** |
| `ruff check .` (backend) | limpio |
| `scripts.transfer_validation` | `OK=True` |
| `tsc --noEmit` | limpio |
| `vitest run` | **948/948** (108 ficheros) |
| `npm run build` | correcto (`package.json` en `3.79.0`) |
| i18n `--strict` | **1680** cadenas · **0 huérfanas / 0 usadas sin definir / 0 duplicadas** |
| contraste `--strict` | 480 pares (+6 guardas) · **0 bloqueantes** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.79.0`) |
| `validation_gate.py auto` | **10/10** |
| `pytest` (launcher) | **205/205** + `ruff` limpio |
| `Playwright` (visual) | `profileDialog` **2/2 en los tres proyectos** (desktop, tablet, móvil) |

Tests nuevos: `backend/tests/test_security.py` (**4**),
`frontend/src/components/ProfileDialog.test.tsx` (**5**),
`frontend/src/styles/dialogLayout.test.ts` (**4**) y
`frontend/tests/visual/profileDialog.spec.ts` (**2** × 3 proyectos).

---

## 4. Honestidad

1. **La causa del recorte no era la que el plan suponía, y conviene decirlo.** El
   plan lo atribuía a `align-items: center` + `max-height: 90vh`. Eso era
   fragilidad **real** y está arreglado, pero **no** era la causa: el recorte lo
   producía el `backdrop-filter` del header creando bloque contenedor. Sin el
   portal, el CSS «arreglado» seguía recortando el diálogo (medido: `y = -186`).
   Por eso hay **dos** candados, uno por cada mitad.
2. **El candado del CSS es de FUENTE, no de píxeles, y no puede ser otra cosa.**
   En el Chrome de escritorio `vh == dvh`, así que un test de navegador **no
   puede** reproducir el recorte de la barra de un móvil. El spec de Playwright
   fija la **cota** —a un viewport de 520×300, el diálogo nunca sobresale y el asa
   de cerrar es clicable—, y la invariante se fija leyendo el archivo
   (`dialogLayout.test.ts`), igual que el backend fija
   `test_path_limits_match_real_routes` leyendo su diccionario.
3. **El portal cambia dónde vive el diálogo en el DOM.** Pasa de ser hijo del menú
   de usuario a ser hijo directo de `<body>`. Es un cambio de **estructura**, no de
   pintura, y cualquier test o estilo que lo buscara por contenedor tiene que usar
   `document`. Se declara porque es exactamente el tipo de detalle que rompe cosas
   en silencio.
4. **Los otros tres diálogos NO se portalan.** No cuelgan del header y no sufren el
   problema; el CSS arreglado los cubre. Pero la trampa sigue ahí: si alguien monta
   un diálogo nuevo dentro del `<header>`, el recorte vuelve a aparecer, y hoy no
   hay ninguna comprobación que impida montarlo ahí.
5. **El `busy` protege de la impaciencia, no del doble envío real.** Deshabilita el
   botón mientras la promesa está en vuelo, y con eso basta para el caso del clic
   repetido; no es una clave de idempotencia en el servidor. La baja **sí** es
   idempotente por otra vía —un 409 se cuenta como «ya pedida»—, pero eso es otro
   mecanismo y conviene no confundirlos.
6. **El cupo de la baja (30/min) es holgado a propósito, no una medida de
   seguridad.** Es una escritura autenticada de un clic: su función es que el
   servidor no reciba una tormenta, no defender nada. La defensa de la cola sigue
   donde estaba —los 5/min de `/api/profile-requests` sin sesión y el tope de
   pendientes—, y este cambio **no** los toca. Se añadió un candado para que
   aflojar el de la baja no afloje el de la ruta hermana.
7. **Queda flakiness local preexistente en el barrido visual, y no es de esta
   release.** Con el backend apagado, el conjunto de specs de desktop que falla
   **cambia de una ejecución a otra** (8 fallos en un run, 5 en el siguiente, 13
   antes de empezar) y las mismas specs **pasan en aislamiento sobre un árbol
   limpio** (comprobado con `git stash`). La autoridad es el CI, que corre el
   barrido entero. Lo que sí se verificó aquí es que **ninguna** de esas specs
   toca el diálogo y que las 6 nuevas pasan en los tres proyectos.
8. **`grep` de `backdrop-filter` no es una comprobación.** Nada garantiza hoy que
   ningún otro `position: fixed` de la app esté viviendo dentro de un ancestro con
   `transform`/`filter`/`backdrop-filter`/`contain`/`will-change`. Los diálogos que
   se montan en `App.tsx` se revisaron a mano y están fuera; un candado general
   sería caro y no se ha hecho.
9. **Los 7 gates siguen en `pending`** y el árbol que se certifica sigue siendo el
   de `v3.75.8`. Esta release no toca gates.
