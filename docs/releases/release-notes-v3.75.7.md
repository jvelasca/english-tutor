# Release notes — English Tutor v3.75.7

**Fecha:** 2026-09-20 · **Tipo:** release **DE PRODUCTO** (minor) ·
**Versión de app:** `3.75.2 → 3.75.7`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el currículum (`CURRICULUM_VERSION` sigue
`1.3.1`), SIN tocar las evaluaciones (`assessments.json`) y SIN tocar
`LISTENING_BANK_VERSION`.** No añade ni retira un gate y no adelanta la
validación física (**G1–G7 siguen `pending`**).

> **Esta release publica CINCO ITERACIONES juntas** —`V3.75.3`, `V3.75.4`,
> `V3.75.5`, `V3.75.6` y `V3.75.7`— **bajo una sola etiqueta.** Es la única que
> lleva tag. Se registran una a una en `CHANGELOG.md` y `PLAN.md` para que cada
> etiqueta que citan el código y `docs/audit/PARKED.md` siga siendo localizable;
> `V3.75.3`–`V3.75.6` **no tienen tag propio**. El motivo y el precio están en
> §2.

---

## 1. Qué es esta release

Es la tanda con la que el gerente cierra **la parte de listening** y una
**pregunta de coherencia visual en toda la app**. Cinco iteraciones nacidas del
**uso real** de la aplicación, en este orden:

1. **V3.75.3** — el launcher recuerda sus preferencias, listening pierde un paso
   y el Análisis se va a la cabecera.
2. **V3.75.4** — listening pulido y la rampa de color por nivel, elegible por
   perfil.
3. **V3.75.5** — la voz se configura desde la práctica y la repetición se oye
   con **dos acentos**.
4. **V3.75.6** — STOP en la repetición, la lectura que el perfil elige y la
   **RUTA B1** que no se parecía a las demás.
5. **V3.75.7** — el icono del desplegable dice qué hay dentro, el texto deja de
   quedar debajo del botón, y **cierre del P1 que destapó la auditoría externa**.

Ninguna de las cinco añade una capacidad pedagógica nueva ni una ruta de
producto nueva: el motor pedagógico, el banco de checks del currículum y las
evaluaciones quedan **intactos**.

---

## 2. Por qué cinco iteraciones y una etiqueta

Las cinco iteraciones se documentaron **una a una** en `docs/audit/PARKED.md`, con
su decisión y su precio, y los comentarios de código las citan por su nombre
(`V3.75.5`, `V3.75.6`, `V3.75.7`). Eso deja tres opciones y las tres tienen
coste:

| Opción | Coste |
| --- | --- |
| **Un tag por iteración** | Reconstruir cinco releases sobre trabajo ya hecho: cinco ciclos de verificación, cinco commits y cinco pushes para contenido que ya está escrito y probado. |
| **Una sola entrada** en `CHANGELOG`/`PLAN` | Cuatro etiquetas citadas en el código y en `PARKED.md` **sin nada que las resuelva**: quien busque «V3.75.5» no encuentra nada. |
| **Cinco entradas y un tag** (elegida) | `V3.75.3`–`V3.75.6` aparecen en el historial **sin tag propio**. Hay que declararlo. |

Se elige la tercera, **decidida con el gerente**. La consecuencia se declara en
la primera línea de la entrada `[3.75.7]` del `CHANGELOG` y en el encabezado de
esta nota, para que un auditor no lea un número de versión sin tag como un
hueco: **es una decisión, y está escrita**.

---

## 3. Iteración 1 — `V3.75.3`: preferencias del launcher, listening sin fricción y Análisis global

### 3.1 La preferencia de red se persiste, y eso reabre algo

`launcher/config.json` (nuevo `launcher/config_store.py`) guarda el modo LAN, se
lee **al arrancar** antes de pintar la interfaz y se guarda **en cada cambio**.
Responde a la pregunta abierta nº 1 de `docs/audit/PLAN-P0-IDENTIDAD.md` y
**revierte §5.8** del mismo documento: el modo LAN pasa de decisión de **sesión**
a decisión de **instalación**.

