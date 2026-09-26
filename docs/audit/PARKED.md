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

- **`scripts/validation_gate.py`** — los **8** gates de validación física como estado
  registrado (`auto` / `record` / `status --strict`), con evidencia en
  `docs/audit/validation-evidence.json` y runbook en
  `docs/audit/VALIDATION-RELEASE-V373.md`. `status --strict` es la puerta real de
  V4.0: falla mientras algún gate no esté en `pass`; `--same-tree` la endurece
  exigiendo que los **ocho** `head_sha` sean el commit actual (V3.73.4; la cifra
  pasa de **siete a ocho** en `V3.81.2`, con el gate `G0 · identidad-cuentas`).
  `record` sella el commit validado y la run de CI: un `pass` sin commit se rechaza.
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
  técnica pendiente. **Actualización (V3.76.0):** se decidió e implementó el **PIN
  opcional por perfil** como **mitigación**, no como autenticación real; la
  decisión de fondo —si el producto tendrá cuentas— **sigue abierta** y se ve en la
  sección `V3.76.0` de este documento.
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

## El launcher no arrancaba la app y mentía sobre por qué (2026-09-20)

> Origen: al probar la app, el launcher mostró «Backend: 🔴 Detenido» e «Interfaz:
> 🔴 No compilada». **Ninguna de las dos cosas era cierta.** Síntoma de un conflicto
> de puerto, pero el diagnóstico era imposible de deducir desde la GUI por cuatro
> defectos propios del launcher. Fix: `b40fcdc` (D1/D2) y el commit de esta
> declaración (D3/D4 y la codificación del gate). **Posterior al tag `v3.75.2`**: se
> etiqueta `V3.75.3` en los comentarios de código.

### Cerrado (deja de ser deuda)

- **D1 · «No compilada» era mentira.** La etiqueta la decidía una **sonda de red**,
  así que un origen que no responde se pintaba como un artefacto que falta. Con
  `frontend/dist/index.html` presente y el puerto 8000 ocupado por un servidor HTTP,
  la GUI decía «No compilada» y mandaba a compilar lo ya compilado. Ahora hay **tres**
  estados —`🟢 Servida` · `🔴 No responde` · `🔴 No compilada`— y el artefacto se
  comprueba **en disco** (`ui.interface_state`, pura). Mismo arreglo en el mensaje de
  «Abrir app». `[R]`
- **D2 · La guardia anti-duplicado era ciega al esquema.** Detectaba un backend ya
  activo **solo por HTTPS** (`fetch_health`), así que un backend HTTP en el mismo
  puerto era invisible: el launcher arrancaba el suyo y moría contra el puerto
  ocupado (`WinError 10048`). Ahora se comprueba el **socket** (`core.port_in_use`)
  antes de preparar nada y se explica el motivo (`ProcessManager.ensure_port_free`).
  `_wait_ports_free` espera al socket, no a las sondas, que daban por libre un puerto
  todavía ocupado. `[R]`
- **D3 · El motivo del fallo no llegaba al usuario.** Un backend que moría al
  arrancar dejaba «🔴 Detenido» y el motivo quedaba enterrado en `logs/backend.log`.
  Ahora se espera a que el producto **sirva la UI** y, si no lo hace, se traduce el
  tramo de log de **este** arranque a una frase accionable
  (`ui.backend_failure_hint`). Verificado contra el fallo real: el
  `WinError 10048` del log de 87 MB se traduce a «El puerto ya estaba ocupado por
  otro proceso justo al arrancar». `[R]`
- **D4 · El log crecía sin límite y se leía entero.** `backend.log` estaba en
  **87,3 MB / 1,3 M de líneas** sin rotación, y `read_log_tail` hacía `read_text()`
  completo **cada 2 s** (refresco de la GUI) para quedarse con 250 líneas: **334 ms
  medidos por lectura**, y creciendo. Ahora hay rotación de una generación (5 MB) en
  el único punto de escritura y la lectura se hace **por cola** (`TAIL_BYTES`):
  **0,5 ms, 731× más rápido**, con el mismo contenido. `[R]`
- **El artefacto de validación se corrompía según el entorno.** `validation_gate.py`
  capturaba la salida de sus sub‑scripts con `text=True` y **sin `encoding`**, así
  que el texto dependía del *locale* del equipo: la misma comprobación daba
  `orígenes` o `orÃ­genes`, y el mojibake acababa en un fichero **versionado**. El
  fix fija la codificación en **los dos lados** (el hijo recibe
  `PYTHONIOENCODING=utf-8`), porque fijar solo el padre convierte la salida cp1252 del
  hijo en `U+FFFD` —que además no se puede imprimir en consola cp1252 y **hacía morir
  el gate al imprimir**, devolviendo un fallo inexistente—. La salida propia del gate
  también se hace resiliente. `[R]` Es la misma familia que la deriva de versión de
  arriba: **la evidencia no registraba fielmente lo que pasó**.

**Verificación del fix (el camino real de «Iniciar app»).** Ejercitado el
`ProcessManager` completo: `ensure_port_free` OK → `prepare` OK → `start_backend` OK →
**sirve la UI en 2,1 s** (la GUI diría `🟢 Servida` + `🟢 Activo`), `/api/health` → 200
con `3.75.2`, HTTPS sirve HTML, el log rotó de **87,3 MB a 0,4 KB** dejando su
generación `.1`, y `stop_all` dejó el puerto libre. `[R]` Launcher: **162 tests**
(eran 142; +8 de D1/D2 y +12 de D3/D4), ruff limpio. Backend: 2899 pasados, y el
candado `test_docs_drift_v371` obligó a actualizar el número de tests del launcher en
`docs/ARQUITECTURA.md`. `[R]`

### Sigue abierto (esto **no** lo cierra)

- **El launcher no se prueba en su sistema real.** `launcher/tests/**` cubre los
  módulos puros, pero **la GUI no tiene test** (necesita pantalla), así que los cuatro
  defectos de arriba vivieron sin que ningún test los viera. Su fase natural es el
  **gate G3** (Windows real) y, en general, es el argumento de que la lógica nueva se
  haya puesto en `core`/`ui`/`process_manager`, que sí se testean. `[D]`
- **`logs/frontend.log` conserva una generación antigua** (7,6 MB del 2026-09-15):
  ahora rota igual que el del backend, pero **solo al escribir**; un log huérfano de
  una versión anterior no se limpia solo. Se resolverá con el primer `npm run build`
  que vuelva a escribir en él, o a mano. `[D]`
- **La verificación de la rotación es de unidad, no de uso.** El umbral (5 MB, una
  generación) es una decisión, no un hallazgo: si el diagnóstico real necesitase más
  histórico, se revisa. `[POL]`

## V3.75.3 — preferencias del launcher, listening sin fricción y análisis global (2026-09-20)

> Origen: tres peticiones del gerente sobre la app en uso —(1) que el launcher
> **recuerde** la última configuración (en concreto «ACTIVADA RED LOCAL»), (2) que
> la práctica de listening de móvil no gaste un paso entero en «He escuchado —
> responder», y (3) que el **Análisis** esté en la cabecera junto al usuario y
> muestre la evolución del alumno en su conjunto, en vez de un panel flotante
> dentro del ejercicio. Plan: `lan, listening y análisis` (V3.75.3).

### Decisiones tomadas (y su precio)

- **La preferencia de red se persiste** en `launcher/config.json`
  (`launcher/config_store.py`), se lee **al arrancar** antes de pintar la interfaz y
  se guarda **en cada cambio**. Responde a la pregunta abierta nº 1 de
  `docs/audit/PLAN-P0-IDENTIDAD.md` y **revierte §5.8** del mismo documento: el modo
  LAN pasa de decisión de sesión a **decisión de instalación**. `[POL]`
  - **Lo que esto reabre, dicho sin adornos:** un equipo con `{"lan": true}` arranca
    con uvicorn en `0.0.0.0` y aceptando orígenes de red privada **sin que nadie lo
    declare en esa sesión**. El P0 de identidad sigue abierto y, en modo LAN,
    `GET/POST /api/users` siguen sin credencial (§V3.75). Antes de esta versión, ese
    estado se perdía al cerrar el launcher.
  - **Mitigación (no lo elimina):** el modo es **visible** desde el primer pintado
    (fila LAN con el enlace + botón «Desactivar red local»), el fichero es local y se
    ignora en git, el default es **cerrado**, y un valor editado a mano que no sea el
    booleano `True` (`1`, `"sí"`) se lee como cerrado. Candados:
    `launcher/tests/test_config_store.py` y las cuatro pruebas nuevas de
    `launcher/tests/test_lan_mode.py` (aplicar al arrancar, sin preferencia,
    valor no booleano, y preferencia **por encima** del entorno heredado).
- **Listening sin el paso «He escuchado — responder».** La tarjeta `while1`
  desaparece y la señal de «he escuchado» es **pulsar PLAY**: `play()` avanza la
  etapa al **empezar** el audio (en el TTS, al lanzarlo —`speakWithVoice` resuelve al
  terminar—), y en el `catch` **no** avanza, para que un fallo de audio deje el
  ejercicio donde estaba. `[UX]` Efecto deliberado: sin pulsar PLAY no se ven las
  opciones. Se retiran tres claves i18n huérfanas; `microFlow.ts` no se toca.
- **Compactación móvil de la misma pantalla**: contenedor, tarjeta de audio, botón
  PLAY, waveform y una fila de controles A/B que se oculta por debajo de `sm`. Se
  **conserva** el deslizador de posición (una línea, sirve para releer un tramo) y
  todos los objetivos táctiles (`min-h-10`). `[UX]` La comprobación visual sigue
  pendiente de hardware (ver abajo).
- **El Análisis se va a la cabecera y a su propia ruta.** `frontend/src/features/analysis/AnalysisScreen.tsx`
  en `/analisis` (`ANALYSIS_PATH`), abierto con un botón en el bloque `ml-auto` del
  `Header`. Es **destino auxiliar**: no lleva píldora en `Navigation` (por eso no
  toca `ROUTES` ni rompe el test de las 5 píldoras). Sintetiza posición, actividad
  real con su agrupación temporal, tríada, destrezas y escalera CEFR reutilizando
  endpoints que ya existían, **sin crear ninguno**. `[UX]`
  - **Se retira el panel flotante**: `components/AnalysisPanel.tsx` **borrado**,
    fuera las reglas CSS muertas (`.pane--insights`, `.insights-header`,
    `.insights-toggle`, `workspace--learn`, `chat.resizeInsights`, etc.) y el asa
    derecha del workspace. El panel se había quedado sin analítica propia en V3.1
    (calidad del tutor + enlace a MI PROGRESO) y solo se encontraba dentro del
    ejercicio. La calidad del tutor no se pierde: la recibe la pantalla nueva desde
    los turns de la sesión en curso.

### Sigue abierto (esto **no** lo cierra)

- **El P0 de identidad, entero**, y ahora con una vía más para arrancar expuesto:
  la preferencia persistida. La Fase 3 (credencial o emparejamiento) sigue sin
  existir y **no cambia de prioridad** por esta decisión. Ver
  `docs/audit/PLAN-P0-IDENTIDAD.md` §5.9. `[D]`
- **El barrido visual de `/#/analisis` y del listening compacto no se ha ejecutado.**
  Playwright en Windows es frágil (ya registrado en §V3.75.2) y el plan deja la
  captura para la validación física. `resize.spec.ts` se reescribió sobre el asa del
  **sidebar** —la que sobrevive— porque probaba la derecha, que ya no existe. `[D]`
- **`layout.rightWidth` sigue existiendo y persistiéndose** (`utils/layout.ts`) sin
  consumidor: el asa del panel de análisis se retiró, pero el contrato de layout
  tiene sus propios tests y no se poda en esta release para no arrastrar cambios al
  `useChat`. Es deuda de forma, no una fuga. `[D]`

## V3.75.4 — listening pulido y rampa de niveles configurable (2026-09-20)

> Origen: dos peticiones del gerente sobre la app en uso —(1) qué es el botón de
> «SALTAR» de APRENDER/LISTENING y si se puede quitar, y (2) que los niveles
> (A1, A2, …) tengan **color de fondo progresivo** para leerse de un vistazo, con
> inspiración en las apps top y **elegible por perfil**. Plan:
> `listening pulido y rampa de niveles` (V3.75.4).

### Decisiones tomadas (y su precio)

- **El «Saltar» del pie se conserva, discreto y reubicado.** Era `listening.skip`
  (`ListeningPractice.tsx`) y llamaba a `load()`: **pide otro ítem sin responder**,
  la única salida de una pregunta sin registrar evidencia (audio que no suena,
  ítem incomprensible). Se retira del pie, donde competía con las opciones, y pasa
  a la cabecera nueva como botón fantasma pequeño («Otro ejercicio», clave
  `listening.anotherItem`, la anterior renombrada para no dejar huérfana). `[UX]`
  No se confunde con el otro «Saltar» de la tarjeta de shadowing
  (`listening.flow.skipStage`), que declina el paso **opcional** que el backend
  marca con `allow_skip`.
- **El color de nivel pasa de 3 tramos a 7 pasos, con un solo mecanismo.** Antes
  `utils/cefr.ts::cefrTone` devolvía `basic|intermediate|advanced`, así que A1 y A2
  (o B1 y B2) eran del mismo color y el color no decía nada. Ahora
  `cefrLevelKey`/`levelClass` (Pre-A1 → C2 + «sin dato») son la única puerta y las
  clases **estáticas** `.lv-*` de `styles/legacy.css` la única pintura: sin clases
  Tailwind interpoladas (el escaneo las purgaría) y sin `inline style`. Las clases
  se declaran **fuera de capa** a propósito, para que una utilidad de Tailwind de
  la misma línea no borre el color del nivel. `[UX]`
  - **Fallo previo que se arregla de paso:** `LearningProfile.tsx` llamaba
    `cefrTone(profile.estimated_bands[skill])` con un **número** (escala 0–6), así
    que caía siempre en `basic` y las filas del perfil se pintaban iguales.
    `bandToLevelKey(numeric)` recupera el tramo, declarado como **aproximación de
    color**, no como medida de dominio.
- **La rampa es elegible por usuario (Ajustes > Apariencia), sin backend nuevo.**
  Tres esquemas —**Semáforo** (por defecto, reproduce los colores que ya había),
  **Espectro** y **Monocromo** (7 intensidades del acento, cero hexes propios)— con
  vista previa en el propio diálogo. Se aplica con `data-levels` en `<html>` (igual
  que `data-theme`/`data-accent`/`data-density`), se persiste por perfil con la
  clave `level_scheme` en el `PUT /api/settings` que ya existía y `localStorage`
  como copia para que un backend caído no pierda la preferencia. El relleno y el
  borde se **derivan** de la tinta con `color-mix()`, así que un esquema nuevo son
  7 hexes y no 21. `[UX]`
- **El gate del color es la medición, no el gusto.** `contrast_audit.mjs` mide cada
  paso sobre su **relleno compuesto** (sobre `--color-surface` y sobre `--color-bg`)
  en los **3 esquemas × 2 temas** —y en Monocromo, por los **7 acentos**—, con
  guardas de que la rampa esté completa. Hoy: **472 pares + 4 guardas, 0
  bloqueantes con fallo** en `--strict`. Los hexes se ajustaron hasta AA; el precio
  es que la paleta es tributaria del contraste, no al revés. `[D]`
  - **Alcance honesto de la medición:** mide la tinta sobre el relleno compuesto en
    esos dos fondos, no cada sitio donde se dibuja una insignia; y que un nivel
    tenga color no implica que el alumno domine ese nivel.

- **El selector de rutas del listening se agrupa de dos en dos.** La rejilla de
  seis rutas (A1·A2 / B1·B2 / C1·C2) pasa a **dos columnas** en todos los anchos
  —celda horizontal, anillo a la izquierda y datos a la derecha— y **«Auto»** sale
  de ella a una **fila propia a ancho completo**, después de C2: es la opción que
  **no** elige ruta y no debía competir con las seis que sí la eligen. Entre el
  resumen (precisión · ruta actual) y la rejilla, y entre esta y el panel de nivel,
  quedan **separadores finos** (`border-border/60`). La celda conserva el
  `aria-label` «Level {nivel} history» y el objetivo táctil, así que el arnés
  visual sigue encontrándola. `[UX]`
  - **Medido, no estimado:** con el arnés (`playwright`, 3 viewports), las seis
    celdas ocupan **3 filas de 2** y no hay desbordamiento horizontal
    (`scrollWidth == clientWidth` en 390 / 768 / 1280). En móvil cada celda mide
    158 px de ancho y entre 66 y 107 px de alto; «Auto» ocupa el ancho de la
    tarjeta. `[D]`

### Sigue abierto (esto **no** lo cierra)

- **El barrido visual completo sigue sin hacerse.** De esta release se ha
  ejecutado **solo la parte de listening**: `routeExtraReview` (pasa) y una
  medición geométrica de la rejilla en 3 viewports, que es lo que respalda el
  apartado anterior. El barrido de la **rampa en toda la app** y de **Ajustes**
  sigue pendiente, y Playwright en Windows sigue frágil (V3.75.2 y V3.75.3): la
  validación física no se declara hecha. `[D]`
