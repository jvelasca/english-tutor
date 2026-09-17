# RA — Runtime y offline real (V3.71)

> **Tipo:** dossier de evidencia **interno** (no es un informe de auditoría
> externa). Por eso **no lleva letra**: `Z` y `Z2` siguen reservadas a los
> informes externos pendientes de V3.69
> (`agentes/auditoria-externa-v369-seguimiento.md`).
> **Eje auditado:** **RA** («¿la app funciona con Internet desconectado?») del
> briefing `agentes/v371-runtime-offline-instalacion.md` §A.
> **Origen:** auditoría externa `Y` de V3.68, **§22** — «El proyecto declara
> **100 % local**, así que habrá que probar con **Internet desconectado** que
> funcionan `frontend`, `backend`, `SQLite`, `Ollama`, `Whisper`, `Piper`,
> `dictionary`, `TTS`, `STT`, `course`, `practice` y `review`. **No basta con que
> «normalmente» funcione offline.**»
> **Punto de partida:** `v3.70.0` (`9ba9c49`) + eje RE de V3.71 (`2c07fe0`).
> **Autor:** el propio proyecto.
> **Fecha:** 2026-09-16.

## Alcance

- **Se audita:** de qué depende el runtime **por encima de lo declarado** —
  es decir, qué toca la red **cuando el alumno ya está usando la app** (no durante
  la instalación), y si el manifiesto de modelos que hace falta para funcionar sin
  Internet está completo y **en disco**.
- **No se audita** (para no solapar con los otros ejes): la **instalación limpia**
  (RB), la **salud honesta de la UI** y el servido de `dist` (RC), el cierre del
  **P1 de TTS/offline** y la caché negativa volátil (RD), ni la síntesis (RF).
  Aquí solo se toca la caché negativa en lo que afecta **directamente al offline**
  (reintentos contra un host inalcanzable).
- **Estado:** el **instrumento y el protocolo están entregados**; la
  **ejecución en vivo con la red cortada está PENDIENTE** (§5). El eje **no puede
  cerrarse** hasta ejecutarla.

## Método

1. **Instrumento de solo lectura** (`scripts/audit_dossier.py::runtime_audit`,
   subcomando nuevo `runtime-audit`): declara cada punto del backend que toca la
   red, con su **tipo** (`loopback` / `lan` / `internet`) y si es una dependencia
   **oculta** (`hidden=True` = no es un paso de instalación explícito y puede
   dispararse en tiempo de uso). El instrumento **se autocomprueba**: cada
   declaración lleva un `needle` que debe seguir existiendo en el fichero, y
   reporta `cuadra=NO` si la declaración deriva del código.
2. **Guard de falsabilidad por test** (`backend/tests/test_runtime_audit_v371.py`):
   escanea el backend buscando primitivas de red (`urlretrieve`, `urlopen`,
   `requests.*`, `httpx.`) y **falla si aparece una en código de producto que no
   esté declarada**. Es lo que convierte el instrumento en una medida que no se
   puede quedar obsoleta.
3. **Determinismo exigido.** El par generado en `docs/audit/generated/` se
   regenera **byte a byte** (verificado con `Get-FileHash`). Por eso el sondeo en
   vivo de Ollama es un **modo aparte** (`--probe-ollama`): su resultado depende
   de la máquina.
4. **Solo lectura.** Ningún paso escribe en `data/` ni en `curriculum/`
   (comprobado por test, con huella de mtimes antes/después).

## Evidencia

### E1 — Puntos de red del backend (9 declarados, todos cuadran)

| tipo | cuántos | ficheros |
|---|---|---|
| `loopback` | 1 | `services/llm.py` (`ollama.AsyncClient()`) |
| `lan` | 2 | `services/net_interfaces.py` (`getaddrinfo` del propio equipo) · `services/network.py` (`getaddrinfo` mDNS) |
| `internet` | 6 | `services/voice_downloads.py`, `services/tts.py`, `routers/voz.py`, `services/stt.py`, `download_models.py` (×2) |

