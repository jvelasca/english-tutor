# Briefing de auditoría EXTERNA — V3.59 (Context Engine 3.0: Context Bank Family/Instance)

> **Para quién:** un agente/auditor EXTERNO que solo tiene acceso al repositorio
> público de GitHub (no al chat del gerente ni al historial de la sesión).
> **Qué entregar:** un informe siguiendo `docs/audit/TEMPLATE.md`, propuesto como
> `docs/audit/R-AUDITORIA-TOTAL-V359.md` (la letra `R` queda reservada para este
> dossier; `Q` se usó en V3.52). Severidad P0–P3, cada hallazgo con **evidencia
> `fichero:línea`** y **reproducción**.
> **Regla de oro:** no te fíes de este documento. Es la **afirmación** del
> proyecto; tu trabajo es **falsarla** contra el código del commit auditado.

## Punto de entrada (todo desde GitHub)

- **Repositorio:** https://github.com/jvelasca/english-tutor (público).
- **Release de referencia (el objeto de la auditoría):** tag anotado **`v3.59.0`**
  → commit `e721fce` («release(v3.59.0): Context Engine 3.0 (Context Bank
  Family/Instance)»). El diff completo de la release es
  `7687f1b..e721fce` (15 ficheros, +1326 / −58).
- **Estado auditado:** `main`, que es `e721fce` **más** el único commit
  `docs(v3.59.0)` encima, que **solo registra el run de CI** de la release (y este
  briefing). Ninguna línea de producto cambia entre ambos: si encuentras un
  `release-notes-v3.59.0.md` o un `docs/RELEVO.md` distintos de los del tag,
  **audita el árbol del tag** y repórtalo.