**Lo que esto reabre, sin adornos:** un equipo con `{"lan": true}` arranca con
uvicorn en `0.0.0.0` y aceptando orígenes de red privada **sin que nadie lo
declare en esa sesión**, y el P0 de identidad sigue abierto. Antes de esta
versión ese estado se perdía al cerrar el launcher.

**Mitigación (no lo elimina):**

- el modo es **visible desde el primer pintado** (fila LAN con el enlace y botón
  «Desactivar red local»);
- el fichero es local y está en `.gitignore`;
- el **default es cerrado**;
- un valor editado a mano que no sea el booleano `True` (`1`, `"sí"`) se lee como
  **cerrado**.

Candados: `launcher/tests/test_config_store.py` y cuatro pruebas nuevas en
`launcher/tests/test_lan_mode.py` (aplicar al arrancar, sin preferencia, valor no
booleano, y preferencia **por encima** del entorno heredado).

### 3.2 Listening sin el paso «He escuchado — responder»

La tarjeta `while1` desaparece y la señal de «he escuchado» es **pulsar PLAY**:
`play()` avanza la etapa al **empezar** el audio, y en el `catch` **no** avanza,
para que un fallo de audio deje el ejercicio donde estaba. **Efecto deliberado:**
sin pulsar PLAY no se ven las opciones. Se retiran tres claves i18n huérfanas;
`microFlow.ts` no se toca.

### 3.3 El Análisis se va a la cabecera

`features/analysis/AnalysisScreen.tsx` vive en `/analisis` (`ANALYSIS_PATH`) y se
abre con un botón en el bloque `ml-auto` del `Header`. Es **destino auxiliar**: no
lleva píldora en `Navigation`, así que no toca `ROUTES` ni rompe el test de las 5
píldoras. Sintetiza posición, actividad real con su agrupación temporal, tríada,
destrezas y escalera CEFR **reutilizando endpoints que ya existían**, sin crear
ninguno. El panel flotante `components/AnalysisPanel.tsx` se **borra**, junto con
las reglas CSS muertas y el asa derecha del workspace; la calidad del tutor no se
pierde porque la recibe la pantalla nueva desde los turns de la sesión en curso.

**Límite declarado:** `layout.rightWidth` sigue existiendo y persistiéndose **sin
consumidor** (`utils/layout.ts`). Es deuda de forma, no una fuga: el contrato de
layout tiene sus propios tests y no se poda aquí para no arrastrar cambios al
`useChat`.

---

## 4. Iteración 2 — `V3.75.4`: listening pulido y rampa de niveles configurable

### 4.1 El «Saltar» no se elimina, se reubica

Era la **única salida** de una pregunta sin registrar evidencia (audio que no
suena, ítem incomprensible): llamaba a `load()` y **pedía otro ítem sin
responder**. Sale del pie, donde competía con las opciones, y pasa a la cabecera
nueva como botón fantasma pequeño (`listening.anotherItem`). No se confunde con el
otro «Saltar» de la tarjeta de shadowing (`listening.flow.skipStage`), que declina
el paso **opcional** que el backend marca con `allow_skip`.

### 4.2 El color de nivel pasa de 3 tramos a 7 pasos, con un solo mecanismo

Antes `cefrTone` devolvía `basic|intermediate|advanced`: A1 y A2 (o B1 y B2) eran
del **mismo** color y el color no decía nada. Ahora:

- `cefrLevelKey`/`levelClass` (Pre-A1 → C2 + «sin dato») son la **única puerta**;
- las clases **estáticas** `.lv-*` de `styles/legacy.css` son la **única pintura**:
  sin clases Tailwind interpoladas (el escaneo las purgaría) y sin `inline style`;
- se declaran **fuera de capa** a propósito, para que una utilidad de Tailwind de
  la misma línea no borre el color del nivel.

