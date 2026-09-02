# V2.7 (escalado 2/4) — V27-Depth-B2: profundizar B2 con la plantilla B1

## Rol
Backend (contenido curricular). Autor del **contenido de profundidad** de `backend/curriculum/b2.json`,
tomando **B1 como plantilla maestra** (implementación de referencia ya cerrada en V2.7). No tocas
frontend, ni lógica de servicios, ni el scoring.

## Objetivo
Subir el **CEFR Depth Score** de B2 de **68,4 → 82+** mediante competencias reales. Meta orientativa:
**~13–14 objetivos** (hoy 9) con evidencia completa, 7 secciones y las 9 fases del loop en cada unidad.

## Contexto

### Plantilla maestra
- `docs/UNIT_ARCHITECTURE.md` — norma de 7 secciones + 9 fases + evidencia por sección.
- `backend/curriculum/b1.json` — implementación de referencia ya verificada (18 objetivos, depth 90,4).
  **Imítala** (adaptando el registro y la complejidad al nivel B2).

### Estado actual de B2 (dashboard V2.7)
| Métrica | Valor |
|---|---|
| Unidades / Objetivos | 3 / 9 |
| Depth Score | 68,4 |
| Unit Coverage (media) | 80,9% |
| Loop (media) | *(por cerrar en la unidad fina)* |

Huecos por sección (porcentaje de unidades pobladas):

| Sección | Cobertura | Diagnóstico |
|---|---|---|
| vocabulary | 100% | OK |
| **grammar** | **66,7% (2/3)** | una unidad sin grammar |
| **listening** | **66,7% (2/3)** | una unidad sin listening |
| **speaking** | **66,7% (2/3)** | una unidad sin speaking |
| **interaction** | **66,7% (2/3)** | una unidad sin interaction |
| review / assessment | 100% | OK |

## Tarea detallada

1. **Completar la unidad fina.** B2 tiene 3 unidades y una de ellas no declara grammar/listening/
   speaking/interaction. Añade a esa unidad los objetivos que faltan, cableando `listening_items` del
   banco B2 (`l16`, `l17`, `l20`, `l21` y el corpus B2 `c031`–`c040` / `c086`–`c100`) y `scenario_ids`
   B2 (`work_meeting`,
   `problem_solving`, `interview`, `negotiation`, `team_presentation`).
2. **Cerrar el loop en todos los objetivos.** Etiqueta/añade `retrieve`/`transfer`/`review`/`assess`
   donde falte (ver `docs/UNIT_ARCHITECTURE.md` §3–4).
3. **Volumen real.** Sube de 9 a ~13–14 objetivos: interacción B2 (presentar opinión, responder,
   negociar acuerdo), discourse markers avanzados y transferencia. Competencias reales, no duplicados.
4. **Verificar** y actualizar `docs/CURRICULUM_COVERAGE.md` + registrar el delta.

## Criterios de aceptación
- `depth_score(b2) >= 82` (medido con `python -m scripts.curriculum_coverage --quality`).
- Cada unidad B2: `covered_sections == 7` y `loop_pct == 100`.
- `grammar`/`listening`/`speaking`/`interaction` en `section_coverage` de B2 = 100% por unidad.
- Cero objetivos artificiales: todo objetivo nuevo tiene evidencia completa.
- `validate_level(load_level("b2")) == []` y `pytest tests/ -q` verde.

## Restricciones
- Solo contenido (`backend/curriculum/b2.json`) + docs. No toques `services/`, `scripts/`, frontend.
- No cambies `DEPTH_WEIGHTS` ni los targets de volumen/densidad.
- No renumeres ids existentes; añade ids nuevos y únicos siguiendo la convención `b2-m..-u..-l..-o..`.
- Un único commit `feat: profundizar B2 (plantilla Unit Architecture)`. No push.

## Salida esperada
Objetivos añadidos/modificados por unidad, el `depth_score` antes/después, el nuevo mapa de secciones
de B2 y el delta en `quality_report_delta()`.
