# Briefing de subagente — V3.72 (UX / product completion)

> **Estado:** **APROBADO** (2026-09-17). Las tres decisiones de alcance marcadas
> abajo están **cerradas por el gerente** (ver §Decisiones de alcance).
> **Qué es:** la release de **UX y completitud de producto**, la penúltima antes
> de la auditoría final `V3.73` y de `V4.0` («English Tutor, primera versión
> completa y estable»). Tras V3.69 (el motor adaptativo funciona como una pieza),
> V3.70 (la pedagogía está medida) y V3.71 (el runtime real está medido y
> declarado), el eslabón que queda es el que ve el alumno: **que el producto se
> sirva de verdad, que diga la verdad sobre lo que descarga y suena, y que el
> alumno entienda qué hace y por qué**.
> **Qué cierra:** los **dos ítems que V3.71 dejó fechados en vez de cerrados**
> (**RD-04**/mitad de **RA-01**: vector UI del P1 de TTS/offline, y **RC-01**:
> servido de `frontend/dist` con Node como requisito de ejecución), lo que V3.70
> asignó a V3.72 (**AE-04**, **AE-06**) y la deuda UX declarada de
> `docs/audit/PARKED.md` y `docs/audit/F-UX-JOURNEY.md` (**F2**, **F3**, **F4**,
> 50 claves i18n huérfanas).
> **Qué NO cierra (deuda declarada):** los **33 hallazgos de V3.70** (contenido →
> `V4.0.x`, motor → Planner 4.0), los **6 P2 de V3.69**, la **matriz de
> dispositivos** (G5, acción humana), el **corte de red real** (RA-05, acción
> humana), la **máquina limpia real** (RB-05, acción humana), **RA-02**
> (endpoint de Ollama sin declarar), el **sesgo posicional de los ítems MC**
> (fix mecánico que requiere aprobación) y **Planner 4.0**.
> **Motivación/roadmap:** `PLAN.md:1541-1551`, `docs/audit/X-AUDITORIA-TOTAL-V367.md`
> §19, `docs/audit/Y-AUDITORIA-TOTAL-V368.md` §23 y §28, y las condiciones de
> salida de `docs/audit/RC-RUNTIME-PRODUCTO.md:76-78` y
> `docs/audit/RD-DEPENDENCIAS-OCULTAS.md:141`.
> **Regla dura declarada:** *V3.72 es una release de **UX y completitud**, no de
> capacidad pedagógica.* No se toca el motor adaptativo, ni el banco, ni el
> currículum, ni `DECISION_POLICY_VERSION`/`GENERATOR_VERSION`, ni el argmax del
> Planner, ni el scoring, ni FSRS. Todo cambio de producto va **forzado por un
> hallazgo declarado**, acompañado de un **test que falla sin él** (premisa 12) y
> **sin recalcular señales en el cliente** (premisa 21).
> **Ejes:** **UA** (servido real de la UI / RC-01) · **UB** (voz y TTS en la UI /
> RD-04) · **UC** (patrones de UI y estados honestos / F2–F4) · **UD**
> (instrumentos y declaraciones / AE-04, AE-06) · **UE** (i18n e higiene) ·
> **UF** (síntesis y declaración honesta).
> **Entrega:** los cambios de UX, runtime y declaración con sus tests, un
> `release-notes-v3.72.0.md` con §Honestidad y §Fuera de alcance, y el cierre de
> release con sus gates.
> **Base de partida:** árbol `v3.71.0` (commit `a09bada`, tag anotado `v3.71.0`).

## Rol

**Ingeniero de producto y UX.** Convertir «la app funciona medida y declarada»
en «la app **se sirve de verdad**, **dice la verdad** sobre lo que descarga y
suena, y **se entiende**»: cerrar RC-01 sirviendo `frontend/dist` desde el
backend, cerrar el vector UI del P1 de TTS/offline, y liquidar la deuda de UX
declarada (estados loading/error honestos, i18n limpio, divulgación de
instrumentos). Sin migración de BD, sin bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, sin tocar banco ni currículum y sin umbrales nuevos.

## Objetivo

1. **Servir la UI de verdad** (RC-01): el backend sirve `frontend/dist`; el
   launcher construye el artefacto y arranca **un solo origen HTTPS**; Node deja
   de ser requisito de **ejecución** y pasa a ser requisito de **compilación**.
