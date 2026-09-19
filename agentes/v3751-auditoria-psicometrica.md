# Briefing maestro — V3.75.1 · Auditoría psicométrica del banco (pausa pedagógica pre-baseline)

> **Estado:** **EN CURSO** (2026-09-19). Auditoría de **SOLO MEDICIÓN** sobre el
> baseline congelado **V3.75.1**.
> **Qué es:** los cinco dossieres de eje `AH`–`AL` más la síntesis `AM`, en
> `docs/audit/`, y el instrumento de solo lectura que los sustenta.
> **Qué NO cierra:** ninguna deuda de contenido. No se corrige el sesgo de
> longitud, ni el de `assessments.json`, ni la forma del banco, ni se decide la
> distribución 2/3/4 opciones. **Se mide y se declara**, y la fase de cierre de
> cada hallazgo se **propone**, no se implementa.
> **Qué NO es:** una release. No hay bump de app, ni `CURRICULUM_VERSION`, ni
> `ASSESSMENT_VERSION`, ni migración.
> **Regla dura:** *no se toca `backend/curriculum/**.json` ni
> `backend/services/**`*. El único código que cambia es el instrumento de
> medición (`backend/scripts/audit_dossier.py`) y sus tests.

## Baseline (no lo re-derives: verifícalo y cítalo)

| Concepto | Valor | Procedencia |
|---|---|---|
| Commit | `7962d57de719ee8e4c62b0f3017c517b04714408` | `git rev-parse HEAD` |
| Tag anotado | `v3.75.1` (apunta a ese mismo commit) | `git rev-parse v3.75.1^{commit}` |
| `CURRICULUM_VERSION` | `1.3.1` | `backend/services/curriculum.py` |
| `ASSESSMENT_VERSION` | `1.0.0` | `backend/services/curriculum.py` |
| Checks MC del currículum | **368** | `item-form` |
| Corpus de listening (`c*`) | **490** | `item-form` |
| Exámenes finales (A1 10 · B1 12) | **22** | `item-form` |
| Placement | **24** | `item-form` |

**Lo que ya está cerrado y no se reabre:** el **P0 del sesgo posicional de los
368 checks** (V3.75.1, regla `j % k`). El reparto por grupo de `k` es
`0:33,4 % · 1:33,2 % · 2:32,9 %` con peor posición `33,5 %`, bajo el límite del
35 %. No se re-mide como hallazgo: se cita como estado de partida.

## Por qué esta auditoría

V3.75.1 eliminó el atajo «marca siempre la primera opción». Quedan deudas de
**forma** que el propio informe de P0 declaró abiertas:

- la correcta sigue siendo la opción **más larga** en el 39,1 % de los checks y
  en el 50,0 % del placement (hallazgo `#7` de `AA`);
- `assessments.json` sigue con la correcta en la **posición 0** en el 63,6 % de
  los 22 ítems de examen, y el placement la concentra en la **posición 1** en
  **17/24**;
- solo **10 de 368** checks tienen 4 opciones;
- los distractores pueden seguir siendo inferibles por longitud, gramática,
  palabras clave o forma.

Antes de decidir **otro parche** de contenido, la pregunta es si hay un patrón
sistemático de autoría detrás de todo esto. Eso es lo que miden los cinco ejes.

## Instrumento (solo lectura, ya implementado)

