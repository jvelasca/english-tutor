# Auditoría EXTERNA de DISEÑO de V3.69 — punto de entrada (listo para lanzar)

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite el **DISEÑO** del
> siguiente incremento **antes de que se implemente**. La revisión es **de solo
> lectura**: no se cambia código, datos, configuración ni etiquetas publicadas.
>
> **Por qué una auditoría de DISEÑO y no de release.** **`v3.69.0` todavía no
> existe.** El HEAD documental es `f86addc` y la versión estable sigue siendo
> **`3.68.0`** (`backend/config.py:32`), sin tag `v3.69*`, sin
> `release-notes-v3.69.0.md` y sin `backend/tests/test_adaptive_e2e_v369.py`.
> Lo que existe es el **plan** de V3.69, y el objetivo es que el auditor lo valide
> **antes** de que se gaste esfuerzo en implementarlo, tal como pidió el gerente
> tras la auditoría `Y`.
>
> **Estado:** entregado 2026-09-15. **Informe esperado:**
> `docs/audit/Z-AUDITORIA-DISENO-V369.md` (letra `Z`; la `V` sigue **reservada**
> al informe externo de V3.62, que nunca se publicó, y la `Y` la usó la auditoría
> de V3.68).

## Objetivo

Dictaminar si **el diseño de V3.69 es el correcto, suficiente y verificable**
antes de implementarlo, y en particular si la batería **E01–E19** demuestra de
verdad el circuito adaptativo completo o deja fuera escenarios obligatorios.

**El auditor no audita código de V3.69: audita el plan de V3.69.**

## Alcance y enfoque

1. Revisar el **briefing** `agentes/v369-e2e-adaptive-validation.md` completo:
   rol, objetivo, estado de partida, decisiones de alcance, diseño (§A–§F),
   tests, criterios de salida, fuera de alcance y checklist de cierre.
2. Auditar la **batería E01–E19**: si cada escenario tiene una aserción
   **verificable**, si el conjunto es **suficiente** (no deja huecos) y si es
   **proporcionado** (no sobreingeniería para una release de validación).
3. Comprobar la **cobertura frente a los 10 casos originales** de la auditoría `X`
   de V3.67 (§16 de `docs/audit/X-AUDITORIA-TOTAL-V367.md`), usando la tabla de
   mapeo declarada más abajo y dictaminando sobre la **calidad del cierre** de los
   tres casos que el proyecto había detectado como huecos (3), (8) y (10).
4. Verificar que las **afirmaciones sobre el estado de partida** son ciertas
   contra el árbol `3.68.0`: que la infraestructura de tests declarada (patrón
   `TestClient` + `monkeypatch` de la BD, helpers de siembra, *fake* de ASR,
   fechas fijas) **existe y es suficiente** para montar los 19 escenarios; y que
   las rutas, firmas y números de línea citados son correctos.
5. Comprobar que los **criterios de salida** son verificables y no
   auto-referenciales, y que la **regla dura** («V3.69 no introduce arquitectura
   nueva salvo que un escenario E2E demuestre que la arquitectura actual es
   insuficiente») es **satisfacible** con el diseño propuesto.
6. Auditar el **criterio de derivación P2/P3** del dossier
   `docs/audit/Y-AUDITORIA-TOTAL-V368.md` §30: si es fiel al informe del auditor
   o si fuerza la cuenta `6 P2 / 5 P3` moviendo hallazgos de severidad.
7. Entregar hallazgos **de alta confianza**, priorizados, con
   `archivo:línea` de evidencia, impacto y **corrección concreta**; y dictaminar
   explícitamente sobre las **tres decisiones discutibles** de E17/E18/E19
   declaradas más abajo.

## Punto de entrada

- Repositorio: `jvelasca/english-tutor` (público).
- **Revisión a auditar:** HEAD de `main` = `f86addc`
  (documentación); base `d5311cc` (**cierre documental de `v3.68.0`**).