2. **Cerrar RD-04**: la UI **avisa** de la descarga de voz, **pide
   consentimiento**, muestra **progreso indeterminado** y **consume** las
   cabeceras `X-TTS-Voice`/`X-TTS-Degraded` para decir qué voz suena.
3. **Estados honestos**: extender el patrón `loading → error → done` con
   reintento a los paneles profundos (F4), resolver la duplicidad de readiness
   (F2) y anclar el «estás aquí» (F3).
4. **Declaración de instrumentos** (AE-04) y **unificación de umbrales de banda**
   (AE-06).
5. **Higiene i18n**: eliminar las 50 claves huérfanas y dejar el checker en el
   gate.
6. **Declarar honestamente lo que V3.72 NO demuestra.**

## Estado de partida verificado (árbol `v3.71.0`)

> Verificado por lectura de código (`archivo:línea`) el 2026-09-17.

### UA · Runtime de producto: la UI no la sirve el producto (RC-01)

| Hecho | Evidencia |
|---|---|
| El backend **no** monta nada estático: no hay `StaticFiles` ni `FileResponse` en todo `backend/` | `backend/main.py` (verificado); candado en `backend/tests/test_docs_drift_v371.py:261-270` |
| La UI la sirve el **dev server de Vite** (`npm run dev`) por HTTPS autofirmado en `:5173` | `launcher/core.py:57-60`; `frontend/vite.config.ts:12-21,27-31` |
| El backend arranca en **HTTP** `:8000` y el proxy de Vite reenvía `/api` | `launcher/core.py:38-54`; `frontend/vite.config.ts:32-37` |
| `frontend/dist` **existe** en disco pero está **gitignored** (`dist/`) y **nadie lo sirve** | `.gitignore:2`; `.github/workflows/ci.yml:52-53` (solo `npm run build`) |
| El frontend usa **rutas relativas** `/api/...` (no hay `VITE_*` ni `import.meta.env`) | `frontend/src/api/client.ts:23,76` |
| El launcher valida el frontend con `GET https://localhost:5173` aceptando el autofirmado | `launcher/status.py:43-57` |
| `POST /api/tts` ya expone `X-TTS-Voice`/`X-TTS-Degraded` y CORS los expone | `backend/routers/voz.py:80-84`; `backend/main.py:132` |

### UB · Voz/TTS: el backend habla, la UI no escucha (RD-04)

| Hecho | Evidencia |
|---|---|
| `speak()` es el **único** cliente TTS y **descarta** las cabeceras (no lee `res.headers`) | `frontend/src/api/voz.ts:44-52` |
| Sin **timeout** ni `AbortController` en TTS/STT (el `withTimeout` de `client.ts` no aborta) | `frontend/src/api/voz.ts:9-65`; `frontend/src/api/client.ts:52-74` |
| El error de TTS es **silencioso** en casi todos los sitios; solo `SpeakButton` usa `alert()` | `ListenButton.tsx:40-42`; `SpeakButton.tsx:14`; `ListeningPractice.tsx:676-678`; `useHandsFree.ts:225-227` |
| La descarga de voz se dispara **implícitamente** (sin consentimiento) al montar el traductor | `ConversationTranslator.tsx:93-112` |
| `VoicesPanel` avisa del tamaño pero **no** pide consentimiento ni muestra progreso (%) | `VoicesPanel.tsx:191-193,214,217-233` |
| El endpoint de descarga es **síncrono y bloqueante** (sin progreso que consumir) | `backend/routers/voices.py:63-79` |

### UC · Estados y comprensión (deuda declarada)

| Hecho | Evidencia |
|---|---|
| `FsrsReviewPanel`, `EvidenceGraphPanel` y `AssessmentLadder` **tragan** errores de carga (catch vacío) | `docs/audit/F-UX-JOURNEY.md:61` (F4) |
| Home muestra el readiness **dos veces** casi yuxtapuesto | `docs/audit/F-UX-JOURNEY.md:60` (F2) |
| `home.youAreHere` está **definido y sin uso** | `docs/audit/F-UX-JOURNEY.md:60` (F3); `i18n.ts` |
| El patrón correcto ya existe: `loading → error → done` con `home.unavailable`/`home.retry` | `HomeScreen.tsx:249-259`; `docs/audit/F-UX-JOURNEY.md:43-46` |
| El «por qué» ya existe en `NextBestCard` (`home.whyThisActivity`) y en FSRS (`fsrs.whyReason.*`) | `NextBestCard.tsx:66-73`; `i18n.ts:1979-2029` |

