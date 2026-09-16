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

- Depuración de las **50 claves i18n huérfanas** (candidatas legacy;
  `docs/audit/generated/i18n-report.json`).
- Decidir **consolidación de la doble lectura de readiness** en Home y ancla
  textual «Estás aquí» (F2/F3).
- Extender el **patrón loading/error** (aplicado en Home) a los paneles
  profundos que hoy tragan errores en silencio (F4).

## V3.70 — auditoría pedagógica (1 P0 · 15 P1 · 12 P2 · 5 P3)

> Origen: `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md` (síntesis de los cinco ejes
> `AA`–`AE`). **V3.70 no corrige nada**: estos 33 hallazgos se **aparcan
> asignados a fase** y **dejan de ser opinión**. Los 6 P2 de la auditoría de V3.69
> siguen abiertos aparte (decisión de alcance, no aparecen aquí).

### Contenido y banco (→ V4.0.x)

- **P0 · Posición de la correcta en los checks del currículum**: **329/368
  checks (89,4 %)** tienen la respuesta correcta en la **posición 0**, así que
  marcar siempre la primera opción acierta ~9/10. El corpus de listening **no**
  tiene este defecto (~25 % por posición). Reproducir con
  `python -m scripts.audit_dossier cefr-adequacy`.
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
  listening/speaking/writing/pronunciation (lo declara su docstring).
- **P2 · Sesgo de forma del placement**: correcta = más larga única en el **50 %**,
  más larga o empatada en el **75 %**, **70,8 %** en la posición 1 y la **posición
  3 nunca** correcta.
- **P2 · Umbrales de banda triplicados** y sub-bandas `+` que **ningún estimador
  emite**.
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
- **RC-01 · Servido de `frontend/dist` → V3.72/V3.73.** Hoy la UI la sirve el dev
  server de Vite y **Node + npm son requisito de EJECUCIÓN**; se declaró con
  condición de salida en lugar de implementarse (decisión A del briefing de V3.71)
  porque la pregunta «¿qué debe tener instalado el usuario?» se responde con el eje
  RB y el empaquetado está vetado.

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

## Pendientes de acción humana (no aparcados, en curso)

- Aplicar (tras tu aprobación) el **fix mecánico del sesgo posicional** en
  corpus de listening (B1) y checks del currículo (A1): rotación determinista
  por ítem, con `python -m scripts.audit_dossier mc-bias` para re-medir. **V3.70 lo
  midió y lo elevó a P0** (`docs/audit/AA-PED-CONTENIDO-CEFR.md`: 329/368 checks
  con la correcta en la posición 0); el test `test_ped_content_cefr_v370.py` fija
  la cifra y **fallará** cuando se corrija, obligando a re-auditar el eje.
- Ejecutar la **matriz de dispositivos** en hardware (G) y volcar resultados a
  `docs/DEVICE_MATRIX.md`.
- Medir la **variabilidad LLM de speaking** con Ollama real (`eval_speaking_variability`).
