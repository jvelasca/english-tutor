# T — Auditoría total de V3.60.0 (verificación funcional del Context Engine 4.0)

> **Posición auditada:** tag anotado **`v3.60.0`** → commit `2c79040`. El delta
> auditado es `e721fce..2c79040` (**18 ficheros, +2854 / −78**).
> **Autor:** auditoría independiente con ejecución del backend de la etiqueta.
> **Fecha:** 2026-09-14.
> **Relación con `S-AUDITORIA-TOTAL-V360.md`:** la auditoría `S` da V3.60 por
> aprobada (9,6/10) y valida el anti-spoiler sobre el `template`; esta auditoría
> verifica la **superficie realmente servida** y encuentra **2 defectos
> funcionales** que `S` no cubría.

## Alcance

- **Se audita:** la consigna servida por `GET /api/vocabulary/drill/transfer-context`
  y lo que persiste `POST /api/vocabulary/drill/transfer-attempt`, sobre el
  nuevo espacio paramétrico de instancias.
- **No se audita:** la elección de familia (novedad/distancia/CEFR), el scoring
  léxico, el Sense Engine, FSRS ni el frontend.

## Método

```powershell
# 1. suite completa de la etiqueta
python -m ruff check backend launcher
python -m pytest backend/tests -q

# 2. reproducción del espacio de instancias de `shopping` y de la consigna servida
python -c "from services import transfer as t; [print(i, s['prompt']) for i, s in enumerate(t.context_instance_details('shopping'))]"
```

## Evidencia

| Comprobación | Resultado | Veredicto |
|---|---|---|
| `ruff` backend + launcher | limpio | OK |
| `pytest backend/tests -q` | **2333 passed, 2 skipped** | OK |
| Superficies de `shopping` | 19 | OK |
| Consigna del intento 7 de `shopping` | contiene `supermarket` | **DEFECTO** |
| Identidad de la instancia respondida en el POST | no viaja | **DEFECTO** |

### Reproducción del defecto 1 (fuga del target)

`backend/services/transfer.py:1074` declara, en el `instance_space` de la familia
`shopping`, el valor de slot:

```python
{"value": "a supermarket", "scenario": "doing the shopping"},
```

La superficie resultante ocupa el índice 7 y `context_for` la sirve tal cual
(`backend/services/transfer.py:2978`, `_compose_prompt(detail["prompt"], ...)`):

```
7 a_supermarket_cannot_find_what_you_need | You are in a supermarket and cannot find what you need. Ask an assistant for help.
```

Si la unidad a recuperar es `supermarket`, el alumno **lee la respuesta** en la
consigna: la tarea deja de ser recuperación espontánea y la evidencia de
transferencia queda contaminada (se acredita un uso que la consigna indujo).

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| T-01 | **alta** | Las instancias generadas pueden revelar la palabra objetivo. La familia `shopping` genera el escenario «a supermarket» y `context_for` lo sirve directamente. Reproducido en el intento 7. Invalida la recuperación espontánea y contamina la evidencia de transferencia. | `backend/services/transfer.py:1074`, `:2978` | Filtrar/rechazar cualquier superficie no guiada que contenga el target normalizado; aplicarlo también a la dificultad servida | **abierto → V3.61** |
| T-02 | media | La evidencia puede guardar la dificultad de una instancia **distinta** a la que contestó el alumno: `TransferAttemptIn` no identifica la superficie emitida y el POST recalcula la rotación con el contador actual. Con dos respuestas simultáneas o retrasadas se persiste el vector de la **siguiente** rotación. | `backend/schemas/vocabulary.py:826`, `backend/domain/vocabulary.py:850`, `backend/services/transfer.py:2520` | Devolver una identidad inmutable de instancia en el GET que el POST valide y use para persistir exactamente su vector servido | **abierto → V3.61** |

### Por qué importa T-01 (impacto en la evidencia del alumno)