- **Versión estable vigente:** `v3.68.0` → release commit `8acee38`, tag
  `v3.68.0`. **No existe tag `v3.69.0`.** Auditarse como diseño, no como release.
- **Objetos de la auditoría (rutas exactas):**
  - `agentes/v369-e2e-adaptive-validation.md` (el briefing: objeto principal).
  - `docs/audit/Y-AUDITORIA-TOTAL-V368.md` (§28 regla dura, §30 tabla P2/P3).
  - `docs/audit/X-AUDITORIA-TOTAL-V367.md` (§16: los 10 casos originales).
  - `PLAN.md` («Siguiente incremento» y M13) y la nota de cabecera de
    `docs/RELEVO.md`.
- **Código de referencia (solo para verificar que el plan es montable):** el
  propio de `v3.68.0`, es decir `backend/`, `frontend/`, `.github/workflows/ci.yml`
  y `scripts/`.
- Run de CI del cierre de V3.68 declarado como **6/6** en
  `34964205252`; si la API de GitHub no devuelve runs verificables, el auditor
  debe declararlo como **documental** (así lo hizo la auditoría `Y`).

## Cobertura declarada frente a los 10 casos de la auditoría `X`

El diseño declara que E01–E19 **sustituyen y amplían** los 10 casos de la
auditoría `X`. **El auditor debe dictaminar sobre esta tabla**, incluida la
**calidad** del cierre de los tres casos que el proyecto detectó como huecos al
preparar esta auditoría y cerró añadiendo **E17, E18 y E19**:

| Caso original (auditoría `X` §16) | Escenario que lo cubre | Estado declarado |
|---|---|---|
| (1) alumno nuevo / sin historial | **E01** | cubierto |
| (2) recall fuerte / speaking débil | **E02** | cubierto |
| (3) **alta dependencia de apoyo** | **E17** | **cerrado en el diseño**: hueco servido − acreditado → penalización declarada (`SCAFFOLDING_PENALTY = 0.2`) |
| (4) mala retención | **E03** | cubierto |
| (5) fallos repetidos | **E06** | cubierto (`ok, ok, ko`) |
| (6) domina una tarea pero no transfiere | **E04** | cubierto |
| (7) ASR `unclear` | **E07** | cubierto |
| (8) **dos usuarios simultáneos** | **E12 + E19** | **cerrado en el diseño**: E12 = propiedad ajena **rechazada**; E19 = **coexistencia** de dos alumnos activos sin mezcla, verificada **en ambas direcciones** |
| (9) refresh repetido de la cola | **E09** | cubierto (y ampliado con E10/E11, E14) |
| (10) **evidencia entrando DURANTE la decisión** | **E18** | **cerrado en el diseño**: contrato de frescura por HTTP + reproducción determinista del TOCTOU de V3.64.1 |

**Aportaciones nuevas** de E01–E19 sobre los 10 casos: `E05` (task vs task
instance por HTTP), `E08` (abandono sin contaminar `ko`), `E11` (submit
contradictorio), `E13` (target ajeno), `E15` (serving stale) y `E16`
(determinismo del Planner), todas ellas exigidas por las auditorías `X`/`Y`.

**Tres puntos que el auditor debe examinar con lupa** (el proyecto los declara
como decisiones discutibles, no como certezas):

1. **E17 afirma una DIFERENCIA, no un valor.** El hueco servido − acreditado
   gobierna la decisión (penalización declarada), pero **no** se expone por HTTP:
   el ítem de la cola publica `served_load = dict(task_difficulty)`
   (`services/lexicon.py:949`), no el bloque `load` de la proyección donde vive
   `scaffolding_gap` (`services/decision_projection.py:298`). Por eso E17 usa
   **escenarios gemelos** que solo difieren en `served_ceiling` vs
   `credited_ceiling`. ¿Es aceptable una aserción diferencial, o el diseño
   debería exigir que el hueco sea visible en el contrato de la cola?
