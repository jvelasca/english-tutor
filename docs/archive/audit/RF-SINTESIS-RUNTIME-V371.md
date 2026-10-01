# RF — Síntesis del incremento V3.71 (runtime, offline e instalación) (V3.71)

> **Tipo:** dossier de evidencia **interno** (no es un informe de auditoría
> externa). Por eso **no lleva letra**: `Z` y `Z2` siguen reservadas a los
> informes externos pendientes de V3.69
> (`agentes/auditoria-externa-v369-seguimiento.md`).
> **Papel:** **síntesis** (la redacta el orquestador, no un subagente): consolida
> los cinco ejes `RE`, `RA`, `RD`, `RC` y `RB` del briefing
> `agentes/v371-runtime-offline-instalacion.md` §F.
> **Punto de partida:** `v3.70.0` (`9ba9c49`).
> **Autor:** el propio proyecto.
> **Fecha:** 2026-09-16.

## Alcance

- **Se consolida:** la matriz de hallazgos `P0/P1/P2/P3` de los cinco ejes, el
  veredicto numérico por área y —lo más importante— la sección de **honestidad**:
  lo que este incremento **NO** demuestra.
- **No se audita:** nada nuevo. La síntesis no produce hallazgos propios; si
  apareciera uno, se asignaría a un eje.

## Los cinco ejes en una frase

| Eje | Pregunta | Cierre |
|---|---|---|
| **RE** | ¿lo que la documentación declara ✅ está en verde? | El launcher deja de ser el único subsistema sin gate (**CI 7/7**) y **4 derivas documentales** quedan corregidas y fijadas por test |
| **RA** | ¿qué depende de Internet de verdad? | Instrumento determinista de solo lectura + protocolo de 12 flujos; **3 dependencias de Internet no declaradas** identificadas |
| **RD** | ¿la degradación es explícita? | **P1 de TTS/offline cerrado** (diferido 4 veces desde V3.46): el `timeout` era **código muerto** |
| **RC** | ¿el runtime de producto es el de desarrollo y la UI dice la verdad? | La UI pasa a **3 estados** (decía «Conectado» con la BD caída) y el sondeo de Ollama se acota |
| **RB** | ¿se instala en una máquina limpia? | La **voz con la que la app da clase** podía no descargarse nunca; ahora hay verificación previa y runbook |

## Matriz consolidada de hallazgos

| # | Severidad | Hallazgo | Estado final |
|---|---|---|---|
| **RD-01/RD-02/RD-03** | **P1** | El `timeout` de la descarga de voces era **inerte** (`urlretrieve` no lo acepta) ⇒ la única dependencia de Internet en ruta de producto estaba **sin límite** y su degradación era muda | ✅ **cerrado** |
| RE (2 P2) | P2 | ✅ falsos en `docs/BETA_GATES.md` (launcher y «CI completa») y matriz de dispositivos declarada verde con 10/10 en ⬜ | ✅ corregido + fijado por test (G5 declarado abierto) |
| **RA-04** | P2 | En un clon limpio el manifiesto está vacío (1,1 GB) y **no había verificación previa ni runbook** | ✅ **cerrado (RB-03/RB-04)** |
| **RA-03** | P2 | La caché negativa de voces era volátil y el cuelgue **ilimitado** | ✅ **cerrado (RD-01)**; volatilidad declarada (RD-05) |
| **RA-01** | P2 | **3 dependencias de Internet no declaradas** que se disparan en tiempo de uso (voz en caliente, Whisper, y su disparador en `/api/tts`) | 🟡 **parcial**: timeout real y degradación declarada (RD); la **UI/consentimiento** pasa a **V3.72** (RD-04) |
| **RC-02** | P2 | El sondeo de Ollama **no tenía cota** y el launcher solo espera **1,5 s** ⇒ un Ollama **lento** (cargando modelo) se disfrazaba de «backend caído» | ✅ **cerrado** |
| **RC-03** | P2 | El indicador de cabecera leía `/api/health`, que responde **200 siempre** ⇒ decía «Conectado» con Ollama o la BD caídos | ✅ **cerrado** (3 estados) |
| **RB-01** | P2 | La **voz inglesa por defecto no estaba en el catálogo**: `ensure_voice_for_language("en")` salía **sin intentar la descarga** (el español sí) | ✅ **cerrado** + falsado |
| **RB-02 / RD-06** | P3 | El bootstrap descargaba con `urlretrieve` **sin timeout** y con URLs propias duplicadas | ✅ **cerrado (RB-02)** |
| **RA-02** | P2 | El endpoint de Ollama (`127.0.0.1:11434`) **no está declarado en `config.py`**: se delega en el default de la librería y `OLLAMA_HOST` no se contempla | ⬜ **abierto, declarado** |
| **RA-05** | P2 | La ejecución **en vivo con la red cortada** está pendiente: los veredictos de los 12 flujos son **estáticos** | ⬜ **abierto (acción humana; bloquea el cierre pleno de RA)** |
| **RC-01** | P2 | El runtime de producto es el **de desarrollo**: la UI la sirve el **dev server de Vite** y `frontend/dist` **no lo sirve nadie** ⇒ **Node + npm son requisito de ejecución** | 🟡 **declarado con condición de salida** (decisión A; se reevalúa en V3.72/V3.73) |
| **RC-04** | P3 | `ready` informa de `audio_library` pero no la exige | 🟡 **declarado** (`ready` = «puede dar clase») |
| **RB-05** | P3 | No se ejecutó el runbook en una **máquina físicamente limpia** | ⬜ **acción humana, declarada** |
| **RE (G5)** | — | Matriz de dispositivos en **hardware** (10/10 ⬜) | ⬜ **abierto (acción humana)** |
| **RA-06, RA-07, RD-05, RD-07, RC-05, RE (D1–D4)** | P3 | Propiedades **positivas** verificadas (cero CDN en el frontend, cero primitivas de red no declaradas en producto, `ADMIN_PIN` fail-closed, backend sin `--reload`, 4 derivas corregidas) y **deudas aceptadas** (caché negativa volátil, medición estática) | ✅ verificadas / 🟡 aceptadas |

