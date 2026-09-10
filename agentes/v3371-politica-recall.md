# V3.37.1 — Política de consolidación y regresión de la escalera de recall

> Rol: documento de diseño e implementación del candidato **V3.37.1**. Es un
> patch **quirúrgico** sobre V3.37.0 que cierra sus dos P1 pedagógicos sin
> rehacer arquitectura y **sin** migración de BD. Se publica como **v3.37.1**.
> Si lo retomas desde otro contexto, este archivo es autocontenido: incluye el
> estado de partida, la política formal, los ficheros y los criterios de
> aceptación.
>
> Normas que este eslabón respeta:
>
> - **Premisa 21**: la UI nunca declara acierto; el servidor re-deriva el
>   peldaño y puntúa. V3.37.1 no toca scoring.
> - **Separación decisión/disponibilidad**: `next_recall_rung` decide el peldaño
>   pedagógico; `resolve_recall_cue` lo degrada SOLO hacia más apoyo según el
>   contenido real. V3.37.1 endurece la decisión, no la disponibilidad.
> - **D5/E3**: la evidencia debe estar ESPACIADA para consolidar. La
>   consolidación exige ≥2 éxitos en ≥2 DÍAS NATURALES distintos.
> - **No inventar contenido**: ningún cambio añade generación; los histogramas
>   nuevos se derivan del `activity_id` que V3.37 ya escribía.
> - **Evidencia legacy ≠ evidencia negativa**: `drill:recall` (sin peldaño) no
>   alimenta la progresión ni la regresión.
>
> Borrador: 2026-09-10.

## Relevo rápido (leer antes de tocar nada)

- Versión estable de partida: **3.37.0** (`backend/config.py::VERSION`); la
  entrega es **3.37.1**.
- **No hace falta migración de BD**: `learning_evidence` ya tiene `activity_id`
  desde V3.36.0 y V3.37 ya escribe `drill:recall:<peldaño>`. Si crees que
  necesitas una columna nueva, párate y revisa el esquema real.
- Fuente de verdad del estado: `CHANGELOG.md` + `docs/RELEVO.md` (nota superior).
- No se tocan: scoring, FSRS, la semántica del intervalo de evidencia,
  `error_type`, `blank_out`, `recall_prompt_for` ni el contrato HTTP salvo campos
  aditivos.

## El hallazgo que motiva V3.37.1

La auditoría de V3.37.0 (9,4/10) aprobó la arquitectura de cues graduados
(`translation (cued) < definition (cued) < cloze (guided)`) pero detectó una
**asimetría**: el lado del ÉXITO tenía política de progresión y el lado del
FALLO no tenía ninguna.

```text
V3.37.0                          V3.37.1
EVIDENCIA                        EVIDENCIA
   │                                │
┌──┴──┐                         ┌───┴───┐
↓     ↓                         ↓       ↓
SUCCESS FAILURE              SUCCESS  FAILURE
↓        ↓                      ↓        ↓
PROGRESSION ❌              consolidación remediación
  1 éxito → sube                2 éxitos/2 días   ≥2 fallos sin éxito
                                → sube            → baja apoyo
```

- **P1-01** — `next_recall_rung` ascendía con UN solo éxito (`translation → 1
  acierto → definition`). Un acierto suelto puede ser accidental, con latencia
  alta, tras mirar contexto o sobre una palabra trivial.
- **P1-02** — fallos repetidos en `cloze` no bajaban el apoyo: `recall_rungs` es
  un histograma de éxitos. El sistema no respondía «¿dónde puede rendir AHORA?».

## Política formal

Dos capas separadas, ambas en `services/recall.py`:

```text
progresión:  un peldaño está SUPERADO si
             successes >= RECALL_RUNG_PASS_MIN_SUCCESSES (2)
             Y days   >= RECALL_RUNG_PASS_MIN_DAYS       (2)
             ideal = primer peldaño NO superado de RECALL_CUES;
             si todos superados → "cloze" (mantenimiento espaciado).

regresión:   si failures[ideal] >= RECALL_REGRESSION_FAILURES (2)
             Y successes[ideal] == 0
                 → devolver el peldaño inmediatamente inferior
             nunca por debajo de "translation".
```

Constantes declaradas y calibrables (junto a `RECALL_CUES`):

```python
RECALL_RUNG_PASS_MIN_SUCCESSES = 2
RECALL_RUNG_PASS_MIN_DAYS = 2
RECALL_REGRESSION_FAILURES = 2
```

Decisiones de diseño (justificadas en el código):

- El umbral se mide sobre **éxitos del propio peldaño**, no sobre
  `independent_successes`: `cued`/`guided` nunca son `independent` y exigir
  automaticidad bloquearía la escalera.
- Un fallo NO borra éxitos ya logrados, pero **≥2 fallos sin ningún éxito** en el
  peldaño ideal estabilizan la recomendación en el anterior. **Oscilación
  imposible**: el peldaño inferior ya está consolidado por construcción, así que
  la recomendación se queda ahí hasta que aparezca un éxito en el superior.
