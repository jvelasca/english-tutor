# Briefing de subagente — V3.70 · Eje 1: adecuación CEFR real del contenido

> **Estado:** **PENDIENTE** (V3.70, 2026-09-15). Primer eje de la auditoría
> pedagógica. **Solo medición**: no se corrige contenido.
> **Qué es:** el dossier `docs/audit/AA-PED-CONTENIDO-CEFR.md` más el test
> `backend/tests/test_ped_content_cefr_v370.py` que fija lo medido.
> **Qué NO cierra:** la remediación del contenido (renivelar ítems, arreglar
> distractores, subir wpm de C1/C2). Todo hallazgo se **registra con severidad**,
> nunca se arregla aquí.
> **Regla dura:** *V3.70 no toca contenido, banco ni currículum.* Si un ítem está
> mal etiquetado, el dossier lo declara y el test lo **pinnea como hallazgo
> conocido**, no se cambia el JSON.
> **Briefing maestro:** `agentes/v370-auditoria-pedagogica.md` (regla dura,
> decisiones cerradas, criterios de salida de la release).

## Rol

**Auditor de contenido.** Produce el dossier `AA` con el formato de
`docs/audit/TEMPLATE.md` y el fichero de test `test_ped_content_cefr_v370.py`.
No modifica `backend/curriculum/**`, ni `backend/services/**`, ni
`backend/data/**`.

## Objetivo

Responder con números, no con impresiones, a: **¿el contenido A1..C2 es de su
nivel?** Comparando lo **declarado** en cada ítem con el criterio interno
`docs/audit/CEFR-REFERENCE.md`.

## Estado de partida ya medido (no lo re-derives: verifícalo y cítalo)

Los números siguientes ya están generados en
`docs/audit/generated/cefr-adequacy.json` (y su `.md`) por
`python -m scripts.audit_dossier cefr-adequacy`. **Son la evidencia del
dossier.** Debes reproducirlos para confirmarlos, no volver a inventarlos.

### Corpus de listening (490 ítems `cNNN`) frente a la banda de velocidad

| Nivel | N | wpm media (min–max) | banda de referencia | **fuera de banda** |
|---|---|---|---|---|
| A1 | 200 | 117,22 (115–125) | 80–115 | **86** |
| A2 | 200 | 130,85 (130–135) | 110–135 | 0 |
| B1 | 25 | 143,40 (130–175) | 130–160 | 2 |
| B2 | 25 | 162,40 (150–185) | 150–185 | 0 |
| C1 | 20 | 156,15 (150–170) | 165–195 | **18** |
| C2 | 20 | 164,35 (159–175) | 175–200 | **19** |

- **Dificultad escalar:** los 490 ítems caen **dentro** de la banda de su nivel
  (`0` fuera en los seis niveles). El problema **no** es la dificultad global,
  es la **velocidad**.
- **Monotonía de wpm máximo entre niveles: `False`** (el máximo de B2, 185, es
  mayor que el de C1, 170). La escalera de velocidad **no es monótona**.
- **Monotonía de dificultad media entre niveles: `False`** (C1 4,0 < B2 4,04).

### Propiedades declaradas frente a realizadas

| Nivel | `connected_speech` declarado | realizado (reducción real en la transcripción) |
|---|---|---|
| A1 | 0 | 0 |
| A2 | 0 | 0 |
| B1 | 4 | 4 |
| B2 | 11 | **3** |
| C1 | 14 | **0** |
| C2 | 20 | **0** |

- **Inferencia:** ítems etiquetados `inference` que **sí** exigen integrar claves
  (no se resuelven con una palabra literal del audio): A2 **1 de 5**,
  B1 1 de 2, B2 4 de 5, C1 3 de 3, C2 3 de 3.

### Ítems de opción múltiple (sesgo de forma)

| Fuente | N | correcta = opción más larga | reparto de posiciones |
|---|---|---|---|
| corpus de listening | 490 | 195 (39,8 %) | equilibrado (~25 % cada una) |
| **checks del currículum** | 368 | 144 (39,1 %) | **0:329 (89,4 %) · 1:37 · 2:2** |
| exámenes (a1/b1) | 22 | 8 (36,4 %) | 0:14 (63,6 %) · 1:8 |
| placement | 24 | 12 (**50,0 %**) | 0:6 · 1:17 · 2:1 |