- **`cefrTone` sobrevive en documentos históricos** (`agentes/pedagogia/*`,
  `agentes/endurecimiento/*`, `RELEVO.md`, `CHANGELOG.md`): son briefs y actas de
  lo que se decidió entonces y **no se reescriben**. El código ya no tiene ninguna
  referencia. `[D]`
- **El P0 de identidad sigue entero** y este incremento no lo toca (ninguna ruta
  nueva, ningún endpoint nuevo). `[D]`

## V3.75.5 — voz configurable y dos acentos en listening y rutas de quiz (2026-09-20)

> Origen: una petición del gerente sobre la app en uso —desde el «…» de la
> tarjeta de audio **elegir** la voz (no sólo verla), y que el altavoz que
> aparece tras responder leyera el **ítem completo** y dejara oírlo con **dos
> acentos** (p. ej. inglés de Inglaterra y de EE. UU.)—, más la extensión de la
> convención visual de V3.75.4 (niveles de dos en dos, «Auto» en fila propia,
> rampa de color, separadores finos y «Saltar» discreto) a las **rutas de quiz**.
> Plan: `voz configurable y dos acentos` (V3.75.5).

### Decisiones tomadas (y su precio)

- **El «…» deja de ser un cartel y pasa a configurar.** Antes sólo leía «Voz
  sintética local (TTS) · <voz> · <wpm>» y no había ningún camino a la
  configuración desde la práctica. Ahora abre el bloque `VoicePicker`: fila
  **Voz A** (la del perfil, `tts_voice`), fila **Voz B** (segundo acento,
  `tts_voice_alt`) y dos chips **«Probar A» / «Probar B»** que reproducen *ese*
  ítem para comparar antes de decidir. El mismo bloque, tal cual, cuelga del
  «…» de las rutas de quiz: una sola idea de acento en toda la app. `[UX]`
- **Se puede pedir voz, y sólo una instalada.** `TTSRequest.voice` y el query
  param `voice` de `/api/listening/audio/{id}` viajan hasta
  `tts.pick_requested_voice`, que **sólo** acepta una voz instalada y del idioma
  pedido; si no pasa el filtro **se ignora en silencio** y manda
  `resolve_voice(prefs)`. No es laxitud: es que la UI no puede romperse por una
  preferencia vieja (ni recibir un 400 por ella) y, sobre todo, el id de voz
  **entra en rutas de disco** (`PIPER_DIR / "<voz>.onnx"` y
  `data/listening/{banco}/{voz}/…`), así que aceptarlo sin validar sería path
  traversal por construcción. `[D]`
- **`X-TTS-Voice` / `X-TTS-Degraded` siguen declarando lo que realmente sonó**,
  no lo que se pidió: la UI puede ser honesta cuando degrada. `[D]`
- **Cero backend nuevo para la preferencia.** Voz A = `tts_voice` (ya existía),
  voz B = `tts_voice_alt`, una clave más del mismo `PUT /api/settings`. La caché
  de audio ya estaba separada por voz, así que el segundo acento es **una caché
  más**, no un motor nuevo. `[D]`
- **La B se sugiere sola, y nunca cruza idiomas.** `utils/voices.ts::suggestAltVoice`
  propone la primera voz del **mismo idioma y otra locale** (US → GB y al revés),
  de modo que «dos acentos» funciona recién instalada la app sin obligar a
  configurar nada; el selector sólo ofrece voces del idioma de la voz A, porque
  mezclar idiomas haría que la B leyera el ítem en otro idioma. `[UX]`
- **Un store de módulo, no un contexto.** `hooks/useVoiceChoice.ts` (patrón de
  `useVoiceDownload`, `useSyncExternalStore`) hace **una sola** lectura de
  `GET /api/voices` + `GET /api/settings` para toda la app aunque haya varios
  altavoces en pantalla, y **vacía el estado al cambiar de perfil** (la voz de un
  alumno no puede quedarse a la vista de otro). Configuración → Voces escribe
  `tts_voice` por su cuenta, así que el panel **relee** el store al elegir voz y
  al instalar una nueva (`refreshVoiceChoice`): sin eso la voz A de la práctica
  quedaba desincronizada. `[D]`
- **`ListenButton` sin `accent` no cambia.** El componente histórico mantiene su
  comportamiento (3 argumentos, sin tocar el store) cuando no se le pide acento:
  es lo que hace que 40 y pico usos previos y sus tests sigan intactos. Donde el
  altavoz lee un **ítem**, se usa `ItemReplayButton` (un botón por acento
  disponible); donde lee texto arbitrario del alumno (traductor), sigue el
  `ListenButton` de siempre. `[D]`
- **PLAY sigue sonando en voz A.** El botón grande no cambia de significado: la
  escucha de estudio es una sola y el segundo acento vive donde el alumno lo
  pide, que es **después de responder**. `[UX]`
- **El altavoz de después de responder lee el ítem entero** —enunciado y opciones
  con su letra (`buildReplayText`: `"<enunciado>. A: …. B: …."`)— en voz A o B, y
  con una sola voz instalada **sólo** aparece A: nunca un botón que no puede
  sonar. La etiqueta cambia según el caso (`voice.replayOptions*` con opciones,
  `voice.replayPhrase*` sin ellas): no promete opciones donde no las hay. `[UX]`
  - **Actualizado en V3.75.6** (ver más abajo): la lectura pasa a ser una
    **composición** que elige el perfil (`replay_scope`), así que «el ítem entero»
    es sólo una de las tres; las claves `voice.replayOptions*` se sustituyen por
    `voice.replayItem*`, que no prometen opciones porque el defecto ya no las lee.
    `[D]`
- **El mismo control, allí donde se escucha.** Además de listening y las rutas de
  quiz, se sustituyó el altavoz mudo por el consciente de la voz en los paneles de
  nivel de listening/vocabulario/gramática/conversación/pronunciación/speaking, en
  los escenarios de pronunciation y speaking, en el drill de vocabulario, en el
  diccionario (palabra y ejemplo) y en la evaluación de speaking. `[UX]`
- **Rutas de quiz con la convención de V3.75.4.** Las seis rutas van **de dos en
  dos** (A1·A2 / B1·B2 / C1·C2) con celda horizontal (anillo + datos), **«Auto» en
  fila propia** a ancho completo —es la opción que *no* elige ruta y no debe
  competir con las seis que sí—, **rampa de color** (`levelClass` + `lv-ink` /
  `lv-outline` en el anillo), **separadores finos** y el `LevelBadge` con el mismo
  mecanismo que listening. `[UX]`
  - **El «Saltar» se muda a la cabecera, pero no se pierde.** Antes vivía al pie
    de la tarjeta de práctica, compitiendo con las opciones; ahora es un botón
    fantasma discreto en la cabecera de la pantalla (63×32 px medidos), visible
    **también dentro de una sesión** —como estaba— y oculto sólo mientras se
    evalúa o cuando ya hay resultado, que es cuando manda «Continuar». Retirarlo
    durante las sesiones habría sido una regresión silenciosa: es la única salida
    de un ítem sin registrar evidencia. `[UX]`
- **Medido, no estimado.** El arnés (`playwright`, 3 viewports, mock determinista
  de las rutas de gramática, spec temporal ya retirada) deja: **6 celdas en 3
  filas de 2** en 390 / 768 / 1280, sin desbordamiento horizontal
  (`scrollWidth == clientWidth`), celda de **154×66** px en móvil y **335×70** en
  tablet/escritorio, «Auto» a ancho de tarjeta (316 / 678 px). En el mismo
  recorrido se comprobó que el «…» muestra las dos filas de voz y que, tras
  responder, aparecen los dos altavoces (A y B). `[D]`
- **Verificación completa de la release:** `tsc --noEmit` limpio, `vitest run`
  **777/777**, `npm run build` correcto, `audit:contrast --strict` **472 pares +
  4 guardas, 0 bloqueantes** (sin colores nuevos: la rampa sigue siendo la de
  V3.75.4 y el informe se regenera con esa etiqueta a propósito),
  `check_i18n_coverage --strict` **1504 claves, 0 huérfanas**, `ruff` limpio,
  `pytest` **2906/2906** y los 6 specs visuales de rutas (desktop) en verde. `[D]`

### Sigue abierto (esto **no** lo cierra)

- **La primera reproducción en voz B cuesta unos segundos.** Sintetizar y alinear
  (ASR) ese WAV es trabajo real la primera vez que se pide cada ítem × voz ×
  variante; después queda cacheado. El chip muestra su spinner y no se queda
  mudo, pero no es instantáneo y no se disimula. `[D]`
- **La caché crece**: ~100 KB por ítem × voz × variante. Es disco local y se puede
  borrar sin romper nada, pero no se recolecta sola. `[D]`
- **El acento sigue siendo simulado.** Piper sintetiza; una voz «británica» no es
  un hablante británico. Dos voces hacen la diferencia audible y la etiqueta
  honesta sigue junto al selector, pero la promesa no crece. `[D]`
- **El barrido visual completo sigue sin hacerse** (viene de V3.75.4): de esta
  release se ha medido la rejilla de rutas y la presencia del control de voz, no
  cada pantalla donde se sustituyó el altavoz. Playwright en Windows sigue
  frágil; la validación física no se declara hecha. `[D]`
- **El P0 de identidad sigue entero** y este incremento no lo toca: no añade
  endpoints, sólo dos parámetros validados sobre rutas que ya exigían sesión. `[D]`

## V3.75.6 — STOP en la repetición, lectura corta y la RUTA B1 que no se parecía a las demás (2026-09-20)

> Origen: tres observaciones del gerente usando la app —(1) al elegir **RUTA B1**
> el ítem no aparecía como en las otras rutas y mostraba «Enviar dictado»; (2) la
> repetición en A/B está bien, pero una lectura larga necesita un **STOP**; (3) en
> el «…» debe poder fijarse —y persistir— si esa repetición lee **solo la
> respuesta correcta** o **todas las opciones**. Su petición de (3) se concretó el
> mismo día, tras la primera entrega, en **tres composiciones** (ver abajo): la
> primera versión del control ofrecía dos y el gerente precisó qué piezas entran
> en cada una.

### Decisiones tomadas (y su precio)

- **(1) Era una etiqueta mal puesta, no un flujo nuevo.** `c071` y `c084` —los dos
  únicos ítems del corpus (490) etiquetados `dictation`/`shadowing`— estaban
  **autorados como pregunta de opción múltiple** (`question` + 4 `options` +
  `answer_index`). El flujo se elige por `skill` (`flow_for_skill` → producción),
  así que la app pedía **escribir a mano** una frase cuyo contenido autorado era
  «Which time did you hear?» con opciones. Corregido **en el contenido**: `c071` →
  `numbers`, `c084` → `phrase_recognition` (corpus `3.0.0` → `3.0.1`). B1 vuelve a
  recibir lo mismo que las otras cinco rutas y **recupera dos ítems servibles**
  que antes se tiraban. `[D]`
  - **Precio declarado: hoy no queda ningún ítem de dictado.** El endpoint
    `/api/listening/dictation` y el flujo de producción siguen vivos y probados,
    pero el esquema del corpus **exige** `options` + `answer_index`, así que no
    puede representar un dictado: es **deuda de contenido**, no de código. Quien
    quiera dictado real tendrá que autorarlo con un esquema que lo represente. El
    test `test_corpus_production_items_do_not_carry_multiple_choice_options` cierra
    el atajo: una etiqueta no convierte una pregunta en un dictado. `[D]`
  - El **shadowing** no desaparece de la práctica: sigue siendo el paso opcional
    del micro-flujo receptivo (grabar y escucharse), que ya existía. `[D]`
- **(2) STOP en la repetición, no en el PLAY.** `api/voz.ts` gana un registro de
  módulo con la locución en curso: `stopSpeaking()` pausa el audio **y** cancela la
  síntesis si aún no había sonado, y la promesa de `speak()` **resuelve** —parar no
  es un error—, así el botón apaga su spinner sin tratar el corte como fallo.
  Además, **una sola locución a la vez**: empezar otra corta la anterior (antes se
  solapaban). El STOP sólo existe mientras suena y vive junto a los botones A/B. `[D]`
- **(3) `replay_scope`, una clave más del mismo `PUT /api/settings`.** El «…» —el
  mismo `VoicePicker` de listening y de las rutas de quiz— añade «Al repetir, leer»
  con **tres composiciones** (corrección del gerente del mismo día: la primera
  versión ofrecía dos y él concretó las piezas). Un ítem tiene cuatro: **texto** (el
  `script`, lo que suena), **pregunta**, **opciones** y **respuesta correcta**. De
  ahí salen `"item"` (**defecto**: texto + pregunta + respuesta), `"withOptions"`
  (texto + pregunta + opciones + respuesta) y `"correct"` (pregunta + respuesta).
  `[UX]`
  - **Por defecto, menos es más:** quien no toca nada oye lo que sonó y la clave, no
    las tres alternativas. Es un cambio de defecto **declarado**: hasta ahora la
    única lectura era la larga. El valor histórico `"all"` se normaliza a
    `"withOptions"`, así que quien la había elegido de forma explícita no pierde su
    elección; ausente o desconocido cae a `"item"`. `[D]`
  - **Una sola función decide el texto** (`buildReplayText`), con salvaguardas:
    descarta piezas ausentes en vez de inventarlas, no repite el ítem cuando el
    script *es* la pregunta (habitual en A1) y si el alcance elegido dejara la
    lectura vacía cae a la composición completa —nunca una repetición muda—. `[D]`
  - **No puede filtrar la respuesta antes de tiempo:** `correct_index` sólo lo
    aportan los sitios que ya han respondido (listening y rutas de quiz); hasta
    entonces el altavoz de repetición ni existe. `[D]`
  - El control se muestra aunque falle el catálogo de voces: cómo se repite no
    depende de qué voces estén instaladas. `[UX]`
  - **El «recibo» nació de un problema real de diseño:** las tres etiquetas se
    parecen («el ítem completo» / «el ítem más las opciones») y la diferencia está
    en las piezas, no en las palabras. En vez de un párrafo que explique las tres,
    bajo los botones se describe **la activa** («Se lee: texto del ítem + pregunta +
    opciones + respuesta correcta»). `[UX]`
- **Contrato de UI fijado en pantalla real:** `frontend/tests/visual/
  listeningReplayStop.spec.ts` (mock-based, 3 breakpoints) navega a la RUTA B1 y
  comprueba que las opciones están y la tarjeta de producción no, que el «…» ofrece
  las tres lecturas con la primera activa, y que tras responder aparecen A/B y el
  STOP. Además **lee el cuerpo real del `POST /api/tts`** y exige que el texto
  compuesto sea texto + pregunta + opciones + clave: la composición del gerente
  verificada de punta a punta, no sólo en unitarios. Medido: STOP **32×32** dentro
  del viewport (x+w = 199 en 390) y **sin desbordamiento horizontal**
  (390/390 · 768/768 · 1280/1280). Que el **banco** sirva una pregunta receptiva en
  B1 lo fija `test_listening_corpus.py`: la suite visual mide la UI, no el
  contenido. `[D]`
- **Verificación de la release:** `tsc --noEmit` limpio, `vitest run` **805/805**,
  `check_i18n_coverage --strict` **1511 claves, 0 huérfanas**, `audit:contrast
  --strict` **472 pares + 4 guardas, 0 bloqueantes**, `ruff` limpio, `pytest`
  **2907/2907**, `playwright test --workers=1` **41/41** y métricas del corpus
  regeneradas (`docs/audit/generated/listening-corpus-stats.*`). `[D]`

### Sigue abierto (esto **no** lo cierra)

- **La suite visual no aguanta el paralelismo del arnés.** `playwright test` con los
  3 workers por defecto encadena fallos que **no** son del producto: en la misma
  ejecución fallaron 14 specs ajenos (`resize`, `smoke`, `speaking`,
  `pronunciationRoutesReview`…) con `page.goto` agotando los 30 s o elementos que no
  aparecen, y **cada uno pasa en aislamiento**. Con `--workers=1` los **41/41** son
  verdes. La causa probable es la saturación del dev server de Vite (transformación
  en frío × 3 navegadores × 15 specs). La medición de este bloque se hizo con
  `--workers=1`, y la de V3.75.4/5 con specs sueltos: conviene decidir si el arnés
  fija un worker, sube el timeout o sirve `dist` compilado en vez de dev server. `[D]`
- **El corpus no tiene dictado ni shadowing autorado** (arriba): hay endpoint,
  flujo, UI y tests, pero ningún contenido que los dispare. `[D]`
- **`docs/LISTENING_ENGINE_4.0.md` (2026-09-09)** citaba `c071`/`c084` como
  evidencia de dictado y shadowing. Es una especificación fechada y no se
  reescribe, pero se le añade la nota de corrección para no dejar una cita falsa
  en un documento que se sigue leyendo. `[D]`
- **El corpus en marcha no se recarga solo.** El backend lee el banco al importar:
  quien tenga el servidor arrancado de antes seguirá viendo la tarjeta de dictado en
  B1 hasta reiniciarlo (y `frontend/dist`, servido por el backend, necesita
  recompilarse para ver la UI nueva). Es el precio de servir la UI compilada desde
  el mismo proceso. `[D]`

## V3.75.7 — el icono del desplegable y el texto que no queda debajo del botón (2026-09-20)

