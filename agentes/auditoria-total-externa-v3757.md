# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.75.7`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **lo publicado en el tag
> `v3.75.7`**. La revisión es **de solo lectura**: no se cambia código, datos,
> configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué ahora.** `v3.75.7` cierra **la parte de
> listening** que pidió el gerente —cinco iteraciones de producto y de UI— y, de
> paso, **el P1 que destapó la auditoría interna de esta misma tanda**: dos ítems
> del **banco heredado** (`l18`, `l19`) seguían etiquetados de producción con
> opciones, así que la **RUTA B1 seguía sirviendo la tarjeta de dictado** que la
> iteración anterior decía haber cerrado. Este documento es el ancla de esa
> auditoría y declara, sin adornos, **qué cambia y qué no** frente a `v3.75.2`.
>
> **Aviso de encuadre (léelo antes de puntuar).** A diferencia de `v3.75.2` —que era
> documental y de instrumento—, **esta release SÍ cambia el producto**: toca backend
> de listening, frontend (listening, rutas de quiz, apariencia, i18n, estilos) y el
> launcher. Por eso **el invariante clásico de esta casa («el diff de producto sale
> vacío») no se declara**: sería falso. En su lugar se declara una **lista cerrada**
> de lo que cambia y tres invariantes **acotados** que sí pueden salir vacíos o
> exactos (§1.1). Un invariante que no se puede cumplir **no se escribe**.
>
> **Estado:** entregado 2026-09-20, **dentro del commit de release** de `v3.75.7`.
> **Informe esperado:** `docs/audit/AP-AUDITORIA-TOTAL-V3757.md`. Prefijo **`AP`**
> porque `AA`–`AF` los ocupan los dossiers de V3.70, `AG`–`AM` los del motor y la
> pausa pedagógica, `AN` está reservado por el punto de entrada de `v3.75.1` y `AO`
> lo ocupa la política psicométrica (`AO-POLITICA-PSICOMETRICA-V40.md`). Ver la nota
> de prefijos en `PLAN.md`.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (nota de la posición vigente) y **§0 «START
   HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. `release-notes-v3.75.7.md` — **el documento central**: describe las cinco
   iteraciones, el P1 y **los 12 límites declarados**.
4. `docs/audit/PARKED.md` — lo **aparcado a propósito**. Sus secciones **`V3.75.3`**
   a **`V3.75.7`** son la declaración honesta de lo que esta tanda **no** cierra.
5. **Este documento**, hasta el final.
6. `docs/UI_V3.1.md` §3.2–3.5 — las cuatro convenciones de UI que esta tanda fija
   (rampa de color, dos acentos, composición de la repetición, icono del
   desplegable).
7. `docs/LISTENING_ENGINE_4.0.md` — la especificación de listening, **con su nota de
   corrección** sobre `c071`/`c084` (documento fechado que no se reescribe).
8. `docs/BETA_GATES.md`, `docs/audit/KIT-VALIDACION-GATES.md` y
   `docs/audit/VALIDATION-RELEASE-V373.md` — los 7 gates: **siguen en `pending`**;
   el kit es la planilla de campo, no una validación.
9. `docs/ARQUITECTURA.md`, `docs/PREMISAS.md`, `docs/CONSTITUCION_PEDAGOGICA.md`,
   `CHANGELOG.md` y `docs/audit/TEMPLATE.md` (formato del informe).

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
- **Release auditada: el tag anotado `v3.75.7`.** Los identificadores exactos se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.75.7            # objeto del tag anotado
git rev-parse v3.75.7^{commit}   # commit de release (el SHA exacto que se audita)
git log -1 --format='%H %s' v3.75.7^{commit}
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run de CI que dispara su
  push: son datos que solo existen **después** de publicar. Fijarlos obligaba a un
  commit de re-anclaje **posterior al tag**, que quedaba a su vez fuera del tag
  siguiente, y por eso `main` iba siempre por delante en documentación. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando** y este archivo es coherente **dentro de su propio tag**. Si un documento
  de este tipo vuelve a fijar un SHA o un run a mano, es una **regresión**.

- **Base de comparación:** `v3.75.2` (la release inmediatamente anterior). Para el
  arco largo, `v3.73.6` (el árbol de la última auditoría externa con producto
  estable) y `v3.75.1` (el baseline que la pausa pedagógica declaró como punto de
  reinicio).

- **Una advertencia de higiene que el auditor debe conocer:** entre el tag
  `v3.75.2` y el commit de release hay **siete commits ya en `main`** que
  **post-datan** el tag `v3.75.2` —tres de ellos son documentación *etiquetada*
  «v3.75.2»—. Es la deriva que V3.73.5 declaró cerrada y que **aquí se declara, no
  se oculta**: su lista cerrada está en §1.2. Si el auditor considera que un commit
  documental posterior al tag lo deja desfasado, **tiene razón por definición**, y
  el hallazgo es de proceso, no de producto.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

