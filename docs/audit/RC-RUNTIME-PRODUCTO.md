# RC — Runtime de producto y salud honesta (V3.71)

> **Tipo:** dossier de evidencia **interno** (no es un informe de auditoría
> externa). Por eso **no lleva letra**: `Z` y `Z2` siguen reservadas a los
> informes externos pendientes de V3.69
> (`agentes/auditoria-externa-v369-seguimiento.md`).
> **Eje auditado:** **RC** («¿el runtime de producto es el de desarrollo, y la UI
> dice la verdad sobre su estado?») del briefing
> `agentes/v371-runtime-offline-instalacion.md` §C.
> **Punto de partida:** `v3.70.0` (`9ba9c49`) + eje RE (`2c07fe0`) + eje RA
> (`fdefb2c`) + eje RD (`b8d2ac4`).
> **Autor:** el propio proyecto.
> **Fecha:** 2026-09-16.

## Alcance

- **Se audita** el **runtime que se ejecuta de verdad** cuando alguien abre la
  app, que son cuatro preguntas separadas:
  1. qué servidor sirve la UI y qué servidor sirve la API;
  2. si existe un artefacto de producción (`frontend/dist`) y quién lo sirve;
  3. si la **salud que la UI muestra** es la real;
  4. si esa salud se responde **dentro del presupuesto de quien la consulta**.
- **Se cierra:** la mentira del indicador de cabecera (**RC-03**) y la sonda de
  Ollama sin cota que disfrazaba un Ollama lento de backend caído (**RC-02**).
- **Se declara con condición de salida:** Node como **requisito de ejecución** y
  el `dist` que nadie sirve (**RC-01**), por la **decisión A** del briefing
  («medir y declarar; implementar solo si hay bloqueo duro»).
- **No se audita:** la instalación limpia (RB), la síntesis (RF) ni las
  dependencias de red (RA, ya entregado).

## Método

1. **Medir antes de tocar.** Cada afirmación se comprueba contra el código y
   contra el comportamiento observable, no contra lo que el proyecto declara.
2. **Endurecimiento mínimo.** Solo se cambia lo que cierra un vector medido, con
   **test que falla sin el cambio**. Nada de refactor.
3. **Re-declarar con fase lo que no se cierra**, en lugar de cerrarlo en falso.

## Evidencia

### RC-01 — El runtime de producto es el de desarrollo (P2, **CERRADO en V3.72**)

Lo que había, medido (árbol `v3.71.0`):

| Pieza | Comando real | Dónde |
|---|---|---|
| API | `<backend>/.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000` | `launcher/core.py:38-54` |
| UI | `npm run dev` → **Vite dev server** | `launcher/core.py:57-60` |
| Build de producción | `tsc && vite build` (existe) | `frontend/package.json:8` |
| Quién sirve `frontend/dist` | **nadie** | — |

Hechos que sostienen la última fila:

- El backend **no monta** `frontend/dist`: no hay `StaticFiles` ni
  `FileResponse` en ningún sitio de `backend/` (`grep` completo).
- `frontend/dist` no se versiona (`frontend/.gitignore`), así que en un clon
  limpio **ni siquiera existe** hasta que alguien lo construya — y construirlo no
  cambia nada, porque nadie lo sirve.

**Declaración (no defecto abierto en V3.71):** hoy el producto son **dos procesos
arrancados por el launcher**, y el de la UI es un servidor que su propio
fabricante declara para desarrollo (sin minificar, sin caché HTTP, con HMR y
websocket de recarga). Consecuencia que el proyecto no declaraba en ninguna
parte: **Node + npm son requisito de EJECUCIÓN del producto**, no solo de
compilación.

Por la **decisión A** del briefing de V3.71, esto **se declaró y no se
implementó**: no había bloqueo duro medido. Quedó como **deuda con fase y
condición de salida** con **reevaluación en V3.72** — y en V3.72 se cerró (abajo).

