# Kit de validación — los 7 gates de la puerta de V4.0

> **Naturaleza:** planilla de **campo**. No es un protocolo nuevo ni sustituye a
> ninguno: **referencia** los protocolos existentes (RA, RB, `DEVICE_MATRIX`,
> `F-UX-JOURNEY`, `CONSTITUCION-PEDAGOGICA`) y añade lo único que faltaba para
> ejecutarlos: **pre-vuelo, orden por sesión y el comando `record` exacto de cada
> gate**.
> **Companion de:** `docs/audit/VALIDATION-RELEASE-V373.md` (el runbook, que
> define los 7 gates y cómo se usa el instrumento).
> **Puerta de V4.0:** `python scripts/validation_gate.py status --strict` debe
> salir **0** (los 7 gates en `pass`) y, con el árbol congelado,
> `status --strict --same-tree` debe salir **0** también: la puerta fuerte exige
> que la evidencia **sea de este mismo commit**.
> **Estado de partida (2026-09-17, `v3.73.2`):** `auto` **10/10** · 7 gates
> `pending`. Nada de esta planilla está ejecutado todavía.

**Regla de oro:** un gate no se cierra con una opinión. Se cierra con `record`, y
**sin `--notes` el instrumento rechaza el registro**. Un `fail` o un `skip` son
resultados válidos y **se registran con su motivo**; lo prohibido es declarar
`pass` sin haberlo hecho.

---

## A · Pre-vuelo (una vez, antes de tocar hardware)

Se ejecuta en el **árbol congelado** que se va a validar. Si el árbol cambia
después, los gates quedan marcados como «grabado en vX» y hay que repetirlos.

```powershell
# 1. El artefacto de la UI y las comprobaciones estáticas (debe dar 10/10)
cd frontend
npm run build
cd ..
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist

# 2. Identidad del árbol que se sella en cada `record`
Select-String -Path backend\config.py -Pattern '^VERSION ='
git rev-parse HEAD
git status --short          # debe estar limpio

# 3. Manifiesto offline: nada ausente (RA-RUNTIME-OFFLINE.md §5, preparación)
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit   # E3: "Ausentes: 0"
.venv\Scripts\python.exe download_models.py --check
cd ..
```

**Anotar aquí:**

| Dato | Valor |
|---|---|
| `VERSION` | |
| `HEAD` (SHA) | |
| Run de CI que publicó ese commit (id numérico) | |
| Fecha de la sesión | |
| Equipo / SO | |
| Modelo de Ollama instalado (`ollama list`) | |

**URLs de producto** (desde V3.72 solo hay **un** origen; el puerto `5173` es el
dev server de Vite y **no** forma parte del runtime de producto):

- Local: `https://localhost:8000`
- LAN: `https://<ip>:8000` (la muestra el launcher; también sirve
  `https://<hostname>.local:8000` si `local_url_available` es `true`)

**Recordatorio del instrumento:** `record` sella estado, notas, fecha UTC, la
`VERSION` del árbol, **el commit validado (`head_sha`)** y, con `--ci-run <id>`,
la run de CI que lo publicó: la cadena `commit → run → gates` queda dentro de la
evidencia. Un **`pass` sin commit no se registra** (sin git en el árbol, el
registro se rechaza); `fail`/`skip`/`pending` sí se pueden registrar sin SHA,
porque declaran un no-cierre. El `<run>` de los comandos de esta planilla es el id
anotado en la tabla de arriba. La comprobación 10 de `auto` valida después que la
evidencia no tenga gates ni estados inventados ni notas vacías, y que el `pass`
traiga `head_sha` con formato de commit.

---

## B · Orden de ejecución recomendado

Cada sesión cierra **varios** gates: se agrupan por lo que exigen (hardware,
red, tiempo), no por número.

```mermaid
flowchart LR
    P["Pre-vuelo: build + auto 10/10"] --> S1["Sesion Windows: G3 + G5"]
    S1 --> S2["Sesion sin red: G1"]
    S2 --> S3["Sesion recorridos: G6"]
    S3 --> S4["Sesion dispositivos: G4"]
    S4 --> S5["Otra maquina / VM: G2"]
    S5 --> S6["Despacho con instrumentos: G7"]
    S6 --> Cierre["status --strict == 0 → V4.0"]
```

