# Auditoría EXTERNA de CIERRE (antes de V4.0) — punto de entrada (listo para lanzar)

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el producto publicado
> en `v3.73.0`**, no un plan ni un incremento aislado. La revisión es **de solo
> lectura**: no se cambia código, datos, configuración ni etiquetas publicadas.
>
> **Por qué una auditoría de CIERRE y no otra revisión incremental.** El gerente la
> ha pedido explícitamente como **auditoría de cierre**: no se audita «qué añade
> V3.73», sino **el conjunto del producto tal y como está publicado ahora**, porque
> es el material sobre el que se decide **dar o no el salto a V4.0**. Por eso este
> documento combina la mecánica del punto de entrada de RELEASE (estado de
> publicación verificado contra GitHub) con el **alcance total** de las auditorías
> `-total-` (batería completa sobre todo el stack) y termina en una **matriz de
> cierre** de 15 áreas.
>
> **Aviso de encuadre.** V3.73 **no añade capacidad pedagógica**: es una *validation
> release* que endurece dos fronteras y construye el instrumento de los 7 gates. Si
> el auditor busca «qué se ha mejorado para el alumno», la respuesta honesta es
> **nada**; si busca «qué se ha demostrado», el objeto de esta auditoría es
> justamente **separar lo demostrado de lo declarado**.
>
> **Estado:** entregado 2026-09-17. **Informe esperado:**
> `docs/audit/AI-AUDITORIA-CIERRE-V373.md`. Prefijo **`AI`** porque `AA`–`AF` los
> ocupan los dossiers de V3.70, `AG` está reservado por el informe (pendiente) del
> punto de entrada de V3.70 y `AH` por el de V3.71 (ambos entregados y **sin informe
> recibido**): `AI` es el primer prefijo libre de la secuencia y no colisiona con la
> trazabilidad.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (nota de la posición vigente: `v3.73.0`) y
   **§0 «START HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. `docs/BETA_GATES.md` — gates de salida de Beta y su estado.
4. `docs/audit/PARKED.md` — lo **aparcado a propósito** por fase y los pendientes de
   acción humana (la lista de lo que **no** bloquea y de lo que **sí** espera).
5. **Este documento**, hasta el final.
6. Dossiers de evidencia: `docs/audit/VALIDATION-RELEASE-V373.md` (runbook de los 7
   gates), `docs/audit/RA-RUNTIME-OFFLINE.md`, `docs/audit/RC-RUNTIME-PRODUCTO.md`,
   `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`, `docs/audit/B-LISTENING-CEFR.md`,
   `docs/audit/AB-PED-COBERTURA.md`, `docs/audit/AC-PED-FEEDBACK.md`.