**Fallo previo que se arregla de paso:** `LearningProfile.tsx` llamaba
`cefrTone(profile.estimated_bands[skill])` con un **número** (escala 0–6), así que
caía **siempre** en `basic` y las filas del perfil se pintaban iguales.
`bandToLevelKey(numeric)` recupera el tramo, declarado como **aproximación de
color**, no como medida de dominio.

### 4.3 La rampa es elegible por usuario, sin backend nuevo

Ajustes > Apariencia ofrece tres esquemas —**Semáforo** (por defecto, reproduce
los colores que ya había), **Espectro** y **Monocromo** (7 intensidades del
acento, cero hexes propios)— con vista previa en el propio diálogo. Se aplica con
`data-levels` en `<html>`, se persiste por perfil con la clave `level_scheme` en
el `PUT /api/settings` que ya existía y `localStorage` como copia para que un
backend caído no pierda la preferencia. El relleno y el borde se **derivan** de la
tinta con `color-mix()`, así que un esquema nuevo son **7 hexes y no 21**.

### 4.4 El gate del color es la medición, no el gusto

`contrast_audit.mjs` mide cada paso sobre su **relleno compuesto** (sobre
`--color-surface` y sobre `--color-bg`) en los **3 esquemas × 2 temas** —y en
Monocromo, por los **7 acentos**—, con guardas de que la rampa esté completa.

```
472 pares + 4 guardas, 0 bloqueantes con fallo (--strict)
```

Los hexes se ajustaron hasta AA. El precio es que la paleta es **tributaria del
contraste**, no al revés.

### 4.5 El selector de rutas se agrupa de dos en dos

Las seis rutas (A1·A2 / B1·B2 / C1·C2) pasan a **dos columnas** en todos los
anchos —celda horizontal, anillo a la izquierda y datos a la derecha— y **«Auto»**
sale de la rejilla a una **fila propia a ancho completo**, después de C2: es la
opción que **no** elige ruta y no debía competir con las seis que sí la eligen.

**Medido, no estimado** (playwright, 3 viewports): 3 filas de 2 y sin
desbordamiento horizontal (`scrollWidth == clientWidth` en 390/768/1280); celda de
**158 px** de ancho y entre **66 y 107 px** de alto en móvil.

---

## 5. Iteración 3 — `V3.75.5`: voz configurable y dos acentos

### 5.1 El «…» deja de ser un cartel y pasa a configurar

Antes solo leía «Voz sintética local (TTS) · \<voz\> · \<wpm\>» y no había **ningún**
camino a la configuración desde la práctica. Ahora abre el bloque `VoicePicker`:

- fila **Voz A** (la del perfil, `tts_voice`);
- fila **Voz B** (segundo acento, `tts_voice_alt`);
- dos chips **«Probar A» / «Probar B»** que reproducen *ese* ítem para comparar
  antes de decidir.

El mismo bloque, tal cual, cuelga del «…» de las rutas de quiz: **una sola idea de
acento en toda la app**.

### 5.2 Se puede pedir voz, y solo una instalada

`TTSRequest.voice` y el query param `voice` de `/api/listening/audio/{id}` viajan
hasta `tts.pick_requested_voice`, que **solo** acepta una voz instalada y del
idioma pedido; si no pasa el filtro **se ignora en silencio** y manda
`resolve_voice(prefs)`.

No es laxitud. Es que la UI no puede romperse por una preferencia vieja (ni
recibir un 400 por ella) y, sobre todo, **el id de voz entra en rutas de disco**
(`PIPER_DIR / "<voz>.onnx"` y `data/listening/{banco}/{voz}/…`), así que aceptarlo
sin validar sería *path traversal* por construcción.

`X-TTS-Voice` / `X-TTS-Degraded` siguen declarando lo que **realmente** sonó, no lo
que se pidió: la UI puede ser honesta cuando degrada.

### 5.3 La B se sugiere sola, y nunca cruza idiomas

