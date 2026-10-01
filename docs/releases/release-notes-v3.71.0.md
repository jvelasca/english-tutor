# v3.71.0 — Runtime real, offline verificado e instalación limpia

> **Fecha:** 2026-09-16 · **Tag:** `v3.71.0` · **Versión de app:** `3.70.0 → 3.71.0`.
> **Naturaleza de la release:** **VERIFICACIÓN con endurecimiento mínimo**. SIN
> migración de BD, SIN bump de `GENERATOR_VERSION`, SIN bump de
> `DECISION_POLICY_VERSION`, SIN tocar el banco, SIN tocar el currículum y SIN
> capacidad pedagógica nueva.
> **Dossiers:** `docs/audit/RE-GATES-DERIVA.md` · `RA-RUNTIME-OFFLINE.md` ·
> `RB-INSTALACION.md` · `RC-RUNTIME-PRODUCTO.md` · `RD-DEPENDENCIAS-OCULTAS.md` ·
> `RF-SINTESIS-RUNTIME-V371.md`.

## Contexto

V3.69 validó la **arquitectura** del motor adaptativo y V3.70 midió su
**pedagogía**. V3.71 baja al **suelo físico**, que es dónde un proyecto que se
declara «100 % local» se juega su credibilidad. Tres preguntas concretas:

1. **¿Qué toca Internet de verdad**, y está declarado?
2. **¿Se instala en una máquina limpia** sin pasos tácitos que nadie escribió?
3. **¿Le dice la app la verdad al usuario** sobre su propio estado cuando algo de
   lo anterior falla?

El incremento se organiza en seis ejes: **RE** (gates/CI/deriva) · **RA** (offline
real) · **RB** (instalación limpia) · **RC** (runtime de producto y salud
honesta) · **RD** (dependencias ocultas y degradación) · **RF** (síntesis).

**Regla de todo el incremento:** medir antes de tocar, endurecer lo mínimo, y
**re-declarar con fase lo que no se cierra** en lugar de cerrarlo en falso. Cada
endurecimiento trae un **test que falla sin el cambio**.

## A · RE — Gates, CI y deriva documental

El launcher era el **único subsistema sin gate**: sus **75 tests** no se
ejecutaban en CI, y `docs/BETA_GATES.md` daba ✅ a «Launcher de escritorio» y «CI
completa» de todos modos.

- **Nuevo job `launcher`** en `.github/workflows/ci.yml` (lint + tests, con los
  **mismos pins** de `pytest`/`ruff` que el backend, y un test lo verifica). El CI
  pasa a **7/7 jobs**.
- **Cuatro derivas documentales corregidas**, anotadas sin reescribir el
  histórico: árbol del launcher en `ARQUITECTURA.md`; **modelo por defecto** en
  `PREMISAS.md`/`README.md` (declaraban `qwen3.5:9b`, que el código **veta**: es
  `llama3.1:8b`); los ✅ de `BETA_GATES.md`; y la matriz de dispositivos declarada
  verde con `DEVICE_MATRIX.md` **10/10 en ⬜**.
- **8 tests** (`backend/tests/test_docs_drift_v371.py`) fallan si una deriva
  vuelve. **G5 (matriz de dispositivos) queda declarado ABIERTO.**

## B · RD — El P1 de TTS/offline, cerrado (diferido 4 veces desde V3.46)

**El hallazgo central del incremento.** El proyecto venía difiriendo un **P1 de
TTS/offline** desde V3.46 en cuatro sitios, con tres vectores declarados
(*timeout*, *UI*, *degradación*). Lo medido:

- El `timeout` **era código muerto**: `urllib.request.urlretrieve` **no acepta**
  el parámetro, así que se declaraba y se ignoraba.
- Consecuencia: la **única dependencia de Internet en ruta de producto** —un
  `POST /api/tts` de un idioma sin voz instalada— quedaba **sin límite de tiempo**,
  y la degradación a otra voz era **muda**.

**Cierre.** `urlopen` con timeout **real** por operación de socket (15 s), descarga
**atómica** (`.part` → `replace`) y verificación del tamaño contra
`Content-Length` (se rechazan descargas vacías o truncadas). La degradación pasa a
ser **observable**: log + cabeceras `X-TTS-Voice` / `X-TTS-Degraded` (expuestas
también por CORS).