7. `docs/CONSTITUCION-PEDAGOGICA.md` — qué se considera «tener un nivel» (norma).
8. `docs/audit/TEMPLATE.md` — **formato** del informe que se entrega.
9. `docs/PREMISAS.md` y `CHANGELOG.md` — reglas del proyecto y relato de releases.

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -3 main
```

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Commit de release auditado:** `859c6c2` (`859c6c2115a7675af2d657b179ae9bfc7f9f5fbf`),
  `release(v3.73.0): validation release / fail-closed del runtime de producto, LAN
  sin referencias externas, CI Windows y arnés de los 7 gates`.
- **Tag anotado `v3.73.0`:** objeto `8196ab7`
  (`8196ab7ddb4ce471a6718c86b0ab75cbcb839e30`), que apunta a `859c6c2`.
- **`main`:** `9d815815c54dc7122a330674887949106253e407`
  (`docs(v3.73.0): registrar el cierre (commit 859c6c2, tag v3.73.0 y CI 11/11)`).
- **Base de comparación:** `v3.72.0` → release `096dcc4`, tag anotado `v3.72.0`
  (objeto `da6fb6d`), cierre documental `7a8e5de`.
- **Sin GitHub Release** para `v3.73.0`: es una decisión declarada del gerente (solo
  tag, que es la convención real del repo desde `v3.34.0`). El último Release object
  publicado es `v3.33.0`.

**Estado de publicación (verificado, no declarado):**

- **CI 11/11 verde** en
  [run 35204203522](https://github.com/jvelasca/english-tutor/actions/runs/35204203522)
  (sha `859c6c2`, `success`), con **los tres jobs nuevos estrenándose en verde**:
  - `Launcher (Windows, ruff + pytest)` `105145894473` ← **bloqueante**, el job nuevo
  - `Validation gate (checks automáticos)` `105145894604` ← job nuevo
  - `Product origin (Windows, informativo)` `105145894484` ← job nuevo, **informativo**
  - `Backend (ruff + pytest)` `105145894648` · `Frontend (tsc + vitest + build)`
    `105145894171` · `Playwright E2E (visual)` `105145894407` · `Content validation`
    `105145894495` · `Beta V3.0 gate` `105145894504` · `Release consistency`
    `105145894437` · `Launcher (ruff + pytest)` `105145894596` ·
    `Product origin (UI served over HTTPS)` `105145894459`
- **El commit de cierre también está verde:** **CI 11/11** en
  [run 35205022773](https://github.com/jvelasca/english-tutor/actions/runs/35205022773)
  (sha `9d81581`).
- **Nota para el auditor:** el run se dispara con el **push de `main`**; el tag se
  publicó en el mismo push y apunta al commit de release.

**Aviso de `HEAD` e invariante del código.** `main` va **por delante** del commit
auditado con commits **solo documentales** (la nota de cierre y este mismo archivo).
El recuento de commits por delante crece por diseño y **no debe tomarse como
referencia**. Lo que sí es estable y obligatorio es este invariante:

```bash
git diff --stat v3.73.0..main -- backend frontend launcher scripts
```

Debe salir **vacío** (comprobado en el momento de redactar este documento). Es
decir: da igual clonar `main` o hacer `git checkout v3.73.0`; **el código de
producto citado aquí es el mismo**. Si el auditor encuentra una diferencia en esas
cuatro rutas entre el tag y `main`, tiene un hallazgo P0.

**Consistencia de versión:** `backend/config.py::VERSION` es la fuente única
(`scripts/check_release_consistency.py`) y `3.73.0` debe aparecer en **6 orígenes**:
`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
`README.md`, `CHANGELOG.md` y `PLAN.md`.

---

