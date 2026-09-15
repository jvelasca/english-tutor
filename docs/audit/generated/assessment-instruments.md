# Instrumentos de nivelación (V3.70 · Eje 5)

> Generado por `python -m scripts.audit_dossier assessment-instruments`.
> Mide placement, exámenes, remediación, gate de unidad y la
> equivalencia de los umbrales de banda. Solo lectura.

## Placement

- Ítems: **24** · máximo por sesión 8 · mínimo 4.
- Umbral de parada `SE < 0.5`: mejor caso alcanzable con 8 ítems **SE ≥ 0.7071** ⇒ alcanzable = **False**.
- Dificultades: 1:4, 2:4, 3:4, 4:4, 5:4, 6:4.
- Correcta = opción más larga: 12 de 24 (50.0%).

## Exámenes finales

| Nivel | Ítems | Destrezas | Mínimo por destreza |
|---|---|---|---|
| A1 | 10 | grammar, listening, reading, vocabulary | 0.75 |
| B1 | 12 | grammar, listening, reading, vocabulary | 0.75 |

- Niveles SIN examen final: **A2, B2, C1, C2**.

## Remediación y gate de unidad

- Banco de remediación `grammar`: 6 ítems.
- Banco de remediación `vocabulary`: 6 ítems.
- Banco de remediación `reading`: 3 ítems.
- Banco de remediación `listening`: 5 ítems.
- Banco de remediación `speaking`: 6 ítems.

- Secciones de unidad: vocabulary, grammar, listening, speaking, interaction, review, assessment.
- Umbrales de gate: vocabulary 0.8, grammar 0.8, listening 0.75, speaking 0.7.

## Umbrales de banda

- Niveles emitidos por los tres estimadores: A1, A2, B1, B2, C1, C2.
- Desacuerdos entre los tres estimadores: **0**.
- Bandas de la escalera alcanzables por `band_for_numeric`: a1, a2, a2+, b1, b1+, b2, b2+, c1, c2, pre-a1.
- Sub-bandas declaradas (`+`): a2+, b1+, b2+ · emitidas por los estimadores: ninguna.