> Origen: cierre de la pantalla de listening pedido por el gerente. (1) «Donde el
> desplegable solo muestre información el botón tendrá una (i) y donde sea info y
> posibles opciones será (...). Revísalo en toda la APP». (2) «Al desplegarse el
> texto no debe tener partes cubiertas por el botón (...), como sucede ahora».

### Decisiones tomadas (y su precio)

- **(1) El icono es un contrato, no un adorno: una sola fuente de verdad.** El «...»
  ya significaba «abre para configurar» (tarjeta de audio de listening); un «...» que
  solo escondía un párrafo obligaba a pulsar para descubrir que no había nada que
  decidir, y una (i) sobre controles escondía opciones bajo una promesa falsa. La
  regla vive en `components/InfoDisclosure.tsx` (`content: "info" | "options"`) y el
  **defecto es `"info"`**: un panel nuevo que no declare nada no puede prometer
  opciones. La etiqueta accesible acompaña al icono (`common.moreOptions` =
  «Opciones e información» para el «...»; `common.moreInfo` para la (i)). `[UX]`
  - **Inventario de la revisión (11 disparadores, ninguno sin clasificar).** Ocho
    `InfoDisclosure` con **(i)**: notas de ruta de listening y notas de los paneles de
    nivel de las seis destrezas (speaking tiene dos). Uno con **(...)**: notas de ruta
    de las rutas de quiz, que cuelgan del mismo `VoicePicker`. Y tres que no usan el
    componente: el «...» de la tarjeta de audio (velocidad + voces + repetición, ya
    era «...» y sigue), el desplegable de texto «Cómo funcionan las rutas» (ya era (i)
    con etiqueta visible) y el propio botón de los paneles, que no se toca. `[D]`
- **(2) El panel reserva la columna del botón, no altura.** En `variant="corner"` el
  disparador flota sobre la Card y el panel se monta donde el llamador lo ponga —en
  listening, como primer hijo—, así que su primera línea salía **tapada** por el botón
  que acababa de abrirla: medido, el párrafo «A real CEFR B1 means…» quedaba dentro del
  rectángulo del botón. El panel ahora reserva `pr-12` (36 px del botón + 12 px de
  aire). Reservar altura (`pt`) habría dejado un hueco muerto en los paneles que no
  llegan al borde superior; reservar columna no cuesta nada en ninguno y hace que el
  botón se apoye en la esquina del panel sin tapar una sola letra, suba el panel o no.
  `[D]`
  - La composición de clases se hace explícita (`py-2 pl-3 pr-12` en la esquina frente
    a `px-3 py-2` en el flujo) para **no depender del orden** en que Tailwind emita
    `px-*` y `pr-*`. `[D]`
- **El «...» de la tarjeta de audio no necesitaba corrección, y se comprueba.** Su
  panel vive muy por debajo del botón (nace tras el PLAY), así que ningún nodo suyo
  intersecta el disparador: se midió en los tres breakpoints en vez de darlo por hecho.
  `[D]`
- **Contrato de UI fijado en pantalla real:** nuevo test en `frontend/tests/visual/
  listeningReplayStop.spec.ts` que en **desktop, tablet y móvil** (390/768/1280)
  comprueba (a) que el disparador de notas lleva `lucide-info` y el de audio
  `lucide-ellipsis`/`more-horizontal`, (b) que ningún nodo de texto del panel
  intersecta el rectángulo del disparador —lista vacía en los tres— y (c) que el panel
  del «...» contiene opciones de verdad (las tres composiciones de la repetición). Y en
  unitario, `InfoDisclosure.test.tsx` fija el icono por defecto (i), el de `options`,
  y la reserva de columna de la variante de esquina. `[D]`
  - **La guarda tiene dientes, verificado:** revirtiendo `pr-12` a `px-3` el test
    vuelve a fallar con `coveredNotes: ["p|A real CEFR B1 means hundreds of known w"]`.
    Sin esa comprobación, un test verde no probaría nada. `[D]`

### El P1 que destapó la auditoría de la tanda, y tres P3 (V3.75.7)

La verificación de esta tanda se hizo en **dos auditorías independientes en
paralelo** (frontend y backend/launcher). La de backend encontró un **P1 que
contradecía el objetivo visible de la propia tanda**, y destapó tres P3.

- **(P1) La RUTA B1 seguía sirviendo la tarjeta de dictado, y el defecto estaba en
  el banco heredado.** `V3.75.6` corrigió `c071`/`c084` **en el corpus**, y su test
  —`test_production_items_do_not_carry_multiple_choice_options`— **filtraba ids
  `c`**: miraba solo el corpus. Los ítems **`l18` (`dictation`) y `l19`
  (`shadowing`)** del `_LEGACY_BANK` seguían con `question` y `options`, así que el
  flujo de producción los servía igual y B1 seguía mostrando «Enviar dictado».
  Medido, no supuesto: `B1 prod [('l18','dictation',4), ('l19','shadowing',4)]`
  frente a `corpus prod con opciones []`. `[D]`
  - **Se cierra en la causa raíz, no en el síntoma.** (1) `PRODUCTION_SKILLS` se
    declara **una sola vez** en `services/listening_flow.py` y la consume
    `build_item_flow`: estaba **duplicado en tres sitios**, y esa duplicación fue
    parte de por qué el defecto sobrevivió a su propio arreglo. (2) El barrido del
    test es sobre **todo** `QUESTION_BANK`. (3) `l18` → `numbers` y `l19` →
    `phrase_recognition`. **Cambia la etiqueta, no el contenido:** su `script`, sus
    opciones y su audio son los mismos. `[D]`
  - **El test que no mordía se arregla en los dos sentidos.** Hoy **no queda ningún
    ítem de producción** en el banco, así que el barrido del test es **vacío** y
    podría pasar **por estar roto**: se le añade un **control positivo**
    (`test_production_guard_bites_on_a_synthetic_offender`) que inyecta un ítem de
    producción **con opciones** y exige que la comprobación lo reconozca. `[D]`
  - **La suite deja de apoyarse en ítems concretos del banco.** Nuevo fixture
    `production_items` en `tests/conftest.py` (ítems de producción **sintéticos**:
    copia de un ítem real con el `skill` cambiado) y migran a él
    `test_listening_production.py`, `test_word_breakdown_v329.py`,
    `test_listening_shadowing2_v328.py` y `test_listening_attempts_v327.py`, que se
    rompían **cada vez** que el banco cambiaba. Y `test_bank_covers_every_subskill`
    → **`test_bank_covers_every_receptive_subskill`**: el banco **no puede** contener
    producción (el esquema exige `question` + `options` + `answer_index` en todos sus
    ítems), así que la ausencia se exige **exacta** en vez de una igualdad que ya no
    puede cumplirse. `[D]`
- **(P3) La voz que suena no se declaraba en el audio de listening.**
  `domain/listening.py::get_audio` devuelve ahora la voz **realmente usada** y
  `routers/listening.py` la publica en **`X-TTS-Voice`**: el frontend ya no puede
  creer que oyó **dos acentos** cuando, por falta de voz instalada, sonó la misma dos
  veces. `[D]`
- **(P3) `config.json` no se escribía de forma atómica.** `launcher/config_store.py::save_config`
  escribe a un temporal y hace `os.replace`, así que un corte a mitad ya no puede
  dejar el fichero de preferencias a medias. `[D]`
- **(P3) La decisión que cambia la frontera de red no tenía test propio.** La lógica
  de LAN se centraliza en `launcher/core.py` (`apply_stored_lan_config`,
  `toggle_lan_config`) para que se pueda probar **fuera de `tkinter`**, que no se
  puede ejecutar sin pantalla. `[D]`
- **La deriva documental que la propia release creó.** El recuento de tests del
  launcher en `docs/ARQUITECTURA.md` había quedado en `155` y el test de deriva lo
  exige real: **161 funciones / 178 casos**. Se corrige el número, no el test. `[D]`

**Lo que el P1 declara abierto.** (i) **El provenance del banco no distingue el
antes del después:** `LISTENING_BANK_VERSION` sigue en **`7.0.0`** a propósito
—la constante **también** nombra la caché de audio y ningún `script` ni `audio_id`
cambió—, así que dos contenidos servidos distintos comparten `bank_version`. Es un
hueco **declarado** y candidato a hallazgo del auditor, no una omisión: la política
del proyecto sí bumpea provenance cuando el coste es cero (así se hizo con
`CURRICULUM_VERSION` en V3.75.1) y aquí el coste es re-sintetizar el banco entero.
(ii) **Hoy no queda ningún ítem de dictado autorado.** (iii) El corpus en marcha **no
se recarga solo** ni la UI compilada en `dist`: sin reiniciar y recompilar, quien
tuviera el backend arrancado seguiría viendo la tarjeta de dictado en B1. `[D]`

### Sigue abierto (esto **no** lo cierra)

- **Los paneles de nivel solo están verificados por estructura y en unitario.** Sus
  desplegables son `inline` (el botón y el panel se apilan en un `flex-col`), así que
  el solapamiento es imposible por construcción y el unitario fija icono y clases; pero
  **no** se navegó a las seis pantallas para medir su geometría real como sí se hizo en
  listening. Si alguna se cambia a `corner`, la guarda visual no la cubre. `[D]`
- Sin cambios: el corpus no tiene dictado autorado, la suite visual no aguanta el
  paralelismo del arnés (medir con `--workers=1`) y el corpus en marcha no se recarga
  solo (reiniciar backend y recompilar `frontend/dist` para ver la UI nueva). `[D]`

## V3.75.8 — el diccionario de consulta con buscador grande y un color por sentido (2026-09-20)

> Origen: tres peticiones del gerente sobre la app **en uso**: «que la parte visual
> sea más atractiva (como los diccionarios de apps top)», «que el espacio para meter
> la palabra sea más grande y esté más claro, especialmente en el móvil» y «si está
> en un sentido tiene un color y si está en otro, otro color, para que sea más
> visual». Al cerrar la sesión pidió además que la **Ayuda** declare la **versión de
> compilación** junto al autor.

### Decisiones tomadas (y su precio)

- **(1) El buscador es la vista, no un control más.** El campo era una fila de
  **40 px** (`h-10 text-sm`) con el botón al lado, compitiendo con el `h1`, con las
  pestañas de la pantalla y con el conmutador de sentido —que vivía **encima** del
  campo, en una pastilla `bg-secondary`, sin relación visual con él—. Ahora el campo
  vive dentro de una **tarjeta-buscador** (`rounded-2xl`, marco de 2 px, barra
  superior de color y anillo de foco del mismo color) y mide **48 px en móvil y
  56 px en escritorio/tablet**; el icono de lupa va teñido del sentido activo y el
  **conmutador entra dentro del buscador**, en dos pastillas a ancho completo.
  El precio, declarado: **la pantalla es más alta** (la tarjeta metida en el flujo
  ocupa **132 px** en escritorio y **172 px** en móvil, medido) y el botón de
  consulta deja de estar a la altura del campo en móvil, porque el campo y el botón
  se apilan. A cambio, el objetivo táctil del campo sube por encima de los 44 px que
  pide el estándar en el sitio donde el gerente lo pedía. `[UX]`
- **(2) Sin consulta, la vista empieza con ejemplos.** Cuatro palabras por sentido
  (`travel/book/water/family` en EN→ES, `casa/viaje/comida/tiempo` en ES→EN) que
  **rellenan el campo y buscan** al pulsarlas, y un botón de borrado (`X`) dentro del
  campo que **solo existe cuando hay texto** y que **solo vacía el campo**: el
  resultado de la última consulta sigue a la vista —no es «nueva consulta»—, y esa
  semántica queda fijada por test en `DictionaryLookup.test.tsx`, no abierta. Van
  marcadas con su `lang` (los
  ejemplos de ES→EN se teclean en español, que es la lengua de la que se busca) y
  viven en `utils/dictionaryDirection.ts` como **contenido**, no como interfaz: no
  pasan por i18n. El precio: son **cuatro palabras fijas por sentido** que hay que
  mantener a mano; no se generan del léxico del alumno ni del banco. `[UX]`
- **(3) Un color por sentido, y el color es una convención —no una preferencia—.**
  **Azul** para EN→ES y **fucsia** para ES→EN, con el relleno y el borde **derivados
  de la tinta** (`color-mix()` al 15 % y 35 %), el mismo mecanismo que la rampa de
  niveles de V3.75.4. La pareja es **complementaria** y **no pisa los colores de
  estado** (verde dominada, ámbar en curso, rojo débil). **A diferencia de la rampa,
  no sigue el acento del perfil** y no se ofrece en Ajustes: si el color del sentido
  cambiara con el acento, dos acentos afines podrían dejar azul y fucsia casi iguales
  y la señal se perdería; es una **leyenda del diccionario** (azul ↔ fucsia), y una
  leyenda que se puede cambiar deja de ser una leyenda. El precio: **no es
  consistente con la rampa** en ese punto —hay colores de la app que siguen al perfil
  y este no—, y esa asimetría hay que declararla para que no se lea como un olvido.
  `[D]`
  - `directionClass()` devuelve el **nombre de una clase** (`.dir-en-es` /
    `.dir-es-en`) y nunca una interpolación de Tailwind: el escaneo de clases
    purgaría `text-${dir}` y el color desaparecería sin que ningún test se enterara.
    Es el mismo contrato que `levelClass` para la rampa. `[D]`
- **(4) Cuál manda: el buscador se tiñe del sentido ACTIVO; la tarjeta, del sentido
  DE SU CONSULTA.** La tarjeta usa `entry.direction` y lleva una **marca de
  dirección** («English → Spanish») junto a la palabra, de modo que **conmutar el
  buscador después de buscar no repinta el resultado**: el resultado no puede mentir
  sobre en qué sentido se pidió. Dentro de la ficha el color se concentra en el
  **equivalente** —el bloque con más tinta y `text-lg font-semibold`, porque es la
  respuesta— y en la pestaña del ejemplo; el resto queda en neutro para que el color
  **informe** en vez de decorar. Precio: **dos convenciones de color en la misma
  pantalla** (activo vs. resultado) que solo se entienden si el rótulo de dirección
  está a la vista, y está. `[D]`
- **(5) Un solo `h1` en `/diccionario` (defecto encontrado de paso).** La vista de
  consulta traía cabecera propia (`h1` + subtítulo) y la pantalla la suya: había
  **dos `h1`** en la misma página, el título repetido y el relleno de página aplicado
  dos veces. `DictionaryLookup` recibe `showHeader` (**defecto `true`**, para quien la
  monte suelta) y `DictionaryScreen` lo apaga. `[D]`
- **(6) La Ayuda declara la versión de la compilación.** Nuevo
  `utils/buildInfo.ts`: la versión se lee del `package.json` **en tiempo de
  compilación** y viaja en el bundle —solo el campo `version`; el resto del fichero
  no entra—. La razón no es cosmética: la única versión visible en la app era la del
  **backend** (`GET /api/health` → `SystemStatus`), que es exactamente la que **no**
  responde cuando el alumno pregunta «¿qué versión tengo?». La Ayuda es una pantalla
  **sin red**, así que su versión no puede depender de la API.
  `check_release_consistency.py` mantiene ese número igual al de los otros orígenes.
  Precio, declarado: lo que muestra es la **versión**, no la fecha ni el `hash` del
  build, así que **dos compilaciones de la misma versión se declaran igual**; y la
  tarjeta de vocabulario de la Ayuda explica ahora el sentido y su color, con lo que
  el texto de ayuda depende del diseño del diccionario. `[P]`
- **(7) La ayuda se actualiza donde el diseño cambió, y solo ahí.** La tarjeta de
  «Vocabulary y diccionario» decía «tu diccionario personal» y no mencionaba el
  **diccionario de consulta** ni su conmutador de sentido: se le añade una frase
  («…y tú eliges el sentido (inglés → español o español → inglés): cada sentido tiene
  su color»). No se toca ninguna otra tarjeta porque ninguna otra describe algo que
  haya cambiado. `[UX]`

### Medición y contrato (V3.75.8)

- **El color se mide, no se elige a ojo.** `scripts/contrast_audit.mjs` gana el par
  de direcciones: tinta de cada sentido sobre su **relleno compuesto**, en los **2
  temas** × **2 fondos** (`--color-bg`, `--color-surface`), con el **porcentaje de
  mezcla leído del CSS** en vez de supuesto. Resultado: **5.76–8.02:1** frente al
  mínimo **4.5:1** (**480 pares + 6 guardas, 0 bloqueantes** en `--strict`). `[D]`
- **Dos guardas nuevas, y la que importa es la de las clases:** `direccion-completa`
  (las dos tintas en los dos temas) y `direccion-clases-y-derivados` (relleno al
  15 %, borde, las clases `.dir-*` y el marco `.dir-field`). Si `directionClass()`
  devolviera una clase que **no** existe, el buscador se quedaría **sin color** y
  ninguna otra prueba se enteraría: el unitario comprueba el **nombre** de la clase,
  no que exista una regla CSS con ese nombre. `[D]`
- **Contrato visual medido en los tres breakpoints, con spec temporal.** Campo de
  **48 px** en móvil (**390×844**) y **56 px** en tablet (**768×1024**) y escritorio
  (**1280×800**), conmutador con **dos colores computados distintos** al conmutar
  (EN→ES computa `rgb(30, 64, 175)` en tema claro; el spec exigía que el segundo
  **fuera distinto**, no un valor concreto) y **cero desbordamiento horizontal**
  (`scrollWidth - innerWidth <= 0`). El spec **se borró** al cerrar la revisión.
  `[D]`