## 2. Artefactos que introduce V3.73 (objeto directo de la auditoría)

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/services/net_interfaces.py` | Descubrimiento de IP de LAN **sin referencias externas**: `select_lan_ipv4` (puro) + `candidate_addresses` + override `ENGLISH_TUTOR_LAN_IP` | Que el descubrimiento no consulta ninguna dirección pública y que es determinista y falsable sin red |
| `backend/services/frontend_dist.py` | `mount_frontend(app, path, require_ui)`: en producto **fail-closed**, en desarrollo fail-open | Que el producto **no puede arrancar pareciendo listo y sin interfaz** |
| `launcher/core.py` (`backend_env()`), `launcher/process_manager.py` | Inyecta `ENGLISH_TUTOR_REQUIRE_UI=1`; **no arranca** sin `frontend/dist/index.html` | Que la exigencia vive en el **runtime de producto**, no en quien lanza el comando |
| `scripts/validation_gate.py` | Arnés de los **7 gates**: `auto`, `record`, `status [--strict]` | Que una validación física que nadie ha hecho todavía es **estado registrado y exigible** |
| `docs/audit/VALIDATION-RELEASE-V373.md` | Runbook de los 7 gates (protocolo + tabla de estado) | Que cada gate referencia un protocolo existente en vez de duplicarlo |
| `docs/audit/generated/release-validation.{md,json}` | Informe **determinista** de las 10 comprobaciones estáticas | Que `auto` es reproducible y **no filtra rutas absolutas del equipo** |
| `backend/tests/test_serve_frontend_v373.py` (**19**) | Candado del fail-closed, las dos mitades | Que renombrar la variable en un solo lado hace fallar el contrato |
| `backend/tests/test_net_interfaces_v373.py` (**23**) | Candado del algoritmo puro + guard anti-deriva por **AST** | Que una IP pública que vuelva al **código** (no a la prosa) hace fallar el test |
| `backend/tests/test_validation_gate_v373.py` (**24**) | Candado del arnés | Que un gate no se cierra sin notas y que `--strict` falla sin los 7 en `pass` |
| `backend/tests/test_docs_drift_v373.py` (**19**) | Candado anti-deriva documental | Que `DEVICE_MATRIX.md` no vuelve a `:5173` y que las fronteras nuevas están declaradas |
| `launcher/tests/test_preflight_v373.py` (**7**) + `test_lan_ip_v373.py` (**13**) | Candados del launcher | El **contrato compartido** de la variable y el algoritmo replicado (el launcher no puede importar el backend) |
| `.github/workflows/ci.yml` (**8 → 11 jobs**) | Cobertura Windows | Que el launcher y el origen de producto se ejercitan en Windows real |

---

## 3. Batería automática — reproducir, no creer

El auditor **debe** ejecutar esto y comparar con lo declarado. Cifras declaradas por
la release (verificadas en el árbol publicado en el momento de redactar):

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q          # declarado: 2779 passed
.venv\Scripts\python.exe -m ruff check .               # declarado: limpio
#   los 4 ficheros nuevos suman 85 (19+23+24+19)

# Frontend
cd ..\frontend
npx vitest run                                         # declarado: 699 passed (83 ficheros)
npx tsc --noEmit                                       # declarado: limpio
npm run build                                          # declarado: OK

# Launcher
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q  # declarado: 113 passed
#   los 2 ficheros nuevos suman 20 (7+13)
..\backend\.venv\Scripts\python.exe -m ruff check .      # declarado: limpio

# Gates de release
cd ..
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist  # declarado: 10/10
backend\.venv\Scripts\python.exe scripts\validation_gate.py status               # declarado: 7 pending
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict      # declarado: exit 1
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict         # declarado: 0 huérfanas
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py            # declarado: 3.73.0, 6 orígenes
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py                        # declarado: OK
cd backend
.venv\Scripts\python.exe scripts\content_validation.py                           # declarado: OK
.venv\Scripts\python.exe scripts\transfer_validation.py                          # declarado: OK (con avisos advisory)
```