### UD · Instrumentos y umbrales

| Hecho | Evidencia |
|---|---|
| El placement mide **reconocimiento/meta-lenguaje** en 4 destrezas, y no se declara en la UI | `docs/audit/AE-PED-INSTRUMENTOS.md:105` (AE-04); `curriculum.py:375-382` |
| Los umbrales de banda están **triplicados** y `+`/`pre-a1` no los emite nadie | `docs/audit/AE-PED-INSTRUMENTOS.md:107` (AE-06); `adaptive.py:52`; `academy.py:1033`; `cefr.py:58` |
| Los tres estimadores **coinciden** en toda la rejilla (propiedad a preservar) | `docs/audit/AE-PED-INSTRUMENTOS.md:88-89,110` |
| `api/academy.ts` define el placement pero **ningún componente lo consume** hoy | `frontend/src/api/academy.ts:89-119`; grep sin usos |

### UE · i18n

| Hecho | Evidencia |
|---|---|
| **50 claves huérfanas** (definidas y nunca referenciadas), sin duplicados ni roturas | `docs/audit/F-UX-JOURNEY.md:62`; `docs/audit/generated/i18n-report.json` |
| El checker es reproducible y hay allow-list de prefijos dinámicos | `scripts/check_i18n_coverage.py`; `frontend/src/utils/i18n.parity.test.ts:31-48` |

### Restricciones de proceso aplicables

- **Premisa 5**: briefing autocontenido en `agentes/`; **premisa 6**: un
  incremento a la vez, con su release.
- **Premisa 12**: todo lo que se afirma se fija con un test **rápido y
  determinista**; los tests **no** dependen de red, de modelos ni de descargas
  (los flujos con red se fijan con dobles y se prueban a mano en el runbook).
- **Premisa 21**: la IA produce evidencia; **el motor determinista decide**. La
  UI **no** recalcula señales (ni readiness, ni candidatas, ni prioridades).
- **Premisa 17**: la Ayuda y los avisos van dirigidos a un usuario **no
  ingeniero**.
- **Gate real**: `scripts/check_release_consistency.py` (primera coincidencia →
  insertar arriba).

## Decisiones de alcance (CERRADAS por el gerente el 2026-09-17)

1. **Decisión A — RC-01: se IMPLEMENTA el servido de `frontend/dist`.** El
   backend sirve el artefacto y el launcher lo construye; el producto pasa a
   **un solo origen HTTPS en `:8000`**. `npm run dev` deja de ser requisito de
   **ejecución** (queda como modo de **desarrollo**, preservado). Node sigue
   siendo requisito de **instalación/compilación** (el `dist` no se versiona).
2. **Decisión B — RD-04: consentimiento + aviso + progreso INDETERMINADO, sin
   tocar el endpoint de descarga.** Se consume `X-TTS-Voice`/`X-TTS-Degraded`. El
   progreso real exigiría rediseñar el endpoint bloqueante y queda **fuera**.
3. **Decisión C — Alcance medio.** Además de lo fechado, entran: **AE-04**,
   **AE-06**, **F2**, **F3**, **F4**, la limpieza de las **50 claves i18n** y la
   extensión de «por qué esta actividad» a las superficies clave donde falta.

## Diseño

### §UA · Servido real de la UI (RC-01)

**Pregunta:** ¿el producto que arranca el launcher es el que se construye?
**Acción:** el backend monta `frontend/dist` (assets + fallback SPA) y el
launcher deja de arrancar Vite.

- **`backend/main.py`**: tras los routers, si `frontend/dist` existe, montar
  `/assets` con `StaticFiles` y una ruta catch-all `/{full_path:path}` que
  devuelve el fichero pedido o `index.html` (la app no usa router propio, así que
  el fallback es defensivo). **Fail-open:** sin `dist` no se monta nada y el
  arranque no se rompe; se registra en log qué se está sirviendo.