| Vector del P1 | Estado tras V3.71 |
|---|---|
| **timeout** | ✅ **cerrado** (real y acotado) |
| **degradación** | ✅ **cerrado** (log + cabeceras) |
| **UI** | ⬜ **re-declarado con fase: V3.72** (aviso/progreso/consentimiento y consumo de `X-TTS-Degraded`) |

Es decir: **2 de 3 cerrados**, y el tercero ya no puede quedar en el olvido porque
el backend expone el dato que la UI necesita. **6 tests nuevos**, todos fallan sin
el cambio.

## C · RC — Runtime de producto y salud honesta

**La frontera, medida.** La UI la sirve el **dev server de Vite** (`npm run dev`)
y el backend **no** monta `frontend/dist` (no hay `StaticFiles` ni `FileResponse`
en todo `backend/`): el artefacto de producción **existe y no lo sirve nadie**.
Consecuencia que el proyecto no declaraba: **Node + npm son requisito de
EJECUCIÓN**, no solo de compilación.

Por la **decisión A** se **declara con condición de salida** (se reevalúa en
V3.72/V3.73 con el eje RB) en vez de implementarse, y queda **fijado por test**
(si alguien monta el `dist` o cambia el comando del launcher, el test obliga a
actualizar la declaración).

**Dos defectos reales que caen en el camino:**

- **RC-02 — el sondeo de Ollama no tenía cota.** El launcher solo espera **1,5 s**
  por el estado del backend, y `llm.ping()` hacía `list()` **sin timeout**: con
  Ollama **cargando un modelo** —el caso normal justo tras arrancar— la respuesta
  llegaba tarde, el launcher concluía «backend caído» y llamaba a `start_backend()`
  sobre un backend que ya escuchaba. **Un Ollama lento se disfrazaba de backend
  caído.** → `LLM_PING_TIMEOUT_SECONDS = 1.0` con `asyncio.wait_for`.
- **RC-03 — la UI mentía sobre su estado.** El indicador de cabecera (visible
  **siempre**) preguntaba a `/api/health`, que responde **200 siempre** que el
  proceso esté vivo: con Ollama, la BD, el STT o el TTS caídos seguía en verde
  diciendo «Conectado», con la app incapaz de dar clase. Lo llamativo es que la
  verdad **ya estaba en el proyecto** a un clic (el popover y el launcher ya usaban
  `/api/health/dependencies`); la mentira era solo del titular. → **tres estados**:
  **Conectado / Degradado / Desconectado**.

Se declara además que `ready` = «la app puede dar clase» (BD + LLM + STT + TTS),
**no** «todo el catálogo está»: la biblioteca de audio es opcional por diseño.

## D · RB — Instalación limpia desde cero

Absorbe **RA-04** y **RD-06**.

- **RB-01 — la voz con la que la app da clase no se podía auto-descargar.**
  `config.PIPER_VOICE = "en_US-lessac-medium"` es el default del idioma inglés y
  la voz del núcleo pedagógico, pero **no estaba** en el catálogo curado, y
  `ensure_voice_for_language` abandona cuando el default no está en el catálogo. En
  una instalación limpia, el **español sí se auto-descargaba y el inglés no** —en
  silencio, sin error ni log, con el TTS degradando a otra voz. **Falsado
  empíricamente** reproduciendo el catálogo previo:

  | Catálogo | `spec_for(PIPER_VOICE)` | `ensure_voice_for_language("en")` |
  |---|---|---|
  | actual (con la voz) | `PiperVoiceSpec(id='en_US-lessac-medium', …)` | **`True`** |
  | pre-fix (sin la voz) | `None` | **`False`** (sale sin intentarlo) |

- **RB-02 — el bootstrap descargaba sin límite y con URLs propias.** Ahora
  `download_piper()` recorre `config.DEFAULT_VOICES` y delega en el catálogo:
  hereda el endurecimiento del eje RD y el script **no contiene ninguna primitiva
  de red**. Efecto colateral verificado: el manifiesto del eje RA declaraba
  `urlretrieve` aquí, así que se actualizó y se regeneró su par generado (**mismo
  censo: 6 puntos de internet**).
