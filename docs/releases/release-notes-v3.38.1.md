# v3.38.1 — Cierre quirúrgico de los P1 del Planner + UI de diccionario y estado

**Release ADITIVA que NO añade funcionalidad: cierra los 4 P1 reales de la
auditoría de V3.38.0 sobre el Planner (globalidad de candidatos, señales por
modalidad, `skill_gap` parcial accionable y automaticidad robusta), endurece la
validación de `situation` (P2) y reubica dos elementos de UI — el diccionario como
destino propio y el estado de conexión en la cabecera, retirando la barra
inferior. Sin migración de BD, sin cambios de esquema y sin tocar scoring, FSRS ni
la semántica del intervalo de evidencia (V3.35.1 P1-01).**

Versión de app `3.38.0 → 3.38.1`. Backend (`domain/review.py`,
`services/planner.py`, `services/evidence.py`, `repositories/evidence.py`,
`services/situation.py` nuevo, `services/dictionary_content.py`,
`services/recall.py`, `schemas/vocabulary.py`) + frontend (ruta dedicada del
diccionario, indicador de conexión en la cabecera, tipos TS, i18n) + tests y docs.
Contrato HTTP **aditivo** (`LexicalEvidence` gana dos histogramas;
`planned_signals` gana `skills`); el bump de `generator_version` regenera la
caché previa una sola vez.

## Contexto

La auditoría de V3.38.0 (9,1/10) aprobó la arquitectura —segmentación por
modalidad, planner explicable, peldaño situacional— pero señaló cuatro P1 que
impedían que esa arquitectura rindiera lo que prometía. El diagnóstico tenía un
patrón común: **la evidencia o el ranking existían, pero se recortaban antes de
usarse**.

```text
    LO QUE SE MEDÍA                     LO QUE EL PLANNER VEÍA
    ─────────────────                   ──────────────────────
    TODAS las vencidas                  ❌ solo el top-N del scheduler
    latencia POR modalidad              ❌ media global mezclada
    written ✓ / spoken ✗                ❌ exigía que faltaran AMBAS
    automaticidad por volumen           ❌ 2 aciertos entre 100 intentos
    situación validada a mano           ❌ reglas duplicadas y laxas
```

- **P1-01** — `get_review_queue` pasaba el límite de PRESENTACIÓN directamente a
  `fsrs.due_queue`, así que el planner solo comparaba el subconjunto que el
  scheduler ya había recortado: la mejor tarea podía quedar fuera del top-20.
- **P1-02** — la evidencia se segmentaba por modalidad, pero el planner la
  recomprimía en una `weakness`/`support`/`latency` global; `is_slow_recall` leía
  la media global, que mezcla un recall lento con una producción oral rápida.
- **P1-03** — `evidence_reason` solo emitía `skill_gap` cuando faltaban **las dos**
  modalidades productivas, de modo que el caso que V3.38 quería detectar
  (`written ✓ / spoken ✗`) caía en mantenimiento.
- **P1-04** — la automaticidad bastaba con `independent_successes >= 2` y ≥2 días:
  dos aciertos sueltos entre cien intentos declaraban «automático».
- **P2-01** — la validación de `situation` vivía duplicada dentro de
  `dictionary_content` y solo comprobaba hueco único + no-spoiler.

## Qué cambia

### 1. P1-01 — Planner globalmente óptimo (`domain/review.py`)

- Se declara `REVIEW_QUEUE_CANDIDATE_LIMIT = 500` (cota de salvaguarda, no
  decisión pedagógica) **separado** de `REVIEW_QUEUE_DEFAULT_LIMIT`/`REVIEW_QUEUE_MAX_LIMIT`.
- `fsrs.due_queue(..., limit=REVIEW_QUEUE_CANDIDATE_LIMIT)` → se construyen
  `review_queue_item` para **TODOS** los candidatos, se ordena por `priority`
  (mismo desempate por `retrievability` y palabra) y **después** se aplica el
  recorte de presentación.
- Las cues (`next_recall_rung` + `resolve_recall_cue`) se resuelven en una
  **segunda pasada** solo para los ítems servidos: de paso deja de pagarse
  `example_for` por todas las vencidas (P2-13 de la auditoría).
- `due_count` sigue siendo `len(items)` para no cambiar el contrato HTTP.

### 2. P1-02 — Señales por modalidad (`services/evidence.py`, `repositories/evidence.py`, `services/planner.py`)

- `summarize_evidence`/`empty_summary` añaden `skill_attempts` (TODOS los eventos
  del skill, aciertos y fallos) y `skill_mean_response_time_ms` (latencia media
  por modalidad; clave ausente si no se midió), leídos de `skill` +
  `response_time_ms`.
- `repositories/evidence.py` los replica en SQL con un `GROUP BY LOWER(skill)`
  (conteo de intentos + `AVG(response_time_ms)`), con **paridad exacta pura↔SQL**
  fijada por test. Sin migración: ambas columnas ya existían.