`utils/voices.ts::suggestAltVoice` propone la primera voz del **mismo idioma y
otra locale** (US → GB y al revés), de modo que «dos acentos» funciona recién
instalada la app sin obligar a configurar nada. El selector solo ofrece voces del
idioma de la voz A, porque mezclar idiomas haría que la B leyera el ítem en otro
idioma.

### 5.4 Un store de módulo, no un contexto

`hooks/useVoiceChoice.ts` (patrón de `useVoiceDownload`, `useSyncExternalStore`)
hace **una sola** lectura de `GET /api/voices` + `GET /api/settings` para toda la
app aunque haya varios altavoces en pantalla, y **vacía el estado al cambiar de
perfil** (la voz de un alumno no puede quedarse a la vista de otro). Configuración
→ Voces escribe `tts_voice` por su cuenta, así que el panel **relee** el store al
elegir voz y al instalar una nueva (`refreshVoiceChoice`): sin eso la voz A de la
práctica quedaba desincronizada.

### 5.5 Dónde se usa qué

- El altavoz de **después de responder** lee el ítem entero en voz A o B, y con
  una sola voz instalada **solo** aparece A: nunca un botón que no puede sonar.
- **PLAY sigue sonando en voz A.** La escucha de estudio es una sola y el segundo
  acento vive donde el alumno lo pide, que es después de responder.
- `ListenButton` **no cambia** cuando no se le pide acento (40 y pico usos previos
  y sus tests intactos); donde el altavoz lee un **ítem** se usa
  `ItemReplayButton`, y donde lee texto arbitrario del alumno (traductor), el de
  siempre.
- Se sustituye el altavoz mudo por el consciente de la voz en los paneles de nivel
  de listening/vocabulario/gramática/conversación/pronunciación/speaking, en los
  escenarios de pronunciation y speaking, en el drill de vocabulario, en el
  diccionario (palabra y ejemplo) y en la evaluación de speaking.

---

## 6. Iteración 4 — `V3.75.6`: STOP, lectura corta y la RUTA B1

### 6.1 La RUTA B1 no era un caso especial: era una etiqueta mal puesta

`c071` y `c084` —los **dos únicos** ítems del corpus (490) etiquetados
`dictation`/`shadowing`— estaban **autorados como pregunta de opción múltiple**
(`question` + 4 `options` + `answer_index`). El flujo se elige por `skill`, así
que la app pedía **escribir a mano** una frase cuyo contenido autorado era «Which
time did you hear?» con opciones: la tarjeta no se parecía a las otras cinco rutas
y el contenido autorado se tiraba.

Corregido **en el contenido** (`curriculum/listening_corpus.json` `3.0.0 →
3.0.1`): `c071` → `numbers`, `c084` → `phrase_recognition`. B1 vuelve a recibir lo
mismo que las demás y **recupera dos ítems servibles**.

### 6.2 STOP en la repetición, y una sola locución a la vez

`api/voz.ts` gana un registro de módulo con la locución en curso:

- `stopSpeaking()` pausa el audio **y** cancela la síntesis si aún no había sonado;
- la promesa de `speak()` **resuelve** —parar no es un error—, así el botón apaga
  su spinner sin tratar el corte como fallo;
- **empezar otra locución corta la anterior** (antes se solapaban).

El STOP solo existe mientras suena y vive junto a los botones A/B.

### 6.3 `replay_scope`: tres composiciones, no dos

Un ítem tiene cuatro piezas: **texto** (el `script`, lo que suena), **pregunta**,
**opciones** y **respuesta correcta**. De ahí salen:

| Valor | Composición |
| --- | --- |
| `"item"` (**defecto**) | texto + pregunta + respuesta |
| `"withOptions"` | texto + pregunta + opciones + respuesta |
| `"correct"` | pregunta + respuesta |

Es una clave más del mismo `PUT /api/settings`, así que **no hay backend nuevo**.
El valor histórico `"all"` se normaliza a `"withOptions"` (quien lo había elegido
de forma explícita no pierde su elección); ausente o desconocido cae a `"item"`.

