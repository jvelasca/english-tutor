# v3.64.1 — Consistencia snapshot/fingerprint del re-sellado

> Release **SIN migración de BD**, **SIN bump de `GENERATOR_VERSION`**, **SIN
> tocar el banco** y **SIN cambios de UI** que corrige los dos **P1** de la
> auditoría de V3.64, sin funcionalidad pedagógica nueva:
>
> - **P1-01** — carrera durante el recálculo/sellado del Student Skill State.
> - **P1-02** — TOCTOU de la caché, formalizado como semántica de snapshot.

## Contexto

El contrato de frescura de V3.63 es: `skill_state_source` guarda
`evidence_fingerprint(user_id)` (la huella `COUNT(*) + MAX(id)` de las cuatro
fuentes append-only) y `skill_state_is_fresh()` responde `True` cuando esa huella
coincide con la evidencia actual.

El invariante de sellado correcto es: **el sello guardado debe ser ≤ (en
evidencia) al estado, NUNCA mayor.** Si el sello es mayor que el estado,
`skill_state_is_fresh()` responde `True` y se sirve estado viejo como fresco.

En V3.64 el sello se tomaba **DESPUÉS** de leer/calcular el estado, en dos sitios:

```
T0  leer evidence / academy / listening / pronunciation
T1       ← NUEVA EVIDENCIA INSERTADA AQUÍ
T2  construir state   (sin la evidencia de T1)
T3  calcular sello    (sí incluye la evidencia de T1)
```

Se sellaba `(estado_viejo, sello_nuevo)`. El comentario del código lo describía
al revés («sello más nuevo que el estado → caché no fresca»), cuando ese es
justamente el caso peligroso.

## Cambios

### A · Sellado estable (`domain/decision.py`)

`_recompute` toma la huella **antes** y **después** de leer las fuentes y
calcular el estado, y solo sella cuando ambas coinciden (reintento acotado
`_SEAL_MAX_ATTEMPTS = 3`):

```
seal_before → leer fuentes → calcular estado → seal_after
if before == after: sellar(state, seal_after)
```

Si tras agotar los reintentos siguen sin coincidir, devuelve la huella
**anterior** (más vieja que el estado): la caché se reportará NO fresca y se
recomputará. Nunca un estado viejo sellado con huella nueva.

### B · Sello del perfil (`domain/profile.py`)

`get_profile_summary` lee el sello **antes** de `_compute_profile`, garantizando
que la huella persistida sea ≤ a todo lo que el perfil lee y agrega. Se corrige
el comentario que razonaba la carrera al revés.

### C · Snapshot de decisión (`domain/decision.py`)

`project_state` y `decision_projection` exponen `snapshot_fingerprint`: la huella
de las cuatro fuentes observada **al inicio** de la decisión. Formaliza el P1-02:
la decisión se toma sobre el snapshot de evidencia vigente en ese instante,
identificado y trazable. Es un token de trazabilidad, **no** el sello de caché
(que sigue gestionando `skill_state_is_fresh`). El camino del perfil
(`source="profile"`) lo deja vacío porque no es una decisión.

## Tests

Nuevos en `test_decision_projection_v364.py`:

- `test_recompute_reseals_only_a_stable_snapshot` — la huella que cambia durante
  la lectura provoca reintento y el sello devuelto es el estable.
- `test_decision_payload_declares_the_observed_snapshot_fingerprint` — la decisión
  declara la huella observada al inicio; el perfil la deja vacía.

Los 27 tests existentes siguen verdes.

## Fuera de alcance

Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica), Decision
Provenance completo y los P2 de calibración pedagógica (pesos de `skill_values`,
`capacity_by_skill` lexical, `review_due` en tiempo real) quedan para V3.65+.