- **Declaraciones que han derivado del código: ninguna** (`cuadra=si` en las 9).
- **Dependencias de Internet NO declaradas: 3** (`services/tts.py`,
  `routers/voz.py`, `services/stt.py`) — ver RA-01.

El **guard por test** es falsable y no pasa en vacío: el escáner ve 4 ficheros
reales con primitivas de red, y de ellos **solo uno está en código de producto**:

```
download_models.py                       ['urlretrieve']      <- bootstrap (declarado)
scripts/audit_dossier.py                 ['urlretrieve','urlopen'] <- instrumento (declarado)
scripts/smoke_test.py                    ['urlopen']          <- herramienta dev (declarado)
services/voice_downloads.py              ['urlretrieve']      <- PRODUCTO (declarado)
```

**Propiedad positiva:** **no hay ninguna otra primitiva de red en código de
producto**. Es decir, el diccionario, el léxico, el currículum, el scoring, el
Planner, FSRS y la persistencia **no tienen acceso a Internet por construcción**,
no por disciplina.

### E2 — El frontend no tiene dependencias externas

| Comprobación | Resultado |
|---|---|
| `frontend/index.html` | 100 % local: `favicon.svg`, `main.tsx`, script inline de tema. **Sin** `fonts.googleapis`/`gstatic`/CDN |
| Barrido de `frontend/` por CDN/fuentes/websockets externos | **0 coincidencias** |
| `vite.config.ts` | `basicSsl` (certificado autofirmado, generado en local), `host: true`, proxy `/api` → `127.0.0.1:8000` |

### E3 — Manifiesto de modelos (lo que debe estar en disco)

| id | ruta | presente | MB |
|---|---|---|---|
| `piper:en_US-lessac-medium.onnx` | `backend/models/piper/…` | sí | 60,3 |
| `piper:en_US-lessac-medium.onnx.json` | `backend/models/piper/…` | sí | ~0 |
| `piper:es_ES-davefx-medium.onnx` | `backend/models/piper/…` | sí | 60,3 |
| `piper:es_ES-davefx-medium.onnx.json` | `backend/models/piper/…` | sí | ~0 |
| `whisper:small` | `backend/models/whisper` | sí (11 ficheros) | 927,4 |

**Ausentes: 0** en este equipo. Consecuencia honesta e importante para RB:
`backend/models/` está en `.gitignore`, así que **en un clon limpio el manifiesto
está vacío** y los ~1,1 GB hay que descargarlos (§4, RA-04).

### E4 — Sondeo en vivo de Ollama (`--probe-ollama`)

```
- Endpoint: http://127.0.0.1:11434 (default de la libreria ollama, NO declarado en config.py)
- Alcanzable: si
- Modelo por defecto llama3.1:8b instalado: si
- Modelos visibles: ['llama3.1:8b', 'qwen2.5-coder:1.5b', 'qwen3-coder:30b', 'qwen3.5:9b']
```

- El modelo por defecto (`llama3.1:8b`) **está** instalado ⇒ el flujo de chat
  arranca sin descargar nada.
- `qwen3.5:9b` sigue **instalado en Ollama** pero **vetado en el código**
  (`config.UNUSABLE_MODELS`): correcto por diseño, y coherente con la corrección
  D2 del eje RE.

### E5 — Los 12 flujos de `Y` §22

Veredicto **estático** (código + manifiesto) por flujo. La columna «en vivo»
queda **pendiente** hasta ejecutar el protocolo de §5 con la red cortada.