**Totales del incremento: P0 = 0 · P1 = 1 (cerrado) · P2 = 15 · P3 = 14.**
De los 15 P2: **8 cerrados**, **3 declarados con fase o condición de salida**,
**3 abiertos que requieren acción humana** (RA-02, RA-05, G5) y **1 parcial**
(RA-01, con su mitad ya cerrada y la otra fechada en V3.72).

## Veredicto

**Aprobado con tres deudas de acción humana y dos declaraciones de alcance.** El
incremento hace lo que su nombre promete: **mide** el runtime real, **cierra** los
defectos que esa medición destapa y **declara** lo que no cierra, en lugar de
cerrarlo en falso.

Lo sustantivo no es cosmético. Tres hallazgos habrían aparecido en un uso normal:

1. **La app podía mentir sobre su propio estado** (RC-03): decía «Conectado» con
   la base de datos o el modelo caídos, porque preguntaba al endpoint que responde
   200 siempre. Ahora la salud que se enseña es la que decide si la app sirve.
2. **La voz con la que da clase no se podía descargar por la vía de producto**
   (RB-01), y solo en inglés: en una instalación limpia, el español se
   auto-descargaba y el inglés no, sin error ni aviso.
3. **La única dependencia de Internet en ruta de producto estaba sin límite de
   tiempo** (RD-01), con un `timeout` que parecía existir pero era **código
   muerto** — el vector señalado cuatro veces desde V3.46 y nunca cerrado.

| Área | Valoración |
|---|---|
| Dependencias de red: declaración y censo | 9,5/10 (instrumento determinista de solo lectura, con guard falsable) |
| Robustez de la descarga real (timeout + integridad) | 9,5/10 (era 0 antes de RD) |
| Honestidad de la salud en la UI | 9/10 (tres estados con test; consume la dependencia real) |
| Bootstrap de instalación | 9/10 (deriva del catálogo y avisa; falta prueba en máquina limpia real) |
| Honestidad del runtime declarado | 8/10 (frontera medida y documentada; **Node sigue siendo requisito de ejecución**) |
| Offline **verificado en vivo** | **sin evaluar** (RA-05: pendiente de cortar la red) |
| Instalación en **máquina limpia real** | **sin ejecutar** (RB-05) |

## Honestidad: lo que V3.71 NO demuestra

Esta sección es obligatoria (premisa 12 y estilo del proyecto: antes declarar que
alucinar). Se lee **antes** que el veredicto.

