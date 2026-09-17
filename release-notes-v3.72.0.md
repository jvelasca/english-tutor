# v3.72.0 — UX / product completion

> **Fecha:** 2026-09-17 · **Tag:** `v3.72.0` · **Versión de app:** `3.71.0 → 3.72.0`.
> **Naturaleza de la release:** **PRODUCTO**. SIN migración de BD, SIN bump de
> `GENERATOR_VERSION`, SIN bump de `DECISION_POLICY_VERSION`, SIN tocar el banco y
> SIN tocar el currículum.
> **Cierra:** `RC-01` (servido real de la UI) · `RD-04` + mitad de `RA-01`
> (consentimiento/aviso de voz) · `F2` · `F3` · `F4` · claves i18n huérfanas ·
> `AE-06`; **re-declara con fase** `AE-04` (divulgación en UI → V4.0.x).
> **Dossiers:** `docs/audit/RC-RUNTIME-PRODUCTO.md` (cierre) ·
> `F-UX-JOURNEY.md` · `AE-PED-INSTRUMENTOS.md` · `PARKED.md` ·
> `docs/audit/generated/i18n-report.md`.
> **Briefing de ejecución:** `agentes/v372-ux-product-completion.md`.

## Contexto

V3.69 validó la **arquitectura** del motor adaptativo, V3.70 midió su
**pedagogía** y V3.71 midió el **suelo físico** (qué toca Internet, qué necesita
la máquina). Las tres releases dejaron, en vez de promesas, una lista corta de
cosas **fechadas**: dos ítems que la propia V3.71 se asignó a V3.72 (`RC-01` y el
vector UI del P1 de TTS/offline), tres hallazgos que V3.70 asignó a esta fase
(`AE-04`, `AE-06`) y la deuda UX que `PARKED.md` venía arrastrando (`F2`, `F3`,
`F4`, claves i18n huérfanas, «por qué esta actividad»).

V3.72 las cierra con un hilo conductor: **que el producto se sirva de verdad, que
diga la verdad sobre lo que descarga y suena, y que el alumno entienda qué hace y
por qué**.

**Regla de todo el incremento:** nada de «cerrado en falso». Lo que no se puede
cerrar de verdad (porque exige una pantalla que no existe, un progreso real que el
endpoint no puede dar, o hardware humano) se **re-declara con fase y con un
candado que falla el día que exista la superficie**.

## A · UA — Servido real de la UI (`RC-01`, cerrado)

**El hallazgo (V3.71).** La interfaz la servía el **dev server de Vite** y el
backend **no** montaba `frontend/dist`: el artefacto de producción **existía y no
lo servía nadie**. Consecuencia declarada y fijada por test: **Node + npm eran
requisito de EJECUCIÓN** del producto.

**Lo que cambia.**

- **El backend sirve el artefacto** (`backend/services/frontend_dist.py`):
  `/assets` con `StaticFiles` y **fallback SPA** (`/{full_path:path}` →
  `index.html`) montado **al final**, para que los routers `/api/*` conserven
  prioridad. Es **fail-open**: sin `dist` no se monta nada y el arranque **no se
  rompe** (el backend sigue siendo útil solo-API). La raíz pasa a ser la UI, así
  que los **metadatos del servicio se mueven de `/` a `/api`**
  (`backend/routers/models.py`).
- **TLS autofirmado determinista** (`backend/services/tls_cert.py` +
  `backend/scripts/ensure_tls_cert.py`, dependencia nueva **`cryptography`**):
  genera cert+clave **idempotentes** con los SANs que hacen falta
  (`localhost`, `127.0.0.1`, `<hostname>`, `<hostname>.local` y la IP de LAN),
  detecta cobertura incompleta y **renueva** en ese caso. Vive en
  `backend/data/certs/` y **no se versiona**.
  **Por qué es obligatorio:** en HTTP por LAN `navigator.mediaDevices` es
  `undefined` y **el micrófono se rompe**; servir en HTTPS no es una preferencia,
  es un requisito funcional.
- **Un solo proceso** (`launcher/`): `backend_command()` añade
  `--ssl-certfile/--ssl-keyfile`, desaparece `start_frontend()`, aparece
  `ensure_frontend_dist()` (compila con `npm run build` **si falta**, con mensaje
  accionable si no hay Node) y el launcher pasa de orquestar **dos** procesos a
  **uno**. `allow-firewall.ps1` abre **solo el 8000**.
- **Orígenes y puerto únicos:** `ALLOWED_ORIGINS` incorpora
  `https://localhost:8000` / `http://localhost:8000`; `routers/network.py` pasa
  `FRONTEND_PORT` de 5173 a **8000**, así que el QR de `ConnectDeviceCard` apunta
  al origen real de producto.