| # | Flujo | Dependencia real | Veredicto estático | En vivo |
|---|---|---|---|---|
| 1 | `frontend` | Vite dev server (Node) sirviendo `src/`; sin CDN ni fuentes externas | ✅ offline, pero **exige Node/Vite en marcha** (es el eje RC) | ⬜ |
| 2 | `backend` | FastAPI local | ✅ offline | ⬜ |
| 3 | `SQLite` | fichero local (`backend/data/`, gitignored) | ✅ offline | ⬜ |
| 4 | `Ollama` | loopback `127.0.0.1:11434` | ✅ offline si el modelo está descargado (lo está) | ⬜ |
| 5 | `Whisper` | caché local en `backend/models/whisper`; **descarga en caliente si falta** | ⚠️ offline **solo si** el cache existe (RA-01) | ⬜ |
| 6 | `Piper` | voces locales en `backend/models/piper`; **descarga en caliente si falta** | ⚠️ offline **solo si** las voces existen (RA-01) | ⬜ |
| 7 | `dictionary` | Ollama (loopback) + caché en BD; **cero** acceso a Internet (E1) | ✅ offline (la definición a demanda falla con gracia si Ollama no está) | ⬜ |
| 8 | `TTS` | `routers/voz.py` → `ensure_voice_for_language` → **descarga si falta** | ⚠️ ver RA-01 (y RD) | ⬜ |
| 9 | `STT` | `services/stt.py` → faster-whisper con `download_root` | ⚠️ ver RA-01 | ⬜ |
| 10 | `course` | `curriculum/*.json` en disco | ✅ offline | ⬜ |
| 11 | `practice` | backend + currículum + Ollama (según actividad) | ✅ offline | ⬜ |
| 12 | `review` | FSRS + BD local | ✅ offline | ⬜ |