- `resolve_recall_cue` no cambia: si el peldaño regresado no tiene contenido,
  sigue bajando hacia más apoyo.

## Cambios por fichero

### 1. Servicio puro de la escalera — `backend/services/recall.py`

- Añade las tres constantes y los helpers puros `_int_field`/`_rung_stats`/
  `_rung_passed`.
- Reescribe `next_recall_rung` en dos fases: ideal por consolidación y regresión
  sobre el ideal.
- No cambia `resolve_recall_cue` ni `recall_prompt_for` ni `blank_out`.

### 2. Resumen de evidencia puro — `backend/services/evidence.py`

- `summarize_evidence` añade dos campos ADITIVOS:
  - `recall_rung_days: dict[str, int]` — días naturales distintos con éxito por
    peldaño;
  - `recall_rung_failures: dict[str, int]` — intentos fallidos por peldaño.
- Se derivan de `activity_id` (`drill:recall:<peldaño>`) y `occurred_at[:10]`.
  El peldaño se calcula ANTES del corte por éxito para poder contar fallos.
- `empty_summary()` devuelve ambos como `{}`.

### 3. Agregado SQL — `backend/repositories/evidence.py`

- `summarize_by_target` añade dos consultas agrupadas por `activity_id`:
  `COUNT(DISTINCT NULLIF(substr(occurred_at,1,10),''))` de los éxitos y
  `COUNT(*)` de los fallos (`success = 0`). El `NULLIF` replica el 0 de la
  versión pura para la paridad exacta.

### 4. Contrato (aditivo) — `backend/schemas/vocabulary.py` y `frontend/src/types/api.ts`

- `LexicalEvidence` gana `recall_rung_days` y `recall_rung_failures` (default
  `{}`). Sin romper clientes. El fixture de `frontend/src/api/learning.test.ts`
  se actualiza para `tsc`.

### 5. Sin cambios

`domain/vocabulary.py`, `routers/vocabulary.py`, `services/lexicon.py`,
`domain/review.py` (la cola ya consume `next_recall_rung`) y `wordDrill.tsx`
(sigue recibiendo `recommended_cue`/el cue servido).

## Tests

### Backend — nuevo `backend/tests/test_recall_policy_v3371.py`

- `translation` 1 éxito en 1 día → NO asciende.
- `translation` 2+ éxitos el MISMO día → NO asciende.
- `translation` 2 éxitos en 2 días distintos → asciende a `definition`.
- `definition` consolidado → `cloze`; techo en `cloze`.
- 1 fallo → repite el peldaño (ni asciende ni regresa).
- ≥2 fallos en el peldaño ideal sin ningún éxito → regresa un peldaño.
- La regresión nunca baja de `translation`.
- 2 fallos CON algún éxito → NO regresa.
- Tras regresar, `resolve_recall_cue` sigue bajando hacia más apoyo (nunca sube).
- Evidencia legacy `drill:recall` no cuenta ni para progresión ni para regresión.
- Histogramas puros de días/fallos.
- Paridad pura↔SQL de `recall_rung_days`/`recall_rung_failures` y política leída
  del agregado SQL real.
- La cola de repaso sirve el peldaño regresado sin spoilear.

### Tests existentes actualizados

- `test_graduated_cues_v337.py`: `test_next_recall_rung_ascends_only_with_evidence`
  → `..._only_with_consolidated_evidence`, y la evidencia de la cola pasa a
  2/2 días.
- `test_learning_evidence_v336.py`: el contrato de `empty_summary` incluye los
  dos campos nuevos.

## Criterios de aceptación

- Un peldaño solo habilita el siguiente con ≥2 éxitos en ≥2 días naturales
  distintos.
- Fallos repetidos (≥2, sin éxito) en el peldaño ideal bajan la recomendación a
  más apoyo, nunca por debajo de `translation`.
- `resolve_recall_cue` sigue degradando solo hacia más apoyo.
- Evidencia legacy sin peldaño no altera la progresión (no es evidencia
  negativa).
- Scoring, FSRS y contrato HTTP sin cambios; solo campos aditivos en
  `LexicalEvidence`.
- Paridad pura↔SQL y suite completa en verde (`ruff`, pytest, vitest,
  `tsc --noEmit`, build) + `check_release_consistency` **3.37.1** exit 0.

## Fuera de alcance (diferido, documentado)

- **P1-03 automaticidad por skill/modalidad** → V3.38. Requiere segmentar
  modalidad (hoy `skill=""` en todos los eventos léxicos) y agregar por skill; es
  un cambio de modelo, no de política.
- **P2-01 `cloze_coverage`** (métrica de corpus), **P2-03 `example_for_many`**
  (coste de la Review Queue) y **P2-04 refactor de `wordDrill.tsx`** → V3.39.
- Cualquier migración de BD, cambio de scoring/FSRS, o cambio de contrato
  incompatible.