1. **No hay verificación offline en vivo.** Los 12 flujos tienen veredicto
   **estático** (código + manifiesto). La red no se ha cortado todavía (RA-05). En
   CI es **imposible** por diseño: la premisa 12 prohíbe tests dependientes de
   red, así que cualquier «offline verde» en CI sería **simulado**. Lo que sí
   queda demostrado es que **no hay primitivas de red en código de producto fuera
   de las declaradas** — que no es lo mismo que «no hace red en tiempo de
   ejecución» (RA-07: un `import` dinámico o una librería de terceros que llame a
   casa no aparecería en el escáner).
2. **No se ha probado en una máquina limpia de verdad** (RB-05). El runbook y la
   verificación previa existen y están fijados por test, pero nadie los ha
   ejecutado en un sistema recién instalado. Es la diferencia entre «el runbook es
   correcto» y «el runbook funciona».
3. **No se prueba hardware móvil real.** La matriz de dispositivos sigue **10/10
   en ⬜** (G5) y ninguna afirmación de este incremento cubre móviles, tablets ni
   navegadores ajenos a los usados aquí.
4. **No se mide calidad acústica** (ni del STT ni del TTS). Se mide que suenan y
   que degradan de forma explícita, no **cómo** suenan.
5. **El runtime declarado sigue siendo el de desarrollo** (RC-01). Este incremento
   **mide y declara** la frontera (dev server de Vite, `dist` sin servir, Node como
   requisito de ejecución); **no** la cambia. Un auditor debe leer «offline
   verificado» como «sin dependencias de Internet declaradas», **no** como
   «producto empaquetado y distribuible».
6. **No hay empaquetado ni instalador** (vetado por decisión de producto) y el
   launcher es **solo Windows**.
7. **`ollama pull` sigue siendo un paso manual que el proyecto no verifica**: el
   informe de instalación lo declara `exists=None` a propósito, porque el modelo
   lo gestiona el servicio de Ollama. Si el usuario no lo ejecuta, la app degrada
   en el chat y el runtime no puede evitarlo.

## Fuera de alcance (deuda declarada, no olvidada)

- **RA-02**: declarar el endpoint de Ollama en `config.py` (o documentar que se
  delega en la librería y que `OLLAMA_HOST` no se contempla).
- **RD-04 / mitad de RA-01**: aviso de descarga, progreso y **consentimiento** en
  la UI, y consumo de `X-TTS-Degraded` por el frontend. **Fase: V3.72.**
- **RD-05**: caché negativa de voces **volátil** (300 s, en memoria).
- **RC-01**: servido de `frontend/dist`; se reevalúa en **V3.72/V3.73** con el eje
  RB (la pregunta «¿qué debe tener instalado el usuario?» se responde allí).
- **G5** (matriz de dispositivos) y **RA-05** (corte de red): acción humana.
- Los **6 P2 de V3.69** y los **33 hallazgos de V3.70** siguen abiertos por
  decisión de alcance de sus incrementos.

## Tests que respaldan (cifras del incremento)

- **Backend: 2643 tests** (antes de V3.71: 2600 al cerrar V3.70). Nuevos:
  `test_docs_drift_v371.py` (RE, ampliado por RC), `test_runtime_audit_v371.py`
  (RA), `test_install_bootstrap_v371.py` (RB), más los añadidos a
  `test_health.py` (RC) y `test_voices.py` (RD, 6 tests).
- **Frontend: 661 tests** (incluye los 5 de `ConnectionIndicator`, que ahora
  cubren Conectado / **Degradado** / Desconectado).
- **Launcher: 75 tests**, **ahora también en CI** (job `launcher`, 7/7 jobs).
- **CI**: `ci.yml` con **7 jobs**.

## Regenerar / Verificar

```powershell
# Backend (incluye los tests de los cinco ejes)
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m ruff check .

# Frontend (los 3 estados del indicador)
cd ..\frontend
npx tsc --noEmit
npx vitest run

# Launcher (75 tests, ya en CI)
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q
..\backend\.venv\Scripts\python.exe -m ruff check .

# Instalación (RB): verificación previa de solo lectura
cd ..\backend
.venv\Scripts\python.exe download_models.py --check

# El instrumento de runtime (RA) sigue cuadrando y es determinista
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
```

## Dossiers de los que sale esta síntesis

- `docs/audit/RE-GATES-DERIVA.md` · `docs/audit/RA-RUNTIME-OFFLINE.md` ·
  `docs/audit/RD-DEPENDENCIAS-OCULTAS.md` · `docs/audit/RC-RUNTIME-PRODUCTO.md` ·
  `docs/audit/RB-INSTALACION.md`.