**(a) El currículum de checks y las evaluaciones: VACÍO.** Ni una línea.

```bash
git diff --stat v3.75.2..v3.75.7 -- \
  backend/curriculum/a1.json backend/curriculum/a2.json \
  backend/curriculum/b1.json backend/curriculum/b2.json \
  backend/curriculum/c1.json backend/curriculum/c2.json \
  backend/curriculum/assessments.json
```

Debe salir **vacío**. Es decir: el **P0 posicional cerrado en V3.75.1 no se reabre**
y las evaluaciones **siguen con sus sesgos declarados** (no se tocan en esta
release). Si no sale vacío, tienes un hallazgo **P0**.

**(b) El corpus de listening cambia en EXACTAMENTE tres líneas.**

```bash
git diff v3.75.2..v3.75.7 -- backend/curriculum/listening_corpus.json
```

Esperado, y **nada más**: la línea `"version"` (`3.0.0` → `3.0.1`) y la línea
`"skill"` de **`c071`** (`dictation` → `numbers`) y de **`c084`** (`shadowing` →
`phrase_recognition`). Ningún `script`, ninguna `options`, ningún `id`, ninguna
`difficulty_vector` se mueve. Si aparece un ítem más, es un hallazgo.

**(c) El banco heredado cambia en EXACTAMENTE dos etiquetas.**

```bash
git diff v3.75.2..v3.75.7 -- backend/services/listening.py
```

Esperado: solo el `"skill"` de **`l18`** (`dictation` → `numbers`) y de **`l19`**
(`shadowing` → `phrase_recognition`), más los comentarios que explican el cambio.
Ningún `script`, ninguna `options` y ningún `audio_id` se mueve: **cambia la
etiqueta, no el contenido**.

**(d) El diff de producto: no vacío, y declarado como lista CERRADA.**

```bash
git diff --stat v3.75.2..v3.75.7
```

Cualquier ruta **fuera** de las áreas declaradas en §1.2 y §1.3 es un hallazgo.
Las áreas de producto son exactamente: `backend/services`, `backend/routers`,
`backend/repositories`, `backend/domain`, `backend/curriculum`, `frontend/src` y
`launcher`. **No** se toca `backend/data/`, `backend/models/`, `frontend/dist/`
(no versionados) ni `backend/scripts/` de producto.

### 1.2 Lista cerrada — los siete commits que post-datan `v3.75.2`

```bash
git log --oneline v3.75.2..v3.75.7
git diff --stat v3.75.2..HEAD
```

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `launcher/core.py` | Fix del launcher | Que el **motivo real** de «Detenido» llega a la ventana |
| `launcher/launcher.py` | Fix del launcher | Que la **etiqueta de la interfaz es honesta** y el log deja de crecer |
| `launcher/process_manager.py` | Fix del launcher | Que el motivo del fallo llega a la ventana y el log **no crece sin límite** |
| `launcher/ui.py`, `launcher/tests/test_ui.py` | Fix del launcher + tests | Que la etiqueta honesta está fijada por test |
| `launcher/tests/test_core.py`, `launcher/tests/test_process_manager.py` | Tests | Los candados de los dos fixes |
| `scripts/validation_gate.py` | Instrumento (**no** es producto) | Que la evidencia **no puede depender del entorno** |
| `docs/audit/AO-POLITICA-PSICOMETRICA-V40.md` | Dossier | La **política de autoría** derivada de la pausa |
| `docs/audit/PARKED.md`, `PLAN.md`, `docs/ARQUITECTURA.md` | Documentación | El registro de lo anterior |
| `docs/audit/generated/release-validation.{md,json}` | Artefacto determinista | Regenerado (deriva `3.75.0` → `3.75.2`) |

Estos siete commits **no forman parte de las cinco iteraciones** de esta release: se
publican con ella porque estaban en `main` sin tag. Se declaran para que el auditor
pueda decidir si eso es un problema de proceso.

### 1.3 Lista cerrada — el diff de las cinco iteraciones

`git diff --stat v3.75.2..v3.75.7 -- backend frontend/src launcher` da **84
ficheros** (5 896 inserciones / 862 borrados). Por área:

