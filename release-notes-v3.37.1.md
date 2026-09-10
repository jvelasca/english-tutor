# v3.37.1 — Política de consolidación y regresión de la escalera de recall

**Cierre de la auditoría de V3.37.0: la escalera de recall deja de ascender con un
acierto suelto y aprende a RETROCEDER hacia más apoyo. Un peldaño
(`translation`/`definition`/`cloze`) solo se da por SUPERADO con ≥2 éxitos en ≥2
DÍAS NATURALES distintos (la progresión pasa a ser EVIDENCIA → CONSOLIDACIÓN →
MÁS EXIGENCIA), y ≥2 fallos SIN ningún éxito en el peldaño ideal hacen bajar la
recomendación al peldaño inmediatamente inferior, nunca por debajo de
`translation`. Sin migración de BD (el peldaño ya se declaraba en `activity_id`
desde V3.37.0), contrato HTTP aditivo y sin tocar scoring ni FSRS. La
automaticidad por skill (P1-03), `cloze_coverage` y el refactor de `wordDrill.tsx`
se difieren a V3.38/V3.39.**
Versión de app `3.37.0 → 3.37.1`. Backend (política pura + histogramas aditivos
del resumen) + frontend (tipo) + tests y docs.

## Contexto

La auditoría de V3.37.0 (9,4/10) aprobó la arquitectura de cues graduados pero
señaló una **asimetría** entre los dos lados de la evidencia:

```text
        EVIDENCIA
            │
    ┌───────┴───────┐
    ↓               ↓
 SUCCESS         FAILURE
    ↓               ↓
PROGRESSION   ❌ sin política
```

- **P1-01** — `next_recall_rung` ascendía con UN solo éxito: `translation → 1
  acierto → definition`. Un acierto suelto puede ser accidental, con latencia
  alta, tras mirar contexto o sobre una palabra trivial; el sistema confundía
  «un intento correcto» con «peldaño superado».
- **P1-02** — no existía regresión: fallos repetidos en `cloze` no bajaban el
  apoyo porque el histograma `recall_rungs` solo cuenta éxitos. El sistema sabía
  responder «¿hasta dónde ha llegado?» pero no «¿dónde puede rendir AHORA?».

V3.37.1 formaliza las **dos** políticas en la capa pura, sin rehacer
arquitectura.

## Qué cambia

### 1. Progresión: consolidación, no un acierto suelto (`services/recall.py`)

- `RECALL_RUNG_PASS_MIN_SUCCESSES = 2` y `RECALL_RUNG_PASS_MIN_DAYS = 2`
  (declarados y calibrables, junto a `RECALL_CUES`).
- `_rung_passed(successes, days)` — un peldaño está SUPERADO solo con ≥2 éxitos
  en ≥2 días naturales distintos. El volumen del mismo día tampoco basta (mismo
  rigor que `distinct_success_days`).
- El umbral se mide sobre los **éxitos del propio peldaño**, NO sobre
  `independent_successes`: `cued`/`guided` nunca son `independent` y exigir
  automaticidad bloquearía la escalera por completo.

### 2. Regresión: remediación hacia más apoyo (`services/recall.py`)

- `RECALL_REGRESSION_FAILURES = 2`.
- Si el peldaño ideal acumula ≥2 fallos **sin ningún éxito**, `next_recall_rung`
  devuelve el peldaño inmediatamente inferior (más apoyo). Nunca baja de
  `translation` y fallar jamás hace subir.
- **Sin oscilación**: el peldaño inferior está consolidado por construcción (es
  el primero que pasó el filtro de `_rung_passed`), así que la recomendación se
  queda ahí hasta que aparezca un éxito en el superior.
- Un fallo solo repite el peldaño; la remediación exige **patrón**, no un
  tropiezo. Un acierto cualquiera en el peldaño ya evita la regresión.
- `resolve_recall_cue` no cambia: si el peldaño regresado no tiene contenido,
  sigue degradando SOLO hacia más apoyo.

### 3. Histogramas aditivos del resumen (`services/evidence.py`, `repositories/evidence.py`)

- `summarize_evidence`/`empty_summary` y `summarize_by_target` añaden:
  - `recall_rung_days` — días naturales distintos con ÉXITO por peldaño (lo que
    exige la consolidación);
  - `recall_rung_failures` — intentos FALLIDOS por peldaño (lo que lee la
    regresión).
- Ambos se derivan del `activity_id` `drill:recall:<peldaño>` que V3.37 ya
  escribía: **sin migración de BD**.
- **Paridad exacta pura↔SQL** fijada por test (`COUNT(DISTINCT
  NULLIF(substr(occurred_at,1,10),''))` y `COUNT(*)` con `success = 0`).
- La evidencia legacy `drill:recall` (sin peldaño) no entra en ningún histograma:
  no es evidencia negativa ni acredita un peldaño que no declaraba.

### 4. Contrato (aditivo)

- `LexicalEvidence` (schema Pydantic y tipo TS) amplía `recall_rung_days` y
  `recall_rung_failures` con default `{}`.
- El resto del contrato HTTP no cambia. La cola de repaso sigue sin exponer el
  cue ni la forma esperada (P1-03 de V3.35.1 intacto); solo cambia el
  `recommended_cue` que ya exponía, ahora consolidado o regresado según la
  política.

### 5. Sin cambios

`resolve_recall_cue`, `recall_prompt_for`, `blank_out`, scoring, FSRS, la
semántica del intervalo de evidencia, `error_type` (observacional),
`domain/vocabulary.py` y `routers/vocabulary.py`. El frontend solo necesita el
tipo nuevo (`wordDrill.tsx` consume `recommended_cue`/el cue servido sin cambios).

## Verificación

- Backend: `ruff check .` limpio y `pytest` → **1824 passed** (+11 sobre
  v3.37.0), con el nuevo `tests/test_recall_policy_v3371.py`.
- Frontend: `tsc --noEmit` limpio, `vitest` → **65 ficheros/560 tests** y
  `npm run build` OK.
- `python scripts/check_release_consistency.py` → **3.37.1** exit 0.

### Matriz de la política (tests nuevos)

| Caso | Entrada | Recomendación |
|---|---|---|
| Sin evidencia | — | `translation` |
| 1 éxito en 1 día | `translation` | `translation` (no consolida) |
| 4 éxitos el mismo día | `translation` | `translation` (no espaciado) |
| 2 éxitos en 2 días | `translation` | `definition` (consolidado) |
| 1 fallo | `definition` (ideal) | `definition` (repite) |
| 2+ fallos, 0 éxitos | `definition` (ideal) | `translation` (regresa) |
| 2 fallos, 1 éxito | `definition` (ideal) | `definition` (con acierto no regresa) |
| Legacy `drill:recall` | éxito/fallo | no alimenta ninguna política |

## Fuera de alcance (V3.38/V3.39)

- **P1-03 automaticidad por skill/modalidad** — hoy `skill=""` en todos los
  eventos léxicos; requiere segmentar y agregar por skill (cambio de modelo de
  evidencia, no de política) → V3.38.
- **P2-01 `cloze_coverage`** (métrica de disponibilidad del corpus),
  **P2-03 `example_for_many`** (coste de la Review Queue) y **P2-04 refactor de
  `wordDrill.tsx`** → V3.39.
- Cualquier migración de BD, cambio de scoring/FSRS o cambio de contrato
  incompatible.
