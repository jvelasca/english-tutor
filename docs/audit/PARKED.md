# PARKED — fuera del alcance de la fase V3.0 post-freeze

> Lista de temas detectados en las auditorías A–G **y en la auditoría pedagógica
> de V3.70 (dossiers `AA`–`AF`)** que **no se implementan en esta fase** (no son
> features nuevas ni calibración con datos inexistentes). Se documentan aquí para
> que la fase de observación posterior los recoja en orden. Un ítem no aparcado =
> no bloquea el freeze.

## Métricas / producto (no implementar sin decisión)

- **Learning Effectiveness y transfer como KPI** (medir uso real del idioma,
  no solo dentro de la app). Requiere definir objetivo de aprendizaje, cohortes
  y ventana; fuera del motor V2.7–V2.12.
- **Pre-A1 como producto** (decisión de catálogo, `BETA_V3.md` §4.1). Opcional.

## Motor (parámetros / calibración con datos reales)

- **FSRS por tipo de memoria**: `schedule()` es uniforme; auditoría E midió y
  documentó la uniformidad. Cambiar parámetros por tipo requiere datos de uso
  (`REQUEST_RETENTION` con alumnos reales), no se toca el scheduler ahora.
- **Calibración con alumnos reales** (protocolos en dossiers A–E):
  - Umbrales Assessment 2.0 (`PASS_THRESHOLDS`) y gates de mastery.
  - Readiness CEFR (`cefr_matrix`) vs sensación de nivel.
  - Speaking weak threshold / mission drills.
- **Drills de producción por aspecto de Personal Dictionary** (vocabulario
  activo por aspecto: estructura, significado…). Idea anotada, sin diseño.

## Contenido / audio (fase de contenido, no del freeze)

- **Audio humano real**: `manifest.json` del corpus sigue vacío (hoy TTS).
  La calibración escrita está auditada (B); la capa acústica (prosodia, ironía)
  es un proxy documentado hasta grabar clips humanos.
- **Autoría fina de prompts/checks por unidad** (sin inflar objetivos).
- **Ampliar catálogo de escenarios speaking** (variedad A1; más C1/C2) y
  revisión de prompts C1/C2.
- **QA de clips rechazados** del audio humano.

## UX (mejoras anotadas, no urgentes)

> F2, F3, F4 y la depuración de claves i18n huérfanas **se cerraron en V3.72**
> (ver su sección al final); ya no viven en esta lista.


## V3.70 — auditoría pedagógica (1 P0 · 15 P1 · 12 P2 · 5 P3)

> Origen: `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md` (síntesis de los cinco ejes
> `AA`–`AE`). **V3.70 no corrige nada**: estos 33 hallazgos se **aparcan
> asignados a fase** y **dejan de ser opinión**. Los 6 P2 de la auditoría de V3.69
> siguen abiertos aparte (decisión de alcance, no aparecen aquí).

### Contenido y banco (→ V4.0.x)

- **P0 · Posición de la correcta en los checks del currículum** — **CERRADO en
  V3.75.1** (ver §V3.75.1). Medido en V3.70: **329/368 checks (89,4 %)** tenían la
  respuesta correcta en la **posición 0**, así que marcar siempre la primera opción
  acertaba ~9/10. El corpus de listening **no** tenía este defecto (~25 % por
  posición). Reproducir con `python -m scripts.audit_dossier cefr-adequacy`.
- **P1 · Velocidad de habla por nivel**: A1 entero **por encima** de su banda
  (86/200 por encima del techo de 115 wpm) y C1/C2 casi enteros **por debajo**
  (18/20 y 19/20).
- **P1 · `connected_speech: true` sin reducción real**: **C1 14/14** y **C2 20/20**
  no presentan ninguna reducción en la transcripción. Lo declarado no coincide con
  lo realizado.
- **P2 · Escalera de velocidad no monótona**: el máximo de B2 (185 wpm) **supera**
  al de C1 (170).
- **P2 · Ítems `inference` de A2 resolubles por palabra literal** (4 de 5).
- **P2 · Sesgo de forma/longitud de los MC** (compartido con el placement).
- **P1 · Corpus de listening B1–C2 al 13,9–20,0 %** de su objetivo declarado
  (`LISTENING_CORPUS_TARGETS`).
- **P1 · `reading` sin módulo**: declara 15 objetivos y 18 checks pero **no existe
  `backend/services/reading.py`**.
- **P3 · `pre-a1` sin curso** (0/7 celdas) — enlaza con «Pre-A1 como producto».

### Motor y acreditación (→ Planner 4.0)

- **P1 · Tres registros con tres tamaños para el mismo concepto**: 9 modalidades ·
  8 en matriz · 7 canales.
- **P1 · `interaction` y `mediation` no pueden acreditar evidencia por ninguna
  vía** aunque la matriz les exija requisitos en los 6 niveles.
- **P2 · `novel_required = 0` en las 48 celdas** pese a que el emisor real de
  `novel` existe desde V3.26 (la señal existe, la exigencia no).
- **P2 · Las filas sin `objective_id` resoluble no acreditan éxito** (medido
  conductualmente: `result 1,0` → `success False`), lo que deja fuera del gate
  espaciado a speaking assessment y misión (F-K3).
