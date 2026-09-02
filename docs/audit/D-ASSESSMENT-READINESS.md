# D — Mastery / Assessment / Readiness thresholds (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** escalera Assessment 2.0 (`services/assessment_v2.py`), Evidence Graph (`services/evidence_graph.py`), readiness (`services/adaptive.py` + `services/cefr_matrix.py` + `curriculum/cefr_matrix.json`) y `min_per_skill` de exámenes (`services/curriculum.Exam`). Sin cambios de umbrales: documentación + golden.
- **Relación con freeze:** calibración (`BETA_V3.md` §4.2).
- **Golden:** `tests/golden/assessment/thresholds.json`, `tests/golden/evidence_graph/profiles.json`, `backend/tests/test_golden_assessment.py`, `backend/tests/test_golden_evidence_graph.py`.

## Método

1. Justificación por escrito de cada constante, verificada contra el código.
2. Casos de frontera sintéticos (golden) que congelan la semántica.
3. Perfil sintético dorado (incluido el caso 88/91/85/63/58) para el Evidence Graph.
4. Protocolo de calibración con alumnos reales → se documenta, no se ejecuta (sin datos reales la justificación es provisional).

## Justificación de las constantes

### Escalera Assessment 2.0 (`PASS_THRESHOLDS`)

| Peldaño | Umbral | Por qué |
|---|---|---|
| formative | 0.70 | Micro-evaluación de una lección: basta con dominar la mayoría (≈70 %) para continuar; el objetivo no es certificar sino señalar. Por eso es el más bajo junto con retention. |
| unit | 0.75 | Cubre una unidad completa (checks de varios objetivos): exige dominar las tres cuartas partes. Marca que la unidad "se sostiene" antes de apilar la siguiente. |
| progress | 0.80 | Sintetiza 3 unidades: quiere decir "dominio consolidado", no "aprobado justo"; sube el listón frente a unit. |
| level | 0.80 | Examen CEFR: el overall 0.80 **no basta solo**; además cada destreza exige ≥ 0.75 (`Exam.min_per_skill`). Es el único peldaño con doble gate. |
| retention | 0.70 | Re-test retardado de la misma batería: el umbral bajo mide caída *relativa* (ratio ≥ 0.9 = estable), no re-certificación. 0.70 ≈ mismo nivel de exigencia que formative pero su decisión real es `retention_delta.stable`. |

### `min_per_skill = 0.75` en exámenes (`services.curriculum.Exam`)

Un alumno no certifica un nivel CEFR compensando listening malo con grammar bueno. El overall (0.80) valida el nivel medio; `min_per_skill` (0.75) valida que ninguna macro-destreza está rota. Golden: `level-blocks-weak-skill` (overall 0.90, grammar 0.74 → fail) y `level-passes-when-all-above-min`.

### Matriz CEFR por nivel (`cefr_matrix.json`, macro-destrezas)

| | mastery | confianza | evidencias | transfer | novel |
|---|---|---|---|---|---|
| A1 | 0.55–0.60 | 0.50 | 2 | 0 | 0 |
| A2 | 0.60–0.65 | 0.55 | 3 | 0 | 0 |
| B1 | 0.65–0.70 | 0.60 | 3 | **1** | 0 |
| B2 | 0.70–0.75 | 0.65 | 4 | **2** | **1** |

Escucha siempre 0.05 por encima de speaking (B2: 0.75 vs 0.70): la comprensión es el input que sostiene la interacción; exige más evidencia acumulada. El salto **B1 transfer 1 → B2 transfer 2 + novel 1** operacionaliza que "independiente" (B1) exige un uso transferido; "fluido/dominio" (B2) exige uso transferido *repetido* en contexto nuevo (novel). Mientras el CEFR no da un umbral numérico, esta es la lectura más conservadora del descriptor B2 ("deal with complex... in own field/abstract").

**C1/C2 caen al fallback plano** (`READINESS_MINIMUMS`: grammar/vocab/listening/reading 0.70, speaking/writing/pronunciation 0.60, confianza ≥ 0.60, evidencia ≥ 3) porque la matriz no llega más allá de B2. Consecuencia honesta: **no hay un gate C1/C2 distinto del de B2 ampliado**; es una deuda de calibración, no un error de código.

### Evidence Graph: el limiting factor no es la destreza más alta

Verificado con perfiles sintéticos (`test_golden_evidence_graph.py`):

- **88/91/85/63/58** → limiting factor **interaction (58)**, focus phase `interact`, y `because[]` menciona "Your B1 interaction mastery is 58%." además del contraste "Your vocabulary is already 91%." Nunca vocabulary (91) ni listening (88).
- Sin evidencia transfer, el grafo prioriza **transfer missing** sobre cualquier destreza débil (cobertura de evidencia primero): un objetivo con práctica pero sin transfer no se declara dominado.
- Caso de control: si vocabulary es genuinamente la más débil (55), el grafo la señala (no hay sesgo hacia interaction).
- `MASTERY_EVIDENCE_REQUIREMENTS` (initial 1, practice 2, transfer 1, novel 1, delayed 1) fija que **terminar no es dominar**: hacen falta ≥2 prácticas familiares + transfer + novel + delayed.

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| D1 | media | No existe gate distinto para C1/C2 (fallback plano a B2-ish). | `cefr_matrix.json` (solo A1–B2) | Aparcar hasta la fase de observación con alumnos C1/C2; documentar en PARKED. | aceptado (documentado) |
| D2 | info | La decisión real de retention es el ratio de caída (≥ 0.9), no el 0.70 absoluto; el 0.70 solo evita "aprobar" a quien ya suspendía. | `retention_delta` | Mantener; añadir explicación en UI de retention cuando exista. | aceptado |
| D3 | info | Los umbrales por peldaño (0.70→0.80) y los mínimos de la matriz (A1→B2) son dos capas distintas con fuentes distintas; no mezclarlas al leer un dashboard. | código + matrix | — | aceptado |

## Protocolo de calibración con alumnos reales (fase de observación)

Sin datos reales la justificación es provisional. Cuando exista una cohorte:

1. Recoger overall por peldaño y `result` por ítem (ya se registra en evidencia).
2. Comparar tasa de paso con retención a +7 días (`RETENTION_MIN_DAYS`) y ratio ≥ 0.9: si la retención cae por debajo de 0.9 con overall 0.80, el nivel 0.80 es insuficiente y hay que subirlo.
3. Medir si el sesgo posicional (auditoría A/B) infla el overall en listening/vocabulary: corregir el sesgo **antes** de calibrar con alumnos.
4. Revisar el fallback C1/C2 con alumnos que certifican B2: ¿`READINESS_MINIMUMS` 0.70 es alcanzable/permissivo?

## Regenerar / Verificar

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_golden_assessment.py tests/test_golden_evidence_graph.py -q
```
