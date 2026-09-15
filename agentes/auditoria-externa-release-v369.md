# Auditoría EXTERNA de RELEASE de V3.69 — punto de entrada (listo para lanzar)

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **`v3.69.0` ya
> publicada**, no un plan. La revisión es **de solo lectura**: no se cambia código,
> datos, configuración ni etiquetas publicadas.
>
> **Por qué una auditoría de RELEASE y no de diseño.** Su pareja es
> `agentes/auditoria-externa-v369.md` (auditoría de **DISEÑO**, escrita antes de
> implementar, informe esperado en `docs/audit/Z-AUDITORIA-DISENO-V369.md`).
> Este documento audita **lo entregado**: la diferencia entre «el plan es
> correcto» y «lo publicado demuestra lo que dice demostrar».
>
> **Estado:** entregado 2026-09-15. **Informe esperado:**
> `docs/audit/Z2-AUDITORIA-RELEASE-V369.md` (la `Z` la ocupa el informe de diseño;
> `Z2` evita colisión y conserva la trazabilidad del mismo incremento).

## Punto de entrada

- Repositorio: `jvelasca/english-tutor` (**público**), rama `main`.
- **Release auditada:** commit **`9a4e70a`** (`release(v3.69.0): E2E + Adaptive
  Engine Validation`) con el **tag anotado `v3.69.0`** (objeto `bc82477…`, apunta
  a `9a4e70a`).
- **Cierre documental posterior** (no toca código): `8b41d7d` (registro del cierre
  y del run de CI) y `bded470` (precisión del alcance del diff + este documento).
  El **HEAD documental** puede ser posterior; **el objeto de esta auditoría es el
  tag `v3.69.0`**.
- **Base de comparación:** `v3.68.0` → release `8acee38`, cierre documental
  `d5311cc`.