- **P2 · `reading`/`mediation` sin canal de corrección** y `listening`,
  `pronunciation`, `vocabulary` e `interaction` con corrección **solo de
  puntuación, sin mensaje**.
- **P1 · 4 de las 7 reglas de grammar nunca pueden confirmarse**
  (`confidence < CONFIRMED_THRESHOLD = 0.8`) y **solo 2 pueden alcanzar
  `MASTERY_STREAK = 3`** (5 de 7 sin patrón de uso correcto).
- **P2 · El error dentro de las rúbricas solo resta nota** (`1.0 − 0.25·len(errors)`)
  y **no genera la explicación** (siempre la redacta el LLM desde el prompt).

### Instrumentos de nivelación (→ V4.0.x / V3.72)

- **P1 · El criterio de parada del placement es inalcanzable**: pide `SE < 0,5` y la
  mejor cota con los 8 ítems declarados es **`0,7071`** (cota analítica del 1PL
  declarado, no simulación).
- **P1 · El examen de B1 tiene los 12 ítems en dificultad 1** (igual que el de A1):
  no se escala.
- **P1 · Cuatro de seis niveles sin examen final** (A2, B2, C1, C2).
- **P2 · Placement por reconocimiento/meta-lenguaje** para
  listening/speaking/writing/pronunciation (lo declara su docstring). **V3.72**:
  divulgado en el instrumento y en su contrato; la pantalla de nivelación no existe
  (ningún componente consume el placement) → **V4.0.x**, con candado-tripwire.
- **P2 · Sesgo de forma del placement**: correcta = más larga única en el **50 %**,
  más larga o empatada en el **75 %**, **70,8 %** en la posición 1 y la **posición
  3 nunca** correcta.
- **P2 · Umbrales de banda triplicados** y sub-bandas `+` que **ningún estimador
  emite**. **Cerrado en V3.72** (un solo módulo del corte; `+` retiradas de la
  emisión y conservadas como descriptores; `pre-a1` conserva su emisor):
  `docs/audit/AE-PED-INSTRUMENTOS.md` §Cierre.
- **P3 · `pronunciation` fuera de la matriz a propósito** y **escenarios de
  speaking con 1 en A1 y 1 en C1**.

### Propiedades positivas verificadas (no aparcar, no tocar)

- **0 de 490 ítems fuera de su banda de dificultad**; 0 objetivos sin actividades o
  sin checks; 0 checks fuera de las `skills` de su objetivo.
- **Sin evidencia no se afirma nada** (9/9 modalidades en `not_started`, banda `—`)
  y `transfer_required` crece 0 → 4.
- **La nota la decide el scorer determinista, nunca el LLM.**
- **Los tres estimadores de banda coinciden en toda la rejilla** (0 desacuerdos) y
  el banco de placement **no tiene huecos de dificultad**.

## V3.71 — runtime, offline e instalación (P0 = 0 · P1 = 1 cerrado · P2 = 15 · P3 = 14)

> Origen: `docs/audit/RF-SINTESIS-RUNTIME-V371.md` (síntesis de los seis ejes
> `RE`–`RF`). Aquí va lo que V3.71 **deja sin cerrar a propósito**, con su fase o
> su acción. **Lo cerrado en V3.71 no se aparca**: ya no es deuda.

### Acción humana (no es trabajo del proyecto: requiere a una persona)

- **RA-05 · Corte de red real.** Los 12 flujos de `Y` §22 tienen veredicto
  **estático**; falta ejecutar el protocolo de `docs/audit/RA-RUNTIME-OFFLINE.md` §5
  con la red **desconectada** (no basta con desactivar el DNS: se buscan
  dependencias de Internet, no resolución de nombres). En CI es **imposible** por
  la premisa 12, así que cualquier «offline verde» en CI sería **simulado**.
- **RB-05 · Máquina físicamente limpia.** Existen el runbook (README) y la
  verificación previa (`download_models.py --check`), y ambos están fijados por
  test; falta **ejecutarlos en un clon/sistema recién instalado**. Es la diferencia
  entre «el runbook es correcto» y «el runbook funciona».
- **G5 · Matriz de dispositivos** (hardware real) y **variabilidad LLM de speaking**
  con Ollama real (ya aparcados arriba, siguen aquí).

### Abierto sin fase asignada (decisión pendiente)

- **RA-02 · El endpoint de Ollama no está declarado en `config.py`.** Se delega en
  el default de la librería (`127.0.0.1:11434`); un usuario con `OLLAMA_HOST` en
  otro puerto no está contemplado ni documentado. Caben dos cierres: declararlo en
  `config.py` o documentar explícitamente que se delega.

### Con fase asignada

- **RD-04 · Vector UI del P1 de TTS/offline → V3.72.** Aviso de descarga, progreso y
  **consentimiento** del usuario, y consumo de `X-TTS-Voice`/`X-TTS-Degraded`. El
  backend **ya expone** el dato; el P1 quedó cerrado en sus otros dos vectores
  (timeout y degradación) y este **no puede volver al olvido** porque está fechado.

### Deuda aceptada (declarada, no se arregla sin datos o sin decisión)