- **RB-03 — verificación previa de solo lectura** (`download_models.py --check` y
  `--json`) que dice **qué falta y distingue descarga de local**. Ollama se declara
  `exists=None` a propósito: este script **no puede** comprobarlo, y un `False`
  fingiría un artefacto de disco que falta. La ruta de la BD se toma de
  `repositories.db` (fuente única), no se escribe a mano.
- **RB-04 — runbook.** `README.md` gana el **`ollama pull llama3.1:8b`** explícito
  (manual por diseño: el modelo lo gestiona el servicio de Ollama), la nota de que
  `backend/models/` **no se versiona** (~1,1 GB: 2 voces Piper + Whisper `small`)
  y la verificación previa.

**13 tests.**

## E · RA — Offline real: instrumento y protocolo

- Nuevo subcomando **de solo lectura** `runtime-audit` en
  `scripts/audit_dossier.py`: determinista (el par generado se regenera byte a
  byte), con guard por test de que **no escribe** en `data/` ni en `curriculum/`, y
  con el censo de puntos de red **declarado y falsable** (si aparece una primitiva
  nueva sin declarar, el CI falla).
- **Protocolo de los 12 flujos** para cortar la red, con qué se considera FALLO en
  cada uno.
- La medición identifica **3 dependencias de Internet no declaradas** que se
  disparan **en tiempo de uso** (voz Piper en caliente, modelo Whisper, y su
  disparador en `/api/tts`): la promesa «100 % local con la descarga inicial como
  única excepción» **no las cubría**, porque no son la instalación, son el uso.
- **Propiedades positivas medidas:** el frontend **no tiene CDN, fuentes ni
  websockets externos**, y **no existe ninguna otra primitiva de red en código de
  producto** fuera de las declaradas.

**11 tests.** El eje queda **entregado pero ABIERTO**: falta ejecutar el corte de
red real (**RA-05**).

## F · RF — Síntesis

`docs/audit/RF-SINTESIS-RUNTIME-V371.md`: matriz consolidada, veredicto por área y
sección de honestidad.

**Totales del incremento: P0 = 0 · P1 = 1 (cerrado) · P2 = 15 · P3 = 14.**
De los 15 P2: **8 cerrados**, **3 declarados con fase o condición de salida**,
**3 abiertos que exigen acción humana** y **1 parcial**.

| Área | Valoración |
|---|---|
| Dependencias de red: declaración y censo | 9,5/10 |
| Robustez de la descarga real (timeout + integridad) | 9,5/10 (**era 0 antes de RD**) |
| Honestidad de la salud en la UI | 9/10 |
| Bootstrap de instalación | 9/10 |
| Honestidad del runtime declarado | 8/10 |
| Offline **verificado en vivo** | **sin evaluar** (RA-05) |
| Instalación en **máquina limpia real** | **sin ejecutar** (RB-05) |

## Tabla de hallazgos (consolidada)

| # | Sev. | Hallazgo | Estado final |
|---|---|---|---|
| RD-01/02/03 | **P1** | El `timeout` de la descarga de voces era **inerte** ⇒ dependencia de Internet **sin límite** y degradación muda | ✅ cerrado |
| RC-03 | P2 | La UI decía «Conectado» con la BD o el modelo caídos | ✅ cerrado (3 estados) |
| RC-02 | P2 | Un Ollama **lento** se disfrazaba de «backend caído» | ✅ cerrado |
| RB-01 | P2 | La **voz inglesa por defecto** no podía auto-descargarse (el español sí) | ✅ cerrado + falsado |
| RA-03 | P2 | Caché negativa volátil y cuelgue **ilimitado** | ✅ cerrado |
| RA-04 | P2 | Clon limpio sin manifiesto **ni verificación previa** | ✅ cerrado |
| RE (2×) | P2 | ✅ falsos en `BETA_GATES.md`; matriz de dispositivos declarada verde | ✅ corregido |
| **RA-01** | P2 | **3 dependencias de Internet no declaradas** en tiempo de uso | 🟡 **parcial** (UI → V3.72) |
| **RC-01** | P2 | Runtime de **desarrollo**: `dist` sin servir ⇒ **Node como requisito de ejecución** | 🟡 declarado con condición de salida |
| **RA-02** | P2 | El endpoint de Ollama **no está declarado** en `config.py` | ⬜ abierto |
| **RA-05** | P2 | **Corte de red real pendiente**: los 12 veredictos son estáticos | ⬜ abierto (acción humana) |
| P3 (14) | P3 | Positivos verificados y deudas aceptadas (caché volátil, medición estática, `ready` sin `audio_library`, RB-05, G5) | ✅ / 🟡 declaradas |