| Área | Qué cambia | Dónde mirar |
|---|---|---|
| **Listening (backend)** | La voz pedida se valida (`tts.pick_requested_voice`), la voz usada se declara (`X-TTS-Voice`), el flujo de producción sale de **una sola** constante | `backend/services/tts.py`, `backend/services/listening_flow.py`, `backend/services/listening.py`, `backend/domain/listening.py`, `backend/routers/listening.py`, `backend/routers/voz.py` |
| **Listening (frontend)** | La pantalla se reescribe: sin el paso «He escuchado», cabecera con «Otro ejercicio», tarjeta de audio con `VoicePicker`, repetición con STOP y tres composiciones | `frontend/src/features/listening/*`, `frontend/src/components/ItemReplayButton.tsx`, `frontend/src/components/VoicePicker.tsx`, `frontend/src/hooks/useVoiceChoice.ts`, `frontend/src/utils/voices.ts`, `frontend/src/api/voz.ts` |
| **Rutas de quiz** | Se aplica la convención visual de `V3.75.4` y el mismo `VoicePicker` | `frontend/src/features/routes/QuizRoutePage.tsx` |
| **Apariencia / niveles** | La rampa de 7 pasos, los 3 esquemas y `data-levels` | `frontend/src/utils/cefr.ts`, `frontend/src/utils/appearance.ts`, `frontend/src/hooks/useAppearance.ts`, `frontend/src/styles/legacy.css`, `frontend/src/components/{LevelBadge,SettingsDialog,LearningProfile,JourneyNode}.tsx` |
| **Análisis** | Sale del ejercicio y pasa a `/analisis`; el panel flotante **se borra** | `frontend/src/features/analysis/AnalysisScreen.tsx` (nuevo), `frontend/src/components/AnalysisPanel.tsx` (**borrado**), `frontend/src/app/{Header,Workspace,PracticeView}.tsx`, `frontend/src/router/*` |
| **Desplegables** | El icono dice qué hay dentro y el panel reserva la columna del botón | `frontend/src/components/InfoDisclosure.tsx` + su test |
| **i18n** | Claves nuevas y retirada de huérfanas | `frontend/src/utils/i18n.ts` |
| **Launcher** | La preferencia de LAN se persiste y la decisión sale de `tkinter` | `launcher/core.py`, `launcher/config_store.py` (nuevo), `launcher/launcher.py` |

### 1.4 Estado de publicación (verificado por comando, no fijado a mano)

```bash
git rev-parse v3.75.7^{commit}      # SHA exacto del commit del tag
gh run list --commit $(git rev-parse v3.75.7^{commit}) --limit 1
```

La run del commit del tag debe estar en **`success`** con los **12 jobs** en verde
(un nombre por línea, para que un `grep` literal funcione):

- `Backend (ruff + pytest)`
- `Frontend (tsc + vitest + build)`
- `Release consistency`
- `Validation gate (checks automáticos)`
- `Beta V3.0 gate`
- `Content validation`
- `Playwright E2E (visual)`
- `Launcher (ruff + pytest)`
- `Dependency audit (pip-audit + npm audit)` (**bloqueante**)
- `Product origin (UI served over HTTPS)`
- `Launcher (Windows, ruff + pytest)` (**bloqueante**)
- `Product origin (Windows, informativo)` (**informativo declarado**,
  `continue-on-error: true`)