**Señal adicional (no prueba):** los **2608 tests** del backend corren sin
necesitar Internet (premisa 12: los tests no dependen de red). Si algún camino de
`course`/`practice`/`review`/`dictionary` hiciera una llamada saliente real, la
suite sería lenta e inestable en lugar de tardar ~5 min de forma estable.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| **RA-01** | **P2** | **Tres dependencias de Internet NO declaradas que se disparan en tiempo de uso.** Si falta el artefacto, la app **descarga en caliente** en lugar de fallar de forma explícita: (a) un `POST /api/tts` de un idioma sin voz instalada baja ~60 MB de Hugging Face; (b) la primera transcripción descarga el modelo Whisper (~900 MB) si no está en disco. La promesa «100 % local, con la descarga inicial como única excepción» **no cubre este caso**: no es la instalación, es el uso | `routers/voz.py:54`; `services/tts.py:184-190`; `services/stt.py:54-57`; `services/voice_downloads.py:121` | Declarar el comportamiento (¿descarga perezosa **consentida** o fallo explícito `voz no instalada → Configuración → Voces`?) y que la UI lo anuncie **antes** de descargar | **parcialmente cerrado por RD** (`docs/audit/RD-DEPENDENCIAS-OCULTAS.md`): el timeout es real y la degradación se declara; **sigue abierta la parte de UI/consentimiento** (RD-04, fase V3.72) |
| **RA-02** | **P2** | **El endpoint de Ollama no está declarado en el código.** `ollama.AsyncClient()` sin argumentos toma el default de la librería (`127.0.0.1:11434`). El manifiesto puede afirmarlo, pero `config.py` no; si un usuario tiene Ollama en otro puerto (`OLLAMA_HOST`), el proyecto no lo contempla ni lo documenta | `services/llm.py:11,18` | Declarar el endpoint en `config.py` (aunque sea el default) o documentar explícitamente que se delega en la librería | **abierto** |
| **RA-03** | **P2** | **La caché negativa de voces es volátil (300 s, en memoria).** Con la red cortada y una voz ausente, cada reintento vuelve a intentar la descarga con un timeout declarado de 300 s: la petición de TTS puede quedarse **colgada** en lugar de fallar rápido, y el olvido se produce en cada reinicio del proceso | `services/tts.py:56-57,176-179`; `services/voice_downloads.py:113` (antes) | Cachear el fallo de forma persistente o usar un timeout corto para el intento optimista; devolver error explícito y ofrecer la descarga como acción del usuario | **cerrado por RD** (`docs/audit/RD-DEPENDENCIAS-OCULTAS.md`): el timeout declarado era **código muerto**, así que el cuelgue era **ilimitado**; ahora es real y acotado (RD-01). La volatilidad de la caché queda como deuda aceptada (RD-05) |
| **RA-04** | **P2** | **En un clon limpio el manifiesto está VACÍO y no había runbook que lo dijera.** `backend/models/` está en `.gitignore`, así que hacen falta ~1,1 GB de descargas (Piper EN+ES 120 MB, Whisper 927 MB) más el `ollama pull` del modelo por defecto. Sin ellos, RA-01 convierte el primer uso en descargas implícitas | `.gitignore:15`; E3 (`Ausentes: 0` **solo** en este equipo) | **Cerrado en el eje RB** (RB-03/RB-04): `download_models.py --check` (solo lectura, distingue descarga de local) + runbook en `README.md` con el `ollama pull` explícito | **cerrado (RB)** |
| **RA-05** | **P2** | **La ejecución en vivo con la red cortada está pendiente**, así que el eje no se puede cerrar. Los veredictos de E5 son **estáticos** | §5 (protocolo) | Ejecutar el protocolo de §5 en la máquina (o una VM) con la red desconectada y volcar los 12 resultados | **abierto (bloquea el cierre del eje)** |
| **RA-06** | **P3 (positivo)** | Propiedades positivas medidas: (i) el frontend **no** tiene CDN, fuentes ni websockets externos; (ii) **no existe ninguna otra primitiva de red en código de producto** (E1) | E1, E2 | Ninguna; registrarlo como propiedad verificada | **verificado** |
| **RA-08** | **P3** | **Referencia externa en el descubrimiento de la IP de LAN.** `get_lan_ip()` usaba un socket UDP «connect» a una IP pública (`8.8.8.8:80`) en **tres** sitios (`services/network.py`, `services/tls_cert.py`, `launcher/core.py`). No hay dependencia de Internet (el `connect` UDP es perezoso), pero es una referencia pública en la lógica de descubrimiento de una app 100 % local | `services/network.py:17`; `services/tls_cert.py:64`; `launcher/core.py:125` | Descubrir la IP enumerando las interfaces del sistema, sin direcciones externas | **cerrado en V3.73**: `services/net_interfaces.py` (algoritmo puro `select_lan_ipv4` + enumeración del propio equipo + override declarado `ENGLISH_TUTOR_LAN_IP`); los tres consumidores delegan o replican; candado anti-deriva en `backend/tests/test_net_interfaces_v373.py` |
| **RA-07** | **P3 (deuda)** | El instrumento mide **estáticamente**: no puede demostrar que un camino concreto no haga red en tiempo de ejecución (solo que no contiene primitivas conocidas). Un `import` dinámico o una librería de terceros que llame a casa no aparecería | E1 (alcance del escáner) | Declararlo como límite; la parte dinámica la cubre el protocolo de §5 | **aceptado** |

## 5. Protocolo de los 12 flujos (pendiente de ejecutar)

**Preparación (una vez):**

```powershell
# 0. Antes de cortar la red: dejar constancia del manifiesto.
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit   # E3 debe salir "Ausentes: 0"
```

**Corte de red:** desconectar el adaptador (o poner la máquina en un punto de
acceso sin Internet). **No** vale desactivar solo el DNS: el protocolo busca
dependencias de Internet, no resolución de nombres.

```powershell
# 1. Arrancar la app con el launcher (backend + frontend) y abrir la UI.
# 2. Por cada flujo: ejecutarlo y anotar OK / FALLO / DEGRADA, con el log.
```

