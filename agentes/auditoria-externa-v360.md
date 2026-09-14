# Briefing de auditoría EXTERNA — V3.60 (Context Engine 4.0: Instance Specification → Parameterized Instance)

> **Para quién:** un agente/auditor EXTERNO que solo tiene acceso al repositorio
> público de GitHub (no al chat del gerente ni al historial de la sesión).
> **Qué entregar:** un informe siguiendo `docs/audit/TEMPLATE.md`, propuesto como
> `docs/audit/S-AUDITORIA-TOTAL-V360.md` (la letra `S` queda reservada para este
> dossier: la `R` sigue reservada para el informe de V3.59, todavía **no
> entregado**). Severidad P0–P3, cada hallazgo con **evidencia `fichero:línea`** y
> **reproducción**.
> **Regla de oro:** no te fíes de este documento. Es la **afirmación** del
> proyecto; tu trabajo es **falsarla** contra el código del commit auditado.

## Punto de entrada (todo desde GitHub)

- **Repositorio:** https://github.com/jvelasca/english-tutor (público).
- **Release de referencia (el objeto de la auditoría):** tag anotado **`v3.60.0`**
  → commit `2c79040` («release(v3.60.0): Context Engine 4.0 (Instance
  Specification -> Parameterized Instance)»). El diff completo de la release es
  `e721fce..2c79040` (**18 ficheros, +2854 / −78**); `e721fce` es el cierre de
  V3.59.
- **Estado auditado:** `main`, que es `2c79040` **más** los commits `docs(v3.60.0)`
  encima, que **solo registran el run de CI** de la release y este briefing
  (último: `34622fe`, 5 ficheros, +34 / −4). Ninguna línea de producto cambia
  entre ellos: si encuentras un `release-notes-v3.60.0.md` o un `docs/RELEVO.md`
  distintos de los del tag, **audita el árbol del tag** y repórtalo.
