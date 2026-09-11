# Briefing de auditoría EXTERNA — V3.50.0 (Context→Skill mapping + difficulty matching)

> **Para quién:** un agente/auditor EXTERNO que solo tiene acceso al repositorio
> público de GitHub (no al chat del gerente ni al historial de la sesión).
> **Qué entregar:** un informe siguiendo `docs/audit/TEMPLATE.md`, propuesto como
> `docs/audit/Q-AUDITORIA-TOTAL-V350.md`.

## Punto de entrada (todo desde GitHub)

- **Repositorio:** https://github.com/jvelasca/english-tutor (público).
- **Release auditada:** tag **`v3.50.0`** → commit `1c8d6e0` («release(v3.50.0):
  Context->Skill mapping + difficulty matching»).
- **HEAD de `main` (incluye el commit de evidencia de CI):** `7d9597f`.
- **CI del release:** run
  [34594042697](https://github.com/jvelasca/english-tutor/actions/runs/34594042697)
  sobre `1c8d6e0`, **6/6 jobs en success** (Release consistency, Backend
  ruff+pytest, Frontend tsc+vitest+build, Playwright E2E, Beta V3.0 gate, Content
  validation). El commit de evidencia `7d9597f` tiene su propio run en verde.
- **Documento de resultado (fuente de verdad de lo que se afirma):**
  `release-notes-v3.50.0.md`. Briefing previo (planificación): 
  `agentes/v350-context-skill-mapping.md`.

## Contexto: qué es V3.50 y qué reemplaza

Hasta V3.49, `services/transfer.py::context_for` elegía el contexto de
transferencia mirando solo (1) contextos ya usados, (2) CEFR alcanzable
(`_within_level`, V3.47) y (3) novedad respecto a los contextos logrados
(V3.43). El banco declaraba `cefr` y `difficulty_vector` (V3.47) y el planner ya
calculaba una modalidad limitante (`limiting_skill`), pero **ninguno de esos
datos decidía nada**.

V3.50 introduce dos cambios de comportamiento, declarados como **aditivos** y
**sin migración de BD**:

- **Context→Skill mapping:** cada contexto declara `skills` (subconjunto de
  `CONTEXT_SKILLS`) y `context_for` acepta `skill` (derivada del planner) y la
  prefiere.
- **Difficulty matching:** con un `level` reconocible, `context_for` prefiere
  contextos dentro de una banda de dificultad (`TRANSFER_DIFFICULTY_BAND`) para
  no servir el contexto más plano del banco a un alumno avanzado.

## Alcance de la auditoría (qué juzgar)

**Dentro:** `services/transfer.py` (banco, `skills`, `context_skills`,
`_filter_skill`, `_difficulty_floor`, `_within_band`, `context_for`),
`domain/vocabulary.py` (`_transfer_target_skill` y sus dos puntos de uso),
`schemas/vocabulary.py` (`TransferContextOut.skills`),
`frontend/src/types/api.ts` (`DrillTransferContext.skills?`) y los tests
`backend/tests/test_context_skill_v350.py` + `test_transfer_cefr_v347.py`.

**Fuera:** Sense Engine 2.0, semantic appropriateness (punto 7),
`expected_learning_value` / Adaptive Planner 2.0, persistencia de la dificultad
por evento, y cualquier cambio en `transfer_state`/umbrales (V3.46/V3.47), FSRS,
Evidence Ledger, scoring (`score_transfer_attempt`) o la CONSTITUCIÓN (R8/R9
sigue como propuesta abierta). Si un hallazgo cae aquí, márcalo como
«fuera de alcance/diferido», no como P0.

## Método reproducible (clona en el tag)

```powershell
git clone https://github.com/jvelasca/english-tutor.git
cd english-tutor
git checkout v3.50.0

# Backend
cd backend
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest tests/ -q

# Frontend
cd ../frontend
npm ci
npx tsc --noEmit
npm test
npm run build

# Gates del repo
cd ..
python scripts/check_release_consistency.py   # debe imprimir 3.50.0
python scripts/check_beta_v3.py
python backend/scripts/content_validation.py
```

Cifras declaradas que debes poder reproducir: pytest **2099 passed** (+15),
`ruff` limpio, vitest **75 ficheros/641 tests**, `tsc`/`build` limpios,
`check_release_consistency` **3.50.0** exit 0.

## Preguntas concretas que debe responder el informe

1. **Contratos.** ¿Los cambios son estrictamente aditivos y retrocompatibles?
   ¿Algún cliente existente se rompe? ¿`skills` viaja en el GET y en el POST?
2. **Cero regresión de la escalera.** ¿Se ha tocado algún umbral o lógica de
   `transfer_state`, `context_signals`, `context_diversity`, scoring o FSRS?
   Contrasta con `services/evidence.py` y `services/lexicon.py`.
3. **Semántica de la banda.** El objetivo es
   `max(techo de dificultad alcanzable, cefr_index(level) + 1)` y el mínimo
   `objetivo − TRANSFER_DIFFICULTY_BAND`. ¿Es justificable y consistente con la
   escala de `difficulty_from_vector` (1..6)? ¿Deja fuera contextos adecuados o
   sirve alguno más plano de lo razonable? Aporta ejemplos por nivel.
4. **Degradación con gracia.** ¿Se garantiza que `context_for` nunca deja al
   alumno sin tarea (`available=True`) y que un `skill`/`level` desconocido no
   altera la elección de V3.49?
5. **Determinismo.** ¿La elección es función determinista de
   (palabra, evidencia, `level`, `skill`) sin reloj ni `hash()` aleatorizado?
6. **Skill limitante.** `_transfer_target_skill` usa
   `planner.limiting_skill(planned_signals(...))` (argmax de **prioridad
   ponderada**, no de debilidad pura) y devuelve `""` si `skill_attempts` está
   vacío. ¿Es la modalidad correcta para orientar un contexto de producción?
7. **Autoría del banco.** ¿El reparto de `skills` por contexto es pedagógicamente
   defendible y suficiente para discriminar? ¿Los seis contextos originales
   conservan sus valores core congelados?
8. **Paridad GET↔POST.** ¿Los dos caminos derivan el mismo `context_id` para la
   misma evidencia? ¿Hay alguna forma de que diverjan?
9. **Cobertura de tests.** ¿Los criterios de aceptación del briefing están
   cubiertos por test? ¿Falta algún borde (umbral exacto de la banda, `level`
   desconocido, `skill` sin contextos, pool agotado/`exhausted`)?

## Formato del informe

Sigue `docs/audit/TEMPLATE.md`. Para cada hallazgo:

- **ID y severidad** (P0 bloqueante / P1 alto / P2 medio / P3 menor).
- **Evidencia** verificable desde el repositorio (archivo:línea del tag, comando
  exacto y salida, o test concreto).
- **Recomendación** y, si aplica, el test que fallaría hoy.
- **Veredicto final** de 2-3 líneas: ¿la release es publicable como estable tal
  cual?

No aceptes como evidencia el contenido de `release-notes-v3.50.0.md` por sí
mismo: úsalo como afirmación a verificar contra el código y los tests del tag.