| # | Flujo | Qué ejecutar | Qué se considera FALLO |
|---|---|---|---|
| 1 | `frontend` | Abrir `https://localhost:5173`, navegar las 3 secciones | recursos que no cargan, fuentes por defecto |
| 2 | `backend` | `GET /api/health` y `GET /api/health/ready` | 5xx o timeout |
| 3 | `SQLite` | abrir un perfil, crear un usuario | error de BD |
| 4 | `Ollama` | un turno de chat real | respuesta vacía o timeout |
| 5 | `Whisper` | una actividad de **listening** con audio | audio que no suena |
| 6 | `Piper` | `Test playback` en Ajustes | silencio o excepción |
| 7 | `dictionary` | buscar una palabra **ya cacheada** y una **no cacheada** | la cacheada debe ir; la no cacheada debe **degradar**, no colgarse |
| 8 | `TTS` | `/api/tts` en inglés **y** en español | debe responder; **si la voz falta, anotar el tiempo de espera** (RA-03) |
| 9 | `STT` | grabar un intento de **speaking** | transcripción vacía |
| 10 | `course` | abrir Course y completar una lección | lección que no carga |
| 11 | `practice` | una práctica de drill | no sirve la tarea |
| 12 | `review` | Today → Spaced review → calificar | no actualiza el `due` |

**Registro:** volcar el resultado de los 12 en la tabla E5 de este dossier
(⬜ → ✅/⚠️/❌) con la fecha y el `VERSION` del árbol, y **cambiar RA-05 a
cerrado**. Un solo FALLO no declarado convierte el eje en no aprobado.

## Veredicto

**Eje ABIERTO — no aprobado todavía.** El instrumento y el protocolo están
entregados y el guard por test hace que las dependencias declaradas no puedan
quedar obsoletas en silencio; además hay dos propiedades positivas fuertes: el
frontend no tiene ninguna dependencia externa y **no existe ninguna otra
primitiva de red en código de producto**.

Pero **el eje se cierra ejecutando los 12 flujos con la red cortada**, y eso está
pendiente (RA-05). Lo medido hasta ahora ya deja un hallazgo que contradice
matizadamente la promesa de «100 % local»: **3 dependencias de Internet que se
disparan en tiempo de uso** (RA-01), con el agravante de que en un clon limpio el
manifiesto está vacío (RA-04) y el fallo es un cuelgue de hasta 5 minutos en lugar
de un error claro (RA-03).

| Área | Valoración |
|---|---|
| Medición estática de dependencias de red | 9,5/10 (9 puntos declarados, guard por test falsable) |
| Offline del frontend | 10/10 (cero dependencias externas) |
| Offline del backend en uso (con el manifiesto completo) | 8,5/10 (funciona; el fallo no es explícito si falta un artefacto) |
| Offline en un clon **limpio** | **sin evaluar** (es RB) |
| Verificación en vivo con la red cortada | **pendiente** (RA-05) |

**Hallazgos: P0 = 0 · P1 = 0 · P2 = 5 (1 trasladado a RB, 1 bloquea el cierre, 2 cerrados por el eje RD, 1 abierto) · P3 = 2 (1 positivo, 1 deuda).**

