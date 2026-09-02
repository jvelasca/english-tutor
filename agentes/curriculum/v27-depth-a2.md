# V2.7 (escalado 1/4) — V27-Depth-A2: profundizar A2 con la plantilla B1

## Rol
Backend (contenido curricular). Autor del **contenido de profundidad** de `backend/curriculum/a2.json`,
tomando **B1 como plantilla maestra** (la implementación de referencia ya cerrada en V2.7). No tocas
frontend, ni lógica de servicios, ni el scoring.

## Objetivo
Subir el **CEFR Depth Score** de A2 de **60,9 → 80+** mediante competencias reales, no multiplicando
objetivos vacíos. Meta orientativa: **~15–17 objetivos** (hoy 11) con evidencia completa, 7 secciones
y las 9 fases del loop en cada unidad.

## Contexto

### Plantilla maestra
- `docs/UNIT_ARCHITECTURE.md` — norma de 7 secciones + 9 fases + evidencia por sección.
- `backend/curriculum/b1.json` — implementación de referencia ya verificada (18 objetivos, depth 90,4,
  `covered_sections == 7` y `loop_pct == 100` en las 4 unidades). **Imítala**.

### Estado actual de A2 (dashboard V2.7)
| Métrica | Valor |
|---|---|
| Unidades / Objetivos | 7 / 11 |
| Depth Score | 60,9 |
| Unit Coverage (media) | 87,7% |
| Loop (media) | *(por cerrar en unidades finas)* |

Huecos por sección (porcentaje de unidades pobladas):

| Sección | Cobertura | Diagnóstico |
|---|---|---|
| vocabulary | 85,7% (6/7) | una unidad sin vocabulario explícito |
| grammar | 100% | OK |
| **listening** | **28,6% (2/7)** | hueco principal: solo 2 de 7 unidades integran listening |
| speaking | 100% | OK |
| interaction | 100% | OK |
| review / assessment | 100% | OK (módulo Final + fases) |

## Tarea detallada

1. **Listening por unidad.** Añade a cada unidad un objetivo de listening con `listening_items` del
   banco A2 (referencias por ID del nivel correcto; consulta `services/listening.py` para los ítems A2:
   `l4`–`l6`, `l10`, `l12`, `l13` y el corpus A2 `c011`–`c020` / `c056`–`c070`). Declara subskills de
   listening variados (`gist`, `detail`,
   `speaker_intention`, `inference`…) para ampliar `subskill_breadth`.
2. **Cerrar el loop en todos los objetivos.** Etiqueta/añade actividades con `phase`: `retrieve`,
   `transfer`, `review`, `assess`, como hace B1 (ver `docs/UNIT_ARCHITECTURE.md` §4).
3. **Completar vocabulary en la unidad que falta** (una unidad con la sección vacía).
4. **Volumen real.** Sube de 11 a ~15–17 objetivos: añade competencias reales (interaction, discourse,
   transferencia, listening), no dupliques objetivos. Cada objetivo nuevo con `concepts`/`vocabulary`,
   checks de destrezas evaluables, actividades con fase y referencias a bancos cuando aplique.
5. **Verificar** (ver abajo) y actualizar `docs/CURRICULUM_COVERAGE.md` + registrar el delta.

## Criterios de aceptación
- `depth_score(a2) >= 80` (medido con `python -m scripts.curriculum_coverage --quality`).
- Cada unidad A2: `covered_sections == 7` y `loop_pct == 100`.
- `listening` en `section_coverage` de A2 = 100% por unidad.
- Cero objetivos artificiales: todo objetivo nuevo tiene evidencia completa.
- `validate_level(load_level("a2")) == []` y `pytest tests/ -q` verde.

## Restricciones
- Solo contenido (`backend/curriculum/a2.json`) + docs. No toques `services/`, `scripts/`, frontend.
- No cambies `DEPTH_WEIGHTS` ni los targets de volumen/densidad.
- No renumeres ids existentes; añade ids nuevos y únicos siguiendo la convención `a2-m..-u..-l..-o..`.
- Un único commit `feat: profundizar A2 (plantilla Unit Architecture)`. No push.

## Salida esperada
Objetivos añadidos/modificados por unidad, el `depth_score` antes/después, el nuevo mapa de secciones
de A2 y el delta en `quality_report_delta()`.