**Una sola función decide el texto** (`utils/voices.ts::buildReplayText`), con
salvaguardas: descarta piezas ausentes en vez de inventarlas, **no repite** el ítem
cuando el script *es* la pregunta (habitual en A1) y, si el alcance elegido dejara
la lectura vacía, cae a la composición completa —**nunca una repetición muda**—.

**No puede filtrar la respuesta antes de tiempo:** `correct_index` solo lo aportan
los sitios que ya han respondido, y hasta entonces el altavoz de repetición **ni
existe**.

Bajo los botones se describe **la composición activa** («Se lee: …») en vez de un
párrafo que explique las tres: las etiquetas se parecen («el ítem completo» / «el
ítem más las opciones») y la diferencia está en las **piezas**, no en las palabras.

### 6.4 El test deja de declarar y pasa a medir en pantalla

`frontend/tests/visual/listeningReplayStop.spec.ts` (mock-based, 3 breakpoints)
navega a la RUTA B1 y comprueba que las opciones están y la tarjeta de producción
no, que el «…» ofrece las tres lecturas con la primera activa, y que tras
responder aparecen A/B y el STOP. Además **lee el cuerpo real del `POST /api/tts`**
y exige que el texto compuesto sea texto + pregunta + opciones + clave: la
composición del gerente verificada de punta a punta, no solo en unitarios.

Medido: STOP **32×32** dentro del viewport y **sin desbordamiento horizontal**
(390/390 · 768/768 · 1280/1280).

Que el **banco** sirva una pregunta receptiva en B1 lo fija
`backend/tests/test_listening_corpus.py`: la suite visual mide la UI, no el
contenido.

---

## 7. Iteración 5 — `V3.75.7`: el icono del desplegable y el P1 del banco heredado

### 7.1 El icono del desplegable es un contrato

`InfoDisclosure` gana `content: "info" | "options"` con **defecto `"info"`**: un
panel nuevo que no declare nada **no puede** prometer opciones que no tiene.

- **(i)** cuando el panel **solo explica** (una nota, un aviso de honestidad);
- **(...)** cuando además trae **opciones**.

La etiqueta accesible acompaña al icono (`common.moreInfo` / `common.moreOptions`
= «Opciones e información»). **Inventario de la revisión: 11 disparadores, ninguno
sin clasificar.**

| Icono | Cuántos | Cuáles |
| --- | --- | --- |
| **(i)** | 8 | Notas de ruta de listening y notas de los paneles de nivel de las seis destrezas (speaking tiene dos). |
| **(...)** | 1 | Notas de ruta de las rutas de quiz: de verdad cuelgan del `VoicePicker`. |
| **Sin cambio** | 3 | El «...» de la tarjeta de audio (ya era «...»: velocidad + voces + repetición), el desplegable de texto «Cómo funcionan las rutas» (ya era (i) con etiqueta visible) y el botón de los propios paneles. |

### 7.2 El texto ya no queda debajo del botón

En la variante de esquina el disparador flota sobre la `Card` y el panel nace justo
debajo (era su primer hijo), así que su primera línea salía **tapada** por el botón
que acababa de abrirla. Medido antes del arreglo, el párrafo
`"A real CEFR B1 means hundreds of known w…"` quedaba dentro del rectángulo del
botón.

El panel reserva ahora la **columna** del disparador (`py-2 pl-3 pr-12` = 36 px del
botón + 12 px de aire) y **no altura**: reservar altura habría dejado un hueco
muerto en los paneles que no llegan al borde superior. La composición se hace
explícita frente a `px-3 py-2` para **no depender del orden** en que Tailwind emita
`px-*` y `pr-*`.

**La guarda tiene dientes, verificado:** revirtiendo `pr-12` a `px-3` el test
vuelve a fallar con
`coveredNotes: ["p|A real CEFR B1 means hundreds of known w"]`. Sin esa
comprobación, un test verde no probaría nada.

### 7.3 El P1 que destapó la auditoría externa

