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
antes de implementarlo, y en particular si la batería **E01–E16** demuestra de
verdad el circuito adaptativo completo o deja fuera escenarios obligatorios.

**El auditor no audita código de V3.69: audita el plan de V3.69.**

## Alcance y enfoque

1. Revisar el **briefing** `agentes/v369-e2e-adaptive-validation.md` completo:
   rol, objetivo, estado de partida, decisiones de alcance, diseño (§A–§F),
   tests, criterios de salida, fuera de alcance y checklist de cierre.
2. Auditar la **batería E01–E16**: si cada escenario tiene una aserción
   **verificable**, si el conjunto es **suficiente** (no deja huecos) y si es
   **proporcionado** (no sobreingeniería para una release de validación).
3. Comprobar la **cobertura frente a los 10 casos originales** de la auditoría `X`
   de V3.67 (§16 de `docs/audit/X-AUDITORIA-TOTAL-V367.md`), usando la tabla de
   mapeo declarada más abajo y dictaminando sobre los **huecos declarados**.
4. Verificar que las **afirmaciones sobre el estado de partida** son ciertas
   contra el árbol `3.68.0`: que la infraestructura de tests declarada (patrón
   `TestClient` + `monkeypatch` de la BD, helpers de siembra, *fake* de ASR,
   fechas fijas) **existe y es suficiente** para montar los 16 escenarios; y que
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
   explícitamente sobre los tres huecos declarados.

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

El diseño declara que E01–E16 **sustituyen y amplían** los 10 casos de la
auditoría `X`. **El auditor debe dictaminar sobre esta tabla**, que el proyecto
publica **con sus propios huecos señalados**:

| Caso original (auditoría `X` §16) | Escenario que lo cubre | Dictamen del proyecto |
|---|---|---|
| (1) alumno nuevo / sin historial | **E01** | cubierto |
| (2) recall fuerte / speaking débil | **E02** | cubierto |
| (3) **alta dependencia de apoyo** | **—** | **HUECO**: ningún escenario ejerce `support_level`/`scaffolding_gap` |
| (4) mala retención | **E03** | cubierto |
| (5) fallos repetidos | **E06** | cubierto (`ok, ok, ko`) |
| (6) domina una tarea pero no transfiere | **E04** | cubierto |
| (7) ASR `unclear` | **E07** | cubierto |
| (8) **dos usuarios simultáneos** | **E12** | **PARCIAL**: E12 prueba *propiedad ajena rechazada*, no *aislamiento y coexistencia de dos alumnos activos* |
| (9) refresh repetido de la cola | **E09** | cubierto (y ampliado con E10/E11, E14) |
| (10) **evidencia entrando DURANTE la decisión** | **—** | **HUECO**: es el TOCTOU/snapshot que cerraron V3.64.1 y V3.68 (P2 de la auditoría `X` §11) y **no tiene escenario** |

**Aportaciones nuevas** de E01–E16 sobre los 10 casos: `E05` (task vs task
instance por HTTP), `E08` (abandono sin contaminar `ko`), `E11` (submit
contradictorio), `E13` (target ajeno), `E15` (serving stale) y `E16`
(determinismo del Planner), todas ellas exigidas por las auditorías `X`/`Y`.

**Pregunta central para el auditor:** ¿los huecos (3) y (10) **deben** cerrarse
en V3.69, o pueden declararse fuera de alcance sin que la validación E2E deje de
ser concluyente? Y en el caso de (8), ¿E12 basta como evidencia de aislamiento?

## Consideraciones

- **No se re-audita V3.68.** El código de `v3.68.0` ya fue auditado (dossier `Y`);
  aquí se usa **solo** para comprobar que el plan de V3.69 es **montable** con lo
  que existe.
- **La numeración P2/P3 del dossier `Y` es una derivación del proyecto** y así
  está etiquetada; su validación es parte explícita de esta auditoría.
- Se trata como **hallazgo** cualquier escenario E01–E16 que: (a) no sea
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
   `transcribe_with_timing`) **existe** y **basta** para montar los 16 escenarios.
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

## Preguntas de alto valor

1. ¿Los huecos (3) alta dependencia de apoyo y (10) evidencia durante la decisión
   **invalidan** la validación E2E, o son diferibles a V3.70 con justificación
   escrita?
2. ¿E12 es evidencia suficiente de **aislamiento entre usuarios**, o hace falta
   un escenario de dos alumnos activos sobre la misma BD?
3. ¿E16 debe cubrir también el **determinismo del orden de la cola** con
   empates reales (`-ELV, -priority, retrievability, word`), o basta con
   repeticiones sobre una única decisión?
4. ¿Algún escenario está **redactado de forma que pueda pasar sin demostrar
   nada** (aserción vacía, tautológica o dependiente de un valor que el propio
   test siembra para que coincida)?
5. ¿La separación **contrato de backend (E01–E16) / contrato de frontend con
   mocks** deja sin verificar el **round-trip real** `started`/`abandoned`, que es
   justamente el eslabón que V3.68 tuvo que arreglar?
6. ¿V3.69 debe además **arreglar** lo que un escenario descubra, o basta con
   registrarlo como hallazgo? ¿Es coherente la regla de excepción con el proceso
   de release del proyecto?
7. ¿Es suficiente el criterio de salida «E01–E16 verdes + gates», o falta un
   criterio de **cobertura** (p. ej. que la suite nueva ejecute el camino
   `decision_records` de principio a fin por HTTP)?
8. ¿La numeración P2/P3 derivada resiste la comprobación de que el informe
   original declara `6 P2 / 5 P3`?
9. ¿El checklist de cierre cubre todos los puntos que
   `scripts/check_release_consistency.py` exige (primera coincidencia por
   fichero)?
10. ¿Hay algún riesgo de que la release de validación **se convierta** en una
    release de arquitectura (el riesgo que la auditoría `Y` §28 advirtió)?

## Formato del informe

Sigue la plantilla de `docs/audit/TEMPLATE.md` más el patrón de las auditorías
`S`/`T` de V3.60 y `X`/`Y` de V3.67/V3.68: `Alcance` · `Método` · `Evidencia` ·
`Hallazgos` (`| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`)
· `Veredicto` · `Regenerar / Verificar`.

**Requisitos adicionales de este informe:**

1. Una tabla explícita de **dictamen por escenario** (E01–E16): *aceptado tal
   cual* / *aceptado con matiz* / *insuficiente* / *excesivo*, con una línea de
   motivo.
2. Un **dictamen sobre los tres huecos** declarados (casos 3, 8 y 10), con
   recomendación de acción: **añadir escenario**, **declarar fuera de alcance con
   motivo**, o **mover a V3.70+**.
3. Un **dictamen sobre la tabla P2/P3** del dossier `Y` §30: confirmada o
   corregida, con la frontera propuesta.
4. Un **veredicto de una línea** apto para publicar: *¿se autoriza implementar
   V3.69 tal cual, con cambios, o no se autoriza?*
5. Etiquetar los hallazgos `P0`/`P1`/`P2`/`P3` con severidad
   `alta`/`media`/`baja`/`documental` y `archivo:línea` como evidencia. Los
   hallazgos de diseño deben distinguir **«el plan está mal»** de **«el plan está
   bien pero el motor no lo permitiría»**.