**Consistencia de versión:** `backend/config.py::VERSION` es la fuente única
(`scripts/check_release_consistency.py`) y `3.75.7` debe aparecer en **6 orígenes**:
`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
`README.md`, `CHANGELOG.md` y `PLAN.md`.

**Una particularidad que el auditor debe entender antes de contar versiones:**
esta release publica **cinco iteraciones** (`V3.75.3`–`V3.75.7`) bajo **una sola
etiqueta**. `CHANGELOG.md` y `PLAN.md` llevan **cinco entradas**; **solo `v3.75.7`
tiene tag**. Que `V3.75.3`–`V3.75.6` no existan como tag **es una decisión
declarada**, no un hueco (ver §2 y `release-notes-v3.75.7.md` §2). Si el auditor
considera que el historial debería tener un tag por iteración, el hallazgo es de
proceso y debe citar esta declaración.

---

## 2. Qué trae esta línea, y con qué palabras

### 2.1 `V3.75.3` — preferencias del launcher, listening sin fricción, Análisis global

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `launcher/config_store.py` (nuevo), `launcher/core.py` | El modo LAN se **persiste** en `config.json` (atómico, `os.replace`) y la decisión sale de `tkinter` | Que el modo LAN pasa de decisión de **sesión** a decisión de **instalación**, y que **reabre** una vía para arrancar expuesto |
| `frontend/src/features/listening/ListeningPractice.tsx` | `while1` desaparece; la señal de «he escuchado» es **pulsar PLAY** | Que sin pulsar PLAY no se ven las opciones, y que un fallo de audio **no** avanza la etapa |
| `frontend/src/features/analysis/AnalysisScreen.tsx` (nuevo), `/analisis` | El Análisis sale del ejercicio | Que reutiliza endpoints existentes y **no crea ninguno** |
| `frontend/src/components/AnalysisPanel.tsx` | **Borrado** | Que el panel flotante ya no existe y `resize.spec.ts` se reescribió sobre el asa del sidebar |

### 2.2 `V3.75.4` — listening pulido y rampa de niveles configurable

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `frontend/src/utils/cefr.ts`, `styles/legacy.css` | Rampa de **7 pasos** (`.lv-*` estáticas) | Que `cefrTone` de 3 tramos ya no existe en el código y que el color tiene una sola puerta |
| `frontend/src/utils/appearance.ts`, `hooks/useAppearance.ts`, `components/SettingsDialog.tsx` | 3 esquemas (**Semáforo**, **Espectro**, **Monocromo**) con `data-levels` | Que la rampa es elegible **por perfil** (`level_scheme` en `PUT /api/settings`) sin backend nuevo |
| `frontend/scripts/contrast_audit.mjs` | Mide cada paso sobre su relleno **compuesto** | **472 pares + 4 guardas, 0 bloqueantes**; el color es **medido**, no elegido a ojo |
| `frontend/src/components/LearningProfile.tsx` | `bandToLevelKey(numeric)` | Que el fallo previo (un **número** donde se esperaba una banda) queda arreglado |

### 2.3 `V3.75.5` — voz configurable y dos acentos

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/services/tts.py` | `pick_requested_voice` | Que **solo** se acepta una voz instalada y del idioma pedido, y que un id de voz **no** sirve como *path traversal* |
| `frontend/src/components/VoicePicker.tsx` (nuevo) | Voz A, Voz B y chips de prueba | Que el «…» deja de ser un cartel y pasa a **configurar** |
| `frontend/src/hooks/useVoiceChoice.ts` (nuevo) | Store de módulo | Que hay **una sola** lectura del catálogo para toda la app, y que el estado **se vacía al cambiar de perfil** |
| `frontend/src/utils/voices.ts` | `suggestAltVoice`, `buildReplayText` | Que la B se sugiere **sin cruzar idiomas** y que la composición de la lectura es función **pura** |

### 2.4 `V3.75.6` — STOP, lectura corta y la RUTA B1

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/curriculum/listening_corpus.json` | `c071` → `numbers`, `c084` → `phrase_recognition` | Que la RUTA B1 mostraba «Enviar dictado» porque **dos ítems estaban mal etiquetados**, no porque el flujo fallara |
| `frontend/src/api/voz.ts` | `stopSpeaking()` + una sola locución a la vez | Que parar **no** es un error (la promesa resuelve) y que antes las locuciones **se solapaban** |
| `frontend/src/utils/voices.ts`, `i18n.ts` | `replay_scope` con 3 composiciones | Que el defecto es `"item"` y que el valor histórico `"all"` **no pierde** la elección de quien lo había elegido |
| `frontend/tests/visual/listeningReplayStop.spec.ts` (nuevo) | Lee el **cuerpo real** del `POST /api/tts` | Que la composición se verifica **de punta a punta**, no solo en unitarios |

### 2.5 `V3.75.7` — el icono, el texto tapado y el P1 del banco heredado

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `frontend/src/components/InfoDisclosure.tsx` | `content: "info" \| "options"` (defecto `"info"`) | Que el icono **(i)/(...)** **promete lo que hay dentro** y que un panel nuevo no puede prometer opciones por omisión |
| `frontend/src/components/InfoDisclosure.tsx` | `pr-12` en la variante de esquina | Que el panel reserva la **columna** del botón y su primera línea **no** queda tapada |
| `backend/services/listening_flow.py` | `PRODUCTION_SKILLS` (fuente única) | Que los skills de producción se declaran **una vez** y `build_item_flow` los consume |
| `backend/services/listening.py` | `l18`, `l19` reetiquetados | Que el **banco heredado** seguía sirviendo la tarjeta de dictado en B1 |
| `backend/tests/test_listening_corpus.py` | Barrido sobre **todo** `QUESTION_BANK` + control positivo | Que la guarda **muerde** aunque hoy su barrido sea vacío |
| `backend/tests/conftest.py` | Fixture `production_items` | Que los tests de producción ya **no** dependen de ítems concretos del banco |

---

## 3. Batería automática — reproducir, no creer

El auditor **debe** ejecutar esto y comparar con lo declarado:

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q          # declarado: 2909 passed, 0 skipped
.venv\Scripts\python.exe -m ruff check .              # declarado: limpio

# Los invariantes de §1.1 (los tres primeros deben dar el resultado exacto declarado)
git diff --stat v3.75.2..v3.75.7 -- backend/curriculum/a1.json backend/curriculum/a2.json `
  backend/curriculum/b1.json backend/curriculum/b2.json backend/curriculum/c1.json `
  backend/curriculum/c2.json backend/curriculum/assessments.json    # declarado: VACÍO

# Consistencia de versión
.venv\Scripts\python.exe ..\scripts\check_release_consistency.py   # declarado: 3.75.7 en 6 orígenes

# Frontend
cd ..\frontend
npx tsc --noEmit                                      # declarado: limpio
npx vitest run                                        # declarado: 806 passed (93 ficheros)
npm run build                                         # declarado: OK
npm run audit:contrast                                # declarado: 472 pares + 4 guardas, 0 bloqueantes
npm audit --omit=dev --audit-level=high               # declarado: 0 vulnerabilidades

# i18n (el script vive en la raíz y necesita el venv del backend)
..\backend\.venv\Scripts\python.exe ..\scripts\check_i18n_coverage.py --strict
                                                      # declarado: 1512 claves, 0 huérfanas

# Launcher
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q  # declarado: 178 casos
..\backend\.venv\Scripts\python.exe -m ruff check .      # declarado: limpio

# Visual (un worker: ver §6.9)
cd ..\frontend
npx playwright test --workers=1                       # declarado: 44 passed / 28 skipped / 0 failed
```