2. **E18 tiene una mitad que toca internals.** La mitad (b) reproduce el TOCTOU
   **en proceso** (`monkeypatch` del lector de evidencia para insertar una fila
   durante la lectura) porque intercalar por HTTP de forma determinista no es
   viable. ¿Es admisible esta excepción a la regla «afirmar sobre contrato
   público», o el diseño debe quedarse solo con la mitad HTTP y declarar el resto
   como no verificable por E2E?
3. **E19 vs E12.** El proyecto sostiene que son dos mitades complementarias
   (rechazo de lo ajeno vs coexistencia sin mezcla). ¿Basta E12, o es correcto
   que la validación E2E exija además E19?

## Consideraciones

- **No se re-audita V3.68.** El código de `v3.68.0` ya fue auditado (dossier `Y`);
  aquí se usa **solo** para comprobar que el plan de V3.69 es **montable** con lo
  que existe.
- **La numeración P2/P3 del dossier `Y` es una derivación del proyecto** y así
  está etiquetada; su validación es parte explícita de esta auditoría.
- Se trata como **hallazgo** cualquier escenario E01–E19 que: (a) no sea
  verificable con contrato público, (b) exija tocar internals o añadir relojes
  inyectables, (c) obligue a **cambiar arquitectura** (lo que contradiría la
  regla dura), o (d) afirme un comportamiento que el contrato de V3.68 **no**
  garantiza.
- Se trata igualmente como hallazgo cualquier **afirmación falsa sobre el estado
  de partida** (infraestructura, rutas, líneas, cobertura de tests).

## Afirmaciones a falsar

1. La infraestructura declarada (`TestClient` sobre `main.app`, `_setup` con
   `monkeypatch` de `repositories.db`, auth por `?user_id=`, helpers
   `_seed_word`/`_seed_evidence`/`_due_lexicon_card`/`_record`, *fake* de
   `transcribe_with_timing`) **existe** y **basta** para montar los 19 escenarios.
2. Hoy **ningún** test cierra por HTTP el tramo
   `cola → GET peldaño (decision_id) → POST intento → outcome → calibración`, y
   `GET /api/learning/decisions` **no** aparece en ningún test (falsable por
   búsqueda en `backend/tests/`).
3. Cada escenario tiene **una aserción principal verificable** y **ninguno**
   necesita afirmar sobre estructuras internas sin contrato público, salvo donde
   el briefing lo justifica por no existir lectura pública equivalente.
4. **Ningún escenario exige arquitectura nueva**: la regla dura es satisfacible
   con el motor congelado en V3.68.
5. **E16 es comprobable de forma determinista** sin reloj real, sin `random()` y
   sin `hash()`, tanto en la función pura como por HTTP (depende del desempate
   canónico de la cola).
6. Los **criterios de salida** son verificables con los gates existentes y no
   dependen de cifras que el propio incremento se auto-imponga.
7. El **contrato de frontend** se puede fijar con red mockeada porque el job
   `playwright` de CI **no** levanta backend (falsable en
   `.github/workflows/ci.yml` y `frontend/playwright.config.ts`).
8. Los **números de línea y rutas** citados en el briefing corresponden al árbol
   `3.68.0`.
9. El **criterio de derivación P2/P3** del dossier `Y` §30 es fiel al informe del
   auditor y **no** reinterpreta severidades.
10. La batería **no** introduce umbrales nuevos, migraciones, cambios de
    `GENERATOR_VERSION` ni de `DECISION_POLICY_VERSION`.
11. **E17** es montable sin exponer nada nuevo: el hueco servido − acreditado
    gobierna la decisión por la penalización declarada
    (`SCAFFOLDING_PENALTY = 0.2`) y la aserción **diferencial** basta para
    demostrarlo (falsable: si el hueco no gobierna, los gemelos empatan).
12. **E18** (mitad b) reproduce el TOCTOU **sin** cambiar producción, y el sello
    con huella desajustada **nunca** se declara fresco (`_SEAL_MAX_ATTEMPTS = 3`,
    `evidence_fingerprint`).
13. **E19** demuestra aislamiento **en las dos direcciones**: ni B ve lo de A, ni
    A deja de ver lo suyo tras la actividad de B.

