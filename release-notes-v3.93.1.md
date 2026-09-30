# Release notes — English Tutor v3.93.1

**Fecha:** 2026-09-30 · **Tipo:** release de **ROBUSTEZ** (patch) · **Versión de app:**
`3.93.0 → 3.93.1`

**Con backend y frontend** (el cambio de frontend es una señal técnica, `attempt_id`, no
una conducta nueva), **CON migración de BD aditiva e idempotente** (columna `attempt_id`
en `listening_attempts` + índice único **parcial**; columna `version` en `fsrs_cards`;
columna `attempt_id` en `listening_difficulty_evidence`), **SIN endpoints nuevos** y **SIN
cambio de contrato incompatible**: `difficulty_evidence: {words, count}` conserva su
forma y `attempt_id` es un campo **aditivo** de `POST /api/listening/answer`.
`GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue
`1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json` **sigue
sin existir**.

**En una frase.** El evento pedagógico de Listening (`attempt` → `review_queue` →
`evidence` → `FSRS`) deja de tener ramas que se desincronizan: la evidencia y la carta se
escriben juntas o no se escriben, el intento y su cola son idempotentes por `attempt_id`,
la cola no pierde incrementos concurrentes y el CAS de la carta protege la fila completa.

---

## 1. Por qué este patch, y no V3.94

La reauditoría de V3.93 encontró la arquitectura SENSE-CONTEXT-01 **correcta** (dark
launch, resolver cableado sin gobernar) pero **tres fugas de integridad** en el flujo
completo del intento, más dos mejoras de robustez del resolver y del CAS. Ninguna obliga a
replantear el diseño: son endurecimientos de la persistencia **antes** de activar la
política semántica (`ENFORCE`), que sigue siendo V3.94.

## 2. P0 — evidencia ↔ FSRS en una sola transacción

Antes: `record_difficulty_evidence()` (su propia transacción) reclamaba la clave y
**después** `_persist_card()` escribía la carta (otra transacción). Si el CAS agotaba sus
3 reintentos, quedaba **fila de evidencia sin FSRS**, y la idempotencia por `evidence_key`
impedía volver a intentarlo: una señal perdida.

Ahora: `listening_repo.claim_evidence_and_write_card(...)` abre `BEGIN IMMEDIATE`, reclama
la clave (`INSERT ... ON CONFLICT DO NOTHING`) y aplica el CAS de la carta **en la misma
transacción**:

- `inserted == 0` → `duplicate` (rollback; el intento ya estaba registrado);
- CAS no escribe → `conflict` (**rollback**: no queda fila y la clave se libera);
- todo OK → `ok`.

`_apply_difficulty_evidence` reintenta en `conflict` releyendo la carta (hasta 3 veces).
**O ambas cosas, o ninguna.**

## 3. P0 — el intento completo es idempotente

Antes: `record_attempt()` insertaba siempre y `_sync_review_queue()` re-incrementaba
`fail_count`; solo el ledger deduplicaba. Un doble envío del mismo intento dejaba
`2` intentos y `2` fallos con `1` evidencia.

Ahora: `listening_repo.record_answer_event(...)` en una transacción `BEGIN IMMEDIATE`:

1. inserta el intento con `ON CONFLICT(user_id, attempt_id) DO NOTHING`;
2. solo si insertó de verdad, lee `fail_count`, calcula `schedule` y actualiza la cola
   (o la resuelve, si el intento fue un acierto);
3. devuelve `{inserted, fail_count, attempt}`.

La identidad es `attempt_id`, un **UUID que genera el cliente por intento** y **reutiliza
en el reintento HTTP** (se regenera al avanzar de intento o cargar otra pregunta). No se
usa `attempt_number` como clave porque se reinicia por carga de pregunta y colapsaría
reintentos legítimos posteriores de la misma frase.

## 4. P0 — la cola de repaso no pierde incrementos

`queue_fail_counts` → `+1` → `enqueue_failure` era un read-compute-write sin CAS (el lost
update que V3.93 cerró en FSRS seguía abierto en la cola). Al vivir dentro de la
transacción `BEGIN IMMEDIATE` de `record_answer_event`, queda serializado por el write
lock: dos fallos simultáneos suman `2`.

## 5. P1 — el CAS protege la fila completa de la carta

El CAS de V3.93 comparaba solo `difficulty`, así que un repaso FSRS legítimo que cambiara
`reps`/`stability` sin mover `difficulty` podía ser sobrescrito. Nueva columna
`fsrs_cards.version` (aditiva, `DEFAULT 0`):

```sql
ON CONFLICT(user_id, target_type, target_id) DO UPDATE SET ... ,
    version = fsrs_cards.version + 1