**Nota honesta sobre el reparto de la suite de backend.** `2909 passed, 0 skipped`
es el recuento **medido en el árbol de desarrollo** (con `frontend/dist` construido
y los modelos presentes). En un **clon limpio** el reparto **no** es idéntico:
algunos casos se **saltan** por **artefactos no versionados** —`frontend/dist` (1) y
el **modelo Whisper opt-in** (2)—. El **invariante** es el **total de casos**; el
reparto `passed`/`skipped` **no** lo es. Es la errata que V3.73.6 dejó escrita: si
ves un número distinto de `passed` en un clon limpio, **no** es un hallazgo por sí
mismo; cuenta los casos.

---

## 4. Áreas y preguntas falsables

Cada pregunta debe responderse con **evidencia del árbol publicado**
(`archivo:línea`), **comando de reproducción** y **qué la falsaría**. Si no se puede
comprobar sin hardware o persona: **NO COMPROBABLE**.

### A. El ancla, la release y el historial

1. ¿Se sostienen los **tres invariantes acotados** de §1.1 (currículum vacío, corpus
   en 3 líneas, banco heredado en 2 etiquetas)? ¿O hay algo más movido?
2. ¿Contiene el tag `v3.75.7` **este mismo documento** (y no un commit posterior)?
3. ¿Es el commit del tag **final** (sin commits documentales posteriores)?
4. **Los siete commits que post-datan `v3.75.2`** (§1.2): ¿es correcta la lista?
   ¿Alguno cambia producto de una forma que esta release no declara?
5. **Cinco iteraciones, una etiqueta** (§1.4): ¿es defendible que `V3.75.3`–`V3.75.6`
   no tengan tag, habiendo entradas de `CHANGELOG` y `PLAN` con su nombre? El
   proyecto lo declara como decisión; dictamínala.
6. ¿Está `3.75.7` en los **6 orígenes** y coinciden entre sí?

### B. El P1 del banco heredado (el hallazgo que motivó media release)

7. ¿Sigue habiendo **algún** ítem de `PRODUCTION_SKILLS` (`dictation`/`shadowing`)
   con `question` u `options` en **todo** `QUESTION_BANK`? Ejecuta el barrido del
   test a mano sobre el banco completo, no solo sobre los ids `c`.
8. ¿Sirve la **RUTA B1** una pregunta receptiva con opciones? ¿Y las otras cinco?
9. El control positivo (`test_production_guard_bites_on_a_synthetic_offender`):
   ¿**muerde** de verdad? Inyecta un ítem de producción con opciones en una copia
   del banco y comprueba que la guarda lo reconoce. Si no lo hace, el test es
   decorativo y **su verde no prueba nada**.
10. ¿Es `PRODUCTION_SKILLS` **de verdad** la fuente única, o queda algún sitio con
    la tupla `("dictation", "shadowing")` escrita a mano? (Se declara que estaba
    duplicada en **tres** sitios antes de esta release; verifica cuántos quedan.)
11. **El provenance del banco.** `LISTENING_BANK_VERSION` sigue en **`7.0.0`**
    aunque el contenido servido cambió. El proyecto lo declara a propósito (la
    constante **también** nombra la caché de audio y ningún `script` ni `audio_id`
    cambió). ¿Es aceptable ese hueco —dos contenidos distintos con el mismo
    `bank_version`— o debe bumpearse? Razona el coste.
