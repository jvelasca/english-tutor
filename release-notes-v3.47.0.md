# v3.47.0 — Transfer Evidence 2.0 + CEFR/`difficulty_vector` del contexto

**Release doble y ADITIVA, SIN migración de BD, que cierra los dos P1 abiertos
de la auditoría de V3.46.0 sobre la transferencia. (A) *Transfer Evidence 2.0*:
la escalera `transfer_state` deja de acreditar transferencia con un único éxito
no andamiado — ahora `transfer_demonstrated` exige ≥2 éxitos limpios en
condiciones NO andamiadas, y `transfer_stable` exige ≥3 contextos, ≥3 días y ≥2
objetivos comunicativos distintos. (B) *CEFR/`difficulty_vector` del contexto*:
cada contexto del banco declara su nivel del Marco y su carga
(`lexical`/`syntax`/`discourse`/`interaction`), y `context_for` los usa para no
servir un contexto por encima del alcance del alumno si hay uno alcanzable. No se
toca el scoring (`score_transfer_attempt`) ni FSRS.**

Versión de app `3.46.0 → 3.47.0`. Backend (`services/evidence.py`,
`services/transfer.py`, `domain/vocabulary.py`, `schemas/vocabulary.py`) +
frontend (`types/api.ts`) + tests y docs.

## Contexto

La V3.46.0 corrigió la ambigüedad de fondo (usar la palabra porque la tarea la
pide no es transferir), pero dejó la escalera todavía generosa: **un solo** éxito
limpio no andamiado bastaba para declarar `transfer_demonstrated` y
`transfer_stable` se alcanzaba con dos días. Además, el motor sabía QUÉ contexto
tocaba (`work`, `future`…) pero no CUÁNTO exigía cada uno: no es lo mismo «Tell
your friend about your weekend» que «Explain to a colleague how you would handle
a problem and justify your decision». La auditoría de V3.46.0 marcó ambos como P1
(`Transfer Evidence 2.0` y CEFR/`difficulty_vector` del contexto).

Fuera de alcance (diferido y documentado): TTS/offline P1s (V3.47.1/V3.48), Sense
Engine 2.0 (V3.48), Context Bank 2.0/expansión del banco (V3.48/V3.49),
`expected_learning_value`/Adaptive Planner 2.0, `transfer_state` como objeto
enriquecido y el aislamiento por usuario del Traductor.

## Qué cambia

### Parte A — Transfer Evidence 2.0 (P1-02)

- **Escalera endurecida (`services/evidence.py`).**
  `TRANSFER_DEMONSTRATED_MIN_UNSCAFFOLDED = 2`: `transfer_demonstrated` exige ahora
  ≥2 éxitos limpios en condiciones NO andamiadas
  (`open_context`/`free_choice`/`naturally_emergent`), además de 2 contextos
  limpios con diversidad real. `TRANSFER_STABLE_MIN_DAYS` pasa de 2 a 3 y nace
  `TRANSFER_STABLE_MIN_GOALS = 2` (objetivos comunicativos distintos entre los
  contextos con éxito limpio). `TRANSFER_STABLE_MIN_CONTEXTS = 3` se mantiene.
- **Señales finas (`context_signals`).** Se exponen
  `unscaffolded_clean_success_contexts` (lista ordenada),
  `unscaffolded_clean_success_days` (días distintos), `clean_success_goals`
  (objetivos comunicativos distintos, derivados de la dimensión
  `communicative_goal` del banco), y las marcas ISO `last_clean_success_at` /
  `last_unscaffolded_clean_success_at` para explicabilidad. La decisión de
  `transfer_state` no usa reloj: solo la evidencia registrada. `empty_summary`
  expone los campos nuevos con defaults neutros.
- **Fallback legacy intacto.** `_unscaffolded_transfer_ok` devuelve `True` cuando
  no hay datos de condición (resúmenes/ledger previos a V3.46): sin poder afirmar
  que falte el requisito, se conserva la regla anterior. Sin datos de diversidad
  se conserva la regla de V3.43. Paridad pura↔SQL por construcción:
  `repositories/evidence.py` reutiliza `context_signals` y su SELECT de detalle ya
  trae `transfer_condition` y `occurred_at`.
- **Impacto en el planner.** `has_contextual_transfer` y `transfer_gap` leen el
  `transfer_state` derivado, así que con la escalera más dura el planner seguirá
  proponiendo `transfer` hasta que existan 2 éxitos no andamiados (comportamiento
  deseado). No requiere cambios propios.