- Sin cambios: el `dist` **no se versiona** (hay que recompilar para ver la UI nueva),
  el P0 de identidad sigue entero —la congelación de esta candidata lo reverificó y
  dejó su briefing de decisión en `docs/audit/PLAN-P0-IDENTIDAD.md` §15— y los
  **7 gates** siguen en `pending`. `[D]`

### Lo que queda abierto de esta pantalla (aparcado)

- **No hay spec visual permanente del diccionario.** La medición se hizo con un spec
  temporal que se borró al cerrar la revisión, así que una regresión de layout o de
  color en `/diccionario` solo la volvería a ver una revisión manual. El contraste
  **sí** está cubierto por guarda permanente (script), y la clase que se aplica por
  unitario; lo que no está cubierto es **cómo se ve**. `[D]`
- **El color no añade información, evita una confusión:** el sentido ya lo decía el
  rótulo y el color solo lo adelanta. Quien no distinga azul de fucsia sigue teniendo
  el rótulo; lo que no hay es una señal redundante **no cromática** más allá de él
  (ni forma, ni icono distinto por sentido). `[UX]`
- **Los ejemplos son fijos.** Cuatro palabras por sentido, escritas a mano. Generarlas
  del léxico del alumno (o del banco) sería material para otra iteración. `[UX]`

## V3.76.0 — el PIN opcional por perfil (Fase 3 del P0 de identidad) y G7 preparado (2026-09-21)

> Origen: la Fase 3 del P0 (`docs/audit/PLAN-P0-IDENTIDAD.md` §15) —`POST
> /api/session` aceptaba cualquier `user_id` existente **sin credencial**— y la
> preparación de G7 sobre el árbol congelado. Decisión del gerente: **PIN opcional
> por perfil**, 4-6 dígitos, hash PBKDF2 stdlib y cookie de un año; y **regenerar
> los 9 dossiers** para que la revisión humana de G7 sea leer y firmar. Notas en
> `release-notes-v3.76.0.md`.

### Cerrado en V3.76.0 (deja de ser deuda)

- **El perfil que activa PIN deja de abrirse sin credencial.** `POST /api/session`
  responde `401 PIN_REQUIRED` / `401 PIN_INVALID` / `429 PIN_THROTTLED` y existe
  `PUT /api/session/pin` bajo la sesión (sin `{id}` en la ruta) para poner, cambiar
  y retirar el PIN. Cambiar o retirar exige el anterior.
- **El freno de intentos por perfil** (5 fallos libres; después retardo que dobla
  con techo de 300 s; se limpia al acertar). Es la pieza que sostiene un PIN de 4
  dígitos, y está declarado así en el código.
- **El arranque con PIN deja de fallar en silencio.** `planSession` gana el
  desenlace `pin` y `useChat` centraliza la apertura en `openProfile`, compartido
  por arranque, selector y alta.
- **Los 9 dossiers de G7 son reproducibles.** Regenerados sobre el árbol congelado
  (`v3.75.8` · `7134e538`) con `docs/audit/generated/` **sin un byte de
  diferencia**. `record pedagogia` **no** se ha ejecutado: G7 se cierra con la
  revisión, no con una regeneración.

### Sigue abierto (esto **no** lo cierra)

- **El P0 sigue abierto para el producto.** Un perfil **sin** PIN sigue entrando
  sin credencial, que es el defecto: la mitigación es **opt-in** y el P0 queda
  cerrado **para los perfiles que la usan**, no para la app. `[SEGURIDAD]`
- **No hay autenticación de persona: ni identidad, ni recuperación.** Quien olvide
  el PIN **no puede demostrar que es él**; el único camino es perder el acceso al
  perfil (o editar la BD a mano). Decisión declarada, no un olvido. `[SEGURIDAD]`
- **La cookie de un año es un tecleo por navegador.** Protege ante *otro equipo
  sin la cookie*; **no** protege ante quien se sienta delante del tuyo, ni ante un
  navegador ya autenticado, ni ante quien pueda leer el fichero de la BD (el hash
  viaja en el backup a propósito). `[SEGURIDAD]`
- **`GET/POST /api/users` siguen sin credencial** (enumerar y crear perfiles), con
  `has_pin` como único añadido: la puerta de perfil los necesita antes de que
  exista sesión. La puerta muestra **qué perfiles están protegidos**. `[SEGURIDAD]`
- **El freno vive en memoria del proceso.** Un reinicio del backend lo vacía; con
  un servidor local de un solo usuario es suficiente, y el cupo por IP
  (`/api/session`, 120/min) es la primera valla, no la defensa. `[SEGURIDAD]`
- **La decisión de fondo sigue abierta: ¿tendrá el producto cuentas?** El PIN
  responde «¿cómo mitigo el acceso mientras no las tenga?», no «¿las tendrá?».
  Sigue contradiciendo «sin cuentas, sin contraseñas» de `docs/PREMISAS.md` y es
  una decisión **de producto**. `[PRODUCTO]`
- **El hash viaja en el backup.** Es estado del perfil (dentro de la BD) y se
  declaró que **sí** debe viajar, mientras `session.secret` sigue sin viajar. Quien
  reciba un ZIP sin cifrar puede atacar el PIN **con el freno desactivado** (fuera
  de línea, sin la API). La única defensa real es la entropía del hash, no la
  longitud del PIN. `[SEGURIDAD]`
- **G7 no está cerrado.** Los dossiers son reproducibles, pero la **revisión
  humana** de la matriz de los 9 ejes sigue pendiente, y `record pedagogia` sin
  ejecutar. **Los 7 gates siguen en `pending`.** `[VALIDACIÓN]`
- **La matriz de lectura de los 9 ejes no queda versionada como documento.** Se
  entrega para la revisión de G7 y se sella con el `record`; si no se copia a
  `docs/audit/`, la próxima campaña tendrá que volver a derivarla de los
  artefactos. `[VALIDACIÓN]`

## V3.77.0 — retención léxica del diccionario personal y perfiles con autorización del webmaster (2026-09-21)

> Origen: dos peticiones del gerente en la misma sesión —(a) que el diccionario
> **personal** sirviera para **añadir** vocabulario (palabra suelta, lista o tema) y
> **practicarlo** con enfoque de tarjetas para retención a largo plazo, mirando a
> Anki/Memrise/Drops/Lingvist; (b) que los **perfiles** se creen y se borren **desde
> el lanzador**, con la solicitud del alumno llegando al **webmaster** y siendo él
> quien autoriza—. Decisiones: unidades léxicas, FSRS-lite, «añadir a personal» como
> acto explícito, petición **inerte**, **desactivar** antes de **purgar**, y
> administración con **doble candado** (loopback + PIN) **fail-closed**. Corrección
> registrada en `agentes/v377-perfiles-webmaster.md` §4bis: el candado es el **PIN**
> de V1.37 (declarado por el lanzador), no un token nuevo en fichero. Notas en
> `release-notes-v3.77.0.md`.

### Cerrado en V3.77.0 (deja de ser deuda)

- **El diccionario personal deja de ser un archivo y pasa a ser un plan.** Se
  guardan **unidades léxicas** (palabra **o frase funcional**, con forma, sentido y
  **contexto**), se añaden de tres formas por **una sola puerta** y se repasan con
  una sesión de tarjetas programada por **FSRS-lite** (`docs/FSRS.md`).
- **Retención ≠ dominio, y está en el código.** El evento de repaso entra en la
  evidencia con **papel de retención** (`services/evidence.py`), no como prueba de
  competencia: recordar tarjetas no puede subir la matriz de destrezas.
- **Los packs de vocabulario son contenido versionado.** Estaban en
  `backend/data/vocab_packs/` (**ignorado por git**), así que el contenido se
  habría quedado **fuera del repositorio y de la release**; pasan a
  `backend/curriculum/vocab_packs/`. Se descubrió al verificar la release.
- **El alta de perfiles desde la LAN deja de estar abierta.** `POST /api/users`
  exige **loopback**: hasta V3.76 **cualquier equipo de la red podía crear perfiles**
  en la BD del alumno. El primer arranque en el propio equipo sigue igual y los
  tests visuales conservan su perfil `is_test`.
- **El borrado de un perfil deja de ser un clic irreversible.**
  **Desactivar** primero (sale del selector, no abre sesión: `403
  PROFILE_DISABLED`, evidencia intacta y reactivable) y **purgar** después como acto
  aparte, con **nombre exacto**, **snapshot ZIP previo** y la exigencia de que el
  perfil **ya esté desactivado**; si la copia falla, **no se purga**.
- **La administración de perfiles tiene doble candado.** `/api/admin/*` exige
  **loopback Y** PIN (`X-Admin-Pin`) y es **fail-closed**: sin PIN declarado está
  **deshabilitada**, no abierta. El PIN se puede **declarar y retirar** desde el
  lanzador, que es lo que faltaba para que el candado de V1.37 fuera real.
- **El webmaster tiene dónde trabajar.** Sección **«Perfiles»** en el lanzador:
  contador de pendientes con **refresco periódico**, aprobar/rechazar con nota, crear
  con PIN, desactivar/reactivar, purgar y **el estado del candado a la vista**.

### Sigue abierto (esto **no** lo cierra)

- **No hay autenticación de persona y el P0 sigue abierto.** Un perfil **sin** PIN
  entra sin credencial y **no hay identidad ni recuperación**; lo que cambia es que
  crear y borrar perfiles **ya no** es algo que cualquiera en la red pueda hacer.
  `[SEGURIDAD]`
- **Desactivar corta el acceso, no protege los datos.** La evidencia sigue en la
  BD hasta que se purgue; una sesión abierta de ese perfil recibe `403`. `[SEGURIDAD]`
- **Purgar es irreversible y la copia es la única red.** El ZIP **no está
  cifrado**: quien lo reciba tiene los datos, incluido el hash del PIN. `[SEGURIDAD]`
- **El PIN de administración es una credencial compartida, no por persona.** Quien
  lo sepa y esté en el equipo administra; no hay registro de quién aprobó qué más
  allá de la nota de la decisión. `[SEGURIDAD]`
- **Sin el lanzador delante nadie crea un perfil.** Es el precio declarado de no
  tener cuentas: la administración vive en la máquina. `[PRODUCTO]`
- **La decisión de fondo sigue abierta: ¿tendrá el producto cuentas?** Esta release
  responde «¿quién puede crear y borrar perfiles?», no «¿habrá cuentas?». Sigue
  contradiciendo «sin cuentas, sin contraseñas» de `docs/PREMISAS.md`. `[PRODUCTO]`
- **FSRS-lite no es FSRS.** Cuatro salidas y un planificador declarado, **sin** los
  parámetros por alumno que FSRS completo ajusta con el historial. El ítem «FSRS por
  tipo de memoria» **sigue aparcado** y no se ha tocado el scheduler más de lo
  necesario. `[MOTOR]`
- **Los packs por tema son tres** (comida, viaje, trabajo) y **no cubren un
  currículum**: son un punto de partida, no una biblioteca. `[CONTENIDO]`
- **No hay drills de producción por aspecto** sobre lo añadido al diccionario
  (sigue aparcado arriba, en «Motor»). `[MOTOR]`
- **El orden de publicación importa.** La retención léxica se publica **junto** al
  control de perfiles, no antes: escribe vocabulario personal en la BD de un perfil
  y no podía salir mientras cualquiera en la LAN pudiera crear perfiles.
  `[PRODUCTO]`
- **Los 7 gates siguen en `pending`** y el árbol que se certifica sigue siendo el de
  `v3.75.8`. `[VALIDACIÓN]`
- **El `dist` no se versiona** (`.gitignore`): hay que recompilar y reiniciar el
  backend para ver la UI nueva. `[OPERACIÓN]`

## V3.77.1 — el diccionario personal no puede morir por un campo que falta (2026-09-21)

> Origen: **el job `Playwright E2E (visual)` de CI, quince minutos después de
> publicar la V3.77.0.** Es un fallo **real de la release publicada** que los tests
> unitarios no podían ver por construcción: ninguna unidad se había pedido qué pasa
> con un **contrato incompleto**. Notas en `release-notes-v3.77.1.md`.

### Cerrado en V3.77.1 (deja de ser deuda)

- **Un campo que falta ya no tumba la pantalla del diccionario personal.**
  `AddVocabSection` guardaba `data.collections` sin comprobar la forma; con la
  respuesta sin ese campo, el estado quedaba en `undefined` y el `packs.filter` de
  la lista de temas **lanzaba al pintar**, lo que no rompe la lista sino el **árbol
  de React entero**. Ahora el estado se queda **siempre** con un array
  (`Array.isArray(data?.collections) ? … : []`) y los avisos de alta usan `?.` y
  `?? 0`. **Falla la lista, no la pantalla.**
- **La sonda de contrato queda formalizada, no tapada.** El `mockApi` de la spec
  sigue devolviendo **vacío** a lo que no conoce: era lo que destapaba el defecto.
  Se descartaron los dos atajos (mocked nuevos para poner el CI verde y aflojar el
  localizador) por la misma razón: **el mismo camino lo recorre un servidor que
  cambie el contrato**.
- **Candado con mordida comprobada.** `AddVocabSection.test.tsx` fija los tres
  casos y se verificó revirtiendo la línea: con el código anterior, el caso de la
  respuesta sin `collections` **falla**.

### Sigue abierto (esto **no** lo cierra)

- **La fragilidad del arnés visual bajo carga en Windows sigue aparcada** (§V3.75.2)
  y **no** es lo que falló aquí: en local, la tanda completa volvió a dar fallos en
  specs que esta release **no toca**, mientras que `drillProvenance` pasa aislado.
  La autoridad sigue siendo el CI. `[R]`
- **La sonda es oportunista, no sistemática.** Que el harness destapara este defecto
  fue **suerte con método**: no hay ninguna prueba que recorra *todas* las respuestas
  del producto con la forma vacía. Un defecto del mismo tipo en una pantalla que
  ninguna spec visita seguiría sin verse. `[VALIDACIÓN]`
- **Ningún invariante exige «una respuesta completa» en el cliente.** La defensa de
  cada componente es local; no hay un tipo/validador compartido que convierta
  «contrato incompleto» en un error visible en vez de en un render raro o vacío.
  `[PRODUCTO]`

## V3.77.2 — el endurecimiento del diccionario personal (2026-09-22)

> Origen: **una auditoría externa sobre el tag `v3.77.1`**, que reprodujo lo que la
> release anterior decía haber cerrado y encontró que **el padre tenía el mismo
> defecto sin arreglar** (H4) y que faltaba una pieza que ninguna release note
> mencionaba: **un `ErrorBoundary`**. A eso se sumó un **P0 de backend** que no
> venía de la UI. Notas en `release-notes-v3.77.2.md`.

### Cerrado en V3.77.2 (deja de ser deuda)

- **El invariante compartido que V3.77.1 declaró abierto ahora existe**
  (`[PRODUCTO]` de §V3.77.1: «ningún invariante exige una respuesta completa en el
  cliente»). `frontend/src/api/normalize.ts` normaliza **por contrato** y se aplica
  en la frontera de API **y** en los componentes. Cierra el caso concreto que
  V3.77.1 dejó abierto: `PersonalDictionary` guardaba `setLexicon(data)` /
  `setCandidates(drill.words)` sin comprobar la forma, así que un contrato
  incompleto mataba **la pantalla del diccionario y a sus tres hijos**, incluido el
  `AddVocabSection` que V3.77.1 ya había parcheado. **Parcial, ver abajo.**
- **El `ErrorBoundary` que no existía.** Un `throw` en render desmontaba el árbol
  entero. Ahora hay dos radios (`app` en `main.tsx`, `route` en el `Workspace`) y
  un panel de recuperación i18n. **Este era el multiplicador de radio**, no el
  defecto: es lo que hacía que un campo que faltaba dejara al alumno en blanco.
- **Las hermanas del mismo defecto.** `ReviewQueueSection` usaba
  `queue?.items ?? []` (**más débil** que el `Array.isArray(...)` de
  `AddVocabSection`: deja pasar un `items` truthy que no sea array),
  `DictionaryLookup` guardaba `entry` sin normalizar y `wordDrill`/`wordDrillSteps`
  hacían `.map` sobre `options` sin guardia.
- **El spinner infinito de `userId === null`.** `refresh()` salía temprano y
  `lexicon` se quedaba en `null` para siempre, así que la vista giraba sin pedir
  nada. Ahora pide elegir perfil.
- **El cierre de sesión de retención no se veía nunca.** El camino de fin llamaba a
  `load()` y reseteaba `index`/`done`: el resumen no aparecía jamás.
- **El doble `h1` del diccionario.** `DictionaryScreen` es dueño del layout y
  `PersonalDictionary` lo repetía. Candado nuevo que monta el componente **real**:
  `DictionaryScreen.test.tsx` mockea la vista, así que podía verificar que la
  pantalla monta pero **no** que haya un solo `h1`.