12. ¿Sigue el **shadowing** alcanzable como paso opcional del micro-flujo receptivo,
    o el reetiquetado lo ha dejado inalcanzable sin que nadie lo note?

### C. Escritura y autorización (heredado: el P0 sigue abierto)

13. **Identidad:** ¿`POST /api/session` acepta cualquier `user_id` **existente** sin
    credencial? El proyecto lo declara y lo llama «no autenticación». ¿Lo es?
14. ¿Se puede **forjar** una sesión sin el secreto del equipo? ¿Y leer la cookie
    desde JavaScript (`HttpOnly`)?
15. ¿Cierra `PATCH /api/users/{id}` el borde de **autorización** (403 si el id no es
    el de la sesión)?
16. **Frontera de red:** ¿es `lan_mode()` **fail-closed** con valores raros
    (`ausente`, `0`, `false`, `no`, `off`)? **Y ahora la pregunta nueva de esta
    release:** con la preferencia **persistida** en `config.json`, ¿arranca expuesto
    un equipo sin que nadie lo declare en esa sesión? ¿Se lee como **cerrado** un
    valor editado a mano que no sea el booleano `True` (`1`, `"sí"`)?
17. ¿Pueden discrepar las dos mitades de la política de CORS (la regex compilada por
    `CORSMiddleware` y `security.origin_allowed`)? Hay un test que lo compara:
    ¿muerde?
18. ¿Viaja `session.secret` en los **backups**? ¿Y qué pasa al **restaurar**?
19. **Superficie sin sesión:** ¿responde `/api/system/status` sin sesión y **no**
    devuelve datos de alumno? ¿Está la lista completa?

### D. TTS, voz y disco (lo nuevo de `V3.75.5`)