Todos los comandos se ejecutan desde `backend/` con el intérprete del proyecto:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.audit_dossier item-form
.\.venv\Scripts\python.exe -m scripts.audit_dossier distractor-signals
.\.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.\.venv\Scripts\python.exe -m scripts.audit_dossier cefr-adequacy
.\.venv\Scripts\python.exe -m scripts.audit_dossier assessment-instruments
```

Artefactos generados (evidencia citable, versionada):

| Fichero | Qué mide |
|---|---|
| `docs/audit/generated/item-form.{md,json}` | Nº de opciones, posición y longitud de la correcta, por banco, nivel y grupo de `k` |
| `docs/audit/generated/distractor-signals.{md,json}` | Tres señales declaradas de distractor inferible + muestra determinista |
| `docs/audit/generated/mc-position-bias.{md,json}` | Reparto de posiciones; exámenes y placement **separados** |
| `docs/audit/generated/cefr-adequacy.{md,json}` | Adecuación CEFR por nivel (incluye `correct_is_longest` por banco) |
| `docs/audit/generated/assessment-instruments.{md,json}` | Placement, exámenes, remediación, umbrales de banda |

**Corrección de medición ya aplicada (cítala, no la redescubras como hallazgo
nuevo):** hasta V3.75.1 el grupo de `mc-bias` llamado «exámenes level/placement»
**solo contaba los exámenes** (22 ítems); el placement (24 ítems) no aparecía en
esa medición. Ahora son dos grupos. El 63,6 % de `AA` es de **exámenes**, no del
conjunto con placement.

## Los cinco ejes

Cada eje produce **su** dossier (evita que varios escritores toquen un fichero):
`TEMPLATE` → `docs/audit/TEMPLATE.md`. Severidad `P0`–`P3` con la escala de la
casa (P0 = permite aprender/evaluar mal de forma sistemática; P3 = higiene).

| Eje | Dossier | Pregunta | Cifra de partida |
|---|---|---|---|
| **AH** · longitud | `AH-PSICO-LONGITUD.md` | ¿La longitud de la opción correcta permite acertar sin comprender? ¿Se refuerza con la posición? | 39,1 % checks · 50,0 % placement |
| **AI** · assessments | `AI-PSICO-ASSESSMENTS.md` | ¿El sesgo posicional de exámenes y placement sobrevive tras V3.75.1? ¿Es alcanzable alguna posición muerta? | 63,6 % pos. 0 (exámenes) · 17/24 pos. 1 (placement) · posición 2 muerta en ambos exámenes |
| **AJ** · forma | `AJ-PSICO-FORMA.md` | ¿Qué forma tiene el banco (2/3/4 opciones) y qué implica? ¿Es homogénea por nivel y destreza? | 358 `k=3` · 10 `k=4` · 0 `k=2` |
| **AK** · distractores | `AK-PSICO-DISTRACTORES.md` | ¿La correcta es inferible por forma, gramática, palabra clave del enunciado o solapamiento léxico? | `prompt_keyword_echo` 6,0 % checks · `shape_outlier` 16,0 % checks / 21,0 % corpus |
| **AL** · niveles | `AL-PSICO-NIVELES.md` | ¿El patrón es el mismo en A1→C2 o hay niveles donde la forma está rota? | C2 checks 56,1 % más larga · corpus C1/C2 80 % |

**Regla anti-solapamiento:** cada eje parte de su cifra y **cita** el instrumento;
no re-deriva las cifras de otro eje. Si un eje necesita un corte que el
instrumento no da, lo **declara como límite** en lugar de improvisar una
medición ad-hoc no reproducible.

## Regla de evidencia (obligatoria en los cinco ejes)

- `[D]` **declarado**: aparece escrito en el código o en un documento.
- `[A]` **árbol**: se verificó leyendo el fichero en **este** commit.
- `[R]` **reproducible**: se ejecutó y el resultado está en el dossier.

Toda afirmación lleva `archivo:línea` o un comando del §Regenerar. Una
afirmación sin evidencia se descarta.

## Regla de honestidad

Distinguir siempre **«el banco no cumple»** de **«esta medición no lo
demuestra»**. Un ítem con la correcta más larga **no** es por sí solo un ítem
malo: puede ser el ítem más claro del banco. Lo que se mide es la **tasa** y su
**capacidad de predecir la correcta sin comprender**, no la calidad editorial de
un ítem concreto. La parte cualitativa la cierra la muestra determinista, y en
ella se dice qué se ve y qué no.

## Lo que NO se hace en esta auditoría

1. **No se corrige nada** de `backend/curriculum/` ni de `assessments.json`.
2. **No se añaden candados que fijen el defecto.** El instrumento mide; los
   invariantes se diseñan **con** la corrección, en su fase.
3. **No se propone** «todos los ítems a 4 opciones» ni «normalizar todas las
   longitudes» como conclusión automática: si el eje lo sugiere, se argumenta y
   se marca como decisión pedagógica pendiente.
4. **No se toca el motor** ni ningún umbral.

## Entrega

Cada eje entrega: (a) su dossier `docs/audit/<X>-PSICO-*.md` con la estructura de
`TEMPLATE`, y (b) un resumen de 5–10 líneas con los hallazgos y su severidad,
para que la síntesis `AM` los consolide sin releer los cinco dossiers.