- **La mordida, comprobada revirtiendo.** Guardia neutralizada → los **3** tests de
  seguridad fallan (y el de la colección inexistente con un
  `sqlite3.IntegrityError` sin capturar, es decir un **500** en mitad de la
  escritura); `normalizeLexicon`/`normalizeDrillCandidates` hechos passthrough →
  el test del componente **muere en `PersonalDictionary.tsx:130`, en render**, el
  mismo sitio que describe el hallazgo.

### Sigue abierto (esto **no** lo cierra)

- **La normalización es un contrato de FORMA, no de SIGNIFICADO.** Un léxico
  incompleto ya no tumba la pantalla pero **se degrada al estado vacío**: un fallo
  **silencioso** donde antes había uno **ruidoso**. Lo que lo mitigaría es
  distinguir «vacío porque no hay» de «vacío porque no entendí»; hoy `loadError`
  solo cubre el fallo de red, no el contrato raro. Intercambio declarado a
  propósito, y **deuda**, no cierre. `[PRODUCTO]`
- **La sonda sigue siendo oportunista, no sistemática** (§V3.77.1). No se ha añadido
  ninguna prueba que recorra *todas* las respuestas del producto con la forma
  vacía: el `normalize.ts` cubre las pantallas que se han tocado, no «cualquier
  contrato de cualquier endpoint». `[VALIDACIÓN]`
- **La suite visual no se ha corrido en local para esta release** (la autoridad es
  el CI). Añadido a eso: los botones nuevos de «Repasar» usan `aria-expanded` y
  **no** `aria-pressed` **a propósito**, porque `drillProvenance.spec.ts` localiza
  la entrada al drill con `li:has(button[aria-pressed]) button[aria-pressed]`; que
  eso no rompa la spec **lo tiene que confirmar el CI**. `[R]`
- **La fragilidad del arnés visual bajo carga en Windows sigue aparcada**
  (§V3.75.2), igual que en V3.77.1. `[R]`
- **El P0 de identidad sigue abierto** (`docs/audit/PLAN-P0-IDENTIDAD.md`): esta
  release cierra **una** autorización que faltaba en **dos** endpoints, no el
  modelo de identidad. `[PRODUCTO]`

## V3.78.0 — el diccionario en tres modos y la única superficie de estudio (2026-09-22)

> Origen: **una petición del gerente sobre la app en uso**, no una auditoría.
> «Piensa si tal vez estaría mejor tener tres modos, no dos: CONSULTA, PERSONAL y
> FLASHCARDS en este orden. El segundo se trata de ver las palabras aprendidas en
> toda la APP y practicar con ellas. El tercero, copia de la app Anki: tarjetas
> personalizables de control absoluto.» De ahí salieron las dos decisiones que
> gobiernan la release: alcance **Anki-lite** (sin plantillas, cloze ni
> import/export) y **una sola superficie de estudio** —Personal gestiona,
> Flashcards estudia—. Notas en `release-notes-v3.78.0.md`.

### Cerrado en V3.78.0 (deja de ser deuda)

- **El diccionario tenía dos pestañas y una de ellas estudiaba.** PERSONAL
  incrustaba una sesión de repaso y «Mis listas»/packs abrían otra acotada a su
  colección: dos superficies de calificación para el mismo motor, con el mismo
  gesto. Ahora hay **una** (`Flashcards`) y PERSONAL es el inventario —buscador,
  filtro por estado, procedencia y fuerza de memoria por fila—, con un botón
  «Estudiar» que salta con el mazo ya elegido.
- **El dato que se guardaba y no se veía.** `vocabulary.source` (de dónde salió
  cada palabra) se guardaba desde V3.77.0 y ninguna pantalla lo mostraba, así que
  «¿de dónde salió esto?» era incontestable. Ahora es una columna filtrable de
  PERSONAL.
- **Las dos fuerzas que M4 separó, por fin visibles juntas.** El `recall`
  (derivado de la evidencia) y el estado del scheduler FSRS responden a preguntas
  distintas y hasta ahora solo se veía el primero. `GET /api/vocabulary/lexicon`
  gana `memory` por fila, calculado **puro** sobre una lectura de cartas: no
  añade conexiones.
- **El mazo «de toda la app» ya existía y no se podía usar.** `sync_fsrs_cards`
  siembra cartas `lexicon` desde toda la tabla `vocabulary`, que se puebla sola
  desde currículum, chat, speaking/writing/conversation/pronunciation y el drill.
  El mazo automático es una **vista** de eso (`id = 0`, virtual, no borrable), no
  una copia: no hay nada que sembrar ni que pueda quedar desincronizado.
- **El cierre de sesión de las tarjetas ahora es exacto.** Los límites diarios y
  las estadísticas salían de deducir «cartas con `last_review_at` de hoy», que no
  distingue nuevas de repaso ni cuenta repeticiones. El ledger
  `flashcard_reviews` (append-only) los hace **exactos**.
- **La deuda que el plan declaró y se cerró en el mismo commit:** sin excluir
  `flashcard` del panel autograduable, las tarjetas manuales se colaban en
  REVISAR. Se cerró con candado que muerde (verificado revirtiendo).

### Sigue abierto (esto **no** lo cierra)

- **La consulta del diccionario no alimenta el léxico, y ahora se nota más.** Es
  la invariante **D3** declarada en V3.77.0 y esta release **no** la toca: buscar
  «however» en Consultar **no** lo añade a PERSONAL. Con PERSONAL presentado como
  «las palabras aprendidas en toda la app», esa ausencia se lee como un hueco, y
  se declara como hueco **explícito**: cambiarlo exige decidir antes si consultar
  es estudiar, y eso es una decisión de producto, no un arreglo. Lo mismo vale
  para listening y reading, que tampoco pueblan `vocabulary`. `[PRODUCTO]`
- **El mazo automático y los manuales no son simétricos, y el automático es el
  peor parado.** No se renombra, no se borra, **no admite límites propios** (usa
  10 y 50) ni tarjetas escritas a mano —añadir a mano es lo que hacen las
  listas—. Es coherente con ser una vista del léxico, pero significa que
  «estudiar solo estas 20 palabras con tope 20» se consigue con una lista, no con
  un mazo. `[PRODUCTO]`
- **`FSRS-lite` sigue sin ser FSRS, ahora también para las tarjetas a mano.** Los
  intervalos salen de la versión simplificada y declarada de
  `domain/retention.py`, **sin** los parámetros por alumno que FSRS completo
  ajusta con el historial. Una tarjeta escrita a mano no recibe un plan mejor que
  una palabra del currículum: recibe el mismo. `[MOTOR]`
- **El ledger no distingue de dónde vino la calificación.** Una palabra del léxico
  calificada desde el endpoint viejo de retención cuenta como un repaso del mazo
  automático —deliberado: es lo que evita dos contabilidades— pero «repasos de
  hoy» incluye calificaciones hechas en otra pantalla. `[PRODUCTO]`
- **La migración es aditiva y no migra datos.** Las tres tablas nacen vacías y las
  palabras que ya existían **no tienen carta** hasta que alguien sincronice (lo
  que hace el propio mazo automático al abrirse). Una palabra sin carta sale como
  «sin estudiar», que es la lectura honesta de «no consta»; no se disimula con una
  fecha inventada. `[PRODUCTO]`
- **La tarjeta a mano guarda texto, no conocimiento.** Un anverso de 400
  caracteres y un reverso de 2000, sin comprobar que el reverso sea correcto ni
  que el anverso sea una pregunta. Es un bloc de notas con memoria, y se presenta
  como tal. `[PRODUCTO]`
- **Una sesión está topada en 100 tarjetas** (`QUEUE_MAX`, `limit ≤ 100`). No es
  una medida pedagógica, es defensiva: una sesión no debe convertirse en un
  atracón. `[PRODUCTO]`
- **El barrido visual completo no se corrió en local**, igual que en V3.77.2: la
  autoridad es el CI. Sí se corrieron las **dos** specs que tocan el diccionario, y
  `drillProvenance.spec.ts` **tuvo que cambiar** —entra explícitamente a «Personal»
  antes de buscar la entrada al drill, porque el defecto ya no es esa pestaña—.
  Esa spec localiza la entrada con `li:has(button[aria-pressed]) button[aria-pressed]`
  y la fila del léxico **conserva** ese botón. `[VALIDACIÓN]`

### Aparcado por decisión de alcance (Anki-lite, declarado)

- Tipos de nota personalizables con campos propios y **plantillas** frente/dorso;
  **cloze deletion**.
- **Importar/exportar** (CSV y `.apkg`), mazos filtrados, suspender/enterrar,
  **leech** y opciones avanzadas por mazo (pasos de aprendizaje, orden de las
  nuevas).
- Que la **consulta del diccionario** y listening/reading alimenten `vocabulary`
  (rompe la invariante D3 declarada; ver arriba).
- Mover `ReviewQueueSection`/`wordDrill`: son la superficie de **producción**, no
  la de tarjetas, y se quedan donde están.

## V3.79.0 — el perfil: el diálogo recortado y la baja «saturada» (2026-09-22)

> Origen: **el alumno usando la app**, no una auditoría. «Al editar un perfil, el
> cuadro de selección de icono se sale de pantalla por arriba. También al pulsar
> "PEDIR DAR DE BAJA MI PERFIL" sale en rojo: "El servidor local está saturado…"
> y no funciona.» Notas en `release-notes-v3.79.0.md`.

### Cerrado en V3.79.0 (deja de ser deuda)

- **El rate limiter medía rutas ajenas.** Una sola cola por equipo comparada
  contra el cupo de cada ruta: cinco peticiones cualesquiera agotaban el 5/min de
  `/api/profile-requests` y la baja del perfil devolvía 429 sin que nadie hubiera
  saturado nada. Ahora la ventana es por `(host, clase de ruta)`, con el prefijo
  **más largo** ganando (para que una ruta que es prefijo de otra no dependa del
  orden de escritura del diccionario) y **cupo propio para la baja**.
- **El diálogo de perfil no cabía en la pantalla.** La causa no era el CSS sino la
  contención: `backdrop-filter` en el `<header>` crea bloque contenedor para
  `position: fixed`, así que el `inset: 0` del backdrop medía la franja del header
  (~80 px) y no el viewport. Se cierra con un **portal a `document.body`**, más el
  endurecimiento del CSS que protege a los otros tres diálogos.
- **La baja gastaba su propio cupo a base de clics impacientes.** El botón se
  deshabilitaba solo tras el éxito; ahora hay estado `busy` y un 429 dice los
  segundos que faltan, usando el `Retry-After` que ya se recibía y se tiraba.

### Sigue abierto (esto **no** lo cierra)

- **Nada comprueba que un `position: fixed` no viva dentro de un ancestro con
  `transform`/`filter`/`backdrop-filter`/`contain`/`will-change`.** El caso del
  header se arregló para el diálogo de perfil y se revisaron a mano los otros
  tres, pero montar un diálogo nuevo dentro del header **vuelve a reproducir el
  recorte** y hoy ningún test lo impide. Un candado general sería caro; queda
  aparcado con el motivo escrito. `[UI]`
- **Los otros tres diálogos no se portalan** —no cuelgan del header y no sufren el
  problema—, así que la mitad de la protección es todavía «el CSS es correcto» y
  no «es imposible montarlo mal». `[UI]`
- **El `busy` es del cliente.** Evita el clic repetido, no es una clave de
  idempotencia del servidor; el 409 se sigue leyendo como «ya pedida». `[PRODUCTO]`
- **La fragilidad del arnés visual bajo carga en Windows sigue aparcada** (ver
  §V3.75.2 y V3.78.0): con el backend apagado el conjunto de specs de desktop que
  falla cambia de una ejecución a otra, y las mismas specs pasan en aislamiento
  sobre un árbol limpio. La autoridad es el CI. `[VALIDACIÓN]`

## V3.80.0 — Flashcards a fondo: la cara B, el mazo y los packs como mazos listos (2026-09-22)

> Origen: **el alumno usando la app**, no una auditoría. «En DICCIONARIO/FLASHCARDS
> no funciona muy bien. En ESTUDIAR al dar a "Mostrar respuesta" indica que "Aún no
> está en caché y no se muestra…". En MAZOS creo uno nuevo pero luego no sé cómo
> añadir palabras y empezar a practicar con ellas. También tal vez debería haber
> mazos predefinidos. Revisa bien cómo lo hacen las apps top.» Notas en
> `release-notes-v3.80.0.md`.

### Cerrado en V3.80.0 (deja de ser deuda)

- **La cara B vacía era un dato que no existía, no un fallo de pintado.** 139 de
  145 cartas del léxico del alumno sin traducción: `card_face` solo miraba el
  catálogo de packs (75 pares) y la caché (`dictionary_entries`, 9 filas), y
  `vocabulary` **no tenía columna de traducción** —el dato que `add_item`/`add_bulk`
  ya recibían se tiraba—. Ahora hay columna aditiva, **precedencia declarada**
  (alumno → pack → caché), `PATCH /api/vocabulary/items` para corregirla sin crear
  léxico, y la traducción del pack se guarda al inscribirse.
- **El mazo creado no era el que se editaba.** `CardsTab` tenía su propio `deckId`
  y arrancaba en `manual[0]`, no en el recién creado: ahora la selección es única
  y de la pantalla, crear un mazo salta a Tarjetas con el anverso enfocado y cada
  fila manual tiene «Añadir tarjetas».
- **No había forma de cargar tarjetas en bloque.** `POST .../cards/bulk` con el
  **mismo parser** que el léxico (`parse_bulk_lines`), en una transacción y con
  recuento real.
- **No había mazos con los que empezar.** Sección «Mazos listos» con los
  `theme_pack` globales: **Añadir** (materializa palabras + FSRS) o **Estudiar**
  el mazo automático filtrado por ese pack, sin copiar contenido.

### Sigue abierto (esto **no** lo cierra)

- **Copiar un pack a un mazo propio editable.** Hoy un pack se *añade* (sus
  palabras entran al léxico con su carta) o se *estudia* filtrado; no se puede
  tomar como base y quitarle o cambiarle palabras sin tocar el catálogo. Es lo que
  haría un usuario de Anki y **no está**. `[PRODUCTO]`
- **El mismo pack aparece en dos sitios**: en «Añadir» de PERSONAL (añadir a mi
  diccionario) y en «Mazos listos» de Flashcards (empezar a estudiar). La
  duplicación es **deliberada** y está declarada, pero consolidarla en una sola
  superficie con las dos acciones no se ha hecho. `[UI]`
- **Un mazo listo se estudia con los límites del mazo automático** (10 nuevas /
  50 repasos): no tiene fila de mazo donde guardar límites propios, así que no se
  puede decir «20 palabras al día solo de viajes». `[PRODUCTO]`
- **Ampliar el catálogo curado de packs** (más temas, más niveles): autoría de
  contenido, no de motor. `[CONTENIDO]`
- **Plantillas y campos propios, cloze, import/export `.apkg`/CSV, mazos
  filtrados, suspender/enterrar, leech y opciones avanzadas por mazo**
  (pasos de aprendizaje, orden de las nuevas). Es el resto de la lista de «lo que
  hacen las apps top» que el alumno pidió revisar: **aparcado entero**, no como
  deuda escondida. `[PRODUCTO]`
- **El reverso generado no se guarda como propio del alumno.** Vive en la caché
  del diccionario (`dictionary_entries`) y solo lo que **escribe** el alumno entra
  en `vocabulary.translation`: no se le atribuye un texto que no ha escrito, pero
  significa que el generado no se puede editar desde PERSONAL ni se conserva si la
  caché se vacía. `[PRODUCTO]`
- **La definición no es editable**, solo la traducción: el lápiz del estudio toca
  el reverso y la definición del modelo se conserva como apoyo. `[UI]`
- **La consulta del diccionario sigue sin alimentar el léxico** (invariante D3 de
  V3.77.0, no tocada): buscar una palabra no la añade a PERSONAL. Con PERSONAL
  presentado como «las palabras de toda la app», la ausencia se lee como hueco.
  `[PRODUCTO]`
- **El guardia `test_el_instrumento_no_escribe_en_data_ni_en_curriculum` es
  sensible al entorno**: compara mtime de todo `backend/data`, incluido
  `tutor.db`, así que **falla si el alumno tiene la app abierta** mientras corre
  la suite. No se ha tocado (acotarlo a `curriculum/` y a las rutas que el
  instrumento puede escribir debilitaría lo que protege, y hay que decidirlo con
  cuidado). Se declara medido: falló una vez con la app viva y pasó en la segunda
  pasada con la app ociosa. `[VALIDACIÓN]`

## V3.80.1 — Estabilización pre-freeze: la carrera cara B, el badge, la X, las pestañas, el `lang` y la cola del lanzador (2026-09-22)

> Origen: **la auditoría externa de V3.80.0**. Veredicto: la release está
> técnicamente bien planteada y soluciona problemas reales, pero **no se debe
> congelar todavía**: hay una carrera real en la UI (P1) y tres P2 de pulido. Esta
> release los cierra **sin añadir funcionalidad**, más un sexto hallazgo de **uso
> real** (una baja de perfil invisible en el lanzador) que era una promesa
> incumplida del lanzador, no del flujo del alumno. Notas en
> `release-notes-v3.80.1.md`.

### Cerrado en V3.80.1 (deja de ser deuda)