| Sesión | Gates | Por qué van juntos |
|---|---|---|
| 1 · Windows real | G3 + G5 | La misma sesión con launcher, micrófono y altavoces reales cubre los tres |
| 2 · Sin red | G1 | Exige cortar Wi-Fi **y** Ethernet: no se puede combinar con nada que necesite red |
| 3 · Recorridos | G6 | Recorrido largo por la UI; necesita la app estable y un perfil con datos |
| 4 · Dispositivos | G4 | Móvil/tablet sobre la LAN: mismo servidor, otro hardware |
| 5 · Otra máquina/VM | G2 | Es la única que exige un sistema **físicamente limpio** |
| 6 · Despacho | G7 | Es lectura de contenido e instrumentos; no necesita la app arrancada |

---

## C · Hoja por gate

### G1 · `offline-fisico` — los 12 flujos con la red cortada

- **Protocolo:** `docs/audit/RA-RUNTIME-OFFLINE.md` §5 (tabla E5).
- **Precondiciones:** pre-vuelo completo; manifiesto de modelos **sin ausentes**;
  Ollama con el modelo por defecto descargado.
- **Pasos:**
  1. Anotar el manifiesto (`runtime-audit` + `download_models.py --check`).
  2. **Desconectar Wi-Fi y Ethernet** (no basta desactivar el DNS: se buscan
     dependencias de Internet, no resolución de nombres).
  3. Arrancar con el launcher y abrir `https://localhost:8000`.
  4. Ejecutar los 12 flujos y anotar ✅/⚠️/❌ en la tabla E5 del dossier:
     `frontend`, `backend`, `SQLite`, `Ollama`, `Whisper`, `Piper`, `dictionary`,
     `TTS`, `STT`, `course`, `practice`, `review`.
  5. `backend`: `GET /api/health` y `GET /api/health/ready` (5xx o timeout =
     FALLO).
- **FALLO:** un flujo que no funciona y **no se declara**. Un solo FALLO no
  declarado invalida el gate. Si falta una voz/modelo, anotar el **tiempo de
  espera** (RA-03/RD-01 lo acotan, pero se mide).
- **Evidencia a capturar:** los 12 veredictos con fecha y `VERSION`; los logs de
  los flujos degradados.
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record offline-fisico pass --ci-run <run> `
  --notes "12/12 flujos OK con Wi-Fi y Ethernet desconectados (v3.73.2); Whisper/Piper desde disco, dictionary no cacheada degrada sin colgarse"
```

### G2 · `maquina-limpia` — instalación desde cero

- **Protocolo:** runbook de `README.md` · `docs/audit/RB-INSTALACION.md`.
- **Precondiciones:** un **clon o sistema recién instalado** (otra máquina o VM),
  sin `backend/models/` ni `frontend/dist/` (no se versionan).
- **Pasos:**
  1. Python + `requirements.txt` + `requirements-dev.txt`.
  2. Ollama instalado y `ollama pull llama3.1:8b` (**paso manual**: el proyecto no
     lo verifica).
  3. `download_models.py --check` **antes** de descargar, y después
     `download_models.py` (~1,1 GB: Piper EN+ES ~120 MB + Whisper `small`
     927 MB).
  4. `npm run build` (**Node/npm son requisito de COMPILACIÓN**, no de ejecución:
     con el `dist` construido la app arranca sin Node — RC-01, V3.72).
  5. Arrancar desde el launcher y abrir `https://localhost:8000`.
- **FALLO:** cualquier paso tácito (algo que hubo que hacer a mano y el runbook no
  decía), o el arranque sin `dist` sin mensaje accionable.
- **Evidencia a capturar:** qué se instaló, qué falló, qué se hizo a mano y
  cuánto tardó la descarga.
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record maquina-limpia pass --ci-run <run> `
  --notes "Clon limpio en VM Windows: Python+deps, ollama pull llama3.1:8b, download_models.py (~1,1 GB), npm run build y launcher OK; ningun paso tacito"
```