## Honestidad — lo que V3.71 NO demuestra

Leer **antes** que el veredicto.

1. **No hay verificación offline en vivo.** Los 12 flujos tienen veredicto
   **estático**; la red no se ha cortado (RA-05). En CI es **imposible** por diseño
   (premisa 12: prohibido tests dependientes de red), así que cualquier «offline
   verde» en CI sería **simulado**. Lo demostrado es que **no hay primitivas de red
   en producto fuera de las declaradas**, que **no** es lo mismo que «no hace red en
   tiempo de ejecución»: un `import` dinámico o una librería de terceros que llame
   a casa **no** aparecería en el escáner.
2. **No se ha probado en una máquina físicamente limpia** (RB-05). Existen el
   runbook y la verificación, y ambos están fijados por test; nadie los ha
   ejecutado en un sistema recién instalado. Es la diferencia entre «el runbook es
   correcto» y «el runbook funciona».
3. **No se prueba hardware móvil real** (matriz de dispositivos **10/10 ⬜**) ni
   navegadores ajenos a los usados aquí.
4. **No se mide calidad acústica** (ni de STT ni de TTS): se demuestra que suenan y
   que degradan de forma explícita, no **cómo** suenan.
5. **El runtime declarado sigue siendo el de desarrollo.** «Offline verificado»
   debe leerse como «**sin dependencias de Internet declaradas**», **no** como
   «producto empaquetado y distribuible».
6. **`ollama pull` sigue siendo un paso manual que el proyecto no verifica.** Si el
   usuario no lo ejecuta, la app degrada en el chat y el runtime no puede evitarlo.
7. **No hay empaquetado ni instalador** (vetado por decisión de producto) y el
   launcher es **solo Windows**.

## Fuera de alcance (deuda declarada, no olvidada)

- **RA-02**: declarar el endpoint de Ollama en `config.py` (o documentar que se
  delega en la librería y que `OLLAMA_HOST` no se contempla).
- **RD-04 / mitad de RA-01**: aviso de descarga, progreso y **consentimiento** en
  la UI, y consumo de `X-TTS-Degraded`. **Fase: V3.72.**
- **RD-05**: caché negativa de voces **volátil** (300 s, en memoria).
- **RC-01**: servido de `frontend/dist`; se reevalúa en **V3.72/V3.73**.
- **G5** (matriz de dispositivos) y **RA-05** (corte de red): acción humana.
- **Empaquetado/instalador** y **multiplataforma**.
- Los **6 P2 de V3.69** y los **33 hallazgos de V3.70** siguen abiertos por decisión
  de alcance de sus incrementos.

## Verificación

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q          # 2643 passed
.venv\Scripts\python.exe -m ruff check .              # All checks passed

# Frontend
cd ..\frontend
npx tsc --noEmit
npx vitest run                                        # 661 passed (76 ficheros)

# Launcher (ahora también en CI)
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q   # 75 passed
..\backend\.venv\Scripts\python.exe -m ruff check .

# Instalación (RB): verificación previa, solo lectura
cd ..\backend
.venv\Scripts\python.exe download_models.py --check

# Instrumento de runtime (RA): determinista y de solo lectura
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit

# Consistencia de versión (6 orígenes)
cd ..
python scripts/check_release_consistency.py
```

## Roadmap

**V3.72** UX/product completion (incluye el **vector UI** del P1 de TTS/offline y
la reevaluación de **RC-01**) → **V3.73** auditoría final técnica → **V4.0**
release final («English Tutor, primera versión completa y estable») y a partir de
ahí `V4.0.x` de mantenimiento y calibración.
