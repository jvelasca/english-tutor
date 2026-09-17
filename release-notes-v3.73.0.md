# Release notes — English Tutor v3.73.0

**Fecha:** 2026-09-17 · **Tipo:** release de **VALIDACIÓN** (sin capacidad
pedagógica nueva) · **Versión de app:** `3.72.0 → 3.73.0`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.**

---

## Qué es esta release

V3.73 no añade nada que el alumno pueda usar. Hace dos cosas y las declara
separadas:

1. **Cierra el endurecimiento mínimo** que la auditoría de V3.72 dejó como P2/P3:
   el runtime de producto es **fail-closed** y el descubrimiento de la IP de LAN
   **no usa direcciones públicas**.
2. **Construye el instrumento de certificación** que convierte los siete gates de
   validación física (cinco de ellos **acción humana**) en **evidencia registrada
   y exigible**, en vez de en promesas.

**El valor de V3.73 es el instrumento, no fingir una validación que no se ha
hecho.** La release se publica **con los 7 gates en `pending`** por diseño.

---

## 1 · Fail-closed del runtime de producto (P2 del dictamen)

**Lo que había (medido):** el launcher **sí** elevaba `PreparationError` si
`npm run build` fallaba, pero el backend era **siempre fail-open**
(`mount_frontend` devolvía `False` en silencio). Resultado: lanzar el producto sin
artefacto producía una app que **parecía lista y se veía vacía**. El hueco real no
era el launcher: era el **runtime de producto**.

**Lo que hay ahora:**

| Capa | Qué hace |
|---|---|
| `backend/services/frontend_dist.py` | `mount_frontend(app, path, require_ui)` distingue los dos runtime. En **producto**, la falta de `dist/index.html` eleva `RuntimeError` con mensaje accionable (`npm run build`); en **desarrollo** conserva el `return False`. |
| `backend/main.py` | Declara el modo explícitamente: `mount_frontend(app, require_ui=require_ui_from_env())`. |
| `launcher/core.py` | `backend_env()` inyecta `ENGLISH_TUTOR_REQUIRE_UI=1` en el entorno de uvicorn, copiando el entorno del usuario (no lo pisa). |
| `launcher/process_manager.py` | `start_backend()` **no arranca** sin `frontend/dist/index.html`; `ensure_frontend_dist()` distingue «el build falló» de «el build dijo OK y no dejó artefacto». |

**Un `uvicorn main:app` manual sigue siendo fail-open**: es el modo desarrollo,
donde un clon limpio sin `npm run build` conserva la API. La exigencia la declara
el **runtime de producto**, no el código de la app.

**Tests:** `backend/tests/test_serve_frontend_v373.py` (19) y
`launcher/tests/test_preflight_v373.py` (7). Fijan las dos mitades y el contrato
compartido: si alguien renombra la variable en un solo lado, fallan.

## 2 · Descubrimiento de la IP de LAN sin referencias externas (P3)

**Lo que había (medido):** la IP de LAN se obtenía con un socket UDP «connect» a
`8.8.8.8:80` en **tres** sitios: `backend/services/network.py`,
`backend/services/tls_cert.py` y `launcher/core.py`. Técnicamente correcto (el
`connect` UDP es **perezoso**: elige la interfaz de salida y **no envía paquetes**,
así que funciona sin Internet), pero es una **referencia pública** en la lógica de
descubrimiento de una aplicación que se declara **100 % local**.

**Lo que hay ahora:** `backend/services/net_interfaces.py`

- `select_lan_ipv4(addresses)` — **puro** y testeable sin red: descarta loopback,
  link-local (`169.254/16`), `0.0.0.0` y multicast; prefiere rangos privados; es
  determinista respecto al orden de entrada; nunca devuelve vacío (último recurso
  `127.0.0.1`).
- `candidate_addresses()` — enumera las direcciones del **propio equipo**
  (`getaddrinfo` + `gethostbyname_ex` del nombre local, dos vías porque en algunos
  Windows el nombre solo aparece en una). Un fallo de resolución devuelve lista
  vacía, nunca una excepción.
- Override declarado `ENGLISH_TUTOR_LAN_IP` para equipos con varias NIC o VPN.
- Delegan en él `services/network.py::get_lan_ip` y
  `services/tls_cert.py::_local_ip`. `launcher/core.py` **replica el algoritmo
  puro** (no puede importar el backend: son proyectos separados).

