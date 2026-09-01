# Cobertura y calidad curricular (V2.4 → V2.6)

Este documento es el **mapa de cobertura y calidad** generado por la auditoría
`services/curriculum_coverage.py`. Responde con datos a la pregunta:

> ¿El alumno puede recorrer completo A1 → A2 → B1 → B2 → C1 → C2, con un curso
> denso, secuencial y evaluable —no una colección organizada de contenidos?

La fuente de verdad es el script `python -m scripts.curriculum_coverage`, que
emite `curriculum_coverage_report.json` (cobertura) y, con `--quality`, el
Curriculum Quality Dashboard. Este documento lo resume; si el contenido cambia,
vuelve a ejecutar el script y actualiza las cifras.

## Tres métricas complementarias (V2.6)

La auditoría V2.6 descubrió que **"cobertura" y "profundidad" son cosas distintas**.
`42/49 celdas` NO significa "curso terminado al 85,7%": una celda cuenta como
poblada si *alguna* unidad tiene contenido en esa sección. Por eso conviven tres
métricas, cada una con un grano distinto:

| Métrica | Qué mide | Valor actual |
|---|---|---|
| `TOTAL VALIDATED LEARNING ITEMS` | Cuántos ejercicios fiables existen | **189** (163 listening + 26 speaking) |
| `TOTAL CURRICULUM COVERAGE` | Celdas nivel×sección pobladas | **42/49 (85,7%)** |
| `UNIT COVERAGE` | Secciones pobladas **por unidad** | media A1..C2 **61,7%** |
| `CEFR DEPTH SCORE` | Densidad + tamaño + completitud por nivel | media **57,7** / 100 |

La primera mide *volumen de contenido validado*; la segunda, *cobertura* de la
matriz; la tercera, *completitud por unidad*; la cuarta, *profundidad* del curso
por nivel. Pueden divergir: tener 140 ítems de listening no significa que cada
unidad integre listening, ni que C2 sea un curso "serio".

## Mapa de cobertura (nivel × sección)

Leyenda: **OK** = todas las unidades del nivel tienen contenido en la sección ·
**~** = parcial (solo algunas unidades) · **—** = vacío. Entre paréntesis, para
listening/speaking, el `count` (objetivos + checks + referencias cableadas al banco)
y el `bank_count` (ítems disponibles en el banco separado). Desde V2.5-C4, `count`
incluye las referencias `listening_items`/`scenario_ids`.

| Nivel | Vocabulary | Grammar | Listening | Speaking | Interaction | Review | Assessment |
|-------|-----------|---------|-----------|----------|-------------|--------|------------|
| Pre-A1 | — | — | — | — | — | — | — |
| A1 | OK (64) | OK (58) | ~ (40 · banco 30) | OK (44 · banco 1) | OK (18) | ~ (1) | ~ (6) |
| A2 | ~ (21) | OK (30) | ~ (14 · banco 31) | OK (22 · banco 6) | OK (11) | ~ (1) | ~ (6) |
| B1 | OK (23) | ~ (18) | ~ (20 · banco 33) | ~ (12 · banco 7) | ~ (1) | ~ (1) | ~ (6) |
| B2 | OK (19) | ~ (11) | ~ (25 · banco 29) | ~ (6 · banco 5) | ~ (2) | ~ (1) | ~ (5) |
| C1 | OK (18) | ~ (13) | ~ (7 · banco 20) | OK (10 · banco 1) | OK (5) | ~ (1) | ~ (6) |
| C2 | OK (14) | ~ (4) | ~ (13 · banco 20) | ~ (6 · banco 6) | ~ (3) | ~ (1) | ~ (5) |

**Cobertura por sección** (niveles poblados de 7):

| Sección | Poblada |
|---|---|
| Vocabulary | 6/7 |
| Grammar | 6/7 |
| Listening | 6/7 |
| Speaking | 6/7 |
| Interaction | **6/7** |
| Review | 6/7 |
| Assessment | 6/7 |

## Unit Coverage y CEFR Depth Score (V2.6)

La tabla de arriba oculta un problema: `~` en Listening significa "alguna unidad lo
tiene", pero no cuántas. La **UNIT COVERAGE** (por unidad) y el **CEFR DEPTH SCORE**
(profundidad por nivel) lo hacen explícito.

| Nivel | Unidades | Objetivos | Depth Score | Unit Coverage (media) |
|---|---|---|---|---|
| A1 | 10 | 23 | **74,2** | 67,1% |
| A2 | 7 | 11 | 52,3 | 63,2% |
| B1 | 4 | 10 | 55,7 | 53,6% |
| B2 | 3 | 9 | 61,7 | 61,9% |
| C1 | 4 | 7 | 48,0 | 64,3% |
| C2 | 3 | 5 | **42,5** | 61,9% |

**Hallazgo clave (V2.6):** el recuento real de objetivos es A1 23 → A2 11 → B1 10 →
B2 9 → C1 7 → C2 5. La caída es **más abrupta de lo que parecía**: no solo C1/C2 son
finos, también A2 (11) y B1/B2 (10/9). El *depth score* lo refleja: C2 es el nivel
más superficial (42,5) y A1 el más denso (74,2).