- **RD-05 · Caché negativa de voces volátil** (300 s, en memoria): un reinicio la
  olvida. Aceptada: el timeout ya es real y acotado, así que el reintento no
  cuelga.
- **RA-07 · La medición de red es estática.** El instrumento no puede demostrar que
  un camino concreto no haga red **en tiempo de ejecución** (solo que no contiene
  primitivas conocidas): un `import` dinámico o una librería de terceros que llame
  a casa no aparecería. La parte dinámica la cubre el protocolo de RA-05.
- **RC-04 · `ready` no exige la biblioteca de audio.** Deliberado: la biblioteca de
  audio es **opcional por diseño** (el corpus usa TTS), así que `ready` significa
  «la app puede dar clase», no «todo el catálogo está».
- **`ollama pull` es un paso manual que el proyecto no verifica.** El informe de
  instalación lo declara `exists=None` a propósito (el modelo lo gestiona el
  servicio de Ollama). Si el usuario no lo ejecuta, la app degrada en el chat y el
  runtime no puede evitarlo.

## V3.72 — UX / product completion

> Origen: briefing `agentes/v372-ux-product-completion.md`. Aquí va lo que V3.72
> **deja sin cerrar a propósito**. Lo cerrado en V3.72 no se aparca: ya no es
> deuda.

### Cerrado en V3.72 (deja de ser deuda)

- **RC-01 · Servido de `frontend/dist`.** El backend sirve la UI compilada por HTTPS
  en el mismo origen (`:8000`) y el launcher compila el artefacto si falta: **Node
  pasa de requisito de EJECUCIÓN a requisito de COMPILACIÓN**. Cierre y evidencia en
  `docs/audit/RC-RUNTIME-PRODUCTO.md` (§RC-01 · Cierre) y candados en
  `backend/tests/test_docs_drift_v372.py`.

### Cerrado en V3.72 (deuda UX)

- **F2** (doble lectura de readiness en Home), **F3** («estás aquí» con nivel
  estimado y objetivo) y **F4** (patrón loading/error/reintento en
  `FsrsReviewPanel`, `EvidenceGraphPanel` y `AssessmentLadder`).
- **«Por qué esta actividad» (Q5 de `F-UX-JOURNEY.md`)**: el `why` que el motor ya
  declaraba se pinta también en el pie «Next» de cada práctica (`NextStep`) y en
  las filas de la cola de repaso (`ReviewQueueSection`), con una sola pieza
  compartida (`components/WhyThisActivity.tsx`) y **sin recalcular señales en
  cliente** (premisa 21). Detalle en `docs/audit/F-UX-JOURNEY.md` §V3.72.
- **i18n**: `docs/audit/generated/i18n-report.json` queda a **0 huérfanas / 0
  duplicadas / 0 vacías**. El checker de V3.72 aprende dos indirecciones que
  antes contaba como huérfanas — plantillas de helper fuera de `t(...)` y el
  namespace `ns: "…"` de la página compartida de quiz — y eso reduce el residuo
  real de **10 claves** (no 50: la cifra de la auditoría F incluía falsos
  positivos de esas familias vivas). El checker corre ahora en el CI en
  `--strict`, así que una huérfana nueva vuelve a fallar el gate.
- **AE-04** (divulgación del placement): la limitación («mide reconocimiento/
  meta-lenguaje, no producción») queda declarada en el instrumento y en su
  contrato, y un candado avisa en cuanto el placement tenga pantalla: hoy **no
  existe superficie** (ningún componente consume `api/academy.ts`), así que la
  pantalla de nivelación sigue fuera de alcance (**→ V4.0.x**, con el onboarding
  o donde se muestre el resultado).
- **AE-06** (umbrales de banda): **cerrado**. Un solo módulo del corte
  (`services/cefr.py`) y decisión declarada sobre sub-bandas: `pre-a1` se
  conserva con su emisor; las `+` se retiran de la emisión y quedan como
  contenido de descriptores (ver `docs/audit/AE-PED-INSTRUMENTOS.md` §Cierre).

### Fuera de alcance declarado (no es deuda nueva)

- **Progreso real de descarga de voces**: el endpoint es síncrono y bloqueante; V3.72
  entrega consentimiento + aviso + progreso **indeterminado**.
- **Empaquetado/instalador** (vetado) y **multiplataforma** (el launcher es Windows).

## V3.73 — release de validación

> Origen: el dictamen externo de V3.72 (9,7/10) y su propuesta de **V3.73 como
> release de validación**. Aquí va lo que V3.73 **cierra** y lo que **deja
> declarado a propósito**. Lo cerrado no se aparca.

### Cerrado en V3.73 (deja de ser deuda)

- **Fail-closed del runtime de producto (P2 del dictamen).** El launcher arranca
  el backend con `ENGLISH_TUTOR_REQUIRE_UI=1` y **no lo arranca** si falta
  `frontend/dist/index.html`; con la variable activa, la falta del artefacto es un
  `RuntimeError` accionable en `mount_frontend`. Un `uvicorn main:app` manual
  sigue siendo fail-open (modo desarrollo). Candados:
  `backend/tests/test_serve_frontend_v373.py`,
  `launcher/tests/test_preflight_v373.py`.