- **La carrera generación ↔ edición de la cara B (P1).** Una respuesta tardía de
  `hydrate()` podía pisar la traducción que el alumno acababa de guardar. Se
  cierra con token por tarjeta (`hydrationEpoch`) + espejo síncrono (`ownBacksRef`)
  y con retirar el spinner de esa tarjeta al guardar. Candado con promesa diferida.
- **El badge «Tu versión» sobre una traducción borrada (P2).** Guardar `""` ya no
  deja la tarjeta marcada como propia: se restaura la cara efectiva del backend
  (o se reintenta la caché).
- **La `X` del diccionario limpiaba el campo pero no el resultado (P2).** Ahora
  limpia búsqueda y resultado y devuelve el estado honesto de «nueva consulta».
- **La semántica ARIA de los dos selectores tipo pestaña (P2).** Los tres modos y
  las cuatro vistas son `tablist`/`tab`/`tabpanel` reales con roving tabindex y
  teclado (`useTabList`).
- **El `lang` de las tarjetas manuales (P2).** Solo se declara cuando el idioma se
  conoce (léxico); en las manuales se omite.
- **No había sonda visual permanente de Diccionario ni de Flashcards.** Se añaden
  `dictionarySmoke.spec.ts` y `flashcardsSmoke.spec.ts`, permanentes y en los tres
  breakpoints —el hueco que V3.80.0 había declarado—.
- **La cola de solicitudes de perfil no se veía en el lanzador si no había PIN,
  y una consulta fallida se pintaba como cola vacía.** Era una capacidad
  **declarada y no implementada** desde V3.77 («contar las pendientes sin depender
  del backend»). Se cierra con `status.read_pending_requests` (contador
  solo-lectura, `0` = vacía y `None` = no se pudo leer), `ui.pending_view` (los
  estados no se confunden; un fallo dice el motivo) y el reinicio automático al
  guardar o retirar el PIN, para que el backend en marcha lo aplique de verdad.

### Sigue abierto (esto **no** lo cierra)

- **El timeout de hidratación de la cara B sigue siendo el global de 120 s.** Un
  timeout **corto** específico de Flashcards (para no dejar el spinner eterno
  cuando el modelo está *lento* en vez de caído, y para fallar antes a «No consta»)
  queda aparcado: cambiar el timeout global afecta a toda la app y no es una
  estabilización. `[PRODUCTO]`
- **No hay idioma por mazo.** El `lang` de una tarjeta manual se omite porque no
  se conoce; una configuración de idioma por mazo (con su valor por defecto y su
  herencia) es funcionalidad nueva y queda aparcada. `[PRODUCTO]`
- **El mismo pack sigue listado en dos sitios** (PERSONAL para añadir, Mazos para
  estudiar). Sigue siendo la duplicación **declarada** de V3.80.0; no se consolida
  aquí. `[UI]`
- **El barrido visual completo sigue con flakiness local** cuando el arnés corre
  en paralelo sobre esta máquina: la tanda completa da **54 pasan / 2 fallan /
  28 omiten**, y los dos que fallan (`keyboard.spec.ts`, del hub de `/#/aprender`,
  y `resize.spec.ts`, del panel de conversaciones) **pasan en aislamiento con y
  sin los cambios de esta release**, y el conjunto que falla se mueve al repetir.
  La causa es del entorno —el Vite local proxea `/api` a un `:8000` que aquí sirve
  **HTTPS**—, y la autoridad del barrido completo sigue siendo el CI. Las dos
  specs nuevas son deterministas (mockean todo su `/api`) y dan **6/6 en los tres
  breakpoints**. `[VALIDACIÓN]`
- **Los mocks de `/api/**` deben anclarse al ORIGEN, no a globs por endpoint.**
  Aprendido al escribir los dos specs nuevos: `**​/api/settings*` casa también con
  el módulo de la app `/src/api/settings.ts` y, al servirle JSON, **la app no
  arranca**. Queda documentado en los dos specs y en `release-notes-v3.80.1.md`
  (la trampa ya estaba escrita en `drillProvenance.spec.ts`; sigue sin haber un
  helper compartido que la haga imposible de repetir). `[VALIDACIÓN]`
- **La cola de solicitudes sigue exigiendo PIN para leerse en detalle y
  resolverse.** Sin PIN, el lanzador ahora **cuenta y anuncia** las pendientes
  leyendo la BD en solo-lectura, pero ver la fila y aprobar/rechazar sigue detrás
  del doble candado (PIN + loopback). Es una decisión deliberada —**contar no es
  decidir**—, y lo que se cierra en (G) es la mentira («sin solicitudes» cuando
  había una), no el candado. `[PRODUCTO]`
- **La base de certificación se re-ancla a `v3.80.1`, pero G1–G7 siguen
  `pending`.** El pre-vuelo del nuevo árbol **no se ha ejecutado** (exige
  hardware): esta release solo mueve el ancla documental por tag (regla V3.73.5) y
  lo declara en `docs/audit/KIT-VALIDACION-GATES.md`. `[VALIDACIÓN]`
- **Todo lo declarado abierto en V3.80.0 sigue abierto** y no se toca aquí (copiar
  un pack a un mazo editable, límites propios por pack, plantillas/cloze/import,
  el reverso generado no editable desde PERSONAL, etc.).

## V3.81.0 — Gestión de usuarios: cuentas con contraseña, alta y baja autoservicio y la consola del lanzador (Fase 3 del P0) · 2026-09-23

> Release que publica **dos lotes**: la estabilización pre-freeze (preparada como
> `v3.80.1`) y **la Fase 3 del P0 de identidad**. Lo que sigue son **deudas
> declaradas**, no olvidos. Detalle en `release-notes-v3.81.0.md`.

### Cerrado en V3.81.0 (deja de ser deuda)

- **«Sin cuentas, sin contraseñas» deja de ser la premisa del producto.** `docs/PREMISAS.md`
  §13 se reescribe: la cuenta es local, con **nombre + email + contraseña**, y la
  premisa que sobrevive es «**sin cuentas en la nube**» (coherente con la 2). El
  briefing de §15 de `docs/audit/PLAN-P0-IDENTIDAD.md` queda **cerrado** con la
  decisión y su implementación en §16.
- **El PIN de perfil (V3.76) se retira como concepto.** `PUT /api/session/pin`
  desaparece, `services/pins.py` y `backend/tests/test_pin.py` se **borran** y
  `pin_hash` se conserva en la tabla **sin leerse** (borrar una columna de una BD
  viva es riesgo con cero beneficio). El relevo es `services/credentials.py`.
- **La contraseña de la cuenta sustituye al PIN**, con política de forma, freno
  de intentos **por cuenta** y **revocación efectiva** (época de autenticación:
  cambiar la contraseña o forzar la baja tumban las sesiones vivas al instante).
- **`GET /api/users` deja de filtrar correos.** Sigue enumerando **nombres** sin
  sesión (la puerta los necesita), pero el email de las demás cuentas se recorta
  en el borde HTTP. Era PII nueva sobre la única superficie sin sesión.
- **La mentira del lanzador sobre la cola de solicitudes (V3.80.1, apartado G)**
  se conserva cerrada y ahora la cola **es** la consola de Usuarios.

### Lo que sigue abierto o aparcado (deuda declarada)

- **Las cuentas heredadas sin credencial siguen entrando sin contraseña.** Es la
  deuda central de esta release: `password_hash == ''` abre como siempre para no
  dejar a nadie fuera de sus datos, así que **el P0 sigue abierto para esas
  cuentas**, no para el producto. La consola de Usuarios las lista como tarea
  pendiente; llevarlas a cero es trabajo de uso, no de código. `[PRODUCTO]`
- **No hay recuperación de contraseña por correo.** La restablece el webmaster
  desde la consola y la entrega como **temporal** (`must_change_password`, que el
  servidor hace cumplir con `403 PASSWORD_CHANGE_REQUIRED`). Un flujo de
  «olvidé mi contraseña» con token por email exigiría decidir la caducidad y el
  freno del propio flujo: funcionalidad nueva, no estabilización. `[PRODUCTO]`
- **No hay segundo factor** (TOTP, passkeys) ni **verificación obligatoria** para
  usar la app: el email es una **señal**, y sin SMTP configurado la verificación
  la firma el webmaster a mano. `[PRODUCTO]`
- **`GET /api/users` sigue enumerando nombres en modo LAN.** Es consecuencia
  declarada del diseño de selector (Netflix-style) y lo que la acota es que cada
  cuenta con credencial **no entra** sin su contraseña. Quien quiera cerrar
  también los nombres tiene la vía del modo LAN con solicitudes. `[PRODUCTO]`
- **El hash de la contraseña viaja en el backup** (es estado de la cuenta, dentro
  de la BD); `session.secret` y `mail.secret` **no**. Quien reciba un backup puede
  atacar la contraseña **fuera de línea**, sin el freno del servidor. `[SEGURIDAD]`
- **El freno de intentos vive en memoria del proceso**: un reinicio lo vacía. Es
  el mismo límite declarado del PIN en V3.76. `[SEGURIDAD]`
- **La verificación por email depende de SMTP.** Sin él la app funciona igual y la
  UI lo dice con esas palabras («no hay correo configurado, pídele al webmaster
  que lo confirme»); prometer un envío que no existe sería la peor clase de
  mentira: la que hace esperar. `[PRODUCTO]`
- **La consola de Usuarios sigue detrás del doble candado** (PIN de administración
  + loopback). Sin PIN se **cuenta** la cola leyendo la BD, pero ver el detalle,
  resolver, editar, forzar una baja o purgar exige PIN. `[PRODUCTO]`
- **La purga exige que la cuenta esté dada de baja o desactivada**, hace copia
  previa y pide confirmación por nombre. No hay purga «a un clic» y es deliberado.
  `[PRODUCTO]`
- **El transporte del correo no está probado contra un servidor real** en esta
  máquina: los candados cubren el modo fail-closed, la negociación STARTTLS/TLS
  implícito y la autenticación con y sin contraseña, pero una prueba contra un
  SMTP de verdad (y contra un proveedor que exija OAuth en vez de contraseña de
  aplicación) queda **pendiente de acción humana**. `[VALIDACIÓN]`
- **La prueba manual end-to-end se hizo sobre una COPIA de la BD real**, no sobre
  la BD en uso (el gerente lo pidió así), y quedó **reproducible**: el guion
  `backend/scripts/e2e_accounts_v381.py` copia la BD a un temporal, levanta el
  backend de verdad y recorre el contrato entero (**62/62 pasos**, con el sha256
  de la BD original comprobado al final). Queda pendiente repetirla sobre la BD de
  uso el día que se actualice el equipo de verdad. `[VALIDACIÓN]`
- **La base de certificación se re-ancla a `v3.81.0`, pero G1–G7 siguen
  `pending`.** El pre-vuelo del nuevo árbol sigue **sin ejecutarse** (exige
  hardware): esta release solo mueve el ancla documental por tag (regla V3.73.5) y
  lo declara en `docs/audit/KIT-VALIDACION-GATES.md`. `[VALIDACIÓN]`
- **Todo lo declarado abierto en V3.80.0 y V3.80.1 sigue abierto** y no se toca
  aquí (timeout corto de hidratación, idioma por mazo, el pack listado en dos
  sitios, la duplicación de plantillas/cloze/import, etc.).

## V3.81.2 — Cierre de G0: identidad y ciclo de vida de cuentas · 2026-09-23

> Parche de privacidad y de cierre de fase sobre V3.81.x (publicado como
> `v3.81.2`). **SIN** cambio de contrato de API y **SIN** migración de columnas:
> todo es **aditivo y no destructivo** en SQLite. Detalle en
> `release-notes-v3.81.2.md`.

### Cerrado en V3.81.2

- **El historial ya no guarda el correo.** `user_events` sobrevive a la purga a
  propósito —responde «¿quién borró esta cuenta y por qué?»—, pero deja de ser
  una copia histórica de PII: las notas de alta, credenciales, edición y
  verificación registran el **hecho administrativo**, no el email.
- **Se redacta lo ya guardado.** Una migración de arranque en `init_db()`
  sustituye cualquier correo de las notas por `(email)`, y al purgar una cuenta se
  redactan también sus notas antes de borrar la fila de `users`: **después de la
  purga no queda PII** en el historial que sobrevive.
- **`EVENT_PURGED` se registra solo si la purga ocurrió.** Se invierte el orden
  —borrar y **después** registrar—, así no puede quedar escrito «datos purgados»
  sin haber purgado nada.
- **El E2E de cuentas recorre la migración heredada entera.** El guion siembra una
  cuenta sin credencial en la copia y la lleva hasta `without_password = 0`: alta
  de credenciales temporales, login, bloqueo por cambio obligatorio, cambio,
  cookie anterior tumbada (`SESSION_STALE`), login con la definitiva y datos
  intactos. Incluye la comprobación de que el historial post-purga no tiene PII.

### Deuda que sigue abierta (y ahora es candado de V4.0)

- **Marcador de historicidad del recuento de gates.** Las entradas **fechadas** de
  este documento (y las de `docs/audit/KIT-VALIDACION-GATES.md`, y las notas de
  release de la serie V3.73–V3.80) dicen «**7** gates» y **es correcto para su
  fecha**: son el registro de entonces y no se reescriben. La cifra **vigente** es
  **8** (`G0 · identidad-cuentas`, `V3.81.2`) y `status --strict` exige **8/8**. Un
  «7» **solo** es hallazgo si aparece en una sección **sin fecha**. `[VALIDACIÓN]`

- **La transición de las cuentas heredadas se cierra con un candado, no con
  código.** Se mantiene la compatibilidad (`password_hash == ''` sigue entrando)
  y se añade el gate **G0 · `identidad-cuentas`**: `status --strict` exige ahora
  **8/8** gates y G0 **no** puede declararse en `pass` mientras
  `without_password > 0`. Es el cierre real del P0 de identidad: llevar el
  contador a cero es trabajo de uso (asignar credenciales a cada cuenta heredada
  desde la consola), no de código. **Hoy la BD de uso de este equipo tiene 3
  cuentas sin credencial** (`J.A` ×2 y `Paz`), así que **G0 queda `pending`** y
  V4.0 no puede declararse hasta que ese contador llegue a cero. `[PRODUCTO]`
- **En la BD de uso no había PII que limpiar** (`user_events` tiene 0 filas): el
  hallazgo de esta release era un **riesgo de código**, no un dato ya expuesto, y
  se declara así para no vender como «limpieza de datos» lo que fue «cierre de una
  vía». La migración de arranque existe para las instalaciones que **sí** grabaron
  correos. `[PRIVACIDAD]`
- **El historial sigue guardando el nombre del sujeto** (`subject_name`), y es
  deliberado: sin él, «¿a quién se purgó?» no tiene respuesta, y un nombre no es
  por sí solo un identificador de contacto. Seudonimizarlo también sería una
  decisión de producto, no una corrección. `[PRIVACIDAD]`
- **La redacción por regex es un patrón, no un analizador:** un correo con formas
  exóticas (comentarios RFC, corchetes, partido por saltos de línea) podría no
  casar. Se acepta a propósito, porque la garantía fuerte es **dejar de escribir el
  correo**, no redactar. `[PRIVACIDAD]`
- **Fuera de alcance de este parche (declarado):** política de contraseña
  (mínimo corto y la afirmación de «miles de años» en la documentación), freno de
  intentos en memoria y limpieza global de la terminología perfil/usuario. Siguen
  como deuda. `[SEGURIDAD]` `[PRODUCTO]`

## V3.82.0 — Alta profesional de cuentas: solicitud autorizada, invitación, entrada por email y recuperación · 2026-09-24

> Release que **cierra el P0 de identidad para las cuentas activas** y publica
> **un cambio incompatible de contrato** (`SessionCreate` pasa de `user_id` a
> `email` + `password`), coordinado en el mismo lanzamiento entre backend,
> frontend, lanzador y sus tests. Todas las columnas nuevas son **aditivas**. Lo
> que sigue son **deudas declaradas**, no olvidos. Detalle en
> `release-notes-v3.82.0.md`.

### Cerrado en V3.82.0 (deja de ser deuda)

- **El alta sin autorización.** `POST /api/users` (registro autoservicio en
  loopback) se **retira**: una cuenta nace de una **solicitud** que el webmaster
  autoriza, o de un alta directa desde `/api/admin/users` cuando tiene a la
  persona delante. El formulario de solicitud captura **email y avatar**, así que
  aprobar no exige teclear nada.
- **Aprobar no mandaba nada.** Ahora crea la cuenta **con los datos solicitados**,
  emite un **token de activación** (7 días) y manda la **invitación**; y devuelve
  el enlace en claro una única vez para poder entregarlo **a mano** sin SMTP
  (`POST /api/admin/users/{id}/resend-activation` lo reemite).
- **No había recuperación de contraseña por correo.** Flujo estándar: `POST
  /api/account/forgot-password` (responde **200 siempre**, sin revelar si el correo
  tiene cuenta, con cupo de 5/min por IP) + `POST /api/account/reset-password`
  (token de un solo uso, caducidad de 1 hora, sube la época de autenticación y
  tumba las demás sesiones).
- **El enlace de verificación estaba roto.** El mailer lo enlazaba a
  `/#/cuenta/verificar?token=…` desde V3.81 y esa ruta **no existía** en el
  frontend: pulsarlo caía en Inicio y no confirmaba nada. La ruta y su página
  existen ahora, junto con `cuenta/activar` y `cuenta/restablecer`.
