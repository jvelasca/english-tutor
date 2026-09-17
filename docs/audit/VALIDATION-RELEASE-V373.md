# V3.73 — Release de validación (runbook de los 7 gates)

> **Naturaleza:** V3.73 es una release de **validación**, no de producto. Cierra
> el endurecimiento que la auditoría de V3.72 dejó como P2/P3 (fail-closed del
> runtime de producto y descubrimiento de IP de LAN sin referencias externas) y
> construye el instrumento que convierte los siete gates de validación física en
> **evidencia registrada**.
> **Regla:** un gate no se cierra con una opinión. Se cierra con `record`, y un
> `fail`/`skip` **exige notas**.
> **Puerta de V4.0:** `python scripts/validation_gate.py status --strict` debe
> salir 0 (los 7 gates en `pass`).

## Por qué existe este instrumento

V3.72 declaró honestamente cinco bloques de validación como **acción humana**:
corte de red real (`RA-05`), instalación en máquina limpia (`RB-05`), prueba en
Windows real, matriz de dispositivos (`G5`) y audio real. El riesgo de dejarlos
en prosa es conocido: se olvidan, o alguien los declara cerrados sin haberlos
hecho. Este runbook y `scripts/validation_gate.py` existen para eso.

## Cómo se usa

```powershell
# 1. Comprobaciones automáticas (estáticas: no arrancan la app)
#    Tras `npm run build` para certificar también el artefacto:
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
#    → docs/audit/generated/release-validation.{md,json}

# 2. Ejecutar un gate humano y registrar el resultado
backend\.venv\Scripts\python.exe scripts\validation_gate.py record offline-fisico pass `
    --notes "12/12 flujos OK con Wi-Fi y Ethernet desconectados (v3.73.0)"

# 3. Consultar el estado (y la puerta de V4.0)
backend\.venv\Scripts\python.exe scripts\validation_gate.py status
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict
```

Ids válidos: `offline-fisico`, `maquina-limpia`, `launcher-windows`,
`dispositivos`, `audio-stt-tts`, `journeys`, `pedagogia`.

## Los 7 gates

### G1 · `offline-fisico` — los 12 flujos con la red cortada

- **Protocolo:** `docs/audit/RA-RUNTIME-OFFLINE.md` §5 (tabla E5).
- **Qué se hace:** Wi-Fi **y** Ethernet desconectados (no basta con desactivar el
  DNS: se buscan dependencias de Internet, no resolución de nombres). Ejecutar los
  12 flujos: `frontend`, `backend`, `SQLite`, `Ollama`, `Whisper`, `Piper`,
  `dictionary`, `TTS`, `STT`, `course`, `practice`, `review`.
- **Qué se registra:** los 12 veredictos (✅/⚠️/❌) con fecha y `VERSION`.
- **Criterio:** un solo FALLO no declarado invalida el gate.

### G2 · `maquina-limpia` — instalación desde cero

- **Protocolo:** runbook de `README.md` · `docs/audit/RB-INSTALACION.md`.
- **Qué se hace:** en un clon/sistema recién instalado: Python + dependencias +
  Ollama + `ollama pull` + `download_models.py` + `npm run build` + launcher.
- **Qué se registra:** qué se instaló, qué falló y qué hubo que hacer a mano.
- **Recuerda:** `backend/models/` **no se versiona** (~1,1 GB) y `ollama pull` es
  un paso manual que el proyecto no verifica.

### G3 · `launcher-windows` — Windows real

- **Protocolo:** §Verificación de `release-notes-v3.73.0.md` (bloque C).
- **Qué se hace:** arrancar desde el launcher y comprobar
  `start → HTTPS → navegador → micrófono → TTS → STT → chat → persistencia`.
- **Por qué no lo cubre el CI:** el job `launcher-windows` prueba el launcher en
  Windows, y `product-origin-windows` el origen de producto **sobre HTTPS con TLS
  autofirmado**, pero ninguno puede probar el micrófono ni un navegador real.

### G4 · `dispositivos` — móvil y tablet

- **Protocolo:** `docs/DEVICE_MATRIX.md`.
- **Qué se hace:** Windows desktop, Android Chrome, iPhone Safari y tablet, sobre
  la LAN con el certificado autofirmado aceptado.
- **Qué se registra:** micrófono, audio, touch, responsive, viewport, teclado y
  orientación. **No basta con capturas.**

### G5 · `audio-stt-tts` — voz de verdad

- **Qué se hace:** una grabación y transcripción reales (speaking), una
  reproducción real (TTS) y el aviso de voz degradada mostrando la voz
  realmente usada.
- **Criterio:** si la voz cae a una peor, el alumno **se entera** (V3.72 lo hizo
  observable; aquí se confirma en hardware).

### G6 · `journeys` — todos los recorridos

- **Protocolo:** `docs/audit/F-UX-JOURNEY.md`.
- **Qué se hace:** Home, Today, Curso, Aprender, Listening, Vocabulary, Grammar,
  Reading, Speaking, Conversation, Review y Progress, de principio a fin.
- **Qué se registra:** recorrido, incidencia y si el «por qué esta actividad»
  aparece donde el motor lo declara.

### G7 · `pedagogia` — auditoría final del contenido

- **Protocolo:** `docs/CONSTITUCION-PEDAGOGICA.md` ·
  `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`.
- **Qué se mide:** léxico (frecuencia, utilidad, CEFR, colocaciones, phrasal
  verbs, chunks), gramática (progresión, errores frecuentes, contrastes,
  transferencia), listening (bottom-up/top-down, connected speech, cloze,
  dictation, shadowing, acentos, velocidad) y speaking (inteligibilidad,
  pronunciación, fluidez, interacción, reparación).
- **Candado conceptual:** **no** convertir «número de palabras conocidas» en
  «nivel CEFR». El nivel estimado es interno y se declara como tal.

## Lo que el instrumento NO hace

- **No ejecuta** flujos de la app: certifica lo que una persona hizo y registró.
- **No puede** sustituir a la red desconectada, a Windows real ni a un móvil.
  Nada de eso se puede simular en CI con honestidad.
- **`auto` no importa** código del backend (es stdlib pura): comprueba estática
  del repositorio, no comportamiento en runtime. El comportamiento lo fijan los
  suites de tests y los jobs del CI.

## Estado

| Gate | Estado |
|---|---|
| G1 `offline-fisico` | ⬜ pendiente (acción humana) |
| G2 `maquina-limpia` | ⬜ pendiente (acción humana) |
| G3 `launcher-windows` | ⬜ pendiente (acción humana) |
| G4 `dispositivos` | ⬜ pendiente (acción humana) |
| G5 `audio-stt-tts` | ⬜ pendiente (acción humana) |
| G6 `journeys` | ⬜ pendiente (acción humana) |
| G7 `pedagogia` | ⬜ pendiente (acción humana) |

El estado real y con notas vive en `docs/audit/validation-evidence.json`, que
**se crea con el primer `record`** y se consulta con `validation_gate.py status`.
Esta tabla es el punto de partida, no la verdad: la verdad es la que registra el
instrumento.
