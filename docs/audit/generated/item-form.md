# Forma de los ítems de opción múltiple (V3.75.1 · pausa pedagógica)

> Generado por `python -m scripts.audit_dossier item-form`. Solo lectura.
> Mide la FORMA (número de opciones, posición y longitud de la correcta),
> no la calidad del contenido. `más larga` cuenta solo la más larga única;
> `o empatada` incluye los empates a longitud máxima.

## Posición y número de opciones

| Grupo | N | k (reparto) | Posiciones de la correcta | Muertas |
|---|---|---|---|---|
| checks del currículum (todos) | 368 | k=3:358, k=4:10 | 0:123, 1:122, 2:121, 3:2 | — |
| checks A1 | 105 | k=3:95, k=4:10 | 0:35, 1:35, 2:33, 3:2 | — |
| checks A2 | 55 | k=3:55 | 0:18, 1:18, 2:19 | — |
| checks B1 | 53 | k=3:53 | 0:18, 1:18, 2:17 | — |
| checks B2 | 35 | k=3:35 | 0:12, 1:11, 2:12 | — |
| checks C1 | 63 | k=3:63 | 0:21, 1:21, 2:21 | — |
| checks C2 | 57 | k=3:57 | 0:19, 1:19, 2:19 | — |
| corpus listening (todos) | 490 | k=4:490 | 0:125, 1:121, 2:122, 3:122 | — |
| corpus A1 | 200 | k=4:200 | 0:51, 1:49, 2:49, 3:51 | — |
| corpus A2 | 200 | k=4:200 | 0:51, 1:50, 2:50, 3:49 | — |
| corpus B1 | 25 | k=4:25 | 0:7, 1:5, 2:7, 3:6 | — |
| corpus B2 | 25 | k=4:25 | 0:6, 1:7, 2:6, 3:6 | — |
| corpus C1 | 20 | k=4:20 | 0:5, 1:4, 2:5, 3:6 | — |
| corpus C2 | 20 | k=4:20 | 0:5, 1:6, 2:5, 3:4 | — |
| exámenes finales (todos) | 22 | k=3:22 | 0:14, 1:8, 2:0 | 2 |
| examen a1 | 10 | k=3:10 | 0:5, 1:5, 2:0 | 2 |
| examen b1 | 12 | k=3:12 | 0:9, 1:3, 2:0 | 2 |
| placement | 24 | k=3:24 | 0:6, 1:17, 2:1 | — |

## Longitud de la opción correcta

| Grupo | N | más larga | o empatada | correcta / distractores |
|---|---|---|---|---|
| checks del currículum (todos) | 368 | 144 (39.1%) | 219 (59.5%) | 1.162 |
| checks A1 | 105 | 27 (25.7%) | 52 (49.5%) | 1.057 |
| checks A2 | 55 | 20 (36.4%) | 32 (58.2%) | 1.173 |
| checks B1 | 53 | 27 (50.9%) | 34 (64.2%) | 1.225 |
| checks B2 | 35 | 15 (42.9%) | 23 (65.7%) | 1.216 |
| checks C1 | 63 | 23 (36.5%) | 37 (58.7%) | 1.147 |
| checks C2 | 57 | 32 (56.1%) | 41 (71.9%) | 1.268 |
| corpus listening (todos) | 490 | 195 (39.8%) | 266 (54.3%) | 1.249 |
| corpus A1 | 200 | 59 (29.5%) | 90 (45.0%) | 1.186 |
| corpus A2 | 200 | 79 (39.5%) | 112 (56.0%) | 1.252 |
| corpus B1 | 25 | 15 (60.0%) | 19 (76.0%) | 1.36 |
| corpus B2 | 25 | 10 (40.0%) | 13 (52.0%) | 1.227 |
| corpus C1 | 20 | 16 (80.0%) | 16 (80.0%) | 1.482 |
| corpus C2 | 20 | 16 (80.0%) | 16 (80.0%) | 1.503 |
| exámenes finales (todos) | 22 | 8 (36.4%) | 15 (68.2%) | 1.221 |
| examen a1 | 10 | 2 (20.0%) | 6 (60.0%) | 1.111 |
| examen b1 | 12 | 6 (50.0%) | 9 (75.0%) | 1.312 |
| placement | 24 | 12 (50.0%) | 18 (75.0%) | 1.225 |

## Desglose por número de opciones (una posición solo existe en su k)

| Grupo | k | N | Posiciones | Muertas | más larga |
|---|---|---|---|---|---|
| checks del currículum (todos) | 3 | 358 | 0:120, 1:119, 2:119 | — | 39.4% |
| checks del currículum (todos) | 4 | 10 | 0:3, 1:3, 2:2, 3:2 | — | 30.0% |
| checks A1 | 3 | 95 | 0:32, 1:32, 2:31 | — | 25.3% |
| checks A1 | 4 | 10 | 0:3, 1:3, 2:2, 3:2 | — | 30.0% |
| checks A2 | 3 | 55 | 0:18, 1:18, 2:19 | — | 36.4% |
| checks B1 | 3 | 53 | 0:18, 1:18, 2:17 | — | 50.9% |
| checks B2 | 3 | 35 | 0:12, 1:11, 2:12 | — | 42.9% |
| checks C1 | 3 | 63 | 0:21, 1:21, 2:21 | — | 36.5% |
| checks C2 | 3 | 57 | 0:19, 1:19, 2:19 | — | 56.1% |
| corpus listening (todos) | 4 | 490 | 0:125, 1:121, 2:122, 3:122 | — | 39.8% |
| corpus A1 | 4 | 200 | 0:51, 1:49, 2:49, 3:51 | — | 29.5% |
| corpus A2 | 4 | 200 | 0:51, 1:50, 2:50, 3:49 | — | 39.5% |
| corpus B1 | 4 | 25 | 0:7, 1:5, 2:7, 3:6 | — | 60.0% |
| corpus B2 | 4 | 25 | 0:6, 1:7, 2:6, 3:6 | — | 40.0% |
| corpus C1 | 4 | 20 | 0:5, 1:4, 2:5, 3:6 | — | 80.0% |
| corpus C2 | 4 | 20 | 0:5, 1:6, 2:5, 3:4 | — | 80.0% |
| exámenes finales (todos) | 3 | 22 | 0:14, 1:8, 2:0 | 2 | 36.4% |
| examen a1 | 3 | 10 | 0:5, 1:5, 2:0 | 2 | 20.0% |
| examen b1 | 3 | 12 | 0:9, 1:3, 2:0 | 2 | 50.0% |
| placement | 3 | 24 | 0:6, 1:17, 2:1 | — | 50.0% |