#### Cierre (V3.72, eje UA — 2026-09-17)

La condición de salida era: *«se implementa el servido de `frontend/dist` si (a)
se decide que Node deje de ser requisito de ejecución»*. **La decisión se tomó
(Decisión A del briefing `agentes/v372-ux-product-completion.md`) y se
implementó**, con un motivo además del higiénico: el acceso desde la LAN necesita
**HTTPS** para que el navegador exponga `navigator.mediaDevices` (micrófono), y
servir la UI desde el propio backend da **un único origen** con el TLS bajo
control del proyecto.

Lo que hay ahora, medido:

| Pieza | Comando real | Dónde |
|---|---|---|
| API + UI | `uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-certfile … --ssl-keyfile …` | `launcher/core.py::backend_command` |
| UI compilada | `StaticFiles /assets` + *fallback* SPA (*fail-open*) | `backend/services/frontend_dist.py::mount_frontend` |
| Certificado TLS | Generado (idempotente, con SANs de LAN) antes de arrancar | `backend/scripts/ensure_tls_cert.py` |
| Build del artefacto | `npm run build` **solo si falta** `frontend/dist` | `launcher/process_manager.py::ensure_frontend_dist` |

> **Corrección de deriva (V3.73.x).** La fila «API + UI» ya no es exacta: el
> `--host` **no** es siempre `0.0.0.0`. Desde V3.73.x el launcher enlaza a
> `127.0.0.1` salvo que el **modo LAN** esté declarado (`ENGLISH_TUTOR_LAN=1`), y
> el modo viaja al backend en su entorno desde la misma decisión. La tabla de
> arriba se deja como la midió este dossier (árbol `v3.72.0`): es la medición de
> su momento, no el contrato vigente. La frontera vigente está en
> `docs/ARQUITECTURA.md` → «Frontera de red: loopback por defecto, LAN opt-in».

- **Node deja de ser requisito de EJECUCIÓN**: pasa a ser requisito de
  **COMPILACIÓN** (la primera vez que se instala). Es la afirmación honesta: sin
  Node no hay `dist`, pero con el `dist` construido la app arranca sin Node.
- `npm run dev` (Vite en `:5173`) se conserva como **modo de desarrollo** con HMR
  (proxy `/api`), no como runtime de producto.
- El montaje es **fail-open en desarrollo**: sin `dist` el backend arranca igual
  (solo API) si se lanza a mano (`uvicorn main:app`).
- **V3.73 — fail-closed en producto (cierre del P2 de la auditoría externa):** el
  launcher arranca el backend con `ENGLISH_TUTOR_REQUIRE_UI=1` y (a) **no lo
  arranca** si falta `frontend/dist/index.html` (`ProcessManager.start_backend`
  eleva `PreparationError`) y (b) con la variable activa, la falta del artefacto
  es un `RuntimeError` accionable en `mount_frontend` (dice `npm run build`), no
  una app que parece lista y se ve vacía. Un `uvicorn main:app` manual sigue
  siendo fail-open a propósito: es el modo desarrollo.
- Firewall: solo se abre el **8000** (`launcher/allow-firewall.ps1`); el puerto de
  la UI anunciada por `/api/network` (y el QR de `ConnectDeviceCard`) es el mismo.
- **La ruta raíz de la API (`GET /`) se movió a `GET /api`** (`routers/models.py`):
  `/` lo sirve ahora la UI. El `/api` sin ruta sigue siendo 404 real (el
  *fallback* no enmascara endpoints inexistentes).

**Tests que lo fijan:** `backend/tests/test_serve_frontend_v372.py` (14),
`test_serve_frontend_v373.py` (fail-closed de producto),
`launcher/tests/test_preflight_v373.py` (la otra mitad, en el launcher),
`test_tls_cert_v372.py` (14), `test_docs_drift_v372.py`,
`test_docs_drift_v373.py`, y los actualizados de `launcher/tests/`
(`test_core`, `test_process_manager`, `test_status`) y
`backend/tests/test_network.py`/`test_cors.py`/`test_security.py`.

