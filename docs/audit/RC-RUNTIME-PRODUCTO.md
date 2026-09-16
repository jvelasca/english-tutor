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

### RC-01 — El runtime de producto es el de desarrollo (P2, **declarado**)

Lo que hay, medido:

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

**Declaración (no defecto abierto):** hoy el producto son **dos procesos
arrancados por el launcher**, y el de la UI es un servidor que su propio
fabricante declara para desarrollo (sin minificar, sin caché HTTP, con HMR y
websocket de recarga). Consecuencia que el proyecto no declaraba en ninguna
parte: **Node + npm son requisito de EJECUCIÓN del producto**, no solo de
compilación.

Por la **decisión A** del briefing, esto **se declara y no se implementa**: no
hay bloqueo duro medido (el producto funciona así y es como se usa a diario), y
añadir el servido de `dist` en un incremento de verificación sería capacidad
nueva sin vector medido. Queda como **deuda con fase y condición de salida**:

- **se implementa** el servido de `frontend/dist` **si** (a) se decide que Node
  deje de ser requisito de ejecución (instalación limpia sin toolchain de JS), o
  (b) aparece un bloqueo duro (p. ej. el acceso desde móvil por la LAN depende de
  que el dev server siga vivo);
- **reevaluación:** V3.72/V3.73, junto con el eje RB (instalación limpia), que es
  donde la pregunta «¿qué necesita el usuario tener instalado?» se responde de
  verdad.

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

- **Cerrado:** RC-02 (sonda sin cota) y RC-03 (salud mentirosa en la UI).
- **Declarado con condición de salida:** RC-01 (Node como requisito de ejecución
  y el `dist` que nadie sirve), a reevaluar en V3.72/V3.73 con el eje RB.
- **Declarado sin cambio de código:** RC-04 (significado de `ready`).
- **La frontera de producto, en una frase:** hoy el producto es **un backend
  uvicorn de un solo proceso + un servidor de desarrollo de Vite**, los dos
  arrancados por el launcher, y la salud ya es honesta en las tres superficies
  que la consultan (backend `/ready`, launcher e indicador web).

## Deriva documental que este eje cierra

- `docs/PREMISAS.md` §3: declarar Node/npm como requisito de **ejecución** y que
  la UI la sirve el dev server de Vite (antes no se decía en ninguna parte).
- `docs/ARQUITECTURA.md`: quién sirve la UI y quién la API.
- Fixado por test en `backend/tests/test_docs_drift_v371.py` (clase RC), de modo
  que si alguien monta `frontend/dist` o cambia el comando del launcher, el test
  obliga a actualizar la declaración.