WHERE fsrs_cards.version = ?   -- versión leída
```

Todos los upserts (`upsert_fsrs_card`, `upsert_fsrs_cards`, el CAS) pasan por la versión.

## 6. P1 — el resolver elige la ocurrencia por discriminación

`classify_sense_evidence` seleccionaba la ocurrencia por **suma** de solapamientos
(`declared + other`), de modo que dos apariciones podían empatar y ganar la ambigua aunque
otra fuera inequívocamente `matched`. Ahora prioriza el **margen**
(`abs(declared_overlap - best_other_overlap)`) y el veredicto claro sobre la suma, con
desempate estable por índice. No cambia la matriz `matched`/`mismatch`/`ambiguous` ni la
regla dura de no fabricar `matched`.

## 7. Migración (aditiva e idempotente)

| Tabla | Columna | Notas |
|---|---|---|
| `listening_attempts` | `attempt_id TEXT DEFAULT ''` | + índice único **parcial** `(user_id, attempt_id) WHERE attempt_id <> ''`; las filas viejas quedan en `''` y no colisionan |
| `fsrs_cards` | `version INTEGER DEFAULT 0` | escritura optimista de fila completa |
| `listening_difficulty_evidence` | `attempt_id TEXT DEFAULT ''` | la clave de idempotencia pasa a `user:question:word:attempt_id` |

## 8. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff` (backend) | limpio |
| `pytest` backend | **3459/3459** (3450 + 9 nuevos) |
| `vitest` frontend | **1106/1106** |
| `tsc --noEmit` | limpio |
| `check_release_consistency` | OK en los **6 orígenes** (`3.93.1`) |
| Migración aditiva | verificada desde un árbol V3.92 (filas antiguas intactas, índice parcial, idempotente) |

Tests nuevos, incluidos los que la auditoría pidió expresamente:
`test_evidence_claim_rolls_back_when_fsrs_write_fails`,
`test_double_submit_same_attempt_id_is_fully_idempotent`,
`test_two_real_attempts_distinct_attempt_ids`,
`test_real_concurrency_two_answers`,
`test_full_row_cas_protects_reps_and_stability`,
`test_migration_from_v392_keeps_legacy_evidence_rows`,
`test_sense_resolver_selects_occurrence_by_discrimination`.

## 9. Honestidad y límites

1. **Nada cambia para el alumno**: la evidencia generada sigue siendo la de V3.92 (la
   política sense-aware es V3.94+). El cambio de frontend es una señal técnica nueva.
2. `mismatch` **sigue sin poder dispararse** en la ruta real (`senses=()`), igual que en
   V3.93.
3. `sense_key` sigue derivándose en tiempo de evidencia y `sense_id` estable es V3.94+.
4. El ledger **sigue creciendo** y no se poda.
5. Los **ocho gates humanos siguen `pending`**.

## 10. Qué queda para V3.94+

- `ENFORCE`: decidir `declared:none` con datos reales y aplicar `allows_difficulty_evidence`.
- Cablear las **alternativas** del diccionario para que `mismatch` sea alcanzable
  (`new_sense_exposure`).
- `MAX_MATCHES` por relevancia en vez de por orden de aparición.
- Persistir `sense_key`/`sense_id` estables en el alta.