- `planned_signals` gana el bloque `skills` (por modalidad: `attempts`,
  `successes`, `success_rate`, `weakness`, `support`, `latency`), que **NO entra
  todavía en `priority_score`** (pesos intactos; prioridad por skill = V3.39).
- `is_slow_recall` deja de leer la media GLOBAL: usa la latencia DE `recall`
  (`SLOW_RECALL_MS = 8000.0`) y **exige un éxito de recall**. Sin latencia de
  recall medida → `False` (honesto).
- Contrato aditivo: `LexicalEvidence` (schema Pydantic y tipo TS) amplía los dos
  histogramas con defaults `{}`.

### 3. P1-03 — `skill_gap` parcial accionable (`services/planner.py`)

- `evidence_reason` emite `skill_gap` cuando el ítem ya logra algo, hay evidencia
  de producción (`matrix.production`) y falta la modalidad **oral**
  (`SPEAKING_SKILL`), que la actividad `sentence` sí puede cerrar. El caso
  `written ✓ / spoken ✗` dirigirá a producción oral.
- El hueco simétrico (solo falta `written_production`) se sigue exponiendo en
  `signals.skill_gaps` pero **no** emite razón accionable: no hay todavía drill de
  escritura en la cola (deuda documentada para V3.39).
- `ACTIVITY_FOR_REASON["skill_gap"]` sigue siendo `sentence` y `explain_priority`
  nombra la modalidad concreta que falta.
- `recommend_review_activity` ya respetaba el orden `production_gap` →
  `evidence_reason`, así que el caso parcial pasa a `sentence` sin tocar V3.35.

### 4. P1-04 — Automaticidad robusta (`services/evidence.py`)

Criterio declarado y calibrable, aplicado por igual a `is_automatic` (global) y a
`automatic_skills` (por modalidad):

- `AUTOMATIC_MIN_INDEPENDENT` 2 → **3** (éxitos independientes en días naturales
  distintos).
- Nuevo `AUTOMATIC_MIN_SUCCESS_RATIO = 0.80` (sobre `success_rate` global o
  `skill_successes`/`skill_attempts` por modalidad).
- Nuevo `AUTOMATIC_MAX_WRONG_WORD_ERRORS = 1`: aproximación determinista de «sin
  fallo reciente grave» vía `error_types["wrong_word"]` (la errata
  `orthographic_error` no cuenta — no es confusión). La constante vive en
  `evidence.py` para no crear ciclo con `planner`.
- La **recencia** ponderada de los fallos queda como deuda de V3.39 (documentada
  en el módulo).

### 5. P2-01 — `situation` endurecida (`services/situation.py`, nuevo)

- Módulo PURO como **única fuente de verdad**, compartido por generación, lectura
  y disponibilidad. Reglas: exactamente **UN** hueco (normalizado a `_____`),
  **UNA sola frase** (como mucho un signo de cierre `.!?` y, si lo hay, al final),
  longitud ≤ `MAX_SITUATION_CHARS = 240` y **sin fuga de la diana**, incluida la
  morfológica REGULAR (plural/3.ª persona `-s/-es/-ies`, pasado `-ed/-ied/-d`,
  gerundio con e-drop/duplicación, adverbio `-ly`, posesivo `'s`, comparativos
  cortos). Las formas irregulares (`go`→`went`) quedan documentadas como
  limitación conocida.
- `services/dictionary_content.py`: `_situation_from` delega en el validador y
  `GENERATOR_VERSION` sube 1.2.0 → **1.2.1** (regeneración lazy, una sola vez).
- `services/recall.py`: el camino de lectura (`cue="situation"`) revalida con el
  mismo helper, de modo que una situación cacheada por reglas laxas no se sirve ni
  cuenta como peldaño disponible.

### 6. UI — Ruta dedicada del diccionario

- Nuevo destino AUXILIAR `dictionary` con raíz `/diccionario` (`DICTIONARY_PATH`,
  `routeMap` reversible, `routeMap.test` con 9 valores de `Route`).
- Cuarto destino en la navegación tras un **separador** (barra vertical en las
  píldoras de la cabecera, borde divisorio en la bottom-nav, `grid-cols-3 →
  grid-cols-4`), icono `BookOpen`.
- Nueva `DictionaryScreen` con las dos vistas existentes (Personal / Consultar),
  reutilizando los componentes sin duplicar lógica.
