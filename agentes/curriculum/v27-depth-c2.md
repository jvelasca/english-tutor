# V2.7 (escalado 4/4) — V27-Depth-C2: profundizar C2 con la plantilla B1

## Rol
Backend (contenido curricular). Autor del **contenido de profundidad** de `backend/curriculum/c2.json`,
tomando **B1 como plantilla maestra** (implementación de referencia ya cerrada en V2.7). No tocas
frontend, ni lógica de servicios, ni el scoring.

## Objetivo
Subir el **CEFR Depth Score** de C2 de **49,2 → 80+** mediante competencias reales. Meta orientativa:
**~12–13 objetivos** (hoy 5) con evidencia completa, 7 secciones y las 9 fases del loop en cada unidad.

## Contexto

### Plantilla maestra
- `docs/UNIT_ARCHITECTURE.md` — norma de 7 secciones + 9 fases + evidencia por sección.
- `backend/curriculum/b1.json` — implementación de referencia ya verificada (18 objetivos, depth 90,4).
  **Imítala** (adaptando registro y complejidad al nivel C2: comunicación diplomática, matiz, ironía,
  discurso implícito).

### Estado actual de C2 (dashboard V2.7)
| Métrica | Valor |
|---|---|
| Unidades / Objetivos | 3 / 5 |
| Depth Score | 49,2 |
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

1. **Completar la unidad fina.** C2 tiene 3 unidades y una de ellas no declara grammar/listening/
   speaking/interaction. Añade los objetivos que faltan, cableando `listening_items` del banco C2
   (corpus C2 `c121`–`c140`) y `scenario_ids` C2 (`persuasion`, `conflict_mediation`, `academic_defence`,
   `abstract_conversation`, `stakes_negotiation`, `diplomatic_talk`).
2. **Cerrar el loop en todos los objetivos.** Etiqueta/añade `retrieve`/`transfer`/`review`/`assess`
   donde falte.
3. **Volumen real.** Sube de 5 a ~12–13 objetivos: matiz/hedging, discurso implícito, diplomacia,
   ironía y registro formal, cada uno con evidencia completa. Competencias reales, no duplicados.
4. **Verificar** y actualizar `docs/CURRICULUM_COVERAGE.md` + registrar el delta.

## Criterios de aceptación
- `depth_score(c2) >= 80` (medido con `python -m scripts.curriculum_coverage --quality`).
- Cada unidad C2: `covered_sections == 7` y `loop_pct == 100`.
- `grammar`/`listening`/`speaking`/`interaction` en `section_coverage` de C2 = 100% por unidad.
- Cero objetivos artificiales: todo objetivo nuevo tiene evidencia completa.
- `validate_level(load_level("c2")) == []` y `pytest tests/ -q` verde.

## Restricciones
- Solo contenido (`backend/curriculum/c2.json`) + docs. No toques `services/`, `scripts/`, frontend.
- No cambies `DEPTH_WEIGHTS` ni los targets de volumen/densidad.
- No renumeres ids existentes; añade ids nuevos y únicos siguiendo la convención `c2-m..-u..-l..-o..`.
- Un único commit `feat: profundizar C2 (plantilla Unit Architecture)`. No push.

## Salida esperada
Objetivos añadidos/modificados por unidad, el `depth_score` antes/después, el nuevo mapa de secciones
de C2 y el delta en `quality_report_delta()`.