**El reparto de posiciones de los checks del currículum es el hallazgo más
severo del eje:** un alumno que responda siempre la primera opción acierta el
**89,4 %**. El corpus de listening, en cambio, está equilibrado (~25 %).

### Currículo (medido, y ya corregido en las métricas generadas)

| Nivel | Módulos | Unidades | Objetivos | Checks | Actividades | Production | Sin actividades | Sin checks |
|---|---|---|---|---|---|---|---|---|
| A1 | 10 | 10 | 28 | 105 | 86 | 6 | 0 | 0 |
| A2 | 7 | 7 | 17 | 55 | 83 | 6 | 0 | 0 |
| B1 | 4 | 4 | 18 | 53 | 84 | 6 | 0 | 0 |
| B2 | 3 | 3 | 13 | 35 | 63 | 6 | 0 | 0 |
| C1 | 4 | 4 | 20 | 63 | 98 | 6 | 0 | 0 |
| C2 | 3 | 3 | 20 | 57 | 98 | 4 | 0 | 0 |
| **Total** | **31** | **31** | **116** | **368** | **512** | **34** | **0** | **0** |

- **Ningún objetivo carece de actividades ni de checks**, y **ningún check
  declara una destreza fuera de las `skills` de su objetivo**
  (`checks_out_of_objective_skills = 0`): la integridad estructural del
  currículum está **limpia**.

### Deriva corregida de las métricas generadas (hallazgo documental)

Antes de esta release, `docs/audit/generated/` estaba **desincronizado con el
disco**:

- `curriculum-stats` declaraba C1 = 14 y C2 = 14 objetivos; el disco tiene
  **20 y 20** (y 116 totales).
- `listening-corpus-stats` arrastraba conteos de destrezas (`detail` 54 vs 55),
  medias de palabras por script (13,6 vs 13,56; 14,84 vs 15,04) y el top-3 de B1.
- `mc-position-bias` arrastraba los recuentos de posiciones.

Tras regenerarlas, las tres coinciden con el disco. **Debe quedar escrito en el
dossier**: la evidencia de auditorías previas se apoyaba en cifras derivadas.

## Diseño del dossier `docs/audit/AA-PED-CONTENIDO-CEFR.md`

Estructura obligatoria (`docs/audit/TEMPLATE.md`):

1. **Alcance** — qué se audita (los 6 cursos, los 368 checks MC, los 512
   actividades, los 34 `production_checks`, el corpus de 490 ítems de listening y
   los instrumentos MC de placement/exámenes). Qué **NO** se audita (calidad
   acústica real del audio, discriminación empírica con alumnos, el corpus de
   speaking — es del eje 2, la matriz CEFR — es del eje 4).
2. **Método** — el criterio es `docs/audit/CEFR-REFERENCE.md` (**referencia
   interna del proyecto, NO un documento CEFR normativo**: hay que repetirlo);
   instrumento `python -m scripts.audit_dossier cefr-adequacy`; muestreo
   cualitativo determinista con
   `python -m scripts.audit_dossier sample --bank listening --level C1 --count 5 --seed 7`
   (y `--bank objectives --level B1`).
3. **Evidencia** — tablas por nivel (las de arriba) + una tabla de **muestra
   cualitativa revisada** con al menos: 3 ítems A1 fuera de banda, 3 ítems
   C1/C2 con `connected_speech: true` sin reducción, 2 ítems `inference` A2
   resolubles por palabra, y 3 checks del currículum con la correcta en la
   posición 0. **Cada fila con el `id` real del ítem** y la cita textual.
4. **Hallazgos** — tabla `| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`
   con severidad P0/P1/P2/P3. Los candidatos ya medidos, a valorar por ti:
   - Sesgo posicional de los checks del currículum (89,4 % en la posición 0).
   - A1 sistemáticamente rápido (86/200 por encima del techo de su banda).
   - C1/C2 sistemáticamente lentos (18/20 y 19/20 por debajo del suelo).
   - Escalera de velocidad **no monótona** (B2 max 185 > C1 max 170).
   - `connected_speech` declarado sin respaldo textual: **C1 14/14 y C2 20/20**
     (y B2 8/11).
   - Ítems `inference` mal etiquetados en A2 (4 de 5 se resuelven por palabra).
   - Deriva de las métricas generadas (documental).