- **Corte de la navegación `md` → `xl` (corrección del propio release).** Con
  cuatro destinos con etiqueta, la fila de píldoras ya no cabía en la cabecera
  por debajo de 1280px sin invadir los botones de acción: se medía en tablet
  (768: 288px de píldoras en 129px de hueco) y en el borde `lg` (1024), y empeora
  en español (`Diccionario`/`Formación` son más largos que `Dictionary`/`Course`;
  +50px). Las píldoras de cabecera pasan a montarse desde `xl` (≥1280, donde
  caben en ambos idiomas) y la bottom-nav —ya con los 4 destinos— cubre hasta
  entonces, lo que además encaja con «ganar espacio útil». `overflow-x-auto` en
  el contenedor de píldoras queda como red de seguridad. Lo destapó el job de
  Playwright E2E del release (una píldora interceptaba el clic de *Help* en
  tablet); verificado en local con la suite completa en verde.

### 7. UI — Estado de conexión en la cabecera

- Se elimina la barra de estado inferior (`StatusBar.tsx` y las reglas CSS
  huérfanas `.status-bar*`/`.status-popover`; se conserva `.status-bar-muted`,
  que usan `SystemStatus` y `BackupPanel`).
- Nuevo `ConnectionIndicator` en la cabecera: punto verde/rojo con etiqueta
  Conectado/Desconectado (sondeo de `/api/health` cada ~15 s) que, al pulsarlo,
  abre un popover con el panel completo `<SystemStatus />` (que sigue además en
  Ajustes). Estado y etiqueta visibles en móvil (el punto siempre; la etiqueta
  desde `sm`).
- E2E `mobile.spec.ts` actualizado al nuevo trigger (`System status`).

### 8. Contrato (aditivo)

- `LexicalEvidence` amplía `skill_attempts` y `skill_mean_response_time_ms`
  (defaults `{}`).
- `planned_signals` amplía `skills`. Ningún campo existente cambia de forma ni de
  semántica; `ReviewQueueItem` y el resto del contrato HTTP no cambian.

### 9. Sin cambios

Scoring, FSRS, `PRIORITY_WEIGHTS`, la semántica del intervalo de evidencia, el
mecanismo de degradación de la cola (sigue sin spoiler) y el esquema de BD.

## Verificación

- Backend: `ruff check .` → *All checks passed!* y `pytest` → **1890 passed**
  (+10 sobre v3.38.0).
- Frontend: `tsc --noEmit` limpio, `vitest` → **67 ficheros/568 tests**
  (+2 ficheros/+8 tests) y `npm run build` OK.
- Playwright E2E (visual): suite completa en local **23 passed / 22 skipped /
  0 failed** (con un único worker; en paralelo el dev server compartido da
  flakiness). Incluye el caso que falló en el primer push (tablet: la ayuda se
  abre desde el header) tras el cambio de corte de la navegación.
- `python scripts/check_release_consistency.py` → **3.38.1** exit 0.

### Matriz de pruebas nueva (resumen)

| Frente | Qué fija el test |
|---|---|
| Planner global | 100 vencidas con la mejor tarjeta fuera del top-20 del scheduler → el planner la encuentra y la sirve 1.ª |
| Señales por modalidad | `planned_signals.skills`, latencia por skill, `slow_recall` con recall lento y producción oral rápida (y el inverso no), paridad pura↔SQL de `skill_attempts`/latencia |
| `skill_gap` parcial | `written` automático + `spoken` sin evidencia → `skill_gap` y actividad `sentence`; `skill_gap` simétrico expuesto pero NO accionable |
| Automaticidad | umbral 3 + ratio ≥0.80 + sin fallo grave; «2 éxitos / 20 fallos» NO declara automaticidad |
| `situation` | una sola frase, un solo hueco, fuga morfológica regular, revalidación de situación cacheada inválida |
| UI diccionario | round-trip de `/diccionario`, render de los 4 destinos con separador, estado activo en bottom-nav |
| UI estado | `ConnectionIndicator` conectado/desconectado y apertura del popover `SystemStatus` |

## CI

- Commit de release `217ebfe` con el run
  [34499476359](https://github.com/jvelasca/english-tutor/actions/runs/34499476359):
  **5/6 jobs en success**; falló **Playwright E2E (visual)** en tablet (768px)
  porque la 4.ª píldora desbordaba su contenedor `flex-1` e interceptaba el clic
  del botón *Help* del header.
- Corrección en el commit `856e11541897da41a20eccc06d21b430bc2bdee5` (corte de la
  navegación `md` → `xl`, ver arriba), con el run
  [34500794657](https://github.com/jvelasca/english-tutor/actions/runs/34500794657)
  en **success** (6/6 jobs: backend ruff+pytest, frontend tsc+vitest+build,
  release consistency, Beta V3.0 gate, content validation, Playwright E2E).
  Este es el commit verde y auditable de la release.

## Fuera de alcance (V3.39)

- **Prioridad completa por skill** (el planner decide skill + actividad óptima, no
  solo la razón) y **routing de escritura** para `written_production`.
- `sense`/CEFR/contexto en la caché y transferencia contextual real (V3.23).
- Optimización de `PRIORITY_WEIGHTS` y recencia ponderada de fallos.
- `example_for_many` de la Review Queue y refactor de `wordDrill.tsx`.