**El hallazgo.** La verificación de esta release se hizo en dos auditorías
independientes en paralelo (frontend y backend/launcher). La de backend encontró un
**P1 que contradecía el objetivo visible de la tanda**: la RUTA B1 seguía
mostrando la tarjeta de dictado.

**La causa raíz, con su alcance medido.**

```
total 513 corpus 490
corpus prod con opciones []                      # el corpus estaba limpio desde V3.75.6
B1 total 33
B1 prod [('l18', 'dictation', 4), ('l19', 'shadowing', 4)]     # el banco heredado, NO
banco heredado prod [('l18', 'dictation', 4), ('l19', 'shadowing', 4)]
```

V3.75.6 corrigió `c071`/`c084` **en el corpus**, y su test —
`test_production_items_do_not_carry_multiple_choice_options`— **filtraba ids `c`**:
miraba solo el corpus. Los ítems `l18` (`dictation`) y `l19` (`shadowing`) del
**banco heredado** seguían con opciones, así que el flujo de producción los
seguía sirviendo y B1 seguía mostrando «Enviar dictado».

**Se cierra en la causa raíz, no en el síntoma:**

1. **Una sola fuente de verdad.** `PRODUCTION_SKILLS` se declara **una vez** en
   `backend/services/listening_flow.py` y la consume `build_item_flow`. Estaba
   duplicado en tres sitios, y esa duplicación fue parte de por qué el defecto
   sobrevivió.
2. **El barrido es sobre todo el banco.** `_production_items_with_options` recorre
   **todo** `QUESTION_BANK`, no solo los ids `c`.
3. **Los dos ítems se reetiquetan:** `l18` → `numbers`, `l19` →
   `phrase_recognition`. Cambia la etiqueta, **no el contenido**: su `script`, sus
   opciones y su audio son los mismos; lo que cambia es por qué flujo se sirven y,
   por tanto, cómo se ven en B1.

**Y se arregla el test que no mordía, en los dos sentidos.** Hoy **no queda ningún
ítem de producción** en el banco, así que el barrido del test es **vacío** y podría
pasar **por estar roto**: se le añade un control positivo,
`test_production_guard_bites_on_a_synthetic_offender`, que inyecta un ítem
etiquetado de dictado **con opciones** y exige que la comprobación lo reconozca.

**La suite deja de apoyarse en ítems concretos del banco.** Nuevo fixture
`production_items` en `tests/conftest.py`: construye ítems de producción
**sintéticos** (copia de un ítem real con el `skill` cambiado) y los inyecta
durante el test. Migran a él `test_listening_production.py`,
`test_word_breakdown_v329.py`, `test_listening_shadowing2_v328.py` y
`test_listening_attempts_v327.py`, que hasta ahora se rompían **cada vez** que el
banco cambiaba. Y `test_bank_covers_every_subskill` → **`test_bank_covers_every_receptive_subskill`**:
el banco **no puede** contener producción (el esquema `ListeningAsset` exige
`question` + `options` + `answer_index` en **todos** sus ítems), así que la
ausencia se exige **exacta** —todas las receptivas cubiertas, y exactamente las de
`PRODUCTION_SKILLS` fuera— en lugar de una igualdad que ya no puede cumplirse.

### 7.4 Dos P3 y un launcher que se puede probar

1. **`X-TTS-Voice` en la respuesta de audio.** `domain/listening.py::get_audio`
   devuelve la voz **realmente usada** y `routers/listening.py` la publica en la
   cabecera. Antes, el frontend podía creer que había oído **dos acentos** cuando,
   por falta de voz instalada, había sonado la misma dos veces.
2. **`config.json` se escribe de forma atómica.** `launcher/config_store.py::save_config`
   escribe a un temporal y hace `os.replace`: un corte a mitad ya no puede dejar el
   fichero de preferencias a medias.
3. **La lógica de LAN se centraliza** en `launcher/core.py`
   (`apply_stored_lan_config`, `toggle_lan_config`) para que la decisión que cambia
   la **frontera de red** tenga test fuera de `tkinter`, que no se puede probar sin
   pantalla.