> **Actualización (2026-09-16, eje RD):** **RA-03** queda **cerrado** por RD-01
> (el `timeout` declarado era **código muerto** y el cuelgue era **ilimitado**, no
> de 5 minutos) y **RA-01** queda **parcialmente cerrado** por RD-02/RD-03 (el
> timeout es real y acotado, y la degradación se declara en log y cabeceras); la
> parte de **UI/consentimiento** sigue con fase asignada a **V3.72** (RD-04).
> Ver `docs/audit/RD-DEPENDENCIAS-OCULTAS.md`. **RA-05 sigue bloqueando el cierre
> del eje**: la ejecución en vivo con la red cortada sigue pendiente.
>
> **Actualización (2026-09-16, eje RB):** **RA-04** queda **cerrado** por RB-03 y
> RB-04: `download_models.py --check` es una verificación previa **de solo
> lectura** que informa de lo que falta y distingue **descarga** de **local**, y el
> runbook de `README.md` declara el `ollama pull` explícito y el hecho de que
> `backend/models/` no se versiona. Ver `docs/audit/RB-INSTALACION.md`.
> **Nota de coherencia del instrumento:** el eje RB quitó `urlretrieve` del
> bootstrap, así que la declaración `RUNTIME_TOUCHPOINTS` se actualizó (la
> primitiva vive ahora en `services/voice_downloads.py`) y el par generado se
> regeneró: el reparto por tipo sigue siendo **6 puntos de internet**.
>
> **Actualización (2026-09-17, V3.73):** **RA-08** queda **cerrado**. El
> descubrimiento de la IP de LAN deja de usar el socket UDP a `8.8.8.8`: ahora
> `services/net_interfaces.py` enumera las direcciones del propio equipo
> (`getaddrinfo`/`gethostbyname_ex` del nombre local) y `select_lan_ipv4` es
> **puro** (se prueba sin red). Hay un override declarado
> (`ENGLISH_TUTOR_LAN_IP`) para equipos con varias NIC o VPN.
> **Cascada del instrumento:** `RUNTIME_TOUCHPOINTS` cambia el punto `lan` de
> `services/network.py` (UDP) por uno en `services/net_interfaces.py`; el reparto
> por tipo sigue siendo **1 loopback · 2 lan · 6 internet** y el par generado se
> regeneró. **RA-06** conserva las propiedades positivas (i) y (ii); su punto
> (iii) pasa a ser RA-08 y deja de ser una excepción declarada.
> **RA-05 sigue bloqueando el cierre del eje**: la ejecución en vivo con la red
> cortada sigue pendiente.

## Regenerar / Verificar

```powershell
# 1. El instrumento (determinista: el par generado se regenera byte a byte)
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
#   → docs/audit/generated/runtime-audit.{md,json}

# 2. Comprobar el determinismo
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit | Out-Null
Get-FileHash ..\docs\audit\generated\runtime-audit.md
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit | Out-Null
Get-FileHash ..\docs\audit\generated\runtime-audit.md   # mismo hash

# 3. El sondeo en vivo de Ollama (medición aparte; NO regenera el par estable)
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit --probe-ollama

# 4. Los tests del eje y el lint
.venv\Scripts\python.exe -m pytest tests/test_runtime_audit_v371.py -q   # 11 passed
.venv\Scripts\python.exe -m ruff check .
```

## Tests que respaldan

- `backend/tests/test_runtime_audit_v371.py` (**11 tests**, nuevos en V3.71):
  - `test_todo_punto_de_red_declarado_sigue_en_el_codigo` — anti-deriva: cada
    `needle` declarado sigue existiendo (RA-01/RA-02/RA-06).
  - `test_no_hay_descargas_de_internet_sin_declarar_en_codigo_de_producto` — el
    guard: una primitiva de red nueva en `services`/`routers`/`repositories`/
    `domain` **rompe el CI** si no se declara.
  - `test_las_primitivas_de_red_fuera_de_producto_estan_declaradas` — el mismo
    guard fuera de producto (bootstrap y herramientas).
  - `test_las_descargas_ocultas_conocidas_siguen_declaradas` — fija las **3**
    dependencias ocultas de RA-01: si alguna desaparece (p. ej. se cachea el fallo
    de forma persistente), obliga a actualizar el dossier en lugar de dejarlo
    obsoleto.
  - `test_el_manifiesto_cubre_todas_las_voces_por_defecto` — una voz por defecto
    nueva no puede quedar fuera del manifiesto offline (RA-04).
  - `test_el_manifiesto_es_determinista` y
    `test_el_sondeo_de_ollama_no_entra_en_la_medicion_determinista` — el par
    generado es reproducible; el sondeo en vivo es aparte.
  - `test_el_instrumento_no_escribe_en_data_ni_en_curriculum` — solo lectura
    (huella de mtimes antes/después).
  - `test_los_tipos_de_punto_de_red_son_los_declarados` (×3) — `kind` es un
    conjunto cerrado.
- `backend/tests/test_voices.py` — ya cubría que `ensure_voice_for_language`
  **no** descarga si la voz está instalada y que **sí** lo intenta si falta
  (RA-01); sin cambios en este eje.