- **Las cuentas heredadas entraban sin contraseña** (`password_hash == ''` abría
  sesión). Ahora responden **403 `ACCOUNT_NOT_ACTIVATED`**. `without_password` deja
  de ser un agujero y pasa a ser **contador operativo** de trabajo pendiente, así
  que G0 ya no vigila un agujero abierto sino una cola de tareas.
- **`GET /api/users` enumeraba cuentas sin sesión.** Pasa a exigir sesión: la
  puerta ya no pide la lista (entra por email), así que el catálogo de a quién
  intentar entrar deja de publicarse.

### Lo que sigue abierto o aparcado (deuda declarada)

- **No hay segundo factor** (TOTP, passkeys) ni **verificación obligatoria** para
  usar la app: el email es una **señal**. `[PRODUCTO]`
- **La entrega del correo depende de que el webmaster configure SMTP.** Sin él,
  invitación y restablecimiento **no se pierden** (el enlace se entrega a mano
  desde el lanzador o desde la pantalla) pero el flujo deja de ser autoservicio de
  verdad, y la UI lo dice con esas palabras en vez de prometer un correo que no ha
  salido. `[PRODUCTO]`
- **Los tokens de activación y restablecimiento viven en columnas de `users`**
  (`activation_token_hash`, `password_reset_token_hash`), **hasheados** y con
  caducidad, pero sin historial: emitir uno nuevo **anula el anterior** sin dejar
  rastro de cuántos se emitieron. `[SEGURIDAD]`
- **El *plus-addressing* es una dependencia del proveedor de correo.** `J.A` y
  `Paz` comparten bandeja con `josealberto.vel+ja@…` y `josealberto.vel+paz@…`
  porque Gmail y Outlook soportan `+`. Un proveedor que no lo soporte obligaría a
  usar correos distintos, y la migración heredada dejaría de poder hacerse así.
  `[PRODUCTO]`
- **El cupo de recuperación es por IP y por proceso** (5/min en
  `security._PATH_LIMITS`): un reinicio lo vacía y una red con una sola salida
  comparte cupo. Es el mismo límite declarado del freno de contraseña. `[SEGURIDAD]`
- **No hay cuenta atrás ni aviso al usuario cuando se emite un restablecimiento**:
  quien tenga acceso al correo puede pedirlo sin que el titular se entere hasta que
  llegue (o no llegue). Un aviso «se pidió cambiar tu contraseña» es la mejora
  natural y no está. `[PRODUCTO]`
- **Sin perfil de cobros ni nada económico** (a petición expresa del gerente): la
  estructura del alta es la que necesitaría un uso público —solicitud,
  autorización, estado de la cuenta, recuperación— pero no hay planes, facturación
  ni límites por tipo de cuenta. `[PRODUCTO]`
- **El hash de la contraseña sigue viajando en el backup** (es estado de la
  cuenta, dentro de la BD); `session.secret` y `mail.secret` **no**. Quien reciba un
  backup puede atacar la contraseña **fuera de línea**, sin el freno del servidor.
  `[SEGURIDAD]`
- **La migración heredada de este equipo quedó preparada, no ejecutada sobre la BD
  en uso**: `backend/scripts/migrate_legacy_accounts.py` es idempotente y simula por
  defecto (`--apply` escribe, con copia previa), y `J.A` y `Paz` siguen
  «pendientes de activación» hasta que se ejecute de verdad. G0 sigue `pending` por
  eso, no por código. `[VALIDACIÓN]`
- **La prueba manual end-to-end se hizo sobre una COPIA de la BD**, como en V3.81.2;
  repetirla sobre la BD de uso queda pendiente de acción humana. `[VALIDACIÓN]`
- **Todo lo declarado abierto en V3.81.x sigue abierto** salvo lo que esta release
  cierra de forma explícita arriba (no hay recuperación por correo, las cuentas sin
  credencial no entran, `GET /api/users` no es público y el registro autoservicio no
  existe).

## V3.83.0 — Diccionario → Flashcards y sesión de estudio tipo juego · 2026-09-24

> Release **SOLO FRONTEND** que hace visible el vínculo Diccionario → Flashcards →
> PERSONAL y rediseña la sesión de estudio. **SIN migración, SIN endpoints nuevos y
> SIN cambio de contrato**: reutiliza `POST /api/vocabulary/items`,
> `GET /api/vocabulary/collections`, los mazos y la cola FSRS. Lo que sigue son
> **deudas declaradas**, no olvidos. Detalle en `release-notes-v3.83.0.md`.

### Cerrado en V3.83.0 (deja de ser deuda)

- **El vínculo «todo uno» existía pero no se veía.** El botón «Añadir a Personal»
  pasa a **«Añadir a Flashcards»** y abre un panel que declara qué significa el
  alta: la palabra queda en **aprendizaje**, aparece en **Personal** y en el mazo
  automático **«Mi diccionario»**, y se repasa con FSRS. El alta sigue siendo el
  **mismo** `addVocabularyItem` de siempre: no hay copia ni segundo vocabulario.
- **No se ofrecía estudiar desde el diccionario.** El panel cierra con **«Estudiar
  en Flashcards»**, que salta al modo de estudio de la propia pantalla.
- **Una palabra ya rastreada se podía «añadir» otra vez.** Si `usage.tracked` es
  cierto, no se ofrece un alta que no cambiaría nada: se declara «Ya está en tu
  diccionario» y se ofrece estudiar.
- **No se podía archivar en una lista desde el diccionario.** Selector opcional con
  las listas **propias** (`user_list`), cargado de forma perezosa; el alta entra con
  `collection_id`.
- **La barra de progreso no se anunciaba.** `components/ui/progress.tsx` no
  reenviaba `value` a la raíz de Radix, así que no pintaba `aria-valuenow`: se veía,
  no se oía. Se reenvía.
- **La sesión se veía como un formulario.** Volteo **3D** real (dos caras),
  **barra de progreso**, notas con **icono + color semántico + atajo 1–4** y cierre
  con **celebración** que declara el **acierto de la sesión** (grados ≥ 3).

### Lo que sigue abierto o aparcado (deuda declarada)

- **No hay gamificación de datos**: ni XP, ni niveles, ni rachas. El «juego» es
  visual y de movimiento, **a propósito**. `[PRODUCTO]`
- **El acierto del resumen es de la sesión**, no una nota de dominio (D5/E3): dice
  cuántas de las tarjetas repasadas fueron Bien o Fácil, nada más. `[PRODUCTO]`
- **Crear una lista desde el diccionario no se ofrece**: el panel solo elige entre
  las que ya existen; para crear una hay que ir a Añadir/packs. Es una limitación
  declarada, no un olvido. `[PRODUCTO]`
- **El volteo 3D y la celebración se apagan con `prefers-reduced-motion`**: la
  información no cambia, pero quien reduzca movimiento no ve la animación. `[UX]`
- **El alta sigue dependiendo del modelo/backend para el reverso** (léxico al día
  siguiente): nada nuevo, pero tampoco se mejora aquí. `[PRODUCTO]`
- **`frontend/dist` no se reconstruyó en esta release**: el artefacto compilado es
  anterior a v3.82.0/v3.83.0 hasta que se ejecute `npm run build` y se vuelva a
  validar el origen de producto. `[VALIDACIÓN]`
- **Los 8 gates humanos siguen `pending`** (incluido **G0**, que depende de ejecutar
  la migración heredada: acción del gerente, no del agente). `[VALIDACIÓN]`
- **Todo lo declarado abierto en V3.82.0 y anteriores sigue abierto** salvo lo que
  esta release cierra de forma explícita arriba.

## V3.83.1 — Instrumento y honestidad: la versión que el informe `AU` pedía y que no existía · 2026-09-24

> Release **DE INSTRUMENTO Y HONESTIDAD (patch)**, SIN producto nuevo: `frontend/src`
> y `launcher/` intactos; el único cambio en `backend/` es la línea de `VERSION`. Existe
> porque **la versión que se estaba auditando no existía** (la última etiqueta era
> `v3.83.0` y el arreglo H2 vivía en `main` sin etiqueta). Publica el parche que
> `docs/audit/AU-AUDITORIA-TOTAL-V383.md` §8 pidió. Detalle en
> `release-notes-v3.83.1.md` y `docs/audit/CIERRE-GLOBAL-V383.md`.

### Cerrado en V3.83.1 (deja de ser deuda)

- **H2 — el gate `reduced-motion` que emulaba en vacío.** `test.use({ reducedMotion:
  "reduce" })` no es opción válida en Playwright 1.62 y se ignoraba en silencio desde
  `V3.73.1`, así que `GUI-05` pasaba **sin emular nada**. Ahora emula de verdad
  (`page.emulateMedia`) y lleva **guarda de mordida** (`matchMedia(...).matches ===
  true`): si alguien vuelve a un arnés que no muerde, el test **falla**.
- **E5/i — la contradicción literal de la letra.** `release-notes-v3.83.0.md §5.1`
  («No se toca ni el backend ni la BD») queda como «sin lógica de backend (solo el bump
  de `VERSION`) y sin tocar la BD», que es lo que el diff dice.
- **H4 — el cambio de arnés ya tiene tag.** `fd086e8` (`playwright.config.ts`) queda
  **dentro** de `v3.83.1`, así que se cierra la observación de `AU` §5-H4.
- **El ancla reproducible existe.** El tag `v3.83.1` (`4ee32e5`) es el último y su
  commit es el tip de `main`; su run de CI (`36042834375`, `success`) lo certifica.

### Sigue abierto o aparcado (deuda declarada)

- **H1 sigue vivo en el código** y **no se endurece aquí.** `_collection_writable`
  (`backend/domain/retention.py` ~185) devuelve `True` para un pack global (`not
  owner`): la promesa «un pack curado no es un destino» sigue siendo **solo de
  cliente**. Se **sitúa fuera** de un patch de instrumento y queda como **deuda
  aceptada `P2`** en `AU §12`, con la recomendación viva
  (`return bool(owner) and owner == user_id`). Mientras siga en el código, sigue
  declarada. `[SEGURIDAD]` `[PRODUCTO]`
- **H5 (`add_item` no atómico) sigue abierto.** Un fallo posterior a `seed_study_items`
  puede pintar «No se pudo añadir» cuando la palabra **ya está** en el léxico: el modo
  de fallo es del lado seguro, pero el **mensaje** miente sobre el estado. `[PRODUCTO]`
- **H3 (`Sparkles` celebra también el 0 %) sigue abierto** como `P3` cosmético. `[UX]`
- **Los 8 gates humanos siguen `pending`** y `docs/audit/validation-evidence.json`
  **no existe**. `[VALIDACIÓN]`
- **El ancla de certificación estaba desfasada y este cierre la mueve a `v3.83.1`.**
  El kit (`docs/audit/KIT-VALIDACION-GATES.md`) y el runbook
  (`docs/audit/VALIDATION-RELEASE-V373.md`) ya declaran la re-congelación; el pre-vuelo
  hay que **repetirlo** sobre este árbol. `[VALIDACIÓN]`
- **El informe `AV` del arco `v3.81.2..v3.82.0` (contrato + migración) sigue
  pendiente** aunque su encargo existe (`agentes/auditoria-total-externa-v382.md`). Es
  la mayor deuda de auditoría de la serie. `[AUDITORÍA]`
- **Los 12 PRs de Dependabot siguen abiertos** (`#7`–`#18`); `#10` y `#13` siguen
  rojos y los diez restantes sin dictaminar. `[MANTENIMIENTO]`
- **`frontend/dist` puede estar desfasado** respecto a `3.83.1` (no se reconstruyó);
  `check_dist_artifact` solo comprueba que el `index.html` sea servible. `[VALIDACIÓN]`
- **Todo lo declarado abierto en V3.83.0 y anteriores sigue abierto** salvo lo que esta
  release cierra de forma explícita arriba.

## V3.84.0 — Responsive global, mazos estándar y ruta de aprendizaje · 2026-09-25

> Release **DE PRODUCTO (minor)** con backend y frontend, **SIN migración de BD**
> (los packs se siembran solos por `slug` desde `backend/curriculum/vocab_packs/*.json`)
> y **SIN endpoints nuevos** (mazos, tarjetas y `collection_id` ya existían). Detalle en
> `release-notes-v3.84.0.md`.

### Cerrado en V3.84.0 (deja de ser deuda)

- **El recorte del botón «Practicar esta palabra»** en DICCIONARIO/CONSULTAR y **su
  clase**: clusters sin `flex-wrap` dentro de contenedores con `overflow-hidden`
  (cluster de la `ResultCard`, conmutador de 5 peldaños de `wordDrill`, `Header`,
  cabecera y caras de `StudySession`, filas de `FlashcardsScreen`, pestañas de
  `DictionaryScreen` y filas con `shrink-0` de `AddVocabSection`/`PersonalDictionary`).
  `[UX]` `[RESPONSIVE]`
- **No había guardia contra el recorte silencioso.** Nuevo
  `frontend/tests/visual/layoutHelper.ts` (`expectNoHorizontalOverflow` +
  `expectInsideClippingAncestor`) y `responsiveOverflow.spec.ts`: 11 rutas y las 3
  pestañas del diccionario a 390/768/1280 y a **320 px**, más la regresión del botón en
  `dictionarySmoke.spec.ts`. `[VALIDACIÓN]`
- **El diccionario no dejaba elegir destino.** El panel de alta ofrece ahora
  **mazo manual** (elegir / `Crear mazo nuevo…` en línea) y crea la tarjeta con
  `createFlashcard`, además del léxico + carta FSRS de siempre; «Estudiar en Flashcards»
  abre **ese mazo**. `[PRODUCTO]`
- **Solo había 3 packs de ~25 palabras.** Ahora **15 packs de 40–60** (12 nuevos + 3
  enriquecidos), con test de contenido `test_vocab_packs_content.py`. `[CONTENIDO]`
- **El mazo automático no se podía filtrar.** Gana el filtro Todas / por pack / por
  lista, reutilizando el `collection_id` que la cola ya soportaba. `[PRODUCTO]`

### Sigue abierto o aparcado (deuda declarada)

- **El alta en un mazo manual DUPLICA el ítem**: la palabra queda en el léxico/«Mi
  diccionario» **y** como tarjeta manual del mazo. Es el precio de no compartir el
  modelo de tarjetas; se declara en la UI y consolidarlo queda aparcado. `[PRODUCTO]`
- **Archivar en listas desde el panel del diccionario se retira.** Las listas siguen
  existiendo y se crean desde PERSONAL; el destino del diccionario pasa a ser el mazo
  elegido. `[UX]`
- **El contenido de los packs es autoría acotada** (~650 entradas nuevas): el test
  garantiza forma, `slug` único y 40–60 ítems, **no** calidad léxica. `[CONTENIDO]`
- **320 px es un ancho nuevo** que la suite no probaba y reveló más defectos de los
  enumerados; los encontrados se cerraron, pero el ancho entra en la guardia desde
  ahora. `[RESPONSIVE]`
- **H1 sigue vivo en el código** (`_collection_writable` devuelve `True` para un pack
  global, `backend/domain/retention.py` ~185; **deuda aceptada `P2`** en
  `AU §12`). `[SEGURIDAD]` `[PRODUCTO]`
- **H5 (`add_item` no atómico) y H3 (`Sparkles` celebra también el 0 %) siguen
  abiertos.** `[PRODUCTO]` `[UX]`
- **Los 8 gates humanos siguen `pending`** y `docs/audit/validation-evidence.json`
  **no existe**; el ancla de certificación sigue en `v3.83.1`. `[VALIDACIÓN]`
- **El informe `AV` del arco `v3.81.2..v3.82.0` sigue pendiente.** `[AUDITORÍA]`
- **Los 12 PRs de Dependabot siguen abiertos** (`#7`–`#18`). `[MANTENIMIENTO]`
- **`frontend/dist` se reconstruyó** en esta release (`npm run build` + gate con
  `--require-dist`), así que deja de estar desfasado respecto a `3.84.0`.
- **Todo lo declarado abierto en V3.83.1 y anteriores sigue abierto** salvo lo que esta
  release cierra de forma explícita arriba.

## V3.84.1 — Cierre del estado parcial Diccionario → léxico + mazo · 2026-09-25

> Release **DE ROBUSTEZ** (patch), con backend y frontend, **SIN migración de BD** y
> **SIN endpoints nuevos** (solo se afina el `detail` de un 400 existente). Detalle en
> `release-notes-v3.84.1.md`.

### Cerrado en V3.84.1 (deja de ser deuda)

- **El estado parcial del alta del diccionario se declara y se puede reintentar.**
  `addVocabularyItem` (léxico + FSRS) y `createFlashcard` (tarjeta del mazo) son dos
  escrituras; si la segunda fallaba, la UI decía «No se pudo añadir la palabra» aunque
  el aprendizaje **ya estaba hecho**. Ahora el alta del léxico tiene su propio
  `try/catch`, la tarjeta fallida queda como `pendingDeck`, el panel declara el estado
  **parcial** («ya está en aprendizaje, pero no se pudo guardar en el mazo») y ofrece
  **reintentar solo la tarjeta** sin repetir el alta. `[PRODUCTO]` `[UX]`