---

## 8. Verificación

Medida en el árbol de trabajo, con `dist` construido y modelos presentes.

| Suite | Resultado |
| --- | --- |
| Backend `pytest tests/ -q` | **2909 passed**, 0 skipped |
| Frontend `vitest run` | **806 passed** (93 ficheros) |
| Frontend `tsc --noEmit` | limpio |
| Frontend `npm run build` | correcto (`dist` recompilado) |
| i18n `check_i18n_coverage.py --strict` | **1512 claves, 0 huérfanas** |
| Contraste `npm run audit:contrast` (`--strict`) | **472 pares + 4 guardas, 0 bloqueantes** |
| Backend `ruff check .` (en `backend/`) | limpio |
| Launcher `pytest tests/ -q` | **178 casos** |
| `scripts/check_release_consistency.py` | **OK (3.75.7) en los 6 orígenes** |
| `scripts/validation_gate.py auto` | **10/10** |
| `playwright test --workers=1` | **44 passed / 28 skipped / 0 failed** |

**Nota de alcance del `ruff`.** Las invocaciones limpias son **por directorio**
(`backend/` y `launcher/`), que son los árboles que esta release toca. Un
`ruff check .` desde la **raíz** del repo reporta **1 hallazgo preexistente**
(`DTZ005` en `scripts/purge_virtual_testers.py:198`, un script de mantenimiento que
esta release no toca y que ya estaba así en `v3.75.2`). Se declara, no se silencia.

**Los 6 orígenes de versión** son `backend/config.py` (fuente de verdad),
`frontend/package.json`, `frontend/package-lock.json`, `README.md`, `CHANGELOG.md`
y `PLAN.md`.

**La mordida de las guardas nuevas se comprobó por sabotaje controlado:**

- revertir `pr-12` a `px-3` → el spec visual vuelve a fallar con el párrafo tapado;
- inyectar un ítem de producción con opciones → el control positivo del test del
  banco lo reconoce (si no, el test no probaría nada, porque su barrido es vacío);
- reetiquetar un ítem del banco como producción **sin** quitarle las opciones → el
  barrido sobre todo `QUESTION_BANK` lo detecta.

`playwright test` con los **3 workers por defecto** encadena fallos que **no** son
del producto (14 specs ajenos con `page.goto` agotando los 30 s, todos verdes en
aislamiento). Con `--workers=1` no falla ninguno; por eso la medición declarada es
la de un worker. Es fragilidad del **arnés en Windows**, no del producto, y queda
registrada.

---

## 9. Honestidad: lo que esta release **no** cierra

1. **El provenance del banco no distingue el antes del después.**
   `LISTENING_BANK_VERSION` sigue en **`7.0.0`** a propósito, porque además de
   identificar el banco **nombra la caché de audio** (`data/listening/{versión}/{voz}/`)
   y ningún `script` ni `audio_id` cambió: subirlo habría re-sintetizado el banco
   entero por cero audio distinto. El hueco —un mismo `bank_version` para dos
   contenidos servidos distintos— queda **declarado** y es candidato a hallazgo del
   auditor, no una omisión. La política del proyecto sí bumpea provenance cuando el
   coste es cero (así se hizo con `CURRICULUM_VERSION` en V3.75.1); aquí el coste no
   lo es.
2. **Hoy no queda ningún ítem de dictado autorado.** Hay endpoint, flujo, UI y
   tests, pero el esquema del corpus exige `options` + `answer_index` y no puede
   representar un dictado. Es deuda de **contenido**, no de código: quien quiera
   dictado real tendrá que autorarlo con un esquema que lo represente. El
   **shadowing** no desaparece de la práctica: sigue siendo el paso opcional del
   micro-flujo receptivo.