- **TLS autofirmado**: HTTPS es **obligatorio**, no cosmético: sin *secure
  context* por LAN `navigator.mediaDevices` es `undefined` y se rompe
  `getUserMedia` (micrófono), que es el corazón de speaking/listening. Nuevo
  `backend/scripts/ensure_tls_cert.py` (determinista, idempotente) que genera
  `backend/data/certs/{cert,key}.pem` con SANs `localhost`, `127.0.0.1`,
  `<hostname>`, `<hostname>.local` y la IP de LAN. Requiere **`cryptography`**
  (no está instalada hoy) añadida a `backend/requirements.txt`. El certificado
  **no se versiona** (`backend/data/` ya está ignorado).
- **`launcher/core.py`**:
  - `backend_command()` añade `--ssl-keyfile`/`--ssl-certfile` con las rutas del
    certificado.
  - `frontend_command()` **deja de arrancar Vite**. Nuevo `ensure_dist()` que
    construye `frontend/dist` con `npm run build` si falta (o si el usuario pide
    reconstruir) y **falla con un mensaje claro y accionable** si no hay Node
    (`npm` no encontrado).
  - `FRONTEND_PORT` desaparece como puerto propio: la UI y la API comparten
    `:8000`. `backend_url()`, `frontend_url()`, `lan_url()` y `local_url()` pasan
    a **`https://…:8000`**.
- **`launcher/status.py`**: `_get_json` y `fetch_frontend` usan contexto SSL que
  acepta el autofirmado (ya existe `_frontend_ssl_context`) y apuntan al origen
  unificado; el estado deja de tener dos URLs.
- **`launcher/process_manager.py`** y la GUI: un solo proceso de producto
  (backend); Vite deja de gestionarse.
- **`launcher/allow-firewall.ps1`**: se abre **solo 8000** (la UI ya no vive en
  5173).
- **`backend/routers/network.py`**: `FRONTEND_PORT` → `8000`, para que el QR de
  `ConnectDeviceCard` anuncie `https://<ip>:8000`.
- **`backend/config.py`**: añadir `https://localhost:8000` / `http://localhost:8000`
  a `ALLOWED_ORIGINS` (la regex de IPs privadas ya cubre la LAN). CORS se
  mantiene por compatibilidad con el modo dev.
- **Modo dev preservado**: `npm run dev` + proxy de Vite y `.vscode/launch.json`
  siguen funcionando para HMR. **No** se borra.
- **Tests y candados** (premisa 12, tests-first): reescribir los dos tests de
  deriva de `backend/tests/test_docs_drift_v371.py:250-296` a la **nueva**
  frontera; ajustar `launcher/tests/test_core.py:57-60`, `backend/tests/test_network.py`
  (5173→8000), `test_cors.py` y `test_security.py`; nuevos: servido de
  `index.html`/assets, fallback SPA, **fail-open** sin `dist`, generación de
  cert con SANs y `ensure_dist`.
- **CI**: paso de humo que, con `dist` construido, arranca `uvicorn` con TLS y
  comprueba por `https://127.0.0.1:8000/` que sirve el `index.html`. Playwright
  sigue sobre el dev server (prueba la app React, que es el objeto real).
- **Docs a re-declarar**: `docs/PREMISAS.md` §3, `docs/ARQUITECTURA.md`,
  `README.md`, `docs/BETA_GATES.md`, y **cierre de RC-01** en
  `docs/audit/RC-RUNTIME-PRODUCTO.md` + retirada de `docs/audit/PARKED.md`.

### §UB · Voz y TTS en la UI (RD-04 / mitad de RA-01)

**Pregunta:** ¿sabe el alumno que se descarga una voz y qué voz suena?
**Acción:** consentimiento explícito + aviso honesto, sin tocar el backend.

- **`frontend/src/api/voz.ts`**: `speak()` pasa a devolver `{ voice, degraded }`
  leyendo `res.headers.get("X-TTS-Voice")` / `X-TTS-Degraded` (CORS ya los
  expone). Añadir `AbortController` con timeout (el actual no aborta el fetch).
- **Estado del TTS compartido**: un punto único (hook) que centraliza si la
  última reproducción fue **degradada** y con qué voz, para que todos los
  consumidores digan lo mismo.
- **Superficies**: `ListenButton` y `SpeakButton` propagan el estado; los
  fallbacks directos (`ListeningPractice`, `SpeakingRoutesPractice`,
  `ConversationTranslator`, `useHandsFree`, `MicrophoneTest`) usan el mismo
  canal en vez de tragar el error.