### Parte B — CEFR/`difficulty_vector` del contexto

- **Banco etiquetado (`services/transfer.py`).** Cada uno de los 6 contextos
  declara `cefr` (valor de `services.cefr.CEFR_LEVELS`) y `difficulty_vector`
  (`lexical`/`syntax`/`discourse`/`interaction`, enteros 1..5), la misma
  convención que `services/listening.py` y `services/speaking.py`.
- **Helper puro `difficulty_from_vector`.** Media redondeada del vector con clamp
  a 1..6, gemelo del de listening/speaking. `cefr_index` da el orden ordinal de un
  nivel (`-1` si no se reconoce).
- **Selección con nivel (`context_for(..., level=...)`).** Nuevo parámetro
  `level` retrocompatible: sin él (o sin nivel reconocible) el comportamiento es
  idéntico al de V3.46. Con nivel, se prefieren los contextos de nivel igual o
  inferior; si ninguno es alcanzable, se cae a los del nivel más cercano por
  arriba (nunca se deja al alumno sin tarea). La novedad y el desempate estable
  existentes se conservan.
- **Contrato aditivo (`context_for`, `TransferContextOut`, `types/api.ts`).**
  `context_for` devuelve además `cefr`, `difficulty_vector` y `difficulty`; el
  endpoint los expone y el tipo `DrillTransferContext` del frontend los declara.
  **Sin cambio de UI** en esta release.
- **Dominio (`domain/vocabulary.py`).** `get_transfer_context` y
  `submit_transfer_attempt` pasan `level=row.get("cefr")` al derivar el contexto,
  de modo que el servidor y el registro concuerdan.

## Tests

- Backend pytest **2063 passed** (+16): nuevos `test_transfer_evidence_v347.py`
  (8) y `test_transfer_cefr_v347.py` (8). El primero fija la regresión — 2
  contextos limpios con diversidad y **1** éxito no andamiado → `contextualized`
  (antes `transfer_demonstrated`), con **2** → `transfer_demonstrated`; `stable`
  exige 3 contextos + 3 días + 2 objetivos; señales nuevas; fallback legacy; y
  paridad pura↔SQL de todos los campos nuevos. El segundo fija el etiquetado del
  banco, `difficulty_from_vector`, la selección por `level` (incluido el fallback
  al nivel más cercano y el determinismo), y el contrato HTTP aditivo.
- Se ajustan a los nuevos umbrales/campos `test_transfer_v340.py`,
  `test_transfer_v343.py`, `test_transfer_condition_v346.py` y el contrato del
  resumen vacío en `test_learning_evidence_v336.py`.
- Frontend vitest **72 ficheros/623 tests** (sin cambios: la release no toca UI).
- Verificación: `pytest` 0 fallos, `ruff check backend/` limpio, `npm run test`,
  `npx tsc --noEmit`, `npm run build` y `check_release_consistency` **3.47.0**
  exit 0.

## Fuera de alcance (V3.47.1/V3.48)

- TTS/offline: el P1 de la auto-descarga implícita de voces (timeout, UI y
  degradación) se aborda como V3.47.1/V3.48.
- Sense Engine 2.0 y Context Bank 2.0 (expansión del banco de contextos).
- `transfer_state` como objeto enriquecido (`confidence`/`recency`) y
  `expected_learning_value` / Adaptive Planner 2.0.
- Aislamiento por usuario del historial del Traductor y su máquina de estados.

## Decisiones de diseño

- **Endurecer sin romper el pasado.** Sin datos de condición la regla anterior se
  conserva: los resúmenes y el ledger previos a V3.46 no degradan su estado.
- **La evidencia fina se expone, la decisión no usa reloj.** Las marcas ISO de
  último éxito son para explicar y depurar; `transfer_state` es puro y
  determinista (mismos datos → mismo estado), lo que mantiene los tests estables.
- **El nivel es un TECHO, no un destino.** El alumno A1 no recibe el contexto más
  difícil del banco si hay uno a su alcance; si no lo hay, se le da el más cercano
  antes que dejarlo sin práctica.
- **Aditivo de punta a punta.** Sin migración de BD (las columnas de V3.46 ya
  existen), sin cambio de scoring ni de FSRS, y sin UI nueva (evita churn de
  Playwright).
- **Sin LLM en la evidencia (premisa 21).** Ni la escalera ni el etiquetado del
  banco dependen del modelo: son tablas y funciones puras.
