# Release notes — English Tutor v3.93.0

**Fecha:** 2026-09-30 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.92.0 → 3.93.0`

**Con backend y SIN frontend** (la conducta visible es **idéntica** a V3.92), **CON
migración de BD aditiva e idempotente** (cuatro columnas aditivas —`evidence_key`,
`sense_key`, `sense_match`, `sense_reason`— en `listening_difficulty_evidence` + índice
único **parcial** sobre `evidence_key`), **SIN endpoints nuevos** y **SIN cambio de
contrato incompatible**: `difficulty_evidence: {words, count}` conserva su forma.
`GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue
`1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json`
**sigue sin existir**.

**En una frase.** La evidencia de Listening empieza a distinguir **la palabra** de **la
acepción** —el Sense Resolver se cablea para **registrar** su veredicto— pero **todavía
no decide** qué evidencia se genera (dark launch), y de paso el ledger deja de perder
señal: la evidencia pasa a ser **idempotente por intento** y el read-compute-write deja
de pisar una **subida concurrente**.

---

## 1. Lo que se verificó antes de tocar nada

| Comprobación | Estado en `main` antes de V3.93 |
|---|---|
| Emparejamiento del puente | **Lemma-only**: `banks`/`banking` encuentran `bank`, pero una frase de «orilla» genera evidencia sobre la acepción «financiera» |
| Sense Resolver | Diseñado y **fijado con tests** (`SENSE-CONTEXT-01`), pero **no lo importaba ningún camino de producción** |
| Idempotencia del ledger | **Inexistente**: el mismo `attempt_number` reintentado volvía a sumar `+0.6` |
| Concurrencia | `upsert_fsrs_card` era un upsert de **REEMPLAZO** ciego: dos lecturas del mismo estado perdían una subida (lost update) |

De ahí el recorte, **deliberadamente conservador**: no se aplica la política sense-aware
(cambiaría cuánta evidencia se genera y es irreversible en datos reales) sino que (1) se
**mide** su impacto con el veredicto guardado, y (2) se cierran los dos defectos de
robustez que la auditoría dejó medidos.

## 2. El resolver se cablea, pero NO decide (dark launch)

`domain/listening.py::_apply_difficulty_evidence` consulta, por cada palabra que ya
recibe evidencia, el Sense Resolver:

```python
verdict = sense_context.classify_sense_evidence(
    word, text, senses.get(word), senses=()
)
```

y **guarda** el resultado en el ledger (`sense_key`, `sense_match`, `sense_reason`).
Lo que **no** hace es llamar a `allows_difficulty_evidence`: la política **no** filtra
qué palabras reciben evidencia, que sigue siendo **exactamente** lo de V3.92. La frontera
está fijada por un test que falla si alguien importa el resolver en otro sitio o usa la
política para decidir:

```
tests/test_sense_context_v392.py::test_sense_context_is_dark_launched_but_does_not_gate_evidence
```

`services/listening_bridge.py::sense_index` es el helper **puro** que reúne
`{palabra: acepción declarada}` del léxico. Una acepción ausente o vacía **no entra** en
el índice: «no consta» no se inventa, y el resolver responde `ambiguous`
(`declared:none`).

> **Sin alternativas todavía.** La ruta del puente no tiene a mano las alternativas de la
> ficha del diccionario, así que se llama con `senses=()`. Consecuencia honesta: `mismatch`
> **todavía no puede dispararse**; lo que se mide es `matched` vs `ambiguous`.

## 3. Idempotencia por intento (H8)

Cada fila del ledger lleva `evidence_key` = `usuario:frase:palabra:intento`, con un
**índice único parcial** (solo las filas con clave participan; las de V3.92 quedan en `''`
y la dedup empieza a aplicar sin migrar ni borrar nada). La escritura **reclama la clave
ANTES de tocar la carta** (`INSERT ... ON CONFLICT DO NOTHING`):

- repetir el **mismo** `attempt_number` —doble toque, reintento de red— **no vuelve a sumar**;
- dos intentos **distintos** siguen siendo **dos evidencias**: fallar la frase en el intento
  1 y volver a fallarla en el intento 2 son dos sucesos, y contarlos es la lectura honesta.

## 4. El lost update, cerrado (H7)

`academy_repo.upsert_fsrs_card` era un upsert de **REEMPLAZO**: dos evidencias que leían la
MISMA base calculaban la misma subida (`5.6`) y la segunda pisaba a la primera. Nuevo
`academy_repo.upsert_fsrs_card_cas(..., expected_difficulty=...)`:

```sql
ON CONFLICT(user_id, target_type, target_id) DO UPDATE SET ... 
WHERE fsrs_cards.difficulty = ?   -- valor leído
```

Escribe **solo** si la carta sigue en el valor leído; `_persist_card` relee y reintenta
(hasta 3 veces) para cobrar la subida que se había perdido. Dos evidencias simultáneas
suman las **dos**.

## 5. El instrumento, para decidir ENFORCE con datos

`scripts/sense_shadow_report.py` (solo lectura, `mode=ro`) agrega el ledger por veredicto y
**proyecta** la fase ENFORCE: cuánta evidencia se **conservaría** (`matched`) y cuánta se
**suprimiría**. El número que hay que mirar antes de aplicar la política es `declared:none`
(palabras sin acepción declarada): tratarlas como `ambiguous` **apagaría la mayor parte del
puente**, y eso hay que decidirlo con datos, no por defecto.

## 6. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff` (backend) | limpio |
| `pytest` backend | **3450/3450** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.93.0`) |
| Migración aditiva | verificada desde un árbol V3.92 (columnas + índice parcial, idempotente) |

## 7. Honestidad y límites

1. **Nada cambia para el alumno**: la evidencia generada es idéntica y el veredicto es, hoy,
   solo una columna medible. Es una release de **instrumentación**, no de política.
2. **`mismatch` no puede dispararse todavía** (sin alternativas en esa ruta): se mide
   `matched` vs `ambiguous`.
3. **`sense_key` no se persiste en `sense_json`**: se deriva en tiempo de evidencia.
   Persistirlo (y con ello estabilizar la identidad frente a cambios de la fila) es V3.94+.
4. El ledger **sigue creciendo con el uso** y no se poda.
5. Los **ocho gates humanos siguen `pending`**.

## 8. Qué queda para V3.94+ (ENFORCE)

- Decidir qué se hace con `declared:none` **antes** de aplicar la política.
- Cablear las **alternativas** del diccionario para que `mismatch` sea posible
  (`new_sense_exposure`).
- `MAX_MATCHES` por **relevancia** en vez de por orden de aparición.
- Persistir `sense_key` en el alta (`sense_json`).
