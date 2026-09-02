# V2.7 (escalado 3/4) — V27-Depth-C1: profundizar C1 con la plantilla B1

## Rol
Backend (contenido curricular). Autor del **contenido de profundidad** de `backend/curriculum/c1.json`,
tomando **B1 como plantilla maestra** (implementación de referencia ya cerrada en V2.7). No tocas
frontend, ni lógica de servicios, ni el scoring.

## Objetivo
Subir el **CEFR Depth Score** de C1 de **55,5 → 80+** mediante competencias reales. Meta orientativa:
**~13–14 objetivos** (hoy 7) con evidencia completa, 7 secciones y las 9 fases del loop en cada unidad.

## Contexto

### Plantilla maestra
- `docs/UNIT_ARCHITECTURE.md` — norma de 7 secciones + 9 fases + evidencia por sección.
- `backend/curriculum/b1.json` — implementación de referencia ya verificada (18 objetivos, depth 90,4).
  **Imítala** (adaptando registro y complejidad al nivel C1: hedging, matización, precisión léxica).

### Estado actual de C1 (dashboard V2.7)
| Métrica | Valor |
|---|---|
| Unidades / Objetivos | 4 / 7 |
| Depth Score | 55,5 |
| Unit Coverage (media) | 85,7% |
| Loop (media) | *(por cerrar en unidades finas)* |

Huecos por sección (porcentaje de unidades pobladas):

| Sección | Cobertura | Diagnóstico |
|---|---|---|
| vocabulary | 100% | OK |
| **grammar** | **75,0% (3/4)** | una unidad sin grammar |
| **listening** | **25,0% (1/4)** | hueco principal: solo 1 de 4 unidades integra listening |
| speaking | 100% | OK |
| interaction | 100% | OK |
| review / assessment | 100% | OK |

## Tarea detallada

1. **Listening por unidad.** Añade a cada unidad un objetivo de listening con `listening_items` del
   banco C1 (corpus C1 `c101`–`c120`). Subskills variados: `inference`, `speaker_intention`,
   `attitude`, `nuance`, `multiple_speakers` (amplía `subskill_breadth`).
2. **Grammar en la unidad que falta** (una unidad sin grammar).
3. **Cerrar el loop en todos los objetivos.** Etiqueta/añade `retrieve`/`transfer`/`review`/`assess`
   donde falte.
4. **Volumen real.** Sube de 7 a ~13–14 objetivos: precisión léxica, hedging/matización, idiomas en
   contexto, discurso abstracto con evidencia completa. Competencias reales, no duplicados.
5. **Verificar** y actualizar `docs/CURRICULUM_COVERAGE.md` + registrar el delta.

## Criterios de aceptación
- `depth_score(c1) >= 80` (medido con `python -m scripts.curriculum_coverage --quality`).
- Cada unidad C1: `covered_sections == 7` y `loop_pct == 100`.
- `listening` en `section_coverage` de C1 = 100% por unidad.
- Cero objetivos artificiales: todo objetivo nuevo tiene evidencia completa.
- `validate_level(load_level("c1")) == []` y `pytest tests/ -q` verde.

## Restricciones
- Solo contenido (`backend/curriculum/c1.json`) + docs. No toques `services/`, `scripts/`, frontend.
- No cambies `DEPTH_WEIGHTS` ni los targets de volumen/densidad.
- No renumeres ids existentes; añade ids nuevos y únicos siguiendo la convención `c1-m..-u..-l..-o..`.
- Un único commit `feat: profundizar C1 (plantilla Unit Architecture)`. No push.

## Salida esperada
Objetivos añadidos/modificados por unidad, el `depth_score` antes/después, el nuevo mapa de secciones
de C1 y el delta en `quality_report_delta()`.