**Cascada obligatoria del instrumento de V3.71** (el eje RA lo exige): la
declaración `RUNTIME_TOUCHPOINTS` de `backend/scripts/audit_dossier.py` cambia el
punto `lan` de `services/network.py` (UDP) por uno en
`services/net_interfaces.py`; el par determinista
`docs/audit/generated/runtime-audit.{md,json}` se regenera y
`docs/audit/RA-RUNTIME-OFFLINE.md` recoge el cierre (**RA-08**). El reparto por
tipo sigue siendo **1 loopback · 2 lan · 6 internet**.

**Tests:** `backend/tests/test_net_interfaces_v373.py` (23),
`launcher/tests/test_lan_ip_v373.py` (13) y un **candado anti-deriva** que falla si
una IP pública vuelve a aparecer en **código** (no en prosa: se escanea el AST y se
excluyen los docstrings) de los cuatro ficheros implicados.

## 3 · Cobertura CI en Windows (bloque C del dictamen)

**Lo que había (medido):** los 8 jobs corrían en `ubuntu-latest`. El launcher es
una utilidad **de Windows** y el certificado TLS se genera con
`cryptography`/rutas de Windows: **nada de eso se ejercitaba en CI**.

**Lo que hay ahora:** de **8 a 11 jobs**.

| Job | Runner | Bloqueante | Qué prueba |
|---|---|---|---|
| `launcher-windows` | `windows-latest` | **Sí** | `ruff` + los **113 tests** del launcher en Windows real. Solo necesita stdlib + pytest/ruff, con los **mismos pins** que el job `backend`. |
| `product-origin-windows` | `windows-latest` | **No** (declarado) | Build de la UI + `ensure_tls_cert` + `uvicorn` con TLS + PowerShell comprobando HTML en `/`, `version` en `/api/health` y **404** en `/api/no-existe`. |
| `validation-gate` | `ubuntu-latest` | **Sí** | `validation_gate.py auto`: las comprobaciones estáticas del arnés (stdlib pura, sin instalar nada). |

**Honestidad sobre `product-origin-windows`:** se estrena como **informativo**
(`continue-on-error: true`) porque instalar `requirements-dev.txt` en Windows
depende de **ruedas nativas** (`piper-tts`, `faster-whisper` → `ctranslate2`) que
**no se pueden verificar desde Linux**. **Criterio de promoción explícito:** pasa a
`continue-on-error: false` cuando acumule **runs verdes consecutivos** en Windows;
mientras tanto, su fallo es **visible** pero no bloquea la release, y así se
declara. El gate humano **G3** (launcher en Windows real) sigue siendo el que
certifica.

## 4 · Arnés de validación (los 7 gates)

**`scripts/validation_gate.py`** — stdlib pura, mismo patrón que
`check_release_consistency.py`. Tres subcomandos:

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
backend\.venv\Scripts\python.exe scripts\validation_gate.py record offline-fisico pass --notes "12/12 flujos OK"
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict
```

- **`auto`** — 10 comprobaciones **estáticas** (versión consistente, i18n
  `--strict`, fail-closed cableado, descubrimiento de LAN sin IPs públicas, jobs
  Windows en CI, matriz de dispositivos en `:8000`, instrumento de red sin deriva,
  los 7 gates declarados, artefacto de UI —`skip` sin `--require-dist`— y evidencia
  íntegra). Escribe el informe determinista
  `docs/audit/generated/release-validation.{md,json}` y **sale 1** si algo falla.
- **`record <gate> <pass|fail|skip> --notes`** — registra el resultado en
  `docs/audit/validation-evidence.json`. **Registrar exige notas**: una evidencia
  vacía no vale, y un gate desconocido o un estado inventado se rechazan. Guarda
  estado, notas, fecha y la `VERSION` del árbol.
- **`status [--strict]`** — tabla de los 7 gates. **`--strict` sale 1 mientras
  algún gate no esté en `pass`**: es la **puerta real de V4.0**.

Los 7 gates: `offline-fisico` (G1), `maquina-limpia` (G2), `launcher-windows` (G3),
`dispositivos` (G4), `audio-stt-tts` (G5), `journeys` (G6) y `pedagogia` (G7). Cada
uno referencia su **protocolo existente** (`RA-RUNTIME-OFFLINE.md` §5, runbook de
`RB-INSTALACION.md`, `DEVICE_MATRIX.md`, `F-UX-JOURNEY.md`,
`CONSTITUCION-PEDAGOGICA.md`) en vez de duplicarlo. Runbook completo en
`docs/audit/VALIDATION-RELEASE-V373.md`.

**`--strict` NO corre en CI**: los gates humanos están `pending` por diseño, y un
CI que los exigiera sería un CI permanentemente rojo. Lo que el CI sí ejecuta es
`auto`.

**Tests:** `backend/tests/test_validation_gate_v373.py` (24) y
`backend/tests/test_docs_drift_v373.py` (19).

## 5 · Drift documental corregido

- **`docs/DEVICE_MATRIX.md` seguía documentando `https://<ip>:5173` y Vite como
  runtime**, contra lo que V3.72 declaró. Corregido a **`:8000`**, y ampliado con
  una **matriz de interacción** (touch/tap targets, viewport y scroll, teclado en
  pantalla y orientación) porque una web de escritorio suele romperse ahí y **no se
  puede certificar con capturas**.