- **CI de la release:** run
  [34782482120](https://github.com/jvelasca/english-tutor/actions/runs/34782482120)
  sobre `e721fce` — debe estar **6/6 en success** (Release consistency, Backend
  ruff+pytest, Frontend tsc+vitest+build, Playwright E2E (visual), Beta V3.0 gate
  y Content validation). Verifícalo tú mismo: si algún check está en rojo o el run
  no existe, es un **P1** de verificación.
- **Documentos de resultado (afirmaciones a verificar):**
  `release-notes-v3.59.0.md` (el informe de la release) y
  `agentes/v359-context-engine-3.md` (el briefing de implementación).
  En `docs/RELEVO.md`, la **nota superior** y la sección «0. START HERE».
- **Releases previas de referencia:** `v3.58.0` → `82f17c4` (Sense Engine 2.0),
  `v3.57.0` → `a40b58d` (Planner 2.0, argmax sobre ELV), `v3.55.0` → el último
  cambio de ledger (`Task Difficulty 3.0`).

## Contexto: qué es V3.59 y qué reemplaza

El **banco de contextos de transferencia** son 20 «familias» curadas
(`backend/services/transfer.py`, `TRANSFER_CONTEXTS`): cada una declara `id`,
seis dimensiones core (`topic`, `communicative_goal`, `discourse_type`,
`social_relation`, `time_reference`, `interaction_type`), `register`, `cefr`,
`difficulty_vector`, `skills`, `lexical_environment`, `syntactic_focus` y
**una consigna**. Los seis primeros contextos están **congelados** desde V3.43.

El `context_id` que se escribe en el ledger es el de la **familia**
(`transfer:<id>`). De él dependen la escalera `transfer_state` y sus umbrales, la
distancia y la diversidad contextuales y la novedad: por eso **añadir familias**
habría movido la evidencia ya registrada y reescalado los umbrales.

**El problema (P2-04 de la auditoría de V3.43, diferido desde V3.48):** el banco es
**finito** y cada familia tiene **una sola** consigna. Con el pool agotado
(`exhausted=True`) el motor vuelve a servir la **misma redacción**: el alumno
puede memorizar la estructura en lugar de transferir la unidad, y la evidencia lo
cuenta como transferencia.

**La solución:** separar **FAMILIA** (identidad pedagógica + **unidad de
evidencia**) de **INSTANCIA** (otra **redacción** del mismo escenario, declarada
en el banco). La familia **no cambia** (20 y las mismas `id`); cada familia
**declara superficies adicionales** y el intento N de un ítem en esa familia
recibe la superficie `N % nº_superficies`, con la **superficie 0 = la consigna
histórica**, byte a byte.

## Lo que V3.59 afirma (el delta a falsar)

1. **La familia servida NO cambia.** `context_for` no pasa la superficie por
   `_within_level`, `_filter_skill`, `select_by_difficulty`, `_novelty_score` ni
   `_stable_index`. Con y sin el kwarg nuevo `attempts_by_context`, el payload es
   idéntico **salvo** `prompt` / `context_instance` / `instance_index`.
2. **La superficie 0 es la consigna histórica**, para las 20 familias y en
   particular para los seis contextos congelados (comparación **byte a byte**
   contra el literal de V3.58).
3. **Rotación determinista** `attempts % nº_superficies` (sin azar, sin hash, sin
   LLM). Sin intentos ⇒ índice 0 ⇒ degradación **exacta** a V3.58.
4. **Guardas de identidad:** `CONTEXT_INSTANCE_KEYS = ("instance", "prompt")` es
   lista blanca y `context_instances` **reconstruye** cada superficie con esas dos
   claves, **descartando cualquier otra**: una instancia no puede declarar
   `cefr`/`difficulty_vector`/dimensiones core/`id`/`skills`. `FAMILY_KEYS`
   (verificado por test) fija que la **única** clave nueva del banco es
   `instances`.
5. **`CONTEXT_INSTANCES_MIN = 2`**: toda familia declara ≥2 superficies
   adicionales; el banco pasa de **20 consignas a 60 superficies** sin tocar
   ninguna `id`.
6. **Contrato aditivo:** tres claves nuevas en **todos** los retornos
   (`context_instance`, `instance_index`, `instance_count`, incluido el retorno
   temprano de banco vacío) y **25 claves de V3.58 intactas** (28 en total).
   `TransferContextOut` + espejo opcional en `frontend/src/types/api.ts`.
7. **Cableado único:** los dos caminos de `backend/domain/vocabulary.py` (GET de
   la consigna y derivación del `context_id` al registrar sin contexto) pasan
   `attempts_by_context=summary.get("contexts")`, el mismo mapa del que salen los
   `used_context_ids`.
8. **Sin migración de BD, sin bump de `GENERATOR_VERSION`, sin cambios de UI y sin
   tocar el ledger.**
9. **Sin regresión:** `pytest` **2312 passed**, `ruff` limpio, launcher **75
   passed**, `tsc` OK, `vitest` **651**, build OK, `check_release_consistency`
   **3.59.0**, `check_beta_v3` OK, `content_validation` OK.

## Preguntas de alto valor (por dónde morder)

1. **Identidad semántica de las superficies.** Las guardas impiden cambiar
   atributos **declarados**, pero **no** que una `instance` describa otro
   escenario (una superficie de `story` que en realidad pida una queja formal a
   soporte). Revisa las 40 superficies nuevas y di si **respetan** las seis
   dimensiones de su familia, su `cefr`, su `difficulty_vector` y su
   `lexical_environment`. ¿Hay alguna que cambie el **registro** o el **tiempo
   verbal** que la familia declara?
2. **¿La rotación mide lo que dice medir?** `_count` es deliberadamente
   permisivo (dict `{"attempts": n}`, entero, su forma textual; `bool`,
   negativos y `None` valen 0). Busca una forma del resumen de evidencia real
   que haga que el índice **no** avance, que **salte** superficies o que
   oscile entre intentos. ¿Puede el alumno **elegir** la superficie?
3. **¿Puede divergir el GET y el POST?** Compara qué mapa se pasa en cada camino
   de `domain/vocabulary.py` y si la superficie servida en el GET es la que queda
   registrada (o si el ledger registra solo la familia, como se afirma).
4. **¿La memoria se rompe de verdad?** Con el pool agotado y N intentos, ¿la
   segunda estancia sirve una redacción **distinta** (el test lo comprueba por
   HTTP), y son las 3 superficies de cada familia **distintas entre sí** —no una
   variación cosmética de una palabra—? ¿Cubren el objetivo comunicativo o alguna
   es una paráfrasis trivial?
5. **Aditividad real del contrato.** ¿Hay consumidores (frontend, tests,
   documentación) que asuman la forma antigua? ¿Alguna clave de V3.58 cambió de
   tipo, de valor o de presencia, o el payload de banco vacío dejó de traer las
   tres claves nuevas?
6. **Cero efecto en el ledger.** ¿Alguna escritura, migración, columna nueva o
   cambio de `context_id`? ¿Se toca `transfer_state`, sus umbrales,
   `context_signals`, `context_distance`, `context_diversity`, `_novelty_score`,
   `difficulty.py`, `CEFR_CAPACITY`, el scoring o FSRS?
7. **Determinismo.** ¿Hay orden de `dict`/`set` que influya, `random`, `time` o
   cualquier llamada al modelo en el camino de la evidencia (premisa 21)?
8. **Los tests prueban la invariante o la implementación?** Distingue: ¿la
   no-regresión de la decisión compara contra la **evidencia real** o contra
   literales copiados de la implementación? ¿El test de la consigna histórica
   compara con el literal de V3.58 o consigo mismo?

## Método reproducible

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor && git checkout v3.59.0        # e721fce
git diff 7687f1b..e721fce                       # el delta de la release
cd backend && python -m pytest tests/ -q        # 2312 passed
python -m ruff check .
cd ../frontend && npx tsc --noEmit && npm test  # 651
cd .. && python scripts/check_release_consistency.py   # 3.59.0
```

Ficheros calientes: `backend/services/transfer.py` (banco, `context_instances`,
`context_instance_index`, `_count`, `_attempts_for`, `context_for`),
`backend/domain/vocabulary.py` (los dos caminos del drill),
`backend/schemas/vocabulary.py` + `frontend/src/types/api.ts` (contrato y espejo)
y `backend/tests/test_context_engine_v359.py` (16 tests).

## Fuera de alcance (deuda aceptada, no la reportes como nueva)

- El contrato/prompt de **generación de sentidos** y su bump de
  `GENERATOR_VERSION` (V3.60).
- Ponderar la adecuación semántica en `transfer_confidence` (V3.60).
- Los P3-02/P3-03 de auditorías anteriores, ya aceptados y declarados en
  `docs/RELEVO.md`.

## Formato del informe

Sigue `docs/audit/TEMPLATE.md`. Cada hallazgo: **severidad**, **título**,
**evidencia `fichero:línea`**, **por qué importa** (impacto en la evidencia del
alumno), **reproducción** y **arreglo sugerido**. Cierra con un **veredicto de
merge-readiness** explícito: ¿se puede dejar `v3.59.0` como release estable, o hay
que parchear antes?