- **Aviso de voz degradada**: aviso **no bloqueante** (`role="status"`,
  reutilizando el patrón de `MicUnavailableNotice`/`InfoDisclosure`) que explica
  que suena la voz por defecto porque la del idioma no está instalada, con la
  voz real.
- **Consentimiento de descarga**: componente con el patrón de diálogo
  (`dialog-backdrop/.dialog[aria-modal]`) que, **antes** del primer TTS de un
  idioma sin voz instalada, avisa del tamaño (~60 MB, una vez, requiere
  Internet) y pide consentimiento. El auto-download actual del traductor pasa
  por ese flujo. **Progreso indeterminado** (spinner): el endpoint es bloqueante
  y se declara así.
- **i18n** es/en de las claves nuevas y **tests**: `voz.test.ts` (cabeceras y
  timeout), `ListenButton`, consentimiento y degradación; ajustar los mocks de
  `speak` en `TranslatorScreen.test.tsx`/`ConversationPanel.test.tsx`.

### §UC · Estados honestos y comprensión (F2, F3, F4)

- **F4**: extender `loading → error → done` con reintento (`home.unavailable` /
  `home.retry`) a `FsrsReviewPanel`, `EvidenceGraphPanel` y `AssessmentLadder`,
  que hoy dejan la sección vacía sin explicación.
- **F2**: resolver la duplicidad de readiness en Home (la tríada y la tarjeta
  contigua): una sola fuente de lectura y una sola superficie que la muestre,
  con test que fija que no se duplica.
- **F3**: usar `home.youAreHere` como ancla textual explícita y posición en la
  ruta (hoy definida y sin uso).
- **«Por qué esta actividad»**: partir de `NextBestCard`/FSRS y extenderlo a las
  superficies clave que hoy no lo explican. **La razón la sirve el backend**
  (premisa 21): la UI solo la presenta.

### §UD · Instrumentos y declaraciones (AE-04, AE-06)

- **AE-04**: **declarar** en la UI que el placement mide reconocimiento/
  meta-lenguaje en listening/speaking/writing/pronunciation y no producción. Si
  no existe superficie que muestre el resultado de nivelación, el hallazgo se
  **re-declara con fase** en vez de inventar una pantalla.
- **AE-06**: **unificar** los umbrales de banda triplicados en **un solo módulo**
  preservando la equivalencia exacta (0 desacuerdos en la rejilla, propiedad
  positiva a mantener) y **decidir** las sub-bandas `+`/`pre-a1`: se **retiran
  de la escalera** si ningún estimador las emite, o se les da emisor. La decisión
  se declara y se fija por test.

### §UE · i18n e higiene

- Eliminar las **50 claves huérfanas** confirmadas por el checker, respetando la
  allow-list de prefijos dinámicos (`i18n.parity.test.ts:31-48`) y sin tocar
  claves accedidas por indirección.
- Regenerar `docs/audit/generated/i18n-report.{md,json}` y dejar
  `scripts/check_i18n_coverage.py` en el **gate de cierre**.

### §UF · Síntesis (orquestador, no subagente)

`release-notes-v3.72.0.md` con: contexto, los ejes, la tabla de hallazgos
cerrados/declarados, los tests, una sección **§Honestidad** (lo que V3.72 **NO**
demuestra) y **§Fuera de alcance**. Actualizar la Nota superior de
`docs/RELEVO.md`, `PLAN.md` (mover la flecha a **V3.73**) y `docs/audit/PARKED.md`.

## Tests

- **UA**: `backend/tests/test_serve_frontend_v372.py` (servido de `index.html` y
  assets, fallback SPA, fail-open sin `dist`), `test_tls_cert_v372.py` (SANs,
  idempotencia, no versionado), actualización de los candados de deriva y de
  `launcher/tests/test_core.py`.
- **UB**: `frontend/src/api/voz.test.ts` (cabeceras + timeout), tests de
  `ListenButton`/consentimiento/degradación y ajuste de los mocks existentes.
- **UC**: tests de `FsrsReviewPanel`/`EvidenceGraphPanel`/`AssessmentLadder`
  (error visible + reintento), de Home (readiness no duplicado, «estás aquí»).
- **UD**: tests de la unificación de umbrales (equivalencia en la rejilla y
  decisión declarada sobre `+`/`pre-a1`) y de la declaración del placement.