El *depth score* pondera 4 componentes (suman 1.0, auditables en
`depth_score()`): densidad de objetivos/unidad (0.20), volumen total de objetivos
(0.35), cobertura de secciones por unidad (0.35) y amplitud de subskills (0.10).
El volumen pesa más que la densidad a propósito: la densidad sola premiaba a B2
(3 unidades densas con 9 objetivos) por encima de A2 (7 unidades con 11), cuando un
curso "serio" necesita volumen, no solo unidades llenas.

## Curriculum Quality Dashboard (V2.6)

Una única cifra por dimensión para dejar de desarrollar "a sensación":

| Dimensión | Score |
|---|---|
| **Overall** | **56,8** |
| Coverage (matriz nivel×sección) | 85,7 |
| Depth (CEFR Depth Score, media) | 55,7 |
| Listening (por unidad) | 47,8 |
| Speaking (por unidad) | 84,7 |
| Interaction (por unidad) | 76,4 |
| Assessment (por unidad) | 23,5 |
| Review (por unidad) | 23,5 |

Los puntos débiles son claros: **Review y Assessment (23,5)** viven solo en los
módulos "Final" y **Listening (47,8)** está integrado solo en parte de las unidades.
Son las dimensiones a priorizar en V2.6+ (Unit Learning Loop + Listening
Progression + Review/SRS). `quality_report_delta()` permite ver el antes/después de
cada cambio de contenido.

## Unit Learning Loop (V2.6)

La auditoría fija como **PRIORIDAD Nº1** que cada unidad sea un bucle pedagógico
completo (`introduce → practice → listen → speak → interact → retrieve → transfer →
assess → review`), no una colección de contenidos. `unit_learning_loop()` mide, por
unidad, qué fases están presentes (media **50,6%**):

| Fase | Unidades cubiertas |
|---|---|
| introduce | 100% (31/31) |
| practice | 100% (31/31) |
| listen | 45,2% (14/31) |
| speak | 90,3% (28/31) |
| interact | 83,9% (26/31) |
| retrieve | **0% (0/31)** |
| transfer | **0% (0/31)** |
| assess | 19,4% (6/31, solo Final) |
| review | 19,4% (6/31, solo Final) |

El hueco es explícito: las fases de cierre del bucle (**retrieve**, **transfer**) no
tienen marcador propio por unidad, y **assess/review** viven solo en el módulo Final.

**Marcador de fase (V2.6-C2):** para poder cerrar ese hueco sin inventar lógica, el
modelo añade `Activity.phase` (default vacío = `practice`) con la taxonomía canónica
`LEARNING_PHASES` en `services/curriculum.py`. `unit_learning_loop()` ahora lee
`retrieve`/`transfer`/`review`/`assess` desde ese marcador. La tabla de arriba sigue
igual porque **ningún JSON usa aún el marcador**: etiquetar las actividades de cierre
por unidad es el trabajo de contenido del briefing `agentes/curriculum/c5-loop-phases.md`
(no de este instrumento). Cuando se etiquete, `retrieve`/`transfer` dejarán de ser 0 y
`assess`/`review` aparecerán en las unidades normales.

## Huecos priorizados

Ordenados por impacto pedagógico (no por gravedad técnica):

1. **Pre-A1 sin curso** — existe solo como banda de competencia (descriptores
   Can-Do), no como curso. La escalera visual muestra un peldaño sin contenido
   detrás. (Marcado, no completado en V2.4.)

2. **Interaction ahora declarado en todo el curso (6/7)** — desde V2.5-C3, A1, A2,
   B2, C1 y C2 declaran `interaction`/`turn_taking` (subskills en objetivos con
   `speaking`). Solo Pre-A1 queda vacío, por ser banda sin curso. Desde V2.5-C4 esos
   objetivos están cableados a escenarios concretos de speaking (`scenario_ids`).
   Queda pendiente ampliar la oferta de escenarios en A1 y C1 (solo 1 cada uno).

3. **Listening cableado pero fino en el curso** — desde V2.5-C4, los objetivos de
   listening referencian ítems del banco por ID (`listening_items`; 18 objetivos
   cableados, 4 ítems cada uno). El corpus de 140 ítems ya no está desconectado. La
   sección sigue `~` (parcial) porque solo algunas unidades tienen objetivos de
   listening, no por falta de cableado.

4. **Speaking cableado pero sin evaluación en el curso** — desde V2.5-C4, los 50
   objetivos que declaran `speaking` referencian un escenario (`scenario_ids`; 26
   escenarios con `cefr_target`). Sigue habiendo 0 checks (es performance-skill), por
   lo que la evaluación real de speaking vive en el instrumento de Speaking
   Assessment, no en el curso secuencial.

5. **Review y Assessment solo en módulos "Final"** — cada nivel tiene 1 módulo Final
   con repaso/evaluación; las unidades normales no los integran (por eso son `~`).
   No existe el "Unit Learning Loop" (introduce → practice → listen → speak →
   retrieve → transfer → assess) dentro de cada unidad.

6. **C1 y C2 muy finos** — 7 y 5 objetivos respectivamente, frente a 23 (A1) y 11
   (A2). El volumen decae a medida que sube el nivel.

## Regenerar

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.curriculum_coverage           # reporte + resumen
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict  # exit 1 si hay huecos
.venv\Scripts\python.exe -m scripts.curriculum_coverage --quality # + dashboard JSON
```

Los tests de invariantes están en `backend/tests/test_curriculum_coverage.py`
(cobertura) y `backend/tests/test_curriculum_quality.py` (unit coverage + depth +
dashboard, V2.6).
