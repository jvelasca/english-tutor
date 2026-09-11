# v3.52.2 — Cierre de los P2 de la auditoría Q (calibración del Difficulty Engine)

> Release **SIN migración de BD** y **SIN cambios de contrato**: recalibra la tabla
> de capacidad del Difficulty Engine al banco real y corrige la documentación de
> la tolerancia. **NO toca** la escalera `transfer_state`, sus umbrales,
> `context_signals`, `context_diversity`, el scoring (`score_transfer_attempt`)
> ni FSRS. Determinista, sin LLM.

## Contexto

La auditoría externa **Q** de V3.52.1
([`docs/audit/Q-AUDITORIA-TOTAL-V352.md`](docs/audit/Q-AUDITORIA-TOTAL-V352.md))
cerró con 🟢 **sin P0/P1** y dos P2 de calibración:

- **P2-01:** la tabla declarada `CEFR_CAPACITY` afirmaba estar «calibrada con la
  distribución real del banco de transferencia», pero la medición de los 20
  contextos la desmentía: la `interaction` de A1/A2 estaba por debajo del máximo
  real (1 frente a 2/3) y el léxico/sintaxis de B2/C1 por encima (4/4 y 5/5 frente
  a 3/4).
- **P2-02:** la distinción `DIFFICULTY_TOLERANCE` (demostrado) vs
  `DIFFICULTY_TOLERANCE_ESTIMATED` no cambiaba **ninguna** selección sobre el banco
  real (0 de 48 combinaciones) y su justificación escrita estaba invertida.

V3.52.2 cierra ambos con dos tests que impiden que vuelvan a divergir en silencio.

## Cambios

### A. P2-01 — `CEFR_CAPACITY` es el envelope monótono del banco

La consecuencia operativa del desajuste estaba medida: con la tolerancia
**estricta** (suelo demostrado), un alumno **A2 certificado** quedaba fuera de
`directions`/`shopping` —2 de los 4 contextos que el banco etiqueta A2— porque
declaran `interaction` 3 sobre una capacidad de 1 (`overshoot` 2 > tolerancia 1).
Es decir, el alumno con **más** confianza recibía el conjunto **más plano**, justo
lo contrario de lo que el motor dice querer.

La tabla pasa a ser el **máximo acumulado por dimensión** de los
`difficulty_vector` reales:

| Nivel | antes (lex/syn/dis/int) | ahora |
| --- | --- | --- |
| A1 | 1 / 1 / 1 / **1** | 1 / 1 / 2 / **2** |
| A2 | 2 / 2 / 2 / **1** | 2 / 2 / 2 / **3** |
| B1 | 3 / 3 / 3 / **2** | 3 / 3 / 3 / **3** |
| B2 | **4** / **4** / 4 / 3 | **3** / **3** / 4 / 3 |
| C1 | **5** / 5 / 5 / 4 | **4** / 5 / 5 / **5** |
| C2 | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 |

La envolvente (y no el máximo del nivel a secas) es lo que mantiene la
monotonía no decreciente aunque un nivel puntual sea más plano que el anterior
(A2 tiene contextos con `interaction` 3 y B1 declara 2). Es una calibración del
**banco**, no una escala CEFR normativa.

**Impacto medido: 15 de 48 combinaciones (nivel de ítem × nivel de alumno; 49
posibles, una sin reto) cambian de contexto servido, y el patrón es el esperado
por el envelope**: el alumno A2 **demostrado** pasa por fin a
`directions`/`shopping` (interaction 3) en vez de `story`/`future`
(interaction 1) —el fallo medido—, el alumno C1 pasa de `academic` (C2) a
`mediation` (C1), y los empates que la tabla inflada «diluía» se estrechan al
contexto que encaja exacto (B1 4→1, B2 3→1, C1 2→1). En el caso `A1`→alumno A2
ocurre lo contrario (1→3 contextos) por un empate nuevo: el reto sube y tres
contextos quedan equidistantes.

Tests:

- `test_capacity_is_the_monotone_envelope_of_the_bank` — recalcula la envolvente
  desde `TRANSFER_CONTEXTS` y falla si la tabla se desvía (habría cazado P2-01).
- `test_every_bank_context_fits_its_own_level_under_strict_tolerance` — invariante
  operativo: ningún contexto del banco puede quedar `within=False` frente al reto
  de su propio nivel con la tolerancia estricta.

### B. P2-02 — la tolerancia queda como red de seguridad (y bien explicada)

Dos afirmaciones falsas corregidas en `services/difficulty.py`:

1. El margen amplio **no** es «conservador… más margen en lugar de más exigencia»:
   un margen mayor admite **más** `overshoot`, es decir deja entrar contextos que
   exceden el reto (más exigencia). La tolerancia estricta es la que **menos**
   exceso deja pasar.
2. La diferenciación por fuente no cambia hoy ninguna selección: con el envelope,
   ningún contexto supera la capacidad de su nivel, así que la tolerancia es una
   red de seguridad para bancos que declaren cargas por encima de la envolvente.

`test_tolerance_bites_only_when_a_context_declares_above_the_envelope` fija ambas
cosas: la inercia sobre el banco real (0 de 48 combinaciones) y que la tolerancia
**sí** discrimina con un contexto sintético que excede el reto (`within` falso con
tolerancia 1, verdadero con 2).

### C. Proceso — etiqueta `v3.52.1`

Creada y empujada la etiqueta anotada `v3.52.1` sobre `89eff0b` (P3-04 de la
auditoría), que faltaba desde el hotfix.

## Verificación

- Backend: `ruff` limpio y `pytest` **2166 passed** en local (+2 netos: 3 tests
  nuevos y 1 reemplazado). En CI serán 2164 + 2 skipped (los mismos 2 de
  `test_stt_asr_integration.py`).
- Frontend: `vitest` **76 ficheros/651 tests**, `tsc --noEmit` y `npm run build`
  en verde (sin cambios de contrato, el espejo `DrillDifficultyFit` no cambia).
- Scripts: `check_release_consistency.py` (**3.52.2**), `check_beta_v3.py`,
  `content_validation.py` y `check_i18n_coverage` exit 0.
- Medición del impacto (§A) y de la inercia de la tolerancia (§B) reproducidas con
  el banco real antes de fijar los tests.

## Qué NO cambia

- La escalera `transfer_state`, sus umbrales, `context_signals`,
  `context_diversity`, `score_transfer_attempt` y FSRS.
- El contrato HTTP (`difficulty_fit`, `learner_level_source`, `dimensions_*`,
  `coverage`): las claves ya existían desde V3.52.1.
- La política de suelo (`demostrado > estimado > declarado > ninguno`) y el techo
  lingüístico del ítem (`_within_level`).
- Sin migración de BD.

## Fuera de alcance (V3.53+)

- **P1-02** (Learner Skill State 2.0 + `observed_difficulty` persistido por
  evento) y **P1-03** (Planner 2.0 / Expected Learning Value).
- P3-01 (fila legacy de V3.51 etiquetada `practice` en vez de `estimated`) y
  P3-02 (`_context_vector` trata un contexto sin vector como si fuera un vector):
  abiertos y aceptados, sin impacto de comportamiento.