- **Regla**: se afirma sobre **contratos observables** (cabeceras, estados de UI,
  artefactos en disco, funciones puras), **nunca** sobre implementación privada.
  Ningún test depende de red, de modelos ni de descargas.
- **No-regresión obligatoria**: `test_docs_drift_v371.py` (re-escrito, no
  borrado), `test_adaptive_e2e_v369.py`, las baterías pedagógicas `*_v370.py`,
  `test_decision_v368.py`, los 75 tests del launcher y los ~661 de vitest.

## Criterios de salida

1. El backend sirve `frontend/dist` (assets + fallback) y **degrada con
   elegancia** si el artefacto no existe.
2. El certificado TLS se genera de forma determinista e idempotente, con los
   SANs necesarios para LAN y mDNS, y **no** se versiona.
3. El launcher arranca **un solo origen HTTPS en `:8000`**, construye el `dist`
   si falta y da un mensaje accionable si no hay Node.
4. La UI **avisa y pide consentimiento** antes de descargar una voz y **declara**
   cuando la voz es degradada, sin tragar errores de TTS.
5. F2, F3 y F4 cerrados con test; «por qué esta actividad» disponible donde
   falta.
6. AE-04 declarado o re-declarado con fase; AE-06 unificado preservando la
   equivalencia.
7. Las 50 claves huérfanas eliminadas y el informe regenerado.
8. Los tests nuevos **verdes** y el total de `pytest`/`vitest` es anterior +
   nuevos; `ruff`, `tsc`, `build`, launcher y gates de script OK.
9. **CI verde** (8/8 jobs, con el job nuevo `product-origin` que arranca uvicorn
   con TLS sobre el `dist` construido y comprueba el origen de producto), registrado con su
   run id.
10. La release note declara **honestamente** el diff de producto y lo que la
    release **no** demuestra.

## Fuera de alcance (deuda declarada)

- **Progreso real de descarga** (exigiría rediseñar el endpoint bloqueante).
- **RA-02** (endpoint de Ollama sin declarar), **RA-05** (corte de red real),
  **RB-05** (máquina limpia real) y **G5** (matriz de dispositivos): acción
  humana.
- **Los 33 hallazgos de V3.70** (contenido → `V4.0.x`; motor → Planner 4.0) y los
  **6 P2 de V3.69**.
- **Sesgo posicional/longitud de los ítems MC** (fix mecánico que requiere
  aprobación explícita).
- **RD-05** (caché negativa de voces volátil).
- **Empaquetado/distribución** (vetado) y **multiplataforma** (el launcher es
  solo Windows).
- **Planner 4.0** y calibración con tráfico real.
- **V3.73** auditoría final técnica → **V4.0**.

## Cierre (higiene de release)

`check_release_consistency.py` usa **la primera coincidencia**: insertar arriba.

1. `backend/config.py` → `VERSION = "3.71.0"` → `"3.72.0"` (**fuente única**).
2. `frontend/package.json` → `"version"`.
3. `frontend/package-lock.json` (y la copia de la línea 9).
4. `README.md` → «Última versión estable: **v3.72.0**» + re-declarar la
   instalación/arranque (un solo origen HTTPS).
5. `CHANGELOG.md` → `## [3.72.0] — <fecha>` **en la cabecera**.
6. `PLAN.md` → bullet primero de «Estado actual» + `### M13` (marcar V3.72 hecho y
   mover la flecha a **V3.73**) + tablero de briefings.
7. `docs/RELEVO.md` → **nota nueva encima** + fecha + refrescar «0. START HERE».
8. `release-notes-v3.72.0.md` (nuevo, raíz) con contexto, ejes, tabla de
   hallazgos, tests, **§Honestidad** y **§Fuera de alcance**.
9. `docs/audit/PARKED.md` → registrar lo deliberadamente **no** arreglado y
   retirar lo cerrado.
10. **No** tocar `DECISION_POLICY_VERSION` ni `GENERATOR_VERSION`.

Verificación local antes de commitear: `ruff`, `pytest`, `tsc`, `vitest`,
`build`, launcher, `check_release_consistency`, `check_beta_v3`,
`content_validation` y `transfer_validation`. Después: commit de release + tag
anotado `v3.72.0` + push, y registrar el run de **CI** en la nota de
`docs/RELEVO.md`.
