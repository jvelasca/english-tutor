# Adecuación CEFR del contenido (V3.70 · Eje 1)

> Generado por `python -m scripts.audit_dossier cefr-adequacy`.
> Criterio: `docs/audit/CEFR-REFERENCE.md` — referencia INTERNA del
> proyecto, no un documento CEFR normativo. Solo lectura.

## Corpus de listening por nivel

| Nivel | N | dificultad media (min–max) | banda | fuera | wpm media (min–max) | banda wpm | fuera |
|---|---|---|---|---|---|---|---|
| A1 | 200 | 1.21 (1–2) | 1–2 | 0 | 117.22 (115.0–125.0) | 80–115 | 86 |
| A2 | 200 | 2.23 (2–3) | 2–3 | 0 | 130.85 (130.0–135.0) | 110–135 | 0 |
| B1 | 25 | 2.92 (2–3) | 2–4 | 0 | 143.4 (130.0–175.0) | 130–160 | 2 |
| B2 | 25 | 4.04 (3–5) | 3–5 | 0 | 162.4 (150.0–185.0) | 150–185 | 0 |
| C1 | 20 | 4.0 (4–4) | 4–5 | 0 | 156.15 (150.0–170.0) | 165–195 | 18 |
| C2 | 20 | 4.35 (4–5) | 4–6 | 0 | 164.35 (159.0–175.0) | 175–200 | 19 |

## Propiedades declaradas frente a realizadas

| Nivel | CS declarado | CS realizado | inference | con integración |
|---|---|---|---|---|
| A1 | 0 | 0 | 0 | 0 |
| A2 | 0 | 0 | 5 | 1 |
| B1 | 4 | 4 | 2 | 1 |
| B2 | 11 | 3 | 5 | 4 |
| C1 | 14 | 0 | 3 | 3 |
| C2 | 20 | 0 | 3 | 3 |

- **Monotonía de wpm máximo entre niveles:** False
- **Monotonía de dificultad media entre niveles:** False

## Ítems de opción múltiple

| Fuente | N | correcta = opción más larga | reparto de posiciones |
|---|---|---|---|
| corpus | 490 | 195 (39.8%) | 0:125, 1:121, 2:122, 3:122 |
| curriculum_checks | 368 | 144 (39.1%) | 0:123, 1:122, 2:121, 3:2 |
| exams | 22 | 8 (36.4%) | 0:14, 1:8 |
| placement | 24 | 12 (50.0%) | 0:6, 1:17, 2:1 |

## Currículo por nivel

| Nivel | Módulos | Unidades | Objetivos | Checks | Actividades | Production | Sin act. | Sin checks | Con listening | Con escenario |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 10 | 10 | 28 | 105 | 86 | 6 | 0 | 0 | 11 | 22 |
| A2 | 7 | 7 | 17 | 55 | 83 | 6 | 0 | 0 | 7 | 12 |
| B1 | 4 | 4 | 18 | 53 | 84 | 6 | 0 | 0 | 7 | 11 |
| B2 | 3 | 3 | 13 | 35 | 63 | 6 | 0 | 0 | 5 | 4 |
| C1 | 4 | 4 | 20 | 63 | 98 | 6 | 0 | 0 | 4 | 10 |
| C2 | 3 | 3 | 20 | 57 | 98 | 4 | 0 | 0 | 4 | 9 |

Fuente: `services.listening.QUESTION_BANK` (ítems `cNNN`),
`services.curriculum.load_all_levels()` y `load_assessments()`.