### G3 · `launcher-windows` — Windows real

- **Protocolo:** `release-notes-v3.73.0.md` §Verificación (bloque C).
- **Precondiciones:** `frontend/dist` construido (el launcher lo construye si
  falta, pero con Node instalado); firewall permitiendo **solo** el `:8000`.
- **Pasos:** `start → HTTPS en :8000 → abre el navegador → micrófono → TTS →
  STT → chat → persistencia` (cerrar y reabrir: el estado sigue).
- **Por qué no lo cubre el CI:** el job `launcher-windows` prueba el launcher y
  `product-origin-windows` el origen de producto sobre HTTPS, pero **ninguno**
  prueba un navegador real ni el micrófono.
- **FALLO:** arranque que no llega a servir la UI, o cualquiera de los pasos que
  no funcione con el navegador y el micrófono reales.
- **Evidencia a capturar:** capturas del arranque y de la URL LAN mostrada; el
  flujo completo en el orden indicado.
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record launcher-windows pass --ci-run <run> `
  --notes "Launcher en Windows 11: start, HTTPS :8000, navegador, microfono, TTS, STT, chat y persistencia tras reinicio OK"
```

### G4 · `dispositivos` — móvil y tablet

- **Protocolo:** `docs/DEVICE_MATRIX.md` (matriz de hardware **y** matriz de
  interacción).
- **Precondiciones:** dispositivo en la **misma Wi-Fi**; certificado autofirmado
  aceptado (Android: Avanzado → Continuar; iPhone/iPad: ajustes de Safari).
- **Pasos:** cubrir las filas de la matriz de hardware (HTTPS, mDNS, micrófono,
  audio, listening, speaking, **recuperación de permiso sin recargar**) y la
  matriz de interacción (touch/tap targets, viewport y scroll, teclado en
  pantalla, orientación).
- **FALLO:** **no basta con capturas.** Un micrófono que no captura, una
  actividad que pierde estado al rotar o un permiso que no se refleja sin
  recargar son FALLO.
- **Evidencia a capturar:** qué dispositivos/navegadores se probaron, resultados
  y notas de cada celda; copiar el resultado a `DEVICE_MATRIX.md`.
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record dispositivos skip --ci-run <run> `
  --notes "Pendiente: no hay dispositivo movil fisico disponible en esta sesion (accion humana)"
```

### G5 · `audio-stt-tts` — voz de verdad

- **Precondiciones:** micrófono y altavoces reales; voces Piper en disco.
- **Pasos:**
  1. Una grabación y transcripción reales (una actividad de speaking).
  2. Una reproducción real (TTS en inglés **y** español).
  3. Provocar/observar el **aviso de voz degradada** (`DegradedVoiceNotice`) y
     comprobar que muestra la voz **realmente usada**.
- **FALLO:** transcripción vacía, silencio, o degradación silenciosa (si la voz
  cae a una peor, el alumno **debe** enterarse: V3.72 lo hizo observable).
- **Evidencia a capturar:** el texto transcrito, el idioma/voz usada y la captura
  del aviso si aparece.
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record audio-stt-tts pass --ci-run <run> `
  --notes "Grabacion+transcripcion reales OK; TTS en EN y ES OK; aviso de voz degradada mostro la voz realmente usada"
```

### G6 · `journeys` — todos los recorridos

- **Protocolo:** `docs/audit/F-UX-JOURNEY.md` (incluye el protocolo de «usuario
  real» de ~25 min como referencia de observación).
- **Precondiciones:** perfil con datos (al menos una semana de uso idealmente).
- **Pasos:** recorrer de principio a fin Home, Today, Curso, Aprender, Listening,
  Vocabulary, Grammar, Reading, Speaking, Conversation, Review y Progress.
- **FALLO:** un recorrido que no se puede completar, o el «por qué esta
  actividad» (`WhyThisActivity`) ausente donde el motor lo declara.