- **RA-08 · Descubrimiento de la IP de LAN sin referencias externas (P3 del
  dictamen).** Se retira el socket UDP «connect» a `8.8.8.8` de
  `services/network.py`, `services/tls_cert.py` y `launcher/core.py`. Ahora
  `backend/services/net_interfaces.py` enumera las direcciones del propio equipo
  con un algoritmo **puro** (`select_lan_ipv4`) y un override declarado
  (`ENGLISH_TUTOR_LAN_IP`). Cascada del instrumento RA actualizada
  (`docs/audit/RA-RUNTIME-OFFLINE.md`, par generado regenerado). Candados:
  `backend/tests/test_net_interfaces_v373.py`, `launcher/tests/test_lan_ip_v373.py`.
- **Cobertura CI en Windows (bloque C del dictamen).** El CI pasa de 8 a 11 jobs:
  `launcher-windows` (bloqueante) y `product-origin-windows` (informativo a
  propósito: instalar `requirements-dev.txt` en Windows depende de ruedas nativas
  que no se pueden verificar desde Linux; el criterio de promoción está en las
  notas de release). Además `validation-gate` corre las comprobaciones estáticas.
- **Drift documental del runtime de producto.** `docs/DEVICE_MATRIX.md` seguía
  documentando `https://<ip>:5173` y el dev server de Vite como runtime, contra lo
  que V3.72 declaró. Corregido a `:8000` y ampliado con la matriz de interacción
  (touch, viewport, teclado, orientación).

### Instrumento nuevo (no es código de producto)

- **`scripts/validation_gate.py`** — los 7 gates de validación física como estado
  registrado (`auto` / `record` / `status --strict`), con evidencia en
  `docs/audit/validation-evidence.json` y runbook en
  `docs/audit/VALIDATION-RELEASE-V373.md`. `status --strict` es la puerta real de
  V4.0: falla mientras algún gate no esté en `pass`; `--same-tree` la endurece
  exigiendo que los siete `head_sha` sean el commit actual (V3.73.4). `record`
  sella el commit validado y la run de CI: un `pass` sin commit se rechaza.
  Candados: `backend/tests/test_validation_gate_v373.py` y
  `backend/tests/test_docs_drift_v373.py`.

### Sigue pendiente (acción humana) y sigue abierto

- **`RA-05` corte de red real**, **`RB-05` máquina físicamente limpia**, **`G5`
  matriz de dispositivos**, prueba en **Windows real** y **audio real**: son los
  gates `G1`–`G7` del arnés. V3.73 los convierte en estado registrado, **no** los
  ejecuta.
- **`RA-02` endpoint de Ollama sin declarar en `config.py`: sigue abierto.**
- **`RA-07`** (la medición de red es estática) y **`RD-05`** (caché negativa
  volátil) siguen como deuda aceptada.
- **Progreso real de descarga de voces** y **pantalla de nivelación** (con la
  divulgación de `AE-04`): → V4.0.x.
- **Empaquetado/instalador** (vetado por premisa) y **launcher para macOS/Linux**.

## V3.74 — frontera de red (loopback por defecto)

> Origen: el **P0 de identidad** abierto por la auditoría (`R1`): el `user_id` lo
> elige el cliente, los endpoints de perfil no exigen credencial y, encima, el
> producto se exponía **solo** en la red local por defecto. Esta fase ataca la
> **segunda** mitad (la superficie), **no** la primera. Plan por fases en
> `docs/audit/PLAN-P0-IDENTIDAD.md`; notas en `release-notes-v3.74.0.md`.

### Cerrado en V3.74 (deja de ser deuda)

- **La exposición en red dejó de ser el comportamiento por defecto.** El backend se
  enlazaba **siempre** a `0.0.0.0` y la regex de CORS aceptaba **cualquier** IP
  privada, así que exponer los datos del alumno a la WiFi no lo había pedido nadie:
  era la omisión del código. Ahora uvicorn se enlaza a `127.0.0.1` y la LAN es
  **opt-in declarado** (`ENGLISH_TUTOR_LAN=1`, o el botón «Activar red local» del
  panel de acceso del launcher, que lo declara y reinicia el servidor), leído
  **fail-closed**. Una sola decisión gobierna el `--host` y la política de orígenes
  (el launcher la propaga en el entorno del backend), de modo que las dos mitades no
  pueden discrepar. Candados: `backend/tests/test_lan_mode.py`,
  `launcher/tests/test_lan_mode.py` y
  `test_las_dos_mitades_de_la_politica_de_origen_coinciden`.
- **La trampa del patrón vacío.** `origin_allowed` comprobaba con `match`, así que
  un patrón vacío casaba con cualquier cadena: «desactivar» la regex de la LAN
  habría **abierto** CORS. Se sustituye por dos patrones (`LOCAL`/`LAN`), `fullmatch`
  y consulta por petición.

### Sigue abierto (esto **no** lo cierra)

- **El P0 de identidad sigue abierto, entero.** Lo que cambia es la superficie, no
  el modelo: **en modo LAN, `/api/users` sigue enumerando y creando perfiles sin
  credencial**, y el `user_id` lo sigue eligiendo el cliente. Quien active la LAN
  sigue entregando los datos del alumno a cualquier equipo de esa red.