- **Modo dev preservado:** `npm run dev` + proxy de Vite y `.vscode/launch.json`
  (ahora con «App completa HTTPS :8000 (producto)» y «Desarrollo con HMR») siguen
  funcionando para HMR.

**Lo que se gana, dicho con precisión.** **Node deja de ser requisito de
EJECUCIÓN**: no hace falta `npm run dev` para usar el producto, y hay **un
proceso menos** que puede caerse. **No** se gana un «producto empaquetado»: el
`dist` **no se versiona** y en un clon limpio hay que compilarlo (o dejar que el
launcher lo haga), así que Node **sigue siendo requisito de instalación /
compilación**. Esa es la afirmación honesta, y es la que queda escrita en
`docs/audit/RC-RUNTIME-PRODUCTO.md` §Cierre y `docs/PREMISAS.md` §3.

**Candados.** `backend/tests/test_serve_frontend_v372.py` (index.html, assets,
fallback SPA, prioridad de `/api`, fail-open, no-escape del artefacto),
`backend/tests/test_tls_cert_v372.py` (generación, idempotencia, SANs, renovación)
y `backend/tests/test_docs_drift_v372.py` (que PREMISAS/ARQUITECTURA/README/BETA_GATES
declaren la frontera nueva, que el launcher **no** lance Vite en producto, que el
firewall abra **solo** el 8000 y que el CI pruebe el servido estático por HTTPS).
El job **`product-origin`** del CI arranca `uvicorn` con el certificado sobre el
`dist` construido y comprueba que la **raíz devuelve HTML de la UI** ⇒ **CI 8/8**.

## B · RD/RA — Voz/TTS en la UI (el vector que V3.71 fechó)

**El hallazgo (V3.71).** El backend ya hacía **observable** la degradación
(`X-TTS-Voice`/`X-TTS-Degraded`, expuestas por CORS) y **la UI no las leía**: si el
sistema caía a una voz peor, el alumno **no se enteraba**; y la descarga de una
voz (~60 MB, la única dependencia de Internet en ruta de producto) se disparaba
**sin preguntar**.

**Lo que cambia.**

- **El cliente dice la verdad** (`frontend/src/api/voz.ts`): `speak()` deja de
  devolver `void` y devuelve `{voice, degraded}`, y **aborta de verdad**
  (`AbortController` + `timeoutMs`; el `withTimeout` de `api/client.ts` **no
  cancelaba el `fetch`**, solo dejaba de esperar).
- **Consumo centralizado** (`frontend/src/hooks/useVoiceDownload.ts`):
  `speakWithVoice()` es el único camino y orquesta consentimiento → `speak()` →
  aviso de degradación. Los **siete** puntos de TTS (`ListenButton`,
  `SpeakButton`, `MicrophoneTest`, `useHandsFree`, `ListeningPractice`,
  `SpeakingRoutesPractice`, `ConversationTranslator`) pasan por él.
- **Aviso no bloqueante de voz degradada** (`useDegradedVoice` +
  `DegradedVoiceNotice`, `role="status"`): informa **con la voz realmente usada**,
  se auto-descarta y **no interrumpe** la práctica.
- **Consentimiento de descarga** (`VoiceDownloadDialog`): antes del primer TTS de
  un idioma **sin voz instalada** se explica qué se va a descargar, cuánto ocupa
  (~60 MB), que es **una sola vez** y que **necesita Internet**, y se pide
  permiso. El progreso es **indeterminado** (spinner): el endpoint es **síncrono y
  bloqueante**, así que un progreso real exigiría rediseñarlo (fuera de alcance,
  declarado).
- **El auto-download implícito desaparece:**
  `ConversationTranslator.tsx` ya no descarga voces por su cuenta; pasa por el
  mismo flujo de consentimiento.

**Candados.** `frontend/src/api/voz.test.ts` (parseo de cabeceras, degradación
ausente cuando no hay cabeceras, aborto), `useVoiceDownload.test.ts` (consentimiento
una sola vez, cancelación, fallo de catálogo **fail-open**, fallo de descarga,
TTS simultáneos compartiendo una sola pregunta, propagación de la degradación),
`VoiceDownloadDialog.test.tsx`, `DegradedVoiceNotice.test.tsx` y
`ListenButton.test.tsx`.

## C · UX — Deuda declarada (`F2`/`F3`/`F4`, i18n y «por qué esta actividad»)

- **F4 — paneles que se tragaban los errores.** `FsrsReviewPanel`,
  `EvidenceGraphPanel` y `AssessmentLadder` tenían un `catch` **vacío**: si el
  backend no respondía, la sección quedaba **en blanco y muda**. Ahora usan
  `PanelState` (`loading → error → retry`), el mismo patrón que Home, con
  `common.unavailable` y `common.retry`.