El invariante de V3.43/P1-01 es que la consigna da **ESCENARIO**, nunca la
unidad objetivo. V3.60 lo mantiene en el `template` y lo verifica en los tests
(`assert "{" not in prompt`, `test_context_engine_v360.py:286`), pero **no en los
valores de slot**, que son texto declarado nuevo de esta release. El resultado es
que el invariante se sostiene «por suerte del banco» y no por construcción.

### Por qué importa T-02 (impacto en la evidencia del alumno)

La propia release declara como cierre que `served_difficulty` representa la tarea
REAL. Si el POST recalcula la superficie desde el contador, la fila del ledger
puede declarar la carga de la superficie **siguiente**, no la respondida: la
señal del Difficulty Engine 2.0 (capacidad observada por dimensión) queda
desplazada un intento.

## Fortalezas verificadas

- **Determinismo:** el diseño familia → especificación → instancia es
  determinista, sin `hash()`/`random`/`time`/LLM en el camino de la decisión.
- **Contrato aditivo:** compatibilidad de payload mantenida; las 28 claves de
  V3.59 intactas.
- **Deltas acotados:** `normalize_delta`/`apply_delta` limitan el ajuste a ±2 y
  el envelope 1..5.
- **No-fragmentación:** las instancias no alteran la identidad pedagógica de su
  familia (`context_id = FAMILIA`).
- **Suite completa de la etiqueta en verde:** 2333 tests, 2 omitidos, `ruff`
  limpio.

## Observaciones que NO son hallazgos

- **No hay GitHub Release publicada** asociada al tag `v3.60.0`. El tag anotado
  existe; la ausencia de Release es una decisión de publicación, no un defecto de
  producto (P3 documental si el proyecto quiere Releases por versión).
- **CI 6/6:** la documentación declara el run `34814504063`; la consulta
  directa devuelve `statuses: []` / `workflow_runs: []`. Se registra como
  **documentado, no verificado de forma independiente** (coincide con
  `S-AUDITORIA-TOTAL-V360.md`, P3-03). No es un fallo de producto.
- **`CONTEXT_INSTANCE_SPACE_MAX = 96` es inerte hoy** (máximo real 19): no es un
  defecto actual, pero el recorte por prefijo sesgará el espacio al crecer
  (P2-01 de `S`).

## Veredicto

**No apta para aprobarse sin corrección (2 defectos funcionales) — el resto, en
verde.** La etiqueta existe, la arquitectura es correcta y toda la suite pasa,
pero el invariante anti-spoiler de V3.43 **no se sostiene por construcción** en
las superficies generadas y la dificultad persistida puede ser la de otra
superficie. Ambos se corrigen en **V3.61**, sin `V3.60.1` (coincide con `S`).

## Recomendación para el siguiente incremento

**V3.61 — Instance-aware Evidence + Anti-spoiler Guard**, en este orden:

1. Guard anti-spoiler sobre la **superficie servida** (no solo sobre la
   plantilla) y sobre `served_difficulty`.
2. Identidad inmutable de instancia en el GET que el POST valide y use para
   persistir **su** vector servido.
3. Evidencia instance-aware: `context_instance` aditivo en el ledger,
   manteniendo `context_id = FAMILIA`.

## Regenerar / Verificar

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest tests/ -q          # 2333 passed, 2 skipped
# fuga del target:
.\.venv\Scripts\python.exe -c "from services import transfer as t; d=t.context_instance_details('shopping'); print(d[7]['prompt'])"
# identidad de instancia: el POST no recibe ninguna referencia a la superficie servida
Select-String -Path schemas\vocabulary.py -Pattern 'class TransferAttemptIn' -Context 0,12
```

## Tests que respaldan (y el hueco que dejan)

- `backend/tests/test_context_engine_v360.py:286` verifica que **la plantilla
  renderizada no deja llaves**, pero **no** que el texto no contenga la unidad
  objetivo.
- `backend/tests/test_context_engine_v360.py:697` cubre el end-to-end HTTP de una
  superficie generada con el vector efectivo persistido, **sin** comprobar que la
  superficie registrada sea la misma que la servida cuando el contador cambia.