- **El nombre de mazo duplicado se dice como tal.** El backend responde
  `400 DECK_NAME_TAKEN` (antes: «No se pudo crear el mazo») y la UI lo traduce a «ya
  tienes un mazo con ese nombre» **sin ocultar el selector**: el fallo de creación deja
  de compartir estado con el de carga de mazos. `[UX]`
- **El puente Diccionario → Flashcards tiene E2E de sus cuatro desenlaces** (crear
  mazo → añadir → estudiar ese mazo → tarjeta visible; mazo existente; solo
  aprendizaje; fallo de la tarjeta → parcial → reintento), con la cola de cada mazo
  construida a partir de lo que entró de verdad, más el test unitario del reintento y
  del duplicado. `[VALIDACIÓN]`

### Sigue abierto o aparcado (deuda declarada)

- **La consolidación del ítem (léxico + tarjeta manual) sigue aparcada.** La palabra
  continúa existiendo como léxico **y** como tarjeta manual: es el precio de no
  compartir el modelo de tarjetas. `[PRODUCTO]`
- **La opción B —un endpoint transaccional «alta de léxico + tarjeta de mazo»— queda
  fuera de esta release.** Se eligió la opción A (dos escrituras + estado parcial
  declarado + reintento) por ser quirúrgica y no cambiar el contrato de API; la B sigue
  siendo arquitectónicamente más fuerte y queda pendiente de decidir. `[ARQUITECTURA]`
- **H5 (`add_item` no atómico) sigue abierto para su propio flujo** (retención); lo que
  V3.84.1 cierra es el estado parcial del puente Diccionario → mazo, que era su
  variante de producto. `[PRODUCTO]`
- **`delete_deck` tampoco es transaccional** (borra las cartas FSRS una a una y después
  el mazo): deuda preexistente del módulo que gana peso ahora que los mazos son pieza
  central. `[ROBUSTEZ]`
- **H1 sigue vivo en el código** (`_collection_writable` devuelve `True` para un pack
  global, `backend/domain/retention.py` ~185; **deuda aceptada `P2`** en `AU §12`). No
  se endurece aquí. `[SEGURIDAD]` `[PRODUCTO]`
- **Los packs sembrados por `slug` son inmutables en la práctica.** Editar un `*.json`
  no propaga a la BD; la política se documenta en `ensure_theme_packs_seeded` y un
  proceso de actualización de catálogo queda pendiente. `[CONTENIDO]`
- **H3 (`Sparkles` celebra también el 0 %) sigue abierto** como `P3` cosmético. `[UX]`
- **Los 8 gates humanos siguen `pending`** y `docs/audit/validation-evidence.json` **no
  existe**; el ancla de certificación sigue en `v3.83.1`. `[VALIDACIÓN]`
- **El informe `AV` del arco `v3.81.2..v3.82.0` sigue pendiente.** `[AUDITORÍA]`
- **Los 12 PRs de Dependabot siguen abiertos** (`#7`–`#18`). `[MANTENIMIENTO]`
- **Todo lo declarado abierto en V3.84.0 y anteriores sigue abierto** salvo lo que esta
  release cierra de forma explícita arriba.

## V3.85.0 — Diccionario en dos pestañas y «Repasar hoy» accionable · 2026-09-26

> Release de **PRODUCTO** (minor) **SOLO FRONTEND**, **SIN migración de BD**, **SIN
> endpoints nuevos** y **SIN cambio de contrato de API**. Detalle en
> `release-notes-v3.85.0.md`.

### Cerrado en V3.85.0 (deja de ser deuda)

- **«Repasar hoy» deja de ser una lista de estados y pasa a ser una acción.** Era una
  lista de hasta 20 filas con un botón por ítem cuya etiqueta era una **palabra de
  estado** («vencida»), así que no se leía como algo que se pulsa. Ahora es un
  **resumen** («tienes N palabras para repasar hoy») con **una sola acción**,
  «Repasar ahora (N)», que **encadena la cola del día** montando `WordDrill` palabra a
  palabra con su peldaño recomendado y su `decision_id`. Con `N = 0` no hay botón.
  `[PRODUCTO]` `[UX]`
- **El diccionario pasa de tres pestañas a dos y el inventario se coloca donde se
  trabaja.** `Consultar` · `Flashcards`, con el inventario del léxico como
  **sub-pestaña `Mi léxico`** de Flashcards (Estudiar · Mi léxico · Mazos · Tarjetas ·
  Estadísticas). La sub-pestaña de Estudiar presenta **dos acciones etiquetadas**
  —«Repasar hoy (N)» y «Estudiar tarjetas (N)»— que antes se confundían en un solo
  botón «Iniciar sesión». `[PRODUCTO]` `[UX]`
- **La traza declarada del «por qué» deja de repetirse veinte veces y se muestra una
  sola vez**, para la palabra que se está trabajando, que es cuando significa algo.
  `[UX]`
- **El barrido responsive cubre las cinco sub-pestañas de Flashcards a 320 px**, que es
  donde vive la sub-tablist estrecha que esta release añade. `[VALIDACIÓN]`

### Sigue abierto o aparcado (deuda declarada)

- **La sesión encadenada no es un motor nuevo.** Reutiliza `WordDrill` ítem a ítem y el
  mismo `GET /api/learning/review`; no hay planificador de sesión ni estado persistido
  de «sesión en curso»: salir del drill sale de la sesión. `[ARQUITECTURA]`
- **El panel incrustado de APRENDER → Vocabulario pierde el acceso al drill de repaso.**
  Decisión declarada: conserva sus dos modos (consulta + inventario) y el estudio vive
  en Flashcards. `[PRODUCTO]`
- **`StudyEntryCard` desaparece** y con él el alta directa a estudio desde la fila del
  inventario: esa puerta sigue en Flashcards (Estudiar y Mazos). `[PRODUCTO]`
- **Renombrar «Estadísticas» a «Progreso» no se incluye.** `[UX]`
- **La consolidación del ítem (léxico + tarjeta manual) sigue aparcada** (heredada de
  V3.84.1), igual que **H5**, **`delete_deck` no transaccional** y **H1**. `[PRODUCTO]`
- **Los 8 gates humanos siguen `pending`** y `docs/audit/validation-evidence.json` **no
  existe**. `[VALIDACIÓN]`
- **El encargo externo de auditoría de este arco está entregado** en
  `agentes/auditoria-total-externa-v385.md` (**prefijo `AY`**; informe esperado
  `docs/audit/AY-AUDITORIA-TOTAL-V385.md`), en un commit documental **posterior** a los tags
  `v3.84.1` y `v3.85.0`. Declaraba dos cosas que **este tag no declara** —el límite de
  presentación de la cola pasó **de 20 a 50** (`§6-D3`) y las notas nombran un
  `ReviewTodayCard` **que no existe en el código** (`§6-D2`)—, **ambas ya declaradas como
  errata y cerradas por V3.85.1** (ver el bloque siguiente). `[AUDITORÍA]`
- **La cola de auditoría sigue atrasada:** `AV` (`v3.82.0`, contrato + migración), `AW` (cierre
  V3.83.x) y `AX` (`v3.84.0`) **esperan informe**; `AY` es el cuarto encargo abierto. `[AUDITORÍA]`
- **Todo lo declarado abierto en V3.84.1 y anteriores sigue abierto** salvo lo que esta
  release cierra de forma explícita arriba.

## V3.86.0 — Diccionario polisémico y fichas en varios mazos (fase 1 de 2) · 2026-09-26

> Release de **PRODUCTO** (minor) **CON backend y frontend**, **CON migración de BD aditiva e
> idempotente**, **CON endpoints nuevos** (ficha-primero) y **CON bump de `GENERATOR_VERSION`**
> (`1.4.0 → 1.5.0`). Detalle en `release-notes-v3.86.0.md`.

### Cerrado en V3.86.0 (deja de ser deuda)

- **«lima» → la capital del Perú, servido a todos para siempre.** La caché guardaba una sola
  traducción por palabra y el prompt no prohibía nombres propios ni recibía contexto, así que un
  nombre propio podía quedar como equivalente de un nombre común. Ahora los prompts devuelven
  **significados elegibles** (`meanings`), la regla dura es que **un nombre propio nunca es el
  equivalente de un nombre común** (si existe, va **el último** y marcado) y **el defecto es el
  primer significado no nombre propio**. `GENERATOR_VERSION` a `1.5.0` invalida la fila envenenada.
  `[PRODUCTO]` `[CONTENIDO]`
- **La traducción curada ya existía y no se consultaba.** `match_pack_translation` lee los packs
  globales (`vocab_collection_items`): es **autoridad determinista, gratis y sin latencia** sobre el
  modelo (`tornillo → screw`, `lima → file`). `[ARQUITECTURA]` `[CONTENIDO]`
- **El alta en mazo dejaba sin salida a una palabra ya rastreada.** El botón de añadir no se pintaba
  con `usage.tracked` verdadero y la única acción saltaba al mazo automático **sin mazo elegido**.
  El panel está siempre disponible, no reescribe el léxico si la palabra ya está, los mazos son
  casillas y el CTA de estudio viaja con el mazo elegido. `[PRODUCTO]`
- **Un `deckError` escondía el selector y no se reintentaba nunca.** Ahora hay «Reintentar».
  `[ROBUSTEZ]`
- **Sin `translation` no había ninguna acción.** Se pide el reverso a mano y la ficha se crea con
  él. `[PRODUCTO]`
- **Una ficha no podía estar en dos mazos.** Tabla puente `flashcard_deck_cards` (N:M), API
  ficha-primero con `deck_ids` y borrado de mazo que **conserva** lo compartido y lo dice.
  `[ARQUITECTURA]` `[PRODUCTO]`
- **No existía recordatorio.** Columna `mnemonic` en la ficha, editable y borrable, visible en el
  reverso de la sesión y en el buscador de fichas. `[PRODUCTO]`
- **El diccionario incrustado de APRENDER → Vocabulario no daba salida a una palabra rastreada.**
  La vista de consulta declara el salto y lo transporta con su mazo. `[PRODUCTO]`
- **Un fallo real de arranque, destapado por la sonda:** `StudyTab` arrancaba con la cola del mazo
  anterior si resolvía después del foco, y el alumno se quedaba en el panel sin sesión aunque su
  mazo tuviera tarjetas. El arranque exige ahora `queue.deck.id === deck`. `[ROBUSTEZ]`

### Sigue abierto o aparcado (deuda declarada)

- **El léxico (`vocabulary`) y la ficha manual siguen separados.** El **recordatorio vive en la
  ficha**, así que el **mazo automático (id 0)** —que es una vista del léxico— **no lo muestra**.
  No se disimula con un campo espejo. `[ARQUITECTURA]` `[PRODUCTO]`
- **`flashcard_cards.deck_id` queda deprecada como «mazo principal» de un solo escritor.** Se
  conserva para que el esquema viejo siga abriendo; su retirada exige una **ventana de
  reconstrucción de tabla**. La pertenencia real es `flashcard_deck_cards`. `[ARQUITECTURA]`
- **La corrección de la caché es perezosa.** El bump de `GENERATOR_VERSION` invalidó la fila, pero
  `lima` (y cualquier otra fila envenenada) se regenera **al consultarla**: no hay barrido ni
  regeneración en el arranque, a propósito. `[CONTENIDO]`
- **No hay transacción entre léxico y ficha.** Siguen siendo **dos escrituras** con estado parcial
  declarado y reintento (decisión de V3.84.1, que se mantiene). `[ROBUSTEZ]`
- **`delete_deck` gana responsabilidades y sigue sin ser transaccional** (borra pertenencias, borra
  huérfanas con sus cartas FSRS y repunta la columna deprecada): la deuda heredada se agranda.
  `[ROBUSTEZ]`
- **`QUEUE_MAX` (100) y los límites diarios no cambian** en esta release. `[PRODUCTO]`
- **La fase 2 no está y se declara fuera:** elegir mazos al estudiar (incluido el automático) con
  dedupe, botón `(...)` de sesión con dirección ES↔EN y respuesta escrita persistida por usuario,
  validación de la respuesta respetando la premisa 21 (el servidor puntúa) y ayuda escalonada por
  **sílabas** (`syllables()` en `backend/services/phonemes.py` es hoy un proxy de grupos vocálicos
  impreciso, p. ej. `file` daría 2). `[PRODUCTO]` `[UX]`
- **El recordatorio no se puede ordenar ni filtrar por él** (solo se busca por su texto).
  `[UX]`
- **Los nombres propios se pueden elegir**, pero solo de forma **explícita**: van marcados, al final
  y nunca preseleccionados. `[PRODUCTO]`
- **El ancla de certificación sigue en `v3.83.1`** y **la cola de auditoría sigue atrasada**: `AV`
  (`v3.82.0`, contrato + migración), `AW` (cierre V3.83.x) y `AX` (`v3.84.0`) esperan informe.
  `[AUDITORÍA]`
- **Todo lo declarado abierto en V3.85.1 y anteriores sigue abierto** salvo lo que esta release
  cierra de forma explícita arriba.

## V3.85.1 — La sesión de repaso deja de atascarse y cierra la auditoría `AY` · 2026-09-26

> Release de **PRODUCTO** (patch) **SOLO FRONTEND**, **SIN migración de BD**, **SIN
> endpoints nuevos** y **SIN cambio de contrato de API**. Detalle en
> `release-notes-v3.85.1.md`; la auditoría que la origina es
> `docs/audit/AY-AUDITORIA-TOTAL-V385.md`.
>
> **ERRATA (declarada el 2026-09-26, antes de publicar `v3.86.0`): esta versión nunca se
> etiquetó.** El trabajo quedó **en el árbol de trabajo** y el `HEAD` público siguió en
> `v3.85.0`, así que **`v3.85.1` no existe como tag** y **no se recrea**. **Su delta va
> incluido íntegro en `v3.86.0`** (ver `§V3.86.0`), que lo absorbe; el rango
> `v3.85.0..v3.86.0` tiene **un solo commit de release** y no se puede auditar `v3.85.1`
> por separado.

### Cerrado en V3.85.1 (deja de ser deuda)

- **P0 (C1): «Repasar hoy» se quedaba clavada en un ítem reconductivo.** La sesión solo
  avanzaba con `onProduced`, que `recognition` y `recall` no disparan: si el planner servía
  uno de ellos como actividad inicial no aparecía «Siguiente palabra» y la única salida era
  cerrar el drill (que aborta la sesión). Se separa **`stepCompleted`** (veredicto del
  peldaño, apruebe o falle) de **`produced`** (evidencia productiva): el veredicto avanza, la
  producción sigue siendo otra cosa. `[PRODUCTO]` `[ARQUITECTURA]`
- **Accesibilidad de la sesión.** El contador es **región viva** (`role="status"` +
  `aria-live`), y el foco **viaja al CTA** («Siguiente palabra»/«Terminar») al aparecer.
  `[UX]`
- **D4: el panel APRENDER → Vocabulario recupera el acceso al repaso**, con **un solo CTA**
  que transporta a la superficie central (Flashcards → Estudiar) en vez de duplicar la sesión.
  `[PRODUCTO]`
- **G3: el artefacto de contraste identifica la release.** `contrast_audit.mjs` deriva
  `audit`/`version` de `frontend/package.json` y el informe se regenera. `[VALIDACIÓN]`
- **D3: el límite de la cola 20 → 50 queda declarado** (era errata de `v3.85.0`) y con
  **decisión de UX** escrita. `[DOCUMENTACIÓN]` `[UX]`
- **D2: la errata del `ReviewTodayCard` inexistente queda declarada** en
  `release-notes-v3.85.0.md` (el tag no se recrea). `[DOCUMENTACIÓN]`
- **C2: la semántica de «Repasar hoy» queda fijada.** Trabaja **competencia**; **no consume
  vencimiento FSRS**, así que el contador puede reaparecer y eso no es un bucle. `[PRODUCTO]`

### Sigue abierto o aparcado (deuda declarada)

- **La sesión larga sigue sin resolverse.** Hasta 50 ítems con **un clic obligatorio por
  ítem** y **sin estado persistido** (salir la pierde entera). Segmentar la sesión (lotes,
  reanudación, o un techo de sesión menor que el techo del endpoint) queda **aparcado**.
  `[PRODUCTO]` `[UX]`
- **El panel incrustado tiene CTA, no sesión.** El CTA transporta; el estudio sigue viviendo
  solo en Flashcards. `[PRODUCTO]`
- **La evidencia específica contra recorte interno en las cinco sub-pestañas a 320 px puede
  reforzarse** (la guardia vigila desborde de página, no recorte dentro del contenedor).
  `[VALIDACIÓN]`
- **El ancla de certificación sigue en `v3.83.1`** y **la cola de auditoría sigue atrasada**:
  `AV` (`v3.82.0`, contrato + migración), `AW` (cierre V3.83.x) y `AX` (`v3.84.0`) esperan
  informe; `AY` ya está dictaminado. `[AUDITORÍA]`
- **Todo lo declarado abierto en V3.85.0 y anteriores sigue abierto** salvo lo que esta
  release cierra de forma explícita arriba.

## Pendientes de acción humana (no aparcados, en curso)

- Ejecutar la **matriz de dispositivos** en hardware (G) y volcar resultados a
  `docs/DEVICE_MATRIX.md`.
- Medir la **variabilidad LLM de speaking** con Ollama real (`eval_speaking_variability`).