20. `tts.pick_requested_voice`: ¿rechaza de verdad una voz **no instalada** y una voz
    **de otro idioma**? ¿Qué pasa si el id de voz trae `..`, `/`, `\` o una ruta
    absoluta? El proyecto afirma que sin validar sería *path traversal* por
    construcción: **intenta falsarlo**.
21. Con una sola voz instalada, ¿**solo** aparece el botón A? ¿Y el PLAY sigue
    sonando en voz A?
22. ¿Declara `X-TTS-Voice` la voz **realmente usada** y no la pedida, cuando hay
    degradación? ¿Puede el frontend creer que oyó **dos acentos** y haber oído la
    misma voz dos veces?
23. `replay_scope`: ¿es `"item"` el **defecto** de verdad para un perfil nuevo
    (sin la clave guardada)? ¿Se normaliza `"all"` a `"withOptions"` y **no** a
    `"item"`?
24. `buildReplayText`: ¿puede producir una lectura **vacía**? ¿Puede **repetir** el
    ítem cuando el script *es* la pregunta? ¿Puede **filtrar la respuesta correcta
    antes** de que el alumno responda? El proyecto declara que no; busca el caso.

### E. UI: el icono, el texto tapado y la rampa de color

25. `InfoDisclosure`: ¿es `"info"` el **defecto** del prop `content`? ¿Puede un panel
    nuevo prometer opciones por omisión? Recorre la app y **cuenta** los
    disparadores: el proyecto declara **11** (8 con (i), 1 con (...), 3 sin cambio).
26. ¿Reserva `pr-12` la **columna** del botón en la variante de esquina? ¿Es cierto
    que **ningún** nodo de texto del panel intersecta el rectángulo del disparador en
    los tres breakpoints? El proyecto declara que lo midió y que la guarda **mordió**
    al revertirla. Reproduce el revertido y comprueba que el test falla.
27. **Alcance honesto de la medición de contraste:** el proyecto declara que mide la
    tinta sobre el relleno **compuesto** en dos fondos, **no** cada sitio donde se
    dibuja una insignia. ¿Hay algún sitio donde el par real **no** sea el medido?
28. **`cefrTone` en documentos históricos:** se declara que sobrevive en briefs y
    actas fechadas y que el código no tiene ninguna referencia. Compruébalo: si el
    código **sí** lo usa en algún sitio, el hallazgo contradice la declaración.
29. ¿Es cierto que el color del nivel **no** implica dominio? Busca cualquier texto
    de UI que pueda leerse como «estás en A2» a partir del color.

### F. Deriva documental

30. ¿Declara `docs/RELEVO.md` la posición vigente correcta en su **cabecera**?
31. ¿Está `PLAN.md` sin declarar ningún prefijo de auditoría como libre cuando ya
    está ocupado? (`AN` reservado, `AO` ocupado, `AP` reservado por este documento.)
32. ¿Sigue `docs/DEVICE_MATRIX.md` **entero en ⬜**? El proyecto lo declara: si el
    auditor encuentra una celda rellena sin evidencia, es un hallazgo **al revés**.
33. ¿Declara `docs/ARQUITECTURA.md` el número **real** de tests del launcher (161
    funciones / 178 casos)? Un test de deriva lo exige: ¿muerde?
34. **`docs/LISTENING_ENGINE_4.0.md` es un documento fechado (2026-09-09)** que
    citaba `c071`/`c084` como evidencia de dictado y shadowing. Se declara que
    **no** se reescribe y que se le añade una nota de corrección. ¿Está la nota? ¿Es
    suficientemente visible o queda una cita falsa leyéndose como verdadera?

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
| **Contenido (corpus y banco heredado)** | | | |
| **El P1 del banco heredado (§1.1b/c)** | | | |
| GUI | | | |
| **Convención del desplegable (i)/(...)** | | | |
| **Rampa de color y contraste** | | | |
| Responsive | | | |
| Listening | | | |
| Speaking | | | |
| **TTS/voz (voz pedida, A/B, STOP)** | | | |
| STT | | | |
| Offline | | | |
| Instalación | | | |
| Identidad y sesión | | | |
| **Frontera de red (preferencia persistida)** | | | |
| Superficie sin sesión | | | |
| Cadena de suministro | | | |
| Seguridad | | | |
| CI | | | |
| **Ancla, invariantes y lista cerrada** | | | |
| Documentación | | | |

**Criterio de veredicto:** `APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`
para el **tag `v3.75.7`**, con la lista de lo que debe cerrarse. Recordatorio: la
puerta declarada de V4.0 sigue siendo `validation_gate.py status --strict` saliendo
**0**, y **no** depende de esta release.

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
7. **No confundir el instrumento con la validación.** Que exista un gate, un
   candado, un kit o un informe **no** es evidencia de que el hecho esté verificado.
8. **No confundir «firmado» con «autenticado».** Una cookie firmada por el servidor
   prueba **quién emitió** la identidad, no **quién tiene derecho** a ella.
9. **No confundir una release de UI con una de pedagogía.** Esta tanda **no** añade
   ninguna capacidad de aprendizaje ni toca el currículum de checks: cambia cómo se
   **ve** y cómo se **oye** lo que ya existía. Un hallazgo que le atribuya una mejora
   pedagógica está leyendo mal el diff.
10. **Regla nueva (V3.75.7): un verde con el barrido vacío no prueba nada.** El test
    central de esta release (el P1 del banco) hoy barre un conjunto **vacío**, porque
    ya no queda ningún ítem de producción. Su valor es el **control positivo**, no su
    verde. Exige el control positivo o marca el test como **decorativo**.
11. **Regla nueva (V3.75.7): distingue «cambia la etiqueta» de «cambia el
    contenido».** `l18`/`l19` cambian de `skill`; su `script`, sus opciones y su
    audio **no** se mueven. Un hallazgo que afirme que el contenido cambió está
    leyendo la etiqueta como contenido.

---

## 7. Honestidad esperada del informe

El auditor debe pronunciarse **explícitamente** sobre estas declaraciones del propio
proyecto, que acotan lo que puede leerse como demostrado:

- **Esta release cambia el producto, y lo dice.** Toca backend de listening,
  frontend y launcher. **No** toca el currículum de checks, las evaluaciones ni
  `LISTENING_BANK_VERSION`.
- **El P0 de identidad sigue entero** y esta tanda **no** lo toca. `POST
  /api/session` acepta cualquier `user_id` **existente** sin credencial y
  `GET/POST /api/users` siguen abiertos. Cerrarlo exige credencial y contradice «sin
  cuentas, sin contraseñas» de `docs/PREMISAS.md`: es decisión de producto, no
  pendiente técnico.
- **`V3.75.3` empeoró la superficie de exposición** al persistir la preferencia LAN:
  un equipo con `{"lan": true}` arranca expuesto sin declararlo en esa sesión. Está
  declarado con su mitigación y **no** se presenta como neutro.
- **El provenance del banco tiene un hueco declarado:** `LISTENING_BANK_VERSION`
  sigue en `7.0.0` para dos contenidos servidos distintos, a propósito, porque la
  constante **también** nombra la caché de audio. Se declara como **candidato a
  hallazgo**, no se esconde.
- **Hoy no queda ningún ítem de dictado autorado.** Hay endpoint, flujo, UI y tests,
  pero el esquema del corpus exige `options` + `answer_index` y no puede representar
  un dictado: es deuda de **contenido**, no de código.
- **El acento es simulado.** Piper sintetiza; una voz «británica» no es un hablante
  británico.
- **La primera reproducción en voz B cuesta segundos** (síntesis + ASR para alinear)
  y **la caché crece** (~100 KB por ítem × voz × variante) sin recolectarse sola.
- **El barrido visual completo no se ha hecho.** Se midió listening (B1, STOP, tres
  lecturas, rejilla), los desplegables y las tres geometrías de la rejilla de rutas.
  **No** se midió la geometría real de los desplegables de las seis pantallas de
  nivel (son `inline` por construcción, cubiertos por unitario), ni se barrió la
  rampa en toda la app, ni Ajustes. La validación física **no** se declara hecha.
- **Cambiar el defecto de la lectura es un cambio visible:** hasta `V3.75.6` la única
  lectura era la larga; quien no toque nada oirá menos piezas.
- **El corpus en marcha no se recarga solo** ni la UI compilada en `dist`: hay que
  reiniciar y recompilar para ver el efecto del reetiquetado de B1.
- **La suite visual no aguanta el paralelismo del arnés en Windows:** con los 3
  workers por defecto fallan specs ajenos que pasan en aislamiento. La cifra
  declarada es la de `--workers=1`.
- **Los 7 gates están en `pending`.** Nadie ha hecho el corte de red real (`RA-05`),
  ni una instalación en máquina limpia (`RB-05`), ni pruebas en móvil real, ni
  pruebas con audio real. El código marca los **7** gates como `human: bool = True`.
- **El kit es una planilla, no una validación.** `KIT-VALIDACION-GATES.md` ordena y
  registra la ejecución humana; **no** mueve ningún gate a `pass`. Y la identidad
  sellada en el kit sigue siendo la del pre-vuelo (`3.73.6` → `13cc30b`).
- **`product-origin-windows` es informativo**, no bloqueante, y así se declara.
- **Siete commits post-datan el tag `v3.75.2`** (§1.2). Se declaran; si eso invalida
  la lectura de `v3.75.2` como «release documental cerrada», es un hallazgo de
  proceso y debe decirlo.
- **La accesibilidad y la matriz de dispositivos no tienen evidencia ejecutada:**
  `docs/DEVICE_MATRIX.md` está **en ⬜** y no hay motor de accesibilidad (`axe`). Lo
  que hay son contratos de UI en Playwright: acotado, no es una auditoría.
- **`ruff` limpio se declara por directorio, y hay una excepción declarada.** Las
  invocaciones de §3 corren dentro de `backend/` y `launcher/` —los dos árboles que
  la release toca— y ambas salen limpias. Un `ruff check .` desde la **raíz** del
  repo **no** lo está: reporta **1 hallazgo** (`DTZ005`, `datetime.now()` sin `tz`)
  en **`scripts/purge_virtual_testers.py:198`**, un script de mantenimiento que esta
  release **no toca** y que ya venía así en `v3.75.2` (el `git diff v3.75.2..v3.75.7
  -- scripts` solo contiene `validation_gate.py`). Se declara en vez de arreglarlo
  fuera de alcance; si el auditor lo considera bloqueante, es hallazgo de higiene y
  no de esta release.
- **Sigue abierto y aceptado:** `RA-02` (endpoint de Ollama sin declarar en
  `config.py`), `RA-07`, `RD-05`, `layout.rightWidth` sin consumidor y los cinco
  hallazgos de la pausa pedagógica (`AH`–`AM`, política en
  `AO-POLITICA-PSICOMETRICA-V40.md`).

---

## 8. Cierre

**Estado del punto de entrada: entregado (2026-09-20), dentro del commit de release
de `v3.75.7`.** Verificado por comando contra GitHub, no contra el árbol local:

- **Release auditada:** el tag anotado **`v3.75.7`**; el commit y el objeto del tag
  se resuelven con `git rev-parse` (§1), **no** se fijan a mano.
- **Base de comparación:** **`v3.75.2`**, con el aviso de que **siete commits** la
  post-datan (§1.2).
- **Los invariantes que sí se pueden declarar** son los tres acotados de §1.1
  (currículum y evaluaciones **vacíos**, corpus en **3 líneas**, banco heredado en
  **2 etiquetas**). El invariante clásico de «producto sin cambios» **no se declara
  porque sería falso** en esta release.
- **CI:** se resuelve por comando sobre el commit del tag (`gh run list`).
- **Consistencia de versión:** `3.75.7` en los **6 orígenes**.
- **Historial:** cinco iteraciones (`V3.75.3`–`V3.75.7`) y **una sola etiqueta**; se
  declara que las cuatro primeras no tienen tag propio.
- **Lo que queda después de esto:** sellar el baseline y ejecutar **G1–G7**; los 7
  gates siguen en `pending` y **nada** de esta línea los adelanta.
