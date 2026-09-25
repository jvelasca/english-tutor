# V3.73 — Release de validación (runbook de los 8 gates)

> **Naturaleza:** V3.73 es una release de **validación**, no de producto. Cierra
> el endurecimiento que la auditoría de V3.72 dejó como P2/P3 (fail-closed del
> runtime de producto y descubrimiento de IP de LAN sin referencias externas) y
> construye el instrumento que convierte los ocho gates de validación física en
> **evidencia registrada**.
> **Regla:** un gate no se cierra con una opinión. Se cierra con `record`, y un
> `fail`/`skip` **exige notas**.
> **Puerta de V4.0:** `python scripts/validation_gate.py status --strict` debe
> salir 0 (los 8 gates en `pass`); con el árbol congelado, la puerta fuerte
> `status --strict --same-tree` exige además que la evidencia sea **de este mismo
> commit**.
> **Planilla de campo:** `docs/audit/KIT-VALIDACION-GATES.md` ordena la ejecución
> (pre-vuelo, agrupación por sesión y el comando `record` exacto de cada gate) sin
> duplicar los protocolos; este runbook sigue siendo la definición de los gates.

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
    --notes "12/12 flujos OK con Wi-Fi y Ethernet desconectados (v3.73.0)" `
    --ci-run 35219576565

# 3. Consultar el estado (y la puerta de V4.0)
backend\.venv\Scripts\python.exe scripts\validation_gate.py status
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict --same-tree
```

Ids válidos: `identidad-cuentas`, `offline-fisico`, `maquina-limpia`,
`launcher-windows`, `dispositivos`, `audio-stt-tts`, `journeys`, `pedagogia`.

## Qué sella la evidencia

Cada `record` escribe en `docs/audit/validation-evidence.json`: el estado, las
notas, la fecha UTC, la `VERSION` del árbol, **el commit validado (`head_sha`)** y,
con `--ci-run <id>`, la run de CI que lo publicó (se acepta el id o la URL; se
guarda el id).

- Un **`pass` sin commit no se registra**: sin git en el árbol, el instrumento
  rechaza el cierre. Un `pass` que no dice de qué árbol es no es evidencia.
- `fail`, `skip` y `pending` **sí** se registran sin SHA: declaran un no-cierre.
- `--strict` exige los 8 en `pass`. `--same-tree` exige además que los ocho
  `head_sha` sean el commit actual: es lo que impide que ocho gates verdes en
  ocho commits distintos se presenten como «los ocho gates».

**Los 8 gates son de acción humana.** La expresión «7 gates (5 de ellos acción
humana)» de notas históricas de V3.73.0 se refería a los **cinco bloques físicos
que V3.72 declaró** (corte de red, máquina limpia, Windows real, dispositivos y
audio); el instrumento los cubre y añade `journeys` y `pedagogia`, que también
exigen una persona,   y **G0** (`identidad-cuentas`), que exige el E2E de cuentas verde y que ninguna
cuenta pendiente de activación se quede sin su invitación. `Gate.human` se declara
gate a gate y vale `True` en los ocho: no hay dos cifras válidas.

## Los 8 gates

### G0 · `identidad-cuentas` — identidad y ciclo de vida de cuentas

- **Protocolo:** `backend/scripts/e2e_accounts_v382.py` ·
  `docs/audit/PLAN-P0-IDENTIDAD.md` §17.
- **Qué se hace:** el E2E de cuentas sobre una **copia** de la BD (solicitud con
  email y avatar, autorización e invitación, activación, entrada por email,
  recuperación con correo y sin correo, migración de una cuenta heredada por
  invitación, baja autoservicio, reactivación, purga con copia e historial sin PII).
- **Qué se registra:** el resultado del E2E y el contador `without_password` de la
  BD de uso, con la constancia de que cada cuenta de esa lista tiene su invitación
  emitida y entregada.
- **Criterio:** entrar sin contraseña ya **no existe** (V3.82 lo cierra por
  construcción: `403 ACCOUNT_NOT_ACTIVATED`), así que el contador es una lista de
  tareas, no un agujero. El gate queda `pending` mientras el E2E no esté verde o
  haya una cuenta esperando contraseña **sin invitación entregada**.

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
| G0 `identidad-cuentas` | ⬜ pendiente (acción humana) |
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

> **Árbol de la campaña (2026-09-24, `v3.83.1`).** El ancla documental pasa de
> `v3.81.0` a **`v3.83.1`** (`4ee32e5`): `V3.82.0` movió el contrato de sesión y migró
> la BD, `V3.83.0` movió la UI y `v3.83.1` publica el arreglo del gate
> `reduced-motion` (H2) que la campaña necesita. La campaña sigue con **0 `record`**
> (no hay nada que invalidar). Siguen los **ocho** gates, todos `pending`. Detalle en
> `docs/audit/KIT-VALIDACION-GATES.md` (re-congelación) y
> `docs/audit/CIERRE-GLOBAL-V383.md` §5.
