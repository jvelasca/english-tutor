# V3.38 — La siguiente tarea óptima: `situación`, planner y automaticidad por skill

> Rol: documento de diseño e implementación del candidato **V3.38**. Cierra el
> incremento que V3.37 dejó abierto en tres frentes: el peldaño situacional que
> exige AUTORAR contenido, la generalización de `recommend_review_activity` a un
> planner (Optimal Next Task) y el P1-03 diferido de la auditoría de V3.37.0
> (automaticidad segmentada por skill/modalidad). Se publica como **v3.38.0**.
>
> Normas que este eslabón respeta:
>
> - **Premisa 21**: la UI nunca declara acierto. El cliente dice QUÉ peldaño le
>   sirvieron; el servidor re-deriva ese peldaño de forma pura y determinista y
>   puntúa. El GET nunca expone la forma esperada.
> - **D3 (V3.30)**: «consultar ≠ aprender». El diccionario de consulta sigue
>   siendo SOLO lectura; el contenido es idioma, no evidencia.
> - **D5/E3**: una producción del día no consolida; la automaticidad exige éxito
>   **independiente y espaciado** (días naturales distintos).
> - **Puros primero**: la escalera, el planner y la segmentación por skill son
>   funciones puras con paridad pura↔SQL fijada por test.
> - **Contrato aditivo**: nada de cambios incompatibles; el despliegue no exige
>   coordinar cliente y servidor.
>
> Borrador: 2026-09-10.

## Relevo rápido (leer antes de tocar nada)

- Versión estable de partida: **3.37.1** (`backend/config.py::VERSION`); la
  entrega es **3.38.0**.
- **Sí hay migración, pero ADITIVA e idempotente**: `dictionary_entries.situation`
  (`ALTER TABLE ... ADD COLUMN situation TEXT NOT NULL DEFAULT ''`). El esquema
  del ledger **no cambia**: `skill` ya existe desde V3.36.0.
- El bump `GENERATOR_VERSION` 1.1.0 → **1.2.0** invalida la caché previa: se
  regenera una sola vez al primer lookup (misma política de V3.30.1). No hay
  migración de datos.
- Fuente de verdad del estado: `CHANGELOG.md` + `docs/RELEVO.md` (nota superior).

## El hallazgo que motiva V3.38

V3.35–V3.37 dejaron tres huecos documentados:

```text
    EVIDENCIA por peldaño        ¿POR QUÉ esta tarea?         CONTENIDO
    ─────────────────────        ────────────────────         ─────────
    translation                  ❌ solo urgencia FSRS        ❌ falta el techo
    definition                   ❌ skill="" en el ledger       situacional
    cloze (techo V3.37)          ❌ automaticidad global      (exige autoría)
```

1. **P1-03.** El `skill` del ledger léxico era `""` en todos los eventos: la
   automaticidad era un único booleano, así que un ítem con aciertos de recall y
   de producción mezclados podía declararse «automático» sin serlo en ninguna
   modalidad concreta. Es un cambio de **modelo de evidencia**, no de política.
2. **Planner.** La cola de repaso ordenaba por `retrievability` y elegía
   actividad por hueco de competencia, sin usar la evidencia fina ya persistida
   (modalidad, latencia, tipo de error, apoyo): el sistema sabía «qué toca» pero
   no «por qué esa tarea y con qué apoyo».
3. **`situación`.** La escalera tenía techo en `cloze`, que reutiliza una frase
   REAL del banco de pronunciación. Para pedir más había que AUTORAR contenido:
   de ahí la extensión del contrato de la caché.

## Qué cambia

### 1. P1-03 — modalidad canónica y automaticidad segmentada

`services/evidence.py`, `repositories/evidence.py`, `domain/vocabulary.py`,
`schemas/vocabulary.py`, `frontend/src/types/api.ts`.

- Vocabulario canónico `LEXICAL_SKILLS` y mapeo canal→skill (`production_skill`).
  El recall declara `recall`; el drill/retrieval su modalidad; la producción su
  modalidad, no el canal crudo.
- Histogramas nuevos en el resumen (`skill_successes`, `skill_success_days`,
  `skill_independent_successes`, `skill_independent_days`) con paridad exacta
  pura↔SQL.
- `automatic_skills(summary)` — automaticidad POR modalidad con el mismo rigor
  de espaciado que `is_automatic`.
- **Sin migración**: la columna `skill` ya existía.

### 2. Planner — Optimal Next Task (`services/planner.py`, nuevo)

- `planned_signals` — `forgetting`, `gap`, `weakness`, `support`, `latency` + los
  derivados `automatic`/`automatic_skills`/`skill_gaps`/`error_prone`/
  `slow_recall`.
- `priority_score` — suma ponderada con `PRIORITY_WEIGHTS` declarados.
- `evidence_reason` — `error_prone`, `skill_gap`, `slow_recall` en orden
  declarado, integrados en `recommend_review_activity` sin sustituir a V3.35.
- `explain_priority` — el `why` en inglés.
- La cola se ordena por `priority` (desempate por `retrievability` y palabra) y
  expone `priority`/`signals`/`why`/`automatic_skills`, sin spoiler.

### 3. `situación` — contrato de contenido y techo de la escalera

`repositories/db.py`, `repositories/dictionary.py`,
`services/dictionary_content.py`, `services/recall.py`, `domain/vocabulary.py`.

- `GENERATOR_VERSION` 1.2.0 y `situation` en el prompt, validado de forma
  determinista (`_situation_from`): exactamente un hueco `_____`, sin spoiler,
  acotado. Si no cumple, se descarta sin invalidar definición/traducción.
- Columna `dictionary_entries.situation`, migración aditiva e idempotente.
- `RECALL_CUES` gana `situation` como TECHO con apoyo `guided`; el GET/POST del
  drill lo sirven y lo declaran (`drill:recall:situation`); la cola lo recomienda
  cuando hay contenido y degrada hacia más apoyo cuando no.

## Criterios de aceptación

1. `ruff check backend/` limpio y `pytest` en verde (1880).
2. `vitest` (65 ficheros/560) y `tsc --noEmit` limpios; `npm run build` OK.
3. `check_release_consistency` → **3.38.0** exit 0.
4. La cola de repaso nunca expone el cue ni la forma esperada.
5. Un ítem sin situación cacheada degrada a `cloze`/`definition`/`translation`
   (nunca asciende) y el POST responde 422 sin evento si el peldaño pedido no
   tiene contenido.
6. Paridad pura↔SQL de los histogramas por skill y del resumen completo.

## Qué NO entra en V3.38

- Deudas diferidas de V3.30, transferencia por contexto V3.23, `cloze_coverage`
  del corpus, `example_for_many` de la Review Queue y el refactor de
  `wordDrill.tsx` → V3.39.
- Cambios de scoring/FSRS, migraciones no aditivas o cambios de contrato
  incompatibles.