5. **Veredicto** — 2–3 líneas. Debe distinguir **«el test no demuestra»** de
   **«el motor no cumple»** (regla de la auditoría `Y` §28): aquí se ha medido
   **adecuación declarada frente a criterio interno**, **no** eficacia con
   alumnos.
6. **Regenerar / Verificar** — bloque `powershell` con los comandos exactos.
7. **Tests que respaldan** — el fichero nuevo y qué pinnea.

## Tests: `backend/tests/test_ped_content_cefr_v370.py`

Reglas: se afirma sobre **contenido real resuelto del disco** y sobre contratos
públicos; **nunca** sobre implementación privada; **nunca** se escribe un test
que pase «porque el contenido es pobre»: si el hueco existe, el test lo
**declara como hueco medido con su número**.

Tests requeridos (nombres orientativos, uno por hallazgo):

- `test_mc_position_bias_of_curriculum_checks_is_declared` — mide el reparto de
  `correct_index` sobre los 368 checks y **afirma el hecho medido** (que la
  posición 0 concentra ≥ 80 % y que el corpus de listening está equilibrado con
  ≤ 35 % por posición). Si alguien reequilibra el currículum, el test **falla**
  y obliga a revisar el hallazgo.
- `test_a1_corpus_is_faster_than_its_reference_band` y
  `test_c1_c2_corpus_is_slower_than_its_reference_band` — con las bandas de
  `docs/audit/CEFR-REFERENCE.md` (`REFERENCE_BANDS` de
  `scripts/audit_dossier.py` es la copia del script; **no** lo importes desde
  `services`). Afirma el conteo medido.
- `test_speed_ladder_is_not_monotonic_is_declared` — el máximo de B2 > el de C1.
- `test_connected_speech_declared_without_textual_support` — para cada ítem con
  `connected_speech: true`, comprueba que la transcripción contiene una
  reducción real (mismo conjunto de marcadores que el instrumento) y afirma
  **0 de 14 en C1 y 0 de 20 en C2**.
- `test_inference_items_of_a2_are_resolvable_by_literal_word` — afirma que la
  mayoría de los `inference` de A2 se resuelven con palabras literales del audio.
- `test_curriculum_structural_integrity_is_clean` — 116 objetivos, 368 checks,
  512 actividades, 0 objetivos sin checks/actividades y 0 checks fuera de las
  `skills` de su objetivo.
- `test_generated_metrics_match_disk` — `services.content_validation.content_stats()`
  y los conteos del currículum coinciden con lo que el dossier declara
  (anti-drift, igual que `test_content_stats_matches_validator_and_bank`).

Convención de imports de los tests del repo: `from services import ...`
(el `conftest.py` ya pone `backend/` en el path); `TestClient` solo si hace
falta HTTP (aquí **no** hace falta: es medición de contenido).

## Criterios de salida

1. `docs/audit/AA-PED-CONTENIDO-CEFR.md` creado, con la plantilla completa y
   **toda evidencia con `archivo:línea` o `id` de ítem real**.
2. `backend/tests/test_ped_content_cefr_v370.py` creado y **verde**.
3. `python -m ruff check .` limpio en `backend/`.
4. `python -m pytest -q` verde, con el total **anterior + los nuevos**.
5. `python -m scripts.audit_dossier cefr-adequacy` reproducible y sin escribir
   en `curriculum/` ni en `data/`.
6. Ningún fichero de `backend/curriculum/**`, `backend/services/**` ni
   `backend/data/**` modificado.

## Fuera de alcance

- Renivelar, reescribir o reetiquetar cualquier ítem.
- Cambiar `GENERATOR_VERSION`, la velocidad de TTS o el corpus.
- Auditar el corpus de speaking (eje 2), la matriz CEFR (eje 4) o los
  instrumentos (eje 5).
- Validación empírica con alumnos (`docs/audit/PARKED.md`).
