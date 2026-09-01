# Cobertura curricular (V2.4)

Este documento es el **mapa de cobertura** generado por la auditoría
`services/curriculum_coverage.py`. Responde con datos a la pregunta:

> ¿El alumno puede recorrer completo A1 → A2 → B1 → B2 → C1 → C2?

La fuente de verdad es el script `python -m scripts.curriculum_coverage`, que
emite `curriculum_coverage_report.json`. Este documento lo resume; si el contenido
cambia, vuelve a ejecutar el script y actualiza las cifras.

## Dos métricas distintas

| Métrica | Qué mide | Valor actual |
|---|---|---|
| `TOTAL VALIDATED LEARNING ITEMS` | Cuántos ejercicios fiables existen | **189** (163 listening + 26 speaking) |
| `TOTAL CURRICULUM COVERAGE` | Cuánto del curso completo está cubierto | **42/49 celdas (85,7%)** |

La primera mide *volumen de contenido validado*; la segunda, *cobertura
pedagógica* de la matriz 7 niveles × 7 secciones. Pueden divergir: tener 140 ítems
de listening no significa que cada unidad del curso integre listening.

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
.venv\Scripts\python.exe -m scripts.curriculum_coverage          # reporte + resumen
.venv\Scripts\python.exe -m scripts.curriculum_coverage --strict # exit 1 si hay huecos
```

Los tests de invariantes están en `backend/tests/test_curriculum_coverage.py`.