- **`et_user_id` sigue siendo una cookie elegida por el cliente.** Su retirada
  (identidad derivada de una sesión firmada) es la **Fase 2** del plan, y cambia el
  **contrato de la API**: un cliente que hoy manda `?user_id=` dejará de funcionar.
  Por eso va en su propia release, y por eso esta no la adelanta.
- **La Fase 2 no está implementada ni aprobada en código**: el plan está aprobado
  **en diseño** y pendiente de revisión de la Fase 1.

## V3.75 — la identidad la firma el servidor (Fase 2 del P0) + P3 VG-N5/VG-N6

> Origen: las **dos mitades** que quedaban del P0 (`VG-01`: el cliente elegía la
> identidad) y los dos hallazgos P3 abiertos en
> `docs/audit/VERIFICACION-SEGURIDAD-V373.md` (`VG-N5`, `VG-N6`). Diseño y alcance
> en `docs/audit/PLAN-P0-IDENTIDAD.md` §6 y §14; notas en
> `release-notes-v3.75.0.md`.

### Cerrado en V3.75 (deja de ser deuda)

- **La identidad ya no viaja en la URL ni la elige el cliente.** `POST /api/session`
  emite una cookie `et_session` **firmada por el servidor** (HMAC-SHA256,
  `services/sessions.py`) y `HttpOnly`; `current_user` la verifica en cada petición
  (sin cookie, manipulada o caducada ⇒ **401 `SESSION_REQUIRED`**). El `?user_id=`
  de la URL **no significa nada** (fijado por `test_identity_source.py`, que manda
  las dos cosas a la vez —sesión de A y `?user_id=B`— y exige los datos de A).
  `et_user_id`, la cookie que escribía JavaScript, **se retira**.
- **Un perfil ya no edita a otro.** `PATCH /api/users/{id}` y `PUT /api/settings`
  exigen sesión **y** que el id sea el de la sesión (403 si no).
- **El secreto de firma no viaja en los backups** (`_NON_PORTABLE_TOP_NAMES`), así
  que restaurar el ZIP de otro equipo no permite forjar sesiones; restaurar
  **no** borra el secreto local.
- **`VG-N5`**: Actions fijadas por **SHA**, `permissions: contents: read` y job
  bloqueante `deps-audit` (`pip-audit` + `npm audit`). El escaneo **destapó** 10
  avisos en `starlette 0.50.0` (por `fastapi==0.128.0`), que se cierran subiendo a
  `fastapi==0.141.1` (→ `starlette 1.6.0`). Se añade **Dependabot** (pip, npm,
  `github-actions`).
- **`VG-N6`**: la superficie que responde **sin sesión** queda **declarada** por
  escrito y **acotada** por test en las dos direcciones
  (`test_public_surface.py` + sección en `docs/ARQUITECTURA.md`).
- **El panel del launcher ya no imprime el token**: informa de «sesión abierta:
  sí/no» y enmascara el valor (Firefox guarda las cookies en claro).

### Sigue abierto (esto **no** lo cierra)

- **No hay autenticación, y esta fase no la añade.** `POST /api/session` acepta
  cualquier `user_id` **existente** sin credencial: quien pueda alcanzar la API
  sigue pudiendo abrir sesión para cualquier perfil. Lo que ya no puede es
  **forjar** una identidad (sin el secreto del equipo) ni **elegirla en cada
  petición**. La frontera que decide **quién llega** sigue siendo la red (loopback
  por defecto, LAN opt-in, V3.74).
- **En modo LAN, `GET/POST /api/users` siguen sin credencial** (enumerar y crear
  perfiles), porque la puerta de perfil los necesita antes de que exista sesión.
- **Fase 3 (autenticación real) sigue sin decidir.** Contradice «sin cuentas, sin
  contraseñas» de `docs/PREMISAS.md`: es una **decisión de producto** y no una fase
  técnica pendiente.
- **`/api/network`, `/api/models` y `/api/system/status` siguen sin sesión**: es
  la decisión **aceptada** de `VG-N6` (reconocimiento barato, sin datos del alumno),
  no un olvido. La lista viva está en `docs/ARQUITECTURA.md`.

## V3.75.1 — el P0 del sesgo posicional del currículum