- **CI de la release:** run
  [34814504063](https://github.com/jvelasca/english-tutor/actions/runs/34814504063)
  sobre `2c79040` — debe estar **6/6 en success** (Release consistency, Backend
  ruff+pytest, Frontend tsc+vitest+build, Playwright E2E (visual), Beta V3.0 gate
  y Content validation). Verifícalo tú mismo: si algún check está en rojo o el run
  no existe, es un **P1** de verificación.
- **Documentos de resultado (afirmaciones a verificar):**
  `release-notes-v3.60.0.md` (el informe de la release) y
  `agentes/v360-context-engine-4.md` (el briefing de implementación).
  En `docs/RELEVO.md`, la **nota superior** y la sección «0. START HERE».
- **Reglas del proyecto a las que apelan las afirmaciones:** `docs/PREMISAS.md`
  (la **premisa 21** es la que prohíbe el LLM en el camino de la evidencia y la
  **8/12** las que ordenan verificar contra el árbol real antes de creer a un
  documento), `docs/ARQUITECTURA.md` y `docs/AUDITORIA-V3.md` (el estándar de
  auditoría del proyecto).
- **Procedencia de los hallazgos que V3.60 dice cerrar:** el informe de la
  auditoría externa de V3.59 (**P1-1**, **P1-2**, **P2-6**, **P2-7**) **no está
  publicado** en `docs/audit/` (se esperaba en `R-AUDITORIA-TOTAL-V359.md`). Su
  contenido se resume en `release-notes-v3.60.0.md`; si necesitas el original,
  pídelo antes de auditar, porque aquí solo tienes la paráfrasis del proyecto.
- **Releases previas de referencia:** `v3.59.0` → `e721fce` (Context Engine 3.0,
  Family/Instance), `v3.58.0` → `82f17c4` (Sense Engine 2.0), `v3.57.0` →
  `a40b58d` (Planner 2.0, argmax sobre ELV), `v3.55.0` → el último cambio de
  ledger (`Task Difficulty 3.0`, columnas `declared`/`served`/
  `observed_task_difficulty`).

## Contexto: qué es V3.60 y qué reemplaza

El **banco de contextos de transferencia** son 20 «familias» curadas
(`backend/services/transfer.py`, `TRANSFER_CONTEXTS`): cada una declara `id`, seis
dimensiones core (`topic`, `communicative_goal`, `discourse_type`,
`social_relation`, `time_reference`, `interaction_type`), `register`, `cefr`,
`difficulty_vector`, `skills`, `lexical_environment`, `syntactic_focus` y una
consigna. El `context_id` del ledger es el de la **familia** (`transfer:<id>`) y
de él dependen la escalera `transfer_state` y sus umbrales, la distancia y la
diversidad contextuales y la novedad.

**V3.59** separó FAMILIA de INSTANCIA (una **redacción** declarada de la misma
familia, servida por rotación `N % nº_superficies`), pero dejó dos límites: el
banco seguía siendo **finito y escrito a mano** (20 × 3 = 60 consignas, agotables
en tres intentos) y la instancia **no podía declarar** su ajuste de carga
(`CONTEXT_INSTANCE_KEYS` era `("instance", "prompt")`), así que el ledger
persistía siempre el vector de la **familia**.

**V3.60** no añade redacciones a mano **ni** genera texto con un LLM (premisa 21:
nada de modelo en el camino de la evidencia). Parametriza la **COMBINACIÓN de
contenido DECLARADO**: cada familia declara un `instance_space` (`template` +
`slots` + `selection` + `difficulty_delta`) y de ahí se derivan superficies
deterministas de la MISMA identidad. **FAMILIA → ESPECIFICACIÓN → INSTANCIA**, con
la superficie 0 siempre la consigna histórica, las dos declaradas de V3.59 en los
índices 1–2 y las generadas a partir del índice 3.

## Lo que V3.60 afirma (el delta a falsar)

1. **Frontera de identidad ampliada, no identitaria.**
   `CONTEXT_INSTANCE_KEYS` (`backend/services/transfer.py:164`) tiene **7 claves**
   (`instance`, `prompt`, `scenario`, `goal`, `register`, `difficulty_delta`,
   `skill_delta`); su intersección con las claves de familia es **exactamente**
   `{"prompt"}` (más `register`, que es dimensión core y solo la lee la familia) y
   `_surface_details` (`:2378`) **lee solo** esas claves **descartando cualquier
   otra**: una superficie no puede declarar `id`, dimensiones core, `cefr`,
   `difficulty_vector`, `skills`, `lexical_environment` ni `syntactic_focus`.
   `FAMILY_KEYS` está declarado **en los tests** (`tests/test_context_engine_v360.py:51`),
   no en el módulo: la única clave nueva del banco es `instances` + `instance_space`.
2. **Las tres primeras superficies son las de V3.59, byte a byte.**
   `context_instance_details(context)[:3]` == `[histórica, instances[0], instances[1]]`;
   la rotación no cambia, solo se **prolonga**.
3. **Determinismo total.** Expansión = producto cartesiano en orden declarado,
   prefijo cortado a `CONTEXT_INSTANCE_SPACE_MAX`; `_slug` (`:2103`) se deriva del
   contenido y **nunca** de `hash()`; sin `random`, sin `time`, sin LLM.
4. **Anti-memorización.** `CONTEXT_INSTANCE_SPACE_MIN = 12` (`:184`) superficies
   **totales** por familia, verificado sobre el banco real: el banco declarado
   tiene **358 superficies** (16–19 por familia) y una familia ya no se agota en 3
   intentos. `CONTEXT_INSTANCE_SPACE_MAX = 96` (`:189`) es techo y hoy es inerte
   (el máximo real es 19).
5. **Especificación inservible no rompe nada.** `context_instance_spec` (`:2207`)
   devuelve `{}` si la plantilla no tiene placeholders válidos o si algún
   placeholder no tiene un slot con ≥1 valor utilizable, y `_instance_value`
   (`:2132`) **descarta** los valores sin `value`: la familia conserva sus
   superficies declaradas y **no se inventa contenido**.
6. **Dificultad efectiva explícita.** `difficulty.normalize_delta` acepta deltas
   **enteros** por dimensión canónica y los recorta a **±2** (ignora claves
   desconocidas, fraccionarios y basura); `apply_delta` suma base + delta y recorta
   al envelope **1..5**, **ignorando** un delta que apunte a una dimensión que la
   base no declara. Con delta vacío o inválido devuelve `normalize_vector(vector)`
   **exacto**.
7. **Degradación EXACTA.** Sin intentos, `context_instance_index` es 0 ⇒ la
   superficie servida es la consigna histórica y el delta efectivo es `{}`; y
   `context_difficulty()` (la carga de la familia) **no cambia**, así que los
   llamadores de solo lectura quedan intactos.
8. **La elección de FAMILIA no cambia.** Ninguna clave nueva entra en
   `CONTEXT_DIMENSIONS`, `context_distance`, `context_diversity`, `_novelty_score`,
   `transfer_state` ni sus umbrales; la superficie **no participa** en
   `_within_level`, `_filter_skill`, `select_by_difficulty` ni `_stable_index`.
9. **Contrato aditivo.** 8 claves nuevas en **todos** los retornos, incluido el
   temprano de banco vacío (`transfer.py`, retorno `:2934`-`:2945` y payload
   `:3022`-`:3036`): `instance_scenario`, `instance_goal`, `instance_register`,
   `instance_difficulty_delta`, `instance_difficulty_vector`,
   `instance_difficulty`, `instance_skills`, `instance_generated`. Las **28 claves
   de V3.59** quedan intactas (36 en total), con `TransferContextOut`
   (`schemas/vocabulary.py`) y espejo opcional en `frontend/src/types/api.ts`.
10. **Ledger aditivo, sin migración.** `_record_transfer_evidence`
    (`domain/vocabulary.py:761`) persiste `served=transfer.served_difficulty(
    context_id, attempts_by_context)` —la superficie que **toca servirse**— en las
    columnas de V3.55; `observed_difficulty` sigue siendo la proyección legacy y
    las superficies **sin delta** (incluida siempre la 0) escriben **bytes
    idénticos** a V3.59. Sin columnas nuevas, sin bump de `GENERATOR_VERSION`, sin
    cambios de UI.
11. **Sin regresión.** `pytest` **2335 passed** en local (**2333 + 2 skipped** en
    CI: Whisper no descargado en el runner), `ruff` limpio, launcher **75 passed**,
    `tsc` OK, `vitest` **651** (76 ficheros), build OK,
    `check_release_consistency` **3.60.0**, `check_beta_v3` OK,
    `content_validation` OK.

## Preguntas de alto valor (por dónde morder)

1. **Equivalencia pedagógica REAL, no declarativa.** El test comprueba que las
   superficies de una familia comparten dimensiones core, `cefr` y `skills` de
   familia. Revísalo tú sobre las **358 superficies**: ¿alguna combinación cambia
   el **registro**, el **tiempo verbal**, el **objetivo comunicativo** o exige una
   competencia que la familia no declara? ¿Algún slot introduce un escenario de
   otra familia (una superficie de `story` que en realidad pida una reclamación
   formal)?
2. **¿El delta puede escalar a identidad?** `apply_delta` recorta a 1..5, pero
   **¿qué LEE** la carga efectiva? Rastrea `instance_difficulty_vector`,
   `instance_difficulty_delta` y `served_difficulty` por todo el repo: si el vector
   con ajuste entra en `observed_signals`/`observed_capacity`
   (`services/evidence.py`), en `learner_skill`, en el suelo del alumno o en el
   planner, un matiz de superficie (+1 de `discourse`) estaría moviendo el
   **Student Model**. Ese sería el P1 de esta release si existe.
3. **¿GET y POST pueden divergir?** Compara qué mapa de intentos se pasa en cada
   camino: el GET (`get_transfer_context`, `domain/vocabulary.py:976`) lo pasa en
   `:1037`; el POST (`submit_transfer_attempt`, `:1041`) lo pasa al derivar el
   `context_id` (`context_for`, `:1116`) y al registrar (`:1143`), y lee el resumen
   en `:1090`, **antes** de escribir el evento. Decide si el POST registra la
   dificultad de la superficie que el GET **sirvió** o la de la **siguiente**.
   Prueba doble intento seguido, reintento del cliente tras fallo de red,
   `context_id` explícito del cliente de **otra** familia que la servida, y
   `attempts_by_context` ausente o con basura.
4. **Anti-spoiler (invariante de V3.43).** `template` y valores de slot deben dar
   **ESCENARIO**, nunca la unidad objetivo. Busca si algún `template`/valor
   contiene la unidad léxica del ítem o una forma suya (o el campo léxico que la
   delata), sobre todo en los valores con `scenario`/`goal`.
5. **Dedup y colisiones.** El dedup de `context_instance_details` es por **texto**
   de consigna y el slug por valores. ¿Puede haber dos superficies con la MISMA
   consigna y **delta distinto** (el dedup perdería un ajuste declarado en
   silencio) o dos slugs iguales con textos distintos? ¿Y una superficie que se
   caiga por no renderizar la plantilla?
6. **El cap y el sesgo de `selection`.** Verifica si `CONTEXT_INSTANCE_SPACE_MAX`
   es hoy inerte (máximo real 19). Construye una familia sintética que lo supere y
   comprueba si el recorte por **prefijo** deja siempre fijos los últimos slots,
   de modo que el espacio nuevo variara solo en el primero.
7. **Coste en el camino caliente.** `context_instance_details` re-expande el
   producto cartesiano en **cada** llamada a `context_for`, y `served_difficulty`
   lo vuelve a expandir en la **escritura**. Mide el coste por request y decide si
   es aceptable (¿O(n) estable? ¿crece con el banco? ¿hay caché o memoización?).
   Una regresión de latencia en el drill sería un P2.
8. **Aditividad real del contrato.** ¿Hay consumidores (frontend, tests, docs) que
   asuman la forma antigua? ¿El retorno de banco vacío trae las 8 claves con los
   **mismos defaults**? ¿Cambió de tipo, de valor o de presencia alguna de las 28
   claves de V3.59?
9. **Determinismo.** ¿Algún orden de `dict`/`set` influye en el resultado
   (expansión, deltas, `skills`), algún `hash()`, `random`, `time` o llamada al
   modelo en el camino de la evidencia (premisa 21)? ¿Están fijados el orden de
   `CONTEXT_SKILLS` y el de `CONTEXT_INSTANCE_DETAIL_KEYS`?
10. **¿Los tests prueban la invariante o la implementación?** Distingue si la
    equivalencia pedagógica compara la superficie contra la **familia real** o
    contra literales copiados del propio código; si la no-regresión de la elección
    compara payloads **reales** con y sin `attempts_by_context`; y si el
    end-to-end HTTP comprueba la **fila persistida** de una superficie GENERADA
    (con qué `attempts`, y que el vector guardado es el **efectivo**, no el de la
    familia).

## Método reproducible

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor && git checkout v3.60.0        # 2c79040
git diff e721fce..2c79040                       # el delta de la release
cd backend && python -m pytest tests/ -q        # 2335 passed
python -m ruff check .
python -c "from services import transfer as t; print(len(t.TRANSFER_CONTEXTS), sum(len(t.context_instance_details(c)) for c in t.TRANSFER_CONTEXTS))"   # 20 358
python -c "from services import transfer as t; d=t.context_instance_details('debate'); print(len(d), [s['generated'] for s in d[:4]])"   # 19 [False, False, False, True]
cd ../frontend && npx tsc --noEmit && npm test  # 651
npm run build
cd .. && python scripts/check_release_consistency.py   # 3.60.0
python scripts/check_beta_v3.py
python backend/scripts/content_validation.py
```

Ficheros calientes: `backend/services/transfer.py` (banco + `instance_space`,
`CONTEXT_INSTANCE_KEYS`, `CONTEXT_INSTANCE_SPACE_MIN/MAX`, `context_instance_spec`,
`_expand_spec`, `_surface_details`, `context_instance_details`,
`context_instance_index`, `context_instance_metadata`,
`context_instance_difficulty`, `served_difficulty`, `context_for`),
`backend/services/difficulty.py` (`normalize_delta`, `apply_delta`),
`backend/domain/vocabulary.py` (`_record_transfer_evidence`,
`submit_transfer_attempt`), `backend/schemas/vocabulary.py` +
`frontend/src/types/api.ts` (contrato y espejo) y
`backend/tests/test_context_engine_v360.py` (23 tests: frontera de identidad,
anti-memorización, preservación de V3.59, **equivalencia pedagógica** en `:300`,
**determinismo** en `:349` y end-to-end HTTP de la superficie generada en
`:697`), más el ajuste declarado en `backend/tests/test_context_engine_v359.py`
(`== 1 + MIN` → `>= 1 + MIN`).

## Fuera de alcance (deuda aceptada, no la reportes como nueva)

- **`context_instance` en el ledger** (evidencia instance-aware): hoy la evidencia
  sigue siendo de **familia** por diseño.
- **Motor de política de instancia** (cuándo repetir una superficie, cuándo forzar
  una nueva, cómo pesa el fallo) — V3.61+.
- **Student Skill State 3.0**, WSD real, aprendizaje de `P(success | learner, task)`,
  Observed Task Difficulty 2.0 y **Planner 3.0**.
- **Re-priorización declarada:** `release-notes-v3.59.0.md` anunciaba que V3.60
  sería «el contrato/prompt de generación de sentidos y la ponderación de la
  adecuación en `transfer_confidence`». V3.60 hizo **Context Engine 4.0** en su
  lugar. Es una decisión de rumbo **consciente y documentada** (las notas de
  V3.60 lo declaran en su «Fuera de alcance»); si crees que la documentación debe
  corregirse para no prometer lo que no se hizo, repórtalo como P3 documental, no
  como defecto de código.
- Los **P3-02/P3-03** de auditorías anteriores, ya aceptados y declarados en
  `docs/RELEVO.md`.

## Formato del informe

Sigue `docs/audit/TEMPLATE.md`. El **precedente concreto** más reciente y de la
misma familia es `docs/audit/Q-AUDITORIA-TOTAL-V352.md`, cuya estructura
recomendamos reutilizar: **veredicto ARRIBA**, posición auditada y evidencia
ejecutada, cierre real de los P1 que la release dice haber cerrado, cero regresión
/ determinismo / coste, **hallazgos** (severidad P0–P3, cada uno con
**evidencia `fichero:línea`**, por qué importa —impacto en la evidencia del
alumno—, reproducción y arreglo sugerido), un apartado explícito de
**observaciones que NO son hallazgos** (verificadas y correctas), las **respuestas
a las preguntas de este briefing** (una por una), recomendación para el siguiente
incremento y **Regenerar / Verificar** con los comandos exactos.

Cierra con un **veredicto de merge-readiness** explícito: ¿se puede dejar
`v3.60.0` como release estable, o hay que parchear antes?