- **`docs/PREMISAS.md`, `docs/ARQUITECTURA.md` y `README.md`** declaran el
  fail-closed del runtime de producto y el descubrimiento de LAN sin referencias
  externas, con el nombre del módulo, la variable de entorno y el override.
- **`docs/audit/RC-RUNTIME-PRODUCTO.md`** recoge el fail-closed como cierre
  completo del P2 de RC-01.
- **`docs/audit/RA-RUNTIME-OFFLINE.md`** cierra **RA-08** y anota la cascada del
  instrumento.
- Fijado por **`backend/tests/test_docs_drift_v373.py`** (19 tests).

---

## Verificación (lo que se ejecutó en este árbol)

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q     # 2779 passed
.venv\Scripts\python.exe -m ruff check .          # limpio

# Frontend (V3.73 no toca producto: se comprueba que NO ha derivado)
cd ..\frontend
npx vitest run                                    # 699 passed (83 ficheros)
npx tsc --noEmit                                  # limpio
npm run build                                     # OK

# Launcher
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q   # 113 passed
..\backend\.venv\Scripts\python.exe -m ruff check .       # limpio

# Arnés y gates de release
cd ..
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist  # 10/10
backend\.venv\Scripts\python.exe scripts\validation_gate.py status               # 7 pending
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict      # exit 1 (correcto)
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict         # 0 huérfanas
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py            # 6 orígenes
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py                        # OK
```

---

## Honestidad

- **Los 7 gates están en `pending`.** V3.73 **no** ha hecho el corte de red real
  (RA-05), **no** se ha probado en una máquina físicamente limpia (RB-05), **no**
  se ha probado en hardware móvil real y **no** se ha probado con micrófono y
  altavoces reales. Lo que V3.73 aporta es que **ahora eso es estado registrado y
  exigible**: `status --strict` **falla** mientras falte, y no se puede cerrar un
  gate sin escribir qué se observó.
- **`product-origin-windows` es informativo.** Se declara en vez de fingir que es
  bloqueante, porque no puedo verificar desde Linux que sus ruedas nativas
  instalen en Windows. `launcher-windows` **sí** es bloqueante (stdlib pura).
- **El fail-closed cubre el arranque, no la ejecución degradada.** Si el artefacto
  desaparece **después** de arrancar, el proceso sigue sirviendo lo que ya tiene
  montado; la guardia es de arranque (que es donde estaba el hueco medido).
- **El descubrimiento de LAN cambia de técnica, no de garantía.** `getaddrinfo` del
  nombre local puede devolver solo loopback en Windows mal configurados; por eso
  hay dos vías de enumeración, un override declarado y un último recurso
  `127.0.0.1`. Lo que **sí** se garantiza es que ya no hay ninguna dirección
  pública en el camino.
- **`auto` es estático y stdlib pura**: comprueba el repositorio, **no** el
  comportamiento en runtime. Eso lo fijan los suites de tests y los jobs del CI. No
  sustituye a nada.
- **`RA-02` (endpoint de Ollama sin declarar en `config.py`) sigue abierto**, y
  `RA-07`/`RD-05` siguen como deuda aceptada.

## Criterio de V4.0

V4.0 se declara cuando `validation_gate.py status --strict` salga **0**: los 7
gates en `pass`. V3.73 deja el instrumento listo y el endurecimiento hecho; lo que
falta es **humano y físico**, y ahora es **verificable de un vistazo**.