> Origen: el **único P0** que quedaba abierto del motor pedagógico, medido por la
> auditoría pedagógica de V3.70 (`docs/audit/AA-PED-CONTENIDO-CEFR.md` §3 y
> §Hallazgos #1) y aparcado con fase de contenido. Notas en
> `release-notes-v3.75.1.md`.

### Cerrado en V3.75.1 (deja de ser deuda)

- **La correcta ya no se concentra en la posición 0.** Estaba en **329 de 368
  checks (89,4 %)**, y **A2, B2, C1 y C2 estaban al 100 %** en la posición 0: un
  alumno que marcase siempre la primera opción acertaba casi 9 de cada 10 sin
  leer. Ahora el reparto es **`0:33,4 % · 1:33,2 % · 2:32,9 % · 3:0,5 %`** (peor
  posición **33,5 %** por grupo de `k`, bajo el límite del 35 % que pidió la
  auditoría). El contenido es el mismo: mismo `id`, mismo enunciado, misma opción
  correcta y mismos distractores.
- **El instrumento es re-ejecutable, no un arreglo de una vez.**
  `backend/scripts/rebalance_mc_positions.py` (`--check` / `--write`) reposiciona
  la correcta de forma determinista —en cada grupo de `k` opciones, ordenado por
  `id`, la posición destino es `j % k`— **moviendo solo la correcta** para que los
  distractores conserven su orden relativo. Tiene **tres invariantes** antes de
  escribir (forma canónica, nº de líneas intacto, JSON válido) y es
  **idempotente**; el diff fueron **614/614 líneas**, sin formato.
- **El candado muerde en las dos direcciones.**
  `test_mc_position_of_curriculum_checks_is_balanced` mide el reparto **por grupo
  de `k`**, exige **≤ 35 % por posición** y **ninguna posición muerta**, así que
  también falla si una reautoría futura vuelve a concentrar la correcta. El test
  anterior fijaba la cifra del defecto (329/368) y ya se reescribió: su contrato
  —forzar la re-auditoría al corregir— se cumplió.
- **`CURRICULUM_VERSION` 1.3.0 → 1.3.1.** Provenance pura: la constante se sella
  en evidencia y snapshots pero **nunca se compara**, así que no invalida el
  estado de ningún alumno.

### Sigue abierto (esto **no** lo cierra)

- **El P2 de sesgo de forma/longitud.** La correcta sigue siendo la opción más
  larga en el **39,1 %** de los checks y en el **50,0 %** del placement (hallazgo
  `#7` de `AA`). Reposicionar no toca longitudes.
- **`assessments.json` (exámenes y placement).** Siguen con la correcta en la
  posición 0 en el **63,6 %** de sus 22 ítems, y el placement la concentra en la
  posición 1 en **17/24**. Es **otro instrumento**, con su propio
  `ASSESSMENT_VERSION`, y su arreglo no se ha mezclado con este.
- **Los ítems en sí.** Esto elimina el atajo de marcar siempre la primera opción;
  no cambia distractores ni enunciados, así que no mejora la discriminación del
  ítem. Y que solo **10 de 368** checks tengan 4 opciones sigue siendo una
  irregularidad de autoría.

> **Corrección al enunciado del pendiente.** El pendiente decía «corpus de
> listening (B1) y checks del currículo (A1)». La medición dice otra cosa: el
> corpus de listening **ya estaba equilibrado** (máx. 30 % por posición, dentro
> del ≤35 %) y A1 era el **único** nivel del currículum con variedad apreciable.
> Lo que estaba roto era **todo el currículum** (368 checks) y no solo su nivel
> A1. Se anota para que el registro no arrastre la imprecisión.

## Pausa pedagógica pre-baseline — deuda de forma del banco (V3.75.1 · 2026-09-19)

Esta sección **sustituye la frase genérica del pendiente anterior** («normalizar
longitudes de opciones y reparto de posiciones al regenerar contenido») por el
alcance **medido**. Auditoría de solo lectura sobre el baseline congelado
**v3.75.1 = `7962d57`**; instrumento `item-form`, `distractor-signals` y el
`mc-bias` extendido (`backend/scripts/audit_dossier.py`), artefactos en
`docs/audit/generated/`. Dossiers: `AH`–`AL` y la síntesis
`AM-SINTESIS-PSICOMETRIA-V3751.md`.

**Resultado: 0 P0 · 4 P1 · 12 P2 · 9 P3** (25 hallazgos que describen **5
problemas reales**; los ejes se solapan a propósito). **Nada de esta sección se
ha corregido**: cada fila tiene su **fase** asignada y ninguna se implementa en
la pausa.

| # | Problema | Alcance medido | Fase propuesta |
|---|---|---|---|
| 1 | **Sesgo de longitud de la opción correcta** | Checks 39,1 % (144/368) · corpus 39,8 % (195/490) · exámenes 36,4 % · placement 50 %. **Concentrado por lote**: corpus C1/C2 **80 %**, B1 checks 50,9 %, C2 checks 56,1 %; A1 (25,7 %) por debajo del azar. Gradiente **no monótono** y sin banda en `CEFR-REFERENCE.md` ⇒ **deriva de autoría**, no incumplimiento CEFR | **V4.0.x contenido**, en la misma pasada que el reposicionamiento |
| 2 | **Sesgo posicional de los instrumentos de evaluación** | Exámenes: 63,6 % en posición 0 (B1 9/12) y **posición 2 muerta en los 22**. Placement: posición 1 en **17/24 = 70,8 %**, posición 2 en 1/24, y «marcar siempre 1» simula **6/8 y banda C2** (latente: ningún componente lo consume). La posición del examen es función del **bloque de destreza** | **V4.0.x contenido**, **antes** de cualquier pantalla de nivelación; regla `j % k` **por destreza** y sin posiciones muertas |
| 3 | **Heterogeneidad de forma (`k`)** | 358 checks `k=3` / 10 `k=4` (los 10 son un **residuo accidental** en A1 listening `o03`); corpus 100 % `k=4`; exámenes/placement 100 % `k=3`; **0 ítems `k=2`**. Suelo de azar distinto entre práctica (25 %) y evaluación (33,3 %) | **Decisión pedagógica de V4.0.x** antes de reautorar. **No** convertir todo a `k=4` por defecto |
| 4 | **Puntos ciegos del instrumento de medición** | `quantity_literal` dispara **1/904** pese a 87 enunciados de cantidad (falso negativo); `prompt_keyword_echo` cuenta solo el **eco exclusivo** (la correcta contiene palabra del enunciado en 80/904 = 8,9 %, ~2,8× la cifra reportada) | **Instrumento (coste bajo)**: ampliar el léxico de cantidad y publicar el eco no exclusivo |
| 5 | **Gradiente por nivel no monótono** | Checks 25,7→36,4→50,9→42,9→36,5→56,1 (ρ=0,77, rompe en B1→B2 y B2→C1); corpus 29,5→39,5→60,0→40,0→80,0→80,0 (ρ=0,93, rompe en B1→B2) | **Declaración, no corrección**: si se quiere progresión de forma, se diseña explícitamente |

**Positivo (no requiere acción).** El invariante de reparto de V3.75.1
(`≤ 35 %` por grupo de `k`) se cumple **también por nivel**, sin ninguna posición
muerta — pero es **emergente**, no blindado: con n=20–35 un ítem mueve 3–5 pp y
no existe candado por nivel.

**Qué NO se hizo (y por qué).** No se corrigió ningún `.json`; **no se añadieron
candados que fijen el defecto** —a diferencia del test de 329/368 de V3.70—,
porque el invariante de forma correcto todavía no se conoce: se diseñará **con**
la corrección. Tampoco se decide aquí la política de `k` ni el arreglo de
`assessments.json`.

**Honestidad.** (i) Mide **acierto explotable**, no aprendizaje. (ii) No mide
plausibilidad semántica de distractores (exigiría hablantes) ni la **tasa real**
del atajo (la estrategia se **simula**, no se observa). (iii) Los instrumentos de
evaluación son **46 ítems, no 904**; no se generalizan con la confianza de los
368.

**Árbol de la entrega (decisión sobre los ficheros hoy sin seguimiento).** El
árbol queda **limpio** incorporando, como parte de esta entrega del baseline, el
dossier **`docs/audit/AG-AUDITORIA-MOTOR-V375.md`** (auditoría del motor de
dominio/pedagogía sobre V3.75.0): es el **eje de motor** de la misma serie y su
lugar correcto es `docs/audit/`, junto a `AH`–`AM`. `AM` no lo repite y lo cita
como el eje del **cálculo**, frente a `AH`–`AL`, que miran la **forma de lo que
ese cálculo sirve**. Con él incorporado, no queda ningún fichero sin declarar
antes de sellar el baseline.

**La política que ordena el cierre de esta deuda (2026-09-19).** La decisión de
**cómo** se corrigen los 5 problemas —y no solo **cuándo**— queda fijada en el
dossier de diseño **`docs/audit/AO-POLITICA-PSICOMETRICA-V40.md`**
(`POLITICA_PSICOMETRICA_VERSION = "1.0.0 (V4.0)"`): **Regla A** (posición `≤ 35 %`
por `k`, nivel y **destreza**, sin posiciones muertas, extensible a
`assessments.json`), **Regla B** (longitud `≤ 1,5 × azar` de su `k` por lote, con
excepciones enumeradas), **Regla C** (`k=3` en lo que gatea · `k=4` en el corpus
de práctica · residuo de 10 checks alineado · `k=2` prohibido) y **Regla D**
(rúbrica de plausibilidad del distractor). AO **no corrige nada ni añade
candados**: ordena la reautoría de V4.0.x y fija sus criterios de aceptación.
Las cinco filas de esta tabla siguen **abiertas** y con la misma fase asignada.

## V3.75.2 — verificación de la release y fragilidad del arnés visual (2026-09-19)

> Origen: verificación **completa y local** del árbol en `c9c234d` (`docs(v3.75.2):
> politica psicometrica…`, sobre `0ff7488` = tag `v3.75.2`), replicando los trabajos
> de `.github/workflows/ci.yml` en **Windows con PowerShell 5.1**, que es donde vive
> el alumno. Se ejecuta porque la suite declarada (2900) y los jobs de script no se
> habían corrido **desde el árbol real de la release**, solo desde el CI.

### Cerrado en V3.75.2 (deja de ser deuda)

- **El humo del origen de producto pasa en Windows, por HTTPS.** `product-origin` es
  el único job que arranca el **producto de verdad** (uvicorn con TLS sirviendo el
  `dist` construido) y **no se había ejecutado nunca en el sistema del alumno**: en
  el CI corre en ubuntu y su gemelo Windows (`product-origin-windows`) está en
  `continue-on-error: true`. En esta máquina: raíz sirve HTML, `/api/health` → `200`
  con `version 3.75.2` y `/api/no-existe` → **404** (el fallback SPA no enmascara la
  API). El certificado se reutilizó con sus SANs (`127.0.0.1`, LAN, `english-tutor.local`,
  `localhost`). `[R]`
- **La cadena de suministro está limpia.** `pip-audit -r backend/requirements.txt` →
  *no known vulnerabilities*; `npm audit --omit=dev --audit-level=high` → 0. `[R]`
- **Deriva del artefacto de validación automática.** `docs/audit/generated/release-validation.{json,md}`
  estaba estampado con la versión `3.75.0`: lo genera `scripts/validation_gate.py auto`,
  que **el CI ejecuta pero no commitea**, así que el artefacto versionado en el tag
  `v3.75.2` declaraba una versión de árbol que ya no era la suya (ni V3.75.1 ni V3.75.2
  lo regeneraron). Regenerado y commiteado (`4e99009`); el diff es **solo la estampa de
  versión**, con los 10 checks igual. `[R]` Patrón a vigilar por la auditoría externa:
  **un artefacto generado por el CI puede quedar obsoleto sin que ningún job falle**.

### Sigue abierto (esto **no** lo cierra)

- **El arnés visual (`playwright`) es frágil bajo carga en Windows — no se pudo
  reproducir una ejecución completa verde.** El job pasa en ubuntu, pero en esta
  máquina: **1.ª tanda 14 fallos / 24 pasados / 28 skipped**; **`desktop` aislado
  18 pasados / 4 skipped**; **tanda completa 10 fallos / 28 pasados / 28 skipped**.
  `[R]`

  **Evidencia de que no es el producto ni la API.** (i) El código es **idéntico byte
  a byte** al del tag `v3.75.2` (la única diferencia del árbol es documentación). (ii)
  El backend registró **776 peticiones, todas `200 OK`** durante la tanda que falló
  (`/api/academy/session`, `/api/settings`, `/api/profile`, `/api/academy/student-model`…):
  el proxy `/api` de Vite funciona. (iii) Entre los fallos hay specs **con `mock`**, que
  interceptan `/api` sin tocar el backend, y aun así caen. (iv) El humo del origen pasa
  entero (arriba).

  **Diagnóstico.** Es **contención de recursos + arranque en frío**, no un fallo
  funcional: el DOM del fallo muestra la carcasa renderizada con `status: Loading…`, es
  decir una aserción **agotada por tiempo**, y las aserciones tienen **presupuesto de
  15 s** mientras varias pruebas tardan **15,9–27 s** ya con la caché caliente. El
  primer proyecto en ejecutarse (`desktop`) concentra los fallos. Hipótesis concreta
  y verificable en Windows: `baseURL`/`webServer.url` son `https://localhost:5173`
  mientras Vite escucha con `host: true` (IPv4), de modo que **`localhost` puede
  resolverse primero a `::1` y cada petición paga el intento fallido antes de caer a
  IPv4**; sumado a 3 proyectos en paralelo, empuja al filo del presupuesto. `[D]`

  **Arreglos candidatos (decisión pendiente, no implementados).** (a) Fijar el extremo
  a `https://127.0.0.1:5173` en `playwright.config.ts` (o `server.host`), que elimina
  el fallback IPv6 y es el más barato; (b) acotar `workers` en local o añadir un
  precalentamiento en `globalSetup`; (c) subir el presupuesto de las aserciones del
  arnés. (a) y (b) atacan la causa; (c) tapa el síntoma. `[POL]`

  **Por qué se aparca y no se arregla ahora.** No toca al alumno ni el runtime, y el
  CI (ubuntu) es la ejecución autoritativa, donde el job está verde. Tocar
  `frontend/tests/visual/**` es una decisión de diseño sobre **reproducibilidad del
  arnés**, no una corrección de producto, y su fase natural es la próxima release que
  toque el frontend o el **gate G3** (Windows real): este hallazgo **refuerza** que el
  arnés visual en el sistema del alumno solo está probado de verdad en ubuntu.

- **Los 7 avisos `advisory` de `transfer_validation`.** `demand_spread` avisa de
  familias (`story`, `future`, `problem`, `routine`, `debate`, `academic`) cuya carga
  efectiva cae fuera de su banda de demanda heurística **sin WSD**. Siguen
  **advisory** por diseño (`ok: true`): no bloquean y su cierre exige la fase de
  calibración con alumnos. `[R]`
- **Cobertura `pre-a1` en 0/7 celdas.** `content_validation` cierra en 42/49 celdas
  (**85,7 %**); el hueco entero es `pre-a1`, coherente con «Pre-A1 como producto»
  (§Métricas). No es una regresión: es la decisión de catálogo sin tomar. `[R]`

> **Nota de alcance.** Esta sección **no** reabre la pausa pedagógica: las cinco
> filas de la tabla de arriba siguen **abiertas** con su fase asignada y su política
> (AO). Aquí solo se registra qué quedó **verificado** al probar la release y qué
> deuda **nueva** apareció al hacerlo. Ningún `.json` de banco, servicio, frontend ni
> launcher se modificó para escribirla; el árbol quedó limpio y los artefactos de
> Playwright (`tests/visual/.artifacts/`, `screenshots/`, `.tester.json`) están
> ignorados por git.

## Pendientes de acción humana (no aparcados, en curso)

- Ejecutar la **matriz de dispositivos** en hardware (G) y volcar resultados a
  `docs/DEVICE_MATRIX.md`.
- Medir la **variabilidad LLM de speaking** con Ollama real (`eval_speaking_variability`).