- **F2 — el readiness se leía dos veces.** Home mostraba la tríada y además la
  tarjeta inferior, con dos lecturas del mismo dato. Ahora Home lo lee **una sola
  vez** (manda `TodayPlan`) y la tríada queda para **Progress**. Fijado por test
  (`HomeScreen.test.tsx`, `TodayPlan.test.tsx`).
- **F3 — «estás aquí».** La cabecera de Home ancla el nivel con
  `home.youAreHere` junto al badge de nivel estimado y muestra `home.yourTarget`
  con el objetivo del perfil, para que la posición en la ruta deje de ser un
  número suelto.
- **i18n — 0 huérfanas.** El checker se ha vuelto **fiable con las familias
  dinámicas** (`_TPL_ANY` para plantillas y `_NS_LIT` para namespaces declarados),
  lo que reveló que el residuo real eran **10 claves**, no 50: la cifra de la
  auditoría incluía **falsos positivos de claves vivas**. Se han eliminado las 10
  (más las dos que el flujo de consentimiento sustituye), se ha regenerado
  `docs/audit/generated/i18n-report.*` y el checker corre en **`--strict` dentro
  del CI**, con un test de deriva que falla si vuelven las huérfanas.
- **«Por qué esta actividad», extendido donde faltaba.** El `why` que el motor
  **ya declaraba** solo se pintaba en la tarjeta de inicio (y el `fsrs.whyReason`
  en su panel). Ahora una **sola pieza compartida**
  (`frontend/src/components/WhyThisActivity.tsx`, variantes `full`/`compact`)
  lo pinta también en el **pie «Next» de cada práctica** (`NextStep`) y en las
  **filas de la cola de repaso**, **sin recalcular señales en el cliente**
  (premisa 21): si el servidor no manda `why` ni `because`, **no se pinta nada**
  (no se inventa una explicación).

## D · AE — Instrumentos (`AE-04` divulgado, `AE-06` cerrado)

- **AE-04 (P2) — el placement mide reconocimiento, no producción.** El
  instrumento se presentaba sin declarar su límite. Ahora la limitación
  («mide reconocimiento/meta-lenguaje; **no** captura producción libre ni audio»)
  está en la **descripción del instrumento** (`backend/curriculum/assessments.json`),
  en el **contrato** (`PlacementTest`) y por tanto en la respuesta de
  `GET /api/academy/placement`. **Verificado:** hoy **ningún componente** consume
  ese endpoint, así que **no existe pantalla** donde divulgarlo; la divulgación en
  UI queda **declarada con fase → V4.0.x** y protegida por un **candado
  tripwire** (`test_ninguna_superficie_consume_el_placement_sin_divulgarlo`) que
  **falla el día** que alguien empiece a mostrar el resultado sin divulgar.
- **AE-06 (P2) — umbrales de banda triplicados.** El corte de banda vivía
  **tres veces** (`adaptive.py`, `academy.py`, `cefr.py`). Ahora hay **un solo
  módulo** (`backend/services/cefr.py`: `BAND_BOUNDARIES` + `level_for_numeric`,
  con `numeric_for_score`/`score_for_numeric`) y los tres estimadores **delegan**;
  la equivalencia se fija por test (**0 desacuerdos** en la rejilla).
  **Sub-bandas `+`:** se **retiran de la emisión** (ningún estimador las producía y
  el badge muestra la etiqueta discreta), pero **siguen existiendo** como
  **descriptores de contenido** y como posición en `cefr_descriptors.band_for_numeric`.
  **`pre-a1`:** conserva su emisor (`estimated_level` cuando **no hay evidencia**).
  Candado: `backend/tests/test_band_thresholds_v372.py`, que además impide que el
  corte vuelva a duplicarse fuera de `cefr.py`.

## Tabla de cierre (lo que V3.71/V3.70 dejaron abierto)