3. **El P0 de identidad sigue entero.** V3.75.3 le añadió incluso una vía más para
   arrancar expuesto (la preferencia LAN persistida). En modo LAN,
   `GET/POST /api/users` siguen **sin credencial** y el `user_id` lo sigue eligiendo
   el cliente. `POST /api/session` acepta cualquier `user_id` **existente** sin
   credencial. Nada de esta tanda toca ese eje, y **no cambia de prioridad** por
   ella.
4. **El acento es simulado.** Piper sintetiza; una voz «británica» no es un hablante
   británico. Dos voces hacen la diferencia audible y la etiqueta honesta sigue
   junto al selector, pero la promesa no crece.
5. **La primera reproducción en voz B cuesta unos segundos** (síntesis + ASR para
   alinear) y **la caché crece** (~100 KB por ítem × voz × variante). No se
   recolecta sola, aunque borrarla no rompe nada.
6. **El barrido visual completo no se ha hecho.** De estas cinco iteraciones se
   ejecutó la parte de listening (specs de la RUTA B1, STOP y las tres lecturas, y
   la medición geométrica de la rejilla), la de los desplegables y las tres
   geometrías de la rejilla de rutas. **No** se navegó a las seis pantallas de nivel
   para medir la geometría real de sus desplegables, ni se barrió la rampa de color
   en toda la app, ni Ajustes. Los desplegables de los paneles de nivel son
   `inline` —botón y panel apilados en columna— así que el solapamiento es
   imposible **por construcción** y están cubiertos por unitario; **si alguna se
   pasara a `corner`, la guarda visual no la cubre**. La validación física no se
   declara hecha.
7. **Cambiar el defecto de la lectura es un cambio visible:** hasta V3.75.6 la única
   lectura era la larga; quien no toque nada oirá menos piezas.
8. **El corpus en marcha no se recarga solo** (el backend lee el banco al importar)
   ni la UI compilada en `dist`: hay que reiniciar y recompilar para ver el efecto
   del reetiquetado de B1.
9. **`cefrTone` sobrevive en documentos históricos** (briefs y actas de `agentes/`,
   `RELEVO.md`, `CHANGELOG.md`): son documentos fechados de lo que se decidió
   entonces y **no se reescriben**. El código ya no tiene ninguna referencia.
10. **`docs/LISTENING_ENGINE_4.0.md` (2026-09-09)** citaba `c071`/`c084` como
    evidencia de dictado y shadowing. Es una especificación fechada y no se
    reescribe, pero se le añade la **nota de corrección** para no dejar una cita
    falsa en un documento que se sigue leyendo.
11. **`layout.rightWidth` sigue existiendo y persistiéndose sin consumidor:**
    deuda de forma declarada, no una fuga.
12. **Los 7 gates siguen en `pending`** y la identidad sellada en el kit sigue
    siendo la del pre-vuelo (`3.73.6` → `13cc30b`), que es historia y no se
    reescribe. `status --strict` sigue saliendo **1**, que es lo correcto: el
    siguiente hito sigue siendo ejecutar físicamente G1–G7.

---

## 10. Cómo auditar esta release

1. **El ancla es el tag `v3.75.7`**, no `main`. Los comandos que resuelven el commit
   y el objeto del tag están en el punto de entrada
   (`agentes/auditoria-total-externa-v3757.md`), en lugar de fijarse a mano: un
   commit no contiene su propio SHA y un documento que lo fije nace desfasado (la
   lección de V3.73.5).
2. **El invariante honesto de esta release no es «producto sin cambios»** —esta vez
   el producto **sí** cambia— sino una **lista cerrada** de lo que cambia frente a
   `v3.75.2`, y el punto de entrada la enumera para que el auditor pueda comprobar
   que **nada fuera de la lista** cambió.
3. **Los recuentos de test declarados aquí se midieron en el árbol de trabajo**, no
   en un clon limpio. Un clon sin `frontend/dist` y sin el modelo Whisper opt-in da
   **saltos**, no fallos: el reparto por entorno está declarado en el punto de
   entrada (la errata de V3.73.6).

Ver `agentes/auditoria-total-externa-v3757.md`.