## Preguntas de alto valor

1. Una vez cerrados los huecos con E17/E18/E19, ¿**queda alguno** de los 10 casos
   de `X` cubierto solo de forma nominal (el test existe pero no demuestra la
   propiedad)?
2. ¿E17 debe bastar con una aserción **diferencial** sobre `ELV`/`priority`, o el
   diseño debería **exigir** que el hueco servido − acreditado sea visible en el
   contrato de la cola (hoy `served_load` publica la dificultad de tarea, no el
   bloque `load` de la proyección)?
3. ¿Es admisible que la mitad (b) de **E18** toque internals con `monkeypatch`
   para reproducir el TOCTOU, o la validación E2E debe limitarse a contrato
   público y declarar el resto como no verificable?
4. ¿E12 + E19 bastan para el caso (8), o hace falta además **concurrencia real**
   (dos peticiones simultáneas) y no solo intercalado determinista?
5. ¿E16 debe cubrir también el **determinismo del orden de la cola** con
   empates reales (`-ELV, -priority, retrievability, word`), o basta con
   repeticiones sobre una única decisión?
6. ¿Algún escenario está **redactado de forma que pueda pasar sin demostrar
   nada** (aserción vacía, tautológica o dependiente de un valor que el propio
   test siembra para que coincida)?
7. ¿La separación **contrato de backend (E01–E19) / contrato de frontend con
   mocks** deja sin verificar el **round-trip real** `started`/`abandoned`, que es
   justamente el eslabón que V3.68 tuvo que arreglar?
8. ¿V3.69 debe además **arreglar** lo que un escenario descubra, o basta con
   registrarlo como hallazgo? ¿Es coherente la regla de excepción con el proceso
   de release del proyecto?
9. ¿Es suficiente el criterio de salida «E01–E19 verdes + gates», o falta un
   criterio de **cobertura** (p. ej. que la suite nueva ejecute el camino
   `decision_records` de principio a fin por HTTP)?
10. ¿La numeración P2/P3 derivada resiste la comprobación de que el informe
    original declara `6 P2 / 5 P3`?
11. ¿El checklist de cierre cubre todos los puntos que
    `scripts/check_release_consistency.py` exige (primera coincidencia por
    fichero)?
12. ¿Hay algún riesgo de que la release de validación **se convierta** en una
    release de arquitectura (el riesgo que la auditoría `Y` §28 advirtió)?

## Formato del informe

Sigue la plantilla de `docs/audit/TEMPLATE.md` más el patrón de las auditorías
`S`/`T` de V3.60 y `X`/`Y` de V3.67/V3.68: `Alcance` · `Método` · `Evidencia` ·
`Hallazgos` (`| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`)
· `Veredicto` · `Regenerar / Verificar`.

**Requisitos adicionales de este informe:**

1. Una tabla explícita de **dictamen por escenario** (E01–E19): *aceptado tal
   cual* / *aceptado con matiz* / *insuficiente* / *excesivo*, con una línea de
   motivo.
2. Un **dictamen sobre el cierre de los casos (3), (8) y (10)** —los tres que el
   proyecto detectó como huecos y cerró con E17, E18 y E19—, con recomendación de
   acción: **aceptar el escenario nuevo**, **reformularlo**, **declararlo fuera
   de alcance con motivo** o **mover a V3.70+**.
3. Un **dictamen sobre la tabla P2/P3** del dossier `Y` §30: confirmada o
   corregida, con la frontera propuesta.
4. Un **veredicto de una línea** apto para publicar: *¿se autoriza implementar
   V3.69 tal cual, con cambios, o no se autoriza?*
5. Etiquetar los hallazgos `P0`/`P1`/`P2`/`P3` con severidad
   `alta`/`media`/`baja`/`documental` y `archivo:línea` como evidencia. Los
   hallazgos de diseño deben distinguir **«el plan está mal»** de **«el plan está
   bien pero el motor no lo permitiría»**.