- **CI del commit de release:** **6/6 verde** en
  [run 34978215154](https://github.com/jvelasca/english-tutor/actions/runs/34978215154)
  — `Content validation` `104411343743` · `Playwright E2E` `104411343956` ·
  `Beta V3.0 gate` `104411344002` · `Release consistency` `104411344187` ·
  `Frontend` `104411344226` · `Backend` `104411344275`. Los dos commits de cierre
  documental también salieron 6/6 (`34979393221`, `34979804033`).
- **Los números de línea citados** corresponden al árbol publicado en `v3.69.0`
  (los commits posteriores son solo documentales).

**Artefactos nuevos de la release (objeto de la auditoría):**

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/tests/test_adaptive_e2e_v369.py` | Batería **E01–E19 + E16b** (20 tests HTTP) | Que la cadena `Evidence → Student State → Decision Projection → Task selection → Decision → Serving → Attempt → Outcome → Evidence` funciona como una pieza |
| `frontend/tests/visual/drillProvenance.spec.ts` | **2 specs** de navegador con red mockeada | Que el cliente envía el `decision_id` y declara `started`/`abandoned`; y que **sin** `decision_id` no declara nada |
| `release-notes-v3.69.0.md` | Nota de release | Alcance, **tabla §C con los 5 hallazgos medidos**, §G-1/§G-2 (lo que no se declara limpio) |
| `docs/RELEVO.md` (nota de cabecera), `CHANGELOG.md` `[3.69.0]`, `PLAN.md` | Relevo y coherencia | Estado, verificación y **CIERRE** con el run id |

## Alcance y enfoque

1. **Falsar el alcance del diff.** La release afirma **cero líneas de LÓGICA de
   producto**. Comprobarlo; cualquier línea de producto que no sea un bump de
   versión es **hallazgo P1**.
2. **Validar la batería como DEMOSTRACIÓN**, no como inventario: ¿cada escenario
   tiene una aserción que **fallaría** si el comportamiento declarado no se
   cumple? ¿hay alguno que pase **sin demostrar nada** (tautológico, sembrado
   para coincidir, o afirmando sobre un valor que el propio test calcula)?
3. **Auditar la honestidad de los cinco hallazgos** de §C: el proyecto los declara
   **deuda aceptada**; el auditor debe dictaminar si alguno debería ser
   **P1/P2** (es decir, si «aceptado» es una decisión legítima o una forma de
   cerrar un agujero de observabilidad).
4. **Comprobar el contrato del cliente** (§F): ¿fija lo que el navegador **real**
   envía, o solo lo que el mock permite creer?
5. **Verificar los números del CI** en la API de GitHub (jobs, conteos y
   conclusión) y distinguir lo que es **resultado del run** de lo que sigue siendo
   **declaración del release**.
6. **Comprobar que no se ha tocado la política ni el contenido**:
   `DECISION_POLICY_VERSION`, `GENERATOR_VERSION`, migraciones, umbrales.
7. **Comprobar la coherencia con la auditoría `Y`**: que V3.69 **no contradiga**
   ninguno de sus veredictos ni convierta hallazgos P2/P3 en «cerrados» sin
   evidencia.

**No se audita:** el diseño del motor adaptativo de V3.68 (ya auditado en `Y`) ni
el plan de V3.69 (lo cubre `Z`). No se pide re-implementar nada: el resultado
esperado es un **dictamen**, no un rediseño.

## Afirmaciones a falsar

Cada punto trae **cómo comprobarlo** y **qué resultado lo falsaría**.

1. **Cero lógica de producto.**
   `git diff v3.68.0 v3.69.0 --stat -- backend frontend ':!backend/tests' ':!frontend/tests'`
   → **2 ficheros / 2 líneas**: `backend/config.py` (`VERSION` `3.68.0 → 3.69.0`) y
   `frontend/package.json` (misma cadena), más `frontend/package-lock.json`.
   *Falsado por*: cualquier otra línea de producto.
2. **SIN migración.** `git diff v3.68.0 v3.69.0 -- backend/repositories/db.py` vacío
   y **ningún** `CREATE TABLE`/`ALTER TABLE` nuevo respecto a V3.68.
3. **Política y contenido intactos.** `DECISION_POLICY_VERSION = "v3.68.0"`
   (`backend/repositories/decision_records.py:61`) y los tres
   `GENERATOR_VERSION` (`services/dictionary_content.py:74` = `"1.4.0"`,
   `services/listening_generate.py:35`, `services/speaking_generate.py:30`) **sin
   diff** contra `v3.68.0`.
4. **La batería son 20 tests** (`Select-String "^def test_"` → 20) y **ninguno
   necesita red**: `TestClient(app)` sobre `main.app` con BD aislada por
   `monkeypatch` (`DATA_DIR`/`DB_PATH`, líneas 78-79).
5. **Contrato público, con dos excepciones DECLARADAS.** Salvo **E15**
   (`decision_records_repo.close_stale(...)` invocado directamente, línea 756 —
   control del reloj del barrido) y **E18(b)** (reproducción en proceso del TOCTOU
   con `monkeypatch` y `evidence_fingerprint`, líneas 933-972), el resto afirma
   sobre HTTP. *Falsado por*: una tercera incursión no declarada en internals.
6. **E16 es determinismo de verdad y en dos niveles**: puro
   (`planner.select_task_by_elv` en 786 y `expected_learning_value` en 790) y HTTP
   (repetición de `GET /api/learning/review` comparando `decision_id`,
   `expected_learning_value`, `decision_start_fingerprint` y `state_fingerprint`,
   815-817). *Falsado por*: uso de reloj real, `random()` o `hash()` en el camino
   afirmado.
7. **E05 fija la identidad de tarea por HTTP**: misma tarea en dos contextos ⇒
   **mismo `task_key` y distinto `task_instance_key`**.
8. **E01(a) declara el límite, no lo esconde**: con un alumno **sin ninguna celda
   medida** la cola sirve la tarea pero **no** hay bloque `decision` ni
   `decision_id` (puerta `has_comparable_capacity`,
   `services/decision_projection.py:387`). El circuito se demuestra **desde que hay
   estado medible** (E01(b) y el resto de la batería).
9. **E08 fija una asimetría de observabilidad**:
   `calibration["abandoned_count"] == 0` (línea 592) aunque la fila quede
   `decision_status = "abandoned"`, porque el informe solo carga filas `completed`
   y ese contador cuenta **otra cosa** (`outcome = "abandoned"`, alcanzable por el
   camino interno: `backend/tests/test_decision_v368.py:675` lo fija con valor 1).
   El abandono está **correctamente fuera del denominador** y, a la vez,
   **invisible** en el informe.
10. **E15: una servida caducada se REABRE.** La constante de reapertura es
    `PROVENANCE_REOPENED = "reopened"`
    (`repositories/decision_records.py:118`) y el test exige que el registro final
    **nunca** sea `completed` (el estado es final, no historia: P2-04).
11. **E17 mide la dirección real del andamiaje.** `SCAFFOLDING_PENALTY = 0.2`
    (`services/decision_projection.py:83`) y la aserción es **diferencial**: el
    gemelo con hueco servido − acreditado recibe `expected_learning_value`
    **MAYOR** (`assert item_a[...] > item_b[...]`, línea 929). Es decir: el nombre
    «penalty» describe **perjuicio en el diagnóstico** (pesa en la elección de
    modalidad), **no** descuento en la puntuación.
12. **§F-1 es un defecto del cliente, no del servidor.** `wordDrill.tsx` declara
    `started` **solo** cuando el peldaño ya está cargado y una vez por montaje
    (`!decisionId || !rungLoaded || startedDeclaredRef.current`, líneas 465-468),
    pero declara `abandoned` con **solo** tener `decisionId`, **sin** comprobar
    `rungLoaded` (líneas 470-478). Con el doble montaje de `StrictMode` (el
    launcher sirve `npm run dev`) eso dispara un `abandoned` **antes** de que nada
    se sirva, y la FSM del servidor lo **rechaza** por transición inválida
    (`_ALLOWED_TRANSITIONS`, `repositories/decision_records.py:81`;
    contador `invalid_transition`).
13. **El `decision_id` viaja de verdad en el cliente**:
    `frontend/src/api/vocabulary.ts` lo reenvía en query (`params.decision_id`,
    líneas 102/153/205/281) y en body (`decision_id`, 181/234/261/317), con
    `markDrillStarted`/`markDrillAbandoned` en 356/368. Sin id, el helper **no
    postea** (`if (!decisionId) return false;`, 336). La spec de navegador lo fija
    con red mockeada (`drillProvenance.spec.ts:215` y `:276`; `test.skip` por
    viewport en 218/279).
14. **Los números del release salen del run, no del propio incremento:** Backend →
    `2550 passed, 2 skipped in 357.50s` (job `104411344275`); Frontend → **659
    tests** + `build` (job `104411344226`); Playwright → **25 passed + 26
    skipped** (job `104411343956`, incluidas las 2 specs nuevas en verde). En
    local el mismo árbol da **2552 passed**: los 2 `skipped` son
    `backend/tests/test_stt_asr_integration.py` (modelo Whisper opt-in no
    descargado en el runner).
15. **Coherencia documental:** `python scripts/check_release_consistency.py` →
    `OK: Release consistency (3.69.0) en todos los orígenes`; `docs/RELEVO.md`
    lleva la nota de V3.69 con su bloque **CIERRE**; `CHANGELOG.md` la entrada
    `[3.69.0]`; y `release-notes-v3.69.0.md` la tabla §C de hallazgos.

## Cómo reproducir la batería (comandos exactos)

```powershell
# Backend (puerta de lint del CI + batería + suite completa + gate de transferencia)
cd backend
python -m ruff check .                                  # All checks passed
python -m pytest tests/test_adaptive_e2e_v369.py -q     # 20 passed
python -m pytest tests/ -q                              # 2552 passed (local); en CI 2550 + 2 skipped
python -m scripts.transfer_validation                    # OK=True

# Frontend
cd ..\frontend
npx tsc --noEmit                                        # OK
npm test                                                # 76 ficheros / 659 tests
npm run build                                           # OK
npx playwright test --grep "decision_id"                # las 2 specs nuevas (proyecto desktop)

# Gates de script
cd ..
python scripts/check_release_consistency.py              # OK (3.69.0)
python scripts/check_beta_v3.py                          # OK
cd backend; python scripts/content_validation.py         # OK=True quality=True
```

**Dos avisos que el proyecto declara en vez de esconder** (§G-1 y §G-2 de la
release note, y aquí se ofrecen al auditor como material de dictamen):

- **§G-1** `ruff format --check` **no** es un gate del CI (`ci.yml` corre solo
  `ruff check .`) y el árbol arrastra deriva de formato **preexistente** en
  ficheros que V3.69 no ha tocado (`services/transfer_audit.py`,
  `services/decision_projection.py`, `config.py`…). El proyecto **no** lo declara
  limpio: lo declara **medido**.
- **§G-2** `resize.spec.ts` (preexistente) es **intermitente en local** (pasa
  aislado, falla en tandas; reproducible **excluyendo** la spec nueva con
  `npx playwright test --grep-invert decision_id`). En el **CI del release salió
  verde**, así que el proyecto lo acota al entorno local.

## Preguntas de alto valor

1. ¿La batería **demuestra** el circuito —cada aserción fallaría si el
   comportamiento declarado no se cumple— o solo lo **ejercita** y comprueba
   campos?
2. **E01(a)**: ¿es aceptable que el «circuito de un extremo al otro» **no** exista
   en arranque en frío (sin `decision` ni `decision_id`), o la afirmación de la
   auditoría `Y` de que el circuito está cubierto «desde el primer minuto» queda
   **contradicha** y debe reclasificarse?
3. **E08**: un abandono real del ciclo de vida **no aparece** en el informe de
   calibración. ¿Es deuda P2 de observabilidad (como se declara) o un **P1** de
   medición —el sistema no puede contar lo que sí registra—?
4. **E15**: la reapertura de una servida caducada, ¿contradice el contrato que
   V3.68 declaró («el upsert REABRE una fila terminal sin outcome medible») o es
   exactamente lo declarado y el test lo confirma?
5. **E17**: que `SCAFFOLDING_PENALTY` **sume** al hueco en lugar de descontar,
   ¿es un problema de **nombre** (como se declara) o un defecto de **semántica
   pública** que puede inducir a un ingeniero a invertir una decisión futura?
6. **§F-1**: el `abandoned` prematuro del `StrictMode`, ¿es puramente un contador
   de salud «sucio» o puede **ocultar** transiciones inválidas reales al mezclarse
   con rechazos legítimos en `transition_health()`?
7. ¿Algún escenario **pasa sin demostrar nada**: aserción tautológica, valor
   sembrado para que coincida, o comparación entre dos valores que el propio test
   calcula con la misma función que se audita?
8. La **excepción de E15** (llamar a `close_stale` en proceso para controlar el
   reloj), ¿es admisible, o el barrido debería ser verificable por HTTP con un
   reloj inyectable?
9. La **mitad (b) de E18** (TOCTOU con `monkeypatch`), ¿es un test de contrato o
   un test de implementación disfrazado? ¿Su valor justifica la excepción?
10. El **contrato de frontend** con red mockeada, ¿demuestra el round-trip real
    `started`/`abandoned` o deja el eslabón crítico (el que V3.68 tuvo que
    arreglar) verificado solo contra un mock escrito por el propio proyecto?
11. La afirmación «la arquitectura es **suficiente**», ¿resiste tras ver los cinco
    hallazgos, o alguno demuestra que **falta capacidad** (no solo rigor)?
12. ¿Hay riesgo de que esta release de validación **se haya convertido** en una
    release de arquitectura por la puerta de atrás (helpers nuevos, constantes,
    umbrales, dobles de test que fijan contratos no declarados)?
13. ¿La **deuda declarada** (P2-01…P2-06, P3-01, P3-02 y §F-1) está completa, o
    queda alguna desviación **no** registrada en la tabla §C?

## Formato del informe

Sigue `docs/audit/TEMPLATE.md` y el patrón de las auditorías `S`/`T` (V3.60),
`W` (V3.63) y `X`/`Y` (V3.67/V3.68): `Alcance` · `Método` · `Evidencia` ·
`Hallazgos` (`| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`)
· `Veredicto` · `Regenerar / Verificar`.

**Requisitos adicionales:**

1. **Dictamen por escenario** (E01–E19 + E16b): *demuestra* / *demuestra con
   matiz* / *no demuestra* / *excesivo*, con una línea de motivo y, donde
   aplique, la aserción que faltaría.
2. **Dictamen de los cinco hallazgos de §C** (E01(a), E08, E15, E17, §F-1):
   *aceptado como deuda* / *promovido a P2* / *promovido a P1*, con motivo.
3. **Dictamen del alcance del diff**: confirmado «cero lógica de producto» o
   corregido con `archivo:línea`.
4. **Dictamen de §G-1 y §G-2**: ¿son hallazgos del release o ruido de entorno?
5. **Veredicto de una línea** apto para publicar: *¿se acepta `v3.69.0` como base
   para V3.70 (auditoría pedagógica), con o sin condiciones?*
6. Severidades `P0`/`P1`/`P2`/`P3` con `alta`/`media`/`baja`/`documental` y
   evidencia `archivo:línea`. Distinguir **«el test no demuestra»** de **«el motor
   no cumple»**: son hallazgos distintos y con destinatarios distintos.

## Checklist de cierre del auditor

- [ ] El diff de producto contra `v3.68.0` es **solo** bumps de versión.
- [ ] La batería se reproduce en local (20 tests) y la suite completa da el número
      declarado (2552 local / 2550 + 2 skipped en CI).
- [ ] Las **dos** excepciones declaradas (E15, E18b) son las **únicas**.
- [ ] CI del release comprobado en la API de GitHub (6/6, job ids y conteos).
- [ ] Los cinco hallazgos de §C están dictaminados **uno a uno**.
- [ ] Existe al menos un juicio explícito sobre **E16 (determinismo)** y sobre
      **E05 (task vs task instance)**, que son las afirmaciones que sostienen el
      resto de la demostración.
- [ ] El veredicto distingue **capacidad** de **rigor**: V3.69 no añade capacidad.
