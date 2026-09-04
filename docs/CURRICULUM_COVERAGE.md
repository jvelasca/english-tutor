# Cobertura y calidad curricular (V2.4 → V2.8)

Este documento es el **mapa de cobertura y calidad** generado por la auditoría
`services/curriculum_coverage.py`. Responde con datos a la pregunta:

> ¿El alumno puede recorrer completo A1 → A2 → B1 → B2 → C1 → C2, con un curso
> denso, secuencial y evaluable —no una colección organizada de contenidos?

La fuente de verdad es el script `python -m scripts.curriculum_coverage`, que
emite `curriculum_coverage_report.json` (cobertura) y, con `--quality`, el
Curriculum Quality Dashboard. Este documento lo resume; si el contenido cambia,
vuelve a ejecutar el script y actualiza las cifras.

## Tres métricas complementarias (V2.6 → V2.8)

La auditoría V2.6 descubrió que **"cobertura" y "profundidad" son cosas distintas**.
V2.8 añade que **"listening cableado" ≠ "listening curricular"**: referenciar ítems
del banco no basta; cada nivel debe entrenar subskills concretos (ver
`docs/LISTENING_CURRICULUM.md`).

| Métrica | Qué mide | Valor actual |
|---|---|---|
| `TOTAL VALIDATED LEARNING ITEMS` | Cuántos ejercicios fiables existen | **539** (513 listening + 26 speaking) |
| `TOTAL CURRICULUM COVERAGE` | Celdas nivel×sección pobladas | **42/49 (85,7%)** |
| `UNIT COVERAGE` | Secciones pobladas **por unidad** | media A1..C2 **100%** |
| `CEFR DEPTH SCORE` | Densidad + tamaño + completitud por nivel | media **84,2** / 100 |
| `LISTENING CURRICULUM` | Objetivos de escucha alineados al foco del nivel | **38/38 (100%)** |

## Speaking por rutas (V3.8)

La **práctica oral por rutas CEFR** (APRENDER → Speaking) no se mide con las
celdas de la matriz de esta auditoría (la columna *Speaking* de abajo cuenta el
bucle *speak* de las unidades del curso). Desde V3.8 usa su **propio banco
curado de micro-conversaciones guiadas**
(`backend/curriculum/speaking_corpus.json`, v2.0.0): cada tarjeta es un
intercambio `{setup, you, app_line, model_response}` y el progreso se mide con
la puerta de ruta de `backend/services/speaking_routes.py` (cobertura del banco
oficial, precisión, temas y checkpoint). Banco por nivel: A1 36 · A2 32 · B1 28 ·
B2 22 · C1 16 · C2 14 (148 tarjetas). La ruta es un hito de práctica (`functional`
como techo); demostrar el nivel viene del Speaking Assessment + escenarios/
misiones + retención, nunca de la ruta. Validación de la forma del banco en
`backend/tests/test_speaking_routes.py`.

## Mapa de cobertura (nivel × sección)

Leyenda: **OK** = todas las unidades del nivel tienen contenido en la sección ·
**~** = parcial · **—** = vacío.

| Nivel | Vocabulary | Grammar | Listening | Speaking | Interaction | Review | Assessment |
|-------|-----------|---------|-----------|----------|-------------|--------|------------|
| Pre-A1 | — | — | — | — | — | — | — |
| A1 | OK (74) | OK (58) | OK (75) | OK (44) | OK (18) | OK (15) | OK (20) |
| A2 | OK (34) | OK (30) | OK (49) | OK (24) | OK (12) | OK (17) | OK (22) |
| B1 | OK (44) | OK (23) | OK (44) | OK (22) | OK (5) | OK (18) | OK (25) |
| B2 | OK (29) | OK (14) | OK (32) | OK (8) | OK (3) | OK (13) | OK (17) |
| C1 | OK (34) | OK (18) | OK (28) | OK (16) | OK (8) | OK (14) | OK (19) |
| C2 | OK (38) | OK (7) | OK (26) | OK (16) | OK (8) | OK (14) | OK (18) |

**Cobertura por sección** (niveles con curso, de 6): **6/6 en todas las secciones**.

## Unit Coverage y CEFR Depth Score

| Nivel | Unidades | Objetivos | Depth Score | Unit Coverage (media) |
|---|---|---|---|---|
| A1 | 10 | 28 | 89,5 | 100,0% |
| A2 | 7 | 17 | 82,6 | 100,0% |
| B1 | 4 | 18 | 90,4 | 100,0% |
| B2 | 3 | 13 | 82,7 | 100,0% |
| C1 | 4 | 14 | 82,6 | 100,0% |
| C2 | 3 | 14 | 82,2 | 100,0% |

## Curriculum Quality Dashboard

| Dimensión | Score |
|---|---|
| **Overall** | **95,7** |
| Coverage (matriz nivel×sección) | 85,7 |
| Depth (CEFR Depth Score, media) | 84,2 |
| Listening (por unidad) | **100,0** |
| Speaking (por unidad) | 100,0 |
| Interaction (por unidad) | 100,0 |
| Assessment (por unidad) | 100,0 |
| Review (por unidad) | 100,0 |

## Unit Learning Loop

Media **100%** — las 9 fases presentes en las 31 unidades:

| Fase | Unidades cubiertas |
|---|---|
| introduce | 100% (31/31) |
| practice | 100% (31/31) |
| listen | **100% (31/31)** |
| speak | 100% (31/31) |
| interact | 100% (31/31) |
| retrieve | 100% (31/31) |
| transfer | 100% (31/31) |
| assess | 100% (31/31) |
| review | 100% (31/31) |

## Listening Curriculum (V2.8)

Progresión por nivel y alineación de subskills (**100%** en 38 objetivos):

| Nivel | Foco | Objetivos alineados |
|---|---|---|
| A1 | word/sound recognition | 11/11 |
| A2 | gist, detail, information | 7/7 |
| B1 | connected speech, natural pace | 7/7 |
| B2 | inference, attitude | 5/5 |
| C1 | nuance, speaker intention | 4/4 |
| C2 | pragmatics, attitude | 4/4 |

Detalle en `docs/LISTENING_CURRICULUM.md`.

## Delta V2.7 → V2.8

| Dimensión | Before | After | Delta |
|---|---|---|---|
| Overall | 94,5 | 95,7 | +1,2 |
| Listening (por unidad) | 91,7 | **100,0** | +8,3 |
| Loop `listen` | 83,9% | **100%** | +16,1 |
| Listening curriculum alignment | — | **100%** | nuevo |

**A1**: +5 objetivos de listening (Family, Food, Shopping, Past, Plans) + loop
Final cerrado. **Todos los niveles**: subskills de escucha alineados al foco CEFR.

## Huecos priorizados

1. **Pre-A1 sin curso** — banda Can-Do sin contenido propio.
2. **Matriz A1 listening legacy** — la celda nivel×sección sigue siendo OK; el
   curso A1 ya integra listening en todas sus unidades (V2.8).

## Regenerar

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.curriculum_coverage           # reporte + resumen
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict  # exit 1 si hay huecos
.venv\Scripts\python.exe -m scripts.curriculum_coverage --quality # + dashboard JSON
```

Tests: `backend/tests/test_curriculum_coverage.py` y
`backend/tests/test_curriculum_quality.py`.