- **Evidencia a capturar:** recorrido, incidencia y si el «por qué» aparece.
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record journeys pass --ci-run <run> `
  --notes "12 recorridos completos sin bloqueo; el porque de la actividad aparece en Home, NextStep y cola de repaso"
```

### G7 · `pedagogia` — auditoría final del contenido

- **Protocolo:** `docs/CONSTITUCION-PEDAGOGICA.md` ·
  `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`.
- **Pasos:** regenerar los instrumentos de solo lectura y revisar la matriz de
  hallazgos:

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier corpus-stats
.venv\Scripts\python.exe -m scripts.audit_dossier curriculum-stats
.venv\Scripts\python.exe -m scripts.audit_dossier speaking-stats
.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.venv\Scripts\python.exe -m scripts.audit_dossier cefr-adequacy
.venv\Scripts\python.exe -m scripts.audit_dossier skill-coverage
.venv\Scripts\python.exe -m scripts.audit_dossier feedback-coverage
.venv\Scripts\python.exe -m scripts.audit_dossier mastery-claims
.venv\Scripts\python.exe -m scripts.audit_dossier assessment-instruments
```

- **Qué se mide:** léxico (frecuencia, utilidad, CEFR, colocaciones, phrasal
  verbs, chunks), gramática (progresión, errores frecuentes, contrastes,
  transferencia), listening (bottom-up/top-down, connected speech, cloze,
  dictation, shadowing, acentos, velocidad) y speaking (inteligibilidad,
  pronunciación, fluidez, interacción, reparación).
- **Candado conceptual:** **no** convertir «número de palabras conocidas» en
  «nivel CEFR» (regla **R3** de la constitución). El nivel estimado es interno y
  se declara como tal.
- **FALLO:** una afirmación de maestría sin evidencia que la respalde (reglas
  R1–R7), o una propiedad declarada que los instrumentos desmientan.
- **Evidencia a capturar:** veredicto por eje con las cifras regeneradas; lo que
  la medición **no demuestra** se anota como tal (no como incumplimiento).
- **Registro:**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record pedagogia pass --ci-run <run> `
  --notes "9 instrumentos regenerados; contenido en banda, sin afirmaciones sin evidencia; vocabulario NO se presenta como nivel CEFR"
```

---

## D · Cierre

```powershell
# Estado legible (informa siempre)
backend\.venv\Scripts\python.exe scripts\validation_gate.py status

# La puerta real de V4.0: sale 0 solo con los 7 gates en `pass`
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict

# La puerta fuerte: además, la evidencia tiene que ser de ESTE commit
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict --same-tree
```

- **7/7 en `pass`** → V4.0 puede declararse (y `auto` debe seguir en 10/10). Si
  además `--same-tree` sale **0**, los siete gates se probaron contra el **mismo
  commit**: es la forma de cierre que exige la certificación de V4.0.
- **Algún `fail`** → se **deja registrado con su motivo** y se abre incidencia;
  no se reescribe a `pass`. El gate se puede volver a registrar cuando se
  corrija.
- **Algún `skip`** → el gate **no está cerrado**; `status --strict` seguirá
  saliendo 1. Un `skip` es honesto, no un cierre.

```mermaid
flowchart LR
    R["record de cada gate"] --> A["auto verifica la evidencia"]
    A --> ST["status"]
    ST --> STR{"status --strict"}
    STR -->|"0"| ST2{"status --strict --same-tree"}
    STR -->|"1"| Pend["Quedan gates sin pass: repetir la sesion que falte"]
    ST2 -->|"0"| V4["V4.0 declarable: 7 gates contra el mismo commit"]
    ST2 -->|"1"| Rep["Evidencia de otro commit: repetir el gate en el arbol congelado"]
```

---

## E · Lo que este kit NO es

- **No ejecuta** ningún flujo de la app: los ejecuta una persona.
- **No puede** simular el corte de red, Windows real, un móvil real ni un
  micrófono real.
- **No sustituye** a los protocolos: si un protocolo cambia, manda el protocolo
  (este kit solo lo ordena y lo registra).
- **No cierra** ningún gate por sí mismo: la verdad es la que registra el
  instrumento en `docs/audit/validation-evidence.json`.
