# Validez de la afirmación de maestría (V3.70 · Eje 4)

> Generado por `python -m scripts.audit_dossier mastery-claims`.
> Contrasta las modalidades declaradas con la matriz CEFR, el canal de
> evidencia y los mínimos del gate. Solo lectura.

## Tres registros que deben coincidir

- Modalidades de `MASTERY_SKILLS`: **9**.
- Destrezas de la matriz CEFR (`2.1.0`): **8**.
- Canales de evidencia (`MODALITY_CHANNEL`): **7**.

- Sin canal de evidencia: **interaction, mediation**.
- Sin requisitos en matriz: **pronunciation**.
- Sin competencias declaradas: **interaction, mediation**.

## Gates declarados

- Estados: not_started, developing, functional, demonstrated.
- Destrezas de producción: grammar, speaking, writing.
- Destrezas de apoyo (tope `functional`): vocabulary.
- Gate espaciado: 2 muestras × 2 días.
- Tipos de ítem de producción: speaking, writing, pronunciation, controlled_production.
- `novel_required` sumado en la matriz: **0**.
- `transfer_required` sumado en la matriz: **80**.

## Mínimos por nivel y destreza

| Nivel | Destreza | Maestría | Confianza | Evidencia | Transfer | Novel |
|---|---|---|---|---|---|---|
| A1 | vocabulary | 0.7 | 0.6 | 3 | 0 | 0 |
| A1 | grammar | 0.7 | 0.6 | 3 | 0 | 0 |
| A1 | listening | 0.6 | 0.5 | 2 | 0 | 0 |
| A1 | speaking | 0.55 | 0.5 | 2 | 0 | 0 |
| A1 | interaction | 0.7 | 0.6 | 3 | 0 | 0 |
| A1 | reading | 0.6 | 0.5 | 2 | 0 | 0 |
| A1 | writing | 0.55 | 0.5 | 2 | 0 | 0 |
| A1 | mediation | 0.7 | 0.6 | 3 | 0 | 0 |
| A2 | vocabulary | 0.7 | 0.6 | 3 | 0 | 0 |
| A2 | grammar | 0.7 | 0.6 | 3 | 0 | 0 |
| A2 | listening | 0.65 | 0.55 | 3 | 0 | 0 |
| A2 | speaking | 0.6 | 0.55 | 3 | 0 | 0 |
| A2 | interaction | 0.7 | 0.6 | 3 | 0 | 0 |
| A2 | reading | 0.65 | 0.55 | 3 | 0 | 0 |
| A2 | writing | 0.6 | 0.55 | 3 | 0 | 0 |
| A2 | mediation | 0.7 | 0.6 | 3 | 0 | 0 |
| B1 | vocabulary | 0.7 | 0.6 | 3 | 1 | 0 |
| B1 | grammar | 0.7 | 0.6 | 3 | 1 | 0 |
| B1 | listening | 0.7 | 0.6 | 3 | 1 | 0 |
| B1 | speaking | 0.65 | 0.6 | 3 | 1 | 0 |
| B1 | interaction | 0.7 | 0.6 | 3 | 1 | 0 |
| B1 | reading | 0.7 | 0.6 | 3 | 1 | 0 |
| B1 | writing | 0.65 | 0.6 | 3 | 1 | 0 |
| B1 | mediation | 0.7 | 0.6 | 3 | 1 | 0 |
| B2 | vocabulary | 0.75 | 0.65 | 4 | 2 | 0 |
| B2 | grammar | 0.75 | 0.65 | 4 | 2 | 0 |
| B2 | listening | 0.75 | 0.65 | 4 | 2 | 0 |
| B2 | speaking | 0.7 | 0.65 | 4 | 2 | 0 |
| B2 | interaction | 0.75 | 0.65 | 4 | 2 | 0 |
| B2 | reading | 0.75 | 0.65 | 4 | 2 | 0 |
| B2 | writing | 0.7 | 0.65 | 4 | 2 | 0 |
| B2 | mediation | 0.75 | 0.65 | 4 | 2 | 0 |
| C1 | vocabulary | 0.8 | 0.7 | 5 | 3 | 0 |
| C1 | grammar | 0.8 | 0.7 | 5 | 3 | 0 |
| C1 | listening | 0.8 | 0.7 | 5 | 3 | 0 |
| C1 | speaking | 0.75 | 0.7 | 5 | 3 | 0 |
| C1 | interaction | 0.8 | 0.7 | 5 | 3 | 0 |
| C1 | reading | 0.8 | 0.7 | 5 | 3 | 0 |
| C1 | writing | 0.75 | 0.7 | 5 | 3 | 0 |
| C1 | mediation | 0.8 | 0.7 | 5 | 3 | 0 |
| C2 | vocabulary | 0.85 | 0.75 | 6 | 4 | 0 |
| C2 | grammar | 0.85 | 0.75 | 6 | 4 | 0 |
| C2 | listening | 0.85 | 0.75 | 6 | 4 | 0 |
| C2 | speaking | 0.8 | 0.75 | 6 | 4 | 0 |
| C2 | interaction | 0.85 | 0.75 | 6 | 4 | 0 |
| C2 | reading | 0.85 | 0.75 | 6 | 4 | 0 |
| C2 | writing | 0.8 | 0.75 | 6 | 4 | 0 |
| C2 | mediation | 0.85 | 0.75 | 6 | 4 | 0 |

## Línea base sin evidencia

| Destreza | Estado | Demostrado | Banda |
|---|---|---|---|
| vocabulary | not_started | False | — |
| grammar | not_started | False | — |
| pronunciation | not_started | False | — |
| listening | not_started | False | — |
| speaking | not_started | False | — |
| reading | not_started | False | — |
| writing | not_started | False | — |
| interaction | not_started | False | — |
| mediation | not_started | False | — |

- Profundidad de evidencia sin muestras (grammar A1): `depth = low`, `meets_matrix = False`.