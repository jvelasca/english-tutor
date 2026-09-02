# Evidence Graph (V2.12)

Conecta cada **can-do** del currículo con la evidencia del alumno:

```
CAN-DO
  ├── vocabulary
  ├── grammar
  ├── discourse
  ├── listening
  ├── speaking
  ├── interaction
  └── transfer
         ↓
    limiting factor → mastery
```

## Objetivo

Que el Adaptive Engine no solo diga *qué* hacer, sino *por qué*, con
contraste entre dimensiones fuertes y el factor limitante:

```
Why this activity?
Because:
1. Your B1 interaction mastery is 61%.
2. Your vocabulary is already 88%.
3. Transfer evidence is missing.
4. This activity directly targets transfer.
```

## Motor puro

`services/evidence_graph.py`:

- `objective_node()` — dimensiones + limiting factor + focus
- `build_level_graph()` — grafo del nivel + top limiting factor
- `explain_because()` — viñetas estructuradas
- `enrich_next_best()` — enriquece `/next-best` con `because[]`

Versión: `2.12.0`.

## API

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/academy/evidence-graph` | Grafo del nivel |
| GET | `/api/academy/evidence-graph/objective/{id}` | Nodo can-do |
| GET | `/api/academy/next-best` | + `because`, `limiting_factor`, `can_do` |

## Frontend

- `EvidenceGraphPanel` en la pestaña Profile
- `NextBestCard` muestra la lista **Because:** y el factor limitante

## Relación con V2.10 / V2.11

- V2.10 aporta kinds de evidencia (`familiar`/`transfer`/`novel`/`delayed`)
- V2.11 agenda *cuándo* volver a pedir evidencia (FSRS)
- V2.12 conecta *qué competencia* limita el can-do y *por qué* esta actividad