**Determinismo del informe (comprobación exigible):**

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
git diff --stat -- docs/audit/generated/release-validation.md docs/audit/generated/release-validation.json
# debe salir VACÍO: el informe regenerado es idéntico al commiteado
```

Y el artefacto commiteado **no puede contener la ruta absoluta de ninguna máquina**:

```powershell
Select-String -Path docs/audit/generated/release-validation.md -Pattern 'E:\\|/home/|/Users/'
# debe salir VACÍO
```

Si el informe cambia al regenerarlo, o filtra una ruta absoluta, la afirmación
«informe determinista» es **falsa** y es un hallazgo.

---

## 4. Áreas auditadas y preguntas falsables

Cada pregunta está pensada para **refutarse desde el clon**, sin credenciales, sin
servicios y sin hardware. Se indica dónde mirar y **qué la falsaría**.

### A. Arquitectura y backend

1. **¿La arquitectura declarada coincide con los directorios reales?** Comparar
   `docs/ARQUITECTURA.md` con el árbol de `backend/` (`services/`, `routers/`,
   `repositories/`, `domain/`, `curriculum/`, `scripts/`). **Falsable:** cualquier
   módulo citado que no exista, o módulo vivo sin declarar.
2. **¿La máquina de estados tiene estados y transiciones cerrados?** Localizar el
   FSM y comprobar que sus estados están enumerados y que un estado inventado se
   rechaza (no que se ignore en silencio). **Falsable:** un `else` que degrada
   cualquier estado desconocido sin error.
3. **¿Hay concurrencia declarada sin resolver?** SQLite + FastAPI: buscar
   `check_same_thread`, `WAL`, `timeout`, `pool`, `asyncio.Lock`. **Falsable:** la
   afirmación «multiusuario» sin ninguna serialización declarada.
4. **¿La persistencia es **migrable** o hay que recrear la BD?** Buscar migraciones
   aditivas y su guard. V3.73 **no** migra: confirmarlo (`VERSION` de BD sin cambio).
5. **¿El tratamiento de errores es honesto?** Buscar `except Exception: pass`,
   `return None` silenciosos en `backend/services` y `backend/routers`. Comparar con
   lo que la API devuelve. **Falsable:** un error que el cliente no puede distinguir
   de «vacío legítimo».
6. **¿Seguridad: qué superficie expone el producto?** El runtime de producto sirve
   la UI y la API por **HTTPS en `:8000`** con **certificado autofirmado**; buscar
   `CORS` (`ALLOWED_ORIGINS`), rutas sin auth, `StaticFiles` con traversal y si el
   `dist` puede servirse fuera de `frontend/dist`. **Falsable:** un `allow_origins`
   con `*`, o un endpoint de escritura sin control.
7. **¿Rendimiento: hay alguna métrica o solo promesas?** Buscar timeouts, cachés,
   límites de tamaño, paginación. Declarar **NO COMPROBABLE** lo que no tenga
   medición: la release **no** aporta benchmarks.
8. **¿Offline: qué toca Internet de verdad?** Ejecutar el instrumento y **buscarlo
   por su cuenta**:

   ```powershell
   cd backend
   .venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
   ```

   Después buscar primitivas de red (`urlopen`, `urlretrieve`, `requests.`,
   `httpx.`, `socket.`, `aiohttp`) en `backend/services`, `backend/routers`,
   `backend/repositories`, `backend/domain` y comparar con `RUNTIME_TOUCHPOINTS` de
   `backend/scripts/audit_dossier.py`. **Falsable:** una primitiva sin declarar hace
   falso el hallazgo central del eje de offline.

### B. Adaptive Engine, evidencia y procedencia

9. **¿El motor adaptativo decide con evidencia rastreable?** Localizar el Planner y
   comprobar que cada decisión lleva su `why`/`because` y que el cliente **no**
   recalcula señales (premisa 21: sin `why` ni `because` no se pinta nada).
   **Falsable:** una decisión pintada en la UI sin `why` procedente del backend.
10. **¿La evidencia es procedural (con origen) o solo un número?** Comprobar que los
    registros de evidencia guardan de dónde vienen y que existe un grafo/panel que lo
    muestra. **Falsable:** un score sin procedencia declarada.
11. **¿Los umbrales de banda están en un solo sitio?** Deben estar unificados en
    `backend/services/cefr.py` (V3.72). **Falsable:** un segundo corte de banda
    duplicado en otro módulo.
12. **¿La divulgación del placement es cierta?** El proyecto declara que el placement
    mide **reconocimiento/meta-lenguaje, no producción**, y que **no hay pantalla de
    nivelación**. Comprobar las dos mitades: que el instrumento lo dice y que **no**
    existe superficie que muestre el resultado sin divulgarlo (hay un candado
    *tripwire*). **Falsable:** un componente que consuma el placement sin divulgación.

### C. Pedagogía, contenido y claims de nivel

13. **¿«Tener un nivel» está definido o es retórica?** Leer
    `docs/CONSTITUCION-PEDAGOGICA.md` y comprobar que el código la implementa: qué
    evidencia exige cada nivel y qué la bloquea. **Falsable:** un camino que conceda
    nivel sin la evidencia exigida.
14. **¿La acreditación se distingue de la práctica?** El proyecto declara que un
    hito de práctica es `functional` y **nunca certifica**. **Falsable:** un badge de
    nivel alcanzable solo con práctica.
15. **¿La cobertura de contenido aguanta la afirmación de CEFR A1–C2?** Ejecutar la
    validación de contenido y leer `docs/audit/AB-PED-COBERTURA.md`. El propio
    proyecto declara **huecos** (niveles altos por debajo del objetivo) y **0 audio
    humano**. Comprobar que **no** se cuentan como cubiertos.
16. **¿La transferencia se mide como se declara?** El proyecto declara que la
    transferencia mide **escrito, no oral**. Verificar en
    `backend/scripts/transfer_validation.py` y sus tests.
17. **¿El feedback textual existe en todas las destrezas?** El proyecto declara que
    **listening solo puntúa, sin mensaje correctivo**. Comprobar si eso sigue siendo
    cierto (`docs/audit/AC-PED-FEEDBACK.md`).
18. **¿Los claims de nivel CEFR están acotados?** Buscar en la UI y en los informes
    cualquier afirmación del tipo «alcanzarás B2» y contrastarla con el mecanismo
    real. **Falsable:** una promesa de nivel sin la evidencia que la constitución
    exige.

### D. Listening (área bajo escrutinio especial)

19. **¿Qué fases existen de verdad?** El proyecto declara **`pre`, `while1`,
    `while2`, `post`, `shadowing`** (`backend/services/listening_flow.py`), **no**
    `pre/while/post` con otra nomenclatura, y declara además que **la UI se salta la
    fase `pre`** (`frontend/src/features/listening/microFlow.ts`, `SKIPPED_STAGES`).
    **Falsable:** que la UI ejecute `pre`, o que alguna fase declarada no se sirva.
20. **¿Hay escucha pasiva y activa, y se distinguen?** Diferenciar comprensión
    global de pregunta nativa y de producción. **Falsable:** que «pasiva» y «activa»
    sean la misma pantalla con distinto título.
21. **¿Dictado y cloze están en el contenido o se derivan?** El proyecto declara que
    **no hay cloze ni dictado parcial ni segmentación en el currículum JSON**: se
    **derivan en runtime** desde otros ítems. Comprobar en
    `backend/services/listening_bottom_up.py` y en
    `backend/curriculum/listening_corpus.json`. **Falsable:** un `"skill": "cloze"`
    en el corpus (contradiría la declaración).
22. **¿El connected speech está realizado en el audio o solo etiquetado?** Comprobar
    que hay **realización real** de reducciones en la síntesis, no solo una etiqueta
    de dificultad. **Falsable:** que el audio de un ítem `connected_speech` no
    contenga la reducción declarada.
23. **¿El shadowing se puntúa de verdad?** El proyecto declara dos cosas distintas:
    que el **shadowing puntúa sobre texto ASR** con score fonético, **y** que en el
    paso `shadowing` del micro-flujo receptivo **la grabación es libre y no
    puntuada**. Comprobar ambas y que no se presente como evaluación acústica.
24. **¿La velocidad es continua o una escalera fija?** El proyecto declara **3
    variantes fijas** (`slow`/`normal`/`fast` → 0.75/1.0/1.25) y que los factores son
    **globales, no por nivel CEFR**. **Falsable:** afirmar calibración de velocidad
    por banda si los factores son globales.
25. **¿El transcript se revela con política o siempre?** Comprobar que hay política de
    revelado/reintentos **por nivel CEFR** y que la UI la respeta.
26. **¿La dificultad del listening es adaptativa?** El proyecto declara que la
    dificultad es **fija por ítem** (vector de dimensiones → escalar) y que la
    adaptación es **por sub-destreza débil y capa cognitiva**, **no** recalibración
    de dificultad (sin IRT). **Falsable:** la palabra «adaptativo» aplicada a la
    dificultad del listening sin motor que la recalibre.
27. **¿El audio es humano o TTS?** El proyecto declara que **todo el listening es TTS
    Piper** y que la biblioteca de audio humana está **vacía**. Comprobar
    `backend/audio_library/manifest.json`. **Falsable:** un ítem con audio humano.

### E. GUI y navegación (el área que el gerente pide con más dureza)

28. **¿La estructura real coincide con la declarada?** El gerente describe este
    árbol:

    ```
    INICIO
      ├── FORMACIÓN REGLADA → Curso / progreso
      └── APRENDER → Listening, Vocabulary, Reading, Grammar, Speaking, Chat
    ```

    **Lo que el código dice hoy** (verificado al redactar este documento) es
    **distinto**, y el auditor debe confirmarlo o refutarlo:

    - La navegación raíz son **3 mundos hermanos** (Inicio, Formación, Aprender) más
      **2 auxiliares** (Diccionario, Traductor). **No** hay un árbol donde Formación
      y Aprender cuelguen de Inicio: `frontend/src/app/routes.ts` y
      `frontend/src/app/Navigation.tsx`.
    - El hub de **Aprender tiene 4 tarjetas** (Listening, Speaking, Vocabulary,
      Grammar), **no 6**: `frontend/src/features/learn/LearnHub.tsx` (`ACTIVITIES`).
    - **Reading y Writing no tienen superficie en el hub** (Reading solo se pinta
      dentro de la vista de práctica; Writing cae al chat libre). **Falsable:**
      encontrar una tarjeta o URL de Reading/Writing en el hub.
    - La navegación es un **hash router propio**, no `react-router`:
      `frontend/src/router/hash.ts` y `frontend/src/App.tsx`.
    - **«Trayecto» no es una pantalla de primer nivel**: solo una **pestaña** de
      Progreso (`/progreso/trayectoria`) y hay un `JourneyScreen` que **no se importa
      en ningún sitio** (código muerto): `frontend/src/features/journey/JourneyScreen.tsx`.
    - **«Ruta»/«route» significa nivel CEFR dentro de una práctica**, no navegación
      (`learn.routeSelected`, `useSelectedRoute`): una fuente real de confusión
      terminológica.

    **Pregunta falsable:** ¿existe todavía confusión entre **Curso / Aprender /
    Trayecto / Vocabulary / Chat**? En particular: Vocabulary existe **como sección
    de unidad del curso y como página independiente**; Chat es una **ruta propia**
    que fuerza `speaking/conversation`, **distinta** de la página de Speaking.
    Dictaminar si eso es un problema de producto o una decisión declarada
    (`docs/DISENO-SPEAKING-UNICO.md`).
29. **¿Los estados loading/error/empty/success son consistentes?** El proyecto
    declara un patrón compartido mínimo (`PanelState`, con `loading | error` +
    reintento) y reconoce que **no hay** componentes compartidos de vacío/carga/error.
    **Falsable:** una pantalla que muestre «vacío» cuando en realidad hay error.
30. **¿Hay errores silenciados?** Buscar `catch {}`, `.catch(() => {})` y comentarios
    «backend no disponible» en `frontend/src`. El proyecto reconoce varios casos
    (registro de sesión, persistencia de ajustes, escenarios de speaking, plan de
    hoy, lectura). Dictaminar cuáles son **benignos** (limpieza de recursos) y cuáles
    son **errores silenciosos con impacto de UI**. **Falsable:** que el proyecto lo
    niegue.
31. **¿Accesibilidad: hay evidencia o solo intención?** El proyecto declara: skip
    link, `aria-current`, pestañas con `role="tablist"/"tab"/"tabpanel"`,
    `role="status"`/`aria-live` en cargas, `role="alert"` en errores y `sr-only`; y
    declara también que **no hay tests de accesibilidad automatizados** (ni
    `axe-core`) y que los tests solo fijan contratos ARIA puntuales. **Falsable:**
    encontrar una dependencia de a11y o, al contrario, que el proyecto afirme
    cobertura de accesibilidad.
32. **¿Responsive/touch/teclado: hay verificación?** El proyecto declara 3 viewports
    en Playwright (1280×800, 768×1024, 390×844) pero **sin aserciones de tamaño
    táctil ni de layout numérico**, y **sin hook de breakpoints** (solo Tailwind).
    Comprobar overflow, scroll, jerarquía visual, tamaño de objetivos táctiles
    (44/48 px) y navegación por teclado. **Falsable:** declarar la matriz de
    dispositivos como verificada: `docs/DEVICE_MATRIX.md` está **en ⬜**.
33. **¿Los estados de la UI tienen feedback al usuario?** Comprobar que toda acción
    con efecto (descargar voz, grabar, enviar) informa de avance o de fallo, y
    buscar acciones mudas.

### F. Runtime, instalación y entorno

34. **¿El fail-closed es real y está en los dos lados?** Quitar (o renombrar)
    `frontend/dist/index.html` y comprobar que el **runtime de producto** eleva un
    error accionable, **y** que un `uvicorn main:app` manual sigue siendo fail-open
    (es el modo desarrollo declarado). **Falsable:** que el producto arranque sin UI.
35. **¿HTTPS y micrófono?** El proyecto declara que sin HTTPS en LAN
    `navigator.mediaDevices` es `undefined` y el micrófono se rompe, por eso el
    certificado autofirmado es obligatorio. Comprobar el certificado (SANs) y que se
    genera de forma determinista e idempotente. **Falsable:** servir producto por
    HTTP y declararlo equivalente.
36. **¿TTS/STT/Ollama: qué es local y qué necesita Internet?** El proyecto declara
    que la voz se descarga **una vez** (~60 MB, con Internet, con consentimiento) y
    que el modelo LLM por defecto es `llama3.1:8b` vía Ollama. Comprobar el modelo
    por defecto real en `backend/config.py` frente a lo que `README.md` dice.
    **Falsable:** una discrepancia entre `config.py` y la documentación (hubo una en
    el pasado: se declaraba un modelo que el código **veta**).
37. **¿La instalación limpia está documentada o ejecutada?** El proyecto declara que
    **no** se ha probado en una máquina físicamente limpia (`RB-05`) y que
    `backend/models/` (~1,1 GB) no se versiona. **Falsable:** declararla verificada.
38. **¿El launcher es Windows-only?** Comprobar que se declara, y que el job de CI en
    Windows **no sustituye** a la prueba humana (gate G3).

### G. CI/CD y release

39. **¿Cuántos jobs y cuáles son bloqueantes?** Deben ser **11**, con
    `launcher-windows` **bloqueante** y `product-origin-windows`
    **informativo declarado** (`continue-on-error: true`) con criterio de promoción
    escrito. **Falsable:** que el informativo pase por bloqueante en la práctica, o
    que el proyecto lo cuente como certificación.
40. **¿`--strict` se exige en CI?** **No** puede estar en CI (los gates son acción
    humana: un CI que los exigiera sería rojo permanentemente). Hay un test que lo
    fija. **Falsable:** encontrar `validation_gate.py status --strict` en el workflow.
41. **¿La reproducibilidad aguanta?** Regenerar el informe y el par de auditoría de
    red y comprobar **diff vacío** e **idempotencia**:

    ```powershell
    backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
    cd backend
    .venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
    .venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
    cd ..
    git diff --stat -- docs/audit/generated/
    ```

42. **¿Los artefactos commiteados son reproducibles o llevan la huella del autor?**
    Buscar rutas absolutas, timestamps y orden no determinista en
    `docs/audit/generated/`. **Falsable:** cualquier ruta absoluta de una máquina.
43. **¿La documentación declara lo que el código hace?** Buscar **drift** entre docs
    y código, en particular en `docs/DEVICE_MATRIX.md` (debe apuntar a `:8000` y no
    al dev server de Vite), `docs/PREMISAS.md`, `docs/ARQUITECTURA.md`, `README.md`
    y `docs/RELEVO.md`. **Falsable:** la deriva ya corregida que reaparezca.

---

## 5. Matriz de cierre (la rellena el auditor)

Cada fila debe sostenerse en **evidencia de código o de test** del árbol publicado.
Si un área no se puede comprobar sin hardware o sin persona, se marca **NO
COMPROBABLE** con el motivo; **no** se puntúa por lo que la documentación promete.

| Área | 🟢/🟡/🔴 | Evidencia (archivo:línea, test o comando) | DEMOSTRADO / DECLARADO / NO COMPROBABLE |
|---|---|---|---|
| Arquitectura | | | |
| Backend | | | |
| Adaptive Engine | | | |
| Pedagogía | | | |
| Contenido | | | |
| GUI | | | |
| Responsive | | | |
| Listening | | | |
| Speaking | | | |
| TTS/STT | | | |
| Offline | | | |
| Instalación | | | |
| Seguridad | | | |
| CI | | | |
| Documentación | | | |

**Criterio de veredicto:** `APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`
para el salto a **V4.0**, con la lista de lo que debe cerrarse antes. Recordatorio:
la puerta declarada de V4.0 es `validation_gate.py status --strict` saliendo **0**.

---

## 6. Reglas duras para el auditor

1. **Solo lectura.** No se modifica nada; no se abren PRs correctivos.
2. **Separar lo verificado de lo declarado.** Toda afirmación que no se pueda
   reproducir desde el clon se marca como **DECLARACIÓN**, no como hecho.
3. **Severidad `P0`–`P3`** (`P0` rompe una garantía central, `P3` es documental), y
   **una afirmación por hallazgo**, con `archivo:línea` del árbol publicado y
   comando de reproducción.
4. **Falsabilidad primero:** un hallazgo que no se pueda refutar con un comando no es
   un hallazgo. **Nada de «podría», «convendría» ni «en el futuro»** sin dato.
5. **Lo que no se pueda comprobar se declara NO COMPROBABLE**, con el motivo.
6. **Sin cortesía:** si el producto no demuestra lo que dice, decirlo; si lo
   demuestra, decirlo también.
7. **No confundir el instrumento con la validación.** Que exista un gate, un candado
   o un informe **no** es evidencia de que el hecho esté verificado.

---

## 7. Honestidad esperada del informe

El auditor debe pronunciarse **explícitamente** sobre estas declaraciones del propio
proyecto, que acotan lo que puede leerse como demostrado:

- **Los 7 gates están en `pending`.** V3.73 construye el instrumento; **no** ejecuta
  la validación física. Nadie ha hecho el corte de red real (`RA-05`), ni una
  instalación en máquina limpia (`RB-05`), ni pruebas en móvil real, ni pruebas con
  audio real. **Comprobación abierta:** el código marca los **7** gates como
  `human: bool = True` (`scripts/validation_gate.py`) sin ninguna entrada que lo
  sobrescriba, mientras `PLAN.md` y `release-notes-v3.73.0.md` dicen «7 gates (5 de
  ellos acción humana)». **Dictaminar cuál de las dos cifras es la correcta** y si la
  discrepancia es un hallazgo documental.
- **`product-origin-windows` es informativo**, no bloqueante, y así se declara: su
  verde en el run de publicación **no** certifica Windows.
- **El fail-closed cubre el arranque, no la ejecución degradada.** Si el artefacto
  desaparece **después** de arrancar, el proceso sigue sirviendo lo montado.
- **El descubrimiento de LAN cambia de técnica, no de garantía.** `getaddrinfo` del
  nombre local puede devolver solo loopback en Windows mal configurados; por eso hay
  dos vías, un override declarado y un último recurso `127.0.0.1`.
- **`auto` es estático y stdlib pura:** comprueba el repositorio, **no** el
  comportamiento en runtime. No sustituye a nada.
- **El listening no tiene audio humano, ni evaluación acústica, ni feedback textual
  correctivo**, y su dificultad **no** es adaptativa. La biblioteca de audio humana
  está vacía.
- **La accesibilidad y la matriz de dispositivos no tienen evidencia ejecutada:**
  `docs/DEVICE_MATRIX.md` está **en ⬜** y no hay tests de accesibilidad.
- **Siguen abiertos:** `RA-02` (endpoint de Ollama sin declarar en `config.py`),
  `RA-07` y `RD-05` como deuda aceptada.

---

## 8. Cierre

**Estado del punto de entrada: CERRADO (2026-09-17).** Verificado contra GitHub, no
contra el árbol local:

- **Commit de release:** `859c6c2` (`859c6c2115a7675af2d657b179ae9bfc7f9f5fbf`).
- **Tag anotado:** `v3.73.0` (objeto `8196ab7`), apuntando a `859c6c2`.
- **`main`:** `9d81581` (cierre documental), con `859c6c2` como ancestro directo.
- **CI 11/11 verde** en el
  [run 35204203522](https://github.com/jvelasca/english-tutor/actions/runs/35204203522)
  (publicación, sha `859c6c2`) y en el
  [run 35205022773](https://github.com/jvelasca/english-tutor/actions/runs/35205022773)
  (cierre, sha `9d81581`).
- **Invariante del código:** `git diff --stat v3.73.0..main -- backend frontend
  launcher scripts` sale **vacío**.
- **Consistencia de versión:** `3.73.0` en los **6 orígenes**
  (`scripts/check_release_consistency.py`).

**Informe esperado:** `docs/audit/AI-AUDITORIA-CIERRE-V373.md`.
