# Briefing de subagente — V3.71 (Runtime real, offline verificado e instalación limpia)

> **Estado:** **PROPUESTO** (2026-09-16). Pendiente del **visto bueno del gerente**
> en las decisiones de alcance marcadas ⚠️ antes de arrancar (§Decisiones).
> **Qué es:** la release del **runtime de producto**, no del motor. Tras V3.69
> (validación del motor adaptativo) y V3.70 (medición de la pedagogía), el
> eslabón que **nadie ha auditado todavía** es el que hace que el tutor exista en
> una máquina real: **arrancar, instalar, funcionar sin Internet**. La auditoría
> `Y` §22 es explícita: *«No basta con que «normalmente» funcione offline»*.
> **Qué cierra:** lo que la auditoría `X` §18 asignó a **«V3.71 — Offline /
> Runtime / Installation»** (`docs/audit/X-AUDITORIA-TOTAL-V367.md:363-369`) y la
> confirmación de la `Y` §22 (`docs/audit/Y-AUDITORIA-TOTAL-V368.md:430-435`):
> producto 100 % local **sin dependencia accidental de Internet**; instalación
> limpia, BD vacía, primer usuario, descarga de modelos, arranque, micrófono, TTS,
> STT, LAN, HTTPS y móvil.
> **Qué NO cierra (deuda declarada):** **los 6 P2 de la auditoría de V3.69**, los
> **33 hallazgos de V3.70** (asignados a V4.0.x / Planner 4.0 / V3.72), la
> **matriz de dispositivos** (prueba en hardware, `docs/DEVICE_MATRIX.md`), la
> **variabilidad LLM de speaking** con Ollama real y **Planner 4.0**.
> **Auditoría/roadmap que lo motivan:** auditoría `X` §18 (roadmap
> `docs/audit/X-AUDITORIA-TOTAL-V367.md:328-336`), auditoría `Y` §22 y §«riesgo
> mayor» (el riesgo nº 3 es «que el funcionamiento 100 % offline tenga alguna
> dependencia oculta»), y `PLAN.md:1490-1500`.
> **Regla dura declarada:** *V3.71 es una release de **VERIFICACIÓN** del runtime
> real, con **endurecimiento mínimo** solo donde la verificación demuestre un
> bloqueo duro.* Todo cambio de producto debe (i) estar **forzado por un fallo
> medido**, (ii) quedar **pinneado por un test** (premisa 12) y (iii) **no añadir
> capacidad pedagógica**. No se toca el motor adaptativo, ni el banco, ni el
> currículum, ni `DECISION_POLICY_VERSION`/`GENERATOR_VERSION`.
> **Ejes:** **RA→RF** (ver §Diseño), ejecutados **un subagente a la vez**.
> **Entrega:** informe de verificación reproducible (`docs/audit/RA…RF`), un
> **instrumento de medición de runtime de solo lectura** nuevo, el **runbook de
> instalación limpia**, los **tests** que fijan cada hallazgo y las correcciones
> **mínimas** declaradas.
> **Base de partida:** árbol `v3.70.0` (commit `9ba9c49`, tag anotado `v3.70.0`;
> CI 6/6 run [35062382562](https://github.com/jvelasca/english-tutor/actions/runs/35062382562)).
> **Auditoría externa:** punto de entrada de la **release de V3.70** en
> `agentes/auditoria-externa-release-v370.md` (informe esperado
> `docs/audit/AG-AUDITORIA-RELEASE-V370.md`). Los informes **`Z`/`Z2` de V3.69
> siguen sin recibir** (`agentes/auditoria-externa-v369-seguimiento.md`).

## Rol

**Auditor de runtime y plataforma.** Verificar, medir y —solo si es
imprescindible— **endurecer mínimamente** el arranque, la instalación y el
funcionamiento offline de la app en una **máquina limpia**; producir un
instrumento de medición de runtime **de solo lectura**, corregir las **derivas
documentales ya detectadas** y añadir al **CI** lo que hoy solo se prueba en
local. Sin migración destructiva, sin bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, sin tocar el banco ni el currículum y sin umbrales
pedagógicos nuevos.

## Objetivo

Convertir «la app funciona en mi máquina de desarrollo» en «**la app se instala
desde cero, arranca y funciona con Internet desconectado, y está medido**», y
dejar por escrito y **con evidencia reproducible** qué partes del runtime son de
**desarrollo** y cuáles de **producto**. Es la antesala obligatoria de V3.72 (UX)
y V3.73 (auditoría final técnica).

## Estado de partida verificado (árbol `v3.70.0`)

> Verificado por lectura de código (`archivo:línea`), **sin ejecutar** una
> máquina limpia todavía: esa ejecución es precisamente el objeto de V3.71.

### Runtime real = runtime de DESARROLLO (hallazgo central)

| Hecho | Evidencia |
|---|---|
| El launcher arranca el backend con `uvicorn ... --host 0.0.0.0 --port 8000` | `launcher/core.py:38-55` |
| El launcher arranca el frontend con **`npm run dev`** (Vite dev server) | `launcher/core.py:57-60` |
| **El ejecutable Python es una ruta fija dentro del repo** (`backend/.venv/Scripts/python.exe`), con nombre por `os.name` pero **`Scripts/` también en POSIX** | `launcher/core.py:43-44,59` |
| El frontend se sirve por **HTTPS autofirmado** (necesario para `getUserMedia` en móvil) | `frontend/vite.config.ts:9-21,26-36` |
| `frontend/dist` **se construye en CI** pero **nadie lo sirve** (no hay `StaticFiles` en `backend/main.py`) | `.github/workflows/ci.yml:53-54`; `backend/main.py:135-162` |
| El doble montaje de `StrictMode` del dev server **ocurre en el producto** (§F-1 de V3.69) | `release-notes-v3.69.0.md:119`; `frontend/src/main.tsx:1-9` |

### Offline: premisa declarada, no capacidad verificada

| Hecho | Evidencia |
|---|---|
| Principio rector: «100 % local», con **única excepción**: la descarga inicial | `docs/PREMISAS.md:11-16` |
| Mandato de verificación: probar con **Internet desconectado** 12 flujos | `docs/audit/Y-AUDITORIA-TOTAL-V368.md:430-435` |
| `download_models.py` solo baja **Whisper + Piper**; **Ollama no se bootstrapea** (`ollama pull` es manual) | `backend/download_models.py:54-62`; `agentes/m5-modelo-conversacional.md:20` |
| La salud que consume el frontend es `/api/health`, que **responde 200 sin comprobar nada** | `backend/routers/health.py:12-16`; `frontend/src/components/ConnectionIndicator.tsx:7,28-32` |
| El **503 real** vive en `/api/health/ready` (BD/Ollama/STT/TTS) y **el frontend no lo consume** | `backend/routers/health.py:44-58` |
| Descargas sin **checksum** ni tamaño esperado (solo `.part` atómico + timeout 300 s) | `backend/services/voice_downloads.py:113-125` |
| El servidor arranca **aunque falten** Ollama/Whisper/Piper (el `lifespan` solo hace `init_db()`) | `backend/main.py:68-70` |
| Estado de producto «Offline» = 🟡 en los mapas de deuda de `X` y `Y` | `docs/audit/X-AUDITORIA-TOTAL-V367.md:412`; `docs/audit/Y-AUDITORIA-TOTAL-V368.md:479` |

### Instalación / distribución

| Hecho | Evidencia |
|---|---|
| Instalación **manual y de desarrollador** (venv + `requirements.txt` + `download_models.py` + `npm install`) | `README.md:144-189`; `docs/DESARROLLO.md:5-43` |
| **No** hay script de bootstrap de máquina limpia | no existen `scripts/install*`/`bootstrap*` |
| Requisitos declarados: Ollama corriendo, Python 3.11+, Node 18+ | `README.md:186-189` |
| **No** hay `.env`/`.env.example` y el backend **no lee** `os.environ` | `.gitignore:11`; `backend/config.py` (todo constantes) |
| `ADMIN_PIN = ""` ⇒ **fail-closed**: restore administrativo deshabilitado, sin UI/entorno para fijarlo | `backend/config.py:55-60`; `backend/routers/system.py:110-128` |
| **No** hay empaquetado (0 hits de Docker/PyInstaller/Electron/Tauri/instalador) y **el contenedor está vetado** | `docs/PLAN-ENDURECIMIENTO.md:242` |
| **No** hay versión de esquema de BD (`PRAGMA user_version`) ni ruta de downgrade | `backend/repositories/db.py:37-44,813-872` |
| `.gitignore` deja fuera **modelos, BD, logs y estado del launcher** (artefactos de máquina, sin manifiesto) | `.gitignore:13-17` |
| Rutas/scripts **solo Windows**: `install_shortcut.ps1`, `allow-firewall.ps1`, `make_icon.ps1`, `taskkill` | `launcher/make_icon.ps1:1-2`; `launcher/install_shortcut.ps1:1-2`; `launcher/process_manager.py:14-17` |

### Launcher: existe, está probado… pero **no en el CI**

| Hecho | Evidencia |
|---|---|
| GUI `tkinter` que arranca/para backend + frontend, muestra estado, BD y logs | `launcher/launcher.py:1-14`; `docs/ARQUITECTURA.md:279-306` |
| **75 tests** (20 core · 17 status · 20 browser_cookies · 11 ui · 5 state_store · 2 process_manager) | `launcher/tests/` |
| **Ningún job de CI ejecuta el launcher** (los 6 jobs son backend, frontend, release-consistency, beta-v3, content-validation, playwright) | `.github/workflows/ci.yml:7,33,56,66,88,107` |
| Estado que muestra: `/api/health/dependencies`, `/api/health`, `/api/system/status`, GET al frontend, SQLite **read-only** | `launcher/status.py:22-79` |
| Timeout HTTP del launcher: **1,5 s** (el backend documenta que un modelo saturado encola) | `launcher/status.py:14`; `backend/security.py:12-16` |

### Derivas documentales ya detectadas (huecos medibles)

| Deriva | Evidencia |
|---|---|
| El árbol del launcher en `ARQUITECTURA.md` **no refleja** `browser_cookies.py`, `state_store.py` ni `allow-firewall.ps1` | `docs/ARQUITECTURA.md:281-291` vs `launcher/` |
| **Modelo por defecto contradictorio**: el código fija `llama3.1:8b` y **prohíbe** `qwen3.5:9b`, mientras `PREMISAS.md`/`README.md` dicen lo contrario | `backend/config.py:10,18` vs `docs/PREMISAS.md:20` y `README.md:267-270` |
| `BETA_GATES.md` declara ✅ «Launcher de escritorio», «CI completa» y «Matriz de dispositivos» | `docs/BETA_GATES.md:24,26,98` |
| …pero el launcher **no está en CI** y la **matriz está 10/10 sin ejecutar** | `ci.yml:7-126`; `docs/DEVICE_MATRIX.md:30-42` |
| `BETA_GATES.md` está fechado «2026-08-31 · Versión: `2.0.0`» | `docs/BETA_GATES.md:6` |
| Deuda **TTS/offline** (auto-descarga implícita: timeout, UI y degradación) diferida **4 veces** sin cierre explícito | `release-notes-v3.47.0.md:110-113`; `release-notes-v3.48.0.md:97`; `CHANGELOG.md:439,453` |

### Restricciones de proceso aplicables

- **Premisa 5**: briefing autocontenido en `agentes/`; **un cambio a la vez**
  (premisa 6).
- **Premisa 12**: toda la app con tests, y los tests deben ser **rápidos y
  deterministas** — **tensión directa** con «probar offline» y «primer arranque
  con descargas»: V3.71 debe **separar** el test automático (con dobles/`monkeypatch`)
  de la **prueba manual documentada** (runbook reproducible, sin red real en CI).
- **Premisa 17**: la Ayuda enlaza a `docs/` y debe servir al usuario **no
  ingeniero**.
- **Premisa 21**: la IA produce evidencia; **el motor determinista decide** (nada
  de un LLM en una ruta nueva de runtime).
- **Gate real**: `scripts/check_release_consistency.py` (primera coincidencia →
  insertar arriba).

## Decisiones de alcance

> Las **⚠️** requieren el **visto bueno del gerente** antes de arrancar. El resto
> se dan por cerradas como recomendación de este briefing.

1. **Solo verificación + endurecimiento mínimo.** No se añade capacidad
   pedagógica; todo cambio de producto se justifica por un fallo **medido** y se
   fija con test.
2. **⚠️ Decisión A — runtime de producto.** ¿Se **sirve `frontend/dist`** desde
   el backend (`StaticFiles`) para que el runtime de producto no dependa de
   `npm run dev`/Node, o se **declara la frontera** (el producto requiere Node y
   se documenta) y se deja el cambio para V3.72? **Recomendación:** *medir y
   declarar* en V3.71; implementar el servido de `dist` solo si la verificación
   demuestra que es **bloqueo duro** de instalación (probable candidato a
   V3.72/V4.0 por riesgo de romper el flujo de desarrollo y el launcher).
3. **⚠️ Decisión B — `ollama pull` en el bootstrap.** ¿El bootstrap **descarga el
   modelo por defecto** (requiere red, primera ejecución) o **verifica y guía**
   sin descargar? **Recomendación:** verificar + guiar, con descarga explícita
   opcional; la descarga inicial es la **única excepción** admitida por la
   premisa 2, así que debe ser **explícita, visible y verificable**.
4. **⚠️ Decisión C — modelo por defecto.** Resolver la contradicción
   `config.py` vs `PREMISAS.md`/`README.md` **en favor del código** (fuente de
   verdad) y corregir la documentación, o cambiar el código. **Recomendación:**
   corregir la documentación (`PREMISAS.md`/`README.md`) y **declarar** la
   política; no cambiar el código sin decisión del gerente.
5. **⚠️ Decisión D — launcher en CI.** Añadir un **job de CI** para los 75 tests
   del launcher (hoy solo locales), aunque el launcher sea solo Windows (los tests
   son de lógica pura y pueden correr en ubuntu). **Recomendación:** sí.
6. **Entrega verificable.** Un **instrumento de medición de runtime de solo
   lectura** (nuevo subcomando, mismo patrón que `audit_dossier.py`), un
   **runbook de instalación limpia reproducible** y un **informe** por eje con
   hallazgos `P0/P1/P2/P3` y evidencia `archivo:línea`.
7. **Sin tocar** `DECISION_POLICY_VERSION`, `GENERATOR_VERSION`, banco,
   currículum, scoring, planner ni FSRS.

## Diseño

### §A · Eje RA — Auditoría de offline real (12 flujos de `Y` §22)

**Pregunta:** ¿la app funciona con **Internet desconectado**? **Método:**
protocolo reproducible flujo a flujo (`frontend`, `backend`, `SQLite`, `Ollama`,
`Whisper`, `Piper`, `dictionary`, `TTS`, `STT`, `course`, `practice`, `review`),
con **red cortada** y registro de cada dependencia oculta (peticiones salientes,
descargas implícitas, timeouts). **Instrumento:** subcomando nuevo de **solo
lectura** en `backend/scripts/audit_dossier.py` (p. ej. `runtime-audit`) que
inspecciona constantes, rutas, servicios con red y el manifiesto de modelos, y
escribe su par regenerable en `docs/audit/generated/`. **Dossier:**
`docs/audit/RA-RUNTIME-OFFLINE.md`.

### §B · Eje RB — Instalación limpia desde cero

**Pregunta:** ¿se instala en una **máquina limpia** sin pasos tácitos? **Método:**
runbook reproducible (venv → `requirements.txt` → **verificación de Ollama y
`ollama pull`** → `download_models.py` → `npm install` → arranque → **BD vacía →
primer usuario** → micrófono/TTS/STT), con los fallos reales encontrados y su
corrección mínima. **Debe responder:** qué falta hoy, qué es descarga y qué es
local, y qué debe hacer un **usuario no ingeniero** (premisa 17). **Dossier:**
`docs/audit/RB-INSTALACION.md`.

### §C · Eje RC — Runtime de producto y salud honesta

**Pregunta:** ¿el runtime de producto es el de desarrollo y la UI dice la verdad
sobre su estado? **Medir:** dependencia de `npm run dev`/Node, ausencia de
servido de `dist`, `ConnectionIndicator` contra `/api/health` (200 siempre) frente
a `/api/health/ready` (503 real), `ADMIN_PIN` fail-closed, timeout de 1,5 s del
launcher bajo carga. **Dossier:** `docs/audit/RC-RUNTIME-PRODUCTO.md`.

### §D · Eje RD — Dependencias ocultas y degradación (TTS/offline)

**Pregunta:** ¿hay **dependencia accidental** de Internet y la degradación es
explícita? **Medir:** barrido de red en servicios (`requests`/`urllib`/`ollama`),
auto-descarga implícita de voces (`ensure_voice_for_language`), caché negativa
volátil (`_VOICE_ENSURE_FAILED` en memoria), ausencia de checksum/tamaño, y el
cierre (o re-declaración con fase) del **P1 de TTS/offline** diferido 4 veces.
**Dossier:** `docs/audit/RD-DEPENDENCIAS-OCULTAS.md`.

### §E · Eje RE — Gates, CI y deriva documental

**Pregunta:** ¿lo que la documentación declara ✅ está realmente en verde?
**Acción:** añadir el **job del launcher** al CI (Decisión D) y corregir las
**derivas**: árbol del launcher en `ARQUITECTURA.md`, modelo por defecto
(`PREMISAS.md`/`README.md`), los ✅ falsos de `BETA_GATES.md` (launcher, «CI
completa», matriz de dispositivos) y la fecha/versión de `BETA_GATES.md`.
**Dossier:** `docs/audit/RE-GATES-DERIVA.md`.

### §F · Síntesis (orquestador, no subagente)

`docs/audit/RF-SINTESIS-RUNTIME-V371.md`: matriz consolidada `P0/P1/P2/P3`,
veredicto numérico, y sección de **honestidad**: lo que V3.71 **NO** demuestra
(no prueba en hardware móvil real —eso es la matriz de dispositivos—, no mide
calidad acústica, no garantiza ausencia de dependencias ocultas **en todos** los
caminos, y cualquier verificación offline en CI es **simulada** porque la premisa
12 prohíbe tests dependientes de red).

## Tests

- **Nuevos**, uno por hallazgo **medido y determinista**: p. ej.
  `backend/tests/test_runtime_offline_v371.py`,
  `test_install_bootstrap_v371.py`, `test_runtime_product_v371.py`,
  `test_hidden_deps_v371.py`. Nada de red ni de modelos en los tests: los flujos
  que exigen red/descarga se fijan con **dobles** (`monkeypatch`) y se **separan**
  en el **runbook manual** documentado.
- **Regla:** se afirma sobre **contratos observables** (constantes, artefactos en
  disco, funciones puras del launcher/core), nunca sobre implementación privada, y
  **nunca** se escribe un test que pase porque el runtime es pobre: si el hueco
  existe, el test lo **declara**.
- **No-regresión obligatoria:** los 75 tests del launcher, `test_*_v370.py`,
  `test_adaptive_e2e_v369.py`, `test_decision_v368.py` y las baterías pedagógicas
  deben seguir verdes.
- **CI:** si se aprueba la Decisión D, nuevo job del launcher; el resto del CI no
  se toca.

## Criterios de salida

1. Los seis dossiers `RA`–`RF` existen, siguen `docs/audit/TEMPLATE.md` y cada
   hallazgo lleva `archivo:línea` y comando de reproducción.
2. El **instrumento de runtime** corre **sin escribir** en `data/` ni en
   `curriculum/` y regenera su par en `docs/audit/generated/` de forma
   determinista.
3. El **runbook de instalación limpia** es reproducible de principio a fin en una
   máquina limpia y está escrito para usuario **no ingeniero**.
4. Los tests nuevos están **verdes** y el total de `pytest` es anterior + nuevos.
5. `ruff`, `tsc`, `vitest`, `build`, launcher y los gates de script OK.
6. Las **derivas documentales** corregidas (o declaradas con su fase si alguna
   excede el alcance).
7. **CI 6/6** (o 7/7 si se añade el job del launcher), registrado con su run id.
8. La release note declara **honestamente** el diff de producto (endurecimientos
   mínimos) y lo que la release **no** demuestra.

## Fuera de alcance (deuda declarada)

- **Matriz de dispositivos** en hardware (G) y `docs/DEVICE_MATRIX.md` (10/10 ⬜).
- **Variabilidad LLM de speaking** con Ollama real.
- **Los 6 P2 de V3.69** y los **33 hallazgos de V3.70**.
- **Planner 4.0**, **Expected Learning Gain real**, calibración con tráfico real.
- **Empaquetado/instalador** (vetado el contenedor; decisión de producto).
- **Multiplataforma** (hoy el launcher es solo Windows; se puede **declarar** pero
  no implementar salvo decisión).
- **V3.72** UX/product completion → **V3.73** auditoría final técnica → **V4.0**.

## Cierre (higiene de release, cuando se ejecute)

`check_release_consistency.py` usa **la primera coincidencia**: insertar arriba.

1. `backend/config.py` → `VERSION = "3.70.0"` → `"3.71.0"` (**fuente única**).
2. `frontend/package.json` → `"version"`.
3. `frontend/package-lock.json` (y la copia de la línea 9).
4. `README.md` → «Última versión estable: **v3.71.0**».
5. `CHANGELOG.md` → `## [3.71.0] — <fecha>` **en la cabecera**.
6. `PLAN.md` → bullet primero de «Estado actual» + `### M13` (marcar V3.71 hecho y
   mover la flecha a **V3.72**) + tablero de briefings.
7. `docs/RELEVO.md` → **nota nueva encima** + fecha + refrescar «0. START HERE».
8. `release-notes-v3.71.0.md` (nuevo, raíz) con contexto, ejes, tabla de
   hallazgos, tests, §«Honestidad» y §«Fuera de alcance».
9. `docs/audit/PARKED.md` → registrar lo deliberadamente **no** arreglado.
10. **No** tocar `DECISION_POLICY_VERSION` ni `GENERATOR_VERSION`.

Verificación local antes de commitear: `ruff`, `pytest`, `tsc`, `vitest`, `build`,
launcher, `check_release_consistency`, `check_beta_v3`, `content_validation` y
`transfer_validation`. Después: commit de release + tag anotado `v3.71.0` + push,
y registrar el run de **CI** en la nota de `docs/RELEVO.md`.