**Honestidad del cierre:** queda fuera el **progreso de descarga real** y el
empaquetado (no hay instalador). La frase «Node no es requisito de ejecución» es
correcta solo **después** de haber compilado el artefacto al menos una vez, y por
eso V3.73 hace que su ausencia sea un **fallo explícito** en el runtime de
producto en vez de un arranque silencioso sin interfaz.

### RC-02 — La sonda de Ollama no tenía cota y el launcher solo espera 1,5 s (P2, **cerrado**)

Cadena medida:

- `launcher/status.py` → `_get_json(url, timeout=1.5)`: **todo** lo que el
  launcher pregunta al backend caduca en **1,5 s**.
- `launcher/launcher.py:1006` y `:1045` → `backend_up = fetch_health() is not None`,
  y `fetch_health()` es `GET /api/health/dependencies`.
- `backend/routers/health.py` → `_dependencies()` incluye `await llm.ping()`.
- `backend/services/llm.py` → `ping()` hacía `await get_client().list()` **sin
  timeout** (el cliente se construye sin `timeout`, y `list()` no lo lleva).

**Modo de fallo (deducido de la cadena, no hipotético):** con Ollama **cargando
un modelo** —el caso normal justo después de arrancar— `list()` puede tardar más
de 1,5 s. Entonces `fetch_health()` devuelve `None`, el launcher concluye «el
backend no está vivo» y llama a `start_backend()` sobre un backend que ya
escucha → **puerto ocupado**. Es decir: **un Ollama lento se disfrazaba de
backend caído.**

El matiz importa y acota el fallo: con Ollama **apagado** la sonda falla en
seguida (conexión rechazada), el JSON llega igual y el launcher no se equivoca.
El fallo es específicamente del Ollama **lento**, que es el de la puesta en
marcha.

**Cierre:** `LLM_PING_TIMEOUT_SECONDS = 1.0` aplicado con `asyncio.wait_for`, de
modo que la sonda cabe con holgura en los 1,5 s del launcher. No se toca el
cliente de chat, que sí necesita generaciones largas.

**Tests que lo fijan** (`backend/tests/test_health.py`):

- `test_el_timeout_del_sondeo_cabe_en_el_que_espera_el_launcher` — 0 < 1,0 < 1,5.
- `test_ping_devuelve_false_si_ollama_no_contesta_a_tiempo` — un cliente que
  duerme 5 s devuelve `False` en vez de colgarse.
- `test_ping_devuelve_true_cuando_ollama_contesta`.

### RC-03 — La UI mentía sobre su estado (P2, **cerrado**)

- El indicador de cabecera (`ConnectionIndicator`, visible **siempre**) preguntaba
  a `/api/health`, que responde **200 siempre que el proceso esté vivo**.
- Con Ollama, la base de datos, el STT o el TTS caídos seguía en verde dicendo
  «Conectado»: la app **no podía dar clase** y la UI afirmaba que sí.
- Lo llamativo es que la verdad **ya estaba en el proyecto** y a un clic: el
  popover (`SystemStatus`) muestra el detalle por dependencia, y el **launcher ya
  preguntaba a `/api/health/dependencies`** (la dependencia honesta, la misma que
  gatea `/ready` con 503). La mentira era solo del titular del frontend.

**Cierre:** `connectionState()` en `frontend/src/api/health.ts` — función pura
que resume `CORE_DEPENDENCIES = {database, ollama, stt, tts}` (exactamente las
cuatro que gatean `/api/health/ready`) — y **tres** estados en el indicador:

| Estado | Cuándo | Punto |
|---|---|---|
| Conectado | las cuatro dependencias clave en `ok`/`ready` | verde |
| **Degradado** | la API responde y alguna clave no | ámbar |
| Desconectado | las dependencias no se pueden leer | rojo |

