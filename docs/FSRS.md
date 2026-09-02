# FSRS-lite — Retention Scheduler (V2.11)

Scheduler de repetición espaciada sobre el **Evidence Model** (V2.10).

```
Evidence → Card → Due queue → Review (Again/Hard/Good/Easy) → Reschedule
```

## Preguntas que responde (auditoría)

| Pregunta | Campo |
|---|---|
| What? | `target_type` + `target_id` + `label` |
| Why? | `why` (forgetting-curve, weak-skill, weak-lexicon…) |
| When? | `due_at` / `next_in_days` |
| How strong? | `stability` + `retrievability` + `difficulty` |
| Last evidence? | `last_review_at` / `last_grade` |
| Next evidence? | próximo `due_at` + intervalo sugerido |

## Motor puro

`services/fsrs.py` (FSRS-4.5-lite, sin calibrar 19 pesos):

- Retrievability `(1 + FACTOR·t/S)^DECAY`
- Grades `1..4` (Again / Hard / Good / Easy)
- `schedule(card, grade)` → nueva stability/difficulty/due
- `explain(card)` → bloque auditable completo
- `due_queue(cards)` → urgencia por menor R

Versión: `2.11.0-lite`.

## Orígenes de cartas

Al sincronizar (`sync_fsrs_cards`):

- **skill** — destrezas con evidencia y `review_due` / score bajo / sin delayed
- **lexicon** — ítems `weak` / `learning` / `known` (reconocimiento)

Las cartas ya revisadas (`reps > 0`) conservan el scheduling; solo se refresca `why`.

## API

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/academy/fsrs/due` | Cola due + explain |
| GET | `/api/academy/fsrs/summary` | Totales por estado/tipo |
| POST | `/api/academy/fsrs/sync` | Resincroniza desde evidencia |
| POST | `/api/academy/fsrs/review` | Grade → reprograma |

Persistencia: tabla `fsrs_cards`.

## Frontend

`FsrsReviewPanel` en la pestaña Today: muestra la carta due y los 4 grades.

## Relación con V2.10 / V2.12

- V2.10 aporta el Evidence Model (`familiar`/`transfer`/`novel`/`delayed`).
- V2.11 agenda **cuándo** volver a pedir evidencia.
- V2.12 (Evidence Graph) conectará can-do → subskills → limiting factor.