| Ítem | Origen | Estado en V3.72 |
|---|---|---|
| `RC-01` Node/npm requisito de **ejecución** | V3.71 (condición de salida) | **Cerrado**: el backend sirve el `dist` por HTTPS en `:8000`; Node pasa a requisito de **compilación** |
| `RD-04` / mitad de `RA-01` (UI de voz) | V3.71 (fase V3.72) | **Cerrado**: cabeceras consumidas, aviso de degradación, consentimiento de descarga |
| `F4` paneles mudos | `PARKED.md` | **Cerrado**: `PanelState` en los tres paneles |
| `F2` readiness duplicado | `PARKED.md` | **Cerrado**: una sola lectura en Home |
| `F3` «estás aquí» | `PARKED.md` | **Cerrado**: `home.youAreHere` + objetivo |
| i18n huérfanas | `PARKED.md` (decía ~50) | **Cerrado**: 10 reales eliminadas, checker `--strict` en CI |
| «Por qué esta actividad» | `F-UX-JOURNEY.md` Q5 | **Cerrado (extensión)**: `WhyThisActivity` en Next y en la cola de repaso |
| `AE-06` umbrales de banda | V3.70 (P2) | **Cerrado**: un solo módulo, equivalencia fijada por test |
| `AE-04` divulgación del placement | V3.70 (P2) | **Divulgado** en el instrumento/contrato; **UI con fase → V4.0.x** y candado tripwire |
| `RA-05` corte de red real | V3.71 | **Abierto — acción humana** |
| `RB-05` máquina físicamente limpia | V3.71 | **Abierto — acción humana** |
| `G5` matriz de dispositivos | V3.71 | **Abierto (10/10 en ⬜) — acción humana** |
| `RA-02` endpoint de Ollama no declarado | V3.71 | **Abierto** (deuda declarada) |
| Empaquetado / instalador | Vetado (premisa) | **Fuera de alcance** |

## Honestidad — lo que V3.72 NO demuestra

1. **El certificado es autofirmado.** El navegador **avisará** la primera vez
   (exactamente igual que antes con Vite) y aceptarlo es un paso del usuario. No
   es un fallo: **sin HTTPS no hay micrófono en LAN**, porque
   `navigator.mediaDevices` es `undefined` fuera de contexto seguro.
2. **`RC-01` se cierra como «Node no es requisito de EJECUCIÓN»**, no como
   «producto empaquetado y distribuible». El `dist` no se versiona: en un clon
   limpio **hay que compilarlo** (a mano o vía launcher) y eso exige Node. La
   promesa «sin Node» solo es cierta **una vez compilado**.
3. **El progreso de descarga de voz es indeterminado.** El endpoint de descarga es
   **síncrono y bloqueante**; esta release entrega **consentimiento, aviso y
   progreso indeterminado**, no un progreso real. Un progreso real exige rediseñar
   el endpoint (declarado fuera de alcance).
4. **`AE-04` no se muestra en UI** porque **no hay pantalla** que muestre el
   resultado del placement. La divulgación vive en el instrumento y su contrato,
   con un candado que forzará el trabajo en cuanto exista superficie. **No** se
   puede afirmar «el usuario ya sabe que el placement no mide producción».
5. **`RA-05`, `RB-05` y `G5` siguen siendo acción humana.** No se ha desconectado
   la red de verdad, no se ha instalado en una máquina físicamente limpia ni se ha
   probado en 10 dispositivos. Nada de eso se puede simular en CI con honestidad.
6. **No hay empaquetado ni instalador** (vetado por premisa) y **el launcher es
   solo Windows**.
7. **No hay capacidad pedagógica nueva**: V3.72 no toca el banco, el currículum ni
   los umbrales de decisión del Planner. Es una release de **producto y UX**.

## Fuera de alcance (deuda declarada, no olvidada)

- Progreso **real** de descarga de voz (rediseño del endpoint a streaming/chunks).
- Pantalla de **nivelación/onboarding** que muestre el resultado del placement
  (obligará a la divulgación de `AE-04`; el candado ya existe).
- Endurecer `RA-02` (endpoint de Ollama declarado en `config.py`).
- Empaquetado/multiplataforma y launcher para macOS/Linux.

## Verificación

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q      # 2694 passed
.venv\Scripts\python.exe -m ruff check .

# Frontend
cd ..\frontend
npx tsc --noEmit
npx vitest run                                     # 699 passed (83 ficheros)
npm run build                                      # genera frontend/dist

# Launcher (un solo proceso HTTPS :8000)
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q   # 93 passed
..\backend\.venv\Scripts\python.exe -m ruff check .

# Humo del origen de producto (lo que hace el job product-origin del CI)
cd ..\backend
.venv\Scripts\python.exe -m scripts.ensure_tls_cert
.venv\Scripts\python.exe -m uvicorn main:app --port 8000 `
    --ssl-certfile data\certs\cert.pem --ssl-keyfile data\certs\key.pem
# y en otra terminal: curl -k https://127.0.0.1:8000/ | Select-String "<html"

# Gates de release
cd ..
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict   # 0 huérfanas
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py
```

## Roadmap

- **V3.73 / V4.0** — la deuda que esta release deja declarada: pantalla de
  nivelación (con la divulgación de `AE-04` que su candado ya exige), progreso real
  de descarga, `RA-02` y, si el gerente lo prioriza, el paquete distribuible que
  haría literal el «sin Node».
- **Acción humana pendiente, fuera del código:** `RA-05` (corte de red real),
  `RB-05` (instalación en máquina limpia) y `G5` (matriz de dispositivos).