`status-dot--warn` **ya existía** en la hoja de estilos: solo faltaba la etiqueta
`status.degraded` (es/en). El estado «degradado» es nuevo para el usuario: antes
ese caso se mostraba como «Conectado».

**Tests que lo fijan** (`frontend/src/components/ConnectionIndicator.test.tsx`,
5 casos): Conectado, **Degradado cuando la API responde pero una dependencia
falla**, Desconectado cuando no se pueden leer, «no declara degradación por la
biblioteca de audio» (ver RC-04) y el popover.

### RC-04 — `ready` informa de la biblioteca de audio pero no la exige (P3, **declarado**)

`/api/health/dependencies` devuelve `audio_library`, pero `/api/health/ready` no
la incluye en su condición. **Es correcto por diseño** —el corpus de audio humano
es opcional porque el proyecto usa TTS (`docs/audit/PARKED.md`)—, pero el nombre
`ready` no lo dice, y un operador puede leer «ready» como «todo el catálogo
está». Se declara el significado sin cambiar código:

> `ready` = «la app puede dar clase» (BD + LLM + STT + TTS), **no** «todo
> está disponible».

El frontend ya lo refleja: `audio_library` está fuera de `CORE_DEPENDENCIES`, con
test que impide que entre por descuido.

### RC-05 — Lo que ya estaba bien (verificado, sin cambio)

- **`ADMIN_PIN` fail-closed**: sin PIN configurado, `/api/admin/*` responde 401
  «Administración deshabilitada» — no se abre por defecto.
- **El backend no arranca en modo dev**: `uvicorn` **sin** `--reload`, un solo
  proceso.
- **Ligado a la LAN** (`0.0.0.0`) pero con CORS restringido a localhost + IPs
  privadas, middleware de origen (CSRF) y rate limiting.
- **El launcher ya usaba la dependencia honesta**, no `/api/health`.

## Resultado

- **Cerrado:** RC-02 (sonda sin cota), RC-03 (salud mentirosa en la UI) y **RC-01
  (runtime de producto: Node como requisito de ejecución y el `dist` que nadie
  servía — cerrado en V3.72, eje UA)**.
- **Declarado sin cambio de código:** RC-04 (significado de `ready`).
- **V3.73 — endurecimiento del cierre de RC-01:** el montaje del artefacto pasa a
  ser **fail-closed en producto** (el launcher lo exige y no arranca sin él) y
  sigue siendo fail-open en desarrollo. Es lo que faltaba para que «Node no es
  requisito de ejecución» no se pueda leer como «el producto puede arrancar sin
  interfaz».
- **La frontera de producto, en una frase:** el producto es **un solo backend
  uvicorn que sirve la API y la UI compilada por HTTPS en `:8000`**, arrancado por
  el launcher; Node solo hace falta para **compilar** el artefacto, y la salud es
  honesta en las tres superficies que la consultan (backend `/ready`, launcher e
  indicador web). **Sin el artefacto, el producto no arranca** (V3.73).

## Deriva documental que este eje cierra

- `docs/PREMISAS.md` §3: V3.71 declaró Node/npm como requisito de **ejecución**;
  **V3.72 lo re-declara** como requisito de **compilación** y documenta el servido
  de `frontend/dist` desde el backend.
- `docs/ARQUITECTURA.md`: quién sirve la UI y quién la API (re-declarado en V3.72:
  un solo proceso, un solo origen HTTPS).
- `README.md`: arranque manual re-escrito (compilar + `ensure_tls_cert` + uvicorn
  con `--ssl-*`) y requisitos corregidos.
- Fijado por test: `backend/tests/test_docs_drift_v371.py` fijó **la declaración
  de V3.71**; su parte RC se sustituyó por `backend/tests/test_docs_drift_v372.py`
  (nueva frontera), de modo que el candado sigue vivo apuntando a la verdad actual.
