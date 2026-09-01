# V2.6 (5/5) — C5: Etiquetar actividades con la fase del Unit Learning Loop

## Rol
Backend (contenido curricular). Marcas, en los JSON de nivel, **qué actividad cumple cada fase** del
Unit Learning Loop, para cerrar el hueco medido en V2.6-C1. **Sin UI y sin lógica nueva**: la lógica
(marcador `phase` + validación + medición) ya está implementada; tú solo **etiquetas contenido** y
ajustas los invariantes de snapshot.

## Objetivo
La auditoría V2.6 midió el Unit Learning Loop por unidad y encontró el hueco exacto:

| Fase | Cobertura | Causa |
|---|---|---|
| introduce | 100% | `concepts` + `vocabulary` (derivado, ya existe) |
| practice | 100% | `activities` + `checks` (derivado, ya existe) |
| listen | 45,2% | solo en unidades con listening cableado |
| speak | 90,3% | casi todas las unidades declaran speaking |
| interact | 83,9% | subskills `interaction`/`turn_taking` |
| **retrieve** | **0%** | **no hay marcador de recuperación** |
| **transfer** | **0%** | **no hay marcador de transferencia** |
| assess | 19,4% | solo en el módulo "Final" |
| review | 19,4% | solo en el módulo "Final" |

Tu tarea: **etiquetar actividades existentes (o añadir las mínimas necesarias)** con `phase` para que
las fases de cierre del bucle dejen de estar vacías **por unidad**, no solo en el módulo Final.

## Contexto

### El marcador (ya implementado en V2.6-C1)
- `services/curriculum.py` define `LEARNING_PHASES` (9 fases canónicas) y añade a `Activity` el campo
  `phase: str = ""` (default vacío = `practice`, retrocompatible).
- `validate_level()` rechaza cualquier `phase` no canónico.
- `services/curriculum_coverage.py::unit_learning_loop()` lee las fases así:
  - `retrieve` = nº de actividades con `phase == "retrieve"`.
  - `transfer` = nº de actividades con `phase == "transfer"`.
  - `review` = actividades con `phase == "review"` + módulo Final.
  - `assess` = actividades con `phase == "assess"` + módulo Final.
  - Las demás fases siguen derivándose de la estructura (sin etiquetar).

### Fases canónicas (LEARNING_PHASES)
`introduce`, `practice`, `listen`, `speak`, `interact`, `retrieve`, `transfer`, `assess`, `review`.

### Formato de una actividad (nivel JSON)
```json
{
  "id": "a1-m01-u01-l01-o01-a01",
  "type": "dialogue",
  "instruction": "Introduce yourself to the tutor...",
  "target": "I am ... / My name is ...",
  "phase": "transfer"
}
```
El campo `phase` es opcional; si se omite, la actividad cuenta como `practice`.

## Tarea detallada

1. **Piloto A1 (implementación de referencia).** Trabaja solo `backend/curriculum/a1.json` primero.
   Para **cada unidad normal** (las 9 que no son `a1-m10` Final), asegura que exista al menos una
   actividad por cada fase de cierre:
   - **retrieve** — recuperación espaciada del vocabulario/estructuras de la unidad: pide recordar
     desde memoria (sin ver la lista), p. ej. `"Without looking, write three past forms you learned."`
     o `"Recall the prepositions of place from this unit."`. `type` sugerido: `recall` o `dialogue`.
   - **transfer** — aplicar lo aprendido a un contexto nuevo (no ensayado): p. ej. en la unidad de
     direcciones, pedir indicaciones a un sitio **distinto** del ejemplo. `type` sugerido: `dialogue`
     o `writing`.
   - **review** — micro-repaso de la unidad: un ítem que recupere el can-do de la unidad en 1 frase.
   - **assess** — evaluación formativa de la unidad: idealmente una actividad de cierre que pida
     demostrar el can-do (no sustituye a los `checks` deterministas; los complementa como
     auto-evaluación abierta).

   Reglas:
   - No dupliques contenido: reutiliza `concepts`/`vocabulary` ya declarados; las instrucciones deben
     ser nuevas (recuperar/transferir, no re-explicar).
   - Mantén `type` en los valores que ya usa el proyecto (`dialogue`, `fill_gap`, `listen`, `writing`,
     `essay`, `listening`, `recall`). Si introduces `recall`, es aceptable (es una actividad abierta,
     no un `ObjectiveCheck`).
   - Los `checks` (opción múltiple) **no** llevan `phase`; la fase `assess` por unidad se marca en la
     actividad abierta, no en el check.

2. **Escalar a A2/B1/B2/C1/C2.** Repite el patrón en el resto de niveles (`a2.json`…`c2.json`),
   respetando el nivel CEFR de cada instrucción (no pidas discurso abstracto en A1).

3. **Invariantes de snapshot.** Actualiza los tests que codifican el "hueco" ahora que se cierra:
   - `backend/tests/test_curriculum_quality.py::test_loop_retrieve_and_transfer_are_still_ungapped`
     — se invierte: retrieve/transfer pasan a `covered_units > 0` en A1.
   - `test_loop_assess_and_review_only_in_final_module` — se actualiza: assess/review ya no están
     solo en Final (la unidad normal también los tiene).
   El resto de invariantes (estructurales) no debe tocarse.

4. **Verificación local.** Ejecuta y reporta el antes/después:
   ```powershell
   cd backend
   .venv\Scripts\python.exe -m scripts.curriculum_coverage   # UNIT LEARNING LOOP debe subir
   .venv\Scripts\python.exe -m pytest tests/ -q
   .venv\Scripts\python.exe -m ruff check .
   ```

## Criterios de aceptación
- `UNIT LEARNING LOOP` por unidad sube: `retrieve`/`transfer` dejan de ser 0/31 y `assess`/`review`
  pasan de 6/31 (solo Final) a estar presentes en las unidades normales. Objetivo orientativo: media
  por unidad de 50,6% → **≥ 77%** (las 9 fases cubiertas en las unidades normales).
- `python -m scripts.curriculum_coverage --strict` sigue saliendo 0.
- `validate_level(load_level(id)) == []` para los 6 niveles (ninguna `phase` no canónica).
- `pytest tests/ -q` verde + `ruff check .` limpio.

## Restricciones
- **Sin UI, sin lógica nueva**: solo etiquetas contenido y actualizas los invariantes de snapshot.
  No toques `services/`, `scripts/`, ni el frontend.
- No cambies el modelo `Objective`/`Activity` (ya tiene `phase`).
- No elimines contenido existente ni renumeres `id`; añade actividades con ids nuevos y únicos.
- Un único commit `feat: etiquetar fases del Unit Learning Loop (retrieve/transfer/assess/review)`.
  No push.

## Salida esperada
Nº de unidades con cada fase (antes/después), el nuevo `UNIT LEARNING LOOP` del CLI y el diff del
invariante de snapshot. Señala explícitamente qué niveles quedaron fuera del objetivo (si alguno) y por
qué.
